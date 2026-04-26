"""TagService + AccountService 标签集成测试"""
import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models.orm import Account, Base
from services.account import AccountService
from services.tag import TagService


class TagServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = self.session_factory()
        self.svc = TagService(self.db)
        self.acc_svc = AccountService(self.db)

    def tearDown(self) -> None:
        self.db.close()

    def test_create_and_list(self) -> None:
        tid_a = self.svc.create("VIP")
        tid_b = self.svc.create("待处理")

        tags = self.svc.list_all()
        names = [t["name"] for t in tags]
        self.assertEqual(sorted(names), sorted(["VIP", "待处理"]))
        self.assertTrue(all(t["accounts_count"] == 0 for t in tags))
        self.assertGreater(tid_a, 0)
        self.assertGreater(tid_b, 0)

    def test_create_duplicate_name_raises(self) -> None:
        self.svc.create("VIP")
        with self.assertRaises(ValueError):
            self.svc.create("VIP")

    def test_create_empty_name_raises(self) -> None:
        with self.assertRaises(ValueError):
            self.svc.create("")
        with self.assertRaises(ValueError):
            self.svc.create("   ")

    def test_update_renames_tag(self) -> None:
        tid = self.svc.create("草稿")
        ok = self.svc.update(tid, "正式")
        self.assertTrue(ok)
        tag = self.svc.get_by_id(tid)
        self.assertEqual(tag["name"], "正式")

    def test_update_to_existing_name_raises(self) -> None:
        a = self.svc.create("A")
        self.svc.create("B")
        with self.assertRaises(ValueError):
            self.svc.update(a, "B")

    def test_update_nonexistent_returns_false(self) -> None:
        self.assertFalse(self.svc.update(99999, "X"))

    def test_delete_returns_true_then_false(self) -> None:
        tid = self.svc.create("一次性")
        self.assertTrue(self.svc.delete(tid))
        self.assertFalse(self.svc.delete(tid))

    def test_list_all_returns_accounts_count(self) -> None:
        tid_vip = self.svc.create("VIP")
        tid_pending = self.svc.create("待处理")

        # 两个账号，账号 1 打 VIP+待处理，账号 2 只打 VIP
        a1 = Account(email="a1@example.com")
        a2 = Account(email="a2@example.com")
        self.db.add_all([a1, a2])
        self.db.flush()

        self.acc_svc.update(
            account_id=a1.id, email=a1.email, tag_ids=[tid_vip, tid_pending],
        )
        self.acc_svc.update(
            account_id=a2.id, email=a2.email, tag_ids=[tid_vip],
        )

        tags = {t["name"]: t for t in self.svc.list_all()}
        self.assertEqual(tags["VIP"]["accounts_count"], 2)
        self.assertEqual(tags["待处理"]["accounts_count"], 1)


class AccountTagFilterTests(unittest.TestCase):
    """AccountService 的标签筛选与关联管理"""

    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)
        self.db = self.session_factory()
        self.tag_svc = TagService(self.db)
        self.acc_svc = AccountService(self.db)

        self.tid_vip = self.tag_svc.create("VIP")
        self.tid_pending = self.tag_svc.create("待处理")
        self.tid_done = self.tag_svc.create("已完成")

        a1 = Account(email="a1@example.com")
        a2 = Account(email="a2@example.com")
        a3 = Account(email="a3@example.com")
        self.db.add_all([a1, a2, a3])
        self.db.flush()
        self.a1_id, self.a2_id, self.a3_id = a1.id, a2.id, a3.id

        # a1: VIP+待处理；a2: 待处理+已完成；a3: 无标签
        self.acc_svc.update(
            account_id=self.a1_id, email="a1@example.com",
            tag_ids=[self.tid_vip, self.tid_pending],
        )
        self.acc_svc.update(
            account_id=self.a2_id, email="a2@example.com",
            tag_ids=[self.tid_pending, self.tid_done],
        )

    def tearDown(self) -> None:
        self.db.close()

    def test_filter_by_single_tag(self) -> None:
        rows, total = self.acc_svc.get_all(tag_ids=[self.tid_vip])
        emails = [r["email"] for r in rows]
        self.assertEqual(total, 1)
        self.assertEqual(emails, ["a1@example.com"])

    def test_filter_by_multiple_tags_uses_or(self) -> None:
        # OR 逻辑：选 VIP + 已完成 → a1 (VIP) 和 a2 (已完成) 都应返回
        rows, total = self.acc_svc.get_all(tag_ids=[self.tid_vip, self.tid_done])
        emails = sorted(r["email"] for r in rows)
        self.assertEqual(total, 2)
        self.assertEqual(emails, ["a1@example.com", "a2@example.com"])

    def test_filter_no_match_returns_empty(self) -> None:
        # 用一个不存在的 tag id
        rows, total = self.acc_svc.get_all(tag_ids=[99999])
        self.assertEqual(total, 0)
        self.assertEqual(rows, [])

    def test_to_dict_includes_tags(self) -> None:
        a1 = self.acc_svc.get_by_id(self.a1_id)
        names = sorted(t["name"] for t in a1["tags"])
        self.assertEqual(names, ["VIP", "待处理"])

    def test_update_with_empty_list_clears_tags(self) -> None:
        self.acc_svc.update(
            account_id=self.a1_id, email="a1@example.com", tag_ids=[],
        )
        a1 = self.acc_svc.get_by_id(self.a1_id)
        self.assertEqual(a1["tags"], [])

    def test_update_with_none_keeps_tags(self) -> None:
        # tag_ids=None 表示不动，应保留原有关联
        self.acc_svc.update(
            account_id=self.a1_id, email="a1@example.com", tag_ids=None,
        )
        a1 = self.acc_svc.get_by_id(self.a1_id)
        names = sorted(t["name"] for t in a1["tags"])
        self.assertEqual(names, ["VIP", "待处理"])

    def test_delete_tag_removes_association(self) -> None:
        # 删除 VIP 后，a1 应只剩 待处理；a2/a3 不变
        self.tag_svc.delete(self.tid_vip)
        a1 = self.acc_svc.get_by_id(self.a1_id)
        a2 = self.acc_svc.get_by_id(self.a2_id)
        self.assertEqual([t["name"] for t in a1["tags"]], ["待处理"])
        self.assertEqual(sorted(t["name"] for t in a2["tags"]), ["已完成", "待处理"])
        # 账号本身应仍存在
        self.assertIsNotNone(a1)

    def test_resolve_tags_dedupes_and_skips_invalid(self) -> None:
        # 重复 ID + 无效 ID 应被忽略
        self.acc_svc.update(
            account_id=self.a3_id, email="a3@example.com",
            tag_ids=[self.tid_vip, self.tid_vip, 99999],
        )
        a3 = self.acc_svc.get_by_id(self.a3_id)
        self.assertEqual([t["name"] for t in a3["tags"]], ["VIP"])


if __name__ == "__main__":
    unittest.main()

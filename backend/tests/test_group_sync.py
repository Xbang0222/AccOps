import unittest
from contextlib import contextmanager
from types import SimpleNamespace

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.constants import ACTION_FAMILY_ACCEPT, ACTION_FAMILY_CREATE, ACTION_FAMILY_REMOVE
from models.orm import Account, Base, Group
from services.group_sync import sync_group_after_action, sync_group_from_discover


class GroupSyncTests(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        self.session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session_scope(self):
        session = self.session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    def test_create_action_creates_group_and_assigns_owner(self) -> None:
        with self.session_scope() as session:
            owner = Account(email="owner@gmail.com")
            session.add(owner)
            session.flush()
            owner_id = owner.id

        sync_group_after_action(
            ACTION_FAMILY_CREATE,
            owner_id,
            True,
            "created",
            session_factory=self.session_scope,
        )

        with self.session_scope() as session:
            owner = session.query(Account).filter(Account.id == owner_id).one()
            group = session.query(Group).filter(Group.id == owner.family_group_id).one()

            self.assertEqual(group.main_account_id, owner_id)
            self.assertEqual(owner.family_group_id, group.id)

    def test_accept_action_joins_manager_group_and_inherits_subscription(self) -> None:
        with self.session_scope() as session:
            owner = Account(
                email="owner@gmail.com",
                subscription_status="ultra",
                subscription_expiry="Mar 23, 2026",
            )
            member = Account(email="member@gmail.com")
            session.add_all([owner, member])
            session.flush()

            group = Group(name="owner family", main_account_id=owner.id)
            session.add(group)
            session.flush()

            owner.family_group_id = group.id
            owner_id = owner.id
            member_id = member.id
            group_id = group.id

        sync_group_after_action(
            ACTION_FAMILY_ACCEPT,
            member_id,
            True,
            "accepted",
            extra={"manager_account_id": owner_id},
            session_factory=self.session_scope,
        )

        with self.session_scope() as session:
            member = session.query(Account).filter(Account.id == member_id).one()
            self.assertEqual(member.family_group_id, group_id)
            self.assertEqual(member.subscription_status, "ultra")
            self.assertEqual(member.subscription_expiry, "Mar 23, 2026")

    def test_remove_action_clears_family_state(self) -> None:
        with self.session_scope() as session:
            group = Group(name="owner family")
            owner = Account(email="owner@gmail.com")
            member = Account(
                email="member@gmail.com",
                is_family_pending=True,
                subscription_status="ultra",
                subscription_expiry="Mar 23, 2026",
            )
            session.add_all([group, owner, member])
            session.flush()
            owner.family_group_id = group.id
            owner_id = owner.id
            member.family_group_id = group.id

        sync_group_after_action(
            ACTION_FAMILY_REMOVE,
            account_id=owner_id,
            success=True,
            result_msg="removed",
            extra={"member_email": "member@gmail.com"},
            session_factory=self.session_scope,
        )

        with self.session_scope() as session:
            member = session.query(Account).filter(Account.email == "member@gmail.com").one()
            self.assertIsNone(member.family_group_id)
            self.assertFalse(member.is_family_pending)
            self.assertEqual(member.subscription_status, "")
            self.assertEqual(member.subscription_expiry, "")

    def test_discover_without_group_clears_existing_family_state(self) -> None:
        with self.session_scope() as session:
            group = Group(name="owner family")
            session.add(group)
            session.flush()

            account = Account(
                email="member@gmail.com",
                family_group_id=group.id,
                is_family_pending=True,
                subscription_status="ultra",
                subscription_expiry="Mar 23, 2026",
            )
            session.add(account)
            session.flush()
            account_id = account.id

        discover_result = SimpleNamespace(
            success=True,
            has_group=False,
            role="member",
            members=[],
            member_count=0,
        )

        sync_group_from_discover(
            account_id,
            discover_result,
            session_factory=self.session_scope,
        )

        with self.session_scope() as session:
            account = session.query(Account).filter(Account.id == account_id).one()
            self.assertIsNone(account.family_group_id)
            self.assertFalse(account.is_family_pending)
            self.assertEqual(account.subscription_status, "")
            self.assertEqual(account.subscription_expiry, "")


if __name__ == "__main__":
    unittest.main()

"""Google Family Group batchexecute RPC 封装 (纯 httpx)

架构: 浏览器登录 → 提取 Cookies → httpx 纯 HTTP 操作

纯 HTTP 操作 (无需浏览器):
  - query_status()      查询家庭组状态     DmVhMc
  - query_members()     查询成员列表       V2esPe
  - create_family()     创建家庭组         nKULBd → Wffnob → c5gch
  - send_invite()       发送邀请           B3vhdd → xN05r
  - accept_invite()     接受邀请           SZ903d

需要 rapt token 的操作 (浏览器做密码重验证, RPC 本身仍是纯 HTTP):
  - remove_member()     移除成员           Csu7b
  - leave_family()      退出家庭组         Csu7b + "me"
  - delete_family()     删除家庭组         hQih3e
"""

import json
import logging
import re
from typing import Any
from urllib.parse import urlencode

import httpx

from core.constants import (
    FAMILY_BASE_URL as BASE_URL,
)
from core.constants import (
    FAMILY_BATCHEXECUTE_URL as BATCHEXECUTE_URL,
)
from core.constants import (
    FAMILY_DEFAULT_REQID,
    FAMILY_HTTP_TIMEOUT,
    FAMILY_USER_AGENT,
    RPC_ACCEPT_INVITE,
    RPC_CANCEL_INVITE,
    RPC_CREATE_STEP1,
    RPC_CREATE_STEP2,
    RPC_CREATE_STEP3,
    RPC_DELETE_FAMILY,
    RPC_INVITE_INIT,
    RPC_INVITE_SEND,
    RPC_QUERY_MEMBERS,
    RPC_QUERY_STATUS,
    RPC_REMOVE_MEMBER,
    WIZ_TOKEN_AT,
    WIZ_TOKEN_BL,
    WIZ_TOKEN_FSID,
)
from core.constants import (
    FAMILY_ROLE_ADMIN as ROLE_ADMIN,
)

logger = logging.getLogger(__name__)


class TokenError(Exception):
    """页面 token 提取失败"""


class RPCError(Exception):
    """batchexecute RPC 调用失败"""

    def __init__(self, rpc_id: str, status_code: int, detail: str = ""):
        self.rpc_id = rpc_id
        self.status_code = status_code
        super().__init__(f"[{rpc_id}] HTTP {status_code}" + (f": {detail}" if detail else ""))


class NoInvitationError(Exception):
    """没有待接受的邀请"""


# ── 工具函数 ──────────────────────────────────────────────

def parse_response(text: str, rpc_id: str) -> Any:
    """解析 batchexecute 响应, 提取 RPC 返回的 JSON 数据"""
    clean = text[4:] if text.startswith(")]}'") else text
    for line in clean.split("\n"):
        line = line.strip()
        if not line or line.isdigit():
            continue
        if rpc_id not in line:
            continue
        try:
            outer = json.loads(line)
            for item in outer:
                if isinstance(item, list) and len(item) > 2 and item[1] == rpc_id:
                    inner = item[2]
                    return json.loads(inner) if isinstance(inner, str) else inner
        except (json.JSONDecodeError, IndexError, TypeError):
            continue
    return None


def extract_tokens(html: str) -> dict[str, str]:
    """从页面 HTML 的 WIZ_global_data 中提取认证 token"""
    tokens: dict[str, str] = {}
    for key, pattern in {
        "at": rf'"{WIZ_TOKEN_AT}":"([^"]+)"',
        "f.sid": rf'"{WIZ_TOKEN_FSID}":"([^"]+)"',
        "bl": rf'"{WIZ_TOKEN_BL}":"([^"]+)"',
    }.items():
        m = re.search(pattern, html)
        if m:
            tokens[key] = m.group(1)
    return tokens


# ── 核心 API 类 ───────────────────────────────────────────


class FamilyAPI:
    """Google Family Group 纯 HTTP API

    Usage:
        with FamilyAPI(cookies) as api:
            status = api.query_status()
            members = api.query_members()
            api.create_family()
            api.send_invite("someone@gmail.com")
    """

    def __init__(self, cookies: dict[str, str]):
        self.client = httpx.Client(
            cookies=cookies,
            headers={
                "User-Agent": FAMILY_USER_AGENT,
                "Accept-Language": "en-US,en;q=0.9",
            },
            follow_redirects=True,
            timeout=FAMILY_HTTP_TIMEOUT,
        )
        self._tokens: dict[str, str] = {}
        self.refresh_tokens()

    # ── 内部方法 ──

    def refresh_tokens(self, source_path: str = "/family/details") -> None:
        """访问页面并提取 WIZ_global_data token (at, f.sid, bl)"""
        resp = self.client.get(f"{BASE_URL}{source_path}")
        resp.raise_for_status()
        self._tokens = extract_tokens(resp.text)
        if "at" not in self._tokens:
            raise TokenError(f"无法从 {source_path} 提取 XSRF token")
        logger.debug("tokens refreshed from %s", source_path)

    def _rpc(
        self,
        rpc_id: str,
        payload: str,
        source_path: str = "/family/details",
        rapt: str | None = None,
        seq: str = "generic",
    ) -> dict[str, Any]:
        """发送 batchexecute RPC 请求"""
        params: dict[str, str] = {
            "rpcids": rpc_id,
            "source-path": source_path,
            "f.sid": self._tokens["f.sid"],
            "bl": self._tokens["bl"],
            "hl": "en",
            "soc-app": "1",
            "soc-platform": "1",
            "soc-device": "1",
            "_reqid": FAMILY_DEFAULT_REQID,
            "rt": "c",
        }
        if rapt:
            params["rapt"] = rapt

        url = f"{BATCHEXECUTE_URL}?{urlencode(params)}"
        body = urlencode({
            "f.req": json.dumps([[[rpc_id, payload, None, seq]]]),
            "at": self._tokens["at"],
        })

        resp = self.client.post(
            url,
            content=body,
            headers={
                "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
                "X-Same-Domain": "1",
                "Origin": BASE_URL,
                "Referer": f"{BASE_URL}{source_path}",
            },
        )

        parsed = parse_response(resp.text, rpc_id)
        logger.info("[%s] HTTP %d, raw_len=%d", rpc_id, resp.status_code, len(resp.text))

        return {"status_code": resp.status_code, "raw": resp.text, "parsed": parsed}

    # ── 纯 HTTP 操作 ──

    def query_status(self) -> dict:
        """查询家庭组状态 (DmVhMc)"""
        data = self._rpc(RPC_QUERY_STATUS, "[]")["parsed"]
        if data is None:
            return {"has_family": False, "remaining_slots": None}
        return {
            "has_family": bool(data[0]),
            "remaining_slots": data[3] if data[0] else None,
        }

    def query_subscription(self) -> dict:
        """查询账号订阅状态 (免费/Ultra)

        访问 https://myaccount.google.com/subscriptions 页面并解析 HTML。
        页面为服务端渲染, 无 batchexecute RPC。

        返回: {'status': 'free'|'ultra', 'title': '订阅名称'}
        """
        try:
            resp = self.client.get(f"{BASE_URL}/subscriptions")
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[subscription] 获取订阅页面失败: {e}")
            return {"status": "free", "title": ""}

        html = resp.text
        status = "free"
        title = ""
        renew_date = ""

        # Ultra 特征: 页面含 "AI Ultra"
        if "AI Ultra" in html:
            status = "ultra"
            # 提取具体计划名, 如 "Google AI Ultra (30 TB)"
            m = re.search(r'class="SeZS9d"[^>]*>([^<]*AI Ultra[^<]*)<', html)
            title = m.group(1).strip() if m else "Google One AI Ultra"
            # 提取续期日期, 如 "Renews on Mar 23, 2026" → "2026年3月23日"
            m = re.search(r'Renews on ([A-Za-z]+ \d{1,2}, \d{4})', html)
            if m:
                from datetime import datetime as _dt
                try:
                    d = _dt.strptime(m.group(1), "%b %d, %Y")
                    renew_date = f"{d.year}年{d.month}月{d.day}日"
                except ValueError:
                    renew_date = m.group(1)

        return {"status": status, "title": title, "renew_date": renew_date}

    def query_members(self) -> dict:
        """查询成员列表 (V2esPe)

        pending 判断逻辑 (基于实测):
          - m[1] 只区分管理员(1) vs 非管理员(3), 无法区分已接受/待接受
          - pending 真正标志: m[2]==True (布尔) 且 m[9] 包含邀请数据
          - 已接受成员: len(m)=19, 无 m[2], 无 m[9]
          - 待接受成员: len(m)=10, m[2]=True, m[9]=[invite_id, null, email, ...]
        """
        raw_result = self._rpc(RPC_QUERY_MEMBERS, "[]")
        data = raw_result["parsed"]
        no_family = {
            "has_family": False,
            "members": [],
            "member_count": 0,
            "current_user_id": data[2] if data else None,
            "is_admin": False,
            "family_group_id": None,
            "remaining_slots": 0,
        }
        if data is None:
            return no_family
        if not isinstance(data[0], list) or data[0][1] is None:
            return no_family

        members = []
        for m in data[0][1]:
            info = m[0]
            # pending 判断: m[2]==True 或 m[9] 存在邀请数据
            is_pending = (len(m) > 2 and m[2] is True) or (len(m) > 9 and m[9] is not None)
            role = m[1]
            if role == ROLE_ADMIN:
                role_name = "admin"
            elif is_pending:
                role_name = "pending"
            else:
                role_name = "member"
            # email 来源: 已接受成员在 info[5], pending 成员在 m[9][2]
            email = info[5] if len(info) > 5 and info[5] else None
            invitation_id = None
            if is_pending and len(m) > 9 and isinstance(m[9], list):
                if len(m[9]) > 0 and m[9][0] is not None:
                    invitation_id = str(m[9][0])
                if not email and len(m[9]) > 2:
                    email = m[9][2]
            members.append({
                "name": info[0],
                "user_id": info[1],
                "avatar_url": info[2] if len(info) > 2 else None,
                "email": email,
                "role": role,
                "role_name": role_name,
                "pending": is_pending,
                "invitation_id": invitation_id,
            })

        return {
            "has_family": True,
            "members": members,
            "member_count": sum(1 for m in members if not m["pending"]),
            "current_user_id": data[2],
            "is_admin": bool(data[4]),
            "family_group_id": data[0][8] if len(data[0]) > 8 else None,
            "remaining_slots": data[3],
        }

    def create_family(self) -> bool:
        """创建家庭组 (nKULBd → Wffnob → c5gch)"""
        path = "/family/createconfirmation"

        self._rpc(RPC_CREATE_STEP1, "[]", path, seq="1")

        r = self._rpc(RPC_CREATE_STEP2, '[[null,null,["v2",18,null,["googleaccount"]]]]', path)
        raw = r["raw"].replace('\\"', '"').replace("\\\\", "\\")
        m = re.search(r"AP[A-Za-z0-9+/=_-]{20,}", raw)
        if not m:
            raise RPCError(RPC_CREATE_STEP2, r["status_code"], "无法提取加密 token")
        token = m.group(0)

        payload = json.dumps([[None, None, ["v2", 18, None, ["googleaccount"]]], [token]])
        self._rpc(RPC_CREATE_STEP3, payload, path)

        return self.query_status()["has_family"]

    def send_invite(self, email: str) -> dict:
        """发送家庭组邀请 (B3vhdd → xN05r)"""
        path = "/family/invitemembers"

        self._rpc(RPC_INVITE_INIT, '[[null,null,["v2",18,null,["googleaccount"]]]]', path)

        payload = json.dumps([
            [None, None, ["v2", 18, None, ["googleaccount"]]],
            [[None, [email], None, 3, None, None, None, None, None, 1, email]],
        ])
        r = self._rpc(RPC_INVITE_SEND, payload, path)

        invitation_id = None
        if r["parsed"] and isinstance(r["parsed"], list) and len(r["parsed"]) > 1:
            try:
                invitation_id = r["parsed"][1][0][0]
            except (IndexError, TypeError):
                pass

        if r["status_code"] != 200:
            return {"success": False, "invitation_id": None,
                    "error": f"HTTP {r['status_code']}"}
        if not invitation_id:
            logger.warning(f"[send_invite] HTTP 200 但无 invitation_id, parsed={r['parsed']}")
            return {"success": False, "invitation_id": None,
                    "error": "Google 返回 200 但未生成邀请 (cookies 失效/配额超限/对方已在组/家庭组已满)"}

        return {"success": True, "invitation_id": invitation_id}

    def accept_invite(self) -> dict:
        """接受待处理的家庭组邀请 (SZ903d)"""
        resp = self.client.get(f"{BASE_URL}/family/pendinginvitations")
        html = resp.text

        # Google 会用 HTML 实体编码 URL (&#47; = /), 先解码再匹配
        import html as html_mod
        decoded = html_mod.unescape(html)

        token = None
        m = re.search(r"families\.google\.com/join/promo/t/([A-Za-z0-9_-]+)", decoded)
        if m:
            token = m.group(1)
        if not token:
            m = re.search(r"/family/join/t/([A-Za-z0-9_-]+)", decoded)
            if m:
                token = m.group(1)

        if not token:
            raise NoInvitationError("pendinginvitations 页面未找到邀请链接")

        join_path = f"/family/join/t/{token}"
        self.refresh_tokens(join_path)

        payload = json.dumps([
            [None, None, ["v2", 18, None, ["googleaccount"]]],
            None, None, None,
            token,
        ])
        r = self._rpc(RPC_ACCEPT_INVITE, payload, join_path)

        logger.debug(f"[accept_invite] SZ903d parsed={r['parsed']}")

        family_group_id = None
        if r["parsed"] and isinstance(r["parsed"], list) and len(r["parsed"]) > 1:
            try:
                family_group_id = r["parsed"][1][0][0]
            except (IndexError, TypeError):
                pass

        # HTTP 200 但无 family_group_id 说明加入失败 (地区不同、账号受限等)
        if r["status_code"] == 200 and not family_group_id:
            return {"success": False, "family_group_id": None,
                    "error": "加入失败, 可能与管理员不在同一国家/地区"}

        return {"success": r["status_code"] == 200 and bool(family_group_id),
                "family_group_id": family_group_id}

    # ── 需要 rapt token 的操作 ──

    def cancel_invite(self, invitation_id: str) -> bool:
        """撤销待接受的邀请 (fijTGe) — 管理员操作, 不需要 rapt

        Args:
            invitation_id: 邀请 ID (从 send_invite 返回或 query_members 的 pending 成员数据中获取)
        """
        path = f"/family/member/i/{invitation_id}"
        self.refresh_tokens(path)

        payload = json.dumps([
            [None, None, ["v2", 18, None, ["googleaccount"]]],
            invitation_id,
        ])
        r = self._rpc(RPC_CANCEL_INVITE, payload, path)
        ok = r["status_code"] == 200
        logger.info(f"[cancel_invite] invitation_id={invitation_id}, HTTP={r['status_code']}, parsed={r['parsed']}")
        return ok

    def remove_member(self, member_user_id: str, rapt: str) -> bool:
        """移除家庭组成员 (Csu7b) — 管理员操作"""
        payload = json.dumps([
            [None, None, ["v2", 18, None, ["googleaccount"]]],
            member_user_id,
        ])
        r = self._rpc(RPC_REMOVE_MEMBER, payload, f"/family/remove/g/{member_user_id}", rapt=rapt)
        return r["status_code"] == 200

    def leave_family(self, rapt: str) -> bool:
        """退出家庭组 (Csu7b + "me") — 普通成员操作"""
        payload = json.dumps([
            [None, None, ["v2", 18, None, ["googleaccount"]]],
            "me",
        ])
        r = self._rpc(RPC_REMOVE_MEMBER, payload, "/family/leave", rapt=rapt)
        return r["status_code"] == 200

    def delete_family(self, rapt: str) -> bool:
        """删除家庭组 (hQih3e) — 管理员操作"""
        r = self._rpc(RPC_DELETE_FAMILY, "[]", "/family/delete", rapt=rapt)
        return r["status_code"] == 200

    # ── 生命周期 ──

    def close(self) -> None:
        self.client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

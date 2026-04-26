"""CLIProxyAPI 集成: 上传 OAuth 凭证到管理 API"""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass

import httpx

from models.orm import Account
from services.runtime_config import get_str


@dataclass(frozen=True)
class UploadResult:
    account_id: int
    email: str
    success: bool
    message: str


def _load_config() -> tuple[str, str]:
    base_url = get_str("cliproxy_base_url").strip().rstrip("/")
    api_key = get_str("cliproxy_api_key").strip()
    return base_url, api_key


def _build_payload(account: Account) -> dict:
    raw = (account.oauth_credential_json or "").strip()
    if not raw:
        raise ValueError("账号未完成 OAuth 验证")
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("OAuth 凭证格式异常")
    payload.setdefault("email", account.email)
    payload.setdefault("type", "antigravity")
    return payload


async def _upload_one(
    client: httpx.AsyncClient,
    base_url: str,
    api_key: str,
    account: Account,
) -> UploadResult:
    try:
        payload = _build_payload(account)
    except (ValueError, json.JSONDecodeError) as e:
        return UploadResult(account.id, account.email, False, str(e))
    try:
        resp = await client.post(
            f"{base_url}/v0/management/auth-files",
            params={"name": f"{account.email}.json"},
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            content=json.dumps(payload),
        )
    except httpx.RequestError as e:
        return UploadResult(account.id, account.email, False, f"网络错误: {e}")
    if 200 <= resp.status_code < 300:
        return UploadResult(account.id, account.email, True, "已上传")
    return UploadResult(
        account.id,
        account.email,
        False,
        f"HTTP {resp.status_code}: {resp.text[:200]}",
    )


async def upload_accounts(
    db, account_ids: list[int]
) -> list[UploadResult]:
    base_url, api_key = _load_config()
    if not base_url or not api_key:
        raise ValueError(
            "CLIProxyAPI 未配置: 请先在系统设置中填写 Base URL 和 API Key"
        )
    accounts = db.query(Account).filter(Account.id.in_(account_ids)).all()
    if not accounts:
        return []
    async with httpx.AsyncClient(timeout=30.0) as client:
        return list(
            await asyncio.gather(
                *[_upload_one(client, base_url, api_key, a) for a in accounts]
            )
        )


async def check_status() -> dict:
    base_url, api_key = _load_config()
    if not base_url or not api_key:
        return {"configured": False, "reachable": False, "message": "未配置"}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{base_url}/v0/management/auth-files",
                headers={"Authorization": f"Bearer {api_key}"},
            )
        ok = 200 <= resp.status_code < 300
        return {
            "configured": True,
            "reachable": ok,
            "status_code": resp.status_code,
            "message": "连接成功" if ok else f"HTTP {resp.status_code}",
        }
    except httpx.RequestError as e:
        return {
            "configured": True,
            "reachable": False,
            "message": f"网络错误: {e}",
        }

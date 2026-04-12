"""OAuth 流程辅助函数。"""
from __future__ import annotations

import json
import logging
import re
import time
import uuid
from typing import Optional, Tuple

import httpx

from core.constants import (
    ANTIGRAVITY_API_CLIENT as ANTIGRAVITY_API_CLIENT,
    ANTIGRAVITY_API_ENDPOINT as API_ENDPOINT,
    ANTIGRAVITY_API_USER_AGENT as API_USER_AGENT,
    ANTIGRAVITY_API_VERSION as API_VERSION,
    ANTIGRAVITY_CLIENT_METADATA as CLIENT_METADATA,
    ANTIGRAVITY_DAILY_ENDPOINT,
    ANTIGRAVITY_DEFAULT_MODEL,
    ANTIGRAVITY_STREAM_PATH,
    FAMILY_HTTP_TIMEOUT,
    OAUTH_AUTH_ENDPOINT as AUTH_ENDPOINT,
    OAUTH_CLIENT_ID as CLIENT_ID,
    OAUTH_CLIENT_SECRET as CLIENT_SECRET,
    OAUTH_REDIRECT_URI as REDIRECT_URI,
    OAUTH_SCOPES as SCOPES,
    OAUTH_TOKEN_ENDPOINT as TOKEN_ENDPOINT,
    OAUTH_USERINFO_ENDPOINT as USERINFO_ENDPOINT,
    SEL_OAUTH_ALLOW,
    SEL_OAUTH_ALLOW_CN,
    SEL_OAUTH_APPROVE,
    SEL_OAUTH_BTN_ALLOW,
    SEL_OAUTH_BTN_CONTINUE,
    SEL_OAUTH_CONTINUE,
    SEL_OAUTH_CONTINUE_CN,
    SEL_PASSWORD_INPUT,
    SEL_TOTP_INPUT,
)
from services.auth_steps import enter_password, enter_totp
from services.page_wait import safe_ele, safe_click, safe_url

logger = logging.getLogger(__name__)


def build_auth_url(state: str) -> str:
    """构建 Google OAuth 授权 URL。"""
    from urllib.parse import urlencode

    params = {
        "access_type": "offline",
        "client_id": CLIENT_ID,
        "prompt": "consent",
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "state": state,
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}"


def exchange_code_for_tokens(code: str) -> dict:
    """用 authorization code 换取 access_token + refresh_token。"""
    response = httpx.post(
        TOKEN_ENDPOINT,
        data={
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=FAMILY_HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(f"Token 交换失败: HTTP {response.status_code} - {response.text[:200]}")
    return response.json()


def fetch_user_info(access_token: str) -> str:
    """用 access_token 获取用户邮箱。"""
    response = httpx.get(
        USERINFO_ENDPOINT,
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=FAMILY_HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        raise RuntimeError(f"获取用户信息失败: HTTP {response.status_code}")
    return response.json().get("email", "")


def fetch_project_id(access_token: str) -> str:
    """通过 loadCodeAssist 获取 GCP project ID。"""
    response = httpx.post(
        f"{API_ENDPOINT}/{API_VERSION}:loadCodeAssist",
        json={
            "metadata": {
                "ideType": "ANTIGRAVITY",
                "platform": "PLATFORM_UNSPECIFIED",
                "pluginType": "GEMINI",
            }
        },
        headers=_build_api_headers(access_token),
        timeout=FAMILY_HTTP_TIMEOUT,
    )
    if response.status_code != 200:
        return onboard_user(access_token)

    data = response.json()
    project_id = ""
    project = data.get("cloudaicompanionProject")
    if isinstance(project, str):
        project_id = project.strip()
    elif isinstance(project, dict):
        project_id = project.get("id", "").strip()

    if project_id:
        return project_id

    tier_id = "legacy-tier"
    for tier in data.get("allowedTiers", []):
        if isinstance(tier, dict) and tier.get("isDefault"):
            default_tier_id = tier.get("id", "").strip()
            if default_tier_id:
                tier_id = default_tier_id
                break

    return onboard_user(access_token, tier_id)


def onboard_user(access_token: str, tier_id: str = "legacy-tier") -> str:
    """通过 onboardUser 获取 project ID。"""
    for _ in range(5):
        response = httpx.post(
            f"{API_ENDPOINT}/{API_VERSION}:onboardUser",
            json={
                "tierId": tier_id,
                "metadata": {
                    "ideType": "ANTIGRAVITY",
                    "platform": "PLATFORM_UNSPECIFIED",
                    "pluginType": "GEMINI",
                },
            },
            headers=_build_api_headers(access_token),
            timeout=FAMILY_HTTP_TIMEOUT,
        )
        if response.status_code != 200:
            raise RuntimeError(f"onboardUser 失败: HTTP {response.status_code} - {response.text[:200]}")

        data = response.json()
        if data.get("done"):
            response_data = data.get("response", {})
            project = response_data.get("cloudaicompanionProject", "")
            if isinstance(project, dict):
                return project.get("id", "").strip()
            if isinstance(project, str):
                return project.strip()
            return ""

        time.sleep(2)

    return ""


def probe_api(access_token: str, project_id: str = "") -> Tuple[bool, str, Optional[str]]:
    """探测 API 是否可用。"""
    response = httpx.post(
        f"{ANTIGRAVITY_DAILY_ENDPOINT}{ANTIGRAVITY_STREAM_PATH}",
        json={
            "model": ANTIGRAVITY_DEFAULT_MODEL,
            "userAgent": "antigravity",
            "requestType": "agent",
            "project": project_id or "probe-test-00000",
            "requestId": f"agent-{uuid.uuid4()}",
            "request": {
                "sessionId": f"-{int(time.time() * 1000)}",
                "contents": [{"role": "user", "parts": [{"text": "hi"}]}],
                "generationConfig": {"maxOutputTokens": 32},
            },
        },
        headers=_build_api_headers(access_token),
        timeout=FAMILY_HTTP_TIMEOUT,
    )

    if response.status_code == 200:
        return True, "API 可用", None

    error_text = response.text
    logger.warning("API 探测失败: HTTP %s - %s", response.status_code, error_text[:500])

    validation_url = extract_validation_url(error_text)
    if validation_url:
        return False, "需要账号验证", validation_url

    return False, f"HTTP {response.status_code}: {error_text[:500]}", None


def extract_validation_url(error_text: str) -> Optional[str]:
    """从 Google API 403 错误响应中提取 validation_url。"""
    try:
        data = json.loads(error_text)
        error_obj = data[0] if isinstance(data, list) else data
        details = error_obj.get("error", {}).get("details", [])
        for detail in details:
            metadata = detail.get("metadata", {})
            validation_url = metadata.get("validation_url")
            if validation_url:
                return validation_url

            for link in detail.get("links", []):
                link_url = link.get("url", "")
                if "accounts.google.com" in link_url:
                    return link_url
    except Exception:
        pass

    match = re.search(r'https?://accounts\.google\.com/[^\s"\'<>]+', error_text)
    if match:
        return match.group(0).rstrip('.,;!)')
    return None


def check_for_code(url: str) -> Optional[str]:
    """从 URL 中提取 authorization code。"""
    if "localhost:51121/oauth-callback" in url or ("code=" in url and "accounts.google" not in url):
        match = re.search(r'[?&]code=([^&]+)', url)
        if match:
            return match.group(1)
    return None


def check_for_error(url: str) -> Optional[str]:
    """从 URL 中提取 error。"""
    if "error=" in url and "localhost" in url:
        match = re.search(r'[?&]error=([^&]+)', url)
        return match.group(1) if match else "unknown"
    return None


def is_password_page(page) -> bool:
    """检测是否在密码输入页面。"""
    url = safe_url(page)
    if "challenge/pwd" in url or "signin/v2/challenge/password" in url:
        return True
    password_input = safe_ele(page, SEL_PASSWORD_INPUT, timeout=0.5) or safe_ele(page, 'input[type="password"]', timeout=0.5)
    return bool(password_input)


def is_totp_page(page) -> bool:
    """检测是否在 2FA/TOTP 验证页面。"""
    url = safe_url(page)
    if "challenge/totp" in url or "challenge/selection" in url:
        return True
    totp_input = safe_ele(page, SEL_TOTP_INPUT, timeout=0.5) or safe_ele(page, 'input[type="tel"]', timeout=0.5)
    return bool(totp_input)


def handle_password(page, password: str, tracker) -> bool:
    """处理密码输入页面。"""
    ok = enter_password(page, password, timeout=3)
    if not ok:
        tracker.step("密码验证", "fail", "找不到密码输入框")
        return False
    tracker.step("密码验证", "ok")
    return True


def handle_totp(page, totp_secret: str, tracker) -> bool:
    """处理 2FA/TOTP 验证页面。"""
    if not totp_secret:
        tracker.step("2FA 验证", "fail", "需要 2FA 但账号未配置 TOTP")
        return False

    ok = enter_totp(page, totp_secret, timeout=5)
    if not ok:
        tracker.step("2FA 验证", "fail", "找不到 TOTP 输入框")
        return False

    tracker.step("2FA 验证", "ok", "已输入验证码")
    return True


def try_click_consent_buttons(page) -> bool:
    """尝试点击 OAuth 同意页面上的各种按钮。"""
    selectors = [
        SEL_OAUTH_APPROVE,
        SEL_OAUTH_ALLOW,
        SEL_OAUTH_ALLOW_CN,
        SEL_OAUTH_CONTINUE,
        SEL_OAUTH_CONTINUE_CN,
        SEL_OAUTH_BTN_ALLOW,
        SEL_OAUTH_BTN_CONTINUE,
    ]
    for selector in selectors:
        button = safe_ele(page, selector, timeout=0.5, retries=1)
        if button:
            if safe_click(button, page=page):
                return True
    return False


def _build_api_headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
        "User-Agent": API_USER_AGENT,
        "X-Goog-Api-Client": ANTIGRAVITY_API_CLIENT,
        "Client-Metadata": CLIENT_METADATA,
    }

"""系统设置路由 — 通过 services.runtime_config 单一数据源读写。"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from deps import verify_token
from services import runtime_config

router = APIRouter(
    prefix="/settings",
    tags=["系统设置"],
    dependencies=[Depends(verify_token)],
)


class SettingsResponse(BaseModel):
    debug_mode: bool
    headless_mode: bool
    default_sms_provider_id: str
    age_verify_enabled: bool
    card_number: str
    card_expiry: str
    card_cvv: str
    card_zip: str
    cliproxy_base_url: str
    cliproxy_api_key: str


class SettingsUpdateRequest(BaseModel):
    debug_mode: bool | None = None
    headless_mode: bool | None = None
    default_sms_provider_id: str | None = None
    age_verify_enabled: bool | None = None
    card_number: str | None = None
    card_expiry: str | None = None
    card_cvv: str | None = None
    card_zip: str | None = None
    cliproxy_base_url: str | None = None
    cliproxy_api_key: str | None = None


_BOOL_KEYS = ("debug_mode", "headless_mode", "age_verify_enabled")
_STR_KEYS = (
    "default_sms_provider_id",
    "card_number",
    "card_expiry",
    "card_cvv",
    "card_zip",
    "cliproxy_base_url",
    "cliproxy_api_key",
)


def _build_response() -> SettingsResponse:
    return SettingsResponse(
        debug_mode=runtime_config.get_bool("debug_mode"),
        headless_mode=runtime_config.get_bool("headless_mode"),
        default_sms_provider_id=runtime_config.get_str("default_sms_provider_id"),
        age_verify_enabled=runtime_config.get_bool("age_verify_enabled"),
        card_number=runtime_config.get_str("card_number"),
        card_expiry=runtime_config.get_str("card_expiry"),
        card_cvv=runtime_config.get_str("card_cvv"),
        card_zip=runtime_config.get_str("card_zip"),
        cliproxy_base_url=runtime_config.get_str("cliproxy_base_url"),
        cliproxy_api_key=runtime_config.get_str("cliproxy_api_key"),
    )


@router.get("")
def get_settings():
    """获取所有系统设置"""
    return _build_response()


@router.put("")
def update_settings(req: SettingsUpdateRequest):
    """更新系统设置"""
    payload = req.model_dump(exclude_unset=True)
    for key in _BOOL_KEYS:
        if key in payload and payload[key] is not None:
            runtime_config.set_value(key, "true" if payload[key] else "false")
    for key in _STR_KEYS:
        if key in payload and payload[key] is not None:
            runtime_config.set_value(key, payload[key])
    return _build_response()

"""Pydantic 请求/响应模型 (Schemas)"""

from pydantic import BaseModel, Field

TAG_NAME_MAX_LENGTH = 32


# ---- 认证 ----

class LoginRequest(BaseModel):
    password: str


class SetPasswordRequest(BaseModel):
    password: str
    confirm_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


# ---- 账号 ----

class AccountBase(BaseModel):
    email: str
    password: str | None = ""
    recovery_email: str | None = ""
    totp_secret: str | None = ""
    group_id: int | None = None
    notes: str | None = ""
    tag_ids: list[int] | None = None


class AccountCreate(AccountBase):
    pass


class AccountUpdate(AccountBase):
    pass


class AccountImportRequest(BaseModel):
    """批量导入账号请求

    格式: 邮箱----密码----辅助邮箱----2FA密钥----短信验证链接(可选)
    每行一个账号, 用 ---- 分隔字段
    """
    text: str
    notes: str | None = ""


# ---- 标签 ----

class TagBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=TAG_NAME_MAX_LENGTH)


class TagCreate(TagBase):
    pass


class TagUpdate(TagBase):
    pass


class TagOut(BaseModel):
    id: int
    name: str
    sort_order: int = 0
    accounts_count: int = 0
    created_at: str | None = None
    updated_at: str | None = None


class TagListOut(BaseModel):
    tags: list[TagOut]


class TagCreateOut(BaseModel):
    id: int
    message: str


class MessageOut(BaseModel):
    message: str


# ---- 分组 ----

class GroupCreate(BaseModel):
    name: str
    notes: str | None = ""


class GroupUpdate(BaseModel):
    name: str
    main_account_id: int | None = None
    notes: str | None = ""


# ---- 浏览器配置 ----

class BrowserProfileBase(BaseModel):
    name: str
    account_id: int | None = None
    proxy_type: str | None = ""
    proxy_host: str | None = ""
    proxy_port: int | None = None
    proxy_username: str | None = ""
    proxy_password: str | None = ""
    user_agent: str | None = ""
    os_type: str | None = "macos"
    timezone: str | None = ""
    language: str | None = "en-US"
    screen_width: int | None = 1920
    screen_height: int | None = 1080
    webrtc_disabled: bool | None = True
    notes: str | None = ""


class BrowserProfileCreate(BrowserProfileBase):
    pass


class BrowserProfileUpdate(BrowserProfileBase):
    pass

"""AccOps 全局常量定义

按功能域分组, 消除散落在各模块中的魔法值。
"""

# ============================================================
# Google Family API (services/family_api.py)
# ============================================================

# -- Base URLs --
FAMILY_BASE_URL = "https://myaccount.google.com"
FAMILY_BATCHEXECUTE_URL = f"{FAMILY_BASE_URL}/_/AccountSettingsUi/data/batchexecute"

# -- RPC IDs --
RPC_QUERY_STATUS = "DmVhMc"          # 查询家庭组状态
RPC_QUERY_MEMBERS = "V2esPe"         # 查询成员列表
RPC_CREATE_STEP1 = "nKULBd"          # 创建家庭组 - 第1步
RPC_CREATE_STEP2 = "Wffnob"          # 创建家庭组 - 第2步 (获取加密 token)
RPC_CREATE_STEP3 = "c5gch"           # 创建家庭组 - 第3步 (确认创建)
RPC_INVITE_INIT = "B3vhdd"           # 发送邀请 - 初始化
RPC_INVITE_SEND = "xN05r"            # 发送邀请 - 执行
RPC_ACCEPT_INVITE = "SZ903d"         # 接受邀请
RPC_CANCEL_INVITE = "fijTGe"         # 撤销邀请
RPC_REMOVE_MEMBER = "Csu7b"          # 移除成员 / 退出家庭组
RPC_DELETE_FAMILY = "hQih3e"         # 删除家庭组

# -- WIZ token keys (WIZ_global_data 中的字段名) --
WIZ_TOKEN_AT = "SNlM0e"             # XSRF token
WIZ_TOKEN_FSID = "FdrFJe"           # f.sid
WIZ_TOKEN_BL = "cfb2h"              # bl

# -- Family roles --
FAMILY_ROLE_ADMIN = 1
FAMILY_ROLE_MEMBER = 2
FAMILY_ROLE_NAMES = {FAMILY_ROLE_ADMIN: "admin", FAMILY_ROLE_MEMBER: "member"}

# -- HTTP client defaults --
FAMILY_USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/131.0.0.0 Safari/537.36"
)
FAMILY_HTTP_TIMEOUT = 30
FAMILY_DEFAULT_REQID = "100001"

# ============================================================
# Browser Automation (services/browser.py)
# ============================================================

# -- CSS Selectors: Login --
SEL_EMAIL_INPUT = "#identifierId"
SEL_EMAIL_NEXT = "#identifierNext"
SEL_PASSWORD_INPUT = "@name=Passwd"
SEL_PASSWORD_NEXT = "#passwordNext"
SEL_TOTP_INPUT = "#totpPin"
SEL_TOTP_NEXT = "#totpNext"

# -- CSS Selectors: Skip buttons (登录后中间页) --
SEL_SKIP_LATER_CN = "text:以后再说"
SEL_SKIP_NOT_NOW = "text:Not now"
SEL_SKIP = "text:Skip"
SEL_SKIP_LATER_CN2 = "text:稍后再说"

# -- Browser port range --
BROWSER_PORT_MIN = 9600
BROWSER_PORT_MAX = 59600

# ============================================================
# OAuth (services/oauth.py)
# ============================================================

# -- OAuth client credentials (从环境变量读取) --
import os as _os
OAUTH_CLIENT_ID = _os.environ.get(
    "GAM_OAUTH_CLIENT_ID",
    "1071006060591-tmhssin2h21lcre235vtolojh4g403ep.apps.googleusercontent.com",
)
OAUTH_CLIENT_SECRET = _os.environ.get("GAM_OAUTH_CLIENT_SECRET", "")

OAUTH_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
    "https://www.googleapis.com/auth/cclog",
    "https://www.googleapis.com/auth/experimentsandconfigs",
]

# -- OAuth endpoints --
OAUTH_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
OAUTH_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
OAUTH_USERINFO_ENDPOINT = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"
OAUTH_REDIRECT_URI = "http://localhost:51121/oauth-callback"

# -- Antigravity API --
ANTIGRAVITY_API_ENDPOINT = "https://cloudcode-pa.googleapis.com"
ANTIGRAVITY_API_VERSION = "v1internal"
ANTIGRAVITY_DAILY_ENDPOINT = "https://daily-cloudcode-pa.googleapis.com"
ANTIGRAVITY_STREAM_PATH = "/v1internal:streamGenerateContent"
ANTIGRAVITY_API_USER_AGENT = "google-api-nodejs-client/9.15.1"
ANTIGRAVITY_API_CLIENT = "google-cloud-sdk vscode_cloudshelleditor/0.1"
ANTIGRAVITY_CLIENT_METADATA = '{"ideType":"IDE_UNSPECIFIED","platform":"PLATFORM_UNSPECIFIED","pluginType":"GEMINI"}'

# -- AI model --
ANTIGRAVITY_DEFAULT_MODEL = "claude-sonnet-4-20250514"

# -- OAuth consent button selectors --
SEL_OAUTH_APPROVE = "#submit_approve_access"
SEL_OAUTH_ALLOW = "text:Allow"
SEL_OAUTH_ALLOW_CN = "text:允许"
SEL_OAUTH_CONTINUE = "text:Continue"
SEL_OAUTH_CONTINUE_CN = "text:继续"
SEL_OAUTH_BTN_ALLOW = 'button:has-text("Allow")'
SEL_OAUTH_BTN_CONTINUE = 'button:has-text("Continue")'

# -- Phone verification selectors --
SEL_PHONE_NUMBER_INPUT = "#phoneNumberId"
SEL_PHONE_CODE_INPUT = "#idvAnyPhonePin"
SEL_PHONE_VERIFY_NEXT = "#idvanyphoneverifyNext"

# ============================================================
# SMS API (services/sms_api.py)
# ============================================================

# -- Provider API URLs --
HEROSMS_DEFAULT_URL = "https://hero-sms.com/stubs/handler_api.php"
SMSBUS_DEFAULT_URL = "https://sms-bus.com/api/control"

# -- SMS wait parameters --
SMS_WAIT_TIMEOUT = 120
SMS_POLL_INTERVAL = 5.0

# -- SMS HTTP timeout --
SMS_HTTP_TIMEOUT = 30

# -- Country phone codes --
COUNTRY_PHONE_CODES = {
    "Russia": "+7", "Ukraine": "+380", "Kazakhstan": "+7", "China": "+86",
    "Philippines": "+63", "Indonesia": "+62", "Malaysia": "+60", "Kenya": "+254",
    "Tanzania": "+255", "Vietnam": "+84", "South Africa": "+27", "Myanmar": "+95",
    "India": "+91", "Hong Kong": "+852", "Poland": "+48", "England": "+44",
    "USA": "+1", "Thailand": "+66", "Iraq": "+964", "Nigeria": "+234",
    "Colombia": "+57", "Bangladesh": "+880", "Turkey": "+90", "Germany": "+49",
    "France": "+33", "Canada": "+1", "Sweden": "+46", "Netherlands": "+31",
    "Spain": "+34", "Portugal": "+351", "Italy": "+39", "Mexico": "+52",
    "Argentina": "+54", "Brazil": "+55", "Pakistan": "+92", "Cambodia": "+855",
    "Laos": "+856", "Nepal": "+977", "Egypt": "+20", "Ireland": "+353",
    "Australia": "+61", "Taiwan": "+886", "Japan": "+81", "South Korea": "+82",
    "Singapore": "+65", "Saudi Arabia": "+966", "Israel": "+972", "Peru": "+51",
    "Chile": "+56", "Morocco": "+212", "Romania": "+40", "Hungary": "+36",
    "Czech Republic": "+420", "Austria": "+43", "Belgium": "+32", "Switzerland": "+41",
    "Denmark": "+45", "Norway": "+47", "Finland": "+358", "Greece": "+30",
    "Estonia": "+372", "Latvia": "+371", "Lithuania": "+370", "Croatia": "+385",
    "Serbia": "+381", "Bulgaria": "+359", "Slovakia": "+421", "Slovenia": "+386",
    "New Zealand": "+64", "UAE": "+971", "Georgia": "+995", "Armenia": "+374",
    "Azerbaijan": "+994", "Moldova": "+373", "Belarus": "+375", "Uzbekistan": "+998",
    "Kyrgyzstan": "+996", "Tajikistan": "+992", "Turkmenistan": "+993",
    "Ghana": "+233", "Uganda": "+256", "Cameroon": "+237", "Ethiopia": "+251",
    "Ivory Coast": "+225", "Senegal": "+221", "Algeria": "+213", "Tunisia": "+216",
    "Afghanistan": "+93", "Bolivia": "+591", "Costa Rica": "+506",
    "Dominican Republic": "+1", "Ecuador": "+593", "El Salvador": "+503",
    "Guatemala": "+502", "Haiti": "+509", "Honduras": "+504", "Jamaica": "+1",
    "Nicaragua": "+505", "Panama": "+507", "Paraguay": "+595", "Uruguay": "+598",
    "Venezuela": "+58", "Cuba": "+53", "Puerto Rico": "+1",
    "United Kingdom": "+44", "UK": "+44",
}

# ============================================================
# Group Management (services/group.py)
# ============================================================

# 家庭组最大成员数 (1 管理员 + 5 成员)
FAMILY_MAX_MEMBERS = 6

# ============================================================
# ORM Defaults (models/orm.py)
# ============================================================

DEFAULT_SCREEN_WIDTH = 1920
DEFAULT_SCREEN_HEIGHT = 1080
DEFAULT_OS_TYPE = "macos"
DEFAULT_LANGUAGE = "en-US"
DEFAULT_SMS_COUNTRY = 2

# ============================================================
# Automation Actions (routers/automation.py)
# ============================================================

ACTION_LOGIN = "login"
ACTION_FAMILY_CREATE = "family-create"
ACTION_FAMILY_INVITE = "family-invite"
ACTION_FAMILY_ACCEPT = "family-accept"
ACTION_FAMILY_REMOVE = "family-remove"
ACTION_FAMILY_LEAVE = "family-leave"
ACTION_FAMILY_DISCOVER = "family-discover"
ACTION_FAMILY_BATCH_INVITE = "family-batch-invite"
ACTION_FAMILY_BATCH_REMOVE = "family-batch-remove"
ACTION_FAMILY_REPLACE = "family-replace"
ACTION_FAMILY_ROTATE = "family-rotate"
ACTION_POOL_BATCH_LOGIN = "pool-batch-login"
ACTION_OAUTH = "oauth"
ACTION_PHONE_VERIFY = "phone-verify"

# -- Replace workflow phase labels --
PHASE_REMOVE_OLD = "--- 阶段1: 移除旧成员 ---"
PHASE_INVITE_NEW = "--- 阶段2: 邀请新成员 ---"
PHASE_AUTO_ACCEPT = "--- 阶段3: 新成员自动接受邀请 ---"
PHASE_AUTO_LOGIN = "--- 新成员自动登录 ---"
PHASE_ACCEPT_INVITE = "--- 新成员接受邀请 ---"

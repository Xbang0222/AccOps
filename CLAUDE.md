# AccOps - 项目上下文

## 项目概述

Google 账号批量管理系统：FastAPI 后端 + React (Ant Design) 前端 + DrissionPage 浏览器自动化 + httpx RPC 家庭组操作。

## 技术栈

- **后端**: Python 3.11+ · FastAPI · SQLAlchemy · PostgreSQL
- **前端**: React 19 · TypeScript · Ant Design 6 · Vite 7
- **浏览器自动化**: DrissionPage（登录 / 密码重验证 / rapt 获取）
- **HTTP RPC**: httpx（Google Family batchexecute 接口）
- **认证**: JWT (python-jose) · bcrypt
- **包管理**: 后端 uv · 前端 pnpm

## 项目结构

```
backend/
├── app.py                      # FastAPI 入口，注册所有路由
├── config.py                   # 配置项 (JWT, 数据库, CORS, 服务器)
├── deps.py                     # 依赖注入 (JWT 验证, AppState)
├── run.py                      # 启动入口: uv run python run.py [--reload]
├── models/
│   ├── database.py             # SQLAlchemy 引擎 + SessionLocal
│   ├── orm.py                  # ORM 模型 (Account, Group, Config, BrowserProfile, SmsProvider, SmsActivation)
│   └── schemas.py              # Pydantic 请求/响应模型
├── routers/
│   ├── auth.py                 # 认证 API (登录/设置密码)
│   ├── accounts.py             # 账号管理 API (CRUD + 导入 + 标签筛选 + 批量标签)
│   ├── groups.py               # 家庭组管理 API (CRUD + 成员管理)
│   ├── tags.py                 # 用户自定义标签 CRUD
│   ├── dashboard.py            # 仪表盘 API (统计数据)
│   ├── browser.py              # 浏览器配置 API (启动/停止/状态)
│   ├── automation.py           # 自动化 REST API (登录/家庭组操作)
│   ├── automation_ws.py        # 自动化 WebSocket (实时步骤推送)
│   ├── automation_swap.py      # 统一换号操作 (移除→选号→邀请→接受→同步)
│   ├── automation_helpers.py   # WebSocket 基础设施 (步骤队列/任务轮询)
│   ├── settings.py             # 系统设置 API (GET/PUT, 存 config 表)
│   ├── sms.py                  # 接码管理 API (提供商 CRUD + 购买/查询/取消)
│   └── cliproxy.py             # CLIProxyAPI 集成 API (上传 OAuth 凭证 + 连接测试)
├── core/
│   ├── constants.py            # 项目常量
│   └── parsing.py              # 通用入参解析工具 (parse_int_list 等)
├── services/
│   ├── account.py              # 账号 CRUD + 标签关联服务
│   ├── account_import_parser.py # 账号导入解析器
│   ├── age_verification.py     # 年龄验证服务
│   ├── auth.py                 # 认证服务 (密码设置/验证)
│   ├── auth_steps.py           # 登录步骤处理
│   ├── automation.py           # 自动化核心逻辑 (StepTracker + 所有自动化函数)
│   ├── automation_types.py     # 自动化类型定义
│   ├── automation_utils.py     # 自动化共享工具 (cookies保存/订阅同步/解密)
│   ├── browser.py              # DrissionPage 浏览器管理 (登录 + rapt 获取)
│   ├── family_api.py           # Google Family batchexecute RPC 封装 (纯 httpx)
│   ├── group.py                # 家庭组 CRUD + 成员管理服务
│   ├── group_sync.py           # 家庭组同步 (discover结果→数据库)
│   ├── oauth.py                # OAuth 自动授权 + API 探测 + 自动手机号验证
│   ├── oauth_support.py        # OAuth 辅助工具
│   ├── page_wait.py            # DrissionPage 页面等待与重试工具 (防 "page is refreshed" 异常)
│   ├── sms_api.py              # 接码平台 API 封装 (HeroSMS / SMS-Bus 多提供商)
│   ├── tag.py                  # 用户自定义标签 CRUD (含关联账号计数)
│   ├── cliproxy.py             # CLIProxyAPI 凭证上传服务 (httpx 异步并发)
│   └── verification.py         # 验证链接提取
└── utils/
    └── crypto.py               # 加密工具

frontend/src/
├── api/
│   ├── client.ts               # Axios 客户端 (baseURL, 拦截器)
│   ├── index.ts                # 统一导出
│   ├── accounts.ts             # 账号 API (含 tag_ids 筛选)
│   ├── groups.ts               # 分组 API
│   ├── auth.ts                 # 认证 API
│   ├── dashboard.ts            # 仪表盘 API
│   ├── browser.ts              # 浏览器管理 API
│   ├── automation.ts           # 自动化 API
│   ├── settings.ts             # 设置 API
│   ├── sms.ts                  # 接码管理 API
│   ├── tags.ts                 # 用户标签 CRUD API
│   └── cliproxy.ts             # CLIProxyAPI 集成 API (上传 + 连接测试)
├── features/
│   ├── automation/             # 自动化共享元数据与展示映射
│   ├── browser/                # 浏览器配置默认值等领域逻辑
│   ├── group-detail/           # 分组详情组件 (账号卡片 + 日志面板 + 换号操作)
│   ├── settings/               # 系统设置组件 (StorageStatsCard)
│   ├── sms/                    # 接码管理组件 (国家列表 + 历史 + 配置弹窗)
│   └── accountsTableColumns.tsx # 账号表格列定义 (可拖拽列宽)
├── pages/
│   ├── LoginPage.tsx            # 登录页
│   ├── DashboardPage.tsx        # 仪表盘
│   ├── AccountsPage.tsx         # 账号管理 (表格 + 操作面板)
│   ├── GroupManagePage.tsx       # 分组管理 (卡片列表)
│   ├── GroupDetailPage.tsx       # 分组详情 (左侧卡片列表 + 右侧日志面板)
│   ├── SmsPage.tsx              # 接码管理 (左侧国家列表 + 右侧历史记录)
│   └── SettingsPage.tsx         # 系统设置 (调试模式 / 无头模式 / 年龄认证 / 默认接码 / CLIProxyAPI 集成)
├── components/
│   ├── AccountModal.tsx         # 账号编辑弹窗 (含标签多选)
│   ├── ErrorBoundary.tsx        # 错误边界 (渲染错误优雅降级)
│   ├── ResizableTitle.tsx       # 可拖拽列宽表头组件 (react-resizable)
│   ├── TagManageModal.tsx       # 标签管理弹窗 (创建/重命名/删除 + 关联账号计数)
│   └── TOTPDisplay.tsx          # TOTP 验证码显示 + 倒计时
├── layouts/
│   └── MainLayout.tsx           # 主布局 (侧边栏 + 内容区 + 主题切换)
├── theme/
│   └── index.ts                 # Ant Design 主题配置 (浅色/深色 双主题)
├── types/
│   └── index.ts                 # TypeScript 类型定义
├── utils/
│   ├── http.ts                  # HTTP 错误消息提取
│   ├── mask.ts                  # 邮箱脱敏工具
│   └── totp.ts                  # TOTP 验证码生成
└── hooks/
    ├── useAutomationWs.ts       # 自动化 WebSocket hook
    └── useThemeMode.tsx         # 主题模式 Context (system/light/dark)
```

> 自动化模块拆分为 4 个文件: `automation.py` (REST) / `automation_ws.py` (WebSocket) / `automation_swap.py` (换号) / `automation_helpers.py` (WS工具)。共享工具函数位于 `services/automation_utils.py`。

## 环境变量

| 变量                       | 默认值                  | 说明                    |
| -------------------------- | ----------------------- | ----------------------- |
| `GAM_DATABASE_URL`         | 见 `.env.example`       | 数据库连接串            |
| `GAM_SECRET_KEY`           | 见 `.env.example`       | JWT 签名密钥            |
| `GAM_TOKEN_EXPIRE_MINUTES` | `480`                   | Token 有效期（分钟）    |
| `GAM_CORS_ORIGINS`         | `http://localhost:5173` | CORS 允许的源，逗号分隔 |
| `GAM_HOST`                 | `127.0.0.1`             | 服务监听地址            |
| `GAM_PORT`                 | `8000`                  | 服务监听端口            |

---

## 自动化架构

### 整体架构

浏览器 (DrissionPage) 只负责两件事:

1. **登录** → 提取 cookies
2. **密码/TOTP 重验证** → 获取 rapt token

家庭组的所有实际操作通过 **httpx + batchexecute RPC** 完成，不需要浏览器页面交互。

### 同步流程 (discover)

cookies 过期时的自动恢复机制 (4 级回退):

```
1. 数据库保存的 cookies → 直接查询 (最快)
   ↓ 过期
2. 运行中浏览器的 cookies → 重试
   ↓ 也过期或浏览器未运行
3. 自动启动浏览器 → 登录 → 获取新 cookies → 查询 → 关闭浏览器
   ↓ 登录失败
4. 报错提示
```

> **注意**: 自动登录强制 `headless=False`，因为 Google 会拦截无头模式登录。服务器环境需配合 Xvfb。

### StepTracker 日志追踪器

- 记录每个自动化步骤的状态 (ok / fail / skip / info)
- 支持 `on_step` 回调，通过 WebSocket 实时推送步骤进度
- `debug_mode=True` 时输出详细日志
- 设置存储在数据库 `config` 表

### 自动化函数

| 函数                           | 说明                                             | 方式                           |
| ------------------------------ | ------------------------------------------------ | ------------------------------ |
| `auto_login_sync()`            | 自动登录 Google 账号                             | DrissionPage                   |
| `create_family_group_sync()`   | 创建家庭组                                       | RPC: nKULBd → Wffnob → c5gch   |
| `send_family_invite_sync()`    | 发送家庭组邀请                                   | RPC: B3vhdd → xN05r            |
| `accept_family_invite_sync()`  | 接受家庭组邀请                                   | RPC: SZ903d                    |
| `remove_family_member_sync()`  | 移除家庭组成员                                   | rapt + RPC: Csu7b              |
| `leave_family_group_sync()`    | 退出/删除家庭组                                  | rapt + RPC: Csu7b / hQih3e     |
| `discover_family_group_sync()` | 发现家庭组关系                                   | RPC: V2esPe                    |
| `discover_family_by_cookies()` | 纯 cookies 发现 + 自动登录刷新                   | httpx + DrissionPage 回退      |
| `oauth_sync()`                 | OAuth 自动授权 + API 探测 + 自动接码验证         | DrissionPage + httpx           |
| `auto_phone_verify_sync()`     | Google 手机号验证 (接码平台自动完成)             | DrissionPage + HeroSMS/SMS-Bus |
| `_handle_family_swap()`        | 统一换号 (移除→选号→邀请→登录→接受→discover同步) | RPC + DrissionPage             |

每个函数都有对应的异步包装器 `run_xxx()` 用于 API 调用。

### 统一换号操作 (routers/automation_swap.py)

将原有的替换/轮换/一键换号合并为单一 `family-swap` 操作:

**流程阶段:**

1. 自动启动浏览器（如未运行）
2. 批量移除旧子号（rapt + RPC 批量移除）
3. 选取新子号（号池自动选取 或 手动指定）
4. 批量邀请新子号
5. 登录子号刷新 cookies
6. 用 cookies 自动接受邀请
7. 完整 discover 同步（与"同步"按钮一致）

**两种模式:**

- `pool` — 从号池自动选取，指定数量
- `manual` — 手动指定邮箱列表

**关键改进:** 换号完成后执行完整的 `discover_family_by_cookies` + `sync_group_from_discover`，确保数据库与 Google 实际状态完全一致。

### OAuth + 自动手机号验证 (services/oauth.py)

**OAuth 流程:**

1. 构建 OAuth URL (Antigravity client_id) → 浏览器打开 → 自动同意授权
2. 提取 authorization code → 交换 access_token + refresh_token
3. 获取 project_id (loadCodeAssist / onboardUser)
4. `probe_api()` 向 Antigravity API 发送测试请求 (streamGenerateContent)
5. 如果返回 403 `VALIDATION_REQUIRED` → 提取 `validation_url` → 自动接码验证

**自动接码验证流程 (auto_phone_verify_sync):**

1. 打开 `validation_url` → 选择 "Verify your phone number"
2. 从默认接码提供商购买号码
3. 输入带 `+` 号的完整号码 (Google 自动切换国家)
4. 点 Next → 轮询等待验证码 (HeroSMS getStatus)
5. 输入纯数字验证码 → 点确认
6. 成功判断: URL 包含 `auth_success` 或 `gemini-code-assist`

**关键选择器:**

- 手机号输入: `#phoneNumberId`
- 验证码输入: `#idvAnyPhonePin`
- 确认按钮: `#idvanyphoneverifyNext`

### 接码管理 (services/sms_api.py)

多提供商抽象架构:

- `SmsProviderBase` — 抽象基类
- `HeroSmsProvider` — HeroSMS (SMS-Activate 协议兼容)
- `SmsBusProvider` — SMS-Bus (独立 REST API)
- `create_provider(type, api_key)` — 工厂函数

接码 API (routers/sms.py):

- 提供商 CRUD + 余额查询
- 购买号码 / 查询状态 / 完成 / 取消
- 历史记录 + 国家/服务/价格查询

### 浏览器管理 (services/browser.py)

- `BrowserManager.launch(profile, headless=None)` — 启动浏览器实例，`headless` 参数可覆盖全局设置
- `login_sync()` — 同步登录 (邮箱 → 密码 → 2FA)
- `handle_reauth_sync()` — 密码 + TOTP 重验证
- `get_rapt_sync()` — 导航敏感页面获取 rapt token
- `get_cookies()` — 提取 Google 域 cookies (优先 myaccount > accounts > .google.com)

### 家庭组 RPC (services/family_api.py)

`FamilyAPI` 类封装所有 Google Family batchexecute RPC:

**纯 HTTP 操作 (只需 cookies):**

- `query_status()` — 查询家庭组状态 (DmVhMc)
- `query_members()` — 查询成员列表 (V2esPe)
- `query_subscription()` — 查询订阅状态 (HTTP GET /subscriptions 页面)
- `create_family()` — 创建家庭组 (nKULBd → Wffnob → c5gch)
- `send_invite(email)` — 发送邀请 (B3vhdd → xN05r)
- `accept_invite()` — 接受邀请 (SZ903d)

**需要 rapt token 的操作:**

- `remove_member(member_user_id, rapt)` — 移除成员 (Csu7b)
- `leave_family(rapt)` — 退出家庭组 (Csu7b + "me")
- `delete_family(rapt)` — 删除家庭组 (hQih3e)

### 订阅状态检测

- **检测方式**: HTTP GET 访问 `/subscriptions` 页面，搜索 "AI Ultra" 关键词
- **日期提取**: 正则匹配 `Renews on Mar 23, 2026` → 转换为 `2026年3月23日`
- **状态传播**: 主号 Ultra → 自动传播给同组所有子号
- **状态清理**: 成员被移除/退出/家庭组删除 → 清除订阅状态

### CLIProxyAPI 集成 (services/cliproxy.py)

将分组详情页中已完成 OAuth 验证的子号凭证批量上传到 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 管理接口，免去手动复制下载。

**触发入口**: 分组详情页顶部「全选子号 → 上传到 CLIProxy」按钮（主号自动排除）。

**上传流程**:

1. 读取 `Account.oauth_credential_json`（plain JSON）
2. 补全 `email` 与 `type: "antigravity"` 字段
3. `httpx.AsyncClient` 并发 `POST {base_url}/v0/management/auth-files?name={email}.json`
4. 携带 `Authorization: Bearer {api_key}` 认证
5. CLIProxyAPI 默认行为是同名覆盖，无需显式去重

**API 端点 (routers/cliproxy.py)**:

| Endpoint                       | 说明                                                                       |
| ------------------------------ | -------------------------------------------------------------------------- |
| `POST /api/v1/cliproxy/upload` | 批量上传，body `{ account_ids: [int] }`，返回 `{ total, succeeded, failed, items }` |
| `GET  /api/v1/cliproxy/status` | 连接测试，返回 `{ configured, reachable, status_code, message }`           |

**配置**: 系统设置页填写 `cliproxy_base_url` + `cliproxy_api_key`，未配置时上传接口返回 400。

**前端**:

- `frontend/src/api/cliproxy.ts` — `uploadToCliproxy` / `getCliproxyStatus`
- `frontend/src/pages/SettingsPage.tsx` — CLIProxyAPI 集成 Card（Base URL + API Key + 测试连接 + 保存）
- `frontend/src/features/group-detail/components/GroupAccountCard.tsx` — 卡片左上角 Checkbox（无 OAuth 凭证时禁用）
- `frontend/src/features/group-detail/useGroupDetailController.ts` — `selectedForUpload` Set state + `handleUploadToCliproxy`

---

## Google 家庭组操作研究成果

### 页面流程 (已用 RPC 替代，仅供参考)

| 操作       | 页面流程                                                 | 直接 URL                    |
| ---------- | -------------------------------------------------------- | --------------------------- |
| 创建家庭组 | details → create → confirm → invitemembers → skip → done | —                           |
| 发送邀请   | invitemembers → combobox 输入 → chip → Send              | `family/invitemembers`      |
| 接受邀请   | details → pendinginvitations → join/t/{token} → success  | `family/pendinginvitations` |
| 成员退出   | details → Leave → 密码验证 → 确认                        | `family/leave`              |
| 管理员删除 | details → Delete → 密码+2FA → 确认                       | `family/delete`             |
| 管理员移除 | details → member/{id} → Remove → 密码验证 → 确认         | `family/remove/g/{id}`      |

### rapt token 机制

- 敏感操作 (leave/delete/remove) 触发密码重验证
- 验证通过后 URL 附带 `?rapt=xxx` 参数
- rapt token **跨操作共享**: 一次验证后 remove/delete/leave 全部跳过
- token 有时效性 (几分钟内有效)

### 家庭组限制

- 最多 6 成员 (管理员 + 5 名额)
- 成员 12 个月内只能切换一次家庭组

---

## 系统设置

存储在数据库 `config` 表 (key-value)，通过 `settings.py` API 读写。

| 设置项                    | 说明                                                   |
| ------------------------- | ------------------------------------------------------ |
| `debug_mode`              | 调试模式: 自动化步骤详细日志                           |
| `headless_mode`           | 无头浏览器模式 (Google 登录不支持，自动登录时强制关闭) |
| `age_verify_enabled`      | 年龄认证开关: 关闭时 OAuth 跳过年龄认证 (默认关闭)     |
| `default_sms_provider_id` | 默认接码提供商 ID                                      |
| `cliproxy_base_url`       | CLIProxyAPI 部署地址 (含 `https://`，不带尾斜杠)       |
| `cliproxy_api_key`        | CLIProxyAPI Bearer 认证密钥                            |

---

## 账号标签系统

用户自定义的多对多标签，用于按业务维度分类管理账号（如 VIP / 待处理 / 已完成）。**已替代历史版本中的 `group_name` 字段**（已通过迁移 `397999fb03da` 删除）。家庭组（`family_groups`）是 Google 业务概念，与标签无关。

### 数据模型

- `tags` 表：`id` / `name`（唯一，1-32 字符）/ `sort_order` / 时间戳
- `account_tags` 关联表（多对多）：`(account_id, tag_id)` 复合主键，双向 `ON DELETE CASCADE`
- 索引：`ix_account_tags_tag_id` 用于按标签反查账号

### API

| Endpoint                          | 说明                                            |
| --------------------------------- | ----------------------------------------------- |
| `GET    /api/v1/tags`             | 列出所有标签（含 `accounts_count` 关联账号数）  |
| `POST   /api/v1/tags`             | 创建标签（name 长度 1-32，唯一）                |
| `PUT    /api/v1/tags/{id}`        | 重命名标签                                      |
| `DELETE /api/v1/tags/{id}`        | 删除标签（关联自动清理，账号本身保留）          |
| `POST   /api/v1/accounts/batch-tags` | 批量更新账号标签（add / replace / remove 三模式） |

### 账号端集成

- `GET /api/v1/accounts?tag_ids=1,2,3` — 按标签 OR 筛选（含任一即返回）
- `POST/PUT /api/v1/accounts` body 含 `tag_ids: [int]` — 全量替换关联；传 `null` 表示不动
- 响应中每个账号包含 `tags: [{id, name}]`

### 批量标签操作

`POST /api/v1/accounts/batch-tags` body:

```json
{
  "account_ids": [1, 2, 3],
  "tag_ids": [10, 11],
  "mode": "add",                   // add | replace | remove
  "replace_from_id": null          // mode=replace 时必填，指定被替换的源标签
}
```

- `add` — 在原有标签基础上追加（去重）
- `replace` — 仅当账号包含 `replace_from_id` 时，移除该标签并追加 `tag_ids`
- `remove` — 从账号移除 `tag_ids` 中存在的标签
- 返回 `{ message, count }`，`count` 为实际产生变化的账号数

### 前端入口

账号管理页顶部「管理标签」按钮（🏷️ 图标）→ 弹窗增删改；账号编辑弹窗内"标签"字段多选；筛选区"标签"多选 Select 支持 OR 筛选。

## 开发指引

### 启动项目

**一键启动（推荐）：**

```bash
./start.sh        # 杀残留 → 启后端 → 启前端 → 健康检查
./stop.sh         # 停止所有服务
tail -f /tmp/accops-backend.log    # 查看后端日志
tail -f /tmp/accops-frontend.log   # 查看前端日志
```

脚本位于项目根目录，会自动处理残留进程、`.browser_profiles` 排除、健康检查。

---

**手动启动（需要独立控制时）：**

步骤 1 — 杀残留进程：

```bash
pkill -9 -f "uvicorn app:app" 2>/dev/null; pkill -9 -f "run.py" 2>/dev/null; pkill -9 -f "node.*vite" 2>/dev/null; sleep 1
```

> `lsof | xargs kill` 杀不干净 StatReload 子进程，**必须用 `pkill -f` 按进程名杀**。

步骤 2 — 启动后端：

```bash
cd backend && uv run uvicorn app:app --host 127.0.0.1 --port 8000 --reload --reload-exclude ".browser_profiles"
```

> ⚠️ 不要用 `uv run python run.py --reload`，StatReload 主进程和子进程竞争端口，被杀后容易残留。直接用 `uvicorn` 命令更可靠。
> 必须加 `--reload-exclude ".browser_profiles"`，否则清理缓存时文件变化会触发 reload 导致 crash。

步骤 3 — 启动前端：

```bash
cd frontend && pnpm dev
```

步骤 4 — 验证：

```bash
curl -s http://localhost:8000/docs | head -5   # 后端：应返回 HTML
curl -s http://localhost:5173 | head -5        # 前端：应返回 HTML
```

### 服务地址

| 服务               | 地址                       |
| ------------------ | -------------------------- |
| 后端 API           | http://localhost:8000      |
| API 文档 (Swagger) | http://localhost:8000/docs |
| 前端               | http://localhost:5173      |

### 端口说明

| 端口   | 用途                   |
| ------ | ---------------------- |
| `8000` | FastAPI 后端 (Uvicorn) |
| `5173` | Vite 前端开发服务器    |
| `5432` | PostgreSQL 数据库      |

### 停止服务

```bash
./stop.sh
# 或手动:
pkill -9 -f "uvicorn app:app" 2>/dev/null; pkill -9 -f "node.*vite" 2>/dev/null
```

### 注意事项

- **不要用 `run.py --reload`** — StatReload 主进程和子进程共享端口 fd，被杀后残留子进程会持续占用端口，导致 `Address already in use`
- **不要用 `lsof | xargs kill`** — 杀不干净 StatReload 的多个子进程，用 `pkill -9 -f` 按进程名匹配
- Google 自动登录强制 `headless=False`，服务器环境需配合 Xvfb
- 数据库迁移在应用启动时通过 Alembic 自动执行

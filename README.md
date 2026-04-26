# AccOps

<p align="center">
  <img src="frontend/public/logo-512.png" alt="AccOps" width="120" />
</p>

<p align="center">
  <em>Google 账号批量管理与家庭组自动化操作平台</em>
</p>

<p align="center">
  <a href="#features">功能</a> ·
  <a href="#quick-start">快速开始</a> ·
  <a href="#configuration">配置</a> ·
  <a href="#architecture">架构</a> ·
  <a href="#license">许可证</a>
</p>

---

## Features

### 账号管理
- 邮箱、密码、辅助邮箱、2FA 密钥集中存储
- 实时 TOTP 验证码生成与一键复制
- 批量导入（支持多种格式，智能识别字段）
- 服务端排序（按创建时间、邮箱等）
- 使用状态追踪（`今日可复用` / `已用完`）
- **用户自定义标签** — 多对多标签体系，按业务维度分类（如 VIP / 待处理）
- **批量标签操作** — 选中多账号一键追加/替换/移除标签，替换/移除仅显示账号实际持有的标签

### 分组管理
- 主号 + 子号分组体系，卡片列表 + 实时日志面板
- **统一换号** — 手动指定邮箱列表 → 移除旧子号 → 邀请 → Cookies RPC 接受 → Discover 全量同步
- 移除子号自动标记 `retired`，便于识别已废弃账号

### 家庭组自动化
- 创建/删除家庭组、发送/接受邀请、移除成员
- 批量邀请 + 批量移除 + 批量接受邀请，支持多账号并行操作
- 统一换号操作（合并了替换/轮换/一键换号）
- 同步状态（Discover），订阅状态自动传播
- 邀请时可搜索下拉选择账号（仅显示可用号）

### OAuth 与验证
- OAuth 自动授权（支持 Google v2/v3 账号选择页面）
- 年龄认证自动检测（4层检测 + 信用卡自动填卡）
- 手机号自动验证（接码平台自动购号 → 输入 → 验证）
- API 可用性探测

### 接码管理
- 多提供商支持（HeroSMS / SMS-Bus）
- 国家/服务/价格查询
- 完整购买生命周期管理

### CLIProxyAPI 凭证同步
- 分组详情页勾选已完成 OAuth 验证的子号，一键批量上传到 [CLIProxyAPI](https://github.com/router-for-me/CLIProxyAPI) 管理接口
- 主号自动排除，仅同步子号；冲突策略默认覆盖
- 系统设置页提供 Base URL / API Key 配置和连接测试

### 其他
- **并行操作** — 多个账号可同时执行自动化任务，互不干扰
- **实时反馈** — WebSocket 推送步骤进度，调试模式下截图 + 页面源码
- **错误边界** — 页面渲染错误优雅降级，不会白屏
- **暗黑模式** — 三段式主题切换（跟随系统 / 浅色 / 深色）
- **可拖拽列宽** — 账号表格支持 Excel 风格列宽调整
- **浏览器缓存管理** — 可视化缓存占用，一键清理释放空间

## Tech Stack

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy · PostgreSQL |
| 前端 | React 19 · TypeScript · Ant Design 6 · Vite 7 |
| 浏览器自动化 | DrissionPage |
| HTTP RPC | httpx · Google `batchexecute` |
| 安全 | JWT · bcrypt · AES-256-GCM |
| 包管理 | uv (后端) · pnpm (前端) |

## Quick Start

### 环境要求

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Chrome / Chromium

### 1. 克隆项目

```bash
git clone https://github.com/Xbang0222/AccOps.git
cd AccOps
```

### 2. 配置环境变量

```bash
cp backend/.env.example backend/.env
# 编辑 backend/.env 填入你的配置
```

### 3. 启动后端

```bash
cd backend
uv sync
uv run python run.py
```

API 文档：http://localhost:8000/docs

### 4. 启动前端

```bash
cd frontend
pnpm install
pnpm dev
```

访问：http://localhost:5173

### 5. 首次使用

1. 打开 http://localhost:5173
2. 设置主密码（用于 JWT 认证和数据加密，**无法找回**）
3. 添加 Google 账号（手动或批量导入）
4. 创建分组，设置主号

## Configuration

所有配置通过 `backend/.env` 文件管理：

```bash
cp backend/.env.example backend/.env
```

| 变量 | 必填 | 说明 |
|------|:---:|------|
| `GAM_DATABASE_URL` | ✅ | PostgreSQL 连接串 |
| `GAM_SECRET_KEY` | ✅ | JWT 签名密钥（随机字符串） |
| `GAM_OAUTH_CLIENT_ID` | ✅ | Google OAuth Client ID |
| `GAM_OAUTH_CLIENT_SECRET` | ✅ | Google OAuth Client Secret |
| `GAM_TOKEN_EXPIRE_MINUTES` | | Token 有效期，默认 `480` 分钟 |
| `GAM_CORS_ORIGINS` | | CORS 允许源，默认 `http://localhost:5173` |
| `GAM_HOST` | | 监听地址，默认 `127.0.0.1` |
| `GAM_PORT` | | 监听端口，默认 `8000` |

### 运行时设置

通过系统设置页面管理（存储在数据库 `config` 表）：

| 设置项 | 说明 |
|--------|------|
| `debug_mode` | 调试模式：详细日志、截图、页面源码 |
| `headless_mode` | 无头浏览器（自动登录时强制关闭，Google 会拦截） |
| `age_verify_enabled` | 年龄认证开关（默认关闭） |
| `default_sms_provider_id` | 默认接码提供商 |
| `cliproxy_base_url` | CLIProxyAPI 部署地址（含 `https://`，不带尾斜杠） |
| `cliproxy_api_key` | CLIProxyAPI Bearer 认证密钥 |

## Architecture

```
┌─────────────┐     ┌──────────────────────────────────────────────┐
│   React UI  │────▶│              FastAPI Backend                  │
│  Ant Design │ WS  │                                              │
└─────────────┘     │  ┌─────────────┐  ┌───────────────────────┐  │
                    │  │ DrissionPage │  │   httpx RPC Client    │  │
                    │  │  - 登录      │  │  - 家庭组 CRUD        │  │
                    │  │  - 重验证    │  │  - 邀请/接受/移除     │  │
                    │  │  - rapt 获取 │  │  - 订阅状态查询       │  │
                    │  └──────┬──────┘  └──────────┬────────────┘  │
                    │         │ cookies             │ batchexecute  │
                    │         ▼                     ▼               │
                    │     ┌───────────────────────────────┐        │
                    │     │       Google Services          │        │
                    │     └───────────────────────────────┘        │
                    └──────────────────────────────────────────────┘
```

### 设计原则

- **浏览器最小化** — DrissionPage 仅负责登录和密码重验证，其余全部走纯 HTTP RPC
- **Cookies 自动恢复** — 4 级回退：数据库 → 运行中浏览器 → 自动登录 → 报错
- **并行友好** — WebSocket 连接池，每个账号独立管理，互不干扰

### 换号工作流

```
手动指定子号邮箱 → 换号
                  ├── 阶段1: 移除旧子号 (rapt + RPC 批量)
                  ├── 阶段2: 批量邀请新子号 (RPC)
                  ├── 阶段3: 登录子号刷新 cookies
                  ├── 阶段4: 用 cookies 自动接受邀请
                  └── 阶段5: Discover 全量同步 (与同步按钮一致)
```

### 自动化函数

| 函数 | 说明 | 方式 |
|------|------|------|
| `auto_login_sync` | 自动登录 Google 账号 | DrissionPage |
| `create_family_group_sync` | 创建家庭组 | RPC |
| `send_family_invite_sync` | 发送家庭组邀请 | RPC |
| `accept_family_invite_sync` | 接受家庭组邀请 | RPC |
| `remove_family_member_sync` | 移除家庭组成员 | rapt + RPC |
| `leave_family_group_sync` | 退出/删除家庭组 | rapt + RPC |
| `discover_family_by_cookies` | 发现家庭组关系 | httpx + 自动回退 |
| `_handle_family_swap` | 统一换号 (移除→选号→邀请→接受→同步) | RPC + DrissionPage |
| `oauth_sync` | OAuth 授权 + API 探测 | DrissionPage + httpx |
| `auto_phone_verify_sync` | 自动手机号验证 | DrissionPage + SMS API |

## Project Structure

```
backend/
├── app.py                      # FastAPI 入口
├── config.py                   # 环境变量配置 (.env 自动加载)
├── core/constants.py           # 全局常量 (选择器、RPC ID、OAuth)
├── models/
│   ├── orm.py                  # ORM 模型 (Account, Group, BrowserProfile...)
│   └── schemas.py              # Pydantic 请求/响应模型
├── routers/
│   ├── accounts.py             # 账号管理 (CRUD + 排序 + 标签筛选 + 批量标签)
│   ├── groups.py               # 分组管理 (CRUD)
│   ├── tags.py                 # 用户自定义标签 CRUD
│   ├── automation.py           # 自动化 REST API (登录/家庭组操作)
│   ├── automation_ws.py        # 自动化 WebSocket (实时步骤推送)
│   ├── automation_swap.py      # 统一换号 (移除→选号→邀请→接受→同步)
│   ├── automation_helpers.py   # WebSocket 基础设施 (步骤队列/任务轮询)
│   ├── browser.py              # 浏览器配置 + 缓存管理
│   ├── sms.py                  # 接码管理
│   ├── cliproxy.py             # CLIProxyAPI 凭证上传与连接测试
│   └── settings.py             # 系统设置
├── services/
│   ├── automation.py           # 自动化核心逻辑 (StepTracker + 自动化函数)
│   ├── automation_utils.py     # 自动化共享工具 (cookies保存/订阅同步)
│   ├── browser.py              # DrissionPage 浏览器管理
│   ├── family_api.py           # Google Family batchexecute RPC
│   ├── group_sync.py           # 家庭组与本地分组同步
│   ├── oauth.py                # OAuth + 手机号验证
│   ├── age_verification.py     # 年龄认证检测 + 信用卡自动填卡
│   ├── tag.py                  # 用户标签 CRUD (含关联账号计数)
│   ├── cliproxy.py             # 批量上传 OAuth 凭证到 CLIProxyAPI 管理接口
│   └── sms_api.py              # 接码平台 API (HeroSMS / SMS-Bus)
└── utils/crypto.py             # AES-256-GCM 加密

frontend/src/
├── api/                        # Axios 客户端 + API 封装
├── features/
│   ├── automation/             # 自动化操作定义与展示
│   ├── group-detail/           # 分组详情 (卡片 + 日志 + 换号操作)
│   ├── settings/               # 系统设置组件 (StorageStatsCard)
│   └── browser/                # 浏览器配置
├── pages/                      # 页面 (账号/分组/接码/设置)
├── components/
│   ├── ErrorBoundary.tsx       # 错误边界 (渲染错误优雅降级)
│   ├── AccountModal.tsx        # 账号编辑弹窗 (含标签多选)
│   ├── TagManageModal.tsx      # 标签管理弹窗 (CRUD + 关联账号计数)
│   └── ResizableTitle.tsx      # 可拖拽列宽表头
├── hooks/
│   ├── useAutomationWs.ts      # WebSocket 多连接管理
│   └── useThemeMode.tsx        # 主题模式
└── theme/                      # Ant Design 双主题配置
```

## Important Notes

> [!CAUTION]
> 首次登录需设置主密码，用于 JWT 认证及数据加密，**无法找回**，请妥善保管。

> [!WARNING]
> Google 登录不支持无头浏览器模式（会被反检测拦截）。服务器环境需配合 **Xvfb** 虚拟显示。

- 家庭组限制：最多 6 名成员（管理员 + 5 名额），成员 12 个月内只能切换一次
- 敏感操作（退出/删除/移除）需要 **rapt token**（密码重验证），token 跨操作共享，几分钟内有效
- 建议定期备份 PostgreSQL 数据

## Documentation

- [架构说明](docs/ARCHITECTURE.md)
- [维护与扩展指南](docs/MAINTENANCE_GUIDE.md)
- [家庭组 API 记录](docs/FAMILY_GROUP_API.md)

## License

[MIT](LICENSE)

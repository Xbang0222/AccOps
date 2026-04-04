# AccOps

<p align="center">
  <img src="frontend/public/logo-512.png" alt="AccOps" width="120" />
</p>

<p align="center">
  <em>Google 账号批量管理与家庭组自动化操作平台</em>
</p>

---

## Overview

AccOps 是一个自托管的 Google 账号批量管理系统，将**浏览器自动化**与**直接 RPC 调用**相结合，实现家庭组全生命周期管理。

浏览器（DrissionPage）仅负责登录和密码重验证，所有家庭组操作均通过 httpx 直接调用 Google 内部 `batchexecute` RPC 完成——无需页面交互，速度快、稳定性高。

## Documentation

- [架构说明](docs/ARCHITECTURE.md)
- [维护与扩展指南](docs/MAINTENANCE_GUIDE.md)
- [家庭组 API 记录](docs/FAMILY_GROUP_API.md)
- [重构计划记录](docs/plans/2026-04-04-engineering-refactor-plan.md)

## Features

- **账号管理** — 邮箱、密码、辅助邮箱、2FA 密钥集中存储，实时 TOTP 验证码生成
- **分组管理** — 主号 + 子号分组体系，卡片列表 + 实时日志面板
- **家庭组自动化** — 创建/删除家庭组、发送/接受邀请、移除/替换成员、同步状态
- **OAuth 自动授权** — 自动完成 OAuth 流程，获取凭证并探测 API 可用性
- **自动手机号验证** — API 探测触发验证时，自动购买号码、输入验证码、完成验证
- **接码管理** — 多提供商支持（HeroSMS / SMS-Bus），国家/服务/价格查询，完整购买生命周期
- **订阅检测** — 识别 Google One AI Ultra 订阅状态及到期日，主号状态自动传播给组内子号
- **实时反馈** — WebSocket 推送自动化步骤进度，调试模式下每步截图 + 保存页面源码
- **暗黑模式** — 三段式主题切换（跟随系统 / 浅色 / 深色），全组件适配 Ant Design design tokens
- **可拖拽列宽** — 账号表格支持 Excel 风格的列宽拖拽调整

## Tech Stack

| 层 | 技术 |
|---|---|
| 后端 | Python 3.11+ · FastAPI · SQLAlchemy · PostgreSQL |
| 前端 | React 19 · TypeScript · Ant Design 6 · Vite 7 |
| 浏览器自动化 | DrissionPage |
| HTTP RPC | httpx · Google `batchexecute` |
| 安全 | JWT · bcrypt · AES-256-GCM |
| 包管理 | uv (后端) · pnpm (前端) |

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

### Cookies 自动恢复机制

当 Cookies 过期时，系统执行 4 级回退：

1. **数据库 Cookies** → 直接使用（最快）
2. **运行中浏览器** → 从活跃浏览器实例提取
3. **自动登录** → 启动浏览器 → 登录 → 获取新 Cookies → 关闭
4. **报错** → 提示用户手动处理

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
| `oauth_sync` | OAuth 授权 + API 探测 | DrissionPage + httpx |
| `auto_phone_verify_sync` | 自动手机号验证 | DrissionPage + SMS API |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL
- Chrome / Chromium

### Backend

```bash
cd backend
uv sync

# 可选：配置环境变量（均有默认值）
export GAM_DATABASE_URL="postgresql://user:pass@127.0.0.1:5432/gam"
export GAM_SECRET_KEY="your-secret-key"

# 启动前杀残留进程（--reload 模式必须）
lsof -ti:8000 | xargs kill -9 2>/dev/null

# 启动
uv run python run.py

# 开发模式（热重载）
uv run python run.py --reload
```

API 文档：http://localhost:8000/docs

测试：

```bash
cd backend
uv run python -m unittest discover -s tests -p "test_*.py"
uv run python -m compileall app.py config.py deps.py core models routers services utils
```

### Frontend

```bash
cd frontend
pnpm install
pnpm dev
```

访问：http://localhost:5173

开发模式下前端默认通过 Vite 代理把 `/api` 请求转发到后端，不需要在 `.env` 里再写死 `VITE_API_BASE_URL` 或 `VITE_WS_BASE_URL`。

如果后端端口变了，只需要改：

```bash
cd frontend
export VITE_DEV_PROXY_TARGET="http://127.0.0.1:9000"
pnpm dev
```

如果前端访问地址也变了，例如改成 `http://localhost:3000` 或局域网域名，需要同步调整后端 `GAM_CORS_ORIGINS`。

### Production Build

```bash
cd frontend
pnpm lint
pnpm test:run
pnpm build
# 产物在 dist/
```

## Configuration

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `GAM_DATABASE_URL` | `postgresql://root:123456@127.0.0.1:5432/gam` | PostgreSQL 连接串 |
| `GAM_SECRET_KEY` | 随机生成 | JWT 签名密钥 |
| `GAM_TOKEN_EXPIRE_MINUTES` | `480` | Token 有效期（分钟） |
| `GAM_CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | CORS 允许源，逗号分隔 |
| `GAM_HOST` | `127.0.0.1` | 监听地址 |
| `GAM_PORT` | `8000` | 监听端口 |
| `VITE_DEV_PROXY_TARGET` | `http://127.0.0.1:8000` | 前端开发代理目标，仅 Vite 开发模式使用 |

### Development Connectivity

为避免本地开发时反复出现“无法连接服务器”，当前约定如下：

- 前端默认走同源 `/api`，由 Vite 开发服务器代理到后端。
- WebSocket 默认跟随当前页面来源生成 `ws://` 或 `wss://` 地址，不再写死 `127.0.0.1:8000`。
- 后端默认同时允许 `http://localhost:5173` 和 `http://127.0.0.1:5173` 两种本地来源。

因此以后换端口时，通常只需要改配置，不需要改代码：

```bash
# 后端
export GAM_PORT="9000"
export GAM_CORS_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"

# 前端
export VITE_DEV_PROXY_TARGET="http://127.0.0.1:9000"
```

如果前端本身也换端口，例如 `3000`，则把 `GAM_CORS_ORIGINS` 一并改成对应来源：

```bash
export GAM_CORS_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"
```

### Runtime Settings

系统设置存储在数据库 `config` 表中，通过设置页面管理：

| 设置项 | 说明 |
|--------|------|
| `debug_mode` | 调试模式：每个自动化步骤输出详细日志、截图、页面源码 |
| `headless_mode` | 无头浏览器模式（自动登录时强制关闭，Google 会拦截无头登录） |
| `default_sms_provider_id` | 默认接码提供商 |

## Project Structure

```
backend/
├── app.py                      # FastAPI 入口，路由注册
├── config.py                   # 环境变量配置
├── deps.py                     # 依赖注入 (JWT, AppState)
├── run.py                      # 启动脚本
├── models/
│   ├── database.py             # SQLAlchemy 引擎
│   ├── orm.py                  # ORM 模型
│   └── schemas.py              # Pydantic schemas
├── routers/
│   ├── auth.py                 # 认证
│   ├── accounts.py             # 账号管理
│   ├── groups.py               # 分组管理
│   ├── dashboard.py            # 仪表盘
│   ├── browser.py              # 浏览器配置
│   ├── automation.py           # 自动化 (REST + WebSocket)
│   ├── settings.py             # 系统设置
│   └── sms.py                  # 接码管理
├── services/
│   ├── account.py              # 账号 CRUD
│   ├── auth.py                 # 认证逻辑
│   ├── automation.py           # StepTracker + 自动化函数
│   ├── browser.py              # DrissionPage 浏览器管理
│   ├── family_api.py           # Google Family RPC 封装
│   ├── group.py                # 分组 + 成员管理
│   ├── oauth.py                # OAuth + API 探测 + 自动验证
│   ├── sms_api.py              # 接码平台 API
│   ├── age_verification.py     # 年龄验证
│   └── verification.py         # 验证链接提取
└── utils/
    └── crypto.py               # AES-256-GCM 加密

frontend/src/
├── App.tsx                     # 应用入口 (ThemeProvider 包装)
├── main.tsx                    # React 入口
├── api/                        # Axios 客户端 + API 封装
├── features/                   # 领域逻辑 (automation / browser / group-detail / sms)
├── pages/                      # 页面组件
├── components/                 # 通用组件 (ResizableTitle 等)
├── layouts/                    # 布局组件 (侧边栏 + 主题切换)
├── hooks/                      # 自定义 Hooks (useThemeMode / useAutomationWs)
├── theme/                      # Ant Design 主题配置 (浅色/深色双主题)
├── types/                      # TypeScript 类型
└── utils/                      # 工具函数
```

## Important Notes

> [!CAUTION]
> 首次登录需设置主密码，此密码用于 JWT 认证及数据加密，**无法找回**，请妥善保管。

> [!WARNING]
> Google 登录不支持无头浏览器模式（会被反检测拦截）。服务器环境需配合 **Xvfb** 虚拟显示。

- 所有敏感字段（密码、2FA 密钥、Cookies）均以 **AES-256-GCM** 密文存储
- 家庭组限制：最多 5 名成员（管理员 + 4 名额），成员 12 个月内只能切换一次
- 敏感操作（退出/删除/移除）需要 **rapt token**（密码重验证），token 获取后跨操作共享，几分钟内有效
- 建议定期备份 PostgreSQL 数据

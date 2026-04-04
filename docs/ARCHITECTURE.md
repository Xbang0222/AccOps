# AccOps 架构与模块说明

> 面向后续维护、重构与功能扩展的工程文档。

---

## 1. 系统目标

AccOps 是一个围绕 **Google 账号批量管理**、**家庭组自动化**、**OAuth 授权**、**SMS 验证** 构建的本地/自托管系统。

系统核心设计目标：

1. **浏览器负责登录与重验证**
2. **业务操作尽量通过 HTTP / RPC 完成**
3. **前端页面只负责展示与交互**
4. **复杂流程拆到 feature / service 层**
5. **关键流程都有最少可用测试覆盖**

---

## 2. 总体架构

```text
Frontend (React + AntD)
  ├─ pages/                页面入口
  ├─ features/             领域逻辑与页面控制器
  ├─ api/                  HTTP 请求封装
  └─ hooks/                通用 hooks（如 WebSocket）

Backend (FastAPI + SQLAlchemy)
  ├─ routers/              HTTP / WS 路由层
  ├─ services/             领域服务与自动化流程
  ├─ models/               ORM / schema / DB
  └─ utils/                通用工具
```

职责边界：

- **pages**：路由入口、页面布局、组合组件
- **features**：页面级状态、业务流程、局部 UI 组件
- **routers**：参数校验、编排服务、返回响应
- **services**：真实业务逻辑、自动化流程、外部系统交互

---

## 3. 前端结构

### 3.1 页面入口

- `frontend/src/pages/AccountsPage.tsx`
- `frontend/src/pages/GroupManagePage.tsx`
- `frontend/src/pages/GroupDetailPage.tsx`
- `frontend/src/pages/SmsPage.tsx`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/pages/DashboardPage.tsx`
- `frontend/src/pages/LoginPage.tsx`

页面原则：

1. 页面尽量保持为**展示层**
2. 状态与副作用优先放到 `features/*/use...Controller.ts`
3. 可复用展示块放到 `features/*/components`

### 3.2 重要 feature 模块

#### `features/group-detail/`

用途：分组详情页的领域逻辑与展示组件。

关键文件：

- `useGroupDetailController.ts`
  - 分组详情页主控制器
  - 管理加载分组、浏览器状态、WebSocket 自动化、表单状态
- `utils.ts`
  - 邮箱解析、账号排序、成员选项构建、操作状态更新
- `components/GroupAccountCard.tsx`
  - 单账号卡片
- `components/GroupOperationLogPanel.tsx`
  - 日志面板
- `components/GroupOperationModal.tsx`
  - 邀请/移除/替换成员弹窗

扩展建议：

- 新的分组详情操作优先加到 `operationMeta.ts`
- 新交互先判断是“卡片动作”还是“日志/表单动作”
- 复杂 UI 不要直接塞回 `GroupDetailPage.tsx`

#### `features/sms/`

用途：SMS 页面拆分后的领域模块。

关键文件：

- `useSmsPageController.ts`
  - 管理 provider、国家列表、购买号码、轮询验证码、历史记录、配置弹窗
- `constants.ts`
  - 提供商常量、状态映射
- `utils.ts`
  - provider 选择、国家过滤与排序
- `components/SmsCountryList.tsx`
- `components/SmsActivationCard.tsx`
- `components/SmsHistoryCard.tsx`
- `components/SmsConfigModal.tsx`

扩展建议：

- 新 provider 支持先改 `api/sms.ts` 与后端 `/sms`
- 前端只关心 provider 配置结构，不直接写 provider 特有逻辑
- 国家筛选/排序逻辑统一走 `features/sms/utils.ts`

#### `features/browser/`

- `browserProfileDefaults.ts`
  - 新建浏览器 profile 默认配置
- `runtime.ts`
  - 浏览器运行态、loading set、profileMap 计算

目的：

- 避免多个页面重复维护浏览器运行状态

#### `features/automation/`

- `operationMeta.ts`
  - 自动化操作元数据、可见性判断
- `operationPresentation.tsx`
  - 操作 icon 映射

扩展建议：

- 新操作先补元数据，再接页面按钮和后端 action

---

## 4. 后端结构

### 4.1 routers 层

#### `routers/accounts.py`

负责：

- 账号 CRUD
- 标签/分组筛选
- 批量导入

依赖：

- `services/account.py`
- `services/account_import_parser.py`

#### `routers/groups.py`

负责：

- 分组 CRUD
- 分组成员管理
- 主号设置

依赖：

- `services/group.py`

#### `routers/browser.py`

负责：

- 浏览器 profile CRUD
- 启动/停止浏览器
- 清理浏览器数据

依赖：

- `services/browser.py`

#### `routers/automation.py`

负责：

- 自动登录
- 家庭组操作 REST / WebSocket 编排
- 批量邀请 / 批量移除 / 替换成员
- OAuth / 手机号验证流程调度

注意：

- 这是当前仍然偏大的编排器
- 已抽出：
  - 队列转发 / cancel 轮询 helper
  - `group_sync.py`
- 如果后续继续拆，优先按“动作族”拆：
  - family batch
  - replace flow
  - ws task execution helpers

#### `routers/sms.py`

负责：

- provider CRUD
- 请求号码
- 轮询状态
- 完成/取消激活
- 历史查询

### 4.2 services 层

#### `services/automation.py`

用途：

- Google 家庭组核心自动化服务
- 同步操作函数
- discover 流程
- 异步 wrapper

已拆出的共享类型：

- `services/automation_types.py`

包含：

- `CancellationToken`
- `CancelledError`
- `AutomationResult`
- `FamilyDiscoverResult`
- `StepTracker`

后续建议：

- 再往下拆成：
  - family mutation service
  - family discovery service
  - browser fallback / auto login refresh service

#### `services/group_sync.py`

用途：

- 自动化动作成功后同步本地 group / family 关系
- discover 结果写回本地 group 结构

这是一个非常关键的“**Google 状态 → 本地模型**”同步层。

以后所有“家庭组状态变更后要不要更新 DB”的逻辑，优先放这里。

#### `services/oauth.py`

用途：

- OAuth 主流程
- 手机号验证主流程

已拆出的辅助：

- `services/oauth_support.py`

包含：

- OAuth URL 构建
- token 交换
- project id 获取
- validation url 提取
- 页面状态检测（密码/2FA/同意按钮）

后续建议：

- 如果继续拆，优先分成：
  - oauth token / api support
  - phone verify flow

#### `services/family_api.py`

用途：

- Google Family RPC 封装
- 核心 batchexecute 调用

原则：

- 与 Google Family RPC 直接相关的协议细节放这里
- 不要把页面逻辑混入这里

#### `services/browser.py`

用途：

- DrissionPage 浏览器管理
- 浏览器实例生命周期
- cookies 提取
- 登录相关支持

---

## 5. 关键业务流程

### 5.1 家庭组状态发现

入口：

- 前端：分组详情页“同步”
- 后端：`routers/automation.py`
- 服务：`discover_family_by_cookies()`

回退顺序：

1. 数据库保存 cookies
2. 运行中浏览器 cookies
3. 自动启动浏览器并登录刷新 cookies
4. 失败并提示重新登录

同步写回：

- `services/group_sync.py`

### 5.2 分组详情自动化

入口：

- `GroupDetailPage`
- `useAutomationWs`
- `routers/automation.py` WebSocket

行为：

- 单账号动作绑定单日志面板状态
- 成功/失败/异常都要回写 `opStates`

### 5.3 OAuth 与手机号验证

入口：

- 前端：分组详情 OAuth / phone verify 操作
- 后端：`routers/automation.py`

流程：

1. 打开 OAuth
2. 处理密码 / TOTP / 同意授权
3. 换 token
4. 获取 project id
5. 探测 API
6. 如果需要验证，走手机号验证流程

辅助模块：

- `oauth_support.py`
- `oauth.py`

### 5.4 SMS 购买与轮询

前端：

- `useSmsPageController.ts`

后端：

- `routers/sms.py`
- `services/sms_api.py`

流程：

1. 读取默认 provider
2. 按服务加载国家报价
3. 购买号码
4. 前端定时轮询
5. 收到验证码后可复制 / 完成 / 取消

---

## 6. 新功能应该改哪里

### 6.1 新增一个自动化操作

前端：

1. `features/automation/operationMeta.ts`
2. `features/automation/operationPresentation.tsx`（如果要新图标）
3. `GroupAccountCard.tsx` / controller（如果有特殊交互）

后端：

1. `core/constants.py` 增加 action 常量
2. `routers/automation.py` 接 action
3. `services/automation.py` / 相关 service 实现
4. 如果涉及本地 group 状态同步，补 `group_sync.py`

### 6.2 新增一个 SMS provider

后端：

1. `services/sms_api.py`
2. `routers/sms.py`
3. ORM / config 如需新增字段则补 migration

前端：

1. `features/sms/constants.ts`
2. `api/sms.ts`（如接口结构变化）
3. `useSmsPageController.ts`

### 6.3 新增一个页面

优先结构：

```text
pages/NewPage.tsx
features/new-page/
  ├─ useNewPageController.ts
  ├─ utils.ts
  └─ components/
```

不要把完整业务逻辑直接堆回 `pages/`。

---

## 7. 测试策略

### 后端

当前采用 `unittest`。

建议覆盖：

- parser / helper / sync 写回逻辑
- wrapper 函数
- 关键纯函数

优先测试这些“稳定边界”：

- `group_sync.py`
- `oauth_support.py`
- `automation router helpers`

### 前端

当前采用 `vitest`。

优先测试：

- feature utils
- 排序/过滤/解析逻辑
- 状态映射

不建议现在大量引入脆弱的 UI snapshot。

---

## 8. 当前已知技术债

1. `backend/routers/automation.py` 仍偏大
2. `backend/services/automation.py` 仍混合了：
   - family mutation
   - discover
   - auto login fallback
3. `backend/services/oauth.py` 仍可继续拆 phone verify 流程
4. `frontend/src/pages/GroupManagePage.tsx` / `SettingsPage.tsx` 仍可继续 feature 化

---

## 9. 修改约束建议

后续维护请尽量遵守：

1. **页面不直接承载复杂业务**
2. **外部系统协议细节只放 service 层**
3. **同步写回 DB 的逻辑集中**
4. **重复状态计算先抽 utils**
5. **先补测试，再做大规模迁移**

如果未来继续大改，建议优先从：

1. `automation router`
2. `automation service`
3. `oauth phone verify`
4. `settings / groups 页面 feature 化`

开始。

# AccOps 维护与扩展指南

本指南面向以后继续改这个项目的人，目标是回答三个问题：

1. **改功能时先看哪里**
2. **排问题时先查哪里**
3. **扩展功能时怎么避免把结构再次做坏**

---

## 1. 本地开发与验证

### 后端

```bash
cd backend
uv sync
uv run python run.py --reload
```

验证：

```bash
cd backend
uv run python -m unittest discover -s tests -p "test_*.py"
python3 -m compileall app.py config.py deps.py core models routers services utils
```

### 前端

```bash
cd frontend
pnpm install
pnpm dev
```

说明：

- 开发环境默认通过 Vite 代理访问后端，请优先保留同源 `/api` 方案。
- 不要重新把 `VITE_API_BASE_URL` 或 `VITE_WS_BASE_URL` 写死成某个固定端口，除非有明确部署需求。
- 后端端口变更时，优先改 `VITE_DEV_PROXY_TARGET`，而不是修改前端业务代码。

验证：

```bash
cd frontend
pnpm lint
pnpm test:run
pnpm build
```

如果前端访问地址变了，还需要同步检查后端 `GAM_CORS_ORIGINS` 是否包含当前来源。

---

## 2. 常见改动入口

### 2.1 账号列表改动

主要看：

- `pages/AccountsPage.tsx`
- `features/accountsTableColumns.tsx`
- `features/browser/runtime.ts`
- `components/AccountModal.tsx`

如果只是改表格展示或操作按钮，优先改 `features/accountsTableColumns.tsx`。

### 2.2 分组详情改动

主要看：

- `pages/GroupDetailPage.tsx`
- `features/group-detail/useGroupDetailController.ts`
- `features/group-detail/components/*`
- `features/automation/operationMeta.ts`

如果要新增动作：

1. 先加 operation metadata
2. 再在 controller 里加行为
3. 最后视情况补专用组件

### 2.3 SMS 页面改动

主要看：

- `pages/SmsPage.tsx`
- `features/sms/useSmsPageController.ts`
- `features/sms/components/*`
- `features/sms/utils.ts`

如果改 provider 配置流程，优先：

- `SmsConfigModal.tsx`
- `useSmsPageController.ts`

如果改国家过滤、排序、显示：

- `features/sms/utils.ts`
- `SmsCountryList.tsx`

### 2.4 自动化流程改动

主要看：

- `routers/automation.py`
- `services/automation.py`
- `services/automation_types.py`
- `services/group_sync.py`
- `services/oauth.py`
- `services/oauth_support.py`

原则：

- 路由层只做编排，不写协议细节
- service 层才做真实流程
- 共享结果对象与 tracker 放 `automation_types.py`

---

## 3. 排障路径

### 3.1 前端页面出错

先跑：

```bash
cd frontend
pnpm lint
pnpm test:run
pnpm build
```

再看：

1. 当前页面对应的 controller
2. 对应 feature 的 utils
3. API 请求模块

如果登录页报“无法连接服务器”，优先检查这几项：

1. 前端开发服务器是否正常启动
2. `VITE_DEV_PROXY_TARGET` 是否指向正确的后端地址
3. 后端 `GAM_CORS_ORIGINS` 是否包含当前前端来源
4. 是否有人把 `frontend/src/config.ts` 改回了写死地址

### 3.2 WebSocket 自动化出错

先看：

- 前端：`hooks/useAutomationWs.ts`
- 后端：`routers/automation.py`

再看对应 action 映射到哪个 service：

- family 操作 → `services/automation.py`
- OAuth / phone verify → `services/oauth.py`

### 3.3 家庭组状态不一致

优先检查：

- `services/group_sync.py`

因为“Google 状态”和“本地分组状态”的桥接逻辑集中在这里。

### 3.4 OAuth / 验证流程问题

优先检查：

- `services/oauth.py`
- `services/oauth_support.py`

如果是 token / project / validation_url 解析问题，大概率在 `oauth_support.py`。

如果是页面流程卡住，大概率在 `oauth.py`。

### 3.5 SMS 收码问题

优先检查：

- `routers/sms.py`
- `services/sms_api.py`
- `features/sms/useSmsPageController.ts`

判断思路：

1. 先确认 provider 配置是否正确
2. 再确认 request-number 是否成功
3. 再确认 status 轮询返回
4. 最后确认前端是否正确更新激活状态

---

## 4. 扩展时的工程约束

### 4.1 不要把大逻辑直接塞回页面

如果页面出现以下情况，就应该拆出去：

- 超过 200~300 行
- 同时管理 5+ 个状态
- 同时负责网络请求 + 交互 + 表格列 + 弹窗 + 派生计算

优先拆成：

- `useXxxController.ts`
- `components/`
- `utils.ts`

### 4.2 不要让 routers 变成业务黑洞

路由里如果开始出现：

- 大量重复任务调度
- 大量状态同步
- 大量第三方协议细节

就应该继续往 `services/` 拆。

### 4.3 不要复制同样的状态计算逻辑

例如：

- browser running/loading set 维护
- email 批量解析
- 国家筛选/排序
- account card / operation 状态映射

这些统一抽 utils 或 feature helper。

---

## 5. 推荐的改动流程

以后改功能，建议按这个顺序：

1. 先确定改动落在哪个 feature / service
2. 先补或新增最小测试
3. 再改代码
4. 跑本地验证
5. 再提交

建议最少跑：

```bash
cd backend && uv run python -m unittest discover -s tests -p "test_*.py"
cd frontend && pnpm lint && pnpm test:run && pnpm build
```

---

## 6. 当前重构后新增的关键模块

### 前端新增

- `features/group-detail/*`
- `features/sms/*`
- `features/browser/runtime.ts`
- `features/accountsTableColumns.tsx`

### 后端新增

- `services/group_sync.py`
- `services/automation_types.py`
- `services/oauth_support.py`

这些模块都是后续继续扩展时的**优先承接点**。

---

## 7. 建议的下一阶段重构方向

如果之后还要继续优化，优先级建议：

1. 继续拆 `backend/routers/automation.py`
2. 拆 `backend/services/automation.py` 的 discover / fallback login
3. 拆 `backend/services/oauth.py` 的 phone verify 流程
4. 继续 feature 化 `GroupManagePage.tsx` / `SettingsPage.tsx`

---

## 8. 提交前检查清单

### 代码

- [ ] 页面是否只负责展示
- [ ] 逻辑是否有重复
- [ ] 新增逻辑是否放到了正确 feature / service
- [ ] 是否破坏现有 action / route / API 约定

### 验证

- [ ] backend unittest 通过
- [ ] backend compileall 通过
- [ ] frontend lint 通过
- [ ] frontend vitest 通过
- [ ] frontend build 通过

### 文档

- [ ] README / docs 是否需要同步更新
- [ ] 新模块是否有明确职责说明

---

如果只是临时修 bug，也尽量不要破坏上面的边界。  
**把逻辑放对位置，比把功能做出来更重要。**

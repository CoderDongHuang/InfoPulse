# InfoPulse 项目审计（2026-10-21）

> 本文保留修复前审计快照；问题的当前完成状态见 [修复验收报告](./2026-10-21-remediation.md)。probes 中的旧结果有意记录缺陷，不作为修复后的验收结果。

本轮记录 **14 类问题：P1 7 类、P2 6 类、P3 1 类**。测试和构建通过，但报告编辑、身份策略、账户删除、任务状态机和部署模板仍有明确缺陷。公开数据本地 beta 的既有验收不能覆盖这些路径，也不能扩展成全项目生产就绪结论。

这是基于当前工作树的审计，包含之前已存在的未提交功能和修复。**本轮只新增审计资料及复现脚本，并更新文档索引，没有修改业务逻辑、真实业务库或部署环境。** arXiv 429 的前序修复保留，本报告没有将它重新列为未修复问题。

## 范围与方法

报告生成前盘点了 **546 份正式源代码、配置和文档文件，共 74,868 行，其中 80 份 Markdown**。文件路径、行数、SHA-256、文档标题及能力承诺/待办索引见 [全量清单](./probes/2026-10-21-inventory.results.json)。

- 范围包含后端 app、测试、脚本、全部 Alembic 迁移和模板，前端源代码、测试与构建配置，两个 SDK，Docker/Compose/Kubernetes，GitHub 工作流，以及根目录设计文档、docs 全树中的正式文档、历史审计、博客和许可证。
- 对全部纳入文件做清单和文本扫描；对 Python 做 AST 解析，对严格 JSON 做解析；TypeScript JSONC 配置通过前端类型检查验证。没有语法解析错误。
- 人工重点复核了认证授权、租户策略、私人配置与出站请求、采集同步、搜索/发现/工作台、报告、自动化任务、知识库/媒体/编排 worker、数据删除、部署发布链路，以及对应文档中的实现和验收承诺。不能将全量扫描表述为每一行都经过同等深度的人工审查。
- 80 份既有 Markdown 的 **229 个本地链接目标均存在**，见 [链接检查结果](./probes/2026-10-21-doc-links.results.json)。此检查不验证远程网址和标题锚点。
- 排除依赖目录、虚拟环境、构建产物、运行数据库、用户上传、日志、图片二进制、实际私密 dotenv、审计巨型数据夹具；公开 `.env.example` 纳入。新增的本报告与 probes 不计入上述审计前快照。

证据等级：**隔离复现**表示实际执行生产函数或真实依赖链；**静态确认**表示从源码/配置可以定位缺口，但没有声称完成真实生产演练。部分风险已在路线图中列为待办，本轮进一步定位了具体失败行为。

## 问题总表

| 编号 | 优先级 | 问题 | 证据 |
| --- | --- | --- | --- |
| A01 | P1 | 报告保存请求在途时继续编辑，会被误标成已保存 | 提取真实前端函数执行 |
| A02 | P1 | “强制 SSO / 要求 MFA”策略没有访问拦截 | 真实认证与租户服务隔离复现 |
| A03 | P1 | 账户删除：SQLite 残留私有记录，启用外键后又被约束阻止 | 两种 SQLite 外键模式复现 |
| A04 | P1 | 暂停/取消没有阻止已经排队的任务重试 | 真实调度器隔离复现 |
| A05 | P1 | 发布流程在等待迁移和金丝雀验证前更新正式实例 | 工作流及渲染配置确认 |
| A06 | P1 | NetworkPolicy 阻断网页代理访问 API | 配置路径确认；依赖 CNI 执行策略 |
| A07 | P1 | 独立部署遗漏 sources/actions worker | Compose/Kubernetes 与入口代码确认 |
| A08 | P2 | 报告导出链接没有携带 Bearer，浏览器下载失败 | 真实路由匿名请求 401 |
| A09 | P2 | 定时任务终态失败后不进入下一周期，确认后也不恢复等待运行 | 真实调度器隔离复现 |
| A10 | P2 | 发现页先截取 500 条再筛频道，静默漏结果 | 501 条内容隔离复现 |
| A11 | P2 | 部分写接口响应成功后才提交，提交失败仍已发送成功 | 真实 get_db 依赖顺序复现 |
| A12 | P2 | 媒体 worker 中断后的 running 租约没有恢复扫描 | 源码确认；既有待办 |
| A13 | P2 | 网页 Ingress 没有上传大小配置，默认配置下较大文件被 413 拦截 | 静态配置确认；依赖控制器全局配置 |
| A14 | P3 | 当前说明、历史完成声明与实际能力存在冲突 | 文档与实现交叉核对 |

## P1：优先修复

### A01 报告编辑存在静默丢失

位置：`frontend/src/views/ReportEditorView.vue:15`，关联 `:16`、`:19`、`:24`。

保存请求发送内容 A，等待网络时用户输入 B；返回后代码读取当前 `content.value`，把 B 写入 `savedContent`，而服务端实际只保存了 A。此时 `dirty=false`，界面会把尚未持久化的 B 显示为已保存。若下一次自动保存定时器在请求未完成时触发，还会因 `saving` 直接退出。

[前端复现脚本](./probes/2026-10-21-editor.mjs) 从真实 Vue 文件抽取 `save` 函数，使用延迟响应，得到 [实际结果](./probes/2026-10-21-editor.results.json)：

```json
{"serverContent":"A","editorContent":"B","markedSaved":"B","dirty":false}
```

此外，卸载只清理 1.4 秒的自动保存定时器，没有离开保护；快速切页可直接丢失最后输入。导出时 `await save(true)` 在已有保存请求时也会立即返回，不能保证导出最新内容。

建议保存请求捕获不可变快照，只将该快照标为已保存；请求在途的后续编辑排队保存；导出等待保存队列完成；离开/恢复版本提供未保存内容保护。应增加慢网络并发编辑、快速离开和保存中导出的行为回归。

### A02 强制 SSO/MFA 开关没有形成认证约束

位置：`frontend/src/views/EnterpriseView.vue:33`、`backend/app/models/enterprise.py:136`、`backend/app/api/enterprise.py:186`、`backend/app/services/auth_service.py:63`、`backend/app/services/enterprise.py:53`。

页面提供“强制企业 SSO”“要求 MFA”，策略接口保存字段，但密码登录与租户访问没有据此检查认证方式或 MFA 状态。隔离环境将两项设为 true 后，真实 `login_user` 仍签发密码登录令牌，`resolve_tenant` 仍允许访问该组织。

这不需要否定平台已有成员权限检查；缺口是管理员启用了身份策略，访问链路仍未实施该策略。当前会话也没有足以可信判定 SSO/MFA assurance 的信息。

建议在可信会话中记录认证方式与验证强度，在统一租户入口实施策略；真实提供商未接通前，应禁用或明确标示尚不可生效的设置，避免把“保存成功”当作安全策略已启用。复现见后端结果的 `sso_mfa_policy`。

### A03 账户删除同时缺少外键保证与租户处置

位置：`backend/app/api/auth.py:225`、`backend/app/core/database.py:52`、`backend/app/models/intelligence.py:322`、`backend/app/models/enterprise.py:26`。

删除接口清理知识文件后调用 `db.delete(current_user)`，其余私有对象主要依赖数据库级联。当前 SQLite 连接未启用 `PRAGMA foreign_keys=ON`；按同样 ORM 删除路径复现，用户删除提交后，原用户的私有 Report 仍剩 1 条。不能据此宣称删除了全部私有数据。

另一方面，正常注册会创建个人 Organization，其 `created_by -> users.id` 使用 `ON DELETE RESTRICT`。在启用外键的独立 SQLite 中，创建个人租户再删除用户，提交被外键约束阻止。这验证了该约束路径；本轮没有把它冒充为真实 PostgreSQL 验收。

接口还在最终数据库提交前删除文件，若随后因约束或其他原因失败，会留下数据库仍引用已删除文件的状态；响应后提交的问题见 A11。路线图已承认账户删除一致性尚未完成。

建议先定义组织所有者转移/组织删除和法律保留规则，梳理所有私有对象、存储和外键；SQLite 启用外键并做历史孤儿校验；数据库事务在响应前完成，外部文件清理采用可重试、可对账流程。不能仅启用 PRAGMA 就将此问题视为修复。

### A04 取消和暂停不能阻止已排队重试

位置：`backend/app/api/automation.py:105`、`backend/app/services/automation.py:146`、`:188`。

暂停/取消只改变任务字段。调度器领取 `retrying` 的 TaskRun 时没有约束所属任务仍为 active；`execute_run` 也不检查取消状态。隔离环境创建 cancelled 任务及到期 retry，执行真实 `process_due_once` 后：任务仍为 cancelled，运行却 succeeded，并产生 1 份报告。

同一缺口也存在于暂停任务；手动 `/task-runs/{run_id}/retry` 路径没有复用 `/tasks/{id}/run` 的取消检查。用户停止任务后仍可能发生后续处理和通知。本轮仅使用站内通知，没有发送真实外部消息。

建议取消时终止未执行重试，领取和产生副作用前再次核对任务状态；暂停保留可恢复状态但停止执行；所有手动/自动重试共用状态门禁。复现结果键为 `cancelled_retry`。

### A05 发布流程的执行顺序与声明不符

位置：`.github/workflows/deploy.yml:51`、`:54`、`:63`、`:71`；`deploy/scripts/render_manifests.py`；`deploy/k8s/production.yaml`。

渲染时 stable 和 canary 都替换成新版本。名为“Run migration before traffic shift”的步骤首先 apply 整份 release manifest，内含 stable、web、workers、preflight 和 migration Job；然后才等待 Job 完成。Kubernetes 不会因 YAML 文档排列而等待前一个 Job 完成，新正式实例和 worker 可以在旧 schema 上运行，preflight 失败时变更也已发出。

后续健康检查请求公共 API 域名，可能命中 stable，不能单独证明 canary 版本通过。失败回滚只 undo 两个 API deployment，没有覆盖已更新的 web/worker。

建议拆分 preflight、迁移、canary、正式推广的资源及步骤；前一门禁通过后才 apply 下一组。金丝雀探测必须可确认所测版本；应用回滚需覆盖本次更新的全部组件，并说明数据库向后兼容边界。本项未在真实集群执行发布。

### A06 默认拒绝策略阻断网页容器到 API

位置：`deploy/k8s/production.yaml:268`、`:273`；`frontend/nginx.conf:19`。

策略拒绝 infopulse 命名空间所有 Pod 的入站，只允许来自 ingress-nginx 命名空间的流量进入 API/web。浏览器同源 `/api` 先到 web Nginx，再由 web Pod 请求 `backend:8000`，第二跳来自 infopulse 命名空间，缺少允许规则。

在正确执行 NetworkPolicy 的 CNI 上，该路径会被拦截；网页静态资源和 readiness 可以正常，实际业务 API 却超时。直接走 API 域名的入口可能可用，不能用它排除网页代理路径的问题。

建议明确允许 web Pod 到 API Pod 的 TCP 8000，保留其余隔离，并验收 app 域名下登录、查询、上传和 WebSocket。本项为静态路径核对，未做真实 CNI 连通性实验。

### A07 部署模板没有启动来源同步与行动处理 worker

位置：`deploy/staging.compose.yml:61`、`:79`；`deploy/k8s/production.yaml:11`、`:108`；`backend/app/worker.py:22`、`:27`；`backend/app/main.py:51`；`backend/app/services/action_worker.py:10`。

两套独立部署模板关闭 API 内置后台循环，但只启动 scheduler、knowledge、orchestration、media 四类 worker，遗漏代码中已有的 sources 和 actions 角色。

按这些模板启动，来源周期同步没有执行者；平台 webhook 队列、行动状态推进等依赖 `action_operations_loop` 的后台工作也没有执行者。orchestration worker 的 dispatch 处理不能覆盖整个 action loop。手动同步以及独立 public_server 的成功验收不代表这些部署模板已启动对应循环。

建议补齐两个角色的部署、运行参数、可观测性和告警，验证重启、积压和重复执行边界。若某环境有意不开放相关能力，应同步禁用入口并说明边界，不能让任务静默停留在队列。

## P2：影响功能完整性与故障恢复

### A08 浏览器报告下载没有认证头

位置：`frontend/src/views/ReportEditorView.vue:21`、`frontend/src/api/reports.ts:19`、`frontend/src/api/request.ts:35`、`backend/app/api/reports.py:84`。

报告下载使用 `window.open` 导航，Bearer 仅由 Axios 拦截器附加。普通新窗口导航不会读取 sessionStorage 并构造 Authorization；下载接口则必须认证。挂载真实报告路由、不带 Bearer 请求得到 **401 Not authenticated**，与浏览器该路径一致。

建议用经过认证的请求获取 Blob 并触发下载，或实现绑定用户、短时有效的下载票据。应保留文件所有权校验，不能通过移除鉴权来修复。结果键为 `navigation_download_without_bearer`。

### A09 失败周期与等待确认运行会停滞

位置：`backend/app/services/automation.py:148`、`:162`、`:172`、`:188`；`backend/app/api/automation.py:110`。

只有成功执行才推进 `task.next_run_at`。进入 dead_letter/blocked 后，调度器继续用旧定时点构造同一个幂等键，`enqueue_run` 查到已有运行后直接返回；下一周期不会自然产生新运行。

高风险运行进入 awaiting_confirmation 后，confirm 接口只改任务的 confirmation_status；调度器既不领取这种状态，也不重新执行旧记录。实际等待运行即使批准仍不恢复。

隔离复现故障注入使用 max_retries=0 的不支持任务类型，模拟执行器终态失败；时钟推进两天后仍只有 1 条 dead_letter。另一正常监控任务从 pending 改为 approved 后，运行仍为 awaiting_confirmation。这里验证的是状态机，不是生产第三方故障。

建议分离“调度周期游标”和“单次运行终态”，确认操作显式恢复目标运行；处理 blocked/终态失败后的策略，避免永久占用到期扫描。结果键为 `schedule_after_terminal_failure`、`confirmed_run_not_resumed`。

### A10 发现页先截候选集，频道分页静默遗漏

位置：`backend/app/services/stage3.py:53`、`:56`、`:65`、`:75`。

查询先取时间范围内最新 500 条内容，再在 Python 中筛频道、排序和分页。构造前 500 条 AI、第 501 条 Java 的同日数据，Java 频道返回 total=0、has_more=false，库中实际上存在 1 条匹配内容。“全部”频道的 total 同样仅代表候选集。

路线图已声明工作台关注匹配的 500 条限制，但发现页没有相应候选窗口说明，不能把返回 total 当完整范围的计数。

建议将可表达的频道条件与过滤下推数据库，使用完整 count 和稳定分页；若产品选择有限推荐窗口，应返回窗口范围/截断信息并在页面明确展示。结果键为 `discover_501st_matching_item`。

### A11 其他领域仍存在成功响应先于提交

位置：`backend/app/core/database.py:102`、`:103`；示例 `backend/app/api/automation.py:49`、`:84`。

默认 get_db 在 yield 之后 commit，当前 FastAPI 依赖结束阶段发生在响应发送后。创建订阅/任务等接口仅 flush 后返回，若最终提交失败，成功状态和响应体已经发给客户端，刷新会出现“刚创建又消失”。

使用真实 get_db 和 ASGI 应用、注入提交失败，事件顺序为：

```json
["response_201","response_body","commit_failed"]
```

这复现的是基础依赖的实际执行顺序，没有声称对全部写接口逐一注入故障。此前已显式在响应前 commit 的认证、资料、报告和最近浏览路径不列入此次误报；路线图也明确其余领域事务仍待验收。

建议逐领域明确事务边界，在发送成功响应前完成提交，并用独立数据库连接检查可见性、提交失败和重复点击。外部副作用应采用 outbox/补偿机制，避免简单在服务内部到处 commit。结果键为 `dependency_commit_order`。

### A12 媒体 running 任务在进程退出后不能自动恢复

位置：`backend/app/services/multimodal.py:194`、`:196`、`:200`；`backend/app/api/multimodal.py:87`。

worker 只领取 queued；领取后将 running 和 30 分钟租约提交，然后处理。没有扫描过期 running 的恢复逻辑；手动 retry 接口只接受 failed。进程被 kill 后执行不到普通异常处理，即使租约已过期，该任务仍可能一直 running。

已有普通异常处理会把供应商调用后失败记为 unknown 并拒绝重放，这是正确的边界；不能把它当作进程中断恢复已完成。路线图与能力矩阵已将此列为未验收项。本轮未运行媒体进程 kill 实验，结论来自领取条件与租约使用点的全仓核对。

建议记录外部请求开始阶段，区分可安全重试、需人工对账的 unknown 和终态失败；提供过期租约扫描、原子接管和操作入口，并补真实独立进程恢复验收，避免盲目重发付费调用。

### A13 网页入口上传限制没有贯通

位置：`deploy/k8s/production.yaml:228`、`:249`；`frontend/nginx.conf:13`。

仅 API 域名的 Ingress 配置了 proxy-body-size=260m，网页域名的 Ingress 没有；前端 API 使用同源网页入口。即使 web Nginx 配置 256m，外层 ingress-nginx 仍先执行自己的限制。在没有全局覆盖、采用常见默认 1m 限制的控制器上，合法的较大知识文件/媒体上传会提前返回 413。

此项依赖部署环境的控制器全局设置，不应声称每个现有集群都必然复现；A06 的网络策略修复后也仍需单独处理这个限制。

建议在实际承载上传的 web Ingress 显式配置与服务端一致的上限、请求超时，并用小文件、临界值和超限请求做 app 域名端到端验证。

## P3：文档与能力边界

### A14 当前说明未同步，历史“完成”语义容易误导

具体冲突：

- `README.md:34` 仍称头像不支持上传及账户删除，`docs/02-UI设计规范.md:123` 也称不支持上传；当前已有头像上传/本地裁剪与 DELETE `/auth/me`。账户删除“接口存在”与其可靠性通过验收是两个不同问题，见 A03。
- `README.md:13`、`docs/api-deprecation-policy.md:3` 仍用“当前”描述 354 路径，本次契约为 357。具有日期和原验证语境的历史验收数字应保留，不应追溯全部改成新数字。
- `docs/04-接口文档.md` 混合设计目标和实现说明，如通用 jobs、用户路径、统一错误信封、幂等和并发约定；独立阅读时不能直接当作可调用的现行契约，应标注设计范围并链接实际 OpenAPI。文档中心虽声明 OpenAPI 优先，仍有同步成本。
- `docs/23-global-intelligence-coordination.md:5`、`docs/25-provable-autonomy-global-continuous-intelligence.md:5`、`docs/28-global-cognitive-commons.md:5` 使用“已完成”“生产门禁”，并描述 TEE 在线证明、三区主动运行、密码学遗忘和四节点 BFT。当前 README 和能力矩阵则明确它们属于 experimental 规则/治理记录。

实现例证：`backend/app/services/provable_autonomy.py:22` 逐条检查输入的状态和转移；`:38` 对请求提供的副本数据做确定性合并；`:62` 的 erase_memory 返回带签名的 erased=true 声明，没有在此函数删除源数据、密钥、对象、缓存或备份。这些函数的规则测试通过不等于部署了完整分布式系统、形式证明器或密码学擦除机制。

建议在历史阶段文档首屏加入“历史设计/实验性控制面”标记，统一指向当前能力矩阵；维护一份当前发布状态，把设计愿景、已实现功能、已验证环境分开。根目录四份大设计文档也应明确适用阶段，避免旧架构和新实现并列为当前事实。

## 本轮验证结果

| 检查 | 结果与边界 |
| --- | --- |
| 后端全量 | **295/295**，Python 3.10.11，本机约 878 秒；无 failure/error/skip/expected failure，完整 discovery 覆盖 |
| 前端测试 | **83/83** |
| 前端生产构建 | vue-tsc、Vite、入口 bundle budget 通过；仍有 PURE/chunk 大小非阻断警告 |
| API 契约 | **357 paths** 验证通过；不是语义兼容或逐接口 E2E 认证 |
| TypeScript SDK | 构建通过 |
| Python 依赖一致性 | pip check 通过；这不是最新 CVE 漏洞库扫描，本轮未重新执行 Python 在线漏洞审计 |
| 前端依赖漏洞 | 本次 npm audit 返回 **0 vulnerabilities**，仅代表该次审计源与锁文件结果 |
| 迁移 | 临时空 SQLite 升级至 `20261020_0036`，降至 `20260729_0013`，再升级成功；单一 head |
| 全量清单/解析 | 546 份既有正式文件，Python/严格 JSON 解析通过；JSONC 由前端构建验证 |
| Markdown 本地链接 | 80 份既有文档，229 个本地目标存在；不含远程网址与锚点验证 |
| 审计复现 | 后端 9 组观察结果、前端保存竞态结果均与报告一致 |

后端全量原始 JSON 位于本机 `acceptance-artifacts/audit-2026-10-21-backend-tests.json`，该目录属于本地验收产物；问题复现结果保存在本报告旁的 probes，可随报告审阅。

本轮没有重新运行真实 PostgreSQL 带数据迁移、Docker 产品环境、Kubernetes/CNI/Ingress、全站浏览器按钮矩阵、付费模型、SMTP、真实 SSO/SCIM 或真实外部消息投递。历史报告中的相应通过记录只代表当时范围，不并入本轮通过项。

### 复现命令

从仓库根目录执行以下命令；Python 命令使用现有审计虚拟环境。隔离后端脚本禁用实际 `.env`、使用内存/临时数据库，并关闭后台循环及真实网络，不会删除业务数据。

```powershell
backend\.venv-audit\Scripts\python.exe docs/audits/probes/2026-10-21-backend.py
node docs/audits/probes/2026-10-21-editor.mjs
backend\.venv-audit\Scripts\python.exe docs/audits/probes/2026-10-21-migrations.py
backend\.venv-audit\Scripts\python.exe docs/audits/probes/2026-10-21-inventory.py
backend\.venv-audit\Scripts\python.exe docs/audits/probes/2026-10-21-doc-links.py
```

清单脚本重新运行时会纳入后来新增的正式文件，数量和哈希会随工作树变化；上文数字指本报告生成前的快照。复现脚本断言的是**审计时的缺陷行为**，用于保存证据；修复时应改成期望正确行为的正式回归测试，不能将“缺陷仍能复现”当作产品验收成功。

后端功能复现与结果：[脚本](./probes/2026-10-21-backend.py)、[JSON](./probes/2026-10-21-backend.results.json)；迁移：[脚本](./probes/2026-10-21-migrations.py)、[JSON](./probes/2026-10-21-migrations.results.json)；文档：[清单脚本](./probes/2026-10-21-inventory.py)、[链接检查脚本](./probes/2026-10-21-doc-links.py)。

## 建议修复顺序与验收

1. **数据与身份**：A01、A02、A03、A04。先防止编辑丢失、虚假安全策略和用户停止操作后继续执行；每项增加独立复现回归。
2. **调度与交付环境**：A05、A06、A07、A09、A13。用隔离环境演练正确发布顺序、实际网页入口、全部 worker 及至少两个定时周期，禁止只探测直接 API 健康接口。
3. **功能与恢复**：A08、A10、A11、A12。补认证下载、完整分页语义、提交失败可观察性和媒体中断恢复。
4. **文档同步**：A14。修复每项时同步当前能力边界与对应验收记录，保留历史事实。完成 P1 之后仍需按部署范围做真实环境验收，不能只依赖此次 295/83 项现有测试。

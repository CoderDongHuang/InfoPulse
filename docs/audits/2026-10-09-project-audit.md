# InfoPulse 项目审计与收敛路线

> 历史审计，描述修复前基线。当前整改状态、新增浏览器发现和验证边界见 [修复验收报告](./2026-10-09-remediation.md)。保留原始发现以便追溯，不能将下文的“尚未修复”视作最新状态。报告不包含真实凭据或用户数据。

审计日期：2026-10-09。代码基线：`467acf5`，分支 `codex/dependency-gates-paper-blog`。

本文是本地审计记录，不是发布认证。包含尚未修复的安全问题，不建议直接公开或推送。审计没有修改业务源码、真实业务数据库、账号配置或 GitHub PR。

## 1. 结论

项目已经具备较完整的工程骨架：前后端、数据库迁移、测试、SDK、配置模板、CI、许可证与文档均存在，多个模块有真实持久化与计算实现。但目前不能判断为“功能完整、所有链路通畅、可以稳定作为正式产品使用”。建议定位为开发者预览，而不是稳定 v1。

主要问题不是页面或接口数量不够，而是以下四类欠账：

1. 权限与网络访问边界不一致：公开注册可能授予管理员、普通账号能管理全局源、匿名模型调用、出站请求缺少完整 SSRF 防护。
2. 确定性运行故障：行动回执重复关键字、SQLite 时区比较、SSE 成功后仍超时、条件分支不匹配仍继续执行。
3. 成功状态与真实业务效果脱节：编排工具没有实际投递，行动启动没有完整执行器，工作流协作没有写回执行版本。
4. 验证承诺大于测试实际覆盖：单测和构建通过，但没有覆盖整个浏览器业务流程、真实外部服务、容器运行与干净安装环境。

不建议继续按阶段编号扩展新模块。先确定核心用户流程，并将已有模块收敛为可靠的、可复现的闭环。

## 2. 方法与验证边界

本次结合代码阅读、模块与请求路径盘点、自动化检查、隔离数据库测试和小范围故障复现。区分三种证据：

- **运行复现**：执行实际函数或前端辅助代码；必要时替换数据库/HTTP/模型依赖，不消耗模型额度、不访问真实内网。
- **代码确认**：顺着调用关系检查状态与落库路径，但未在完整部署环境运行该业务。
- **验证缺口**：不能从已有测试推出结论，需要额外验收。

本地分支与 GitHub 默认分支并非相同基线。本文的源码结论针对上述本地提交，不自动代表所有远程分支。测试数量也不等于功能覆盖率；未获得行覆盖率与分支覆盖率报告。

### 已执行的检查

| 检查 | 结果 | 能证明什么 / 不能证明什么 |
| --- | --- | --- |
| 后端编译检查 | 通过 | 无可见语法错误，不证明业务正确 |
| 后端全量 unittest | 154/154 通过，652.297 秒 | 现有测试场景通过，不代表所有 API、异常和并发场景通过 |
| 认证与公共契约补查 | 各 4 项通过 | 补查现有测试，不覆盖下面发现的所有权限漏洞 |
| 编排补查 | 5/5 通过，36.083 秒 | 现有审批、预算与静态评测测试通过，未覆盖真实工具投递和无匹配分支 |
| OpenAPI 快照检查 | 353 条路径通过 | 路径、operationId、响应状态码未漂移，不是请求/响应字段完整契约测试 |
| Alembic 隔离 SQLite 往返 | upgrade head / downgrade base / upgrade head 通过 | 当前迁移 head 为 `20260804_0029`；不证明真实 PostgreSQL 数据升级、性能或数据保留 |
| 前端类型检查与构建 | 通过 | 沙箱 `spawn EPERM` 经授权重跑解决，不是项目构建缺陷 |
| 前端 npm audit | 0 条已知漏洞，退出码 0 | 当前官方 npm registry 的审计结果；不证明应用逻辑安全，也不覆盖 Python 依赖 |
| TypeScript SDK | 构建与 audit 通过 | 不等于 SDK 所有真实调用场景通过 |
| Docker Compose | 配置解析通过 | 没有据此声称整个容器栈已启动或联通 |
| Playwright 冒烟 | 通过 | 当前脚本打开百度，不是 InfoPulse 浏览器端到端测试 |
| 文档本地链接 | 检查 37 个 Markdown，无断链 | 不证明文档描述与实现一致 |
| 前端请求静态匹配 | 285 处可识别请求未发现路由不匹配 | 仅 URL/HTTP 方法匹配，不检查载荷、权限、响应结构或全部动态请求 |

当前前端主包为 1,021.07 kB，gzip 327.89 kB，仍有大 chunk 提示及两条 `@vueuse/core` 注释警告。源码盘点为 86 个 TS/Vue 文件、42 个 Vue 视图、29 个 API TS 模块，`any` 出现约 300 次。后端有 32 个 `test_*.py` 文件。

### 未完成的验证

- 干净 Python 3.10/3.11 安装后的全量运行；本机已有依赖与声明范围不一致。
- Python 依赖漏洞审计；当前环境没有安装 `pip-audit`，不能报告 Python 依赖零漏洞。
- InfoPulse 真实浏览器用户流程、断网/401/超时/刷新/多窗口协作回归。
- 完整 Docker 启动、Nginx WebSocket、PostgreSQL/Redis/pgvector 联调。
- 微博/B站/贴吧等真实数据源、真实模型、SMTP/S3/SSO/第三方 Webhook 的完整验证。
- 任务崩溃恢复、并发配额、并发幂等、租户隔离负向矩阵与性能压力基线。

用户未配置 SMTP、S3、GitHub Token 等可选账号，不应自动认定为项目缺陷。正确的完成标准是能力明确关闭或明确降级，不是填写虚构凭据。

## 3. 真实架构与断点

项目目前至少存在以下三组流程。它们不能简单视为同一条已经完成的链路。

```text
微博 / B站 / 贴吧
  -> crawler.search -> RawPost -> workflows
  -> 洞察 / 时间线 / 解读 -> AnalysisHistory
  （未统一进入 DataSource / SyncRun / ContentItem 主链）

Hacker News / GitHub / DEV Community / arXiv / RSS
  -> Collector -> NormalizedContent -> source_sync
  -> DataSource / SyncRun / ContentItem
  -> 搜索 / 排名 / 事件 / 报告等持久化能力

组织 / 策略 / 编排 / 决策 / 行动
  -> WorkflowRun / WorkflowStepRun / ActionRun
  -> 审批与业务状态
  -> [缺少完整 dispatch -> 执行 -> 回执 -> 完成 的统一连接]
```

私有知识库、媒体处理、实时协作、开放平台与阶段 20-29 的治理能力又有各自的数据与执行边界。建议明确公共内容、租户私有内容、临时分析样本和外部副作用四种边界，而不是仅复用名称相似的模型。

## 4. 优先问题

以下 P1 表示应优先修复的安全或核心功能问题；P2 表示重要的稳定性与工程完整性问题。严重度以配置启用、多用户使用和本地开源场景为条件，不把所有开发默认值一概当作公网漏洞。

### A01 / P1：注册可自报管理员邮箱取得管理员身份

证据：[auth_service.py](../../backend/app/services/auth_service.py#L45)。`register_user` 直接根据用户提交的邮箱是否在 `ADMIN_EMAILS` 中设置 `is_admin`，没有验证邮箱所有权。

触发条件是配置中存在管理员邮箱且该邮箱尚未被注册。模拟数据库与配置调用实际注册服务，得到 `self_claimed_admin_email_is_admin=True`。

建议：公开注册永远不根据自报邮箱授予管理员；管理员由可信 bootstrap/CLI、受控邀请或人工审批创建。补充邮箱未验证、邮箱大小写、已存在账号和权限升级负向测试。

### A02 / P1：RSS 重定向绕过内网地址限制

证据：[rss.py](../../backend/app/services/collectors/rss.py#L21)。采集前检查初始 URL，但 HTTP 客户端启用 `follow_redirects=True`，后续重定向目标没有经过同样校验。

使用 MockTransport 模拟公开 IP 返回 302 到回环地址，实际采集器访问序列为：

```text
http://93.184.216.34/feed
http://127.0.0.1/internal
```

没有发送真实内网请求。建议逐跳校验 URL、解析 IP、禁止内网与保留地址，限制端口、跳数、响应大小，并处理 DNS 重绑定/实际连接目标问题。响应大小应在流式读取阶段限制，而不是完整读取后才检查。

### A03 / P1：连接器允许对任意内网 URL 发起 POST

证据：[commercialization.py](../../backend/app/services/commercialization.py#L39) 与 [ConnectorExecute](../../backend/app/schemas/commercialization.py#L14)。`HttpUrl` 只是 URL 类型校验，不是公网或供应商地址校验。安装记录审批也没有把本次目标 URL 约束到可信目的地。

在满足安装审批的模拟条件下，传入回环地址，MockTransport 捕获了实际 POST，结果为 `succeeded`。此问题需要账号拥有 `action.execute` 且存在已批准安装，不是匿名请求漏洞。

建议：Webhook 目标由受控安装配置绑定，不由每次执行任意指定；建立供应商/组织出站允许名单，并使用与 RSS 一致的出站安全策略。若确需内部 Webhook，使用显式管理员授权的受限内网策略，不能默认开放。

### A04 / P1：热搜解读匿名调用模型

证据：[hot_search.py](../../backend/app/api/hot_search.py#L20)。`POST /api/v1/hot-search/explain` 没有身份依赖；配置模型后会调用模型服务。

TestClient + 模拟解读服务复现匿名 HTTP 200，服务被调用 1 次，没有真实消耗额度。建议对有成本的生成操作鉴权、限流、限额，并将公开只读榜单与生成接口分别设计。

### A05 / P1：普通用户可以修改全局数据源

证据：[sources.py](../../backend/app/api/sources.py#L98) 与 [DataSource](../../backend/app/models/intelligence.py#L45)。源是全局共享实体，而新增、更新、删除与同步仅验证“已登录”。

普通注册用户可以停用他人使用的共享源、删除尚无内容的 RSS、反复触发同步。内置源不能删除、已有内容 RSS 不能删除，并不弥补共享写权限问题。

建议：公共源仅管理员可写；租户私有源必须有所有权和租户过滤；同步增加权限、限频、互斥与审计。不能用隐藏前端按钮替代服务端授权。

### A06 / P1：行动回执创建必然产生重复关键字异常

证据：[action_loop.py](../../backend/app/api/action_loop.py#L58)。

```python
ActionReceipt(
    organization_id=ctx.organization.id,
    action_id=aid,
    evidence_content_ids=ev,
    **p.model_dump(),
)
```

`ReceiptCreate` 的 `model_dump()` 也包含 `evidence_content_ids`，即使是默认空列表。调用实际 API 函数复现 `got multiple values for keyword argument 'evidence_content_ids'`，合法回执无法保存。

建议：排除已显式传入的字段，并检查 `run_id`/`step_id` 是否属于本行动与组织。验收需要 HTTP 层创建、数据库保存、详情读取、跨行动拒绝完整回归，不能只测试模型构造。

### A07 / P1：SQLite 日期读回导致行动运营接口崩溃

证据：[action_loop.py](../../backend/app/api/action_loop.py#L82)。代码把 `due_at` 与 `datetime.now(timezone.utc)` 直接比较。

真实内存 SQLite 将 `DateTime(timezone=True)` 的 UTC 时间写入再读出，`tzinfo` 变为 `None`；比较复现 `can't compare offset-naive and offset-aware datetimes`。行动运营函数对 naive 数据也产生相同异常。无截止日期的空数据测试不会暴露该问题。

建议：统一数据库 UTC 时间适配与比较入口；巡检其他“数据库时间 vs aware now”的比较。SQLite 与 PostgreSQL 都要有真实读写往返测试。

### A08 / P1：SSE 成功/失败后不清理计时器

证据：[sse.ts](../../frontend/src/utils/sse.ts#L74)、[InsightView.vue](../../frontend/src/views/insight/InsightView.vue#L35)、[agent.ts](../../frontend/src/api/agent.ts#L4)。只有显式 `close()` 清 interval，EOF、HTTP 错误、异常没有统一终结清理。

将实际 TypeScript 辅助代码转译后，以 fake fetch / clock 运行，结果为：

```json
{"response":"result_then_EOF","events":["result","timeout","timeout"],"clearedIntervals":0}
{"response":"HTTP_401","events":["error","timeout","timeout"],"clearedIntervals":0}
```

洞察视图成功后没有关闭连接，随后会出现错误提示；Agent 只传 `onEvent`，HTTP/网络失败走 `onError` 时可能一直保持 `streaming=true`。

建议：在 helper 中定义幂等终结操作，EOF/异常/超时/取消统一清理 timer、reader 和控制器；业务视图处理全部终态。增加 success、401、断流、超时一次性通知、卸载等测试。

### A09 / P1：无匹配条件仍进入本应不执行的分支

证据：[orchestration.py](../../backend/app/services/orchestration.py#L67)。`next_node` 使用 `(selected or edges)[0]`，没有无匹配分支语义。

实际函数复现：只有一条 `condition=true` 的出边，节点输出 `result=False`，仍返回该出边目标 `send`。条件门禁因此可能失效；并非所有副作用都会发生，因为工具仍有独立权限审批。

建议：明确无匹配时停止/失败/走显式 default，拒绝歧义图；不要用任意第一条边兜底。如果支持并行 DAG，还需真正实现 fork/join；目前执行器主要是单一路径遍历。

### A10 / P1：编排工具“queued”不是实际投递

证据：[orchestration.py](../../backend/app/services/orchestration.py#L105)。`tool_guard` 在审批通过后只返回描述字典，未创建持久派发任务、未调用连接器执行器。后续 `execute_one` 把 step 标为 `completed` 并继续运行。

仓库存在另一个真实 HTTP 执行入口 `commercialization.execute_connector`，但没有找到消费上述 `dispatch` 并把结果反馈给编排步骤的调用链。内置 `memory.read/write` 工具同样不能仅靠字典结果视为真实执行。

建议：建立持久化 dispatch/outbox、worker、幂等键和回执映射；step 只有获得实际结果才完成。未配置模型的 agent 节点目前返回占位文本并累计估算费用，应标记 `unavailable`/`degraded`，不能表现为正常完成。

### A11 / P1：行动启动与执行回执之间没有完整闭环

证据：[action_loop.py](../../backend/app/services/action_loop.py#L13)、[action_worker.py](../../backend/app/services/action_worker.py#L7)。`start` 创建 ActionRun 并标记 `executing`，当前 worker 仅做逾期扫描，不执行 ActionStep，也不处理执行结果或死信重试。

真实连接器执行是独立 API，未见其自动更新 ActionRun/ActionStep 和形成 ActionReceipt 的闭环。已有所谓 E2E 测试仅验证直接调用 `create_run` 的记录与幂等，不证明外部执行完成。

建议：把业务“行动”与技术“编排”的关系写成明确契约，再用相同派发能力承接副作用；保留两个领域模型的不同职责，不强行合并全部状态机。

### A12 / P1：工作流协作成功但不写回工作流

证据：[collaboration.py](../../backend/app/services/collaboration.py#L40)。`verify_resource` 支持 workflow，界面也允许选择 workflow，但 `sync_resource` 对非 report 直接返回。

变更会更新 CollaborativeDocument snapshot，实际 WorkflowVersion/active_version 不变。建议修改工作流生成新的草稿版本，经过图验证与发布门禁后激活；不要直接改已发布版本。验收应比较协作后的执行版本和运行结果，不只是 snapshot。

## 5. 重要稳定性与工程问题

### B01 / P2：测试环境与 requirements 不一致

| 依赖 | 项目声明 | 本机实际 |
| --- | --- | --- |
| fastapi | `>=0.109,<0.110` | `0.112.0` |
| httpx | `>=0.26,<0.28` | `0.28.1` |
| playwright | `>=1.62,<2` | `1.61.0` |
| openai | `>=1.7,<2` | `2.38.0` |

当前 Python 为 3.10.11。只读查询官方 PyPI 确认 Playwright 1.62/1.63 可用，不能把沙箱内查询失败误判为版本不存在。真正的问题是现有环境不能代表声明依赖安装结果。

建议在独立干净环境解析依赖、运行测试并锁定可复现版本；审计完整传递依赖，输出 SBOM。升级 PR 必须按新的依赖组合验证，不能以旧环境的通过结果背书。

### B02 / P2：超时预算不统一

[request.ts](../../frontend/src/api/request.ts#L27) 的同步请求预算为 30 秒，贴吧采集允许 45 秒，后续模型还会继续调用。[llm.py](../../backend/app/core/llm.py#L20) 没有显式业务级 timeout/retry 预算。

存在“前端已经失败，后台仍生成结果”的风险；这是代码预算不一致，不是本轮对所有真实网络条件的复现。建议耗时流程进入持久任务或 SSE，并支持总预算、取消语义、请求去重和已有结果查询。

### B03 / P2：知识处理状态可能永久停留 processing

[knowledge.py](../../backend/app/services/knowledge.py#L61) 先提交 `processing` 再访问存储/解析；worker 只认 queued，循环吞异常。worker 崩溃或 staging 读取异常后，没有在该路径看到 processing 的超时回收。

建议使用 lease、heartbeat、attempt、next_retry_at；失败有日志与原因；崩溃后可恢复，而非只依靠进程内 Queue。避免同步 S3/解析重任务长时间占用异步 API 事件循环。

### B04 / P2：默认网络边界与文档不符，WebSocket 代理缺失

[docker-compose.yml](../../docker-compose.yml) 的 `8000:8000` / `5173:80` 默认绑定所有宿主接口，而路线图声称不默认公开监听。建议本地 profile 绑定 `127.0.0.1`，LAN 使用另行显式开启。

[nginx.conf](../../frontend/nginx.conf#L10) 没有 WebSocket Upgrade/Connection 转发设置，而协作前端连接同源 `/api/v1/multimodal/ws/...`。这是容器入口的配置缺口，尚未运行完整容器进行握手复现。Vite 开发路径与 Docker 路径都需要单独验收。

### B05 / P2：认证撤销、限流与开发指标入口

refresh 接口会重新发 token，但未见 token family、jti、服务端撤销与单次消费记录；前端退出仅清 sessionStorage。登录/注册/生成还需要明确限流和配额。

`METRICS_TOKEN` 为空时指标接口开放；生产 Settings 已有检查，不能说生产 guard 不存在。开发环境也应显式启用或绑定本机，默认敏感指标不要暴露。弱开发 JWT 密钥应由首次初始化生成，不填固定“完整配置”冒充安全配置。

### B06 / P2：API 契约与评测门禁覆盖不足

`api_contract_check.py` 冻结路径、operationId、deprecated、响应状态码，没有冻结参数、required、请求/响应 schema。字段删除或类型变化可能不触发门禁。

`orchestration.evaluate` 只比较图中工具与 `forbidden_tools`，没有运行用例输入、评估输出或引用质量。应明确称为静态安全检查，真实模型质量评测需要另一套执行与评分基线。

### B07 / P2：实验模块命名超出实现保证

例如 `adaptive_intelligence` 的数字孪生是给定拓扑的 BFS 传播；透明日志是签名哈希链，不能等同完整 Merkle inclusion proof；`policy_gate` 信任调用者提交的 formal_result、sandbox_diff 与 approver_ids。

`provable_autonomy.model_check` 是有限规则检查；`erase_memory` 生成签名“已删除”声明，相关 API 更新治理记录状态，但未形成源数据、向量、对象存储、缓存和备份的真实删除闭环。

这些计算可以作为实验性规则模型，不能表述为已经完成分布式执行、形式化验证、真正多方审批或删除证明。建议分级为 stable/beta/experimental，不能由客户端声明替代可信审批事件与运行证据。

## 6. 重叠代码应该怎样收敛

没有用“相似命名”或 `any` 数量推断所有模块都应合并，也没有测得整仓重复率。可以明确看到的收敛对象如下：

| 重叠面 | 当前代价 | 建议边界 |
| --- | --- | --- |
| crawler + collector 两套采集 | 样本、健康、历史与来源覆盖不一致 | 统一来源适配器结果、清洗去重、落库与诊断；保留公开讨论和资讯的业务差异 |
| workflows + analyses/agent/reports | 模型调用、降级、引用和结果状态分散 | 共享模型预算/错误/来源契约，业务任务仍分别实现 |
| automation 通知 + platform webhook + commercialization connector + orchestration | 外部副作用、重试、幂等和回执重复且未互通 | 统一出站安全与投递基础设施，不混淆 webhook 发布和业务通知 |
| WorkflowRun + ActionRun + 审批流 | 有状态记录却缺少统一执行连接 | 明确领域状态转换与技术 dispatch 关联，禁止凭“queued”跳到完成 |
| tenant/permission/serialize/error 处理 | 各模块过滤与输出口径不一致 | 少量共用的租户查询、权限策略、UTC、DTO 和错误响应；不要一次性重写所有 API |
| 大型 Vue 单文件与大量 any | 异常状态、响应字段漂移难被发现 | OpenAPI 类型生成、领域 composables、组件与单元测试，按实际热点拆分 |

优先消除重复的策略与副作用实现，其次处理普通工具函数重复。不要以一个巨型 BaseService 或一个万能状态机承载所有模块。

## 7. 模块完成度的判断

| 模块组 | 当前判断 | 发布前重点 |
| --- | --- | --- |
| 认证、企业、多租户 | 有实现和测试，但管理员注册和共享源权限有缺口 | 权限矩阵、撤销、越权负向测试 |
| 洞察、创作、时间线、热搜、历史 | 主流程和本地降级存在 | 数据源语义、SSE 终态、模型预算、真实源状态 |
| 采集、内容、搜索、事件、分析、报告 | 持久化主链存在 | 将公开讨论接入/明确隔离，采集到报告可重复验收 |
| 订阅自动化、Webhook、连接器 | 多条实现存在 | 统一安全投递、实际到达、重试与回执 |
| 私有知识库、图谱 | 文档处理与检索存在 | processing 恢复、引用质量、权限、删除一致性 |
| Agent、工作流、模型路由、评测 | 运行记录和审批存在，但执行语义不完整 | 条件正确性、真实工具、真实评测、并发幂等 |
| 多模态、实时协作 | 资源与协作结构存在 | 模型依赖明确关闭、workflow 写回、WS 入口验收 |
| 决策室、行动、影响评估 | 记录和部分计算存在 | 回执故障、实际执行、状态完成与指标归因边界 |
| 阶段 20-29 治理与自治能力 | 大量规则/声明/记录型实现 | 实验标签、可信输入、能力边界，不作生产能力保证 |
| 运维、安全、发布、SDK | 工程框架齐全 | 干净安装、Python audit、真实 E2E、容器与数据库矩阵 |

此表不是逐个按钮全部实测通过的清单。没有真实外部账号或完整部署验证的能力均不能判为已完成。

## 8. 为什么现有测试没有拦住这些问题

1. 部分测试直接调 service 或构造 ORM 对象，绕过 API 参数合并、依赖、事务和响应序列化。
2. 空数据与缺少日期的样本不能暴露 SQLite 时区故障。
3. 编排测试覆盖默认拒绝、审批和预算，没有验证实际工具副作用与无匹配出边。
4. 名为 E2E 的行动测试只验证创建运行记录，并未走浏览器、执行器、真实回执和完成状态。
5. Playwright 脚本仅确认浏览器可以启动和打开百度，没有覆盖本产品。
6. 前端缺少可见的 Vitest/产品 Playwright 测试脚本；类型检查不能发现 timer 泄漏和 loading 永不结束。
7. 构建、OpenAPI 路径快照和 Compose 解析属于不同层级，不能相互代替功能验收。

后续每个已修问题至少增加一个“原始缺陷会使测试失败”的回归案例，不仅新增一个正常返回 200 的测试。

## 9. 优化路线与验收

时间为建议排期，不是实施承诺。由 P1 修复和验证先行，再做结构收敛。

### 第 1 阶段：0-2 周，安全与确定性故障

- 修复 A01-A09：管理员注册、SSRF、匿名模型调用、源权限、回执、UTC、SSE、条件语义。
- 补 HTTP/前端 helper 的回归及租户/角色负向矩阵。
- 建立干净 Python 安装、Python audit、锁定依赖组合；默认本机绑定与 WebSocket 配置补齐。

验收：普通用户不能授予管理员或写全局源；出站内网与重定向测试拒绝；合法回执能保存并读取；SQLite 日期场景不 500；SSE 每次只进入一个终态；不满足条件绝不进入受限分支。不得遗留未接受风险的 P1 后发布稳定版。

### 第 2 阶段：2-4 周，打通实际业务闭环

- 定义统一采集结果与来源追踪，明确临时样本如何进入持久化主链。
- 实现 dispatch/outbox、执行 worker、幂等与回执关联，补齐 A10-A12。
- 协作生成工作流草稿版本，验证后再激活。
- 建立可重复 fixture：采集 -> 内容 -> 事件 -> 分析 -> 报告 -> 通知 -> 回执。

验收：一次完整运行能追溯来源和证据；副作用只能在已授权情况下实际发生；重复提交不重复发送；未投递不能 completed；协作后的执行版本与预期一致；失败有可重试的终态。

### 第 3 阶段：1-2 个月，测试与可维护性

- OpenAPI schema 兼容检查与生成前端类型，分批移除高风险 any。
- 引入前端单测与本产品 Playwright，覆盖 401/断网/取消/长任务/两用户协作。
- SQLite/PostgreSQL 与独立 worker 的集成矩阵；任务 lease、重试、死信、恢复。
- 拆分测试层级、前端业务 composables 和按领域懒加载，建立构建体积预算。

验收：从零安装可重复；CI 捕捉响应字段漂移和本轮故障；worker 中断恢复不丢任务；两用户/两租户互不可越权；首屏资源和核心 API 延迟有实测预算。

### 第 4 阶段：3-6 个月，质量、可观测性和实验隔离

- 可选真实源 canary，不把验证码/限流误判为项目核心失败。
- trace_id 覆盖 API、采集、模型、任务、通知；记录重试原因与成本。
- 固定模型评测集，度量引用完整率、无证据拒答、结构正确率与失败降级。
- 验证对象存储/向量/缓存删除一致性、备份恢复；实验模块按插件或 feature flag 隔离。
- 只在用户需求明确的模块投入真实分布式、形式化或多方治理实现。

验收：能解释一次结果来自哪里、实际运行了什么、失败在哪里、费用多少；实验性能力不会被误认为可信执行；恢复与删除能自动验证。

## 10. 文档应补全与更正的内容

1. README 的“默认仅微博/B站/贴吧”和“热搜是 B站公开热榜”与持久化源及当前 ranking 实现不一致，应按实际产品口径修改。
2. 将“未配置明确降级”逐模块列为 unavailable/degraded/disabled，尤其不要把编排占位文本视作正常模型结果。
3. 路线图的“不默认公开监听”与 Compose 端口绑定冲突，应同步默认值与说明。
4. 发布清单分开列编译、单测、HTTP 集成、浏览器 E2E、迁移、容器、外部账号验证，分别标明日期和证据。
5. 接口契约说明应明确目前只冻结操作元数据；增加 schema 兼容门禁后再升级承诺。
6. 行动闭环、编排、协作、删除证明等文档增加“已实现/未实现/实验性”边界。
7. 技术博客可以保留设计愿景，但每项设计都应分开说明当前代码、缺口和规划；不能用设计图代替运行证明。
8. 增加模块能力矩阵、威胁模型、任务状态转换图与关键 ADR，优先于继续扩充宣传性篇幅。

现有长博客和路线图本轮未改，避免把尚未修复的结论直接发布为新的完成声明。

## 11. GitHub 未合并 PR 补查

本轮只读查询到 11 个 open PR：#48-#58，主要是依赖更新；它们已有的 CodeQL 与 Release Gate 检查均显示成功。不是只有此前提到的三个。没有合并、重跑、修改或推送这些 PR。

其中包含 Pinia major、Playwright-stealth major、pypdf major 等升级。CI 通过不代表真实爬虫、解析、前端运行与业务交互兼容。由于没有确定用户当时指的三个 PR 编号及其本地报错栈，不能宣称已经定位那三次错误，也不能自动合并。

建议逐个在隔离环境按实际依赖组合验证：不仅安装/构建，还要浏览器导入、采集适配、文档解析和核心用户流程。先补上述门禁再处理 major 升级。

## 12. 下一步建议

先处理安全边界与可复现故障，再打通副作用和版本写回，最后重构重复代码。重构前固定关键场景，重构后以同一数据集比较结果、权限和副作用。

本次新增的唯一交付文件是本审计记录。没有据此修改功能、填入凭据、提交分支或改变 GitHub 仓库状态。

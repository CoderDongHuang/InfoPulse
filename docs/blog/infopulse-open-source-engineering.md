# 从舆情工作台到可验证智能平台：InfoPulse 的开源工程设计

> 2026-10-15 补充：第 75–81 节记录真实工作台报告、顶部导航、右上头像菜单、个人中心和搜索入口的设计与实验，配图独立保存在 `docs/blog-assets/2026-10-15/`。旧章节的侧栏与历史截图保留用于说明演进过程，当前界面以新增章节及 R19 专项为准。本文是工程案例报告，不是同行评审论文，测试计数不等于覆盖率或模型质量。

> 2026-10-13 修订说明：第 1–46 节保留 2026-08-08 的设计背景，第 47–55 节是 2026-10-09 审计时点；其中 154/188 项测试、353/354 条路径、7 组浏览器检查和“完整镜像待验收”等描述不得当作当前结果。第 56 节起追加本轮真实失败、根因、修复与实验：完整 Chromium/ffmpeg 镜像、14 张核心表迁移、独立知识 worker、Windows 双版本、前端预算、取消、表格、媒体失败与认证事务。R04 Windows 实测基线为 198 项，后续测试数量以各 PR 最新日志为准。最新事实以 [逐项验收](../audits/2026-10-13-roadmap-progress.md)、[认证专项](../audits/2026-10-13-auth-durability.md)、[能力矩阵](../32-capability-matrix.md) 与 [路线图](../30-open-source-roadmap.md) 为准；不宣称外部提供商、全部按钮或所有 worker 已验证。

## 摘要

面向公开信息的舆情与情报系统正从关键词检索、热度统计演进到由大语言模型参与的证据归纳、事件理解和决策辅助。然而，模型生成的不确定性、外部数据源的不稳定性、跨租户数据隔离、异步任务的可恢复性以及第三方依赖的快速演进，使“能够生成一段答案”和“能够作为可信工程系统运行”之间存在显著差距。

本文以开源项目 InfoPulse 为研究对象，给出一种证据优先、可追溯、可降级的智能信息平台设计。系统使用 FastAPI、SQLAlchemy Async、PostgreSQL/SQLite、Redis、Vue 3 与 TypeScript 构建模块化单体和独立 Worker；通过统一 Collector 契约、来源定位、分析版本、租户上下文、工具默认拒绝、预算与审批状态机，将采集、检索、RAG、Agent、多模态分析、报告和行动闭环连接起来。本文不仅描述正常架构，还报告开源前实证验收：154 项后端自动化测试、353 条 API 路径契约、阶段 13 至 29 数据库迁移往返、前端与 TypeScript SDK 构建、Docker Compose 配置解析以及依赖审计。

研究结果表明，系统的主要可靠性收益并非来自更复杂的模型，而来自确定性边界：没有证据时拒答、外部源失败时显式降级、高风险工具由代码授权、租户过滤发生在查询层、任务状态持久化、迁移和 SDK 纳入发布门禁。依赖升级案例进一步说明，自动化更新机器人只能发现新版本，不能替代兼容性工程：TypeScript、Vue Router 与 LangChain OpenAI 的三个独立 major PR 均因兼容集合不完整而失败。本文给出对应根因、修复策略、有效性威胁和可复现实验协议，为类似 AI 工程项目从功能原型走向可审计开源系统提供参考。

## 关键词

舆情分析；开源情报；证据溯源；大语言模型；检索增强生成；Agent 编排；多租户；异步任务；供应链安全；可复现工程；FastAPI；Vue 3

## 研究问题与贡献

本文围绕四个研究问题展开：

- **RQ1：** 如何在数据源不稳定、模型服务可选的条件下，保持核心信息链路可用且不产生伪造内容？
- **RQ2：** 如何把引用、身份、租户、审批和幂等性设计为系统约束，而不是依赖 prompt 或开发约定？
- **RQ3：** 如何用可重复的工程实验判断一个大型功能仓库是否达到开发者预览版开源标准？
- **RQ4：** 自动依赖升级为何会在单包层面失败，如何建立兼容性集合与发布门禁？

本文的主要贡献包括：

1. 提出一条从公开采集、证据归一、分析版本到行动回执的端到端可追溯链路。
2. 总结模型不确定性与确定性治理代码之间的职责划分，并给出 Agent 工具、预算和审批的约束方法。
3. 给出覆盖代码、API、迁移、构建、SDK、供应链和真实 UI 的开源验收矩阵。
4. 公开报告失败的依赖升级案例，不以强制解析参数掩盖 peer dependency 和编译器接口冲突。
5. 明确结论的适用范围和有效性威胁，区分“本地开发可用”“外部链路已验证”和“生产规模就绪”。

![InfoPulse 工作台实览](../blog-assets/infopulse-dashboard.png)

## 1. 背景：信息很多，可信结论很少

公开讨论分散在社交平台、技术社区、新闻源和研究资料中。传统舆情工具常见两个问题：一是只给出热度和情绪，无法回到原始证据；二是把模型总结包装成事实，让使用者难以判断结论来自哪里。

InfoPulse 的出发点不是“再做一个聊天机器人”，而是建立一条可追溯的信息处理链：采集公开内容，保留来源定位，形成事件与观点结构，调用模型时携带证据，最后把洞察、报告、行动和审计记录连接起来。

项目坚持三个边界：

1. 重要结论必须能回到来源。
2. 没有证据时明确拒答或降级，不生成伪事实。
3. 采集器只能访问公开或明确授权的数据，不绕过平台权限。

## 2. 总体设计

```mermaid
flowchart LR
    A["公开数据源\nRSS / GitHub / arXiv / HN / 平台页面"] --> B["Collector 契约层"]
    B --> C["清洗、去重与来源定位"]
    C --> D[("PostgreSQL / SQLite")]
    D --> E["搜索、事件、知识图谱"]
    E --> F["证据约束的分析与 Agent"]
    F --> G["报告、订阅、决策与行动"]
    G --> H["审计、回执与影响评估"]
    R[(Redis)] --> I["任务调度与后台 Worker"]
    I --> B
    I --> F
    I --> G
```

后端使用 FastAPI、SQLAlchemy Async 和 Pydantic；前端使用 Vue 3、TypeScript、Pinia 和 Element Plus；PostgreSQL 是完整环境的数据底座，本地开发可以使用 SQLite；Redis 承担缓存和后台协调，但在基础开发场景下不可用也不会阻止 API 启动。

架构的重点不是技术栈本身，而是四个隔离面：

- 数据源与业务逻辑通过 collector 契约隔离。
- HTTP 请求与耗时任务通过 worker 隔离。
- 用户数据、企业租户与开放平台凭证通过所有权和权限上下文隔离。
- 模型生成与事实证据通过引用和拒答策略隔离。

## 3. 配置：默认能开发，生产必须显式安全

配置由环境变量加载。开发环境允许外部服务为空，但生产环境会拒绝默认密钥、SQLite、通配 CORS、内嵌 Worker 等不安全组合：

```python
def production_errors(self) -> list[str]:
    if self.ENVIRONMENT.lower() != "production":
        return []
    errors = []
    if self.JWT_SECRET_KEY.startswith("change-me") or len(self.JWT_SECRET_KEY) < 32:
        errors.append("JWT_SECRET_KEY must be a random value of at least 32 characters")
    if "sqlite" in self.DATABASE_URL.lower():
        errors.append("production DATABASE_URL must use PostgreSQL")
    if not self.CORS_ORIGINS or "*" in self.CORS_ORIGINS:
        errors.append("CORS_ORIGINS must contain explicit origins")
    return errors
```

开源项目不应该提交“可用的默认生产密钥”。InfoPulse 提供完整的 `.env.example`，但 LLM、SMTP、S3、SSO、GitHub Token 和平台 Cookie 保持为空，由使用者在本地注入。配置模板与 `Settings` 字段已做 1:1 校验，避免“代码支持但文档没写”的隐性功能缺失。

## 4. 数据采集：失败必须真实，结果不能伪造

所有采集器返回统一结构。同步服务负责幂等更新、失败记录和来源健康状态。设计原则是：平台返回空数据、限流或验证页面时，系统记录不可用状态并继续其他来源，而不是生成示例内容冒充真实采集结果。

```python
class BaseCollector(ABC):
    @abstractmethod
    async def collect(self, limit: int = 20) -> list[CollectedItem]:
        """Collect public items and preserve their source URLs."""
```

RSS 与网页入口还必须防御 SSRF。URL 在请求前解析并拒绝 loopback、私网、链路本地和非法协议，测试覆盖 `127.0.0.1` 等典型绕过目标。

## 5. 证据约束：没有引用就不输出确定结论

洞察、Agent 和知识图谱不是简单地把数据库内容拼进提示词。服务层先构建归属明确的证据集合，再要求输出中的 claim 绑定 citation；证据为空时返回拒答，不让模型用常识补齐事实。

```python
if not evidence:
    return {
        "status": "insufficient_evidence",
        "answer": "当前没有可核验来源，无法形成可靠结论。",
        "citations": [],
    }
```

这种设计会牺牲“什么都能回答”的表面体验，但换来三个工程收益：结果可复核、测试可确定、模型切换不会改变事实边界。

## 6. 认证、租户和高风险动作

JWT 只接受指定算法，并区分 access token 与 refresh token。受保护接口从数据库重新读取用户状态，停用账号不会因为持有旧 access token 而继续访问。

```python
payload = verify_token(token)
if payload is None or payload.get("type") != "access":
    raise HTTPException(status_code=401, detail="Invalid or expired token")

user = await get_user_by_id(db, payload.get("sub", ""))
if not user or not user.is_active:
    raise HTTPException(status_code=403, detail="Account is deactivated")
```

企业功能通过 `X-Organization-ID` 和 `X-Workspace-ID` 解析租户上下文，再执行角色权限判断。Webhook 密钥、SCIM token、API Key 不以明文持久化；外部写入、成本提高和敏感动作进入审批链，并保留幂等键、签名或补偿记录。

目前仍有两个明确短板：应用层尚未内建登录限流，refresh token 也没有服务端单次使用撤销。默认本地边界下可接受，但在任何网络暴露之前都应完成，这也是路线图的 P0 项。

## 7. 异步任务与应用生命周期

采集、知识处理、多模态处理、调度和行动执行由独立循环承载。开发环境可以把 Worker 嵌入 API 进程，生产配置则强制关闭内嵌 Worker，避免多副本 API 重复消费任务。

```python
run_embedded = settings.RUN_BACKGROUND_WORKERS_IN_API
scheduler_task = (
    asyncio.create_task(scheduler_loop(scheduler_stop))
    if run_embedded and settings.TASK_SCHEDULER_ENABLED
    else None
)
```

这一设计兼顾了“克隆后容易启动”和“规模化运行时职责清晰”。代价是全量测试涉及多个异步模块，当前 154 项测试约需 5 分 39 秒，后续需要拆分 unit、integration 和 e2e 矩阵。

## 8. 前端：按业务视图加载，而不是一个巨型控制台

前端路由使用动态 import，让洞察、报告、知识、企业治理、多模态和高级智能模块按页面加载。统一请求层负责注入 access token、刷新凭证和规范化错误。

```typescript
request.interceptors.request.use((config) => {
  const userStore = useUserStore()
  if (userStore.token) {
    config.headers.Authorization = `Bearer ${userStore.token}`
  }
  return config
})
```

当前构建可以成功完成，但公共主包仍约 1.02 MB，gzip 后约 328 KB。主要来源是 UI 组件与公共依赖，应通过更细粒度导入、vendor chunk 和 bundle budget 继续优化。

![InfoPulse 认证页面](../blog-assets/infopulse-auth.png)

## 9. 开源前如何验证“链路通畅”

一次构建成功不等于系统可开源。本次发布验收覆盖五个层次：

| 层次 | 验证 | 结果 |
| --- | --- | --- |
| 语法与类型 | Python compileall、Vue TypeScript | 通过 |
| 业务行为 | 后端 154 项测试 | 全部通过 |
| 接口契约 | 353 条 OpenAPI 路径 | 通过 |
| 数据演进 | Alembic 阶段 13→29 降级再升级 | 通过 |
| 构建与供应链 | 前端构建、Compose、SDK、npm audit | 通过；前端 0 个已知漏洞 |

典型验证命令：

```powershell
cd backend
python -m compileall -q app tests scripts
python -m unittest discover -s tests -v
python scripts/api_contract_check.py
alembic upgrade head

cd ..\frontend
npm ci
npm run build
```

CI 在 Pull Request 和默认分支 push 时重复这些检查；CodeQL 分析 Python 与 JavaScript/TypeScript；Dependabot 每周检查后端、前端、SDK 和 GitHub Actions 依赖。

## 10. 开源过程中发现的问题与解决方案

### 10.1 配置项不完整

`Settings` 中存在编排 Worker、知识文件大小和 GitHub Token 配置，但模板没有全部列出。解决方式不是手工目测，而是提取设置字段与 `.env.example` 键名做集合比较，最终做到无缺失、无未知项。

### 10.2 Python SDK 安装后可能无法使用

SDK 代码导入 `httpx`，原始 `pyproject.toml` 却没有运行依赖。已增加：

```toml
dependencies = ["httpx>=0.26,<1"]
```

TypeScript SDK 同时补齐 `exports`、类型入口、发布文件白名单和 MIT 元数据，并通过真实编译和 `npm pack --dry-run` 验证。

### 10.3 仓库能运行，但不等于可以合规开源

原仓库缺少 License、安全披露流程和贡献规范。现已增加 MIT License、`SECURITY.md`、`CONTRIBUTING.md`，并将入口放入 README。安全文档明确要求漏洞私下报告，避免公开 Issue 先暴露攻击细节。

### 10.4 文档很多，但导航与当前实现脱节

阶段文档已经推进到 29，根 README 仍主要描述早期六个页面。新的文档中心按首次阅读、开发、安全运维和能力演进重新索引，同时明确阶段能力与默认开源体验不是同一层级。

## 11. 实际展示与运行

本地开发使用 SQLite 时，只需配置数据库 URL，然后执行迁移：

```env
DATABASE_URL=sqlite+aiosqlite:///./infopulse.db
AUTO_CREATE_TABLES=false
LLM_API_KEY=
```

```powershell
cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

cd ..\frontend
npm install
npm run dev
```

浏览器打开 `http://127.0.0.1:5173`。模型 Key 为空时，依赖模型的能力会使用确定性降级或提示缺少配置；这使贡献者不需要购买外部服务也能开发大部分功能。

## 12. 从一次请求理解完整业务链路

仅看目录结构很难理解系统如何工作。以“用户创建一次热点洞察”为例，一次请求至少穿过浏览器状态、HTTP 契约、身份认证、数据访问、采集器、清洗器、模型适配器、持久化和结果呈现九个层次。

```mermaid
sequenceDiagram
    participant U as 用户
    participant V as Vue 页面
    participant A as FastAPI
    participant D as Auth Dependency
    participant S as Workflow Service
    participant C as Collectors
    participant L as LLM Adapter
    participant DB as Database

    U->>V: 输入主题并选择数据源
    V->>A: POST /api/v1/insights
    A->>D: 校验 access token 与用户状态
    D-->>A: 当前用户
    A->>S: 创建洞察任务
    S->>C: 并发采集公开内容
    C-->>S: 统一 CollectedItem 列表
    S->>S: 清洗、去重、风险标记
    S->>L: 携带来源证据请求结构化分析
    alt 模型可用
        L-->>S: 结构化结果
    else 模型未配置或失败
        L-->>S: 确定性降级结果
    end
    S->>DB: 保存输入、证据、版本与结果
    DB-->>A: 持久化对象
    A-->>V: 返回可解释结果
    V-->>U: 展示来源、观点和风险
```

这个链路有几个容易被忽视的工程细节。第一，认证不是只验证 JWT 签名，还会重新读取数据库中的用户，因此管理员停用账号后，旧 token 不会继续拥有完整访问能力。第二，采集失败不能被模型层掩盖。服务必须先得到真实证据，再决定是否调用模型。第三，结果对象需要保留版本，因为相同主题在不同时间、不同模型和不同来源下可能得到不同结论，覆盖旧结果会破坏审计能力。

前端请求层集中处理 token 注入和刷新，页面不直接拼接 Authorization 头。这样可以避免几十个 API 模块各自实现一套鉴权逻辑：

```typescript
request.interceptors.response.use(
  response => response,
  async error => {
    if (error.response?.status === 401 && !error.config.__retried) {
      error.config.__retried = true
      const refreshed = await userStore.refreshToken()
      if (refreshed) {
        error.config.headers.Authorization = `Bearer ${userStore.token}`
        return request(error.config)
      }
    }
    return Promise.reject(error)
  },
)
```

这里还需要防止刷新风暴。当多个请求同时收到 401 时，不能并发调用十次 refresh。Pinia store 使用 `refreshInFlight` 复用同一个 Promise；刷新结束后再清空引用。这是一个很小的实现，但能显著降低会话过期瞬间的异常流量和 token 竞争。

## 13. 领域模型：为什么不能只存一张“文章表”

舆情系统的难点不在于保存文本，而在于表达“文本从哪里来、属于哪个事件、支持什么观点、是否被分析过、谁可以访问、何时应该删除”。如果所有内容都塞进一张表，后续的搜索、引用、租户隔离和生命周期管理会相互污染。

InfoPulse 把领域对象分成五组：

1. 身份与租户：用户、组织、Workspace、成员、角色、策略和配额。
2. 信息对象：数据源、公开内容、事件、实体、关系和来源定位。
3. 智能产物：洞察、分析版本、对话、报告、提示词版本和模型路由。
4. 执行对象：订阅、任务、运行、通知、投递、审批、行动与回执。
5. 治理对象：审计、凭证引用、隐私预算、策略决策、证明和透明日志。

```mermaid
erDiagram
    USER ||--o{ ORGANIZATION_MEMBER : joins
    ORGANIZATION ||--o{ ORGANIZATION_MEMBER : contains
    ORGANIZATION ||--o{ WORKSPACE : owns
    DATA_SOURCE ||--o{ CONTENT : provides
    CONTENT }o--o{ EVENT : grouped_into
    EVENT ||--o{ ANALYSIS_VERSION : analyzed_as
    USER ||--o{ REPORT : authors
    REPORT ||--o{ REPORT_VERSION : versions
    USER ||--o{ AGENT_TASK : creates
    AGENT_TASK ||--o{ TASK_RUN : executes
    TASK_RUN ||--o{ DELIVERY_ATTEMPT : delivers
    ORGANIZATION ||--o{ AUDIT_LOG : records
```

模型层采用 SQLAlchemy 2.0 的 typed mapping。典型对象把业务字段、所有权字段和时间字段明确分开：

```python
class AnalysisHistory(Base):
    __tablename__ = "analysis_history"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    event_id: Mapped[str | None] = mapped_column(ForeignKey("events.id"))
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
```

上面的代码用于解释建模风格；实际仓库会按不同模块拆分更多字段。关键点是 `user_id`、`organization_id` 不能藏在 JSON 里，否则数据库无法高效执行所有权过滤，也难以利用外键和索引发现跨租户错误。

对于模型输出，JSON 并不意味着“无结构”。输入输出都先经过 Pydantic schema，数据库 JSON 只是为了保存版本化结构和兼容字段演进。需要过滤、排序或关联的字段仍应提升为普通列，而不是依赖数据库在大 JSON 上做全表扫描。

## 14. 数据库迁移：把阶段演进变成可验证历史

项目从基础信息平台逐步演进到阶段 29。数据库不能靠应用启动时 `create_all` 猜测差异，因此常规开发和部署都使用 Alembic。`AUTO_CREATE_TABLES` 只适合一次性开发环境，生产配置会拒绝它。

迁移的安全要求不只是“upgrade 能跑”。一次可接受的迁移至少要回答：

- 新表或新列在旧应用仍运行时是否兼容？
- 默认值会不会锁住大表？
- downgrade 能否恢复拓扑，或者明确说明为什么不可逆？
- SQLite 测试通过是否掩盖了 PostgreSQL 类型、索引和事务差异？
- 数据回填失败后如何恢复？

本次开源验收执行了阶段 13 到 29 的降级再升级：

```powershell
alembic upgrade head
alembic downgrade 20260729_0013
alembic upgrade head
```

这项测试验证的是迁移拓扑和 SQL 可执行性，不代表数十亿行数据上的锁等待已经被证明。面向大型生产数据时，应该采用 expand-contract 策略：先增加可空字段或新表，部署兼容新旧结构的应用，异步回填数据，切换读取路径，最后再删除旧结构。

```mermaid
flowchart LR
    A["Expand\n增加兼容结构"] --> B["Dual Read/Write\n兼容新旧版本"]
    B --> C["Backfill\n限速回填并校验"]
    C --> D["Switch\n切换主读取路径"]
    D --> E["Contract\n移除旧结构"]
```

迁移 Job 必须在应用流量切换前完成。仓库的发布工作流先渲染不可变镜像版本，执行 preflight 和 migrate Job，再调整 canary 流量。这个顺序避免新代码先接收到旧 schema 导致运行时错误。

## 15. Collector 设计：统一接口背后的现实复杂度

官方 API、RSS、Atom、HTML 页面和浏览器渲染页面的可靠性完全不同。统一 collector 接口不是为了假装它们一样，而是让差异停留在适配器内部，把业务层需要的最小事实暴露出来。

一个采集结果至少应包含：

```python
@dataclass
class CollectedItem:
    external_id: str
    title: str
    content: str
    url: str
    author: str | None
    published_at: datetime | None
    metrics: dict[str, int]
    raw_metadata: dict[str, Any]
```

`external_id` 与数据源共同构成幂等键。同步任务再次看到相同内容时更新变化字段，而不是插入副本。URL 是事实定位器，不能为了界面整洁而丢失。`raw_metadata` 保存暂时不进入统一模型的公开字段，但它不是长期堆积任意响应的借口，敏感字段和无用大对象必须在进入数据库前剔除。

### 15.1 HTTP 采集器

HTTP 采集器应设置连接、读取和总超时，限制重定向次数，使用明确 User-Agent，并对 429 与 5xx 区分处理。429 表示主动限流，应遵守 `Retry-After`；5xx 可以采用带抖动的指数退避；4xx 多数情况下不应盲目重试。

```python
timeout = httpx.Timeout(connect=5, read=15, write=10, pool=5)
async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
    response = await client.get(url, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
```

### 15.2 浏览器采集器

Playwright 只用于必须执行 JavaScript 的公开页面。浏览器进程昂贵且可能泄漏内存，因此 BrowserManager 负责复用、关闭和按内存阈值重启。项目不会实现验证码破解、设备指纹伪装或账号权限绕过。页面返回登录墙、验证页或空数据时，采集器应把来源标记为不可用。

### 15.3 SSRF 防御

允许用户添加 RSS 或知识网页意味着服务端会访问用户提供的 URL，这是典型 SSRF 入口。仅检查字符串是否以 `http` 开头远远不够。安全流程应解析主机、执行 DNS 解析、拒绝私有地址，并在重定向后重新校验目标。

```python
blocked = (
    ip.is_private
    or ip.is_loopback
    or ip.is_link_local
    or ip.is_multicast
    or ip.is_unspecified
)
if blocked:
    raise ValueError("Private network targets are not allowed")
```

进一步加固还应处理 DNS rebinding：连接使用校验后的 IP，TLS SNI 和 Host 仍保持原主机名；或者把外部抓取放入没有内网路由的专用网络沙箱。

## 16. 清洗、去重、事件聚类与风险评分

多个来源会转载同一新闻，也会用不同标题描述相同事件。简单比较字符串相等会产生大量重复；完全依赖 embedding 又会造成不可解释的误合并。InfoPulse 采用确定性特征与语义特征结合的思路。

清洗阶段先统一空白、移除模板噪声、保留原始 URL 和文本摘要，再生成规范化标题。ASCII 关键词使用词边界，避免 `AI` 匹配到 `said`；中文则采用适合连续文本的包含和分词策略。

候选聚类可以先用时间窗、来源和关键词倒排缩小范围，再计算标题 token、实体重合、链接引用和语义相似度：

```text
score = 0.30 * title_similarity
      + 0.25 * entity_overlap
      + 0.20 * semantic_similarity
      + 0.15 * temporal_proximity
      + 0.10 * explicit_reference
```

分数只是候选依据。跨平台事件如果没有实体、链接或可解释的共同证据，不应仅凭 embedding 接近就创建确定关系。测试覆盖“相似跨来源内容可以稳定聚类”和“没有跨平台证据时拒绝生成路径”。

风险评分同样不能是神秘数字。界面展示风险时，至少应能解释由哪些可见信号构成，例如来源集中度、未经证实的强断言、情绪极端程度、短时间异常增长和引用缺失。人工合并、拆分和锁定事件需要审计记录，自动任务不得覆盖人工锁定结果。

## 17. 搜索与知识图谱：相关不等于可信

搜索服务需要支持关键词、时间、来源、事件、热度和分页。返回结构统一包含 `items`、分页信息和 `has_more`，避免前端根据“返回数量是否等于 page_size”猜测还有没有下一页。

知识图谱的节点可以是人物、组织、地点、产品、事件和概念，边表示提及、引用、隶属、影响或明确关系。每条边必须带证据定位器：来源内容 ID、URL、文本片段或多媒体时间点。图谱不能因为模型认为两个实体“可能有关”就写入确定关系。

```mermaid
graph TD
    E1["事件：模型发布"] -->|"由其发布"| O1["组织：Example AI"]
    C1["来源内容 A"] -->|"支持"| E1
    C2["来源内容 B"] -->|"交叉验证"| E1
    P1["人物：发言人"] -->|"公开回应"| E1
```

图谱质量不只看节点数量。更有意义的指标包括：有证据边比例、孤立节点比例、跨来源验证比例、过期关系比例、实体合并冲突数和人工纠错率。大量没有证据的节点会让图谱看起来丰富，却降低实际价值。

## 18. 私有知识库与 RAG 安全

私有知识库允许上传 PDF、Word、图片或导入网页。这里同时存在文件安全、所有权、对象存储一致性、解析资源消耗和提示词注入风险。

上传入口不能相信扩展名和浏览器提供的 MIME。服务应检查文件头、限制大小和数量、拒绝伪装二进制文本，并把原文件放入按用户或租户隔离的存储路径。文档进入 `staged` 状态后由独立 Worker 解析；即使 API 进程重启，Worker 也能从数据库恢复待处理任务，而不是依赖内存队列。

```mermaid
stateDiagram-v2
    [*] --> staged
    staged --> processing
    processing --> ready
    processing --> failed
    ready --> deleting
    deleting --> deleted
    failed --> staged: retry
```

检索时必须先应用所有权和状态过滤，再做向量或全文相似度排序。如果先从全库取 top-k，再在应用层过滤，攻击者可能通过耗时、数量或错误信息推断其他租户内容。正确顺序是在数据库查询本身绑定 `user_id`、`organization_id`、`status=ready` 和数据驻留约束。

RAG 还要防止文档中的指令覆盖系统规则。知识片段是“不可信数据”，不是新的 system prompt。模型输入应明确分隔证据，并要求引用定位器；工具权限永远由服务端策略决定，不能因为文档写了“调用管理员 API”就提升权限。

删除不是把数据库状态改成 deleted 就结束。服务需要删除对象存储文件、切片、向量和派生图谱，再保证检索查询排除已删除版本。项目测试覆盖“删除文档不能被再次召回”和严格存储删除失败的处理，后续还应增加跨存储删除证明和定期一致性修复。

## 19. Agent 编排：从聊天转向受控执行

自由循环 Agent 容易出现无限迭代、成本失控、工具越权和不可复现。InfoPulse 的编排层把 Agent 表达为有向图：节点声明类型和配置，边声明条件；保存前验证无环、节点可达和起止节点完整。

```json
{
  "nodes": [
    {"id": "start", "type": "start", "config": {}},
    {"id": "research", "type": "agent", "config": {"prompt": "evidence-research"}},
    {"id": "review", "type": "approval", "config": {"permission": "action.approve"}},
    {"id": "end", "type": "end", "config": {}}
  ],
  "edges": [
    {"source": "start", "target": "research", "condition": "always"},
    {"source": "research", "target": "review", "condition": "has_evidence"},
    {"source": "review", "target": "end", "condition": "approved"}
  ]
}
```

工具策略采用默认拒绝。即使 prompt 要求调用某工具，运行时仍检查工作流声明、调用者权限、租户策略、预算和审批状态。模型路由定义主模型、回退模型、token 上限和成本上限，在模型调用前完成预算判断，而不是账单产生后才告警。

持久化运行是另一个关键点。遇到人工审批时，Worker 把运行状态写为 waiting，不占用协程等待数小时。审批完成后，新的 Worker 从数据库加载执行游标、输入、已完成步骤和幂等键继续运行。测试验证了“单独审批者批准后可以恢复”和“重复执行不会制造第二次副作用”。

```mermaid
stateDiagram-v2
    [*] --> queued
    queued --> running
    running --> waiting_approval
    waiting_approval --> running: approved
    waiting_approval --> rejected: rejected
    running --> completed
    running --> failed
    failed --> queued: retry with linked attempt
```

评测数据集用于在发布 prompt 或工作流前运行基线案例。除了期望答案，还可以声明 forbidden tools，确保模型即使输出质量不错，也不会通过越权工具达成结果。

## 20. 多模态证据：文本之外如何保持可定位

图片、音频和视频不是“交给模型看一下”这么简单。文本引用可以定位到 URL 和段落，多模态证据还需要页码、时间段、帧号和 bounding box。

图像分析结果中的对象应包含归一化坐标，避免原图缩放后定位失效：

```json
{
  "label": "brand mark",
  "confidence": 0.91,
  "bbox": {"x": 0.12, "y": 0.18, "width": 0.23, "height": 0.16},
  "source": {"media_id": "...", "frame": 0}
}
```

音频转写保留每个 segment 的开始和结束时间；视频按配置间隔抽帧，并限制最大帧数，避免长视频造成不可控成本。感知哈希用于发现近似图片，但它只说明视觉相似，不自动证明内容相同或来源可信。

检测到人脸、身份证件、地址或其他潜在个人信息时，结果进入 review，而不是直接用于报告或外部投递。媒体模型未配置时，任务应明确失败或保持待处理，不能用文件名猜测内容。

## 21. 自动化、通知与外部投递

订阅和定时任务最容易产生重复执行。系统需要同时处理时区、夏令时、静默时段、失败重试、通知聚合和幂等性。

任务运行通常使用“任务 ID + 计划时间窗”生成幂等键。数据库唯一约束是最终防线，应用层检查只是减少冲突。多个 Worker 同时领取任务时，需要行锁、原子状态更新或队列的 claim 机制。

```text
idempotency_key = sha256(
    task_id + scheduled_window_start + task_version
)
```

通知与投递分开建模。通知是用户收件箱中的业务事实，DeliveryAttempt 是邮件或 Webhook 的一次传输尝试。即使 SMTP 失败，通知仍应存在；重试只创建新的 attempt，不复制业务通知。

Webhook 请求使用时间戳、事件 ID 和原始 body 计算签名。接收方必须校验签名、时间容差和 event ID 去重：

```python
message = f"{timestamp}.{event_id}.".encode() + body
expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
valid = hmac.compare_digest(expected, signature)
```

仅有签名仍不能解决 SSRF。用户配置的 webhook URL 必须拒绝私网地址，并限制响应大小、重定向和超时。外部写入属于高风险动作，应在租户策略和审批通过后执行。

## 22. 开放平台与 SDK 设计

开放平台提供 API Key、OAuth 应用、Webhook 和连接器。凭证的共同原则是“明文只展示一次”。数据库存储哈希或密文，列表接口只返回前缀、权限、创建时间和状态。

API Key 可以表示为：

```text
ip_live_<public_prefix>_<random_secret>
```

服务端通过 prefix 快速定位候选记录，再使用常量时间算法比较哈希。scope 必须在每个开放接口执行，不能只在创建密钥时记录。密钥撤销后立即失效，日志中只能出现 prefix。

OAuth 授权码流程要求 PKCE S256，回调地址与注册值精确匹配，应用在安全审查通过前不能进入生产状态。连接器安装保存的是 `vault://...` 一类凭证引用，而不是把第三方密钥复制到普通业务表。

Python SDK 的最小客户端负责超时、鉴权、错误转换和 webhook 验签：

```python
from infopulse_sdk import InfoPulseClient

with InfoPulseClient(
    base_url="http://127.0.0.1:8000/api/v1",
    api_key="ip_live_example",
    timeout=15,
) as client:
    events = client.get("/events", params={"page": 1, "page_size": 20})
```

开源检查发现 Python SDK 原先没有在包元数据声明 `httpx`，这会导致用户安装成功但首次 import 或请求失败。现已添加运行依赖。TypeScript SDK 则补齐 `exports`、`.d.ts` 入口和 `files` 白名单，避免把源码缓存和开发文件发布到 npm 包。

SDK 下一阶段应从 OpenAPI 自动生成基础类型，再保留手写的鉴权、分页和 webhook 辅助层。完全手写 353 条路径既容易漂移，也会让 API 变更成本过高。

## 23. 企业多租户：隔离必须发生在查询层

多租户不是在页面上增加一个组织选择器。每个查询、缓存键、对象路径、任务、日志和费用记录都必须带租户边界。InfoPulse 使用 `TenantContext` 聚合当前用户、组织、Workspace、成员角色和权限。

```python
async def get_tenant_context(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    organization_id: str | None = Header(alias="X-Organization-ID"),
    workspace_id: str | None = Header(alias="X-Workspace-ID"),
) -> TenantContext:
    return await resolve_tenant(db, user, organization_id, workspace_id)
```

业务服务接受 context，而不是相信请求 body 中的 organization_id。创建对象时组织 ID 来自 context；读取对象时查询条件同时包含对象 ID 和组织 ID。仅在对象取出后比较组织 ID，容易产生时间差、错误信息侧信道和遗漏。

PostgreSQL 环境还可以通过 session context 与 Row Level Security 提供第二道防线，但 RLS 不能替代应用权限。应用仍需判断 `reports.read`、`agents.manage`、`action.approve` 等业务权限，数据库只负责行级隔离。

SSO 交换接口只信任受控身份代理，并使用长度足够的共享密钥做常量时间比较。组织必须存在且启用 OIDC/SAML provider，邮箱域需要符合租户策略。SCIM token 只保存哈希，轮换后旧 token 失效。

## 24. 安全威胁模型：从资产而不是漏洞清单出发

安全审计不能只搜索 `eval`、`shell=True` 和硬编码密码。更系统的方法是先识别资产、信任边界和攻击者能力。

### 24.1 关键资产

- 用户密码哈希、access token、refresh token。
- 平台 API Key、Webhook secret、SSO proxy secret、第三方凭证引用。
- 私有知识文档、派生向量和报告。
- 租户策略、审批记录、审计日志和成本数据。
- 公开内容的原始来源、引用和分析版本。

### 24.2 信任边界

```mermaid
flowchart TB
    Internet["不可信互联网"] --> Proxy["TLS / Reverse Proxy / Rate Limit"]
    Proxy --> API["FastAPI 信任边界"]
    API --> DB[("Database")]
    API --> Redis[("Redis")]
    API --> Worker["Worker"]
    Worker --> External["第三方平台与模型 API"]
    Worker --> Storage["Private Object Storage"]
    TenantA["租户 A"] -.必须隔离.-> TenantB["租户 B"]
```

### 24.3 主要威胁与现有控制

| 威胁 | 影响 | 当前控制 | 后续加固 |
| --- | --- | --- | --- |
| JWT 伪造 | 接管账号 | 指定算法、生产密钥校验 | 密钥轮换与 `kid` |
| 密码撞库 | 账号泄露 | bcrypt、统一错误 | Redis 限流、锁定与 MFA |
| refresh 重放 | 长期会话盗用 | 类型和过期校验 | jti 单次使用、token family 撤销 |
| SSRF | 探测内网和云元数据 | 私网 URL 拒绝 | 网络沙箱、DNS rebinding 防御 |
| 跨租户读取 | 私有数据泄漏 | TenantContext、所有权过滤 | PostgreSQL RLS 自动测试 |
| Prompt injection | 工具越权或数据泄漏 | 证据隔离、工具默认拒绝 | 注入评测集与输出策略 |
| Webhook 重放 | 重复外部动作 | 时间戳、event ID、签名 | 接收端去重示例与轮换 |
| 依赖投毒 | 构建或运行被接管 | Dependabot、CodeQL | lockfile、SBOM、签名镜像 |

默认开发密钥是本地便利与安全之间的折中。生产环境启动会拒绝默认值，但用户如果把 development 模式直接暴露到公网，仍然不安全。因此文档明确把默认边界限定为 localhost，并要求公网之前配置 TLS、限流、显式 CORS、Trusted Hosts 和独立 Worker。

## 25. 可观测性：日志不是把请求全部打印出来

项目的请求中间件生成 request ID，记录方法、路径、状态码和耗时。错误响应使用稳定结构，让前端和监控系统不必解析任意字符串。

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "fields": [{"path": "page", "message": "Input should be a valid integer"}]
  },
  "request_id": "424cc803-887a-4c3f-a0a8-d26acd797f85"
}
```

日志红线是不能记录 Authorization、Cookie、密码、token、完整 webhook secret 和用户上传正文。项目包含敏感形状脱敏测试，Operations Center 的反馈入口也拒绝看起来像凭证的数据。

指标标签必须保持低基数。`path=/events/{id}` 应记录路由模板，而不是把每个 ID 作为新标签；不能把 query、用户名或 request ID 放进 Prometheus label。否则一次攻击就能制造百万级时序。

下一阶段应引入 OpenTelemetry，把 API span 与数据库、Redis、采集器、模型调用和后台运行连接起来。模型 span 只记录模型名、token 数、成本、耗时和结果状态，不记录私有 prompt 正文。

```mermaid
flowchart LR
    R["request_id / trace_id"] --> API["API Span"]
    API --> SQL["SQL Span"]
    API --> Q["Task Enqueue"]
    Q --> W["Worker Span"]
    W --> M["Model Span"]
    W --> H["HTTP Collector Span"]
```

## 26. 测试策略：154 个测试分别证明什么

测试数量本身没有意义，重要的是覆盖哪些风险。InfoPulse 当前测试大致分为六类：

1. Schema 与契约测试：校验输入规范化、边界值、错误结构和鉴权要求。
2. 服务单元测试：用确定数据验证评分、聚类、策略、预算和状态机。
3. 数据库集成测试：验证所有权、幂等性、版本不可变和删除行为。
4. HTTP collector 契约测试：使用 MockTransport 验证真实响应映射和错误处理。
5. 安全测试：覆盖 SSRF、跨租户访问、secret 脱敏、原型污染和工具默认拒绝。
6. 端到端领域测试：验证决策到审批、行动、回执和影响评估的闭环。

一个好的测试应验证外部可观察行为，而不是复制实现。例如 refresh token 不得访问受保护接口：

```python
async def test_refresh_token_cannot_access_protected_endpoint(self):
    token = create_refresh_token({"sub": user.id})
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    self.assertEqual(response.status_code, 401)
```

事件聚类测试除了“能聚类”还要验证重复执行得到相同结果。自动化测试验证同一计划窗口只产生一次报告。开放平台测试验证 API Key 只存哈希、payload 篡改会导致签名失败。私有知识测试验证已删除文档无法被召回。

### 26.1 为什么全量测试较慢

当前 154 项测试耗时约 338.9 秒。耗时来自异步数据库建表、复杂领域测试和部分应用生命周期。CI 优化不能简单删除慢测，而应先测量每个文件耗时，再拆分：

```text
unit       < 60s   每次 push
contract   < 90s   每次 PR
integration 3-5m  每次 PR，并行分片
e2e        5-10m  合并与定时任务
external canary    每日，不阻塞普通贡献
```

外部 canary 与 MockTransport 测试职责不同。Mock 测试证明“解析逻辑在给定响应下正确”，canary 证明“第三方接口今天仍可访问”。前者稳定且适合 PR，后者容易受网络波动影响，应单独展示健康状态。

## 27. CI/CD 与供应链：从提交到可追溯制品

Release Gate 在 Pull Request 和默认分支 push 时执行后端编译、154 项测试、API 契约、迁移往返、生产配置检查和前端构建。CodeQL 每周及代码变更时分析 Python、JavaScript/TypeScript。Dependabot 覆盖 pip、前端 npm、SDK npm 和 GitHub Actions。

```mermaid
flowchart LR
    C["Commit / Pull Request"] --> T["Tests + Contract"]
    C --> Q["CodeQL"]
    T --> B["Build Images"]
    B --> P["Preflight"]
    P --> M["Migration Job"]
    M --> K["Canary"]
    K -->|healthy| S["Promote Stable"]
    K -->|failed| R["Rollback"]
```

部署工作流使用 commit SHA 或显式不可变版本作为镜像标签，不能只推 `latest`。迁移完成后先把少量流量切到 canary，健康验证成功再更新 stable；失败时把 canary 权重归零并回滚 Deployment。

当前供应链仍缺三个关键能力：

- Python 完整 lockfile：确保开发、CI 和镜像使用相同解析结果。
- SBOM：列出镜像内所有包、版本和许可证。
- 制品签名与 provenance：证明镜像来自该仓库的受控工作流。

建议采用 CycloneDX 或 SPDX 生成 SBOM，使用 GitHub Artifact Attestations 或 Sigstore 对镜像签名，并在部署策略中验证签名。

## 28. Docker 与本地开发体验

完整 Compose 包含 PostgreSQL/pgvector、Redis、后端和 Nginx 前端。后端镜像还包含 Chromium，因此构建时间、镜像体积和内存占用都高于普通 API。

```yaml
services:
  backend:
    build: ./backend
    env_file: ./backend/.env
    environment:
      DATABASE_URL: postgresql+asyncpg://infopulse:infopulse@postgres:5432/infopulse
      REDIS_URL: redis://redis:6379/0
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
```

健康检查分为 liveness 和 readiness 更合理。进程活着不表示数据库迁移完成或依赖可用；ready 失败时负载均衡器不应发送业务流量，但不一定立即重启进程。

开源开发体验下一步应增加 Compose profiles：

- `core`：SQLite 或 PostgreSQL、API、前端，不安装浏览器。
- `collectors`：增加 Chromium 和采集 Worker。
- `full`：增加 Redis、全部 Worker 和多模态依赖。

这样第一次体验者不必下载完整重型镜像，贡献采集器的人又能进入完整环境。

## 29. 前端信息架构与实际空状态

工作台不是营销首页。登录后第一屏直接展示关注、建议、最近浏览、报告和数据源状态。左侧导航按“开始工作、兼容工具、情报研究、个人空间”组织，避免把阶段 20-29 的所有概念平铺成无差别菜单。

真实截图中的“0 条”和“数据源尚未成功同步”是刻意保留的正确状态。许多演示项目会在数据库为空时生成漂亮的假趋势，这会让使用者误以为采集成功。InfoPulse 的空状态明确说明数据从哪里产生，并提供管理数据源入口。

前端组件需要稳定尺寸，加载状态不应推动布局跳动。错误、空、加载三种状态使用公共组件，但页面仍要给出业务语义。例如“暂无报告”与“报告加载失败”不能使用同一句提示。

移动端的主要挑战不是把桌面缩小，而是导航、表格、图谱和工作流编辑器如何重新组织。当前多数业务页有响应式规则，但尚未建立覆盖所有路由的移动端截图门禁，这是开源后的重要缺口。

## 30. 性能分析与容量规划

性能优化应从用户等待时间和资源瓶颈出发，而不是先给所有函数加缓存。InfoPulse 的主要成本中心包括：外部 HTTP 延迟、浏览器采集、数据库搜索、embedding、LLM 调用、多媒体解析和前端公共包。

### 30.1 API 与数据库

列表接口必须限制 `page_size`，通常上限 100。常用过滤组合需要复合索引，例如 `(organization_id, status, created_at)`。索引顺序应由真实查询和选择性决定，不能为每个字段单独建索引。

慢查询阈值通过 `SLOW_QUERY_MS` 配置。发现慢查询后，应记录脱敏 SQL 模板和执行时间，在 PostgreSQL 用 `EXPLAIN (ANALYZE, BUFFERS)` 确认是全表扫描、错误 join 顺序、排序溢出还是锁等待。

### 30.2 Worker

并发不是越高越好。`TASK_WORKER_CONCURRENCY` 需要同时考虑数据库连接池、外部平台限流、CPU、内存和模型配额。浏览器任务与轻量 HTTP 任务应使用不同队列，否则几个视频或 Chromium 任务就会阻塞所有通知投递。

### 30.3 前端

当前主 JS chunk 约 1.02 MB，gzip 后约 327.66 KB。虽然业务路由已经动态加载，Element Plus 和公共依赖仍进入共享包。优化步骤应该可测量：

1. 用 bundle visualizer 确认模块占比。
2. 检查图标和组件是否按需引入。
3. 为图谱、编辑器和高级治理模块建立独立 chunk。
4. 设置首屏 JS gzip budget，例如 250 KB。
5. 在 CI 中比较基线，避免一次依赖升级增加数百 KB。

### 30.4 建议容量指标

| 指标 | 初始目标 | 说明 |
| --- | --- | --- |
| API P95 | < 500 ms | 不含主动等待的模型与采集任务 |
| 搜索 P95 | < 800 ms | 典型租户数据量和 20 条分页 |
| 任务排队 P95 | < 30 s | 正常负载 |
| Webhook 成功率 | > 99% | 排除接收方永久 4xx |
| 引用完整率 | > 98% | 有事实 claim 的输出 |
| 前端首屏 gzip JS | < 250 KB | 后续目标，不是当前结果 |

## 31. 故障案例与解决思路

专业系统不仅描述正常路径，还要说明失败时如何定位。

### 31.1 Redis 不可用

启动日志会标记 Redis unavailable，但基础 API 仍可运行。依赖 Redis 的协调能力应进入 degraded，而不是悄悄假装成功。运维先检查连接地址、DNS、认证和 healthcheck，再判断是否需要暂停调度 Worker。

### 31.2 数据源返回 200 但没有内容

200 不代表采集成功，可能是验证页面、登录墙或 HTML 结构变化。采集器需要检查内容类型、关键节点和最小有效记录数，把原始响应摘要写入受控诊断日志，不能把整页 Cookie 或个人数据落盘。

### 31.3 模型超时

交互请求应有总预算。模型超时后，如果已有真实证据，可以返回确定性摘要和“模型分析暂不可用”；如果任务要求模型生成且无法降级，则记录失败并允许重试。重试必须链接原 attempt，防止审计记录断裂。

### 31.4 迁移成功但新版本 readiness 失败

先保持 stable 流量，不要继续 promote。检查新应用是否依赖未回填数据、环境变量是否缺失、Worker 是否错误嵌入 API。若 schema 向后兼容，可以直接回滚应用；若迁移破坏兼容性，需要执行已演练的 downgrade 或前向修复。

### 31.5 Webhook 重复送达

发送端因超时无法知道接收方是否处理成功，因此“至少一次”投递天然会重复。接收方必须按 event ID 去重，发送方使用同一业务事件 ID 创建新的 DeliveryAttempt，不能每次重试生成新事件。

### 31.6 删除文档后搜索仍命中

可能是事务未提交、向量索引异步延迟、缓存未失效或对象状态过滤遗漏。正确处理顺序是立即把文档状态改为 deleting/deleted，使所有查询先排除，再异步清理派生对象；定期一致性任务查找孤立切片和对象。

## 32. 开源文档为什么也是产品的一部分

开源使用者面对的第一个界面不是 Vue 页面，而是 GitHub 仓库。仓库简介、Topics、README 前两屏、许可证和启动命令决定他是否愿意继续。

文档分层如下：

- README：产品是什么、适合谁、如何在本地启动、哪些能力需要外部配置。
- 文档中心：产品、架构、接口、数据库、运维和阶段能力的导航。
- 配置指南：每个环境变量的默认值、必需性和安全边界。
- SECURITY：漏洞如何私下报告，维护者如何响应。
- CONTRIBUTING：开发、测试、迁移和数据采集合规要求。
- 路线图：哪些是已完成基线，哪些只是未来计划。
- 技术博客：解释为什么这样设计，以及真实权衡。

文档中最危险的错误是把“代码里有一个模块”写成“真实环境已经验证”。例如 SMTP、S3、SSO、微博 Cookie 和 LLM Key 留空是正确的开源处理，但文档必须说明空配置的行为。否则用户无法区分 bug、未配置和主动降级。

## 33. 从零开始的贡献者教程

### 33.1 获取代码

```powershell
git clone https://github.com/CoderDongHuang/InfoPulse.git
cd InfoPulse
git switch main
```

建议 Python 3.10 或 3.11、Node.js 20+。不要把已有全局 Python 环境的 `pip check` 结果当成本项目依赖状态；创建独立虚拟环境才能得到可重复结论。

### 33.2 后端最小环境

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

把 `.env` 的数据库改成 SQLite：

```env
DATABASE_URL=sqlite+aiosqlite:///./infopulse.db
AUTO_CREATE_TABLES=false
RUN_BACKGROUND_WORKERS_IN_API=true
LLM_API_KEY=
```

执行迁移和启动：

```powershell
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/docs` 查看 353 条 OpenAPI 路径。不要用 `--host 0.0.0.0`，除非已经理解网络暴露风险并配置安全边界。

### 33.3 前端

```powershell
cd ..\frontend
npm ci
npm run dev
```

Vite 默认把 `/api` 代理到后端。后端端口变化时，在 ignored 的 `.env.local` 写入：

```env
VITE_API_PROXY_TARGET=http://127.0.0.1:8001
```

### 33.4 提交前检查

```powershell
cd backend
python -m compileall -q app tests scripts
python -m unittest discover -s tests -v
python scripts/api_contract_check.py

cd ..\frontend
npm run build
```

数据库变更必须附带 Alembic migration；接口变更需要更新契约和 SDK；采集器变更必须提供 MockTransport 响应样本，并证明失败时不会生成假内容。

## 34. 架构权衡与没有选择的方案

### 34.1 为什么使用 FastAPI，而不是拆成许多微服务

当前团队和开源规模下，模块化单体更容易保持事务、一致测试和本地启动。服务层、模型层和 API 层已经按领域拆分，未来真正出现独立扩缩容需求时，可以先把 Worker 或媒体处理拆出，而不是现在承担分布式事务和本地开发复杂度。

### 34.2 为什么同时支持 SQLite 和 PostgreSQL

SQLite 降低首次贡献门槛，适合 schema、服务和界面开发；PostgreSQL 提供生产并发、pgvector、索引和更强约束。代价是必须避免只在 SQLite 工作的 SQL，并在 CI 增加 PostgreSQL 矩阵。SQLite 是开发兼容层，不是生产等价物。

### 34.3 为什么模型失败要降级，而不是让整个请求失败

数据采集和证据整理本身有价值。模型服务是昂贵且不稳定的外部依赖，完全绑定会让系统可用性等于模型提供商可用性。降级结果必须明确标记，不能假装与模型分析等价。

### 34.4 为什么不用模型自动决定所有工具

Prompt 不是授权系统。模型可能被注入、误解上下文或选择高成本工具，因此工具允许列表、预算、审批和租户策略由确定性代码控制。模型可以提出动作，不能给自己授权。

### 34.5 为什么不追求“全自动事实核查”

公开信息可能互相引用、来源不独立、语言含糊或持续变化。系统可以提供交叉来源、矛盾提示和证据链，但不能保证自动得到最终真相。高风险结论仍需要人工核验原始来源。

## 35. 不足、技术债与诚实边界

一个真正可维护的开源项目必须把不足写得和功能一样清楚。

### 35.1 外部数据源不稳定

真实微博、贴吧、B站和部分外部 API 会受页面结构、地区、限流、账号状态和服务条款影响。MockTransport 能证明解析器逻辑，却不能替代每日真实 canary。平台不允许访问时，项目不会通过对抗手段强行采集。

### 35.2 Python 依赖尚未完全锁定

`requirements.txt` 使用版本范围，便于兼容安全更新，但时间久后可能解析到不兼容组合。开发者全局环境中的 `litellm`、`mediapipe` 等无关包还可能干扰 `pip check`。需要在干净虚拟环境生成 lockfile，并对 Python 3.10/3.11、Windows/Linux 分别验证。

### 35.3 认证仍需加固

密码使用 bcrypt，JWT 有类型和生产密钥校验，但注册、登录尚未内建 Redis 限流，refresh token 也未做 jti 单次使用和 token family 撤销。项目默认只监听 localhost；进入任何共享网络前必须完成 P0 加固或在可信反向代理实施等价控制。

### 35.4 前端工程门禁不够完整

构建和类型检查通过，真实认证页与工作台截图正常，但缺少全路由视觉回归、WCAG 自动检查、键盘导航测试和系统化移动端 E2E。主包体积也超过后续期望预算。

### 35.5 高阶段能力需要更多用户验证

阶段 20-29 的治理、市场、全球协调和认知基础设施模块拥有确定性领域测试，但测试通过不等于真实组织会采用这些概念。后续应减少抽象能力扩张，优先用真实用户任务验证信息架构和价值。

### 35.6 国际化不足

当前主要文档和界面为中文，代码标识与部分运维文档为英文。国际贡献者缺少英文 README、贡献指南和界面语言包。国际化不仅是翻译，还涉及时间、数字、时区、法规和数据源差异。

### 35.7 生产规模仍需专项验证

迁移往返、功能测试和本地构建都已通过，但没有在本轮对大规模 PostgreSQL 数据、跨区域对象存储、数百并发浏览器任务或长时间 Worker 内存进行验证。生产容量结论必须来自独立压测和演练。

## 36. 分阶段优化路线

短期优先级不是继续增加新模块，而是让一个陌生开发者更安全、更快地成功运行。

### P0：0-4 周

- 增加 core/collectors/full Docker profiles。
- 实现 Redis 登录限流、失败计数、refresh jti 与 token family 撤销。
- 在干净环境运行 `pip-audit`，生成 SBOM。
- 增加 Linux/Windows startup smoke test。
- 增加演示数据命令、Issue 模板和 PR 模板。
- 为认证、工作台、数据源、洞察和报告补 Playwright 回归。

### P1：1-3 个月

- 建立真实数据源每日 canary 和状态页。
- 设计统一 connector SDK 与插件能力声明。
- 从 OpenAPI 生成 SDK 类型，建立 PyPI/npm 发布流水线。
- 拆分前端 vendor chunk 并设置 bundle budget。
- 将测试拆成并行 unit/integration/e2e 矩阵。
- 发布可重复的“采集到报告”示例工作流。

### P2：3-6 个月

- 使用 OpenTelemetry 打通 API、Worker、数据库、模型和采集器 trace。
- 建立引用完整率、拒答准确率、事实风险和 prompt injection 评测。
- 增加租户备份恢复、删除证明和对象存储一致性修复。
- 在 PostgreSQL/pgvector 上建立真实性能基线。
- 发布威胁模型和 Architecture Decision Records。

### P3：6-12 个月

- 稳定 v1 API 和 SDK 兼容承诺。
- 建立插件签名、最小权限沙箱和撤销机制。
- 明确维护者职责、版本支持周期和社区治理规则。
- 推进英文文档、WCAG 2.2 AA 与多区域合规评估。

完整里程碑与完成标准见 [开源优化路线图](../30-open-source-roadmap.md)。

## 37. 给维护者的发布检查表

发布前应逐项确认，而不是只看 CI 绿色：

- [ ] Release Notes 明确版本是开发者预览还是稳定版。
- [ ] `.env.example` 与 Settings 字段无缺失、无多余项。
- [ ] 仓库与 Git 历史未包含真实密钥、Cookie、数据库、日志和上传文件。
- [ ] 全量测试、API 契约、迁移往返、前端构建、SDK 构建通过。
- [ ] CodeQL 和依赖审计没有未处理高危问题。
- [ ] README 启动命令在干净环境重新验证。
- [ ] 外部服务未配置时的行为与文档一致。
- [ ] 截图不包含真实用户、token、邮箱或私有数据。
- [ ] License、SECURITY、CONTRIBUTING 和路线图可访问。
- [ ] 已知不足出现在 Release Notes，而不是隐藏在 Issue 深处。

## 38. 常见问题

### 没有 LLM API Key 能运行吗？

可以运行基础认证、数据管理、搜索、事件、报告结构和大部分确定性逻辑。依赖模型的功能会降级或明确提示未配置，不会自动调用收费服务。

### 为什么默认推荐 SQLite，却又说生产必须 PostgreSQL？

SQLite 用于降低本地开发门槛。生产需要 PostgreSQL 的并发、索引、pgvector、治理能力和运维工具。生产配置检查会拒绝 SQLite。

### Redis 挂了 API 为什么还能启动？

基础同步 API 与 Redis 解耦，便于本地开发和部分降级场景。任务协调、缓存或限流等依赖 Redis 的能力会受影响，应通过 readiness 和监控展示 degraded。

### 采集器为什么不自动绕过验证页？

因为验证页代表平台不希望当前访问继续。绕过验证码、伪造设备或规避账号权限既不稳定，也可能违反平台条款和法律边界。

### 阶段 20-29 是否都适合普通用户？

不是。普通用户主要使用工作台、洞察、事件、报告和知识能力；高级阶段更多是企业治理和研究性模块。后续会继续优化信息架构，避免所有概念同时暴露。

### 现在能直接部署公网吗？

仓库包含生产配置检查和部署模板，但默认开源边界是本地自托管开发。公网前至少需要 TLS、反向代理限流、强随机密钥、显式 CORS/Trusted Hosts、PostgreSQL、独立 Worker、备份和监控，并完成认证 P0 加固。

## 39. 实验设计与可重复验收协议

### 39.1 实验目标

实验不是为了证明 InfoPulse 在所有环境绝对正确，而是验证以下有限命题：当前提交在指定 Python/Node 环境能够安装和构建；核心领域规则在自动化样本下满足预期；API 路由与契约快照一致；数据库迁移拓扑可往返；空外部配置不会伪造成功；前端关键入口能够真实渲染；SDK manifest 与 lockfile 能完成干净构建。

### 39.2 环境与变量控制

本地验收使用 Windows、PowerShell、Python 3.10、Node.js 20+，数据库主路径使用 SQLite 以降低环境噪声。CI 使用 Ubuntu 与 Python 3.11、Node.js 22。LLM Key、平台 Cookie、SMTP、S3 与 SSO 凭证保持为空，从而验证无付费外部依赖的开发者基线。

实验控制变量包括：固定代码提交、固定 lockfile、`AUTO_CREATE_TABLES=false`、显式 SQLite URL、关闭不需要的后台调度、使用 MockTransport 提供外部 API 响应。非控制变量包括 GitHub Runner 镜像中预装工具、包仓库可用性和外部网络时延，因此依赖安装时间不作为性能结论。

### 39.3 验收矩阵

| 实验编号 | 对象 | 操作 | 判定条件 | 实际结果 |
| --- | --- | --- | --- | --- |
| E1 | Python 源码 | `compileall` | 无语法错误 | 通过 |
| E2 | 后端领域逻辑 | 154 项 unittest | 0 failure / 0 error | 通过，338.857 秒 |
| E3 | API 契约 | contract checker | 预期路径全部匹配 | 353 条路径通过 |
| E4 | 数据迁移 | 13→29 downgrade/upgrade | 迁移命令全部成功 | 通过 |
| E5 | 生产配置 | production check | 不安全配置被拒绝，完整配置通过 | 通过 |
| E6 | 前端 | `npm ci && npm run build` | 类型检查和构建成功 | 通过 |
| E7 | 前端依赖 | `npm audit --offline --omit=dev` | 无已知漏洞 | 0 vulnerabilities |
| E8 | TypeScript SDK | `npm ci && npm run build` | lockfile 安装与 `tsc` 成功 | TypeScript 7 下通过 |
| E9 | Compose | `docker compose config --quiet` | 配置可解析 | 通过 |
| E10 | 关键 UI | Playwright 截图 | 中文、布局、真实空状态可见 | 认证页与工作台通过 |

### 39.4 失败注入与负向测试

正向测试只能证明系统在理想输入下工作。更关键的是负向断言：refresh token 不能访问 access-only 路由；私网 RSS URL 被拒绝；用户不能读取他人知识文档；不存在证据时 Agent 返回拒答；重复幂等键不产生第二次副作用；Webhook payload 篡改导致签名失败；图谱没有跨平台证据时拒绝构造路径；生产环境默认 secret 阻止启动。

```python
test_cases = [
    "refresh_token_cannot_access_protected_endpoint",
    "rss_rejects_private_networks",
    "deleted_document_cannot_be_recalled",
    "no_evidence_returns_refusal_not_fabrication",
    "signature_detects_payload_tampering",
    "tool_policy_defaults_to_deny",
]
```

这种测试命名直接陈述安全不变量。与追求覆盖率百分比相比，不变量测试更能表达“哪些错误绝不能发生”。未来可把这些不变量转换为 property-based test，在更大的随机输入空间验证。

## 40. 结果分析与消融思考

### 40.1 RQ1：可用性来自降级边界

当 Redis 不可用时，基础 API 仍能启动；当 LLM Key 为空时，证据采集和确定性处理仍可测试；当单个数据源失败时，其他来源继续处理。这支持“外部依赖不应决定整个系统可用性”的设计。但降级不是返回成功状态和空对象，必须携带 `degraded`、`insufficient_evidence` 或来源健康信息，否则监控和用户会误判。

### 40.2 RQ2：治理约束必须位于模型之外

测试表明，工具默认拒绝、租户查询过滤、预算前置判断和审批持久化可以用确定性断言验证。若移除这些约束，仅在 system prompt 写“不要越权”，系统将无法证明跨租户隔离或成本上限。可以把这种对比视为概念性消融：删除确定性 guard 后，关键属性不再可由普通单元测试保证，只剩对模型行为的概率期待。

### 40.3 RQ3：项目完整性是向量，不是布尔值

154 项测试、353 条路径和构建通过支持“开发者预览可用”，但不支持“生产规模完整”。项目完整性至少包含功能覆盖、接口一致性、数据演进、安全控制、运维能力、文档可达性、外部集成真实性和用户价值验证八个维度。当前前五项基线较强，真实外部 canary、移动端 E2E、依赖锁定和高阶段模块用户验证仍不足。

### 40.4 RQ4：依赖机器人不能识别兼容性集合

三个失败 PR 形成了清晰对照：

| PR | 机器人操作 | 隐含兼容集合 | 失败点 | 决策 |
| --- | --- | --- | --- | --- |
| #37 | TypeScript 6→7 | TypeScript + vue-tsc + Vite | `./lib/tsc` 不再导出 | 关闭，等待工具链整体迁移 |
| #43 | Vue Router 4→5 | Router + Pinia + Vue | Pinia peer dependency 冲突 | 关闭，人工规划框架迁移 |
| #44 | langchain-openai 0.x→1.4 | LangChain + Core + OpenAI SDK | OpenAI 1.x/2.x 冲突 | 删除未使用 LangChain 依赖 |

如果使用 `npm --legacy-peer-deps`，E7 可能暂时安装成功，但运行时类型和插件契约仍未得到验证；如果同时放宽所有 Python 上限，pip 可能解析出一套新依赖，却引入大面积 API 迁移。这些“让安装命令变绿”的做法没有解决兼容性问题。

本轮复验还暴露了“离线审计假阴性”：`npm ci` 在线获取公告后报告 `nanoid <=3.3.16` 与 `postcss <=8.5.22` 两个高危传递依赖，而紧随其后的 `npm audit --offline` 因本地 advisory 缓存不完整显示 0。维护者随后执行在线 `npm audit`，确认前者可能因异常 size 进入无限循环，后者涉及 source map 路径穿越和文件泄露；两项均存在兼容修复。使用非 major 的 `npm audit fix` 更新 lockfile 后，重新执行 `npm ci`、前端构建和在线审计，结果为 0 vulnerabilities。

这个案例说明安全门禁必须记录审计数据源和联网状态。“命令退出 0”不等于安全数据库完整；离线审计适合网络受限环境的补充检查，不能作为发布时唯一证据。CI 应优先使用在线 advisory，并把审计时间、lockfile commit 和结果作为发布证据保留。

## 41. 有效性威胁

按照实证软件工程论文的习惯，本文从构念、内部、外部和结论四类有效性威胁说明限制。

### 41.1 构念有效性

本文用测试、契约、迁移和构建表示“工程完整性”，但这些指标不能完整测量可用性、洞察质量和真实组织价值。测试数量可能重复覆盖同一逻辑，API 路径数量也不代表每条路径都具有相同成熟度。为降低威胁，本文同时报告负向安全不变量、真实 UI 截图和未验证项，不使用单一分数。

### 41.2 内部有效性

部分测试使用 SQLite 和模拟外部响应，失败可能被环境差异掩盖。全局 Python 环境中的无关包也可能影响 `pip check`。缓解措施包括 CI 使用干净 Runner、lockfile、MockTransport 与外部 canary 分离、迁移单独执行，以及未来加入 PostgreSQL service matrix。

### 41.3 外部有效性

InfoPulse 的结论未必直接推广到医疗、金融或关键基础设施系统。这些领域具有更严格的数据、模型和法规要求。本文模式更适合公开信息研究、企业情报和可审计 AI 工作流；在高风险领域应用前需要独立认证和领域评估。

### 41.4 结论有效性

154 项测试全部通过并不等于不存在未知漏洞。依赖审计数据库可能滞后，CodeQL 也无法识别所有业务授权错误。本文结论限定为“未发现阻断本地开源的已知问题且基线测试通过”，不声称形式化证明整个系统安全。

## 42. 可复现性声明

复现实验需要仓库提交、Python/Node 版本、依赖清单、环境变量和命令。外部账号不是基础实验必需条件。建议记录：

```text
Repository: https://github.com/CoderDongHuang/InfoPulse
Python: 3.10 / CI 3.11
Node.js: 20+ / CI 22
Database: SQLite for baseline; PostgreSQL for production matrix
LLM_API_KEY: empty
Crawler credentials: empty
AUTO_CREATE_TABLES: false
```

为进一步提高复现性，路线图包括 Python lockfile、容器镜像 digest、SBOM、制品 provenance、示例数据初始化和固定外部响应语料。涉及真实第三方服务的 canary 结果应记录时间、地区、账号权限和 API 版本，但不能公开 Cookie 或 token。

## 43. 伦理、隐私与负责任披露

公开可访问不等于可以无限采集、永久保存或重新识别个人。使用者应遵守所在地区法律、平台条款和数据授权范围，执行数据最小化、保留期、删除和访问控制。系统不提供验证码破解、设备指纹伪装或账号权限绕过。

模型输出用于辅助整理，不替代事实核验和高风险人工决策。涉及个人、危机、政策或商业行动时，应回到原始来源并保留异议。漏洞通过 GitHub Private Vulnerability Reporting 私下报告，在修复或缓解方案可用前不公开攻击细节。

## 44. 术语表

| 术语 | 本文含义 |
| --- | --- |
| Evidence / 证据 | 可定位到来源 URL、文本片段、页码、时间段或画框的输入事实 |
| Claim / 断言 | 分析结果中需要证据支持的陈述 |
| Citation / 引用 | Claim 与 Evidence 之间的可验证连接 |
| Collector | 将某个公开数据源映射为统一内容结构的适配器 |
| Degradation / 降级 | 外部能力不可用时返回范围更小但不伪造的结果 |
| TenantContext | 当前用户在组织和 Workspace 中的身份、角色与权限集合 |
| Idempotency / 幂等 | 重复请求不会制造重复业务副作用 |
| Provenance / 来源证明 | 数据、模型产物或构建制品的来源与演进记录 |
| Canary | 用少量真实流量或定时探测验证外部依赖和新版本 |
| Compatibility set | 必须联合升级和验证的一组相互依赖组件 |

## 45. 参考文献与规范

1. NIST, *Artificial Intelligence Risk Management Framework (AI RMF 1.0)*, 2023. [https://www.nist.gov/itl/ai-risk-management-framework](https://www.nist.gov/itl/ai-risk-management-framework)
2. OWASP, *Server Side Request Forgery Prevention Cheat Sheet*. [https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html)
3. OWASP, *Application Security Verification Standard*. [https://owasp.org/www-project-application-security-verification-standard/](https://owasp.org/www-project-application-security-verification-standard/)
4. M. Jones, J. Bradley, N. Sakimura, *JSON Web Token (JWT)*, RFC 7519, 2015. [https://www.rfc-editor.org/rfc/rfc7519](https://www.rfc-editor.org/rfc/rfc7519)
5. SLSA Community, *Supply-chain Levels for Software Artifacts Specification*. [https://slsa.dev/spec/](https://slsa.dev/spec/)
6. OpenTelemetry Authors, *OpenTelemetry Specification*. [https://opentelemetry.io/docs/specs/](https://opentelemetry.io/docs/specs/)
7. GitHub Docs, *About dependency review and Dependabot*. [https://docs.github.com/code-security](https://docs.github.com/code-security)
8. PostgreSQL Global Development Group, *PostgreSQL Documentation: Row Security Policies*. [https://www.postgresql.org/docs/current/ddl-rowsecurity.html](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
9. Alembic Authors, *Alembic Documentation*. [https://alembic.sqlalchemy.org/](https://alembic.sqlalchemy.org/)
10. Martin Kleppmann, *Designing Data-Intensive Applications*, O'Reilly Media, 2017.
11. Patrick Lewis et al., *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*, NeurIPS 2020. [https://arxiv.org/abs/2005.11401](https://arxiv.org/abs/2005.11401)
12. ReAct Authors, *ReAct: Synergizing Reasoning and Acting in Language Models*, ICLR 2023. [https://arxiv.org/abs/2210.03629](https://arxiv.org/abs/2210.03629)

这些资料用于建立风险、协议、供应链、可观测性和 RAG 的通用背景。InfoPulse 的具体实现与验收结论以仓库代码、测试和本文记录的实验为准。

## 46. 结语

InfoPulse 当前已经达到“可以公开代码、供开发者本地运行和继续贡献”的阶段。它还没有达到“拿到任意环境即可无配置生产运行”的阶段，也不应该这样宣传。

开源的价值在于把边界写清楚：哪些链路经过自动化验证，哪些依赖外部账号，哪些问题仍待解决。相比展示更多功能，这种可验证、可追溯、可持续改进的工程基础更重要。

## 47. 二次审计：从功能存在到结果可验证

### 47.1 为什么已有测试不能回答“项目是否完整”

一个模块具有路由、数据库模型、页面和状态字段，只能说明它有实现入口，不能证明完整业务闭环。实际审计需要追问：请求由谁授权，输入来自哪里，数据在哪个事务提交，哪个进程执行，如何判定远端结果，失败后能否恢复，用户看到的状态是否与事实一致。

本轮审计发现四类具有代表性的缺口。第一类是边界不一致：注册根据未验证邮箱授予管理员，共享源写操作缺乏系统级权限限制，个别生成接口允许匿名调用。第二类是确定性故障：重复回执构造参数、SQLite 时间比较、SSE 成功后的残留超时、无匹配条件仍继续执行。第三类是业务假完成：工具只更新状态而不执行投递，行动缺少真正执行器，协作版本没有连接执行图。第四类是验证不足：浏览器只打开外部网页，API 快照只比较路径，SQLite 没有打开外键，已有依赖环境不代表干净安装。

这些问题解释了为何历史 154 项测试通过仍不能推出“所有链路通畅”。不是测试数量无意义，而是测试观察点离真实失败条件太远。改进方向应是提高每项断言的证据强度，而不是只让测试总数增长。

### 47.2 审计采用的证据层级

| 层级 | 例子 | 可以推导 | 不可以推导 |
| --- | --- | --- | --- |
| 静态检查 | schema、路由、类型与调用关系 | 结构一致性、显式缺陷 | 实际执行结果 |
| 隔离服务测试 | mock HTTP、SQLite、故障注入 | 本地状态机与授权规则 | 第三方真实协议全兼容 |
| 跨组件验收 | UI -> API -> PostgreSQL -> worker -> UI | 指定 fixture 的闭环 | 任意内容与所有页面 |
| 真实提供商 canary | 授权 SMTP/模型/webhook 调用 | 特定账号、时点、版本的协议效果 | 永久可用或全面 SLA |
| 运行演练 | 崩溃、恢复、负载、备份回滚 | 设定环境的恢复与容量 | 所有拓扑与故障组合 |

本轮主要完成前三层；后两层保留为后续专项。开源本地使用不需要把服务部署到公网，也不需要公开密钥，但仍需要限制本地程序访问内网和执行外部副作用。

## 48. 身份与出站边界：把默认拒绝写入代码

### 48.1 管理员不是用户自报的属性

旧设计将 `ADMIN_EMAILS` 当作注册授权来源，但公开表单中邮箱只是未经验证的字符串。即使配置内容由维护者填写，攻击者仍可以抢先注册该字符串。因此可信配置与可信身份不能混为一谈。

本轮注册固定设置 `is_admin=False`，管理员通过具有本地数据库访问权限的 CLI 对已有账号提升。这里依赖的信任边界是“能管理本地实例的操作者”，而不是“知道管理员邮箱的人”。未来若增加邮件验证和受控邀请，应形成独立授权流程，而不能恢复原来的隐式提升。

```python
# backend/app/services/auth_service.py，省略非关键字段
user = User(
    username=data.username,
    email=str(data.email).lower(),
    password_hash=await run_in_threadpool(hash_password, data.password),
    is_admin=False,
)
```

共享公共源的配置影响所有使用者，因此写操作需要系统管理员；租户内 connector 和行动则遵循组织/Workspace 权限。两类资源不能仅因都需要登录，就使用同一个“当前用户”检查替代领域授权。

### 48.2 JWT 签名正确不等于会话仍有效

纯无状态 access token 一旦签发，注销不能阻止它在过期前继续使用。本轮加入 `AuthSession`：access token 包含 `sid`，每次身份解析核验会话归属、到期及撤销；refresh token 增加 `jti`，刷新时原子消费并轮换，避免同一 refresh 多次成功；注销在服务器持久化撤销，再清空客户端会话。

浏览器验收不仅观察登录页出现，还用注销前保存的 token 请求 `/auth/me`，断言返回 401。这比“客户端删掉 token”更接近安全需求。迁移后旧 token 缺少 `sid` 会被拒绝，升级文档必须明确需要重新登录。

数据库限流进一步解决多 worker 内存计数彼此独立的问题。计数以窗口和身份为键，用条件 upsert 原子递增；存储不可用返回 503，而不是故障时无限放行。当前实现仍需代理拓扑与高并发压测，不能把算法测试当作容量证明。

### 48.3 SSRF 防护必须覆盖连接过程

只在请求前校验一次 URL 不够：重定向可以改变目的地，DNS 可以在检查与连接之间变化，环境代理可能重新解释目标。统一 `core/outbound.py` 采用逐跳策略：限制协议和标准端口、拒绝 userinfo/fragment、解析所有地址并拒绝非公网结果，将实际连接主机固定为检查后的 IP，同时保留原始 `Host` 和 TLS SNI。

```python
# 实现节选；完整资源界限和 finally 清理见 core/outbound.py
addresses = await asyncio.to_thread(public_addresses, current)
original = httpx.URL(current)
target = original.copy_with(host=addresses[0])
headers = {**request_headers, "Host": original.netloc.decode("ascii")}
transport = httpx.AsyncClient(
    timeout=timeout, follow_redirects=False, trust_env=False
)
async with transport.stream(
    method, target, headers=headers,
    follow_redirects=False,
    extensions={"sni_hostname": original.host},
) as response:
    # GET 的重定向返回上层循环，再解析并检查新目标
    # 有副作用的 POST 不自动跟随重定向
    ...
```

读取响应使用流式累计字节上限，整个调用受 `asyncio.wait_for` 总预算约束，避免每次 redirect 都重置成完整等待时间。注入 `httpx.MockTransport` 只用于测试，没有公开 API 可让调用者关闭目标校验。

保守限制会牺牲部分兼容性：非标准端口、私网 webhook、带认证的 RSS 以及某些特殊重定向不能直接使用。当前面向本地开源的公开采集/公网 connector，这是刻意收窄的能力。未来确有私有集成需求，应增加独立、可审计的管理员 allowlist，而不是把公网安全检查全局关闭。

## 49. 持久化执行：区分入队、发送和远端确认

### 49.1 为什么不能把 pending 直接改为 succeeded

跨数据库与 HTTP 的操作没有天然原子事务。先写成功再发送可能产生假成功；先发送再提交可能在提交失败后重复发送；超时可能发生在远端已经执行、响应尚未返回之后。因此“收到 HTTP timeout”不能证明“对方没有收到”。

本轮新增 `DispatchJob` outbox，领域操作先在事务内写投递意图，worker 原子 claim 后执行。工作流保持 `waiting_dispatch`，读取真实结果后才决定继续或失败。行动执行器依据实际 execution 创建自动回执，人工动作保持等待人工回执。

```mermaid
stateDiagram-v2
    [*] --> pending: 事务提交投递意图
    pending --> running: 原子 claim
    running --> succeeded: 收到明确成功
    running --> failed: 明确拒绝或执行前校验失败
    running --> unknown: 网络不确定或 worker 中断
    succeeded --> [*]: 产生可信回执并推进业务
    failed --> [*]: 暴露失败
    unknown --> [*]: 停止自动重放，人工对账
```

`unknown` 是业务事实，不是可以隐藏的内部错误。若提供商支持可查询的幂等键，可以基于远端查询设计恢复；若不支持，就不能声称本地 idempotency key 实现了端到端 exactly-once。

### 49.2 原子领取的作用与限制

```python
# backend/app/services/dispatch.py
claimed = await db.execute(
    update(DispatchJob)
    .where(DispatchJob.id == identifier, DispatchJob.status == "pending")
    .values(status="running", claimed_at=at)
)
await db.commit()
if claimed.rowcount != 1:
    return False
```

条件更新保证只有一个竞争者成功领取指定任务。过期 running 变为 unknown，不被重新当作 pending。`execution_fingerprint` 绑定请求输入，已有幂等键遇到不同目标、Workspace、行动或消息必须拒绝，避免重用 key 复用错误结果。

这套策略优先避免重复高风险副作用，代价是中断时需要人工对账，也可能将尚未发送的任务保守归入 unknown。后续可以细化 preparing/sending/acknowledged 状态及远端幂等协议，但不能通过无限重试“提升成功率”。

### 49.3 审批必须绑定执行目标

审批 connector 安装后，执行请求不能临时传入另一个 webhook。执行时重新确认安装状态、撤销标记、组织与 Workspace、提供商、目标和消息边界。入队授权不等于永远有效授权，worker 必须在实际执行时复查。

支持范围同样需要说明：本轮是人工与 connector 两种行动执行，编排通知和记忆工具具有真实效果；不支持的停止条件或工具必须显式拒绝。形式化标记、治理分数和声明记录不会因此自动变成真实安全证明。

## 50. 异步知识链路：先持久化输入，再确认任务

### 50.1 staging 顺序决定可恢复性

旧流程如果先提交 queued 文档再保存输入，磁盘或对象存储失败会留下永远无法处理的任务。正确顺序是有界读取与校验、写 staging、提交文档，再由 worker 处理。

```text
文件输入
  -> 受限读取与结构校验
  -> staging 持久化
  -> queued 文档事务提交
  -> claim / lease / processing_attempts
  -> 解析、版本、chunks
  -> ready + active_version
  -> UI 自动刷新 + 证据检索
```

反方向的失败仍存在：staging 成功但 DB commit 失败可能留下孤儿文件。它比“承诺任务却丢失输入”更安全，但需要未来的有界孤儿清理与审计，不应写成跨存储原子事务已实现。

### 50.2 lease 与 attempt 不等于无限重试

claim 持久化 processing_attempts 和 lease_until；过期 processing 可恢复，达到上限进入明确失败。主动 reindex 重置耗尽计数，但正在处理或已排队的任务返回 409，避免重复创建工作。阻塞的文件读写、PDF/DOCX 解析放入线程，防止长解析堵住 async API 事件循环。

线程隔离不是进程级沙箱，无法强制终止所有解析器或限制极端内存行为。因此恶意复杂文件、OCR/视频资源预算与对象存储恢复仍应独立压测。当前文本 embedding 是确定性 hash 特征，不是已经验收的高质量语义模型；检索有结果不等于语义召回率优秀。

## 51. 浏览器如何找到单测之外的缺陷

### 51.1 FormData 与全局 JSON 请求头

浏览器点击知识上传时返回 422，但直接服务测试成功。根因是请求层全局声明 JSON，Axios 在发送 FormData 时改变序列化，后端要求 multipart。这是典型跨层契约错误：服务函数、API 路径与前端组件分别正确，组合后却不正确。

```typescript
// frontend/src/api/request.ts：由 Axios 根据实际数据选择格式
const request = axios.create({
  baseURL: '/api/v1',
  timeout: 120_000,
  // 不在这里设置全局 Content-Type: application/json
})

// JSON 请求自动处理；上传的 boundary 由浏览器/Axios 生成
const form = new FormData()
form.append('files', file)
await request.post(`/knowledge-bases/${baseId}/documents`, form)
```

验收不是“上传返回 200”就结束，而是等文档 ready，再检索固定文本，断言结果带 `acceptance.md`。这连接了前端编码、API、存储、worker、索引与展示六个观察点。

![实际桌面知识检索，隔离数据](../audits/images/2026-10-09/knowledge-desktop.png)

### 51.2 SQLite 的便利可能隐藏 PostgreSQL 的约束

编排工具目录引用 connector 定义，首次打开时平台目录未创建。默认 SQLite 测试没打开外键而通过，PostgreSQL 立即拒绝。修复将平台目录初始化放在工具目录之前，并为测试显式启用外键。

随后路由巡检暴露并发目录创建的唯一键错误。逻辑上“如果不存在则插入”由两个 SQL 操作组成，两个请求都能先读到不存在。解决方案是将并发决定交给数据库唯一约束和原子 upsert。

```python
# 示意代码，对应 platform.seed_catalog 的数据库方言选择
if db.bind.dialect.name == "sqlite":
    from sqlalchemy.dialects.sqlite import insert
else:
    from sqlalchemy.dialects.postgresql import insert

await db.execute(
    insert(ConnectorDefinition)
    .values(catalog_rows)
    .on_conflict_do_nothing(index_elements=["key"])
)
```

使用 DO NOTHING 而不是覆盖更新很重要：已有目录中的禁用项可能是用户主动配置，初始化不能把它重新启用。回归同时检查空库依赖顺序、12 个并发访问、目录数量和用户配置保留，不只检查“没有异常”。

### 51.3 截图是证据，但不是唯一断言

本轮在 1440px 桌面和 390px 移动视口保存实际 UI。截图帮助发现按钮折行、横向溢出和处理中状态不刷新；自动断言则核验 document ready、引用文件名、scrollWidth、会话失效与 JS/5xx。

![实际移动端知识页面，隔离数据](../audits/images/2026-10-09/knowledge-mobile.png)

移动截图发生在路由巡检后，检索框为空属于新页面状态，并不表示桌面检索证据失效。报告要说明截图上下文，不能用视觉素材代替状态因果关系。

## 52. 可复现实验协议与发布门禁

### 52.1 隔离是实验的前提

验收入口 `scripts.acceptance_server` 不读取个人 `.env`，清除 Settings 对应环境值，明确使用本机隔离数据库、Redis、测试密钥和知识路径，关闭 crawler/media/scheduler。`product_smoke` 拒绝非 localhost 地址，但数据库隔离仍是操作者责任，脚本不可指向真实业务库。

测试创建唯一账号和固定 Markdown fixture，不访问真实私有网页、不调用付费模型、不向真实 webhook 发送消息。所有测试凭据只能用于此隔离实例。截图与 JSON 分文件保存，日志和上传数据不提交 Git。

### 52.2 指标与观察点

| 实验 | 结果 | 主要观察点 |
| --- | --- | --- |
| Windows Python 3.10 后端测试 | 187/187，751.843 秒 | 授权、负向、故障、并发、状态与数据 |
| Linux Python 3.11 第二批完整后端 | 188/188，158.138 秒 | 新增媒体有界读取回归；不覆盖先前本机测试时点 |
| SSE 辅助逻辑 | 5/5 | 成功/失败/超时只有一个终态 |
| 完整 OpenAPI 快照 | 354 条路径 | schema、认证、参数、请求与响应 |
| SQLite 迁移往返 | 通过 | 空库 base/head 往返 |
| PostgreSQL/pgvector 空库启动 | 通过 | 实际约束与跨组件写入 |
| 浏览器验收 | 7 组通过 | UI 上传、索引、引用、WS、协作、会话、移动 |
| 路由巡检 | 36 个页面壳 | 非空页面、JS 错误和 API 5xx |
| 前端/SDK | 构建通过 | 编译与类型，不等于业务完备 |
| Linux Python 3.10/3.11 产品验收 | 各 7 组通过 | 最小安装、迁移往返、PostgreSQL/Redis、Chromium/Vite |
| 最小容器栈产品验收 | 7 组通过 | 真实镜像构建、Nginx、超过 1 MiB 上传与 WS |
| Python 全依赖审计 | 92 个依赖，0 条已知漏洞 | CI setuptools 84.0.0，JSON 与 CycloneDX 制品 |

没有测量行覆盖率、吞吐量或语义质量，本文不填写虚构数值。187 相比 154 的增加包含本轮新回归，不是覆盖率提高百分比。耗时受设备、bcrypt 与测试 fixture 影响，也不是 API 性能指标。

新增 CI 在 Linux Python 3.10/3.11 使用 PostgreSQL/Redis、Playwright Chromium 和 Vite 同源代理，运行迁移往返与真实产品验收，上传结果和日志。Python 漏洞审计生成 JSON 与 CycloneDX 制品。[Release Gate 37902377401](https://github.com/CoderDongHuang/InfoPulse/actions/runs/37902377401) 已实际通过全部 job，代码提交为 `303aeb9`。定义 job 只是建立可执行实验，绿色结果才构成该环境的证据；文档收尾提交仍再次执行门禁。

### 52.3 为什么完整 schema gate 仍不是兼容性证明

历史快照只捕捉 operationId、路径和状态码，无法发现字段类型、认证方式或 required 参数变化。本轮扩大到完整参数、请求体、响应引用和 components/schema，使不一致在 CI 明确失败。

严格快照会阻止未经审视的变化，但批准更新快照仍可能包含破坏性修改。v0.x 可以进行记录清楚的安全修正；稳定 v1 必须再引入语义兼容检查、SDK contract tests 和迁移政策，不能把“更新快照后通过”当作兼容性的数学证明。

## 53. 供应链：漏洞结果具有时效性

第一批修复在本机完成后，GitHub npm audit 又发现 Vue、Axios 与 source-map-js 的 4 条 high 项（Vue 与 renderer 形成两个受影响节点）。已有构建绿色不能抵消漏洞审计红色；旧时点“零已知漏洞”也不能永久保留为项目事实。

处理流程是读取官方 advisory 的版本范围，更新修复版本和锁文件，在不使用 `--force` 的前提下重新安装，重新运行前端测试、构建和产品验收，再由 CI 审计复核。Vue 与相关编译/renderer 包需要保持版本协调，Axios 升级必须复查 JSON 与 multipart 两种载荷，不能只确认包安装成功。

```text
锁文件中的版本
  -> 当前官方漏洞数据库
  -> 受影响范围与实际使用面
  -> 修复版本集合
  -> clean install / tests / build / UI
  -> CI audit + 记录依赖与时点
```

SBOM 是库存和关联分析基础，不是“没有漏洞”证书；pip check 验证依赖声明兼容，不检查漏洞；npm/pip audit 检查已知公告，不证明没有未知逻辑缺陷。这三种信号应同时保留，不能互相替代。

第二批持续审计还揭示了一个容易遗漏的层次：应用 requirements 没有声明 setuptools，但 runner 自带 79.0.1 仍进入实际环境库存。审计报告指出旧版在构建源分发时可能因 NFC/NFD 文件名不一致而漏掉 MANIFEST.in 排除规则，83.0.0 已修复。不能因应用不直接 import 它就删除审计对象；构建工具同样可能影响最终公开的包。CI 和两类后端镜像现在显式升级 `setuptools>=83.0.0`，复验使用 84.0.0。漏洞 JSON 和 SBOM 分步生成，前一步检出问题时仍保留后一步诊断，不使用 ignore-vuln 绕过。

## 54. 有效性威胁、局限与结构收敛

### 54.1 内部有效性

mock HTTP 能证明构造、状态和调用次数，但可能与真实提供商响应格式不同。SQLite 并发测试能暴露竞争，但无法替代 PostgreSQL 隔离级别、锁等待及实际 worker 中断。浏览器验收需要观察 API 错误、业务状态和持久化内容，截图单独无法证明因果。

### 54.2 外部有效性

本机网络阻止部分 Docker Hub 基础镜像获取，因此随后把容器实验迁移到 GitHub Linux runner。最小后端镜像、前端 Nginx、PostgreSQL/Redis 的真实构建和 7 组产品检查已通过，不能再把“本机受限”写成“所有环境未验证”；也不能反向把最小镜像结果扩大为完整 Chromium 采集镜像结果。没有第三方凭据仍无法证明 SMTP、SSO、S3、模型和 connector 在真实账号权限下有效；保持空配置是正确边界，而不是用假的演示结果填补实验缺口。

容器首次失败还说明健康探针本身需要验证：镜像构建成功、API 已启动，前端仍被判 unhealthy。探针使用 `localhost`，而 Nginx 的自定义配置仅 `listen 80`，IPv6 解析会使探针访问不匹配的监听地址。把探针固定到 `127.0.0.1` 后，既保留真实检查也消除了地址歧义。不是删掉 HEALTHCHECK、延长等待或直接忽略失败，再把容器启动状态包装为健康。

### 54.3 构念有效性

“有引用”不是“事实正确”，“规则得分高”不是“模型质量高”，“状态 completed”不是“现实行动已发生”，“formal_result”字段存在不是“形式化证明已验证”。后续指标应由真实用户任务定义：引用定位率、无证据拒答率、远端副作用可核验率、跨租户误读率、恢复时间、包体预算与安装成功率。

### 54.4 重复代码如何收敛

项目有 crawler/collector、领域通知/平台 webhook/connector 和多个复杂治理页面。重复名称不必然意味着可以合并业务模型，统一技术基础设施也不意味着统一授权语义。

适合共享的是 URL 安全、时间归一、发送预算、任务领取、低层存储和可观测性。应保持独立的是公共内容与临时讨论样本、平台事件与业务行动回执、租户角色与系统管理员。重构前建立同一 fixture 的结果与副作用基线，重构后验证授权、状态和数据一致；只有减少实际复杂度才引入新抽象。

前端仍有高风险 `any` 和约 1 MB 主包。后续按领域拆分大型视图，生成 DTO/OpenAPI 类型，按需加载依赖，并设定包体与加载预算。调高 chunk 告警阈值不等于性能改善，删除复杂测试也不等于 CI 优化。

## 55. 下一阶段：以验收条件而非模块数量推进

最小容器、Linux 双 Python 版本与每 PR 依赖审计已经落实。第一优先级剩余发布可靠性：完整 Chromium 镜像、独立 worker 崩溃恢复、带数据迁移、所有核心按钮负向矩阵和固定跨域 fixture。第二优先级是结构收敛：来源契约、投递技术基础设施、严格类型、大型页面与 SDK 协议测试。第三优先级是真实质量：提供商 canary、固定模型评测、trace_id、成本/失败指标、删除一致性与备份恢复。

第二批验收又将入口检查扩展到大文件：Nginx 默认 1 MiB 请求限制与知识/媒体后端能力不匹配，改为 256 MiB 整体上限，并为媒体读取增加单文件上限加一的有界调用。浏览器 fixture 使用超过 1 MiB 的固定文本检测代理 413，新增媒体超限回归。第一批完整测试 187 项仍保留其原始时点，第二批远端实际通过 188 项，结果另记在修复报告。避免把后续代码变化悄悄套用到先前测试结果，是可复现实验记录的基本要求。

每个事项应记录负责人、前置条件、可运行实验、结果制品和通过标准。例如“知识库优化”太宽泛，应拆成“worker 在 claim 后终止，lease 过期后另一进程处理，同一文档只产生一个有效 active_version”；“LLM 优化”应拆成“固定证据集下引用与拒答指标，记录模型版本和费用”；“协作完成”应拆成“两用户冲突处理、重连和发布版本不被草稿覆盖”。

本轮完成的是明确缺陷与可重复的核心验收，不是无限范围的产品完成证明。公开开发者预览的前提是代码可运行、风险有边界、状态不造假、文档与证据一致。稳定版则需要更多外部协议、恢复、兼容性和长期维护证据，不能靠博客篇幅或功能阶段编号获得。

## 56. 第二轮研究设计：从“运行成功”到“失败也有正确语义”

2026-10-13 的工作不是重复执行一次已有测试，而是扩展原门禁没有观察到的边界。第一轮证明了若干核心路径可以完成，但留下四类问题：安装是否跨平台、成功响应是否已持久化、工作进程中断是否会丢失任务、部分模型结果是否会被错误发布。它们共同指向一个工程问题：系统对用户宣告的状态，是否与其他观察者实际能看到的状态一致？

### 56.1 可检验的研究问题

| 编号 | 问题 | 失败判据 | 不能据此推断 |
| --- | --- | --- | --- |
| RQ5 | 成功 HTTP 响应是否对应已提交数据库状态？ | handler 已返回但独立 reader 看不到资源/会话；提交异常仍返回成功 | 所有接口、所有隔离级别都正确 |
| RQ6 | worker 被操作系统中断后是否能恢复？ | staging 消失、有效 lease 被抢、重复版本、过期任务永不处理 | 所有 worker 或外部副作用恰好一次 |
| RQ7 | UI 的正常取消是否被视为错误或写入？ | pageerror、写请求、选中状态意外变化 | 401、断网、超时等其他负向场景也完成 |
| RQ8 | 多模态后半程失败是否泄漏前半程证据？ | failed/unknown 下仍出现本轮部分 OCR、usage 或已发布帧 | 真实模型质量、计费对账已验证 |
| RQ9 | 优化是否有可重复的量化结果？ | 相同依赖、相同构建统计规则下无改善，或超过预算不失败 | LCP、INP、业务转化率已经改善 |

这些问题都需要“观察者”。同一个 ORM session 能读到自己的未提交对象，不足以证明其他请求可读；同一个 Python 进程抛异常，不等于操作系统 kill；一张成功页面截图，也不能证明取消时没有副作用。实验先指定观察者，再选择工具，避免把方便测量的量当成真正想证明的性质。

### 56.2 实验隔离

本机验收使用专用 PostgreSQL 16、Redis、临时 SQLite 文件、隔离知识目录和 `acceptance_server`。该入口禁用个人 `.env`，清理 Settings 对应的环境变量，再设置测试专用配置。第三方模型密钥保持为空，测试仅调用本机服务和受控 fixture。临时数据库采用唯一名称并校验目标，不能把“测试清理”变成删除已有业务库。

本轮不测量模型事实准确率，也不假装已经连接真实 SMTP、S3、Slack 或 OIDC 服务。模型 adapter 的 mock 用于触发超时、部分响应和数据库异常；Chromium/ffmpeg 的真实进程用于验证运行依赖。两类实验对应不同构念，必须分别报告。

## 57. 响应前提交：一次 404 如何暴露事务边界

### 57.1 现象与原因

浏览器顺序执行创建工作流与打开协作文档时，创建接口返回 201，随后的资源校验却返回 `Workflow not found`。另一次验收中，退出登录已经跳转到认证页，旧 token 请求 `/auth/me` 仍得到 200。前端确实等待了前一个 Promise，因而简单增加 `await` 不能解决问题。

根因在服务端：handler 只执行 `flush`，把 `commit` 留在 FastAPI 数据库依赖的 `yield` 之后。`flush` 会把 SQL 发给数据库并获得主键，但不代表事务已提交。真实 ASGI 网络响应可能先到达客户端，新的数据库连接仍看不到未提交数据，或者仍能看到尚未提交撤销之前的会话。

```mermaid
sequenceDiagram
    participant UI as 浏览器
    participant API as 请求 A
    participant DB as 数据库
    participant B as 请求 B / 独立连接
    UI->>API: 创建资源 / 撤销会话
    API->>DB: flush / UPDATE（未提交）
    API-->>UI: 201 / 204
    UI->>B: 立即读取 / 使用旧 token
    B->>DB: SELECT
    DB-->>B: 旧的已提交状态
    API->>DB: 依赖清理阶段 commit
```

这不是缓存延迟问题，也不是应当重试所有 404 的理由。重试会改变观察窗口，可能让错误看似消失，但无法保证成功响应前提交失败不会发生。正确修复是把事务提交纳入 API 的成功条件。

### 57.2 修复方式与原子性

下面是认证注册修复的结构摘录；生产实现还包含输入约束和错误映射：

```python
async def register(data, db):
    try:
        tokens = await auth_service.register_user(db, data)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    await db.commit()
    return tokens
```

`register_user` 仍负责组合用户、个人组织、工作区、角色和会话，`_generate_tokens` 仍不自行提交。这样不会因为底层 helper 提前 commit 而使“用户已创建但租户失败”成为半成品。令牌先在内存构造；若签名失败，不先提交不可用会话；若提交失败，不把凭据返回客户端。

同一原则分别落实于本轮遇到的 Agent 会话、WS ticket、协作文档、工作流创建、logout，以及后续注册、登录、SSO exchange、refresh。每个领域都保留自己的授权、审计和事务组合。没有贸然全局修改流式依赖的生命周期：SSE、长连接、transaction-local 租户上下文和 RLS 都需要单独判断。

### 57.3 为什么已有 HTTP 单测没有发现

内存 ASGITransport 通常等待完整应用调用返回，包括依赖清理。测试端读到 HTTP 响应时，数据库可能已经提交；实际 TCP 客户端则可能更早读取响应字节。因此，“ASGITransport 测试绿色”和“真实网络存在竞态”并不矛盾，它们观察的是不同时间边界。

新的回归直接执行实际 handler，在 writer session 保持打开、未执行测试端 commit 的情况下，让独立 reader 使用真实权限函数：

```python
async with sessions() as writer:
    tokens = await register(payload, writer)
    async with sessions() as reader:
        user = await get_current_user(
            HTTPAuthorizationCredentials(
                scheme="Bearer", credentials=tokens.access_token
            ),
            reader,
        )
        assert user is not None
```

还必须加入提交失败测试，只替换 `writer.commit` 使其抛错，要求 API 不返回成功；rollback 后，独立 reader 不得看到新增账户、成员或会话。refresh 则要求原 jti 没有被失败事务消费。测试不是只断言 mock 被调用一次，而是检查持久化状态。

认证专项新增 8 项与原认证/撤销/企业权限回归合计 19/19，通过耗时 135.766 秒。本机真实 PostgreSQL、Vite dev、Edge 的 9 组产品检查也通过。这里的时间是整个测试执行时间，不是登录 API 延迟，更不是性能基线。

## 58. 任务恢复：数据库 lease 需要进程级实验

### 58.1 知识文件为何先 staging

知识入库不能只把上传内容留在 API 进程内存，再向后台任务传一个引用。响应返回后进程可能重启；任务记录存在而原始字节已经丢失，会产生永久无法完成的队列项。当前实现先将源文件写入 staging，再持久化任务。最终版本和分块可见之后，才清理 staging。

它仍不是数据库与对象存储之间的分布式事务。上传成功但任务提交失败可能留下孤儿文件；清理失败可能残留 staging。需要通过幂等键、可追踪状态和后续清理处理，不能声称跨系统严格原子。当前恢复实验聚焦 claim 已提交后进程中断这一明确窗口。

### 58.2 实验序列

```mermaid
flowchart TD
    A[创建 staging 与任务] --> B[独立 worker A 领取并提交 lease]
    B --> C[操作系统终止 worker A]
    C --> D[启动已连接数据库的 worker B]
    D --> E{lease 是否过期}
    E -->|否| F[不抢占 不产生版本]
    E -->|测试推进到过期| G[再次领取 attempts = 2]
    G --> H[生成唯一 active_version 和非空分块]
    H --> I[清理 staging]
```

测试确实启动生产 worker 入口的独立进程，等待领取事务落库后注入停顿，再由操作系统 kill。为了避免每次等待生产的 5 分钟 lease，实验把数据库到期时间推进到过去；这是显式加速时间条件，不是跳过 lease 逻辑。第二个 worker 在到期前已连接数据库，从而避免“还没启动所以没重复处理”的假阳性。

另一个实验在两个独立 worker 都完成初始化后才提交新任务，检查 attempts=1、版本数=1。只断言最终 status=ready 不够：两个进程都成功一次也可能留下 ready，但已经重复索引或重复计费。attempts、活动版本、分块、源文件和清理状态共同组成观察面。

### 58.3 有限结论

这一结果只属于 knowledge worker。actions、orchestration 和 media 具有不同的外部副作用，不能复制“lease 过期就重试”规则。发送通知或调用模型后连接断开，远端可能已经接收；再次执行可能重复通知或重复收费。知识恢复的成功不是“所有任务恰好一次”的证据。

## 59. 带数据迁移：退出码之外还要比较什么

空数据库 `upgrade -> downgrade -> upgrade` 能发现 DDL 错误、语法不兼容和部分约束问题，但无法证明业务数据在迁移后保持一致。第二轮向 PostgreSQL 写入 14 张核心表：用户、来源、正文、事件及关联、分析及引用、报告及版本、知识库/文档/版本/分块/处理记录，然后执行 head → revision 29 → head。

逐表记录行数，并对稳定字段进行规范化后计算 SHA-256。行数一致不代表正文和外键没有变化；hash 一致也必须明确哪些字段被纳入，不能排除关键字段再宣称无损。实验同时核对引用、活动版本、非空正文和 96 维向量等业务不变量。

```text
迁移前：表名 + 行数 + 稳定字段摘要 + 业务关系
             ↓ downgrade / upgrade
迁移后：表名 + 行数 + 稳定字段摘要 + 业务关系
             ↓ 精确比较
结论：这 14 张已有核心表在这条 revision 路径上保持所测数据
```

降级到 revision 29 会删除后续版本新增的 dispatch_jobs、auth_sessions、api_rate_limits 等表或字段。所以本实验不是全业务无损回滚保证；更不能把脚本指向运行中的业务库。真正发布回滚要协调 worker 停止、备份、文件、应用版本和模式兼容。数据库可降级不代表业务副作用可逆，远端已经送达的消息不会被 Alembic 撤回。

复现入口是 `scripts.postgres_recovery_smoke`，它限定本机 audit 服务器、生成唯一临时库名并检查删除目标。CI 保存逐表摘要和 worker 日志。后续应扩展其他领域及基于备份的恢复，而不是不断加长一条破坏性 downgrade 链来代替灾备。

## 60. 多模态失败原子性：不发布半份证据

### 60.1 原缺陷的两个层次

源对象读取曾位于异常处理边界外。文件丢失时，进程已经把任务标成 running，却没有机会记录 failed。把读取放进 try 只能修复这一层；后续 OCR 的第二条记录出错、唯一键冲突或视频第二帧处理失败时，第一条证据可能已进入 ORM 待提交集合。如果异常分支直接 commit，就会错误发布部分结果。

SQLAlchemy 的 flush 抛出 IntegrityError 后，session 还处于需要 rollback 的失败状态。直接再次 commit 不能可靠写入失败终态，反而可能抛 PendingRollbackError。因此失败处理必须先恢复事务可用性，再记录状态。

### 60.2 修复结构

```python
provider_started = False
try:
    data = await asyncio.to_thread(storage.get, asset.storage_key)
    # 元数据、OCR/转录证据、usage 在同一发布事务中构造
    # 调用 adapter 前设置 provider_started = True
    await db.commit()
except Exception:
    await db.rollback()
    await db.refresh(asset)
    await db.refresh(run)
    terminal = "unknown" if provider_started else "failed"
    asset.status = run.status = terminal
    run.lease_owner = run.lease_until = None
    await db.commit()
    raise
```

这是结构摘录，不是可以直接替换生产函数的完整实现。生产代码另有错误信息、结束时间、证据定位、模型路由和视频帧清理。核心约束是本轮证据、元数据、usage 要么成功发布，要么整体回滚；失败终态在 rollback 后的新事务中写入。

### 60.3 为什么不是所有失败都叫 failed

调用前发现源文件缺失或路由不可用，可以确定没有启动 provider adapter，修复本地原因后允许显式重试。adapter 启动后超时、响应解析失败或数据库提交失败，不能证明远端没有处理或收费，因此保守记录 unknown，普通 retry 和队列领取都不重放它。

```mermaid
flowchart LR
    A[queued] --> B[读取与本地验证]
    B -->|调用前确定失败| C[failed 可显式重试]
    B --> D[启动 provider adapter]
    D -->|证据和 usage 提交成功| E[succeeded / ready]
    D -->|超时 解析或发布失败| F[unknown 不自动重放]
    F --> G[后续对账与人工处置]
```

这个边界有意偏保守：adapter 内部可能尚未发出网络包就失败，仍归 unknown。好处是不会把“无法确认是否执行”错误当成“确认没有执行”；代价是需要人工核对或未来的 provider request id 查询机制。当前尚未实现完整的自动对账界面和恢复策略，这一不足应公开保留。

### 60.4 SDK 隐式重试也是副作用

仅在 worker 层不重试还不够。SDK 本身可能对连接错误、超时、429 或服务器错误重新发送请求。多模态客户端现在显式设置：

```python
AsyncOpenAI(
    api_key=settings.LLM_API_KEY,
    base_url=settings.LLM_API_BASE,
    max_retries=0,
)
```

独立构造回归验证 `max_retries=0`，防止未来重构时丢失。该设置不证明远端永不重复，也不提供 provider-side 幂等；它只消除当前 SDK 的隐式重放来源。对于允许安全重试的读请求，可以在其他明确边界采用独立策略，不能把这一配置无差别推广成全系统性能建议。

### 60.5 实验和仍未解决的窗口

新增六项数据库回归覆盖源对象丢失后修复、路由拒绝、模型超时、第二条 OCR 非法、真实重复 ordinal 引发 IntegrityError、视频第二帧失败后的帧和临时目录清理。与原四项媒体测试合计 10/10，205.814 秒；SDK 配置回归另一次 1/1，10.268 秒。它们不是同一次“11/11”执行，应保留两条记录。

本修复处理普通 Python 异常，不覆盖操作系统 kill、失联 worker 的 fencing token、跨对象存储原子提交或全部 claim 竞争。视频帧删除是尽力清理，失败有日志；进程被 kill 后清理代码可能不运行。后续应引入可识别的临时帧命名空间、后台回收和明确的 provider 对账，避免把清理成功的一个样本写成永久无残留承诺。

## 61. 前端可靠性：取消、非空状态和包体预算

### 61.1 取消不是异常失败

Element Plus MessageBox 用 Promise rejection 表示 cancel/close。如果 handler 直接 await，开发服务器可能把用户正常取消上报为未处理异常。正确做法不是忽略所有 pageerror，而是只处理协议规定的两个退出值：

```typescript
export async function runDialog<T>(open: () => Promise<T>): Promise<T | undefined> {
  try {
    return await open()
  } catch (action) {
    if (action === 'cancel' || action === 'close') return undefined
    throw action
  }
}
```

页面在返回 undefined 时立即结束，不调用写 API、不刷新、不清空选择。图谱有两步或三步输入，每一步都要测试取消，否则第一步正确并不能保证第二步不会使用缺失值继续写入。实际 handler 由 TypeScript parser 从页面提取，执行时只替换对话框和 API 边界，避免复制一份“理想业务逻辑”自测。

前端完整回归为 25/25；知识库浏览器实际打开新建、网页导入、删除库、删除文档四种弹框并取消，检查网络无写入及 ready 文档仍存在。POST `/search-test` 携带查询体但语义只读，不能机械地把所有 POST 计为写入；同样不能为了通过测试把真正的 POST 写操作排除。

![取消操作后知识库与 ready 文档仍保留](../blog-assets/2026-10-13/knowledge-cancellation.png)

图中是取消后的业务状态，不是正在打开的弹框。截图可以帮助复核结果位置，零写入由网络请求断言提供证据；仅凭截图无法证明没有发生一次写入后又被撤销。

### 61.2 非空 fixture 发现 HTML 结构问题

行动详情原先把 tr 直接放到 table 中。浏览器可能自动插入 tbody，导致 DOM 与 Vue 的预期结构不一致。空列表巡检不会渲染执行步骤，因此 36 个路由都能打开仍可能遗漏这一缺陷。修复明确区分 thead/tbody，新增一条非空步骤展示。

![行动详情非空步骤表：只读展示 fixture](../blog-assets/2026-10-13/action-step-table.png)

这里的行动标题明确标注 fixture，三列表头与 `1 / manual / succeeded` 是展示测试数据，不能视为真实行动执行或送达证明。脚本只拦截两条 GET，写方法被拒绝，finally 撤除拦截；同时把 `cannot be child of` 控制台警告纳入失败条件。新增后本机产品验收为 10/10，page/server/component 三类错误数组为空。

### 61.3 按需组件不是简单调大告警阈值

原入口全局安装 Element Plus 并导入全量 CSS。项目路由已经动态 import，主要收益来自按需注册实际 19 种组件，保留 loading 指令和 Message/MessageBox 的程序化样式。只导入表面组件样式而遗漏内部依赖，会产生下拉、遮罩或弹框残缺，所以还要用真实交互验收。

![真实 loading、筛选和确认框交互后的报告页面](../blog-assets/2026-10-13/components-desktop.png)

包体统计读取 Vite manifest，从所有静态入口递归遍历 imports，CSS 和共享 chunk 去重，分别累计每个资源原始、gzip、Brotli 大小。若只量名为 index 的文件，拆出 vendor 就会“优化成功”但首屏仍下载同样代码；依赖图预算可以避免这种统计错觉。

| 指标（同环境初版对比） | 全量注册 | 按需注册 | 相对变化 |
| --- | ---: | ---: | ---: |
| JS raw / 字节 | 1,099,167 | 503,002 | -54.2% |
| JS gzip / 字节 | 355,166 | 173,251 | -51.2% |
| CSS raw / 字节 | 368,917 | 136,414 | -63.0% |
| CSS gzip / 字节 | 50,745 | 19,963 | -60.7% |

门禁固定 JS raw 600,000、JS gzip 200,000、CSS raw 160,000 字节。后续小改动会使压缩字节数略变，报告保留每个时点而不覆盖历史实验。动态路由、图片、冷缓存网络、LCP 与 INP 尚未纳入；减少传输字节是已测结果，“快了多少毫秒”不是。

## 62. 平台与容器：测试环境也是实验对象

Windows Python 3.10/3.11 持续 CI 从完整 requirements 入口安装依赖，执行 pip check、编译、完整 unittest、API 快照与 SQLite head → revision 13 → head。每条 native 命令拆为单独 step，避免 PowerShell 后一条成功命令覆盖前一条失败退出码。

首次 Windows CI 的知识测试有九项 `invalid storage key`。生产存储构造函数会 resolve 根目录，夹具替换根路径时却保留了 Windows 短路径别名；再把 resolved 子路径与未 resolved 父目录比较，自然不相等。修复夹具规范化而不是放松生产路径遍历防御，并补真实嵌套读写、删除及绝对路径/遍历/根目录拒绝回归。最终两版本基线均通过 198 项，后续专项继续增加。

完整容器实验则真正启动 BrowserManager 和 Chromium，渲染本地 HTML、执行 JavaScript、检查 stealth 兼容层与任务锁释放；媒体用合成视频运行 ffprobe/ffmpeg，检查帧数量上限、图片尺寸、WAV 音轨和临时目录清理。它证明镜像具备所测依赖，不证明微博登录、站点反自动化策略或模型准确率。

本机曾在 Docker Hub 元数据拉取阶段超时，后来 CI 完整镜像通过。文档必须同时保留“本机未能执行”和“CI 实际通过”：前者不能被改写成通过，后者也不能继续被旧 README 写成完全未验收。环境差异不是掩盖结果的借口，而是结果不可缺少的一部分。

## 63. 实际展示、证据索引与复现协议

![超过 1 MiB 文档入库与有来源检索](../blog-assets/2026-10-13/knowledge-desktop.png)

这张桌面图来自隔离验收服务，1026 KB 文档通过上传、自动索引及引用检索。检索结果能定位文件与段落，但图中的 72% 是系统检索分数，不是事实正确率或模型置信度。fixture 的文本是固定测试材料，不是用户私人资料。

![移动视口下知识库单列布局](../blog-assets/2026-10-13/knowledge-mobile.png)

移动图证明当前视口的单列布局、上传工具栏和检索输入可见。它不证明所有手机、缩放、屏幕阅读器、键盘操作或完整 WCAG 要求已满足。后续无障碍测试仍需焦点顺序、对比度、语义标签和真实辅助技术参与。

图片统一存于 `docs/blog-assets/2026-10-13/`，来源及用途记录在该目录 README。所有新图来自实际浏览器，不是生成式效果图。GitHub Markdown 使用相对链接，可随克隆离线查看；CI 的结果 JSON、日志、bundle report 和依赖清单是更完整的机器证据。

### 63.1 本地复现顺序

先按仓库 README 安装依赖，再启动专用 audit PostgreSQL/Redis。不要复用个人服务或修改已有 `.env`；启动 API 的脚本会主动隔离配置。

```powershell
# 仓库根目录，仅启动隔离数据库和缓存
docker compose -p infopulse-audit -f docker-compose.audit.yml up -d postgres redis

# backend，窗口一：专用审计库，不是业务库
python -m scripts.acceptance_server --database-url postgresql+asyncpg://audit:audit-local-only@127.0.0.1:15432/infopulse_audit

# frontend，窗口二
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:18080'
npm run dev -- --host 127.0.0.1 --port 15173 --strictPort

# backend，窗口三：本机已安装 Edge；Linux CI 使用 Chromium
python -m scripts.product_smoke --base-url http://127.0.0.1:15173 --browser-channel msedge --output ../acceptance-artifacts/local-product
python -m scripts.postgres_recovery_smoke --output ../acceptance-artifacts/local-recovery

# frontend
npm test
npm run build

# 结束自己启动的 API/Vite 后，在仓库根目录停止隔离栈；不删除数据卷
docker compose -p infopulse-audit -f docker-compose.audit.yml down
```

浏览器测试会创建测试账号和文档，所以必须使用专用环境。重复执行产生不同唯一账号，不要求清空已有数据库。运行成功查看 `completed`、checks 和所有 error 数组，不能只看 shell 最后一行；失败保留现场日志，不自动 rerun 后只保存最后一次绿色。

### 63.2 分层证据矩阵

| 层级 | 实际证据 | 主要意义 | 主要盲区 |
| --- | --- | --- | --- |
| 函数/handler | 前端 25/25；认证专项 19/19；媒体 10/10 与独立 SDK 1/1 | 指定输入、边界、失败副作用 | 浏览器时序、外部服务 |
| 独立连接 | 会话/工作流/撤销持久性 | 不依赖 writer 清理仍可见 | 所有 API 与全部隔离级别 |
| 独立进程 | knowledge claim/kill/recovery/双 worker | 恢复与重复处理约束 | 其他 worker、收费副作用 |
| 真实产品 | 本机 9 组，表格专项后 10 组；36 路由壳 | UI、代理、API、DB、worker 协同 | 所有按钮、真实提供商 |
| 容器 | minimal/full Nginx 产品与完整运行 fixture | 镜像运行依赖与入口 | 公网、真实平台反爬 |
| 跨平台 CI | Linux 与 Windows 双 Python；依赖与契约 | 持续安装、回归、漂移发现 | 未来版本和稳定兼容承诺 |

数字只属于具体执行时点。表格专项的 10 组不自动覆盖媒体新代码，认证专项的 19 项也不代表全部后端测试总数。合并依据是最新提交的全部 CI，不是从不同 commit 各取一个绿色 job 拼出一个看似完整的结果。

## 64. 后续优化的验收合同

后续路线不按“再加十个模块”安排，而按风险和可验证合同推进。每个合同包括前提、动作、可观察结果与禁止扩大解释的边界。

### 64.1 P0：仍需优先收敛的可靠性

1. **其余写 API 的事务审计。** 列出 profile、删除、编排修改等写路径，在返回成功前用独立连接检查状态。外部文件删除与数据库删除分开建模，不能通过简单添加 commit 就声称跨系统原子。
2. **actions/orchestration/media 进程恢复。** 在领取、远端发送、响应收到、回执提交前后分别 kill，检查不会永久 running 或重复收费。引入 fencing 前先明确谁有资格更新状态，旧 worker 恢复后不能覆盖新 owner。
3. **核心按钮负向矩阵。** 对每个业务动作列确认/取消、401/403、断网、超时、重复点击及冲突；两用户同文档与跨租户访问要实际经过 UI 和 API。路由壳检查作为基础门禁继续保留。
4. **固定跨域 fixture。** 用本地可控来源贯穿采集、内容、事件、分析、报告、通知、回执，断言同一证据标识在链路上不丢失。没有真实模型时使用明确 fixture，不把固定输出宣称语义推理正确。
5. **版本约束与镜像固定。** 针对 Linux/Windows、Python 3.10/3.11 生成可复现约束并持续验证；镜像 digest 定期更新。pip freeze 是运行库存，不天然等于经维护的跨平台锁文件。

### 64.2 P1：减少重复代码，但保留业务差异

collector 与 crawler 可共享安全 HTTP、预算和清洗工具，但持久化资讯与临时讨论样本的留存、授权和结果契约不同。通知、平台 webhook 和 connector 可共享投递技术，不应合并为同一种业务权限。抽象是否值得引入，要看减少了多少实际分支与重复失败处理，而不是类名是否更统一。

大型 Vue 页面应先提取请求状态和明确 DTO，优先消除权限、工作流、知识 API 的高风险 any。类型生成需要 API schema 与后端响应都正确，不能生成类型后强制断言来消除红线。组件拆分后用同一 fixture 比较 DOM、网络副作用、取消和错误行为，防止“代码更整齐但交互退化”。

测试分层可降低 CI 等待，但需要实测哪一部分是 schema 初始化、密码哈希、依赖安装或测试本身。并行测试必须隔离数据库、端口和 storage；不能删除慢测后报告“性能优化”。SDK 后续补真实 HTTP、分页、版本兼容和发布流水线，构建通过只是入口。

### 64.3 P2/P3：质量、恢复与治理

真实源 canary 应把代码故障、源停机、限流和账号权限区分开。模型评测先固定证据集、问题、拒答标签和人工标注规范，再记录模型版本、温度、费用与输出；不能用系统自己的静态评分评价自己。通知和 SSO 等提供商测试由获授权账号及 secret 注入触发，未提供密钥的使用者仍可运行本地核心链路。

trace_id 应贯穿请求、任务、模型和投递，但指标标签不得直接放入用户邮箱、任意 URL 或高基数 request id。备份恢复需要同时考虑数据库、原文件、向量、对象、配置与版本；定义 RPO/RTO 后才能说是否达到目标。v1 之前建立支持周期、弃用策略、威胁模型与维护者职责，让后来的贡献者知道哪些行为不能随意改变。

## 65. 局限、反例与结论

本轮最重要的反例，是“测试很多但响应仍可能先于提交”。它说明覆盖数量不是可靠性的充分条件，关键在于是否覆盖正确的观察边界。另一个反例是“任务失败但远端可能已收费”，说明二元 success/failed 不能承载全部事实；unknown 是对知识边界的诚实表达，而不是一个可以无限搁置的终点。

本文仍有明确局限：缺少真实提供商矩阵，缺少完整性能与无障碍基线，只有部分 worker 的进程恢复实验，数据库迁移只验证限定核心表。截图是受控环境，fixture 不是现实行动，检索分数不是模型事实准确率，源码中出现治理术语也不等于拥有对应的分布式或形式化保证。

因此当前合理发布形式仍是本地 `v0.x` 开发者预览。开源的价值在于让安装、实现、失败和限制都可检查，而不是在 README 上把实验模块称为完整产品。之后每一个“完成”标记，都应能沿着文档找到代码、实验、结果和独立 PR；如果无法找到，应当把它重新标为未验证。

## 66. 实验时钟：为什么真实的 200 也可能是测试错误

文档提交的 Windows Python 3.10 CI 完整执行 217 项，却在固定窗口限流回归中失败。原测试发出 11 次登录请求，预期前 10 次成功、第 11 次 429；日志显示第一条请求在 10:18:59.956，第二条在 10:19:00.039。实现以 `at // 60 * 60` 计算窗口，第一条与后十条属于不同分钟，因此全部 200 符合算法。错误在于实验暗含了“所有请求处于同一分钟”的前提，却没有控制这一前提。

修复不修改生产阈值，不把 200 放进允许结果，不用重试等到一次绿色。只替换限流模块引用的时钟对象，保留实际 middleware 和数据库条件 upsert：

```python
clock = SimpleNamespace(time=Mock(return_value=239))
with patch.object(rate_limit, "time", clock):
    # 同一分钟内 11 次真实 ASGI 请求：10 次 200，然后 429。
    responses = [await client.post("/api/v1/auth/login") for _ in range(11)]
    assert [r.status_code for r in responses] == [200] * 10 + [429]
    assert responses[-1].headers["retry-after"] == "1"
    clock.time.return_value = 240
    # 新窗口应恢复额度；再次耗尽后 Retry-After 为 60。
```

这里替换模块的 `time` 绑定，避免 patch 共享的 `time.time` 影响日志或其他库。并发计数仍使用真实文件 SQLite 的 20 个 session，只允许 5 次成功；HTTP 边界也在两个窗口各发 11 次并检查 Retry-After。专项 **6/6** 通过，独立修复 [PR #71](https://github.com/CoderDongHuang/InfoPulse/pull/71) 的最新完整 CI 通过后已正常合并，详细失败及合并证据见 [R10 报告](../audits/2026-10-13-rate-limit-clock.md)。

固定分钟并不等于任意滚动 60 秒：窗口边缘可连续使用两个分钟的额度。这是算法本身的限制，应公开说明；未来改成令牌桶或滑动窗口时，需要新的业务合同和相同边界的回归。确定性测试的目的，是让时间作为受控实验输入，而不是让测试脱离真实数据库或删除失败路径。

## 67. 实验预算：完整测试与 CI 时限之间的关系

实验可重复除了需要固定输入，还需要足够的资源预算。在最终文档提交 `847de1d` 上，Linux、产品、容器、前端、SDK 与 CodeQL 全部通过，两个 Windows job 却在 30 分钟被取消。取消前的日志给出了区分性能预算不足和业务失败的依据：Python 3.10 已输出 `Ran 217 tests in 1702.129s`；Python 3.11 在 11:36:30 仍输出正常通过项，随后在夹具初始化中收到 runner 终止。

### 67.1 预算应覆盖哪个边界

`timeout-minutes` 限制整个 job，而非仅 unittest。对于当前 Windows 门禁，实际总时长是：

```text
T_job = T_checkout + T_python_setup + T_install + T_pip_check
      + T_compile + T_full_suite + T_contract + T_migrations
      + T_dependency_inventory + T_artifact + T_cleanup
```

单测试阶段 1702.129 秒约为 28.4 分钟，距离原 30 分钟只剩约 1.6 分钟；前后的安装与验收会消耗这一余量。另一个成功运行更快并不能证明预算充足，hosted runner 的 I/O、缓存命中与资源竞争也会影响时长。

| 观察 | 能得出的结论 | 不能得出的结论 |
| --- | --- | --- |
| 最后仍持续输出 `ok` | 测试有进度，不是从开始就卡住 | 整个 suite 以及后续步骤均通过 |
| 已输出 `Ran 217 tests` | 测试阶段已跑完完整集合 | 契约、迁移、制品已完成 |
| runner 报 canceled | 当前 head 的门禁未完成 | 业务断言必然失败或可忽略 |
| 旧 head 更快且成功 | 环境耗时存在浮动 | 可以代替当前 head 合并证据 |

### 67.2 最小修正与验收

独立 [PR #72](https://github.com/CoderDongHuang/InfoPulse/pull/72) 将 Windows job 调整为有限的 45 分钟，为实际约 30 分钟的总时长保留约 50% 余量。Linux 和其他 job 预算不变；两个 Python 版本、完整依赖、全部测试、契约和迁移继续保留：

```yaml
windows-backend:
  runs-on: windows-latest
  timeout-minutes: 45
  strategy:
    fail-fast: false
    matrix:
      python: ["3.10", "3.11"]
```

本机使用 YAML parser 比较修改前后的完整对象，只允许这一字段从 30 变为 45，防止同时误改命令、权限或矩阵。结构比较只能证明修改范围，无法证明实际运行；仍须最新提交的两个 Windows job 真正跑完，所有其他门禁同样通过，才允许正常合并。具体日志与结果见 [R11 报告](../audits/2026-10-13-windows-budget.md) 的独立 PR。

### 67.3 后续性能工作

增加预算不等于提升性能，也不完成测试分层。后续应逐项测量 schema 初始化、数据库事务、密码哈希、安装缓存与业务用例，把 unit / integration / e2e 按责任拆分；独立 fixture、端口与 storage 是并行化的前提。分片需要核对全部测试恰好被执行一次，以及跨数据库、进程和平台用例没有被漏掉。若只删除慢测或接受 canceled，就改变了验收合同，不能报告为性能优化。

## 68. 资料更新：将持久性合同推广到普通写接口

认证专项的结论不能自动推广到每个写 API。继续审计发现 `PUT /api/v1/auth/me` 仍直接返回服务结果；服务只执行 flush / refresh，因此响应模型里虽然已有新 username、email 和 avatar，另一请求却可能读到旧资料。它和令牌竞态属于同一事务边界问题，但资料更新没有签发新会话，测试合同必须按其业务行为另行定义。

### 68.1 API 与服务的责任

采用与认证签发一致的责任边界：服务构造更新并校验响应，API 对成功提交负责。实际 handler 的关键代码为：

```python
try:
    profile = await auth_service.update_user(db, current_user.id, data)
except ValueError as e:
    raise HTTPException(status_code=404, detail=str(e))
await db.commit()
return profile
```

先构造响应对象，再提交，避免响应验证错误发生在不必要的成功写入之后。提交失败直接传播，不返回成功 profile。没有给 service 添加 commit，调用者仍可以在一个上层事务中组合多个操作，也没有全局改变数据库依赖与流式 API 生命周期。

### 68.2 有区分能力的测试

新增四项回归使用文件 SQLite 与实际 endpoint、service、ORM、JWT、认证依赖。关键观察发生在 writer 保持打开时：

```python
async with sessions() as writer:
    user = await writer.get(User, user_id)
    profile = await update_me(
        UserUpdateRequest(
            username="new-name",
            email="new@example.com",
            avatar_url="/avatar.png",
        ),
        user,
        writer,
    )
    # 没有测试端 commit，也没有响应后的依赖清理。
    async with sessions() as reader:
        persisted = await get_current_user(credentials, reader)
        assert persisted.username == profile.username
        assert persisted.email == profile.email
        assert persisted.avatar_url == profile.avatar_url
```

同时检查原 access token 仍可认证、refresh jti 没有被修改、管理员和启用状态保持，确保修改资料不会偷偷改变会话合同。第二项只注入 commit 异常，要求 endpoint 不返回结果，rollback 后独立连接仍看到原资料。第三项验证不存在的用户仍返回 404 且不尝试提交。第四项直接调用 service，要求没有自行提交，独立 reader 仍看到旧资料，证明没有破坏组合事务。

本机 Windows Python 3.10 新增四项与原认证、撤销、签发合计 **18/18** 通过，耗时 142.729 秒；API 契约 **354 paths** 一致。独立 [PR #73](https://github.com/CoderDongHuang/InfoPulse/pull/73) 在最新 head 跑完整 CI，并在依赖 PR #72 正常合并后再合并。完整复现与结果见 [R12 报告](../audits/2026-10-13-profile-durability.md)。

### 68.3 仍然不能扩大解释的边界

本项只修正提交时序，没有证明资料 schema 的所有输入边界。显式 null、非法邮箱、大小写冲突和并发唯一性仍需独立处理。账户删除尤其不能直接照搬：知识删除服务可能先提交软删除，再操作外部文件；最后用户删除失败时，前面的副作用已经发生。要保证一致性，需要明确可恢复状态、外部清理任务与 legal hold 合同，不能在末尾多写一个 commit 就宣称整体原子。

事务专项逐个推进的意义在于让每个结论都有自己的观察点和反例。完整后端集合从历史 217 项增加到含资料回归的 221 项后，应使用新提交的实际运行记录，而不是将旧总数当成最终验证。未完成的领域继续保留在路线图；每次扩展覆盖都需要真实测试与独立合并证据。

## 69. 从“能够更新资料”到完整身份合同

本节记录 2026-10-14 的实现与实验，不能将前文的历史待办当作本节之后仍未修复，也不能把本节的四个专项扩展为整个产品已正式完成。对应独立变更为 [R13 / PR #74](https://github.com/CoderDongHuang/InfoPulse/pull/74)、[R14 / PR #75](https://github.com/CoderDongHuang/InfoPulse/pull/75)、[R15 / PR #76](https://github.com/CoderDongHuang/InfoPulse/pull/76) 与 [R16 / PR #77](https://github.com/CoderDongHuang/InfoPulse/pull/77)，最终 CI 和合并状态应查对应 PR 的最新 head。

### 69.1 为什么事务修好之后还有漏洞

R12 保证成功资料在响应前提交，但事务不会替我们定义输入含义。一个请求完全可能成功提交错误身份；另一个请求可能因为 null 触发非空约束，返回服务器错误。正确性至少包含三个相互独立的命题：请求值符合身份合同、数据库在竞争下仍保持唯一、登录能够唯一解析到预期账户。只有其中一个成立，不能推出其他两个。

![资料输入、数据库唯一性与登录命名空间](../blog-assets/2026-10-14/identity-boundaries.svg)

图 69-1 是工程说明图，图片独立保存在博客资源目录，不是产品截图。箭头代表约束的依赖，底部说明了可观察结果与迁移前提。图片刻意保留 Unicode 和维护窗口限制，不把尚未验证的性质画成绿灯。

### 69.2 省略与 null 是两种不同操作

对部分资料更新，`{}` 表示没有修改字段；`{"email": null}` 是主动给字段赋空值。原模型把两者都声明为 Optional，存储层却不接受空邮箱，API 和数据库的合同因此不一致。修正后的规则为：省略保留、显式 null 返回 422、头像空字符串表示清空。

```python
class UserUpdateRequest(BaseModel):
    model_config = ConfigDict(json_schema_extra=profile_schema)
    username: str | SkipJsonSchema[None] = Field(None, min_length=3, max_length=50)
    email: EmailStr | SkipJsonSchema[None] = Field(None, max_length=100)
    avatar_url: str | SkipJsonSchema[None] = Field(None, max_length=500)

    @field_validator("username", "email", "avatar_url", mode="before")
    @classmethod
    def reject_null(cls, value):
        if value is None:
            raise ValueError("省略字段以保留原值；清空头像请使用空字符串")
        return value
```

None 在这里是内部省略哨兵，不是外部接受值。默认值不触发 supplied-value validator，服务使用 `model_dump(exclude_unset=True)`，因此空 patch 不写字段。SkipJsonSchema 避免把内部哨兵公布为可接受 JSON 类型；额外 schema 处理移除默认 null。运行时行为与 OpenAPI 一起改变，不能只修 Python 校验而留下客户端误导。

用户名还需要先 trim 再验证长度。若长度检查先运行，`" a "` 会以三个字符通过，然后被清理为一个字符。注册与更新共用规范化逻辑，并禁止 @，邮箱则用 EmailStr 校验后转小写。头像沿用原字符串合同，本项没有引入图片抓取或新的网络副作用。前端资料 DTO 单独定义，避免复用注册类型时意外带 password 或漏掉 avatar_url。

### 69.3 422、409 和 500 的区分

422 表示请求本身不能写入；409 表示格式正确的身份已被其他账户占用；提交失败仍应传播为失败，不能为了“友好”返回成功。资料服务在写字段前排除当前账户进行大小写查重，并在 flush 遇到唯一冲突时 rollback 后返回领域冲突异常。API 将这一异常映射为 409，用户不存在仍保持 404。

服务没有增加 commit。业务组合仍可由上层事务控制；实际资料 API 在响应前提交。预检负责常见冲突的可解释反馈，数据库负责竞争时的最终裁决，两者用途不同。

新增四项 schema 和四项真实 HTTP 回归。HTTP 使用实际 JWT、鉴权依赖、ORM 与文件 SQLite，测试依赖不替 API 提交；非法输入、重复身份和竞争 flush 失败后，另一连接必须仍读到原资料。合法输入、本人大小写变体、空 patch 和清空头像则必须立即可见。本机与既有认证/事务组合 **24/24** 通过，455.472 秒；前端 **25/25**、类型检查、构建与 **354 paths** 契约同步通过。

## 70. 唯一性迁移是一项数据治理操作

### 70.1 查重不能代替唯一约束

考虑两个连接同时检查 SharedUser 尚未存在。它们都获得“可用”，随后分别写 SharedUser 和 SHAREDUSER。原区分大小写的唯一约束允许两者提交，登录的 lower 查询却可能返回两行。无论服务检查写得多仔细，只要检查和写入之间存在并发窗口，就需要数据库约束兜底。

实际模型和迁移 0034 增加：

```python
op.create_index("uq_users_username_lower", "users", [sa.text("lower(username)")], unique=True)
op.create_index("uq_users_email_lower", "users", [sa.text("lower(email)")], unique=True)
```

对于已有账户，索引创建不仅是 DDL，还提出“重复身份属于谁”的治理问题。不能自动删掉后一条、给后一条加后缀，或把邮箱大小写重复直接合并。账户可能拥有报告、组织、会话和隐私数据，字符串重复不证明它们属于同一个人。

### 70.2 先检查全部字段，再创建任何索引

迁移分别按 lower(username) 和 lower(email) 分组寻找重复，两项全部通过后才创建任一索引。PostgreSQL 持有 SHARE ROW EXCLUSIVE 表锁，阻止预检和创建之间出现新写入。失败提示指出冲突字段和人工解决要求，不输出具体身份值，也不改变账户记录。

SQLite 的迁移测试直接调用实际 revision，检查升级、降级、再升级和两个冲突分支。PostgreSQL 则使用随机命名临时库，先升级到 33，写入两账户，再分别制造用户名或邮箱冲突；升级失败后完整字段快照、Alembic version 和索引状态都不能改变。修正冲突后升级并执行实际资料 API 的 409 检查。

```python
outcomes = await asyncio.gather(
    writer("a", "SharedUser"),
    writer("b", "SHAREDUSER"),
)
assert sorted(outcomes) == ["committed", "conflict"]
```

代码只展示竞争断言；实际脚本为每个 writer 建立独立 asyncpg 连接，用事件同步开始，每个 UPDATE 有独立数据库事务和超时预算。相同实验也对邮箱执行。测试结果为每次一提交、一唯一冲突，而不是两个 mock 按预设值返回。之后 head → 33 → head 的带数据往返必须保留全部身份字段。

本机 SQLite **2/2**（0.037 秒），PostgreSQL 16 五组检查全部完成，脚本同时接入 Python 3.10/3.11 的产品 CI。随机临时库在 finally 删除，本机验收容器结束后关闭，卷保留。

### 70.3 这项约束仍然有哪些不足

lower() 是数据库操作，不是跨语言、跨排序规则的通用 Unicode casefold。SQLite 默认 lower 的能力与 PostgreSQL 排序规则可能不同，Python `.lower()` 也不能被当作完全相同的定义。本次实验使用 ASCII 大小写，没有声称所有国际化身份已统一。若将来定义规范化 identity_key，必须同时讨论存量转换、冲突政策、显示名和登录名分离、规则版本及索引变更。

表锁与普通索引创建会阻塞写入，因此指南明确要求维护窗口和副本演练。大型表的在线索引创建涉及事务限制和失败索引清理，需要独立设计；不能简单在当前迁移加 CONCURRENTLY 就宣称无停机。降级删除新增索引后，大小写竞争保护消失，也需要作为回退风险说明。

## 71. 字段内唯一不等于登录无歧义

一个更隐蔽的反例来自旧数据：账户 A 的 email 是 `owner@example.com`，账户 B 的旧 username 恰好为同一字符串，但 B 的 email 是 `legacy@example.com`。两个字段内部都唯一，因此 0034 升级可以通过；原登录 OR 查询却匹配两个账户。

新注册与资料规则禁止 @ 用户名，但历史值不会自动消失。把 scalar_one_or_none 换成 first 只会把报错变成任意选择账户，没有解决合同。R16 按输入划分命名空间：

```python
identity = User.email if "@" in username else User.username
result = await db.execute(
    select(User).where(func.lower(identity) == username.lower())
)
user = result.scalar_one_or_none()
```

邮箱形输入仅按邮箱认证，其余按用户名认证；密码与启用状态继续校验。历史账户 B 仍可通过自己的邮箱登录，随后修改用户名，不自动改名、不丢失数据。这是一次有明确兼容影响的安全修正，弃用说明记录了替代入口。

真实双账户 HTTP 回归覆盖六种请求。每次成功都分别解析 access 和 refresh token，要求 sub 为指定用户；尝试使用 B 的密码登录 A 的邮箱必须 401，缺失邮箱和用户名也必须无令牌。只断言 200 不足以证明认证正确，验证最终身份才是这一实验的关键。专项与认证/签发组合 **13/13**（104.976 秒）通过，完整三环境 CI 在独立 PR 上继续执行。

## 72. 完整回归如何并行，同时证明没有少跑

### 72.1 超时也是需要保留的实验结果

R13 初始 head 的 Windows 3.10 实际执行 229 项，2616.649 秒，随后 45 分钟 job 预算取消，后续契约和迁移没有完整验收。Windows 3.11 则通过。这不是测试断言失败，也不能算完整门禁通过。先将旧串行预算临时提高到 60 分钟，保留原失败和新 head 的重新验收；R15 再用独立分片方案解决反馈时长。

### 72.2 分类按夹具，而不是按文件名或方法长度

unit 类经过人工审阅，不使用数据库/文件 fixture。含 HTTP、ORM 或持久化夹具的类整体归 integration，即使其中一个方法仅校验字符串。未分类的新类默认 integration，避免开发者增加复杂测试时因漏维护白名单而完全不执行。

以完整类名的 SHA256 映射三个分片，同类留在同一进程，保留类夹具和方法顺序。每个 job 独立安装依赖、使用临时存储及测试数据库。e2e 仍是独立 PostgreSQL 浏览器与容器验收，不把某个文件名中的 e2e 当作完整产品证据。

```python
class_id = identifier.rsplit(".", 1)[0]
index = int.from_bytes(
    hashlib.sha256(class_id.encode()).digest()[:8], "big"
) % shard_count + 1
```

稳定分配易复现，但不天然平衡耗时。当前 55 unit、49/59/74 integration 的条数不均，最长片反而是 59 项，说明数量不能代替耗时。后续可以用已记录的逐项耗时做类级分配，但应保持可审查、可复现的计划，不能临时改分片绕过失败。

### 72.3 两层完整性证明

runner 发现完整集合后保存 discovered、partitions 和 planned，completed 初始为 false。执行结束保存实际 IDs、逐项秒数和失败列表。导入失败、重复发现、过期分类、空选择、漏跑、skip 或 expectedFailure 都不能通过；list-only 只是计划，没有验收含义。

```python
complete = Counter(result.executed) == Counter(report["planned"])
success = (
    result.wasSuccessful()
    and complete
    and not result.skipped
    and not result.expectedFailures
)
```

第二层由独立汇总 job 核对每个指定环境的四份原始 JSON：环境和分片必须齐全，各自发现集合及分区一致，计划等于该分区，实际执行等于计划。合并四组后，每个发现项必须恰好出现一次。一个 job 没运行、没有上传、只上传初始化报告，或重复执行同一片，都不能让总门禁通过。

六项新增回归故意构造重复发现、失败导入、漏组、缺环境、伪计划、skip 和 expectedFailure，检查门禁确实拒绝它们。这些测试验证的是防止“绿色但少跑”的机制，而不是简单复制业务实现。

### 72.4 本机测量和解释限制

| 层 | 项数 | 测试阶段秒数 | 结果 |
| --- | ---: | ---: | --- |
| unit | 55 | 0.035 | 全通过 |
| integration-1 | 49 | 296.694 | 全通过 |
| integration-2 | 59 | 495.463 | 全通过 |
| integration-3 | 74 | 398.742 | 全通过 |
| 汇总覆盖 | 237 | 不以求和代表墙钟时长 | 每项恰好一次 |

本机为 Windows Python 3.10，三个集成进程同时启动，最长测试阶段约 8.26 分钟。表格不包含安装和 discovery，不应与历史 hosted runner 的 43.61 分钟直接计算加速比；测试集合也不同。CI 在 Linux 3.11、Windows 3.10、Windows 3.11 各跑四组，共 12 个回归 job，并保存自己环境的统计。

并行减少关键路径等待，但增加重复安装与计算成本。当前预算保留，待积累实际分片统计再收紧。跨平台完整依赖、SQLite 往返、契约、PostgreSQL 双版本产品、两种容器和漏洞审计继续保留，没有用删测试换数字。

## 73. 下一阶段：恢复、删除与跨域 fixture

完成四个专项后，项目仍定位 v0.x 开发者预览。现有源码可以公开研究和本地使用，不等于所有模块具备稳定版保证。下一批优先处理账户删除的可恢复状态和 legal hold、媒体/行动/编排 worker 中断恢复、全按钮负向 UI、固定跨域业务 fixture 和 SDK 真实 HTTP 合同。真实模型、SMTP、S3、SSO 与消息平台需要独立提供商环境，不填写虚构密钥。

账户删除尤需先明确数据合同：外部文件与数据库不能通过一个本地事务共同原子提交。若先删文件再提交用户，数据库失败时文件已丢；若先提交再删文件，存储失败时可能留下孤儿。应考虑可恢复删除请求、授权与 hold 预检、后台幂等清理、逐对象结果和人工核对，再分别设计失败、重启和并发 worker 的观察点。这个方向当前仍是设计要求，没有在路线图勾成已完成。

审计的价值是让完成范围可被反驳和复核：合法请求成功时查独立 reader；竞争唯一性时用独立连接；认证时查 token sub；并行时查实际执行 inventory；迁移失败时查数据、version 和两个索引。每个结论都有明确观察对象，比“运行没有报错”更适合开源项目的长期维护。

## 74. 从独立修复到主分支：最终证据

截至 2026-10-14，R13–R16 已按依赖顺序分别合并。资料校验 [PR #74](https://github.com/CoderDongHuang/InfoPulse/pull/74)、数据库身份唯一性 [PR #75](https://github.com/CoderDongHuang/InfoPulse/pull/75)、测试覆盖 [PR #76](https://github.com/CoderDongHuang/InfoPulse/pull/76)、历史登录身份 [PR #77](https://github.com/CoderDongHuang/InfoPulse/pull/77) 都以各自最新 head 的完整 CI 为前提。main 合并提交依次为 `3de9ace`、`9192a8d`、`4ce7a9b`、`fd1f87a`。改指向 main 后查询到的合并提交仍与已验证提交一致，没有在合并时加入未测试文件。

| 覆盖报告的历史时点 | Linux 3.11 | Windows 3.10 | Windows 3.11 |
| --- | --- | --- | --- |
| R15 分片方案 | 237 / 237 | 237 / 237 | 237 / 237 |
| R16 加入历史身份回归 | 238 / 238 | 238 / 238 | 238 / 238 |

每个环境四组报告齐全、每项恰好执行一次，覆盖汇总 completed=true。R16 最长测试组的实际阶段时长分别为 96.079 / 775.905 / 738.123 秒；这些数字不包含依赖安装和 discovery，也不能当作历史串行 job 的同机对照。产品浏览器、PostgreSQL 迁移与竞争写入、两种容器、前端构建与回归、SDK、安全审计和 CodeQL 同时通过。

这轮没有把旧 Windows 取消记录改写为通过。PR #74 预算修正后 Windows 3.10 / 3.11 的完整 job 分别耗时 38 分 55 秒 / 27 分 45 秒，原先 45 分钟时限的失败另行保留。后续分片解决的是反馈关键路径，覆盖门禁证明的是测试集合没有丢失，两者对应不同的工程问题。

博客与最终验收文档归入独立 [PR #78](https://github.com/CoderDongHuang/InfoPulse/pull/78)，补充合并证据后的最终 head 仍执行完整门禁。开源成熟度继续使用 v0.x 开发者预览；上述测试结果证明这些明确范围，并不证明真实提供商、所有功能按钮或全部异常恢复已经完成。

## 75. 从“有页面”到“真实可用”：工作台的数据合同

### 75.1 问题不是空状态难看，而是它没有连接数据

在多阶段功能开发中，很容易得到一个路由丰富、功能名称齐全的应用，但首页仍返回固定的 `recent_reports=[]`。即便报告模块已经能创建和编辑，用户也不能从工作台继续上次工作。它不是单个组件的视觉缺陷，而是上下文在聚合 API 和领域数据之间中断。

R18 的目标不是做一套推荐算法，而是建立一个足够小、可以完整验证的合同：只返回当前账户的未删除报告，最多八份，按更新时间倒序、ID 次序兜底，只携带列表需要的字段。隔离、删除语义、排序和上限都是合同的一部分；“查到任意八条”不等于正确。

对后端而言，用户条件必须进入查询，而不是查询所有报告后在前端过滤。对前端而言，空列表必须来自成功响应；读取失败应有错误状态及重试。若把异常捕获为 `items=[]`，用户会被误导为数据不存在，这比简单抛出异常更难定位。

### 75.2 操作成功与刷新成功是两个事实

收藏和反馈也存在类似问题。一次请求已经成功写入，随后刷新首页失败，此时如果统一提示“收藏失败”，用户可能重复提交。相反，如果一开始就乐观显示成功而没有等待写请求，又会把未保存的动作当成事实。

采用的处理顺序是：锁定操作、等待写请求、明确确认写结果，再刷新读取；刷新失败给出“操作已保存，列表刷新失败”的独立反馈。请求期间禁用入口，finally 清理状态，失败不冒充成功。这种分层反馈让用户知道究竟应重试哪一步。

本项后端专项 4/4、前端 29/29、真实浏览器 11/11；[PR #79](https://github.com/CoderDongHuang/InfoPulse/pull/79) 最新 head 的 Release Gate 与 CodeQL 全部通过后，正常合并为 main 的 `0da5109`。后续 R19 会增加测试，不能把本节的历史数量当作当前总数。

## 76. 顶部工作空间：信息架构先于配色

### 76.1 研究问题和设计假设

本轮界面改版的研究问题可以表述为：当应用已有数十个页面时，能否移除常驻侧栏，同时不丢入口、不降低当前任务的可辨识度，并让账户操作始终可找到？这里没有进行用户实验，因此不能宣称“效率提升百分之多少”。能够验证的是导航完整性、关键交互可达和空间约束。

设计采用常见工作空间模式，而不是临摹某个平台的品牌资产：顶部品牌与常用入口、分组菜单、右侧账户；第二行保留当前位置、全局搜索、通知和 AI 入口；内容区域承担具体研究任务。灰白构成背景和面板，蓝色只用于主操作、选中和焦点，风险颜色保留语义，不再为每个功能设置一套装饰色。

![顶部工作台真实截图](../blog-assets/2026-10-15/workspace-top-navigation.png)

上图为隔离数据库中的测试账户、测试报告与空推荐状态。空推荐意味着未同步真实内容，不通过预置“热门新闻”伪造数据丰富程度。左侧内容面板仍有继续压缩空白和优化密度的空间，截图不证明推荐质量。

### 76.2 用数据表达导航，而不是复制多份模板

顶部常用项为工作台、数据概览、发现；分组为研究分析、协作与行动、平台与工具。个人中心属于账户菜单，不混入业务功能组。新的 `navigation.ts` 同时供桌面菜单和移动抽屉使用，避免两个模板分别增删入口后逐渐漂移。

下面摘自实际匹配逻辑：

```ts
export function isActivePath(current: string, target: string) {
  return current === target ||
    (target !== '/' && current.startsWith(target + '/'))
}
```

根路径不能按普通前缀判断，否则所有页面都选中工作台；`/reports-other` 也不能被误判为 `/reports` 的子页。报告编辑器和事件详情则应正确选中父模块。因此这里验证路径边界，而不是简单 `startsWith(target)`。

导航回归从真实路由声明提取静态目的地，排除登录、账户和重定向别名后，与导航集合精确比较，同时检查重复项。这个测试可以发现未来“路由有了、导航没加”或“双入口误重复”的回归；它并不证明每个路由内部所有按钮已经可用。

管理员入口通过 `adminOnly` 筛选，普通用户看不到运行管理。必须强调，这只是信息架构与体验：授权仍应由后端执行，不能把菜单隐藏当作权限保障。

### 76.3 布局预算要统一计算

旧界面的内容和工具栏包含侧栏偏移。仅改变菜单模板，会留下空白左边距或覆盖内容。现在外壳约束为：顶部主栏 68px，工具栏桌面 56px、小屏 52px，因此内容顶部留出 124px 或 120px。内容区不再计算侧栏宽度，登录页则完全移除外壳及其留白。

主内容宽度、stage 页面宽度和个人中心宽度分别按阅读任务约束，不强行所有页面全屏铺满。个人中心 1120px 上限在桌面给账户摘要和编辑区分配稳定比例，小屏在 760px 以下改单栏；1050px 以下主导航换成抽屉，避免十几个文字入口挤压头像。

![390px 工作台](../blog-assets/2026-10-15/workspace-mobile.png)

## 77. 个人中心：一个表单同时涉及身份、事务和会话

### 77.1 页面结构和功能边界

个人中心左侧显示头像、用户名、邮箱、账户类型和加入时间，右侧为资料编辑及会话说明。账户摘要来自真实当前用户，表单初始值必须等待 GET 成功；读取失败提供重试，不能用空字符串构造“已加载”页面。

![桌面个人中心](../blog-assets/2026-10-15/profile-desktop.png)

本轮支持用户名、邮箱、头像链接，支持撤销和保存。没有加文件上传、头像裁剪、密码修改、账户删除或“已验证邮箱”标签，因为这些需要另外的后端合同与验收。尤其账户删除不能仅靠一个危险按钮调用多存储删除逻辑，前文的跨存储一致性问题仍未解决。

### 77.2 差量字段与历史兼容

资料表单不能简单把所有值每次全部发送。历史用户名可能包含 @，即使用户只修改邮箱，也不能顺手触发新用户名规则并阻断保存。实际 helper 先规范化，再比较保存快照，只对变更字段校验和构建请求：

```ts
const username = form.username.trim()
if (username !== saved.username) {
  if (username.length < 3 || username.length > 50 || username.includes('@')) {
    throw new Error('用户名需为 3–50 个字符，且不能包含 @。')
  }
  patch.username = username
}
```

邮箱 trim 后小写，头像 trim，未改字段省略。空头像字符串明确表示清空，不发送 null。这里前端函数名为 `profilePatch`，但它返回的是“仅变更字段的请求体”，实际 HTTP 仍遵循既有 PUT `/auth/me` 合同，不擅自发明 PATCH 端点。

客户端校验用于提前反馈，不取代服务端 Pydantic 校验、409 领域冲突和数据库 lower 唯一索引。浏览器可以被替换，前端规则不是数据完整性的最终裁决者。服务响应前提交的持久性由此前 R12/R13/R14 的回归支撑，本项再通过真实页面操作与 reload 验证 UI 接到了那条正确链路。

### 77.3 一个过期响应不应恢复旧账户

假设资料保存请求 A 仍在网络上，用户已退出或切换为账户 B。如果 A 回来后直接赋值 `userInfo`，右上角可能显示 A 的身份。令牌已经清理不代表前端不会被旧异步响应污染。

Store 使用会话 epoch，而不是单纯检查请求成功：

```ts
async function updateProfile(data: ProfileUpdateRequest) {
  const epoch = sessionEpoch
  const info = await authApi.updateMe(data)
  if (epoch !== sessionEpoch) throw new Error('会话已变化，请重新登录。')
  userInfo.value = info
  return info
}
```

epoch 表示当前登录生命周期，退出和替换登录会推进它。只有发起时与完成时仍属于同一生命周期，响应才能更新账户信息。新增回归挂起真实函数依赖的 Promise，在返回前改变 epoch，要求函数拒绝且不覆盖新账户对象。这不是服务器端会话撤销的替代物：本项关注 UI 迟到响应，服务器撤销仍由实际 logout 流程验证。

### 77.4 头像的网络和隐私语义

`UserAvatar` 对 URL 解析后只接受 HTTP/HTTPS，拒绝相对地址、data、javascript 以及 URL 内嵌账号密码；图片失败显示姓名首字。`referrerpolicy="no-referrer"` 避免把当前页面地址带给图片源。头像是普通浏览器图片加载，本轮没有引入服务器抓图，因此不能声称实现了图片代理或统一图片出站治理。

no-referrer 也不等于匿名请求：图片站点仍可能看到客户端 IP 和其他浏览器请求特征。界面明确要求使用受信公开链接。若未来提供上传，应补文件类型识别、大小/尺寸限制、隔离存储、访问控制、缓存和删除策略，不能直接把任意上传变成公开静态文件。

## 78. 账户菜单：看到菜单不等于键盘可以用

![右上角头像菜单](../blog-assets/2026-10-15/avatar-menu.png)

菜单有个人中心和退出登录。验收从键盘 focus 开始，Enter 打开、Escape 关闭，再检查焦点回到触发按钮。第一次真实浏览器检查发现菜单关闭行为不稳定：UI 库内部状态和触发器焦点并不总能满足新的外壳结构。修复后维护 dropdown 实例引用，Escape 显式调用 `handleClose()`，随后 focus 触发器；测试同时检查菜单不可见和按钮 focused。

这比“click 可以打开”更有约束力。若焦点遗留在已经隐藏的菜单项，键盘使用者下一步导航会不确定；若只把焦点挪走而菜单未关，屏幕上仍有悬浮状态。两个断言分别捕获不同问题。

退出使用进行中标志，避免重复发起；先执行现有 Store 的本地清理与服务端撤销请求，再跳登录页。浏览器产品脚本不是只断言“到了登录页”，还拿旧令牌调用 API，要求服务端拒绝，再用修改后的用户名和原密码登录。此验证运行于正常网络，不能据此宣称断网退出也能立即撤销服务器会话；断网时本地已清理与服务器已确认撤销仍是不同事实。

![320px 单栏个人中心](../blog-assets/2026-10-15/profile-mobile.png)

最窄截图中长邮箱在输入控件内水平滚动，属于输入框自身的正常行为；页面不能出现横向溢出。测试在 1024、768、390、320px 逐一检查两个页面及导航入口。抽屉关闭和路由切换会产生短暂动画，检查等待宽度在限定 5 秒内稳定，超时报告溢出元素，不用 `overflow:hidden` 掩盖布局问题。无障碍仍需全站进一步审计：当前只是基础键盘和响应式证据，不是 WCAG 完整合规声明。

## 79. 搜索入口修复：参数、并行读取与空状态时序

### 79.1 URL 改变不代表业务已使用参数

原全局搜索跳转到洞察页并带 q，但实际业务并没有完整使用它。改版将入口对齐 `/search?q=...`，搜索页从路由读取字符串 q。外壳的 router-view 已按 fullPath 重建页面，因此连续不同 q 会触发新实例，不需要再叠加一个重复发请求的 query watcher。

浏览器检查不只看输入框文字，还记录实际 `/api/v1/search` 请求中的 q；分别提交两个关键词，要求两次参数都正确。这避免“地址栏正确、请求仍是旧条件”的假通过。

### 79.2 初始空状态是一种竞争条件

初版实现先等待来源和已保存搜索，再调用搜索；搜索 loading 初始为 false。浏览器可能在元数据尚未结束时看到 `items=[]`，于是显示“没有匹配内容”。这不是数据确实为空，而是尚未查询。测试曾在这一中间状态完成断言，暴露了状态合同不清。

修复分成三点：loading 初始为 true；搜索与元数据独立启动；元数据内部使用 `Promise.allSettled`，保留成功的一半并展示可恢复提示。这样来源接口异常不阻止搜索，也不丢掉已成功读取的已保存搜索。

```ts
onMounted(() => {
  void loadMetadata()
  void search()
})
```

搜索异常只设置 `searchError`，不把数据清空成成功的空结果；页面优先显示加载，再错误，再真正空列表，最后结果。两项新增前端测试执行页面真实函数，验证已有数据保留、错误明确、重试恢复，以及元数据部分失败与后续恢复。

本项没有同时完成搜索详情、保存/删除搜索、创建事件的全部异常和并发顺序控制。读请求的迟到响应次序也需要后续专门设计请求序号或取消机制。不能因为入口正确就把整个搜索模块标成完工。

## 80. 实验协议、可复现证据与有效性威胁

### 80.1 分层实验

本轮采用四层证据：纯逻辑与提取真实函数回归、TypeScript/生产构建、真实浏览器/API/数据库链路、GitHub 跨平台门禁。前三层本机已经完成，第四层必须针对准备合并的最新 head 重新执行，不能借用 R18 的绿色状态。

| 实验 | 本机结果 | 不能推导的结论 |
| --- | --- | --- |
| 前端 Node 回归 | 36/36，无跳过 | 不等于所有组件 DOM 和所有业务按钮通过 |
| 类型与生产构建 | 通过 | 不等于运行时 API 或提供商必然可用 |
| 入口包体 | JS raw 505160 / gzip 174180；CSS raw 133805 字节 | 不等于所有动态路由、网络和设备的性能预算 |
| Edge 产品 | 12/12，三类错误数组为空 | 不等于真实模型、外部数据源、所有 worker 恢复通过 |
| 小屏布局 | 两页四种宽度通过 | 不等于所有页面、设备和辅助技术完整验收 |

JS/CSS 数字为当前静态入口依赖图，不是整个 dist 总体积；预算分别为 raw JS 600000、gzip JS 200000、raw CSS 160000 字节。UI 库依赖存在 PURE 注释告警，构建器仍成功，它不能被误写为类型或构建错误，也不应为了日志漂亮修改第三方代码。

### 80.2 真实冲突、故障注入和持久化验证

资料测试先注册第二个随机账户，用它的真实邮箱制造冲突，要求页面出现已被占用、输入保留，独立 GET 仍是原邮箱。网络失败通过浏览器路由仅中断 PUT，不制造一个虚假的成功 API。随后挂起 PUT，检查按钮和字段禁用，再放行真实请求，要求仅一次写入。最后 reload 后仍显示新用户名。

这里使用了故障注入，但没有把整个后端替换成预置响应。冲突由真实数据库产生，保存由真实事务完成；网络拦截用于可重复构造传输失败和提交中状态。产品脚本还保留知识大文件上传与引用检索、取消无写入、协作 WebSocket、非空行动表格、36 路由巡检和退出撤销。各组范围不同，不能把“36 路由能加载”解释成 36 个模块的每个按钮都验收完毕。

### 80.3 截图也可能产生错误证据

首次目视检查发现，菜单已能交互时，截图捕获了缩放淡入的中间帧；移动资料页也在 opacity 过渡中显得灰白。业务断言通过不保证配图是最终视觉状态。文档捕获使用 Playwright `animations="disabled"` 将有限 CSS 动画推进终态，仅作用于截图，不把交互阶段的动画全部禁用。

截图随后重新生成、完整产品脚本重跑 12/12，并检查桌面/移动图。它们单独保存于图片目录，记录视口、测试数据来源与生成方式。随机邮箱和报告标题只是 fixture，不是用户资料或模型能力展示。

### 80.4 内部、外部和构造有效性

内部有效性方面，本地 dev server 可以暴露 Vue 运行警告，但与 Nginx 生产包不是同一运行方式；因此构建和容器 e2e 都保留。网络故障注入验证可控传输异常，不覆盖所有真实代理或断电情况。

外部有效性方面，本机 Windows + Edge + PostgreSQL 不能代表所有 Linux、Python、浏览器或 Docker 构建；CI 的双 Python 产品、minimal/full 容器和 Windows 回归必须按最新 head 独立成立。本轮本机 Docker Hub 元数据连接失败，没有把缓存数据库运行写成容器镜像构建成功。

构造有效性方面，“通过项数”是协议执行结果，不是缺陷密度、代码覆盖率或用户满意度。界面采用常见工作空间模式，也未进行可用性对照实验。本文不给没有测量依据的提效比例或“达到头部平台水平”评价。

## 81. 后续路线：从外壳收敛到领域完成度

后续优先级遵循风险和实际用户链路，而不是继续增加抽象阶段编号。

第一，沿工作台 → 搜索 → 事件 → 报告补齐固定跨域 fixture。现在各模块有不同层次的测试，但仍缺一条从采集到通知回执的完整可重复业务证据。设计时应固定输入来源、时间、身份和预期副作用，分开验证“入队”“执行”“远端确认”。

第二，逐领域统一页面组件与请求状态。新的全局外壳已经统一，但旧页面仍有硬编码青绿色、复杂内联模板和重复异步逻辑。下一步应抽取经过验证的表单/列表状态与领域 composable，补真实 DTO，避免一次性全站换皮同时改变业务行为。每个领域单独 PR、单独回归，比较改前后请求和副作用。

第三，继续负向矩阵：401、409、422、断网、取消、超时、多次提交、响应乱序、跨账户及跨租户。这里本次已证明的只是个人中心和部分读取路径；按按钮列出“前置状态、请求、成功、失败、重试、权限、持久化观察点”，比仅按页面打勾更能发现实现不彻底。

第四，账户删除、媒体/行动/编排 worker 中断恢复优先于装饰性功能。它们涉及外部副作用和未知执行结果，错误重试可能造成重复投递或扣费。必须定义 lease、未知状态、人工核对和可恢复清理，不把单数据库 rollback 当作跨存储事务。

第五，补真实提供商和性能评测。LLM、SMTP、S3、SSO 及消息渠道需要使用维护者明确提供的测试账号与 secret，不能写入虚构配置。固定模型集应测引用、无证据行为、结构、成本和失败降级；前端性能则需要动态路由、长列表和实际设备的测量。当前包体门禁只是起点。

最终，开源可用性不是“没有任何待办”。一个诚实的 v0.x 项目可以在本地清晰启动，有可信的完成范围、可复现测试、清楚的限制和可执行路线。维护者需要做的是让每个完成标记都能追溯到代码与证据，并让未完成部分继续显式存在，而不是用更多页面和更漂亮的截图替代可靠性。

## 82. 从开发预览到公开数据可用：一次真实数据实验

2026-10-16 的迭代把目标限定为无需第三方密钥的读者链路。这个范围的核心研究问题是：仅凭公开接口，能否从空白安装持续获得真实信息，并让普通账户完成检索、阅读、收藏和日报通知？这比证明页面能打开更接近实际使用，也比笼统宣称所有 AI 能力可用更容易复核。

实验包含四类异构输入：HN 的社区讨论信号、GitHub 的仓库元数据、DEV 的文章摘要和 arXiv 的论文摘要。它们并不提供同一种业务含义。例如 star、评论和论文时间不能直接理解为同质的社会热度；GitHub Search 也不等于 GitHub Trending。统一层只保存共同可观察字段，展示来源与解释规则，保留原始 payload 以便追溯。暂不把缺失正文补成模型生成的“原文”。

### 82.1 调度状态与持久化状态分开

原有手动同步入口可执行，不等于普通读者首次打开时一定有数据。为此增加周期来源 worker：先原子登记内置来源，逐一判断 enabled 和 last_sync_at，再对到期来源执行采集。每个来源使用独立事务，一个上游异常不终止整个批次。

```python
async with sessions() as db:
    source = await db.get(DataSource, source_id)
    if source is None or not source_is_due(source, utc_now()):
        continue
    run = await sync_source(db, source, trigger_type="scheduled")
    await db.commit()
```

轮询间隔默认 30 秒，但不是每 30 秒抓取每个网站：HN/GitHub 周期为 30 分钟，DEV 为 60 分钟，arXiv 为 120 分钟。没有成功的新数据时保持诚实空态，来源失败则保留实际错误。这里的周期值是保守默认值，后续仍需根据上游政策、请求额度和数据质量调整。

### 82.2 网络 IO 不能占着本地数据库写锁

最初实现先更新同步状态，再等待上游返回。这在 PostgreSQL 中可能表现为长事务，在 SQLite 中更直接地阻塞注册、收藏或调度任务。即使网络最终超时，用户也已经体验到无关功能卡住。修复的关键是把慢网络操作放在获取写锁之前。

抓取之后不能无条件入库，否则两个 worker 同时读到同一快照会重复更新。实现使用 last_sync_at 比较并交换：

```python
claimed = await db.execute(
    update(DataSource).where(
        DataSource.id == source.id,
        DataSource.enabled.is_(True),
        DataSource.last_sync_at == source.last_sync_at,
    ).values(last_sync_at=started)
    .execution_options(synchronize_session=False)
)
if claimed.rowcount != 1:
    raise AppError("SOURCE_BUSY", "该来源已被其他同步任务处理，请刷新后重试", 409)
```

这保证只有仍持有有效快照的一方能进入写入阶段，不保证只有一次网络请求。其工程收益是避免外部 IO 占用写锁，也不需要提交一个可能永久遗留的 running lease。进程在事务提交前退出，数据库会回滚该事务；对外部副作用有不可逆影响的行动 worker 则不能简单复用这一推理。

回归使用真实文件 SQLite 和两个独立连接：第一个任务的 collector 被事件挂起，第二个连接必须仍能提交来源更新；随后释放第一个 collector，要求陈旧 CAS 被拒绝且内容数仍为零。单连接或纯 Mock 测试无法证明“等待网络期间不阻塞另一个写者”这一性质。

### 82.3 批次失败与审计记录的原子性

还有一个容易忽略的失败模式：前几个条目已加入 session，后面的条目违反约束。如果只捕获异常并将 run 标记 failed，数据库仍可能提交前面的内容，统计却声称整个批次失败。反过来，对整个 session rollback 又会丢掉解释失败的 run。

这里用 savepoint 包围内容写入，失败后保留外层运行记录。计数归零、来源健康标为 error，最后提交失败事实。savepoint rollback 还可能使 ORM 对象过期，因此异常分支显式 refresh run，再更新终态，避免在异步上下文隐式触发数据库 IO。

```python
try:
    async with db.begin_nested():
        # 查找 source_id + external_id，新增、更新或刷新抓取时间
        await persist_items(db, items)  # 此处为说明性伪函数
        await db.flush()
except Exception:
    await db.refresh(run)
    run.status = "failed"
    run.created_count = run.updated_count = run.skipped_count = 0
```

仓库实际实现将循环保留在 source_sync.py 中，上例的 persist_items 仅用于突出事务边界。行为测试让第二个条目的 canonical_url 为非法空值，验证内容完全回滚而失败运行记录仍存在。测试不是“断言调用了 begin_nested”，而是观察可持久化结果。

### 82.4 真实网络暴露证书问题

第一次真实 canary 中 HN、DEV、arXiv 成功，GitHub 因本机证书链无法验证而失败。修复没有关闭 TLS 校验，而是合并操作系统信任与 certifi 的公共根：

```python
def public_ssl_context() -> ssl.SSLContext:
    context = ssl.create_default_context()
    context.load_verify_locations(cafile=certifi.where())
    return context
```

这样可以识别由本机明确授信的企业代理，同时继续验证证书和主机名。它不代表任意代理都可信，也不能解决接口配额或连接不可达问题。复测四个内置源各取得 30 条，GitHub 历史失败保留在运行日志中。把失败保留下来，是后续诊断所需的证据，而不是影响展示的“脏数据”。

### 82.5 信息真实还要求时间和摘要真实

某些上游没有发布时间。如果按 published_at 过滤，真实采集内容可能永远不可见；如果把抓取时间写成发布时间，则产生错误事实。新的发现查询使用 coalesce(published_at, fetched_at) 参与候选筛选，输出仍保留 published_at=null，界面显示“来源未提供发布时间”。发布时间是来源声明，抓取时间是系统观察，这两个概念必须保留区别。

同样，SQLite 返回的 naive datetime 需要按数据库既定 UTC 约定恢复时区再序列化，否则浏览器可能把 UTC 当成本地时间，造成八小时偏差。HN 的 HTML 摘要转换为纯文本，保留原始 payload；Vue 文本插值仍负责转义，没有用 v-html 执行外部内容。

发现页默认“全部 / 本周”，并明确分页是在最近 500 条候选里进行。论文和开源仓库可按 content_type 进入对应频道，不能要求标题必须恰好包含 paper 或 GitHub 才可被发现。推荐分数只是时效、互动与关注命中的规则排序，不是事实可信度或模型判断。

![真实公开数据发现页](../blog-assets/2026-10-16/discover-real.png)

### 82.6 普通读者视角的验收

实际浏览器脚本通过注册界面创建普通用户，读取真实后台采集结果，按真实标题检索并核对详情，点击收藏，再检查工作台推荐和收藏持久化。随后创建 daily_report 任务，等待 worker 执行成功，要求 output.matched 大于零，并找到引用同一 report_id 的站内通知。最后暂停验收任务，避免留下持续运行的测试日报。

这是无模型的有来源规则汇总，不是模型摘要质量评测。站内通知也不能扩大解释为邮件送达。来源页检查普通账户没有“添加 RSS”和“立即同步”管理按钮，服务端原有管理员鉴权继续保留，界面隐藏只是减少误操作，不能代替权限控制。

![普通读者来源状态](../blog-assets/2026-10-16/sources-real.png)

此次观察到四源最新请求成功，首次完整验收保留 124 条真实内容，最终摘要/时区复测为 129 条；7 组普通读者链路通过。重复同步和来源滚动会改变数量，因此这些数字是实验记录。另有确定性前端 42 项、来源相关后端 19 项、354 路径 API 契约及隔离产品 12 组回归；完整后端发现 245 项，由 CI 的 Linux/Windows 分片继续验证。实时网络 canary 与 CI fixture 保持分离，不能让上游临时故障造成不可重复的每次 PR 门禁，也不能用 fixture 冒充真实源成功。

### 82.7 本地使用边界与可持续优化

新增 public_server 入口专门服务本机使用：自动迁移、持久化随机密钥、专用目录、不读取原有 .env。普通用户无需填写凭据，维护者可通过本机命令给已注册账户授权。此设计减少首次安装障碍，但不能替代公网反向代理、HTTPS、备份、操作系统账户隔离或长期运维。当前前端入口仍使用 Vite 本地服务器，两个进程需要保持运行。

下一阶段优先补三类证据：第一，上游限流分类、Retry-After 与退避，避免把外部限额当作代码异常；第二，PostgreSQL 多进程竞争及来源 worker 中断恢复，避免把 SQLite 证明外推到所有数据库；第三，大数据量检索、跨源重复与 RSS 实站兼容矩阵，避免小样本验证掩盖规模问题。LLM、邮件和身份提供商仍需要真实测试账号单独验收，实验模块不因主链完成而自动升级等级。完整完成标记和后续路线见 [R20/R21 验收记录](../audits/2026-10-16-public-use.md)。

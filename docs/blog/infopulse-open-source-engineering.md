# 从舆情工作台到可验证智能平台：InfoPulse 的开源工程设计

> 本文基于 InfoPulse 2026-08-08 的代码与实测结果，介绍项目背景、架构选择、关键实现、验证方法、问题解决过程、已知不足与后续路线。它不是营销材料，也不把未配置的第三方服务描述为已经完成真实生产验证。

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

## 39. 结语

InfoPulse 当前已经达到“可以公开代码、供开发者本地运行和继续贡献”的阶段。它还没有达到“拿到任意环境即可无配置生产运行”的阶段，也不应该这样宣传。

开源的价值在于把边界写清楚：哪些链路经过自动化验证，哪些依赖外部账号，哪些问题仍待解决。相比展示更多功能，这种可验证、可追溯、可持续改进的工程基础更重要。

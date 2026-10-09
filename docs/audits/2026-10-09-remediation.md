# InfoPulse 修复与验收报告

日期：2026-10-09。原始问题见 [修复前审计](./2026-10-09-project-audit.md)，长期路线见 [路线图](../30-open-source-roadmap.md)，功能边界见 [能力矩阵](../32-capability-matrix.md)。

## 1. 结论与完成定义

本轮已修复审计列出的 A01-A12 具体缺陷，补齐知识任务恢复、会话撤销、跨进程限流和 API schema 门禁，并通过隔离 PostgreSQL 的真实浏览器验收。建议仍以 `v0.x` 本地开发者预览发布，不宣称所有模块已经成为稳定产品。

“完成”指表中明确的实现与测试，不表示任意第三方账号、任意网络、全量 UI 按钮、生产负载或未来漏洞都已验证。可选密钥保持空值，不使用虚构凭据。本轮不读取个人 `.env`、不连接业务数据库、不调用付费模型、不修改真实第三方资源。

## 2. 缺陷逐项对应

| 编号 | 状态 | 修复范围 | 验证与文件 |
| --- | --- | --- | --- |
| A01 注册越权 | 完成 | 注册永远非管理员；本机 CLI 单独提升，大小写查重 | `auth_service.py`、`scripts/admin.py`；`test_audit_regressions.py` |
| A02 RSS SSRF | 完成 | 公网 IP 校验、每跳 DNS 固定、原始 TLS SNI、禁用环境代理、大小/总预算限制 | `core/outbound.py`、`collectors/rss.py`；出站负向回归 |
| A03 安装/执行目标漂移 | 完成 | connector 安装与审批目标绑定，逐次复查权限/URL；POST 不追随重定向 | `services/platform.py`、`commercialization.py`；`test_execution_regressions.py` |
| A04 匿名生成 | 完成 | 热搜解释要求身份，生成接口限流 | `api/hot_search.py`、`middleware/rate_limit.py`；匿名 401 浏览器断言 |
| A05 共享源权限 | 完成 | 全局源创建/编辑/删除/同步要求系统管理员 | `api/sources.py`；普通用户 403 回归 |
| A06 回执异常 | 完成 | 去除重复构造字段，核验租户、行动、run；自动回执只由执行器创建 | `services/action_loop.py`；回执与越权回归 |
| A07 SQLite 时区 | 完成 | 数据库无时区时间归一 UTC 后比较 | `core/time.py`、相关 worker；过期/租约回归 |
| A08 SSE 终态 | 完成 | 统一成功/失败/取消/超时结算，清理 timer，传递服务端错误 | `frontend/src/utils/sse.ts`；5 项前端测试 |
| A09 条件分支 | 完成 | 无匹配必须失败，含混出边和错误图结构拒绝 | `services/orchestration.py`；执行回归 |
| A10 编排空执行 | 完成（支持工具范围内） | durable dispatch；真实投递结束前保持 pending；真实记忆查询；缺模型明确 unavailable | `services/dispatch.py`、`orchestration.py`；mock HTTP 的副作用与故障回归 |
| A11 行动无执行器 | 完成（人工/connector） | 人工等待回执；connector 执行、自动回执、完成连接；不支持的停止条件拒绝 | `action_worker.py`、`action_loop.py`；未知投递不得伪装完成 |
| A12 协作不写执行版本 | 完成 | 校验工作流图、CAS、保存 WorkflowVersion 草稿，不替换发布版本 | `collaboration.py`、`test_collaboration.py`；浏览器版本 1 -> 2 断言 |

关键实现文件均在 `backend/app/` 下，测试在 `backend/tests/` 下。重用公网请求和 dispatch 基础设施，不把不同领域的通知、平台 webhook 与业务回执强行合为一个服务。

## 3. 工程问题与剩余范围

| 编号 | 本轮状态 | 已落实 | 未落实/不能推出的结论 |
| --- | --- | --- | --- |
| B01 安装与依赖 | 部分完成 | base/render/full 分层、维护版本、tzdata、干净 Python 3.10 安装与 pip check、一次 Python 审计 | 全平台锁文件、镜像 digest 和长期兼容矩阵仍需维护 |
| B02 超时预算 | 完成配置与回归 | 模型 45 秒总预算，前端 120 秒，Nginx 180 秒；超预算终止 | 全长任务取消/恢复/跨域事务尚未统一，是独立后续优化 |
| B03 知识任务 | 完成（当前队列范围） | staging 先于 DB commit、lease/attempt/恢复、有界读取、阻塞存储/解析转线程 | 大规模对象存储一致性、孤儿 staging 清理和压力测试待补 |
| B04 默认网络与代理 | 部分完成 | Docker loopback 端口绑定；Vite/Nginx WS 配置 | Vite WS 实测通过；本机完整镜像构建与 Nginx WS 未通过环境验收 |
| B05 安全与会话 | 部分完成 | refresh 单次消费、sid 会话校验、logout 撤销、DB 限流失败关闭、指标默认拒绝 | 全 API 威胁模型、代理身份与分布式压测仍需专项验证 |
| B06 门禁与评测 | 部分完成 | 354 路径的完整参数/认证/body/response/schema 快照；真实产品验收脚本 | 静态规则得分不是模型质量；固定模型评测集待补 |
| B07 实验模块宣传 | 完成文档纠偏 | 能力矩阵标明实验/外部依赖，不再把 formal/BFT/删除声明当作证明 | 没有因此实现真实形式化验证或分布式共识 |

## 4. 浏览器发现的额外故障

### 4.1 知识上传 422

前端 Axios 全局 `Content-Type: application/json` 将 FormData 转成 JSON，后端 multipart 路由返回 422。移除全局格式，由 Axios 根据请求数据自动处理 JSON 或 multipart boundary。验收实际点击上传，等待 worker 将文档标为 ready，再检索到带文件名的结果；不是直接调服务函数替代 UI。

### 4.2 空 PostgreSQL 外键与并发目录初始化

编排工具引用 connector 定义，首次进入编排时平台目录还未初始化，PostgreSQL 报外键错误。修复为先初始化平台目录。多个页面同时进入时，原来的 select-then-insert 又发生唯一键竞争，改为 SQLite/PostgreSQL `INSERT ... ON CONFLICT DO NOTHING`，保留用户禁用配置。增加启用外键的空库测试和 12 个并发初始化测试。

### 4.3 UI 状态与移动工具栏

知识页面上传后定时刷新状态，销毁页面时清理 timer；修复窄屏溢出和“上传”按钮折行。桌面与移动端截图来自本轮隔离 fixture，不含用户数据。

### 4.4 容器上传入口与媒体有界读取

Nginx 默认限制 1 MB 与后端知识 25 MB、媒体 250 MB 的默认限制不一致。代理整体请求上限设为 256 MiB，后端仍按单文件约束拒绝；提高后端配置时应同步评估代理限制。媒体 API 原先无界 `file.read()` 改为上限加一读取，新增超限负向测试。浏览器固定上传 fixture 改为略大于 1 MiB 的 Markdown（空行填充，不制造海量索引），容器 job 可以捕捉代理 413。

![桌面知识检索](./images/2026-10-09/knowledge-desktop.png)

![移动知识页面](./images/2026-10-09/knowledge-mobile.png)

## 5. 实测证据

| 检查 | 本机结果 | 解释 |
| --- | --- | --- |
| 最终全量后端 unittest | 187/187，751.843 秒 | 包含本轮负向、并发、生命周期回归；不等于行/分支覆盖率 |
| 第二批媒体有界读取回归 | 新增 1 项，模块共 4 项 | 第一批全量为 187；第二批远端全量预期 188，以 CI 实际结果确认 |
| 初始化配置复查 | 1/1 | 两次生成不同密钥，禁止覆盖，模型空值，crawler/media 默认关闭 |
| 前端 SSE | 5/5 | 单终态、服务端错误和清理逻辑 |
| 前端类型检查/构建 | 通过 | 主包仍约 1 MB，有第三方 PURE 注释告警，不冒充优化完成 |
| 前端依赖升级与审计 | 通过，0 条已知漏洞 | CI 首次发现 4 个 high 节点，已更新 Axios 1.20.0、Vue 3.5.43、source-map-js 1.2.2；升级后测试/构建/浏览器复跑通过 |
| TypeScript SDK 构建 | 通过 | 不等于 SDK 已完成真实 HTTP 兼容矩阵 |
| OpenAPI 完整快照 | 354 路径通过 | 检测 schema 漂移；不是语义兼容性证明 |
| SQLite 迁移 | 空库 -> head -> base -> head 通过 | 隔离库，无用户数据 |
| PostgreSQL 迁移与 API | 空库 -> head 通过 | pgvector/pg16，33 个迁移，实际注册与写入 |
| 干净 Python 环境 | 3.10 base 安装、pip check 通过 | 本机 Windows；Linux 矩阵由新增 CI 验证 |
| Python 依赖审计 | 记录中零条已知漏洞 | 见 `python-dependency-audit.json`；仅对应记录依赖及审计时点 |
| 浏览器产品验收 | 7 组通过，JS 错误/5xx 均为空 | Edge Chromium；原始结果见 [result.json](./images/2026-10-09/result.json) |
| 完整 Docker/Nginx | 尚未验收 | Docker Hub 基础镜像获取失败；不是把配置解析算成运行通过 |

浏览器检查覆盖：未登录重定向、UI 注册与非管理员身份、匿名解释拒绝、UI 新建/上传/索引/引用检索、同源 WebSocket ping/pong、协作草稿落库与发布版本不变、36 路由壳巡检、390px 移动布局、刷新恢复、UI 注销后旧 token 401、重新登录。

36 条路由能加载不代表每个页面按钮都正确；检索 fixture 通过不代表复杂 PDF/OCR/视频或真实向量质量通过。没有调用真实 LLM/SMTP/S3/SSO/第三方 connector。

### 复现命令

在项目根目录运行，API/UI 终端单独保持运行。只对隔离测试库使用这些脚本，不能指向业务数据库。

```powershell
docker compose -p infopulse-audit -f docker-compose.audit.yml up -d postgres redis
cd backend
python -m scripts.acceptance_server --database-url postgresql+asyncpg://audit:audit-local-only@127.0.0.1:15432/infopulse_audit
```

```powershell
# 另一个终端，frontend 目录
$env:VITE_API_PROXY_TARGET='http://127.0.0.1:18080'
npm run dev -- --host 127.0.0.1 --port 15173 --strictPort
```

```powershell
# backend 目录；未安装 Edge 时去掉 --browser-channel msedge
python -m playwright install chromium
python -m scripts.product_smoke --base-url http://127.0.0.1:15173 --browser-channel msedge --output ../acceptance-artifacts
python -m unittest discover -s tests -v
python scripts/api_contract_check.py
```

新增 CI 使用 Linux、Python 3.10/3.11、隔离 PostgreSQL/Redis 和 Playwright Chromium，运行空库迁移往返及上述产品验收，上传失败/成功截图、JSON 和服务日志。另设 Python 漏洞门禁与 CycloneDX 制品，以及实际构建容器栈、经 Nginx 运行 UI/WS 验收的 job；前端镜像升级到 Node 22 和 Nginx stable。是否在远端通过应以 PR checks 为准，不以 YAML 存在宣称验证成功。

## 6. 升级注意

1. 停止旧 API/worker，备份数据库、知识文件和配置，记录当前迁移版本。
2. 更新代码与依赖，运行 `alembic upgrade head`，当前 head 为 `20261009_0033`。
3. 首次使用可运行 `python -m scripts.init_local`，它拒绝覆盖已有配置；已有环境逐项比较 `.env.example`，不要覆盖原密钥或数据库地址。
4. 新会话要求 `sid`，旧 token 需要重新登录；管理员通过 `python -m scripts.admin --help` 查看本机提升命令。
5. 开启 connector 前配置真实 webhook 并完成授权审批；`unknown` 表示远端结果无法确定，应人工对账，不自动重新发送。
6. 回滚先恢复备份并评估字段/会话损失，不能以空库降级成功承诺业务数据无损回滚。

## 7. 后续验收顺序

先补完整容器与独立 worker 崩溃恢复、数据保留迁移矩阵和全核心 UI 负向验收，再进行重复模块收敛、DTO 类型生成、前端按需依赖与包体预算。最后补真实提供商、模型质量、删除一致性与性能/恢复基线。细节和完成标记统一维护在路线图，不重复制造互相矛盾的任务列表。

本轮代码提交分安全运行修复与产品验收文档两批；具体 PR 与 CI 结果见 GitHub。没有自动合并未经验证的 Dependabot major 更新。

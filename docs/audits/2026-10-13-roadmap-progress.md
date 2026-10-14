# 路线图逐项验收记录（2026-10-13）

每项以独立 PR 提交；只有实际测试通过才标记完成。A01–A12 的历史修复见 [前轮报告](./2026-10-09-remediation.md)，未完成工作见 [路线图](../30-open-source-roadmap.md)。本报告不将依赖运行验收扩大为真实提供商质量或全功能完成。

## R01：完整 Chromium / 媒体镜像

状态：完整容器运行依赖验收完成；独立 [PR #62](https://github.com/CoderDongHuang/InfoPulse/pull/62) 在全部门禁通过后合并。

- `docker-compose.audit-full.yml` 仅覆盖隔离测试栈的后端 Dockerfile，不读取个人配置，不修改生产栈。
- Release Gate 分别构建 minimal / full 镜像，两者都运行 Nginx 产品验收。
- `scripts.full_runtime_smoke` 在完整镜像中实际启动项目 BrowserManager 和 Chromium，渲染本地页面、执行 JS、应用 stealth 兼容层，并检查任务锁及进程释放。
- 使用 Pillow 和合成视频实际执行 ffprobe / ffmpeg，验证两帧上限、图像尺寸、WAV 音轨与临时目录清理。
- 清除模型凭据，验证缺少配置时拒绝调用；不访问第三方采集源、不调用付费模型。

本机验证：编译、工作流 YAML / compose 配置、`git diff --check` 通过；`tests.test_multimodal` + `tests.test_workflows` 共 **11/11** 通过。完整镜像构建在拉取基础镜像元数据前遇到 Docker Hub TCP 超时，未运行容器验收，不能作为通过证据。实际 CI 结果将补入本节。

复现（根目录；仅使用隔离测试栈）：

```powershell
docker compose -p infopulse-audit -f docker-compose.audit.yml -f docker-compose.audit-full.yml up --build --wait -d
docker compose -p infopulse-audit -f docker-compose.audit.yml -f docker-compose.audit-full.yml exec -T backend python -m scripts.full_runtime_smoke --output /tmp/full-runtime.json
docker compose -p infopulse-audit -f docker-compose.audit.yml -f docker-compose.audit-full.yml cp backend:/tmp/full-runtime.json full-runtime.json
docker compose -p infopulse-audit -f docker-compose.audit.yml -f docker-compose.audit-full.yml down
```

证据：CI 的 `container-acceptance-full` 制品包含 JSON、产品截图与容器日志。`completed: true` 只证明本地可选运行依赖及合成 fixture；真实网站登录、限流、站点变更、OCR/转录模型准确率仍是 P2 待验收内容。

首次 [Release Gate 38346096716](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38346096716) 中 full/minimal 容器均通过，full 的 JSON 有 5 项运行检查；Python 3.11 产品验收发现创建 Agent 会话后立即查询偶发 404。根因是 handler 只 flush，事务提交依赖响应后的清理阶段。会话创建、更新、删除、反馈改为成功响应前显式提交；新增独立数据库连接可见性与提交失败回归，不通过重试或忽略 pageerror 隐藏问题。

修复后本机 Agent 事务、Agent 业务、媒体、工作流共 **15/15** 回归通过；最终 Release Gate / CodeQL 状态及合并证据以 PR checks 为准。其他 API 中依赖 teardown 的事务提交仍需按领域审计，不能由这 4 个写操作的修复推定全项目已无竞态。

最终 [Release Gate 38347495734](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38347495734) 与 [CodeQL 38347495736](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38347495736) 全部通过，PR #62 已合并，主分支提交为 `45b1189`。

## R02：PostgreSQL 带数据迁移 / 独立知识 worker 恢复

状态：以下明确范围本机与 Linux Python 3.10/3.11 CI 均通过；独立 [PR #63](https://github.com/CoderDongHuang/InfoPulse/pull/63) 已在全部门禁通过后合并，主分支提交为 `2161117`。

使用专用 localhost 审计服务器创建唯一临时数据库，结束后删除该临时库；不清空或迁移服务器已有数据库。不读取个人 .env、模型凭据或知识目录。脚本拒绝业务库、非本机服务器和非 audit 用户，删除操作只接受生成的唯一库名。

1. head 建库并写入用户、来源、正文、事件及关联、分析及引用、报告及版本、知识库/文档/版本/向量分块/处理记录，共 14 张有数据的核心表。
2. head → 20260804_0029 → head，逐表比较行数及全部稳定字段 SHA-256；检查引用、外键、活动版本、正文和 PostgreSQL 96 维向量字段，不仅看迁移退出码。
3. staging 先落地，真正独立运行生产 worker 入口。在 claim 已提交后注入等待，再由操作系统 kill；原始上传仍存在，当前版本尚未提交。
4. 启动已连接数据库的第二个 worker，验证未到期 lease 不被抢占。随后将 lease 改为过去时刻，模拟生产 5 分钟到期，不实际等待 5 分钟。
5. 重启不修改知识处理逻辑的 worker，验证 attempts=2、ready、唯一活动版本与非空分块、staging 清理。
6. 两个独立 worker 均初始化后提交新任务，验证 attempts=1、版本数=1，不重复索引。

本机 PostgreSQL 16 / Windows Python 3.10 的 4 组集成检查通过；harness 安全边界单元测试与知识生命周期回归共 **15/15** 通过。CI 每次在 Linux Python 3.10 / 3.11 执行同一脚本，保存 `postgres-recovery.json` 的逐表摘要及 worker 日志。

代码提交 `4eca4bb` 的 [Release Gate 38348236028](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38348236028) 与 [CodeQL 38348235951](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38348235951) 全部通过，包含两个 Python 产品环境、完整/最小容器、后端、前端、SDK 与漏洞门禁。文档补充提交仍需通过最新 head 的同一门禁后才能合并。

最终提交 `1d1a30b` 的 [Release Gate 38348652259](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38348652259) 与 [CodeQL 38348652277](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38348652277) 全部通过后正常 squash 合并，没有跳过门禁。

复现（backend；先用隔离 compose 启动 postgres）：

```powershell
python -m scripts.postgres_recovery_smoke --output ../acceptance-artifacts/recovery
python -m unittest tests.test_recovery_harness tests.test_knowledge tests.test_knowledge_lifecycle -v
```

重要限制：降级会删除 revision 30–33 的 dispatch_jobs、auth_sessions、api_rate_limits 以及新增字段。本验收只证明 revision 29 已有核心数据保留，**不是全业务无损回滚保证**。仍须停 worker、备份数据库和文件、核对迁移版本，不能将脚本指向业务库。actions 的不确定投递不能自动重放；media / orchestration 恢复、其他领域表、完整备份恢复、RPO/RTO 仍为待完成事项。

## R03：前端按需组件与包体预算

状态：本机测试和生产构建浏览器验收完成；独立 [PR #64](https://github.com/CoderDongHuang/InfoPulse/pull/64) 已在最新 head 全部门禁通过后合并，主分支提交为 `c94c606`。

现有路由已使用动态 import，图标也已明确导入。主要问题是入口 `app.use(ElementPlus)` 注册整个库并导入全量 CSS。本轮只注册实际使用的 19 种组件，保留 `v-loading` 指令以及程序调用的 Message / MessageBox 样式。官方组件样式入口会带入内部依赖，避免只导入表面样式造成下拉/遮罩缺失。

构建使用同一工作区、同一已安装依赖（Vite 8.1.3、Node 22），基线为 `2161117`。统计所有 Vite manifest 的静态入口、递归 imports 及 CSS 的并集，共享依赖去重；gzip/Brotli 按单个资源压缩后累加，单位为字节。

| 指标 | 修改前 | 修改后 | 变化 |
| --- | ---: | ---: | ---: |
| 静态入口 JS 原始体积 | 1,099,167 | 503,002 | -54.2% |
| 静态入口 JS gzip | 355,166 | 173,251 | -51.2% |
| 静态入口 JS Brotli | 293,334 | 149,826 | -48.9% |
| 静态入口 CSS 原始体积 | 368,917 | 136,414 | -63.0% |
| 静态入口 CSS gzip | 50,745 | 19,963 | -60.7% |

以上为初版按需构建；补充取消处理后的静态 JS raw/CSS raw 不变，JS gzip 为 173,242、Brotli 为 149,868 字节，路由 chunk 的修复不会因动态拆分而改变静态图统计规则。

预算为 JS raw ≤ 600,000、JS gzip ≤ 200,000、CSS raw ≤ 160,000 字节；超出预算构建返回非零。预算约留 15–20% 空间，不能靠改 chunk 名称、拆 vendor 或提高 Vite 告警阈值绕过统计。所有执行 `npm run build` 的 CI 和 Docker 构建都会检查，frontend job 保存 `bundle-budget.json` 制品。

本机验证：

- `npm test`：初版 **9/9** 通过，补充取消确认回归后 **12/12** 通过，含静态依赖图递归/循环/去重/多入口、超限拒绝、缺失 manifest 拒绝、全部 Vue 组件注册/样式覆盖、loading 指令、SSE、取消/关闭无删除、确认后单次删除与失败不冒充成功。
- `npm run build`：类型检查、生产构建与新预算通过；第三方 VueUse PURE 注释位置警告仍存在，未隐藏或调高告警阈值。
- 隔离 SQLite + 本机 Vite **preview 生产产物** + Edge 的产品脚本：**8/8** 通过，新增真实 API 请求阻塞下的 loading 样式、选择日报筛选、打开确认框并取消删除、确认报告仍存在。原有上传/检索、WS、36 路由、移动布局和撤销登录继续通过。
- JSON 记录 `completed: true`，page_errors / server_errors / component_errors 均为空。初版新增脚本误将 create 响应当成包含 title，随后取消按钮误用了中文默认标签；已按实际契约及默认英文按钮修正，失败没有通过重试屏蔽。

复现（frontend）：

```powershell
npm test
npm run build
# 生成 dist/bundle-budget.json；超限会导致 build 失败
```

浏览器截图保存于 CI 产品验收制品（`components-desktop.png`、知识桌面/移动图），本机证据在忽略的 `acceptance-artifacts/bundle` 中。动态路由、认证页图片、首屏 LCP/INP、冷缓存网络测量未纳入当前预算；本轮减少传输体积，不宣称已证明某个加载耗时或全核心按钮完成。

首次 [Release Gate 38351461978](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38351461978) 的完整/最小生产容器通过，但开发服务器下两个 Python 产品环境均捕获 `page_errors: ["cancel"]`。原有报告删除 handler 没有处理 MessageBox 取消时的 Promise rejection；生产 Vue 的异常行为差异使本机生产预览没有将其上报为 pageerror。现已只处理预期的 cancel/close，其他异常继续传播，新增直接执行实际 handler 的回归；未忽略浏览器错误。其他模块的取消操作尚需逐页验收。

修复提交 `f2b872a` 的 [Release Gate 38352699229](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38352699229) 与 [CodeQL 38352699244](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38352699244) 全部通过，包含开发服务器的两个 Python 环境及两个生产容器环境。文档证据补充后仍以最新提交的 checks 为合并条件。

文档提交 `150c65a` 的 [Release Gate 38353290271](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38353290271) 中 Python 3.10 产品验收在 WS 等待 connected/pong 时失败，其余门禁通过。日志显示票据 POST 成功后连接被接受，但未收到消息。票据创建没有响应前提交，独立 WS 连接可能看不到尚未提交的票据；同时文档创建也存在相同边界。两个接口现在成功响应前提交，新增文件数据库的独立连接可见性、审计同事务持久化和两种提交失败回归。WS 验收记录提前关闭的状态码，不再将关闭误报为等待超时；没有加入重试或放宽成功标准。

本机隔离配置下后端全量 **193/193** 通过（补充协作事务测试之前的完整集合，702.690 秒）；新增回归结果和最新 CI 仍分别记录，不能将旧提交全绿当作当前 head 已通过。

补充协作事务、协作业务和多模态回归 **9/9** 通过（63.325 秒）；实际 PostgreSQL WS / 容器链路仍以本次提交的 CI 为准。

最终提交 `bdae03e` 的 [Release Gate 38354536068](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38354536068) 与 [CodeQL 38354536209](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38354536209) 全部通过。本机 Windows Python 3.10、隔离 PostgreSQL 16 + Vite dev + Edge 的 **8/8** 产品检查通过，错误列表均为空；随后正常 squash 合并，没有自动重试失败验收或绕过门禁。

## R04：Windows 后端持续验收

状态：以下范围的 Windows 两版本及其他 CI 门禁均通过；独立 [PR #65](https://github.com/CoderDongHuang/InfoPulse/pull/65) 以最新 head 全部门禁通过为合并条件。

原门禁主要运行于 Linux，本机 Windows 的一次成功不能代替持续兼容验证。新增 `windows-latest` Python 3.10/3.11 矩阵，从 checkout 安装完整 `requirements.txt`（包括可选浏览器 Python 包），执行 pip check、全模块编译、完整 unittest、API 契约快照，以及独立空 SQLite 库 head → revision 13 → head。每条 native 命令独立 step，失败立即影响 job，不能被下一条命令的退出码覆盖。两个 Python job 互不取消，保存各自依赖清单，详细执行证据在 Actions 日志。

CI 设置 UTF-8，并关闭采集、模型凭据、调度器及后台 worker；不访问个人配置或业务数据库。本机已有 Python 3.10 的 **193/193** 全量及补充事务 **9/9** 回归证据；Windows Python 3.11、干净解析安装和新迁移链路以本次 CI 的实际结果为准。

边界：此项验证 Python 包安装、代码导入、后端逻辑及 SQLite 空库迁移，不验证 Windows Chromium/ffmpeg、Windows PostgreSQL worker kill、所有浏览器按钮或完整备份恢复。依赖版本清单只是证据，不是约束/锁文件；多平台版本约束、镜像 digest 仍独立待完成。

本机独立运行 API 契约检查，**354 paths** 匹配；在唯一临时目录内执行 SQLite 空库 head → revision 13 → head 通过，未读取个人配置。首次 [Release Gate 38355919678](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38355919678) 的两项 Windows job 失败，其余 job 通过：Python 3.11 完整运行 196 项，其中知识库相关 9 项报 `invalid storage key`。生产 `Storage.__init__` 已 resolve 根目录，但测试夹具替换 `storage.local` 时使用未规范化的临时路径，Windows 的短路径别名/目录解析使它与 resolved 子路径的 parents 不等。夹具改为同样 resolve，不修改或放松生产越界判断；新增实际本地存储嵌套读写、删除、绝对路径/遍历/根目录拒绝回归。修复后的 Windows 全量结果仍待 CI，失败不能被勾选为完成。

Python 3.10 同样完整执行 196 项并出现同 9 项夹具错误（870.954 秒），无其他测试失败。修复后本机知识、生命周期、本地存储回归 **14/14** 通过（62.769 秒），`git diff --check` 通过。生产存储逻辑未修改；仍需新提交的 Windows 两版本全量证明。

修复提交 `7d03678` 的 [Release Gate 38358918583](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38358918583) 与 [CodeQL 38358918582](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38358918582) 全部通过：Windows Python 3.10 job 15 分 32 秒、3.11 job 12 分 52 秒，包含完整 **198 项** unittest、API 契约、SQLite 迁移、pip check 和模块编译。Linux 后端、两个产品环境、完整/最小容器、前端、SDK 与漏洞门禁也通过。文档补充后仍检查最新 head，不将旧 head 证据替代合并门禁。

最终提交 `3a03617` 的 [Release Gate 38362658709](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38362658709) 和 [CodeQL 38362658745](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38362658745) 全部通过后，PR #65 正常 squash 合并，main 为 `2133100`；没有跳过 Windows 全量门禁。

## R05：多页面对话框取消与写入边界

状态：以下范围完成；独立 [PR #66](https://github.com/CoderDongHuang/InfoPulse/pull/66) 的最终 head `df8a753` 通过 [Release Gate 38371505306](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38371505306) 与 [CodeQL 38371505311](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38371505311) 全部门禁后合并，main 提交 `643e235`。下文保留中间失败及修复过程，不把旧失败删除或靠 rerun 掩盖。

R03 产品测试发现报告删除的取消 rejection；逐页检查发现同样模式还存在于历史、订阅、多模态、知识库、图谱和预警页面。统一 `runDialog` 只将 Element Plus 的 `cancel` / `close` 转为正常退出；其他对话框错误及 API 错误继续传播。所有当前 MessageBox 操作都通过这一入口，取消后不调用写 API、不刷新、不清空选中对象；图谱 2/3 步输入在任何一步退出后立即终止。证据约束与确认后的实际参数保持不变。

测试直接用 TypeScript parser 提取页面实际 handler，并执行实际 helper，模拟对话框及 API 边界；不复制业务逻辑。新增 13 项，包含 12 个领域操作的每一步 cancel/close、确认仅写一次、非预期错误及 API 失败传播、失败不刷新/不报成功，以及图谱无来源证据拒绝写入。报告已有 3 项继续通过，前端完整 **25/25** 通过。

提交 `500c22a` 的 [Release Gate 38363697572](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38363697572) 与 [CodeQL 38363697676](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38363697676) 全部通过。随后将基分支衔接已合并的 main，仍以新 head 门禁为合并条件，不能沿用改基前通过结果。

`npm run build` 的类型、生产构建、静态入口预算通过：JS raw 502,997 / gzip 173,247、CSS raw 136,414 字节。第三方 PURE 注释警告仍未隐藏。

Windows Python 3.10 + 隔离 PostgreSQL 16 + Vite dev + Edge 的产品脚本 **9/9** 通过：知识库新建、网页导入、删除库、删除文档分别打开真实弹框并取消；记录请求并断言没有知识数据写入，文档 ready 和库名仍可见，再检索来源。报告取消、真实大文件上传/检索、WS、协作草稿、36 路由、移动端、登录撤销均通过，`page_errors` / `server_errors` / `component_errors` 为空。截图单独保存为制品 `knowledge-cancellation.png`。

首次新增检测误把携带查询体的 POST `/search-test` 计为写入，实际返回检索结果；随后按接口语义排除这一只读查询并重新运行，未忽略真实数据写入或浏览器错误。没有真实第三方调用或个人配置读取。

复现：`frontend` 执行 `npm test`、`npm run build`；隔离验收服务运行后，在 `backend` 执行 `python -m scripts.product_smoke --base-url http://127.0.0.1:15173 --browser-channel msedge --output ../acceptance-artifacts/dialogs`。CI 在两个 Python 产品环境及两个容器环境运行同一浏览器验收。当前单元模拟不能替代其余六页面全部按钮的浏览器操作；401/断网/超时、两用户协作、跨租户 UI 仍未标记完成。

改基后的 `b76c355` 在 [Release Gate 38367992804](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38367992804) 的 Python 3.10 产品验收失败：工作流 POST 201 后立即打开协作文档收到 404 `Workflow not found`。工作流创建仍只 flush，依赖响应后才 commit；现将工作流、初始版本、活动版本引用与审计在成功响应前同事务提交，不增加等待或重试。新增独立 SQLite 连接读取与真实协作资源校验、提交失败不得成功返回两项回归；首次测试传错上下文参数已修正，完整协作事务/协作/编排 **12/12** 通过（101.785 秒）。重启隔离 PostgreSQL 16 服务后 Edge + Vite dev 产品 **9/9** 通过，三类错误数组为空，证据为 `acceptance-artifacts/dialogs-transaction/result.json`。仍需修复后最新 head 的 CI；其他编排写操作的事务边界未由此全部证明。

随后 `7ba193a` 的 [Release Gate 38370214003](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38370214003) 中 Python 3.11 产品失败：UI 退出跳转后旧令牌 GET `/auth/me` 仍返回 200。前端已等待 logout API，后端撤销仍在响应后提交。logout 现在 204 之前 commit；新增文件 SQLite 独立连接验证访问/refresh 同时立即拒绝，以及 commit 失败不返回成功且不持久化撤销。认证专项 **6/6** 通过（19.188 秒），重启隔离 PostgreSQL 后 Edge 产品 **9/9** 通过，错误数组为空，证据为 `acceptance-artifacts/dialogs-revocation/result.json`。原 ASGITransport 回归会等待整个应用调用完成，包含依赖清理，无法证明真实网络上的响应前持久性，因此保留原测试并补上不同层次的验证。注册、登录、refresh 和其他领域事务边界仍需后续专项审计。

## R06：行动执行步骤表格结构

状态：以下范围完成；独立 [PR #67](https://github.com/CoderDongHuang/InfoPulse/pull/67) 的 head `97f7fa7` 通过 [Release Gate 38371632652](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38371632652) 与 [CodeQL 38371632664](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38371632664) 全部门禁后合并，main 提交 `be87a99`。

开发服务器巡检发现 `ActionLoopView` 把 tr 直接放在 table 下，Vue 报 HTML 嵌套告警；浏览器自动补 tbody 可能导致实际 DOM 与 Vue 预期不同。表头和步骤行改用明确的 thead / tbody，保持字段和操作逻辑。

本机 `npm run build` 类型检查、生产构建、包体预算通过，JS raw 502,997 / gzip 173,243，CSS raw 136,414 字节。隔离 PostgreSQL + Vite dev + Edge 产品验收 **10/10** 通过，新增展示专用 GET fixture 打开非空行动详情，检查三个表头、序号/渠道/状态各列和无直接子 tr，截图单独保存 `action-step-table.png`。产品脚本还将 `cannot be child of` 控制台信息视为失败，防止再次只巡检空状态而错过模板缺陷。错误列表为空。

这一 fixture 只替代两条 GET 展示请求，拒绝拦截写请求，结束即撤除；不创建、批准或执行真实行动，不将展示验收当成 dispatch/outbox 的端到端验收。其余九组真实产品检查继续通过。复现命令与 R05 相同，仅输出目录改为 `../acceptance-artifacts/action-table`。

## R07：媒体失败原子性与不确定模型调用

状态：以下普通异常范围完成；独立 [PR #68](https://github.com/CoderDongHuang/InfoPulse/pull/68) 的 head `cbe7dcb` 通过 [Release Gate 38374321538](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38374321538) 与 [CodeQL 38374321541](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38374321541) 全部门禁后合并，main 提交 `1653bc0`。进程中断恢复并未由本项覆盖。

原代码在 try 之外读取源文件，文件丢失后 run 永远保持 running；except 又直接 commit，可能发布第一条 OCR/视频帧而后续处理失败，下一次重试撞 ordinal 唯一键，数据库 flush 失败后还可能触发 PendingRollbackError。

读取移入异常边界，使用线程执行同步存储操作。处理成功时证据、元数据、ModelUsage 与终态同事务提交并清 lease；失败先 rollback，再刷新持久化对象，独立提交终态，不把未发布元数据/证据/usage 留在数据库。视频普通失败会尝试清理本次生成但未发布的帧，并保留清理异常日志；这是尽力清理，不是对象存储和数据库分布式事务。

进入视觉/转写 adapter 后的任何错误保守标为 `unknown`，提示人工核对提供商结果。队列只认领 queued，普通 retry 只接受 failed，unknown 两条路径都拒绝；不自动重发可能已经扣费的请求。源丢失、模型路由缺失等调用前的确定本地失败仍为 failed，可在修正后显式重试。现有 actual_cost 字段是估算，unknown 的默认零值不代表免费；后续需真实账单/回执核对和人工解决流程。

同时关闭媒体 OpenAI SDK 默认的传输重试（`max_retries=0`），避免任务层拒绝重试但 SDK 已在内部重放。新增 adapter 构造参数回归，不请求外部服务；本机单独 **1/1** 通过（10.268 秒），与前述 10 项错误恢复回归分开记录。

本机隔离 Windows Python 3.10 文件 SQLite 的新 6 项与原媒体 4 项合计 **10/10** 通过（205.814 秒）。真实数据库事务、独立连接可见性和唯一约束生效；提供商用 mock，无付费调用。覆盖：源丢失终态及修复后显式重试成功；路由失败不调用模型；超时 unknown、worker 不重放和 API retry 返回 409；第二条 OCR 非法时第一条回滚；真实重复 ordinal 导致 IntegrityError 后仍可持久化 unknown；第二视频帧失败回滚证据、清理两帧并关闭临时目录。原成功图像 bbox/PII/usage 行为保持。

复现（backend，隔离配置）：`python -m unittest tests.test_media_failures tests.test_multimodal -v`。失败回归需持久化 queued fixture，再由实际 process_media_once 认领；测试不会自行补成功提交。

边界：旧版本已经提交的部分证据未自动删改，进程硬退出可能留下 running / 帧文件；claim 并发、lease 过期、旧 worker 写回 fencing、PostgreSQL kill/重启与 S3 清理仍是后续专项。未将总路线图的 worker 恢复项勾选完成。

## R08：认证令牌响应前持久化

状态：注册、登录、SSO exchange 和 refresh 四个 API 的专项实现完成，19/19 本机回归及真实 PostgreSQL + Edge 产品 9/9 通过；独立 [PR #69](https://github.com/CoderDongHuang/InfoPulse/pull/69) 的 head `e6937b1` 通过 [Release Gate 38374328468](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38374328468) 与 [CodeQL 38374328484](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38374328484) 全部门禁后合并，main 提交 `bf27447`。完整实验与限制见 [认证事务报告](./2026-10-13-auth-durability.md)。不把这里的 SSO 夹具扩展为真实身份提供商验收。

## R09：文档、证据与长篇博客同步

状态：README、文档索引、发布清单及博客已更新；新增第 56–68 节，明确历史时点、独立连接/进程、普通异常/进程 kill、fixture/真实副作用、实验时钟与 CI 预算的区别。博客约 7.1 万字符（不是中文词数），五张未加工真实截图保存于 `docs/blog-assets/2026-10-13/`，均有来源说明。

本机最终文档校验 **12 份 Markdown、93 个本地链接**及代码围栏闭合通过；最终输出与 CI/合并证据保存在 PR #70。5 张 PNG 全部解码验证，并逐图人工视觉检查。复现命令与现有脚本参数、隔离 compose 的数据库/端口核对。独立 [PR #70](https://github.com/CoderDongHuang/InfoPulse/pull/70) 同样执行完整 CI，不通过文档标签绕过门禁；最新合并证据以 PR 为准。

集成提交 `b8e27f5` 的本机认证/媒体组合回归 **30/30**（226.387 秒）、前端 **25/25**、API 契约 **354 paths** 与构建预算通过。隔离 PostgreSQL 16 + Vite dev + Edge 产品 **10/10**，三类错误列表均为空，结果为 `acceptance-artifacts/roadmap-integrated/result.json`；该原始目录不提交业务数据。其 [Release Gate 38374700051](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38374700051) 和 [CodeQL 38374700017](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38374700017) 全部通过，Linux 全量 **217/217**。随后同步 main 和补充本文合并证据，仍需最新 head 的门禁，不能沿用旧提交通过状态。

保留后续未完成项，不把整份路线图勾选完成；真实第三方密钥、备份恢复、其他 worker、完整 UI 负向矩阵仍需独立证据。查看当前勾选范围请使用 [路线图](../30-open-source-roadmap.md)，而不是旧博客中的设计目标。

## R10：限流测试的分钟边界

最终文档提交 `a7f0c59` 的 [Release Gate 38380603890](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38380603890) 中 Windows Python 3.10 完整运行 217 项，216 项通过；限流 HTTP 回归第一条请求在 10:18:59，后续进入 10:19:00，因此预期第 11 条 429 却得到 200。生产采用固定分钟窗口，测试错误依赖所有请求恰好位于同一分钟。没有重跑原失败以隐藏它。

独立 [PR #71](https://github.com/CoderDongHuang/InfoPulse/pull/71) 只替换测试中的限流模块时钟绑定，保留真实 middleware、SQLite 事务和并发计数；补充 239 秒额度耗尽、240 秒恢复额度、两个 Retry-After 的明确断言。本机限流/签名投递/模型预算专项 **6/6**，23.998 秒。head `4d8ac9f` 的 [Release Gate 38386828324](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38386828324) 与 [CodeQL 38386828656](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38386828656) 全部通过后正常合并，main 为 `159f1c1`。范围与限制见 [R10 报告](./2026-10-13-rate-limit-clock.md)，未修改生产算法。

## R11：Windows 全量门禁预算

状态：时限修正与本机 YAML 全结构比较通过；独立 [PR #72](https://github.com/CoderDongHuang/InfoPulse/pull/72) 以最新 head 的完整 CI 为合并前提，最终测试与合并记录见该 PR。只将 Windows job 的 30 分钟预算改为 45 分钟，保留完整依赖、测试命令、两个 Python 版本、迁移、契约与失败传播。

文档 head `847de1d` 的 Release Gate 38387941056 两个 Windows job 被 30 分钟时限取消；3.10 单测试阶段已完成 217 项，1702.129 秒，后续步骤尚未结束；3.11 直到取消前持续通过。取消未当作成功，不用旧 head rerun 替代修正，详见 [运行预算报告](./2026-10-13-windows-budget.md)。P1 的测试分层/并行仍待完成。

## R12：资料更新响应前持久化

状态：资料更新事务专项实现完成，本机新增四项与认证回归 **18/18**（142.729 秒），API 契约 **354 paths** 一致；独立 [PR #73](https://github.com/CoderDongHuang/InfoPulse/pull/73) 以最新 head 全部门禁通过为合并条件，最终证据见该 PR。

`PUT /auth/me` 构造响应后提交才返回；服务继续不自行 commit。独立文件 SQLite 连接立即可见 username/email/avatar，原令牌仍有效；提交失败不返回新资料，用户不存在保持 404，服务单独调用不泄露未提交数据。测试不读取个人配置、不使用业务库。字段验证、大小写唯一性、账户删除跨存储一致性及其他领域事务未由此完成，详见 [资料事务报告](./2026-10-13-profile-durability.md)。

## R13：资料输入校验与冲突响应

状态：专项实现与本机测试完成，独立 PR 的最新 head CI 及最终合并记录为发布依据。显式 null 返回 422，省略保留字段，注册与更新统一规范化用户名，邮箱验证并转小写；身份冲突返回 409，flush 竞争异常回滚。前端使用专用资料 DTO，契约同步说明安全修正。

新增 8 项与既有认证/事务回归合计 **24/24**（455.472 秒），前端 **25/25**、生产构建与 **354 paths** 契约通过。数据库并发大小写约束和账户删除仍独立跟进，详见 [R13 报告](./2026-10-14-profile-validation.md)。

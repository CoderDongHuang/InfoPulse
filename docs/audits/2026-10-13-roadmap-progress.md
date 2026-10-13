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

状态：本机测试和生产构建浏览器验收完成；独立 PR 的完整门禁通过后才能合并。

现有路由已使用动态 import，图标也已明确导入。主要问题是入口 `app.use(ElementPlus)` 注册整个库并导入全量 CSS。本轮只注册实际使用的 19 种组件，保留 `v-loading` 指令以及程序调用的 Message / MessageBox 样式。官方组件样式入口会带入内部依赖，避免只导入表面样式造成下拉/遮罩缺失。

构建使用同一工作区、同一已安装依赖（Vite 8.1.3、Node 22），基线为 `2161117`。统计所有 Vite manifest 的静态入口、递归 imports 及 CSS 的并集，共享依赖去重；gzip/Brotli 按单个资源压缩后累加，单位为字节。

| 指标 | 修改前 | 修改后 | 变化 |
| --- | ---: | ---: | ---: |
| 静态入口 JS 原始体积 | 1,099,167 | 503,002 | -54.2% |
| 静态入口 JS gzip | 355,166 | 173,251 | -51.2% |
| 静态入口 JS Brotli | 293,334 | 149,826 | -48.9% |
| 静态入口 CSS 原始体积 | 368,917 | 136,414 | -63.0% |
| 静态入口 CSS gzip | 50,745 | 19,963 | -60.7% |

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

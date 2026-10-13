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

状态：以下明确范围本机与 Linux Python 3.10/3.11 CI 均通过；独立 [PR #63](https://github.com/CoderDongHuang/InfoPulse/pull/63) 按全部门禁通过后合并的流程提交。

使用专用 localhost 审计服务器创建唯一临时数据库，结束后删除该临时库；不清空或迁移服务器已有数据库。不读取个人 .env、模型凭据或知识目录。脚本拒绝业务库、非本机服务器和非 audit 用户，删除操作只接受生成的唯一库名。

1. head 建库并写入用户、来源、正文、事件及关联、分析及引用、报告及版本、知识库/文档/版本/向量分块/处理记录，共 14 张有数据的核心表。
2. head → 20260804_0029 → head，逐表比较行数及全部稳定字段 SHA-256；检查引用、外键、活动版本、正文和 PostgreSQL 96 维向量字段，不仅看迁移退出码。
3. staging 先落地，真正独立运行生产 worker 入口。在 claim 已提交后注入等待，再由操作系统 kill；原始上传仍存在，当前版本尚未提交。
4. 启动已连接数据库的第二个 worker，验证未到期 lease 不被抢占。随后将 lease 改为过去时刻，模拟生产 5 分钟到期，不实际等待 5 分钟。
5. 重启不修改知识处理逻辑的 worker，验证 attempts=2、ready、唯一活动版本与非空分块、staging 清理。
6. 两个独立 worker 均初始化后提交新任务，验证 attempts=1、版本数=1，不重复索引。

本机 PostgreSQL 16 / Windows Python 3.10 的 4 组集成检查通过；harness 安全边界单元测试与知识生命周期回归共 **15/15** 通过。CI 每次在 Linux Python 3.10 / 3.11 执行同一脚本，保存 `postgres-recovery.json` 的逐表摘要及 worker 日志。

代码提交 `4eca4bb` 的 [Release Gate 38348236028](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38348236028) 与 [CodeQL 38348235951](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38348235951) 全部通过，包含两个 Python 产品环境、完整/最小容器、后端、前端、SDK 与漏洞门禁。文档补充提交仍需通过最新 head 的同一门禁后才能合并。

复现（backend；先用隔离 compose 启动 postgres）：

```powershell
python -m scripts.postgres_recovery_smoke --output ../acceptance-artifacts/recovery
python -m unittest tests.test_recovery_harness tests.test_knowledge tests.test_knowledge_lifecycle -v
```

重要限制：降级会删除 revision 30–33 的 dispatch_jobs、auth_sessions、api_rate_limits 以及新增字段。本验收只证明 revision 29 已有核心数据保留，**不是全业务无损回滚保证**。仍须停 worker、备份数据库和文件、核对迁移版本，不能将脚本指向业务库。actions 的不确定投递不能自动重放；media / orchestration 恢复、其他领域表、完整备份恢复、RPO/RTO 仍为待完成事项。

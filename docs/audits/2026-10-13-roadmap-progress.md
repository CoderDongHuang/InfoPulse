# 路线图逐项验收记录（2026-10-13）

每项以独立 PR 提交；只有实际测试通过才标记完成。A01–A12 的历史修复见 [前轮报告](./2026-10-09-remediation.md)，未完成工作见 [路线图](../30-open-source-roadmap.md)。本报告不将依赖运行验收扩大为真实提供商质量或全功能完成。

## R01：完整 Chromium / 媒体镜像

状态：完整容器已运行通过；修复产品验收发现的事务竞态后待完整门禁复验。

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

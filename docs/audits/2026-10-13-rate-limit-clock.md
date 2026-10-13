# R10：固定窗口限流的确定性测试

日期：2026-10-13。状态：已完成并正常合并 [PR #71](https://github.com/CoderDongHuang/InfoPulse/pull/71)。head `4d8ac9f` 的 [Release Gate 38386828324](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38386828324) 与 [CodeQL 38386828656](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38386828656) 全部通过，main 为 `159f1c1`。本机专项 **6/6** 通过（23.998 秒，Windows Python 3.10）。本项只改变测试夹具，不改变生产限流。

## 实际失败与根因

文档 PR #70 的提交 `a7f0c59` 在 Release Gate 38380603890 中，Windows Python 3.10 完整执行 217 项，216 项通过，只有 `test_concurrent_workers_share_atomic_window` 失败。第一条 HTTP 请求日志为 10:18:59.956，第二条为 10:19:00.039；生产逻辑以 `at // 60 * 60` 划分固定分钟，因此测试实际跨过两个窗口。第 11 条返回 200 并不能证明原子计数失效。Python 3.11 和其他门禁通过，不能用它们覆盖这次失败。

## 修复与验收合同

- 保留真实文件 SQLite、20 个并发 session 的条件 upsert 与提交，仍要求限额 5 时只有 5 次成功；下一窗口可再次消费。
- HTTP 测试只替换 `app.middleware.rate_limit` 的 `time` 模块绑定，提供固定 `239` 秒，不全局修改 `time.time`，不 mock 数据库或计数函数。
- 实际通过 ASGI middleware 发出 11 次登录请求，断言前 10 次 200、第 11 次 429，`Retry-After: 1`。
- 把同一时钟推进到 `240` 秒，实际再发 11 次，断言新窗口恢复 10 次额度并再次 429，`Retry-After: 60`。
- 不等待真实分钟、不增加重试、不放宽阈值、不把 200 接受为失败场景的通过结果。

这证明固定窗口的确定语义，不把它描述为任意滚动 60 秒限流。窗口边缘允许连续两分钟额度的突发是现有算法边界；滚动窗口/令牌桶和 PostgreSQL 多进程限流可另行立项，不能由本项假定已完成。

复现：在禁用个人配置的隔离环境中，于 backend 执行 `python -m unittest tests.test_delivery_security -v`。所有 CI job 保留，完整验收以独立 PR 的最新 checks 为准。

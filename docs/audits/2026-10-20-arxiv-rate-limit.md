# arXiv 429 修复记录

日期：2026-10-20。

原采集器对所有 HTTP 错误都在 0.2、0.4 秒后重试，没有处理限流等待时间。当前对 429 读取秒数或 HTTP 日期格式的 `Retry-After`，缺失或非法值默认等待 60 秒，不进行快速重试。其他来源的临时 5xx 仍有有界重试，永久 4xx 不再重复请求。

arXiv 采集器在同一进程中串行请求，保持至少 3 秒间隔；同一请求结果缓存 5 分钟。API 冷却期间使用官方联合分类 RSS，RSS 自身的 429 也进入冷却。RSS HTML 摘要转换为文本、分类交叉记录去重，并通过 OAI guid 保留与 API 一致的版本标识。两个入口都失败时不会返回过期缓存冒充成功，也不会清除历史内容。

验证：

- `tests.test_arxiv_resilience`、`tests.test_sources`、`tests.test_public_data` 首轮共 28 项通过。
- 补充 RSS OAI guid 回归后，`tests.test_arxiv_resilience` 共 10 项通过。
- 使用现有 `.public-local` 数据库真实同步 arXiv：`succeeded`，获取 30 条，新增 0 条，`error=None`。该验证由官方 API 恢复完成。
- 官方 RSS 的直接联网检查连接超时；回退解析及限流行为通过 MockTransport 验证，未声称本机 RSS 实际连通。

边界：缓存、间隔和冷却在进程内共享，不跨多个采集 worker。RSS 反映每日发布，不能保证与 API 提交时间排序完全相同。第三方限流或网络故障仍可能产生真实覆盖提醒。

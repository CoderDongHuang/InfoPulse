# 公开来源联网恢复与千问适配

日期：2026-10-19。范围是本机采集运行环境和私人模型配置，不是全项目稳定性验收。

## 已完成

- [x] 定位四源同时连接失败：此前后端从受限运行环境启动，本地 API 可达但采集连接受阻。保留原数据库、知识文件和加密主密钥，在具备外网权限的环境重启后恢复。
- [x] 实际运行 `python -m scripts.public_server --sync-once`：Hacker News、GitHub、DEV Community、arXiv 全部 `succeeded`，各获取 30 条。这是获取数，去重后新增数可能较少。
- [x] 增加千问北京/新加坡快捷配置和可编辑的文本、视觉、语音模型；密钥由每个账号自行保存，不上传仓库。
- [x] 新增 `media_transcription_protocol`，默认 `openai` 保持旧配置兼容；`qwen_asr` 通过 Chat Completions 的 `input_audio` 传递音频，不误用 Whisper 接口。
- [x] 请求前拒绝不兼容的 Filetrans/Realtime 模型、扩展名和过大 Base64；无时间戳时保留 `null`。官方千问文本/视觉调用关闭 thinking，以适配现有最终文本/JSON 消费方式。
- [x] 更新配置指南、能力边界、路线图、环境变量示例和 UI 回归脚本的预设选择器。

## 验证记录

| 验证 | 结果与边界 |
| --- | --- |
| 四源实际联网同步 | 4/4 成功，各 30 条，不保证未来上游可用性 |
| `python -m unittest tests.test_service_settings tests.test_qwen_models tests.test_media_failures tests.test_sources -q` | 41 项通过；覆盖私人配置加密与隔离、协议持久化/校验、SDK 请求、失败回滚与来源逻辑 |
| `npm test` | 59 项通过，包含预设地域、模型映射、凭据保留和服务切换 |
| `npm run build` | TypeScript、Vite 构建与 bundle 预算通过 |
| 调整音频体积边界后的协议与契约回归 | `tests.test_qwen_models`、`tests.test_api_contract_gate` 共 5 项通过；OpenAPI 快照更新为兼容新增字段，356 路径校验通过 |
| 重启运行检查 | 前端与代理 `/api/v1/health` 均返回 200，`demo_mode=false`、`acceptance_mode=false`；保持原本地运行数据 |

SDK 模型测试通过 MockTransport 检查真实 SDK 的请求结构、客户端关闭、无时间戳语义和旧 OpenAI 分段定位，未发送任何真实付费模型请求。浏览器停在登录界面，未使用用户账号修改私人配置；新增预设与保存流程本次没有完整浏览器登录验收，已有 UI 回归脚本已补相应断言。

## 待完成及使用限制

- [ ] 用户真实百炼账号下的文本、图片、音频效果与费用验收；不要把免费额度当成永久免费。
- [ ] 客户端音频时长检查与自动分段。当前本地检查体积，少于 5 分钟的要求由上游校验。
- [ ] Filetrans 时间戳、Realtime、语音合成和跨供应商独立密钥。
- [ ] 界面用量余额展示及真实费用限额控制；当前成本估算不代表服务商账单。

运行入口：[本地真实应用](http://127.0.0.1:15174/)。私人配置方法与官方参考见 [配置指南](../29-configuration-guide.md)。15173 为隔离验收实例，不作为日常采集入口。

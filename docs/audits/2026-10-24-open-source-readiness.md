# 2026-10-24 开源学习就绪与快速启动验收

## 结论

本次全新电脑路径在 Windows + Edge 上完成：按 README 启动后可注册、登录、打开工作台、查看真实公开来源健康状态，并运行无模型 Agent 证据摘要。项目适合开源学习和本地 beta 自托管；公网生产仍需独立完成真实凭据、备份恢复、可观测性、反向代理和长期稳定性验收。

## 环境与命令

- 日期：2026-10-24
- Node.js：22.19.0
- Python：3.12.14（使用 `backend/.venv-audit312` 验收环境）
- 后端：`backend/.venv-audit312/Scripts/python.exe -m scripts.public_server --port 18081`
- 前端：`VITE_API_PROXY_TARGET=http://127.0.0.1:18081`，`npm run dev -- --host 127.0.0.1 --port 15174 --strictPort`
- 浏览器：Microsoft Edge，`http://127.0.0.1:15174/auth`

## 实际步骤

1. 打开登录页并注册本地验收账号，登录成功。
2. 工作台加载成功，显示已采集公开内容和个人入口。
3. 打开发现页，路由和内容请求成功。
4. 打开来源中心，显示 4 个健康来源：DEV Community、GitHub、Hacker News、arXiv。
5. 打开 Agent，运行“总结今天 AI 行业的公开情报”，返回基于 20 条已采集证据的规则摘要；页面明确提示未配置模型时使用证据摘要。

## 发现并修正的问题

`frontend/.env.local` 的旧代理值为 `http://127.0.0.1:8010`，会让按 README 启动的注册/登录请求指向错误端口。验收使用命令行环境变量覆盖为 `http://127.0.0.1:18081`，并在 README 增加了醒目说明。后续可将本地示例文件进一步改成只保留占位符。

公开入口日志中的 Redis unavailable 属于可接受降级：Redis 是可选依赖，API 仍健康响应；需要缓存、分布式限流或生产任务吞吐时应配置 Redis。

## 数据与凭据边界

- 来源页和工作台的文章来自公开采集链路，不注入“演示文章”。截图和本记录中的账号、内容只属于隔离本地环境。
- 未配置 LLM 时，日报和 Agent 仅使用规则/证据摘要；编排 Agent 节点不会伪造模型成功。
- SMTP、S3、SSO/SCIM、微博/贴吧 Cookie、GitHub token 等均由使用者自行配置，仓库不包含凭据。
- 详见 [能力矩阵](../32-capability-matrix.md) 与 [配置指南](../29-configuration-guide.md)。

## 代码维护状态

本轮已将 `AgentView.vue` 和 `OrchestrationView.vue` 的状态、请求和生命周期逻辑拆到 `frontend/src/composables/useAgentView.ts` 与 `frontend/src/composables/useOrchestration.ts`，保持路由和 UI 行为不变，为后续组件拆分与单元测试提供边界。

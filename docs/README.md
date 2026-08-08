# InfoPulse 文档中心

本文档中心按“了解产品、开始开发、理解架构、运行维护、扩展能力”的顺序组织。接口实现以运行时 OpenAPI 为准，`api-contract-v1.json` 用于检测非预期契约漂移。

## 首次阅读

1. [产品 PRD](./01-产品PRD.md)：产品角色、页面、交互与验收边界。
2. [架构说明书](../架构说明书.md)：总体架构、模块边界与关键数据流。
3. [数据库设计](./03-数据库设计.md)：核心实体、约束、索引与迁移策略。
4. [接口文档](./04-接口文档.md)：REST、SSE、错误结构与鉴权约定。
5. [配置指南](./29-configuration-guide.md)：开发、测试与生产配置矩阵。
6. [开源优化路线图](./30-open-source-roadmap.md)：发布后的工程优先级与里程碑。

## 产品与开发

- [UI 设计规范](./02-UI设计规范.md)
- [开发计划](./05-开发计划.md)
- [技术博客：从舆情工作台到可验证智能平台](./blog/infopulse-open-source-engineering.md)
- [API 弃用策略](./api-deprecation-policy.md)
- [API 契约快照](./api-contract-v1.json)

## 安全、发布与运维

- [生产运行手册](./06-production-runbook.md)
- [安全、隐私与数据生命周期](./07-security-privacy.md)
- [发布检查清单](./08-release-checklist.md)
- [性能基线](./09-performance-baseline.md)
- [生产部署](./10-production-deployment.md)
- [SLO、错误预算与值班](./11-slo-oncall.md)
- [版本发布记录模板](./12-release-notes-template.md)
- [发布认证](./29-release-certification.md)
- [操作手册](./29-operations-handbook.md)

## 能力演进

| 阶段 | 文档 | 主题 |
| --- | --- | --- |
| 13 | [企业治理](./14-enterprise-governance.md) | 多租户、角色、SSO、SCIM、配额 |
| 14 | [开放平台](./15-open-platform.md) | API Key、OAuth、Webhook、连接器 |
| 15 | [Agent 编排](./16-agent-orchestration.md) | 工作流、模型路由、记忆、评测 |
| 16 | [多模态协作](./17-multimodal-collaboration.md) | 图片、音视频证据与实时协作 |
| 17 | [全球智能决策](./18-global-intelligence-decision.md) | 多语言证据、情景与决策室 |
| 18-19 | [行动闭环](./19-action-loop-impact.md) | 审批、执行回执与影响评估 |
| 20 | [产品化与商业化](./20-decision-productization-commercialization.md) | 模板、套餐、计费与交付 |
| 21 | [自治企业智能](./21-autonomous-enterprise-intelligence.md) | 策略、审批、隐私预算、FinOps |
| 22 | [可信生态网络](./22-intelligence-network-and-trust-marketplace.md) | 联邦交换、信任与市场结算 |
| 23 | [全球协调](./23-global-intelligence-coordination.md) | 协议协商、监管冲突与危机链路 |
| 24 | [自适应智能 OS](./24-adaptive-global-intelligence-os.md) | 灰度、数字孪生、治理与透明日志 |
| 25 | [可证明自治](./25-provable-autonomy-global-continuous-intelligence.md) | 约束证明、模型检查与连续性 |
| 26 | [行星级韧性](./26-planetary-intelligence-resilience.md) | 多区域复制、保险与应急资源 |
| 27 | [认知基础设施](./27-global-cognitive-infrastructure.md) | 长期治理、协议认证与可复现构建 |
| 28 | [认知公地](./28-global-cognitive-commons.md) | BFT 共识、公共财政与跨代治理 |
| 29 | [生产收敛](./29-global-production-convergence.md) | 发布门禁、恢复演练与可观测性 |

## 文档维护规则

- 产品范围变化先更新 PRD 和架构说明。
- 接口变化同步更新 OpenAPI 契约、接口文档、SDK 与弃用说明。
- 数据结构变化必须包含 Alembic upgrade/downgrade，并更新数据库设计。
- 配置变化必须同步 `backend/.env.example` 和配置指南。
- 功能完成只能表示自动化验收通过；依赖真实第三方账号的链路必须单独标明验证环境。

# InfoPulse 产品与开发文档

Stage 13: [Enterprise multi-tenancy and governance](./14-enterprise-governance.md)

Stage 14: [Open platform and ecosystem integrations](./15-open-platform.md)

Stage 15: [Agent orchestration and governed autonomy](./16-agent-orchestration.md)

Stage 20: [智能决策产品化与商业化](./20-decision-productization-commercialization.md)

Stage 21: [自治型企业情报与合规规模化](./21-autonomous-enterprise-intelligence.md)

Stage 22: [可信情报网络与生态交易规模化](./22-intelligence-network-and-trust-marketplace.md)

Stage 23: [全球情报协同与持续验证](./23-global-intelligence-coordination.md)

Stage 24: [自适应全球情报操作系统](./24-adaptive-global-intelligence-os.md)

上线相关文档：

- [生产运行手册](./06-production-runbook.md)
- [安全、隐私与数据生命周期](./07-security-privacy.md)
- [发布检查清单](./08-release-checklist.md)
- [性能基线](./09-performance-baseline.md)
- [生产部署与运维](./10-production-deployment.md)
- [SLO、错误预算与值班](./11-slo-oncall.md)
- [版本发布记录模板](./12-release-notes-template.md)

## 文档顺序

1. [重构方案](../重构方案.md)：产品定位、完整功能范围、数据源和迁移总纲。
2. [产品 PRD](./01-产品PRD.md)：页面、按钮、弹窗、状态与业务流程。
3. [UI 设计规范](./02-UI设计规范.md)：设计令牌、布局、组件、响应式和无障碍。
4. [数据库设计](./03-数据库设计.md)：表结构、字段、约束、索引、ER 图和迁移策略。
5. [接口文档](./04-接口文档.md)：REST/SSE 契约、请求响应、错误和安全要求。
6. [开发计划](./05-开发计划.md)：双周阶段、依赖、验收、测试和风险。

## 使用规则

- 产品范围变化先更新重构方案和 PRD。
- 交互变化同步更新 PRD 与 UI 规范。
- 数据字段变化先更新数据库设计，再更新接口文档和迁移。
- 接口实现以 OpenAPI 为可执行契约，本文件描述产品级约定。
- 开发阶段只有在对应验收标准满足后才能标记完成。

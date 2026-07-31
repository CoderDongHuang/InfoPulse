# 阶段 18：行动闭环与影响验证

## 目标
将预警、情景推演和决策室结论转化为可审批、可执行、可回执、可复盘的处置行动。所有影响结论必须保留测量窗口、来源证据和归因边界。

## 数据与权限
- `response_actions` 绑定 `event_id`、`scenario_id` 或 `decision_room_id` 至少一个来源，并保存负责人、SLA、预算、依赖、停止条件和证据 ID。
- `action_steps`、`action_runs`、`action_receipts` 分离执行计划、幂等运行和外部回执；同一行动的 `idempotency_key` 只能产生一个运行。
- `impact_metric_definitions` 与 `impact_measurements` 保存指标定义、前后值、观测时间、来源和归因边界，不把相关性写成因果事实。
- `action_reviews`、`anonymous_benchmarks`、`action_drills` 支持复盘、隐私安全的群体基准和无副作用演练。
- `action.read/write/approve/execute/manage` 与 `benchmark.read/manage` 遵守组织隔离；来源删除或跨租户时拒绝引用。

## 状态与安全规则
`draft -> pending_approval -> approved -> executing -> completed`，也可进入 `blocked/cancelled`。高风险行动必须由非创建者审批；执行携带幂等键；预算耗尽阻塞；外部连接器必须来自已审批平台；演练只重放快照，不产生真实外部副作用。

## API
`GET/POST /api/v1/actions`、`GET /actions/{id}`、`POST /actions/{id}/steps|approve|start|receipts|impact`、`GET /actions/{id}/impact`、`POST /impact/metrics`、`GET /action-dashboard`。

## 前端
`/action-loop` 提供行动看板、创建表单、状态/预算摘要、证据和执行步骤视图。没有真实行动或影响测量时只显示明确空状态，不生成模拟数据。

## 后续
补齐定时 SLA 升级、连接器执行 Worker、复盘/演练/匿名基准管理接口、指标图表和端到端审计测试。

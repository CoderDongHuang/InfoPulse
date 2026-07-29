# 智能自治与 Agent 编排

## 执行模型

工作流是有向无环图，必须包含一个 `start` 和至少一个 `end`。支持 `agent`、`tool`、`approval`、`condition`、`memory_read`、`memory_write` 节点。保存会创建不可变版本，正在运行的实例固定版本，不受后续编辑影响。

运行按节点提交事务，并由数据库租约领取。Worker 中断后，租约过期的 `queued` 运行可被其他实例恢复；相同组织内的幂等键只能创建一个运行。重放创建关联的新运行，不覆盖原始输入、步骤或审计记录。

## 工具与审批

工具策略默认拒绝，并限制单次运行调用次数。外部工具必须同时满足：工具启用、Workspace 策略允许、连接器安装已审批且未撤销。`high` 和 `critical` 工具无条件进入人工审批；申请人不能批准自己的操作。运行记录只保存连接器和动作，不读取或复制凭据引用。

当前连接器动作进入受控 dispatch 队列边界；真实供应商写入由持有 Vault 访问权的连接器 Worker 实现。未配置供应商账号时不会伪造成功投递。

## Prompt、模型与成本

Prompt 按 key 和版本管理，同一 key 只有一个 active 版本。模型路由按组织、Workspace 和任务类型选择 primary/fallback 模型。每个 Agent 节点在调用前检查运行预算和路由成本上限；全部批准模型失败时步骤失败，不自动切换到未批准模型。

## 记忆隔离

记忆查询始终包含组织、Workspace、用户和 namespace，可选绑定运行并设置 TTL。删除后立即清空 value 并软删除，过期或删除记录不会被运行时召回。

## 评测与发布门禁

评测集只接受受控字段，可声明禁用工具和最低得分。工作流版本必须至少有一次通过的评测才能激活。评测结果与版本绑定，旧版本通过不能授权新版本发布。

## 生产运行

使用 `python -m app.worker --role orchestration` 启动独立 Worker。Kubernetes 默认两个副本并支持扩至十个；API 生产进程必须保持 `RUN_BACKGROUND_WORKERS_IN_API=false`。告警覆盖 Worker 无可用副本，运维还应监控 queued 时长、waiting_approval 数量、失败率、租约超时和模型成本。

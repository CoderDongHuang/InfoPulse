# R14：身份唯一性、存量迁移与并发写入

日期：2026-10-14。状态：实现与本机专项验收完成；最终发布依据为独立 PR 最新 head 的完整 CI 和合并记录。

## 问题与设计

登录和服务查重采用 lower()，原数据库只有区分大小写的唯一字段。两个写入者都可以通过查重，再分别提交 Alice 和 ALICE，后续登录查询便可能匹配多账户。服务预检无法消除这一竞争窗口。

模型和迁移 `20261014_0034` 添加两个唯一表达式索引：`lower(username)` 和 `lower(email)`。保留原索引；迁移先检查两个字段的冲突，全部通过后才建索引。PostgreSQL 使用 SHARE ROW EXCLUSIVE 表锁阻止检查与建索引之间的写入，锁随迁移事务释放。downgrade 只删除新增索引，不改变账户资料。

## 升级操作

1. 备份数据库，并在隔离副本验证当前版本和升级；先安排停写维护窗口。索引创建及表锁可能阻塞写请求，大型表应另行设计在线迁移。
2. 执行 `alembic upgrade head`。如果提示 users.username 或 users.email collision，停止发布，保留旧版本运行。错误不输出具体身份值。
3. 管理员在受限数据库会话内检查 `SELECT lower(username), count(*) FROM users GROUP BY lower(username) HAVING count(*) > 1`；邮箱替换字段同理。输出含个人信息，不应贴入公共 issue 或日志。
4. 核实账户所有权，与用户协商唯一身份；使用现有管理流程逐条处理并留审计记录。不能批量删除、合并或擅自更名。重新备份并再次升级。
5. 验证版本为 `20261014_0034` 和两个新索引存在，再恢复写流量。回退使用 `alembic downgrade 20261009_0033`，但回退后大小写竞争保护会消失。

## 运行证据

实际 SQLite revision 两项测试 **2/2** 通过（0.037 秒）：带数据升级/降级/再升级、两字段大小写唯一约束、存量冲突在创建任一索引前中止、人工纠正后升级。复现：backend 隔离配置下 `python -m unittest tests.test_identity_migration -v`。

独立 PostgreSQL 16 五组检查全部通过：用户名冲突和邮箱冲突各自阻止升级，完整账户快照、Alembic 版本和两个新索引不变；人工修正后升级；实际 update_me 返回 409；两个独立 asyncpg 连接同步启动，用户名和邮箱竞争各得到一 committed、一 conflict；head → 33 → head 保持每个身份字段。原始结果保存在验收制品 `identity-uniqueness.json`。

复现：先启动隔离 `docker-compose.audit.yml` 的 postgres，然后在 backend 执行 `python -m scripts.identity_uniqueness_smoke --output ../acceptance-artifacts/identity`。脚本仅接受本地验收根库，创建随机临时库并 finally 清理，不触碰业务数据库。Release Gate 的 Python 3.10/3.11 产品环境均执行它并上传结果。

## 未覆盖范围

这是数据库 lower() 语义的唯一约束，实验使用 ASCII 大小写；SQLite、PostgreSQL、Python 的 Unicode 折叠与排序规则可能不同。跨数据库 Unicode 身份规范化、在线无阻塞迁移、账户删除及所有其他领域并发不属于本次完成范围。没有付费提供商调用。

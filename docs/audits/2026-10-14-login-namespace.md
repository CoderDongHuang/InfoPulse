# R16：历史身份数据与登录命名空间

日期：2026-10-14。状态：本项完成。[PR #77](https://github.com/CoderDongHuang/InfoPulse/pull/77) 的最新 head `92a6afd` 通过 [Release Gate 38550471530](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38550471530) 和 CodeQL 全部门禁；改指向 main 后已测试的合并提交保持不变，正常合并提交 `fd1f87a`。下载 CI 覆盖制品核对三个环境各 **238/238**、四组、每项恰一次。

旧版资料 API 接受含 @ 的用户名，可以与另一账户的邮箱相同。即使两字段各自 lower() 唯一，原登录 OR 查询仍匹配两个用户，触发 MultipleResultsFound。不能用 first() 任取一个账户，否则可能让一个身份遮蔽另一个。

登录现按输入选择单一命名空间：含 @ 查邮箱，其余查用户名。注册与新资料校验已禁止 @ 用户名；保留历史记录不自动重命名，历史账户仍可用自己的邮箱登录，再更新用户名。密码、启用状态、令牌事务与撤销机制保持。

真实文件 SQLite、ASGI HTTP 测试同时持久化邮箱所有者与同邮箱形用户名的另一账户；六种请求检查邮箱大小写/空白、普通用户名、历史账户自己的邮箱、错误密码和两种缺失身份。成功令牌的 access/refresh sub 必须是预期所有者，另一账户密码不能登录邮箱所有者。新增一项与现有认证/签发组合 **13/13** 通过（104.976 秒），无提供商调用或个人配置读取。

复现：backend 隔离环境执行 `python -m unittest tests.test_login_identity tests.test_auth tests.test_auth_issuance_transactions -v`。历史 @ 用户名登录行为变化属消除歧义的安全修正，用户应改用邮箱；数据库大小写存量重复必须先处理 R14 迁移，Unicode 跨数据库折叠仍待专项。

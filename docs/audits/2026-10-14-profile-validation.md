# R13：资料输入边界与身份冲突

日期：2026-10-14。状态：本项完成。[PR #74](https://github.com/CoderDongHuang/InfoPulse/pull/74) 的最新 head `a7e3cea` 通过 [Release Gate 38550277691](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38550277691) 和 CodeQL 全部门禁，正常合并至 main，合并提交 `3de9ace`。Windows 3.10/3.11 job 分别耗时 38 分 55 秒 / 27 分 45 秒；此前取消记录保留下文，不能替代此次通过结果。

## 缺陷与修正

资料更新原来允许显式 null、未校验邮箱，用户名没有采用注册时的清理规则。将 null 写入非空字段会产生数据库异常；带空白或 @ 的用户名可能不能通过登录入口找到。更新也未检查大小写重复身份，数据库异常可能变成 500。

- 省略字段保留原值；显式 null 返回 422；清空头像使用空字符串。
- 注册和资料更新共用用户名清理逻辑：先去两端空白，再验证 3–50 字符和禁止 @。注册的清理后过短输入同步修复。
- 更新邮箱采用 EmailStr 并转小写，最长 100 字符。头像保留原有字符串契约，本项未增加 URL 抓取。
- 更新前排除自己，检查大小写重复用户名/邮箱，返回 409；数据库 flush 唯一冲突回滚并映射为 409。不把缺失用户的 404 或提交失败改成成功。
- 注册遇到用户名和邮箱分别命中不同账户时，安全地返回冲突，不触发 MultipleResultsFound。
- 前端 ProfileUpdateRequest 独立于注册 DTO，包含头像，不再误带 password。

## 验收方法

新增 8 项回归：4 项 schema 检查和 4 项真实 ASGI HTTP/文件 SQLite 测试。HTTP 使用实际认证、JWT、路由、ORM；依赖不替 API 提交。验证 422/409 后独立连接数据不变、合法输入规范化、本人大小写更新、空 patch、清空头像、flush 竞争失败回滚。原 R12 的提交失败和可组合服务测试继续运行。

OpenAPI 审查范围仅 PUT /auth/me 的 409 和 UserUpdateRequest：optional 字段仍可省略，但 schema 不再声明 null 是可写值，email 增加 format。不能用无条件重生成替代差异审查。

## 本机结果

Windows Python 3.10 的资料校验、资料事务、认证与签发组合回归 **24/24** 通过，455.472 秒。API 契约 **354 paths**、编译和差异检查通过。前端 **25/25**、vue-tsc、Vite 与静态入口预算通过，JS raw 502,997、CSS raw 136,414 字节。沙箱内 Node 子进程出现 EPERM 后，经授权在沙箱外重跑原命令成功；没有把这一环境错误记作产品通过。

隔离配置下，在 backend 运行 `python -m unittest tests.test_profile_validation tests.test_profile_transactions tests.test_auth tests.test_auth_issuance_transactions -v`；frontend 运行 `npm test`、`npm run build`。个人配置、业务数据库与付费提供商不参与验收。

## CI 预算修正

首个 head `737fd5f` 的 [Release Gate 38542482659](https://github.com/CoderDongHuang/InfoPulse/actions/runs/38542482659) 中 Windows 3.11 通过，Windows 3.10 完整执行 229 项耗时 2616.649 秒（43.61 分钟），随后 job 在 45 分钟预算取消，契约/迁移未完整验收。取消不能当作通过，也不采用旧 head 原样重跑掩盖失败。临时将旧串行 Windows job 预算增至 60 分钟，所有依赖、回归、契约、迁移和失败传播保持；后续独立 R15 采用完整分片解决反馈时长。最终需要预算修正后最新 head 的完整门禁。

## 仍待验证

本项完成请求校验和冲突响应；并发大小写唯一性必须由下一项数据库约束和迁移验证保证。账户删除、外部存储清理、真实提供商和全部 UI 负向场景仍未完成。

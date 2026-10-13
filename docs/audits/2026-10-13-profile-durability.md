# R12：资料更新的响应前持久性

日期：2026-10-13。状态：实现、新增四项独立连接回归与关联认证 **18/18** 均通过；独立 PR 最新 head 的全量 CI 仍须通过后合并。最终合并记录以 PR 为准。

## 问题与修正

`PUT /api/v1/auth/me` 原先直接返回 `auth_service.update_user` 的结果。服务只 flush / refresh，真实网络客户端可以先收到新资料，而另一请求仍读到旧资料；最终提交失败还可能发生在成功响应之后。R08 修复了令牌签发，该路径不在其验收范围内。

API 现在先构造经 Pydantic 验证的 profile，再 `await db.commit()`，提交成功才返回。事务责任留在 API 边界；服务仍不自行 commit，以便用于上层组合事务。不存在的用户保持 404，提交异常继续传播，不返回假成功。请求、响应与 OpenAPI schema 均未改变。

## 实际测试

新增 `tests/test_profile_transactions.py` 使用真实文件 SQLite、实际 endpoint / service、ORM、JWT 与认证依赖。writer 保持打开，不调用测试端 commit，也不运行响应后的依赖清理。

1. 更新 username / email / avatar，独立 reader 立即认证并读到所有新值；原有 access token 仍有效、refresh jti 未改变、管理员和启用状态保持。
2. 仅注入 commit 失败，要求异常传播；rollback 后独立 reader 读到原资料和仍有效的会话。
3. 用户不存在时返回 404，未尝试 commit。
4. 单独调用服务时未提交；另一连接读到旧资料，随后 rollback，不把组合事务拆开。

本机 Windows Python 3.10 新增 **4/4**，与原认证、撤销、令牌签发合计 **18/18** 通过（142.729 秒）；API 契约 **354 paths** 一致，模块编译与 `git diff --check` 通过。测试入口禁用 `.env` 读取并清除 Settings 对应环境变量；数据库位于唯一临时目录，不触碰现有业务库。CI 仍需执行最新 head 的全量后端、前端、产品、容器与安全门禁。

复现：隔离配置后在 backend 执行 `python -m unittest tests.test_profile_transactions tests.test_auth_transactions tests.test_auth_issuance_transactions tests.test_auth -v`。

## 未由此解决的事项

本项是资料写入的事务专项，未改变资料字段校验或并发唯一性约束。显式 null、非法邮箱、大小写冲突等输入边界仍需单独改善。账户删除会调用知识删除服务，其数据库和外部文件有不同提交边界，不能只增加一个最终 commit 就宣称删除原子性；跨存储删除、legal hold、恢复和并发 worker 必须另立专项。其他领域事务审计也未完成。

# R08：认证令牌签发的持久性边界

日期：2026-10-13。状态：实现和本机专项测试完成；推送后必须通过最新 head 的完整 CI 才可合并。对应 [路线图](../30-open-source-roadmap.md)。

## 问题与修复范围

R05 的真实网络验收发现 logout 返回后旧令牌仍可短暂访问。继续审计发现 register、login、SSO exchange 和 refresh 同样只 flush 或执行 UPDATE，再把提交留给请求依赖的清理阶段。客户端收到成功凭据不等于另一数据库连接已经能看见它；提交失败也可能发生在响应以后。

这四个 API 现在先构造响应对象、再 `await db.commit()`，只有提交成功才返回。注册的用户、个人组织、工作区、角色及会话保持同一事务；SSO 的用户、成员关系与会话同一事务；refresh 的条件更新继续保证旧 jti 只能消费一次。服务层 `_generate_tokens` 不自行提交，避免把上层组合事务拆开。令牌签名若抛异常不会先提交不可用会话，提交若抛异常不会返回成功凭据。

没有全局修改 `get_db` 或流式依赖生命周期。租户数据库上下文使用 transaction-local 配置，贸然全局拆分事务会影响 RLS 与后续读写；按 API 成功边界修复更容易核对责任。此前 logout、Agent 和协作修复继续保留。

## 验证设计与结果

`tests/test_auth_issuance_transactions.py` 新增 8 项：四种签发路径的独立连接可见性，以及四种提交失败的原子性。测试使用真实文件 SQLite、真实密码校验/JWT、实际 endpoint 函数及生产 ORM，不用内存数据库共享连接模拟跨连接隔离。

成功路径在 writer 仍打开、没有测试端 commit、没有依赖清理时，新 reader 必须能通过实际 `get_current_user` 验证令牌；新 refresh 可立即消费，再次使用必须 401。注册同时核对租户和工作区成员，SSO 同时核对组织与 member 角色，不能授予系统管理员。失败路径仅注入 commit 错误，要求异常传播；rollback 后只有原有账户和会话，refresh jti 保持未消费。

- 新 8 项 + 原认证/撤销/企业权限回归：**19/19**，135.766 秒，Windows Python 3.10。
- 不读取个人 `.env`；测试入口禁用其加载并移除 Settings 对应环境变量。数据库在唯一临时目录创建并清理。
- SSO secret 是夹具，且只替换可信代理配置；未连接真实 OIDC/SAML 服务，不能据此声称外部 SSO 已验收。
- 原 ASGITransport HTTP 回归保留；它会等待完整应用调用和依赖清理，因此不是响应前持久性的单独证据。

复现：隔离配置后在 backend 执行 `python -m unittest tests.test_auth_issuance_transactions tests.test_auth_transactions tests.test_auth tests.test_enterprise -v`。浏览器使用隔离 PostgreSQL 服务及 `python -m scripts.product_smoke --base-url http://127.0.0.1:15173 --browser-channel msedge --output ../acceptance-artifacts/auth-issuance`。

重启隔离 PostgreSQL 16 验收 API 后，本机 Vite dev + Edge 产品 **9/9** 通过，`completed: true`，page_errors / server_errors / component_errors 均为空，原始结果为 `acceptance-artifacts/auth-issuance/result.json`。包含 UI 注册、知识入库/检索、取消无写、WS/协作、36 路由、移动端、退出撤销与重新登录；refresh/SSO 的故障边界由上述独立连接专项证明，不冒充为全部浏览器场景。

## 保留的限制

本项没有完成 SSO 身份绑定、MFA/tenant policy enforcement 的全面审计，也没有改变会话过期策略。profile update、账户删除、其他领域写 API 的事务与外部存储一致性仍待专项处理。没有更改 token schema、API 契约或数据库迁移；一次测试通过不等于所有并发和崩溃场景已覆盖。

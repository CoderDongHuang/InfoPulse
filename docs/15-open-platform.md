# 开放平台与生态集成

## 安全边界

- API Key 明文仅在创建响应中出现一次，服务端保存 SHA-256 哈希和可识别前缀。Scope 只能来自固定白名单，调用按显式组织与 Workspace 计量。
- OAuth 仅支持 OAuth 2.1 Authorization Code，强制 PKCE S256、精确回调地址、5 分钟一次性授权码。禁止 implicit、password grant 和通配回调地址。
- Webhook 签名内容为 `timestamp.event_id.raw_body`，使用 HMAC-SHA256。消费者应拒绝超过 5 分钟的请求并按事件 ID 幂等。
- 外发前重新解析域名并拒绝凭据、重定向、非 HTTPS、私网、环回、链路本地和非全局 IP。重放创建关联的新记录，不覆盖历史。
- 连接器只保存 Vault 或云密钥管理器引用。具有外部写权限的安装必须由管理员复核；撤销时清空凭据引用。
- Sandbox 不投递外部消息、不读取私有知识库、不执行生产写入。

## Scope 与 OAuth

Scope 白名单：`events:read`、`search:read`、`reports:read`、`reports:write`、`webhooks:read`、`webhooks:write`、`knowledge:read`、`agent:run`。

管理员注册应用并完成安全审查。客户端生成 `code_verifier`，提交 SHA-256 Base64URL 值作为 `code_challenge`；用户授权得到 5 分钟的一次性 code，再向 `/api/v1/platform/oauth/token` 交换令牌。机密客户端同时提交仅展示一次的 client secret。应用撤销会同步撤销全部访问授权。

## Webhook 与连接器

请求头为 `InfoPulse-Timestamp`、`InfoPulse-Event-ID`、`InfoPulse-Signature: sha256=<hex>`。投递状态包括 `queued`、`delivered`、`retrying`、`dead_letter` 和 `sandboxed`；控制台测试只渲染真实签名报文，不进行网络发送。

市场内置 Slack、Microsoft Teams、飞书、钉钉、Jira、Notion、Confluence、企业微信的协议定义。生产安装需在供应商创建真实应用，将凭据写入企业密钥管理器，再提交引用；仓库不包含或生成第三方生产凭据。

## 用量、SDK 与生产清单

计量按组织、Workspace、月份和 Scope 记录。达到套餐上限且未启用超额时返回稳定的 HTTP 429 `plan_quota_exceeded`。账单只保存外部账单引用，不存支付卡信息。

Python SDK 位于 `sdk/python`，TypeScript SDK 位于 `sdk/typescript`，均支持租户头、分页、超时、幂等键、错误解析和带时间容差的 Webhook 验签。OpenAPI 位于运行实例 `/openapi.json`，交互文档位于 `/docs`。

上线前必须配置独立 `PLATFORM_ENCRYPTION_KEY`，验证 PostgreSQL RLS，在供应商后台配置精确回调 URI，写入真实密钥引用，部署投递 Worker 与死信告警，并使用供应商账号完成授权、投递和撤销演练。

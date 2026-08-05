# 阶段 29 生产配置清单

敏感值只写入部署平台的 Secret 或未纳入 Git 的 `backend/.env`，前端公开地址写入 `frontend/.env.production`。不要把真实凭据提交到仓库。

| 配置 | 当前状态 | 获取方式 | 写入位置 |
| --- | --- | --- | --- |
| `DATABASE_URL` | 未达生产要求 | 在云数据库创建 PostgreSQL 16 实例、数据库和最小权限用户，并启用 pgvector；复制异步连接串 | Secret 或 `backend/.env` |
| `REDIS_URL` | 生产必需 | 创建启用 TLS、认证和持久化的托管 Redis，复制连接串 | Secret 或 `backend/.env` |
| `JWT_SECRET_KEY` | 未填写安全值 | 密码管理器生成至少 32 字节随机值 | Secret 或 `backend/.env` |
| `PLATFORM_ENCRYPTION_KEY` | 未填写 | KMS/密码管理器独立生成至少 32 字节值，不能与 JWT 共用 | Secret 或 `backend/.env` |
| `SSO_PROXY_SECRET` | 未填写 | 在身份代理与 InfoPulse 间生成并共享至少 32 字节签名密钥 | Secret 或 `backend/.env` |
| `ADMIN_EMAILS` | 未填写 | 由组织安全负责人确认管理员邮箱白名单 | Secret 或 `backend/.env`，JSON 数组 |
| `METRICS_TOKEN` | 未填写 | 监控平台生成只读抓取令牌，至少 24 字符 | Secret 或 `backend/.env` |
| `CORS_ORIGINS` / `TRUSTED_HOSTS` | 必需 | 部署后端和前端域名确定后填写精确域名，不允许 `*` | `backend/.env` |
| `LLM_API_KEY` / `LLM_API_BASE` / `LLM_MODEL` | AI 功能必需 | 从获批的 OpenAI 兼容模型供应商控制台创建受限项目密钥 | Secret 或 `backend/.env` |
| `SMTP_HOST` / `SMTP_FROM` / `SMTP_PASSWORD` | 未填写 | 邮件服务商创建 SMTP 凭据并验证发件域名 | Secret 或 `backend/.env` |
| `S3_ACCESS_KEY` / `S3_SECRET_KEY` | 未填写，当前为本地存储 | 创建私有桶和仅限该桶的服务账号；配置驻留区域，并设 `KNOWLEDGE_STORAGE_BACKEND=s3` | Secret 或 `backend/.env` |
| `GITHUB_TOKEN` | 未填写 | GitHub App 安装令牌或细粒度 PAT，仅授予所需仓库权限 | Secret 或 `backend/.env` |
| `WEIBO_COOKIE` / `TIEBA_COOKIE` | 可选 | 使用获授权账号登录后由浏览器开发者工具读取；遵守平台条款 | Secret 或 `backend/.env` |
| `VITE_API_BASE_URL` | 前端生产必需 | 使用公开 API 网关 HTTPS 地址 | `frontend/.env.production`，构建时注入 |
| Slack/Teams/飞书/钉钉凭据 | 未配置生产租约 | 在对应平台创建应用或机器人并获得 webhook/OAuth 凭据，将密文写入 Vault | 管理员“开发者平台”安装连接器，再在自治控制中心填写 `vault://...` 凭据引用；不写 `.env` |
| 企业 OIDC/SAML | 未配置 | 在企业 IdP 创建客户端，登记回调地址并取得 client ID/secret/issuer | 管理员“企业治理”身份提供商配置；secret 存 Vault，代理签名仍用 `SSO_PROXY_SECRET` |
| 支付、税务、保险及托管渠道 | 未接生产渠道 | 分别向获批支付服务商、税务服务、保险人和托管行申请商户/账户凭据 | 凭据存 Vault，以连接器安装和凭据租约录入；仓库当前没有对应 `.env` 字段 |

生产还必须设定 `ENVIRONMENT=production`、`AUTO_CREATE_TABLES=false`、`RUN_BACKGROUND_WORKERS_IN_API=false`，并将调度/媒体工作进程作为独立服务部署。配置后先运行 `python scripts/production_check.py`，再运行完整发布门禁。

# InfoPulse

[![Release Gate](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/release-gate.yml/badge.svg)](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/release-gate.yml)
[![CodeQL](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/codeql.yml/badge.svg)](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

InfoPulse 是一个面向公开信息研究的 AI 情报与舆情工作台。持久化资讯链路支持 Hacker News、GitHub、DEV Community、arXiv 和 RSS；兼容讨论工具另行整理微博、B站和百度贴吧的公开样本。两类采集并非同一个已统一的数据管道。

> 当前版本以可解释结果为中心：展示来源覆盖、样本数量、代表观点和事实风险，不把模型生成内容包装成已核验事实。

## 开源状态

当前**公开数据主链可供本地自托管使用（beta）**，其余模块仍按能力矩阵区分 beta、外部依赖与实验功能，不代表全项目已达到稳定 v1。2026-10-16 已实测无需密钥的 HN、GitHub、DEV、arXiv 采集，以及检索、详情、收藏、工作台、无模型日报与站内通知；默认自动周期同步，不注入演示文章。357 条 API 契约、Linux/Windows 回归、容器产品验收继续作为发布门禁。2026-10-21 审计修复与未完成验证见 [修复状态](./docs/audits/2026-10-21-remediation.md)。最新范围与证据见 [公众使用验收](./docs/audits/2026-10-16-public-use.md)、[逐项测试与合并记录](./docs/audits/2026-10-13-roadmap-progress.md) 和 [能力矩阵](./docs/32-capability-matrix.md)。真实模型/邮件等提供商、其余 worker 恢复、全部核心按钮及性能基线仍需继续验收。

本项目不承诺第三方平台接口永久可用，也不提供验证码破解、权限绕过或私有数据采集能力。生产或公网使用不属于默认开源运行边界。

## 十分钟快速启动与能力边界

按下表可以区分“打开页面即可看到的本地验收”与“需要你提供凭据后才会发生的真实服务”：

| 页面/能力 | 默认看到的内容 | 真实服务所需配置 |
| --- | --- | --- |
| 工作台、发现、来源 | 本机四个公开源的实际采集结果和来源健康状态 | 无第三方密钥；受网络、上游限流和源策略影响 |
| 日报、Agent | 有引用的规则/证据摘要，并明确标注未配置模型 | LLM API 地址、模型名和 API key 才启用模型生成 |
| 私人配置 | 空配置表单和连接测试入口 | 用户自己的 LLM/视觉/转写、SMTP 账号与授权；S3 由部署者通过服务端环境配置 |
| 邮件、对象存储、SSO/SCIM、社交讨论采集 | 能力入口或降级提示，不会伪造成功 | SMTP、S3、身份提供商，或经授权的平台 Cookie/token |

仓库截图、测试账号和本地 `.public-local` 内容只用于隔离验收，不代表线上数据。公开主链不会注入演示文章；没有凭据时，页面会显示降级、不可用或待配置状态。按 README 完成注册、登录、工作台、来源和 Agent 演示的实际 Edge 记录见[十分钟验收报告](./docs/audits/2026-10-24-open-source-readiness.md)。

## 核心功能

| 模块 | 路由 | 作用 |
| --- | --- | --- |
| 今日工作台 | `/` | 已同步内容推荐、当前用户最近报告、快捷入口与失败重试 |
| 个人中心 | `/profile` | 用户名、邮箱与本地头像裁剪上传，保存反馈与冲突提示 |
| 私人配置 | `/settings` | 自行配置模型、视觉/转录与邮件；加密保存、连接测试、密钥不回显 |
| 热点洞察 | `/insight` | 多来源采集、情绪分布、观点聚类、代表讨论 |
| 表达工作室 | `/mouthpiece` | 按场景、语气、强度和篇幅生成可发布文案 |
| 事件脉络 | `/timeline` | 将公开线索整理为带来源和可信度的时间线 |
| 热搜解读 | `/hot-search` | 持久化内容真实信号排名与 AI 背景摘要，不是 B站热榜代理 |
| 内容档案 | `/history` | 统一保存洞察、文案和时间线记录 |

仓库还包含数据源管理、统一搜索、事件聚类、报告、订阅、私有知识库、Agent 编排、多模态、企业多租户及开放平台。阶段 20-29 的部分能力是实验性规则和治理记录，不能视为真实分布式共识、形式化证明或隐私删除证明。完整索引见 [docs/README.md](./docs/README.md)。

## 界面预览

采用灰白背景、蓝色强调的顶部工作空间：常用入口直接展示，研究分析、协作与行动、平台与工具分组展开。右上角头像提供个人中心、私人配置和退出登录；小屏改用导航抽屉，原有业务路由保留。个人中心支持本地头像裁剪上传、恢复默认与密码确认删除账户；共享组织所有者须先转移所有权，法律保留或运行中处理会阻止删除。

![顶部导航与工作台](./docs/blog-assets/2026-10-15/workspace-top-navigation.png)

截图来自隔离本地验收环境，展示测试账户和测试报告，不代表真实业务或模型质量。桌面、移动端及资料保存的验收范围见 [R19](./docs/audits/2026-10-15-top-navigation-profile.md)，真实报告链路见 [R18](./docs/audits/2026-10-15-workspace-reliability.md)。旧业务页面的细节样式、所有按钮和外部服务尚需继续收敛，不将全局外壳改版等同于全站完成。

## 自己配置服务

需要 AI 或邮件时，从头像进入“私人配置”，填写自己的服务地址、模型/API Key 或 SMTP 信息，保存后测试。公开数据主链无需密钥。配置加密存储在自己运行的后端；普通账号彼此隔离，实例管理员仍掌握服务器与主密钥。升级后个人调用不再继承全局 LLM/SMTP 凭据，需在页面重新配置。完整必填项、可选项和限制见 [配置指南](./docs/29-configuration-guide.md)。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Element Plus
- 后端：FastAPI、SQLAlchemy Async、Pydantic、JWT
- 数据：PostgreSQL、Redis；本地开发可使用 SQLite
- 采集：httpx、RSS、平台 API；可选 Playwright 讨论采集
- AI：兼容 OpenAI API 协议；部分分析工具有本地降级，工作流 agent 节点缺少模型时明确失败，不伪造模型成功

## 本地开发

### 无需密钥的公开数据使用入口

先安装 Python 3.11/3.12、Node.js 22 LTS、Git 和浏览器，再克隆本仓库并进入项目目录。2026-10-24 在 Windows + Edge 的干净项目环境中，从创建虚拟环境到完成页面演示实测约 **9 分 9 秒**；运行时已预装，包下载缓存未清除，耗时受网络影响，详见[验收条件与截图](./docs/audits/2026-10-24-open-source-readiness.md)。在两个终端分别执行（依赖安装可同时进行）：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-base.txt
.\.venv\Scripts\python.exe -m scripts.public_server
```

```powershell
cd frontend
npm ci
$env:VITE_API_PROXY_TARGET = 'http://127.0.0.1:18081'
npm run dev -- --host 127.0.0.1 --port 15174 --strictPort
```

打开 [本地工作台](http://127.0.0.1:15174/)，注册账号即可使用。此入口自动迁移专用 SQLite，随机密钥、知识文件和真实采集内容保存在 `backend/.public-local/`，不读取现有 `.env`，不覆盖原开发数据库。请备份整个目录并限制访问，删除密钥会使旧会话或加密配置失效。前端使用 Vite 本地服务器，两个终端需要保持运行；不构成公网部署方案。

首次演示按以下顺序操作：

1. 登录页切到注册，创建自己的本地账号，进入工作台；再从账户菜单退出，用相同账号登录。
2. 打开「发现」，等待首次同步后刷新，查看文章；从「平台与工具 → 数据源中心」查看四个来源及同步时间。来源异常时查看网络和错误提示，不会自动填入演示文章。
3. 点击「询问 AI」，选择「总结今天 AI 行业的公开情报」并发送。未配模型时返回证据摘要；点击回答下方引用查看来源详情。

命令直接使用虚拟环境中的 Python，无需修改 PowerShell 脚本执行策略。

> 如果发现页或工作台没有内容，先检查地址：以上日常使用入口为 `15174 → 18081`。`15173 → 18080` 是浏览器验收环境，使用独立账号和测试数据库，自动采集被关闭，页面会显示「隔离验收环境」。不要把验收库、账号或密钥复制进日常环境。首次同步完成后点击「刷新内容／刷新工作台」，并到数据源中心检查真实同步状态；频道、时间范围和个人反馈也会影响可见内容。

如果仓库中已有 `frontend/.env.local`，请用上面的 `VITE_API_PROXY_TARGET` 命令覆盖旧值；该文件可能保留其他端口的个人开发配置。

首次同步通常需要几分钟，实际取决于网络；发现页默认「全部 / 本周」。来源页会显示成功、异常和同步记录，失败不补假内容。GitHub 匿名 API 可能限流；其余来源也受网络、上游服务与使用政策影响。本入口不启用浏览器讨论采集，默认没有 LLM/SMTP 凭据；媒体 worker 只处理用户提交的任务，模型能力仍需在私人配置中开通。日报使用有来源的规则汇总，站内通知无需邮件服务。

普通注册用户没有共享数据源管理权限。需要管理时，在同一后端虚拟环境执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.public_server --promote your-email@example.com
# 仅对本地已注册、启用中的账号授权；退出重新登录。
.\.venv\Scripts\python.exe -m scripts.public_server --sync-once
# 对已启用来源执行一次真实同步；有来源失败时返回非零。
```

独立 worker 部署可使用 `python -m app.worker --role sources`；同时关闭 API 内嵌 worker，避免不必要的重复抓取。`SOURCE_SYNC_ENABLED` 控制同步开关，默认轮询 30 秒，按每个来源的分钟周期判断是否到期；失败也按周期等待，不进行无限快速重试。已有开发环境的迁移与配置方式见下文。

![真实公开来源健康状态](./docs/blog-assets/2026-10-16/sources-real.png)

### 自定义开发环境

环境要求：Python 3.11/3.12、Node.js 22 LTS（使用满足 Vite engine 要求的维护补丁版本）。

1. 配置后端：

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-base.txt
python -m scripts.init_local
```

初始化命令生成唯一密钥并默认使用 SQLite，已有 `.env` 时拒绝覆盖，不需要填写任何第三方凭据。最小安装默认关闭浏览器采集和媒体 worker；需要讨论采集时设 `CRAWLER_ENABLED=true`，另行执行：

```powershell
pip install -r requirements.txt
playwright install chromium
```

2. 启动后端：

```powershell
cd backend
alembic upgrade head
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

数据库结构由 Alembic 管理。`AUTO_CREATE_TABLES` 仅用于一次性开发环境，常规开发和部署必须保持为 `false` 并执行迁移。

3. 启动前端：

```powershell
cd frontend
npm ci
npm run dev
```

打开 `http://127.0.0.1:5173`。开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

公开注册不会授予管理员。需要管理共享数据源时，先注册账号，再由本机操作者在 `backend` 执行 `python -m scripts.admin your-email@example.com`。`ADMIN_EMAILS` 不是自动注册提权入口。

后端使用其他端口时，在 `frontend/.env.local` 中设置：

```env
VITE_API_PROXY_TARGET=http://127.0.0.1:8001
```

## Docker Compose

先运行上述初始化命令，生成 `backend/.env`。浏览器无关的本机安装：

```powershell
docker compose -f docker-compose.yml -f docker-compose.local.yml up --build
```

前端为 `http://127.0.0.1:5173`，API 文档为 `http://127.0.0.1:8000/docs`。默认只绑定宿主机 loopback，启动 API 前自动执行迁移。需要完整 Chromium 采集镜像时使用 `docker compose up --build`，建议至少 4GB 可用内存。镜像下载需要能够访问容器 registry。

## 升级已有安装

先备份数据库和知识文件，停止旧 worker，再安装依赖并执行 `alembic upgrade head`，最后重启 API/worker。迁移 30-33 增加投递 outbox、知识 lease、认证会话、执行指纹和共享限流；旧令牌需要重新登录。不要在真实库执行审计脚本或 downgrade。投递状态为 `unknown` 表示可能已到达远端，必须人工核对后决定是否重放，不能盲目自动重试。

## 环境变量

| 变量 | 必需 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 是 | PostgreSQL 或 SQLite 异步连接串 |
| `REDIS_URL` | 否 | Redis 不可用时服务仍可启动 |
| `JWT_SECRET_KEY` | 是 | 至少 32 位随机字符串，生产环境必须更换 |
| `LLM_API_KEY` | 否 | 分析模块按能力降级；编排 agent 无模型时返回不可用 |
| `LLM_API_BASE` | 否 | 模型 API 基础地址 |
| `LLM_MODEL` | 否 | 模型名称 |
| `WEIBO_COOKIE` | 否 | 提升微博搜索稳定性，不得提交 Git |
| `TIEBA_COOKIE` | 否 | 提升贴吧访问稳定性，不得提交 Git |
| `BROWSER_RESTART_MB` | 否 | Chromium 进程树内存重启阈值，默认 800MB |
| `VITE_API_PROXY_TARGET` | 否 | Vite 开发代理目标，默认 `http://localhost:8000` |

## 验证

```powershell
cd backend
python -m compileall -q app tests
python -m unittest discover -s tests -v

cd ..\frontend
npm run build
npm test
```

进一步执行接口和发布检查：

```powershell
cd backend
python scripts/api_contract_check.py
python scripts/production_check.py
```

`production_check.py` 仅用于检查显式生产配置，不要求本地预览补填生产凭据。产品浏览器验收与隔离环境启动命令见 [验收报告](./docs/audits/2026-10-09-remediation.md)；这些脚本会创建测试数据，不可对真实业务库运行。

## 安全与合规

- `.env`、数据库、日志和私有插件均被 Git 与 Docker 构建上下文排除。
- 只采集公开页面，不提供验证码破解、设备指纹伪装或绕过账号权限的能力。
- 平台返回空数据、限流或验证页面时，系统会标记来源不可用并继续处理其他来源。
- AI 输出是辅助整理结果，重要事实必须回到原始链接核验。
- 本软件只是自动化信息整理工具。使用者必须遵守所在地法律、目标平台条款和数据授权范围。

详细说明见 [需求.md](./需求.md)、[架构说明书.md](./架构说明书.md) 和 [开发步骤.md](./开发步骤.md)。

## 参与和安全

- 贡献流程见 [CONTRIBUTING.md](./CONTRIBUTING.md)。
- 安全问题请按 [SECURITY.md](./SECURITY.md) 私下报告，不要公开披露漏洞细节。
- 本项目采用 [MIT License](./LICENSE)。
- 后续优化计划见 [开源优化路线图](./docs/30-open-source-roadmap.md)。
- 版本发布说明见 [v0.1.0-beta](./docs/releases/v0.1.0-beta.md)；贡献入口包含 Issue/PR 模板和 CODEOWNERS。
- 项目设计、实际启动证据与当前边界见[技术博客](./docs/blog/infopulse-open-source-engineering.md)，采集、认证、Agent 和测试重构详解见[专题索引](./docs/blog/README.md)；原长文另存历史记录。

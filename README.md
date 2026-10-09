# InfoPulse

[![Release Gate](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/release-gate.yml/badge.svg)](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/release-gate.yml)
[![CodeQL](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/codeql.yml/badge.svg)](https://github.com/CoderDongHuang/InfoPulse/actions/workflows/codeql.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](./LICENSE)

InfoPulse 是一个面向公开信息研究的 AI 情报与舆情工作台。持久化资讯链路支持 Hacker News、GitHub、DEV Community、arXiv 和 RSS；兼容讨论工具另行整理微博、B站和百度贴吧的公开样本。两类采集并非同一个已统一的数据管道。

> 当前版本以可解释结果为中心：展示来源覆盖、样本数量、代表观点和事实风险，不把模型生成内容包装成已核验事实。

## 开源状态

当前定位为**本地开发者预览**，不是功能全部完整或生产级 v1。2026-10-09 已修复认证、出站访问、回执、工作流执行和知识任务恢复等审计缺陷。GitHub CI 已通过 188 项后端测试、354 条 API 契约检查、Linux Python 3.10/3.11 产品浏览器验收，以及最小容器栈的真实构建、Nginx 上传与 WebSocket 验收。完整证据、截图、剩余边界见 [修复验收报告](./docs/audits/2026-10-09-remediation.md) 和 [能力矩阵](./docs/32-capability-matrix.md)。完整 Chromium 采集镜像与真实外部提供商仍需单独验收。

本项目不承诺第三方平台接口永久可用，也不提供验证码破解、权限绕过或私有数据采集能力。生产或公网使用不属于默认开源运行边界。

## 核心功能

| 模块 | 路由 | 作用 |
| --- | --- | --- |
| 今日工作台 | `/` | 实时讨论榜、趋势摘要、快捷入口 |
| 热点洞察 | `/insight` | 多来源采集、情绪分布、观点聚类、代表讨论 |
| 表达工作室 | `/mouthpiece` | 按场景、语气、强度和篇幅生成可发布文案 |
| 事件脉络 | `/timeline` | 将公开线索整理为带来源和可信度的时间线 |
| 热搜解读 | `/hot-search` | 持久化内容真实信号排名与 AI 背景摘要，不是 B站热榜代理 |
| 内容档案 | `/history` | 统一保存洞察、文案和时间线记录 |

仓库还包含数据源管理、统一搜索、事件聚类、报告、订阅、私有知识库、Agent 编排、多模态、企业多租户及开放平台。阶段 20-29 的部分能力是实验性规则和治理记录，不能视为真实分布式共识、形式化证明或隐私删除证明。完整索引见 [docs/README.md](./docs/README.md)。

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Element Plus
- 后端：FastAPI、SQLAlchemy Async、Pydantic、JWT
- 数据：PostgreSQL、Redis；本地开发可使用 SQLite
- 采集：httpx、RSS、平台 API；可选 Playwright 讨论采集
- AI：兼容 OpenAI API 协议；部分分析工具有本地降级，工作流 agent 节点缺少模型时明确失败，不伪造模型成功

## 本地开发

环境要求：Python 3.10/3.11、Node.js 22 LTS（使用满足 Vite engine 要求的维护补丁版本）。

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
- 项目设计与开源实践详解见 [技术博客](./docs/blog/infopulse-open-source-engineering.md)。

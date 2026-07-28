# InfoPulse

InfoPulse 是一个面向普通用户的 AI 舆情洞察工作台。它从微博、B站和百度贴吧的公开讨论中整理话题样本，并提供热点洞察、表达创作、事件脉络和热搜解读四项核心能力。

> 当前版本以可解释结果为中心：展示来源覆盖、样本数量、代表观点和事实风险，不把模型生成内容包装成已核验事实。

## 核心功能

| 模块 | 路由 | 作用 |
| --- | --- | --- |
| 今日工作台 | `/` | 实时讨论榜、趋势摘要、快捷入口 |
| 热点洞察 | `/insight` | 多来源采集、情绪分布、观点聚类、代表讨论 |
| 表达工作室 | `/mouthpiece` | 按场景、语气、强度和篇幅生成可发布文案 |
| 事件脉络 | `/timeline` | 将公开线索整理为带来源和可信度的时间线 |
| 热搜解读 | `/hot-search` | B站公开热榜与 AI 背景摘要 |
| 内容档案 | `/history` | 统一保存洞察、文案和时间线记录 |

## 技术栈

- 前端：Vue 3、TypeScript、Vite、Pinia、Element Plus
- 后端：FastAPI、SQLAlchemy Async、Pydantic、JWT
- 数据：PostgreSQL、Redis；本地开发可使用 SQLite
- 采集：httpx、Playwright；默认来源仅微博、B站、百度贴吧
- AI：兼容 OpenAI API 协议；未配置或调用失败时使用确定性本地降级

## 本地开发

环境要求：Python 3.10/3.11、Node.js 20+。

1. 配置后端：

```powershell
cd backend
Copy-Item .env.example .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
playwright install chromium
```

本地没有 PostgreSQL 时，可将 `backend/.env` 中的数据库改为：

```env
DATABASE_URL=sqlite+aiosqlite:///./infopulse.db
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
npm install
npm run dev
```

打开 `http://127.0.0.1:5173`。开发服务器会把 `/api` 代理到 `http://127.0.0.1:8000`。

后端使用其他端口时，在 `frontend/.env.local` 中设置：

```env
VITE_API_PROXY_TARGET=http://127.0.0.1:8001
```

## Docker Compose

先创建 `backend/.env`，至少修改 `JWT_SECRET_KEY`。然后在项目根目录运行：

```powershell
docker compose up --build
```

前端地址为 `http://127.0.0.1:5173`，后端接口文档为 `http://127.0.0.1:8000/docs`。完整后端镜像包含 Chromium，建议宿主机至少有 4GB 可用内存。

## 环境变量

| 变量 | 必需 | 说明 |
| --- | --- | --- |
| `DATABASE_URL` | 是 | PostgreSQL 或 SQLite 异步连接串 |
| `REDIS_URL` | 否 | Redis 不可用时服务仍可启动 |
| `JWT_SECRET_KEY` | 是 | 至少 32 位随机字符串，生产环境必须更换 |
| `LLM_API_KEY` | 否 | OpenAI 兼容 API Key；为空时走本地降级 |
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
```

## 安全与合规

- `.env`、数据库、日志和私有插件均被 Git 与 Docker 构建上下文排除。
- 只采集公开页面，不提供验证码破解、设备指纹伪装或绕过账号权限的能力。
- 平台返回空数据、限流或验证页面时，系统会标记来源不可用并继续处理其他来源。
- AI 输出是辅助整理结果，重要事实必须回到原始链接核验。
- 本软件只是自动化信息整理工具。使用者必须遵守所在地法律、目标平台条款和数据授权范围。

详细说明见 [需求.md](./需求.md)、[架构说明书.md](./架构说明书.md) 和 [开发步骤.md](./开发步骤.md)。

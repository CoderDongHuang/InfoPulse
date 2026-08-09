# InfoPulse 依赖升级政策

## 目标

依赖升级必须降低已知漏洞和维护风险，同时不能把版本号更新误当成功能完成。所有直接依赖变更都需要经过与其影响面匹配的安装、构建、测试和运行验证。

## 更新分类

| 类型 | 默认处理 | 最低验证 |
| --- | --- | --- |
| Patch | Dependabot PR，可在 CI 通过后审阅合并 | 安装、构建、完整测试 |
| Minor | Dependabot PR，检查 release notes 和弃用项 | 安装、构建、完整测试、关键 smoke test |
| Major | 不自动独立合并，建立人工迁移分支 | 兼容矩阵、迁移说明、完整测试、E2E、回滚方案 |
| 安全紧急修复 | 优先级最高，允许最小范围升级 | 漏洞复现或受影响分析、回归测试、发布说明 |

## 兼容性集合

以下依赖不能视为彼此独立的大版本升级：

- Vue、Vue Router、Pinia、TypeScript、`vue-tsc`、Vite 和 `@vitejs/plugin-vue`。
- OpenAI SDK、任何模型适配器及其 schema/streaming 调用方式。
- FastAPI、Starlette、Pydantic 和 pydantic-settings。
- SQLAlchemy、Alembic、asyncpg 和数据库驱动。

当其中一个组件发生 major 更新时，必须先列出 peer dependency、运行时 API、编译器接口和 Node/Python 支持矩阵，再在单独分支整体升级。

## Dependabot 规则

前端 TypeScript、Vue Router 以及 TypeScript SDK 的 major 更新被显式忽略。忽略不表示永久拒绝升级，而是避免 Dependabot 创建无法独立通过的 PR。维护者应按季度检查 major 版本，并建立带迁移文档的人工 PR。

## 删除未使用依赖

升级前先确认依赖是否在生产代码、测试、脚本或插件中实际导入。未使用依赖应删除，而不是为了通过自动升级同时引入整套新生态。删除后执行干净环境安装，确认没有隐式依赖。

本项目只直接使用 OpenAI Python SDK，不使用 `langchain` 或 `langchain-openai`。这两个包已从依赖清单移除，避免 LangChain 0.1、LangChain Core 1.x 与 OpenAI SDK 1.x/2.x 之间的解析冲突。

## 合并门禁

依赖 PR 必须满足：

1. lockfile 与 manifest 同步。
2. `npm ci` 或干净虚拟环境安装成功。
3. 对应应用或 SDK 构建成功。
4. 自动化测试和 API 契约通过。
5. 没有通过 `--force`、`--legacy-peer-deps` 或忽略解析错误绕过冲突。
6. major 更新包含迁移说明、破坏性变化清单和回滚方式。

## 当前三个失败 PR 的结论

- PR #37（TypeScript 7）：当前 `vue-tsc` 访问 TypeScript 已移除的 `./lib/tsc` 子路径，不能合并。
- PR #43（Vue Router 5）：要求 Pinia `^3.0.4` 或 `^4.0.2`，当前项目为 Pinia 2，不能单包升级。
- PR #44（langchain-openai 1.4）：要求 OpenAI SDK 2.45+ 和 LangChain Core 1.5+，与当前依赖冲突；项目并未使用 LangChain，因此删除无用依赖。

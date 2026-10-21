# 2026-10-21 全项目审计修复验收

本表对应 [本次审计](./2026-10-21-project-audit.md) 的 A01–A14；与 10 月 9 日同名编号无关。`[x]` 表示表内明确范围已完成，集群现场验收单独列出。旧 probes 保留修复前缺陷证据，不作为本次通过结果。

## 逐项状态

| 状态 | 编号 | 已完成范围 | 验证与限制 |
| --- | --- | --- | --- |
| [x] | A01 | 保存不可变快照并排空后续编辑；导出、离开和恢复版本等待保存；保存失败阻止离开；改写返回时保留用户新输入 | 前端真实函数回归覆盖慢请求、失败、离开和改写竞态；关闭标签页有未保存提示 |
| [x] | A02 | 禁用不可实施的 SSO/MFA 开关，API 启用请求返回 409；旧强制策略在租户入口拒绝访问 | 访问拒绝及策略更新测试通过；真实 SSO/MFA assurance 尚未实现，不能标为身份提供商验收完成 |
| [x] | A03 | SQLite 开启外键；个人租户及私有记录事务删除；共享组织、legal hold 和处理中 worker 拒绝删除；对象清理进入持久 outbox，提交后由 knowledge worker 重试 | 级联、提交失败、清理重试和运行中阻止删除回归；增加只读旧库外键检查工具。对象、备份和外部服务的合规擦除证明不在完成范围 |
| [x] | A04 | 暂停/取消约束手动重试、自动领取、执行和通知投递；取消清理未执行运行 | paused/cancelled 重试与确认恢复回归；已向外部发送的请求无法撤回 |
| [x] | A05 | 发布拆成 bootstrap、preflight、migration、canary、promote；金丝雀独立端口探测并核对镜像；回滚覆盖 web/API/全部 workers 与管理资源 | 阶段渲染、顺序与模拟 kubectl 回滚测试；真实集群演练仍待完成 |
| [x] | A06 | 增加 web Pod → API TCP 8000 的 NetworkPolicy | YAML 回归通过；真实 CNI 执行及 app 域名连通性待验收 |
| [x] | A07 | Compose/Kubernetes 补 sources/actions 独立 worker | 角色、渲染及推广清单检查通过；现场积压、重启与告警验证待完成 |
| [x] | A08 | 通过认证请求取得 Blob，再下载并释放 object URL | 前端行为测试、真实 HTTP 认证下载 200 / 匿名 401 |
| [x] | A09 | 调度周期游标不依赖运行成功；批准恢复 awaiting_confirmation；等待确认期间合并定时触发 | 终态失败后下一周期、确认后运行回归 |
| [x] | A10 | 分批读取完整时间范围，筛选后计数和稳定分页，移除发现页 500 条截断 | 第 501 条匹配与第 26 页计数回归；工作台关注流最近 500 条限制仍独立保留 |
| [x] | A11 | 统一 API route 在普通响应前提交；失败返回错误；SSE 显式提交终态，未提交内容结束时回滚 | 独立连接可见性、提交失败 500、流式显式提交及回滚回归；不是外部副作用的通用分布式事务 |
| [x] | A12 | 过期媒体 lease 扫描；仅认领阶段可重排，已开始供应商调用进入 unknown；owner fence 阻止旧 worker 发布 | 真实子进程 kill、过期恢复、无自动供应商重放及旧 owner 回归；付费提供商对账仍需人工 |
| [x] | A13 | web Ingress 显式 260m，与 Nginx/应用上传路径对应 | 清单测试通过；真实控制器临界值上传待验收 |
| [x] | A14 | README、接口设计、能力矩阵和路线图同步；根设计文档及阶段 20–29 增加历史/实验范围标识 | 保留历史日期及计数，当前契约 357 paths；文档本地链接检查独立记录 |

## 运行与测试

- 前端：87/87 行为测试、vue-tsc、Vite 生产构建及 bundle budget 通过。
- API 契约：357 paths 验证通过。
- 后端全量：Windows Python 3.12.14 最小依赖环境 318/318 通过（952.384 秒，无跳过/预期失败）；17 项审计专项另行通过。沙箱内首次运行的临时文件权限错误不作为通过证据，完整回归在获准的沙箱外环境执行。
- 媒体普通失败与审计定向回归：22/22 通过；新增真实子进程 kill 场景单独通过，离线恢复/外键检查与共享卷定向检查 3/3 通过。
- 隔离真实 HTTP：注册、认证资料、报告创建与版本保存、独立请求可见性、导出、认证下载、匿名拒绝、账户删除及会话失效共 11 项通过。使用独立临时库与本地端口，不读取私密 `.env`，不调用付费提供商。
- 临时 SQLite：空库升至 `20261021_0037`，降至 `0036`、`0013`，再升至 `0037`，外键检查无异常。
- 依赖：修复 Pillow、Vite 和 follow-redirects 公告；Pillow 13 要求 Python ≥3.11，当前支持 Python 3.11/3.12。GitHub Python/npm 漏洞门禁通过；本机 Python 3.12 的 pip check 及 pip-audit 通过（虚拟环境自带旧 pip 升至 26.2.2 后零已知漏洞）。原 Python 3.10 本机回归仅作行为补充，不能证明新依赖可在 3.10 安装。
- CI 稳定性：修复旧流式总预算测试的 40 毫秒墙钟竞态，使用受控模块时钟验证跨段预算耗尽与关闭；真实 complete 请求取消仍单独覆盖，专项 2/2 通过。
- 文档：82 份 Markdown 的 278 个本地文件链接目标全部存在；不验证远程 URL 与标题锚点。原审计 80 份/229 链接快照保留不覆盖。
- 后端全量与 GitHub 最终结果：见下方发布记录；未结束的检查不计为通过。

本机原始产物位于忽略目录 `acceptance-artifacts/`，包括后端 runner JSON、`fixes-http-smoke.json` 和服务器日志。正式回归为 `backend/tests/test_october21_fixes.py`、`backend/tests/test_deploy_release.py` 和 `frontend/tests/report-editor.test.mjs`。

## 升级与运维

升级前备份数据库、知识对象及报告导出目录。安装 Python 3.11/3.12 并重建虚拟环境，安装 requirements 后执行 `python -m alembic upgrade head`。0037 新增 storage cleanup outbox；knowledge worker 必须持续运行并监控清理行数、attempts 和 error_message。清理失败保留记录重试，不应删除 outbox 来隐藏失败。

对历史 SQLite 库先在备份副本执行：

```powershell
cd backend
python -m scripts.sqlite_integrity_check C:/backup/infopulse.db
```

该工具只读，不自动修复孤儿行。输出 `ok=false` 时先逐条核对归属与备份，再安排迁移修复，不能把启用外键视为历史孤儿已清理。

旧版曾启用强制身份策略的组织将被拒绝访问；实例操作者核对组织与所有者 UUID 后，可在受控维护环境执行：

```powershell
python -m scripts.identity_policy_recovery --organization-id ORGANIZATION_UUID --owner-id OWNER_UUID
```

工具读取实例正常数据库配置，校验组织所有者，仅关闭当前无法实施的两项要求；不授予成员资格，也不代表身份认证已完成。命令中的占位符必须替换为实际 UUID。

报告导出由 API 多副本及清理 worker 共用 `REPORT_EXPORT_PATH`。Compose 使用 `staging_exports`；Kubernetes 需先按 [PVC 示例](../../deploy/k8s/exports-pvc.example.yaml) 配置真实 RWX StorageClass，独立创建 `infopulse-exports`，确认 Bound 后发布。PVC 不随失败发布删除。旧库 ReportExport 保存的是绝对路径：迁移旧导出时必须保留可访问的旧路径挂载，或在停写/备份后复制文件并核对更新对应 storage_key；未完成前不承诺旧下载与旧导出清理成功。

发布只在 preflight 和迁移通过后更新应用。回滚恢复应用资源，不降级数据库、不回滚 Secret/PVC；迁移必须兼容旧应用，破坏性 schema 变更需独立维护方案。当前使用提交 SHA 标签，尚未实现镜像 digest 强制固定。

## 仍待现场验收

- [ ] 有真实 Kubernetes/CNI/Ingress 的环境执行 app 域名登录、查询、WS、小文件/临界值/超限上传。
- [ ] RWX 卷在多 API 副本和 knowledge worker 间的下载/删除可见性，备份与恢复演练。
- [ ] 发布各阶段故障注入、web/所有 workers 回滚和数据库向后兼容演练。
- [ ] 真实 SSO/MFA、S3、SMTP 和付费模型提供商矩阵；actions/orchestration 进程中断与其他领域带数据迁移。

本机没有可用 Kubernetes 上下文及 Docker daemon；GitHub 容器/PostgreSQL门禁与真实集群验收分别记录，不能互相替代。

## GitHub 发布记录

1. 基线与依赖安全：[PR #93](https://github.com/CoderDongHuang/InfoPulse/pull/93)，全部 CI 通过并已合并。
2. 业务与数据修复：[PR #94](https://github.com/CoderDongHuang/InfoPulse/pull/94)，全部 CI 通过并已合并；Linux 3.11、Windows 3.11/3.12 精确覆盖汇总、前端/SDK、产品浏览器、full/minimal 容器、依赖及 CodeQL 均通过。
3. 部署门禁与 worker 修复：[PR #95](https://github.com/CoderDongHuang/InfoPulse/pull/95)，独立 CI 门禁通过后合并。
4. 文档状态与最终证据：独立文档 PR，通过完整门禁后合并。PR 的最终 CI、合并时间与提交以 GitHub 状态为准。

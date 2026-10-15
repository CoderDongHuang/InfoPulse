# R18：工作台真实报告与失败恢复

日期：2026-10-15。范围是首页的数据链路，不是所有页面或全部跨域业务验收。

## 问题与修复

- [x] 后端固定返回 `recent_reports=[]`：改为当前用户、未删除、按更新时间及 ID 倒序的最近 8 条报告；不暴露正文和其他用户数据。
- [x] 前端最近报告固定空文案：改为真实列表及报告编辑器链接，只有实际为空才展示空状态。
- [x] 加载异常没有页面反馈：增加加载/失败/重试状态，失败不伪装为空数据。
- [x] 收藏/不感兴趣没有操作状态且可能重复提交：增加请求期间禁用、成功/失败提示，写入成功后刷新；刷新失败与写入失败分开处理。
- [x] 首页移除 `any`，工作台响应有明确 TypeScript 类型；这不是全站 DTO 生成完成。

## 验证

- Windows Python 3.10：`tests.test_stage3` **4/4**，29.257 秒。新增报告隔离/软删除/排序/8 条上限测试；空库和真实内容推荐回归保留。
- Node：`npm test` **29/29**；四个新增测试执行真实页面处理函数，覆盖断网重试、重复提交、写失败和写成功后刷新失败。
- `npm run build`：类型检查、生产构建和包体预算通过，静态入口 JS 502,997 字节、CSS 136,414 字节。依赖中的 PURE 注释告警不是构建失败。
- Edge 浏览器：`scripts.product_smoke` **11/11**，包括真实报告从首页进入详情、网络失败后恢复；保留注册、知识上传检索、取消无写入、协作 WS、36 路由、移动与退出撤销。`page_errors/server_errors/component_errors` 均为空。本机证据：`acceptance-artifacts/r18-product/result.json`（忽略目录）。第一次运行因页面错误区和全局 toast 同为 alert 导致测试定位歧义，限定到工作台后完整重跑通过，没有屏蔽页面错误。

## 复现方式与边界

在无个人 `.env` 的隔离测试环境：

```powershell
cd backend
python -m unittest tests.test_stage3 -v
python -m scripts.product_smoke --base-url http://127.0.0.1:15173 --browser-channel msedge --output ../acceptance-artifacts/r18-product
cd ../frontend
npm test
npm run build
```

浏览器验收仅对本地隔离服务运行，会创建随机测试账户、知识文档和报告，不得指向业务数据。本机 Docker Hub 连接失败，改用缓存 PostgreSQL 16/Redis 加本地 API/Vite；不能因此声称本机容器构建成功。容器覆盖以 PR 最新 head 的 GitHub Release Gate 为准。

首页 `tasks` 字段仍未接入任务聚合，UI 未展示虚构任务。其余页面的错误、超时和按钮矩阵，以及账户删除跨存储一致性等仍在路线图中未完成。CI 与合并状态以对应 PR 的实际结果为准，不由本地测试替代。

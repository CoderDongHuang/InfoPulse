# 2026-10-13 博客截图来源

这些 PNG 是真实本机 Edge 浏览器截图，不是生成式效果图；使用隔离 PostgreSQL 16 / Vite dev / acceptance_server，不含个人数据或生产凭据。账号名为脚本生成的 smoke fixture。

| 图片 | 原始验收目录 | 证明范围 |
| --- | --- | --- |
| knowledge-desktop.png | acceptance-artifacts/dialogs-revocation | 固定大文件入库与引用检索页面 |
| knowledge-cancellation.png | acceptance-artifacts/dialogs-revocation | 取消后的文档状态；无写入由脚本网络断言证明 |
| knowledge-mobile.png | acceptance-artifacts/dialogs-revocation | 当前移动视口布局，不是全部无障碍验收 |
| components-desktop.png | acceptance-artifacts/dialogs-revocation | 筛选、loading、取消确认测试后的页面 |
| action-step-table.png | acceptance-artifacts/action-table | 两条 GET 展示 fixture 的非空表格；不是实际行动执行证明 |

前四张所属执行结果 9/9，最后一张所属执行结果 10/10；均 completed=true 且 page_errors/server_errors/component_errors 为空。截图保留原始文件未加工。读者不应把画面中的检索分数、状态 fixture 或日期当作外部业务结果。

# 2026-10-15 产品截图来源

这些 PNG 由仓库的 `backend/scripts/product_smoke.py` 和 `ui_shell_smoke.py` 在隔离本地 PostgreSQL/API/Vite/Edge 环境生成，并人工目视检查。不是设计稿或 AI 生成图片，没有读取个人数据或真实第三方模型输出。

| 文件 | 内容 | 视口宽度 |
| --- | --- | ---: |
| workspace-top-navigation.png | 顶部导航、工作台及测试最近报告 | 1440px |
| profile-desktop.png | 个人中心双栏资料表单 | 1440px |
| avatar-menu.png | 右上角个人中心/退出登录菜单 | 1440px |
| workspace-mobile.png | 小屏工作台与抽屉触发器 | 390px |
| profile-mobile.png | 最窄验收宽度的单栏个人中心 | 320px |

账户名、邮箱、日期和报告均为可重复验收产生的随机 fixture；报告标题不代表模型生成或真实研究成果。截图时只将有限 CSS 动画推进至终态，不改变业务 API、不伪造保存成功，交互断言阶段保留正常动效。重新验收生成的随机账户和截图时间可能不同，不能以像素完全相同作为业务通过条件。

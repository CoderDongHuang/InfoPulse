# 第三方爬虫插件目录

InfoPulse 主产品只注册微博、B站和百度贴吧。本目录用于私有部署中的自定义数据源，不会自动出现在产品界面。

## 如何添加数据源

1. 实现 `BaseCrawler` 接口，并确认数据来源授权与平台条款
2. 将适配器放入本目录
3. 在私有部署的爬虫注册表中显式注册
4. 重启服务

```python
from app.services.crawler.plugins.custom_source import CustomSourceCrawler
from app.services.crawler import CRAWLER_REGISTRY

CRAWLER_REGISTRY["custom_source"] = CustomSourceCrawler
```

## 开发新插件

所有插件必须实现 `BaseCrawler` 接口（见 `crawler/base.py`）：

```python
from app.services.crawler.base import BaseCrawler, RawPost, RawComment

class MyCrawler(BaseCrawler):
    platform_name = "my_platform"

    def is_available(self) -> bool: ...

    async def search(self, keyword, max_items) -> List[RawPost]: ...

    async def get_comments(self, post_id, max_items) -> List[RawComment]: ...
```

## ⚠️ 重要提示

- 本框架不对任何第三方插件的合法性负责
- 请在使用前确认你遵守了目标平台的 `robots.txt` 和服务条款
- 插件代码的授权、维护和安全由插件作者独立负责
- 本项目的 MIT 协议**不覆盖**本目录中的第三方插件
- 请勿把 Cookie、签名参数或其他账号凭证提交到 Git

# URL Parser Plugin

URL 内容解析插件，为 Neo-MoFox 提供可扩展的多引擎 URL 解析能力。

## 功能特性

### 🔗 多引擎可扩展架构

后端解析引擎基于抽象基类 `BaseParseEngine`，新增引擎只需继承实现，不改上层逻辑。

| 引擎 | 类型 | 特点 | 状态 |
|------|------|------|------|
| **Crawl4AI** | 渲染型 | 基于 Playwright，支持 JS 渲染，输出 Markdown | ✅ 首个内置 |
| **httpx** | 轻量型 | 基于 httpx+BeautifulSoup，无浏览器依赖，快速 | 🔜 可选内置 |
| 自定义引擎 | — | 继承 `BaseParseEngine` 即可接入 | 🔧 可扩展 |

### 🎯 站点级路由

支持为特定网站指定解析引擎及参数：

- **域名匹配**：按域名精确匹配（如 `github.com`）
- **正则匹配**：用正则表达式匹配完整 URL（如知乎问答页）
- **优先级排序**：多条规则按 `priority` 降序匹配
- **参数透传**：规则可指定 CSS 选择器、JS 执行等引擎参数

### 🛠️ 双组件暴露

| 组件 | 签名 | 用途 |
|------|------|------|
| **Tool** | `url_parser:tool:parse_url` | 供 LLM 自动调用，返回格式化文本 |
| **Service** | `url_parser:service:url_parse` | 供其他插件程序化调用，返回结构化数据 |

### 📋 引擎有序回退

- 站点规则未命中时，按全局 `engine_order` 列表顺序回退尝试
- 站点规则引擎不可用时，自动降级到全局回退
- 单个引擎解析失败不影响其他引擎尝试

---

## 安装

### 1. 依赖安装

Crawl4AI 引擎需要 Playwright 浏览器环境：

```bash
# 安装 Python 依赖
uv add crawl4ai

# 安装 Playwright 浏览器
crawl4ai-install
```

### 2. 启用插件

在插件配置目录中编辑 `url_parser/config.toml`：

```toml
[plugin]
enabled = true

[components]
enable_url_parser_tool = true       # 启用 Tool 组件（供 LLM 调用）
enable_url_parser_service = true    # 启用 Service 组件（供插件调用）
```

---

## 配置

### 引擎全局配置

```toml
[engines]
# 引擎使用顺序（从前到后依次尝试）
# 站点规则未命中时，按此顺序回退
engine_order = ["crawl4ai"]

# 默认超时时间（秒）
default_timeout = 30

# 内容最大长度（字符数），超出截断
max_content_length = 8000
```

> `engine_order` 同时隐含了「启用列表」语义：不在列表中的引擎不会被使用。

### Crawl4AI 引擎配置

```toml
[crawl4ai]
# 浏览器配置
headless = true
viewport_width = 1280
viewport_height = 720

# 页面交互配置
page_timeout = 60000                    # 页面超时（毫秒）
wait_for = ""                           # 等待条件，如 "css:.content-loaded"
delay_before_return_html = 0.0          # 抓取前延迟（秒）

# 内容过滤
content_filter_threshold = 0.6          # PruningContentFilter 阈值 (0.0-1.0)
remove_overlay_elements = true          # 移除弹窗/遮罩

# 是否启用 JS 执行
enable_js = false
```

### 代理配置（可选）

```toml
[proxy]
enable_proxy = false
http_proxy = ""
https_proxy = ""
socks5_proxy = ""
```

### 站点路由规则

使用 TOML 数组表定义多条规则：

```toml
# 知乎问答页 — 正则匹配，指定 CSS 选择器
[[site_rules.rules]]
name = "zhihu_question"
match_type = "regex"
match_pattern = 'https?://(www\.)?zhihu\.com/question/\d+'
engine = "crawl4ai"
css_selector = ".QuestionHeader-main, .RichContent-inner"
priority = 10

# GitHub 仓库页 — 域名匹配
[[site_rules.rules]]
name = "github_repo"
match_type = "domain"
match_pattern = "github.com"
engine = "crawl4ai"
css_selector = "main"
priority = 5

# 微博 — 正则匹配，启用 JS 渲染
[[site_rules.rules]]
name = "weibo"
match_type = "regex"
match_pattern = 'https?://(www\.)?weibo\.com/.+'
engine = "crawl4ai"
priority = 8

[site_rules.rules.extra_options]
enable_js = true
wait_for = "css:.Feed"
```

#### 规则字段说明

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `name` | `str` | ✅ | 规则名称（用于日志） |
| `match_type` | `str` | ✅ | `"domain"` 或 `"regex"` |
| `match_pattern` | `str` | ✅ | 域名或正则表达式 |
| `engine` | `str` | ✅ | 使用的引擎名称 |
| `css_selector` | `str` | ❌ | CSS 选择器，提取页面特定区域 |
| `extra_options` | `dict` | ❌ | 引擎特定额外选项 |
| `priority` | `int` | ❌ | 优先级，数值越大越优先（默认 0） |

---

## 使用方法

### Tool 组件

Tool 组件会自动注册到 LLM 可用工具列表。当用户发送网页链接时，LLM 会自动调用：

```
用户: 帮我看看这个网页讲了什么 https://example.com/article
LLM:  [自动调用 parse_url 工具]
LLM:  这个网页的内容是...
```

Tool 始终返回完整内容，由配置项 `engines.max_content_length` 控制截断长度。

### Service 组件

在其他插件中调用解析服务：

```python
from src.core.managers import get_service_manager

# 获取服务
service_manager = get_service_manager()
parse_service = service_manager.get_service("url_parser:service:url_parse")

# 解析单个 URL
response = await parse_service.parse("https://example.com")
print(response.title)
print(response.content)
print(response.engine_used)    # 实际使用的引擎
print(response.rule_matched)   # 命中的站点规则（无则为 None）

# 强制指定引擎
response = await parse_service.parse(
    "https://example.com",
    engine="crawl4ai",
    css_selector="#main-content",
    timeout=60,
)

# 批量解析
responses = await parse_service.parse_batch([
    "https://example.com",
    "https://example.org",
])

# 检查可用引擎
available = await parse_service.get_available_engines()
print(f"可用引擎: {available}")
```

---

## API 参考

### URLParseService

#### `parse(url, *, engine=None, css_selector=None, timeout=None)`

解析单个 URL。

**参数：**
- `url` (str): 要解析的 URL
- `engine` (str | None): 强制指定引擎，None 则走站点路由 + 全局回退
- `css_selector` (str | None): CSS 选择器覆盖
- `timeout` (int | None): 超时覆盖（秒）

**返回：** `ParseResponse`

#### `parse_batch(urls, *, engine=None)`

批量解析多个 URL（并发执行）。

**返回：** `list[ParseResponse]`

#### `get_available_engines()`

获取当前可用的引擎列表。

**返回：** `list[str]`

#### `get_engine_status(engine_name)`

获取指定引擎的状态信息。

**返回：** `dict`

### ParseResponse 字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `url` | `str` | 原始请求 URL |
| `title` | `str` | 页面标题 |
| `content` | `str` | 正文内容（已按 `max_content_length` 截断） |
| `content_format` | `str` | 内容格式（`markdown` / `html` / `text`） |
| `engine_used` | `str` | 实际使用的引擎名称 |
| `rule_matched` | `str \| None` | 命中的站点规则名称 |
| `metadata` | `dict` | 元数据 |
| `success` | `bool` | 是否成功 |
| `error` | `str \| None` | 错误信息 |

---

## 引擎选择优先级

当请求解析一个 URL 时，引擎选择的完整优先级：

```
1. 站点规则匹配
   ├─ 有匹配 → 使用规则指定的引擎 + 规则参数
   │           └─ 该引擎不可用？→ 降级到步骤 2
   └─ 无匹配 → 步骤 2

2. 全局引擎顺序回退
   └─ 按 config.engines.engine_order 列表顺序尝试
      ├─ 引擎可用 → 使用
      └─ 引擎不可用 → 尝试下一个

3. 所有引擎均不可用 → 返回错误
```

---

## 开发指南

### 添加新解析引擎

1. 在 `engines/` 目录创建新文件
2. 继承 `BaseParseEngine`，实现 `parse()` 和 `is_available()`
3. 在 `ParseManager.__init__()` 中注册引擎实例
4. 在 `config.py` 中添加引擎专属配置节
5. 在 `manifest.json` 的 `python_dependencies` 中添加依赖

```python
# engines/my_engine.py
from .base import BaseParseEngine, ParseResult

class MyEngine(BaseParseEngine):
    """自定义解析引擎。"""

    engine_name = "my_engine"

    def is_available(self) -> bool:
        # 检查依赖是否可用
        return True

    async def parse(self, url, *, css_selector=None, timeout=None, extra_options=None):
        # 实现解析逻辑
        ...
        return ParseResult(
            url=url,
            title=...,
            content=...,
            engine=self.engine_name,
        )
```

```python
# managers/parse_manager.py — 注册引擎
from ..engines.my_engine import MyEngine

self.engines["my_engine"] = MyEngine(self.config)
```

### 添加站点规则

无需修改代码，只需在配置文件中添加规则：

```toml
[[site_rules.rules]]
name = "my_site"
match_type = "regex"
match_pattern = 'https?://my-site\.com/.+'
engine = "crawl4ai"
css_selector = "#main-content"
priority = 15
```

配置热重载后规则立即生效。

---

## 故障排除

### 常见问题

**Q: Crawl4AI 引擎不可用？**
- 确认已安装 `crawl4ai` Python 包
- 运行 `crawl4ai-install` 安装 Playwright 浏览器
- 检查系统是否支持无头浏览器运行

**Q: 解析结果内容为空？**
- 检查目标页面是否需要 JS 渲染（配置 `enable_js = true`）
- 尝试添加 `wait_for` 等待条件
- 查看日志了解具体错误

**Q: 站点规则不生效？**
- 确认 `match_pattern` 正则表达式正确
- 检查 `priority` 值是否足够高
- 查看日志中的规则匹配记录

**Q: 代理无法使用？**
- 确认代理地址格式正确
- 测试代理连接是否正常

---

## 目录结构

```
url_parser/
├── manifest.json                    # 插件元数据
├── plugin.py                        # 插件入口
├── config.py                        # 配置类
├── components/                      # 组件层
│   ├── tools/
│   │   └── url_parser.py            # LLM Tool 组件
│   └── services/
│       └── url_parse_service.py     # 插件间 Service 组件
├── engines/                         # 引擎层
│   ├── base.py                      # 引擎抽象基类
│   └── crawl4ai_engine.py           # Crawl4AI 引擎
├── managers/                        # 管理器层
│   └── parse_manager.py             # 解析管理器
├── utils/                           # 工具函数
│   ├── url_utils.py
│   ├── site_matcher.py
│   └── formatters.py
└── examples/
    └── usage.py
```

详细设计请参阅 [DESIGN.md](DESIGN.md)。

---

## 更新日志

### 1.0.0
- ✨ 初始版本
- 🔗 Crawl4AI 引擎支持
- 🎯 站点级路由（域名/正则匹配）
- 📋 引擎有序回退
- 🛠️ Tool + Service 双组件

## 许可证

GPL-3.0

## 相关链接

- [Neo-MoFox 官网](https://github.com/MoFox-Studio/Neo-MoFox)
- [Crawl4AI 文档](https://docs.crawl4ai.com/)
- [插件开发文档](https://docs.mofox-sama.com/docs/development/)

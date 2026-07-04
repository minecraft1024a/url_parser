# URL Parser 插件技术设计文档

> URL Parser 是一个独立的 URL 内容解析插件，提供可扩展的多引擎解析架构，
> 支持按站点/正则路由到不同解析引擎，首个内置引擎为 Crawl4AI。

---

## 目录

- [1. 项目概述](#1-项目概述)
- [2. 整体架构](#2-整体架构)
- [3. 目录结构](#3-目录结构)
- [4. 引擎系统设计](#4-引擎系统设计)
- [5. 站点路由设计](#5-站点路由设计)
- [6. 配置设计](#6-配置设计)
- [7. 数据模型](#7-数据模型)
- [8. 组件 API 设计](#8-组件-api-设计)
- [9. 解析流程详解](#9-解析流程详解)
- [10. 扩展指南](#10-扩展指南)
- [11. 实现计划](#11-实现计划)

---

## 1. 项目概述

### 1.1 设计目标

| 目标 | 说明 |
|---|---|
| **多引擎可扩展** | 后端解析引擎基于抽象基类，新增引擎只需继承实现，不改上层逻辑 |
| **站点级路由** | 支持按域名精确匹配或正则表达式匹配 URL，为特定站点指定引擎及参数 |
| **引擎有序回退** | 全局配置引擎启用列表与使用顺序，无站点规则时按序回退尝试 |
| **双组件暴露** | 同时提供 Tool（供 LLM 调用）和 Service（供其他插件调用） |
| **与 web_search_tool 解耦** | 独立插件，不依赖 web_search_tool，职责单一 |

### 1.2 与现有 web_search_tool 的关系

`web_search_tool` 插件内部已有简单的 URL 解析能力（基于 Exa API + httpx 本地回退），
但存在以下局限：

- 解析逻辑硬编码在 Tool 内部，不可复用、不可扩展
- 无引擎抽象，无法替换为 Crawl4AI 等更强的渲染型引擎
- 无站点级路由能力

本插件作为**独立的、专用的 URL 解析方案**，解决以上问题。
`web_search_tool` 的 URL 解析功能可保留作为搜索结果的附属性能，
本插件则专注于「给定一个 URL，提取其结构化内容」这一单一职责。

### 1.3 技术栈

| 层 | 技术 |
|---|---|
| 插件框架 | Neo-MoFox 插件系统（`BasePlugin` / `BaseTool` / `BaseService` / `BaseConfig`） |
| 首个引擎 | Crawl4AI（基于 Playwright 的异步渲染型爬虫） |
| Python | >= 3.11 |
| 依赖管理 | uv |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                      调用方                              │
│         (LLM via Tool / 其他插件 via Service)            │
└────────────┬────────────────────────┬───────────────────┘
             │                        │
             ▼                        ▼
   ┌─────────────────┐     ┌─────────────────────┐
   │  URLParserTool   │     │ URLParseService      │
   │  (LLM Tool)      │     │ (插件间 Service)     │
   └────────┬─────────┘     └──────────┬──────────┘
            │                          │
            └──────────┬───────────────┘
                       ▼
            ┌──────────────────────┐
            │   ParseManager       │
            │   (解析管理器)        │
            │                      │
            │  1. 站点规则匹配      │
            │  2. 引擎选择与排序    │
            │  3. 引擎调用与回退    │
            │  4. 结果聚合          │
            └──────────┬───────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ Engine A │ │ Engine B │ │ Engine C │
   │Crawl4AI  │ │ (未来)   │ │ (未来)   │
   └──────────┘ └──────────┘ └──────────┘
```

### 2.1 分层职责

| 层 | 组件 | 职责 |
|---|---|---|
| **工具层** | `components/tools/URLParserTool` | 供 LLM 调用，接收 URL，返回格式化文本 |
| **服务层** | `components/services/URLParseService` | 供其他插件调用，返回结构化数据 |
| **管理器层** | `managers/ParseManager` | 核心调度：站点匹配、引擎排序、回退策略、结果聚合 |
| **引擎层** | `engines/BaseParseEngine` + 各实现 | 单一职责：给定 URL + 参数，返回解析结果 |
| **工具函数层** | `utils/` | URL 校验、站点匹配、结果格式化 |

### 2.2 设计原则

1. **引擎无状态**：引擎实例不缓存单次请求的中间状态，每次 `parse()` 调用独立
2. **管理器有状态**：管理器持有引擎实例字典和编译后的站点规则，在插件加载时初始化
3. **配置驱动**：引擎启用、顺序、站点规则全部由配置文件控制，代码不硬编码
4. **渐进降级**：站点规则引擎不可用时，回退到全局引擎顺序，而非直接失败

---

## 3. 目录结构

```
url_parser/
├── manifest.json                    # 插件元数据
├── plugin.py                        # 插件入口（BasePlugin 子类）
├── config.py                        # 配置类（UrlParserConfig）
├── components/                      # 组件层：向框架注册的组件
│   ├── __init__.py
│   ├── tools/
│   │   ├── __init__.py
│   │   └── url_parser.py            # URLParserTool 工具组件
│   └── services/
│       ├── __init__.py
│       └── url_parse_service.py     # URLParseService 服务组件
├── engines/
│   ├── __init__.py
│   ├── base.py                      # BaseParseEngine 抽象基类
│   ├── crawl4ai_engine.py           # Crawl4AI 引擎实现
│   └── httpx_engine.py             # httpx+BeautifulSoup 轻量引擎（可选内置）
├── managers/
│   ├── __init__.py
│   └── parse_manager.py             # ParseManager 解析管理器
├── utils/
│   ├── __init__.py
│   ├── url_utils.py                 # URL 校验与提取
│   ├── site_matcher.py              # 站点规则匹配引擎
│   └── formatters.py                # 结果格式化
└── examples/
    └── usage.py                     # 使用示例
```

> 目录命名遵循 Neo-MoFox 插件规范：使用相对导入，禁止 `plugins.url_parser...` 绝对路径。
> `components/` 下按组件类型分子目录，与框架注册的组件类型（tool/service）一一对应。

---

## 4. 引擎系统设计

### 4.1 引擎基类接口

`BaseParseEngine` 定义所有解析引擎的统一契约：

```python
"""URL 解析引擎基类。"""

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import UrlParserConfig


class ParseResult:
    """引擎统一返回的解析结果。"""

    def __init__(
        self,
        url: str,
        title: str,
        content: str,
        content_format: str = "markdown",
        metadata: dict[str, Any] | None = None,
        engine: str = "",
        success: bool = True,
        error: str | None = None,
    ) -> None:
        self.url = url
        self.title = title
        self.content = content
        self.content_format = content_format  # "markdown" | "html" | "text"
        self.metadata = metadata or {}
        self.engine = engine
        self.success = success
        self.error = error


class BaseParseEngine(ABC):
    """URL 解析引擎抽象基类。

    所有引擎必须继承此类并实现 parse() 和 is_available()。
    引擎实例应在构造时接收配置对象，运行时无状态。
    """

    # 引擎名称标识，必须与配置中的引擎名一致
    engine_name: str = ""

    def __init__(self, config: "UrlParserConfig | None" = None) -> None:
        """初始化引擎。

        Args:
            config: 插件配置对象，引擎可从中读取自身专属配置节
        """
        self.config = config

    @abstractmethod
    async def parse(
        self,
        url: str,
        *,
        css_selector: str | None = None,
        timeout: int | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ParseResult:
        """解析单个 URL，返回结构化结果。

        Args:
            url: 要解析的 URL
            css_selector: CSS 选择器，用于提取页面特定区域（可选）
            timeout: 超时时间（秒），None 使用引擎默认值
            extra_options: 引擎特定选项（可选），由站点规则或调用方传入

        Returns:
            ParseResult: 解析结果对象
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查引擎是否可用（依赖已安装、配置已就绪）。

        Returns:
            bool: 是否可用
        """
        ...

    async def close(self) -> None:
        """释放引擎持有的资源（如浏览器实例、连接池）。

        默认空实现，有资源管理的引擎应重写。
        """
        pass
```

### 4.2 引擎注册机制

引擎不使用动态注册，而是在 `ParseManager.__init__()` 中**显式实例化**并注册到字典：

```python
# managers/parse_manager.py 中的注册逻辑
from ..engines.crawl4ai_engine import Crawl4AIEngine
from ..engines.httpx_engine import HttpxEngine

self.engines: dict[str, BaseParseEngine] = {
    "crawl4ai": Crawl4AIEngine(self.config),
    "httpx": HttpxEngine(self.config),
}
```

> **设计决策**：参考 `web_search_tool` 的做法，采用显式实例化而非动态扫描。
> 原因：Neo-MoFox 的 `manifest.include` 是声明清单，组件注册以 `get_components()` 为准；
> 引擎不是独立组件（不向框架注册），而是插件内部管理器的私有资源。

### 4.3 Crawl4AI 引擎设计

`Crawl4AIEngine` 是首个内置引擎，基于 [Crawl4AI](https://docs.crawl4ai.com/) 库。

#### 4.3.1 核心特性映射

| Crawl4AI 能力 | 引擎中的用途 |
|---|---|
| `AsyncWebCrawler` | 异步爬取主入口 |
| `BrowserConfig` | 浏览器配置（headless、代理、视口） |
| `CrawlerRunConfig` | 单次运行配置（CSS 选择器、等待条件、JS 执行） |
| `result.markdown` | 主输出内容（Markdown 格式） |
| `result.metadata` | 页面元数据（标题等） |
| `PruningContentFilter` | 内容过滤，去除噪音 |

#### 4.3.2 引擎配置读取

引擎从 `UrlParserConfig` 读取 `crawl4ai` 配置节：

| 配置项 | Crawl4AI 映射 | 默认值 |
|---|---|---|
| `headless` | `BrowserConfig(headless=...)` | `True` |
| `viewport_width` | `BrowserConfig(viewport_width=...)` | `1280` |
| `viewport_height` | `BrowserConfig(viewport_height=...)` | `720` |
| `page_timeout` | `CrawlerRunConfig(page_timeout=...)` | `60000` (ms) |
| `wait_for` | `CrawlerRunConfig(wait_for=...)` | `None` |
| `delay_before_return_html` | `CrawlerRunConfig(delay_before_return_html=...)` | `0.0` |
| `content_filter_threshold` | `PruningContentFilter(threshold=...)` | `0.6` |
| `remove_overlay_elements` | `CrawlerRunConfig(remove_overlay_elements=...)` | `True` |

#### 4.3.3 浏览器实例管理

Crawl4AI 的 `AsyncWebCrawler` 基于 Playwright，启动浏览器有开销。设计策略：

- **懒初始化**：首次 `parse()` 时创建 `AsyncWebCrawler` 实例
- **上下文管理**：使用 `async with` 管理生命周期
- **单例复用**：引擎内部持有单一 crawler 实例，复用于多次解析
- **插件卸载时清理**：`ParseManager` 在插件卸载钩子中调用 `engine.close()`

```python
class Crawl4AIEngine(BaseParseEngine):
    engine_name = "crawl4ai"

    def __init__(self, config):
        super().__init__(config)
        self._crawler = None  # 懒初始化

    async def _get_crawler(self):
        if self._crawler is None:
            from crawl4ai import AsyncWebCrawler
            browser_config = self._build_browser_config()
            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.start()
        return self._crawler

    async def close(self):
        if self._crawler:
            await self._crawler.close()
            self._crawler = None
```

### 4.4 httpx 轻量引擎（可选内置）

作为 Crawl4AI 的轻量回退方案，无需浏览器环境：

- 基于 `httpx` + `BeautifulSoup`
- 适用于静态 HTML 页面
- 资源占用低，启动快
- 无法处理 JavaScript 渲染的动态内容

> 是否内置取决于实现阶段评估。若 Crawl4AI 在无头浏览器环境下安装复杂，
> httpx 引擎可作为「零依赖回退」保证基本可用性。

---

## 5. 站点路由设计

### 5.1 路由规则模型

每条站点规则定义「如何为匹配的 URL 选择引擎及参数」：

```python
class SiteRule:
    """站点路由规则。"""

    def __init__(
        self,
        name: str,               # 规则名称（用于日志和调试）
        match_type: str,         # "domain" | "regex"
        match_pattern: str,      # 域名或正则表达式
        engine: str,             # 使用的引擎名称
        css_selector: str | None = None,       # 引擎参数：CSS 选择器
        extra_options: dict | None = None,     # 引擎参数：额外选项
        priority: int = 0,       # 优先级，数值越大越优先匹配
    ) -> None:
        ...
```

### 5.2 匹配逻辑

`SiteMatcher` 负责将 URL 匹配到站点规则：

```
输入: url = "https://www.zhihu.com/question/123456"

规则表（按 priority 降序）:
  [
    { name: "zhihu", match_type: "regex",
      match_pattern: r"https?://(www\.)?zhihu\.com/.+",
      engine: "crawl4ai", css_selector: ".QuestionHeader-main" },
    { name: "github", match_type: "domain",
      match_pattern: "github.com",
      engine: "crawl4ai", css_selector: "main" },
  ]

匹配过程:
  1. 提取 url 的域名和完整字符串
  2. 按 priority 降序遍历规则
  3. domain 类型: 比较 url 域名是否等于或以 match_pattern 结尾
  4. regex 类型: 用 re.search 匹配完整 url
  5. 返回第一个匹配的规则，无匹配返回 None
```

### 5.3 匹配优先级总览

当用户请求解析一个 URL 时，引擎选择的完整优先级：

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

### 5.4 规则编译与缓存

- 站点规则在 `ParseManager` 初始化时编译（正则预编译）
- 规则列表按 `priority` 降序排序后缓存
- 配置热重载时重新编译

---

## 6. 配置设计

### 6.1 配置结构概览

`UrlParserConfig` 继承 `BaseConfig`，包含以下配置节：

| 配置节 | 说明 |
|---|---|
| `plugin` | 插件基本信息 |
| `components` | 组件启用开关 |
| `engines` | 引擎全局配置（启用列表、顺序、超时） |
| `crawl4ai` | Crawl4AI 引擎专属配置 |
| `httpx` | httpx 引擎专属配置（若内置） |
| `proxy` | 代理配置 |
| `site_rules` | 站点路由规则列表 |

### 6.2 配置节详细定义

#### 6.2.1 `[plugin]` 节

```toml
[plugin]
enabled = true
version = "1.0.0"
```

#### 6.2.2 `[components]` 节

控制 Tool 和 Service 组件的启用：

```toml
[components]
enable_url_parser_tool = true       # 启用 LLM Tool 组件
enable_url_parser_service = true    # 启用插件间 Service 组件
```

#### 6.2.3 `[engines]` 节 — 引擎全局配置

```toml
[engines]
# 引擎使用顺序（从前到后依次尝试）
# 站点规则未命中时，按此顺序回退
engine_order = ["crawl4ai", "httpx"]

# 默认超时时间（秒），引擎未单独指定时使用
default_timeout = 30

# 内容最大长度（字符数），超出截断
max_content_length = 8000
```

> `engine_order` 同时隐含了「启用列表」语义：不在列表中的引擎不会被使用。

#### 6.2.4 `[crawl4ai]` 节 — Crawl4AI 引擎专属配置

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

# 用户代理（空则使用默认）
user_agent = ""

# 是否启用 JS 执行
enable_js = false
js_code = []                            # 自定义 JS 代码列表
```

#### 6.2.5 `[httpx]` 节 — httpx 引擎专属配置（若内置）

```toml
[httpx]
# 请求超时（秒）
timeout = 15

# 是否跟随重定向
follow_redirects = true

# 请求头
user_agent = "Mozilla/5.0 (compatible; UrlParser/1.0)"

# 内容最大长度（字符数），仅对该引擎生效
max_content_length = 5000
```

#### 6.2.6 `[proxy]` 节 — 代理配置

```toml
[proxy]
enable_proxy = false
http_proxy = ""
https_proxy = ""
socks5_proxy = ""
```

> 代理配置对 Crawl4AI 和 httpx 引擎均生效。Crawl4AI 通过 `BrowserConfig(proxy_config=...)` 传入。

#### 6.2.7 `[site_rules]` 节 — 站点路由规则

使用 TOML 数组表定义多条规则：

```toml
# 知乎问答页 — 使用正则匹配，指定 CSS 选择器
[[site_rules.rules]]
name = "zhihu_question"
match_type = "regex"
match_pattern = 'https?://(www\.)?zhihu\.com/question/\d+'
engine = "crawl4ai"
css_selector = ".QuestionHeader-main, .RichContent-inner"
priority = 10

# GitHub 仓库页 — 使用域名匹配
[[site_rules.rules]]
name = "github_repo"
match_type = "domain"
match_pattern = "github.com"
engine = "crawl4ai"
css_selector = "main"
priority = 5

# 微博 — 使用正则，启用 JS 渲染
[[site_rules.rules]]
name = "weibo"
match_type = "regex"
match_pattern = 'https?://(www\.)?weibo\.com/.+'
engine = "crawl4ai"
priority = 8

[site_rules.rules.extra_options]
enable_js = true
wait_for = "css:.Feed"

# 普通博客 — 使用 httpx 轻量引擎
[[site_rules.rules]]
name = "static_blogs"
match_type = "regex"
match_pattern = 'https?://[^/]+/(blog|post|article)/.+'
engine = "httpx"
priority = 1
```

### 6.3 配置类实现要点

```python
class UrlParserConfig(BaseConfig):
    """URL Parser 插件配置。"""

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "URL 解析工具插件配置"

    @config_section("plugin", title="插件设置", tag="plugin")
    class PluginSection(SectionBase):
        enabled: bool = Field(default=True, ...)
        version: str = Field(default="1.0.0", ...)

    @config_section("components", title="组件配置", tag="plugin")
    class ComponentsSection(SectionBase):
        enable_url_parser_tool: bool = Field(default=True, ...)
        enable_url_parser_service: bool = Field(default=True, ...)

    @config_section("engines", title="引擎配置", tag="general")
    class EnginesSection(SectionBase):
        engine_order: list[str] = Field(default=["crawl4ai"], ...)
        default_timeout: int = Field(default=30, ...)
        max_content_length: int = Field(default=8000, ...)

    @config_section("crawl4ai", title="Crawl4AI 配置", tag="engine")
    class Crawl4AISection(SectionBase):
        headless: bool = Field(default=True, ...)
        viewport_width: int = Field(default=1280, ...)
        viewport_height: int = Field(default=720, ...)
        page_timeout: int = Field(default=60000, ...)
        # ... 其余字段

    @config_section("site_rules", title="站点规则", tag="routing")
    class SiteRulesSection(SectionBase):
        rules: list[dict[str, Any]] = Field(default_factory=list, ...)

    # 配置节实例
    plugin: PluginSection = Field(default_factory=PluginSection)
    components: ComponentsSection = Field(default_factory=ComponentsSection)
    engines: EnginesSection = Field(default_factory=EnginesSection)
    crawl4ai: Crawl4AISection = Field(default_factory=Crawl4AISection)
    # ... 其余节实例
```

---

## 7. 数据模型

### 7.1 ParseResult（引擎输出）

引擎层统一返回 `ParseResult` 对象（见 4.1 节定义）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `url` | `str` | 实际解析的 URL（可能经过重定向） |
| `title` | `str` | 页面标题 |
| `content` | `str` | 解析后的正文内容 |
| `content_format` | `str` | 内容格式：`"markdown"` / `"html"` / `"text"` |
| `metadata` | `dict[str, Any]` | 额外元数据（状态码、响应头等） |
| `engine` | `str` | 实际使用的引擎名称 |
| `success` | `bool` | 是否成功 |
| `error` | `str \| None` | 失败时的错误信息 |

### 7.2 ParseResponse（管理器输出）

`ParseManager` 在 `ParseResult` 基础上增加路由信息，作为对上层组件的统一输出：

| 字段 | 类型 | 说明 |
|---|---|---|
| `url` | `str` | 原始请求 URL |
| `title` | `str` | 页面标题 |
| `content` | `str` | 正文内容（已截断/摘要） |
| `content_format` | `str` | 内容格式 |
| `engine_used` | `str` | 实际使用的引擎 |
| `rule_matched` | `str \| None` | 命中的站点规则名称（无则为 None） |
| `metadata` | `dict[str, Any]` | 元数据 |
| `success` | `bool` | 是否成功 |
| `error` | `str \| None` | 错误信息 |

### 7.3 多 URL 批量结果

Tool/Service 支持批量解析多个 URL，返回列表：

```python
# Service 返回
list[ParseResponse]

# Tool 返回（格式化文本）
str  # 多个结果用分隔线连接
```

---

## 8. 组件 API 设计

### 8.1 URLParserTool（LLM Tool）

供 LLM 调用的工具组件。

```python
# components/tools/url_parser.py
# 位于 components/tools/ 下，导入 managers/config 需用 ... (三个点)
from ...managers.parse_manager import ParseManager

class URLParserTool(BaseTool):
    """URL 内容解析工具。"""

    tool_name = "parse_url"
    tool_description = (
        "解析一个或多个网页URL，提取页面标题和正文内容。"
        "使用场景：用户发送了网页链接并希望了解其内容时调用。"
    )

    def __init__(self, plugin: "BasePlugin") -> None:
        super().__init__(plugin)
        self._manager = ParseManager(plugin.config)

    async def execute(
        self,
        urls: Annotated[str, "要解析的URL，多个URL用逗号分隔"],
    ) -> tuple[bool, str | dict[str, Any]]:
        """解析URL内容。

        始终返回完整内容，由配置项 ``engines.max_content_length`` 控制截断长度。

        Args:
            urls: 要解析的URL字符串，支持逗号分隔多个

        Returns:
            (是否成功, 格式化文本结果或错误信息)
        """
        ...
```

#### Tool Schema（自动生成）

```json
{
  "type": "function",
  "function": {
    "name": "parse_url",
    "description": "解析一个或多个网页URL，提取页面标题和正文内容...",
    "parameters": {
      "type": "object",
      "properties": {
        "urls": {
          "type": "string",
          "description": "要解析的URL，多个URL用逗号分隔"
        }
      },
      "required": ["urls"]
    }
  }
}
```

### 8.2 URLParseService（插件间 Service）

供其他插件程序化调用的服务组件。

```python
# components/services/url_parse_service.py
# 位于 components/services/ 下，导入 managers/config 需用 ... (三个点)
from ...managers.parse_manager import ParseManager

class URLParseService(BaseService):
    """URL 解析服务。"""

    service_name = "url_parse"
    service_description = "URL 内容解析服务，支持多引擎和站点路由"
    version = "1.0.0"

    def __init__(self, plugin: "BasePlugin") -> None:
        super().__init__(plugin)
        self._manager = ParseManager(plugin.config)

    async def parse(
        self,
        url: str,
        *,
        engine: str | None = None,
        css_selector: str | None = None,
        timeout: int | None = None,
    ) -> ParseResponse:
        """解析单个 URL。

        始终返回完整内容，由配置项 ``engines.max_content_length`` 控制截断长度。

        Args:
            url: 要解析的 URL
            engine: 强制指定引擎（None 则走站点路由 + 全局回退）
            css_selector: CSS 选择器覆盖
            timeout: 超时覆盖

        Returns:
            ParseResponse: 解析响应对象
        """
        ...

    async def parse_batch(
        self,
        urls: list[str],
        *,
        engine: str | None = None,
    ) -> list[ParseResponse]:
        """批量解析多个 URL（并发执行）。"""
        ...

    async def get_available_engines(self) -> list[str]:
        """获取当前可用的引擎列表。"""
        ...

    async def get_engine_status(self, engine_name: str) -> dict[str, Any]:
        """获取指定引擎的状态信息。"""
        ...
```

#### Service 签名

```
url_parser:service:url_parse
```

其他插件调用方式：

```python
from src.core.managers import get_service_manager

service_manager = get_service_manager()
parse_service = service_manager.get_service("url_parser:service:url_parse")

response = await parse_service.parse("https://example.com")
print(response.title)
print(response.content)
```

### 8.3 ParseManager（内部管理器）

`ParseManager` 是插件内部组件，不向框架注册，由 Tool 和 Service 共享实例。

```python
class ParseManager:
    """URL 解析管理器，负责引擎调度和站点路由。"""

    def __init__(self, config: UrlParserConfig | None) -> None:
        self.config = config
        self.engines: dict[str, BaseParseEngine] = {}
        self._site_matcher: SiteMatcher | None = None
        self._init_engines()
        self._init_site_rules()

    async def parse(
        self,
        url: str,
        *,
        engine: str | None = None,
        css_selector: str | None = None,
        timeout: int | None = None,
    ) -> ParseResponse:
        """解析 URL 的核心调度方法。

        流程：
        1. 校验 URL
        2. 若指定 engine，直接使用该引擎
        3. 否则匹配站点规则
        4. 站点规则引擎不可用时，回退到全局引擎顺序
        5. 调用引擎 parse()
        6. 后处理（截断/摘要）
        """
        ...

    async def parse_batch(
        self,
        urls: list[str],
        **kwargs,
    ) -> list[ParseResponse]:
        """并发解析多个 URL。"""
        ...

    def get_available_engines(self) -> list[str]:
        """返回所有可用引擎名称。"""
        ...

    async def close(self) -> None:
        """关闭所有引擎，释放资源。"""
        for engine in self.engines.values():
            await engine.close()
```

---

## 9. 解析流程详解

### 9.1 单 URL 解析流程

```
parse(url) 调用
    │
    ▼
┌─────────────────────┐
│ 1. URL 校验          │  url_utils.validate_url(url)
│    失败 → 返回错误   │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 2. 引擎选择          │
│                     │
│  if engine 参数指定: │
│    → 直接使用该引擎  │
│  else:              │
│    → 站点规则匹配    │  site_matcher.match(url)
│    → 命中？          │
│        是 → 规则引擎 │
│        否 → 全局回退 │  engine_order 列表
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 3. 引擎可用性检查    │  engine.is_available()
│    不可用 → 回退下一个│
│    全部不可用 → 错误 │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 4. 调用引擎 parse()  │  engine.parse(url, css_selector=..., ...)
│    异常 → 记录日志   │
│    → 回退下一个引擎  │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 5. 后处理            │
│    - 内容截断        │  max_content_length
│    - 构建 Response   │
└─────────┬───────────┘
          │
          ▼
    返回 ParseResponse
```

### 9.2 站点规则匹配与回退的边界情况

| 情况 | 处理方式 |
|---|---|
| 站点规则命中，但规则引擎不可用 | 降级到全局 `engine_order` 回退 |
| 站点规则命中，引擎可用但 `parse()` 抛异常 | 记录日志，降级到全局回退 |
| 无站点规则命中 | 直接走全局 `engine_order` |
| 全局引擎列表全部不可用 | 返回错误 `"没有可用的解析引擎"` |
| 全局引擎均可用但全部解析失败 | 返回错误，附带各引擎失败原因 |

### 9.3 批量解析流程

```
parse_batch(urls)
    │
    ▼
    并发为每个 URL 调用 parse()  (asyncio.gather)
    │
    ▼
    收集结果，部分失败不影响其他 URL
    │
    ▼
    返回 list[ParseResponse]
```

### 9.4 内容后处理

返回内容始终按配置项 `engines.max_content_length` 截断，无摘要模式。
> 未来可扩展 LLM 总结能力（需调用 `llm_api`），当前不做。

---

## 10. 扩展指南

### 10.1 新增解析引擎

1. 在 `engines/` 目录创建新文件，如 `engines/playwright_engine.py`
2. 继承 `BaseParseEngine`，实现 `parse()` 和 `is_available()`
3. 在 `ParseManager.__init__()` 中注册引擎实例
4. 在 `config.py` 中添加引擎专属配置节
5. 在 `manifest.json` 的 `python_dependencies` 中添加依赖

```python
# engines/playwright_engine.py
from .base import BaseParseEngine, ParseResult

class PlaywrightEngine(BaseParseEngine):
    """基于 Playwright 的解析引擎。"""

    engine_name = "playwright"

    def is_available(self) -> bool:
        try:
            import playwright
            return True
        except ImportError:
            return False

    async def parse(self, url, *, css_selector=None, timeout=None, extra_options=None):
        # 实现解析逻辑
        ...
        return ParseResult(url=url, title=..., content=..., engine=self.engine_name)
```

```python
# managers/parse_manager.py — 注册引擎
from ..engines.playwright_engine import PlaywrightEngine

self.engines["playwright"] = PlaywrightEngine(self.config)
```

### 10.2 新增站点规则

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

### 10.3 扩展检查清单

新增引擎时逐条检查：

1. 是否继承了 `BaseParseEngine`
2. 是否定义了 `engine_name` 类属性
3. 是否实现了 `parse()` 和 `is_available()`
4. 是否在 `ParseManager` 中注册
5. 是否在配置中添加了专属配置节
6. 是否更新了 `manifest.json` 的 `python_dependencies`
7. `close()` 是否正确释放资源（若有）

---

## 11. 实现计划

### 11.1 实现阶段

| 阶段 | 内容 | 优先级 |
|---|---|---|
| **P0** | 引擎基类 + Crawl4AI 引擎 + ParseManager 核心 | 高 |
| **P0** | 配置类 + manifest + plugin.py | 高 |
| **P0** | URLParserTool（LLM Tool） | 高 |
| **P1** | URLParseService（插件间 Service） | 中 |
| **P1** | 站点路由规则匹配（SiteMatcher） | 中 |
| **P2** | httpx 轻量引擎（回退方案） | 低 |
| **P2** | 使用示例（examples/） | 低 |

### 11.2 文件实现顺序

```
1. manifest.json
2. config.py
3. engines/base.py                          ← 引擎基类 + ParseResult
4. engines/crawl4ai_engine.py
5. utils/url_utils.py
6. utils/site_matcher.py
7. utils/formatters.py
8. managers/parse_manager.py
9. components/tools/url_parser.py
10. components/services/url_parse_service.py
11. plugin.py
12. examples/usage.py
```

### 11.3 风险与对策

| 风险 | 对策 |
|---|---|
| Crawl4AI 安装复杂（需 Playwright 浏览器） | 内置 httpx 引擎作为零依赖回退 |
| 站点规则正则编写错误 | 初始化时编译验证，日志报告无效规则 |
| 浏览器实例泄漏 | `on_plugin_unloaded` 钩子调用 `manager.close()` |
| 解析超时阻塞 | 引擎层强制超时，管理器层 `asyncio.wait_for` 兜底 |

---

> **本文档为设计文档，实际实现时以源码为准。**
> 若文档与实现冲突，以 Neo-MoFox 框架的基类、加载器、管理器的真实行为为准。
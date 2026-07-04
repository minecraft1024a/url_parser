# Trafilatura 引擎配置文档

Trafilatura 是 url_parser 插件的内置轻量解析引擎，基于 [trafilatura](https://trafilatura.readthedocs.io/) 库，使用 httpx 进行异步 HTML 抓取，trafilatura 进行正文提取和元数据解析。无需浏览器环境，资源占用低、启动快，适合作为默认轻量引擎或 Crawl4AI 的回退方案。

---

## 目录

- [环境要求](#环境要求)
- [依赖安装](#依赖安装)
- [启用引擎](#启用引擎)
- [配置项详解](#配置项详解)
- [代理配置](#代理配置)
- [CSS 选择器支持](#css-选择器支持)
- [常见使用场景](#常见使用场景)
- [与 Crawl4AI 引擎对比](#与-crawl4ai-引擎对比)
- [故障排除](#故障排除)
- [相关链接](#相关链接)

---

## 环境要求

| 项目 | 要求 |
|------|------|
| **Python** | >= 3.11 |
| **trafilatura** | >= 1.12.0 |
| **httpx** | >= 0.24.0 |
| **beautifulsoup4** | >= 4.11.0 |
| **操作系统** | Linux / macOS / Windows |
| **浏览器** | 不需要 |

> Trafilatura 引擎无需安装任何浏览器或系统级图形库，这是它与 Crawl4AI 引擎的核心区别。

---

## 依赖安装

### Python 依赖

trafilatura 引擎依赖以下 Python 包（已在 [`manifest.json`](../manifest.json) 的 `python_dependencies` 中声明）：

- `trafilatura>=1.12.0`
- `httpx>=0.24.0`
- `beautifulsoup4>=4.11.0`

在 Neo-MoFox 项目根目录执行：

```bash
# 安装 trafilatura
uv add trafilatura
```

> `httpx` 与 `beautifulsoup4` 通常作为 Neo-MoFox 核心依赖已存在，无需单独安装。如缺失，可一并添加：`uv add httpx beautifulsoup4`。

### 安装验证

安装完成后，可在 Neo-MoFox 运行时通过日志验证。引擎启动时若成功初始化，插件加载日志会输出：

```
[INFO] [url_parser_plugin] ✅ 引擎 Trafilatura: 可用
```

若引擎不可用，[`is_available()`](../engines/trafilatura_engine.py:46) 方法会返回 `False`，插件将跳过该引擎并尝试下一个回退引擎。

你也可以手动验证安装：

```bash
uv run python -c "import trafilatura; print(trafilatura.__version__)"
```

---

## 启用引擎

编辑插件配置文件 `config/plugins/url_parser/config.toml`，将 trafilatura 加入引擎顺序：

```toml
[plugin]
enabled = true

[components]
enable_url_parser_tool = true       # 启用 Tool 组件（供 LLM 调用）
enable_url_parser_service = true    # 启用 Service 组件（供插件调用）

[engines]
# 引擎使用顺序，同时作为启用列表
# 不在列表中的引擎不会被使用
engine_order = ["trafilatura"]
```

### 作为 Crawl4AI 的回退引擎

推荐将 trafilatura 作为 Crawl4AI 的回退引擎，实现「渲染型优先 + 轻量兜底」策略：

```toml
[engines]
# 先尝试 Crawl4AI（支持 JS 渲染），不可用时回退到 trafilatura
engine_order = ["crawl4ai", "trafilatura"]
```

---

## 配置项详解

trafilatura 引擎的配置位于配置文件的 `[trafilatura]` 节。这些配置由 [`_extract()`](../engines/trafilatura_engine.py:249) 和 [`_fetch_html()`](../engines/trafilatura_engine.py:165) 方法读取。

### HTTP 请求配置

```toml
[trafilatura]
# HTTP 请求超时时间（秒）
timeout = 15

# 是否跟随 HTTP 重定向
follow_redirects = true

# 请求头 User-Agent
user_agent = "Mozilla/5.0 (compatible; UrlParser/1.0)"
```

| 配置项 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `timeout` | `int` | `15` | 3-60 | HTTP 请求超时（秒） |
| `follow_redirects` | `bool` | `true` | — | 跟随 HTTP 重定向 |
| `user_agent` | `str` | `Mozilla/5.0 (compatible; UrlParser/1.0)` | — | 请求头 User-Agent |

### 内容提取配置

以下配置项对应 trafilatura `bare_extraction()` 函数的参数：

```toml
[trafilatura]
# 输出格式：markdown / txt / html
output_format = "markdown"

# 是否提取评论内容
include_comments = false

# 是否提取表格内容
include_tables = true

# 是否保留链接及其目标（实验性）
include_links = false

# 是否移除重复段落和文档
deduplicate = true

# 目标语言（ISO 639-1 格式，如 zh/en），留空表示不限语言
target_language = ""
```

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `output_format` | `str` | `markdown` | 输出格式：`markdown` / `txt` / `html` |
| `include_comments` | `bool` | `false` | 是否提取评论内容 |
| `include_tables` | `bool` | `true` | 是否提取表格内容 |
| `include_links` | `bool` | `false` | 是否保留链接及其目标（实验性） |
| `deduplicate` | `bool` | `true` | 是否移除重复段落和文档 |
| `target_language` | `str` | `""` | 目标语言（ISO 639-1），留空不限 |

> **关于输出格式**：推荐使用 `markdown` 格式，与 Crawl4AI 引擎的默认输出一致。`txt` 格式会丢失结构化信息，`html` 格式保留原始标签。

---

## 代理配置

代理配置位于独立的 `[proxy]` 节，对所有引擎生效。由 [`_get_proxy_url()`](../engines/trafilatura_engine.py:317) 读取并传递给 httpx 客户端。

```toml
[proxy]
enable_proxy = false
http_proxy = ""           # 格式: http://proxy.example.com:8080
https_proxy = ""          # 格式: http://proxy.example.com:8080
socks5_proxy = ""         # 格式: socks5://proxy.example.com:1080
```

**优先级**：SOCKS5 代理 > HTTP/HTTPS 代理。

启用代理示例：

```toml
[proxy]
enable_proxy = true
socks5_proxy = "socks5://127.0.0.1:1080"
```

> httpx 的代理支持带认证的代理，格式为 `http://user:pass@proxy:8080`。请将用户名密码嵌入 URL 中。

---

## CSS 选择器支持

trafilatura 引擎支持通过 `css_selector` 参数提取页面特定区域。实现方式由 [`_apply_css_selector()`](../engines/trafilatura_engine.py:229) 完成：

1. 使用 BeautifulSoup 解析 HTML
2. 应用 CSS 选择器筛选匹配元素
3. 将匹配元素拼装为 HTML 片段
4. 交由 trafilatura 提取正文

```python
# 在 Service 调用中指定 CSS 选择器
response = await parse_service.parse(
    "https://example.com/article",
    engine="trafilatura",
    css_selector="div.article-body",
)
```

> **注意**：CSS 选择器预过滤后，trafilatura 会失去全页上下文，可能影响元数据提取质量。如需完整元数据，建议不指定 CSS 选择器。

### 通过站点规则指定 CSS 选择器

```toml
[[site_rules.rules]]
name = "blog_main"
match_type = "regex"
match_pattern = 'https?://[^/]+/blog/.+'
engine = "trafilatura"
css_selector = "article.post-content"
priority = 5
```

---

## 常见使用场景

### 场景 1：解析静态博客/新闻页面

trafilatura 的核心优势场景，使用默认配置即可：

```toml
[trafilatura]
output_format = "markdown"
include_tables = true
deduplicate = true
```

### 场景 2：解析中文内容

指定目标语言为中文，过滤非中文页面：

```toml
[trafilatura]
target_language = "zh"
```

### 场景 3：保留链接和表格

需要完整链接信息时（如内容索引）：

```toml
[trafilatura]
include_links = true
include_tables = true
include_comments = false
```

### 场景 4：纯文本输出

用于后续 NLP 处理，不需要 Markdown 结构：

```toml
[trafilatura]
output_format = "txt"
```

### 场景 5：轻量回退策略

将 trafilatura 配置为 Crawl4AI 不可用时的自动回退：

```toml
[engines]
engine_order = ["crawl4ai", "trafilatura"]

[trafilatura]
# 回退场景下使用保守配置，确保快速响应
timeout = 10
output_format = "markdown"
deduplicate = true
```

---

## 与 Crawl4AI 引擎对比

| 特性 | Crawl4AI | Trafilatura |
|------|----------|-------------|
| **渲染方式** | Playwright 无头浏览器 | httpx 直接请求 |
| **JS 渲染** | ✅ 支持 | ❌ 不支持 |
| **浏览器依赖** | 需要 Chromium | 无需浏览器 |
| **系统依赖** | 需要图形库 | 无 |
| **资源占用** | 高（200-500MB 内存） | 低 |
| **启动速度** | 慢（浏览器启动） | 快 |
| **正文提取** | PruningContentFilter | trafilatura 算法 |
| **元数据提取** | 有限 | ✅ 丰富（作者、日期、站点名等） |
| **输出格式** | Markdown | Markdown / txt / html |
| **去重** | 不支持 | ✅ 支持 |
| **语言过滤** | 不支持 | ✅ 支持 |
| **适用场景** | 动态页面、JS 渲染 | 静态页面、新闻/博客 |

### 推荐策略

1. **默认轻量模式**：仅使用 trafilatura，适合资源受限环境
2. **渲染优先模式**：`["crawl4ai", "trafilatura"]`，动态页面用 Crawl4AI，静态页面用 trafilatura 回退
3. **按站点路由**：为特定站点指定引擎（见下方示例）

```toml
# 知乎等需要 JS 渲染的站点用 Crawl4AI
[[site_rules.rules]]
name = "zhihu"
match_type = "regex"
match_pattern = 'https?://(www\.)?zhihu\.com/.+'
engine = "crawl4ai"
priority = 10

# 博客/新闻类静态站点用 trafilatura
[[site_rules.rules]]
name = "static_blogs"
match_type = "regex"
match_pattern = 'https?://[^/]+/(blog|post|article)/.+'
engine = "trafilatura"
priority = 5
```

---

## 故障排除

### 引擎不可用（`is_available()` 返回 False）

1. **确认 Python 包已安装**：
   ```bash
   uv run python -c "import trafilatura; print(trafilatura.__version__)"
   ```
   若报 `ImportError`，执行 `uv add trafilatura`。

2. **确认 httpx 已安装**：
   ```bash
   uv run python -c "import httpx; print(httpx.__version__)"
   ```

3. **确认 beautifulsoup4 已安装**（CSS 选择器功能依赖）：
   ```bash
   uv run python -c "import bs4; print(bs4.__version__)"
   ```

### 解析结果内容为空

- **页面需要 JS 渲染**：trafilatura 无法渲染 JavaScript，请改用 Crawl4AI 引擎
- **检查 CSS 选择器**：若指定了 `css_selector`，确认选择器能匹配到页面元素
- **降低过滤强度**：尝试设置 `deduplicate = false`
- **检查目标语言**：若设置了 `target_language`，确认页面语言匹配
- **查看日志**：搜索 `trafilatura_engine` 相关记录了解具体错误

### HTTP 请求失败

- **超时**：增大 `timeout` 值
- **SSL 错误**：检查证书或网络环境
- **403/429**：网站反爬，尝试更换 `user_agent`
- **网络不通**：检查代理配置或网络连通性

### 元数据缺失

trafilatura 的元数据提取依赖页面结构。以下情况可能导致元数据不完整：

- 页面缺少标准的 `<meta>` 标签
- 页面使用非标准的 JSON-LD 结构
- CSS 选择器预过滤导致上下文丢失

如需完整元数据，建议不指定 `css_selector`，让 trafilatura 分析完整页面。

---

## 相关链接

- [Trafilatura 官方文档](https://trafilatura.readthedocs.io/)
- [Trafilatura GitHub 仓库](https://github.com/adbar/trafilatura)
- [Trafilatura 核心函数文档](https://trafilatura.readthedocs.io/en/latest/corefunctions.html)
- [httpx 官方文档](https://www.python-httpx.org/)
- [BeautifulSoup 文档](https://www.crummy.com/software/BeautifulSoup/bs4/doc/)
- [Crawl4AI 引擎文档](./crawl4ai.md)
- [url_parser 插件 README](../../README.md)
- [url_parser 插件设计文档](../../DESIGN.md)

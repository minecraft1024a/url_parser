# Crawl4AI 引擎配置文档

Crawl4AI 是 url_parser 插件的内置渲染型解析引擎，基于 [Playwright](https://playwright.dev/) 无头浏览器，支持 JavaScript 渲染、CSS 选择器提取、内容过滤和 Markdown 输出。本指南介绍如何在 Neo-MoFox 中安装依赖并配置该引擎。

---

## 目录

- [环境要求](#环境要求)
- [依赖安装](#依赖安装)
  - [Python 依赖](#python-依赖)
  - [Playwright 浏览器安装](#playwright-浏览器安装)
  - [安装验证](#安装验证)
  - [系统依赖（Linux）](#系统依赖linux)
- [启用引擎](#启用引擎)
- [配置项详解](#配置项详解)
  - [浏览器配置（BrowserConfig）](#浏览器配置browserconfig)
  - [运行时配置（CrawlerRunConfig）](#运行时配置crawlerrunconfig)
- [代理配置](#代理配置)
- [常见使用场景](#常见使用场景)
- [故障排除](#故障排除)
- [相关链接](#相关链接)

---

## 环境要求

| 项目 | 要求 |
|------|------|
| **Python** | >= 3.11 |
| **crawl4ai** | >= 0.4.0 |
| **操作系统** | Linux / macOS / Windows |
| **浏览器** | Chromium（由 Playwright 自动管理） |
| **系统库** | 无头浏览器依赖（见[系统依赖](#系统依赖linux)） |

> Neo-MoFox 使用 [`uv`](https://docs.astral.sh/uv/) 进行依赖管理，以下命令均基于 uv 环境。若使用原生 pip，请自行替换 `uv pip install` 为 `pip install`。

---

## 依赖安装

### Python 依赖

crawl4ai 引擎依赖以下 Python 包（已在 [`manifest.json`](../manifest.json) 的 `python_dependencies` 中声明）：

- `crawl4ai>=0.4.0`
- `httpx>=0.24.0`
- `beautifulsoup4>=4.11.0`

在 Neo-MoFox 项目根目录执行：

```bash
# 安装 crawl4ai 及其依赖
uv pip install crawl4ai
```

> `httpx` 与 `beautifulsoup4` 通常作为 Neo-MoFox 核心依赖已存在，无需单独安装。如缺失，可一并添加：`uv add httpx beautifulsoup4`。

### Playwright 浏览器安装

crawl4ai 依赖 Playwright 提供的 Chromium 浏览器。**安装 Python 包后必须执行此步骤**，否则引擎会因找不到浏览器而不可用。

```bash
# 安装 Playwright 浏览器（推荐方式）
crawl4ai-setup
```

`crawl4ai-setup` 会自动下载并配置 Chromium 浏览器及其依赖。

> **旧命令提示**：早期 crawl4ai 版本使用 `crawl4ai-install` 命令。自 0.4.x 起，官方命令已更名为 `crawl4ai-setup`。若你的版本仍为旧版，请使用 `crawl4ai-install`，或升级 crawl4ai 后使用新命令。

如果 `crawl4ai-setup` 失败，可手动安装 Playwright 浏览器作为回退方案：

```bash
# 手动安装 Chromium
playwright install chromium

# 如需强制重装
playwright install chromium --force
```

### 安装验证

安装完成后，运行官方诊断工具确认环境就绪：

```bash
crawl4ai-doctor
```

`crawl4ai-doctor` 会检查 Python 包、浏览器、系统依赖是否完整，并输出诊断报告。若所有检查项通过，说明环境配置正确。

你也可以在 Neo-MoFox 运行时通过日志验证。引擎启动时若成功初始化，日志会输出：

```
[INFO] [crawl4ai_engine] Crawl4AI 浏览器实例已启动
```

若引擎不可用，[`is_available()`](../engines/crawl4ai_engine.py:45) 方法会返回 `False`，插件将跳过该引擎并尝试下一个回退引擎。

### 系统依赖（Linux）

在 Linux 服务器（特别是 Docker 容器或精简系统）上，无头浏览器需要额外的系统库。如果 `crawl4ai-setup` 未自动处理，请手动安装：

**Ubuntu / Debian：**

```bash
sudo apt-get update
sudo apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libx11-6 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2
```

**或者使用 Playwright 官方安装脚本（推荐）：**

```bash
playwright install-deps chromium
```

> Docker 部署时，建议在 Dockerfile 的构建阶段执行上述命令，确保运行时镜像包含浏览器依赖。

---

## 启用引擎

编辑插件配置文件 `config/plugins/url_parser/config.toml`，确保插件已启用并将 crawl4ai 加入引擎顺序：

```toml
[plugin]
enabled = true

[components]
enable_url_parser_tool = true       # 启用 Tool 组件（供 LLM 调用）
enable_url_parser_service = true    # 启用 Service 组件（供插件调用）

[engines]
# 引擎使用顺序，同时作为启用列表
# 不在列表中的引擎不会被使用
engine_order = ["crawl4ai"]
```

---

## 配置项详解

Crawl4AI 引擎的配置位于配置文件的 `[crawl4ai]` 节。这些配置对应 crawl4ai 库的 `BrowserConfig`（浏览器启动参数）和 `CrawlerRunConfig`（单次抓取参数）。

### 浏览器配置（BrowserConfig）

以下配置项由 [`_build_browser_config()`](../engines/crawl4ai_engine.py:161) 读取，用于控制浏览器实例的启动行为：

```toml
[crawl4ai]
# 是否使用无头模式（无 GUI 界面）
# 服务器部署建议 true；调试时可设为 false 观察浏览器行为
headless = true

# 浏览器视口宽度（像素）
# 影响 CSS 响应式布局的渲染结果
viewport_width = 1280

# 浏览器视口高度（像素）
viewport_height = 720

# 自定义用户代理字符串
# 留空使用 crawl4ai 默认 UA；某些站点需要伪装为真实浏览器
user_agent = ""
```

| 配置项 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `headless` | `bool` | `true` | — | 无头浏览器模式 |
| `viewport_width` | `int` | `1280` | 320-3840 | 视口宽度 |
| `viewport_height` | `int` | `720` | 240-2160 | 视口高度 |
| `user_agent` | `str` | `""` | — | 自定义 UA，空值用默认 |

### 运行时配置（CrawlerRunConfig）

以下配置项由 [`_build_run_config()`](../engines/crawl4ai_engine.py:191) 读取，用于控制每次 URL 抓取的行为：

```toml
[crawl4ai]
# 页面超时（毫秒），包括导航和脚本执行
page_timeout = 60000

# 等待条件，留空表示不等待
# 常见格式：
#   "css:.content-loaded"   等待指定 CSS 选择器出现
#   "js:() => document.ready" 等待 JS 条件为真
wait_for = ""

# 抓取前延迟（秒），用于等待动态内容加载完成
delay_before_return_html = 0.0

# PruningContentFilter 阈值 (0.0-1.0)
# 越高过滤越严格，保留更精炼的正文内容
content_filter_threshold = 0.6

# 是否移除弹窗、遮罩等覆盖层元素
remove_overlay_elements = true

# 是否启用 JavaScript 执行
# 需要渲染动态内容时设为 true
enable_js = false

# 自定义 JS 代码列表，在页面加载后执行
# 仅当 enable_js = true 时生效
js_code = []
```

| 配置项 | 类型 | 默认值 | 范围 | 说明 |
|--------|------|--------|------|------|
| `page_timeout` | `int` | `60000` | 5000-300000 | 页面超时（毫秒） |
| `wait_for` | `str` | `""` | — | 等待条件 |
| `delay_before_return_html` | `float` | `0.0` | 0.0-30.0 | 抓取前延迟（秒） |
| `content_filter_threshold` | `float` | `0.6` | 0.0-1.0 | 内容过滤阈值 |
| `remove_overlay_elements` | `bool` | `true` | — | 移除遮罩层 |
| `enable_js` | `bool` | `false` | — | 启用 JS 执行 |
| `js_code` | `list[str]` | `[]` | — | 自定义 JS 代码列表 |

> **关于内容过滤**：引擎使用 [`PruningContentFilter`](https://docs.crawl4ai.com/core/fit-markdown/) 和 [`DefaultMarkdownGenerator`](https://docs.crawl4ai.com/core/fit-markdown/) 生成 Markdown。`content_filter_threshold` 控制过滤强度——值越高，保留的内容越精炼（噪声越少），但可能丢失部分正文。建议范围 0.45-0.6。引擎会优先输出 `fit_markdown`（过滤后内容），其次 `raw_markdown`。

---

## 代理配置

代理配置位于独立的 `[proxy]` 节，对所有引擎生效。由 [`_get_proxy_url()`](../engines/crawl4ai_engine.py:328) 读取并传递给 crawl4ai 的 `BrowserConfig.proxy_config`。

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

> crawl4ai 的 `proxy_config` 支持带认证的代理，格式为 `http://user:pass@proxy:8080`。当前插件实现将代理 URL 以字符串形式直接传递，请将用户名密码嵌入 URL 中。

---

## 常见使用场景

### 场景 1：解析静态内容页面

大多数博客、文档站点无需 JS 渲染，使用默认配置即可：

```toml
[crawl4ai]
enable_js = false
content_filter_threshold = 0.6
```

### 场景 2：解析动态渲染页面（微博、知乎等）

需要 JavaScript 渲染的页面，启用 JS 并设置等待条件：

```toml
[crawl4ai]
enable_js = true
wait_for = "css:.Feed"
delay_before_return_html = 2.0
page_timeout = 90000
```

### 场景 3：通过站点规则为特定站点指定参数

无需全局启用 JS，通过站点规则按需启用：

```toml
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

站点规则的 `extra_options` 会覆盖全局 `[crawl4ai]` 节的对应配置项。

### 场景 4：服务器资源受限时优化性能

降低超时、关闭不必要的功能以节省资源：

```toml
[crawl4ai]
headless = true
page_timeout = 30000
delay_before_return_html = 0.0
content_filter_threshold = 0.5
remove_overlay_elements = true
enable_js = false
```

---

## 故障排除

### 引擎不可用（`is_available()` 返回 False）

1. **确认 Python 包已安装**：
   ```bash
   uv run python -c "import crawl4ai; print(crawl4ai.__version__)"
   ```
   若报 `ImportError`，执行 `uv pip install crawl4ai`。

2. **确认浏览器已安装**：
   ```bash
   crawl4ai-doctor
   ```
   若提示浏览器缺失，执行 `crawl4ai-setup`。

3. **确认系统依赖完整**（Linux）：
   ```bash
   playwright install-deps chromium
   ```

### 浏览器启动失败

- **内存不足**：无头浏览器占用约 200-500MB 内存。服务器内存紧张时，可降低 `viewport_width` / `viewport_height`。
- **沙箱权限问题**：Docker 容器中可能需要以 `--no-sandbox` 方式运行，但当前插件实现未暴露此选项。如遇此问题，请通过环境变量或系统级 Chromium 配置处理。
- **端口冲突**：浏览器调试端口被占用。确保没有其他 Playwright 实例占用调试端口。

### 解析结果内容为空

- 检查目标页面是否需要 JS 渲染：设 `enable_js = true`。
- 添加 `wait_for` 等待动态内容加载：如 `wait_for = "css:.content"`。
- 增加 `delay_before_return_html` 给页面更多加载时间。
- 降低 `content_filter_threshold`（如 0.4）以保留更多内容。
- 查看日志：搜索 `crawl4ai_engine` 相关记录了解具体错误。

### 解析超时

- 增大 `page_timeout`（单位毫秒，如 `90000`）。
- 检查网络连通性，必要时配置代理。

### Docker 部署问题

在 Dockerfile 构建阶段安装依赖：

```dockerfile
# 安装系统依赖
RUN apt-get update && apt-get install -y \
    libnss3 libnspr4 libatk1.0-0 libatk-bridge2.0-0 \
    libcups2 libdrm2 libdbus-1-3 libxkbcommon0 \
    libx11-6 libxcomposite1 libxdamage1 libxext6 \
    libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 \
    libcairo2 libasound2

# 安装 crawl4ai 和浏览器
RUN uv add crawl4ai
RUN crawl4ai-setup
```

---

## 相关链接

- [Crawl4AI 官方文档](https://docs.crawl4ai.com/)
- [Crawl4AI GitHub 仓库](https://github.com/unclecode/crawl4ai)
- [Playwright 官方文档](https://playwright.dev/python/docs/intro)
- [PruningContentFilter 与 Fit Markdown](https://docs.crawl4ai.com/core/fit-markdown)
- [BrowserConfig 与 CrawlerRunConfig 参数](https://docs.crawl4ai.com/core/browser-crawler-config)
- [url_parser 插件 README](../../README.md)
- [url_parser 插件设计文档](../../DESIGN.md)

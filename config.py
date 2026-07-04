"""URL Parser 插件配置定义。

定义插件的全部配置节，包括引擎全局配置、Crawl4AI 引擎配置、
trafilatura 引擎配置、httpx 引擎配置、代理配置和站点路由规则。
所有字段均带 WebUI 增强参数（input_type / step / choices / hint 等），
供 WebUI 可视化配置编辑器渲染表单使用。
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class SiteRuleEntry(SectionBase):
    """单条站点路由规则。

    定义如何为匹配的 URL 选择引擎及参数。
    规则按 ``priority`` 降序匹配，优先级高的规则先匹配。
    """

    name: str = Field(
        default="",
        description="规则名称（用于日志和调试）",
        label="规则名称",
        placeholder="例：GitHub 规则",
        hint="仅用于日志和调试识别，不影响匹配逻辑",
        tag="general",
        order=0,
    )
    match_type: str = Field(
        default="domain",
        description='匹配类型，"domain" 或 "regex"',
        label="匹配类型",
        choices=["domain", "regex"],
        hint="domain 按域名匹配，regex 使用正则表达式匹配完整 URL",
        tag="general",
        order=1,
    )
    match_pattern: str = Field(
        default="",
        description="域名或正则表达式",
        label="匹配模式",
        placeholder="example.com 或 ^https?://.*",
        hint="domain 模式下填写域名（如 github.com）；regex 模式下填写完整正则表达式",
        tag="general",
        order=2,
    )
    engine: str = Field(
        default="",
        description="使用的引擎名称（crawl4ai / trafilatura / httpx）",
        label="引擎",
        choices=["crawl4ai", "trafilatura", "httpx"],
        hint="留空则使用引擎顺序中的默认引擎",
        tag="general",
        order=3,
    )
    css_selector: str | None = Field(
        default=None,
        description="CSS 选择器（可选，仅对支持选择器的引擎生效）",
        label="CSS 选择器",
        placeholder=".article-content",
        hint="仅对 crawl4ai 引擎生效，留空则提取整页正文",
        tag="advanced",
        order=4,
    )
    extra_options: dict[str, Any] = Field(
        default_factory=dict,
        description="引擎特定额外选项（可选，键值对）",
        label="额外选项",
        input_type="json",
        hint="引擎特定的额外参数，以 JSON 对象形式填写",
        tag="advanced",
        order=5,
    )
    priority: int = Field(
        default=0,
        description="优先级，数值越大越优先匹配",
        label="优先级",
        ge=0,
        le=100,
        input_type="slider",
        step=1,
        hint="数值越大越优先匹配，相同优先级按列表顺序匹配",
        tag="general",
        order=6,
    )


class UrlParserConfig(BaseConfig):
    """URL Parser 插件配置。

    包含插件基本设置、组件开关、引擎全局配置、Crawl4AI/trafilatura/httpx 引擎专属配置、
    代理配置以及站点路由规则。
    """

    config_name: ClassVar[str] = "config"
    config_description: ClassVar[str] = "URL 解析工具插件配置"

    # ── 插件基本设置 ──────────────────────────────────────────────

    @config_section("plugin", title="插件设置", tag="plugin")
    class PluginSection(SectionBase):
        """插件基本配置。"""

        enabled: bool = Field(
            default=True,
            description="是否启用插件",
            label="启用插件",
            input_type="switch",
            tag="plugin",
            order=0,
        )
        version: str = Field(
            default="1.0.0",
            description="插件版本",
            label="插件版本",
            disabled=True,
            tag="general",
            order=1,
        )

    # ── 组件开关 ────────────────────────────────────────────────

    @config_section("components", title="组件配置", tag="plugin")
    class ComponentsSection(SectionBase):
        """组件启用配置。"""

        enable_url_parser_tool: bool = Field(
            default=True,
            description="是否启用 URL 解析工具（供 LLM 调用）",
            label="启用解析工具",
            input_type="switch",
            hint="启用后 LLM 可通过工具调用解析 URL 内容",
            tag="plugin",
            order=0,
        )
        enable_url_parser_service: bool = Field(
            default=True,
            description="是否启用 URL 解析服务（供其他插件调用）",
            label="启用解析服务",
            input_type="switch",
            hint="启用后其他插件可通过 Service API 调用 URL 解析能力",
            tag="plugin",
            order=1,
        )

    # ── 引擎全局配置 ────────────────────────────────────────────

    @config_section("engines", title="引擎配置", tag="general")
    class EnginesSection(SectionBase):
        """引擎全局配置。

        ``engine_order`` 同时作为启用列表和回退顺序：
        站点规则未命中时，按此列表顺序依次尝试引擎。
        """

        engine_order: list[str] = Field(
            default=["crawl4ai"],
            description="引擎使用顺序（从前到后依次尝试），同时作为启用列表",
            label="引擎顺序",
            input_type="list",
            item_type="str",
            tag="list",
            hint="可选：crawl4ai, trafilatura, httpx。站点规则未命中时按此顺序依次尝试",
            order=0,
        )
        default_timeout: int = Field(
            default=30,
            description="默认超时时间（秒），引擎未单独指定时使用",
            label="默认超时",
            ge=5,
            le=120,
            input_type="slider",
            step=5,
            hint="引擎未单独指定超时时间时使用此默认值",
            tag="performance",
            order=1,
        )
        max_content_length: int = Field(
            default=8000,
            description="内容最大长度（字符数），超出截断",
            label="内容最大长度",
            ge=500,
            le=50000,
            input_type="slider",
            step=500,
            hint="解析结果超出此长度将被截断，影响 LLM 上下文消耗",
            tag="performance",
            order=2,
        )

    # ── Crawl4AI 引擎配置 ───────────────────────────────────────

    @config_section("crawl4ai", title="Crawl4AI 配置", tag="general")
    class Crawl4AISection(SectionBase):
        """Crawl4AI 引擎专属配置。

        对应 Crawl4AI 的 ``BrowserConfig`` 和 ``CrawlerRunConfig``。
        """

        headless: bool = Field(
            default=True,
            description="是否使用无头浏览器模式",
            label="无头模式",
            input_type="switch",
            hint="无头模式下浏览器不显示图形界面，适合服务器环境",
            tag="general",
            order=0,
        )
        viewport_width: int = Field(
            default=1280,
            description="浏览器视口宽度",
            label="视口宽度",
            ge=320,
            le=3840,
            input_type="slider",
            step=10,
            hint="影响页面渲染布局，部分响应式站点会因视口宽度返回不同内容",
            tag="general",
            order=1,
        )
        viewport_height: int = Field(
            default=720,
            description="浏览器视口高度",
            label="视口高度",
            ge=240,
            le=2160,
            input_type="slider",
            step=10,
            hint="影响页面渲染布局，部分懒加载内容需足够高度才会触发加载",
            tag="general",
            order=2,
        )
        page_timeout: int = Field(
            default=60000,
            description="页面超时时间（毫秒）",
            label="页面超时",
            ge=5000,
            le=300000,
            input_type="slider",
            step=1000,
            hint="页面加载和导航的超时时间，单位为毫秒",
            tag="network",
            order=3,
        )
        wait_for: str = Field(
            default="",
            description="等待条件，如 'css:.content-loaded'，留空表示不等待",
            label="等待条件",
            placeholder="css:.content-loaded",
            hint="支持 css: 选择器、js: JS 表达式等前缀，留空表示不等待",
            tag="general",
            order=4,
        )
        delay_before_return_html: float = Field(
            default=0.0,
            description="抓取前延迟时间（秒），用于等待动态内容加载",
            label="抓取前延迟",
            ge=0.0,
            le=30.0,
            input_type="slider",
            step=0.5,
            hint="抓取 HTML 前的等待时间，用于动态内容加载",
            tag="performance",
            order=5,
        )
        content_filter_threshold: float = Field(
            default=0.6,
            description="PruningContentFilter 阈值 (0.0-1.0)，越高过滤越严格",
            label="内容过滤阈值",
            ge=0.0,
            le=1.0,
            input_type="slider",
            step=0.1,
            hint="PruningContentFilter 阈值，值越高过滤越严格，保留的核心内容越少",
            tag="performance",
            order=6,
        )
        remove_overlay_elements: bool = Field(
            default=True,
            description="是否移除弹窗、遮罩等覆盖层元素",
            label="移除遮罩",
            input_type="switch",
            hint="移除弹窗、广告遮罩等覆盖层元素，提升正文提取质量",
            tag="general",
            order=7,
        )
        user_agent: str = Field(
            default="",
            description="自定义用户代理，留空使用默认",
            label="用户代理",
            placeholder="Mozilla/5.0 ...",
            hint="留空使用 Crawl4AI 默认 User-Agent",
            tag="network",
            order=8,
        )
        enable_js: bool = Field(
            default=False,
            description="是否启用 JavaScript 执行",
            label="启用 JS",
            input_type="switch",
            hint="启用后会执行页面 JavaScript，适合 SPA 站点但会增加抓取耗时",
            tag="general",
            order=9,
        )
        js_code: list[str] = Field(
            default=[],
            description="自定义 JS 代码列表，在页面加载后执行",
            label="JS 代码",
            input_type="list",
            item_type="str",
            tag="advanced",
            depends_on="enable_js",
            depends_value=True,
            order=10,
        )

    # ── trafilatura 引擎配置 ─────────────────────────────────────

    @config_section("trafilatura", title="Trafilatura 配置", tag="general")
    class TrafilaturaSection(SectionBase):
        """trafilatura 引擎专属配置。

        trafilatura 引擎是轻量级解析方案，无需浏览器环境，
        基于 httpx 抓取 + trafilatura 正文提取，适合静态 HTML 页面。
        """

        timeout: int = Field(
            default=15,
            description="HTTP 请求超时时间（秒）",
            label="请求超时",
            ge=3,
            le=60,
            input_type="slider",
            step=1,
            hint="httpx 抓取页面的超时时间",
            tag="network",
            order=0,
        )
        follow_redirects: bool = Field(
            default=True,
            description="是否跟随 HTTP 重定向",
            label="跟随重定向",
            input_type="switch",
            tag="general",
            order=1,
        )
        user_agent: str = Field(
            default="Mozilla/5.0 (compatible; UrlParser/1.0)",
            description="请求头 User-Agent",
            label="User-Agent",
            hint="部分站点会根据 User-Agent 返回不同内容",
            tag="network",
            order=2,
        )
        output_format: str = Field(
            default="markdown",
            description="trafilatura 输出格式：markdown / txt / html",
            label="输出格式",
            choices=["markdown", "txt", "html"],
            hint="markdown 适合 LLM 阅读，txt 为纯文本，html 保留原始标签",
            tag="general",
            order=3,
        )
        include_comments: bool = Field(
            default=False,
            description="是否提取评论内容",
            label="包含评论",
            input_type="switch",
            hint="启用后会提取页面中的评论内容",
            tag="general",
            order=4,
        )
        include_tables: bool = Field(
            default=True,
            description="是否提取表格内容",
            label="包含表格",
            input_type="switch",
            hint="启用后会提取页面中的表格数据",
            tag="general",
            order=5,
        )
        include_links: bool = Field(
            default=False,
            description="是否保留链接及其目标（实验性）",
            label="包含链接",
            input_type="switch",
            hint="实验性功能，启用后会保留文档中的链接及其目标",
            tag="general",
            order=6,
        )
        deduplicate: bool = Field(
            default=True,
            description="是否移除重复段落和文档",
            label="去重",
            input_type="switch",
            hint="启用后会移除重复段落，减少冗余内容",
            tag="general",
            order=7,
        )
        target_language: str = Field(
            default="",
            description="目标语言（ISO 639-1 格式，如 zh/en），留空表示不限语言",
            label="目标语言",
            placeholder="zh",
            pattern=r"^([a-z]{2})?$",
            hint="ISO 639-1 两字母语言代码（如 zh、en、ja），留空表示不限语言",
            tag="general",
            order=8,
        )

    # ── httpx 引擎配置 ──────────────────────────────────────────

    @config_section("httpx", title="httpx 配置", tag="general")
    class HttpxSection(SectionBase):
        """httpx 引擎专属配置。

        httpx 引擎是轻量级回退方案，无需浏览器环境。
        """

        timeout: int = Field(
            default=15,
            description="请求超时时间（秒）",
            label="请求超时",
            ge=3,
            le=60,
            input_type="slider",
            step=1,
            hint="httpx 请求超时时间",
            tag="network",
            order=0,
        )
        follow_redirects: bool = Field(
            default=True,
            description="是否跟随重定向",
            label="跟随重定向",
            input_type="switch",
            tag="general",
            order=1,
        )
        user_agent: str = Field(
            default="Mozilla/5.0 (compatible; UrlParser/1.0)",
            description="请求头 User-Agent",
            label="User-Agent",
            hint="部分站点会根据 User-Agent 返回不同内容",
            tag="network",
            order=2,
        )
        max_content_length: int = Field(
            default=5000,
            description="内容最大长度（字符数），仅对该引擎生效",
            label="内容最大长度",
            ge=500,
            le=50000,
            input_type="slider",
            step=500,
            hint="仅对 httpx 引擎生效，超出此长度的内容将被截断",
            tag="performance",
            order=3,
        )

    # ── 代理配置 ────────────────────────────────────────────────

    @config_section("proxy", title="代理配置", tag="network")
    class ProxySection(SectionBase):
        """代理配置，对所有引擎生效。"""

        enable_proxy: bool = Field(
            default=False,
            description="是否启用代理",
            label="启用代理",
            input_type="switch",
            hint="启用后所有引擎的 HTTP 请求都将通过指定代理发送",
            tag="network",
            order=0,
        )
        http_proxy: str | None = Field(
            default=None,
            description="HTTP 代理地址，格式如: http://proxy.example.com:8080",
            label="HTTP 代理",
            placeholder="http://proxy.example.com:8080",
            tag="network",
            depends_on="enable_proxy",
            depends_value=True,
            order=1,
        )
        https_proxy: str | None = Field(
            default=None,
            description="HTTPS 代理地址，格式如: http://proxy.example.com:8080",
            label="HTTPS 代理",
            placeholder="http://proxy.example.com:8080",
            tag="network",
            depends_on="enable_proxy",
            depends_value=True,
            order=2,
        )
        socks5_proxy: str | None = Field(
            default=None,
            description="SOCKS5 代理地址，格式如: socks5://proxy.example.com:1080",
            label="SOCKS5 代理",
            placeholder="socks5://proxy.example.com:1080",
            tag="network",
            depends_on="enable_proxy",
            depends_value=True,
            order=3,
        )

    # ── 站点路由规则 ────────────────────────────────────────────

    @config_section("site_rules", title="站点规则", tag="general")
    class SiteRulesSection(SectionBase):
        """站点路由规则配置。

        在 TOML 中以 [[site_rules.items]] 数组形式定义多条规则。
        规则按 ``priority`` 降序匹配，优先级高的规则先匹配。
        """

        items: list[SiteRuleEntry] = Field(
            default_factory=list,
            description="站点路由规则列表",
            label="路由规则",
            hint="为特定 URL 指定引擎和参数，规则按优先级降序匹配",
        )

    # ── 配置节实例 ──────────────────────────────────────────────

    plugin: PluginSection = Field(default_factory=PluginSection)
    components: ComponentsSection = Field(default_factory=ComponentsSection)
    engines: EnginesSection = Field(default_factory=EnginesSection)
    crawl4ai: Crawl4AISection = Field(default_factory=Crawl4AISection)
    trafilatura: TrafilaturaSection = Field(default_factory=TrafilaturaSection)
    httpx: HttpxSection = Field(default_factory=HttpxSection)
    proxy: ProxySection = Field(default_factory=ProxySection)
    site_rules: SiteRulesSection = Field(default_factory=SiteRulesSection)

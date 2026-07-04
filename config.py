"""URL Parser 插件配置定义。

定义插件的全部配置节，包括引擎全局配置、Crawl4AI 引擎配置、
httpx 引擎配置、代理配置和站点路由规则。
"""

from __future__ import annotations

from typing import Any, ClassVar

from src.core.components.base.config import BaseConfig, Field, SectionBase, config_section


class UrlParserConfig(BaseConfig):
    """URL Parser 插件配置。

    包含插件基本设置、组件开关、引擎全局配置、Crawl4AI/httpx 引擎专属配置、
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
            tag="plugin",
            order=0,
        )
        enable_url_parser_service: bool = Field(
            default=True,
            description="是否启用 URL 解析服务（供其他插件调用）",
            label="启用解析服务",
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
            hint="可选：crawl4ai, httpx",
            order=0,
        )
        default_timeout: int = Field(
            default=30,
            description="默认超时时间（秒），引擎未单独指定时使用",
            label="默认超时",
            ge=5,
            le=120,
            input_type="slider",
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
            tag="general",
            order=0,
        )
        viewport_width: int = Field(
            default=1280,
            description="浏览器视口宽度",
            label="视口宽度",
            ge=320,
            le=3840,
            tag="general",
            order=1,
        )
        viewport_height: int = Field(
            default=720,
            description="浏览器视口高度",
            label="视口高度",
            ge=240,
            le=2160,
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
            tag="network",
            order=3,
        )
        wait_for: str = Field(
            default="",
            description="等待条件，如 'css:.content-loaded'，留空表示不等待",
            label="等待条件",
            placeholder="css:.content-loaded",
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
            tag="performance",
            order=6,
        )
        remove_overlay_elements: bool = Field(
            default=True,
            description="是否移除弹窗、遮罩等覆盖层元素",
            label="移除遮罩",
            tag="general",
            order=7,
        )
        user_agent: str = Field(
            default="",
            description="自定义用户代理，留空使用默认",
            label="用户代理",
            placeholder="Mozilla/5.0 ...",
            tag="network",
            order=8,
        )
        enable_js: bool = Field(
            default=False,
            description="是否启用 JavaScript 执行",
            label="启用 JS",
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
            tag="network",
            order=0,
        )
        follow_redirects: bool = Field(
            default=True,
            description="是否跟随重定向",
            label="跟随重定向",
            tag="general",
            order=1,
        )
        user_agent: str = Field(
            default="Mozilla/5.0 (compatible; UrlParser/1.0)",
            description="请求头 User-Agent",
            label="User-Agent",
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

        每条规则定义如何为匹配的 URL 选择引擎及参数。
        规则按 ``priority`` 降序匹配，优先级高的规则先匹配。

        规则字段：
        - name: 规则名称
        - match_type: "domain" 或 "regex"
        - match_pattern: 域名或正则表达式
        - engine: 使用的引擎名称
        - css_selector: CSS 选择器（可选）
        - extra_options: 引擎特定额外选项（可选）
        - priority: 优先级，数值越大越优先（默认 0）
        """

        rules: list[dict[str, Any]] = Field(
            default=[],
            description="站点路由规则列表",
            label="路由规则",
            input_type="list",
            item_type="object",
            tag="list",
            order=0,
        )

    # ── 配置节实例 ──────────────────────────────────────────────

    plugin: PluginSection = Field(default_factory=PluginSection)
    components: ComponentsSection = Field(default_factory=ComponentsSection)
    engines: EnginesSection = Field(default_factory=EnginesSection)
    crawl4ai: Crawl4AISection = Field(default_factory=Crawl4AISection)
    httpx: HttpxSection = Field(default_factory=HttpxSection)
    proxy: ProxySection = Field(default_factory=ProxySection)
    site_rules: SiteRulesSection = Field(default_factory=SiteRulesSection)

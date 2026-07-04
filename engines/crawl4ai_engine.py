"""Crawl4AI 引擎实现。

基于 [Crawl4AI](https://docs.crawl4ai.com/) 库的渲染型 URL 解析引擎，
支持 JavaScript 渲染、CSS 选择器提取、内容过滤和 Markdown 输出。

使用懒初始化策略管理 AsyncWebCrawler 实例，插件卸载时通过 close() 释放。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.kernel.logger import get_logger

from .base import BaseParseEngine, ParseResult

if TYPE_CHECKING:
    from ..config import UrlParserConfig

logger = get_logger("crawl4ai_engine")


class Crawl4AIEngine(BaseParseEngine):
    """基于 Crawl4AI 的 URL 解析引擎。

    使用 Playwright 无头浏览器渲染页面，支持动态内容。
    输出 Markdown 格式的正文内容和页面标题。

    Attributes:
        engine_name: 引擎名称标识
        _crawler: 懒初始化的 AsyncWebCrawler 实例
    """

    engine_name: str = "crawl4ai"

    def __init__(self, config: "UrlParserConfig | None" = None) -> None:
        """初始化 Crawl4AI 引擎。

        Args:
            config: 插件配置对象，用于读取 crawl4ai 配置节
        """
        super().__init__(config)
        self._crawler: Any | None = None

    def is_available(self) -> bool:
        """检查 Crawl4AI 引擎是否可用。

        通过尝试导入 crawl4ai 库来判断可用性。

        Returns:
            bool: crawl4ai 已安装则返回 True
        """
        try:
            import crawl4ai  # noqa: F401

            return True
        except ImportError:
            return False

    async def parse(
        self,
        url: str,
        *,
        css_selector: str | None = None,
        timeout: int | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ParseResult:
        """使用 Crawl4AI 解析 URL。

        Args:
            url: 要解析的 URL
            css_selector: CSS 选择器，提取页面特定区域
            timeout: 超时时间（秒），None 使用配置默认值
            extra_options: 额外选项，可覆盖以下键：
                - wait_for: 等待条件
                - delay_before_return_html: 抓取前延迟
                - enable_js: 是否启用 JS
                - js_code: JS 代码列表

        Returns:
            ParseResult: 解析结果对象
        """
        try:
            crawler = await self._get_crawler()
            run_config = self._build_run_config(
                css_selector=css_selector,
                timeout=timeout,
                extra_options=extra_options,
            )

            result = await crawler.arun(url=url, config=run_config)

            if not result.success:
                error_msg = getattr(result, "error_message", None) or "未知错误"
                logger.warning(f"Crawl4AI 解析 '{url}' 失败: {error_msg}")
                return ParseResult.failure(url, self.engine_name, f"解析失败: {error_msg}")

            # 提取 Markdown 内容
            content = self._extract_markdown(result)
            if not content:
                return ParseResult.failure(url, self.engine_name, "无法从页面提取有效内容")

            # 提取标题
            title = self._extract_title(result)

            # 构建元数据
            metadata: dict[str, Any] = {}
            if hasattr(result, "status_code") and result.status_code is not None:
                metadata["status_code"] = result.status_code
            if hasattr(result, "redirected_url") and result.redirected_url:
                metadata["redirected_url"] = result.redirected_url

            logger.info(f"Crawl4AI 成功解析 '{url}'，内容长度: {len(content)}")

            return ParseResult(
                url=url,
                title=title,
                content=content,
                content_format="markdown",
                metadata=metadata,
                engine=self.engine_name,
                success=True,
            )

        except Exception as e:
            logger.error(f"Crawl4AI 解析 '{url}' 时发生异常: {e}", exc_info=True)
            return ParseResult.failure(url, self.engine_name, f"引擎异常: {e!s}")

    async def close(self) -> None:
        """关闭 Crawl4AI 引擎，释放浏览器实例。"""
        if self._crawler is not None:
            try:
                await self._crawler.close()
                logger.info("Crawl4AI 浏览器实例已关闭")
            except Exception as e:
                logger.warning(f"关闭 Crawl4AI 浏览器实例时出错: {e}")
            finally:
                self._crawler = None

    # ── 内部方法 ────────────────────────────────────────────────

    async def _get_crawler(self) -> Any:
        """获取或懒初始化 AsyncWebCrawler 实例。

        Returns:
            AsyncWebCrawler 实例

        Raises:
            ImportError: crawl4ai 未安装
        """
        if self._crawler is None:
            from crawl4ai import AsyncWebCrawler

            browser_config = self._build_browser_config()
            self._crawler = AsyncWebCrawler(config=browser_config)
            await self._crawler.start()
            logger.info("Crawl4AI 浏览器实例已启动")

        return self._crawler

    def _build_browser_config(self) -> Any:
        """构建 Crawl4AI BrowserConfig。

        从配置的 crawl4ai 节读取浏览器参数。

        Returns:
            BrowserConfig 实例
        """
        from crawl4ai import BrowserConfig

        cfg = self._get_crawl4ai_config()

        kwargs: dict[str, Any] = {
            "headless": getattr(cfg, "headless", True),
            "viewport_width": getattr(cfg, "viewport_width", 1280),
            "viewport_height": getattr(cfg, "viewport_height", 720),
        }

        # 代理配置
        proxy_url = self._get_proxy_url()
        if proxy_url:
            kwargs["proxy_config"] = proxy_url

        # 用户代理
        user_agent = getattr(cfg, "user_agent", "")
        if user_agent:
            kwargs["user_agent"] = user_agent

        return BrowserConfig(**kwargs)

    def _build_run_config(
        self,
        *,
        css_selector: str | None = None,
        timeout: int | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> Any:
        """构建 Crawl4AI CrawlerRunConfig。

        Args:
            css_selector: CSS 选择器覆盖
            timeout: 超时覆盖（秒）
            extra_options: 额外选项覆盖

        Returns:
            CrawlerRunConfig 实例
        """
        from crawl4ai import CrawlerRunConfig, CacheMode
        from crawl4ai.content_filter_strategy import PruningContentFilter
        from crawl4ai.markdown_generation_strategy import DefaultMarkdownGenerator

        cfg = self._get_crawl4ai_config()
        extra = extra_options or {}

        # 内容过滤器和 Markdown 生成器
        threshold = extra.get("content_filter_threshold", getattr(cfg, "content_filter_threshold", 0.6))
        content_filter = PruningContentFilter(threshold=threshold)
        markdown_generator = DefaultMarkdownGenerator(content_filter=content_filter)

        # 构建 kwargs
        kwargs: dict[str, Any] = {
            "cache_mode": CacheMode.BYPASS,
            "markdown_generator": markdown_generator,
            "remove_overlay_elements": extra.get(
                "remove_overlay_elements",
                getattr(cfg, "remove_overlay_elements", True),
            ),
        }

        # CSS 选择器
        if css_selector:
            kwargs["css_selector"] = css_selector

        # 页面超时（毫秒）
        if timeout is not None:
            kwargs["page_timeout"] = timeout * 1000
        else:
            kwargs["page_timeout"] = getattr(cfg, "page_timeout", 60000)

        # 等待条件
        wait_for = extra.get("wait_for", getattr(cfg, "wait_for", ""))
        if wait_for:
            kwargs["wait_for"] = wait_for

        # 抓取前延迟
        delay = extra.get("delay_before_return_html", getattr(cfg, "delay_before_return_html", 0.0))
        if delay > 0:
            kwargs["delay_before_return_html"] = delay

        # JS 执行
        enable_js = extra.get("enable_js", getattr(cfg, "enable_js", False))
        if enable_js:
            js_code = extra.get("js_code", getattr(cfg, "js_code", []))
            if js_code:
                kwargs["js_code"] = js_code

        return CrawlerRunConfig(**kwargs)

    def _extract_markdown(self, result: Any) -> str:
        """从 CrawlResult 提取 Markdown 内容。

        优先使用 fit_markdown（经过过滤的高质量内容），
        其次使用 raw_markdown。

        Args:
            result: CrawlResult 对象

        Returns:
            Markdown 格式的正文内容
        """
        markdown = getattr(result, "markdown", None)
        if markdown is None:
            return ""

        # markdown 可能是字符串或 MarkdownGenerationResult 对象
        if isinstance(markdown, str):
            return markdown

        # 尝试 fit_markdown（过滤后内容）
        fit_markdown = getattr(markdown, "fit_markdown", None)
        if fit_markdown:
            return fit_markdown

        # 回退到 raw_markdown
        raw_markdown = getattr(markdown, "raw_markdown", None)
        if raw_markdown:
            return raw_markdown

        return ""

    def _extract_title(self, result: Any) -> str:
        """从 CrawlResult 提取页面标题。

        Args:
            result: CrawlResult 对象

        Returns:
            页面标题，无法提取时返回 "无标题"
        """
        # 优先从 metadata 提取
        metadata = getattr(result, "metadata", None)
        if metadata and isinstance(metadata, dict):
            title = metadata.get("title")
            if title:
                return title

        # 回退：从 cleaned_html 提取 <title> 标签
        cleaned_html = getattr(result, "cleaned_html", None)
        if cleaned_html:
            import re

            title_match = re.search(r"<title[^>]*>(.*?)</title>", cleaned_html, re.IGNORECASE | re.DOTALL)
            if title_match:
                return title_match.group(1).strip()

        return "无标题"

    def _get_crawl4ai_config(self) -> Any:
        """获取 crawl4ai 配置节。

        Returns:
            crawl4ai 配置节对象，配置缺失时返回 None
        """
        if self.config is None:
            return None
        return getattr(self.config, "crawl4ai", None)

    def _get_proxy_url(self) -> str | None:
        """从配置获取代理 URL。

        优先使用 SOCKS5 代理，其次 HTTP/HTTPS 代理。

        Returns:
            代理 URL 字符串，未配置代理时返回 None
        """
        if self.config is None:
            return None

        proxy_cfg = getattr(self.config, "proxy", None)
        if proxy_cfg is None or not getattr(proxy_cfg, "enable_proxy", False):
            return None

        socks5 = getattr(proxy_cfg, "socks5_proxy", None)
        if socks5:
            return socks5

        http_proxy = getattr(proxy_cfg, "http_proxy", None)
        https_proxy = getattr(proxy_cfg, "https_proxy", None)
        return http_proxy or https_proxy

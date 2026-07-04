"""Trafilatura 引擎实现。

基于 [trafilatura](https://trafilatura.readthedocs.io/) 库的轻量 URL 解析引擎，
使用 httpx 进行异步 HTML 抓取，trafilatura 进行正文提取和元数据解析。

无需浏览器环境，适用于静态 HTML 页面，资源占用低、启动快。
是 Crawl4AI 渲染型引擎的轻量替代方案，适合作为默认回退引擎。
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from src.kernel.logger import get_logger

from .base import BaseParseEngine, ParseResult

if TYPE_CHECKING:
    from ..config import UrlParserConfig
    from trafilatura.settings import Document

logger = get_logger("trafilatura_engine")

# trafilatura output_format 到 ParseResult content_format 的映射
_FORMAT_MAP: dict[str, str] = {
    "markdown": "markdown",
    "txt": "text",
    "html": "html",
    "xml": "text",
    "json": "text",
    "csv": "text",
}


class TrafilaturaEngine(BaseParseEngine):
    """基于 trafilatura 的 URL 解析引擎。

    使用 httpx 异步抓取 HTML，trafilatura 提取正文内容和元数据。
    输出 Markdown 格式正文（可配置），附带标题、作者、日期等元数据。

    无需浏览器环境，适用于静态内容页面。对于需要 JavaScript 渲染的动态页面，
    请使用 Crawl4AI 引擎。

    Attributes:
        engine_name: 引擎名称标识
    """

    engine_name: str = "trafilatura"

    def is_available(self) -> bool:
        """检查 trafilatura 引擎是否可用。

        通过尝试导入 trafilatura 和 httpx 库来判断可用性。

        Returns:
            bool: 两个依赖均已安装则返回 True
        """
        try:
            import trafilatura  # noqa: F401
            import httpx  # noqa: F401

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
        """使用 trafilatura 解析 URL。

        流程：
        1. httpx 异步抓取 HTML
        2. 若指定 CSS 选择器，用 BeautifulSoup 预过滤
        3. trafilatura ``bare_extraction`` 提取正文和元数据（在线程中执行）

        Args:
            url: 要解析的 URL
            css_selector: CSS 选择器，提取页面特定区域（通过 BeautifulSoup 预过滤实现）
            timeout: 超时时间（秒），None 使用配置默认值
            extra_options: 额外选项，可覆盖以下键：
                - output_format: 输出格式（markdown/txt/html）
                - include_comments: 是否包含评论
                - include_tables: 是否包含表格
                - include_links: 是否保留链接
                - deduplicate: 是否去重
                - target_language: 目标语言（ISO 639-1）
                - user_agent: 自定义 User-Agent

        Returns:
            ParseResult: 解析结果对象
        """
        try:
            # 1. 异步抓取 HTML
            html, fetch_metadata = await self._fetch_html(url, timeout, extra_options)
            if not html:
                return ParseResult.failure(url, self.engine_name, "无法获取页面内容（HTTP 请求失败或返回空内容）")

            # 2. CSS 选择器预过滤
            effective_format = "markdown"
            if css_selector:
                html = self._apply_css_selector(html, css_selector)
                if not html:
                    return ParseResult.failure(
                        url, self.engine_name, f"CSS 选择器 '{css_selector}' 未匹配到任何内容"
                    )

            # 3. trafilatura 提取（在线程中执行避免阻塞事件循环）
            extraction_result = await asyncio.to_thread(
                self._extract, html, url, extra_options
            )

            if extraction_result is None:
                return ParseResult.failure(url, self.engine_name, "trafilatura 无法从页面提取有效内容")

            content, title, extract_metadata, effective_format = extraction_result
            if not content:
                return ParseResult.failure(url, self.engine_name, "提取的内容为空")

            # 合并抓取元数据和提取元数据
            metadata: dict[str, object] = {}
            metadata.update(fetch_metadata)
            metadata.update(extract_metadata)

            logger.info(f"trafilatura 成功解析 '{url}'，内容长度: {len(content)}")

            return ParseResult(
                url=url,
                title=title or "无标题",
                content=content,
                content_format=_FORMAT_MAP.get(effective_format, "text"),
                metadata=metadata,
                engine=self.engine_name,
                success=True,
            )

        except Exception as e:
            logger.error(f"trafilatura 解析 '{url}' 时发生异常: {e}", exc_info=True)
            return ParseResult.failure(url, self.engine_name, f"引擎异常: {e!s}")

    async def close(self) -> None:
        """释放引擎资源。

        trafilatura 引擎无持久化资源（httpx 客户端按请求创建销毁），无需特殊清理。
        """
        pass

    # ── 内部方法 ────────────────────────────────────────────────

    async def _fetch_html(
        self,
        url: str,
        timeout: int | None,
        extra_options: dict[str, Any] | None,
    ) -> tuple[str, dict[str, int | str]]:
        """使用 httpx 异步抓取 HTML。

        Args:
            url: 要抓取的 URL
            timeout: 超时覆盖（秒）
            extra_options: 额外选项，可覆盖 user_agent

        Returns:
            (HTML 内容字符串, 抓取元数据字典) 元组，元数据包含 status_code 与 redirected_url

        Raises:
            httpx.HTTPError: HTTP 请求失败时抛出
        """
        import httpx

        cfg: UrlParserConfig.TrafilaturaSection | None = (
            self.config.trafilatura if self.config is not None else None
        )
        extra: dict[str, Any] = extra_options or {}

        # 构建请求参数
        default_timeout: int = cfg.timeout if cfg is not None else 15
        request_timeout: int = timeout if timeout is not None else default_timeout

        follow_redirects: bool = cfg.follow_redirects if cfg is not None else True

        default_ua: str = cfg.user_agent if cfg is not None else ""
        user_agent: str = extra.get("user_agent", default_ua) or "Mozilla/5.0 (compatible; UrlParser/1.0)"

        headers: dict[str, str] = {"User-Agent": user_agent}

        # 构建 client kwargs（解包给 httpx.AsyncClient，值类型异构）
        client_kwargs: dict[str, Any] = {
            "timeout": request_timeout,
            "follow_redirects": follow_redirects,
            "headers": headers,
        }

        # 代理配置：直接从配置节读取，优先 SOCKS5，其次 HTTP/HTTPS
        proxy_url: str | None = None
        if self.config is not None:
            proxy_cfg = self.config.proxy
            if proxy_cfg.enable_proxy:
                proxy_url = proxy_cfg.socks5_proxy or proxy_cfg.http_proxy or proxy_cfg.https_proxy
        if proxy_url:
            client_kwargs["proxy"] = proxy_url

        metadata: dict[str, int | str] = {}

        try:
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(url)
                response.raise_for_status()
                html: str = response.text
                metadata["status_code"] = response.status_code
                redirected = str(response.url)
                if redirected != url:
                    metadata["redirected_url"] = redirected
        except TypeError:
            # httpx < 0.26 使用 'proxies' 而非 'proxy'
            proxy_val = client_kwargs.pop("proxy", None)
            if proxy_val:
                client_kwargs["proxies"] = proxy_val
            async with httpx.AsyncClient(**client_kwargs) as client:
                response = await client.get(url)
                response.raise_for_status()
                html = response.text
                metadata["status_code"] = response.status_code
                redirected = str(response.url)
                if redirected != url:
                    metadata["redirected_url"] = redirected

        return html, metadata

    def _apply_css_selector(self, html: str, css_selector: str) -> str:
        """使用 BeautifulSoup 应用 CSS 选择器提取特定区域。

        将匹配到的元素拼装为 HTML 片段，再交由 trafilatura 提取。
        注意：预过滤后 trafilatura 会失去全页上下文，可能影响元数据提取质量。

        Args:
            html: 原始 HTML
            css_selector: CSS 选择器字符串

        Returns:
            匹配区域的 HTML 字符串，无匹配时返回空字符串
        """
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        elements = soup.select(css_selector)
        if not elements:
            return ""
        return "".join(str(el) for el in elements)

    def _extract(
        self,
        html: str,
        url: str,
        extra_options: dict[str, Any] | None,
    ) -> tuple[str, str, dict[str, str | list[str]], str] | None:
        """使用 trafilatura 提取正文和元数据（同步方法，在线程中调用）。

        Args:
            html: HTML 内容
            url: 页面 URL（辅助元数据提取）
            extra_options: 额外选项覆盖

        Returns:
            (content, title, metadata, output_format) 元组，提取失败返回 None

        Raises:
            ValueError: trafilatura 提取过程中发生错误
        """
        from trafilatura import bare_extraction
        from trafilatura.settings import Document

        cfg: UrlParserConfig.TrafilaturaSection | None = (
            self.config.trafilatura if self.config is not None else None
        )
        extra: dict[str, Any] = extra_options or {}

        # 从配置和 extra_options 构建提取参数
        output_format: str = extra.get(
            "output_format",
            cfg.output_format if cfg is not None else "markdown",
        )

        kwargs: dict[str, Any] = {
            "url": url,
            "output_format": output_format,
            "include_comments": extra.get(
                "include_comments",
                cfg.include_comments if cfg is not None else False,
            ),
            "include_tables": extra.get(
                "include_tables",
                cfg.include_tables if cfg is not None else True,
            ),
            "include_links": extra.get(
                "include_links",
                cfg.include_links if cfg is not None else False,
            ),
            "deduplicate": extra.get(
                "deduplicate",
                cfg.deduplicate if cfg is not None else True,
            ),
            "with_metadata": True,
        }

        target_lang: str = extra.get(
            "target_language",
            cfg.target_language if cfg is not None else "",
        )
        if target_lang:
            kwargs["target_language"] = target_lang

        # prune_xpath 支持（extra_options 或配置）
        prune_xpath: str | list[str] | None = extra.get(
            "prune_xpath",
            None,  # trafilatura 配置节未暴露 prune_xpath，仅支持 extra_options 覆盖
        )
        if prune_xpath:
            kwargs["prune_xpath"] = prune_xpath

        doc = bare_extraction(html, **kwargs)
        if doc is None:
            return None

        # bare_extraction 默认 as_dict=False，返回 Document 对象
        if not isinstance(doc, Document):
            return None

        content: str = doc.raw_text or doc.text or ""
        title: str = doc.title or ""

        # 构建元数据：直接访问 Document 的类型化属性
        metadata: dict[str, str | list[str]] = {}

        author = doc.author
        if author:
            metadata["author"] = author
        date = doc.date
        if date:
            metadata["date"] = date
        sitename = doc.sitename
        if sitename:
            metadata["sitename"] = sitename
        description = doc.description
        if description:
            metadata["description"] = description
        language = doc.language
        if language:
            metadata["language"] = language
        hostname = doc.hostname
        if hostname:
            metadata["hostname"] = hostname
        image = doc.image
        if image:
            metadata["image"] = image
        fingerprint = doc.fingerprint
        if fingerprint:
            metadata["fingerprint"] = fingerprint

        categories = doc.categories
        if categories:
            metadata["categories"] = categories

        tags = doc.tags
        if tags:
            metadata["tags"] = tags

        return content, title, metadata, output_format

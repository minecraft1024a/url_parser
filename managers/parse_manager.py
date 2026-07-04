"""URL 解析管理器。

核心调度组件，负责站点路由匹配、引擎选择与排序、回退策略和结果聚合。
由 Tool 和 Service 组件共享实例，不向框架注册。
"""

from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from src.kernel.logger import get_logger

from ..engines.base import BaseParseEngine, ParseResult
from ..engines.crawl4ai_engine import Crawl4AIEngine
from ..engines.trafilatura_engine import TrafilaturaEngine
from ..utils.site_matcher import SiteMatcher
from ..utils.url_utils import is_valid_url, truncate_content

if TYPE_CHECKING:
    from ..config import UrlParserConfig

logger = get_logger("parse_manager")


class ParseResponse:
    """管理器输出给上层组件的解析响应。

    在 ParseResult 基础上增加路由信息（命中的站点规则名称）。

    Attributes:
        url: 原始请求 URL
        title: 页面标题
        content: 正文内容（已截断）
        content_format: 内容格式
        engine_used: 实际使用的引擎名称
        rule_matched: 命中的站点规则名称（无则为 None）
        metadata: 元数据
        success: 是否成功
        error: 错误信息
    """

    def __init__(
        self,
        url: str,
        title: str,
        content: str,
        content_format: str = "markdown",
        engine_used: str = "",
        rule_matched: str | None = None,
        metadata: dict[str, Any] | None = None,
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """初始化解析响应。

        Args:
            url: 原始请求 URL
            title: 页面标题
            content: 正文内容
            content_format: 内容格式
            engine_used: 实际使用的引擎
            rule_matched: 命中的规则名称
            metadata: 元数据
            success: 是否成功
            error: 错误信息
        """
        self.url: str = url
        self.title: str = title
        self.content: str = content
        self.content_format: str = content_format
        self.engine_used: str = engine_used
        self.rule_matched: str | None = rule_matched
        self.metadata: dict[str, Any] = metadata or {}
        self.success: bool = success
        self.error: str | None = error

    @classmethod
    def from_result(
        cls,
        result: ParseResult,
        rule_matched: str | None = None,
    ) -> "ParseResponse":
        """从 ParseResult 创建 ParseResponse。

        Args:
            result: 引擎返回的解析结果
            rule_matched: 命中的站点规则名称

        Returns:
            ParseResponse 实例
        """
        return cls(
            url=result.url,
            title=result.title,
            content=result.content,
            content_format=result.content_format,
            engine_used=result.engine,
            rule_matched=rule_matched,
            metadata=result.metadata,
            success=result.success,
            error=result.error,
        )

    @classmethod
    def failure(cls, url: str, error: str) -> "ParseResponse":
        """创建一个失败响应。

        Args:
            url: 解析失败的 URL
            error: 错误信息

        Returns:
            标记为失败的 ParseResponse 实例
        """
        return cls(
            url=url,
            title="",
            content="",
            success=False,
            error=error,
        )


class ParseManager:
    """URL 解析管理器，负责引擎调度和站点路由。

    持有引擎实例字典和编译后的站点规则，在插件加载时初始化。
    由 Tool 和 Service 组件共享实例。

    Examples:
        >>> manager = ParseManager(config)
        >>> response = await manager.parse("https://example.com")
        >>> print(response.title)
    """

    def __init__(self, config: "UrlParserConfig | None" = None) -> None:
        """初始化解析管理器。

        Args:
            config: 插件配置对象
        """
        self.config = config
        self.engines: dict[str, BaseParseEngine] = {}
        self._site_matcher: SiteMatcher | None = None

        self._init_engines()
        self._init_site_rules()

    def _init_engines(self) -> None:
        """初始化所有引擎实例并注册到字典。"""
        self.engines = {
            "crawl4ai": Crawl4AIEngine(self.config),
            "trafilatura": TrafilaturaEngine(self.config),
        }

        # 报告引擎可用性
        for name, engine in self.engines.items():
            available = engine.is_available()
            status = "✅ 可用" if available else "❌ 不可用"
            logger.info(f"引擎 '{name}': {status}")

    def _init_site_rules(self) -> None:
        """从配置加载站点规则并编译。"""
        if self.config is None:
            self._site_matcher = SiteMatcher([])
            return

        site_rules_cfg = getattr(self.config, "site_rules", None)
        if site_rules_cfg is None:
            self._site_matcher = SiteMatcher([])
            return

        # site_rules.items 为 SiteRuleEntry 实例列表，转换为字典列表
        # 供 SiteMatcher.from_config 使用
        items = getattr(site_rules_cfg, "items", [])
        rules_data: list[dict[str, Any]] = []
        for item in items:
            if hasattr(item, "model_dump"):
                rules_data.append(item.model_dump())
            elif isinstance(item, dict):
                rules_data.append(item)

        self._site_matcher = SiteMatcher.from_config(rules_data)

        logger.info(f"已加载 {len(rules_data)} 条站点规则")

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
        6. 后处理（截断）

        Args:
            url: 要解析的 URL
            engine: 强制指定引擎名称，None 则走站点路由 + 全局回退
            css_selector: CSS 选择器覆盖
            timeout: 超时覆盖（秒）

        Returns:
            ParseResponse: 解析响应对象
        """
        # 1. URL 校验
        if not url or not url.strip():
            return ParseResponse.failure(url or "", "URL 不能为空")

        url = url.strip()
        if not is_valid_url(url):
            return ParseResponse.failure(url, "URL 格式无效，必须以 http:// 或 https:// 开头")

        # 2. 引擎选择
        if engine:
            # 强制指定引擎
            return await self._parse_with_engine(
                url, engine, css_selector=css_selector, timeout=timeout, rule_matched=None,
            )

        # 3. 站点规则匹配
        if self._site_matcher is not None:
            rule = self._site_matcher.match(url)
            if rule:
                logger.info(f"URL '{url}' 命中规则 '{rule.name}'，使用引擎 '{rule.engine}'")
                # 合并规则参数与调用参数（调用参数优先）
                effective_css = css_selector or rule.css_selector
                effective_timeout = timeout
                result = await self._parse_with_engine(
                    url,
                    rule.engine,
                    css_selector=effective_css,
                    timeout=effective_timeout,
                    extra_options=rule.extra_options or None,
                    rule_matched=rule.name,
                )

                # 站点规则引擎不可用或失败时，降级到全局回退
                if not result.success:
                    logger.warning(
                        f"规则 '{rule.name}' 指定的引擎 '{rule.engine}' 解析失败，降级到全局回退"
                    )
                    return await self._parse_with_fallback(
                        url, css_selector=css_selector, timeout=timeout, rule_matched=rule.name,
                    )

                return result

        # 4. 全局引擎顺序回退
        return await self._parse_with_fallback(url, css_selector=css_selector, timeout=timeout)

    async def parse_batch(
        self,
        urls: list[str],
        *,
        engine: str | None = None,
        css_selector: str | None = None,
        timeout: int | None = None,
    ) -> list[ParseResponse]:
        """并发解析多个 URL。

        单个 URL 失败不影响其他 URL。

        Args:
            urls: URL 列表
            engine: 强制指定引擎
            css_selector: CSS 选择器覆盖
            timeout: 超时覆盖

        Returns:
            ParseResponse 列表，顺序与输入一致
        """
        if not urls:
            return []

        tasks = [
            self.parse(url, engine=engine, css_selector=css_selector, timeout=timeout)
            for url in urls
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        responses: list[ParseResponse] = []
        for i, result in enumerate(results):
            if isinstance(result, ParseResponse):
                responses.append(result)
            elif isinstance(result, Exception):
                url = urls[i] if i < len(urls) else ""
                logger.error(f"解析 '{url}' 时发生未捕获异常: {result}")
                responses.append(ParseResponse.failure(url, f"未捕获异常: {result!s}"))
            else:
                url = urls[i] if i < len(urls) else ""
                responses.append(ParseResponse.failure(url, "未知错误"))

        return responses

    def get_available_engines(self) -> list[str]:
        """返回所有可用引擎名称。

        Returns:
            可用引擎名称列表
        """
        return [name for name, engine in self.engines.items() if engine.is_available()]

    async def get_engine_status(self, engine_name: str) -> dict[str, Any]:
        """获取指定引擎的状态信息。

        Args:
            engine_name: 引擎名称

        Returns:
            包含引擎状态信息的字典
        """
        engine = self.engines.get(engine_name)
        if not engine:
            return {
                "engine": engine_name,
                "exists": False,
                "available": False,
                "error": "引擎不存在",
            }

        return {
            "engine": engine_name,
            "exists": True,
            "available": engine.is_available(),
            "type": engine.__class__.__name__,
        }

    async def close(self) -> None:
        """关闭所有引擎，释放资源。"""
        for engine in self.engines.values():
            try:
                await engine.close()
            except Exception as e:
                logger.warning(f"关闭引擎时出错: {e}")
        logger.info("所有引擎已关闭")

    # ── 内部方法 ────────────────────────────────────────────────

    async def _parse_with_engine(
        self,
        url: str,
        engine_name: str,
        *,
        css_selector: str | None = None,
        timeout: int | None = None,
        extra_options: dict[str, Any] | None = None,
        rule_matched: str | None = None,
    ) -> ParseResponse:
        """使用指定引擎解析 URL。

        Args:
            url: 要解析的 URL
            engine_name: 引擎名称
            css_selector: CSS 选择器
            timeout: 超时
            extra_options: 额外选项
            rule_matched: 命中的规则名称

        Returns:
            ParseResponse 实例
        """
        engine = self.engines.get(engine_name)
        if not engine:
            return ParseResponse.failure(
                url, f"引擎 '{engine_name}' 不存在",
            )

        if not engine.is_available():
            return ParseResponse.failure(
                url, f"引擎 '{engine_name}' 不可用",
            )

        try:
            result = await engine.parse(
                url,
                css_selector=css_selector,
                timeout=timeout,
                extra_options=extra_options,
            )

            # 后处理：内容截断
            if result.success and result.content:
                result.content = self._truncate(result.content)

            return ParseResponse.from_result(result, rule_matched=rule_matched)

        except Exception as e:
            logger.error(f"引擎 '{engine_name}' 解析 '{url}' 时发生异常: {e}", exc_info=True)
            return ParseResponse.failure(url, f"引擎 '{engine_name}' 异常: {e!s}")

    async def _parse_with_fallback(
        self,
        url: str,
        *,
        css_selector: str | None = None,
        timeout: int | None = None,
        rule_matched: str | None = None,
    ) -> ParseResponse:
        """按全局引擎顺序回退解析。

        Args:
            url: 要解析的 URL
            css_selector: CSS 选择器
            timeout: 超时
            rule_matched: 命中的规则名称（用于日志）

        Returns:
            ParseResponse 实例
        """
        engine_order = self._get_engine_order()

        if not engine_order:
            return ParseResponse.failure(url, "没有配置可用引擎")

        errors: list[str] = []
        for engine_name in engine_order:
            engine = self.engines.get(engine_name)
            if not engine:
                logger.debug(f"引擎 '{engine_name}' 不存在，跳过")
                continue

            if not engine.is_available():
                logger.debug(f"引擎 '{engine_name}' 不可用，跳过")
                continue

            logger.debug(f"尝试使用引擎 '{engine_name}' 解析 '{url}'")
            try:
                result = await engine.parse(
                    url,
                    css_selector=css_selector,
                    timeout=timeout,
                )

                if result.success:
                    # 后处理：内容截断
                    if result.content:
                        result.content = self._truncate(result.content)

                    logger.info(f"引擎 '{engine_name}' 成功解析 '{url}'")
                    return ParseResponse.from_result(result, rule_matched=rule_matched)
                else:
                    error_msg = result.error or "未知错误"
                    errors.append(f"{engine_name}: {error_msg}")
                    logger.warning(f"引擎 '{engine_name}' 解析失败: {error_msg}")

            except Exception as e:
                errors.append(f"{engine_name}: {e!s}")
                logger.warning(f"引擎 '{engine_name}' 解析异常: {e}")
                continue

        return ParseResponse.failure(
            url,
            f"所有引擎均解析失败 ({'; '.join(errors)})",
        )

    def _get_engine_order(self) -> list[str]:
        """获取引擎使用顺序。

        Returns:
            引擎名称列表
        """
        if self.config is None:
            return list(self.engines.keys())

        engines_cfg = getattr(self.config, "engines", None)
        if engines_cfg is None:
            return list(self.engines.keys())

        order = getattr(engines_cfg, "engine_order", [])
        return list(order) if order else list(self.engines.keys())

    def _truncate(self, content: str) -> str:
        """按配置截断内容。

        Args:
            content: 原始内容

        Returns:
            截断后的内容
        """
        if self.config is None:
            return content

        engines_cfg = getattr(self.config, "engines", None)
        if engines_cfg is None:
            return content

        max_length = getattr(engines_cfg, "max_content_length", 8000)
        return truncate_content(content, max_length)

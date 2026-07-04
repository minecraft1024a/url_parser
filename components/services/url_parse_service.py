"""URL 解析服务组件。

供其他插件程序化调用的 Service 组件，返回结构化数据。
通过服务签名 ``url_parser:service:url_parse`` 获取实例。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

from src.core.components.base.service import BaseService
from src.kernel.logger import get_logger

from ...managers.parse_manager import ParseManager, ParseResponse

if TYPE_CHECKING:
    from src.core.components.base import BasePlugin

logger = get_logger("url_parse_service")


class URLParseService(BaseService):
    """URL 解析服务。

    提供程序化的 URL 解析能力，支持多引擎和站点路由。
    始终返回完整内容，由配置项 ``engines.max_content_length`` 控制截断长度。

    Examples:
        >>> service = service_manager.get_service("url_parser:service:url_parse")
        >>> response = await service.parse("https://example.com")
        >>> print(response.title)
        >>> print(response.content)
    """

    service_name: str = "url_parse"
    service_description: str = "URL 内容解析服务，支持多引擎和站点路由"
    version: str = "1.0.0"

    def __init__(self, plugin: "BasePlugin") -> None:
        """初始化 URL 解析服务。

        Args:
            plugin: 所属插件实例
        """
        super().__init__(plugin)

        # 类型安全地获取配置
        from ...config import UrlParserConfig

        config = plugin.config if isinstance(plugin.config, UrlParserConfig) else None
        self._manager: ParseManager = ParseManager(config)

        logger.info("URL 解析服务已初始化")

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
            timeout: 超时覆盖（秒）

        Returns:
            ParseResponse: 解析响应对象
        """
        if not url or not url.strip():
            return ParseResponse.failure(url or "", "URL 不能为空")

        return await self._manager.parse(
            url.strip(),
            engine=engine,
            css_selector=css_selector,
            timeout=timeout,
        )

    async def parse_batch(
        self,
        urls: list[str],
        *,
        engine: str | None = None,
        css_selector: str | None = None,
        timeout: int | None = None,
    ) -> list[ParseResponse]:
        """批量解析多个 URL（并发执行）。

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

        return await self._manager.parse_batch(
            urls,
            engine=engine,
            css_selector=css_selector,
            timeout=timeout,
        )

    def get_available_engines(self) -> list[str]:
        """获取当前可用的引擎列表。

        Returns:
            可用引擎名称列表
        """
        return self._manager.get_available_engines()

    async def get_engine_status(self, engine_name: str) -> dict[str, Any]:
        """获取指定引擎的状态信息。

        Args:
            engine_name: 引擎名称

        Returns:
            包含引擎状态信息的字典
        """
        return await self._manager.get_engine_status(engine_name)

    async def close(self) -> None:
        """关闭服务，释放引擎资源。"""
        await self._manager.close()

"""URL Parser 插件入口。

提供 URL 内容解析功能，支持多引擎（首个引擎为 Crawl4AI）和站点级路由。
同时暴露 Tool 组件（供 LLM 调用）和 Service 组件（供其他插件调用）。
"""

from typing import TYPE_CHECKING

from src.kernel.logger import get_logger
from src.core.components import BasePlugin, register_plugin

from .config import UrlParserConfig
from .components.tools.url_parser import URLParserTool
from .components.services.url_parse_service import URLParseService

if TYPE_CHECKING:
    pass

logger = get_logger("url_parser_plugin")


@register_plugin
class URLParserPlugin(BasePlugin):
    """URL 解析工具插件。

    提供可扩展的多引擎 URL 解析能力，支持站点级路由和引擎有序回退。

    组件：
    - URLParserTool: 供 LLM 调用的解析工具
    - URLParseService: 供其他插件调用的解析服务
    """

    # 插件基本信息（必需，必须与 manifest.json 中的 name 一致）
    plugin_name: str = "url_parser"
    plugin_description: str = "URL 内容解析插件，支持多引擎和站点级路由"
    plugin_version: str = "1.0.0"

    # 插件配置
    configs: list[type] = [UrlParserConfig]

    # 依赖组件
    dependent_components: list[str] = []

    async def on_plugin_loaded(self) -> None:
        """插件加载完成后的生命周期钩子。

        报告引擎可用性状态，不阻塞插件注册流程。
        """
        logger.info("🚀 URL Parser 插件正在初始化...")

        try:
            from .engines.crawl4ai_engine import Crawl4AIEngine

            # 类型安全地获取配置
            config = self.config if isinstance(self.config, UrlParserConfig) else None

            # 检查引擎可用性
            crawl4ai_engine = Crawl4AIEngine(config)
            available = crawl4ai_engine.is_available()

            if available:
                logger.info("✅ 引擎 Crawl4AI: 可用")
            else:
                logger.warning(
                    "❌ 引擎 Crawl4AI: 不可用（未安装 crawl4ai 或其依赖）。"
                    "请运行: uv add crawl4ai && crawl4ai-install"
                )

        except Exception as e:
            logger.error(f"❌ 引擎初始化检查失败: {e}", exc_info=True)

    async def on_plugin_unloaded(self) -> None:
        """插件卸载时的生命周期钩子。

        释放引擎持有的资源（如浏览器实例）。
        """
        logger.info("🔄 URL Parser 插件正在卸载...")

        try:
            # 通过 Service 或 Tool 的管理器释放资源
            # 这里直接创建临时管理器来关闭引擎（因为 Tool/Service 实例由框架管理）
            from .managers.parse_manager import ParseManager

            config = self.config if isinstance(self.config, UrlParserConfig) else None
            manager = ParseManager(config)
            await manager.close()
            logger.info("✅ URL Parser 插件已卸载")
        except Exception as e:
            logger.error(f"插件卸载时出错: {e}", exc_info=True)

    def get_components(self) -> list[type]:
        """获取插件组件列表。

        根据配置中的组件开关决定返回哪些组件类。

        Returns:
            插件内所有组件类的列表
        """
        components: list[type] = []

        # 从配置读取组件启用状态
        if self.config and isinstance(self.config, UrlParserConfig):
            if self.config.components.enable_url_parser_tool:
                components.append(URLParserTool)
            if self.config.components.enable_url_parser_service:
                components.append(URLParseService)
        else:
            # 如果没有配置，默认启用所有组件
            components.extend([URLParserTool, URLParseService])

        return components

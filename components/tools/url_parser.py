"""URL 内容解析工具组件。

供 LLM 调用的 Tool 组件，接收 URL 字符串，返回格式化文本。
始终返回完整内容，由配置项 ``engines.max_content_length`` 控制截断长度。
"""

from __future__ import annotations

from typing import Annotated, Any, TYPE_CHECKING

from src.core.components.base.tool import BaseTool
from src.kernel.logger import get_logger

from ...managers.parse_manager import ParseManager
from ...utils.formatters import format_parse_responses
from ...utils.url_utils import parse_urls_from_input, validate_urls

if TYPE_CHECKING:
    from src.core.components.base import BasePlugin

logger = get_logger("url_parser_tool")


class URLParserTool(BaseTool):
    """URL 内容解析工具。

    供 LLM 调用，解析一个或多个网页 URL，提取页面标题和正文内容。
    始终返回完整内容，由配置项控制截断长度。

    Examples:
        用户: "帮我看看这个网页 https://example.com/article"
        LLM: [自动调用 parse_url 工具]
    """

    tool_name: str = "parse_url"
    tool_description: str = (
        "解析一个或多个网页URL，提取页面标题和正文内容。"
        "使用场景：用户发送了网页链接并希望了解其内容时调用。"
        "支持多个URL（用逗号分隔）。返回 Markdown 格式的内容。"
    )

    def __init__(self, plugin: "BasePlugin") -> None:
        """初始化 URL 解析工具。

        Args:
            plugin: 所属插件实例
        """
        super().__init__(plugin)

        # 类型安全地获取配置
        from ...config import UrlParserConfig

        config = plugin.config if isinstance(plugin.config, UrlParserConfig) else None
        self._manager: ParseManager = ParseManager(config)

    async def execute(
        self,
        urls: Annotated[str, "要解析的URL，多个URL用逗号分隔"],
    ) -> tuple[bool, str | dict[str, Any]]:
        """解析 URL 内容。

        始终返回完整内容，由配置项 ``engines.max_content_length`` 控制截断长度。

        Args:
            urls: 要解析的 URL 字符串，支持逗号分隔多个

        Returns:
            (是否成功, 格式化文本结果或错误信息)
        """
        if not urls or not urls.strip():
            return False, "请提供要解析的 URL。"

        # 解析 URL 输入
        url_list = parse_urls_from_input(urls)
        if not url_list:
            return False, "输入中未找到有效的 URL。"

        # 验证 URL 格式
        valid_urls = validate_urls(url_list)
        if not valid_urls:
            return False, "未找到有效的 URL（必须以 http:// 或 https:// 开头）。"

        logger.info(f"开始解析 {len(valid_urls)} 个 URL: {valid_urls}")

        # 批量解析
        try:
            responses = await self._manager.parse_batch(valid_urls)

            # 检查是否有成功的结果
            success_responses = [r for r in responses if r.success]
            if not success_responses:
                # 全部失败
                errors = [r.error or "未知错误" for r in responses]
                return False, f"所有 URL 解析失败: {'; '.join(errors)}"

            # 格式化成功结果
            formatted = format_parse_responses(success_responses)

            # 如果有部分失败，附加错误信息
            failed_responses = [r for r in responses if not r.success]
            if failed_responses:
                error_msgs = [f"{r.url}: {r.error}" for r in failed_responses]
                formatted += f"\n\n--- 以下 URL 解析失败 ---\n" + "\n".join(error_msgs)

            return True, formatted

        except Exception as e:
            logger.error(f"执行 URL 解析时发生异常: {e}", exc_info=True)
            return False, f"解析过程中发生错误: {e!s}"

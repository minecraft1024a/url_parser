"""解析结果格式化工具。

提供将 ParseResponse 格式化为可读文本的工具函数。
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..managers.parse_manager import ParseResponse


def format_parse_response(response: "ParseResponse") -> str:
    """将单个解析响应格式化为可读文本。

    Args:
        response: 解析响应对象

    Returns:
        格式化后的文本
    """
    if not response.success:
        return f"解析失败: {response.error or '未知错误'}\nURL: {response.url}"

    lines: list[str] = [
        f"标题: {response.title}",
        f"URL: {response.url}",
        f"引擎: {response.engine_used}",
    ]

    if response.rule_matched:
        lines.append(f"匹配规则: {response.rule_matched}")

    lines.append("")
    lines.append("内容:")
    lines.append(response.content)

    return "\n".join(lines)


def format_parse_responses(responses: list["ParseResponse"]) -> str:
    """将多个解析响应格式化为可读文本。

    多个结果之间用分隔线连接。

    Args:
        responses: 解析响应列表

    Returns:
        格式化后的文本
    """
    if not responses:
        return "没有解析结果。"

    if len(responses) == 1:
        return format_parse_response(responses[0])

    formatted_parts: list[str] = []
    for i, response in enumerate(responses, 1):
        header = f"─── 结果 {i}/{len(responses)} ───"
        body = format_parse_response(response)
        formatted_parts.append(f"{header}\n{body}")

    return "\n\n".join(formatted_parts)


def response_to_dict(response: "ParseResponse") -> dict[str, Any]:
    """将解析响应转换为字典。

    Args:
        response: 解析响应对象

    Returns:
        包含所有字段的字典
    """
    return {
        "url": response.url,
        "title": response.title,
        "content": response.content,
        "content_format": response.content_format,
        "engine_used": response.engine_used,
        "rule_matched": response.rule_matched,
        "metadata": response.metadata,
        "success": response.success,
        "error": response.error,
    }

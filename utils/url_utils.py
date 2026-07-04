"""URL 处理工具函数。

提供 URL 校验、提取和域名解析等工具函数。
"""

from __future__ import annotations

import re
from urllib.parse import urlparse


def parse_urls_from_input(urls_input: str | list[str]) -> list[str]:
    """从输入中解析 URL 列表。

    支持以下输入格式：
    - 字符串：自动提取所有 HTTP/HTTPS URL（逗号、空格分隔均可）
    - 列表：直接过滤有效字符串

    Args:
        urls_input: URL 输入，可以是字符串或字符串列表

    Returns:
        解析出的 URL 列表
    """
    if isinstance(urls_input, str):
        # 从字符串中提取所有 HTTP/HTTPS URL
        url_pattern = r"https?://[^\s,\]\)]+"
        urls = re.findall(url_pattern, urls_input)
        if not urls:
            # 没有找到标准 URL，检查是否整个字符串是单个 URL
            stripped = urls_input.strip()
            if stripped.startswith(("http://", "https://")):
                urls = [stripped]
            else:
                return []
    elif isinstance(urls_input, list):
        urls = [url.strip() for url in urls_input if isinstance(url, str) and url.strip()]
    else:
        return []

    return urls


def validate_urls(urls: list[str]) -> list[str]:
    """验证 URL 格式，返回有效的 URL 列表。

    Args:
        urls: 待验证的 URL 列表

    Returns:
        格式有效的 URL 列表
    """
    return [url for url in urls if is_valid_url(url)]


def is_valid_url(url: str) -> bool:
    """检查字符串是否为有效的 HTTP/HTTPS URL。

    Args:
        url: 待检查的字符串

    Returns:
        是否为有效 URL
    """
    if not url or not isinstance(url, str):
        return False

    if not url.startswith(("http://", "https://")):
        return False

    try:
        parsed = urlparse(url)
        return bool(parsed.netloc)
    except Exception:
        return False


def get_domain(url: str) -> str:
    """从 URL 中提取域名。

    Args:
        url: 完整 URL

    Returns:
        域名字符串，提取失败时返回空字符串

    Examples:
        >>> get_domain("https://www.example.com/path")
        'www.example.com'
        >>> get_domain("https://example.com")
        'example.com'
    """
    try:
        parsed = urlparse(url)
        return parsed.netloc.lower()
    except Exception:
        return ""


def truncate_content(content: str, max_length: int) -> str:
    """截断内容到指定长度。

    超过最大长度时截断并追加省略号。

    Args:
        content: 原始内容
        max_length: 最大字符数

    Returns:
        截断后的内容
    """
    if len(content) <= max_length:
        return content
    return content[:max_length] + "..."

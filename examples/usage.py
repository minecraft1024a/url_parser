"""URL Parser 插件使用示例。

演示如何通过 Service 组件调用 URL 解析功能。
运行前请确保已启用 url_parser 插件并配置好引擎。

注意：此示例需在 Neo-MoFox 运行环境中执行，
通过 ``python -m plugins.url_parser.examples.usage`` 或集成测试运行。
"""

from __future__ import annotations

import asyncio
from typing import Any

from src.core.managers import get_service_manager


async def _get_parse_service() -> Any:
    """获取 URLParseService 实例。

    Returns:
        URLParseService 实例，获取失败返回 None
    """
    service_manager = get_service_manager()
    return service_manager.get_service("url_parser:service:url_parse")


async def demo_single_parse() -> None:
    """演示解析单个 URL。"""
    print("=== 解析单个 URL ===")

    parse_service = await _get_parse_service()
    if parse_service is None:
        print("❌ 无法获取 URLParseService，请确保插件已启用")
        return

    # 基本解析（走站点路由 + 全局回退）
    response = await parse_service.parse("https://example.com")
    print(f"标题: {response.title}")
    print(f"引擎: {response.engine_used}")
    print(f"匹配规则: {response.rule_matched}")
    print(f"内容前 200 字符: {response.content[:200]}")
    print()


async def demo_parse_with_engine() -> None:
    """演示强制指定引擎解析。"""
    print("=== 强制指定引擎解析 ===")

    parse_service = await _get_parse_service()
    if parse_service is None:
        print("❌ 无法获取 URLParseService")
        return

    # 强制使用 crawl4ai 引擎，并指定 CSS 选择器
    response = await parse_service.parse(
        "https://news.example.com/article/123",
        engine="crawl4ai",
        css_selector="main.article-body",
        timeout=60,
    )

    if response.success:
        print(f"解析成功: {response.title}")
    else:
        print(f"解析失败: {response.error}")
    print()


async def demo_batch_parse() -> None:
    """演示批量解析多个 URL。"""
    print("=== 批量解析 ===")

    parse_service = await _get_parse_service()
    if parse_service is None:
        print("❌ 无法获取 URLParseService")
        return

    urls = [
        "https://example.com",
        "https://example.org",
        "https://example.net",
    ]

    responses = await parse_service.parse_batch(urls)

    for resp in responses:
        status = "✅" if resp.success else "❌"
        print(f"{status} {resp.url} -> {resp.title or resp.error}")
    print()


async def demo_engine_status() -> None:
    """演示检查引擎状态。"""
    print("=== 引擎状态 ===")

    parse_service = await _get_parse_service()
    if parse_service is None:
        print("❌ 无法获取 URLParseService")
        return

    # 获取所有可用引擎
    available = parse_service.get_available_engines()
    print(f"可用引擎: {available}")

    # 检查单个引擎状态
    for engine_name in ["crawl4ai", "httpx", "nonexistent"]:
        status = await parse_service.get_engine_status(engine_name)
        print(f"  {engine_name}: exists={status['exists']}, available={status['available']}")
    print()


async def demo_site_rule_routing() -> None:
    """演示站点规则路由（需在配置中设置 site_rules）。"""
    print("=== 站点规则路由 ===")

    parse_service = await _get_parse_service()
    if parse_service is None:
        print("❌ 无法获取 URLParseService")
        return

    # 假设配置中有针对 zhihu.com 的规则
    response = await parse_service.parse("https://www.zhihu.com/question/123456")

    if response.rule_matched:
        print(f"命中规则: {response.rule_matched}")
        print(f"使用引擎: {response.engine_used}")
    else:
        print("未命中任何站点规则，使用全局回退")
    print()


async def main() -> None:
    """运行所有示例。"""
    await demo_single_parse()
    await demo_parse_with_engine()
    await demo_batch_parse()
    await demo_engine_status()
    await demo_site_rule_routing()


if __name__ == "__main__":
    asyncio.run(main())

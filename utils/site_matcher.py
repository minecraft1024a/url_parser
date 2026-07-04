"""站点规则匹配引擎。

负责将 URL 匹配到对应的站点路由规则，支持域名匹配和正则匹配两种模式。
"""

from __future__ import annotations

import re
from typing import Any

from src.kernel.logger import get_logger

from .url_utils import get_domain

logger = get_logger("site_matcher")


class SiteRule:
    """站点路由规则。

    定义如何为匹配的 URL 选择引擎及参数。

    Attributes:
        name: 规则名称（用于日志和调试）
        match_type: 匹配类型 ("domain" 或 "regex")
        match_pattern: 域名或正则表达式
        engine: 使用的引擎名称
        css_selector: CSS 选择器（可选）
        extra_options: 引擎特定额外选项（可选）
        priority: 优先级，数值越大越优先匹配
    """

    def __init__(
        self,
        name: str,
        match_type: str,
        match_pattern: str,
        engine: str,
        css_selector: str | None = None,
        extra_options: dict[str, Any] | None = None,
        priority: int = 0,
    ) -> None:
        """初始化站点规则。

        Args:
            name: 规则名称
            match_type: 匹配类型，"domain" 或 "regex"
            match_pattern: 域名或正则表达式
            engine: 引擎名称
            css_selector: CSS 选择器
            extra_options: 额外选项
            priority: 优先级
        """
        self.name: str = name
        self.match_type: str = match_type
        self.match_pattern: str = match_pattern
        self.engine: str = engine
        self.css_selector: str | None = css_selector
        self.extra_options: dict[str, Any] = extra_options or {}
        self.priority: int = priority

        # 预编译正则表达式
        self._compiled_regex: re.Pattern[str] | None = None
        if match_type == "regex":
            try:
                self._compiled_regex = re.compile(match_pattern)
            except re.error as e:
                logger.error(f"站点规则 '{name}' 的正则表达式无效 '{match_pattern}': {e}")
                self._compiled_regex = None

    def matches(self, url: str) -> bool:
        """检查 URL 是否匹配此规则。

        Args:
            url: 待匹配的 URL

        Returns:
            是否匹配
        """
        if self.match_type == "domain":
            return self._match_domain(url)
        elif self.match_type == "regex":
            return self._match_regex(url)
        else:
            logger.warning(f"站点规则 '{self.name}' 的 match_type '{self.match_type}' 无效")
            return False

    def _match_domain(self, url: str) -> bool:
        """域名匹配：比较 URL 域名是否等于或以 match_pattern 结尾。

        Args:
            url: 待匹配的 URL

        Returns:
            是否匹配
        """
        domain = get_domain(url)
        if not domain or not self.match_pattern:
            return False

        # 精确匹配或后缀匹配（带点号边界）
        pattern = self.match_pattern.lower()
        domain = domain.lower()

        if domain == pattern:
            return True

        # 支持 "*.example.com" 通配符
        if pattern.startswith("*."):
            suffix = pattern[2:]
            return domain == suffix or domain.endswith("." + suffix)

        # 普通后缀匹配（确保是子域名）
        return domain.endswith("." + pattern)

    def _match_regex(self, url: str) -> bool:
        """正则匹配：用预编译的正则表达式匹配完整 URL。

        Args:
            url: 待匹配的 URL

        Returns:
            是否匹配
        """
        if self._compiled_regex is None:
            return False
        return bool(self._compiled_regex.search(url))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SiteRule":
        """从字典创建 SiteRule 实例。

        Args:
            data: 包含规则字段的字典

        Returns:
            SiteRule 实例
        """
        return cls(
            name=data.get("name", ""),
            match_type=data.get("match_type", "domain"),
            match_pattern=data.get("match_pattern", ""),
            engine=data.get("engine", ""),
            css_selector=data.get("css_selector"),
            extra_options=data.get("extra_options"),
            priority=data.get("priority", 0),
        )


class SiteMatcher:
    """站点规则匹配器。

    持有一组已编译的站点规则，按优先级降序排列，
    提供 URL 到规则的匹配能力。

    Examples:
        >>> rules = [SiteRule(name="github", match_type="domain", ...)]
        >>> matcher = SiteMatcher(rules)
        >>> rule = matcher.match("https://github.com/repo")
        >>> if rule:
        ...     print(f"命中规则: {rule.name}, 引擎: {rule.engine}")
    """

    def __init__(self, rules: list[SiteRule]) -> None:
        """初始化匹配器。

        Args:
            rules: 站点规则列表，会按 priority 降序排序
        """
        self._rules: list[SiteRule] = sorted(rules, key=lambda r: r.priority, reverse=True)

    def match(self, url: str) -> SiteRule | None:
        """匹配 URL 到第一个命中的规则。

        按 priority 降序遍历规则，返回第一个匹配的规则。

        Args:
            url: 待匹配的 URL

        Returns:
            命中的 SiteRule，无匹配时返回 None
        """
        for rule in self._rules:
            if rule.matches(url):
                logger.debug(f"URL '{url}' 命中规则 '{rule.name}'（引擎: {rule.engine}）")
                return rule

        return None

    @classmethod
    def from_config(cls, rules_data: list[dict[str, Any]]) -> "SiteMatcher":
        """从配置数据创建匹配器。

        Args:
            rules_data: 规则字典列表（来自配置 site_rules.rules）

        Returns:
            SiteMatcher 实例
        """
        rules: list[SiteRule] = []
        for data in rules_data:
            try:
                rule = SiteRule.from_dict(data)
                rules.append(rule)
                logger.debug(f"已加载站点规则: '{rule.name}' (type={rule.match_type}, engine={rule.engine})")
            except Exception as e:
                logger.error(f"加载站点规则失败: {e}", exc_info=True)

        return cls(rules)

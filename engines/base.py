"""URL 解析引擎基类。

定义所有解析引擎的统一契约：``BaseParseEngine`` 抽象基类和 ``ParseResult`` 结果模型。
所有引擎必须继承 ``BaseParseEngine`` 并实现 ``parse()`` 和 ``is_available()``。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from ..config import UrlParserConfig


class ParseResult:
    """引擎统一返回的解析结果。

    封装单个 URL 解析后的结构化数据，所有引擎必须返回此对象。

    Attributes:
        url: 实际解析的 URL（可能经过重定向）
        title: 页面标题
        content: 解析后的正文内容
        content_format: 内容格式 ("markdown" / "html" / "text")
        metadata: 额外元数据（状态码、响应头等）
        engine: 实际使用的引擎名称
        success: 是否成功
        error: 失败时的错误信息
    """

    def __init__(
        self,
        url: str,
        title: str,
        content: str,
        content_format: str = "markdown",
        metadata: dict[str, Any] | None = None,
        engine: str = "",
        success: bool = True,
        error: str | None = None,
    ) -> None:
        """初始化解析结果。

        Args:
            url: 实际解析的 URL
            title: 页面标题
            content: 解析后的正文内容
            content_format: 内容格式，默认为 "markdown"
            metadata: 额外元数据，默认为空字典
            engine: 引擎名称
            success: 是否成功，默认为 True
            error: 错误信息，默认为 None
        """
        self.url: str = url
        self.title: str = title
        self.content: str = content
        self.content_format: str = content_format
        self.metadata: dict[str, Any] = metadata or {}
        self.engine: str = engine
        self.success: bool = success
        self.error: str | None = error

    def to_dict(self) -> dict[str, Any]:
        """转换为字典表示。

        Returns:
            包含所有字段的字典
        """
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "content_format": self.content_format,
            "metadata": self.metadata,
            "engine": self.engine,
            "success": self.success,
            "error": self.error,
        }

    @classmethod
    def failure(cls, url: str, engine: str, error: str) -> "ParseResult":
        """创建一个失败结果。

        Args:
            url: 解析失败的 URL
            engine: 尝试使用的引擎名称
            error: 错误信息

        Returns:
            标记为失败的 ParseResult 实例
        """
        return cls(
            url=url,
            title="",
            content="",
            engine=engine,
            success=False,
            error=error,
        )


class BaseParseEngine(ABC):
    """URL 解析引擎抽象基类。

    所有引擎必须继承此类并实现 ``parse()`` 和 ``is_available()``。
    引擎实例应在构造时接收配置对象，运行时无状态。

    Class Attributes:
        engine_name: 引擎名称标识，必须与配置中的引擎名一致

    Examples:
        >>> class MyEngine(BaseParseEngine):
        ...     engine_name = "my_engine"
        ...
        ...     def is_available(self) -> bool:
        ...         return True
        ...
        ...     async def parse(self, url, *, css_selector=None, timeout=None, extra_options=None):
        ...         # 实现解析逻辑
        ...         return ParseResult(url=url, title="...", content="...", engine=self.engine_name)
    """

    engine_name: str = ""

    def __init__(self, config: "UrlParserConfig | None" = None) -> None:
        """初始化引擎。

        Args:
            config: 插件配置对象，引擎可从中读取自身专属配置节
        """
        self.config = config

    @abstractmethod
    async def parse(
        self,
        url: str,
        *,
        css_selector: str | None = None,
        timeout: int | None = None,
        extra_options: dict[str, Any] | None = None,
    ) -> ParseResult:
        """解析单个 URL，返回结构化结果。

        Args:
            url: 要解析的 URL
            css_selector: CSS 选择器，用于提取页面特定区域（可选）
            timeout: 超时时间（秒），None 使用引擎默认值
            extra_options: 引擎特定选项（可选），由站点规则或调用方传入

        Returns:
            ParseResult: 解析结果对象
        """
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查引擎是否可用（依赖已安装、配置已就绪）。

        Returns:
            bool: 是否可用
        """
        ...

    async def close(self) -> None:
        """释放引擎持有的资源（如浏览器实例、连接池）。

        默认空实现，有资源管理的引擎应重写。
        """
        pass

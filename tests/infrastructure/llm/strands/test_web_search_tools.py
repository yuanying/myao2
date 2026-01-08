"""Tests for web_search tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from myao2.config.models import WebSearchConfig
from myao2.infrastructure.llm.strands.web_search_tools import (
    WEB_SEARCH_CONFIG_KEY,
    WEB_SEARCH_TOOLS,
    WebSearchToolsFactory,
    get_web_search_config,
    web_search,
)


@pytest.fixture
def web_search_config() -> WebSearchConfig:
    """Create WebSearchConfig for testing."""
    return WebSearchConfig(
        enabled=True,
        api_key="test-api-key",
        search_depth="basic",
        max_results=5,
        max_content_length=500,
    )


@pytest.fixture
def mock_tool_context(web_search_config: WebSearchConfig) -> MagicMock:
    """Create mock ToolContext with web_search config in invocation_state."""
    context = MagicMock()
    context.invocation_state = {WEB_SEARCH_CONFIG_KEY: web_search_config}
    return context


@pytest.fixture
def empty_tool_context() -> MagicMock:
    """Create mock ToolContext without web_search config."""
    context = MagicMock()
    context.invocation_state = {}
    return context


class TestGetWebSearchConfig:
    """Tests for get_web_search_config helper."""

    def test_returns_config_from_invocation_state(
        self, mock_tool_context: MagicMock, web_search_config: WebSearchConfig
    ) -> None:
        """Test that config is returned from invocation_state."""
        result = get_web_search_config(mock_tool_context)

        assert result is web_search_config

    def test_raises_runtime_error_when_not_found(
        self, empty_tool_context: MagicMock
    ) -> None:
        """Test that RuntimeError is raised when config not found."""
        with pytest.raises(RuntimeError, match="WebSearchConfig not found"):
            get_web_search_config(empty_tool_context)


class TestWebSearch:
    """Tests for web_search tool."""

    async def test_web_search_success(self, mock_tool_context: MagicMock) -> None:
        """Test successful web search."""
        mock_response = {
            "query": "Python async programming",
            "answer": "Python async programming allows...",
            "results": [
                {
                    "title": "Python asyncio docs",
                    "url": "https://docs.python.org/3/library/asyncio.html",
                    "content": "Official asyncio documentation.",
                    "score": 0.95,
                },
                {
                    "title": "Real Python Guide",
                    "url": "https://realpython.com/async-io-python/",
                    "content": "Comprehensive async tutorial.",
                    "score": 0.90,
                },
            ],
        }

        with patch(
            "myao2.infrastructure.llm.strands.web_search_tools.AsyncTavilyClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await web_search(
                query="Python async programming",
                tool_context=mock_tool_context,
            )

        assert "Python async programming" in result
        assert "Python asyncio docs" in result
        assert "https://docs.python.org/3/library/asyncio.html" in result
        assert "Python async programming allows..." in result
        mock_client.search.assert_called_once()

    async def test_web_search_with_answer(self, mock_tool_context: MagicMock) -> None:
        """Test web search result includes answer section."""
        mock_response = {
            "query": "test query",
            "answer": "This is the summarized answer.",
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": "Test content.",
                    "score": 0.9,
                },
            ],
        }

        with patch(
            "myao2.infrastructure.llm.strands.web_search_tools.AsyncTavilyClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await web_search(
                query="test query",
                tool_context=mock_tool_context,
            )

        assert "回答" in result
        assert "This is the summarized answer." in result

    async def test_web_search_content_truncation(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test that content is truncated when exceeding max_content_length."""
        long_content = "A" * 1000  # Exceeds default 500
        mock_response = {
            "query": "test query",
            "answer": None,
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": long_content,
                    "score": 0.9,
                },
            ],
        }

        with patch(
            "myao2.infrastructure.llm.strands.web_search_tools.AsyncTavilyClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await web_search(
                query="test query",
                tool_context=mock_tool_context,
            )

        # Content should be truncated to 500 chars + ellipsis
        assert long_content not in result  # Full content should not be present
        assert "..." in result

    async def test_web_search_empty_query(self, mock_tool_context: MagicMock) -> None:
        """Test web search with empty query."""
        result = await web_search(
            query="",
            tool_context=mock_tool_context,
        )

        assert "検索クエリを入力してください" in result

    async def test_web_search_whitespace_only_query(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test web search with whitespace-only query."""
        result = await web_search(
            query="   ",
            tool_context=mock_tool_context,
        )

        assert "検索クエリを入力してください" in result

    async def test_web_search_api_error(self, mock_tool_context: MagicMock) -> None:
        """Test web search API error handling."""
        with patch(
            "myao2.infrastructure.llm.strands.web_search_tools.AsyncTavilyClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(side_effect=Exception("API Error"))
            mock_client_class.return_value = mock_client

            result = await web_search(
                query="test query",
                tool_context=mock_tool_context,
            )

        assert "検索に失敗しました" in result
        assert "Exception" in result

    async def test_web_search_no_results(self, mock_tool_context: MagicMock) -> None:
        """Test web search with no results."""
        mock_response = {
            "query": "very obscure query",
            "answer": None,
            "results": [],
        }

        with patch(
            "myao2.infrastructure.llm.strands.web_search_tools.AsyncTavilyClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await web_search(
                query="very obscure query",
                tool_context=mock_tool_context,
            )

        assert "検索結果が見つかりませんでした" in result

    async def test_web_search_no_content_limit(
        self, mock_tool_context: MagicMock, web_search_config: WebSearchConfig
    ) -> None:
        """Test web search with max_content_length=0 (no limit)."""
        web_search_config.max_content_length = 0
        long_content = "A" * 1000
        mock_response = {
            "query": "test query",
            "answer": None,
            "results": [
                {
                    "title": "Test Result",
                    "url": "https://example.com",
                    "content": long_content,
                    "score": 0.9,
                },
            ],
        }

        with patch(
            "myao2.infrastructure.llm.strands.web_search_tools.AsyncTavilyClient"
        ) as mock_client_class:
            mock_client = AsyncMock()
            mock_client.search = AsyncMock(return_value=mock_response)
            mock_client_class.return_value = mock_client

            result = await web_search(
                query="test query",
                tool_context=mock_tool_context,
            )

        # Full content should be present when no limit
        assert long_content in result


class TestWebSearchToolsFactory:
    """Tests for WebSearchToolsFactory."""

    def test_get_invocation_state(self, web_search_config: WebSearchConfig) -> None:
        """Test invocation_state construction."""
        factory = WebSearchToolsFactory(web_search_config)

        state = factory.get_invocation_state()

        assert WEB_SEARCH_CONFIG_KEY in state
        assert state[WEB_SEARCH_CONFIG_KEY] is web_search_config

    def test_tools_property(self, web_search_config: WebSearchConfig) -> None:
        """Test tools property returns correct list."""
        factory = WebSearchToolsFactory(web_search_config)

        tools = factory.tools

        assert tools is WEB_SEARCH_TOOLS

    def test_tools_contains_web_search(
        self, web_search_config: WebSearchConfig
    ) -> None:
        """Test that web_search tool is in the list."""
        factory = WebSearchToolsFactory(web_search_config)

        tools = factory.tools

        assert len(tools) == 1
        assert web_search in tools


class TestWebSearchConfig:
    """Tests for WebSearchConfig."""

    def test_default_values(self) -> None:
        """Test WebSearchConfig default values."""
        config = WebSearchConfig(
            api_key="test-key",
        )

        assert config.enabled is True
        assert config.search_depth == "basic"
        assert config.max_results == 5
        assert config.max_content_length == 500

    def test_custom_values(self) -> None:
        """Test WebSearchConfig with custom values."""
        config = WebSearchConfig(
            enabled=False,
            api_key="custom-key",
            search_depth="advanced",
            max_results=10,
            max_content_length=1000,
        )

        assert config.enabled is False
        assert config.api_key == "custom-key"
        assert config.search_depth == "advanced"
        assert config.max_results == 10
        assert config.max_content_length == 1000

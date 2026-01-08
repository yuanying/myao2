"""Tests for web_fetch tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from myao2.config.models import WebFetchConfig
from myao2.infrastructure.llm.strands.web_fetch_tools import (
    WEB_FETCH_CONFIG_KEY,
    WEB_FETCH_TOOLS,
    WebFetchToolsFactory,
    get_web_fetch_config,
    web_fetch,
)


@pytest.fixture
def web_fetch_config() -> WebFetchConfig:
    """Create WebFetchConfig for testing."""
    return WebFetchConfig(
        enabled=True,
        api_endpoint="https://api.example.com",
        timeout_seconds=60,
        max_content_length=20000,
    )


@pytest.fixture
def mock_tool_context(web_fetch_config: WebFetchConfig) -> MagicMock:
    """Create mock ToolContext with web_fetch config in invocation_state."""
    context = MagicMock()
    context.invocation_state = {WEB_FETCH_CONFIG_KEY: web_fetch_config}
    return context


@pytest.fixture
def empty_tool_context() -> MagicMock:
    """Create mock ToolContext without web_fetch config."""
    context = MagicMock()
    context.invocation_state = {}
    return context


class TestGetWebFetchConfig:
    """Tests for get_web_fetch_config helper."""

    def test_returns_config_from_invocation_state(
        self, mock_tool_context: MagicMock, web_fetch_config: WebFetchConfig
    ) -> None:
        """Test that config is returned from invocation_state."""
        result = get_web_fetch_config(mock_tool_context)

        assert result is web_fetch_config

    def test_raises_runtime_error_when_not_found(
        self, empty_tool_context: MagicMock
    ) -> None:
        """Test that RuntimeError is raised when config not found."""
        with pytest.raises(RuntimeError, match="WebFetchConfig not found"):
            get_web_fetch_config(empty_tool_context)


class TestWebFetch:
    """Tests for web_fetch tool."""

    async def test_web_fetch_success(self, mock_tool_context: MagicMock) -> None:
        """Test successful web fetch."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "url": "https://example.com",
            "filter": "llm",
            "query": None,
            "cache": "0",
            "markdown": "# Example Page\n\nThis is content.",
            "success": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await web_fetch(
                url="https://example.com",
                tool_context=mock_tool_context,
            )

        assert "# Example Page" in result
        assert "This is content." in result
        mock_client.post.assert_called_once()

    async def test_web_fetch_content_truncation(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test that content is truncated when exceeding max_content_length."""
        long_content = "A" * 25000  # Exceeds default 20000
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "url": "https://example.com",
            "filter": "llm",
            "query": None,
            "cache": "0",
            "markdown": long_content,
            "success": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await web_fetch(
                url="https://example.com",
                tool_context=mock_tool_context,
            )

        assert len(result) <= 20000 + 100  # Allow for truncation message
        assert "（コンテンツが切り詰められました）" in result

    async def test_web_fetch_invalid_url_no_scheme(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test web fetch with URL missing http/https scheme."""
        result = await web_fetch(
            url="example.com",
            tool_context=mock_tool_context,
        )

        assert "無効なURL" in result
        assert "http://" in result or "https://" in result

    async def test_web_fetch_invalid_url_ftp_scheme(
        self, mock_tool_context: MagicMock
    ) -> None:
        """Test web fetch with non-http/https scheme."""
        result = await web_fetch(
            url="ftp://example.com",
            tool_context=mock_tool_context,
        )

        assert "無効なURL" in result

    async def test_web_fetch_timeout(self, mock_tool_context: MagicMock) -> None:
        """Test web fetch timeout handling."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await web_fetch(
                url="https://example.com",
                tool_context=mock_tool_context,
            )

        assert "タイムアウト" in result

    async def test_web_fetch_http_error(self, mock_tool_context: MagicMock) -> None:
        """Test web fetch HTTP error handling."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
                "Not Found",
                request=MagicMock(),
                response=MagicMock(status_code=404),
            )
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await web_fetch(
                url="https://example.com/notfound",
                tool_context=mock_tool_context,
            )

        assert "ページを取得できませんでした" in result

    async def test_web_fetch_api_failure(self, mock_tool_context: MagicMock) -> None:
        """Test web fetch when API returns success=false."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "url": "https://example.com",
            "filter": "llm",
            "query": None,
            "cache": "0",
            "markdown": "",
            "success": False,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await web_fetch(
                url="https://example.com",
                tool_context=mock_tool_context,
            )

        assert "ページを取得できませんでした" in result

    async def test_web_fetch_request_error(self, mock_tool_context: MagicMock) -> None:
        """Test web fetch request error handling."""
        with patch("httpx.AsyncClient") as mock_client_class:
            mock_client = AsyncMock()
            mock_client.post = AsyncMock(
                side_effect=httpx.RequestError("Connection failed")
            )
            mock_client_class.return_value.__aenter__.return_value = mock_client

            result = await web_fetch(
                url="https://example.com",
                tool_context=mock_tool_context,
            )

        assert "ページを取得できませんでした" in result


class TestWebFetchToolsFactory:
    """Tests for WebFetchToolsFactory."""

    def test_get_invocation_state(self, web_fetch_config: WebFetchConfig) -> None:
        """Test invocation_state construction."""
        factory = WebFetchToolsFactory(web_fetch_config)

        state = factory.get_invocation_state()

        assert WEB_FETCH_CONFIG_KEY in state
        assert state[WEB_FETCH_CONFIG_KEY] is web_fetch_config

    def test_tools_property(self, web_fetch_config: WebFetchConfig) -> None:
        """Test tools property returns correct list."""
        factory = WebFetchToolsFactory(web_fetch_config)

        tools = factory.tools

        assert tools is WEB_FETCH_TOOLS

    def test_tools_contains_web_fetch(self, web_fetch_config: WebFetchConfig) -> None:
        """Test that web_fetch tool is in the list."""
        factory = WebFetchToolsFactory(web_fetch_config)

        tools = factory.tools

        assert len(tools) == 1
        assert web_fetch in tools


class TestWebFetchConfig:
    """Tests for WebFetchConfig."""

    def test_default_values(self) -> None:
        """Test WebFetchConfig default values."""
        config = WebFetchConfig(
            api_endpoint="https://api.example.com",
        )

        assert config.enabled is True
        assert config.timeout_seconds == 60
        assert config.max_content_length == 20000

    def test_custom_values(self) -> None:
        """Test WebFetchConfig with custom values."""
        config = WebFetchConfig(
            enabled=False,
            api_endpoint="https://custom.api.com",
            timeout_seconds=30,
            max_content_length=10000,
        )

        assert config.enabled is False
        assert config.api_endpoint == "https://custom.api.com"
        assert config.timeout_seconds == 30
        assert config.max_content_length == 10000

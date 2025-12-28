"""Tests for SlackEventAdapter."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from myao2.domain.entities import Message, User
from myao2.infrastructure.slack import SlackEventAdapter


class TestSlackEventAdapter:
    """SlackEventAdapter tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack AsyncWebClient."""
        client = MagicMock()
        client.users_info = AsyncMock(
            return_value={
                "user": {
                    "id": "U123456",
                    "name": "testuser",
                    "is_bot": False,
                }
            }
        )
        return client

    @pytest.fixture
    def mock_user_repository(self) -> MagicMock:
        """Create mock UserRepository."""
        repo = MagicMock()
        repo.find_by_id = AsyncMock(return_value=None)
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_channel_repository(self) -> MagicMock:
        """Create mock ChannelRepository."""
        repo = MagicMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def adapter(self, mock_client: MagicMock) -> SlackEventAdapter:
        """Create adapter instance."""
        return SlackEventAdapter(client=mock_client)

    async def test_to_message_basic(
        self, adapter: SlackEventAdapter, mock_client: MagicMock
    ) -> None:
        """Test basic event to message conversion."""
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = await adapter.to_message(event)

        assert isinstance(message, Message)
        assert message.id == "1234567890.123456"
        assert message.channel.id == "C123456"
        assert message.user.id == "U123456"
        assert message.user.name == "testuser"
        assert message.text == "<@UBOT123> hello"
        assert message.thread_ts is None
        assert "UBOT123" in message.mentions

    async def test_to_message_in_thread(
        self, adapter: SlackEventAdapter, mock_client: MagicMock
    ) -> None:
        """Test event to message conversion for thread message."""
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> help me",
            "ts": "1234567890.123456",
            "channel": "C123456",
            "thread_ts": "1234567890.000000",
        }

        message = await adapter.to_message(event)

        assert message.thread_ts == "1234567890.000000"
        assert message.is_in_thread() is True

    async def test_to_message_bot_user(
        self, adapter: SlackEventAdapter, mock_client: MagicMock
    ) -> None:
        """Test event to message conversion for bot user."""
        mock_client.users_info = AsyncMock(
            return_value={
                "user": {
                    "id": "UBOT456",
                    "name": "bot",
                    "is_bot": True,
                }
            }
        )
        event = {
            "type": "app_mention",
            "user": "UBOT456",
            "text": "<@UBOT123> test",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = await adapter.to_message(event)

        assert message.user.is_bot is True

    async def test_to_message_timestamp_conversion(
        self, adapter: SlackEventAdapter
    ) -> None:
        """Test that timestamp is properly converted."""
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = await adapter.to_message(event)

        assert isinstance(message.timestamp, datetime)
        assert message.timestamp.tzinfo == timezone.utc

    def test_extract_mentions_single(self, adapter: SlackEventAdapter) -> None:
        """Test extracting single mention."""
        text = "<@U123456> hello"

        mentions = adapter.extract_mentions(text)

        assert mentions == ["U123456"]

    def test_extract_mentions_multiple(self, adapter: SlackEventAdapter) -> None:
        """Test extracting multiple mentions."""
        text = "<@U123> and <@U456> are here"

        mentions = adapter.extract_mentions(text)

        assert mentions == ["U123", "U456"]

    def test_extract_mentions_none(self, adapter: SlackEventAdapter) -> None:
        """Test extracting when no mentions."""
        text = "hello everyone"

        mentions = adapter.extract_mentions(text)

        assert mentions == []

    def test_extract_mentions_with_display_name(
        self, adapter: SlackEventAdapter
    ) -> None:
        """Test extracting mentions with display name format."""
        text = "<@U123|username> hello"

        mentions = adapter.extract_mentions(text)

        assert mentions == ["U123"]


class TestSlackEventAdapterWithCache:
    """SlackEventAdapter tests with caching."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack AsyncWebClient."""
        client = MagicMock()
        client.users_info = AsyncMock(
            return_value={
                "user": {
                    "id": "U123456",
                    "name": "testuser",
                    "is_bot": False,
                }
            }
        )
        return client

    @pytest.fixture
    def mock_user_repository(self) -> MagicMock:
        """Create mock UserRepository."""
        repo = MagicMock()
        repo.find_by_id = AsyncMock(return_value=None)
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def mock_channel_repository(self) -> MagicMock:
        """Create mock ChannelRepository."""
        repo = MagicMock()
        repo.save = AsyncMock()
        return repo

    async def test_user_cache_miss_fetches_from_api(
        self,
        mock_client: MagicMock,
        mock_user_repository: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test that cache miss triggers Slack API call and saves to cache."""
        adapter = SlackEventAdapter(
            client=mock_client,
            user_repository=mock_user_repository,
            channel_repository=mock_channel_repository,
        )
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        await adapter.to_message(event)

        # Should check cache first
        mock_user_repository.find_by_id.assert_called_once_with("U123456")
        # Should fetch from API since cache miss
        mock_client.users_info.assert_called_once_with(user="U123456")
        # Should save to cache
        mock_user_repository.save.assert_called_once()
        saved_user = mock_user_repository.save.call_args[0][0]
        assert saved_user.id == "U123456"

    async def test_user_cache_hit_skips_api(
        self,
        mock_client: MagicMock,
        mock_user_repository: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test that cache hit skips Slack API call."""
        # Return cached user
        cached_user = User(id="U123456", name="cached_user", is_bot=False)
        mock_user_repository.find_by_id = AsyncMock(return_value=cached_user)

        adapter = SlackEventAdapter(
            client=mock_client,
            user_repository=mock_user_repository,
            channel_repository=mock_channel_repository,
        )
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = await adapter.to_message(event)

        # Should check cache
        mock_user_repository.find_by_id.assert_called_once_with("U123456")
        # Should NOT call API
        mock_client.users_info.assert_not_called()
        # Should NOT save (already in cache)
        mock_user_repository.save.assert_not_called()
        # Should use cached user
        assert message.user.name == "cached_user"

    async def test_channel_saved_to_cache(
        self,
        mock_client: MagicMock,
        mock_user_repository: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test that channel is saved to cache."""
        adapter = SlackEventAdapter(
            client=mock_client,
            user_repository=mock_user_repository,
            channel_repository=mock_channel_repository,
        )
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        await adapter.to_message(event)

        # Should save channel to cache
        mock_channel_repository.save.assert_called_once()
        saved_channel = mock_channel_repository.save.call_args[0][0]
        assert saved_channel.id == "C123456"

    async def test_no_cache_without_repositories(self, mock_client: MagicMock) -> None:
        """Test that adapter works without repositories (no caching)."""
        adapter = SlackEventAdapter(client=mock_client)
        event = {
            "type": "app_mention",
            "user": "U123456",
            "text": "<@UBOT123> hello",
            "ts": "1234567890.123456",
            "channel": "C123456",
        }

        message = await adapter.to_message(event)

        # Should call API directly
        mock_client.users_info.assert_called_once_with(user="U123456")
        assert message.user.id == "U123456"

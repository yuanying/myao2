"""Tests for SlackChannelInitializer."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from myao2.domain.entities import Channel
from myao2.infrastructure.slack.channel_initializer import SlackChannelInitializer


class TestSlackChannelInitializer:
    """SlackChannelInitializer tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack AsyncWebClient."""
        client = MagicMock()
        client.users_conversations = AsyncMock(
            return_value={
                "channels": [
                    {"id": "C001", "name": "general"},
                    {"id": "C002", "name": "random"},
                    {"id": "C003", "name": "dev"},
                ]
            }
        )
        return client

    @pytest.fixture
    def mock_channel_repository(self) -> MagicMock:
        """Create mock ChannelRepository."""
        repo = MagicMock()
        repo.save = AsyncMock()
        return repo

    @pytest.fixture
    def initializer(
        self, mock_client: MagicMock, mock_channel_repository: MagicMock
    ) -> SlackChannelInitializer:
        """Create initializer instance."""
        return SlackChannelInitializer(
            client=mock_client,
            channel_repository=mock_channel_repository,
        )

    async def test_sync_channels_returns_channels(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
    ) -> None:
        """Test sync_channels returns list of channels."""
        channels = await initializer.sync_channels()

        assert len(channels) == 3
        assert all(isinstance(ch, Channel) for ch in channels)
        assert channels[0].id == "C001"
        assert channels[0].name == "general"
        assert channels[1].id == "C002"
        assert channels[1].name == "random"
        assert channels[2].id == "C003"
        assert channels[2].name == "dev"

    async def test_sync_channels_calls_api_correctly(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
    ) -> None:
        """Test sync_channels calls Slack API with correct parameters."""
        await initializer.sync_channels()

        mock_client.users_conversations.assert_called_once_with(
            types="public_channel,private_channel"
        )

    async def test_sync_channels_saves_to_repository(
        self,
        initializer: SlackChannelInitializer,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test sync_channels saves each channel to repository."""
        await initializer.sync_channels()

        assert mock_channel_repository.save.call_count == 3
        saved_channels = [
            call.args[0] for call in mock_channel_repository.save.call_args_list
        ]
        assert saved_channels[0].id == "C001"
        assert saved_channels[1].id == "C002"
        assert saved_channels[2].id == "C003"

    async def test_sync_channels_empty_response(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test sync_channels handles empty channel list."""
        mock_client.users_conversations = AsyncMock(return_value={"channels": []})

        channels = await initializer.sync_channels()

        assert channels == []
        mock_channel_repository.save.assert_not_called()

    async def test_sync_channels_missing_channels_key(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test sync_channels handles missing channels key in response."""
        mock_client.users_conversations = AsyncMock(return_value={})

        channels = await initializer.sync_channels()

        assert channels == []
        mock_channel_repository.save.assert_not_called()

    async def test_sync_channels_api_error(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test sync_channels handles API errors gracefully."""
        mock_client.users_conversations = AsyncMock(side_effect=Exception("API error"))

        channels = await initializer.sync_channels()

        assert channels == []
        mock_channel_repository.save.assert_not_called()

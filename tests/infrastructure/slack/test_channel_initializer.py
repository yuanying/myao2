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


class TestSyncChannelsWithCleanup:
    """sync_channels_with_cleanup method tests."""

    @pytest.fixture
    def mock_client(self) -> MagicMock:
        """Create mock Slack AsyncWebClient."""
        client = MagicMock()
        client.users_conversations = AsyncMock(
            return_value={
                "channels": [
                    {"id": "C001", "name": "general"},
                ]
            }
        )
        return client

    @pytest.fixture
    def mock_channel_repository(self) -> MagicMock:
        """Create mock ChannelRepository."""
        repo = MagicMock()
        repo.save = AsyncMock()
        repo.find_all = AsyncMock(return_value=[])
        repo.delete = AsyncMock(return_value=True)
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

    async def test_sync_with_cleanup_removes_channels_not_in_slack(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test that channels not in Slack are removed from DB."""
        # Slack returns only C001
        mock_client.users_conversations = AsyncMock(
            return_value={"channels": [{"id": "C001", "name": "general"}]}
        )
        # DB has C001 and C002
        mock_channel_repository.find_all = AsyncMock(
            return_value=[
                Channel(id="C001", name="general"),
                Channel(id="C002", name="old-channel"),
            ]
        )

        channels, removed = await initializer.sync_channels_with_cleanup()

        assert len(channels) == 1
        assert channels[0].id == "C001"
        assert removed == ["C002"]
        mock_channel_repository.delete.assert_awaited_once_with("C002")

    async def test_sync_with_cleanup_saves_new_channels(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test that new channels from Slack are saved."""
        mock_client.users_conversations = AsyncMock(
            return_value={
                "channels": [
                    {"id": "C001", "name": "general"},
                    {"id": "C002", "name": "new-channel"},
                ]
            }
        )
        mock_channel_repository.find_all = AsyncMock(
            return_value=[Channel(id="C001", name="general")]
        )

        channels, removed = await initializer.sync_channels_with_cleanup()

        assert len(channels) == 2
        assert removed == []
        assert mock_channel_repository.save.call_count == 2

    async def test_sync_with_cleanup_no_changes(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test when Slack and DB are in sync."""
        mock_client.users_conversations = AsyncMock(
            return_value={"channels": [{"id": "C001", "name": "general"}]}
        )
        mock_channel_repository.find_all = AsyncMock(
            return_value=[Channel(id="C001", name="general")]
        )

        channels, removed = await initializer.sync_channels_with_cleanup()

        assert len(channels) == 1
        assert removed == []
        mock_channel_repository.delete.assert_not_awaited()

    async def test_sync_with_cleanup_removes_multiple_channels(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test removing multiple channels at once."""
        mock_client.users_conversations = AsyncMock(return_value={"channels": []})
        mock_channel_repository.find_all = AsyncMock(
            return_value=[
                Channel(id="C001", name="channel-1"),
                Channel(id="C002", name="channel-2"),
                Channel(id="C003", name="channel-3"),
            ]
        )

        channels, removed = await initializer.sync_channels_with_cleanup()

        assert channels == []
        assert set(removed) == {"C001", "C002", "C003"}
        assert mock_channel_repository.delete.call_count == 3

    async def test_sync_with_cleanup_api_error_returns_empty(
        self,
        initializer: SlackChannelInitializer,
        mock_client: MagicMock,
        mock_channel_repository: MagicMock,
    ) -> None:
        """Test that API errors return empty results."""
        mock_client.users_conversations = AsyncMock(side_effect=Exception("API error"))

        channels, removed = await initializer.sync_channels_with_cleanup()

        assert channels == []
        assert removed == []
        mock_channel_repository.delete.assert_not_awaited()

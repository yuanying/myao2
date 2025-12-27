"""Tests for ReplyToMentionUseCase."""

from datetime import datetime, timezone

import pytest

from myao2.application.use_cases import ReplyToMentionUseCase
from myao2.config import PersonaConfig
from myao2.domain.entities import Channel, Message, User


class MockMessagingService:
    """Mock messaging service for testing."""

    def __init__(self) -> None:
        self.sent_messages: list[dict[str, str | None]] = []

    def send_message(
        self,
        channel_id: str,
        text: str,
        thread_ts: str | None = None,
    ) -> None:
        """Record sent message."""
        self.sent_messages.append(
            {
                "channel_id": channel_id,
                "text": text,
                "thread_ts": thread_ts,
            }
        )


class MockResponseGenerator:
    """Mock response generator for testing."""

    def __init__(self, response: str = "Hello!") -> None:
        self.response = response
        self.calls: list[dict[str, str]] = []

    def generate(
        self,
        user_message: str,
        system_prompt: str,
    ) -> str:
        """Return mock response."""
        self.calls.append(
            {
                "user_message": user_message,
                "system_prompt": system_prompt,
            }
        )
        return self.response


class TestReplyToMentionUseCase:
    """ReplyToMentionUseCase tests."""

    @pytest.fixture
    def bot_user_id(self) -> str:
        """Bot's user ID."""
        return "B001"

    @pytest.fixture
    def messaging_service(self) -> MockMessagingService:
        """Create mock messaging service."""
        return MockMessagingService()

    @pytest.fixture
    def response_generator(self) -> MockResponseGenerator:
        """Create mock response generator."""
        return MockResponseGenerator(response="Nice to meet you!")

    @pytest.fixture
    def persona(self) -> PersonaConfig:
        """Create persona config."""
        return PersonaConfig(
            name="TestBot",
            system_prompt="You are a friendly bot.",
        )

    @pytest.fixture
    def use_case(
        self,
        messaging_service: MockMessagingService,
        response_generator: MockResponseGenerator,
        persona: PersonaConfig,
        bot_user_id: str,
    ) -> ReplyToMentionUseCase:
        """Create use case instance."""
        return ReplyToMentionUseCase(
            messaging_service=messaging_service,
            response_generator=response_generator,
            persona=persona,
            bot_user_id=bot_user_id,
        )

    @pytest.fixture
    def channel(self) -> Channel:
        """Create test channel."""
        return Channel(id="C123", name="general")

    @pytest.fixture
    def user(self) -> User:
        """Create test user."""
        return User(id="U123", name="Test User")

    @pytest.fixture
    def timestamp(self) -> datetime:
        """Create test timestamp."""
        return datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

    def test_mention_in_channel_sends_message(
        self,
        use_case: ReplyToMentionUseCase,
        messaging_service: MockMessagingService,
        response_generator: MockResponseGenerator,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that bot replies when mentioned in channel."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"Hello <@{bot_user_id}>!",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        use_case.execute(message)

        assert len(messaging_service.sent_messages) == 1
        sent = messaging_service.sent_messages[0]
        assert sent["channel_id"] == channel.id
        assert sent["text"] == "Nice to meet you!"
        assert sent["thread_ts"] is None

    def test_mention_in_thread_replies_to_thread(
        self,
        use_case: ReplyToMentionUseCase,
        messaging_service: MockMessagingService,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that bot replies to thread when mentioned in thread."""
        thread_ts = "1234567890.123456"
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> help me",
            timestamp=timestamp,
            thread_ts=thread_ts,
            mentions=[bot_user_id],
        )

        use_case.execute(message)

        assert len(messaging_service.sent_messages) == 1
        sent = messaging_service.sent_messages[0]
        assert sent["channel_id"] == channel.id
        assert sent["thread_ts"] == thread_ts

    def test_no_mention_does_nothing(
        self,
        use_case: ReplyToMentionUseCase,
        messaging_service: MockMessagingService,
        channel: Channel,
        user: User,
        timestamp: datetime,
    ) -> None:
        """Test that bot does not reply when not mentioned."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text="Hello everyone!",
            timestamp=timestamp,
            mentions=["U999"],  # Other user mentioned
        )

        use_case.execute(message)

        assert len(messaging_service.sent_messages) == 0

    def test_bot_message_ignored(
        self,
        use_case: ReplyToMentionUseCase,
        messaging_service: MockMessagingService,
        channel: Channel,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that bot ignores its own messages."""
        bot_user = User(id=bot_user_id, name="Bot", is_bot=True)
        message = Message(
            id="M001",
            channel=channel,
            user=bot_user,
            text=f"<@{bot_user_id}> I mentioned myself",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        use_case.execute(message)

        assert len(messaging_service.sent_messages) == 0

    def test_uses_persona_system_prompt(
        self,
        use_case: ReplyToMentionUseCase,
        response_generator: MockResponseGenerator,
        persona: PersonaConfig,
        channel: Channel,
        user: User,
        timestamp: datetime,
        bot_user_id: str,
    ) -> None:
        """Test that use case passes persona system prompt to generator."""
        message = Message(
            id="M001",
            channel=channel,
            user=user,
            text=f"<@{bot_user_id}> hello",
            timestamp=timestamp,
            mentions=[bot_user_id],
        )

        use_case.execute(message)

        assert len(response_generator.calls) == 1
        call = response_generator.calls[0]
        assert call["system_prompt"] == persona.system_prompt
        assert call["user_message"] == message.text

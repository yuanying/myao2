"""Reply to mention use case."""

from datetime import datetime, timedelta, timezone

from myao2.application.use_cases.helpers import (
    build_context_with_memory,
    create_bot_message,
    log_llm_metrics,
)
from myao2.config import PersonaConfig
from myao2.domain.entities import JudgmentCache, Message
from myao2.domain.repositories import ChannelRepository, MessageRepository
from myao2.domain.repositories.judgment_cache_repository import JudgmentCacheRepository
from myao2.domain.repositories.memo_repository import MemoRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.services import (
    MessagingService,
    ResponseGenerator,
)


class ReplyToMentionUseCase:
    """Use case for replying to messages that mention the bot.

    This use case handles incoming messages and generates responses
    when the bot is mentioned, using conversation history for context.
    """

    def __init__(
        self,
        messaging_service: MessagingService,
        response_generator: ResponseGenerator,
        message_repository: MessageRepository,
        channel_repository: ChannelRepository,
        memory_repository: MemoryRepository,
        persona: PersonaConfig,
        bot_user_id: str,
        memo_repository: MemoRepository | None = None,
        judgment_cache_repository: JudgmentCacheRepository | None = None,
    ) -> None:
        """Initialize the use case.

        Args:
            messaging_service: Service for sending messages.
            response_generator: Service for generating responses.
            message_repository: Repository for storing messages.
            channel_repository: Repository for channel operations.
            memory_repository: Repository for memory access.
            persona: Bot persona configuration.
            bot_user_id: The bot's user ID.
            memo_repository: Repository for memo access (optional).
            judgment_cache_repository: Repository for judgment cache (optional).
        """
        self._messaging_service = messaging_service
        self._response_generator = response_generator
        self._message_repository = message_repository
        self._channel_repository = channel_repository
        self._memory_repository = memory_repository
        self._persona = persona
        self._bot_user_id = bot_user_id
        self._memo_repository = memo_repository
        self._judgment_cache_repository = judgment_cache_repository

    async def execute(self, message: Message) -> None:
        """Execute the use case.

        Processing flow:
        1. Ignore messages from the bot itself
        2. Ignore messages that don't mention the bot
        3. Save the received message
        4. Build Context with memory (retrieves messages from repository)
        5. Generate response with context
        6. Send response
        7. Save response message

        Args:
            message: The received message.
        """
        # 1. Ignore messages from the bot itself
        if message.user.id == self._bot_user_id:
            return

        # 2. Ignore messages that don't mention the bot
        if not message.mentions_user(self._bot_user_id):
            return

        # 3. Save the received message
        await self._message_repository.save(message)

        # 4. Build Context with memory (retrieves messages from repository)
        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            channel=message.channel,
            persona=self._persona,
            target_thread_ts=message.thread_ts,
            memo_repository=self._memo_repository,
        )

        # 5. Generate response with context
        result = await self._response_generator.generate(context=context)
        log_llm_metrics("generate", result.metrics)

        # 6. Send response
        await self._messaging_service.send_message(
            channel_id=message.channel.id,
            text=result.text,
            thread_ts=message.thread_ts,
        )

        # 7. Save response message
        bot_message = create_bot_message(
            result.text, message, self._bot_user_id, self._persona.name
        )
        await self._message_repository.save(bot_message)

        # 8. Create judgment cache to prevent duplicate responses from periodic checker
        if self._judgment_cache_repository is not None:
            current_time = datetime.now(timezone.utc)
            skip_seconds = 3600  # 1 hour
            cache = JudgmentCache(
                channel_id=message.channel.id,
                thread_ts=message.thread_ts,
                should_respond=True,
                confidence=1.0,
                reason="Responded to mention",
                latest_message_ts=bot_message.id,
                next_check_at=current_time + timedelta(seconds=skip_seconds),
                created_at=current_time,
                updated_at=current_time,
            )
            await self._judgment_cache_repository.save(cache)

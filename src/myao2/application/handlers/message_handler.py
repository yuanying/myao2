"""Handler for MESSAGE events in the event-driven architecture.

This module defines the MESSAGE event handler used by the event dispatcher
to process incoming message events, replacing the previous
ReplyToMentionUseCase-based implementation.
"""

import logging
from datetime import datetime, timedelta, timezone

from myao2.application.use_cases.helpers import (
    build_context_with_memory,
    create_bot_message,
    log_llm_metrics,
)
from myao2.config import PersonaConfig
from myao2.domain.entities import Event, JudgmentCache, Message
from myao2.domain.entities.event import EventType
from myao2.domain.repositories import ChannelRepository, MessageRepository
from myao2.domain.repositories.judgment_cache_repository import JudgmentCacheRepository
from myao2.domain.repositories.memo_repository import MemoRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.services import MessagingService, ResponseGenerator
from myao2.infrastructure.events.dispatcher import event_handler

logger = logging.getLogger(__name__)


class MessageEventHandler:
    """Handler for MESSAGE events.

    Processes mention events and generates responses.
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
        """Initialize the handler.

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

    @event_handler(EventType.MESSAGE)
    async def handle(self, event: Event) -> None:
        """Handle MESSAGE event.

        Processing flow:
        1. Extract message from event payload
        2. Save the received message
        3. Build Context with memory
        4. Generate response with context
        5. Send response
        6. Save response message
        7. Create judgment cache

        Args:
            event: The MESSAGE event.
        """
        message: Message = event.payload["message"]
        channel_id = event.payload["channel_id"]
        thread_ts = event.payload.get("thread_ts")

        logger.info(
            "Handling MESSAGE event: channel=%s, thread_ts=%s",
            channel_id,
            thread_ts,
        )

        # 1. Save the received message
        await self._message_repository.save(message)

        # 2. Build Context with memory
        channel = await self._channel_repository.find_by_id(channel_id)
        if channel is None:
            logger.warning("Channel not found: %s", channel_id)
            return

        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            channel=channel,
            persona=self._persona,
            target_thread_ts=thread_ts,
            memo_repository=self._memo_repository,
        )

        # 3. Generate response with context
        result = await self._response_generator.generate(context=context)
        log_llm_metrics("generate", result.metrics)

        # 4. Send response
        await self._messaging_service.send_message(
            channel_id=channel_id,
            text=result.text,
            thread_ts=thread_ts,
        )

        # 5. Save response message
        bot_message = create_bot_message(
            result.text, message, self._bot_user_id, self._persona.name
        )
        await self._message_repository.save(bot_message)

        # 6. Create judgment cache to prevent duplicate responses
        if self._judgment_cache_repository is not None:
            current_time = datetime.now(timezone.utc)
            skip_seconds = 3600  # 1 hour
            cache = JudgmentCache(
                channel_id=channel_id,
                thread_ts=thread_ts,
                should_respond=True,
                confidence=1.0,
                reason="Responded to mention",
                latest_message_ts=bot_message.id,
                next_check_at=current_time + timedelta(seconds=skip_seconds),
                created_at=current_time,
                updated_at=current_time,
            )
            await self._judgment_cache_repository.save(cache)

        logger.info("MESSAGE event handled successfully")

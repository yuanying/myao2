"""Autonomous response use case."""

import logging
from datetime import datetime, timedelta, timezone

from myao2.application.use_cases.helpers import (
    build_context_with_memory,
    create_bot_message_for_thread,
)
from myao2.config import Config, JudgmentSkipConfig
from myao2.domain.entities import Channel, Context
from myao2.domain.entities.judgment_cache import JudgmentCache
from myao2.domain.entities.judgment_result import JudgmentResult
from myao2.domain.exceptions import ChannelNotAccessibleError
from myao2.domain.repositories import ChannelRepository, MessageRepository
from myao2.domain.repositories.judgment_cache_repository import JudgmentCacheRepository
from myao2.domain.repositories.memory_repository import MemoryRepository
from myao2.domain.services import (
    ChannelSyncService,
    MessagingService,
    ResponseGenerator,
)
from myao2.domain.services.channel_monitor import ChannelMonitor
from myao2.domain.services.response_judgment import ResponseJudgment

logger = logging.getLogger(__name__)


class AutonomousResponseUseCase:
    """Use case for autonomous response.

    Detects unreplied messages in channels, performs response judgment,
    and generates/sends responses when appropriate.
    """

    def __init__(
        self,
        channel_monitor: ChannelMonitor,
        response_judgment: ResponseJudgment,
        response_generator: ResponseGenerator,
        messaging_service: MessagingService,
        message_repository: MessageRepository,
        judgment_cache_repository: JudgmentCacheRepository,
        channel_repository: ChannelRepository,
        memory_repository: MemoryRepository,
        config: Config,
        bot_user_id: str,
        channel_sync_service: ChannelSyncService | None = None,
    ) -> None:
        """Initialize the use case.

        Args:
            channel_monitor: Service for monitoring channels.
            response_judgment: Service for judging whether to respond.
            response_generator: Service for generating responses.
            messaging_service: Service for sending messages.
            message_repository: Repository for storing messages.
            judgment_cache_repository: Repository for judgment cache.
            channel_repository: Repository for channel operations.
            memory_repository: Repository for memory access.
            config: Application configuration.
            bot_user_id: The bot's user ID.
            channel_sync_service: Service for channel synchronization (optional).
        """
        self._channel_monitor = channel_monitor
        self._response_judgment = response_judgment
        self._response_generator = response_generator
        self._messaging_service = messaging_service
        self._message_repository = message_repository
        self._judgment_cache_repository = judgment_cache_repository
        self._channel_repository = channel_repository
        self._memory_repository = memory_repository
        self._config = config
        self._bot_user_id = bot_user_id
        self._channel_sync_service = channel_sync_service

    async def execute(self) -> None:
        """Execute autonomous response.

        Processing flow:
        1. Sync channels with cleanup (if enabled)
        2. Get all channels the bot is in
        3. Check each channel for unreplied messages
        4. For each unreplied message, perform response judgment
        5. If should respond, generate and send response
        """
        # Sync channels before checking (removes stale channels)
        if self._channel_sync_service is not None:
            await self._channel_sync_service.sync_with_cleanup()

        channels = await self._channel_monitor.get_channels()

        for channel in channels:
            logger.info("Checking channel %s for unreplied messages", channel.name)
            await self.check_channel(channel)

    async def check_channel(self, channel: Channel) -> None:
        """Check a specific channel for unreplied threads.

        Args:
            channel: The channel to check.
        """
        unreplied_threads = await self._channel_monitor.get_unreplied_threads(
            channel_id=channel.id,
            min_wait_seconds=self._config.response.min_wait_seconds,
            max_message_age_seconds=self._config.response.max_message_age_seconds,
        )

        for thread_ts in unreplied_threads:
            try:
                logger.info(
                    "Processing unreplied thread %s in channel %s",
                    thread_ts,
                    channel.id,
                )
                await self._process_thread(channel, thread_ts)
            except Exception:
                logger.exception(
                    "Error processing thread %s in channel %s",
                    thread_ts,
                    channel.id,
                )

    async def _process_thread(self, channel: Channel, thread_ts: str | None) -> None:
        """Process a single thread.

        Args:
            channel: The channel containing the thread.
            thread_ts: Thread timestamp (None for top-level).
        """
        # Build context with memory (reused for both judgment and response generation)
        context = await build_context_with_memory(
            memory_repository=self._memory_repository,
            message_repository=self._message_repository,
            channel_repository=self._channel_repository,
            channel=channel,
            persona=self._config.persona,
            target_thread_ts=thread_ts,
            message_limit=self._config.response.message_limit,
        )

        # Get latest message ID for cache handling
        latest_message_id = self._get_latest_message_id(context, thread_ts)

        # Check if we should skip judgment
        if await self._should_skip_judgment(channel.id, thread_ts, latest_message_id):
            logger.info(
                "Skipping judgment for thread %s (cache valid)",
                thread_ts,
            )
            return

        # Perform response judgment
        judgment_result = await self._response_judgment.judge(context=context)

        # Log judgment result
        logger.info(
            "Judgment for thread %s: should_respond=%s, reason=%s, confidence=%.2f",
            thread_ts,
            judgment_result.should_respond,
            judgment_result.reason,
            judgment_result.confidence,
        )

        # Cache judgment result
        await self._cache_judgment_result(
            channel.id, thread_ts, latest_message_id, judgment_result
        )

        if not judgment_result.should_respond:
            return

        # Generate response using the same context
        response_text = await self._response_generator.generate(context=context)

        # Send response
        logger.info(
            "Sending autonomous response to channel %s (thread_ts=%s)",
            channel.id,
            thread_ts,
        )
        try:
            await self._messaging_service.send_message(
                channel_id=channel.id,
                text=response_text,
                thread_ts=thread_ts,
            )
        except ChannelNotAccessibleError:
            logger.warning(
                "Channel %s is no longer accessible, removing from database",
                channel.id,
            )
            if self._channel_repository is not None:
                await self._channel_repository.delete(channel.id)
            return

        # Save bot response message
        bot_message = create_bot_message_for_thread(
            response_text,
            channel,
            thread_ts,
            self._bot_user_id,
            self._config.persona.name,
        )
        await self._message_repository.save(bot_message)

    def _get_latest_message_id(
        self, context: Context, thread_ts: str | None
    ) -> str | None:
        """Get the latest message ID from context.

        Args:
            context: Conversation context.
            thread_ts: Thread timestamp (None for top-level).

        Returns:
            Latest message ID or None if not found.
        """
        if thread_ts is None:
            messages = context.conversation_history.top_level_messages
        else:
            messages = context.conversation_history.get_thread(thread_ts)

        if messages:
            return max(messages, key=lambda m: m.timestamp).id
        return None

    async def _should_skip_judgment(
        self,
        channel_id: str,
        thread_ts: str | None,
        latest_message_id: str | None,
    ) -> bool:
        """Check if judgment should be skipped based on cache.

        Args:
            channel_id: The channel ID.
            thread_ts: Thread timestamp (None for top-level).
            latest_message_id: The latest message ID in the thread.

        Returns:
            True if judgment should be skipped, False otherwise.
        """
        skip_config = self._config.response.judgment_skip
        if skip_config is None or not skip_config.enabled:
            return False

        if latest_message_id is None:
            return False

        cache = await self._judgment_cache_repository.find_by_scope(
            channel_id=channel_id,
            thread_ts=thread_ts,
        )

        if cache is None:
            return False

        current_time = datetime.now(timezone.utc)
        return cache.is_valid(current_time, latest_message_id)

    async def _cache_judgment_result(
        self,
        channel_id: str,
        thread_ts: str | None,
        latest_message_id: str | None,
        result: JudgmentResult,
    ) -> None:
        """Cache judgment result.

        Args:
            channel_id: The channel ID.
            thread_ts: Thread timestamp (None for top-level).
            latest_message_id: The latest message ID in the thread.
            result: The judgment result.
        """
        skip_config = self._config.response.judgment_skip
        if skip_config is None or not skip_config.enabled:
            return

        if latest_message_id is None:
            return

        current_time = datetime.now(timezone.utc)
        skip_seconds = self._calculate_skip_seconds(result.confidence, skip_config)
        next_check_at = current_time + timedelta(seconds=skip_seconds)

        cache = JudgmentCache(
            channel_id=channel_id,
            thread_ts=thread_ts,
            should_respond=result.should_respond,
            confidence=result.confidence,
            reason=result.reason,
            latest_message_ts=latest_message_id,
            next_check_at=next_check_at,
            created_at=current_time,
            updated_at=current_time,
        )

        await self._judgment_cache_repository.save(cache)

    def _calculate_skip_seconds(
        self,
        confidence: float,
        config: JudgmentSkipConfig,
    ) -> int:
        """Calculate skip seconds based on confidence.

        Args:
            confidence: The confidence value (0.0-1.0).
            config: The judgment skip configuration.

        Returns:
            Number of seconds to skip.
        """
        sorted_thresholds = sorted(
            config.thresholds,
            key=lambda t: t.min_confidence,
            reverse=True,
        )

        for threshold in sorted_thresholds:
            if confidence >= threshold.min_confidence:
                return threshold.skip_seconds

        return config.default_skip_seconds

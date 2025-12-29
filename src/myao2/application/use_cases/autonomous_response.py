"""Autonomous response use case."""

import logging
import uuid
from datetime import datetime, timedelta, timezone

from myao2.config import Config, JudgmentSkipConfig
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.entities.judgment_cache import JudgmentCache
from myao2.domain.entities.judgment_result import JudgmentResult
from myao2.domain.exceptions import ChannelNotAccessibleError
from myao2.domain.repositories import ChannelRepository, MessageRepository
from myao2.domain.repositories.judgment_cache_repository import JudgmentCacheRepository
from myao2.domain.services import (
    ChannelSyncService,
    ConversationHistoryService,
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
        conversation_history_service: ConversationHistoryService,
        config: Config,
        bot_user_id: str,
        channel_repository: ChannelRepository | None = None,
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
            conversation_history_service: Service for fetching conversation history.
            config: Application configuration.
            bot_user_id: The bot's user ID.
            channel_repository: Repository for channel operations (optional).
            channel_sync_service: Service for channel synchronization (optional).
        """
        self._channel_monitor = channel_monitor
        self._response_judgment = response_judgment
        self._response_generator = response_generator
        self._messaging_service = messaging_service
        self._message_repository = message_repository
        self._judgment_cache_repository = judgment_cache_repository
        self._conversation_history_service = conversation_history_service
        self._config = config
        self._bot_user_id = bot_user_id
        self._channel_repository = channel_repository
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
        """Check a specific channel for unreplied messages.

        Args:
            channel: The channel to check.
        """
        unreplied_messages = await self._channel_monitor.get_unreplied_messages(
            channel_id=channel.id,
            min_wait_seconds=self._config.response.min_wait_seconds,
            max_message_age_seconds=self._config.response.max_message_age_seconds,
        )

        for message in unreplied_messages:
            try:
                logger.info(
                    "Processing unreplied message %s in channel %s",
                    message.id,
                    channel.id,
                )
                await self._process_message(channel, message)
            except Exception:
                logger.exception(
                    "Error processing message %s in channel %s",
                    message.id,
                    channel.id,
                )

    async def _process_message(self, channel: Channel, message: Message) -> None:
        """Process a single message.

        Args:
            channel: The channel containing the message.
            message: The message to process.
        """
        # Check if we should skip judgment
        if await self._should_skip_judgment(message):
            logger.info(
                "Skipping judgment for message %s (cache valid)",
                message.id,
            )
            return

        # Get conversation history
        conversation_history = await self._get_conversation_history(message)

        # Build context for judgment (without auxiliary context)
        judgment_context = Context(
            persona=self._config.persona,
            conversation_history=conversation_history,
        )

        # Perform response judgment
        judgment_result = await self._response_judgment.judge(
            context=judgment_context,
            message=message,
        )

        # Log judgment result
        logger.info(
            "Judgment for message %s: should_respond=%s, reason=%s, confidence=%.2f",
            message.id,
            judgment_result.should_respond,
            judgment_result.reason,
            judgment_result.confidence,
        )

        # Cache judgment result
        await self._cache_judgment_result(message, judgment_result)

        if not judgment_result.should_respond:
            return

        # Build other channel messages
        other_channel_messages = await self._build_other_channel_messages(channel)

        # Build context for response generation (with other channel messages)
        response_context = Context(
            persona=self._config.persona,
            conversation_history=conversation_history,
            other_channel_messages=other_channel_messages,
        )

        # Generate response
        response_text = await self._response_generator.generate(
            user_message=message,
            context=response_context,
        )

        # Send response
        logger.info(
            "Sending autonomous response to channel %s (thread_ts=%s)",
            channel.id,
            message.thread_ts,
        )
        try:
            await self._messaging_service.send_message(
                channel_id=channel.id,
                text=response_text,
                thread_ts=message.thread_ts,
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
        bot_message = self._create_bot_message(response_text, message)
        await self._message_repository.save(bot_message)

    async def _get_conversation_history(self, message: Message) -> list[Message]:
        """Get conversation history.

        Fetches thread history for messages in a thread,
        or channel history for messages in the channel.

        Args:
            message: The message to get history for.

        Returns:
            Conversation history (oldest first).
        """
        if message.is_in_thread():
            return await self._conversation_history_service.fetch_thread_history(
                channel_id=message.channel.id,
                thread_ts=message.thread_ts,  # type: ignore[arg-type]
                limit=self._config.response.message_limit,
            )
        else:
            return await self._conversation_history_service.fetch_channel_history(
                channel_id=message.channel.id,
                limit=self._config.response.message_limit,
            )

    async def _build_other_channel_messages(
        self, target_channel: Channel
    ) -> dict[str, list[Message]]:
        """Build other channel messages dict.

        Collects recent messages from channels other than the target channel.

        Args:
            target_channel: The channel to exclude.

        Returns:
            Dict mapping channel names to their messages.
        """
        all_channels = await self._channel_monitor.get_channels()
        other_channels = [ch for ch in all_channels if ch.id != target_channel.id]

        result: dict[str, list[Message]] = {}

        for channel in other_channels:
            messages = await self._channel_monitor.get_recent_messages(
                channel_id=channel.id,
                limit=self._config.response.message_limit,
            )

            if messages:
                result[channel.name] = messages

        return result

    def _create_bot_message(
        self,
        response_text: str,
        original_message: Message,
    ) -> Message:
        """Create bot response message.

        Args:
            response_text: The response text.
            original_message: The original message being replied to.

        Returns:
            Bot response Message.
        """
        return Message(
            id=str(uuid.uuid4()),
            channel=original_message.channel,
            user=User(
                id=self._bot_user_id,
                name=self._config.persona.name,
                is_bot=True,
            ),
            text=response_text,
            timestamp=datetime.now(timezone.utc),
            thread_ts=original_message.thread_ts,
            mentions=[],
        )

    async def _should_skip_judgment(self, message: Message) -> bool:
        """Check if judgment should be skipped based on cache.

        Args:
            message: The message to check.

        Returns:
            True if judgment should be skipped, False otherwise.
        """
        skip_config = self._config.response.judgment_skip
        if skip_config is None or not skip_config.enabled:
            return False

        cache = await self._judgment_cache_repository.find_by_scope(
            channel_id=message.channel.id,
            thread_ts=message.thread_ts,
        )

        if cache is None:
            return False

        current_time = datetime.now(timezone.utc)
        # message.id is the latest message timestamp
        return cache.is_valid(current_time, message.id)

    async def _cache_judgment_result(
        self,
        message: Message,
        result: JudgmentResult,
    ) -> None:
        """Cache judgment result.

        Args:
            message: The message that was judged.
            result: The judgment result.
        """
        skip_config = self._config.response.judgment_skip
        if skip_config is None or not skip_config.enabled:
            return

        current_time = datetime.now(timezone.utc)
        skip_seconds = self._calculate_skip_seconds(result.confidence, skip_config)
        next_check_at = current_time + timedelta(seconds=skip_seconds)

        cache = JudgmentCache(
            channel_id=message.channel.id,
            thread_ts=message.thread_ts,
            should_respond=result.should_respond,
            confidence=result.confidence,
            reason=result.reason,
            latest_message_ts=message.id,
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

"""Autonomous response use case."""

import logging
import uuid
from datetime import datetime, timezone

from myao2.config import Config
from myao2.domain.entities import Channel, Context, Message, User
from myao2.domain.repositories import MessageRepository
from myao2.domain.services import (
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
        conversation_history_service: ConversationHistoryService,
        config: Config,
        bot_user_id: str,
    ) -> None:
        """Initialize the use case.

        Args:
            channel_monitor: Service for monitoring channels.
            response_judgment: Service for judging whether to respond.
            response_generator: Service for generating responses.
            messaging_service: Service for sending messages.
            message_repository: Repository for storing messages.
            conversation_history_service: Service for fetching conversation history.
            config: Application configuration.
            bot_user_id: The bot's user ID.
        """
        self._channel_monitor = channel_monitor
        self._response_judgment = response_judgment
        self._response_generator = response_generator
        self._messaging_service = messaging_service
        self._message_repository = message_repository
        self._conversation_history_service = conversation_history_service
        self._config = config
        self._bot_user_id = bot_user_id

    async def execute(self) -> None:
        """Execute autonomous response.

        Processing flow:
        1. Get all channels the bot is in
        2. Check each channel for unreplied messages
        3. For each unreplied message, perform response judgment
        4. If should respond, generate and send response
        """
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

        if not judgment_result.should_respond:
            return

        # Build auxiliary context from other channels
        auxiliary_context = await self._build_auxiliary_context(channel)

        # Build context for response generation (with auxiliary context)
        response_context = Context(
            persona=self._config.persona,
            conversation_history=conversation_history,
            auxiliary_context=auxiliary_context,
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
        await self._messaging_service.send_message(
            channel_id=channel.id,
            text=response_text,
            thread_ts=message.thread_ts,
        )

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

    async def _build_auxiliary_context(self, target_channel: Channel) -> str | None:
        """Build auxiliary context from other channels.

        Collects recent messages from channels other than the target channel
        and formats them as auxiliary context.

        Args:
            target_channel: The channel to exclude from auxiliary context.

        Returns:
            Formatted auxiliary context string, or None if no messages.
        """
        all_channels = await self._channel_monitor.get_channels()
        other_channels = [ch for ch in all_channels if ch.id != target_channel.id]

        if not other_channels:
            return None

        context_parts: list[str] = []

        for channel in other_channels:
            messages = await self._channel_monitor.get_recent_messages(
                channel_id=channel.id,
                limit=self._config.response.message_limit,
            )

            if messages:
                # Format messages for this channel
                channel_context = f"### #{channel.name}\n"
                for msg in messages:
                    channel_context += f"- {msg.user.name}: {msg.text}\n"
                context_parts.append(channel_context)

        if not context_parts:
            return None

        return "\n".join(context_parts)

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

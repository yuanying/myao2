"""Reply to mention use case."""

from datetime import datetime, timezone

from myao2.config import PersonaConfig
from myao2.domain.entities import Context, Message, User
from myao2.domain.repositories import MessageRepository
from myao2.domain.services import (
    ConversationHistoryService,
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
        conversation_history_service: ConversationHistoryService,
        persona: PersonaConfig,
        bot_user_id: str,
    ) -> None:
        """Initialize the use case.

        Args:
            messaging_service: Service for sending messages.
            response_generator: Service for generating responses.
            message_repository: Repository for storing messages.
            conversation_history_service: Service for fetching conversation history.
            persona: Bot persona configuration.
            bot_user_id: The bot's user ID.
        """
        self._messaging_service = messaging_service
        self._response_generator = response_generator
        self._message_repository = message_repository
        self._conversation_history_service = conversation_history_service
        self._persona = persona
        self._bot_user_id = bot_user_id

    def execute(self, message: Message) -> None:
        """Execute the use case.

        Processing flow:
        1. Ignore messages from the bot itself
        2. Ignore messages that don't mention the bot
        3. Save the received message
        4. Fetch conversation history (thread or channel)
        5. Build Context
        6. Generate response with context
        7. Send response
        8. Save response message

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
        self._message_repository.save(message)

        # 4. Fetch conversation history
        conversation_history = self._get_conversation_history(message)

        # 5. Build Context
        context = self._build_context(conversation_history)

        # 6. Generate response with context
        response_text = self._response_generator.generate(
            user_message=message,
            context=context,
        )

        # 7. Send response
        self._messaging_service.send_message(
            channel_id=message.channel.id,
            text=response_text,
            thread_ts=message.thread_ts,
        )

        # 8. Save response message
        bot_message = self._create_bot_message(response_text, message)
        self._message_repository.save(bot_message)

    def _get_conversation_history(self, message: Message) -> list[Message]:
        """Get conversation history.

        Fetches thread history for messages in a thread,
        or channel history for messages in the channel.

        Args:
            message: The received message.

        Returns:
            Conversation history (oldest first).
        """
        if message.is_in_thread():
            # Fetch thread history for messages in a thread
            return self._conversation_history_service.fetch_thread_history(
                channel_id=message.channel.id,
                thread_ts=message.thread_ts,  # type: ignore[arg-type]
                limit=20,
            )
        else:
            # Fetch channel history for messages in the channel
            return self._conversation_history_service.fetch_channel_history(
                channel_id=message.channel.id,
                limit=20,
            )

    def _build_context(self, conversation_history: list[Message]) -> Context:
        """Build Context.

        Args:
            conversation_history: Conversation history.

        Returns:
            Context instance.
        """
        return Context(
            persona=self._persona,
            conversation_history=conversation_history,
        )

    def _create_bot_message(
        self,
        response_text: str,
        original_message: Message,
    ) -> Message:
        """Create bot response message.

        Args:
            response_text: Response text.
            original_message: Original message.

        Returns:
            Bot response Message.
        """
        return Message(
            id=str(datetime.now(timezone.utc).timestamp()),  # Temporary ID
            channel=original_message.channel,
            user=User(
                id=self._bot_user_id,
                name=self._persona.name,
                is_bot=True,
            ),
            text=response_text,
            timestamp=datetime.now(timezone.utc),
            thread_ts=original_message.thread_ts,
            mentions=[],
        )

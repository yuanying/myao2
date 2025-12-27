"""Reply to mention use case."""

from myao2.config import PersonaConfig
from myao2.domain.entities import Message
from myao2.domain.services import MessagingService, ResponseGenerator


class ReplyToMentionUseCase:
    """Use case for replying to messages that mention the bot.

    This use case handles incoming messages and generates responses
    when the bot is mentioned.
    """

    def __init__(
        self,
        messaging_service: MessagingService,
        response_generator: ResponseGenerator,
        persona: PersonaConfig,
        bot_user_id: str,
    ) -> None:
        """Initialize the use case.

        Args:
            messaging_service: Service for sending messages.
            response_generator: Service for generating responses.
            persona: Bot persona configuration.
            bot_user_id: The bot's user ID.
        """
        self._messaging_service = messaging_service
        self._response_generator = response_generator
        self._persona = persona
        self._bot_user_id = bot_user_id

    def execute(self, message: Message) -> None:
        """Execute the use case.

        Responds to a message if:
        - The bot is mentioned in the message
        - The message is not from the bot itself

        If the message is in a thread, the response is sent to that thread.

        Args:
            message: The received message.
        """
        if message.user.id == self._bot_user_id:
            return

        if not message.mentions_user(self._bot_user_id):
            return

        response_text = self._response_generator.generate(
            user_message=message.text,
            system_prompt=self._persona.system_prompt,
        )

        self._messaging_service.send_message(
            channel_id=message.channel.id,
            text=response_text,
            thread_ts=message.thread_ts,
        )

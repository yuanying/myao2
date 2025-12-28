"""アプリケーションのエントリポイント"""

import logging
import sys
from pathlib import Path

from myao2.application.use_cases import ReplyToMentionUseCase
from myao2.config import ConfigError, load_config
from myao2.infrastructure.llm import LiteLLMResponseGenerator, LLMClient
from myao2.infrastructure.persistence import DatabaseManager, SQLiteMessageRepository
from myao2.infrastructure.slack import (
    SlackAppRunner,
    SlackConversationHistoryService,
    SlackEventAdapter,
    SlackMessagingService,
    create_slack_app,
)
from myao2.presentation import register_handlers

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main() -> None:
    """アプリケーションを起動する"""
    config_path = Path("config.yaml")
    if not config_path.exists():
        logger.error("config.yaml not found")
        sys.exit(1)

    try:
        config = load_config(config_path)
    except ConfigError as e:
        logger.error("Failed to load config: %s", e)
        sys.exit(1)

    app = create_slack_app(config.slack)

    # Get bot user ID
    auth_result = app.client.auth_test()
    bot_user_id = auth_result["user_id"]
    logger.info("Bot user ID: %s", bot_user_id)

    # Initialize database
    db_manager = DatabaseManager(config.memory.database_path)
    db_manager.create_tables()

    # Build dependencies
    messaging_service = SlackMessagingService(app.client)
    event_adapter = SlackEventAdapter(app.client)
    conversation_history_service = SlackConversationHistoryService(app.client)
    message_repository = SQLiteMessageRepository(db_manager.get_session)

    # Use default LLM config
    if "default" not in config.llm:
        logger.error("No 'default' LLM config found")
        sys.exit(1)

    llm_config = config.llm["default"]
    llm_client = LLMClient(llm_config)
    response_generator = LiteLLMResponseGenerator(llm_client)

    # Initialize use case
    reply_use_case = ReplyToMentionUseCase(
        messaging_service=messaging_service,
        response_generator=response_generator,
        message_repository=message_repository,
        conversation_history_service=conversation_history_service,
        persona=config.persona,
        bot_user_id=bot_user_id,
    )

    register_handlers(app, reply_use_case, event_adapter, bot_user_id)

    logger.info("Starting %s...", config.persona.name)
    runner = SlackAppRunner(app, config.slack.app_token)

    try:
        runner.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        runner.stop()


if __name__ == "__main__":
    main()

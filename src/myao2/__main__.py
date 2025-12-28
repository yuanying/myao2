"""アプリケーションのエントリポイント"""

import asyncio
import logging
import sys
from pathlib import Path

from myao2.application.use_cases import ReplyToMentionUseCase
from myao2.config import ConfigError, LoggingConfig, load_config
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

# Default logging for early startup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def configure_logging(config: LoggingConfig | None) -> None:
    """Configure logging based on config.

    Args:
        config: Logging configuration. If None, uses defaults.
    """
    if config is None:
        return

    # Get root logger
    root_logger = logging.getLogger()

    # Set root level
    level = getattr(logging, config.level.upper(), logging.INFO)
    root_logger.setLevel(level)

    # Update handler format if specified
    if root_logger.handlers:
        formatter = logging.Formatter(config.format)
        for handler in root_logger.handlers:
            handler.setFormatter(formatter)

    # Configure individual loggers
    if config.loggers:
        for logger_name, logger_level in config.loggers.items():
            individual_logger = logging.getLogger(logger_name)
            individual_level = getattr(logging, logger_level.upper(), logging.INFO)
            individual_logger.setLevel(individual_level)
            logger.debug(
                "Set logger '%s' to level %s", logger_name, logger_level.upper()
            )


async def main() -> None:
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

    # Apply logging configuration
    configure_logging(config.logging)

    app = create_slack_app(config.slack)

    # Get bot user ID
    messaging_service = SlackMessagingService(app.client)
    bot_user_id = await messaging_service.get_bot_user_id()
    logger.info("Bot user ID: %s", bot_user_id)

    # Initialize database
    db_manager = DatabaseManager(config.memory.database_path)
    await db_manager.create_tables()

    # Build dependencies
    event_adapter = SlackEventAdapter(app.client)
    conversation_history_service = SlackConversationHistoryService(app.client)
    message_repository = SQLiteMessageRepository(db_manager.get_session)

    # Use default LLM config
    if "default" not in config.llm:
        logger.error("No 'default' LLM config found")
        sys.exit(1)

    llm_config = config.llm["default"]
    llm_client = LLMClient(llm_config)
    debug_llm_messages = bool(config.logging and config.logging.debug_llm_messages)
    response_generator = LiteLLMResponseGenerator(
        llm_client,
        debug_llm_messages=debug_llm_messages,
    )

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
        await runner.start()
    finally:
        logger.info("Shutting down...")
        await runner.stop()


def run() -> None:
    """Run the async main function."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    run()

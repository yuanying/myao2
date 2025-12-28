"""アプリケーションのエントリポイント"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from myao2.application.services import PeriodicChecker
from myao2.application.use_cases import AutonomousResponseUseCase, ReplyToMentionUseCase
from myao2.config import ConfigError, LoggingConfig, load_config
from myao2.infrastructure.llm import (
    LiteLLMResponseGenerator,
    LLMClient,
    LLMResponseJudgment,
)
from myao2.infrastructure.persistence import (
    DatabaseManager,
    DBChannelMonitor,
    DBConversationHistoryService,
    SQLiteChannelRepository,
    SQLiteMessageRepository,
    SQLiteUserRepository,
)
from myao2.infrastructure.slack import (
    SlackAppRunner,
    SlackChannelInitializer,
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
    message_repository = SQLiteMessageRepository(db_manager.get_session)
    user_repository = SQLiteUserRepository(db_manager.get_session)
    channel_repository = SQLiteChannelRepository(db_manager.get_session)

    event_adapter = SlackEventAdapter(
        client=app.client,
        user_repository=user_repository,
        channel_repository=channel_repository,
    )
    conversation_history_service = DBConversationHistoryService(message_repository)

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

    # Initialize use case for mention replies
    reply_use_case = ReplyToMentionUseCase(
        messaging_service=messaging_service,
        response_generator=response_generator,
        message_repository=message_repository,
        conversation_history_service=conversation_history_service,
        persona=config.persona,
        bot_user_id=bot_user_id,
    )

    register_handlers(
        app, reply_use_case, event_adapter, bot_user_id, message_repository
    )

    # Sync channels from Slack at startup
    channel_initializer = SlackChannelInitializer(
        client=app.client,
        channel_repository=channel_repository,
    )
    await channel_initializer.sync_channels()

    # Initialize autonomous response components
    # Use judgment LLM config if available, otherwise use default
    judgment_llm_config = config.llm.get("judgment", config.llm["default"])
    judgment_llm_client = LLMClient(judgment_llm_config)
    response_judgment = LLMResponseJudgment(client=judgment_llm_client)

    channel_monitor = DBChannelMonitor(
        message_repository=message_repository,
        channel_repository=channel_repository,
        bot_user_id=bot_user_id,
    )

    autonomous_response_use_case = AutonomousResponseUseCase(
        channel_monitor=channel_monitor,
        response_judgment=response_judgment,
        response_generator=response_generator,
        messaging_service=messaging_service,
        message_repository=message_repository,
        conversation_history_service=conversation_history_service,
        config=config,
        bot_user_id=bot_user_id,
    )

    periodic_checker = PeriodicChecker(
        autonomous_response_use_case=autonomous_response_use_case,
        config=config.response,
    )

    runner = SlackAppRunner(app, config.slack.app_token)

    logger.info("Starting %s...", config.persona.name)
    logger.info("Starting Socket Mode handler...")
    logger.info(
        "Starting periodic checker (interval: %ds)...",
        config.response.check_interval_seconds,
    )

    # Create tasks
    runner_task = asyncio.create_task(runner.start())
    checker_task = asyncio.create_task(periodic_checker.start())

    # Setup signal handlers for graceful shutdown
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def shutdown_handler() -> None:
        logger.info("Received shutdown signal...")
        stop_event.set()

    loop.add_signal_handler(signal.SIGINT, shutdown_handler)
    loop.add_signal_handler(signal.SIGTERM, shutdown_handler)

    # Wait for shutdown signal
    await stop_event.wait()

    # Graceful shutdown
    logger.info("Shutting down...")

    # Stop periodic checker (has graceful stop)
    await periodic_checker.stop()

    # Try to close runner with timeout
    closed = await runner.close(timeout=5.0)
    if not closed:
        logger.warning("Runner close timed out, cancelling tasks...")

    # Cancel any remaining tasks
    runner_task.cancel()
    checker_task.cancel()

    # Wait for tasks to complete
    await asyncio.gather(runner_task, checker_task, return_exceptions=True)

    # Close database connections
    await db_manager.close()

    logger.info("Shutdown complete")


def run() -> None:
    """Run the async main function."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down...")


if __name__ == "__main__":
    run()

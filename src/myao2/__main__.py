"""アプリケーションのエントリポイント"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from myao2.application.services import PeriodicChecker
from myao2.application.services.background_memory import BackgroundMemoryGenerator
from myao2.application.use_cases import AutonomousResponseUseCase, ReplyToMentionUseCase
from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.config import ConfigError, LoggingConfig, load_config
from myao2.infrastructure.llm.strands import (
    StrandsMemorySummarizer,
    StrandsResponseGenerator,
    StrandsResponseJudgment,
    create_model,
)
from myao2.infrastructure.llm.strands.memo_tools import MemoToolsFactory
from myao2.infrastructure.persistence import (
    DatabaseManager,
    DBChannelMonitor,
    SQLiteChannelRepository,
    SQLiteJudgmentCacheRepository,
    SQLiteMemoRepository,
    SQLiteMemoryRepository,
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
    memory_repository = SQLiteMemoryRepository(db_manager.get_session)
    memo_repository = SQLiteMemoRepository(db_manager.get_session)

    event_adapter = SlackEventAdapter(
        client=app.client,
        user_repository=user_repository,
        channel_repository=channel_repository,
    )

    # Validate agents config
    if "response" not in config.agents:
        logger.error("No 'response' agent config found")
        sys.exit(1)
    if "judgment" not in config.agents:
        logger.error("No 'judgment' agent config found")
        sys.exit(1)
    if "memory" not in config.agents:
        logger.error("No 'memory' agent config found")
        sys.exit(1)

    # Create models (once at startup, reused across requests)
    response_model = create_model(config.agents["response"])
    judgment_model = create_model(config.agents["judgment"])
    memory_model = create_model(config.agents["memory"])

    # Create components
    memo_tools_factory = MemoToolsFactory(memo_repository=memo_repository)
    response_generator = StrandsResponseGenerator(
        response_model,
        memo_tools_factory=memo_tools_factory,
    )

    # Initialize use case for mention replies
    reply_use_case = ReplyToMentionUseCase(
        messaging_service=messaging_service,
        response_generator=response_generator,
        message_repository=message_repository,
        channel_repository=channel_repository,
        memory_repository=memory_repository,
        persona=config.persona,
        bot_user_id=bot_user_id,
        memo_repository=memo_repository,
    )

    register_handlers(
        app,
        reply_use_case,
        event_adapter,
        bot_user_id,
        message_repository,
        channel_repository,
    )

    # Sync channels from Slack at startup
    channel_initializer = SlackChannelInitializer(
        client=app.client,
        channel_repository=channel_repository,
    )
    await channel_initializer.sync_channels()

    # Initialize autonomous response components
    response_judgment = StrandsResponseJudgment(judgment_model)

    channel_monitor = DBChannelMonitor(
        message_repository=message_repository,
        channel_repository=channel_repository,
        bot_user_id=bot_user_id,
    )

    judgment_cache_repository = SQLiteJudgmentCacheRepository(db_manager.get_session)

    autonomous_response_use_case = AutonomousResponseUseCase(
        channel_monitor=channel_monitor,
        response_judgment=response_judgment,
        response_generator=response_generator,
        messaging_service=messaging_service,
        message_repository=message_repository,
        judgment_cache_repository=judgment_cache_repository,
        channel_repository=channel_repository,
        memory_repository=memory_repository,
        config=config,
        bot_user_id=bot_user_id,
        channel_sync_service=channel_initializer,
        memo_repository=memo_repository,
    )

    periodic_checker = PeriodicChecker(
        autonomous_response_use_case=autonomous_response_use_case,
        config=config.response,
    )

    # Initialize memory generation components
    memory_summarizer = StrandsMemorySummarizer(
        model=memory_model,
        config=config.memory,
    )

    generate_memory_use_case = GenerateMemoryUseCase(
        memory_repository=memory_repository,
        message_repository=message_repository,
        channel_repository=channel_repository,
        memory_summarizer=memory_summarizer,
        config=config.memory,
        persona=config.persona,
    )

    background_memory_generator = BackgroundMemoryGenerator(
        generate_memory_use_case=generate_memory_use_case,
        config=config.memory,
    )

    runner = SlackAppRunner(app, config.slack.app_token)

    logger.info("Starting %s...", config.persona.name)
    logger.info("Starting Socket Mode handler...")
    logger.info(
        "Starting periodic checker (interval: %ds)...",
        config.response.check_interval_seconds,
    )
    logger.info(
        "Starting background memory generator (interval: %ds)...",
        config.memory.long_term_update_interval_seconds,
    )

    # Create tasks
    runner_task = asyncio.create_task(runner.start())
    checker_task = asyncio.create_task(periodic_checker.start())
    memory_task = asyncio.create_task(background_memory_generator.start())

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

    # Stop periodic checker and background memory generator (have graceful stop)
    await periodic_checker.stop()
    await background_memory_generator.stop()

    # Try to close runner with timeout
    closed = await runner.close(timeout=5.0)
    if not closed:
        logger.warning("Runner close timed out, cancelling tasks...")

    # Cancel any remaining tasks
    runner_task.cancel()
    checker_task.cancel()
    memory_task.cancel()

    # Wait for tasks to complete
    await asyncio.gather(runner_task, checker_task, memory_task, return_exceptions=True)

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

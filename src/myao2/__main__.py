"""アプリケーションのエントリポイント"""

import asyncio
import logging
import signal
import sys
from pathlib import Path

from myao2.application.handlers import (
    AutonomousCheckEventHandler,
    ChannelSyncEventHandler,
    MessageEventHandler,
    SummaryEventHandler,
)
from myao2.application.use_cases import AutonomousResponseUseCase
from myao2.application.use_cases.generate_memory import GenerateMemoryUseCase
from myao2.config import ConfigError, LoggingConfig, load_config
from myao2.infrastructure.events.dispatcher import EventDispatcher
from myao2.infrastructure.events.loop import EventLoop
from myao2.infrastructure.events.queue import EventQueue
from myao2.infrastructure.events.scheduler import EventScheduler
from myao2.infrastructure.llm.strands import (
    StrandsMemorySummarizer,
    StrandsResponseGenerator,
    StrandsResponseJudgment,
    create_model,
)
from myao2.infrastructure.llm.strands.memo_tools import MemoToolsFactory
from myao2.infrastructure.llm.strands.web_fetch_tools import WebFetchToolsFactory
from myao2.infrastructure.llm.strands.web_search_tools import WebSearchToolsFactory
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
    judgment_cache_repository = SQLiteJudgmentCacheRepository(db_manager.get_session)

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

    # Create web_fetch_tools_factory if enabled
    web_fetch_tools_factory: WebFetchToolsFactory | None = None
    if config.tools and config.tools.web_fetch and config.tools.web_fetch.enabled:
        web_fetch_tools_factory = WebFetchToolsFactory(config.tools.web_fetch)
        logger.info("Web fetch tool enabled")

    # Create web_search_tools_factory if enabled
    web_search_tools_factory: WebSearchToolsFactory | None = None
    if config.tools and config.tools.web_search and config.tools.web_search.enabled:
        if config.tools.web_search.api_key:
            web_search_tools_factory = WebSearchToolsFactory(config.tools.web_search)
            logger.info("Web search tool enabled")
        else:
            logger.warning(
                "Web search tool is enabled but API key is not set. "
                "Tool not registered."
            )

    response_generator = StrandsResponseGenerator(
        response_model,
        memo_tools_factory=memo_tools_factory,
        web_fetch_tools_factory=web_fetch_tools_factory,
        web_search_tools_factory=web_search_tools_factory,
    )

    # Initialize event system
    event_queue = EventQueue()
    event_dispatcher = EventDispatcher()

    # Initialize message event handler
    message_event_handler = MessageEventHandler(
        messaging_service=messaging_service,
        response_generator=response_generator,
        message_repository=message_repository,
        channel_repository=channel_repository,
        memory_repository=memory_repository,
        persona=config.persona,
        bot_user_id=bot_user_id,
        memo_repository=memo_repository,
        judgment_cache_repository=judgment_cache_repository,
    )
    event_dispatcher.register_handler(message_event_handler.handle)

    register_handlers(
        app,
        event_queue,
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

    # Initialize autonomous response use case (without channel_sync_service)
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
        channel_sync_service=None,  # Channel sync is now handled by event
        memo_repository=memo_repository,
    )

    # Initialize autonomous check event handler
    autonomous_check_handler = AutonomousCheckEventHandler(
        autonomous_response_use_case=autonomous_response_use_case,
    )
    event_dispatcher.register_handler(autonomous_check_handler.handle)

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

    # Initialize summary event handler
    summary_event_handler = SummaryEventHandler(
        generate_memory_use_case=generate_memory_use_case,
    )
    event_dispatcher.register_handler(summary_event_handler.handle)

    # Initialize channel sync event handler
    channel_sync_handler = ChannelSyncEventHandler(
        channel_sync_service=channel_initializer,
    )
    event_dispatcher.register_handler(channel_sync_handler.handle)

    # Initialize event loop and scheduler
    event_loop = EventLoop(
        queue=event_queue,
        dispatcher=event_dispatcher,
    )

    event_scheduler = EventScheduler(
        queue=event_queue,
        check_interval_seconds=config.response.check_interval_seconds,
        summary_interval_seconds=config.memory.long_term_update_interval_seconds,
        channel_sync_interval_seconds=config.response.check_interval_seconds,
    )

    runner = SlackAppRunner(app, config.slack.app_token)

    logger.info("Starting %s...", config.persona.name)
    logger.info("Starting Socket Mode handler...")
    logger.info("Starting event loop...")
    logger.info(
        "Starting event scheduler (check=%ds, summary=%ds, channel_sync=%ds)...",
        config.response.check_interval_seconds,
        config.memory.long_term_update_interval_seconds,
        config.response.check_interval_seconds,
    )

    # Create tasks
    runner_task = asyncio.create_task(runner.start())
    event_loop_task = asyncio.create_task(event_loop.start())
    event_scheduler_task = asyncio.create_task(event_scheduler.start())

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

    # Stop event loop and scheduler (have graceful stop)
    await event_loop.stop()
    await event_scheduler.stop()

    # Try to close runner with timeout
    closed = await runner.close(timeout=5.0)
    if not closed:
        logger.warning("Runner close timed out, cancelling tasks...")

    # Cancel any remaining tasks
    runner_task.cancel()
    event_loop_task.cancel()
    event_scheduler_task.cancel()

    # Wait for tasks to complete
    await asyncio.gather(
        runner_task, event_loop_task, event_scheduler_task, return_exceptions=True
    )

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

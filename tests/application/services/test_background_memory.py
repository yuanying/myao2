"""Tests for BackgroundMemoryGenerator service."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.application.services.background_memory import BackgroundMemoryGenerator
from myao2.config.models import MemoryConfig


@pytest.fixture
def mock_generate_memory_use_case() -> Mock:
    """Create mock GenerateMemoryUseCase."""
    usecase = Mock()
    usecase.execute = AsyncMock()
    return usecase


@pytest.fixture
def config() -> MemoryConfig:
    """Create test MemoryConfig with short interval."""
    return MemoryConfig(
        database_path=":memory:",
        long_term_update_interval_seconds=1,
    )


@pytest.fixture
def long_interval_config() -> MemoryConfig:
    """Create test MemoryConfig with long interval."""
    return MemoryConfig(
        database_path=":memory:",
        long_term_update_interval_seconds=10,
    )


@pytest.fixture
def generator(
    mock_generate_memory_use_case: Mock,
    config: MemoryConfig,
) -> BackgroundMemoryGenerator:
    """Create BackgroundMemoryGenerator instance."""
    return BackgroundMemoryGenerator(
        generate_memory_use_case=mock_generate_memory_use_case,
        config=config,
    )


class TestBackgroundMemoryGeneratorStart:
    """Tests for start method."""

    async def test_executes_immediately_on_start(
        self,
        generator: BackgroundMemoryGenerator,
        mock_generate_memory_use_case: Mock,
    ) -> None:
        """Test that execute() is called immediately on start."""
        task = asyncio.create_task(generator.start())

        # Wait for at least one execution
        await asyncio.sleep(0.1)

        # Stop the generator
        await generator.stop()
        await task

        # Verify usecase was called at least once
        assert mock_generate_memory_use_case.execute.await_count >= 1

    async def test_executes_periodically(
        self,
        generator: BackgroundMemoryGenerator,
        mock_generate_memory_use_case: Mock,
    ) -> None:
        """Test that execute() is called periodically."""
        task = asyncio.create_task(generator.start())

        # Wait for multiple executions (interval=1s, wait 2.5s)
        await asyncio.sleep(2.5)

        await generator.stop()
        await task

        # Should have executed at least twice (immediate + 1-2 intervals)
        assert mock_generate_memory_use_case.execute.await_count >= 2

    async def test_stop_ends_loop(
        self,
        generator: BackgroundMemoryGenerator,
    ) -> None:
        """Test that stop() ends the loop."""
        task = asyncio.create_task(generator.start())

        # Wait a bit
        await asyncio.sleep(0.05)

        # Stop should end the loop
        await generator.stop()
        await task

        # Task should complete without error
        assert task.done()
        assert not generator.is_running

    async def test_continues_after_exception(
        self,
        generator: BackgroundMemoryGenerator,
        mock_generate_memory_use_case: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that loop continues after exception in execute()."""
        call_count = 0
        continue_event = asyncio.Event()

        async def execute_with_error() -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Test error")
            else:
                # Signal that we've been called again after error
                continue_event.set()

        mock_generate_memory_use_case.execute = AsyncMock(
            side_effect=execute_with_error
        )

        task = asyncio.create_task(generator.start())

        # Wait until second execution or timeout
        try:
            await asyncio.wait_for(continue_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass

        await generator.stop()
        await task

        # Should have been called multiple times despite error
        assert call_count >= 2


class TestBackgroundMemoryGeneratorStop:
    """Tests for stop method."""

    async def test_stop_sets_is_running_false(
        self,
        generator: BackgroundMemoryGenerator,
    ) -> None:
        """Test that stop() sets is_running to False."""
        task = asyncio.create_task(generator.start())

        await asyncio.sleep(0.05)
        assert generator.is_running

        await generator.stop()
        await task

        assert not generator.is_running

    async def test_stop_during_sleep_exits_immediately(
        self,
        mock_generate_memory_use_case: Mock,
        long_interval_config: MemoryConfig,
    ) -> None:
        """Test that stop() during sleep interval exits immediately."""
        generator = BackgroundMemoryGenerator(
            generate_memory_use_case=mock_generate_memory_use_case,
            config=long_interval_config,
        )

        task = asyncio.create_task(generator.start())

        # Wait for first execution to complete
        await asyncio.sleep(0.05)

        # Stop should exit immediately, not wait for 10s interval
        start_time = asyncio.get_running_loop().time()
        await generator.stop()
        await task
        elapsed = asyncio.get_running_loop().time() - start_time

        # Should have stopped quickly, not waiting for full interval
        assert elapsed < 1.0


class TestBackgroundMemoryGeneratorIsRunning:
    """Tests for is_running property."""

    async def test_is_running_false_before_start(
        self,
        generator: BackgroundMemoryGenerator,
    ) -> None:
        """Test that is_running is False before start."""
        assert not generator.is_running

    async def test_is_running_true_during_execution(
        self,
        generator: BackgroundMemoryGenerator,
    ) -> None:
        """Test that is_running is True during execution."""
        task = asyncio.create_task(generator.start())

        await asyncio.sleep(0.05)
        assert generator.is_running

        await generator.stop()
        await task

    async def test_is_running_false_after_stop(
        self,
        generator: BackgroundMemoryGenerator,
    ) -> None:
        """Test that is_running is False after stop."""
        task = asyncio.create_task(generator.start())

        await asyncio.sleep(0.05)
        await generator.stop()
        await task

        assert not generator.is_running


class TestBackgroundMemoryGeneratorLogging:
    """Tests for logging."""

    async def test_logs_error_on_exception(
        self,
        generator: BackgroundMemoryGenerator,
        mock_generate_memory_use_case: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that errors are logged."""
        mock_generate_memory_use_case.execute = AsyncMock(
            side_effect=RuntimeError("Test error")
        )

        with caplog.at_level(logging.ERROR):
            task = asyncio.create_task(generator.start())
            await asyncio.sleep(0.1)
            await generator.stop()
            await task

        # Error should be logged
        assert any(
            record.levelno == logging.ERROR
            and "memory generation" in record.getMessage().lower()
            for record in caplog.records
        )

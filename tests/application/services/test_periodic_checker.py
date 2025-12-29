"""Tests for PeriodicChecker service."""

import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from myao2.application.services.periodic_checker import PeriodicChecker
from myao2.config import ResponseConfig


@pytest.fixture
def mock_usecase() -> Mock:
    """Create mock AutonomousResponseUseCase."""
    usecase = Mock()
    usecase.execute = AsyncMock()
    return usecase


@pytest.fixture
def config() -> ResponseConfig:
    """Create test ResponseConfig."""
    return ResponseConfig(
        check_interval_seconds=1,
        min_wait_seconds=300,
        message_limit=20,
    )


@pytest.fixture
def long_interval_config() -> ResponseConfig:
    """Create test ResponseConfig with long interval."""
    return ResponseConfig(
        check_interval_seconds=10,
        min_wait_seconds=300,
        message_limit=20,
    )


@pytest.fixture
def checker(mock_usecase: Mock, config: ResponseConfig) -> PeriodicChecker:
    """Create PeriodicChecker instance."""
    return PeriodicChecker(
        autonomous_response_use_case=mock_usecase,
        config=config,
    )


class TestPeriodicCheckerStart:
    """Tests for start method."""

    async def test_executes_usecase_in_loop(
        self,
        checker: PeriodicChecker,
        mock_usecase: Mock,
    ) -> None:
        """Test that usecase is executed in the loop."""
        # Start checker in background
        task = asyncio.create_task(checker.start())

        # Wait for at least one execution
        await asyncio.sleep(0.1)

        # Stop the checker
        await checker.stop()
        await task

        # Verify usecase was called at least once
        assert mock_usecase.execute.await_count >= 1

    async def test_stop_ends_loop(
        self,
        checker: PeriodicChecker,
    ) -> None:
        """Test that stop() ends the loop."""
        task = asyncio.create_task(checker.start())

        # Wait a bit
        await asyncio.sleep(0.05)

        # Stop should end the loop
        await checker.stop()
        await task

        # Task should complete without error
        assert task.done()
        assert not checker.is_running

    async def test_continues_after_exception(
        self,
        checker: PeriodicChecker,
        mock_usecase: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that loop continues after exception in usecase."""
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

        mock_usecase.execute = AsyncMock(side_effect=execute_with_error)

        task = asyncio.create_task(checker.start())

        # Wait until second execution or timeout
        try:
            await asyncio.wait_for(continue_event.wait(), timeout=2.0)
        except asyncio.TimeoutError:
            pass

        await checker.stop()
        await task

        # Should have been called multiple times despite error
        assert call_count >= 2
        # Error should be logged with the expected message format
        assert any(
            record.levelno == logging.ERROR
            and "Periodic check failed" in record.getMessage()
            for record in caplog.records
        )


class TestPeriodicCheckerStop:
    """Tests for stop method."""

    async def test_stop_sets_is_running_false(
        self,
        checker: PeriodicChecker,
    ) -> None:
        """Test that stop() sets is_running to False."""
        task = asyncio.create_task(checker.start())

        await asyncio.sleep(0.05)
        assert checker.is_running

        await checker.stop()
        await task

        assert not checker.is_running

    async def test_stop_during_sleep_exits_immediately(
        self,
        mock_usecase: Mock,
        long_interval_config: ResponseConfig,
    ) -> None:
        """Test that stop() during sleep interval exits immediately."""
        checker = PeriodicChecker(
            autonomous_response_use_case=mock_usecase,
            config=long_interval_config,
        )

        task = asyncio.create_task(checker.start())

        # Wait for first execution to complete
        await asyncio.sleep(0.05)

        # Stop should exit immediately, not wait for 10s interval
        start_time = asyncio.get_running_loop().time()
        await checker.stop()
        await task
        elapsed = asyncio.get_running_loop().time() - start_time

        # Should have stopped quickly, not waiting for full interval
        assert elapsed < 1.0


class TestPeriodicCheckerIsRunning:
    """Tests for is_running property."""

    async def test_is_running_false_before_start(
        self,
        checker: PeriodicChecker,
    ) -> None:
        """Test that is_running is False before start."""
        assert not checker.is_running

    async def test_is_running_true_during_execution(
        self,
        checker: PeriodicChecker,
    ) -> None:
        """Test that is_running is True during execution."""
        task = asyncio.create_task(checker.start())

        await asyncio.sleep(0.05)
        assert checker.is_running

        await checker.stop()
        await task

    async def test_is_running_false_after_stop(
        self,
        checker: PeriodicChecker,
    ) -> None:
        """Test that is_running is False after stop."""
        task = asyncio.create_task(checker.start())

        await asyncio.sleep(0.05)
        await checker.stop()
        await task

        assert not checker.is_running


class TestPeriodicCheckerLogging:
    """Tests for logging."""

    async def test_logs_error_on_exception(
        self,
        checker: PeriodicChecker,
        mock_usecase: Mock,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that errors are logged."""
        mock_usecase.execute = AsyncMock(side_effect=RuntimeError("Test error"))

        with caplog.at_level(logging.ERROR):
            task = asyncio.create_task(checker.start())
            await asyncio.sleep(0.1)
            await checker.stop()
            await task

        # Error should be logged with the expected message format
        assert any(
            record.levelno == logging.ERROR
            and "Periodic check failed" in record.getMessage()
            for record in caplog.records
        )

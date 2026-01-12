"""テレメトリ設定のテスト"""

import os
from typing import Generator
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def clean_env() -> Generator[None, None, None]:
    """環境変数をクリーンアップするフィクスチャ"""
    original_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    original_service = os.environ.get("OTEL_SERVICE_NAME")

    # Clear environment variables before test
    os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)
    os.environ.pop("OTEL_SERVICE_NAME", None)

    yield

    # Restore original values
    if original_endpoint is not None:
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = original_endpoint
    else:
        os.environ.pop("OTEL_EXPORTER_OTLP_ENDPOINT", None)

    if original_service is not None:
        os.environ["OTEL_SERVICE_NAME"] = original_service
    else:
        os.environ.pop("OTEL_SERVICE_NAME", None)


class TestConfigureTelemetry:
    """configure_telemetry関数のテスト"""

    def test_disabled_without_endpoint(self, clean_env: None) -> None:
        """OTEL_EXPORTER_OTLP_ENDPOINT未設定時はテレメトリ無効"""
        from myao2.__main__ import configure_telemetry

        # Use patch.dict to ensure environment variable is not set during test
        with patch.dict(os.environ, {}, clear=True):
            # Mock StrandsTelemetry to verify it's not called
            with patch("strands.telemetry.StrandsTelemetry") as mock_telemetry:
                configure_telemetry()
                # StrandsTelemetry should not be called when endpoint is not set
                mock_telemetry.assert_not_called()

    def test_enabled_with_endpoint(self, clean_env: None) -> None:
        """OTEL_EXPORTER_OTLP_ENDPOINT設定時はテレメトリ有効"""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        os.environ.pop("OTEL_SERVICE_NAME", None)

        from myao2.__main__ import configure_telemetry

        with patch("strands.telemetry.StrandsTelemetry") as mock_telemetry_class:
            mock_telemetry = MagicMock()
            mock_telemetry_class.return_value = mock_telemetry

            with patch("myao2.__main__.logger") as mock_logger:
                configure_telemetry()

                mock_telemetry_class.assert_called_once()
                mock_telemetry.setup_otlp_exporter.assert_called_once()
                mock_logger.info.assert_called_once()
                assert "http://localhost:4318" in mock_logger.info.call_args[0][1]

    def test_sets_default_service_name(self, clean_env: None) -> None:
        """OTEL_SERVICE_NAME未設定時はデフォルト値が設定される"""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        os.environ.pop("OTEL_SERVICE_NAME", None)

        from myao2.__main__ import configure_telemetry

        with patch("strands.telemetry.StrandsTelemetry") as mock_telemetry_class:
            mock_telemetry = MagicMock()
            mock_telemetry_class.return_value = mock_telemetry

            configure_telemetry()

            assert os.environ.get("OTEL_SERVICE_NAME") == "myao2"

    def test_service_name_not_overwritten_when_already_set(
        self, clean_env: None
    ) -> None:
        """OTEL_SERVICE_NAME設定済みの場合は上書きしない"""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        os.environ["OTEL_SERVICE_NAME"] = "custom-service"

        from myao2.__main__ import configure_telemetry

        with patch("strands.telemetry.StrandsTelemetry") as mock_telemetry_class:
            mock_telemetry = MagicMock()
            mock_telemetry_class.return_value = mock_telemetry

            configure_telemetry()

            assert os.environ.get("OTEL_SERVICE_NAME") == "custom-service"

    def test_handles_import_error(self, clean_env: None) -> None:
        """strands.telemetryがインポートできない場合は警告"""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"
        os.environ.pop("OTEL_SERVICE_NAME", None)

        from myao2.__main__ import configure_telemetry

        # Mock the import to raise ImportError
        with (
            patch.dict("sys.modules", {"strands.telemetry": None}),
            patch("myao2.__main__.logger") as mock_logger,
        ):
            # Remove the module from sys.modules to force re-import
            import sys

            # Save and remove the module
            saved_modules = {}
            for mod_name in list(sys.modules.keys()):
                if mod_name.startswith("strands"):
                    saved_modules[mod_name] = sys.modules.pop(mod_name)

            try:
                # Patch builtins.__import__ to raise ImportError for strands
                import builtins

                original_import = builtins.__import__

                def mock_import(
                    name: str,
                    globals: dict[str, object] | None = None,
                    locals: dict[str, object] | None = None,
                    fromlist: tuple[str, ...] = (),
                    level: int = 0,
                ) -> object:
                    if name == "strands.telemetry" or name.startswith("strands"):
                        raise ImportError(f"No module named '{name}'")
                    return original_import(name, globals, locals, fromlist, level)

                with patch.object(builtins, "__import__", mock_import):
                    configure_telemetry()

                mock_logger.warning.assert_called_once()
                assert "not installed" in mock_logger.warning.call_args[0][0]
            finally:
                # Restore modules
                sys.modules.update(saved_modules)

    def test_handles_general_exception(self, clean_env: None) -> None:
        """一般的な例外が発生した場合は警告"""
        os.environ["OTEL_EXPORTER_OTLP_ENDPOINT"] = "http://localhost:4318"

        from myao2.__main__ import configure_telemetry

        with patch("strands.telemetry.StrandsTelemetry") as mock_telemetry_class:
            mock_telemetry_class.side_effect = RuntimeError("Connection failed")

            with patch("myao2.__main__.logger") as mock_logger:
                configure_telemetry()

                mock_logger.warning.assert_called_once()
                warning_msg = mock_logger.warning.call_args[0][0]
                assert "Failed to setup telemetry" in warning_msg

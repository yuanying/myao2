"""Tests for create_model factory function."""

from unittest.mock import MagicMock, patch

import pytest

from myao2.config.models import AgentConfig
from myao2.infrastructure.llm.strands import create_model


class TestCreateModel:
    """Tests for create_model function."""

    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        """Create AgentConfig for testing."""
        return AgentConfig(
            model_id="openai/gpt-4o",
            params={"temperature": 0.7, "max_tokens": 1000},
            client_args={"api_key": "test-api-key"},
        )

    def test_create_model_success(self, agent_config: AgentConfig) -> None:
        """Test successful LiteLLMModel creation."""
        with patch(
            "myao2.infrastructure.llm.strands.factory.LiteLLMModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = create_model(agent_config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_id="openai/gpt-4o",
                params={"temperature": 0.7, "max_tokens": 1000},
                client_args={"api_key": "test-api-key"},
            )

    def test_create_model_with_empty_params(self) -> None:
        """Test LiteLLMModel creation with empty params."""
        config = AgentConfig(
            model_id="openai/gpt-4o",
            params={},
            client_args={"api_key": "test-api-key"},
        )

        with patch(
            "myao2.infrastructure.llm.strands.factory.LiteLLMModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = create_model(config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_id="openai/gpt-4o",
                params={},
                client_args={"api_key": "test-api-key"},
            )

    def test_create_model_with_empty_client_args(self) -> None:
        """Test LiteLLMModel creation with empty client_args."""
        config = AgentConfig(
            model_id="openai/gpt-4o",
            params={"temperature": 0.5},
            client_args={},
        )

        with patch(
            "myao2.infrastructure.llm.strands.factory.LiteLLMModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = create_model(config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_id="openai/gpt-4o",
                params={"temperature": 0.5},
                client_args={},
            )

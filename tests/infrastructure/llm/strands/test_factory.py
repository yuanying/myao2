"""Tests for StrandsAgentFactory."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from myao2.config.models import AgentConfig

if TYPE_CHECKING:
    from myao2.infrastructure.llm.strands import StrandsAgentFactory


class TestStrandsAgentFactory:
    """Tests for StrandsAgentFactory."""

    @pytest.fixture
    def factory(self) -> "StrandsAgentFactory":
        """Create StrandsAgentFactory instance."""
        from myao2.infrastructure.llm.strands import StrandsAgentFactory

        return StrandsAgentFactory()

    @pytest.fixture
    def agent_config(self) -> AgentConfig:
        """Create AgentConfig for testing."""
        return AgentConfig(
            model_id="openai/gpt-4o",
            params={"temperature": 0.7, "max_tokens": 1000},
            client_args={"api_key": "test-api-key"},
        )

    def test_create_model_success(
        self, factory: "StrandsAgentFactory", agent_config: AgentConfig
    ) -> None:
        """Test successful LiteLLMModel creation."""
        with patch(
            "myao2.infrastructure.llm.strands.factory.LiteLLMModel"
        ) as mock_model_class:
            mock_model = MagicMock()
            mock_model_class.return_value = mock_model

            result = factory.create_model(agent_config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_id="openai/gpt-4o",
                params={"temperature": 0.7, "max_tokens": 1000},
                client_args={"api_key": "test-api-key"},
            )

    def test_create_model_with_empty_params(
        self, factory: "StrandsAgentFactory"
    ) -> None:
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

            result = factory.create_model(config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_id="openai/gpt-4o",
                params={},
                client_args={"api_key": "test-api-key"},
            )

    def test_create_model_with_empty_client_args(
        self, factory: "StrandsAgentFactory"
    ) -> None:
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

            result = factory.create_model(config)

            assert result == mock_model
            mock_model_class.assert_called_once_with(
                model_id="openai/gpt-4o",
                params={"temperature": 0.5},
                client_args={},
            )



"""Tests for StrandsAgentFactory."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch

import pytest

from myao2.config.models import AgentConfig

if TYPE_CHECKING:
    from myao2.infrastructure.llm.strands import StrandsAgentFactory


class TestStrandsAgentFactoryCreateModel:
    """Tests for StrandsAgentFactory.create_model."""

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


class TestStrandsAgentFactoryCreateAgent:
    """Tests for StrandsAgentFactory.create_agent."""

    @pytest.fixture
    def factory(self) -> "StrandsAgentFactory":
        """Create StrandsAgentFactory instance."""
        from myao2.infrastructure.llm.strands import StrandsAgentFactory

        return StrandsAgentFactory()

    @pytest.fixture
    def mock_model(self) -> MagicMock:
        """Create mock LiteLLMModel."""
        return MagicMock()

    def test_create_agent_with_system_prompt(
        self, factory: "StrandsAgentFactory", mock_model: MagicMock
    ) -> None:
        """Test Agent creation with system_prompt."""
        with patch(
            "myao2.infrastructure.llm.strands.factory.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent

            result = factory.create_agent(
                model=mock_model,
                system_prompt="You are a helpful assistant.",
            )

            assert result == mock_agent
            mock_agent_class.assert_called_once_with(
                model=mock_model,
                system_prompt="You are a helpful assistant.",
                tools=[],
            )

    def test_create_agent_without_system_prompt(
        self, factory: "StrandsAgentFactory", mock_model: MagicMock
    ) -> None:
        """Test Agent creation without system_prompt."""
        with patch(
            "myao2.infrastructure.llm.strands.factory.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent

            result = factory.create_agent(model=mock_model)

            assert result == mock_agent
            mock_agent_class.assert_called_once_with(
                model=mock_model,
                system_prompt=None,
                tools=[],
            )

    def test_create_agent_with_tools(
        self, factory: "StrandsAgentFactory", mock_model: MagicMock
    ) -> None:
        """Test Agent creation with tools."""
        mock_tool1 = MagicMock()
        mock_tool2 = MagicMock()
        tools = [mock_tool1, mock_tool2]

        with patch(
            "myao2.infrastructure.llm.strands.factory.Agent"
        ) as mock_agent_class:
            mock_agent = MagicMock()
            mock_agent_class.return_value = mock_agent

            result = factory.create_agent(
                model=mock_model,
                system_prompt="Test prompt",
                tools=tools,
            )

            assert result == mock_agent
            mock_agent_class.assert_called_once_with(
                model=mock_model,
                system_prompt="Test prompt",
                tools=tools,
            )

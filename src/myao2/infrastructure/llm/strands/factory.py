"""StrandsAgentFactory for creating strands-agents Agent and LiteLLMModel."""

from strands import Agent
from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig


class StrandsAgentFactory:
    """Factory for creating strands-agents Agent and LiteLLMModel."""

    def create_model(self, config: AgentConfig) -> LiteLLMModel:
        """Create LiteLLMModel from AgentConfig.

        Args:
            config: Agent configuration

        Returns:
            LiteLLMModel instance
        """
        return LiteLLMModel(
            model_id=config.model_id,
            params=config.params,
            client_args=config.client_args,
        )

    def create_agent(
        self,
        model: LiteLLMModel,
        system_prompt: str | None = None,
        tools: list | None = None,
    ) -> Agent:
        """Create Agent from LiteLLMModel.

        Args:
            model: LiteLLMModel instance
            system_prompt: System prompt (fixed part)
            tools: Tool list (for future extension)

        Returns:
            Agent instance
        """
        return Agent(
            model=model,
            system_prompt=system_prompt,
            tools=tools or [],
        )

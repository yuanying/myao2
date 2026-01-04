"""StrandsAgentFactory for creating LiteLLMModel from AgentConfig."""

from strands.models.litellm import LiteLLMModel

from myao2.config.models import AgentConfig


class StrandsAgentFactory:
    """Factory for creating LiteLLMModel from AgentConfig."""

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

"""LLM client wrapper."""

import logging
from typing import Any

import litellm
from litellm.exceptions import AuthenticationError, RateLimitError

from myao2.config import LLMConfig
from myao2.infrastructure.llm.exceptions import (
    LLMAuthenticationError,
    LLMError,
    LLMRateLimitError,
)

logger = logging.getLogger(__name__)


class LLMClient:
    """LiteLLM wrapper client.

    This class provides a simplified interface to LiteLLM,
    applying configuration and handling errors.
    """

    def __init__(self, config: LLMConfig) -> None:
        """Initialize the client.

        Args:
            config: LLM configuration (model, temperature, max_tokens, etc.).
        """
        self._config = config

    def complete(
        self,
        messages: list[dict[str, str]],
        **kwargs: Any,
    ) -> str:
        """Execute chat completion.

        Args:
            messages: OpenAI-format message list.
                [{"role": "system", "content": "..."}, ...]
            **kwargs: Additional parameters (override config).

        Returns:
            Generated text.

        Raises:
            LLMAuthenticationError: Invalid API key.
            LLMRateLimitError: Rate limit exceeded.
            LLMError: Other API errors.
        """
        params = {
            "model": self._config.model,
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
            "messages": messages,
            **kwargs,
        }

        logger.debug("LLM request: model=%s", params["model"])

        try:
            response = litellm.completion(**params)
            content = response.choices[0].message.content
            logger.debug("LLM response received")
            return content
        except AuthenticationError as e:
            logger.error("LLM authentication error: %s", e)
            raise LLMAuthenticationError(str(e)) from e
        except RateLimitError as e:
            logger.warning("LLM rate limit exceeded: %s", e)
            raise LLMRateLimitError(str(e)) from e
        except Exception as e:
            logger.error("LLM error: %s", e)
            raise LLMError(str(e)) from e

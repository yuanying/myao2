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

    def __init__(
        self,
        config: LLMConfig,
        *,
        debug_llm_messages: bool = False,
    ) -> None:
        """Initialize the client.

        Args:
            config: LLM configuration (model, temperature, max_tokens, etc.).
            debug_llm_messages: If True, log LLM messages at INFO level.
        """
        self._config = config
        self._debug_llm_messages = debug_llm_messages

    def _should_log(self) -> bool:
        """Check if logging should occur.

        Returns:
            True if debug_llm_messages is enabled or logger is at DEBUG level.
        """
        return self._debug_llm_messages or logger.isEnabledFor(logging.DEBUG)

    def _log_messages(self, messages: list[dict[str, str]], caller: str) -> None:
        """Log LLM request messages.

        Args:
            messages: OpenAI-format message list.
            caller: Caller identifier for log context.
        """
        if not self._should_log():
            return

        level = logging.INFO if self._debug_llm_messages else logging.DEBUG
        logger.log(level, "=== LLM Request [%s] ===", caller)
        logger.log(level, "Model: %s", self._config.model)
        for i, msg in enumerate(messages):
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            logger.log(level, "[%d] role=%s", i, role)
            logger.log(level, "    content: %s", content)

    def _log_response(self, response: str, caller: str) -> None:
        """Log LLM response.

        Args:
            response: LLM response text.
            caller: Caller identifier for log context.
        """
        if not self._should_log():
            return

        level = logging.INFO if self._debug_llm_messages else logging.DEBUG
        logger.log(level, "=== LLM Response [%s] ===", caller)
        logger.log(level, "%s", response)

    async def complete(
        self,
        messages: list[dict[str, str]],
        caller: str = "unknown",
        **kwargs: Any,
    ) -> str:
        """Execute chat completion.

        Args:
            messages: OpenAI-format message list.
                [{"role": "system", "content": "..."}, ...]
            caller: Caller identifier for logging (e.g., "response_generator").
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

        self._log_messages(messages, caller)

        try:
            response = await litellm.acompletion(**params)
            content = response.choices[0].message.content
            self._log_response(content, caller)
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

"""LLM metrics entity."""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class LLMMetrics:
    """LLM invocation metrics.

    Represents metrics from an LLM call including token usage,
    performance data, and tool usage statistics.

    Attributes:
        input_tokens: Number of input tokens.
        output_tokens: Number of output tokens.
        total_tokens: Total number of tokens.
        total_cycles: Number of agent cycles.
        total_duration: Total execution duration in seconds.
        latency_ms: Latency in milliseconds (optional).
        tool_usage: Tool usage statistics (optional).
    """

    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    total_cycles: int = 0
    total_duration: float = 0.0
    latency_ms: int | None = None
    tool_usage: dict[str, dict] = field(default_factory=dict)

    @classmethod
    def from_strands_result(cls, result) -> "LLMMetrics":
        """Create LLMMetrics from a Strands AgentResult.

        Args:
            result: Strands AgentResult object.

        Returns:
            LLMMetrics instance.
        """
        try:
            metrics = result.metrics.get_summary()
        except Exception:
            return cls()

        usage = metrics.get("accumulated_usage", {})
        acc_metrics = metrics.get("accumulated_metrics", {})

        return cls(
            input_tokens=usage.get("inputTokens", 0),
            output_tokens=usage.get("outputTokens", 0),
            total_tokens=usage.get("totalTokens", 0),
            total_cycles=metrics.get("total_cycles", 0),
            total_duration=metrics.get("total_duration", 0.0),
            latency_ms=acc_metrics.get("latencyMs"),
            tool_usage=metrics.get("tool_usage", {}),
        )

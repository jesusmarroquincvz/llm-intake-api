"""Per-agent model configuration. Experiments change this, agents only read it."""
from dataclasses import dataclass

THINKING_LEVELS = ("low", "medium", "high")


@dataclass(frozen=True)
class ModelConfig:
    """Which model and thinking level an agent uses."""

    model: str
    thinking: str = "high"


# Current production mapping (Gemini 2.x, thinking high everywhere; to be migrated before the deprecation).
MODELS: dict[str, ModelConfig] = {
    "intent": ModelConfig("gemini-2.5-flash"),
    "urgency": ModelConfig("gemini-2.5-flash"),
    "language": ModelConfig("gemini-2.5-flash"),
    "pii": ModelConfig("gemini-2.1-pro"),
    "sentiment": ModelConfig("gemini-2.5-flash"),
    "routing": ModelConfig("gemini-2.1-pro"),
}

"""Sentiment agent: reads the tone of a support request and flags escalation."""
from dataclasses import dataclass

from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

VALID_LABELS = ("negative", "neutral", "positive")

_SYSTEM_PROMPT = (
    "You read the sentiment of incoming support requests. Read the request and classify its "
    f"sentiment into exactly one of these labels: {', '.join(VALID_LABELS)}. Also decide whether "
    "the request should be escalated to a human: escalate when the customer threatens to cancel, "
    "mentions legal action, or uses abusive language, and do not escalate otherwise. Respond with "
    'a JSON object of the shape {"sentiment": <label>, "escalate": <bool>} and nothing else.'
)


@dataclass
class SentimentResult:
    """The sentiment label found in a support request and whether to escalate it."""

    label: str
    escalate: bool


def analyse_sentiment(text: str, llm: LLM) -> SentimentResult:
    """Analyse a support request's sentiment and return the label and escalation flag."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    response = llm.complete(system=_SYSTEM_PROMPT, user=text, config=MODELS["sentiment"])

    if "sentiment" not in response:
        raise AgentError(f"model response has no 'sentiment' key: {response!r}")

    label = str(response["sentiment"]).strip().lower()
    if label not in VALID_LABELS:
        raise AgentError(f"model returned an unknown sentiment label: {label!r}")

    if "escalate" not in response:
        escalate = False
    else:
        escalate = response["escalate"]
        if not isinstance(escalate, bool):
            raise AgentError(f"model returned a non-bool 'escalate' value: {escalate!r}")

    return SentimentResult(label=label, escalate=escalate)

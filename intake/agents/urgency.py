"""Urgency classification agent: labels a support request for prioritisation."""
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

VALID_LABELS = ("high", "medium", "low")

_SYSTEM_PROMPT = (
    "You classify incoming support requests by urgency. Read the request and classify it into "
    f"exactly one of these labels: {', '.join(VALID_LABELS)}, defined as: "
    "high: the customer cannot use the product, or money is at risk. "
    "medium: the product is degraded but still working. "
    "low: questions, requests, or feedback. "
    'Respond with a JSON object of the shape {"urgency": <label>} and nothing else.'
)


def classify_urgency(text: str, llm: LLM) -> str:
    """Classify a support request's urgency and return the label."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    response = llm.complete(system=_SYSTEM_PROMPT, user=text, config=MODELS["urgency"])

    if "urgency" not in response:
        raise AgentError(f"model response has no 'urgency' key: {response!r}")

    label = str(response["urgency"]).strip().lower()
    if label not in VALID_LABELS:
        raise AgentError(f"model returned an unknown urgency label: {label!r}")

    return label

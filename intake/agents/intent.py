"""Intent classification agent: labels a support request for routing."""
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

VALID_LABELS = ("billing", "account", "bug", "feature", "other")

_SYSTEM_PROMPT = (
    "You classify incoming support requests by intent. Read the request and classify it into "
    f"exactly one of these labels: {', '.join(VALID_LABELS)}. "
    'Respond with a JSON object of the shape {"intent": <label>} and nothing else.'
)


def classify_intent(text: str, llm: LLM) -> str:
    """Classify a support request's intent and return the label."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    response = llm.complete(system=_SYSTEM_PROMPT, user=text, config=MODELS["intent"])

    if "intent" not in response:
        raise AgentError(f"model response has no 'intent' key: {response!r}")

    label = str(response["intent"]).strip().lower()
    if label not in VALID_LABELS:
        raise AgentError(f"model returned an unknown intent label: {label!r}")

    return label

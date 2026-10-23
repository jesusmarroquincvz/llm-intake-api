"""PII detection agent: finds personally identifiable information and redacts it."""
from dataclasses import dataclass

from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

VALID_TYPES = ("email", "phone", "card", "address", "name")

_SYSTEM_PROMPT = (
    "You detect personally identifiable information (PII) in incoming support requests. Read "
    f"the request and find any of these PII types: {', '.join(VALID_TYPES)}. Respond with a "
    'JSON object of the shape {"types": [...], "redacted": "..."} and nothing else, where '
    '"types" is a JSON array containing whichever of the valid type names above appear in the '
    'text (an empty array if none appear), and "redacted" is the input text with each PII value '
    "you found replaced by its type name in angle brackets, e.g. an email address replaced by "
    "<email>, a phone number by <phone>, and so on."
)


@dataclass
class PiiResult:
    """The PII types found in a support request and its redacted text."""

    types: list[str]
    redacted: str


def detect_pii(text: str, llm: LLM) -> PiiResult:
    """Detect PII in a support request and return the types found and a redacted version."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    response = llm.complete(system=_SYSTEM_PROMPT, user=text, config=MODELS["pii"])

    if "types" not in response or "redacted" not in response:
        raise AgentError(f"model response has no 'types' or 'redacted' key: {response!r}")

    types = set()
    for entry in response["types"]:
        normalised = str(entry).strip().lower()
        if normalised not in VALID_TYPES:
            raise AgentError(f"model returned an unknown PII type: {normalised!r}")
        types.add(normalised)

    return PiiResult(types=sorted(types), redacted=str(response["redacted"]))

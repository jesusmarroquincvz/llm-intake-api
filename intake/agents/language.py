"""Language detection agent: labels a support request with its ISO 639-1 language code."""
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

_SYSTEM_PROMPT = (
    "You detect the language of incoming support requests. Read the request and identify its "
    "language. Respond with a JSON object of the shape {\"language\": <code>} and nothing else, "
    "where <code> is the ISO 639-1 two-letter lowercase code for the detected language, e.g. "
    "en, es, pt, fr, de, it. Any two-letter lowercase code is an allowed answer, not just these "
    "examples."
)


def detect_language(text: str, llm: LLM) -> str:
    """Detect a support request's language and return its ISO 639-1 code."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    response = llm.complete(system=_SYSTEM_PROMPT, user=text, config=MODELS["language"])

    if "language" not in response:
        raise AgentError(f"model response has no 'language' key: {response!r}")

    code = str(response["language"]).strip().lower()
    if len(code) != 2 or not code.isalpha():
        raise AgentError(f"model returned an invalid language code: {code!r}")

    return code

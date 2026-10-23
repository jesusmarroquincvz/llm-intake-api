"""Orchestrator: runs the five independent classification agents concurrently and routes the result."""
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from intake.agents.intent import classify_intent
from intake.agents.language import detect_language
from intake.agents.pii import PiiResult, detect_pii
from intake.agents.routing import RoutingResult, route
from intake.agents.sentiment import SentimentResult, analyse_sentiment
from intake.agents.urgency import classify_urgency
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

_AGENTS = {
    "intent": classify_intent,
    "urgency": classify_urgency,
    "language": detect_language,
    "pii": detect_pii,
    "sentiment": analyse_sentiment,
}


@dataclass
class Decision:
    """The assembled outcome of classifying and routing a support request."""

    intent: str
    urgency: str
    language: str
    pii: PiiResult
    sentiment: SentimentResult
    routing: RoutingResult

    def to_dict(self) -> dict:
        """Return a plain, JSON-serialisable dict of this decision."""
        return {
            "intent": self.intent,
            "urgency": self.urgency,
            "language": self.language,
            "pii": {"types": self.pii.types, "redacted": self.pii.redacted},
            "sentiment": {"label": self.sentiment.label, "escalate": self.sentiment.escalate},
            "routing": {"team": self.routing.team, "summary": self.routing.summary, "actions": self.routing.actions},
        }


def classify(text: str, llm: LLM) -> Decision:
    """Classify a support request with the five independent agents, then route it, as a Decision."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {name: executor.submit(agent, text, llm) for name, agent in _AGENTS.items()}
        results = {}
        for name, future in futures.items():
            try:
                results[name] = future.result()
            except AgentError as e:
                raise AgentError(f"{name}: {e}") from e

    intent: str = results["intent"]
    urgency: str = results["urgency"]
    language: str = results["language"]
    pii: PiiResult = results["pii"]
    sentiment: SentimentResult = results["sentiment"]

    signals = {
        "intent": intent,
        "urgency": urgency,
        "language": language,
        "pii_types": pii.types,
        "sentiment": sentiment.label,
        "escalate": sentiment.escalate,
    }

    try:
        routing = route(text, signals, llm)
    except AgentError as e:
        raise AgentError(f"routing: {e}") from e

    return Decision(intent=intent, urgency=urgency, language=language, pii=pii, sentiment=sentiment, routing=routing)

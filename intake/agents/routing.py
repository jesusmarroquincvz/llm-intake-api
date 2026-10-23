"""Routing agent: decides which team should handle a support request."""
import json
from dataclasses import dataclass

from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import LLM

VALID_TEAMS = ("billing-ops", "support-l1", "support-l2", "engineering", "trust-safety")

_SYSTEM_PROMPT = (
    "You route incoming support requests, given the request text and the other agents' signals "
    f"about it, to exactly one of these teams: {', '.join(VALID_TEAMS)}. Follow this policy: if "
    "the 'escalate' signal is true, or the request raises trust or safety concerns, route to "
    "trust-safety; otherwise, if the intent is a bug and urgency is high, route to engineering; "
    "otherwise, if the intent is a bug (any other urgency), route to support-l2; otherwise, if "
    "the intent is billing, route to billing-ops; otherwise, route to support-l1. Respond with a "
    'JSON object of the shape {"team": <team>, "summary": <summary>, "actions": [<action>, ...]} '
    'and nothing else, where "team" is one of the five teams above, "summary" is one sentence '
    'describing the request (at most 160 characters), and "actions" is a JSON array of zero to '
    "three short imperative strings describing what should be done next (an empty array if none "
    "are needed)."
)


@dataclass
class RoutingResult:
    """The team a support request should go to, with a summary and next actions."""

    team: str
    summary: str
    actions: list[str]


def route(text: str, signals: dict, llm: LLM) -> RoutingResult:
    """Route a support request to a team using its text and the other agents' signals."""
    if not text.strip():
        raise ValidationError("text must not be empty or whitespace-only")

    user = json.dumps({"text": text, "signals": signals})
    response = llm.complete(system=_SYSTEM_PROMPT, user=user, config=MODELS["routing"])

    if "team" not in response:
        raise AgentError(f"model response has no 'team' key: {response!r}")

    team = str(response["team"]).strip().lower()
    if team not in VALID_TEAMS:
        raise AgentError(f"model returned an unknown team: {team!r}")

    if "summary" not in response:
        raise AgentError(f"model response has no 'summary' key: {response!r}")

    summary = str(response["summary"])
    if len(summary) > 160:
        raise AgentError(f"model returned a summary longer than 160 characters: {summary!r}")

    if "actions" not in response:
        actions: list[str] = []
    else:
        raw_actions = response["actions"]
        if not isinstance(raw_actions, list):
            raise AgentError(f"model returned a non-list 'actions' value: {raw_actions!r}")
        if len(raw_actions) > 3:
            raise AgentError(f"model returned more than 3 actions: {raw_actions!r}")
        actions = [str(a) for a in raw_actions]

    return RoutingResult(team=team, summary=summary, actions=actions)

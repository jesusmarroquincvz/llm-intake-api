import json

import pytest

from intake.agents.routing import RoutingResult, VALID_TEAMS, route
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM


def _signals(**overrides):
    base = {
        "intent": "bug",
        "urgency": "high",
        "language": "en",
        "pii_types": [],
        "sentiment": "negative",
        "escalate": False,
    }
    base.update(overrides)
    return base


def test_route_returns_result():
    llm = FakeLLM([{"team": "engineering", "summary": "App crashes on login.", "actions": ["Reproduce the crash"]}])
    result = route("the app crashes on login", _signals(), llm)
    assert result == RoutingResult(team="engineering", summary="App crashes on login.", actions=["Reproduce the crash"])


def test_route_calls_llm_exactly_once_with_expected_args():
    signals = _signals()
    llm = FakeLLM([{"team": "support-l1", "summary": "General question.", "actions": []}])
    route("just checking my balance", signals, llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["config"] is MODELS["routing"]
    assert isinstance(call["system"], str) and call["system"]
    assert call["user"] == json.dumps({"text": "just checking my balance", "signals": signals})


def test_route_passes_signals_through_unchanged():
    signals = _signals(intent="billing", urgency="low", pii_types=["email"])
    llm = FakeLLM([{"team": "billing-ops", "summary": "Billing question.", "actions": []}])
    route("some request", signals, llm)
    sent = json.loads(llm.calls[0]["user"])
    assert sent["signals"] == signals


def test_route_system_prompt_names_all_valid_teams():
    llm = FakeLLM([{"team": "support-l1", "summary": "General question.", "actions": []}])
    route("some request", _signals(), llm)
    system = llm.calls[0]["system"]
    for team in VALID_TEAMS:
        assert team in system


def test_route_normalises_team_whitespace_and_case():
    llm = FakeLLM([{"team": "  Engineering  ", "summary": "App crashes on login.", "actions": []}])
    result = route("the app crashes on login", _signals(), llm)
    assert result.team == "engineering"


@pytest.mark.parametrize("team", VALID_TEAMS)
def test_route_accepts_all_valid_teams(team):
    llm = FakeLLM([{"team": team, "summary": "Some summary.", "actions": []}])
    result = route("some request", _signals(), llm)
    assert result.team == team


def test_route_raises_agent_error_on_missing_team_key():
    llm = FakeLLM([{"summary": "Some summary.", "actions": []}])
    with pytest.raises(AgentError):
        route("some request", _signals(), llm)


def test_route_raises_agent_error_on_invalid_team():
    llm = FakeLLM([{"team": "sales", "summary": "Some summary.", "actions": []}])
    with pytest.raises(AgentError):
        route("some request", _signals(), llm)


def test_route_raises_agent_error_on_missing_summary_key():
    llm = FakeLLM([{"team": "support-l1", "actions": []}])
    with pytest.raises(AgentError):
        route("some request", _signals(), llm)


def test_route_raises_agent_error_on_summary_too_long():
    llm = FakeLLM([{"team": "support-l1", "summary": "x" * 161, "actions": []}])
    with pytest.raises(AgentError):
        route("some request", _signals(), llm)


def test_route_accepts_summary_at_exactly_160_chars():
    llm = FakeLLM([{"team": "support-l1", "summary": "x" * 160, "actions": []}])
    result = route("some request", _signals(), llm)
    assert result.summary == "x" * 160


def test_route_defaults_actions_to_empty_list_when_missing():
    llm = FakeLLM([{"team": "support-l1", "summary": "Some summary."}])
    result = route("some request", _signals(), llm)
    assert result.actions == []


def test_route_raises_agent_error_on_non_list_actions():
    llm = FakeLLM([{"team": "support-l1", "summary": "Some summary.", "actions": "do the thing"}])
    with pytest.raises(AgentError):
        route("some request", _signals(), llm)


def test_route_raises_agent_error_on_more_than_three_actions():
    llm = FakeLLM([{"team": "support-l1", "summary": "Some summary.", "actions": ["a", "b", "c", "d"]}])
    with pytest.raises(AgentError):
        route("some request", _signals(), llm)


def test_route_accepts_up_to_three_actions_in_order():
    llm = FakeLLM([{"team": "support-l1", "summary": "Some summary.", "actions": ["a", "b", "c"]}])
    result = route("some request", _signals(), llm)
    assert result.actions == ["a", "b", "c"]


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_route_raises_validation_error_on_empty_text(text):
    llm = FakeLLM([{"team": "support-l1", "summary": "Some summary.", "actions": []}])
    with pytest.raises(ValidationError):
        route(text, _signals(), llm)
    assert llm.calls == []

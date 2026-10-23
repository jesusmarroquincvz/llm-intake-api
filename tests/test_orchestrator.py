import json
import threading

import pytest

from intake.agents.pii import PiiResult
from intake.agents.routing import RoutingResult
from intake.agents.sentiment import SentimentResult
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM
from intake.orchestrator import Decision, classify

_DEFAULT_ANSWERS = {
    "intent": {"intent": "bug"},
    "urgency": {"urgency": "high"},
    "language": {"language": "en"},
    "pii": {"types": [], "redacted": "no pii here"},
    "sentiment": {"sentiment": "neutral", "escalate": False},
    "routing": {"team": "support-l1", "summary": "General question.", "actions": []},
}


def _make_rule(overrides=None):
    answers = {**_DEFAULT_ANSWERS, **(overrides or {})}

    def rule(system, user, config):
        for name, answer in answers.items():
            if config is MODELS[name]:
                return answer
        raise AssertionError(f"unexpected config: {config}")

    return rule


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_classify_raises_validation_error_on_empty_text(text):
    llm = FakeLLM()
    with pytest.raises(ValidationError):
        classify(text, llm)
    assert llm.calls == []


def test_classify_returns_decision_with_expected_fields():
    llm = FakeLLM(rule=_make_rule({
        "intent": {"intent": "bug"},
        "urgency": {"urgency": "high"},
        "language": {"language": "en"},
        "pii": {"types": ["email"], "redacted": "contact at <email>"},
        "sentiment": {"sentiment": "negative", "escalate": True},
        "routing": {"team": "engineering", "summary": "Bug report.", "actions": ["Investigate"]},
    }))
    decision = classify("my account is broken, email me at a@b.com", llm)
    assert decision == Decision(
        intent="bug",
        urgency="high",
        language="en",
        pii=PiiResult(types=["email"], redacted="contact at <email>"),
        sentiment=SentimentResult(label="negative", escalate=True),
        routing=RoutingResult(team="engineering", summary="Bug report.", actions=["Investigate"]),
    )


def test_classify_calls_each_agent_with_text_and_llm():
    calls = []

    def rule(system, user, config):
        calls.append((config, user))
        for name, answer in _DEFAULT_ANSWERS.items():
            if config is MODELS[name]:
                return answer
        raise AssertionError(f"unexpected config: {config}")

    llm = FakeLLM(rule=rule)
    text = "my account is broken"
    classify(text, llm)
    assert len(llm.calls) == 6
    non_routing_users = [user for config, user in calls if config is not MODELS["routing"]]
    assert len(non_routing_users) == 5
    assert all(user == text for user in non_routing_users)


def test_classify_builds_expected_signals_for_routing():
    captured = {}

    def rule(system, user, config):
        if config is MODELS["routing"]:
            captured["user"] = user
            return _DEFAULT_ANSWERS["routing"]
        for name, answer in _DEFAULT_ANSWERS.items():
            if config is MODELS[name]:
                return answer
        raise AssertionError(f"unexpected config: {config}")

    llm = FakeLLM(rule=rule)
    classify("some request", llm)
    sent = json.loads(captured["user"])
    assert sent["signals"] == {
        "intent": "bug",
        "urgency": "high",
        "language": "en",
        "pii_types": [],
        "sentiment": "neutral",
        "escalate": False,
    }


def test_classify_submits_all_five_independent_agents_concurrently():
    barrier = threading.Barrier(5, timeout=2)

    def rule(system, user, config):
        if config is MODELS["routing"]:
            return _DEFAULT_ANSWERS["routing"]
        barrier.wait()
        for name, answer in _DEFAULT_ANSWERS.items():
            if config is MODELS[name]:
                return answer
        raise AssertionError(f"unexpected config: {config}")

    llm = FakeLLM(rule=rule)
    classify("some request", llm)


@pytest.mark.parametrize("name", ["intent", "urgency", "language", "pii", "sentiment"])
def test_classify_raises_agent_error_prefixed_with_agent_name_when_an_agent_fails(name):
    llm = FakeLLM(rule=_make_rule({name: {}}))
    with pytest.raises(AgentError) as excinfo:
        classify("some request", llm)
    assert str(excinfo.value).startswith(f"{name}: ")


def test_classify_does_not_call_route_when_an_agent_fails():
    route_called = []

    def rule(system, user, config):
        if config is MODELS["routing"]:
            route_called.append(True)
            return _DEFAULT_ANSWERS["routing"]
        if config is MODELS["intent"]:
            return {}
        for name, answer in _DEFAULT_ANSWERS.items():
            if config is MODELS[name]:
                return answer
        raise AssertionError(f"unexpected config: {config}")

    llm = FakeLLM(rule=rule)
    with pytest.raises(AgentError):
        classify("some request", llm)
    assert route_called == []


def test_classify_raises_agent_error_prefixed_with_routing_when_route_fails():
    llm = FakeLLM(rule=_make_rule({"routing": {}}))
    with pytest.raises(AgentError) as excinfo:
        classify("some request", llm)
    assert str(excinfo.value).startswith("routing: ")


def test_decision_to_dict_returns_plain_json_serialisable_shape():
    decision = Decision(
        intent="bug",
        urgency="high",
        language="en",
        pii=PiiResult(types=["email"], redacted="<email>"),
        sentiment=SentimentResult(label="negative", escalate=True),
        routing=RoutingResult(team="engineering", summary="App crashes on login.", actions=["Investigate"]),
    )
    expected = {
        "intent": "bug",
        "urgency": "high",
        "language": "en",
        "pii": {"types": ["email"], "redacted": "<email>"},
        "sentiment": {"label": "negative", "escalate": True},
        "routing": {"team": "engineering", "summary": "App crashes on login.", "actions": ["Investigate"]},
    }
    assert decision.to_dict() == expected
    json.dumps(decision.to_dict())

import pytest

from intake.agents.intent import classify_intent
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM


def test_classify_intent_returns_label():
    llm = FakeLLM([{"intent": "billing"}])
    assert classify_intent("I was charged twice", llm) == "billing"


def test_classify_intent_calls_llm_exactly_once_with_expected_args():
    llm = FakeLLM([{"intent": "bug"}])
    classify_intent("the app crashes on login", llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["user"] == "the app crashes on login"
    assert call["config"] is MODELS["intent"]
    assert isinstance(call["system"], str) and call["system"]


def test_classify_intent_normalises_label_whitespace_and_case():
    llm = FakeLLM([{"intent": "  Billing  "}])
    assert classify_intent("I was charged twice", llm) == "billing"


@pytest.mark.parametrize("label", ["billing", "account", "bug", "feature", "other"])
def test_classify_intent_accepts_all_valid_labels(label):
    llm = FakeLLM([{"intent": label}])
    assert classify_intent("some request", llm) == label


def test_classify_intent_raises_agent_error_on_missing_key():
    llm = FakeLLM([{"wrong_key": "billing"}])
    with pytest.raises(AgentError):
        classify_intent("some request", llm)


def test_classify_intent_raises_agent_error_on_invalid_label():
    llm = FakeLLM([{"intent": "unknown"}])
    with pytest.raises(AgentError):
        classify_intent("some request", llm)


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_classify_intent_raises_validation_error_on_empty_text(text):
    llm = FakeLLM([{"intent": "billing"}])
    with pytest.raises(ValidationError):
        classify_intent(text, llm)
    assert llm.calls == []

import pytest

from intake.agents.urgency import classify_urgency
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM


def test_classify_urgency_returns_label():
    llm = FakeLLM([{"urgency": "high"}])
    assert classify_urgency("I can't log in and my money is gone", llm) == "high"


def test_classify_urgency_calls_llm_exactly_once_with_expected_args():
    llm = FakeLLM([{"urgency": "medium"}])
    classify_urgency("the app is slow", llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["user"] == "the app is slow"
    assert call["config"] is MODELS["urgency"]
    assert isinstance(call["system"], str) and call["system"]


def test_classify_urgency_normalises_label_whitespace_and_case():
    llm = FakeLLM([{"urgency": "  High  "}])
    assert classify_urgency("I can't use the product", llm) == "high"


@pytest.mark.parametrize("label", ["high", "medium", "low"])
def test_classify_urgency_accepts_all_valid_labels(label):
    llm = FakeLLM([{"urgency": label}])
    assert classify_urgency("some request", llm) == label


def test_classify_urgency_raises_agent_error_on_missing_key():
    llm = FakeLLM([{"wrong_key": "high"}])
    with pytest.raises(AgentError):
        classify_urgency("some request", llm)


def test_classify_urgency_raises_agent_error_on_invalid_label():
    llm = FakeLLM([{"urgency": "unknown"}])
    with pytest.raises(AgentError):
        classify_urgency("some request", llm)


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_classify_urgency_raises_validation_error_on_empty_text(text):
    llm = FakeLLM([{"urgency": "high"}])
    with pytest.raises(ValidationError):
        classify_urgency(text, llm)
    assert llm.calls == []

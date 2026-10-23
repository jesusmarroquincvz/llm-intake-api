import pytest

from intake.agents.sentiment import SentimentResult, analyse_sentiment
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM


def test_analyse_sentiment_returns_result():
    llm = FakeLLM([{"sentiment": "negative", "escalate": True}])
    result = analyse_sentiment("I will cancel my account", llm)
    assert result == SentimentResult(label="negative", escalate=True)


def test_analyse_sentiment_calls_llm_exactly_once_with_expected_args():
    llm = FakeLLM([{"sentiment": "neutral", "escalate": False}])
    analyse_sentiment("just checking my balance", llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["user"] == "just checking my balance"
    assert call["config"] is MODELS["sentiment"]
    assert isinstance(call["system"], str) and call["system"]


def test_analyse_sentiment_system_prompt_names_labels_and_triggers():
    llm = FakeLLM([{"sentiment": "neutral", "escalate": False}])
    analyse_sentiment("just checking my balance", llm)
    system = llm.calls[0]["system"]
    assert "negative" in system and "neutral" in system and "positive" in system
    assert "cancel" in system.lower()
    assert "legal" in system.lower()
    assert "abusive" in system.lower()


def test_analyse_sentiment_normalises_label_whitespace_and_case():
    llm = FakeLLM([{"sentiment": "  Negative  ", "escalate": False}])
    result = analyse_sentiment("some request", llm)
    assert result.label == "negative"


@pytest.mark.parametrize("label", ["negative", "neutral", "positive"])
def test_analyse_sentiment_accepts_all_valid_labels(label):
    llm = FakeLLM([{"sentiment": label, "escalate": False}])
    result = analyse_sentiment("some request", llm)
    assert result.label == label


def test_analyse_sentiment_raises_agent_error_on_missing_sentiment_key():
    llm = FakeLLM([{"escalate": False}])
    with pytest.raises(AgentError):
        analyse_sentiment("some request", llm)


def test_analyse_sentiment_raises_agent_error_on_invalid_label():
    llm = FakeLLM([{"sentiment": "furious", "escalate": False}])
    with pytest.raises(AgentError):
        analyse_sentiment("some request", llm)


def test_analyse_sentiment_defaults_escalate_to_false_when_missing():
    llm = FakeLLM([{"sentiment": "positive"}])
    result = analyse_sentiment("some request", llm)
    assert result.escalate is False


@pytest.mark.parametrize("bad_escalate", [1, 0, "true", "false", None, "True"])
def test_analyse_sentiment_raises_agent_error_on_non_bool_escalate(bad_escalate):
    llm = FakeLLM([{"sentiment": "negative", "escalate": bad_escalate}])
    with pytest.raises(AgentError):
        analyse_sentiment("some request", llm)


@pytest.mark.parametrize("escalate", [True, False])
def test_analyse_sentiment_accepts_bool_escalate(escalate):
    llm = FakeLLM([{"sentiment": "negative", "escalate": escalate}])
    result = analyse_sentiment("some request", llm)
    assert result.escalate is escalate


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_analyse_sentiment_raises_validation_error_on_empty_text(text):
    llm = FakeLLM([{"sentiment": "neutral", "escalate": False}])
    with pytest.raises(ValidationError):
        analyse_sentiment(text, llm)
    assert llm.calls == []

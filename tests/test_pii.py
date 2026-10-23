import pytest

from intake.agents.pii import PiiResult, detect_pii
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM


def test_detect_pii_returns_result():
    llm = FakeLLM([{"types": ["email"], "redacted": "contact me at <email>"}])
    result = detect_pii("contact me at a@b.com", llm)
    assert result == PiiResult(types=["email"], redacted="contact me at <email>")


def test_detect_pii_calls_llm_exactly_once_with_expected_args():
    llm = FakeLLM([{"types": [], "redacted": "no pii here"}])
    detect_pii("no pii here", llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["user"] == "no pii here"
    assert call["config"] is MODELS["pii"]
    assert isinstance(call["system"], str) and call["system"]


def test_detect_pii_normalises_types_whitespace_and_case():
    llm = FakeLLM([{"types": ["  Email  ", "PHONE"], "redacted": "<email> <phone>"}])
    result = detect_pii("a@b.com 555-1234", llm)
    assert result.types == ["email", "phone"]


def test_detect_pii_dedupes_and_sorts_types():
    llm = FakeLLM([{"types": ["phone", "email", "phone", "email"], "redacted": "<email> <phone>"}])
    result = detect_pii("a@b.com 555-1234", llm)
    assert result.types == ["email", "phone"]


def test_detect_pii_accepts_empty_types_as_valid():
    llm = FakeLLM([{"types": [], "redacted": "nothing sensitive here"}])
    result = detect_pii("nothing sensitive here", llm)
    assert result == PiiResult(types=[], redacted="nothing sensitive here")


@pytest.mark.parametrize("pii_type", ["email", "phone", "card", "address", "name"])
def test_detect_pii_accepts_all_valid_types(pii_type):
    llm = FakeLLM([{"types": [pii_type], "redacted": f"<{pii_type}>"}])
    result = detect_pii("some request", llm)
    assert result.types == [pii_type]


def test_detect_pii_raises_agent_error_on_missing_types_key():
    llm = FakeLLM([{"redacted": "some text"}])
    with pytest.raises(AgentError):
        detect_pii("some request", llm)


def test_detect_pii_raises_agent_error_on_missing_redacted_key():
    llm = FakeLLM([{"types": ["email"]}])
    with pytest.raises(AgentError):
        detect_pii("some request", llm)


def test_detect_pii_raises_agent_error_on_invalid_type():
    llm = FakeLLM([{"types": ["ssn"], "redacted": "<ssn>"}])
    with pytest.raises(AgentError):
        detect_pii("some request", llm)


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_detect_pii_raises_validation_error_on_empty_text(text):
    llm = FakeLLM([{"types": [], "redacted": text}])
    with pytest.raises(ValidationError):
        detect_pii(text, llm)
    assert llm.calls == []

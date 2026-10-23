import pytest

from intake.agents.language import detect_language
from intake.config import MODELS
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM


def test_detect_language_returns_code():
    llm = FakeLLM([{"language": "en"}])
    assert detect_language("Hello, I need help", llm) == "en"


def test_detect_language_calls_llm_exactly_once_with_expected_args():
    llm = FakeLLM([{"language": "fr"}])
    detect_language("Bonjour, j'ai besoin d'aide", llm)
    assert len(llm.calls) == 1
    call = llm.calls[0]
    assert call["user"] == "Bonjour, j'ai besoin d'aide"
    assert call["config"] is MODELS["language"]
    assert isinstance(call["system"], str) and call["system"]


def test_detect_language_normalises_code_whitespace_and_case():
    llm = FakeLLM([{"language": "  En  "}])
    assert detect_language("Hello there", llm) == "en"


@pytest.mark.parametrize("code", ["en", "es", "pt", "fr", "de", "it"])
def test_detect_language_accepts_example_codes(code):
    llm = FakeLLM([{"language": code}])
    assert detect_language("some request", llm) == code


def test_detect_language_accepts_any_two_letter_code_not_in_examples():
    llm = FakeLLM([{"language": "zz"}])
    assert detect_language("some request", llm) == "zz"


def test_detect_language_raises_agent_error_on_missing_key():
    llm = FakeLLM([{"wrong_key": "en"}])
    with pytest.raises(AgentError):
        detect_language("some request", llm)


@pytest.mark.parametrize("code", ["", "e", "eng", "e1"])
def test_detect_language_raises_agent_error_on_invalid_code(code):
    llm = FakeLLM([{"language": code}])
    with pytest.raises(AgentError):
        detect_language("some request", llm)


@pytest.mark.parametrize("text", ["", "   ", "\t\n"])
def test_detect_language_raises_validation_error_on_empty_text(text):
    llm = FakeLLM([{"language": "en"}])
    with pytest.raises(ValidationError):
        detect_language(text, llm)
    assert llm.calls == []

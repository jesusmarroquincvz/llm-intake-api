import contextlib
import os

os.environ["INTAKE_LLM"] = "fake"

import pytest
from fastapi.testclient import TestClient

import intake.api
from intake.config import MODELS
from intake.llm import FakeLLM

client = TestClient(intake.api.app)

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


@pytest.fixture(autouse=True)
def _default_llm():
    intake.api.set_llm(FakeLLM(rule=_make_rule()))


class _FakeSpan:
    def __init__(self, name):
        self.name = name
        self.attributes = {}

    def set_attribute(self, key, value):
        self.attributes[key] = value


class _FakeTracer:
    def __init__(self):
        self.spans = []

    def start_as_current_span(self, name):
        span = _FakeSpan(name)
        self.spans.append(span)
        return contextlib.nullcontext(span)


def test_get_llm_returns_fake_llm_when_intake_llm_env_is_fake(monkeypatch):
    monkeypatch.setenv("INTAKE_LLM", "fake")
    assert isinstance(intake.api.get_llm(), FakeLLM)


def test_get_llm_returns_gemini_llm_otherwise(monkeypatch):
    monkeypatch.delenv("INTAKE_LLM", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", "some-project")
    monkeypatch.setattr("google.genai.Client", lambda **kwargs: object())

    from intake.llm import GeminiLLM

    assert isinstance(intake.api.get_llm(), GeminiLLM)


def test_classify_returns_200_with_decision_json():
    response = client.post("/classify", json={"text": "my app crashes"})
    assert response.status_code == 200
    assert response.json() == {
        "intent": "bug",
        "urgency": "high",
        "language": "en",
        "pii": {"types": [], "redacted": "no pii here"},
        "sentiment": {"label": "neutral", "escalate": False},
        "routing": {"team": "support-l1", "summary": "General question.", "actions": []},
    }


def test_classify_uses_the_llm_set_by_set_llm():
    llm = FakeLLM(rule=_make_rule({"intent": {"intent": "billing"}}))
    intake.api.set_llm(llm)

    response = client.post("/classify", json={"text": "hello"})

    assert response.status_code == 200
    assert response.json()["intent"] == "billing"
    assert len(llm.calls) == 6


def test_classify_returns_422_on_validation_error():
    response = client.post("/classify", json={"text": "   "})
    assert response.status_code == 422
    assert response.json()["detail"]
    assert isinstance(response.json()["detail"], str)


def test_classify_returns_502_on_agent_error():
    intake.api.set_llm(FakeLLM(rule=_make_rule({"intent": {}})))

    response = client.post("/classify", json={"text": "hello"})

    assert response.status_code == 502
    assert response.json()["detail"].startswith("intent: ")


def test_classify_missing_text_field_returns_422_and_does_not_call_classify():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify", json={})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_non_string_text_returns_422_and_does_not_call_classify():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify", json={"text": 123})

    assert response.status_code == 422
    assert llm.calls == []


def test_classify_invalid_json_body_returns_422():
    response = client.post(
        "/classify", content=b"not json", headers={"Content-Type": "application/json"}
    )
    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"]


def test_classify_wraps_classify_call_in_a_span_named_classify_on_success(monkeypatch):
    tracer = _FakeTracer()
    monkeypatch.setattr(intake.api, "_tracer", tracer)

    response = client.post("/classify", json={"text": "my app crashes"})

    assert response.status_code == 200
    assert len(tracer.spans) == 1
    assert tracer.spans[0].name == "classify"
    assert tracer.spans[0].attributes["input.value"] == "my app crashes"


def test_classify_wraps_classify_call_in_a_span_named_classify_on_failure(monkeypatch):
    tracer = _FakeTracer()
    monkeypatch.setattr(intake.api, "_tracer", tracer)
    intake.api.set_llm(FakeLLM(rule=_make_rule({"intent": {}})))

    response = client.post("/classify", json={"text": "hello"})

    assert response.status_code == 502
    assert len(tracer.spans) == 1
    assert tracer.spans[0].name == "classify"
    assert tracer.spans[0].attributes["input.value"] == "hello"

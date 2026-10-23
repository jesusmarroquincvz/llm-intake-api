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


def test_classify_batch_returns_200_with_one_decision_per_text_in_order():
    response = client.post(
        "/classify/batch", json={"texts": ["my app crashes", "another ticket"]}
    )

    assert response.status_code == 200
    body = response.json()
    expected = {
        "intent": "bug",
        "urgency": "high",
        "language": "en",
        "pii": {"types": [], "redacted": "no pii here"},
        "sentiment": {"label": "neutral", "escalate": False},
        "routing": {"team": "support-l1", "summary": "General question.", "actions": []},
    }
    assert body == {"decisions": [expected, expected]}


def test_classify_batch_marks_empty_and_whitespace_texts_as_errors_without_calling_classify():
    llm = FakeLLM(rule=_make_rule())
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json={"texts": ["", "   ", "hello"]})

    assert response.status_code == 200
    body = response.json()
    assert body["decisions"][0] == {"error": "text must not be empty"}
    assert body["decisions"][1] == {"error": "text must not be empty"}
    assert "error" not in body["decisions"][2]
    assert len(llm.calls) == 6  # only "hello" reaches classify, which makes 6 LLM calls


def test_classify_batch_continues_after_one_element_fails_with_agent_error():
    def rule(system, user, config):
        if config is MODELS["intent"] and user == "bad":
            return {}
        return _make_rule()(system, user, config)

    intake.api.set_llm(FakeLLM(rule=rule))

    response = client.post("/classify/batch", json={"texts": ["good", "bad", "good"]})

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body["decisions"][0]
    assert body["decisions"][1]["error"].startswith("intent: ")
    assert "error" not in body["decisions"][2]


def test_classify_batch_continues_after_one_element_fails_with_validation_error():
    response = client.post("/classify/batch", json={"texts": ["good", "   ", "good"]})

    assert response.status_code == 200
    body = response.json()
    assert "error" not in body["decisions"][0]
    assert body["decisions"][1] == {"error": "text must not be empty"}
    assert "error" not in body["decisions"][2]


def test_classify_batch_returns_422_when_texts_field_is_missing():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json={})

    assert response.status_code == 422
    assert isinstance(response.json()["detail"], str)
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_batch_returns_422_when_body_is_not_an_object():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json=["my app crashes"])

    assert response.status_code == 422
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_batch_returns_422_when_texts_is_not_a_list():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json={"texts": "my app crashes"})

    assert response.status_code == 422
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_batch_returns_422_when_texts_contains_a_non_string_element():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json={"texts": ["ok", 123]})

    assert response.status_code == 422
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_batch_returns_422_when_texts_is_empty():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json={"texts": []})

    assert response.status_code == 422
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_batch_returns_422_when_texts_has_more_than_20_elements():
    llm = FakeLLM()
    intake.api.set_llm(llm)

    response = client.post("/classify/batch", json={"texts": ["hi"] * 21})

    assert response.status_code == 422
    assert response.json()["detail"]
    assert llm.calls == []


def test_classify_batch_accepts_exactly_20_elements():
    response = client.post("/classify/batch", json={"texts": ["hi"] * 20})

    assert response.status_code == 200
    assert len(response.json()["decisions"]) == 20


def test_classify_batch_wraps_processing_in_a_single_span_with_batch_size(monkeypatch):
    tracer = _FakeTracer()
    monkeypatch.setattr(intake.api, "_tracer", tracer)

    response = client.post("/classify/batch", json={"texts": ["a", "", "b"]})

    assert response.status_code == 200
    assert len(tracer.spans) == 1
    assert tracer.spans[0].name == "classify_batch"
    assert tracer.spans[0].attributes["batch.size"] == 3


def test_classify_batch_does_not_open_span_on_validation_failure():
    tracer = _FakeTracer()
    original = intake.api._tracer
    intake.api._tracer = tracer
    try:
        response = client.post("/classify/batch", json={"texts": []})
    finally:
        intake.api._tracer = original

    assert response.status_code == 422
    assert tracer.spans == []

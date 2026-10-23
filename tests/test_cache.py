import pytest

import intake.cache
from intake.cache import DecisionCache
from intake.errors import AgentError, ValidationError
from intake.llm import FakeLLM
from intake.orchestrator import Decision


class _StubLLM(FakeLLM):
    """FakeLLM subclass used only to assert llm.complete is never reached on a cache hit."""


def _make_decision(label="bug"):
    return Decision(
        intent=label,
        urgency="high",
        language="en",
        pii=None,
        sentiment=None,
        routing=None,
    )


def test_constructor_stores_ttl_s():
    cache = DecisionCache(ttl_s=42.0)
    assert cache.ttl_s == 42.0


def test_constructor_default_ttl_is_60():
    cache = DecisionCache()
    assert cache.ttl_s == 60.0


def test_get_or_classify_calls_orchestrator_classify_on_miss(monkeypatch):
    decision = _make_decision()
    captured = {}

    def fake_classify(text, llm):
        captured["text"] = text
        captured["llm"] = llm
        return decision

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache()
    llm = _StubLLM()
    result = cache.get_or_classify("hello world", llm, now=0.0)
    assert result is decision
    assert captured["text"] == "hello world"
    assert captured["llm"] is llm


def test_get_or_classify_passes_text_unnormalised_to_classify(monkeypatch):
    captured = {}

    def fake_classify(text, llm):
        captured["text"] = text
        return _make_decision()

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache()
    cache.get_or_classify("  Hello   World  \n", FakeLLM(), now=0.0)
    assert captured["text"] == "  Hello   World  \n"


@pytest.mark.parametrize(
    "first,second",
    [
        ("Hello   World", "  hello world  "),
        ("Hello   World", "hello\nworld"),
        ("hello world", "HELLO\t WORLD"),
    ],
)
def test_normalised_keys_are_treated_as_the_same_text(monkeypatch, first, second):
    calls = []

    def fake_classify(text, llm):
        calls.append(text)
        return _make_decision()

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache()
    d1 = cache.get_or_classify(first, FakeLLM(), now=0.0)
    d2 = cache.get_or_classify(second, FakeLLM(), now=1.0)
    assert d1 is d2
    assert calls == [first]


def test_different_text_is_not_treated_as_same_key(monkeypatch):
    decisions = [_make_decision("a"), _make_decision("b")]

    def fake_classify(text, llm):
        return decisions.pop(0)

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache()
    d1 = cache.get_or_classify("Hello World", FakeLLM(), now=0.0)
    d2 = cache.get_or_classify("Hello World2", FakeLLM(), now=0.0)
    assert d1 is not d2


def test_cache_hit_returns_same_object_and_does_not_call_classify_or_llm(monkeypatch):
    decision = _make_decision()
    calls = []

    def fake_classify(text, llm):
        calls.append(text)
        return decision

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache(ttl_s=10.0)
    llm = _StubLLM()
    first = cache.get_or_classify("hello", llm, now=0.0)
    second = cache.get_or_classify("hello", llm, now=5.0)
    assert second is first
    assert calls == ["hello"]
    assert llm.calls == []


def test_cache_expiry_calls_classify_again_and_replaces_entry(monkeypatch):
    decisions = [_make_decision("first"), _make_decision("second")]
    calls = []

    def fake_classify(text, llm):
        calls.append(text)
        return decisions.pop(0)

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache(ttl_s=10.0)
    llm = FakeLLM()
    first = cache.get_or_classify("hello", llm, now=0.0)
    second = cache.get_or_classify("hello", llm, now=10.0)
    assert second is not first
    assert calls == ["hello", "hello"]


def test_now_none_uses_time_time(monkeypatch):
    monkeypatch.setattr(intake.cache.time, "time", lambda: 123.0)
    decisions = [_make_decision("first"), _make_decision("second")]

    def fake_classify(text, llm):
        return decisions.pop(0)

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache(ttl_s=10.0)
    first = cache.get_or_classify("hello", FakeLLM())
    assert cache.get_or_classify("hello", FakeLLM(), now=130.0) is first
    assert cache.get_or_classify("hello", FakeLLM(), now=133.0) is not first


def test_get_or_classify_does_not_call_time_time_when_now_given(monkeypatch):
    def boom():
        raise AssertionError("time.time() must not be called when now is given")

    monkeypatch.setattr(intake.cache.time, "time", boom)
    monkeypatch.setattr(intake.cache, "classify", lambda text, llm: _make_decision())
    cache = DecisionCache()
    cache.get_or_classify("hello", FakeLLM(), now=0.0)


def test_classify_exception_propagates_and_does_not_poison_cache(monkeypatch):
    def fake_classify(text, llm):
        raise ValidationError("text must not be empty or whitespace-only")

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache()
    with pytest.raises(ValidationError):
        cache.get_or_classify("", FakeLLM(), now=0.0)
    assert cache.size == 0


def test_agent_error_propagates_without_overwriting_live_entry(monkeypatch):
    good_decision = _make_decision()
    responses = [good_decision, AgentError("intent: bad output")]

    def fake_classify(text, llm):
        result = responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache(ttl_s=10.0)
    first = cache.get_or_classify("hello", FakeLLM(), now=0.0)
    with pytest.raises(AgentError):
        cache.get_or_classify("hello", FakeLLM(), now=10.0)
    still_cached = cache.get_or_classify("hello", FakeLLM(), now=5.0)
    assert still_cached is first


def test_size_is_zero_for_empty_cache():
    assert DecisionCache().size == 0


def test_size_counts_only_live_entries(monkeypatch):
    monkeypatch.setattr(intake.cache.time, "time", lambda: 100.0)
    monkeypatch.setattr(intake.cache, "classify", lambda text, llm: _make_decision())
    cache = DecisionCache(ttl_s=10.0)
    cache.get_or_classify("alive", FakeLLM(), now=95.0)
    cache.get_or_classify("expired", FakeLLM(), now=50.0)
    assert cache.size == 1


def test_size_reads_current_time_via_time_time(monkeypatch):
    monkeypatch.setattr(intake.cache, "classify", lambda text, llm: _make_decision())
    cache = DecisionCache(ttl_s=10.0)
    cache.get_or_classify("hello", FakeLLM(), now=0.0)

    monkeypatch.setattr(intake.cache.time, "time", lambda: 5.0)
    assert cache.size == 1

    monkeypatch.setattr(intake.cache.time, "time", lambda: 11.0)
    assert cache.size == 0


def test_clear_removes_all_entries_regardless_of_liveness(monkeypatch):
    monkeypatch.setattr(intake.cache.time, "time", lambda: 1000.0)
    monkeypatch.setattr(intake.cache, "classify", lambda text, llm: _make_decision())
    cache = DecisionCache(ttl_s=10.0)
    cache.get_or_classify("live", FakeLLM(), now=1.0)
    cache.get_or_classify("expired", FakeLLM(), now=-100.0)
    cache.clear()
    assert cache.size == 0


def test_get_or_classify_is_a_miss_right_after_clear(monkeypatch):
    calls = []

    def fake_classify(text, llm):
        calls.append(text)
        return _make_decision()

    monkeypatch.setattr(intake.cache, "classify", fake_classify)
    cache = DecisionCache(ttl_s=10.0)
    cache.get_or_classify("hello", FakeLLM(), now=0.0)
    cache.clear()
    cache.get_or_classify("hello", FakeLLM(), now=1.0)
    assert calls == ["hello", "hello"]

import pytest

import intake.ratelimit
from intake.errors import ValidationError
from intake.ratelimit import RateLimiter


def test_constructor_stores_limit_and_window_s():
    limiter = RateLimiter(limit=5, window_s=30.0)
    assert limiter.limit == 5
    assert limiter.window_s == 30.0


def test_constructor_defaults():
    limiter = RateLimiter()
    assert limiter.limit == 30
    assert limiter.window_s == 60.0


def test_allow_true_under_limit():
    limiter = RateLimiter(limit=2, window_s=60.0)
    assert limiter.allow("alice", now=0.0) is True
    assert limiter.allow("alice", now=1.0) is True


def test_allow_false_at_limit():
    limiter = RateLimiter(limit=2, window_s=60.0)
    limiter.allow("alice", now=0.0)
    limiter.allow("alice", now=1.0)
    assert limiter.allow("alice", now=2.0) is False


def test_denied_call_is_not_recorded_and_does_not_count_against_future_calls():
    limiter = RateLimiter(limit=1, window_s=60.0)
    assert limiter.allow("alice", now=0.0) is True
    assert limiter.allow("alice", now=1.0) is False
    # the window has not advanced past 0.0, so a new denied call changes nothing
    assert limiter.allow("alice", now=2.0) is False
    # once the original moment drops out of the window, allow succeeds again
    assert limiter.allow("alice", now=61.0) is True


def test_moment_exactly_at_window_edge_still_counts():
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=0.0)
    # now - window_s == 0.0, which is NOT < now - window_s, so it still counts
    assert limiter.allow("alice", now=60.0) is False


def test_moment_just_past_window_edge_drops_out():
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=0.0)
    assert limiter.allow("alice", now=60.000001) is True


def test_customers_have_independent_histories():
    limiter = RateLimiter(limit=1, window_s=60.0)
    assert limiter.allow("alice", now=0.0) is True
    assert limiter.allow("bob", now=0.0) is True
    assert limiter.allow("alice", now=1.0) is False
    assert limiter.allow("bob", now=1.0) is False


def test_customer_id_is_stripped_and_treated_as_same_customer():
    limiter = RateLimiter(limit=1, window_s=60.0)
    assert limiter.allow("alice", now=0.0) is True
    assert limiter.allow("  alice  ", now=1.0) is False
    assert limiter.allow("alice\t", now=2.0) is False


def test_allow_raises_validation_error_on_empty_customer_id():
    limiter = RateLimiter(limit=1, window_s=60.0)
    with pytest.raises(ValidationError):
        limiter.allow("", now=0.0)


def test_allow_raises_validation_error_on_whitespace_only_customer_id():
    limiter = RateLimiter(limit=1, window_s=60.0)
    with pytest.raises(ValidationError):
        limiter.allow("   \t  ", now=0.0)


def test_allow_error_does_not_record_anything():
    limiter = RateLimiter(limit=1, window_s=60.0)
    with pytest.raises(ValidationError):
        limiter.allow("", now=0.0)
    assert limiter.remaining("alice", now=0.0) == 1


def test_allow_now_none_uses_time_time(monkeypatch):
    monkeypatch.setattr(intake.ratelimit.time, "time", lambda: 100.0)
    limiter = RateLimiter(limit=1, window_s=60.0)
    assert limiter.allow("alice") is True
    assert limiter.allow("alice", now=100.0) is False
    assert limiter.allow("alice", now=160.000001) is True


def test_allow_does_not_call_time_time_when_now_given(monkeypatch):
    def boom():
        raise AssertionError("time.time() must not be called when now is given")

    monkeypatch.setattr(intake.ratelimit.time, "time", boom)
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=0.0)


def test_remaining_returns_limit_when_no_history():
    limiter = RateLimiter(limit=3, window_s=60.0)
    assert limiter.remaining("alice", now=0.0) == 3


def test_remaining_decreases_as_moments_are_recorded():
    limiter = RateLimiter(limit=3, window_s=60.0)
    limiter.allow("alice", now=0.0)
    assert limiter.remaining("alice", now=1.0) == 2
    limiter.allow("alice", now=1.0)
    assert limiter.remaining("alice", now=2.0) == 1
    limiter.allow("alice", now=2.0)
    assert limiter.remaining("alice", now=3.0) == 0


def test_remaining_recovers_as_moments_drop_out_of_window():
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=0.0)
    assert limiter.remaining("alice", now=60.0) == 0
    assert limiter.remaining("alice", now=60.000001) == 1


def test_remaining_does_not_record_or_change_history():
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=0.0)
    limiter.remaining("alice", now=0.5)
    limiter.remaining("alice", now=0.5)
    limiter.remaining("alice", now=0.5)
    assert limiter.allow("alice", now=0.5) is False
    assert limiter.allow("alice", now=60.000001) is True


def test_remaining_raises_validation_error_on_empty_customer_id():
    limiter = RateLimiter(limit=1, window_s=60.0)
    with pytest.raises(ValidationError):
        limiter.remaining("   ", now=0.0)


def test_remaining_strips_customer_id():
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=0.0)
    assert limiter.remaining("  alice  ", now=0.5) == 0


def test_remaining_now_none_uses_time_time(monkeypatch):
    monkeypatch.setattr(intake.ratelimit.time, "time", lambda: 100.0)
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.allow("alice", now=100.0)
    assert limiter.remaining("alice") == 0


def test_remaining_does_not_call_time_time_when_now_given(monkeypatch):
    def boom():
        raise AssertionError("time.time() must not be called when now is given")

    monkeypatch.setattr(intake.ratelimit.time, "time", boom)
    limiter = RateLimiter(limit=1, window_s=60.0)
    limiter.remaining("alice", now=0.0)

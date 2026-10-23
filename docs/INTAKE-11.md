# INTAKE-11: Per-customer rate limit

**User story:** As the operator of the intake service, I want to cap how many requests a single
customer can make in a rolling time window, so that one customer cannot monopolise the service.

## Requirements

1. Add a new module `intake/ratelimit.py` exposing a class `RateLimiter` with constructor
   signature `RateLimiter(limit: int = 30, window_s: float = 60.0) -> None`, storing `limit` (the
   maximum number of requests allowed per customer per window) and `window_s` (the window length,
   in seconds) for this instance.

2. `intake/ratelimit.py` imports the `time` module as `import time` (not `from time import
   time`), so that `time.time` is reachable and patchable in tests as the attribute
   `intake.ratelimit.time.time` (for example via `monkeypatch.setattr(intake.ratelimit.time,
   "time", ...)`). The default for `now` in both `allow` (requirement 4) and `remaining`
   (requirement 8) must be read through this `time.time()` call, and through no other import of
   `time`.

3. `RateLimiter` exposes a method `allow(self, customer_id: str, now: float | None = None) ->
   bool`.

4. When `now` is `None`, `allow` treats the current moment as `time.time()` (requirement 2). When
   `now` is given (not `None`), it is used as the current moment instead, and `allow` must not
   call `time.time()` at all in that case.

5. Customer identification: before anything else, `allow` strips leading and trailing whitespace
   from `customer_id`. Two calls whose `customer_id` strips to the same string refer to the same
   customer's request history; a different stripped string is a different customer with an
   independent history (requirement 7). If the stripped `customer_id` is the empty string, `allow`
   raises `intake.errors.ValidationError` and does not record anything (the call has no effect on
   any customer's history).

6. Sliding window and limiting: for each customer (identified by its stripped `customer_id`),
   `RateLimiter` remembers the moments `now` at which previous calls to `allow` for that customer
   returned `True` ("allowed moments"). On a call `allow(customer_id, now=now)` (with `now`
   resolved per requirements 2/4), for that customer's allowed moments:
   - a moment `t` counts toward the customer's current count unless `t < now - window_s`; that
     is, only a moment strictly less than `now - window_s` drops out of the window, and a moment
     exactly equal to `now - window_s` still counts;
   - if the number of moments that still count is strictly less than `limit`, the call is
     allowed: `allow` returns `True` and records `now` as a new allowed moment for that customer;
   - otherwise (the count is already `>= limit`), the call is **not** allowed: `allow` returns
     `False`, and `now` is **not** recorded — the call that would exceed the limit does not count
     against any future call.

7. Customer histories are independent: calls for one (stripped) `customer_id` never count toward,
   and are never counted by, the allowed-moments history of a different (stripped) `customer_id`.

8. `RateLimiter` exposes a method `remaining(self, customer_id: str, now: float | None = None) ->
   int`. It applies the same `customer_id` stripping and validation as requirement 5 (raising
   `intake.errors.ValidationError` if the stripped `customer_id` is empty) and resolves `now` the
   same way as requirements 2/4 (defaulting to `time.time()`, and not calling `time.time()` when
   `now` is given). It returns `limit` minus the number of that customer's allowed moments that
   still count in the window as of `now`, using the exact windowing rule from requirement 6 — in
   other words, the number of immediately-following calls to `allow(customer_id, now=now)` that
   would currently return `True` before any of them is denied. Calling `remaining` never records a
   new moment and never otherwise changes any customer's history, so calling it any number of
   times has no effect on subsequent calls to `allow` or `remaining`.

## Out of scope

- Thread-safety / concurrent access to the same `RateLimiter` instance from multiple threads.
- Persisting rate-limit state across process restarts, or sharing it between multiple
  `RateLimiter` instances.
- Wiring `RateLimiter` into `intake/api.py` or any HTTP endpoint.
- Any eviction, cleanup, or memory-bounding of old allowed moments beyond what is needed to
  implement the windowing rule in requirement 6; moments that have dropped out of the window may
  remain in internal storage until overwritten or the process ends — only the return values of
  `allow` and `remaining` are observable.
- Validating `limit` or `window_s` (e.g. rejecting zero, negative, or non-numeric values).
- Any identification of the caller beyond the provided `customer_id` string (e.g. IP address,
  auth tokens, request headers).

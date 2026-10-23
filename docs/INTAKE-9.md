# INTAKE-9: Decision cache

**User story:** As the operator of the intake service, I want repeated identical support
requests classified only once within a short time window, so that the five agents and the
router are not re-run for a text we already classified a moment ago.

## Requirements

1. Add a new module `intake/cache.py` exposing a class `DecisionCache` with constructor
   signature `DecisionCache(ttl_s: float = 60.0) -> None`, storing `ttl_s` as the entry
   lifetime, in seconds, for this cache instance.

2. `intake/cache.py` imports the `time` module as `import time` (not `from time import time`),
   so that `time.time` is reachable and patchable in tests as the attribute
   `intake.cache.time.time` (for example via `monkeypatch.setattr(intake.cache.time, "time",
   ...)`). Both the default for `now` (requirement 4) and the `size` property (requirement 8)
   must read the current time through this `time.time()` call, not through any other import of
   `time`.

3. `DecisionCache` exposes a method `get_or_classify(self, text: str, llm: intake.llm.LLM, now:
   float | None = None) -> intake.orchestrator.Decision`.

4. When `now` is `None`, `get_or_classify` treats the current moment as `time.time()` (see
   requirement 2). When `now` is given, it is used as the current moment instead, and
   `get_or_classify` must not call `time.time()` in that case.

5. Cache key normalisation: two calls to `get_or_classify` are considered to be requesting the
   same text when, after (a) stripping leading and trailing whitespace, (b) collapsing every
   run of one or more whitespace characters (spaces, tabs, newlines, ...) elsewhere in the text
   into a single space character, and (c) lower-casing the result, the two resulting strings are
   identical. For example `"Hello   World"`, `"  hello world  "` and `"hello\nworld"` all
   normalise to the same key and are treated as the same cached text; `"Hello World"` and `"Hello
   World2"` do not.

6. Cache hit: if, for the normalised key of `text`, there is an entry that was stored at a moment
   `t0` (requirement 7) such that `now - t0 < ttl_s` ("live"), `get_or_classify` returns that
   entry's `Decision` object (the exact same object previously returned, i.e. `is`-identical) and
   does **not** call `intake.orchestrator.classify` or `llm.complete` at all.

7. Cache miss or expiry: if there is no entry for the normalised key of `text`, or the existing
   entry is not live per requirement 6 (i.e. `now - t0 >= ttl_s`, "expired"), `get_or_classify`
   calls `intake.orchestrator.classify(text, llm)` with `text` passed exactly as received (not
   normalised — the agents and the router must see the original text, unchanged), stores the
   returned `Decision` as the entry for the normalised key together with the moment `now` used
   for this call (replacing any previous entry for that key), and returns that `Decision`.

8. `DecisionCache` exposes a read-only property `size` returning an `int`: the number of entries
   currently stored whose stored moment `t0` is still live, i.e. for which `time.time() - t0 <
   ttl_s` (same liveness rule as requirement 6, but evaluated against `time.time()` right now,
   since `size` takes no `now` argument — see requirement 2). Entries for which `time.time() -
   t0 >= ttl_s` do not count towards `size`, even if `get_or_classify` has not been called again
   to notice their expiry.

9. `DecisionCache` exposes a method `clear(self) -> None` that removes every entry from the
   cache, regardless of whether it is live or expired; immediately afterwards, `size` is `0`, and
   the next `get_or_classify` call for any text is a cache miss (requirement 7).

10. If `intake.orchestrator.classify` raises (`intake.errors.ValidationError` or
    `intake.errors.AgentError`), `get_or_classify` lets that exception propagate unchanged to its
    caller, and must not create or replace any cache entry for that text as a result (any
    previously-live entry for that normalised key, if one existed, is left untouched).

11. `intake/cache.py` is a new, standalone module: `intake/api.py` and `intake/orchestrator.py`
    are not modified by this story. `POST /classify` keeps calling
    `intake.orchestrator.classify` directly on every request, exactly as before — the cache from
    this story is not wired into the HTTP endpoint, so two identical requests to `POST /classify`
    still run the agents twice.

## Out of scope

- Wiring `DecisionCache` into `intake/api.py` or `POST /classify` (requirement 11) — that is a
  future story.
- Thread-safety / concurrent access to the same `DecisionCache` instance from multiple threads.
- Any eviction policy, size limit, or background cleanup beyond what requirements 6-9 describe;
  expired entries may remain in internal storage until overwritten by requirement 7 or removed by
  `clear()` — only `size` (requirement 8) and the behaviour described above are observable.
- Persisting the cache across process restarts, or sharing it between multiple `DecisionCache`
  instances.
- Any change to `intake/orchestrator.py`, `intake/llm.py`, or the agents.
- Validating `ttl_s` (e.g. rejecting zero or negative values).

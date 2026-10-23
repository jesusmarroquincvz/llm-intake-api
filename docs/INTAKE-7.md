# INTAKE-7: Orchestrator

**User story:** As the intake pipeline, I need an orchestrator that runs the five independent
classification agents concurrently, feeds their signals to the routing agent, and assembles a
single decision, so that one call classifies and routes a support request end to end.

## Requirements

1. Add a new module `intake/orchestrator.py` that exposes:
   - a dataclass `Decision` with exactly these fields: `intent: str`, `urgency: str`,
     `language: str`, `pii: PiiResult` (from `intake.agents.pii`), `sentiment: SentimentResult`
     (from `intake.agents.sentiment`), and `routing: RoutingResult` (from
     `intake.agents.routing`);
   - a function with exactly this signature: `classify(text: str, llm: LLM) -> Decision`.

2. Input validation: if `text` is empty or consists only of whitespace, `classify` raises
   `intake.errors.ValidationError` **before any agent is called** — `llm.complete` must not be
   invoked at all in this case.

3. Otherwise, `classify` runs the five independent agents below, each called with `(text, llm)`
   exactly as its existing signature requires:
   - `intake.agents.intent.classify_intent`
   - `intake.agents.urgency.classify_urgency`
   - `intake.agents.language.detect_language`
   - `intake.agents.pii.detect_pii`
   - `intake.agents.sentiment.analyse_sentiment`

   These five calls are submitted to a `concurrent.futures.ThreadPoolExecutor` with enough
   worker threads for all five to be in flight at the same time (for example `max_workers=5`).
   `classify` must not call them sequentially (i.e. it must not wait for one to finish before
   starting the next) — all five must be submitted before `classify` blocks on any of their
   results.

4. Once all five of the agents in requirement 3 have completed successfully, `classify` builds a
   `signals` dict with exactly these keys and values:
   - `"intent"`: the string returned by `classify_intent`
   - `"urgency"`: the string returned by `classify_urgency`
   - `"language"`: the string returned by `detect_language`
   - `"pii_types"`: the `types` list from the `PiiResult` returned by `detect_pii`
   - `"sentiment"`: the `label` string from the `SentimentResult` returned by `analyse_sentiment`
   - `"escalate"`: the `escalate` bool from the `SentimentResult` returned by `analyse_sentiment`

5. `classify` then calls `intake.agents.routing.route(text, signals, llm)` using the `signals`
   dict from requirement 4, and only after all five agents from requirement 3 have completed —
   it must not call `route` while any of the five is still running. The returned `RoutingResult`
   becomes `Decision.routing`.

6. `Decision`'s other fields are taken directly from the five agents' outputs: `intent`,
   `urgency`, and `language` are the plain strings returned by their respective agents; `pii` is
   the `PiiResult` returned by `detect_pii`; `sentiment` is the `SentimentResult` returned by
   `analyse_sentiment`.

7. Error propagation: if any of the six agent calls (the five from requirement 3, or `route` from
   requirement 5) raises `intake.errors.AgentError`, `classify` raises `intake.errors.AgentError`
   instead of returning a `Decision`. The new exception's message is exactly
   `f"{agent_name}: {original_message}"`, where:
   - `agent_name` is `"intent"`, `"urgency"`, `"language"`, `"pii"`, or `"sentiment"` for a
     failure in one of the five agents from requirement 3 (matching which one failed), or
     `"routing"` for a failure in `route`;
   - `original_message` is `str()` of the `AgentError` that the failing agent raised.
   Any results already produced by other agents are discarded — `classify` does not return a
   partial `Decision`. (Behaviour when more than one of the five agents fails at the same time is
   unspecified — only one failing agent at a time needs to be handled correctly.)

8. `Decision` has a method `to_dict(self) -> dict` that returns a plain, JSON-serialisable dict
   of exactly this shape (no dataclass instances anywhere in the result):
   ```
   {
       "intent": <str>,
       "urgency": <str>,
       "language": <str>,
       "pii": {"types": [<str>, ...], "redacted": <str>},
       "sentiment": {"label": <str>, "escalate": <bool>},
       "routing": {"team": <str>, "summary": <str>, "actions": [<str>, ...]},
   }
   ```

## Out of scope

- The five independent agents and the routing agent themselves (already implemented) — the
  orchestrator only calls them and assembles their outputs.
- Retrying a failed agent, timeouts for slow agents, or producing a partial/degraded `Decision`
  when an agent fails.
- Any validation of `text` beyond the empty/whitespace-only check.
- Any validation of `llm` itself.
- Caching, logging, or metrics for the orchestration.
- Deterministic behaviour when more than one of the five independent agents fails at the same
  time (see requirement 7).

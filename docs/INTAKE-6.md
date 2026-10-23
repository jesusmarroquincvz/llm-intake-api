# INTAKE-6: Routing and summary agent

**User story:** As the intake orchestrator, I need an agent that takes the other agents' signals
together with the request text and decides which team should handle it, with a one-sentence
summary and a short list of next actions, so that a request can be routed and triaged in one step.

## Requirements

1. Add a new module `intake/agents/routing.py` that exposes:
   - a dataclass `RoutingResult` with exactly these fields: `team: str`, `summary: str`, and
     `actions: list[str]`;
   - a function with exactly this signature: `route(text: str, signals: dict, llm: LLM) -> RoutingResult`.

2. The set of valid team names is exactly: `billing-ops`, `support-l1`, `support-l2`,
   `engineering`, `trust-safety`.

3. `signals` is a dict carrying the other agents' outputs, with keys `intent`, `urgency`,
   `language`, `pii_types`, `sentiment`, and `escalate`. The function does not validate or
   transform `signals` in any way (that is each producing agent's responsibility) — it passes the
   dict through unchanged.

4. The function builds the user message by JSON-encoding (via `json.dumps`) a dict of exactly
   this shape: `{"text": text, "signals": signals}`. This encoded string is passed as `user` to
   `llm.complete`.

5. The function builds a system prompt that states the routing policy the model must follow:
   - if `escalate` is true, or the request raises trust or safety concerns, route to
     `trust-safety`;
   - otherwise, if the intent is a bug and urgency is high, route to `engineering`;
   - otherwise, if the intent is a bug (any other urgency), route to `support-l2`;
   - otherwise, if the intent is billing, route to `billing-ops`;
   - otherwise, route to `support-l1`.
   The prompt names all five valid team names (requirement 2) and instructs the model to respond
   with a JSON object of the shape `{"team": ..., "summary": ..., "actions": [...]}`, where
   `"team"` is one of the five valid team names, `"summary"` is one sentence describing the
   request (at most 160 characters), and `"actions"` is a JSON array of zero to three short
   imperative strings describing what should be done next (an empty array if none are needed).

6. The function calls `llm.complete(system=<the system prompt>, user=<the JSON string from
   requirement 4>, config=MODELS["routing"])` — where `MODELS` is `intake.config.MODELS` —
   **exactly once**.

7. Validation of the model's response:
   - If the response dict has no `"team"` key, raise `intake.errors.AgentError`.
   - The team value is normalised by stripping surrounding whitespace and lower-casing it, exactly
     as the intent agent (`intake/agents/intent.py`) normalises its label. If, after
     normalisation, the team is not one of the five valid team names (requirement 2), raise
     `intake.errors.AgentError`.
   - If the response dict has no `"summary"` key, raise `intake.errors.AgentError`.
   - If the `"summary"` value, taken as a `str`, is longer than 160 characters, raise
     `intake.errors.AgentError`.
   - If the response dict has no `"actions"` key, `RoutingResult.actions` is `[]` (an empty
     list) — this is not an error.
   - If the response dict has an `"actions"` key, its value must be a list; if that list has more
     than 3 entries, raise `intake.errors.AgentError`. Otherwise, `RoutingResult.actions` is that
     list with each entry taken as a `str`, in the order the model returned them.

8. `RoutingResult.team` is the normalised team from requirement 7, and `RoutingResult.summary` is
   the response's `"summary"` value taken as-is as a `str` (no normalisation).

9. Input validation: if `text` is empty or consists only of whitespace, raise
   `intake.errors.ValidationError` **before** calling the model (`llm.complete` must not be
   invoked in this case).

## Out of scope

- The other five agents (intent, urgency, language, pii, sentiment) and validating or producing
  the values inside `signals` — `route` trusts `signals` as given.
- The orchestrator that runs the other agents, assembles `signals`, and calls `route`.
- Enforcing that the model's chosen team actually matches the routing policy described in the
  system prompt (e.g. checking that `escalate: true` in `signals` really produced `trust-safety`)
  — the function only validates the shape of the model's answer, not its adherence to the policy.
- Enforcing that `"summary"` is grammatically a single sentence, beyond the 160-character length
  check.
- Validating the content or imperative phrasing of `"actions"` entries beyond the count check.
- Handling of malformed (non-JSON) raw model output — that is already handled by the LLM door
  (`intake.llm.parse_json` / `GeminiLLM`) before `route` ever sees a response.
- Any validation of `text` beyond the empty/whitespace-only check (e.g. length limits, encoding,
  content filtering).
- Retry logic for failed or invalid model calls.

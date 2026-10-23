# INTAKE-5: Sentiment agent

**User story:** As the intake orchestrator, I need an agent that reads the sentiment of an
incoming support request and flags when it needs to be escalated, so that angry or at-risk
customers can be routed to a human quickly.

## Requirements

1. Add a new module `intake/agents/sentiment.py` that exposes:
   - a dataclass `SentimentResult` with exactly these fields: `label: str` and `escalate: bool`;
   - a function with exactly this signature: `analyse_sentiment(text: str, llm: LLM) -> SentimentResult`.

2. The set of valid sentiment labels is exactly: `negative`, `neutral`, `positive`.

3. The function builds a system prompt that instructs the model to read the support request and
   respond with a JSON object of the shape `{"sentiment": <label>, "escalate": <bool>}`, where:
   - `<label>` is one of the three valid labels (requirement 2);
   - `<bool>` is `true` when the customer threatens to cancel, mentions legal action, or uses
     abusive language, and `false` otherwise.
   The prompt names all three valid labels and states all three escalation triggers (threatening
   to cancel, mentioning legal action, using abusive language).

4. The function calls `llm.complete(system=<the system prompt>, user=text,
   config=MODELS["sentiment"])` — where `MODELS` is `intake.config.MODELS` — **exactly once**.

5. Validation of the model's response, in this order:
   - If the response dict has no `"sentiment"` key, raise `intake.errors.AgentError`.
   - Otherwise normalise the `"sentiment"` value by stripping surrounding whitespace and
     lower-casing it, exactly as the intent agent (`intake/agents/intent.py`) normalises its
     label. If, after normalisation, the value is not one of the three valid labels (requirement
     2), raise `intake.errors.AgentError`. This normalised value becomes `SentimentResult.label`.
   - If the response dict has no `"escalate"` key, `SentimentResult.escalate` defaults to `False`
     (this is not an error).
   - If the response dict has an `"escalate"` key, its value must be a `bool` (`True` or `False`
     exactly, not a truthy/falsy stand-in such as the integer `1`, the string `"true"`, or `None`).
     If it is not a `bool`, raise `intake.errors.AgentError`. Otherwise `SentimentResult.escalate`
     is that `bool` value, taken as-is.

6. Input validation: if `text` is empty or consists only of whitespace, raise
   `intake.errors.ValidationError` **before** calling the model (`llm.complete` must not be
   invoked in this case).

## Out of scope

- The other five classification agents (intent, urgency, language, PII, routing).
- The orchestrator that runs the agents and combines their decisions.
- Verifying that the model's escalation decision is actually correct for the given text (e.g.
  that `text` really does contain a cancellation threat) — the function trusts the model's
  `"sentiment"` and `"escalate"` values as given, once they pass the type/label checks above.
- Handling of malformed (non-JSON) raw model output — that is already handled by the LLM door
  (`intake.llm.parse_json` / `GeminiLLM`) before `analyse_sentiment` ever sees a response.
- Any validation of `text` beyond the empty/whitespace-only check (e.g. length limits, encoding,
  content filtering).
- Retry logic for failed or invalid model calls.

# INTAKE-4: PII agent

**User story:** As the intake orchestrator, I need an agent that detects personally identifiable
information in an incoming support request and produces a redacted version of the text, so that
PII does not leak downstream to routing, logging, or other systems.

## Requirements

1. Add a new module `intake/agents/pii.py` that exposes:
   - a dataclass `PiiResult` with exactly these fields: `types: list[str]` and `redacted: str`;
   - a function with exactly this signature: `detect_pii(text: str, llm: LLM) -> PiiResult`.

2. The set of valid PII type names is exactly: `email`, `phone`, `card`, `address`, `name`.

3. The function builds a system prompt that instructs the model to detect PII in the support
   request and respond with a JSON object of the shape `{"types": [...], "redacted": "..."}`,
   where:
   - `"types"` is a JSON array containing whichever of the five valid type names (requirement 2)
     appear in the text (an empty array if none appear).
   - `"redacted"` is the input text with each PII value the model found replaced by its type
     name in angle brackets (e.g. an email address replaced by `<email>`, a phone number by
     `<phone>`, and so on).
   The prompt names all five valid type names and shows the angle-bracket format with at least
   one example (e.g. `<email>`).

4. The function calls `llm.complete(system=<the system prompt>, user=text, config=MODELS["pii"])`
   — where `MODELS` is `intake.config.MODELS` — **exactly once**.

5. Validation of the model's response:
   - If the response dict has no `"types"` key or no `"redacted"` key, raise
     `intake.errors.AgentError`.
   - Each entry of `"types"` is normalised by stripping surrounding whitespace and lower-casing
     it, exactly as the intent agent (`intake/agents/intent.py`) normalises its label. If, after
     normalisation, any entry is not one of the five valid type names from requirement 2, raise
     `intake.errors.AgentError`.

6. Building `PiiResult.types`: after normalising and validating every entry of the response's
   `"types"` list (requirement 5), remove duplicate values and sort the remaining values
   alphabetically; this sorted, duplicate-free list is `PiiResult.types`. `PiiResult.redacted` is
   the response's `"redacted"` value, taken as-is as a `str`, with no further transformation.

7. An empty `"types"` list in the response is a valid answer, not an error: it produces
   `PiiResult(types=[], redacted=<response's "redacted" value>)`. In particular, the model is
   free to answer that no PII was found with `"redacted"` equal to the original input text, and
   the function must accept that result unchanged.

8. Input validation: if `text` is empty or consists only of whitespace, raise
   `intake.errors.ValidationError` **before** calling the model (`llm.complete` must not be
   invoked in this case).

## Out of scope

- The other five classification agents (intent, urgency, language, sentiment, routing).
- The orchestrator that runs the agents and combines their decisions.
- Verifying that every PII value actually present in `text` was found by the model, or that
  `"redacted"` is a faithful redaction of `text` — the function trusts the model's `"redacted"`
  string as given.
- Handling of malformed (non-JSON) raw model output — that is already handled by the LLM door
  (`intake.llm.parse_json` / `GeminiLLM`) before `detect_pii` ever sees a response.
- Any validation of `text` beyond the empty/whitespace-only check (e.g. length limits, encoding,
  content filtering).
- Retry logic for failed or invalid model calls.

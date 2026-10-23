# INTAKE-2: Urgency agent

**User story:** As the intake orchestrator, I need an agent that classifies an incoming support
request's urgency, so that urgent requests can be prioritised for handling.

## Requirements

1. Add a new module `intake/agents/urgency.py` that exposes a function with exactly this
   signature: `classify_urgency(text: str, llm: LLM) -> str`.
2. The function builds a system prompt that instructs the model to classify the support request
   into **exactly one** of these three labels: `high`, `medium`, `low`, defined as:
   - `high`: the customer cannot use the product, or money is at risk.
   - `medium`: the product is degraded but still working.
   - `low`: questions, requests, or feedback.
   The prompt asks the model to answer with a JSON object of the shape `{"urgency": <label>}`.
3. The function calls `llm.complete(system=<the system prompt>, user=text, config=MODELS["urgency"])`
   — where `MODELS` is `intake.config.MODELS` — **exactly once**, and returns the classified
   label as a `str`.
4. Validation of the model's response:
   - If the response dict has no `"urgency"` key, raise `intake.errors.AgentError`.
   - If the value of `"urgency"`, after normalisation (see requirement 5), is not one of the
     three valid labels (`high`, `medium`, `low`), raise `intake.errors.AgentError`.
5. Label normalisation: before validating and returning the label, strip surrounding whitespace
   and lower-case it, exactly as the intent agent (`intake/agents/intent.py`) does. For example,
   a model response of `"High"` (or `"  High  "`) must be normalised to `"high"`.
6. Input validation: if `text` is empty or consists only of whitespace, raise
   `intake.errors.ValidationError` **before** calling the model (`llm.complete` must not be
   invoked in this case).

## Out of scope

- The other five classification agents (intent, language, pii, sentiment, routing).
- The orchestrator that runs the agents and combines their decisions.
- Handling of malformed (non-JSON) raw model output — that is already handled by the LLM door
  (`intake.llm.parse_json` / `GeminiLLM`) before `classify_urgency` ever sees a response.
- Any validation of `text` beyond the empty/whitespace-only check (e.g. length limits,
  encoding, content filtering).
- Retry logic for failed or invalid model calls.

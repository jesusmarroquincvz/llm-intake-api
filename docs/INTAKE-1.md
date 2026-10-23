# INTAKE-1: Intent agent

**User story:** As the intake orchestrator, I need an agent that classifies an incoming support
request's intent, so that the request can be routed to the right downstream handling.

## Requirements

1. Add a new module `intake/agents/intent.py` that exposes a function with exactly this
   signature: `classify_intent(text: str, llm: LLM) -> str`.
2. The function builds a system prompt that instructs the model to classify the support request
   into **exactly one** of these five labels: `billing`, `account`, `bug`, `feature`, `other`,
   and to answer with a JSON object of the shape `{"intent": <label>}`.
3. The function calls `llm.complete(system=<the system prompt>, user=text, config=MODELS["intent"])`
   — where `MODELS` is `intake.config.MODELS` — **exactly once**, and returns the classified
   label as a `str`.
4. Validation of the model's response:
   - If the response dict has no `"intent"` key, raise `intake.errors.AgentError`.
   - If the value of `"intent"`, after normalisation (see requirement 5), is not one of the
     five valid labels (`billing`, `account`, `bug`, `feature`, `other`), raise
     `intake.errors.AgentError`.
5. Label normalisation: before validating and returning the label, strip surrounding whitespace
   and lower-case it. For example, a model response of `"Billing"` (or `"  Billing  "`) must be
   normalised to `"billing"`.
6. Input validation: if `text` is empty or consists only of whitespace, raise
   `intake.errors.ValidationError` **before** calling the model (`llm.complete` must not be
   invoked in this case).

## Out of scope

- The other five classification agents (urgency, language, pii, sentiment, routing).
- The orchestrator that runs the agents and combines their decisions.
- Handling of malformed (non-JSON) raw model output — that is already handled by the LLM door
  (`intake.llm.parse_json` / `GeminiLLM`) before `classify_intent` ever sees a response.
- Any validation of `text` beyond the empty/whitespace-only check (e.g. length limits,
  encoding, content filtering).
- Retry logic for failed or invalid model calls.

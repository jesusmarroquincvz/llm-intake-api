# INTAKE-3: Language agent

**User story:** As the intake orchestrator, I need an agent that detects the language of an
incoming support request, so that replies and routing can take the customer's language into
account.

## Requirements

1. Add a new module `intake/agents/language.py` that exposes a function with exactly this
   signature: `detect_language(text: str, llm: LLM) -> str`.
2. The function builds a system prompt that instructs the model to detect the language of the
   support request and respond with a JSON object of the shape `{"language": <code>}`, where
   `<code>` is an ISO 639-1 two-letter language code in lowercase. The prompt gives examples of
   valid codes (`en`, `es`, `pt`, `fr`, `de`, `it`) and makes clear that any two-letter lowercase
   code is an allowed answer, not just those examples.
3. The function calls `llm.complete(system=<the system prompt>, user=text, config=MODELS["language"])`
   — where `MODELS` is `intake.config.MODELS` — **exactly once**, and returns the detected
   language code as a `str`.
4. Validation of the model's response:
   - If the response dict has no `"language"` key, raise `intake.errors.AgentError`.
   - After normalisation (see requirement 5), if the resulting code is not exactly two letters
     (e.g. it is empty, one letter, three or more letters, or contains a character that is not a
     letter), raise `intake.errors.AgentError`.
5. Code normalisation: before validating and returning the code, strip surrounding whitespace and
   lower-case it, exactly as the intent agent (`intake/agents/intent.py`) does with its label. For
   example, a model response of `"EN"` (or `"  En  "`) must be normalised to `"en"`.
6. Unlike the intent and urgency agents, the set of valid codes is not a fixed list: any string
   that normalises to exactly two letters is accepted and returned as-is (e.g. `"zz"` is a valid
   return value even though it is not a real language code).
7. Input validation: if `text` is empty or consists only of whitespace, raise
   `intake.errors.ValidationError` **before** calling the model (`llm.complete` must not be
   invoked in this case).

## Out of scope

- The other five classification agents (intent, urgency, pii, sentiment, routing).
- The orchestrator that runs the agents and combines their decisions.
- Validating the returned code against a fixed list of real ISO 639-1 codes.
- Handling of malformed (non-JSON) raw model output — that is already handled by the LLM door
  (`intake.llm.parse_json` / `GeminiLLM`) before `detect_language` ever sees a response.
- Any validation of `text` beyond the empty/whitespace-only check (e.g. length limits,
  encoding, content filtering).
- Retry logic for failed or invalid model calls.

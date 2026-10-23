# INTAKE-10: Batch classification endpoint

**User story:** As a caller of the intake service, I want to classify several support requests
in a single HTTP call, so that I don't have to issue one `POST /classify` request per text.

## Requirements

1. Add a new route `POST /classify/batch` to `intake/api.py`, alongside the existing
   `POST /classify` route. It reads the request body as JSON, expecting an object of the shape
   `{"texts": [str, ...]}` (a list of strings under the key `"texts"`). On a request whose shape
   is valid (see requirement 2), it returns HTTP status `200` with a JSON body of the shape
   `{"decisions": [entry, ...]}`, where `decisions` has exactly one `entry` per element of
   `texts`, in the same order as `texts` (`decisions[i]` corresponds to `texts[i]`). Each `entry`
   is either:
   - the dict returned by `Decision.to_dict()` (`intake.orchestrator.Decision`) when `texts[i]`
     was classified successfully, or
   - a dict of the shape `{"error": <message>}`, where `<message>` is a non-empty string, when
     classifying `texts[i]` failed (see requirements 4 and 5).

   The overall response status is `200` whenever the request shape itself was valid, regardless
   of how many individual entries are `{"error": ...}` entries.

2. Request-shape validation happens before any text is classified and before any LLM call is
   made. If any of the following hold, `POST /classify/batch` returns HTTP status `422` with a
   JSON body `{"detail": <message>}` (`<message>` a non-empty string), makes no call to
   `intake.orchestrator.classify` or to the LLM's `complete` method for any text, and does not
   open the span described in requirement 3:
   - the parsed JSON body is not an object, or has no `"texts"` key ("missing texts field");
   - the value at `"texts"` is present but is not a list, or the list contains at least one
     element that is not a `str`;
   - the list at `"texts"` has zero elements;
   - the list at `"texts"` has more than 20 elements.

   A request whose `"texts"` list has between 1 and 20 elements (inclusive), all strings, passes
   this validation.

3. For a request that passes the validation in requirement 2, the entire remainder of the
   request's handling (the per-text processing described in requirements 4 and 5, and the
   assembly of the `decisions` list) happens inside exactly one span, opened via this module's
   existing `_tracer.start_as_current_span(...)` (see `intake/api.py`'s handling of
   `POST /classify` for the existing pattern), named `"classify_batch"`. Before any text is
   processed, this span's attribute `"batch.size"` is set to the number of elements in `texts`
   (i.e. `len(texts)`), counting every text in the request regardless of whether it later
   succeeds or produces an `{"error": ...}` entry.

4. Each element of `texts` is classified independently of the others, in order, inside the span
   from requirement 3, using the same module-level LLM that `POST /classify` uses (the one
   returned by `get_llm()` / replaceable via `set_llm()`):
   - If an element, after stripping leading and trailing whitespace, is the empty string (i.e.
     the text is empty or contains only whitespace), its `decisions` entry is
     `{"error": "text must not be empty"}` exactly, and neither `intake.orchestrator.classify`
     nor the LLM's `complete` method is called for this element.
   - Otherwise, `intake.orchestrator.classify(text, llm)` is called for this element, where
     `text` is the element exactly as given (not stripped) and `llm` is the module's current LLM.

5. For an element that reaches `intake.orchestrator.classify` (requirement 4's second case):
   - On success, its `decisions` entry is `decision.to_dict()`, where `decision` is the
     `intake.orchestrator.Decision` returned by `classify`.
   - If `classify` raises `intake.errors.AgentError` or `intake.errors.ValidationError` with
     message `e`, its `decisions` entry is `{"error": str(e)}` and processing continues with the
     remaining elements of `texts` — one element's failure does not affect any other element's
     entry, does not change the overall response status (still `200`), and does not stop the
     remaining elements from being classified.

## Out of scope

- Any change to `POST /classify`, `intake/orchestrator.py`, `intake/llm.py`, `intake/cache.py`,
  or any agent module.
- Running the per-text classifications in `texts` concurrently with each other (each text may be
  processed one after another; `intake.orchestrator.classify` already parallelises the five
  agents for a single text internally).
- Any limit, validation, or special handling of an individual text's length or content beyond
  the empty/whitespace-only check in requirement 4.
- Wiring `intake.cache.DecisionCache` into `POST /classify/batch`.
- Authentication, rate limiting, or any response format other than the JSON bodies described
  above.
- Malformed JSON request bodies (a body that fails to parse as JSON at all) for
  `POST /classify/batch` — only the shapes described in requirement 2 are specified.

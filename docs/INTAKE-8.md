# INTAKE-8: HTTP endpoint and tracing

**User story:** As a caller of the intake service, I can POST a support request's text to an
HTTP endpoint and get back the classification decision as JSON, with every call traced for
observability.

## Requirements

1. Add a new module `intake/api.py` that exposes a FastAPI application as the module-level
   attribute `app` (an instance of `fastapi.FastAPI`).

2. `app` exposes `POST /classify`, accepting a JSON request body with a string field `text`
   (for example `{"text": "my app crashes"}`).

3. On a valid request, the handler calls `intake.orchestrator.classify(text, llm)` (`llm` is the
   LLM described in requirements 4-6 below) with the request's `text` value, and on success
   responds with status `200` and a JSON body equal to exactly `decision.to_dict()`, where
   `decision` is the `Decision` returned by `classify`.

4. `intake/api.py` exposes a module-level function `get_llm() -> intake.llm.LLM` that:
   - returns `intake.llm.FakeLLM()` when the environment variable `INTAKE_LLM` is exactly the
     string `"fake"`;
   - otherwise returns `intake.llm.GeminiLLM()`.

5. The LLM used to serve `POST /classify` is created exactly once, at import time of
   `intake/api.py`, by calling `get_llm()` and storing the result at module level. `get_llm()`
   must not be called again afterwards by the running application (it is not re-invoked per
   request).

6. `intake/api.py` exposes a module-level function `set_llm(llm: intake.llm.LLM) -> None` that
   replaces the LLM used to serve `POST /classify` with `llm`. After `set_llm(llm)` is called,
   every subsequent call to `POST /classify` must use `llm` (this is how tests preload a
   `FakeLLM` with `INTAKE_LLM=fake` set before `intake.api` is imported, without constructing a
   real `GeminiLLM` or touching the network).

7. Error handling for `POST /classify`:
   - If `intake.orchestrator.classify` raises `intake.errors.ValidationError`, the endpoint
     responds with status `422` and a JSON body of exactly `{"detail": str(e)}`, where `e` is
     the raised `ValidationError`.
   - If `intake.orchestrator.classify` raises `intake.errors.AgentError`, the endpoint responds
     with status `502` and a JSON body of exactly `{"detail": str(e)}`, where `e` is the raised
     `AgentError`.
   - If the JSON request body does not supply a string value for `text` (for example, the `text`
     key is missing entirely from the body), the endpoint responds with status `422` and a JSON
     body of exactly `{"detail": <message>}`, where `<message>` is any non-empty string
     describing the problem (its exact wording is not specified, and `classify` must not be
     called in this case).

8. Add a new module `intake/tracing.py` that exposes a module-level function
   `setup_tracing(project_name: str = "intake-api") -> None`:
   - `intake/tracing.py` imports the module `phoenix.otel` (i.e. `import phoenix.otel`, not
     `from phoenix.otel import register`), so that the call described below is reachable, and
     patchable in tests, as the attribute `phoenix.otel.register`.
   - When `os.environ.get("PHOENIX_ENDPOINT")` is a non-empty string, `setup_tracing` calls
     `phoenix.otel.register(endpoint=os.environ["PHOENIX_ENDPOINT"], project_name=project_name,
     auto_instrument=True)`.
   - When `os.environ.get("PHOENIX_ENDPOINT")` is unset or empty, `setup_tracing` does nothing:
     it must not call `phoenix.otel.register`, and must not raise.

9. `intake/api.py` calls `intake.tracing.setup_tracing()` (using its default `project_name`) at
   import time, unconditionally — this must not raise and must not require `PHOENIX_ENDPOINT` to
   be set (see requirement 8's second bullet).

10. Every call to `intake.orchestrator.classify` made by the `POST /classify` handler (requirement
    3) is wrapped in a span:
    - the span is obtained from a tracer created with `opentelemetry.trace.get_tracer(...)` (for
      example `opentelemetry.trace.get_tracer(__name__)`), used as the current span for the
      duration of the `classify` call (for example via
      `tracer.start_as_current_span("classify")` as a context manager);
    - the span's name is exactly `"classify"`;
    - the span carries the attribute `input.value` set to the request's `text` string;
    - this applies whether `classify` succeeds or raises (requirement 7) — the span must be
      created and carry `input.value` in both cases.
    - This must work with `PHOENIX_ENDPOINT` unset (requirement 8's second bullet): creating the
      span and setting its attribute must not depend on `phoenix.otel.register` having been
      called.

## Out of scope

- Any HTTP route other than `POST /classify`.
- Authentication, authorization, rate limiting, CORS, or request logging beyond the single
  `"classify"` span described in requirement 10.
- Retrying a failed `classify` call, request timeouts, or graceful shutdown/flushing of the
  tracer provider.
- The internals of `GeminiLLM` and `FakeLLM` (already implemented in `intake/llm.py`), and of
  `Decision`/`classify` (already implemented in `intake/orchestrator.py`).
- Any instrumentation beyond the single `"classify"` span, including whatever
  `auto_instrument=True` adds automatically inside `phoenix.otel.register` itself.
- Validating `INTAKE_LLM` or `PHOENIX_ENDPOINT` beyond the checks described above, or any other
  environment variable.

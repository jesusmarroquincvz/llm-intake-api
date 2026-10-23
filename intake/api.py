"""FastAPI app exposing POST /classify, traced with OpenTelemetry."""
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry import trace

import intake.tracing
from intake.errors import AgentError, ValidationError
from intake.llm import LLM, FakeLLM, GeminiLLM
from intake.orchestrator import classify

intake.tracing.setup_tracing()

app = FastAPI()
_tracer = trace.get_tracer(__name__)


def get_llm() -> LLM:
    """Return FakeLLM() when INTAKE_LLM=fake, otherwise GeminiLLM()."""
    if os.environ.get("INTAKE_LLM") == "fake":
        return FakeLLM()
    return GeminiLLM()


_llm: LLM = get_llm()


def set_llm(llm: LLM) -> None:
    """Replace the LLM used to serve POST /classify."""
    global _llm
    _llm = llm


@app.post("/classify")
async def classify_request(request: Request) -> JSONResponse:
    """Classify the request body's `text` and return the decision, or an error response."""
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": "request body must be valid JSON"})
    text = body.get("text") if isinstance(body, dict) else None
    if not isinstance(text, str):
        return JSONResponse(status_code=422, content={"detail": "'text' must be a string"})

    with _tracer.start_as_current_span("classify") as span:
        span.set_attribute("input.value", text)
        try:
            decision = classify(text, _llm)
        except ValidationError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        except AgentError as e:
            return JSONResponse(status_code=502, content={"detail": str(e)})

    return JSONResponse(status_code=200, content=decision.to_dict())

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


@app.post("/classify/batch")
async def classify_batch_request(request: Request) -> JSONResponse:
    """Classify the request body's `texts` list and return one decision per text, in order."""
    try:
        body = await request.json()
    except ValueError:
        return JSONResponse(status_code=422, content={"detail": "request body must be valid JSON"})

    texts = body.get("texts") if isinstance(body, dict) else None
    if texts is None:
        return JSONResponse(status_code=422, content={"detail": "missing texts field"})
    if not isinstance(texts, list) or not all(isinstance(t, str) for t in texts):
        return JSONResponse(status_code=422, content={"detail": "'texts' must be a list of strings"})
    if len(texts) == 0:
        return JSONResponse(status_code=422, content={"detail": "'texts' must not be empty"})
    if len(texts) > 20:
        return JSONResponse(status_code=422, content={"detail": "'texts' must have at most 20 elements"})

    with _tracer.start_as_current_span("classify_batch") as span:
        span.set_attribute("batch.size", len(texts))
        decisions: list[dict] = []
        for text in texts:
            if not text.strip():
                decisions.append({"error": "text must not be empty"})
                continue
            try:
                decision = classify(text, _llm)
            except (ValidationError, AgentError) as e:
                decisions.append({"error": str(e)})
            else:
                decisions.append(decision.to_dict())

    return JSONResponse(status_code=200, content={"decisions": decisions})

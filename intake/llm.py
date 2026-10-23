"""The one door to a language model. Agents call `complete`; tests use FakeLLM; production uses GeminiLLM."""
import json
import os
import re
from typing import Any, Protocol

from intake.config import ModelConfig
from intake.errors import AgentError


class LLM(Protocol):
    """Anything that can answer a prompt with a JSON object."""

    def complete(self, *, system: str, user: str, config: ModelConfig) -> dict[str, Any]:
        """Return the model's answer parsed as a JSON object."""
        ...


def parse_json(text: str) -> dict[str, Any]:
    """Parse the JSON object in a model answer, tolerating code fences and surrounding prose."""
    match = re.search(r"\{.*\}", text, flags=re.S)
    if not match:
        raise AgentError(f"no JSON object in model answer: {text[:80]!r}")
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError as e:
        raise AgentError(f"invalid JSON in model answer: {e}") from e


class FakeLLM:
    """Deterministic stand-in for tests: answers come from a queue or from a rule function."""

    def __init__(self, answers: list[dict[str, Any]] | None = None, rule=None) -> None:
        self.answers = list(answers or [])
        self.rule = rule
        self.calls: list[dict[str, Any]] = []

    def complete(self, *, system: str, user: str, config: ModelConfig) -> dict[str, Any]:
        self.calls.append({"system": system, "user": user, "config": config})
        if self.rule is not None:
            return self.rule(system, user, config)
        if not self.answers:
            raise AgentError("FakeLLM has no answer queued")
        return self.answers.pop(0)


class GeminiLLM:
    """Gemini on Vertex AI, US region only (the global endpoint is not allowed)."""

    def __init__(self, project: str | None = None, location: str | None = None) -> None:
        from google import genai

        self.client = genai.Client(vertexai=True, project=project or os.environ["GOOGLE_CLOUD_PROJECT"],
                                   location=location or os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1"))

    def complete(self, *, system: str, user: str, config: ModelConfig) -> dict[str, Any]:
        from google.genai import types

        response = self.client.models.generate_content(
            model=config.model, contents=user,
            config=types.GenerateContentConfig(system_instruction=system, response_mime_type="application/json",
                                               thinking_config=types.ThinkingConfig(thinking_level=config.thinking)),
        )
        return parse_json(response.text or "")

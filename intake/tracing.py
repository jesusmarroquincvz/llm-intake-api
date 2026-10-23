"""Wires intake's traces to a Phoenix collector, when one is configured."""
import os

import phoenix.otel


def setup_tracing(project_name: str = "intake-api") -> None:
    """Register a Phoenix OTel tracer provider if PHOENIX_ENDPOINT is set; otherwise do nothing."""
    endpoint = os.environ.get("PHOENIX_ENDPOINT")
    if not endpoint:
        return
    phoenix.otel.register(endpoint=endpoint, project_name=project_name, auto_instrument=True)

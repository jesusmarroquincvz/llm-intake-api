# intake

Request-intake API: a request arrives as free text, an orchestrator runs six classification agents and returns one
structured decision. Built story by story with AI assistance; see `docs/` for the tickets.

    python -m pytest -q
    uvicorn intake.api:app --port 8000

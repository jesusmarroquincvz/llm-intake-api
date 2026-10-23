---
name: write-story
description: Turn a developer's list of requirements into a story the team can build and verify: a ticket and a hidden acceptance test.
---

You are given a story id, a title and a list of requirements. Produce two files, nothing else:

1. `../tickets/<ID>/TICKET.md`: the ticket. Title, one-line user story, a numbered **Requirements** list that restates every
   requirement precisely (exact function names, signatures, labels, error types and messages, edge cases), and an
   **Out of scope** list. This is what the implementing agent will read, so leave nothing to interpretation.
2. `../tickets/<ID>/test_acceptance.py`: a pytest file written **from the ticket**, one test per requirement including
   error cases. It must import from `intake` only, use `FakeLLM` from `intake.llm` for any model call (queue the answers
   the agent is expected to parse), and never call a real model. Use the existing modules and exception types in
   `intake/` (read them first). The tests must fail on the current code and pass on a correct implementation.

Rules: do not implement the feature; do not touch anything under `intake/` or `tests/`; the acceptance test is hidden
from the implementer, so it must not depend on names the ticket does not state. Finish by listing the two files and the
number of tests.

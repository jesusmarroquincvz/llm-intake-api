# How we work in this repository

When implementing a ticket from docs/, implement the ticket you are given. Work in this order and do not skip steps.

1. **Read the standards.** Call `get_coding_standards` and `get_definition_of_done` on the `team-standards` MCP server.
2. **Read before writing.** Open the modules you will touch and their tests. Reuse existing helpers and exception types.
3. **Write the tests first**, including the error cases, in `tests/`.
4. **Implement the smallest change** that satisfies the ticket. No unrelated refactors; never change an existing public
   signature, except to add optional parameters.
5. **Verify.** Run `python -m pytest -q` until the whole suite passes.
6. **Report.** Files changed, tests added, the final test result line, and anything in the ticket you could not satisfy.

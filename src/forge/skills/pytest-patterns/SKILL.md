---
name: pytest-patterns
description: Write tests in the repo's pytest style (fixtures, seeded data, parametrisation, fakes for LLMs/external services, no weakening).
---
# pytest in this codebase

1. Read the repo's `tests/conftest.py` first: reuse its fixtures (app, client, sessions, auth headers,
   seeded rows, fake LLM registries). Add new fixtures there only if several tests need them.
2. One behaviour per test; names say what is checked (`test_count_returns_404_for_unknown_policy`).
3. Use `pytest.mark.parametrize` for input variations instead of copy-pasted tests.
4. External services (LLMs, HTTP, email) are faked with the repo's existing pattern; never real calls.
5. Assert on outcomes the user cares about (status code, JSON body, rows written), not implementation details.
6. Never weaken, skip or xfail an existing test to make a change pass; fix the code (the reviewer checks).
7. Run the new tests with `python -m pytest <file>`, then the tests of the touched modules, then the full suite.

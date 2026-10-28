---
name: pytest-patterns
description: Use when you write or change tests in a pytest repository: reuse its fixtures, parametrise, fake external services, never weaken a test
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

## Gotchas
- A test that passes alone can fail in the suite through shared state: use `tmp_path` and fresh fixtures, never module globals.
- Seen in the benchmarks: the model's own tests are left out when hidden tests score the code, so the code must pass the *spec*, not only its own tests.
- (2026-10-29, t20_migration_script) A function that takes a file path is called with a pathlib.Path as often as with a str: call it with both in your tests and convert once at the top (path = Path(path)). In t20 every hidden test that passed a Path crashed on path + '.bak'.

# deps

The Dependencies section (D-238): finds the libraries a project uses (`scan.py`: requirements, pyproject, poetry/uv/Pipfile locks,
package.json + package-lock, what is installed in the project's environment) and checks them against two vulnerability sources
(`osv.py`: OSV.dev; `audit.py`: pip-audit, optional extra), merging what they report so each vulnerability says which source found it
(`check.py`). Scanning only reads files; the check sends library names and versions to the internet and runs only when the user asks.

- **Depends on:** (none) (httpx and pydantic only)
- **Invariants:** nothing is executed from the project; the check never runs on its own; a failing source becomes a status line, never an exception; only names and versions are sent.
- **Tests:** test_deps.py, test_web_deps_e2e.py
- **Decisions:** docs/DECISIONS.md (D-238); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.

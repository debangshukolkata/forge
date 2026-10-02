## What and why

## Checks
- [ ] `ruff check .` and `ruff format --check .`
- [ ] `mypy`
- [ ] Tests for the touched module, plus `tests/test_module_boundaries.py`
- [ ] Full suite for broad or risky changes: `pytest -n 12 --dist loadfile`
- [ ] `MODULE.md` and docs/DECISIONS.md updated if a module boundary or a decision changed

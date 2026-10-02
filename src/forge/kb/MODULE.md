# kb

> **Status: Knowledge Base builder and search. RETIRING (D-156): the repo is explored on demand instead.**

Knowledge Base of a repository: deterministic extractors, narrative documents, BM25 search, store.

- **Depends on:** llm, safety, workspace
- **Invariants:** Deterministic first, LLM second. Mode A only.
- **Tests:** test_kb.py, test_live_kb.py
- **Decisions:** docs/DECISIONS.md (search the module's feature names); layering is enforced by tests/test_module_boundaries.py.

Keep this file in step with the code: the `Depends on` line is checked against the real imports.

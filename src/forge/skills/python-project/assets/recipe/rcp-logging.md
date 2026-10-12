---
id: rcp-logging
type: recipe
title: "Logging, not print"
summary: "One logger per module, configure once at the entry point, structured context, no secrets."
moods: [robust]
products: [services, cli]
tags: [logging, observability]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Logging, not print

Rules: `log = logging.getLogger(__name__)` at the top of each module; call `logging.basicConfig(...)` (or dictConfig) once,
in `main()`, never in library code; use lazy formatting (`log.info("loaded %s rows", n)`), not f-strings; `log.exception`
inside `except` to keep the traceback; never log passwords, tokens or whole request bodies; `print` is for the program's
real output only.

```python
# runnable
import io
import logging

log = logging.getLogger("inventory.sync")


def configure(stream: io.StringIO, level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(stream)
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)


def sync(rows: list[int]) -> int:
    log.info("syncing %d rows", len(rows))
    try:
        return sum(10 // value for value in rows)
    except ZeroDivisionError:
        log.exception("row with value 0 cannot be synced")
        return -1


buffer = io.StringIO()
configure(buffer)
assert sync([1, 2]) == 15
assert sync([0]) == -1
text = buffer.getvalue()
assert "syncing 2 rows" in text and "ZeroDivisionError" in text
```

Levels: DEBUG for developer detail, INFO for normal milestones, WARNING for something odd that was handled, ERROR for a
failed operation, CRITICAL when the program cannot go on. Tests can check logs with pytest's `caplog` fixture.

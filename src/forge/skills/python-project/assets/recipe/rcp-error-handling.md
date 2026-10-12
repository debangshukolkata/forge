---
id: rcp-error-handling
type: recipe
title: Error handling that helps
summary: "Specific exception classes, raise from, no swallowed errors, cleanup with context managers."
moods: [robust]
products: [any python code]
tags: [errors, exceptions, reliability]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## Error handling that helps

Rules: raise the most specific exception you can; catch only what you can handle at that level; never `except:` or
`except Exception: pass`; keep the original cause with `raise ... from error`; clean up with `with`/`finally`; messages say
what happened, with the value, and what to do.

```python
# runnable
class ConfigError(Exception):
    """The program's own base class: callers can catch all of its failures at once."""


class MissingSetting(ConfigError):
    def __init__(self, name: str) -> None:
        super().__init__(f"setting {name!r} is not set; add it to the .env file")
        self.name = name


def read_port(settings: dict[str, str]) -> int:
    try:
        raw = settings["PORT"]
    except KeyError:
        raise MissingSetting("PORT") from None  # the KeyError adds nothing for the reader
    try:
        port = int(raw)
    except ValueError as error:
        raise ConfigError(f"PORT must be a whole number, got {raw!r}") from error
    if not 0 < port < 65536:
        raise ConfigError(f"PORT must be between 1 and 65535, got {port}")
    return port


assert read_port({"PORT": "8080"}) == 8080
for bad in ({}, {"PORT": "abc"}, {"PORT": "70000"}):
    try:
        read_port(bad)
    except ConfigError as error:
        assert str(error)
    else:
        raise AssertionError("expected a ConfigError")
```

At the edge of the program (the CLI `main`, the HTTP handler) catch the base class once, log it and turn it into an exit
code or a status code; inside, let exceptions travel. Do not return `None` or `-1` to signal failure when an exception says
it better. Use `contextlib.suppress(FileNotFoundError)` only for the one expected case.

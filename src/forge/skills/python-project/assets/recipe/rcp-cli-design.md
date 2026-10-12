---
id: rcp-cli-design
type: recipe
title: A command line tool people can use
summary: "Arguments, subcommands, exit codes, stdin and stdout, errors to stderr; testable main()."
moods: [clean, robust]
products: [cli, command line, script]
tags: [argparse, cli, exit code, subcommands]
density: any
dependencies: []
licence: original
source: authored for DebCraft (python recipes, 2026-10-13)
tested: runnable examples are executed by tests/test_python_recipes.py
---

## A command line tool people can use

Rules: `main(argv=None) -> int` holds the logic and returns the exit code (0 success, 1 failure of the task, 2 bad usage);
results go to stdout, messages and errors to stderr; read from stdin when no file is given and `-` means stdin; a
`--json` flag for machine output; `--help` text that says what each option does; no traceback for expected problems.

```python
# runnable
import argparse
import io
import sys
from collections.abc import Sequence
from pathlib import Path


def main(argv: Sequence[str] | None = None, stdin: io.TextIOBase | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tool")
    sub = parser.add_subparsers(dest="command", required=True)
    count = sub.add_parser("count", help="count lines in a file or stdin")
    count.add_argument("file", nargs="?", default="-")
    sub.add_parser("version", help="print the version")
    args = parser.parse_args(argv)
    if args.command == "version":
        print("1.0")
        return 0
    try:
        text = (
            (stdin or sys.stdin).read() if args.file == "-" else Path(args.file).read_text(encoding="utf-8")
        )
    except OSError as error:
        print(f"tool: cannot read {args.file}: {error.strerror}", file=sys.stderr)
        return 1
    print(len(text.splitlines()))
    return 0


assert main(["count", "-"], stdin=io.StringIO("a\nb\n")) == 0
assert main(["count", "no-such-file.txt"]) == 1
try:
    main(["bogus"])
except SystemExit as stop:
    assert stop.code == 2
```

Typer or Click are fine when a project already uses them; the structure (a `main` that returns a code, tested directly) stays
the same. Make the entry point a console script in `pyproject.toml` (`[project.scripts]`).

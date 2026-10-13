"""Which shell commands may run side by side (TODO X3, D-271).

Only checkers and readers that do not change the project: linters, type checkers, one test run, a TypeScript check,
simple file listing and reading. Anything else (installs, builds, servers, git, redirects, chained commands) runs alone,
in order, as before. Each command still goes through the permission gate and the sandbox on its own."""

from __future__ import annotations

import re

MAX_PARALLEL_COMMANDS = 4
# Characters that chain, redirect or substitute: such a command can do more than its first word says.
UNSAFE_SYNTAX = re.compile(r"[;&|<>`$()]|\n")
CHECKERS = {"ruff", "mypy", "pyright", "flake8", "pylint", "bandit", "pip-audit", "eslint", "tsc"}
READERS = {
    "ls",
    "dir",
    "cat",
    "type",
    "head",
    "tail",
    "grep",
    "rg",
    "wc",
    "get-content",
    "get-childitem",
    "select-string",
}
TEST_RUNNERS = {"pytest"}
FORMATTERS_WITH_CHECK_ONLY = {"black", "prettier", "isort"}


def _words(command: str) -> list[str]:
    return command.strip().split()


def _program(words: list[str]) -> tuple[str, list[str]]:
    """The program name and its arguments, looking through `python -m x` and `npx x`."""
    if len(words) >= 3 and words[0].lower() in {"python", "python3", "py"} and words[1] == "-m":
        return words[2].lower(), words[3:]
    if len(words) >= 2 and words[0].lower() == "npx":
        rest = [w for w in words[1:] if w not in {"--no-install", "-y", "--yes"}]
        return (rest[0].lower(), rest[1:]) if rest else ("", [])
    return (words[0].lower(), words[1:]) if words else ("", [])


def is_test_command(command: str) -> bool:
    words = _words(command)
    return bool(words) and _program(words)[0] in TEST_RUNNERS


def is_parallel_safe_command(command: str) -> bool:
    """True when the command only checks or reads (see the module note). Conservative on purpose."""
    if not command.strip() or UNSAFE_SYNTAX.search(command):
        return False
    program, arguments = _program(_words(command))
    if program == "ruff" and arguments[:1] == ["format"]:
        return "--check" in arguments or "--diff" in arguments
    if program in CHECKERS or program in READERS or program in TEST_RUNNERS:
        # `ruff check --fix` and `eslint --fix` rewrite files
        return not any(a in {"--fix", "--write", "-w", "--unsafe-fixes"} for a in arguments)
    if program in FORMATTERS_WITH_CHECK_ONLY:
        return "--check" in arguments or "--diff" in arguments
    return False

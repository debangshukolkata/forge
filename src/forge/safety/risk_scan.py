"""Risks the model should name in its final reply when the code it worked with has them (D-410).

The approach challenge c09 (2026-10-15) gave the model a small task in a file that unpickles its settings and holds a committed token: the prompt already said to report such flaws
and the final reply did not mention them. A prompt line is not enough, so a short deterministic scan of the source files the model read finds the usual suspects and, once, asks for them
to be named before the turn ends. It is a notice, never a refusal, and it finds patterns, not proof: the reply says what could go wrong and leaves the code alone."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

SOURCE_SUFFIXES = (".py", ".js", ".jsx", ".ts", ".tsx", ".php", ".rb", ".java", ".cs", ".go")
PLACEHOLDER = re.compile(
    r"(?i)x{3,}|changeme|example|your[-_ ]|<[^>]+>|dummy|placeholder|test[-_]?key|\*{3,}"
)
MAX_FINDINGS = 6

# (kind, pattern, what can go wrong, what to do)
RULES: tuple[tuple[str, re.Pattern[str], str, str], ...] = (
    (
        "unsafe deserialisation",
        re.compile(r"\b(pickle|cPickle|marshal|dill)\.loads?\(|\byaml\.load\((?![^)]*Loader)"),
        "loading data with pickle, marshal or yaml.load can run any code the data contains",
        "use json, or yaml.safe_load",
    ),
    (
        "eval or exec",
        re.compile(r"(?<![\w.])(eval|exec)\("),
        "evaluating a string runs whatever it says",
        "parse the value instead",
    ),
    (
        "SQL built from strings",
        re.compile(
            r"""(?i)\bf["'].*\b(select|insert|update|delete)\b.*\{|["']\s*(select|insert|update|delete)\b[^"'\n]*["']\s*(\+|%)\s*\w"""
        ),
        "a value in the SQL text can change the query (SQL injection)",
        "pass values as bound parameters",
    ),
    (
        "hard-coded secret",
        re.compile(
            r"""(?i)(api[_-]?key|secret|token|password|passwd)\w*\s*[:=]\s*["']([A-Za-z0-9_\-/+=.]{12,})["']"""
        ),
        "a secret in the source ends up in the repository history and every copy of it",
        "read it from the environment or a secret store and rotate it",
    ),
    (
        "shell command from a string",
        re.compile(r"shell\s*=\s*True|\bos\.system\("),
        "a value in the command line can run other commands",
        "pass an argument list without a shell",
    ),
    (
        "certificate check turned off",
        re.compile(r"verify\s*=\s*False|rejectUnauthorized\s*:\s*false"),
        "the connection can be read or changed by anyone on the path",
        "trust the company certificate instead of switching the check off",
    ),
)


@dataclass(frozen=True)
class Risk:
    path: str
    line: int
    kind: str
    what: str
    advice: str

    def sentence(self) -> str:
        return f"{self.path}:{self.line}: {self.kind}: {self.what} ({self.advice})"


def scan_text(path: str, text: str) -> list[Risk]:
    found: list[Risk] = []
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith(("#", "//", "*")):
            continue
        for kind, pattern, what, advice in RULES:
            match = pattern.search(line)
            if match is None:
                continue
            if kind == "hard-coded secret" and PLACEHOLDER.search(match.group(2)):
                continue
            found.append(Risk(path, number, kind, what, advice))
            break
    return found


def scannable(path: str) -> bool:
    name = Path(path.replace("\\", "/")).name.lower()
    normalised = f"/{path.replace(chr(92), '/').lower()}"
    if not name.endswith(SOURCE_SUFFIXES):
        return False
    return not (
        name.startswith("test_")
        or "_test." in name
        or ".test." in name
        or ".spec." in name
        or "/tests/" in normalised
        or "conftest" in name
    )


def mentioned(risk: Risk, reply: str) -> bool:
    """The reply names this kind of risk: good enough to leave the model alone."""
    lowered = reply.lower()
    keywords = {
        "unsafe deserialisation": ("pickle", "deserial", "yaml.load", "marshal"),
        "eval or exec": ("eval", "exec("),
        "SQL built from strings": (
            "sql injection",
            "injectable",
            "injection",
            "string-built",
            "bound parameter",
        ),
        "hard-coded secret": ("secret", "token", "hard-coded", "hardcoded", "credential"),
        "shell command from a string": ("shell=true", "os.system", "shell injection"),
        "certificate check turned off": ("verify=false", "certificate check", "tls"),
    }[risk.kind]
    return any(k in lowered for k in keywords)

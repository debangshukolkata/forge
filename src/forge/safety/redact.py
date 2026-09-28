"""Secret redaction (DECISIONS D-016).

Two layers:
1. Exact values: every secret Forge loads is registered here and masked wherever it appears.
2. Patterns: secret-shaped text (JWTs, bearer tokens, passwords in URLs, key=value assignments)
   is masked even when Forge never saw the value — e.g. credentials printed in a traceback.

Redaction runs on everything that leaves the engine: LLM requests, events, transcripts, logs.
"""

from __future__ import annotations

import re
import threading
from collections.abc import Callable
from typing import Any

MIN_REGISTERED_LENGTH = 6

_PATTERNS: list[tuple[str, re.Pattern[str], int]] = [
    # (label, pattern, group to mask — 0 means the whole match)
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), 0),
    ("bearer", re.compile(r"(?i)\bbearer\s+([A-Za-z0-9._~+/=-]{16,})"), 1),
    ("url-password", re.compile(r"://[^:/\s@]+:([^@\s]+)@"), 1),
    # Well-known token shapes (GitHub, OpenAI-style, Slack, Google, AWS access key id).
    (
        "token",
        re.compile(
            r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}"
            r"|xox[abprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_-]{35}|AKIA[0-9A-Z]{16})\b"
        ),
        0,
    ),
    ("sas-signature", re.compile(r"[?&]sig=([^&\s\"']{10,})"), 1),
    (
        "secure-string",
        re.compile(r"(?i)ConvertTo-SecureString\s+(?:-String\s+)?[\"']([^\"']{4,})[\"']"),
        1,
    ),
    (
        # KEY=value, "key": "value" (JSON/YAML), header "api-key: value", "Pwd=...;" in connection strings.
        # Plain numbers are left alone so "max_tokens: 128000" and token counts stay readable.
        "assignment",
        re.compile(
            r"(?i)\b[A-Z0-9_-]*(?:PASSWORD|PASSWD|PWD|SECRET|API[_-]?KEY|ACCESS[_-]?KEY|ACCOUNT[_-]?KEY"
            r"|SUBSCRIPTION[_-]?KEY|TOKEN)[A-Z0-9_-]*[\"']?\s*[=:]\s*[\"']?(?![\d.]+\b)([^\s\"',;]{6,})"
        ),
        1,
    ),
    (
        "private-key",
        re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
        0,
    ),
]


class Redactor:
    def __init__(self) -> None:
        self._values: dict[str, str] = {}
        self._lock = threading.Lock()

    def register(self, value: str | None, label: str) -> None:
        """Remember a secret value. Short values are ignored: masking 'admin' everywhere would
        destroy ordinary text, and short values are caught by the pattern layer instead."""
        if value and len(value) >= MIN_REGISTERED_LENGTH:
            with self._lock:
                self._values[value] = label

    def registered_labels(self) -> list[str]:
        with self._lock:
            return sorted(set(self._values.values()))

    def redact(self, text: str) -> str:
        if not text:
            return text
        with self._lock:
            # Longest first, so a secret that contains another is masked whole.
            values = sorted(self._values.items(), key=lambda item: len(item[0]), reverse=True)
        for value, label in values:
            if value in text:
                text = text.replace(value, f"[REDACTED:{label}]")
        for label, pattern, group in _PATTERNS:
            text = pattern.sub(_masker(label, group), text)
        return text

    def redact_data(self, data: Any) -> Any:
        """Redacts every string inside nested dicts/lists (event payloads, request bodies)."""
        if isinstance(data, str):
            return self.redact(data)
        if isinstance(data, dict):
            return {key: self.redact_data(value) for key, value in data.items()}
        if isinstance(data, list):
            return [self.redact_data(item) for item in data]
        if isinstance(data, tuple):
            return tuple(self.redact_data(item) for item in data)
        return data


def _masker(label: str, group: int) -> Callable[[re.Match[str]], str]:
    def mask(match: re.Match[str]) -> str:
        return _mask(match, label, group)

    return mask


def _mask(match: re.Match[str], label: str, group: int) -> str:
    if group == 0:
        return f"[REDACTED:{label}]"
    whole = match.group(0)
    secret = match.group(group)
    if secret.startswith("[REDACTED"):
        return whole
    start = match.start(group) - match.start(0)
    if label == "assignment" and _is_code_expression(whole[:start], secret):
        return whole
    return whole[:start] + f"[REDACTED:{label}]" + whole[start + len(secret) :]


# `image_token = extract(q)`, `token = response.token`, `password = None`: Python code, not a secret. Masking
# them hid code from the model and the reviewer (seen live: a false "blocking" finding). Only unquoted values
# after a lower-case, code-style `name = ` qualify, so .env lines (`API_KEY=value`) are always masked.
_CODE_LEFT = re.compile(r"^[a-z][a-z0-9_]*\s+=\s+$|^self\.[a-z_]\w*\s+=\s+$")
_CODE_VALUE = re.compile(
    r"^(?:[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*[(\[]|[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+$|None$|True$|False$)"
)
# Keyword arguments (`api_key=config.chat.api_key`, `token=get_token()`): no spaces around `=`, so the value
# must look unmistakably like code — lower-case snake_case attribute access or a call.
_KEYWORD_LEFT = re.compile(r"^[a-z][a-z0-9_]*=$")
_KEYWORD_VALUE = re.compile(r"^(?:[a-z_]+(?:\.[a-z_]+)+$|[a-z_][a-z_.]*\()")


def _is_code_expression(left: str, value: str) -> bool:
    if _CODE_LEFT.match(left) and _CODE_VALUE.match(value):
        return True
    if left.rstrip("= ").lower() == value.lower():  # `api_key=api_key`: a parameter passed through
        return True
    return bool(_KEYWORD_LEFT.match(left) and _KEYWORD_VALUE.match(value))


# Process-wide instance: secrets are registered once at startup and apply everywhere.
default_redactor = Redactor()

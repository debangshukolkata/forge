"""Log anonymiser: strict, deterministic pseudonyms for emails, IPs, users and secrets."""

from __future__ import annotations

import hashlib
import re
from typing import Callable

ALREADY_DONE = re.compile(r"<(?:REDACTED|(?:IP|EMAIL|USER):[0-9a-f]{8})>")
VALUE = r"""(?P<value>"[^"\r\n]*"|'[^'\r\n]*'|[^\s&,;"']+)"""
SEPARATOR = r"""(?P<end_quote>")?(?P<sep>[ \t]*[=:][ \t]*)"""
SECRET_PAIR = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<key>[A-Za-z0-9_-]*?(?:token|password|passwd|secret|api[_-]?key))"
    + SEPARATOR
    + VALUE,
    re.IGNORECASE,
)
BEARER = re.compile(r"\b(?P<word>bearer)(?P<gap>[ \t]+)(?P<credential>[A-Za-z0-9\-._~+/=]{8,})", re.IGNORECASE)
USER_PAIR = re.compile(
    r"(?<![A-Za-z0-9_-])(?P<key>user|username|user_id)" + SEPARATOR + VALUE,
    re.IGNORECASE,
)
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}")
OCTET = r"(?:25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)"
IPV4 = re.compile(rf"(?<![\w.]){OCTET}(?:\.{OCTET}){{3}}(?!\w|\.\d)")


def pseudonym(kind: str, value: str, salt: str) -> str:
    digest = hashlib.sha256(f"{salt}|{kind}|{value}".encode()).hexdigest()[:8]
    return f"<{kind.upper()}:{digest}>"


def _split_quotes(value: str) -> tuple[str, str, str]:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[0], value[1:-1], value[0]
    return "", value, ""


def _pair_replacer(counts: dict[str, int], count_as: str, make: Callable[[str], str]) -> Callable[[re.Match[str]], str]:
    def replace(match: re.Match[str]) -> str:
        opening, inner, closing = _split_quotes(match.group("value"))
        if not inner or ALREADY_DONE.fullmatch(inner):
            return match.group(0)
        counts[count_as] += 1
        return (
            f"{match.group('key')}{match.group('end_quote') or ''}{match.group('sep')}"
            f"{opening}{make(inner)}{closing}"
        )

    return replace


def anonymise_with_report(text: str, salt: str = "") -> tuple[str, dict[str, int]]:
    counts = {"ip": 0, "email": 0, "user": 0, "secret": 0}

    def bearer(match: re.Match[str]) -> str:
        if ALREADY_DONE.fullmatch(match.group("credential")):
            return match.group(0)
        counts["secret"] += 1
        return f"{match.group('word')}{match.group('gap')}<REDACTED>"

    def email(match: re.Match[str]) -> str:
        counts["email"] += 1
        return pseudonym("email", match.group(0).lower(), salt)

    def ip(match: re.Match[str]) -> str:
        counts["ip"] += 1
        return pseudonym("ip", match.group(0), salt)

    text = SECRET_PAIR.sub(_pair_replacer(counts, "secret", lambda inner: "<REDACTED>"), text)
    text = BEARER.sub(bearer, text)
    text = USER_PAIR.sub(_pair_replacer(counts, "user", lambda inner: pseudonym("user", inner, salt)), text)
    text = EMAIL.sub(email, text)
    text = IPV4.sub(ip, text)
    return text, counts


def anonymise_text(text: str, salt: str = "") -> str:
    return anonymise_with_report(text, salt)[0]


def anonymise_line(line: str, salt: str = "") -> str:
    return anonymise_text(line, salt)

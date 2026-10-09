"""Sorts a license name into a plain risk category (D-239). Informational only, not legal advice: the
category says how much a license asks of whoever ships the code, not whether using the library is allowed."""

from __future__ import annotations

import re
from typing import Literal

Category = Literal["permissive", "weak_copyleft", "strong_copyleft", "unknown"]
RISK_ORDER: list[Category] = ["permissive", "weak_copyleft", "strong_copyleft", "unknown"]
LABELS: dict[Category, str] = {
    "permissive": "Permissive",
    "weak_copyleft": "Weak copyleft",
    "strong_copyleft": "Strong copyleft",
    "unknown": "Unknown",
}
_NOT_A_LICENSE = {
    "",
    "UNKNOWN",
    "NONE",
    "NON-STANDARD",
    "NOASSERTION",
    "SEE LICENSE FILE",
    "SEE LICENSE IN LICENSE",
}
# Matched against the upper-cased text; the order matters (LGPL and AGPL before GPL).
_RULES: list[tuple[re.Pattern[str], Category]] = [
    (re.compile(r"\bLGPL|LESSER GENERAL PUBLIC|LIBRARY GENERAL PUBLIC"), "weak_copyleft"),
    (re.compile(r"\bAGPL|AFFERO|\bSSPL|SERVER SIDE PUBLIC"), "strong_copyleft"),
    (re.compile(r"\bGPL|GENERAL PUBLIC LICEN|\bCPAL|\bOSL-|\bRPL"), "strong_copyleft"),
    (
        re.compile(r"\bMPL|MOZILLA|\bEPL|ECLIPSE PUBLIC|\bCDDL|\bCPL-|COMMON PUBLIC|\bEUPL|\bCECILL"),
        "weak_copyleft",
    ),
    (
        re.compile(
            r"\bMIT\b|MIT-0|\bBSD|APACHE|\bISC\b|\bPSF|PYTHON SOFTWARE|PYTHON-2|\bZLIB|UNLICENSE|\bCC0|\b0BSD"
            r"|\bBSL-1|BOOST|\bWTFPL|\bHPND|\bX11|CC-BY-[0-9]|ARTISTIC|\bBLUEOAK|PUBLIC DOMAIN|\bNCSA"
            r"|\bLIBPNG"
        ),
        "permissive",
    ),
]


def _single(term: str) -> Category:
    text = term.strip().upper()
    if text in _NOT_A_LICENSE:
        return "unknown"
    for pattern, category in _RULES:
        if pattern.search(text):
            return category
    return "unknown"


def classify(license_text: str) -> Category:
    """SPDX expressions are understood: `A OR B` is the easier of the two (the user may pick it), `A AND B`
    the stricter; a `WITH` exception is ignored."""
    text = re.sub(r"[()]", " ", license_text.strip())
    if not text:
        return "unknown"
    ors = re.split(r"\s+OR\s+", text, flags=re.IGNORECASE)
    ranks = []
    for alternative in ors:
        parts = [
            _single(re.split(r"\s+WITH\s+", p, flags=re.IGNORECASE)[0])
            for p in re.split(r"\s+AND\s+", alternative, flags=re.IGNORECASE)
        ]
        ranks.append(max(RISK_ORDER.index(p) for p in parts))
    # Unknown (the last rank) must not look better than a known option: pick the easiest known alternative.
    known = [r for r in ranks if RISK_ORDER[r] != "unknown"]
    return RISK_ORDER[min(known)] if known else "unknown"

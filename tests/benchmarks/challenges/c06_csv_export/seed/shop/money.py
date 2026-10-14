"""Money is stored in cents; this is the one place that formats it."""

from __future__ import annotations


def format_money(cents: int, currency: str = "EUR") -> str:
    """12345 -> "123.45 EUR" (negative amounts keep their sign)."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d} {currency}"

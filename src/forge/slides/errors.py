"""Errors of the slides module, shared so builders and the chart builder can raise the same kind (D-284)."""

from __future__ import annotations

from forge.errors import ForgeError


class BuildError(ForgeError):
    """A slide cannot be built; the message names it."""

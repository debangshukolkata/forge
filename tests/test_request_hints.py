"""D-527 (TODO BV1): a request for several designs of one page gets a note to build them with build_variants."""

from __future__ import annotations

import pytest

from forge.agent.hints import variants_hint

ASKS_FOR_DESIGNS = [
    "Give me three different design options for the homepage of a small bakery so I can choose one.",
    "Can you make 2 versions of the landing page, one dark and one light?",
    "I'd like several alternative layouts for the pricing page",
    "Show me a few design directions for our dashboard screen",
    "three takes on the hero section please",
]
OTHER_REQUESTS = [
    "Add a validation rule to the claims form, test first",
    "Fix the two layout bugs on the settings page",
    "Write three tests for the login page",
    "Add two API endpoints for orders",
    "Describe three design options for a bakery homepage in words, do not build anything",
    "Make the homepage look better",
    "Support two versions of the API",
]


@pytest.mark.parametrize("request_text", ASKS_FOR_DESIGNS)
def test_a_request_for_several_designs_gets_the_note(request_text: str) -> None:
    assert "build_variants" in variants_hint(request_text)


@pytest.mark.parametrize("request_text", OTHER_REQUESTS)
def test_other_requests_get_nothing(request_text: str) -> None:
    assert variants_hint(request_text) == ""


def test_a_security_review_gets_the_function_by_function_note() -> None:
    from forge.agent.hints import security_hint

    assert "hostile test" in security_hint("Review `webapp.py` for security problems and fix them.")
    assert "hostile test" in security_hint("Harden the upload endpoint against path traversal and injection")
    assert security_hint("Add a CSV export to the orders page") == ""
    assert security_hint("Fix the typo in the README") == ""

"""Per-request notes put in front of the model, found by plain pattern matching (no model call, nothing leaves the machine).

The model follows a note beside the request far more often than a rule in the system prompt (D-518: 1 in 23 runs used the catalogue
from the prompt rule, 23 in 24 with a note). `variants_hint` (TODO BV1, D-527): asked for "three design options for the homepage", the model
wrote three directions as text and used no tool in 3 runs of 3, although the system prompt says to call build_variants.
"""

from __future__ import annotations

import re

COUNT = r"(two|three|four|five|several|multiple|a few|a couple of|[2-5])"
CHOICES = (
    r"(options?|variants?|versions?|alternatives?|designs?|directions?|concepts?|mock-?ups?|takes|looks)"
)
SUBJECT = r"(design|homepage|home page|landing|page|screen|layout|look|website|site|ui|dashboard|hero|interface|theme|style)"
SEVERAL_DESIGNS = re.compile(rf"\b{COUNT}\b[\w\s,'-]{{0,40}}?\b{CHOICES}\b", re.IGNORECASE)
DESIGN_SUBJECT = re.compile(rf"\b{SUBJECT}s?\b", re.IGNORECASE)
IN_WORDS = re.compile(
    r"\b(describe|in words|in text|just (the )?ideas|brainstorm|suggest(ions)?|list|outline|explain|without building)\b",
    re.IGNORECASE,
)
HINT_REQUEST_CHARS = 400

VARIANTS_NOTE = (
    "This request asks for several designs of one thing. Deliver them as built pages the user can open and compare, not as descriptions in "
    "text: call build_variants with the shared requirement once and, per variant, a name, its own folder (designs/design-a, designs/design-b, "
    "...) and a direction that differs on palette, type and layout. The ui-design-quality skill's recipes/skill-variants.md says how to check "
    "and compare them afterwards. A question first is fine when a decisive fact is missing (the business name, the place). Answer in words only "
    "if the user asked for ideas or descriptions rather than designs."
)


def variants_hint(request: str) -> str:
    """The note for a request that asks for several designs of a page or screen, or "" for any other request."""
    start = request[:HINT_REQUEST_CHARS]
    if not SEVERAL_DESIGNS.search(start) or not DESIGN_SUBJECT.search(start) or IN_WORDS.search(start):
        return ""
    return VARIANTS_NOTE


SECURITY_REQUEST = re.compile(
    r"\b(security|secure|vulnerab\w*|attacker|exploit\w*|injection|xss|ssrf|csrf|hardening|harden|pentest|threat model)\b",
    re.IGNORECASE,
)
SECURITY_NOTE = (
    "This request is a security review or fix. Work function by function, not file by file: (1) list every function that takes outside "
    "input; (2) for each, name the sinks it reaches (HTML, link, redirect, file path, archive, SQL, shell, deserialiser, evaluator, outgoing "
    "request, header, log line, token); (3) write one hostile test per function and sink, see it fail, then fix at the root by parsing and "
    "allowing a short list, never by blocking example strings; (4) you are done only when every pair has a passing hostile test. "
    "add_asset rcp-security gives tested checks for links, redirects, signed cookies, paths and SQL; rcp-threat-model-review gives the method."
)


def security_hint(request: str) -> str:
    """The note for a security review or fix (D-536): in run c1-t15-23 neither security task opened the recipes the catalogue hint named,
    and both stopped when the existing tests passed (t22 70/93, t23 47/53)."""
    return SECURITY_NOTE if SECURITY_REQUEST.search(request[:HINT_REQUEST_CHARS]) else ""

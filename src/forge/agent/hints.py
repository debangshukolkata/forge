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


READ_ONLY_DATABASE_TOOLS = frozenset(
    {"read_background", "monitor", "run_command", "python_run", "http_request", "start_background"}
)
DATABASE_REFUSED_WRITE = re.compile(
    r"permission denied for (table|relation|schema|sequence)|InsufficientPrivilege|"
    r"cannot execute (insert|update|delete|create|alter|drop|truncate)[^\n]{0,40}read-only|"
    r"read-only transaction|must be owner of",
    re.IGNORECASE,
)
READ_ONLY_DATABASE_NOTE = (
    "[note: the database refused a write. The application is connected to a database DebCraft may only read. Do not "
    "change the application to ignore or work around this error: copy the tables it needs into your scratch schema "
    "(db_copy_table, from the development database), point the application's settings at it (use_scratch_database), "
    "stop the application and start it again. Its writes then land in your copy.]"
)


def read_only_database_note(tool: str, content: str, already_on_scratch: bool, given: int) -> str:
    """D-600: output of a command or call that shows the database refused a write, while the application is not yet
    pointed at the scratch schema. In two live runs the model patched the application to swallow the error and ran it on the
    real development data instead of using the scratch tools. At most twice per session (`given` counts the notes so far)."""
    if already_on_scratch or given >= 2 or tool not in READ_ONLY_DATABASE_TOOLS:
        return ""
    return READ_ONLY_DATABASE_NOTE if DATABASE_REFUSED_WRITE.search(content) else ""


NAME_RESOLUTION_FAILED = re.compile(
    r"getaddrinfo failed|Name or service not known|Temporary failure in name resolution|"
    r"nodename nor servname provided|No such host is known|could not resolve host|NameResolutionError|"
    r"socket\.gaierror|\[Errno 11001\]",
    re.IGNORECASE,
)
NAME_RESOLUTION_NOTE = (
    "[note: a host name did not resolve from this machine. For an internal or company host that is usually the VPN or "
    "the company DNS being off, not a fault in the code. Say that to the user first, in one sentence (check the VPN, "
    "`nslookup <host>`), and ask them to tell you when the network is back. Do not hand them the call to run by hand "
    "and do not work around it in the code.]"
)


def name_resolution_note(tool: str, content: str, given: int) -> str:
    """D-601: output that shows a host name did not resolve. On the office laptop a run that had worked the day before
    failed in `fetch_from_infisical` on `nonprod.wisdomnext.eng`; the model asked the user a five-step card and never
    named the likely cause. At most twice per session; only for tools that run or call something."""
    if given >= 2 or tool not in READ_ONLY_DATABASE_TOOLS:
        return ""
    return NAME_RESOLUTION_NOTE if NAME_RESOLUTION_FAILED.search(content) else ""

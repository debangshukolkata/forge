"""The same kind of error again after fixes: name the class, not only the instance (D-673, office 2026-11-27).

In the dashboard run the generated agent failed four times on the playground with SyntaxErrors that all came from one
cause: HTML and JavaScript written inside Python strings. DebCraft fixed each instance and never named the class, so
the next change brought the next one. When an error kind comes back after two code changes, the model is asked to
name the common cause and a design in its own code that makes the whole class impossible.

Changes to systems DebCraft does not own (another team's service, the platform a job runs on) are proposed only
when the user asked for suggestions (the user's rule, 2026-11-27). Otherwise the model stays within the project."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# Tools whose output is what something did when it ran, not the text of a file (reading `except ValueError:` in a
# source file is not an error).
RUNNING_TOOLS = frozenset(
    {
        "read_background",
        "monitor",
        "run_command",
        "python_run",
        "http_request",
        "start_background",
        "scratch_exec",
    }
)
# `SyntaxError: unterminated string literal`, also inside a JSON answer (`"error": "TypeError: ..."`).
ERROR_KIND = re.compile(r"(?:^|[\"'\s(\[:=])((?:[A-Z][a-z0-9]+)+(?:Error|Exception))(?=: \S)", re.MULTILINE)
# Kinds that say only that something failed, not what: they repeat for unrelated reasons.
TOO_GENERAL = frozenset(
    {"Exception", "RuntimeError", "AssertionError", "Error", "HTTPError", "CalledProcessError"}
)
ROUNDS = 3  # seen after this many different code states: the first one and two fixes

SUGGESTION_REQUEST = re.compile(
    r"\b(suggest\w*|recommend\w*|advi[cs]e|ideas?|alternatives?|"
    r"what (?:would|should|can|could) (?:you|we|i) (?:do|change|ask)|"
    r"how (?:can|could|should|do) (?:we|i|you) (?:avoid|prevent|stop|make sure|get rid of|improve)|"
    r"(?:a|any) better way|ways? to (?:avoid|prevent))\b",
    re.IGNORECASE,
)

OWN_SCOPE = (
    "Stay within what this project owns: the design you propose changes only the code you write. Do not propose "
    "that the user or another team change an external system (a platform, a service, a library); the user asks for "
    "such suggestions when they want them."
)
WIDER_SCOPE = (
    "The user asked for suggestions, so you may also name a change to a system you do not own when it would make the "
    "class impossible (for example a job that takes files as inputs instead of code inside a string). First check in "
    "the code that calls that system what its interface accepts today; then put it as a question for its owners, "
    "with what you checked, not as a fact."
)


def error_kinds(tool: str, content: str) -> set[str]:
    """The error kinds a running tool's output shows."""
    if tool not in RUNNING_TOOLS:
        return set()
    return {kind for kind in ERROR_KIND.findall(content) if kind not in TOO_GENERAL}


def asks_for_suggestions(request: str | None) -> bool:
    return bool(request) and SUGGESTION_REQUEST.search(request or "") is not None


@dataclass
class ErrorClasses:
    """Per session: in which code states each error kind was seen, and which kinds were already raised."""

    seen: dict[str, set[int]] = field(
        default_factory=dict
    )  # kind -> the last code-edit step when it was seen
    raised: set[str] = field(default_factory=set)  # kinds the model was asked about in a result
    finish_told: set[str] = field(default_factory=set)  # kinds the finish check asked about
    suggestions_asked: bool = False  # the request of this turn asks for suggestions

    def observe(self, tool: str, content: str, code_state: int) -> str:
        """The note to add to this result, or "": the kind came back after two code changes and was not raised yet."""
        fresh = []
        for kind in sorted(error_kinds(tool, content)):
            states = self.seen.setdefault(kind, set())
            states.add(code_state)
            if len(states) >= ROUNDS and kind not in self.raised:
                self.raised.add(kind)
                fresh.append(kind)
        if not fresh:
            return ""
        return (
            f"[note: {', '.join(fresh)} again, after {ROUNDS - 1} or more code changes meant to fix it. Before you fix "
            "this instance, find what these errors have in common: the one cause (for example one language written "
            "inside another language's strings, a value built by hand instead of by a library, a step that runs "
            "before what it needs). Then change the design so this class of error cannot happen again, not only this "
            f"line, and say the cause in your reply. {WIDER_SCOPE if self.suggestions_asked else OWN_SCOPE}]"
        )

    def suggestion_note(self) -> str:
        """For a request that asks for suggestions: the error kinds this session saw in more than one code state."""
        recurring = sorted(kind for kind, states in self.seen.items() if len(states) >= 2)
        if not recurring:
            return ""
        return (
            f"Errors of the same kind came back in this session: {', '.join(recurring)}. Before you suggest anything, "
            "name what they have in common (the one cause), then suggest the design that makes that class of error "
            "impossible. " + WIDER_SCOPE
        )

    def finish_note(self, reply: str) -> str:
        """Before the turn ends: a raised kind the reply does not explain with a cause."""
        lowered = reply.lower()
        open_kinds = [
            kind
            for kind in sorted(self.raised - self.finish_told)
            if not (kind.lower() in lowered and "cause" in lowered)
        ]
        if not open_kinds:
            return ""
        self.finish_told.update(open_kinds)
        return (
            f"{', '.join(open_kinds)} came back several times in this session. Your reply must say, in a few lines: the "
            "common cause of these errors, and the change that makes them impossible (made, or why not). "
            + (WIDER_SCOPE if self.suggestions_asked else OWN_SCOPE)
        )

"""Mode B tools (spec §6A): the host profile (search / read / propose an update), the assumption register,
user-pinned interface contracts (§6A.2A, D-129), and the contract/integration documents. Only offered in
Mode B sessions."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from forge.modeb.assumptions import AssumptionRegister
from forge.modeb.contracts import ContractError, ContractRegister
from forge.modeb.output import DOCUMENT_NAMES, read_document, write_document
from forge.safety.redact import default_redactor
from forge.tools.base import Tool, ToolArgs, ToolContext, ToolResult


def _profile(context: ToolContext) -> Any:
    return context.profile


def _propose_contract_lesson(context: ToolContext, contract: Any) -> None:
    """D-129: a pinned/revised contract becomes a lesson proposal, scoped to this host profile, so Forge
    recommends it on a later, similar requirement instead of re-deriving or re-asking (spec §12)."""
    from forge.config import forge_home
    from forge.learning.lessons import LessonStore
    from forge.learning.scope import scope_of

    scope = scope_of(context.workspace, forge_home())
    LessonStore(forge_home()).propose(
        f"For the '{contract.seam}' seam on this host, build to this exact signature: {contract.signature}"
        + (f" ({contract.note})" if contract.note else ""),
        scope,
        source="contract",
        evidence=contract.id,
        confidence="high",  # the user stated it directly, not inferred
    )


class ProfileSearch(Tool):
    name = "profile_search"
    read_only = True
    description = (
        "Search the host's imported structure export (module paths, class/function signatures, "
        "blueprints and "
        "routes, models and columns, env key names — never code) for what the requirement touches."
    )

    class Args(ToolArgs):
        query: str
        limit: int = Field(default=6, ge=1, le=15)

    async def run(self, args: ProfileSearch.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        if profile is None:
            return ToolResult(ok=False, content="No host profile is attached to this workspace.")
        hits = profile.search(args.query, args.limit)
        if not hits:
            return ToolResult(
                ok=True,
                content="Nothing in the structure export matches; ask the user (briefly, with options).",
            )
        return ToolResult(ok=True, content="\n\n".join(f"### {path}\n{text}" for path, text in hits))


class ProfileRead(Tool):
    name = "profile_read"
    read_only = True
    description = (
        "Read part of the host profile: PROFILE (interview answers), CONVENTIONS, INTERFACES (known host "
        "symbols), or an exemplar by id (e.g. E001), or 'packages' (the host's pinned versions)."
    )

    class Args(ToolArgs):
        part: str

    async def run(self, args: ProfileRead.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        if profile is None:
            return ToolResult(ok=False, content="No host profile is attached to this workspace.")
        part = args.part.strip()
        if part.upper() in ("PROFILE", "CONVENTIONS", "INTERFACES"):
            text = profile.read(part.upper())
            return ToolResult(ok=True, content=text or f"{part.upper()} is empty so far.")
        if part.lower() == "packages":
            packages = profile.packages()
            return ToolResult(
                ok=True, content="\n".join(f"{k} {v}" for k, v in packages.items()) or "Unknown."
            )
        code = profile.read_exemplar(part.upper())
        if code is None:
            return ToolResult(
                ok=False, content=f"No exemplar {part}. Exemplars: {[i for i, _ in profile.exemplars()]}"
            )
        return ToolResult(ok=True, content=code)


class ProfileUpdate(Tool):
    name = "profile_update"
    read_only = True  # changes Forge Home, never the workspace; the user approves every change
    description = (
        "Propose a change to the host profile when you learned a lasting fact about the host (from "
        "the user). "
        "Give the whole new document text; the user sees it and approves or rejects it."
    )

    class Args(ToolArgs):
        document: Literal["PROFILE", "CONVENTIONS", "INTERFACES"]
        markdown: str
        change: str = Field(description="One line: what changed and why")

    async def run(self, args: ProfileUpdate.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        if profile is None or context.interaction is None:
            return ToolResult(
                ok=False, content="Profile updates need an attached profile and a user to approve them."
            )
        approved, feedback = await context.interaction.approve_profile_change(
            args.document, args.markdown, args.change
        )
        if not approved:
            return ToolResult(ok=True, content=f"The user did not approve it: {feedback}")
        profile.write(args.document, args.markdown, args.change)
        return ToolResult(ok=True, content=f"Profile updated (v{profile.version}).")


class ProfileAddExemplar(Tool):
    name = "profile_add_exemplar"
    read_only = True  # Forge Home only; the user approves the cleaned snippet first
    description = (
        "Save a snippet the user pasted (e.g. one existing MethodView blueprint with the logic removed) "
        "as a profile exemplar, so later work mirrors it. The user sees the cleaned version (secrets "
        "and sensitive terms removed) and decides to keep or drop it."
    )

    class Args(ToolArgs):
        code: str
        note: str = Field(
            description="What it demonstrates, e.g. 'MethodView blueprint + marshmallow schema'"
        )

    async def run(self, args: ProfileAddExemplar.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        if profile is None or context.interaction is None:
            return ToolResult(
                ok=False, content="Exemplars need an attached profile and a user to approve them."
            )
        cleaned = profile.clean(args.code)
        warning = (
            "\n\n**Something in the snippet looked like a secret or a sensitive term and was replaced.** "
            "Keep the cleaned version, or reject to drop it."
            if cleaned != args.code
            else ""
        )
        approved, feedback = await context.interaction.approve_profile_change(
            "exemplar", f"```python\n{cleaned}\n```{warning}", args.note
        )
        if not approved:
            return ToolResult(ok=True, content=f"The user dropped the snippet: {feedback}")
        exemplar_id, _ = profile.add_exemplar(args.code, args.note)
        return ToolResult(ok=True, content=f"Saved as exemplar {exemplar_id}.")


class AssumptionAdd(Tool):
    name = "assumption_add"
    read_only = True  # the register lives in .forge/
    description = (
        "Record an assumption about the host that nobody stated (with a one-line check the user can run "
        "in the host). High-impact assumptions should also be raised with ask_user."
    )

    class Args(ToolArgs):
        text: str
        confidence: Literal["high", "medium", "low"]
        impact: Literal["high", "medium", "low"]
        check: str

    async def run(self, args: AssumptionAdd.Args, context: ToolContext) -> ToolResult:
        item = AssumptionRegister(context.workspace).add(args.text, args.confidence, args.impact, args.check)
        return ToolResult(ok=True, content=f"Recorded {item.id}.")


class ContractRead(Tool):
    name = "contract_read"
    read_only = True
    description = (
        "List the interface contracts the user pinned for this host (a seam's exact signature, e.g. the "
        "LLM call wrapper or a file read/write helper) — build new code at these seams to match them "
        "exactly. Empty when the user hasn't pinned any: use your own judgement for those seams."
    )

    class Args(ToolArgs):
        pass

    async def run(self, args: ContractRead.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        if profile is None:
            return ToolResult(ok=False, content="No host profile is attached to this workspace.")
        items = ContractRegister(profile).all()
        if not items:
            return ToolResult(ok=True, content="No contracts pinned yet.")
        return ToolResult(
            ok=True,
            content="\n".join(
                f"{c.id} {c.seam}: {c.signature}" + (f" — {c.note}" if c.note else "") for c in items
            ),
        )


class ContractPin(Tool):
    name = "contract_pin"
    read_only = True  # Forge Home only (the profile), never the workspace
    description = (
        "Record a user-pinned interface contract for a seam (e.g. seam='llm_call_wrapper', "
        "signature='def call_llm(prompt: str, **kwargs) -> LLMResponse'). Use this when the user tells "
        "you the exact signature/shape to build a seam to, so the result is easy to retrofit into their "
        "repository by hand. Pinning an existing seam again revises it — the user may change their mind "
        "after seeing generated code."
    )

    class Args(ToolArgs):
        seam: str = Field(description="Short lowercase id, e.g. 'llm_call_wrapper', 'file_read_write'")
        signature: str = Field(description="The exact signature/contract text the user gave")
        note: str = Field(default="", description="Why, or how it's used")

    async def run(self, args: ContractPin.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        if profile is None:
            return ToolResult(ok=False, content="No host profile is attached to this workspace.")
        try:
            contract = ContractRegister(profile).pin(args.seam, args.signature, args.note)
        except ContractError as error:
            return ToolResult(ok=False, content=str(error))
        _propose_contract_lesson(context, contract)
        return ToolResult(ok=True, content=f"Pinned {contract.id} ({contract.seam}).")


class ModebDocument(Tool):
    name = "modeb_document"
    read_only = True  # .forge/modeb/, assembled into output/ at EXPORT
    description = (
        "Write INTERFACE_CONTRACT (every host symbol the code depends on: import path, expected "
        "signature and "
        "behaviour; for each _host_adapter function a suggested implementation) or INTEGRATION_NOTES "
        "(registrations, config keys, new dependencies). Give the whole document."
    )

    class Args(ToolArgs):
        name: Literal["INTERFACE_CONTRACT", "INTEGRATION_NOTES"]
        markdown: str

    async def run(self, args: ModebDocument.Args, context: ToolContext) -> ToolResult:
        profile = _profile(context)
        text = profile.clean(args.markdown) if profile is not None else default_redactor.redact(args.markdown)
        write_document(context.workspace, args.name, text)
        current = read_document(context.workspace, args.name)
        return ToolResult(ok=True, content=f"{args.name} saved ({len(current.splitlines())} lines).")


def modeb_tools() -> list[Tool]:
    assert DOCUMENT_NAMES  # the documents the tools write
    return [
        ProfileSearch(),
        ProfileRead(),
        ProfileUpdate(),
        ProfileAddExemplar(),
        AssumptionAdd(),
        ContractRead(),
        ContractPin(),
        ModebDocument(),
    ]

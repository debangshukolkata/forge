"""Slash commands handled by the engine, so the terminal and web UIs behave identically (spec §15)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import TYPE_CHECKING

from forge.config import ROLES, forge_home
from forge.engine.events import EventType
from forge.errors import ConfigError
from forge.kb.builder import build as kb_build
from forge.kb.builder import status as kb_status
from forge.kb.knowledge import KnowledgeBase
from forge.kb.narrative import llm_writer
from forge.llm.cost import format_money
from forge.memory.store import CommandStore, MemoryStore
from forge.workspace.output import build_output
from forge.workspace.workspace import Workspace, WorkspaceError

if TYPE_CHECKING:
    from forge.engine.session_host import SessionHost

HELP_TEXT = """Available commands:
  /help                     this list
  /model                    show which model each role uses
  /model <model>            use <model> for the coder role
  /model <role> <model>     use <model> for <role>
                            roles: coder, kb_builder, reviewer, summariser, vision, judge, fallback
  /cost                     cost and token usage so far
  /clear                    start a fresh conversation
  /context                  how full the context window is
  /compact [focus]          summarise earlier conversation now (optionally what to focus on)
  /checkpoints              list checkpoints (workspace sessions)
  /undo                     undo the last file change
  /rewind <id>              undo every change back to and including checkpoint <id>
  /export                   rebuild output/ (only new and modified files, plus instructions)
  /mode [plan|default|auto] show or change the permission mode
  /requirements | /plan | /tasks   the approved requirements, the plan, the task board
  /restructure <how>        reshape delivered code to fit your repo (behaviour kept)
  /kb status|build|refresh|rebuild|search <text>   the repository knowledge base
  /db [status]              what Forge may do on each database, and the scratch schema
  /db requests              DB requests Forge wrote for you or your DBA
  /db done <DBR-n> [result] you ran it: Forge verifies and unblocks the tasks waiting on it
  /db cant <DBR-n> <why>    it can't be run: Forge looks for a workaround
  /db skip <DBR-n>          drop it; Forge works around it
  /db cleanup               drop every object Forge created in the scratch schema
  /diagnose [error text]    after copying output/ into your repo: find what is wrong
  /remember <text>          remember a preference for all future work
  /profile [show|list|terms <t1,t2,...>]   Mode B: the host profile (sensitive terms masked everywhere)
  /assumptions [confirm|wrong <id> [note]] Mode B: what Forge assumed about the host
  /contract | /revision     Mode B: the interface contract; the current revision and what changed
  /contracts [pin <seam> <signature> | forget <seam|id>]   Mode B: user-pinned interface contracts (D-129)
  /forget-snippet <id>      Mode B: remove a pasted snippet (exemplar) from the profile
  /library [search <text> | show <REQ-n>]   earlier requirements on this codebase
  /lessons [approve|reject|delete|promote <id> | edit <id> <text>]
                            what Forge learned (only approved lessons are ever used)
  /retro [REQ-n]            the last (or a given) retrospective
  /stats                    trends across requirements (cost, first-pass success, failure causes)
  /init                     draft the repository-level FORGE.md (instructions Forge always follows)
  # <text>                  (a message starting with #) save an instruction to a FORGE.md
  /effort [low|medium|high] reasoning effort for this session ('think hard: ...' raises it for one message)
  /style [concise|explanatory|learning]   how much Forge explains while working
  /skills | /agents         the skills and custom subagents Forge can use
  /bg [kill <name>]         background processes (dev servers...) with the tail of their output
  /log | /diff <task|hash>  the workspace's local history: one commit per completed task
  /rename <name>            name this session/workspace
  /export-chat              save the conversation as Markdown (.forge/exports/)
  /mcp                      connected MCP servers and their tools (optional; config mcp.*)
  /improve [list | show IP-n | suggest <idea> | validate IP-n | apply IP-n | reject IP-n]
                            Forge's proposals to improve itself (you apply them)
  /memory [delete <id>]     list (or delete) what Forge remembers
  /<name> [args]            your custom commands: <forge home>/commands/<name>.md ($ARGUMENTS = args)
  /exit                     end the session
Other commands from the spec arrive with later milestones."""


class SlashCommandHandler:
    def __init__(self, host: SessionHost) -> None:
        self.host = host

    async def handle(self, text: str) -> None:
        name, *args = text.strip().split()
        handlers = {
            "/help": self._help,
            "/model": self._model,
            "/cost": self._cost,
            "/clear": self._clear,
            "/context": self._context,
            "/compact": self._compact,
            "/checkpoints": self._checkpoints,
            "/undo": self._undo,
            "/rewind": self._rewind,
            "/export": self._export,
            "/mode": self._mode,
            "/requirements": self._requirements,
            "/plan": self._plan,
            "/tasks": self._tasks,
            "/kb": self._kb,
            "/db": self._db,
            "/diagnose": self._diagnose,
            "/remember": self._remember,
            "/profile": self._profile,
            "/library": self._library,
            "/init": self._init,
            "/effort": self._effort,
            "/style": self._style,
            "/skills": self._skills,
            "/agents": self._agents,
            "/bg": self._bg,
            "/log": self._log,
            "/diff": self._diff,
            "/rename": self._rename,
            "/export-chat": self._export_chat,
            "/mcp": self._mcp,
            "/lessons": self._lessons,
            "/retro": self._retro,
            "/stats": self._stats,
            "/improve": self._improve,
            "/assumptions": self._assumptions,
            "/contract": self._contract,
            "/contracts": self._contracts,
            "/revision": self._revision,
            "/forget-snippet": self._forget_snippet,
            "/memory": self._memory,
            "/exit": self._exit,
        }
        handler = handlers.get(name)
        if handler is None:
            expanded = CommandStore(forge_home()).expand(name.lstrip("/"), " ".join(args))
            if expanded is not None:  # a custom command: its text goes to Forge as a message
                await self.host.run_message(expanded)
                return
            custom = ", ".join(f"/{n}" for n in CommandStore(forge_home()).names())
            await self._say(
                f"Unknown command: {name}. Type /help."
                + (f" Your custom commands: {custom}" if custom else "")
            )
            return
        try:
            await handler(args)
        except (ConfigError, WorkspaceError, ValueError) as error:
            await self._say(str(error))

    def _workspace(self) -> Workspace:
        if self.host.workspace is None:
            raise WorkspaceError("No workspace is attached. Start Forge with --workspace <path>.")
        return self.host.workspace

    async def _checkpoints(self, args: list[str]) -> None:
        checkpoints = self._workspace().checkpoints.all()
        if not checkpoints:
            await self._say("No checkpoints yet.")
            return
        await self._say("\n".join(f"  {cp.id:>4}  {cp.created}  {cp.label}" for cp in checkpoints))

    async def _undo(self, args: list[str]) -> None:
        checkpoint = self._workspace().undo()
        await self._say(
            f"Undid checkpoint {checkpoint.id}: {checkpoint.label}" if checkpoint else "Nothing to undo."
        )

    async def _rewind(self, args: list[str]) -> None:
        if len(args) != 1 or not args[0].isdigit():
            await self._say("Usage: /rewind <checkpoint id>  (see /checkpoints)")
            return
        undone = self._workspace().rewind(int(args[0]))
        await self._say(f"Rewound {len(undone)} checkpoint(s): " + ", ".join(cp.label for cp in undone))

    async def _requirements(self, args: list[str]) -> None:
        await self._show_document("REQUIREMENTS.md", "No approved requirements yet.")

    async def _plan(self, args: list[str]) -> None:
        await self._show_document("PLAN.md", "No approved plan yet.")

    async def _tasks(self, args: list[str]) -> None:
        orchestrator = self.host.orchestrator
        if orchestrator is None:
            raise WorkspaceError("Tasks exist in orchestrated workspace sessions only.")
        state = orchestrator.state
        await self._say(f"{state.resume_summary()}\n{state.task_board()}")

    async def _show_document(self, name: str, missing: str) -> None:
        path = self._workspace().forge_dir / name
        await self._say(path.read_text(encoding="utf-8") if path.exists() else missing)

    async def _mode(self, args: list[str]) -> None:
        agent = self.host.agent
        if agent is None:
            raise WorkspaceError(
                "Permission modes apply to workspace sessions. Start Forge with --workspace <path>."
            )
        if args:
            if args[0] not in ("plan", "default", "auto"):
                await self._say("Usage: /mode plan|default|auto")
                return
            agent.gate.mode = args[0]  # type: ignore[assignment]  # checked against the literals above
        await self._say(
            f"Permission mode: {agent.gate.mode}. plan = read-only; default = edits applied, "
            "unlisted commands ask; auto = no questions except the always-ask list."
        )

    async def _kb(self, args: list[str]) -> None:
        workspace = self._workspace()
        if workspace.mode_b:
            await self._say(
                "/kb is not used in Mode B: the host profile replaces the knowledge base (/profile)."
            )
            return
        kb_dir = self.host.kb_dir()
        assert kb_dir is not None
        action = args[0] if args else "status"
        repo, app = Path(workspace.info.repo_path), workspace.info.app_subfolder
        if action == "status":
            changes = await asyncio.to_thread(kb_status, repo, app, kb_dir)
            text = (
                "No knowledge base yet: /kb build"
                if changes is None
                else f"Knowledge base at {kb_dir}: up to date."
                if not changes.all
                else f"Knowledge base at {kb_dir}: {len(changes.all)} file(s) changed — /kb refresh"
            )
            await self._say(text)
        elif action in ("build", "refresh", "rebuild"):

            async def progress(message: str) -> None:
                await self._say(message)

            def on_progress(message: str) -> None:
                asyncio.get_running_loop().create_task(progress(message))

            report = await kb_build(
                repo,
                app,
                kb_dir,
                llm_writer(self.host.router),
                full=action == "rebuild",
                on_progress=on_progress,
            )
            self.host.reload_kb()
            await self._say(
                f"Knowledge base {'built' if report.full else 'refreshed'}: "
                f"{len(report.changes.all)} changed "
                f"file(s); {len(report.llm_documents)} document(s) written by the LLM"
                + (
                    f"; kept your pinned edits in {', '.join(report.docs_kept_pinned)}"
                    if report.docs_kept_pinned
                    else ""
                )
            )
        elif action == "search" and len(args) > 1:
            kb = KnowledgeBase.open(kb_dir)
            if kb is None:
                await self._say("No knowledge base yet: /kb build")
                return
            hits = kb.search(" ".join(args[1:]))
            listing = [f"[{h.kind}] {h.name} — {h.location}" for h in hits]
            await self._say("\n".join(listing) or "No matches.")
        else:
            await self._say("Usage: /kb status | build | refresh | rebuild | search <text>")

    async def _db(self, args: list[str]) -> None:
        db = self.host.db
        if db is None:
            await self._say("No database configured: set LOCAL_PG_URL (and/or DEV_PG_URL) in Forge's .env.")
            return
        action = args[0].lower() if args else "status"
        if action == "status":
            await self.host.prepare_database(force=True)
            return  # prepare_database announces the status
        if action == "requests":
            requests = db.requests.all()
            await self._say(
                "\n".join(f"  {r.id}  [{r.status}]  {r.title}" for r in requests) or "No DB requests."
            )
            return
        if action == "cleanup":
            if db.scratch is None:
                await self._say("No scratch schema in use.")
                return
            dropped = await asyncio.to_thread(db.scratch.cleanup)
            db.scratch = None
            await self._say("Dropped: " + (", ".join(dropped) or "nothing (Forge created no objects)"))
            return
        if action not in ("done", "cant", "skip") or len(args) < 2:
            await self._say(
                "Usage: /db [status] | requests | done <DBR-n> [result] | cant <DBR-n> <why> | "
                "skip <DBR-n> | cleanup"
            )
            return
        request = db.requests.get(args[1])
        if request is None:
            await self._say(f"No DB request {args[1]}. See /db requests.")
            return
        rest = " ".join(args[2:])
        if action == "done":
            await self.host.prepare_database(force=True)  # it may have created the scratch schema
            ok, message = await asyncio.to_thread(db.verify_request, request, rest or None)
            if not ok:
                await self._say(f"{request.id} is not verified yet: {message}")
                return
            updated = db.requests.set_status(request.id, "done", message)
        else:
            updated = db.requests.set_status(request.id, "cannot" if action == "cant" else "skipped", rest)
            message = rest or updated.status
        await self.host.bus.publish(
            EventType.DB_REQUEST_UPDATED, {"id": updated.id, "status": updated.status}
        )
        self.host.refresh_database_pin()
        await self._say(f"{request.id}: {message}")
        orchestrator = self.host.orchestrator
        if orchestrator is not None and orchestrator.db_request_resolved(request.id, action == "done", rest):
            await self.host.continue_work()

    async def _diagnose(self, args: list[str]) -> None:
        from forge.diagnose.run import run_diagnose

        host = self.host
        if self._workspace().mode_b:  # spec §6A.7: chat-driven diagnose, no repository to copy
            await self._say(
                "In Mode B, paste the error, test output or behaviour as a message (never secrets): Forge "
                "classifies it (wrong assumption, version mismatch, missed step or bug), asks for the "
                "minimum "
                "detail it needs, fixes the code and issues a new revision."
            )
            return
        workspace = self._workspace()
        await self._say(
            "Diagnosing: checking your repository against output/, then running its tests on a fresh copy…"
        )
        await host.prepare_database()
        result = await run_diagnose(
            workspace,
            db=host.db,
            router=host.router,
            context=host.agent.context if host.agent else None,
            pasted_error=" ".join(args) or None,
        )
        problems = result.integrity.problems
        tests = result.fresh.tests if result.fresh else None
        lines = [f"Diagnose report {result.number}: {result.report_path}"]
        lines += [f"- {f.kind}: {f.path} — {f.instruction.splitlines()[0]}" for f in problems[:10]]
        if tests is not None:
            lines.append(
                f"Tests on a fresh copy of your repository: {'passed' if tests.passed else 'FAILED'}"
            )
        if result.analysis:
            lines.append("Analysis:\n" + result.analysis)
        if not problems and (tests is None or tests.passed) and not result.analysis:
            lines.append("No problems found.")
        await self._say("\n".join(lines))

    async def _remember(self, args: list[str]) -> None:
        if not args:
            await self._say("Usage: /remember <a preference for all future work>")
            return
        memory = MemoryStore(forge_home()).add(" ".join(args))
        self.host.refresh_memory_pin()
        await self._say(f"Remembered ({memory.id}): {memory.title}")

    async def _memory(self, args: list[str]) -> None:
        store = MemoryStore(forge_home())
        if len(args) == 2 and args[0] == "delete":
            deleted = store.delete(args[1])
            self.host.refresh_memory_pin()
            await self._say(f"Deleted {args[1]}." if deleted else f"No memory {args[1]}.")
            return
        memories = store.all()
        await self._say(
            "\n".join(f"  {m.id}  {m.text}" for m in memories) or "Nothing remembered yet: /remember <text>"
        )

    def _modeb(self) -> Workspace:
        workspace = self._workspace()
        if not workspace.mode_b:
            raise WorkspaceError("This command is for Mode B (standalone) workspaces.")
        return workspace

    async def _profile(self, args: list[str]) -> None:
        from forge.modeb.profile import ProfileStore

        if args and args[0] == "list":
            await self._say("Host profiles: " + (", ".join(ProfileStore(forge_home()).names()) or "none"))
            return
        self._modeb()
        profile = self.host.host_profile()
        if profile is None:
            await self._say("This workspace's host profile is missing (see .forge/host_profile_ref.json).")
            return
        if args and args[0] == "terms":
            profile.set_sensitive_terms(" ".join(args[1:]).split(","))
            await self._say(
                f"Sensitive terms set ({len(profile.sensitive_terms)}); they are masked from now on."
            )
            return
        await self._say(profile.essentials(max_chars=20_000))

    async def _assumptions(self, args: list[str]) -> None:
        from forge.modeb.assumptions import AssumptionRegister

        register = AssumptionRegister(self._modeb())
        if len(args) >= 2 and args[0] in ("confirm", "wrong"):
            try:
                item = register.resolve(
                    args[1].upper(), "confirmed" if args[0] == "confirm" else "wrong", " ".join(args[2:])
                )
            except KeyError:
                await self._say(f"No assumption {args[1]}.")
                return
            await self._say(
                f"{item.id} marked {item.status}."
                + (" Tell Forge what is true instead." if item.status == "wrong" else "")
            )
            return
        await self._say(register.markdown())

    async def _contract(self, args: list[str]) -> None:
        from forge.modeb.output import read_document

        await self._say(read_document(self._modeb(), "INTERFACE_CONTRACT") or "No interface contract yet.")

    async def _contracts(self, args: list[str]) -> None:
        """User-pinned interface contracts (§6A.2A, D-129) — not INTERFACE_CONTRACT.md (/contract), which
        is what the delivered code ended up using."""
        from forge.modeb.contracts import ContractError, ContractRegister

        self._modeb()
        profile = self.host.host_profile()
        if profile is None:
            await self._say("This workspace's host profile is missing.")
            return
        register = ContractRegister(profile)
        if len(args) >= 2 and args[0] == "pin":
            seam, signature = args[1], " ".join(args[2:])
            if not signature:
                await self._say("Usage: /contracts pin <seam> <signature>")
                return
            try:
                contract = register.pin(seam, signature, "")
            except ContractError as error:
                await self._say(str(error))
                return
            await self._say(f"Pinned {contract.id} ({contract.seam}): {contract.signature}")
            return
        if len(args) == 2 and args[0] == "forget":
            removed = register.forget(args[1])
            await self._say(f"{args[1]} forgotten." if removed else f"No contract {args[1]}.")
            return
        items = register.all()
        if not items:
            await self._say("No contracts pinned yet. Usage: /contracts pin <seam> <signature>")
            return
        await self._say(
            "\n".join(
                f"  {c.id}  {c.seam}: {c.signature}" + (f" — {c.note}" if c.note else "") for c in items
            )
        )

    async def _revision(self, args: list[str]) -> None:
        from forge.modeb.output import current_revision

        workspace = self._modeb()
        notes = workspace.output_dir / "REVISION_NOTES.md"
        revision = current_revision(workspace)
        await self._say(
            (notes.read_text(encoding="utf-8") if notes.exists() else "")
            or f"Revision {revision}: nothing exported yet (EXPORT, or /export)."
        )

    async def _forget_snippet(self, args: list[str]) -> None:
        self._modeb()
        profile = self.host.host_profile()
        if not args or profile is None:
            await self._say("Usage: /forget-snippet <exemplar id, e.g. E001>")
            return
        removed = profile.forget_exemplar(args[0].upper())
        self.host.open_kb()  # refresh the pinned profile essentials
        await self._say(
            f"{args[0].upper()} removed from the profile." if removed else f"No snippet {args[0]}."
        )

    def _scopes(self) -> tuple[str, ...]:
        from forge.learning.scope import scope_of, visible_scopes

        return visible_scopes(scope_of(self._workspace(), forge_home()))

    async def _library(self, args: list[str]) -> None:
        from forge.learning.library import Library

        library = Library(forge_home())
        if len(args) >= 2 and args[0] == "show":
            await self._say(
                library.read(args[1], self._scopes()) or f"No requirement {args[1]} for this codebase."
            )
            return
        if args and args[0] == "search":
            hits = library.search(" ".join(args[1:]), self._scopes())
            await self._say("\n".join(f"  {h.id}  {h.title}" for h in hits) or "No matches.")
            return
        cards = library.cards(self._scopes())
        await self._say(
            "\n".join(f"  {c['id']}  [{c['status']}] {c['title']}" for c in cards) or "No requirements yet."
        )

    async def _lessons(self, args: list[str]) -> None:
        from forge.learning.lessons import LessonStore

        store = LessonStore(forge_home())
        try:
            if len(args) >= 2 and args[0] in ("approve", "reject", "delete"):
                status = {"approve": "approved", "reject": "rejected", "delete": "archived"}[args[0]]
                lesson = store.set_status(args[1], status)  # type: ignore[arg-type]
                await self._say(f"{lesson.id} {status}.")
                return
            if len(args) >= 3 and args[0] == "edit":
                lesson = store.set_status(args[1], "approved", " ".join(args[2:]))
                await self._say(f"{lesson.id} edited and approved.")
                return
            if len(args) >= 2 and args[0] == "promote":
                lesson = store.promote(args[1])
                await self._say(f"{lesson.id} is now global (used for every codebase).")
                return
        except KeyError:
            await self._say(f"No lesson {args[1]}.")
            return
        visible = [
            item
            for item in store.all()
            if item.scope in self._scopes() and item.status in ("approved", "proposed")
        ]
        lines = [f"  {item.id}  [{item.status}] ({item.scope}) {item.text}" for item in visible]
        await self._say(
            "\n".join(lines) or "No lessons yet: they are proposed in the retro after each requirement."
        )

    async def _retro(self, args: list[str]) -> None:
        from forge.learning.library import Library

        folder = forge_home() / "learning" / "retros"
        cards = Library(forge_home()).cards(self._scopes())
        wanted = args[0].upper() if args else (cards[-1]["id"] if cards else "")
        path = folder / f"{wanted}.md"
        allowed = {c["id"] for c in cards}
        await self._say(
            path.read_text(encoding="utf-8") if wanted in allowed and path.exists() else "No retro yet."
        )

    async def _stats(self, args: list[str]) -> None:
        from forge.learning.metrics import Metrics

        await self._say(Metrics(forge_home()).stats())

    async def _improve(self, args: list[str]) -> None:
        from forge.learning.improve import Improvements

        improvements = Improvements(forge_home())
        action = args[0].lower() if args else "list"
        if action == "list":
            items = improvements.all()
            await self._say(
                "\n".join(
                    f"  {p.id}  tier {p.meta['tier']}  [{p.meta['status']}] {p.meta['title']}" for p in items
                )
                or "No improvement proposals."
            )
            return
        if action == "suggest":
            idea = " ".join(args[1:]) or "anything that recurring problems in the metrics and retros suggest"
            await self.host.run_message(
                "Draft a self-improvement proposal for Forge (spec §12.5) about: "
                f"{idea}. Use the evidence in /stats and the retros; write it with improvement_propose."
            )
            return
        proposal = improvements.get(args[1]) if len(args) > 1 else None
        if proposal is None:
            await self._say(
                "Usage: /improve [list | show IP-n | suggest <idea> | validate IP-n | apply IP-n | "
                "reject IP-n]"
            )
            return
        if action == "show":
            text = (proposal.folder / "PROPOSAL.md").read_text(encoding="utf-8")
            validation = proposal.folder / "VALIDATION.md"
            await self._say(
                text + ("\n" + validation.read_text(encoding="utf-8") if validation.exists() else "")
            )
        elif action == "validate":
            await self._say(
                f"Validating {proposal.id} in a sandbox copy of Forge's source (runs its test suite)…"
            )
            await self._say(await asyncio.to_thread(improvements.validate, proposal.id))
        elif action == "apply":
            try:
                target = improvements.apply_tier2(proposal.id)
            except ValueError as error:
                await self._say(str(error))
                return
            await self._say(f"{proposal.id} applied to {target}; it takes effect from the next session.")
        elif action == "reject":
            improvements.set_status(proposal, "rejected")
            await self._say(f"{proposal.id} rejected.")

    async def _init(self, args: list[str]) -> None:
        from forge.parity.instructions import draft_from_kb

        workspace = self._workspace()
        level = self.host.repo_level_dir()
        if level is None:
            await self._say(
                "No repository/host folder to hold a FORGE.md yet (build the KB first: /kb build)."
            )
            return
        path = level / "FORGE.md"
        if path.exists():
            await self._say(f"{path} already exists; edit it directly (or add lines with '# <instruction>').")
            return
        essentials = self.host.context_manager.pinned.get("kb_essentials")
        level.mkdir(parents=True, exist_ok=True)
        path.write_text(draft_from_kb(essentials, workspace.info.name), encoding="utf-8")
        self.host.refresh_instructions()
        await self._say(
            f"Drafted {path}. Edit it: Forge reads it at the start of every session on this codebase."
        )

    async def _effort(self, args: list[str]) -> None:
        agent = self.host.agent
        if agent is None:
            return
        if args and args[0] in ("low", "medium", "high"):
            agent.effort = args[0]
        elif args and args[0] == "default":
            agent.effort = None
        await self._say(
            f"Reasoning effort: {agent.effort or 'model default'} (low | medium | high | default)"
        )

    async def _style(self, args: list[str]) -> None:
        from forge.parity.instructions import STYLES

        if args and args[0] in STYLES:
            self.host.style = args[0]
        elif args and args[0] == "default":
            self.host.style = None
        self.host.refresh_instructions()
        await self._say(f"Output style: {self.host.style or 'default'} ({' | '.join(STYLES)} | default)")

    async def _skills(self, args: list[str]) -> None:
        await self._say(self.host.context_manager.pinned.get("skills") or "No skills found.")

    async def _agents(self, args: list[str]) -> None:
        from forge.parity.agents import load_agents
        from forge.tools.parity import BUILT_IN_TYPES

        lines = [f"  {name} (built-in): {text}" for name, text in BUILT_IN_TYPES.items()]
        lines += [
            f"  {a.name}: {a.description or a.prompt[:80]} "
            f"[tools: {', '.join(a.tools) or 'read-only'}; model: {a.role}]"
            for a in load_agents(forge_home()).values()
        ]
        await self._say("\n".join(lines) + f"\nAdd your own in {forge_home() / 'agents'}/<name>.md")

    async def _bg(self, args: list[str]) -> None:
        agent = self.host.agent
        manager = agent.context.background if agent is not None else None
        if manager is None:
            await self._say("No background processes.")
            return
        if len(args) == 2 and args[0] == "kill":
            stopped = await manager.stop(args[1])
            await self._say(f"Stopped {args[1]}." if stopped else f"No background process {args[1]}.")
            return
        lines = []
        for name, entry in manager.processes.items():
            state = "running" if entry.running else f"exited ({entry.process.returncode})"
            tail = "\n".join(f"      {line}" for line in list(entry.lines)[-5:])
            lines.append(f"  {name}  [{state}]  port {entry.port or '-'}  {entry.command}\n{tail}")
        await self._say("\n".join(lines) or "No background processes.")

    async def _log(self, args: list[str]) -> None:
        from forge.parity.history import History

        await self._say(await asyncio.to_thread(History(self._workspace()).log))

    async def _diff(self, args: list[str]) -> None:
        from forge.parity.history import History

        if not args:
            await self._say("Usage: /diff <task id or commit hash> (see /log)")
            return
        await self._say(await asyncio.to_thread(History(self._workspace()).diff, args[0]))

    async def _rename(self, args: list[str]) -> None:
        workspace = self._workspace()
        if not args:
            await self._say(f"This session is '{workspace.info.name}'. Usage: /rename <name>")
            return
        workspace.info.name = " ".join(args)[:80]
        workspace.save_info()
        await self._say(f"Renamed to '{workspace.info.name}'.")

    async def _export_chat(self, args: list[str]) -> None:
        from forge.parity.sessions import export_chat

        path = export_chat(self._workspace(), self.host.bus.events_since(0))
        await self._say(f"Conversation saved to {path}.")

    async def _mcp(self, args: list[str]) -> None:
        hub = getattr(self.host, "mcp_hub", None)
        if hub is None:
            await self._say("MCP is off. Enable it in config.yaml (mcp.enabled: true, mcp.servers: ...).")
            return
        await self._say(hub.describe())

    async def _export(self, args: list[str]) -> None:
        if self._workspace().mode_b:
            from forge.modeb.output import build_modeb_output, current_revision

            build_modeb_output(self._workspace())
            await self._say(
                f"output/ rebuilt as revision {current_revision(self._workspace())}: see REVISION_NOTES.md."
            )
            return
        report = build_output(self._workspace())
        counts = {
            status: sum(1 for f in report.files if f.status == status)
            for status in ("added", "modified", "deleted")
        }
        await self._say(
            f"output/ rebuilt: {counts['added']} added, {counts['modified']} modified, "
            f"{counts['deleted']} deleted."
        )

    async def _say(self, text: str) -> None:
        await self.host.bus.publish(EventType.NOTICE, {"kind": "command_output", "text": text})

    async def _help(self, args: list[str]) -> None:
        await self._say(HELP_TEXT)

    async def _model(self, args: list[str]) -> None:
        router = self.host.router
        if len(args) == 1:
            router.set_role_model("coder", args[0])
        elif len(args) == 2:
            router.set_role_model(args[0], args[1])
        elif args:
            await self._say("Usage: /model [<role>] <model>")
            return
        models = router.config.llm.models
        lines = [f"  {role:<11} {router.role_models[role] or '-'}" for role in ROLES]
        available = ", ".join(f"{key} ({model.label})" for key, model in sorted(models.items()))
        await self._say("Models by role:\n" + "\n".join(lines) + f"\nAvailable: {available}")

    async def _cost(self, args: list[str]) -> None:
        cost = self.host.router.cost
        config = self.host.router.config.cost
        lines = [
            f"Spent {format_money(cost.total_usd, config)} of {format_money(cost.budget_usd, config)} "
            f"in {cost.calls} call(s)"
        ]
        for model_key, usage in cost.usage_by_model.items():
            lines.append(
                f"  {model_key}: {usage.input_tokens} in ({usage.cached_input_tokens} cached), "
                f"{usage.output_tokens} out ({usage.reasoning_tokens} reasoning)"
            )
        await self._say("\n".join(lines))

    async def _context(self, args: list[str]) -> None:
        manager = self.host.context_manager
        tools = self.host.agent.tools.specs() if self.host.agent else []
        parts = manager.breakdown(self.host.history, tools)
        model = self.host.router.model_for_role("coder")
        lines = [
            f"Context ({model}): {parts.percent}% of {parts.usable:,} usable tokens",
            f"  fixed (system prompt + tool schemas): {parts.fixed:,}",
            f"  pinned: {parts.pinned:,}",
            f"  history: {parts.history:,}",
            f"  free: {parts.free:,}",
            f"  compactions so far: {manager.compactions}",
        ]
        await self._say("\n".join(lines))

    async def _compact(self, args: list[str]) -> None:
        compacted = await self.host.context_manager.compact(self.host.history, " ".join(args) or None)
        if not compacted:
            await self._say("Nothing to compact yet (the conversation is still short).")

    async def _clear(self, args: list[str]) -> None:
        self.host.reset_history()
        await self._say("Conversation cleared.")

    async def _exit(self, args: list[str]) -> None:
        self.host.closed = True
        await self._say("Session ended.")

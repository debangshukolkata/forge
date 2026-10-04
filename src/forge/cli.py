"""Command-line entry point (spec §15). More subcommands arrive with later milestones."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from rich.console import Console

from forge.buildinfo import describe
from forge.errors import ConfigError, ForgeError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="forge", description="Forge coding agent")
    parser.add_argument("--version", action="version", version=describe())
    parser.add_argument("--workspace", type=Path, help="attach the interactive session to a workspace")
    parser.add_argument(
        "--direct",
        action="store_true",
        help="with --workspace: chat with the tool-using agent without the requirement workflow",
    )
    subcommands = parser.add_subparsers(dest="command")
    doctor = subcommands.add_parser("doctor", help="check the environment and model access")
    doctor.add_argument("--offline", action="store_true", help="skip the live model calls")
    new = subcommands.add_parser(
        "new", help="create a workspace: from a repository (Mode A) or standalone (B)"
    )
    new.add_argument("--repo", type=Path, help="Mode A: the repository to copy")
    new.add_argument("--standalone", action="store_true", help="Mode B: never sees the host code")
    new.add_argument("--project", help="the project name (Mode B: its saved knowledge is reused by name)")
    new.add_argument("--profile", help="Mode B: an existing host profile (default: from --project)")
    new.add_argument("--python", help="Mode B: base interpreter for the workspace venv (default: this one)")
    new.add_argument("--workspace", type=Path, required=True, dest="new_workspace")
    new.add_argument("--app-folder", help="the sub-folder holding the Python app, e.g. backend")
    export = subcommands.add_parser("export", help="rebuild the output/ folder of a workspace")
    export.add_argument("--workspace", type=Path, required=True, dest="export_workspace")
    run = subcommands.add_parser("run", help="headless: run (or resume) a requirement without prompts")
    run.add_argument("--workspace", type=Path, required=True, dest="run_workspace")
    run.add_argument("--requirement-file", type=Path)
    run.add_argument("-p", "--prompt", dest="run_prompt", help="the requirement text")
    run.add_argument(
        "--auto-approve",
        action="store_true",
        help="approve requirements/plan and ordinary commands (never the always-ask list)",
    )
    run.add_argument("--output-format", choices=["text", "json"], default="text")
    resume = subcommands.add_parser("resume", help="resume a workspace session where it stopped")
    resume.add_argument("--workspace", type=Path, required=True, dest="resume_workspace")
    cleanup = subcommands.add_parser(
        "cleanup", help="drop the database objects Forge created in a workspace's scratch schema"
    )
    cleanup.add_argument("--workspace", type=Path, required=True, dest="cleanup_workspace")
    cleanup.add_argument("--yes", action="store_true", help="don't ask for confirmation")
    diagnose = subcommands.add_parser(
        "diagnose", help="after copying output/ into your repo: check it and run its tests on a fresh copy"
    )
    diagnose.add_argument("--workspace", type=Path, required=True, dest="diagnose_workspace")
    diagnose.add_argument("--error-file", type=Path, help="an error/log from your own run to start from")
    diagnose.add_argument("--no-run", action="store_true", help="only the integrity check (no test run)")
    log_summary = subcommands.add_parser(
        "log-summary", help="one-page summary of a run: where the time and tokens went (D-151)"
    )
    log_summary.add_argument("--workspace", type=Path, help="a workspace folder (uses its transcripts)")
    log_summary.add_argument("--log", type=Path, help="an events.jsonl file instead of a workspace")
    profile = subcommands.add_parser("profile", help="Mode B host profiles")
    profile.add_argument("action", choices=["list", "new", "show", "import", "export-script"])
    profile.add_argument("name", nargs="?", help="the profile name (new/show/import)")
    profile.add_argument("file", nargs="?", type=Path, help="import: structure_export.json")
    profile.add_argument(
        "--terms", default="", help="new: comma-separated sensitive terms (company, codenames)"
    )
    profile.add_argument("--out", type=Path, help="export-script: where to write forge_structure_export.py")
    label = subcommands.add_parser(
        "label", help="label eval samples in the browser (boxes, fields, unreadable)"
    )
    label.add_argument("eval_dir", type=Path, help="an eval set folder with samples/ (labels/ is written)")
    label.add_argument("--no-browser", action="store_true")
    sessions = subcommands.add_parser("sessions", help="list recent workspaces/sessions")
    sessions.add_argument("action", choices=["list"])
    skill = subcommands.add_parser("skill", help="add, list or remove skills (instruction packs)")
    skill_commands = skill.add_subparsers(dest="skill_command", required=True)
    skill_add = skill_commands.add_parser("add", help="install skills from a github.com link or a folder")
    skill_add.add_argument(
        "source", help="https://github.com/<owner>/<repo>[/tree/<branch>/<folder>] or a folder"
    )
    skill_add.add_argument("--list", action="store_true", help="only show what the source contains")
    skill_add.add_argument("--yes", action="store_true", help="install without asking (you trust the source)")
    skill_add.add_argument("--force", action="store_true", help="replace a skill of the same name")
    skill_commands.add_parser("list", help="list the skills Forge can load")
    skill_remove = skill_commands.add_parser("remove", help="remove an installed skill")
    skill_remove.add_argument("name")
    ui = subcommands.add_parser("ui", help="start the local web UI (opens Edge)")
    ui.add_argument("--workspace", type=Path, dest="ui_workspace", help="open this workspace right away")
    ui.add_argument("--port", type=int, help="default 8765 (the next free one if taken)")
    ui.add_argument("--host", default="127.0.0.1", help="only 127.0.0.1 is allowed")
    ui.add_argument("--no-browser", action="store_true", help="print the URL instead of opening Edge")
    ui.add_argument(
        "--react", action="store_true", help=argparse.SUPPRESS
    )  # old flag: the React UI is the only UI
    ui.add_argument(
        "--dev", action="store_true", help="accept the Vite dev server (127.0.0.1:5173) for UI development"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    from forge.net import use_system_certificates

    use_system_certificates()  # before any HTTPS client exists (company TLS inspection, D-110)
    if args.command == "doctor":
        return asyncio.run(_doctor(args.offline))
    if args.command == "new":
        if args.standalone:
            return _new_standalone(args.new_workspace, args.profile, args.python, args.project or "")
        if args.repo is None:
            build_parser().error("forge new needs --repo (Mode A) or --standalone --project NAME (Mode B)")
        return _new(args.repo, args.new_workspace, args.app_folder, args.project or "")
    if args.command == "profile":
        return _profile(args)
    if args.command == "export":
        return _export(args.export_workspace)
    if args.command == "run":
        text = args.run_prompt or (
            args.requirement_file.read_text(encoding="utf-8") if args.requirement_file else None
        )
        return asyncio.run(_run(args.run_workspace, text, args.auto_approve, args.output_format))
    if args.command == "resume":
        return _interactive(args.resume_workspace, direct=False)
    if args.command == "diagnose":
        error = args.error_file.read_text(encoding="utf-8", errors="replace") if args.error_file else None
        return asyncio.run(_diagnose(args.diagnose_workspace, error, not args.no_run))
    if args.command == "log-summary":
        return _log_summary(args.workspace, args.log)
    if args.command == "skill":
        return _skill(args)
    if args.command == "ui":
        from forge.safety.server_security import BindError
        from forge.web.run import run_ui

        try:
            return run_ui(args.ui_workspace, args.port, args.host, args.no_browser, args.dev)
        except BindError as error:
            Console().print(str(error), markup=False)
            return 2
    if args.command == "label":
        return _label(args.eval_dir, args.no_browser)
    if args.command == "sessions":
        from forge.parity.sessions import list_sessions

        Console().print(list_sessions(), markup=False)
        return 0
    if args.command == "cleanup":
        return _cleanup(args.cleanup_workspace, args.yes)
    return _interactive(args.workspace, direct=args.direct)


def _printable(console: Console, text: str) -> str:
    """Third-party text can hold characters the Windows console cannot show; that must not stop the output."""
    encoding = console.encoding or "utf-8"
    return text.encode(encoding, errors="replace").decode(encoding)


def _skill(args: argparse.Namespace) -> int:
    from forge.config import forge_home
    from forge.parity import skill_install
    from forge.parity.skills import discover

    console = Console()
    skills_root = forge_home() / "skills"
    if args.skill_command == "list":
        for skill in sorted(discover(skills_root).values(), key=lambda s: s.name):
            console.print(_printable(console, f"{skill.name}: {skill.description}"), markup=False)
        return 0
    if args.skill_command == "remove":
        removed = skill_install.remove(args.name, skills_root)
        console.print("Removed." if removed else f"No installed skill named {args.name!r}.", markup=False)
        return 0 if removed else 1

    def confirm(candidate: skill_install.Candidate) -> bool:
        console.print(_printable(console, skill_install.summary(candidate)), markup=False)
        if args.list:
            return False
        return args.yes or input("Install this skill? [y/N] ").strip().lower() in ("y", "yes")

    try:
        lines = skill_install.add_from_source(args.source, skills_root, confirm, args.force)
    except ForgeError as error:
        console.print(str(error), markup=False)
        return 1
    console.print(_printable(console, "\n".join(lines)), markup=False)
    return 0


async def _doctor(offline: bool) -> int:
    from forge.doctor import render_results, run_doctor
    from forge.tools.web_doctor import check_web_research

    results = await run_doctor(offline=offline)
    results.insert(5, await check_web_research())  # after the basic checks, before config and models
    console = Console()
    console.print(describe())
    render_results(results, console.print)
    return 1 if any(result.status == "fail" for result in results) else 0


async def _run(workspace_path: Path, requirement: str | None, auto_approve: bool, output_format: str) -> int:
    import json

    from forge.engine.headless import EXIT_FAILED, run_headless
    from forge.session import build_session
    from forge.workspace.workspace import Workspace, WorkspaceError

    console = Console()
    try:
        host = build_session(workspace=Workspace.open(workspace_path), orchestrated=True)
    except (ConfigError, WorkspaceError) as error:
        console.print(f"Cannot start: {error}", markup=False)
        return EXIT_FAILED
    assert host.orchestrator is not None
    if not requirement and not host.orchestrator.needs_resume:
        console.print(
            "Nothing to do: give --requirement-file/-p, or a workspace with an unfinished run.", markup=False
        )
        return EXIT_FAILED
    result = await run_headless(host, requirement, auto_approve)
    if output_format == "json":
        print(
            json.dumps(
                {
                    "exit_code": result.exit_code,
                    "status": result.activity,
                    "tasks": result.tasks,
                    "errors": result.errors,
                    "output": str(workspace_path / "output"),
                },
                indent=1,
            )
        )
    else:
        console.print(f"Status: {result.activity}", markup=False)
        for task in result.tasks:
            console.print(f"  [{task['status']}] {task['id']} {task['title']} — {task['note']}", markup=False)
        for message in result.errors:
            console.print(f"Error: {message}", markup=False)
    return result.exit_code


def _new(repo: Path, workspace_path: Path, app_folder: str | None, project: str = "") -> int:
    from forge.config import forge_home
    from forge.workspace.create import create_workspace
    from forge.workspace.pyenv import find_app_folder_candidates
    from forge.workspace.repo_memory import remember_app_folder, remembered_app_folder
    from forge.workspace.workspace import WorkspaceError

    console = Console()
    home = forge_home()
    app_folder = app_folder or remembered_app_folder(home, repo)
    if app_folder is None:
        candidates = find_app_folder_candidates(repo) if repo.is_dir() else []
        if len(candidates) != 1:
            listing = ", ".join(candidates) or "none found"
            console.print(
                f"Which folder is the Python app? Candidates: {listing}. Use --app-folder.", markup=False
            )
            return 2
        app_folder = candidates[0]
    try:
        with console.status("Copying the repository..."):
            workspace = create_workspace(repo, workspace_path, app_folder)
    except WorkspaceError as error:
        console.print(f"Could not create the workspace: {error}", markup=False)
        return 1
    remember_app_folder(home, repo, app_folder)
    if project:
        workspace.info.project = project
        workspace.save_info()
    report = workspace.info.copy_report
    env = workspace.info.python_env
    console.print(f"Workspace ready: {workspace.root}", markup=False)
    console.print(
        f"  copied {report.files} files ({report.bytes / 1_048_576:.1f} MB) from {app_folder}/", markup=False
    )
    for label, items in (
        ("skipped (too large)", report.skipped_large),
        ("skipped (links)", report.skipped_links),
        ("secret files (never sent to the LLM)", report.secret_files),
    ):
        if items:
            console.print(f"  {label}: {', '.join(items)}", markup=False)
    if env is None:
        console.print(
            "  No usable venv found in the app folder; Forge will ask which interpreter to use.", markup=False
        )
    else:
        shim = " (editable install of the original detected and corrected)" if env.shim_dir else ""
        console.print(f"  interpreter: {env.python}{shim}", markup=False)
    return 0


def _cleanup(workspace_path: Path, yes: bool) -> int:
    """Spec §9.5: lists the objects Forge recorded in this workspace's scratch schema(s) and drops only
    those, after confirmation. A schema the user created is never dropped."""
    from forge.config import forge_home, load_config, load_secrets
    from forge.db.connection import DbTarget
    from forge.db.scratch import ScratchRegistry, ScratchSchema
    from forge.workspace.workspace import Workspace, WorkspaceError

    console = Console()
    try:
        workspace = Workspace.open(workspace_path)
    except WorkspaceError as error:
        console.print(str(error), markup=False)
        return 1
    home = forge_home()
    config, secrets = load_config(home), load_secrets(home)
    registry = ScratchRegistry(home)
    owned = {
        key: entry
        for key, entry in registry.load().items()
        if Path(entry.get("workspace", "")).resolve() == workspace.root.resolve()
    }
    if not owned:
        console.print("Forge created no database objects for this workspace.", markup=False)
        return 0
    status = 0
    for key, entry in owned.items():
        target_name, schema = key.split(":", 1)
        objects = ", ".join(f"{kind} {name}" for kind, name in entry.get("objects", [])) or "none"
        console.print(f"{target_name} database, schema {schema}: {objects}", markup=False)
        if not yes and input("Drop these objects? [y/N] ").strip().lower() not in ("y", "yes"):
            continue
        settings = config.postgres.connections.get(target_name)
        if settings is None:
            console.print(f"No '{target_name}' connection is configured; skipped.", markup=False)
            status = 1
            continue
        target = DbTarget(target_name, settings.url_env, settings.sslmode, settings.statement_timeout_s)
        try:
            dropped = ScratchSchema(target, secrets, schema, registry, workspace, []).cleanup()
        except Exception as error:
            console.print(f"Cleanup failed: {error}", markup=False)
            status = 1
            continue
        console.print("Dropped: " + (", ".join(dropped) or "nothing"), markup=False)
    return status


def _log_summary(workspace_path: Path | None, log_path: Path | None) -> int:
    from forge.engine.log_summary import summarize_file

    path = log_path or (
        workspace_path / ".forge" / "transcripts" / "events.jsonl" if workspace_path else None
    )
    if path is None or not path.exists():
        print("forge log-summary needs --workspace (with a transcript) or --log events.jsonl")
        return 2
    print(summarize_file(path))
    return 0


async def _diagnose(workspace_path: Path, pasted_error: str | None, fresh_run: bool) -> int:
    """Spec §6.6: exit 0 when nothing is wrong, 2 when problems were found, 1 on errors."""
    from forge.diagnose.run import run_diagnose
    from forge.session import build_session
    from forge.workspace.workspace import Workspace, WorkspaceError

    console = Console()
    try:
        workspace = Workspace.open(workspace_path)
    except WorkspaceError as error:
        console.print(str(error), markup=False)
        return 1
    host = build_session(workspace=workspace, orchestrated=False)
    await host.prepare_database()
    result = await run_diagnose(
        workspace,
        db=host.db,
        router=host.router,
        context=host.agent.context if host.agent else None,
        pasted_error=pasted_error,
        fresh_run=fresh_run,
    )
    console.print(Path(result.report_path).read_text(encoding="utf-8"), markup=False)
    tests_failed = bool(result.fresh and result.fresh.tests and not result.fresh.tests.passed)
    return 2 if result.integrity.problems or tests_failed else 0


def _new_standalone(
    workspace_path: Path, profile_name: str | None, python: str | None, project: str = ""
) -> int:
    from forge.config import forge_home
    from forge.modeb.profile import ProfileError, ProfileStore, project_slug
    from forge.modeb.workspace import create_standalone_workspace
    from forge.workspace.workspace import WorkspaceError

    console = Console()
    if not profile_name and not project:
        console.print("Mode B needs a project name: --project <name>.", markup=False)
        return 2
    try:
        store = ProfileStore(forge_home())
        if profile_name:
            profile = store.open(profile_name)
        else:  # the project's knowledge is its profile: created the first time, reused after
            slug = project_slug(project)
            profile = store.open(slug) if slug in store.names() else store.create(slug)
        workspace = create_standalone_workspace(workspace_path, profile, python)
        if project:
            workspace.info.project = project
            workspace.save_info()
    except (ProfileError, WorkspaceError, OSError) as error:
        console.print(str(error), markup=False)
        return 1
    from forge.modeb.workspace import test_runner_note

    console.print(
        f"Standalone workspace created at {workspace.root} (profile {profile.name} v{profile.version}); "
        f"pytest: {test_runner_note(workspace)}. Start with: forge --workspace {workspace.root}",
        markup=False,
    )
    return 0


def _profile(args: argparse.Namespace) -> int:
    import json
    import shutil
    from importlib import resources

    from forge.config import forge_home
    from forge.modeb.profile import ProfileError, ProfileStore

    console = Console()
    store = ProfileStore(forge_home())
    try:
        if args.action == "list":
            console.print(
                "\n".join(store.names()) or "No host profiles yet: forge profile new <name>", markup=False
            )
        elif args.action == "export-script":
            source = Path(str(resources.files("forge.modeb") / "forge_structure_export.py"))
            target = args.out or Path("forge_structure_export.py")
            shutil.copyfile(source, target)
            console.print(
                f"Wrote {target}. Copy it to the host machine and run it there YOURSELF "
                "(Forge never runs it):\n"
                "  python forge_structure_export.py <app folder> --out structure_export [--mask terms.txt]\n"
                "Review structure_export.md, then: forge profile import <name> structure_export.json",
                markup=False,
            )
        elif not args.name:
            console.print(f"forge profile {args.action} needs a profile name.", markup=False)
            return 2
        elif args.action == "new":
            profile = store.create(args.name, [t for t in args.terms.split(",") if t.strip()])
            console.print(f"Profile {profile.name} created at {profile.root}.", markup=False)
        elif args.action == "show":
            console.print(store.open(args.name).essentials(max_chars=50_000), markup=False)
        elif args.action == "import":
            if args.file is None:
                console.print("forge profile import <name> <structure_export.json>", markup=False)
                return 2
            report = store.open(args.name).import_structure(json.loads(args.file.read_text(encoding="utf-8")))
            console.print(f"Imported: {report.summary()}", markup=False)
    except (ProfileError, OSError, ValueError) as error:
        console.print(str(error), markup=False)
        return 1
    return 0


def _label(eval_dir: Path, no_browser: bool) -> int:
    import uvicorn

    from forge.safety.server_security import ServerSecurity
    from forge.vision.labeler import create_label_app
    from forge.web.run import free_port, open_browser

    if not (eval_dir / "samples").is_dir():
        Console().print(f"{eval_dir} has no samples/ folder.", markup=False)
        return 2
    port = free_port(8766)
    security = ServerSecurity(port=port)
    Console().print(f"Labelling {eval_dir}: {security.url()}  (Ctrl+C to stop)", markup=False)
    if not no_browser:
        open_browser(security.url())
    uvicorn.run(create_label_app(eval_dir, security), host="127.0.0.1", port=port, log_level="warning")
    return 0


def _export(workspace_path: Path) -> int:
    from forge.workspace.output import build_output
    from forge.workspace.workspace import Workspace, WorkspaceError

    console = Console()
    try:
        report = build_output(Workspace.open(workspace_path))
    except WorkspaceError as error:
        console.print(str(error), markup=False)
        return 1
    counts = {
        status: sum(1 for f in report.files if f.status == status)
        for status in ("added", "modified", "deleted")
    }
    console.print(
        f"output/ rebuilt: {counts['added']} added, {counts['modified']} modified, "
        f"{counts['deleted']} deleted. See output/COPY_INSTRUCTIONS.md",
        markup=False,
    )
    return 0


def _interactive(workspace_path: Path | None, direct: bool = False) -> int:
    from forge.session import build_session
    from forge.ui.console import run_console
    from forge.workspace.workspace import Workspace, WorkspaceError

    try:
        workspace = Workspace.open(workspace_path) if workspace_path else None
        host = build_session(workspace=workspace, orchestrated=not direct)
    except (ConfigError, WorkspaceError) as error:
        Console().print(f"Cannot start: {error}\nRun 'forge doctor' for details.", markup=False)
        return 2
    asyncio.run(run_console(host))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

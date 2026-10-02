"""Mode B, phase 2 (D-141): scaffolding a frontend from scratch for a standalone workspace that has no host
to conform to. `create_standalone_workspace` stays Python-only (most Mode B projects never need a frontend,
D-141's "lazy, not eager" call) — this tool is how the model adds one the first time a requirement needs it.

The stack is the model's own per-project judgment (D-141: no one fixed default), so the tool exposes both a
structured, common-case shape (framework + typescript, translated into the matching `npm create vite@latest`
template) and a free-form `create_command` escape hatch for anything the structured shape doesn't cover
(Angular's own CLI, a framework with no Vite template, etc.). Whichever form is used, the actual scaffold runs
through the existing shell/approval mechanism (`toolkit/shell.py`'s `execute`) like any other install —
per D-141, deliberately not a hand-written offline template."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.shell import execute
from forge.workspace.nodeenv import detect_node_environment

SCAFFOLD_TIMEOUT_S = 600

Framework = Literal["react", "vue", "svelte", "preact", "vanilla", "other"]

# Vite's own template names (https://vitejs.dev/guide/#scaffolding-your-first-vite-project), the common case
# D-141 says to make easy. "other" has no template: create_command is required for it.
_VITE_TEMPLATES: dict[Framework, str] = {
    "react": "react",
    "vue": "vue",
    "svelte": "svelte",
    "preact": "preact",
    "vanilla": "vanilla",
}


class SetupFrontend(Tool):
    name = "setup_frontend"
    description = (
        "Scaffold a brand-new frontend in this standalone (Mode B) workspace, e.g. when a requirement needs "
        "a web UI and none exists yet. Runs the real scaffolder (npm create vite@latest by default) through "
        "the normal shell approval flow, then wires the result up for verify. Use this instead of "
        "hand-writing package.json/build config yourself. Only usable once per workspace; if you need a "
        "different stack, ask the user before calling it again."
    )

    class Args(ToolArgs):
        folder: str = Field(
            default="frontend", description="Subfolder of project/ to scaffold into, e.g. 'frontend'."
        )
        framework: Framework = Field(
            default="react",
            description="Common frameworks map to a Vite template; 'other' needs create_command.",
        )
        typescript: bool = Field(default=True, description="Use the '-ts' variant of the chosen template.")
        create_command: str | None = Field(
            default=None,
            description=(
                "Exact scaffold command to run instead of the framework/typescript shorthand, e.g. "
                "'npm create vue@latest . -- --typescript' or an Angular CLI invocation. Required when "
                "framework is 'other'."
            ),
        )

        @model_validator(mode="after")
        def _require_command_for_other(self) -> SetupFrontend.Args:
            if self.framework == "other" and not self.create_command:
                raise ValueError("framework 'other' needs an explicit create_command.")
            return self

    def summary(self, args: SetupFrontend.Args) -> str:
        return f"setup_frontend {args.folder} ({args.framework})"

    def command(self, args: SetupFrontend.Args, context: ToolContext) -> str | None:
        return _scaffold_command(args)

    async def run(self, args: SetupFrontend.Args, context: ToolContext) -> ToolResult:
        workspace = context.workspace
        if not workspace.mode_b:
            return ToolResult(
                ok=False,
                content="setup_frontend is only for standalone (Mode B) workspaces: Mode A already has an "
                "existing repo to add a frontend to.",
            )
        if workspace.info.node_env is not None:
            return ToolResult(
                ok=False,
                content=f"A frontend is already set up at {workspace.info.node_env.app_dir!r} "
                "(node_env is already populated). Work in that folder, or ask the user before replacing it.",
            )
        target = workspace.repo_dir / args.folder
        if target.exists() and any(target.iterdir()):
            return ToolResult(
                ok=False,
                content=f"project/{args.folder} already exists and is not empty. Choose an empty folder "
                "name, or ask the user before overwriting it.",
            )
        target.mkdir(parents=True, exist_ok=True)
        command = _scaffold_command(args)
        # cwd is host-relative (workspace.path_of resolves it under project/ in Mode B), matching how
        # run_command's own cwd argument works; passing "project/<folder>" here would be misread as
        # already-project-relative and rejected (see Workspace.path_of's guard for that mistake).
        result = await execute(context, command, SCAFFOLD_TIMEOUT_S, args.folder)
        if not result.ok:
            return ToolResult(
                ok=False,
                content=f"Scaffolding failed, no node_env was set:\n{result.content}",
                meta=result.meta,
            )
        node_env = detect_node_environment(target)
        if node_env is None:
            return ToolResult(
                ok=False,
                content="The scaffold command exited cleanly but no package.json/node was found afterwards "
                f"in project/{args.folder}; nothing was wired up. Check the command's actual output above.",
            )
        workspace.info.node_env = node_env
        workspace.save_info()
        return ToolResult(
            ok=True,
            content=(
                f"Frontend scaffolded at project/{args.folder} ({args.framework}"
                f"{', TypeScript' if args.typescript else ''}) using {node_env.package_manager}. "
                "node_env is now set, so verify/the React ladder applies to files in that folder going "
                f"forward. Run `{node_env.install_command}` in that folder next if the scaffolder didn't "
                "already install dependencies."
            ),
        )


def _scaffold_command(args: SetupFrontend.Args) -> str:
    if args.create_command:
        return args.create_command
    template = _VITE_TEMPLATES[args.framework]
    if args.typescript:
        template = f"{template}-ts"
    # Scaffold into the current directory (the folder this command runs in is already project/<folder>/,
    # made and cwd'd into by run()), matching Vite's own "npm create vite@latest ." convention.
    return f"npm create vite@latest . -- --template {template}"

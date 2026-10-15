"""`shadcn_setup`: a Vite + React project made ready for shadcn/ui, and shadcn initialised, in one call (D-402).

A fresh Vite project fails `npx shadcn@latest init` with "No Tailwind CSS configuration found" and "Could not find valid path aliases" until Tailwind v4 is installed and
wired into Vite, the `@/` alias exists in vite.config.ts and in both tsconfig files, and the stylesheet imports Tailwind. A weaker model gets one of the five steps wrong or
runs `init` first and gives up, so the steps are code. Company networks that inspect HTTPS are handled by the shell layer: a step that fails on a certificate is repeated once
after DebCraft has exported the Windows certificates for Node (forge.net, toolkit.shell)."""

from __future__ import annotations

import json
import re
from typing import Literal

from pydantic import Field

from forge.net import looks_like_certificate_error
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.shell import execute

TAILWIND_IMPORT = '@import "tailwindcss";'
ALIAS_PATHS = '"baseUrl": ".",\n    "paths": { "@/*": ["./src/*"] }'
STEP_TIMEOUT_S = 600


def patch_index_css(text: str) -> str:
    """The Tailwind import first; the template's own rules stay below it."""
    if re.search(r"""@import\s+["']tailwindcss["']""", text):
        return text
    return f"{TAILWIND_IMPORT}\n\n{text}" if text.strip() else f"{TAILWIND_IMPORT}\n"


def patch_vite_config(text: str) -> str | None:
    """The Vite config with the Tailwind plugin and the `@` alias, or None when its shape is not the usual `defineConfig({ plugins: [react()] })`."""
    if "@tailwindcss/vite" in text and "resolve" in text and "alias" in text:
        return text
    if "defineConfig({" not in text:
        return None
    patched = text
    imports: list[str] = []
    if 'from "path"' not in patched and "from 'path'" not in patched and "node:path" not in patched:
        imports.append('import path from "path"')
    if "@tailwindcss/vite" not in patched:
        imports.append('import tailwindcss from "@tailwindcss/vite"')
    if imports:
        patched = "\n".join(imports) + "\n" + patched
    if "tailwindcss()" not in patched:
        match = re.search(r"plugins:\s*\[", patched)
        if match is None:
            patched = patched.replace("defineConfig({", "defineConfig({\n  plugins: [tailwindcss()],", 1)
        else:
            patched = patched[: match.end()] + "tailwindcss(), " + patched[match.end() :]
    if not re.search(r"\balias\s*:", patched):
        alias = '  resolve: {\n    alias: { "@": path.resolve(__dirname, "./src") },\n  },\n'
        index = patched.rindex("})")
        before = patched[:index].rstrip()
        if not before.endswith(","):
            before += ","
        patched = before + "\n" + alias + patched[index:]
    return patched


def patch_tsconfig(text: str) -> str:
    """`baseUrl` and the `@/*` path added to compilerOptions (created when the file has none); comments and layout elsewhere are kept."""
    if '"paths"' in text and "@/*" in text:
        return text
    match = re.search(r'"compilerOptions"\s*:\s*\{', text)
    if match:
        return text[: match.end()] + "\n    " + ALIAS_PATHS + "," + text[match.end() :]
    first = text.find("{")
    if first == -1:
        return text
    return text[: first + 1] + '\n  "compilerOptions": {\n    ' + ALIAS_PATHS + "\n  }," + text[first + 1 :]


def dependency_names(package_json: str) -> set[str]:
    try:
        data = json.loads(package_json)
    except ValueError:
        return set()
    return set(data.get("dependencies", {})) | set(data.get("devDependencies", {}))


class ShadcnSetup(Tool):
    name = "shadcn_setup"
    description = (
        "Set up shadcn/ui in a Vite + React + TypeScript project (created first when the folder has no package.json): installs Tailwind v4 and its Vite plugin, writes the `@/` alias "
        "into vite.config.ts and both tsconfig files, imports Tailwind in src/index.css, runs `npx shadcn@latest init` and adds the components you name. Safe to run again. "
        "On networks that inspect HTTPS it repeats a step that failed on a certificate after exporting the Windows certificates. Use it instead of running npx shadcn yourself."
    )

    class Args(ToolArgs):
        project_dir: str = Field(
            default=".",
            description="The project folder relative to the repository root (where package.json is or should be).",
        )
        base: Literal["radix", "base"] = Field(
            default="radix",
            description="The primitives under the components: Radix UI (most examples and documentation) or Base UI.",
        )
        components: list[str] = Field(
            default_factory=list,
            description="Components to add after init, e.g. ['button', 'card', 'input', 'dialog'].",
        )
        reason: str = ""

    def summary(self, args: ShadcnSetup.Args) -> str:
        return f"set up shadcn/ui in {args.project_dir}" + (
            f" with {', '.join(args.components)}" if args.components else ""
        )

    async def step(self, context: ToolContext, command: str, cwd: str) -> ToolResult:
        """One command; a certificate failure is repeated once because the shell layer has switched to the Windows certificate bundle by then."""
        result = await execute(context, command, STEP_TIMEOUT_S, cwd)
        if (
            not result.ok
            and looks_like_certificate_error(result.content)
            and "run the same command again" in result.content
        ):
            result = await execute(context, command, STEP_TIMEOUT_S, cwd)
        return result

    def read(self, context: ToolContext, relative: str) -> str | None:
        try:
            return context.workspace.read_text(relative)[0]
        except Exception:  # a missing file is a normal answer here
            return None

    async def run(self, args: ShadcnSetup.Args, context: ToolContext) -> ToolResult:
        if context.shell is None:
            return ToolResult(ok=False, content="No shell is available in this session.")
        folder = args.project_dir.strip().strip("/\\") or "."
        prefix = "" if folder == "." else folder + "/"
        done: list[str] = []

        def failure(step: str, result: ToolResult) -> ToolResult:
            return ToolResult(
                ok=False,
                content="Done so far: "
                + (", ".join(done) or "nothing")
                + f".\nFailed at: {step}\n{result.content[-2500:]}",
            )

        if self.read(context, prefix + "package.json") is None:
            created = await self.step(
                context, "npm create vite@latest . -- --template react-ts --no-interactive", folder
            )
            if not created.ok:
                return failure("creating the Vite project", created)
            done.append("created a Vite + React + TypeScript project")
        package = self.read(context, prefix + "package.json") or ""
        if "vite" not in dependency_names(package):
            return ToolResult(
                ok=False,
                content="This setup is for Vite projects (package.json has no vite). For Next.js run `npx shadcn@latest init` yourself; it configures its own Tailwind and alias.",
            )
        installed = dependency_names(package)
        wanted = [name for name in ("tailwindcss", "@tailwindcss/vite") if name not in installed]
        commands = [] if context.workspace.path_of(prefix + "node_modules").exists() else ["npm install"]
        if wanted:
            commands.append("npm install " + " ".join(wanted))
        if "@types/node" not in installed:
            commands.append("npm install -D @types/node")
        for command in commands:
            result = await self.step(context, command, folder)
            if not result.ok:
                return failure(command, result)
            done.append(command)

        edits: list[tuple[str, str | None, str]] = [
            (prefix + "src/index.css", self.read(context, prefix + "src/index.css"), "css"),
            (prefix + "vite.config.ts", self.read(context, prefix + "vite.config.ts"), "vite"),
            (prefix + "tsconfig.json", self.read(context, prefix + "tsconfig.json"), "ts"),
            (prefix + "tsconfig.app.json", self.read(context, prefix + "tsconfig.app.json"), "ts"),
        ]
        for relative, text, kind in edits:
            if text is None:
                if kind == "css":
                    text = ""
                else:
                    continue
            patched = (
                patch_index_css(text)
                if kind == "css"
                else patch_vite_config(text)
                if kind == "vite"
                else patch_tsconfig(text)
            )
            if patched is None:
                return ToolResult(
                    ok=False,
                    content=f'Done so far: {", ".join(done)}.\n{relative} does not have the usual shape, so it was not changed. Edit it so that it imports `tailwindcss from "@tailwindcss/vite"` and `path`, '
                    'lists `tailwindcss()` in plugins and has `resolve: { alias: { "@": path.resolve(__dirname, "./src") } }`, then call shadcn_setup again.',
                )
            if patched != text:
                context.workspace.write_text(relative, patched, args.reason or "shadcn/ui prerequisites")
                done.append(f"updated {relative}")
        context.last_edit_step = context.step

        init = await self.step(
            context, f"npx --yes shadcn@latest init -b {args.base} -y --no-monorepo", folder
        )
        if not init.ok:
            return failure("shadcn init", init)
        done.append("shadcn init")
        if args.components:
            add = await self.step(
                context, "npx --yes shadcn@latest add " + " ".join(args.components) + " -y", folder
            )
            if not add.ok:
                return failure("shadcn add", add)
            done.append("added " + ", ".join(args.components))
        return ToolResult(
            ok=True,
            content="shadcn/ui is set up. "
            + "; ".join(done)
            + f".\nComponents are in {prefix}src/components/ui; import them as `@/components/ui/<name>`. "
            "Edit the colours in the project's src/index.css (the CSS variables), compose pages from the components, and screenshot the result: a shadcn page that still looks stock has not been designed.",
        )

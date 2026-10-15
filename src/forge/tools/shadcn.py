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
        preset: Literal["nova", "vega", "maia", "lyra", "mira", "luma", "sera", "rhea"] = Field(
            default="nova",
            description="The look of the generated components (nova: Lucide icons and Geist; the others differ in radius, density and font).",
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

        if folder != ".":  # the shell refuses a working folder that does not exist yet
            context.workspace.jail.check(context.workspace.path_of(folder)).mkdir(parents=True, exist_ok=True)
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

        # Without -p the CLI asks which preset to use and, with no terminal, stops there and still exits 0 (found by running this tool for real, D-402).
        init = await self.step(
            context, f"npx --yes shadcn@latest init -b {args.base} -p {args.preset} -y --no-monorepo", folder
        )
        if not init.ok:
            return failure("shadcn init", init)
        if self.read(context, prefix + "components.json") is None:
            return failure("shadcn init (it ended without writing components.json)", init)
        done.append("shadcn init")
        if args.components:
            add = await self.step(
                context, "npx --yes shadcn@latest add " + " ".join(args.components) + " -y", folder
            )
            if not add.ok:
                return failure("shadcn add", add)
            absent = [
                n
                for n in args.components
                if not context.workspace.path_of(prefix + f"src/components/ui/{n}.tsx").exists()
            ]
            if absent:
                return failure(
                    f"shadcn add (no file for: {', '.join(absent)}; the registry may call them something else)",
                    add,
                )
            done.append("added " + ", ".join(args.components))
        return ToolResult(
            ok=True,
            content="shadcn/ui is set up. "
            + "; ".join(done)
            + f".\nComponents are in {prefix}src/components/ui; import them as `@/components/ui/<name>`. "
            "Edit the colours in the project's src/index.css (the CSS variables), compose pages from the components, and screenshot the result: a shadcn page that still looks stock has not been designed.",
        )


# What may be installed, and under whose terms (D-437). Magic UI is MIT and may be named; the others are chosen by the user on the site and given as a link they typed,
# because their licences differ per component and per author and a model must not pick someone's component by itself.
NAMED_REGISTRIES = {"@magicui/": "MIT (Magic UI)"}
CHOSEN_HOSTS = {
    "21st.dev": "the author's own licence, which the site does not state: open the component page and check it, keep the author's credit (21st.dev's terms ask for it)",
    "ui.aceternity.com": "the Aceternity licence: end products for yourself or clients are allowed, reselling it as a theme or template is not; the terms of the free components are not stated on the site, so check the component page",
    "magicui.design": "MIT (Magic UI)",
    "ui.shadcn.com": "MIT (shadcn/ui)",
}
INSTALL_ADDRESS = re.compile(r"https://[^\s\"'`]+")


def classify_source(source: str, typed: set[str]) -> tuple[str, str] | str:
    """(the address or name to give the CLI, whose terms apply) or the reason it is refused."""
    text = source.strip()
    for prefix, terms in NAMED_REGISTRIES.items():
        if text.startswith(prefix) and re.fullmatch(r"@[a-z0-9-]+/[a-z0-9][a-z0-9._/-]*", text):
            return text, terms
    found = INSTALL_ADDRESS.search(text)
    if found is None:
        return "Give a Magic UI name such as @magicui/marquee, or the install address of a component the user chose (https://21st.dev/r/...)."
    address = found.group(0).rstrip(".,;)")
    host = address.split("/")[2].lower()
    if host not in CHOSEN_HOSTS:
        return f"{host} is not one of the registries this tool installs from ({', '.join(sorted(CHOSEN_HOSTS))})."
    if address not in typed:
        return (
            f"The user has not typed {address} in a message, so it is not installed: these components carry the licence of their author, and the user must choose them. "
            "Ask them to send the install link of the component they want."
        )
    return address, CHOSEN_HOSTS[host]


class AddUiComponent(Tool):
    name = "add_ui_component"
    read_only = False
    description = (
        "Add one component from a shadcn-compatible registry to a project that shadcn_setup has set up: a Magic UI component by name (`@magicui/marquee`, MIT), or the install address "
        "of a component the USER chose on 21st.dev, Aceternity UI, Magic UI or shadcn (a link they typed in a message; you cannot use one you found yourself, because each author licenses "
        "their own work). The component's files are copied into the project, it is recorded in NOTICES.md with whose terms apply, and you tell the user in your final message which "
        "components came from where and that they must check the licence of a 21st.dev or Aceternity component before the site ships."
    )

    class Args(ToolArgs):
        source: str = Field(
            description="`@magicui/<name>`, or the install address (or the whole `npx shadcn add` line) the user sent"
        )
        project_dir: str = Field(default=".", description="The project folder (where components.json is)")
        reason: str = ""

    def summary(self, args: AddUiComponent.Args) -> str:
        return f"add component {args.source[:70]}"

    async def run(self, args: AddUiComponent.Args, context: ToolContext) -> ToolResult:
        if context.shell is None:
            return ToolResult(ok=False, content="No shell is available in this session.")
        typed = context.user_urls() if context.user_urls is not None else set()
        verdict = classify_source(args.source, typed)
        if isinstance(verdict, str):
            return ToolResult(ok=False, content=verdict)
        target, terms = verdict
        folder = args.project_dir.strip().strip("/\\") or "."
        prefix = "" if folder == "." else folder + "/"
        try:
            context.workspace.read_text(prefix + "components.json")
        except Exception:
            return ToolResult(
                ok=False, content=f"No components.json in {folder}: run shadcn_setup there first."
            )
        result = await execute(context, f'npx --yes shadcn@latest add "{target}" -y', STEP_TIMEOUT_S, folder)
        if not result.ok:
            return ToolResult(ok=False, content="The component was not added.\n" + result.content[-2500:])
        line = f"- component `{target}`: terms: {terms}\n"
        try:
            existing = context.workspace.read_text(prefix + "NOTICES.md")[0]
        except Exception:
            existing = "# Notices\n\nThird-party code and pictures used in this project.\n"
        if line not in existing:
            context.workspace.write_text(
                prefix + "NOTICES.md",
                existing.rstrip("\n") + "\n" + line,
                args.reason or "component recorded in NOTICES.md",
            )
        context.last_edit_step = context.step
        return ToolResult(
            ok=True,
            content=f"Added {target}. Terms: {terms}. Recorded in NOTICES.md. Import it from the path the CLI printed, restyle it with the project's tokens, and screenshot the page.\n{result.content[-800:]}",
        )

"""library_versions: which versions of a Python library the project uses and which exist, and what a name looks like in
any of them (D-642).

`library_api` answers for the installed version only. Code for a library that changes fast (LangChain, LangGraph) also
needs the others: is the installed one old, what did an example for another version use, what would an upgrade break."""

from __future__ import annotations

import asyncio
import re
import zipfile
from pathlib import Path
from typing import Literal

import httpx
from pydantic import Field

from forge.deps.model import normalise
from forge.deps.published import (
    NAME,
    VERSION,
    Published,
    Release,
    WheelCode,
    fetch_published,
    fetch_wheel,
    line_of,
    pick_release,
    version_key,
)
from forge.deps.scan import installed_python_packages, scan_project
from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.powershell import ps_quote
from forge.toolkit.shell import execute

FAMILY = {
    "langchain": (
        "langchain",
        "langchain-core",
        "langgraph",
        "langgraph-prebuilt",
        "langchain-openai",
        "langchain-classic",
        "langchain-community",
    ),
}
MAX_LINES = 8
MAX_WHEELS = 6
_wheels: dict[tuple[str, str], bytes] = {}  # releases never change, so a download is kept for the session


def venv_of(context: ToolContext) -> Path | None:
    python = getattr(context.shell, "python", None)
    return Path(python).parent.parent if python else None


def overview(
    name: str,
    declared: list[str],
    installed: str | None,
    published: Published | None,
    problem: str,
) -> str:
    lines = [f"## {name}"]
    lines.append(f"declared in the project: {'; '.join(declared) or 'not declared'}")
    lines.append(f"installed in the project's environment: {installed or 'not installed'}")
    if published is None or not published.releases:
        lines.append(f"published versions: {problem or 'none found'}")
        return "\n".join(lines)
    usable = [r for r in published.releases if not r.yanked] or published.releases
    latest = usable[-1]
    python = f", needs Python {latest.requires_python}" if latest.requires_python else ""
    lines.append(f"latest: {latest.version} ({latest.date or 'date unknown'}{python})")
    if installed:
        newer = sum(1 for r in usable if version_key(r.version) > version_key(installed))
        lines.append(f"releases newer than the installed one: {newer}")
        if line_of(installed).split(".")[0] != latest.version.split(".")[0]:
            lines.append(
                "The installed major version differs from the latest: examples for the latest may not run here."
            )
    newest: dict[str, Release] = {}
    for release in usable:
        newest[line_of(release.version)] = release
    recent = sorted(newest.values(), key=lambda r: version_key(r.version))[-MAX_LINES:]
    lines.append("newest of each line: " + ", ".join(f"{r.version} ({r.date})" for r in recent))
    related = [r for r in published.requires if re.match(r"(?i)lang", r)]
    if related:
        lines.append("the latest needs: " + "; ".join(related))
    return "\n".join(lines)


class LibraryVersions(Tool):
    name = "library_versions"
    description = (
        "Versions of Python libraries, the installed one, the latest and the earlier ones. action `overview`: for each of "
        "`packages` (langchain stands for the whole LangChain family) what the project declares, what is installed, the "
        "latest release and the newest of each earlier line. action `api`: what `symbol` looks like in other versions: "
        "signature, deprecation, or that it does not exist, for each of `versions` ('latest', '1.0.0', or a line such as "
        "'0.3'), read from the published package without installing it. For the installed version use library_api."
    )
    read_only = True
    sends_outside = True
    output_kind = "tool"

    class Args(ToolArgs):
        action: Literal["overview", "api"] = "overview"
        packages: list[str] = Field(
            default_factory=lambda: ["langchain"],
            description="package names as on PyPI; for api the one package that holds the symbol",
        )
        symbol: str = Field(
            default="", description="for api: a dotted path, e.g. langchain.agents.create_agent"
        )
        versions: list[str] = Field(
            default_factory=lambda: ["latest"], description="for api: up to four versions or lines"
        )

    def summary(self, args: LibraryVersions.Args) -> str:
        if args.action == "api":
            return f"library versions {args.symbol} in {', '.join(args.versions)}"
        return f"library versions {', '.join(args.packages)}"

    async def run(self, args: LibraryVersions.Args, context: ToolContext) -> ToolResult:
        bad = [p for p in args.packages if not NAME.fullmatch(p)]
        bad += [v for v in args.versions if v != "latest" and not VERSION.fullmatch(v)]
        if bad or not args.packages:
            return ToolResult(
                ok=False, content=f"Not a package name or version: {', '.join(bad) or '(none given)'}"
            )
        if args.action == "api":
            return await self._api(args, context)
        return await self._overview(args, context)

    async def _overview(self, args: LibraryVersions.Args, context: ToolContext) -> ToolResult:
        names = list(dict.fromkeys(n for p in args.packages for n in FAMILY.get(p.lower(), (p,))))[:12]
        venv = venv_of(context)
        installed = await asyncio.to_thread(installed_python_packages, venv) if venv else {}
        known = []
        if context.workspace is not None:
            known = await asyncio.to_thread(scan_project, context.workspace.repo_dir, None)
        blocks = []
        for name, (published, problem) in zip(
            names, await asyncio.gather(*(self._published(n, context) for n in names)), strict=True
        ):
            slug = normalise(name)
            declared = [
                f"{d.version or 'no version'} ({d.file})"
                for d in known
                if d.direct and normalise(d.name) == slug
            ]
            have = installed.get(slug)
            blocks.append(overview(name, declared, have[1] if have else None, published, problem))
        return ToolResult(ok=True, content="\n\n".join(blocks))

    async def _published(self, name: str, context: ToolContext) -> tuple[Published | None, str]:
        try:
            return await asyncio.to_thread(fetch_published, name), ""
        except (httpx.HTTPError, ValueError) as error:
            problem = f"PyPI could not be read ({type(error).__name__})"
        releases = await self._from_pip(name, context)
        if releases:
            return Published(name, releases), ""
        return None, problem + ", and pip could not list them either"

    @staticmethod
    async def _from_pip(name: str, context: ToolContext) -> list[Release]:
        """pip knows the company's package index (pip.ini), which PyPI's own address does not go through."""
        if context.shell is None or not context.shell.python:
            return []
        command = f"& {ps_quote(str(context.shell.python))} -m pip index versions {ps_quote(name)}"
        result = await execute(context, command, 60, None)
        found = re.search(r"Available versions: (.+)", result.content) if result.ok else None
        if found is None:
            return []
        versions = [v.strip() for v in found.group(1).split(",")]
        return sorted(
            (Release(v) for v in versions if VERSION.fullmatch(v)), key=lambda r: version_key(r.version)
        )

    async def _wheel(self, name: str, release: Release, context: ToolContext) -> bytes:
        key = (normalise(name), release.version)
        if key in _wheels:
            return _wheels[key]
        if release.wheel_url:
            data = await asyncio.to_thread(fetch_wheel, release.wheel_url)
        else:
            data = await self._wheel_from_pip(name, release.version, context)
        while len(_wheels) >= MAX_WHEELS:
            _wheels.pop(next(iter(_wheels)))
        _wheels[key] = data
        return data

    @staticmethod
    async def _wheel_from_pip(name: str, version: str, context: ToolContext) -> bytes:
        if context.shell is None or not context.shell.python or context.workspace is None:
            raise ValueError("the release has no pure Python wheel to read")
        folder = context.workspace.forge_dir / "tmp" / "wheels" / f"{normalise(name)}-{version}"
        command = (
            f"& {ps_quote(str(context.shell.python))} -m pip download --no-deps --only-binary=:all: "
            f"--dest {ps_quote(str(folder))} {ps_quote(f'{name}=={version}')}"
        )
        await execute(context, command, 120, None)
        wheel = next(iter(folder.glob("*.whl")), None) if folder.is_dir() else None
        if wheel is None:
            raise ValueError("pip could not download this release")
        return wheel.read_bytes()

    async def _api(self, args: LibraryVersions.Args, context: ToolContext) -> ToolResult:
        if not re.fullmatch(r"[A-Za-z_][\w.]*", args.symbol):
            return ToolResult(
                ok=False, content="api needs `symbol`: a dotted path such as langchain.agents.create_agent"
            )
        name = args.packages[0]
        published, problem = await self._published(name, context)
        if published is None:
            return ToolResult(ok=False, content=f"{name}: {problem}")
        blocks = []
        for wanted in list(dict.fromkeys(args.versions))[:4]:
            release = pick_release(published, wanted)
            if release is None:
                blocks.append(f"## {name} {wanted}\nno such release")
                continue
            try:
                data = await self._wheel(name, release, context)
                text = await asyncio.to_thread(lambda d=data: WheelCode(d).describe(args.symbol))  # type: ignore[misc]
            except (httpx.HTTPError, ValueError, OSError, zipfile.BadZipFile) as error:
                text = f"could not be read: {error or type(error).__name__}"
            blocks.append(f"## {name} {release.version} {release.date}\n{text}")
        return ToolResult(ok=True, content="\n\n".join(blocks))

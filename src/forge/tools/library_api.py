"""library_api: what the INSTALLED version of a Python library really offers (TODO C8, D-372).

Models invent method names and arguments of libraries they know only from memory. This tool asks the app's own interpreter (so the version is the one
that will run): the installed version, the public names of a module or class with their signatures, one symbol with its signature and docstring, or a
search by word. A name that does not exist is answered with the nearest real names, which is the attribute-level check an import check cannot give.
It reads installed code only: no network, nothing is written."""

from __future__ import annotations

import base64
import json

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult
from forge.toolkit.powershell import ps_quote
from forge.toolkit.shell import execute

# Runs in the app's interpreter: standard library only. Prints one JSON object.
INTROSPECT = r"""
import difflib, importlib, importlib.metadata as md, inspect, json, pkgutil, sys

package, symbol, query = sys.argv[1], sys.argv[2], sys.argv[3]
symbol = "" if symbol == "-" else symbol
query = "" if query == "-" else query
LIMIT = 70


def one_line(obj):
    doc = inspect.getdoc(obj) or ""
    return doc.strip().splitlines()[0][:110] if doc.strip() else ""


def signature(obj):
    try:
        return str(inspect.signature(obj))
    except (TypeError, ValueError):
        return "(...)"


def kind(obj):
    if inspect.ismodule(obj):
        return "module"
    if inspect.isclass(obj):
        return "class"
    if inspect.isroutine(obj):
        return "function"
    return type(obj).__name__


def names_of(obj):
    found = []
    for name in sorted(dir(obj)):
        if name.startswith("_"):
            continue
        try:
            value = getattr(obj, name)
        except Exception:
            continue
        found.append((name, value))
    return found


def resolve(path):
    parts = path.split(".")
    for cut in range(len(parts), 0, -1):
        try:
            current = importlib.import_module(".".join(parts[:cut]))
        except Exception:
            continue
        for index in range(cut, len(parts)):
            if not hasattr(current, parts[index]):
                return None, ".".join(parts[:index]), current, parts[index]
            current = getattr(current, parts[index])
        return current, path, None, None
    return None, "", None, parts[0]


out = {"package": package}
try:
    out["version"] = md.version(package.split(".")[0].replace("_", "-"))
except Exception:
    try:
        out["version"] = md.version(package.split(".")[0])
    except Exception:
        out["version"] = None
out["python"] = sys.version.split()[0]
target = symbol or package
out["target"] = target
obj, where, parent, missing = resolve(target)
if obj is None and parent is None:
    out["error"] = "cannot import " + (missing or target) + " (not installed in this environment, or it fails on import)"
elif obj is None:
    close = difflib.get_close_matches(missing, [n for n, _ in names_of(parent)], n=6, cutoff=0.5)
    out["error"] = target + " does not exist: " + where + " has no attribute " + repr(missing)
    out["nearest"] = close
    out["available"] = [n for n, _ in names_of(parent)][:LIMIT]
else:
    out["kind"] = kind(obj)
    if not inspect.ismodule(obj):
        out["signature"] = signature(obj)
    out["doc"] = (inspect.getdoc(obj) or "")[:2500]
    try:
        out["file"] = inspect.getsourcefile(obj) or ""
    except (TypeError, OSError):
        out["file"] = ""
    if query:
        pool = names_of(obj)
        if inspect.ismodule(obj) and hasattr(obj, "__path__"):
            pool += [(m.name, None) for m in pkgutil.iter_modules(obj.__path__)]
        out["matches"] = [(n, kind(v) if v is not None else "submodule", signature(v) if callable(v) else "", one_line(v) if v is not None else "") for n, v in pool if query.lower() in n.lower()][:LIMIT]
    elif inspect.ismodule(obj) or inspect.isclass(obj):
        members = names_of(obj)
        out["members"] = [(n, kind(v), signature(v) if callable(v) else "", one_line(v)) for n, v in members][:LIMIT]
        out["member_count"] = len(members)
        if inspect.ismodule(obj) and hasattr(obj, "__path__"):
            out["submodules"] = [m.name for m in pkgutil.iter_modules(obj.__path__)][:LIMIT]
print(json.dumps(out, default=str))
"""


def render(data: dict[str, object]) -> str:
    """The JSON the interpreter printed, as text for the model."""
    head = (
        f"{data.get('package')} {data.get('version') or '(version unknown)'} on Python {data.get('python')}"
    )
    if "error" in data:
        lines = [head, f"NOT FOUND: {data['error']}"]
        if data.get("nearest"):
            lines.append("Nearest real names: " + ", ".join(str(n) for n in data["nearest"]))  # type: ignore[attr-defined]
        if data.get("available"):
            lines.append("Public names there: " + ", ".join(str(n) for n in data["available"]))  # type: ignore[attr-defined]
        return "\n".join(lines)
    lines = [head, f"{data.get('target')}{data.get('signature', '')}  [{data.get('kind')}]"]
    if data.get("file"):
        lines.append(f"defined in {data['file']}")
    if data.get("doc"):
        lines.append("")
        lines.append(str(data["doc"]))
    for title, key in (("Matches", "matches"), ("Public members", "members")):
        rows = data.get(key)
        if rows:
            lines.append("")
            suffix = (
                f" ({data.get('member_count')} in all)"
                if key == "members" and data.get("member_count")
                else ""
            )
            lines.append(f"{title}{suffix}:")
            for name, kind, signature, summary in rows:  # type: ignore[attr-defined]
                lines.append(
                    f"  {name}{signature if kind in ('function', 'class') else ''}  [{kind}]"
                    + (f" {summary}" if summary else "")
                )
    if data.get("submodules"):
        lines.append("")
        lines.append("Submodules: " + ", ".join(str(n) for n in data["submodules"]))  # type: ignore[attr-defined]
    return "\n".join(lines)


class LibraryApi(Tool):
    name = "library_api"
    sends_outside = True
    read_only = True
    output_kind = "tool"
    description = (
        "What the INSTALLED version of a Python library really offers. Use it before you call a library you know only from memory, and whenever a call "
        "fails with 'no attribute' or an unexpected argument. package='requests' gives the installed version and its public names; symbol='requests.Session.request' "
        "gives the signature and docstring; query='retry' lists names that contain the word. A name that does not exist is answered with the nearest real ones. "
        "It reads the installed code of the app's own environment: no network."
    )

    class Args(ToolArgs):
        package: str = Field(
            description="the distribution or top-level module, e.g. requests, pydantic, fastapi"
        )
        symbol: str = Field(
            default="",
            description="a dotted path to look at, e.g. requests.Session.request (empty = the package itself)",
        )
        query: str = Field(
            default="", description="list names containing this word, inside the package or the symbol"
        )

    def summary(self, args: LibraryApi.Args) -> str:
        return f"library api {args.symbol or args.package}" + (f" ~{args.query}" if args.query else "")

    async def run(self, args: LibraryApi.Args, context: ToolContext) -> ToolResult:
        if context.shell is None:
            return ToolResult(ok=False, content="No shell is available to inspect the library.")
        encoded = base64.b64encode(INTROSPECT.encode("utf-8")).decode("ascii")
        python = context.shell.python
        runner = f"& {ps_quote(python)}" if python else "python"
        loader = "import base64,sys;exec(compile(base64.b64decode(sys.argv.pop(1)), '<introspect>', 'exec'))"
        # Windows PowerShell 5.1 drops empty arguments of a native program: "-" stands for "none".
        command = f"{runner} -I -c {ps_quote(loader)} {ps_quote(encoded)} {ps_quote(args.package)} {ps_quote(args.symbol or '-')} {ps_quote(args.query or '-')}"
        result = await execute(context, command, 30, None)
        if not result.ok:
            return ToolResult(ok=False, content=result.content[-1500:])
        # The shell adds its own trailer lines ([exit code], [cwd]) after the program's output.
        text = next((line for line in result.content.splitlines() if line.startswith('{"package"')), "")
        try:
            data = json.loads(text)
        except ValueError:
            return ToolResult(
                ok=False,
                content="The interpreter did not answer with the library's description:\n"
                + result.content[-800:],
            )
        return ToolResult(ok=True, content=render(data))

"""Notebook tools (spec §13B): read and edit .ipynb files cell by cell. Edits go through the workspace (jail,
checkpoints, diff); outputs are kept unless clear_outputs is asked for."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import Field

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

MAX_OUTPUT_CHARS = 1500


def _load(context: ToolContext, path: str) -> dict[str, Any]:
    if not path.endswith(".ipynb"):
        raise ValueError("notebook tools work on .ipynb files")
    text, _ = context.workspace.read_text(path)
    notebook: dict[str, Any] = json.loads(text)
    if not isinstance(notebook.get("cells"), list):
        raise ValueError(f"{path} is not a Jupyter notebook")
    return notebook


def _source(cell: dict[str, Any]) -> str:
    source = cell.get("source", "")
    return "".join(source) if isinstance(source, list) else str(source)


def _outputs(cell: dict[str, Any]) -> str:
    parts = []
    for output in cell.get("outputs", []):
        if "text" in output:
            parts.append("".join(output["text"]) if isinstance(output["text"], list) else str(output["text"]))
        elif "data" in output and "text/plain" in output["data"]:
            data = output["data"]["text/plain"]
            parts.append("".join(data) if isinstance(data, list) else str(data))
        elif output.get("output_type") == "error":
            parts.append(f"{output.get('ename')}: {output.get('evalue')}")
        elif "data" in output:
            parts.append(f"[{', '.join(output['data'])}]")
    text = "\n".join(parts)
    return text[:MAX_OUTPUT_CHARS] + ("…" if len(text) > MAX_OUTPUT_CHARS else "")


class NotebookRead(Tool):
    name = "notebook_read"
    read_only = True
    description = "Read a Jupyter notebook: every cell with its index, type, source and (truncated) outputs."

    class Args(ToolArgs):
        path: str

    def summary(self, args: NotebookRead.Args) -> str:
        return f"read notebook {args.path}"

    async def run(self, args: NotebookRead.Args, context: ToolContext) -> ToolResult:
        notebook = _load(context, args.path)
        blocks = []
        for index, cell in enumerate(notebook["cells"]):
            outputs = _outputs(cell) if cell.get("cell_type") == "code" else ""
            blocks.append(
                f"[{index}] {cell.get('cell_type')}\n{_source(cell)}"
                + (f"\n--- output ---\n{outputs}" if outputs else "")
            )
        context.reads.record(args.path, context.workspace.path_of(args.path).read_bytes())
        return ToolResult(ok=True, content="\n\n".join(blocks) or "(empty notebook)")


class NotebookEditCell(Tool):
    name = "notebook_edit_cell"
    description = (
        "Edit one cell of a notebook: replace its source, insert a new cell at index, or delete it. "
        "Outputs are kept unless clear_outputs=true (a replaced code cell's outputs usually should be "
        "cleared)."
    )

    class Args(ToolArgs):
        path: str
        index: int = Field(ge=0)
        action: Literal["replace", "insert", "delete"] = "replace"
        source: str = ""
        cell_type: Literal["code", "markdown"] | None = None
        clear_outputs: bool = False

    def summary(self, args: NotebookEditCell.Args) -> str:
        return f"notebook {args.action} cell {args.index} in {args.path}"

    async def run(self, args: NotebookEditCell.Args, context: ToolContext) -> ToolResult:
        stale = context.reads.check(args.path, context.workspace.path_of(args.path).read_bytes())
        if stale:
            return ToolResult(ok=False, content=stale + " (use notebook_read)")
        notebook = _load(context, args.path)
        cells: list[dict[str, Any]] = notebook["cells"]
        if args.action != "insert" and args.index >= len(cells):
            return ToolResult(ok=False, content=f"No cell {args.index}; the notebook has {len(cells)} cells.")
        lines = args.source.splitlines(keepends=True)
        if args.action == "delete":
            cells.pop(args.index)
        elif args.action == "insert":
            kind = args.cell_type or "code"
            new: dict[str, Any] = {"cell_type": kind, "metadata": {}, "source": lines}
            if kind == "code":
                new |= {"execution_count": None, "outputs": []}
            cells.insert(min(args.index, len(cells)), new)
        else:
            cell = cells[args.index]
            cell["source"] = lines
            if args.cell_type and args.cell_type != cell.get("cell_type"):
                cell["cell_type"] = args.cell_type
                cell.pop("outputs", None) if args.cell_type == "markdown" else cell.setdefault("outputs", [])
            if args.clear_outputs and cell.get("cell_type") == "code":
                cell["outputs"], cell["execution_count"] = [], None
        text = json.dumps(notebook, indent=1, ensure_ascii=False) + "\n"
        context.workspace.write_text(args.path, text, reason=f"notebook {args.action} cell {args.index}")
        context.reads.record(args.path, context.workspace.path_of(args.path).read_bytes())
        context.last_edit_step = context.step
        await context.emit("file_changed", {"path": args.path, "op": "write", "diff": ""})
        return ToolResult(ok=True, content=f"{args.action} cell {args.index}: done ({len(cells)} cells now).")

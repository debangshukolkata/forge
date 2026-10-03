"""The model's own todo list (D-177), like Claude Code's TodoWrite: a lightweight list the model keeps for its
own step tracking. No approval and no verification gate (unlike propose_plan/task_update, which are the
user-facing, evidence-checked task list). The whole list is sent each time; it is pinned so it survives
compaction, and the clients show it live through the `todo_updated` event."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator

from forge.toolkit.base import Tool, ToolArgs, ToolContext, ToolResult

PIN_SLOT = "todos"
MAX_ITEMS = 40
MARK = {"pending": "[ ]", "in_progress": "[~]", "completed": "[x]"}


class TodoItem(BaseModel):
    content: str = Field(min_length=1, max_length=200)
    status: Literal["pending", "in_progress", "completed"] = "pending"


def render(items: list[TodoItem]) -> str:
    return "\n".join(f"{MARK[item.status]} {item.content}" for item in items)


class TodoWrite(Tool):
    name = "todo_write"
    read_only = True  # keeps a list in the session only; never touches the workspace
    description = (
        "Keep a short todo list for yourself on work with three or more steps: send the WHOLE list every "
        "time (content + status pending/in_progress/completed), mark exactly one item in_progress while "
        "you work on it and completed as soon as it is done. It needs no approval and is not the user's "
        "task list. Skip it for one- or two-step jobs."
    )

    class Args(ToolArgs):
        todos: list[TodoItem] = Field(max_length=MAX_ITEMS)

        @model_validator(mode="after")
        def at_most_one_in_progress(self) -> TodoWrite.Args:
            if sum(item.status == "in_progress" for item in self.todos) > 1:
                raise ValueError("at most one item can be in_progress at a time")
            return self

    def summary(self, args: TodoWrite.Args) -> str:
        done = sum(item.status == "completed" for item in args.todos)
        return f"todo list ({done}/{len(args.todos)} done)"

    async def run(self, args: TodoWrite.Args, context: ToolContext) -> ToolResult:
        context.todos = [item.model_dump() for item in args.todos]
        if context.pin is not None:
            context.pin(PIN_SLOT, render(args.todos) if args.todos else None)
        await context.emit("todo_updated", {"items": context.todos})
        return ToolResult(ok=True, content="Todo list updated:\n" + (render(args.todos) or "(empty)"))

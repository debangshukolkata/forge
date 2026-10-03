// Forge's own todo list (D-177): the model sends the whole list each time with `todo_write`. It shows as a strip
// above the message box (collapsible) and in the side panel's Tasks tab.
import { CheckCircle2, ChevronRight, Circle } from "lucide-react";
import { useState } from "react";
import { cx } from "../lib";
import type { TodoItem } from "../types";
import { Spinner } from "./ui";

export function todoSummary(todos: TodoItem[]): { done: number; total: number; current: string } {
  const done = todos.filter((t) => t.status === "completed").length;
  const active = todos.find((t) => t.status === "in_progress") ?? todos.find((t) => t.status === "pending");
  return { done, total: todos.length, current: active ? active.content : "All done" };
}

export function TodoItems({ todos }: { todos: TodoItem[] }) {
  return (
    <ol aria-label="Todo list" className="space-y-1.5">
      {todos.map((todo, index) => (
        <li key={index} className="flex items-start gap-2 text-[13px]">
          <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center">
            {todo.status === "completed" ? (
              <CheckCircle2 className="h-4 w-4 text-ok" aria-label="Done" />
            ) : todo.status === "in_progress" ? (
              <Spinner className="h-3.5 w-3.5 text-accent" />
            ) : (
              <Circle className="h-4 w-4 text-fg-muted" aria-label="To do" />
            )}
          </span>
          <span
            className={cx(
              "min-w-0 flex-1 break-words",
              todo.status === "completed" && "text-fg-muted line-through",
              todo.status === "in_progress" && "font-semibold",
            )}
          >
            {todo.content}
          </span>
        </li>
      ))}
    </ol>
  );
}

/** The strip above the message box: progress and the item being worked on; opens to the whole list. */
export function TodoStrip({ todos }: { todos: TodoItem[] }) {
  const [open, setOpen] = useState(true);
  if (todos.length === 0) return null;
  const { done, total, current } = todoSummary(todos);
  return (
    <div className="shrink-0 bg-bg px-6 pt-1">
      <div className="mx-auto max-w-[760px] rounded-[18px] border border-border bg-surface">
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          className="flex w-full cursor-pointer items-center gap-2 rounded-[18px] px-4 py-2 text-left text-[13px] transition-colors duration-150 hover:bg-raised"
        >
          <ChevronRight className={cx("h-3.5 w-3.5 shrink-0 text-fg-muted transition-transform duration-150", open && "rotate-90")} aria-hidden />
          <span className="font-semibold">Todo</span>
          <span className="font-mono text-[12px] tabular-nums text-fg-muted">
            {done}/{total}
          </span>
          {!open && <span className="min-w-0 flex-1 truncate text-fg-muted">{current}</span>}
        </button>
        {open && (
          <div className="max-h-44 overflow-y-auto px-4 pb-3 pt-1">
            <TodoItems todos={todos} />
          </div>
        )}
      </div>
    </div>
  );
}

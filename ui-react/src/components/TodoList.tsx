// Forge's own todo list (D-177): the model sends the whole list each time with `todo_write`. It shows as a strip
// above the message box and in the side panel's Tasks tab. The strip is one quiet line by default (progress and the
// item in progress); it opens to the whole list on a click, remembers that choice, and folds when everything is done (D-216).
import { CheckCircle2, ChevronRight, Circle } from "lucide-react";
import { useEffect, useState } from "react";
import { cx } from "../lib";
import type { TodoItem } from "../types";
import { Spinner } from "./ui";

export function todoSummary(todos: TodoItem[]): { done: number; total: number; current: string } {
  const done = todos.filter((t) => t.status === "completed").length;
  const active = todos.find((t) => t.status === "in_progress") ?? todos.find((t) => t.status === "pending");
  return { done, total: todos.length, current: active ? active.content : "All done" };
}

export function TodoItems({ todos, small }: { todos: TodoItem[]; small?: boolean }) {
  const icon = small ? "h-3.5 w-3.5" : "h-4 w-4";
  return (
    <ol aria-label="Todo list" className={cx(small ? "space-y-1" : "space-y-1.5")}>
      {todos.map((todo, index) => (
        <li key={index} className={cx("flex items-start gap-2", small ? "text-[12px]" : "text-[13px]")}>
          <span className={cx("mt-0.5 flex shrink-0 items-center justify-center", icon)}>
            {todo.status === "completed" ? (
              <CheckCircle2 className={cx(icon, "text-ok")} aria-label="Done" />
            ) : todo.status === "in_progress" ? (
              <Spinner className={cx(small ? "h-3 w-3" : "h-3.5 w-3.5", "text-accent")} />
            ) : (
              <Circle className={cx(icon, "text-fg-muted")} aria-label="To do" />
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

const OPEN_KEY = "forge.todo.open";

function readOpen(): boolean {
  try {
    return window.localStorage.getItem(OPEN_KEY) === "1";
  } catch {
    return false; // storage can be blocked: the default is the quiet one-line strip
  }
}

function saveOpen(open: boolean): void {
  try {
    window.localStorage.setItem(OPEN_KEY, open ? "1" : "0");
  } catch {
    /* a remembered choice is a convenience only */
  }
}

/** The strip above the message box: one line by default (progress and the item being worked on), the whole list on a
 * click. The choice is remembered, and the strip folds by itself once every item is done. */
export function TodoStrip({ todos }: { todos: TodoItem[] }) {
  const { done, total, current } = todoSummary(todos);
  const finished = total > 0 && done === total;
  const [open, setOpen] = useState(readOpen);
  useEffect(() => {
    if (finished) setOpen(false);
  }, [finished]);
  if (total === 0) return null;
  const toggle = () =>
    setOpen((value) => {
      saveOpen(!value);
      return !value;
    });
  return (
    <div className="shrink-0 bg-bg px-6 pt-1">
      <div className="mx-auto max-w-[760px] rounded-[16px] border border-border bg-surface">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="flex w-full cursor-pointer items-center gap-2 rounded-[16px] px-3.5 py-1.5 text-left text-[12px] transition-colors duration-150 hover:bg-raised"
        >
          <ChevronRight className={cx("h-3 w-3 shrink-0 text-fg-muted transition-transform duration-150", open && "rotate-90")} aria-hidden />
          <span className="font-semibold">Todo</span>
          <span className="font-mono text-[11px] tabular-nums text-fg-muted">
            {done}/{total}
          </span>
          {!open && <span className="min-w-0 flex-1 truncate text-fg-muted">{current}</span>}
        </button>
        {open && (
          <div className="max-h-40 overflow-y-auto px-3.5 pb-2.5 pt-1">
            <TodoItems todos={todos} small />
          </div>
        )}
      </div>
    </div>
  );
}

// Forge's own todo list (D-177): the model sends the whole list each time with `todo_write`. It shows in the side
// panel's Tasks tab only; the strip above the message box was removed (D-221).
import { CheckCircle2, Circle } from "lucide-react";
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

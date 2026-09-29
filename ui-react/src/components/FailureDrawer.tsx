// What failed during the run (D-122): a drawer sliding in from the right over the Run map, one entry per failed
// tool call — what it tried, a plain-language kind, whether a later call fixed it, and the error output (the
// first lines, "Show more" for all the engine kept). Opened for everything, for one task, or on one failure.
import { ArrowRight, CheckCircle2, ChevronDown, ChevronUp, CircleAlert, CircleCheck, X, XCircle } from "lucide-react";
import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { cx } from "../lib";
import { FAILURE_KIND_LABEL, type Failure } from "../runmap";
import type { Task } from "../types";
import { Badge, IconButton } from "./ui";

const PREVIEW_LINES = 6;

export interface DrawerRequest {
  task: string | null; // null = all tasks
  highlight: number | null; // a failure's seq to scroll to
}

export function FailureDrawer({
  failures,
  tasks,
  request,
  onClose,
  onJump,
}: {
  failures: Failure[];
  tasks: Task[];
  request: DrawerRequest;
  onClose: () => void;
  onJump: (seq: number) => void;
}) {
  const [task, setTask] = useState<string | null>(request.task);
  const panel = useRef<HTMLElement>(null);
  const list = useRef<HTMLDivElement>(null);
  useEffect(() => setTask(request.task), [request]);

  useEffect(() => {
    panel.current?.focus();
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  useLayoutEffect(() => {
    if (request.highlight === null) return;
    list.current?.querySelector(`[data-failure="${request.highlight}"]`)?.scrollIntoView({ block: "center" });
  }, [request]);

  const titles = new Map(tasks.map((t) => [t.id, t.title]));
  const withFailures = [...new Set(failures.map((f) => f.task ?? ""))];
  const shown = failures.filter((f) => task === null || (f.task ?? "") === task);
  const groups = new Map<string, Failure[]>();
  for (const failure of shown) {
    const key = failure.task ?? "";
    groups.set(key, [...(groups.get(key) ?? []), failure]);
  }
  const open = shown.filter((f) => f.outcome === "open").length;

  return (
    <div className="fixed inset-0 z-40" role="presentation">
      <div className="drawer-backdrop absolute inset-0 bg-bg/50" onClick={onClose} aria-hidden />
      <aside
        role="dialog"
        aria-modal="true"
        aria-labelledby="failures-title"
        data-testid="failure-drawer"
        ref={panel}
        tabIndex={-1}
        className="drawer-panel absolute outline-none inset-y-0 right-0 flex w-[min(520px,100vw)] flex-col border-l border-border bg-surface shadow-2xl"
      >
        <header className="flex items-center gap-3 border-b border-border px-4 py-3">
          <XCircle className="h-5 w-5 shrink-0 text-danger" aria-hidden />
          <div className="min-w-0 flex-1">
            <h2 id="failures-title" className="text-[14px] font-semibold">
              Failed calls ({shown.length})
            </h2>
            <p className="text-[12px] text-fg-muted">
              {open ? `${open} not fixed yet` : shown.length ? "All fixed later or their task finished" : "Nothing failed"}
            </p>
          </div>
          <IconButton label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </IconButton>
        </header>
        {withFailures.length > 1 && (
          <div className="flex items-center gap-2 border-b border-border px-4 py-2 text-[12.5px]">
            <label htmlFor="failure-task" className="text-fg-muted">
              Task
            </label>
            <select
              id="failure-task"
              value={task ?? "*"}
              onChange={(e) => setTask(e.target.value === "*" ? null : e.target.value)}
              className="h-7 min-w-0 flex-1 cursor-pointer rounded-md border border-border bg-bg px-2 text-[12.5px] text-fg"
            >
              <option value="*">All tasks ({failures.length})</option>
              {withFailures.map((id) => (
                <option key={id} value={id}>
                  {id ? `${id} · ${titles.get(id) ?? ""}` : "Outside a task"} ({failures.filter((f) => (f.task ?? "") === id).length})
                </option>
              ))}
            </select>
          </div>
        )}
        <div ref={list} className="min-h-0 flex-1 overflow-y-auto px-4 py-3">
          {[...groups.entries()].map(([id, items]) => (
            <section key={id} className="mb-4">
              <h3 className="mb-2 text-[12px] font-medium text-fg-muted">
                {id ? (
                  <>
                    <span className="font-mono text-fg">{id}</span> · {titles.get(id) ?? ""}
                  </>
                ) : (
                  "Outside a task"
                )}
              </h3>
              <ol className="flex flex-col gap-2">
                {items.map((failure) => (
                  <FailureEntry
                    key={failure.seq}
                    failure={failure}
                    highlighted={failure.seq === request.highlight}
                    onJump={() => {
                      onClose();
                      onJump(failure.startSeq ?? failure.seq);
                    }}
                  />
                ))}
              </ol>
            </section>
          ))}
        </div>
      </aside>
    </div>
  );
}

const OUTCOME: Record<Failure["outcome"], { label: string; tone: "accent" | "neutral" | "danger"; icon: ReactNode; hint: string }> = {
  fixed: {
    label: "Fixed later",
    tone: "accent",
    icon: <CircleCheck className="h-3 w-3" aria-hidden />,
    hint: "A later call of the same tool in the same task succeeded",
  },
  "task-done": {
    label: "Task finished",
    tone: "neutral",
    icon: <CheckCircle2 className="h-3 w-3" aria-hidden />,
    hint: "The same tool didn't run again, but the task was completed",
  },
  open: {
    label: "Not fixed yet",
    tone: "danger",
    icon: <CircleAlert className="h-3 w-3" aria-hidden />,
    hint: "No later successful call of this tool in this task so far",
  },
};

function FailureEntry({ failure, highlighted, onJump }: { failure: Failure; highlighted: boolean; onJump: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const lines = failure.output.trimEnd().split("\n");
  const long = lines.length > PREVIEW_LINES;
  // A failure's cause is usually at the end of its output (tracebacks, test summaries): preview the last lines.
  const text = expanded || !long ? failure.output.trimEnd() : lines.slice(-PREVIEW_LINES).join("\n");
  const outcome = OUTCOME[failure.outcome];
  return (
    <li
      data-failure={failure.seq}
      data-outcome={failure.outcome}
      className={cx("rounded-lg border bg-bg px-3 py-2.5", highlighted ? "border-danger ring-2 ring-danger/30" : "border-border")}
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-[12.5px] font-medium text-danger">{FAILURE_KIND_LABEL[failure.kind]}</span>
        <span title={outcome.hint}>
          <Badge tone={outcome.tone}>
            {outcome.icon}
            {outcome.label}
          </Badge>
        </span>
        <span className="ml-auto text-[11.5px] text-fg-muted tabular-nums">
          {new Date(failure.at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
        </span>
      </div>
      <div className="mt-1 truncate font-mono text-[12px] text-fg" title={failure.summary}>
        {failure.summary}
      </div>
      {failure.output.trim() ? (
        <>
          <pre className="mt-2 max-h-[50vh] overflow-auto whitespace-pre-wrap break-words rounded-md border border-border bg-surface px-2.5 py-2 font-mono text-[11.5px] leading-relaxed text-fg-muted">
            {!expanded && long ? "…\n" : ""}
            {text}
          </pre>
          {long && (
            <button
              type="button"
              onClick={() => setExpanded((v) => !v)}
              className="mt-1 inline-flex cursor-pointer items-center gap-1 text-[12px] text-fg-muted hover:text-fg"
            >
              {expanded ? <ChevronUp className="h-3.5 w-3.5" aria-hidden /> : <ChevronDown className="h-3.5 w-3.5" aria-hidden />}
              {expanded ? "Show less" : `Show more (${lines.length} lines)`}
            </button>
          )}
        </>
      ) : (
        <p className="mt-1 text-[12px] text-fg-muted">No output was recorded for this call.</p>
      )}
      <div className="mt-1.5 flex justify-end">
        <button type="button" onClick={onJump} className="inline-flex cursor-pointer items-center gap-1 text-[12px] font-medium text-info hover:underline">
          Show in chat <ArrowRight className="h-3.5 w-3.5" aria-hidden />
        </button>
      </div>
    </li>
  );
}

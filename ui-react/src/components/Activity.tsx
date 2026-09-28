// Live progress while Forge works: a header with the phase stepper and the task bar (real counts only), and
// an activity line above the message box saying what Forge is doing right now, with an animated indicator per
// kind of activity and an elapsed timer.
import { Check, FileSearch, Globe, Hand, PenLine, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import { STEPS, STEP_OF_PHASE, elapsed, stepOf, thinkingLabel, toolActivity, type LoaderStyle } from "../activity";
import type { UsageBucket } from "../types";
import { UsageBadge } from "../usage";
import { cx } from "../lib";
import type { Forge } from "../useForge";

/** Re-renders every second while `active` (for timers). */
function useNow(active: boolean): number {
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [active]);
  return now;
}

export function Loader({ style }: { style: LoaderStyle }) {
  if (style === "dots") {
    return (
      <span className="loader loader-dots" aria-hidden>
        <span />
        <span />
        <span />
      </span>
    );
  }
  if (style === "tests") {
    return (
      <span className="loader loader-tests" aria-hidden>
        <span />
        <span />
        <span />
        <span />
      </span>
    );
  }
  const icon =
    style === "scan" ? <FileSearch className="h-3.5 w-3.5" />
      : style === "type" ? <PenLine className="h-3.5 w-3.5" />
      : style === "globe" ? <Globe className="h-3.5 w-3.5" />
      : style === "pulse" ? <Hand className="h-3.5 w-3.5" />
      : <Terminal className="h-3.5 w-3.5" />;
  return (
    <span className={cx("loader", `loader-${style}`)} aria-hidden>
      {icon}
    </span>
  );
}

export function ActivityLine({ forge }: { forge: Forge }) {
  const { activity, state } = forge;
  const running = activity.kind !== "idle";
  const now = useNow(running);
  if (!running || !state.workspace) return null;
  const task = state.tasks?.find((t) => t.id === state.current_task);
  let label: string;
  let detail: string | undefined;
  let loader: LoaderStyle;
  if (activity.kind === "tool" && activity.tool) {
    ({ label, detail, loader } = toolActivity(activity.tool.name, activity.tool.summary));
  } else if (activity.kind === "writing") {
    label = "Writing the reply";
    loader = "type";
  } else if (activity.kind === "waiting") {
    label = `Waiting for ${activity.waitingFor ?? "you"}`;
    detail = "see the card above";
    loader = "pulse";
  } else {
    label = thinkingLabel(state.phase, task?.title);
    loader = "dots";
  }
  return (
    <div role="status" aria-live="polite" className="mx-auto mb-2 flex max-w-3xl items-center gap-3 px-1">
      <Loader style={loader} />
      <div className="min-w-0 flex-1 text-[13px]">
        <span className={cx("font-medium", activity.kind === "waiting" ? "text-warn" : "text-fg")}>{label}</span>
        {detail && <span className="ml-2 truncate font-mono text-[12px] text-fg-muted">{detail}</span>}
      </div>
      <span className="shrink-0 font-mono text-[12px] tabular-nums text-fg-muted" title="Time on this step">
        {elapsed(activity.since, now)}
      </span>
      {activity.kind !== "waiting" && <span className="shrink-0 text-[11.5px] text-fg-muted">Esc stops</span>}
    </div>
  );
}

export function ProgressHeader({ forge }: { forge: Forge }) {
  const { state, runStartedAt } = forge;
  const step = stepOf(state.phase);
  const busy = Boolean(state.busy);
  const now = useNow(busy);
  if (step === null) return null; // not following the phases (e.g. a plain chat in "direct" mode)
  const tasks = state.tasks || [];
  const done = tasks.filter((t) => t.status === "done").length;
  // Tokens and cost per visible step: the engine's phases summed into the six steps.
  const stepUsage: Record<number, UsageBucket> = {};
  for (const [phase, bucket] of Object.entries(forge.cost?.project?.by_phase ?? {})) {
    const index = STEP_OF_PHASE[phase];
    if (index === undefined || index > 5) continue;
    const sum = (stepUsage[index] ??= { input_tokens: 0, output_tokens: 0, cost_usd: 0, calls: 0 });
    sum.input_tokens += bucket.input_tokens;
    sum.output_tokens += bucket.output_tokens;
    sum.cost_usd += bucket.cost_usd;
    sum.calls += bucket.calls;
  }
  const current = tasks.find((t) => t.id === state.current_task);
  const currentIndex = current ? tasks.indexOf(current) : -1;
  return (
    <div className="shrink-0 border-b border-border bg-surface px-6 py-3">
      <div className="mx-auto max-w-3xl">
        <ol className="flex items-center" aria-label="Progress">
          {STEPS.map((name, index) => {
            const complete = index < step;
            const active = index === step;
            return (
              <li key={name} className="flex flex-1 items-center last:flex-none">
                <span className="flex items-center gap-1.5" aria-current={active ? "step" : undefined}>
                  <span
                    className={cx(
                      "flex h-5 w-5 items-center justify-center rounded-full border text-[10px] font-semibold transition-colors duration-300",
                      complete && "border-accent bg-accent text-accent-fg",
                      active && "border-accent text-accent",
                      !complete && !active && "border-border-strong text-fg-muted",
                    )}
                  >
                    {complete ? <Check className="h-3 w-3" /> : active && busy ? <span className="h-2 w-2 animate-pulse rounded-full bg-accent" /> : index + 1}
                  </span>
                  <span className={cx("text-[12px] font-medium", active ? "text-fg" : "text-fg-muted")}>{name}</span>
                  {stepUsage[index] && <UsageBadge compact bucket={stepUsage[index]} limits={forge.costColors?.phase} />}
                </span>
                {index < STEPS.length - 1 && (
                  <span className={cx("mx-2 h-px flex-1 transition-colors duration-300", complete ? "bg-accent" : "bg-border")} aria-hidden />
                )}
              </li>
            );
          })}
        </ol>
        {tasks.length > 0 && (
          <div className="mt-3">
            <div className="mb-1.5 flex items-center justify-between gap-3 text-[12.5px]">
              <span className="min-w-0 truncate">
                {current ? (
                  <>
                    <span className="text-fg-muted">Task {currentIndex + 1} of {tasks.length} · </span>
                    <span className="font-medium">{current.title}</span>
                  </>
                ) : (
                  <span className="text-fg-muted">{done === tasks.length ? "All tasks done" : `${tasks.length} tasks planned`}</span>
                )}
              </span>
              <span className="shrink-0 font-mono text-[12px] tabular-nums text-fg-muted">
                {done}/{tasks.length} done{runStartedAt && busy ? ` · ${elapsed(runStartedAt, now)}` : ""}
              </span>
            </div>
            <div className="flex h-1.5 gap-0.5 overflow-hidden rounded-full" aria-hidden>
              {tasks.map((task) => (
                <span
                  key={task.id}
                  title={`${task.id}: ${task.title} (${task.status.replace("_", " ")})`}
                  className={cx(
                    "h-full flex-1 transition-colors duration-300",
                    task.status === "done" && "bg-accent",
                    task.status === "blocked" && "bg-danger",
                    task.status === "in_progress" && cx("bg-accent/50", busy && "shimmer"),
                    task.status === "pending" && "bg-muted",
                  )}
                />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}


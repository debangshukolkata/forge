// Live progress while Forge works: a header with the phase stepper and the task bar (real counts only), and
// an activity line above the message box saying what Forge is doing right now, with an animated indicator per
// kind of activity and an elapsed timer.
import { Check, FileSearch, Globe, Hand, PenLine, Terminal } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { STEPS, STEP_OF_PHASE, elapsed, stepOf, thinkingLabel, toolActivity, type LoaderStyle } from "../activity";
import type { UsageBucket } from "../types";
import { UsageBadge } from "../usage";
import { cx } from "../lib";
import { duration, phaseWorkMs } from "../runmap";
import type { Forge } from "../useForge";

function stepTitle(name: string, usage: UsageBucket | undefined, ms: number | undefined): string {
  const parts = [name];
  if (usage) parts.push(`$${usage.cost_usd.toFixed(4)} · ${(usage.input_tokens + usage.output_tokens).toLocaleString()} tokens`);
  if (ms) parts.push(`${duration(ms)} working`);
  return parts.join(" — ");
}

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

/** True once the observed element is at least `minPx` wide. Element-relative (not viewport-relative)
 * so the stepper adapts to the chat column's own width, not the window's — a `@container` query would
 * do this in CSS, but it isn't reliably supported in every Edge build we test on (headless or not). */
function useMinWidth<T extends Element>(minPx: number): [React.RefObject<T | null>, boolean] {
  const ref = useRef<T | null>(null);
  const [wide, setWide] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      const width = entries[0]?.contentRect.width ?? 0;
      setWide(width >= minPx);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, [minPx]);
  return [ref, wide];
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
  // Working time per step (time spent waiting for you excluded), summed like the usage.
  const stepTime: Record<number, number> = {};
  const working = forge.activity.kind !== "idle" && forge.activity.kind !== "waiting";
  for (const [phase, ms] of Object.entries(phaseWorkMs(forge.events, working ? now : null))) {
    const index = STEP_OF_PHASE[phase];
    if (index !== undefined && index <= 5) stepTime[index] = (stepTime[index] ?? 0) + ms;
  }
  const current = tasks.find((t) => t.id === state.current_task);
  const currentIndex = current ? tasks.indexOf(current) : -1;
  // Below this width there isn't room for six even columns with legible labels (sidebar
  // collapsed, narrow window, etc), so the stepper switches to a vertical stack instead.
  const [stepperRef, wide] = useMinWidth<HTMLOListElement>(420);
  return (
    <div className="shrink-0 border-b border-border bg-surface px-6 py-3">
      <div className="mx-auto max-w-3xl">
        <ol
          ref={stepperRef}
          className={cx("grid items-stretch", wide ? "grid-cols-6 gap-y-0" : "grid-cols-1 gap-y-3")}
          aria-label="Progress"
        >
          {STEPS.map((name, index) => {
            const complete = index < step;
            const active = index === step;
            // The current step animates while Forge works on it; amber and gently pulsing while it waits for you.
            const motion = active ? (forge.activity.kind === "waiting" ? "step-waiting" : forge.activity.kind !== "idle" ? "step-working" : "") : "";
            const meta = (stepUsage[index] || stepTime[index]) && (
              <span className="flex items-center gap-1 whitespace-nowrap text-[11px]" data-step-meta>
                {stepUsage[index] && <UsageBadge compact bucket={stepUsage[index]} limits={forge.costColors?.phase} />}
                {stepUsage[index] && stepTime[index] ? <span className="text-fg-muted">·</span> : null}
                {stepTime[index] ? (
                  <span className="font-mono tabular-nums text-fg-muted" title="Working time (waiting for you not counted)">
                    {duration(stepTime[index])}
                  </span>
                ) : null}
              </span>
            );
            const circle = (
              <span
                data-motion={motion || undefined}
                className={cx(
                  "relative isolate z-10 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border bg-surface text-[10px] font-semibold transition-colors duration-300",
                  complete && "border-accent bg-accent text-accent-fg",
                  active && (motion === "step-waiting" ? "border-warn text-warn" : "border-accent text-accent"),
                  motion,
                  !complete && !active && "border-border-strong text-fg-muted",
                )}
              >
                {complete ? <Check className="h-3 w-3" /> : index + 1}
              </span>
            );
            return (
              <li
                key={name}
                className={cx("relative flex items-center gap-2", wide && "flex-col items-center gap-1.5")}
                aria-current={active ? "step" : undefined}
                title={stepUsage[index] || stepTime[index] ? stepTitle(name, stepUsage[index], stepTime[index]) : undefined}
              >
                {/* connector to the previous step: a vertical bar to its left when stacked, a
                    horizontal bar centered through the circles' row when in columns — drawn as
                    its own full-width/height line so its length never depends on label width. */}
                {index > 0 && (
                  <span
                    className={cx(
                      "absolute bg-border transition-colors duration-300",
                      wide ? "top-2.5 right-1/2 h-px w-full" : "top-0 left-2.5 -mt-3 h-3 w-px",
                      complete && "bg-accent",
                    )}
                    aria-hidden
                  />
                )}
                {circle}
                {/* name and, underneath, cost/working time; centered under the circle in column
                    mode, to the right of it when stacked. Always visible — no hiding at width. */}
                <span className={cx("flex flex-col leading-tight", wide && "items-center")}>
                  <span className={cx("text-[12px] font-medium whitespace-nowrap leading-5", active ? "text-fg" : "text-fg-muted")}>{name}</span>
                  {meta}
                </span>
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


// Live progress while Forge works: an activity line above the message box saying what Forge is doing right
// now, with an animated indicator per kind of activity and an elapsed timer. The old phase stepper
// (`ProgressHeader`) is gone (D-133): there is no fixed phase pipeline left to represent honestly.
// D-133 also adds cost/time visibility: a per-task badge on the activity line, and a small persistent
// `RunTotals` strip above it for the whole run's cost + elapsed time.
import { FileSearch, Globe, Hand, PenLine, Terminal } from "lucide-react";
import { useEffect, useState } from "react";
import { elapsed, thinkingNow, toolActivity, type LoaderStyle } from "../activity";
import { cx } from "../lib";
import { duration } from "../runmap";
import type { UsageBucket } from "../types";
import type { Forge } from "../useForge";
import { UsageBadge } from "../usage";
import { agentCounts, latestStepText, roleLabel } from "./AgentSteps";

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

/** When the current task first appeared in the event stream (its first event with a matching `where.task`). */
function currentTaskStartedAt(forge: Forge): number | null {
  const taskId = forge.state.current_task;
  if (!taskId) return null;
  for (const event of forge.events) {
    if (event.where?.task === taskId) {
      const at = Date.parse(event.ts);
      return Number.isNaN(at) ? null : at;
    }
  }
  return null;
}

/** A small persistent strip for the whole run's total cost + elapsed time. Sits above the activity line;
 * shown only while the run is active (D-133) so it never lingers as stale chrome once Forge goes idle. */
export function RunTotals({ forge }: { forge: Forge }) {
  const { state, runStartedAt } = forge;
  const now = useNow(!!state.busy);
  if (!state.busy || !state.workspace || runStartedAt === null) return null;
  const bucket = forge.cost?.project?.total;
  if (!bucket) return null;
  return (
    <div className="mx-auto mb-1 flex max-w-3xl items-center justify-end gap-2 px-1 text-[11px] text-fg-muted">
      <span>Project total</span>
      <UsageBadge bucket={bucket} limits={forge.costColors?.task} compact />
      <span className="font-mono tabular-nums" title="Time since this run started">
        {duration(now - runStartedAt)}
      </span>
    </div>
  );
}

export function ActivityLine({ forge }: { forge: Forge }) {
  const { activity, state } = forge;
  const running = activity.kind !== "idle";
  const now = useNow(running);
  if (!running || !state.workspace) return null;
  const task = state.tasks?.find((t) => t.id === state.current_task);
  const progress = activity.kind === "tool" ? activity.progress : undefined;
  let label: string;
  let detail: string | undefined;
  let loader: LoaderStyle;
  if (activity.kind === "tool" && activity.tool) {
    ({ label, detail, loader } = toolActivity(activity.tool.name, activity.tool.summary));
    if (activity.progress?.line) detail = activity.progress.line; // what the command printed last
    const helper = [...forge.timeline.items].reverse().find((item) => item.kind === "tool" && item.agent && item.state === "running");
    if (activity.tool.name === "spawn_subagent" && helper?.kind === "tool" && helper.agent) {
      label = `${roleLabel(helper.agent.role)} is working`;
      detail = `${agentCounts(helper.agent)} · ${latestStepText(helper.agent)}`;
    }
  } else if (activity.kind === "writing") {
    label = "Writing the reply";
    loader = "type";
  } else if (activity.kind === "waiting") {
    label = `Waiting for ${activity.waitingFor ?? "you"}`;
    detail = "see the card above";
    loader = "pulse";
  } else {
    const items = forge.timeline.items;
    const lastTool = [...items].reverse().find((item) => item.kind === "tool");
    const doing = forge.timeline.todos.find((item) => item.status === "in_progress");
    ({ label, detail } = thinkingNow(
      state.phase,
      task?.title,
      doing?.content,
      lastTool?.kind === "tool" ? lastTool.name : undefined,
    ));
    loader = "dots";
  }
  const taskUsage: UsageBucket | undefined = state.current_task
    ? forge.cost?.project?.by_task?.[state.current_task]
    : undefined;
  const taskStartedAt = task ? currentTaskStartedAt(forge) : null;
  return (
    <div role="status" aria-live="polite" className="mx-auto mb-2 flex max-w-3xl items-center gap-3 px-1">
      <Loader style={loader} />
      <div className="min-w-0 flex-1 text-[13px]">
        <span className={cx("font-medium", activity.kind === "waiting" ? "text-warn" : "text-fg")}>{label}</span>
        {detail && <span className="ml-2 truncate font-mono text-[12px] text-fg-muted">{detail}</span>}
        {progress?.percent != null && (
          <span className="ml-2 font-mono text-[12px] tabular-nums text-accent">{Math.round(progress.percent)}%</span>
        )}
        {progress?.stalled_s != null && (
          <span className="ml-2 text-[12px] text-warn">no output for {Math.floor(progress.stalled_s / 60)} min</span>
        )}
        {progress?.percent != null && (
          <div className="mt-1 h-0.5 w-full overflow-hidden rounded bg-raised">
            <div
              data-testid="activity-progress"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={Math.round(progress.percent)}
              className="h-full bg-accent transition-[width] duration-500"
              style={{ width: `${Math.min(100, Math.max(0, progress.percent))}%` }}
            />
          </div>
        )}
      </div>
      {taskUsage && (
        <span className="shrink-0 flex items-center gap-1.5" title="Cost and time on the current task">
          <UsageBadge bucket={taskUsage} limits={forge.costColors?.task} compact />
          {taskStartedAt !== null && (
            <span className="font-mono text-[11px] tabular-nums text-fg-muted">{duration(now - taskStartedAt)}</span>
          )}
        </span>
      )}
      <span className="shrink-0 font-mono text-[12px] tabular-nums text-fg-muted" title="Time on this step">
        {elapsed(activity.since, now)}
      </span>
      {activity.kind !== "waiting" && <span className="shrink-0 text-[11.5px] text-fg-muted">Esc stops</span>}
    </div>
  );
}


// The Run map's model, derived from the project's events (D-119): which tasks exist and how they depend on each
// other, what happened to each (failures, stuck warnings, helper agents), and when each task and agent ran.
// Pure functions of the event list, so a replayed project draws the same map as a live one.
// No `phase` tracking here (D-128/D-131/D-133): the engine dropped its fixed phase pipeline, so `where.phase`
// on events is a stale, best-effort label only — the graph is derived purely from what has actually happened.
import type { ForgeEvent, Task } from "./types";

export interface Agent {
  id: string;
  role: string;
  purpose: string;
  task: string | null;
  start: number;
  end: number | null;
  ok: boolean | null;
  toolCalls: number;
  failedCalls: number;
  costUsd: number;
  seq: number;
}

export type FailureKind = "tests" | "edit" | "command" | "blocked" | "tool";
export type FailureOutcome = "fixed" | "task-done" | "open";

export interface Failure {
  seq: number; // the tool_call_finished event
  startSeq: number | null; // its tool_call_started event (the chat row)
  at: number;
  task: string | null;
  phase: string | null;
  tool: string;
  summary: string; // what it tried ("run tests tests/test_invoice.py")
  output: string; // start and end of the result, as the engine kept it
  kind: FailureKind;
  outcome: FailureOutcome;
}

export const FAILURE_KIND_LABEL: Record<FailureKind, string> = {
  tests: "Tests failed",
  edit: "Edit didn't apply",
  command: "Command failed",
  blocked: "Blocked or declined",
  tool: "Tool error",
};

const TEST_TOOLS = new Set(["run_tests", "verify", "run_eval"]);
const EDIT_TOOLS = new Set(["edit_file", "multi_edit", "write_file", "notebook_edit_cell", "delete_file", "move_file"]);
const COMMAND_TOOLS = new Set(["run_command", "python_run", "start_background", "scratch_exec", "db_query"]);

function failureKind(tool: string, output: string): FailureKind {
  if (/declined|not allowed|denied|outside the (workspace|write jail)|refus/i.test(output.slice(0, 400))) return "blocked";
  if (TEST_TOOLS.has(tool)) return "tests";
  if (EDIT_TOOLS.has(tool)) return "edit";
  if (COMMAND_TOOLS.has(tool)) return "command";
  return "tool";
}

export interface TaskStats {
  failures: number;
  stuck: number;
  agents: number;
  firstSeq: number | null;
}

export interface RunModel {
  tasks: Task[];
  currentTask: string | null;
  stats: Record<string, TaskStats>;
  agents: Agent[];
  failures: Failure[];
  exported: boolean; // output/ has been built at least once (D-133: the deliver node's signal)
  waitingSince: number | null; // seq of the request Forge is still waiting on, if any
  start: number | null;
  end: number | null;
}

function time(event: ForgeEvent): number {
  const value = Date.parse(event.ts);
  return Number.isNaN(value) ? 0 : value;
}

function emptyStats(): TaskStats {
  return { failures: 0, stuck: 0, agents: 0, firstSeq: null };
}

/** `live` is the current time while Forge is working; otherwise the map ends at the last event, so a project
 * reopened days later doesn't stretch its timeline to today. */
export function buildRunModel(events: ForgeEvent[], fallbackTasks: Task[] = [], live: number | null = null): RunModel {
  let tasks: Task[] = fallbackTasks;
  let currentTask: string | null = null;
  let exported = false;
  const stats: Record<string, TaskStats> = {};
  const statsOf = (id: string) => (stats[id] ??= emptyStats());
  const agents: Agent[] = [];
  const openAgents = new Map<string, Agent>();
  const toolNames = new Map<string, string>();
  const toolStarts = new Map<string, number>();
  const failures: Failure[] = [];
  // Successful calls per task and tool, in order, to tell whether a failure was fixed later.
  const successes: { seq: number; task: string | null; tool: string }[] = [];
  let start: number | null = null;
  let end: number | null = null;

  // Forge blocks on a request: whatever event comes next means you answered, so the wait ends there.
  let waitingSeq: number | null = null;
  for (const event of events) {
    const at = time(event);
    if (!at) continue;
    start ??= at;
    end = at;
    if (waitingSeq !== null) waitingSeq = null;
    const p = event.payload;
    const where = event.where ?? null;
    const task = where?.task ?? null;

    if (task && statsOf(task).firstSeq === null) statsOf(task).firstSeq = event.seq;

    switch (event.type) {
      case "task_list_updated":
        tasks = (p.tasks as Task[]) ?? tasks;
        currentTask = p.current_task ?? null;
        if (p.exported) exported = true;
        break;
      case "tool_call_started":
        toolNames.set(p.id, p.summary || p.name);
        toolStarts.set(p.id, event.seq);
        break;
      case "tool_call_finished":
        if (p.ok !== false) successes.push({ seq: event.seq, task, tool: p.name });
        if (p.ok === false) {
          const output = String(p.preview ?? "");
          failures.push({
            seq: event.seq, startSeq: toolStarts.get(p.id) ?? null, at, task, phase: where?.phase ?? null,
            tool: p.name ?? "tool", summary: toolNames.get(p.id) ?? p.summary ?? p.name ?? "", output,
            kind: failureKind(p.name ?? "", output), outcome: "open",
          });
          if (task) statsOf(task).failures += 1;
        }
        break;
      case "notice":
        if (p.kind === "stuck" && task) statsOf(task).stuck += 1;
        break;
      case "approval_requested":
      case "question_asked":
      case "user_action_requested":
        waitingSeq = event.seq;
        break;
      case "agent_started": {
        const agent: Agent = {
          id: p.id, role: p.role || "helper", purpose: p.purpose || "", task, start: at, end: null, ok: null,
          toolCalls: 0, failedCalls: 0, costUsd: 0, seq: event.seq,
        };
        agents.push(agent);
        openAgents.set(agent.id, agent);
        if (task) statsOf(task).agents += 1;
        break;
      }
      case "agent_finished": {
        const agent = openAgents.get(p.id);
        if (!agent) break;
        openAgents.delete(p.id);
        agent.end = at;
        agent.ok = p.ok !== false;
        agent.toolCalls = p.tool_calls ?? 0;
        agent.failedCalls = p.failed_calls ?? 0;
        agent.costUsd = p.cost_usd ?? 0;
        break;
      }
    }
  }

  const statusOf = new Map(tasks.map((t) => [t.id, t.status]));
  for (const failure of failures) {
    const later = successes.some((s) => s.seq > failure.seq && s.tool === failure.tool && s.task === failure.task);
    failure.outcome = later ? "fixed" : failure.task && statusOf.get(failure.task) === "done" ? "task-done" : "open";
  }

  if (live !== null && end !== null) end = Math.max(end, live);
  return { tasks, currentTask, stats, agents, failures, exported, start, end, waitingSince: waitingSeq };
}

export interface GraphNodeData {
  kind: "start" | "task" | "agent" | "deliver";
  title: string;
  task?: Task;
  agent?: Agent;
  stats?: TaskStats;
  current?: boolean;
  state?: "pending" | "active" | "done" | "failed";
}

export interface GraphEdge {
  from: string;
  to: string;
  kind: "depends_on" | "spawned" | "flow";
}

export interface Graph {
  nodes: { id: string; data: GraphNodeData }[];
  edges: GraphEdge[];
}

/** Builds the run's DAG incrementally from what has already happened, rather than pre-drawing a fixed
 * skeleton (D-133, replacing the old phase-driven `planGraph`): a `start` node once the run has begun, a
 * `task` node per task known so far (tasks can arrive later via `update_plan`), an `agent` node per helper
 * run spawned so far, and a `deliver` node once the run has actually exported. */
export function buildGraph(model: RunModel): Graph {
  if (model.start === null) return { nodes: [], edges: [] };

  const ids = new Set(model.tasks.map((t) => t.id));
  const startState: GraphNodeData["state"] = model.tasks.length > 0 || model.exported ? "done" : "active";

  const nodes: { id: string; data: GraphNodeData }[] = [
    { id: "@start", data: { kind: "start", title: "Start", state: startState } },
    ...model.tasks.map((task) => ({
      id: task.id,
      data: {
        kind: "task" as const,
        title: task.title,
        task,
        stats: model.stats[task.id],
        current: task.id === model.currentTask,
        state: (task.status === "done" ? "done"
          : task.status === "blocked" ? "failed"
          : task.status === "in_progress" ? "active"
          : "pending") as GraphNodeData["state"],
      },
    })),
    ...model.agents.map((agent) => ({
      id: `@agent:${agent.id}`,
      data: {
        kind: "agent" as const,
        title: agent.purpose || agent.role,
        agent,
        state: (agent.end === null ? "active" : agent.ok === false || agent.failedCalls > 0 ? "failed" : "done") as GraphNodeData["state"],
      },
    })),
  ];
  if (model.exported) {
    nodes.push({ id: "@deliver", data: { kind: "deliver", title: "Deliver", state: "done" } });
  }

  const edges: GraphEdge[] = [];
  const hasDependents = new Set<string>();
  for (const task of model.tasks) {
    const deps = (task.depends_on ?? []).filter((d) => ids.has(d));
    if (deps.length === 0) edges.push({ from: "@start", to: task.id, kind: "flow" });
    for (const dep of deps) {
      edges.push({ from: dep, to: task.id, kind: "depends_on" });
      hasDependents.add(dep);
    }
  }
  for (const agent of model.agents) {
    edges.push({ from: agent.task && ids.has(agent.task) ? agent.task : "@start", to: `@agent:${agent.id}`, kind: "spawned" });
  }
  if (model.exported) {
    // Every task with nothing depending on it feeds Deliver; with no tasks at all (a plain chat that
    // still ended in an export), Deliver hangs straight off Start.
    const leaves = model.tasks.filter((t) => !hasDependents.has(t.id));
    const sources = leaves.length ? leaves.map((t) => t.id) : ["@start"];
    for (const source of sources) edges.push({ from: source, to: "@deliver", kind: "flow" });
  }
  return { nodes, edges };
}

export function duration(ms: number): string {
  const minutes = Math.round(ms / 60_000);
  if (ms < 60_000) return `${Math.max(1, Math.round(ms / 1000))}s`;
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${String(minutes % 60).padStart(2, "0")}m`;
  return `${Math.floor(hours / 24)}d ${hours % 24}h`;
}

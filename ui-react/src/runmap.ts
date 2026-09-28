// The Run map's model, derived from the project's events (D-119): which tasks exist and how they depend on each
// other, what happened to each (failures, stuck warnings, helper agents), and when each phase, task and agent ran.
// Pure functions of the event list, so a replayed project draws the same map as a live one.
import type { ForgeEvent, Task } from "./types";

export type MarkerKind = "failure" | "stuck" | "waiting";

export interface Marker {
  kind: MarkerKind;
  at: number; // ms timestamp
  seq: number; // the event, for jumping to it in the chat
  label: string;
  lane: string; // lane id: "phase", "task:<id>" or "agent:<role>"
}

export interface Span {
  lane: string;
  label: string;
  start: number;
  end: number | null; // null = still running
  seq: number;
  tone: "phase" | "task" | "agent" | "agent-failed";
}

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
  seq: number;
}

export interface TaskStats {
  failures: number;
  stuck: number;
  agents: number;
  firstSeq: number | null;
}

export interface RunModel {
  tasks: Task[];
  phase: string | null;
  currentTask: string | null;
  stats: Record<string, TaskStats>;
  agents: Agent[];
  spans: Span[];
  markers: Marker[];
  lanes: { id: string; label: string; group: "phase" | "task" | "agent" }[];
  start: number | null;
  end: number | null;
}

export const PHASE_LABEL: Record<string, string> = {
  intake: "Intake", clarify: "Clarify", kb_check: "Knowledge", explore: "Explore", plan: "Plan", execute: "Build",
  review: "Review", export: "Export", restructure: "Restructure", handoff: "Hand-over", done: "Done", direct: "Chat",
};

const WAITING: Record<string, string> = {
  approval_requested: "Waiting for your approval",
  question_asked: "Waiting for your answer",
  user_action_requested: "Waiting for you to act",
};

function time(event: ForgeEvent): number {
  const value = Date.parse(event.ts);
  return Number.isNaN(value) ? 0 : value;
}

function emptyStats(): TaskStats {
  return { failures: 0, stuck: 0, agents: 0, firstSeq: null };
}

/** `live` is the current time while Forge is working (open spans grow to it); otherwise the map ends at the
 * last event, so a project reopened days later doesn't stretch its timeline to today. */
export function buildRunModel(events: ForgeEvent[], fallbackTasks: Task[] = [], live: number | null = null): RunModel {
  let tasks: Task[] = fallbackTasks;
  let phase: string | null = null;
  let currentTask: string | null = null;
  const stats: Record<string, TaskStats> = {};
  const statsOf = (id: string) => (stats[id] ??= emptyStats());
  const agents: Agent[] = [];
  const openAgents = new Map<string, Agent>();
  const spans: Span[] = [];
  const markers: Marker[] = [];
  const toolNames = new Map<string, string>();
  let phaseSpan = null as Span | null;
  let taskSpan = null as Span | null;
  let start: number | null = null;
  let end: number | null = null;

  for (const event of events) {
    const at = time(event);
    if (!at) continue;
    start ??= at;
    end = at;
    const p = event.payload;
    const where = event.where ?? null;
    const task = where?.task ?? null;

    // Phase and task spans follow the stamp every event carries: a change closes the open span.
    if (where?.phase && where.phase !== phaseSpan?.label) {
      if (phaseSpan) phaseSpan.end = at;
      phaseSpan = { lane: "phase", label: where.phase, start: at, end: null, seq: event.seq, tone: "phase" };
      spans.push(phaseSpan);
    }
    if (task !== (taskSpan ? taskSpan.lane.slice(5) : null)) {
      if (taskSpan) taskSpan.end = at;
      taskSpan = task ? { lane: `task:${task}`, label: task, start: at, end: null, seq: event.seq, tone: "task" } : null;
      if (taskSpan) spans.push(taskSpan);
    }
    if (task && statsOf(task).firstSeq === null) statsOf(task).firstSeq = event.seq;
    const lane = task ? `task:${task}` : "phase";

    switch (event.type) {
      case "task_list_updated":
        tasks = (p.tasks as Task[]) ?? tasks;
        phase = p.phase ?? phase;
        currentTask = p.current_task ?? null;
        break;
      case "tool_call_started":
        toolNames.set(p.id, p.summary || p.name);
        break;
      case "tool_call_finished":
        if (p.ok === false) {
          if (task) statsOf(task).failures += 1;
          markers.push({ kind: "failure", at, seq: event.seq, lane, label: `Failed: ${toolNames.get(p.id) ?? p.name ?? "tool call"}` });
        }
        break;
      case "notice":
        if (p.kind === "stuck") {
          if (task) statsOf(task).stuck += 1;
          markers.push({ kind: "stuck", at, seq: event.seq, lane, label: String(p.text ?? "Stuck").split("\n")[0] });
        }
        break;
      case "approval_requested":
      case "question_asked":
      case "user_action_requested":
        markers.push({ kind: "waiting", at, seq: event.seq, lane, label: String(p.title || p.question || WAITING[event.type]).split("\n")[0] });
        break;
      case "agent_started": {
        const agent: Agent = {
          id: p.id, role: p.role || "helper", purpose: p.purpose || "", task, start: at, end: null, ok: null,
          toolCalls: 0, failedCalls: 0, seq: event.seq,
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
        break;
      }
      case "session_ended":
        currentTask = null;
        break;
    }
  }

  // Open spans (end null) are drawn up to the map's end.
  if (live !== null && end !== null) end = Math.max(end, live);
  for (const agent of agents) {
    spans.push({
      lane: `agent:${agent.role}`, label: agent.purpose || agent.role, start: agent.start, end: agent.end, seq: agent.seq,
      tone: agent.ok === false || agent.failedCalls > 0 ? "agent-failed" : "agent",
    });
  }

  const taskIds = new Set(tasks.map((t) => t.id));
  const laneTaskIds = [...tasks.map((t) => t.id), ...Object.keys(stats).filter((id) => !taskIds.has(id))];
  const roles = [...new Set(agents.map((a) => a.role))];
  const lanes: RunModel["lanes"] = [
    { id: "phase", label: "Phases", group: "phase" },
    ...laneTaskIds.map((id) => ({ id: `task:${id}`, label: id, group: "task" as const })),
    ...roles.map((role) => ({ id: `agent:${role}`, label: role.charAt(0).toUpperCase() + role.slice(1), group: "agent" as const })),
  ];
  return { tasks, phase, currentTask, stats, agents, spans, markers, lanes, start, end };
}

export interface GraphNodeData {
  kind: "start" | "task" | "review" | "deliver";
  title: string;
  task?: Task;
  stats?: TaskStats;
  current?: boolean;
  state?: "pending" | "active" | "done";
}

export interface GraphEdge {
  from: string;
  to: string;
  kind: "depends" | "flow" | "fix";
}

/** Nodes and edges of the plan: Plan → tasks (by depends_on) → Review → FIX tasks → Deliver. */
export function planGraph(model: RunModel): { nodes: { id: string; data: GraphNodeData }[]; edges: GraphEdge[] } {
  const isFix = (t: Task) => /^FIX/i.test(t.id);
  const work = model.tasks.filter((t) => !isFix(t));
  const fixes = model.tasks.filter(isFix);
  const ids = new Set(model.tasks.map((t) => t.id));
  const phaseOrder = ["intake", "clarify", "kb_check", "explore", "plan", "execute", "restructure", "review", "export", "handoff", "done"];
  const at = phaseOrder.indexOf(model.phase ?? "");
  const stateOf = (index: number): GraphNodeData["state"] => (at > index ? "done" : at === index ? "active" : "pending");

  const nodes: { id: string; data: GraphNodeData }[] = [
    { id: "@plan", data: { kind: "start", title: "Plan", state: at >= 5 ? "done" : at >= 0 ? "active" : "pending" } },
    ...model.tasks.map((task) => ({
      id: task.id,
      data: { kind: "task" as const, title: task.title, task, stats: model.stats[task.id], current: task.id === model.currentTask },
    })),
    { id: "@review", data: { kind: "review", title: "Review", state: stateOf(phaseOrder.indexOf("review")) } },
    { id: "@deliver", data: { kind: "deliver", title: "Deliver", state: model.phase === "done" ? "done" : at >= 8 ? "active" : "pending" } },
  ];
  const edges: GraphEdge[] = [];
  const hasDependents = new Set<string>();
  for (const task of work) {
    const deps = (task.depends_on ?? []).filter((d) => ids.has(d));
    if (deps.length === 0) edges.push({ from: "@plan", to: task.id, kind: "flow" });
    for (const dep of deps) {
      edges.push({ from: dep, to: task.id, kind: "depends" });
      hasDependents.add(dep);
    }
  }
  const leaves = work.filter((t) => !hasDependents.has(t.id));
  if (leaves.length === 0) edges.push({ from: "@plan", to: "@review", kind: "flow" });
  for (const leaf of leaves) edges.push({ from: leaf.id, to: "@review", kind: "flow" });
  for (const fix of fixes) {
    edges.push({ from: "@review", to: fix.id, kind: "fix" });
    edges.push({ from: fix.id, to: "@deliver", kind: "flow" });
  }
  if (fixes.length === 0) edges.push({ from: "@review", to: "@deliver", kind: "flow" });
  return { nodes, edges };
}

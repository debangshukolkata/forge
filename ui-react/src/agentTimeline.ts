// A subagent's progress inside the chat timeline (D-179, D-181): the `spawn_subagent` tool row carries the
// agent's own tool calls as nested steps. Parallel spawns are paired in the order they started; a subagent
// started by anything else (the review step) gets a row of its own.
import type { AgentStep, AgentView, ChatItem, ForgeEvent } from "./types";

type ToolItem = Extract<ChatItem, { kind: "tool" }>;
const MAX_STEPS = 400; // a verifier can make hundreds of calls; the oldest fall off the list

function isToolItem(item: ChatItem): item is ToolItem {
  return item.kind === "tool";
}

function withAgent(items: ChatItem[], agentId: string, change: (agent: AgentView, item: ToolItem) => ToolItem): ChatItem[] {
  return items.map((item) => (isToolItem(item) && item.agent?.id === agentId ? change(item.agent, item) : item));
}

export function agentStarted(items: ChatItem[], key: string, p: ForgeEvent["payload"]): ChatItem[] {
  const agent: AgentView = { id: p.id, role: p.role || "agent", purpose: p.purpose || "", steps: [] };
  const index = items.findIndex((item) => isToolItem(item) && item.name === "spawn_subagent" && item.state === "running" && !item.agent);
  if (index >= 0) return items.map((item, i) => (i === index ? { ...(item as ToolItem), agent } : item));
  return [...items, { key, kind: "tool", id: agent.id, name: agent.role, summary: agent.purpose, state: "running", agent }];
}

export function agentStep(items: ChatItem[], p: ForgeEvent["payload"]): ChatItem[] {
  return withAgent(items, p.agent, (agent, item) => {
    let steps: AgentStep[] = agent.steps;
    if (p.kind === "tool_started") {
      steps = [...steps, { kind: "tool", name: p.name, summary: p.summary || "", state: "running" }];
    } else if (p.kind === "tool_finished") {
      // The call that was running with the same name and summary (the nearest one, as calls can overlap).
      let at = -1;
      for (let i = steps.length - 1; i >= 0; i--) {
        if (steps[i].kind === "tool" && steps[i].state === "running" && steps[i].name === p.name) {
          at = i;
          break;
        }
      }
      const done: AgentStep = { kind: "tool", name: p.name, summary: p.summary || "", state: p.ok ? "ok" : "fail", duration: p.duration_s };
      steps = at >= 0 ? steps.map((step, i) => (i === at ? { ...step, ...done } : step)) : [...steps, done];
    } else if (p.kind === "thinking") {
      steps = [...steps, { kind: "thinking", text: p.text || "" }];
    }
    if (steps.length > MAX_STEPS) steps = steps.slice(steps.length - MAX_STEPS);
    return { ...item, agent: { ...agent, steps } };
  });
}

export function agentFinished(items: ChatItem[], p: ForgeEvent["payload"]): ChatItem[] {
  return withAgent(items, p.id, (agent, item) => {
    const done = { ok: Boolean(p.ok), tool_calls: p.tool_calls ?? 0, failed_calls: p.failed_calls ?? 0, duration_s: p.duration_s ?? 0 };
    // A row made only for this agent has no tool call of its own to finish it.
    const own = item.id === agent.id;
    return { ...item, agent: { ...agent, done }, ...(own ? { state: done.ok ? ("ok" as const) : ("fail" as const), duration: done.duration_s } : {}) };
  });
}

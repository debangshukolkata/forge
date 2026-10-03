// What a subagent did, nested inside its row (D-181): its own tool calls and short reasoning notes, in order.
import { AlertOctagon, CheckCircle2, XCircle } from "lucide-react";
import type { AgentStep, AgentView } from "../types";
import { Spinner } from "./ui";

const ROLE_LABEL: Record<string, string> = {
  explore: "Explorer",
  reviewer: "Reviewer",
  debugger: "Debugger",
  verifier: "Verifier",
};

export function roleLabel(role: string): string {
  return ROLE_LABEL[role] ?? role.charAt(0).toUpperCase() + role.slice(1);
}

/** The newest thing the agent is doing or did, for the collapsed row. */
export function latestStepText(agent: AgentView): string {
  const step = [...agent.steps].reverse().find((s) => s.kind === "tool" || s.text);
  if (!step) return "starting…";
  return step.kind === "tool" ? `${step.name}: ${step.summary}` : step.text ?? "";
}

export function agentCounts(agent: AgentView): string {
  const calls = agent.done ? agent.done.tool_calls : agent.steps.filter((s) => s.kind === "tool").length;
  const failed = agent.done ? agent.done.failed_calls : agent.steps.filter((s) => s.state === "fail").length;
  return `${calls} call${calls === 1 ? "" : "s"}${failed ? `, ${failed} failed` : ""}`;
}

function StepRow({ step }: { step: AgentStep }) {
  if (step.kind === "thinking") {
    return <li className="px-1 text-[12px] italic text-fg-muted">{step.text}</li>;
  }
  return (
    <li className="flex items-center gap-2 px-1 text-[12.5px]">
      {step.state === "running" ? (
        <Spinner className="h-3 w-3 shrink-0 text-accent" />
      ) : step.state === "ok" ? (
        <CheckCircle2 className="h-3 w-3 shrink-0 text-ok" aria-label="Succeeded" />
      ) : step.state === "fail" ? (
        <XCircle className="h-3 w-3 shrink-0 text-danger" aria-label="Failed" />
      ) : (
        <AlertOctagon className="h-3 w-3 shrink-0" aria-hidden />
      )}
      <span className="shrink-0 font-mono text-[11.5px] font-semibold">{step.name}</span>
      <span className="min-w-0 flex-1 truncate text-fg-muted" title={step.summary}>
        {step.summary}
      </span>
      {step.duration !== undefined && <span className="shrink-0 font-mono text-[11px] tabular-nums text-fg-muted">{step.duration}s</span>}
    </li>
  );
}

export function AgentSteps({ agent }: { agent: AgentView }) {
  if (agent.steps.length === 0) {
    return <div className="text-[12px] text-fg-muted">No steps yet.</div>;
  }
  return (
    <div>
      <div className="mb-1 font-mono text-[10.5px] font-semibold uppercase tracking-wider text-fg-muted">
        {roleLabel(agent.role)} steps · {agentCounts(agent)}
      </div>
      <ol aria-label={`${roleLabel(agent.role)} steps`} className="max-h-72 space-y-1 overflow-y-auto rounded-lg bg-surface p-2">
        {agent.steps.map((step, index) => (
          <StepRow key={index} step={step} />
        ))}
      </ol>
    </div>
  );
}

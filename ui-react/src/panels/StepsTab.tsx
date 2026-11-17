// The Steps tab (FC1, D-629): what DebCraft did for each request, top to bottom, one box per step, with failures and
// what it did by itself on the way (a sign-in after a 401) as side branches. A click goes to that point in the chat.
// Everything comes from the events (steps.ts), so it grows while DebCraft works and looks the same after a reload.
import { ChevronDown, ChevronRight, CornerDownRight, Workflow } from "lucide-react";
import { useMemo, useState } from "react";
import { Empty, Spinner } from "../components/ui";
import { cx } from "../lib";
import { buildSteps, took, type Request, type Step } from "../steps";
import type { Forge } from "../useForge";

function StepRow({ step, last, onJump }: { step: Step; last: boolean; onJump: (seq: number) => void }) {
  const failed = step.branches.some((branch) => branch.bad && !branch.fixed);
  return (
    <li className="relative pl-6" data-step={step.kind}>
      {!last && <span className="absolute bottom-0 left-[7px] top-4 w-px bg-border" aria-hidden />}
      <span
        className={cx(
          "absolute left-[3px] top-[7px] h-2.5 w-2.5 rounded-full",
          step.running ? "animate-pulse bg-accent" : failed ? "bg-danger" : "bg-ok",
        )}
        aria-hidden
      />
      <button
        type="button"
        onClick={() => onJump(step.seq)}
        title="Show this step in the chat"
        className="flex w-full cursor-pointer items-baseline gap-2 rounded-md px-1.5 py-1 text-left transition-colors duration-150 hover:bg-raised focus-visible:outline-2 focus-visible:outline-accent"
      >
        <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{step.label}</span>
        {step.running ? <Spinner className="h-3 w-3 shrink-0" /> : <span className="shrink-0 text-[11.5px] tabular-nums text-fg-muted">{took(step.seconds)}</span>}
      </button>
      {step.detail && <p className="truncate px-1.5 text-[11.5px] text-fg-muted">{step.detail}</p>}
      {step.branches.map((branch) => (
        <button
          key={branch.seq}
          type="button"
          onClick={() => onJump(branch.seq)}
          className="flex w-full cursor-pointer items-center gap-1.5 rounded-md px-1.5 py-0.5 text-left text-[12px] hover:bg-raised"
        >
          <CornerDownRight className="h-3 w-3 shrink-0 text-fg-muted" aria-hidden />
          <span className={cx("min-w-0 flex-1 truncate", branch.bad ? "text-danger" : "text-fg-muted")}>
            {branch.bad ? "✕ " : ""}
            {branch.text}
          </span>
          {branch.bad && <span className="shrink-0 text-[11px] text-fg-muted">{branch.fixed ? "then worked" : "not solved"}</span>}
        </button>
      ))}
      <div className="h-2.5" />
    </li>
  );
}

function RequestBlock({ request, open, onToggle, onJump }: { request: Request; open: boolean; onToggle: () => void; onJump: (seq: number) => void }) {
  const failures = request.steps.reduce((sum, step) => sum + step.branches.filter((branch) => branch.bad).length, 0);
  return (
    <section className="border-b border-border" data-testid="steps-request">
      <button
        type="button"
        aria-expanded={open}
        onClick={onToggle}
        className="flex w-full cursor-pointer items-center gap-2 px-4 py-2.5 text-left transition-colors duration-150 hover:bg-raised"
      >
        {open ? <ChevronDown className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden /> : <ChevronRight className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden />}
        <span className="min-w-0 flex-1 truncate text-[13px] font-semibold">{request.text || "Work without a message"}</span>
        <span className="shrink-0 text-[11.5px] text-fg-muted">
          {request.steps.length} {request.steps.length === 1 ? "step" : "steps"}{failures ? `, ${failures} failed` : ""}
          {took(request.seconds) ? ` · ${took(request.seconds)}` : ""}
        </span>
      </button>
      {open && (
        <ol className="px-4 pb-2 pt-1">
          {request.steps.map((step, index) => (
            <StepRow key={step.seq} step={step} last={index === request.steps.length - 1 && !request.answer} onJump={onJump} />
          ))}
          {request.answer && (
            <li className="relative pl-6" data-step="answer">
              <span className="absolute left-[2px] top-[6px] h-3 w-3 rounded-full border-2 border-ok bg-surface" aria-hidden />
              <button
                type="button"
                onClick={() => onJump(request.answer!.seq)}
                className="w-full cursor-pointer rounded-md px-1.5 py-1 text-left text-[13px] hover:bg-raised"
              >
                <span className="font-medium">Answer: </span>
                <span className="text-fg-muted">{request.answer.text}</span>
              </button>
            </li>
          )}
        </ol>
      )}
    </section>
  );
}

export function StepsTab({ forge, onJump }: { forge: Forge; onJump: (seq: number) => void }) {
  const requests = useMemo(() => buildSteps(forge.events).filter((request) => request.steps.length > 0), [forge.events]);
  const [toggled, setToggled] = useState<Record<number, boolean>>({});
  if (requests.length === 0) {
    return (
      <Empty icon={<Workflow className="h-6 w-6" />} title="No steps yet">
        They appear as DebCraft works: one line per step, with what failed on the way.
      </Empty>
    );
  }
  const latest = requests[requests.length - 1].seq;
  return (
    <div className="min-h-0 flex-1 overflow-y-auto" data-testid="steps">
      {[...requests].reverse().map((request) => {
        const open = toggled[request.seq] ?? request.seq === latest; // the request in hand is open, earlier ones folded
        return (
          <RequestBlock
            key={request.seq}
            request={request}
            open={open}
            onToggle={() => setToggled({ ...toggled, [request.seq]: !open })}
            onJump={onJump}
          />
        );
      })}
    </div>
  );
}

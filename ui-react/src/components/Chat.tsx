import {
  AlertOctagon, Hand, HelpCircle, Info, ShieldQuestion, Terminal, Upload,
} from "lucide-react";
import { useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { api, Code, DRAFT_EVENT, Markdown, cx } from "../lib";
import type { ChatItem, EnvironmentOverview, UserInput } from "../types";
import type { Forge } from "../useForge";
import { UsageBadge } from "../usage";
import { Composer, useAttachments } from "./Composer";
import { QuestionDialog, QuestionForm, QuestionPopup } from "./QuestionDialog";
import { TodoStrip } from "./TodoList";
import { LookingGroup, ThinkingLine, ToolCard, groupLookingRuns } from "./ToolRows";
import { Badge, Button, CopyButton, Textarea } from "./ui";


export function Chat({ forge, onOpenEnvironment }: { forge: Forge; onOpenEnvironment?: () => void }) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const { items } = forge.timeline;
  const attachments = useAttachments();
  const [dragging, setDragging] = useState(false);
  // The oldest question still waiting for an answer opens as a pop-up; "Answer later" leaves it in the chat.
  const pending = items.find(
    (item): item is Extract<ChatItem, { kind: "question" }> => item.kind === "question" && forge.timeline.answered[item.id] === undefined,
  );
  const [dismissed, setDismissed] = useState<string[]>([]);
  const popupId = pending && forge.controls && !dismissed.includes(pending.id) ? pending.id : null;

  useLayoutEffect(() => {
    const box = scroller.current;
    if (box && (stick.current || forge.replaying)) box.scrollTop = box.scrollHeight;
  }, [items, forge.replaying]);

  return (
    <QuestionPopup.Provider value={{ popupId, reopen: (id) => setDismissed((list) => list.filter((x) => x !== id)) }}>
    <div
      className="relative flex min-h-0 flex-1 flex-col"
      onDragOver={(e) => {
        if (e.dataTransfer.types.includes("Files")) {
          e.preventDefault();
          setDragging(true);
        }
      }}
      onDragLeave={(e) => {
        if (e.currentTarget === e.target) setDragging(false);
      }}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (e.dataTransfer.files.length && forge.controls) void attachments.add(e.dataTransfer.files);
      }}
    >
      {dragging && (
        <div className="pointer-events-none absolute inset-3 z-10 flex flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed border-accent bg-bg/85 text-accent">
          <Upload className="h-8 w-8" aria-hidden />
          <span className="font-medium">Drop files or images to attach them</span>
        </div>
      )}
      <div
        ref={scroller}
        onScroll={(e) => {
          const box = e.currentTarget;
          stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 160;
        }}
        className="min-h-0 flex-1 overflow-y-auto"
        aria-live="polite"
      >
        <div className="mx-auto flex max-w-[760px] flex-col gap-4 px-6 py-6">
          {items.length === 0 && !forge.replaying && <Welcome forge={forge} onOpenEnvironment={onOpenEnvironment} />}
          {!forge.controls && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-warn/40 bg-warn-soft px-4 py-2.5 text-[13px] text-warn">
              Another window controls this project; this one watches.
              <Button size="sm" onClick={forge.takeControl}>
                Take control
              </Button>
            </div>
          )}
          {groupLookingRuns(items).map((row) =>
            row.kind === "looking" ? (
              <div key={row.items[0].key} data-seq={/^e\d+$/.test(row.items[0].key) ? row.items[0].key.slice(1) : undefined}>
                <LookingGroup items={row.items} />
              </div>
            ) : (
              <div key={row.item.key} data-seq={/^e\d+$/.test(row.item.key) ? row.item.key.slice(1) : undefined}>
                <Item item={row.item} forge={forge} />
              </div>
            ),
          )}
        </div>
      </div>
      <TodoStrip todos={forge.timeline.todos} />
      <Composer forge={forge} attachments={attachments} />
      {pending && popupId && (
        <QuestionDialog id={pending.id} p={pending.payload} forge={forge} onDismiss={() => setDismissed((list) => [...list, pending.id])} />
      )}
    </div>
    </QuestionPopup.Provider>
  );
}

const STARTERS: Record<"A" | "B", string[]> = {
  B: [
    "Build a function from a signature I paste",
    "Write a small API with tests",
    "Add tests for a module I describe",
  ],
  A: [
    "Explain how this repository is structured",
    "Find and fix a bug I describe",
    "Add a feature and tests for it",
  ],
};

// What a new project's chat opens with (D-186): what Forge is about to work with, and ways to begin.
function Welcome({ forge, onOpenEnvironment }: { forge: Forge; onOpenEnvironment?: () => void }) {
  const workspace = forge.state.workspace;
  const mode = workspace?.mode === "B" ? "B" : "A";
  const [env, setEnv] = useState<EnvironmentOverview | null>(null);
  useEffect(() => {
    api<EnvironmentOverview>("/api/environment").then(setEnv).catch(() => setEnv(null));
  }, []);
  const coder = env?.plan.roles.find((r) => r.role === "coder")?.model;
  const coderLabel = env?.plan.options.find((o) => o.key === coder)?.label;
  const confirmed = Boolean(env?.saved.confirmed_at);
  const draft = (text: string) => window.dispatchEvent(new CustomEvent(DRAFT_EVENT, { detail: text }));
  return (
    <div className="px-2 pb-4 pt-10 text-center">
      <h1 className="text-balance text-[34px] font-semibold leading-[1.1] tracking-[-0.3px]">
        {mode === "B" ? "What are we building?" : "What should we change?"}
      </h1>
      <p className="mx-auto mt-3 max-w-lg text-[17px] leading-[1.47] tracking-[-0.37px] text-fg-muted">
        {mode === "B"
          ? "Say what to build. Paste any function signatures or snippets it must use: Forge uses them exactly and asks what it needs to know."
          : "Describe the change. Forge reads the copy of your repository, proposes requirements and a plan for your approval, then builds and tests it."}
      </p>
      <div className="mt-5 flex flex-wrap items-center justify-center gap-2">
        {workspace && <Badge>{workspace.name}</Badge>}
        <Badge tone={mode === "B" ? "info" : "neutral"}>{mode === "B" ? "Standalone" : "Repository copy"}</Badge>
        {coderLabel && <Badge>Coder: {coderLabel}</Badge>}
        {onOpenEnvironment && (
          <button
            type="button"
            onClick={onOpenEnvironment}
            className="inline-flex cursor-pointer items-center gap-1 rounded-full border border-border px-2.5 py-0.5 text-[11.5px] font-semibold text-accent transition-colors duration-150 hover:bg-accent-soft"
          >
            {confirmed ? "Environment" : "Review environment"}
          </button>
        )}
      </div>
      <div className="mt-6 flex flex-wrap justify-center gap-2" aria-label="Ways to begin">
        {STARTERS[mode].map((text) => (
          <button
            key={text}
            type="button"
            onClick={() => draft(text)}
            className="cursor-pointer rounded-full border border-border bg-surface px-4 py-2 text-[13px] transition-colors duration-150 hover:border-accent hover:text-accent active:scale-95"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}

function Item({ item, forge }: { item: ChatItem; forge: Forge }) {
  switch (item.kind) {
    case "user":
      // Your message: a soft blue pill on the right, no avatar.
      return (
        <div className="flex justify-end">
          <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-[20px] bg-accent-soft px-4 py-2.5 text-[14.5px] leading-[1.5]">
            {item.text}
          </div>
        </div>
      );
    case "assistant":
      // Forge's reply: plain text on the page, no box and no avatar.
      return (
        <div className="min-w-0 text-[14.5px] leading-[1.6]">
          {item.streaming ? (
            <div className="caret whitespace-pre-wrap break-words">{item.text}</div>
          ) : (
            <Markdown text={item.text} />
          )}
          {!item.streaming && item.usage && (item.usage.input > 0 || item.usage.cost > 0) && (
            <UsageBadge
              className="mt-1.5"
              bucket={{ input_tokens: item.usage.input, output_tokens: item.usage.output, cost_usd: item.usage.cost }}
              limits={forge.costColors?.reply}
            />
          )}
        </div>
      );
    case "tool":
      return <ToolCard item={item} />;
    case "thinking":
      return <ThinkingLine text={item.text} />;
    case "notice":
      return <Notice kind={item.noticeKind} text={item.text} />;
    case "error":
      return (
        <div role="alert" className="flex gap-2 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger">
          <AlertOctagon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span className="whitespace-pre-wrap">{item.text}</span>
        </div>
      );
    case "approval":
      return <ApprovalCard id={item.id} p={item.payload} forge={forge} />;
    case "question":
      return <QuestionCard id={item.id} p={item.payload} forge={forge} />;
    case "action":
      return <ActionCard id={item.id} p={item.payload} forge={forge} />;
  }
}

function Notice({ kind, text }: { kind: string; text: string }) {
  if (kind === "command_output") return <Code text={text} />;
  const tone = kind === "stuck" || kind === "injection" ? "warn" : "info";
  return (
    <div className={cx("flex gap-2 rounded-md px-3 py-1.5 text-[12.5px]", tone === "warn" ? "bg-warn-soft text-warn" : "text-fg-muted")}>
      <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
      <span className="whitespace-pre-wrap break-words">{text}</span>
    </div>
  );
}

// --- cards that wait for the user ---

function AskCard({ kind, icon, title, answered, children }: { kind: "approval" | "question" | "action"; icon: ReactNode; title: ReactNode; answered?: string; children: ReactNode }) {
  return (
    <div data-card={kind} data-pending={answered === undefined ? "" : undefined} className={cx("rounded-xl border bg-surface p-4", answered === undefined ? "border-warn/60 shadow-[0_0_0_3px_var(--warn-soft)]" : "border-border opacity-80")}>
      <div className="mb-3 flex items-center gap-2">
        <span className={cx("flex h-7 w-7 items-center justify-center rounded-full", answered === undefined ? "bg-warn-soft text-warn" : "bg-raised text-fg-muted")}>
          {icon}
        </span>
        <h4 className="min-w-0 flex-1 break-words font-semibold">{title}</h4>
        {answered !== undefined && (
          <span
            data-testid="answered-badge"
            title={answered || "Answered"}
            className="min-w-0 max-w-[40%] shrink-0 truncate rounded-full border border-border bg-raised px-2 py-0.5 text-[11.5px] font-medium text-fg-muted"
          >
            {answered || "Answered"}
          </span>
        )}
      </div>
      {/* min-w-0: a fieldset's default min-width is its widest content, so a long code line would widen the whole chat. */}
      <fieldset disabled={answered !== undefined} className="min-w-0 space-y-3">
        {children}
      </fieldset>
    </div>
  );
}

type P = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

function ApprovalCard({ id, p, forge }: { id: string; p: P; forge: Forge }) {
  const [text, setText] = useState("");
  const answered = forge.timeline.answered[id];
  const reply = (input: UserInput, label: string) => forge.answer(id, input, label);
  if (p.kind) {
    return (
      <AskCard kind="approval" icon={<ShieldQuestion className="h-4 w-4" />} title={`Approve the ${p.kind}?`} answered={answered}>
        <div className="max-h-[480px] overflow-y-auto rounded-lg border border-border bg-bg p-4">
          <Markdown text={p.markdown || p.summary || ""} />
        </div>
        <Textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="What should change? (for Request changes)" />
        <div className="flex flex-wrap gap-2">
          <Button variant="primary" onClick={() => reply({ kind: "approve", request_id: p.id }, "Approved")}>
            Approve
          </Button>
          <Button onClick={() => reply({ kind: "reject", request_id: p.id, instruction: text || "Please revise." }, "Changes requested")}>
            Request changes
          </Button>
          <Button variant="danger" onClick={() => reply({ kind: "reject", request_id: p.id, instruction: text || "Rejected." }, "Rejected")}>
            Reject
          </Button>
        </div>
      </AskCard>
    );
  }
  const prefix = p.can_remember_prefix && !p.always_ask ? String(p.can_remember_prefix) : null;
  return (
    <AskCard kind="approval" icon={<Terminal className="h-4 w-4" />} title={<>Allow <span className="font-mono">{p.tool}</span>?</>} answered={answered}>
      {p.command ? <Code text={p.command} language="powershell" /> : <div className="text-[13px]">{p.summary}</div>}
      {p.reason && <div className="text-[12.5px] text-fg-muted">{p.reason}</div>}
      <Textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="If you deny: tell Forge what to do instead (optional)" />
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => reply({ kind: "approve", request_id: p.id, scope: "once" }, "Allowed once")}>
          Allow once
        </Button>
        <Button variant="danger" onClick={() => reply({ kind: "reject", request_id: p.id, instruction: text || null }, "Denied")}>
          Deny
        </Button>
      </div>
      {prefix && (
        <button
          type="button"
          data-testid="always-allow"
          title={prefix}
          onClick={() => reply({ kind: "approve", request_id: p.id, scope: "prefix" }, `Always allowed '${prefix}'`)}
          className="flex w-full cursor-pointer items-center gap-2 rounded-lg border border-border bg-raised px-3 py-2 text-left text-[13px] font-medium transition-colors duration-150 hover:border-border-strong hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
        >
          <span className="shrink-0">Always allow</span>
          <span className="min-w-0 flex-1 truncate font-mono text-[12px] font-normal text-fg-muted">{prefix}</span>
        </button>
      )}
    </AskCard>
  );
}

function QuestionCard({ id, p, forge }: { id: string; p: P; forge: Forge }) {
  const answered = forge.timeline.answered[id];
  const { popupId, reopen } = useContext(QuestionPopup);
  const icon = <HelpCircle className="h-4 w-4" />;
  if (answered === undefined && popupId === id) {
    // The question is open as a pop-up: this card only marks the place in the conversation.
    return (
      <AskCard kind="question" icon={icon} title={p.question} answered={undefined}>
        <div className="text-[13px] text-fg-muted">Waiting for your answer in the pop-up.</div>
      </AskCard>
    );
  }
  return (
    <AskCard kind="question" icon={icon} title={p.question} answered={answered}>
      {p.context && <Markdown text={p.context} className="text-fg-muted" />}
      {answered === undefined && (
        <>
          <QuestionForm id={id} p={p} forge={forge} />
          <button type="button" onClick={() => reopen(id)} className="cursor-pointer text-[12px] font-semibold text-accent hover:underline">
            Show as a pop-up
          </button>
        </>
      )}
    </AskCard>
  );
}

function ActionCard({ id, p, forge }: { id: string; p: P; forge: Forge }) {
  const [note, setNote] = useState("");
  const answered = forge.timeline.answered[id];
  const choose = (choice: string, label: string) =>
    forge.answer(id, { kind: "answer", question_id: p.id, choice, text: note.trim() || null }, label);
  return (
    <AskCard kind="action" icon={<Hand className="h-4 w-4" />} title={p.title || "A step for you"} answered={answered}>
      <ol className="space-y-2">
        {(p.steps || []).map((step: string, index: number) => (
          <li key={index} className="flex items-start gap-2 rounded-md bg-bg px-3 py-2 text-[13px]">
            <span className="mt-0.5 font-mono text-[11.5px] text-fg-muted">{index + 1}.</span>
            <span className="min-w-0 flex-1 whitespace-pre-wrap break-words font-mono text-[12.5px]">{step}</span>
            <CopyButton text={step} />
          </li>
        ))}
      </ol>
      {p.verify_command && (
        <div className="text-[12.5px] text-fg-muted">
          Forge will check with <code className="rounded bg-muted px-1 font-mono">{p.verify_command}</code>
        </div>
      )}
      <Textarea rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="Reason, or paste the output if it failed" />
      <div className="flex flex-wrap gap-2">
        <Button variant="primary" onClick={() => choose("done", "Done")}>
          Done
        </Button>
        <Button onClick={() => choose("skip", "Skipped")}>Skip</Button>
        <Button onClick={() => choose("cant", "You can't do it")}>I can't</Button>
        <Button variant="danger" onClick={() => choose("failed", "It failed")}>
          It failed
        </Button>
      </div>
    </AskCard>
  );
}


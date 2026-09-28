import {
  AlertOctagon, Bot, CheckCircle2, ChevronRight, Hand, HelpCircle, Info, ShieldQuestion, Terminal, Upload, User,
  Wrench, XCircle,
} from "lucide-react";
import { useLayoutEffect, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { Code, Markdown, cx } from "../lib";
import type { ChatItem, UserInput } from "../types";
import type { Forge } from "../useForge";
import { UsageBadge } from "../usage";
import { ProgressHeader } from "./Activity";
import { Composer, useAttachments } from "./Composer";
import { Badge, Button, CopyButton, Spinner, Textarea } from "./ui";


export function Chat({ forge }: { forge: Forge }) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const { items } = forge.timeline;
  const attachments = useAttachments();
  const [dragging, setDragging] = useState(false);

  useLayoutEffect(() => {
    const box = scroller.current;
    if (box && (stick.current || forge.replaying)) box.scrollTop = box.scrollHeight;
  }, [items, forge.replaying]);

  return (
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
      <ProgressHeader forge={forge} />
      <div
        ref={scroller}
        onScroll={(e) => {
          const box = e.currentTarget;
          stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 160;
        }}
        className="min-h-0 flex-1 overflow-y-auto"
        aria-live="polite"
      >
        <div className="mx-auto flex max-w-3xl flex-col gap-3 px-6 py-6">
          {items.length === 0 && !forge.replaying && <Welcome standalone={forge.state.workspace?.mode === "B"} />}
          {!forge.controls && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-warn/40 bg-warn-soft px-4 py-2.5 text-[13px] text-warn">
              Another window controls this project; this one watches.
              <Button size="sm" onClick={forge.takeControl}>
                Take control
              </Button>
            </div>
          )}
          {items.map((item) => (
            <div key={item.key} data-seq={/^e\d+$/.test(item.key) ? item.key.slice(1) : undefined}>
              <Item item={item} forge={forge} />
            </div>
          ))}
        </div>
      </div>
      <Composer forge={forge} attachments={attachments} />
    </div>
  );
}

function Welcome({ standalone }: { standalone: boolean }) {
  return (
    <div className="rounded-xl border border-dashed border-border-strong p-6 text-center">
      <div className="mx-auto mb-3 flex h-10 w-10 items-center justify-center rounded-full bg-accent-soft text-accent">
        <Bot className="h-5 w-5" aria-hidden />
      </div>
      <div className="font-medium">Describe what you need</div>
      <p className="mx-auto mt-1 max-w-md text-[13px] text-fg-muted">
        {standalone
          ? "Say what to build. Paste any function signatures or snippets it must use — Forge uses them exactly and asks what it needs to know."
          : "Describe the change. Forge reads the copy of your repository, proposes requirements and a plan for your approval, then builds and tests it."}
      </p>
    </div>
  );
}

function Item({ item, forge }: { item: ChatItem; forge: Forge }) {
  switch (item.kind) {
    case "user":
      return (
        <Row icon={<User className="h-4 w-4" />} tone="user">
          <div className="whitespace-pre-wrap break-words">{item.text}</div>
        </Row>
      );
    case "assistant":
      return (
        <Row icon={<Bot className="h-4 w-4" />} tone="assistant">
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
        </Row>
      );
    case "tool":
      return <ToolCard item={item} />;
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

function Row({ icon, tone, children }: { icon: ReactNode; tone: "user" | "assistant"; children: ReactNode }) {
  return (
    <div className="flex gap-3">
      <div
        className={cx(
          "mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          tone === "user" ? "bg-raised text-fg-muted" : "bg-accent-soft text-accent",
        )}
        aria-hidden
      >
        {icon}
      </div>
      <div className={cx("min-w-0 flex-1 pt-0.5", tone === "user" && "rounded-lg bg-raised px-3 py-2")}>{children}</div>
    </div>
  );
}

function ToolCard({ item }: { item: Extract<ChatItem, { kind: "tool" }> }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="ml-10 rounded-lg border border-border bg-surface">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-2 px-3 py-2 text-left text-[13px] transition-colors duration-150 hover:bg-raised rounded-lg"
      >
        <ChevronRight className={cx("h-3.5 w-3.5 shrink-0 text-fg-muted transition-transform duration-150", open && "rotate-90")} aria-hidden />
        <Wrench className="h-3.5 w-3.5 shrink-0 text-fg-muted" aria-hidden />
        <span className="shrink-0 font-mono text-[12.5px] font-medium">{item.name}</span>
        <span className="min-w-0 flex-1 truncate text-fg-muted">{item.summary}</span>
        {item.state === "running" ? (
          <Spinner className="h-3.5 w-3.5 text-accent" />
        ) : item.state === "ok" ? (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-accent" aria-label="Succeeded" />
        ) : (
          <XCircle className="h-3.5 w-3.5 shrink-0 text-danger" aria-label="Failed" />
        )}
        {item.duration !== undefined && <span className="shrink-0 font-mono text-[11.5px] tabular-nums text-fg-muted">{item.duration}s</span>}
      </button>
      {open && item.preview && <Code text={item.preview} className="m-2 mt-0 max-h-80 text-[12px]" />}
    </div>
  );
}

function Notice({ kind, text }: { kind: string; text: string }) {
  if (kind === "command_output") return <Code text={text} className="ml-10" />;
  const tone = kind === "stuck" || kind === "injection" ? "warn" : "info";
  return (
    <div className={cx("ml-10 flex gap-2 rounded-md px-3 py-1.5 text-[12.5px]", tone === "warn" ? "bg-warn-soft text-warn" : "text-fg-muted")}>
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
        <h4 className="min-w-0 flex-1 font-semibold">{title}</h4>
        {answered !== undefined && <Badge>{answered || "Answered"}</Badge>}
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
        {prefix && (
          <Button onClick={() => reply({ kind: "approve", request_id: p.id, scope: "prefix" }, `Always allowed '${prefix}'`)}>
            Always allow <span className="font-mono">{prefix}</span>
          </Button>
        )}
        <Button variant="danger" onClick={() => reply({ kind: "reject", request_id: p.id, instruction: text || null }, "Denied")}>
          Deny
        </Button>
      </div>
    </AskCard>
  );
}

function QuestionCard({ id, p, forge }: { id: string; p: P; forge: Forge }) {
  const [text, setText] = useState("");
  const answered = forge.timeline.answered[id];
  const options: P[] = p.options || [];
  const choose = (label: string) => forge.answer(id, { kind: "answer", question_id: p.id, choice: label }, `You chose: ${label}`);
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const option = options[Number(event.key) - 1];
    if (option && answered === undefined && event.target === event.currentTarget) choose(option.label);
  };
  return (
    <div tabIndex={0} onKeyDown={onKey} className="rounded-xl outline-none">
      <AskCard kind="question" icon={<HelpCircle className="h-4 w-4" />} title={p.question} answered={answered}>
        {p.context && <Markdown text={p.context} className="text-fg-muted" />}
        <div className="space-y-2">
          {options.map((option, index) => {
            const recommended = option.label === p.recommended;
            return (
              <button
                key={option.label}
                type="button"
                data-recommended={recommended ? "" : undefined}
                onClick={() => choose(option.label)}
                className={cx(
                  "flex w-full cursor-pointer gap-3 rounded-lg border p-3 text-left transition-colors duration-150",
                  recommended ? "border-accent/60 bg-accent-soft hover:border-accent" : "border-border hover:border-border-strong hover:bg-raised",
                )}
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded border border-border-strong font-mono text-[11px] text-fg-muted">
                  {index + 1}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2 font-medium">
                    {option.label}
                    {recommended && <Badge tone="accent">Recommended</Badge>}
                  </span>
                  {option.description && <span className="mt-0.5 block text-[12.5px] text-fg-muted">{option.description}</span>}
                  {(option.pros || option.cons || option.risks) && (
                    <span className="mt-1 block space-y-0.5 text-[12px]">
                      {option.pros && <span className="block text-accent">Pros: {option.pros}</span>}
                      {option.cons && <span className="block text-warn">Cons: {option.cons}</span>}
                      {option.risks && <span className="block text-danger">Risks: {option.risks}</span>}
                    </span>
                  )}
                </span>
              </button>
            );
          })}
        </div>
        <div className="flex gap-2">
          <Textarea rows={1} value={text} onChange={(e) => setText(e.target.value)} placeholder="Or type your own answer…" className="flex-1" />
          <Button
            disabled={!text.trim()}
            onClick={() => forge.answer(id, { kind: "answer", question_id: p.id, text: text.trim() }, `You answered: ${text.trim()}`)}
          >
            Send
          </Button>
        </div>
      </AskCard>
    </div>
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


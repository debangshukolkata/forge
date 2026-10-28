import {
  AlertOctagon, ArrowDown, Check, ChevronDown, Hand, HelpCircle, Info, ShieldQuestion, Terminal, Upload,
} from "lucide-react";
import { useContext, useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { api, Code, DRAFT_EVENT, Markdown, cx } from "../lib";
import type { ChatItem, EnvironmentOverview, SlideSet, UserInput } from "../types";
import type { Forge } from "../useForge";
import { UsageBadge } from "../usage";
import { Composer, useAttachments } from "./Composer";
import { SlideStrip } from "./Slides";
import { QuestionDialog, QuestionForm, QuestionPopup } from "./QuestionDialog";
import { LookingGroup, ThinkingLine, ToolCard, groupLookingRuns } from "./ToolRows";
import { Badge, Button, CopyButton, Textarea } from "./ui";


export function Chat({ forge, onOpenEnvironment }: { forge: Forge; onOpenEnvironment?: () => void }) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  // Scrolled away from the newest message (the "jump to latest" button shows) and whether something new arrived meanwhile (a dot on the button).
  const [away, setAway] = useState(false);
  const [unread, setUnread] = useState(false);
  const jumpToLatest = () => {
    const box = scroller.current;
    if (!box) return;
    stick.current = true;
    setAway(false);
    setUnread(false);
    box.scrollTo({ top: box.scrollHeight, behavior: window.matchMedia("(prefers-reduced-motion: reduce)").matches ? "auto" : "smooth" });
  };
  const { items } = forge.timeline;
  const attachments = useAttachments();
  const [dragging, setDragging] = useState(false);
  // The oldest question still waiting for an answer opens as a pop-up; "Answer later" leaves it in the chat.
  const pending = items.find(
    (item): item is Extract<ChatItem, { kind: "question" }> => item.kind === "question" && forge.timeline.answered[item.key] === undefined,
  );
  const [dismissed, setDismissed] = useState<string[]>([]);
  const popupId = pending && forge.controls && !dismissed.includes(pending.key) ? pending.key : null;

  const content = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const box = scroller.current;
    if (box && (stick.current || forge.replaying)) box.scrollTop = box.scrollHeight;
    else if (box && items.length > 0) setUnread(true); // the reader is looking at older messages and something new came in
  }, [items, forge.replaying]);
  // Things change height without a new message: a picture finishes loading, a code block is decorated, a card opens, or the activity line above the
  // message box appears and the chat area gets shorter. Follow the bottom through those too, unless the reader has scrolled up.
  useEffect(() => {
    const box = scroller.current;
    const inner = content.current;
    if (!box || !inner || typeof ResizeObserver === "undefined") return;
    const follow = () => {
      if (stick.current) box.scrollTop = box.scrollHeight;
    };
    const observer = new ResizeObserver(follow);
    observer.observe(inner);
    observer.observe(box);
    return () => observer.disconnect();
  }, []);

  return (
    <QuestionPopup.Provider value={{ popupId, reopen: (id) => setDismissed((list) => list.filter((x) => x !== id)) }}>
    <div
      className="chat-scale relative flex min-h-0 flex-1 flex-col"
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
      <div className="relative flex min-h-0 flex-1 flex-col">
      <div
        ref={scroller}
        onScroll={(e) => {
          const box = e.currentTarget;
          stick.current = box.scrollHeight - box.scrollTop - box.clientHeight < 160;
          setAway(!stick.current);
          if (stick.current) setUnread(false);
        }}
        className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden"
        aria-live="polite"
      >
        <div ref={content} className="mx-auto flex max-w-[var(--chat-max,760px)] flex-col gap-4 px-6 py-6">
          {items.length === 0 && !forge.replaying && <Welcome forge={forge} onOpenEnvironment={onOpenEnvironment} />}
          {!forge.controls && (
            <div className="flex items-center justify-between gap-3 rounded-lg border border-warn/40 bg-warn-soft px-4 py-2.5 text-[13px] text-warn">
              Another window controls this project; this one watches.
              <Button size="sm" onClick={forge.takeControl}>
                Take control
              </Button>
            </div>
          )}
          {groupIntoTurns(groupLookingRuns(items)).map((turn) => (
            // One turn = your message plus everything DebCraft did for it. The message sticks to the top while that
            // turn is on screen, so a scrolled-up reply always shows which prompt it answers.
            <div key={turn.key} className="flex flex-col gap-4">
              {turn.rows.map((row) =>
                row.kind === "looking" ? (
                  <div key={row.items[0].key} data-seq={/^e\d+$/.test(row.items[0].key) ? row.items[0].key.slice(1) : undefined}>
                    <LookingGroup items={row.items} />
                  </div>
                ) : row.item.kind === "user" ? (
                  <div key={row.item.key} data-seq={/^e\d+$/.test(row.item.key) ? row.item.key.slice(1) : undefined} className="sticky top-0 z-10 -mx-6 bg-bg/95 px-6 py-2 backdrop-blur">
                    <StickyPrompt text={row.item.text} />
                  </div>
                ) : (
                  <div key={row.item.key} data-seq={/^e\d+$/.test(row.item.key) ? row.item.key.slice(1) : undefined}>
                    <Item item={row.item} forge={forge} />
                  </div>
                ),
              )}
            </div>
          ))}
        </div>
      </div>
      {away && (
        <button
          type="button"
          onClick={jumpToLatest}
          title="Jump to the latest message"
          aria-label={unread ? "Jump to the latest message, new messages below" : "Jump to the latest message"}
          className="absolute bottom-4 right-6 z-20 grid h-10 w-10 place-items-center rounded-full border border-border bg-surface text-fg shadow-lg transition hover:bg-raised focus-visible:outline-2 focus-visible:outline-accent"
        >
          <ArrowDown className="h-4 w-4" aria-hidden />
          {unread && <span aria-hidden="true" className="absolute right-0 top-0 h-2.5 w-2.5 rounded-full bg-accent ring-2 ring-surface" />}
        </button>
      )}
      </div>
      <Composer forge={forge} attachments={attachments} />
      {pending && popupId && (
        <QuestionDialog itemKey={pending.key} p={pending.payload} forge={forge} onDismiss={() => setDismissed((list) => [...list, pending.key])} />
      )}
    </div>
    </QuestionPopup.Provider>
  );
}

type ChatRow = ReturnType<typeof groupLookingRuns>[number];

/** Split rows at each user message; rows before the first message form a turn of their own. */
function groupIntoTurns(rows: ChatRow[]): Array<{ key: string; rows: ChatRow[] }> {
  const turns: Array<{ key: string; rows: ChatRow[] }> = [];
  for (const row of rows) {
    const startsTurn = row.kind === "single" && row.item.kind === "user";
    if (startsTurn || turns.length === 0) turns.push({ key: row.kind === "looking" ? row.items[0].key : row.item.key, rows: [] });
    turns[turns.length - 1].rows.push(row);
  }
  return turns;
}

/** Your message, long ones cut to three lines while pinned; click to read all of it. */
function StickyPrompt({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="flex justify-end">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        title={open ? "Show less" : "Show the whole message"}
        className={cx(
          "max-w-[85%] cursor-pointer whitespace-pre-wrap break-words rounded-[20px] bg-accent-soft px-4 py-2.5 text-left text-[13.5px] leading-[1.5]",
          !open && "line-clamp-3",
        )}
      >
        {text}
      </button>
    </div>
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

// What a new project's chat opens with (D-186): what DebCraft is about to work with, and ways to begin.
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
          ? "Say what to build. Paste any function signatures or snippets it must use: DebCraft uses them exactly and asks what it needs to know."
          : "Describe the change. DebCraft reads the copy of your repository, proposes requirements and a plan for your approval, then builds and tests it."}
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
          <div className="max-w-[85%] whitespace-pre-wrap break-words rounded-[20px] bg-accent-soft px-4 py-2.5 text-[13.5px] leading-[1.5]">
            {item.text}
          </div>
        </div>
      );
    case "assistant":
      // DebCraft's reply: plain text on the page, no box and no avatar.
      return (
        <div className="min-w-0 text-[13.5px] leading-[1.6]">
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
      return <Notice kind={item.noticeKind} text={item.text} image={item.image} slides={item.slides} />;
    case "error":
      return (
        <div role="alert" className="flex gap-2 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger">
          <AlertOctagon className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <span className="whitespace-pre-wrap">{item.text}</span>
        </div>
      );
    case "approval":
      return <ApprovalCard itemKey={item.key} p={item.payload} forge={forge} />;
    case "question":
      return <QuestionCard itemKey={item.key} p={item.payload} forge={forge} />;
    case "action":
      return <ActionCard itemKey={item.key} p={item.payload} forge={forge} />;
  }
}

function Notice({ kind, text, image, slides }: { kind: string; text: string; image?: string; slides?: SlideSet }) {
  if (kind === "command_output") return <Code text={text} />;
  if (kind === "slides_ready" && slides) return <SlideStrip set={slides} />;
  const tone = kind === "stuck" || kind === "injection" ? "warn" : "info";
  return (
    <div className="space-y-2">
      <div className={cx("flex gap-2 rounded-md px-3 py-1.5 text-[12.5px]", tone === "warn" ? "bg-warn-soft text-warn" : "text-fg-muted")}>
        <Info className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="whitespace-pre-wrap break-words">{text}</span>
      </div>
      {image && <ImageThumb path={image} />}
    </div>
  );
}

// The picture DebCraft is looking at, shown in the chat so the user sees the work too; click to enlarge, Esc to close.
function ImageThumb({ path }: { path: string }) {
  const [open, setOpen] = useState(false);
  const [broken, setBroken] = useState(false);
  const url = `/api/image?path=${encodeURIComponent(path)}`;
  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);
  if (broken) return null;
  return (
    <>
      <button
        type="button"
        data-testid="chat-image"
        onClick={() => setOpen(true)}
        title="Click to enlarge"
        className="block w-full max-w-sm overflow-hidden rounded-xl border border-border bg-surface shadow-sm transition hover:shadow-md"
      >
        <img src={url} alt="What DebCraft is looking at" onError={() => setBroken(true)} className="max-h-72 w-full object-cover object-top" />
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Enlarged picture"
          data-testid="chat-image-large"
          onClick={() => setOpen(false)}
          className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-6"
        >
          <img src={url} alt="What DebCraft is looking at, enlarged" className="max-h-full max-w-full rounded-lg bg-white object-contain shadow-2xl" />
        </div>
      )}
    </>
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

function ApprovalCard({ itemKey, p, forge }: { itemKey: string; p: P; forge: Forge }) {
  const [text, setText] = useState("");
  const answered = forge.timeline.answered[itemKey];
  const reply = (input: UserInput, label: string) => forge.answer(itemKey, input, label);
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
      <Textarea rows={2} value={text} onChange={(e) => setText(e.target.value)} placeholder="If you deny: tell DebCraft what to do instead (optional)" />
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

function QuestionCard({ itemKey, p, forge }: { itemKey: string; p: P; forge: Forge }) {
  const answered = forge.timeline.answered[itemKey];
  const { popupId, reopen } = useContext(QuestionPopup);
  const icon = <HelpCircle className="h-4 w-4" />;
  const given = forge.timeline.questionAnswers[p.id];
  if (answered !== undefined && given !== undefined) return <AnsweredQuestion p={p} given={given} />;
  if (answered === undefined && popupId === itemKey) {
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
          <QuestionForm itemKey={itemKey} p={p} forge={forge} />
          <button type="button" onClick={() => reopen(itemKey)} className="cursor-pointer text-[12px] font-semibold text-accent hover:underline">
            Show as a pop-up
          </button>
        </>
      )}
    </AskCard>
  );
}

// A settled question (D-232): the question, every option, and the one the user picked (plus their note or own
// answer), folded away with the chevron. Built from the question_answered event, so it also shows after a reopen.
function AnsweredQuestion({ p, given }: { p: P; given: { choice: string | null; text: string | null } }) {
  const [open, setOpen] = useState(true);
  const options: P[] = p.options || [];
  const own = given.choice === null ? given.text : null;
  return (
    <div data-card="question" data-answered="" className="rounded-xl border border-border bg-surface p-4">
      <button type="button" aria-expanded={open} onClick={() => setOpen(!open)} className="flex w-full cursor-pointer items-center gap-2 text-left">
        <HelpCircle className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />
        <span className="font-semibold">Question</span>
        <span className="text-[12.5px] text-fg-muted">Answered · 1 question</span>
        <ChevronDown className={cx("ml-auto h-4 w-4 shrink-0 text-fg-muted transition-transform duration-150", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div className="mt-3 space-y-3">
          <h4 className="break-words font-semibold">{p.question}</h4>
          {p.context && <Markdown text={p.context} className="text-fg-muted" />}
          <ul className="space-y-2">
            {options.map((option) => {
              const chosen = given.choice === option.label;
              return (
                <li key={option.label} data-chosen={chosen ? "" : undefined} className={cx("flex gap-3 rounded-lg border p-3", chosen ? "border-accent bg-accent-soft" : "border-border opacity-60")}>
                  <span className={cx("mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border", chosen ? "border-accent bg-accent text-accent-fg" : "border-border-strong")}>
                    {chosen && <Check className="h-3 w-3" aria-hidden />}
                  </span>
                  <span className="min-w-0 flex-1">
                    <span className="block font-medium">{option.label}</span>
                    {option.description && <span className="mt-0.5 block text-[12.5px] text-fg-muted">{option.description}</span>}
                    {chosen && option.image && (
                      <img src={`/api/image?path=${encodeURIComponent(option.image)}`} alt={`Picture of ${option.label}`} loading="lazy" className="mt-2 block max-h-40 rounded-md border border-border object-contain object-left" />
                    )}
                    {chosen && given.text && <span className="mt-1 block text-[12.5px]">Your note: {given.text}</span>}
                  </span>
                </li>
              );
            })}
            {own && (
              <li data-chosen="" className="flex gap-3 rounded-lg border border-accent bg-accent-soft p-3">
                <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full border border-accent bg-accent text-accent-fg">
                  <Check className="h-3 w-3" aria-hidden />
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block font-medium">Other</span>
                  <span className="mt-0.5 block whitespace-pre-wrap break-words text-[12.5px]">{own}</span>
                </span>
              </li>
            )}
          </ul>
        </div>
      )}
    </div>
  );
}

function ActionCard({ itemKey, p, forge }: { itemKey: string; p: P; forge: Forge }) {
  const [note, setNote] = useState("");
  const answered = forge.timeline.answered[itemKey];
  const choose = (choice: string, label: string) =>
    forge.answer(itemKey, { kind: "answer", question_id: p.id, choice, text: note.trim() || null }, label);
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
          DebCraft will check with <code className="rounded bg-muted px-1 font-mono">{p.verify_command}</code>
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


// The timeline rows between your message and Forge's reply (D-151/D-189): narration, tool calls, edits as inline
// diffs, and runs of read/search calls folded into one line. A call is one quiet line; opening it shows what
// went in and what came out. Failed calls and edits open by themselves.
import { AlertOctagon, CheckCircle2, ChevronRight, XCircle } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Code, cx } from "../lib";
import type { ChatItem } from "../types";
import { AgentSteps, agentCounts, latestStepText, roleLabel } from "./AgentSteps";
import { Badge, Spinner } from "./ui";

export type ToolItem = Extract<ChatItem, { kind: "tool" }>;
const OUT_COLLAPSED_LINES = 15;

/** Calls that only look: a run of two or more is shown as one folded line. */
const LOOKING_TOOLS = new Set(["read_file", "glob", "list_dir", "grep"]);

export type Row = { kind: "single"; item: ChatItem } | { kind: "looking"; items: ToolItem[] };

export function groupLookingRuns(items: ChatItem[]): Row[] {
  const rows: Row[] = [];
  let run: ToolItem[] = [];
  const flush = () => {
    if (run.length >= 2) rows.push({ kind: "looking", items: run });
    else run.forEach((item) => rows.push({ kind: "single", item }));
    run = [];
  };
  for (const item of items) {
    if (item.kind === "tool" && !item.agent && LOOKING_TOOLS.has(item.name)) {
      run.push(item);
      continue;
    }
    flush();
    rows.push({ kind: "single", item });
  }
  flush();
  return rows;
}

function lookingSummary(items: ToolItem[]): string {
  const count = (names: string[]) => items.filter((i) => names.includes(i.name)).length;
  const parts: string[] = [];
  const reads = count(["read_file"]);
  const searches = count(["grep", "glob"]);
  const lists = count(["list_dir"]);
  if (reads) parts.push(`Read ${reads} file${reads === 1 ? "" : "s"}`);
  if (searches) parts.push(`Searched ${searches} time${searches === 1 ? "" : "s"}`);
  if (lists) parts.push(`Listed ${lists} folder${lists === 1 ? "" : "s"}`);
  return parts.join(", ");
}

/** The IN block: the command when there is one, else the arguments one per line. */
function inputText(item: ToolItem): string {
  const args = item.args;
  if (!args || Object.keys(args).length === 0) return item.summary;
  if (typeof args.command === "string") return args.command;
  return Object.entries(args)
    .map(([key, value]) => `${key}: ${typeof value === "string" ? value : JSON.stringify(value)}`)
    .join("\n");
}

function IoBlock({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <div className="mb-1 font-mono text-[10.5px] font-semibold uppercase tracking-wider text-fg-muted">{label}</div>
      {children}
    </div>
  );
}

function StatusIcon({ item, retried }: { item: ToolItem; retried: boolean }) {
  if (item.state === "running") return <Spinner className="h-3.5 w-3.5 text-accent" />;
  if (item.state === "ok") return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-ok" aria-label="Succeeded" />;
  if (retried) return <AlertOctagon className="h-3.5 w-3.5 shrink-0" aria-label="Failed, then retried successfully" />;
  return <XCircle className="h-3.5 w-3.5 shrink-0 text-danger" aria-label="Failed" />;
}

/** What Forge said between calls (the model's reasoning summaries): dim, in order. */
export function ThinkingLine({ text }: { text: string }) {
  return <p className="whitespace-pre-wrap break-words px-2 text-[13px] italic leading-[1.5] text-fg-muted">{text}</p>;
}

function diffCounts(diff: string): { added: number; removed: number } {
  let added = 0;
  let removed = 0;
  for (const line of diff.split("\n")) {
    if (line.startsWith("+") && !line.startsWith("+++")) added++;
    else if (line.startsWith("-") && !line.startsWith("---")) removed++;
  }
  return { added, removed };
}

/** A unified diff: added lines green, removed lines red, hunk markers dim. The file name is on the row. */
export function DiffView({ diff }: { diff: string }) {
  const lines = diff.split("\n").filter((line) => !line.startsWith("--- ") && !line.startsWith("+++ ") && line !== "");
  return (
    <div role="region" aria-label="Changes" className="max-h-96 overflow-auto rounded-lg border border-border bg-surface py-1 font-mono text-[12px] leading-[1.55]">
      {lines.map((line, index) => (
        <div
          key={index}
          className={cx(
            "whitespace-pre px-3",
            line.startsWith("+") && "bg-ok-soft",
            line.startsWith("-") && "bg-danger-soft",
            line.startsWith("@@") && "text-fg-muted",
          )}
        >
          {line}
        </div>
      ))}
    </div>
  );
}

// A tool call is one quiet line; opening it shows what went in and what came out, long output folded.
export function ToolCard({ item }: { item: ToolItem }) {
  const retried = item.state === "fail" && Boolean(item.retried);
  const failed = item.state === "fail" && !retried;
  const [open, setOpen] = useState(Boolean(item.diff));
  const [showAll, setShowAll] = useState(false);
  // A failure shows what went wrong without a click (once, when it fails; the user can still close it).
  useEffect(() => {
    if (failed) setOpen(true);
  }, [failed]);
  useEffect(() => {
    if (item.diff) setOpen(true);
  }, [Boolean(item.diff)]); // eslint-disable-line react-hooks/exhaustive-deps
  const lines = item.preview ? item.preview.split("\n") : [];
  const folded = !showAll && lines.length > OUT_COLLAPSED_LINES;
  const counts = item.diff ? diffCounts(item.diff) : null;
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={cx(
          "flex w-full cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] text-fg-muted transition-colors duration-150 hover:bg-surface",
          retried && "opacity-70",
        )}
      >
        <ChevronRight className={cx("h-3.5 w-3.5 shrink-0 transition-transform duration-150", open && "rotate-90")} aria-hidden />
        {item.agent ? (
          <>
            <Badge tone="info">{roleLabel(item.agent.role)}</Badge>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-fg">{item.agent.purpose || item.summary}</span>
              <span className="block truncate text-[12px]">
                {item.state === "running" ? `${agentCounts(item.agent)} · ${latestStepText(item.agent)}` : agentCounts(item.agent)}
              </span>
            </span>
          </>
        ) : (
          <>
            <span className="shrink-0 font-mono text-[12.5px] font-semibold text-fg">{item.name}</span>
            <span className="min-w-0 flex-1 truncate">{item.summary}</span>
          </>
        )}
        {counts && (
          <span className="shrink-0 font-mono text-[11.5px] tabular-nums">
            <span className="text-ok">+{counts.added}</span> <span className="text-danger">−{counts.removed}</span>
          </span>
        )}
        {retried && <Badge tone="neutral">retried</Badge>}
        <StatusIcon item={item} retried={retried} />
        {item.duration !== undefined && <span className="shrink-0 font-mono text-[11.5px] tabular-nums">{item.duration}s</span>}
      </button>
      {open && (
        <div className="mb-1 ml-3.5 mt-1 space-y-3 border-l-2 border-border pl-4">
          {item.agent && <AgentSteps agent={item.agent} />}
          {item.diff ? (
            <DiffView diff={item.diff} />
          ) : (
            <IoBlock label="In">
              <Code text={inputText(item)} className="max-h-60 text-[12px]" />
            </IoBlock>
          )}
          {item.preview && (
            <IoBlock label="Out">
              <Code text={folded ? lines.slice(0, OUT_COLLAPSED_LINES).join("\n") : item.preview} className="max-h-96 text-[12px]" />
              {lines.length > OUT_COLLAPSED_LINES && (
                <button
                  type="button"
                  onClick={() => setShowAll((v) => !v)}
                  className="mt-1 cursor-pointer text-[12px] font-semibold text-accent hover:underline"
                >
                  {folded ? `Show ${lines.length - OUT_COLLAPSED_LINES} more lines` : "Show less"}
                </button>
              )}
            </IoBlock>
          )}
        </div>
      )}
    </div>
  );
}

/** Two or more read/search calls in a row: one folded line, "Read 3 files, Searched 2 times". */
export function LookingGroup({ items }: { items: ToolItem[] }) {
  const running = items.some((i) => i.state === "running");
  const failed = items.some((i) => i.state === "fail" && !i.retried);
  const [open, setOpen] = useState(false);
  return (
    <div>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2 py-1.5 text-left text-[13px] text-fg-muted transition-colors duration-150 hover:bg-surface"
      >
        <ChevronRight className={cx("h-3.5 w-3.5 shrink-0 transition-transform duration-150", open && "rotate-90")} aria-hidden />
        <span className="min-w-0 flex-1 truncate">{lookingSummary(items)}</span>
        {running ? (
          <Spinner className="h-3.5 w-3.5 text-accent" />
        ) : failed ? (
          <XCircle className="h-3.5 w-3.5 shrink-0 text-danger" aria-label="Some failed" />
        ) : (
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-ok" aria-label="Succeeded" />
        )}
      </button>
      {open && (
        <div className="ml-3.5 mt-1 space-y-0.5 border-l-2 border-border pl-3">
          {items.map((item) => (
            <ToolCard key={item.key} item={item} />
          ))}
        </div>
      )}
    </div>
  );
}

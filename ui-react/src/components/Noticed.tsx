import { ChevronRight } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Markdown, cx } from "../lib";
import type { NoticedRisk } from "../types";

const HEADING = /^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*noticed,? (?:but )?not changed\s*:?\s*(?:\*\*|__)?\s*:?\s*$/i;
const LIST_LINE = /^\s*(?:[-*+•]|\d+[.)])\s+/;

/** Cuts a "Noticed, not changed" list (heading plus the list right under it) out of a reply. */
export function splitNoticed(text: string): { before: string; noticed: string; after: string } {
  const lines = text.split("\n");
  const none = { before: text, noticed: "", after: "" };
  let start = -1;
  let fenced = false;
  lines.forEach((line, index) => {
    if (/^\s*(```|~~~)/.test(line)) fenced = !fenced;
    else if (!fenced && HEADING.test(line)) start = index;
  });
  if (start < 0) return none;
  let end = start + 1;
  let items = 0;
  for (; end < lines.length; end++) {
    const line = lines[end];
    if (LIST_LINE.test(line)) items++;
    else if (line.trim() && !(items && (/^\s+/.test(line) || lines[end - 1].trim()))) break; // a wrapped line belongs to its item
  }
  if (!items) return none;
  return {
    before: lines.slice(0, start).join("\n").trim(),
    noticed: lines.slice(start + 1, end).join("\n").trim(),
    after: lines.slice(end).join("\n").trim(),
  };
}

function Fold({ count, detail, warn, children }: { count: number; detail?: string; warn?: boolean; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div data-testid="noticed" className="my-2">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className={cx("flex items-center gap-1.5 rounded-md px-2 py-1 text-left text-[12.5px] transition hover:bg-raised", warn ? "text-warn" : "text-fg-muted")}
      >
        <ChevronRight className={cx("h-3.5 w-3.5 shrink-0 transition-transform", open && "rotate-90")} aria-hidden />
        <span>
          <span className="font-medium">Noticed, not changed · {count}</span>
          {detail && <span> ({detail})</span>}
        </span>
      </button>
      {open && <div className="mt-1 pl-5 text-[13px] leading-[1.55]">{children}</div>}
    </div>
  );
}

/** The list the model wrote in its reply, folded. */
export function NoticedSection({ text }: { text: string }) {
  const top = text.split("\n").filter((line) => LIST_LINE.test(line) && !/^\s{2,}/.test(line)).length;
  return (
    <Fold count={top || 1} warn={/secret|password|credential/i.test(text)}>
      <Markdown text={text} />
    </Fold>
  );
}

/** The list DebCraft made from its own scan, folded, with the kinds in the closed row. */
export function NoticedRisks({ risks }: { risks: NoticedRisk[] }) {
  const counts = new Map<string, number>();
  risks.forEach((risk) => counts.set(risk.kind, (counts.get(risk.kind) ?? 0) + 1));
  const detail = [...counts].map(([kind, count]) => `${count} ${kind}`).join(", ");
  const text = risks.map((risk) => `- \`${risk.path}:${risk.line}\`: ${risk.kind}: ${risk.what}. Suggestion: ${risk.advice}.`).join("\n");
  return (
    <Fold count={risks.length} detail={detail} warn={counts.has("hard-coded secret")}>
      <Markdown text={text} />
    </Fold>
  );
}

// The message box, Claude Code style: Enter sends, Shift+Enter new line, "/" commands and "@" files with
// suggestions, Up/Down recalls earlier messages, Shift+Tab cycles the permission mode, Esc stops; files and
// images can be attached with the paperclip, pasted (Ctrl+V a screenshot) or dropped on the chat.
import { ArrowUp, CircleStop, FileImage, FileText, FileType, Paperclip, X } from "lucide-react";
import { useEffect, useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { api, cx, DRAFT_EVENT, storageGet, storageSet, uploadFile, type Attachment } from "../lib";
import type { Forge } from "../useForge";
import { ActivityLine, RunTotals } from "./Activity";
import { Badge, Button, IconButton, Spinner } from "./ui";

const SLASH = [
  "/help", "/model", "/cost", "/clear", "/context", "/compact", "/checkpoints", "/undo", "/rewind", "/export", "/mode",
  "/requirements", "/plan", "/tasks", "/db", "/db requests",
  "/db done", "/db cant", "/db cleanup", "/diagnose", "/remember", "/memory", "/profile", "/assumptions", "/contract",
  "/revision", "/forget-snippet", "/contracts", "/handoff", "/effort", "/style",
  "/skills", "/allow-read", "/revoke-read", "/agents", "/bg", "/log", "/diff", "/rename", "/export-chat", "/mcp", "/init",
];
const MODES = ["default", "auto", "plan"] as const;
const MODE_HELP: Record<string, string> = {
  default: "asks before commands that change things",
  auto: "runs ordinary commands without asking (never the always-ask list)",
  plan: "read-only: Forge only looks and plans",
};
const HISTORY_LIMIT = 50;

interface Suggestion {
  kind: "command" | "file";
  value: string;
}

export function useAttachments() {
  const [items, setItems] = useState<Attachment[]>([]);
  const [uploading, setUploading] = useState(0);
  const [error, setError] = useState("");
  const add = async (files: FileList | File[]) => {
    setError("");
    for (const file of Array.from(files)) {
      setUploading((n) => n + 1);
      try {
        const stored = await uploadFile(file);
        setItems((list) => [...list, stored]);
      } catch (failure) {
        setError((failure as Error).message);
      } finally {
        setUploading((n) => n - 1);
      }
    }
  };
  return { items, uploading, error, add, remove: (path: string) => setItems((l) => l.filter((a) => a.path !== path)), clear: () => setItems([]) };
}

export type Attachments = ReturnType<typeof useAttachments>;

export function Composer({ forge, attachments }: { forge: Forge; attachments: Attachments }) {
  const [text, setText] = useState("");
  const [caret, setCaret] = useState(0);
  const [active, setActive] = useState(0);
  const [files, setFiles] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState<number | null>(null);
  const area = useRef<HTMLTextAreaElement>(null);
  const picker = useRef<HTMLInputElement>(null);
  const busy = Boolean(forge.state.busy);
  const workspace = forge.state.workspace?.path ?? "";
  const historyKey = `forge-history-${workspace}`;
  const mode = forge.state.mode ?? "default";

  // A starter chip on the welcome screen puts its text in the box (the user still reviews and sends it).
  useEffect(() => {
    const fill = (event: Event) => {
      setText(String((event as CustomEvent).detail ?? ""));
      area.current?.focus();
    };
    window.addEventListener(DRAFT_EVENT, fill);
    return () => window.removeEventListener(DRAFT_EVENT, fill);
  }, []);

  // The "@word" being typed right before the caret, if any.
  const mention = useMemo(() => {
    const match = /(^|\s)@([\w./\\-]*)$/.exec(text.slice(0, caret));
    return match ? match[2] : null;
  }, [text, caret]);

  useEffect(() => {
    if (mention === null || !workspace) return setFiles([]);
    const timer = window.setTimeout(() => {
      api<string[]>(`/api/files?q=${encodeURIComponent(mention)}`).then(setFiles).catch(() => setFiles([]));
    }, 120);
    return () => window.clearTimeout(timer);
  }, [mention, workspace]);

  const suggestions: Suggestion[] = useMemo(() => {
    if (mention !== null) return files.slice(0, 8).map((value) => ({ kind: "file", value }));
    if (!text.startsWith("/") || text.includes("\n")) return [];
    const head = text.split(" ")[0];
    if (SLASH.includes(text.trim())) return [];
    return SLASH.filter((c) => c.startsWith(head)).slice(0, 8).map((value) => ({ kind: "command", value }));
  }, [text, mention, files]);

  useEffect(() => setActive(0), [suggestions.length]);

  useLayoutEffect(() => {
    const box = area.current;
    if (!box) return;
    box.style.height = "auto";
    box.style.height = `${Math.min(box.scrollHeight, 240)}px`;
  }, [text]);

  useEffect(() => {
    const onEscape = (event: globalThis.KeyboardEvent) => {
      if (event.key === "Escape" && forge.state.workspace && busy) forge.send({ kind: "interrupt" });
    };
    document.addEventListener("keydown", onEscape);
    return () => document.removeEventListener("keydown", onEscape);
  }, [forge, busy]);

  const history = (): string[] => {
    try {
      return JSON.parse(storageGet(historyKey) || "[]") as string[];
    } catch {
      return [];
    }
  };

  const accept = (suggestion: Suggestion) => {
    if (suggestion.kind === "command") {
      setText(`${suggestion.value} `);
    } else {
      const before = text.slice(0, caret).replace(/@([\w./\\-]*)$/, `@${suggestion.value} `);
      setText(before + text.slice(caret));
      setCaret(before.length);
    }
    area.current?.focus();
  };

  const submit = () => {
    const typed = text.trim();
    const mentions = attachments.items.map((a) => `@${a.path}`).join(" ");
    if (!typed && !mentions) return;
    if (typed.startsWith("/") && !mentions) {
      forge.command(typed);
    } else {
      forge.send({ kind: "send_message", text: mentions ? `${typed}\n\n${mentions}`.trim() : typed });
    }
    if (typed) storageSet(historyKey, JSON.stringify([typed, ...history().filter((h) => h !== typed)].slice(0, HISTORY_LIMIT)));
    setText("");
    setHistoryIndex(null);
    attachments.clear();
    if ("Notification" in window && Notification.permission === "default") void Notification.requestPermission();
  };

  const cycleMode = () => {
    const next = MODES[(MODES.indexOf(mode as (typeof MODES)[number]) + 1) % MODES.length];
    forge.send({ kind: "slash_command", text: `/mode ${next}` });
    window.setTimeout(() => void forge.reload(), 300);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Tab" && event.shiftKey) {
      event.preventDefault();
      cycleMode();
      return;
    }
    if (suggestions.length && (event.key === "ArrowDown" || event.key === "ArrowUp")) {
      event.preventDefault();
      setActive((i) => (i + (event.key === "ArrowDown" ? 1 : -1) + suggestions.length) % suggestions.length);
      return;
    }
    if (suggestions.length && (event.key === "Tab" || (event.key === "Enter" && mention !== null))) {
      event.preventDefault();
      accept(suggestions[active]);
      return;
    }
    const atStart = event.currentTarget.selectionStart === 0 && event.currentTarget.selectionEnd === 0;
    if (event.key === "ArrowUp" && (atStart || !text) && !suggestions.length) {
      const past = history();
      const index = historyIndex === null ? 0 : Math.min(historyIndex + 1, past.length - 1);
      if (past[index] !== undefined) {
        event.preventDefault();
        setHistoryIndex(index);
        setText(past[index]);
      }
      return;
    }
    if (event.key === "ArrowDown" && historyIndex !== null && !suggestions.length) {
      event.preventDefault();
      const index = historyIndex - 1;
      setHistoryIndex(index < 0 ? null : index);
      setText(index < 0 ? "" : history()[index] ?? "");
      return;
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      submit();
    }
  };

  const ready = !attachments.uploading && forge.controls;

  return (
    <div className="shrink-0 bg-bg px-6 pb-4 pt-2">
      <RunTotals forge={forge} />
      <ActivityLine forge={forge} />
      <div className="relative mx-auto max-w-[760px]">
        {suggestions.length > 0 && (
          <ul role="listbox" aria-label={mention !== null ? "Files" : "Commands"} className="absolute bottom-full mb-2 max-w-full min-w-72 overflow-hidden rounded-lg border border-border bg-surface py-1 shadow-lg">
            {suggestions.map((s, index) => (
              <li key={s.value} role="option" aria-selected={index === active}>
                <button
                  type="button"
                  onMouseDown={(e) => {
                    e.preventDefault();
                    accept(s);
                  }}
                  className={cx("flex w-full cursor-pointer items-center gap-2 px-3 py-1.5 text-left font-mono text-[12.5px]", index === active ? "bg-accent-soft text-accent" : "hover:bg-raised")}
                >
                  {s.kind === "file" && <FileText className="h-3.5 w-3.5 shrink-0" aria-hidden />}
                  <span className="truncate">{s.value}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="rounded-[26px] border border-border bg-surface px-3 py-2 transition-colors duration-150 focus-within:border-accent/70">
          {(attachments.items.length > 0 || attachments.uploading > 0) && (
            <div className="flex flex-wrap gap-1.5 px-1 pb-2">
              {attachments.items.map((a) => (
                <span key={a.path} className="inline-flex max-w-60 items-center gap-1.5 rounded-md border border-border bg-raised py-1 pl-2 pr-1 text-[12px]" title={a.path}>
                  {a.kind === "image" ? <FileImage className="h-3.5 w-3.5 shrink-0 text-info" /> : a.kind === "pdf" ? <FileType className="h-3.5 w-3.5 shrink-0 text-danger" /> : <FileText className="h-3.5 w-3.5 shrink-0 text-fg-muted" />}
                  <span className="truncate">{a.name}</span>
                  <IconButton label={`Remove ${a.name}`} className="h-5 w-5" onClick={() => attachments.remove(a.path)}>
                    <X className="h-3 w-3" />
                  </IconButton>
                </span>
              ))}
              {attachments.uploading > 0 && (
                <span className="inline-flex items-center gap-1.5 px-2 text-[12px] text-fg-muted">
                  <Spinner className="h-3.5 w-3.5" /> Uploading…
                </span>
              )}
            </div>
          )}
          <div className="flex items-end gap-2">
            <IconButton label="Attach files or images" onClick={() => picker.current?.click()} disabled={!forge.controls}>
              <Paperclip className="h-4 w-4" />
            </IconButton>
            <input
              ref={picker}
              type="file"
              multiple
              hidden
              onChange={(e) => {
                if (e.target.files?.length) void attachments.add(e.target.files);
                e.target.value = "";
              }}
            />
            <textarea
              ref={area}
              rows={1}
              value={text}
              onChange={(e) => {
                setText(e.target.value);
                setCaret(e.target.selectionStart);
              }}
              onSelect={(e) => setCaret(e.currentTarget.selectionStart)}
              onKeyDown={onKeyDown}
              onPaste={(e) => {
                const pasted = Array.from(e.clipboardData.files);
                if (pasted.length) {
                  e.preventDefault();
                  void attachments.add(pasted);
                }
              }}
              disabled={!forge.controls}
              placeholder="Message Forge. / for commands, @ for files"
              aria-label="Message"
              className="max-h-60 min-h-[40px] flex-1 resize-none appearance-none border-0 bg-transparent px-1 py-2 text-[14px] leading-relaxed text-fg placeholder:text-fg-muted/70 focus:outline-none focus:ring-0"
            />
            {busy ? (
              <Button variant="danger" onClick={() => forge.send({ kind: "interrupt" })} icon={<CircleStop className="h-4 w-4" />} aria-label="Stop (Esc)">
                Stop
              </Button>
            ) : (
              <Button
                variant="primary"
                className="h-9 w-9 shrink-0 !px-0"
                onClick={submit}
                disabled={!ready || (!text.trim() && !attachments.items.length)}
                icon={<ArrowUp className="h-4 w-4" />}
                aria-label="Send (Enter)"
                title="Send (Enter)"
              />
            )}
          </div>
        </div>
        {attachments.error && (
          <div role="alert" className="mt-1.5 px-1 text-[12px] text-danger">
            {attachments.error}
          </div>
        )}
        <div className="mt-1.5 flex items-center justify-between gap-3 px-1 text-[11.5px] text-fg-muted">
          <span>
            <kbd className="font-mono">Enter</kbd> sends · <kbd className="font-mono">Shift+Enter</kbd> new line · <kbd className="font-mono">/</kbd> commands ·{" "}
            <kbd className="font-mono">@</kbd> files · <kbd className="font-mono">↑</kbd> history · <kbd className="font-mono">Esc</kbd> stops
          </span>
          <button type="button" onClick={cycleMode} title={MODE_HELP[mode]} className="flex cursor-pointer items-center gap-1.5 rounded px-1 hover:text-fg">
            <Badge tone={mode === "auto" ? "warn" : mode === "plan" ? "info" : "neutral"}>{mode} mode</Badge>
            <kbd className="font-mono">Shift+Tab</kbd>
          </button>
        </div>
      </div>
    </div>
  );
}

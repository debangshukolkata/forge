// The conversations of the open project (D-582): the title in the top bar opens a list. Start a new one, open an
// earlier one, rename one. The files, notes and cost belong to the project; each conversation has its own chat and
// its own memory for the model. A switch while DebCraft works asks first (the server answers "busy").
import { Check, ChevronDown, MessageSquare, Pencil, Plus } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { ApiError, api, cx } from "../lib";
import type { Forge } from "../useForge";
import { Button } from "./ui";

interface ConversationRow {
  id: string;
  title: string;
  updated: string;
  active: boolean;
  running: boolean;
}

export function ago(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (!Number.isFinite(seconds)) return "";
  if (seconds < 90) return "now";
  if (seconds < 3600) return `${Math.round(seconds / 60)} min`;
  if (seconds < 86400) return `${Math.round(seconds / 3600)} h`;
  return `${Math.round(seconds / 86400)} d`;
}

export function ConversationSwitcher({ forge }: { forge: Forge }) {
  const [open, setOpen] = useState(false);
  const [rows, setRows] = useState<ConversationRow[]>([]);
  const [renaming, setRenaming] = useState<string | null>(null);
  const [draft, setDraft] = useState("");
  const [switching, setSwitching] = useState(false);
  const [error, setError] = useState("");
  const [asking, setAsking] = useState<{ id: string | null } | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const current = forge.state.workspace?.conversation;

  async function load() {
    try {
      const listing = await api<{ conversations: ConversationRow[] }>("/api/conversations");
      setRows([...listing.conversations].reverse());
    } catch {
      setRows([]);
    }
  }

  useEffect(() => {
    if (!open) return;
    void load();
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        if (renaming) setRenaming(null);
        else if (asking) setAsking(null);
        else setOpen(false);
      }
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape, true);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape, true);
    };
  }, [open, renaming, asking]);

  async function switchTo(id: string | null, stopRunning = false) {
    setSwitching(true);
    setError("");
    try {
      await api(id === null ? "/api/conversations" : "/api/conversations/open", {
        method: "POST",
        body: id === null ? { title: "", stop_running: stopRunning } : { id, stop_running: stopRunning },
      });
      setAsking(null);
      setOpen(false);
      await forge.enter(); // the project was opened again on the other conversation: read it and replay its events
    } catch (failure) {
      if (failure instanceof ApiError && failure.status === 409 && failure.data.busy) setAsking({ id });
      else setError((failure as Error).message);
    } finally {
      setSwitching(false);
    }
  }

  async function rename(id: string) {
    try {
      await api("/api/conversations/rename", { method: "POST", body: { id, title: draft } });
      setRenaming(null);
      await load();
      await forge.reload();
    } catch (failure) {
      setError((failure as Error).message);
    }
  }

  return (
    <div ref={box} className="relative min-w-0">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Conversations"
        title="Conversations of this project"
        onClick={() => setOpen(!open)}
        className="flex min-w-0 cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 text-[13px] text-fg-muted transition-colors duration-150 hover:bg-raised hover:text-fg"
      >
        <MessageSquare className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="max-w-48 truncate">{current?.title || "New conversation"}</span>
        <ChevronDown className={cx("h-3.5 w-3.5 shrink-0 transition-transform duration-150", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div role="menu" aria-label="Conversations" className="absolute left-0 top-full z-40 mt-1 w-80 rounded-xl border border-border bg-surface p-1.5 shadow-xl">
          {asking ? (
            <div role="alertdialog" aria-label="Stop and switch" className="rounded-lg border border-warn/40 p-3">
              <p className="text-[13px] font-semibold">DebCraft is working in this conversation.</p>
              <p className="mt-1 text-[12px] text-fg-muted">Stop it and switch? What it has finished so far is kept.</p>
              <div className="mt-2 flex gap-2">
                <Button variant="primary" size="sm" disabled={switching} onClick={() => switchTo(asking.id, true)}>
                  {switching ? "Stopping…" : "Stop and switch"}
                </Button>
                <Button variant="ghost" size="sm" disabled={switching} onClick={() => setAsking(null)}>
                  Keep working
                </Button>
              </div>
            </div>
          ) : (
            <>
              <button
                type="button"
                role="menuitem"
                disabled={switching}
                onClick={() => switchTo(null)}
                className="flex w-full cursor-pointer items-center gap-2 rounded-lg px-2.5 py-2 text-[13px] font-medium text-accent transition-colors duration-150 hover:bg-raised disabled:opacity-60"
              >
                <Plus className="h-4 w-4" aria-hidden /> New conversation
              </button>
              <ul className="mt-1 max-h-72 overflow-y-auto border-t border-border pt-1">
                {rows.map((row) => (
                  <li key={row.id} className="group flex items-center rounded-lg hover:bg-raised">
                    {renaming === row.id ? (
                      <form
                        className="flex min-w-0 flex-1 items-center gap-1 px-2 py-1.5"
                        onSubmit={(event) => {
                          event.preventDefault();
                          void rename(row.id);
                        }}
                      >
                        <input
                          autoFocus
                          aria-label="Conversation name"
                          value={draft}
                          maxLength={60}
                          onChange={(event) => setDraft(event.target.value)}
                          className="min-w-0 flex-1 rounded-md border border-border bg-surface px-2 py-1 text-[13px]"
                        />
                        <button type="submit" aria-label="Save name" className="cursor-pointer rounded-md p-1 text-accent hover:bg-muted">
                          <Check className="h-4 w-4" aria-hidden />
                        </button>
                      </form>
                    ) : (
                      <>
                        <button
                          type="button"
                          role="menuitem"
                          disabled={switching}
                          onClick={() => (row.active ? setOpen(false) : void switchTo(row.id))}
                          className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 px-2.5 py-2 text-left"
                        >
                          {row.running ? (
                            <span className="h-2 w-2 shrink-0 rounded-full bg-accent" role="img" aria-label="Running" />
                          ) : (
                            <span className="h-2 w-2 shrink-0" aria-hidden />
                          )}
                          <span className="min-w-0 flex-1 truncate text-[13px] font-medium">{row.title || "New conversation"}</span>
                          <span className="shrink-0 text-[11.5px] text-fg-muted">{row.active ? "open" : ago(row.updated)}</span>
                        </button>
                        <button
                          type="button"
                          aria-label={`Rename ${row.title || "conversation"}`}
                          title="Rename"
                          onClick={() => {
                            setDraft(row.title);
                            setRenaming(row.id);
                          }}
                          className="mr-1 flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-fg-muted opacity-0 transition-opacity duration-150 hover:bg-muted hover:text-fg focus-visible:opacity-100 group-hover:opacity-100"
                        >
                          <Pencil className="h-3.5 w-3.5" aria-hidden />
                        </button>
                      </>
                    )}
                  </li>
                ))}
              </ul>
              {error && (
                <p role="alert" className="px-2.5 py-1.5 text-[12px] text-danger">
                  {error}
                </p>
              )}
            </>
          )}
        </div>
      )}
    </div>
  );
}

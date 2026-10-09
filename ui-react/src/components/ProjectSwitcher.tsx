// The project name in the top bar (D-234): click it to switch to another recent project, start a new one, or
// delete one. Replaces the permanent "Recent" pane on the left, which took space the chat needs.
import { Check, ChevronDown, FolderPlus, Layers, FolderGit2, Trash2 } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { api, cx } from "../lib";
import type { Forge } from "../useForge";
import { Button } from "./ui";

export function ProjectSwitcher({
  forge,
  onOpen,
  onNew,
  onDeleted,
}: {
  forge: Forge;
  onOpen: (path: string) => void;
  onNew: () => void;
  onDeleted: (path: string, wasCurrent: boolean) => void;
}) {
  const [open, setOpen] = useState(false);
  const [confirming, setConfirming] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const box = useRef<HTMLDivElement>(null);
  const workspace = forge.state.workspace;
  const recent = forge.state.recent || [];

  useEffect(() => {
    if (!open) return;
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape, true);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape, true);
    };
  }, [open]);

  async function remove(path: string) {
    setBusy(true);
    setError("");
    try {
      await api("/api/projects/delete", { method: "POST", body: { workspace: path } });
      setConfirming(null);
      setOpen(false);
      onDeleted(path, path === workspace?.path);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div ref={box} className="relative min-w-0">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        title={workspace?.path}
        onClick={() => setOpen(!open)}
        className="flex min-w-0 cursor-pointer items-center gap-1 rounded-md px-1.5 py-1 font-medium transition-colors duration-150 hover:bg-raised"
      >
        <span className="truncate">{workspace?.name}</span>
        <ChevronDown className={cx("h-3.5 w-3.5 shrink-0 text-fg-muted transition-transform duration-150", open && "rotate-180")} aria-hidden />
      </button>
      {open && (
        <div role="menu" aria-label="Projects" className="absolute left-0 top-full z-40 mt-1 w-80 rounded-xl border border-border bg-surface p-1.5 shadow-xl">
          <ul className="max-h-80 overflow-y-auto">
            {recent.map((entry) => {
              const current = entry.path === workspace?.path;
              const standalone = entry.repo.startsWith("standalone");
              return (
                <li key={entry.path}>
                  {confirming === entry.path ? (
                    <div role="alertdialog" aria-label={`Delete ${entry.name}`} className="rounded-lg border border-danger/40 p-3">
                      <p className="text-[13px] font-semibold">Delete “{entry.name}”?</p>
                      <p className="mt-1 break-all text-[12px] text-fg-muted">
                        Permanently deletes {entry.path} and everything in it. Your original repository is not touched.
                      </p>
                      {error && (
                        <p role="alert" className="mt-1 text-[12px] text-danger">
                          {error}
                        </p>
                      )}
                      <div className="mt-2 flex gap-2">
                        <Button variant="danger" size="sm" disabled={busy} onClick={() => remove(entry.path)}>
                          {busy ? "Deleting…" : "Delete project"}
                        </Button>
                        <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirming(null)}>
                          Cancel
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div className="group flex items-center rounded-lg hover:bg-raised">
                      <button
                        type="button"
                        role="menuitem"
                        title={entry.path}
                        onClick={() => {
                          setOpen(false);
                          if (!current) onOpen(entry.path);
                        }}
                        className="flex min-w-0 flex-1 cursor-pointer items-center gap-2.5 px-2.5 py-2 text-left"
                      >
                        {standalone ? <Layers className="h-4 w-4 shrink-0 text-info" aria-hidden /> : <FolderGit2 className="h-4 w-4 shrink-0 text-fg-muted" aria-hidden />}
                        <span className="min-w-0 flex-1">
                          <span className="block truncate text-[13px] font-medium">{entry.name}</span>
                          <span className="block truncate text-[11.5px] text-fg-muted">{standalone ? "Standalone" : entry.repo}</span>
                        </span>
                        {current && <Check className="h-4 w-4 shrink-0 text-accent" aria-label="Open now" />}
                      </button>
                      <button
                        type="button"
                        aria-label={`Delete ${entry.name}`}
                        title="Delete this project"
                        onClick={() => {
                          setError("");
                          setConfirming(entry.path);
                        }}
                        className="mr-1 flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-md text-fg-muted transition-colors duration-150 hover:bg-danger-soft hover:text-danger"
                      >
                        <Trash2 className="h-3.5 w-3.5" aria-hidden />
                      </button>
                    </div>
                  )}
                </li>
              );
            })}
          </ul>
          <button
            type="button"
            role="menuitem"
            onClick={() => {
              setOpen(false);
              onNew();
            }}
            className="mt-1 flex w-full cursor-pointer items-center gap-2 rounded-lg border-t border-border px-2.5 py-2 text-[13px] font-medium text-accent transition-colors duration-150 hover:bg-raised"
          >
            <FolderPlus className="h-4 w-4" aria-hidden /> New project
          </button>
        </div>
      )}
    </div>
  );
}

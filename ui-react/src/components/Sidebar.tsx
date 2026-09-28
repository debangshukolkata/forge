import { FolderGit2, FolderPlus, Layers } from "lucide-react";
import { cx } from "../lib";
import type { Forge } from "../useForge";

export function Sidebar({ forge, onNew, onOpen }: { forge: Forge; onNew: () => void; onOpen: (path: string) => void }) {
  const current = forge.state.workspace?.path;
  const recent = forge.state.recent || [];
  return (
    <nav aria-label="Projects" className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="p-3">
        <button
          type="button"
          onClick={onNew}
          className="flex h-9 w-full cursor-pointer items-center gap-2 rounded-md border border-dashed border-border-strong px-3 text-[13px] font-medium text-fg transition-colors duration-150 hover:border-accent hover:text-accent"
        >
          <FolderPlus className="h-4 w-4" aria-hidden /> New project
        </button>
      </div>
      <div className="px-4 pb-1 text-[11.5px] font-semibold uppercase tracking-wide text-fg-muted">Recent</div>
      <ul className="flex-1 overflow-y-auto px-2 pb-3">
        {recent.length === 0 && <li className="px-2 py-3 text-[12.5px] text-fg-muted">No projects yet.</li>}
        {recent.map((entry) => {
          const standalone = entry.repo.startsWith("standalone");
          const active = entry.path === current;
          return (
            <li key={entry.path}>
              <button
                type="button"
                title={entry.path}
                onClick={() => onOpen(entry.path)}
                className={cx(
                  "group flex w-full cursor-pointer items-start gap-2.5 rounded-md px-2 py-2 text-left transition-colors duration-150",
                  active ? "bg-accent-soft" : "hover:bg-raised",
                )}
              >
                {standalone ? (
                  <Layers className={cx("mt-0.5 h-4 w-4 shrink-0", active ? "text-accent" : "text-info")} aria-hidden />
                ) : (
                  <FolderGit2 className={cx("mt-0.5 h-4 w-4 shrink-0", active ? "text-accent" : "text-fg-muted")} aria-hidden />
                )}
                <span className="min-w-0">
                  <span className={cx("block truncate text-[13px] font-medium", active ? "text-accent" : "text-fg")}>{entry.name}</span>
                  <span className="block truncate text-[11.5px] text-fg-muted">{standalone ? "Standalone" : entry.repo}</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

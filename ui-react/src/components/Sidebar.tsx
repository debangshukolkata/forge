import { FolderGit2, FolderPlus, Layers, PanelLeftClose, PanelLeftOpen } from "lucide-react";
import { useState } from "react";
import { cx, storageGet, storageSet } from "../lib";
import type { Forge } from "../useForge";

export function Sidebar({ forge, onNew, onOpen }: { forge: Forge; onNew: () => void; onOpen: (path: string) => void }) {
  const current = forge.state.workspace?.path;
  const recent = forge.state.recent || [];
  const [collapsed, setCollapsed] = useState(storageGet("forge-sidebar-collapsed") === "1");
  const toggle = () => {
    setCollapsed(!collapsed);
    storageSet("forge-sidebar-collapsed", collapsed ? "0" : "1");
  };
  if (collapsed) {
    return (
      <nav aria-label="Projects" className="flex w-12 shrink-0 flex-col items-center gap-1 border-r border-border bg-surface py-3">
        <button type="button" aria-label="Show projects" title="Show projects" onClick={toggle} className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-md text-fg-muted transition-colors duration-150 hover:bg-raised hover:text-fg">
          <PanelLeftOpen className="h-4 w-4" aria-hidden />
        </button>
        <button type="button" aria-label="New project" title="New project" onClick={onNew} className="flex h-9 w-9 cursor-pointer items-center justify-center rounded-md text-fg-muted transition-colors duration-150 hover:bg-raised hover:text-accent">
          <FolderPlus className="h-4 w-4" aria-hidden />
        </button>
      </nav>
    );
  }
  return (
    <nav aria-label="Projects" className="flex w-60 shrink-0 flex-col border-r border-border bg-surface">
      <div className="flex items-center gap-1 p-3">
        <button
          type="button"
          aria-label="Hide projects"
          title="Hide projects"
          onClick={toggle}
          className="flex h-9 w-9 shrink-0 cursor-pointer items-center justify-center rounded-md text-fg-muted transition-colors duration-150 hover:bg-raised hover:text-fg"
        >
          <PanelLeftClose className="h-4 w-4" aria-hidden />
        </button>
        <button
          type="button"
          onClick={onNew}
          className="flex h-9 min-w-0 flex-1 cursor-pointer items-center gap-2 rounded-full border border-dashed border-border-strong px-3 text-[13px] font-medium text-fg transition-colors duration-150 hover:border-accent hover:text-accent"
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

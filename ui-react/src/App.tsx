import { MessagesSquare, Network, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Chat } from "./components/Chat";
import { RunMap } from "./components/RunMap";
import { Home } from "./components/Home";
import { Setup } from "./components/Setup";
import { IconButton, Spinner } from "./components/ui";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { api, cx, storageGet, storageSet } from "./lib";
import { Panels } from "./panels/Panels";
import type { SetupStatus } from "./types";
import { useForge } from "./useForge";

export function App() {
  const forge = useForge();
  const [view, setView] = useState<"home" | "chat">("home");
  // D-145/D-146: null while the one-time check is in flight (nothing renders yet, so there's no flash of
  // the setup screen when everything's already configured — the common case on every run after the first).
  const [missingSecrets, setMissingSecrets] = useState<string[] | null>(null);
  useEffect(() => {
    api<SetupStatus>("/api/setup")
      .then((status) => setMissingSecrets(status.missing))
      .catch(() => setMissingSecrets([])); // can't tell: don't block the app on a broken check
  }, []);
  // Light is the default (D-125). A new key, written only when the user toggles: the old "forge-theme" was
  // saved on every load, so it can't tell a real choice of dark from the old default.
  const [theme, setTheme] = useState<"dark" | "light">(storageGet("forge-theme-choice") === "dark" ? "dark" : "light");
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    storageSet("forge-theme-choice", next);
  };
  const [stopped, setStopped] = useState(false);
  const [surface, setSurface] = useState<Surface>("chat");
  const [panelsCollapsed, setPanelsCollapsed] = useState(storageGet("forge-panels-collapsed") === "1");
  const collapsePanels = (collapsed: boolean) => {
    setPanelsCollapsed(collapsed);
    storageSet("forge-panels-collapsed", collapsed ? "1" : "0");
  };

  // From the Run map to the chat: show the row of that event (or the last row before it) and flash it.
  const jump = useCallback((seq: number) => {
    setSurface("chat");
    window.setTimeout(() => {
      const rows = [...document.querySelectorAll<HTMLElement>("[data-seq]")];
      const row = rows.filter((r) => Number(r.dataset.seq) <= seq).pop() ?? rows[0];
      if (!row) return;
      row.scrollIntoView({ block: "center" });
      row.classList.remove("jump-flash");
      void row.offsetWidth; // restart the animation
      row.classList.add("jump-flash");
    }, 60);
  }, []);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  useEffect(() => {
    setView(forge.state.workspace ? "chat" : "home");
  }, [forge.state.workspace?.path]); // eslint-disable-line react-hooks/exhaustive-deps

  const open = async (path: string) => {
    try {
      await forge.openWorkspace(path);
      setView("chat");
    } catch (error) {
      alert((error as Error).message);
    }
  };

  const quit = async () => {
    if (!confirm("Stop Forge (the server and any running work)?")) return;
    await api("/api/quit", { method: "POST" }).catch(() => undefined);
    setStopped(true);
  };

  if (stopped) {
    return <div className="flex h-full items-center justify-center text-fg-muted">Forge has stopped. You can close this tab.</div>;
  }

  if (missingSecrets === null) {
    return (
      <div className="flex h-full items-center justify-center text-fg-muted">
        <Spinner />
      </div>
    );
  }

  if (missingSecrets.length > 0) {
    return <Setup missing={missingSecrets} onDone={() => setMissingSecrets([])} />;
  }

  return (
    <div className="flex h-full flex-col">
      <TopBar forge={forge} theme={theme} onToggleTheme={toggleTheme} onHome={() => setView("home")} onQuit={quit} />
      <div className="flex min-h-0 flex-1">
        <Sidebar forge={forge} onNew={() => setView("home")} onOpen={open} />
        <main className="flex min-w-0 flex-1 flex-col">
          {view === "home" || !forge.state.workspace ? (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <Home onCreated={async () => { await forge.enter(); setView("chat"); }} />
            </div>
          ) : (
            <>
              <ViewSwitch
                surface={surface}
                onChange={setSurface}
                panelsCollapsed={surface === "chat" ? panelsCollapsed : null}
                onTogglePanels={() => collapsePanels(!panelsCollapsed)}
              />
              {surface === "map" ? <RunMap forge={forge} onJump={jump} /> : <Chat forge={forge} />}
            </>
          )}
        </main>
        {view === "chat" && surface === "chat" && forge.state.workspace && (
          <Panels forge={forge} collapsed={panelsCollapsed} onExpand={() => collapsePanels(false)} />
        )}
      </div>
    </div>
  );
}

type Surface = "chat" | "map";

function ViewSwitch({
  surface,
  onChange,
  panelsCollapsed,
  onTogglePanels,
}: {
  surface: Surface;
  onChange: (surface: Surface) => void;
  panelsCollapsed: boolean | null; // null: no side panel in this view
  onTogglePanels: () => void;
}) {
  const tab = (value: Surface, icon: ReactNode, label: string) => (
    <button
      type="button"
      role="tab"
      aria-selected={surface === value}
      onClick={() => onChange(value)}
      className={cx(
        "inline-flex h-7 cursor-pointer items-center gap-1.5 rounded-md px-3 text-[12.5px] font-medium transition-colors duration-150",
        surface === value ? "bg-surface text-fg shadow-sm" : "text-fg-muted hover:text-fg",
      )}
    >
      {icon}
      {label}
    </button>
  );
  return (
    <div className="flex items-center border-b border-border px-4 py-1.5">
      <div role="tablist" aria-label="View" className="inline-flex gap-0.5 rounded-lg bg-raised p-0.5">
        {tab("chat", <MessagesSquare className="h-3.5 w-3.5" aria-hidden />, "Chat")}
        {tab("map", <Network className="h-3.5 w-3.5" aria-hidden />, "Run map")}
      </div>
      {panelsCollapsed !== null && (
        <IconButton
          label={panelsCollapsed ? "Show the side panel" : "Hide the side panel"}
          aria-expanded={!panelsCollapsed}
          onClick={onTogglePanels}
          className="ml-auto"
        >
          {panelsCollapsed ? <PanelRightOpen className="h-4 w-4" /> : <PanelRightClose className="h-4 w-4" />}
        </IconButton>
      )}
    </div>
  );
}

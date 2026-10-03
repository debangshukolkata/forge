import { MessagesSquare, Network, PanelRightClose, PanelRightOpen } from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Chat } from "./components/Chat";
import { RunMap } from "./components/RunMap";
import { EnvironmentDrawer } from "./components/Environment";
import { Hub } from "./components/Hub";
import { Login } from "./components/Login";
import { NewProject } from "./components/NewProject";
import { ProjectList } from "./components/ProjectList";
import { Setup } from "./components/Setup";
import { IconButton, Spinner } from "./components/ui";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { api, cx, SIGNED_OUT_EVENT, storageGet, storageSet } from "./lib";
import { Panels } from "./panels/Panels";
import type { AuthStatus, SetupStatus } from "./types";
import { useForge } from "./useForge";

type Theme = "dark" | "light";
type View = "hub" | "new" | "open" | "chat";

// Login first (D-184); the engine session and everything else only start once signed in.
export function App() {
  // Light is the default (D-125). A new key, written only when the user toggles: the old "forge-theme" was
  // saved on every load, so it can't tell a real choice of dark from the old default.
  const [theme, setTheme] = useState<Theme>(storageGet("forge-theme-choice") === "dark" ? "dark" : "light");
  const toggleTheme = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    storageSet("forge-theme-choice", next);
  };
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
  }, [theme]);

  const [auth, setAuth] = useState<AuthStatus | null>(null);
  useEffect(() => {
    api<AuthStatus>("/api/auth").then(setAuth).catch(() => setAuth({ configured: true, signed_in: false, user: null }));
    const back = () => setAuth((prev) => ({ configured: prev?.configured ?? true, signed_in: false, user: null }));
    window.addEventListener(SIGNED_OUT_EVENT, back);
    return () => window.removeEventListener(SIGNED_OUT_EVENT, back);
  }, []);
  const signOut = async () => {
    await api("/api/auth/logout", { method: "POST" }).catch(() => undefined);
    setAuth({ configured: true, signed_in: false, user: null });
  };

  if (auth === null) {
    return (
      <div className="flex h-full items-center justify-center text-fg-muted">
        <Spinner />
      </div>
    );
  }
  if (!auth.signed_in) {
    return <Login configured={auth.configured} onSignedIn={(user) => setAuth({ configured: true, signed_in: true, user })} />;
  }
  return <Shell user={auth.user} theme={theme} onToggleTheme={toggleTheme} onSignOut={signOut} />;
}

function Shell({ user, theme, onToggleTheme, onSignOut }: { user: string | null; theme: Theme; onToggleTheme: () => void; onSignOut: () => void }) {
  const forge = useForge();
  const [view, setView] = useState<View>("hub");
  // D-145/D-146: null while the one-time check is in flight (nothing renders yet, so there's no flash of
  // the setup screen when everything's already configured — the common case on every run after the first).
  const [missingSecrets, setMissingSecrets] = useState<string[] | null>(null);
  useEffect(() => {
    api<SetupStatus>("/api/setup")
      .then((status) => setMissingSecrets(status.missing))
      .catch(() => setMissingSecrets([])); // can't tell: don't block the app on a broken check
  }, []);
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

  // The environment drawer (D-186): opens by itself on the New project screen, and from the top bar anywhere.
  const [envOpen, setEnvOpen] = useState(false);
  const showView = (next: View) => {
    setView(next);
    if (next === "new") setEnvOpen(true);
  };

  useEffect(() => {
    setView(forge.state.workspace ? "chat" : "hub");
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

  const landing = view !== "chat" || !forge.state.workspace;

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
      <TopBar forge={forge} theme={theme} onToggleTheme={onToggleTheme} onHome={() => setView("hub")} onQuit={quit} user={user} onSignOut={onSignOut} onEnvironment={() => setEnvOpen((open) => !open)} />
      <div className="flex min-h-0 flex-1">
        {!landing && <Sidebar forge={forge} onNew={() => showView("new")} onOpen={open} />}
        <main className="flex min-w-0 flex-1 flex-col">
          {landing ? (
            <div className="min-h-0 flex-1 overflow-y-auto bg-bg">
              {view === "new" ? (
                <NewProject onBack={() => setView("hub")} onOpenEnvironment={() => setEnvOpen(true)} onCreated={async () => { setEnvOpen(false); await forge.enter(); setView("chat"); }} />
              ) : view === "open" ? (
                <ProjectList onBack={() => setView("hub")} onOpen={open} />
              ) : (
                <Hub user={user} projectCount={forge.state.recent?.length ?? 0} onNew={() => showView("new")} onOpen={() => setView("open")} />
              )}
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
        {envOpen && <EnvironmentDrawer onClose={() => setEnvOpen(false)} />}
        {!envOpen && view === "chat" && surface === "chat" && forge.state.workspace && (
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

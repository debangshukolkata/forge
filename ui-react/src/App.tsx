import { useEffect, useState } from "react";
import { Chat } from "./components/Chat";
import { Home } from "./components/Home";
import { Sidebar } from "./components/Sidebar";
import { TopBar } from "./components/TopBar";
import { api, storageGet, storageSet } from "./lib";
import { Panels } from "./panels/Panels";
import { useForge } from "./useForge";

export function App() {
  const forge = useForge();
  const [view, setView] = useState<"home" | "chat">("home");
  const [theme, setTheme] = useState<"dark" | "light">(storageGet("forge-theme") === "light" ? "light" : "dark");
  const [stopped, setStopped] = useState(false);

  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    storageSet("forge-theme", theme);
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

  return (
    <div className="flex h-full flex-col">
      <TopBar forge={forge} theme={theme} onToggleTheme={() => setTheme((t) => (t === "dark" ? "light" : "dark"))} onHome={() => setView("home")} onQuit={quit} />
      <div className="flex min-h-0 flex-1">
        <Sidebar forge={forge} onNew={() => setView("home")} onOpen={open} />
        <main className="flex min-w-0 flex-1 flex-col">
          {view === "home" || !forge.state.workspace ? (
            <div className="min-h-0 flex-1 overflow-y-auto">
              <Home onCreated={async () => { await forge.enter(); setView("chat"); }} />
            </div>
          ) : (
            <Chat forge={forge} />
          )}
        </main>
        {view === "chat" && forge.state.workspace && <Panels forge={forge} />}
      </div>
    </div>
  );
}

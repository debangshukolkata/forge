import { Anvil, Gauge, Home, LogOut, Moon, Power, ShieldCheck, Sun, UserRound } from "lucide-react";
import type { Forge } from "../useForge";
import { AnimatedCost } from "./AnimatedCost";
import { ProjectSwitcher } from "./ProjectSwitcher";
import { Badge, Button, IconButton, Spinner } from "./ui";

export function TopBar({
  forge,
  theme,
  onToggleTheme,
  onHome,
  onQuit,
  user,
  onSignOut,
  onEnvironment,
  onAccount,
  onOpenProject,
  onNewProject,
  onProjectDeleted,
}: {
  forge: Forge;
  theme: "dark" | "light";
  onToggleTheme: () => void;
  onHome: () => void;
  onQuit: () => void;
  user: string | null;
  onSignOut: () => void;
  onEnvironment: () => void;
  onAccount: () => void;
  onOpenProject: (path: string) => void;
  onNewProject: () => void;
  onProjectDeleted: (path: string, wasCurrent: boolean) => void;
}) {
  const { state, context, cost, waiting, connected, controls, replaying } = forge;
  const workspace = state.workspace;
  return (
    <header className="relative z-30 flex h-12 shrink-0 items-center gap-3 border-b border-border bg-surface/80 px-4 backdrop-blur-xl">
      <div className="flex items-center gap-2">
        <div className="flex h-7 w-7 items-center justify-center rounded-md bg-action text-accent-fg">
          <Anvil className="h-4 w-4" aria-hidden />
        </div>
        <span className="font-mono text-[14px] font-semibold tracking-tight">Forge</span>
      </div>
      <div className="mx-1 h-5 w-px bg-border" />
      {workspace ? (
        <div className="flex min-w-0 items-center gap-2">
          <ProjectSwitcher forge={forge} onOpen={onOpenProject} onNew={onNewProject} onDeleted={onProjectDeleted} />
          <Badge tone={workspace.mode === "B" ? "info" : "neutral"}>{workspace.mode === "B" ? "Standalone" : "Repository"}</Badge>
          {waiting ? (
            <Badge tone="warn">Waiting for you</Badge>
          ) : state.busy ? (
            <Badge tone="accent">
              <Spinner className="h-3 w-3" /> Working
            </Badge>
          ) : (
            <Badge>Idle</Badge>
          )}
          {!connected && !replaying && <Badge tone="danger">Reconnecting…</Badge>}
          {!controls && <Badge tone="warn">Watching (read-only)</Badge>}
        </div>
      ) : (
        <span className="text-fg-muted">No project open</span>
      )}
      <div className="flex-1" />
      {context && (
        <span className="hidden items-center gap-1.5 text-[12.5px] text-fg-muted md:flex" title="Context window used">
          <Gauge className="h-3.5 w-3.5" aria-hidden />
          <span className="tabular-nums">{context.percent}%</span>
        </span>
      )}
      {cost && <AnimatedCost total={cost.project?.total.cost_usd ?? cost.total_usd} />}
      <IconButton label={theme === "dark" ? "Light theme" : "Dark theme"} onClick={onToggleTheme}>
        {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
      </IconButton>
      <Button variant="ghost" size="sm" icon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={onEnvironment} title="Connections and models">
        Environment
      </Button>
      <Button variant="ghost" size="sm" icon={<Home className="h-3.5 w-3.5" />} onClick={onHome}>
        Home
      </Button>
      {user && (
        <Button variant="ghost" size="sm" icon={<UserRound className="h-3.5 w-3.5" />} onClick={onAccount} title="Your account and password">
          <span className="max-w-24 truncate">{user}</span>
        </Button>
      )}
      {user && (
        <Button variant="ghost" size="sm" icon={<LogOut className="h-3.5 w-3.5" />} onClick={onSignOut} title={`Signed in as ${user}`}>
          Sign out
        </Button>
      )}
      <Button variant="danger" size="sm" icon={<Power className="h-3.5 w-3.5" />} onClick={onQuit}>
        Quit
      </Button>
    </header>
  );
}

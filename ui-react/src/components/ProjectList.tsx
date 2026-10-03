// "Open an existing project" (D-184): newest first, with what the user last asked for. Opening replays the
// project's events and loads its memory, so work continues where it stopped.
import { ArrowLeft, ChevronRight, FolderGit2, Layers, Search } from "lucide-react";
import { useEffect, useState } from "react";
import { api, timeAgo } from "../lib";
import type { ProjectEntry } from "../types";
import { Headline, Tagline } from "./landing";
import { Badge, Button, Empty, Input, Spinner } from "./ui";

export function ProjectList({ onBack, onOpen }: { onBack: () => void; onOpen: (path: string) => void }) {
  const [projects, setProjects] = useState<ProjectEntry[] | null>(null);
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  useEffect(() => {
    api<ProjectEntry[]>("/api/projects")
      .then(setProjects)
      .catch((failure: Error) => {
        setError(failure.message);
        setProjects([]);
      });
  }, []);
  const shown = (projects ?? []).filter((p) => `${p.name} ${p.repo} ${p.last_request} ${p.memory.state?.goal ?? ""} ${p.memory.state?.next ?? ""}`.toLowerCase().includes(filter.toLowerCase()));

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Button variant="ghost" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={onBack} className="-ml-3 mb-4">
        Back
      </Button>
      <Headline className="!text-[34px]">Your projects.</Headline>
      <Tagline className="mt-2">Choose one to continue. Forge picks up from its memory and history.</Tagline>
      <div className="relative mt-6">
        <Search className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-fg-muted" aria-hidden />
        <Input aria-label="Search projects" placeholder="Search projects" value={filter} onChange={(e) => setFilter(e.target.value)} className="h-11 rounded-full pl-10" />
      </div>
      {error && (
        <p role="alert" className="mt-4 text-[13px] text-danger">
          {error}
        </p>
      )}
      {projects === null ? (
        <div className="mt-10 flex justify-center text-fg-muted">
          <Spinner />
        </div>
      ) : shown.length === 0 ? (
        <Empty title={projects.length === 0 ? "No projects yet" : "No match"}>
          {projects.length === 0 ? "Start a new project and it will show up here." : "Try a different search."}
        </Empty>
      ) : (
        <ul className="mt-5 space-y-3">
          {shown.map((project) => (
            <li key={project.path}>
              <button
                type="button"
                onClick={() => onOpen(project.path)}
                title={project.path}
                className="group flex w-full cursor-pointer items-center gap-4 rounded-[18px] border border-border bg-surface p-5 text-left transition-colors duration-150 hover:border-accent active:scale-[0.995]"
              >
                {project.mode === "B" ? (
                  <Layers className="h-5 w-5 shrink-0 text-fg-muted" aria-hidden />
                ) : (
                  <FolderGit2 className="h-5 w-5 shrink-0 text-fg-muted" aria-hidden />
                )}
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-2">
                    <span className="truncate text-[17px] font-semibold tracking-[-0.37px]">{project.name}</span>
                    <Badge tone={project.mode === "B" ? "info" : "neutral"}>{project.mode === "B" ? "Standalone" : "Repository"}</Badge>
                  </span>
                  <span className="mt-0.5 block truncate text-[13.5px] text-fg-muted">
                    {project.last_request ? `Last: ${project.last_request}` : "No requests yet"}
                  </span>
                  {project.memory.state && (
                    <span className="mt-2 block space-y-0.5 border-l-2 border-border pl-3 text-[13px]" data-testid="project-state">
                      {project.memory.state.goal && (
                        <span className="block truncate">
                          <span className="text-fg-muted">Goal: </span>
                          {project.memory.state.goal}
                        </span>
                      )}
                      {project.memory.state.next && (
                        <span className="block truncate">
                          <span className="text-fg-muted">Next: </span>
                          {project.memory.state.next}
                        </span>
                      )}
                    </span>
                  )}
                  <span className="mt-2 flex flex-wrap items-center gap-1.5">
                    {project.memory.memories > 0 && (
                      <Badge>
                        {project.memory.memories} note{project.memory.memories === 1 ? "" : "s"}
                      </Badge>
                    )}
                    {project.memory.instructions && <Badge>FORGE.md</Badge>}
                    {project.memory.state?.saved && <Badge>handoff {timeAgo(project.memory.state.saved)}</Badge>}
                  </span>
                  <span className="mt-1.5 block truncate text-[12px] text-fg-muted">
                    {timeAgo(project.last_activity)} · {project.path}
                  </span>
                </span>
                <ChevronRight className="h-5 w-5 shrink-0 text-fg-muted transition-colors group-hover:text-accent" aria-hidden />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

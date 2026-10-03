import { ArrowLeft, FolderGit2, Layers, ShieldCheck, XCircle } from "lucide-react";
import { useEffect, useState, type FormEvent } from "react";
import { api, cx } from "../lib";
import { Headline, Tagline } from "./landing";
import { Button, Card, Field, Input, Spinner } from "./ui";

type Mode = "A" | "B";

export function NewProject({ onCreated, onBack, onOpenEnvironment }: { onCreated: () => void; onBack: () => void; onOpenEnvironment: () => void }) {
  const [mode, setMode] = useState<Mode>("B");
  const [project, setProject] = useState("");
  const [folder, setFolder] = useState("");
  const [repo, setRepo] = useState("");
  const [appFolder, setAppFolder] = useState("");
  const [askAppFolder, setAskAppFolder] = useState(false);
  const [terms, setTerms] = useState("");
  const [busy, setBusy] = useState(false);
  const [setupPhase, setSetupPhase] = useState("");
  const [error, setError] = useState("");
  const [known, setKnown] = useState<string[]>([]);

  useEffect(() => {
    api<string[]>("/api/profiles").then(setKnown).catch(() => setKnown([]));
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setSetupPhase(mode === "A" ? "Copying the repository…" : "Setting up the project…");
    // Setup runs as one blocking backend call, before this project's own session/WebSocket exists to carry
    // progress events — so the only way to show real steps is to poll a small status endpoint meanwhile.
    const poll = window.setInterval(() => {
      api<{ phase: string | null }>("/api/setup-progress")
        .then(({ phase }) => phase && setSetupPhase(phase))
        .catch(() => undefined);
    }, 400);
    try {
      await api("/api/projects", {
        method: "POST",
        body: { mode, project, folder, repo: mode === "A" ? repo : "", app_folder: mode === "A" ? appFolder : "", sensitive_terms: mode === "B" ? terms : "" },
      });
      onCreated();
    } catch (failure) {
      const message = (failure as Error).message;
      setError(message);
      if (mode === "A" && /Which folder is the Python app/.test(message)) setAskAppFolder(true);
    } finally {
      window.clearInterval(poll);
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <div className="mb-4 flex items-center justify-between">
        <Button variant="ghost" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={onBack} className="-ml-3">
          Back
        </Button>
        <Button variant="ghost" size="sm" icon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={onOpenEnvironment}>
          Environment
        </Button>
      </div>
      <Headline className="!text-[34px]">New project.</Headline>
      <Tagline className="mt-2">Give it a name and a folder. Everything after that happens in the chat.</Tagline>

      <Card className="mt-6 p-6">
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div role="radiogroup" aria-label="Kind of project" className="grid grid-cols-2 gap-3">
            <ModeOption
              selected={mode === "B"}
              onSelect={() => setMode("B")}
              icon={<Layers className="h-5 w-5" aria-hidden />}
              title="Standalone"
              text="Forge builds new code and never sees yours. Paste signatures or snippets in the chat."
            />
            <ModeOption
              selected={mode === "A"}
              onSelect={() => setMode("A")}
              icon={<FolderGit2 className="h-5 w-5" aria-hidden />}
              title="From an existing repository"
              text="Forge works on a copy of your repository and never writes to the original."
            />
          </div>

          <Field label="Project name" hint={mode === "B" ? "Reusing a name reuses what Forge learned about that project." : undefined}>
            <Input required list="known-projects" value={project} onChange={(e) => setProject(e.target.value)} placeholder="e.g. payments-masking" autoFocus />
            <datalist id="known-projects">
              {known.map((name) => (
                <option key={name} value={name} />
              ))}
            </datalist>
          </Field>

          <Field label="Project folder" hint="A new, empty folder. Forge works here and puts the result in its output folder.">
            <Input required value={folder} onChange={(e) => setFolder(e.target.value)} placeholder="C:\Work\LocalDevelopment\payments-masking" />
          </Field>

          {mode === "A" && (
            <Field label="Existing project / repository path" hint="Read only: Forge copies it into the project folder.">
              <Input required value={repo} onChange={(e) => setRepo(e.target.value)} placeholder="C:\Work\LocalDevelopment\claims-repo" />
            </Field>
          )}
          {mode === "A" && askAppFolder && (
            <Field label="App sub-folder" hint="The folder that holds the Python app, e.g. backend.">
              <Input value={appFolder} onChange={(e) => setAppFolder(e.target.value)} placeholder="backend" />
            </Field>
          )}
          {mode === "B" && (
            <Field label="Sensitive terms (optional)" hint="Company, product or client names. They never go into a web search.">
              <Input value={terms} onChange={(e) => setTerms(e.target.value)} placeholder="Acme, Project Falcon" />
            </Field>
          )}

          {error && (
            <div role="alert" className="flex gap-2 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{error}</span>
            </div>
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" variant="primary" disabled={busy || !project.trim() || !folder.trim() || (mode === "A" && !repo.trim())}>
              {busy && <Spinner />}
              Create and open
            </Button>
            {busy && <span className="text-[13px] text-fg-muted">{setupPhase}</span>}
          </div>
        </form>
      </Card>

    </div>
  );
}

function ModeOption({ selected, onSelect, icon, title, text }: { selected: boolean; onSelect: () => void; icon: React.ReactNode; title: string; text: string }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className={cx(
        "flex cursor-pointer flex-col gap-1.5 rounded-lg border p-4 text-left transition-colors duration-150",
        selected ? "border-accent bg-accent-soft" : "border-border hover:border-border-strong hover:bg-raised",
      )}
    >
      <span className={cx("flex items-center gap-2 font-medium", selected ? "text-accent" : "text-fg")}>
        {icon}
        {title}
      </span>
      <span className="text-[12.5px] leading-snug text-fg-muted">{text}</span>
    </button>
  );
}

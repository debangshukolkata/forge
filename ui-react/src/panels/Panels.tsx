import "diff2html/bundles/css/diff2html.min.css";
import DOMPurify from "dompurify";
import { html as diffHtml } from "diff2html";
import {
  Brain, ChevronDown, ChevronRight, Columns2, Database, Download, FileCode2, FileText, Folder, FolderOpen, Gauge,
  GitCompareArrows, ListChecks, RotateCcw, Rows2, Settings2, Target,
} from "lucide-react";
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Badge, Button, Card, CopyButton, Empty, KeyValues, SectionTitle, Spinner, Textarea } from "../components/ui";
import { Code, Markdown, api, cx, languageOf, money, storageGet, storageSet } from "../lib";
import type { Forge } from "../useForge";

type Tab = "tasks" | "files" | "diffs" | "db" | "evals" | "learning" | "context" | "settings";

const TABS: Array<{ id: Tab; label: string; icon: ReactNode }> = [
  { id: "tasks", label: "Tasks", icon: <ListChecks className="h-4 w-4" /> },
  { id: "files", label: "Files", icon: <FileCode2 className="h-4 w-4" /> },
  { id: "diffs", label: "Diffs", icon: <GitCompareArrows className="h-4 w-4" /> },
  { id: "db", label: "DB", icon: <Database className="h-4 w-4" /> },
  { id: "evals", label: "Evals", icon: <Target className="h-4 w-4" /> },
  { id: "learning", label: "Learning", icon: <Brain className="h-4 w-4" /> },
  { id: "context", label: "Context", icon: <Gauge className="h-4 w-4" /> },
  { id: "settings", label: "Settings", icon: <Settings2 className="h-4 w-4" /> },
];

export function Panels({ forge }: { forge: Forge }) {
  const [tab, setTab] = useState<Tab>((storageGet("forge-react-tab") as Tab) || "tasks");
  const select = (next: Tab) => {
    setTab(next);
    storageSet("forge-react-tab", next);
  };
  return (
    <aside aria-label="Details" className="flex w-[440px] shrink-0 flex-col border-l border-border bg-surface">
      {/* Eight tabs in one row that always fits: icon above a short label, no hidden overflow. */}
      <div role="tablist" className="grid shrink-0 grid-cols-8 border-b border-border px-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            role="tab"
            aria-selected={tab === t.id}
            onClick={() => select(t.id)}
            title={t.label}
            className={cx(
              "flex cursor-pointer flex-col items-center gap-1 border-b-2 px-1 pb-2 pt-2.5 text-[11px] font-medium transition-colors duration-150",
              tab === t.id ? "border-accent text-fg" : "border-transparent text-fg-muted hover:text-fg",
            )}
          >
            <span aria-hidden className={tab === t.id ? "text-accent" : ""}>{t.icon}</span>
            {t.label}
          </button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4" role="tabpanel">
        {tab === "tasks" && <TasksTab forge={forge} />}
        {tab === "files" && <FilesTab forge={forge} />}
        {tab === "diffs" && <DiffsTab forge={forge} />}
        {tab === "db" && <DbTab forge={forge} />}
        {tab === "evals" && <EvalsTab forge={forge} />}
        {tab === "learning" && <LearningTab forge={forge} />}
        {tab === "context" && <ContextTab forge={forge} />}
        {tab === "settings" && <SettingsTab forge={forge} />}
      </div>
    </aside>
  );
}

/** Loads data for a tab and reloads it when Forge reports changes. */
function useData<T>(path: string, tick: number): { data: T | null; error: string; reload: () => void } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const load = useCallback(() => {
    api<T>(path).then((d) => { setData(d); setError(""); }).catch((e: Error) => setError(e.message));
  }, [path]);
  useEffect(load, [load, tick]);
  return { data, error, reload: load };
}

function Loading({ error }: { error?: string }) {
  if (error) return <div role="alert" className="text-[13px] text-danger">{error}</div>;
  return <div className="flex items-center gap-2 text-[13px] text-fg-muted"><Spinner /> Loading…</div>;
}

// --- Tasks ---

const STATUS_TONE: Record<string, "accent" | "info" | "danger" | "neutral" | "warn"> = {
  done: "accent", in_progress: "info", blocked: "danger", pending: "neutral", skipped: "warn",
};

function TasksTab({ forge }: { forge: Forge }) {
  const { state } = forge;
  if (!state.workspace) return <Empty title="No project open" />;
  const tasks = state.tasks || [];
  const done = tasks.filter((t) => t.status === "done").length;
  return (
    <div>
      <div className="mb-3 flex items-center justify-between text-[13px]">
        <span className="text-fg-muted">Phase <span className="font-medium text-fg">{state.phase}</span></span>
        {tasks.length > 0 && <span className="font-mono text-[12px] text-fg-muted tabular-nums">{done}/{tasks.length} done</span>}
      </div>
      {tasks.length > 0 && (
        <div className="mb-4 h-1.5 overflow-hidden rounded-full bg-muted" aria-hidden>
          <div className="h-full rounded-full bg-accent transition-all duration-300" style={{ width: `${(done / tasks.length) * 100}%` }} />
        </div>
      )}
      {tasks.length === 0 ? (
        <Empty icon={<ListChecks className="h-8 w-8" />} title="No tasks yet">They appear once the plan is approved.</Empty>
      ) : (
        <ol className="space-y-2">
          {tasks.map((task) => (
            <li key={task.id} className={cx("rounded-lg border px-3 py-2.5", task.id === state.current_task ? "border-accent/60 bg-accent-soft" : "border-border")}>
              <div className="flex items-start gap-2">
                <span className="mt-0.5 font-mono text-[11.5px] text-fg-muted">{task.id}</span>
                <span className="min-w-0 flex-1 text-[13px] font-medium">{task.title}</span>
                <Badge tone={STATUS_TONE[task.status] ?? "neutral"}>{task.status.replace("_", " ")}</Badge>
              </div>
              {(task.attempts ?? 0) > 1 && <div className="mt-1 text-[12px] text-fg-muted">Attempt {task.attempts}</div>}
              {task.blocked_reason && <div className="mt-1 text-[12px] text-danger">{task.blocked_reason}</div>}
            </li>
          ))}
        </ol>
      )}
    </div>
  );
}

// --- Files ---

interface TreeEntry { name: string; path: string; dir: boolean; status?: string }

function FilesTab({ forge }: { forge: Forge }) {
  const [viewer, setViewer] = useState<ReactNode>(null);
  const openFile = async (root: string, path: string) => {
    setViewer(<Loading />);
    try {
      const file = await api<{ text: string; binary: boolean; truncated: boolean }>(`/api/file?root=${root}&path=${encodeURIComponent(path)}`);
      setViewer(
        <div>
          <div className="mb-2 flex items-center justify-between">
            <span className="truncate font-mono text-[12px] text-fg-muted">{root}/{path}</span>
            {!file.binary && <CopyButton text={file.text} label="Copy file" />}
          </div>
          {file.binary ? <p className="text-[13px] text-fg-muted">Binary file</p> : <Code text={file.text} language={languageOf(path)} className="max-h-[520px]" />}
          {file.truncated && <p className="mt-1 text-[12px] text-fg-muted">(truncated)</p>}
        </div>,
      );
    } catch (e) {
      setViewer(<Loading error={(e as Error).message} />);
    }
  };
  const instructions = async () => {
    try {
      const file = await api<{ text: string }>("/api/file?root=output&path=COPY_INSTRUCTIONS.md");
      setViewer(<Markdown text={file.text} />);
    } catch {
      setViewer(<p className="text-[13px] text-fg-muted">No output yet: it is built at the end of a requirement, or with /export.</p>);
    }
  };
  if (!forge.state.workspace) return <Empty title="No project open" />;
  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <a href="/api/output.zip" download className="contents">
          <Button size="sm" icon={<Download className="h-3.5 w-3.5" />}>Download output</Button>
        </a>
        <Button size="sm" variant="ghost" icon={<FileText className="h-3.5 w-3.5" />} onClick={instructions}>Copy instructions</Button>
      </div>
      {(["repo", "output"] as const).map((root) => (
        <div key={`${root}-${forge.changeTick}`}>
          <SectionTitle>{root === "repo" ? "Project files" : "Output"}</SectionTitle>
          <Tree root={root} dir="" onOpen={openFile} />
        </div>
      ))}
      {viewer && <div className="border-t border-border pt-4">{viewer}</div>}
    </div>
  );
}

function Tree({ root, dir, onOpen }: { root: string; dir: string; onOpen: (root: string, path: string) => void }) {
  const [entries, setEntries] = useState<TreeEntry[] | null>(null);
  const [error, setError] = useState("");
  useEffect(() => {
    api<{ entries: TreeEntry[] }>(`/api/tree?root=${root}&dir=${encodeURIComponent(dir)}`)
      .then((d) => setEntries(d.entries)).catch((e: Error) => setError(e.message));
  }, [root, dir]);
  if (error) return <div className="pl-2 text-[12px] text-fg-muted">{/not exist|no output|404/i.test(error) ? "Empty" : error}</div>;
  if (!entries) return <div className="pl-2"><Spinner className="h-3 w-3" /></div>;
  if (!entries.length) return <div className="pl-2 text-[12px] text-fg-muted">Empty</div>;
  return (
    <ul className={cx(dir && "ml-3 border-l border-border pl-2")}>
      {entries.map((entry) => <TreeRow key={entry.path} root={root} entry={entry} onOpen={onOpen} />)}
    </ul>
  );
}

function TreeRow({ root, entry, onOpen }: { root: string; entry: TreeEntry; onOpen: (root: string, path: string) => void }) {
  const [open, setOpen] = useState(false);
  const tone = entry.status === "added" ? "text-accent" : entry.status === "modified" ? "text-warn" : entry.status === "deleted" ? "text-danger line-through" : "";
  return (
    <li>
      <button
        type="button"
        onClick={() => (entry.dir ? setOpen((v) => !v) : onOpen(root, entry.path))}
        className={cx("flex w-full cursor-pointer items-center gap-1.5 rounded px-1.5 py-1 text-left font-mono text-[12.5px] transition-colors duration-150 hover:bg-raised", tone)}
      >
        {entry.dir ? (
          <>
            {open ? <ChevronDown className="h-3 w-3 shrink-0" /> : <ChevronRight className="h-3 w-3 shrink-0" />}
            {open ? <FolderOpen className="h-3.5 w-3.5 shrink-0 text-info" /> : <Folder className="h-3.5 w-3.5 shrink-0 text-info" />}
          </>
        ) : (
          <FileCode2 className="ml-[18px] h-3.5 w-3.5 shrink-0 text-fg-muted" />
        )}
        <span className="truncate">{entry.name}</span>
      </button>
      {entry.dir && open && <Tree root={root} dir={entry.path} onOpen={onOpen} />}
    </li>
  );
}

// --- Diffs and checkpoints ---

function DiffsTab({ forge }: { forge: Forge }) {
  const [format, setFormat] = useState<"line-by-line" | "side-by-side">("line-by-line");
  const diff = useData<{ patch: string }>("/api/diff", forge.changeTick);
  const checkpoints = useData<Array<{ id: string; label: string; created: string }>>("/api/checkpoints", forge.changeTick);
  if (!forge.state.workspace) return <Empty title="No project open" />;
  if (!diff.data) return <Loading error={diff.error} />;
  const html = diff.data.patch.trim()
    ? DOMPurify.sanitize(diffHtml(diff.data.patch, { drawFileList: true, matching: "lines", outputFormat: format }))
    : "";
  return (
    <div>
      <div className="mb-3 flex justify-end">
        <Button size="sm" variant="ghost" onClick={() => setFormat((f) => (f === "side-by-side" ? "line-by-line" : "side-by-side"))}
          icon={format === "side-by-side" ? <Rows2 className="h-3.5 w-3.5" /> : <Columns2 className="h-3.5 w-3.5" />}>
          {format === "side-by-side" ? "Unified" : "Side by side"}
        </Button>
      </div>
      {html ? <div className="diff-view overflow-x-auto" dangerouslySetInnerHTML={{ __html: html }} /> : <Empty icon={<GitCompareArrows className="h-8 w-8" />} title="No changes yet" />}
      <SectionTitle>Checkpoints</SectionTitle>
      {!checkpoints.data?.length ? (
        <p className="text-[13px] text-fg-muted">None yet.</p>
      ) : (
        <ul className="space-y-1.5">
          {checkpoints.data.slice().reverse().map((cp) => (
            <li key={cp.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-2">
              <span className="font-mono text-[11.5px] text-fg-muted">{cp.id}</span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[13px]">{cp.label}</span>
                <span className="block text-[11.5px] text-fg-muted">{cp.created}</span>
              </span>
              <Button size="sm" variant="ghost" icon={<RotateCcw className="h-3.5 w-3.5" />}
                onClick={() => confirm(`Undo every change back to and including checkpoint ${cp.id}?`) && forge.command(`/rewind ${cp.id}`)}>
                Rewind
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --- Database ---

function DbTab({ forge }: { forge: Forge }) {
  const { state } = forge;
  if (!state.database) return <Empty icon={<Database className="h-8 w-8" />} title="No database configured">Set LOCAL_PG_URL / DEV_PG_URL in Forge's .env.</Empty>;
  return (
    <div className="space-y-4">
      <Code text={state.database} />
      <div className="flex gap-2">
        <Button size="sm" onClick={() => forge.command("/db status")}>Re-check access</Button>
        <Button size="sm" variant="danger" onClick={() => confirm("Drop every object Forge created in the scratch schema?") && forge.command("/db cleanup")}>
          Clean up scratch objects
        </Button>
      </div>
      {(state.db_requests || []).map((request) => <DbRequestCard key={request.id} request={request} forge={forge} />)}
    </div>
  );
}

function DbRequestCard({ request, forge }: { request: NonNullable<Forge["state"]["db_requests"]>[number]; forge: Forge }) {
  const [pasted, setPasted] = useState("");
  const pending = request.status === "pending";
  return (
    <Card className="space-y-2 p-3">
      <div className="flex items-center gap-2">
        <span className="font-mono text-[11.5px] text-fg-muted">{request.id}</span>
        <span className="min-w-0 flex-1 truncate font-medium">{request.title}</span>
        <Badge tone={pending ? "warn" : "accent"}>{request.status}</Badge>
      </div>
      <p className="text-[13px]">{request.purpose}</p>
      <p className="text-[12px] text-fg-muted">{request.target} · run by {request.who}</p>
      <div className="flex items-center justify-between text-[12px] font-medium text-fg-muted">SQL <CopyButton text={request.sql} /></div>
      <Code text={request.sql} language="sql" />
      <div className="flex items-center justify-between text-[12px] font-medium text-fg-muted">Verification <CopyButton text={request.verification_query} /></div>
      <Code text={request.verification_query} language="sql" />
      {pending && (
        <>
          <Textarea rows={2} value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder="If Forge can't reach the DB: paste the verification query's result (column names, no data rows)" />
          <div className="flex gap-2">
            <Button size="sm" variant="primary" onClick={() => forge.command(`/db done ${request.id} ${pasted}`.trim())}>Mark done</Button>
            <Button size="sm" onClick={() => forge.command(`/db cant ${request.id} ${pasted || "no access"}`)}>I can't</Button>
            <Button size="sm" variant="ghost" onClick={() => forge.command(`/db skip ${request.id}`)}>Skip</Button>
          </div>
        </>
      )}
    </Card>
  );
}

// --- Evals ---

interface EvalRun { n: number; name: string; misses: string[]; metrics: Record<string, number> }

function EvalsTab({ forge }: { forge: Forge }) {
  const runs = useData<EvalRun[]>("/api/evals", forge.changeTick);
  const [report, setReport] = useState<{ n: number; markdown: string; overlays: string[] } | null>(null);
  if (!runs.data) return <Loading error={runs.error} />;
  if (!runs.data.length) return <Empty icon={<Target className="h-8 w-8" />} title="No eval runs yet">For extraction or perception work Forge keeps an eval set in evals/&lt;name&gt;/ and measures accuracy against it.</Empty>;
  return (
    <div className="space-y-2">
      {runs.data.slice().reverse().map((run) => (
        <Card key={run.n} className="p-3">
          <div className="flex items-center gap-2">
            <span className="font-medium">Run {run.n} · {run.name}</span>
            <span className="flex-1" />
            <Badge tone={run.misses.length ? "danger" : "accent"}>{run.misses.length ? "Targets missed" : "Targets met"}</Badge>
          </div>
          <div className="mt-1 font-mono text-[12px] text-fg-muted">
            {Object.entries(run.metrics).map(([k, v]) => `${k} ${v}`).join(" · ")}
          </div>
          <Button size="sm" variant="ghost" className="mt-2" onClick={async () => setReport({ n: run.n, ...(await api<{ markdown: string; overlays: string[] }>(`/api/evals/${run.n}`)) })}>
            Show report
          </Button>
        </Card>
      ))}
      {report && (
        <div className="border-t border-border pt-3">
          <Markdown text={report.markdown} />
          {report.overlays.map((name) => (
            <figure key={name} className="mt-3">
              <img src={`/api/evals/${report.n}/overlay/${encodeURIComponent(name)}`} alt={name} className="w-full rounded-md border border-border" />
              <figcaption className="mt-1 text-[12px] text-fg-muted">{name} — green expected, red predicted</figcaption>
            </figure>
          ))}
        </div>
      )}
    </div>
  );
}

// --- Learning ---

interface Learning {
  lessons: Array<{ id: string; status: string; scope: string; text: string }>;
  cards: Array<{ id: string; title: string; status: string; created: string }>;
  improvements: Array<{ id: string; tier: number; status: string; title: string }>;
}

function LearningTab({ forge }: { forge: Forge }) {
  const { data, error } = useData<Learning>("/api/learning", forge.changeTick);
  if (!data) return <Loading error={error} />;
  return (
    <div>
      <SectionTitle>Lessons</SectionTitle>
      <p className="mb-2 text-[12.5px] text-fg-muted">Only approved lessons are used; they are pinned at the start of related tasks.</p>
      {!data.lessons.length && <p className="text-[13px] text-fg-muted">None yet: proposed in the retro after each requirement.</p>}
      <div className="space-y-2">
        {data.lessons.map((lesson) => (
          <Card key={lesson.id} className="space-y-2 p-3">
            <div className="flex items-center gap-2 text-[12px]">
              <Badge tone={lesson.status === "approved" ? "accent" : "warn"}>{lesson.status}</Badge>
              <span className="font-mono text-fg-muted">{lesson.id}</span>
              <span className="text-fg-muted">· {lesson.scope}</span>
            </div>
            <p className="text-[13px]">{lesson.text}</p>
            <div className="flex gap-2">
              {lesson.status !== "approved" && <Button size="sm" variant="primary" onClick={() => forge.command(`/lessons approve ${lesson.id}`)}>Approve</Button>}
              <Button size="sm" variant="ghost" onClick={() => forge.command(`/lessons reject ${lesson.id}`)}>Reject</Button>
              {lesson.scope !== "global" && lesson.status === "approved" && <Button size="sm" onClick={() => forge.command(`/lessons promote ${lesson.id}`)}>Make global</Button>}
            </div>
          </Card>
        ))}
      </div>
      <SectionTitle>Requirements library</SectionTitle>
      {!data.cards.length && <p className="text-[13px] text-fg-muted">No earlier requirements yet.</p>}
      <ul className="space-y-1.5">
        {data.cards.map((card) => (
          <li key={card.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-2">
            <span className="font-mono text-[11.5px] text-fg-muted">{card.id}</span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[13px]">{card.title}</span>
              <span className="block text-[11.5px] text-fg-muted">{card.status} · {card.created}</span>
            </span>
            <Button size="sm" variant="ghost" onClick={() => forge.command(`/library show ${card.id}`)}>Show</Button>
          </li>
        ))}
      </ul>
      <SectionTitle>Improvement proposals</SectionTitle>
      <p className="mb-2 text-[12.5px] text-fg-muted">Forge never changes itself: you apply tier-2 tweaks; tier-3 patches are yours to apply.</p>
      <div className="space-y-2">
        {data.improvements.map((p) => (
          <Card key={p.id} className="space-y-2 p-3">
            <div className="text-[13px]"><span className="font-mono text-fg-muted">{p.id}</span> · tier {p.tier} · {p.status} · {p.title}</div>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => forge.command(`/improve show ${p.id}`)}>Show</Button>
              {p.tier === 3 && <Button size="sm" onClick={() => forge.command(`/improve validate ${p.id}`)}>Validate</Button>}
              {p.tier === 2 && p.status !== "applied" && <Button size="sm" variant="primary" onClick={() => confirm(`Apply ${p.id}?`) && forge.command(`/improve apply ${p.id}`)}>Apply</Button>}
              <Button size="sm" variant="ghost" onClick={() => forge.command(`/improve reject ${p.id}`)}>Reject</Button>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
}

// --- Context and cost ---

function ContextTab({ forge }: { forge: Forge }) {
  const { context: c, cost } = forge;
  return (
    <div>
      <SectionTitle>Context window</SectionTitle>
      {c ? (
        <>
          <div className="mb-1 flex justify-between text-[13px]"><span className="text-fg-muted">Used</span><span className="font-mono tabular-nums">{c.percent}%</span></div>
          <div className="mb-4 h-2 overflow-hidden rounded-full bg-muted" aria-hidden>
            <div className={cx("h-full rounded-full transition-all duration-300", c.percent > 85 ? "bg-danger" : c.percent > 65 ? "bg-warn" : "bg-accent")} style={{ width: `${Math.min(100, c.percent)}%` }} />
          </div>
          <KeyValues rows={[["Fixed (prompt + tools)", c.fixed], ["Pinned", c.pinned], ["History", c.history], ["Free", c.free], ["Usable", c.usable], ["Compactions", c.compactions]]} />
        </>
      ) : (
        <p className="text-[13px] text-fg-muted">No model call yet.</p>
      )}
      {cost && (
        <>
          <SectionTitle>Cost</SectionTitle>
          <KeyValues rows={[["Total", money(cost.total_usd)], ["Budget", money(cost.budget_usd)], ["Calls", cost.calls], ...Object.entries(cost.cost_by_role || {}).map(([role, usd]) => [role, money(usd)] as [string, string])]} />
        </>
      )}
      <Button size="sm" className="mt-4" onClick={() => forge.command("/compact")}>Compact now</Button>
    </div>
  );
}

// --- Settings ---

interface Config { roles?: Record<string, string>; models?: string[]; permission_mode?: string; sandbox?: unknown; limits?: Record<string, unknown> }

function SettingsTab({ forge }: { forge: Forge }) {
  const { data, error } = useData<Config>("/api/config", forge.changeTick);
  if (!data) return <Loading error={error} />;
  const select = "h-8 rounded-md border border-border bg-bg px-2 text-[13px] text-fg cursor-pointer hover:border-border-strong";
  return (
    <div>
      <p className="mb-4 text-[12.5px] text-fg-muted">Keys and endpoints stay in Forge's .env; they can't be viewed or edited here.</p>
      <SectionTitle>Model per role</SectionTitle>
      <div className="space-y-2">
        {Object.entries(data.roles || {}).map(([role, model]) => (
          <label key={role} className="flex items-center justify-between gap-3 text-[13px]">
            <span className="text-fg-muted">{role}</span>
            <select className={select} defaultValue={model} onChange={(e) => forge.command(`/model ${role} ${e.target.value}`)}>
              {(data.models || []).map((m) => <option key={m} value={m}>{m}</option>)}
            </select>
          </label>
        ))}
      </div>
      <SectionTitle>Permission mode</SectionTitle>
      <select className={select} defaultValue={data.permission_mode} onChange={(e) => forge.command(`/mode ${e.target.value}`)} aria-label="Permission mode">
        {["plan", "default", "auto"].map((m) => <option key={m} value={m}>{m}</option>)}
      </select>
      <SectionTitle>Other</SectionTitle>
      <KeyValues rows={[["Sandbox", String(data.sandbox)], ...Object.entries(data.limits || {}).map(([k, v]) => [k, String(v)] as [string, string])]} />
    </div>
  );
}

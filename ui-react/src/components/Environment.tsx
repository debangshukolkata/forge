// Environment and model plan (D-186) as a drawer on the right: the checks run live and flip from "checking" to a
// result one by one, then Forge proposes which model serves each role from what actually answered. The user
// confirms (or changes a row) and the choice is remembered per machine; next time the saved results show at once
// while the checks re-run. It opens by itself on the New project screen and from "Environment" in the top bar.
import { AlertTriangle, CheckCircle2, RotateCw, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, timeAgo } from "../lib";
import type { CheckInfo, CheckResultView, EnvironmentOverview, ModelPlan } from "../types";
import { Badge, Button, IconButton, Select, Spinner } from "./ui";

type Row = { result: CheckResultView | null; running: boolean };

const ROLE_LABEL: Record<string, string> = { kb_builder: "Knowledge builder", judge: "Judge (evals)", fallback: "Fallback" };

export function EnvironmentDrawer({ onClose }: { onClose: () => void }) {
  const [checks, setChecks] = useState<CheckInfo[]>([]);
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [plan, setPlan] = useState<ModelPlan | null>(null);
  const [choice, setChoice] = useState<Record<string, string>>({});
  const touched = useRef<Set<string>>(new Set());
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);

  const adopt = useCallback((next: ModelPlan) => {
    setPlan(next);
    // Follow the proposal for every role the user has not changed by hand.
    setChoice((prev) => {
      const merged = { ...prev };
      for (const entry of next.roles) if (!touched.current.has(entry.role) && entry.model) merged[entry.role] = entry.model;
      return merged;
    });
  }, []);

  const runCheck = useCallback(
    async (id: string) => {
      setRows((prev) => ({ ...prev, [id]: { result: prev[id]?.result ?? null, running: true } }));
      try {
        const done = await api<{ result: CheckResultView; plan: ModelPlan }>(`/api/environment/check/${id}`, { method: "POST" });
        setRows((prev) => ({ ...prev, [id]: { result: done.result, running: false } }));
        adopt(done.plan);
      } catch (failure) {
        const detail = (failure as Error).message;
        setRows((prev) => ({ ...prev, [id]: { result: { id, status: "fail", detail, hint: "Retry.", models: {} }, running: false } }));
      }
    },
    [adopt],
  );

  useEffect(() => {
    api<EnvironmentOverview>("/api/environment")
      .then((overview) => {
        setChecks(overview.checks);
        setRows(Object.fromEntries(overview.checks.map((c) => [c.id, { result: overview.saved.results[c.id] ?? null, running: true }])));
        adopt(overview.plan);
        overview.checks.forEach((c) => void runCheck(c.id));
      })
      .catch((failure: Error) => setError(failure.message));
  }, [adopt, runCheck]);

  const azure = rows["azure"];
  const waiting = checks.filter((c) => !c.optional).some((c) => rows[c.id]?.running);
  const canSave = !waiting && azure?.result?.status !== "fail" && Boolean(choice["coder"]) && plan !== null;

  const save = async () => {
    setSaving(true);
    setError("");
    try {
      await api("/api/environment/confirm", { method: "POST", body: { roles: choice } });
      onClose();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <aside
      role="dialog"
      aria-label="Environment"
      className="drawer-in flex w-[460px] max-w-[92vw] shrink-0 flex-col border-l border-border bg-surface"
    >
      <div className="flex items-start gap-2 border-b border-border px-5 py-4">
        <div className="min-w-0 flex-1">
          <h2 className="text-[19px] font-semibold tracking-[-0.3px]">Environment</h2>
          <p className="mt-0.5 text-[12.5px] text-fg-muted">Forge tests each connection, then picks the models from what works. No keys are shown.</p>
        </div>
        <IconButton label="Close" onClick={onClose}>
          <X className="h-4 w-4" />
        </IconButton>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="divide-y divide-border">
          {checks.length === 0 && !error && (
            <div className="flex justify-center p-6 text-fg-muted">
              <Spinner />
            </div>
          )}
          {checks.map((check) => (
            <CheckRow key={check.id} check={check} row={rows[check.id]} onRetry={() => void runCheck(check.id)} />
          ))}
        </div>

        {plan && (
          <div className="border-t border-border px-5 py-4">
            <h3 className="text-[15px] font-semibold">Models</h3>
            <p className="text-[12.5px] text-fg-muted">Chosen from the models that answered. Change a row if you prefer another.</p>
            <div className="mt-3 space-y-3">
              {plan.roles.map((entry) => (
                <div key={entry.role}>
                  <div className="flex items-center gap-3">
                    <span className="w-32 shrink-0 text-[13px] font-medium">{ROLE_LABEL[entry.role] ?? entry.role.charAt(0).toUpperCase() + entry.role.slice(1)}</span>
                    <Select
                      aria-label={`Model for ${entry.role}`}
                      className="flex-1"
                      value={choice[entry.role] ?? ""}
                      onChange={(event) => {
                        touched.current.add(entry.role);
                        setChoice((prev) => ({ ...prev, [entry.role]: event.target.value }));
                      }}
                    >
                      {!choice[entry.role] && <option value="">No model available</option>}
                      {plan.options
                        .filter((option) => (entry.role !== "vision" || option.vision) && (option.usable || option.key === choice[entry.role]))
                        .map((option) => (
                          <option key={option.key} value={option.key}>
                            {option.label}
                          </option>
                        ))}
                    </Select>
                  </div>
                  <div className="ml-[8.75rem] mt-0.5 text-[11.5px] text-fg-muted">{entry.reason}</div>
                </div>
              ))}
            </div>
            {plan.notes.map((note) => (
              <p key={note} className="mt-3 flex gap-2 text-[12.5px] text-warn">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
                {note}
              </p>
            ))}
          </div>
        )}
      </div>

      <div className="border-t border-border px-5 py-3">
        {error && (
          <p role="alert" className="mb-2 flex gap-2 text-[12.5px] text-danger">
            <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
            {error}
          </p>
        )}
        <div className="flex items-center gap-2">
          <Button variant="primary" disabled={!canSave || saving} onClick={() => void save()}>
            {saving && <Spinner />}
            Save models
          </Button>
          <Button variant="secondary" disabled={waiting} icon={<RotateCw className="h-3.5 w-3.5" />} onClick={() => checks.forEach((c) => void runCheck(c.id))}>
            Check again
          </Button>
        </div>
        {!canSave && !waiting && plan && <p className="mt-2 text-[12px] text-fg-muted">Azure OpenAI has to work before models can be saved.</p>}
      </div>
    </aside>
  );
}

function CheckRow({ check, row, onRetry }: { check: CheckInfo; row: Row | undefined; onRetry: () => void }) {
  const result = row?.result ?? null;
  const running = row?.running ?? true;
  return (
    <div className="flex items-start gap-3 px-5 py-3.5">
      <div className="mt-0.5 w-5 shrink-0" aria-live="polite">
        {running ? (
          <Spinner className="text-fg-muted" />
        ) : result?.status === "ok" ? (
          <CheckCircle2 className="h-5 w-5 text-ok" aria-label="Working" />
        ) : result?.status === "warn" ? (
          <AlertTriangle className="h-5 w-5 text-warn" aria-label="Warning" />
        ) : (
          <XCircle className="h-5 w-5 text-danger" aria-label="Failed" />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[13.5px] font-semibold">{check.label}</span>
          {check.optional && <Badge>Optional</Badge>}
        </div>
        <div className="text-[12px] text-fg-muted">{check.purpose}</div>
        {result && (
          <div className="mt-1 break-words text-[12.5px]">
            {result.detail}
            {running && <span className="text-fg-muted"> (earlier result, checking again…)</span>}
          </div>
        )}
        {result && !running && result.hint && <div className="mt-0.5 text-[12px] text-fg-muted">{result.hint}</div>}
        {result?.checked_at && !running && <div className="mt-0.5 text-[11px] text-fg-muted">Checked {timeAgo(result.checked_at)}</div>}
        {!result && running && <div className="mt-1 text-[12.5px] text-fg-muted">Checking…</div>}
      </div>
      <IconButton label={`Check ${check.label} again`} disabled={running} onClick={onRetry}>
        <RotateCw className="h-3.5 w-3.5" />
      </IconButton>
    </div>
  );
}

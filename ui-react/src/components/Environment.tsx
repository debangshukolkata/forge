// Environment and model plan (D-186): the checks run live and flip from "checking" to a result one by one, then
// Forge proposes which model serves each role from what actually answered. The user confirms (or changes a row)
// and the choice is remembered per machine; next time the saved results show at once while the checks re-run.
import { AlertTriangle, ArrowLeft, CheckCircle2, RotateCw, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, timeAgo } from "../lib";
import type { CheckInfo, CheckResultView, EnvironmentOverview, ModelPlan } from "../types";
import { Headline, Tagline } from "./landing";
import { Badge, Button, Card, Select, Spinner } from "./ui";

const ROLE_LABEL: Record<string, string> = { kb_builder: "Knowledge builder", judge: "Judge (evals)", fallback: "Fallback" };

type Row = { result: CheckResultView | null; running: boolean };

export function Environment({
  onContinue,
  onBack,
  continueLabel,
  backLabel,
}: {
  onContinue: () => void;
  onBack: () => void;
  continueLabel: string;
  backLabel: string;
}) {
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
  const required = checks.filter((c) => !c.optional);
  const waiting = required.some((c) => rows[c.id]?.running);
  const coderReady = Boolean(choice["coder"]);
  const canContinue = !waiting && azure?.result?.status !== "fail" && coderReady && plan !== null;

  const confirm = async () => {
    setSaving(true);
    setError("");
    try {
      await api("/api/environment/confirm", { method: "POST", body: { roles: choice } });
      onContinue();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      <Button variant="ghost" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={onBack} className="-ml-3 mb-4">
        {backLabel}
      </Button>
      <Headline className="!text-[34px]">Check your environment.</Headline>
      <Tagline className="mt-2">Forge tests each connection now, then picks the models from what works. Nothing here shows a key.</Tagline>

      <Card className="mt-6 divide-y divide-border">
        {checks.length === 0 && !error && (
          <div className="flex justify-center p-6 text-fg-muted">
            <Spinner />
          </div>
        )}
        {checks.map((check) => (
          <CheckRow key={check.id} check={check} row={rows[check.id]} onRetry={() => void runCheck(check.id)} />
        ))}
      </Card>

      {plan && (
        <>
          <h2 className="mt-10 text-[22px] font-semibold tracking-[-0.3px]">Models</h2>
          <Tagline className="mt-1">Chosen from the models that answered. Change a row if you prefer another.</Tagline>
          <Card className="mt-4 divide-y divide-border">
            {plan.roles.map((entry) => (
              <div key={entry.role} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-5 py-3">
                <div className="w-36 shrink-0 font-medium capitalize">{ROLE_LABEL[entry.role] ?? entry.role}</div>
                <Select
                  aria-label={`Model for ${entry.role}`}
                  className="!w-52"
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
                <span className="min-w-0 flex-1 text-[12.5px] text-fg-muted">{entry.reason}</span>
              </div>
            ))}
          </Card>
          {plan.notes.map((note) => (
            <p key={note} className="mt-3 flex gap-2 text-[13px] text-warn">
              <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              {note}
            </p>
          ))}
        </>
      )}

      {error && (
        <p role="alert" className="mt-4 flex gap-2 text-[13px] text-danger">
          <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          {error}
        </p>
      )}

      <div className="mt-8 flex items-center gap-3">
        <Button variant="primary" className="h-11 px-6 text-[15px]" disabled={!canContinue || saving} onClick={() => void confirm()}>
          {saving && <Spinner />}
          {continueLabel}
        </Button>
        <Button variant="secondary" disabled={waiting} icon={<RotateCw className="h-3.5 w-3.5" />} onClick={() => checks.forEach((c) => void runCheck(c.id))}>
          Check again
        </Button>
        {!canContinue && !waiting && <span className="text-[13px] text-fg-muted">Azure OpenAI has to work before Forge can start.</span>}
      </div>
    </div>
  );
}

function CheckRow({ check, row, onRetry }: { check: CheckInfo; row: Row | undefined; onRetry: () => void }) {
  const result = row?.result ?? null;
  const running = row?.running ?? true;
  return (
    <div className="flex items-start gap-3 px-5 py-4">
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
          <span className="font-semibold">{check.label}</span>
          {check.optional && <Badge>Optional</Badge>}
        </div>
        <div className="text-[12.5px] text-fg-muted">{check.purpose}</div>
        {result && (
          <div className="mt-1 break-words text-[13px]">
            {result.detail}
            {running && <span className="text-fg-muted"> (earlier result, checking again…)</span>}
          </div>
        )}
        {result && !running && result.hint && <div className="mt-0.5 text-[12.5px] text-fg-muted">{result.hint}</div>}
        {result?.checked_at && !running && <div className="mt-0.5 text-[11.5px] text-fg-muted">Checked {timeAgo(result.checked_at)}</div>}
        {!result && running && <div className="mt-1 text-[13px] text-fg-muted">Checking…</div>}
      </div>
      <Button variant="ghost" size="sm" disabled={running} onClick={onRetry} icon={<RotateCw className="h-3.5 w-3.5" />}>
        Retry
      </Button>
    </div>
  );
}

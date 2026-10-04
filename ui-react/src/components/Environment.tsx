// The Environment drawer (D-186, D-204): it reads what the .env file holds (the server never sends a value) and
// lets the user test each connection on its own, or all at once, with a clear Connected / Failed and the reason.
// Nothing is tested until the user asks (and the two optional tools only after a yes, D-201). Then Forge proposes
// which model serves each role from what answered; the user confirms and the choice is remembered per machine.
// It opens by itself on the New project screen and from "Environment" in the top bar.
import { AlertTriangle, CheckCircle2, CircleDashed, FileText, Info, Minus, RotateCw, X, XCircle } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { api, cx, timeAgo } from "../lib";
import type { CheckInfo, CheckResultView, EnvironmentOverview, ModelPlan } from "../types";
import { Badge, Button, IconButton, Select, Spinner } from "./ui";
import { YesNo } from "./YesNo";

type Row = { result: CheckResultView | null; running: boolean };

const ROLE_LABEL: Record<string, string> = { kb_builder: "Knowledge builder", judge: "Judge (evals)", fallback: "Fallback" };

/** Tools the user may not have (Tesseract, Gemini) are tested only after a yes (D-201). */
const shouldRun = (check: CheckInfo, answers: Record<string, boolean>) => !check.ask || answers[check.id] === true;

/** Rows that are a connection say "Connected"; the others say "Working". */
const CONNECTIONS = new Set(["azure", "postgres_local", "postgres_dev", "gemini"]);

const notInUse = (id: string, answer: boolean | undefined): CheckResultView => ({
  id,
  status: "off",
  detail: answer === false ? "Not in use." : "Answer the question to test it.",
  hint: "",
  models: {},
});

function statusWord(check: CheckInfo, row: Row | undefined): { text: string; tone: string } {
  if (row?.running) return { text: "Testing…", tone: "text-fg-muted" };
  const status = row?.result?.status;
  if (!status) return { text: "Not tested yet", tone: "text-fg-muted" };
  if (status === "ok") return { text: CONNECTIONS.has(check.id) ? "Connected" : "Working", tone: "text-ok" };
  if (status === "warn") return { text: "Warning", tone: "text-warn" };
  if (status === "off") return { text: "Not in use", tone: "text-fg-muted" };
  return { text: "Failed", tone: "text-danger" };
}

export function EnvironmentDrawer({ onClose, onOpenGuide }: { onClose: () => void; onOpenGuide: () => void }) {
  const [checks, setChecks] = useState<CheckInfo[]>([]);
  const [rows, setRows] = useState<Record<string, Row>>({});
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
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
        setRows((prev) => ({ ...prev, [id]: { result: { id, status: "fail", detail, hint: "Test again.", models: {} }, running: false } }));
      }
    },
    [adopt],
  );

  // Opening the drawer tests nothing: it shows the last results, each with when it was tested.
  useEffect(() => {
    api<EnvironmentOverview>("/api/environment")
      .then((overview) => {
        const said = overview.saved.answers ?? {};
        setChecks(overview.checks);
        setAnswers(said);
        setRows(
          Object.fromEntries(
            overview.checks.map((c) => [
              c.id,
              { result: shouldRun(c, said) ? (overview.saved.results[c.id] ?? null) : notInUse(c.id, said[c.id]), running: false },
            ]),
          ),
        );
        adopt(overview.plan);
      })
      .catch((failure: Error) => setError(failure.message));
  }, [adopt]);

  const answer = async (check: CheckInfo, enabled: boolean) => {
    setAnswers((prev) => ({ ...prev, [check.id]: enabled }));
    try {
      await api("/api/environment/answer", { method: "POST", body: { check: check.id, enabled } });
    } catch (failure) {
      setError((failure as Error).message);
      return;
    }
    if (enabled) void runCheck(check.id);
    else setRows((prev) => ({ ...prev, [check.id]: { result: notInUse(check.id, false), running: false } }));
  };

  const azure = rows["azure"];
  const testing = checks.some((c) => rows[c.id]?.running);
  const azureTested = azure?.result?.status === "ok" || azure?.result?.status === "warn";
  const canSave = !testing && azureTested && Boolean(choice["coder"]) && plan !== null;
  const testAll = () => checks.filter((c) => shouldRun(c, answers)).forEach((c) => void runCheck(c.id));

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
          <p className="mt-0.5 text-[12.5px] text-fg-muted">
            Forge uses the values in your .env file but cannot show them. Test a connection, or test all.
          </p>
          <button
            type="button"
            onClick={onOpenGuide}
            className="mt-1 inline-flex cursor-pointer items-center gap-1 text-[12.5px] font-semibold text-accent hover:underline"
          >
            <FileText className="h-3.5 w-3.5" aria-hidden /> Where is the file, and what goes in it?
          </button>
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
            <CheckRow
              key={check.id}
              check={check}
              row={rows[check.id]}
              onTest={() => void runCheck(check.id)}
              answer={answers[check.id]}
              onAnswer={(enabled) => void answer(check, enabled)}
              onOpenGuide={onOpenGuide}
            />
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
          <Button variant="secondary" disabled={testing} icon={<RotateCw className="h-3.5 w-3.5" />} onClick={testAll}>
            Test all
          </Button>
        </div>
        {!canSave && !testing && plan && <p className="mt-2 text-[12px] text-fg-muted">Test Azure OpenAI first: models can only be saved once it answers.</p>}
      </div>
    </aside>
  );
}

function CheckRow({
  check,
  row,
  onTest,
  answer,
  onAnswer,
  onOpenGuide,
}: {
  check: CheckInfo;
  row: Row | undefined;
  onTest: () => void;
  answer?: boolean;
  onAnswer?: (enabled: boolean) => void;
  onOpenGuide: () => void;
}) {
  const result = row?.result ?? null;
  const running = row?.running ?? false;
  const word = statusWord(check, row);
  const [showSteps, setShowSteps] = useState(false);
  const steps = result?.steps ?? [];
  return (
    <div className="flex items-start gap-3 px-5 py-3.5" data-check={check.id}>
      <div className="mt-0.5 w-5 shrink-0" aria-live="polite">
        {running ? (
          <Spinner className="text-fg-muted" />
        ) : result?.status === "ok" ? (
          <CheckCircle2 className="h-5 w-5 text-ok" aria-hidden />
        ) : result?.status === "warn" ? (
          <AlertTriangle className="h-5 w-5 text-warn" aria-hidden />
        ) : result?.status === "off" ? (
          <Minus className="h-5 w-5 text-fg-muted" aria-hidden />
        ) : result ? (
          <XCircle className="h-5 w-5 text-danger" aria-hidden />
        ) : (
          <CircleDashed className="h-5 w-5 text-fg-muted" aria-hidden />
        )}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-[13.5px] font-semibold">{check.label}</span>
          {check.optional && <Badge>Optional</Badge>}
          {!running && steps.length > 0 && (
            <button
              type="button"
              aria-label={`How to fix ${check.label}`}
              aria-expanded={showSteps}
              onClick={() => setShowSteps((open) => !open)}
              className="cursor-pointer text-accent hover:opacity-80"
            >
              <Info className="h-4 w-4" aria-hidden />
            </button>
          )}
          <span data-testid="status" className={cx("ml-auto text-[12px] font-semibold", word.tone)}>
            {word.text}
          </span>
        </div>
        <div className="text-[12px] text-fg-muted">{check.purpose}</div>
        {check.ask && onAnswer && (
          <div className="mt-2">
            <YesNo question={check.ask} answer={answer} onAnswer={onAnswer} />
          </div>
        )}
        {result && (
          <div className="mt-1 break-words text-[12.5px]">
            {result.detail}
            {running && <span className="text-fg-muted"> (testing again…)</span>}
          </div>
        )}
        {result && !running && result.hint && <div className="mt-0.5 text-[12px] text-fg-muted">{result.hint}</div>}
        {result && !running && check.id === "azure" && (result.missing?.length ?? 0) > 0 && (
          <button
            type="button"
            onClick={onOpenGuide}
            className="mt-1 cursor-pointer text-[12px] font-semibold text-accent hover:underline"
          >
            Open the setup guide
          </button>
        )}
        {!running && showSteps && steps.length > 0 && (
          <ol data-testid="steps" className="mt-2 list-decimal space-y-1 rounded-md border border-border bg-surface py-2 pl-7 pr-3 text-[12px] text-fg-muted">
            {steps.map((step) => (
              <li key={step}>{step}</li>
            ))}
          </ol>
        )}
        {result?.checked_at && !running && result.status !== "off" && <div className="mt-0.5 text-[11px] text-fg-muted">Tested {timeAgo(result.checked_at)}</div>}
      </div>
      <Button
        size="sm"
        variant="secondary"
        aria-label={`Test ${check.label}`}
        disabled={running || (Boolean(check.ask) && answer !== true)}
        onClick={onTest}
      >
        Test
      </Button>
    </div>
  );
}

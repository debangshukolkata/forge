// The settings-file guide (D-204): shown on the first run, and later from the Environment drawer. Forge reads its
// keys and connections from one .env file. This page says where it is, which names it reads and what each should
// hold, offers a template to copy, and checks which names are filled in. Nothing is typed into this page, and
// it cannot see a key: the server tells it only whether a name is filled in.
import { AlertTriangle, ArrowLeft, CheckCircle2, Copy, FileText, Lock, RotateCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, useCopy } from "../lib";
import type { CheckInfo, EnvironmentOverview, SetupGuideInfo } from "../types";
import { Headline, Tagline } from "./landing";
import { Badge, Button, Card, Spinner } from "./ui";
import { YesNo } from "./YesNo";

export function SetupGuide({ first, onDone, onBack }: { first: boolean; onDone: () => void; onBack?: () => void }) {
  const [guide, setGuide] = useState<SetupGuideInfo | null>(null);
  const [asks, setAsks] = useState<CheckInfo[]>([]);
  const [answers, setAnswers] = useState<Record<string, boolean>>({});
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const [copiedPath, copyPath] = useCopy();
  const [copiedTemplate, copyTemplate] = useCopy();

  const load = useCallback(async () => {
    setChecking(true);
    try {
      setGuide(await api<SetupGuideInfo>("/api/setup"));
      setError("");
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setChecking(false);
    }
  }, []);

  useEffect(() => {
    void load();
    api<EnvironmentOverview>("/api/environment")
      .then((overview) => {
        setAsks(overview.checks.filter((c) => c.ask));
        setAnswers(overview.saved.answers ?? {});
      })
      .catch(() => undefined);
  }, [load]);

  const answer = async (check: CheckInfo, enabled: boolean) => {
    setAnswers((prev) => ({ ...prev, [check.id]: enabled }));
    try {
      await api("/api/environment/answer", { method: "POST", body: { check: check.id, enabled } });
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  if (guide === null) {
    return (
      <div className="flex h-full items-center justify-center text-fg-muted">{error ? <span role="alert">{error}</span> : <Spinner />}</div>
    );
  }
  const requiredMissing = guide.missing;
  const ready = requiredMissing.length === 0;

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10">
      {onBack && (
        <Button variant="ghost" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={onBack} className="-ml-3 mb-4">
          Back
        </Button>
      )}
      <Headline className="!text-[34px]">{first ? "Set up Forge." : "Forge's settings file."}</Headline>
      <Tagline className="mt-2">
        Forge reads its keys and connections from one file. Edit it there: nothing is typed into this page.
      </Tagline>

      <Card className="mt-6 p-5">
        <div className="flex items-center gap-2">
          <FileText className="h-4 w-4 text-fg-muted" aria-hidden />
          <h2 className="text-[15px] font-semibold">Where the file is</h2>
          {guide.exists ? <Badge tone="ok">File found</Badge> : <Badge tone="warn">Not created yet</Badge>}
        </div>
        <div className="mt-3 flex items-center gap-2 rounded-lg bg-raised px-3 py-2">
          <code data-testid="env-path" className="min-w-0 flex-1 break-all font-mono text-[12.5px]">
            {guide.path}
          </code>
          <Button size="sm" variant="secondary" icon={<Copy className="h-3.5 w-3.5" />} onClick={() => copyPath(guide.path)}>
            {copiedPath ? "Copied" : "Copy path"}
          </Button>
        </div>
        <p className="mt-2 text-[12.5px] text-fg-muted">
          {guide.exists ? "Open it in a text editor such as Notepad and change the lines below." : "Create it in a text editor such as Notepad, with exactly this name, and paste the template below."}
          {guide.overridden && " This location comes from the FORGE_ENV_FILE variable."}
        </p>
      </Card>

      <div role="note" className="mt-4 flex gap-3 rounded-[18px] border border-info/40 bg-info-soft px-4 py-3 text-[13px]">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-info" aria-hidden />
        <p>
          <span className="font-semibold">This page cannot see your keys.</span> It only checks which names in the file are filled in, and
          Forge never shows a key or sends one to your browser. Double-check the values yourself in the file.
        </p>
      </div>

      <Card className="mt-4 p-5">
        <div className="flex items-center justify-between gap-2">
          <h2 className="text-[15px] font-semibold">Template</h2>
          <Button size="sm" variant="primary" icon={<Copy className="h-3.5 w-3.5" />} onClick={() => copyTemplate(guide.template)}>
            {copiedTemplate ? "Copied" : "Copy template"}
          </Button>
        </div>
        <ol className="mt-2 list-decimal space-y-0.5 pl-5 text-[12.5px] text-fg-muted">
          <li>Copy the template and paste it into the file.</li>
          <li>Replace each &lt;placeholder&gt; with your value, and delete the lines you do not need.</li>
          <li>Save the file, then press &ldquo;Check the file&rdquo; below.</li>
        </ol>
        <pre
          aria-label="Template"
          className="mt-3 max-h-72 overflow-auto rounded-lg border border-border bg-raised p-3 font-mono text-[12px] leading-[1.55] whitespace-pre"
        >
          {guide.template}
        </pre>
      </Card>

      <Card className="mt-4 divide-y divide-border">
        {guide.groups.map((group) => (
          <div key={group.title} className="px-5 py-4">
            <div className="flex items-center gap-2">
              <h3 className="text-[14px] font-semibold">{group.title}</h3>
              <Badge tone={group.required ? "warn" : "neutral"}>{group.required ? "Required" : "Optional"}</Badge>
            </div>
            <p className="mt-0.5 text-[12.5px] text-fg-muted">{group.note}</p>
            <ul className="mt-2 space-y-1.5">
              {guide.variables
                .filter((variable) => variable.group === group.title)
                .map((variable) => (
                  <li key={variable.name} data-variable={variable.name} data-filled={variable.filled ? "yes" : "no"} className="flex items-start gap-2 text-[12.5px]">
                    {variable.filled ? (
                      <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-ok" aria-label="Filled in" />
                    ) : variable.required ? (
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-label="Missing" />
                    ) : (
                      <span className="mt-0.5 h-4 w-4 shrink-0 text-center text-fg-muted" aria-label="Not set">
                        –
                      </span>
                    )}
                    <span className="min-w-0 flex-1">
                      <code className="font-mono text-[12px] font-semibold">{variable.name}</code>
                      <span className="ml-2 text-fg-muted">{variable.why}</span>
                      <span className="block break-all font-mono text-[11.5px] text-fg-muted">= {variable.expects}</span>
                    </span>
                    <span className="shrink-0 text-[11.5px] text-fg-muted">{variable.filled ? "filled in" : variable.required ? "missing" : "not set"}</span>
                  </li>
                ))}
            </ul>
          </div>
        ))}
      </Card>

      {asks.length > 0 && (
        <Card className="mt-4 space-y-3 p-5">
          <h2 className="text-[15px] font-semibold">Optional tools</h2>
          <p className="text-[12.5px] text-fg-muted">Forge tests these only if you say yes. You can change the answers later on the Environment panel.</p>
          {asks.map((check) => (
            <YesNo key={check.id} question={check.ask ?? ""} answer={answers[check.id]} onAnswer={(enabled) => void answer(check, enabled)} />
          ))}
        </Card>
      )}

      {error && (
        <p role="alert" className="mt-4 text-[13px] text-danger">
          {error}
        </p>
      )}

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <Button variant="secondary" disabled={checking} icon={checking ? <Spinner /> : <RotateCw className="h-3.5 w-3.5" />} onClick={() => void load()}>
          Check the file
        </Button>
        <Button variant="primary" className="h-11 px-6 text-[15px]" disabled={!ready} onClick={onDone}>
          {first ? "Continue to the connection tests" : "Done"}
        </Button>
        {first && (
          <Button variant="ghost" onClick={onDone}>
            Skip for now
          </Button>
        )}
        <span role="status" className="text-[13px] text-fg-muted">
          {ready ? "All required names are filled in." : `Still missing: ${requiredMissing.join(", ")}`}
        </span>
      </div>
    </div>
  );
}

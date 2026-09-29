// Guided first-run setup (D-145/D-146): shown only when required Azure OpenAI values are missing from
// Forge's own .env. The field list comes from the backend's own required-names computation (doctor.py's
// check_secrets), never a hardcoded duplicate here. Submitting writes the .env and immediately runs a live
// connectivity check in the same request/response cycle — no restart, no extra "you're all set" click.
import { AlertTriangle, CheckCircle2, KeyRound, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../lib";
import type { DoctorResult } from "../types";
import { Button, Card, Field, Input, Spinner } from "./ui";

export function Setup({ missing, onDone }: { missing: string[]; onDone: () => void }) {
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [results, setResults] = useState<DoctorResult[] | null>(null);

  const set = (name: string) => (event: React.ChangeEvent<HTMLInputElement>) =>
    setValues((prev) => ({ ...prev, [name]: event.target.value }));

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    setResults(null);
    try {
      const filled = Object.fromEntries(Object.entries(values).filter(([, v]) => v.trim()));
      if (Object.keys(filled).length > 0) {
        await api("/api/setup/secrets", { method: "POST", body: { values: filled } });
      }
      const doctor = await api<DoctorResult[]>("/api/doctor?offline=false");
      setResults(doctor);
      const blocking = doctor.some((r) => r.name === "Secrets" && r.status === "fail");
      if (!blocking) onDone(); // success (or the user chose to skip): proceed straight into the app
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-2xl px-6 py-10">
      <div className="mb-1 flex items-center gap-2">
        <KeyRound className="h-5 w-5 text-fg-muted" aria-hidden />
        <h1 className="text-[22px] font-semibold tracking-tight">Set up Forge</h1>
      </div>
      <p className="mt-1 text-fg-muted">
        Forge needs Azure OpenAI details before it can talk to a model. Enter them below, or skip and add them
        to the .env file later.
      </p>

      <Card className="mt-6 p-6">
        <form onSubmit={submit} className="space-y-5" noValidate>
          {missing.map((name) => (
            <Field key={name} label={name}>
              <Input
                type={name.toUpperCase().includes("KEY") ? "password" : "text"}
                autoComplete="off"
                value={values[name] ?? ""}
                onChange={set(name)}
                placeholder={name}
              />
            </Field>
          ))}

          {error && (
            <div role="alert" className="flex gap-2 rounded-md border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{error}</span>
            </div>
          )}

          {results && (
            <ul className="space-y-1.5 rounded-md border border-border bg-raised p-3">
              {results.map((result) => (
                <li key={result.name} className="flex gap-2 text-[13px]">
                  {result.status === "ok" ? (
                    <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-accent" aria-label="OK" />
                  ) : result.status === "warn" ? (
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-warn" aria-label="Warning" />
                  ) : (
                    <XCircle className="mt-0.5 h-4 w-4 shrink-0 text-danger" aria-label="Failed" />
                  )}
                  <span>
                    <span className="font-medium">{result.name}</span>
                    <span className="text-fg-muted"> — {result.detail}</span>
                  </span>
                </li>
              ))}
            </ul>
          )}

          <div className="flex items-center gap-3">
            <Button type="submit" variant="primary" disabled={busy}>
              {busy && <Spinner />}
              Save and test connection
            </Button>
            <Button type="button" variant="ghost" disabled={busy} onClick={onDone}>
              Skip for now
            </Button>
          </div>
        </form>
      </Card>
    </div>
  );
}

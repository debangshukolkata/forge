// Enter or replace the Azure OpenAI values from the Environment drawer (D-200). They go to Forge's own .env file on
// this computer through /api/setup/secrets, which accepts only the names Forge itself requires and never sends a
// value back: the fields start empty, and a field left blank keeps the value that is already saved.
import { KeyRound, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../lib";
import { Button, Input, Spinner } from "./ui";

export function AzureKeys({ missing, onSaved }: { missing: string[]; onSaved: () => void }) {
  const [names, setNames] = useState<string[] | null>(null); // set when the user asks to replace values
  const [values, setValues] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const fields = missing.length > 0 ? missing : names;
  const replacing = missing.length === 0 && names !== null;

  const startReplacing = async () => {
    setError("");
    try {
      setNames((await api<{ required: string[] }>("/api/setup")).required);
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const filled = Object.fromEntries(Object.entries(values).filter(([, value]) => value.trim()));
      if (Object.keys(filled).length > 0) await api("/api/setup/secrets", { method: "POST", body: { values: filled } });
      setValues({});
      setNames(null);
      onSaved();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };

  if (fields === null) {
    return (
      <div className="mt-2">
        <Button size="sm" variant="ghost" icon={<KeyRound className="h-3.5 w-3.5" />} onClick={() => void startReplacing()}>
          Update keys
        </Button>
        {error && (
          <p role="alert" className="mt-1 text-[12px] text-danger">
            {error}
          </p>
        )}
      </div>
    );
  }

  return (
    <form onSubmit={submit} noValidate className="mt-3 space-y-2.5 rounded-xl border border-border p-3" aria-label="Azure OpenAI values">
      <p className="text-[12px] text-fg-muted">
        {replacing ? "Leave a field empty to keep what is saved." : "Enter the missing values."} They are saved in the .env file on this
        computer and never shown again.
      </p>
      {fields.map((name) => (
        <label key={name} className="block">
          <span className="mb-1 block font-mono text-[11.5px] font-semibold">{name}</span>
          <Input
            type={name.toUpperCase().includes("KEY") ? "password" : "text"}
            autoComplete="off"
            spellCheck={false}
            value={values[name] ?? ""}
            onChange={(event) => setValues((prev) => ({ ...prev, [name]: event.target.value }))}
            placeholder={replacing ? "unchanged" : name}
            aria-label={name}
          />
        </label>
      ))}
      {error && (
        <p role="alert" className="flex gap-1.5 text-[12px] text-danger">
          <XCircle className="mt-0.5 h-3.5 w-3.5 shrink-0" aria-hidden />
          {error}
        </p>
      )}
      <div className="flex gap-2">
        <Button type="submit" variant="primary" size="sm" disabled={busy || !Object.values(values).some((v) => v.trim())}>
          {busy && <Spinner />}
          Save and test
        </Button>
        {replacing && (
          <Button
            type="button"
            size="sm"
            variant="ghost"
            onClick={() => {
              setNames(null);
              setValues({});
              setError("");
            }}
          >
            Cancel
          </Button>
        )}
      </div>
    </form>
  );
}

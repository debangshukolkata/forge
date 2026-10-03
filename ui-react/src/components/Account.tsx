// The account screen (D-184): who is signed in, and a way to change the password without deleting
// account.json. Changing it signs every other browser out and keeps this one signed in.
import { ArrowLeft, CheckCircle2, XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../lib";
import { Headline, Tagline } from "./landing";
import { Button, Card, Field, Input, Spinner } from "./ui";

const MIN_LENGTH = 8; // the same minimum the server enforces

export function Account({ user, onBack }: { user: string | null; onBack: () => void }) {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [done, setDone] = useState(false);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setDone(false);
    if (next !== again) {
      setError("The two new passwords don't match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/api/auth/password", { method: "POST", body: { current, new: next } });
      setCurrent("");
      setNext("");
      setAgain("");
      setDone(true);
    } catch (failure) {
      setError((failure as Error).message);
      setCurrent("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mx-auto w-full max-w-xl px-6 py-10">
      <Button variant="ghost" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={onBack} className="-ml-3 mb-4">
        Back
      </Button>
      <Headline className="!text-[34px]">Your account.</Headline>
      <Tagline className="mt-2">
        Signed in as <span className="font-semibold text-fg">{user ?? "you"}</span>. The account is kept on this computer only.
      </Tagline>

      <Card className="mt-6 p-6">
        <h2 className="text-[17px] font-semibold tracking-[-0.37px]">Change password</h2>
        <form onSubmit={submit} noValidate className="mt-4 space-y-4">
          <Field label="Current password">
            <Input type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />
          </Field>
          <Field label="New password" hint={`At least ${MIN_LENGTH} characters.`}>
            <Input type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} />
          </Field>
          <Field label="Repeat the new password">
            <Input type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
          </Field>
          {error && (
            <div role="alert" className="flex gap-2 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{error}</span>
            </div>
          )}
          {done && (
            <div role="status" className="flex gap-2 rounded-lg border border-ok/40 bg-ok-soft px-3 py-2 text-[13px] text-ok">
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>Password changed. Any other browser that was signed in has been signed out.</span>
            </div>
          )}
          <Button type="submit" variant="primary" disabled={busy || !current || !next || !again}>
            {busy && <Spinner />}
            Change password
          </Button>
        </form>
      </Card>
    </div>
  );
}

// The landing page (D-184): sign in, or on the very first run create the one local account. The account only
// keeps other people on this computer out of the projects; it never leaves the machine.
import { XCircle } from "lucide-react";
import { useState, type FormEvent } from "react";
import { api } from "../lib";
import { Brand, Headline, Tagline, Tile } from "./landing";
import { Button, Field, Input, Spinner } from "./ui";

export function Login({ configured, onSignedIn }: { configured: boolean; onSignedIn: (user: string) => void }) {
  const [user, setUser] = useState("");
  const [password, setPassword] = useState("");
  const [again, setAgain] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const creating = !configured;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (creating && password !== again) {
      setError("The two passwords don't match.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api<{ user: string }>(creating ? "/api/auth/register" : "/api/auth/login", {
        method: "POST",
        body: { user, password },
      });
      onSignedIn(result.user);
    } catch (failure) {
      setError((failure as Error).message);
      setPassword("");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-full flex-col">
      <Tile dark className="px-6 py-14 text-center sm:py-20">
        <Brand className="mb-8 justify-center" />
        <Headline>{creating ? "Welcome to Forge." : "Sign in to Forge."}</Headline>
        <Tagline className="mx-auto mt-3 max-w-md">
          {creating
            ? "Create the account for this computer. It keeps your projects and keys private."
            : "A coding agent that works in its own workspace and hands you only the changed files."}
        </Tagline>
      </Tile>
      <Tile className="flex-1 !bg-bg px-6 py-12">
        <form onSubmit={submit} noValidate className="mx-auto w-full max-w-sm space-y-4">
          <Field label="User ID">
            <Input required autoFocus autoComplete="username" value={user} onChange={(e) => setUser(e.target.value)} />
          </Field>
          <Field label="Password" hint={creating ? "At least 8 characters." : undefined}>
            <Input
              required
              type="password"
              autoComplete={creating ? "new-password" : "current-password"}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </Field>
          {creating && (
            <Field label="Repeat the password">
              <Input required type="password" autoComplete="new-password" value={again} onChange={(e) => setAgain(e.target.value)} />
            </Field>
          )}
          {error && (
            <div role="alert" className="flex gap-2 rounded-lg border border-danger/40 bg-danger-soft px-3 py-2 text-[13px] text-danger">
              <XCircle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
              <span>{error}</span>
            </div>
          )}
          <Button type="submit" variant="primary" className="h-11 w-full text-[15px]" disabled={busy || !user.trim() || !password}>
            {busy && <Spinner />}
            {creating ? "Create account" : "Sign in"}
          </Button>
          <p className="text-center text-[12px] text-fg-muted">
            {creating
              ? "Stored only on this computer."
              : "Forgot the password? Delete account.json in the .forge folder and start Forge again. Your projects are kept."}
          </p>
        </form>
      </Tile>
    </div>
  );
}

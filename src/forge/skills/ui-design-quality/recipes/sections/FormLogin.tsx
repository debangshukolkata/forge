// Sign-in form: a narrow, centred form with an e-mail field, a password field with a show/hide button, a remember-me checkbox, a forgotten-password link
// and one button. Validates on submit and shows a message above the fields when the sign-in is refused; `onSubmit` returns an error text or nothing
// and may be async. For a real app wire it to the back end; never keep a password in the page state longer than the submit.
import { useState, type FormEvent } from "react";

export default function FormLogin({
  title = "Sign in",
  text = "Welcome back. Enter your details to continue.",
  forgotHref = "#forgot",
  createHref = "#signup",
  onSubmit,
}: {
  title?: string;
  text?: string;
  forgotHref?: string;
  createHref?: string;
  onSubmit?: (credentials: { email: string; password: string; remember: boolean }) => Promise<string | void> | string | void;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(true);
  const [show, setShow] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const found: typeof errors = {};
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())) found.email = "Enter the e-mail address you signed up with.";
    if (password.length < 8) found.password = "Passwords have at least 8 characters.";
    setErrors(found);
    if (found.email || found.password) return;
    setBusy(true);
    const refused = await onSubmit?.({ email: email.trim(), password, remember });
    setBusy(false);
    if (refused) setErrors({ form: refused });
  };
  return (
    <section className="mx-auto max-w-md px-4 py-16 sm:px-6 md:py-24">
      <h1 className="text-3xl font-semibold sm:text-4xl">{title}</h1>
      <p className="mt-3 text-ink-700">{text}</p>
      <form onSubmit={submit} noValidate className="mt-8 space-y-5">
        <p role="alert" className="min-h-5 text-sm font-semibold text-danger">{errors.form ?? ""}</p>
        <div>
          <label htmlFor="login-email" className="mb-1 block text-sm font-semibold text-ink-900">E-mail</label>
          <input id="login-email" type="email" autoComplete="username" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(errors.email)} aria-describedby="login-email-error" className="field" />
          <p id="login-email-error" role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors.email ?? ""}</p>
        </div>
        <div>
          <div className="mb-1 flex items-baseline justify-between">
            <label htmlFor="login-password" className="text-sm font-semibold text-ink-900">Password</label>
            <a href={forgotHref} className="text-sm font-medium text-brand-600 underline underline-offset-4">Forgotten it?</a>
          </div>
          <div className="relative">
            <input id="login-password" type={show ? "text" : "password"} autoComplete="current-password" value={password} onChange={(event) => setPassword(event.target.value)} aria-invalid={Boolean(errors.password)} aria-describedby="login-password-error" className="field pr-20" />
            <button type="button" onClick={() => setShow(!show)} aria-pressed={show} className="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg px-3 py-2 text-sm font-semibold text-ink-700 hover:bg-ink-100">
              {show ? "Hide" : "Show"}
            </button>
          </div>
          <p id="login-password-error" role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors.password ?? ""}</p>
        </div>
        <label className="flex items-center gap-3 text-sm text-ink-900">
          <input type="checkbox" checked={remember} onChange={(event) => setRemember(event.target.checked)} className="h-5 w-5 accent-brand-600" />
          Keep me signed in on this device
        </label>
        <button type="submit" disabled={busy} className="btn-primary w-full">{busy ? "Signing in" : "Sign in"}</button>
      </form>
      <p className="mt-6 text-center text-sm text-ink-700">
        New here? <a href={createHref} className="font-semibold text-brand-600 underline underline-offset-4">Create an account</a>
      </p>
    </section>
  );
}

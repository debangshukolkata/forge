// Sign-up hero: a headline, one sentence and an inline e-mail field with a button, so the single action happens right in the first view.
// The field is a real labelled input and validates on submit; `onSubmit` receives the address (send it wherever the product needs).
import { useState, type FormEvent } from "react";

export default function HeroSignup({
  eyebrow = "Early access",
  title = "Know where your money went before the month ends.",
  text = "Ledgerly reads your bank feed and shows a plain weekly summary: what came in, what went out and what is about to. No charts you have to decode.",
  button = "Join the waiting list",
  note = "One e-mail when your place opens. Nothing else.",
  onSubmit,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  button?: string;
  note?: string;
  onSubmit?: (email: string) => void;
}) {
  const [email, setEmail] = useState("");
  const [state, setState] = useState<"idle" | "invalid" | "done">("idle");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())) return setState("invalid");
    setState("done");
    onSubmit?.(email.trim());
  };
  return (
    <section id="top" className="mx-auto max-w-3xl px-4 py-16 text-center sm:px-6 md:py-28">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="mt-4 text-4xl font-semibold leading-[1.05] sm:text-6xl">{title}</h1>
      <p className="mx-auto mt-6 max-w-xl text-lg leading-relaxed text-ink-700">{text}</p>
      {state === "done" ? (
        <p role="status" className="mt-10 text-lg font-semibold text-ok">You are on the list. Check your inbox for a confirmation.</p>
      ) : (
        <form onSubmit={submit} noValidate className="mx-auto mt-10 flex max-w-lg flex-col gap-3 sm:flex-row">
          <label htmlFor="hero-signup-email" className="sr-only">E-mail address</label>
          <input
            id="hero-signup-email"
            type="email"
            autoComplete="email"
            placeholder="you@example.com"
            value={email}
            onChange={(event) => {
              setEmail(event.target.value);
              setState("idle");
            }}
            aria-invalid={state === "invalid"}
            aria-describedby="hero-signup-note"
            className="field flex-1"
          />
          <button type="submit" className="btn-primary">{button}</button>
        </form>
      )}
      <p id="hero-signup-note" className={`mt-4 text-sm ${state === "invalid" ? "text-danger" : "text-ink-500"}`}>
        {state === "invalid" ? "That does not look like an e-mail address." : note}
      </p>
    </section>
  );
}

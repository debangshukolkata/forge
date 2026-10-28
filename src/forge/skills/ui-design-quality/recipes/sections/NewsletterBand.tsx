// Newsletter band: a slim full-width band with one sentence on the left and an inline e-mail field on the right; goes above a footer.
// A real labelled input with validation on submit; `onSubmit` receives the address.
import { useState, type FormEvent } from "react";

export default function NewsletterBand({
  title = "One short letter a month.",
  text = "New classes, the firing calendar and the occasional piece for sale. No more than twelve a year.",
  button = "Subscribe",
  onSubmit,
}: {
  title?: string;
  text?: string;
  button?: string;
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
    <section className="border-y border-ink-200 bg-white">
      <div className="mx-auto grid max-w-6xl gap-6 px-4 py-10 sm:px-6 md:grid-cols-2 md:items-center md:py-12">
        <div>
          <h2 className="text-2xl font-semibold">{title}</h2>
          <p className="mt-2 max-w-md text-ink-700">{text}</p>
        </div>
        {state === "done" ? (
          <p role="status" className="font-semibold text-ok">Thank you. Check your inbox to confirm.</p>
        ) : (
          <form onSubmit={submit} noValidate>
            <div className="flex flex-col gap-3 sm:flex-row">
              <label htmlFor="newsletter-email" className="sr-only">E-mail address</label>
              <input
                id="newsletter-email"
                type="email"
                autoComplete="email"
                placeholder="you@example.com"
                value={email}
                onChange={(event) => {
                  setEmail(event.target.value);
                  setState("idle");
                }}
                aria-invalid={state === "invalid"}
                aria-describedby="newsletter-error"
                className="field flex-1"
              />
              <button type="submit" className="btn-primary">{button}</button>
            </div>
            <p id="newsletter-error" role="alert" className="mt-2 min-h-5 text-sm text-danger">{state === "invalid" ? "That does not look like an e-mail address." : ""}</p>
          </form>
        )}
      </div>
    </section>
  );
}

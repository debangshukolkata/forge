// Contact or sign-up form with visible labels, inline error messages, a disabled state while sending and a success
// message that replaces the form. `onSubmit` receives the values and may be async; throw to show a failure message.
import { useState, type FormEvent } from "react";

export default function ContactForm({
  title = "Reserve your slot",
  text = "It takes under a minute. We email your confirmation and a reminder the day before.",
  submitLabel = "Confirm my slot",
  successTitle = "You are booked.",
  successText = "Check your inbox for the confirmation. See you there!",
  onSubmit,
}: {
  title?: string;
  text?: string;
  submitLabel?: string;
  successTitle?: string;
  successText?: string;
  onSubmit?: (values: { name: string; email: string }) => Promise<void> | void;
}) {
  const [errors, setErrors] = useState<{ name?: string; email?: string; form?: string }>({});
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");

  async function handle(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const name = String(data.get("name") ?? "").trim();
    const email = String(data.get("email") ?? "").trim();
    const next: typeof errors = {};
    if (name.length < 2) next.name = "Please enter your full name.";
    if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) next.email = "Enter an email like asha@example.org.";
    setErrors(next);
    if (next.name || next.email) return;
    setState("sending");
    try {
      await onSubmit?.({ name, email });
      setState("done");
    } catch {
      setErrors({ form: "Something went wrong. Please try again in a moment." });
      setState("idle");
    }
  }

  return (
    <section id="contact" className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 md:grid-cols-2 md:gap-16 md:py-24">
      <div>
        <h2 className="text-3xl font-semibold sm:text-4xl">{title}</h2>
        <p className="mt-4 text-lg text-ink-700">{text}</p>
      </div>
      <div className="card">
        {state === "done" ? (
          <div role="status" className="py-6 text-center">
            <h3 className="text-2xl font-semibold">{successTitle}</h3>
            <p className="mt-2 text-ink-700">{successText}</p>
          </div>
        ) : (
          <form onSubmit={handle} noValidate className="space-y-5">
            <div>
              <label htmlFor="cf-name" className="mb-1.5 block text-sm font-medium text-ink-900">Full name</label>
              <input id="cf-name" name="name" autoComplete="name" className="field" aria-invalid={Boolean(errors.name)} aria-describedby={errors.name ? "cf-name-error" : undefined} />
              {errors.name && <p id="cf-name-error" className="mt-1.5 text-sm text-danger">{errors.name}</p>}
            </div>
            <div>
              <label htmlFor="cf-email" className="mb-1.5 block text-sm font-medium text-ink-900">Email</label>
              <input id="cf-email" name="email" type="email" autoComplete="email" className="field" aria-invalid={Boolean(errors.email)} aria-describedby={errors.email ? "cf-email-error" : undefined} />
              {errors.email && <p id="cf-email-error" className="mt-1.5 text-sm text-danger">{errors.email}</p>}
            </div>
            {errors.form && <p role="alert" className="text-sm text-danger">{errors.form}</p>}
            <button type="submit" disabled={state === "sending"} className="btn-primary w-full">
              {state === "sending" ? "Sending…" : submitLabel}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}

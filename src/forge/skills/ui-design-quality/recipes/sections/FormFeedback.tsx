// Feedback form: a one-to-five rating as a row of real radio buttons (keyboard and screen reader friendly), a comment box with a character count and
// an optional reply-to e-mail. Shows a thank-you after sending. `onSubmit` receives the rating, the comment and the e-mail.
import { useState, type FormEvent } from "react";

const LABELS = ["Poor", "Fair", "Good", "Very good", "Excellent"];

export default function FormFeedback({
  title = "How was your visit?",
  text = "Two minutes of your time helps us decide what to fix first.",
  maxLength = 500,
  onSubmit,
}: {
  title?: string;
  text?: string;
  maxLength?: number;
  onSubmit?: (feedback: { rating: number; comment: string; email: string }) => void;
}) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<{ rating?: string; email?: string }>({});
  const [done, setDone] = useState(false);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: typeof errors = {};
    if (rating === 0) found.rating = "Choose a rating from 1 to 5.";
    if (email.trim() && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(email.trim())) found.email = "That does not look like an e-mail address.";
    setErrors(found);
    if (Object.keys(found).length) return;
    setDone(true);
    onSubmit?.({ rating, comment: comment.trim(), email: email.trim() });
  };
  return (
    <section className="mx-auto max-w-xl px-4 py-16 sm:px-6 md:py-24">
      <h2 className="text-3xl font-semibold sm:text-4xl">{title}</h2>
      <p className="mt-3 text-ink-700">{text}</p>
      {done ? (
        <p role="status" className="mt-8 text-lg font-semibold text-ok">Thank you. Every comment is read by a person on the team.</p>
      ) : (
        <form onSubmit={submit} noValidate className="mt-8 space-y-6">
          <fieldset>
            <legend className="mb-2 text-sm font-semibold text-ink-900">Your rating</legend>
            <div className="grid grid-cols-5 gap-2">
              {LABELS.map((label, position) => (
                <label key={label} className={`cursor-pointer rounded-xl border px-2 py-3 text-center text-sm font-semibold transition focus-within:outline-2 focus-within:outline-offset-2 focus-within:outline-brand-600 ${rating === position + 1 ? "border-brand-600 bg-brand-50 text-brand-700" : "border-ink-300 text-ink-700 hover:border-ink-500"}`}>
                  <input type="radio" name="rating" value={position + 1} checked={rating === position + 1} onChange={() => setRating(position + 1)} className="sr-only" />
                  <span className="block font-display text-xl tabular-nums">{position + 1}</span>
                  <span className="mt-1 hidden text-xs sm:block">{label}</span>
                </label>
              ))}
            </div>
            <p role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors.rating ?? ""}</p>
          </fieldset>
          <div>
            <label htmlFor="feedback-comment" className="mb-1 block text-sm font-semibold text-ink-900">What stood out? <span className="font-normal text-ink-500">(optional)</span></label>
            <textarea id="feedback-comment" rows={5} maxLength={maxLength} value={comment} onChange={(event) => setComment(event.target.value)} className="field" />
            <p className="mt-1 text-right text-xs text-ink-500">{comment.length} / {maxLength}</p>
          </div>
          <div>
            <label htmlFor="feedback-email" className="mb-1 block text-sm font-semibold text-ink-900">E-mail, if you would like a reply <span className="font-normal text-ink-500">(optional)</span></label>
            <input id="feedback-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} aria-invalid={Boolean(errors.email)} aria-describedby="feedback-email-error" className="field" />
            <p id="feedback-email-error" role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors.email ?? ""}</p>
          </div>
          <button type="submit" className="btn-primary">Send feedback</button>
        </form>
      )}
    </section>
  );
}

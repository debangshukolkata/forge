// Multi-step form: three short steps with a progress line, Back and Next buttons, a check on each step before moving on, and a review before sending.
// Use it when one long form would put people off (a booking, an application, a registration). The fields are examples: change the step list and the
// `fields` of each step; every field is a labelled input with its own error message. `onSubmit` receives all the values.
import { useState, type FormEvent } from "react";

export type StepField = { name: string; label: string; type?: "text" | "email" | "tel" | "date" | "number"; required?: boolean; hint?: string };
export type Step = { title: string; text?: string; fields: StepField[] };

const DEFAULT_STEPS: Step[] = [
  { title: "About you", text: "So we know who to expect.", fields: [{ name: "name", label: "Full name", required: true }, { name: "email", label: "E-mail", type: "email", required: true }] },
  { title: "The visit", text: "When would you like to come?", fields: [{ name: "date", label: "Preferred date", type: "date", required: true }, { name: "guests", label: "Number of guests", type: "number", required: true, hint: "Between 1 and 12" }] },
  { title: "Anything else", text: "Optional, but it helps us prepare.", fields: [{ name: "notes", label: "Notes for the team", hint: "Allergies, access needs, a celebration" }] },
];

export default function FormStepper({
  eyebrow = "Book a visit",
  title = "Three short steps.",
  steps = DEFAULT_STEPS,
  onSubmit,
}: {
  eyebrow?: string;
  title?: string;
  steps?: Step[];
  onSubmit?: (values: Record<string, string>) => void;
}) {
  const [index, setIndex] = useState(0);
  const [values, setValues] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [done, setDone] = useState(false);
  const review = index === steps.length;
  const step = steps[index];
  const check = (fields: StepField[]) => {
    const found: Record<string, string> = {};
    for (const field of fields) {
      const value = (values[field.name] ?? "").trim();
      if (field.required && !value) found[field.name] = `${field.label} is needed.`;
      else if (field.type === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value)) found[field.name] = "Enter an e-mail address we can reply to.";
    }
    setErrors(found);
    return Object.keys(found).length === 0;
  };
  const next = () => {
    if (check(step.fields)) setIndex(index + 1);
  };
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!review) return next();
    setDone(true);
    onSubmit?.(values);
  };
  return (
    <section id="contact" className="mx-auto max-w-2xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
      {done ? (
        <p role="status" className="mt-8 text-lg font-semibold text-ok">Thank you. We have your details and will confirm by e-mail within a day.</p>
      ) : (
        <form onSubmit={submit} noValidate className="mt-8">
          <ol aria-label="Progress" className="mb-8 flex gap-2">
            {[...steps, { title: "Review", fields: [] }].map((item, position) => (
              <li key={item.title} aria-current={position === index ? "step" : undefined} className="flex-1">
                <span className={`block h-1 rounded-full ${position <= index ? "bg-brand-600" : "bg-ink-200"}`} />
                <span className={`mt-2 block text-xs font-semibold ${position === index ? "text-ink-900" : "text-ink-500"}`}>{position + 1}. {item.title}</span>
              </li>
            ))}
          </ol>
          {review ? (
            <dl className="border-y border-ink-300">
              {steps.flatMap((item) => item.fields).map((field) => (
                <div key={field.name} className="grid gap-1 border-b border-ink-200 py-3 last:border-b-0 sm:grid-cols-[10rem_1fr]">
                  <dt className="text-sm text-ink-500">{field.label}</dt>
                  <dd className="text-ink-900">{values[field.name] || "Not given"}</dd>
                </div>
              ))}
            </dl>
          ) : (
            <fieldset className="space-y-5">
              <legend className="text-xl font-semibold text-ink-900">{step.title}</legend>
              {step.text && <p className="-mt-3 text-ink-700">{step.text}</p>}
              {step.fields.map((field) => (
                <div key={field.name}>
                  <label htmlFor={`stepper-${field.name}`} className="mb-1 block text-sm font-semibold text-ink-900">{field.label}</label>
                  <input
                    id={`stepper-${field.name}`}
                    type={field.type ?? "text"}
                    value={values[field.name] ?? ""}
                    onChange={(event) => setValues({ ...values, [field.name]: event.target.value })}
                    aria-invalid={Boolean(errors[field.name])}
                    aria-describedby={`stepper-${field.name}-note`}
                    className="field"
                  />
                  <p id={`stepper-${field.name}-note`} role={errors[field.name] ? "alert" : undefined} className={`mt-1 min-h-5 text-sm ${errors[field.name] ? "text-danger" : "text-ink-500"}`}>
                    {errors[field.name] ?? field.hint ?? ""}
                  </p>
                </div>
              ))}
            </fieldset>
          )}
          <div className="mt-8 flex items-center justify-between gap-4">
            <button type="button" onClick={() => setIndex(Math.max(0, index - 1))} disabled={index === 0} className="btn-secondary">Back</button>
            <button type="submit" className="btn-primary">{review ? "Send booking" : "Next"}</button>
          </div>
        </form>
      )}
    </section>
  );
}

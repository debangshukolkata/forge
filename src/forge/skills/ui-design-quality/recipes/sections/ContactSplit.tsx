// Contact split: details on the left (address, hours, phone and e-mail as a definition list), a short message form on the right. Different from
// `ContactForm`, which is a form on its own: use this one when people also need to find the place. The form validates on submit and shows a thank-you.
import { useState, type FormEvent } from "react";

type Message = { name: string; email: string; message: string };

export default function ContactSplit({
  eyebrow = "Visit or write",
  title = "Come by, or send us a note.",
  details = [
    { label: "Address", value: "Mill Lane, Unit 4, Riverside" },
    { label: "Open", value: "Wednesday to Sunday, 10 to 6" },
    { label: "Phone", value: "01234 567 890" },
    { label: "E-mail", value: "hello@millstudio.example" },
  ],
  onSubmit,
}: {
  eyebrow?: string;
  title?: string;
  details?: { label: string; value: string }[];
  onSubmit?: (message: Message) => void;
}) {
  const [values, setValues] = useState<Message>({ name: "", email: "", message: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof Message, string>>>({});
  const [done, setDone] = useState(false);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: Partial<Record<keyof Message, string>> = {};
    if (!values.name.trim()) found.name = "Please tell us your name.";
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(values.email.trim())) found.email = "Enter an e-mail address we can reply to.";
    if (values.message.trim().length < 10) found.message = "Write at least a sentence so we can help.";
    setErrors(found);
    if (Object.keys(found).length === 0) {
      setDone(true);
      onSubmit?.(values);
    }
  };
  const set = (key: keyof Message) => (event: { target: { value: string } }) => setValues({ ...values, [key]: event.target.value });
  const error = (key: keyof Message) => (
    <p id={`contact-split-${key}-error`} role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors[key] ?? ""}</p>
  );
  return (
    <section id="contact" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-10 grid gap-12 md:mt-14 md:grid-cols-12">
        <dl className="md:col-span-5">
          {details.map((detail) => (
            <div key={detail.label} className="border-t border-ink-300 py-4 first:border-t-0 first:pt-0">
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">{detail.label}</dt>
              <dd className="mt-1 text-lg text-ink-900">{detail.value}</dd>
            </div>
          ))}
        </dl>
        <div className="md:col-span-7">
          {done ? (
            <p role="status" className="text-lg font-semibold text-ok">Thank you, {values.name.trim()}. We will write back within two working days.</p>
          ) : (
            <form onSubmit={submit} noValidate className="space-y-5">
              <div>
                <label htmlFor="contact-split-name" className="mb-1 block text-sm font-semibold text-ink-900">Your name</label>
                <input id="contact-split-name" type="text" autoComplete="name" value={values.name} onChange={set("name")} aria-invalid={Boolean(errors.name)} aria-describedby="contact-split-name-error" className="field" />
                {error("name")}
              </div>
              <div>
                <label htmlFor="contact-split-email" className="mb-1 block text-sm font-semibold text-ink-900">E-mail</label>
                <input id="contact-split-email" type="email" autoComplete="email" value={values.email} onChange={set("email")} aria-invalid={Boolean(errors.email)} aria-describedby="contact-split-email-error" className="field" />
                {error("email")}
              </div>
              <div>
                <label htmlFor="contact-split-message" className="mb-1 block text-sm font-semibold text-ink-900">Message</label>
                <textarea id="contact-split-message" rows={5} value={values.message} onChange={set("message")} aria-invalid={Boolean(errors.message)} aria-describedby="contact-split-message-error" className="field" />
                {error("message")}
              </div>
              <button type="submit" className="btn-primary">Send message</button>
            </form>
          )}
        </div>
      </div>
    </section>
  );
}

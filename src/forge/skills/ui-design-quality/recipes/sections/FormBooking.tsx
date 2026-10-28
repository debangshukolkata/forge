// Booking bar: a compact horizontal form for a date, a time slot and a party size, with one button; the choices become a short summary line once sent.
// For restaurants, classes, appointments. The date cannot be in the past, the time is chosen from `slots`, the guests from 1 to `maxGuests`.
// `onSubmit` receives the three values. Stacks to one column on a phone.
import { useState, type FormEvent } from "react";

export default function FormBooking({
  eyebrow = "Reserve a table",
  title = "Pick a time that suits you.",
  slots = ["12:00", "12:30", "13:00", "18:00", "18:30", "19:00", "19:30", "20:00"],
  maxGuests = 8,
  button = "Check availability",
  onSubmit,
}: {
  eyebrow?: string;
  title?: string;
  slots?: string[];
  maxGuests?: number;
  button?: string;
  onSubmit?: (booking: { date: string; time: string; guests: number }) => void;
}) {
  const today = new Date().toISOString().slice(0, 10);
  const [date, setDate] = useState("");
  const [time, setTime] = useState("");
  const [guests, setGuests] = useState(2);
  const [errors, setErrors] = useState<{ date?: string; time?: string }>({});
  const [sent, setSent] = useState<string | null>(null);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: typeof errors = {};
    if (!date || date < today) found.date = "Choose today or a later date.";
    if (!time) found.time = "Choose a time.";
    setErrors(found);
    if (Object.keys(found).length) return;
    setSent(`${guests} ${guests === 1 ? "guest" : "guests"} on ${date} at ${time}`);
    onSubmit?.({ date, time, guests });
  };
  return (
    <section id="contact" className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-20">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <form onSubmit={submit} noValidate className="mt-8 grid items-start gap-4 border-y border-ink-900 py-6 md:grid-cols-[1fr_1fr_1fr_auto]">
        <div>
          <label htmlFor="booking-date" className="mb-1 block text-sm font-semibold text-ink-900">Date</label>
          <input id="booking-date" type="date" min={today} value={date} onChange={(event) => setDate(event.target.value)} aria-invalid={Boolean(errors.date)} aria-describedby="booking-date-error" className="field" />
          <p id="booking-date-error" role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors.date ?? ""}</p>
        </div>
        <div>
          <label htmlFor="booking-time" className="mb-1 block text-sm font-semibold text-ink-900">Time</label>
          <select id="booking-time" value={time} onChange={(event) => setTime(event.target.value)} aria-invalid={Boolean(errors.time)} aria-describedby="booking-time-error" className="field">
            <option value="">Choose a time</option>
            {slots.map((slot) => (
              <option key={slot} value={slot}>{slot}</option>
            ))}
          </select>
          <p id="booking-time-error" role="alert" className="mt-1 min-h-5 text-sm text-danger">{errors.time ?? ""}</p>
        </div>
        <div>
          <label htmlFor="booking-guests" className="mb-1 block text-sm font-semibold text-ink-900">Guests</label>
          <select id="booking-guests" value={guests} onChange={(event) => setGuests(Number(event.target.value))} className="field">
            {Array.from({ length: maxGuests }, (_, position) => position + 1).map((count) => (
              <option key={count} value={count}>{count}</option>
            ))}
          </select>
        </div>
        <button type="submit" className="btn-primary md:mt-7">{button}</button>
      </form>
      <p role="status" className="mt-4 min-h-6 font-semibold text-ok">{sent ? `Request sent for ${sent}. We will confirm by e-mail.` : ""}</p>
    </section>
  );
}

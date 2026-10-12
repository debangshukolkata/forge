// Reference landing page (React + Tailwind v4, with index.css next to it). It shows the QUALITY BAR to match: a
// container, a type scale, a spacing rhythm, one primary button per view, real content, designed states. Copy the
// structure and the discipline, never the wording or colours: every product gets its own palette, fonts, copy and
// layout idea (see palettes-and-fonts.md). Needs: npm i lucide-react
import { useState, type FormEvent } from "react";
import { ArrowRight, CalendarDays, Check, ChevronDown, Clock, HeartPulse, MapPin, ShieldCheck } from "lucide-react";

const nav = [["How it works", "#how"], ["Eligibility", "#faq"], ["FAQ", "#faq"]];
const stats = [["320", "slots available"], ["150+", "units to collect"], ["450+", "lives supported"]];
const facts = [
  { icon: CalendarDays, text: "Sun, 25 Oct" },
  { icon: Clock, text: "9:00 AM – 5:00 PM" },
  { icon: MapPin, text: "Community Hall" },
];
const steps = [
  { icon: CalendarDays, title: "Pick a slot", text: "Choose a 30-minute time that suits you. We send a reminder the day before." },
  { icon: ShieldCheck, title: "Quick health check", text: "A nurse checks your pulse, blood pressure and haemoglobin. It takes ten minutes." },
  { icon: HeartPulse, title: "Donate and rest", text: "The donation takes about eight minutes. Stay for a snack and a short rest." },
];
const faqs = [
  ["Who can donate?", "Healthy adults aged 18 to 65, weighing at least 50 kg, with no fever or recent surgery."],
  ["Does it hurt?", "Most people feel only a brief pinch. A trained nurse stays with you throughout."],
  ["How long does it take?", "About 45 minutes from check-in to your snack, including the health check."],
];

export default function App() {
  return (
    <>
      <Header />
      <main>
        <Hero />
        <Stats />
        <How />
        <Register />
        <Faq />
      </main>
      <footer className="border-t border-ink-200 py-10 text-center text-sm text-ink-500">
        © 2026 Brand name · Questions? help@example.org
      </footer>
    </>
  );
}

function Header() {
  return (
    <header className="sticky top-0 z-20 border-b border-ink-200/70 bg-ink-50/85 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        <a href="#" className="flex items-center gap-2 font-display text-lg font-semibold text-ink-900">
          <span className="grid h-8 w-8 place-items-center rounded-full bg-brand-600 text-white">
            <HeartPulse size={18} />
          </span>
          Brand name
        </a>
        <nav className="hidden gap-8 text-sm font-medium text-ink-700 md:flex">
          {nav.map(([label, href]) => (
            <a key={href} href={href} className="transition hover:text-brand-600">{label}</a>
          ))}
        </nav>
        <a href="#register" className="btn-primary !px-5 !py-2.5">Register</a>
      </div>
    </header>
  );
}

function Hero() {
  return (
    <section className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-16 sm:px-6 md:grid-cols-[1.1fr_0.9fr] md:py-24">
      <div className="fade-up">
        <p className="eyebrow">25 October 2026 · West Bengal</p>
        <h1 className="mt-4 text-5xl leading-[1.05] sm:text-6xl">One hour of your day can give someone years.</h1>
        <p className="mt-6 max-w-prose text-lg leading-relaxed text-ink-700">
          Join our one-day community drive. Medically supervised, gently run, and every donation reaches a patient in a
          nearby hospital.
        </p>
        <div className="mt-8 flex flex-wrap items-center gap-3">
          <a href="#register" className="btn-primary">Reserve my slot <ArrowRight size={16} /></a>
          <a href="#faq" className="btn-secondary">Who can donate?</a>
        </div>
        <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-700">
          {facts.map(({ icon: Icon, text }) => (
            <li key={text} className="flex items-center gap-2"><Icon size={16} className="text-brand-600" />{text}</li>
          ))}
        </ul>
      </div>
      <HeroArt />
    </section>
  );
}

// A drawn visual instead of an empty box: layered shapes in the brand colours. Replace with a real photo when one exists.
function HeroArt() {
  return (
    <div className="relative mx-auto aspect-square w-full max-w-md" aria-hidden>
      <div className="absolute inset-0 rounded-[2.5rem] bg-gradient-to-br from-brand-100 via-brand-50 to-ink-100" />
      <svg viewBox="0 0 200 200" className="absolute inset-0 h-full w-full">
        <circle cx="100" cy="100" r="62" fill="var(--color-brand-600)" opacity="0.1" />
        <circle cx="100" cy="100" r="42" fill="var(--color-brand-600)" opacity="0.18" />
        <path d="M100 52c22 28 36 46 36 64a36 36 0 0 1-72 0c0-18 14-36 36-64z" fill="var(--color-brand-600)" />
        <path d="M82 118a18 18 0 0 0 14 22" stroke="white" strokeWidth="5" strokeLinecap="round" fill="none" opacity="0.7" />
      </svg>
      <div className="absolute -bottom-4 -left-4 rounded-2xl border border-ink-200 bg-white px-4 py-3 shadow-lift">
        <p className="text-xs text-ink-500">Next free slot</p>
        <p className="font-display text-lg font-semibold text-ink-900">9:30 AM</p>
      </div>
    </div>
  );
}

function Stats() {
  return (
    <section className="border-y border-ink-200 bg-white">
      <dl className="mx-auto grid max-w-6xl grid-cols-1 divide-y divide-ink-200 px-4 sm:grid-cols-3 sm:divide-x sm:divide-y-0 sm:px-6">
        {stats.map(([value, label]) => (
          <div key={label} className="flex flex-col-reverse items-center py-8 text-center sm:py-10">
            <dt className="mt-1 text-sm text-ink-500">{label}</dt>
            <dd className="font-display text-5xl font-semibold text-ink-900">{value}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function How() {
  return (
    <section
      id="how"
      className="mx-auto grid max-w-6xl scroll-mt-20 gap-12 px-4 py-20 sm:px-6 md:grid-cols-[0.8fr_1.2fr] md:py-28"
    >
      {/* Asymmetric on purpose: a sticky intro beside a stacked list avoids the generic three-equal-cards row. */}
      <div className="md:sticky md:top-28 md:self-start">
        <p className="eyebrow">How it works</p>
        <h2 className="mt-3 text-4xl">Three simple steps, about 45 minutes in total</h2>
        <p className="mt-4 max-w-sm leading-relaxed text-ink-700">
          Nothing to prepare. Bring a photo ID and drink plenty of water the day before.
        </p>
      </div>
      <ol className="space-y-4">
        {steps.map(({ icon: Icon, title, text }, index) => (
          <li key={title} className="card flex gap-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-lift">
            <span className="font-display text-5xl font-semibold leading-none text-brand-500" aria-hidden>
              {index + 1}
            </span>
            <div className="flex-1">
              <h3 className="text-xl">{title}</h3>
              <p className="mt-2 leading-relaxed text-ink-700">{text}</p>
            </div>
            <span className="hidden h-11 w-11 shrink-0 place-items-center rounded-xl bg-brand-50 text-brand-600 sm:grid">
              <Icon size={22} />
            </span>
          </li>
        ))}
      </ol>
    </section>
  );
}

type Status = "idle" | "sending" | "done";
const fields = [
  { id: "name", label: "Full name", type: "text", hint: "Asha Roy" },
  { id: "email", label: "Email", type: "email", hint: "asha@example.com" },
];

function Register() {
  const [status, setStatus] = useState<Status>("idle");
  const [errors, setErrors] = useState<Record<string, string>>({});

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    const found: Record<string, string> = {};
    if (!String(data.get("name") ?? "").trim()) found.name = "Please tell us your name.";
    if (!/^\S+@\S+\.\S+$/.test(String(data.get("email") ?? ""))) found.email = "Enter an email like name@example.com.";
    setErrors(found);
    if (Object.keys(found).length) return;
    setStatus("sending");
    window.setTimeout(() => setStatus("done"), 900); // replace with the real request
  }

  return (
    <section id="register" className="scroll-mt-20 bg-ink-900 py-20 text-ink-100 md:py-28">
      <div className="mx-auto grid max-w-6xl gap-12 px-4 sm:px-6 md:grid-cols-2">
        <div>
          <p className="eyebrow !text-brand-200">Register</p>
          <h2 className="mt-3 text-4xl !text-white">Reserve your slot</h2>
          <p className="mt-4 max-w-md text-ink-300">
            It takes under a minute. We will email your confirmation and a reminder the day before.
          </p>
        </div>
        {status === "done" ? (
          <div role="status" className="rounded-card bg-white p-8 text-ink-900">
            <span className="grid h-12 w-12 place-items-center rounded-full bg-ok/10 text-ok"><Check size={24} /></span>
            <h3 className="mt-4 text-2xl">You are booked in. Thank you.</h3>
            <p className="mt-2 text-ink-700">A confirmation is on its way to your inbox.</p>
          </div>
        ) : (
          <form onSubmit={submit} noValidate className="space-y-5 rounded-card bg-white p-6 text-ink-900 sm:p-8">
            {fields.map(({ id, label, type, hint }) => (
              <div key={id}>
                <label htmlFor={id} className="mb-1.5 block text-sm font-medium">{label}</label>
                <input
                  id={id}
                  name={id}
                  type={type}
                  placeholder={hint}
                  aria-invalid={!!errors[id]}
                  aria-describedby={errors[id] ? `${id}-error` : undefined}
                  className={`field ${errors[id] ? "!border-brand-600" : ""}`}
                />
                {errors[id] && <p id={`${id}-error`} className="mt-1.5 text-sm text-brand-700">{errors[id]}</p>}
              </div>
            ))}
            <button type="submit" disabled={status === "sending"} className="btn-primary w-full">
              {status === "sending" ? "Booking…" : "Confirm my slot"}
            </button>
          </form>
        )}
      </div>
    </section>
  );
}

function Faq() {
  return (
    <section id="faq" className="mx-auto max-w-3xl scroll-mt-20 px-4 py-20 sm:px-6 md:py-28">
      <h2 className="text-center text-4xl">Questions, answered</h2>
      <div className="mt-10 divide-y divide-ink-200 rounded-card border border-ink-200 bg-white">
        {faqs.map(([question, answer]) => (
          <details key={question} className="group p-6">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 font-medium text-ink-900">
              {question}
              <ChevronDown size={18} className="shrink-0 text-ink-500 transition group-open:rotate-180" />
            </summary>
            <p className="mt-3 leading-relaxed text-ink-700">{answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

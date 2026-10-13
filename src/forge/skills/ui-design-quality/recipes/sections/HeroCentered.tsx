// Centred hero: a short eyebrow chip, a large headline, one sentence, two actions and an optional wide visual below.
// Good for products that can be explained in one line. Keep the headline to three lines at desktop width.
import type { ReactNode } from "react";

export default function HeroCentered({
  eyebrow = "New: reports that write themselves",
  title = "See what your numbers are trying to tell you.",
  text = "Lumen turns raw spreadsheets into a plain-language weekly briefing, so the whole team knows what changed and what to do next.",
  primary = { label: "Start free", href: "#contact" },
  secondary = { label: "See pricing", href: "#pricing" },
  note = "Free for 14 days. No card needed.",
  children,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  primary?: { label: string; href: string };
  secondary?: { label: string; href: string };
  note?: string;
  children?: ReactNode;
}) {
  return (
    <section id="top" className="mx-auto max-w-6xl px-4 pb-10 pt-16 text-center sm:px-6 md:pt-24">
      <p className="mx-auto inline-flex rounded-full border border-ink-200 bg-white px-4 py-1.5 text-sm font-medium text-ink-700 shadow-soft">
        {eyebrow}
      </p>
      <h1 className="mx-auto mt-6 max-w-3xl text-4xl font-semibold leading-[1.08] sm:text-5xl lg:text-6xl">{title}</h1>
      <p className="mx-auto mt-6 max-w-2xl text-lg leading-relaxed text-ink-700">{text}</p>
      <div className="mt-8 flex flex-wrap justify-center gap-3">
        <a href={primary.href} className="btn-primary">{primary.label}</a>
        <a href={secondary.href} className="btn-secondary">{secondary.label}</a>
      </div>
      {note && <p className="mt-4 text-sm text-ink-500">{note}</p>}
      {children && <div className="mx-auto mt-14 max-w-4xl">{children}</div>}
    </section>
  );
}

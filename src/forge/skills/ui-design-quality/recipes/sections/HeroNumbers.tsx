// Numbers hero: the headline on the left and three large figures stacked on the right, each with a short label, separated by hairlines.
// For a product or organisation that can prove its claim with specific numbers. Use real figures; the audit flags placeholder text.
export type HeroFigure = { value: string; label: string };

export default function HeroNumbers({
  eyebrow = "Clinic results, 2026",
  title = "A shorter wait for every patient we see.",
  text = "Since we moved booking to the same day, appointments start earlier and fewer people are turned away. These are the figures from the last twelve months.",
  primary = { label: "Read the report", href: "#report" },
  secondary = { label: "Book a visit", href: "#book" },
  figures = [
    { value: "9 min", label: "average wait, down from 34" },
    { value: "96%", label: "of patients seen the same day" },
    { value: "4,200", label: "visits across three clinics" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  primary?: { label: string; href: string };
  secondary?: { label: string; href: string };
  figures?: HeroFigure[];
}) {
  return (
    <section id="top" className="mx-auto max-w-6xl px-4 py-14 sm:px-6 md:py-24">
      <div className="grid gap-12 md:grid-cols-12 md:items-center">
        <div className="md:col-span-7">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="mt-4 text-4xl font-semibold leading-[1.05] sm:text-5xl lg:text-6xl">{title}</h1>
          <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-700">{text}</p>
          <div className="mt-8 flex flex-wrap gap-3">
            <a href={primary.href} className="btn-primary">{primary.label}</a>
            <a href={secondary.href} className="btn-secondary">{secondary.label}</a>
          </div>
        </div>
        <dl className="border-y border-ink-900 md:col-span-5 md:border-y-0 md:border-l md:pl-10">
          {figures.map((figure) => (
            <div key={figure.label} className="border-b border-ink-200 py-5 last:border-b-0 md:py-6">
              <dd className="font-display text-5xl font-semibold tabular-nums text-brand-600 sm:text-6xl">{figure.value}</dd>
              <dt className="mt-1 text-sm text-ink-500">{figure.label}</dt>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}

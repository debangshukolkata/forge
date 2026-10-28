// Quote hero: a single large statement or pull-quote as the headline, with who said it underneath and one button. For a person, a practice or a small
// firm whose view is the product (a consultant, a coach, a writer). The statement is set big in the display font, left aligned, with a short rule above it.
// Keep it to one or two sentences you would stand behind; a quote from a real client needs their permission.
export default function HeroQuote({
  eyebrow = "Independent consultant",
  quote = "Most strategy documents fail because nobody reads past page three. I write the three pages that get used.",
  name = "Anna Lindqvist",
  role = "Strategy for small organisations, since 2011",
  primary = { label: "Book a first call", href: "#contact" },
  secondary = { label: "How I work", href: "#approach" },
}: {
  eyebrow?: string;
  quote?: string;
  name?: string;
  role?: string;
  primary?: { label: string; href: string };
  secondary?: { label: string; href: string };
}) {
  return (
    <section id="top" className="mx-auto max-w-5xl px-4 py-16 sm:px-6 md:py-28">
      <p className="eyebrow">{eyebrow}</p>
      <span aria-hidden="true" className="mt-6 block h-1 w-16 bg-brand-600" />
      <h1 className="mt-8 font-display text-4xl font-semibold leading-[1.1] sm:text-5xl lg:text-6xl">{quote}</h1>
      <p className="mt-8 text-lg">
        <span className="font-semibold text-ink-900">{name}</span>
        <span className="text-ink-500">, {role}</span>
      </p>
      <div className="mt-10 flex flex-wrap gap-3">
        <a href={primary.href} className="btn-primary">{primary.label}</a>
        <a href={secondary.href} className="btn-secondary">{secondary.label}</a>
      </div>
    </section>
  );
}

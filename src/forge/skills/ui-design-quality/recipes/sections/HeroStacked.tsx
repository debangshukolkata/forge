// Stacked hero: a left-aligned headline and one line of text on top, then a full-width picture band underneath that breaks out of the text column.
// Use it when the picture carries the page (a venue, a product, a place). Pass your own picture as children; the drawn band is only a stand-in.
import type { ReactNode } from "react";

export default function HeroStacked({
  eyebrow = "Harbour Street Bakery",
  title = "Bread that is ready when you walk in.",
  text = "We bake in small batches from four in the morning, so the first loaves are out before the street wakes up and the last ones are gone by two.",
  primary = { label: "See today's bake", href: "#menu" },
  secondary = { label: "Find us", href: "#visit" },
  children,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  primary?: { label: string; href: string };
  secondary?: { label: string; href: string };
  children?: ReactNode;
}) {
  return (
    <section id="top" className="pt-10 md:pt-16">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-4 max-w-4xl text-4xl font-semibold leading-[1.05] sm:text-6xl">{title}</h1>
        <div className="mt-6 flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
          <p className="max-w-xl text-lg leading-relaxed text-ink-700">{text}</p>
          <div className="flex flex-wrap gap-3">
            <a href={primary.href} className="btn-primary">{primary.label}</a>
            <a href={secondary.href} className="btn-secondary">{secondary.label}</a>
          </div>
        </div>
      </div>
      <div className="mt-10 md:mt-14">
        {children ?? (
          <div aria-hidden="true" className="relative h-56 overflow-hidden bg-brand-100 sm:h-80 md:h-[26rem]">
            <div className="absolute -bottom-24 left-[8%] h-72 w-72 rounded-full bg-brand-200" />
            <div className="absolute -bottom-32 left-[38%] h-80 w-80 rounded-full bg-brand-600" />
            <div className="absolute bottom-0 right-0 h-1/3 w-2/5 bg-ink-900" />
          </div>
        )}
      </div>
    </section>
  );
}

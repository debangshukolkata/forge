// Editorial hero: an oversized headline across most of the width, a small tall picture pushed to the right, and a ruled strip of facts underneath.
// Asymmetric on purpose (not a centred column, not a 50/50 split); stacks on a phone with the picture last. Pass your own picture as children.
// The title is a list of lines so the last one can carry the accent; keep it to two or three short lines.
import type { ReactNode } from "react";

function DefaultArt() {
  return (
    <div aria-hidden="true" className="relative aspect-[3/4] w-full overflow-hidden rounded-t-full bg-brand-100">
      <div className="absolute left-1/2 top-[18%] h-[34%] w-[56%] -translate-x-1/2 rounded-full bg-brand-600" />
      <div className="absolute bottom-0 left-0 h-[34%] w-full bg-ink-900" />
      <div className="absolute bottom-[26%] left-[14%] h-[16%] w-[72%] rounded-t-full bg-brand-200" />
    </div>
  );
}

export default function HeroEditorial({
  issue = "Studio notes, autumn",
  date = "Open Wednesday to Sunday",
  title = ["Slow clay,", "made by hand."],
  text = "A small pottery studio in the old mill by the river. Evening classes for beginners, open firing days, and one-off pieces you can take home the same week.",
  primary = { label: "Book a class", href: "#contact" },
  secondary = { label: "See the studio", href: "#studio" },
  facts = [
    { label: "Classes", value: "Six weeks, eight people" },
    { label: "Where", value: "Mill Lane, Unit 4" },
    { label: "Firing", value: "Every second Sunday" },
  ],
  children,
}: {
  issue?: string;
  date?: string;
  title?: string[];
  text?: string;
  primary?: { label: string; href: string };
  secondary?: { label: string; href: string };
  facts?: { label: string; value: string }[];
  children?: ReactNode;
}) {
  return (
    <section id="top" className="mx-auto max-w-6xl px-4 pb-14 pt-8 sm:px-6 md:pb-20 md:pt-12">
      <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-ink-300 pb-3 text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">
        <span>{issue}</span>
        <span>{date}</span>
      </div>
      <div className="mt-10 grid gap-x-8 gap-y-10 md:grid-cols-12">
        <h1 className="text-5xl font-semibold leading-[0.95] tracking-tight sm:text-6xl md:col-span-9 md:self-start lg:text-7xl">
          {title.map((line, index) => (
            <span key={line} className={`block ${index === title.length - 1 ? "italic text-brand-600" : ""}`}>
              {line}
            </span>
          ))}
        </h1>
        <div className="order-last max-w-xs md:order-none md:col-span-3 md:col-start-10 md:row-span-3 md:row-start-1 md:mt-16">{children ?? <DefaultArt />}</div>
        <p className="max-w-xl text-lg leading-relaxed text-ink-700 md:col-span-6">{text}</p>
        <div className="flex flex-wrap items-start gap-3 md:col-span-6">
          <a href={primary.href} className="btn-primary">{primary.label}</a>
          <a href={secondary.href} className="btn-secondary">{secondary.label}</a>
        </div>
      </div>
      {facts.length > 0 && (
        <dl className="mt-12 grid border-t border-ink-900 sm:grid-cols-3">
          {facts.map((fact) => (
            <div key={fact.label} className="border-b border-ink-200 py-4 sm:border-b-0 sm:border-l sm:border-ink-200 sm:pl-5 sm:first:border-l-0 sm:first:pl-0">
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">{fact.label}</dt>
              <dd className="mt-1 text-ink-900">{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </section>
  );
}

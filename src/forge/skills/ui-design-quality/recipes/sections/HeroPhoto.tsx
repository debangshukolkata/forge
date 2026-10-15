// Photography-led hero: one large photograph runs to the edge of the page on the right and fades into the page colour on the left, where the headline sits on the fade.
// The picture is the protagonist and the words explain the promise. Give `src` and `alt` for a real photograph (generate_image, find_image or the brand folder); the drawn
// stand-in is only a placeholder. Set the headline in a light or regular display weight at a large size (it is `font-light`). A row of up to three trust points sits
// below the buttons. On a phone the text comes first and the photograph below it, so the message is never pushed down.
import type { ReactNode } from "react";

export type TrustPoint = { label: string; icon?: ReactNode };

function Stand() {
  return (
    <div aria-hidden="true" className="relative h-full min-h-[18rem] w-full overflow-hidden bg-brand-100">
      <div className="absolute bottom-[-8%] right-[8%] h-[70%] w-[62%] rounded-[50%] bg-brand-600" />
      <div className="absolute bottom-[14%] right-[22%] h-[22%] w-[34%] rounded-[50%] bg-brand-500" />
      <div className="absolute bottom-0 left-0 h-[22%] w-full bg-ink-900" />
    </div>
  );
}

export default function HeroPhoto({
  eyebrow = "Neighbourhood bakery",
  title = "Slow-fermented sourdough, baked fresh daily.",
  text = "Crisp-crusted loaves and flaky pastries, made with organic flour, long patient fermentation and early-morning baking.",
  primary = { label: "View today's bakes", href: "#menu" },
  points = [{ label: "Organic flour" }, { label: "Slow fermentation" }, { label: "Baked locally" }],
  src,
  alt = "",
  children,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  primary?: { label: string; href: string };
  points?: TrustPoint[];
  src?: string;
  alt?: string;
  children?: ReactNode;
}) {
  return (
    <section id="top" className="relative overflow-hidden bg-ink-50">
      <div className="relative z-10 mx-auto max-w-6xl px-4 pb-10 pt-10 sm:px-6 md:py-24">
        <div className="md:max-w-[54%]">
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="mt-4 text-5xl font-light leading-[1.02] tracking-tight sm:text-6xl">{title}</h1>
          <p className="mt-6 max-w-md text-lg leading-relaxed text-ink-700">{text}</p>
          <a href={primary.href} className="btn-primary mt-8">{primary.label}</a>
          {points.length > 0 && (
            <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-700">
              {points.map((point) => (
                <li key={point.label} className="flex items-center gap-2">
                  {point.icon}
                  {point.label}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
      <div className="relative min-h-[18rem] md:absolute md:inset-y-0 md:right-0 md:w-[64%]">
        {src ? <img src={src} alt={alt} className="h-full w-full object-cover" /> : (children ?? <Stand />)}
        <div aria-hidden="true" className="pointer-events-none absolute inset-y-0 left-0 hidden w-1/2 bg-gradient-to-r from-ink-50 to-transparent md:block" />
      </div>
    </section>
  );
}

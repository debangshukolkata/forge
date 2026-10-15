// A full-width band split in two halves that touch the edges of the page: a photograph on one side (flush to the band, no frame) and a coloured panel with the words on
// the other. `tone` "dark" gives a deep panel (use it once per page, for the craft or process step), "light" a cream panel (for an invitation or a visit). `side` puts the
// picture on the left or the right. Give `src` and `alt` for a real photograph, or pass your own picture as children; the drawn stand-in is only a placeholder.
// On a phone the text comes first and the picture follows.
import type { ReactNode } from "react";

function Stand({ dark }: { dark: boolean }) {
  return (
    <div aria-hidden="true" className={`relative h-full min-h-[18rem] w-full overflow-hidden ${dark ? "bg-ink-700" : "bg-brand-100"}`}>
      <div className="absolute left-[14%] top-[16%] h-[38%] w-[34%] rounded-full bg-brand-500" />
      <div className="absolute bottom-0 left-0 h-[30%] w-full bg-ink-200" />
      <div className="absolute bottom-[22%] right-[12%] h-[24%] w-[44%] rounded-t-full bg-brand-200" />
    </div>
  );
}

export default function SplitBand({
  tone = "dark",
  side = "right",
  eyebrow = "Our approach",
  title = "Good bread takes time.",
  text = "We use organic flour, long patient fermentation and traditional baking methods to create bread with depth of flavour, a crisp crust and a soft, open crumb.",
  action = { label: "Our story", href: "#story" },
  src,
  alt = "",
  children,
}: {
  tone?: "dark" | "light";
  side?: "left" | "right";
  eyebrow?: string;
  title?: string;
  text?: string;
  action?: { label: string; href: string };
  src?: string;
  alt?: string;
  children?: ReactNode;
}) {
  const dark = tone === "dark";
  return (
    <section className={`grid md:grid-cols-2 ${dark ? "bg-ink-900 text-ink-100" : "bg-ink-100 text-ink-700"}`}>
      <div className={`flex items-center px-6 py-14 sm:px-10 md:px-16 md:py-20 ${side === "left" ? "md:order-2" : ""}`}>
        <div className="max-w-md">
          <p className={`text-xs font-semibold uppercase tracking-[0.14em] ${dark ? "text-brand-200" : "text-brand-600"}`}>{eyebrow}</p>
          <h2 className={`mt-3 text-4xl font-light leading-tight sm:text-5xl ${dark ? "text-white!" : ""}`}>{title}</h2>
          <p className={`mt-5 text-lg leading-relaxed ${dark ? "text-ink-200" : "text-ink-700"}`}>{text}</p>
          <a href={action.href} className={`mt-8 ${dark ? "btn bg-white text-ink-900 hover:bg-ink-100" : "btn-primary"}`}>{action.label}</a>
        </div>
      </div>
      <div className={`relative min-h-[18rem] ${side === "left" ? "md:order-1" : ""}`}>
        {src ? <img src={src} alt={alt} className="absolute inset-0 h-full w-full object-cover" /> : (children ?? <Stand dark={dark} />)}
      </div>
    </section>
  );
}

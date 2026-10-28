// Icon row: three or four features side by side, each with a small line icon, a title and two sentences, divided by hairlines and not boxed.
// The icons are drawn inline (24 px line icons in the brand colour), so nothing needs installing; pass your own `icon` node per item to change one.
import type { ReactNode } from "react";

export type IconFeature = { title: string; text: string; icon?: ReactNode };

const base = { width: 28, height: 28, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round", "aria-hidden": true } as const;
const CLOCK = (<svg {...base}><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></svg>);
const SHIELD = (<svg {...base}><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z" /><path d="M9 12l2 2 4-4" /></svg>);
const CHAT = (<svg {...base}><path d="M4 5h16v11H9l-5 4z" /><path d="M8 9h8M8 12h5" /></svg>);
const LEAF = (<svg {...base}><path d="M5 19c0-8 5-14 15-14 0 10-6 15-14 15" /><path d="M5 19c3-5 6-8 10-10" /></svg>);
// An item without its own `icon` gets the next one of these four, so a list is never four copies of the same picture.
const DEFAULT_ICONS = [CHAT, SHIELD, CLOCK, LEAF];

export default function FeaturesIconRow({
  eyebrow = "Why people stay",
  title = "Small things that make the difference.",
  items = [
    { title: "Answers the same day", text: "Every message gets a real reply from a person on the team before the office closes.", icon: CHAT },
    { title: "Nothing hidden", text: "The price you are quoted is the price you pay. Extras are listed before you agree, never after.", icon: SHIELD },
    { title: "On time, every time", text: "We turn up in the window we promised, and call ahead if anything changes.", icon: CLOCK },
    { title: "Made to last", text: "We repair before we replace, and give you the old parts back if you want them.", icon: LEAF },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: IconFeature[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ul className="mt-10 grid gap-y-10 border-t border-ink-900 pt-10 sm:grid-cols-2 lg:grid-cols-4 lg:gap-y-0 lg:divide-x lg:divide-ink-200">
        {items.map((item, index) => (
          <li key={item.title} className="lg:px-6 lg:first:pl-0 lg:last:pr-0">
            <span className="text-brand-600">{item.icon ?? DEFAULT_ICONS[index % DEFAULT_ICONS.length]}</span>
            <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
            <p className="mt-2 text-ink-700">{item.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

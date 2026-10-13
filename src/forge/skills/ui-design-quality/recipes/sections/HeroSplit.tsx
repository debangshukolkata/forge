// Hero with the message on the left and a visual on the right (stacks on a phone, visual below). The headline and the
// primary action are visible without scrolling. Pass your own visual as children, or keep the ArtTile.
import type { ReactNode } from "react";
import ArtTile from "./ArtTile";

export default function HeroSplit({
  eyebrow = "Community drive · 25 October",
  title = "One hour of your day can give someone years.",
  text = "Join a one-day drive that is medically supervised, gently run, and close to home. Every donation reaches a patient in a nearby hospital.",
  primary = { label: "Reserve my slot", href: "#contact" },
  secondary = { label: "How it works", href: "#how" },
  facts = ["Sun, 25 Oct", "9:00 AM to 5:00 PM", "Community Hall"],
  children,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  primary?: { label: string; href: string };
  secondary?: { label: string; href: string };
  facts?: string[];
  children?: ReactNode;
}) {
  return (
    <section id="top" className="mx-auto grid max-w-6xl items-center gap-12 px-4 py-14 sm:px-6 md:grid-cols-2 md:py-24">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-4 text-4xl font-semibold leading-[1.08] sm:text-5xl lg:text-6xl">{title}</h1>
        <p className="mt-6 max-w-xl text-lg leading-relaxed text-ink-700">{text}</p>
        <div className="mt-8 flex flex-wrap gap-3">
          <a href={primary.href} className="btn-primary">{primary.label}</a>
          <a href={secondary.href} className="btn-secondary">{secondary.label}</a>
        </div>
        {facts.length > 0 && (
          <ul className="mt-8 flex flex-wrap gap-x-6 gap-y-2 text-sm text-ink-500">
            {facts.map((fact) => <li key={fact}>{fact}</li>)}
          </ul>
        )}
      </div>
      <div>{children ?? <ArtTile variant="orbs" />}</div>
    </section>
  );
}

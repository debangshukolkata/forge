// Three or four feature rows, text and visual swapping sides down the page (visual below the text on a phone).
// Each row: a short title, one paragraph, up to three bullet points. Pass your own visual per item, or keep the ArtTile.
import type { ReactNode } from "react";
import ArtTile, { type ArtVariant } from "./ArtTile";

export type Feature = { title: string; text: string; points?: string[]; art?: ArtVariant; visual?: ReactNode };

export default function FeaturesAlternating({
  eyebrow = "What you get",
  title = "Everything in one calm place",
  items = [
    {
      title: "Pick a time that suits you",
      text: "Choose a 30-minute slot, and we send a reminder the day before. Changing your mind takes one tap.",
      points: ["Live availability", "Reminders by email", "Free rescheduling"],
      art: "stack",
    },
    {
      title: "A health check you can trust",
      text: "A nurse checks your pulse, blood pressure and haemoglobin before anything else happens, in a private cubicle.",
      points: ["Ten minutes, start to finish", "Private and unhurried"],
      art: "bars",
    },
    {
      title: "Rest, snack, and go",
      text: "Stay for a snack and a short rest. You leave with a card that shows when you can give again.",
      points: ["Snacks and water provided", "Next date on your card"],
      art: "orbs",
    },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: Feature[];
}) {
  return (
    <section id="how" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-14 space-y-16 md:space-y-24">
        {items.map((item, index) => (
          <div key={item.title} className="grid items-center gap-8 md:grid-cols-2 md:gap-16">
            <div className={index % 2 === 1 ? "md:order-2" : ""}>
              <h3 className="text-2xl font-semibold sm:text-3xl">{item.title}</h3>
              <p className="mt-4 text-lg leading-relaxed text-ink-700">{item.text}</p>
              {item.points && (
                <ul className="mt-6 space-y-2 text-ink-700">
                  {item.points.map((point) => (
                    <li key={point} className="flex gap-3">
                      <span aria-hidden="true" className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                      {point}
                    </li>
                  ))}
                </ul>
              )}
            </div>
            <div className={index % 2 === 1 ? "md:order-1" : ""}>{item.visual ?? <ArtTile variant={item.art ?? "orbs"} />}</div>
          </div>
        ))}
      </div>
    </section>
  );
}

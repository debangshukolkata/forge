// Tabbed features: a row of tabs and one panel of text under it, so several features share one place. Real tabs: arrow keys move between them,
// Home and End jump to the ends, the selected tab is announced. Use it for three to five features that need a paragraph each.
import { useRef, useState, type KeyboardEvent } from "react";

export type FeatureTab = { label: string; title: string; text: string; points?: string[] };

export default function FeaturesTabs({
  eyebrow = "The studio, in three parts",
  title = "Everything under one roof.",
  tabs = [
    { label: "Classes", title: "Evening classes for beginners", text: "Six weeks, eight people, all clay and tools included. You leave with a set of glazed pieces and enough skill to keep going.", points: ["Tuesday and Thursday, 6:30 to 9", "No experience needed"] },
    { label: "Open studio", title: "Come and work on your own", text: "Once you have finished a course the wheels and kiln are yours by the hour, with someone around to help when something goes wrong.", points: ["Wheels booked by the hour", "Firing every second Sunday"] },
    { label: "Commissions", title: "One-off pieces made for you", text: "A set of bowls for a restaurant, a lamp base, a gift. Tell us the size and the mood and we send a sketch and a price within three days.", points: ["Sketch and price in three days", "Delivery within the city"] },
  ],
}: {
  eyebrow?: string;
  title?: string;
  tabs?: FeatureTab[];
}) {
  const [selected, setSelected] = useState(0);
  const buttons = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (event: KeyboardEvent, index: number) => {
    const last = tabs.length - 1;
    const next = { ArrowRight: index === last ? 0 : index + 1, ArrowLeft: index === 0 ? last : index - 1, Home: 0, End: last }[event.key];
    if (next === undefined) return;
    event.preventDefault();
    setSelected(next);
    buttons.current[next]?.focus();
  };
  const tab = tabs[selected];
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-3xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div role="tablist" aria-label={title} className="mt-8 flex gap-6 overflow-x-auto border-b border-ink-300">
        {tabs.map((item, index) => (
          <button
            key={item.label}
            ref={(element) => {
              buttons.current[index] = element;
            }}
            role="tab"
            id={`features-tab-${index}`}
            aria-selected={index === selected}
            aria-controls="features-panel"
            tabIndex={index === selected ? 0 : -1}
            onClick={() => setSelected(index)}
            onKeyDown={(event) => move(event, index)}
            className={`-mb-px whitespace-nowrap border-b-2 pb-3 text-sm font-semibold transition ${index === selected ? "border-brand-600 text-ink-900" : "border-transparent text-ink-500 hover:text-ink-900"}`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div id="features-panel" role="tabpanel" aria-labelledby={`features-tab-${selected}`} tabIndex={0} className="grid gap-6 pt-8 md:grid-cols-12">
        <h3 className="text-2xl font-semibold md:col-span-5">{tab.title}</h3>
        <div className="md:col-span-7">
          <p className="max-w-xl text-lg text-ink-700">{tab.text}</p>
          {tab.points && (
            <ul className="mt-5 space-y-2 text-ink-900">
              {tab.points.map((point) => (
                <li key={point} className="flex gap-3">
                  <span aria-hidden="true" className="text-brand-600">&#10003;</span>
                  {point}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

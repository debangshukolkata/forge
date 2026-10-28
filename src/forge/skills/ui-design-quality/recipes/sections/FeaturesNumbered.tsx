// Numbered features: a short intro on the left that stays in view (sticky on desktop) and a long column of numbered points on the right, each with a
// large numeral, a title and a paragraph. For a method or a set of principles that deserves reading in order. Four to eight points.
export type NumberedPoint = { title: string; text: string };

export default function FeaturesNumbered({
  eyebrow = "How we work",
  title = "Five habits behind every project.",
  text = "None of this is clever. It is the list we keep coming back to when a job gets busy.",
  items = [
    { title: "Start with the people who will use it", text: "We spend the first week in the building, talking to the people who will rely on the result, before anything is drawn." },
    { title: "Show the rough version early", text: "A half-finished plan on paper by Friday beats a polished one in a month. Mistakes are cheap while everything is still a sketch." },
    { title: "Write down what we decided", text: "Every decision gets two lines: what and why. It saves the argument six weeks later, and the new person on the team can follow it." },
    { title: "Fix the smallest thing first", text: "Small repairs build trust and teach us how the place really works, which the larger plans then have to respect." },
    { title: "Hand over with the manual", text: "The last week is spent making ourselves unnecessary: documents, a walk-through and a name to call when something breaks." },
  ],
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  items?: NumberedPoint[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <div className="grid gap-10 md:grid-cols-12">
        <div className="md:col-span-4">
          <div className="md:sticky md:top-24">
            <p className="eyebrow">{eyebrow}</p>
            <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
            <p className="mt-4 max-w-sm text-ink-700">{text}</p>
          </div>
        </div>
        <ol className="md:col-span-8">
          {items.map((item, index) => (
            <li key={item.title} className="grid gap-x-6 gap-y-2 border-t border-ink-300 py-8 first:border-t-0 first:pt-0 sm:grid-cols-[4.5rem_1fr]">
              <span className="font-display text-4xl tabular-nums text-brand-600">{String(index + 1).padStart(2, "0")}</span>
              <div>
                <h3 className="text-xl font-semibold">{item.title}</h3>
                <p className="mt-2 max-w-xl text-ink-700">{item.text}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}

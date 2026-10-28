// Vertical timeline: dated entries down the page along a thin line, the year or date large on the left and the event on the right. For a history, a
// roadmap or a project programme. Four to eight entries; the newest can come first or last, as you order the list.
export type Milestone = { when: string; title: string; text: string };

export default function TimelineVertical({
  eyebrow = "Our story",
  title = "Twenty years, in five dates.",
  items = [
    { when: "2006", title: "A kitchen table and two ovens", text: "Maria starts selling bread to neighbours on Saturdays from her own kitchen." },
    { when: "2011", title: "The first shop", text: "A unit on Harbour Street, with room for one counter and a queue that ran onto the pavement." },
    { when: "2016", title: "Baking through the night", text: "A second oven and a night shift mean the first loaves are on the shelf at six." },
    { when: "2021", title: "Flour from one mill", text: "All our flour now comes from a single mill forty miles away, milled the week we bake it." },
    { when: "2026", title: "A bakery school", text: "Evening courses open in the old warehouse next door, eight places a term." },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: Milestone[];
}) {
  return (
    <section className="mx-auto max-w-4xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ol className="mt-10 border-l border-ink-300 md:mt-14">
        {items.map((item) => (
          <li key={item.when} className="relative grid gap-x-8 pb-10 pl-6 last:pb-0 md:grid-cols-[7rem_1fr] md:pl-10">
            <span aria-hidden="true" className="absolute -left-[5px] top-3 h-2.5 w-2.5 rounded-full bg-brand-600 md:top-4" />
            <span className="font-display text-3xl font-semibold tabular-nums text-brand-600 md:text-4xl">{item.when}</span>
            <div>
              <h3 className="mt-1 text-xl font-semibold">{item.title}</h3>
              <p className="mt-2 max-w-xl text-ink-700">{item.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

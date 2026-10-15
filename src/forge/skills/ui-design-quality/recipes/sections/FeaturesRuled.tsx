// A ruled list instead of a row of cards: a large numeral, a title, one or two sentences and a small label, each row between hairlines.
// Reads like a table of contents; use it for what a service includes, the programme of a course, or the principles of a brand. Three to six rows.
// A row with `href` is a link as a whole; a row without it is plain text.
export type RuledItem = { title: string; text: string; label?: string; href?: string };

export default function FeaturesRuled({
  eyebrow = "What the course covers",
  title = "Six weeks, from the first lump of clay to a glazed set.",
  items = [
    { title: "Centring and pulling", text: "Wedge the clay, find the centre and raise a first cylinder. Every pot of the first night is thrown, and every one is allowed to fail.", label: "Weeks 1 to 2" },
    { title: "Form and trimming", text: "Turn a cylinder into a bowl, a mug or a vase, and cut a foot so it sits level and feels light in the hand.", label: "Weeks 3 to 4" },
    { title: "Glaze and fire", text: "Choose glazes from our test tiles, dip and brush them, and load the kiln together on the second Sunday.", label: "Weeks 5 to 6" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: RuledItem[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-3xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ol className="mt-10 border-y border-ink-900 md:mt-14">
        {items.map((item, index) => {
          const row = (
            <>
              <span className="font-display text-4xl tabular-nums text-brand-600 sm:text-5xl">{String(index + 1).padStart(2, "0")}</span>
              <h3 className="text-2xl font-semibold">{item.title}</h3>
              <p className="max-w-xl text-ink-700">{item.text}</p>
              {item.label && <span className="text-sm text-ink-500 md:text-right">{item.label}</span>}
            </>
          );
          const layout = "grid items-baseline gap-x-8 gap-y-2 py-7 md:grid-cols-[5rem_1fr_1.3fr_8rem]";
          return (
            <li key={item.title} className="border-b border-ink-200 last:border-b-0">
              {item.href ? (
                <a href={item.href} className={`${layout} transition hover:bg-ink-100 md:-mx-4 md:px-4`}>{row}</a>
              ) : (
                <div className={layout}>{row}</div>
              )}
            </li>
          );
        })}
      </ol>
    </section>
  );
}

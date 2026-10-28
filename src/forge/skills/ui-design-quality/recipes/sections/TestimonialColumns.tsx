// Testimonial columns: three short quotes side by side, set as plain text between hairlines with the name and role under each; no boxes, no stars.
// Use real quotes with real names and one concrete detail each. Pairs with `TestimonialFeature` (one long quote) when a page has both.
export type Quote = { text: string; name: string; role: string };

export default function TestimonialColumns({
  eyebrow = "In their words",
  title = "What the families say.",
  items = [
    { text: "The first month I was sure we would give up. By the third, my daughter was asking when the next lesson was.", name: "Priya Raman", role: "Parent of a year-4 pupil" },
    { text: "They told us honestly that we did not need the longer course. Nobody has ever done that for me before.", name: "Tom Hadley", role: "Parent, two children" },
    { text: "Small groups, patient teachers, and a printed plan after every term so we know what to practise at home.", name: "Aisha Khan", role: "Parent of a year-6 pupil" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: Quote[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-10 grid gap-10 md:mt-14 md:grid-cols-3 md:gap-0 md:divide-x md:divide-ink-200">
        {items.map((item) => (
          <figure key={item.name} className="md:px-8 md:first:pl-0 md:last:pr-0">
            <blockquote className="font-display text-xl leading-snug text-ink-900">&ldquo;{item.text}&rdquo;</blockquote>
            <figcaption className="mt-5 text-sm">
              <span className="block font-semibold text-ink-900">{item.name}</span>
              <span className="text-ink-500">{item.role}</span>
            </figcaption>
          </figure>
        ))}
      </div>
    </section>
  );
}

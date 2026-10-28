// Features with a figure each: a row of two to four points where every one leads with a large number or short word (the proof), followed by a title and
// one sentence. Use it when each feature can be backed by a specific figure; without real figures use FeaturesRuled or FeaturesIconRow instead.
export type FigureFeature = { figure: string; title: string; text: string };

export default function FeaturesFigures({
  eyebrow = "Why it works",
  title = "Three numbers behind the promise.",
  items = [
    { figure: "24 h", title: "Reply time", text: "Every enquiry is answered by a person within one working day, and usually within the hour." },
    { figure: "12 yrs", title: "Same team", text: "The people who start your project are the people who finish it; we have kept the same core team since 2014." },
    { figure: "0", title: "Surprise invoices", text: "A fixed quote before work begins. If the job grows, we tell you first and you decide." },
  ],
}: {
  eyebrow?: string;
  title?: string;
  items?: FigureFeature[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ul className="mt-10 grid gap-10 border-t border-ink-900 pt-10 md:mt-14 md:grid-cols-3 md:gap-0 md:divide-x md:divide-ink-200">
        {items.map((item) => (
          <li key={item.title} className="md:px-8 md:first:pl-0 md:last:pr-0">
            <p className="font-display text-6xl font-semibold tabular-nums text-brand-600">{item.figure}</p>
            <h3 className="mt-4 text-lg font-semibold">{item.title}</h3>
            <p className="mt-2 text-ink-700">{item.text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

// Before and after: two columns of short lines, the old way struck through in grey and the new way set in full colour with a tick, a heading over each.
// Use it where the benefit is a contrast (paper against screen, a week against an hour). Three to six lines per side; keep both sides the same length.
export default function FeaturesComparison({
  eyebrow = "What changes",
  title = "Booking a room, before and after.",
  before = { heading: "Before", items: ["Phone the office between nine and five", "Wait for a call back about availability", "Fill in a paper form on arrival", "Pay by cheque after the event"] },
  after = { heading: "With the new system", items: ["Pick a room and a time at any hour", "See it confirmed on the same page", "Check in with a code on your phone", "Pay by card and get the receipt at once"] },
}: {
  eyebrow?: string;
  title?: string;
  before?: { heading: string; items: string[] };
  after?: { heading: string; items: string[] };
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-3xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-10 grid gap-10 md:mt-14 md:grid-cols-2 md:gap-0">
        <div className="md:border-r md:border-ink-200 md:pr-10">
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-ink-500">{before.heading}</h3>
          <ul className="mt-5 space-y-4">
            {before.items.map((item) => (
              <li key={item} className="flex gap-3 text-ink-500">
                <span aria-hidden="true" className="mt-0.5">&times;</span>
                <span className="line-through decoration-ink-300">{item}</span>
              </li>
            ))}
          </ul>
        </div>
        <div className="md:pl-10">
          <h3 className="text-sm font-semibold uppercase tracking-[0.14em] text-brand-600">{after.heading}</h3>
          <ul className="mt-5 space-y-4">
            {after.items.map((item) => (
              <li key={item} className="flex gap-3 font-medium text-ink-900">
                <span aria-hidden="true" className="mt-0.5 text-brand-600">&#10003;</span>
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

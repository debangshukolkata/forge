// A row of big numbers with short labels: two columns on a phone, one row on desktop, thin dividers between.
// Use real, specific numbers; tabular figures keep them aligned.
export type Stat = { value: string; label: string };

export default function StatsRow({
  items = [
    { value: "320", label: "slots available" },
    { value: "150+", label: "units to collect" },
    { value: "450+", label: "lives supported" },
    { value: "12", label: "partner hospitals" },
  ],
}: {
  items?: Stat[];
}) {
  return (
    <section className="border-y border-ink-200 bg-white">
      <dl className="mx-auto grid max-w-6xl grid-cols-2 gap-y-8 px-4 py-10 sm:px-6 md:grid-cols-4 md:gap-y-0 md:divide-x md:divide-ink-200">
        {items.map((item) => (
          <div key={item.label} className="text-center md:px-6">
            <dd className="font-display text-4xl font-semibold tabular-nums text-ink-900 sm:text-5xl">{item.value}</dd>
            <dt className="mt-1 text-sm text-ink-500">{item.label}</dt>
          </div>
        ))}
      </dl>
    </section>
  );
}

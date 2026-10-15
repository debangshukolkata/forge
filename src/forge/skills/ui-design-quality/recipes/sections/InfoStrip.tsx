// A ruled strip of practical facts (opening hours, address, how to order, contact): a label above a value between hairlines, no boxes.
// Use it under a hero instead of three cards: the items are information, not objects. Two to four items; the row stacks on a phone.
export type InfoItem = { label: string; value: string; note?: string };

export default function InfoStrip({
  items = [
    { label: "Opening hours", value: "Tuesday to Friday, 7:30 to 3", note: "Saturday 8 to 2. Closed Sunday and Monday." },
    { label: "Find us", value: "12 Fernhill Road", note: "Two minutes from the bus stop." },
    { label: "Delivery", value: "Same day, before 11 am", note: "Pre-order loaves for weekend pick-up." },
  ],
}: {
  items?: InfoItem[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:py-14">
      <dl className="grid border-t border-ink-900 md:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="border-b border-ink-200 py-5 md:border-b-0 md:border-l md:px-6 md:first:border-l-0 md:first:pl-0">
            <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">{item.label}</dt>
            <dd className="mt-2 text-lg font-medium text-ink-900">{item.value}</dd>
            {item.note && <dd className="mt-1 text-sm text-ink-700">{item.note}</dd>}
          </div>
        ))}
      </dl>
    </section>
  );
}

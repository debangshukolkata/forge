// A ruled strip of practical facts (opening hours, address, how to order, contact): a thin line icon, a label and a value between hairlines, no boxes.
// Use it under a hero instead of three cards: the items are information, not objects. Two to four items; the row stacks on a phone.
// `icon` takes any element (the bundled Lucide icons from find_image are thin line icons that suit it); the three drawn ones are `clock`, `pin` and `basket`.
import type { ReactNode } from "react";

export type InfoItem = { label: string; value: string; note?: string; icon?: ReactNode };

const PATHS = {
  clock: "M12 7v5l3 2M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z",
  pin: "M12 21s7-6.2 7-11.5A7 7 0 0 0 5 9.5C5 14.800 12 21 12 21ZM12 12a2.500 2.500 0 1 0 0-5 2.500 2.500 0 0 0 0 5Z",
  basket: "M4 9h16l-1.500 10h-13L4 9ZM8 9l3-5M16 9l-3-5",
};

export function LineIcon({ name }: { name: keyof typeof PATHS }) {
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className="shrink-0 text-brand-600">
      <path d={PATHS[name]} />
    </svg>
  );
}

export default function InfoStrip({
  items = [
    { label: "Opening hours", value: "Tuesday to Friday, 7:30 to 3", note: "Saturday 8 to 2. Closed Sunday and Monday.", icon: <LineIcon name="clock" /> },
    { label: "Find us", value: "12 Fernhill Road", note: "Two minutes from the bus stop.", icon: <LineIcon name="pin" /> },
    { label: "Delivery", value: "Same day, before 11 am", note: "Pre-order loaves for weekend pick-up.", icon: <LineIcon name="basket" /> },
  ],
}: {
  items?: InfoItem[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-10 sm:px-6 md:py-14">
      <dl className="grid border-t border-ink-900 md:grid-cols-3">
        {items.map((item) => (
          <div key={item.label} className="flex gap-4 border-b border-ink-200 py-5 md:border-b-0 md:border-l md:px-6 md:first:border-l-0 md:first:pl-0">
            {item.icon}
            <div>
              <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">{item.label}</dt>
              <dd className="mt-2 text-lg font-medium text-ink-900">{item.value}</dd>
              {item.note && <dd className="mt-1 text-sm text-ink-700">{item.note}</dd>}
            </div>
          </div>
        ))}
      </dl>
    </section>
  );
}

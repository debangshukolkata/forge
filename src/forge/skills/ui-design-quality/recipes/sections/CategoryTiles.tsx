// Three large category tiles that each lead to a part of the shop or site: a short label, a one-line promise and an arrow. One column on a phone, three on desktop.
// The first tile is filled with the brand colour; keep the other two quiet. Every tile is one link, so the whole card is the target.
export type Category = { label: string; text: string; href: string };

export default function CategoryTiles({
  categories = [
    { label: "For the table", text: "Mugs, jugs, boards and linen.", href: "#shop" },
    { label: "For the home", text: "Candles, throws and small brass things.", href: "#shop" },
    { label: "Gifts", text: "Wrapped, with a handwritten note.", href: "#shop" },
  ],
}: {
  categories?: Category[];
}) {
  return (
    <section aria-label="Categories" className="mx-auto max-w-6xl px-4 pb-4 pt-4 sm:px-6">
      <ul className="grid gap-4 md:grid-cols-3">
        {categories.map((category, index) => (
          <li key={category.label}>
            <a
              href={category.href}
              className={`group flex h-full min-h-44 flex-col justify-between rounded-card border p-6 transition duration-200 hover:-translate-y-1 hover:shadow-lift ${
                index === 0 ? "border-brand-600 bg-brand-600 text-white" : "border-ink-200 bg-white text-ink-900"
              }`}
            >
              <span className="font-display text-2xl font-semibold">{category.label}</span>
              <span className="flex items-end justify-between gap-4">
                <span className={`max-w-[18ch] text-sm ${index === 0 ? "text-white/90" : "text-ink-700"}`}>{category.text}</span>
                <span aria-hidden="true" className="text-2xl transition group-hover:translate-x-1">&rarr;</span>
              </span>
            </a>
          </li>
        ))}
      </ul>
    </section>
  );
}

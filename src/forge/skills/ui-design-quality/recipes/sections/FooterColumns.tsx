// Footer: brand and one sentence on the left, up to three link columns on the right, a legal line underneath.
export type FooterColumn = { heading: string; links: { label: string; href: string }[] };

export default function FooterColumns({
  brand = "Brand name",
  blurb = "A community drive run by volunteers, with the support of local hospitals.",
  columns = [
    { heading: "The drive", links: [{ label: "How it works", href: "#how" }, { label: "FAQ", href: "#faq" }, { label: "Register", href: "#contact" }] },
    { heading: "Contact", links: [{ label: "help@example.org", href: "mailto:help@example.org" }, { label: "Community Hall, Park Road", href: "#top" }] },
  ],
  legal = "© 2026 Brand name. All rights reserved.",
}: {
  brand?: string;
  blurb?: string;
  columns?: FooterColumn[];
  legal?: string;
}) {
  return (
    <footer className="border-t border-ink-200 bg-white">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 md:grid-cols-[1.4fr_2fr]">
        <div>
          <p className="font-display text-xl font-semibold text-ink-900">{brand}</p>
          <p className="mt-3 max-w-sm text-ink-700">{blurb}</p>
        </div>
        <div className="grid gap-8 sm:grid-cols-2">
          {columns.map((column) => (
            <nav key={column.heading} aria-label={column.heading}>
              <h2 className="font-sans text-sm font-semibold text-ink-900">{column.heading}</h2>
              <ul className="mt-3 space-y-2">
                {column.links.map((link) => (
                  <li key={link.label}><a href={link.href} className="text-ink-700 transition hover:text-brand-600">{link.label}</a></li>
                ))}
              </ul>
            </nav>
          ))}
        </div>
      </div>
      <p className="border-t border-ink-200 py-5 text-center text-sm text-ink-500">{legal}</p>
    </footer>
  );
}

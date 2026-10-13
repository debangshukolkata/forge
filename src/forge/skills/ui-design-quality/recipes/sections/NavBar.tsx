// Sticky top navigation: brand, links, one call to action. On a phone the links open in a native <details> menu
// (no JavaScript, keyboard accessible). Needs the btn-primary utility from index.css.
export type NavLink = { label: string; href: string };

export default function NavBar({
  brand = "Brand name",
  links = [
    { label: "How it works", href: "#how" },
    { label: "Stories", href: "#stories" },
    { label: "FAQ", href: "#faq" },
  ],
  cta = { label: "Get started", href: "#contact" },
}: {
  brand?: string;
  links?: NavLink[];
  cta?: NavLink;
}) {
  return (
    <header className="sticky top-0 z-30 border-b border-ink-200/70 bg-ink-50/90 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
        <a href="#top" className="font-display text-xl font-semibold text-ink-900">{brand}</a>
        <nav aria-label="Main" className="hidden items-center gap-8 text-sm font-medium text-ink-700 md:flex">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="transition hover:text-brand-600">{link.label}</a>
          ))}
        </nav>
        <div className="flex items-center gap-3">
          <a href={cta.href} className="btn-primary !px-5 !py-2.5">{cta.label}</a>
          <details className="relative md:hidden">
            <summary className="grid h-10 w-10 cursor-pointer list-none place-items-center rounded-full border border-ink-300 text-ink-900" aria-label="Menu">
              <span className="block h-0.5 w-4 bg-current shadow-[0_5px_0_currentColor,0_-5px_0_currentColor]" />
            </summary>
            <div className="absolute right-0 top-12 w-56 rounded-2xl border border-ink-200 bg-white p-2 shadow-lift">
              {links.map((link) => (
                <a key={link.href} href={link.href} className="block rounded-xl px-4 py-3 text-sm font-medium text-ink-900 hover:bg-ink-100">
                  {link.label}
                </a>
              ))}
            </div>
          </details>
        </div>
      </div>
    </header>
  );
}

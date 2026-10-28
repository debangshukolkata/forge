// Centred navigation: the brand in the middle of the bar, links split to its left and right, one call to action at the far right. Gives a calm,
// symmetrical top for studios, restaurants and shops. On a phone the brand stays and the links open in a native <details> menu (no JavaScript).
// `links` is split in half around the brand; keep an even number of links, two to six. Needs the btn-primary utility from index.css.
export type CenteredNavLink = { label: string; href: string };

export default function NavCentered({
  brand = "Brand name",
  links = [
    { label: "Menu", href: "#menu" },
    { label: "Our story", href: "#story" },
    { label: "Visit", href: "#visit" },
    { label: "Journal", href: "#journal" },
  ],
  cta = { label: "Book a table", href: "#contact" },
}: {
  brand?: string;
  links?: CenteredNavLink[];
  cta?: CenteredNavLink;
}) {
  const half = Math.ceil(links.length / 2);
  const link = (item: CenteredNavLink) => (
    <a key={item.href} href={item.href} className="transition hover:text-brand-600">{item.label}</a>
  );
  return (
    <header className="sticky top-0 z-30 border-b border-ink-200/70 bg-ink-50/90 backdrop-blur">
      <div className="mx-auto grid h-16 max-w-6xl grid-cols-[1fr_auto_1fr] items-center gap-4 px-4 sm:px-6">
        <nav aria-label="Main" className="hidden items-center gap-8 text-sm font-medium text-ink-700 md:flex">
          {links.slice(0, half).map(link)}
        </nav>
        <details className="relative md:hidden">
          <summary className="grid h-10 w-10 cursor-pointer list-none place-items-center rounded-full border border-ink-300 text-ink-900" aria-label="Menu">
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" aria-hidden="true"><path d="M4 7h16M4 12h16M4 17h16" /></svg>
          </summary>
          <nav aria-label="Menu" className="absolute left-0 top-12 z-40 flex w-56 flex-col rounded-2xl border border-ink-200 bg-white p-2 shadow-lift">
            {links.map((item) => (
              <a key={item.href} href={item.href} className="rounded-xl px-4 py-3 text-sm font-medium text-ink-900 hover:bg-ink-100">{item.label}</a>
            ))}
          </nav>
        </details>
        <a href="#top" className="justify-self-center font-display text-xl font-semibold text-ink-900 md:col-start-2">{brand}</a>
        <div className="flex items-center justify-end gap-8">
          <nav aria-label="More" className="hidden items-center gap-8 text-sm font-medium text-ink-700 md:flex">
            {links.slice(half).map(link)}
          </nav>
          <a href={cta.href} className="btn-primary !px-5 !py-2.5">{cta.label}</a>
        </div>
      </div>
    </header>
  );
}

// Centred footer: a large brand name, one sentence under it, a single row of links and the legal line, all centred. Suits studios, shops and
// event pages where the footer is the last, quiet word. Keep the links to five or fewer.
export type CenteredFooterLink = { label: string; href: string };

export default function FooterCentered({
  brand = "Brand name",
  blurb = "A small studio on Mill Lane, open Wednesday to Sunday.",
  links = [
    { label: "Classes", href: "#classes" },
    { label: "Studio hire", href: "#hire" },
    { label: "Journal", href: "#journal" },
    { label: "Contact", href: "#contact" },
  ],
  legal = "© 2026 Brand name. All rights reserved.",
}: {
  brand?: string;
  blurb?: string;
  links?: CenteredFooterLink[];
  legal?: string;
}) {
  return (
    <footer className="border-t border-ink-900 bg-ink-50">
      <div className="mx-auto max-w-3xl px-4 py-14 text-center sm:px-6 md:py-20">
        <p className="font-display text-4xl font-semibold text-ink-900 sm:text-5xl">{brand}</p>
        <p className="mx-auto mt-4 max-w-md text-ink-700">{blurb}</p>
        <nav aria-label="Footer" className="mt-8 flex flex-wrap justify-center gap-x-8 gap-y-3 text-sm font-semibold text-ink-900">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="underline decoration-ink-300 underline-offset-4 hover:decoration-brand-600">{link.label}</a>
          ))}
        </nav>
        <p className="mt-10 text-sm text-ink-500">{legal}</p>
      </div>
    </footer>
  );
}

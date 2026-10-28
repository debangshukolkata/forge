// Minimal footer: one line with the brand and legal text on the left and a few plain links on the right, nothing else. For short pages, one-page
// sites and anything where a column footer would be heavier than the page above it. Stacks on a phone.
export type FooterLink = { label: string; href: string };

export default function FooterMinimal({
  brand = "Brand name",
  legal = "© 2026 Brand name. All rights reserved.",
  links = [
    { label: "Privacy", href: "#privacy" },
    { label: "Terms", href: "#terms" },
    { label: "Contact", href: "#contact" },
  ],
}: {
  brand?: string;
  legal?: string;
  links?: FooterLink[];
}) {
  return (
    <footer className="border-t border-ink-200">
      <div className="mx-auto flex max-w-6xl flex-col gap-4 px-4 py-8 text-sm sm:px-6 md:flex-row md:items-center md:justify-between">
        <p className="text-ink-500">
          <span className="mr-3 font-display text-base font-semibold text-ink-900">{brand}</span>
          {legal}
        </p>
        <nav aria-label="Footer" className="flex flex-wrap gap-x-6 gap-y-2 font-medium text-ink-700">
          {links.map((link) => (
            <a key={link.href} href={link.href} className="hover:text-brand-600">{link.label}</a>
          ))}
        </nav>
      </div>
    </footer>
  );
}

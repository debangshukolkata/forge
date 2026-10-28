// Page header for an inner page: breadcrumbs, the page's own h1, a one-sentence introduction and an optional line of facts (updated date, reading time, owner).
// Use it at the top of any page that is not the home page (a service, an article, a policy, a product). The breadcrumb is a real navigation landmark and the
// last item is the current page, announced as such. Keep the title to one line where you can.
export type Crumb = { label: string; href?: string };

export default function PageHeader({
  crumbs = [
    { label: "Home", href: "#top" },
    { label: "Services", href: "#services" },
    { label: "Family law" },
  ],
  title = "Family law",
  intro = "Advice on separation, divorce and arrangements for children, from a first conversation to a final order.",
  facts = [
    { label: "Updated", value: "3 October 2026" },
    { label: "Reading time", value: "4 minutes" },
  ],
}: {
  crumbs?: Crumb[];
  title?: string;
  intro?: string;
  facts?: { label: string; value: string }[];
}) {
  return (
    <header id="top" className="mx-auto max-w-6xl border-b border-ink-200 px-4 pb-10 pt-8 sm:px-6 md:pb-14 md:pt-12">
      <nav aria-label="Breadcrumb">
        <ol className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-ink-500">
          {crumbs.map((crumb, index) => (
            <li key={crumb.label} className="flex items-center gap-2">
              {index > 0 && <span aria-hidden="true">/</span>}
              {crumb.href && index < crumbs.length - 1 ? (
                <a href={crumb.href} className="font-medium text-ink-700 underline decoration-ink-300 underline-offset-4 hover:decoration-brand-600">{crumb.label}</a>
              ) : (
                <span aria-current="page" className="font-medium text-ink-900">{crumb.label}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>
      <h1 className="mt-6 max-w-3xl text-4xl font-semibold leading-[1.05] sm:text-5xl">{title}</h1>
      <p className="mt-5 max-w-2xl text-lg leading-relaxed text-ink-700">{intro}</p>
      {facts.length > 0 && (
        <dl className="mt-6 flex flex-wrap gap-x-8 gap-y-2 text-sm">
          {facts.map((fact) => (
            <div key={fact.label} className="flex gap-2">
              <dt className="text-ink-500">{fact.label}</dt>
              <dd className="font-medium text-ink-900">{fact.value}</dd>
            </div>
          ))}
        </dl>
      )}
    </header>
  );
}

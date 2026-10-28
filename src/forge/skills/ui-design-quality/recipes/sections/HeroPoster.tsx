// Poster hero: giant type on a solid brand-colour field, edge to edge, with a thin information bar below. Loud and short: use it for events, launches
// and campaigns, with a headline of one to three words. The text on the field is white; keep the brand colour dark enough for contrast (the token files are).
export default function HeroPoster({
  title = ["Late", "Summer", "Sessions"],
  kicker = "Three nights of live music on the river",
  details = [
    { label: "When", value: "5 to 7 September" },
    { label: "Where", value: "Riverside Park, East Gate" },
    { label: "Tickets", value: "From £18" },
  ],
  action = { label: "Get tickets", href: "#tickets" },
}: {
  title?: string[];
  kicker?: string;
  details?: { label: string; value: string }[];
  action?: { label: string; href: string };
}) {
  return (
    <section id="top">
      <div className="bg-brand-600 text-white">
        <div className="mx-auto max-w-6xl px-4 pb-10 pt-12 sm:px-6 md:pb-14 md:pt-20">
          <p className="text-sm font-semibold uppercase tracking-[0.14em] text-white">{kicker}</p>
          <h1 className="mt-4 font-display text-6xl font-semibold uppercase leading-[0.9] tracking-tight text-white sm:text-8xl lg:text-[9.5rem]">
            {title.map((line) => (
              <span key={line} className="block">{line}</span>
            ))}
          </h1>
        </div>
      </div>
      <div className="border-b border-ink-900 bg-white">
        <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-5 sm:px-6 md:flex-row md:items-center md:justify-between">
          <dl className="grid gap-4 sm:grid-cols-3 md:gap-10">
            {details.map((detail) => (
              <div key={detail.label}>
                <dt className="text-xs font-semibold uppercase tracking-[0.14em] text-ink-500">{detail.label}</dt>
                <dd className="font-semibold text-ink-900">{detail.value}</dd>
              </div>
            ))}
          </dl>
          <a href={action.href} className="btn-primary self-start md:self-auto">{action.label}</a>
        </div>
      </div>
    </section>
  );
}

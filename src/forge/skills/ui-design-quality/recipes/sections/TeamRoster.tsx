// Team roster: people listed as rows (name, role, a one-line note, a contact link) between hairlines, with an initial-letter badge where a photo would go.
// Quieter and faster to scan than a grid of portrait cards; pass `photo` per person to show a real picture instead of the badge.
export type Person = { name: string; role: string; note: string; href?: string; photo?: string };

export default function TeamRoster({
  eyebrow = "The people",
  title = "Who you will be working with.",
  people = [
    { name: "Mira Okafor", role: "Founder and lead architect", note: "Trained in Lagos and Glasgow. Reads every drawing before it leaves the office.", href: "mailto:mira@studio.example" },
    { name: "Daniel Voss", role: "Project manager", note: "Keeps the programme honest and phones you before you have to phone him.", href: "mailto:daniel@studio.example" },
    { name: "Hana Sato", role: "Interior designer", note: "Chooses materials you can still repair in twenty years.", href: "mailto:hana@studio.example" },
    { name: "Luis Ferreira", role: "Site lead", note: "On site every morning at seven; the person to call about anything physical.", href: "mailto:luis@studio.example" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  people?: Person[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ul className="mt-10 border-y border-ink-900 md:mt-14">
        {people.map((person) => (
          <li key={person.name} className="grid items-center gap-x-6 gap-y-2 border-b border-ink-200 py-6 last:border-b-0 md:grid-cols-[4rem_1.1fr_1.6fr_auto]">
            {person.photo ? (
              <img src={person.photo} alt="" className="h-14 w-14 rounded-full object-cover" />
            ) : (
              <span aria-hidden="true" className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-100 p-2 font-display text-xl font-semibold text-brand-700">
                {person.name.charAt(0)}
              </span>
            )}
            <div>
              <h3 className="text-lg font-semibold">{person.name}</h3>
              <p className="text-sm text-ink-500">{person.role}</p>
            </div>
            <p className="text-ink-700">{person.note}</p>
            {person.href && <a href={person.href} className="text-sm font-semibold text-brand-600 underline underline-offset-4">Get in touch</a>}
          </li>
        ))}
      </ul>
    </section>
  );
}

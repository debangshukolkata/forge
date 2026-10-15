// People cards: an initials avatar (replace with a photograph), name, role and one line about the talk. Two columns on a phone, four on desktop.
// Use for speakers, a team or advisers. Keep the line under 90 characters; the name is a heading so the list is easy to navigate.
export type Person = { name: string; role: string; line: string };

export default function SpeakerGrid({
  eyebrow = "Speakers",
  title = "People who build it every day",
  people = [
    { name: "Maya Lindqvist", role: "Design lead, Nordlys", line: "Why the best interface is the one you stop noticing." },
    { name: "Tomas Ruiz", role: "Staff engineer, Kestrel", line: "Design tokens across four platforms and one rebrand." },
    { name: "Ines Okafor", role: "Data journalist", line: "Charts that stay honest on a phone screen." },
    { name: "Sven Aalto", role: "Performance engineer", line: "A budget for every page, and how to keep to it." },
    { name: "Priya Nair", role: "Content designer", line: "Writing the words people actually read." },
    { name: "Daniel Cho", role: "VP Product, Harbour", line: "Lessons from shipping to forty million people." },
    { name: "Aiko Tanaka", role: "Accessibility specialist", line: "Testing with the people who rely on it." },
    { name: "Leo Marchetti", role: "Founder, Studio Loom", line: "Small teams, long-lived software." },
  ],
}: {
  eyebrow?: string;
  title?: string;
  people?: Person[];
}) {
  const initials = (name: string) => name.split(" ").map((part) => part[0]).join("").slice(0, 2);
  return (
    <section id="speakers" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ul className="mt-12 grid grid-cols-2 gap-x-4 gap-y-10 lg:grid-cols-4">
        {people.map((person) => (
          <li key={person.name}>
            <div aria-hidden="true" className="grid aspect-square w-full place-items-center rounded-card bg-gradient-to-br from-brand-100 to-brand-200 font-display text-5xl font-semibold text-brand-700">
              {initials(person.name)}
            </div>
            <h3 className="mt-4 text-base font-semibold">{person.name}</h3>
            <p className="text-sm font-medium text-brand-700">{person.role}</p>
            <p className="mt-1 text-sm text-ink-700">{person.line}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

// "Trusted by" row. Uses the customers' names in muted display type; swap for real logos (SVG, same height) when you have them.
export default function LogoStrip({
  label = "Trusted by teams at",
  names = ["Northwind", "Meridian Health", "Bluebird", "Fieldwork", "Orbit Labs"],
}: {
  label?: string;
  names?: string[];
}) {
  return (
    <section aria-label={label} className="mx-auto max-w-6xl px-4 py-10 sm:px-6">
      <p className="text-center text-sm font-medium text-ink-500">{label}</p>
      <ul className="mt-6 flex flex-wrap items-center justify-center gap-x-10 gap-y-4">
        {names.map((name) => (
          <li key={name} className="font-display text-xl font-semibold tracking-tight text-ink-500">{name}</li>
        ))}
      </ul>
    </section>
  );
}

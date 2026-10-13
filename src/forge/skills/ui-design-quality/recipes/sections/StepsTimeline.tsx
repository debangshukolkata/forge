// Numbered steps joined by a vertical line: heading on the left, the steps on the right on desktop, stacked on a phone.
// Three to five steps; each is one short title and one or two sentences.
export type Step = { title: string; text: string };

export default function StepsTimeline({
  eyebrow = "How it works",
  title = "Three steps, about 45 minutes in total",
  intro = "Nothing to prepare. Bring a photo ID and drink plenty of water the day before.",
  steps = [
    { title: "Pick a slot", text: "Choose a 30-minute time that suits you. We email a reminder the day before." },
    { title: "Quick health check", text: "A nurse checks your pulse, blood pressure and haemoglobin. It takes ten minutes." },
    { title: "Donate and rest", text: "The donation takes about eight minutes. Stay for a snack and a short rest." },
  ],
}: {
  eyebrow?: string;
  title?: string;
  intro?: string;
  steps?: Step[];
}) {
  return (
    <section className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-[1fr_1.4fr] md:gap-16 md:py-24">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
        <p className="mt-4 text-lg text-ink-700">{intro}</p>
      </div>
      <ol className="relative space-y-10 before:absolute before:bottom-4 before:left-[1.1rem] before:top-4 before:w-px before:bg-ink-200">
        {steps.map((step, index) => (
          <li key={step.title} className="relative flex gap-5">
            <span className="relative z-10 grid h-9 w-9 shrink-0 place-items-center rounded-full p-1 bg-brand-600 text-sm font-semibold text-white">
              {index + 1}
            </span>
            <div className="pt-1">
              <h3 className="text-xl font-semibold">{step.title}</h3>
              <p className="mt-1 text-ink-700">{step.text}</p>
            </div>
          </li>
        ))}
      </ol>
    </section>
  );
}

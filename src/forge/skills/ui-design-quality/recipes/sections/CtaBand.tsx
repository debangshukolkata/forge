// Full-width closing band on the darkest colour: one sentence and one action. Put it just before the footer.
export default function CtaBand({
  title = "Ready when you are.",
  text = "Reserve a slot in under a minute. We will remind you the day before.",
  action = { label: "Reserve my slot", href: "#contact" },
}: {
  title?: string;
  text?: string;
  action?: { label: string; href: string };
}) {
  return (
    <section className="bg-ink-900">
      <div className="mx-auto flex max-w-6xl flex-col items-start justify-between gap-8 px-4 py-14 sm:px-6 md:flex-row md:items-center md:py-16">
        <div className="max-w-xl">
          <h2 className="text-3xl font-semibold !text-ink-50 sm:text-4xl">{title}</h2>
          <p className="mt-3 text-lg text-ink-300">{text}</p>
        </div>
        <a href={action.href} className="btn-primary shrink-0">{action.label}</a>
      </div>
    </section>
  );
}

// One large quote with the person's name and role. A single strong, specific quote beats a grid of vague ones.
export default function TestimonialFeature({
  quote = "I was nervous for a week and fine within five minutes. The nurse talked me through every step, and I was back at my desk by noon.",
  name = "Meera Banerjee",
  role = "First-time donor, teacher",
}: {
  quote?: string;
  name?: string;
  role?: string;
}) {
  const initials = name.split(" ").map((part) => part[0]).join("").slice(0, 2);
  return (
    <section id="stories" className="bg-brand-50">
      <figure className="mx-auto max-w-4xl px-4 py-16 text-center sm:px-6 md:py-24">
        <blockquote className="font-display text-2xl font-medium leading-snug text-ink-900 sm:text-3xl md:text-4xl">
          “{quote}”
        </blockquote>
        <figcaption className="mt-8 flex items-center justify-center gap-4 text-left">
          <span aria-hidden="true" className="grid h-12 w-12 place-items-center rounded-full p-1 bg-brand-600 font-semibold text-white">
            {initials}
          </span>
          <span>
            <span className="block font-semibold text-ink-900">{name}</span>
            <span className="block text-sm text-ink-500">{role}</span>
          </span>
        </figcaption>
      </figure>
    </section>
  );
}

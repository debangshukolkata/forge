// Questions and answers in native <details> elements: keyboard accessible, no JavaScript, content visible to search.
// Answer the real objections (cost, time, risk, who it is for) in two or three sentences each.
export type Faq = { question: string; answer: string };

export default function FaqList({
  title = "Questions, answered",
  items = [
    { question: "Who can donate?", answer: "Anyone aged 18 to 65 who weighs at least 50 kg and feels well on the day. The nurse checks your haemoglobin and blood pressure first, so you will know straight away if today is not the right day." },
    { question: "Does it hurt?", answer: "You feel a small pinch when the needle goes in, and nothing after that. Most people read or chat during the donation." },
    { question: "How long does it take?", answer: "About 45 minutes in total: ten minutes for the health check, eight for the donation and the rest for a snack and a short sit." },
    { question: "Can I eat before I come?", answer: "Yes, please do. Eat a normal meal and drink a litre of water in the hours before your slot." },
  ],
}: {
  title?: string;
  items?: Faq[];
}) {
  return (
    <section id="faq" className="mx-auto max-w-3xl px-4 py-16 sm:px-6 md:py-24">
      <h2 className="text-center text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-10 divide-y divide-ink-200 overflow-hidden rounded-card border border-ink-200 bg-white shadow-soft">
        {items.map((item) => (
          <details key={item.question} className="group px-6 py-5">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-4 text-lg font-semibold text-ink-900">
              {item.question}
              <span aria-hidden="true" className="text-2xl font-normal text-ink-500 transition group-open:rotate-45">+</span>
            </summary>
            <p className="mt-3 leading-relaxed text-ink-700">{item.answer}</p>
          </details>
        ))}
      </div>
    </section>
  );
}

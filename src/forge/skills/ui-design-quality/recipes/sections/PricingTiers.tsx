// Three plans side by side (stacked on a phone), the recommended one lifted and filled. Prices are plain text so any
// currency or period works. One primary button per plan; only the recommended plan uses the primary style.
export type Plan = { name: string; price: string; period?: string; text: string; features: string[]; cta: string; featured?: boolean };

export default function PricingTiers({
  eyebrow = "Pricing",
  title = "Simple plans, no surprises",
  plans = [
    { name: "Starter", price: "$0", period: "forever", text: "For trying it out on one project.", features: ["1 project", "Weekly briefing", "Email support"], cta: "Start free" },
    { name: "Team", price: "$24", period: "per month", text: "For small teams who report every week.", features: ["10 projects", "Daily briefing", "Alerts", "Priority support"], cta: "Choose Team", featured: true },
    { name: "Business", price: "$79", period: "per month", text: "For organisations with many sources.", features: ["Unlimited projects", "Single sign-on", "Audit log", "Onboarding call"], cta: "Talk to us" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  plans?: Plan[];
}) {
  return (
    <section id="pricing" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <div className="text-center">
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
      </div>
      <div className="mt-12 grid items-stretch gap-6 md:grid-cols-3">
        {plans.map((plan) => (
          <article
            key={plan.name}
            className={`flex flex-col rounded-card border p-8 ${
              plan.featured ? "border-brand-600 bg-white shadow-lift md:-my-3 md:py-11" : "border-ink-200 bg-white shadow-soft"
            }`}
          >
            <h3 className="text-xl font-semibold">{plan.name}</h3>
            <p className="mt-1 text-ink-700">{plan.text}</p>
            <p className="mt-6 flex items-baseline gap-2">
              <span className="font-display text-5xl font-semibold tabular-nums text-ink-900">{plan.price}</span>
              {plan.period && <span className="text-sm text-ink-500">{plan.period}</span>}
            </p>
            <ul className="mt-6 flex-1 space-y-3 text-ink-700">
              {plan.features.map((feature) => (
                <li key={feature} className="flex gap-3">
                  <span aria-hidden="true" className="mt-2.5 h-1.5 w-1.5 shrink-0 rounded-full bg-brand-600" />
                  {feature}
                </li>
              ))}
            </ul>
            <a href="#contact" className={`mt-8 ${plan.featured ? "btn-primary" : "btn-secondary"}`}>{plan.cta}</a>
          </article>
        ))}
      </div>
    </section>
  );
}

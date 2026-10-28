// Pricing table: plans as columns of one real table, features as rows with ticks and dashes, the price and a button in the header. Reads as a
// comparison, so use it when plans differ in many small ways; `PricingTiers` suits two or three plans that differ in a few. The table scrolls sideways
// inside its own box on a phone, with the feature names kept in view.
export type Plan = { name: string; price: string; period?: string; href: string; cta?: string; highlight?: boolean };
export type PlanFeature = { label: string; values: (boolean | string)[] };

export default function PricingTable({
  eyebrow = "Pricing",
  title = "Pick the plan that fits your team.",
  plans = [
    { name: "Starter", price: "£0", period: "free", href: "#start", cta: "Start free" },
    { name: "Team", price: "£12", period: "per user, per month", href: "#team", cta: "Choose Team", highlight: true },
    { name: "Business", price: "£29", period: "per user, per month", href: "#business", cta: "Talk to us" },
  ],
  features = [
    { label: "Projects", values: ["3", "Unlimited", "Unlimited"] },
    { label: "Team members", values: ["1", "Up to 25", "Unlimited"] },
    { label: "Shared calendars", values: [false, true, true] },
    { label: "Version history", values: ["7 days", "1 year", "Forever"] },
    { label: "Single sign-on", values: [false, false, true] },
    { label: "Priority support", values: [false, true, true] },
  ],
}: {
  eyebrow?: string;
  title?: string;
  plans?: Plan[];
  features?: PlanFeature[];
}) {
  const cell = (value: boolean | string) =>
    value === true ? <span aria-label="Included" className="text-brand-600">&#10003;</span> : value === false ? <span role="img" aria-label="Not included" className="inline-block h-px w-3 bg-ink-500 align-middle" /> : value;
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-10 overflow-x-auto md:mt-14">
        <table className="w-full min-w-[34rem] border-collapse text-left">
          <caption className="sr-only">Plans compared</caption>
          <thead>
            <tr className="border-b border-ink-900 align-bottom">
              <td className="w-1/4 pb-6" />
              {plans.map((plan) => (
                <th key={plan.name} scope="col" className={`pb-6 pr-4 align-bottom font-normal ${plan.highlight ? "text-brand-600" : "text-ink-900"}`}>
                  <span className="block text-sm font-semibold uppercase tracking-[0.14em]">{plan.name}</span>
                  <span className="mt-2 block font-display text-4xl font-semibold tabular-nums text-ink-900">{plan.price}</span>
                  {plan.period && <span className="block text-sm text-ink-500">{plan.period}</span>}
                  <a href={plan.href} className={`mt-4 ${plan.highlight ? "btn-primary" : "btn-secondary"}`}>{plan.cta ?? "Choose"}</a>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {features.map((feature) => (
              <tr key={feature.label} className="border-b border-ink-200">
                <th scope="row" className="py-4 pr-4 font-medium text-ink-900">{feature.label}</th>
                {feature.values.map((value, index) => (
                  <td key={plans[index]?.name ?? index} className="py-4 pr-4 text-ink-700">{cell(value)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

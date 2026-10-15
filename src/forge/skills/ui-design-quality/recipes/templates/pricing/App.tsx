import NavBar from "./sections/NavBar";
import HeroCentered from "./sections/HeroCentered";
import LogoStrip from "./sections/LogoStrip";
import PricingTiers from "./sections/PricingTiers";
import StatsRow from "./sections/StatsRow";
import FaqList from "./sections/FaqList";
import CtaBand from "./sections/CtaBand";
import FooterColumns from "./sections/FooterColumns";

// Pricing page: Outfit and Manrope, burnt orange on cool slate. The example prices a fictional invoicing tool ("Ledgerly");
// replace every plan, price, limit and answer with the real ones. Keep three plans and one filled button, on the plan you want chosen.
export default function App() {
  return (
    <>
      <NavBar
        brand="Ledgerly"
        links={[
          { label: "Plans", href: "#pricing" },
          { label: "Questions", href: "#faq" },
        ]}
        cta={{ label: "Start free", href: "#pricing" }}
      />
      <main>
        <HeroCentered
          eyebrow="Pricing"
          title="Pay for the invoices you send, nothing else."
          text="Every plan includes reminders, bank matching and exports. Change or cancel whenever you like; we refund the unused part of the month."
          primary={{ label: "Compare plans", href: "#pricing" }}
          secondary={{ label: "Read the questions", href: "#faq" }}
          note="Free for the first 5 invoices every month."
        />
        <LogoStrip label="Used by small businesses such as" names={["Alder & Finch", "Northgate Print", "Tidewater Cafe", "Kiln Studio", "Plum Yard"]} />
        <PricingTiers
          eyebrow="Plans"
          title="Choose the size of your business"
          plans={[
            { name: "Solo", price: "$0", period: "free", text: "For freelancers sending a few invoices.", features: ["5 invoices a month", "Payment reminders", "PDF export"], cta: "Start free" },
            { name: "Studio", price: "$19", period: "per month", text: "For small teams that invoice every week.", features: ["Unlimited invoices", "Bank matching", "3 users", "Priority email support"], cta: "Choose Studio", featured: true },
            { name: "Firm", price: "$59", period: "per month", text: "For accountants managing many clients.", features: ["Everything in Studio", "20 users", "Client portal", "Audit log"], cta: "Talk to us" },
          ]}
        />
        <StatsRow
          items={[
            { value: "4 min", label: "to send a first invoice" },
            { value: "9 days", label: "faster payment on average" },
            { value: "30 days", label: "money-back guarantee" },
          ]}
        />
        <FaqList
          title="Questions about billing"
          items={[
            { question: "Can I change plan later?", answer: "Yes, at any time. An upgrade starts at once; a downgrade starts at the next billing date." },
            { question: "What happens if I go over the free limit?", answer: "Nothing is lost. We ask you to pick a plan before the sixth invoice is sent." },
            { question: "Do you charge VAT?", answer: "Prices exclude VAT; it is added at checkout for customers in the EU and the UK." },
            { question: "How do refunds work?", answer: "Within 30 days of paying, write to us and the full amount returns to your card." },
          ]}
        />
        <CtaBand title="Send your first invoice today." text="It takes four minutes, and the first five every month are free." action={{ label: "Start free", href: "#pricing" }} />
      </main>
      <FooterColumns
        brand="Ledgerly"
        blurb="Invoicing for small businesses, made in Lisbon."
        columns={[
          { heading: "Product", links: [{ label: "Plans", href: "#pricing" }, { label: "Questions", href: "#faq" }] },
          { heading: "Contact", links: [{ label: "help@ledgerly.example", href: "mailto:help@ledgerly.example" }] },
        ]}
        legal="© 2026 Ledgerly. All rights reserved."
      />
    </>
  );
}

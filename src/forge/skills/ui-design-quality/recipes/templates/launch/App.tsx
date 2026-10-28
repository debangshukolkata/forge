import NavBar from "./sections/NavBar";
import HeroSignup from "./sections/HeroSignup";
import LogoStrip from "./sections/LogoStrip";
import FeaturesTabs from "./sections/FeaturesTabs";
import FeaturesComparison from "./sections/FeaturesComparison";
import PricingTable from "./sections/PricingTable";
import FaqList from "./sections/FaqList";
import NewsletterBand from "./sections/NewsletterBand";
import FooterMinimal from "./sections/FooterMinimal";

// Product launch or waiting list: indigo on neutral grey (Space Grotesk + Inter), one e-mail field in the first view, then proof, the way the
// product works, a before and after, plans and answers. The example is a fictional budgeting app ("Ledgerly"); replace every claim, plan and price
// with the real product's. Keep one goal on the page: the sign-up.
export default function App() {
  return (
    <>
      <NavBar
        brand="Ledgerly"
        links={[
          { label: "How it works", href: "#how" },
          { label: "Plans", href: "#plans" },
          { label: "Questions", href: "#faq" },
        ]}
        cta={{ label: "Join the list", href: "#top" }}
      />
      <main>
        <HeroSignup />
        <LogoStrip label="Written about in" names={["The Weekly Ledger", "Money Notes", "Small Business Daily", "Fieldwork", "The Index"]} />
        <FeaturesTabs
          eyebrow="How it works"
          title="Three things Ledgerly does for you."
          tabs={[
            { label: "Weekly summary", title: "A plain summary every Monday", text: "One message with what came in, what went out and what is due this week. No dashboards to open.", points: ["Read in under a minute", "Sent to your inbox or phone"] },
            { label: "Bank feed", title: "Connect once, forget about it", text: "Your accounts are read through your bank's own secure connection. Ledgerly can see balances and transactions, never move money.", points: ["Read-only access", "Disconnect any time"] },
            { label: "Reminders", title: "Bills that never surprise you", text: "Ledgerly notices what repeats and tells you three days before it leaves your account, with the amount.", points: ["Works for any bill", "Snooze or skip a reminder"] },
          ]}
        />
        <FeaturesComparison
          eyebrow="What changes"
          title="Your money, before and after."
          before={{ heading: "Before", items: ["Open three apps to see your balance", "Find out about a bill when it is paid", "Export a spreadsheet at the end of the month", "Guess what you can safely spend"] }}
          after={{ heading: "With Ledgerly", items: ["One summary with everything in it", "A reminder three days before each bill", "Your month already sorted for you", "A safe-to-spend figure on Monday morning"] }}
        />
        <PricingTable
          eyebrow="Plans"
          title="Free to start, simple to grow."
          plans={[
            { name: "Free", price: "£0", period: "for ever", href: "#top", cta: "Join the list" },
            { name: "Plus", price: "£4", period: "per month", href: "#top", cta: "Choose Plus", highlight: true },
            { name: "Household", price: "£8", period: "per month", href: "#top", cta: "Choose Household" },
          ]}
          features={[
            { label: "Weekly summary", values: [true, true, true] },
            { label: "Connected accounts", values: ["1", "5", "Unlimited"] },
            { label: "Bill reminders", values: [false, true, true] },
            { label: "People in the household", values: ["1", "1", "4"] },
            { label: "Export to spreadsheet", values: [false, true, true] },
          ]}
        />
        <FaqList
          title="Before you join"
          items={[
            { question: "When does Ledgerly launch?", answer: "We are letting people in a hundred at a time, starting in March. You will get an e-mail when your place opens." },
            { question: "Is my bank data safe?", answer: "Access is read-only and goes through your bank's own connection. We never see your login details and cannot move money." },
            { question: "Which banks work?", answer: "Most major UK banks at launch. The list is on the sign-up confirmation e-mail." },
            { question: "Can I cancel?", answer: "Yes, in two clicks, and your data is deleted within thirty days." },
          ]}
        />
        <NewsletterBand title="Not ready to join yet?" text="One short update when we launch, and one when your country is added. Nothing else." button="Keep me posted" />
      </main>
      <FooterMinimal brand="Ledgerly" legal="© 2026 Ledgerly Ltd." />
    </>
  );
}

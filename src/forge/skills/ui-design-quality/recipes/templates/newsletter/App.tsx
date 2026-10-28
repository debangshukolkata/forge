import HeroSignup from "./sections/HeroSignup";
import FeaturesNumbered from "./sections/FeaturesNumbered";
import TestimonialColumns from "./sections/TestimonialColumns";
import NewsletterBand from "./sections/NewsletterBand";
import FooterMinimal from "./sections/FooterMinimal";

// Newsletter or publication sign-up: indigo on neutral grey (Space Grotesk + Inter), one e-mail field first, what you get, what readers say and a second
// sign-up at the bottom. The example is a fictional weekly note on small-business money ("The Monday Ledger"); replace every promise, number and quote, and
// say honestly how often it is sent. Connect both sign-up forms' onSubmit to the real mailing list.
export default function App() {
  return (
    <>
      <main>
        <HeroSignup
          eyebrow="A weekly note"
          title="The five minutes of money news a small business owner needs."
          text="Every Monday: what changed in tax, banking and late payments, in plain language, with what to do about it."
          button="Subscribe, it is free"
          note="One e-mail a week. Unsubscribe in one click."
        />
        <FeaturesNumbered
          eyebrow="What you get"
          title="Every Monday morning."
          text="The same four parts, so you always know where to look."
          items={[
            { title: "The one thing that changed", text: "A rule, a rate or a deadline that affects you, explained in under a hundred words." },
            { title: "What to do about it", text: "A short, concrete step, with the form or the page to use." },
            { title: "One reader's question", text: "A real question from a reader, answered by an accountant who volunteers her time." },
            { title: "A number worth knowing", text: "One figure from the week, and why it matters to a business your size." },
          ]}
        />
        <TestimonialColumns
          eyebrow="Readers say"
          title="From the inbox."
          items={[
            { text: "The only newsletter I read the day it arrives.", name: "Dana Whitfield", role: "Bakery owner" },
            { text: "It told me about the new deadline two weeks before my accountant did.", name: "Omar Haddad", role: "Electrician" },
            { text: "Five minutes, and I always find one thing to act on.", name: "Lena Fischer", role: "Freelance designer" },
          ]}
        />
        <NewsletterBand title="Join the list." text="Free, weekly, and easy to leave." button="Subscribe" />
      </main>
      <FooterMinimal brand="The Monday Ledger" legal="© 2026 The Monday Ledger." links={[{ label: "Archive", href: "#archive" }, { label: "Privacy", href: "#privacy" }]} />
    </>
  );
}

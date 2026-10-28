import NavBar from "./sections/NavBar";
import HeroQuote from "./sections/HeroQuote";
import FeaturesNumbered from "./sections/FeaturesNumbered";
import FeaturesFigures from "./sections/FeaturesFigures";
import TestimonialFeature from "./sections/TestimonialFeature";
import FaqList from "./sections/FaqList";
import ContactSplit from "./sections/ContactSplit";
import FooterMinimal from "./sections/FooterMinimal";

// Independent consultant, coach or small practice: forest green on warm grey (Nunito + Inter), a hero that is one clear statement, a numbered way of
// working, figures, one client quote, questions and a contact block. The example is a fictional strategy consultant; every claim, figure and quote must be
// true and, for a client quote, used with permission.
export default function App() {
  return (
    <>
      <NavBar
        brand="Anna Lindqvist"
        links={[
          { label: "How I work", href: "#approach" },
          { label: "Questions", href: "#faq" },
          { label: "Contact", href: "#contact" },
        ]}
        cta={{ label: "Book a first call", href: "#contact" }}
      />
      <main>
        <HeroQuote />
        <FeaturesNumbered
          eyebrow="How I work"
          title="Four steps, no surprises."
          text="The same every time, so you always know what comes next."
          items={[
            { title: "A free first call", text: "Thirty minutes to hear the problem and tell you honestly whether I am the right person." },
            { title: "A written proposal", text: "One page: what I will do, what you will have at the end, how long it takes and the fixed fee." },
            { title: "The work, in the open", text: "A short note every Friday and one working session with your team in the middle." },
            { title: "A document people use", text: "Three pages, plain language, and a one-hour hand-over so your team can carry it on without me." },
          ]}
        />
        <FeaturesFigures
          eyebrow="Track record"
          title="What the last five years looked like."
          items={[
            { figure: "41", title: "Organisations helped", text: "Charities, schools and small firms, mostly in the north of England." },
            { figure: "93%", title: "Came back", text: "Of clients asked me to work with them again within two years." },
            { figure: "3 pages", title: "Every strategy", text: "Short enough to be read, which is the only way it gets used." },
          ]}
        />
        <TestimonialFeature
          quote="Anna turned a year of arguments into a three-page plan that all of the trustees signed in one meeting."
          name="Miriam Hale"
          role="Chair of trustees, a youth charity"
        />
        <FaqList
          title="Before you get in touch"
          items={[
            { question: "What does it cost?", answer: "A fixed fee agreed in the written proposal, usually between three and eight thousand pounds depending on the size of the organisation." },
            { question: "How long does a project take?", answer: "Most take six weeks from the first working session to the hand-over." },
            { question: "Do you work remotely?", answer: "Mostly, with one day on site at the start. Travel is charged at cost." },
          ]}
        />
        <ContactSplit
          eyebrow="Get in touch"
          title="Tell me what you are trying to decide."
          details={[
            { label: "E-mail", value: "anna@lindqvist.example" },
            { label: "Phone", value: "07700 900 123" },
            { label: "Based in", value: "Leeds, working across the north" },
            { label: "Replies", value: "Within one working day" },
          ]}
        />
      </main>
      <FooterMinimal brand="Anna Lindqvist" legal="© 2026 Lindqvist Strategy Ltd." />
    </>
  );
}

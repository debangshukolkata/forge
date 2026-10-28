import NavBar from "./sections/NavBar";
import HeroSearch from "./sections/HeroSearch";
import CategoryTiles from "./sections/CategoryTiles";
import StatsRow from "./sections/StatsRow";
import FeaturesNumbered from "./sections/FeaturesNumbered";
import FaqList from "./sections/FaqList";
import NewsletterBand from "./sections/NewsletterBand";
import FooterColumns from "./sections/FooterColumns";

// Directory or help centre: forest green on warm grey (Nunito + Inter), a big search field first, then the main categories, proof that the listings are
// kept up to date, how listings are checked and answers. The example is a fictional community directory ("Greenfield Together"); replace every service,
// number and answer with the real ones.
export default function App() {
  return (
    <>
      <NavBar
        brand="Greenfield Together"
        links={[
          { label: "Browse", href: "#browse" },
          { label: "How we check", href: "#how" },
          { label: "Questions", href: "#faq" },
        ]}
        cta={{ label: "Add a service", href: "#add" }}
      />
      <main>
        <HeroSearch />
        <CategoryTiles
          categories={[
            { label: "Food and essentials", text: "Food banks, community fridges and clothing swaps near you.", href: "#food" },
            { label: "Advice and support", text: "Housing, money and legal help from trained volunteers.", href: "#advice" },
            { label: "Health and wellbeing", text: "Mental health, groups for carers and older people.", href: "#health" },
          ]}
        />
        <StatsRow
          items={[
            { value: "412", label: "services listed" },
            { value: "6 months", label: "longest time since a listing was checked" },
            { value: "38", label: "volunteers keeping it up to date" },
          ]}
        />
        <FeaturesNumbered
          eyebrow="How we check"
          title="Every listing is called, not copied."
          text="A service only appears here once a volunteer has spoken to someone who runs it."
          items={[
            { title: "A volunteer phones", text: "They confirm the address, opening hours and who can use the service, and write down the answers." },
            { title: "We publish what they said", text: "Hours, eligibility and a contact number, in plain words, with the date it was last checked." },
            { title: "We check again", text: "Every listing is called again within six months, and sooner if someone tells us it has changed." },
          ]}
        />
        <FaqList
          title="Questions about the directory"
          items={[
            { question: "Is it free to use?", answer: "Yes, for everyone. The directory is paid for by the town council and local donations." },
            { question: "How do I add a service?", answer: "Use the Add a service button and fill in the short form. A volunteer will phone you within a week." },
            { question: "A listing is out of date. What do I do?", answer: "Send us a message from the listing. We call the service the same week." },
            { question: "Do you share my details?", answer: "No. Searches are not stored against your name, and we never sell data." },
          ]}
        />
        <NewsletterBand title="A short update each month." text="New services added, and any that have changed their hours." button="Subscribe" />
      </main>
      <FooterColumns
        brand="Greenfield Together"
        blurb="A community directory kept up to date by local volunteers."
        columns={[
          { heading: "Directory", links: [{ label: "Browse", href: "#browse" }, { label: "Add a service", href: "#add" }, { label: "Questions", href: "#faq" }] },
          { heading: "Contact", links: [{ label: "hello@greenfield.example", href: "mailto:hello@greenfield.example" }, { label: "Town Hall, Market Square", href: "#top" }] },
        ]}
        legal="© 2026 Greenfield Together. All rights reserved."
      />
    </>
  );
}

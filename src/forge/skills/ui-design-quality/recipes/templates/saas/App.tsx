import NavBar from "./sections/NavBar";
import HeroCentered from "./sections/HeroCentered";
import ArtTile from "./sections/ArtTile";
import LogoStrip from "./sections/LogoStrip";
import FeaturesBento from "./sections/FeaturesBento";
import StatsRow from "./sections/StatsRow";
import PricingTiers from "./sections/PricingTiers";
import FaqList from "./sections/FaqList";
import CtaBand from "./sections/CtaBand";
import FooterColumns from "./sections/FooterColumns";

// Software product: clean light look (Plus Jakarta Sans + Inter, indigo accent). Replace the example product ("Lumen",
// weekly briefings) with the real one; keep one primary action per view.
export default function App() {
  return (
    <>
      <NavBar
        brand="Lumen"
        links={[{ label: "Features", href: "#features" }, { label: "Pricing", href: "#pricing" }, { label: "FAQ", href: "#faq" }]}
        cta={{ label: "Start free", href: "#pricing" }}
      />
      <main>
        <HeroCentered>
          <ArtTile variant="bars" className="shadow-lift" />
        </HeroCentered>
        <LogoStrip />
        <div id="features"><FeaturesBento /></div>
        <StatsRow
          items={[
            { value: "4,200", label: "teams reporting weekly" },
            { value: "9 min", label: "average setup time" },
            { value: "38%", label: "fewer status meetings" },
            { value: "99.9%", label: "uptime last year" },
          ]}
        />
        <PricingTiers />
        <FaqList
          title="Before you start"
          items={[
            { question: "Which data sources work?", answer: "Google Sheets, Excel and CSV files, Postgres and MySQL. Anything else can be sent through our API." },
            { question: "Is my data safe?", answer: "Data is encrypted in transit and at rest, and you can delete a source at any time. We never train models on your data." },
            { question: "Can I cancel any time?", answer: "Yes. Cancel from the billing page and you keep access until the end of the month you paid for." },
          ]}
        />
        <CtaBand title="Your next Monday, handled." text="Connect a sheet and get your first briefing in ten minutes." action={{ label: "Start free", href: "#pricing" }} />
      </main>
      <FooterColumns
        brand="Lumen"
        blurb="Weekly briefings that write themselves."
        legal="© 2026 Lumen Labs. All rights reserved."
        columns={[
          { heading: "Product", links: [{ label: "Features", href: "#features" }, { label: "Pricing", href: "#pricing" }] },
          { heading: "Company", links: [{ label: "About", href: "#top" }, { label: "Contact", href: "mailto:hello@example.com" }] },
        ]}
      />
    </>
  );
}

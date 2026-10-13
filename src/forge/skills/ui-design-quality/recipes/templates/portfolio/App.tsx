import NavBar from "./sections/NavBar";
import HeroSplit from "./sections/HeroSplit";
import ArtTile from "./sections/ArtTile";
import FeaturesAlternating from "./sections/FeaturesAlternating";
import TestimonialFeature from "./sections/TestimonialFeature";
import ContactForm from "./sections/ContactForm";
import FooterColumns from "./sections/FooterColumns";

// Portfolio for an architect, designer or photographer: minimal monochrome (Playfair Display + DM Sans, one dark
// accent). Big type, wide margins, few elements. Replace the example practice ("Studio Rao") and the work items.
export default function App() {
  return (
    <>
      <NavBar
        brand="Studio Rao"
        links={[{ label: "Work", href: "#work" }, { label: "Kind words", href: "#stories" }, { label: "Contact", href: "#contact" }]}
        cta={{ label: "Start a project", href: "#contact" }}
      />
      <main>
        <HeroSplit
          eyebrow="Architecture and interiors · Kolkata"
          title="Quiet buildings that make a day feel easier."
          text="We design homes, studios and small public buildings with local materials, deep shade and good light. Fifteen projects, all still lived in."
          primary={{ label: "See the work", href: "#work" }}
          secondary={{ label: "Say hello", href: "#contact" }}
          facts={["Founded 2011", "Team of 9", "Kolkata and Shantiniketan"]}
        >
          <ArtTile variant="stack" />
        </HeroSplit>
        <div id="work">
          <FeaturesAlternating
            eyebrow="Selected work"
            title="Three projects, three kinds of quiet"
            items={[
              { title: "Courtyard House, Bhowanipore", text: "A family home organised around a shaded courtyard, with lime-washed walls and a roof that drinks the monsoon.", points: ["2022", "Residential"], art: "orbs" },
              { title: "The Reading Room, Shantiniketan", text: "A one-room library for a village school, built from salvaged brick and lit from above.", points: ["2020", "Public"], art: "grid" },
              { title: "Loft for a ceramicist", text: "A studio and home under an old tin roof, with a kiln yard and a long table for visitors.", points: ["2018", "Studio"], art: "bars" },
            ]}
          />
        </div>
        <TestimonialFeature
          quote="They listened for a month before drawing a line. The house feels like it was always here."
          name="Rahul Sen"
          role="Client, Courtyard House"
        />
        <ContactForm
          title="Tell us about your site."
          text="A few lines is enough. We reply within two working days and visit the site before we quote."
          submitLabel="Send"
          successTitle="Thank you."
          successText="We will write to you within two working days."
        />
      </main>
      <FooterColumns
        brand="Studio Rao"
        blurb="Architecture and interiors since 2011."
        legal="© 2026 Studio Rao"
        columns={[
          { heading: "Studio", links: [{ label: "Work", href: "#work" }, { label: "Contact", href: "#contact" }] },
          { heading: "Find us", links: [{ label: "hello@example.com", href: "mailto:hello@example.com" }, { label: "12 Lake Road, Kolkata", href: "#top" }] },
        ]}
      />
    </>
  );
}

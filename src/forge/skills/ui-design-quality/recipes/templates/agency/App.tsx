import NavBar from "./sections/NavBar";
import HeroPoster from "./sections/HeroPoster";
import FeaturesNumbered from "./sections/FeaturesNumbered";
import GalleryMosaic from "./sections/GalleryMosaic";
import TestimonialFeature from "./sections/TestimonialFeature";
import TeamRoster from "./sections/TeamRoster";
import ContactSplit from "./sections/ContactSplit";
import FooterCentered from "./sections/FooterCentered";

// Design or marketing agency: a loud poster hero in vermilion, big grotesque type (Archivo + DM Sans), a numbered way of working, a work gallery and a
// contact block. The example is a fictional studio ("Northfield Studio"); replace every name, project and quote, and put real project pictures in
// the gallery tiles (see GalleryMosaic). Keep the hero to one to three words.
export default function App() {
  return (
    <>
      <NavBar
        brand="Northfield"
        links={[
          { label: "Work", href: "#work" },
          { label: "Approach", href: "#approach" },
          { label: "People", href: "#people" },
        ]}
        cta={{ label: "Start a project", href: "#contact" }}
      />
      <main>
        <HeroPoster
          kicker="Brand and web studio in Leeds"
          title={["We make", "brands that", "get noticed"]}
          details={[
            { label: "Founded", value: "2014" },
            { label: "Team", value: "Twelve people" },
            { label: "Clients", value: "Charities, cafes and startups" },
          ]}
          action={{ label: "Start a project", href: "#contact" }}
        />
        <FeaturesNumbered
          eyebrow="Approach"
          title="How a project runs."
          text="Four steps, the same for a logo as for a whole website."
          items={[
            { title: "Listen", text: "A day with your team and your customers, and a written brief you sign off before any design starts." },
            { title: "Sketch", text: "Three directions on paper, shown early and cheaply, so you can say no to the ones that are not you." },
            { title: "Build", text: "We make the chosen direction real: identity, website, signs or packaging, as the project needs." },
            { title: "Hand over", text: "A guide, the files and a training session for your team, then we stay on call for ninety days." },
          ]}
        />
        <GalleryMosaic
          eyebrow="Recent work"
          title="A few things we are proud of."
          tiles={[
            { caption: "Identity for a community bakery", tone: "brand", shape: "arch" },
            { caption: "Website for a youth charity", tone: "soft", shape: "circle" },
            { caption: "Packaging for a tea company", tone: "ink", shape: "bars" },
            { caption: "Signage for a market hall", tone: "pale", shape: "stripes" },
            { caption: "Annual report, 64 pages", tone: "soft", shape: "arch" },
            { caption: "App icons and interface kit", tone: "brand", shape: "circle" },
          ]}
        />
        <TestimonialFeature
          quote="They asked questions nobody had asked us in ten years, and the answers ended up on the front of our shop. Sales are up a third."
          name="Dana Whitfield"
          role="Owner, Harbour Street Bakery"
        />
        <TeamRoster
          eyebrow="People"
          title="Who you will work with."
          people={[
            { name: "Priti Nair", role: "Founder and creative director", note: "Sets the direction and sits in on every first meeting.", href: "mailto:priti@northfield.example" },
            { name: "Callum Rhodes", role: "Head of web", note: "Builds the sites; fast, accessible and easy for your team to edit.", href: "mailto:callum@northfield.example" },
            { name: "Zoe Barrett", role: "Producer", note: "Keeps the dates honest and tells you early when something slips.", href: "mailto:zoe@northfield.example" },
          ]}
        />
        <ContactSplit
          eyebrow="Start here"
          title="Tell us what you are making."
          details={[
            { label: "Studio", value: "Unit 3, Canal Wharf, Leeds" },
            { label: "Open", value: "Monday to Friday, 9 to 6" },
            { label: "Phone", value: "0113 496 0000" },
            { label: "E-mail", value: "hello@northfield.example" },
          ]}
        />
      </main>
      <FooterCentered brand="Northfield" blurb="A brand and web studio in Leeds." links={[{ label: "Work", href: "#work" }, { label: "Careers", href: "#careers" }, { label: "Contact", href: "#contact" }]} legal="© 2026 Northfield Studio Ltd." />
    </>
  );
}

import NavBar from "./sections/NavBar";
import HeroEditorial from "./sections/HeroEditorial";
import TimelineVertical from "./sections/TimelineVertical";
import FeaturesNumbered from "./sections/FeaturesNumbered";
import TeamRoster from "./sections/TeamRoster";
import TestimonialFeature from "./sections/TestimonialFeature";
import CtaBand from "./sections/CtaBand";
import FooterMinimal from "./sections/FooterMinimal";

// About or company-story page: deep navy on cool grey (Lora + Inter), an editorial opening, a dated timeline, the principles, the people and one closing
// invitation. The example is a fictional family firm ("Hartley & Daughters"); replace every date, name and claim with true ones. History pages lose all
// credit if a single date is wrong, so check each one.
export default function App() {
  return (
    <>
      <NavBar
        brand="Hartley & Daughters"
        links={[
          { label: "Our story", href: "#story" },
          { label: "Principles", href: "#principles" },
          { label: "People", href: "#people" },
        ]}
        cta={{ label: "Get in touch", href: "#contact" }}
      />
      <main>
        <HeroEditorial
          issue="About the firm"
          date="Family-run since 1952"
          title={["Three generations,", "one workshop."]}
          text="We restore and rebuild furniture in the same workshop on Mill Street where our grandfather started. The tools have changed a little. The way we work has not."
          primary={{ label: "Visit the workshop", href: "#contact" }}
          secondary={{ label: "Read our story", href: "#story" }}
          facts={[
            { label: "Founded", value: "1952, Mill Street" },
            { label: "Craftspeople", value: "Nine, three of them family" },
            { label: "Pieces restored", value: "Over 6,000" },
          ]}
        />
        <TimelineVertical
          eyebrow="Our story"
          title="Seventy years, in five dates."
          items={[
            { when: "1952", title: "One bench and a borrowed saw", text: "Arthur Hartley opens the workshop on Mill Street, repairing chairs for his neighbours." },
            { when: "1974", title: "The first apprentice", text: "Arthur's daughter June joins and trains the first of forty apprentices who have passed through since." },
            { when: "1998", title: "A second workshop", text: "The building next door is bought and fitted out for upholstery and finishing." },
            { when: "2012", title: "Restoring for museums", text: "The firm takes on its first commission from a regional museum, and has worked with eleven since." },
            { when: "2024", title: "The third generation", text: "June's granddaughter Ellen becomes managing director and keeps the apprenticeship scheme open." },
          ]}
        />
        <FeaturesNumbered
          eyebrow="Principles"
          title="What we will not change."
          text="These were Arthur's rules. They are still on the workshop wall."
          items={[
            { title: "Repair before replace", text: "A piece that can be saved is saved, even when replacing it would be quicker and cheaper for us." },
            { title: "Say what it will cost", text: "A written quote before work starts, and a call before we spend anything beyond it." },
            { title: "Teach what we know", text: "Every craftsperson trains an apprentice. Knowledge kept in one head is lost with it." },
          ]}
        />
        <TeamRoster
          eyebrow="People"
          title="The family and the workshop."
          people={[
            { name: "Ellen Hartley", role: "Managing director", note: "Third generation. Trained as a cabinet maker and still takes commissions.", href: "mailto:ellen@hartley.example" },
            { name: "June Hartley", role: "Master upholsterer", note: "Fifty years at the bench; leads the apprenticeship scheme.", href: "mailto:june@hartley.example" },
            { name: "Tobias Reid", role: "Head of finishing", note: "Joined as an apprentice in 2009 and now runs the finishing room.", href: "mailto:tobias@hartley.example" },
          ]}
        />
        <TestimonialFeature
          quote="They brought my grandmother's dresser back to life and kept every scratch that mattered. I would not trust anyone else with it."
          name="Michael Odum"
          role="Customer since 2015"
        />
        <CtaBand title="Come and see the workshop." text="We are open to visitors on Saturday mornings, and by appointment any weekday." action={{ label: "Arrange a visit", href: "#contact" }} />
      </main>
      <FooterMinimal brand="Hartley & Daughters" legal="© 2026 Hartley & Daughters Ltd." />
    </>
  );
}

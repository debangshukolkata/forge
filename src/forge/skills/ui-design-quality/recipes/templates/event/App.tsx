import NavBar from "./sections/NavBar";
import HeroCentered from "./sections/HeroCentered";
import StatsRow from "./sections/StatsRow";
import ScheduleList from "./sections/ScheduleList";
import SpeakerGrid from "./sections/SpeakerGrid";
import PricingTiers from "./sections/PricingTiers";
import FaqList from "./sections/FaqList";
import CtaBand from "./sections/CtaBand";
import FooterColumns from "./sections/FooterColumns";

// Conference: Space Grotesk and Inter, a bold orange on cool slate, tighter corners. The example is a two-day web design conference; replace every
// word, name, date and price with the real event's, and the initials with photographs of the speakers.
export default function App() {
  return (
    <>
      <NavBar
        brand="Quiet Web 2026"
        links={[
          { label: "Programme", href: "#programme" },
          { label: "Speakers", href: "#speakers" },
          { label: "Tickets", href: "#pricing" },
        ]}
        cta={{ label: "Get a ticket", href: "#pricing" }}
      />
      <main>
        <HeroCentered
          eyebrow="12 and 13 June · Gothenburg, Sweden"
          title="Two days about making the web calmer, faster and kinder."
          text="Twelve talks, one open-space afternoon and a lot of coffee, for the people who design, write and build for the web."
          primary={{ label: "Get a ticket", href: "#pricing" }}
          secondary={{ label: "See the programme", href: "#programme" }}
          note="Early-bird prices until 1 May."
        />
        <StatsRow
          items={[
            { value: "2", label: "days" },
            { value: "12", label: "talks" },
            { value: "400", label: "attendees" },
            { value: "3", label: "rooms" },
          ]}
        />
        <ScheduleList />
        <SpeakerGrid />
        <PricingTiers
          eyebrow="Tickets"
          title="Pick the ticket that fits"
          plans={[
            { name: "Student", price: "€120", period: "both days", text: "With a valid student card.", features: ["All talks", "Lunch both days", "Recordings"], cta: "Get student ticket" },
            { name: "Standard", price: "€390", period: "both days", text: "For most people.", features: ["All talks", "Lunch both days", "After-party", "Recordings"], cta: "Get standard ticket", featured: true },
            { name: "Team of 5", price: "€1,590", period: "both days", text: "Five seats at a lower price each.", features: ["Everything in Standard", "A reserved table", "One invoice"], cta: "Get team tickets" },
          ]}
        />
        <FaqList
          title="Practical questions"
          items={[
            { question: "Where is it?", answer: "At the Concert Hall in central Gothenburg, ten minutes on foot from the central station." },
            { question: "Is it accessible?", answer: "Yes: step-free entrances, a quiet room, captions on every talk and a signer on request." },
            { question: "Can I get a refund?", answer: "Until 15 May in full, afterwards you can transfer your ticket to a colleague." },
            { question: "Will there be recordings?", answer: "All talks are recorded and sent to ticket holders within two weeks." },
          ]}
        />
        <CtaBand title="Seats are limited to 400." text="Early-bird prices end on 1 May, or when the first hundred tickets are gone." action={{ label: "Get a ticket", href: "#pricing" }} />
      </main>
      <FooterColumns
        brand="Quiet Web 2026"
        blurb="A two-day conference about the calm side of the web, run by volunteers."
        columns={[
          { heading: "Event", links: [{ label: "Programme", href: "#programme" }, { label: "Speakers", href: "#speakers" }, { label: "Tickets", href: "#pricing" }] },
          { heading: "Contact", links: [{ label: "team@quietweb.example", href: "mailto:team@quietweb.example" }, { label: "Concert Hall, Gothenburg", href: "#top" }] },
        ]}
        legal="© 2026 Quiet Web. All rights reserved."
      />
    </>
  );
}

import NavCentered from "./sections/NavCentered";
import HeroStacked from "./sections/HeroStacked";
import InfoStrip from "./sections/InfoStrip";
import FeaturesTabs from "./sections/FeaturesTabs";
import GalleryMosaic from "./sections/GalleryMosaic";
import TestimonialColumns from "./sections/TestimonialColumns";
import FormBooking from "./sections/FormBooking";
import FooterCentered from "./sections/FooterCentered";

// Small hotel, guesthouse or retreat: terracotta on cream (Lora + Nunito), a picture band, practical facts, rooms as tabs, a gallery, guest words and a
// booking bar. The example is a fictional guesthouse ("The Millhouse"); replace every room, price, fact and quote, and put real photographs in the hero band
// and the gallery. Prices and availability must come from the real booking system.
export default function App() {
  return (
    <>
      <NavCentered
        brand="The Millhouse"
        links={[
          { label: "Rooms", href: "#rooms" },
          { label: "The house", href: "#house" },
          { label: "Around here", href: "#around" },
          { label: "Guests", href: "#guests" },
        ]}
        cta={{ label: "Check dates", href: "#contact" }}
      />
      <main>
        <HeroStacked
          eyebrow="Guesthouse in the Dales"
          title="Six rooms in an old mill, with the river at the door."
          text="Breakfast from the village bakery, a fire in the sitting room and walking routes that start at the garden gate."
          primary={{ label: "Check dates", href: "#contact" }}
          secondary={{ label: "See the rooms", href: "#rooms" }}
        />
        <InfoStrip
          items={[
            { label: "Check in", value: "From 3 pm", note: "Check out by 11. Early bags can be left with us." },
            { label: "Find us", value: "The Mill, Water Lane", note: "Twelve minutes from the station by taxi." },
            { label: "Good to know", value: "Dogs welcome", note: "Two rooms are step-free on the ground floor." },
          ]}
        />
        <FeaturesTabs
          eyebrow="Rooms"
          title="Choose a room."
          tabs={[
            { label: "Garden", title: "Garden room, ground floor", text: "A double bed, a wood burner and doors onto the lawn. The easiest room to reach and the quietest at night.", points: ["Step-free access", "Sleeps two"] },
            { label: "River", title: "River room, first floor", text: "Large windows over the weir, a freestanding bath and a window seat. Our most asked-for room.", points: ["River view", "Sleeps two"] },
            { label: "Family", title: "Loft family room", text: "A double bed and two single beds under the old beams, with a small sitting area for the children.", points: ["Sleeps four", "Travel cot on request"] },
          ]}
        />
        <GalleryMosaic
          eyebrow="The house"
          title="A look around."
          tiles={[
            { caption: "The sitting room at dusk", tone: "brand", shape: "arch" },
            { caption: "Breakfast in the old mill room", tone: "soft", shape: "circle" },
            { caption: "The river from the garden", tone: "ink", shape: "bars" },
            { caption: "A river room bath", tone: "pale", shape: "stripes" },
            { caption: "The loft in winter", tone: "soft", shape: "arch" },
            { caption: "The walk to the waterfall", tone: "brand", shape: "circle" },
          ]}
        />
        <TestimonialColumns
          eyebrow="Guests wrote"
          title="After a stay."
          items={[
            { text: "We came for two nights and stayed for four. The fire alone was worth the journey.", name: "Helen Ward", role: "Stayed in October" },
            { text: "The dog had the best weekend of his life, and so did we.", name: "Marcus Bell", role: "Stayed in September" },
            { text: "Breakfast was the best part of every morning, and the room was spotless.", name: "Sana Iqbal", role: "Stayed in August" },
          ]}
        />
        <FormBooking eyebrow="Plan your stay" title="Tell us when you would like to come." slots={["15:00", "16:00", "17:00", "18:00"]} maxGuests={4} button="Check dates" />
      </main>
      <FooterCentered
        brand="The Millhouse"
        blurb="A guesthouse at The Mill, Water Lane, in the Dales."
        links={[{ label: "Rooms", href: "#rooms" }, { label: "Getting here", href: "#around" }, { label: "Contact", href: "#contact" }]}
        legal="© 2026 The Millhouse."
      />
    </>
  );
}

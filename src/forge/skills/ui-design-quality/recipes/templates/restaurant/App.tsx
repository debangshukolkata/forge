import NavCentered from "./sections/NavCentered";
import HeroStacked from "./sections/HeroStacked";
import InfoStrip from "./sections/InfoStrip";
import FeaturesIconRow from "./sections/FeaturesIconRow";
import GalleryMosaic from "./sections/GalleryMosaic";
import TestimonialColumns from "./sections/TestimonialColumns";
import FormBooking from "./sections/FormBooking";
import FooterCentered from "./sections/FooterCentered";

// Restaurant or cafe: a warm, quiet look (Lora + Nunito, terracotta on cream) with a centred navigation, a picture band, opening hours, a booking bar and
// a centred footer. The example is a fictional neighbourhood restaurant ("Olive & Ember"); replace every name, hour, dish and quote with the real ones,
// and put your own photographs in the hero band (children of HeroStacked) and the gallery.
export default function App() {
  return (
    <>
      <NavCentered
        brand="Olive & Ember"
        links={[
          { label: "Menu", href: "#menu" },
          { label: "Our story", href: "#story" },
          { label: "Visit", href: "#visit" },
          { label: "Reviews", href: "#reviews" },
        ]}
        cta={{ label: "Book a table", href: "#contact" }}
      />
      <main>
        <HeroStacked
          eyebrow="Wood-fired kitchen"
          title="Supper cooked over fire, shared across the table."
          text="Seasonal plates from a small kitchen on Quay Street. Most of what we serve comes from farms within thirty miles, and the oven is lit at four every afternoon."
          primary={{ label: "Book a table", href: "#contact" }}
          secondary={{ label: "See the menu", href: "#menu" }}
        />
        <InfoStrip
          items={[
            { label: "Open", value: "Tuesday to Sunday", note: "Dinner from 5:30, lunch on Saturday and Sunday." },
            { label: "Find us", value: "14 Quay Street", note: "Five minutes from the harbour car park." },
            { label: "Bookings", value: "01234 567 890", note: "Or use the form below. Walk-ins are welcome." },
          ]}
        />
        <FeaturesIconRow
          eyebrow="The kitchen"
          title="Simple things, done carefully."
          items={[
            { title: "Cooked on fire", text: "Everything from the starters to the dessert passes through the oven or the grill." },
            { title: "Grown nearby", text: "Our vegetables, eggs and meat come from six farms we visit ourselves." },
            { title: "Made for sharing", text: "Plates arrive together, so the table decides the order and pace of the evening." },
            { title: "Kind to allergies", text: "Tell us when you book and the kitchen plans around it, with no extra charge." },
          ]}
        />
        <GalleryMosaic
          eyebrow="From the pass"
          title="A few plates from this season."
          tiles={[
            { caption: "Charred leeks with hazelnuts", tone: "brand", shape: "arch" },
            { caption: "Sourdough, still warm", tone: "soft", shape: "circle" },
            { caption: "Slow lamb shoulder", tone: "ink", shape: "bars" },
            { caption: "Plum tart with cream", tone: "pale", shape: "stripes" },
            { caption: "The dining room at six", tone: "soft", shape: "arch" },
            { caption: "Late summer tomatoes", tone: "brand", shape: "circle" },
          ]}
        />
        <TestimonialColumns
          eyebrow="Kind words"
          title="What guests wrote after dinner."
          items={[
            { text: "The best meal we have had in the county, and nobody rushed us once.", name: "Helen Ward", role: "Birthday dinner, October" },
            { text: "We came for the lamb and stayed for the plum tart. Booking again for Friday.", name: "Marcus Bell", role: "Regular since 2024" },
            { text: "They remembered my daughter's allergy from the phone call and brought her own dessert.", name: "Sana Iqbal", role: "Family supper" },
          ]}
        />
        <FormBooking eyebrow="Reserve a table" title="Choose a night and we will keep it for you." />
      </main>
      <FooterCentered
        brand="Olive & Ember"
        blurb="A wood-fired kitchen at 14 Quay Street, open Tuesday to Sunday."
        links={[
          { label: "Menu", href: "#menu" },
          { label: "Private dining", href: "#private" },
          { label: "Gift cards", href: "#gifts" },
          { label: "Contact", href: "#contact" },
        ]}
        legal="© 2026 Olive & Ember. All rights reserved."
      />
    </>
  );
}

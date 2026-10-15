import NavBar from "./sections/NavBar";
import HeroSplit from "./sections/HeroSplit";
import CategoryTiles from "./sections/CategoryTiles";
import ProductGrid from "./sections/ProductGrid";
import StatsRow from "./sections/StatsRow";
import TestimonialFeature from "./sections/TestimonialFeature";
import FaqList from "./sections/FaqList";
import CtaBand from "./sections/CtaBand";
import FooterColumns from "./sections/FooterColumns";

// Craft shop: a serif display face (Playfair Display) with Plus Jakarta Sans, sage green on warm stone. The copy below is an example (a small pottery);
// replace every word, price and link with the real shop's, and the drawn tiles with photographs of the products.
export default function App() {
  return (
    <>
      <NavBar
        brand="Stonehill Pottery"
        links={[
          { label: "Shop", href: "#shop" },
          { label: "Our story", href: "#story" },
          { label: "Delivery", href: "#faq" },
        ]}
        cta={{ label: "Basket (0)", href: "#shop" }}
      />
      <main>
        <HeroSplit
          eyebrow="Spring collection · free delivery over €60"
          title="Things for the table that get better with use."
          text="Mugs, jugs and boards made by hand in a small studio on the coast, in batches of fifty or fewer. When they are gone, they are gone."
          primary={{ label: "Shop the collection", href: "#shop" }}
          secondary={{ label: "Meet the makers", href: "#story" }}
          facts={["Made by hand", "Ships in 3 days", "30-day returns"]}
        />
        <CategoryTiles />
        <ProductGrid />
        <StatsRow
          items={[
            { value: "1,200", label: "pieces made each year" },
            { value: "6", label: "people in the studio" },
            { value: "98%", label: "orders arrive unbroken" },
            { value: "30", label: "days to return anything" },
          ]}
        />
        <div id="story">
          <TestimonialFeature
            quote="The mug has been through two years of daily use and two moves, and it still looks like the day it arrived. Better, if anything."
            name="Hannah Weiss"
            role="Customer since 2023"
          />
        </div>
        <FaqList
          title="Delivery and returns"
          items={[
            { question: "How long does delivery take?", answer: "Orders ship within three working days and arrive in two to four more. Free over €60 within the EU; otherwise €6." },
            { question: "What if it arrives broken?", answer: "Write to us with a photograph and we send a new one the same day, no questions asked." },
            { question: "Can I return something?", answer: "Within 30 days, unused, in the original box. We refund the full price to the card you used." },
            { question: "Do you make custom orders?", answer: "Sets of six or more can be made in a colour of your choice. Allow six weeks." },
          ]}
        />
        <CtaBand title="First news of each new batch." text="One email when a collection opens, never more than twice a month." action={{ label: "Join the list", href: "#shop" }} />
      </main>
      <FooterColumns
        brand="Stonehill Pottery"
        blurb="A small studio on the coast, making things for the table since 2016."
        columns={[
          { heading: "Shop", links: [{ label: "All pieces", href: "#shop" }, { label: "Gifts", href: "#shop" }, { label: "Gift cards", href: "#shop" }] },
          { heading: "Help", links: [{ label: "Delivery", href: "#faq" }, { label: "Returns", href: "#faq" }, { label: "hello@stonehill.example", href: "mailto:hello@stonehill.example" }] },
        ]}
        legal="© 2026 Stonehill Pottery. All rights reserved."
      />
    </>
  );
}

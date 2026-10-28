import NavCentered from "./sections/NavCentered";
import FormFeedback from "./sections/FormFeedback";
import TestimonialColumns from "./sections/TestimonialColumns";
import FooterCentered from "./sections/FooterCentered";

// Feedback page: a rating and a comment first, then what other guests said, in the restaurant palette (terracotta on cream, Lora + Nunito). Use it
// after a visit, an order or an event; send FormFeedback's onSubmit to the real back end. Only show quotes people have given you permission to use.
export default function App() {
  return (
    <>
      <NavCentered
        brand="Olive & Ember"
        links={[
          { label: "Menu", href: "#menu" },
          { label: "Visit", href: "#visit" },
        ]}
        cta={{ label: "Book a table", href: "#book" }}
      />
      <main>
        <FormFeedback heading="h1" title="How was your evening?" text="Two minutes of your time helps us decide what to fix first." />
        <TestimonialColumns
          eyebrow="What others said"
          title="Recent comments."
          items={[
            { text: "Lovely food, and nobody hurried us.", name: "Helen Ward", role: "Dinner in October" },
            { text: "The lamb was the best I have had this year.", name: "Marcus Bell", role: "Dinner in September" },
            { text: "They looked after my daughter's allergy without any fuss.", name: "Sana Iqbal", role: "Family supper" },
          ]}
        />
      </main>
      <FooterCentered brand="Olive & Ember" blurb="14 Quay Street, open Tuesday to Sunday." links={[{ label: "Menu", href: "#menu" }, { label: "Contact", href: "#contact" }]} legal="© 2026 Olive & Ember." />
    </>
  );
}

import NavBar from "./sections/NavBar";
import FormStepper from "./sections/FormStepper";
import FeaturesIconRow from "./sections/FeaturesIconRow";
import FaqList from "./sections/FaqList";
import FooterMinimal from "./sections/FooterMinimal";

// Form flow (booking, application, registration): a short page whose one job is to get a multi-step form finished. Uses the clinic palette (teal on cool
// grey) and the same fonts. The example is a fictional visit booking for a community studio; change the steps, the fields and every sentence, and send the
// values from FormStepper's onSubmit to the real back end (the page only validates). Keep the questions that follow the form honest and short.
export default function App() {
  return (
    <>
      <NavBar
        brand="Mill Studio"
        links={[
          { label: "What happens next", href: "#next" },
          { label: "Questions", href: "#faq" },
        ]}
        cta={{ label: "Start", href: "#contact" }}
      />
      <main>
        <FormStepper heading="h1" eyebrow="Book a visit" title="Tell us when you would like to come." />
        <FeaturesIconRow
          eyebrow="What happens next"
          title="After you send the form."
          items={[
            { title: "We read it today", text: "A real person reads every booking the day it arrives, including weekends." },
            { title: "You hear within a day", text: "A confirmation or a suggested alternative time arrives by e-mail." },
            { title: "Change it any time", text: "Reply to the e-mail to move or cancel. There is no charge up to 24 hours before." },
          ]}
        />
        <FaqList
          title="Before you book"
          items={[
            { question: "Do I need an account?", answer: "No. The form asks only for what we need to hold your place." },
            { question: "Can I book for a group?", answer: "Yes, up to twelve people. For more, write to us and we will arrange a larger room." },
            { question: "Is the studio step-free?", answer: "Yes. There is a ramp at the main door and an accessible toilet on the ground floor." },
          ]}
        />
      </main>
      <FooterMinimal brand="Mill Studio" legal="© 2026 Mill Studio." />
    </>
  );
}

import NavBar from "./sections/NavBar";
import HeroNumbers from "./sections/HeroNumbers";
import FeaturesIconRow from "./sections/FeaturesIconRow";
import TeamRoster from "./sections/TeamRoster";
import TestimonialColumns from "./sections/TestimonialColumns";
import FaqList from "./sections/FaqList";
import ContactSplit from "./sections/ContactSplit";
import FooterMinimal from "./sections/FooterMinimal";

// Clinic or health practice: calm teal on cool grey (Plus Jakarta Sans + Manrope), a hero that proves its claim with figures, the people, reassurance
// and a contact block with the address and hours. The example is a fictional family practice ("Riverside Health"); replace every figure, name and
// answer with real ones. Do not invent clinical claims: every number on a health page must be one the practice can stand behind.
export default function App() {
  return (
    <>
      <NavBar
        brand="Riverside Health"
        links={[
          { label: "Services", href: "#services" },
          { label: "Our team", href: "#team" },
          { label: "Questions", href: "#faq" },
        ]}
        cta={{ label: "Book a visit", href: "#contact" }}
      />
      <main>
        <HeroNumbers
          eyebrow="Family practice since 2009"
          title="Seen on the day you call, by someone who knows you."
          text="Riverside Health is a small family practice with three doctors and two nurses. We keep part of every day free for people who need to be seen today."
          primary={{ label: "Book a visit", href: "#contact" }}
          secondary={{ label: "Meet the team", href: "#team" }}
          figures={[
            { value: "9 min", label: "average wait in the waiting room" },
            { value: "96%", label: "of urgent requests seen the same day" },
            { value: "4,200", label: "patients registered with the practice" },
          ]}
        />
        <FeaturesIconRow
          eyebrow="What we offer"
          title="Everyday care under one roof."
          items={[
            { title: "Same-day visits", text: "A doctor or nurse sees you today for anything that cannot wait until next week." },
            { title: "Long-term conditions", text: "Regular reviews for diabetes, asthma and blood pressure, with a plan you keep." },
            { title: "Children and families", text: "Vaccinations, growth checks and a waiting area with room for a pushchair." },
            { title: "Clear results", text: "Test results come with a short explanation, by message or phone as you prefer." },
          ]}
        />
        <TeamRoster
          eyebrow="Our team"
          title="The people who will look after you."
          people={[
            { name: "Dr Amara Osei", role: "Senior doctor", note: "Twenty years in general practice; leads the diabetes and heart clinics.", href: "mailto:amara@riverside.example" },
            { name: "Dr Lucas Meyer", role: "Doctor", note: "Sees children and young adults; runs the Thursday evening surgery.", href: "mailto:lucas@riverside.example" },
            { name: "Nurse Grace Kim", role: "Practice nurse", note: "Vaccinations, wound care and the asthma review clinic.", href: "mailto:grace@riverside.example" },
          ]}
        />
        <TestimonialColumns
          eyebrow="Patients say"
          title="In their own words."
          items={[
            { text: "I rang at eight and was seen by ten. Nobody made me feel I was wasting their time.", name: "Joan Pryce", role: "Patient for six years" },
            { text: "The nurse explained my results twice, slowly, and wrote them down for my husband.", name: "Femi Adeyemi", role: "Patient" },
            { text: "Our son used to dread appointments. Now he asks if he can show them his drawings.", name: "Rachel Stein", role: "Parent of two" },
          ]}
        />
        <FaqList
          title="Common questions"
          items={[
            { question: "How do I register?", answer: "Fill in the form at reception or send us your details through the form below. We confirm within two working days." },
            { question: "Can I get a same-day visit?", answer: "Yes. Call before ten and we keep a number of slots free every day for urgent problems." },
            { question: "What should I bring?", answer: "A form of identification, a list of your medicines and any letters from the hospital." },
            { question: "Do you offer evening appointments?", answer: "On Thursdays the surgery stays open until eight in the evening." },
          ]}
        />
        <ContactSplit
          eyebrow="Visit or write"
          title="Find us, or send a message."
          details={[
            { label: "Address", value: "22 River Road, Millbridge" },
            { label: "Open", value: "Monday to Friday, 8 to 6" },
            { label: "Phone", value: "01234 567 891" },
            { label: "E-mail", value: "reception@riverside.example" },
          ]}
        />
      </main>
      <FooterMinimal
        brand="Riverside Health"
        legal="© 2026 Riverside Health. Registered practice."
        links={[
          { label: "Privacy", href: "#privacy" },
          { label: "Complaints", href: "#complaints" },
          { label: "Contact", href: "#contact" },
        ]}
      />
    </>
  );
}

import NavBar from "./sections/NavBar";
import HeroPoster from "./sections/HeroPoster";
import FeaturesIconRow from "./sections/FeaturesIconRow";
import ScheduleList from "./sections/ScheduleList";
import PricingTable from "./sections/PricingTable";
import FaqList from "./sections/FaqList";
import FormBooking from "./sections/FormBooking";
import FooterCentered from "./sections/FooterCentered";

// Gym, studio or sports club: vermilion poster hero on warm grey (Archivo + DM Sans), what makes the place different, the class timetable, membership
// plans, questions and a trial-class booking bar. The example is a fictional strength studio ("Ironworks Studio"); replace every class, time, price and
// answer, and keep any health claim to what the studio can stand behind.
export default function App() {
  return (
    <>
      <NavBar
        brand="Ironworks"
        links={[
          { label: "Classes", href: "#programme" },
          { label: "Membership", href: "#plans" },
          { label: "Questions", href: "#faq" },
        ]}
        cta={{ label: "Book a free class", href: "#contact" }}
      />
      <main>
        <HeroPoster
          kicker="Strength studio, Leeds"
          title={["Get", "Strong", "Together"]}
          details={[
            { label: "Open", value: "6 am to 9 pm, every day" },
            { label: "Classes", value: "Thirty a week" },
            { label: "First class", value: "Free" },
          ]}
          action={{ label: "Book a free class", href: "#contact" }}
        />
        <FeaturesIconRow
          eyebrow="The studio"
          title="Small classes, real coaching."
          items={[
            { title: "Twelve in a class", text: "Never more, so the coach sees every rep and corrects it before it becomes a habit." },
            { title: "A plan for you", text: "Your first week includes a one-to-one session to set goals and a starting weight." },
            { title: "Open early and late", text: "Classes from six in the morning to eight at night, seven days a week." },
            { title: "Friendly to beginners", text: "Every class has a lighter version of each move, and nobody is expected to keep up." },
          ]}
        />
        <ScheduleList
          eyebrow="Timetable"
          title="This week's classes."
          days={[
            {
              label: "Weekdays",
              date: "Monday to Friday",
              sessions: [
                { time: "06:30", title: "Early strength, full body", who: "Coach Dara", room: "Floor A" },
                { time: "12:15", title: "Lunchtime conditioning", who: "Coach Mia", room: "Floor B" },
                { time: "18:00", title: "Barbell basics for beginners", who: "Coach Jonas", room: "Floor A" },
                { time: "19:15", title: "Evening strength", who: "Coach Dara", room: "Floor A" },
              ],
            },
            {
              label: "Weekend",
              date: "Saturday and Sunday",
              sessions: [
                { time: "09:00", title: "Team workout, all levels", who: "Coach Mia", room: "Floor A" },
                { time: "10:30", title: "Mobility and stretching", who: "Coach Jonas", room: "Floor B" },
              ],
            },
          ]}
        />
        <PricingTable
          eyebrow="Membership"
          title="Pick how often you train."
          plans={[
            { name: "Drop-in", price: "£12", period: "per class", href: "#contact", cta: "Book a class" },
            { name: "Regular", price: "£59", period: "per month", href: "#contact", cta: "Join", highlight: true },
            { name: "Unlimited", price: "£89", period: "per month", href: "#contact", cta: "Join" },
          ]}
          features={[
            { label: "Classes each month", values: ["1 at a time", "8", "Unlimited"] },
            { label: "One-to-one start session", values: [false, true, true] },
            { label: "Open gym hours", values: [false, true, true] },
            { label: "Bring a friend free", values: [false, false, "Twice a month"] },
          ]}
        />
        <FaqList
          title="Common questions"
          items={[
            { question: "I have never lifted a weight. Is that fine?", answer: "Yes. Start with a barbell basics class and your coach will build you up from the empty bar." },
            { question: "Do I have to sign a contract?", answer: "No. Memberships run month to month and you can stop at any time before the next payment." },
            { question: "What should I bring?", answer: "Trainers, a water bottle and a towel. Everything else is here." },
          ]}
        />
        <FormBooking eyebrow="Try a class" title="Book your free class." slots={["06:30", "12:15", "18:00", "19:15"]} maxGuests={2} button="Reserve my place" />
      </main>
      <FooterCentered
        brand="Ironworks"
        blurb="A strength studio at Unit 5, Canal Wharf, Leeds."
        links={[{ label: "Classes", href: "#programme" }, { label: "Membership", href: "#plans" }, { label: "Contact", href: "#contact" }]}
        legal="© 2026 Ironworks Studio Ltd."
      />
    </>
  );
}

import NavBar from "./sections/NavBar";
import HeroSplit from "./sections/HeroSplit";
import StatsRow from "./sections/StatsRow";
import StepsTimeline from "./sections/StepsTimeline";
import TestimonialFeature from "./sections/TestimonialFeature";
import FaqList from "./sections/FaqList";
import ContactForm from "./sections/ContactForm";
import CtaBand from "./sections/CtaBand";
import FooterColumns from "./sections/FooterColumns";

// Charity or community drive: warm editorial look (Fraunces + Inter). Every section's default text is a blood-drive
// example; replace the props with the real product's words, numbers and dates.
export default function App() {
  return (
    <>
      <NavBar brand="Gift of Life" cta={{ label: "Register", href: "#contact" }} />
      <main>
        <HeroSplit />
        <StatsRow />
        <StepsTimeline />
        <TestimonialFeature />
        <FaqList />
        <ContactForm />
        <CtaBand />
      </main>
      <FooterColumns brand="Gift of Life" />
    </>
  );
}

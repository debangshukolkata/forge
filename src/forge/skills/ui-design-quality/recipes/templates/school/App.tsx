import NavBar from "./sections/NavBar";
import HeroSplit from "./sections/HeroSplit";
import FeaturesFigures from "./sections/FeaturesFigures";
import ScheduleList from "./sections/ScheduleList";
import TeamRoster from "./sections/TeamRoster";
import TestimonialColumns from "./sections/TestimonialColumns";
import ContactSplit from "./sections/ContactSplit";
import FooterColumns from "./sections/FooterColumns";

// School, course or training provider: deep navy on cool grey (Lora + Inter), a hero with the term's key facts, figures that back the claim, the
// timetable, the teachers, parents' words and a contact block. The example is a fictional music school ("Harbour Music School"); replace every figure, name,
// date and quote, and only claim results you can show. HeroSplit shows a drawn stand-in picture; pass your own photograph as its child.
export default function App() {
  return (
    <>
      <NavBar
        brand="Harbour Music School"
        links={[
          { label: "Timetable", href: "#programme" },
          { label: "Teachers", href: "#teachers" },
          { label: "Contact", href: "#contact" },
        ]}
        cta={{ label: "Book a trial lesson", href: "#contact" }}
      />
      <main>
        <HeroSplit
          eyebrow="Lessons for ages 6 to 18"
          title="Learn an instrument from working musicians."
          text="Individual and small-group lessons in piano, violin, guitar and voice. Every pupil plays in a concert each term, from their first term."
          primary={{ label: "Book a trial lesson", href: "#contact" }}
          secondary={{ label: "See the timetable", href: "#programme" }}
          facts={["Term starts 8 January", "After school and Saturdays", "Harbour Street"]}
        />
        <FeaturesFigures
          eyebrow="In numbers"
          title="What a term looks like here."
          items={[
            { figure: "6", title: "Pupils in a group", text: "Small groups so every child plays in every lesson." },
            { figure: "12", title: "Teachers", text: "All working musicians, with at least five years of teaching." },
            { figure: "3", title: "Concerts a year", text: "Every pupil plays, from the very first term." },
          ]}
        />
        <ScheduleList
          eyebrow="Timetable"
          title="When lessons run."
          days={[
            {
              label: "Weekdays",
              date: "Monday to Friday",
              sessions: [
                { time: "15:30", title: "Beginner piano, group of six", who: "Ms Okafor", room: "Room 1" },
                { time: "16:30", title: "Violin, individual lessons", who: "Mr Lindgren", room: "Room 2" },
                { time: "17:30", title: "Guitar, ages 10 to 14", who: "Ms Rossi", room: "Room 3" },
              ],
            },
            {
              label: "Saturday",
              date: "Morning and midday",
              sessions: [
                { time: "09:30", title: "Choir, all ages", who: "Mr Adeyemi", room: "Hall" },
                { time: "11:00", title: "Ensemble practice", who: "Ms Okafor", room: "Hall" },
                { time: "12:30", title: "Termly concert (last Saturday)", who: "Everyone", room: "Hall", kind: "keynote" },
              ],
            },
          ]}
        />
        <TeamRoster
          eyebrow="Teachers"
          title="Who will teach your child."
          people={[
            { name: "Ngozi Okafor", role: "Head of piano", note: "Performs with the city orchestra and has taught for fourteen years.", href: "mailto:ngozi@harbour.example" },
            { name: "Erik Lindgren", role: "Violin", note: "Plays in a string quartet and runs the beginners' ensemble.", href: "mailto:erik@harbour.example" },
            { name: "Chiara Rossi", role: "Guitar and voice", note: "Teaches classical and folk styles to ages eight and up.", href: "mailto:chiara@harbour.example" },
          ]}
        />
        <TestimonialColumns
          eyebrow="Parents say"
          title="After a year with us."
          items={[
            { text: "My son went from refusing to practise to asking for an extra lesson.", name: "Priya Raman", role: "Parent of a year-5 pupil" },
            { text: "The termly concert gave her the confidence to play in front of the whole school.", name: "Tom Hadley", role: "Parent of a year-8 pupil" },
            { text: "Clear reports after every term, and a teacher who answers messages the same day.", name: "Aisha Khan", role: "Parent of two pupils" },
          ]}
        />
        <ContactSplit
          eyebrow="Book a trial"
          title="Come and try a lesson."
          details={[
            { label: "Address", value: "8 Harbour Street" },
            { label: "Office", value: "Monday to Friday, 2 to 7" },
            { label: "Phone", value: "01234 567 892" },
            { label: "E-mail", value: "lessons@harbour.example" },
          ]}
        />
      </main>
      <FooterColumns
        brand="Harbour Music School"
        blurb="Instrumental and vocal lessons for ages 6 to 18."
        columns={[
          { heading: "School", links: [{ label: "Timetable", href: "#programme" }, { label: "Teachers", href: "#teachers" }, { label: "Fees", href: "#fees" }] },
          { heading: "Contact", links: [{ label: "lessons@harbour.example", href: "mailto:lessons@harbour.example" }, { label: "8 Harbour Street", href: "#top" }] },
        ]}
        legal="© 2026 Harbour Music School. All rights reserved."
      />
    </>
  );
}

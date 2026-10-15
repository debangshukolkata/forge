// A day-by-day programme: tabs for the days and, for the chosen day, a list of sessions with time, title, speaker and room.
// The first day is selected. Keep titles under two lines; mark a break or a keynote with `kind` so the rhythm of the day is visible.
import { useState } from "react";

export type Session = { time: string; title: string; who: string; room: string; kind?: "keynote" | "break" | "talk" };
export type Day = { label: string; date: string; sessions: Session[] };

export default function ScheduleList({
  eyebrow = "Programme",
  title = "Two days, three rooms",
  days = [
    {
      label: "Thursday",
      date: "12 June",
      sessions: [
        { time: "09:00", title: "Opening keynote: the quiet web", who: "Maya Lindqvist", room: "Main hall", kind: "keynote" },
        { time: "10:30", title: "Coffee and the hallway track", who: "", room: "Atrium", kind: "break" },
        { time: "11:00", title: "Design tokens that survive a rebrand", who: "Tomas Ruiz", room: "Room A", kind: "talk" },
        { time: "12:00", title: "Accessible charts without the compromise", who: "Ines Okafor", room: "Room B", kind: "talk" },
        { time: "13:00", title: "Lunch", who: "", room: "Atrium", kind: "break" },
        { time: "14:30", title: "Performance budgets in practice", who: "Sven Aalto", room: "Main hall", kind: "talk" },
      ],
    },
    {
      label: "Friday",
      date: "13 June",
      sessions: [
        { time: "09:30", title: "Writing for interfaces", who: "Priya Nair", room: "Room A", kind: "talk" },
        { time: "11:00", title: "What we learned shipping to 40 million", who: "Daniel Cho", room: "Main hall", kind: "keynote" },
        { time: "12:30", title: "Lunch", who: "", room: "Atrium", kind: "break" },
        { time: "14:00", title: "Open space: bring a problem", who: "Everyone", room: "Room C", kind: "talk" },
        { time: "16:00", title: "Closing and the after-party", who: "", room: "Main hall", kind: "keynote" },
      ],
    },
  ],
}: {
  eyebrow?: string;
  title?: string;
  days?: Day[];
}) {
  const [active, setActive] = useState(0);
  const day = days[active] ?? days[0];
  return (
    <section id="programme" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div role="tablist" aria-label="Days" className="mt-10 flex flex-wrap gap-2">
        {days.map((item, index) => (
          <button
            key={item.label}
            type="button"
            role="tab"
            id={`tab-${index}`}
            aria-selected={index === active}
            aria-controls="day-panel"
            onClick={() => setActive(index)}
            className={`rounded-full border px-5 py-2.5 text-sm font-semibold transition ${
              index === active ? "border-brand-600 bg-brand-600 text-white" : "border-ink-300 bg-white text-ink-900 hover:border-ink-500"
            }`}
          >
            {item.label} <span className={index === active ? "font-normal text-white/85" : "font-normal text-ink-500"}>{item.date}</span>
          </button>
        ))}
      </div>
      <ol id="day-panel" role="tabpanel" aria-labelledby={`tab-${active}`} className="mt-6 divide-y divide-ink-200 rounded-card border border-ink-200 bg-white shadow-soft">
        {day.sessions.map((session) => (
          <li key={`${session.time}-${session.title}`} className={`grid gap-1 px-5 py-4 sm:grid-cols-[6rem_1fr_9rem] sm:items-center sm:gap-6 ${session.kind === "break" ? "bg-ink-50 text-ink-700" : ""}`}>
            <span className="font-display text-lg font-semibold tabular-nums text-ink-900">{session.time}</span>
            <span>
              <span className={`block font-semibold ${session.kind === "keynote" ? "text-brand-700" : "text-ink-900"}`}>{session.title}</span>
              {session.who && <span className="block text-sm text-ink-700">{session.who}</span>}
            </span>
            <span className="text-sm text-ink-500 sm:text-right">{session.room}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}

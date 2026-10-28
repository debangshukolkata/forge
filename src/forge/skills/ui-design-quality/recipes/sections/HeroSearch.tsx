// Search hero: a headline and one large search field with a button, and a line of popular searches under it. For directories, catalogues,
// listings and help centres, where the first thing a visitor does is look for something. `onSearch` receives the query; the popular terms fill the field.
import { useState, type FormEvent } from "react";

export default function HeroSearch({
  eyebrow = "Local directory",
  title = "Find the help you need, close to home.",
  text = "Over 400 local services, from food banks to legal advice, checked by our volunteers every six months.",
  placeholder = "What are you looking for?",
  button = "Search",
  popular = ["Food bank", "Housing advice", "Mental health", "Childcare", "Legal help"],
  onSearch,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  placeholder?: string;
  button?: string;
  popular?: string[];
  onSearch?: (query: string) => void;
}) {
  const [query, setQuery] = useState("");
  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (query.trim()) onSearch?.(query.trim());
  };
  return (
    <section id="top" className="mx-auto max-w-4xl px-4 py-16 sm:px-6 md:py-28">
      <p className="eyebrow">{eyebrow}</p>
      <h1 className="mt-4 max-w-3xl text-4xl font-semibold leading-[1.05] sm:text-6xl">{title}</h1>
      <p className="mt-5 max-w-xl text-lg leading-relaxed text-ink-700">{text}</p>
      <form onSubmit={submit} role="search" className="mt-10 flex flex-col gap-3 sm:flex-row">
        <label htmlFor="hero-search-query" className="sr-only">Search</label>
        <input id="hero-search-query" type="search" value={query} onChange={(event) => setQuery(event.target.value)} placeholder={placeholder} className="field flex-1 py-4 text-lg" />
        <button type="submit" className="btn-primary">{button}</button>
      </form>
      <p className="mt-5 text-sm text-ink-500">
        <span className="mr-2">Popular:</span>
        {popular.map((term) => (
          <button key={term} type="button" onClick={() => setQuery(term)} className="mr-3 inline-block py-1 font-medium text-ink-900 underline decoration-ink-300 underline-offset-4 hover:decoration-brand-600">
            {term}
          </button>
        ))}
      </p>
    </section>
  );
}

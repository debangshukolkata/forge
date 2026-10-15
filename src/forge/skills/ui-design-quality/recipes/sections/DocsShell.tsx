// A documentation page: a sticky left navigation of sections, the article (headings, paragraphs, a code block, a note) and a right-hand "On this page" list.
// On a phone the navigation folds into a native <details> at the top and the right-hand list disappears. The code block scrolls inside its frame; copy the real text in.
export type DocsLink = { label: string; href: string; current?: boolean };
export type DocsGroup = { title: string; links: DocsLink[] };

const DEFAULT_NAV: DocsGroup[] = [
  { title: "Getting started", links: [{ label: "Introduction", href: "#intro" }, { label: "Install", href: "#install", current: true }, { label: "First request", href: "#first" }] },
  { title: "Guides", links: [{ label: "Authentication", href: "#auth" }, { label: "Pagination", href: "#paging" }, { label: "Errors", href: "#errors" }] },
  { title: "Reference", links: [{ label: "Endpoints", href: "#endpoints" }, { label: "Webhooks", href: "#webhooks" }] },
];

export default function DocsShell({
  product = "Relay API",
  nav = DEFAULT_NAV,
}: {
  product?: string;
  nav?: DocsGroup[];
}) {
  const sidebar = (
    <nav aria-label="Documentation" className="space-y-6 text-sm">
      {nav.map((group) => (
        <div key={group.title}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-500">{group.title}</p>
          <ul className="space-y-1">
            {group.links.map((link) => (
              <li key={link.href}>
                <a href={link.href} aria-current={link.current ? "page" : undefined} className={`block rounded-lg px-3 py-1.5 transition ${link.current ? "bg-brand-50 font-semibold text-brand-700" : "text-ink-700 hover:bg-ink-100 hover:text-ink-900"}`}>
                  {link.label}
                </a>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </nav>
  );
  return (
    <div className="mx-auto grid max-w-7xl gap-10 px-4 py-10 sm:px-6 lg:grid-cols-[14rem_minmax(0,1fr)_12rem]">
      <details className="rounded-xl border border-ink-200 bg-white p-4 lg:hidden">
        <summary className="cursor-pointer text-sm font-semibold text-ink-900">Menu: {product} documentation</summary>
        <div className="mt-4">{sidebar}</div>
      </details>
      <aside className="sticky top-20 hidden h-fit lg:block">{sidebar}</aside>
      <article className="min-w-0 max-w-3xl">
        <p className="eyebrow">Getting started</p>
        <h1 className="mt-2 text-4xl font-semibold">Install the client</h1>
        <p className="mt-4 text-lg text-ink-700">The {product} client is a single package with no dependencies. It works in Node 18 and later and in any modern browser.</p>
        <h2 id="install" className="mt-12 text-2xl font-semibold">Install</h2>
        <p className="mt-3 text-ink-700">Add the package with your package manager, then create one client for the whole app.</p>
        <pre className="mt-4 overflow-x-auto rounded-xl bg-ink-900 p-5 text-sm leading-relaxed text-ink-100" tabIndex={0}>
          <code>{`npm install @relay/client

import { Relay } from "@relay/client";

const relay = new Relay({ key: process.env.RELAY_KEY });
const page = await relay.events.list({ limit: 20 });`}</code>
        </pre>
        <p className="mt-4 rounded-xl border border-ink-200 bg-ink-100 p-4 text-sm text-ink-700">
          <strong className="text-ink-900">Keep your key private.</strong> Use it only on a server; the browser build takes a short-lived token instead.
        </p>
        <h2 id="first" className="mt-12 text-2xl font-semibold">Make your first request</h2>
        <p className="mt-3 text-ink-700">Every call returns a page of results and a cursor. Pass the cursor back to get the next page.</p>
        <ul className="mt-4 list-disc space-y-2 pl-6 text-ink-700">
          <li>Requests are authenticated with the key in the <code className="rounded bg-ink-100 px-1.5 py-0.5 text-sm text-ink-900">Authorization</code> header.</li>
          <li>Responses are JSON; dates are ISO 8601 in UTC.</li>
          <li>A request that fails returns an error object with a code and a message you can show.</li>
        </ul>
      </article>
      <aside aria-label="On this page" className="sticky top-20 hidden h-fit text-sm xl:block lg:block">
        <p className="mb-2 text-xs font-semibold uppercase tracking-[0.12em] text-ink-500">On this page</p>
        <ul className="space-y-2 border-l border-ink-200 pl-4">
          <li><a href="#install" className="text-ink-700 hover:text-brand-700">Install</a></li>
          <li><a href="#first" className="text-ink-700 hover:text-brand-700">Make your first request</a></li>
        </ul>
      </aside>
    </div>
  );
}

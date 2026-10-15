import NavBar from "./sections/NavBar";
import DocsShell from "./sections/DocsShell";
import FooterColumns from "./sections/FooterColumns";

// Product documentation: Inter with a monospace for code (JetBrains Mono), teal on slate, a left navigation, an article and an "On this page" list. The example
// documents a fictional API; replace the navigation and the article with the real documentation, and keep the code blocks as real, copyable text.
export default function App() {
  return (
    <>
      <NavBar
        brand="Relay docs"
        links={[
          { label: "Guides", href: "#intro" },
          { label: "API reference", href: "#endpoints" },
          { label: "Changelog", href: "#top" },
        ]}
        cta={{ label: "Get an API key", href: "#auth" }}
      />
      <main id="top">
        <DocsShell product="Relay" />
      </main>
      <FooterColumns
        brand="Relay"
        blurb="Events, delivered. Documentation for version 3."
        columns={[
          { heading: "Docs", links: [{ label: "Guides", href: "#intro" }, { label: "API reference", href: "#endpoints" }] },
          { heading: "Help", links: [{ label: "support@relay.example", href: "mailto:support@relay.example" }, { label: "Status", href: "#top" }] },
        ]}
        legal="© 2026 Relay. All rights reserved."
      />
    </>
  );
}

import FormLogin from "./sections/FormLogin";
import FooterMinimal from "./sections/FooterMinimal";

// Sign-in page: nothing but the form and a quiet footer, in the launch palette (indigo on neutral grey, Space Grotesk + Inter). The page has no
// navigation on purpose: a sign-in screen has one job. Wire FormLogin's onSubmit to the real back end and return the refusal text it should show; do not
// keep the password anywhere. Replace the product name and the links to the real "forgotten password" and "create account" pages.
export default function App() {
  return (
    <>
      <main className="min-h-[70vh]">
        <p className="mx-auto max-w-md px-4 pt-12 font-display text-2xl font-semibold text-ink-900 sm:px-6">Ledgerly</p>
        <FormLogin title="Sign in to Ledgerly" text="Welcome back. Your weekly summary is waiting." />
      </main>
      <FooterMinimal brand="Ledgerly" legal="© 2026 Ledgerly Ltd." links={[{ label: "Privacy", href: "#privacy" }, { label: "Help", href: "#help" }]} />
    </>
  );
}

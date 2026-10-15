// A dark full-width band that changes the subject from what is sold to how it is made: a picture of the maker's hands or the workshop on one side, the story and
// three short steps on the other. The colour shift is the punctuation of the page: use it once. Pass your own picture as children (a photograph of hands or the
// process works best); the drawn stand-in is only a placeholder. Stacks on a phone, the text first.
import type { ReactNode } from "react";

export type CraftStep = { title: string; text: string };

function DefaultPicture() {
  return (
    <div aria-hidden="true" className="relative aspect-[4/5] w-full overflow-hidden rounded-card bg-ink-700">
      <div className="absolute left-[12%] top-[16%] h-[38%] w-[38%] rounded-full bg-brand-500" />
      <div className="absolute bottom-0 left-0 h-[34%] w-full bg-ink-200" />
      <div className="absolute bottom-[26%] right-[12%] h-[22%] w-[46%] rounded-t-full bg-brand-200" />
    </div>
  );
}

export default function CraftBand({
  eyebrow = "How it is made",
  title = "Thirty-six hours, one starter and two pairs of hands.",
  text = "The dough is mixed at four in the afternoon, folded through the night and shaped before the first light. Nothing is rushed, because the flavour is in the waiting.",
  steps = [
    { title: "Mix and rest", text: "Organic flour, water, salt and the starter. Left alone for the first hour." },
    { title: "Fold and wait", text: "Folded by hand every forty minutes, then a cold night in the fridge." },
    { title: "Shape and bake", text: "Shaped at five, baked on stone until the crust sings." },
  ],
  children,
}: {
  eyebrow?: string;
  title?: string;
  text?: string;
  steps?: CraftStep[];
  children?: ReactNode;
}) {
  return (
    <section id="craft" className="bg-ink-900 text-ink-100">
      <div className="mx-auto grid max-w-6xl items-center gap-10 px-4 py-16 sm:px-6 md:grid-cols-2 md:gap-16 md:py-24">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.14em] text-brand-200">{eyebrow}</p>
          <h2 className="mt-3 text-3xl font-semibold text-white! sm:text-4xl">{title}</h2>
          <p className="mt-4 max-w-xl text-lg text-ink-200">{text}</p>
          <ol className="mt-8 divide-y divide-ink-700 border-y border-ink-700">
            {steps.map((step, index) => (
              <li key={step.title} className="flex gap-5 py-4">
                <span className="w-9 shrink-0 font-display text-2xl tabular-nums text-brand-200">{String(index + 1).padStart(2, "0")}</span>
                <div>
                  <h3 className="text-lg font-semibold text-white!">{step.title}</h3>
                  <p className="text-ink-200">{step.text}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
        <div className="mx-auto w-full max-w-md md:max-w-none">{children ?? <DefaultPicture />}</div>
      </div>
    </section>
  );
}

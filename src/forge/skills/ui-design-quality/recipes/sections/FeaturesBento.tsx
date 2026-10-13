// Bento grid: unequal tiles, each holding one idea. Four columns on desktop, two on tablet, one on a phone.
// `span` makes a tile wider (2) and `tall` makes it taller; keep one big tile and a few small ones, and check that the
// tiles fill every row of the four-column grid (here: 2x2 + 4 singles + two double-width tiles).
import ArtTile, { type ArtVariant } from "./ArtTile";

export type Tile = { title: string; text: string; span?: 1 | 2; tall?: boolean; art?: ArtVariant; dark?: boolean };

export default function FeaturesBento({
  eyebrow = "Features",
  title = "Small pieces that fit together",
  tiles = [
    { title: "Weekly briefing", text: "One page every Monday: what moved, why, and what to try.", span: 2, tall: true, art: "bars" },
    { title: "Plain language", text: "No jargon. Written for the person who has to act on it." },
    { title: "Every source", text: "Sheets, databases and CSV files, side by side." },
    { title: "Alerts that matter", text: "Only when a number leaves its normal range.", dark: true },
    { title: "Team comments", text: "Ask and answer right next to the number in question." },
    { title: "Share in one click", text: "A link that works for everyone, no login needed.", span: 2 },
    { title: "Open API", text: "Send data in and pull briefings out with a few lines of code.", span: 2 },
  ],
}: {
  eyebrow?: string;
  title?: string;
  tiles?: Tile[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-12 grid auto-rows-[minmax(11rem,auto)] gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {tiles.map((tile) => (
          <article
            key={tile.title}
            className={[
              "flex flex-col justify-between overflow-hidden rounded-card border p-6",
              tile.dark ? "border-ink-900 bg-ink-900 text-ink-50" : "border-ink-200 bg-white shadow-soft",
              tile.span === 2 ? "sm:col-span-2" : "",
              tile.tall ? "lg:row-span-2" : "",
            ].join(" ")}
          >
            <div>
              <h3 className={`text-xl font-semibold ${tile.dark ? "!text-ink-50" : ""}`}>{tile.title}</h3>
              <p className={`mt-2 ${tile.dark ? "text-ink-300" : "text-ink-700"}`}>{tile.text}</p>
            </div>
            {tile.art && <ArtTile variant={tile.art} className="mt-6 !aspect-[16/9]" />}
          </article>
        ))}
      </div>
    </section>
  );
}

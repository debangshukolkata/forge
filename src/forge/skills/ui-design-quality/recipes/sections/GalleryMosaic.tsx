// A mosaic of tiles of different sizes (a large one, tall ones, wide ones) with a caption on each, in place of a grid of identical squares.
// Without pictures the tiles are drawn shapes in the theme colours; give a tile `src` and `alt` to show a real photograph (it fills the tile, cropped).
// Six tiles fill the pattern (4 columns by 3 rows on a wide screen); fewer leave gaps, so keep six. The caption sits on a dark strip so it is readable on every tile.
export type MosaicTile = {
  caption: string;
  tone?: "brand" | "ink" | "soft" | "pale";
  shape?: "arch" | "circle" | "stripes" | "bars";
  src?: string;
  alt?: string;
};

const SPANS = ["col-span-2 row-span-2", "", "row-span-2", "", "col-span-2", "col-span-2"]; // 4 columns x 3 rows, no gaps
const TONES = {
  brand: "bg-brand-600",
  ink: "bg-ink-700",
  soft: "bg-brand-100",
  pale: "bg-ink-200",
};
const SHAPE_COLOUR = { brand: "bg-brand-200", ink: "bg-brand-500", soft: "bg-brand-500", pale: "bg-brand-600" };

function Shape({ shape, tone }: { shape: NonNullable<MosaicTile["shape"]>; tone: keyof typeof TONES }) {
  const colour = SHAPE_COLOUR[tone];
  if (shape === "arch") return <div aria-hidden="true" className={`absolute bottom-0 left-1/2 h-3/5 w-1/2 -translate-x-1/2 rounded-t-full ${colour}`} />;
  if (shape === "circle") return <div aria-hidden="true" className={`absolute right-[12%] top-[14%] aspect-square w-2/5 rounded-full ${colour}`} />;
  if (shape === "bars") {
    return (
      <div aria-hidden="true" className="absolute inset-x-[12%] bottom-0 top-[18%] flex items-end gap-[6%]">
        {[45, 80, 60, 95].map((height) => (
          <span key={height} style={{ height: `${height}%` }} className={`flex-1 rounded-t-md ${colour}`} />
        ))}
      </div>
    );
  }
  return <div aria-hidden="true" className={`absolute inset-0 opacity-30 ${colour}`} style={{ clipPath: "polygon(0 0, 100% 0, 0 100%)" }} />;
}

export default function GalleryMosaic({
  eyebrow = "From the studio",
  title = "Things made here this season.",
  tiles = [
    { caption: "Salt-glazed jugs, first firing of the year", tone: "brand", shape: "arch" },
    { caption: "Tea bowls", tone: "soft", shape: "circle" },
    { caption: "A shelf of test tiles", tone: "ink", shape: "bars" },
    { caption: "Hand-built planter", tone: "pale", shape: "stripes" },
    { caption: "Open day in the old mill, 12 October", tone: "soft", shape: "arch" },
    { caption: "Wax resist", tone: "brand", shape: "circle" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  tiles?: MosaicTile[];
}) {
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <div className="mt-10 grid auto-rows-[9rem] grid-cols-2 gap-3 sm:auto-rows-[11rem] md:grid-cols-4 md:auto-rows-[12rem]">
        {tiles.map((tile, index) => {
          const tone = tile.tone ?? "soft";
          return (
            <figure key={tile.caption} className={`relative overflow-hidden rounded-card ${TONES[tone]} ${SPANS[index % SPANS.length]}`}>
              {tile.src ? (
                <img src={tile.src} alt={tile.alt ?? tile.caption} loading="lazy" className="h-full w-full object-cover" />
              ) : (
                <Shape shape={tile.shape ?? "circle"} tone={tone} />
              )}
              <figcaption className="absolute inset-x-0 bottom-0 bg-ink-900 px-3 py-2 text-sm font-medium text-white">{tile.caption}</figcaption>
            </figure>
          );
        })}
      </div>
    </section>
  );
}

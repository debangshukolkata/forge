// A grid of products: a drawn picture, name, short description, price and one add-to-basket button each. Two columns on a phone, four on desktop.
// Prices are plain text so any currency works. Replace ArtTile with real photographs (same aspect ratio) when the shop has them; keep the button label specific.
import ArtTile, { type ArtVariant } from "./ArtTile";

export type Product = { name: string; text: string; price: string; tag?: string; art?: ArtVariant };

export default function ProductGrid({
  eyebrow = "The shop",
  title = "Made in small batches",
  products = [
    { name: "Stoneware mug", text: "Hand-thrown, 300 ml, dishwasher safe.", price: "€28", tag: "Bestseller", art: "orbs" },
    { name: "Linen tea towel", text: "Stonewashed, 50 x 70 cm.", price: "€14", art: "grid" },
    { name: "Walnut serving board", text: "Oiled, with a leather loop.", price: "€46", art: "stack" },
    { name: "Beeswax candle", text: "Burns for 40 hours.", price: "€18", tag: "New", art: "bars" },
    { name: "Ceramic jug", text: "Holds one litre, pours cleanly.", price: "€39", art: "orbs" },
    { name: "Wool throw", text: "Undyed lambswool, 130 x 180 cm.", price: "€92", art: "stack" },
    { name: "Brass bud vase", text: "For a single stem.", price: "€24", art: "grid" },
    { name: "Gift box", text: "Mug, candle and tea, wrapped.", price: "€58", tag: "Gift", art: "bars" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  products?: Product[];
}) {
  return (
    <section id="shop" className="mx-auto max-w-6xl px-4 py-16 sm:px-6 md:py-24">
      <p className="eyebrow">{eyebrow}</p>
      <h2 className="mt-3 max-w-2xl text-3xl font-semibold sm:text-4xl">{title}</h2>
      <ul className="mt-12 grid grid-cols-2 gap-x-4 gap-y-10 lg:grid-cols-4">
        {products.map((product) => (
          <li key={product.name} className="group flex flex-col">
            <div className="relative">
              <ArtTile variant={product.art ?? "orbs"} className="!aspect-square transition duration-300 group-hover:-translate-y-1" />
              {product.tag && (
                <span className="absolute left-3 top-3 rounded-full bg-white px-3 py-1 text-xs font-semibold text-ink-900 shadow-soft">{product.tag}</span>
              )}
            </div>
            <h3 className="mt-4 text-base font-semibold">{product.name}</h3>
            <p className="mt-1 flex-1 text-sm text-ink-700">{product.text}</p>
            <p className="mt-3 flex items-center justify-between gap-3">
              <span className="font-display text-xl font-semibold tabular-nums text-ink-900">{product.price}</span>
              <button type="button" className="btn-secondary !px-4 !py-2" aria-label={`Add ${product.name} to basket`}>
                Add
              </button>
            </p>
          </li>
        ))}
      </ul>
    </section>
  );
}

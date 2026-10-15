// A text block on the left and three products on the right, each a tall picture with its name and one line beneath, the middle one set lower so the row
// is not a line of equal boxes. No card frames: the picture is the object. Give each product `src` and `alt` for a real photograph; without them a drawn
// stand-in in the theme colours is shown (replace it before the page ships). Stacks on a phone, the text first.
export type Product = { name: string; text: string; note?: string; src?: string; alt?: string; tone?: "brand" | "soft" | "pale" };

const TONES = { brand: "bg-brand-600", soft: "bg-brand-100", pale: "bg-ink-200" };
const SHAPES = ["rounded-t-full", "rounded-full", "rounded-t-3xl"];

function Stand({ tone, index }: { tone: keyof typeof TONES; index: number }) {
  const inner = tone === "brand" ? "bg-brand-200" : "bg-brand-500";
  return (
    <div aria-hidden="true" className={`relative aspect-[3/4] w-full overflow-hidden rounded-card ${TONES[tone]}`}>
      <div className={`absolute bottom-0 left-1/2 h-3/5 w-3/5 -translate-x-1/2 ${SHAPES[index % SHAPES.length]} ${inner}`} />
    </div>
  );
}

export default function ProductTrio({
  eyebrow = "Baked every morning",
  title = "Three things worth getting up early for.",
  intro = "Everything is made on the premises from organic flour and a sourdough starter that is older than the shop. When it is gone, it is gone.",
  link = { label: "See the full menu", href: "#menu" },
  products = [
    { name: "The country loaf", text: "A crackling crust and an open, sour crumb. Thirty-six hours from mixing to the oven.", note: "From 4.80", tone: "soft" },
    { name: "Cardamom bun", text: "Soft, sticky and still warm at eight. Baked in small batches until they sell out.", note: "From 3.20", tone: "brand" },
    { name: "Seasonal tart", text: "Whatever the market has: plums in September, rhubarb in spring.", note: "From 5.50", tone: "pale" },
  ],
}: {
  eyebrow?: string;
  title?: string;
  intro?: string;
  link?: { label: string; href: string };
  products?: Product[];
}) {
  return (
    <section id="menu" className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-12 md:gap-10 md:py-24">
      <div className="md:col-span-4">
        <p className="eyebrow">{eyebrow}</p>
        <h2 className="mt-3 text-3xl font-semibold sm:text-4xl">{title}</h2>
        <p className="mt-4 text-lg text-ink-700">{intro}</p>
        <a href={link.href} className="mt-6 inline-block font-semibold text-brand-700 underline decoration-brand-200 underline-offset-4 hover:decoration-brand-600">
          {link.label}
        </a>
      </div>
      <ul className="grid gap-8 sm:grid-cols-3 md:col-span-8 md:gap-6">
        {products.slice(0, 3).map((product, index) => (
          <li key={product.name} className={index === 1 ? "sm:mt-12" : ""}>
            {product.src ? (
              <img src={product.src} alt={product.alt ?? product.name} loading="lazy" className="aspect-[3/4] w-full rounded-card object-cover" />
            ) : (
              <Stand tone={product.tone ?? "soft"} index={index} />
            )}
            <h3 className="mt-4 text-xl font-semibold">{product.name}</h3>
            <p className="mt-1 text-ink-700">{product.text}</p>
            {product.note && <p className="mt-2 text-sm font-semibold text-ink-900">{product.note}</p>}
          </li>
        ))}
      </ul>
    </section>
  );
}

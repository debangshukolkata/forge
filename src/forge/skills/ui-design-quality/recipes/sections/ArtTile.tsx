// Decorative visual used by the sections when a page has no photo: abstract shapes drawn with the theme colours, so it
// always matches the palette. Variants: "orbs" (soft circles), "bars" (a mock chart), "stack" (layered cards), "grid" (dots).
// Replace it with a real image or illustration when the product has one; keep the same rounded frame and aspect ratio.
export type ArtVariant = "orbs" | "bars" | "stack" | "grid";

export default function ArtTile({ variant = "orbs", className = "" }: { variant?: ArtVariant; className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`relative aspect-[4/3] w-full overflow-hidden rounded-card bg-gradient-to-br from-brand-50 to-brand-100 ${className}`}
    >
      {variant === "orbs" && (
        <>
          <div className="absolute left-[12%] top-[16%] h-[46%] w-[46%] rounded-full bg-brand-200/80" />
          <div className="absolute bottom-[10%] right-[10%] h-[58%] w-[58%] rounded-full bg-brand-500/90" />
          <div className="absolute bottom-[18%] left-[22%] h-[22%] w-[22%] rounded-full bg-white/90 shadow-soft" />
        </>
      )}
      {variant === "bars" && (
        <div className="absolute inset-[10%] flex items-end gap-[5%]">
          {[38, 62, 48, 80, 58, 92].map((h, i) => (
            <div
              key={i}
              style={{ height: `${h}%` }}
              className={`flex-1 rounded-t-lg ${i === 5 ? "bg-brand-600" : "bg-brand-200"}`}
            />
          ))}
        </div>
      )}
      {variant === "stack" && (
        <>
          <div className="absolute left-[10%] top-[12%] h-[52%] w-[62%] rounded-2xl bg-white/70 shadow-soft" />
          <div className="absolute left-[20%] top-[26%] h-[52%] w-[62%] rounded-2xl bg-white shadow-soft" />
          <div className="absolute left-[30%] top-[40%] h-[46%] w-[60%] rounded-2xl bg-brand-600 shadow-lift" />
        </>
      )}
      {variant === "grid" && (
        <div className="absolute inset-[8%] grid grid-cols-8 gap-[4%]">
          {Array.from({ length: 48 }, (_, i) => (
            <span key={i} className={`rounded-full ${[5, 14, 22, 29, 38].includes(i) ? "bg-brand-600" : "bg-brand-200"}`} />
          ))}
        </div>
      )}
    </div>
  );
}

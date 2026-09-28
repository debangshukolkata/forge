// The cost in the top bar: counts up smoothly to each new total and flashes briefly when it increases (the
// user's choice: counter only, USD). Figures are Forge's estimates (tokens x configured prices), not the bill.
import { Coins } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { cx, money } from "../lib";

const DURATION_MS = 700;

function reducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
}

export function AnimatedCost({ total }: { total: number }) {
  const [shown, setShown] = useState(total);
  const [flash, setFlash] = useState(false);
  const from = useRef(total);
  const frame = useRef<number | null>(null);

  useEffect(() => {
    const start = from.current;
    if (total === start) return;
    if (total > start) {
      setFlash(true);
      window.setTimeout(() => setFlash(false), 900);
    }
    if (reducedMotion() || total < start) {
      from.current = total;
      setShown(total);
      return;
    }
    const began = performance.now();
    const step = (now: number) => {
      const t = Math.min(1, (now - began) / DURATION_MS);
      const eased = 1 - Math.pow(1 - t, 3); // ease-out: fast at first, settling on the value
      const value = start + (total - start) * eased;
      setShown(value);
      from.current = value;
      if (t < 1) frame.current = requestAnimationFrame(step);
      else from.current = total;
    };
    frame.current = requestAnimationFrame(step);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
    };
  }, [total]);

  return (
    <span
      className={cx(
        "hidden items-center gap-1.5 rounded-md px-1.5 py-0.5 text-[12.5px] transition-colors duration-300 md:flex",
        flash ? "bg-accent-soft text-accent" : "text-fg-muted",
      )}
      title="Estimated cost so far (tokens x configured prices)"
    >
      <Coins className="h-3.5 w-3.5" aria-hidden />
      <span className="font-mono tabular-nums">{money(shown)}</span>
      <span className="sr-only" aria-live="off">
        {money(total)}
      </span>
    </span>
  );
}

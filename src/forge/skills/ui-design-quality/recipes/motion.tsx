// Motion helpers for React (no animation library needed). Use with motion.css.
//   <Reveal><h2>…</h2></Reveal>                      fade/slide in when scrolled into view
//   {items.map((x, i) => <Reveal key={x} index={i}>…</Reveal>)}   staggered
//   <CountUp to={450} suffix="+" />                  number that counts up once when visible
//   <Marquee>{logos}</Marquee>                       endless horizontal strip
//   <SpotlightCard className="card">…</SpotlightCard>  glow that follows the pointer
//   <TiltCard className="card">…</TiltCard>          gentle 3D tilt on hover (pointer devices only)
import { useEffect, useRef, useState, type CSSProperties, type ElementType, type ReactNode, type PointerEvent } from "react";

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** True once the element has entered the viewport (and stays true). Without IntersectionObserver it is true at once. */
export function useInView<T extends HTMLElement>(threshold = 0.15) {
  const ref = useRef<T>(null);
  const [seen, setSeen] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el || seen) return;
    if (typeof IntersectionObserver === "undefined" || reducedMotion()) return setSeen(true);
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setSeen(true);
          observer.disconnect();
        }
      },
      { threshold, rootMargin: "0px 0px -8% 0px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [seen, threshold]);
  return [ref, seen] as const;
}

export function Reveal({
  children,
  index = 0,
  as: Tag = "div",
  variant = "",
  className = "",
}: {
  children: ReactNode;
  index?: number;
  as?: ElementType;
  variant?: "" | "reveal-left" | "reveal-scale";
  className?: string;
}) {
  const [ref, seen] = useInView<HTMLElement>();
  return (
    <Tag ref={ref} className={`reveal ${variant} ${seen ? "is-visible" : ""} ${className}`} style={{ "--i": index } as CSSProperties}>
      {children}
    </Tag>
  );
}

/** Counts from 0 to `to` with an ease-out curve the first time it is visible. Keeps the final number in the DOM
 *  for screen readers and for people who prefer reduced motion. */
export function CountUp({ to, duration = 1400, prefix = "", suffix = "" }: { to: number; duration?: number; prefix?: string; suffix?: string }) {
  const [ref, seen] = useInView<HTMLSpanElement>(0.4);
  const [value, setValue] = useState(reducedMotion() ? to : 0);
  useEffect(() => {
    if (!seen || reducedMotion()) return setValue(to);
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min((now - start) / duration, 1);
      setValue(Math.round(to * (1 - Math.pow(1 - progress, 3)))); // easeOutCubic
      if (progress < 1) frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [seen, to, duration]);
  return (
    <span ref={ref} aria-label={`${prefix}${to}${suffix}`}>
      {prefix}
      {value.toLocaleString()}
      {suffix}
    </span>
  );
}

/** Duplicates its children so the track can slide by exactly half its width without a jump. */
export function Marquee({ children }: { children: ReactNode }) {
  return (
    <div className="marquee" aria-label="Partners">
      <div className="marquee-track">
        <div className="flex gap-12">{children}</div>
        <div className="flex gap-12" aria-hidden>
          {children}
        </div>
      </div>
    </div>
  );
}

export function SpotlightCard({ children, className = "" }: { children: ReactNode; className?: string }) {
  function move(event: PointerEvent<HTMLDivElement>) {
    const box = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--x", `${event.clientX - box.left}px`);
    event.currentTarget.style.setProperty("--y", `${event.clientY - box.top}px`);
  }
  return (
    <div className={`spotlight ${className}`} onPointerMove={move}>
      {children}
    </div>
  );
}

export function TiltCard({ children, className = "", max = 6 }: { children: ReactNode; className?: string; max?: number }) {
  function move(event: PointerEvent<HTMLDivElement>) {
    if (event.pointerType !== "mouse" || reducedMotion()) return;
    const box = event.currentTarget.getBoundingClientRect();
    const x = (event.clientX - box.left) / box.width - 0.5;
    const y = (event.clientY - box.top) / box.height - 0.5;
    event.currentTarget.style.setProperty("--ry", `${x * max * 2}deg`);
    event.currentTarget.style.setProperty("--rx", `${-y * max * 2}deg`);
  }
  function leave(event: PointerEvent<HTMLDivElement>) {
    event.currentTarget.style.setProperty("--rx", "0deg");
    event.currentTarget.style.setProperty("--ry", "0deg");
  }
  return (
    <div className={`tilt ${className}`} onPointerMove={move} onPointerLeave={leave}>
      {children}
    </div>
  );
}

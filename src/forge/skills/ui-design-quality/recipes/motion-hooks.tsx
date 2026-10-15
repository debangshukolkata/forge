// More motion for React, beside motion.tsx (D-383). No animation library; import motion-hooks.css once.
//   <SplitText text="Give blood, give time" by="word" />      words (or letters) rise in one after another when scrolled into view
//   <ScrambleText text="Open every day" />                    letters settle from noise to the real text once; the text is the aria-label
//   <Magnetic><button className="btn">Donate</button></Magnetic>   the child leans toward the pointer (pointer devices only)
//   <PinnedSteps steps={[{ title, body }, ...]} />            a list of steps that stays in view while the active one follows the scroll
//   const [ref, progress] = useScrollProgress<HTMLDivElement>()   0 to 1 while the element crosses the viewport
//   <Parallax speed={0.2}>…</Parallax>                        a layer that moves slower or faster than the page
// Everything shows its final state at once under prefers-reduced-motion, and the real text is always in the DOM for screen readers.
import { useEffect, useRef, useState, type CSSProperties, type ReactNode, type PointerEvent } from "react";

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/** True once the element has entered the viewport (and stays true). Without IntersectionObserver, or when motion is reduced, it is true at once. */
function useSeen<T extends HTMLElement>(threshold = 0.2) {
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
      { threshold },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [seen, threshold]);
  return [ref, seen] as const;
}

/** Words or letters that rise in with a stagger. The whole text is the aria-label; the pieces are hidden from assistive technology. */
export function SplitText({ text, by = "word", className = "" }: { text: string; by?: "word" | "letter"; className?: string }) {
  const [ref, seen] = useSeen<HTMLSpanElement>();
  const pieces = by === "word" ? text.split(" ") : Array.from(text);
  return (
    <span ref={ref} className={`split-text ${seen ? "is-visible" : ""} ${className}`} aria-label={text}>
      {pieces.map((piece, i) => (
        <span key={i} className="split-piece" aria-hidden="true" style={{ "--i": i } as CSSProperties}>
          {piece === " " ? " " : piece}
          {by === "word" && i < pieces.length - 1 ? " " : ""}
        </span>
      ))}
    </span>
  );
}

const NOISE = "ABCDEFGHJKLMNPQRSTUVWXYZ0123456789#%&*+=";

/** Letters change at random and settle left to right into `text`, once, when visible. */
export function ScrambleText({ text, duration = 900, className = "" }: { text: string; duration?: number; className?: string }) {
  const [ref, seen] = useSeen<HTMLSpanElement>(0.4);
  const [shown, setShown] = useState(text);
  useEffect(() => {
    if (!seen || reducedMotion()) return;
    let frame = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const progress = Math.min(1, (now - start) / duration);
      const settled = Math.floor(progress * text.length);
      setShown(
        Array.from(text)
          .map((ch, i) => (i < settled || ch === " " ? ch : NOISE[Math.floor(Math.random() * NOISE.length)]))
          .join(""),
      );
      if (progress < 1) frame = requestAnimationFrame(tick);
      else setShown(text);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [seen, text, duration]);
  return (
    <span ref={ref} className={`scramble-text ${className}`} aria-label={text}>
      <span aria-hidden="true">{shown}</span>
    </span>
  );
}

/** The child leans up to `strength` pixels toward the pointer while it is near, and springs back when it leaves. Touch devices see no effect. */
export function Magnetic({ children, strength = 10, className = "" }: { children: ReactNode; strength?: number; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const move = (event: PointerEvent<HTMLSpanElement>) => {
    const el = ref.current;
    if (!el || event.pointerType === "touch" || reducedMotion()) return;
    const box = el.getBoundingClientRect();
    const x = ((event.clientX - (box.left + box.width / 2)) / (box.width / 2)) * strength;
    const y = ((event.clientY - (box.top + box.height / 2)) / (box.height / 2)) * strength;
    el.style.transform = `translate(${x.toFixed(1)}px, ${y.toFixed(1)}px)`;
  };
  const leave = () => {
    if (ref.current) ref.current.style.transform = "";
  };
  return (
    <span ref={ref} className={`magnetic ${className}`} onPointerMove={move} onPointerLeave={leave}>
      {children}
    </span>
  );
}

/** 0 to 1 while the element travels through the viewport (0 when its top meets the bottom edge, 1 when its bottom leaves the top). */
export function useScrollProgress<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [progress, setProgress] = useState(0);
  useEffect(() => {
    if (reducedMotion()) return;
    let frame = 0;
    const measure = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => {
        const el = ref.current;
        if (!el) return;
        const box = el.getBoundingClientRect();
        const travel = window.innerHeight + box.height;
        setProgress(Math.min(1, Math.max(0, (window.innerHeight - box.top) / travel)));
      });
    };
    measure();
    window.addEventListener("scroll", measure, { passive: true });
    window.addEventListener("resize", measure);
    return () => {
      cancelAnimationFrame(frame);
      window.removeEventListener("scroll", measure);
      window.removeEventListener("resize", measure);
    };
  }, []);
  return [ref, progress] as const;
}

/** A layer that moves by `speed` times the scroll distance (0.2 = a fifth as fast as the page in the opposite direction; negative moves with it faster). */
export function Parallax({ children, speed = 0.2, className = "" }: { children: ReactNode; speed?: number; className?: string }) {
  const [ref, progress] = useScrollProgress<HTMLDivElement>();
  const shift = (progress - 0.5) * speed * 400;
  return (
    <div ref={ref} className={`parallax ${className}`} style={{ transform: `translateY(${shift.toFixed(1)}px)` }}>
      {children}
    </div>
  );
}

export type Step = { title: string; body: string };

/** Steps listed on the left; the matching panel on the right stays pinned while the page scrolls past each step. Each step is also a heading and a paragraph in the document order. */
export function PinnedSteps({ steps, className = "" }: { steps: Step[]; className?: string }) {
  const [active, setActive] = useState(0);
  const refs = useRef<(HTMLElement | null)[]>([]);
  useEffect(() => {
    if (typeof IntersectionObserver === "undefined") return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(Number((entry.target as HTMLElement).dataset.index));
        }
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    refs.current.forEach((el) => el && observer.observe(el));
    return () => observer.disconnect();
  }, [steps.length]);
  return (
    <div className={`pinned-steps ${className}`}>
      <ol className="pinned-list">
        {steps.map((step, i) => (
          <li key={step.title} data-index={i} ref={(el) => {
              refs.current[i] = el;
            }} className={i === active ? "is-active" : ""}>
            <h3>{step.title}</h3>
            <p>{step.body}</p>
          </li>
        ))}
      </ol>
      <div className="pinned-panel" aria-hidden="true">
        <span className="pinned-number">{String(active + 1).padStart(2, "0")}</span>
        <span className="pinned-label">{steps[active]?.title}</span>
      </div>
    </div>
  );
}

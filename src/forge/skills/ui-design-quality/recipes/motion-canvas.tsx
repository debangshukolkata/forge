// Three showpiece effects that need a little code (D-384), all ours, no library. Use one per page at most and only as decoration.
//   <AnimatedBeam containerRef={box} fromRef={a} toRef={b} />   a light travels along a curve between two elements (integrations, "how it connects")
//   <Particles count={60} />                                      drifting dots with faint links, behind a hero (canvas, pauses when hidden)
//   <GlobeLite size={320} />                                      a slowly turning dotted globe (canvas, no map data: a sphere of dots)
// Colours come from the project's tokens (--color-primary, --color-muted). Under prefers-reduced-motion nothing moves: the beam is a still line, the particles and the
// globe are drawn once. They are decoration: put no text or control inside them and give them aria-hidden (they set it themselves).
import { useEffect, useRef, useState, type RefObject } from "react";

const reducedMotion = () => typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

function token(name: string, fallback: string): string {
  if (typeof document === "undefined") return fallback;
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;
}

/** A curve from the centre of `fromRef` to the centre of `toRef`, with a light that travels along it. `containerRef` is the positioned parent both elements sit in. */
export function AnimatedBeam({
  containerRef,
  fromRef,
  toRef,
  curvature = 40,
  duration = 3,
}: {
  containerRef: RefObject<HTMLElement | null>;
  fromRef: RefObject<HTMLElement | null>;
  toRef: RefObject<HTMLElement | null>;
  curvature?: number;
  duration?: number;
}) {
  const [geometry, setGeometry] = useState<{ d: string; width: number; height: number } | null>(null);
  useEffect(() => {
    const measure = () => {
      const box = containerRef.current?.getBoundingClientRect();
      const a = fromRef.current?.getBoundingClientRect();
      const b = toRef.current?.getBoundingClientRect();
      if (!box || !a || !b) return;
      const x1 = a.left - box.left + a.width / 2;
      const y1 = a.top - box.top + a.height / 2;
      const x2 = b.left - box.left + b.width / 2;
      const y2 = b.top - box.top + b.height / 2;
      setGeometry({ d: `M ${x1},${y1} Q ${(x1 + x2) / 2},${(y1 + y2) / 2 - curvature} ${x2},${y2}`, width: box.width, height: box.height });
    };
    measure();
    const observer = typeof ResizeObserver !== "undefined" ? new ResizeObserver(measure) : null;
    if (containerRef.current) observer?.observe(containerRef.current);
    window.addEventListener("resize", measure);
    return () => {
      observer?.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [containerRef, fromRef, toRef, curvature]);
  if (!geometry) return null;
  const moving = !reducedMotion();
  return (
    <svg className="beam" aria-hidden="true" width={geometry.width} height={geometry.height} viewBox={`0 0 ${geometry.width} ${geometry.height}`} style={{ position: "absolute", inset: 0, pointerEvents: "none" }}>
      <path d={geometry.d} fill="none" stroke="currentColor" strokeOpacity={0.18} strokeWidth={2} />
      {moving && (
        <path d={geometry.d} fill="none" stroke={token("--color-primary", "#4f46e5")} strokeWidth={2.5} strokeLinecap="round" pathLength={100} strokeDasharray="18 82" className="beam-light">
          <animate attributeName="stroke-dashoffset" from="100" to="0" dur={`${duration}s`} repeatCount="indefinite" />
        </path>
      )}
    </svg>
  );
}

/** Drifting dots; neighbours closer than `link` pixels are joined by a faint line. Pauses while the tab is hidden or the canvas is off screen. */
export function Particles({ count = 60, link = 110, className = "" }: { count?: number; link?: number; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    let width = 0;
    let height = 0;
    const dots = Array.from({ length: count }, () => ({ x: Math.random(), y: Math.random(), vx: (Math.random() - 0.5) * 0.00025, vy: (Math.random() - 0.5) * 0.00025 }));
    const colour = token("--color-primary", "#4f46e5");
    const resize = () => {
      width = canvas.clientWidth;
      height = canvas.clientHeight;
      canvas.width = Math.max(1, Math.round(width * ratio));
      canvas.height = Math.max(1, Math.round(height * ratio));
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    };
    const draw = (step: boolean) => {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = colour;
      ctx.strokeStyle = colour;
      for (const d of dots) {
        if (step) {
          d.x = (d.x + d.vx * 16 + 1) % 1;
          d.y = (d.y + d.vy * 16 + 1) % 1;
        }
        ctx.globalAlpha = 0.65;
        ctx.beginPath();
        ctx.arc(d.x * width, d.y * height, 2, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.lineWidth = 1;
      for (let i = 0; i < dots.length; i++) {
        for (let j = i + 1; j < dots.length; j++) {
          const dx = (dots[i].x - dots[j].x) * width;
          const dy = (dots[i].y - dots[j].y) * height;
          const distance = Math.hypot(dx, dy);
          if (distance < link) {
            ctx.globalAlpha = 0.18 * (1 - distance / link);
            ctx.beginPath();
            ctx.moveTo(dots[i].x * width, dots[i].y * height);
            ctx.lineTo(dots[j].x * width, dots[j].y * height);
            ctx.stroke();
          }
        }
      }
    };
    resize();
    draw(false);
    if (reducedMotion()) return;
    let frame = 0;
    let visible = true;
    const loop = () => {
      if (visible && !document.hidden) draw(true);
      frame = requestAnimationFrame(loop);
    };
    const observer = typeof IntersectionObserver !== "undefined" ? new IntersectionObserver(([entry]) => (visible = entry.isIntersecting)) : null;
    observer?.observe(canvas);
    window.addEventListener("resize", resize);
    frame = requestAnimationFrame(loop);
    return () => {
      cancelAnimationFrame(frame);
      observer?.disconnect();
      window.removeEventListener("resize", resize);
    };
  }, [count, link]);
  return <canvas ref={ref} className={`particles ${className}`} aria-hidden="true" style={{ display: "block", width: "100%", height: "100%" }} />;
}

/** A sphere of dots (latitude rings), turning about its vertical axis. Dots on the far side are fainter. */
export function GlobeLite({ size = 320, rings = 14, speed = 0.0004, className = "" }: { size?: number; rings?: number; speed?: number; className?: string }) {
  const ref = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;
    const ratio = Math.min(2, window.devicePixelRatio || 1);
    canvas.width = size * ratio;
    canvas.height = size * ratio;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    const colour = token("--color-primary", "#4f46e5");
    const points: [number, number][] = [];
    for (let r = 1; r < rings; r++) {
      const lat = (r / rings) * Math.PI - Math.PI / 2;
      const around = Math.max(6, Math.round(Math.cos(lat) * rings * 2.2));
      for (let k = 0; k < around; k++) points.push([lat, (k / around) * Math.PI * 2]);
    }
    const radius = size * 0.42;
    const draw = (turn: number) => {
      ctx.clearRect(0, 0, size, size);
      ctx.fillStyle = colour;
      for (const [lat, lon] of points) {
        const x = Math.cos(lat) * Math.sin(lon + turn);
        const y = Math.sin(lat);
        const z = Math.cos(lat) * Math.cos(lon + turn);
        ctx.globalAlpha = z > 0 ? 0.35 + 0.55 * z : 0.08;
        ctx.beginPath();
        ctx.arc(size / 2 + x * radius, size / 2 - y * radius, z > 0 ? 2.1 : 1.3, 0, Math.PI * 2);
        ctx.fill();
      }
    };
    draw(0.6);
    if (reducedMotion()) return;
    let frame = 0;
    const start = performance.now();
    const loop = (now: number) => {
      if (!document.hidden) draw(0.6 + (now - start) * speed * 2);
      frame = requestAnimationFrame(loop);
    };
    frame = requestAnimationFrame(loop);
    return () => cancelAnimationFrame(frame);
  }, [size, rings, speed]);
  return <canvas ref={ref} className={`globe-lite ${className}`} aria-hidden="true" style={{ width: size, height: size }} />;
}

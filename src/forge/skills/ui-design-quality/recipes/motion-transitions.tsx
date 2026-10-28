// View transitions for React: a state change or a page change that cross-fades, and elements that morph from one place to another (a card into its detail
// page, a thumbnail into a full picture). Built on the browser's View Transitions API (current Edge and Chrome); where it is missing, or when the user asks for
// reduced motion, the change simply happens at once, so nothing breaks. Import `motion-transitions.css` once for the timing.
import { flushSync } from "react-dom";
import type { CSSProperties, ReactNode } from "react";

type DocumentWithTransitions = Document & { startViewTransition?: (update: () => void) => unknown };

function motionAllowed(): boolean {
  return typeof window !== "undefined" && !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Runs `update` (a state change that redraws the page) inside a view transition when the browser supports it and motion is allowed, else runs it at once. */
export function runTransition(update: () => void): void {
  const doc = document as DocumentWithTransitions;
  if (!doc.startViewTransition || !motionAllowed()) {
    update();
    return;
  }
  // flushSync makes React draw the new state inside the callback, which is what the browser photographs as "after".
  doc.startViewTransition(() => {
    flushSync(update);
  });
}

/** The same as `runTransition`, as a hook, so a component can write `const go = useViewTransition(); go(() => setOpen(true));`. */
export function useViewTransition(): typeof runTransition {
  return runTransition;
}

/**
 * Marks an element that should morph between two states. Give the element in the "before" view and the element in the "after" view the same `name`;
 * a name must be used by only one element on the page at a time (use an id: `card-${id}`). Wrap the change in `runTransition`.
 */
export function SharedElement({ name, children, className }: { name: string; children: ReactNode; className?: string }) {
  const style = { viewTransitionName: name } as unknown as CSSProperties; // not in every version of the React typings yet
  return (
    <div className={className} style={style} data-shared={name}>
      {children}
    </div>
  );
}

/** Page change helper for client-side routing: `goTo(() => navigate("/pricing"))` cross-fades the old page into the new one. */
export function goTo(navigate: () => void): void {
  runTransition(navigate);
}

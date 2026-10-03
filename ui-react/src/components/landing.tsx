// Building blocks of the landing screens (login, hub, project list, new project): full-bleed light and dark
// tiles with a large, tightly tracked headline, as in docs/DESIGN.md. The working screens (chat, run map) keep
// the denser sizes.
import { Anvil } from "lucide-react";
import type { ReactNode } from "react";
import { cx } from "../lib";

export function Headline({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <h1 className={cx("text-balance text-[34px] font-semibold leading-[1.1] tracking-[-0.3px] sm:text-[48px] sm:tracking-[-0.28px]", className)}>
      {children}
    </h1>
  );
}

export function Tagline({ children, className }: { children: ReactNode; className?: string }) {
  return <p className={cx("text-[17px] leading-[1.47] tracking-[-0.37px] text-fg-muted", className)}>{children}</p>;
}

/** A full-width band. `dark` is the near-black tile; the colour change is the divider, so no borders. */
export function Tile({ dark, children, className }: { dark?: boolean; children: ReactNode; className?: string }) {
  return (
    <section className={cx(dark ? "bg-tile text-tile-fg [&_p]:text-tile-fg/70" : "bg-surface text-fg", className)}>{children}</section>
  );
}

export function Brand({ className }: { className?: string }) {
  return (
    <div className={cx("flex items-center gap-2", className)}>
      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-action text-accent-fg">
        <Anvil className="h-[18px] w-[18px]" aria-hidden />
      </span>
      <span className="font-mono text-[15px] font-semibold tracking-tight">Forge</span>
    </div>
  );
}

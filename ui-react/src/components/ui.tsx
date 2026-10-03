// Small, consistent building blocks: every clickable thing has a visible focus ring, a pointer cursor,
// a 150–200 ms colour transition and a disabled state; icons are SVG (lucide), never emoji.
import { Check, Copy, Loader2 } from "lucide-react";
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
import { cx, useCopy } from "../lib";

type Variant = "primary" | "secondary" | "ghost" | "danger";

export function Button({
  variant = "secondary",
  size = "md",
  icon,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: Variant; size?: "sm" | "md"; icon?: ReactNode }) {
  const styles: Record<Variant, string> = {
    primary: "bg-action text-accent-fg hover:brightness-110 active:scale-95 border border-transparent",
    secondary: "bg-raised text-fg border border-border hover:border-border-strong hover:bg-muted",
    ghost: "bg-transparent text-fg-muted border border-transparent hover:bg-raised hover:text-fg",
    danger: "bg-transparent text-danger border border-danger/40 hover:bg-danger-soft",
  };
  return (
    <button
      type="button"
      {...props}
      className={cx(
        "inline-flex items-center justify-center gap-1.5 rounded-full font-medium cursor-pointer select-none",
        "transition-colors duration-150 disabled:opacity-50 disabled:cursor-not-allowed",
        size === "sm" ? "h-7 px-3 text-[12.5px]" : "h-9 px-4 text-[13.5px]",
        styles[variant],
        className,
      )}
    >
      {icon}
      {children}
    </button>
  );
}

export function IconButton({ label, children, className, ...props }: ButtonHTMLAttributes<HTMLButtonElement> & { label: string }) {
  return (
    <button
      type="button"
      aria-label={label}
      title={label}
      {...props}
      className={cx(
        "inline-flex h-8 w-8 items-center justify-center rounded-md text-fg-muted cursor-pointer",
        "transition-colors duration-150 hover:bg-raised hover:text-fg disabled:opacity-50",
        className,
      )}
    >
      {children}
    </button>
  );
}

type Tone = "neutral" | "accent" | "ok" | "danger" | "warn" | "info";

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  const tones: Record<Tone, string> = {
    neutral: "bg-raised text-fg-muted border-border",
    accent: "bg-accent-soft text-accent border-transparent",
    ok: "bg-ok-soft text-ok border-transparent",
    danger: "bg-danger-soft text-danger border-transparent",
    warn: "bg-warn-soft text-warn border-transparent",
    info: "bg-info-soft text-info border-transparent",
  };
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11.5px] font-medium whitespace-nowrap", tones[tone], className)}>
      {children}
    </span>
  );
}

export function Card({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cx("rounded-[18px] border border-border bg-surface", className)}>{children}</div>;
}

export function Field({ label, hint, error, children }: { label: string; hint?: ReactNode; error?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[13px] font-medium text-fg">{label}</span>
      {children}
      {hint && !error && <span className="mt-1 block text-[12px] text-fg-muted">{hint}</span>}
      {error && (
        <span role="alert" className="mt-1 block text-[12px] text-danger">
          {error}
        </span>
      )}
    </label>
  );
}

const inputClass =
  "w-full rounded-lg border border-border bg-surface px-3 text-[13.5px] text-fg placeholder:text-fg-muted/70 " +
  "transition-colors duration-150 hover:border-border-strong focus:border-accent focus:outline-none " +
  "focus-visible:outline-2 focus-visible:outline-accent/60";

export function Input(props: InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={cx(inputClass, "h-9", props.className)} />;
}

export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={cx(inputClass, "h-9 cursor-pointer pr-8", props.className)} />;
}

export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea {...props} className={cx(inputClass, "py-2 leading-relaxed resize-y", props.className)} />;
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 aria-hidden className={cx("h-4 w-4 animate-spin", className)} />;
}

export function Empty({ icon, title, children }: { icon?: ReactNode; title: string; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-2 px-6 py-10 text-center">
      {icon && <div className="text-fg-muted/70">{icon}</div>}
      <div className="font-medium text-fg">{title}</div>
      {children && <div className="max-w-sm text-[13px] text-fg-muted">{children}</div>}
    </div>
  );
}

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, copy] = useCopy();
  return (
    <IconButton label={copied ? "Copied" : label} onClick={() => copy(text)} className="h-7 w-7">
      {copied ? <Check className="h-3.5 w-3.5 text-accent" /> : <Copy className="h-3.5 w-3.5" />}
    </IconButton>
  );
}

export function KeyValues({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-[13px]">
      {rows.map(([key, value]) => (
        <div key={key} className="contents">
          <dt className="text-fg-muted">{key}</dt>
          <dd className="font-mono text-[12.5px] text-fg text-right tabular-nums">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function SectionTitle({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-2 mt-5 flex items-center justify-between first:mt-0">
      <h3 className="text-[12px] font-semibold uppercase tracking-wide text-fg-muted">{children}</h3>
      {action}
    </div>
  );
}

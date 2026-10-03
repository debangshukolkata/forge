// Tokens and cost badges, coloured green / yellow / red by the configurable limits in Forge's config
// (cost.colors: reply / task / phase). The worse of the cost colour and the token colour wins.
import { cx } from "./lib";
import type { CostLimits, UsageBucket } from "./types";

export type Level = "green" | "yellow" | "red";

export function levelOf(limits: CostLimits | undefined, usd: number, tokens: number): Level {
  if (!limits) return "green";
  const rank = (value: number, [green, yellow]: [number, number]) => (value < green ? 0 : value < yellow ? 1 : 2);
  return (["green", "yellow", "red"] as const)[Math.max(rank(usd, limits.usd), rank(tokens, limits.tokens))];
}

export function compactTokens(tokens: number): string {
  if (tokens >= 1_000_000) return `${(tokens / 1_000_000).toFixed(1)}M`;
  if (tokens >= 1000) return `${(tokens / 1000).toFixed(tokens >= 100_000 ? 0 : 1)}k`;
  return String(tokens);
}

export function usd(value: number, digits = 4): string {
  return `$${value.toFixed(digits)}`;
}

const DOT: Record<Level, string> = { green: "bg-ok", yellow: "bg-warn", red: "bg-danger" };
const TEXT: Record<Level, string> = { green: "text-fg-muted", yellow: "text-warn", red: "text-danger" };

/** "● 184k tok · $0.2110" with the level's colour; tooltip with the split. */
export function UsageBadge({
  bucket,
  limits,
  className,
  compact,
}: {
  bucket: Pick<UsageBucket, "input_tokens" | "output_tokens" | "cost_usd"> & { calls?: number };
  limits?: CostLimits;
  className?: string;
  compact?: boolean;
}) {
  const tokens = bucket.input_tokens + bucket.output_tokens;
  const level = levelOf(limits, bucket.cost_usd, tokens);
  const title =
    `${bucket.input_tokens.toLocaleString()} tokens in · ${bucket.output_tokens.toLocaleString()} out` +
    `${bucket.calls !== undefined ? ` · ${bucket.calls} model call${bucket.calls === 1 ? "" : "s"}` : ""} · ${usd(bucket.cost_usd)} (estimate)`;
  return (
    <span className={cx("inline-flex items-center gap-1.5 whitespace-nowrap font-mono text-[11.5px] tabular-nums", TEXT[level], className)} title={title}>
      <span className={cx("h-1.5 w-1.5 shrink-0 rounded-full", DOT[level])} aria-label={`${level} usage`} />
      {compact ? usd(bucket.cost_usd, 2) : `${compactTokens(tokens)} tok · ${usd(bucket.cost_usd)}`}
    </span>
  );
}

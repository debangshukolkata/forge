// The Dependencies tab (D-238): the libraries the open project uses, and, when the user asks, the known
// vulnerabilities in them with the source that reported each one. Listing reads files only; the check sends
// library names and versions to osv.dev and PyPI, so it waits for a click and says so first.
import { ChevronDown, ChevronRight, ExternalLink, Package, ShieldAlert, ShieldCheck } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Badge, Button, Empty, Input, Spinner } from "../components/ui";
import { api, cx, timeAgo } from "../lib";
import type { DepFinding, DepsCheck, DepsResponse, Dependency } from "../types";

const SEVERITIES = ["critical", "high", "moderate", "low", "unknown"] as const;
const TONE: Record<string, "danger" | "warn" | "neutral"> = { critical: "danger", high: "danger", moderate: "warn", low: "neutral", unknown: "neutral" };
const CATEGORIES = ["strong_copyleft", "weak_copyleft", "unknown", "permissive"] as const;
const CATEGORY_LABEL: Record<string, string> = { permissive: "Permissive", weak_copyleft: "Weak copyleft", strong_copyleft: "Strong copyleft", unknown: "License unknown" };
const CATEGORY_TONE: Record<string, "danger" | "warn" | "neutral"> = { strong_copyleft: "danger", weak_copyleft: "warn", unknown: "neutral", permissive: "neutral" };
const slug = (name: string) => name.toLowerCase().replace(/[-_.]+/g, "-");
const rank = (level: string | null) => (level === null ? SEVERITIES.length : SEVERITIES.indexOf(level as (typeof SEVERITIES)[number])); // worst first, clean last
const keyOf = (name: string, ecosystem: string, version: string | null) => `${ecosystem}:${slug(name)}@${version ?? ""}`;

export function DepsTab() {
  const [data, setData] = useState<DepsResponse | null>(null);
  const [check, setCheck] = useState<DepsCheck | null>(null);
  const [asking, setAsking] = useState(false);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("");
  const [onlyVulnerable, setOnlyVulnerable] = useState(false);
  const [category, setCategory] = useState<string | null>(null);
  const [open, setOpen] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const response = await api<DepsResponse>("/api/dependencies");
      setData(response);
      setCheck(response.last_check);
    } catch (failure) {
      setError((failure as Error).message);
    }
  }, []);
  useEffect(() => {
    void load();
  }, [load]);

  async function runCheck() {
    setAsking(false);
    setRunning(true);
    setError("");
    try {
      const result = await api<DepsCheck>("/api/dependencies/check", { method: "POST" });
      setCheck(result);
      setData((current) => (current ? { ...current, dependencies: result.dependencies } : current));
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setRunning(false);
    }
  }

  const findings = useMemo(() => {
    const byLibrary = new Map<string, DepFinding[]>();
    for (const finding of check?.findings ?? []) {
      const key = keyOf(finding.package, finding.ecosystem, finding.version);
      byLibrary.set(key, [...(byLibrary.get(key) ?? []), finding]);
    }
    return byLibrary;
  }, [check]);

  if (data === null) {
    return error ? (
      <p role="alert" className="text-[13px] text-danger">
        {error}
      </p>
    ) : (
      <div className="flex justify-center py-10 text-fg-muted">
        <Spinner />
      </div>
    );
  }
  const libraries = data.dependencies;
  if (libraries.length === 0) {
    return (
      <Empty icon={<Package className="h-8 w-8" />} title="No libraries found yet">
        Forge looks for requirements.txt, pyproject.toml, package.json and their lock files in the project.
      </Empty>
    );
  }
  const worst = (dependency: Dependency) => {
    const list = findings.get(keyOf(dependency.name, dependency.ecosystem, dependency.version)) ?? [];
    return list.length === 0 ? null : SEVERITIES.find((level) => list.some((f) => f.severity === level)) ?? "unknown";
  };
  const shown = libraries
    .filter((d) => `${d.name} ${d.ecosystem}`.toLowerCase().includes(filter.toLowerCase()))
    .filter((d) => !onlyVulnerable || worst(d) !== null)
    .filter((d) => category === null || d.license_category === category)
    .sort((a, b) => rank(worst(a)) - rank(worst(b)));
  const counts = SEVERITIES.map((level) => [level, (check?.findings ?? []).filter((f) => f.severity === level).length] as const).filter(([, n]) => n > 0);
  const direct = libraries.filter((d) => d.direct).length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <div className="min-w-0 flex-1">
          <div className="font-medium">
            {libraries.length} librar{libraries.length === 1 ? "y" : "ies"}
          </div>
          <div className="text-[12px] text-fg-muted">
            {direct} direct · {libraries.length - direct} indirect
          </div>
        </div>
        <Button size="sm" variant="primary" disabled={running} icon={running ? <Spinner className="h-3.5 w-3.5" /> : <ShieldAlert className="h-3.5 w-3.5" />} onClick={() => setAsking(true)}>
          {running ? "Checking…" : check ? "Check again" : "Check for vulnerabilities"}
        </Button>
      </div>

      {asking && (
        <div role="alertdialog" aria-label="Check for vulnerabilities" className="rounded-xl border border-warn/50 bg-warn-soft p-3 text-[13px]">
          <p>
            This sends each library's <strong>name and version</strong> (nothing else) over the internet to <strong>osv.dev</strong>, to <strong>deps.dev</strong> (licenses of libraries that are not installed here) and, through pip-audit, to <strong>PyPI</strong>.
            {data.standalone && " In a standalone project these names describe the host, so only continue if that is allowed."}
          </p>
          <div className="mt-2 flex gap-2">
            <Button size="sm" variant="primary" onClick={runCheck}>
              Check now
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setAsking(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}
      {error && (
        <p role="alert" className="text-[13px] text-danger">
          {error}
        </p>
      )}

      {check && (
        <div data-testid="deps-summary" className="space-y-2 rounded-xl border border-border bg-surface p-3">
          <div className="flex flex-wrap items-center gap-1.5">
            {counts.length === 0 ? (
              <Badge tone="ok">
                <ShieldCheck className="h-3 w-3" /> No known vulnerabilities
              </Badge>
            ) : (
              counts.map(([level, n]) => (
                <Badge key={level} tone={TONE[level]}>
                  {n} {level}
                </Badge>
              ))
            )}
            <span className="ml-auto text-[11.5px] text-fg-muted">checked {timeAgo(check.checked_at)}</span>
          </div>
          <ul className="space-y-0.5 text-[12px]">
            {check.sources.map((source) => (
              <li key={source.name} data-source={source.name} className="flex gap-2">
                <span className="w-20 shrink-0 font-medium">{source.name}</span>
                <span className={cx(source.status === "ok" ? "text-ok" : "text-warn")}>
                  {source.status === "ok" ? (source.detail === "licenses" ? `${source.checked} licenses looked up, ${source.found} found` : `${source.checked} checked, ${source.found} reported`) : source.detail || source.status}
                </span>
              </li>
            ))}
          </ul>
          {check.unchecked > 0 && <p className="text-[12px] text-fg-muted">{check.unchecked} librar{check.unchecked === 1 ? "y has" : "ies have"} no known version and could not be checked.</p>}
        </div>
      )}

      <div data-testid="license-summary" className="flex flex-wrap items-center gap-1.5">
        <span className="text-[12px] text-fg-muted">Licenses:</span>
        {CATEGORIES.map((level) => {
          const n = libraries.filter((d) => d.license_category === level).length;
          return n === 0 ? null : (
            <button key={level} type="button" aria-pressed={category === level} data-category={level} onClick={() => setCategory(category === level ? null : level)} className={cx("cursor-pointer rounded-full", category === level && "ring-2 ring-accent/50")}>
              <Badge tone={CATEGORY_TONE[level]}>
                {n} {CATEGORY_LABEL[level].toLowerCase()}
              </Badge>
            </button>
          );
        })}
      </div>

      <div className="flex items-center gap-2">
        <Input aria-label="Search libraries" placeholder="Search libraries" value={filter} onChange={(e) => setFilter(e.target.value)} className="h-8 flex-1" />
        {check && (
          <label className="flex cursor-pointer items-center gap-1.5 text-[12px] text-fg-muted">
            <input type="checkbox" checked={onlyVulnerable} onChange={(e) => setOnlyVulnerable(e.target.checked)} className="accent-[var(--color-accent)]" />
            Vulnerable only
          </label>
        )}
      </div>

      <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
        {shown.length === 0 && <li className="px-3 py-4 text-center text-[13px] text-fg-muted">No library matches.</li>}
        {shown.map((dependency) => {
          const key = keyOf(dependency.name, dependency.ecosystem, dependency.version);
          const list = findings.get(key) ?? [];
          const level = worst(dependency);
          const expanded = open === key;
          return (
            <li key={`${key}|${dependency.file}`} data-library={dependency.name} data-vulnerable={level ? "" : undefined}>
              <button type="button" aria-expanded={expanded} disabled={list.length === 0} onClick={() => setOpen(expanded ? null : key)} className="flex w-full items-center gap-2 px-3 py-2 text-left enabled:cursor-pointer enabled:hover:bg-raised">
                {list.length === 0 ? <span className="w-4 shrink-0" /> : expanded ? <ChevronDown className="h-4 w-4 shrink-0 text-fg-muted" /> : <ChevronRight className="h-4 w-4 shrink-0 text-fg-muted" />}
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-[13px] font-medium">{dependency.name}</span>
                  <span className="block truncate font-mono text-[11.5px] text-fg-muted">{dependency.version ?? `version unknown${dependency.spec ? ` (${dependency.spec})` : ""}`}</span>
                  <span data-license={dependency.license_category} title={dependency.license_source ? `from ${dependency.license_source}` : undefined} className={cx("block truncate text-[11.5px]", dependency.license_category === "strong_copyleft" ? "font-medium text-danger" : dependency.license_category === "weak_copyleft" ? "font-medium text-warn" : "text-fg-muted")}>
                    {dependency.license || "license unknown"}
                  </span>
                </span>
                <Badge>{dependency.ecosystem === "npm" ? "npm" : "Python"}</Badge>
                {!dependency.direct && <Badge>indirect</Badge>}
                {dependency.dev && <Badge>dev</Badge>}
                {level && (
                  <Badge tone={TONE[level]}>
                    {list.length} {level}
                  </Badge>
                )}
              </button>
              {expanded && (
                <ul className="space-y-2 border-t border-border bg-bg px-3 py-2">
                  {list.map((finding) => (
                    <li key={finding.id} data-finding={finding.id} className="space-y-1 text-[12.5px]">
                      <div className="flex flex-wrap items-center gap-1.5">
                        <a href={finding.link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-mono text-[12px] font-semibold text-accent hover:underline">
                          {finding.id} <ExternalLink className="h-3 w-3" aria-hidden />
                        </a>
                        <Badge tone={TONE[finding.severity]}>{finding.severity}</Badge>
                      </div>
                      {finding.summary && <p>{finding.summary}</p>}
                      {finding.aliases.length > 0 && <p className="text-fg-muted">Also: {finding.aliases.join(", ")}</p>}
                      <p className="text-fg-muted">{finding.fixed_in.length > 0 ? `Fixed in: ${finding.fixed_in.join(", ")}` : "No fixed version listed."}</p>
                      <p className="flex flex-wrap items-center gap-1.5 text-fg-muted">
                        Found by:
                        {finding.found_by.map((source) => (
                          <Badge key={source} tone="info">
                            {source}
                          </Badge>
                        ))}
                      </p>
                    </li>
                  ))}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
      {!data.pip_audit_installed && (
        <p className="text-[12px] text-fg-muted">pip-audit is not installed here, so only osv.dev will answer. Install it with: pip install pip-audit</p>
      )}
    </div>
  );
}

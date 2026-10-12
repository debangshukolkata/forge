// Accessible UI building blocks with NO extra dependency (native <dialog>, <details>, ARIA tabs, live regions).
// Style them with the classes from index.css (btn-primary, card, field…). Use these before reaching for a library; when
// a library is wanted, shadcn/ui (MIT, Radix primitives) is the safe choice: `npx shadcn@latest add dialog tabs`.
import { useEffect, useId, useMemo, useRef, useState, type KeyboardEvent, type ReactNode } from "react";
import { ArrowDown, ArrowUp, Inbox, Search, X } from "lucide-react";

/* ---------- Dialog: the browser provides focus trapping, Esc to close and the backdrop ---------- */
export function Dialog({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);
  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => event.target === ref.current && onClose()} // click on the backdrop closes
      aria-labelledby="dialog-title"
      className="m-auto w-[min(32rem,92vw)] rounded-card border border-ink-200 bg-white p-0 text-ink-700 shadow-lift backdrop:bg-ink-900/50 backdrop:backdrop-blur-sm"
    >
      <div className="flex items-start justify-between gap-4 p-6 pb-2">
        <h2 id="dialog-title" className="text-xl">{title}</h2>
        <button onClick={onClose} aria-label="Close" className="rounded-full p-2 text-ink-500 transition hover:bg-ink-100 hover:text-ink-900">
          <X size={18} />
        </button>
      </div>
      <div className="p-6 pt-2">{children}</div>
    </dialog>
  );
}

/* ---------- Tabs: arrow keys move between tabs, only the active panel is in the tab order ---------- */
export function Tabs({ tabs }: { tabs: { id: string; label: string; content: ReactNode }[] }) {
  const [active, setActive] = useState(tabs[0].id);
  const base = useId();
  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((tab) => tab.id === active);
    const next = event.key === "ArrowRight" ? index + 1 : event.key === "ArrowLeft" ? index - 1 : null;
    if (next === null) return;
    const target = tabs[(next + tabs.length) % tabs.length];
    setActive(target.id);
    document.getElementById(`${base}-tab-${target.id}`)?.focus();
  }
  return (
    <div>
      <div role="tablist" onKeyDown={onKey} className="flex gap-1 border-b border-ink-200">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            id={`${base}-tab-${tab.id}`}
            role="tab"
            aria-selected={active === tab.id}
            aria-controls={`${base}-panel-${tab.id}`}
            tabIndex={active === tab.id ? 0 : -1}
            onClick={() => setActive(tab.id)}
            className={`-mb-px border-b-2 px-4 py-3 text-sm font-medium transition ${
              active === tab.id ? "border-brand-600 text-ink-900" : "border-transparent text-ink-500 hover:text-ink-900"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>
      {tabs.map((tab) => (
        <div key={tab.id} id={`${base}-panel-${tab.id}`} role="tabpanel" aria-labelledby={`${base}-tab-${tab.id}`} hidden={active !== tab.id} className="pt-6">
          {tab.content}
        </div>
      ))}
    </div>
  );
}

/* ---------- Toasts: announced to screen readers, dismiss themselves ---------- */
export type Toast = { id: number; text: string; tone?: "ok" | "error" };
export function ToastRegion({ toasts, dismiss }: { toasts: Toast[]; dismiss: (id: number) => void }) {
  useEffect(() => {
    const timers = toasts.map((toast) => window.setTimeout(() => dismiss(toast.id), 4500));
    return () => timers.forEach(window.clearTimeout);
  }, [toasts, dismiss]);
  return (
    <div role="status" aria-live="polite" className="fixed bottom-4 right-4 z-50 flex w-[min(22rem,calc(100vw-2rem))] flex-col gap-2">
      {toasts.map((toast) => (
        <div key={toast.id} className={`fade-up rounded-xl border bg-white px-4 py-3 text-sm shadow-lift ${toast.tone === "error" ? "border-brand-200 text-brand-700" : "border-ink-200 text-ink-900"}`}>
          {toast.text}
        </div>
      ))}
    </div>
  );
}

/* ---------- Empty state and loading skeleton ---------- */
export function EmptyState({ title, text, action }: { title: string; text: string; action?: ReactNode }) {
  return (
    <div className="grid place-items-center rounded-card border border-dashed border-ink-300 px-6 py-14 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-full bg-ink-100 text-ink-500"><Inbox size={22} /></span>
      <h3 className="mt-4 text-lg">{title}</h3>
      <p className="mt-1 max-w-sm text-sm text-ink-500">{text}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function SkeletonRows({ rows = 4 }: { rows?: number }) {
  return (
    <div aria-busy="true" aria-label="Loading" className="space-y-3">
      {Array.from({ length: rows }, (_, index) => (
        <div key={index} className="skeleton h-12 w-full" style={{ opacity: 1 - index * 0.15 }} />
      ))}
    </div>
  );
}

/* ---------- Data table: search, sortable headers (aria-sort), row hover, empty result state ---------- */
export function DataTable<T extends Record<string, string | number>>({ rows, columns }: { rows: T[]; columns: { key: keyof T & string; label: string; numeric?: boolean }[] }) {
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: 1 | -1 } | null>(null);
  const shown = useMemo(() => {
    const filtered = rows.filter((row) => Object.values(row).some((value) => String(value).toLowerCase().includes(query.toLowerCase())));
    if (!sort) return filtered;
    return [...filtered].sort((a, b) => (a[sort.key] > b[sort.key] ? 1 : a[sort.key] < b[sort.key] ? -1 : 0) * sort.dir);
  }, [rows, query, sort]);
  return (
    <div className="space-y-4">
      <label className="relative block max-w-xs">
        <span className="sr-only">Search</span>
        <Search size={16} className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-ink-500" />
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search…" className="field !py-2 pl-9" />
      </label>
      <div className="overflow-x-auto rounded-card border border-ink-200 bg-white">
        <table className="w-full text-left text-sm">
          <thead className="sticky top-0 bg-ink-50 text-xs uppercase tracking-wide text-ink-500">
            <tr>
              {columns.map((column) => (
                <th key={column.key} scope="col" aria-sort={sort?.key === column.key ? (sort.dir === 1 ? "ascending" : "descending") : "none"} className={`px-4 py-3 ${column.numeric ? "text-right" : ""}`}>
                  <button onClick={() => setSort((current) => ({ key: column.key, dir: current?.key === column.key && current.dir === 1 ? -1 : 1 }))} className="inline-flex items-center gap-1 font-semibold hover:text-ink-900">
                    {column.label}
                    {sort?.key === column.key && (sort.dir === 1 ? <ArrowUp size={12} /> : <ArrowDown size={12} />)}
                  </button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-ink-200">
            {shown.map((row, index) => (
              <tr key={index} className="transition hover:bg-ink-50">
                {columns.map((column) => (
                  <td key={column.key} className={`px-4 py-3 ${column.numeric ? "text-right tabular-nums" : ""}`}>{row[column.key]}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {shown.length === 0 && <p className="px-4 py-10 text-center text-sm text-ink-500">No rows match “{query}”. Try a shorter search.</p>}
      </div>
    </div>
  );
}

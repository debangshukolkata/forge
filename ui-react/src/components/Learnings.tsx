// "What Forge has learned" (D-227): the notes and FORGE.md files Forge keeps, grouped by project, with tick
// boxes so the user picks exactly what to forget. Notes belong to a repository or host, so a group can serve
// several projects; the group title lists them.
import { ArrowLeft, ChevronDown, ChevronRight } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../lib";
import { Headline, Tagline } from "./landing";
import { Badge, Button, Empty, Spinner } from "./ui";

interface Item {
  id: string;
  title: string;
  kind: string;
  description: string;
  text: string;
}
interface Group {
  id: string;
  title: string;
  projects: string[];
  items: Item[];
}

export function Learnings({ onBack }: { onBack: () => void }) {
  const [groups, setGroups] = useState<Group[] | null>(null);
  const [picked, setPicked] = useState<Record<string, Set<string>>>({});
  const [open, setOpen] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const load = () =>
    api<Group[]>("/api/learnings")
      .then(setGroups)
      .catch((failure: Error) => {
        setError(failure.message);
        setGroups([]);
      });
  useEffect(() => {
    void load();
  }, []);

  const count = Object.values(picked).reduce((total, set) => total + set.size, 0);
  const toggle = (group: string, item: string) =>
    setPicked((current) => {
      const set = new Set(current[group] ?? []);
      if (!set.delete(item)) set.add(item);
      return { ...current, [group]: set };
    });
  const toggleGroup = (group: Group) =>
    setPicked((current) => {
      const all = (current[group.id]?.size ?? 0) === group.items.length;
      return { ...current, [group.id]: new Set(all ? [] : group.items.map((item) => item.id)) };
    });

  async function forget() {
    setBusy(true);
    setError("");
    const selections = Object.fromEntries(Object.entries(picked).map(([group, set]) => [group, [...set]]));
    try {
      await api("/api/learnings/delete", { method: "POST", body: { selections } });
      setPicked({});
      setConfirming(false);
      await load();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl px-6 py-10 pb-28">
      <Button variant="ghost" size="sm" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={onBack} className="-ml-3 mb-4">
        Back
      </Button>
      <Headline className="!text-[34px]">What Forge has learned.</Headline>
      <Tagline className="mt-2">Notes and instructions Forge keeps for your projects. Tick what to forget; nothing else changes.</Tagline>
      {error && (
        <p role="alert" className="mt-4 text-[13px] text-danger">
          {error}
        </p>
      )}
      {groups === null ? (
        <div className="mt-10 flex justify-center text-fg-muted">
          <Spinner />
        </div>
      ) : groups.length === 0 ? (
        <Empty title="Nothing learned yet">Notes Forge saves while it works will show up here.</Empty>
      ) : (
        <div className="mt-6 space-y-5">
          {groups.map((group) => {
            const ticked = picked[group.id]?.size ?? 0;
            return (
              <section key={group.id} aria-label={group.title} className="rounded-[18px] border border-border bg-surface p-5">
                <div className="flex items-center gap-3">
                  <input
                    type="checkbox"
                    aria-label={`Select all in ${group.title}`}
                    checked={ticked === group.items.length}
                    onChange={() => toggleGroup(group)}
                    className="h-4 w-4 cursor-pointer accent-[var(--color-accent)]"
                  />
                  <h2 className="min-w-0 flex-1 truncate text-[16px] font-semibold">{group.title}</h2>
                  <Badge>
                    {group.items.length} item{group.items.length === 1 ? "" : "s"}
                  </Badge>
                </div>
                <ul className="mt-3 divide-y divide-border">
                  {group.items.map((item) => {
                    const key = `${group.id}/${item.id}`;
                    return (
                      <li key={item.id} className="py-2.5">
                        <div className="flex items-start gap-3">
                          <input
                            type="checkbox"
                            aria-label={`Forget ${item.title}`}
                            checked={picked[group.id]?.has(item.id) ?? false}
                            onChange={() => toggle(group.id, item.id)}
                            className="mt-1 h-4 w-4 cursor-pointer accent-[var(--color-accent)]"
                          />
                          <button type="button" onClick={() => setOpen(open === key ? null : key)} className="flex min-w-0 flex-1 cursor-pointer items-start gap-1.5 text-left">
                            {open === key ? <ChevronDown className="mt-0.5 h-4 w-4 shrink-0 text-fg-muted" /> : <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-fg-muted" />}
                            <span className="min-w-0">
                              <span className="flex items-center gap-2">
                                <span className="truncate text-[14.5px] font-medium">{item.title}</span>
                                <Badge>{item.kind}</Badge>
                              </span>
                              <span className="block text-[13px] text-fg-muted">{item.description}</span>
                            </span>
                          </button>
                        </div>
                        {open === key && <pre className="ml-11 mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg bg-raised p-3 text-[12.5px]">{item.text}</pre>}
                      </li>
                    );
                  })}
                </ul>
              </section>
            );
          })}
        </div>
      )}
      {count > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-surface/95 px-6 py-3 backdrop-blur">
          <div className="mx-auto flex max-w-3xl items-center gap-3">
            {confirming ? (
              <>
                <span className="flex-1 text-[13.5px]">
                  Forget {count} item{count === 1 ? "" : "s"} for good?
                </span>
                <Button variant="danger" size="sm" disabled={busy} onClick={forget}>
                  {busy ? "Deleting…" : "Yes, forget"}
                </Button>
                <Button variant="ghost" size="sm" disabled={busy} onClick={() => setConfirming(false)}>
                  Cancel
                </Button>
              </>
            ) : (
              <>
                <span className="flex-1 text-[13.5px]">{count} selected</span>
                <Button variant="ghost" size="sm" onClick={() => setPicked({})}>
                  Clear
                </Button>
                <Button variant="danger" size="sm" onClick={() => setConfirming(true)}>
                  Forget selected
                </Button>
              </>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// The connection indicators of the top bar (D-627): one dot per environment DebCraft signs in to (dev, SIT) and per
// tunnel. Green: a valid token, or the tunnel's port answers. Red: the last try failed, with the reason in the panel.
// Grey: nothing yet (DebCraft signs in at the first call; the tunnel opens when the Development DB is needed).
// The state is asked from the server, which looks at the token store and the port: a token ends with time, so it is
// never taken from the events. Reading it opens no window; a sign-in starts only from the button here or from a call.
import { useEffect, useRef, useState } from "react";
import { api, cx } from "../lib";
import { Button, Spinner } from "./ui";

interface Item {
  kind: "login" | "tunnel";
  name: string;
  state: "ok" | "failed" | "none";
  detail: string;
}

const POLL_MS = 30_000;
const TONE: Record<Item["state"], string> = { ok: "bg-ok", failed: "bg-danger", none: "bg-border-strong" };
const WORD: Record<Item["state"], string> = { ok: "ready", failed: "failed", none: "not active" };

function label(item: Item): string {
  return item.kind === "tunnel" && item.name !== "tunnels.yaml" ? `tunnel ${item.name}` : item.name;
}

export function Connections({ busy }: { busy: boolean }) {
  const [items, setItems] = useState<Item[]>([]);
  const [open, setOpen] = useState(false);
  const [working, setWorking] = useState<string | null>(null);
  const [message, setMessage] = useState("");
  const box = useRef<HTMLDivElement>(null);

  async function load(check = false) {
    try {
      const data = await api<{ items: Item[] }>(`/api/connections${check ? "?check=true" : ""}`);
      setItems(data.items);
    } catch {
      // the bar keeps what it showed: a failed poll says nothing about the connections
    }
  }

  // At the start, every half minute, and whenever DebCraft stops working (a call may have signed in or opened the tunnel).
  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), POLL_MS);
    return () => window.clearInterval(timer);
  }, []);
  useEffect(() => {
    if (!busy) void load();
  }, [busy]);

  useEffect(() => {
    if (!open) return;
    void load(true); // the panel asks the server of each environment whether it still takes the token
    const away = (event: MouseEvent) => {
      if (!box.current?.contains(event.target as Node)) setOpen(false);
    };
    const escape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", away);
    document.addEventListener("keydown", escape);
    return () => {
      document.removeEventListener("mousedown", away);
      document.removeEventListener("keydown", escape);
    };
  }, [open]);

  async function act(item: Item) {
    setWorking(`${item.kind}:${item.name}`);
    setMessage("");
    try {
      const path = item.kind === "login" ? "/api/connections/sign-in" : "/api/connections/tunnel";
      const result = await api<{ ok: boolean; message: string; items: Item[] }>(path, { method: "POST", body: { name: item.name } });
      setItems(result.items);
      if (!result.ok) setMessage(result.message || "It did not work.");
    } catch (failure) {
      setMessage((failure as Error).message);
    } finally {
      setWorking(null);
    }
  }

  if (items.length === 0) return null;
  return (
    <div ref={box} className="relative shrink-0">
      <button
        type="button"
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label="Connections"
        title="Sign-ins and tunnels"
        data-testid="connections"
        onClick={() => setOpen(!open)}
        className="flex cursor-pointer items-center gap-2.5 rounded-md px-1.5 py-1 text-[12.5px] text-fg-muted transition-colors duration-150 hover:bg-raised hover:text-fg focus-visible:outline-2 focus-visible:outline-accent"
      >
        {items.map((item) => (
          <span key={`${item.kind}:${item.name}`} className="flex items-center gap-1.5" data-state={item.state}>
            <span className={cx("h-2 w-2 shrink-0 rounded-full", TONE[item.state], working === `${item.kind}:${item.name}` && "animate-pulse")} role="img" aria-label={`${label(item)}: ${WORD[item.state]}`} />
            <span className="hidden lg:inline">{label(item)}</span>
          </span>
        ))}
      </button>
      {open && (
        <div role="dialog" aria-label="Connections" className="absolute right-0 top-full z-40 mt-1.5 w-[26rem] max-w-[90vw] rounded-lg border border-border bg-surface p-1.5 shadow-lg">
          <ul>
            {items.map((item) => {
              const key = `${item.kind}:${item.name}`;
              const file = item.name.endsWith(".yaml");
              return (
                <li key={key} className="flex items-center gap-2.5 rounded-md px-2.5 py-2">
                  <span className={cx("h-2 w-2 shrink-0 rounded-full", TONE[item.state])} aria-hidden />
                  <span className="w-24 shrink-0 truncate text-[13px] font-medium">{label(item)}</span>
                  <span className={cx("min-w-0 flex-1 text-[12.5px]", item.state === "failed" ? "text-danger" : "text-fg-muted")}>{item.detail}</span>
                  {!file && (item.kind === "login" || item.state !== "ok") && (
                    <Button variant="ghost" size="sm" disabled={working !== null} onClick={() => void act(item)}>
                      {working === key ? <Spinner className="h-3 w-3" /> : item.kind === "tunnel" ? "Open" : item.state === "ok" ? "Sign in again" : "Sign in"}
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
          {message && (
            <p role="alert" className="px-2.5 py-1.5 text-[12px] text-danger">
              {message}
            </p>
          )}
          <p className="px-2.5 pb-1 pt-1.5 text-[11.5px] text-fg-muted">
            Grey means nothing is needed yet: DebCraft signs in at the first call and opens the tunnel when the Development DB is used. A sign-in may open a browser
            window.
          </p>
        </div>
      )}
    </div>
  );
}

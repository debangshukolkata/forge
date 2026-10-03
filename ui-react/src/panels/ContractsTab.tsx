// The Contracts panel (D-129, Mode B only): signatures the user pins for a seam (the LLM call wrapper, a file
// helper, ...) so generated code drops into the host repository with minimal changes. The same store the chat's
// `/contracts` and the `contract_pin` tool use; pinning a seam again revises it (the user may change their mind
// after seeing generated code).
import { FileSignature, Pencil, Trash2, X } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Badge, Button, Empty, Field, Input, Spinner, Textarea } from "../components/ui";
import { Code, api, timeAgo } from "../lib";
import type { Contract } from "../types";
import type { Forge } from "../useForge";

interface Listing {
  available: boolean;
  contracts: Contract[];
}

const EMPTY = { seam: "", signature: "", note: "" };

export function ContractsTab({ forge }: { forge: Forge }) {
  const [listing, setListing] = useState<Listing | null>(null);
  const [error, setError] = useState("");
  const [form, setForm] = useState(EMPTY);
  const [revising, setRevising] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [confirmForget, setConfirmForget] = useState<string | null>(null);

  // The chat can pin a contract too (a message, or `/contracts pin`): reload when such a call finishes.
  const pinnedInChat = forge.timeline.items.filter((i) => i.kind === "tool" && i.name === "contract_pin" && i.state !== "running").length;
  const load = useCallback(() => {
    api<Listing>("/api/contracts")
      .then((data) => {
        setListing(data);
        setError("");
      })
      .catch((failure: Error) => setError(failure.message));
  }, []);
  useEffect(load, [load, pinnedInChat]);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setListing(await api<Listing>("/api/contracts", { method: "POST", body: form }));
      setForm(EMPTY);
      setRevising(null);
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  };

  const forget = async (contract: Contract) => {
    setError("");
    try {
      setListing(await api<Listing>(`/api/contracts/${encodeURIComponent(contract.seam)}`, { method: "DELETE" }));
      setConfirmForget(null);
      if (revising === contract.seam) {
        setForm(EMPTY);
        setRevising(null);
      }
    } catch (failure) {
      setError((failure as Error).message);
    }
  };

  if (listing === null) {
    return error ? (
      <div role="alert" className="text-[13px] text-danger">
        {error}
      </div>
    ) : (
      <div className="flex items-center gap-2 text-[13px] text-fg-muted">
        <Spinner /> Loading…
      </div>
    );
  }
  if (!listing.available) {
    return <Empty icon={<FileSignature className="h-8 w-8" />} title="Standalone projects only">Contracts are for a Standalone project, where Forge never sees your code.</Empty>;
  }

  return (
    <div className="space-y-4">
      <p className="text-[13px] text-fg-muted">
        Pin the exact signature for a seam and Forge builds new code to match it, so the result is easy to retrofit by hand. Pin the
        same seam again to change it.
      </p>

      <form onSubmit={submit} className="space-y-3 rounded-[18px] border border-border p-4" noValidate>
        <div className="flex items-center justify-between">
          <h3 className="text-[14px] font-semibold">{revising ? `Revise ${revising}` : "Pin a contract"}</h3>
          {revising && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              icon={<X className="h-3.5 w-3.5" />}
              onClick={() => {
                setForm(EMPTY);
                setRevising(null);
              }}
            >
              Cancel
            </Button>
          )}
        </div>
        <Field label="Seam" hint="Short and lowercase, e.g. llm_call_wrapper or file_read_write">
          <Input
            value={form.seam}
            readOnly={revising !== null}
            onChange={(e) => setForm({ ...form, seam: e.target.value })}
            placeholder="llm_call_wrapper"
            autoComplete="off"
          />
        </Field>
        <Field label="Signature">
          <Textarea
            rows={3}
            value={form.signature}
            onChange={(e) => setForm({ ...form, signature: e.target.value })}
            placeholder="def call_llm(prompt: str, **kwargs) -> LLMResponse"
            className="font-mono text-[12.5px]"
          />
        </Field>
        <Field label="Note (optional)" hint="Why, or how it is used">
          <Input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} autoComplete="off" />
        </Field>
        {error && (
          <p role="alert" className="text-[12.5px] text-danger">
            {error}
          </p>
        )}
        <Button type="submit" variant="primary" disabled={busy || !form.seam.trim() || !form.signature.trim()}>
          {busy && <Spinner />}
          {revising ? "Save revision" : "Pin contract"}
        </Button>
      </form>

      {listing.contracts.length === 0 ? (
        <Empty icon={<FileSignature className="h-8 w-8" />} title="Nothing pinned yet">
          Until you pin one, Forge designs the seams itself.
        </Empty>
      ) : (
        <ul className="space-y-3" aria-label="Pinned contracts">
          {listing.contracts.map((contract) => (
            <li key={contract.id} data-contract={contract.seam} className="rounded-[18px] border border-border p-4">
              <div className="flex items-center gap-2">
                <span className="min-w-0 flex-1 truncate font-mono text-[13px] font-semibold">{contract.seam}</span>
                <Badge tone={contract.source === "corrected" ? "info" : "neutral"}>
                  {contract.source === "corrected" ? "From your corrections" : "Pinned by you"}
                </Badge>
              </div>
              <Code text={contract.signature} language="python" className="mt-2 max-h-40 text-[12px]" />
              {contract.note && <p className="mt-2 text-[12.5px] text-fg-muted">{contract.note}</p>}
              <div className="mt-2 flex items-center gap-2 text-[11.5px] text-fg-muted">
                <span>
                  {contract.id} · pinned {timeAgo(contract.pinned)}
                  {contract.revised && ` · revised ${timeAgo(contract.revised)}`}
                </span>
                <span className="flex-1" />
                {confirmForget === contract.seam ? (
                  <>
                    <span>Forget it?</span>
                    <Button size="sm" variant="danger" onClick={() => void forget(contract)}>
                      Forget
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setConfirmForget(null)}>
                      Keep
                    </Button>
                  </>
                ) : (
                  <>
                    <Button
                      size="sm"
                      variant="ghost"
                      icon={<Pencil className="h-3.5 w-3.5" />}
                      onClick={() => {
                        setForm({ seam: contract.seam, signature: contract.signature, note: contract.note });
                        setRevising(contract.seam);
                      }}
                    >
                      Revise
                    </Button>
                    <Button size="sm" variant="ghost" icon={<Trash2 className="h-3.5 w-3.5" />} onClick={() => setConfirmForget(contract.seam)}>
                      Forget
                    </Button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

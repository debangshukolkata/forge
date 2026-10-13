import { ChevronLeft, ChevronRight, Presentation, X } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import { api, cx } from "../lib";
import type { SlideSet } from "../types";
import { Button, Spinner } from "./ui";

const imageUrl = (path: string) => `/api/image?path=${encodeURIComponent(path)}`;

/** The slides DebCraft just made: a row of thumbnails in the chat; click one to open the viewer (P1.2). */
export function SlideStrip({ set }: { set: SlideSet }) {
  const [open, setOpen] = useState<number | null>(null);
  if (!set.pictures.length) return null;
  return (
    <div data-testid="slide-strip" className="space-y-1.5">
      <div className="flex items-center gap-1.5 text-[12px] text-fg-muted">
        <Presentation className="h-3.5 w-3.5" aria-hidden />
        <span>{set.deck}: {set.pictures.length} slides</span>
      </div>
      <div className="flex gap-2 overflow-x-auto pb-1">
        {set.pictures.map((picture, index) => (
          <button
            key={picture}
            type="button"
            data-testid="slide-thumb"
            onClick={() => setOpen(index)}
            title={`Slide ${index + 1}`}
            className="relative w-40 shrink-0 cursor-pointer overflow-hidden rounded-lg border border-border bg-surface shadow-sm transition hover:shadow-md focus-visible:outline focus-visible:outline-2 focus-visible:outline-accent"
          >
            <img src={imageUrl(picture)} alt={`Slide ${index + 1}`} loading="lazy" className="aspect-video w-full object-cover" />
            <span className="absolute left-1 top-1 rounded bg-black/60 px-1.5 text-[11px] text-white">{index + 1}</span>
          </button>
        ))}
      </div>
      {open !== null && (
        <div role="dialog" aria-label={`Slides of ${set.deck}`} data-testid="slide-modal" className="fixed inset-0 z-50 grid place-items-center bg-black/70 p-4" onClick={() => setOpen(null)}>
          <div className="max-h-full w-full max-w-5xl overflow-auto rounded-xl bg-bg p-3 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-2 flex items-center justify-between">
              <span className="truncate font-mono text-[12px] text-fg-muted">{set.deck}</span>
              <button type="button" aria-label="Close" onClick={() => setOpen(null)} className="cursor-pointer rounded p-1 text-fg-muted hover:bg-raised">
                <X className="h-4 w-4" />
              </button>
            </div>
            <SlideViewer set={set} start={open} onClose={() => setOpen(null)} />
          </div>
        </div>
      )}
    </div>
  );
}

/** Big slide, thumbnails on the left, speaker notes underneath; arrow keys move, Esc closes when a close handler is given. */
export function SlideViewer({ set, start = 0, onClose }: { set: SlideSet; start?: number; onClose?: () => void }) {
  const [index, setIndex] = useState(Math.min(start, Math.max(set.pictures.length - 1, 0)));
  const last = set.pictures.length - 1;
  const move = useCallback((step: number) => setIndex((i) => Math.min(Math.max(i + step, 0), last)), [last]);
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "ArrowRight" || event.key === "ArrowDown") move(1);
      else if (event.key === "ArrowLeft" || event.key === "ArrowUp") move(-1);
      else if (event.key === "Escape" && onClose) onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [move, onClose]);
  if (!set.pictures.length) return null;
  const notes = set.notes[index]?.trim();
  return (
    <div data-testid="slide-viewer" className="flex gap-3">
      <div className="hidden max-h-[60vh] w-28 shrink-0 space-y-1.5 overflow-y-auto pr-1 sm:block">
        {set.pictures.map((picture, i) => (
          <button
            key={picture}
            type="button"
            onClick={() => setIndex(i)}
            aria-label={`Go to slide ${i + 1}`}
            aria-current={i === index}
            className={cx("relative block w-full cursor-pointer overflow-hidden rounded border", i === index ? "border-accent ring-1 ring-accent" : "border-border opacity-80 hover:opacity-100")}
          >
            <img src={imageUrl(picture)} alt="" loading="lazy" className="aspect-video w-full object-cover" />
            <span className="absolute left-0.5 top-0.5 rounded bg-black/60 px-1 text-[10px] text-white">{i + 1}</span>
          </button>
        ))}
      </div>
      <div className="min-w-0 flex-1 space-y-2">
        <img data-testid="slide-large" src={imageUrl(set.pictures[index])} alt={`Slide ${index + 1} of ${set.pictures.length}`} className="w-full rounded-lg border border-border bg-white shadow" />
        <div className="flex items-center justify-between text-[12px] text-fg-muted">
          <Button size="sm" variant="ghost" icon={<ChevronLeft className="h-3.5 w-3.5" />} onClick={() => move(-1)} disabled={index === 0}>Previous</Button>
          <span>Slide {index + 1} of {set.pictures.length}</span>
          <Button size="sm" variant="ghost" onClick={() => move(1)} disabled={index === last}>
            Next <ChevronRight className="ml-1 h-3.5 w-3.5" />
          </Button>
        </div>
        <div data-testid="slide-notes" className="rounded-lg bg-raised px-3 py-2 text-[12.5px] text-fg-muted">
          <span className="font-medium text-fg">Speaker notes: </span>
          {notes ? <span className="whitespace-pre-wrap">{notes}</span> : <span>none for this slide</span>}
        </div>
      </div>
    </div>
  );
}

interface DeckInfo extends SlideSet { stale: boolean; can_render: boolean }

/** A .pptx opened in the Files tab: the pictures PowerPoint made of it, or a button to make them. */
export function DeckPanel({ root, path }: { root: string; path: string }) {
  const [info, setInfo] = useState<DeckInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const query = `root=${root}&path=${encodeURIComponent(path)}`;
  useEffect(() => {
    setInfo(null);
    setError("");
    api<DeckInfo>(`/api/slides?${query}`).then(setInfo).catch((e: Error) => setError(e.message));
  }, [query]);
  const render = async () => {
    setBusy(true);
    setError("");
    try {
      setInfo(await api<DeckInfo>(`/api/slides/render?${query}`, { method: "POST" }));
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  };
  if (!info && !error) return <Spinner className="h-4 w-4" />;
  const pictures = info?.pictures ?? [];
  return (
    <div data-testid="deck-panel" className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="truncate font-mono text-[12px] text-fg-muted">{root}/{path}</span>
        {info?.can_render && (
          <Button size="sm" onClick={render} disabled={busy}>
            {busy ? "Rendering with PowerPoint..." : pictures.length ? "Render again" : "Show slides"}
          </Button>
        )}
      </div>
      {info?.stale && pictures.length > 0 && <p className="text-[12px] text-warn">The deck changed after these pictures were made: render again to see the latest.</p>}
      {error && <p className="text-[13px] text-danger">{error}</p>}
      {info && !pictures.length && (
        <p className="text-[13px] text-fg-muted">
          {info.can_render
            ? "No pictures of this deck yet. Show slides renders them with PowerPoint (a few seconds)."
            : "PowerPoint is not available here, so the slides cannot be shown. Download the file to open it."}
        </p>
      )}
      {info && pictures.length > 0 && <SlideViewer set={info} />}
    </div>
  );
}

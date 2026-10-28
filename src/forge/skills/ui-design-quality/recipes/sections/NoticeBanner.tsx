// Site notice: a slim band at the very top for something every visitor should know (opening hours over a holiday, a price change, a service interruption).
// It can be dismissed with a real button, and stays dismissed for the visit (not stored on disk). It is a status region, announced politely, never an alert:
// use it for information, not for an error. One notice at a time, one sentence, one optional link.
import { useState } from "react";

export default function NoticeBanner({
  text = "We are closed from 24 December to 2 January and open again on Saturday 3 January.",
  link = { label: "See holiday hours", href: "#hours" },
}: {
  text?: string;
  link?: { label: string; href: string };
}) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  return (
    <div role="status" className="border-b border-brand-200 bg-brand-50">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-4 py-2.5 text-sm sm:px-6">
        <p className="text-ink-900">
          {text}{" "}
          {link && <a href={link.href} className="font-semibold text-brand-700 underline underline-offset-4">{link.label}</a>}
        </p>
        <button type="button" onClick={() => setOpen(false)} className="shrink-0 rounded-lg px-3 py-2 font-semibold text-ink-700 hover:bg-brand-100" aria-label="Dismiss this notice">
          Dismiss
        </button>
      </div>
    </div>
  );
}

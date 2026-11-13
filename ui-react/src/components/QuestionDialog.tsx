// The question a model asks the user (ask_user): a pop-up with the options as a radio list and a box for the
// user's own answer. Choosing an option only selects it; the answer is sent with "Submit answer", so a stray
// click sends nothing and the user sees exactly what will be sent (D-214).
import { AlertOctagon, Check, HelpCircle, X } from "lucide-react";
import { createContext, useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Markdown, cx } from "../lib";
import type { Forge } from "../useForge";
import { Badge, Button, IconButton, Textarea } from "./ui";

type P = Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any

/** Which question is open as a pop-up (the inline card then waits quietly), and how to open it again. */
export const QuestionPopup = createContext<{ popupId: string | null; reopen: (id: string) => void }>({
  popupId: null,
  reopen: () => undefined,
});

export function QuestionForm({ itemKey, p, forge }: { itemKey: string; p: P; forge: Forge }) {
  const options: P[] = p.options || [];
  const [selected, setSelected] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const typed = note.trim();
  const ready = selected !== null || typed !== "";
  // On a red card the first option is the approving one: the button that sends it is red and says what it does.
  const approving = Boolean(p.danger) && selected !== null && selected === options[0]?.label;
  const submit = () => {
    if (!ready) return;
    const label = selected !== null ? `You chose: ${selected}${typed ? " (with a note)" : ""}` : `You answered: ${typed}`;
    forge.answer(
      itemKey,
      { kind: "answer", question_id: p.id, ...(selected !== null ? { choice: selected } : {}), text: typed || null },
      label,
    );
  };
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    const inText = event.target instanceof HTMLTextAreaElement;
    if (event.key === "Enter" && !p.danger && (event.ctrlKey || event.metaKey || !inText)) {
      event.preventDefault();
      submit();
      return;
    }
    // A red card is answered with the mouse only: no number key picks "approve" by accident.
    const option = p.danger ? undefined : options[Number(event.key) - 1];
    if (!inText && option) setSelected(option.label);
  };
  const summary =
    selected !== null
      ? `Your answer: ${selected}${typed ? ` + “${typed}”` : ""}`
      : typed
        ? `Your answer: “${typed}”`
        : "Choose an option, or type your own answer.";
  return (
    <div tabIndex={0} onKeyDown={onKey} className="space-y-3 outline-none">
      <div role="radiogroup" aria-label="Options" className="space-y-2">
        {options.map((option, index) => {
          const recommended = option.label === p.recommended;
          const checked = selected === option.label;
          return (
            <button
              key={option.label}
              type="button"
              role="radio"
              aria-checked={checked}
              data-selected={checked ? "" : undefined}
              data-recommended={recommended ? "" : undefined}
              onClick={() => setSelected(checked ? null : option.label)}
              className={cx(
                "flex w-full cursor-pointer gap-3 rounded-lg border p-3 text-left transition-colors duration-150",
                checked && p.danger && index === 0
                  ? "border-danger bg-danger-soft ring-2 ring-danger/30"
                  : checked
                  ? "border-accent bg-accent-soft ring-2 ring-accent/30"
                  : recommended
                    ? "border-accent/40 hover:border-accent"
                    : "border-border hover:border-border-strong hover:bg-raised",
              )}
            >
              <span
                className={cx(
                  "mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full border font-mono text-[11px]",
                  checked ? "border-accent bg-accent text-accent-fg" : "border-border-strong text-fg-muted",
                )}
              >
                {checked ? <Check className="h-3 w-3" aria-hidden /> : index + 1}
              </span>
              <span className="min-w-0 flex-1">
                <span className="flex flex-wrap items-center gap-2 font-medium">
                  {option.label}
                  {recommended && <Badge tone="accent">Recommended</Badge>}
                </span>
                {option.description && <span className="mt-0.5 block text-[12.5px] text-fg-muted">{option.description}</span>}
                {option.image && (
                  <img
                    src={`/api/image?path=${encodeURIComponent(option.image)}`}
                    alt={`Picture of ${option.label}`}
                    loading="lazy"
                    className="mt-2 block max-h-64 w-full rounded-md border border-border bg-surface object-contain object-left"
                  />
                )}
                {(option.pros || option.cons || option.risks) && (
                  <span className="mt-1 block space-y-0.5 text-[12px]">
                    {option.pros && <span className="block text-ok">Pros: {option.pros}</span>}
                    {option.cons && <span className="block text-warn">Cons: {option.cons}</span>}
                    {option.risks && <span className="block text-danger">Risks: {option.risks}</span>}
                  </span>
                )}
              </span>
            </button>
          );
        })}
      </div>
      <Textarea
        rows={2}
        value={note}
        onChange={(e) => setNote(e.target.value)}
        placeholder={selected !== null ? "Add a note (optional)…" : "Or type your own answer…"}
        aria-label="Your own answer or a note"
      />
      <div className="flex items-center gap-3 pt-1">
        <div data-testid="question-summary" aria-live="polite" className="min-w-0 flex-1 truncate text-[12.5px] text-fg-muted">
          {summary}
        </div>
        {approving ? (
          <Button key="approve" variant="danger" data-testid="danger-submit" className="!border-danger !bg-danger !text-white hover:brightness-110" onClick={submit}>
            Change the shared database
          </Button>
        ) : (
          <Button key="send" variant="primary" disabled={!ready} onClick={submit}>
            Submit answer
          </Button>
        )}
      </div>
    </div>
  );
}

export function QuestionDialog({ itemKey, p, forge, onDismiss }: { itemKey: string; p: P; forge: Forge; onDismiss: () => void }) {
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    box.current?.focus();
  }, []);
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === "Escape") {
      // Esc stops a run elsewhere; here it only closes the pop-up (the question stays open in the chat).
      event.stopPropagation();
      event.nativeEvent.stopPropagation();
      onDismiss();
    }
  };
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-4">
      <div
        ref={box}
        role="dialog"
        aria-modal="true"
        aria-label={p.danger ? "Approval for a change to the shared database" : "Question from DebCraft"}
        data-danger={p.danger ? "" : undefined}
        tabIndex={-1}
        onKeyDown={onKey}
        className={cx(
          "max-h-[88vh] w-full overflow-y-auto rounded-2xl border bg-surface p-5 shadow-2xl outline-none",
          p.danger ? "max-w-2xl border-2 border-danger shadow-[0_0_0_4px_var(--danger-soft)]" : "max-w-xl border-border",
        )}
      >
        <div className="mb-3 flex items-start gap-3">
          <span className={cx("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full", p.danger ? "bg-danger text-white" : "bg-warn-soft text-warn")}>
            {p.danger ? <AlertOctagon className="h-4 w-4" aria-hidden /> : <HelpCircle className="h-4 w-4" aria-hidden />}
          </span>
          <h3 className={cx("min-w-0 flex-1 text-[16px] font-semibold leading-snug", p.danger && "text-danger")}>{p.question}</h3>
          <IconButton label="Answer later" onClick={onDismiss}>
            <X className="h-4 w-4" aria-hidden />
          </IconButton>
        </div>
        {p.context && <Markdown text={p.context} className={cx("mb-3", p.danger ? "text-fg" : "text-fg-muted")} />}
        <QuestionForm itemKey={itemKey} p={p} forge={forge} />
      </div>
    </div>
  );
}

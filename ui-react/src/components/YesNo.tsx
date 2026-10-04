// A yes/no question about an optional tool (Tesseract, Gemini): used on the setup guide and on the Environment
// drawer; the answer is saved once per machine (D-201).
import { cx } from "../lib";

export function YesNo({ question, answer, onAnswer }: { question: string; answer?: boolean; onAnswer: (enabled: boolean) => void }) {
  return (
    <div role="group" aria-label={question} className="flex flex-wrap items-center gap-2 text-[12.5px]">
      <span>{question}</span>
      {([true, false] as const).map((value) => (
        <button
          key={String(value)}
          type="button"
          aria-pressed={answer === value}
          onClick={() => onAnswer(value)}
          className={cx(
            "h-6 cursor-pointer rounded-full border px-3 text-[12px] font-semibold transition-colors duration-150 active:scale-95",
            answer === value ? "border-transparent bg-action text-accent-fg" : "border-border hover:bg-raised",
          )}
        >
          {value ? "Yes" : "No"}
        </button>
      ))}
    </div>
  );
}

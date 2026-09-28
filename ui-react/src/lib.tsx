// Shared helpers. All model/tool text is rendered as text, or as Markdown that is parsed with marked and
// sanitised with DOMPurify before it reaches the DOM (spec §15A.3) — never raw HTML.
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/common";
import { marked } from "marked";
import { useEffect, useMemo, useRef, useState } from "react";

export async function api<T = unknown>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "GET",
    credentials: "same-origin",
    headers: options.body !== undefined ? { "Content-Type": "application/json" } : {},
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  return data as T;
}

export function money(usd: number | undefined): string {
  return `$${Number(usd || 0).toFixed(4)}`;
}

export function languageOf(path: string): string | undefined {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return (
    {
      py: "python", js: "javascript", ts: "typescript", tsx: "typescript", sql: "sql", md: "markdown",
      json: "json", yml: "yaml", yaml: "yaml", toml: "ini", ini: "ini", html: "xml", css: "css", ps1: "powershell",
    } as Record<string, string>
  )[ext];
}

export function cx(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/** Sanitised Markdown with highlighted code blocks. */
export function Markdown({ text, className }: { text: string; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const html = useMemo(
    () => DOMPurify.sanitize(marked.parse(text || "", { gfm: true, breaks: false, async: false }) as string),
    [text],
  );
  useEffect(() => {
    ref.current?.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block as HTMLElement));
  }, [html]);
  return <div ref={ref} className={cx("md", className)} dangerouslySetInnerHTML={{ __html: html }} />;
}

/** A code block; highlighted when the language is known. */
export function Code({ text, language, className }: { text: string; language?: string; className?: string }) {
  const html = useMemo(() => {
    if (language && hljs.getLanguage(language)) return hljs.highlight(text, { language }).value;
    return null;
  }, [text, language]);
  return (
    <pre className={cx("font-mono text-[12.5px] leading-relaxed rounded-lg border border-border bg-bg p-3 overflow-auto", className)}>
      {html !== null ? <code dangerouslySetInnerHTML={{ __html: html }} /> : <code>{text}</code>}
    </pre>
  );
}

export function useCopy(): [boolean, (text: string) => void] {
  const [copied, setCopied] = useState(false);
  const copy = (text: string) => {
    void navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1200);
    });
  };
  return [copied, copy];
}

export function storageGet(key: string): string | null {
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null; // storage can be unavailable (private mode, policy)
  }
}

export function storageSet(key: string, value: string): void {
  try {
    window.localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

export interface Attachment {
  path: string; // @-mention path, e.g. .forge/inputs/20260928-101500123456-scan.png
  name: string;
  kind: "image" | "pdf" | "text" | "file";
}

/** Sends a file to Forge (raw body, the name in the query); Forge stores it in the project's .forge/inputs/. */
export async function uploadFile(file: File): Promise<Attachment> {
  const response = await fetch(`/api/upload?name=${encodeURIComponent(file.name || "pasted.png")}`, {
    method: "POST",
    credentials: "same-origin",
    headers: { "Content-Type": "application/octet-stream" },
    body: file,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || `Upload failed (HTTP ${response.status})`);
  return data as Attachment;
}

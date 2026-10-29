// Shared helpers. All model/tool text is rendered as text, or as Markdown that is parsed with marked and
// sanitised with DOMPurify before it reaches the DOM (spec §15A.3) — never raw HTML.
import DOMPurify from "dompurify";
import hljs from "highlight.js/lib/common";
import { marked } from "marked";
import { useEffect, useMemo, useRef, useState } from "react";

export const SIGNED_OUT_EVENT = "forge:signed-out";
export const DRAFT_EVENT = "forge:draft"; // the welcome screen's starter chips fill the composer

export async function api<T = unknown>(path: string, options: { method?: string; body?: unknown } = {}): Promise<T> {
  const response = await fetch(path, {
    method: options.method ?? "GET",
    credentials: "same-origin",
    headers: options.body !== undefined ? { "Content-Type": "application/json" } : {},
    body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  // An expired or missing session (the server restarted): send the user back to the login screen.
  if (response.status === 401 && !path.startsWith("/api/auth")) window.dispatchEvent(new Event(SIGNED_OUT_EVENT));
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
    const root = ref.current;
    if (!root) return;
    root.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block as HTMLElement));
    // A file path in chat looks clickable: it opens the card with its absolute location.
    root.querySelectorAll("code").forEach((code) => {
      if (code.closest("td, th") && !code.closest("pre")) allowBreaks(code);
      if (code.closest("pre") || !filePathOf(code.textContent ?? "")) return;
      code.classList.add("md-file");
      code.title = "Click to see the full path on disk";
    });
    // A copy button beside every code block. The wrapper (not the scrolling <pre>) holds it, so it stays put while a long line scrolls.
    root.querySelectorAll("pre").forEach((pre) => {
      if (pre.parentElement?.classList.contains("md-code")) return;
      const wrapper = document.createElement("div");
      wrapper.className = "md-code";
      pre.replaceWith(wrapper);
      wrapper.appendChild(pre);
      const button = document.createElement("button");
      button.type = "button";
      button.className = "md-copy";
      button.title = "Copy";
      button.setAttribute("aria-label", "Copy code");
      button.innerHTML = COPY_ICON;
      wrapper.appendChild(button);
    });
  }, [html]);
  const onClick = (event: React.MouseEvent<HTMLDivElement>) => {
    const target = event.target as HTMLElement;
    if (target.tagName === "CODE" && !target.closest("pre")) {
      const file = filePathOf(target.textContent ?? "");
      if (file) {
        void showFileLocation(target, file);
        return;
      }
    }
    const button = (event.target as HTMLElement).closest<HTMLButtonElement>(".md-copy");
    if (!button) return;
    const text = button.parentElement?.querySelector("pre")?.textContent ?? "";
    void navigator.clipboard.writeText(text.trimEnd()).then(() => {
      button.innerHTML = CHECK_ICON;
      button.title = "Copied";
      window.setTimeout(() => {
        button.innerHTML = COPY_ICON;
        button.title = "Copy";
      }, 1200);
    });
  };
  return <div ref={ref} onClick={onClick} className={cx("md", className)} dangerouslySetInnerHTML={{ __html: html }} />;
}

// Extensions that make inline code a file name; `json.loads` or `ast.literal_eval` must not look like files.
const FILE_EXTENSIONS = "py|pyi|js|jsx|ts|tsx|json|yaml|yml|toml|ini|cfg|md|txt|sql|html|css|scss|ps1|sh|bat|csv|xml|lock|java|go|rs|rb|php|c|h|cpp|cs|vue|svelte|ipynb|rst|log";
const FILE_PATH = new RegExp(String.raw`^([\w.\-@+]+(?:[\\/][\w.\-@+ ]+)*\.(?:${FILE_EXTENSIONS}))(?::\d+(?:[,-]\d+)*)?$`, "i");

/** `file.py`, `dir/file.py` or `dir/file.py:31,36` as written in chat; null for anything that is not a project file. */
/** A path in a table cell has no spaces, so the browser could not wrap it: the column took the width, the last column was cut
 * off and its rows grew tall (office screenshot 2026-10-29). <wbr> after / \ _ lets it wrap there; the text itself is unchanged,
 * so copying and the file-location click still read the real path. Built from DOM nodes, never HTML strings. */
function allowBreaks(code: Element): void {
  if (code.querySelector("wbr") || code.children.length) return;
  const parts = (code.textContent ?? "").split(/(?<=[/\\_])/);
  if (parts.length < 2) return;
  code.textContent = "";
  parts.forEach((part, index) => {
    code.appendChild(document.createTextNode(part));
    if (index < parts.length - 1) code.appendChild(document.createElement("wbr"));
  });
}

function filePathOf(text: string): string | null {
  const match = FILE_PATH.exec(text.trim());
  return match ? match[1] : null;
}

interface FileLocation {
  workspace: string;
  original: string | null;
  exists_in_workspace: boolean;
  exists_in_original: boolean;
}

let openPopover: HTMLElement | null = null;
function closePopover() {
  openPopover?.remove();
  openPopover = null;
}

/** A small card under a clicked file path: the absolute path in the workspace copy and in the original repo, each one click to copy. */
async function showFileLocation(anchor: HTMLElement, file: string) {
  closePopover();
  let location: FileLocation;
  try {
    location = await api<FileLocation>(`/api/file-location?path=${encodeURIComponent(file)}`);
  } catch {
    location = { workspace: "", original: null, exists_in_workspace: false, exists_in_original: false };
  }
  const card = document.createElement("div");
  card.className = "file-location";
  const rows: Array<[string, string, boolean]> = location.workspace
    ? [["Workspace copy", location.workspace, location.exists_in_workspace]]
    : [["Not found", `No file called ${file} in this project's workspace.`, true]];
  if (location.original) rows.push(["Original repo", location.original, location.exists_in_original]);
  for (const [label, path, exists] of rows) {
    const row = document.createElement("button");
    row.type = "button";
    row.title = "Click to copy";
    const heading = document.createElement("span");
    heading.className = "file-location-label";
    heading.textContent = exists ? label : `${label} (not there yet)`;
    const value = document.createElement("span");
    value.className = "file-location-path";
    value.textContent = path;
    row.append(heading, value);
    row.onclick = () => {
      void navigator.clipboard.writeText(path).then(() => {
        heading.textContent = "Copied";
        window.setTimeout(closePopover, 700);
      });
    };
    card.appendChild(row);
  }
  document.body.appendChild(card);
  const box = anchor.getBoundingClientRect();
  card.style.top = `${window.scrollY + box.bottom + 6}px`;
  card.style.left = `${Math.max(8, Math.min(window.scrollX + box.left, window.innerWidth - card.offsetWidth - 8))}px`;
  openPopover = card;
  const dismiss = (event: Event) => {
    if (card.contains(event.target as Node)) return;
    closePopover();
    document.removeEventListener("mousedown", dismiss);
    document.removeEventListener("keydown", dismiss);
  };
  window.setTimeout(() => {
    document.addEventListener("mousedown", dismiss);
    document.addEventListener("keydown", dismiss);
  }, 0);
}

// The lucide "copy" and "check" icons as fixed strings: the buttons live inside Markdown HTML that React does not render.
const ICON_ATTRIBUTES = 'width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"';
const COPY_ICON = `<svg ${ICON_ATTRIBUTES}><rect width="14" height="14" x="8" y="8" rx="2" ry="2"/><path d="M4 16c-1.1 0-2-.9-2-2V4c0-1.1.9-2 2-2h10c1.1 0 2 .9 2 2"/></svg>`;
const CHECK_ICON = `<svg ${ICON_ATTRIBUTES}><path d="M20 6 9 17l-5-5"/></svg>`;

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

/** Sends a file to DebCraft (raw body, the name in the query); DebCraft stores it in the project's .forge/inputs/. */
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

/** "just now", "5 minutes ago", "3 days ago", else the date. */
export function timeAgo(iso: string, now: number = Date.now()): string {
  const seconds = Math.max(0, Math.round((now - new Date(iso).getTime()) / 1000));
  if (Number.isNaN(seconds)) return "";
  if (seconds < 60) return "just now";
  const units: [number, string][] = [
    [86400, "day"],
    [3600, "hour"],
    [60, "minute"],
  ];
  for (const [size, name] of units) {
    if (seconds >= size) {
      const count = Math.floor(seconds / size);
      if (name === "day" && count >= 30) break;
      return `${count} ${name}${count === 1 ? "" : "s"} ago`;
    }
  }
  return new Date(iso).toLocaleDateString();
}

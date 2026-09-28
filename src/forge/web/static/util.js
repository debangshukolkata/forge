// Small helpers shared by the UI modules. All model/tool text goes through md() or text nodes:
// Markdown is rendered with marked and then sanitised with DOMPurify (spec §15A.3).

export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else if (key === "text") node.textContent = value;
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function md(markdown) {
  const box = el("div", { class: "md" });
  box.innerHTML = DOMPurify.sanitize(marked.parse(markdown || "", { gfm: true, breaks: false }));
  box.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
  return box;
}

export function code(text, language) {
  const block = el("code", { class: language ? `language-${language}` : "" }, text);
  if (language && hljs.getLanguage(language)) hljs.highlightElement(block);
  return el("pre", {}, block);
}

export function copyButton(text) {
  return el("button", {
    class: "copy", type: "button", text: "copy",
    onclick: async (event) => {
      await navigator.clipboard.writeText(text);
      event.target.textContent = "copied";
      setTimeout(() => (event.target.textContent = "copy"), 1200);
    },
  });
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    credentials: "same-origin",
    headers: options.body ? { "Content-Type": "application/json" } : {},
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail || data.error || `HTTP ${response.status}`);
  return data;
}

export function money(usd) {
  return `$${Number(usd || 0).toFixed(4)}`;
}

export function languageOf(path) {
  const ext = (path.split(".").pop() || "").toLowerCase();
  return { py: "python", js: "javascript", ts: "typescript", sql: "sql", md: "markdown", json: "json",
    yml: "yaml", yaml: "yaml", toml: "ini", ini: "ini", html: "xml", css: "css", ps1: "powershell" }[ext];
}

// The right panel (spec §15A.4): Tasks, Files, Diffs (+ checkpoints), DB, Context & cost, Settings.
// Panels read the REST API and re-render when relevant events arrive.

import { api, code, copyButton, el, languageOf, md, money } from "./util.js";

export class Panels {
  constructor(tabs, body, app) {
    this.tabs = tabs;
    this.body = body;
    this.app = app;
    this.active = "tasks";
    this.context = null;
    this.cost = null;
    this.diffFormat = "line-by-line";
    tabs.querySelectorAll("button").forEach((button) =>
      button.addEventListener("click", () => this.show(button.dataset.tab)));
  }

  show(tab) {
    this.active = tab;
    this.tabs.querySelectorAll("button").forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
    this.render();
  }

  refresh(kind) {
    const affects = { tasks: ["tasks", "db", "learning"], files: ["files", "diffs"], context: ["context"], db: ["db"], learning: ["learning"], evals: ["evals"] }[kind] || [];
    if (affects.includes(this.active)) this.render();
  }

  async render() {
    const view = { tasks: this.tasks, files: this.files, diffs: this.diffs, db: this.db, evals: this.evals, learning: this.learning, context: this.contextTab, settings: this.settings }[this.active];
    try {
      this.body.replaceChildren(await view.call(this));
    } catch (error) {
      this.body.replaceChildren(el("div", { class: "error" }, error.message));
    }
  }

  // --- Tasks ---

  async tasks() {
    const state = this.app.state;
    if (!state.workspace) return el("p", { class: "muted" }, "Open a workspace to see its tasks.");
    const items = (state.tasks || []).map((task) =>
      el("li", { class: task.id === state.current_task ? "current" : "" },
        el("span", { class: `st ${task.status}` }, task.status.replace("_", " ")),
        el("strong", {}, `${task.id} `), task.title,
        task.attempts > 1 && el("span", { class: "muted" }, ` · attempt ${task.attempts}`),
        task.blocked_reason && el("div", { class: "muted" }, `blocked: ${task.blocked_reason}`)));
    return el("div", {}, el("div", { class: "muted" }, `Phase: ${state.phase}`),
      items.length ? el("ul", { class: "tasklist" }, items) : el("p", { class: "muted" }, "No tasks yet — they appear once the plan is approved."));
  }

  // --- Files ---

  async files() {
    const box = el("div", {});
    const viewer = el("div", { class: "viewer" });
    box.append(el("div", { class: "row" },
      el("a", { href: "/api/output.zip", download: "" }, el("button", { type: "button" }, "Download output.zip")),
      el("button", { onclick: () => this.showInstructions(viewer) }, "Copy instructions")));
    for (const root of ["repo", "output"]) {
      const tree = el("div", { class: "tree" }, el("strong", {}, root === "repo" ? "repo/" : "output/"));
      tree.append(await this.folder(root, "", viewer));
      box.append(tree);
    }
    box.append(viewer);
    return box;
  }

  async folder(root, dir, viewer) {
    const data = await api(`/api/tree?root=${root}&dir=${encodeURIComponent(dir)}`);
    return el("ul", {}, data.entries.map((entry) => {
      const label = el("span", { class: entry.status || "" }, entry.dir ? `▸ ${entry.name}` : entry.name);
      const item = el("li", {}, label);
      label.addEventListener("click", async () => {
        if (!entry.dir) return this.openFile(root, entry.path, viewer);
        const open = item.querySelector("ul");
        if (open) { open.remove(); label.textContent = `▸ ${entry.name}`; return; }
        label.textContent = `▾ ${entry.name}`;
        item.append(await this.folder(root, entry.path, viewer));
      });
      return item;
    }));
  }

  async openFile(root, path, viewer) {
    const file = await api(`/api/file?root=${root}&path=${encodeURIComponent(path)}`);
    viewer.replaceChildren(el("h4", {}, `${root}/${path}`),
      file.binary ? el("p", { class: "muted" }, "Binary file") : code(file.text, languageOf(path)),
      file.truncated ? el("p", { class: "muted" }, "(truncated)") : "");
  }

  async showInstructions(viewer) {
    try {
      const file = await api("/api/file?root=output&path=COPY_INSTRUCTIONS.md");
      const rendered = md(file.text);
      rendered.classList.add("instructions");
      rendered.querySelectorAll("li").forEach((item, index) => {
        const key = `forge-copy-${this.app.state.workspace.path}-${index}`;
        const box = el("input", { type: "checkbox" });
        try { box.checked = localStorage.getItem(key) === "1"; } catch { /* storage unavailable */ }
        box.addEventListener("change", () => { try { localStorage.setItem(key, box.checked ? "1" : "0"); } catch { /* ignore */ } });
        item.prepend(box);
      });
      viewer.replaceChildren(rendered);
    } catch {
      viewer.replaceChildren(el("p", { class: "muted" }, "No output yet: it is built at EXPORT, or with /export."));
    }
  }

  // --- Diffs and checkpoints ---

  async diffs() {
    const [diff, checkpoints] = await Promise.all([api("/api/diff"), api("/api/checkpoints")]);
    const box = el("div", {});
    box.append(el("div", { class: "row" },
      el("button", { onclick: () => { this.diffFormat = this.diffFormat === "side-by-side" ? "line-by-line" : "side-by-side"; this.render(); } },
        this.diffFormat === "side-by-side" ? "Unified" : "Side by side")));
    if (!diff.patch.trim()) box.append(el("p", { class: "muted" }, "No changes yet."));
    else {
      const html = Diff2Html.html(diff.patch, { drawFileList: true, matching: "lines", outputFormat: this.diffFormat });
      const view = el("div", {});
      view.innerHTML = DOMPurify.sanitize(html);
      box.append(view);
    }
    box.append(el("h4", {}, "Checkpoints"));
    if (!checkpoints.length) box.append(el("p", { class: "muted" }, "None yet."));
    box.append(el("ul", { class: "tasklist" }, checkpoints.slice().reverse().map((cp) =>
      el("li", {}, el("strong", {}, `${cp.id} `), cp.label, el("div", { class: "muted" }, cp.created),
        el("button", { onclick: () => confirm(`Undo every change back to and including checkpoint ${cp.id}?`) && this.app.command(`/rewind ${cp.id}`) }, "Rewind to here")))));
    return box;
  }

  // --- Database ---

  async db() {
    const state = this.app.state;
    const box = el("div", {});
    if (!state.database) return el("p", { class: "muted" }, "No database configured (LOCAL_PG_URL / DEV_PG_URL in Forge's .env).");
    box.append(code(state.database), el("div", { class: "row" },
      el("button", { onclick: () => this.app.command("/db status") }, "Re-check access"),
      el("button", { onclick: () => confirm("Drop every object Forge created in the scratch schema?") && this.app.command("/db cleanup") }, "Clean up scratch objects")));
    for (const request of state.db_requests || []) {
      const pasted = el("textarea", { rows: 2, placeholder: "If Forge can't reach the DB: paste the verification query's result (column names, no data rows)" });
      box.append(el("div", { class: "card" },
        el("h3", {}, `${request.id}: ${request.title} `, el("span", { class: "muted" }, `[${request.status}]`)),
        el("div", {}, request.purpose), el("div", { class: "muted" }, `${request.target} · run by ${request.who}`),
        el("div", {}, "SQL", copyButton(request.sql)), code(request.sql, "sql"),
        el("div", {}, "Verification", copyButton(request.verification_query)), code(request.verification_query, "sql"),
        request.status === "pending" && pasted,
        request.status === "pending" && el("div", { class: "row" },
          el("button", { class: "primary", onclick: () => this.app.command(`/db done ${request.id} ${pasted.value}`.trim()) }, "Mark done"),
          el("button", { onclick: () => this.app.command(`/db cant ${request.id} ${pasted.value || "no access"}`) }, "I can't"),
          el("button", { onclick: () => this.app.command(`/db skip ${request.id}`) }, "Skip"))));
    }
    return box;
  }

  // --- Evals: accuracy runs of the built system (spec §13A) ---

  async evals() {
    const runs = await api("/api/evals");
    const box = el("div", {});
    if (!runs.length) return el("p", { class: "muted" }, "No eval runs yet. For perception/extraction work Forge keeps an eval set in evals/<name>/ and runs it with run_eval.");
    const viewer = el("div", { class: "viewer" });
    box.append(el("ul", { class: "tasklist" }, runs.slice().reverse().map((run) =>
      el("li", {},
        el("strong", {}, `Run ${run.n} · ${run.name} `),
        el("span", { class: run.misses.length ? "st blocked" : "st done" }, run.misses.length ? "targets missed" : "targets met"),
        el("div", { class: "muted" }, Object.entries(run.metrics).map(([k, v]) => `${k}: ${v}`).join(" · ")),
        el("button", { onclick: async () => {
          const report = await api(`/api/evals/${run.n}`);
          viewer.replaceChildren(md(report.markdown), ...report.overlays.map((name) =>
            el("figure", {}, el("img", { src: `/api/evals/${run.n}/overlay/${encodeURIComponent(name)}`, alt: name, width: "100%" }), el("figcaption", { class: "muted" }, `${name} — green expected, red predicted`))));
        } }, "Show report")))), viewer);
    return box;
  }

  // --- Learning: lessons, library, improvements (spec §12) ---

  async learning() {
    const data = await api("/api/learning");
    const box = el("div", {});
    box.append(el("h4", {}, "Lessons"), el("p", { class: "muted" }, "Only approved lessons are used; they are pinned at the start of related tasks."));
    if (!data.lessons.length) box.append(el("p", { class: "muted" }, "None yet: proposed in the retro after each requirement."));
    for (const lesson of data.lessons) {
      box.append(el("div", { class: "card" },
        el("div", {}, el("span", { class: `st ${lesson.status === "approved" ? "done" : "pending"}` }, lesson.status), ` ${lesson.id} (${lesson.scope})`),
        el("div", {}, lesson.text),
        el("div", { class: "row" },
          lesson.status !== "approved" && el("button", { class: "primary", onclick: () => this.app.command(`/lessons approve ${lesson.id}`) }, "Approve"),
          el("button", { onclick: () => this.app.command(`/lessons reject ${lesson.id}`) }, "Reject"),
          lesson.scope !== "global" && lesson.status === "approved" && el("button", { onclick: () => this.app.command(`/lessons promote ${lesson.id}`) }, "Make global"))));
    }
    box.append(el("h4", {}, "Requirements library (this codebase)"));
    box.append(el("ul", { class: "tasklist" }, data.cards.map((card) =>
      el("li", {}, el("strong", {}, `${card.id} `), card.title, el("div", { class: "muted" }, `${card.status} · ${card.created}`),
        el("button", { onclick: () => this.app.command(`/library show ${card.id}`) }, "Show")))));
    if (!data.cards.length) box.append(el("p", { class: "muted" }, "No earlier requirements yet."));
    box.append(el("h4", {}, "Improvement proposals"), el("p", { class: "muted" }, "Forge never changes itself: you apply tier-2 tweaks with /improve apply; tier-3 patches are yours to apply."));
    for (const p of data.improvements) {
      box.append(el("div", { class: "card" }, el("strong", {}, `${p.id} `), `tier ${p.tier} · ${p.status} · ${p.title}`,
        el("div", { class: "row" },
          el("button", { onclick: () => this.app.command(`/improve show ${p.id}`) }, "Show"),
          p.tier === 3 && el("button", { onclick: () => this.app.command(`/improve validate ${p.id}`) }, "Validate"),
          p.tier === 2 && p.status !== "applied" && el("button", { class: "primary", onclick: () => confirm(`Apply ${p.id}?`) && this.app.command(`/improve apply ${p.id}`) }, "Apply"),
          el("button", { onclick: () => this.app.command(`/improve reject ${p.id}`) }, "Reject"))));
    }
    return box;
  }

  // --- Context and cost ---

  async contextTab() {
    const c = this.context;
    const box = el("div", {});
    if (c) {
      box.append(el("div", {}, `Context window: ${c.percent}% used`), el("div", { class: "bar" }, el("div", { style: null })));
      box.querySelector(".bar > div").style.width = `${Math.min(100, c.percent)}%`;
      box.append(el("div", { class: "kv" },
        "Fixed (prompt + tools)", String(c.fixed), "Pinned", String(c.pinned), "History", String(c.history),
        "Free", String(c.free), "Usable", String(c.usable), "Compactions", String(c.compactions)));
    } else box.append(el("p", { class: "muted" }, "No model call yet."));
    if (this.cost) {
      box.append(el("h4", {}, "Cost"), el("div", { class: "kv" },
        "Total", money(this.cost.total_usd), "Budget", money(this.cost.budget_usd), "Calls", String(this.cost.calls),
        ...Object.entries(this.cost.cost_by_role || {}).flatMap(([role, usd]) => [role, money(usd)])));
    }
    box.append(el("div", { class: "row" }, el("button", { onclick: () => this.app.command("/compact") }, "Compact now")));
    return box;
  }

  // --- Settings ---

  async settings() {
    const config = await api("/api/config");
    const box = el("div", {}, el("p", { class: "muted" }, "Keys and endpoints stay in Forge's .env; they can't be viewed or edited here."));
    const rows = Object.entries(config.roles || {}).map(([role, model]) => {
      const select = el("select", { onchange: () => this.app.command(`/model ${role} ${select.value}`) },
        (config.models || []).map((m) => el("option", { value: m, selected: m === model }, m)));
      return [el("span", {}, role), select];
    });
    box.append(el("h4", {}, "Model per role"), el("div", { class: "kv" }, rows.flat()));
    const mode = el("select", { onchange: () => this.app.command(`/mode ${mode.value}`) },
      ["plan", "default", "auto"].map((m) => el("option", { value: m, selected: m === config.permission_mode }, m)));
    box.append(el("h4", {}, "Permission mode"), mode,
      el("h4", {}, "Other"), el("div", { class: "kv" }, "Sandbox", String(config.sandbox),
        ...Object.entries(config.limits || {}).flatMap(([k, v]) => [k, String(v)])));
    return box;
  }
}

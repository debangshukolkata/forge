// Forge web UI entry point: loads state, keeps one WebSocket to the engine (replaying events since the last
// one seen, so a reload or reconnect never loses anything), and wires the composer, home screen and panels.

import { Chat } from "./chat.js";
import { Panels } from "./panels.js";
import { api, el, money } from "./util.js";

const SLASH = ["/help", "/model", "/cost", "/clear", "/context", "/compact", "/checkpoints", "/undo", "/rewind",
  "/export", "/mode", "/requirements", "/plan", "/tasks", "/restructure", "/kb status", "/kb build", "/kb refresh",
  "/db", "/db requests", "/db done", "/db cant", "/db cleanup", "/diagnose", "/remember", "/memory",
  "/profile", "/assumptions", "/contract", "/revision", "/forget-snippet",
  "/library", "/lessons", "/retro", "/stats", "/improve"];

class App {
  constructor() {
    this.state = { workspace: null };
    this.lastSeq = 0;
    this.socket = null;
    this.controls = false;
    this.retry = 500;
    this.$ = (id) => document.getElementById(id);
    this.chat = new Chat(this.$("chat"), (input) => this.send(input), (title) => this.waiting(title));
    this.panels = new Panels(this.$("tabs"), this.$("tab-body"), this);
    this.bind();
  }

  async start() {
    await this.loadState();
    if (this.state.workspace) this.showChat(); else this.showHome();
  }

  async loadState() {
    this.state = await api("/api/state");
    this.renderStatus();
    this.renderRecent();
  }

  // --- views ---

  showHome() {
    this.$("home").hidden = false;
    this.$("chat-view").hidden = true;
    api("/api/profiles").then((names) => {
      this.$("profile-select").replaceChildren(...names.map((n) => el("option", { value: n }, n)));
    }).catch(() => {});
    api("/api/doctor").then((results) => {
      this.$("doctor").replaceChildren(...results.map((r) => el("li", { class: r.status }, `${r.name}: ${r.detail}`)));
    }).catch(() => {});
  }

  showChat() {
    this.$("home").hidden = true;
    this.$("chat-view").hidden = false;
    this.chat.clear();
    this.lastSeq = 0;
    this.connect();
    this.panels.render();
  }

  renderRecent() {
    const current = this.state.workspace && this.state.workspace.path;
    this.$("recent").replaceChildren(...(this.state.recent || []).map((w) =>
      el("li", { class: w.path === current ? "active" : "", title: w.path, onclick: () => this.open(w.path) },
        w.name, el("small", {}, w.repo))));
  }

  renderStatus(extra = {}) {
    const s = this.state;
    this.$("st-workspace").textContent = s.workspace ? `${s.workspace.name}${s.workspace.mode === "B" ? " · Mode B" : ""}` : "no workspace";
    this.$("st-phase").textContent = s.workspace ? `phase: ${s.phase}` : "";
    const busy = extra.busy ?? s.busy;
    const busyPill = this.$("st-busy");
    busyPill.textContent = s.workspace ? (busy ? "working…" : "idle") : "";
    busyPill.className = `pill ${busy ? "busy" : ""}`;
    this.$("st-control").textContent = s.workspace ? (this.controls ? "" : "watching (read-only)") : "";
  }

  // --- workspaces ---

  async open(path) {
    try {
      await api("/api/open", { method: "POST", body: { workspace: path } });
      await this.loadState();
      this.showChat();
    } catch (error) {
      alert(error.message);
    }
  }

  // --- the event stream ---

  connect() {
    if (this.socket) this.socket.close();
    const socket = new WebSocket(`ws://${location.host}/ws`);
    this.socket = socket;
    socket.onopen = () => {
      this.retry = 500;
      this.chat.replaying = this.lastSeq === 0;
      socket.send(JSON.stringify({ type: "hello", since: this.lastSeq }));
    };
    socket.onmessage = (message) => this.receive(JSON.parse(message.data));
    socket.onclose = () => {
      if (this.socket !== socket) return;
      setTimeout(() => this.state.workspace && this.connect(), this.retry);
      this.retry = Math.min(this.retry * 2, 8000);
    };
  }

  async receive(message) {
    if (message.type === "hello") {
      this.controls = message.controls;
      this.replayUntil = message.last_seq;
      if (this.lastSeq >= message.last_seq) this.replayDone();
      this.renderStatus();
      if (!this.controls) this.chat.add(el("div", { class: "notice" }, "Another window controls this session; this one watches. ",
        el("button", { onclick: () => this.socket.send(JSON.stringify({ type: "take_control" })) }, "Take control")));
      return;
    }
    if (message.type === "control") { this.controls = message.controls; this.renderStatus(); return; }
    if (message.type === "rejected") { this.chat.add(el("div", { class: "error" }, message.reason)); return; }
    if (message.type !== "event") return;
    const event = message.event;
    if (event.seq <= this.lastSeq) return;
    this.lastSeq = event.seq;
    this.onEvent(event);
    if (this.chat.replaying && event.seq >= this.replayUntil) this.replayDone();
  }

  async replayDone() {
    this.chat.replaying = false;
    await this.loadState();
    this.chat.settleAfterReplay(this.state.pending || []);
    this.chat.scroll();
    this.panels.render();
  }

  onEvent(event) {
    const p = event.payload;
    if (event.type === "user_message") this.chat.userMessage(p.text);
    else this.chat.handle(event);
    switch (event.type) {
      case "status_changed":
        this.state.busy = p.state === "working";
        this.renderStatus();
        if (p.state === "idle" && !this.chat.replaying) this.loadState().then(() => this.panels.refresh("tasks"));
        break;
      case "context_updated":
        this.panels.context = p;
        this.$("st-context").textContent = `ctx ${p.percent}%`;
        this.panels.refresh("context");
        break;
      case "cost_updated":
        this.panels.cost = p;
        this.$("st-cost").textContent = money(p.total_usd);
        this.panels.refresh("context");
        break;
      case "lesson_proposed":
      case "improvement_proposed":
        if (!this.chat.replaying) this.panels.refresh("learning");
        break;
      case "task_list_updated":
      case "db_request_created":
      case "db_request_updated":
        if (!this.chat.replaying) this.loadState().then(() => this.panels.refresh("tasks"));
        break;
      case "file_changed":
        if (!this.chat.replaying) this.panels.refresh("files");
        break;
      default:
        break;
    }
  }

  send(input) {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.chat.add(el("div", { class: "error" }, "Not connected to Forge; reconnecting…"));
      return;
    }
    this.socket.send(JSON.stringify({ type: "input", input }));
  }

  command(text) {
    this.send({ kind: "slash_command", text });
  }

  waiting(title) {
    this.$("st-busy").className = "pill waiting";
    this.$("st-busy").textContent = "waiting for you";
    if (document.hidden && "Notification" in window && Notification.permission === "granted") {
      new Notification("Forge", { body: title });
    }
  }

  // --- composer, keyboard, buttons ---

  bind() {
    const input = this.$("input");
    const hints = this.$("slash-hints");
    const submit = () => {
      const text = input.value.trim();
      if (!text) return;
      if (text.startsWith("/")) this.command(text); else this.send({ kind: "send_message", text });
      input.value = "";
      hints.hidden = true;
      if ("Notification" in window && Notification.permission === "default") Notification.requestPermission();
    };
    input.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); submit(); }
    });
    input.addEventListener("input", () => {
      const text = input.value;
      const matches = text.startsWith("/") && !text.includes("\n") ? SLASH.filter((c) => c.startsWith(text.split(" ")[0])) : [];
      hints.hidden = matches.length === 0 || SLASH.includes(text.trim());
      hints.replaceChildren(...matches.map((c) => el("div", { onclick: () => { input.value = `${c} `; hints.hidden = true; input.focus(); } }, c)));
    });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && this.state.workspace) this.send({ kind: "interrupt" });
    });
    this.$("btn-send").addEventListener("click", submit);
    this.$("btn-stop").addEventListener("click", () => this.send({ kind: "interrupt" }));
    this.$("btn-home").addEventListener("click", () => this.showHome());
    this.$("btn-quit").addEventListener("click", async () => {
      if (!confirm("Stop Forge (the server and any running work)?")) return;
      await api("/api/quit", { method: "POST" }).catch(() => {});
      document.body.replaceChildren(el("p", { class: "notice" }, "Forge has stopped. You can close this tab."));
    });
    this.$("new-standalone").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      this.$("standalone-error").textContent = "Creating the workspace and its venv…";
      try {
        await api("/api/standalone", { method: "POST", body: { workspace: form.get("workspace"), profile: form.get("profile") } });
        this.$("standalone-error").textContent = "";
        await this.loadState();
        this.showChat();
      } catch (error) {
        this.$("standalone-error").textContent = error.message;
      }
    });
    this.$("new-workspace").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.target);
      this.$("new-error").textContent = "Creating the workspace (copying the repository)…";
      try {
        await api("/api/workspaces", { method: "POST", body: {
          repo: form.get("repo"), workspace: form.get("workspace"), app_folder: form.get("app_folder") || null } });
        this.$("new-error").textContent = "";
        await this.loadState();
        this.showChat();
      } catch (error) {
        this.$("new-error").textContent = error.message;
      }
    });
  }
}

window.forgeApp = new App();
window.forgeApp.start();

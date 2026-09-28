// The chat: renders engine events (spec §15A.2) — streamed text, tool cards, approval / question /
// user-action cards, notices and errors. Interactive cards call send(input) with the typed inputs of
// engine/inputs.py.

import { code, copyButton, el, md } from "./util.js";

export class Chat {
  constructor(root, send, onWaiting) {
    this.root = root;
    this.send = send;
    this.onWaiting = onWaiting;
    this.streaming = null; // the assistant bubble receiving message_delta
    this.tools = new Map(); // tool call id -> <details>
    this.cards = new Map(); // approval/question id -> card element (the latest one wins)
    this.pending = new Set(); // ids still waiting for an answer (from /api/state after a replay)
    this.replaying = false;
  }

  clear() {
    this.root.replaceChildren();
    this.streaming = null;
    this.tools.clear();
    this.cards.clear();
  }

  scroll() {
    const nearBottom = this.root.scrollHeight - this.root.scrollTop - this.root.clientHeight < 200;
    if (nearBottom || this.replaying) this.root.scrollTop = this.root.scrollHeight;
  }

  add(node) {
    this.root.append(node);
    this.scroll();
    return node;
  }

  userMessage(text) {
    this.add(el("div", { class: "msg user" }, text));
  }

  handle(event) {
    const p = event.payload;
    switch (event.type) {
      case "message_delta":
        if (!this.streaming) this.streaming = this.add(el("div", { class: "msg assistant streaming" }));
        this.streaming.append(document.createTextNode(p.text));
        this.scroll();
        break;
      case "message_done":
        if (this.streaming) this.streaming.remove();
        this.streaming = null;
        if (p.text && p.text.trim()) this.add(el("div", { class: "msg assistant" }, md(p.text)));
        break;
      case "tool_call_started":
        this.toolStarted(p);
        break;
      case "tool_call_finished":
        this.toolFinished(p);
        break;
      case "approval_requested":
        this.approval(p);
        break;
      case "question_asked":
        this.question(p);
        break;
      case "user_action_requested":
        this.userAction(p);
        break;
      case "notice":
        this.notice(p);
        break;
      case "error":
        this.add(el("div", { class: "error" }, p.message || "Error"));
        break;
      case "file_changed":
        break; // shown in the Files/Diffs panels
      default:
        break;
    }
  }

  // --- tools ---

  toolStarted(p) {
    const card = el("details", { class: "tool running" },
      el("summary", {}, el("span", { class: "name" }, p.name), el("span", { class: "sum" }, p.summary || ""),
        el("span", { class: "state" }, "…")));
    this.tools.set(p.id, card);
    this.streaming = null;
    this.add(card);
  }

  toolFinished(p) {
    const card = this.tools.get(p.id);
    if (!card) return;
    card.className = `tool ${p.ok ? "ok" : "fail"}`;
    card.querySelector(".state").textContent = `${p.ok ? "✔" : "✖"} ${p.duration_s ?? ""}s`;
    if (p.preview) card.append(code(p.preview));
  }

  // --- cards that wait for the user ---

  register(id, card) {
    const previous = this.cards.get(id);
    if (previous) finish(previous, "superseded");
    this.cards.set(id, card);
    if (!this.replaying) this.onWaiting(card.dataset.title || "Forge is waiting for you");
    return this.add(card);
  }

  settleAfterReplay(pendingIds) {
    this.pending = new Set(pendingIds);
    for (const [id, card] of this.cards) {
      if (!this.pending.has(id)) finish(card, "answered earlier");
    }
  }

  approval(p) {
    const card = el("div", { class: "ask approval", "data-title": "Approval needed" });
    if (p.kind) {
      // Requirements or plan approval: the full Markdown with Approve / Request changes / Reject.
      const feedback = el("textarea", { rows: 3, placeholder: "What should change?" });
      card.append(el("h4", {}, `Approve the ${p.kind}?`), md(p.markdown || p.summary || ""), feedback,
        el("div", { class: "buttons" },
          el("button", { class: "primary", onclick: () => this.reply(card, { kind: "approve", request_id: p.id }, "Approved") }, "Approve"),
          el("button", { onclick: () => this.reply(card, { kind: "reject", request_id: p.id, instruction: feedback.value || "Please revise." }, "Changes requested") }, "Request changes"),
          el("button", { class: "danger", onclick: () => this.reply(card, { kind: "reject", request_id: p.id, instruction: feedback.value || "Rejected." }, "Rejected") }, "Reject")));
    } else {
      // Permission prompt for a command or tool.
      const instruction = el("textarea", { rows: 2, placeholder: "Deny: tell Forge what to do instead (optional)" });
      const prefix = p.can_remember_prefix && !p.always_ask;
      card.append(el("h4", {}, `Allow ${p.tool}?`),
        p.command ? code(p.command, "powershell") : el("div", {}, p.summary || ""),
        el("div", { class: "muted" }, p.reason || ""), instruction,
        el("div", { class: "buttons" },
          el("button", { class: "primary", onclick: () => this.reply(card, { kind: "approve", request_id: p.id, scope: "once" }, "Allowed once") }, "Allow once"),
          prefix && el("button", { onclick: () => this.reply(card, { kind: "approve", request_id: p.id, scope: "prefix" }, `Always allowed '${p.can_remember_prefix}'`) }, `Always allow '${p.can_remember_prefix}'`),
          el("button", { class: "danger", onclick: () => this.reply(card, { kind: "reject", request_id: p.id, instruction: instruction.value || null }, "Denied") }, "Deny")));
    }
    this.register(p.id, card);
  }

  question(p) {
    const card = el("div", { class: "ask question", tabindex: "0", "data-title": "Forge has a question" });
    const other = el("textarea", { rows: 2, placeholder: "Other… (your own answer)" });
    card.append(el("h4", {}, p.question));
    if (p.context) card.append(md(p.context));
    (p.options || []).forEach((option, index) => {
      const recommended = option.label === p.recommended;
      card.append(el("div", { class: "option" },
        el("button", { class: recommended ? "primary" : "", onclick: () => this.answer(card, p.id, option.label) },
          `${index + 1}. ${option.label}`),
        recommended && el("span", { class: "badge" }, "Recommended"),
        option.description && el("div", {}, option.description),
        option.pros && el("small", {}, `Pros: ${option.pros}`),
        option.cons && el("small", {}, `Cons: ${option.cons}`),
        option.risks && el("small", {}, `Risks: ${option.risks}`)));
    });
    card.append(other, el("div", { class: "buttons" },
      el("button", { onclick: () => other.value.trim() && this.reply(card, { kind: "answer", question_id: p.id, text: other.value.trim() }, `You answered: ${other.value.trim()}`) }, "Send answer")));
    card.addEventListener("keydown", (event) => {
      const option = (p.options || [])[Number(event.key) - 1];
      if (option && event.target === card) this.answer(card, p.id, option.label);
    });
    this.register(p.id, card);
  }

  answer(card, id, label) {
    this.reply(card, { kind: "answer", question_id: id, choice: label }, `You chose: ${label}`);
  }

  userAction(p) {
    const card = el("div", { class: "ask action", "data-title": "Please do a step for Forge" });
    const note = el("textarea", { rows: 2, placeholder: "Reason, or paste the output if it failed" });
    const steps = el("ol", { class: "steps" }, (p.steps || []).map((step) => el("li", {}, step, copyButton(step))));
    const choose = (choice, label) =>
      this.reply(card, { kind: "answer", question_id: p.id, choice, text: note.value.trim() || null }, label);
    card.append(el("h4", {}, p.title || "Action needed"), steps,
      p.verify_command && el("div", { class: "muted" }, "Forge will check with: ", el("code", {}, p.verify_command)), note,
      el("div", { class: "buttons" },
        el("button", { class: "primary", onclick: () => choose("done", "Done") }, "Done"),
        el("button", { onclick: () => choose("skip", "Skipped") }, "Skip"),
        el("button", { onclick: () => choose("cant", "You can't do it") }, "I can't"),
        el("button", { class: "danger", onclick: () => choose("failed", "It failed") }, "It failed")));
    this.register(p.id, card);
  }

  reply(card, input, label) {
    if (card.classList.contains("done")) return;
    this.send(input);
    finish(card, label);
  }

  notice(p) {
    if (p.kind === "usage") return;
    if (p.kind === "command_output") {
      this.add(el("div", { class: "notice" }, code(p.text || "")));
      return;
    }
    this.add(el("div", { class: `notice ${p.kind || ""}` }, p.text || p.kind || ""));
  }
}

function finish(card, label) {
  card.classList.add("done");
  card.querySelectorAll("button, textarea").forEach((control) => (control.disabled = true));
  if (!card.querySelector(".answered")) card.append(el("div", { class: "answered" }, label));
}

// Forge labelling helper: draw boxes, type field values, mark unreadable fields; saves labels/<sample>.json.
// No inline scripts or styles (CSP): styling is applied from here.

const $ = (id) => document.getElementById(id);
const state = { samples: [], index: 0, image: new Image(), scale: 1, boxes: [], drag: null };

function style() {
  document.body.style.cssText = "margin:0;font-family:Segoe UI,system-ui,sans-serif;font-size:14px;";
  document.querySelector("header").style.cssText = "display:flex;gap:8px;align-items:center;padding:8px;border-bottom:1px solid #ccc;";
  document.querySelector("main").style.cssText = "display:grid;grid-template-columns:1fr 340px;height:calc(100vh - 48px);";
  $("canvas-wrap").style.cssText = "overflow:auto;background:#eee;";
  document.querySelector("aside").style.cssText = "padding:10px;overflow:auto;border-left:1px solid #ccc;";
}

async function load() {
  const response = await fetch("/api/samples", { credentials: "same-origin" });
  state.samples = await response.json();
  show(0);
}

function show(index) {
  if (!state.samples.length) { $("status").textContent = "No samples in samples/."; return; }
  state.index = (index + state.samples.length) % state.samples.length;
  const sample = state.samples[state.index];
  const label = sample.label || { fields: {}, regions: [], unreadable: [] };
  state.boxes = (label.regions || []).map((r) => ({ label: r.label, box: r.box.slice() }));
  $("sample-name").textContent = sample.name;
  $("progress").textContent = `${state.index + 1} / ${state.samples.length}`;
  $("verified").textContent = label.verified === false || label.unverified ? "Pre-filled by a model: check and save." : (sample.label ? "Saved." : "Not labelled yet.");
  $("sensitive").checked = label.sensitive !== false;
  renderFields(label.fields || {}, label.unreadable || []);
  state.image = new Image();
  state.image.onload = () => draw();
  state.image.src = `/sample/${encodeURIComponent(sample.name)}`;
}

function renderFields(fields, unreadable) {
  const box = $("fields");
  box.replaceChildren();
  const names = new Set([...Object.keys(fields), ...unreadable]);
  if (!names.size) names.add("field_1");
  for (const name of names) addFieldRow(name, typeof fields[name] === "string" ? fields[name] : JSON.stringify(fields[name] ?? ""), unreadable.includes(name));
}

function addFieldRow(name = "", value = "", unreadable = false) {
  const row = document.createElement("div");
  row.style.cssText = "display:flex;gap:4px;margin:4px 0;align-items:center;";
  const key = Object.assign(document.createElement("input"), { value: name, placeholder: "field" });
  key.style.width = "110px";
  const val = Object.assign(document.createElement("input"), { value: value.replace(/^"|"$/g, ""), placeholder: "value" });
  val.style.flex = "1";
  const flag = Object.assign(document.createElement("input"), { type: "checkbox", checked: unreadable, title: "unreadable" });
  row.append(key, val, flag, document.createTextNode("unreadable"));
  $("fields").append(row);
}

function draw() {
  const canvas = $("canvas");
  const maxWidth = $("canvas-wrap").clientWidth - 20;
  state.scale = Math.min(1, maxWidth / state.image.width);
  canvas.width = state.image.width * state.scale;
  canvas.height = state.image.height * state.scale;
  const ctx = canvas.getContext("2d");
  ctx.drawImage(state.image, 0, 0, canvas.width, canvas.height);
  ctx.lineWidth = 2;
  ctx.font = "13px Segoe UI";
  for (const item of state.boxes) {
    const [x1, y1, x2, y2] = item.box.map((v) => v * state.scale);
    ctx.strokeStyle = "#e11d48";
    ctx.strokeRect(x1, y1, x2 - x1, y2 - y1);
    ctx.fillStyle = "#e11d48";
    ctx.fillText(item.label, x1 + 3, Math.max(y1 - 4, 12));
  }
  if (state.drag) {
    ctx.strokeStyle = "#2563eb";
    const { x, y, w, h } = state.drag;
    ctx.strokeRect(x, y, w, h);
  }
  const list = $("boxes");
  list.replaceChildren(...state.boxes.map((item, i) => {
    const li = document.createElement("li");
    li.textContent = `${item.label}: [${item.box.map((v) => Math.round(v)).join(", ")}] ✕`;
    li.style.cursor = "pointer";
    li.addEventListener("click", () => { state.boxes.splice(i, 1); draw(); });
    return li;
  }));
}

function collect() {
  const fields = {}, unreadable = [];
  for (const row of $("fields").children) {
    const [key, val, flag] = row.querySelectorAll("input");
    if (!key.value.trim()) continue;
    if (flag.checked) unreadable.push(key.value.trim()); else fields[key.value.trim()] = val.value;
  }
  return { fields, unreadable, regions: state.boxes.map((b) => ({ label: b.label, page: 1, box: b.box })), sensitive: $("sensitive").checked };
}

async function save() {
  const sample = state.samples[state.index];
  const body = collect();
  const response = await fetch(`/api/labels/${encodeURIComponent(sample.name)}`, {
    method: "POST", credentials: "same-origin", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  $("status").textContent = response.ok ? `Saved ${sample.name}` : "Save failed";
  if (response.ok) sample.label = { ...body, verified: true };
}

function bind() {
  const canvas = $("canvas");
  canvas.addEventListener("mousedown", (e) => { state.drag = { x0: e.offsetX, y0: e.offsetY, x: e.offsetX, y: e.offsetY, w: 0, h: 0 }; });
  canvas.addEventListener("mousemove", (e) => {
    if (!state.drag) return;
    const d = state.drag;
    d.x = Math.min(d.x0, e.offsetX); d.y = Math.min(d.y0, e.offsetY);
    d.w = Math.abs(e.offsetX - d.x0); d.h = Math.abs(e.offsetY - d.y0);
    draw();
  });
  canvas.addEventListener("mouseup", () => {
    const d = state.drag;
    state.drag = null;
    if (d && d.w > 4 && d.h > 4) {
      const s = state.scale;
      state.boxes.push({ label: $("box-label").value || "region", box: [d.x / s, d.y / s, (d.x + d.w) / s, (d.y + d.h) / s] });
    }
    draw();
  });
  $("prev").addEventListener("click", () => show(state.index - 1));
  $("next").addEventListener("click", () => show(state.index + 1));
  $("save").addEventListener("click", save);
  $("add-field").addEventListener("click", () => addFieldRow());
  document.addEventListener("keydown", (e) => { if (e.ctrlKey && e.key === "s") { e.preventDefault(); save(); } });
}

style();
bind();
load();

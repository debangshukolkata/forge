// The steps DebCraft took for each request (FC1, D-629), derived from the project's events by rule: no model call
// and nothing extra during a run. Consecutive tool calls of the same kind become one step ("Looked through the code"
// for ten greps and reads), a failed call hangs off its step as a side branch, and the reply closes the request.
// Pure functions of the event list, like the Run map's model, so a reopened project draws the same steps.
// It shows what was done, as it happens; it cannot show a plan in advance, because the model decides each step
// after seeing the last result.
import type { ForgeEvent } from "./types";

export type StepKind =
  | "skill" | "look" | "start" | "command" | "tests" | "call" | "signin" | "edit" | "database" | "ask" | "web" | "notes"
  | "helper" | "plan" | "other";

export interface Branch {
  seq: number;
  text: string; // "port 8000 busy" or "401 → signed in to dev"
  bad: boolean; // a failure (red); false for something DebCraft did by itself on the way
  fixed: boolean; // a later call of the same step worked
}

export interface Step {
  kind: StepKind;
  label: string;
  detail: string; // "code_map ×3, read_file ×4"
  seq: number; // the first call's event: a click goes there in the chat
  seconds: number;
  calls: number;
  running: boolean;
  branches: Branch[];
}

export interface Request {
  seq: number;
  text: string; // what the user asked
  steps: Step[];
  answer: { seq: number; text: string } | null;
  seconds: number;
}

const KIND: Record<string, StepKind> = {
  load_skill: "skill",
  read_file: "look", grep: "look", glob: "look", list_dir: "look", code_map: "look", code_outline: "look",
  find_definition: "look", find_references: "look", list_symbols: "look", knowledge_search: "look", view_image: "look",
  tool_search: "look",
  start_background: "start", read_background: "start", stop_background: "start", monitor: "start", show_app: "start",
  run_command: "command", python_run: "command",
  run_tests: "tests", verify: "tests",
  http_request: "call",
  app_login: "signin", app_token_status: "signin",
  edit_file: "edit", write_file: "edit", multi_edit: "edit", delete_file: "edit", move_file: "edit", temporary_edits: "edit",
  db_schema: "database", db_query: "database", scratch_exec: "database", db_copy_table: "database",
  use_scratch_database: "database", use_dev_database: "database", dev_db_write: "database", dev_db_undo: "database",
  ask_user: "ask", request_user_action: "ask", request_app_secret: "ask", request_app_keys: "ask", settings_file: "ask",
  web_search: "web", web_fetch: "web", tavily_research: "web", tavily_extract: "web", tavily_crawl: "web",
  knowledge_write: "notes", memory_write: "notes",
  spawn_subagent: "helper",
  task_update: "plan", propose_plan: "plan", propose_requirements: "plan", todo_write: "plan",
};

const LABEL: Record<StepKind, string> = {
  skill: "Loaded a skill",
  look: "Looked through the code",
  start: "Started the application",
  command: "Ran commands",
  tests: "Ran the tests",
  call: "Called the application",
  signin: "Signed in",
  edit: "Changed files",
  database: "Worked with the database",
  ask: "Asked you",
  web: "Searched the web",
  notes: "Wrote down what it learned",
  helper: "Asked a helper agent",
  plan: "Updated the plan",
  other: "Other work",
};

function clip(text: string, length: number): string {
  const flat = text.replace(/\s+/g, " ").trim();
  return flat.length > length ? `${flat.slice(0, length - 1)}…` : flat;
}

/** `POST /api/agents/ops/run` from an http_request summary (`POST http://host:port/path (token from X)`). */
export function callTarget(summary: string): string {
  const [method, url] = summary.split(" ");
  if (!url || !/^https?:/.test(url)) return clip(summary, 60);
  return `${method} ${url.replace(/^https?:\/\/[^/]+/, "").split("?")[0] || "/"}`;
}

function failureText(name: string, preview: string): string {
  const status = /HTTP (\d{3})/.exec(preview);
  if (name === "http_request" && status) return `HTTP ${status[1]}`;
  const line = preview.split("\n").map((part) => part.trim()).find((part) => part.length > 0) ?? "failed";
  return clip(line, 70);
}

interface Open {
  step: Step;
  tools: Map<string, number>;
  key: string; // calls with the same key join the step
  started: Map<string, number>; // call id -> seq, for calls still running
}

function finishDetail(open: Open): void {
  const parts = [...open.tools.entries()].map(([tool, count]) => (count > 1 ? `${tool} ×${count}` : tool));
  if (open.step.kind !== "call" && open.step.kind !== "skill") open.step.detail = parts.join(", ");
  open.step.running = open.started.size > 0;
}

export function buildSteps(events: ForgeEvent[]): Request[] {
  const requests: Request[] = [];
  let current: Request | null = null;
  let open: Open | null = null;
  const names = new Map<string, { name: string; summary: string; seq: number }>();

  const close = () => {
    if (open) finishDetail(open);
    open = null;
  };
  const request = (seq: number, text: string): Request => {
    close();
    const made: Request = { seq, text, steps: [], answer: null, seconds: 0 };
    requests.push(made);
    return made;
  };

  for (const event of events) {
    const payload = event.payload;
    if (event.type === "user_message") {
      current = request(event.seq, String(payload.text ?? ""));
    } else if (event.type === "tool_call_started") {
      current ??= request(event.seq, "");
      const name = String(payload.name ?? "");
      const summary = String(payload.summary ?? name);
      names.set(String(payload.id), { name, summary, seq: event.seq });
      const kind = KIND[name] ?? "other";
      // Each endpoint and each skill is its own step; other kinds join while the kind stays the same.
      const key = kind === "call" ? `call ${callTarget(summary)}` : kind === "skill" ? `skill ${summary}` : kind === "other" ? `other ${name}` : kind;
      if (!open || open.key !== key) {
        close();
        const label =
          kind === "call" ? `Called ${callTarget(summary)}`
          : kind === "skill" ? clip(`Loaded the skill ${String(payload.arguments?.name ?? "")}`.trim(), 60)
          : kind === "other" ? clip(summary, 60)
          : LABEL[kind];
        const step: Step = { kind, label, detail: "", seq: event.seq, seconds: 0, calls: 0, running: true, branches: [] };
        current.steps.push(step);
        open = { step, tools: new Map(), key, started: new Map() };
      }
      open.step.calls += 1;
      open.tools.set(name, (open.tools.get(name) ?? 0) + 1);
      open.started.set(String(payload.id), event.seq);
      current.answer = null; // work after a reply: the reply was not the last word
    } else if (event.type === "tool_call_finished") {
      const begun = names.get(String(payload.id));
      const target: Step | undefined = stepOf(current, begun?.seq) ?? open?.step;
      if (!target || !current) continue;
      const seconds = Number(payload.duration_s ?? 0);
      target.seconds += seconds;
      current.seconds += seconds;
      const preview = String(payload.preview ?? "");
      const name = String(payload.name ?? begun?.name ?? "");
      const status = /HTTP (\d{3})/.exec(preview);
      const refused = name === "http_request" && status !== null && Number(status[1]) >= 400;
      if (payload.ok === false || refused) {
        target.branches.push({ seq: event.seq, text: failureText(name, preview), bad: true, fixed: false });
      } else {
        for (const branch of target.branches) if (branch.bad) branch.fixed = true;
        const signed = /DebCraft signed in to (\S+)/.exec(preview);
        if (signed) target.branches.push({ seq: event.seq, text: `401 → signed in to ${signed[1]}`, bad: false, fixed: true });
        else if (preview.includes("signed in again")) target.branches.push({ seq: event.seq, text: "token ended → signed in again", bad: false, fixed: true });
      }
      if (open && open.step === target) {
        open.started.delete(String(payload.id));
        finishDetail(open);
      } else {
        target.running = false;
      }
    } else if (event.type === "message_done" && current) {
      const text = String(payload.text ?? "").trim();
      if (text) {
        close();
        current.answer = { seq: event.seq, text: clip(text, 110) };
      }
    }
  }
  close();
  return requests;
}

/** The step of the request that a call started at `seq` belongs to: the last step that began at or before it. */
function stepOf(request: Request | null, seq: number | undefined): Step | undefined {
  if (!request || seq === undefined) return undefined;
  let found: Step | undefined;
  for (const step of request.steps) if (step.seq <= seq) found = step;
  return found;
}

export function took(seconds: number): string {
  if (seconds < 1) return "";
  if (seconds < 90) return `${Math.round(seconds)} s`;
  return `${Math.round(seconds / 60)} min`;
}

// Plain-language descriptions of what Forge is doing, from its events (tool names, phases). No invented
// percentages: progress bars only show real counts (phases, tasks); everything else is an animated indicator.

export type ActivityKind = "idle" | "thinking" | "tool" | "writing" | "waiting";
export type LoaderStyle = "ring" | "dots" | "scan" | "type" | "pulse" | "tests" | "globe";

export interface Activity {
  kind: ActivityKind;
  label: string; // "Running tests"
  detail?: string; // "tests/test_masking.py"
  loader: LoaderStyle;
  since: number; // ms timestamp, for the elapsed timer
}

interface ToolWords {
  label: string;
  loader: LoaderStyle;
}

const TOOLS: Record<string, ToolWords> = {
  read_file: { label: "Reading", loader: "scan" },
  list_dir: { label: "Looking through", loader: "scan" },
  glob: { label: "Finding files", loader: "scan" },
  grep: { label: "Searching the code", loader: "scan" },
  kb_search: { label: "Searching the knowledge base", loader: "scan" },
  kb_read: { label: "Reading the knowledge base", loader: "scan" },
  profile_read: { label: "Reading the project profile", loader: "scan" },
  profile_search: { label: "Searching the project profile", loader: "scan" },
  library_search: { label: "Checking earlier requirements", loader: "scan" },
  write_file: { label: "Writing", loader: "type" },
  edit_file: { label: "Editing", loader: "type" },
  multi_edit: { label: "Editing", loader: "type" },
  delete_file: { label: "Deleting", loader: "ring" },
  move_file: { label: "Moving", loader: "ring" },
  notebook_edit_cell: { label: "Editing the notebook", loader: "type" },
  run_tests: { label: "Running tests", loader: "tests" },
  verify: { label: "Verifying (compile, lint, tests)", loader: "tests" },
  run_eval: { label: "Measuring accuracy on the eval set", loader: "tests" },
  run_command: { label: "Running a command", loader: "ring" },
  python_run: { label: "Running Python", loader: "ring" },
  start_background: { label: "Starting the app", loader: "ring" },
  http_request: { label: "Calling the app", loader: "ring" },
  web_search: { label: "Searching the web", loader: "globe" },
  web_fetch: { label: "Reading a web page", loader: "globe" },
  browser_open: { label: "Opening the app in a browser", loader: "globe" },
  view_image: { label: "Looking at an image", loader: "scan" },
  pdf_render: { label: "Rendering the PDF", loader: "ring" },
  db_schema: { label: "Reading the database structure", loader: "scan" },
  db_query: { label: "Querying the database", loader: "ring" },
  scratch_exec: { label: "Running SQL in the scratch schema", loader: "ring" },
  propose_requirements: { label: "Writing the requirements", loader: "type" },
  propose_plan: { label: "Writing the plan", loader: "type" },
  task_update: { label: "Updating the task list", loader: "ring" },
  spawn_subagent: { label: "Asking a helper agent", loader: "dots" },
  modeb_document: { label: "Writing the integration notes", loader: "type" },
  assumption_add: { label: "Recording an assumption", loader: "type" },
};

export function toolActivity(name: string, summary: string): Pick<Activity, "label" | "detail" | "loader"> {
  const words = TOOLS[name];
  if (!words) return { label: humanise(name), detail: summary, loader: "ring" };
  // The summary usually starts with the verb and names the target ("run tests tests/x.py"): keep the target.
  const target = summary.replace(/^(read|write|edit|list|glob|grep|run tests|verify|delete|move|web search:|fetch)\s*/i, "");
  return { label: words.label, detail: target || undefined, loader: words.loader };
}

const PHASE_THINKING: Record<string, string> = {
  intake: "Reading your request",
  clarify: "Understanding the requirement",
  kb_check: "Checking what Forge knows about this code",
  explore: "Exploring the code",
  plan: "Planning the tasks",
  execute: "Working on the task",
  review: "Reviewing the change",
  export: "Preparing the output",
  restructure: "Restructuring the code",
  handoff: "Preparing the hand-over",
  direct: "Thinking",
};

export function thinkingLabel(phase: string | undefined, taskTitle?: string): string {
  if (phase === "execute" && taskTitle) return `Working on: ${taskTitle}`;
  return PHASE_THINKING[phase ?? "direct"] ?? "Thinking";
}

export function elapsed(since: number, now: number): string {
  const seconds = Math.max(0, Math.floor((now - since) / 1000));
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const s = seconds % 60;
  return h ? `${h}h ${String(m).padStart(2, "0")}m` : `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

function humanise(name: string): string {
  const words = name.replace(/^mcp__[^_]+__/, "").replace(/_/g, " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

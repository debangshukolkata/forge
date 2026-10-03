// Shapes of the Forge web API and event stream (src/forge/web/server.py, engine/events.py, engine/inputs.py).

export interface WorkspaceSummary {
  path: string;
  name: string;
  mode: "A" | "B";
  repo: string;
}

export interface Task {
  id: string;
  title: string;
  depends_on?: string[];
  status: "pending" | "in_progress" | "done" | "blocked" | "skipped" | string;
  attempts?: number;
  blocked_reason?: string | null;
}

export interface DbRequest {
  id: string;
  title: string;
  status: string;
  purpose: string;
  target: string;
  who: string;
  sql: string;
  verification_query: string;
}

export interface RecentEntry {
  path: string;
  name: string;
  repo: string;
  app_folder?: string;
}

export interface AppState {
  workspace: WorkspaceSummary | null;
  phase?: string;
  busy?: boolean;
  pending?: string[];
  tasks?: Task[];
  current_task?: string | null;
  mode?: string | null;
  database?: string | null;
  db_requests?: DbRequest[];
  recent?: RecentEntry[];
}

export interface ForgeEvent {
  seq: number;
  type: string;
  ts: string;
  payload: Record<string, any>; // eslint-disable-line @typescript-eslint/no-explicit-any
  where?: { phase: string | null; task: string | null } | null; // phase/task when it happened (D-119)
}

export type ServerMessage =
  | { type: "hello"; controls: boolean; last_seq: number }
  | { type: "control"; controls: boolean }
  | { type: "rejected"; reason: string }
  | { type: "event"; event: ForgeEvent };

export type UserInput =
  | { kind: "send_message"; text: string }
  | { kind: "slash_command"; text: string }
  | { kind: "interrupt" }
  | { kind: "approve"; request_id: string; scope?: "once" | "prefix" }
  | { kind: "reject"; request_id: string; instruction?: string | null }
  | { kind: "answer"; question_id: string; choice?: string; text?: string | null };

export interface DoctorResult {
  name: string;
  status: "ok" | "warn" | "fail";
  detail: string;
}

/** GET /api/setup: which required env values are missing, so the app can decide whether to show the
 * guided first-run setup screen at all (D-145/D-146) before rendering anything else. */
export interface SetupStatus {
  missing: string[];
  config_error: string | null;
}

export interface ContextInfo {
  percent: number;
  fixed: number;
  pinned: number;
  history: number;
  free: number;
  usable: number;
  compactions: number;
}

export interface UsageBucket {
  input_tokens: number;
  output_tokens: number;
  cost_usd: number;
  calls: number;
}

export interface CostInfo {
  total_usd: number;
  budget_usd: number;
  calls: number;
  cost_by_role?: Record<string, number>;
  // Per project (all sessions): tokens and cost per phase and per task (D-118).
  project?: { total: UsageBucket; by_phase: Record<string, UsageBucket>; by_task: Record<string, UsageBucket> } | null;
}

export interface CostLimits {
  usd: [number, number];
  tokens: [number, number];
}

export interface CostColors {
  reply: CostLimits;
  task: CostLimits;
  phase: CostLimits;
}

/** One entry in the chat timeline, derived from events. */
export type ChatItem =
  | { key: string; kind: "user"; text: string }
  | { key: string; kind: "assistant"; text: string; streaming?: boolean; usage?: { input: number; output: number; cost: number } }
  | {
      key: string;
      kind: "tool";
      id: string;
      name: string;
      summary: string;
      args?: Record<string, unknown>; // the call's arguments (shown as the IN block)
      agent?: AgentView; // set on a spawn_subagent row (or a row made for a subagent): its own steps, nested
      state: "running" | "ok" | "fail";
      preview?: string;
      duration?: number;
      // True once a later call of the same tool succeeds before any other failure of that tool
      // intervenes: the model made a mistake, got a clear error, and immediately corrected it —
      // shown de-emphasised rather than as an alarming failure (see ToolCard in Chat.tsx).
      retried?: boolean;
    }
  | { key: string; kind: "notice"; noticeKind: string; text: string }
  | { key: string; kind: "error"; text: string }
  | { key: string; kind: "approval"; id: string; payload: Record<string, any> } // eslint-disable-line @typescript-eslint/no-explicit-any
  | { key: string; kind: "question"; id: string; payload: Record<string, any> } // eslint-disable-line @typescript-eslint/no-explicit-any
  | { key: string; kind: "action"; id: string; payload: Record<string, any> }; // eslint-disable-line @typescript-eslint/no-explicit-any

export interface AuthStatus {
  configured: boolean;
  signed_in: boolean;
  user: string | null;
}

export interface ProjectEntry {
  path: string;
  name: string;
  repo: string;
  mode: "A" | "B";
  app_folder: string | null;
  last_activity: string; // ISO time
  last_request: string; // what the user last asked for ("" if nothing yet)
}

export interface CheckInfo {
  id: string;
  label: string;
  optional: boolean;
  purpose: string;
}

export interface CheckResultView {
  id: string;
  status: "ok" | "warn" | "fail";
  detail: string;
  hint: string;
  models: Record<string, boolean>;
  checked_at?: string;
}

export interface ModelPlan {
  roles: { role: string; model: string | null; reason: string; default: string | null }[];
  options: { key: string; label: string; vision: boolean; usable: boolean }[];
  notes: string[];
}

export interface EnvironmentOverview {
  checks: CheckInfo[];
  saved: { results: Record<string, CheckResultView>; plan: Record<string, string>; confirmed_at: string | null };
  plan: ModelPlan;
}

export interface AgentStep {
  kind: "tool" | "thinking";
  name?: string;
  summary?: string;
  text?: string;
  state?: "running" | "ok" | "fail";
  duration?: number;
}

export interface AgentView {
  id: string;
  role: string;
  purpose: string;
  steps: AgentStep[];
  done?: { ok: boolean; tool_calls: number; failed_calls: number; duration_s: number };
}

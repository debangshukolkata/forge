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
      state: "running" | "ok" | "fail";
      preview?: string;
      duration?: number;
    }
  | { key: string; kind: "notice"; noticeKind: string; text: string }
  | { key: string; kind: "error"; text: string }
  | { key: string; kind: "approval"; id: string; payload: Record<string, any> } // eslint-disable-line @typescript-eslint/no-explicit-any
  | { key: string; kind: "question"; id: string; payload: Record<string, any> } // eslint-disable-line @typescript-eslint/no-explicit-any
  | { key: string; kind: "action"; id: string; payload: Record<string, any> }; // eslint-disable-line @typescript-eslint/no-explicit-any

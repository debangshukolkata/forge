// The connection to Forge: loads /api/state, keeps one WebSocket to the engine (replaying every event since the
// last one seen, so a reload or reconnect never loses anything) and turns events into the chat timeline.
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { agentFinished, agentStarted, agentStep } from "./agentTimeline";
import { api } from "./lib";
import type { AppState, ChatItem, ContextInfo, CostColors, CostInfo, ForgeEvent, ServerMessage, TodoItem, UserInput } from "./types";

interface Timeline {
  items: ChatItem[];
  answered: Record<string, string>; // card id -> how it was settled ("Approved", "superseded", …)
  todos: TodoItem[]; // Forge's own todo list, the whole list as of the last `todo_updated` (D-177)
}

type Action =
  | { type: "reset" }
  | { type: "event"; event: ForgeEvent }
  | { type: "local"; item: ChatItem }
  | { type: "answered"; id: string; label: string }
  | { type: "settle"; pending: string[] };

const initial: Timeline = { items: [], answered: {}, todos: [] };

function reducer(state: Timeline, action: Action): Timeline {
  switch (action.type) {
    case "reset":
      return initial;
    case "local":
      return { ...state, items: [...state.items, action.item] };
    case "answered":
      return { ...state, answered: { ...state.answered, [action.id]: action.label } };
    case "settle": {
      const pending = new Set(action.pending);
      const answered = { ...state.answered };
      for (const item of state.items) {
        if ((item.kind === "approval" || item.kind === "question" || item.kind === "action") && !pending.has(item.id)) {
          answered[item.id] ??= "answered earlier";
        }
      }
      return { ...state, answered };
    }
    case "event":
      return applyEvent(state, action.event);
  }
}

function applyEvent(state: Timeline, event: ForgeEvent): Timeline {
  const p = event.payload;
  const key = `e${event.seq}`;
  const items = state.items;
  const last = items[items.length - 1];
  switch (event.type) {
    case "user_message":
      return { ...state, items: [...items, { key, kind: "user", text: p.text }] };
    case "message_delta":
      if (last && last.kind === "assistant" && last.streaming) {
        return { ...state, items: [...items.slice(0, -1), { ...last, text: last.text + p.text }] };
      }
      return { ...state, items: [...items, { key, kind: "assistant", text: p.text, streaming: true }] };
    case "message_done": {
      const withoutStream = last && last.kind === "assistant" && last.streaming ? items.slice(0, -1) : items;
      if (!p.text || !String(p.text).trim()) return { ...state, items: withoutStream };
      const usage = p.usage
        ? { input: p.usage.input_tokens ?? 0, output: p.usage.output_tokens ?? 0, cost: p.cost_usd ?? 0 }
        : undefined;
      return { ...state, items: [...withoutStream, { key, kind: "assistant", text: p.text, usage }] };
    }
    case "tool_call_started":
      return {
        ...state,
        items: [...endStream(items), { key, kind: "tool", id: p.id, name: p.name, summary: p.summary || "", args: p.arguments, state: "running" }],
      };
    case "tool_call_finished": {
      const updated: ChatItem[] = items.map((item) =>
        item.kind === "tool" && item.id === p.id
          ? { ...item, state: (p.ok ? "ok" : "fail") as "ok" | "fail", preview: p.preview, duration: p.duration_s, outputId: p.output_id, outputChars: p.output_chars }
          : item,
      );
      // A success right after a same-tool failure usually means the model mis-called it, got a
      // clear error, and immediately corrected itself — mark the nearest such failure as retried
      // so it renders de-emphasised instead of alarming (Chat.tsx's ToolCard).
      if (!p.ok) return { ...state, items: updated };
      for (let i = updated.length - 1; i >= 0; i--) {
        const item = updated[i];
        if (item.kind !== "tool" || item.name !== p.name || item.id === p.id) continue;
        if (item.state === "ok") break; // an earlier success of this tool already resolved any failure before it
        if (item.state === "fail" && !item.retried) updated[i] = { ...item, retried: true };
        break;
      }
      return { ...state, items: updated };
    }
    case "thinking_delta": {
      const text = String(p.text ?? "").trim();
      if (!text) return state;
      if (last && last.kind === "thinking") return { ...state, items: [...items.slice(0, -1), { ...last, text: `${last.text}\n\n${text}` }] };
      return { ...state, items: [...endStream(items), { key, kind: "thinking", text }] };
    }
    case "file_changed": {
      // Emitted by the edit while its tool call is still running: the diff belongs to that call.
      if (!p.diff) return state;
      let at = -1;
      for (let i = items.length - 1; i >= 0; i--) {
        const item = items[i];
        if (item.kind === "tool" && !item.agent && (item.state === "running" || at < 0)) {
          at = i;
          if (item.state === "running") break;
        }
      }
      if (at < 0) return state;
      return { ...state, items: items.map((item, i) => (i === at && item.kind === "tool" ? { ...item, diff: String(p.diff) } : item)) };
    }
    case "todo_updated":
      return { ...state, todos: Array.isArray(p.items) ? p.items : [] };
    case "agent_started":
      return { ...state, items: agentStarted(endStream(items), key, p) };
    case "subagent_step":
      return { ...state, items: agentStep(items, p) };
    case "agent_finished":
      return { ...state, items: agentFinished(items, p) };
    case "approval_requested":
    case "question_asked":
    case "user_action_requested": {
      const kind = event.type === "approval_requested" ? "approval" : event.type === "question_asked" ? "question" : "action";
      // A new card for the same id replaces the old one (the latest request wins).
      const kept = items.filter((item) => !(item.kind === kind && "id" in item && item.id === p.id));
      return { ...state, items: [...endStream(kept), { key, kind, id: p.id, payload: p } as ChatItem] };
    }
    case "notice":
      if (p.kind === "usage") return state; // shown as cost/usage, not as a chat line
      return { ...state, items: [...items, { key, kind: "notice", noticeKind: p.kind || "", text: p.text || p.kind || "" }] };
    case "error":
      return { ...state, items: [...items, { key, kind: "error", text: p.message || "Error" }] };
    default:
      return state;
  }
}

function endStream(items: ChatItem[]): ChatItem[] {
  const last = items[items.length - 1];
  return last && last.kind === "assistant" && last.streaming ? [...items.slice(0, -1), { ...last, streaming: false }] : items;
}

/** What Forge is doing right now (labels are derived in the UI from the tool name and phase). */
export interface LiveActivity {
  kind: "idle" | "thinking" | "tool" | "writing" | "waiting";
  tool?: { name: string; summary: string };
  waitingFor?: string;
  since: number;
}

export interface Forge {
  state: AppState;
  timeline: Timeline;
  connected: boolean;
  controls: boolean;
  replaying: boolean;
  waiting: string | null;
  context: ContextInfo | null;
  cost: CostInfo | null;
  changeTick: number; // increments on file/task changes so panels can refresh
  costColors: CostColors | null; // green / yellow / red limits from Forge's config (cost.colors)
  events: ForgeEvent[]; // every event of the project (replayed + live), for the Run map
  activity: LiveActivity;
  runStartedAt: number | null; // when the current stretch of work began (for the elapsed timer)
  reload: () => Promise<AppState>;
  send: (input: UserInput) => void;
  command: (text: string) => void;
  answer: (id: string, input: UserInput, label: string) => void;
  takeControl: () => void;
  openWorkspace: (path: string) => Promise<void>;
  enter: () => Promise<void>; // after a project was created (the server already opened it)
}

export function useForge(): Forge {
  const [state, setState] = useState<AppState>({ workspace: null });
  const [timeline, dispatch] = useReducer(reducer, initial);
  const [connected, setConnected] = useState(false);
  const [controls, setControls] = useState(true);
  const [replaying, setReplaying] = useState(false);
  const [waiting, setWaiting] = useState<string | null>(null);
  const [context, setContext] = useState<ContextInfo | null>(null);
  const [cost, setCost] = useState<CostInfo | null>(null);
  const [changeTick, setChangeTick] = useState(0);
  const [activity, setActivity] = useState<LiveActivity>({ kind: "idle", since: Date.now() });
  const [runStartedAt, setRunStartedAt] = useState<number | null>(null);
  const [costColors, setCostColors] = useState<CostColors | null>(null);
  const [events, setEvents] = useState<ForgeEvent[]>([]);

  useEffect(() => {
    api<{ cost_colors?: CostColors }>("/api/config")
      .then((config) => setCostColors(config.cost_colors ?? null))
      .catch(() => setCostColors(null));
  }, [state.workspace?.path]);
  const socketRef = useRef<WebSocket | null>(null);
  const lastSeq = useRef(0);
  const replayUntil = useRef(0);
  const replayingRef = useRef(false);
  const retry = useRef(500);
  const workspacePath = useRef<string | null>(null);

  const reload = useCallback(async () => {
    const next = await api<AppState>("/api/state");
    setState(next);
    workspacePath.current = next.workspace?.path ?? null;
    return next;
  }, []);

  const bump = () => setChangeTick((n) => n + 1);

  const finishReplay = useCallback(async () => {
    replayingRef.current = false;
    setReplaying(false);
    const next = await reload();
    // After a reload the true start times are unknown: count from now.
    const now = Date.now();
    setActivity(next.busy ? { kind: "thinking", since: now } : { kind: "idle", since: now });
    setRunStartedAt(next.busy ? now : null);
    dispatch({ type: "settle", pending: next.pending || [] });
    bump();
  }, [reload]);

  const onEvent = useCallback(
    (event: ForgeEvent) => {
      dispatch({ type: "event", event });
      setEvents((list) => [...list, event]);
      const p = event.payload;
      const live = !replayingRef.current;
      if (live) trackActivity(event.type, p);
      switch (event.type) {
        case "status_changed":
          setState((s) => ({ ...s, busy: p.state === "working" }));
          if (p.state === "working") setWaiting(null);
          if (p.state === "idle" && live) void reload().then(bump);
          break;
        case "context_updated":
          setContext(p as ContextInfo);
          break;
        case "cost_updated":
          setCost(p as CostInfo);
          break;
        case "notice":
          // Every model call reports its usage with the updated summary: cost moves live, not per turn.
          if (p.kind === "usage" && p.summary) setCost(p.summary as CostInfo);
          break;
        case "approval_requested":
        case "question_asked":
        case "user_action_requested":
          if (live) {
            const title =
              event.type === "approval_requested" ? "Approval needed" : event.type === "question_asked" ? "Forge has a question" : "A step for you";
            setWaiting(title);
            if (document.hidden && "Notification" in window && Notification.permission === "granted") {
              new Notification("Forge", { body: title });
            }
          }
          break;
        case "task_list_updated":
          // Phase and tasks arrive with the event: show them at once, then refresh the rest.
          setState((s) => ({ ...s, phase: p.phase ?? s.phase, current_task: p.current_task ?? null, tasks: p.tasks ?? s.tasks }));
          if (live) void reload().then(bump);
          break;
        case "db_request_created":
        case "db_request_updated":
          if (live) void reload().then(bump);
          break;
        case "file_changed":
        case "eval_report_ready":
          if (live) bump();
          break;
        default:
          break;
      }
    },
    [reload],
  );

  function trackActivity(type: string, p: Record<string, any>) { // eslint-disable-line @typescript-eslint/no-explicit-any
    const now = Date.now();
    switch (type) {
      case "status_changed":
        if (p.state === "working") {
          setRunStartedAt((started) => started ?? now);
          setActivity((a) => (a.kind === "idle" ? { kind: "thinking", since: now } : a));
        } else {
          setRunStartedAt(null);
          setActivity({ kind: "idle", since: now });
        }
        break;
      case "tool_call_started":
        setActivity({ kind: "tool", tool: { name: p.name, summary: p.summary || "" }, since: now });
        break;
      case "tool_call_finished":
      case "message_done":
        setActivity((a) => (a.kind === "idle" || a.kind === "waiting" ? a : { kind: "thinking", since: now }));
        break;
      case "message_delta":
        setActivity((a) => (a.kind === "writing" ? a : { kind: "writing", since: now }));
        break;
      case "approval_requested":
      case "question_asked":
      case "user_action_requested":
        setActivity({ kind: "waiting", waitingFor: type === "approval_requested" ? "your approval" : type === "question_asked" ? "your answer" : "a step from you", since: now });
        break;
      default:
        break;
    }
  }

  const connect = useCallback(() => {
    socketRef.current?.close();
    const socket = new WebSocket(`${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`);
    socketRef.current = socket;
    socket.onopen = () => {
      retry.current = 500;
      setConnected(true);
      replayingRef.current = lastSeq.current === 0;
      setReplaying(replayingRef.current);
      socket.send(JSON.stringify({ type: "hello", since: lastSeq.current }));
    };
    socket.onmessage = (message) => {
      const data = JSON.parse(message.data) as ServerMessage;
      if (data.type === "hello") {
        setControls(data.controls);
        replayUntil.current = data.last_seq;
        if (lastSeq.current >= data.last_seq) void finishReplay();
        return;
      }
      if (data.type === "control") return setControls(data.controls);
      if (data.type === "rejected") return dispatch({ type: "local", item: { key: `r${Date.now()}`, kind: "error", text: data.reason } });
      if (data.type !== "event" || data.event.seq <= lastSeq.current) return;
      lastSeq.current = data.event.seq;
      onEvent(data.event);
      if (replayingRef.current && data.event.seq >= replayUntil.current) void finishReplay();
    };
    socket.onclose = () => {
      if (socketRef.current !== socket) return;
      setConnected(false);
      window.setTimeout(() => workspacePath.current && connect(), retry.current);
      retry.current = Math.min(retry.current * 2, 8000);
    };
  }, [finishReplay, onEvent]);

  const startSession = useCallback(() => {
    dispatch({ type: "reset" });
    setEvents([]);
    lastSeq.current = 0;
    setContext(null);
    setCost(null);
    setWaiting(null);
    connect();
  }, [connect]);

  useEffect(() => {
    void reload().then((s) => {
      if (s.workspace) startSession();
    });
    return () => {
      const socket = socketRef.current;
      socketRef.current = null;
      socket?.close();
    };
  }, [reload, startSession]);

  const send = useCallback((input: UserInput) => {
    const socket = socketRef.current;
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      dispatch({ type: "local", item: { key: `x${Date.now()}`, kind: "error", text: "Not connected to Forge; reconnecting…" } });
      return;
    }
    socket.send(JSON.stringify({ type: "input", input }));
  }, []);

  const command = useCallback(
    (text: string) => {
      // Slash commands aren't events, so echo them locally to keep the conversation readable.
      dispatch({ type: "local", item: { key: `c${Date.now()}`, kind: "user", text } });
      send({ kind: "slash_command", text });
    },
    [send],
  );

  const answer = useCallback(
    (id: string, input: UserInput, label: string) => {
      send(input);
      dispatch({ type: "answered", id, label });
      setWaiting(null);
      setActivity({ kind: "thinking", since: Date.now() });
    },
    [send],
  );

  const takeControl = useCallback(() => socketRef.current?.send(JSON.stringify({ type: "take_control" })), []);

  const openWorkspace = useCallback(
    async (path: string) => {
      await api("/api/open", { method: "POST", body: { workspace: path } });
      await reload();
      startSession();
    },
    [reload, startSession],
  );

  const enter = useCallback(async () => {
    await reload();
    startSession();
  }, [reload, startSession]);

  return {
    state, timeline, connected, controls, replaying, waiting, context, cost, changeTick, activity, runStartedAt, costColors, events,
    reload, send, command, answer, takeControl, openWorkspace, enter,
  };
}

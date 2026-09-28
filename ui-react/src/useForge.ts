// The connection to Forge: loads /api/state, keeps one WebSocket to the engine (replaying every event since the
// last one seen, so a reload or reconnect never loses anything) and turns events into the chat timeline.
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { api } from "./lib";
import type { AppState, ChatItem, ContextInfo, CostInfo, ForgeEvent, ServerMessage, UserInput } from "./types";

interface Timeline {
  items: ChatItem[];
  answered: Record<string, string>; // card id -> how it was settled ("Approved", "superseded", …)
}

type Action =
  | { type: "reset" }
  | { type: "event"; event: ForgeEvent }
  | { type: "local"; item: ChatItem }
  | { type: "answered"; id: string; label: string }
  | { type: "settle"; pending: string[] };

const initial: Timeline = { items: [], answered: {} };

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
      return { ...state, items: [...withoutStream, { key, kind: "assistant", text: p.text }] };
    }
    case "tool_call_started":
      return {
        ...state,
        items: [...endStream(items), { key, kind: "tool", id: p.id, name: p.name, summary: p.summary || "", state: "running" }],
      };
    case "tool_call_finished":
      return {
        ...state,
        items: items.map((item) =>
          item.kind === "tool" && item.id === p.id
            ? { ...item, state: p.ok ? "ok" : "fail", preview: p.preview, duration: p.duration_s }
            : item,
        ),
      };
    case "approval_requested":
    case "question_asked":
    case "user_action_requested": {
      const kind = event.type === "approval_requested" ? "approval" : event.type === "question_asked" ? "question" : "action";
      // A new card for the same id replaces the old one (the latest request wins).
      const kept = items.filter((item) => !(item.kind === kind && "id" in item && item.id === p.id));
      return { ...state, items: [...endStream(kept), { key, kind, id: p.id, payload: p } as ChatItem] };
    }
    case "notice":
      if (p.kind === "usage") return state;
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

export interface Forge {
  state: AppState;
  timeline: Timeline;
  connected: boolean;
  controls: boolean;
  replaying: boolean;
  waiting: string | null;
  context: ContextInfo | null;
  cost: CostInfo | null;
  changeTick: number; // increments on file/task/learning changes so panels can refresh
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
    dispatch({ type: "settle", pending: next.pending || [] });
    bump();
  }, [reload]);

  const onEvent = useCallback(
    (event: ForgeEvent) => {
      dispatch({ type: "event", event });
      const p = event.payload;
      const live = !replayingRef.current;
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
        case "db_request_created":
        case "db_request_updated":
          if (live) void reload().then(bump);
          break;
        case "file_changed":
        case "lesson_proposed":
        case "improvement_proposed":
          if (live) bump();
          break;
        default:
          break;
      }
    },
    [reload],
  );

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

  const command = useCallback((text: string) => send({ kind: "slash_command", text }), [send]);

  const answer = useCallback(
    (id: string, input: UserInput, label: string) => {
      send(input);
      dispatch({ type: "answered", id, label });
      setWaiting(null);
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
    state, timeline, connected, controls, replaying, waiting, context, cost, changeTick,
    reload, send, command, answer, takeControl, openWorkspace, enter,
  };
}

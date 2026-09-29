// The Run map (D-119/D-133): the plan and its helper agents as a single live-growing DAG (React Flow + dagre),
// built incrementally from the project's events rather than a fixed phase skeleton — nodes appear only once
// what they represent has actually happened. Everything is derived from the events, so it works the same live
// and after a replay. Failure/stuck markers live on their task/agent node as a badge. Clicking a task jumps to
// it in the chat.
import dagre from "@dagrejs/dagre";
import {
  Background,
  ControlButton,
  Controls,
  Handle,
  Position,
  ReactFlow,
  useReactFlow,
  type Edge,
  type Node,
  type NodeProps,
  type OnMoveStart,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AlertTriangle, Bot, ChevronRight, CheckCircle2, CircleDashed, Crosshair, Flag, Hand, ListChecks, Repeat, XCircle } from "lucide-react";
import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { cx } from "../lib";
import { buildGraph, buildRunModel, type GraphNodeData, type RunModel } from "../runmap";
import type { CostLimits, UsageBucket } from "../types";
import type { Forge } from "../useForge";
import { UsageBadge } from "../usage";
import { FailureDrawer, type DrawerRequest } from "./FailureDrawer";
import { Badge, Empty } from "./ui";

const TASK_W = 212;
const TASK_H = 118;
const STEP_W = 108;
const STEP_H = 44;
const AGENT_W = 176;
const AGENT_H = 64;

type FlowData = GraphNodeData & {
  usage?: UsageBucket;
  limits?: CostLimits;
  onJump?: () => void;
  onFailures?: () => void;
} & Record<string, unknown>;
type OpenFailures = (request: DrawerRequest) => void;
type FlowNode = Node<FlowData>;

export function RunMap({ forge, onJump }: { forge: Forge; onJump: (seq: number) => void }) {
  const busy = !!forge.state.busy || forge.activity.kind !== "idle";
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setNow(Date.now()), 2000);
    return () => window.clearInterval(timer);
  }, [busy]);

  const [drawer, setDrawer] = useState<DrawerRequest | null>(null);
  const closeDrawer = useCallback(() => setDrawer(null), []);
  const model = useMemo(
    () => buildRunModel(forge.events, forge.state.tasks ?? [], busy ? now : null),
    [forge.events, forge.state.tasks, busy, now],
  );

  if (model.tasks.length === 0 && model.start === null) {
    return (
      <div className="flex flex-1 items-center justify-center p-8">
        <Empty icon={<ListChecks className="h-8 w-8" aria-hidden />} title="Nothing to map yet">
          Once Forge plans the work, the tasks, helper agents and any failures appear here.
        </Empty>
      </div>
    );
  }
  return (
    <div className="flex min-h-0 flex-1 flex-col" data-testid="run-map">
      <Summary
        model={model}
        waiting={forge.activity.kind === "waiting" ? forge.waiting ?? "Waiting for you" : null}
        onFailures={() => setDrawer({ task: null, highlight: null })}
        onOpenRequest={() => onJump(model.waitingSince ?? Number.MAX_SAFE_INTEGER)}
      />
      <div className="min-h-[220px] flex-1">
        <TaskGraph model={model} forge={forge} onJump={onJump} onFailures={setDrawer} />
      </div>
      {drawer && (
        <FailureDrawer failures={model.failures} tasks={model.tasks} request={drawer} onClose={closeDrawer} onJump={onJump} />
      )}
    </div>
  );
}

function Summary({
  model,
  waiting,
  onFailures,
  onOpenRequest,
}: {
  model: RunModel;
  waiting: string | null;
  onFailures: () => void;
  onOpenRequest: () => void;
}) {
  const done = model.tasks.filter((t) => t.status === "done").length;
  const blocked = model.tasks.filter((t) => t.status === "blocked").length;
  const failures = model.failures.length;
  const stuck = Object.values(model.stats).reduce((sum, s) => sum + s.stuck, 0);
  const running = model.agents.filter((a) => a.end === null).length;
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 text-[12.5px]">
      {waiting && (
        <button
          type="button"
          onClick={onOpenRequest}
          data-testid="run-map-waiting"
          className="inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-warn/50 bg-warn-soft px-2.5 py-0.5 text-[12px] font-medium text-warn transition-[filter] duration-150 hover:brightness-95"
        >
          <Hand className="run-live h-3.5 w-3.5" aria-hidden />
          {waiting} — open in chat
          <ChevronRight className="h-3 w-3" aria-hidden />
        </button>
      )}
      <Badge tone="neutral">
        <ListChecks className="h-3.5 w-3.5" aria-hidden /> {done}/{model.tasks.length} tasks done
      </Badge>
      {blocked > 0 && <Badge tone="danger">{blocked} blocked</Badge>}
      {failures ? (
        <button
          type="button"
          onClick={onFailures}
          title="See what failed"
          className="cursor-pointer rounded-full transition-[filter] duration-150 hover:brightness-95 focus-visible:outline-2 focus-visible:outline-danger"
        >
          <Badge tone="danger">
            <XCircle className="h-3.5 w-3.5" aria-hidden /> {failures} failed call{failures === 1 ? "" : "s"}
            <ChevronRight className="h-3 w-3" aria-hidden />
          </Badge>
        </button>
      ) : (
        <Badge tone="neutral">
          <XCircle className="h-3.5 w-3.5" aria-hidden /> 0 failed calls
        </Badge>
      )}
      {stuck > 0 && (
        <Badge tone="warn">
          <AlertTriangle className="h-3.5 w-3.5" aria-hidden /> {stuck} stuck warning{stuck === 1 ? "" : "s"}
        </Badge>
      )}
      <Badge tone={running ? "accent" : "neutral"}>
        <Bot className="h-3.5 w-3.5" aria-hidden /> {model.agents.length} agent{model.agents.length === 1 ? "" : "s"}
        {running ? ` · ${running} running` : ""}
      </Badge>
    </div>
  );
}

// ---------------------------------------------------------------- task graph

function nodeSize(kind: GraphNodeData["kind"]): { width: number; height: number } {
  if (kind === "task") return { width: TASK_W, height: TASK_H };
  if (kind === "agent") return { width: AGENT_W, height: AGENT_H };
  return { width: STEP_W, height: STEP_H };
}

function nodeType(kind: GraphNodeData["kind"]): string {
  return kind === "task" ? "task" : kind === "agent" ? "agent" : "step";
}

function layout(
  model: RunModel,
  forge: Forge,
  onJump: (seq: number) => void,
  onFailures: OpenFailures,
): { nodes: FlowNode[]; edges: Edge[] } {
  const { nodes, edges } = buildGraph(model);
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", nodesep: 20, ranksep: 40, marginx: 16, marginy: 16 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) graph.setNode(node.id, nodeSize(node.data.kind));
  for (const edge of edges) graph.setEdge(edge.from, edge.to);
  dagre.layout(graph);

  const byTask = forge.cost?.project?.by_task ?? {};
  const flowNodes: FlowNode[] = nodes.map((node) => {
    const box = graph.node(node.id);
    const task = node.data.kind === "task";
    const firstSeq = node.data.kind === "task" ? node.data.stats?.firstSeq : node.data.kind === "agent" ? node.data.agent?.seq : undefined;
    return {
      id: node.id,
      type: nodeType(node.data.kind),
      position: { x: box.x - box.width / 2, y: box.y - box.height / 2 },
      data: {
        ...node.data,
        usage: task ? byTask[node.id] : undefined,
        limits: forge.costColors?.task,
        onJump: firstSeq != null ? () => onJump(firstSeq) : undefined,
        onFailures: task ? () => onFailures({ task: node.id, highlight: null }) : undefined,
      },
      draggable: false,
      connectable: false,
    };
  });
  const flowEdges: Edge[] = edges.map((edge) => ({
    id: `${edge.from}->${edge.to}`,
    source: edge.from,
    target: edge.to,
    type: "smoothstep",
    animated: edge.to === model.currentTask,
    className: `run-edge run-edge-${edge.kind}`,
  }));
  return { nodes: flowNodes, edges: flowEdges };
}

function TaskGraph({
  model,
  forge,
  onJump,
  onFailures,
}: {
  model: RunModel;
  forge: Forge;
  onJump: (seq: number) => void;
  onFailures: OpenFailures;
}) {
  const { nodes, edges } = useMemo(() => layout(model, forge, onJump, onFailures), [model, forge, onJump, onFailures]);
  const shape = nodes.map((n) => n.id).join("|");
  // D-133 milestone 2: auto-fit keeps re-centering the graph as it grows, but only until the user manually
  // pans or zooms — from then on their framing is theirs to keep, and only the Recenter control (or a new
  // manual fit) brings auto-fit back. `onMoveStart`'s event is null for a programmatic move (our own
  // `fitView` calls below) and a real MouseEvent/TouchEvent for a user drag or scroll/pinch, which is the
  // distinguishing signal `@xyflow/react` gives for "was this the user."
  const [autoFit, setAutoFit] = useState(true);
  const handleMoveStart = useCallback<OnMoveStart>((event) => {
    if (event) setAutoFit(false);
  }, []);
  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      fitView
      fitViewOptions={{ padding: 0.12, maxZoom: 1 }}
      minZoom={0.2}
      maxZoom={1.6}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      onMoveStart={handleMoveStart}
      proOptions={{ hideAttribution: true }}
    >
      <AutoFit shape={shape} enabled={autoFit} />
      <Background gap={20} size={1} />
      <Controls showInteractive={false} position="bottom-right">
        <ControlButton title="Recenter the map" aria-label="Recenter the map" onClick={() => setAutoFit(true)} data-testid="run-map-recenter">
          <Crosshair aria-hidden />
        </ControlButton>
      </Controls>
    </ReactFlow>
  );
}

/** Fits the plan into view whenever the plan's shape or the area's size changes (window, side panel) — but
 * only while `enabled` (auto-fit hasn't been switched off by a user pan or zoom, D-133 milestone 2). The
 * Recenter control (in `TaskGraph`) flips `enabled` back on, which both re-arms future auto-fits and —
 * because it changes a dependency of the effect below — fits immediately.
 * dagre (in `layout()`) already gives every node an explicit position before it ever mounts, so unlike
 * React Flow's own layout examples this doesn't need to wait on `useNodesInitialized()`'s DOM measurement
 * pass — that flag stayed permanently false in practice here (nodes are sized via inline `style`, not via
 * React Flow's own measured `width`/`height`), which silently prevented every fit. */
function AutoFit({ shape, enabled }: { shape: string; enabled: boolean }) {
  const { fitView } = useReactFlow();
  const [size, setSize] = useState("");
  useEffect(() => {
    const pane = document.querySelector(".react-flow");
    if (!pane) return;
    const observer = new ResizeObserver(([entry]) => setSize(`${Math.round(entry.contentRect.width)}x${Math.round(entry.contentRect.height)}`));
    observer.observe(pane);
    return () => observer.disconnect();
  }, []);
  useEffect(() => {
    if (enabled) void fitView({ padding: 0.12, maxZoom: 1, duration: 200 });
  }, [enabled, shape, size, fitView]);
  return null;
}

const STATUS_TONE: Record<string, "neutral" | "accent" | "danger" | "warn" | "info"> = {
  pending: "neutral", in_progress: "info", done: "accent", blocked: "danger", skipped: "warn",
};

const STATUS_BORDER: Record<string, string> = {
  pending: "border-border", in_progress: "border-info", done: "border-accent/60", blocked: "border-danger", skipped: "border-warn/60",
};

function TaskNode({ id, data }: NodeProps<FlowNode>) {
  const task = data.task!;
  const stats = data.stats;
  const fix = /^FIX/i.test(id);
  return (
    <div
      role="button"
      tabIndex={data.onJump ? 0 : -1}
      aria-disabled={!data.onJump}
      onClick={data.onJump}
      onKeyDown={(e) => {
        if ((e.key === "Enter" || e.key === " ") && e.target === e.currentTarget) {
          e.preventDefault();
          data.onJump?.();
        }
      }}
      data-task={id}
      data-status={task.status}
      title={data.onJump ? "Show this task in the chat" : undefined}
      style={{ width: TASK_W, height: TASK_H }}
      className={cx(
        "run-node-in flex flex-col gap-1 rounded-lg border bg-surface px-3 py-2 text-left shadow-sm transition-colors duration-150",
        STATUS_BORDER[task.status] ?? "border-border",
        data.current && "ring-2 ring-info/60",
        data.onJump ? "cursor-pointer hover:bg-raised" : "cursor-default",
      )}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <div className="flex items-center justify-between gap-2">
        <span className={cx("font-mono text-[11.5px]", fix ? "text-warn" : "text-fg-muted")}>{id}</span>
        <Badge tone={STATUS_TONE[task.status] ?? "neutral"}>
          {task.status === "in_progress" && <span className="run-live h-1.5 w-1.5 rounded-full bg-info" aria-hidden />}
          {task.status.replace("_", " ")}
        </Badge>
      </div>
      <div className="line-clamp-2 text-[12.5px] leading-snug font-medium text-fg">{task.title}</div>
      {task.status === "blocked" && task.blocked_reason && (
        <div className="truncate text-[11.5px] text-danger" title={task.blocked_reason}>
          Blocked: {task.blocked_reason}
        </div>
      )}
      {
        <div className="mt-auto flex items-center gap-2.5 text-[11.5px] text-fg-muted">
          {(task.attempts ?? 0) > 1 && (
            <Stat icon={<Repeat className="h-3 w-3" />} title="Attempts">{task.attempts}</Stat>
          )}
          {!!stats?.failures && (
            <button
              type="button"
              title="Failed tool calls"
              aria-label={`See the ${stats.failures} failed call${stats.failures === 1 ? "" : "s"} of ${id}`}
              onClick={(e) => {
                e.stopPropagation();
                data.onFailures?.();
              }}
              className="nodrag inline-flex cursor-pointer items-center gap-1 rounded px-1 tabular-nums text-danger hover:bg-danger-soft"
            >
              <XCircle className="h-3 w-3" aria-hidden />
              {stats.failures}
            </button>
          )}
          {!!stats?.stuck && (
            <Stat icon={<AlertTriangle className="h-3 w-3" />} title="Stuck warnings" className="text-warn">{stats.stuck}</Stat>
          )}
          {!!stats?.agents && (
            <Stat icon={<Bot className="h-3 w-3" />} title="Helper agents">{stats.agents}</Stat>
          )}
          {data.usage && <UsageBadge className="ml-auto" bucket={data.usage} limits={data.limits} compact />}
        </div>
      }
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}

function Stat({ icon, title, className, children }: { icon: ReactNode; title: string; className?: string; children: ReactNode }) {
  return (
    <span className={cx("inline-flex items-center gap-1 tabular-nums", className)} title={title}>
      {icon}
      {children}
    </span>
  );
}

const STEP_ICON: Partial<Record<GraphNodeData["kind"], ReactNode>> = {
  start: <ListChecks className="h-4 w-4" aria-hidden />,
  deliver: <Flag className="h-4 w-4" aria-hidden />,
};

function StepNode({ data }: NodeProps<FlowNode>) {
  const tone =
    data.state === "done" ? "border-accent/60 text-accent" : data.state === "active" ? "border-info text-info" : "border-border text-fg-muted";
  return (
    <div
      style={{ width: STEP_W, height: STEP_H }}
      data-step={data.kind}
      className={cx("run-node-in flex items-center justify-center gap-2 rounded-full border bg-raised text-[12.5px] font-medium", tone)}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      {data.state === "done" ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : data.state === "active" ? STEP_ICON[data.kind] : <CircleDashed className="h-4 w-4" aria-hidden />}
      {data.title}
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}

function AgentNode({ data }: NodeProps<FlowNode>) {
  const agent = data.agent!;
  const tone =
    data.state === "failed" ? "border-danger text-danger" : data.state === "active" ? "border-info text-info" : "border-border-strong text-fg-muted";
  return (
    <div
      role={data.onJump ? "button" : undefined}
      tabIndex={data.onJump ? 0 : -1}
      onClick={data.onJump}
      title={data.onJump ? "Show this helper agent in the chat" : undefined}
      data-agent={agent.role}
      data-status={data.state}
      style={{ width: AGENT_W, height: AGENT_H }}
      className={cx(
        "run-node-in flex flex-col justify-center gap-1 rounded-lg border border-dashed bg-raised/60 px-3 py-1.5 text-left shadow-sm",
        tone,
        data.onJump && "cursor-pointer hover:bg-raised",
      )}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      <div className="flex items-center gap-1.5 text-[11.5px] font-medium">
        <Bot className="h-3.5 w-3.5 shrink-0" aria-hidden />
        <span className="truncate capitalize">{agent.role}</span>
        {data.state === "failed" && <XCircle className="h-3.5 w-3.5 shrink-0 text-danger" aria-hidden />}
      </div>
      <div className="line-clamp-1 text-[11px] text-fg-muted">{agent.purpose || "Helper agent"}</div>
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}

const NODE_TYPES = { task: TaskNode, step: StepNode, agent: AgentNode };

// The Run map (D-119): the plan as a task graph (React Flow + dagre) above a timeline of phases, tasks and
// helper agents (plain SVG) with failure, stuck and waiting markers. Everything is derived from the project's
// events, so it works the same live and after a replay. Clicking a task or a marker jumps to it in the chat.
import dagre from "@dagrejs/dagre";
import { Background, Controls, Handle, Position, ReactFlow, type Edge, type Node, type NodeProps } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { AlertTriangle, Bot, CheckCircle2, CircleDashed, Flag, Hand, ListChecks, Repeat, Search, XCircle } from "lucide-react";
import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { cx } from "../lib";
import { PHASE_LABEL, buildRunModel, planGraph, type GraphNodeData, type Marker, type RunModel, type Span } from "../runmap";
import type { CostLimits, UsageBucket } from "../types";
import type { Forge } from "../useForge";
import { UsageBadge } from "../usage";
import { Badge, Empty } from "./ui";

const TASK_W = 212;
const TASK_H = 108;
const STEP_W = 108;
const STEP_H = 44;

type FlowData = GraphNodeData & { usage?: UsageBucket; limits?: CostLimits; onJump?: () => void } & Record<string, unknown>;
type FlowNode = Node<FlowData>;

export function RunMap({ forge, onJump }: { forge: Forge; onJump: (seq: number) => void }) {
  const busy = !!forge.state.busy;
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (!busy) return;
    const timer = window.setInterval(() => setNow(Date.now()), 2000);
    return () => window.clearInterval(timer);
  }, [busy]);

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
      <Summary model={model} />
      <div className="min-h-[220px] flex-[3] border-b border-border">
        {model.tasks.length ? (
          <TaskGraph model={model} forge={forge} onJump={onJump} />
        ) : (
          <div className="flex h-full items-center justify-center text-[13px] text-fg-muted">No plan yet — the timeline below shows what has happened so far.</div>
        )}
      </div>
      <div className="min-h-[160px] flex-[2] overflow-auto">
        <Timeline model={model} onJump={onJump} />
      </div>
    </div>
  );
}

function Summary({ model }: { model: RunModel }) {
  const done = model.tasks.filter((t) => t.status === "done").length;
  const blocked = model.tasks.filter((t) => t.status === "blocked").length;
  const failures = model.markers.filter((m) => m.kind === "failure").length;
  const stuck = model.markers.filter((m) => m.kind === "stuck").length;
  const running = model.agents.filter((a) => a.end === null).length;
  return (
    <div className="flex flex-wrap items-center gap-2 border-b border-border px-4 py-2 text-[12.5px]">
      <Badge tone="neutral">
        <ListChecks className="h-3.5 w-3.5" aria-hidden /> {done}/{model.tasks.length} tasks done
      </Badge>
      {model.phase && <Badge tone="info">Phase: {PHASE_LABEL[model.phase] ?? model.phase}</Badge>}
      {blocked > 0 && <Badge tone="danger">{blocked} blocked</Badge>}
      <Badge tone={failures ? "danger" : "neutral"}>
        <XCircle className="h-3.5 w-3.5" aria-hidden /> {failures} failed call{failures === 1 ? "" : "s"}
      </Badge>
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

function layout(model: RunModel, forge: Forge, onJump: (seq: number) => void): { nodes: FlowNode[]; edges: Edge[] } {
  const { nodes, edges } = planGraph(model);
  const graph = new dagre.graphlib.Graph();
  graph.setGraph({ rankdir: "LR", nodesep: 20, ranksep: 40, marginx: 16, marginy: 16 });
  graph.setDefaultEdgeLabel(() => ({}));
  for (const node of nodes) {
    const task = node.data.kind === "task";
    graph.setNode(node.id, { width: task ? TASK_W : STEP_W, height: task ? TASK_H : STEP_H });
  }
  for (const edge of edges) graph.setEdge(edge.from, edge.to);
  dagre.layout(graph);

  const byTask = forge.cost?.project?.by_task ?? {};
  const flowNodes: FlowNode[] = nodes.map((node) => {
    const box = graph.node(node.id);
    const task = node.data.kind === "task";
    const firstSeq = node.data.stats?.firstSeq;
    return {
      id: node.id,
      type: task ? "task" : "step",
      position: { x: box.x - box.width / 2, y: box.y - box.height / 2 },
      data: {
        ...node.data,
        usage: task ? byTask[node.id] : undefined,
        limits: forge.costColors?.task,
        onJump: firstSeq != null ? () => onJump(firstSeq) : undefined,
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

function TaskGraph({ model, forge, onJump }: { model: RunModel; forge: Forge; onJump: (seq: number) => void }) {
  const { nodes, edges } = useMemo(() => layout(model, forge, onJump), [model, forge, onJump]);
  const shape = nodes.map((n) => n.id).join("|"); // refit only when the plan's shape changes
  return (
    <ReactFlow
      key={shape}
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
      proOptions={{ hideAttribution: true }}
    >
      <Background gap={20} size={1} />
      <Controls showInteractive={false} position="bottom-right" />
    </ReactFlow>
  );
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
    <button
      type="button"
      onClick={data.onJump}
      disabled={!data.onJump}
      data-task={id}
      data-status={task.status}
      title={data.onJump ? "Show this task in the chat" : undefined}
      style={{ width: TASK_W, height: TASK_H }}
      className={cx(
        "flex flex-col gap-1 rounded-lg border bg-surface px-3 py-2 text-left shadow-sm transition-colors duration-150",
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
      {task.status === "blocked" && task.blocked_reason ? (
        <div className="truncate text-[11.5px] text-danger" title={task.blocked_reason}>
          Blocked: {task.blocked_reason}
        </div>
      ) : (
        <div className="mt-auto flex items-center gap-2.5 text-[11.5px] text-fg-muted">
          {(task.attempts ?? 0) > 1 && (
            <Stat icon={<Repeat className="h-3 w-3" />} title="Attempts">{task.attempts}</Stat>
          )}
          {!!stats?.failures && (
            <Stat icon={<XCircle className="h-3 w-3" />} title="Failed tool calls" className="text-danger">{stats.failures}</Stat>
          )}
          {!!stats?.stuck && (
            <Stat icon={<AlertTriangle className="h-3 w-3" />} title="Stuck warnings" className="text-warn">{stats.stuck}</Stat>
          )}
          {!!stats?.agents && (
            <Stat icon={<Bot className="h-3 w-3" />} title="Helper agents">{stats.agents}</Stat>
          )}
          {data.usage && <UsageBadge className="ml-auto" bucket={data.usage} limits={data.limits} compact />}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </button>
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

const STEP_ICON: Record<GraphNodeData["kind"], ReactNode> = {
  start: <ListChecks className="h-4 w-4" aria-hidden />,
  review: <Search className="h-4 w-4" aria-hidden />,
  deliver: <Flag className="h-4 w-4" aria-hidden />,
  task: null,
};

function StepNode({ data }: NodeProps<FlowNode>) {
  const tone =
    data.state === "done" ? "border-accent/60 text-accent" : data.state === "active" ? "border-info text-info" : "border-border text-fg-muted";
  return (
    <div
      style={{ width: STEP_W, height: STEP_H }}
      data-step={data.kind}
      className={cx("flex items-center justify-center gap-2 rounded-full border bg-raised text-[12.5px] font-medium", tone)}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />
      {data.state === "done" ? <CheckCircle2 className="h-4 w-4" aria-hidden /> : data.state === "active" ? STEP_ICON[data.kind] : <CircleDashed className="h-4 w-4" aria-hidden />}
      {data.title}
      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}

const NODE_TYPES = { task: TaskNode, step: StepNode };

// ---------------------------------------------------------------- timeline

const LABEL_W = 132;
const LANE_H = 26;
const AXIS_H = 26;
const IDLE_CAP_MS = 45_000; // a pause longer than this (usually waiting for you) is drawn this long, with a break

/** Maps clock time to x, squeezing long idle gaps so hours of waiting don't flatten the work into a line. */
function timeScale(times: number[], start: number, end: number, width: number) {
  const sorted = [...new Set([start, ...times, end])].sort((a, b) => a - b);
  const effective: number[] = [0];
  const breaks: number[] = [];
  for (let i = 1; i < sorted.length; i++) {
    const gap = sorted[i] - sorted[i - 1];
    if (gap > IDLE_CAP_MS) breaks.push(i);
    effective.push(effective[i - 1] + Math.min(gap, IDLE_CAP_MS));
  }
  const total = effective[effective.length - 1] || 1;
  const x = (t: number) => {
    let low = 0;
    let high = sorted.length - 1;
    while (low < high) {
      const mid = (low + high + 1) >> 1;
      if (sorted[mid] <= t) low = mid;
      else high = mid - 1;
    }
    const e = effective[low] + Math.min(Math.max(t - sorted[low], 0), IDLE_CAP_MS);
    return (Math.min(e, total) / total) * width;
  };
  return { x, breaks: breaks.map((i) => ({ at: x(sorted[i - 1]) + (x(sorted[i]) - x(sorted[i - 1])) / 2, resume: sorted[i] })) };
}

function clock(ms: number): string {
  return new Date(ms).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function Timeline({ model, onJump }: { model: RunModel; onJump: (seq: number) => void }) {
  const box = useRef<HTMLDivElement>(null);
  const [width, setWidth] = useState(800);
  useEffect(() => {
    const element = box.current;
    if (!element) return;
    const observer = new ResizeObserver(([entry]) => setWidth(Math.max(420, entry.contentRect.width)));
    observer.observe(element);
    return () => observer.disconnect();
  }, []);

  const start = model.start ?? 0;
  const end = Math.max(model.end ?? start, start + 1000);
  const plotW = width - LABEL_W - 8;
  const times = useMemo(
    () => [...model.spans.flatMap((s) => [s.start, s.end ?? end]), ...model.markers.map((m) => m.at)],
    [model, end],
  );
  const scale = useMemo(() => timeScale(times, start, end, plotW), [times, start, end, plotW]);
  const laneIndex = new Map(model.lanes.map((lane, index) => [lane.id, index]));
  const height = AXIS_H + model.lanes.length * LANE_H + 8;
  const yOf = (lane: string) => AXIS_H + (laneIndex.get(lane) ?? 0) * LANE_H;

  return (
    <div ref={box} className="px-4 py-2" data-testid="run-timeline">
      <svg width={width} height={height} role="img" aria-label="Timeline of phases, tasks and helper agents" className="block">
        {/* lane labels and stripes */}
        {model.lanes.map((lane, index) => (
          <g key={lane.id}>
            <rect x={0} y={AXIS_H + index * LANE_H} width={width} height={LANE_H} className={index % 2 ? "fill-transparent" : "fill-raised/40"} />
            <text x={4} y={AXIS_H + index * LANE_H + LANE_H / 2 + 4} className={cx("text-[11.5px]", lane.group === "task" ? "fill-fg font-mono" : "fill-fg-muted")}>
              {lane.group === "agent" ? `⤷ ${lane.label}` : lane.label}
            </text>
          </g>
        ))}
        <g transform={`translate(${LABEL_W},0)`}>
          {/* axis: start, end, and the clock time after each squeezed pause */}
          <text x={0} y={14} className="fill-fg-muted text-[10.5px]">{clock(start)}</text>
          <text x={plotW} y={14} textAnchor="end" className="fill-fg-muted text-[10.5px]">{clock(end)}</text>
          {scale.breaks.map((b, index) => (
            <g key={index}>
              <line x1={b.at} x2={b.at} y1={AXIS_H - 4} y2={height} className="stroke-border-strong" strokeDasharray="2 3" />
              <text x={b.at + 3} y={14} className="fill-fg-muted text-[10px]">
                <title>A long pause (usually waiting for you) is shortened here</title>
                ≈ {clock(b.resume)}
              </text>
            </g>
          ))}
          {model.spans.map((span, index) => (
            <SpanBar key={index} span={span} x={scale.x} end={end} y={yOf(span.lane)} onJump={onJump} />
          ))}
          {model.markers.map((marker, index) => (
            <MarkerGlyph key={index} marker={marker} x={scale.x(marker.at)} y={yOf(marker.lane)} onJump={onJump} />
          ))}
        </g>
      </svg>
      <Legend />
    </div>
  );
}

const SPAN_CLASS: Record<Span["tone"], string> = {
  phase: "fill-info/25 stroke-info/60",
  task: "fill-accent/25 stroke-accent/60",
  agent: "fill-fg-muted/20 stroke-fg-muted/50",
  "agent-failed": "fill-danger/20 stroke-danger/60",
};

function SpanBar({ span, x, end, y, onJump }: { span: Span; x: (t: number) => number; end: number; y: number; onJump: (seq: number) => void }) {
  const left = x(span.start);
  const right = x(span.end ?? end);
  const width = Math.max(3, right - left);
  const label = span.tone === "phase" ? PHASE_LABEL[span.label] ?? span.label : span.label;
  return (
    <g className="cursor-pointer" onClick={() => onJump(span.seq)} data-span={span.tone}>
      <title>{`${label} · ${clock(span.start)}${span.end === null ? " – now" : ""}`}</title>
      <rect x={left} y={y + 5} width={width} height={LANE_H - 10} rx={3} className={cx(SPAN_CLASS[span.tone], span.end === null && "run-live")} strokeWidth={1} />
      {width > 60 && span.tone === "phase" && (
        <text x={left + 5} y={y + LANE_H / 2 + 3.5} className="pointer-events-none fill-fg text-[10.5px]">{label}</text>
      )}
    </g>
  );
}

function MarkerGlyph({ marker, x, y, onJump }: { marker: Marker; x: number; y: number; onJump: (seq: number) => void }) {
  const middle = y + LANE_H / 2;
  return (
    <g className="cursor-pointer" onClick={() => onJump(marker.seq)} data-marker={marker.kind}>
      <title>{`${marker.label} · ${clock(marker.at)} (click to see it in the chat)`}</title>
      {marker.kind === "failure" && (
        <path d={`M${x - 4} ${middle - 4} L${x + 4} ${middle + 4} M${x + 4} ${middle - 4} L${x - 4} ${middle + 4}`} className="stroke-danger" strokeWidth={2.2} strokeLinecap="round" />
      )}
      {marker.kind === "stuck" && <path d={`M${x} ${middle - 6} L${x + 6} ${middle + 5} L${x - 6} ${middle + 5} Z`} className="fill-warn" />}
      {marker.kind === "waiting" && <path d={`M${x} ${middle - 6} L${x + 6} ${middle} L${x} ${middle + 6} L${x - 6} ${middle} Z`} className="fill-warn/80 stroke-warn" />}
      <rect x={x - 8} y={y} width={16} height={LANE_H} className="fill-transparent" />
    </g>
  );
}

function Legend() {
  const item = (swatch: ReactNode, text: string) => (
    <span className="inline-flex items-center gap-1.5">
      {swatch}
      {text}
    </span>
  );
  return (
    <div className="mt-2 flex flex-wrap gap-4 text-[11.5px] text-fg-muted">
      {item(<span className="h-2.5 w-4 rounded-sm border border-info/60 bg-info/25" />, "Phase")}
      {item(<span className="h-2.5 w-4 rounded-sm border border-accent/60 bg-accent/25" />, "Task being worked on")}
      {item(<span className="h-2.5 w-4 rounded-sm border border-fg-muted/50 bg-fg-muted/20" />, "Helper agent")}
      {item(<XCircle className="h-3.5 w-3.5 text-danger" aria-hidden />, "Failed tool call")}
      {item(<AlertTriangle className="h-3.5 w-3.5 text-warn" aria-hidden />, "Stuck warning")}
      {item(<Hand className="h-3.5 w-3.5 text-warn" aria-hidden />, "Waiting for you")}
    </div>
  );
}

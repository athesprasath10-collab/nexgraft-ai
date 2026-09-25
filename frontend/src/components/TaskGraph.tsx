import type { TaskRun } from "../lib/types";

const W = 680;
const NODE_W = 222;
const NODE_H = 40;

const truncate = (s: string, n: number) => (s.length > n ? `${s.slice(0, n - 1)}…` : s);

/**
 * Dynamic task graph: request → orchestrator → specialised workspaces → unified output.
 * Only the workspaces in the plan appear; edges animate while a task runs.
 */
export function TaskGraph({ tasks, synthesis, colors, names = {} }: { tasks: TaskRun[]; synthesis?: TaskRun; colors: Record<string, string>; names?: Record<string, string> }) {
  const visible = tasks.filter((t) => t.status !== "skipped" && t.enabled !== false);
  const n = Math.max(visible.length, 1);
  const rowH = 54;
  const H = Math.max(132, n * rowH + 36);
  const cy = H / 2;
  const xReq = 44;
  const xOrch = 190;
  const xTask = 318;
  const xOut = W - 44;
  const ys = visible.map((_, i) => cy + (i - (n - 1) / 2) * rowH);
  const multi = visible.length > 1;
  const outActive = multi ? synthesis?.status === "generating" : visible.some((t) => t.status === "generating");
  const outDone = multi ? synthesis?.status === "done" : visible.length > 0 && visible.every((t) => t.status === "done");

  const edgeClass = (status?: string) =>
    status === "generating" || status === "grounding" ? "edge active" : status === "done" ? "edge done" : status === "error" ? "edge error" : "edge";

  return (
    <svg className="task-graph" viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Dynamic task graph">
      <defs>
        <radialGradient id="orchGlow">
          <stop offset="0" stopColor="#a594ff" stopOpacity="0.55" />
          <stop offset="1" stopColor="#a594ff" stopOpacity="0" />
        </radialGradient>
      </defs>
      {/* request → orchestrator */}
      <path d={`M${xReq + 16} ${cy} L${xOrch - 30} ${cy}`} className="edge done" />
      {visible.map((t, i) => {
        const c = colors[t.agent] || "#8b7cff";
        const y = ys[i];
        return (
          <g key={t.id}>
            <path
              d={`M${xOrch + 30} ${cy} C ${xOrch + 80} ${cy}, ${xTask - 60} ${y}, ${xTask} ${y}`}
              className={edgeClass(t.status)}
              style={{ stroke: t.status === "pending" ? undefined : c }}
            />
            <path
              d={`M${xTask + NODE_W} ${y} C ${xTask + NODE_W + 50} ${y}, ${xOut - 60} ${cy}, ${xOut - 22} ${cy}`}
              className={edgeClass(t.status === "done" ? (outDone ? "done" : outActive ? "generating" : "pending") : "pending")}
              style={{ stroke: t.status === "done" ? c : undefined }}
            />
            <g className={`graph-node task ${t.status}`} transform={`translate(${xTask}, ${y - NODE_H / 2})`}>
              <rect width={NODE_W} height={NODE_H} rx={11} style={{ stroke: c, fill: `color-mix(in srgb, ${c} 12%, var(--surface-solid))` }} />
              <circle cx={16} cy={NODE_H / 2} r={5} style={{ fill: c }} className={t.status === "generating" || t.status === "grounding" ? "pulse-dot" : ""} />
              <text x={30} y={16} className="node-kicker">
                {truncate(names[t.agent] || t.agent_name || t.agent, 26)}
              </text>
              <text x={30} y={31} className="node-title">
                {truncate(t.title, 28)}
              </text>
            </g>
          </g>
        );
      })}
      <g className="graph-node req" transform={`translate(${xReq}, ${cy})`}>
        <circle r={16} />
        <text y={34} textAnchor="middle" className="node-caption">
          Request
        </text>
      </g>
      <g className="graph-node orch" transform={`translate(${xOrch}, ${cy})`}>
        <circle r={46} fill="url(#orchGlow)" stroke="none" />
        <circle r={28} />
        <text y={4} textAnchor="middle" className="node-mark">
          NX
        </text>
        <text y={48} textAnchor="middle" className="node-caption">
          Orchestrator
        </text>
      </g>
      <g className={`graph-node out ${outDone ? "done" : outActive ? "active" : ""}`} transform={`translate(${xOut}, ${cy})`}>
        <circle r={20} />
        <path d="M-7 0 l5 5 l9 -10" className="check" />
        <text y={38} textAnchor="middle" className="node-caption">
          {multi ? "Unified output" : "Output"}
        </text>
      </g>
    </svg>
  );
}

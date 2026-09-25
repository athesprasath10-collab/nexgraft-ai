import { ArrowRight, Brain, ChevronDown, Circle, CircleCheck, Info, LoaderCircle, Pencil, Plus, Route, X } from "lucide-react";
import { useState } from "react";
import { proceed } from "../lib/engine";
import { agentById, pluginById, useStore } from "../lib/store";
import type { AssistantTurn, TaskRun } from "../lib/types";
import { cx } from "../lib/utils";
import { IconTile } from "./Icon";
import { TaskGraph } from "./TaskGraph";

const STAGES = [
  { id: "understand", label: "Input understanding" },
  { id: "analyze", label: "Problem & intent analysis" },
  { id: "decompose", label: "Task decomposition" },
  { id: "route", label: "Intelligent routing" },
];

const ROUTER_LABEL: Record<string, string> = {
  llm: "LLM analyzer",
  "llm+guard": "LLM analyzer + keyword guard",
  heuristic: "Keyword router",
};

export function PipelineStages({ turn }: { turn: AssistantTurn }) {
  return (
    <ol className="pipeline">
      {STAGES.map((s) => {
        const st = turn.stages.find((x) => x.stage === s.id);
        const status = st?.status === "done" ? "done" : st?.status === "active" ? "active" : turn.phase === "analyzing" ? "waiting" : "done";
        return (
          <li key={s.id} className={cx("pipe-step", status)}>
            <span className="pipe-icon">
              {status === "done" ? <CircleCheck size={15} /> : status === "active" ? <LoaderCircle size={15} className="spin" /> : <Circle size={15} />}
            </span>
            <span className="pipe-label">{st?.label || s.label}</span>
            {st?.detail && <span className="pipe-detail">{st.detail}</span>}
          </li>
        );
      })}
    </ol>
  );
}

export function AnalysisCard({ convId, turn, request }: { convId: string; turn: AssistantTurn; request: string }) {
  const config = useStore((s) => s.config);
  const updateTurn = useStore((s) => s.updateTurn);
  const [editing, setEditing] = useState<string | null>(null);
  const [addOpen, setAddOpen] = useState(false);
  const a = turn.analysis;
  const awaiting = turn.phase === "awaiting";
  const colors = Object.fromEntries((config?.agents || []).map((x) => [x.id, x.color]));
  const names = Object.fromEntries((config?.agents || []).map((x) => [x.id, x.short_name]));

  const patch = (id: string, p: Partial<TaskRun>) =>
    updateTurn(convId, turn.id, (t) => ({ ...t, tasks: t.tasks.map((k) => (k.id === id ? { ...k, ...p } : k)) }));

  const addWorkspace = (agentId: string) => {
    const spec = agentById(config, agentId);
    if (!spec) return;
    const plugin = spec.uses_plugins ? a?.hardware_domain || null : null;
    updateTurn(convId, turn.id, (t) => ({
      ...t,
      tasks: [
        ...t.tasks,
        {
          id: `u${Date.now().toString(36)}`,
          agent: spec.id,
          agent_name: spec.name,
          color: spec.color,
          title: spec.short_name,
          instruction: spec.subtask_instruction ? spec.subtask_instruction.replace("{message}", request) : request,
          search_query: "",
          plugin,
          plugin_name: pluginById(config, plugin)?.name || null,
          enabled: true,
          status: "pending",
          content: "",
          sources: [],
          tools: [],
          notes: [],
        },
      ],
    }));
    setAddOpen(false);
  };

  const enabledCount = turn.tasks.filter((k) => k.enabled !== false).length;
  const unused = (config?.agents || []).filter((ag) => !turn.tasks.some((k) => k.agent === ag.id));

  return (
    <section className="analysis-card fade-up">
      <header className="analysis-head">
        <div className="analysis-title">
          <span className="brain">
            <Brain size={16} />
          </span>
          <div>
            <h3>{turn.phase === "analyzing" ? "Understanding your requirement…" : "Requirement analysed"}</h3>
            <p className="faint small">NEXGRAFT orchestration layer · LangGraph</p>
          </div>
        </div>
        {a && (
          <span className="router-badge" title={a.router_notes.join("\n") || undefined}>
            <Route size={13} /> {ROUTER_LABEL[a.router]}
            {a.analyzer_model ? ` · ${a.analyzer_model}` : ""}
          </span>
        )}
      </header>

      <PipelineStages turn={turn} />

      {a && (
        <>
          <div className="analysis-grid">
            <div className="kv">
              <span className="k">Detected domain</span>
              <span className="v strong">{a.domain}</span>
            </div>
            <div className="kv">
              <span className="k">Intent</span>
              <span className="v">{a.intent}</span>
            </div>
            <div className="kv">
              <span className="k">Required capabilities</span>
              <span className="v chips">
                {a.capabilities.map((c) => (
                  <span key={c} className="chip">
                    {c}
                  </span>
                ))}
              </span>
            </div>
            <div className="kv">
              <span className="k">Recommended workspaces</span>
              <span className="v chips">
                {turn.tasks
                  .filter((k) => k.enabled !== false)
                  .map((k) => (
                    <span key={k.id} className="chip agent-chip" style={{ "--c": colors[k.agent] } as React.CSSProperties}>
                      {agentById(config, k.agent)?.short_name}
                      {k.plugin && ` · ${pluginById(config, k.plugin)?.name}`}
                    </span>
                  ))}
              </span>
            </div>
            <div className="kv">
              <span className="k">Language</span>
              <span className="v">
                {a.language.native}
                {a.language.native !== a.language.name && ` · ${a.language.name}`}
                {a.language.auto && <span className="faint"> (auto)</span>}
              </span>
            </div>
            <div className="kv">
              <span className="k">Complexity</span>
              <span className="v">{a.complexity === "multi" ? `Multi-agent · ${turn.tasks.length} tasks` : "Single workspace"}</span>
            </div>
          </div>

          <TaskGraph tasks={turn.tasks} synthesis={turn.synthesis} colors={colors} names={names} />

          {a.router_notes.length > 0 && (
            <div className="router-notes">
              {a.router_notes.map((n, i) => (
                <p key={i}>
                  <Info size={13} /> {n}
                </p>
              ))}
            </div>
          )}

          {awaiting && (
            <div className="plan">
              <div className="plan-head">
                <h4>Task plan</h4>
                <span className="faint small">Review, edit or switch workspaces — nothing runs until you proceed.</span>
              </div>
              {turn.tasks.map((k) => {
                const spec = agentById(config, k.agent);
                const plugins = (config?.plugins || []).filter((p) => p.agent === k.agent);
                const off = k.enabled === false;
                return (
                  <div key={k.id} className={cx("plan-row", off && "off")}>
                    <label className="switch" title={off ? "Enable task" : "Skip task"}>
                      <input type="checkbox" checked={!off} onChange={(e) => patch(k.id, { enabled: e.target.checked })} />
                      <span />
                    </label>
                    <IconTile name={spec?.icon || "box"} color={spec?.color || "#888"} size={32} iconSize={16} />
                    <div className="plan-body">
                      <div className="plan-line">
                        <select
                          className="plain-select"
                          value={k.agent}
                          onChange={(e) => {
                            const ns = agentById(config, e.target.value);
                            patch(k.id, { agent: e.target.value, agent_name: ns?.name, color: ns?.color, plugin: ns?.uses_plugins ? k.plugin || a.hardware_domain : null });
                          }}
                        >
                          {config?.agents.map((ag) => (
                            <option key={ag.id} value={ag.id}>
                              {ag.name}
                            </option>
                          ))}
                        </select>
                        {plugins.length > 0 && (
                          <select className="plain-select" value={k.plugin || ""} onChange={(e) => patch(k.id, { plugin: e.target.value || null })}>
                            <option value="">General engineering</option>
                            {plugins.map((p) => (
                              <option key={p.id} value={p.id}>
                                {p.name}
                              </option>
                            ))}
                          </select>
                        )}
                        <span className="plan-title">{k.title}</span>
                        <button className="icon-btn sm" onClick={() => setEditing(editing === k.id ? null : k.id)} title="Edit instruction">
                          <Pencil size={13} />
                        </button>
                        {k.id.startsWith("u") && (
                          <button className="icon-btn sm" onClick={() => updateTurn(convId, turn.id, (t) => ({ ...t, tasks: t.tasks.filter((x) => x.id !== k.id) }))} title="Remove">
                            <X size={13} />
                          </button>
                        )}
                      </div>
                      {editing === k.id ? (
                        <textarea className="plan-edit" value={k.instruction} rows={3} onChange={(e) => patch(k.id, { instruction: e.target.value })} />
                      ) : (
                        <p className="plan-instr">{k.instruction}</p>
                      )}
                    </div>
                  </div>
                );
              })}
              <div className="plan-actions">
                <div className="add-wrap">
                  <button className="btn btn-ghost btn-sm" onClick={() => setAddOpen(!addOpen)} disabled={!unused.length}>
                    <Plus size={14} /> Add workspace <ChevronDown size={13} />
                  </button>
                  {addOpen && (
                    <div className="menu">
                      {unused.map((ag) => (
                        <button key={ag.id} className="menu-item" onClick={() => addWorkspace(ag.id)}>
                          <IconTile name={ag.icon} color={ag.color} size={24} iconSize={13} /> {ag.name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <button className="btn btn-primary" onClick={() => proceed(convId, turn.id)} disabled={!enabledCount}>
                  Proceed with {enabledCount} workspace{enabledCount === 1 ? "" : "s"} <ArrowRight size={15} />
                </button>
              </div>
            </div>
          )}
        </>
      )}
    </section>
  );
}

import { Calculator, ChevronRight, CornerDownLeft, FlaskConical, Globe, LoaderCircle, Play } from "lucide-react";
import { useState } from "react";
import { api, ApiError } from "../lib/api";
import type { ToolOutput, ToolSpec } from "../lib/types";
import { cx } from "../lib/utils";
import { ToolOutputView } from "./ToolOutputView";

function initialValues(tool: ToolSpec): Record<string, unknown> {
  return Object.fromEntries(tool.params.map((p) => [p.name, p.default ?? (p.type === "boolean" ? false : "")]));
}

export function toolResultText(tool: ToolSpec, out: ToolOutput): string {
  const rows = out.results.map((r) => `- ${r.label}: ${r.value}${r.unit ? ` ${r.unit}` : ""}`).join("\n");
  return `Verified ${tool.name} result (NEXGRAFT calculator): ${out.summary}\n${rows}`;
}

export function ToolForm({ tool, onInsert, defaultOpen = false }: { tool: ToolSpec; onInsert?: (text: string) => void; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  const [values, setValues] = useState<Record<string, unknown>>(() => initialValues(tool));
  const [busy, setBusy] = useState(false);
  const [out, setOut] = useState<ToolOutput | null>(null);
  const [error, setError] = useState<string | null>(null);

  const run = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.runTool(tool.id, values);
      setOut(res.output);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : String(err));
      setOut(null);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className={cx("tool-form", open && "open")}>
      <button className="tool-form-head" onClick={() => setOpen(!open)}>
        <span className="tool-form-icon">{tool.agent === "bioinformatics" ? <FlaskConical size={15} /> : tool.requires_network ? <Globe size={15} /> : <Calculator size={15} />}</span>
        <span className="tool-form-title">
          <span>{tool.name}</span>
          <span className="faint small">{tool.description}</span>
        </span>
        <ChevronRight size={15} className="chev" />
      </button>
      {open && (
        <div className="tool-form-body">
          {tool.formula && <code className="formula">{tool.formula}</code>}
          <div className="tool-fields">
            {tool.params.map((p) => (
              <label key={p.name} className={cx("field", (p.type === "text" || p.type === "string") && "wide")}>
                <span>
                  {p.label}
                  {p.unit && <span className="unit"> ({p.unit})</span>}
                  {!p.required && <span className="faint"> · optional</span>}
                </span>
                {p.type === "text" ? (
                  <textarea
                    rows={4}
                    className="mono"
                    value={String(values[p.name] ?? "")}
                    placeholder={p.help}
                    onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                  />
                ) : p.type === "select" ? (
                  <select value={String(values[p.name] ?? "")} onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}>
                    {p.options?.map((o) => (
                      <option key={o} value={o}>
                        {o}
                      </option>
                    ))}
                  </select>
                ) : p.type === "boolean" ? (
                  <span className="switch">
                    <input type="checkbox" checked={!!values[p.name]} onChange={(e) => setValues({ ...values, [p.name]: e.target.checked })} />
                    <span />
                  </span>
                ) : (
                  <input
                    type={p.type === "number" ? "text" : "text"}
                    inputMode={p.type === "number" ? "decimal" : undefined}
                    value={String(values[p.name] ?? "")}
                    placeholder={p.help || (p.required ? "" : "optional")}
                    onChange={(e) => setValues({ ...values, [p.name]: e.target.value })}
                    onKeyDown={(e) => e.key === "Enter" && run()}
                  />
                )}
                {p.help && p.type !== "text" && <span className="help">{p.help}</span>}
              </label>
            ))}
          </div>
          <div className="tool-form-actions">
            <button className="btn btn-sm btn-primary" onClick={run} disabled={busy}>
              {busy ? <LoaderCircle size={14} className="spin" /> : <Play size={14} />} Run
            </button>
            {out && onInsert && (
              <button className="btn btn-sm btn-ghost" onClick={() => onInsert(toolResultText(tool, out))} title="Add this verified result to your next message">
                <CornerDownLeft size={14} /> Use in prompt
              </button>
            )}
          </div>
          {error && <p className="tool-error">{error}</p>}
          {out && <ToolOutputView output={out} />}
        </div>
      )}
    </div>
  );
}

export function ToolPanel({ tools, onInsert, empty }: { tools: ToolSpec[]; onInsert?: (text: string) => void; empty?: string }) {
  if (!tools.length) return <p className="faint small pad">{empty || "No tools for this selection."}</p>;
  const groups = tools.reduce<Record<string, ToolSpec[]>>((acc, t) => {
    (acc[t.category || "Tools"] ||= []).push(t);
    return acc;
  }, {});
  return (
    <div className="tool-panel">
      {Object.entries(groups).map(([cat, list], g) => (
        <div key={cat} className="tool-group">
          <p className="nav-label">{cat}</p>
          {list.map((t, i) => (
            <ToolForm key={t.id} tool={t} onInsert={onInsert} defaultOpen={g === 0 && i === 0} />
          ))}
        </div>
      ))}
    </div>
  );
}

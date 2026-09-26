import { ChevronRight, ExternalLink, Info, TriangleAlert, Wrench } from "lucide-react";
import { useState } from "react";
import type { ToolCall, ToolOutput } from "../lib/types";
import { cx } from "../lib/utils";
import { SchematicView } from "./Schematic";

const EXTRA_BLOCKS: [keyof ToolOutput, string][] = [
  ["protein", "Protein"],
  ["translation_frame1", "Translation (frame 1)"],
  ["reverse_complement", "Reverse complement"],
  ["alignment", "Alignment"],
];

export function ToolOutputView({ output }: { output: ToolOutput }) {
  return (
    <div className="tool-output">
      {output.summary && <p className="tool-summary">{output.summary}</p>}
      {output.schematic && <SchematicView schematic={output.schematic} parts={output.parts} />}
      {output.results?.length > 0 && (
        <dl className="result-grid">
          {output.results.map((r, i) => (
            <div key={`${r.label}-${i}`} className="result-cell">
              <dt>{r.label}</dt>
              <dd>
                <span className="mono">{String(r.value)}</span>
                {r.unit && <span className="unit"> {r.unit}</span>}
              </dd>
            </div>
          ))}
        </dl>
      )}
      {EXTRA_BLOCKS.map(([key, label]) =>
        output[key] ? (
          <div key={String(key)} className="tool-extra">
            <span className="k">{label}</span>
            <pre className="mono">{String(output[key])}</pre>
          </div>
        ) : null,
      )}
      {output.records?.map((rec, i) => (
        <details key={i} className="tool-record">
          <summary>{rec.summary}</summary>
          <ToolOutputView output={rec} />
        </details>
      ))}
      {output.sources && output.sources.length > 0 && (
        <ol className="tool-sources">
          {output.sources.map((s, i) => (
            <li key={i}>
              <a href={s.url} target="_blank" rel="noreferrer">
                {s.title} <ExternalLink size={11} />
              </a>
              <span className="faint small">
                {" "}
                {s.authors} · {s.journal} {s.year}
              </span>
            </li>
          ))}
        </ol>
      )}
      {output.warnings?.map((w, i) => (
        <p key={i} className="tool-warning">
          <TriangleAlert size={13} /> {w}
        </p>
      ))}
      {output.notes?.map((w, i) => (
        <p key={i} className="tool-note">
          <Info size={13} /> {w}
        </p>
      ))}
    </div>
  );
}

export function ToolCallCard({ call }: { call: ToolCall }) {
  const [open, setOpen] = useState(!!call.output?.schematic);
  const hasDetail = (call.output?.results?.length || 0) > 0 || !!call.output?.schematic;
  return (
    <div className={cx("tool-call", open && "open")}>
      <button className="tool-call-head" onClick={() => hasDetail && setOpen(!open)}>
        <Wrench size={13} />
        <span className="tool-name">{call.name}</span>
        <span className="tool-sum">{call.output?.summary}</span>
        <span className="verified">computed</span>
        {hasDetail && <ChevronRight size={14} className="chev" />}
      </button>
      {open && hasDetail && <ToolOutputView output={{ ...call.output, summary: "" }} />}
    </div>
  );
}

import { BookOpen, ChevronDown, Database, ExternalLink, Library } from "lucide-react";
import { useState } from "react";
import type { Source } from "../lib/types";
import { cx } from "../lib/utils";

export function SourceItem({ s, id }: { s: Source; id?: string }) {
  const [open, setOpen] = useState(false);
  const lit = s.kind === "literature";
  return (
    <li id={id} className={cx("source", lit ? "lit" : "kb")}>
      <span className="source-n">{s.n}</span>
      <div className="source-body">
        {lit ? (
          <a className="source-title" href={s.url} target="_blank" rel="noreferrer">
            {s.title} <ExternalLink size={11} />
          </a>
        ) : (
          <span className="source-title">
            {s.title}
            {s.heading ? <span className="faint"> › {s.heading}</span> : null}
          </span>
        )}
        <div className="source-meta">
          {lit ? (
            <>
              {s.authors && <span>{s.authors}</span>}
              {(s.journal || s.year) && (
                <span>
                  {s.journal} {s.year}
                </span>
              )}
              {s.pmid && <span className="tag">PMID {s.pmid}</span>}
              {s.open_access && <span className="tag green">Open access</span>}
              {!!s.cited_by && <span className="tag">Cited by {s.cited_by}</span>}
            </>
          ) : (
            <>
              <span className="tag">
                <Database size={10} /> {s.collection}
              </span>
              <span>{s.doc}</span>
              {s.score !== null && s.score !== undefined && <span className="faint">relevance {s.score}</span>}
            </>
          )}
        </div>
        {s.snippet && (
          <p className={cx("source-snippet", open && "open")} onClick={() => setOpen(!open)}>
            {s.snippet}
          </p>
        )}
      </div>
    </li>
  );
}

export function SourceList({ sources, scope, defaultOpen = false }: { sources: Source[]; scope: string; defaultOpen?: boolean }) {
  const [open, setOpen] = useState(defaultOpen);
  if (!sources.length) return null;
  const lit = sources.filter((s) => s.kind === "literature").length;
  const kb = sources.length - lit;
  return (
    <div className={cx("sources", open && "open")} data-sources={scope}>
      <button className="sources-toggle" onClick={() => setOpen(!open)}>
        <Library size={14} />
        <span>
          {sources.length} source{sources.length === 1 ? "" : "s"}
        </span>
        {lit > 0 && (
          <span className="faint">
            <BookOpen size={12} /> {lit} literature
          </span>
        )}
        {kb > 0 && (
          <span className="faint">
            <Database size={12} /> {kb} knowledge base
          </span>
        )}
        <ChevronDown size={14} className="chev" />
      </button>
      {open && (
        <ol className="source-list">
          {sources.map((s, i) => (
            <SourceItem key={i} s={{ ...s, n: s.n ?? i + 1 }} id={`src-${scope}-${s.n ?? i + 1}`} />
          ))}
        </ol>
      )}
    </div>
  );
}

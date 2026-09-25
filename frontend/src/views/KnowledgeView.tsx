import { Database, FileText, FolderPlus, LoaderCircle, Menu, RefreshCw, Sparkles, Trash2, Upload } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";
import { toast } from "../components/Toast";
import { api, ApiError } from "../lib/api";
import { useStore } from "../lib/store";
import type { KnowledgeStats } from "../lib/types";
import { cx, formatBytes, timeAgo } from "../lib/utils";

export function KnowledgeView() {
  const config = useStore((s) => s.config);
  const setSidebarOpen = useStore((s) => s.setSidebarOpen);
  const [stats, setStats] = useState<KnowledgeStats | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [newId, setNewId] = useState("");
  const fileInput = useRef<HTMLInputElement>(null);
  const target = useRef<string>("");

  const load = useCallback(() => {
    api
      .knowledge()
      .then(setStats)
      .catch((e) => toast.error(e instanceof ApiError ? e.message : String(e)));
  }, []);
  useEffect(load, [load]);
  useEffect(() => {
    if (stats?.status !== "indexing") return;
    const t = setTimeout(load, 2000);
    return () => clearTimeout(t);
  }, [stats, load]);

  const usedBy = (cid: string) => {
    const agents = (config?.agents || []).filter((a) => a.knowledge_collections.includes(cid)).map((a) => a.short_name);
    const plugins = (config?.plugins || []).filter((p) => p.knowledge_collection === cid).map((p) => `${p.name} plugin`);
    return [...new Set([...plugins, ...agents])];
  };

  const run = async (label: string, fn: () => Promise<KnowledgeStats>, ok: string) => {
    setBusy(label);
    try {
      setStats(await fn());
      toast.success(ok);
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  };

  const totalDocs = stats?.collections.reduce((n, c) => n + c.documents.length, 0) || 0;
  const totalChunks = stats?.collections.reduce((n, c) => n + c.chunks, 0) || 0;

  return (
    <div className="view scroll-area">
      <div className="page">
        <header className="page-head">
          <button className="icon-btn mobile-only" onClick={() => setSidebarOpen(true)} aria-label="Open menu">
            <Menu size={20} />
          </button>
          <div>
            <span className="eyebrow">
              <Database size={12} /> Knowledge layer
            </span>
            <h1>Knowledge base</h1>
            <p className="muted">
              Domain collections the workspaces retrieve from before answering (RAG). Add PDFs, DOCX, Markdown or text to a collection and it is chunked
              and indexed locally.
            </p>
          </div>
          <button className="btn btn-ghost" onClick={() => run("all", () => api.reindex(), "Knowledge base re-indexed")} disabled={!!busy}>
            {busy === "all" ? <LoaderCircle size={15} className="spin" /> : <RefreshCw size={15} />} Re-index all
          </button>
        </header>

        {stats && (
          <div className="stat-row">
            <div className={cx("stat-card", stats.mode === "hybrid" ? "good" : "warn")}>
              <span className="stat-k">Retrieval mode</span>
              <span className="stat-v">{stats.mode === "hybrid" ? "Hybrid · vector + BM25" : "Keyword · BM25 only"}</span>
              <span className="faint small">
                {stats.mode === "hybrid" ? (
                  <>
                    <Sparkles size={11} /> Semantic embeddings via {stats.embed_model}
                  </>
                ) : (
                  <>
                    Run <code>ollama pull {stats.embed_model}</code> then re-index to enable semantic search.
                  </>
                )}
              </span>
            </div>
            <div className="stat-card">
              <span className="stat-k">Collections</span>
              <span className="stat-v">{stats.collections.length}</span>
              <span className="faint small">{stats.status === "indexing" ? "Indexing…" : "Ready"}</span>
            </div>
            <div className="stat-card">
              <span className="stat-k">Documents</span>
              <span className="stat-v">{totalDocs}</span>
              <span className="faint small">{totalChunks} chunks indexed</span>
            </div>
            <div className="stat-card">
              <span className="stat-k">Vector index</span>
              <span className="stat-v">Local · NumPy</span>
              <span className="faint small">Stored in data/index/</span>
            </div>
          </div>
        )}
        {stats?.last_error && <p className="turn-error">{stats.last_error}</p>}

        <div className="collection-grid">
          {stats?.collections.map((c) => (
            <section key={c.id} className="collection-card">
              <header>
                <div>
                  <h3 className="mono">{c.id}</h3>
                  <p className="faint small">Used by: {usedBy(c.id).join(", ") || "—"}</p>
                </div>
                <span className={cx("tag", c.vectors ? "green" : "")}>{c.vectors ? "vectors" : "keywords"}</span>
              </header>
              <ul className="doc-list">
                {c.documents.map((d) => (
                  <li key={d.file} className={cx(d.error && "error")}>
                    <FileText size={14} />
                    <span className="doc-title" title={d.file}>
                      {d.title}
                      <span className="faint small"> · {d.error ? d.error : `${d.chunks} chunks${d.size ? ` · ${formatBytes(d.size)}` : ""}`}</span>
                    </span>
                    <button
                      className="icon-btn sm"
                      title="Remove document"
                      onClick={() => confirm(`Delete ${d.file} from ${c.id}?`) && run(`del-${c.id}`, () => api.deleteKnowledge(c.id, d.file), "Document removed")}
                    >
                      <Trash2 size={13} />
                    </button>
                  </li>
                ))}
                {c.documents.length === 0 && <li className="faint small">No documents yet.</li>}
              </ul>
              <footer>
                <span className="faint small">{c.indexed_at ? `Indexed ${timeAgo(c.indexed_at * 1000)}` : ""}</span>
                <button
                  className="btn btn-sm btn-ghost"
                  disabled={!!busy}
                  onClick={() => {
                    target.current = c.id;
                    fileInput.current?.click();
                  }}
                >
                  {busy === `up-${c.id}` ? <LoaderCircle size={14} className="spin" /> : <Upload size={14} />} Add document
                </button>
              </footer>
            </section>
          ))}

          <section className="collection-card new">
            <FolderPlus size={22} />
            <h3>New collection</h3>
            <p className="faint small">A new domain folder under knowledge/. Link it to a workspace or plugin in code to use it.</p>
            <div className="inline-form">
              <input value={newId} onChange={(e) => setNewId(e.target.value.toLowerCase().replace(/[^a-z0-9-]/g, "-"))} placeholder="e.g. hardware-robotics" />
              <button
                className="btn btn-sm btn-primary"
                disabled={newId.length < 2 || !!busy}
                onClick={() => run("new", () => api.createCollection(newId), `Collection ${newId} created`).then(() => setNewId(""))}
              >
                Create
              </button>
            </div>
          </section>
        </div>
        <input
          ref={fileInput}
          type="file"
          hidden
          accept={(config?.features.document_types || []).join(",")}
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) run(`up-${target.current}`, () => api.uploadKnowledge(target.current, file), `${file.name} indexed into ${target.current}`);
          }}
        />
      </div>
    </div>
  );
}

import hljs from "highlight.js/lib/core";
import bash from "highlight.js/lib/languages/bash";
import c from "highlight.js/lib/languages/c";
import cpp from "highlight.js/lib/languages/cpp";
import javascript from "highlight.js/lib/languages/javascript";
import jsonLang from "highlight.js/lib/languages/json";
import markdown from "highlight.js/lib/languages/markdown";
import python from "highlight.js/lib/languages/python";
import r from "highlight.js/lib/languages/r";
import sql from "highlight.js/lib/languages/sql";
import typescript from "highlight.js/lib/languages/typescript";
import xml from "highlight.js/lib/languages/xml";
import yaml from "highlight.js/lib/languages/yaml";
import { Check, Copy, Download, LoaderCircle, Play, ShieldAlert } from "lucide-react";
import { createContext, isValidElement, memo, useContext, useMemo, useState, type ReactNode } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { api, ApiError } from "../lib/api";
import type { RunResult, Source } from "../lib/types";
import { copyText, cx, downloadText, linkCitations } from "../lib/utils";
import { RunOutput } from "./RunOutput";

hljs.registerLanguage("python", python);
hljs.registerLanguage("bash", bash);
hljs.registerLanguage("shell", bash);
hljs.registerLanguage("javascript", javascript);
hljs.registerLanguage("typescript", typescript);
hljs.registerLanguage("json", jsonLang);
hljs.registerLanguage("yaml", yaml);
hljs.registerLanguage("r", r);
hljs.registerLanguage("sql", sql);
hljs.registerLanguage("c", c);
hljs.registerLanguage("cpp", cpp);
hljs.registerLanguage("xml", xml);
hljs.registerLanguage("markdown", markdown);

const ALIASES: Record<string, string> = { py: "python", sh: "bash", js: "javascript", ts: "typescript", yml: "yaml", html: "xml", "c++": "cpp", console: "bash", zsh: "bash" };

interface MdContext {
  scope: string;
  sources: Source[];
  runnable: boolean;
  attachmentIds: string[];
}
const Ctx = createContext<MdContext>({ scope: "x", sources: [], runnable: false, attachmentIds: [] });

let confirmedThisSession = false;

export function CodeBlock({ lang, code, ...override }: { lang: string; code: string; runnable?: boolean; attachmentIds?: string[] }) {
  const ctx = useContext(Ctx);
  const runnable = override.runnable ?? ctx.runnable;
  const attachmentIds = override.attachmentIds ?? ctx.attachmentIds;
  const [copied, setCopied] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<RunResult | null>(null);
  const [runError, setRunError] = useState<string | null>(null);
  const language = ALIASES[lang] || lang;
  const html = useMemo(() => {
    try {
      return hljs.getLanguage(language) ? hljs.highlight(code, { language, ignoreIllegals: true }).value : null;
    } catch {
      return null;
    }
  }, [code, language]);
  const canRun = runnable && language === "python";

  const run = async () => {
    setConfirming(false);
    confirmedThisSession = true;
    setRunning(true);
    setRunError(null);
    try {
      setResult(await api.execute(code, attachmentIds));
    } catch (err) {
      setRunError(err instanceof ApiError ? err.message : String(err));
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="code-block">
      <div className="code-head">
        <span className="code-lang mono">{language || "text"}</span>
        <div className="code-actions">
          {canRun && (
            <button className="code-btn run" onClick={() => (confirmedThisSession ? run() : setConfirming(true))} disabled={running}>
              {running ? <LoaderCircle size={13} className="spin" /> : <Play size={13} />} {running ? "Running…" : "Run locally"}
            </button>
          )}
          <button
            className="code-btn"
            onClick={() => downloadText(language === "python" ? "nexgraft_script.py" : `snippet.${language || "txt"}`, code)}
            title="Download"
          >
            <Download size={13} />
          </button>
          <button
            className="code-btn"
            onClick={async () => {
              if (await copyText(code)) {
                setCopied(true);
                setTimeout(() => setCopied(false), 1400);
              }
            }}
            title="Copy"
          >
            {copied ? <Check size={13} /> : <Copy size={13} />}
          </button>
        </div>
      </div>
      {confirming && (
        <div className="run-confirm">
          <ShieldAlert size={16} />
          <span>
            This runs the script on <b>your computer</b> with your user permissions (separate Python process, temporary folder, timeout). Review the code
            first — you are in control.
          </span>
          <button className="btn btn-sm btn-primary" onClick={run}>
            Run now
          </button>
          <button className="btn btn-sm btn-ghost" onClick={() => setConfirming(false)}>
            Cancel
          </button>
        </div>
      )}
      <pre className="hljs">{html ? <code dangerouslySetInnerHTML={{ __html: html }} /> : <code>{code}</code>}</pre>
      {runError && <div className="run-error">{runError}</div>}
      {result && <RunOutput result={result} code={code} onClose={() => setResult(null)} />}
    </div>
  );
}

function Citation({ n }: { n: number }) {
  const { scope, sources } = useContext(Ctx);
  const src = sources.find((s) => s.n === n) || sources[n - 1];
  return (
    <a
      className="cite"
      href={`#src-${scope}-${n}`}
      title={src ? `${src.title}${src.year ? ` (${src.year})` : ""}` : `Source ${n}`}
      onClick={(e) => {
        e.preventDefault();
        const reveal = () => {
          const el = document.getElementById(`src-${scope}-${n}`);
          if (!el) return false;
          el.scrollIntoView({ behavior: "smooth", block: "center" });
          el.classList.add("flash");
          setTimeout(() => el.classList.remove("flash"), 1200);
          return true;
        };
        if (!reveal()) {
          // Sources list is collapsed: open it, then scroll.
          document.querySelector<HTMLButtonElement>(`[data-sources="${scope}"] .sources-toggle`)?.click();
          setTimeout(reveal, 60);
        }
      }}
    >
      {n}
    </a>
  );
}

const components: Components = {
  pre({ children }) {
    const child = Array.isArray(children) ? children[0] : children;
    if (isValidElement(child)) {
      const props = child.props as { className?: string; children?: ReactNode };
      const lang = /language-([\w+#.-]+)/.exec(props.className || "")?.[1] || "";
      const code = String(props.children ?? "").replace(/\n$/, "");
      return <CodeBlock lang={lang.toLowerCase()} code={code} />;
    }
    return <pre>{children}</pre>;
  },
  a({ href, children }) {
    const m = /^#cite-[^-]+-(\d+)$/.exec(href || "") || /^#cite-.*-(\d+)$/.exec(href || "");
    if (m) return <Citation n={Number(m[1])} />;
    return (
      <a href={href} target="_blank" rel="noreferrer noopener">
        {children}
      </a>
    );
  },
  table({ children }) {
    return (
      <div className="table-wrap">
        <table>{children}</table>
      </div>
    );
  },
};

interface Props {
  content: string;
  scope?: string;
  sources?: Source[];
  runnable?: boolean;
  attachmentIds?: string[];
  streaming?: boolean;
  className?: string;
}

function MarkdownImpl({ content, scope = "x", sources = [], runnable = false, attachmentIds = [], streaming = false, className }: Props) {
  const text = useMemo(() => linkCitations(content, scope, sources.length), [content, scope, sources.length]);
  const ctx = useMemo(() => ({ scope, sources, runnable, attachmentIds }), [scope, sources, runnable, attachmentIds]);
  return (
    <Ctx.Provider value={ctx}>
      <div className={cx("md", streaming && "streaming", className)}>
        <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
          {text}
        </ReactMarkdown>
      </div>
    </Ctx.Provider>
  );
}

export const Markdown = memo(MarkdownImpl);

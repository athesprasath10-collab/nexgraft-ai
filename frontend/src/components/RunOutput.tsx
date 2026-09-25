import { CircleCheck, Clock, Download, FileText, TriangleAlert, Wand2, X } from "lucide-react";
import type { RunResult } from "../lib/types";
import { cx, downloadText, formatBytes, seedComposer } from "../lib/utils";

export function RunOutput({ result, code, onClose }: { result: RunResult; code?: string; onClose?: () => void }) {
  const ok = result.exit_code === 0 && !result.timed_out;
  const askFix = () =>
    seedComposer(
      `This script failed when I ran it. Please explain the error and give a corrected complete script.\n\nError:\n${result.stderr.slice(-1500)}` +
        (code ? `\n\nScript:\n\`\`\`python\n${code.slice(0, 4000)}\n\`\`\`` : ""),
    );
  return (
    <div className={cx("run-output", ok ? "ok" : "fail")}>
      <div className="run-head">
        <span className="run-status">
          {ok ? <CircleCheck size={14} /> : <TriangleAlert size={14} />}
          {result.timed_out ? "Timed out" : ok ? "Finished" : `Exited with code ${result.exit_code}`}
        </span>
        <span className="faint mono">
          <Clock size={12} /> {result.seconds}s · Python {result.python}
        </span>
        {onClose && (
          <button className="icon-btn sm" onClick={onClose} aria-label="Close output">
            <X size={14} />
          </button>
        )}
      </div>
      {result.stdout && <pre className="console">{result.stdout}</pre>}
      {result.stderr && <pre className="console err">{result.stderr}</pre>}
      {!result.stdout && !result.stderr && <p className="faint small pad">No console output.</p>}
      {!ok && result.stderr && (
        <div className="run-fix">
          <button className="btn btn-sm btn-ghost" onClick={askFix}>
            <Wand2 size={13} /> Ask AI to fix
          </button>
          <span>Adds the error to your message box — review, then send.</span>
        </div>
      )}
      {result.artifacts.length > 0 && (
        <div className="artifacts">
          {result.artifacts.map((a) =>
            a.type === "image" && a.data_url ? (
              <figure key={a.name} className="artifact-img">
                <img src={a.data_url} alt={a.name} />
                <figcaption>
                  {a.name}
                  <a href={a.data_url} download={a.name} className="icon-btn sm" title="Download">
                    <Download size={13} />
                  </a>
                </figcaption>
              </figure>
            ) : (
              <div key={a.name} className="artifact-file">
                <FileText size={14} />
                <span>{a.name}</span>
                <span className="faint">{formatBytes(a.size)}</span>
                {a.preview && (
                  <button className="icon-btn sm" onClick={() => downloadText(a.name, a.preview || "")} title="Download">
                    <Download size={13} />
                  </button>
                )}
              </div>
            ),
          )}
        </div>
      )}
    </div>
  );
}

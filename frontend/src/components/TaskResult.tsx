import { Check, CircleStop, Copy, Gauge, Info, LoaderCircle, RefreshCw, TriangleAlert, Volume2, VolumeX, Workflow } from "lucide-react";
import { useState } from "react";
import { speak, stopSpeaking } from "../lib/speech";
import { agentById, pluginById, useStore } from "../lib/store";
import type { TaskRun } from "../lib/types";
import { copyText, cx, stripMarkdown } from "../lib/utils";
import { IconTile } from "./Icon";
import { Markdown } from "./Markdown";
import { SourceList } from "./SourceList";
import { ToolCallCard } from "./ToolOutputView";

const STATUS_LABEL: Record<string, string> = {
  pending: "Queued",
  grounding: "Retrieving knowledge & tools…",
  generating: "Generating…",
  done: "Done",
  error: "Error",
  stopped: "Stopped",
  skipped: "Skipped",
};

interface Props {
  task: TaskRun;
  scope: string;
  attachmentIds: string[];
  languageSpeech: string;
  onRegenerate?: () => void;
  synthesis?: boolean;
  compactHeader?: boolean;
}

export function TaskResult({ task, scope, attachmentIds, languageSpeech, onRegenerate, synthesis = false, compactHeader = false }: Props) {
  const config = useStore((s) => s.config);
  const spec = agentById(config, task.agent);
  const plugin = pluginById(config, task.plugin);
  const [copied, setCopied] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const color = synthesis ? "#a594ff" : spec?.color || "#8b7cff";
  const busy = task.status === "grounding" || task.status === "generating" || task.status === "pending";
  const runnable = !!config?.features.code_runner && task.agent === "bioinformatics";
  const stats = task.stats;

  return (
    <article className={cx("task-result fade-up", synthesis && "synthesis", `st-${task.status}`)} style={{ "--c": color } as React.CSSProperties}>
      {!compactHeader && (
        <header className="task-head">
          {synthesis ? (
            <span className="icon-tile synth">
              <Workflow size={17} />
            </span>
          ) : (
            <IconTile name={spec?.icon || "box"} color={color} />
          )}
          <div className="task-title">
            <span className="task-agent">
              {synthesis ? "NEXGRAFT Orchestrator" : spec?.name || task.agent}
              {plugin && <span className="plugin-chip">{plugin.name}</span>}
            </span>
            <span className="task-sub">{task.title}</span>
          </div>
          <span className={cx("task-status", task.status)}>
            {busy && <LoaderCircle size={13} className="spin" />}
            {task.status === "error" && <TriangleAlert size={13} />}
            {task.status === "stopped" && <CircleStop size={13} />}
            {STATUS_LABEL[task.status]}
          </span>
        </header>
      )}

      {task.tools.length > 0 && (
        <div className="tool-calls">
          {task.tools.map((c, i) => (
            <ToolCallCard key={i} call={c} />
          ))}
        </div>
      )}

      {task.notes.map((n, i) => (
        <p key={i} className="task-note">
          <Info size={13} /> {n}
        </p>
      ))}

      {task.content ? (
        <Markdown
          content={task.content}
          scope={scope}
          sources={task.sources}
          runnable={runnable && task.status !== "generating"}
          attachmentIds={attachmentIds}
          streaming={task.status === "generating"}
        />
      ) : busy ? (
        <div className="skeleton">
          <span />
          <span />
          <span />
        </div>
      ) : null}

      {task.error && (
        <p className="task-error">
          <TriangleAlert size={14} /> {task.error}
        </p>
      )}

      <SourceList sources={task.sources} scope={scope} defaultOpen={false} />

      {(task.status === "done" || task.status === "stopped" || task.status === "error") && (
        <footer className="task-foot">
          <div className="task-actions">
            {task.content && (
              <button
                className="icon-btn"
                title="Copy answer"
                onClick={async () => {
                  if (await copyText(task.content)) {
                    setCopied(true);
                    setTimeout(() => setCopied(false), 1400);
                  }
                }}
              >
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
            )}
            {task.content && "speechSynthesis" in window && (
              <button
                className={cx("icon-btn", speaking && "active")}
                title={speaking ? "Stop reading" : "Read aloud"}
                onClick={() => {
                  if (speaking) {
                    stopSpeaking();
                    setSpeaking(false);
                  } else if (speak(stripMarkdown(task.content), languageSpeech, () => setSpeaking(false))) setSpeaking(true);
                }}
              >
                {speaking ? <VolumeX size={15} /> : <Volume2 size={15} />}
              </button>
            )}
            {onRegenerate && (
              <button className="icon-btn" title="Regenerate" onClick={onRegenerate}>
                <RefreshCw size={15} />
              </button>
            )}
          </div>
          {stats?.model && (
            <span className="task-stats mono">
              <Gauge size={12} /> {stats.model}
              {stats.tokens_per_second ? ` · ${stats.tokens_per_second} tok/s` : ""}
              {stats.eval_count ? ` · ${stats.eval_count} tokens` : ""}
              {stats.seconds ? ` · ${stats.seconds}s` : ""}
              {stats.done_reason === "length" ? " · hit max length" : ""}
            </span>
          )}
        </footer>
      )}
    </article>
  );
}

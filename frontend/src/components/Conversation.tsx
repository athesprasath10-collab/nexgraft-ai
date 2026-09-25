import { FileText, Mic, TriangleAlert } from "lucide-react";
import { useEffect, useLayoutEffect, useRef } from "react";
import { regenerate } from "../lib/engine";
import { useStore } from "../lib/store";
import type { AssistantTurn, Conversation as Conv, UserTurn } from "../lib/types";
import { formatBytes } from "../lib/utils";
import { AnalysisCard } from "./AnalysisCard";
import { TaskResult } from "./TaskResult";

function UserBubble({ turn }: { turn: UserTurn }) {
  return (
    <div className="user-turn fade-up">
      <div className="user-bubble">
        {turn.attachments.length > 0 && (
          <div className="bubble-attachments">
            {turn.attachments.map((a) =>
              a.thumb ? (
                <img key={a.id} src={a.thumb} alt={a.name} title={a.preview} className="bubble-thumb" />
              ) : (
                <span key={a.id} className="bubble-file" title={a.preview}>
                  <FileText size={13} /> {a.name} <span className="faint">{formatBytes(a.size)}</span>
                </span>
              ),
            )}
          </div>
        )}
        {turn.content && <p className="bubble-text">{turn.content}</p>}
        {turn.voice && (
          <span className="voice-badge">
            <Mic size={11} /> voice
          </span>
        )}
      </div>
    </div>
  );
}

function AssistantBlock({ conv, turn, request, attachmentIds, isLast }: { conv: Conv; turn: AssistantTurn; request: string; attachmentIds: string[]; isLast: boolean }) {
  const languages = useStore((s) => s.config?.languages) || [];
  const langCode = turn.analysis?.language.code || useStore.getState().settings.language;
  const speech = languages.find((l) => l.code === langCode)?.speech || "en-IN";
  const multi = turn.tasks.filter((t) => t.enabled !== false).length > 1;
  const canRegenerate = isLast && (turn.phase === "done" || turn.phase === "stopped" || turn.phase === "error");

  return (
    <div className="assistant-turn">
      {turn.mode === "orchestrator" && <AnalysisCard convId={conv.id} turn={turn} request={request} />}
      {turn.phase !== "awaiting" &&
        turn.tasks
          .filter((t) => t.status !== "skipped" && !(turn.phase === "analyzing"))
          .map((t) => (
            <TaskResult
              key={t.id}
              task={t}
              scope={`${turn.id}_${t.id}`}
              attachmentIds={attachmentIds}
              languageSpeech={speech}
              onRegenerate={canRegenerate && !multi ? () => regenerate(conv.id, turn.id) : undefined}
            />
          ))}
      {turn.synthesis && (
        <TaskResult
          task={turn.synthesis}
          scope={`${turn.id}_synthesis`}
          attachmentIds={attachmentIds}
          languageSpeech={speech}
          synthesis
          onRegenerate={canRegenerate ? () => regenerate(conv.id, turn.id) : undefined}
        />
      )}
      {turn.error && (
        <div className="turn-error">
          <TriangleAlert size={15} />
          <span>{turn.error}</span>
        </div>
      )}
    </div>
  );
}

export function ConversationView({ conv }: { conv: Conv }) {
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const last = conv.turns[conv.turns.length - 1];
  const lastKey = last ? `${last.id}:${last.role === "assistant" ? JSON.stringify([last.phase, last.tasks.map((t) => t.content.length), last.synthesis?.content.length]) : ""}` : "";

  useEffect(() => {
    const el = scroller.current?.closest(".scroll-area") as HTMLElement | null;
    if (!el) return;
    const onScroll = () => {
      stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 140;
    };
    el.addEventListener("scroll", onScroll, { passive: true });
    return () => el.removeEventListener("scroll", onScroll);
  }, []);

  useLayoutEffect(() => {
    const el = scroller.current?.closest(".scroll-area") as HTMLElement | null;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [lastKey, conv.turns.length]);

  let request = "";
  let attachmentIds: string[] = [];
  return (
    <div className="conversation" ref={scroller}>
      {conv.turns.map((t, i) => {
        if (t.role === "user") {
          request = t.content;
          attachmentIds = t.attachments.map((a) => a.id);
          return <UserBubble key={t.id} turn={t} />;
        }
        return <AssistantBlock key={t.id} conv={conv} turn={t} request={request} attachmentIds={attachmentIds} isLast={i === conv.turns.length - 1} />;
      })}
    </div>
  );
}

/**
 * Conversation engine: sends requests to the orchestrator, applies streamed
 * events to the store, and batches tokens so rendering stays smooth.
 */
import { ApiError, requestOptions, streamEvents, type RunBody, type StreamEvent } from "./api";
import { agentById, pluginById, uid, useStore } from "./store";
import type { AssistantTurn, Attachment, Conversation, PlanTask, TaskRun, UserTurn } from "./types";

const controllers = new Map<string, AbortController>();

export const isActive = (turnId: string) => controllers.has(turnId);

export function stopTurn(turnId: string) {
  controllers.get(turnId)?.abort();
}

/** Flattened conversation history for the model (previous turns only). */
function historyFor(conv: Conversation, beforeTurnId: string): RunBody["history"] {
  const out: RunBody["history"] = [];
  for (const t of conv.turns) {
    if (t.id === beforeTurnId) break;
    if (t.role === "user") {
      out.push({ role: "user", content: t.content || `(attached ${t.attachments.map((a) => a.name).join(", ")})` });
    } else {
      const text = t.synthesis?.content
        ? t.synthesis.content
        : t.tasks
            .filter((k) => k.status === "done" && k.content)
            .map((k) => (t.tasks.length > 1 ? `[${k.agent_name}] ${k.content}` : k.content))
            .join("\n\n");
      if (text) out.push({ role: "assistant", content: text.slice(0, 3000) });
    }
  }
  return out.slice(-8);
}

function emptyRun(task: PlanTask): TaskRun {
  return { ...task, status: task.enabled === false ? "skipped" : "pending", content: "", sources: [], tools: [], notes: [] };
}

// ---------------------------------------------------------------- batching
const tokenBuffers = new Map<string, { convId: string; turnId: string; parts: Map<string, string> }>();
let flushTimer: number | undefined;

function queueToken(convId: string, turnId: string, taskId: string, text: string) {
  const key = `${convId}:${turnId}`;
  let buf = tokenBuffers.get(key);
  if (!buf) {
    buf = { convId, turnId, parts: new Map() };
    tokenBuffers.set(key, buf);
  }
  buf.parts.set(taskId, (buf.parts.get(taskId) || "") + text);
  if (flushTimer === undefined) flushTimer = window.setTimeout(flushTokens, 40);
}

function flushTokens() {
  flushTimer = undefined;
  const { updateTurn } = useStore.getState();
  for (const buf of tokenBuffers.values()) {
    const parts = new Map(buf.parts);
    buf.parts.clear();
    updateTurn(buf.convId, buf.turnId, (t) => {
      let next = t;
      for (const [taskId, text] of parts) {
        if (taskId === "synthesis" && next.synthesis) {
          next = { ...next, synthesis: { ...next.synthesis, status: "generating", content: next.synthesis.content + text } };
        } else {
          next = { ...next, tasks: next.tasks.map((k) => (k.id === taskId ? { ...k, status: "generating", content: k.content + text } : k)) };
        }
      }
      return next;
    });
  }
  tokenBuffers.clear();
}

// --------------------------------------------------------------- reducers
function patchTask(t: AssistantTurn, taskId: string, fn: (k: TaskRun) => TaskRun): AssistantTurn {
  if (taskId === "synthesis") return t.synthesis ? { ...t, synthesis: fn(t.synthesis) } : t;
  return { ...t, tasks: t.tasks.map((k) => (k.id === taskId ? fn(k) : k)) };
}

function applyRunEvent(t: AssistantTurn, ev: StreamEvent, idMap: Map<string, string>): AssistantTurn {
  const taskId = ev.task_id === "synthesis" ? "synthesis" : idMap.get(ev.task_id) || ev.task_id;
  switch (ev.type) {
    case "task_start":
      if (ev.task_id === "synthesis") {
        return {
          ...t,
          synthesis: {
            id: "synthesis", agent: "orchestrator", title: ev.title, instruction: "", search_query: "", plugin: null,
            status: "generating", content: "", sources: [], tools: [], notes: [],
          },
        };
      }
      return patchTask(t, taskId, (k) => ({ ...k, status: "grounding" }));
    case "task_phase":
      return patchTask(t, taskId, (k) => ({ ...k, status: ev.phase === "generating" ? "generating" : "grounding", model: ev.model || k.model }));
    case "tool":
      return patchTask(t, taskId, (k) => ({ ...k, tools: [...k.tools, { tool: ev.tool, name: ev.name, input: ev.input, output: ev.output }] }));
    case "sources":
      return patchTask(t, taskId, (k) => ({ ...k, sources: ev.sources }));
    case "note":
      return patchTask(t, taskId, (k) => ({ ...k, notes: [...k.notes, ev.message] }));
    case "task_end":
      return patchTask(t, taskId, (k) => ({ ...k, status: "done", stats: ev.stats }));
    case "task_error":
      return patchTask(t, taskId, (k) => ({ ...k, status: "error", error: ev.message }));
    case "error":
      return { ...t, error: ev.message };
    case "done":
      return { ...t, phase: t.error ? "error" : "done", seconds: ev.seconds };
    default:
      return t;
  }
}

function markStopped(t: AssistantTurn): AssistantTurn {
  const stop = (k: TaskRun): TaskRun => (k.status === "pending" || k.status === "grounding" || k.status === "generating" ? { ...k, status: "stopped" } : k);
  return { ...t, phase: "stopped", tasks: t.tasks.map(stop), synthesis: t.synthesis ? stop(t.synthesis) : t.synthesis };
}

// ------------------------------------------------------------------ runs
async function execute(convId: string, turnId: string, body: RunBody, idMap: Map<string, string>) {
  const { updateTurn } = useStore.getState();
  const controller = new AbortController();
  controllers.set(turnId, controller);
  updateTurn(convId, turnId, (t) => ({ ...t, phase: "running", error: undefined }));
  try {
    for await (const ev of streamEvents("/api/run", body, controller.signal)) {
      if (ev.type === "token") {
        queueToken(convId, turnId, ev.task_id === "synthesis" ? "synthesis" : idMap.get(ev.task_id) || ev.task_id, ev.content);
        continue;
      }
      flushTokens();
      updateTurn(convId, turnId, (t) => applyRunEvent(t, ev, idMap));
    }
    flushTokens();
    updateTurn(convId, turnId, (t) => (t.phase === "running" ? { ...t, phase: t.error ? "error" : "done" } : t));
  } catch (err) {
    flushTokens();
    if ((err as Error).name === "AbortError") {
      updateTurn(convId, turnId, markStopped);
    } else {
      const msg = err instanceof ApiError ? err.message : String(err);
      updateTurn(convId, turnId, (t) => ({ ...markStopped(t), phase: "error", error: msg }));
    }
  } finally {
    controllers.delete(turnId);
  }
}

function lastUserTurn(conv: Conversation, beforeTurnId: string): UserTurn | undefined {
  let last: UserTurn | undefined;
  for (const t of conv.turns) {
    if (t.id === beforeTurnId) break;
    if (t.role === "user") last = t;
  }
  return last;
}

/** Orchestrator mode: analyse → (user confirms plan) → run. */
export async function sendOrchestrated(convId: string, text: string, attachments: Attachment[], voice: boolean) {
  const store = useStore.getState();
  const user: UserTurn = { id: uid(), role: "user", content: text, attachments, voice, createdAt: Date.now() };
  const turn: AssistantTurn = { id: uid(), role: "assistant", mode: "orchestrator", phase: "analyzing", stages: [], tasks: [], createdAt: Date.now() };
  store.addTurn(convId, user);
  store.addTurn(convId, turn);

  const controller = new AbortController();
  controllers.set(turn.id, controller);
  const body = { message: text, attachments: attachments.map((a) => a.id), options: requestOptions(store.settings, voice) };
  try {
    for await (const ev of streamEvents("/api/analyze", body, controller.signal)) {
      if (ev.type === "stage") {
        useStore.getState().updateTurn(convId, turn.id, (t) => {
          const stages = t.stages.filter((s) => s.stage !== ev.stage);
          return { ...t, stages: [...stages, { stage: ev.stage, label: ev.label, status: ev.status, detail: ev.detail }] };
        });
      } else if (ev.type === "analysis") {
        const tasks = (ev.analysis.tasks as PlanTask[]).map((k) => emptyRun({ ...k, enabled: true }));
        useStore.getState().updateTurn(convId, turn.id, (t) => ({ ...t, analysis: ev.analysis, tasks, phase: "awaiting" }));
      } else if (ev.type === "error") {
        useStore.getState().updateTurn(convId, turn.id, (t) => ({ ...t, error: ev.message }));
      }
    }
  } catch (err) {
    const aborted = (err as Error).name === "AbortError";
    useStore.getState().updateTurn(convId, turn.id, (t) => ({
      ...t,
      phase: aborted ? "stopped" : "error",
      error: aborted ? undefined : err instanceof ApiError ? err.message : String(err),
    }));
    controllers.delete(turn.id);
    return;
  }
  controllers.delete(turn.id);
  const state = useStore.getState();
  const current = state.conversations[convId]?.turns.find((t) => t.id === turn.id) as AssistantTurn | undefined;
  if (!current?.analysis) {
    state.updateTurn(convId, turn.id, (t) => ({ ...t, phase: "error", error: t.error || "The analysis did not return a plan." }));
    return;
  }
  if (state.settings.autoRun) await proceed(convId, turn.id);
}

/** Runs the (possibly edited) plan of an orchestrator turn. */
export async function proceed(convId: string, turnId: string) {
  const state = useStore.getState();
  const conv = state.conversations[convId];
  const turn = conv?.turns.find((t) => t.id === turnId) as AssistantTurn | undefined;
  const user = conv && lastUserTurn(conv, turnId);
  if (!conv || !turn || !user) return;
  const enabled = turn.tasks.filter((k) => k.enabled !== false);
  if (!enabled.length) return;
  const idMap = new Map<string, string>();
  const tasks: PlanTask[] = enabled.map((k, i) => {
    idMap.set(`t${i + 1}`, k.id);
    return { id: `t${i + 1}`, agent: k.agent, title: k.title, instruction: k.instruction, search_query: k.search_query, plugin: k.plugin };
  });
  state.updateTurn(convId, turnId, (t) => ({
    ...t,
    synthesis: undefined,
    tasks: t.tasks.map((k) => ({ ...k, status: k.enabled === false ? "skipped" : "pending", content: "", sources: [], tools: [], notes: [], error: undefined, stats: undefined })),
  }));
  await execute(
    convId,
    turnId,
    {
      message: user.content || "Please analyse the attached file(s).",
      history: historyFor(conv, user.id),
      attachments: user.attachments.map((a) => a.id),
      tasks,
      options: requestOptions(state.settings, !!user.voice),
    },
    idMap,
  );
}

/** Direct workspace mode: a single specialised agent. */
export async function sendDirect(convId: string, agentId: string, plugin: string | null, text: string, attachments: Attachment[], voice: boolean) {
  const state = useStore.getState();
  const config = state.config;
  const spec = agentById(config, agentId);
  const pl = pluginById(config, plugin);
  const user: UserTurn = { id: uid(), role: "user", content: text, attachments, voice, createdAt: Date.now() };
  const task: TaskRun = emptyRun({
    id: "t1",
    agent: agentId,
    title: spec ? spec.short_name + (pl ? ` · ${pl.name}` : "") : agentId,
    instruction: text,
    search_query: "",
    plugin,
    agent_name: spec?.name,
    plugin_name: pl?.name,
    color: spec?.color,
  });
  const turn: AssistantTurn = { id: uid(), role: "assistant", mode: "direct", phase: "running", stages: [], tasks: [task], createdAt: Date.now() };
  state.addTurn(convId, user);
  state.addTurn(convId, turn);
  const conv = useStore.getState().conversations[convId];
  await execute(
    convId,
    turn.id,
    {
      message: text || "Please analyse the attached file(s).",
      history: historyFor(conv, user.id),
      attachments: attachments.map((a) => a.id),
      agent: agentId,
      plugin,
      options: requestOptions(state.settings, voice),
    },
    new Map([["t1", "t1"]]),
  );
}

/** Re-run the latest direct turn (regenerate). */
export async function regenerate(convId: string, turnId: string) {
  const state = useStore.getState();
  const conv = state.conversations[convId];
  const turn = conv?.turns.find((t) => t.id === turnId) as AssistantTurn | undefined;
  if (!conv || !turn) return;
  if (turn.mode === "orchestrator") return proceed(convId, turnId);
  const user = lastUserTurn(conv, turnId);
  const task = turn.tasks[0];
  if (!user || !task) return;
  state.updateTurn(convId, turnId, (t) => ({ ...t, tasks: [{ ...task, status: "pending", content: "", sources: [], tools: [], notes: [], error: undefined, stats: undefined }] }));
  await execute(
    convId,
    turnId,
    {
      message: user.content || "Please analyse the attached file(s).",
      history: historyFor(conv, user.id),
      attachments: user.attachments.map((a) => a.id),
      agent: task.agent,
      plugin: task.plugin,
      options: requestOptions(state.settings, !!user.voice),
    },
    new Map([["t1", "t1"]]),
  );
}

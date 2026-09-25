import { useEffect, useRef, useState } from "react";
import { navigate } from "../../lib/route";
import { useStore } from "../../lib/store";
import type { SceneAgent, SceneHandle } from "./NexgraftScene";

/** Interactive WebGL hero. three.js loads lazily, only on the home page. */
export default function Hero3D({ onFail }: { onFail: () => void }) {
  const agents = useStore((s) => s.config?.agents) || [];
  const modelUrl = useStore((s) => s.config?.hero_model);
  const host = useRef<HTMLDivElement>(null);
  const [ready, setReady] = useState(false);
  const [hover, setHover] = useState<{ agent: SceneAgent; x: number; y: number } | null>(null);

  useEffect(() => {
    let handle: SceneHandle | null = null;
    let cancelled = false;
    import("./NexgraftScene")
      .then(({ mountScene, webglAvailable }) => {
        if (cancelled || !host.current) return;
        if (!webglAvailable()) return onFail();
        handle = mountScene(host.current, {
          agents: agents.map((a) => ({ id: a.id, name: a.name, color: a.color, icon: a.icon })),
          modelUrl,
          onReady: () => setReady(true),
          onHover: (agent, x, y) => setHover(agent ? { agent, x, y } : null),
          onSelect: (agent) => navigate({ name: "workspace", agent: agent.id }),
        });
      })
      .catch(onFail);
    return () => {
      cancelled = true;
      handle?.dispose();
    };
  }, [agents.length, modelUrl]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div className={`hero3d ${ready ? "ready" : ""}`} ref={host} aria-label="NEXGRAFT orchestrator with four specialised workspaces">
      {hover && (
        <div className="hero3d-tip" style={{ left: hover.x, top: hover.y, "--c": hover.agent.color } as React.CSSProperties}>
          <span className="dot" />
          {hover.agent.name}
          <span className="faint">Open workspace →</span>
        </div>
      )}
    </div>
  );
}

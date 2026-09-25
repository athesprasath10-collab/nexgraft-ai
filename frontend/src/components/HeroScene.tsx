import { Component, lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react";
import { useStore } from "../lib/store";
import { cx } from "../lib/utils";
import { DynamicIcon } from "./Icon";

// The Spline runtime (~2 MB) is only downloaded when a scene is configured.
const Spline = lazy(() => import("@splinetool/react-spline"));

class SceneBoundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

/**
 * Offline, GPU-light pseudo-3D orbit: the workspaces circle the NEXGRAFT core.
 * Positions are projected from an ellipse each frame; depth drives scale,
 * opacity and z-order, so nodes pass in front of and behind the core.
 */
export function OrbitCore({ still = false, compact = false }: { still?: boolean; compact?: boolean }) {
  const agents = useStore((s) => s.config?.agents) || [];
  const scene = useRef<HTMLDivElement>(null);
  const nodes = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    const el = scene.current;
    if (!el) return;
    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tilt = (-9 * Math.PI) / 180;
    let raf = 0;
    const started = performance.now();
    const place = (now: number) => {
      const w = el.clientWidth;
      const rx = w * 0.4;
      const ry = rx * 0.34;
      const n = nodes.current.length || 1;
      const angle = still || reduced ? 0.6 : ((now - started) / 1000) * 0.22 + 0.6;
      nodes.current.forEach((node, i) => {
        if (!node) return;
        const a = angle + (i * 2 * Math.PI) / n;
        const x0 = Math.cos(a) * rx;
        const y0 = Math.sin(a) * ry;
        const x = x0 * Math.cos(tilt) - y0 * Math.sin(tilt);
        const y = x0 * Math.sin(tilt) + y0 * Math.cos(tilt);
        const depth = Math.sin(a); // -1 = far side, +1 = near side
        const scale = 0.74 + 0.3 * ((depth + 1) / 2);
        node.style.transform = `translate(-50%, -50%) translate(${x.toFixed(1)}px, ${y.toFixed(1)}px) scale(${scale.toFixed(3)})`;
        node.style.zIndex = depth > 0 ? "4" : "1";
        node.style.opacity = (0.5 + 0.5 * ((depth + 1) / 2)).toFixed(2);
        node.style.filter = depth < -0.2 ? `blur(${((-depth - 0.2) * 1.4).toFixed(2)}px)` : "none";
      });
      if (!still && !reduced) raf = requestAnimationFrame(place);
    };
    raf = requestAnimationFrame(place);
    return () => cancelAnimationFrame(raf);
  }, [still, agents.length]);

  return (
    <div ref={scene} className={cx("orbit-scene", still && "still", compact && "compact")} aria-hidden>
      <div className="orbit-halo" />
      <svg className="orbit-rings" viewBox="-100 -50 200 100" preserveAspectRatio="xMidYMid meet">
        <g transform="rotate(-9)">
          <ellipse rx="96" ry="30" className="ring-outer" />
          <ellipse rx="80" ry="27.2" className="ring-mid" />
          <ellipse rx="52" ry="17.7" className="ring-inner" />
        </g>
      </svg>
      <div className="orbit-core">
        <div className="core-sphere">
          <svg viewBox="0 0 64 64" className="core-mark">
            <defs>
              <linearGradient id="coreGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="#c9c0ff" />
                <stop offset=".5" stopColor="#8fe3ff" />
                <stop offset="1" stopColor="#7df0c9" />
              </linearGradient>
            </defs>
            <path d="M18 46V18l28 28V18" fill="none" stroke="url(#coreGrad)" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </div>
      </div>
      {agents.slice(0, 6).map((a, i) => (
        <div
          key={a.id}
          ref={(el) => {
            nodes.current[i] = el;
          }}
          className="orbit-node"
          style={{ "--c": a.color } as React.CSSProperties}
          title={a.name}
        >
          <DynamicIcon name={a.icon} size={compact ? 14 : 19} />
        </div>
      ))}
      {!still && Array.from({ length: 14 }).map((_, i) => <span key={i} className="spark" style={{ "--i": i } as React.CSSProperties} />)}
    </div>
  );
}

export function HeroScene() {
  const scene = useStore((s) => s.config?.spline_scene);
  const enabled = useStore((s) => s.settings.scene3d);
  const [loaded, setLoaded] = useState(false);
  const [timedOut, setTimedOut] = useState(false);

  useEffect(() => {
    if (!scene || !enabled) return;
    const t = setTimeout(() => setTimedOut(true), 15000);
    return () => clearTimeout(t);
  }, [scene, enabled]);

  if (!enabled) return <OrbitCore still />;
  if (!scene || (timedOut && !loaded)) return <OrbitCore />;

  const fallback = <OrbitCore />;
  return (
    <div className="spline-wrap">
      {!loaded && <div className="spline-fallback">{fallback}</div>}
      <SceneBoundary fallback={fallback}>
        <Suspense fallback={null}>
          <Spline scene={scene} onLoad={() => setLoaded(true)} className={cx("spline-canvas", loaded && "ready")} />
        </Suspense>
      </SceneBoundary>
    </div>
  );
}

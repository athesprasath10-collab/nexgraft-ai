import { cx } from "../lib/utils";

/**
 * Animated SVG signature per workspace: constellation (General), double helix
 * (Bioinformatics), ECG trace (Medical), circuit traces (Hardware). Pure SVG +
 * CSS stroke animations — no canvas, negligible GPU cost.
 */
export function WorkspaceMotif({ kind, color, className }: { kind: string; color: string; className?: string }) {
  const style = { "--c": color } as React.CSSProperties;
  if (kind === "code") {
    const strandA: string[] = [];
    const strandB: string[] = [];
    const rungs: [number, number, number][] = [];
    for (let x = 0; x <= 600; x += 6) {
      const y1 = 60 + Math.sin(x / 38) * 34;
      const y2 = 60 - Math.sin(x / 38) * 34;
      strandA.push(`${x === 0 ? "M" : "L"}${x} ${y1.toFixed(1)}`);
      strandB.push(`${x === 0 ? "M" : "L"}${x} ${y2.toFixed(1)}`);
      if (x % 24 === 0) rungs.push([x, y1, y2]);
    }
    return (
      <svg className={cx("motif motif-helix", className)} viewBox="0 0 600 120" preserveAspectRatio="xMidYMid slice" style={style} aria-hidden>
        {rungs.map(([x, a, b]) => (
          <line key={x} x1={x} x2={x} y1={a} y2={b} className="rung" style={{ animationDelay: `${(x / 600) * -3}s` }} />
        ))}
        <path d={strandA.join(" ")} className="strand" />
        <path d={strandB.join(" ")} className="strand b" />
      </svg>
    );
  }
  if (kind === "research") {
    const beat = "l14 0 l6 -10 l6 10 l8 0 l4 8 l6 -52 l6 62 l5 -18 l12 0 l10 -9 l10 9 l20 0";
    const d = `M0 70 ${Array.from({ length: 5 }, () => beat).join(" ")} l40 0`;
    return (
      <svg className={cx("motif motif-ecg", className)} viewBox="0 0 700 120" preserveAspectRatio="xMidYMid slice" style={style} aria-hidden>
        <path d={d} className="trace-bg" />
        <path d={d} className="trace" pathLength={1} />
      </svg>
    );
  }
  if (kind === "engineering") {
    const traces = [
      "M0 30 H120 L150 60 H300 L330 30 H460 L490 60 H700",
      "M0 90 H80 L110 60 H200 M240 60 H260 L290 90 H520 L550 60 H700",
      "M40 0 V20 L60 40 V120 M380 0 V30 L400 50 V120 M620 0 V40 L600 60 V120",
    ];
    const pads: [number, number][] = [[120, 30], [300, 60], [460, 30], [200, 60], [520, 90], [60, 40], [400, 50], [600, 60]];
    return (
      <svg className={cx("motif motif-circuit", className)} viewBox="0 0 700 120" preserveAspectRatio="xMidYMid slice" style={style} aria-hidden>
        {traces.map((d, i) => (
          <g key={i}>
            <path d={d} className="wire" />
            <path d={d} className="pulse" pathLength={1} style={{ animationDelay: `${i * -1.3}s` }} />
          </g>
        ))}
        {pads.map(([x, y]) => (
          <circle key={`${x}-${y}`} cx={x} cy={y} r={3.5} className="pad" />
        ))}
      </svg>
    );
  }
  // chat / general: constellation
  const stars: [number, number][] = [[40, 80], [110, 30], [170, 70], [240, 25], [300, 85], [360, 45], [430, 90], [490, 35], [560, 70], [640, 30]];
  return (
    <svg className={cx("motif motif-stars", className)} viewBox="0 0 700 120" preserveAspectRatio="xMidYMid slice" style={style} aria-hidden>
      <polyline points={stars.map((p) => p.join(",")).join(" ")} className="link" />
      {stars.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 3.2 : 2.2} className="star" style={{ animationDelay: `${i * -0.37}s` }} />
      ))}
    </svg>
  );
}

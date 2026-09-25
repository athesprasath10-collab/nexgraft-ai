import {
  Box,
  Building2,
  CircuitBoard,
  Cog,
  Cpu,
  Dna,
  HeartPulse,
  Microscope,
  Sparkles,
  Workflow,
  Zap,
  type LucideIcon,
  type LucideProps,
} from "lucide-react";

const ICONS: Record<string, LucideIcon> = {
  sparkles: Sparkles,
  dna: Dna,
  microscope: Microscope,
  cpu: Cpu,
  "heart-pulse": HeartPulse,
  "circuit-board": CircuitBoard,
  cog: Cog,
  building: Building2,
  zap: Zap,
  orchestrator: Workflow,
};

export function DynamicIcon({ name, ...props }: { name: string } & LucideProps) {
  const Cmp = ICONS[name] || Box;
  return <Cmp {...props} />;
}

/** Rounded, colour-tinted icon tile used for workspaces and plugins. */
export function IconTile({ name, color, size = 34, iconSize = 17 }: { name: string; color: string; size?: number; iconSize?: number }) {
  return (
    <span
      className="icon-tile"
      style={{
        width: size,
        height: size,
        color,
        background: `color-mix(in srgb, ${color} 14%, transparent)`,
        borderColor: `color-mix(in srgb, ${color} 30%, transparent)`,
      }}
    >
      <DynamicIcon name={name} size={iconSize} strokeWidth={2} />
    </span>
  );
}

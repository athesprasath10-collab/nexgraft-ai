# NEXGRAFT design system

The interface and its Figma file share one set of tokens, so designers and the code stay in sync.

**Figma file:** [NEXGRAFT AI — Design System](https://www.figma.com/design/lmdUNL99MpkJhzGsA1jBNl) (in your Figma drafts)

| Page | Contents |
|---|---|
| Foundations | Cover, colour tokens, typography, radius and spacing boards |
| Components | 16 Lucide icon components, Button, Chip, Icon tile, Pipeline step, Nav item, Workspace card, Composer, Task result |
| Screens | *Home — Orchestrator* and *Orchestrator — Plan review*, built from component instances |

The file was created on the Figma Starter plan, which limits files to 3 pages and variables to one mode, so the variables hold the **dark** theme. Light-theme values live in `frontend/src/styles/tokens.css` (`[data-theme="light"]`).

## Tokens

| Figma variable | CSS variable | Value (dark) |
|---|---|---|
| `bg/base`, `bg/raised` | `--bg`, `--bg-2` | `#06070C`, `#0A0C13` |
| `surface/solid`, `surface/raised` | `--surface-solid`, `--surface-raised` | `#0E1119`, `#131723` |
| `surface/glass`, `surface/glass-strong` | `--surface`, `--surface-2` | white at 3.5% / 6% |
| `border/default`, `border/strong` | `--border`, `--border-2` | white at 7.5% / 13% |
| `text/primary`, `text/secondary`, `text/tertiary` | `--text`, `--text-2`, `--text-3` | `#EEF0F7`, `#A8ADC2`, `#6C7189` |
| `workspace/general` | `--general` | `#8B7CFF` |
| `workspace/bioinformatics` | `--bio` | `#2DD4A0` |
| `workspace/medical` | `--medical` | `#4CC9F0` |
| `workspace/hardware` | `--hardware` | `#FFB547` |
| `tint/*`, `edge/*` | `color-mix(... 14% / 45%)` | workspace colour at 14% (fills) / 45% (borders) |
| `status/success`, `warning`, `danger` | `--success`, `--warning`, `--danger` | `#34D399`, `#FBBF24`, `#FF6B81` |
| `radius/xs … xl` | `--radius-xs … --radius-xl` | 6, 10, 14, 20, 28 px |
| `space/1 … 8` | — | 4-pt scale (4–32 px) |

Brand gradient (primary button, hero composer border, synthesis card): `#A594FF → #6AB8FF → #3FE0B0 → #FFC266`.

Type: **Space Grotesk** (display and headings), **Inter** (UI text), **JetBrains Mono** (code, metrics, model names). All three are bundled with the app via Fontsource, so the UI works offline.

## Rules the UI follows

- **Colour means something:** each workspace keeps its colour everywhere: sidebar, chips, task graph, result cards, citations, 3D satellites and workspace motifs.
- **Glass on near-black:** translucent surfaces, 1 px hairline borders and backdrop blur. The background aurora is static so it doesn't take GPU time from the local model.
- **One gradient per view:** the brand gradient marks the single highest-emphasis action.
- **Verified vs generated:** deterministic tool output is marked **Computed**; citations are numbered and link to their sources.
- **User control is visible:** every workspace states what stays under the user's control.

## Signature UI pieces

- **Interactive 3D hero** (`frontend/src/components/three/`): a three.js scene with a glass orchestrator core, workspace satellites on a tilted orbit, connection beams with travelling data pulses, and a particle field. Hover a satellite to see its name; click to open that workspace. It requests the low-power GPU, renders at up to 45 fps and stops rendering when off-screen or hidden. Settings → *3D hero* switches between interactive WebGL, a lite CSS orbit, and off. Priority order: Spline scene (if configured) → WebGL → lite orbit.
- **Custom 3D model:** put a `hero.glb` in `frontend/public/models/` (or set `NEXGRAFT_HERO_MODEL`) to replace the procedural core with your own model, e.g. exported from Spline, Blender or an image-to-3D tool.
- **Workspace motifs** (`WorkspaceMotif.tsx`): animated SVG signatures in each workspace header — constellation (General), double helix (Bioinformatics), ECG trace (Medical), circuit traces with pulses (Hardware).
- **Command palette** (Ctrl/⌘ + K): jump to workspaces and pages, start example requests, reopen recent conversations, switch theme, open settings.
- **Spotlight cards:** home and workspace cards pick up a soft glow in the workspace colour that follows the cursor.

## Keeping Figma and code in sync

1. Change a token in `tokens.css` **and** the matching Figma variable. The variables carry WEB code syntax such as `var(--general)`, so Dev Mode shows the CSS name.
2. New components: build in React first, then add a Figma component using the same variable bindings.
3. The Starter plan allows about 20 Figma MCP calls a month, so batch design-system updates.

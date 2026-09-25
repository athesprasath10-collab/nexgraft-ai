# 3D hero with Spline

The home page has a 3D "hero" above *What are you working on?*. Out of the box it shows a built-in, offline animation: the four workspaces orbiting the NEXGRAFT core. You can replace it with your own [Spline](https://spline.design) scene without touching any code.

## 1. Design the scene in Spline

A scene that matches the product story and the UI palette:

- **Core:** a glossy sphere or rounded icosahedron at the centre (the orchestrator). Use a dark purple material (`#2a2350`) with a subtle fresnel glow (`#a594ff`).
- **Four satellites** on a tilted orbit (about 65° from the camera), one per workspace:
  - General AI — violet `#8b7cff`
  - Bioinformatics AI — emerald `#2dd4a0` (a small double-helix works well)
  - Medical Research AI — cyan `#4cc9f0`
  - Hardware Design AI — amber `#ffb547` (a chip or gear)
- **Orbit rings:** thin torus shapes with a low-opacity emissive material.
- **Motion:** one slow looping rotation of the orbit group (20–30 s per turn). Optionally, a hover state that scales the satellites.
- **Background:** transparent. Turn off the scene background colour so the app's aurora shows through.
- **Canvas:** about 1200 × 520, with the camera framing the orbit.

### Keep it light — the GPU is shared with the AI model

On a GTX 1650 Ti the same GPU runs Qwen. Keep the scene cheap:

- Under ~50k triangles; prefer simple primitives.
- No real-time shadows, depth of field or heavy post-processing (bloom at low intensity is fine).
- Use a single light plus emissive materials instead of many lights.
- Disable physics and game controls.

## 2. Connect it to NEXGRAFT

**Option A — hosted URL.** In Spline: *Export → Code → React*, then copy the scene URL (it looks like `https://prod.spline.design/XXXXXXXX/scene.splinecode`). Add it to `.env`:

```
NEXGRAFT_SPLINE_SCENE=https://prod.spline.design/XXXXXXXX/scene.splinecode
```

**Option B — fully offline.** Download the `scene.splinecode` file and put it in `frontend/public/spline/scene.splinecode`, then rebuild the interface (`cd frontend && npm run build`). NEXGRAFT detects the file automatically.

Restart `python run.py`. The Spline runtime (about 2 MB) loads only when a scene is configured. If the scene fails or takes longer than 15 s, the built-in orbit is shown instead. **Settings → 3D hero scene** turns the 3D hero off completely.

## Design language (UI inspiration)

The interface follows current AI-workspace design patterns:

- Deep near-black canvas with a faint grid and four static aurora glows, one per workspace colour.
- Glass panels (translucent surfaces, 1 px hairline borders, backdrop blur) and generous 14–28 px radii.
- One brand gradient (violet → sky → emerald → amber) that links the four workspaces. It is used sparingly: the primary button, the hero composer border and the synthesis card.
- Type: *Space Grotesk* for headings, *Inter* for UI text, *JetBrains Mono* for code and metrics (bundled, so it works offline).
- Colour means something: each workspace keeps its colour everywhere (sidebar, chips, task graph, result cards, citations).

All colours, radii and fonts are CSS variables in `frontend/src/styles/tokens.css`. Change them there to apply your own palette from Figma or a moodboard.

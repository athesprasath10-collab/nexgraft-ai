/**
 * NEXGRAFT hero scene (three.js): a glass orchestrator core, the specialised
 * workspaces orbiting on a tilted ring with connection beams and data pulses,
 * and a particle field.
 *
 * GPU etiquette — the GPU is shared with the local LLM:
 *  - requests the low-power GPU (integrated graphics on Optimus laptops),
 *  - caps pixel ratio and frame rate,
 *  - stops rendering entirely when hidden, off-screen or paused.
 */
import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { RoundedBoxGeometry } from "three/addons/geometries/RoundedBoxGeometry.js";
import { ICON_PATHS } from "./iconPaths";

export interface SceneAgent {
  id: string;
  name: string;
  color: string;
  icon: string;
}

export interface SceneOptions {
  agents: SceneAgent[];
  modelUrl?: string | null;
  onHover?: (agent: SceneAgent | null, x: number, y: number) => void;
  onSelect?: (agent: SceneAgent) => void;
  onReady?: () => void;
}

export interface SceneHandle {
  dispose: () => void;
  setPaused: (paused: boolean) => void;
}

const MAX_FPS = 45;
const ORBIT_R = 3.25;
const TILT_X = 1.18; // radians — how far the orbit plane leans back
const TILT_Z = -0.16;

export function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

function glowTexture(color: string, soft = 0.55): THREE.Texture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, color);
  g.addColorStop(soft * 0.4, color + "88");
  g.addColorStop(1, color + "00");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function iconTexture(icon: string, color: string): THREE.Texture {
  const size = 128;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  ctx.translate(size * 0.2, size * 0.2);
  ctx.scale((size * 0.6) / 24, (size * 0.6) / 24);
  ctx.lineWidth = 2;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = color;
  ctx.shadowColor = color;
  ctx.shadowBlur = 3;
  for (const d of ICON_PATHS[icon] || ["M12 2a10 10 0 1 0 0.01 0"]) ctx.stroke(new Path2D(d));
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.anisotropy = 4;
  return tex;
}

function markTexture(): THREE.Texture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createLinearGradient(0, 0, size, size);
  g.addColorStop(0, "#c9c0ff");
  g.addColorStop(0.5, "#8fe3ff");
  g.addColorStop(1, "#7df0c9");
  ctx.scale(size / 64, size / 64);
  ctx.lineWidth = 6;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.strokeStyle = g;
  ctx.shadowColor = "#8fe3ff";
  ctx.shadowBlur = 4;
  ctx.stroke(new Path2D("M18 46V18l28 28V18"));
  const tex = new THREE.CanvasTexture(canvas);
  tex.colorSpace = THREE.SRGBColorSpace;
  return tex;
}

function ringLine(radius: number, color: string, opacity: number, dashed = false): THREE.Line {
  const pts: THREE.Vector3[] = [];
  for (let i = 0; i <= 160; i++) {
    const a = (i / 160) * Math.PI * 2;
    pts.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0));
  }
  const geo = new THREE.BufferGeometry().setFromPoints(pts);
  const mat = dashed
    ? new THREE.LineDashedMaterial({ color, transparent: true, opacity, dashSize: 0.12, gapSize: 0.22, depthWrite: false })
    : new THREE.LineBasicMaterial({ color, transparent: true, opacity, depthWrite: false });
  const line = new THREE.Line(geo, mat);
  if (dashed) line.computeLineDistances();
  return line;
}

export function mountScene(host: HTMLElement, opts: SceneOptions): SceneHandle {
  const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.1;
  renderer.setClearColor(0x000000, 0);
  renderer.domElement.className = "hero3d-canvas";
  host.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(32, 1, 0.1, 100);
  camera.position.set(0, 1.2, 13);
  const disposables: { dispose: () => void }[] = [];
  const track = <T extends { dispose: () => void }>(x: T) => (disposables.push(x), x);

  scene.add(new THREE.AmbientLight(0xffffff, 0.45));
  const key = new THREE.DirectionalLight(0xc9c0ff, 1.6);
  key.position.set(3, 5, 6);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x4cc9f0, 1.2);
  rim.position.set(-5, -2, -4);
  scene.add(rim);

  // ------------------------------------------------------------- core
  const core = new THREE.Group();
  scene.add(core);
  const coreGlow = new THREE.Sprite(
    track(new THREE.SpriteMaterial({ map: track(glowTexture("#8b7cff", 0.6)), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false })),
  );
  coreGlow.scale.setScalar(6.2);
  core.add(coreGlow);
  const coreLight = new THREE.PointLight(0x8b7cff, 5, 12, 1.6);
  core.add(coreLight);

  const procedural = new THREE.Group();
  core.add(procedural);
  const sphere = new THREE.Mesh(
    track(new THREE.IcosahedronGeometry(0.92, 6)),
    track(
      new THREE.MeshPhysicalMaterial({
        color: 0x241d4d,
        emissive: 0x2a1f6e,
        emissiveIntensity: 0.7,
        roughness: 0.18,
        metalness: 0.25,
        clearcoat: 1,
        clearcoatRoughness: 0.1,
        iridescence: 0.6,
        iridescenceIOR: 1.4,
        sheen: 0.5,
        sheenColor: new THREE.Color(0xa594ff),
      }),
    ),
  );
  procedural.add(sphere);
  const lattice = new THREE.Mesh(
    track(new THREE.IcosahedronGeometry(1.22, 1)),
    track(new THREE.MeshBasicMaterial({ color: 0xa594ff, wireframe: true, transparent: true, opacity: 0.32 })),
  );
  procedural.add(lattice);
  const shell = new THREE.LineSegments(
    track(new THREE.EdgesGeometry(track(new THREE.IcosahedronGeometry(1.62, 0)))),
    track(new THREE.LineBasicMaterial({ color: 0x6ab8ff, transparent: true, opacity: 0.2 })),
  );
  procedural.add(shell);

  const mark = new THREE.Sprite(track(new THREE.SpriteMaterial({ map: track(markTexture()), transparent: true, depthTest: false })));
  mark.scale.setScalar(0.95);
  mark.renderOrder = 5;
  core.add(mark);

  if (opts.modelUrl) {
    new GLTFLoader().load(
      opts.modelUrl,
      (gltf) => {
        const model = gltf.scene;
        const box = new THREE.Box3().setFromObject(model);
        const size = box.getSize(new THREE.Vector3()).length() || 1;
        model.scale.setScalar(2.6 / size);
        box.setFromObject(model);
        model.position.sub(box.getCenter(new THREE.Vector3()));
        procedural.remove(sphere, lattice);
        procedural.add(model);
      },
      undefined,
      () => {
        /* keep the procedural core if the model fails to load */
      },
    );
  }

  // ------------------------------------------------------------ orbit
  const orbit = new THREE.Group();
  orbit.rotation.set(TILT_X, 0, TILT_Z);
  scene.add(orbit);
  orbit.add(ringLine(ORBIT_R, "#a594ff", 0.42));
  orbit.add(ringLine(ORBIT_R * 1.33, "#ffffff", 0.16, true));
  orbit.add(ringLine(ORBIT_R * 0.64, "#2dd4a0", 0.22, true));

  interface Sat {
    agent: SceneAgent;
    group: THREE.Group;
    body: THREE.Mesh;
    beam: THREE.Line;
    pulse: THREE.Sprite;
    phase: number;
    pulseT: number;
  }
  const sats: Sat[] = [];
  const boxGeo = track(new RoundedBoxGeometry(0.62, 0.62, 0.62, 4, 0.16));
  opts.agents.slice(0, 6).forEach((agent, i, arr) => {
    const color = new THREE.Color(agent.color);
    const group = new THREE.Group();
    const body = new THREE.Mesh(
      boxGeo,
      track(
        new THREE.MeshPhysicalMaterial({
          color: color.clone().multiplyScalar(0.35),
          emissive: color,
          emissiveIntensity: 0.55,
          roughness: 0.3,
          metalness: 0.2,
          clearcoat: 1,
          transparent: true,
          opacity: 0.92,
        }),
      ),
    );
    body.userData.agent = agent;
    group.add(body);
    const halo = new THREE.Sprite(
      track(new THREE.SpriteMaterial({ map: track(glowTexture(agent.color)), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false })),
    );
    halo.scale.setScalar(2.1);
    group.add(halo);
    const icon = new THREE.Sprite(track(new THREE.SpriteMaterial({ map: track(iconTexture(agent.icon, "#ffffff")), transparent: true, depthTest: false })));
    icon.scale.setScalar(0.5);
    icon.renderOrder = 10;
    group.add(icon);
    scene.add(group);

    const beamGeo = track(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(), new THREE.Vector3()]));
    const beam = new THREE.Line(beamGeo, track(new THREE.LineBasicMaterial({ color: agent.color, transparent: true, opacity: 0.28, depthWrite: false })));
    scene.add(beam);
    const pulse = new THREE.Sprite(
      track(new THREE.SpriteMaterial({ map: track(glowTexture(agent.color, 0.3)), blending: THREE.AdditiveBlending, transparent: true, depthWrite: false })),
    );
    pulse.scale.setScalar(0.45);
    scene.add(pulse);
    sats.push({ agent, group, body, beam, pulse, phase: (i / arr.length) * Math.PI * 2 + 0.5, pulseT: i / arr.length });
  });

  // -------------------------------------------------------- particles
  const count = 700;
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i++) {
    const r = 5 + Math.random() * 6;
    const t = Math.random() * Math.PI * 2;
    const p = Math.acos(2 * Math.random() - 1);
    positions.set([r * Math.sin(p) * Math.cos(t), r * Math.cos(p) * 0.55, r * Math.sin(p) * Math.sin(t) - 2], i * 3);
  }
  const pGeo = track(new THREE.BufferGeometry());
  pGeo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  const particles = new THREE.Points(
    pGeo,
    track(new THREE.PointsMaterial({ color: 0xcfc7ff, size: 0.035, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false })),
  );
  scene.add(particles);

  // ------------------------------------------------------ interaction
  const pointer = new THREE.Vector2(0, 0);
  const parallax = new THREE.Vector2(0, 0);
  const raycaster = new THREE.Raycaster();
  let hovered: Sat | null = null;
  const onMove = (e: PointerEvent) => {
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set(((e.clientX - rect.left) / rect.width) * 2 - 1, -((e.clientY - rect.top) / rect.height) * 2 + 1);
    raycaster.setFromCamera(pointer, camera);
    const hit = raycaster.intersectObjects(sats.map((s) => s.body))[0];
    const sat = hit ? sats.find((s) => s.body === hit.object) || null : null;
    if (sat !== hovered) {
      hovered = sat;
      renderer.domElement.style.cursor = sat ? "pointer" : "";
    }
    opts.onHover?.(sat ? sat.agent : null, e.clientX - rect.left, e.clientY - rect.top);
    if (paused || !running) renderOnce();
  };
  const onLeave = () => {
    pointer.set(0, 0);
    hovered = null;
    renderer.domElement.style.cursor = "";
    opts.onHover?.(null, 0, 0);
  };
  const onClick = () => {
    if (hovered) opts.onSelect?.(hovered.agent);
  };
  renderer.domElement.addEventListener("pointermove", onMove);
  renderer.domElement.addEventListener("pointerleave", onLeave);
  renderer.domElement.addEventListener("click", onClick);

  // ------------------------------------------------------------ loop
  let elapsed = 0;
  let lastTick = performance.now();
  let raf = 0;
  let running = false;
  let paused = false;
  let visible = true;
  let lastFrame = 0;
  const tmp = new THREE.Vector3();

  const update = (dt: number) => {
    elapsed += dt;
    procedural.rotation.y += dt * 0.25;
    lattice.rotation.x += dt * 0.12;
    shell.rotation.z -= dt * 0.08;
    coreGlow.material.opacity = 0.85 + Math.sin(elapsed * 1.6) * 0.12;
    particles.rotation.y += dt * 0.015;
    parallax.lerp(pointer, 0.04);
    camera.position.x = parallax.x * 0.9;
    camera.position.y = 1.2 + parallax.y * 0.5;
    camera.lookAt(0, -0.55, 0);

    for (const s of sats) {
      s.phase += dt * 0.18;
      tmp.set(Math.cos(s.phase) * ORBIT_R, Math.sin(s.phase) * ORBIT_R, 0).applyEuler(orbit.rotation);
      s.group.position.copy(tmp);
      s.body.rotation.x += dt * 0.5;
      s.body.rotation.y += dt * 0.35;
      const target = s === hovered ? 1.28 : 1;
      s.group.scale.setScalar(THREE.MathUtils.lerp(s.group.scale.x, target, 0.15));
      const attr = s.beam.geometry.getAttribute("position") as THREE.BufferAttribute;
      attr.setXYZ(1, tmp.x, tmp.y, tmp.z);
      attr.needsUpdate = true;
      s.pulseT = (s.pulseT + dt * 0.35) % 1;
      s.pulse.position.copy(tmp).multiplyScalar(s.pulseT);
      (s.pulse.material as THREE.SpriteMaterial).opacity = Math.sin(s.pulseT * Math.PI);
    }
  };

  const renderOnce = () => renderer.render(scene, camera);

  const frame = (now: number) => {
    raf = requestAnimationFrame(frame);
    if (now - lastFrame < 1000 / MAX_FPS) return;
    lastFrame = now;
    update(Math.min((now - lastTick) / 1000, 0.1));
    lastTick = now;
    renderOnce();
  };

  const start = () => {
    if (running || paused || !visible || reduced) return;
    running = true;
    lastTick = performance.now();
    raf = requestAnimationFrame(frame);
  };
  const stop = () => {
    running = false;
    cancelAnimationFrame(raf);
  };

  const resize = () => {
    const w = host.clientWidth || 1;
    const h = host.clientHeight || 1;
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    // keep the whole orbit in view on narrow screens
    camera.position.z = w / h < 1.4 ? 16 : 13;
    camera.updateProjectionMatrix();
    renderOnce();
  };
  const ro = new ResizeObserver(resize);
  ro.observe(host);
  const io = new IntersectionObserver(([entry]) => {
    visible = entry.isIntersecting;
    if (visible) start();
    else stop();
  });
  io.observe(host);
  const onVisibility = () => (document.hidden ? stop() : start());
  document.addEventListener("visibilitychange", onVisibility);

  resize();
  update(0.016);
  renderOnce();
  opts.onReady?.();
  start();

  return {
    setPaused(p: boolean) {
      paused = p;
      if (p) stop();
      else start();
    },
    dispose() {
      stop();
      ro.disconnect();
      io.disconnect();
      document.removeEventListener("visibilitychange", onVisibility);
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerleave", onLeave);
      renderer.domElement.removeEventListener("click", onClick);
      scene.traverse((o) => {
        const m = o as THREE.Mesh;
        if (m.geometry) m.geometry.dispose();
      });
      for (const d of disposables) d.dispose();
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
}

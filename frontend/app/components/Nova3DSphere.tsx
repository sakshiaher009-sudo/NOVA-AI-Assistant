"use client";

import { useRef, useMemo, useState, useCallback, useEffect } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

// ── Types ────────────────────────────────────────────────────────────────────

export type NovaVisualState = "dormant" | "listening" | "speaking" | "thinking" | "error";

interface Nova3DSphereProps {
  state: NovaVisualState;
  amplitude: number;
  onClick: () => void;
}

export function mapToVisualState(jarvisState: string): NovaVisualState {
  switch (jarvisState) {
    case "LISTENING_WAKE":
    case "WAKE_DETECTED":
    case "LISTENING_CMD":
      return "listening";
    case "SPEAKING":
      return "speaking";
    case "PROCESSING":
    case "THINKING":
    case "PLANNING":
    case "VERIFYING":
    case "RESPONDING":
      return "thinking";
    case "ERROR":
      return "error";
    default:
      return "dormant";
  }
}

// ── Sky-Blue State Configurations ────────────────────────────────────────────

const STATE_CONFIG = {
  dormant: {
    coreGlow: 0.75,
    rotationSpeed: 0.18,
    waveSpeed: 0.32,
    ringSpeed: 0.25,
    pulseSpeed: 1.1,
    pulseAmp: 0.02,
    innerLight: 2.2,
    flareBrightness: 0.95,
    lightColor: new THREE.Color("#38bdf8"),
    waveColor: new THREE.Color("#0ea5e9"),
    crestColor: new THREE.Color("#7dd3fc"),
    innerCoreColor: new THREE.Color("#0284c7"),
  },
  listening: {
    coreGlow: 1.15,
    rotationSpeed: 0.35,
    waveSpeed: 0.7,
    ringSpeed: 0.65,
    pulseSpeed: 2.2,
    pulseAmp: 0.06,
    innerLight: 3.2,
    flareBrightness: 1.4,
    lightColor: new THREE.Color("#7dd3fc"),
    waveColor: new THREE.Color("#38bdf8"),
    crestColor: new THREE.Color("#bae6fd"),
    innerCoreColor: new THREE.Color("#0ea5e9"),
  },
  speaking: {
    coreGlow: 1.0,
    rotationSpeed: 0.28,
    waveSpeed: 0.6,
    ringSpeed: 0.5,
    pulseSpeed: 2.5,
    pulseAmp: 0.05,
    innerLight: 2.7,
    flareBrightness: 1.2,
    lightColor: new THREE.Color("#38bdf8"),
    waveColor: new THREE.Color("#0ea5e9"),
    crestColor: new THREE.Color("#7dd3fc"),
    innerCoreColor: new THREE.Color("#0284c7"),
  },
  thinking: {
    coreGlow: 1.05,
    rotationSpeed: 0.6,
    waveSpeed: 1.0,
    ringSpeed: 0.9,
    pulseSpeed: 1.8,
    pulseAmp: 0.035,
    innerLight: 2.9,
    flareBrightness: 1.25,
    lightColor: new THREE.Color("#38bdf8"),
    waveColor: new THREE.Color("#0284c7"),
    crestColor: new THREE.Color("#60a5fa"),
    innerCoreColor: new THREE.Color("#0369a1"),
  },
  error: {
    coreGlow: 0.65,
    rotationSpeed: 0.1,
    waveSpeed: 0.18,
    ringSpeed: 0.14,
    pulseSpeed: 0.6,
    pulseAmp: 0.015,
    innerLight: 1.2,
    flareBrightness: 0.6,
    lightColor: new THREE.Color("#ef4444"),
    waveColor: new THREE.Color("#b91c1c"),
    crestColor: new THREE.Color("#f87171"),
    innerCoreColor: new THREE.Color("#7f1d1d"),
  },
};

function lerp(start: number, end: number, factor: number) {
  return start + (end - start) * factor;
}

// ── Sky-Blue Constellation Wave Texture Generator ────────────────────────────

function createConstellationWaveTexture(): THREE.CanvasTexture {
  const size = 1024;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;

  // Smooth Sky Blue gradient (electric sky blue to vivid cyan to soft frost)
  const grad = ctx.createLinearGradient(0, 0, size, size);
  grad.addColorStop(0, "#0284c7");    // deep electric sky blue
  grad.addColorStop(0.35, "#0ea5e9"); // vivid sky blue
  grad.addColorStop(0.7, "#38bdf8");  // bright cyan sky blue
  grad.addColorStop(0.9, "#7dd3fc");  // soft cyan
  grad.addColorStop(1, "#bae6fd");    // luminous sky frost
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  // Soft glowing atmospheric wave energy
  for (let i = 0; i < 5; i++) {
    const yCenter = (i / 5) * size;
    const radial = ctx.createRadialGradient(
      size * 0.5,
      yCenter,
      30,
      size * 0.5,
      yCenter,
      size * 0.55
    );
    radial.addColorStop(0, "rgba(224, 242, 254, 0.65)");
    radial.addColorStop(0.4, "rgba(56, 189, 248, 0.4)");
    radial.addColorStop(1, "rgba(14, 165, 233, 0)");
    ctx.fillStyle = radial;
    ctx.fillRect(0, 0, size, size);
  }

  // 45 constellation star nodes
  const stars: { x: number; y: number; r: number }[] = [];
  for (let i = 0; i < 45; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const r = Math.random() * 2.4 + 1.2;
    stars.push({ x, y, r });
  }

  // Draw delicate constellation connecting threads
  ctx.strokeStyle = "rgba(240, 249, 255, 0.45)";
  ctx.lineWidth = 0.9;
  for (let i = 0; i < stars.length; i++) {
    for (let j = i + 1; j < stars.length; j++) {
      const dx = stars[i].x - stars[j].x;
      const dy = stars[i].y - stars[j].y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < 115) {
        ctx.beginPath();
        ctx.moveTo(stars[i].x, stars[i].y);
        ctx.lineTo(stars[j].x, stars[j].y);
        ctx.stroke();
      }
    }
  }

  // Draw glowing star nodes
  for (const star of stars) {
    const starGlow = ctx.createRadialGradient(
      star.x,
      star.y,
      0,
      star.x,
      star.y,
      star.r * 3.8
    );
    starGlow.addColorStop(0, "rgba(255, 255, 255, 1)");
    starGlow.addColorStop(0.3, "rgba(224, 242, 254, 0.9)");
    starGlow.addColorStop(1, "rgba(56, 189, 248, 0)");
    ctx.fillStyle = starGlow;
    ctx.beginPath();
    ctx.arc(star.x, star.y, star.r * 3.8, 0, Math.PI * 2);
    ctx.fill();
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.wrapS = THREE.RepeatWrapping;
  texture.wrapT = THREE.RepeatWrapping;
  texture.needsUpdate = true;
  return texture;
}

// ── Parametric 3D S-Wave Fluid Geometry Generator ────────────────────────────

function createFluidWaveGeometry(
  type: "primary" | "secondary"
): THREE.BufferGeometry {
  const uSegments = 160;
  const vSegments = 32;
  const vertexCount = (uSegments + 1) * (vSegments + 1);
  const positions = new Float32Array(vertexCount * 3);
  const uvs = new Float32Array(vertexCount * 2);
  const indices: number[] = [];

  let idx = 0;
  let uvIdx = 0;

  for (let i = 0; i <= uSegments; i++) {
    const u = (i / uSegments) * Math.PI * 2;

    let x: number, y: number, z: number;
    let width: number;

    if (type === "primary") {
      const r = 0.74 + Math.sin(u * 2) * 0.04;
      x = Math.cos(u) * r;
      y = Math.sin(u) * 0.44 * Math.cos(u * 0.5);
      z = Math.sin(u) * r * 0.85;
      width = 0.38 + Math.sin(u) * 0.08;
    } else {
      const r = 0.68 + Math.cos(u * 3) * 0.03;
      x = Math.sin(u) * r * 0.9;
      y = -Math.cos(u) * 0.38 + Math.sin(u * 2) * 0.1;
      z = Math.cos(u) * r;
      width = 0.28 + Math.cos(u) * 0.06;
    }

    const spine = new THREE.Vector3(x, y, z);
    const normal = spine.clone().normalize();
    const tangent = new THREE.Vector3(
      -Math.sin(u),
      Math.cos(u * 2) * 0.3,
      Math.cos(u)
    ).normalize();
    const binormal = new THREE.Vector3().crossVectors(tangent, normal).normalize();

    for (let j = 0; j <= vSegments; j++) {
      const v = (j / vSegments - 0.5) * 2;
      const offsetDist = v * (width / 2);
      const arch = Math.cos(v * (Math.PI / 2)) * 0.06;
      const pt = spine
        .clone()
        .addScaledVector(binormal, offsetDist)
        .addScaledVector(normal, arch);

      positions[idx++] = pt.x;
      positions[idx++] = pt.y;
      positions[idx++] = pt.z;

      uvs[uvIdx++] = i / uSegments;
      uvs[uvIdx++] = j / vSegments;
    }
  }

  for (let i = 0; i < uSegments; i++) {
    for (let j = 0; j < vSegments; j++) {
      const row1 = i * (vSegments + 1);
      const row2 = (i + 1) * (vSegments + 1);
      indices.push(row1 + j, row2 + j, row1 + j + 1);
      indices.push(row2 + j, row2 + j + 1, row1 + j + 1);
    }
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geo.setAttribute("uv", new THREE.BufferAttribute(uvs, 2));
  geo.setIndex(indices);
  geo.computeVertexNormals();
  return geo;
}

// ── Brilliant Star Glint Flare Generator ─────────────────────────────────────

function createFlareTexture(): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement("canvas");
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext("2d")!;

  ctx.clearRect(0, 0, size, size);

  const cx = size / 2;
  const cy = size / 2;

  const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, 55);
  core.addColorStop(0, "rgba(255, 255, 255, 1)");
  core.addColorStop(0.25, "rgba(186, 230, 253, 0.95)");
  core.addColorStop(0.65, "rgba(56, 189, 248, 0.4)");
  core.addColorStop(1, "rgba(14, 165, 233, 0)");
  ctx.fillStyle = core;
  ctx.beginPath();
  ctx.arc(cx, cy, 55, 0, Math.PI * 2);
  ctx.fill();

  ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
  const drawSpike = (angle: number, length: number, width: number) => {
    ctx.save();
    ctx.translate(cx, cy);
    ctx.rotate(angle);
    ctx.beginPath();
    ctx.moveTo(0, -width);
    ctx.lineTo(length, 0);
    ctx.lineTo(0, width);
    ctx.lineTo(-length, 0);
    ctx.closePath();
    ctx.fill();
    ctx.restore();
  };

  drawSpike(0, 95, 4.5);
  drawSpike(Math.PI / 2, 95, 4.5);
  drawSpike(Math.PI / 4, 45, 2.5);
  drawSpike(-Math.PI / 4, 45, 2.5);

  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

// ── Sky-Blue Fluid S-Wave Energy System ──────────────────────────────────────

function FluidEnergyWaveSystem({
  state,
  amplitude,
}: {
  state: NovaVisualState;
  amplitude: number;
}) {
  const groupRef = useRef<THREE.Group>(null);
  const primaryMeshRef = useRef<THREE.Mesh>(null);
  const secondaryMeshRef = useRef<THREE.Mesh>(null);
  const primaryMatRef = useRef<THREE.MeshPhysicalMaterial>(null);
  const secondaryMatRef = useRef<THREE.MeshPhysicalMaterial>(null);
  const flareRef = useRef<THREE.Sprite>(null);

  const waveTex = useMemo(() => createConstellationWaveTexture(), []);
  const flareTex = useMemo(() => createFlareTexture(), []);

  const primaryGeo = useMemo(() => createFluidWaveGeometry("primary"), []);
  const secondaryGeo = useMemo(() => createFluidWaveGeometry("secondary"), []);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const cfg = STATE_CONFIG[state];
    const lerpFactor = 0.045;

    if (groupRef.current) {
      groupRef.current.rotation.y += cfg.waveSpeed * 0.008;
      groupRef.current.rotation.x = Math.sin(t * 0.22) * 0.08;
      groupRef.current.rotation.z = Math.cos(t * 0.18) * 0.06;
    }

    if (primaryMatRef.current) {
      primaryMatRef.current.color.lerp(cfg.crestColor, lerpFactor);
      primaryMatRef.current.emissive.lerp(cfg.waveColor, lerpFactor);
      primaryMatRef.current.emissiveIntensity = lerp(
        primaryMatRef.current.emissiveIntensity,
        cfg.coreGlow * 0.85 + amplitude * 0.45,
        lerpFactor
      );
    }

    if (secondaryMatRef.current) {
      secondaryMatRef.current.color.lerp(cfg.waveColor, lerpFactor);
      secondaryMatRef.current.emissive.lerp(cfg.innerCoreColor, lerpFactor);
      secondaryMatRef.current.emissiveIntensity = lerp(
        secondaryMatRef.current.emissiveIntensity,
        cfg.coreGlow * 0.65 + amplitude * 0.35,
        lerpFactor
      );
    }

    if (flareRef.current) {
      const flareScale = (0.42 + Math.sin(t * 3) * 0.04 + amplitude * 0.2) * cfg.flareBrightness;
      flareRef.current.scale.set(flareScale, flareScale, 1);
    }
  });

  return (
    <group ref={groupRef}>
      {/* Primary Sweeping S-Wave in Sky Blue */}
      <mesh ref={primaryMeshRef} geometry={primaryGeo}>
        <meshPhysicalMaterial
          ref={primaryMatRef}
          map={waveTex}
          color="#38bdf8"
          emissive="#0ea5e9"
          emissiveIntensity={0.8}
          roughness={0.08}
          metalness={0.12}
          clearcoat={1.0}
          clearcoatRoughness={0.05}
          transparent
          opacity={0.92}
          side={THREE.DoubleSide}
          blending={THREE.NormalBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Secondary Counter-Curving Wave Fold */}
      <mesh ref={secondaryMeshRef} geometry={secondaryGeo}>
        <meshPhysicalMaterial
          ref={secondaryMatRef}
          map={waveTex}
          color="#0ea5e9"
          emissive="#0284c7"
          emissiveIntensity={0.65}
          roughness={0.12}
          metalness={0.15}
          clearcoat={0.95}
          clearcoatRoughness={0.08}
          transparent
          opacity={0.84}
          side={THREE.DoubleSide}
          blending={THREE.NormalBlending}
          depthWrite={false}
        />
      </mesh>

      {/* Diamond Star Glint on Wave Crest */}
      <sprite ref={flareRef} position={[0.26, 0.08, 0.64]}>
        <spriteMaterial
          map={flareTex}
          transparent
          opacity={0.98}
          blending={THREE.AdditiveBlending}
          depthWrite={false}
        />
      </sprite>
    </group>
  );
}

// ── Floating Sky-Blue Satellite Beads ────────────────────────────────────────

interface SatelliteDef {
  radius: number;
  orbitRadiusX: number;
  orbitRadiusZ: number;
  tilt: [number, number, number];
  speed: number;
  phaseOffset: number;
  color: string;
}

function OrbitingSatelliteBeads({
  state,
}: {
  state: NovaVisualState;
}) {
  const beadsRef = useRef<THREE.Mesh[]>([]);

  const satellites: SatelliteDef[] = useMemo(
    () => [
      {
        radius: 0.065,
        orbitRadiusX: 1.58,
        orbitRadiusZ: 1.48,
        tilt: [0.38, 0, -0.28],
        speed: 0.7,
        phaseOffset: 0.4,
        color: "#38bdf8", // bright sky blue
      },
      {
        radius: 0.052,
        orbitRadiusX: 1.68,
        orbitRadiusZ: 1.56,
        tilt: [-0.42, 0, 0.36],
        speed: -0.6,
        phaseOffset: 2.1,
        color: "#0ea5e9", // vivid sky blue
      },
      {
        radius: 0.078,
        orbitRadiusX: 1.48,
        orbitRadiusZ: 1.42,
        tilt: [0.58, 0, 0.16],
        speed: 0.85,
        phaseOffset: 4.2,
        color: "#7dd3fc", // light cyan-sky
      },
      {
        radius: 0.042,
        orbitRadiusX: 1.78,
        orbitRadiusZ: 1.64,
        tilt: [-0.25, 0, -0.42],
        speed: -0.5,
        phaseOffset: 1.2,
        color: "#0284c7", // electric sky blue
      },
      {
        radius: 0.058,
        orbitRadiusX: 1.62,
        orbitRadiusZ: 1.52,
        tilt: [0.22, 0, 0.48],
        speed: 0.65,
        phaseOffset: 5.4,
        color: "#38bdf8",
      },
      {
        radius: 0.036,
        orbitRadiusX: 1.72,
        orbitRadiusZ: 1.60,
        tilt: [-0.48, 0, -0.22],
        speed: -0.75,
        phaseOffset: 3.5,
        color: "#0ea5e9",
      },
    ],
    []
  );

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const cfg = STATE_CONFIG[state];

    satellites.forEach((sat, i) => {
      const bead = beadsRef.current[i];
      if (!bead) return;

      const angle = t * sat.speed * cfg.ringSpeed * 0.8 + sat.phaseOffset;
      const x = Math.cos(angle) * sat.orbitRadiusX;
      const z = Math.sin(angle) * sat.orbitRadiusZ;

      const vec = new THREE.Vector3(x, 0, z);
      const euler = new THREE.Euler(...sat.tilt);
      vec.applyEuler(euler);

      bead.position.copy(vec);
    });
  });

  return (
    <group>
      {satellites.map((sat, i) => (
        <mesh
          key={i}
          ref={(el) => {
            if (el) beadsRef.current[i] = el;
          }}
        >
          <sphereGeometry args={[sat.radius, 24, 24]} />
          <meshPhysicalMaterial
            color={sat.color}
            emissive="#0284c7"
            emissiveIntensity={0.55}
            roughness={0.15}
            metalness={0.1}
            clearcoat={1.0}
            clearcoatRoughness={0.05}
          />
        </mesh>
      ))}
    </group>
  );
}

// ── 3D Visible Tubular Orbital Rings in Sky-Blue Shades ──────────────────────

function createEllipticalTube(
  rx: number,
  rz: number,
  tubeRadius = 0.011,
  segments = 140,
  radialSegments = 8
): THREE.BufferGeometry {
  const points: THREE.Vector3[] = [];
  for (let i = 0; i <= segments; i++) {
    const theta = (i / segments) * Math.PI * 2;
    points.push(new THREE.Vector3(Math.cos(theta) * rx, 0, Math.sin(theta) * rz));
  }
  const curve = new THREE.CatmullRomCurve3(points, true);
  return new THREE.TubeGeometry(curve, segments, tubeRadius, radialSegments, true);
}

function VisibleOrbitalRingsSystem({ state }: { state: NovaVisualState }) {
  // Distinctly visible 3D tubular rings with darkened central ring and cohesive sky-blue accents
  const ringsData = useMemo(() => {
    return [
      {
        // Central Orbital Ring - darkened high-contrast obsidian / deep navy
        rx: 1.58,
        rz: 1.48,
        tilt: [0.38, 0, -0.28] as [number, number, number],
        color: "#0a192f",      // dark obsidian navy
        emissive: "#075985",   // subtle dark cyan-slate glow
        emissiveIntensity: 0.35,
        tubeRadius: 0.012,
        roughness: 0.20,
        metalness: 0.35,
        opacity: 0.96,
        behindOpacity: 0.68,
        speed: 0.6,
      },
      {
        rx: 1.68,
        rz: 1.56,
        tilt: [-0.42, 0, 0.36] as [number, number, number],
        color: "#0284c7",      // deep electric sky blue
        emissive: "#0ea5e9",
        emissiveIntensity: 0.65,
        tubeRadius: 0.010,
        roughness: 0.15,
        metalness: 0.15,
        opacity: 0.92,
        behindOpacity: 0.55,
        speed: -0.55,
      },
      {
        rx: 1.48,
        rz: 1.42,
        tilt: [0.58, 0, 0.16] as [number, number, number],
        color: "#38bdf8",      // bright cyan sky blue
        emissive: "#0284c7",
        emissiveIntensity: 0.55,
        tubeRadius: 0.009,
        roughness: 0.15,
        metalness: 0.1,
        opacity: 0.88,
        behindOpacity: 0.50,
        speed: 0.75,
      },
      {
        rx: 1.78,
        rz: 1.64,
        tilt: [-0.25, 0, -0.42] as [number, number, number],
        color: "#0369a1",      // deep cobalt sky blue
        emissive: "#0284c7",
        emissiveIntensity: 0.60,
        tubeRadius: 0.010,
        roughness: 0.15,
        metalness: 0.15,
        opacity: 0.85,
        behindOpacity: 0.50,
        speed: -0.45,
      },
    ];
  }, []);

  const ringGeometries = useMemo(() => {
    return ringsData.map((r) => createEllipticalTube(r.rx, r.rz, r.tubeRadius));
  }, [ringsData]);

  const groupRefs = useRef<(THREE.Group | null)[]>([]);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const cfg = STATE_CONFIG[state];

    ringsData.forEach((r, i) => {
      const g = groupRefs.current[i];
      if (!g) return;
      // Smooth continuous 360-degree rotation along the orbital plane's normal axis
      g.rotation.y = t * r.speed * cfg.ringSpeed * 0.65;
    });
  });

  return (
    <group>
      {ringsData.map((ring, i) => (
        <group key={i} rotation={ring.tilt}>
          <group
            ref={(el) => {
              groupRefs.current[i] = el;
            }}
          >
            {/* Pass 1: Front and exterior segments (depth <= sphere depth) */}
            <mesh geometry={ringGeometries[i]} renderOrder={10}>
              <meshPhysicalMaterial
                color={ring.color}
                emissive={ring.emissive}
                emissiveIntensity={ring.emissiveIntensity}
                roughness={ring.roughness}
                metalness={ring.metalness}
                clearcoat={1.0}
                clearcoatRoughness={0.05}
                transparent
                opacity={ring.opacity}
                depthFunc={THREE.LessEqualDepth}
                depthWrite={false}
              />
            </mesh>

            {/* Pass 2: Continuous 360° through-sphere segments (depth > sphere depth) */}
            <mesh geometry={ringGeometries[i]} renderOrder={11}>
              <meshPhysicalMaterial
                color={ring.color}
                emissive={ring.emissive}
                emissiveIntensity={ring.emissiveIntensity * 0.75}
                roughness={0.15}
                metalness={0.1}
                transparent
                opacity={ring.behindOpacity}
                depthFunc={THREE.GreaterDepth}
                depthWrite={false}
              />
            </mesh>
          </group>
        </group>
      ))}
    </group>
  );
}

// ── Luminous 3D Ground Light Reflection Disc ─────────────────────────────────

function GroundLightReflectionDisc({
  state,
  amplitude,
}: {
  state: NovaVisualState;
  amplitude: number;
}) {
  const discRef = useRef<THREE.Mesh>(null);
  const matRef = useRef<THREE.MeshBasicMaterial>(null);

  const discTex = useMemo(() => {
    const size = 512;
    const canvas = document.createElement("canvas");
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext("2d")!;

    ctx.clearRect(0, 0, size, size);

    const cx = size / 2;
    const cy = size / 2;

    // Concentric sky-blue glowing rings
    const grad = ctx.createRadialGradient(cx, cy, 10, cx, cy, size * 0.48);
    grad.addColorStop(0, "rgba(255, 255, 255, 1)");
    grad.addColorStop(0.2, "rgba(186, 230, 253, 0.95)");
    grad.addColorStop(0.5, "rgba(56, 189, 248, 0.65)");
    grad.addColorStop(0.75, "rgba(14, 165, 233, 0.3)");
    grad.addColorStop(1, "rgba(2, 132, 199, 0)");
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(cx, cy, size * 0.48, 0, Math.PI * 2);
    ctx.fill();

    // Central bright lens flare band
    const flareGrad = ctx.createLinearGradient(0, cy, size, cy);
    flareGrad.addColorStop(0, "rgba(56, 189, 248, 0)");
    flareGrad.addColorStop(0.35, "rgba(186, 230, 253, 0.85)");
    flareGrad.addColorStop(0.5, "rgba(255, 255, 255, 1)");
    flareGrad.addColorStop(0.65, "rgba(186, 230, 253, 0.85)");
    flareGrad.addColorStop(1, "rgba(56, 189, 248, 0)");
    ctx.fillStyle = flareGrad;
    ctx.fillRect(size * 0.08, cy - 7, size * 0.84, 14);

    const texture = new THREE.CanvasTexture(canvas);
    texture.needsUpdate = true;
    return texture;
  }, []);

  useFrame(({ clock }) => {
    if (!discRef.current) return;
    const t = clock.getElapsedTime();
    const cfg = STATE_CONFIG[state];

    const pulse = 1 + Math.sin(t * cfg.pulseSpeed) * 0.05 + amplitude * 0.12;
    discRef.current.scale.set(pulse * 2.9, pulse * 1.65, 1);

    if (matRef.current) {
      matRef.current.opacity = lerp(
        matRef.current.opacity,
        0.82 * cfg.coreGlow + amplitude * 0.25,
        0.05
      );
    }
  });

  return (
    <mesh ref={discRef} position={[0, -1.28, 0]} rotation={[-Math.PI / 2, 0, 0]}>
      <planeGeometry args={[1, 1]} />
      <meshBasicMaterial
        ref={matRef}
        map={discTex}
        transparent
        opacity={0.82}
        blending={THREE.AdditiveBlending}
        depthWrite={false}
      />
    </mesh>
  );
}

// ── Complete Sky-Blue Futuristic Nova Core ───────────────────────────────────

function NovaCrystalCore({
  state,
  amplitude,
}: {
  state: NovaVisualState;
  amplitude: number;
}) {
  const outerSphereRef = useRef<THREE.Mesh>(null);
  const outerMatRef = useRef<THREE.MeshPhysicalMaterial>(null);
  const innerCoreRef = useRef<THREE.Mesh>(null);
  const innerCoreMatRef = useRef<THREE.MeshPhysicalMaterial>(null);
  const pointLightRef = useRef<THREE.PointLight>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    const cfg = STATE_CONFIG[state];
    const lerpSpeed = 0.045;

    const pulse = 1 + Math.sin(t * cfg.pulseSpeed) * cfg.pulseAmp;
    const ampBoost = 1 + Math.min(amplitude, 1) * 0.07;
    const finalScale = pulse * ampBoost;

    if (outerSphereRef.current) {
      outerSphereRef.current.scale.set(finalScale, finalScale, finalScale);
      outerSphereRef.current.rotation.y += cfg.rotationSpeed * 0.003;
      outerSphereRef.current.rotation.x = Math.sin(t * 0.12) * 0.015;
    }

    if (innerCoreRef.current) {
      const coreScale = 0.54 * finalScale;
      innerCoreRef.current.scale.set(coreScale, coreScale, coreScale);
      innerCoreRef.current.rotation.y -= cfg.rotationSpeed * 0.005;
    }

    if (outerMatRef.current) {
      outerMatRef.current.attenuationColor.lerp(cfg.crestColor, lerpSpeed);
      outerMatRef.current.emissive.lerp(cfg.lightColor, lerpSpeed);
      outerMatRef.current.emissiveIntensity = lerp(
        outerMatRef.current.emissiveIntensity,
        cfg.coreGlow * 0.22,
        lerpSpeed
      );
    }

    if (innerCoreMatRef.current) {
      innerCoreMatRef.current.color.lerp(cfg.innerCoreColor, lerpSpeed);
      innerCoreMatRef.current.emissive.lerp(cfg.waveColor, lerpSpeed);
      innerCoreMatRef.current.emissiveIntensity = lerp(
        innerCoreMatRef.current.emissiveIntensity,
        cfg.coreGlow * 0.6,
        lerpSpeed
      );
    }

    if (pointLightRef.current) {
      pointLightRef.current.intensity = lerp(
        pointLightRef.current.intensity,
        cfg.innerLight + amplitude * 1.8,
        lerpSpeed
      );
      pointLightRef.current.color.lerp(cfg.lightColor, lerpSpeed);
    }
  });

  return (
    <group>
      {/* Central Radiating Sky-Blue Point Light */}
      <pointLight
        ref={pointLightRef}
        distance={4.8}
        decay={2}
        intensity={2.2}
        color="#38bdf8"
      />

      {/* Layer 1: Vibrant Electric Sky Blue Inner Core */}
      <mesh ref={innerCoreRef}>
        <sphereGeometry args={[1, 48, 48]} />
        <meshPhysicalMaterial
          ref={innerCoreMatRef}
          color="#0284c7"
          emissive="#0ea5e9"
          emissiveIntensity={0.6}
          roughness={0.18}
          metalness={0.15}
          clearcoat={0.8}
          transparent
          opacity={0.94}
          depthWrite={false}
        />
      </mesh>

      {/* Layer 2: Sculpted Fluid S-Wave Energy System */}
      <FluidEnergyWaveSystem state={state} amplitude={amplitude} />

      {/* Layer 3: Ultra-Glassy Transparent Outer Sphere in Sky Blue */}
      <mesh ref={outerSphereRef}>
        <sphereGeometry args={[1, 64, 64]} />
        <meshPhysicalMaterial
          ref={outerMatRef}
          transmission={0.92}
          roughness={0.02}
          ior={1.48}
          reflectivity={0.95}
          thickness={1.35}
          attenuationColor={new THREE.Color("#38bdf8")}
          attenuationDistance={2.2}
          clearcoat={1.0}
          clearcoatRoughness={0.02}
          specularIntensity={1.4}
          specularColor={new THREE.Color("#ffffff")}
          emissive={new THREE.Color("#0ea5e9")}
          emissiveIntensity={0.15}
          transparent
          opacity={0.98}
          depthWrite={true}
        />
      </mesh>
    </group>
  );
}

// ── Drag & Inertia Controller ────────────────────────────────────────────────

function DragController({
  groupRef,
}: {
  groupRef: React.RefObject<THREE.Group | null>;
}) {
  const { gl } = useThree();
  const isDragging = useRef(false);
  const prev = useRef({ x: 0, y: 0 });
  const velocity = useRef({ x: 0, y: 0 });

  useEffect(() => {
    const canvas = gl.domElement;

    const onDown = (e: PointerEvent) => {
      isDragging.current = true;
      prev.current = { x: e.clientX, y: e.clientY };
      velocity.current = { x: 0, y: 0 };
    };

    const onMove = (e: PointerEvent) => {
      if (!isDragging.current) return;
      const dx = e.clientX - prev.current.x;
      const dy = e.clientY - prev.current.y;
      velocity.current = { x: dx * 0.005, y: dy * 0.005 };
      prev.current = { x: e.clientX, y: e.clientY };
    };

    const onUp = () => {
      isDragging.current = false;
    };

    canvas.addEventListener("pointerdown", onDown);
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerup", onUp);
    canvas.addEventListener("pointerleave", onUp);

    return () => {
      canvas.removeEventListener("pointerdown", onDown);
      canvas.removeEventListener("pointermove", onMove);
      canvas.removeEventListener("pointerup", onUp);
      canvas.removeEventListener("pointerleave", onUp);
    };
  }, [gl]);

  useFrame(() => {
    if (!groupRef.current) return;
    if (isDragging.current) {
      groupRef.current.rotation.y += velocity.current.x;
      groupRef.current.rotation.x += velocity.current.y;
      groupRef.current.rotation.x = Math.max(-0.55, Math.min(0.55, groupRef.current.rotation.x));
    } else {
      velocity.current.x *= 0.94;
      velocity.current.y *= 0.94;
      groupRef.current.rotation.y += velocity.current.x;
      groupRef.current.rotation.x += velocity.current.y;
      groupRef.current.rotation.x = Math.max(-0.55, Math.min(0.55, groupRef.current.rotation.x));
    }
  });

  return null;
}

// ── Complete Scene Content ───────────────────────────────────────────────────

function Nova3DScene({
  state,
  amplitude,
}: {
  state: NovaVisualState;
  amplitude: number;
}) {
  const mainGroupRef = useRef<THREE.Group>(null);

  useFrame(({ clock }) => {
    if (!mainGroupRef.current) return;
    const t = clock.getElapsedTime();
    mainGroupRef.current.position.y = Math.sin(t * 0.65) * 0.05;
  });

  return (
    <>
      {/* Studio Lighting Tuned for Sky-Blue Glow & White Background */}
      <ambientLight intensity={0.75} color="#f0f9ff" />
      <directionalLight position={[4, 5, 5]} intensity={1.6} color="#ffffff" />
      <directionalLight position={[-4, -2, -3]} intensity={0.85} color="#38bdf8" />
      <directionalLight position={[0, -4, 2]} intensity={0.5} color="#bae6fd" />

      {/* Interactive Drag & Tilt Controls */}
      <DragController groupRef={mainGroupRef} />

      {/* Floating 3D Ground Light Disc */}
      <GroundLightReflectionDisc state={state} amplitude={amplitude} />

      <group ref={mainGroupRef}>
        {/* The Central Sky-Blue Futuristic Glass AI Core */}
        <NovaCrystalCore state={state} amplitude={amplitude} />

        {/* Clearly Visible 3D Tubular Rings with Complete 360° Continuity */}
        <VisibleOrbitalRingsSystem state={state} />

        {/* Orbiting Sky-Blue Satellite Beads */}
        <OrbitingSatelliteBeads state={state} />
      </group>
    </>
  );
}

// ── CSS Fallback Component ───────────────────────────────────────────────────

function CSSFallbackOrb({
  state,
  onClick,
}: {
  state: NovaVisualState;
  onClick: () => void;
}) {
  return (
    <div
      className="nova-orb-stage"
      onClick={onClick}
      role="button"
      tabIndex={0}
      aria-label="NOVA AI Core. Click to activate."
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onClick();
        }
      }}
    >
      <div className="nova-orb-glow" />
      <div className="nova-orb-ring-outer" />
      <div className="nova-orb-ring-inner" />
      <div className="nova-orb-sphere">
        <span className="nova-orb-letter">N</span>
      </div>
    </div>
  );
}

// ── Main Exported Component ──────────────────────────────────────────────────

export default function Nova3DSphere({
  state,
  amplitude,
  onClick,
}: Nova3DSphereProps) {
  const [webglFailed, setWebglFailed] = useState(false);
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReducedMotion(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);

  if (webglFailed || reducedMotion) {
    return (
      <div className="nova-3d-wrapper">
        <CSSFallbackOrb state={state} onClick={onClick} />
        <div className="nova-ground-reflection" />
      </div>
    );
  }

  return (
    <div className="nova-3d-wrapper">
      <div
        className="nova-3d-container"
        onClick={onClick}
        role="button"
        tabIndex={0}
        aria-label="NOVA 3D AI Core. Drag to inspect or click to speak."
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onClick();
          }
        }}
      >
        <Canvas
          camera={{ position: [0, 0, 4.2], fov: 42 }}
          dpr={[1, 2]}
          gl={{
            antialias: true,
            alpha: true,
            powerPreference: "high-performance",
          }}
          style={{ background: "transparent" }}
          onCreated={({ gl }) => {
            gl.setClearColor(0x000000, 0);
            gl.toneMapping = THREE.ACESFilmicToneMapping;
            gl.toneMappingExposure = 1.25;
          }}
          onError={() => setWebglFailed(true)}
          fallback={<CSSFallbackOrb state={state} onClick={onClick} />}
        >
          <Nova3DScene state={state} amplitude={amplitude} />
        </Canvas>
      </div>

      {/* Realistic Soft Radial Ground Light Reflection */}
      <div className="nova-ground-reflection" />
    </div>
  );
}

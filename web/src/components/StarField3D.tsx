import { useEffect, useMemo, useRef, type ComponentRef } from "react";
import { Canvas, useFrame, useThree, type ThreeEvent } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";
import type { Star } from "../types";
import { categoryColor, type ColorMode } from "../categories";

interface Props {
  stars: Star[];
  selected: Star | null;
  onSelect: (star: Star | null) => void;
  colorMode: ColorMode;
}

/**
 * A soft circular sprite (white core fading to transparent) used as the point
 * texture so stars render as round glowing dots instead of GL quads (squares).
 */
function makeStarSprite(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d")!;
  const g = ctx.createRadialGradient(
    size / 2,
    size / 2,
    0,
    size / 2,
    size / 2,
    size / 2,
  );
  g.addColorStop(0.0, "rgba(255,255,255,1)");
  g.addColorStop(0.4, "rgba(255,255,255,0.9)");
  g.addColorStop(1.0, "rgba(255,255,255,0)");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

/**
 * Per-star point-size multiplier from estimated mass (solar masses). Uses a
 * sqrt law so the huge dynamic range (red dwarfs ~0.1 M☉ up to ~2-3 M☉) stays
 * visually readable, with a floor so the smallest stars remain clickable.
 * Stars with no mass estimate fall back to a typical M-dwarf size.
 */
function massToSizeMul(mass: number | null): number {
  const m = mass && mass > 0 ? mass : 0.3;
  return Math.min(2.2, Math.max(0.45, Math.sqrt(m)));
}

/**
 * Inject a per-vertex `aSize` attribute into PointsMaterial's shader so each
 * star can have its own size while keeping the material's built-in colour
 * management, sprite texture and tone-mapping.
 */
function patchPointSize(shader: THREE.WebGLProgramParametersWithUniforms) {
  shader.vertexShader = shader.vertexShader
    .replace(
      "uniform float size;",
      "uniform float size;\nattribute float aSize;",
    )
    .replace("gl_PointSize = size;", "gl_PointSize = size * aSize;");
}

/**
 * Renders the solar neighbourhood as a single THREE.Points cloud in
 * heliocentric Galactic Cartesian coordinates (pc). The Sun sits at the origin.
 * Each star uses its true-colour RGB from the catalogue.
 */
function StarPoints({ stars, selected, onSelect, colorMode }: Props) {
  // Only stars with full Cartesian coordinates can be plotted.
  const plottable = useMemo(
    () => stars.filter((s) => s.x !== null && s.y !== null && s.z !== null),
    [stars],
  );

  // Positions and sizes don't depend on colour mode, so memoise them separately.
  const { positions, sizes } = useMemo(() => {
    const positions = new Float32Array(plottable.length * 3);
    const sizes = new Float32Array(plottable.length);
    plottable.forEach((s, i) => {
      positions[i * 3 + 0] = s.x!;
      positions[i * 3 + 1] = s.z!; // map Galactic z -> screen up
      positions[i * 3 + 2] = s.y!;
      // Size scales with estimated mass (mass_est, falling back to FLAME mass).
      sizes[i] = massToSizeMul(s.massEst ?? s.massFlame);
    });
    return { positions, sizes };
  }, [plottable]);

  // Colours depend on the mode: each star's true sRGB, or its category hue.
  const colors = useMemo(() => {
    const colors = new Float32Array(plottable.length * 3);
    const c = new THREE.Color();
    plottable.forEach((s, i) => {
      if (colorMode === "category") {
        // Category hex is sRGB; setStyle handles the colour-space conversion.
        c.set(categoryColor(s.starClass));
      } else {
        // The catalogue RGB is sRGB; convert to the renderer's linear working
        // space so the colour isn't washed out toward white on output.
        c.setRGB(
          (s.rgbR ?? 128) / 255,
          (s.rgbG ?? 128) / 255,
          (s.rgbB ?? 128) / 255,
          THREE.SRGBColorSpace,
        );
      }
      colors[i * 3 + 0] = c.r;
      colors[i * 3 + 1] = c.g;
      colors[i * 3 + 2] = c.b;
    });
    return colors;
  }, [plottable, colorMode]);

  const sprite = useMemo(() => makeStarSprite(), []);

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    g.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    g.setAttribute("aSize", new THREE.BufferAttribute(sizes, 1));
    return g;
  }, [positions, colors, sizes]);

  const handleClick = (e: ThreeEvent<MouseEvent>) => {
    e.stopPropagation();
    if (e.index === undefined) return;
    onSelect(plottable[e.index]);
  };

  const selectedPos = useMemo(() => {
    if (!selected || selected.x === null) return null;
    return new THREE.Vector3(selected.x, selected.z!, selected.y!);
  }, [selected]);

  return (
    <group>
      <points geometry={geometry} onClick={handleClick}>
        <pointsMaterial
          vertexColors
          map={sprite}
          alphaMap={sprite}
          size={0.5}
          sizeAttenuation
          transparent
          alphaTest={0.05}
          depthWrite={false}
          toneMapped={false}
          onBeforeCompile={patchPointSize}
        />
      </points>

      {/* Highlight ring around the selected star */}
      {selected && selectedPos && (
        <mesh position={selectedPos}>
          <ringGeometry args={[0.5, 0.65, 32]} />
          <meshBasicMaterial color="#7fd4ff" side={THREE.DoubleSide} />
          <Html distanceFactor={20} position={[0, 0.9, 0]} center>
            <div className="star-label">
              {selected.properName ?? selected.simbadMainId ?? selected.starId}
            </div>
          </Html>
        </mesh>
      )}
    </group>
  );
}

type OrbitControlsRef = ComponentRef<typeof OrbitControls>;

const ARROW_KEYS = new Set([
  "arrowleft",
  "arrowright",
  "arrowup",
  "arrowdown",
]);

/**
 * Keyboard navigation for the 3D scene, driven each frame:
 *   Arrow Left/Right  – pan the view sideways (translate, not rotate)
 *   Arrow Up/Down     – move forward / backward across the map
 *   a / s             – rotate (orbit) the scene left / right
 * Speeds scale with distance to the orbit target so they feel consistent at
 * any zoom. Ignored while a form control (e.g. a filter slider) is focused.
 */
function KeyboardNav({ controls }: { controls: React.RefObject<OrbitControlsRef | null> }) {
  const camera = useThree((s) => s.camera);
  const keys = useRef<Record<string, boolean>>({});

  useEffect(() => {
    const isTyping = () => {
      const el = document.activeElement;
      return (
        el instanceof HTMLInputElement ||
        el instanceof HTMLTextAreaElement ||
        el instanceof HTMLSelectElement
      );
    };
    const down = (e: KeyboardEvent) => {
      if (isTyping()) return;
      const key = e.key.toLowerCase();
      keys.current[key] = true;
      if (ARROW_KEYS.has(key)) e.preventDefault(); // don't scroll the page
    };
    const up = (e: KeyboardEvent) => {
      keys.current[e.key.toLowerCase()] = false;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, []);

  useFrame((_, delta) => {
    const c = controls.current;
    if (!c) return;
    const k = keys.current;
    const target = c.target as THREE.Vector3;

    const dist = camera.position.distanceTo(target);
    const panStep = dist * 0.9 * delta; // pc/s, scaled by zoom
    const rotStep = 1.3 * delta; // rad/s

    // Horizontal forward (view direction flattened) and right vectors.
    const forward = new THREE.Vector3();
    camera.getWorldDirection(forward);
    forward.y = 0;
    forward.normalize();
    const right = new THREE.Vector3()
      .crossVectors(forward, new THREE.Vector3(0, 1, 0))
      .normalize();

    const move = new THREE.Vector3();
    if (k["arrowleft"]) move.addScaledVector(right, -panStep);
    if (k["arrowright"]) move.addScaledVector(right, panStep);
    if (k["arrowup"]) move.addScaledVector(forward, panStep);
    if (k["arrowdown"]) move.addScaledVector(forward, -panStep);

    let angle = 0;
    if (k["a"]) angle += rotStep;
    if (k["s"]) angle -= rotStep;

    if (move.lengthSq() === 0 && angle === 0) return;

    if (move.lengthSq() > 0) {
      camera.position.add(move);
      target.add(move);
    }
    if (angle !== 0) {
      // Orbit the camera around the target about the world up axis.
      const offset = camera.position.clone().sub(target);
      offset.applyAxisAngle(new THREE.Vector3(0, 1, 0), angle);
      camera.position.copy(target).add(offset);
    }
    c.update();
  });

  return null;
}

export default function StarField3D(props: Props) {
  const controls = useRef<OrbitControlsRef>(null);

  return (
    <>
    <Canvas
      camera={{ position: [12, 8, 12], near: 0.01, far: 2000, fov: 55 }}
      raycaster={{ params: { Points: { threshold: 0.4 } } } as never}
      onPointerMissed={() => props.onSelect(null)}
      style={{ background: "radial-gradient(circle at 50% 40%, #0b1026 0%, #03040a 70%)" }}
    >
      <ambientLight intensity={0.6} />

      {/* The Sun at the origin */}
      <mesh>
        <sphereGeometry args={[0.18, 16, 16]} />
        <meshBasicMaterial color="#fff4cc" />
        <Html distanceFactor={20} position={[0, 0.6, 0]} center>
          <div className="star-label sun-label">Sun</div>
        </Html>
      </mesh>

      <StarPoints {...props} />

      <axesHelper args={[5]} />
      <OrbitControls ref={controls} enableDamping dampingFactor={0.1} />
      <KeyboardNav controls={controls} />
    </Canvas>
    <div className="nav-hint">
      <span><kbd>←</kbd><kbd>→</kbd> pan</span>
      <span><kbd>↑</kbd><kbd>↓</kbd> move</span>
      <span><kbd>A</kbd><kbd>S</kbd> rotate</span>
      <span>drag / scroll to orbit &amp; zoom</span>
    </div>
    </>
  );
}

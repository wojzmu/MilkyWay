import { useEffect, useMemo, useRef } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
import * as THREE from "three";
import type { PointCloud } from "../data/loadPointCloud";
import { NameLayout, NameOverlay, type NameLabel } from "./StarNames";
import { categoryColor, type ColorMode } from "../categories";

export interface CloudSettings {
  distMax: number; // pc
  fMax: number; // relative distance uncertainty threshold
  fraction: number; // 0..1 of points drawn (prefix of the random order)
  pointSize: number; // px
  brightness: number; // per-point opacity (additive blending saturates at 1.5 M points)
  classMask: number; // bit c set = class code c visible
  labels: boolean; // names of well-known stars
}

interface Props {
  cloud: PointCloud;
  settings: CloudSettings;
  colorMode: ColorMode;
  selected: number | null;
  onSelect: (i: number | null) => void;
}

type ViewName = "top" | "side" | "reset";
interface CameraApi {
  go: (v: ViewName) => void;
}

const LOG_HALF_PLUS_3 = Math.log10(0.5) + 3;
const RESET_POS = new THREE.Vector3(1800, 1200, 1800);
const RINGS = [250, 500, 1000, 1250];

const VERT = /* glsl */ `
uniform float uPointSize;
uniform float uPixelRatio;
uniform float uDistMax;
uniform float uFMax;
uniform float uBrightness;
uniform float uClassMask;
uniform int uColorMode;
uniform vec3 uCategoryColors[9];
attribute vec3 aColor;
attribute float aU;
attribute float aClass;
varying vec3 vColor;
varying float vAlpha;

vec3 srgbToLinear(vec3 c) {
  return mix(c / 12.92, pow((c + 0.055) / 1.055, vec3(2.4)), step(vec3(0.04045), c));
}

void main() {
  float d = length(position);
  int cls = int(aClass + 0.5);
  bool classOn = ((int(uClassMask + 0.5) >> cls) & 1) == 1;
  if (d > uDistMax || !classOn) {
    gl_Position = vec4(2.0, 2.0, 2.0, 1.0);
    gl_PointSize = 0.0;
    vColor = vec3(0.0);
    vAlpha = 0.0;
    return;
  }
  float u = floor(aU + 0.5);
  float f = u >= 254.5 ? 0.5 : pow(10.0, u / 254.0 * ${LOG_HALF_PLUS_3.toFixed(8)} - 3.0);
  vAlpha = (f > uFMax ? 0.08 : 1.0) * uBrightness;
  vColor = uColorMode == 1 ? uCategoryColors[cls] : srgbToLinear(aColor);
  vec4 mv = modelViewMatrix * vec4(position, 1.0);
  float atten = clamp(sqrt(1500.0 / max(-mv.z, 1.0)), 0.6, 2.5);
  gl_PointSize = uPointSize * uPixelRatio * atten;
  gl_Position = projectionMatrix * mv;
}
`;

const FRAG = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
void main() {
  vec2 p = gl_PointCoord - 0.5;
  float r = length(p) * 2.0;
  if (r > 1.0) discard;
  float fall = 1.0 - smoothstep(0.0, 1.0, r);
  gl_FragColor = vec4(vColor * 0.9, vAlpha * fall);
  #include <colorspace_fragment>
}
`;

function classVisible(mask: number, cls: number): boolean {
  return ((mask >> cls) & 1) === 1;
}

/** The point cloud itself plus click picking and the selection ring. */
function CloudPoints({
  cloud,
  settings,
  colorMode,
  selected,
  onSelect,
}: Props) {
  const gl = useThree((s) => s.gl);
  const camera = useThree((s) => s.camera) as THREE.PerspectiveCamera;
  const settingsRef = useRef(settings);
  const countRef = useRef(cloud.n);

  const geometry = useMemo(() => {
    const g = new THREE.BufferGeometry();
    g.setAttribute("position", new THREE.BufferAttribute(cloud.positions, 3));
    const ib = new THREE.InterleavedBuffer(cloud.rgbu, 4);
    g.setAttribute(
      "aColor",
      new THREE.InterleavedBufferAttribute(ib, 3, 0, true),
    );
    g.setAttribute("aU", new THREE.InterleavedBufferAttribute(ib, 1, 3, false));
    g.setAttribute("aClass", new THREE.BufferAttribute(cloud.classes, 1));
    return g;
  }, [cloud]);

  const material = useMemo(() => {
    const cats = Array.from({ length: 9 }, (_, code) =>
      new THREE.Color(categoryColor(cloud.classCodes[code] ?? "Unknown")),
    );
    return new THREE.ShaderMaterial({
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
      depthWrite: false,
      depthTest: false,
      blending: THREE.AdditiveBlending,
      uniforms: {
        uPointSize: { value: 2 },
        uPixelRatio: { value: 1 },
        uDistMax: { value: 1250 },
        uFMax: { value: 0.2 },
        uBrightness: { value: 0.15 },
        uClassMask: { value: 511 },
        uColorMode: { value: 0 },
        uCategoryColors: { value: cats },
      },
    });
  }, [cloud]);

  useEffect(
    () => () => {
      geometry.dispose();
      material.dispose();
    },
    [geometry, material],
  );

  // Filters only touch uniforms and the draw range.
  useEffect(() => {
    settingsRef.current = settings;
    const u = material.uniforms;
    u.uPointSize.value = settings.pointSize;
    u.uDistMax.value = settings.distMax;
    u.uFMax.value = settings.fMax;
    u.uBrightness.value = settings.brightness;
    u.uClassMask.value = settings.classMask;
    const k = Math.max(1, Math.round(settings.fraction * cloud.n));
    countRef.current = k;
    geometry.setDrawRange(0, k);
  }, [settings, material, geometry, cloud.n]);

  useEffect(() => {
    material.uniforms.uColorMode.value = colorMode === "category" ? 1 : 0;
  }, [colorMode, material]);

  useEffect(() => {
    material.uniforms.uPixelRatio.value = gl.getPixelRatio();
  }, [gl, material]);

  // Click picking: the nearest point to the ray within ~8 px, honouring the
  // draw range, distance and class filters (uncertainty fade is ignored).
  useEffect(() => {
    const el = gl.domElement;
    let down: { x: number; y: number } | null = null;
    const onDown = (e: PointerEvent) => {
      down = { x: e.clientX, y: e.clientY };
    };
    const onUp = (e: PointerEvent) => {
      if (!down) return;
      const moved = Math.hypot(e.clientX - down.x, e.clientY - down.y);
      down = null;
      if (moved > 4) return;
      const rect = el.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      const ray = new THREE.Raycaster();
      ray.setFromCamera(ndc, camera);
      const o = ray.ray.origin;
      const dir = ray.ray.direction;
      const pos = cloud.positions;
      const cls = cloud.classes;
      const s = settingsRef.current;
      const dmax2 = s.distMax * s.distMax;
      // Angular tolerance corresponding to 8 px at the current field of view.
      const tol =
        ((2 * Math.tan((camera.fov * Math.PI) / 360)) / rect.height) * 8;
      const tol2 = tol * tol;
      let best = -1;
      let bestA = Infinity;
      const k = countRef.current;
      for (let i = 0; i < k; i++) {
        const x = pos[3 * i];
        const y = pos[3 * i + 1];
        const z = pos[3 * i + 2];
        if (x * x + y * y + z * z > dmax2) continue;
        if (!classVisible(s.classMask, cls[i])) continue;
        const vx = x - o.x;
        const vy = y - o.y;
        const vz = z - o.z;
        const t = vx * dir.x + vy * dir.y + vz * dir.z;
        if (t <= camera.near) continue;
        const a = (vx * vx + vy * vy + vz * vz - t * t) / (t * t);
        if (a < tol2 && a < bestA) {
          bestA = a;
          best = i;
        }
      }
      onSelect(best >= 0 ? best : null);
    };
    el.addEventListener("pointerdown", onDown);
    el.addEventListener("pointerup", onUp);
    return () => {
      el.removeEventListener("pointerdown", onDown);
      el.removeEventListener("pointerup", onUp);
    };
  }, [gl, camera, cloud, onSelect]);

  const selPos = useMemo<[number, number, number] | null>(() => {
    if (selected === null) return null;
    const p = cloud.positions;
    return [p[3 * selected], p[3 * selected + 1], p[3 * selected + 2]];
  }, [selected, cloud]);

  return (
    <>
      <points
        geometry={geometry}
        material={material}
        frustumCulled={false}
        renderOrder={1}
      />
      {selPos && (
        <Html position={selPos} center zIndexRange={[10, 0]}>
          <div className="pt-ring" />
        </Html>
      )}
    </>
  );
}

/** Sun marker, Galactic-plane reference rings and the Galactic-centre arrow. */
function Reference() {
  const rings = useMemo(
    () =>
      RINGS.map((r) => {
        const pts: THREE.Vector3[] = [];
        for (let i = 0; i < 128; i++) {
          const a = (i / 128) * Math.PI * 2;
          pts.push(new THREE.Vector3(r * Math.cos(a), 0, r * Math.sin(a)));
        }
        return { r, geo: new THREE.BufferGeometry().setFromPoints(pts) };
      }),
    [],
  );
  const arrow = useMemo(
    () =>
      new THREE.ArrowHelper(
        new THREE.Vector3(1, 0, 0),
        new THREE.Vector3(0, 0, 0),
        320,
        0xff9f43,
        50,
        25,
      ),
    [],
  );
  return (
    <group>
      <mesh renderOrder={2}>
        <sphereGeometry args={[7, 16, 16]} />
        <meshBasicMaterial color="#fff4cc" depthTest={false} />
        <Html position={[0, 20, 0]} center>
          <div className="star-label sun-label">Sun</div>
        </Html>
      </mesh>
      {rings.map(({ r, geo }) => (
        <group key={r}>
          <lineLoop geometry={geo}>
            <lineBasicMaterial
              color="#5a6a96"
              transparent
              opacity={0.3}
              depthTest={false}
            />
          </lineLoop>
          <Html position={[r * Math.SQRT1_2, 0, -r * Math.SQRT1_2]} center>
            <div className="ring-label">{r} pc</div>
          </Html>
        </group>
      ))}
      <primitive object={arrow} />
      <Html position={[400, 0, 0]} center>
        <div className="ring-label ring-label--gc">→ Galactic centre</div>
      </Html>
    </group>
  );
}

/** Smooth camera moves for the view buttons. */
function CameraRig({ apiRef }: { apiRef: React.RefObject<CameraApi | null> }) {
  const camera = useThree((s) => s.camera);
  const controls = useThree((s) => s.controls) as unknown as {
    target: THREE.Vector3;
    update: () => void;
  } | null;
  const tween = useRef<{ to: THREE.Vector3; t: number } | null>(null);

  useEffect(() => {
    apiRef.current = {
      go: (v) => {
        const to =
          v === "top"
            ? new THREE.Vector3(0, 2300, 1)
            : v === "side"
              ? new THREE.Vector3(0, 0, 2300)
              : RESET_POS.clone();
        tween.current = { to, t: 0 };
      },
    };
    return () => {
      apiRef.current = null;
    };
  }, [apiRef]);

  useFrame((_, delta) => {
    const tw = tween.current;
    if (!tw || !controls) return;
    tw.t = Math.min(1, tw.t + delta / 0.8);
    const done = tw.t >= 1;
    const a = done ? 1 : 1 - Math.pow(0.001, delta); // frame-rate independent ease
    camera.position.lerp(tw.to, a);
    controls.target.lerp(new THREE.Vector3(0, 0, 0), a);
    if (done) {
      camera.position.copy(tw.to);
      controls.target.set(0, 0, 0);
      tween.current = null;
    }
    controls.update();
  });
  return null;
}

export default function GalaxyField3D(props: Props) {
  const apiRef = useRef<CameraApi | null>(null);
  const labelEls = useRef<(HTMLDivElement | null)[]>([]);
  const { labels: cloudLabels } = props.cloud;
  const labels = useMemo<NameLabel[]>(
    () =>
      cloudLabels.map((lb) => ({
        key: lb.hip,
        name: lb.name,
        title: `${lb.nameIau} · HIP ${lb.hip} · ${lb.distPc.toFixed(1)} pc`,
        tier: lb.tier,
        pos: lb.pos,
        clickable: lb.point !== null,
      })),
    [cloudLabels],
  );
  const shownRef = useRef<(i: number) => boolean>(() => false);
  shownRef.current = (i) =>
    props.settings.labels && cloudLabels[i].distPc <= props.settings.distMax;
  return (
    <>
      <Canvas
        camera={{
          position: RESET_POS.toArray(),
          near: 1,
          far: 20000,
          fov: 55,
        }}
        gl={{ antialias: false }}
        style={{
          background:
            "radial-gradient(circle at 50% 40%, #0b1026 0%, #03040a 70%)",
        }}
      >
        <CloudPoints {...props} />
        <Reference />
        <OrbitControls makeDefault enableDamping dampingFactor={0.1} />
        <CameraRig apiRef={apiRef} />
        {labels.length > 0 && (
          <NameLayout labels={labels} elsRef={labelEls} shownRef={shownRef}
                      reserve={[0, 20, 0]} />
        )}
      </Canvas>
      <NameOverlay
        labels={labels}
        elsRef={labelEls}
        onPick={(i) => {
          const p = cloudLabels[i].point;
          if (p !== null) props.onSelect(p);
        }}
      />
      <div className="viewbtns" role="group" aria-label="Camera view">
        <button onClick={() => apiRef.current?.go("top")}>
          Top (face-on)
        </button>
        <button onClick={() => apiRef.current?.go("side")}>
          Side (edge-on)
        </button>
        <button onClick={() => apiRef.current?.go("reset")}>Reset</button>
      </div>
    </>
  );
}

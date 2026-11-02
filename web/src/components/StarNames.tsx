// Names of well-known stars over a 3D scene (D-026), shared by the CSV view
// (StarField3D) and the binary map (GalaxyField3D). The DOM nodes live outside
// the Canvas; a component inside it projects them every frame and lays them out
// greedily, best known first, hiding any label that would overlap one already
// placed. Zooming out therefore leaves only the famous names.
import { useEffect, useMemo, useRef } from "react";
import { useFrame, useThree } from "@react-three/fiber";
import * as THREE from "three";

export type { StarName } from "../data/starNames";

export interface NameLabel {
  key: string | number;
  name: string;
  /** Tooltip (IAU name, catalogue id, distance). */
  title: string;
  /** 1 best known, 2, 3; drives the style. The list order drives priority. */
  tier: number;
  /** Screen axes (x, galactic z, galactic y), in scene units. */
  pos: [number, number, number];
  clickable: boolean;
}

/** Inside the Canvas: positions the overlay's labels each frame. */
export function NameLayout({
  labels,
  elsRef,
  shownRef,
  reserve,
}: {
  labels: NameLabel[];
  elsRef: React.RefObject<(HTMLDivElement | null)[]>;
  /** shownRef.current(i): may label i be shown at all (filters, toggle). */
  shownRef: React.RefObject<(i: number) => boolean>;
  /** The Sun's scene position: its dot and the label just above stay free. */
  reserve?: [number, number, number];
}) {
  const camera = useThree((s) => s.camera);
  const size = useThree((s) => s.size);
  const v = useMemo(() => new THREE.Vector3(), []);
  // Label box sizes by key, measured once per label: reading offsetWidth after
  // a style write would force a layout per label per frame. Cleared when the
  // web font arrives, since it changes the widths.
  const sizes = useRef(new Map<string | number, [number, number]>());
  // Last transform written per node (null = hidden), so a still camera writes
  // nothing. Keyed by node: when the label list changes, indices move.
  const last = useRef(new WeakMap<HTMLElement, string | null>());
  useEffect(() => {
    let live = true;
    document.fonts?.ready.then(() => live && sizes.current.clear());
    return () => {
      live = false;
    };
  }, []);

  useFrame(() => {
    const els = elsRef.current;
    const allowed = shownRef.current;
    const placed: number[] = []; // x0, y0, x1, y1 per shown label
    if (reserve) {
      v.set(reserve[0], reserve[1], reserve[2]).project(camera);
      if (v.z < 1) {
        const sx = ((v.x + 1) / 2) * size.width;
        const sy = ((1 - v.y) / 2) * size.height;
        placed.push(sx - 20, sy - 26, sx + 20, sy + 6);
      }
    }
    for (let i = 0; i < labels.length; i++) {
      const el = els[i];
      if (!el) continue;
      const lb = labels[i];
      let show = allowed(i);
      let x0 = 0;
      let y0 = 0;
      if (show) {
        v.set(lb.pos[0], lb.pos[1], lb.pos[2]).project(camera);
        show = v.z < 1 && Math.abs(v.x) <= 1 && Math.abs(v.y) <= 1;
      }
      if (show) {
        let wh = sizes.current.get(lb.key);
        if (!wh) {
          // Measured while hidden (visibility keeps the layout box).
          wh = [el.offsetWidth, el.offsetHeight || 16];
          if (wh[0] > 0) sizes.current.set(lb.key, wh);
        }
        const [w, h] = wh;
        const x = ((v.x + 1) / 2) * size.width;
        const y = ((1 - v.y) / 2) * size.height;
        x0 = x - w / 2;
        y0 = y - h - 6; // just above the star
        const x1 = x0 + w;
        const y1 = y0 + h;
        for (let k = 0; k < placed.length; k += 4) {
          if (x0 < placed[k + 2] + 3 && x1 > placed[k] - 3 &&
              y0 < placed[k + 3] + 2 && y1 > placed[k + 1] - 2) {
            show = false;
            break;
          }
        }
        if (show) placed.push(x0, y0, x1, y1);
      }
      const t = show ? `translate(${x0.toFixed(1)}px, ${y0.toFixed(1)}px)` : null;
      if (last.current.get(el) === t) continue;
      last.current.set(el, t);
      el.style.visibility = show ? "visible" : "hidden";
      if (t) el.style.transform = t;
    }
  });
  return null;
}

/** Outside the Canvas: the label nodes themselves. */
export function NameOverlay({
  labels,
  elsRef,
  onPick,
}: {
  labels: NameLabel[];
  elsRef: React.RefObject<(HTMLDivElement | null)[]>;
  onPick: (i: number) => void;
}) {
  return (
    <div className="starnames" aria-label="Star names">
      {labels.map((lb, i) => (
        <div
          key={lb.key}
          ref={(el) => {
            elsRef.current[i] = el;
          }}
          className={`starname starname--t${lb.tier}${lb.clickable ? " starname--pick" : ""}`}
          title={lb.title}
          onClick={() => lb.clickable && onPick(i)}
        >
          {lb.name}
        </div>
      ))}
    </div>
  );
}

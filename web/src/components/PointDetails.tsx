import { useEffect, useState } from "react";
import type { PointCloud, PointDetail } from "../data/loadPointCloud";
import { fetchPointDetails } from "../data/loadPointCloud";
import { PC_TO_LY } from "../filters";

interface Props {
  cloud: PointCloud;
  index: number | null;
  onClose: () => void;
}

const nameOf = (cloud: PointCloud, i: number) =>
  cloud.labels.find((l) => l.point === i);

/** Parallax over error at or below which the catalogue flags dist_flag = low_snr (D-020). */
const LOW_SNR = 5;

/** ϖ/σ from the distance and the lower quantile r_lo = 1000/(ϖ + σ). */
const parallaxSnr = (d: number, rLo: number) => {
  const plx = 1000 / d;
  const sigma = 1000 / rLo - plx;
  return sigma > 0 ? plx / sigma : Infinity;
};

const fmt = (n: number, digits = 2, unit = "") =>
  Number.isFinite(n) ? `${n.toFixed(digits)}${unit ? ` ${unit}` : ""}` : "—";

/** Side panel for a selected binary-cloud point; id/G/BP-RP come lazily from
 *  details.bin, the geometry from the already-loaded positions. */
export default function PointDetails({ cloud, index, onClose }: Props) {
  const [loaded, setLoaded] = useState<{
    index: number;
    detail: PointDetail | null;
  } | null>(null);

  useEffect(() => {
    if (index === null) return;
    let ignore = false;
    fetchPointDetails(cloud.baseUrl, index)
      .then((d) => !ignore && setLoaded({ index, detail: d }))
      .catch(() => !ignore && setLoaded({ index, detail: null }));
    return () => {
      ignore = true;
    };
  }, [cloud, index]);

  if (index === null) return null;

  const p = cloud.positions;
  const x = p[3 * index];
  const y = p[3 * index + 2]; // screen z = galactic y
  const z = p[3 * index + 1]; // screen y = galactic z
  const d = Math.hypot(x, y, z);
  const l = ((Math.atan2(y, x) * 180) / Math.PI + 360) % 360;
  const b = (Math.asin(z / d) * 180) / Math.PI;
  const cls = cloud.classCodes[cloud.classes[index]] ?? "Unknown";
  const named = nameOf(cloud, index);

  const ready = loaded?.index === index;
  const det = ready ? loaded.detail : null;
  const pending = !ready;
  const val = (f: (d: PointDetail) => string) =>
    pending ? "…" : det ? f(det) : "—";
  const absG = det ? det.gMag - 5 * Math.log10(d) + 5 : NaN;
  const snr = det ? parallaxSnr(d, det.rLo) : Infinity;
  const uncertain = snr <= LOW_SNR;
  // r_hi is missing when ϖ − σ ≤ 0: the interval is open upwards.
  const interval = (t: PointDetail) =>
    Number.isFinite(t.rHi)
      ? `${fmt(t.rLo, 0)} – ${fmt(t.rHi, 0)} pc (${fmt(t.rLo * PC_TO_LY, 0)} – ${fmt(t.rHi * PC_TO_LY, 0)} ly)`
      : `> ${fmt(t.rLo, 0)} pc (> ${fmt(t.rLo * PC_TO_LY, 0)} ly)`;

  const rows: [string, string][] = [
    ["Class", cls],
    ["Distance", `${uncertain ? "≈ " : ""}${fmt(d, 1, "pc")} (${fmt(d * PC_TO_LY, 0, "ly")})`],
    ["Interval (±1σ)", val(interval)],
    ["G mag", val((t) => fmt(t.gMag, 2))],
    ["Absolute G", val(() => fmt(absG, 2))],
    ["BP − RP", val((t) => fmt(t.bpRp, 3))],
    ["Galactic l, b", `${fmt(l, 1)}°, ${fmt(b, 1)}°`],
    ["Height z", fmt(z, 1, "pc")],
  ];
  const r = cloud.rgbu[4 * index];
  const g = cloud.rgbu[4 * index + 1];
  const bl = cloud.rgbu[4 * index + 2];

  return (
    <aside className="details">
      <button className="details__close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="details__header">
        <span
          className="details__swatch"
          style={{ background: `rgb(${r},${g},${bl})` }}
        />
        <h2>
          {named ? named.name : pending ? "…" : (det?.label ?? "Unknown source")}
        </h2>
      </div>
      {named && (
        <p className="details__sub">
          {named.name !== named.nameIau && `${named.nameIau} · `}
          {pending ? "…" : (det?.label ?? "")}
        </p>
      )}
      <table className="details__table">
        <tbody>
          {rows.map(([k, v]) => (
            <tr key={k}>
              <th>{k}</th>
              <td>{v}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {uncertain && (
        <p className="details__warn" role="note">
          Uncertain distance: the parallax is only {fmt(snr, 1)}× its error, so
          1/parallax is a rough guess. The true distance can lie anywhere in the
          interval above (or beyond it).
        </p>
      )}
    </aside>
  );
}

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

  const rows: [string, string][] = [
    ["Class", cls],
    ["Distance", `${fmt(d, 1, "pc")} (${fmt(d * PC_TO_LY, 0, "ly")})`],
    ["Interval", val((t) => `${fmt(t.rLo, 1)} – ${fmt(t.rHi, 1)} pc`)],
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
    </aside>
  );
}

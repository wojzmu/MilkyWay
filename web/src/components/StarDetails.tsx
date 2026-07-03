import type { Star } from "../types";
import { PC_TO_LY } from "../filters";

interface Props {
  star: Star | null;
  onClose: () => void;
}

function fmt(n: number | null, digits = 2, unit = ""): string {
  if (n === null) return "—";
  return `${n.toFixed(digits)}${unit ? ` ${unit}` : ""}`;
}

/** Side panel describing the currently selected star. Renders nothing when no
 * star is selected, so the map/diagram stays fully visible (important on mobile,
 * where the panel is a bottom sheet). */
export default function StarDetails({ star, onClose }: Props) {
  if (!star) return null;

  const title = star.properName ?? star.simbadMainId ?? star.starId;

  const rows: [string, string][] = [
    ["Catalogue ID", star.starId],
    ["SIMBAD ID", star.simbadMainId ?? "—"],
    ["Class", star.starClass],
    ["Spectral type", star.spType ?? "—"],
    ["Source", star.sourceCatalogue],
    [
      "Distance",
      star.distPc === null ? "—" : fmt(star.distPc * PC_TO_LY, 2, "ly"),
    ],
    ["Parallax", fmt(star.parallaxMas, 2, "mas")],
    ["G mag", fmt(star.gMag, 2)],
    ["Absolute G", fmt(star.absG, 2)],
    ["BP − RP", fmt(star.bpRp, 3)],
    ["Teff (Apsis)", star.teffGspphot ? fmt(star.teffGspphot, 0, "K") : "—"],
    ["Teff (colour)", fmt(star.teffColor, 0, "K")],
    ["Mass est.", fmt(star.massEst, 2, "M☉")],
    ["Galactic l, b", `${fmt(star.l, 1)}°, ${fmt(star.b, 1)}°`],
    [
      "XYZ (pc)",
      `${fmt(star.x, 2)}, ${fmt(star.y, 2)}, ${fmt(star.z, 2)}`,
    ],
    [
      "UVW (km/s)",
      star.u === null
        ? "—"
        : `${fmt(star.u, 1)}, ${fmt(star.v, 1)}, ${fmt(star.w, 1)}`,
    ],
    ["Photometry", star.photOrigin],
  ];

  return (
    <aside className="details">
      <button className="details__close" onClick={onClose} aria-label="Close">
        ×
      </button>
      <div className="details__header">
        <span
          className="details__swatch"
          style={{ background: star.rgbHex }}
          title={star.rgbHex}
        />
        <h2>{title}</h2>
      </div>
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

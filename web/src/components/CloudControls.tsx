import { CATEGORY_ORDER, CATEGORY_COLORS } from "../categories";

import { F_MIN, F_MAX, type CloudUi } from "../cloudUi";

interface Props {
  ui: CloudUi;
  maxDist: number;
  counts: Record<string, number>;
  onChange: (u: CloudUi) => void;
}

const fToSlider = (f: number) =>
  (Math.log10(f) - Math.log10(F_MIN)) / (Math.log10(F_MAX) - Math.log10(F_MIN));
const sliderToF = (v: number) =>
  10 ** (Math.log10(F_MIN) + v * (Math.log10(F_MAX) - Math.log10(F_MIN)));

/** Compact filter panel for binary point-cloud datasets. */
export default function CloudControls({ ui, maxDist, counts, onChange }: Props) {
  const toggle = (c: string) => {
    const hidden = ui.hidden.includes(c)
      ? ui.hidden.filter((h) => h !== c)
      : [...ui.hidden, c];
    onChange({ ...ui, hidden });
  };
  return (
    <div className="cloudctl" aria-label="Point cloud filters">
      <label>
        <span>Max distance</span>
        <output>{Math.round(ui.distMax)} pc</output>
        <input
          type="range"
          min={0}
          max={maxDist}
          step={5}
          value={ui.distMax}
          onChange={(e) => onChange({ ...ui, distMax: Number(e.target.value) })}
        />
      </label>
      <label title="Stars with a larger relative distance uncertainty are faded">
        <span>Max uncertainty</span>
        <output>{(ui.fMax * 100).toFixed(ui.fMax < 0.01 ? 2 : 1)} %</output>
        <input
          type="range"
          min={0}
          max={1}
          step={0.005}
          value={fToSlider(ui.fMax)}
          onChange={(e) =>
            onChange({ ...ui, fMax: sliderToF(Number(e.target.value)) })
          }
        />
      </label>
      <label>
        <span>Points shown</span>
        <output>{ui.percent} %</output>
        <input
          type="range"
          min={5}
          max={100}
          step={1}
          value={ui.percent}
          onChange={(e) => onChange({ ...ui, percent: Number(e.target.value) })}
        />
      </label>
      <label>
        <span>Point size</span>
        <output>{ui.pointSize.toFixed(1)} px</output>
        <input
          type="range"
          min={0.5}
          max={8}
          step={0.1}
          value={ui.pointSize}
          onChange={(e) => onChange({ ...ui, pointSize: Number(e.target.value) })}
        />
      </label>
      <label>
        <span>Brightness</span>
        <output>{Math.round(ui.brightness * 100)} %</output>
        <input
          type="range"
          min={0.02}
          max={1}
          step={0.01}
          value={ui.brightness}
          onChange={(e) => onChange({ ...ui, brightness: Number(e.target.value) })}
        />
      </label>
      <div className="cloudctl__classes">
        {CATEGORY_ORDER.map((c) => (
          <label key={c} className="cloudctl__class">
            <input
              type="checkbox"
              checked={!ui.hidden.includes(c)}
              onChange={() => toggle(c)}
            />
            <span
              className="legend__swatch"
              style={{ background: CATEGORY_COLORS[c] }}
            />
            <span>{c}</span>
            <em>{(counts[c] ?? 0).toLocaleString()}</em>
          </label>
        ))}
      </div>
    </div>
  );
}

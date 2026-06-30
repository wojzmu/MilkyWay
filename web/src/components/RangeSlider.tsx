interface Props {
  min: number;
  max: number;
  step?: number;
  value: [number, number];
  onChange: (v: [number, number]) => void;
}

/**
 * Dual-thumb range slider built from two overlaid native range inputs. The
 * inputs are pointer-events:none except their thumbs (see App.css), so both
 * thumbs stay independently draggable. Thumbs cannot cross each other.
 */
export default function RangeSlider({
  min,
  max,
  step = 1,
  value,
  onChange,
}: Props) {
  const [lo, hi] = value;
  const span = max - min || 1;
  const loPct = ((lo - min) / span) * 100;
  const hiPct = ((hi - min) / span) * 100;

  const setLo = (v: number) => onChange([Math.min(v, hi), hi]);
  const setHi = (v: number) => onChange([lo, Math.max(v, lo)]);

  return (
    <div className="range">
      <div className="range__track" />
      <div
        className="range__fill"
        style={{ left: `${loPct}%`, right: `${100 - hiPct}%` }}
      />
      <input
        className="range__input range__input--lo"
        type="range"
        min={min}
        max={max}
        step={step}
        value={lo}
        onChange={(e) => setLo(Number(e.target.value))}
        aria-label="Minimum"
      />
      <input
        className="range__input range__input--hi"
        type="range"
        min={min}
        max={max}
        step={step}
        value={hi}
        onChange={(e) => setHi(Number(e.target.value))}
        aria-label="Maximum"
      />
    </div>
  );
}

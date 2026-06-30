import { CATEGORY_ORDER, CATEGORY_COLORS } from "../categories";

interface Props {
  counts: Record<string, number>;
}

/** Floating legend mapping each category to its colour, shown in category mode.
 * Only categories actually present in the data are listed. */
export default function Legend({ counts }: Props) {
  const present = CATEGORY_ORDER.filter((c) => (counts[c] ?? 0) > 0);
  return (
    <div className="legend">
      <div className="legend__title">Category</div>
      {present.map((c) => (
        <div className="legend__row" key={c}>
          <span
            className="legend__swatch"
            style={{ background: CATEGORY_COLORS[c] }}
          />
          <span className="legend__label">{c}</span>
          <span className="legend__count">
            {counts[c].toLocaleString()}
          </span>
        </div>
      ))}
    </div>
  );
}

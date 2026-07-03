import { CATEGORY_ORDER, CATEGORY_COLORS } from "../categories";
import type { Filters, FilterDomains } from "../filters";
import RangeSlider from "./RangeSlider";

interface Props {
  filters: Filters;
  domains: FilterDomains;
  counts: Record<string, number>; // full per-category counts (unfiltered)
  spuriousCount: number; // total likely-spurious-parallax stars in the catalogue
  onChange: (f: Filters) => void;
  onReset: () => void;
  onClose: () => void;
}

export default function FilterPanel({
  filters,
  domains,
  counts,
  spuriousCount,
  onChange,
  onReset,
  onClose,
}: Props) {
  const present = CATEGORY_ORDER.filter((c) => (counts[c] ?? 0) > 0);

  const toggleCategory = (c: string) => {
    const next = new Set(filters.categories);
    if (next.has(c)) next.delete(c);
    else next.add(c);
    onChange({ ...filters, categories: next });
  };

  const allOn = present.every((c) => filters.categories.has(c));
  const setAll = (on: boolean) =>
    onChange({
      ...filters,
      categories: on ? new Set(present) : new Set(),
    });

  return (
    <div className="filter-panel" role="dialog" aria-label="Filters">
      <div className="filter-panel__head">
        <strong>Filters</strong>
        <div className="filter-panel__head-actions">
          <button className="linkbtn" onClick={onReset}>
            Reset
          </button>
          <button
            className="filter-panel__close"
            onClick={onClose}
            aria-label="Close filters"
          >
            ×
          </button>
        </div>
      </div>

      {/* Category */}
      <section className="filter-section">
        <div className="filter-section__title">
          <span>Category</span>
          <button className="linkbtn" onClick={() => setAll(!allOn)}>
            {allOn ? "None" : "All"}
          </button>
        </div>
        <div className="filter-cats">
          {present.map((c) => (
            <label className="filter-cat" key={c}>
              <input
                type="checkbox"
                checked={filters.categories.has(c)}
                onChange={() => toggleCategory(c)}
              />
              <span
                className="filter-cat__swatch"
                style={{ background: CATEGORY_COLORS[c] }}
              />
              <span className="filter-cat__label">{c}</span>
              <span className="filter-cat__count">
                {counts[c].toLocaleString()}
              </span>
            </label>
          ))}
        </div>
      </section>

      {/* Estimated mass */}
      <section className="filter-section">
        <div className="filter-section__title">
          <span>Estimated mass</span>
          <span className="filter-section__value">
            {filters.mass[0].toFixed(2)} – {filters.mass[1].toFixed(2)} M☉
          </span>
        </div>
        <RangeSlider
          min={domains.mass[0]}
          max={domains.mass[1]}
          step={0.01}
          value={filters.mass}
          onChange={(mass) => onChange({ ...filters, mass })}
        />
        <p className="filter-hint">
          Stars without a mass estimate (white dwarfs, giants) aren’t hidden by
          this slider — use the categories above.
        </p>
      </section>

      {/* Distance */}
      <section className="filter-section">
        <div className="filter-section__title">
          <span>Distance</span>
          <span className="filter-section__value">
            {filters.dist[0].toFixed(1)} – {filters.dist[1].toFixed(1)} ly
          </span>
        </div>
        <RangeSlider
          min={domains.dist[0]}
          max={domains.dist[1]}
          step={0.1}
          value={filters.dist}
          onChange={(dist) => onChange({ ...filters, dist })}
        />
      </section>

      {/* Data quality */}
      <section className="filter-section">
        <div className="filter-section__title">
          <span>Data quality</span>
        </div>
        <label className="filter-cat">
          <input
            type="checkbox"
            checked={filters.showSpurious}
            onChange={(e) =>
              onChange({ ...filters, showSpurious: e.target.checked })
            }
          />
          <span className="filter-cat__label">Show spurious-parallax stars</span>
          <span className="filter-cat__count">
            {spuriousCount.toLocaleString()}
          </span>
        </label>
        <p className="filter-hint">
          Likely distant background stars with inflated Gaia parallaxes (crowded
          fields toward the Galactic centre). Hidden by default.
        </p>
      </section>
    </div>
  );
}

import { useEffect, useMemo, useState } from "react";
import type { Star } from "./types";
import type { ColorMode } from "./categories";
import type { Filters, FilterDomains } from "./filters";
import {
  computeDomains,
  defaultFilters,
  applyFilters,
  isFiltered,
} from "./filters";
import { loadStars } from "./data/loadStars";
import StarField3D from "./components/StarField3D";
import HRDiagram from "./components/HRDiagram";
import StarDetails from "./components/StarDetails";
import Legend from "./components/Legend";
import FilterPanel from "./components/FilterPanel";
import "./App.css";

type View = "3d" | "hr";

export default function App() {
  const [stars, setStars] = useState<Star[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [error, setError] = useState<string>("");
  const [view, setView] = useState<View>("3d");
  const [colorMode, setColorMode] = useState<ColorMode>("trueColor");
  const [selected, setSelected] = useState<Star | null>(null);

  const [domains, setDomains] = useState<FilterDomains | null>(null);
  const [filters, setFilters] = useState<Filters | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);

  useEffect(() => {
    loadStars()
      .then((data) => {
        const d = computeDomains(data);
        setStars(data);
        setDomains(d);
        setFilters(defaultFilters(d));
        setStatus("ready");
      })
      .catch((e: unknown) => {
        setError(e instanceof Error ? e.message : String(e));
        setStatus("error");
      });
  }, []);

  // Per-category totals across the whole catalogue (for the filter checkboxes).
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of stars) counts[s.starClass] = (counts[s.starClass] ?? 0) + 1;
    return counts;
  }, [stars]);

  const filteredStars = useMemo(
    () => (filters ? applyFilters(stars, filters) : stars),
    [stars, filters],
  );

  // Legend reflects what's currently visible.
  const visibleCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of filteredStars)
      counts[s.starClass] = (counts[s.starClass] ?? 0) + 1;
    return counts;
  }, [filteredStars]);

  const active = filters && domains ? isFiltered(filters, domains) : false;

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">✦</span>
          <div>
            <h1>MilkyWay</h1>
            <p className="brand__sub">The solar neighbourhood within ~65 ly</p>
          </div>
        </div>

        <div className="topbar__right">
          {status === "ready" && (
            <span className="count">
              {filteredStars.length.toLocaleString()}
              {active && ` / ${stars.length.toLocaleString()}`} stars
            </span>
          )}

          {status === "ready" && (
            <button
              className={`filterbtn${active ? " filterbtn--active" : ""}`}
              onClick={() => setFiltersOpen((o) => !o)}
              aria-expanded={filtersOpen}
            >
              ⚙ Filters{active && <span className="filterbtn__dot" />}
            </button>
          )}

          <div className="viewtoggle" role="group" aria-label="Colour by">
            <button
              className={colorMode === "trueColor" ? "active" : ""}
              onClick={() => setColorMode("trueColor")}
            >
              True colour
            </button>
            <button
              className={colorMode === "category" ? "active" : ""}
              onClick={() => setColorMode("category")}
            >
              Category
            </button>
          </div>

          <div className="viewtoggle" role="tablist">
            <button
              className={view === "3d" ? "active" : ""}
              onClick={() => setView("3d")}
              role="tab"
              aria-selected={view === "3d"}
            >
              3D Map
            </button>
            <button
              className={view === "hr" ? "active" : ""}
              onClick={() => setView("hr")}
              role="tab"
              aria-selected={view === "hr"}
            >
              HR Diagram
            </button>
          </div>
        </div>

        {filtersOpen && filters && domains && (
          <FilterPanel
            filters={filters}
            domains={domains}
            counts={categoryCounts}
            onChange={setFilters}
            onReset={() => setFilters(defaultFilters(domains))}
            onClose={() => setFiltersOpen(false)}
          />
        )}
      </header>

      <main className="stage">
        {status === "loading" && (
          <div className="overlay">Loading catalogue…</div>
        )}
        {status === "error" && (
          <div className="overlay overlay--error">
            Failed to load dataset: {error}
          </div>
        )}
        {status === "ready" && (
          <>
            <div className="viewport">
              {view === "3d" ? (
                <StarField3D
                  stars={filteredStars}
                  selected={selected}
                  onSelect={setSelected}
                  colorMode={colorMode}
                />
              ) : (
                <HRDiagram
                  stars={filteredStars}
                  selected={selected}
                  onSelect={setSelected}
                  colorMode={colorMode}
                />
              )}
              {colorMode === "category" && <Legend counts={visibleCounts} />}
            </div>
            <StarDetails star={selected} onClose={() => setSelected(null)} />
          </>
        )}
      </main>
    </div>
  );
}

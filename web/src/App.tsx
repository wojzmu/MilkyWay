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
import { loadPointCloud, type PointCloud } from "./data/loadPointCloud";
import {
  loadDatasetManifest,
  resolveInitialDataset,
  rememberDataset,
  isBinDataset,
  type DatasetMeta,
} from "./data/datasets";
import StarField3D from "./components/StarField3D";
import GalaxyField3D, { type CloudSettings } from "./components/GalaxyField3D";
import PointDetails from "./components/PointDetails";
import CloudControls from "./components/CloudControls";
import { defaultCloudUi, type CloudUi } from "./cloudUi";
import { CATEGORY_ORDER } from "./categories";
import HRDiagram from "./components/HRDiagram";
import StarDetails from "./components/StarDetails";
import Legend from "./components/Legend";
import FilterPanel from "./components/FilterPanel";
import DatasetPicker from "./components/DatasetPicker";
import AboutModal from "./components/AboutModal";
import { loadStarNames, type StarName } from "./data/starNames";
import "./App.css";

type View = "3d" | "hr";

export default function App() {
  const [stars, setStars] = useState<Star[]>([]);
  const [starNames, setStarNames] = useState<Map<string, StarName>>(new Map());
  useEffect(() => {
    let ignore = false;
    loadStarNames().then((m) => !ignore && setStarNames(m));
    return () => {
      ignore = true;
    };
  }, []);
  const [status, setStatus] = useState<"loading" | "ready" | "error">(
    "loading",
  );
  const [error, setError] = useState<string>("");
  const [view, setView] = useState<View>("3d");
  const [colorMode, setColorMode] = useState<ColorMode>("trueColor");
  const [selected, setSelected] = useState<Star | null>(null);

  // Binary point-cloud mode (datasets with format "bin").
  const [cloud, setCloud] = useState<PointCloud | null>(null);
  const [loadedKind, setLoadedKind] = useState<"csv" | "bin">("csv");
  const [cloudUi, setCloudUi] = useState<CloudUi>(defaultCloudUi(1250));
  const [selectedPoint, setSelectedPoint] = useState<number | null>(null);
  const [progress, setProgress] = useState("");

  const [datasets, setDatasets] = useState<DatasetMeta[]>([]);
  const [datasetFile, setDatasetFile] = useState<string | null>(null);

  const [domains, setDomains] = useState<FilterDomains | null>(null);
  const [filters, setFilters] = useState<Filters | null>(null);
  const [filtersOpen, setFiltersOpen] = useState(false);
  const [aboutOpen, setAboutOpen] = useState(false);

  // Load the dataset manifest once, then pick the initial file (URL param >
  // remembered choice > default > first entry).
  useEffect(() => {
    loadDatasetManifest().then((list) => {
      setDatasets(list);
      setDatasetFile(resolveInitialDataset(list));
    });
  }, []);

  // (Re)load the catalogue whenever the selected dataset changes. The `ignore`
  // flag drops a stale response if the user switches again mid-load.
  useEffect(() => {
    if (!datasetFile) return;
    let ignore = false;
    setStatus("loading");
    setSelected(null);
    setSelectedPoint(null);
    setProgress("");
    const meta = datasets.find((d) => d.file === datasetFile);
    const request: Promise<() => void> = isBinDataset(meta)
      ? loadPointCloud(datasetFile, (t) => !ignore && setProgress(t)).then(
          (pc) => () => {
            setCloud(pc);
            setCloudUi(
              defaultCloudUi(pc.index.selection?.dist_pc_max ?? 1250),
            );
            setLoadedKind("bin");
          },
        )
      : loadStars(datasetFile).then((data) => () => {
          const d = computeDomains(data);
          setStars(data);
          setDomains(d);
          setFilters(defaultFilters(d));
          setLoadedKind("csv");
        });
    request
      .then((apply) => {
        if (ignore) return;
        apply();
        setStatus("ready");
      })
      .catch((e: unknown) => {
        if (ignore) return;
        setError(e instanceof Error ? e.message : String(e));
        setStatus("error");
      });
    return () => {
      ignore = true;
    };
  }, [datasetFile, datasets]);

  const handleDatasetChange = (file: string) => {
    if (file === datasetFile) return;
    rememberDataset(file);
    setDatasetFile(file);
  };

  // Per-category totals across the whole catalogue (for the filter checkboxes).
  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const s of stars) counts[s.starClass] = (counts[s.starClass] ?? 0) + 1;
    return counts;
  }, [stars]);

  // Total likely-spurious-parallax stars (for the data-quality toggle label).
  const spuriousCount = useMemo(
    () => stars.reduce((n, s) => n + (s.spuriousParallax ? 1 : 0), 0),
    [stars],
  );

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

  const isBin = loadedKind === "bin" && cloud !== null;
  const cloudMaxDist = cloud?.index.selection?.dist_pc_max ?? 1250;

  const theFarestDistance = useMemo(() => {
    if (isBin) return Math.round(cloudMaxDist * 3.26156);
    if (stars.length === 0) return null;
    return Math.max(...stars.map((s) => s.distPc ? Math.round(s.distPc) : 0));
  }, [stars, isBin, cloudMaxDist]);

  const cloudSettings = useMemo<CloudSettings>(() => {
    let mask = 0;
    cloud?.classCodes.forEach((name, code) => {
      if (!cloudUi.hidden.includes(name)) mask |= 1 << code;
    });
    return {
      distMax: cloudUi.distMax,
      fMax: cloudUi.fMax,
      fraction: cloudUi.percent / 100,
      pointSize: cloudUi.pointSize,
      brightness: cloudUi.brightness,
      classMask: mask,
      labels: cloudUi.labels,
    };
  }, [cloud, cloudUi]);

  // Per-class totals and the number of points currently drawn.
  const cloudClassCounts = useMemo(() => {
    const counts: Record<string, number> = {};
    if (!cloud) return counts;
    const per = new Array<number>(cloud.classCodes.length).fill(0);
    for (let i = 0; i < cloud.n; i++) per[cloud.classes[i]]++;
    cloud.classCodes.forEach((name, code) => (counts[name] = per[code]));
    return counts;
  }, [cloud]);

  const cloudDrawn = useMemo(() => {
    if (!cloud) return 0;
    const k = Math.max(1, Math.round(cloudSettings.fraction * cloud.n));
    const d2 = cloudSettings.distMax ** 2;
    const pos = cloud.positions;
    let c = 0;
    for (let i = 0; i < k; i++) {
      const x = pos[3 * i];
      const y = pos[3 * i + 1];
      const z = pos[3 * i + 2];
      if (x * x + y * y + z * z > d2) continue;
      if (((cloudSettings.classMask >> cloud.classes[i]) & 1) === 0) continue;
      c++;
    }
    return c;
  }, [cloud, cloudSettings]);

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand__mark">✦</span>
          <div>
            <h1>MilkyWay</h1>
            <p className="brand__sub">The solar neighbourhood within ~{theFarestDistance ? theFarestDistance.toLocaleString() : "?"} ly</p>
          </div>
        </div>

        <div className="topbar__right">
          {datasetFile && (
            <DatasetPicker
              datasets={datasets}
              value={datasetFile}
              onChange={handleDatasetChange}
            />
          )}

          {status === "ready" && (
            <span className="count">
              {isBin && cloud ? (
                <>
                  {cloudDrawn.toLocaleString()} / {cloud.n.toLocaleString()}
                </>
              ) : (
                <>
                  {filteredStars.length.toLocaleString()}
                  {active && ` / ${stars.length.toLocaleString()}`}
                </>
              )}{" "}
              stars
            </span>
          )}

          {status === "ready" && !isBin && (
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
              className={view === "3d" || isBin ? "active" : ""}
              onClick={() => setView("3d")}
              role="tab"
              aria-selected={view === "3d" || isBin}
            >
              3D Map
            </button>
            <button
              className={view === "hr" && !isBin ? "active" : ""}
              onClick={() => setView("hr")}
              role="tab"
              aria-selected={view === "hr" && !isBin}
              disabled={isBin}
              title={
                isBin ? "HR diagram is available for CSV datasets" : undefined
              }
            >
              HR Diagram
            </button>
          </div>

          <button
            className="iconbtn"
            onClick={() => setAboutOpen(true)}
            aria-label="Data sources"
            title="Data sources"
          >
            ⓘ
          </button>
        </div>

        {filtersOpen && !isBin && filters && domains && (
          <FilterPanel
            filters={filters}
            domains={domains}
            counts={categoryCounts}
            spuriousCount={spuriousCount}
            onChange={setFilters}
            onReset={() => setFilters(defaultFilters(domains))}
            onClose={() => setFiltersOpen(false)}
          />
        )}
      </header>

      <main className="stage">
        {status === "loading" && (
          <div className="overlay">{progress || "Loading catalogue…"}</div>
        )}
        {status === "error" && (
          <div className="overlay overlay--error">
            Failed to load dataset: {error}
          </div>
        )}
        {status === "ready" && isBin && cloud && (
          <>
            <div className="viewport">
              <GalaxyField3D
                cloud={cloud}
                settings={cloudSettings}
                colorMode={colorMode}
                selected={selectedPoint}
                onSelect={setSelectedPoint}
              />
              <CloudControls
                ui={cloudUi}
                maxDist={cloudMaxDist}
                counts={cloudClassCounts}
                onChange={setCloudUi}
              />
              {colorMode === "category" && (
                <Legend
                  counts={Object.fromEntries(
                    CATEGORY_ORDER.filter(
                      (c) => !cloudUi.hidden.includes(c),
                    ).map((c) => [c, cloudClassCounts[c] ?? 0]),
                  )}
                />
              )}
            </div>
            <PointDetails
              cloud={cloud}
              index={selectedPoint}
              onClose={() => setSelectedPoint(null)}
            />
          </>
        )}
        {status === "ready" && !isBin && (
          <>
            <div className="viewport">
              {view === "3d" ? (
                <StarField3D
                  stars={filteredStars}
                  selected={selected}
                  onSelect={setSelected}
                  colorMode={colorMode}
                  names={starNames}
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
            <StarDetails
              star={selected}
              name={selected ? starNames.get(selected.starId) : undefined}
              onClose={() => setSelected(null)}
            />
          </>
        )}
      </main>

      {aboutOpen && <AboutModal onClose={() => setAboutOpen(false)} />}
    </div>
  );
}

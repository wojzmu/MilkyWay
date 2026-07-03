# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Two parts that share one dataset:

1. **Pipeline** (the `milkyway/` package, with [MilkyWay.py](MilkyWay.py) as a
   thin CLI entry point) — builds a merged, de-duplicated catalogue of nearby
   stars from **Gaia DR3** + **Hipparcos**, expresses all photometry in the Gaia
   system, assigns each star a true-colour RGB from its temperature, estimates
   masses, computes UVW Galactic space velocities, classifies each star, flags
   spurious parallaxes, and renders PNG figures. [Dataset.md](Dataset.md) is the
   column-by-column reference for the CSV.
2. **Web viewer** ([web/](web/)) — a Vite + React 19 + TypeScript single-page app
   that visualises that CSV as an interactive 3D star map and HR diagram. See the
   [Web app](#web-app-web) section below.

> Note: `Dataset.md` refers to the script as `nearby_stars_pipeline.py`; the
> actual file is `MilkyWay.py`. Same pipeline.

## Commands

```bash
pip install astroquery astropy numpy pandas matplotlib adjustText   # dependencies (no requirements.txt)
python MilkyWay.py                              # full pipeline (networked) -> CSV + PNGs (see below)
python MilkyWay.py --plot-only                  # offline: load existing CSV, only redraw the PNGs
python MilkyWay.py --plot-only --csv FILE.csv   # ...from a specific CSV
python MilkyWay.py --min-mass 0.5               # keep only stars with mass_est >= 0.5 Msun (drops unknown-mass rows)
python MilkyWay.py --max-dist 30                # limit the search volume to 30 pc (raises the parallax floor)
```

`--max-dist PC` overrides the default `MAX_DIST_PC` (60 pc) search radius. On a
full run it is converted to a parallax floor (`1000/dist` mas) pushed into both
ADQL queries, and the output filename becomes `nearby_stars_<dist>pc.csv`. With
`--plot-only` it instead trims the already-loaded CSV to `dist_pc <= PC` (reading
from the standard 60 pc catalogue by default, since a smaller-volume file may not
exist yet).

There is no test suite, linter config, or build step. A plain run hits live ESA
Gaia TAP and SIMBAD services over the network, so it needs connectivity and takes
a while. **`--plot-only` skips all network calls** — it loads a catalogue CSV and
only regenerates the figures, which is the fast loop when iterating on plotting
code. The `/figures` project skill wraps this (see `.claude/skills/figures/`).

The colour math (`teff_to_rgb`, `teff_from_bprp`, `build_rgb_table`, the `_poly`
photometric transforms) imports nothing network-bound and is deliberately
separable — it can be exercised in a REPL without astroquery installed. The
astroquery/astropy imports are all **lazy** (inside functions) for exactly this
reason; preserve that pattern when editing.

## Architecture

### Package layout (`milkyway/`)

[MilkyWay.py](MilkyWay.py) is a thin shim: it re-exports the package's public API
(so `from MilkyWay import <name>` and `python MilkyWay.py` both still work) and
calls `milkyway.cli.main()`. The logic is split by concern:

| Module | Contents |
|---|---|
| `config.py` | constants + `PROJECT_ROOT` (output anchor) |
| `photometry.py` | Johnson↔Gaia transforms (`_poly`, `g_minus_v_*`, `bprp_from_vi`) |
| `color.py` | `teff_from_bprp`, blackbody→sRGB, `build_rgb_table` |
| `mass.py` | `estimate_mass`, `mg_upper_bound_for_mass`, `apply_min_mass` |
| `classify.py` | spectral/CMD classification **and** `flag_spurious_parallax` (shared `_MS_*` ridge) |
| `query.py` | Gaia/Hipparcos ADQL + SIMBAD (network) |
| `astrometry.py` | epoch propagation, cross-match, UVW, `add_galactic_xyz` (astropy) |
| `pipeline.py` | `gaia/hipparcos_to_common` + `build_merged_catalogue` orchestrator |
| `plots.py` | figures + helpers (`_resolve_path`, `_save`, `_label_famous`) |
| `cli.py` | argparse `main()` |

`color.py`/`photometry.py`/`mass.py`/`classify.py` have **no network imports** and
are runnable without astroquery/astropy; the astroquery/astropy calls in
`query.py`/`astrometry.py` stay function-local (lazy). Preserve that separation.

### Pipeline flow

`build_merged_catalogue()` (in `pipeline.py`) is the orchestrator and the best
entry point for understanding flow. The stages, in order:

1. **Query** — `query_gaia()` and `query_hipparcos()` fire ADQL at the same ESA
   TAP service. Selection cuts (`MIN_PARALLAX_MAS`, parallax-over-error, RUWE)
   are inline in the ADQL strings; the module constants gate them. `--min-mass`
   additionally pushes a **coarse server-side pre-filter** into `query_gaia`'s
   `WHERE`: a lower mass bound becomes an upper bound on absolute G
   (`mg_upper_bound_for_mass` inverts the MS relation), so faint low-mass stars a
   min-mass run would discard are never downloaded. It is deliberately loose (a
   margin keeps a superset); the *exact* cut is `apply_min_mass()` in step 4.
   Keep the two in sync — both must trace to the same `_MASS_MG`/`_MASS_MSUN`.
2. **De-duplicate** — Hipparcos is merged in only to recover the brightest/closest
   stars that *saturate* in Gaia (Sirius, Procyon, Alpha Cen). `propagate_hipparcos()`
   epoch-shifts Hipparcos J1991.25 positions to Gaia's J2016.0 along proper motion,
   then `cross_match()` drops Hipparcos rows within `MATCH_RADIUS_ARCSEC` of a Gaia
   star. Non-matches are kept as "gap-fillers".
3. **Harmonise** — `gaia_to_common()` and `hipparcos_to_common()` map both
   catalogues onto one schema. Hipparcos Johnson V/B-V/V-I is converted to Gaia
   G/BP-RP via the official EDR3 Table 5.7 polynomials (`g_minus_v_from_bv`,
   `bprp_from_vi`, `g_minus_v_from_bprp`). The `phot_origin` column records
   `native_gaia` vs `transformed_from_johnson`.
4. **Derive** — `add_galactic_xyz()` (l/b + heliocentric Cartesian), display
   colour (`teff_from_bprp` -> `build_rgb_table`), `estimate_mass()` (`mass_est`),
   `compute_uvw()`, and `flag_spurious_parallax()` (`spurious_parallax`). When
   `--min-mass` is set, `apply_min_mass()` applies the exact `mass_est >= min`
   cut here (dropping unknown-mass rows) — it also runs standalone in the
   `--plot-only` path.
5. **Name** — `add_simbad_names()` batches TAP queries against SIMBAD's
   `ident`/`basic` tables; failure is caught and the pipeline continues with NaN
   name columns.

### Two distinct temperatures — do not conflate

- `teff_gspphot`: the **scientific** temperature from Gaia Apsis. Often NaN.
- `teff_color`: temperature inferred from BP-RP purely to pick a display colour,
  via a monotonic interpolation over approximate anchors (`_BPRP_ANCHORS` /
  `_TEFF_ANCHORS`). **Display only, not science.** All RGB output derives from
  this, never from `teff_gspphot`.

### Colour rendering

`teff_to_rgb()` integrates a Planck blackbody against the CIE 1931 colour-matching
functions (Wyman-Sloan-Shirley analytic fit, `_cie_xyz_bar`) -> linear sRGB (D65)
-> gamma. Output is normalised *hue* at full brightness (max channel = 1), so
luminosity is intentionally discarded here. Unknown temperature -> grey `#808080`.
`build_rgb_table()` builds a 50 K-quantised lookup table rather than calling
`teff_to_rgb` per star.

### Visualisation outputs

The `__main__` block writes the CSV then four PNGs, all saved next to the script
via `_resolve_path()` (absolute path, so cwd doesn't matter) and confirmed by
`_save()`:

- `plot_hr()` -> `hr_diagram.png` — H-R diagram (BP-RP vs `abs_g`), points in true colour.
- `plot_maps()` -> `map_xy.png` (face-on X-Y) and `map_xz.png` (edge-on X-Z),
  heliocentric Galactic parsec coordinates, Sun at the origin.
- `plot_3d()` -> `map_3d.png` — static 3D scatter of X/Y/Z at a fixed camera angle.

All plotting functions force the non-interactive **`Agg`** backend (headless-safe)
and share three helpers: `_resolve_path()`, `_save()`, and `_label_famous()`.
`_label_famous()` labels only the stars whose `proper_name` matches the
`FAMOUS_STARS` list (case-insensitive substring), boxed and repelled with
`adjustText`. `plot_3d` labels directly instead — `adjustText` is 2D-only.

Note the sample is a ~20 pc **sphere**, not a disk: X and Z spreads are nearly
equal, so the "edge-on" map shows a round blob, not the flattened Galactic plane
(the disk's ~300 pc scale height is far larger than this volume). Seeing the
plane edge-on would require relaxing `MIN_PARALLAX_MAS` to sample out to
hundreds of pc.

## Web app (`web/`)

A separate Vite + React 19 + TypeScript SPA (its own `package.json`, not part of
the Python toolchain). Run from inside `web/`:

```bash
npm install
npm run dev       # Vite dev server, http://localhost:5173
npm run build     # tsc -b && vite build -> web/dist/
npm run lint      # oxlint (config: web/.oxlintrc.json)
npm run preview   # serve the production build
```

- **Two views**, toggled in [App.tsx](web/src/App.tsx), both coloured by each
  star's true-colour RGB (or by `star_class` category): a 3D map
  ([StarField3D.tsx](web/src/components/StarField3D.tsx), `@react-three/fiber` +
  `three`) and an HR diagram ([HRDiagram.tsx](web/src/components/HRDiagram.tsx),
  `plotly.js`). Clicking a star in either view selects it in both.
- **Data flow** — [loadStars.ts](web/src/data/loadStars.ts) fetches a CSV from
  `web/public/` (papaparse) and maps rows to the typed `Star`
  ([types.ts](web/src/types.ts)). The filename is `VITE_DATASET_FILE` from
  `web/.env`. Filtering/domains live in [filters.ts](web/src/filters.ts),
  categories in [categories.ts](web/src/categories.ts).

> The `web/public/*psc.csv` files are the user's own working datasets — **leave
> them alone** (don't regenerate, overwrite, or "fix" them). They carry extra
> columns beyond the pipeline output (`star_class`, `sp_type`, `mass_flame`,
> `age_flame`, `mass_est`); `star_class` drives category colouring, the legend,
> and the filters. Columns the app reads but a CSV lacks parse as
> `null`/`"Unknown"`, so any dataset still loads.

## Conventions when editing

- **Keep astroquery/astropy imports lazy** (function-local), so the colour/photometry
  math stays runnable without network deps.
- Photometric transforms must **return NaN outside their validity range**, never
  extrapolate — the existing `np.where(...range..., _poly(...), np.nan)` pattern.
- The validity ranges and polynomial coefficients trace to specific published
  sources (Gaia EDR3 Table 5.7, Jordi 2010, Pecaut & Mamajek 2013); if you touch
  the numbers, update the comment/reference, and mirror any output-schema change
  in [Dataset.md](Dataset.md)'s field table.
- `radial_velocity` is NaN for all Hipparcos rows and most Gaia rows, so `U/V/W`
  are NaN for the majority — guard derived kinematics accordingly.

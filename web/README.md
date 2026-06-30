# MilkyWay — Solar Neighbourhood Explorer

Interactive web app that visualises the nearby-stars catalogue
(`nearby_stars_merged.csv`, Gaia DR3 + Hipparcos within ~20 pc) produced by the
pipeline in [`../MilkyWay.py`](../MilkyWay.py).

Two coordinated views, both coloured by each star's true-colour RGB:

- **3D Map** — every star plotted in heliocentric Galactic Cartesian
  coordinates (pc), with the Sun at the origin. Orbit, zoom, and click a star to
  inspect it. Built with `@react-three/fiber` + `three`.
- **HR Diagram** — BP−RP colour vs absolute G magnitude (Plotly). Click a point
  to select the same star as in the 3D view.

Stack: **Vite + React 19 + TypeScript**.

## Develop

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build to dist/
npm run preview  # serve the production build
```

## Data

The dataset is served from [`public/nearby_stars_merged.csv`](public/nearby_stars_merged.csv),
a copy of the repo-root output. If you regenerate the catalogue, refresh this
copy:

```bash
cp ../nearby_stars_merged.csv public/nearby_stars_merged.csv
```

Parsing and the typed `Star` schema live in
[`src/data/loadStars.ts`](src/data/loadStars.ts) and
[`src/types.ts`](src/types.ts). The column-by-column reference is
[`../Dataset.md`](../Dataset.md).

> Display colours come from `teff_color`/`rgb_*` (derived from BP−RP for
> rendering only) — **not** from the scientific `teff_gspphot`.

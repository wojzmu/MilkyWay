# MilkyWay — Solar Neighbourhood Explorer

Interactive web app that visualises the nearby-stars catalogue (Gaia DR3 +
Hipparcos) produced by the pipeline in [`../MilkyWay.py`](../MilkyWay.py).

Two coordinated views, both coloured by each star's true-colour RGB (or by
`star_class` category):

- **3D Map** — every star plotted in heliocentric Galactic Cartesian
  coordinates (pc), with the Sun at the origin. Orbit, zoom, and click a star to
  inspect it. Built with `@react-three/fiber` + `three`.
- **HR Diagram** — BP−RP colour vs absolute G magnitude (Plotly). Click a point
  to select the same star as in the 3D view.

Selecting a star in either view highlights it in both and opens a details panel.
A **filter panel** narrows the sample (by distance, magnitude, category, and a
spurious-parallax toggle), and an **ⓘ Data sources** dialog credits the archives.

Stack: **Vite + React 19 + TypeScript**.

## Develop

```bash
npm install
npm run dev      # http://localhost:5173
npm run build    # typecheck + production build to dist/
npm run preview  # serve the production build
npm run lint     # oxlint
```

## Data

The app loads catalogue CSVs served from [`public/`](public/). Which one is shown
is chosen **at runtime** from a curated manifest,
[`public/datasets.json`](public/datasets.json) — the **Dataset** picker in the top
bar lists each entry by its friendly `label`:

```json
{
  "datasets": [
    { "file": "nearby_stars_60.0pc.csv",
      "label": "All stars within 60 pc",
      "description": "…",
      "default": true }
  ]
}
```

To offer another dataset, drop the CSV in `public/` and add an entry here. The
active file resolves by precedence **`?dataset=<file>` URL param → `localStorage`
→ manifest `default` → first entry**, and the choice is persisted back to both
(so links stay shareable). `VITE_DATASET_FILE` (see [`.env.example`](.env.example))
is only a fallback used if the manifest can't be fetched.

> **Deploying to GitHub Pages:** the workflow builds from a fresh checkout, so any
> **untracked** CSV in `public/` won't reach production, and GitHub Pages rejects
> files over 100 MB. Keep the manifest pointing at committed, reasonably-sized
> files (the default `nearby_stars_60.0pc.csv` is both).

Parsing and the typed `Star` schema live in
[`src/data/loadStars.ts`](src/data/loadStars.ts) and
[`src/types.ts`](src/types.ts); the manifest logic in
[`src/data/datasets.ts`](src/data/datasets.ts). The column-by-column reference is
[`../Dataset.md`](../Dataset.md). Columns the app reads but a CSV happens to lack
parse as `null`/`"Unknown"`, so any pipeline-shaped dataset still loads.

> Display colours come from `teff_color`/`rgb_*` (derived from BP−RP for
> rendering only) — **not** from the scientific `teff_gspphot`.

## Deploy

Deploys to GitHub Pages via
[`../.github/workflows/main.yml`](../.github/workflows/main.yml) on push to
`master`. Vite `base` is `/MilkyWay/`, so the app is served from
`https://<user>.github.io/MilkyWay/`.

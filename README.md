# MilkyWay — the solar neighbourhood, mapped

MilkyWay builds a clean, de-duplicated catalogue of the stars around the Sun from
**Gaia DR3** and **Hipparcos**, gives every star a physically-motivated true
colour, estimated mass and space velocity, and then lets you explore the result
as an interactive 3D star map and Hertzsprung–Russell diagram.

The repository has two parts that share one dataset:

1. **Pipeline** (Python) — queries ESA's archives, merges and harmonises the two
   catalogues onto a single photometric system, derives colours/masses/kinematics,
   flags spurious parallaxes, and renders figures.
2. **Web viewer** (`web/`) — a Vite + React + TypeScript single-page app that
   visualises the catalogue CSV in the browser.

---

## What the pipeline does

Starting from the nearest, well-measured stars it:

- **queries Gaia DR3 + Hipparcos** over ESA's TAP service (Hipparcos fills the gap
  where Gaia saturates on the brightest, closest stars — Sirius, Procyon,
  Alpha Centauri);
- **de-duplicates** by epoch-propagating Hipparcos positions to Gaia's J2016.0 and
  cross-matching;
- **harmonises photometry** onto the Gaia G / BP−RP system (official Gaia EDR3
  transforms);
- **derives** a true-colour RGB per star (blackbody → CIE 1931 → sRGB), an
  estimated mass, Galactic Cartesian coordinates and UVW space velocities;
- **classifies** each star and **flags likely spurious parallaxes** (crowded-field
  contamination toward the Galactic centre);
- **names** stars from SIMBAD;
- **renders** an H-R diagram and face-on / edge-on / 3D maps as PNGs.

The two temperatures are kept distinct: `teff_gspphot` (scientific, from Gaia
Apsis) versus `teff_color` (inferred from BP−RP **for display only**). All colour
output derives from the latter.

See **[Dataset.md](Dataset.md)** for the column-by-column dataset reference and
**[CLAUDE.md](CLAUDE.md)** for the architecture in depth.

### Run it

```bash
pip install astroquery astropy numpy pandas matplotlib adjustText   # no requirements.txt

python MilkyWay.py                       # full pipeline (networked) -> CSV + PNGs
python MilkyWay.py --plot-only           # offline: reuse an existing CSV, redraw figures
python MilkyWay.py --max-dist 30         # limit the search volume to 30 pc
python MilkyWay.py --min-mass 0.5        # keep only stars with mass_est >= 0.5 Msun
```

A full run hits live Gaia TAP + SIMBAD services, so it needs connectivity and takes
a while; `--plot-only` skips all network calls and just regenerates the figures.
Output (`nearby_stars_<dist>pc.csv` plus `hr_diagram.png`, `map_xy.png`,
`map_xz.png`, `map_3d.png`) lands at the repository root.

The code lives in the `milkyway/` package; [MilkyWay.py](MilkyWay.py) is a thin CLI
entry point. The colour/photometry/mass/classification math has no network imports
and is runnable without astroquery/astropy installed.

## The web viewer

An interactive explorer of the catalogue CSV — two coordinated views (a 3D map and
an H-R diagram), each star coloured by its true RGB (or by category). Click a star
in either view to select it in both. A dataset picker lets you switch between the
CSVs listed in `web/public/datasets.json`.

```bash
cd web
npm install
npm run dev       # http://localhost:5173
npm run build     # typecheck + production build -> web/dist/
```

More detail in **[web/README.md](web/README.md)**. The app deploys to GitHub Pages
via [.github/workflows/main.yml](.github/workflows/main.yml) (Vite `base` is
`/MilkyWay/`).

## Repository layout

```
MilkyWay.py            # CLI entry point (thin shim over the package)
milkyway/              # the pipeline, split by concern (query, photometry,
                       #   colour, mass, classify, astrometry, pipeline, plots, cli)
Dataset.md             # dataset column reference
CLAUDE.md              # architecture & conventions
web/                   # Vite + React + TypeScript viewer
  public/              #   served CSVs + datasets.json manifest
  src/                 #   components, data loading, filters
```

## Data sources & attribution

The catalogue is built from public astronomical archives — please credit them if
you reuse the data:

- **Gaia DR3** — ESA / Gaia DPAC · <https://www.cosmos.esa.int/gaia>
- **Hipparcos** — ESA (1997) · <https://www.cosmos.esa.int/web/hipparcos>
- **Star names & spectral types** — SIMBAD, CDS Strasbourg · <https://simbad.cds.unistra.fr/simbad/>

Photometric transforms and reference relations trace to specific published
sources (Gaia EDR3 documentation Table 5.7, Jordi et al. 2010, Pecaut & Mamajek
2013); see the inline comments and [Dataset.md](Dataset.md).

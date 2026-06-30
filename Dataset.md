# Nearby-Star Dataset — Documentation

A merged, de-duplicated catalogue of the stars in the solar neighbourhood,
built from **Gaia DR3** and supplemented with **Hipparcos**. All photometry is
expressed in a single (Gaia) system, every star carries a true-colour RGB value,
and Galactic space velocities (UVW) are computed where possible.

Produced by `nearby_stars_pipeline.py`. Primary output file:
`nearby_stars_merged.csv`.

---

## 1. How the dataset is built

1. **Query Gaia DR3** (`gaiadr3.gaia_source`) for the nearest, well-measured stars.
2. **Query Hipparcos** (`public.hipparcos`, same ESA TAP service) for nearby
   bright stars — these fill Gaia's gap, since Gaia saturates on the brightest
   (and closest) stars such as Sirius, Procyon and Alpha Centauri.
3. **Epoch-propagate** Hipparcos positions from J1991.25 to Gaia's J2016.0 epoch
   along each star's proper motion, then **cross-match** the two catalogues.
   A Hipparcos star that matches a Gaia star is dropped as a duplicate; one that
   matches nothing is added as a gap-filler.
4. **Transform** Hipparcos Johnson photometry (V, B−V, V−I) onto the Gaia
   G / BP−RP system using the official Gaia EDR3 relations.
5. **Assign a true-colour RGB** to each star from its colour-derived temperature.
6. **Compute UVW** Galactic space velocities (requires radial velocity).
7. **Attach names** from SIMBAD — resolve each `star_id` to its primary
   designation and proper name (e.g. "Sirius") where one exists.

### Selection criteria

| Catalogue | Filter | Meaning |
|---|---|---|
| Gaia | `parallax > 50` | closer than ~20 pc |
| Gaia | `parallax_over_error > 10` | parallax reliable to ≤10% |
| Gaia | `ruwe < 1.4` | clean single-star astrometry |
| Hipparcos | `plx > 50` | closer than ~20 pc |
| Hipparcos | `plx / e_plx > 10` | parallax reliable to ≤10% |

The 20 pc cut and `TOP 1000` limit are configurable in the script
(`MIN_PARALLAX_MAS`, `query_gaia(limit=...)`).

---

## 2. Field reference (merged catalogue)

These are the columns in `nearby_stars_merged.csv`.

| Field | Description | Unit | Source / derivation | Notes |
|---|---|---|---|---|
| `star_id` | Identifier, prefixed by catalogue | — | `Gaia DR3 <source_id>` or `HIP <hip>` | Not a proper name; see §5 to attach "Sirius" etc. |
| `ra` | Right ascension (ICRS) | degrees | native (Gaia); epoch-propagated to J2016.0 (Hipparcos) | Equatorial longitude on the sky |
| `dec` | Declination (ICRS) | degrees | as above | Equatorial latitude on the sky |
| `parallax_mas` | Trigonometric parallax | mas (milliarcsec) | Gaia `parallax` / Hipparcos `plx` | Larger = closer |
| `dist_pc` | Distance from the Sun | parsec | `1000 / parallax_mas` | 1 pc ≈ 3.26 ly. Valid because parallax is reliable here |
| `l` | Galactic longitude | degrees | from ICRS ra/dec (astropy), all rows | Longitude measured from the Galactic centre |
| `b` | Galactic latitude | degrees | as above | Latitude above/below the Galactic plane |
| `x_pc` | Cartesian X (toward Galactic centre) | parsec | `dist_pc · cos(b) · cos(l)` | Sun at origin |
| `y_pc` | Cartesian Y (toward rotation) | parsec | `dist_pc · cos(b) · sin(l)` | Sun at origin |
| `z_pc` | Cartesian Z (toward NGP) | parsec | `dist_pc · sin(b)` | Sun at origin |
| `pmra` | Proper motion in RA | mas/yr | native | Already includes cos(dec) (μα*) |
| `pmdec` | Proper motion in Dec | mas/yr | native | Angular drift per year |
| `radial_velocity` | Line-of-sight velocity | km/s | Gaia RVS | **Often NaN** — only the brighter RVS subset has it; always NaN for Hipparcos rows |
| `g_mag` | Apparent magnitude, Gaia G | mag | native (Gaia); `V + (G−V)` (Hipparcos) | Brightness as seen from Earth; smaller = brighter |
| `bp_rp` | Colour index, Gaia BP−RP | mag | native (Gaia); from V−I (Hipparcos) | Blue/hot = small; red/cool = large |
| `v_mag` | Apparent magnitude, Johnson V | mag | native (Hipparcos); `G − (G−V)` (Gaia) | Provided so the table works in either photometric system |
| `abs_g` | Absolute magnitude, Gaia G | mag | `g_mag + 5·log10(parallax_mas) − 10` | Intrinsic luminosity proxy; **y-axis of the H-R diagram** |
| `teff_gspphot` | Effective temperature (Gaia Apsis) | K | Gaia `teff_gspphot` | The *scientific* temperature. NaN for Hipparcos rows and many Gaia rows |
| `teff_color` | Temperature inferred from BP−RP | K | colour→Teff interpolation | **For colouring only**, not science. Approximate, esp. for M dwarfs |
| `rgb_r`, `rgb_g`, `rgb_b` | True-colour components | 0–255 | blackbody(`teff_color`)→CIE→sRGB | Hue at full brightness; brightness handled separately |
| `rgb_hex` | Same colour as hex string | `#RRGGBB` | as above | `#808080` (grey) where temperature is unknown |
| `phot_origin` | Provenance of photometry | — | `native_gaia` or `transformed_from_johnson` | Tells you which numbers were measured vs converted |
| `source_catalogue` | Origin catalogue | — | `Gaia` or `Hipparcos` | Hipparcos rows are the bright gap-fillers |
| `U` | Galactic velocity toward centre | km/s | astropy 6D transform | Heliocentric. NaN without radial velocity |
| `V` | Galactic velocity toward rotation | km/s | as above | Heliocentric |
| `W` | Galactic velocity toward NGP | km/s | as above | Heliocentric |
| `simbad_main_id` | SIMBAD primary designation | — | SIMBAD `basic.main_id` via TAP | e.g. `* alf CMa`; NaN if not in SIMBAD |
| `proper_name` | IAU / common name | — | SIMBAD `NAME`-prefixed identifier | e.g. `Sirius`; NaN for the majority (only a few hundred stars have one) |
| `sp_type` | SIMBAD MK spectral type | — | SIMBAD `basic.sp_type` via TAP | e.g. `A1V`, `M3.5V`, `DA2`; NaN for stars SIMBAD has not typed (most faint Gaia stars) |
| `star_class` | Coarse evolutionary category | — | `sp_type` luminosity class, else CMD position | One of `Main sequence`, `White dwarf`, `Subgiant`, `Red giant`, `Giant`, `Supergiant`, `Brown dwarf`, `Subdwarf`, `Unknown`. See note below |

### Note on `star_class`

A coarse category, **not** spectroscopy. It is assigned in priority order:

1. **SIMBAD spectral type** (`sp_type`) when present — the MK luminosity class is
   authoritative: `V`/`VI` → Main sequence, `IV` → Subgiant, `II`/`III` → Giant
   (Red giant if the spectral letter is K/M), `I` → Supergiant, a leading `D`
   (DA/DB/…) → White dwarf, `L`/`T`/`Y` → Brown dwarf, `sd…` → Subdwarf.
2. **Colour–magnitude position** (`abs_g` vs `bp_rp`) as a fallback for the many
   faint stars SIMBAD has not typed. White dwarfs are taken from the
   below-main-sequence CMD locus (the same cut `estimate_mass` uses to exclude
   them); giants/subgiants from over-luminosity above a main-sequence reference
   (`_MS_BPRP`/`_MS_ABSG`, fitted as the per-colour median M_G of this sample);
   everything else is Main sequence. `Unknown` where `abs_g`/`bp_rp` are missing.

There are no true supergiants within the sample volume, so the fallback gates
`Supergiant` on absolute luminosity (M_G < −3.5), not over-luminosity, to avoid
mislabelling ordinary red giants (Arcturus, Aldebaran).

### Note on coordinates

`l`, `b` are computed from the ICRS `ra`/`dec` for every row via astropy, so the
Galactic coordinates and the derived `x_pc/y_pc/z_pc` are consistent across both
catalogues (rather than mixing Gaia's native `l`/`b` with computed Hipparcos
values). For Gaia rows the computed `l`/`b` match the archive's native values to
well within measurement precision.

---

## 3. Key formulas

**Distance** `dist_pc = 1000 / parallax_mas` (parallax in mas).

**Absolute magnitude** `M = m + 5·log10(parallax_mas) − 10`.

**Galactic Cartesian position** (Sun at origin):
`X = d·cos(b)·cos(l)`, `Y = d·cos(b)·sin(l)`, `Z = d·sin(b)`.

**Display brightness from magnitude** (if scaling RGB by luminosity):
`brightness ∝ 10^(−0.4 · g_mag)` (magnitude is logarithmic and inverted).

---

## 4. Photometric transformations

All from the official **Gaia EDR3 documentation, Table 5.7**
(Carrasco & Bellazzini). Each is a polynomial in a colour; outside its validity
range the pipeline returns NaN rather than extrapolating.

| Transform | Purpose | Validity | Typical scatter |
|---|---|---|---|
| `G − V = f(B−V)` | Hipparcos V → Gaia G | −0.4 < B−V < 3.3 | ~0.05 mag |
| `GBP − GRP = f(V−I)` | Hipparcos colour → BP−RP | −0.4 < V−I < 5.0 | ~0.04 mag |
| `G − V = f(BP−RP)` | Gaia → Johnson V (reverse) | −0.5 < BP−RP < 5.0 | ~0.03 mag |

**Colour → temperature (for RGB only):** a monotonic interpolation across the
full BP−RP range, anchored on a Pecaut & Mamajek-style dwarf sequence. The
clean Jordi et al. (2010) polynomial is only valid for BP−RP < 1.5 (Teff ≳
4500 K) and collapses for redder stars, so the interpolation is used instead to
keep M-dwarf colours sensible. These temperatures are **approximate and for
display only** — use `teff_gspphot` for science.

**Temperature → RGB:** Planck blackbody spectrum at the temperature, integrated
against the CIE 1931 colour-matching functions (Wyman, Sloan & Shirley 2013
analytic fit), converted to linear sRGB (D65) and gamma-corrected. Output is the
*hue* at full brightness (normalised so max channel = 1). Verified behaviour:
hot ≈ `#BACDFF` (blue-white), Sun ≈ `#FFF1E9` (near-white), coolest M dwarfs ≈
`#FFB05C` (orange). No star is pure red or pure blue, which is physically correct.

---

## 5. Known limitations and caveats

**Names come from SIMBAD, not the source catalogues.** Gaia and Hipparcos
identify stars only by number; the `simbad_main_id` and `proper_name` columns are
filled by cross-referencing SIMBAD (`ident`/`basic` tables via TAP). Only a few
hundred stars have IAU proper names at all, so `proper_name` is NaN for the
majority. The lookup needs network access and astroquery ≥ 0.4.8; if it fails the
pipeline fills both columns with NaN and continues.

**Bright-star gap.** The very brightest, closest stars saturate in Gaia — they
are the reason Hipparcos is merged in. Ironically the most *famous* nearby stars
are the ones most likely missing from the Gaia rows.

**Radial velocity is sparse.** Most stars lack `radial_velocity`, so `U`, `V`,
`W` are NaN for the majority. The kinematically complete subset is the brighter
Gaia RVS stars.

**Volume sample = mostly M dwarfs.** A nearest-N selection is dominated by red
dwarfs and the main sequence; giants are essentially absent in this small volume.
A few white dwarfs may appear at the lower left of the H-R diagram.

**M-dwarf colours are approximate.** Both the colour→Teff step and the
Johnson↔Gaia transforms are least reliable at red colours (BP−RP > 1.5), exactly
where most stars sit. Fine for visualisation; treat with care for science.

**Photometric system mixing.** Hipparcos rows carry *transformed* G/BP−RP
(population-average relations with scatter), not direct Gaia measurements. The
`phot_origin` column flags this.

**Cross-match scope.** Duplicates are identified against the queried Gaia sample
only. A bright star removed by the `ruwe` filter (rather than truly absent) will
be re-added from Hipparcos — usually desirable for completeness.

**UVW conventions.** Heliocentric, astropy Galactic axes: U toward the Galactic
centre, V toward rotation, W toward the north Galactic pole. Set `to_lsr=True` to
add the solar peculiar motion (Schönrich, Binney & Dehnen 2010: 11.1, 12.24,
7.25 km/s) for LSR-relative velocities.

---

## 6. References

- **Gaia DR3** — Gaia Collaboration et al. (2023); catalogue table `gaiadr3.gaia_source`.
- **Hipparcos** — ESA (1997); archive table `public.hipparcos`.
- **Photometric relations** — Gaia EDR3 documentation §5.5.1, Table 5.7
  (Carrasco & Bellazzini).
- **BP−RP / Teff** — Jordi et al. (2010), *Gaia broad band photometry*.
- **Cool-dwarf colour sequence** — Pecaut & Mamajek (2013).
- **CIE colour-matching fit** — Wyman, Sloan & Shirley (2013).
- **Solar motion** — Schönrich, Binney & Dehnen (2010).
- **Gaia archive (TAP/ADQL)** — https://gea.esac.esa.int/archive/

---

*Generated as documentation for the nearby-star pipeline. Data release: Gaia DR3
(latest as of 2026; DR4 expected December 2026).*

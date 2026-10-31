"""Build the schema-v2 catalogue from a raw fetch (Mapa 1.0, milestone M3; D-020).

Input: a complete raw fetch (`raw.open_fetch`) and the Hipparcos auxiliary tables
(`data/raw/dr3/aux/`). Output: a Parquet dataset (`storage.write_dataset`), one
partition per raw tile. Two passes over the tiles:

1. Hipparcos candidates. A Hipparcos star enters the catalogue only when Gaia has no
   5p/6p counterpart (plan v4 S2 D10). `hipparcos2_best_neighbour` answers that for
   99 524 stars; the rest (no entry, or a 2p neighbour) are epoch-propagated to
   J2016.0 and matched against every tile by position (< 0.5 arcsec, or < 2 arcsec
   with |dG| < 1 mag: the V -> G transform fails for very red stars), so a
   counterpart just across a tile border is still found. Unmatched candidates that
   pass the fetch's own selection (parallax, G) are kept.
2. Rows. Each tile becomes one table: zero-point and corrected parallax
   (`parallax.py`), inversion distances (`distance.py`), positions, display colour,
   mass, UVW and CMD class, plus the Hipparcos rows that fall in that partition.

Every row is kept: quality columns (`ruwe`, `dist_flag`) are stored, never cut on
here; the 1.25 kpc limit is applied at export (M4). The one exception is
`quality_cuts=LEGACY_QUALITY_CUTS`, which reproduces the old pipeline's cuts for the
reference-catalogue comparison (D-013) and is recorded in the manifest's selection.
Memory is one tile at a time.
"""
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from . import distance, parallax, raw, schema, storage
from .astrometry import (add_galactic_xyz, compute_uvw, galactocentric_xyz,
                         galcen_frame_params, propagate_hipparcos)
from .classify import classify_stars, flag_spurious_parallax
from .color import build_rgb_table, teff_from_bprp
from .mass import estimate_mass
from .pipeline import hipparcos_to_common
from .photometry import g_minus_v_from_bprp

HIP_MATCH_ARCSEC = 2.0     # D-020: 1" missed 2 of 40 sampled duplicates
HIP_MAX_DG = 1.0
HIP_SURE_ARCSEC = 0.5      # closer than this it is the same star whatever G says (D-020)
_GAIA_5P6P = (parallax.SOLVED_5P, parallax.SOLVED_6P)
# milkyway.query.query_gaia / query_hipparcos (the legacy pipeline).
LEGACY_QUALITY_CUTS = {"parallax_over_error_min": 10.0, "ruwe_max": 1.4,
                       "hip_plx_over_error_min": 10.0}


def _apply_gaia_cuts(t, cuts):
    """Rows of raw tile `t` passing the legacy cuts (float32 ratio, as archived)."""
    if not cuts:
        return t
    import pyarrow as pa
    plx = t["parallax"].to_numpy(zero_copy_only=False)
    err = t["parallax_error"].to_numpy(zero_copy_only=False).astype(np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        poe = (plx / err).astype(np.float32)
    ruwe = t["ruwe"].to_numpy(zero_copy_only=False).astype(np.float64)
    keep = (poe > cuts["parallax_over_error_min"]) & (ruwe < cuts["ruwe_max"])  # NaN fails
    return t.filter(pa.array(keep))


AUX_FILES = ("hipparcos.parquet", "hip2_best_neighbour.parquet")


def _load_hipparcos(aux_dir):
    """(hipparcos, best_neighbour) DataFrames, after checking both files' SHA-256
    against aux_manifest.json; also returns the {file: sha256} that was checked."""
    aux_dir = Path(aux_dir)
    listed = json.loads((aux_dir / "aux_manifest.json").read_text())["files"]
    hashes = {}
    for name in AUX_FILES:
        hashes[name] = storage._sha256(aux_dir / name)
        if hashes[name] != listed[name]["sha256"]:
            raise ValueError(f"{aux_dir / name}: SHA-256 differs from aux_manifest.json")
    hip = pq.read_table(aux_dir / AUX_FILES[0]).to_pandas()
    nb = pq.read_table(aux_dir / AUX_FILES[1]).to_pandas()
    return hip, nb, hashes


def hipparcos_candidates(hip, nb, selection, cuts=None):
    """(candidates DataFrame, SkyCoord at J2016, counts) for pass 1.

    Candidates: no best_neighbour or a non-5p/6p one, finite astrometry, passing the
    fetch selection on Hipparcos parallax and transformed G. With `cuts` (legacy
    comparison) best_neighbour is ignored: like the old pipeline, every Hipparcos star
    is a candidate and only a Gaia row that survives the cuts can replace it.
    """
    nb_ok = set() if cuts else set(
        nb.loc[nb["astrometric_params_solved"].isin(_GAIA_5P6P), "hip"])
    counts = {"hipparcos_rows": len(hip), "best_neighbour_5p6p": len(nb_ok & set(hip["hip"]))}
    c = hip[~hip["hip"].isin(nb_ok)]
    counts["without_5p6p_neighbour"] = len(c)
    c = c.dropna(subset=["ra", "de", "pmra", "pmde", "plx", "e_plx"])
    counts["with_full_astrometry"] = len(c)
    c = c[c["plx"] > selection["parallax_min_mas"]]
    if cuts:
        c = c[c["plx"] / c["e_plx"] > cuts["hip_plx_over_error_min"]]
    from .photometry import g_minus_v_from_bv
    g = c["vmag"].to_numpy() + g_minus_v_from_bv(c["b_v"].to_numpy())
    if selection.get("g_max") is not None:
        c = c[g < selection["g_max"]]            # NaN G fails: selection untestable
    c = c.reset_index(drop=True)
    counts["passing_selection"] = len(c)
    return c, (propagate_hipparcos(c) if len(c) else None), counts


def match_candidates(fetch_dir, coord, g_hip, radius_arcsec=HIP_MATCH_ARCSEC,
                     max_dg=HIP_MAX_DG, sure_arcsec=HIP_SURE_ARCSEC, cuts=None):
    """Pass 1: nearest Gaia row over all tiles (passing `cuts`) for each candidate.

    Returns (matched bool array, best separation arcsec, |dG| at that neighbour).
    """
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    n = 0 if coord is None else len(coord)
    best_sep = np.full(n, np.inf)
    best_dg = np.full(n, np.nan)
    if n == 0:                                       # coord may be None when empty
        return np.zeros(0, bool), best_sep, best_dg
    manifest = raw.open_fetch(fetch_dir)
    for e in manifest["tiles"]:
        t = _apply_gaia_cuts(pq.read_table(Path(fetch_dir) / e["path"], columns=[
            "ra", "dec", "phot_g_mean_mag", "parallax", "parallax_error", "ruwe"]), cuts)
        if t.num_rows == 0:
            continue
        gc = SkyCoord(ra=t["ra"].to_numpy() * u.deg, dec=t["dec"].to_numpy() * u.deg)
        idx, sep, _ = coord.match_to_catalog_sky(gc)
        sep = sep.arcsec
        better = sep < best_sep
        best_sep[better] = sep[better]
        g_gaia = t["phot_g_mean_mag"].to_numpy(zero_copy_only=False).astype(float)
        best_dg[better] = np.abs(g_gaia[idx[better]] - g_hip[better])
    close = best_sep < radius_arcsec
    matched = (best_sep < sure_arcsec) | (close & ((best_dg < max_dg) | np.isnan(g_hip)))
    return matched, best_sep, best_dg


def _derive(df):
    """Columns computed the same way for Gaia and Hipparcos rows (needs dist_pc)."""
    df = add_galactic_xyz(df)
    df["xgc_pc"], df["ygc_pc"], df["zgc_pc"] = galactocentric_xyz(
        df["ra"].to_numpy(), df["dec"].to_numpy(), df["dist_pc"].to_numpy())
    teff_col = teff_from_bprp(df["bp_rp"].to_numpy())
    df["teff_color"] = teff_col
    df["rgb_r"], df["rgb_g"], df["rgb_b"], df["rgb_hex"] = build_rgb_table(teff_col)
    df["mass_est"] = estimate_mass(df["abs_g"].to_numpy(), df["bp_rp"].to_numpy())
    df["U"], df["V"], df["W"] = compute_uvw(df, to_lsr=False)
    for c in ("simbad_main_id", "proper_name", "sp_type"):
        df[c] = None
    df["star_class"] = classify_stars(df)
    df["spurious_parallax"] = flag_spurious_parallax(df).to_numpy()
    return df


def gaia_rows(t, hip_by_source_id):
    """DataFrame with all catalogue columns from one raw tile (pa.Table)."""
    d = t.to_pandas()
    sid = t["source_id"].to_pylist()                  # Python ints: ids exceed 2**53
    varpi_c, sigma_c, zp, zp_origin = parallax.corrected_parallax(
        d["parallax"], d["parallax_error"], d["phot_g_mean_mag"],
        d["nu_eff_used_in_astrometry"], d["pseudocolour"], d["ecl_lat"],
        d["astrometric_params_solved"])
    r_lo, r_med, r_hi, flag = distance.inversion_distances(varpi_c, sigma_c)
    if np.isnan(r_med).any():
        raise ValueError(f"{int(np.isnan(r_med).sum())} Gaia rows without a distance "
                         f"(corrected parallax <= 0 or no zero-point)")
    g, bprp = d["phot_g_mean_mag"].astype(float), d["bp_rp"].astype(float)
    df = pd.DataFrame({
        "star_id": [schema.GAIA_ID_PREFIX + str(s) for s in sid],
        "source_id": pd.array(sid, dtype="Int64"),
        "hip": pd.array([hip_by_source_id.get(s) for s in sid], dtype="Int64"),
        "healpix": np.array([s >> schema.GAIA_HEALPIX_SHIFT for s in sid], dtype=np.int64),
        "source_catalogue": "Gaia",
        "ra": d["ra"], "dec": d["dec"],
        "parallax_mas": d["parallax"], "parallax_error": d["parallax_error"],
        "parallax_zp_mas": zp, "zp_origin": zp_origin, "ruwe": d["ruwe"],
        "dist_pc": r_med, "r_lo_pc": r_lo, "r_hi_pc": r_hi,
        "dist_origin": distance.DIST_ORIGIN, "dist_flag": flag,
        "pmra": d["pmra"], "pmdec": d["pmdec"], "radial_velocity": d["radial_velocity"],
        "g_mag": g, "bp_rp": bprp, "v_mag": g - g_minus_v_from_bprp(bprp.to_numpy()),
        "abs_g": g + 5 * np.log10(varpi_c) - 10, "phot_origin": "native_gaia",
        "teff_gspphot": d["teff_gspphot"], "mass_flame": np.nan, "age_flame": np.nan,
    })
    return _derive(df)


def hipparcos_rows(cand, coord):
    """DataFrame with all catalogue columns for the kept Hipparcos candidates."""
    import astropy.units as u
    from astropy_healpix import HEALPix
    df = hipparcos_to_common(cand, coord)
    r_lo, r_med, r_hi, flag = distance.inversion_distances(cand["plx"], cand["e_plx"])
    df["dist_pc"], df["r_lo_pc"], df["r_hi_pc"], df["dist_flag"] = r_med, r_lo, r_hi, flag
    df["source_id"] = pd.array([None] * len(df), dtype="Int64")
    df["hip"] = pd.array(cand["hip"].astype(int).tolist(), dtype="Int64")
    hpx = HEALPix(nside=2 ** schema.HEALPIX_LEVEL, order="nested")
    df["healpix"] = hpx.lonlat_to_healpix(df["ra"].to_numpy() * u.deg,
                                          df["dec"].to_numpy() * u.deg).astype(np.int64)
    df["parallax_error"] = cand["e_plx"].to_numpy()
    df["parallax_zp_mas"], df["zp_origin"], df["ruwe"] = np.nan, "none", np.nan
    df["dist_origin"] = distance.DIST_ORIGIN
    return _derive(df)


def build_catalogue(fetch_dir, aux_dir, dataset_dir, *, dataset_id, quality_cuts=None,
                    log=print):
    """Build the catalogue dataset; returns its manifest."""
    t0 = time.time()
    fetch_dir, aux_dir = Path(fetch_dir), Path(aux_dir)
    fm = raw.open_fetch(fetch_dir)
    selection = fm["selection"]

    hip, nb, aux_hashes = _load_hipparcos(aux_dir)
    cand, coord, hip_counts = hipparcos_candidates(hip, nb, selection, quality_cuts)
    from .photometry import g_minus_v_from_bv
    g_hip = cand["vmag"].to_numpy() + g_minus_v_from_bv(cand["b_v"].to_numpy())
    log(f"Hipparcos: {hip_counts['passing_selection']} candidates without a 5p/6p "
        f"best_neighbour; matching against {len(fm['tiles'])} tiles ...")
    matched, sep, dg = match_candidates(fetch_dir, coord, g_hip, cuts=quality_cuts)
    hip_counts.update({
        "matched_by_position": int(matched.sum()),
        "close_but_dg_too_large": int(((sep < HIP_MATCH_ARCSEC) & ~matched).sum()),
        "kept": int((~matched).sum())})
    log(f"  {hip_counts['matched_by_position']} matched by position, "
        f"{hip_counts['kept']} kept as Hipparcos rows "
        f"({hip_counts['close_but_dg_too_large']} within {HIP_MATCH_ARCSEC}\" but |dG| >= {HIP_MAX_DG})")
    keep = ~matched
    if keep.any():
        hip_df = hipparcos_rows(cand[keep].reset_index(drop=True), coord[keep])
        hip_part = schema.partition_of(hip_df["healpix"].to_numpy(), fm["tile_level"])
    else:
        hip_df, hip_part = pd.DataFrame({"hip": pd.array([], dtype="Int64")}), np.zeros(0)

    nb5 = nb[nb["astrometric_params_solved"].isin(_GAIA_5P6P)]
    nb5 = nb5[~nb5["hip"].isin(hip_df["hip"].astype(int))]   # a kept HIP row owns its hip
    hip_by_sid = dict(zip(nb5["source_id"].astype("int64").tolist(),
                          nb5["hip"].astype(int).tolist()))
    zp_counts, flag_counts = {}, {}

    def tables():
        for k, t in raw.read_tiles(fetch_dir):
            df = gaia_rows(_apply_gaia_cuts(t, quality_cuts), hip_by_sid)
            extra = hip_df[hip_part == k]
            if len(extra):
                df = pd.concat([df, extra[df.columns]], ignore_index=True)
            for col, acc in (("zp_origin", zp_counts), ("dist_flag", flag_counts)):
                for v, n in df[col].value_counts().items():
                    acc[v] = acc.get(v, 0) + int(n)
            yield schema.conform(df)
            log(f"  tile {k:3d}: {len(df):7d} rows ({time.time() - t0:.0f} s)")

    provenance = {
        "parallax": parallax.provenance(), "distance": distance.provenance(),
        "frame": galcen_frame_params(),
        "hipparcos": {"match_radius_arcsec": HIP_MATCH_ARCSEC, "max_abs_dg": HIP_MAX_DG,
                      "sure_match_arcsec": HIP_SURE_ARCSEC,
                      "epoch_from": 1991.25, "epoch_to": 2016.0,
                      "catalogue": "public.hipparcos (ESA 1997) + gaiadr3.hipparcos2_best_neighbour",
                      "counts": hip_counts},
        "counts": {"zp_origin": zp_counts, "dist_flag": flag_counts},
    }
    source = {"kind": "raw_fetch", "fetch_id": fm["fetch_id"], "service": fm["service"],
              "fetch_manifest_sha256": storage._sha256(fetch_dir / raw.FETCH_MANIFEST_NAME),
              "aux": aux_hashes}
    n_part = 12 * 4 ** fm["tile_level"]
    manifest = storage.write_dataset(
        tables(), dataset_dir, dataset_id=dataset_id,
        selection={**selection, "quality_cuts": quality_cuts}, source=source,
        level=fm["tile_level"], expected_partitions=range(n_part), provenance=provenance)
    log(f"Wrote {dataset_dir}: {manifest['storage']['total_rows']} rows in "
        f"{time.time() - t0:.0f} s")
    return manifest

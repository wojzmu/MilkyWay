"""Harmonise Gaia + Hipparcos onto one schema and orchestrate the full build.

`build_merged_catalogue()` is the entry point and the best place to understand
the flow: query -> de-duplicate -> harmonise -> derive -> name -> classify.
"""
import numpy as np
import pandas as pd

from .photometry import g_minus_v_from_bv, g_minus_v_from_bprp, bprp_from_vi
from .color import teff_from_bprp, build_rgb_table
from .mass import estimate_mass, apply_min_mass
from .classify import classify_stars, flag_spurious_parallax
from .query import query_gaia, query_hipparcos, add_simbad_names
from .astrometry import (propagate_hipparcos, cross_match, compute_uvw,
                         add_galactic_xyz)


# ===========================================================================
# Harmonise to one Gaia-system table
# ===========================================================================
def gaia_to_common(g):
    return pd.DataFrame({
        "star_id": "Gaia DR3 " + g["source_id"].astype(str),
        "ra": g["ra"], "dec": g["dec"], "parallax_mas": g["parallax"],
        "dist_pc": 1000.0/g["parallax"], "pmra": g["pmra"], "pmdec": g["pmdec"],
        "radial_velocity": g["radial_velocity"],
        "g_mag": g["phot_g_mean_mag"], "bp_rp": g["bp_rp"],
        "v_mag": g["phot_g_mean_mag"] - g_minus_v_from_bprp(g["bp_rp"].to_numpy()),
        "abs_g": g["phot_g_mean_mag"] + 5*np.log10(g["parallax"]) - 10,
        "teff_gspphot": g["teff_gspphot"],
        "mass_flame": g["mass_flame"], "age_flame": g["age_flame"],
        "phot_origin": "native_gaia", "source_catalogue": "Gaia",
    })

def hipparcos_to_common(h, coord):
    plx = h["plx"].to_numpy(); v = h["vmag"].to_numpy()
    g_mag = v + g_minus_v_from_bv(h["b_v"].to_numpy())
    return pd.DataFrame({
        "star_id": "HIP " + h["hip"].astype(int).astype(str),
        "ra": coord.ra.deg, "dec": coord.dec.deg, "parallax_mas": plx,
        "dist_pc": 1000.0/plx, "pmra": h["pmra"].to_numpy(), "pmdec": h["pmde"].to_numpy(),
        "radial_velocity": np.nan,
        "g_mag": g_mag, "bp_rp": bprp_from_vi(h["v_i"].to_numpy()), "v_mag": v,
        "abs_g": g_mag + 5*np.log10(plx) - 10, "teff_gspphot": np.nan,
        "mass_flame": np.nan, "age_flame": np.nan,
        "phot_origin": "transformed_from_johnson", "source_catalogue": "Hipparcos",
    })


def build_merged_catalogue(add_names=True, min_mass=None, max_dist_pc=None):
    # A tighter search volume is a higher parallax floor (parallax[mas] = 1000/dist).
    min_plx = 1000.0 / max_dist_pc if max_dist_pc is not None else None
    if max_dist_pc is not None:
        print(f"Search volume limited to {max_dist_pc} pc (parallax > {min_plx:.3f} mas)")
    print("Querying Gaia ...")
    gaia = query_gaia(min_mass=min_mass, min_parallax_mas=min_plx);  print(f"  {len(gaia)} stars")
    print("Querying Hipparcos ...")
    hip = query_hipparcos(min_parallax_mas=min_plx).dropna(subset=["ra","de","pmra","pmde","plx"]).reset_index(drop=True)
    print(f"  {len(hip)} stars")

    print("Epoch-propagating + cross-matching ...")
    hc = propagate_hipparcos(hip)
    dup = cross_match(gaia, hc)
    print(f"  {int(dup.sum())} duplicates dropped, {len(hip)-int(dup.sum())} gap-fillers added")
    hip_m, hc_m = hip[~dup].reset_index(drop=True), hc[~dup]

    merged = pd.concat([gaia_to_common(gaia), hipparcos_to_common(hip_m, hc_m)],
                       ignore_index=True).sort_values("dist_pc").reset_index(drop=True)

    print("Adding galactic coordinates + 3D position ...")
    merged = add_galactic_xyz(merged)

    print("Assigning display colours ...")
    teff_col = teff_from_bprp(merged["bp_rp"].to_numpy())
    merged["teff_color"] = teff_col
    r, g, b, hexes = build_rgb_table(teff_col)
    merged["rgb_r"], merged["rgb_g"], merged["rgb_b"], merged["rgb_hex"] = r, g, b, hexes

    print("Estimating masses (main-sequence M_G relation) ...")
    merged["mass_est"] = estimate_mass(merged["abs_g"].to_numpy(),
                                       merged["bp_rp"].to_numpy())
    n_mass = int(merged["mass_est"].notna().sum())
    print(f"  {n_mass} of {len(merged)} stars got a mass estimate")

    if min_mass is not None:
        print(f"Applying lower mass cut (>= {min_mass} Msun) ...")
        merged = apply_min_mass(merged, min_mass)

    print("Computing UVW space velocities ...")
    U, V, W = compute_uvw(merged, to_lsr=False)
    merged["U"], merged["V"], merged["W"] = U, V, W

    if add_names:
        print("Resolving names from SIMBAD ...")
        try:
            merged = add_simbad_names(merged)
            n = merged["proper_name"].notna().sum()
            print(f"  {n} stars have a proper name")
        except Exception as e:
            print(f"  SIMBAD step skipped ({e})")
            merged["simbad_main_id"] = pd.NA
            merged["proper_name"] = pd.NA
            merged["sp_type"] = pd.NA

    print("Classifying stars (spectral type + CMD position) ...")
    if "sp_type" not in merged.columns:
        merged["sp_type"] = pd.NA
    merged["star_class"] = classify_stars(merged)
    counts = pd.Series(merged["star_class"]).value_counts()
    print("  " + ", ".join(f"{k}: {v}" for k, v in counts.items()))

    print("Flagging likely spurious parallaxes (crowded-field contamination) ...")
    merged["spurious_parallax"] = flag_spurious_parallax(merged)
    n_spur = int(merged["spurious_parallax"].sum())
    pct = 100*n_spur/len(merged) if len(merged) else 0.0
    print(f"  {n_spur} of {len(merged)} rows flagged spurious_parallax ({pct:.1f}%)")
    return merged

"""Nearby-star pipeline (Gaia DR3 + Hipparcos, within ~MAX_DIST_PC pc).

Builds a merged, de-duplicated catalogue with unified Gaia photometry, a
true-colour RGB per star, estimated masses, UVW space velocities, a coarse
evolutionary classification, and a spurious-parallax quality flag; then renders
figures. Run via `python MilkyWay.py` (see milkyway.cli) or import the pieces:

    from milkyway import build_merged_catalogue, plot_hr, estimate_mass

The astroquery/astropy calls live inside milkyway.query and milkyway.astrometry
and are imported lazily, so the pure math (colour, photometry, mass, classify)
stays importable and testable without network dependencies installed.
"""
from .config import (EPOCH_HIP, EPOCH_GAIA, MAX_DIST_PC, MIN_PARALLAX_MAS,
                     MATCH_RADIUS_ARCSEC, SOLAR_UVW, FAMOUS_STARS, PROJECT_ROOT)
from .photometry import (g_minus_v_from_bv, g_minus_v_from_bprp, bprp_from_vi)
from .color import teff_from_bprp, teff_to_rgb, build_rgb_table
from .mass import estimate_mass, mg_upper_bound_for_mass, apply_min_mass
from .classify import (classify_from_sptype, classify_from_hr, classify_stars,
                       flag_spurious_parallax)
from .query import query_gaia, query_hipparcos, add_simbad_names
from .astrometry import (propagate_hipparcos, cross_match, compute_uvw,
                         add_galactic_xyz)
from .pipeline import (gaia_to_common, hipparcos_to_common,
                       build_merged_catalogue)
from .plots import (plot_hr, plot_map, plot_maps, plot_3d, render_all,
                    _label_famous, _resolve_path, _save)
from .cli import main

__all__ = [
    "EPOCH_HIP", "EPOCH_GAIA", "MAX_DIST_PC", "MIN_PARALLAX_MAS",
    "MATCH_RADIUS_ARCSEC", "SOLAR_UVW", "FAMOUS_STARS", "PROJECT_ROOT",
    "g_minus_v_from_bv", "g_minus_v_from_bprp", "bprp_from_vi",
    "teff_from_bprp", "teff_to_rgb", "build_rgb_table",
    "estimate_mass", "mg_upper_bound_for_mass", "apply_min_mass",
    "classify_from_sptype", "classify_from_hr", "classify_stars",
    "flag_spurious_parallax",
    "query_gaia", "query_hipparcos", "add_simbad_names",
    "propagate_hipparcos", "cross_match", "compute_uvw", "add_galactic_xyz",
    "gaia_to_common", "hipparcos_to_common", "build_merged_catalogue",
    "plot_hr", "plot_map", "plot_maps", "plot_3d", "render_all",
    "main",
]

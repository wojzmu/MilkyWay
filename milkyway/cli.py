"""Command-line entry point: build the catalogue (or load one with --plot-only)
and render the figures."""
import argparse

import pandas as pd

from .config import MAX_DIST_PC
from .mass import apply_min_mass
from .pipeline import build_merged_catalogue
from .plots import _resolve_path, render_all


def main(argv=None):
    parser = argparse.ArgumentParser(description="Nearby-star pipeline and plotter.")
    parser.add_argument("--plot-only", action="store_true",
                        help="skip the Gaia/SIMBAD queries; load an existing CSV "
                             "and only redraw the figures (offline, fast)")
    parser.add_argument("--csv", default=None,
                        help=f"CSV to read (--plot-only) or write. Default is "
                             f"nearby_stars_<dist>pc.csv, where <dist> is --max-dist "
                             f"on a full run, or {MAX_DIST_PC} pc otherwise.")
    parser.add_argument("--min-mass", type=float, default=None, metavar="MSUN",
                        help="keep only stars with an estimated mass >= this many "
                             "solar masses; drops below-threshold and unknown-mass "
                             "stars (default: no cut)")
    parser.add_argument("--max-dist", type=float, default=None, metavar="PC",
                        help=f"limit the search volume to this radius in parsecs "
                             f"(default: {MAX_DIST_PC}). With --plot-only it trims "
                             f"the loaded CSV to stars within this distance.")
    args = parser.parse_args(argv)

    # On a full run the output file is named for the volume actually queried, and
    # for the mass cut when one is set (e.g. nearby_stars_30.0pc_m0.5.csv). On
    # --plot-only we default to reading the standard MAX_DIST_PC catalogue (then
    # optionally trim it), so the defaults don't point us at a file that may not exist.
    if args.plot_only:
        csv_name = args.csv or f"nearby_stars_{MAX_DIST_PC}pc.csv"
    else:
        build_dist = args.max_dist if args.max_dist is not None else MAX_DIST_PC
        mass_suffix = f"_m{args.min_mass}" if args.min_mass is not None else ""
        csv_name = args.csv or f"nearby_stars_{build_dist}pc{mass_suffix}.csv"
    path = _resolve_path(csv_name)

    if args.plot_only:
        print(f"Loading {path} ...")
        cat = pd.read_csv(path)
        print(f"  {len(cat)} stars")
        if args.max_dist is not None:
            cat = cat[cat["dist_pc"] <= args.max_dist].reset_index(drop=True)
            print(f"  {len(cat)} within {args.max_dist} pc")
        cat = apply_min_mass(cat, args.min_mass)
    else:
        cat = build_merged_catalogue(min_mass=args.min_mass,
                                     max_dist_pc=args.max_dist)
        cols = ["star_id","proper_name","dist_pc","bp_rp","abs_g","rgb_hex","source_catalogue"]
        print("\nClosest 10:\n", cat[cols].head(10).to_string(index=False))
        cat.to_csv(path, index=False)
        print(f"\nWrote {path} ({len(cat)} stars)")

    render_all(cat)

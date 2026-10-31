"""Command-line entry point: build the catalogue (or load one with --plot-only)
and render the figures."""
import argparse
import hashlib
import os

import pandas as pd

from .config import MAX_DIST_PC, PROJECT_ROOT
from .mass import apply_min_mass
from .pipeline import build_merged_catalogue
from .plots import _resolve_path, render_all


def _dataset_dir(dir_or_id, data_dir):
    """An existing directory path as given, else `<data_dir>/<id>`."""
    return dir_or_id if os.path.isdir(dir_or_id) else os.path.join(data_dir, dir_or_id)


def _to_parquet(csv_path, dataset_id, data_dir):
    """Convert a legacy catalogue CSV into a Parquet dataset under `data_dir`."""
    from . import csv_io, storage                      # lazy: pyarrow stays optional
    csv_path = os.path.abspath(csv_path)
    dataset_id = dataset_id or os.path.splitext(os.path.basename(csv_path))[0]
    root = os.path.abspath(PROJECT_ROOT)
    try:
        inside = os.path.commonpath([root, csv_path]) == root
    except ValueError:                                 # different drives on Windows
        inside = False
    shown = os.path.relpath(csv_path, root) if inside else csv_path
    with open(csv_path, "rb") as f:
        sha = hashlib.file_digest(f, "sha256").hexdigest()
    table = csv_io.read_catalogue_csv(csv_path)
    out = os.path.join(data_dir, dataset_id)
    manifest = storage.write_dataset(
        [table], out, dataset_id=dataset_id,
        selection={"defined_by": "legacy pipeline (milkyway.query.query_gaia / "
                                 "query_hipparcos)", "g_max": None},
        source={"kind": "legacy_csv", "path": shown.replace(os.sep, "/"), "sha256": sha})
    st = manifest["storage"]
    print(f"Wrote {out}: {len(st['partitions'])} partitions, {st['total_rows']} rows")


def _export_csv(dataset, out_path):
    """Write a dataset as the legacy CSV (dist_pc ascending, like the pipeline)."""
    from . import catalog_query, csv_io
    table = catalog_query.read_table(dataset)
    csv_io.write_catalogue_csv(table, out_path)
    print(f"Wrote {out_path} ({table.num_rows} stars)")


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
    parser.add_argument("--to-parquet", default=None, metavar="CSV",
                        help="convert a legacy catalogue CSV into a Parquet dataset "
                             "under the data dir, then exit")
    parser.add_argument("--dataset-id", default=None, metavar="ID",
                        help="dataset id for --to-parquet (default: the CSV file stem)")
    parser.add_argument("--dataset", default=None, metavar="DIR_OR_ID",
                        help="Parquet dataset (directory, or an id under the data dir) "
                             "to load with --plot-only or export with --export-csv")
    parser.add_argument("--export-csv", default=None, metavar="OUT",
                        help="with --dataset: write the legacy CSV and exit")
    parser.add_argument("--data-dir", default=os.path.join(PROJECT_ROOT, "data"),
                        metavar="DIR", help="where datasets live (default: <project>/data)")
    args = parser.parse_args(argv)

    if args.dataset_id and not args.to_parquet:
        parser.error("--dataset-id requires --to-parquet")
    if args.export_csv and not args.dataset:
        parser.error("--export-csv requires --dataset")
    if args.to_parquet and (args.dataset or args.export_csv or args.plot_only):
        parser.error("--to-parquet cannot be combined with --dataset, --export-csv "
                     "or --plot-only")
    if args.dataset and not (args.plot_only or args.export_csv):
        parser.error("--dataset requires --plot-only or --export-csv")

    if args.to_parquet:
        _to_parquet(args.to_parquet, args.dataset_id, args.data_dir)
        return
    if args.export_csv:
        _export_csv(_dataset_dir(args.dataset, args.data_dir), args.export_csv)
        return

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
        if args.dataset:
            from . import catalog_query
            ds = _dataset_dir(args.dataset, args.data_dir)
            print(f"Loading {ds} ...")
            cat = catalog_query.read_catalogue(ds)
        else:
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

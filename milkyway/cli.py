"""Command-line entry point: build the catalogue (or load one with --plot-only)
and render the figures."""
import argparse
import hashlib
import os
import re

import pandas as pd

from .config import MAX_DIST_PC, PROJECT_ROOT
from .mass import apply_min_mass
from .pipeline import build_merged_catalogue
from .plots import _resolve_path, render_all


_ID_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_RESERVED_IDS = ("reference",)         # data/reference holds the frozen reference CSV


def _id_problem(dataset_id):
    """Why `dataset_id` is not a usable dataset id, or None."""
    if not _ID_RE.match(dataset_id) or dataset_id in (".", ".."):
        return f"invalid dataset id {dataset_id!r} (allowed: letters, digits, '.', '_', '-')"
    if dataset_id in _RESERVED_IDS:
        return f"dataset id {dataset_id!r} is reserved"
    return None


def _is_path(value):
    return os.path.isabs(value) or any(s and s in value for s in (os.sep, os.altsep))


def _dataset_dir(dir_or_id, data_dir):
    """A value with a path separator (or absolute) is a directory as given; a bare id
    is always `<data_dir>/<id>`, whatever the cwd holds."""
    return dir_or_id if _is_path(dir_or_id) else os.path.join(data_dir, dir_or_id)


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
    csv_io.write_catalogue_csv(table, out_path)        # default max_rows guard
    print(f"Wrote {out_path} ({table.num_rows} stars)")


def _fetch(args, tile_ids):
    """Run the raw download; returns the process exit code (1 if any tile failed)."""
    from . import fetch, raw                           # lazy: requests/pyarrow optional
    if args.fetch_aux:
        manifest = fetch.run_aux(data_dir=args.data_dir)
        if manifest.get("already_complete"):
            return 0                                   # run_aux already said so
        for name, e in manifest["files"].items():
            print(f"{name}: {e['rows']} rows ({e['service']})")
        return 0
    try:
        summary = fetch.run_fetch(data_dir=args.data_dir,
                                  fetch_id=args.fetch_id or raw.DEFAULT_FETCH_ID,
                                  tiles=tile_ids, max_jobs=args.max_jobs)
    except raw.TileError as exc:
        print(f"ERROR: existing fetch does not check out: {exc}\n"
              f"Not re-downloading; inspect or delete it, or use a new --fetch-id.")
        return 1
    if summary.get("already_complete"):
        print(f"fetch {summary['fetch_id']} already complete ({summary['rows_total_on_disk']} "
              f"rows); nothing to download. Use a new --fetch-id to fetch again.")
        return 0
    print(f"Fetch {summary['fetch_id']}: {summary['tiles_fetched_now']} fetched now, "
          f"{summary['tiles_done_before']} already done, "
          f"{len(summary['tiles_failed'])} failed of {summary['tiles_planned']}")
    print(f"  {summary['rows_total_on_disk']} rows, {summary['bytes_on_disk'] / 1e6:.1f} MB, "
          f"{summary['elapsed_s']:.0f} s, manifest written: {summary['manifest_written']}")
    for f in summary["tiles_failed"]:
        print(f"  FAILED tile {f['tile']}: {f['error'][:120]}")
    return 1 if summary["tiles_failed"] else 0


def _build(args):
    """Build the schema-v2 catalogue from a complete raw fetch (M3)."""
    from . import build, raw
    fetch_id = args.fetch_id or raw.DEFAULT_FETCH_ID
    raw_dir = os.path.join(args.data_dir, "raw", raw.RELEASE)
    dataset_id = args.dataset_id or f"{fetch_id}_v{_schema_version()}"
    out = os.path.join(args.data_dir, dataset_id)
    build.build_catalogue(os.path.join(raw_dir, fetch_id), os.path.join(raw_dir, "aux"),
                          out, dataset_id=dataset_id)
    return 0


def _schema_version():
    from . import schema
    return schema.SCHEMA_VERSION


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
    parser.add_argument("--fetch", action="store_true",
                        help="download the raw Gaia DR3 tiles (192, resumable) into "
                             "<data-dir>/raw/dr3/<fetch-id>/, then exit")
    parser.add_argument("--fetch-tiles", default=None, metavar="K,K,...",
                        help="pilot: fetch only these level-2 pixels (implies --fetch; "
                             "no manifest is written)")
    parser.add_argument("--fetch-aux", action="store_true",
                        help="download the Hipparcos auxiliary tables into "
                             "<data-dir>/raw/dr3/aux/, then exit")
    parser.add_argument("--fetch-id", default=None, metavar="ID",
                        help="fetch id (default: dr3_g15_p0.5)")
    parser.add_argument("--build", action="store_true",
                        help="build the catalogue dataset from a complete raw fetch "
                             "(--fetch-id) and the Hipparcos aux tables into "
                             "<data-dir>/<dataset-id> (default id: <fetch-id>_v<schema>)")
    parser.add_argument("--max-jobs", type=int, default=2, metavar="N",
                        help="concurrent archive jobs for --fetch, 1..4 (default 2)")
    args = parser.parse_args(argv)

    fetching = args.fetch or args.fetch_aux or args.fetch_tiles is not None
    if args.build:
        if fetching or args.to_parquet or args.dataset or args.plot_only or args.export_csv:
            parser.error("--build cannot be combined with fetching, --to-parquet, "
                         "--dataset, --export-csv or --plot-only")
        for value in (args.fetch_id, args.dataset_id):
            if value is not None and (msg := _id_problem(value)):
                parser.error(msg)
        return _build(args)
    if fetching:
        if args.to_parquet or args.dataset or args.plot_only or args.export_csv:
            parser.error("--fetch/--fetch-tiles/--fetch-aux cannot be combined with "
                         "--to-parquet, --dataset, --export-csv or --plot-only")
        if args.fetch_aux and (args.fetch or args.fetch_tiles is not None):
            parser.error("--fetch-aux cannot be combined with --fetch/--fetch-tiles")
        if not 1 <= args.max_jobs <= 4:
            parser.error("--max-jobs must be between 1 and 4")
        if args.fetch_id is not None and (msg := _id_problem(args.fetch_id)):
            parser.error(msg)
    elif args.fetch_id is not None:
        parser.error("--fetch-id requires --fetch, --fetch-tiles or --fetch-aux")
    tile_ids = None
    if args.fetch_tiles is not None:
        try:
            tile_ids = sorted({int(x) for x in args.fetch_tiles.split(",") if x.strip()})
        except ValueError:
            parser.error("--fetch-tiles expects comma-separated integers")
        if not tile_ids or tile_ids[0] < 0 or tile_ids[-1] > 191:
            parser.error("--fetch-tiles ids must be within 0..191")

    if args.dataset_id and not args.to_parquet:
        parser.error("--dataset-id requires --to-parquet")
    if args.export_csv and not args.dataset:
        parser.error("--export-csv requires --dataset")
    if args.to_parquet and (args.dataset or args.export_csv or args.plot_only):
        parser.error("--to-parquet cannot be combined with --dataset, --export-csv "
                     "or --plot-only")
    if args.dataset and not (args.plot_only or args.export_csv):
        parser.error("--dataset requires --plot-only or --export-csv")

    if args.dataset_id is not None and (msg := _id_problem(args.dataset_id)):
        parser.error(msg)
    if args.to_parquet and args.dataset_id is None:
        stem = os.path.splitext(os.path.basename(args.to_parquet))[0]
        if msg := _id_problem(stem):
            parser.error(f"{msg}; pass --dataset-id")
    if args.dataset and not _is_path(args.dataset) and (msg := _id_problem(args.dataset)):
        parser.error(msg)

    if fetching:
        return _fetch(args, tile_ids)
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

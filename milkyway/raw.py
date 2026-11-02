"""Contract for raw Gaia tiles fetched from the archive (Mapa 1.0, milestone M2).

A fetch downloads `gaiadr3.gaia_source` rows passing the selection, one tile per
NESTED HEALPix pixel at TILE_LEVEL (= the store's partition level), columns 1:1 as
the archive returns them. This module holds everything except the network: column
list and types, the ADQL template, the tile plan, tile verification, atomic tile
writes, and the fetch manifest. The download loop lives in `fetch.py`.

Layout (git-ignored, under data/):

    data/raw/<release>/<fetch_id>/
      tiles/tile_<k>.parquet     # k = level-2 pixel, 3 digits; written verified-only
      fetch_manifest.json        # written last, once every planned tile is present

A tile file exists only after it passed verify_tile(), so "file present" means
"done" and an interrupted fetch resumes by skipping present tiles. The strongest
check is the row count: it must equal the per-pixel COUNT measured for the same
selection on the same service (docs/data/dr3_g15_hpx2_counts.csv, D-011).
"""
import datetime
import json
from collections import namedtuple
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import schema
from .storage import _atomic_write, _fsync, _sha256

RELEASE = "dr3"
TABLE = "gaiadr3.gaia_source"
TILE_LEVEL = schema.PARTITION_LEVEL
FETCH_MANIFEST_NAME = "fetch_manifest.json"
FETCH_MANIFEST_VERSION = 1
DEFAULT_FETCH_ID = "dr3_g15_p0.5"
DEFAULT_SELECTION = {"parallax_min_mas": 0.5, "g_max": 15.0}   # D-008, D-011

# Archive column -> type as returned by AIP's Parquet output (checked 31.10.2026).
# Includes the zero-point inputs M3 needs (nu_eff_used_in_astrometry, pseudocolour,
# ecl_lat, astrometric_params_solved), so M3 never has to re-download.
_d, _f, _i16 = pa.float64(), pa.float32(), pa.int16()
RAW_SCHEMA = pa.schema([
    ("source_id", pa.int64()),
    ("ra", _d), ("dec", _d), ("l", _d), ("b", _d), ("ecl_lat", _d),
    ("parallax", _d), ("parallax_error", _f),
    ("ra_error", _f), ("dec_error", _f),
    ("pmra", _d), ("pmra_error", _f), ("pmdec", _d), ("pmdec_error", _f),
    ("ruwe", _f), ("astrometric_excess_noise", _f), ("ipd_gof_harmonic_amplitude", _f),
    ("nu_eff_used_in_astrometry", _f), ("pseudocolour", _f),
    ("astrometric_params_solved", _i16), ("visibility_periods_used", _i16),
    ("ipd_frac_multi_peak", _i16), ("duplicated_source", pa.bool_()),
    ("phot_g_mean_mag", _f), ("phot_bp_mean_mag", _f), ("phot_rp_mean_mag", _f),
    ("bp_rp", _f), ("phot_bp_rp_excess_factor", _f),
    ("radial_velocity", _f), ("radial_velocity_error", _f),
    ("teff_gspphot", _f), ("distance_gspphot", _f),
    ("distance_gspphot_lower", _f), ("distance_gspphot_upper", _f),
    ("ag_gspphot", _f), ("ebpminrp_gspphot", _f),
])
RAW_COLUMNS = tuple(RAW_SCHEMA.names)

# Only these may appear in WHERE besides the tile's source_id range: quality columns
# (ruwe, parallax_over_error, ...) never select rows at download time (plan v4 S3
# dec. 4); quality cuts are applied later and reversibly.
_SELECTION_KEYS = {"parallax_min_mas": "parallax >", "g_max": "phot_g_mean_mag <"}

Tile = namedtuple("Tile", "k level lo hi expected_rows")


class TileError(ValueError):
    """A downloaded tile violates the contract."""


def tile_range(k, level=TILE_LEVEL):
    """Inclusive source_id range of NESTED pixel k at `level` (source_id >> 35 = hp12)."""
    shift = schema.GAIA_HEALPIX_SHIFT + 2 * (schema.HEALPIX_LEVEL - level)
    return k << shift, ((k + 1) << shift) - 1


def load_counts(path):
    """{pixel: expected rows} from a counts CSV with columns hpx2,n."""
    import pandas as pd
    df = pd.read_csv(path)
    return {int(k): int(n) for k, n in zip(df["hpx2"], df["n"])}


def plan_tiles(counts=None, level=TILE_LEVEL):
    """All 12*4**level tiles in pixel order; expected_rows from `counts` or None.

    With counts, every pixel must be present (a missing one is an error, not 0).
    """
    n_pix = 12 * 4 ** level
    if counts is not None and set(counts) != set(range(n_pix)):
        raise ValueError(f"counts must cover exactly pixels 0..{n_pix - 1}")
    return [Tile(k, level, *tile_range(k, level), None if counts is None else counts[k])
            for k in range(n_pix)]


def _check_selection(selection):
    unknown = set(selection) - set(_SELECTION_KEYS)
    if unknown:
        raise ValueError(f"selection keys not allowed at download time: {sorted(unknown)}")
    return {key: float(v) for key, v in selection.items() if v is not None}


def tile_query(tile, selection=DEFAULT_SELECTION, columns=RAW_COLUMNS):
    """ADQL for one tile. Values are cast to int/float, so nothing is injected."""
    sel = _check_selection(selection)
    bad = [c for c in columns if c not in RAW_SCHEMA.names]
    if bad:
        raise ValueError(f"columns outside RAW_SCHEMA: {bad}")
    where = [f"source_id BETWEEN {int(tile.lo)} AND {int(tile.hi)}"]
    where += [f"{_SELECTION_KEYS[key]} {sel[key]!r}" for key in _SELECTION_KEYS if key in sel]
    return f"SELECT {', '.join(columns)} FROM {TABLE} WHERE " + " AND ".join(where)


def verify_tile(table, tile, selection=DEFAULT_SELECTION):
    """Raise TileError listing every way `table` breaks the contract for `tile`."""
    sel = _check_selection(selection)
    if table.schema.names != list(RAW_COLUMNS) or not all(
            a.type == b.type for a, b in zip(table.schema, RAW_SCHEMA)):
        got = {f.name: str(f.type) for f in table.schema}
        want = {f.name: str(f.type) for f in RAW_SCHEMA}
        raise TileError(f"tile {tile.k}: schema differs: "
                        f"{ {k: (got.get(k), want.get(k)) for k in set(got) | set(want) if got.get(k) != want.get(k)} }")
    problems = []
    if tile.expected_rows is not None and table.num_rows != tile.expected_rows:
        problems.append(f"{table.num_rows} rows, expected {tile.expected_rows}")
    sid = table["source_id"]
    if sid.null_count:
        problems.append(f"{sid.null_count} null source_id")
    elif table.num_rows:
        lo, hi = pc.min_max(sid).values()
        if lo.as_py() < tile.lo or hi.as_py() > tile.hi:
            problems.append(f"source_id outside [{tile.lo}, {tile.hi}]")
        if pc.count_distinct(sid).as_py() != table.num_rows:
            problems.append("duplicate source_id")
    # Re-check the server-side cuts locally. Nulls become NaN and fail the comparison;
    # float32 G is compared against a float32 limit, as the server does.
    if "parallax_min_mas" in sel:
        p = table["parallax"].to_numpy(zero_copy_only=False)
        if not np.all(p > sel["parallax_min_mas"]):
            problems.append("rows with parallax <= parallax_min_mas or null")
    if "g_max" in sel:
        g = table["phot_g_mean_mag"].to_numpy(zero_copy_only=False)
        if not np.all(g < np.float32(sel["g_max"])):
            problems.append("rows with phot_g_mean_mag >= g_max or null")
    if problems:
        raise TileError(f"tile {tile.k}: " + "; ".join(problems))


def tile_path(fetch_dir, k):
    return Path(fetch_dir) / "tiles" / f"tile_{int(k):03d}.parquet"


def write_tile(table, fetch_dir, tile, selection=DEFAULT_SELECTION):
    """Verify, then write atomically (.tmp -> fsync -> rename). Returns the manifest entry."""
    verify_tile(table, tile, selection)
    final = tile_path(fetch_dir, tile.k)
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.with_name(final.name + ".tmp")
    pq.write_table(table.replace_schema_metadata(None), tmp, compression="zstd",
                   compression_level=3)
    _fsync(tmp)
    tmp.replace(final)
    return _entry(fetch_dir, tile, table.num_rows)


def _entry(fetch_dir, tile, rows):
    path = tile_path(fetch_dir, tile.k)
    return {"tile": tile.k, "lo": tile.lo, "hi": tile.hi, "rows": rows,
            "expected_rows": tile.expected_rows,
            "path": path.relative_to(fetch_dir).as_posix(), "sha256": _sha256(path)}


def done_tiles(fetch_dir, tiles):
    """{k: entry} for tiles already on disk whose footer matches the contract.

    Cheap (footer only): schema and row count. A file that fails is deleted so the
    caller re-fetches it. Leftover *.tmp files are removed.
    """
    fetch_dir = Path(fetch_dir)
    for orphan in (fetch_dir / "tiles").glob("*.tmp"):
        orphan.unlink()
    done = {}
    for tile in tiles:
        path = tile_path(fetch_dir, tile.k)
        if not path.exists():
            continue
        with pq.ParquetFile(path) as pf:   # closed before unlink (Windows locks open files)
            rows = pf.metadata.num_rows
            ok = pf.schema_arrow.equals(RAW_SCHEMA, check_metadata=False) and (
                tile.expected_rows is None or rows == tile.expected_rows)
        if ok:
            done[tile.k] = _entry(fetch_dir, tile, rows)
        else:
            path.unlink()
    return done


def finalize_fetch(fetch_dir, tiles, *, fetch_id, selection, service, notes=None):
    """Write fetch_manifest.json once every planned tile is on disk; return it.

    Raises if any tile is missing — a fetch with gaps is never marked complete.
    """
    fetch_dir = Path(fetch_dir)
    done = done_tiles(fetch_dir, tiles)
    missing = [t.k for t in tiles if t.k not in done]
    if missing:
        raise TileError(f"{len(missing)} tiles missing, e.g. {missing[:10]}; "
                        f"no manifest written")
    manifest = {
        "manifest_version": FETCH_MANIFEST_VERSION,
        "fetch_id": fetch_id,
        "status": "complete",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"),
        "release": RELEASE,
        "table": TABLE,
        "service": service,
        "selection": selection,
        "tile_level": tiles[0].level,
        "query_template": tile_query(Tile(0, tiles[0].level, 0, 0, None), selection),
        "columns": list(RAW_COLUMNS),
        "total_rows": sum(e["rows"] for e in done.values()),
        "tiles": [done[t.k] for t in tiles],
        "notes": notes,
    }
    _atomic_write(fetch_dir / FETCH_MANIFEST_NAME, json.dumps(manifest, indent=1).encode())
    return manifest


def open_fetch(fetch_dir, *, verify_hashes=False):
    """Check a fetch is complete and its tiles match the manifest; return the manifest."""
    fetch_dir = Path(fetch_dir)
    path = fetch_dir / FETCH_MANIFEST_NAME
    if not path.exists():
        raise TileError(f"{fetch_dir}: no fetch manifest (fetch incomplete)")
    manifest = json.loads(path.read_text())
    if manifest.get("status") != "complete" or manifest.get("columns") != list(RAW_COLUMNS):
        raise TileError(f"{fetch_dir}: manifest not complete or columns differ from RAW_SCHEMA")
    listed = {e["path"]: e for e in manifest["tiles"]}
    on_disk = {p.relative_to(fetch_dir).as_posix()
               for p in (fetch_dir / "tiles").rglob("*") if p.is_file()}
    if on_disk != set(listed):
        raise TileError(f"{fetch_dir}: tile files differ from manifest "
                        f"(missing {sorted(set(listed) - on_disk)[:5]}, "
                        f"unexpected {sorted(on_disk - set(listed))[:5]})")
    for rel, e in listed.items():
        pf = pq.ParquetFile(fetch_dir / rel)
        if not pf.schema_arrow.equals(RAW_SCHEMA, check_metadata=False) \
                or pf.metadata.num_rows != e["rows"]:
            raise TileError(f"{fetch_dir}/{rel}: schema or row count differs from manifest")
        if verify_hashes and _sha256(fetch_dir / rel) != e["sha256"]:
            raise TileError(f"{fetch_dir}/{rel}: SHA-256 differs from manifest")
    return manifest


def read_tiles(fetch_dir):
    """Yield (k, pa.Table) per tile of a complete fetch, in tile order (for M3)."""
    manifest = open_fetch(fetch_dir)
    for e in manifest["tiles"]:
        yield e["tile"], pq.read_table(Path(fetch_dir) / e["path"], schema=RAW_SCHEMA)

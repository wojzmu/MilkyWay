"""Partitioned Parquet store with a completion manifest (Mapa 1.0, milestone M1).

Layout of one dataset (immutable once its manifest says `complete`, D-004):

    data/<dataset_id>/
      catalog/part_hpx=<k>/part-0.parquet   # k = healpix >> 2*(12 - level)
      manifest.json                         # written last, atomically

Each partition file is sorted by schema.SORT_KEY, split into fixed-size row groups,
zstd-compressed, and written as `.tmp` then renamed, so a crash never leaves a
`*.parquet` holding partial data. The manifest records per-partition row counts
and file SHA-256 (D-016); `open_catalog()` refuses a dataset that is incomplete
or whose files no longer match it.
"""
import datetime
import hashlib
import json
import os
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import schema

MANIFEST_NAME = "manifest.json"
MANIFEST_VERSION = 1
ROW_GROUP_SIZE = 131_072      # 2**17 rows, ~20 MB per group (S1 dec. 5)
COMPRESSION = "zstd"
COMPRESSION_LEVEL = 3


class IncompleteDatasetError(RuntimeError):
    """The dataset has no `complete` manifest or its files disagree with it."""


def partition_path(part_hpx):
    return f"catalog/part_hpx={int(part_hpx)}/part-0.parquet"


def write_dataset(tables, dataset_dir, *, dataset_id, selection, source,
                  level=schema.PARTITION_LEVEL, row_group_size=ROW_GROUP_SIZE,
                  expected_partitions=None, provenance=None, fill_empty=False):
    """Write `tables` (an iterable of schema-conforming pa.Tables) as a dataset.

    Streaming rule: every partition must arrive whole inside a single input table
    (true for one-table inputs and for M2's one-tile-per-level-2-pixel download),
    so memory is bounded by the largest input table. A partition seen twice raises.
    `hip` must be unique across the whole dataset, not just within one table.

    `expected_partitions` (iterable of part_hpx, optional): the partitions the build
    must produce. Any missing or extra one raises before the manifest is written, so
    a download that silently skipped a tile can never be marked complete. It is
    stored in the manifest and re-checked by open_catalog(). `fill_empty=True` writes
    a zero-row file for each expected partition that received no rows instead (for
    callers that guarantee every partition was produced, e.g. one table per raw tile,
    where a strict cut can leave a tile empty).

    `selection` (the cuts that define the sample, e.g. parallax floor and `g_max`,
    None when unset) and `source` (where the rows came from) are stored verbatim in
    the manifest so the dataset can be rebuilt from it. `provenance` (optional dict:
    methods, package versions, frame parameters, build counts) is stored as well.
    Returns the manifest dict.
    """
    root = Path(dataset_dir)
    expected = None if expected_partitions is None else sorted({int(k) for k in expected_partitions})
    if (root / MANIFEST_NAME).exists():
        raise FileExistsError(f"{root} already holds a dataset; build a new dataset_id")
    if (root / "catalog").exists() and any((root / "catalog").rglob("*.parquet")):
        raise FileExistsError(f"{root} holds partition files from an earlier build; "
                              f"remove the directory first")
    root.mkdir(parents=True, exist_ok=True)
    # Only our own leftovers: partition temp files and the manifest temp file.
    for orphan in [*(root / "catalog").glob("*/*.tmp"), root / (MANIFEST_NAME + ".tmp")]:
        orphan.unlink(missing_ok=True)

    partitions, seen_hip = {}, set()
    for table in tables:
        schema.validate(table)
        hips = table["hip"].drop_null().to_pylist()
        dup = seen_hip.intersection(hips)
        if dup:
            raise ValueError(f"hip duplicated across input tables: {sorted(dup)[:10]}")
        seen_hip.update(hips)
        parts = pc.shift_right(table["healpix"], 2 * (schema.HEALPIX_LEVEL - level))
        for k in pc.unique(parts).to_pylist():
            if k in partitions:
                raise ValueError(f"partition {k} split across input tables; each "
                                 f"partition must arrive in one table")
            rows = table.filter(pc.equal(parts, k))
            partitions[k] = _write_partition(root, k, rows, row_group_size)

    if fill_empty and expected is not None:
        empty = schema.CATALOGUE_SCHEMA.empty_table()
        for k in set(expected) - set(partitions):
            partitions[k] = _write_partition(root, k, empty, row_group_size)
    if expected is not None and sorted(partitions) != expected:
        missing = sorted(set(expected) - set(partitions))
        extra = sorted(set(partitions) - set(expected))
        raise ValueError(f"partitions differ from expected_partitions: missing "
                         f"{missing[:10]} ({len(missing)}), unexpected {extra[:10]} "
                         f"({len(extra)}); no manifest written")

    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "dataset_id": dataset_id,
        "status": "complete",
        "created_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(
            timespec="seconds"),
        "schema_version": schema.SCHEMA_VERSION,
        "columns": list(schema.COLUMNS),
        "selection": selection,
        "source": source,
        "provenance": provenance,
        "storage": {
            "healpix_level": schema.HEALPIX_LEVEL,
            "partition_level": level,
            "sort_key": list(schema.SORT_KEY),
            "row_group_size": row_group_size,
            "compression": f"{COMPRESSION}:{COMPRESSION_LEVEL}",
            "expected_partitions": expected,
            "total_rows": sum(p["rows"] for p in partitions.values()),
            "partitions": [partitions[k] for k in sorted(partitions)],
        },
        "software": {"pyarrow": pa.__version__},
    }
    _atomic_write(root / MANIFEST_NAME, json.dumps(manifest, indent=1).encode())
    return manifest


def _write_partition(root, k, rows, row_group_size):
    # Nulls sort last by default; 2-tuples keep this working on older pyarrow.
    order = pc.sort_indices(rows, sort_keys=[(c, "ascending") for c in schema.SORT_KEY])
    rows = rows.take(order)
    rel = partition_path(k)
    final = root / rel
    final.parent.mkdir(parents=True, exist_ok=True)
    tmp = final.with_name(final.name + ".tmp")
    pq.write_table(rows, tmp, row_group_size=row_group_size, compression=COMPRESSION,
                   compression_level=COMPRESSION_LEVEL, write_statistics=True)
    _fsync(tmp)
    os.replace(tmp, final)
    return {"part_hpx": int(k), "path": rel, "rows": rows.num_rows,
            "sha256": _sha256(final)}


def open_catalog(dataset_dir, *, allow_incomplete=False, verify_hashes=False):
    """Check a dataset is complete and intact; return its manifest.

    Cheap by default (reads only footers): the manifest's schema version and columns
    match this code; every file under `catalog/` is listed in the manifest and vice
    versa; each file's Arrow schema equals CATALOGUE_SCHEMA and its row count the
    recorded one; recorded `expected_partitions` are all present. `verify_hashes=True`
    also re-hashes every file (reads all bytes). `allow_incomplete=True` skips the
    checks for a dataset without a `complete` manifest and returns it (or None).
    Readers must read exactly `manifest["storage"]["partitions"][*]["path"]`.
    """
    root = Path(dataset_dir)
    path = root / MANIFEST_NAME
    manifest = json.loads(path.read_text()) if path.exists() else None
    if manifest is None or manifest.get("status") != "complete":
        if allow_incomplete:
            import warnings
            warnings.warn(f"{root}: dataset is not complete; reading it anyway")
            return manifest
        raise IncompleteDatasetError(f"{root}: no complete manifest")

    if manifest.get("schema_version") != schema.SCHEMA_VERSION:
        raise IncompleteDatasetError(
            f"{root}: schema version {manifest.get('schema_version')}, this code reads "
            f"{schema.SCHEMA_VERSION}; rebuild or migrate the dataset")
    if manifest.get("columns") != list(schema.COLUMNS):
        raise IncompleteDatasetError(f"{root}: manifest columns differ from the schema")

    st = manifest["storage"]
    listed = {p["path"]: p for p in st["partitions"]}
    on_disk = {p.relative_to(root).as_posix()
               for p in (root / "catalog").rglob("*") if p.is_file()}
    if on_disk != set(listed):
        raise IncompleteDatasetError(
            f"{root}: files differ from manifest (missing {sorted(set(listed) - on_disk)[:5]}, "
            f"unexpected {sorted(on_disk - set(listed))[:5]})")
    expected = st.get("expected_partitions")
    if expected is not None and sorted(p["part_hpx"] for p in st["partitions"]) != expected:
        raise IncompleteDatasetError(f"{root}: partitions differ from expected_partitions")
    for rel, entry in listed.items():
        pf = pq.ParquetFile(root / rel)
        if not pf.schema_arrow.equals(schema.CATALOGUE_SCHEMA, check_metadata=False):
            raise IncompleteDatasetError(f"{root}/{rel}: file schema differs from CATALOGUE_SCHEMA")
        n = pf.metadata.num_rows
        if n != entry["rows"]:
            raise IncompleteDatasetError(f"{root}/{rel}: {n} rows, manifest says {entry['rows']}")
        if verify_hashes and _sha256(root / rel) != entry["sha256"]:
            raise IncompleteDatasetError(f"{root}/{rel}: SHA-256 differs from manifest")
    return manifest


def _sha256(path, chunk=1 << 20):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while block := f.read(chunk):
            h.update(block)
    return h.hexdigest()


def _fsync(path):
    with open(path, "rb+") as f:
        os.fsync(f.fileno())


def _atomic_write(path, data):
    tmp = Path(str(path) + ".tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)

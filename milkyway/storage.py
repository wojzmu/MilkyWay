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
                  level=schema.PARTITION_LEVEL, row_group_size=ROW_GROUP_SIZE):
    """Write `tables` (an iterable of schema-conforming pa.Tables) as a dataset.

    Streaming rule: every partition must arrive whole inside a single input table
    (true for one-table inputs and for M2's one-tile-per-level-2-pixel download),
    so memory is bounded by the largest input table. A partition seen twice raises.

    `selection` (the cuts that define the sample, e.g. parallax floor and `g_max`,
    None when unset) and `source` (where the rows came from) are stored verbatim in
    the manifest so the dataset can be rebuilt from it. Returns the manifest dict.
    """
    root = Path(dataset_dir)
    if (root / MANIFEST_NAME).exists():
        raise FileExistsError(f"{root} already holds a dataset; build a new dataset_id")
    if root.exists() and any(p for p in root.rglob("*.parquet")):
        raise FileExistsError(f"{root} holds partition files from an earlier build; "
                              f"remove the directory first")
    root.mkdir(parents=True, exist_ok=True)
    for orphan in root.rglob("*.tmp"):
        orphan.unlink()

    partitions = {}
    for table in tables:
        schema.validate(table)
        parts = pc.shift_right(table["healpix"], 2 * (schema.HEALPIX_LEVEL - level))
        for k in pc.unique(parts).to_pylist():
            if k in partitions:
                raise ValueError(f"partition {k} split across input tables; each "
                                 f"partition must arrive in one table")
            rows = table.filter(pc.equal(parts, k))
            partitions[k] = _write_partition(root, k, rows, row_group_size)

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
        "storage": {
            "healpix_level": schema.HEALPIX_LEVEL,
            "partition_level": level,
            "sort_key": list(schema.SORT_KEY),
            "row_group_size": row_group_size,
            "compression": f"{COMPRESSION}:{COMPRESSION_LEVEL}",
            "total_rows": sum(p["rows"] for p in partitions.values()),
            "partitions": [partitions[k] for k in sorted(partitions)],
        },
        "software": {"pyarrow": pa.__version__},
    }
    _atomic_write(root / MANIFEST_NAME, json.dumps(manifest, indent=1).encode())
    return manifest


def _write_partition(root, k, rows, row_group_size):
    order = pc.sort_indices(rows, sort_keys=[(c, "ascending", "at_end")
                                             for c in schema.SORT_KEY])
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

    Cheap by default: compares the partition files on disk with the manifest's list
    and each file's footer row count with the recorded one. `verify_hashes=True`
    also re-hashes every file (reads all bytes). `allow_incomplete=True` skips the
    checks for a dataset without a `complete` manifest and returns None for it.
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

    listed = {p["path"]: p for p in manifest["storage"]["partitions"]}
    on_disk = {p.relative_to(root).as_posix() for p in root.glob("catalog/*/*.parquet")}
    if on_disk != set(listed):
        raise IncompleteDatasetError(
            f"{root}: files differ from manifest (missing {sorted(set(listed) - on_disk)[:5]}, "
            f"unexpected {sorted(on_disk - set(listed))[:5]})")
    for rel, entry in listed.items():
        n = pq.ParquetFile(root / rel).metadata.num_rows
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

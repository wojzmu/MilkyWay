"""Read side of the Parquet catalogue: DuckDB views and pandas/Arrow loaders.

`connect()` exposes a dataset as the SQL view `catalog` (all schema columns plus the
hive partition key `part_hpx`). Every entry point first runs `storage.open_catalog`,
so incomplete or tampered datasets are refused. duckdb is imported at module level;
this module is not re-exported from the package root.
"""
from pathlib import Path

import duckdb
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import schema, storage

# Nullable ints must not degrade to float64 (Gaia source_ids exceed 2**53).
_INT_DTYPES = {pa.int64(): pd.Int64Dtype(), pa.int32(): pd.Int64Dtype()}


def _partition_files(dataset_dir, manifest):
    """Absolute paths of exactly the files the manifest lists (never a glob)."""
    root = Path(dataset_dir).resolve()
    return [(root / p["path"]).as_posix() for p in manifest["storage"]["partitions"]]


def connect(dataset_dir, *, verify_hashes=False):
    """Open an in-memory DuckDB connection with a `catalog` view over the dataset."""
    manifest = storage.open_catalog(dataset_dir, verify_hashes=verify_hashes)
    # DDL cannot be parameterised: the manifest's file list goes in as SQL string
    # literals (quotes doubled). An explicit list, not a glob, so stray files and
    # glob characters in the path ('[', '*') cannot change what is read.
    files = ", ".join("'" + f.replace("'", "''") + "'"
                      for f in _partition_files(dataset_dir, manifest))
    con = duckdb.connect(":memory:")
    con.execute(
        f"CREATE VIEW catalog AS SELECT * FROM read_parquet([{files}], "
        "hive_partitioning = true, hive_types = {'part_hpx': INTEGER})")
    level = int(manifest["storage"]["partition_level"])
    con.execute("CREATE TABLE catalog_meta AS SELECT ?::INTEGER AS partition_level", [level])
    return con


def read_table(dataset_dir, columns=None, *, verify_hashes=False):
    """All rows of a dataset as a `pa.Table`, sorted by dist_pc ascending."""
    manifest = storage.open_catalog(dataset_dir, verify_hashes=verify_hashes)
    table = pq.read_table(_partition_files(dataset_dir, manifest),
                          schema=schema.CATALOGUE_SCHEMA, columns=columns)
    if "dist_pc" in table.column_names:
        table = table.take(pc.sort_indices(table, sort_keys=[("dist_pc", "ascending")]))
    return table


def read_catalogue(dataset_dir, columns=None):
    """All rows as a DataFrame sorted by dist_pc (legacy CSV order), 0..n-1 index."""
    df = read_table(dataset_dir, columns).to_pandas(types_mapper=_INT_DTYPES.get)
    return df.reset_index(drop=True)


def _check_int(value, name):
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an int, got {value!r}")
    return value


def sky_slice(con, pixel, level, columns="*"):
    """Rows whose NESTED HEALPix pixel at `level` (0..12) is `pixel`, as a DataFrame.

    Always adds a `part_hpx` predicate so DuckDB skips the other partition files.
    `columns` is SQL text chosen by the caller, not user data.
    """
    pixel, level = _check_int(pixel, "pixel"), _check_int(level, "level")
    if not 0 <= level <= schema.HEALPIX_LEVEL:
        raise ValueError(f"level must be 0..{schema.HEALPIX_LEVEL}")
    if not 0 <= pixel < 12 * 4 ** level:
        raise ValueError(f"pixel {pixel} out of range for level {level}")
    p = con.execute("SELECT partition_level FROM catalog_meta").fetchone()[0]
    shift = 2 * (schema.HEALPIX_LEVEL - level)
    lo, hi = pixel << shift, ((pixel + 1) << shift) - 1
    if level >= p:
        part_lo = part_hi = pixel >> (2 * (level - p))
    else:
        part_lo, part_hi = pixel << (2 * (p - level)), ((pixel + 1) << (2 * (p - level))) - 1
    return con.execute(
        f"SELECT {columns} FROM catalog WHERE part_hpx BETWEEN ? AND ? "
        "AND healpix BETWEEN ? AND ?", [part_lo, part_hi, lo, hi]).df()


def within_distance(con, max_dist_pc, columns="*"):
    """Rows with dist_pc <= max_dist_pc, as a DataFrame."""
    return con.execute(f"SELECT {columns} FROM catalog WHERE dist_pc <= ?",
                       [float(max_dist_pc)]).df()


def z_histogram(con, *, bin_pc=50.0, max_dist_pc=None):
    """Star counts per z_pc bin: DataFrame[z_lo, n], bins floor(z / bin) * bin."""
    where, params = "", [float(bin_pc), float(bin_pc)]
    if max_dist_pc is not None:
        where, params = "WHERE dist_pc <= ?", params + [float(max_dist_pc)]
    return con.execute(
        f"SELECT floor(z_pc / ?) * ? AS z_lo, count(*) AS n FROM catalog {where} "
        "GROUP BY z_lo ORDER BY z_lo", params).df()

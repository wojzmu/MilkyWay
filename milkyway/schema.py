"""Column contract of the Parquet catalogue (Mapa 1.0, milestone M1).

One `pyarrow.Schema` is the single source of truth for column names, types and
nullability; the store (`storage.py`), the CSV adapter and the tests all read it
from here. It is the M1 subset of plan v4's schema v2 (docs/plan-v4/S1, dec. 8):
today's catalogue columns plus the identifiers `source_id`, `hip` and `healpix`.
M2 (download) and M3 (distances) add columns and bump `SCHEMA_VERSION`.

Deliberate departures from plan v4 (see docs/DECISIONS.md):
- `star_id` keeps the current pipeline format, "Gaia DR3 <source_id>" /
  "HIP <hip>", not v4's "gdr3:<id>" (D-015);
- `dist_pc` is a stored column until M3 introduces `r_med_pc` (D-015).

pyarrow is imported at module level; this module is not re-exported from the
package root, so `MilkyWay.py` and the colour/photometry math still run without it.
"""
import numpy as np
import pyarrow as pa

SCHEMA_VERSION = 1
SCHEMA_METADATA_KEY = b"milkyway.schema_version"

# star_id prefixes. The Gaia prefix names the data release on purpose: source_ids
# are not guaranteed stable across releases, so ids from two releases never mix (D-002).
GAIA_ID_PREFIX = "Gaia DR3 "
HIP_ID_PREFIX = "HIP "

# HEALPix: `healpix` is NESTED at level 12. For Gaia rows it is source_id >> 35 by
# construction of the Gaia source_id; Hipparcos-only rows get it from (ra, dec).
HEALPIX_LEVEL = 12
GAIA_HEALPIX_SHIFT = 35
PARTITION_LEVEL = 2          # D-011: max 462 780 rows per level-2 pixel at G < 15

# In-file sort order (S1 dec. 3). Gaia rows: healpix is a prefix of source_id, so
# this equals sorting by source_id; Hipparcos-only rows (null source_id) slot in
# by sky position and are ordered among themselves by hip.
SORT_KEY = ("healpix", "source_id", "hip")

ENUMS = {
    "source_catalogue": ("Gaia", "Hipparcos"),
    "phot_origin": ("native_gaia", "transformed_from_johnson"),
    # Labels produced by classify.classify_stars().
    "star_class": ("Main sequence", "White dwarf", "Subgiant", "Giant",
                   "Red giant", "Supergiant", "Subdwarf", "Brown dwarf", "Unknown"),
}

_f64, _f32, _str = pa.float64(), pa.float32(), pa.string()

# (name, type, nullable). float64 only for geometry that feeds later astrometry
# (S1 dec. 8); everything else numeric is float32.
_FIELDS = [
    # identification
    ("star_id",           _str,         False),
    ("source_id",         pa.int64(),   True),   # null for Hipparcos-only rows
    ("hip",               pa.int32(),   True),   # null for Gaia rows (until M2 cross-ids)
    ("healpix",           pa.int64(),   False),
    ("source_catalogue",  _str,         False),
    # astrometry
    ("ra",                _f64,         False),
    ("dec",               _f64,         False),
    ("parallax_mas",      _f64,         False),
    ("dist_pc",           _f32,         False),
    ("pmra",              _f32,         True),
    ("pmdec",             _f32,         True),
    ("radial_velocity",   _f32,         True),
    # photometry
    ("g_mag",             _f32,         True),
    ("bp_rp",             _f32,         True),
    ("v_mag",             _f32,         True),
    ("abs_g",             _f32,         True),
    ("phot_origin",       _str,         False),
    # Gaia astrophysical parameters
    ("teff_gspphot",      _f32,         True),
    ("mass_flame",        _f32,         True),
    ("age_flame",         _f32,         True),
    # position
    ("l",                 _f64,         False),
    ("b",                 _f64,         False),
    ("x_pc",              _f32,         False),
    ("y_pc",              _f32,         False),
    ("z_pc",              _f32,         False),
    # display colour (teff_color is display-only, never science)
    ("teff_color",        _f32,         True),
    ("rgb_r",             pa.uint8(),   True),
    ("rgb_g",             pa.uint8(),   True),
    ("rgb_b",             pa.uint8(),   True),
    ("rgb_hex",           _str,         True),
    # derived
    ("mass_est",          _f32,         True),
    ("U",                 _f32,         True),
    ("V",                 _f32,         True),
    ("W",                 _f32,         True),
    # names and classification
    ("simbad_main_id",    _str,         True),
    ("proper_name",       _str,         True),
    ("sp_type",           _str,         True),
    ("star_class",        _str,         False),
    ("spurious_parallax", pa.bool_(),   False),
]

CATALOGUE_SCHEMA = pa.schema(
    [pa.field(name, typ, nullable=nullable) for name, typ, nullable in _FIELDS],
    metadata={SCHEMA_METADATA_KEY: str(SCHEMA_VERSION).encode()},
)
COLUMNS = tuple(CATALOGUE_SCHEMA.names)


class SchemaError(ValueError):
    """A table does not satisfy the catalogue contract."""


def partition_of(healpix, level=PARTITION_LEVEL):
    """Partition key (`part_hpx`) of level-12 NESTED pixel(s) at `level`."""
    return np.asarray(healpix, dtype=np.int64) >> (2 * (HEALPIX_LEVEL - level))


def conform(df):
    """Build a `pa.Table` in CATALOGUE_SCHEMA from a DataFrame holding its columns.

    Column order follows the schema; extra DataFrame columns are dropped. Values are
    cast to the schema types (float64 -> float32 rounds to nearest; ints must fit).
    Raises SchemaError on missing columns. Does not validate content — see validate().
    """
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing:
        raise SchemaError(f"missing columns: {missing}")
    arrays = []
    for field in CATALOGUE_SCHEMA:
        arr = pa.array(df[field.name], from_pandas=True)
        try:
            arrays.append(arr.cast(field.type, safe=not pa.types.is_floating(field.type)))
        except (pa.ArrowInvalid, pa.ArrowNotImplementedError) as e:
            raise SchemaError(f"column {field.name!r}: cannot cast {arr.type} "
                              f"to {field.type}: {e}") from e
    return pa.Table.from_arrays(arrays, schema=CATALOGUE_SCHEMA)


def validate(table):
    """Check a table against the contract; raise SchemaError listing every problem.

    Checks: exact schema (names, order, types); no nulls (or NaN) in non-nullable
    fields; enum membership; unique star_id/source_id/hip; star_id agrees with
    source_id/hip and source_catalogue; healpix == source_id >> 35 for Gaia rows.
    """
    import pyarrow.compute as pc

    if not table.schema.equals(CATALOGUE_SCHEMA, check_metadata=False):
        got = {f.name: str(f.type) for f in table.schema}
        want = {f.name: str(f.type) for f in CATALOGUE_SCHEMA}
        diff = {k: (got.get(k), want.get(k)) for k in set(got) | set(want)
                if got.get(k) != want.get(k)}
        order = "" if diff else " (column order differs)"
        raise SchemaError(f"schema mismatch{order}: {diff}")

    problems = []
    for field in CATALOGUE_SCHEMA:
        col = table[field.name]
        if not field.nullable:
            n_bad = col.null_count
            if pa.types.is_floating(field.type):
                n_bad += pc.sum(pc.is_nan(col)).as_py() or 0
            if n_bad:
                problems.append(f"{field.name}: {n_bad} null/NaN in non-nullable column")
        if field.name in ENUMS:
            bad = pc.filter(col, pc.invert(pc.is_in(col, pa.array(ENUMS[field.name]))))
            if len(bad):
                problems.append(f"{field.name}: values outside enum "
                                f"{sorted(set(bad.drop_null().to_pylist()))[:5]}")

    for name in ("star_id", "source_id", "hip"):
        col = table[name].drop_null()
        n_dup = len(col) - pc.count_distinct(col).as_py()
        if n_dup:
            problems.append(f"{name}: {n_dup} duplicate values")

    is_gaia = pc.equal(table["source_catalogue"], "Gaia")
    gaia, hip = table.filter(is_gaia), table.filter(pc.invert(is_gaia))
    if gaia["source_id"].null_count:
        problems.append(f"source_id: {gaia['source_id'].null_count} Gaia rows without it")
    if hip["source_id"].null_count != len(hip) or hip["hip"].null_count:
        problems.append("Hipparcos rows must have hip and no source_id")
    want_gaia_id = pc.binary_join_element_wise(
        GAIA_ID_PREFIX, pc.cast(gaia["source_id"], _str), "")
    if not pc.all(pc.equal(gaia["star_id"], want_gaia_id)).as_py() and len(gaia):
        problems.append("star_id does not match 'Gaia DR3 <source_id>' on some Gaia rows")
    want_hip_id = pc.binary_join_element_wise(HIP_ID_PREFIX, pc.cast(hip["hip"], _str), "")
    if len(hip) and not pc.all(pc.equal(hip["star_id"], want_hip_id)).as_py():
        problems.append("star_id does not match 'HIP <hip>' on some Hipparcos rows")
    if len(gaia):
        hpx = pc.shift_right(gaia["source_id"], GAIA_HEALPIX_SHIFT)
        if not pc.all(pc.equal(gaia["healpix"], hpx)).as_py():
            problems.append("healpix != source_id >> 35 on some Gaia rows")

    if problems:
        raise SchemaError("; ".join(problems))

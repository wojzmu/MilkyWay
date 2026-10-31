"""CSV <-> Arrow adapter for the legacy 36-column catalogue CSV (web viewer format).

`read_catalogue_csv` derives `source_id`, `hip` and `healpix` from `star_id`/(ra, dec)
and returns a validated `pa.Table`; `write_catalogue_csv` is the inverse. Gaia
source_ids exceed 2**53, so they are only ever handled as Python ints / int64.
"""
import csv

import numpy as np
import pandas as pd
import pyarrow as pa

from . import schema

LEGACY_CSV_COLUMNS = (
    "star_id", "ra", "dec", "parallax_mas", "dist_pc", "pmra", "pmdec",
    "radial_velocity", "g_mag", "bp_rp", "v_mag", "abs_g", "teff_gspphot",
    "mass_flame", "age_flame", "phot_origin", "source_catalogue", "l", "b",
    "x_pc", "y_pc", "z_pc", "teff_color", "rgb_r", "rgb_g", "rgb_b", "rgb_hex",
    "mass_est", "U", "V", "W", "simbad_main_id", "proper_name", "sp_type",
    "star_class", "spurious_parallax",
)

_STR_COLS = [f.name for f in schema.CATALOGUE_SCHEMA if f.type == pa.string()]
_RGB_COLS = ("rgb_r", "rgb_g", "rgb_b")


def _derive_ids(df):
    """(source_id, hip, healpix) arrays from star_id and ra/dec."""
    gp, hp = schema.GAIA_ID_PREFIX, schema.HIP_ID_PREFIX
    ids = df["star_id"].tolist()
    n = len(ids)
    source_id, hip = [None] * n, [None] * n
    healpix = np.zeros(n, dtype=np.int64)
    hip_rows, bad = [], []
    for i, sid in enumerate(ids):
        num = sid[len(gp):] if isinstance(sid, str) and sid.startswith(gp) else None
        if num is not None and num.isascii() and num.isdigit():
            source_id[i] = int(num)
            healpix[i] = source_id[i] >> schema.GAIA_HEALPIX_SHIFT
            continue
        num = sid[len(hp):] if isinstance(sid, str) and sid.startswith(hp) else None
        if num is not None and num.isascii() and num.isdigit():
            hip[i] = int(num)
            hip_rows.append(i)
        else:
            bad.append(sid)
    if bad:
        raise ValueError(f"star_id matches neither {gp!r} nor {hp!r}: {bad[:10]}"
                         + (f" (+{len(bad) - 10} more)" if len(bad) > 10 else ""))
    if hip_rows:
        import astropy.units as u                      # lazy: astropy convention
        from astropy_healpix import HEALPix
        hpx = HEALPix(nside=2 ** schema.HEALPIX_LEVEL, order="nested")
        idx = np.asarray(hip_rows)
        healpix[idx] = hpx.lonlat_to_healpix(df["ra"].to_numpy()[idx] * u.deg,
                                             df["dec"].to_numpy()[idx] * u.deg)
    return (pd.array(source_id, dtype="Int64"), pd.array(hip, dtype="Int64"), healpix)


def read_catalogue_csv(path):
    """Read a legacy catalogue CSV into a validated `pa.Table` (CATALOGUE_SCHEMA)."""
    dtypes = {c: str for c in _STR_COLS if c in LEGACY_CSV_COLUMNS}
    dtypes.update({c: "Int64" for c in _RGB_COLS})
    # Only "" is NA: strings like "NA" or "None" in name columns are real values.
    df = pd.read_csv(path, dtype=dtypes, keep_default_na=False, na_values=[""],
                     float_precision="round_trip")
    df["source_id"], df["hip"], df["healpix"] = _derive_ids(df)
    table = schema.conform(df)
    schema.validate(table)
    return table


def _format_column(col, typ):
    """Strings for one Arrow column; nulls (and NaN) become empty fields."""
    vals = col.to_numpy(zero_copy_only=False) if pa.types.is_floating(typ) else None
    if pa.types.is_float32(typ):
        return ["" if np.isnan(v) else str(np.float32(v)) for v in vals]
    if pa.types.is_float64(typ):
        return ["" if np.isnan(v) else repr(float(v)) for v in vals]
    if pa.types.is_boolean(typ):
        return ["" if v is None else ("True" if v else "False") for v in col.to_pylist()]
    return ["" if v is None else str(v) for v in col.to_pylist()]


def write_catalogue_csv(table, path):
    """Write `table` as a legacy catalogue CSV (drops source_id/hip/healpix)."""
    cols = [_format_column(table[c].combine_chunks(), table.schema.field(c).type)
            for c in LEGACY_CSV_COLUMNS]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(LEGACY_CSV_COLUMNS)
        w.writerows(zip(*cols))

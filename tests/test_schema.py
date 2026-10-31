"""validate()/conform(): one negative test per check, starting from a valid table."""
import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

from milkyway import csv_io, schema
from milkyway.schema import SchemaError


@pytest.fixture
def valid(sample_csv_path):
    return csv_io.read_catalogue_csv(sample_csv_path)


def _rows(t, cat):
    return [i for i, c in enumerate(t["source_catalogue"].to_pylist()) if c == cat]


def _set(t, name, mutate):
    """Copy of `t` with column `name` replaced by mutate(list_of_values)."""
    i = t.schema.get_field_index(name)
    vals = mutate(t[name].to_pylist())
    return t.set_column(i, t.schema.field(i), pa.array(vals, type=t.schema.field(i).type))


def _put(t, name, idx, value):
    def f(v):
        v[idx] = value
        return v
    return _set(t, name, f)


def _fails(t, match):
    with pytest.raises(SchemaError, match=match):
        schema.validate(t)


def test_valid_fixture(valid):
    schema.validate(valid)


def test_wrong_type(valid):
    i = valid.schema.get_field_index("dist_pc")
    t = valid.set_column(i, "dist_pc", valid["dist_pc"].cast(pa.float64()))
    _fails(t, "schema mismatch")


def test_missing_column(valid):
    _fails(valid.drop_columns(["mass_est"]), "schema mismatch")


def test_column_order(valid):
    names = list(valid.column_names)
    names[0], names[1] = names[1], names[0]
    _fails(valid.select(names), "column order differs")


def test_null_in_non_nullable(valid):
    _fails(_put(valid, "star_class", 0, None), "null/NaN in non-nullable")


def test_nan_in_non_nullable_float(valid):
    _fails(_put(valid, "ra", 0, float("nan")), "null/NaN in non-nullable")


def test_inf_in_nullable_float(valid):
    _fails(_put(valid, "pmra", 0, float("inf")), "infinite")


def test_float32_overflow_becomes_inf(valid, sample_csv_path):
    df = pd.read_csv(sample_csv_path, dtype={"star_id": str}, keep_default_na=False,
                     na_values=[""])
    df["source_id"], df["hip"], df["healpix"] = csv_io._derive_ids(df)
    df["pmra"] = df["pmra"].astype("float64")
    df.loc[0, "pmra"] = 1e40
    _fails(schema.conform(df), "pmra: .*infinite")


def test_enum_violation(valid):
    _fails(_put(valid, "phot_origin", 0, "bogus"), "outside enum")


def test_duplicate_star_id(valid):
    _fails(_put(valid, "star_id", 1, valid["star_id"][0].as_py()), "star_id: 1 duplicate")


def test_duplicate_source_id(valid):
    g = _rows(valid, "Gaia")
    _fails(_put(valid, "source_id", g[1], valid["source_id"][g[0]].as_py()),
           "source_id: 1 duplicate")


def test_duplicate_hip(valid):
    h = _rows(valid, "Hipparcos")
    _fails(_put(valid, "hip", h[1], valid["hip"][h[0]].as_py()), "hip: 1 duplicate")


def test_gaia_without_source_id(valid):
    _fails(_put(valid, "source_id", _rows(valid, "Gaia")[0], None), "Gaia rows without it")


def test_hipparcos_with_source_id(valid):
    _fails(_put(valid, "source_id", _rows(valid, "Hipparcos")[0], 12345),
           "Hipparcos rows must have")


def test_gaia_star_id_mismatch(valid):
    _fails(_put(valid, "star_id", _rows(valid, "Gaia")[0], "Gaia DR3 1"),
           "'Gaia DR3 <source_id>'")


def test_hip_star_id_mismatch(valid):
    _fails(_put(valid, "star_id", _rows(valid, "Hipparcos")[0], "HIP 999999999"),
           "'HIP <hip>'")


def test_gaia_healpix_mismatch(valid):
    i = _rows(valid, "Gaia")[0]
    _fails(_put(valid, "healpix", i, valid["healpix"][i].as_py() ^ 1), "source_id >> 35")


def test_healpix_negative(valid):
    _fails(_put(valid, "healpix", _rows(valid, "Hipparcos")[0], -1), "healpix outside")


def test_healpix_too_large(valid):
    _fails(_put(valid, "healpix", _rows(valid, "Hipparcos")[0],
                12 * 4 ** schema.HEALPIX_LEVEL), "healpix outside")


def test_hipparcos_healpix_inconsistent(valid):
    i = _rows(valid, "Hipparcos")[0]
    _fails(_put(valid, "healpix", i, valid["healpix"][i].as_py() ^ 1),
           "inconsistent with ra/dec")


def test_conform_missing_column(sample_csv_path):
    df = pd.read_csv(sample_csv_path).drop(columns=["ra"])
    with pytest.raises(SchemaError, match="missing columns"):
        schema.conform(df)


def test_conform_uint8_overflow(sample_csv_path):
    df = pd.read_csv(sample_csv_path, dtype={"star_id": str}, keep_default_na=False,
                     na_values=[""])
    df["source_id"], df["hip"], df["healpix"] = csv_io._derive_ids(df)
    df["rgb_r"] = pd.array([300] + [1] * (len(df) - 1), dtype="Int64")
    with pytest.raises(SchemaError, match="rgb_r"):
        schema.conform(df)

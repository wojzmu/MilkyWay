"""CSV <-> Arrow adapter: bit-exact ids, healpix, lossless round trip."""
import numpy as np
import pandas as pd
import pyarrow as pa
import pytest

from milkyway import schema
from milkyway.csv_io import LEGACY_CSV_COLUMNS, read_catalogue_csv, write_catalogue_csv


@pytest.fixture(params=["sample_csv_path", "reference_csv_path"])
def csv_path(request):
    return request.getfixturevalue(request.param)


@pytest.fixture
def table(csv_path):
    return read_catalogue_csv(csv_path)


def _raw(path):
    return pd.read_csv(path, dtype={"star_id": str}, keep_default_na=False, na_values=[""],
                       float_precision="round_trip")


def test_read_validates_and_counts(csv_path, table):
    schema.validate(table)
    raw = _raw(csv_path)
    assert table.num_rows == len(raw)
    for cat in schema.ENUMS["source_catalogue"]:
        assert (table["source_catalogue"].to_pylist().count(cat)
                == (raw["source_catalogue"] == cat).sum())


def test_source_id_bit_exact(table):
    pre = len(schema.GAIA_ID_PREFIX)
    n = 0
    for sid, star_id in zip(table["source_id"].to_pylist(), table["star_id"].to_pylist()):
        if star_id.startswith(schema.GAIA_ID_PREFIX):
            assert sid == int(star_id[pre:])
            n += 1
        else:
            assert sid is None
    assert n > 0


def test_healpix(table):
    sid = table["source_id"].to_pylist()
    hpx = table["healpix"].to_pylist()
    hip_n = 0
    for s, h in zip(sid, hpx):
        if s is not None:
            assert h == s >> schema.GAIA_HEALPIX_SHIFT
        else:
            assert 0 <= h < 12 * 4 ** schema.HEALPIX_LEVEL
            hip_n += 1
    assert hip_n == table["hip"].drop_null().length()


def test_round_trip(csv_path, table, tmp_path):
    out = tmp_path / "out.csv"
    write_catalogue_csv(table, out)
    a, b = _raw(csv_path), _raw(out)
    assert list(b.columns) == list(a.columns) == list(LEGACY_CSV_COLUMNS)
    assert set(a["star_id"]) == set(b["star_id"])
    a, b = a.set_index("star_id"), b.set_index("star_id").loc[a["star_id"]]
    for f in schema.CATALOGUE_SCHEMA:
        if f.name not in LEGACY_CSV_COLUMNS[1:]:
            continue
        x, y = a[f.name], b[f.name]
        assert (x.isna() == y.isna()).all(), f.name
        if pa.types.is_float32(f.type):
            m = x.notna()
            x, y = x[m].to_numpy(float), y[m].to_numpy(float)
            zero = x == 0
            assert (np.abs(x - y)[zero] <= 1e-30).all(), f.name
            rel = np.abs(x - y)[~zero] / np.abs(x[~zero])
            assert (rel <= 1.2e-7).all(), (f.name, rel.max())
        else:
            assert x.equals(y), f.name


def test_round_trip_idempotent(table, tmp_path):
    p1, p2 = tmp_path / "1.csv", tmp_path / "2.csv"
    write_catalogue_csv(table, p1)
    write_catalogue_csv(read_catalogue_csv(p1), p2)
    assert p1.read_bytes() == p2.read_bytes()


def test_unknown_prefix_raises(sample_csv_path, tmp_path):
    df = pd.read_csv(sample_csv_path, dtype={"star_id": str}, keep_default_na=False)
    df.loc[0, "star_id"] = "TYC 123"
    p = tmp_path / "bad.csv"
    df.to_csv(p, index=False)
    with pytest.raises(ValueError, match="TYC 123"):
        read_catalogue_csv(p)

import numpy as np
import pandas as pd
import pytest

from milkyway import catalog_query as cq
from milkyway import csv_io, schema, storage


@pytest.fixture
def built(sample_csv_path, tmp_dataset_dir):
    table = csv_io.read_catalogue_csv(sample_csv_path)
    d = tmp_dataset_dir / "ds"
    storage.write_dataset([table], d, dataset_id="ds", selection={}, source={})
    return d, table.to_pandas()


def test_connect_refuses_without_manifest(built):
    d, _ = built
    (d / storage.MANIFEST_NAME).unlink()
    with pytest.raises(storage.IncompleteDatasetError):
        cq.connect(d)


def test_count_matches_csv(built, sample_csv_path):
    d, _ = built
    n = len(pd.read_csv(sample_csv_path))
    assert cq.connect(d).execute("select count(*) from catalog").fetchone()[0] == n


def test_read_catalogue_roundtrip(built):
    d, ref = built
    df = cq.read_catalogue(d)
    assert set(df["star_id"]) == set(ref["star_id"])
    assert df["dist_pc"].is_monotonic_increasing
    assert list(df.index) == list(range(len(df)))
    gaia = df[df["source_catalogue"] == "Gaia"]
    assert len(gaia) > 0
    assert all(int(s[9:]) == sid for s, sid in zip(gaia["star_id"], gaia["source_id"]))
    assert list(cq.read_catalogue(d, columns=["star_id", "dist_pc"]).columns) == [
        "star_id", "dist_pc"]


@pytest.mark.parametrize("level", [0, 2, 5])
def test_sky_slice(built, level):
    d, ref = built
    con = cq.connect(d)
    pix = pd.Series(ref["healpix"].to_numpy("int64") >> (2 * (schema.HEALPIX_LEVEL - level)))
    for pixel in pix.unique()[:3]:
        got = cq.sky_slice(con, int(pixel), level)
        assert set(got["star_id"]) == set(ref["star_id"][pix == pixel])
        assert len(got) == int((pix == pixel).sum())
    seen = set(pix)
    absent = next((p for p in range(12 * 4 ** level) if p not in seen), None)
    if absent is not None:
        assert cq.sky_slice(con, absent, level).empty


def test_sky_slice_validates(built):
    con = cq.connect(built[0])
    with pytest.raises(ValueError):
        cq.sky_slice(con, 12, 0)
    with pytest.raises(ValueError):
        cq.sky_slice(con, 0, 13)
    with pytest.raises(TypeError):
        cq.sky_slice(con, "0; drop", 0)


def test_within_distance_and_z_histogram(built):
    d, ref = built
    con = cq.connect(d)
    cut = float(ref["dist_pc"].median())
    assert len(cq.within_distance(con, cut)) == int((ref["dist_pc"] <= cut).sum())
    h = cq.z_histogram(con, bin_pc=10.0, max_dist_pc=cut)
    sub = ref[ref["dist_pc"] <= cut]
    want = pd.Series(np.floor(sub["z_pc"].astype("float64") / 10.0) * 10.0).value_counts()
    assert dict(zip(h["z_lo"], h["n"])) == want.to_dict()

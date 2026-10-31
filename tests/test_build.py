"""build_catalogue on a synthetic 192-tile fetch plus Hipparcos aux tables (offline)."""
import json

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

pytest.importorskip("zero_point")

from milkyway import build, catalog_query, raw, storage   # noqa: E402
from tests.test_raw import make_table                    # noqa: E402

N = 2   # rows per tile


def _fetch(tmp_path, ruwe=(1.0, 1.0), empty=()):
    fdir = tmp_path / "fetch"
    tiles = raw.plan_tiles({k: 0 if k in empty else N for k in range(192)})
    for tile in tiles:
        if tile.k in empty:
            raw.write_tile(make_table(tile, 0), fdir, tile)
            continue
        t = make_table(tile, N, astrometric_params_solved=[31] * N,
                       nu_eff_used_in_astrometry=[1.5] * N, pseudocolour=[None] * N,
                       ecl_lat=[10.0] * N, parallax_error=[0.05] * N,
                       bp_rp=[0.8] * N, radial_velocity=[None] * N, ruwe=list(ruwe))
        raw.write_tile(t, fdir, tile)
    raw.finalize_fetch(fdir, tiles, fetch_id="synthetic", selection=raw.DEFAULT_SELECTION,
                       service="test")
    return fdir, tiles


def _aux(tmp_path, gaia_sid):
    adir = tmp_path / "aux"
    adir.mkdir()
    #           hip   ra     de    plx  note
    stars = [(1, 10.0, 10.0, 5.0),    # 5p best_neighbour -> excluded
             (2, 1.5, 1.5, 5.0),      # same position as the synthetic Gaia rows -> matched
             (3, 100.0, 40.0, 5.0),   # isolated -> kept
             (4, 200.0, -30.0, 0.3),  # parallax below the fetch floor -> dropped
             (5, 250.0, 60.0, 2.0),   # 2p best_neighbour, isolated -> kept
             (6, 1.5, 1.5 + 2.5 / 3600, 1.0),  # 2.5" off, same parallax -> matched
             (7, 300.0, 10.0, 5.0)]   # no B-V (G untransformable), isolated -> kept
    hip = pd.DataFrame(stars, columns=["hip", "ra", "de", "plx"])
    hip = hip.assign(e_plx=0.2, pmra=0.0, pmde=0.0, vmag=9.0, b_v=0.5, v_i=0.6)
    hip.loc[hip["hip"].isin([2, 6]), "vmag"] = 10.1   # G within 1 mag of the Gaia rows (10.0)
    hip.loc[hip["hip"] == 7, "b_v"] = np.nan
    hip["hip"] = hip["hip"].astype("int32")
    pq.write_table(pa.Table.from_pandas(hip, preserve_index=False), adir / "hipparcos.parquet")
    nb = pa.table({"hip": pa.array([1, 5], pa.int32()),
                   "source_id": pa.array([gaia_sid, 12345], pa.int64()),
                   "angular_distance": pa.array([0.1, 0.1], pa.float32()),
                   "number_of_neighbours": pa.array([1, 1], pa.int16()),
                   "parallax": [5.0, None], "parallax_error": pa.array([0.05, None], pa.float32()),
                   "phot_g_mean_mag": pa.array([9.0, 9.0], pa.float32()),
                   "bp_rp": pa.array([0.8, None], pa.float32()),
                   "astrometric_params_solved": pa.array([31, 3], pa.int16()),
                   "ra": [10.0, 250.0], "dec": [10.0, 60.0]})
    pq.write_table(nb, adir / "hip2_best_neighbour.parquet")
    files = {n: {"rows": pq.read_metadata(adir / n).num_rows, "sha256": storage._sha256(adir / n)}
             for n in ("hipparcos.parquet", "hip2_best_neighbour.parquet")}
    (adir / "aux_manifest.json").write_text(json.dumps({"files": files}))
    return adir


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("build")
    fdir, tiles = _fetch(tmp)
    gaia_sid = tiles[7].lo                       # first row of tile 7
    adir = _aux(tmp, gaia_sid)
    out = tmp / "ds"
    m = build.build_catalogue(fdir, adir, out, dataset_id="ds", log=lambda *a: None)
    return m, out, gaia_sid


def test_manifest_and_counts(built):
    m, out, _ = built
    assert storage.open_catalog(out)["status"] == "complete"
    assert m["storage"]["total_rows"] == 192 * N + 3
    h = m["provenance"]["hipparcos"]["counts"]
    assert h["matched_by_position"] == 2 and h["kept"] == 3
    assert h["matched_by_parallax_only"] == 1 and h["without_transformed_g"] == 1
    assert h["kept_with_neighbour_within_match_radius"] == 0
    assert m["provenance"]["counts"]["zp_origin"] == {"lindegren2021": 192 * N, "none": 3}
    assert m["provenance"]["parallax"]["method"] == "lindegren2021_clamped"
    assert m["provenance"]["frame"]["preset"] == "v4.0"
    assert m["selection"] == {**raw.DEFAULT_SELECTION, "quality_cuts": None}


def test_rows(built):
    _, out, gaia_sid = built
    df = catalog_query.read_catalogue(out)
    hip_rows = df[df["source_catalogue"] == "Hipparcos"]
    assert sorted(hip_rows["star_id"]) == ["HIP 3", "HIP 5", "HIP 7"]
    assert hip_rows.loc[hip_rows["star_id"] == "HIP 7", "g_mag"].isna().all()
    assert (hip_rows["zp_origin"] == "none").all()
    g = df[df["source_catalogue"] == "Gaia"]
    assert g.loc[g["source_id"] == gaia_sid, "hip"].tolist() == [1]
    # corrected parallax = raw - zp; distance is its inverse
    vc = g["parallax_mas"] - g["parallax_zp_mas"]
    np.testing.assert_allclose(g["dist_pc"], 1000 / vc, rtol=1e-6)
    assert (g["r_lo_pc"] < g["dist_pc"]).all() and (g["dist_pc"] < g["r_hi_pc"]).all()
    # Galactocentric: distance from the Sun's position (-8121.97, 0, 20.8) is dist_pc
    d = np.sqrt((df["xgc_pc"] + 8121.9734) ** 2 + df["ygc_pc"] ** 2 + (df["zgc_pc"] - 20.8) ** 2)
    np.testing.assert_allclose(d, df["dist_pc"], atol=0.01)


def test_galactocentric_sun_and_roundtrip():
    from milkyway.astrometry import galactocentric_xyz
    x, y, z = galactocentric_xyz([0.0], [90.0], [1e-9])
    np.testing.assert_allclose([x[0], y[0], z[0]], [-8121.97, 0.0, 20.8], atol=0.01)


def test_no_hipparcos_candidates(tmp_path):
    fdir, tiles = _fetch(tmp_path)
    adir = _aux(tmp_path, tiles[7].lo)
    hip = pq.read_table(adir / "hipparcos.parquet").to_pandas()
    pq.write_table(pa.Table.from_pandas(hip[hip["plx"] < 0.5], preserve_index=False),
                   adir / "hipparcos.parquet")
    with pytest.raises(ValueError, match="SHA-256"):
        build.build_catalogue(fdir, adir, tmp_path / "x", dataset_id="x", log=lambda *a: None)
    am = json.loads((adir / "aux_manifest.json").read_text())
    am["files"]["hipparcos.parquet"]["sha256"] = storage._sha256(adir / "hipparcos.parquet")
    (adir / "aux_manifest.json").write_text(json.dumps(am))
    m = build.build_catalogue(fdir, adir, tmp_path / "ds", dataset_id="ds", log=lambda *a: None)
    assert m["storage"]["total_rows"] == 192 * N
    assert m["provenance"]["hipparcos"]["counts"]["kept"] == 0


def test_legacy_cuts(tmp_path):
    """Cuts drop the ruwe >= 1.4 row of every tile; best_neighbour is ignored, so HIP 1
    (isolated, its neighbour row is not where it is) stays and owns its hip number."""
    fdir, tiles = _fetch(tmp_path, ruwe=(1.0, 2.0))
    adir = _aux(tmp_path, tiles[7].lo)
    m = build.build_catalogue(fdir, adir, tmp_path / "ds", dataset_id="ds",
                              quality_cuts=build.LEGACY_QUALITY_CUTS, log=lambda *a: None)
    assert m["selection"]["quality_cuts"] == build.LEGACY_QUALITY_CUTS
    df = catalog_query.read_catalogue(tmp_path / "ds")
    gaia = df[df["source_catalogue"] == "Gaia"]
    assert len(gaia) == 192 and (gaia["ruwe"] < 1.4).all()
    # HIP 5 has plx/e_plx = 10 exactly and HIP 6 has 5: both fail the legacy "> 10" cut
    assert sorted(df.loc[df["source_catalogue"] == "Hipparcos", "star_id"]) == [
        "HIP 1", "HIP 3", "HIP 7"]
    # HIP 2 was matched by position, so one Gaia row at its place carries hip 2
    assert gaia["hip"].dropna().tolist() == [2]


def test_empty_tile_becomes_empty_partition(tmp_path):
    fdir, tiles = _fetch(tmp_path, empty=(3,))
    adir = _aux(tmp_path, tiles[7].lo)
    m = build.build_catalogue(fdir, adir, tmp_path / "ds", dataset_id="ds", log=lambda *a: None)
    parts = {p["part_hpx"]: p["rows"] for p in m["storage"]["partitions"]}
    assert len(parts) == 192 and parts[3] == 0
    assert storage.open_catalog(tmp_path / "ds")["status"] == "complete"

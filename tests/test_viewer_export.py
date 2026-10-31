"""Binary viewer export (points.bin / details.bin / index.json) on a synthetic build."""
import json

import numpy as np
import pytest

pytest.importorskip("zero_point")

from milkyway import build, catalog_query, viewer_export as ve   # noqa: E402
from tests.test_build import N, _aux, _fetch                      # noqa: E402


@pytest.fixture(scope="module")
def dataset(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("vx")
    fdir, tiles = _fetch(tmp)
    adir = _aux(tmp, tiles[7].lo)
    build.build_catalogue(fdir, adir, tmp / "ds", dataset_id="ds", log=lambda *a: None)
    return tmp / "ds"


def _read(out):
    pts = (out / "points.bin").read_bytes()
    det = (out / "details.bin").read_bytes()
    idx = json.loads((out / "index.json").read_text())
    n = int(np.frombuffer(pts, "<u4", 1, 8)[0])
    assert np.frombuffer(pts, "<u2", 2, 4).tolist() == [2, 0b11]   # version, flags
    rgbu_at = 16 + 6 * n + (-6 * n) % 4
    xyz = np.frombuffer(pts, "<i2", 3 * n, 16).reshape(n, 3) * idx["position_scale_pc"]
    rgbu = np.frombuffer(pts, np.uint8, 4 * n, rgbu_at).reshape(n, 4)
    cls = np.frombuffer(pts, np.uint8, n, rgbu_at + 4 * n)
    rec = np.frombuffer(det, [("id", "<i8"), ("r_lo", "<f4"), ("r_hi", "<f4"),
                              ("g", "<f4"), ("bp_rp", "<f4")], n, 16)
    return pts, det, idx, n, xyz, rgbu, cls, rec


def test_splitmix64_reference_value():
    assert int(ve.splitmix64(np.array([0], np.uint64))[0]) == 0xE220A8397B1DCDAF


def test_uncertainty_code():
    d = np.ones(4, np.float32)
    u = ve.uncertainty_code(d, np.array([1.0, 0.5, 0.9995, 1.0], np.float32),
                            np.array([1.0, 1.5, 1.0005, np.nan], np.float32))
    assert list(u) == [0, 254, 0, 255]


def test_full_export_roundtrip(dataset, tmp_path):
    ve.export_viewer(dataset, tmp_path, target=10**9)          # f = 1: keep all
    pts, det, idx, n, xyz, rgbu, cls, rec = _read(tmp_path)
    assert pts[:4] == b"MWPT" and det[:4] == b"MWDT"
    assert n == idx["n"] == 192 * N + 3 and idx["sampling"]["f"] == 1.0
    assert len(pts) % 4 == 0 and len(pts) - (16 + 11 * n) < 6 and len(det) == 16 + 24 * n
    assert idx["files"]["points.bin"]["bytes"] == len(pts)
    df = catalog_query.read_catalogue(dataset).set_index("star_id")
    ids = [f"Gaia DR3 {i}" if i >= 0 else f"HIP {-i}" for i in rec["id"].tolist()]
    sub = df.loc[ids]
    tol = idx["position_scale_pc"] / 2 + 1e-6               # int16 quantisation
    np.testing.assert_allclose(xyz[:, 0], sub["x_pc"].to_numpy(), atol=tol, rtol=0)
    np.testing.assert_allclose(xyz[:, 2], sub["z_pc"].to_numpy(), atol=tol, rtol=0)
    np.testing.assert_array_equal(rgbu[:, 0], sub["rgb_r"].fillna(128).to_numpy(np.uint8))
    assert [ve.CLASS_CODES[c] for c in cls] == sub["star_class"].tolist()
    assert sorted(i for i in rec["id"].tolist() if i < 0) == [-7, -5, -3]


def test_thinning_and_order(dataset, tmp_path):
    ve.export_viewer(dataset, tmp_path, target=100, always_g_max=9.5)
    *_, idx, n, xyz, rgbu, cls, rec = _read(tmp_path)
    s = idx["sampling"]
    assert s["n_always"] == 2              # HIP 3 and 5 (G ~ 8.9); HIP 7 has no G
    assert 2 < n < 2 + 250 and (rec["id"][:2] < 0).all()
    h = ve.splitmix64(rec["id"][2:].view(np.uint64))
    assert (np.diff(h.astype(np.float64)) >= 0).all()          # sorted by hash
    assert (h < np.uint64(int(s["f"] * 2 ** 64))).all()


def test_abs_mag_cut_without_thinning(dataset, tmp_path):
    ve.export_viewer(dataset, tmp_path, target=None, abs_mag_max=0.5)
    *_, idx, n, xyz, rgbu, cls, rec = _read(tmp_path)
    df = catalog_query.read_catalogue(dataset)
    assert n == int((df["abs_g"] <= 0.5).sum()) > 0         # every eligible star, no thinning
    assert idx["sampling"]["f"] == 1.0 and idx["selection"]["abs_mag_max"] == 0.5


def test_display_rgb_prefers_dereddened_colour():
    import pyarrow as pa
    from milkyway.color import build_rgb_table, teff_from_bprp
    t = pa.table({"bp_rp0": pa.array([0.0, None, None], pa.float32()),
                  "bp_rp": pa.array([1.5, 1.5, None], pa.float32())})
    rgb = ve.display_rgb(t)
    r, g, b, _ = build_rgb_table(teff_from_bprp(np.array([0.0, 1.5])))
    assert rgb[:2].tolist() == np.stack([r, g, b], axis=1).tolist()
    assert rgb[2].tolist() == [128, 128, 128]


def test_abs_mag_cut_uses_dereddened_magnitude(tmp_path):
    from tests.test_dust import write_map
    fdir, tiles = _fetch(tmp_path)
    adir = _aux(tmp_path, tiles[7].lo)
    dmap = write_map(tmp_path / "dust.fits", 1e-3, bounds=np.array([69.0, 300.0, 1250.0]))
    build.build_catalogue(fdir, adir, tmp_path / "ds", dataset_id="ds",
                          dust_map_path=dmap, log=lambda *a: None)
    df = catalog_query.read_catalogue(tmp_path / "ds")
    ve.export_viewer(tmp_path / "ds", tmp_path / "out", target=None, abs_mag_max=0.5)
    *_, n, _, _, _, _ = _read(tmp_path / "out")
    m = df["abs_g0"].fillna(df["abs_g"])
    assert n == int(((m <= 0.5) & (df["dist_pc"] <= 1250)).sum())


def test_labels(dataset, tmp_path):
    names = tmp_path / "names.csv"
    names.write_text("# test\nhip,name,name_iau,v_mag,tier\n3,Trzecia,Third,1.0,1\n"
                     "1,Pierwsza,First,2.0,2\n999,Brak,Missing,3.0,3\n", encoding="utf-8")
    ve.export_viewer(dataset, tmp_path / "out", target=None, names_file=names)
    *_, idx, n, xyz, rgbu, cls, rec = _read(tmp_path / "out")
    doc = json.loads((tmp_path / "out" / "labels.json").read_text(encoding="utf-8"))
    by = {lb["name_iau"]: lb for lb in doc["labels"]}
    assert set(by) == {"Third", "First"}
    assert idx["labels"]["not_in_catalogue"] == ["Missing"]
    assert idx["labels"]["n"] == 2 and "labels.json" in idx["files"]
    df = catalog_query.read_catalogue(dataset)
    for lb in by.values():
        row = df[df["hip"] == lb["hip"]].iloc[0]
        assert abs(lb["x_pc"] - row["x_pc"]) < 0.01 and abs(lb["dist_pc"] - row["dist_pc"]) < 0.01
        i = lb["point"]
        assert i is not None
        assert rec["id"][i] == (row["source_id"] if row["source_catalogue"] == "Gaia" else -row["hip"])
    assert by["Third"]["name"] == "Trzecia"


def test_star_names_file():
    names = ve.load_star_names()
    assert len(names) == 102
    assert {"Sirius", "Betelgeuse", "Vega", "Polaris", "Alpha Centauri A"} <= {n["name"] for n in names}
    assert names[0]["name_iau"] == "Sirius" and names[0]["tier"] == 1


def test_export_star_names(dataset, tmp_path):
    """Each name lists HIP <n> plus the Gaia ids the catalogue and best_neighbour give."""
    import pyarrow as pa
    import pyarrow.parquet as pq
    names = tmp_path / "names.csv"
    names.write_text("hip,name,name_iau,v_mag,tier\n1,Pierwsza,First,2.0,1\n"
                     "3,Trzecia,Third,1.0,1\n", encoding="utf-8")
    df = catalog_query.read_catalogue(dataset)
    sid1 = int(df.loc[df["hip"] == 1, "source_id"].iloc[0])
    aux = tmp_path / "aux"
    aux.mkdir()
    pq.write_table(pa.table({"source_id": pa.array([42, 43], pa.int64()),
                             "hip": pa.array([3, 999], pa.int32())}),
                   aux / "hip2_best_neighbour.parquet")
    doc = ve.export_star_names(dataset, aux, tmp_path / "star_names.json", names_file=names)
    by = {n["name_iau"]: n["star_ids"] for n in doc["names"]}
    assert by["First"] == ["HIP 1", f"Gaia DR3 {sid1}"]
    assert by["Third"] == ["HIP 3", "Gaia DR3 42"]
    on_disk = json.loads((tmp_path / "star_names.json").read_text(encoding="utf-8"))
    assert on_disk["names"] == doc["names"]


def test_named_stars_bypass_abs_mag_cut(dataset, tmp_path):
    """Every label gets a point, even when the magnitude cut drops its star (D-027)."""
    names = tmp_path / "names.csv"
    names.write_text("hip,name,name_iau,v_mag,tier\n3,Third,Third,1.0,1\n1,First,First,2.0,2\n",
                     encoding="utf-8")
    ve.export_viewer(dataset, tmp_path / "out", target=None, abs_mag_max=-99,
                     names_file=names)
    *_, idx, n, xyz, rgbu, cls, rec = _read(tmp_path / "out")
    doc = json.loads((tmp_path / "out" / "labels.json").read_text(encoding="utf-8"))
    assert n == 2 and idx["sampling"]["n_named_extra"] == 2
    assert sorted(lb["point"] for lb in doc["labels"]) == [0, 1]
    assert idx["labels"]["not_exported"] == 0

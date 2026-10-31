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

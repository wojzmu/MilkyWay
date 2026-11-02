"""New pipeline vs the frozen 60 pc reference catalogue at the old cuts (D-013, D-020).

Needs the local no-G-limit fetch `data/raw/dr3/dr3_p16.667` (192 tiles, 97 394 rows)
and the Hipparcos aux tables; skips when they are absent. Builds in ~15 s.
The fetch was made with `fetch.run_fetch(data_dir=..., fetch_id="dr3_p16.667",
counts_path="docs/data/dr3_p16.667_hpx2_counts.csv",
selection={"parallax_min_mas": 16.666667, "g_max": None})` (no CLI flag for that).
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("zero_point")

from milkyway import build, catalog_query   # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
FETCH = ROOT / "data" / "raw" / "dr3" / "dr3_p16.667"
AUX = ROOT / "data" / "raw" / "dr3" / "aux"
# Hipparcos stars the old pipeline dropped by matching them to a faint Gaia neighbour
# 1.5-1.6" away (|dG| = 4.6 and 6.2 mag); the new rule keeps them.
EXTRA_HIP = {"HIP 88405", "HIP 108422"}
# Binaries the old pipeline held twice: a Gaia component 2.3-2.9" away with the same
# parallax (within 3 sigma, |dG| < 2.5) now stands for the system (D-020).
DROPPED_HIP = {"HIP 14886", "HIP 6234", "HIP 28796", "HIP 54980", "HIP 45688",
               "HIP 69442", "HIP 83608", "HIP 72423", "HIP 112504", "HIP 91919"}


@pytest.fixture(scope="module")
def merged(tmp_path_factory, reference_csv_path):
    if not (FETCH / "fetch_manifest.json").exists() or not (AUX / "aux_manifest.json").exists():
        pytest.skip("60 pc fetch or Hipparcos aux tables not present")
    out = tmp_path_factory.mktemp("ref60") / "ds"
    build.build_catalogue(FETCH, AUX, out, dataset_id="ref60",
                          quality_cuts=build.LEGACY_QUALITY_CUTS, log=lambda *a: None)
    new = catalog_query.read_catalogue(out)
    ref = pd.read_csv(reference_csv_path, dtype={"star_id": str}, float_precision="round_trip")
    return new, ref


def _ids(df, cat):
    return set(df.loc[df["source_catalogue"] == cat, "star_id"])


def test_same_gaia_stars_and_parallaxes(merged):
    new, ref = merged
    assert _ids(new, "Gaia") == _ids(ref, "Gaia")
    m = new.merge(ref, on="star_id", suffixes=("", "_ref"))
    g = m[m["source_catalogue"] == "Gaia"]
    assert len(g) == 58_931
    assert (g["parallax_mas"] == g["parallax_mas_ref"]).all()       # bit for bit


def test_hipparcos_rows(merged):
    new, ref = merged
    assert _ids(new, "Hipparcos") - _ids(ref, "Hipparcos") == EXTRA_HIP
    assert _ids(ref, "Hipparcos") - _ids(new, "Hipparcos") == DROPPED_HIP
    m = new.merge(ref, on="star_id", suffixes=("", "_ref"))
    h = m[m["source_catalogue"] == "Hipparcos"]
    # The old CSV went through float32; compare at that precision.
    assert (h["parallax_mas"].astype(np.float32) == h["parallax_mas_ref"].astype(np.float32)).all()


def test_distances_differ_only_by_zero_point(merged):
    new, ref = merged
    m = new.merge(ref, on="star_id", suffixes=("", "_ref"))
    g = m[m["source_catalogue"] == "Gaia"]
    np.testing.assert_allclose(1000 / g["dist_pc_ref"], g["parallax_mas"], rtol=1e-6)
    np.testing.assert_allclose(1000 / g["dist_pc"], g["parallax_mas"] - g["parallax_zp_mas"],
                               rtol=1e-6)
    half = (g["r_hi_pc"] - g["r_lo_pc"]) / 2
    outside = (g["dist_pc_ref"] - g["dist_pc"]).abs() > 3 * half
    assert outside.mean() < 0.05                                    # measured: 4.0 %
    # every outlier is a star whose zero-point is ~3 sigma or more of its parallax
    zp_sigma = g["parallax_zp_mas"].abs() / g["parallax_error"]
    assert (zp_sigma[outside] > 2.99).all()

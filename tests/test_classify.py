import numpy as np

from milkyway.classify import classify_from_hr, classify_from_hr_array


def test_array_matches_scalar():
    rng = np.random.default_rng(3)
    n = 20000
    abs_g = rng.uniform(-6, 20, n)
    bp_rp = rng.uniform(-0.5, 5, n)
    teff = rng.uniform(1500, 12000, n)
    abs_g[::50], bp_rp[1::50], teff[2::50] = np.nan, np.nan, np.nan
    got = classify_from_hr_array(abs_g, bp_rp, teff)
    want = [classify_from_hr(a, b, t) for a, b, t in zip(abs_g, bp_rp, teff)]
    assert list(got) == want
    assert len(set(want)) >= 7

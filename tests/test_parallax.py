"""Zero-point layer and inversion distances (plan v4 S2 acceptance, adapted to 1.0)."""
import numpy as np
import pytest

pytest.importorskip("zero_point")
from zero_point import zpt                                     # noqa: E402

from milkyway import distance, parallax                        # noqa: E402
from milkyway.parallax import EPS_COLOUR, EPS_G                # noqa: E402

zpt.load_tables()


def _zp(g, nu=1.5, pc=1.5, beta=10.0, solved=31):
    zp, origin = parallax.zero_point([g], [nu], [pc], [beta], [solved])
    return zp[0], origin[0]


def _pkg(g, nu=1.5, pc=1.5, beta=10.0, solved=31):
    return zpt.get_zpt(np.array([g]), np.array([nu]), np.array([pc]), np.array([beta]),
                       np.array([float(solved)]), _warnings=False)[0]


def test_in_range_equals_package():
    rng = np.random.default_rng(1)
    n = 2000
    g = rng.uniform(6.5, 20.5, n)
    nu = rng.uniform(1.15, 1.85, n)
    pc = rng.uniform(1.3, 1.7, n)
    beta = rng.uniform(-90, 90, n)
    solved = rng.choice([31, 95], n)
    zp, origin = parallax.zero_point(g, nu, pc, beta, solved)
    want = zpt.get_zpt(g, np.where(solved == 31, nu, np.nan),
                       np.where(solved == 95, pc, np.nan), beta, solved.astype(float),
                       _warnings=False)
    np.testing.assert_array_equal(zp, want)
    assert set(origin) == {"lindegren2021"}


@pytest.mark.parametrize("kw, clamped", [
    ({"g": 6.0}, {"g": 6.0 + EPS_G}),
    ({"g": 21.0}, {"g": 21.0 - EPS_G}),
    ({"g": 12.0, "nu": 1.95}, {"g": 12.0, "nu": 1.9 - EPS_COLOUR}),
    ({"g": 12.0, "nu": 1.05}, {"g": 12.0, "nu": 1.1 + EPS_COLOUR}),
    ({"g": 12.0, "pc": 1.80, "solved": 95}, {"g": 12.0, "pc": 1.72 - EPS_COLOUR, "solved": 95}),
])
def test_out_of_range_is_clamped_to_interior(kw, clamped):
    zp, origin = _zp(**kw)
    assert np.isfinite(zp) and origin == "lindegren2021_clamped"
    assert zp == _pkg(**clamped)


def test_bright_end_continuous():
    assert abs(_zp(5.5)[0] - _zp(6.0 + EPS_G)[0]) < 1e-3   # < 1 microarcsec


def test_mixed_batch():
    zp, origin = parallax.zero_point(
        g=[12, 12, 12, np.nan, 12, 12],
        nu_eff=[1.5, 1.5, np.nan, 1.5, 1.5, np.nan],
        pseudocolour=[np.nan, np.nan, 1.5, np.nan, np.nan, np.nan],
        ecl_lat=[10, 10, 10, 10, np.nan, 10],
        solved=[3, 31, 95, 31, 31, 95])
    assert list(origin) == ["none", "lindegren2021", "lindegren2021", "global_fallback",
                            "global_fallback", "global_fallback"]
    assert np.isnan(zp[0])
    assert zp[3] == parallax.GLOBAL_FALLBACK_ZP_MAS


def test_corrected_parallax_sign_and_inflation():
    vc, sc, zp, _ = parallax.corrected_parallax([1.0], [0.1], [12], [1.5], [np.nan],
                                                [10], [31], error_inflation=1.2)
    assert vc[0] == 1.0 - zp[0] and sc[0] == pytest.approx(0.12)
    assert zp[0] < 0          # typical DR3 zero-point: corrected parallax grows


def test_inversion_quantiles():
    r_lo, r_med, r_hi, flag = distance.inversion_distances(
        [10.0, 1.0, 0.5, 2.0], [0.1, 0.5, 0.6, np.nan])
    np.testing.assert_allclose(r_med, [100, 1000, 2000, 500])
    np.testing.assert_allclose(r_lo[:3], [1000 / 10.1, 1000 / 1.5, 1000 / 1.1])
    assert r_hi[0] == pytest.approx(1000 / 9.9) and r_hi[1] == pytest.approx(2000)
    assert np.isnan(r_hi[2]) and np.isnan(r_lo[3]) and np.isnan(r_hi[3])
    assert list(flag) == ["ok", "low_snr", "low_snr", "no_error"]


def test_inversion_quantiles_match_monte_carlo():
    rng = np.random.default_rng(2)
    varpi, sigma = 2.0, 0.2
    r = 1000 / rng.normal(varpi, sigma, 1_000_000)
    r_lo, r_med, r_hi, _ = distance.inversion_distances([varpi], [sigma])
    q = np.quantile(r, [0.158655, 0.5, 0.841345])
    np.testing.assert_allclose([r_lo[0], r_med[0], r_hi[0]], q, rtol=5e-3)


def test_nonpositive_parallax_has_no_distance():
    _, r_med, r_hi, _ = distance.inversion_distances([0.0, -1.0], [0.1, 0.1])
    assert np.isnan(r_med).all() and np.isnan(r_hi).all()

"""Scale-height fit on synthetic exponential discs (offline, no dataset needed)."""
import numpy as np
import pytest

from milkyway import scale_height as sh


def _disc(h, z_sun, n=200_000, seed=1, h_south=None):
    """Heliocentric z of an exponential disc whose plane is at z = -z_sun."""
    rng = np.random.default_rng(seed)
    side = rng.choice([-1, 1], n)
    hh = np.where(side > 0, h, h if h_south is None else h_south)
    z = rng.exponential(hh) * side - z_sun
    return z[np.abs(z) <= sh.Z_MAX_PC]


def test_recovers_h_and_z_sun():
    f = sh.fit_exponential(_disc(300.0, 20.0))
    assert abs(f["h_pc"] - 300) < 3 * f["h_err_pc"] and f["h_err_pc"] < 6
    assert abs(f["z_sun_pc"] - 20) < 3 * f["z_sun_err_pc"]
    assert not f["z_sun_fixed"] and f["side"] == "both"


def test_fixed_z_sun_and_one_side():
    z = _disc(250.0, 20.8, h_south=400.0)
    n = sh.fit_exponential(z, z_sun=20.8, side="north")
    s = sh.fit_exponential(z, z_sun=20.8, side="south")
    assert abs(n["h_pc"] - 250) < 3 * n["h_err_pc"] and n["n_south"] == 0
    assert abs(s["h_pc"] - 400) < 3 * s["h_err_pc"] and s["n_north"] == 0
    with pytest.raises(ValueError, match="fixed z_sun"):
        sh.fit_exponential(z, side="north")


def test_too_few_stars():
    with pytest.raises(ValueError, match="too few"):
        sh.fit_exponential(np.array([200.0, -200.0]))


def test_select_dwarfs():
    nan = np.nan
    cyl = {"bp_rp0": np.array([0.82, 0.82, 0.82, 1.5, nan, 0.82]),
           "abs_g0": np.array([4.7, 2.0, 6.5, 6.0, 4.7, nan]),
           "bp_rp": np.array([1.0, 1.0, 1.0, 1.5, 1.0, 1.0]),
           "abs_g": np.array([5.5, 2.8, 7.3, 6.0, 5.5, 5.5])}
    # Sun-like dwarf in; subgiant, too faint, too red, no colour, no magnitude out
    assert sh.select_dwarfs(cyl).tolist() == [True, False, False, False, False, False]
    assert sh.select_dwarfs(cyl, dereddened=False)[0]       # observed: 1.0, 5.5 on the MS


def test_summary_keeps_one_sided_fits_apart():
    z = _disc(300.0, 20.0, n=100_000)
    fits = {"main": sh.fit_exponential(z),
            "no_dust_correction": sh.fit_exponential(z, window=(200.0, 500.0)),
            "north_only": sh.fit_exponential(z, z_sun=20.8, side="north"),
            "south_only": sh.fit_exponential(z, z_sun=20.8, side="south")}
    s = sh.summary(fits)
    assert s["h_range_pc"] == [round(fits["main"]["h_pc"], 1)] * 2
    assert s["h_north_pc"] == round(fits["north_only"]["h_pc"], 1)

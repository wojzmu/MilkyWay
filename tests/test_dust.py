"""Extinction from a synthetic Edenhofer-layout dust map, and the band coefficients."""
import numpy as np
import pandas as pd
import pytest

from milkyway import dust

BOUNDS = np.array([10.0, 20.0, 40.0, 80.0])


def write_map(path, density, nside=2, bounds=BOUNDS, inner_pc=None, inner=None):
    """FITS file in the layout of mean_and_std_healpix.fits (nested ordering).

    `density` is a scalar or an array of shape (12 nside^2,), constant in distance;
    the inner integral defaults to density * bounds[0]."""
    from astropy.io import fits
    npix = 12 * nside ** 2
    dens = np.broadcast_to(np.asarray(density, np.float32), (npix,))
    cube = np.tile(dens, (len(bounds) - 1, 1)).astype(np.float32)
    if inner is None:
        inner = dens * bounds[0]
    inner_pc = bounds[0] if inner_pc is None else inner_pc

    def img(data, name, **hdr):
        h = fits.ImageHDU(np.asarray(data, np.float32), name=name)
        h.header["NSIDE"], h.header["ORDERING"] = nside, "NESTED"
        for k, v in hdr.items():
            h.header[k] = v
        return h

    hdus = [fits.PrimaryHDU(),
            img(cube, "MEAN"), img(np.full_like(cube, 0.1), "STD."),
            img(inner, "MEAN OF INTEGRATED INNER",
                CTYPE=f"inner density integrated within {inner_pc:g} pc"),
            img(np.zeros(npix), "STD. OF INTEGRATED INNER",
                CTYPE=f"std. of inner density integrated within {inner_pc:g} pc"),
            fits.BinTableHDU.from_columns([fits.Column(
                "radial pixel centers", "E", array=(bounds[1:] + bounds[:-1]) / 2)]),
            fits.BinTableHDU.from_columns([fits.Column(
                "radial pixel boundaries", "E", array=bounds)])]
    fits.HDUList(hdus).writeto(path)
    return path


def test_constant_density_is_linear_in_distance(tmp_path):
    dm = dust.load_map(write_map(tmp_path / "m.fits", 0.01))
    assert dm.cum.shape == (4, 48)
    d = np.array([5.0, 10.0, 15.0, 33.0, 80.0, 200.0])
    e, flag = dust.integrated_e(dm, np.full(6, 123.0), np.full(6, -20.0), d)
    np.testing.assert_allclose(e, 0.01 * np.minimum(d, 80.0), rtol=1e-5)
    assert flag.tolist() == ["inner", "map", "map", "map", "map", "beyond_map"]


def test_pixel_centres_take_their_pixel(tmp_path):
    from astropy_healpix import HEALPix
    hp = HEALPix(nside=2, order="nested")
    dens = np.arange(48) * 1e-3
    dm = dust.load_map(write_map(tmp_path / "m.fits", dens))
    lon, lat = hp.healpix_to_lonlat(np.arange(48))
    e, _ = dust.integrated_e(dm, lon.deg, lat.deg, np.full(48, 30.0))
    np.testing.assert_allclose(e, dens * 30.0, rtol=1e-4, atol=1e-7)


def test_inner_radius_must_match_first_boundary(tmp_path):
    with pytest.raises(ValueError, match="inner integral"):
        dust.load_map(write_map(tmp_path / "m.fits", 0.01, inner_pc=69.0))


def test_missing_file_names_the_download(tmp_path):
    with pytest.raises(FileNotFoundError, match="zenodo"):
        dust.load_map(tmp_path / "nope.fits")


def test_band_coefficients():
    a = dust.band_extinction([0.01, 0.01, 1.0], [5800.0, 3500.0, 5800.0])
    ag, ebr = a["G"], a["BP"] - a["RP"]
    assert 2.25 < ag[0] / 0.01 < 2.35                 # A_G/A_V ~ 0.86, R(550) = 2.68
    assert 1.8 < ag[0] / ebr[0] < 1.9                 # A_G / E(BP-RP) for a solar star
    assert ag[1] < ag[0]                              # redder star, smaller A_G
    assert ag[2] < 100 * ag[0]                        # broad band: sublinear in E


def test_deredden_inverts_reddening():
    true0 = np.array([0.82, 1.84, 0.0])
    e = np.array([0.7, 0.3, 2.0])
    from milkyway.color import teff_from_bprp
    a = dust.band_extinction(e, teff_from_bprp(true0))
    observed = true0 + a["BP"] - a["RP"]
    ag, ebr, bp_rp0 = dust.deredden(observed, e)
    np.testing.assert_allclose(bp_rp0, true0, atol=2e-3)
    np.testing.assert_allclose(ag, a["G"], atol=2e-3)
    ag, _, bp_rp0 = dust.deredden(np.array([np.nan]), np.array([1.0]))
    assert np.isnan(bp_rp0[0])
    np.testing.assert_allclose(ag, dust.band_extinction([1.0], [dust.DEFAULT_TEFF])["G"])


def test_add_extinction(tmp_path):
    dm = dust.load_map(write_map(tmp_path / "m.fits", 0.01))
    df = pd.DataFrame({"l": [10.0, 200.0], "b": [5.0, -60.0], "dist_pc": [50.0, 100.0],
                       "bp_rp": [0.82, np.nan], "abs_g": [4.6, np.nan]})
    dust.add_extinction(df, dm)
    np.testing.assert_allclose(df["dust_e"], [0.5, 0.8], rtol=1e-5)
    np.testing.assert_allclose(df["abs_g0"][0], 4.6 - df["a_g"][0])
    assert df["dust_flag"].tolist() == ["map", "beyond_map"]
    dust.add_extinction(df, None)
    assert df["dust_e"].isna().all() and (df["dust_flag"] == "none").all()


def test_provenance(tmp_path):
    dm = dust.load_map(write_map(tmp_path / "m.fits", 0.01))
    p = dust.provenance(dm)
    assert p["map"]["shells"] == 3 and p["map"]["r_max_pc"] == 80.0
    assert set(p["passbands"]) == {"G", "BP", "RP"}
    assert dust.provenance(None) == {"map": None}

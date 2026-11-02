"""Extinction from the Edenhofer et al. (2024) 3D dust map (Mapa 1.0, milestone M5; D-024).

Map: posterior mean of the dust density, `mean_and_std_healpix.fits` (Zenodo
10.5281/zenodo.8187943, 3.25 GB): HEALPix nside 256 times 516 log-spaced distance
shells from 69 to 1250 pc, in units of E per pc, where E is the extinction unit of
Zhang, Green & Rix (2023). A_lambda = E * R(lambda), with R(lambda) their published
curve (Zenodo 10.5281/zenodo.7811871, `extinction_curve.txt`; R(550 nm) = 2.68).

We read the FITS file ourselves instead of using `dustmaps.edenhofer2023`: that
module needs healpy, which has no Windows wheels. The interpolation also differs on
purpose. dustmaps integrates up to the shell centres and interpolates log E; here
the cumulative E is put on the shell *boundaries*, where it is exact for a density
constant inside a shell, so E is linear in distance between boundaries. Across the
sky it is bilinear over the 4 nearest pixels (astropy-healpix). Inside the inner
radius (68.6 pc) the map gives only the total; we scale it as d / 68.6 pc. Beyond
the last boundary (1248.1 pc) E stays at its edge value (a lower bound) and the
row is flagged.

Band extinction: A_band(Teff, E) = -2.5 log10( int w 10^(-0.4 E R) / int w ) with
w = B_lambda(Teff) T_band(lambda) lambda (photon-counting Gaia EDR3 passbands, SVO
copies of the ESA files), tabulated on a (Teff, E) grid. Broad bands make the
coefficient depend on the star's colour (A_G/E = 1.96 at 3500 K, 2.31 at 5800 K,
2.59 at 10 000 K for small E) and on E itself (~9 % lower at E = 1). Teff comes
from the *dereddened* colour, so `deredden` iterates. R(lambda) starts at 392 nm;
below it it is extrapolated linearly (< 4 % of the BP weight at 5800 K).

numpy only at import; astropy (FITS, units) and astropy-healpix are imported inside
functions, like the rest of the package.
"""
import hashlib
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np

from .color import teff_from_bprp
from .config import PROJECT_ROOT

EDENHOFER_FILE = "mean_and_std_healpix.fits"
EDENHOFER_MD5 = "10c823a5fcf81b47b6e15530bcdf54dc"     # as published on Zenodo
EDENHOFER_DOI = "10.5281/zenodo.8187943"
DEFAULT_MAP_PATH = Path(PROJECT_ROOT) / "data" / "dust" / "edenhofer2023" / EDENHOFER_FILE

_DATA = Path(__file__).resolve().parent / "dust_data"
CURVE_FILE = "zhang2023_extinction_curve.txt"
PASSBAND_FILES = {"G": "gaia_edr3_G.dat", "BP": "gaia_edr3_BP.dat", "RP": "gaia_edr3_RP.dat"}
_SVO_IDS = {"G": "GAIA/GAIA3.G", "BP": "GAIA/GAIA3.Gbp", "RP": "GAIA/GAIA3.Grp"}

DEFAULT_TEFF = 5800.0      # band coefficients for rows without a colour
DEREDDEN_TOL = 1e-4        # mag: iterate Teff <- dereddened colour until this stable
DEREDDEN_MAX_ITER = 20
_TEFF_GRID = np.geomspace(2500.0, 30000.0, 61)   # teff_from_bprp's output range
_E_GRID = np.linspace(0.0, 20.0, 401)            # step 0.05; E above 20 is clamped

FLAG_MAP, FLAG_INNER, FLAG_BEYOND, FLAG_NONE = "map", "inner", "beyond_map", "none"


@dataclass
class DustMap:
    """Cumulative E on shell boundaries: `cum[k, pix]` = E from the Sun to `bounds[k]`."""
    nside: int
    nest: bool
    bounds: np.ndarray     # (n_shells + 1,) pc
    cum: np.ndarray        # (n_shells + 1, 12 nside^2) float32
    path: str = ""


def load_map(path=DEFAULT_MAP_PATH):
    """Read the mean density of an Edenhofer HEALPix file and integrate it (~1.6 GB)."""
    from astropy.io import fits

    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(
            f"{path} not found. Download it (3.25 GB, md5 {EDENHOFER_MD5}) from "
            f"https://zenodo.org/records/8187943/files/{EDENHOFER_FILE}")
    density = inner = bounds = None
    with fits.open(path, memmap=True) as hdul:
        for hdu in hdul:
            name = hdu.name.lower()
            if isinstance(hdu, fits.BinTableHDU):
                if "radial pixel boundaries" in hdu.data.names:
                    bounds = np.asarray(hdu.data["radial pixel boundaries"], dtype=np.float64)
            elif hdu.data is None:
                continue
            elif name in ("primary", "mean", "healpix times distance"):
                nside = int(hdu.header["NSIDE"])
                nest = hdu.header["ORDERING"].lower().startswith("nest")
                density = np.array(hdu.data, dtype=np.float32)       # out of the memmap
            elif name.startswith("mean of integrated inner"):
                ctype = (hdu.header.get("CTYPE") or hdu.header.get("CTYPE1")).lower()
                inner_pc = float(ctype.rsplit("within", 1)[1].strip().removesuffix("pc"))
                inner = np.array(hdu.data, dtype=np.float32)
    if density is None or inner is None or bounds is None:
        raise ValueError(f"{path}: mean density, inner integral or radial boundaries missing")
    n_shells, npix = density.shape
    if npix != 12 * nside ** 2 or inner.shape != (npix,) or bounds.shape != (n_shells + 1,):
        raise ValueError(f"{path}: inconsistent shapes {density.shape}, {inner.shape}, "
                         f"{bounds.shape} for nside {nside}")
    # The published file labels the inner integral "within 68.8 pc" (the first shell's
    # centre) while the first boundary is 68.62 pc; we take it as E at bounds[0]. The
    # half-shell difference (0.19 pc of density) is far below the map's resolution.
    if abs(inner_pc - bounds[0]) > bounds[1] - bounds[0]:
        raise ValueError(f"inner integral to {inner_pc} pc, first boundary {bounds[0]} pc")
    density *= np.diff(bounds).astype(np.float32)[:, None]
    np.cumsum(density, axis=0, out=density)
    density += inner
    cum = np.vstack([inner[None, :], density])
    return DustMap(nside, nest, bounds, cum, str(path))


def integrated_e(dm, l_deg, b_deg, dist_pc):
    """E (Zhang+2023 units) from the Sun to each (l, b, d); returns (e, flag)."""
    import astropy.units as u
    from astropy_healpix import bilinear_interpolation_weights

    l_deg, b_deg = np.asarray(l_deg, np.float64), np.asarray(b_deg, np.float64)
    dist = np.asarray(dist_pc, np.float64)
    idx, w = bilinear_interpolation_weights(l_deg * u.deg, b_deg * u.deg, dm.nside,
                                            order="nested" if dm.nest else "ring")
    bounds = dm.bounds
    d = np.clip(dist, bounds[0], bounds[-1])
    j = np.clip(np.searchsorted(bounds, d, side="right") - 1, 0, len(bounds) - 2)
    t = (d - bounds[j]) / (bounds[j + 1] - bounds[j])
    e_lo = (dm.cum[j[None, :], idx] * w).sum(axis=0)
    e_hi = (dm.cum[j[None, :] + 1, idx] * w).sum(axis=0)
    e = (1 - t) * e_lo + t * e_hi
    inside = dist < bounds[0]
    e = np.where(inside, e * dist / bounds[0], e)
    flag = np.where(inside, FLAG_INNER, np.where(dist > bounds[-1], FLAG_BEYOND, FLAG_MAP))
    return e, flag.astype(object)


def _planck(lam_nm, teff):
    h, c, k = 6.62607015e-34, 2.99792458e8, 1.380649e-23
    lam = lam_nm[None, :] * 1e-9
    return 1.0 / lam ** 5 / np.expm1(h * c / (lam * k * np.asarray(teff)[:, None]))


def extinction_curve(lam_nm):
    """R(lambda) of Zhang+2023 (mag per unit E); linear extrapolation below 392 nm."""
    lam_r, r = _curve()
    slope = (r[1] - r[0]) / (lam_r[1] - lam_r[0])
    lam_nm = np.asarray(lam_nm, np.float64)
    return np.where(lam_nm < lam_r[0], r[0] + slope * (lam_nm - lam_r[0]),
                    np.interp(lam_nm, lam_r, r))


@lru_cache(maxsize=1)
def _curve():
    c = np.loadtxt(_DATA / CURVE_FILE, skiprows=1)
    return c[:, 0], c[:, 1]


@lru_cache(maxsize=1)
def band_table():
    """{band: A_band on (_TEFF_GRID, _E_GRID)} in mag."""
    out = {}
    for band, fname in PASSBAND_FILES.items():
        p = np.loadtxt(_DATA / fname)
        lam, trans = p[:, 0] / 10.0, p[:, 1]                 # Angstrom -> nm
        w = _planck(lam, _TEFF_GRID) * trans * lam            # (nT, nlam) photon counts
        att = 10 ** (-0.4 * _E_GRID[:, None] * extinction_curve(lam)[None, :])  # (nE, nlam)
        num = np.trapezoid(w[:, None, :] * att[None, :, :], lam, axis=-1)
        out[band] = -2.5 * np.log10(num / np.trapezoid(w, lam, axis=-1)[:, None])
    return out


def band_extinction(e, teff):
    """{"G", "BP", "RP"}: extinction in mag for E `e` and temperature `teff` (K)."""
    e = np.clip(np.asarray(e, np.float64), _E_GRID[0], _E_GRID[-1])
    lt = np.log(np.clip(np.asarray(teff, np.float64), _TEFF_GRID[0], _TEFF_GRID[-1]))
    lg = np.log(_TEFF_GRID)
    i = np.clip(np.searchsorted(lg, lt, side="right") - 1, 0, len(lg) - 2)
    k = np.clip(np.searchsorted(_E_GRID, e, side="right") - 1, 0, len(_E_GRID) - 2)
    u_ = (lt - lg[i]) / (lg[i + 1] - lg[i])
    v_ = (e - _E_GRID[k]) / (_E_GRID[k + 1] - _E_GRID[k])
    out = {}
    for band, tab in band_table().items():
        out[band] = ((1 - u_) * (1 - v_) * tab[i, k] + u_ * (1 - v_) * tab[i + 1, k]
                     + (1 - u_) * v_ * tab[i, k + 1] + u_ * v_ * tab[i + 1, k + 1])
    return out


def deredden(bp_rp, e):
    """(a_g, e_bp_rp, bp_rp0) for observed BP-RP and E; Teff from the dereddened colour.

    Rows without a colour get the coefficients of DEFAULT_TEFF and a NaN bp_rp0."""
    bp_rp = np.asarray(bp_rp, np.float64)
    known = np.isfinite(bp_rp)
    bp_rp0 = bp_rp.copy()
    for _ in range(DEREDDEN_MAX_ITER):
        teff = np.where(known, teff_from_bprp(np.where(known, bp_rp0, 0.0)), DEFAULT_TEFF)
        a = band_extinction(e, teff)
        ebr = a["BP"] - a["RP"]
        step = np.abs(bp_rp - ebr - bp_rp0)
        bp_rp0 = bp_rp - ebr
        if not (step[known] > DEREDDEN_TOL).any():
            break
    return a["G"], ebr, bp_rp0


def add_extinction(df, dm):
    """Set dust_e, a_g, e_bp_rp, bp_rp0, abs_g0, dust_flag on `df` (dm None -> no map)."""
    n = len(df)
    if dm is None:
        for c in ("dust_e", "a_g", "e_bp_rp", "bp_rp0", "abs_g0"):
            df[c] = np.full(n, np.nan)
        df["dust_flag"] = FLAG_NONE
        return df
    e, flag = integrated_e(dm, df["l"].to_numpy(), df["b"].to_numpy(),
                           df["dist_pc"].to_numpy())
    a_g, ebr, bp_rp0 = deredden(df["bp_rp"].to_numpy(dtype=np.float64, na_value=np.nan), e)
    df["dust_e"], df["a_g"], df["e_bp_rp"], df["bp_rp0"] = e, a_g, ebr, bp_rp0
    df["abs_g0"] = df["abs_g"].to_numpy(dtype=np.float64, na_value=np.nan) - a_g
    df["dust_flag"] = flag
    return df


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def provenance(dm):
    """Manifest record of the dust step (map file, curve, passbands, method)."""
    if dm is None:
        return {"map": None}
    return {
        "map": {"file": os.path.basename(dm.path), "doi": EDENHOFER_DOI,
                "published_md5": EDENHOFER_MD5, "bytes": os.path.getsize(dm.path),
                "nside": dm.nside, "shells": len(dm.bounds) - 1,
                "r_min_pc": float(dm.bounds[0]), "r_max_pc": float(dm.bounds[-1])},
        "statistic": "posterior mean density, integrated on shell boundaries",
        "interpolation": "bilinear HEALPix (astropy-healpix), linear in distance; "
                         "inner: E(r_min) * d / r_min; beyond r_max: E(r_max)",
        "extinction_curve": {"file": CURVE_FILE, "doi": "10.5281/zenodo.7811871",
                             "sha256": _sha256(_DATA / CURVE_FILE)},
        "passbands": {b: {"file": f, "sha256": _sha256(_DATA / f),
                          "svo_id": _SVO_IDS[b]}
                      for b, f in PASSBAND_FILES.items()},
        "band_weight": "Planck(Teff) * T(lambda) * lambda",
        "teff": "teff_from_bprp(bp_rp0), iterated", "tolerance_mag": DEREDDEN_TOL,
        "max_iterations": DEREDDEN_MAX_ITER,
        "default_teff_k": DEFAULT_TEFF,
    }

"""Per-star display colour: BP-RP -> temperature -> true-colour sRGB.

Two independent steps:
  * teff_from_bprp: an approximate, monotonic colour->Teff interpolation used
    ONLY to pick a display colour (not science).
  * teff_to_rgb / build_rgb_table: Planck blackbody -> CIE 1931 -> sRGB (D65),
    normalised to pure hue at full brightness.
"""
import numpy as np

# ---------------------------------------------------------------------------
# Colour (BP-RP) -> effective temperature, for assigning a display colour.
# Monotonic interpolation across the whole range; anchors approximate.
# ---------------------------------------------------------------------------
_BPRP_ANCHORS = np.array([-0.5, -0.3, 0.0, 0.3, 0.46, 0.6, 0.82, 0.98,
                          1.2, 1.45, 1.84, 2.25, 2.6, 2.95, 3.4, 3.7, 4.1, 4.5])
_TEFF_ANCHORS = np.array([30000, 15000, 10000, 8000, 7200, 6500, 5772, 5280,
                          4900, 4410, 3870, 3550, 3410, 3190, 3030, 2860, 2700, 2600])

def teff_from_bprp(bprp):
    """Approximate Teff (K) from BP-RP, for colouring only. np.interp clamps
    at the ends, so out-of-range colours saturate rather than diverge."""
    return np.interp(bprp, _BPRP_ANCHORS, _TEFF_ANCHORS)


# ---------------------------------------------------------------------------
# Blackbody temperature -> sRGB  (Planck -> CIE 1931 -> sRGB, D65)
# CIE colour-matching functions: Wyman, Sloan & Shirley (2013) analytic fit.
# ---------------------------------------------------------------------------
def _pgauss(x, mu, t1, t2):
    t = (x - mu) * np.where(x < mu, t1, t2)
    return np.exp(-0.5 * t * t)

def _cie_xyz_bar(lam):
    x = (1.056*_pgauss(lam,599.8,0.0264,0.0323)
         + 0.362*_pgauss(lam,442.0,0.0624,0.0374)
         - 0.065*_pgauss(lam,501.1,0.0490,0.0382))
    y = (0.821*_pgauss(lam,568.8,0.0213,0.0247)
         + 0.286*_pgauss(lam,530.9,0.0613,0.0322))
    z = (1.217*_pgauss(lam,437.0,0.0845,0.0278)
         + 0.681*_pgauss(lam,459.0,0.0385,0.0725))
    return x, y, z

_LAM = np.arange(380.0, 781.0, 1.0)             # nm
_XB, _YB, _ZB = _cie_xyz_bar(_LAM)
_H, _C, _K = 6.626e-34, 3.0e8, 1.381e-23

def _planck(T):
    l = _LAM * 1e-9
    return (1.0 / l**5) / (np.exp(_H*_C / (l*_K*T)) - 1.0)

def teff_to_rgb(T):
    """Single temperature (K) -> (r,g,b) ints 0-255, normalised to pure hue."""
    I = _planck(T)
    X, Y, Z = np.sum(I*_XB), np.sum(I*_YB), np.sum(I*_ZB)
    s = X + Y + Z
    X, Y, Z = X/s, Y/s, Z/s
    r =  3.2406*X - 1.5372*Y - 0.4986*Z
    g = -0.9689*X + 1.8758*Y + 0.0415*Z
    b =  0.0557*X - 0.2040*Y + 1.0570*Z
    rgb = np.clip([r, g, b], 0, None)
    rgb = rgb / (rgb.max() or 1.0)
    gamma = np.where(rgb > 0.0031308, 1.055*rgb**(1/2.4) - 0.055, 12.92*rgb)
    return tuple(int(round(255*v)) for v in gamma)

def build_rgb_table(teff_array):
    """Vectorised-ish: compute RGB on a temperature grid, map each star to it."""
    finite = teff_array[np.isfinite(teff_array)]
    grid = np.unique(np.clip(np.round(finite / 50) * 50, 1500, 40000))
    lut = {T: teff_to_rgb(T) for T in grid}
    keys = np.array(list(lut.keys()))
    out = []
    for T in teff_array:
        if not np.isfinite(T):
            out.append((128, 128, 128)); continue
        out.append(lut[keys[np.argmin(np.abs(keys - T))]])
    rgb = np.array(out)
    hexes = ['#%02X%02X%02X' % tuple(c) for c in rgb]
    return rgb[:, 0], rgb[:, 1], rgb[:, 2], hexes

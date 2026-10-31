"""Parallax zero-point correction (Mapa 1.0, milestone M3; plan v4 S2 D5, D-005).

Gaia DR3 parallaxes carry a zero-point offset that depends on magnitude, colour and
ecliptic latitude (Lindegren et al. 2021, A&A 649, A4). The official package
`gaiadr3-zeropoint` evaluates it; this module is the only place it is called, so
rows (`corrected_parallax`) and any later population model share one policy:

- convention: corrected parallax = parallax - zp (zp is `parallax_zp_mas`);
- only 5p/6p solutions (`astrometric_params_solved` 31/95) with finite inputs go
  to the package, which raises for a whole batch otherwise;
- outside the package's validity range (6 < G < 21, 1.1 < nu_eff < 1.9 for 5p,
  1.24 < pseudocolour < 1.72 for 6p) inputs are clamped to just *inside* the range
  (the package treats the bounds themselves as outside and would return NaN) and
  the row is flagged `lindegren2021_clamped`. This is our policy, not the package's:
  the result is bounded and predictable, where the package would extrapolate in
  colour;
- a 5p/6p row with a missing input gets the global offset `global_fallback`
  (-0.017 mas, as Bailer-Jones et al. 2021 use for sources without G);
- any other solution type gets no zero-point (`none`, zp = NaN).

The package is a plain numpy module; it is imported lazily all the same, so the
rest of the package imports without it.
"""
import numpy as np

ZP_METHOD = "lindegren2021_clamped"
GLOBAL_FALLBACK_ZP_MAS = -0.017
G_RANGE = (6.0, 21.0)
NU_EFF_RANGE = (1.1, 1.9)            # 1/micron, 5p solutions
PSEUDOCOLOUR_RANGE = (1.24, 1.72)    # 1/micron, 6p solutions
EPS_G = 1e-3                         # mag
EPS_COLOUR = 1e-4                    # 1/micron
SOLVED_5P, SOLVED_6P = 31, 95

_tables_loaded = False


def _get_zpt():
    global _tables_loaded
    from zero_point import zpt
    if not _tables_loaded:
        zpt.load_tables()
        _tables_loaded = True
    return zpt.get_zpt


def _clamp(x, lo, hi, eps):
    """Clip into the open interval's interior; also return which values moved."""
    y = np.clip(x, lo + eps, hi - eps)
    return y, y != x


def zero_point(g, nu_eff, pseudocolour, ecl_lat, solved):
    """Per-row zero-point (mas, float64) and its origin label (object array)."""
    g, nu_eff, pseudocolour, ecl_lat = (np.asarray(a, dtype=np.float64) for a in
                                        (g, nu_eff, pseudocolour, ecl_lat))
    solved = np.asarray(solved)
    n = len(g)
    zp = np.full(n, np.nan)
    origin = np.full(n, "none", dtype=object)

    is5, is6 = solved == SOLVED_5P, solved == SOLVED_6P
    colour = np.where(is5, nu_eff, pseudocolour)
    has_inputs = np.isfinite(g) & np.isfinite(ecl_lat) & np.isfinite(colour)
    fallback = (is5 | is6) & ~has_inputs
    zp[fallback], origin[fallback] = GLOBAL_FALLBACK_ZP_MAS, "global_fallback"

    use = (is5 | is6) & has_inputs
    if use.any():
        gc, g_moved = _clamp(g[use], *G_RANGE, EPS_G)
        c_lo = np.where(is5[use], NU_EFF_RANGE[0], PSEUDOCOLOUR_RANGE[0])
        c_hi = np.where(is5[use], NU_EFF_RANGE[1], PSEUDOCOLOUR_RANGE[1])
        cc, c_moved = _clamp(colour[use], c_lo, c_hi, EPS_COLOUR)
        # Each solution type reads only its own colour; the other is a dummy in range.
        nu_in = np.where(is5[use], cc, 1.5)
        pc_in = np.where(is6[use], cc, 1.5)
        zp[use] = _get_zpt()(gc, nu_in, pc_in, ecl_lat[use], solved[use].astype(float),
                             _warnings=False)
        origin[use] = np.where(g_moved | c_moved, "lindegren2021_clamped", "lindegren2021")
        if np.isnan(zp[use]).any():                  # cannot happen after clamping
            raise RuntimeError("zero-point package returned NaN for clamped inputs")
    return zp, origin


def corrected_parallax(parallax, parallax_error, g, nu_eff, pseudocolour, ecl_lat,
                       solved, *, error_inflation=1.0):
    """(varpi_c, sigma_c, zp, zp_origin) for Gaia rows; varpi_c = parallax - zp.

    Rows without a zero-point (`none`) get varpi_c = NaN: their parallax is not
    usable. `error_inflation` scales parallax_error (1.0 in Mapa 1.0, plan v4 S2 D6).
    """
    zp, origin = zero_point(g, nu_eff, pseudocolour, ecl_lat, solved)
    varpi_c = np.asarray(parallax, dtype=np.float64) - zp
    sigma_c = np.asarray(parallax_error, dtype=np.float64) * float(error_inflation)
    return varpi_c, sigma_c, zp, origin


def provenance(error_inflation=1.0):
    """What a manifest needs to reproduce the correction."""
    from importlib.metadata import version
    return {"method": ZP_METHOD, "package": "gaiadr3-zeropoint",
            "package_version": version("gaiadr3-zeropoint"),
            "convention": "parallax_corrected = parallax - parallax_zp_mas",
            "clamp": {"g": list(G_RANGE), "nu_eff": list(NU_EFF_RANGE),
                      "pseudocolour": list(PSEUDOCOLOUR_RANGE),
                      "eps_g": EPS_G, "eps_colour": EPS_COLOUR},
            "global_fallback_mas": GLOBAL_FALLBACK_ZP_MAS,
            "error_inflation": float(error_inflation)}

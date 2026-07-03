"""Empirical main-sequence mass estimate from absolute G magnitude, plus the
lower-mass filters (both the exact post-hoc cut and the coarse M_G bound used to
pre-filter the Gaia query)."""
import numpy as np

# M_G -> mass, anchored on a Pecaut & Mamajek-style main sequence (M_G ascending).
# Approximate. Valid only for single main-sequence stars; blank otherwise.
_MASS_MG   = np.array([1.0, 1.4, 2.2, 3.5, 4.67, 5.5, 6.5, 7.5, 8.2,
                       9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5])
_MASS_MSUN = np.array([2.20, 1.90, 1.45, 1.15, 1.00, 0.85, 0.70, 0.60, 0.56,
                       0.45, 0.36, 0.25, 0.18, 0.14, 0.11, 0.095, 0.085])


def mg_upper_bound_for_mass(min_mass, margin=0.5):
    """Faint-end absolute-G limit corresponding to a lower mass bound.

    Inverts the same MS relation `estimate_mass` uses: brighter (smaller M_G) =
    more massive, so a lower bound on mass becomes an UPPER bound on M_G. Used to
    pre-filter the Gaia query server-side. A margin is added so the coarse server
    cut can never remove a star the exact client cut (`apply_min_mass`) keeps.
    """
    # _MASS_MSUN descends as _MASS_MG ascends; reverse both for np.interp.
    return float(np.interp(min_mass, _MASS_MSUN[::-1], _MASS_MG[::-1])) + margin

def estimate_mass(abs_g, bp_rp):
    """Approximate stellar mass (M_sun) from absolute Gaia G magnitude.

    Returns NaN (left blank) where the estimate would be unreliable:
      - white dwarfs / below-main-sequence objects (CMD cut),
      - stars brighter or fainter than the calibrated M_G range
        (likely giants/subgiants at the bright end, beyond the MS bottom
        at the faint end).
    Assumes a single main-sequence star; over-luminous unresolved binaries
    (largely removed by the ruwe < 1.4 filter) will read slightly high.
    """
    abs_g = np.asarray(abs_g, float)
    bp_rp = np.asarray(bp_rp, float)
    mass = np.interp(abs_g, _MASS_MG, _MASS_MSUN)
    in_range = (abs_g >= _MASS_MG[0]) & (abs_g <= _MASS_MG[-1])
    is_wd = abs_g > 2.7 * bp_rp + 8.0        # below the main sequence
    good = in_range & ~is_wd & np.isfinite(abs_g) & np.isfinite(bp_rp)
    return np.where(good, mass, np.nan)


def apply_min_mass(df, min_mass):
    """Keep only stars with an estimated mass >= min_mass (solar masses).

    Rows without a mass estimate (white dwarfs, giants, and anything outside the
    calibrated main-sequence range, where `mass_est` is NaN) are dropped: an
    unknown mass cannot be shown to clear the threshold. No-op when min_mass is
    None or the frame has no `mass_est` column.
    """
    if min_mass is None or "mass_est" not in df.columns:
        return df
    before = len(df)
    df = df[df["mass_est"] >= min_mass].reset_index(drop=True)
    print(f"  min-mass {min_mass} Msun: kept {len(df)} of {before} rows "
          f"(dropped below-threshold and unknown-mass stars)")
    return df

"""Distances from corrected parallaxes (Mapa 1.0, milestone M3; D-020).

Mapa 1.0 inverts the zero-point-corrected parallax for every row. If the measured
parallax is Gaussian around the true one with error sigma, the distance 1000/varpi
has its 15.87 / 50 / 84.13 % points at 1000/(varpi + sigma), 1000/varpi and
1000/(varpi - sigma) (the map is monotonic), which is what `r_lo_pc`, `dist_pc`
and `r_hi_pc` store. Those are the quantiles of the *measurement*, not a Bayesian
posterior; for varpi/sigma > 5 the two hardly differ, below that the estimate is
biased and the row is flagged `low_snr` (0.9 % of the G < 15 sample). The EDSD
prior of plan v4 (S2 D3) stays for later.
"""
import numpy as np

DIST_ORIGIN = "parallax_inversion"
LOW_SNR = 5.0       # varpi/sigma at or below this -> dist_flag "low_snr"


def inversion_distances(varpi, sigma):
    """(r_lo, r_med, r_hi, dist_flag) in pc from parallax and error in mas.

    r_med is NaN where varpi <= 0 (callers must drop or reject those rows); r_hi is
    NaN where varpi - sigma <= 0 (the 84 % point is unbounded); r_lo and r_hi are
    NaN where sigma is unknown, and the flag is then "no_error".
    """
    varpi = np.asarray(varpi, dtype=np.float64)
    sigma = np.asarray(sigma, dtype=np.float64)
    with np.errstate(divide="ignore", invalid="ignore"):
        r_med = np.where(varpi > 0, 1000.0 / varpi, np.nan)
        r_lo = np.where(varpi > 0, 1000.0 / (varpi + sigma), np.nan)
        upper = varpi - sigma
        r_hi = np.where(upper > 0, 1000.0 / upper, np.nan)
        snr = varpi / sigma
    flag = np.where(~np.isfinite(sigma), "no_error",
                    np.where(snr > LOW_SNR, "ok", "low_snr")).astype(object)
    return r_lo, r_med, r_hi, flag


def provenance():
    return {"estimator": DIST_ORIGIN, "quantiles": [0.1587, 0.5, 0.8413],
            "low_snr_threshold": LOW_SNR,
            "note": "quantiles of 1000/parallax under a Gaussian parallax error; "
                    "dist_pc is the median"}

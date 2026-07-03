"""Official Gaia EDR3 photometric transformations (Table 5.7, Carrasco &
Bellazzini). Each is a polynomial in a colour; outside its published validity
range it returns NaN rather than extrapolating."""
import numpy as np


def _poly(c, x):
    return sum(k * x**i for i, k in enumerate(c))

def g_minus_v_from_bv(bv):       # Hipparcos V -> Gaia G.   valid -0.4<B-V<3.3
    return np.where((bv > -0.4) & (bv < 3.3),
                    _poly([-0.04749, -0.0124, -0.2901, 0.02008], bv), np.nan)

def bprp_from_vi(vi):            # Hipparcos colour -> BP-RP. valid -0.4<V-I<5.0
    return np.where((vi > -0.4) & (vi < 5.0),
                    _poly([-0.03298, 1.259, -0.1279, 0.01631], vi), np.nan)

def g_minus_v_from_bprp(bprp):   # reverse: Johnson V for Gaia stars. -0.5<BP-RP<5
    return np.where((bprp > -0.5) & (bprp < 5.0),
                    _poly([-0.02704, 0.01424, -0.2156, 0.01426], bprp), np.nan)

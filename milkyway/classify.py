"""Coarse evolutionary classification and the spurious-parallax data-quality
flag. Both lean on the same main-sequence colour-magnitude reference
(`_MS_BPRP` / `_MS_ABSG`), so they live together."""
import re

import numpy as np
import pandas as pd

# ===========================================================================
# Stellar classification (evolutionary / luminosity category)
# ===========================================================================
# A coarse category per star: White dwarf, Brown dwarf, Supergiant, Red giant,
# Giant, Subgiant, Main sequence, Unknown. Two sources, in priority order:
#   1. SIMBAD MK spectral type (`sp_type`) when present -> authoritative
#      luminosity class (V dwarf, IV subgiant, II/III giant, I supergiant,
#      leading 'D' white dwarf, L/T/Y brown dwarf).
#   2. Position in the Gaia colour-magnitude diagram (abs_g vs bp_rp) as a
#      fallback for the many faint stars SIMBAD has not typed.
# The HR fallback uses approximate empirical cuts (the same below-main-sequence
# white-dwarf locus as estimate_mass; a Pecaut & Mamajek-style MS reference). It
# is a coarse label, not spectroscopy.

# Matches the MK luminosity class within a spectral-type string, longest first.
_LUM_RE = re.compile(r"(Ia0|Iab|Ia|Ib|IV|III|II|VI|V|I)")

def classify_from_sptype(sp):
    """Coarse category from a SIMBAD MK spectral-type string, or None when the
    string is missing or carries no usable class."""
    if sp is None:
        return None
    sp = str(sp).strip()
    if sp == "" or sp.lower() in ("nan", "none", "--"):
        return None
    # White dwarfs: 'DA','DB','DC','DO','DQ','DZ','DX', or a bare leading 'D'.
    if re.match(r"^D[ABCOQZX]?", sp):
        return "White dwarf"
    # Hot subdwarfs ('sdB', 'sdO', 'esdK...', 'usd...').
    if sp.startswith(("sd", "esd", "usd")):
        return "Subdwarf"
    # Ultracool / substellar spectral classes.
    if sp[0] in "LTY":
        return "Brown dwarf"
    letter = sp[0] if sp[0] in "OBAFGKM" else None
    cool = letter in ("K", "M")
    m = _LUM_RE.search(sp)
    lum = m.group(1) if m else None
    if lum in ("Ia0", "Iab", "Ia", "Ib", "I"):
        return "Supergiant"
    if lum in ("II", "III"):
        return "Red giant" if cool else "Giant"
    if lum == "IV":
        return "Subgiant"
    if lum in ("V", "VI"):
        return "Main sequence"
    # A bare spectral letter with no luminosity class -> assume dwarf.
    if letter is not None:
        return "Main sequence"
    return None


# Main-sequence reference M_G as a function of BP-RP, for the HR fallback.
# Fitted as the median M_G per colour bin of this very sample (which is ~99%
# local main sequence + white dwarfs, so the median tracks the MS ridge and is
# robust to the handful of giants). Pinned values land on the Sun (BP-RP 0.82 ->
# M_G ~4.7) and the reddest dwarfs (Proxima BP-RP 3.80 -> M_G 13.41), so late-M
# red dwarfs are not mistaken for giants. Re-derive if the selection changes.
_MS_BPRP = np.array([-0.25, 0.15, 0.45, 0.725, 0.975, 1.25, 1.55,
                     1.85, 2.15, 2.45, 2.8, 3.25, 3.75, 4.3])
_MS_ABSG = np.array([0.45, 1.54, 2.75, 4.19, 5.46, 6.38, 7.26,
                     8.14, 9.0, 9.97, 11.09, 12.3, 13.41, 14.39])

def classify_from_hr(abs_g, bp_rp, teff_color=np.nan):
    """Coarse category from colour-magnitude position (scalar inputs).

    Note: there are no true supergiants within ~20 pc, so 'Supergiant' is gated
    on absolute luminosity (M_G < -3.5) rather than the over-luminosity delta,
    which would otherwise mislabel ordinary red giants (Arcturus, Aldebaran).
    """
    if not (np.isfinite(abs_g) and np.isfinite(bp_rp)):
        return "Unknown"
    # Substellar: extremely cool display temperature.
    if np.isfinite(teff_color) and teff_color < 2300:
        return "Brown dwarf"
    # White dwarfs sit well below the main sequence (faint for their colour);
    # same CMD cut estimate_mass() uses to exclude them.
    if bp_rp < 1.8 and abs_g > 2.7 * bp_rp + 8.0:
        return "White dwarf"
    if abs_g < -3.5:
        return "Supergiant"
    delta = abs_g - np.interp(bp_rp, _MS_BPRP, _MS_ABSG)   # -ve = above MS
    cool = bp_rp > 1.0
    # Equal-mass unresolved binaries sit ~0.75 mag above the MS, so the subgiant
    # threshold is set below that to avoid sweeping them up.
    if delta < -2.5:
        return "Red giant" if cool else "Giant"
    if delta < -1.3:
        return "Subgiant"
    return "Main sequence"

def classify_stars(df):
    """Per-row evolutionary category for a merged catalogue: SIMBAD spectral
    type first, colour-magnitude position as fallback. Returns a list aligned
    with df rows."""
    has_sp = "sp_type" in df.columns
    abs_g = df["abs_g"].to_numpy(float)
    bp_rp = df["bp_rp"].to_numpy(float)
    teff = (df["teff_color"].to_numpy(float)
            if "teff_color" in df.columns else np.full(len(df), np.nan))
    out = []
    for i in range(len(df)):
        cat = classify_from_sptype(df["sp_type"].iloc[i]) if has_sp else None
        if cat is None:
            cat = classify_from_hr(abs_g[i], bp_rp[i], teff[i])
        out.append(cat)
    return out


# ===========================================================================
# Spurious-parallax flag  (Gaia DR3 crowded-field contamination)
# ===========================================================================
# Toward crowded, dust-reddened directions (the Galactic centre and plane), Gaia
# DR3 produces correlated spurious astrometric solutions: distant background
# stars are assigned an inflated parallax and masquerade as faint nearby red
# dwarfs. The parallax_over_error > 10 and ruwe < 1.4 cuts do NOT fully remove
# them in dense fields (a documented DR3 limitation). They betray themselves in
# the colour-magnitude diagram -- their colour implies a bright M_G, but the
# (wrong) parallax drops them many magnitudes BELOW the main sequence, a
# "forbidden zone" no real single star occupies -- while their apparent G sits
# near Gaia's faint limit (they are really kiloparsecs away). See Dataset.md
# section "Spurious parallaxes" for the empirical diagnosis.
SPURIOUS_BELOW_MS_MAG = 4.0    # mag below the MS ridge that counts as unphysical
SPURIOUS_FAINT_G      = 19.0   # apparent G near Gaia's limit -> really distant
SPURIOUS_NOCOLOUR_MG  = 15.0   # colourless + this faint absolute -> crowding

def flag_spurious_parallax(df):
    """Boolean per-row flag, True where the Gaia parallax is likely spurious.

    Conservative by design: it targets the crowded-field contamination without
    touching genuine nearby white/brown dwarfs (which are apparently bright,
    g < ~18, because they really are close). Two signatures, both requiring the
    star to be apparently faint (near Gaia's limit, i.e. really distant):
      1. has colour, is red (BP-RP > 1), yet sits > SPURIOUS_BELOW_MS_MAG below
         the main-sequence ridge -- colour and absolute magnitude are grossly
         inconsistent, which only a wrong parallax explains;
      2. has no BP-RP at all (crowding killed the BP/RP photometry) yet claims a
         very faint absolute magnitude on nominally good astrometry.
    """
    absg = df["abs_g"].to_numpy(float)
    bprp = df["bp_rp"].to_numpy(float)
    g    = df["g_mag"].to_numpy(float)
    delta = absg - np.interp(bprp, _MS_BPRP, _MS_ABSG)      # +ve = below the MS
    faint = g > SPURIOUS_FAINT_G
    below_ms  = np.isfinite(bprp) & (bprp > 1.0) & (delta > SPURIOUS_BELOW_MS_MAG) & faint
    no_colour = ~np.isfinite(bprp) & (absg > SPURIOUS_NOCOLOUR_MG) & faint
    return pd.Series(below_ms | no_colour, index=df.index)

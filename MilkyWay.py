"""
Complete nearby-star pipeline:
  Gaia DR3 + Hipparcos  ->  merged, de-duplicated, unified Gaia photometry,
  + true-colour RGB per star  + UVW Galactic space velocities.

Stages
  1. Query nearest Gaia stars and nearby bright Hipparcos stars (same TAP service).
  2. Epoch-propagate Hipparcos (J1991.25 -> J2016.0) and cross-match to drop
     duplicates; Hipparcos stars missing from Gaia are added as gap-fillers.
  3. Transform Hipparcos Johnson V / B-V / V-I onto the Gaia G / BP-RP system
     using the official EDR3 relations (Carrasco & Bellazzini, Table 5.7).
  4. Assign each star an sRGB colour from its temperature (blackbody -> CIE -> sRGB).
  5. Compute UVW Galactic space velocities (needs radial velocity).
  6. Attach proper names / SIMBAD designations (optional; needs network).

Requirements:  pip install astroquery astropy numpy pandas matplotlib adjustText

Photometric-transform refs:
  - G-V, GBP-GRP, etc.:  Gaia EDR3 docs Table 5.7 (Carrasco & Bellazzini).
  - BP-RP -> Teff (hot end): Jordi et al. 2010, valid BP-RP < 1.5 only.
  - Colour-temperature anchors below ~4500 K: Pecaut & Mamajek-style dwarf
    sequence (APPROXIMATE; used only to assign a display colour, not science).
"""

import re

import numpy as np
import pandas as pd

EPOCH_HIP  = 1991.25
EPOCH_GAIA = 2016.0
MAX_DIST_PC = 400.0                          # search radius
MIN_PARALLAX_MAS = 100.0 / MAX_DIST_PC     # 30 pc -> 33.33 mas
MATCH_RADIUS_ARCSEC = 2.0

# Solar peculiar motion (Schonrich, Binney & Dehnen 2010) for optional LSR shift
SOLAR_UVW = np.array([11.1, 12.24, 7.25])   # km/s

# Well-known nearby stars to label on the H-R diagram. Matched case-insensitively
# as substrings of proper_name, so "Procyon" also catches "Procyon A".
FAMOUS_STARS = [
    "Sirius", "Procyon", "Proxima Centauri", "Rigil Kentaurus", "Toliman",
    "Barnard", "Vega", "Altair", "Fomalhaut", "Aldebaran", "Arcturus",
    "Capella", "Pollux", "Castor", "Kapteyn", "Teegarden",
]


# ===========================================================================
# Official Gaia EDR3 photometric transformations (Table 5.7)
# ===========================================================================
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


# ===========================================================================
# Colour (BP-RP) -> effective temperature, for assigning a display colour.
# Monotonic interpolation across the whole range; anchors approximate.
# ===========================================================================
_BPRP_ANCHORS = np.array([-0.5, -0.3, 0.0, 0.3, 0.46, 0.6, 0.82, 0.98,
                          1.2, 1.45, 1.84, 2.25, 2.6, 2.95, 3.4, 3.7, 4.1, 4.5])
_TEFF_ANCHORS = np.array([30000, 15000, 10000, 8000, 7200, 6500, 5772, 5280,
                          4900, 4410, 3870, 3550, 3410, 3190, 3030, 2860, 2700, 2600])

def teff_from_bprp(bprp):
    """Approximate Teff (K) from BP-RP, for colouring only. np.interp clamps
    at the ends, so out-of-range colours saturate rather than diverge."""
    return np.interp(bprp, _BPRP_ANCHORS, _TEFF_ANCHORS)


# ===========================================================================
# Blackbody temperature -> sRGB  (Planck -> CIE 1931 -> sRGB, D65)
# CIE colour-matching functions: Wyman, Sloan & Shirley (2013) analytic fit.
# ===========================================================================
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


# ===========================================================================
# Queries  (imported lazily so the colour math can be tested without astroquery)
# ===========================================================================
def query_gaia(limit=None):
    from astroquery.gaia import Gaia
    top = f"TOP {limit}" if limit else ""        # no limit by default
    adql = f"""
    SELECT {top}
      gs.source_id, gs.ra, gs.dec, gs.l, gs.b, gs.parallax, gs.parallax_over_error,
      gs.pmra, gs.pmdec, gs.radial_velocity,
      gs.phot_g_mean_mag, gs.bp_rp, gs.teff_gspphot, gs.ruwe,
      ap.mass_flame, ap.age_flame
    FROM gaiadr3.gaia_source AS gs
    LEFT OUTER JOIN gaiadr3.astrophysical_parameters AS ap
      ON gs.source_id = ap.source_id
    WHERE gs.parallax > {MIN_PARALLAX_MAS}
      AND gs.parallax_over_error > 10
      AND gs.ruwe < 1.4
    ORDER BY gs.parallax DESC
    """
    return Gaia.launch_job_async(adql).get_results().to_pandas()

def query_hipparcos():
    from astroquery.gaia import Gaia
    adql = f"""
    SELECT hip, ra, de, plx, e_plx, pmra, pmde, vmag, b_v, v_i
    FROM public.hipparcos
    WHERE plx > {MIN_PARALLAX_MAS} AND plx / e_plx > 10
    ORDER BY plx DESC
    """
    return Gaia.launch_job_async(adql).get_results().to_pandas()


# ===========================================================================
# Epoch propagation, cross-match, UVW  (astropy)
# ===========================================================================
def propagate_hipparcos(hip):
    from astropy.coordinates import SkyCoord
    from astropy.time import Time
    import astropy.units as u
    c = SkyCoord(ra=hip["ra"].to_numpy()*u.deg, dec=hip["de"].to_numpy()*u.deg,
                 pm_ra_cosdec=hip["pmra"].to_numpy()*u.mas/u.yr,
                 pm_dec=hip["pmde"].to_numpy()*u.mas/u.yr,
                 distance=(1000.0/hip["plx"].to_numpy())*u.pc,
                 obstime=Time(EPOCH_HIP, format="decimalyear"))
    return c.apply_space_motion(new_obstime=Time(EPOCH_GAIA, format="decimalyear"))

def cross_match(gaia, hip_coord):
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    gcoord = SkyCoord(ra=gaia["ra"].to_numpy()*u.deg, dec=gaia["dec"].to_numpy()*u.deg)
    _, sep2d, _ = hip_coord.match_to_catalog_sky(gcoord)
    return sep2d.arcsec < MATCH_RADIUS_ARCSEC

def compute_uvw(df, to_lsr=False):
    """Galactic UVW (km/s), heliocentric. astropy Galactic axes:
    U toward Galactic centre, V toward rotation, W toward NGP.
    Only computed where radial_velocity is finite; else NaN."""
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    uvw = np.full((len(df), 3), np.nan)
    m = np.isfinite(df["radial_velocity"].to_numpy())
    if m.any():
        s = df[m]
        c = SkyCoord(ra=s["ra"].to_numpy()*u.deg, dec=s["dec"].to_numpy()*u.deg,
                     distance=s["dist_pc"].to_numpy()*u.pc,
                     pm_ra_cosdec=s["pmra"].to_numpy()*u.mas/u.yr,
                     pm_dec=s["pmdec"].to_numpy()*u.mas/u.yr,
                     radial_velocity=s["radial_velocity"].to_numpy()*u.km/u.s,
                     frame="icrs").galactic
        v = c.velocity
        uvw[m, 0] = v.d_x.to(u.km/u.s).value
        uvw[m, 1] = v.d_y.to(u.km/u.s).value
        uvw[m, 2] = v.d_z.to(u.km/u.s).value
        if to_lsr:
            uvw[m] += SOLAR_UVW
    return uvw[:, 0], uvw[:, 1], uvw[:, 2]


# ===========================================================================
# Star names from SIMBAD
# ===========================================================================
def add_simbad_names(df, batch_size=300):
    """Resolve each star_id to its SIMBAD designation and proper name.

    Adds three columns:
      simbad_main_id : SIMBAD's preferred designation (e.g. '* alf CMa')
      proper_name    : IAU / common name if one exists (e.g. 'Sirius'), else NaN
      sp_type        : SIMBAD MK spectral type (e.g. 'A1V', 'M3.5V', 'DA2'),
                       used by classify_stars() for a luminosity category; NaN
                       for stars SIMBAD has not typed.

    Uses a few batched TAP queries instead of one call per star. The star_id
    strings ('Gaia DR3 <id>', 'HIP <n>') are exactly the formats SIMBAD's
    `ident` table indexes, so we can match on them directly.

    Requires astroquery >= 0.4.8 (the SIMBAD TAP interface). For older versions
    the per-star fallback is `Simbad.query_objectids(star_id)`.
    """
    from astroquery.simbad import Simbad

    ids = df["star_id"].tolist()
    main, proper, sptype = {}, {}, {}

    for i in range(0, len(ids), batch_size):
        batch = ids[i:i + batch_size]
        in_list = ", ".join("'" + s.replace("'", "''") + "'" for s in batch)

        # 1) preferred designation + spectral type for each queried id
        q_main = f"""
            SELECT i.id AS query_id, b.main_id AS main_id, b.sp_type AS sp_type
            FROM ident AS i JOIN basic AS b ON i.oidref = b.oid
            WHERE i.id IN ({in_list})
        """
        for row in Simbad.query_tap(q_main):
            qid = str(row["query_id"])
            main[qid] = str(row["main_id"])
            sp = row["sp_type"]
            if sp is not None and str(sp).strip() not in ("", "--"):
                sptype[qid] = str(sp).strip()

        # 2) proper name: any identifier for the same object starting 'NAME '
        q_name = f"""
            SELECT iq.id AS query_id, nm.id AS name_id
            FROM ident AS iq JOIN ident AS nm ON iq.oidref = nm.oidref
            WHERE iq.id IN ({in_list}) AND nm.id LIKE 'NAME %'
        """
        for row in Simbad.query_tap(q_name):
            proper[str(row["query_id"])] = str(row["name_id"]).replace("NAME ", "", 1)

    df["simbad_main_id"] = df["star_id"].map(main)
    df["proper_name"]    = df["star_id"].map(proper)
    df["sp_type"]        = df["star_id"].map(sptype)
    return df


# ===========================================================================
# Galactic coordinates + 3D Cartesian position
# ===========================================================================
def add_galactic_xyz(df):
    """Add galactic longitude/latitude and heliocentric Cartesian position.

    l, b are computed from ICRS ra/dec for every row (consistent across both
    catalogues). XYZ uses the standard frame: X toward the Galactic centre,
    Y toward rotation, Z toward the north Galactic pole; Sun at the origin.
    """
    from astropy.coordinates import SkyCoord
    import astropy.units as u
    gal = SkyCoord(ra=df["ra"].to_numpy()*u.deg,
                   dec=df["dec"].to_numpy()*u.deg, frame="icrs").galactic
    l, b = gal.l.deg, gal.b.deg
    d = df["dist_pc"].to_numpy()
    lr, br = np.radians(l), np.radians(b)
    df["l"], df["b"] = l, b
    df["x_pc"] = d * np.cos(br) * np.cos(lr)
    df["y_pc"] = d * np.cos(br) * np.sin(lr)
    df["z_pc"] = d * np.sin(br)
    return df


# ===========================================================================
# Empirical main-sequence mass estimate from absolute G magnitude
# ===========================================================================
# M_G -> mass, anchored on a Pecaut & Mamajek-style main sequence (M_G ascending).
# Approximate. Valid only for single main-sequence stars; blank otherwise.
_MASS_MG   = np.array([1.0, 1.4, 2.2, 3.5, 4.67, 5.5, 6.5, 7.5, 8.2,
                       9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5])
_MASS_MSUN = np.array([2.20, 1.90, 1.45, 1.15, 1.00, 0.85, 0.70, 0.60, 0.56,
                       0.45, 0.36, 0.25, 0.18, 0.14, 0.11, 0.095, 0.085])

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
# Harmonise to one Gaia-system table
# ===========================================================================
def gaia_to_common(g):
    return pd.DataFrame({
        "star_id": "Gaia DR3 " + g["source_id"].astype(str),
        "ra": g["ra"], "dec": g["dec"], "parallax_mas": g["parallax"],
        "dist_pc": 1000.0/g["parallax"], "pmra": g["pmra"], "pmdec": g["pmdec"],
        "radial_velocity": g["radial_velocity"],
        "g_mag": g["phot_g_mean_mag"], "bp_rp": g["bp_rp"],
        "v_mag": g["phot_g_mean_mag"] - g_minus_v_from_bprp(g["bp_rp"].to_numpy()),
        "abs_g": g["phot_g_mean_mag"] + 5*np.log10(g["parallax"]) - 10,
        "teff_gspphot": g["teff_gspphot"],
        "mass_flame": g["mass_flame"], "age_flame": g["age_flame"],
        "phot_origin": "native_gaia", "source_catalogue": "Gaia",
    })

def hipparcos_to_common(h, coord):
    plx = h["plx"].to_numpy(); v = h["vmag"].to_numpy()
    g_mag = v + g_minus_v_from_bv(h["b_v"].to_numpy())
    return pd.DataFrame({
        "star_id": "HIP " + h["hip"].astype(int).astype(str),
        "ra": coord.ra.deg, "dec": coord.dec.deg, "parallax_mas": plx,
        "dist_pc": 1000.0/plx, "pmra": h["pmra"].to_numpy(), "pmdec": h["pmde"].to_numpy(),
        "radial_velocity": np.nan,
        "g_mag": g_mag, "bp_rp": bprp_from_vi(h["v_i"].to_numpy()), "v_mag": v,
        "abs_g": g_mag + 5*np.log10(plx) - 10, "teff_gspphot": np.nan,
        "mass_flame": np.nan, "age_flame": np.nan,
        "phot_origin": "transformed_from_johnson", "source_catalogue": "Hipparcos",
    })


def build_merged_catalogue(add_names=True):
    print("Querying Gaia ...");      gaia = query_gaia();      print(f"  {len(gaia)} stars")
    print("Querying Hipparcos ...")
    hip = query_hipparcos().dropna(subset=["ra","de","pmra","pmde","plx"]).reset_index(drop=True)
    print(f"  {len(hip)} stars")

    print("Epoch-propagating + cross-matching ...")
    hc = propagate_hipparcos(hip)
    dup = cross_match(gaia, hc)
    print(f"  {int(dup.sum())} duplicates dropped, {len(hip)-int(dup.sum())} gap-fillers added")
    hip_m, hc_m = hip[~dup].reset_index(drop=True), hc[~dup]

    merged = pd.concat([gaia_to_common(gaia), hipparcos_to_common(hip_m, hc_m)],
                       ignore_index=True).sort_values("dist_pc").reset_index(drop=True)

    print("Adding galactic coordinates + 3D position ...")
    merged = add_galactic_xyz(merged)

    print("Assigning display colours ...")
    teff_col = teff_from_bprp(merged["bp_rp"].to_numpy())
    merged["teff_color"] = teff_col
    r, g, b, hexes = build_rgb_table(teff_col)
    merged["rgb_r"], merged["rgb_g"], merged["rgb_b"], merged["rgb_hex"] = r, g, b, hexes

    print("Estimating masses (main-sequence M_G relation) ...")
    merged["mass_est"] = estimate_mass(merged["abs_g"].to_numpy(),
                                       merged["bp_rp"].to_numpy())
    n_mass = int(merged["mass_est"].notna().sum())
    print(f"  {n_mass} of {len(merged)} stars got a mass estimate")

    print("Computing UVW space velocities ...")
    U, V, W = compute_uvw(merged, to_lsr=False)
    merged["U"], merged["V"], merged["W"] = U, V, W

    if add_names:
        print("Resolving names from SIMBAD ...")
        try:
            merged = add_simbad_names(merged)
            n = merged["proper_name"].notna().sum()
            print(f"  {n} stars have a proper name")
        except Exception as e:
            print(f"  SIMBAD step skipped ({e})")
            merged["simbad_main_id"] = pd.NA
            merged["proper_name"] = pd.NA
            merged["sp_type"] = pd.NA

    print("Classifying stars (spectral type + CMD position) ...")
    if "sp_type" not in merged.columns:
        merged["sp_type"] = pd.NA
    merged["star_class"] = classify_stars(merged)
    counts = pd.Series(merged["star_class"]).value_counts()
    print("  " + ", ".join(f"{k}: {v}" for k, v in counts.items()))
    return merged


def _resolve_path(path):
    """Make a relative filename absolute, next to this script, so output always
    lands somewhere predictable regardless of the current working directory."""
    import os
    if not os.path.isabs(path):
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), path)
    return path

def _save(fig, path):
    """Save a figure and report whether it actually reached disk."""
    import os
    fig.savefig(path, dpi=130)
    print(f"Saved {path}" if os.path.exists(path)
          else f"WARNING: figure was not written to {path}")

def _label_famous(ax, df, xcol, ycol):
    """Annotate the most famous named stars at (xcol, ycol), with a bordered
    background box so the text stays legible. adjustText repels overlapping
    labels and draws a thin leader line back to each star."""
    if "proper_name" not in df.columns:
        return
    named = df[df["proper_name"].notna() & df[xcol].notna() & df[ycol].notna()]
    pat = "|".join(FAMOUS_STARS)
    famous = named[named["proper_name"].str.contains(pat, case=False, na=False)]
    label_box = dict(boxstyle="round,pad=0.2", facecolor="#0a0a18",
                     edgecolor="white", linewidth=0.5, alpha=0.75)
    texts = [ax.text(s[xcol], s[ycol], str(s["proper_name"]),
                     fontsize=6, color="white", bbox=label_box)
             for _, s in famous.iterrows()]
    from adjustText import adjust_text
    adjust_text(texts, ax=ax,
                arrowprops=dict(arrowstyle="-", color="white", lw=0.4))
    print(f"  labelled {len(famous)} famous stars")


def plot_hr(merged, path="hr_diagram.png"):
    import matplotlib
    matplotlib.use("Agg")           # save to disk without needing a GUI display
    import matplotlib.pyplot as plt
    path = _resolve_path(path)
    fig, ax = plt.subplots(figsize=(7, 8))
    ax.scatter(merged["bp_rp"], merged["abs_g"],
               c=merged["rgb_hex"].tolist(), s=18, edgecolors="none")
    # Sun reference position (Gaia M_G ~ 4.67, BP-RP ~ 0.82)
    SUN_BP_RP, SUN_ABS_G = 0.82, 4.67
    ax.scatter(SUN_BP_RP, SUN_ABS_G, marker="+", c="yellow",
               s=220, linewidths=2.2, zorder=5, label="Sun")
    ax.annotate("Sun", (SUN_BP_RP, SUN_ABS_G), color="yellow",
                xytext=(8, 4), textcoords="offset points", fontsize=9)
    _label_famous(ax, merged, "bp_rp", "abs_g")
    ax.invert_yaxis()
    ax.set_xlabel("BP - RP"); ax.set_ylabel(r"$M_G$")
    ax.set_title("Nearby-star H-R diagram (true colour)")
    ax.set_facecolor("#0a0a18"); fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


def plot_map(merged, xcol, ycol, xlabel, ylabel, title, path):
    """One face-on 2D map of the stars in heliocentric Galactic coordinates
    (parsec). The Sun sits at the origin; points keep their true-colour RGB."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = _resolve_path(path)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_facecolor("#0a0a18")
    ax.scatter(merged[xcol], merged[ycol],
               c=merged["rgb_hex"].tolist(), s=10, edgecolors="none")
    ax.scatter([0], [0], marker="+", c="yellow", s=140, linewidths=1.4, zorder=5)
    ax.annotate("Sun", (0, 0), xytext=(5, 5), textcoords="offset points",
                fontsize=7, color="yellow")
    _label_famous(ax, merged, xcol, ycol)
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(title)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


def plot_maps(merged, xy_path="map_xy.png", xz_path="map_xz.png"):
    """Two 2D star maps: face-on (X-Y, Galactic plane) and edge-on (X-Z)."""
    plot_map(merged, "x_pc", "y_pc",
             "X (pc, toward Galactic centre)", "Y (pc, toward rotation)",
             "Nearby stars - face-on map (X-Y)", xy_path)
    plot_map(merged, "x_pc", "z_pc",
             "X (pc, toward Galactic centre)", "Z (pc, toward NGP)",
             "Nearby stars - edge-on map (X-Z)", xz_path)


def plot_3d(merged, path="map_3d.png", elev=22, azim=-60):
    """Static 3D scatter of the sample in heliocentric Galactic XYZ (parsec).
    Sun at the origin; points keep their true-colour RGB; famous stars labelled.
    adjustText is 2D-only, so 3D labels are placed directly (may overlap)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = _resolve_path(path)
    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_subplot(projection="3d")
    fig.patch.set_facecolor("#0a0a18"); ax.set_facecolor("#0a0a18")
    ax.scatter(merged["x_pc"], merged["y_pc"], merged["z_pc"],
               c=merged["rgb_hex"].tolist(), s=8, edgecolors="none", depthshade=True)
    ax.scatter([0], [0], [0], marker="+", c="yellow", s=160, linewidths=1.6)
    ax.text(0, 0, 0, "Sun", color="yellow", fontsize=7)

    if "proper_name" in merged.columns:
        pat = "|".join(FAMOUS_STARS)
        famous = merged[merged["proper_name"].notna()
                        & merged["proper_name"].str.contains(pat, case=False, na=False)]
        for _, s in famous.iterrows():
            ax.text(s["x_pc"], s["y_pc"], s["z_pc"], str(s["proper_name"]),
                    color="white", fontsize=5)
        print(f"  labelled {len(famous)} famous stars")

    ax.set_box_aspect((1, 1, 1))            # cubic, so distances aren't distorted
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.label.set_color("white"); a.set_tick_params(colors="white")
    ax.set_xlabel("X (pc)"); ax.set_ylabel("Y (pc)"); ax.set_zlabel("Z (pc)")
    ax.set_title("Nearby stars - 3D (heliocentric Galactic XYZ)", color="white")
    ax.view_init(elev=elev, azim=azim)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


if __name__ == "__main__":
    cat = build_merged_catalogue()
    cols = ["star_id","proper_name","dist_pc","bp_rp","abs_g","rgb_hex","source_catalogue"]
    print("\nClosest 10:\n", cat[cols].head(10).to_string(index=False))
    filename = f"nearby_stars_{MAX_DIST_PC}pc.csv"
    cat.to_csv(filename, index=False)
    print(f"\nWrote {filename} ({len(cat)} stars)")
    plot_hr(cat)
    plot_maps(cat)
    plot_3d(cat)

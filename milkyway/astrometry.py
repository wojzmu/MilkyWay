"""Epoch propagation, cross-matching, space velocities and Galactic Cartesian
positions. astropy is imported lazily inside each function to keep the rest of
the package importable without it."""
import numpy as np

from .config import EPOCH_HIP, EPOCH_GAIA, MATCH_RADIUS_ARCSEC, SOLAR_UVW


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

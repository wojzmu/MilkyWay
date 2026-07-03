"""ESA TAP / SIMBAD queries. astroquery is imported lazily inside each function
so the rest of the package (the colour/photometry/mass math) stays importable
without network dependencies installed."""
from .config import MIN_PARALLAX_MAS
from .mass import mg_upper_bound_for_mass


def query_gaia(limit=None, min_mass=None, min_parallax_mas=None):
    from astroquery.gaia import Gaia
    if min_parallax_mas is None:
        min_parallax_mas = MIN_PARALLAX_MAS
    top = f"TOP {limit}" if limit else ""        # no limit by default
    # Coarse server-side mass pre-filter: a lower mass bound is an upper bound on
    # absolute G (M_G = G + 5*log10(parallax) - 10), so we never download the
    # faint low-mass stars a min-mass run would discard anyway. The exact cut is
    # still applied client-side by apply_min_mass(); this only trims the transfer.
    mass_cut = ""
    if min_mass is not None:
        mg_max = mg_upper_bound_for_mass(min_mass)
        mass_cut = (f"\n      AND gs.phot_g_mean_mag + 5*LOG10(gs.parallax) - 10 "
                    f"<= {mg_max}")
    adql = f"""
    SELECT {top}
      gs.source_id, gs.ra, gs.dec, gs.l, gs.b, gs.parallax, gs.parallax_over_error,
      gs.pmra, gs.pmdec, gs.radial_velocity,
      gs.phot_g_mean_mag, gs.bp_rp, gs.teff_gspphot, gs.ruwe,
      ap.mass_flame, ap.age_flame
    FROM gaiadr3.gaia_source AS gs
    LEFT OUTER JOIN gaiadr3.astrophysical_parameters AS ap
      ON gs.source_id = ap.source_id
    WHERE gs.parallax > {min_parallax_mas}
      AND gs.parallax_over_error > 10
      AND gs.ruwe < 1.4{mass_cut}
    ORDER BY gs.parallax DESC
    """
    return Gaia.launch_job_async(adql).get_results().to_pandas()

def query_hipparcos(min_parallax_mas=None):
    from astroquery.gaia import Gaia
    if min_parallax_mas is None:
        min_parallax_mas = MIN_PARALLAX_MAS
    adql = f"""
    SELECT hip, ra, de, plx, e_plx, pmra, pmde, vmag, b_v, v_i
    FROM public.hipparcos
    WHERE plx > {min_parallax_mas} AND plx / e_plx > 10
    ORDER BY plx DESC
    """
    return Gaia.launch_job_async(adql).get_results().to_pandas()


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

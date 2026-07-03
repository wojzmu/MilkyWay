// Schema for one row of nearby_stars_merged.csv.
// See ../../Dataset.md for the authoritative column reference.
// Numeric fields are `number | null` because many columns (teff_gspphot,
// radial_velocity, U/V/W, proper_name, ...) are frequently empty in the source.

export interface Star {
  starId: string;

  // Astrometry
  ra: number | null; // deg, ICRS @ J2016.0
  dec: number | null; // deg
  parallaxMas: number | null;
  distPc: number | null;
  pmra: number | null; // mas/yr
  pmdec: number | null; // mas/yr
  radialVelocity: number | null; // km/s, NaN for most rows

  // Photometry (Gaia system)
  gMag: number | null;
  bpRp: number | null;
  vMag: number | null;
  absG: number | null;

  // Astrophysical params
  teffGspphot: number | null; // scientific Teff (Gaia Apsis), often null
  massFlame: number | null;
  ageFlame: number | null;
  massEst: number | null;

  // Provenance
  photOrigin: string; // native_gaia | transformed_from_johnson
  sourceCatalogue: string; // Gaia | Hipparcos

  // Galactic coordinates
  l: number | null; // deg
  b: number | null; // deg
  x: number | null; // pc, heliocentric Cartesian
  y: number | null; // pc
  z: number | null; // pc

  // Display colour (NOT science — derived from BP-RP for rendering)
  teffColor: number | null;
  rgbR: number | null;
  rgbG: number | null;
  rgbB: number | null;
  rgbHex: string; // e.g. "#FFB260"; "#808080" when unknown

  // Galactic space velocities (NaN for most rows)
  u: number | null;
  v: number | null;
  w: number | null;

  // Identity
  simbadMainId: string | null;
  properName: string | null;

  // Classification
  spType: string | null; // SIMBAD MK spectral type, e.g. "M3.5V"
  starClass: string; // coarse category, e.g. "Main sequence" (see categories.ts)

  // Data quality
  spuriousParallax: boolean; // likely inflated Gaia parallax (see spurious.ts /
  // Dataset.md). From the CSV column when present, else derived client-side.
}

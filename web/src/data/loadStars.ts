import Papa from "papaparse";
import type { Star } from "../types";

// Dataset filename comes from VITE_DATASET_FILE (.env), with a built-in default.
const DATASET_FILE =
  import.meta.env.VITE_DATASET_FILE ?? "nearby_stars_merged.csv";
const CSV_URL = `${import.meta.env.BASE_URL}${DATASET_FILE}`;

/** Parse a possibly-empty CSV cell into `number | null`. */
function num(value: string | undefined): number | null {
  if (value === undefined || value === "") return null;
  const n = Number(value);
  return Number.isFinite(n) ? n : null;
}

/** Parse a possibly-empty CSV cell into `string | null`. */
function str(value: string | undefined): string | null {
  if (value === undefined || value === "") return null;
  return value;
}

type Row = Record<string, string>;

function toStar(r: Row): Star {
  return {
    starId: r.star_id,
    ra: num(r.ra),
    dec: num(r.dec),
    parallaxMas: num(r.parallax_mas),
    distPc: num(r.dist_pc),
    pmra: num(r.pmra),
    pmdec: num(r.pmdec),
    radialVelocity: num(r.radial_velocity),
    gMag: num(r.g_mag),
    bpRp: num(r.bp_rp),
    vMag: num(r.v_mag),
    absG: num(r.abs_g),
    teffGspphot: num(r.teff_gspphot),
    massFlame: num(r.mass_flame),
    ageFlame: num(r.age_flame),
    massEst: num(r.mass_est),
    photOrigin: r.phot_origin ?? "",
    sourceCatalogue: r.source_catalogue ?? "",
    l: num(r.l),
    b: num(r.b),
    x: num(r.x_pc),
    y: num(r.y_pc),
    z: num(r.z_pc),
    teffColor: num(r.teff_color),
    rgbR: num(r.rgb_r),
    rgbG: num(r.rgb_g),
    rgbB: num(r.rgb_b),
    rgbHex: r.rgb_hex || "#808080",
    u: num(r.U),
    v: num(r.V),
    w: num(r.W),
    simbadMainId: str(r.simbad_main_id),
    properName: str(r.proper_name),
    spType: str(r.sp_type),
    starClass: r.star_class || "Unknown",
  };
}

/** Fetch and parse the nearby-stars catalogue from /public. */
export async function loadStars(): Promise<Star[]> {
  const res = await fetch(CSV_URL);
  if (!res.ok) {
    throw new Error(`Failed to fetch dataset: ${res.status} ${res.statusText}`);
  }
  const text = await res.text();

  const parsed = Papa.parse<Row>(text, {
    header: true,
    skipEmptyLines: true,
  });

  return parsed.data
    .filter((r) => r.star_id) // drop any blank trailing rows
    .map(toStar);
}

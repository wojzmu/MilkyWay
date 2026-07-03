import Papa from "papaparse";
import type { Star } from "../types";
import { deriveSpuriousParallax } from "../spurious";

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

/** Parse a boolean CSV cell (pandas writes `True`/`False`), else null. */
function bool(value: string | undefined): boolean | null {
  if (value === undefined || value === "") return null;
  const v = value.trim().toLowerCase();
  if (v === "true" || v === "1") return true;
  if (v === "false" || v === "0") return false;
  return null;
}

type Row = Record<string, string>;

function toStar(r: Row): Star {
  const absG = num(r.abs_g);
  const bpRp = num(r.bp_rp);
  const gMag = num(r.g_mag);
  // Prefer the pipeline's flag when the CSV carries it; otherwise derive it
  // client-side (the web working sets predate the column). See spurious.ts.
  const csvSpurious = bool(r.spurious_parallax);
  const spuriousParallax =
    csvSpurious ?? deriveSpuriousParallax(absG, bpRp, gMag);
  return {
    starId: r.star_id,
    ra: num(r.ra),
    dec: num(r.dec),
    parallaxMas: num(r.parallax_mas),
    distPc: num(r.dist_pc),
    pmra: num(r.pmra),
    pmdec: num(r.pmdec),
    radialVelocity: num(r.radial_velocity),
    gMag,
    bpRp,
    vMag: num(r.v_mag),
    absG,
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
    spuriousParallax,
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

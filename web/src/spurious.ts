// Client-side mirror of MilkyWay.py `flag_spurious_parallax`.
//
// SOURCE OF TRUTH is the Python pipeline. These thresholds and the main-sequence
// reference curve are copied from milkyway/classify.py (`SPURIOUS_*` constants
// and `_MS_BPRP` / `_MS_ABSG`) — keep them in sync if the pipeline changes.
//
// Used only as a FALLBACK: loadStars prefers the CSV's `spurious_parallax`
// column when present, and only calls this when the dataset lacks that column
// (e.g. the hand-curated web working sets). See Dataset.md "Spurious parallaxes".

// Main-sequence ridge M_G(BP-RP), Pecaut & Mamajek-style anchors.
const MS_BPRP = [
  -0.25, 0.15, 0.45, 0.725, 0.975, 1.25, 1.55, 1.85, 2.15, 2.45, 2.8, 3.25,
  3.75, 4.3,
];
const MS_ABSG = [
  0.45, 1.54, 2.75, 4.19, 5.46, 6.38, 7.26, 8.14, 9.0, 9.97, 11.09, 12.3, 13.41,
  14.39,
];

const BELOW_MS_MAG = 4.0; // mag below the MS ridge that counts as unphysical
const FAINT_G = 19.0; // apparent G near Gaia's limit -> really distant
const NOCOLOUR_MG = 15.0; // colourless + this faint absolute -> crowding

/** Linear interpolation with end-clamping (matches numpy.interp). */
function interpClamped(x: number, xs: number[], ys: number[]): number {
  if (x <= xs[0]) return ys[0];
  if (x >= xs[xs.length - 1]) return ys[ys.length - 1];
  for (let i = 1; i < xs.length; i++) {
    if (x <= xs[i]) {
      const t = (x - xs[i - 1]) / (xs[i] - xs[i - 1]);
      return ys[i - 1] + t * (ys[i] - ys[i - 1]);
    }
  }
  return ys[ys.length - 1];
}

/**
 * True where the Gaia parallax is likely spurious (a distant background star
 * inflated into the nearby sample). Conservative: only flags apparently-faint
 * stars (g > 19, i.e. really distant) that are either red but far below the main
 * sequence, or colourless yet very faint in absolute magnitude. Genuine nearby
 * white/brown dwarfs are apparently bright (g < ~18) and are left untouched.
 */
export function deriveSpuriousParallax(
  absG: number | null,
  bpRp: number | null,
  gMag: number | null,
): boolean {
  if (absG == null || gMag == null) return false;
  if (gMag <= FAINT_G) return false; // apparently bright -> genuinely nearby
  if (bpRp != null) {
    const delta = absG - interpClamped(bpRp, MS_BPRP, MS_ABSG); // +ve = below MS
    return bpRp > 1.0 && delta > BELOW_MS_MAG;
  }
  return absG > NOCOLOUR_MG; // no colour (crowding killed BP/RP) + very faint
}

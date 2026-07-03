import type { Star } from "./types";
import { CATEGORY_ORDER } from "./categories";

// 1 parsec in light years.
export const PC_TO_LY = 3.261563777;

export interface FilterDomains {
  mass: [number, number]; // solar masses
  dist: [number, number]; // light years
}

export interface Filters {
  categories: Set<string>; // categories allowed through
  mass: [number, number]; // M_sun, inclusive
  dist: [number, number]; // light years, inclusive
  showSpurious: boolean; // include likely-spurious-parallax stars (default off)
}

/** Min/max sliders' bounds, derived from the data (nicely rounded). */
export function computeDomains(stars: Star[]): FilterDomains {
  let mlo = Infinity,
    mhi = -Infinity,
    dlo = Infinity,
    dhi = -Infinity;
  for (const s of stars) {
    if (s.massEst != null && Number.isFinite(s.massEst)) {
      mlo = Math.min(mlo, s.massEst);
      mhi = Math.max(mhi, s.massEst);
    }
    if (s.distPc != null && Number.isFinite(s.distPc)) {
      const ly = s.distPc * PC_TO_LY;
      dlo = Math.min(dlo, ly);
      dhi = Math.max(dhi, ly);
    }
  }
  if (!Number.isFinite(mlo)) [mlo, mhi] = [0, 1];
  if (!Number.isFinite(dlo)) [dlo, dhi] = [0, 1];
  return {
    mass: [Math.floor(mlo * 100) / 100, Math.ceil(mhi * 100) / 100],
    dist: [Math.floor(dlo * 10) / 10, Math.ceil(dhi * 10) / 10],
  };
}

/**
 * Default filter: every category and the full mass/distance range, but
 * likely-spurious-parallax stars hidden (they are data artefacts — see
 * spurious.ts). Toggle `showSpurious` on to reveal them.
 */
export function defaultFilters(d: FilterDomains): Filters {
  return {
    categories: new Set(CATEGORY_ORDER),
    mass: [...d.mass],
    dist: [...d.dist],
    showSpurious: false,
  };
}

/** True when the filter would hide at least some stars (used for the badge). */
export function isFiltered(f: Filters, d: FilterDomains): boolean {
  return (
    !f.showSpurious ||
    f.categories.size < CATEGORY_ORDER.length ||
    f.mass[0] > d.mass[0] ||
    f.mass[1] < d.mass[1] ||
    f.dist[0] > d.dist[0] ||
    f.dist[1] < d.dist[1]
  );
}

/**
 * Apply the global filters to a star list.
 *
 * Mass note: many stars (white dwarfs, giants, anything outside the calibrated
 * main-sequence range) have no `mass_est`. They are NOT excluded by the mass
 * slider — you can't filter on an unknown value — so narrowing mass keeps them
 * visible; use the category checkboxes to hide those populations instead.
 */
export function applyFilters(stars: Star[], f: Filters): Star[] {
  return stars.filter((s) => {
    if (!f.showSpurious && s.spuriousParallax) return false;

    if (!f.categories.has(s.starClass)) return false;

    if (s.distPc != null) {
      const ly = s.distPc * PC_TO_LY;
      if (ly < f.dist[0] || ly > f.dist[1]) return false;
    }

    if (s.massEst != null && Number.isFinite(s.massEst)) {
      if (s.massEst < f.mass[0] || s.massEst > f.mass[1]) return false;
    }
    return true;
  });
}

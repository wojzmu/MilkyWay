// Canonical stellar categories (the `star_class` column produced by
// MilkyWay.py) plus a categorical colour palette for the "colour by category"
// view. Order is roughly by evolutionary stage / abundance, used for the legend.

export const CATEGORY_ORDER = [
  "Main sequence",
  "White dwarf",
  "Subgiant",
  "Red giant",
  "Giant",
  "Supergiant",
  "Brown dwarf",
  "Subdwarf",
  "Unknown",
] as const;

export type Category = (typeof CATEGORY_ORDER)[number];

/** How star markers are coloured in the views. */
export type ColorMode = "trueColor" | "category";

// Distinct, dark-background-friendly hues (not the stars' true colours).
export const CATEGORY_COLORS: Record<string, string> = {
  "Main sequence": "#ffcf4d",
  "White dwarf": "#cfe8ff",
  Subgiant: "#7fe0c0",
  "Red giant": "#ff6b5e",
  Giant: "#ff9f43",
  Supergiant: "#ff4d97",
  "Brown dwarf": "#a6694a",
  Subdwarf: "#b39ddb",
  Unknown: "#6b7488",
};

const FALLBACK = CATEGORY_COLORS.Unknown;

/** Hex colour for a star's category, falling back to the Unknown grey. */
export function categoryColor(starClass: string | null | undefined): string {
  if (!starClass) return FALLBACK;
  return CATEGORY_COLORS[starClass] ?? FALLBACK;
}

// Well-known star names for the CSV view (public/star_names.json, D-026).

/** One entry of public/star_names.json (the CSV view matches it by star_id). */
export interface StarName {
  name: string;
  name_iau: string;
  hip: number;
  tier: number;
  v_mag: number;
  star_ids: string[];
}

/** star_id -> name entry from public/star_names.json; empty map on any failure. */
export async function loadStarNames(): Promise<Map<string, StarName>> {
  const url = `${import.meta.env.BASE_URL}star_names.json`;
  const out = new Map<string, StarName>();
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const doc = (await res.json()) as { names?: StarName[] };
    for (const n of doc.names ?? []) for (const id of n.star_ids) out.set(id, n);
  } catch (e) {
    console.warn(`star names: ${url}: ${(e as Error).message}`);
  }
  return out;
}

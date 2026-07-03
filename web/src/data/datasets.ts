// Dataset registry: the app fetches a curated manifest (public/datasets.json)
// listing the CSVs a visitor may load, each with a human-friendly label. This is
// deliberately a runtime manifest rather than a build-time env var so datasets
// can be added/renamed without a rebuild, and so large working-set CSVs that must
// never be served (e.g. the ~1.25 GB 1000 pc file) are simply left off the list.

/** One selectable dataset, as described in public/datasets.json. */
export interface DatasetMeta {
  file: string; // CSV filename served from /public
  label: string; // friendly name shown in the picker
  description?: string; // optional longer blurb (tooltip)
  default?: boolean; // pre-selected when nothing else resolves
}

const MANIFEST_URL = `${import.meta.env.BASE_URL}datasets.json`;
const STORAGE_KEY = "milkyway.dataset";
const QUERY_PARAM = "dataset";

// Ultimate fallback if datasets.json can't be fetched: keep today's behaviour by
// synthesising a single entry from VITE_DATASET_FILE (or a built-in default).
const FALLBACK_FILE =
  import.meta.env.VITE_DATASET_FILE ?? "nearby_stars_merged.csv";

function fallbackList(): DatasetMeta[] {
  return [{ file: FALLBACK_FILE, label: FALLBACK_FILE, default: true }];
}

/** Fetch and validate the dataset manifest; falls back to a single synthetic
 *  entry so the app still loads if the manifest is missing or malformed. */
export async function loadDatasetManifest(): Promise<DatasetMeta[]> {
  try {
    const res = await fetch(MANIFEST_URL);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const json = (await res.json()) as { datasets?: DatasetMeta[] };
    const list = (json.datasets ?? []).filter(
      (d): d is DatasetMeta => typeof d?.file === "string" && d.file.length > 0,
    );
    return list.length > 0 ? list : fallbackList();
  } catch {
    return fallbackList();
  }
}

/** Pick the file to load first: ?dataset= param, then remembered choice, then
 *  the manifest default, then the first entry. Only files present in the
 *  manifest are ever accepted, so an arbitrary path can't be fetched. */
export function resolveInitialDataset(list: DatasetMeta[]): string {
  const known = new Set(list.map((d) => d.file));

  const fromUrl = new URLSearchParams(location.search).get(QUERY_PARAM);
  if (fromUrl && known.has(fromUrl)) return fromUrl;

  const remembered = safeGet(STORAGE_KEY);
  if (remembered && known.has(remembered)) return remembered;

  const def = list.find((d) => d.default);
  if (def) return def.file;

  return list[0]?.file ?? FALLBACK_FILE;
}

/** Persist the choice (localStorage) and reflect it in ?dataset= without a
 *  reload, so the URL stays shareable/deep-linkable. */
export function rememberDataset(file: string): void {
  safeSet(STORAGE_KEY, file);
  const url = new URL(location.href);
  url.searchParams.set(QUERY_PARAM, file);
  history.replaceState(null, "", url);
}

// localStorage can throw (private mode, disabled storage); never let that break
// dataset selection.
function safeGet(key: string): string | null {
  try {
    return localStorage.getItem(key);
  } catch {
    return null;
  }
}

function safeSet(key: string, value: string): void {
  try {
    localStorage.setItem(key, value);
  } catch {
    /* ignore */
  }
}

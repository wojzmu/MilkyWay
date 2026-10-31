// Binary point-cloud loader for the "bin" datasets (public/map_1250pc/).
// points.bin is fetched whole; details.bin (36 MB) is read lazily, one 24-byte
// record at a time, with HTTP Range requests.

export interface PointCloudIndex {
  n: number;
  class_codes: string[];
  dataset_id?: string;
  selection?: { dist_pc_max?: number; abs_mag_max?: number | null };
  /** Version 2: parsec per int16 position unit. */
  position_scale_pc?: number;
  labels?: { file: string; n: number };
  [key: string]: unknown;
}

/** A well-known star's name, placed at its catalogue position (labels.json). */
export interface StarLabel {
  name: string;
  nameIau: string;
  hip: number;
  tier: number;
  vMag: number;
  /** Screen axes (x, galactic z, galactic y), parsec. */
  pos: [number, number, number];
  distPc: number;
  /** Index into points.bin, or null when the star is not among the exported points. */
  point: number | null;
}

export interface PointCloud {
  index: PointCloudIndex;
  n: number;
  /** Screen axes (x, galactic z, galactic y), parsec; length 3n. */
  positions: Float32Array;
  /** Interleaved R, G, B, U bytes; length 4n. */
  rgbu: Uint8Array;
  /** Class code per point; length n. */
  classes: Uint8Array;
  classCodes: string[];
  /** Directory URL (with trailing slash) holding points.bin / details.bin. */
  baseUrl: string;
  /** Named stars, best known first; empty when the export has no labels.json. */
  labels: StarLabel[];
}

export interface PointDetail {
  label: string;
  rLo: number;
  rHi: number;
  gMag: number;
  bpRp: number;
}

const HEADER = 16;

function dirOf(url: string): string {
  return url.slice(0, url.lastIndexOf("/") + 1);
}

async function fetchBuffer(
  url: string,
  onProgress?: (text: string) => void,
): Promise<ArrayBuffer> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status} ${res.statusText}`);
  const total = Number(res.headers.get("content-length") ?? 0);
  if (!res.body || !onProgress) return res.arrayBuffer();
  const reader = res.body.getReader();
  const chunks: Uint8Array[] = [];
  let got = 0;
  for (;;) {
    const { done, value } = await reader.read();
    if (done) break;
    chunks.push(value);
    got += value.length;
    onProgress(
      total
        ? `Loading star map… ${(got / 1e6).toFixed(1)} / ${(total / 1e6).toFixed(1)} MB`
        : `Loading star map… ${(got / 1e6).toFixed(1)} MB`,
    );
  }
  const out = new Uint8Array(got);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.length;
  }
  return out.buffer;
}

export async function loadPointCloud(
  indexFile: string,
  onProgress?: (text: string) => void,
): Promise<PointCloud> {
  // A manifest entry may point at another host (absolute URL, e.g. a data repo);
  // otherwise the file is served next to the app from public/.
  const indexUrl = /^https?:\/\//.test(indexFile)
    ? indexFile
    : `${import.meta.env.BASE_URL}${indexFile}`;
  const res = await fetch(indexUrl);
  if (!res.ok) throw new Error(`${indexUrl}: ${res.status} ${res.statusText}`);
  const index = (await res.json()) as PointCloudIndex;
  if (typeof index.n !== "number" || !Array.isArray(index.class_codes)) {
    throw new Error(`${indexUrl}: malformed index.json`);
  }
  const baseUrl = dirOf(indexUrl);
  const buf = await fetchBuffer(`${baseUrl}points.bin`, onProgress);

  if (buf.byteLength < HEADER) throw new Error("points.bin: file too short");
  const dv = new DataView(buf);
  const magic = String.fromCharCode(
    dv.getUint8(0),
    dv.getUint8(1),
    dv.getUint8(2),
    dv.getUint8(3),
  );
  if (magic !== "MWPT") throw new Error(`points.bin: bad magic "${magic}"`);
  const version = dv.getUint16(4, true);
  if (version !== 1 && version !== 2) {
    throw new Error(`points.bin: unsupported version ${version}`);
  }
  const flags = dv.getUint16(6, true);
  if (!(flags & 1)) throw new Error("points.bin: class block missing");
  const n = dv.getUint32(8, true);
  if (n !== index.n) {
    throw new Error(`points.bin: N=${n} does not match index.json n=${index.n}`);
  }
  // v1: float32 xyz (12 B/star); v2: int16 xyz (6 B/star) padded to 4 bytes,
  // scaled by index.position_scale_pc.
  const posBytes = version === 1 ? 12 * n : 6 * n + ((4 - ((6 * n) % 4)) % 4);
  const rgbuAt = HEADER + posBytes;
  const body = rgbuAt + 5 * n;
  const expected = body + ((4 - (body % 4)) % 4);
  const scale = index.position_scale_pc;
  if (version === 2 && !(typeof scale === "number" && scale > 0)) {
    throw new Error(`${indexUrl}: version 2 needs position_scale_pc`);
  }
  if (buf.byteLength !== expected) {
    throw new Error(
      `points.bin: expected ${expected} bytes, got ${buf.byteLength}`,
    );
  }

  // Galactic (x, y, z) -> screen (x, z, y), like StarField3D.
  const src =
    version === 1
      ? new Float32Array(buf, HEADER, 3 * n)
      : new Int16Array(buf, HEADER, 3 * n);
  const k = version === 1 ? 1 : (scale as number);
  const positions = new Float32Array(3 * n);
  for (let i = 0; i < n; i++) {
    positions[3 * i] = src[3 * i] * k;
    positions[3 * i + 1] = src[3 * i + 2] * k;
    positions[3 * i + 2] = src[3 * i + 1] * k;
  }
  const rgbu = new Uint8Array(buf, rgbuAt, 4 * n);
  const classes = new Uint8Array(buf, rgbuAt + 4 * n, n);
  return {
    index,
    n,
    positions,
    rgbu,
    classes,
    classCodes: index.class_codes,
    baseUrl,
    labels: index.labels ? await loadLabels(`${baseUrl}${index.labels.file}`, n) : [],
  };
}

interface LabelRecord {
  name: string;
  name_iau: string;
  hip: number;
  tier: number;
  v_mag: number;
  x_pc: number;
  y_pc: number;
  z_pc: number;
  dist_pc: number;
  point: number | null;
}

/** labels.json -> StarLabel[]; a missing or broken file only costs the names. */
async function loadLabels(url: string, n: number): Promise<StarLabel[]> {
  try {
    const res = await fetch(url);
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
    const doc = (await res.json()) as { labels?: LabelRecord[] };
    return (doc.labels ?? []).map((r) => ({
      name: r.name,
      nameIau: r.name_iau,
      hip: r.hip,
      tier: r.tier,
      vMag: r.v_mag,
      pos: [r.x_pc, r.z_pc, r.y_pc],
      distPc: r.dist_pc,
      point: r.point !== null && r.point >= 0 && r.point < n ? r.point : null,
    }));
  } catch (e) {
    console.warn(`labels: ${url}: ${(e as Error).message}`);
    return [];
  }
}

const fullDetails = new Map<string, ArrayBuffer>();

function parseRecord(dv: DataView, off: number): PointDetail {
  const id = dv.getBigInt64(off, true);
  return {
    label: id >= 0n ? `Gaia DR3 ${id}` : `HIP ${-id}`,
    rLo: dv.getFloat32(off + 8, true),
    rHi: dv.getFloat32(off + 12, true),
    gMag: dv.getFloat32(off + 16, true),
    bpRp: dv.getFloat32(off + 20, true),
  };
}

export async function fetchPointDetails(
  baseUrl: string,
  i: number,
): Promise<PointDetail> {
  const url = `${baseUrl}details.bin`;
  const start = HEADER + 24 * i;
  const cached = fullDetails.get(url);
  if (cached) return parseRecord(new DataView(cached, start, 24), 0);

  const res = await fetch(url, {
    headers: { Range: `bytes=${start}-${start + 23}` },
  });
  if (res.status === 206) {
    const b = await res.arrayBuffer();
    if (b.byteLength !== 24) throw new Error("details.bin: short range reply");
    return parseRecord(new DataView(b), 0);
  }
  if (res.status === 200) {
    const b = await res.arrayBuffer();
    fullDetails.set(url, b);
    return parseRecord(new DataView(b, start, 24), 0);
  }
  throw new Error(`${url}: ${res.status} ${res.statusText}`);
}

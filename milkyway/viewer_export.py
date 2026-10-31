"""Binary export of a catalogue dataset for the web viewer (Mapa 1.0, milestone M4; D-021).

Plan v4 S1 dec. 11-12, simplified for 1.0 to one file without 250 pc cubes:

    <out>/index.json     format, provenance, sampling, decoding parameters
    <out>/points.bin     everything the map draws, loaded whole (11 B/star)
    <out>/details.bin    per-star extras, fetched one 24 B record at a time on click

points.bin (little-endian, 4-byte aligned):
    header 16 B: b"MWPT", uint16 version (2), uint16 flags (bit 0: class block,
                 bit 1: int16 positions), uint32 N, uint32 reserved
    N x 3 int16     x, y, z in units of index.json "position_scale_pc" (dist_max/32767,
                    ~0.04 pc for 1250 pc; heliocentric Galactic: x -> Galactic centre,
                    y -> rotation, z -> north Galactic pole); padded to 4 bytes
    N x 4 uint8     R, G, B (display sRGB; grey when unknown), U (uncertainty code)
    N x 1 uint8     star_class code (index into index.json "class_codes"), padded to 4
details.bin:
    header 16 B: b"MWDT", uint16 version, uint16 record size (24), uint32 N, uint32 0
    N x 24 B        int64 id (source_id; -hip for Hipparcos-only rows),
                    float32 r_lo_pc, r_hi_pc, g_mag, bp_rp (NaN when unknown)
Record i of details.bin is point i of points.bin (offset 16 + 24 i).

U = round(254 (log10 f + 3) / (log10 0.5 + 3)) clipped to [0, 254], where
f = (r_hi - r_lo) / (2 dist) is the relative distance uncertainty; 255 = r_hi unknown.
The byte carries data, not opacity: the viewer maps it to opacity with a slider.

Version 1 (float32 positions, 17 B/star) is no longer written; the viewer still reads it.

Thinning: a star is kept when splitmix64(id) < f * 2**64 with one f = target / N
everywhere (keeps the disc's contrast); stars brighter than `always_g_max` are always
kept and come first. Inside each group points are ordered by hash, so every prefix is
itself a random sample (the viewer can draw fewer points with drawRange).
"""
import hashlib
import json
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from . import schema, storage

FORMAT_VERSION = 2
DETAILS_VERSION = 1
DEFAULT_TARGET = 1_500_000
DEFAULT_DIST_MAX_PC = 1250.0       # plan 1.0: the Edenhofer dust map's reach (D-003)
DEFAULT_ALWAYS_G_MAX = 6.0         # naked-eye stars are never thinned out
U_F_MIN, U_F_MAX = 1e-3, 0.5
CLASS_CODES = list(schema.ENUMS["star_class"])
_COLUMNS = ["source_id", "hip", "x_pc", "y_pc", "z_pc", "rgb_r", "rgb_g", "rgb_b",
            "dist_pc", "r_lo_pc", "r_hi_pc", "g_mag", "bp_rp", "abs_g", "star_class"]

_M64 = (1 << 64) - 1


def splitmix64(x):
    """splitmix64 finaliser on a uint64 array (wrapping arithmetic)."""
    z = np.asarray(x, dtype=np.uint64) + np.uint64(0x9E3779B97F4A7C15)
    z = (z ^ (z >> np.uint64(30))) * np.uint64(0xBF58476D1CE4E5B9)
    z = (z ^ (z >> np.uint64(27))) * np.uint64(0x94D049BB133111EB)
    return z ^ (z >> np.uint64(31))


def star_ids(table):
    """int64 id per row: source_id, or -hip for Hipparcos-only rows."""
    # fill_null first: to_numpy() on a column with nulls would go through float64,
    # and source_ids exceed 2**53.
    sid = pc.fill_null(table["source_id"], 0).to_numpy().astype(np.int64)
    hip = pc.fill_null(table["hip"], 0).to_numpy().astype(np.int64)
    return np.where(table["source_id"].is_null().to_numpy(zero_copy_only=False), -hip, sid)


def uncertainty_code(dist, r_lo, r_hi):
    """uint8 U code from distance quantiles (see module docstring)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        f = (r_hi - r_lo) / (2 * dist)
        u = np.rint(254 * (np.log10(np.maximum(f, U_F_MIN)) + 3)
                    / (np.log10(U_F_MAX) + 3))
    u = np.clip(u, 0, 254)
    return np.where(np.isfinite(f), u, 255).astype(np.uint8)


def _f32(table, name):
    return table[name].to_numpy(zero_copy_only=False).astype(np.float32)


def _eligible(t, dist_max_pc, abs_mag_max):
    keep = pc.less_equal(t["dist_pc"], dist_max_pc)
    if abs_mag_max is not None:                       # null abs_g -> excluded
        keep = pc.and_(keep, pc.fill_null(pc.less_equal(t["abs_g"], abs_mag_max), False))
    return keep


def export_viewer(dataset_dir, out_dir, *, target=DEFAULT_TARGET,
                  dist_max_pc=DEFAULT_DIST_MAX_PC, always_g_max=DEFAULT_ALWAYS_G_MAX,
                  abs_mag_max=None):
    """Write index.json, points.bin and details.bin for `dataset_dir`; return the index.

    `abs_mag_max` keeps only stars with abs_g <= it (e.g. 2: intrinsically bright
    stars seen through the whole volume at G < 15, D-023). `target=None` disables
    thinning (every eligible star is exported).
    """
    manifest = storage.open_catalog(dataset_dir)
    root = Path(dataset_dir)
    files = [root / p["path"] for p in manifest["storage"]["partitions"]]

    # Pass 1: how many stars the cut leaves, to fix f.
    n_eligible = 0
    for f in files:
        d = pq.read_table(f, columns=["dist_pc", "abs_g"])
        n_eligible += pc.sum(_eligible(d, dist_max_pc, abs_mag_max)).as_py() or 0
    frac = min(1.0, target / n_eligible) if n_eligible and target else 1.0
    threshold = np.uint64(min(_M64, int(frac * 2 ** 64)))

    # Pass 2: keep sampled + bright stars, partition by partition.
    kept = []
    for f in files:
        t = pq.read_table(f, columns=_COLUMNS, schema=schema.CATALOGUE_SCHEMA)
        t = t.filter(_eligible(t, dist_max_pc, abs_mag_max))
        if t.num_rows == 0:
            continue
        ids = star_ids(t)
        h = splitmix64(ids.view(np.uint64))
        g = _f32(t, "g_mag")
        always = g < always_g_max                     # NaN -> False
        keep = always | (h < threshold)
        sub = t.filter(pa.array(keep))
        kept.append((sub, ids[keep], h[keep], always[keep]))
    if not kept:
        raise ValueError(f"no stars within {dist_max_pc} pc")
    t = pa.concat_tables([k[0] for k in kept])
    ids = np.concatenate([k[1] for k in kept])
    h = np.concatenate([k[2] for k in kept])
    always = np.concatenate([k[3] for k in kept])
    order = np.lexsort((h, ~always))                  # bright first, then by hash
    t, ids, always = t.take(pa.array(order)), ids[order], always[order]
    n = t.num_rows

    dist, r_lo, r_hi = _f32(t, "dist_pc"), _f32(t, "r_lo_pc"), _f32(t, "r_hi_pc")
    rgb = np.stack([pc.fill_null(t[c], 128).to_numpy().astype(np.uint8)
                    for c in ("rgb_r", "rgb_g", "rgb_b")], axis=1)
    rgbu = np.concatenate([rgb, uncertainty_code(dist, r_lo, r_hi)[:, None]], axis=1)
    cls = pc.index_in(t["star_class"], pa.array(CLASS_CODES)).to_numpy(
        zero_copy_only=False)
    if np.isnan(cls.astype(float)).any():
        raise ValueError("star_class outside the schema enum")
    cls = cls.astype(np.uint8)
    scale = dist_max_pc / 32767.0
    xyz = np.stack([_f32(t, c) for c in ("x_pc", "y_pc", "z_pc")], axis=1)
    if np.abs(xyz).max(initial=0) > dist_max_pc * (1 + 1e-6):
        raise ValueError("position outside dist_max_pc; int16 quantisation would wrap")
    xyz_q = np.clip(np.rint(xyz / scale), -32767, 32767).astype("<i2")

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    pos_pad = (-6 * n) % 4                            # keep the RGBU block 4-aligned
    pad = (-(6 * n + pos_pad + 5 * n)) % 4
    points = b"".join([
        b"MWPT", np.array([FORMAT_VERSION, 0b11], "<u2").tobytes(),
        np.array([n, 0], "<u4").tobytes(),
        xyz_q.tobytes(), b"\0" * pos_pad, np.ascontiguousarray(rgbu).tobytes(),
        cls.tobytes(), b"\0" * pad])
    rec = np.zeros(n, dtype=[("id", "<i8"), ("r_lo", "<f4"), ("r_hi", "<f4"),
                             ("g", "<f4"), ("bp_rp", "<f4")])
    rec["id"], rec["r_lo"], rec["r_hi"] = ids, r_lo, r_hi
    rec["g"], rec["bp_rp"] = _f32(t, "g_mag"), _f32(t, "bp_rp")
    details = b"".join([b"MWDT", np.array([DETAILS_VERSION, 24], "<u2").tobytes(),
                        np.array([n, 0], "<u4").tobytes(), rec.tobytes()])
    for name, data in (("points.bin", points), ("details.bin", details)):
        storage._atomic_write(out / name, data)

    index = {
        "format": "milkyway-viewer", "format_version": FORMAT_VERSION,
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": storage._sha256(root / storage.MANIFEST_NAME),
        "n": n, "frame": "heliocentric Galactic, pc: x -> GC, y -> rotation, z -> NGP",
        "position_scale_pc": scale,
        "selection": {"dist_pc_max": dist_max_pc, "abs_mag_max": abs_mag_max,
                      "dataset_selection": manifest["selection"]},
        "sampling": {"method": "splitmix64(id) < f * 2**64", "target": target,
                     "n_eligible": int(n_eligible), "f": frac,
                     "always_g_max": always_g_max, "n_always": int(always.sum()),
                     "order": "always-kept first, then by hash (every prefix is a random sample)"},
        "uncertainty_code": {"f": "(r_hi_pc - r_lo_pc) / (2 dist_pc)", "f_min": U_F_MIN,
                             "f_max": U_F_MAX, "missing": 255,
                             "formula": "round(254 (log10 f + 3) / (log10 f_max + 3))"},
        "class_codes": CLASS_CODES,
        "files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in (("points.bin", points), ("details.bin", details))},
    }
    storage._atomic_write(out / "index.json", json.dumps(index, indent=1).encode())
    return index

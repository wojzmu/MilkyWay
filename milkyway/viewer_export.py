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
    N x 4 uint8     R, G, B (display sRGB of the dereddened colour bp_rp0, observed
                    bp_rp where the catalogue has no extinction; grey when unknown),
                    U (uncertainty code)
    N x 1 uint8     star_class code (index into index.json "class_codes"), padded to 4
details.bin:
    header 16 B: b"MWDT", uint16 version, uint16 record size (24), uint32 N, uint32 0
    N x 24 B        int64 id (source_id; -hip for Hipparcos-only rows),
                    float32 r_lo_pc, r_hi_pc, g_mag, bp_rp (NaN when unknown)
Record i of details.bin is point i of points.bin (offset 16 + 24 i).
labels.json:
    names of well-known stars (`milkyway/star_names.csv`, D-026) matched by `hip`:
    name, name_iau, hip, tier, v_mag, x/y/z_pc (heliocentric Galactic), dist_pc and
    `point` (index into points.bin, or null when the star is not exported, e.g. a
    dwarf in the tracer map). Stars missing from the catalogue or beyond dist_max
    are listed in index.json "labels", never dropped silently.

U = round(254 (log10 f + 3) / (log10 0.5 + 3)) clipped to [0, 254], where
f = (r_hi - r_lo) / (2 dist) is the relative distance uncertainty; 255 = r_hi unknown.
The byte carries data, not opacity: the viewer maps it to opacity with a slider.

Version 1 (float32 positions, 17 B/star) is no longer written; the viewer still reads it.

`abs_mag_max` cuts on the extinction-corrected abs_g0 (M5, D-024), abs_g where it is
missing. details.bin keeps the observed g_mag and bp_rp.

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
from .color import build_rgb_table, teff_from_bprp

FORMAT_VERSION = 2
DETAILS_VERSION = 1
DEFAULT_TARGET = 1_500_000
DEFAULT_DIST_MAX_PC = 1250.0       # plan 1.0: the Edenhofer dust map's reach (D-003)
DEFAULT_ALWAYS_G_MAX = 6.0         # naked-eye stars are never thinned out
U_F_MIN, U_F_MAX = 1e-3, 0.5
CLASS_CODES = list(schema.ENUMS["star_class"])
_COLUMNS = ["source_id", "hip", "x_pc", "y_pc", "z_pc", "dist_pc", "r_lo_pc", "r_hi_pc",
            "g_mag", "bp_rp", "bp_rp0", "abs_g", "abs_g0", "star_class"]

_M64 = (1 << 64) - 1
NAMES_FILE = Path(__file__).resolve().parent / "star_names.csv"
LABELS_VERSION = 1


def load_star_names(path=NAMES_FILE):
    """[{hip, name, name_iau, v_mag, tier}] from the curated CSV (comment lines '#')."""
    import csv
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(line for line in f if not line.startswith("#")))
    out = [{"hip": int(r["hip"]), "name": r["name"], "name_iau": r["name_iau"],
            "v_mag": float(r["v_mag"]), "tier": int(r["tier"])} for r in rows]
    hips = [r["hip"] for r in out]
    if len(set(hips)) != len(hips):
        raise ValueError(f"{path}: duplicate hip")
    return out


def export_star_names(dataset_dir, aux_dir, out_path, names_file=NAMES_FILE):
    """Name list for the CSV viewer (D-026): every `star_id` a named star may carry.

    Legacy CSVs are matched by `star_id`, and the old pipeline may hold a star as a
    Hipparcos row or as its Gaia counterpart, so each name lists "HIP <n>" plus the
    Gaia DR3 source_ids that the catalogue (`dataset_dir`) and the archive's
    hipparcos2_best_neighbour table (`aux_dir`) give for that HIP number."""
    names = load_star_names(names_file)
    hips = pa.array([nm["hip"] for nm in names], pa.int32())
    ids = {nm["hip"]: set() for nm in names}
    manifest = storage.open_catalog(dataset_dir)
    for p in manifest["storage"]["partitions"]:
        t = pq.read_table(Path(dataset_dir) / p["path"], columns=["source_id", "hip"])
        t = t.filter(pc.and_(pc.fill_null(pc.is_in(t["hip"], hips), False),
                             pc.is_valid(t["source_id"])))
        for s, hp in zip(t["source_id"].to_pylist(), t["hip"].to_pylist()):
            ids[hp].add(s)
    nb = pq.read_table(Path(aux_dir) / "hip2_best_neighbour.parquet",
                       columns=["source_id", "hip"])
    for s, hp in zip(nb["source_id"].to_pylist(), nb["hip"].to_pylist()):
        if hp in ids:
            ids[hp].add(s)
    out = [{**nm, "star_ids": [f"{schema.HIP_ID_PREFIX}{nm['hip']}"]
            + [f"{schema.GAIA_ID_PREFIX}{s}" for s in sorted(ids[nm["hip"]])]}
           for nm in names]
    doc = {"format": "milkyway-star-names", "version": LABELS_VERSION,
           "source": "IAU Catalog of Star Names (WGSN); see milkyway/star_names.csv",
           "dataset_id": manifest["dataset_id"], "names": out}
    data = json.dumps(doc, ensure_ascii=False, indent=0).encode("utf-8")
    storage._atomic_write(Path(out_path), data)
    return doc


def _labels(named_rows, names, ids, dist_max_pc):
    """labels.json body and its report from the named stars' catalogue rows."""
    t = pa.concat_tables(named_rows) if named_rows else None
    by_hip = {}
    if t is not None:
        hip = t["hip"].to_numpy(zero_copy_only=False)
        for i, hp in enumerate(hip):
            by_hip[int(hp)] = i
        sid = star_ids(t)
    point_of = {int(v): i for i, v in enumerate(ids)}
    labels, missing, beyond = [], [], []
    for nm in names:
        i = by_hip.get(nm["hip"])
        if i is None:
            missing.append(nm["name_iau"])
            continue
        d = float(t["dist_pc"][i].as_py())
        if d > dist_max_pc:
            beyond.append(nm["name_iau"])
            continue
        labels.append({**nm, **{c: round(float(t[c][i].as_py()), 2)
                                for c in ("x_pc", "y_pc", "z_pc")},
                       "dist_pc": round(d, 2), "point": point_of.get(int(sid[i]))})
    return labels, {"n": len(labels), "not_in_catalogue": missing,
                    "beyond_dist_max": beyond,
                    "not_exported": sum(lb["point"] is None for lb in labels)}


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
        m = pc.coalesce(t["abs_g0"], t["abs_g"])
        keep = pc.and_(keep, pc.fill_null(pc.less_equal(m, abs_mag_max), False))
    return keep


def display_rgb(t):
    """(N, 3) uint8 sRGB from bp_rp0, falling back to the observed bp_rp."""
    bprp = pc.coalesce(t["bp_rp0"], t["bp_rp"]).to_numpy(zero_copy_only=False)
    r, g, b, _ = build_rgb_table(teff_from_bprp(bprp.astype(np.float64)))
    return np.stack([np.nan_to_num(np.asarray(c, np.float64), nan=128) for c in (r, g, b)],
                    axis=1).astype(np.uint8)


def export_viewer(dataset_dir, out_dir, *, target=DEFAULT_TARGET,
                  dist_max_pc=DEFAULT_DIST_MAX_PC, always_g_max=DEFAULT_ALWAYS_G_MAX,
                  abs_mag_max=None, names_file=NAMES_FILE):
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
        d = pq.read_table(f, columns=["dist_pc", "abs_g", "abs_g0"])
        n_eligible += pc.sum(_eligible(d, dist_max_pc, abs_mag_max)).as_py() or 0
    frac = min(1.0, target / n_eligible) if n_eligible and target else 1.0
    threshold = np.uint64(min(_M64, int(frac * 2 ** 64)))

    # Pass 2: keep sampled + bright stars, partition by partition; collect the
    # named stars' rows whatever the cut.
    names = load_star_names(names_file)
    name_hips = pa.array([nm["hip"] for nm in names], pa.int32())
    kept, named_rows = [], []
    for f in files:
        t = pq.read_table(f, columns=_COLUMNS, schema=schema.CATALOGUE_SCHEMA)
        named = t.filter(pc.fill_null(pc.is_in(t["hip"], name_hips), False))
        if named.num_rows:
            named_rows.append(named)
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
    rgb = display_rgb(t)
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
    labels, label_report = _labels(named_rows, names, ids, dist_max_pc)
    label_doc = json.dumps({"format": "milkyway-labels", "version": LABELS_VERSION,
                            "source": "IAU Catalog of Star Names (WGSN); see star_names.csv",
                            "labels": labels}, ensure_ascii=False, indent=0).encode("utf-8")
    written = (("points.bin", points), ("details.bin", details), ("labels.json", label_doc))
    for name, data in written:
        storage._atomic_write(out / name, data)

    index = {
        "format": "milkyway-viewer", "format_version": FORMAT_VERSION,
        "dataset_id": manifest["dataset_id"],
        "manifest_sha256": storage._sha256(root / storage.MANIFEST_NAME),
        "n": n, "frame": "heliocentric Galactic, pc: x -> GC, y -> rotation, z -> NGP",
        "position_scale_pc": scale,
        "colour": "sRGB of teff_from_bprp(bp_rp0), bp_rp where bp_rp0 is missing",
        "selection": {"dist_pc_max": dist_max_pc, "abs_mag_max": abs_mag_max,
                      "abs_mag_column": "abs_g0, abs_g where missing",
                      "dataset_selection": manifest["selection"]},
        "sampling": {"method": "splitmix64(id) < f * 2**64", "target": target,
                     "n_eligible": int(n_eligible), "f": frac,
                     "always_g_max": always_g_max, "n_always": int(always.sum()),
                     "order": "always-kept first, then by hash (every prefix is a random sample)"},
        "uncertainty_code": {"f": "(r_hi_pc - r_lo_pc) / (2 dist_pc)", "f_min": U_F_MIN,
                             "f_max": U_F_MAX, "missing": 255,
                             "formula": "round(254 (log10 f + 3) / (log10 f_max + 3))"},
        "class_codes": CLASS_CODES,
        "labels": {"file": "labels.json", **label_report},
        "files": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}
                  for name, data in written},
    }
    storage._atomic_write(out / "index.json", json.dumps(index, indent=1).encode())
    return index

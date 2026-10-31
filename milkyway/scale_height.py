"""Rough scale height of the disc from G and early-K dwarfs (Mapa 1.0, milestone M5; D-025).

Plan 1.0 section 4: cylinder R < 250 pc around the Sun, main-sequence dwarfs with
M_G <= 6 (D-014), exponential profile fitted on 150 < |z| < 450 pc. Everything uses
the dust-corrected colour and magnitude (`bp_rp0`, `abs_g0`, D-024).

Model: n(z) proportional to exp(-|z + z_sun| / h), with z the heliocentric height
(`z_pc`), so the plane sits at z = -z_sun. Within the two fit windows (z in
[150, 450] and [-450, -150] pc, both farther from the plane than z_sun) the density
is a plain exponential on each side, so the unbinned likelihood is

    ln L = sum_i ln n(z_i) - N ln( int_windows n(z) dz )

The shape inside each window fixes h; the north/south ratio, exp(-2 z_sun / h),
fixes z_sun (the "N-S symmetry" assumption of plan section 4). The one-sided fits
(z_sun fixed at 20.8 pc) show how far that assumption is from our data: they are
reported separately, not mixed into the variant range. No scipy: a coarse
grid, then a fine one around the best point; 1-sigma errors from the profile
likelihood (Delta ln L = 0.5).

`variants()` repeats the fit with other windows, colour bins, a fixed z_sun and
without the dust correction; their spread is the honest error bar of an
"orientacyjny" result, far larger than the statistical one.
"""
import json
from pathlib import Path

import numpy as np

from .classify import _MS_ABSG, _MS_BPRP

R_MAX_PC = 250.0
Z_MAX_PC = 500.0
BP_RP0_RANGE = (0.70, 1.10)      # late F/G0 to ~K2 dwarfs (teff_from_bprp: ~6170 to ~5070 K)
ABS_G0_MAX = 6.0                 # D-014: complete to ~515 pc at G < 15 with A_G <= 0.3
MS_DELTA = (-1.0, 1.0)           # mag from the MS ridge; unresolved binaries sit at -0.75
FIT_WINDOW = (150.0, 450.0)
Z_SUN_REF = 20.8                 # Bennett & Bovy 2019, astropy preset v4.0 (D-001)
BIN_PC = 25.0                    # histogram in the figure only; the fit is unbinned

_COLUMNS = ["x_pc", "y_pc", "z_pc", "bp_rp", "abs_g", "bp_rp0", "abs_g0", "dust_flag"]


def load_cylinder(dataset_dir, r_max_pc=R_MAX_PC, z_max_pc=Z_MAX_PC):
    """Columns needed for the fit, for every star in the cylinder (dict of arrays)."""
    import pyarrow as pa
    import pyarrow.compute as pc
    import pyarrow.parquet as pq

    from . import schema, storage
    manifest = storage.open_catalog(dataset_dir)
    root = Path(dataset_dir)
    parts = []
    for p in manifest["storage"]["partitions"]:
        t = pq.read_table(root / p["path"], columns=_COLUMNS, schema=schema.CATALOGUE_SCHEMA)
        r2 = pc.add(pc.multiply(t["x_pc"], t["x_pc"]), pc.multiply(t["y_pc"], t["y_pc"]))
        keep = pc.and_(pc.less(r2, r_max_pc ** 2),
                       pc.less_equal(pc.abs(t["z_pc"]), z_max_pc))
        parts.append(t.filter(keep))
    t = pa.concat_tables(parts)
    out = {c: t[c].to_numpy(zero_copy_only=False) for c in _COLUMNS if c != "dust_flag"}
    out = {c: v.astype(np.float64) for c, v in out.items()}
    out["dust_flag"] = t["dust_flag"].to_numpy(zero_copy_only=False)
    out["dataset_id"] = manifest["dataset_id"]
    return out


def select_dwarfs(cyl, bp_rp0_range=BP_RP0_RANGE, abs_g0_max=ABS_G0_MAX,
                  ms_delta=MS_DELTA, dereddened=True):
    """Boolean mask of the G/early-K dwarf sample (NaN colour or magnitude -> False)."""
    c = cyl["bp_rp0"] if dereddened else cyl["bp_rp"]
    m = cyl["abs_g0"] if dereddened else cyl["abs_g"]
    with np.errstate(invalid="ignore"):
        delta = m - np.interp(c, _MS_BPRP, _MS_ABSG)
        return ((c >= bp_rp0_range[0]) & (c < bp_rp0_range[1]) & (m <= abs_g0_max)
                & (delta >= ms_delta[0]) & (delta <= ms_delta[1]))


def _loglike(z_n, z_s, h, zs, lo, hi, sides=(True, True)):
    """ln L on grids h (H,) x zs (Z,): z_n in [lo, hi], z_s in [-hi, -lo]."""
    h, zs = h[:, None], zs[None, :]
    # north: exp(-(z + zs)/h); south: exp((z + zs)/h) = exp(-(|z| - zs)/h)
    norm = h * (np.exp(-lo / h) - np.exp(-hi / h)) * (
        sides[0] * np.exp(-zs / h) + sides[1] * np.exp(zs / h))
    s_n, s_s = z_n.sum(), np.abs(z_s).sum()
    n_n, n_s = len(z_n), len(z_s)
    lnl = (-(s_n + n_n * zs) / h - (s_s - n_s * zs) / h)
    return lnl - (n_n + n_s) * np.log(norm)


def _interval(grid, prof):
    """(best, lo, hi) where the profile ln L is within 0.5 of its maximum."""
    i = int(np.argmax(prof))
    ok = prof >= prof[i] - 0.5
    return float(grid[i]), float(grid[ok].min()), float(grid[ok].max())


def fit_exponential(z, window=FIT_WINDOW, z_sun=None, side="both"):
    """Fit h (and z_sun unless given) to heliocentric heights z; returns a dict.

    side "north"/"south" uses one window only; z_sun must then be given (one side
    alone cannot tell z_sun from the normalisation)."""
    lo, hi = window
    z = np.asarray(z, np.float64)
    sides = {"both": (True, True), "north": (True, False), "south": (False, True)}[side]
    if side != "both" and z_sun is None:
        raise ValueError("a one-sided fit needs a fixed z_sun")
    z_n, z_s = z[(z >= lo) & (z <= hi)], z[(z <= -lo) & (z >= -hi)]
    z_n, z_s = (z_n if sides[0] else z_n[:0]), (z_s if sides[1] else z_s[:0])
    if (sides[0] and len(z_n) < 10) or (sides[1] and len(z_s) < 10):
        raise ValueError(f"too few stars in the fit windows: {len(z_n)} N, {len(z_s)} S")
    h_grid, zs_grid = np.linspace(50, 1500, 1451), (
        np.array([z_sun], float) if z_sun is not None else np.linspace(-100, 100, 401))
    for step in (None, 0.05):                 # coarse, then fine around the optimum
        lnl = _loglike(z_n, z_s, h_grid, zs_grid, lo, hi, sides)
        i, j = np.unravel_index(np.argmax(lnl), lnl.shape)
        if step is None:
            h_grid = np.arange(max(50, h_grid[i] - 30), h_grid[i] + 30, 0.05)
            if z_sun is None:
                zs_grid = np.arange(zs_grid[j] - 10, zs_grid[j] + 10, 0.05)
    h, h_lo, h_hi = _interval(h_grid, lnl.max(axis=1))
    out = {"h_pc": h, "h_err_pc": (h_hi - h_lo) / 2, "window_pc": list(window), "side": side,
           "n_north": int(len(z_n)), "n_south": int(len(z_s))}
    if z_sun is None:
        zs, zs_lo, zs_hi = _interval(zs_grid, lnl.max(axis=0))
        out.update(z_sun_pc=zs, z_sun_err_pc=(zs_hi - zs_lo) / 2, z_sun_fixed=False)
    else:
        out.update(z_sun_pc=float(z_sun), z_sun_err_pc=0.0, z_sun_fixed=True)
    return out


def variants(cyl):
    """The main fit and its systematic variants: {name: fit dict}."""
    main = select_dwarfs(cyl)
    z = cyl["z_pc"]
    r = np.hypot(cyl["x_pc"], cyl["y_pc"])
    runs = {
        "main": (main, {}),
        "window_100_400": (main, {"window": (100.0, 400.0)}),
        "window_200_500": (main, {"window": (200.0, 500.0)}),
        "z_sun_fixed_20.8": (main, {"z_sun": Z_SUN_REF}),
        "north_only": (main, {"z_sun": Z_SUN_REF, "side": "north"}),
        "south_only": (main, {"z_sun": Z_SUN_REF, "side": "south"}),
        "G_dwarfs_0.70_0.90": (select_dwarfs(cyl, bp_rp0_range=(0.70, 0.90)), {}),
        "early_K_0.90_1.10": (select_dwarfs(cyl, bp_rp0_range=(0.90, 1.10)), {}),
        "R_lt_150": (main & (r < 150), {}),
        "M_G_le_5": (select_dwarfs(cyl, abs_g0_max=5.0), {}),
        "no_dust_correction": (select_dwarfs(cyl, dereddened=False), {}),
    }
    out = {}
    for name, (mask, kw) in runs.items():
        res = fit_exponential(z[mask], **kw)
        res["n_sample"] = int(mask.sum())
        out[name] = res
    return out


def summary(fits):
    """Main h, z_sun, the range of the two-sided variants and the one-sided fits."""
    two = {k: f for k, f in fits.items() if f["side"] == "both"}
    hs = [f["h_pc"] for k, f in two.items() if k != "no_dust_correction"]
    zs = [f["z_sun_pc"] for k, f in two.items()
          if not f["z_sun_fixed"] and k != "no_dust_correction"]
    m = fits["main"]
    return {"h_pc": round(m["h_pc"], 1), "h_stat_err_pc": round(m["h_err_pc"], 1),
            "h_range_pc": [round(min(hs), 1), round(max(hs), 1)],
            "z_sun_pc": round(m["z_sun_pc"], 1), "z_sun_stat_err_pc": round(m["z_sun_err_pc"], 1),
            "z_sun_range_pc": [round(min(zs), 1), round(max(zs), 1)],
            "h_north_pc": round(fits["north_only"]["h_pc"], 1),
            "h_south_pc": round(fits["south_only"]["h_pc"], 1),
            "plan_target_pc": [200, 450]}


def plot(cyl, fit, path):
    """log histogram of the sample's z with the fitted model."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    z = cyl["z_pc"][select_dwarfs(cyl)]
    edges = np.arange(-Z_MAX_PC, Z_MAX_PC + BIN_PC, BIN_PC)
    counts, _ = np.histogram(z, edges)
    mid = (edges[1:] + edges[:-1]) / 2
    h, zs, (lo, hi) = fit["h_pc"], fit["z_sun_pc"], fit["window_pc"]
    in_win = (np.abs(mid) >= lo) & (np.abs(mid) <= hi)
    model = np.exp(-np.abs(mid + zs) / h)
    model *= counts[in_win].sum() / model[in_win].sum()
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.step(mid, counts, where="mid", color="0.3", label=f"karły G/wczesne K (N = {len(z)})")
    ax.plot(mid, model, color="C3",
            label=f"exp(−|z + z☉|/h): h = {h:.0f} pc, z☉ = {zs:.0f} pc")
    for s in (-1, 1):
        ax.axvspan(s * lo, s * hi, color="C0", alpha=0.08)
    ax.set_yscale("log")
    ax.set_xlabel("z heliocentryczne [pc]")
    ax.set_ylabel(f"gwiazd na {BIN_PC:.0f} pc")
    ax.set_title(f"Walec R < {R_MAX_PC:.0f} pc; okno fitu {lo:.0f}–{hi:.0f} pc (niebieskie)")
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def run(dataset_dir, out_dir, log=print):
    """Load, fit all variants, write scale_height.json and scale_height.png."""
    cyl = load_cylinder(dataset_dir)
    if (cyl["dust_flag"] == "none").any():
        raise ValueError("dataset built without the dust map (--no-dust): rebuild it")
    fits = variants(cyl)
    res = {"dataset_id": cyl["dataset_id"], "summary": summary(fits),
           "selection": {"r_max_pc": R_MAX_PC, "z_max_pc": Z_MAX_PC,
                         "bp_rp0_range": list(BP_RP0_RANGE), "abs_g0_max": ABS_G0_MAX,
                         "ms_delta_mag": list(MS_DELTA), "n_cylinder": int(len(cyl["z_pc"]))},
           "model": "n(z) ~ exp(-|z + z_sun| / h), unbinned ML on both fit windows",
           "fits": fits}
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    (out / "scale_height.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    plot(cyl, fits["main"], out / "scale_height.png")
    s = res["summary"]
    log(f"h = {s['h_pc']} +- {s['h_stat_err_pc']} pc (variants {s['h_range_pc']}; "
        f"north {s['h_north_pc']}, south {s['h_south_pc']}), "
        f"z_sun = {s['z_sun_pc']} +- {s['z_sun_stat_err_pc']} pc; "
        f"N = {fits['main']['n_sample']}; wrote {out}")
    return res

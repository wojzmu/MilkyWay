"""Figure rendering. All functions force the non-interactive Agg backend so
they are headless-safe, and write next to the project root via _resolve_path."""
import os

from .config import FAMOUS_STARS, PROJECT_ROOT


def _resolve_path(path):
    """Make a relative filename absolute, at the project root, so output always
    lands somewhere predictable regardless of the current working directory."""
    if not os.path.isabs(path):
        path = os.path.join(PROJECT_ROOT, path)
    return path

def _save(fig, path):
    """Save a figure and report whether it actually reached disk."""
    fig.savefig(path, dpi=130)
    print(f"Saved {path}" if os.path.exists(path)
          else f"WARNING: figure was not written to {path}")

def _label_famous(ax, df, xcol, ycol):
    """Annotate the most famous named stars at (xcol, ycol), with a bordered
    background box so the text stays legible. adjustText repels overlapping
    labels and draws a thin leader line back to each star."""
    if "proper_name" not in df.columns:
        return
    named = df[df["proper_name"].notna() & df[xcol].notna() & df[ycol].notna()]
    if named.empty:                      # e.g. SIMBAD skipped -> all-NaN column
        return
    pat = "|".join(FAMOUS_STARS)
    famous = named[named["proper_name"].astype(str).str.contains(pat, case=False, na=False)]
    label_box = dict(boxstyle="round,pad=0.2", facecolor="#0a0a18",
                     edgecolor="white", linewidth=0.5, alpha=0.75)
    texts = [ax.text(s[xcol], s[ycol], str(s["proper_name"]),
                     fontsize=6, color="white", bbox=label_box)
             for _, s in famous.iterrows()]
    from adjustText import adjust_text
    adjust_text(texts, ax=ax,
                arrowprops=dict(arrowstyle="-", color="white", lw=0.4))
    print(f"  labelled {len(famous)} famous stars")


def plot_hr(merged, path="hr_diagram.png"):
    import matplotlib
    matplotlib.use("Agg")           # save to disk without needing a GUI display
    import matplotlib.pyplot as plt
    path = _resolve_path(path)
    fig, ax = plt.subplots(figsize=(7, 8))
    ax.scatter(merged["bp_rp"], merged["abs_g"],
               c=merged["rgb_hex"].tolist(), s=18, edgecolors="none")
    # Sun reference position (Gaia M_G ~ 4.67, BP-RP ~ 0.82)
    SUN_BP_RP, SUN_ABS_G = 0.82, 4.67
    ax.scatter(SUN_BP_RP, SUN_ABS_G, marker="+", c="yellow",
               s=220, linewidths=2.2, zorder=5, label="Sun")
    ax.annotate("Sun", (SUN_BP_RP, SUN_ABS_G), color="yellow",
                xytext=(8, 4), textcoords="offset points", fontsize=9)
    _label_famous(ax, merged, "bp_rp", "abs_g")
    ax.invert_yaxis()
    ax.set_xlabel("BP - RP"); ax.set_ylabel(r"$M_G$")
    ax.set_title("Nearby-star H-R diagram (true colour)")
    ax.set_facecolor("#0a0a18"); fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


def plot_map(merged, xcol, ycol, xlabel, ylabel, title, path):
    """One face-on 2D map of the stars in heliocentric Galactic coordinates
    (parsec). The Sun sits at the origin; points keep their true-colour RGB."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = _resolve_path(path)
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.set_facecolor("#0a0a18")
    ax.scatter(merged[xcol], merged[ycol],
               c=merged["rgb_hex"].tolist(), s=10, edgecolors="none")
    ax.scatter([0], [0], marker="+", c="yellow", s=140, linewidths=1.4, zorder=5)
    ax.annotate("Sun", (0, 0), xytext=(5, 5), textcoords="offset points",
                fontsize=7, color="yellow")
    _label_famous(ax, merged, xcol, ycol)
    ax.set_aspect("equal")
    ax.set_xlabel(xlabel); ax.set_ylabel(ylabel); ax.set_title(title)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


def plot_maps(merged, xy_path="map_xy.png", xz_path="map_xz.png"):
    """Two 2D star maps: face-on (X-Y, Galactic plane) and edge-on (X-Z)."""
    plot_map(merged, "x_pc", "y_pc",
             "X (pc, toward Galactic centre)", "Y (pc, toward rotation)",
             "Nearby stars - face-on map (X-Y)", xy_path)
    plot_map(merged, "x_pc", "z_pc",
             "X (pc, toward Galactic centre)", "Z (pc, toward NGP)",
             "Nearby stars - edge-on map (X-Z)", xz_path)


def plot_3d(merged, path="map_3d.png", elev=22, azim=-60):
    """Static 3D scatter of the sample in heliocentric Galactic XYZ (parsec).
    Sun at the origin; points keep their true-colour RGB; famous stars labelled.
    adjustText is 2D-only, so 3D labels are placed directly (may overlap)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    path = _resolve_path(path)
    fig = plt.figure(figsize=(9, 9))
    ax = fig.add_subplot(projection="3d")
    fig.patch.set_facecolor("#0a0a18"); ax.set_facecolor("#0a0a18")
    ax.scatter(merged["x_pc"], merged["y_pc"], merged["z_pc"],
               c=merged["rgb_hex"].tolist(), s=8, edgecolors="none", depthshade=True)
    ax.scatter([0], [0], [0], marker="+", c="yellow", s=160, linewidths=1.6)
    ax.text(0, 0, 0, "Sun", color="yellow", fontsize=7)

    if "proper_name" in merged.columns and merged["proper_name"].notna().any():
        pat = "|".join(FAMOUS_STARS)
        famous = merged[merged["proper_name"].notna()
                        & merged["proper_name"].astype(str).str.contains(pat, case=False, na=False)]
        for _, s in famous.iterrows():
            ax.text(s["x_pc"], s["y_pc"], s["z_pc"], str(s["proper_name"]),
                    color="white", fontsize=5)
        print(f"  labelled {len(famous)} famous stars")

    ax.set_box_aspect((1, 1, 1))            # cubic, so distances aren't distorted
    for a in (ax.xaxis, ax.yaxis, ax.zaxis):
        a.label.set_color("white"); a.set_tick_params(colors="white")
    ax.set_xlabel("X (pc)"); ax.set_ylabel("Y (pc)"); ax.set_zlabel("Z (pc)")
    ax.set_title("Nearby stars - 3D (heliocentric Galactic XYZ)", color="white")
    ax.view_init(elev=elev, azim=azim)
    fig.tight_layout()
    _save(fig, path)
    plt.close(fig)


def render_all(cat):
    """Draw every figure (H-R diagram, 2D maps, 3D scatter) from a catalogue."""
    plot_hr(cat)
    plot_maps(cat)
    plot_3d(cat)

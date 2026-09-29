"""Render the slide figures (light and dark SVG) and the animation frames from the notebook results.

Run after executing both notebooks:
    python slides/make_figures.py

The figures use IBM Plex Sans when matplotlib can find it (set FIGURE_FONTS
to a folder with its .ttf files); otherwise the default sans-serif font.
Text is stored as paths, so the SVGs look the same in any browser.

Four figures are animated on the slides. For each of them this script also
writes a background image without the moving parts, and it stores the frames
(from the live runs) with the position of the axes in figures/anim-data.json,
which is copied into index.html (<script id="anim-data">).
"""
import base64
import json
import os
import re
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "slides" / "figures"

if os.environ.get("FIGURE_FONTS"):
    for ttf in Path(os.environ["FIGURE_FONTS"]).glob("*.ttf"):
        font_manager.fontManager.addfont(str(ttf))

# Colours: the validated default data-viz palette (light and dark steps)
# plus the slide ink and hairline tokens. All text is drawn in ink (ink2 = ink): grey text is hard
# to read on a projector; muted grey is kept for reference data (DFT points, curves without SOC).
THEMES = {
    "light": dict(ink="#141a24", ink2="#141a24", muted="#8a909c", grid="#e3e6ec",
                  axis="#c5cad3", wash="#e9edf3", surface="#f8f9fb",
                  blue="#2a78d6", orange="#eb6834", aqua="#1baf7a", red="#e34948",
                  diverging=["#104281", "#3987e5", "#f0efec", "#e66767", "#a82a2a"]),
    "dark": dict(ink="#eef1f6", ink2="#eef1f6", muted="#7d8594", grid="#232a36",
                 axis="#3a4352", wash="#1b2230", surface="#11161f",
                 blue="#3987e5", orange="#d95926", aqua="#199e70", red="#e66767",
                 diverging=["#9ec5f4", "#3987e5", "#383835", "#e66767", "#f4b1b1"]),
}

matplotlib.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["IBM Plex Sans", "Helvetica Neue", "Arial", "DejaVu Sans"],
    "font.size": 15,
    "axes.titlesize": 15,
    "axes.labelsize": 16,
    "xtick.labelsize": 14.5,
    "ytick.labelsize": 14.5,
    "legend.fontsize": 14.5,
    "legend.frameon": False,
    "svg.hashsalt": "wannier-berri-demo",
    "mathtext.fontset": "custom",
    "mathtext.rm": "IBM Plex Sans",
    "mathtext.it": "IBM Plex Sans:italic",
})


def style_axes(ax, t, grid_y=False):
    ax.set_facecolor("none")
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(t["axis"])
    ax.tick_params(colors=t["ink2"], labelcolor=t["ink2"], length=4, width=0.8)
    ax.xaxis.label.set_color(t["ink"])
    ax.yaxis.label.set_color(t["ink"])
    if grid_y:
        ax.yaxis.grid(True, color=t["grid"], lw=0.8)
        ax.set_axisbelow(True)


def legend(ax, t, handles, **kw):
    leg = ax.legend(handles=handles, **kw)
    for text in leg.get_texts():
        text.set_color(t["ink2"])
    return leg


def save(fig, name, theme, bbox="tight", close=True):
    OUT.mkdir(parents=True, exist_ok=True)
    svg = OUT / f"{name}-{theme}.svg"
    fig.savefig(svg, transparent=True, bbox_inches=bbox, metadata={"Date": None, "Creator": None})
    # drop the DOCTYPE line: browsers do not need it and some hosts reject DTDs
    svg.write_text(re.sub(r"<!DOCTYPE[^>]*>\s*", "", svg.read_text(), count=1))
    if os.environ.get("FIGURE_PREVIEW"):  # PNG previews on the slide background
        fig.savefig(Path(os.environ["FIGURE_PREVIEW"]) / f"{name}-{theme}.png", dpi=110,
                    bbox_inches=bbox, facecolor=THEMES[theme]["surface"])
    if close:
        plt.close(fig)


def save_animated(fig, ax, name, theme, moving):
    """Save the full figure and a background without the artists in `moving`, on the same canvas.

    The slides draw the moving parts themselves, frame by frame, in the data coordinates of `ax`.
    Returns where the axes sit in the image: box = (left, top, right, bottom) as fractions of the
    image, w and h in points, and the axis limits."""
    fig.canvas.draw()
    bb = fig.get_tightbbox(fig.canvas.get_renderer()).padded(0.1)   # what bbox_inches="tight" uses
    a, dpi = ax.bbox, fig.dpi
    box = [(a.x0 / dpi - bb.x0) / bb.width, (bb.y1 - a.y1 / dpi) / bb.height,
           (a.x1 / dpi - bb.x0) / bb.width, (bb.y1 - a.y0 / dpi) / bb.height]
    geom = dict(w=round(bb.width * 72, 3), h=round(bb.height * 72, 3), box=[round(v, 5) for v in box],
                xlim=[float(v) for v in ax.get_xlim()], ylim=[float(v) for v in ax.get_ylim()],
                xlog=ax.get_xscale() == "log")
    save(fig, name, theme, bbox=bb, close=False)
    for artist in moving:
        artist.set_visible(False)
    save(fig, f"{name}-bg", theme, bbox=bb)
    return geom


def b64(values, dtype):
    """Integers packed for the page: little-endian bytes, base64."""
    return base64.b64encode(np.ascontiguousarray(values).astype(dtype).tobytes()).decode()


def write_anim_data(anim):
    """Store the animation data as JSON and copy it into index.html."""
    text = json.dumps(anim, separators=(",", ":"))
    (OUT / "anim-data.json").write_text(text)
    page = ROOT / "slides" / "index.html"
    if page.exists():
        html, n = re.subn(r'(<script id="anim-data" type="application/json">).*?(</script>)',
                          lambda m: m.group(1) + text + m.group(2), page.read_text(), flags=re.S)
        if n:
            page.write_text(html)


def path_axes(ax, t, ticks, labels):
    ax.set_xticks(ticks, labels)
    ax.set_xlim(ticks[0], ticks[-1])
    for x in ticks[1:-1]:
        ax.axvline(x, color=t["grid"], lw=0.9, zorder=0)
    ax.tick_params(axis="x", length=0, pad=6, labelcolor=t["ink"])


# --------------------------------------------------------------------------- graphene
def graphene_bands(t, theme):
    d = np.load(ROOT / "01_graphene/results/graphene_bands.npz")
    labels = ["Γ" if str(s) == "G" else str(s) for s in d["labels"]]
    fig, ax = plt.subplots(figsize=(7.9, 5.0))
    ax.axhspan(-2.9, 2.8, color=t["wash"], lw=0, zorder=0)
    ax.text(d["x"][-1] - 0.05, 2.65, "frozen window", ha="right", va="top", color=t["ink2"], fontsize=14.5)
    path_axes(ax, t, d["X"], labels)
    ax.axhline(0, color=t["axis"], lw=0.8, zorder=1)
    ax.plot(d["x"], d["E_dft"], "o", ms=3.6, mew=0, color=t["muted"], zorder=2)
    ax.plot(d["x"], d["E_wann"], color=t["blue"], lw=2.6, zorder=3)
    ax.set_ylim(-9, 6)
    ax.set_ylabel("E − E$_F$ (eV)")
    style_axes(ax, t)
    ax.tick_params(axis="x", length=0)
    legend(ax, t, [Line2D([], [], ls="", marker="o", ms=5, mew=0, color=t["muted"], label="DFT (GPAW)"),
                   Line2D([], [], color=t["blue"], lw=2.2, label="2 Wannier functions")],
           loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2, borderaxespad=0.3)
    save(fig, "graphene-bands", theme)


def graphene_gap(t, theme):
    d = np.load(ROOT / "01_graphene/results/graphene_gap.npz")
    k = d["k"] * 1e5
    fig, ax = plt.subplots(figsize=(6.9, 5.0))
    ax.plot(k, d["E0"] * 1e6, color=t["muted"], lw=1.6)
    moving = ax.plot(k, d["E1"] * 1e6, color=t["blue"], lw=2.2)
    E_g = np.unique(np.round(d["E_gpaw"] * 1e6, 2))
    moving += ax.plot(np.zeros_like(E_g), E_g, "D", ms=7, color=t["orange"], mec=t["surface"], mew=1.5, zorder=5)
    i0 = int(np.argmin(np.abs(k)))
    lo, hi = d["E1"][i0, 1] * 1e6, d["E1"][i0, 2] * 1e6
    moving.append(ax.annotate("", xy=(0.55, lo), xytext=(0.55, hi),
                              arrowprops=dict(arrowstyle="<->", color=t["ink2"], lw=1.2, shrinkA=0, shrinkB=0)))
    moving.append(ax.text(0.7, (lo + hi) / 2, f"{hi - lo:.1f} μeV", va="center", color=t["ink"], fontsize=16))
    label = [-1.6, round(float((lo + hi) / 2), 2)]   # SOC strength of the blue curve; the slide animates it
    moving.append(ax.text(*label, "α = 1", ha="center", va="center", color=t["blue"], fontsize=17,
                          fontweight="semibold"))
    ax.set_xlim(k[0], k[-1])
    ax.set_ylim(-110, 170)
    ax.set_xlabel("k − K  (10$^{-5}$ Å$^{-1}$)")
    ax.set_ylabel("E − E$_F$ (μeV)")
    style_axes(ax, t)
    gpaw_gap = (E_g[-1] - E_g[0])
    legend(ax, t, [Line2D([], [], color=t["muted"], lw=1.6, label="α = 0 (no SOC)"),
                   Line2D([], [], color=t["blue"], lw=2.2, label="with SOC, WannierBerri"),
                   Line2D([], [], ls="", marker="D", ms=7, color=t["orange"],
                          label=f"GPAW, full SOC ({gpaw_gap:.1f} μeV)")],
           loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=2, borderaxespad=0.3)
    geom = save_animated(fig, ax, "graphene-gap", theme, moving)
    return dict(geom=geom, k=np.round(k, 4).tolist(), iK=i0, alpha=np.round(d["alpha"], 3).tolist(),
                nb=int(d["E_alpha"].shape[2]), E=b64(np.round(d["E_alpha"] * 1e7), "<i2"),   # 0.1 ueV
                gpaw=[float(v) for v in E_g], label=label)


def graphene_shc(t, theme):
    d = np.load(ROOT / "01_graphene/results/graphene_shc.npz")
    E = d["E"] * 1e3
    i0 = np.argmin(np.abs(E))
    inside = np.abs(d["sigma1000"] - d["sigma1000"][i0]) < 1e-3
    edge = np.abs(E[inside]).max()
    fig, ax = plt.subplots(figsize=(5.9, 4.0))
    ax.axvspan(-edge, edge, color=t["wash"], lw=0, zorder=0)
    ax.text(0, 0.06, "SOC gap", ha="center", color=t["ink2"], fontsize=14)
    ax.axhline(1, color=t["axis"], lw=0.9, zorder=1)
    ax.text(E[-1], 1.02, "e/2π", ha="right", va="bottom", color=t["ink2"], fontsize=14.5)
    ax.plot(E, d["sigma0"], color=t["muted"], lw=1.6, zorder=2)
    ax.plot(E, d["sigma1000"], color=t["blue"], lw=2.2, zorder=3)
    ax.text(edge + 4, 0.93, f"{d['sigma1000'][i0]:.4f} e/2π", va="top", color=t["ink"], fontsize=15)
    ax.set_xlim(E[0], E[-1])
    ax.set_ylim(-0.05, 1.15)
    ax.set_xlabel("E$_F$ − E$_F^0$ (meV)")
    ax.set_ylabel("σ$^{s_z}_{xy}$ (e/2π)")
    style_axes(ax, t)
    legend(ax, t, [Line2D([], [], color=t["blue"], lw=2.2, label="α = 1000"),
                   Line2D([], [], color=t["muted"], lw=1.6, label="α = 0")],
           loc="upper left")
    save(fig, "graphene-shc", theme)


def graphene_shc_polar(t, theme):
    d = np.load(ROOT / "01_graphene/results/graphene_shc_polar.npz")
    r = d["r"]
    fig, ax = plt.subplots(figsize=(5.9, 4.0))
    ax.axhline(1, color=t["axis"], lw=0.9, zorder=1)
    handles = []
    for key, alpha, color, lw in [("alpha1", 1, t["blue"], 2.4), ("alpha100", 100, t["aqua"], 1.8),
                                  ("alpha1000", 1000, t["orange"], 1.8)]:
        ax.plot(r, d[key], color=color, lw=lw, zorder=3)
        handles.append(Line2D([], [], color=color, lw=lw, label=f"α = {alpha}"))
    legend(ax, t, handles, loc="upper left", bbox_to_anchor=(0.0, 0.93))
    ax.text(r[-1], 1.02, f"{d['alpha1'][-1]:.4f}", ha="right", va="bottom", color=t["ink"], fontsize=15)
    ax.set_xscale("log")
    ax.set_xlim(1e-8, r[-1])
    ax.set_ylim(-0.03, 1.12)
    ax.set_xlabel("disc radius around K, K′ (Å$^{-1}$)")
    ax.set_ylabel("σ$^{s_z}_{xy}$ inside the discs (e/2π)")
    style_axes(ax, t, grid_y=True)
    save(fig, "graphene-shc-polar", theme)


def graphene_shc_grids(t, theme):
    """sigma^sz_xy(E_F) for alpha = 1000 on uniform grids against the grid spacing (backup slide)."""
    d = np.load(ROOT / "01_graphene/results/graphene_shc_convergence.npz")
    sp, sig, nk = d["spacing"], d["sigma"], d["nk"]
    width = 0.036 / 5.8   # peak width Delta / (hbar v_F) in 1/A for the 36 meV gap
    fig, ax = plt.subplots(figsize=(6.0, 4.6))
    ax.axhline(1, color=t["axis"], lw=1.0, zorder=1)
    ax.text(sp.max() * 1.25, 1.12, "e/2π", ha="left", va="bottom", color=t["ink2"], fontsize=14.5)
    ax.axvline(width, color=t["muted"], lw=1.2, dashes=(4, 3), zorder=1)
    ax.text(width / 1.08, 4.9, "peak width\nΔ/ħv$_F$", ha="left", va="top", color=t["ink2"], fontsize=14.5)
    ax.plot(sp, sig, "-", color=t["blue"], lw=2.2, zorder=2)
    ax.plot(sp, sig, "o", ms=8, color=t["blue"], mec=t["surface"], mew=1.2, zorder=3)
    for x, y, n in zip(sp, sig, nk):
        ax.annotate(f"{n}²", (x, y), xytext=(0, 11), textcoords="offset points", ha="center",
                    color=t["ink"], fontsize=14.5)
    ax.set_xscale("log")
    ax.set_xlim(0.03, 0.0018)          # finer grids to the right
    ax.set_xticks([0.02, 0.01, 0.005, 0.0025], ["0.02", "0.01", "0.005", "0.0025"])
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_ylim(0, 5.6)
    ax.set_xlabel("grid spacing (Å$^{-1}$)")
    ax.set_ylabel("σ$^{s_z}_{xy}$(E$_F$) (e/2π)")
    style_axes(ax, t, grid_y=True)
    save(fig, "graphene-shc-grids", theme)


# --------------------------------------------------------------------------- MnTe
def split_breaks(x, *arrays):
    """Insert NaN rows where the path jumps (equal consecutive x), so lines do not join segments."""
    jumps = np.where(np.diff(x) == 0)[0] + 1
    out = [np.insert(np.asarray(x, float), jumps, np.nan)]
    for arr in arrays:
        out.append(np.insert(np.asarray(arr, float), jumps, np.nan, axis=0))
    return out


def mnte_path_labels(d):
    bar = {"M̄": r"$\overline{\mathrm{M}}$", "Γ̄": r"$\overline{\Gamma}$"}
    return ["|".join(bar.get(p, p) for p in str(s).split("|")) for s in d["labels"]]


def mnte_bands(t, theme):
    d = np.load(ROOT / "02_mnte/results/mnte_bands.npz")
    x, ticks, labels = d["x"], d["ticks"], mnte_path_labels(d)
    xb, E_dn, E_up = split_breaks(x, d["E_dn"], d["E_up"])
    fig, ax = plt.subplots(figsize=(8.0, 4.9))
    path_axes(ax, t, ticks, labels)
    ax.plot(xb, E_dn, color=t["blue"], lw=2.6, solid_capstyle="round")
    ax.plot(xb, E_up, color=t["red"], lw=1.2, solid_capstyle="round")
    ax.set_ylim(-6, 0.3)
    ax.set_ylabel("E − E$_F$ (eV)")
    for x0, x1, text in [(ticks[0], ticks[2], "k$_z$ = 0"), (ticks[2], ticks[-1], "k$_z$ = 0.35 Å$^{-1}$")]:
        ax.text((x0 + x1) / 2, 0.45, text, ha="center", va="bottom", color=t["ink2"], fontsize=14.5,
                transform=ax.transData)
    style_axes(ax, t)
    ax.tick_params(axis="x", length=0)
    legend(ax, t, [Line2D([], [], color=t["red"], lw=2, label="spin ↑"),
                   Line2D([], [], color=t["blue"], lw=2.6, label="spin ↓")],
           loc="upper center", ncol=2, bbox_to_anchor=(0.5, -0.07))
    save(fig, "mnte-bands", theme)


def mnte_bands_soc(t, theme):
    d = np.load(ROOT / "02_mnte/results/mnte_bands.npz")
    x, ticks, labels = d["x"], d["ticks"], mnte_path_labels(d)
    E, S = d["E_soc"], d["S"][:, :, 1]
    cmap = LinearSegmentedColormap.from_list("spin", t["diverging"])
    fig, ax = plt.subplots(figsize=(5.9, 5.4))
    path_axes(ax, t, ticks, labels)
    moving = ax.plot(*split_breaks(x, E), color=t["muted"], lw=0.9, zorder=1)
    xs, Es, Ss = np.repeat(x, E.shape[1]), E.ravel(), S.ravel()
    order = np.argsort(np.abs(Ss))
    order = order[np.abs(Ss[order]) > 0.02]  # spin-neutral states stay as the grey line
    sc = ax.scatter(xs[order], Es[order], c=Ss[order], s=8,
                    lw=0, cmap=cmap, vmin=-1, vmax=1, zorder=2, rasterized=True)
    ax.set_ylim(-6, 0.3)
    ax.set_ylabel("E − E$_F$ (eV)")
    style_axes(ax, t)
    ax.tick_params(axis="x", length=0)
    cb = fig.colorbar(sc, ax=ax, pad=0.02, fraction=0.04, ticks=[-1, 0, 1])
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=t["ink2"], labelcolor=t["ink2"], length=0)
    cb.set_label("spin along n", color=t["ink"])
    geom = save_animated(fig, ax, "mnte-bands-soc", theme, moving + [sc])
    r = np.load(ROOT / "02_mnte/results/mnte_soc_rotation.npz")   # n from c (theta = 0) to y (theta = 90)
    keep = r["E"].max(axis=(0, 1)) > -6.5                        # bands that reach the plotted window
    return dict(geom=geom, x=np.round(r["x"], 5).tolist(), theta=r["theta"].tolist(),
                shiftA=[int(v) for v in np.round(r["shift_A"])], nb=int(keep.sum()),
                E=b64(np.round(r["E"][:, :, keep] * 1000), "<i2"),     # meV
                S=b64(np.round(r["S_n"][:, :, keep] * 100), "i1"))


def mnte_splitting(t, theme, size=(6.4, 5.0), name="mnte-splitting", animate=False):
    d = np.load(ROOT / "02_mnte/results/mnte_splitting_map.npz")
    K = float(d["K"])
    cmap = LinearSegmentedColormap.from_list("spin", t["diverging"])
    fig, ax = plt.subplots(figsize=size)
    im = ax.pcolormesh(d["kx"], d["ky"], d["top"], cmap=cmap, vmin=-0.5, vmax=0.5, shading="auto",
                       rasterized=True)
    corners = [(K * np.cos(a), K * np.sin(a)) for a in np.deg2rad(np.arange(0, 361, 60))]
    ax.plot(*zip(*corners), color=t["ink2"], lw=1.2)
    for a in np.deg2rad([0, 60, 120]):
        ax.plot([-K * np.cos(a), K * np.cos(a)], [-K * np.sin(a), K * np.sin(a)], color=t["ink2"], lw=0.8)
    for text, (x, y), ha, va in [("Γ", (0.03, -0.05), "left", "top"), ("K", (K + 0.03, 0), "left", "center"),
                                 ("M", (1.03 * K * np.cos(np.pi / 6) ** 2, 1.03 * K * np.cos(np.pi / 6) / 2), "left", "bottom")]:
        ax.text(x, y, text, ha=ha, va=va, color=t["ink"], fontsize=16)
    ax.set_aspect("equal")
    ax.set_xlim(-1.12 * K, 1.2 * K)
    ax.set_ylim(-0.98 * K, 0.98 * K)
    ax.set_xlabel("k$_x$ (Å$^{-1}$)")
    ax.set_ylabel("k$_y$ (Å$^{-1}$)")
    style_axes(ax, t)
    cb = fig.colorbar(im, ax=ax, pad=0.03, fraction=0.045, ticks=[-0.5, 0, 0.5])
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=t["ink2"], labelcolor=t["ink2"], length=0)
    cb.set_label("E$_\\uparrow$ − E$_\\downarrow$ (eV)", color=t["ink"])
    if not animate:
        save(fig, name, theme)
        return None
    geom = save_animated(fig, ax, name, theme, [im])
    z = np.load(ROOT / "02_mnte/results/mnte_splitting_kz.npz")   # the same map from k_z = 0 to pi/c
    q = np.where(np.isnan(z["maps"]), -128, np.clip(np.round(z["maps"] / 0.5 * 127), -127, 127))
    return dict(geom=geom, kz=np.round(z["kz"], 4).tolist(), rest=float(d["kz"]), n=int(z["maps"].shape[1]),
                extent=[float(z["kx"].min()), float(z["kx"].max()), float(z["ky"].min()), float(z["ky"].max())],
                maps=b64(q, "i1"))




def e_of_p(E, p, target):
    """E_F at which the hole density equals target (log interpolation; p falls as E_F rises)."""
    ok = p > 1e15
    return np.interp(np.log(target), np.log(p[ok][::-1]), E[ok][::-1])


def mnte_ahc(t, theme):
    """sigma_xy at 150 K against E_F - E_v for the three Neel vectors; hole density on the top axis."""
    d = np.load(ROOT / "02_mnte/results/mnte_ahc.npz")
    x, p = d["E"] - float(d["Ev"]), d["holes_y"]
    grid = {k: "×".join(str(n) for n in d[f"NK_{k}"]) for k in "xyz"}
    fig, ax = plt.subplots(figsize=(6.1, 4.45))
    ax.axhline(0, color=t["axis"], lw=0.9, zorder=1)
    ax.plot([0, 0], [-205, 80], color=t["muted"], lw=0.9, dashes=(3, 2), zorder=1)   # band top
    ax.plot(x, d["sigma_x"][:, 2], color=t["orange"], lw=1.8, dashes=(5, 3), zorder=3)
    ax.plot(x, d["sigma_z"][:, 2], color=t["blue"], lw=1.8, dashes=(1.5, 2.5), zorder=3)
    ax.plot(x, d["sigma_y"][:, 2], color=t["aqua"], lw=2.4, zorder=4)
    ax.set_xlim(x[0], 0.06)
    ax.set_ylim(-205, 130)
    ax.set_xlabel("E$_F$ − E$_v$ (eV)")
    ax.set_ylabel("σ$_{xy}$ (S/cm), 150 K")
    style_axes(ax, t, grid_y=True)
    top = ax.secondary_xaxis("top")
    top.set_xticks([e_of_p(x, p, v) for v in (1e20, 1e21, 5e21)], ["10$^{20}$", "10$^{21}$", "5·10$^{21}$"])
    top.set_xlabel("hole density (cm$^{-3}$)", color=t["ink"])
    top.spines["top"].set_color(t["axis"])
    top.tick_params(colors=t["ink2"], labelcolor=t["ink2"], length=4, width=0.8)
    legend(ax, t, [Line2D([], [], color=t["aqua"], lw=2.4, label=f"n $\\parallel$ y   ({grid['y']})"),
                   Line2D([], [], color=t["orange"], lw=1.8, dashes=(5, 3), label=f"n $\\parallel$ x   ({grid['x']})"),
                   Line2D([], [], color=t["blue"], lw=1.8, dashes=(1.5, 2.5), label=f"n $\\parallel$ c   ({grid['z']})")],
           loc="lower right", bbox_to_anchor=(0.86, 0.0), fontsize=13.5)
    save(fig, "mnte-ahc", theme)


def mnte_neel(t, theme):
    """sigma_xy(phi)/sigma_xy(30 deg): computed 0-30 deg, the rest generated by the symmetry relations."""
    d = np.load(ROOT / "02_mnte/results/mnte_neel_scan.npz")
    phi = d["phi"]
    y = d["sigma"][:, np.argmin(np.abs(d["E"] - float(d["E0"])))]
    y = y / y[-1]
    color = t["aqua"]
    fig, ax = plt.subplots(figsize=(6.7, 4.9))
    p = np.linspace(0, 120, 481)
    ax.axhline(0, color=t["axis"], lw=0.9)
    ax.axvspan(30, 120, color=t["wash"], lw=0, zorder=0)
    ax.text(75, -1.3, "from symmetry", color=t["ink2"], fontsize=14.5, ha="center", va="bottom")
    ax.plot(p, np.sin(np.deg2rad(3 * p)), color=t["muted"], lw=1.3, dashes=(4, 3), zorder=1)
    coef, *_ = np.linalg.lstsq(np.sin(np.deg2rad(np.outer(phi, [3, 9, 15]))), y, rcond=None)
    moving = ax.plot(p, np.sin(np.deg2rad(np.outer(p, [3, 9, 15]))) @ coef, color=color, lw=1.8, zorder=2)
    ax.plot(phi, y, "o", ms=6.5, color=color, mec=t["surface"], mew=0.9, zorder=4)
    half = np.concatenate([y, y[::-1][1:]])                  # 0-60 deg from sigma(60 - phi) = sigma(phi)
    ph = np.concatenate([phi, 60 - phi[::-1][1:]])
    gen_phi = np.concatenate([ph[phi.size:], ph[1:] + 60])    # 60-120 deg from sigma(phi + 60) = -sigma(phi)
    gen_y = np.concatenate([half[phi.size:], -half[1:]])
    moving += ax.plot(gen_phi, gen_y, "o", ms=5.5, mfc=t["surface"], mec=color, mew=1.1, zorder=3)
    ax.set_xticks(np.arange(0, 121, 15))
    ax.set_xlim(-2, 122)
    ax.set_ylim(-1.35, 1.25)
    ax.set_xlabel("Néel vector angle φ from the a axis (°)")
    ax.set_ylabel("σ$_{xy}$(φ) / σ$_{xy}$(30°)")
    style_axes(ax, t, grid_y=True)
    legend(ax, t, [Line2D([], [], ls="", marker="o", ms=6.5, color=color, label="computed"),
                   Line2D([], [], color=color, lw=1.8, label="fit: 3φ, 9φ, 15φ"),
                   Line2D([], [], color=t["muted"], lw=1.3, dashes=(4, 3), label="sin 3φ alone")],
           loc="lower left", bbox_to_anchor=(0.0, 1.0), ncol=3, borderaxespad=0.3, columnspacing=1.2,
           handlelength=1.8, fontsize=14)
    geom = save_animated(fig, ax, "mnte-neel", theme, moving)
    pf = np.linspace(0, 120, 241)
    return dict(geom=geom, phi=pf.tolist(), fit=np.round(np.sin(np.deg2rad(np.outer(pf, [3, 9, 15]))) @ coef, 4).tolist(),
                comp=[phi.tolist(), np.round(y, 4).tolist()], gen=[np.round(gen_phi, 3).tolist(), np.round(gen_y, 4).tolist()])


if __name__ == "__main__":
    anim = {}
    for theme, t in THEMES.items():
        for make in (graphene_bands, graphene_shc, graphene_shc_polar, graphene_shc_grids,
                     mnte_bands, mnte_splitting, mnte_ahc):
            make(t, theme)
        # animated figures: the frames and the geometry are the same for both themes
        anim["gap"] = graphene_gap(t, theme)
        anim["soc"] = mnte_bands_soc(t, theme)
        anim["kz"] = mnte_splitting(t, theme, size=(5.3, 4.5), name="mnte-splitting-small", animate=True)
        anim["neel"] = mnte_neel(t, theme)
    anim["palette"] = {theme: dict(diverging=t["diverging"], muted=t["muted"]) for theme, t in THEMES.items()}
    write_anim_data(anim)
    print(f"wrote {len(list(OUT.glob('*.svg')))} figures and the animation data to {OUT}")

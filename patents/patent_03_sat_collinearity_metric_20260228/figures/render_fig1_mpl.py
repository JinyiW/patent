#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render fig_1_sat_projection deterministically with matplotlib.
Two side-by-side panels:
  (a) 物体与候选投影轴 — separated case (δ > 0, ω = 0)
  (b) 重叠情形      — overlapping case (ω > 0, δ = 0; signed δ̃ < 0)
"""

import math
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches
from matplotlib.path import Path

# ---- Chinese font ----
plt.rcParams["font.family"] = ["Noto Sans CJK JP", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 12
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

# Colors
C_A          = "#4A90D9"  # blue: object A
C_A_FILL     = "#4A90D955"
C_B          = "#E8A849"  # orange: object B
C_B_FILL     = "#E8A84955"
C_GREEN      = "#5CB85C"  # δ separation margin
C_PURPLE     = "#9B59B6"  # ω overlap
C_AXIS       = "#444444"
C_TEXT       = "#222222"
C_GRID       = "#BBBBBB"

OUT = "/data/zhuanli/patents/patent_03_sat_collinearity_metric_20260228/figures/fig_1_sat_projection_0.png"

DPI = 160
fig = plt.figure(figsize=(13.0, 7.6), dpi=DPI, facecolor="white")
gs = fig.add_gridspec(1, 2, wspace=0.18, left=0.04, right=0.98, top=0.90, bottom=0.10)

# ============================================================
# Helper: draw a convex polygon (rounded)
# ============================================================
def draw_polygon(ax, pts, edge_color, fill_color, lw=2.2, label=None,
                 label_pos=None, label_color=None):
    poly = patches.Polygon(pts, closed=True, edgecolor=edge_color,
                           facecolor=fill_color, linewidth=lw)
    ax.add_patch(poly)
    if label is not None and label_pos is not None:
        ax.text(label_pos[0], label_pos[1], label,
                ha="center", va="center", fontsize=14, fontweight="bold",
                color=label_color or edge_color)

# Helper: project polygon onto horizontal axis a, returns [l, u]
def project_x(pts):
    xs = [p[0] for p in pts]
    return min(xs), max(xs)

# Helper: draw vertical dashed projection lines from polygon vertices to axis y=axis_y
def draw_proj_lines(ax, pts, axis_y, color):
    for x, y in pts:
        ax.plot([x, x], [min(y, axis_y), max(y, axis_y)],
                ls="--", lw=0.8, color=color, alpha=0.55, zorder=1)

# Helper: draw axis arrow with label
def draw_axis(ax, x0, x1, y, label="$\\mathbf{a}$"):
    ax.annotate("", xy=(x1, y), xytext=(x0, y),
                arrowprops=dict(arrowstyle="-|>", color=C_AXIS, lw=1.6))
    ax.text(x1 + 0.10, y, label, fontsize=14, va="center", color=C_AXIS)

# Helper: draw bracket below axis covering [xa, xb], at y_bracket, label above
def draw_bracket(ax, xa, xb, y, color, label, label_y_offset=-0.40, fontsize=11):
    # bracket as |__|
    ax.plot([xa, xa, xb, xb], [y, y - 0.10, y - 0.10, y],
            color=color, lw=2.2, solid_capstyle="butt")
    ax.text((xa + xb)/2, y - 0.10 + label_y_offset, label,
            ha="center", va="top", fontsize=fontsize, color=color)

# Helper: shade band between [xa, xb] on axis line at y, between y_bot..y_top
def shade_band(ax, xa, xb, y_bot, y_top, color, alpha=0.35):
    ax.add_patch(patches.Rectangle((xa, y_bot), xb - xa, y_top - y_bot,
                                    facecolor=color, alpha=alpha, edgecolor="none"))

# ============================================================
# Panel (a): 分离情形
# ============================================================
ax_a = fig.add_subplot(gs[0])
ax_a.set_xlim(-0.5, 9.5)
ax_a.set_ylim(-3.5, 4.5)
ax_a.set_aspect("equal")
ax_a.axis("off")

# Object A: a convex polygon on the left, upper area
A_pts_a = [(1.2, 2.0), (3.0, 2.6), (3.4, 1.6), (2.4, 1.0), (1.2, 1.2)]
draw_polygon(ax_a, A_pts_a, C_A, C_A_FILL, label="A",
             label_pos=(2.3, 1.8), label_color=C_A)

# Object B: a convex polygon on the right, slightly below
B_pts_a = [(5.0, 2.5), (7.0, 3.0), (7.5, 2.0), (6.4, 1.4), (5.0, 1.6)]
draw_polygon(ax_a, B_pts_a, C_B, C_B_FILL, label="B",
             label_pos=(6.2, 2.2), label_color=C_B)

# Projection axis a at y=0
axis_y_a = -0.6
draw_axis(ax_a, 0.0, 8.6, axis_y_a, label=r"$\mathbf{a}$")

# Projection lines (dashed)
draw_proj_lines(ax_a, A_pts_a, axis_y_a, C_A)
draw_proj_lines(ax_a, B_pts_a, axis_y_a, C_B)

lA_a, uA_a = project_x(A_pts_a)  # 1.2, 3.4
lB_a, uB_a = project_x(B_pts_a)  # 5.0, 7.5

# Projection bands on axis (thin rectangles centered on axis)
band_h = 0.18
shade_band(ax_a, lA_a, uA_a, axis_y_a - band_h/2, axis_y_a + band_h/2, C_A, alpha=0.55)
shade_band(ax_a, lB_a, uB_a, axis_y_a - band_h/2, axis_y_a + band_h/2, C_B, alpha=0.55)

# Brackets I_A, I_B
draw_bracket(ax_a, lA_a, uA_a, axis_y_a - 0.20, C_A,
             r"$I_A=[\,l_A,\;u_A\,]$", label_y_offset=-0.42)
draw_bracket(ax_a, lB_a, uB_a, axis_y_a - 0.20, C_B,
             r"$I_B=[\,l_B,\;u_B\,]$", label_y_offset=-0.42)

# Separation gap (uA_a, lB_a): δ > 0
shade_band(ax_a, uA_a, lB_a, axis_y_a - band_h/2, axis_y_a + band_h/2,
           C_GREEN, alpha=0.45)
# Annotate δ above the gap
gap_mid = (uA_a + lB_a)/2
ax_a.annotate(r"$\delta(\mathbf{a}) = l_B - u_A > 0$",
              xy=(gap_mid, axis_y_a + band_h/2),
              xytext=(gap_mid, axis_y_a + 1.7),
              ha="center", va="bottom", fontsize=12, color=C_GREEN,
              arrowprops=dict(arrowstyle="-|>", color=C_GREEN, lw=1.2))

# Tick marks on axis at lA, uA, lB, uB
for x, txt, col in [(lA_a, r"$l_A$", C_A), (uA_a, r"$u_A$", C_A),
                    (lB_a, r"$l_B$", C_B), (uB_a, r"$u_B$", C_B)]:
    ax_a.plot([x, x], [axis_y_a - 0.05, axis_y_a + 0.05], color=col, lw=1.4)
    ax_a.text(x, axis_y_a + 0.18, txt, ha="center", va="bottom",
              fontsize=10, color=col)

# Title
ax_a.set_title("(a) 分离情形：投影区间不重叠（$\\delta>0,\\;\\omega=0$）",
               fontsize=13, color=C_TEXT, pad=4)

# ============================================================
# Panel (b): 重叠情形
# ============================================================
ax_b = fig.add_subplot(gs[1])
ax_b.set_xlim(-0.5, 9.5)
ax_b.set_ylim(-3.5, 4.5)
ax_b.set_aspect("equal")
ax_b.axis("off")

# Object A: left-mid
A_pts_b = [(2.0, 2.6), (4.5, 3.1), (4.8, 1.9), (3.6, 1.2), (2.0, 1.4)]
draw_polygon(ax_b, A_pts_b, C_A, C_A_FILL, label="A",
             label_pos=(3.2, 2.1), label_color=C_A)

# Object B: overlapping with A on x-axis projection
B_pts_b = [(3.5, 2.5), (6.0, 3.0), (6.4, 1.8), (5.0, 1.1), (3.5, 1.5)]
draw_polygon(ax_b, B_pts_b, C_B, C_B_FILL, label="B",
             label_pos=(5.2, 2.2), label_color=C_B)

axis_y_b = -0.6
draw_axis(ax_b, 0.0, 8.6, axis_y_b, label=r"$\mathbf{a}$")

draw_proj_lines(ax_b, A_pts_b, axis_y_b, C_A)
draw_proj_lines(ax_b, B_pts_b, axis_y_b, C_B)

lA_b, uA_b = project_x(A_pts_b)  # 2.0, 4.8
lB_b, uB_b = project_x(B_pts_b)  # 3.5, 6.4

# Bands
shade_band(ax_b, lA_b, uA_b, axis_y_b - band_h/2, axis_y_b + band_h/2, C_A, alpha=0.55)
shade_band(ax_b, lB_b, uB_b, axis_y_b - band_h/2, axis_y_b + band_h/2, C_B, alpha=0.55)

# Overlap region [lB_b, uA_b]
ov_l = max(lA_b, lB_b)
ov_r = min(uA_b, uB_b)
shade_band(ax_b, ov_l, ov_r, axis_y_b - band_h/2, axis_y_b + band_h/2,
           C_PURPLE, alpha=0.55)

# Brackets I_A, I_B with vertical offset to avoid overlap
draw_bracket(ax_b, lA_b, uA_b, axis_y_b - 0.20, C_A,
             r"$I_A=[\,l_A,\;u_A\,]$", label_y_offset=-0.42)
draw_bracket(ax_b, lB_b, uB_b, axis_y_b - 0.95, C_B,
             r"$I_B=[\,l_B,\;u_B\,]$", label_y_offset=-0.42)

# Annotate ω with text placed in upper-right empty region (避免与多边形重叠)
ov_mid = (ov_l + ov_r)/2
ax_b.annotate(r"$\omega(\mathbf{a})=\min(u_A,u_B)-\max(l_A,l_B)$",
              xy=(ov_mid, axis_y_b + band_h/2 + 0.04),
              xytext=(8.8, 4.0),
              ha="right", va="top", fontsize=12, color=C_PURPLE,
              arrowprops=dict(arrowstyle="-|>", color=C_PURPLE, lw=1.2,
                              connectionstyle="arc3,rad=-0.25"))

# Note about δ vs δ̃
ax_b.text((lA_b + uB_b)/2, axis_y_b - 2.2,
          r"$\delta(\mathbf{a}) = 0$    （非负版）",
          ha="center", va="center", fontsize=11, color=C_GREEN)
ax_b.text((lA_b + uB_b)/2, axis_y_b - 2.7,
          r"$\widetilde{\delta}(\mathbf{a}) = \max(l_A,l_B) - \min(u_A,u_B) < 0$  （有符号版）",
          ha="center", va="center", fontsize=11, color="#8B4FAA")

# Tick marks
for x, txt, col in [(lA_b, r"$l_A$", C_A), (uA_b, r"$u_A$", C_A),
                    (lB_b, r"$l_B$", C_B), (uB_b, r"$u_B$", C_B)]:
    ax_b.plot([x, x], [axis_y_b - 0.05, axis_y_b + 0.05], color=col, lw=1.4)
    ax_b.text(x, axis_y_b + 0.18, txt, ha="center", va="bottom",
              fontsize=10, color=col)

ax_b.set_title("(b) 重叠情形：投影区间相交（$\\omega>0,\\;\\delta=0$ ；可用 $\\widetilde{\\delta}<0$ 反映重叠深度）",
               fontsize=12.5, color=C_TEXT, pad=4)

# ============================================================
# Bottom legend
# ============================================================
legend_y = 0.04
items = [
    (C_A,      "对象 A 投影区间 $I_A$"),
    (C_B,      "对象 B 投影区间 $I_B$"),
    (C_GREEN,  "分离裕量 $\\delta(\\mathbf{a})>0$"),
    (C_PURPLE, "重叠长度 $\\omega(\\mathbf{a})>0$"),
]
xs = np.linspace(0.10, 0.78, 4)
for x, (col, txt) in zip(xs, items):
    fig.add_artist(patches.Rectangle((x, legend_y), 0.025, 0.025,
                                      transform=fig.transFigure,
                                      facecolor=col, edgecolor="#555555", lw=0.8))
    fig.text(x + 0.032, legend_y + 0.008, txt,
             fontsize=11, color=C_TEXT, va="center")

# Title
fig.suptitle("图1 分离轴定理（SAT）投影原理示意图",
             fontsize=15, color=C_TEXT, y=0.97)

fig.savefig(OUT, dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.18)
plt.close(fig)

from PIL import Image
print(f"saved {OUT} -> {Image.open(OUT).size}")

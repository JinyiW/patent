#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Render fig_2_detection_objects deterministically with matplotlib.
Two-panel figure:
  (a) edge-chain sliding window
  (b) face-cluster (面片簇) BFS expansion on a triangular mesh
"""

import math
import os
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import patches, font_manager
from matplotlib.collections import PolyCollection, LineCollection

# ---- Chinese font ----
CJK_NAME = "Noto Sans CJK JP"  # supports 簇 / 面 / 片 / 链 / 跳 / 重叠 / 中心
plt.rcParams["font.family"] = [CJK_NAME, "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False
plt.rcParams["font.size"] = 12
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["ps.fonttype"] = 42

# Color palette (consistent with project STYLE_PROMPT)
C_BLUE_DEEP   = "#1F5AA8"
C_BLUE_MED    = "#4A90D9"
C_BLUE_LIGHT  = "#A6CCEB"
C_ORANGE      = "#E8A849"
C_GREEN       = "#5CB85C"
C_PURPLE      = "#9B59B6"
C_GRAY        = "#F0F0F0"
C_GRAY_TEXT   = "#888888"
C_TEXT        = "#222222"

OUT = "/data/zhuanli/patents/patent_03_sat_collinearity_metric_20260228/figures/fig_2_detection_objects_0.png"

# Canvas: 1536x1024 → 12.8 x 8.53 inch @ 120 dpi
DPI = 160
fig = plt.figure(figsize=(12.8, 8.53), dpi=DPI, facecolor="white")
gs = fig.add_gridspec(2, 1, height_ratios=[1.0, 1.6], hspace=0.32,
                      left=0.04, right=0.96, top=0.94, bottom=0.04)

# ============================================================
# Panel (a): 边链滑动窗口
# ============================================================
ax_a = fig.add_subplot(gs[0])
ax_a.set_xlim(-0.6, 11.6)
ax_a.set_ylim(-3.4, 1.6)
ax_a.set_aspect("auto")
ax_a.axis("off")

# vertices on x = 0..10
n_v = 11
vx = np.arange(n_v, dtype=float)
vy = np.zeros(n_v)

# edges between consecutive vertices
for k in range(n_v - 1):
    ax_a.plot([vx[k], vx[k+1]], [vy[k], vy[k+1]], color="#444444", lw=1.6, zorder=2)
# vertices
ax_a.scatter(vx, vy, s=55, color="#222222", zorder=3)
# edge labels e_1 ... e_10
for k in range(n_v - 1):
    ax_a.text((vx[k]+vx[k+1])/2, 0.32, fr"$e_{{{k+1}}}$",
              ha="center", va="bottom", fontsize=11, color=C_TEXT)

# Window brackets
def draw_bracket(ax, x_left, x_right, y_top, y_bot, color, label, label_side="right"):
    rect = patches.FancyBboxPatch(
        (x_left, y_bot), x_right - x_left, y_top - y_bot,
        boxstyle="round,pad=0.06,rounding_size=0.18",
        linewidth=2.5, edgecolor=color, facecolor=color + "22"  # tint
    )
    ax.add_patch(rect)
    if label_side == "right":
        ax.text(x_right + 0.15, (y_top + y_bot)/2, label,
                ha="left", va="center", fontsize=12, color=color, fontweight="bold")

# Each bracket spans from leftmost vertex of first edge to rightmost vertex of last edge
# C1: edges e1..e4 → from v0(x=0) to v4(x=4)
brackets = [
    (0, 4,  -0.55, -1.05, C_BLUE_MED,  r"$C_1=(e_1,e_2,e_3,e_4)$"),
    (2, 6,  -1.20, -1.70, C_ORANGE,    r"$C_2=(e_3,e_4,e_5,e_6)$"),
    (4, 8,  -1.85, -2.35, C_GREEN,     r"$C_3=(e_5,e_6,e_7,e_8)$"),
    (6, 10, -2.50, -3.00, C_PURPLE,    r"$C_4=(e_7,e_8,e_9,e_{10})$"),
]
for xl, xr, yt, yb, col, lab in brackets:
    draw_bracket(ax_a, xl - 0.08, xr + 0.08, yt, yb, col, lab)

# Highlight overlap C1∩C2 = edges e3,e4 (x = 2..4)
ax_a.add_patch(patches.Rectangle((2, -0.08), 2, 0.16,
                                  facecolor="#888888", alpha=0.35, edgecolor="none", zorder=1))
ax_a.annotate("重叠 2 条", xy=(3, 0.04), xytext=(3, 0.95),
              ha="center", va="bottom", fontsize=11, color="#444444",
              arrowprops=dict(arrowstyle="-|>", color="#444444", lw=1.2,
                              connectionstyle="arc3,rad=0.0"))

ax_a.set_title(r"(a) 边链 $C_j$（窗口长度 $L=4$，滑动步长 $\Delta L=2$；相邻边链共享 2 条边）",
               fontsize=13, color=C_TEXT, pad=8)

# ============================================================
# Panel (b): 面片簇 BFS — 真三角网格，颜色按 BFS 跳数
# ============================================================
ax_b = fig.add_subplot(gs[1])
ax_b.set_aspect("equal")
ax_b.axis("off")

# Build a simple triangulated hexagonal patch around origin.
# We generate a 5x5 lattice of points in axial coords, then extract triangles.
# Simpler: use a "fan" of equilateral triangles around a central triangle.

# We'll construct an explicit set of triangles with known BFS hop labels so we
# can color each triangle correctly. Strategy:
#   - central triangle f0 (hop 0)
#   - 3 edge-neighbor triangles f1, f2, f3 (hop 1)
#   - 6 next-layer triangles (hop 2)
#   - outer triangles (hop ∞ → light gray)
# We embed these on a regular triangular lattice by composing equilateral triangles.

# Use barycentric-ish layout: build a hex grid of small equilateral triangles
# centered on origin, then label each triangle by BFS hop from f0.

# Generate triangulated hexagon (radius R rings of triangles)
def gen_hex_triangulation(R):
    """
    Return list of triangles (each as 3 (x,y) tuples) covering a hexagonal region.
    R = number of rings.
    """
    h = math.sqrt(3) / 2
    tris = []
    # Walk over a square index grid (i,j), generate two triangles per cell
    for i in range(-R, R+1):
        for j in range(-R, R+1):
            # vertex coordinates at axial-style position
            # use rectangular grid of equilateral triangles:
            #   vertex (i,j) is at (i + j/2, j*h)
            def vert(p, q):
                return (p + q*0.5, q*h)
            v00 = vert(i, j)
            v10 = vert(i+1, j)
            v01 = vert(i, j+1)
            v11 = vert(i+1, j+1)
            # two triangles: upward (v00, v10, v01) and downward (v10, v11, v01)
            t1 = (v00, v10, v01)
            t2 = (v10, v11, v01)
            for t in (t1, t2):
                cx = sum(p[0] for p in t)/3
                cy = sum(p[1] for p in t)/3
                if math.hypot(cx, cy) < R + 0.4:
                    tris.append(t)
    return tris

R = 4
tris = gen_hex_triangulation(R)

# Build adjacency: two triangles are neighbors if they share exactly 2 vertices
def tri_key(t):
    return tuple(sorted([(round(p[0], 4), round(p[1], 4)) for p in t]))

key2idx = {tri_key(t): i for i, t in enumerate(tris)}
adj = [[] for _ in tris]
for i, t in enumerate(tris):
    vs = set([(round(p[0], 4), round(p[1], 4)) for p in t])
    for j in range(i+1, len(tris)):
        vs2 = set([(round(p[0], 4), round(p[1], 4)) for p in tris[j]])
        if len(vs & vs2) == 2:
            adj[i].append(j)
            adj[j].append(i)

# Find center triangle (closest to origin AND upward-pointing)
def upward(t):
    ys = [p[1] for p in t]
    return ys.count(min(ys)) == 2  # two vertices on bottom

best = None
best_d = 1e9
for i, t in enumerate(tris):
    cx = sum(p[0] for p in t)/3
    cy = sum(p[1] for p in t)/3
    d = math.hypot(cx, cy)
    if upward(t) and d < best_d:
        best_d = d; best = i
f0_idx = best

# BFS from f0
hop = {f0_idx: 0}
frontier = [f0_idx]
while frontier:
    nxt = []
    for u in frontier:
        for v in adj[u]:
            if v not in hop:
                hop[v] = hop[u] + 1
                nxt.append(v)
    frontier = nxt

# Color by hop
def hop_color(h):
    if h == 0:  return C_BLUE_DEEP
    if h == 1:  return C_BLUE_MED
    if h == 2:  return C_BLUE_LIGHT
    return C_GRAY

face_polys = []
face_colors = []
for i, t in enumerate(tris):
    h = hop.get(i, 99)
    face_polys.append(t)
    face_colors.append(hop_color(h))

pc = PolyCollection(face_polys, facecolors=face_colors,
                     edgecolors="white", linewidths=1.6)
ax_b.add_collection(pc)

# Labels f_0..f_9 inside triangles (hop ≤ 2)
# Order by hop, then by angle around f0 for stable labeling
f0_center = (sum(p[0] for p in tris[f0_idx])/3,
             sum(p[1] for p in tris[f0_idx])/3)

ranked = []
for i, t in enumerate(tris):
    h = hop.get(i, 99)
    if h > 2: continue
    cx = sum(p[0] for p in t)/3
    cy = sum(p[1] for p in t)/3
    ang = math.atan2(cy - f0_center[1], cx - f0_center[0])
    ranked.append((h, ang, i, cx, cy))
ranked.sort()

label_idx = 0
for h, ang, i, cx, cy in ranked:
    if h == 0:
        lbl = r"$f_0$"
    elif h == 1:
        # f_1, f_2, f_3 in angular order
        # count how many hop=1 already labeled
        cnt = sum(1 for k in range(label_idx) if ranked[k][0] == 1) + 1
        lbl = fr"$f_{{{cnt}}}$"  # cnt is 1,2,3
    else:  # hop == 2
        cnt = sum(1 for k in range(label_idx) if ranked[k][0] == 2) + 1
        lbl = fr"$f_{{{cnt+3}}}$"  # 4..
    text_color = "white" if h <= 1 else C_TEXT
    ax_b.text(cx, cy, lbl, ha="center", va="center",
              fontsize=10, color=text_color, fontweight="bold")
    label_idx += 1

# Set view
xs = [p[0] for t in tris for p in t]
ys = [p[1] for t in tris for p in t]
ax_b.set_xlim(min(xs) - 0.5, max(xs) + 3.5)  # leave room on right for legend
ax_b.set_ylim(min(ys) - 0.7, max(ys) + 0.7)

# Arrow + 中心面 annotation
ax_b.annotate("中心面 $f_0$",
              xy=(f0_center[0], f0_center[1]),
              xytext=(f0_center[0] - 1.4, f0_center[1] - 1.6),
              fontsize=11, color=C_TEXT,
              arrowprops=dict(arrowstyle="-|>", color=C_TEXT, lw=1.2))

# Legend on the right
legend_x = max(xs) + 1.3
legend_top = max(ys) + 0.2
labels = [
    ("中心面 $f_0$",   C_BLUE_DEEP),
    ("第 1 跳邻面",     C_BLUE_MED),
    ("第 2 跳邻面",     C_BLUE_LIGHT),
    ("外部（未纳入）", C_GRAY),
]
for k, (txt, col) in enumerate(labels):
    sq_y = legend_top - k * 0.85
    ax_b.add_patch(patches.Rectangle((legend_x, sq_y - 0.3), 0.5, 0.5,
                                      facecolor=col, edgecolor="#444444", lw=0.8))
    ax_b.text(legend_x + 0.7, sq_y - 0.05, txt,
              ha="left", va="center", fontsize=11, color=C_TEXT)

ax_b.set_title(r"(b) 面片簇 $P_j$（中心面 $f_0$ 出发，对偶图广度优先扩张 $r=2$，约 10 个三角面片）",
               fontsize=13, color=C_TEXT, pad=8)

# ----- Footer note -----
fig.text(0.5, 0.005,
         r"图中 $L$ = 边链窗口长度，$\Delta L$ = 滑动步长；$r$ = 对偶图扩张步数（跳数，非欧氏半径）",
         ha="center", va="bottom", fontsize=10, color=C_GRAY_TEXT)

# Save
fig.savefig(OUT, dpi=DPI, facecolor="white", bbox_inches="tight", pad_inches=0.18)
plt.close(fig)

# Verify size
from PIL import Image
img = Image.open(OUT)
print(f"saved {OUT} -> {img.size}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
代码生成 图4 正常接触与粘连区分的三重抑制规则（流程图）。
- 顶会论文风配色，白底。
- 串行级联布局：主"否"路径沿中线竖直向下；命中(是)横向进入处理动作，
  再统一汇入右侧竖直绿色轨道 → 正常接触。所有连线均为正交（横平竖直）。
- 所有图内文字使用简体中文；"属于"等关系一律用中文，不用 ∈ 符号。
输出: fig_4_valid_contact_0.png
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon
from matplotlib.lines import Line2D
from matplotlib import font_manager

for cand in ["Arial Unicode MS", "Hiragino Sans GB", "Songti SC", "STHeiti"]:
    if any(f.name == cand for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.family"] = cand
        break
plt.rcParams["axes.unicode_minus"] = False

C_BLUE   = "#4A90D9"
C_ORANGE = "#E8A849"
C_GREEN  = "#5CB85C"
C_PURPLE = "#9B59B6"
C_GRAY   = "#F0F0F0"
C_EDGE   = "#3A3A3A"
C_TEXT   = "#1F2A36"
C_RED    = "#C0504D"

fig, ax = plt.subplots(figsize=(15.5, 13))
ax.set_xlim(0, 100)
ax.set_ylim(0, 100)
ax.axis("off")
fig.patch.set_facecolor("white")

# 列中心
NOTE_X = 13      # 左侧旁注列
MAIN_X = 43      # 主级联列（判断节点 + 否路径）
ACT_X  = 73      # 命中后处理动作列
RAIL_X = 92      # 右侧"正常接触"竖直汇流轨道

# 行中心（均匀间隔 17）
Y_TOP = 92
Y_PEN = 82
R_Y   = [67, 50, 33]   # 规则一/二/三
Y_BOT = 11


def box(cx, cy, w, h, text, fc, tc="white", fs=15, bold=True, ec=C_EDGE):
    p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                       boxstyle="round,pad=0.02,rounding_size=0.9", linewidth=1.7,
                       facecolor=fc, edgecolor=ec, zorder=3)
    ax.add_patch(p)
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=tc,
            zorder=4, fontweight="bold" if bold else "normal", linespacing=1.4)


def diamond(cx, cy, w, h, text, fc=C_BLUE, tc="white", fs=14):
    pts = [(cx, cy + h / 2), (cx + w / 2, cy), (cx, cy - h / 2), (cx - w / 2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=fc, edgecolor=C_EDGE,
                         linewidth=1.7, zorder=3))
    ax.text(cx, cy, text, ha="center", va="center", fontsize=fs, color=tc,
            zorder=4, fontweight="bold", linespacing=1.35)


def note(cx, cy, w, h, title, body, fs=12.5):
    p = FancyBboxPatch((cx - w / 2, cy - h / 2), w, h,
                       boxstyle="round,pad=0.02,rounding_size=0.7", linewidth=1.2,
                       facecolor=C_GRAY, edgecolor="#B8B8B8", linestyle="--", zorder=2)
    ax.add_patch(p)
    ax.text(cx, cy + h / 2 - 1.7, title, ha="center", va="center", fontsize=fs + 1.5,
            color=C_TEXT, fontweight="bold", zorder=4)
    ax.text(cx, cy - 1.0, body, ha="center", va="center", fontsize=fs,
            color="#555555", zorder=4, linespacing=1.4)


def vseg(x, y1, y2, color=C_EDGE, lw=2.2, head=False, ls="-"):
    if head:
        from matplotlib.patches import FancyArrowPatch
        ax.add_patch(FancyArrowPatch((x, y1), (x, y2), arrowstyle="-|>",
                     mutation_scale=22, linewidth=lw, color=color, zorder=2,
                     shrinkA=0, shrinkB=0, linestyle=ls))
    else:
        ax.add_line(Line2D([x, x], [y1, y2], color=color, linewidth=lw, zorder=2,
                    solid_capstyle="round", linestyle=ls))


def hseg(x1, x2, y, color=C_EDGE, lw=2.2, head=False, ls="-"):
    if head:
        from matplotlib.patches import FancyArrowPatch
        ax.add_patch(FancyArrowPatch((x1, y), (x2, y), arrowstyle="-|>",
                     mutation_scale=22, linewidth=lw, color=color, zorder=2,
                     shrinkA=0, shrinkB=0, linestyle=ls))
    else:
        ax.add_line(Line2D([x1, x2], [y, y], color=color, linewidth=lw, zorder=2,
                    solid_capstyle="round", linestyle=ls))


def lbl(x, y, text, color, fs=14):
    ax.text(x, y, text, ha="center", va="center", fontsize=fs, color=color,
            fontweight="bold", bbox=dict(boxstyle="round,pad=0.22", fc="white", ec="none"),
            zorder=6)


# ── 标题 ──
ax.text(50, 98, "图4  正常接触与粘连区分的三重抑制规则", ha="center", va="center",
        fontsize=21, fontweight="bold", color=C_TEXT)

DW, DH = 30, 11   # 规则菱形尺寸
PW2 = 13          # 菱形左右顶点到中心距离 = DW/2 +余量 用于连线
HALF = DW / 2

# ── 顶部两个主节点 ──
box(MAIN_X, Y_TOP, 30, 5.6, "检测到近距离接触", C_BLUE, fs=17)
diamond(MAIN_X, Y_PEN, 27, 9.6, "是否为粘连？\n($S_t \\geq \\gamma_s$)", C_BLUE, fs=15)

# ── 三个规则菱形（名称作为左上方标签）──
rule_meta = [
    ("规则一：白名单豁免", "部件对属于\n白名单集合？"),
    ("规则二：滑移释放",   "累计切向滑移\n> $\\tau_s^{rel}$ ？"),
    ("规则三：动作上下文", "处于高密接触\n动作区间？"),
]
for cy, (name, q) in zip(R_Y, rule_meta):
    # 规则名放在菱形上方、紧贴，居中（白底，立于来线之上不被遮挡）
    diamond(MAIN_X, cy, DW, DH, q, C_BLUE, fs=14)
    ax.text(MAIN_X, cy + DH / 2 + 1.9, name, ha="center", va="center",
            fontsize=15, fontweight="bold", color=C_TEXT, zorder=6,
            bbox=dict(boxstyle="round,pad=0.2", fc="white", ec="#CFD8E3"))

box(MAIN_X, Y_BOT, 27, 6.6, "判定为粘连异常\n（触发告警）", C_ORANGE, tc="#3A2A00", fs=17)

# ── 命中后处理动作（紫色）──
box(ACT_X, R_Y[0], 27, 8.0, "当前帧属于该三元组的\n动作标签与时间区间\n→ 提升阈值 $\\gamma_s'$ 或屏蔽",
    C_PURPLE, fs=12.5)
box(ACT_X, R_Y[1], 27, 7.0, "重置持续帧计数 $k_t\\!\\leftarrow\\!0$\n粘连分数乘衰减因子",
    C_PURPLE, fs=13)
box(ACT_X, R_Y[2], 27, 7.0, "采用更严格持续帧阈值\n$\\tau_t' = 2\\tau_t$ 后重新判定",
    C_PURPLE, fs=13)

# ── 正常接触（右下，绿色）──
GREEN_BOX_X = 79
box(GREEN_BOX_X, Y_BOT, 27, 6.6, "判定为正常接触\n（命中任一规则即豁免）", C_GREEN, fs=16)

# ── 左侧旁注，虚线连到对应规则 ──
notes = [
    ("三元组示例", "(部件A, 部件B, 动作标签)\n手掌-大腿, 蹲踞动作,\n帧10-50"),
    ("物理意义", "确保“短暂粘住后滑开”\n不被累积为粘连告警"),
    ("区间与来源", "示例：蹲踞、布料折叠\n来源：骨骼姿态特征自动\n识别 / 预标注动作标签"),
]
for cy, (t, b) in zip(R_Y, notes):
    note(NOTE_X, cy, 24, DH, t, b)
    hseg(NOTE_X + 12, MAIN_X - HALF, cy, color="#9AA7B4", lw=1.3, ls="--")

# ── 主"否"竖直路径 ──
vseg(MAIN_X, Y_PEN - 4.8, R_Y[0] + DH / 2, color=C_EDGE, head=True)
lbl(MAIN_X + 9.5, (Y_PEN - 4.8 + R_Y[0] + DH / 2) / 2 + 0.3, "是（疑似粘连）", C_EDGE, fs=13)
vseg(MAIN_X, R_Y[0] - DH / 2, R_Y[1] + DH / 2, color=C_RED, head=True)
lbl(MAIN_X - 3.5, (R_Y[0] - DH / 2 + R_Y[1] + DH / 2) / 2, "否", C_RED)
vseg(MAIN_X, R_Y[1] - DH / 2, R_Y[2] + DH / 2, color=C_RED, head=True)
lbl(MAIN_X - 3.5, (R_Y[1] - DH / 2 + R_Y[2] + DH / 2) / 2, "否", C_RED)
vseg(MAIN_X, R_Y[2] - DH / 2, Y_BOT + 3.3, color=C_RED, head=True)
lbl(MAIN_X, (R_Y[2] - DH / 2 + Y_BOT + 3.3) / 2, "否（三规则均未命中）", C_RED, fs=13)

# ── 命中分支：菱形 →(是) 处理动作（横向）──
for cy in R_Y:
    hseg(MAIN_X + HALF, ACT_X - 13.5, cy, color=C_GREEN, head=True)
    lbl((MAIN_X + HALF + ACT_X - 13.5) / 2, cy + 1.9, "是", C_GREEN)

# ── 右侧绿色竖直汇流轨道（全程正交）──
# 顶部"否（非粘连）"汇入
hseg(MAIN_X + 13.5, RAIL_X, Y_PEN, color=C_GREEN, lw=2.3)
lbl((MAIN_X + 13.5 + RAIL_X) / 2, Y_PEN + 2.0, "否（非粘连）", C_GREEN, fs=13)
# 三处理动作右端 → 轨道
for cy in R_Y:
    hseg(ACT_X + 13.5, RAIL_X, cy, color=C_GREEN, lw=2.3)
# 竖直轨道
vseg(RAIL_X, Y_PEN, Y_BOT, color=C_GREEN, lw=2.5)
# 轨道底 → 正常接触框
hseg(RAIL_X, GREEN_BOX_X + 13.5, Y_BOT, color=C_GREEN, lw=2.3, head=True)

# ── 图例 ──
leg = [(C_BLUE, "判断节点"), (C_PURPLE, "命中后处理动作"),
       (C_GREEN, "正常接触路径（命中抑制规则）"), (C_ORANGE, "粘连异常（均未命中）")]
for i, (c, t) in enumerate(leg):
    xx = 7 + i * 24
    yy = 3.5
    ax.add_patch(FancyBboxPatch((xx, yy - 1.3), 3.0, 2.6,
                 boxstyle="round,pad=0.02,rounding_size=0.5",
                 facecolor=c, edgecolor=C_EDGE, linewidth=1.0, zorder=3))
    ax.text(xx + 3.8, yy, t, ha="left", va="center", fontsize=13, color=C_TEXT)

plt.tight_layout()
out = os.path.join(os.path.dirname(__file__), "fig_4_valid_contact_0.png")
fig.savefig(out, dpi=150, bbox_inches="tight", facecolor="white", pad_inches=0.18)
print("saved:", out)

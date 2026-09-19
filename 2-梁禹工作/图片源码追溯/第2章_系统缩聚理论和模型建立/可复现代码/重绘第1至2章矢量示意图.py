"""第1至2章九张非数值示意图的可复现矢量重绘。

这是新建重绘代码，不冒充梁禹原始代码；图2-9由独立MATLAB入口原生导出。几何、自由度编号、流程与子结构
边界均依据《梁禹手稿》第19、21、25、28--31页、图书馆 DOCX 原始嵌入对象
以及答辩 PPT 第7、10--13、25页核对。
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle


项目根 = Path(__file__).resolve().parents[3]
章根 = Path(__file__).resolve().parents[1]
第1章根 = 项目根 / "figure" / "第1章_绪论"
样式路径 = 项目根 / "figure" / "公共绘图工具" / "科研绘图样式.py"
规则 = importlib.util.spec_from_file_location("科研绘图样式", 样式路径)
样式 = importlib.util.module_from_spec(规则)
assert 规则.loader is not None
规则.loader.exec_module(样式)

蓝 = 样式.颜色["Craig-Bampton"]
红 = 样式.颜色["Guyan"]
绿 = 样式.颜色["绿色"]
青 = 样式.颜色["青色"]
黄 = 样式.颜色["黄色"]
灰 = 样式.颜色["灰色"]
黑 = 样式.颜色["原结构"]


def _canvas(width=7.48, height=4.5, xlim=(0, 10), ylim=(0, 6)):
    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    return fig, ax


def _box(ax, xy, wh, text, *, ec=黑, fc="white", lw=0.8, ls="-", fontsize=9):
    x, y = xy
    w, h = wh
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, linewidth=lw, linestyle=ls))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)


def _arrow(ax, a, b, *, color=黑, lw=0.9, style="-|>", mutation=9, connectionstyle="arc3"):
    ax.add_patch(
        FancyArrowPatch(
            a,
            b,
            arrowstyle=style,
            mutation_scale=mutation,
            linewidth=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
            connectionstyle=connectionstyle,
        )
    )


def _line(ax, x1, y1, x2, y2, *, color=黑, lw=0.9, ls="-"):
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, linestyle=ls)


def _support(ax, x, y, scale=0.18, color=黑):
    tri = Polygon([[x, y], [x - scale, y - 0.28], [x + scale, y - 0.28]], closed=True,
                  facecolor="white", edgecolor=color, linewidth=0.8)
    ax.add_patch(tri)
    for dx in np.linspace(-scale, scale, 5):
        _line(ax, x + dx - 0.05, y - 0.34, x + dx + 0.02, y - 0.27, color=color, lw=0.45)


def _node(ax, x, y, number=None, color=黑, radius=0.105):
    ax.add_patch(Circle((x, y), radius, facecolor="white", edgecolor=color, linewidth=0.8, zorder=4))
    if number is not None:
        ax.text(x, y, str(number), ha="center", va="center", fontsize=9, zorder=5)


def _rotation(ax, x, y, label, color=黑, side="right"):
    if side == "right":
        ax.add_patch(Arc((x + 0.12, y + 0.02), 0.45, 0.36, theta1=185, theta2=350,
                         color=color, linewidth=0.65))
        _arrow(ax, (x + 0.32, y - 0.07), (x + 0.36, y + 0.02), color=color, lw=0.55, mutation=6)
        ax.text(x + 0.36, y - 0.23, label, fontsize=9, color=color)
    else:
        ax.add_patch(Arc((x - 0.12, y + 0.02), 0.45, 0.36, theta1=10, theta2=175,
                         color=color, linewidth=0.65))
        _arrow(ax, (x - 0.32, y - 0.07), (x - 0.36, y + 0.02), color=color, lw=0.55, mutation=6)
        ax.text(x - 0.62, y - 0.23, label, fontsize=9, color=color)


def _translation(ax, x, y, label, direction="x", color=黑):
    if direction == "x":
        _arrow(ax, (x + 0.08, y + 0.13), (x + 0.52, y + 0.13), color=color, lw=0.65, mutation=6)
        ax.text(x + 0.55, y + 0.18, label, fontsize=9, color=color, ha="left")
    else:
        _arrow(ax, (x + 0.12, y + 0.06), (x + 0.12, y + 0.52), color=color, lw=0.65, mutation=6)
        ax.text(x + 0.19, y + 0.30, label, fontsize=9, color=color)


def _frame(ax, x0=0, y0=0, bays=3, stories=3, dx=1.35, dy=1.05,
           color=黑, node_numbers=True, linewidth=1.0, supports=True):
    for i in range(bays + 1):
        _line(ax, x0 + i * dx, y0, x0 + i * dx, y0 + stories * dy, color=color, lw=linewidth)
    for j in range(1, stories + 1):
        _line(ax, x0, y0 + j * dy, x0 + bays * dx, y0 + j * dy, color=color, lw=linewidth)
    for j in range(stories + 1):
        for i in range(bays + 1):
            n = j * (bays + 1) + i + 1 if node_numbers else None
            _node(ax, x0 + i * dx, y0 + j * dy, n, color=color, radius=0.10 if node_numbers else 0.05)
    if supports:
        for i in range(bays + 1):
            _support(ax, x0 + i * dx, y0 - 0.04, scale=0.15, color=color)


def _save(fig, uid, title):
    root = 第1章根 if uid == "1-1" else 章根
    base = f"图{uid}_{title}"
    pdf, png = 样式.导出图片(fig, root / "PDF结果" / base)
    # 公共导出函数的单基名双格式不适用于本章分离的 PDF/PNG 目录，移动 PNG。
    wanted_png = root / "PNG结果" / f"{base}.png"
    wanted_png.parent.mkdir(parents=True, exist_ok=True)
    if wanted_png.exists():
        wanted_png.unlink()
    png.replace(wanted_png)
    plt.close(fig)
    return pdf, wanted_png


def draw_1_1():
    fig, ax = _canvas(height=6.0, xlim=(0, 12), ylim=(0, 10))
    # 三个理论/精度/稳定性层次，Tol Bright 边框。
    for y, h, c in [(6.7, 3.0, 蓝), (3.4, 2.9, 红), (0.35, 2.75, 黄)]:
        ax.add_patch(Rectangle((1.3, y), 10.2, h, facecolor="none", edgecolor=c,
                               linewidth=1.1, linestyle=(0, (6, 3))))
    _box(ax, (2.2, 9.0), (1.7, 0.50), "Model reduction")
    _box(ax, (7.8, 9.0), (1.7, 0.50), "Reference frame")
    _box(ax, (1.8, 8.0), (1.6, 0.48), "Dynamic")
    _box(ax, (3.8, 8.0), (1.6, 0.48), "Static")
    _box(ax, (1.8, 7.15), (1.6, 0.55), "Craig--Bampton", ec=蓝)
    _box(ax, (3.8, 7.15), (1.6, 0.55), "Guyan", ec=红)
    _box(ax, (6.9, 8.05), (1.7, 0.50), "Partitioning")
    _box(ax, (6.0, 7.15), (1.7, 0.55), "Two-story PS")
    _box(ax, (8.1, 7.15), (1.7, 0.55), "Three-story PS")
    _line(ax, 3.05, 9.0, 3.05, 8.72); _line(ax, 2.6, 8.72, 4.6, 8.72)
    _line(ax, 2.6, 8.72, 2.6, 8.48); _line(ax, 4.6, 8.72, 4.6, 8.48)
    _arrow(ax, (2.6, 8.0), (2.6, 7.7)); _arrow(ax, (4.6, 8.0), (4.6, 7.7))
    _arrow(ax, (8.65, 9.0), (7.75, 8.55)); _line(ax, 7.75, 8.05, 7.75, 7.88)
    _line(ax, 6.85, 7.88, 8.95, 7.88); _arrow(ax, (6.85, 7.88), (6.85, 7.7)); _arrow(ax, (8.95, 7.88), (8.95, 7.7))

    _box(ax, (1.75, 5.55), (1.55, 0.52), "MDOF RTHS", ec=蓝)
    _box(ax, (1.75, 4.80), (1.55, 0.48), "Partition")
    _box(ax, (1.75, 4.10), (1.55, 0.48), "Reduction")
    _box(ax, (1.75, 3.48), (1.55, 0.48), "Closed loop")
    for y1, y2 in [(5.55, 5.28), (4.80, 4.58), (4.10, 3.96)]: _arrow(ax, (2.53, y1), (2.53, y2))
    _box(ax, (4.15, 5.45), (1.75, 0.52), "Simulation")
    _box(ax, (6.7, 5.45), (1.85, 0.52), "Simulink model")
    _box(ax, (9.2, 5.72), (1.65, 0.46), "El Centro")
    _box(ax, (9.2, 5.10), (1.65, 0.46), "Chirp")
    _arrow(ax, (5.9, 5.71), (6.7, 5.71)); _line(ax, 8.55, 5.71, 8.9, 5.71)
    _line(ax, 8.9, 5.33, 8.9, 5.95); _arrow(ax, (8.9, 5.95), (9.2, 5.95)); _arrow(ax, (8.9, 5.33), (9.2, 5.33))
    _box(ax, (4.15, 4.32), (1.75, 0.52), "Sensitivity")
    _box(ax, (6.7, 4.65), (1.85, 0.52), "Reduction method")
    _box(ax, (6.7, 3.82), (1.85, 0.52), "Partition scheme")
    _box(ax, (9.2, 4.20), (1.65, 0.55), "Accuracy metrics")
    _line(ax, 5.9, 4.58, 6.35, 4.58); _line(ax, 6.35, 4.08, 6.35, 4.91)
    _arrow(ax, (6.35, 4.91), (6.7, 4.91)); _arrow(ax, (6.35, 4.08), (6.7, 4.08))
    _line(ax, 8.55, 4.08, 8.9, 4.08); _line(ax, 8.9, 4.08, 8.9, 4.48); _arrow(ax, (8.9, 4.48), (9.2, 4.48))
    _arrow(ax, (3.3, 5.75), (4.15, 5.71)); _arrow(ax, (3.3, 4.34), (4.15, 4.58))

    # 稳定性层整体上移 0.20，确保黄色边框与输出裁切边界之间有安全边距。
    _box(ax, (1.8, 2.55), (1.7, 0.52), "Stability criterion")
    _box(ax, (1.5, 1.35), (1.55, 0.52), "Continuous")
    _box(ax, (3.3, 1.35), (1.55, 0.52), "Discrete")
    _box(ax, (1.5, 0.60), (1.55, 0.48), "$s$ transform")
    _box(ax, (3.3, 0.60), (1.55, 0.48), "$z$ transform")
    _line(ax, 2.65, 2.55, 2.65, 2.23); _line(ax, 2.28, 2.23, 4.08, 2.23)
    _arrow(ax, (2.28, 2.23), (2.28, 1.87)); _arrow(ax, (4.08, 2.23), (4.08, 1.87))
    _arrow(ax, (2.28, 1.35), (2.28, 1.08)); _arrow(ax, (4.08, 1.35), (4.08, 1.08))
    _box(ax, (6.0, 2.55), (2.1, 0.52), "Coupling interface")
    _box(ax, (6.0, 1.50), (2.1, 0.72), "$K_2$, $C_2$, $M_2$\nwith delays")
    _box(ax, (6.0, 0.50), (2.1, 0.62), "Pole distribution")
    _arrow(ax, (7.05, 2.55), (7.05, 2.22)); _arrow(ax, (7.05, 1.50), (7.05, 1.12))
    _box(ax, (9.25, 1.95), (1.75, 0.55), "Stability region")
    _box(ax, (9.25, 0.95), (1.75, 0.55), "Stability metric")
    _line(ax, 8.1, 0.81, 8.75, 0.81); _line(ax, 8.75, 0.81, 8.75, 2.22)
    _arrow(ax, (8.75, 2.22), (9.25, 2.22)); _arrow(ax, (8.75, 1.22), (9.25, 1.22))
    ax.text(0.48, 5.2, "Theory", rotation=90, color=红, fontsize=9, va="center", ha="center")
    _arrow(ax, (0.94, 6.75), (1.30, 5.55), color=黑)
    _arrow(ax, (0.94, 3.55), (1.30, 1.65), color=黑)
    return _save(fig, "1-1", "技术路线图")


def draw_2_1():
    fig, ax = _canvas(height=2.65, xlim=(0, 12.4), ylim=(0, 4.2))
    boxes = [(1.1, "Numerical\nsubstructure"), (3.55, "Controller"), (5.85, "Actuator\ntransfer system"), (8.55, "Physical\nsubstructure")]
    for x, t in boxes: _box(ax, (x, 2.2), (1.75, 0.85), t, fc="white")
    _arrow(ax, (0.10, 2.63), (1.1, 2.63)); ax.text(0.12, 2.86, "Numerical load", fontsize=9)
    labels = [(2.85, "$x_n$"), (5.30, "$x_c$"), (8.05, "$x_a$"), (10.85, "$x_m$")]
    for (a, b), (x, lab) in zip([(2.85, 3.55), (5.30, 5.85), (7.60, 8.55), (10.30, 11.25)], labels):
        _arrow(ax, (a, 2.63), (b, 2.63)); ax.text(x, 2.87, lab, fontsize=9)
    _arrow(ax, (9.43, 3.9), (9.43, 3.05)); ax.text(8.85, 3.95, "Physical load", fontsize=9)
    # 位移内环反馈和恢复力外环反馈。
    _line(ax, 10.30, 2.63, 10.75, 2.63); _line(ax, 10.75, 2.63, 10.75, 1.42)
    _line(ax, 10.75, 1.42, 5.30, 1.42); _arrow(ax, (5.30, 1.42), (5.30, 2.20))
    ax.text(7.55, 1.62, "Displacement feedback", fontsize=9)
    _line(ax, 10.75, 1.42, 10.75, 0.48); _line(ax, 10.75, 0.48, 1.98, 0.48)
    _arrow(ax, (1.98, 0.48), (1.98, 2.20)); ax.text(6.0, 0.68, "Restoring-force feedback $f_r$", fontsize=9)
    return _save(fig, "2-1", "RTHS反馈控制闭环图")


def _grid_panel(ax, x0, y0, w=3.5, h=2.0, nx=4, ny=3, fill=True):
    if fill: ax.add_patch(Rectangle((x0, y0), w, h, facecolor=青, alpha=0.72, edgecolor="none"))
    for i in range(nx + 1): _line(ax, x0 + w * i / nx, y0, x0 + w * i / nx, y0 + h, lw=0.75)
    for j in range(ny + 1): _line(ax, x0, y0 + h * j / ny, x0 + w, y0 + h * j / ny, lw=0.75)
    for i in range(nx + 1):
        for j in range(ny + 1): _node(ax, x0 + w * i / nx, y0 + h * j / ny, None, radius=0.055)


def draw_2_2():
    fig, ax = _canvas(height=4.2, xlim=(0, 10.6), ylim=(0, 6.0))
    # (a) 为未离散的整体连续体：仅外边界，不画网格或节点。
    ax.add_patch(Rectangle((0.45, 3.35), 3.5, 2.0, facecolor=青, alpha=0.72,
                           edgecolor=黑, linewidth=0.75))
    ax.text(0.10, 5.18, "(a)", fontsize=9)
    _grid_panel(ax, 5.7, 3.35)
    ax.text(5.35, 5.18, "(b)", fontsize=9)
    _grid_panel(ax, 0.45, 0.45)
    ax.text(0.10, 2.28, "(c)", fontsize=9)
    # 划分3个子结构并标出界面自由度。
    _line(ax, 1.33, 0.35, 1.33, 2.55, ls="--", color=蓝, lw=1.0)
    _line(ax, 1.25, 1.12, 4.0, 1.12, ls="--", color=蓝, lw=1.0)
    ax.text(0.78, 1.63, "1", fontsize=9); ax.text(2.45, 1.63, "2", fontsize=9); ax.text(2.45, 0.75, "3", fontsize=9)
    ax.text(1.05, 0.05, "$u_I^1$", fontsize=9); ax.text(4.10, 1.02, "$u_I^2$", fontsize=9)
    # 分离后的三个子结构。
    ax.text(5.35, 2.28, "(d)", fontsize=9)
    _grid_panel(ax, 5.65, 0.48, w=1.20, h=1.90, nx=1, ny=3)
    _grid_panel(ax, 7.35, 1.50, w=2.65, h=0.88, nx=3, ny=1)
    _grid_panel(ax, 7.35, 0.35, w=2.65, h=0.88, nx=3, ny=1)
    ax.text(6.18, 1.42, "1", fontsize=9); ax.text(8.05, 1.85, "2", fontsize=9); ax.text(8.05, 0.70, "3", fontsize=9)
    for x, y, text in [(5.25, 0.25, "$u_i^1$"), (6.45, 0.15, "$u_b^1$"), (10.05, 2.10, "$u_i^2$"),
                       (10.05, 1.55, "$u_b^2$"), (10.05, 0.80, "$u_b^3$"), (10.05, 0.25, "$u_i^3$")]:
        ax.text(x, y, text, fontsize=9)
    # panel dividers
    _line(ax, 5.15, 0.15, 5.15, 5.55, lw=0.55); _line(ax, 0.15, 3.0, 10.25, 3.0, lw=0.55)
    return _save(fig, "2-2", "Craig-Bampton法子结构划分")


def draw_2_3():
    fig, ax = _canvas(height=3.5, xlim=(0, 12), ylim=(0, 5.4))
    _frame(ax, x0=0.8, y0=1.0, bays=3, stories=3, dx=1.4, dy=1.05,
           color=黑, node_numbers=False, linewidth=0.9)
    for j in range(3): ax.text(0.42, 1.52 + j * 1.05, "W5$\\times$16", rotation=90, fontsize=9, va="center")
    # 尺寸线
    _line(ax, 0.8, 0.35, 5.0, 0.35, lw=0.6); _arrow(ax, (0.8, 0.35), (1.05, 0.35), style="<|-", mutation=6, lw=0.6)
    _arrow(ax, (5.0, 0.35), (4.75, 0.35), mutation=6, lw=0.6); ax.text(2.35, 0.10, "$3\\times762$ mm", fontsize=9)
    _line(ax, 5.55, 1.0, 5.55, 4.15, lw=0.6); _arrow(ax, (5.55, 1.0), (5.55, 1.25), style="<|-", mutation=6, lw=0.6)
    _arrow(ax, (5.55, 4.15), (5.55, 3.90), mutation=6, lw=0.6); ax.text(5.68, 2.13, "$3\\times635$ mm", rotation=90, fontsize=9)
    # 定制工字梁截面
    cx, cy = 8.7, 2.4
    ax.add_patch(Rectangle((cx - 0.85, cy + 0.72), 1.7, 0.16, facecolor="white", edgecolor=黑, lw=0.8))
    ax.add_patch(Rectangle((cx - 0.85, cy - 0.88), 1.7, 0.16, facecolor="white", edgecolor=黑, lw=0.8))
    ax.add_patch(Rectangle((cx - 0.08, cy - 0.72), 0.16, 1.44, facecolor="white", edgecolor=黑, lw=0.8))
    _line(ax, cx - 0.85, cy + 1.18, cx + 0.85, cy + 1.18, lw=0.55)
    _arrow(ax, (cx - 0.85, cy + 1.18), (cx - 0.58, cy + 1.18), style="<|-", mutation=6, lw=0.55)
    _arrow(ax, (cx + 0.85, cy + 1.18), (cx + 0.58, cy + 1.18), mutation=6, lw=0.55)
    ax.text(cx - 0.23, cy + 1.30, "38 mm", fontsize=9)
    _line(ax, cx - 1.25, cy - 0.88, cx - 1.25, cy + 0.88, lw=0.55)
    _arrow(ax, (cx - 1.25, cy - 0.88), (cx - 1.25, cy - 0.60), style="<|-", mutation=6, lw=0.55)
    _arrow(ax, (cx - 1.25, cy + 0.88), (cx - 1.25, cy + 0.60), mutation=6, lw=0.55)
    ax.text(cx - 1.55, cy - 0.25, "50 mm", rotation=90, fontsize=9)
    ax.text(cx + 1.05, cy + 0.72, "6 mm", fontsize=9); ax.text(cx + 0.15, cy + 0.05, "6 mm", fontsize=9)
    ax.text(cx - 0.75, 0.55, "Built-up beam section", fontsize=9)
    return _save(fig, "2-3", "参考结构尺寸")


def draw_2_4():
    fig, ax = _canvas(height=4.2, xlim=(-0.8, 5.4), ylim=(-0.7, 4.5))
    _frame(ax, x0=0, y0=0, bays=3, stories=3, dx=1.35, dy=1.05, node_numbers=True)
    labels = {
        5: ("$\\psi_1$", "$\\psi_2$"), 6: ("$\\psi_{28}$", "$\\psi_{29}$"),
        7: ("$\\psi_{20}$", "$\\psi_{21}$"), 8: ("$\\psi_{16}$", "$\\psi_{17}$"),
        9: ("$\\psi_{12}$", "$\\psi_{11}$"), 10: ("$\\psi_6$", "$\\psi_5$"),
        11: ("$\\psi_{25}$", "$\\psi_{24}$"), 12: ("$\\psi_{23}$", "$\\psi_{22}$"),
        13: ("$\\psi_8$", "$\\psi_7$"), 14: ("$\\psi_{15}$", "$\\psi_{14}$"),
        15: ("$\\psi_9$", "$\\psi_{10}$"), 16: ("$\\psi_4$", "$\\psi_3$"),
    }
    for n, (v, r) in labels.items():
        j, i = divmod(n - 1, 4); x, y = i * 1.35, j * 1.05
        _translation(ax, x, y, v, "y"); _rotation(ax, x, y, r)
    _rotation(ax, 1.35, 0, "$\\psi_{19}$"); _rotation(ax, 2.70, 0, "$\\psi_{18}$")
    _translation(ax, 4.05, 1.05, "$\\psi_{27}$", "x")
    _translation(ax, 4.05, 2.10, "$\\psi_{26}$", "x")
    _translation(ax, 4.05, 3.15, "$\\psi_2$", "x")
    _arrow(ax, (4.25, -0.42), (4.85, -0.42), mutation=7); ax.text(4.9, -0.48, "$x$", fontsize=9)
    _arrow(ax, (-0.42, 3.30), (-0.42, 3.95), mutation=7); ax.text(-0.48, 4.02, "$y$", fontsize=9)
    return _save(fig, "2-4", "参考结构自由度")


def draw_2_5():
    fig, ax = _canvas(height=4.0, xlim=(-0.8, 5.4), ylim=(-0.7, 4.35))
    _frame(ax, x0=0, y0=0, bays=3, stories=3, dx=1.35, dy=1.05, node_numbers=True)
    for story, horizontal in [(1, "$\\psi_1$"), (2, "$\\psi_6$"), (3, "$\\psi_{11}$")]:
        y = story * 1.05; _translation(ax, 4.05, y, horizontal, "x")
        first = {1: 2, 2: 7, 3: 12}[story]
        for i in range(4): _rotation(ax, i * 1.35, y, f"$\\psi_{{{first+i}}}$")
    _arrow(ax, (4.25, -0.42), (4.85, -0.42), mutation=7); ax.text(4.9, -0.48, "$x$", fontsize=9)
    _arrow(ax, (-0.42, 3.30), (-0.42, 3.95), mutation=7); ax.text(-0.48, 4.02, "$y$", fontsize=9)
    return _save(fig, "2-5", "简化自由度")


def _partial_frame(ax, coords, edges, offset=(0, 0), color=蓝, label=""):
    ox, oy = offset
    for a, b in edges:
        xa, ya = coords[a]; xb, yb = coords[b]
        _line(ax, xa + ox, ya + oy, xb + ox, yb + oy, color=color, lw=1.25)
    for key, (x, y) in coords.items():
        _node(ax, x + ox, y + oy, key, color=color, radius=0.105)
    bottom = [k for k, (_, y) in coords.items() if y == min(v[1] for v in coords.values())]
    for k in bottom:
        x, y = coords[k]; _support(ax, x + ox, y + oy - 0.03, scale=0.13, color=color)
    if label: ax.text(ox + np.mean([p[0] for p in coords.values()]), oy - 0.6, label, ha="center", fontsize=9, color=color)


def draw_2_6():
    fig, ax = _canvas(height=3.4, xlim=(-0.3, 10.5), ylim=(-0.8, 4.25))
    # 第一类：左侧一品框架底、中两层为物理子结构，其余为数值子结构。
    cnum = {3:(2.8,0),4:(4.0,0),6:(1.6,1),7:(2.8,1),8:(4.0,1),9:(0.4,2),10:(1.6,2),11:(2.8,2),12:(4.0,2),13:(0.4,3),14:(1.6,3),15:(2.8,3),16:(4.0,3)}
    enum = [((3),(7)),(4,8),(6,7),(7,8),(7,11),(8,12),(9,10),(10,11),(11,12),(9,13),(10,14),(11,15),(12,16),(13,14),(14,15),(15,16)]
    _partial_frame(ax, cnum, enum, color=蓝, label="Numerical substructure")
    cphy = {2:(0,0),3:(1.2,0),6:(0,1),7:(1.2,1),9:(0,2),10:(1.2,2)}
    ephy = [(2,6),(3,7),(6,7),(6,9),(7,10),(9,10)]
    _partial_frame(ax, cphy, ephy, offset=(6.7,0), color=红, label="Physical substructure")
    ax.text(5.45, 1.35, "+", fontsize=28, ha="center", va="center")
    return _save(fig, "2-6", "第一类子结构划分")


def draw_2_7():
    fig, ax = _canvas(height=3.4, xlim=(-0.3, 10.5), ylim=(-0.8, 4.25))
    # 第二类：左侧一品框架三层均为物理子结构。
    cnum = {3:(2.8,0),4:(4.0,0),6:(1.6,1),7:(2.8,1),8:(4.0,1),10:(1.6,2),11:(2.8,2),12:(4.0,2),14:(1.6,3),15:(2.8,3),16:(4.0,3)}
    enum = [(3,7),(4,8),(6,7),(7,8),(6,10),(7,11),(8,12),(10,11),(11,12),(10,14),(11,15),(12,16),(14,15),(15,16)]
    _partial_frame(ax, cnum, enum, color=蓝, label="Numerical substructure")
    cphy = {1:(0,0),2:(1.2,0),5:(0,1),6:(1.2,1),9:(0,2),10:(1.2,2),13:(0,3),14:(1.2,3)}
    ephy = [(1,5),(2,6),(5,6),(5,9),(6,10),(9,10),(9,13),(10,14),(13,14)]
    _partial_frame(ax, cphy, ephy, offset=(6.7,0), color=红, label="Physical substructure")
    ax.text(5.45, 1.35, "+", fontsize=28, ha="center", va="center")
    return _save(fig, "2-7", "第二类子结构划分")


def draw_2_8():
    """按论文嵌入图和两份只读 SLX 的真实块语义重绘主闭环。

    完整原生画布未存于单一 SLX，因此本函数明确属于新建矢量重绘；不冒充
    Simulink 原生源码。真实来源包括地震激励增益、数值子结构状态空间块，
    以及 KPrt/CPrt/MPrt 物理反力计算子系统。
    """
    fig, ax = _canvas(height=2.9, xlim=(0, 13.4), ylim=(0, 4.7))
    _box(ax, (0.25, 2.75), (1.55, 0.78), "Ground\nacceleration", fc="white")
    # 地震激励增益：对应 lvxvjie_guyan_2.slx 中“地震激励-力”块。
    tri = Polygon([[2.15, 3.14], [3.25, 3.58], [3.25, 2.70]], closed=True,
                  facecolor="white", edgecolor=黑, linewidth=0.8)
    ax.add_patch(tri)
    ax.text(2.76, 3.14, "$-M_r$", ha="center", va="center", fontsize=9)
    ax.text(2.70, 2.45, "Ground-load mapping", ha="center", fontsize=9)
    # 求和与数值状态空间块。
    ax.add_patch(Circle((4.15, 3.14), 0.24, facecolor="white", edgecolor=黑, linewidth=0.8))
    ax.text(4.07, 3.26, "+", fontsize=9, ha="center"); ax.text(4.07, 3.00, "$-$", fontsize=9, ha="center")
    _box(ax, (5.05, 2.55), (2.25, 1.18), "$\\dot{x}=Ax+Bu$\n$y=Cx+Du$", fc="white")
    ax.text(6.18, 2.25, "Numerical substructure", fontsize=9, ha="center")
    _box(ax, (8.15, 2.78), (1.10, 0.72), "Interface\noutput", fc="white", fontsize=9)
    _box(ax, (10.25, 2.78), (1.35, 0.72), "Response", fc="white", fontsize=9)
    # 恢复力回路：对应 New_Model...slx 中含 KPrt/CPrt/MPrt 的真实子系统。
    _box(ax, (5.80, 0.55), (3.20, 0.85), "$K_{Prt}u+C_{Prt}\\dot{u}+M_{Prt}\\ddot{u}$",
         ec=红, fc="white", fontsize=9)
    ax.text(7.40, 0.22, "Physical restoring-force computation", fontsize=9,
            ha="center", color=红)
    tri2 = Polygon([[4.70, 0.98], [5.55, 1.30], [5.55, 0.66]], closed=True,
                   facecolor="white", edgecolor=黑, linewidth=0.8)
    ax.add_patch(tri2); ax.text(5.18, 0.98, "$T_f$", ha="center", va="center", fontsize=9)
    tri3 = Polygon([[10.10, 0.98], [9.25, 1.30], [9.25, 0.66]], closed=True,
                   facecolor="white", edgecolor=黑, linewidth=0.8)
    ax.add_patch(tri3); ax.text(9.62, 0.98, "$T_u$", ha="center", va="center", fontsize=9)

    _arrow(ax, (1.80, 3.14), (2.15, 3.14)); _arrow(ax, (3.25, 3.14), (3.91, 3.14))
    _arrow(ax, (4.39, 3.14), (5.05, 3.14)); _arrow(ax, (7.30, 3.14), (8.15, 3.14))
    _arrow(ax, (9.25, 3.14), (10.25, 3.14)); _arrow(ax, (11.60, 3.14), (13.10, 3.14))
    ax.text(12.05, 3.36, "Displacement response", fontsize=9)
    # 反馈回路沿下方返回求和负端。
    _line(ax, 10.10, 0.98, 10.35, 0.98); _line(ax, 10.35, 0.98, 10.35, 3.14)
    _arrow(ax, (8.15, 3.14), (10.10, 0.98), connectionstyle="angle3,angleA=0,angleB=90")
    _arrow(ax, (9.25, 0.98), (9.00, 0.98)); _arrow(ax, (5.80, 0.98), (5.55, 0.98))
    _line(ax, 4.70, 0.98, 4.15, 0.98); _arrow(ax, (4.15, 0.98), (4.15, 2.90))
    ax.text(3.15, 1.25, "Restoring-force feedback", fontsize=9, ha="center")
    return _save(fig, "2-8", "Simulink模型")


生成函数 = {
    "1-1": draw_1_1,
    "2-1": draw_2_1,
    "2-2": draw_2_2,
    "2-3": draw_2_3,
    "2-4": draw_2_4,
    "2-5": draw_2_5,
    "2-6": draw_2_6,
    "2-7": draw_2_7,
    "2-8": draw_2_8,
}


def 生成单图(uid: str):
    if uid not in 生成函数:
        raise KeyError(f"未定义矢量图：{uid}")
    return 生成函数[uid]()


def 生成全部矢量图():
    outputs = []
    for uid in 生成函数:
        outputs.append(生成单图(uid))
    print(json.dumps([[str(p) for p in pair] for pair in outputs], ensure_ascii=False, indent=2))
    return outputs


if __name__ == "__main__":
    生成全部矢量图()



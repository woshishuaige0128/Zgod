"""`manuscript_0823_with_figures.tex` 所用八组期刊图的绘制核心。

边界说明
--------
1. 图形语义与数据来自梁禹大论文图片复现包，不新增算例、不拟合曲线。
2. 示意图属于依据大论文证据建立的参数化矢量重绘，不冒充梁禹原始源码。
3. El Centro、Chirp 和稳定域均读取本目录上一级 `输入数据` 中的已验收快照。
4. 输出固定写入 `figure/PDF` 与 `figure/PNG`。
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Polygon, Rectangle

import 科研绘图统一样式 as 样式


源码目录 = Path(__file__).resolve().parent
图片根目录 = 源码目录.parent
数据目录 = 图片根目录 / "输入数据"
PDF目录 = 图片根目录 / "PDF"

黑 = 样式.颜色["原结构"]
蓝 = 样式.颜色["Craig-Bampton"]
红 = 样式.颜色["Guyan"]
浅蓝 = 样式.颜色["浅蓝"]
辅助灰 = "#777777"


def _读取_json(文件名: str) -> dict:
    路径 = 数据目录 / 文件名
    if not 路径.is_file():
        raise FileNotFoundError(f"缺少输入参数：{路径}")
    return json.loads(路径.read_text(encoding="utf-8-sig"))


def _保存(fig: plt.Figure, 文件基名: str) -> tuple[Path, Path]:
    return 样式.导出图片(fig, PDF目录 / 文件基名)


def _有限余量(values: np.ndarray, 比例: float = 0.08) -> tuple[float, float]:
    lo = float(np.nanmin(values))
    hi = float(np.nanmax(values))
    span = hi - lo
    if span <= np.finfo(float).eps:
        span = max(abs(lo), 1.0)
    return lo - 比例 * span, hi + 比例 * span


def _画线(ax: plt.Axes, x1: float, y1: float, x2: float, y2: float, *, color=黑, lw=0.9, ls="-") -> None:
    ax.plot([x1, x2], [y1, y2], color=color, linewidth=lw, linestyle=ls)


def _画箭头(
    ax: plt.Axes,
    起点: tuple[float, float],
    终点: tuple[float, float],
    *,
    color=黑,
    lw=0.9,
    style="-|>",
    mutation=9,
) -> None:
    ax.add_patch(
        FancyArrowPatch(
            起点,
            终点,
            arrowstyle=style,
            mutation_scale=mutation,
            linewidth=lw,
            color=color,
            shrinkA=0,
            shrinkB=0,
            connectionstyle="arc3",
        )
    )


def _画方框(
    ax: plt.Axes,
    xy: tuple[float, float],
    wh: tuple[float, float],
    text: str,
    *,
    ec=黑,
    fc="white",
    lw=0.8,
) -> None:
    x, y = xy
    w, h = wh
    ax.add_patch(Rectangle((x, y), w, h, facecolor=fc, edgecolor=ec, linewidth=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=9)


def _画支座(ax: plt.Axes, x: float, y: float, scale: float = 0.18, color=黑) -> None:
    tri = Polygon(
        [[x, y], [x - scale, y - 0.28], [x + scale, y - 0.28]],
        closed=True,
        facecolor="white",
        edgecolor=color,
        linewidth=0.8,
    )
    ax.add_patch(tri)
    for dx in np.linspace(-scale, scale, 5):
        _画线(ax, x + dx - 0.05, y - 0.34, x + dx + 0.02, y - 0.27, color=color, lw=0.45)


def _画节点(ax: plt.Axes, x: float, y: float, number: int | None = None, *, radius=0.105, color=黑) -> None:
    ax.add_patch(Circle((x, y), radius, facecolor="white", edgecolor=color, linewidth=0.8, zorder=4))
    if number is not None:
        ax.text(x, y, str(number), ha="center", va="center", fontsize=9, zorder=5)


def _画转角(ax: plt.Axes, x: float, y: float, label: str, color=黑) -> None:
    ax.add_patch(Arc((x + 0.12, y + 0.02), 0.45, 0.36, theta1=185, theta2=350, color=color, linewidth=0.65))
    _画箭头(ax, (x + 0.32, y - 0.07), (x + 0.36, y + 0.02), color=color, lw=0.55, mutation=6)
    ax.text(x + 0.36, y - 0.23, label, fontsize=9, color=color)


def _画平移(ax: plt.Axes, x: float, y: float, label: str, direction="x", color=黑) -> None:
    if direction == "x":
        _画箭头(ax, (x + 0.08, y + 0.13), (x + 0.52, y + 0.13), color=color, lw=0.65, mutation=6)
        ax.text(x + 0.55, y + 0.18, label, fontsize=9, color=color, ha="left")
    else:
        _画箭头(ax, (x + 0.12, y + 0.06), (x + 0.12, y + 0.52), color=color, lw=0.65, mutation=6)
        ax.text(x + 0.19, y + 0.30, label, fontsize=9, color=color)


def _画框架(
    ax: plt.Axes,
    *,
    x0=0.0,
    y0=0.0,
    bays=3,
    stories=3,
    dx=1.35,
    dy=1.05,
    node_numbers=True,
    supports=True,
) -> None:
    for i in range(bays + 1):
        _画线(ax, x0 + i * dx, y0, x0 + i * dx, y0 + stories * dy, lw=1.0)
    for j in range(1, stories + 1):
        _画线(ax, x0, y0 + j * dy, x0 + bays * dx, y0 + j * dy, lw=1.0)
    for j in range(stories + 1):
        for i in range(bays + 1):
            number = j * (bays + 1) + i + 1 if node_numbers else None
            _画节点(ax, x0 + i * dx, y0 + j * dy, number, radius=0.10 if node_numbers else 0.05)
    if supports:
        for i in range(bays + 1):
            _画支座(ax, x0 + i * dx, y0 - 0.04, scale=0.15)


def 绘制_RTHS闭环图() -> tuple[Path, Path]:
    """期刊图1：依据大论文图2-1重绘RTHS反馈闭环。"""
    参数 = _读取_json("第1至2章示意图参数.json")
    if "2-1" not in 参数 or len(参数["2-1"].get("顺向链", [])) != 4:
        raise ValueError("图2-1参数快照不完整")

    fig, ax = plt.subplots(figsize=(7.48, 2.65), constrained_layout=True)
    ax.set_xlim(0, 12.4)
    ax.set_ylim(0, 4.2)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    boxes = [
        (1.10, "Numerical\nsubstructure"),
        (3.55, "Controller"),
        (5.85, "Actuator\ntransfer system"),
        (8.55, "Physical\nsubstructure"),
    ]
    for x, text in boxes:
        _画方框(ax, (x, 2.20), (1.75, 0.85), text)
    _画箭头(ax, (0.10, 2.63), (1.10, 2.63))
    ax.text(0.98, 2.86, "Numerical load", fontsize=9, ha="right")

    links = [((2.85, 2.63), (3.55, 2.63), "$x_n$", 2.85),
             ((5.30, 2.63), (5.85, 2.63), "$x_c$", 5.30),
             ((7.60, 2.63), (8.55, 2.63), "$x_a$", 8.05),
             ((10.30, 2.63), (11.25, 2.63), "$x_m$", 10.85)]
    for start, end, label, tx in links:
        _画箭头(ax, start, end)
        ax.text(tx, 2.87, label, fontsize=9)

    _画箭头(ax, (9.43, 3.90), (9.43, 3.05))
    ax.text(8.85, 3.95, "Physical load", fontsize=9)

    _画线(ax, 10.30, 2.63, 10.75, 2.63)
    _画线(ax, 10.75, 2.63, 10.75, 1.42)
    _画线(ax, 10.75, 1.42, 5.30, 1.42)
    _画箭头(ax, (5.30, 1.42), (5.30, 2.20))
    ax.text(7.55, 1.62, "Displacement feedback", fontsize=9)

    _画线(ax, 10.75, 1.42, 10.75, 0.48)
    _画线(ax, 10.75, 0.48, 1.98, 0.48)
    _画箭头(ax, (1.98, 0.48), (1.98, 2.20))
    ax.text(6.00, 0.68, r"Restoring-force feedback $f_r$", fontsize=9)
    return _保存(fig, "fig_rths_loop")


def 绘制_基准结构几何图() -> tuple[Path, Path]:
    """期刊图3：依据大论文图2-3重绘框架尺寸与梁截面。"""
    参数 = _读取_json("第1至2章示意图参数.json")["2-3"]
    frame = 参数["框架"]
    section = 参数["梁截面_mm"]

    fig, ax = plt.subplots(figsize=(7.48, 3.50), constrained_layout=True)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.4)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")

    _画框架(ax, x0=0.8, y0=1.0, bays=3, stories=3, dx=1.4, dy=1.05, node_numbers=False)
    for j in range(3):
        ax.text(0.42, 1.52 + j * 1.05, r"W5$\times$16", rotation=90, fontsize=9, va="center")

    _画线(ax, 0.8, 0.35, 5.0, 0.35, lw=0.6)
    _画箭头(ax, (0.8, 0.35), (1.05, 0.35), style="<|-", mutation=6, lw=0.6)
    _画箭头(ax, (5.0, 0.35), (4.75, 0.35), mutation=6, lw=0.6)
    ax.text(2.35, 0.10, rf"${frame['跨数']}\times{frame['单跨_mm']}$ mm", fontsize=9)

    _画线(ax, 5.55, 1.0, 5.55, 4.15, lw=0.6)
    _画箭头(ax, (5.55, 1.0), (5.55, 1.25), style="<|-", mutation=6, lw=0.6)
    _画箭头(ax, (5.55, 4.15), (5.55, 3.90), mutation=6, lw=0.6)
    ax.text(5.68, 2.13, rf"${frame['层数']}\times{frame['单层_mm']}$ mm", rotation=90, fontsize=9)

    cx, cy = 8.70, 2.40
    ax.add_patch(Rectangle((cx - 0.85, cy + 0.72), 1.70, 0.16, facecolor="white", edgecolor=黑, lw=0.8))
    ax.add_patch(Rectangle((cx - 0.85, cy - 0.88), 1.70, 0.16, facecolor="white", edgecolor=黑, lw=0.8))
    ax.add_patch(Rectangle((cx - 0.08, cy - 0.72), 0.16, 1.44, facecolor="white", edgecolor=黑, lw=0.8))
    _画线(ax, cx - 0.85, cy + 1.18, cx + 0.85, cy + 1.18, lw=0.55)
    _画箭头(ax, (cx - 0.85, cy + 1.18), (cx - 0.58, cy + 1.18), style="<|-", mutation=6, lw=0.55)
    _画箭头(ax, (cx + 0.85, cy + 1.18), (cx + 0.58, cy + 1.18), mutation=6, lw=0.55)
    ax.text(cx - 0.23, cy + 1.30, f"{section['翼缘宽']} mm", fontsize=9)
    _画线(ax, cx - 1.25, cy - 0.88, cx - 1.25, cy + 0.88, lw=0.55)
    _画箭头(ax, (cx - 1.25, cy - 0.88), (cx - 1.25, cy - 0.60), style="<|-", mutation=6, lw=0.55)
    _画箭头(ax, (cx - 1.25, cy + 0.88), (cx - 1.25, cy + 0.60), mutation=6, lw=0.55)
    ax.text(cx - 1.55, cy - 0.25, f"{section['总高']} mm", rotation=90, fontsize=9)
    ax.text(cx + 1.05, cy + 0.72, f"{section['翼缘厚']} mm", fontsize=9)
    ax.text(cx + 0.15, cy + 0.05, f"{section['腹板厚']} mm", fontsize=9)
    ax.text(cx - 0.75, 0.55, "Built-up beam section", fontsize=9)
    return _保存(fig, "fig_benchmark_geometry")


def _绘制完整自由度(ax: plt.Axes) -> None:
    _画框架(ax, x0=0, y0=0, bays=3, stories=3, dx=1.35, dy=1.05, node_numbers=True)
    labels = {
        5: (r"$\psi_1$", r"$\psi_2$"), 6: (r"$\psi_{28}$", r"$\psi_{29}$"),
        7: (r"$\psi_{20}$", r"$\psi_{21}$"), 8: (r"$\psi_{16}$", r"$\psi_{17}$"),
        9: (r"$\psi_{12}$", r"$\psi_{11}$"), 10: (r"$\psi_6$", r"$\psi_5$"),
        11: (r"$\psi_{25}$", r"$\psi_{24}$"), 12: (r"$\psi_{23}$", r"$\psi_{22}$"),
        13: (r"$\psi_8$", r"$\psi_7$"), 14: (r"$\psi_{15}$", r"$\psi_{14}$"),
        15: (r"$\psi_9$", r"$\psi_{10}$"), 16: (r"$\psi_4$", r"$\psi_3$"),
    }
    for n, (vertical, rotation) in labels.items():
        j, i = divmod(n - 1, 4)
        x, y = i * 1.35, j * 1.05
        _画平移(ax, x, y, vertical, "y")
        _画转角(ax, x, y, rotation)
    _画转角(ax, 1.35, 0, r"$\psi_{19}$")
    _画转角(ax, 2.70, 0, r"$\psi_{18}$")
    _画平移(ax, 4.05, 1.05, r"$\psi_{27}$", "x")
    _画平移(ax, 4.05, 2.10, r"$\psi_{26}$", "x")
    _画平移(ax, 4.05, 3.15, r"$\psi_2$", "x")


def _绘制简化自由度(ax: plt.Axes) -> None:
    _画框架(ax, x0=0, y0=0, bays=3, stories=3, dx=1.35, dy=1.05, node_numbers=True)
    for story, horizontal in [(1, r"$\psi_1$"), (2, r"$\psi_6$"), (3, r"$\psi_{11}$")]:
        y = story * 1.05
        _画平移(ax, 4.05, y, horizontal, "x")
        first = {1: 2, 2: 7, 3: 12}[story]
        for i in range(4):
            _画转角(ax, i * 1.35, y, rf"$\psi_{{{first + i}}}$")


def 绘制_自由度理想化图() -> tuple[Path, Path]:
    """期刊图4：组合大论文图2-4（29 DOF）与图2-5（15 DOF）。"""
    参数 = _读取_json("第1至2章示意图参数.json")
    if 参数["2-4"]["节点数"] != 16 or 参数["2-5"]["节点数"] != 16:
        raise ValueError("自由度图节点参数与既有证据不一致")

    fig, axes = plt.subplots(1, 2, figsize=(7.48, 4.35), constrained_layout=True)
    for ax, draw, panel in zip(axes, (_绘制完整自由度, _绘制简化自由度), ("(a)", "(b)"), strict=True):
        draw(ax)
        _画箭头(ax, (4.25, -0.42), (4.85, -0.42), mutation=7)
        ax.text(4.90, -0.48, r"$x$", fontsize=9)
        _画箭头(ax, (-0.42, 3.30), (-0.42, 3.95), mutation=7)
        ax.text(-0.48, 4.02, r"$y$", fontsize=9)
        ax.set_xlim(-0.8, 5.4)
        ax.set_ylim(-0.7, 4.35)
        ax.set_aspect("equal", adjustable="box")
        ax.axis("off")
        ax.text(0.10, 4.26, panel, va="top", ha="left", fontsize=9, fontweight="bold")
    return _保存(fig, "fig_dof_idealization")


def _划分图支座(ax: plt.Axes, x: float, y: float) -> None:
    tri = Polygon([[x - 0.10, y - 0.22], [x + 0.10, y - 0.22], [x, y]], closed=True, fill=False, lw=0.8)
    ax.add_patch(tri)
    ax.plot([x - 0.14, x + 0.14], [y - 0.24, y - 0.24], color=黑, lw=0.8)
    for dx in np.linspace(-0.12, 0.10, 6):
        ax.plot([x + dx, x + dx - 0.05], [y - 0.24, y - 0.31], color=辅助灰, lw=0.5)


def _划分图框架(
    ax: plt.Axes,
    x0: float,
    y0: float,
    stories: int,
    bays: int,
    scale: float,
    node_labels: list[list[int | None]],
    master_labels: list[tuple[int, int, str]],
) -> None:
    xs = [x0 + scale * i for i in range(bays + 1)]
    ys = [y0 + scale * i for i in range(stories + 1)]
    for column, x in enumerate(xs):
        ax.plot([x, x], [ys[0], ys[-1]], color=黑, lw=0.8)
        if node_labels[0][column] is not None:
            _划分图支座(ax, x, ys[0])
    for y in ys[1:]:
        ax.plot([xs[0], xs[-1]], [y, y], color=黑, lw=0.8)
    for level in range(stories + 1):
        for bay in range(bays + 1):
            node = node_labels[level][bay]
            if node is None:
                continue
            x, y = xs[bay], ys[level]
            radius = 0.13
            center = (x - radius - 0.01, y + radius + 0.01)
            ax.add_patch(Circle(center, radius, fill=False, lw=0.65))
            ax.text(*center, str(node), ha="center", va="center", fontsize=9)
    for story, bay, label in master_labels:
        x = xs[min(bay, bays)]
        y = ys[min(story, stories)]
        ax.add_patch(Rectangle((x + 0.08, y + 0.04), 0.43, 0.25, fill=False, edgecolor=红, lw=0.8))
        ax.text(x + 0.295, y + 0.165, rf"$\psi_{{{label}}}$", color=红, ha="center", va="center", fontsize=9)
        ax.add_patch(FancyArrowPatch((x + 0.02, y), (x + 0.36, y), arrowstyle="-|>", mutation_scale=7, color=红, lw=0.8))


def _画组合加号(ax: plt.Axes, x: float, y: float) -> None:
    half = 0.13
    ax.plot([x - half, x + half], [y, y], color=黑, lw=1.0, solid_capstyle="butt")
    ax.plot([x, x], [y - half, y + half], color=黑, lw=1.0, solid_capstyle="butt")


def _绘制划分面板(ax: plt.Axes, kind: int, panel: str) -> None:
    if kind == 1:
        _划分图框架(
            ax, 0.4, 0.4, 3, 3, 0.85,
            [[None, 3, None, 4], [None, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
            [(1, 3, "1"), (2, 3, "6"), (3, 3, "11"), (1, 1, "4"), (2, 1, "9"), (3, 1, "14")],
        )
        _画组合加号(ax, 3.55, 1.70)
        _划分图框架(ax, 4.15, 0.4, 2, 1, 0.85, [[2, 3], [6, 7], [9, 10]], [(1, 1, "1"), (2, 1, "6")])
        ax.text(1.70, 3.42, "Numerical substructure", ha="center")
        ax.text(4.58, 2.57, "Physical substructure", ha="center")
    elif kind == 2:
        _划分图框架(
            ax, 0.6, 0.4, 3, 2, 0.85,
            [[None, 3, 4], [6, 7, 8], [10, 11, 12], [14, 15, 16]],
            [(1, 2, "1"), (2, 2, "6"), (3, 2, "11"), (1, 1, "4"), (2, 1, "9"), (3, 1, "14")],
        )
        _画组合加号(ax, 3.15, 1.70)
        _划分图框架(ax, 3.75, 0.4, 3, 1, 0.85, [[2, 3], [6, 7], [9, 10], [13, 14]], [(1, 1, "1"), (3, 1, "11")])
        x_psi6, y_psi6 = 3.75 + 0.85, 0.4 + 2 * 0.85
        ax.add_patch(Rectangle((x_psi6 + 0.08, y_psi6 + 0.04), 0.43, 0.25, fill=False, edgecolor=黑, lw=0.8))
        ax.text(x_psi6 + 0.295, y_psi6 + 0.165, r"$\psi_6$", color=黑, ha="center", va="center", fontsize=9)
        ax.add_patch(FancyArrowPatch((x_psi6 + 0.02, y_psi6), (x_psi6 + 0.36, y_psi6), arrowstyle="-|>", mutation_scale=7, color=黑, lw=0.8))
        ax.text(1.45, 3.42, "Numerical substructure", ha="center")
        ax.text(4.18, 3.42, "Physical substructure", ha="center")
    else:
        raise ValueError("kind 必须为1或2")
    ax.text(0.01, 0.98, panel, transform=ax.transAxes, va="top", ha="left", fontsize=9, fontweight="bold")
    ax.set_xlim(0, 5.65)
    ax.set_ylim(0, 3.72)
    ax.set_aspect("equal")
    ax.axis("off")


def 绘制_两类子结构划分图() -> tuple[Path, Path]:
    """期刊图5：纵向组合大论文图3-1与图3-2，保证标签可读。"""
    参数 = _读取_json("图3-1与图3-2_结构自由度参数.json")
    if 参数["图3-1"]["物理子结构"]["保留水平自由度"] != [1, 6]:
        raise ValueError("第一类物理子结构主自由度不是 [1, 6]")
    if 参数["图3-2"]["物理子结构"]["保留水平自由度"] != [1, 11]:
        raise ValueError("第二类物理子结构主自由度不是 [1, 11]")

    fig, axes = plt.subplots(2, 1, figsize=(7.48, 6.15), constrained_layout=True)
    _绘制划分面板(axes[0], 1, "(a)")
    _绘制划分面板(axes[1], 2, "(b)")
    return _保存(fig, "fig_division")


def _复平面坐标轴(ax: plt.Axes, xlim, ylim, xlabel, ylabel, xlabel_y_factor=-0.12) -> None:
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    _画箭头(ax, (xlim[0], 0), (xlim[1], 0), lw=0.9, mutation=8)
    _画箭头(ax, (0, ylim[0]), (0, ylim[1]), lw=0.9, mutation=8)
    ax.text(xlim[1], xlabel_y_factor * (ylim[1] - ylim[0]), xlabel, ha="right", va="top")
    ax.text(0.04 * (xlim[1] - xlim[0]), ylim[1], ylabel, ha="left", va="top")


def 绘制_极点平面映射图() -> tuple[Path, Path]:
    """期刊图2：依据大论文图4-2和映射参数重绘s域/z域。"""
    参数 = _读取_json("图4-2_极点映射参数.json")["连续极点示例"]
    sigma = float(参数["sigma"])
    omega = float(参数["omega"])
    T = float(参数["T_示意无量纲"])

    fig, axes = plt.subplots(1, 2, figsize=(7.48, 3.05), layout="none")
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.08, top=0.80, wspace=0.28)

    ax = axes[0]
    ax.add_patch(Rectangle((-2.2, -2.0), 2.2, 4.0, facecolor=浅蓝, edgecolor="none", zorder=0))
    _复平面坐标轴(ax, (-2.2, 1.15), (-2.0, 2.0), r"$\mathrm{Re}(s)$", r"$\mathrm{Im}(s)$")
    ax.plot([sigma, 0], [omega, omega], ls="--", lw=0.8, color=辅助灰)
    ax.plot([sigma, 0], [-omega, -omega], ls="--", lw=0.8, color=辅助灰)
    ax.plot([sigma, sigma], [-omega, omega], ls=":", lw=0.7, color=辅助灰)
    ax.plot([sigma, sigma], [omega, -omega], "x", color=黑, ms=5, mew=1.1)
    ax.text(sigma + 0.08, omega + 0.12, r"$s_1=\sigma+j\omega$", ha="left", va="bottom")
    ax.text(sigma + 0.08, -omega - 0.12, r"$s_2=\sigma-j\omega$", ha="left", va="top")
    ax.text(-1.92, 1.62, "Stable", ha="left", va="top", color="#27566F")
    ax.text(0.10, omega, r"$\omega$", ha="left", va="center")
    ax.text(0.10, -omega, r"$-\omega$", ha="left", va="center")
    ax.text(-2.08, 1.88, "(a)", fontsize=9, fontweight="bold", ha="left", va="top")

    ax = axes[1]
    ax.add_patch(Circle((0, 0), 1.0, facecolor=浅蓝, edgecolor=黑, linewidth=1.0))
    _复平面坐标轴(ax, (-1.35, 1.35), (-1.35, 1.35), r"$\mathrm{Re}(z)$", r"$\mathrm{Im}(z)$", xlabel_y_factor=-0.03)
    radius = np.exp(sigma * T)
    theta = omega * T
    z1 = (radius * np.cos(theta), radius * np.sin(theta))
    z2 = (radius * np.cos(theta), -radius * np.sin(theta))
    ax.plot([0, z1[0]], [0, z1[1]], color=辅助灰, lw=0.8)
    ax.plot([0, z2[0]], [0, z2[1]], color=辅助灰, lw=0.8)
    ax.plot([z1[0], z2[0]], [z1[1], z2[1]], "x", color=黑, ms=5, mew=1.1)
    ax.text(z1[0] + 0.08, z1[1] + 0.06, r"$z_1=e^{s_1T}$", ha="left", va="bottom")
    ax.text(z2[0] - 0.08, z2[1] - 0.08, r"$z_2=e^{s_2T}$", ha="right", va="top")
    ax.text(-1.22, 1.07, r"$|z|=1$", ha="left", va="bottom")
    ax.text(-0.95, 0.92, "Stable", ha="left", va="top", color="#27566F")
    ax.text(-1.27, -1.24, "(b)", fontsize=9, fontweight="bold", ha="left", va="bottom")

    fig.text(0.50, 0.975, r"$z=e^{sT},\quad |z|=e^{\sigma T},\quad \angle z=\omega T$", ha="center", va="top")
    return _保存(fig, "fig_pole_plane")


def _读取响应(文件名: str) -> tuple[np.ndarray, np.ndarray]:
    路径 = 数据目录 / 文件名
    if not 路径.is_file():
        raise FileNotFoundError(f"缺少已验收响应数据：{路径}")
    raw = np.loadtxt(路径, delimiter=",", skiprows=1, encoding="utf-8-sig")
    if raw.ndim != 2 or raw.shape[1] != 10:
        raise ValueError(f"{路径.name} 应为10列，实际{raw.shape}")
    time = raw[:, 0]
    response = np.empty((raw.shape[0], 3, 3), dtype=float)
    for floor in range(3):
        # 数据列顺序：Original, Guyan, Craig-Bampton。
        response[:, floor, :] = raw[:, 1 + floor * 3 : 4 + floor * 3]
    if not np.all(np.diff(time) > 0) or not np.all(np.isfinite(response)):
        raise ValueError(f"{路径.name} 时间不递增或含 NaN/Inf")
    return time, response


def _画三方法(ax: plt.Axes, time: np.ndarray, values: np.ndarray, *, local: bool) -> None:
    order = [(0, "Original"), (2, "Craig-Bampton"), (1, "Guyan")]
    stride = 1 if local else max(1, len(time) // 12_000)
    mark_every = max(1, len(time) // 9)
    for column, name in order:
        style = 样式.方法样式[name]
        kwargs: dict[str, object] = {
            "color": style["color"],
            "linestyle": style["linestyle"],
            "linewidth": 1.0 if local else 0.75,
            "label": name,
            "zorder": 3 if name == "Original" else 2,
        }
        if local:
            kwargs.update(
                marker=style["marker"],
                markevery=mark_every,
                markersize=3.2,
                markerfacecolor="white",
                markeredgewidth=0.7,
            )
        ax.plot(time[::stride], values[::stride, column], **kwargs)


def _绘制响应复合图(
    excitation: str,
    windows: tuple[tuple[float, float], tuple[float, float]],
    文件基名: str,
) -> tuple[Path, Path]:
    file_i = f"第一类划分_{excitation}.csv"
    file_ii = f"第二类划分_{excitation}.csv"
    time_i, response_i = _读取响应(file_i)
    time_ii, response_ii = _读取响应(file_ii)
    if not np.array_equal(time_i, time_ii):
        raise ValueError(f"{excitation} 两类划分的时间轴不一致")

    cases = [
        (response_i, 0),
        (response_i, 2),
        (response_ii, 0),
        (response_ii, 2),
    ]
    fig = plt.figure(figsize=(7.48, 7.85))
    grid = GridSpec(4, 3, figure=fig, width_ratios=[2.35, 1.0, 1.0], hspace=0.38, wspace=0.28)
    legend_handles = None
    legend_labels = None

    for row, ((response, floor), panel) in enumerate(zip(cases, ("(a)", "(b)", "(c)", "(d)"), strict=True)):
        values = response[:, floor, :]
        full_ax = fig.add_subplot(grid[row, 0])
        _画三方法(full_ax, time_i, values, local=False)
        full_ax.set_xlim(0.0, 40.0)
        full_ax.set_ylim(*_有限余量(values))
        full_ax.set_ylabel(r"Displacement (mm)")
        样式.设置坐标轴(full_ax, x主刻度数=5, y主刻度数=4)
        full_ax.text(
            0.02,
            0.92,
            panel,
            transform=full_ax.transAxes,
            va="top",
            ha="left",
            fontsize=9,
            fontweight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.8, "alpha": 0.85},
        )
        if row == 0:
            legend_handles, legend_labels = full_ax.get_legend_handles_labels()

        for col, window in enumerate(windows, start=1):
            ax = fig.add_subplot(grid[row, col])
            mask = (time_i >= window[0]) & (time_i <= window[1])
            if np.count_nonzero(mask) < 20:
                raise ValueError(f"{excitation} 局部窗 {window} 样本不足")
            local_time = time_i[mask]
            local_values = values[mask]
            _画三方法(ax, local_time, local_values, local=True)
            ax.set_xlim(*window)
            ax.set_ylim(*_有限余量(local_values))
            样式.设置坐标轴(ax, x主刻度数=4, y主刻度数=4)

        if row == 3:
            full_ax.set_xlabel(r"Time (s)")
            for col in (1, 2):
                fig.axes[-(3 - col)].set_xlabel(r"Time (s)")

    if legend_handles is None or legend_labels is None:
        raise RuntimeError("未获得响应图例")
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=3,
        frameon=False,
        columnspacing=1.4,
    )
    fig.subplots_adjust(left=0.095, right=0.985, bottom=0.065, top=0.955)
    return _保存(fig, 文件基名)


def 绘制_ElCentro响应图() -> tuple[Path, Path]:
    """期刊图6：组合大论文图3-6、3-8、3-9和3-10。"""
    return _绘制响应复合图(
        "ElCentro地震响应",
        ((10.0, 11.0), (21.5, 22.5)),
        "fig_eq_response",
    )


def 绘制_Chirp响应图() -> tuple[Path, Path]:
    """期刊图7：组合唯一编号图3-11、3-13、3-14和3-15。"""
    return _绘制响应复合图(
        "Chirp响应",
        ((13.0, 14.0), (38.0, 38.3)),
        "fig_chirp_response",
    )


def _读取稳定边界(文件名: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    路径 = 数据目录 / 文件名
    if not 路径.is_file():
        raise FileNotFoundError(f"缺少稳定域边界数据：{路径}")
    values: dict[str, list[tuple[float, float]]] = {"原结构": [], "Craig-Bampton": [], "Guyan": []}
    with 路径.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            method = row["方法"]
            if method not in values:
                raise ValueError(f"{路径.name} 出现未知方法：{method}")
            values[method].append((float(row["时滞1毫秒"]), float(row["时滞2毫秒"])))
    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for method, points in values.items():
        if not points:
            raise ValueError(f"{路径.name} 缺少 {method} 边界")
        arr = np.asarray(sorted(points), dtype=float)
        result[method] = arr[:, 0], arr[:, 1]
    return result


def 绘制_稳定域双面板图() -> tuple[Path, Path]:
    """期刊图8：组合大论文图4-4与图4-5，共享图例和纵轴范围。"""
    datasets = [
        _读取稳定边界("图4-4_第一类子结构划分稳定域_边界数据.csv"),
        _读取稳定边界("图4-5_第二类子结构划分稳定域_边界数据.csv"),
    ]
    english = {"原结构": "Original", "Craig-Bampton": "Craig-Bampton", "Guyan": "Guyan"}
    order = ["原结构", "Craig-Bampton", "Guyan"]
    ymax = max(float(y.max()) for dataset in datasets for _, y in dataset.values()) * 1.10

    fig, axes = plt.subplots(1, 2, figsize=(7.48, 3.15), sharey=True)
    legend_handles = None
    legend_labels = None
    for panel_index, (ax, dataset, panel) in enumerate(zip(axes, datasets, ("(a)", "(b)"), strict=True)):
        xmax = 0.0
        for method in order:
            x, y = dataset[method]
            xmax = max(xmax, float(x.max()))
            style = 样式.方法样式[english[method]]
            ax.plot(
                x,
                y,
                drawstyle="steps-post",
                color=style["color"],
                linestyle=style["linestyle"],
                marker=style["marker"],
                markerfacecolor="white",
                markeredgewidth=0.8,
                markevery=max(1, len(x) // 8),
                label=english[method],
            )
        ax.set_xlim(0.0, xmax * 1.08)
        ax.set_ylim(0.0, ymax)
        ax.set_xlabel(r"Delay $\tau_1$ (ms)")
        if panel_index == 0:
            ax.set_ylabel(r"Delay $\tau_2$ (ms)")
            legend_handles, legend_labels = ax.get_legend_handles_labels()
        样式.设置坐标轴(ax, x主刻度数=5, y主刻度数=5)
        ax.text(0.02, 0.96, panel, transform=ax.transAxes, va="top", ha="left", fontsize=9, fontweight="bold")

    if legend_handles is None or legend_labels is None:
        raise RuntimeError("未获得稳定域图例")
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=3,
        frameon=False,
        columnspacing=1.3,
    )
    fig.subplots_adjust(left=0.09, right=0.985, bottom=0.17, top=0.84, wspace=0.16)
    return _保存(fig, "fig_stability_domain")


全部绘图任务 = [
    ("fig_rths_loop", 绘制_RTHS闭环图),
    ("fig_pole_plane", 绘制_极点平面映射图),
    ("fig_benchmark_geometry", 绘制_基准结构几何图),
    ("fig_dof_idealization", 绘制_自由度理想化图),
    ("fig_division", 绘制_两类子结构划分图),
    ("fig_eq_response", 绘制_ElCentro响应图),
    ("fig_chirp_response", 绘制_Chirp响应图),
    ("fig_stability_domain", 绘制_稳定域双面板图),
]


def 生成全部图片() -> list[tuple[Path, Path]]:
    outputs: list[tuple[Path, Path]] = []
    for stem, function in 全部绘图任务:
        pdf, png = function()
        if pdf.stem != stem or png.stem != stem:
            raise RuntimeError(f"输出命名不一致：预期 {stem}，实际 {pdf.stem}/{png.stem}")
        outputs.append((pdf, png))
        print(f"已生成：{pdf.name} / {png.name}")
    return outputs


if __name__ == "__main__":
    生成全部图片()

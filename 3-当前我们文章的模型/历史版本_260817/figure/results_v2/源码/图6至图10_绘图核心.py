"""V2稿图6至图10的参数化绘图核心。

边界：
1. 图6至图9只读取本绘图包中的已验收响应CSV，不新增算例、不拟合曲线。
2. 图10只读取历史稳定域边界快照，是绘图级复现，不宣称重新求解闭环极点。
3. 每张响应图包含一层与三层两行；每行依次为40 s全时程和两个正文指定局部窗。
"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import FormatStrFormatter

import 科研绘图统一样式_V2 as 样式


源码目录 = Path(__file__).resolve().parent
数据目录 = 源码目录.parent / "输入数据"


def _有限余量(values: np.ndarray, 比例: float = 0.08) -> tuple[float, float]:
    lo = float(np.nanmin(values))
    hi = float(np.nanmax(values))
    span = hi - lo
    if span <= np.finfo(float).eps:
        span = max(abs(lo), 1.0)
    return lo - 比例 * span, hi + 比例 * span


def _读取响应(文件名: str) -> tuple[np.ndarray, np.ndarray]:
    路径 = 数据目录 / 文件名
    if not 路径.is_file():
        raise FileNotFoundError(f"缺少响应数据：{路径}")
    raw = np.loadtxt(路径, delimiter=",", skiprows=1, encoding="utf-8-sig")
    if raw.shape != (40_961, 10):
        raise ValueError(f"{路径.name} 应为40961×10，实际{raw.shape}")
    time = raw[:, 0]
    if time[0] != 0.0 or time[-1] != 40.0:
        raise ValueError(f"{路径.name} 时间范围不是0至40 s")
    if not np.all(np.diff(time) == 1.0 / 1024.0):
        raise ValueError(f"{路径.name} 时间步长不是1/1024 s")
    if not np.all(np.isfinite(raw)):
        raise ValueError(f"{路径.name} 含NaN或Inf")

    response = np.empty((raw.shape[0], 3, 3), dtype=float)
    for floor in range(3):
        # 每层三列依次为Original、Guyan、Craig-Bampton。
        response[:, floor, :] = raw[:, 1 + floor * 3 : 4 + floor * 3]
    return time, response


def _画三方法(ax: plt.Axes, time: np.ndarray, values: np.ndarray, *, local: bool) -> None:
    # 图例按Original、Craig-Bampton、Guyan排列；zorder确保灰色虚线参考在重合处仍可见。
    order = ((0, "Original"), (2, "Craig-Bampton"), (1, "Guyan"))
    stride = 1 if local else max(1, len(time) // 12_000)
    mark_every = max(1, len(time) // 9)
    for column, name in order:
        style = 样式.方法样式[name]
        kwargs: dict[str, object] = {
            "color": style["color"],
            "linestyle": style["linestyle"],
            "linewidth": 1.1 if local else 0.85,
            "label": name,
            "zorder": style["zorder"],
            "dash_capstyle": "butt",
            "solid_capstyle": "round",
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


def _设置局部横轴刻度(ax: plt.Axes, window: tuple[float, float]) -> None:
    """在窄局部窗中固定三个刻度，避免标签相互覆盖。"""
    ticks = np.linspace(window[0], window[1], 3)
    decimals = 2 if window[1] - window[0] <= 0.35 else 1
    ax.set_xticks(ticks)
    ax.xaxis.set_major_formatter(FormatStrFormatter(f"%.{decimals}f"))


def _绘制两层响应图(
    输入文件名: str,
    windows: tuple[tuple[float, float], tuple[float, float]],
    输出基名: str,
) -> tuple[Path, Path]:
    time, response = _读取响应(输入文件名)
    floors = (0, 2)
    panels = ("(a)", "(b)")

    # 6.30 in对应当前A4稿约160 mm正文宽度，插入TeX后9 pt字体基本不缩放。
    fig = plt.figure(figsize=(6.30, 3.82))
    grid = GridSpec(2, 3, figure=fig, width_ratios=[2.30, 1.0, 1.0], hspace=0.34, wspace=0.30)
    legend_handles = None
    legend_labels = None

    for row, (floor, panel) in enumerate(zip(floors, panels, strict=True)):
        values = response[:, floor, :]
        full_ax = fig.add_subplot(grid[row, 0])
        _画三方法(full_ax, time, values, local=False)
        full_ax.set_xlim(0.0, 40.0)
        full_ax.set_ylim(*_有限余量(values))
        full_ax.set_ylabel(r"Displacement (mm)")
        样式.设置坐标轴(full_ax, x主刻度数=5, y主刻度数=4)
        full_ax.text(
            0.025,
            0.92,
            panel,
            transform=full_ax.transAxes,
            va="top",
            ha="left",
            fontsize=9,
            fontweight="bold",
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.5, "alpha": 0.82},
        )
        if row == 0:
            legend_handles, legend_labels = full_ax.get_legend_handles_labels()

        local_axes: list[plt.Axes] = []
        for col, window in enumerate(windows, start=1):
            ax = fig.add_subplot(grid[row, col])
            mask = (time >= window[0]) & (time <= window[1])
            if np.count_nonzero(mask) < 20:
                raise ValueError(f"{输入文件名} 局部窗{window}样本不足")
            local_time = time[mask]
            local_values = values[mask]
            _画三方法(ax, local_time, local_values, local=True)
            ax.set_xlim(*window)
            ax.set_ylim(*_有限余量(local_values))
            样式.设置坐标轴(ax, x主刻度数=3, y主刻度数=4)
            _设置局部横轴刻度(ax, window)
            local_axes.append(ax)

        if row == 1:
            full_ax.set_xlabel(r"Time (s)")
            for ax in local_axes:
                ax.set_xlabel(r"Time (s)")

    if legend_handles is None or legend_labels is None:
        raise RuntimeError("未获得响应图例")
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=3,
        frameon=False,
        columnspacing=1.25,
    )
    fig.subplots_adjust(left=0.105, right=0.990, bottom=0.125, top=0.900)
    return 样式.导出图片(fig, 输出基名)


def 绘制_图6_第一类ElCentro响应() -> tuple[Path, Path]:
    return _绘制两层响应图(
        "第一类划分_ElCentro地震响应.csv",
        ((10.0, 11.0), (21.5, 22.5)),
        "fig06_eq_div1",
    )


def 绘制_图7_第二类ElCentro响应() -> tuple[Path, Path]:
    return _绘制两层响应图(
        "第二类划分_ElCentro地震响应.csv",
        ((10.0, 11.0), (21.5, 22.5)),
        "fig07_eq_div2",
    )


def 绘制_图8_第一类Chirp响应() -> tuple[Path, Path]:
    return _绘制两层响应图(
        "第一类划分_Chirp响应.csv",
        ((13.0, 14.0), (38.0, 38.3)),
        "fig08_chirp_div1",
    )


def 绘制_图9_第二类Chirp响应() -> tuple[Path, Path]:
    return _绘制两层响应图(
        "第二类划分_Chirp响应.csv",
        ((13.0, 14.0), (38.0, 38.3)),
        "fig09_chirp_div2",
    )


def _读取稳定边界(文件名: str) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    路径 = 数据目录 / 文件名
    if not 路径.is_file():
        raise FileNotFoundError(f"缺少稳定域边界数据：{路径}")
    values: dict[str, list[tuple[float, float]]] = {
        "原结构": [],
        "Craig-Bampton": [],
        "Guyan": [],
    }
    with 路径.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            method = row["方法"]
            if method not in values:
                raise ValueError(f"{路径.name} 出现未知方法：{method}")
            values[method].append((float(row["时滞1毫秒"]), float(row["时滞2毫秒"])))

    result: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for method, points in values.items():
        if not points:
            raise ValueError(f"{路径.name} 缺少{method}边界")
        arr = np.asarray(sorted(points), dtype=float)
        result[method] = arr[:, 0], arr[:, 1]
    return result


def 绘制_图10_稳定域双面板() -> tuple[Path, Path]:
    datasets = (
        _读取稳定边界("图4-4_第一类子结构划分稳定域_边界数据.csv"),
        _读取稳定边界("图4-5_第二类子结构划分稳定域_边界数据.csv"),
    )
    english = {"原结构": "Original", "Craig-Bampton": "Craig-Bampton", "Guyan": "Guyan"}
    order = ("原结构", "Craig-Bampton", "Guyan")
    ymax = max(float(y.max()) for dataset in datasets for _, y in dataset.values()) * 1.10

    fig, axes = plt.subplots(1, 2, figsize=(6.30, 2.72), sharey=True)
    legend_handles = None
    legend_labels = None
    for panel_index, (ax, dataset, panel) in enumerate(zip(axes, datasets, ("(a)", "(b)"), strict=True)):
        xmax = 0.0
        for method in order:
            x, y = dataset[method]
            xmax = max(xmax, float(x.max()))
            name = english[method]
            style = 样式.方法样式[name]
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
                linewidth=1.2,
                zorder=style["zorder"],
                label=name,
            )
        ax.set_xlim(0.0, xmax * 1.08)
        ax.set_ylim(0.0, ymax)
        ax.set_xlabel(r"Delay $\tau_1$ (ms)")
        if panel_index == 0:
            ax.set_ylabel(r"Delay $\tau_2$ (ms)")
            legend_handles, legend_labels = ax.get_legend_handles_labels()
        样式.设置坐标轴(ax, x主刻度数=5, y主刻度数=5)
        ax.text(
            0.02,
            1.02,
            panel,
            transform=ax.transAxes,
            va="bottom",
            ha="left",
            fontsize=9,
            fontweight="bold",
            clip_on=False,
        )

    if legend_handles is None or legend_labels is None:
        raise RuntimeError("未获得稳定域图例")
    fig.legend(
        legend_handles,
        legend_labels,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=3,
        frameon=False,
        columnspacing=1.25,
    )
    fig.subplots_adjust(left=0.105, right=0.990, bottom=0.180, top=0.845, wspace=0.18)
    return 样式.导出图片(fig, "fig10_stability_domain")

"""梁禹 RHTS 图片包的统一科研绘图样式。

所有最终图使用 Computer Modern、9 pt、Tol Bright 色板、向内四边刻度，
并同时导出矢量 PDF 与 600 dpi PNG。图内标题默认禁止。
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


颜色 = {
    "原结构": "#333333",
    "Craig-Bampton": "#4477AA",
    "Guyan": "#EE6677",
    "绿色": "#228833",
    "黄色": "#CCBB44",
    "紫色": "#AA3377",
    "青色": "#66CCEE",
    "灰色": "#BBBBBB",
}

方法样式 = {
    "Origin": {"color": 颜色["原结构"], "linestyle": "-", "marker": None},
    "Craig-Bampton": {"color": 颜色["Craig-Bampton"], "linestyle": "-", "marker": "o"},
    "Guyan": {"color": 颜色["Guyan"], "linestyle": "--", "marker": "s"},
}


def 配置科研绘图样式() -> None:
    """设置全局绘图参数；最终图依赖本机 TeX Live 渲染 Computer Modern。"""
    mpl.rcParams.update(
        {
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["Computer Modern Roman"],
            "font.size": 9,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
            "lines.markersize": 4,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "xtick.minor.visible": False,
            "ytick.minor.visible": False,
            "axes.grid": False,
            "axes.axisbelow": True,
            "legend.frameon": False,
            "legend.handlelength": 1.7,
            "legend.handletextpad": 0.4,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def 图幅尺寸(每行图数: int = 2, 高宽比: float = 0.75) -> tuple[float, float]:
    """按双栏总宽 7.48 inch 返回单图尺寸。"""
    if 每行图数 not in (1, 2, 3):
        raise ValueError("每行图数必须为1、2或3")
    总宽 = 7.48
    间距 = 0.20
    宽 = (总宽 - 间距 * (每行图数 - 1)) / 每行图数
    return 宽, 宽 * 高宽比


def 设置坐标轴(ax: mpl.axes.Axes, x主刻度数: int = 5, y主刻度数: int = 5) -> None:
    """应用坐标轴规范并显式清除标题/网格。"""
    ax.set_title("")
    ax.grid(False)
    ax.tick_params(direction="in", top=True, right=True, width=0.8)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=x主刻度数))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=y主刻度数))
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)


def 添加子图标注(ax: mpl.axes.Axes, 标签: str) -> None:
    ax.text(
        0.02,
        0.96,
        标签,
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        fontweight="bold",
    )


def 导出图片(fig: mpl.figure.Figure, 输出基名: str | Path) -> tuple[Path, Path]:
    """同时导出矢量 PDF 和 600 dpi PNG；输出基名不带扩展名。"""
    基名 = Path(输出基名)
    基名.parent.mkdir(parents=True, exist_ok=True)
    pdf = 基名.with_suffix(".pdf")
    png = 基名.with_suffix(".png")
    fig.savefig(pdf, format="pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(png, format="png", dpi=600, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    if not pdf.exists() or pdf.stat().st_size == 0:
        raise RuntimeError(f"PDF导出失败：{pdf}")
    if not png.exists() or png.stat().st_size == 0:
        raise RuntimeError(f"PNG导出失败：{png}")
    return pdf, png


def 验证图对象(fig: mpl.figure.Figure, 允许标题: bool = False) -> list[str]:
    """返回图对象违反统一样式的错误列表。"""
    错误: list[str] = []
    for 序号, ax in enumerate(fig.axes, start=1):
        if not 允许标题 and ax.get_title().strip():
            错误.append(f"坐标轴{序号}存在标题：{ax.get_title()}")
        if hasattr(ax, "xaxis"):
            网格可见 = any(line.get_visible() for line in ax.get_xgridlines() + ax.get_ygridlines())
            if 网格可见:
                错误.append(f"坐标轴{序号}存在可见网格")
    return 错误


def 等间隔标记索引(样本数: int, 目标标记数: int = 12, 偏移: int = 0) -> Iterable[int]:
    if 样本数 <= 0:
        return []
    步长 = max(1, 样本数 // max(1, 目标标记数))
    起点 = min(max(0, 偏移), 样本数 - 1)
    return range(起点, 样本数, 步长)


配置科研绘图样式()

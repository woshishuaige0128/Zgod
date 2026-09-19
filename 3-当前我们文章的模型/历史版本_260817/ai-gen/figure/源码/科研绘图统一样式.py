"""期刊稿八组图片的统一科研绘图样式与导出工具。

规范来源：Doctor Bego 指定的 scientific-plotting skill。
所有图采用 Computer Modern 9 pt、Tol Bright 色盲友好配色、四边向内刻度，
并同时输出矢量 PDF 与 600 dpi PNG。
"""

from __future__ import annotations

from pathlib import Path

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
    "浅蓝": "#D9EEF7",
}

方法样式 = {
    "Original": {"color": 颜色["原结构"], "linestyle": "-", "marker": "o"},
    "Craig-Bampton": {"color": 颜色["Craig-Bampton"], "linestyle": "--", "marker": "s"},
    "Guyan": {"color": 颜色["Guyan"], "linestyle": "-.", "marker": "^"},
}


def 配置科研绘图样式() -> None:
    """应用全文统一的期刊绘图参数。"""
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
            "legend.frameon": False,
            "legend.handlelength": 1.8,
            "legend.handletextpad": 0.4,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def 设置坐标轴(ax: mpl.axes.Axes, x主刻度数: int = 5, y主刻度数: int = 5) -> None:
    """设置坐标轴线宽、刻度、标题和网格。"""
    ax.set_title("")
    ax.grid(False)
    ax.tick_params(which="major", direction="in", top=True, right=True, width=0.8, length=3.5)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=x主刻度数))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=y主刻度数))
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)


def 导出图片(fig: mpl.figure.Figure, 输出基名: str | Path) -> tuple[Path, Path]:
    """把同一图对象导出为单页矢量 PDF 与 600 dpi PNG。"""
    基名 = Path(输出基名)
    基名.parent.mkdir(parents=True, exist_ok=True)
    pdf = 基名.with_suffix(".pdf")
    png目录 = 基名.parent.parent / "PNG"
    png目录.mkdir(parents=True, exist_ok=True)
    png = png目录 / f"{基名.name}.png"
    fig.savefig(pdf, format="pdf", bbox_inches="tight", pad_inches=0.02)
    fig.savefig(png, format="png", dpi=600, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    if not pdf.is_file() or pdf.stat().st_size < 1_000:
        raise RuntimeError(f"PDF 导出失败或文件过小：{pdf}")
    if not png.is_file() or png.stat().st_size < 10_000:
        raise RuntimeError(f"PNG 导出失败或文件过小：{png}")
    return pdf, png


配置科研绘图样式()

"""图6至图10的统一科研绘图样式与导出工具。

方法身份由 Doctor Bego 于 2026-08-24 最终指定：
- Original：深灰色虚线；
- Craig-Bampton：红色实线；
- Guyan：蓝色点划线。

所有图采用 Computer Modern 9 pt、四边向内刻度、无网格和无边框图例，
同时输出单页矢量PDF与600 dpi PNG。
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


颜色 = {
    "Original": "#555555",
    "Craig-Bampton": "#EE6677",
    "Guyan": "#4477AA",
}

方法样式 = {
    "Original": {
        "color": 颜色["Original"],
        "linestyle": "--",
        "marker": "o",
        "zorder": 4,
    },
    "Craig-Bampton": {
        "color": 颜色["Craig-Bampton"],
        "linestyle": "-",
        "marker": "s",
        "zorder": 3,
    },
    "Guyan": {
        "color": 颜色["Guyan"],
        "linestyle": "-.",
        "marker": "^",
        "zorder": 2,
    },
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
            "legend.handlelength": 2.2,
            "legend.handletextpad": 0.45,
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
    """统一刻度、边框与标题状态。"""
    ax.set_title("")
    ax.grid(False)
    ax.tick_params(which="major", direction="in", top=True, right=True, width=0.8, length=3.5)
    ax.xaxis.set_major_locator(MaxNLocator(nbins=x主刻度数))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=y主刻度数))
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)


def 导出图片(fig: mpl.figure.Figure, 文件基名: str) -> tuple[Path, Path]:
    """导出到本绘图包的PDF和PNG目录。"""
    根目录 = Path(__file__).resolve().parent.parent
    pdf目录 = 根目录 / "PDF"
    png目录 = 根目录 / "PNG"
    pdf目录.mkdir(parents=True, exist_ok=True)
    png目录.mkdir(parents=True, exist_ok=True)
    pdf = pdf目录 / f"{文件基名}.pdf"
    png = png目录 / f"{文件基名}.png"
    fig.savefig(pdf, format="pdf", bbox_inches="tight", pad_inches=0.02, facecolor="white")
    fig.savefig(png, format="png", dpi=600, bbox_inches="tight", pad_inches=0.02, facecolor="white")
    plt.close(fig)
    if not pdf.is_file() or pdf.stat().st_size < 1_000:
        raise RuntimeError(f"PDF导出失败或文件过小：{pdf}")
    if not png.is_file() or png.stat().st_size < 10_000:
        raise RuntimeError(f"PNG导出失败或文件过小：{png}")
    return pdf, png


配置科研绘图样式()

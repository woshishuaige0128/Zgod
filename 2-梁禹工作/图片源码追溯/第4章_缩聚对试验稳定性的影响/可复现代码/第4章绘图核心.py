from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import matplotlib

matplotlib.use("Agg")

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.ticker import MaxNLocator
from scipy.io import loadmat


代码目录 = Path(__file__).resolve().parent
章节目录 = 代码目录.parent
来源目录 = 章节目录 / "原始来源副本"
数据目录 = 章节目录 / "输入数据"
PDF目录 = 章节目录 / "PDF结果"
PNG目录 = 章节目录 / "PNG结果"

采样周期秒 = 1.0 / 1024.0
采样周期毫秒 = 1000.0 * 采样周期秒

颜色 = {
    "原结构": "#333333",
    "Craig-Bampton": "#EE6677",
    "Guyan": "#4477AA",
    "浅蓝": "#D9EEF7",
    "界面蓝": "#4477AA",
    "反馈红": "#AA3377",
    "辅助灰": "#777777",
}

图片文件名 = {
    "4-1": "图4-1_含时滞RTHS闭环控制系统",
    "4-2": "图4-2_s域与z域极点映射",
    "4-3": "图4-3_多层框架RTHS子结构耦合",
    "4-4": "图4-4_第一类子结构划分稳定域",
    "4-5": "图4-5_第二类子结构划分稳定域",
}


def 设置科研绘图样式() -> None:
    """应用本章统一的 SCI 绘图规范。"""
    mpl.rcParams.update(
        {
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["Computer Modern Roman"],
            "font.size": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "xtick.minor.visible": False,
            "ytick.minor.visible": False,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
            "lines.markersize": 4,
            "legend.frameon": False,
            "axes.grid": False,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "figure.constrained_layout.use": True,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def 保存图片(fig: plt.Figure, 唯一ID: str) -> Tuple[Path, Path]:
    PDF目录.mkdir(parents=True, exist_ok=True)
    PNG目录.mkdir(parents=True, exist_ok=True)
    stem = 图片文件名[唯一ID]
    pdf = PDF目录 / f"{stem}.pdf"
    png = PNG目录 / f"{stem}.png"
    fig.savefig(pdf, format="pdf")
    fig.savefig(png, format="png", dpi=600, facecolor="white")
    plt.close(fig)
    return pdf, png


def _圆角框(ax, xy, width, height, text, edge="#333333", face="white"):
    patch = FancyBboxPatch(
        xy,
        width,
        height,
        boxstyle="round,pad=0.04,rounding_size=0.08",
        linewidth=1.0,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    ax.text(xy[0] + width / 2, xy[1] + height / 2, text, ha="center", va="center")
    return patch


def _箭头(ax, start, end, color="#333333", style="-|>", lw=1.1, mutation=10):
    arrow = FancyArrowPatch(
        start,
        end,
        arrowstyle=style,
        mutation_scale=mutation,
        linewidth=lw,
        color=color,
        shrinkA=0,
        shrinkB=0,
        connectionstyle="arc3",
    )
    ax.add_patch(arrow)
    return arrow


def 绘制图4_1() -> Tuple[Path, Path]:
    """基于梁禹手稿图4-1及鲁旭杰[48]引用关系作语义等价矢量重绘。"""
    设置科研绘图样式()
    fig, ax = plt.subplots(figsize=(7.48, 3.25))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6)
    ax.axis("off")

    _圆角框(
        ax,
        (2.0, 3.55),
        3.15,
        1.45,
        "Numerical substructure\n$\\mathbf{M}_n,\\,\\mathbf{C}_n,\\,\\mathbf{K}_n$",
        edge=颜色["原结构"],
        face="#F5F5F5",
    )
    _圆角框(
        ax,
        (7.25, 3.55),
        2.45,
        1.45,
        "Controller and actuator\n$e^{-\\tau s}$",
        edge=颜色["界面蓝"],
        face="#EEF5FA",
    )
    _圆角框(
        ax,
        (7.05, 0.65),
        2.85,
        1.45,
        "Physical substructure\n$\\mathbf{M}_e,\\,\\mathbf{C}_e,\\,\\mathbf{K}_e$",
        edge=颜色["原结构"],
        face="#F5F5F5",
    )

    _箭头(ax, (0.45, 4.28), (2.0, 4.28), color=颜色["原结构"])
    ax.text(0.50, 4.55, r"Ground motion $a_g(t)$", ha="left", va="bottom")

    _箭头(ax, (5.15, 4.28), (7.25, 4.28), color=颜色["界面蓝"])
    ax.text(6.20, 4.55, r"Command displacement $u_c(t)$", ha="center", va="bottom", color=颜色["界面蓝"])

    _箭头(ax, (8.48, 3.55), (8.48, 2.10), color=颜色["界面蓝"])
    ax.text(8.70, 2.82, r"Delayed displacement $u(t-\tau)$", ha="left", va="center", color=颜色["界面蓝"])

    # 物理子结构反力沿闭环反馈至数值子结构。
    ax.plot([7.05, 1.15, 1.15], [1.37, 1.37, 3.83], color=颜色["反馈红"], lw=1.1)
    _箭头(ax, (1.15, 3.83), (2.0, 3.83), color=颜色["反馈红"])
    ax.text(4.05, 1.62, r"Measured restoring force $R_e(t)$", ha="center", va="bottom", color=颜色["反馈红"])

    # 单独标出闭环接口，避免将重绘图误解为开环信号图。
    ax.plot(8.48, 2.10, marker="o", ms=4, mfc="white", mec=颜色["界面蓝"], mew=1.0)
    ax.plot(7.05, 1.37, marker="s", ms=4, mfc="white", mec=颜色["反馈红"], mew=1.0)

    return 保存图片(fig, "4-1")


def _复平面坐标轴(ax, xlim, ylim, xlabel, ylabel, xlabel_y_factor=-0.12):
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.set_aspect("equal", adjustable="box")
    ax.axis("off")
    _箭头(ax, (xlim[0], 0), (xlim[1], 0), lw=0.9, mutation=8)
    _箭头(ax, (0, ylim[0]), (0, ylim[1]), lw=0.9, mutation=8)
    ax.text(xlim[1], xlabel_y_factor * (ylim[1] - ylim[0]), xlabel, ha="right", va="top")
    ax.text(0.04 * (xlim[1] - xlim[0]), ylim[1], ylabel, ha="left", va="top")


def 绘制图4_2() -> Tuple[Path, Path]:
    设置科研绘图样式()
    fig, axes = plt.subplots(1, 2, figsize=(7.48, 3.05), layout="none")
    # 顶部留出独立公式带，避免公式与右图单位圆标注互相叠压。
    fig.subplots_adjust(left=0.035, right=0.985, bottom=0.08, top=0.80, wspace=0.28)

    ax = axes[0]
    ax.add_patch(Rectangle((-2.2, -2.0), 2.2, 4.0, facecolor=颜色["浅蓝"], edgecolor="none", zorder=0))
    _复平面坐标轴(ax, (-2.2, 1.15), (-2.0, 2.0), r"$\mathrm{Re}(s)$", r"$\mathrm{Im}(s)$")
    sigma, omega = -1.15, 0.95
    ax.plot([sigma, 0], [omega, omega], ls="--", lw=0.8, color=颜色["辅助灰"])
    ax.plot([sigma, 0], [-omega, -omega], ls="--", lw=0.8, color=颜色["辅助灰"])
    ax.plot([sigma, sigma], [-omega, omega], ls=":", lw=0.7, color=颜色["辅助灰"])
    ax.plot([sigma, sigma], [omega, -omega], "x", color=颜色["原结构"], ms=5, mew=1.1)
    ax.text(sigma + 0.08, omega + 0.12, r"$s_1=\sigma+j\omega$", ha="left", va="bottom")
    ax.text(sigma + 0.08, -omega - 0.12, r"$s_2=\sigma-j\omega$", ha="left", va="top")
    ax.text(-1.92, 1.62, "Stable", ha="left", va="top", color="#27566F")
    ax.text(0.10, omega, r"$\omega$", ha="left", va="center")
    ax.text(0.10, -omega, r"$-\omega$", ha="left", va="center")

    ax = axes[1]
    unit = Circle((0, 0), 1.0, facecolor=颜色["浅蓝"], edgecolor=颜色["原结构"], linewidth=1.0)
    ax.add_patch(unit)
    _复平面坐标轴(
        ax,
        (-1.35, 1.35),
        (-1.35, 1.35),
        r"$\mathrm{Re}(z)$",
        r"$\mathrm{Im}(z)$",
        xlabel_y_factor=-0.03,
    )
    T = 0.6
    radius = np.exp(sigma * T)
    theta = omega * T
    z1 = (radius * np.cos(theta), radius * np.sin(theta))
    z2 = (radius * np.cos(theta), -radius * np.sin(theta))
    ax.plot([0, z1[0]], [0, z1[1]], color=颜色["辅助灰"], lw=0.8)
    ax.plot([0, z2[0]], [0, z2[1]], color=颜色["辅助灰"], lw=0.8)
    ax.plot([z1[0], z2[0]], [z1[1], z2[1]], "x", color=颜色["原结构"], ms=5, mew=1.1)
    ax.text(z1[0] + 0.08, z1[1] + 0.06, r"$z_1=e^{s_1T}$", ha="left", va="bottom")
    ax.text(z2[0] - 0.08, z2[1] - 0.08, r"$z_2=e^{s_2T}$", ha="right", va="top")
    ax.text(-1.22, 1.07, r"$|z|=1$", ha="left", va="bottom")
    ax.text(-0.95, 0.92, "Stable", ha="left", va="top", color="#27566F")

    fig.text(0.50, 0.975, r"$z=e^{sT},\quad |z|=e^{\sigma T},\quad \angle z=\omega T$", ha="center", va="top")
    return 保存图片(fig, "4-2")


def _质量点(ax, x, y, label, radius=0.23, face="#F4F4F4"):
    c = Circle((x, y), radius, facecolor=face, edgecolor=颜色["原结构"], linewidth=0.9)
    ax.add_patch(c)
    ax.text(x, y, label, ha="center", va="center")
    return c


def _固定支座(ax, x, y, width=0.65):
    ax.plot([x, x], [y, y + 0.25], color=颜色["原结构"], lw=1.0)
    ax.plot([x - width / 2, x + width / 2], [y, y], color=颜色["原结构"], lw=1.0)
    for dx in np.linspace(-width / 2, width / 2 - 0.08, 6):
        ax.plot([x + dx, x + dx - 0.10], [y, y - 0.18], color=颜色["原结构"], lw=0.6)


def _质量链(ax, x, levels, labels):
    for y1, y2 in zip(levels[:-1], levels[1:]):
        ax.plot([x, x], [y1 + 0.23, y2 - 0.23], color=颜色["辅助灰"], lw=0.8)
    for y, label in zip(levels, labels):
        _质量点(ax, x, y, label)


def 绘制图4_3() -> Tuple[Path, Path]:
    设置科研绘图样式()
    fig, ax = plt.subplots(figsize=(7.48, 4.15))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.5)
    ax.axis("off")

    # 完整多层框架的集中质量示意。
    levels_full = [0.85, 1.85, 3.05, 4.35, 5.35]
    _质量链(ax, 1.75, levels_full, [r"$m_1$", r"$m_2$", r"$\vdots$", r"$m_{n-1}$", r"$m_n$"])
    _固定支座(ax, 1.75, 0.38)
    ax.text(1.75, 6.10, "Complete structure", ha="center", va="top")
    _箭头(ax, (2.65, 3.05), (3.65, 3.05), color=颜色["原结构"])

    # 数值与物理子结构。
    phys_box = Rectangle((5.0, 3.30), 3.65, 2.55, fill=False, ls="--", lw=0.9, ec=颜色["辅助灰"])
    num_box = Rectangle((5.0, 0.45), 3.65, 2.55, fill=False, ls="--", lw=0.9, ec=颜色["辅助灰"])
    ax.add_patch(phys_box)
    ax.add_patch(num_box)
    ax.text(6.825, 5.70, "Physical substructure", ha="center", va="top")
    ax.text(6.825, 2.85, "Numerical substructure", ha="center", va="top")

    _质量链(ax, 6.85, [4.00, 4.68, 5.32], [r"$m_{k+1}$", r"$m_{n-1}$", r"$m_n$"])
    _质量链(ax, 6.85, [0.95, 1.70, 2.45], [r"$m_1$", r"$m_2$", r"$m_k$"])
    _固定支座(ax, 6.85, 0.60)

    ax.plot([5.0, 8.65], [3.15, 3.15], color=颜色["辅助灰"], ls=":", lw=0.8)
    ax.text(
        8.18,
        3.15,
        "Interface",
        ha="right",
        va="center",
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 1.5},
    )

    # 接口作动器用弹簧和滑台符号表达。
    spring_x = np.linspace(5.55, 6.45, 9)
    spring_y = 3.62 + 0.10 * np.array([0, 1, -1, 1, -1, 1, -1, 1, 0])
    ax.plot(spring_x, spring_y, color=颜色["原结构"], lw=0.9)
    ax.add_patch(Rectangle((6.45, 3.52), 0.75, 0.20, facecolor="#E8E8E8", edgecolor=颜色["原结构"], lw=0.8))
    ax.text(5.92, 3.91, "Actuator", ha="center", va="bottom")

    # 命令位移与恢复力构成双向闭环。
    ax.plot([5.0, 4.25, 4.25, 5.55], [1.70, 1.70, 3.62, 3.62], color=颜色["界面蓝"], lw=1.1)
    _箭头(ax, (4.25, 3.62), (5.55, 3.62), color=颜色["界面蓝"])
    ax.text(4.05, 2.60, "Command\ndisplacement", ha="right", va="center", color=颜色["界面蓝"])

    ax.plot([7.20, 9.50, 9.50, 8.65], [3.62, 3.62, 1.70, 1.70], color=颜色["反馈红"], lw=1.1)
    _箭头(ax, (9.50, 1.70), (8.65, 1.70), color=颜色["反馈红"])
    ax.text(9.68, 2.60, "Restoring\nforce", ha="left", va="center", color=颜色["反馈红"])

    return 保存图片(fig, "4-3")


def 读取稳定域掩膜(类别: int) -> Tuple[Dict[str, np.ndarray], Dict[str, Tuple[int, int]]]:
    if 类别 == 1:
        path = 来源目录 / "第一类划分最终绘图数据_lqr_2.mat"
    elif 类别 == 2:
        path = 来源目录 / "第二类划分最终绘图数据_lqr_3.mat"
    else:
        raise ValueError("类别必须为1或2")

    raw = loadmat(path)
    variable_map = {
        "原结构": "stab_o",
        "Craig-Bampton": "stab_C",
        "Guyan": "stab_g",
    }
    common_shape = tuple(np.asarray(raw["stab_o"]).shape)
    masks: Dict[str, np.ndarray] = {}
    raw_shapes: Dict[str, Tuple[int, int]] = {}

    for method, key in variable_map.items():
        values = np.asarray(raw[key], dtype=float)
        raw_shapes[method] = tuple(values.shape)
        if values.shape[0] < common_shape[0] or values.shape[1] < common_shape[1]:
            raise ValueError(f"{key}尺寸{values.shape}小于共同物理网格{common_shape}")
        values = values[: common_shape[0], : common_shape[1]]
        mask = np.isfinite(values) & (values > 0.0) & (values < 1.0)

        # 三份源数据的稳定区均应从零时滞轴连续填充至上边界，禁止静默跨洞插值。
        for col in range(mask.shape[1]):
            rows = np.flatnonzero(mask[:, col])
            if rows.size and not np.array_equal(rows, np.arange(rows[-1] + 1)):
                raise ValueError(f"{key}第{col + 1}列稳定区存在孔洞，不能用单值边界表示")
        masks[method] = mask

    return masks, raw_shapes


def 提取上边界(mask: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    x_index = []
    y_index = []
    for col in range(mask.shape[1]):
        rows = np.flatnonzero(mask[:, col])
        if rows.size:
            x_index.append(col + 1)
            y_index.append(rows[-1] + 1)
    x_index = np.asarray(x_index, dtype=int)
    y_index = np.asarray(y_index, dtype=int)
    delay_1_ms = (x_index - 1) * 采样周期毫秒
    delay_2_ms = (y_index - 1) * 采样周期毫秒
    return x_index, y_index, delay_1_ms, delay_2_ms


def 绘制稳定域(类别: int) -> Tuple[Path, Path]:
    设置科研绘图样式()
    masks, _ = 读取稳定域掩膜(类别)
    fig, ax = plt.subplots(figsize=(7.48, 4.05))

    styles = {
        "原结构": dict(color=颜色["原结构"], ls="--", marker="o"),
        "Craig-Bampton": dict(color=颜色["Craig-Bampton"], ls="-", marker="s"),
        "Guyan": dict(color=颜色["Guyan"], ls="-.", marker="^"),
    }
    english = {"原结构": "Original", "Craig-Bampton": "Craig-Bampton", "Guyan": "Guyan"}

    max_x = 0.0
    max_y = 0.0
    for method in ["原结构", "Craig-Bampton", "Guyan"]:
        _, _, x_ms, y_ms = 提取上边界(masks[method])
        max_x = max(max_x, float(x_ms.max()))
        max_y = max(max_y, float(y_ms.max()))
        mark_every = max(1, len(x_ms) // 12)
        ax.plot(
            x_ms,
            y_ms,
            drawstyle="steps-post",
            label=english[method],
            markerfacecolor="white",
            markeredgewidth=0.9,
            markevery=mark_every,
            **styles[method],
        )

    ax.set_xlabel(r"Delay $\tau_1$ (ms)")
    ax.set_ylabel(r"Delay $\tau_2$ (ms)")
    ax.set_xlim(0.0, max_x * 1.08)
    ax.set_ylim(0.0, max_y * 1.10)
    ax.set_aspect("equal", adjustable="box")
    ax.xaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=6))
    ax.tick_params(which="both", direction="in", top=True, right=True)
    ax.grid(False)
    ax.set_title("")
    ax.legend(loc="upper right", frameon=False, handlelength=2.2, handletextpad=0.5)

    return 保存图片(fig, "4-4" if 类别 == 1 else "4-5")


def 绘制图4_4() -> Tuple[Path, Path]:
    return 绘制稳定域(1)


def 绘制图4_5() -> Tuple[Path, Path]:
    return 绘制稳定域(2)


def 生成全部图片() -> None:
    jobs = [绘制图4_1, 绘制图4_2, 绘制图4_3, 绘制图4_4, 绘制图4_5]
    for job in jobs:
        pdf, png = job()
        print(f"已生成: {pdf.name} / {png.name}")


if __name__ == "__main__":
    生成全部图片()

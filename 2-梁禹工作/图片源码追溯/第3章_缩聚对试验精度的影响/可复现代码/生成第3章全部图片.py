#!/usr/bin/env python
"""从保存的真实 Simulink 数据重绘第3章全部13张图片。

可从任意当前目录执行：
    D:/Software/python/python.exe 生成第3章全部图片.py

本脚本不运行 MATLAB、不拟合曲线。图3-5至图3-15只读取本章输入数据中的
MAT 文件；图3-1和图3-2读取/刷新结构自由度参数 JSON/CSV 后矢量重绘。
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Circle, FancyArrowPatch, Polygon, Rectangle
from matplotlib.ticker import MaxNLocator
from PIL import Image
from scipy.io import loadmat


CODE_DIR = Path(__file__).resolve().parent
CHAPTER_DIR = CODE_DIR.parent
DATA_DIR = CHAPTER_DIR / "输入数据"
PDF_DIR = CHAPTER_DIR / "PDF结果"
PNG_DIR = CHAPTER_DIR / "PNG结果"
VERIFY_DIR = CHAPTER_DIR / "验证记录"

PDF_DIR.mkdir(parents=True, exist_ok=True)
PNG_DIR.mkdir(parents=True, exist_ok=True)
VERIFY_DIR.mkdir(parents=True, exist_ok=True)

# 全文固定映射：原结构深灰、Craig-Bampton蓝、Guyan红。
STYLES = {
    "Original": {"color": "#333333", "linestyle": "-", "marker": "o"},
    "Craig-Bampton": {"color": "#4477AA", "linestyle": "--", "marker": "^"},
    "Guyan": {"color": "#EE6677", "linestyle": "-.", "marker": "s"},
}
FLOOR_STYLES = [
    {"color": "#4477AA", "linestyle": "-", "label": "Floor 1"},
    {"color": "#EE6677", "linestyle": "--", "label": "Floor 2"},
    {"color": "#228833", "linestyle": "-.", "label": "Floor 3"},
]


def setup_style() -> None:
    """应用 scientific-plotting 技能规定的统一期刊样式。"""
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
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def style_axis(ax: plt.Axes, nx: int = 5, ny: int = 5) -> None:
    ax.xaxis.set_major_locator(MaxNLocator(nbins=nx))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=ny))
    ax.tick_params(which="major", direction="in", top=True, right=True, length=3.5)
    ax.grid(False)
    ax.set_title("")
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)


def finite_margin(values: np.ndarray, fraction: float = 0.08) -> tuple[float, float]:
    lo = float(np.nanmin(values))
    hi = float(np.nanmax(values))
    span = hi - lo
    if span <= np.finfo(float).eps:
        span = max(abs(lo), 1.0)
    return lo - fraction * span, hi + fraction * span


def save_figure(fig: plt.Figure, stem: str) -> tuple[Path, Path]:
    pdf_path = PDF_DIR / f"{stem}.pdf"
    png_path = PNG_DIR / f"{stem}.png"
    fig.savefig(pdf_path, format="pdf", metadata={"Creator": "第3章可复现绘图入口"})
    fig.savefig(png_path, format="png", dpi=600)
    plt.close(fig)
    return pdf_path, png_path


def load_response(name: str) -> tuple[np.ndarray, np.ndarray]:
    path = DATA_DIR / f"{name}.mat"
    if not path.is_file():
        raise FileNotFoundError(f"缺少真实仿真数据：{path}")
    mat = loadmat(path, squeeze_me=False)
    time = np.asarray(mat["time_s"], dtype=float).reshape(-1)
    response = np.asarray(mat["response_mm"], dtype=float)
    if response.ndim != 3 or response.shape[1:] != (3, 3):
        raise ValueError(f"{path.name} response_mm应为N x 3楼层 x 3方法，实际{response.shape}")
    if time.size != response.shape[0] or not np.all(np.diff(time) > 0):
        raise ValueError(f"{path.name}时间轴与响应不一致或不递增")
    if not np.all(np.isfinite(response)):
        raise ValueError(f"{path.name}包含NaN/Inf")
    return time, response


def plot_methods(ax: plt.Axes, time: np.ndarray, values: np.ndarray, local: bool) -> None:
    # MAT列顺序是Original, Guyan, Craig-Bampton；图例固定为Original, CB, Guyan。
    order = [(0, "Original"), (2, "Craig-Bampton"), (1, "Guyan")]
    n = time.size
    markevery = max(1, n // 14)
    for column, name in order:
        style = STYLES[name]
        kwargs: dict[str, object] = {
            "color": style["color"],
            "linestyle": style["linestyle"],
            "linewidth": 1.2 if local else 0.8,
            "label": name,
            "zorder": 3 if name == "Original" else 2,
        }
        if local:
            kwargs.update(
                marker=style["marker"],
                markevery=markevery,
                markersize=3.5,
                markerfacecolor="white",
                markeredgewidth=0.7,
            )
        ax.plot(time, values[:, column], **kwargs)


def comparison_figure(
    time: np.ndarray,
    response: np.ndarray,
    floor_index: int,
    windows: tuple[tuple[float, float], tuple[float, float]],
    stem: str,
) -> tuple[Path, Path]:
    fig = plt.figure(figsize=(7.48, 5.00), constrained_layout=True)
    grid = GridSpec(2, 2, figure=fig, height_ratios=[1.05, 1.0])
    ax_full = fig.add_subplot(grid[0, :])
    ax_left = fig.add_subplot(grid[1, 0])
    ax_right = fig.add_subplot(grid[1, 1])
    values = response[:, floor_index, :]

    plot_methods(ax_full, time, values, local=False)
    ax_full.set_xlim(0, 40)
    ax_full.set_ylim(*finite_margin(values))
    ax_full.set_xlabel(r"Time (s)")
    ax_full.set_ylabel(r"Displacement (mm)")
    ax_full.legend(loc="upper right", handlelength=2.3, handletextpad=0.5)
    style_axis(ax_full, nx=6, ny=5)
    ax_full.text(0.5, -0.27, r"(a) Full-time response", transform=ax_full.transAxes, ha="center")

    for idx, (ax, window) in enumerate(zip((ax_left, ax_right), windows, strict=True)):
        mask = (time >= window[0]) & (time <= window[1])
        if np.count_nonzero(mask) < 20:
            raise ValueError(f"{stem}局部窗{window}样本不足")
        local_time = time[mask]
        local_values = values[mask, :]
        plot_methods(ax, local_time, local_values, local=True)
        ax.set_xlim(*window)
        ax.set_ylim(*finite_margin(local_values))
        ax.set_xlabel(r"Time (s)")
        ax.set_ylabel(r"Displacement (mm)")
        style_axis(ax, nx=5, ny=5)
        # 三种方法已在顶部全时程图统一说明；局部窗不重复放图例，避免遮挡数据。
    ax_left.text(1.05, -0.31, r"(b) Local responses", transform=ax_left.transAxes, ha="center")
    return save_figure(fig, stem)


def unit_response_figure() -> tuple[Path, Path]:
    time, response = load_response("单位激励_原结构三层响应")
    original = response[:, :, 0]
    fig, ax = plt.subplots(figsize=(7.48, 3.60), constrained_layout=True)
    for floor, style in enumerate(FLOOR_STYLES):
        ax.plot(
            time,
            original[:, floor],
            color=style["color"],
            linestyle=style["linestyle"],
            linewidth=1.0,
            label=style["label"],
        )
    ax.set_xlim(0, 40)
    ax.set_ylim(*finite_margin(original))
    ax.set_xlabel(r"Time (s)")
    ax.set_ylabel(r"Displacement (mm)")
    ax.legend(loc="upper right", handlelength=2.2)
    style_axis(ax, nx=6, ny=5)
    return save_figure(fig, "图3-5_单位激励下的三层响应")


def write_structure_parameters() -> tuple[Path, Path]:
    parameters = {
        "图3-1": {
            "名称": "第一类子结构自由度选取",
            "数值子结构": {"层数": 3, "跨数": 3, "保留水平自由度": [1, 6, 11], "保留转角自由度": [4, 9, 14]},
            "物理子结构": {"层数": 2, "跨数": 1, "保留水平自由度": [1, 6], "全部接口水平自由度": [1, 6]},
            "依据": "梁禹手稿PDF第27页图3-1与untitled2.mlx转存代码",
        },
        "图3-2": {
            "名称": "第二类子结构自由度选取",
            "数值子结构": {"层数": 3, "跨数": 2, "保留水平自由度": [1, 6, 11], "保留转角自由度": [4, 9, 14]},
            "物理子结构": {"层数": 3, "跨数": 1, "保留水平自由度": [1, 11], "全部接口水平自由度": [1, 6, 11], "从自由度": [6]},
            "依据": "梁禹手稿PDF第27页图3-2与untitled.mlx转存代码",
        },
    }
    json_path = DATA_DIR / "图3-1与图3-2_结构自由度参数.json"
    json_path.write_text(json.dumps(parameters, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = DATA_DIR / "图3-1与图3-2_结构自由度参数.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["唯一ID", "结构部分", "层数", "跨数", "保留水平自由度", "保留转角自由度", "依据"])
        for figure_id, item in parameters.items():
            for part in ("数值子结构", "物理子结构"):
                block = item[part]
                writer.writerow(
                    [
                        figure_id,
                        part,
                        block["层数"],
                        block["跨数"],
                        ";".join(map(str, block.get("保留水平自由度", []))),
                        ";".join(map(str, block.get("保留转角自由度", []))),
                        item["依据"],
                    ]
                )
    return json_path, csv_path


def draw_support(ax: plt.Axes, x: float, y: float) -> None:
    tri = Polygon([[x - 0.10, y - 0.22], [x + 0.10, y - 0.22], [x, y]], closed=True, fill=False, lw=0.8)
    ax.add_patch(tri)
    ax.plot([x - 0.14, x + 0.14], [y - 0.24, y - 0.24], color="#333333", lw=0.8)
    for dx in np.linspace(-0.12, 0.10, 6):
        ax.plot([x + dx, x + dx - 0.05], [y - 0.24, y - 0.31], color="#777777", lw=0.5)


def draw_frame(
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
        ax.plot([x, x], [ys[0], ys[-1]], color="#333333", lw=0.8)
        if node_labels[0][column] is not None:
            draw_support(ax, x, ys[0])
    for y in ys[1:]:
        ax.plot([xs[0], xs[-1]], [y, y], color="#333333", lw=0.8)

    for level in range(stories + 1):
        for bay in range(bays + 1):
            node = node_labels[level][bay]
            if node is None:
                continue
            x, y = xs[bay], ys[level]
            # 9 pt双位数节点需要比原稿更大的圆内边距。圆心向左上方错开，
            # 并与结构节点保留小间隙，避免圆周压到梁柱线。
            node_radius = 0.13
            node_center = (x - node_radius - 0.01, y + node_radius + 0.01)
            ax.add_patch(Circle(node_center, node_radius, fill=False, lw=0.65))
            ax.text(*node_center, str(node), ha="center", va="center", fontsize=9)

    for story, bay, label in master_labels:
        x = xs[min(bay, bays)]
        y = ys[min(story, stories)]
        ax.add_patch(Rectangle((x + 0.08, y + 0.04), 0.43, 0.25, fill=False, edgecolor="#EE6677", lw=0.8))
        ax.text(x + 0.295, y + 0.165, rf"$\psi_{{{label}}}$", color="#EE6677", ha="center", va="center", fontsize=9)
        ax.add_patch(FancyArrowPatch((x + 0.02, y), (x + 0.36, y), arrowstyle="-|>", mutation_scale=7, color="#EE6677", lw=0.8))


def draw_plus(ax: plt.Axes, x: float, y: float) -> None:
    """用几何线段绘制组合符号，避免把运算符当作超大字号文字。"""
    half = 0.13
    ax.plot([x - half, x + half], [y, y], color="#333333", lw=1.0, solid_capstyle="butt")
    ax.plot([x, x], [y - half, y + half], color="#333333", lw=1.0, solid_capstyle="butt")


def schematic_figure(kind: int) -> tuple[Path, Path]:
    fig, ax = plt.subplots(figsize=(7.48, 3.50), constrained_layout=True)
    ax.set_aspect("equal")
    if kind == 1:
        draw_frame(
            ax, 0.4, 0.4, 3, 3, 0.85,
            [[None, 3, None, 4], [None, 6, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]],
            [(1,3,"1"),(2,3,"6"),(3,3,"11"),(1,1,"4"),(2,1,"9"),(3,1,"14")],
        )
        draw_plus(ax, 3.55, 1.70)
        draw_frame(ax, 4.15, 0.4, 2, 1, 0.85, [[2, 3], [6, 7], [9, 10]], [(1,1,"1"),(2,1,"6")])
        ax.text(1.70, 3.42, r"Numerical substructure", ha="center")
        ax.text(4.58, 2.57, r"Physical substructure", ha="center")
        stem = "图3-1_第一类子结构自由度选取"
    else:
        draw_frame(
            ax, 0.6, 0.4, 3, 2, 0.85,
            [[None, 3, 4], [6, 7, 8], [10, 11, 12], [14, 15, 16]],
            [(1,2,"1"),(2,2,"6"),(3,2,"11"),(1,1,"4"),(2,1,"9"),(3,1,"14")],
        )
        draw_plus(ax, 3.15, 1.70)
        draw_frame(ax, 3.75, 0.4, 3, 1, 0.85, [[2, 3], [6, 7], [9, 10], [13, 14]], [(1,1,"1"),(3,1,"11")])
        # 第二类物理子结构的 psi6 是接口从自由度：保留显示，但用黑色而非
        # 主自由度红色，避免与 psi1/psi11 混淆。
        x_psi6, y_psi6 = 3.75 + 0.85, 0.4 + 2*0.85
        ax.add_patch(Rectangle((x_psi6 + 0.08, y_psi6 + 0.04), 0.43, 0.25, fill=False, edgecolor="#333333", lw=0.8))
        ax.text(x_psi6 + 0.295, y_psi6 + 0.165, r"$\psi_{6}$", color="#333333", ha="center", va="center", fontsize=9)
        ax.add_patch(FancyArrowPatch((x_psi6 + 0.02, y_psi6), (x_psi6 + 0.36, y_psi6), arrowstyle="-|>", mutation_scale=7, color="#333333", lw=0.8))
        ax.text(1.45, 3.42, r"Numerical substructure", ha="center")
        ax.text(4.18, 3.42, r"Physical substructure", ha="center")
        stem = "图3-2_第二类子结构自由度选取"
    ax.set_xlim(0, 5.65)
    ax.set_ylim(0, 3.72)
    ax.axis("off")
    return save_figure(fig, stem)


def verify_outputs(stems: list[str]) -> Path:
    rows: list[dict[str, object]] = []
    for stem in stems:
        pdf_path = PDF_DIR / f"{stem}.pdf"
        png_path = PNG_DIR / f"{stem}.png"
        if not pdf_path.is_file() or pdf_path.stat().st_size < 1_000:
            raise RuntimeError(f"PDF缺失或过小：{pdf_path}")
        if not png_path.is_file() or png_path.stat().st_size < 10_000:
            raise RuntimeError(f"PNG缺失或过小：{png_path}")
        with Image.open(png_path) as image:
            dpi = image.info.get("dpi", (0, 0))
            width, height = image.size
            if min(dpi) < 590:
                raise RuntimeError(f"{png_path.name} DPI不足：{dpi}")
        rows.append(
            {
                "唯一ID": stem.split("_")[0].replace("图", ""),
                "PDF字节": pdf_path.stat().st_size,
                "PNG字节": png_path.stat().st_size,
                "PNG宽_px": width,
                "PNG高_px": height,
                "PNG_DPI_x": round(float(dpi[0]), 2),
                "PNG_DPI_y": round(float(dpi[1]), 2),
                "无NaN_Inf": "PASS",
                "字体与样式": "Computer Modern 9pt; Tol Bright; inward ticks; no title/grid",
                "状态": "PASS",
            }
        )
    path = VERIFY_DIR / "第3章全部图片文件与样式验证.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def file_sha256(path: Path) -> str:
    """流式计算文件 SHA-256，避免将大图一次性读入内存。"""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def response_specifications() -> dict[str, tuple[str, int, tuple[tuple[float, float], tuple[float, float]], str]]:
    """返回唯一ID到真实数据、楼层、局部窗和中文输出名的固定映射。"""
    earthquake_windows = ((10.0, 11.0), (21.5, 22.5))
    chirp_windows = ((13.0, 14.0), (38.0, 38.3))
    return {
        "3-6": ("第一类划分_ElCentro地震响应", 0, earthquake_windows, "图3-6_第一类划分地震激励下一层水平位移"),
        "3-7": ("第一类划分_ElCentro地震响应", 1, earthquake_windows, "图3-7_第一类划分地震激励下二层水平位移"),
        "3-8": ("第一类划分_ElCentro地震响应", 2, earthquake_windows, "图3-8_第一类划分地震激励下三层水平位移"),
        "3-9": ("第二类划分_ElCentro地震响应", 0, earthquake_windows, "图3-9_第二类划分地震激励下一层水平位移"),
        "3-10": ("第二类划分_ElCentro地震响应", 2, earthquake_windows, "图3-10_第二类划分地震激励下三层水平位移"),
        "3-11": ("第一类划分_Chirp响应", 0, chirp_windows, "图3-11_第一类划分Chirp信号下一层水平位移"),
        "3-12": ("第一类划分_Chirp响应", 1, chirp_windows, "图3-12_第一类划分Chirp信号下二层水平位移"),
        "3-13": ("第一类划分_Chirp响应", 2, chirp_windows, "图3-13_第一类划分Chirp信号下三层水平位移"),
        "3-14": ("第二类划分_Chirp响应", 0, chirp_windows, "图3-14_第二类划分Chirp信号下一层水平位移"),
        "3-15": ("第二类划分_Chirp响应", 2, chirp_windows, "图3-15_第二类划分Chirp信号下三层水平位移"),
    }


def all_figure_stems() -> dict[str, str]:
    """返回交付顺序固定的13个唯一ID与中文输出名。"""
    result = {
        "3-1": "图3-1_第一类子结构自由度选取",
        "3-2": "图3-2_第二类子结构自由度选取",
        "3-5": "图3-5_单位激励下的三层响应",
    }
    result.update({uid: specification[3] for uid, specification in response_specifications().items()})
    return result


def 刷新最终图片哈希() -> Path:
    """在每次总图或单图重绘后重建26项最终图片哈希清单。"""
    rows: list[dict[str, object]] = []
    for uid, stem in all_figure_stems().items():
        for fmt, folder, suffix in (("PDF", PDF_DIR, ".pdf"), ("PNG", PNG_DIR, ".png")):
            path = folder / f"{stem}{suffix}"
            if not path.is_file():
                raise RuntimeError(f"刷新图片哈希时发现产物缺失：{path}")
            rows.append(
                {
                    "唯一ID": uid,
                    "格式": fmt,
                    "相对章节路径": path.relative_to(CHAPTER_DIR).as_posix(),
                    "SHA256": file_sha256(path),
                    "字节数": path.stat().st_size,
                }
            )
    if len(rows) != 26:
        raise RuntimeError(f"图片哈希清单应有26项，实际{len(rows)}项")
    path = VERIFY_DIR / "第3章最终图片_SHA256.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def 绘制指定图片(唯一ID: str) -> tuple[Path, Path]:
    """只重绘一个唯一ID对应的PDF和PNG，不改动其他图片。"""
    setup_style()
    uid = 唯一ID.removeprefix("图")
    if uid == "3-1":
        return schematic_figure(1)
    if uid == "3-2":
        return schematic_figure(2)
    if uid == "3-5":
        return unit_response_figure()
    specifications = response_specifications()
    if uid not in specifications:
        raise ValueError(f"未知图片唯一ID：{唯一ID}")
    data_name, floor_index, windows, stem = specifications[uid]
    time, response = load_response(data_name)
    return comparison_figure(time, response, floor_index, windows, stem)


def main() -> int:
    setup_style()
    write_structure_parameters()
    stems: list[str] = []

    for uid in ("3-1", "3-2", "3-5"):
        pdf, _ = 绘制指定图片(uid)
        stems.append(pdf.stem)

    specifications = response_specifications()
    cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    for uid, (data_name, floor_index, windows, stem) in specifications.items():
        if data_name not in cache:
            cache[data_name] = load_response(data_name)
        time, response = cache[data_name]
        pdf, _ = comparison_figure(time, response, floor_index, windows, stem)
        stems.append(pdf.stem)

    if len(stems) != 13 or len(set(stems)) != 13:
        raise RuntimeError(f"应生成13个唯一图片ID，实际{len(stems)}")
    verification = verify_outputs(stems)
    hash_manifest = 刷新最终图片哈希()
    print(f"已生成13张PDF和13张600 dpi PNG。验证记录：{verification}")
    print(f"已刷新26项最终图片SHA-256：{hash_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

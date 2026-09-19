#!/usr/bin/env python
"""从梁禹硕士论文 PDF 的矢量折线逐点重建图 4-4 与图 4-5。

证据边界：本脚本只做论文矢量边界的绘图级复刻，不执行稳定性计算。
CSV 中的 tau1_step/tau2_step 是论文坐标轴上的采样步数，不是毫秒。
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import fitz
import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt


DEFAULT_SOURCE = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\梁禹手稿.pdf")
SOURCE_SHA256 = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
PAGE_INDEX = 69  # 物理页 70，PyMuPDF 从 0 开始计数


@dataclass(frozen=True)
class CurveSpec:
    figure_id: str
    method: str
    drawing_index: int
    expected_points: int
    expected_rightmost: int
    expected_rightmost_tau2: tuple[int, ...]
    csv_name: str


CURVES = (
    CurveSpec("4-4", "Original", 19, 72, 64, (2,), "图4-4_Original_论文矢量边界.csv"),
    CurveSpec("4-4", "CB", 92, 69, 59, (2, 3, 4, 5), "图4-4_CB_论文矢量边界.csv"),
    CurveSpec("4-4", "Guyan", 162, 67, 58, (2, 3), "图4-4_Guyan_论文矢量边界.csv"),
    CurveSpec("4-5", "Original", 260, 69, 57, (2, 3, 4), "图4-5_Original_论文矢量边界.csv"),
    CurveSpec("4-5", "CB", 330, 56, 51, (2, 3), "图4-5_CB_论文矢量边界.csv"),
    CurveSpec("4-5", "Guyan", 387, 53, 48, (2, 3), "图4-5_Guyan_论文矢量边界.csv"),
)


PLOT_SPECS = {
    "4-4": {
        "pdf": "图4-4_第一类子结构划分稳定域_论文矢量边界逐点复刻.pdf",
        "png": "图4-4_第一类子结构划分稳定域_论文矢量边界逐点复刻.png",
        "xlim": (1.5, 64.75),
        "ylim": (1.5, 31.5),
        "xticks": list(range(10, 61, 10)),
        "yticks": list(range(5, 31, 5)),
    },
    "4-5": {
        "pdf": "图4-5_第二类子结构划分稳定域_论文矢量边界逐点复刻.pdf",
        "png": "图4-5_第二类子结构划分稳定域_论文矢量边界逐点复刻.png",
        "xlim": (1.5, 57.75),
        "ylim": (1.5, 28.5),
        "xticks": list(range(5, 56, 5)),
        "yticks": list(range(5, 26, 5)),
    },
}


STYLES = {
    "Original": {"label": "Original", "color": "#0000FF", "marker": "o"},
    "CB": {"label": "CB", "color": "#FF0000", "marker": "s"},
    "Guyan": {"label": "Guyan", "color": "#00CC00", "marker": "^"},
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def output_root_from_script() -> Path:
    return Path(__file__).resolve().parent.parent


def extract_curve(page: fitz.Page, spec: CurveSpec) -> list[dict[str, int | float]]:
    drawings = page.get_drawings()
    if spec.drawing_index >= len(drawings):
        raise RuntimeError(f"绘图对象 {spec.drawing_index} 不存在；PDF 版次可能变化。")
    drawing = drawings[spec.drawing_index]
    items = drawing["items"]
    if not items or any(item[0] != "l" for item in items):
        raise RuntimeError(f"绘图对象 {spec.drawing_index} 不是连续直线折线。")

    points = [items[0][1], *[item[2] for item in items]]
    # 论文矢量坐标存在 0.12 pt 量化抖动。每条边界覆盖从 2 开始的连续
    # 整数网格，因此按唯一坐标的秩恢复采样步，避免手抄和拟合误差。
    x_levels = sorted({round(point.x, 2) for point in points})
    y_levels_desc = sorted({round(point.y, 2) for point in points}, reverse=True)
    x_rank = {value: rank + 2 for rank, value in enumerate(x_levels)}
    y_rank = {value: rank + 2 for rank, value in enumerate(y_levels_desc)}

    rows: list[dict[str, int | float]] = []
    for order, point in enumerate(points, start=1):
        px = round(point.x, 2)
        py = round(point.y, 2)
        rows.append(
            {
                "point_order": order,
                "tau1_step": x_rank[px],
                "tau2_step": y_rank[py],
                "pdf_x_pt": px,
                "pdf_y_pt": py,
                "pdf_page_physical": PAGE_INDEX + 1,
                "pdf_drawing_index": spec.drawing_index,
            }
        )
    return rows


def check_expected(spec: CurveSpec, rows: list[dict[str, int | float]]) -> None:
    rightmost = max(int(row["tau1_step"]) for row in rows)
    right_tau2 = tuple(
        sorted(int(row["tau2_step"]) for row in rows if int(row["tau1_step"]) == rightmost)
    )
    if len(rows) != spec.expected_points:
        raise RuntimeError(f"{spec.figure_id} {spec.method}: 点数 {len(rows)} != {spec.expected_points}")
    if rightmost != spec.expected_rightmost:
        raise RuntimeError(
            f"{spec.figure_id} {spec.method}: 最右列 {rightmost} != {spec.expected_rightmost}"
        )
    if right_tau2 != spec.expected_rightmost_tau2:
        raise RuntimeError(
            f"{spec.figure_id} {spec.method}: 最右列纵坐标 {right_tau2} != {spec.expected_rightmost_tau2}"
        )


def write_csv(path: Path, rows: list[dict[str, int | float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def configure_matplotlib() -> None:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "DejaVu Sans"],
            "font.size": 9,
            "axes.labelsize": 10,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "axes.linewidth": 0.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": False,
            "ytick.right": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 600,
        }
    )


def plot_figure(figure_id: str, rows_by_method: dict[str, list[dict[str, int | float]]], output: Path) -> None:
    spec = PLOT_SPECS[figure_id]
    fig, ax = plt.subplots(figsize=(5.55, 3.75), constrained_layout=True)
    for method in ("Original", "CB", "Guyan"):
        rows = rows_by_method[method]
        style = STYLES[method]
        ax.plot(
            [int(row["tau1_step"]) for row in rows],
            [int(row["tau2_step"]) for row in rows],
            color=style["color"],
            linestyle="-",
            linewidth=1.0,
            marker=style["marker"],
            markersize=5.0,
            markerfacecolor="none",
            markeredgewidth=1.0,
            label=style["label"],
            clip_on=False,
        )
    ax.set_xlim(*spec["xlim"])
    ax.set_ylim(*spec["ylim"])
    ax.set_xticks(spec["xticks"])
    ax.set_yticks(spec["yticks"])
    ax.set_xlabel(r"$\tau 1$")
    ax.set_ylabel(r"$\tau 2$")
    ax.text(0.5, 1.025, "稳定域", transform=ax.transAxes, ha="center", va="bottom", fontsize=10)
    ax.grid(True, color="#B0B0B0", linewidth=0.5, alpha=0.45)
    ax.legend(
        loc="upper right",
        frameon=True,
        fancybox=False,
        framealpha=1.0,
        edgecolor="#333333",
        handlelength=2.2,
        handletextpad=0.5,
    )
    figure_dir = output / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fixed_pdf_metadata = {
        "Creator": "rebuild_thesis_vector_trace.py",
        "Producer": "Matplotlib",
        "CreationDate": dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc),
        "ModDate": dt.datetime(2026, 8, 27, tzinfo=dt.timezone.utc),
        "Title": f"Figure {figure_id} thesis vector boundary trace",
    }
    fig.savefig(figure_dir / spec["pdf"], format="pdf", metadata=fixed_pdf_metadata)
    fig.savefig(figure_dir / spec["png"], format="png", dpi=600)
    plt.close(fig)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--output-root", type=Path, default=output_root_from_script())
    args = parser.parse_args()
    source = args.source.resolve()
    output = args.output_root.resolve()

    if sha256(source) != SOURCE_SHA256:
        raise RuntimeError("论文 PDF 的 SHA-256 与已审计版不一致，停止提取。")
    document = fitz.open(source)
    if len(document) <= PAGE_INDEX:
        raise RuntimeError("论文 PDF 不包含物理页 70。")
    page = document[PAGE_INDEX]

    configure_matplotlib()
    all_rows: dict[str, dict[str, list[dict[str, int | float]]]] = {"4-4": {}, "4-5": {}}
    extraction_summary = []
    for curve in CURVES:
        rows = extract_curve(page, curve)
        check_expected(curve, rows)
        write_csv(output / "data" / curve.csv_name, rows)
        all_rows[curve.figure_id][curve.method] = rows
        extraction_summary.append(
            {
                "figure": curve.figure_id,
                "method": curve.method,
                "drawing_index": curve.drawing_index,
                "point_count": len(rows),
                "rightmost_tau1_step": curve.expected_rightmost,
                "rightmost_tau2_steps": list(curve.expected_rightmost_tau2),
            }
        )

    plot_figure("4-4", all_rows["4-4"], output)
    plot_figure("4-5", all_rows["4-5"], output)
    metadata = {
        "status": "PLOT_LEVEL_TRACE_ONLY_NOT_CALCULATION_REPRODUCTION",
        "source_pdf": str(source),
        "source_sha256": SOURCE_SHA256,
        "source_page_physical": PAGE_INDEX + 1,
        "coordinate_unit": "sample_step",
        "sample_period_seconds": "1/1024",
        "curves": extraction_summary,
    }
    validation_dir = output / "validation"
    validation_dir.mkdir(parents=True, exist_ok=True)
    (validation_dir / "提取元数据.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

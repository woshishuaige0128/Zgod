#!/usr/bin/env python
"""用梁禹硕士论文的六条有序矢量边界生成小论文 Fig. 10。

证据边界：本脚本只重画已从论文 PDF 提取并逐点验收的路径，
不重新求解闭环极点或谱半径网格。
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
from pathlib import Path

os.environ.setdefault("SOURCE_DATE_EPOCH", "1787788800")

import matplotlib as mpl

mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator


ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "01_论文矢量边界主数据"
PDF_DIR = ROOT / "02_小论文Fig10最终图" / "PDF"
PNG_DIR = ROOT / "02_小论文Fig10最终图" / "PNG"
VALIDATION_DIR = ROOT / "08_总验收与论文映射"
DT_SECONDS = 1.0 / 1024.0

CURVES = (
    ("4-4", "Original", "图4-4_Original_论文矢量边界.csv"),
    ("4-4", "Craig-Bampton", "图4-4_CB_论文矢量边界.csv"),
    ("4-4", "Guyan", "图4-4_Guyan_论文矢量边界.csv"),
    ("4-5", "Original", "图4-5_Original_论文矢量边界.csv"),
    ("4-5", "Craig-Bampton", "图4-5_CB_论文矢量边界.csv"),
    ("4-5", "Guyan", "图4-5_Guyan_论文矢量边界.csv"),
)

STYLES = {
    "Original": {
        "color": "#555555",
        "linestyle": "--",
        "marker": "o",
        "zorder": 4,
    },
    "Craig-Bampton": {
        "color": "#EE6677",
        "linestyle": "-",
        "marker": "s",
        "zorder": 3,
    },
    "Guyan": {
        "color": "#4477AA",
        "linestyle": "-.",
        "marker": "^",
        "zorder": 2,
    },
}


def configure_style() -> None:
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
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def read_curve(path: Path) -> list[dict[str, int | float]]:
    rows: list[dict[str, int | float]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for raw in csv.DictReader(handle):
            rows.append(
                {
                    "point_order": int(raw["point_order"]),
                    "tau1_step": int(raw["tau1_step"]),
                    "tau2_step": int(raw["tau2_step"]),
                    "pdf_x_pt": float(raw["pdf_x_pt"]),
                    "pdf_y_pt": float(raw["pdf_y_pt"]),
                    "pdf_page_physical": int(raw["pdf_page_physical"]),
                    "pdf_drawing_index": int(raw["pdf_drawing_index"]),
                }
            )
    expected_order = list(range(1, len(rows) + 1))
    actual_order = [int(row["point_order"]) for row in rows]
    if actual_order != expected_order:
        raise ValueError(f"{path.name} 的 point_order 不连续或已被重排。")
    return rows


def step_to_ms(step: int) -> float:
    return (step - 1) * 1000.0 * DT_SECONDS


def configure_axis(ax: mpl.axes.Axes) -> None:
    ax.set_title("")
    ax.grid(False)
    ax.tick_params(
        which="major",
        direction="in",
        top=True,
        right=True,
        width=0.8,
        length=3.5,
    )
    ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)


def write_combined_csv(datasets: dict[tuple[str, str], list[dict[str, int | float]]]) -> Path:
    destination = DATA_DIR / "Fig10_六条论文边界_采样步与毫秒.csv"
    fields = [
        "figure",
        "method",
        "point_order",
        "tau1_step",
        "tau2_step",
        "tau1_ms",
        "tau2_ms",
        "pdf_x_pt",
        "pdf_y_pt",
        "pdf_page_physical",
        "pdf_drawing_index",
    ]
    with destination.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for figure_id, method, _ in CURVES:
            for row in datasets[(figure_id, method)]:
                writer.writerow(
                    {
                        "figure": figure_id,
                        "method": method,
                        "point_order": row["point_order"],
                        "tau1_step": row["tau1_step"],
                        "tau2_step": row["tau2_step"],
                        "tau1_ms": f"{step_to_ms(int(row['tau1_step'])):.12f}",
                        "tau2_ms": f"{step_to_ms(int(row['tau2_step'])):.12f}",
                        "pdf_x_pt": f"{float(row['pdf_x_pt']):.2f}",
                        "pdf_y_pt": f"{float(row['pdf_y_pt']):.2f}",
                        "pdf_page_physical": row["pdf_page_physical"],
                        "pdf_drawing_index": row["pdf_drawing_index"],
                    }
                )
    return destination


def main() -> int:
    configure_style()
    PDF_DIR.mkdir(parents=True, exist_ok=True)
    PNG_DIR.mkdir(parents=True, exist_ok=True)
    VALIDATION_DIR.mkdir(parents=True, exist_ok=True)

    datasets: dict[tuple[str, str], list[dict[str, int | float]]] = {}
    for figure_id, method, filename in CURVES:
        datasets[(figure_id, method)] = read_curve(DATA_DIR / filename)
    combined_csv = write_combined_csv(datasets)

    ymax = max(
        step_to_ms(int(row["tau2_step"]))
        for rows in datasets.values()
        for row in rows
    ) * 1.10

    fig, axes = plt.subplots(1, 2, figsize=(6.30, 2.72), sharey=True)
    legend_handles = None
    legend_labels = None
    for panel_index, (ax, figure_id, panel_label) in enumerate(
        zip(axes, ("4-4", "4-5"), ("(a)", "(b)"), strict=True)
    ):
        xmax = 0.0
        for method in ("Original", "Craig-Bampton", "Guyan"):
            rows = datasets[(figure_id, method)]
            x = [step_to_ms(int(row["tau1_step"])) for row in rows]
            y = [step_to_ms(int(row["tau2_step"])) for row in rows]
            xmax = max(xmax, max(x))
            style = STYLES[method]
            ax.plot(
                x,
                y,
                color=style["color"],
                linestyle=style["linestyle"],
                marker=style["marker"],
                markerfacecolor="white",
                markeredgewidth=0.8,
                markevery=max(1, len(x) // 8),
                linewidth=1.2,
                zorder=style["zorder"],
                label=method,
            )
        ax.set_xlim(0.0, xmax * 1.08)
        ax.set_ylim(0.0, ymax)
        ax.set_xlabel(r"Delay $\tau_1$ (ms)")
        if panel_index == 0:
            ax.set_ylabel(r"Delay $\tau_2$ (ms)")
            legend_handles, legend_labels = ax.get_legend_handles_labels()
        configure_axis(ax)
        ax.text(
            0.02,
            1.02,
            panel_label,
            transform=ax.transAxes,
            va="bottom",
            ha="left",
            fontsize=9,
            fontweight="bold",
            clip_on=False,
        )

    if legend_handles is None or legend_labels is None:
        raise RuntimeError("未获得图例。")
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

    pdf_path = PDF_DIR / "fig10_stability_domain.pdf"
    png_path = PNG_DIR / "fig10_stability_domain.png"
    fixed_time = dt.datetime(2026, 8, 27, 0, 0, 0, tzinfo=dt.timezone.utc)
    pdf_metadata = {
        "Title": "Small-paper Fig. 10: thesis-vector stability domains",
        "Author": "Reproduction package",
        "Subject": "PLOT_LEVEL_VECTOR_TRACE_ONLY",
        "Keywords": "Fig10, stability domain, vector trace",
        "Creator": "02_生成小论文Fig10.py",
        "Producer": "Matplotlib",
        "CreationDate": fixed_time,
        "ModDate": fixed_time,
    }
    fig.savefig(
        pdf_path,
        format="pdf",
        bbox_inches="tight",
        pad_inches=0.02,
        facecolor="white",
        metadata=pdf_metadata,
    )
    fig.savefig(
        png_path,
        format="png",
        dpi=600,
        bbox_inches="tight",
        pad_inches=0.02,
        facecolor="white",
        metadata={
            "Software": "02_生成小论文Fig10.py",
            "Creation Time": "2026-08-27T00:00:00+08:00",
        },
    )
    plt.close(fig)

    metadata = {
        "status": "PASS",
        "evidence_level": "PLOT_LEVEL_VECTOR_TRACE_ONLY",
        "calculation_reproduction": False,
        "point_count": sum(len(rows) for rows in datasets.values()),
        "sampling_period_seconds": DT_SECONDS,
        "conversion": "tau_ms=(tau_step-1)*1000/1024",
        "preserve_point_order": True,
        "drawstyle": "default ordered polyline",
        "styles": STYLES,
        "figure_size_inches": [6.30, 2.72],
        "pdf": str(pdf_path.relative_to(ROOT)),
        "png": str(png_path.relative_to(ROOT)),
        "combined_csv": str(combined_csv.relative_to(ROOT)),
    }
    (VALIDATION_DIR / "Fig10生成元数据.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    for path in (pdf_path, png_path, combined_csv):
        if not path.is_file() or path.stat().st_size == 0:
            raise RuntimeError(f"输出失败：{path}")
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# -*- coding: utf-8 -*-
"""绘制板块16频率与模态参与度证据图。"""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


SCRIPT_PATH = Path(__file__).resolve()
BASE_DIR = SCRIPT_PATH.parents[1]
OUTPUT_DIR = BASE_DIR / "outputs"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 8.5,
            "axes.labelsize": 9,
            "axes.titlesize": 9,
            "legend.fontsize": 7.5,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.4,
            "lines.markersize": 4.5,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def main() -> int:
    frequency_rows = read_csv(OUTPUT_DIR / "frequency_comparison_thesis_vs_code.csv")
    modal_rows = read_csv(OUTPUT_DIR / "modal_results_python.csv")
    if len(frequency_rows) != 5 or len(modal_rows) != 15:
        raise ValueError("输入行数不符合五阶频率/15阶模态契约")

    mode5 = np.array([int(row["mode"]) for row in frequency_rows])
    thesis = np.array([float(row["thesis_frequency_hz"]) for row in frequency_rows])
    current = np.array([float(row["response_code_frequency_hz"]) for row in frequency_rows])
    relative = np.array([float(row["relative_difference_percent"]) for row in frequency_rows])

    modes = np.array([int(row["mode"]) for row in modal_rows])
    ratios = 100.0 * np.array([float(row["effective_mass_ratio_horizontal"]) for row in modal_rows])
    cumulative = 100.0 * np.array([float(row["cumulative_horizontal"]) for row in modal_rows])

    configure_style()
    blue = "#4477AA"
    red = "#EE6677"
    gray = "#555555"
    grid = "#D9D9D9"

    fig, (ax_frequency, ax_participation) = plt.subplots(
        1,
        2,
        figsize=(180 / 25.4, 84 / 25.4),
        gridspec_kw={"width_ratios": [1.0, 1.25]},
        constrained_layout=True,
    )

    ax_frequency.plot(
        mode5,
        thesis,
        color=gray,
        linestyle="--",
        marker="o",
        markerfacecolor="white",
        label="硕士论文历史值",
    )
    ax_frequency.plot(
        mode5,
        current,
        color=blue,
        linestyle="-",
        marker="s",
        label="冻结代码复算值",
    )
    for x_value, y_value, difference in zip(mode5, current, relative):
        ax_frequency.annotate(
            f"+{difference:.2f}%",
            (x_value, y_value),
            xytext=(0, 7),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=6.8,
            color=blue,
        )
    ax_frequency.set_xlabel("模态阶次")
    ax_frequency.set_ylabel("频率 (Hz)")
    ax_frequency.set_xticks(mode5)
    ax_frequency.set_ylim(0, max(current) * 1.18)
    ax_frequency.set_title("（a）论文频率未被冻结代码精确生成", loc="left")
    ax_frequency.grid(axis="y", color=grid, linewidth=0.6, linestyle=":")
    ax_frequency.legend(frameon=False, loc="upper left")

    ax_participation.bar(
        modes,
        ratios,
        width=0.72,
        color=blue,
        edgecolor="white",
        linewidth=0.4,
        label="逐阶有效模态质量",
    )
    ax_participation.set_xlabel("模态阶次")
    ax_participation.set_ylabel("逐阶占比 (%)", color=blue)
    ax_participation.tick_params(axis="y", colors=blue)
    ax_participation.set_xticks(modes)
    ax_participation.set_ylim(0, max(ratios) * 1.13)
    ax_participation.grid(axis="y", color=grid, linewidth=0.6, linestyle=":")

    cumulative_axis = ax_participation.twinx()
    cumulative_axis.plot(
        modes,
        cumulative,
        color=red,
        marker="o",
        markersize=3.2,
        label="累计有效模态质量",
    )
    cumulative_axis.axhline(90.0, color=gray, linestyle="--", linewidth=0.9, label="90% 论文阈值")
    cumulative_axis.axvline(5.5, color=gray, linestyle=":", linewidth=0.8)
    cumulative_axis.set_ylabel("累计占比 (%)", color=red)
    cumulative_axis.tick_params(axis="y", colors=red)
    cumulative_axis.set_ylim(0, 104)
    cumulative_axis.annotate(
        f"前5阶 {cumulative[4]:.2f}%",
        (5, cumulative[4]),
        xytext=(12, -14),
        textcoords="offset points",
        color=red,
        fontsize=7.2,
        arrowprops={"arrowstyle": "-", "color": red, "linewidth": 0.7},
    )
    ax_participation.set_title("（b）作者 MLX 主路线的水平方向参与度", loc="left")

    handles_left, labels_left = ax_participation.get_legend_handles_labels()
    handles_right, labels_right = cumulative_axis.get_legend_handles_labels()
    ax_participation.legend(
        handles_left + handles_right,
        labels_left + labels_right,
        frameon=False,
        loc="center right",
        bbox_to_anchor=(1.0, 0.52),
    )

    pdf_path = OUTPUT_DIR / "板块16_频率与模态参与度证据图.pdf"
    png_path = OUTPUT_DIR / "板块16_频率与模态参与度证据图.png"
    fig.savefig(pdf_path, bbox_inches="tight")
    fig.savefig(png_path, dpi=600, bbox_inches="tight")
    plt.close(fig)

    if pdf_path.stat().st_size < 10_000 or png_path.stat().st_size < 50_000:
        raise RuntimeError("证据图文件过小，可能导出失败")
    print(f"PDF={pdf_path}")
    print(f"PNG={png_path}")
    print(f"前5阶累计有效模态质量={cumulative[4]:.12f}%")
    print(f"频率最大相对差={relative.max():.12f}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

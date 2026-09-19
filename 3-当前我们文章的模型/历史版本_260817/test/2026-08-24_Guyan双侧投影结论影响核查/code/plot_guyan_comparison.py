from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


TEST_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = TEST_ROOT / "outputs" / "responses"
FIGURE_ROOT = TEST_ROOT / "figures"

ROUTES = {
    "legacy": OUTPUT_ROOT / "historical_single_sided",
    "projected": OUTPUT_ROOT / "projected_congruence",
}

CASES = (
    (1, "ElCentro", "第一类划分_ElCentro地震响应.csv"),
    (1, "Chirp", "第一类划分_Chirp响应.csv"),
    (2, "ElCentro", "第二类划分_ElCentro地震响应.csv"),
    (2, "Chirp", "第二类划分_Chirp响应.csv"),
)

TIME_COLUMN = "时间_s"
FULL_COLUMNS = ["原结构_一层_mm", "原结构_二层_mm", "原结构_三层_mm"]
GUYAN_COLUMNS = ["Guyan_一层_mm", "Guyan_二层_mm", "Guyan_三层_mm"]
CB_COLUMNS = [
    "CraigBampton_一层_mm",
    "CraigBampton_二层_mm",
    "CraigBampton_三层_mm",
]

METHOD_STYLE = {
    "Full-order": {"color": "#3A3A3A", "linestyle": "--", "linewidth": 1.15},
    "Historical Guyan": {
        "color": "#0072B2",
        "linestyle": "-.",
        "linewidth": 1.00,
    },
    "Standard Guyan": {
        "color": "#009E73",
        "linestyle": "-",
        "linewidth": 1.05,
    },
    "Craig--Bampton": {
        "color": "#C44E52",
        "linestyle": ":",
        "linewidth": 1.15,
    },
}


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "font.size": 9,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "axes.linewidth": 0.8,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "savefig.transparent": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_case(filename: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    legacy_path = ROUTES["legacy"] / filename
    projected_path = ROUTES["projected"] / filename
    if not legacy_path.is_file() or not projected_path.is_file():
        raise FileNotFoundError(f"Missing response pair for {filename}")

    legacy = pd.read_csv(legacy_path)
    projected = pd.read_csv(projected_path)
    expected = [TIME_COLUMN]
    for floor in range(3):
        expected.extend([FULL_COLUMNS[floor], GUYAN_COLUMNS[floor], CB_COLUMNS[floor]])
    if list(legacy.columns) != expected or list(projected.columns) != expected:
        raise ValueError(f"Unexpected response schema for {filename}")
    if len(legacy) != 40961 or len(projected) != 40961:
        raise ValueError(f"Unexpected sample count for {filename}")

    for column in [TIME_COLUMN, *FULL_COLUMNS, *CB_COLUMNS]:
        difference = np.max(
            np.abs(legacy[column].to_numpy() - projected[column].to_numpy())
        )
        if difference != 0.0:
            raise ValueError(
                f"Route-invariant column changed in {filename}: {column}, {difference}"
            )
    return legacy, projected


def plot_case(division: int, excitation: str, filename: str) -> None:
    legacy, projected = load_case(filename)
    time = legacy[TIME_COLUMN].to_numpy()

    fig, axes = plt.subplots(3, 1, figsize=(7.2, 6.4), sharex=True)
    for floor, axis in enumerate(axes):
        curves = {
            "Full-order": legacy[FULL_COLUMNS[floor]].to_numpy(),
            "Historical Guyan": legacy[GUYAN_COLUMNS[floor]].to_numpy(),
            "Standard Guyan": projected[GUYAN_COLUMNS[floor]].to_numpy(),
            "Craig--Bampton": legacy[CB_COLUMNS[floor]].to_numpy(),
        }
        for label, values in curves.items():
            axis.plot(time, values, label=label, **METHOD_STYLE[label])
        axis.set_ylabel("Displacement (mm)")
        axis.text(
            0.012,
            0.94,
            f"({chr(ord('a') + floor)}) Floor {floor + 1}",
            transform=axis.transAxes,
            ha="left",
            va="top",
        )
        axis.set_xlim(0.0, 40.0)
        axis.grid(False)
        axis.minorticks_on()
        axis.tick_params(which="major", length=4.0, width=0.8)
        axis.tick_params(which="minor", length=2.0, width=0.6)

    axes[0].legend(
        loc="upper center",
        bbox_to_anchor=(0.5, 1.20),
        ncol=4,
        frameon=False,
        columnspacing=1.1,
        handlelength=2.6,
    )
    axes[-1].set_xlabel("Time (s)")
    fig.align_ylabels(axes)
    fig.subplots_adjust(left=0.11, right=0.985, bottom=0.085, top=0.92, hspace=0.12)

    stem = f"division{division}_{excitation.lower()}_four_method_three_floor"
    pdf_path = FIGURE_ROOT / f"{stem}.pdf"
    png_path = FIGURE_ROOT / f"{stem}.png"
    fig.savefig(pdf_path, format="pdf", bbox_inches="tight")
    fig.savefig(png_path, format="png", dpi=600, bbox_inches="tight")
    plt.close(fig)
    print(f"saved {pdf_path.name} and {png_path.name}")


def main() -> None:
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    configure_style()
    for division, excitation, filename in CASES:
        plot_case(division, excitation, filename)


if __name__ == "__main__":
    main()

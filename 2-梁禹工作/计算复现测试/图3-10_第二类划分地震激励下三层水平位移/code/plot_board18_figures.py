#!/usr/bin/env python
"""Generate the Board 18 figure candidates from the fresh adapted rerun only.

Authorized numerical inputs
---------------------------
1. ``outputs/adapted_run1/输入数据``: exactly five response MAT files.
2. ``outputs/comparisons/response_column_comparisons.csv``: the independent
   numerical comparison gate.

The script never reads an old figure, an old plotting CSV, or the thesis image
as numerical data.  It writes only below ``outputs/figure_candidates`` and
deliberately refuses to overwrite an existing candidate root.

Figure 3-15 has two explicit products:

* ``paper_historical_composite`` keeps the thesis composition: the full panel
  is the Division-II chirp response, while both zoom panels are the Division-II
  El Centro Floor-3 windows used by Figure 3-10.
* ``physically_consistent_corrected`` uses the Division-II chirp response for
  the full panel and both chirp zoom windows.

Run from any working directory with the project Python executable, for example:

    D:/Software/python/python.exe plot_board18_figures.py
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import matplotlib as mpl

mpl.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.gridspec import GridSpec
from matplotlib.ticker import MaxNLocator
from scipy.io import loadmat


BOARD = Path(__file__).resolve().parents[1]
INPUT_ROOT = BOARD / "outputs" / "adapted_run1" / "输入数据"
COMPARISON_CSV = BOARD / "outputs" / "comparisons" / "response_column_comparisons.csv"
OUTPUT_ROOT = BOARD / "outputs" / "figure_candidates"

EXPECTED_SAMPLE_COUNT = 40 * 1024 + 1
EXPECTED_DT_S = 1.0 / 1024.0
EXPECTED_TIME_S = np.arange(EXPECTED_SAMPLE_COUNT, dtype=np.float64) * EXPECTED_DT_S
MAT_METHOD_ORDER = ("Original", "Guyan", "Craig-Bampton")
MAT_FLOOR_ORDER = ("Floor 1", "Floor 2", "Floor 3")
PLOTTING_METHOD_ORDER = ("Original", "Craig-Bampton", "Guyan")

DATASET_FILES = {
    "unit": "单位激励_原结构三层响应.mat",
    "division1_elcentro": "第一类划分_ElCentro地震响应.mat",
    "division2_elcentro": "第二类划分_ElCentro地震响应.mat",
    "division1_chirp": "第一类划分_Chirp响应.mat",
    "division2_chirp": "第二类划分_Chirp响应.mat",
}

EXPECTED_COMPARISONS = (
    "adapted_run1_vs_run2",
    "adapted_run1_vs_2026_plotting_baseline",
    "independent_rk4_vs_adapted_run1",
)

# The plotting order differs from the stored tensor axis and is intentional.
METHOD_INDEX = {name: index for index, name in enumerate(MAT_METHOD_ORDER)}
FLOOR_INDEX = {name: index for index, name in enumerate(MAT_FLOOR_ORDER)}

METHOD_STYLES = {
    "Original": {
        "color": "#555555",
        "linestyle": "--",
        "marker": "o",
        "zorder": 4,
    },
    "Craig-Bampton": {
        "color": "#EE6677",
        "linestyle": "-",
        "marker": "^",
        "zorder": 3,
    },
    "Guyan": {
        "color": "#4477AA",
        "linestyle": "-.",
        "marker": "s",
        "zorder": 2,
    },
}

# Figure 3-5 compares floors, not methods.  The labels retain "Original" so
# that the single permitted method remains explicit while floor identity is
# encoded independently by colour, line style, and marker.
FLOOR_STYLES = {
    "Floor 1": {"color": "#4477AA", "linestyle": "-", "marker": "o"},
    "Floor 2": {"color": "#EE6677", "linestyle": "--", "marker": "^"},
    "Floor 3": {"color": "#228833", "linestyle": "-.", "marker": "s"},
}

FIGURE_DATA_FIELDS = (
    "object_id",
    "object_name",
    "version",
    "panel",
    "source_dataset",
    "source_mat_filename",
    "source_column",
    "time_s",
    "floor",
    "method",
    "response_mm",
    "value_mm",
    "window_start_s",
    "window_end_s",
)

METRIC_FIELDS = (
    "object_id",
    "object_name",
    "version",
    "panel",
    "source_dataset",
    "source_mat_filename",
    "source_column",
    "floor",
    "method",
    "sample_count",
    "window_start_s",
    "window_end_s",
    "peak_abs_mm",
    "rms_mm",
    "final_mm",
    "min_mm",
    "max_mm",
    "status",
)

MANIFEST_FIELDS = (
    "figure_pair_id",
    "object_id",
    "object_name",
    "version",
    "figure_basename",
    "artifact_type",
    "relative_path",
    "sha256",
    "size_bytes",
    "expected_pdf_pages",
    "expected_png_dpi",
    "source_data_csv_relative_path",
    "metrics_csv_relative_path",
    "contract_json_relative_path",
)


@dataclass(frozen=True)
class ResponseDataset:
    dataset_id: str
    filename: str
    source_path: Path
    time_s: np.ndarray
    response_mm: np.ndarray
    sha256: str


@dataclass(frozen=True)
class PanelSpec:
    panel: str
    source_dataset: str
    floors: tuple[str, ...]
    methods: tuple[str, ...]
    window_start_s: float
    window_end_s: float


@dataclass(frozen=True)
class VersionSpec:
    version: str
    figure_basename: str
    panels: tuple[PanelSpec, ...]


@dataclass(frozen=True)
class FigureObject:
    object_id: str
    figure_number: str
    object_name: str
    object_directory: str
    versions: tuple[VersionSpec, ...]


def response_panels(
    dataset_id: str,
    floor: str,
    windows: tuple[tuple[float, float], tuple[float, float]],
) -> tuple[PanelSpec, ...]:
    """Create the fixed full/zoom_1/zoom_2 panel contract."""
    return (
        PanelSpec(
            panel="full",
            source_dataset=dataset_id,
            floors=(floor,),
            methods=PLOTTING_METHOD_ORDER,
            window_start_s=0.0,
            window_end_s=40.0,
        ),
        PanelSpec(
            panel="zoom_1",
            source_dataset=dataset_id,
            floors=(floor,),
            methods=PLOTTING_METHOD_ORDER,
            window_start_s=windows[0][0],
            window_end_s=windows[0][1],
        ),
        PanelSpec(
            panel="zoom_2",
            source_dataset=dataset_id,
            floors=(floor,),
            methods=PLOTTING_METHOD_ORDER,
            window_start_s=windows[1][0],
            window_end_s=windows[1][1],
        ),
    )


EARTHQUAKE_WINDOWS = ((10.0, 11.0), (21.5, 22.5))
CHIRP_WINDOWS = ((13.0, 14.0), (38.0, 38.3))

OBJECTS = (
    FigureObject(
        object_id="F3-5",
        figure_number="3-5",
        object_name="单位激励下的3层响应",
        object_directory="F3-5_单位激励下的3层响应",
        versions=(
            VersionSpec(
                version="standard",
                figure_basename="F3-5_单位激励下的3层响应",
                panels=(
                    PanelSpec(
                        panel="full",
                        source_dataset="unit",
                        floors=MAT_FLOOR_ORDER,
                        methods=("Original",),
                        window_start_s=0.0,
                        window_end_s=40.0,
                    ),
                ),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-6",
        figure_number="3-6",
        object_name="第一类子结构划分-地震激励下的一层水平位移",
        object_directory="F3-6_第一类子结构划分-地震激励下的一层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-6_第一类子结构划分-地震激励下的一层水平位移",
                response_panels("division1_elcentro", "Floor 1", EARTHQUAKE_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-7",
        figure_number="3-7",
        object_name="第一类子结构划分-地震激励下的二层水平位移",
        object_directory="F3-7_第一类子结构划分-地震激励下的二层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-7_第一类子结构划分-地震激励下的二层水平位移",
                response_panels("division1_elcentro", "Floor 2", EARTHQUAKE_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-8",
        figure_number="3-8",
        object_name="第一类子结构划分-地震激励下的三层水平位移",
        object_directory="F3-8_第一类子结构划分-地震激励下的三层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-8_第一类子结构划分-地震激励下的三层水平位移",
                response_panels("division1_elcentro", "Floor 3", EARTHQUAKE_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-9",
        figure_number="3-9",
        object_name="第二类子结构划分-地震激励下的一层水平位移",
        object_directory="F3-9_第二类子结构划分-地震激励下的一层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-9_第二类子结构划分-地震激励下的一层水平位移",
                response_panels("division2_elcentro", "Floor 1", EARTHQUAKE_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-10",
        figure_number="3-10",
        object_name="第二类子结构划分-地震激励下的三层水平位移",
        object_directory="F3-10_第二类子结构划分-地震激励下的三层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-10_第二类子结构划分-地震激励下的三层水平位移",
                response_panels("division2_elcentro", "Floor 3", EARTHQUAKE_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-11",
        figure_number="3-11",
        object_name="第一类子结构划分-Chirp信号的一层水平位移",
        object_directory="F3-11_第一类子结构划分-Chirp信号的一层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-11_第一类子结构划分-Chirp信号的一层水平位移",
                response_panels("division1_chirp", "Floor 1", CHIRP_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-12",
        figure_number="3-12",
        object_name="第一类子结构划分-Chirp信号的二层水平位移",
        object_directory="F3-12_第一类子结构划分-Chirp信号的二层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-12_第一类子结构划分-Chirp信号的二层水平位移",
                response_panels("division1_chirp", "Floor 2", CHIRP_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-13",
        figure_number="3-13",
        object_name="第一类子结构划分-Chirp信号的三层水平位移",
        object_directory="F3-13_第一类子结构划分-Chirp信号的三层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-13_第一类子结构划分-Chirp信号的三层水平位移",
                response_panels("division1_chirp", "Floor 3", CHIRP_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-14",
        figure_number="3-14",
        object_name="第二类子结构划分-Chirp信号的一层水平位移",
        object_directory="F3-14_第二类子结构划分-Chirp信号的一层水平位移",
        versions=(
            VersionSpec(
                "standard",
                "F3-14_第二类子结构划分-Chirp信号的一层水平位移",
                response_panels("division2_chirp", "Floor 1", CHIRP_WINDOWS),
            ),
        ),
    ),
    FigureObject(
        object_id="F3-15",
        figure_number="3-15",
        object_name="第二类子结构划分-Chirp信号的三层水平位移",
        object_directory="F3-15_第二类子结构划分-Chirp信号的三层水平位移",
        versions=(
            VersionSpec(
                version="paper_historical_composite",
                figure_basename="F3-15_论文历史组合版",
                panels=(
                    PanelSpec(
                        "full",
                        "division2_chirp",
                        ("Floor 3",),
                        PLOTTING_METHOD_ORDER,
                        0.0,
                        40.0,
                    ),
                    PanelSpec(
                        "zoom_1",
                        "division2_elcentro",
                        ("Floor 3",),
                        PLOTTING_METHOD_ORDER,
                        10.0,
                        11.0,
                    ),
                    PanelSpec(
                        "zoom_2",
                        "division2_elcentro",
                        ("Floor 3",),
                        PLOTTING_METHOD_ORDER,
                        21.5,
                        22.5,
                    ),
                ),
            ),
            VersionSpec(
                version="physically_consistent_corrected",
                figure_basename="F3-15_物理一致修正版",
                panels=response_panels("division2_chirp", "Floor 3", CHIRP_WINDOWS),
            ),
        ),
    ),
)


def setup_plot_style() -> None:
    """Apply the frozen 9 pt journal plotting style without Type-3 fonts."""
    mpl.rcParams.update(
        {
            "text.usetex": False,
            "font.family": "serif",
            "font.serif": ["DejaVu Serif"],
            "mathtext.fontset": "dejavuserif",
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
            "lines.markersize": 4.0,
            "legend.frameon": False,
            "axes.grid": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.02,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
        }
    )


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def matlab_text_tuple(value: object) -> tuple[str, ...]:
    items: list[str] = []
    for item in np.asarray(value, dtype=object).reshape(-1):
        array = np.asarray(item)
        if array.size != 1:
            raise ValueError(f"MATLAB text cell is not scalar: shape={array.shape}")
        items.append(str(array.reshape(-1)[0]))
    return tuple(items)


def load_response_dataset(dataset_id: str, filename: str) -> ResponseDataset:
    path = INPUT_ROOT / filename
    if not path.is_file():
        raise FileNotFoundError(f"Missing adapted-run response MAT: {path}")
    raw = loadmat(
        path,
        variable_names=["time_s", "response_mm", "method_order", "floor_order"],
        squeeze_me=False,
        struct_as_record=False,
    )
    required = {"time_s", "response_mm", "method_order", "floor_order"}
    missing = sorted(required.difference(raw))
    if missing:
        raise KeyError(f"{path.name}: missing variables {missing}")

    method_order = matlab_text_tuple(raw["method_order"])
    floor_order = matlab_text_tuple(raw["floor_order"])
    if method_order != MAT_METHOD_ORDER:
        raise ValueError(
            f"{path.name}: method_order={method_order}, expected {MAT_METHOD_ORDER}"
        )
    if floor_order != MAT_FLOOR_ORDER:
        raise ValueError(
            f"{path.name}: floor_order={floor_order}, expected {MAT_FLOOR_ORDER}"
        )

    time_s = np.asarray(raw["time_s"], dtype=np.float64).reshape(-1)
    response_mm = np.asarray(raw["response_mm"], dtype=np.float64)
    if time_s.shape != (EXPECTED_SAMPLE_COUNT,):
        raise ValueError(
            f"{path.name}: time shape {time_s.shape}, expected ({EXPECTED_SAMPLE_COUNT},)"
        )
    if response_mm.shape != (EXPECTED_SAMPLE_COUNT, 3, 3):
        raise ValueError(
            f"{path.name}: response shape {response_mm.shape}, expected "
            f"({EXPECTED_SAMPLE_COUNT}, 3, 3)"
        )
    if not np.array_equal(time_s, EXPECTED_TIME_S):
        max_delta = float(np.max(np.abs(time_s - EXPECTED_TIME_S)))
        raise ValueError(
            f"{path.name}: time is not exactly 0:1/1024:40; max delta={max_delta:.17g} s"
        )
    if not np.all(np.isfinite(time_s)) or not np.all(np.isfinite(response_mm)):
        raise ValueError(f"{path.name}: time_s or response_mm contains NaN/Inf")

    # Make the loaded arrays immutable inside this script so plotting and CSV
    # export cannot accidentally change the numerical evidence.
    time_s.setflags(write=False)
    response_mm.setflags(write=False)
    return ResponseDataset(
        dataset_id=dataset_id,
        filename=filename,
        source_path=path,
        time_s=time_s,
        response_mm=response_mm,
        sha256=file_sha256(path),
    )


def load_all_datasets() -> dict[str, ResponseDataset]:
    datasets = {
        dataset_id: load_response_dataset(dataset_id, filename)
        for dataset_id, filename in DATASET_FILES.items()
    }
    if tuple(datasets) != tuple(DATASET_FILES):
        raise AssertionError("Dataset iteration order changed unexpectedly")
    reference_time = datasets["unit"].time_s
    for dataset in datasets.values():
        if not np.array_equal(dataset.time_s, reference_time):
            raise AssertionError(f"Time axes differ: unit vs {dataset.dataset_id}")
    return datasets


def load_comparison_evidence() -> dict[str, object]:
    """Require the complete 135-row numerical comparison gate to pass."""
    if not COMPARISON_CSV.is_file():
        raise FileNotFoundError(f"Missing numerical comparison gate: {COMPARISON_CSV}")
    with COMPARISON_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "comparison",
            "dataset_id",
            "filename",
            "floor",
            "method",
            "status",
        }
        missing = sorted(required.difference(reader.fieldnames or []))
        if missing:
            raise KeyError(f"Comparison CSV is missing columns {missing}")
        rows = list(reader)

    expected_keys = {
        (comparison, dataset_id, floor, method)
        for comparison in EXPECTED_COMPARISONS
        for dataset_id in DATASET_FILES
        for floor in MAT_FLOOR_ORDER
        for method in MAT_METHOD_ORDER
    }
    observed_keys = {
        (row["comparison"], row["dataset_id"], row["floor"], row["method"])
        for row in rows
    }
    if len(rows) != len(observed_keys):
        raise ValueError("Comparison CSV contains duplicate comparison/dataset/floor/method rows")
    if observed_keys != expected_keys:
        missing_keys = sorted(expected_keys - observed_keys)
        extra_keys = sorted(observed_keys - expected_keys)
        raise ValueError(
            f"Comparison key contract mismatch; missing={missing_keys[:3]}, "
            f"extra={extra_keys[:3]}"
        )
    wrong_filename = [
        row
        for row in rows
        if row["filename"] != DATASET_FILES[row["dataset_id"]]
    ]
    if wrong_filename:
        raise ValueError(f"Comparison CSV filename mismatch: {wrong_filename[0]}")
    failed = [row for row in rows if row["status"].strip().upper() != "PASS"]
    if failed:
        first = failed[0]
        raise RuntimeError(
            "Numerical comparison gate failed before plotting: "
            f"{first['comparison']} / {first['dataset_id']} / "
            f"{first['floor']} / {first['method']}"
        )
    return {
        "source_csv": COMPARISON_CSV.relative_to(BOARD).as_posix(),
        "sha256": file_sha256(COMPARISON_CSV),
        "row_count": len(rows),
        "expected_row_count": 135,
        "comparisons": list(EXPECTED_COMPARISONS),
        "all_pass": True,
    }


def validate_object_contract() -> None:
    if len(OBJECTS) != 11:
        raise AssertionError(f"Expected 11 figure objects, got {len(OBJECTS)}")
    if len({obj.object_id for obj in OBJECTS}) != 11:
        raise AssertionError("Figure object IDs are not unique")
    if len({obj.object_directory for obj in OBJECTS}) != 11:
        raise AssertionError("Figure object directories are not unique")
    figure_pairs = [version for obj in OBJECTS for version in obj.versions]
    if len(figure_pairs) != 12:
        raise AssertionError(f"Expected 12 figure pairs, got {len(figure_pairs)}")
    if len({version.figure_basename for version in figure_pairs}) != 12:
        raise AssertionError("Figure basenames are not unique")
    for obj in OBJECTS:
        for version in obj.versions:
            panel_names = tuple(panel.panel for panel in version.panels)
            expected = ("full",) if obj.object_id == "F3-5" else ("full", "zoom_1", "zoom_2")
            if panel_names != expected:
                raise AssertionError(
                    f"{obj.object_id}/{version.version}: panels={panel_names}, expected={expected}"
                )
            for panel in version.panels:
                if panel.source_dataset not in DATASET_FILES:
                    raise AssertionError(f"Unknown source dataset {panel.source_dataset}")
                if not panel.floors or any(floor not in MAT_FLOOR_ORDER for floor in panel.floors):
                    raise AssertionError(f"Invalid floors in {obj.object_id}/{panel.panel}")
                if not panel.methods or any(method not in MAT_METHOD_ORDER for method in panel.methods):
                    raise AssertionError(f"Invalid methods in {obj.object_id}/{panel.panel}")
                if not 0.0 <= panel.window_start_s < panel.window_end_s <= 40.0:
                    raise AssertionError(f"Invalid window in {obj.object_id}/{panel.panel}")


def panel_mask(dataset: ResponseDataset, panel: PanelSpec) -> np.ndarray:
    mask = (dataset.time_s >= panel.window_start_s) & (
        dataset.time_s <= panel.window_end_s
    )
    if np.count_nonzero(mask) < 2:
        raise ValueError(
            f"{panel.source_dataset}/{panel.panel}: window "
            f"[{panel.window_start_s}, {panel.window_end_s}] has fewer than 2 samples"
        )
    return mask


def source_column(floor: str, method: str) -> str:
    return f"response_mm[:,{FLOOR_INDEX[floor]},{METHOD_INDEX[method]}]"


def iter_series(
    version: VersionSpec,
    datasets: dict[str, ResponseDataset],
) -> Iterable[tuple[PanelSpec, ResponseDataset, str, str, np.ndarray, np.ndarray]]:
    for panel in version.panels:
        dataset = datasets[panel.source_dataset]
        mask = panel_mask(dataset, panel)
        time_s = dataset.time_s[mask]
        for floor in panel.floors:
            for method in panel.methods:
                values = dataset.response_mm[
                    mask, FLOOR_INDEX[floor], METHOD_INDEX[method]
                ]
                yield panel, dataset, floor, method, time_s, values


def assert_f315_historical_matches_f310(
    datasets: dict[str, ResponseDataset],
) -> dict[str, object]:
    """Prove both historical F3-15 zooms equal F3-10 zoom data pointwise."""
    f310 = next(obj for obj in OBJECTS if obj.object_id == "F3-10").versions[0]
    f315_historical = next(
        version
        for obj in OBJECTS
        if obj.object_id == "F3-15"
        for version in obj.versions
        if version.version == "paper_historical_composite"
    )
    checked_methods = 0
    checked_points = 0
    for panel_name in ("zoom_1", "zoom_2"):
        left_panel = next(panel for panel in f310.panels if panel.panel == panel_name)
        right_panel = next(
            panel for panel in f315_historical.panels if panel.panel == panel_name
        )
        if left_panel != right_panel:
            raise AssertionError(
                f"F3-15 historical {panel_name} contract differs from F3-10: "
                f"{right_panel!r} != {left_panel!r}"
            )
        dataset = datasets[left_panel.source_dataset]
        left_mask = panel_mask(dataset, left_panel)
        right_mask = panel_mask(dataset, right_panel)
        np.testing.assert_array_equal(dataset.time_s[left_mask], dataset.time_s[right_mask])
        for method in PLOTTING_METHOD_ORDER:
            column = METHOD_INDEX[method]
            left = dataset.response_mm[left_mask, FLOOR_INDEX["Floor 3"], column]
            right = dataset.response_mm[right_mask, FLOOR_INDEX["Floor 3"], column]
            np.testing.assert_array_equal(left, right)
            checked_methods += 1
            checked_points += left.size
    return {
        "status": "PASS",
        "assertion": (
            "F3-15 paper_historical_composite zoom_1 and zoom_2 are pointwise "
            "identical to F3-10 for every plotted method"
        ),
        "checked_method_windows": checked_methods,
        "checked_values": checked_points,
        "source_dataset": "division2_elcentro",
        "floor": "Floor 3",
    }


def finite_margin(values: np.ndarray, fraction: float = 0.08) -> tuple[float, float]:
    lo = float(np.min(values))
    hi = float(np.max(values))
    span = hi - lo
    if span <= np.finfo(float).eps:
        span = max(abs(lo), 1.0)
    return lo - fraction * span, hi + fraction * span


def apply_axis_style(ax: plt.Axes, nx: int = 5, ny: int = 5) -> None:
    ax.xaxis.set_major_locator(MaxNLocator(nbins=nx))
    ax.yaxis.set_major_locator(MaxNLocator(nbins=ny))
    ax.tick_params(which="major", direction="in", top=True, right=True, length=3.5)
    ax.grid(False)
    ax.set_title("")
    for spine in ax.spines.values():
        spine.set_linewidth(0.8)


def plot_method_panel(
    ax: plt.Axes,
    dataset: ResponseDataset,
    panel: PanelSpec,
    *,
    show_legend: bool,
) -> None:
    if len(panel.floors) != 1 or panel.methods != PLOTTING_METHOD_ORDER:
        raise AssertionError("Method panel requires one floor and the frozen plotting order")
    floor = panel.floors[0]
    mask = panel_mask(dataset, panel)
    time_s = dataset.time_s[mask]
    plotted_values: list[np.ndarray] = []
    marker_step = max(1, time_s.size // 18)
    for method in PLOTTING_METHOD_ORDER:
        style = METHOD_STYLES[method]
        values = dataset.response_mm[mask, FLOOR_INDEX[floor], METHOD_INDEX[method]]
        plotted_values.append(values)
        ax.plot(
            time_s,
            values,
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markevery=marker_step,
            markersize=3.4,
            markerfacecolor="white",
            markeredgecolor=style["color"],
            markeredgewidth=0.7,
            linewidth=0.9 if panel.panel == "full" else 1.1,
            label=method,
            zorder=style["zorder"],
        )
    combined = np.column_stack(plotted_values)
    ax.set_xlim(panel.window_start_s, panel.window_end_s)
    ax.set_ylim(*finite_margin(combined))
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Displacement (mm)")
    apply_axis_style(ax, nx=6 if panel.panel == "full" else 5, ny=5)
    if show_legend:
        handles, labels = ax.get_legend_handles_labels()
        if tuple(labels) != PLOTTING_METHOD_ORDER:
            raise AssertionError(f"Legend order changed: {labels}")
        ax.legend(
            handles,
            labels,
            loc="upper right",
            frameon=False,
            handlelength=2.3,
            handletextpad=0.5,
        )


def plot_unit_figure(
    obj: FigureObject,
    version: VersionSpec,
    datasets: dict[str, ResponseDataset],
) -> plt.Figure:
    panel = version.panels[0]
    dataset = datasets[panel.source_dataset]
    mask = panel_mask(dataset, panel)
    time_s = dataset.time_s[mask]
    fig, ax = plt.subplots(figsize=(7.48, 3.60), constrained_layout=True)
    values_for_limits: list[np.ndarray] = []
    marker_step = max(1, time_s.size // 18)
    for floor in MAT_FLOOR_ORDER:
        style = FLOOR_STYLES[floor]
        values = dataset.response_mm[mask, FLOOR_INDEX[floor], METHOD_INDEX["Original"]]
        values_for_limits.append(values)
        ax.plot(
            time_s,
            values,
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markevery=marker_step,
            markersize=3.4,
            markerfacecolor="white",
            markeredgecolor=style["color"],
            markeredgewidth=0.7,
            linewidth=1.0,
            label=f"Original — {floor}",
        )
    ax.set_xlim(0.0, 40.0)
    ax.set_ylim(*finite_margin(np.column_stack(values_for_limits)))
    ax.set_xlabel("Time (s)")
    ax.set_ylabel("Displacement (mm)")
    apply_axis_style(ax, nx=6, ny=5)
    ax.legend(loc="upper right", frameon=False, handlelength=2.3, handletextpad=0.5)
    if ax.get_title():
        raise AssertionError(f"{obj.object_id}: title must be empty")
    return fig


def plot_comparison_figure(
    obj: FigureObject,
    version: VersionSpec,
    datasets: dict[str, ResponseDataset],
) -> plt.Figure:
    panels = {panel.panel: panel for panel in version.panels}
    if tuple(panels) != ("full", "zoom_1", "zoom_2"):
        raise AssertionError(f"{obj.object_id}/{version.version}: unexpected panel order")
    fig = plt.figure(figsize=(7.48, 5.00), constrained_layout=True)
    grid = GridSpec(2, 2, figure=fig, height_ratios=[1.05, 1.0])
    axes = {
        "full": fig.add_subplot(grid[0, :]),
        "zoom_1": fig.add_subplot(grid[1, 0]),
        "zoom_2": fig.add_subplot(grid[1, 1]),
    }
    labels = {"full": "(a)", "zoom_1": "(b)", "zoom_2": "(c)"}
    for panel_name, ax in axes.items():
        panel = panels[panel_name]
        plot_method_panel(
            ax,
            datasets[panel.source_dataset],
            panel,
            show_legend=panel_name == "full",
        )
        ax.text(
            0.02,
            0.96,
            labels[panel_name],
            transform=ax.transAxes,
            ha="left",
            va="top",
            fontsize=9,
        )
        if ax.get_title():
            raise AssertionError(f"{obj.object_id}/{version.version}: title must be empty")
    return fig


def save_figure_pair(fig: plt.Figure, figure_dir: Path, basename: str) -> tuple[Path, Path]:
    pdf_path = figure_dir / f"{basename}.pdf"
    png_path = figure_dir / f"{basename}.png"
    pdf_metadata = {
        "Title": None,
        "Author": None,
        "Subject": None,
        "Keywords": None,
        "Creator": "Board18 auditable candidate plotter",
        "Producer": "Matplotlib",
        "CreationDate": None,
        "ModDate": None,
    }
    fig.savefig(pdf_path, format="pdf", metadata=pdf_metadata)
    fig.savefig(png_path, format="png", dpi=600)
    plt.close(fig)
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        raise RuntimeError(f"PDF was not created: {pdf_path}")
    if not png_path.is_file() or png_path.stat().st_size == 0:
        raise RuntimeError(f"PNG was not created: {png_path}")
    return pdf_path, png_path


def format_float(value: float) -> str:
    return format(float(value), ".17g")


def write_object_data_and_metrics(
    obj: FigureObject,
    datasets: dict[str, ResponseDataset],
    object_dir: Path,
) -> tuple[Path, Path]:
    data_dir = object_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=False)
    data_path = data_dir / "figure_plot_data.csv"
    metrics_path = object_dir / "metrics.csv"
    metric_rows: list[dict[str, object]] = []

    with data_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIGURE_DATA_FIELDS)
        writer.writeheader()
        for version in obj.versions:
            for panel, dataset, floor, method, time_s, values in iter_series(
                version, datasets
            ):
                column = source_column(floor, method)
                start = format_float(panel.window_start_s)
                end = format_float(panel.window_end_s)
                for sample_time, value in zip(time_s, values, strict=True):
                    value_text = format_float(float(value))
                    writer.writerow(
                        {
                            "object_id": obj.object_id,
                            "object_name": obj.object_name,
                            "version": version.version,
                            "panel": panel.panel,
                            "source_dataset": dataset.dataset_id,
                            "source_mat_filename": dataset.filename,
                            "source_column": column,
                            "time_s": format_float(float(sample_time)),
                            "floor": floor,
                            "method": method,
                            "response_mm": value_text,
                            "value_mm": value_text,
                            "window_start_s": start,
                            "window_end_s": end,
                        }
                    )
                metric_rows.append(
                    {
                        "object_id": obj.object_id,
                        "object_name": obj.object_name,
                        "version": version.version,
                        "panel": panel.panel,
                        "source_dataset": dataset.dataset_id,
                        "source_mat_filename": dataset.filename,
                        "source_column": column,
                        "floor": floor,
                        "method": method,
                        "sample_count": values.size,
                        "window_start_s": start,
                        "window_end_s": end,
                        "peak_abs_mm": format_float(float(np.max(np.abs(values)))),
                        "rms_mm": format_float(float(np.sqrt(np.mean(values * values)))),
                        "final_mm": format_float(float(values[-1])),
                        "min_mm": format_float(float(np.min(values))),
                        "max_mm": format_float(float(np.max(values))),
                        "status": "PASS",
                    }
                )

    with metrics_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=METRIC_FIELDS)
        writer.writeheader()
        writer.writerows(metric_rows)
    return data_path, metrics_path


def panel_contract(panel: PanelSpec) -> dict[str, object]:
    return {
        "panel": panel.panel,
        "source_dataset": panel.source_dataset,
        "source_mat_filename": DATASET_FILES[panel.source_dataset],
        "floors": list(panel.floors),
        "methods": list(panel.methods),
        "window_start_s": panel.window_start_s,
        "window_end_s": panel.window_end_s,
        "window_inclusive": True,
    }


def write_contract_json(
    obj: FigureObject,
    datasets: dict[str, ResponseDataset],
    comparison_evidence: dict[str, object],
    object_dir: Path,
) -> Path:
    used_dataset_ids = sorted(
        {
            panel.source_dataset
            for version in obj.versions
            for panel in version.panels
        }
    )
    contract = {
        "schema_version": "board18.figure_contract.v1",
        "object_id": obj.object_id,
        "figure_number": obj.figure_number,
        "object_name": obj.object_name,
        "object_directory": obj.object_directory,
        "versions": [
            {
                "version": version.version,
                "figure_basename": version.figure_basename,
                "panels": [panel_contract(panel) for panel in version.panels],
            }
            for version in obj.versions
        ],
        "source_files": [
            {
                "dataset_id": dataset_id,
                "filename": datasets[dataset_id].filename,
                "relative_path": datasets[dataset_id].source_path.relative_to(BOARD).as_posix(),
                "sha256": datasets[dataset_id].sha256,
            }
            for dataset_id in used_dataset_ids
        ],
        "mat_method_order": list(MAT_METHOD_ORDER),
        "mat_floor_order": list(MAT_FLOOR_ORDER),
        "plotting_method_order": list(PLOTTING_METHOD_ORDER),
        "sample_count": EXPECTED_SAMPLE_COUNT,
        "time_contract": {
            "start_s": 0.0,
            "end_s": 40.0,
            "step_s": EXPECTED_DT_S,
            "sample_count": EXPECTED_SAMPLE_COUNT,
            "validation": "exact array equality with arange(40961)/1024",
        },
        "style": {
            "font_family": "DejaVu Serif",
            "font_size_pt": 9,
            "pdf_fonttype": 42,
            "ps_fonttype": 42,
            "no_title": True,
            "no_grid": True,
            "ticks": "inward on all four sides",
            "method_styles": METHOD_STYLES,
            "floor_styles_for_F3_5": FLOOR_STYLES if obj.object_id == "F3-5" else None,
        },
        "output_contract": {
            "figures_directory": "figures",
            "figure_plot_data_csv": "data/figure_plot_data.csv",
            "metrics_csv": "metrics.csv",
            "contract_json": "contract.json",
            "pdf": "single-page vector with embedded TrueType fonts",
            "png_dpi": 600,
        },
        "comparison_evidence": comparison_evidence,
        "historical_value_status": (
            "历史值：论文原始逐点曲线数组未找到；本对象由现存代码必要适配路线的"
            "adapted_run1重算MAT绘图，最高标签为计算级复现候选。"
        ),
    }
    if obj.object_id == "F3-15":
        contract["figure_3_15_exception"] = {
            "paper_historical_composite": (
                "full uses Division-II chirp Floor 3; zoom_1 and zoom_2 use the "
                "Division-II El Centro Floor-3 windows copied pointwise from F3-10"
            ),
            "physically_consistent_corrected": (
                "full and both zoom panels use Division-II chirp Floor 3"
            ),
        }
    path = object_dir / "contract.json"
    path.write_text(json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def write_manifest(rows: Sequence[dict[str, object]]) -> Path:
    path = OUTPUT_ROOT / "artifact_manifest.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return path


def artifact_rows_for_figure(
    obj: FigureObject,
    version: VersionSpec,
    paths: tuple[Path, Path],
    data_path: Path,
    metrics_path: Path,
    contract_path: Path,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for artifact_type, path in zip(("PDF", "PNG"), paths, strict=True):
        rows.append(
            {
                "figure_pair_id": f"{obj.object_id}:{version.version}",
                "object_id": obj.object_id,
                "object_name": obj.object_name,
                "version": version.version,
                "figure_basename": version.figure_basename,
                "artifact_type": artifact_type,
                "relative_path": path.relative_to(OUTPUT_ROOT).as_posix(),
                "sha256": file_sha256(path),
                "size_bytes": path.stat().st_size,
                "expected_pdf_pages": 1 if artifact_type == "PDF" else "",
                "expected_png_dpi": 600 if artifact_type == "PNG" else "",
                "source_data_csv_relative_path": data_path.relative_to(OUTPUT_ROOT).as_posix(),
                "metrics_csv_relative_path": metrics_path.relative_to(OUTPUT_ROOT).as_posix(),
                "contract_json_relative_path": contract_path.relative_to(OUTPUT_ROOT).as_posix(),
            }
        )
    return rows


def main() -> int:
    validate_object_contract()
    setup_plot_style()
    if OUTPUT_ROOT.exists():
        raise FileExistsError(
            f"Candidate root already exists and will not be overwritten: {OUTPUT_ROOT}"
        )

    # All read-only gates run before the first output directory is created.
    datasets = load_all_datasets()
    comparison_evidence = load_comparison_evidence()
    f315_assertion = assert_f315_historical_matches_f310(datasets)

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=False)
    manifest_rows: list[dict[str, object]] = []
    for obj in OBJECTS:
        object_dir = OUTPUT_ROOT / obj.object_directory
        figure_dir = object_dir / "figures"
        object_dir.mkdir(parents=False, exist_ok=False)
        figure_dir.mkdir(parents=False, exist_ok=False)
        data_path, metrics_path = write_object_data_and_metrics(
            obj, datasets, object_dir
        )
        contract_path = write_contract_json(
            obj, datasets, comparison_evidence, object_dir
        )

        for version in obj.versions:
            if obj.object_id == "F3-5":
                fig = plot_unit_figure(obj, version, datasets)
            else:
                fig = plot_comparison_figure(obj, version, datasets)
            paths = save_figure_pair(fig, figure_dir, version.figure_basename)
            manifest_rows.extend(
                artifact_rows_for_figure(
                    obj,
                    version,
                    paths,
                    data_path,
                    metrics_path,
                    contract_path,
                )
            )

    if len(manifest_rows) != 24:
        raise AssertionError(f"Expected 24 PDF/PNG artifacts, got {len(manifest_rows)}")
    if len({row["figure_pair_id"] for row in manifest_rows}) != 12:
        raise AssertionError("Expected 12 unique figure pairs")
    manifest_path = write_manifest(manifest_rows)
    summary = {
        "schema_version": "board18.figure_generation_summary.v1",
        "status": "PASS",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_root": OUTPUT_ROOT.relative_to(BOARD).as_posix(),
        "input_root": INPUT_ROOT.relative_to(BOARD).as_posix(),
        "comparison_csv": COMPARISON_CSV.relative_to(BOARD).as_posix(),
        "object_count": len(OBJECTS),
        "figure_pair_count": len({row["figure_pair_id"] for row in manifest_rows}),
        "pdf_count": sum(row["artifact_type"] == "PDF" for row in manifest_rows),
        "png_count": sum(row["artifact_type"] == "PNG" for row in manifest_rows),
        "manifest_sha256": file_sha256(manifest_path),
        "f3_15_historical_assertion": f315_assertion,
        "source_mat_sha256": {
            dataset_id: dataset.sha256 for dataset_id, dataset in datasets.items()
        },
        "output_contract": {
            "artifact_manifest": "artifact_manifest.csv",
            "objects": "11 directories named <F3-x_中文名>",
            "figure_pairs": 12,
            "pdf_files": 12,
            "png_files": 12,
            "pdf_pages_each": 1,
            "pdf_kind": "vector",
            "png_dpi": 600,
            "formal_success_directories_created": False,
        },
    }
    summary_path = OUTPUT_ROOT / "generation_summary.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        "Board18 candidate plotting PASS: "
        f"{len(OBJECTS)} objects, 12 PDF, 12 PNG -> {OUTPUT_ROOT}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

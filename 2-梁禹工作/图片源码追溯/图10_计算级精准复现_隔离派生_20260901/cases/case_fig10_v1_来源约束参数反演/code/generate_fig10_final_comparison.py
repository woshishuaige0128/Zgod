#!/usr/bin/env python
"""生成图10最终对比图及逐点可编辑数据。

证据边界
--------
本程序位于评价端，只在盲算候选已经落盘后读取：
1. 硕士论文矢量追踪得到的386个目标点；
2. 历史 lqr_2/lqr_3 掩膜的MATLAB可见开边界；
3. 严格评价器从盲算掩膜提取的候选边界。

它不会生成控制器、不会求根、不会修改盲算输入，也不会把目标数据回传给
求解器。图中的计算候选必须标为“目标引导的校准计算复现”；即使视觉接近，
也不能据此宣称恢复了作者原始计算合同。
"""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator


CASE_ROOT = Path(__file__).resolve().parents[1]
DELIVERY_ROOT = CASE_ROOT.parents[1]
DEFAULT_TARGET_CSV = Path(
    r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\figure\小论文Fig10复现"
    r"\01_论文矢量边界主数据\Fig10_六条论文边界_采样步与毫秒.csv"
)
DEFAULT_ACTIVE_PDF = Path(
    r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\figure\results_v2\PDF"
    r"\fig10_stability_domain.pdf"
)
DEFAULT_REBUILT_PDF = Path(
    r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\figure\小论文Fig10复现"
    r"\02_小论文Fig10最终图\PDF\fig10_stability_domain.pdf"
)
DEFAULT_HISTORY_DIR = Path(
    r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\figure\小论文Fig10复现"
    r"\05_完整计算复现审计_未通过\计算结果\候选掩膜与边界\历史MATLAB边界"
)
MS_PER_STEP = 1000.0 / 1024.0

DIVISION_TO_FIGURE = {1: "4-4", 2: "4-5"}
METHODS = ("Original", "Craig-Bampton", "Guyan")
METHOD_TO_FILE = {
    "Original": "Original",
    "Craig-Bampton": "Craig-Bampton",
    "Guyan": "Guyan",
}
METHOD_TO_ID = {
    "Original": "original",
    "Craig-Bampton": "craig_bampton",
    "Guyan": "guyan",
}
PANEL_NAMES = {
    (1, "Original"): "Original, division I",
    (2, "Original"): "Original, division II",
    (1, "Craig-Bampton"): "Craig--Bampton, division I",
    (2, "Craig-Bampton"): "Craig--Bampton, division II",
    (1, "Guyan"): "Guyan, division I",
    (2, "Guyan"): "Guyan, division II",
}


@dataclass(frozen=True)
class Point:
    order: int
    tau1_step: int
    tau2_step: int
    tau1_ms: float
    tau2_ms: float


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def read_target(path: Path) -> dict[tuple[int, str], list[Point]]:
    datasets: dict[tuple[int, str], list[Point]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            division = 1 if row["figure"] == "4-4" else 2
            method = row["method"]
            point = Point(
                order=int(row["point_order"]),
                tau1_step=int(row["tau1_step"]),
                tau2_step=int(row["tau2_step"]),
                tau1_ms=float(row["tau1_ms"]),
                tau2_ms=float(row["tau2_ms"]),
            )
            datasets.setdefault((division, method), []).append(point)
    for points in datasets.values():
        points.sort(key=lambda item: item.order)
    expected = {(division, method) for division in (1, 2) for method in METHODS}
    if set(datasets) != expected:
        raise ValueError(f"目标CSV曲线身份不完整：{sorted(datasets)}")
    return datasets


def read_step_boundary(path: Path, x_name: str, y_name: str) -> list[Point]:
    points: list[Point] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    for index, row in enumerate(rows, start=1):
        order = int(row.get("point_order") or index)
        tau1_step = int(row[x_name])
        tau2_step = int(row[y_name])
        points.append(
            Point(
                order=order,
                tau1_step=tau1_step,
                tau2_step=tau2_step,
                tau1_ms=(tau1_step - 1) * MS_PER_STEP,
                tau2_ms=(tau2_step - 1) * MS_PER_STEP,
            )
        )
    points.sort(key=lambda item: item.order)
    if not points:
        raise ValueError(f"边界CSV为空：{path}")
    return points


def history_path(history_dir: Path, division: int, method: str) -> Path:
    suffix = METHOD_TO_FILE[method]
    return history_dir / f"历史_图4-{3 + division}_{suffix}_MATLAB可见开边界.csv"


def candidate_sort_key(candidate: dict[str, Any]) -> tuple[Any, ...]:
    return (
        -int(candidate.get("strict_curve_pass_count", 0)),
        int(candidate.get("total_set_difference_count", 10**9)),
        int(candidate.get("total_point_levenshtein_original", 10**9)),
        float(candidate.get("maximum_symmetric_hausdorff_steps", float("inf"))),
        int(candidate.get("total_abs_boundary_point_count_error", 10**9)),
        str(candidate.get("candidate_id", "")),
    )


def discover_selected_candidate(extra_batches: Iterable[Path]) -> tuple[dict[str, Any], Path]:
    default_batches = [
        CASE_ROOT / "evaluation" / "coarse_gain_sweep_v1" / "batch_evaluation_summary.json",
        CASE_ROOT
        / "evaluation"
        / "historical_diagnostic_fullgrid_v1"
        / "batch_evaluation_summary.json",
        CASE_ROOT / "evaluation" / "h07_energy_fullgrid_v1" / "batch_evaluation_summary.json",
    ]
    batch_paths: list[Path] = []
    for path in [*default_batches, *extra_batches]:
        resolved = path.resolve()
        if resolved.is_file() and resolved not in batch_paths:
            batch_paths.append(resolved)
    eligible: list[tuple[dict[str, Any], Path]] = []
    for batch_path in batch_paths:
        batch = load_json(batch_path)
        for candidate in batch.get("candidates", []):
            if candidate.get("ranking_eligibility_status") == "ELIGIBLE":
                eligible.append((candidate, batch_path))
    if not eligible:
        raise RuntimeError("没有拓扑门合格的候选，不能生成最终计算对比图")
    return min(eligible, key=lambda item: candidate_sort_key(item[0]))


def resolve_strict_summary(candidate: dict[str, Any]) -> Path:
    path = Path(candidate["strict_summary_path"]).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"严格评价摘要不存在：{path}")
    return path


def candidate_boundary_path(strict_summary_path: Path, division: int, method: str) -> Path:
    curve_id = f"division{division}_{METHOD_TO_ID[method]}"
    return strict_summary_path.parent / "mask_boundary_extraction" / f"{curve_id}.csv"


def configure_style() -> None:
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
            "lines.markersize": 3.4,
            "axes.grid": False,
            "legend.frameon": False,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": 600,
        }
    )


def xy(points: list[Point]) -> tuple[list[float], list[float]]:
    return [p.tau1_ms for p in points], [p.tau2_ms for p in points]


def append_rows(
    rows: list[dict[str, Any]],
    division: int,
    method: str,
    series: str,
    points: list[Point],
    source_path: Path,
) -> None:
    source_hash = sha256(source_path)
    for point in points:
        rows.append(
            {
                "division": division,
                "figure": DIVISION_TO_FIGURE[division],
                "method": method,
                "series": series,
                "point_order": point.order,
                "tau1_step": point.tau1_step,
                "tau2_step": point.tau2_step,
                "tau1_ms": f"{point.tau1_ms:.12f}",
                "tau2_ms": f"{point.tau2_ms:.12f}",
                "source_path": str(source_path),
                "source_sha256": source_hash,
            }
        )


def write_plot_data(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = (
        "division",
        "figure",
        "method",
        "series",
        "point_order",
        "tau1_step",
        "tau2_step",
        "tau1_ms",
        "tau2_ms",
        "source_path",
        "source_sha256",
    )
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-csv", type=Path, default=DEFAULT_TARGET_CSV)
    parser.add_argument("--active-article-pdf", type=Path, default=DEFAULT_ACTIVE_PDF)
    parser.add_argument("--rebuilt-target-pdf", type=Path, default=DEFAULT_REBUILT_PDF)
    parser.add_argument("--history-dir", type=Path, default=DEFAULT_HISTORY_DIR)
    parser.add_argument(
        "--batch-summary",
        action="append",
        type=Path,
        default=[],
        help="可重复给出额外候选批次摘要；只从拓扑门ELIGIBLE候选中选择。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=CASE_ROOT / "figures" / "final_delivery",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    target_csv = args.target_csv.resolve()
    active_pdf = args.active_article_pdf.resolve()
    rebuilt_pdf = args.rebuilt_target_pdf.resolve()
    history_dir = args.history_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    for required in (target_csv, active_pdf, rebuilt_pdf):
        if not required.is_file():
            raise FileNotFoundError(required)
    if not history_dir.is_dir():
        raise FileNotFoundError(history_dir)
    active_hash = sha256(active_pdf)
    rebuilt_hash = sha256(rebuilt_pdf)
    if active_hash != rebuilt_hash:
        raise RuntimeError(
            "当前文章活跃PDF与论文矢量边界重建PDF并非逐字节相同，停止出图。"
        )

    selected, selected_batch = discover_selected_candidate(args.batch_summary)
    strict_summary_path = resolve_strict_summary(selected)
    strict_summary = load_json(strict_summary_path)
    strict_by_curve = {item["curve_id"]: item for item in strict_summary["curves"]}

    target = read_target(target_csv)
    history: dict[tuple[int, str], list[Point]] = {}
    calculation: dict[tuple[int, str], list[Point]] = {}
    source_paths: dict[tuple[str, int, str], Path] = {}
    for division in (1, 2):
        for method in METHODS:
            h_path = history_path(history_dir, division, method).resolve()
            c_path = candidate_boundary_path(strict_summary_path, division, method).resolve()
            if not h_path.is_file() or not c_path.is_file():
                raise FileNotFoundError(f"缺失边界文件：{h_path} 或 {c_path}")
            history[(division, method)] = read_step_boundary(h_path, "x_index", "y_index")
            calculation[(division, method)] = read_step_boundary(
                c_path, "tau1_step", "tau2_step"
            )
            source_paths[("history", division, method)] = h_path
            source_paths[("calculation", division, method)] = c_path

    configure_style()
    fig, axes = plt.subplots(
        3,
        2,
        figsize=(7.48, 6.25),
        sharex=True,
        sharey=True,
        constrained_layout=True,
    )
    target_style = dict(color="#222222", linestyle="-", linewidth=1.65, zorder=2)
    history_style = dict(
        color="#EE6677",
        linestyle="--",
        linewidth=1.15,
        marker="s",
        markevery=8,
        markerfacecolor="white",
        markeredgewidth=0.7,
        zorder=3,
    )
    calculation_style = dict(
        color="#4477AA",
        linestyle="-.",
        linewidth=1.25,
        marker="o",
        markevery=8,
        markerfacecolor="white",
        markeredgewidth=0.7,
        zorder=4,
    )
    panel_letter = ord("a")
    plot_rows: list[dict[str, Any]] = []
    for row_index, method in enumerate(METHODS):
        for column_index, division in enumerate((1, 2)):
            ax = axes[row_index, column_index]
            key = (division, method)
            ax.plot(*xy(target[key]), **target_style)
            ax.plot(*xy(history[key]), **history_style)
            ax.plot(*xy(calculation[key]), **calculation_style)
            ax.set_xlim(-3.0, 68.0)
            ax.set_ylim(-1.5, 32.5)
            ax.xaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.yaxis.set_major_locator(MaxNLocator(nbins=5, integer=True))
            ax.text(
                0.035,
                0.93,
                rf"({chr(panel_letter)}) {PANEL_NAMES[key]}",
                transform=ax.transAxes,
                ha="left",
                va="top",
            )
            panel_letter += 1
            if row_index == 2:
                ax.set_xlabel(r"Time delay $\tau_1$ (ms)")
            if column_index == 0:
                ax.set_ylabel(r"Time delay $\tau_2$ (ms)")

            append_rows(plot_rows, division, method, "THESIS_AND_ACTIVE_ARTICLE", target[key], target_csv)
            append_rows(
                plot_rows,
                division,
                method,
                "ARCHIVED_HISTORICAL_MAT",
                history[key],
                source_paths[("history", division, method)],
            )
            append_rows(
                plot_rows,
                division,
                method,
                "TARGET_GUIDED_CALIBRATION_CALCULATION",
                calculation[key],
                source_paths[("calculation", division, method)],
            )

    strict_pass_count = int(selected.get("strict_curve_pass_count", 0))
    handles = [
        Line2D([0], [0], label="Thesis / active article (identical)", **target_style),
        Line2D([0], [0], label="Archived MATLAB mask", **history_style),
        Line2D(
            [0],
            [0],
            label=rf"Selected calculation ({strict_pass_count}/6 exact)",
            **calculation_style,
        ),
    ]
    fig.legend(
        handles=handles,
        loc="outside upper center",
        ncol=3,
        handlelength=2.3,
        handletextpad=0.5,
        columnspacing=1.2,
    )

    stem = "图10_论文目标_历史候选_来源约束计算对比"
    pdf_path = output_dir / f"{stem}.pdf"
    png_path = output_dir / f"{stem}.png"
    data_path = output_dir / f"{stem}_逐点数据.csv"
    manifest_path = output_dir / f"{stem}_生成清单.json"
    metadata = {
        "Title": "Figure 10 target, archived mask, and source-constrained calculation comparison",
        "Author": "Codex for Doctor Bego",
        "Subject": "TARGET_GUIDED_CALIBRATION_CALCULATION_REPRODUCTION; STRICT_GATE_RETAINED",
        "Keywords": "Figure 10; stability domain; target-guided calibration; evidence boundary",
        "Creator": "generate_fig10_final_comparison.py",
    }
    fig.savefig(pdf_path, format="pdf", metadata=metadata, bbox_inches="tight", pad_inches=0.02)
    fig.savefig(
        png_path,
        format="png",
        dpi=600,
        metadata={"Software": "generate_fig10_final_comparison.py"},
        bbox_inches="tight",
        pad_inches=0.02,
        facecolor="white",
    )
    plt.close(fig)
    write_plot_data(data_path, plot_rows)

    curve_records = []
    for division in (1, 2):
        for method in METHODS:
            curve_id = f"division{division}_{METHOD_TO_ID[method]}"
            metric = strict_by_curve[curve_id]
            curve_records.append(
                {
                    "curve_id": curve_id,
                    "division": division,
                    "method": method,
                    "target_point_count": metric["target_point_count"],
                    "historical_point_count": len(history[(division, method)]),
                    "calculation_point_count": metric["candidate_point_count"],
                    "ordered_exact": metric["ordered_exact_original"],
                    "set_exact": metric["set_exact"],
                    "start_endpoint_exact": metric["start_endpoint_exact"],
                    "end_endpoint_exact": metric["end_endpoint_exact"],
                    "symmetric_hausdorff_steps": metric["symmetric_hausdorff_steps"],
                    "point_levenshtein_original": metric["point_levenshtein_original"],
                    "strict_curve_status": metric["strict_curve_status"],
                }
            )

    manifest = {
        "schema_version": "FIG10_FINAL_COMPARISON_V1",
        "status": "PASS_GENERATED_WITH_STRICT_FAILURE_DISCLOSED",
        "evidence_label": "目标引导的校准计算复现",
        "claim_boundary": (
            "当前文章活跃图件与硕士论文矢量目标逐字节一致；所选计算候选严格0/6，"
            "不是作者原始计算合同，也不是计算级精准命中。"
        ),
        "active_article_pdf": str(active_pdf),
        "active_article_pdf_sha256": active_hash,
        "rebuilt_target_pdf": str(rebuilt_pdf),
        "rebuilt_target_pdf_sha256": rebuilt_hash,
        "active_and_rebuilt_pdf_byte_identical": active_hash == rebuilt_hash,
        "target_csv": str(target_csv),
        "target_csv_sha256": sha256(target_csv),
        "selected_candidate": selected,
        "selected_candidate_batch": str(selected_batch),
        "selected_candidate_batch_sha256": sha256(selected_batch),
        "selected_strict_summary": str(strict_summary_path),
        "selected_strict_summary_sha256": sha256(strict_summary_path),
        "strict_overall_status": strict_summary["overall_status"],
        "strict_curve_pass_count": strict_pass_count,
        "curves": curve_records,
        "outputs": {
            "pdf": str(pdf_path),
            "pdf_sha256": sha256(pdf_path),
            "png": str(png_path),
            "png_sha256": sha256(png_path),
            "editable_csv": str(data_path),
            "editable_csv_sha256": sha256(data_path),
        },
    }
    write_json(manifest_path, manifest)
    manifest["outputs"]["manifest"] = str(manifest_path)
    manifest["outputs"]["manifest_sha256_before_self_reference"] = sha256(manifest_path)
    write_json(manifest_path, manifest)

    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

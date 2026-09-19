from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import html
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator, ScalarFormatter
from PIL import Image


SCRIPT = Path(__file__).resolve()
PACKAGE_ROOT = SCRIPT.parent.parent
DELIVERY_ROOT = PACKAGE_ROOT.parent
REPORT_PATH = DELIVERY_ROOT / "小论文Fig6至Fig10_全链路计算结果对比汇报.html"

REPO_ROOT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master")
BOARD18 = (
    REPO_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块18_图3-5至图3-15逐图计算复现"
)
BOARD20 = (
    REPO_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
)

FULLCHAIN_ROOT = PACKAGE_ROOT / "01_本轮全链新算结果"
CURRENT_ROOT = PACKAGE_ROOT / "02_当前结果基准"
FIGURE_ROOT = PACKAGE_ROOT / "03_对比图"
AUDIT_ROOT = PACKAGE_ROOT / "04_数值审计"

COLORS = {
    "Original": "#555555",
    "Craig-Bampton": "#EE6677",
    "Guyan": "#4477AA",
}
LINE_STYLES = {
    "Original": "--",
    "Craig-Bampton": "-",
    "Guyan": "-.",
}
MARKERS = {
    "Original": "o",
    "Craig-Bampton": "s",
    "Guyan": "^",
}
METHOD_COLUMNS = {
    "Original": 1,
    "Guyan": 2,
    "Craig-Bampton": 3,
}


@dataclass(frozen=True)
class ResponseSpec:
    figure_id: str
    description: str
    source_name: str
    current_folder: str
    output_stem: str
    thesis_mapping: str


RESPONSE_SPECS = (
    ResponseSpec(
        "Fig.6",
        "第一类划分，El Centro地震响应",
        "第一类划分_ElCentro地震响应.csv",
        "Fig06_第一类划分_ElCentro响应",
        "Fig06_全链新算_vs_当前结果",
        "硕士论文图3-6和图3-8",
    ),
    ResponseSpec(
        "Fig.7",
        "第二类划分，El Centro地震响应",
        "第二类划分_ElCentro地震响应.csv",
        "Fig07_第二类划分_ElCentro响应",
        "Fig07_全链新算_vs_当前结果",
        "硕士论文图3-9和图3-10",
    ),
    ResponseSpec(
        "Fig.8",
        "第一类划分，Chirp响应",
        "第一类划分_Chirp响应.csv",
        "Fig08_第一类划分_Chirp响应",
        "Fig08_全链新算_vs_当前结果",
        "硕士论文图3-11和图3-13",
    ),
    ResponseSpec(
        "Fig.9",
        "第二类划分，Chirp响应",
        "第二类划分_Chirp响应.csv",
        "Fig09_第二类划分_Chirp响应",
        "Fig09_全链新算_vs_当前结果",
        "硕士论文图3-14和图3-15的物理一致修正版",
    ),
)

CANDIDATE_DESCRIPTIONS = {
    "R01": "连续CARE，标量 alpha=0.25，广义力输入",
    "R02": "连续CARE，标量 alpha=0.25，加速度输入",
    "R03": "连续CARE，逐路线矩阵 al，广义力输入",
    "R04": "连续CARE，逐路线矩阵 al，加速度输入",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_csv(path: Path, fieldnames: Iterable[str], rows: Iterable[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames))
        writer.writeheader()
        writer.writerows(rows)


def copy_with_record(source: Path, destination: Path, records: list[dict[str, object]]) -> None:
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    source_hash = sha256_file(source)
    destination_hash = sha256_file(destination)
    if source_hash != destination_hash:
        raise RuntimeError(f"复制后哈希不一致：{source} -> {destination}")
    records.append(
        {
            "source_absolute_path": str(source),
            "local_relative_path": destination.relative_to(PACKAGE_ROOT).as_posix(),
            "size_bytes": destination.stat().st_size,
            "sha256": destination_hash,
        }
    )


def refresh_local_bundle() -> None:
    records: list[dict[str, object]] = []
    board18_data = BOARD18 / "outputs" / "adapted_run1" / "输入数据"
    board18_validation = BOARD18 / "outputs" / "adapted_run1" / "验证记录"
    for spec in RESPONSE_SPECS:
        copy_with_record(
            board18_data / spec.source_name,
            FULLCHAIN_ROOT / "Fig06至Fig09_响应" / spec.source_name,
            records,
        )
        copy_with_record(
            DELIVERY_ROOT / spec.current_folder / "输入数据" / spec.source_name,
            CURRENT_ROOT / "Fig06至Fig09_响应" / spec.source_name,
            records,
        )
    for name in (
        "第3章仿真响应数值统计.csv",
        "第3章生成数据_SHA256.csv",
        "再生第3章真实仿真数据_日志.txt",
    ):
        copy_with_record(
            board18_validation / name,
            FULLCHAIN_ROOT / "Fig06至Fig09_运行证据" / name,
            records,
        )

    step8e_matlab = BOARD20 / "outputs" / "step8e_四候选全网格" / "matlab"
    for name in (
        "MATLAB全网格逐点摘要.csv",
        "MATLAB步骤8E摘要.json",
        "MATLAB步骤8E运行日志.txt",
        "MATLAB边界证书.csv",
        "MATLAB候选准入门禁.csv",
    ):
        copy_with_record(
            step8e_matlab / name,
            FULLCHAIN_ROOT / "Fig10_全网格计算" / name,
            records,
        )

    candidate_source = (
        BOARD20
        / "outputs"
        / "step8f_计算候选与论文目标裁决"
        / "data"
        / "候选MATLAB边界"
    )
    candidate_files = sorted(candidate_source.glob("*.csv"))
    if len(candidate_files) != 24:
        raise RuntimeError(f"Fig.10计算边界应为24份，实际为{len(candidate_files)}份")
    for source in candidate_files:
        copy_with_record(
            source,
            FULLCHAIN_ROOT / "Fig10_四候选计算边界" / source.name,
            records,
        )

    target_source = (
        BOARD20
        / "outputs"
        / "step8f_论文矢量边界逐点复刻"
        / "data"
    )
    target_files = sorted(target_source.glob("图4-*_论文矢量边界.csv"))
    if len(target_files) != 6:
        raise RuntimeError(f"Fig.10论文目标应为6份，实际为{len(target_files)}份")
    for source in target_files:
        copy_with_record(
            source,
            CURRENT_ROOT / "Fig10_论文386点目标" / source.name,
            records,
        )

    adjudication = (
        BOARD20
        / "outputs"
        / "step8f_计算候选与论文目标裁决"
        / "裁决证据"
    )
    for name in (
        "步骤8F计算候选裁决摘要.json",
        "六条目标最近诊断候选.csv",
        "24候选与六条论文目标逐项裁决.csv",
        "4行同候选六曲线全局裁决.csv",
    ):
        copy_with_record(
            adjudication / name,
            AUDIT_ROOT / "Fig10_既有独立裁决证据" / name,
            records,
        )

    write_csv(
        AUDIT_ROOT / "本轮对比数据来源与SHA256.csv",
        ("source_absolute_path", "local_relative_path", "size_bytes", "sha256"),
        records,
    )


def configure_plotting() -> None:
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
            "axes.linewidth": 0.8,
            "lines.linewidth": 1.2,
            "legend.frameon": False,
            "axes.grid": False,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.03,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def response_paths(spec: ResponseSpec) -> tuple[Path, Path]:
    return (
        FULLCHAIN_ROOT / "Fig06至Fig09_响应" / spec.source_name,
        CURRENT_ROOT / "Fig06至Fig09_响应" / spec.source_name,
    )


def load_response_csv(path: Path) -> np.ndarray:
    values = np.loadtxt(path, delimiter=",", skiprows=1, encoding="utf-8-sig")
    if values.shape != (40961, 10):
        raise RuntimeError(f"{path.name}尺寸不是40961x10：{values.shape}")
    if not np.isfinite(values).all():
        raise RuntimeError(f"{path.name}含NaN或Inf")
    expected_time = np.arange(40961, dtype=float) / 1024.0
    if not np.allclose(values[:, 0], expected_time, rtol=0.0, atol=1e-14):
        raise RuntimeError(f"{path.name}时间向量不满足0--40 s、dt=1/1024 s")
    return values


def response_column_name(column_index: int) -> str:
    if column_index == 0:
        return "时间_s"
    floor = (column_index - 1) // 3 + 1
    method = ("Original", "Guyan", "Craig-Bampton")[(column_index - 1) % 3]
    return f"{floor}层_{method}"


def draw_response_comparison(
    spec: ResponseSpec,
    fullchain: np.ndarray,
    current: np.ndarray,
) -> dict[str, Path]:
    output_pdf = FIGURE_ROOT / "PDF" / f"{spec.output_stem}.pdf"
    output_png = FIGURE_ROOT / "PNG_600dpi" / f"{spec.output_stem}.png"
    output_web = FIGURE_ROOT / "HTML内嵌图" / f"{spec.output_stem}_web.png"
    for parent in (output_pdf.parent, output_png.parent, output_web.parent):
        parent.mkdir(parents=True, exist_ok=True)

    time = fullchain[:, 0]
    fig, axes = plt.subplots(2, 2, figsize=(7.48, 5.15), sharex="col")
    plot_stride = 4
    marker_indices = np.unique(np.linspace(0, len(time) - 1, 13).round().astype(int))
    floors = ((1, 1), (3, 7))
    panels = ("(a)", "(b)", "(c)", "(d)")

    for col, (floor, first_column) in enumerate(floors):
        top = axes[0, col]
        residual = axes[1, col]
        for method in ("Original", "Craig-Bampton", "Guyan"):
            column = first_column + METHOD_COLUMNS[method] - 1
            top.plot(
                time[::plot_stride],
                fullchain[::plot_stride, column],
                color=COLORS[method],
                linestyle=LINE_STYLES[method],
                linewidth=0.9,
                zorder=2,
            )
            top.plot(
                time[marker_indices],
                current[marker_indices, column],
                linestyle="none",
                marker=MARKERS[method],
                markersize=3.4,
                markerfacecolor="white",
                markeredgewidth=0.8,
                markeredgecolor=COLORS[method],
                zorder=3,
            )
            delta = fullchain[:, column] - current[:, column]
            residual.plot(
                time[::plot_stride],
                delta[::plot_stride],
                color=COLORS[method],
                linestyle=LINE_STYLES[method],
                linewidth=1.0,
            )

        top.text(
            0.02,
            0.95,
            panels[col],
            transform=top.transAxes,
            va="top",
            fontweight="bold",
        )
        top.text(
            0.98,
            0.95,
            rf"Floor {floor}",
            transform=top.transAxes,
            ha="right",
            va="top",
        )
        top.set_ylabel(r"Displacement (mm)" if col == 0 else "")
        top.set_xlim(0.0, 40.0)
        top.xaxis.set_major_locator(MaxNLocator(5))
        top.yaxis.set_major_locator(MaxNLocator(5))

        residual.axhline(0.0, color="#BBBBBB", linewidth=0.6, zorder=0)
        residual.set_ylim(-1.0e-12, 1.0e-12)
        residual.set_xlabel(r"Time (s)")
        residual.set_ylabel(r"Difference (mm)" if col == 0 else "")
        residual.text(
            0.02,
            0.92,
            panels[col + 2],
            transform=residual.transAxes,
            va="top",
            fontweight="bold",
        )
        residual.text(
            0.98,
            0.92,
            r"$max |Delta|=0$",
            transform=residual.transAxes,
            ha="right",
            va="top",
        )
        formatter = ScalarFormatter(useMathText=True)
        formatter.set_powerlimits((-2, 2))
        residual.yaxis.set_major_formatter(formatter)
        residual.yaxis.set_major_locator(MaxNLocator(3))

    method_handles = [
        Line2D(
            [0],
            [0],
            color=COLORS[method],
            linestyle=LINE_STYLES[method],
            linewidth=1.2,
            label=method,
        )
        for method in ("Original", "Craig-Bampton", "Guyan")
    ]
    source_handles = [
        Line2D([0], [0], color="black", linestyle="-", linewidth=1.0, label="Full-chain recalculation"),
        Line2D(
            [0],
            [0],
            color="black",
            linestyle="none",
            marker="o",
            markerfacecolor="white",
            markersize=3.8,
            label="Current data",
        ),
    ]
    fig.legend(
        handles=method_handles + source_handles,
        loc="upper center",
        ncol=5,
        bbox_to_anchor=(0.5, 1.01),
        handlelength=1.8,
        columnspacing=1.0,
    )
    fig.subplots_adjust(left=0.095, right=0.985, bottom=0.095, top=0.91, wspace=0.16, hspace=0.15)
    fig.savefig(output_pdf)
    fig.savefig(output_png, dpi=600)
    fig.savefig(output_web, dpi=180)
    plt.close(fig)
    return {"pdf": output_pdf, "png": output_png, "web": output_web}


def candidate_boundary_path(figure: str, method: str, candidate: str) -> Path:
    token = method
    return (
        FULLCHAIN_ROOT
        / "Fig10_四候选计算边界"
        / f"候选_图{figure}_{token}_{candidate}_MATLAB可见开边界.csv"
    )


def target_boundary_path(figure: str, method: str) -> Path:
    token = {"Original": "Original", "Craig-Bampton": "CB", "Guyan": "Guyan"}[method]
    return CURRENT_ROOT / "Fig10_论文386点目标" / f"图{figure}_{token}_论文矢量边界.csv"


def read_integer_path(path: Path, x_name: str, y_name: str) -> np.ndarray:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    if not rows:
        raise RuntimeError(f"边界为空：{path}")
    orders = [int(row["point_order"]) for row in rows]
    if orders != list(range(1, len(rows) + 1)):
        raise RuntimeError(f"point_order不连续：{path}")
    return np.asarray([[int(row[x_name]), int(row[y_name])] for row in rows], dtype=int)


def draw_fig10_comparison() -> tuple[dict[str, Path], list[dict[str, object]], list[dict[str, object]]]:
    output_pdf = FIGURE_ROOT / "PDF" / "Fig10_四候选全链计算_vs_论文目标.pdf"
    output_png = FIGURE_ROOT / "PNG_600dpi" / "Fig10_四候选全链计算_vs_论文目标.png"
    output_web = FIGURE_ROOT / "HTML内嵌图" / "Fig10_四候选全链计算_vs_论文目标_web.png"
    for parent in (output_pdf.parent, output_png.parent, output_web.parent):
        parent.mkdir(parents=True, exist_ok=True)

    dt_ms = 1000.0 / 1024.0
    fig, axes = plt.subplots(2, 4, figsize=(7.48, 5.35), sharex=True, sharey=True)
    exact_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    panel_index = 0

    for row, (figure, division_name) in enumerate((("4-4", "Division I"), ("4-5", "Division II"))):
        for col, candidate in enumerate(("R01", "R02", "R03", "R04")):
            ax = axes[row, col]
            match_count = 0
            for method in ("Original", "Craig-Bampton", "Guyan"):
                calc_path = candidate_boundary_path(figure, method, candidate)
                target_path = target_boundary_path(figure, method)
                calc = read_integer_path(calc_path, "x_index", "y_index")
                target = read_integer_path(target_path, "tau1_step", "tau2_step")
                exact = calc.shape == target.shape and np.array_equal(calc, target)
                match_count += int(exact)
                exact_rows.append(
                    {
                        "figure": f"图{figure}",
                        "division": division_name,
                        "candidate": candidate,
                        "method": method,
                        "calculated_point_count": len(calc),
                        "target_point_count": len(target),
                        "ordered_path_exact_match": int(exact),
                    }
                )

                calc_ms = (calc - 1) * dt_ms
                target_ms = (target - 1) * dt_ms
                ax.plot(
                    calc_ms[:, 0],
                    calc_ms[:, 1],
                    color=COLORS[method],
                    linestyle="--",
                    linewidth=1.0,
                    zorder=2,
                )
                target_marker_indices = np.unique(
                    np.linspace(0, len(target_ms) - 1, min(7, len(target_ms))).round().astype(int)
                )
                ax.plot(
                    target_ms[:, 0],
                    target_ms[:, 1],
                    color=COLORS[method],
                    linestyle="-",
                    linewidth=1.0,
                    marker=MARKERS[method],
                    markevery=target_marker_indices.tolist(),
                    markersize=2.8,
                    markerfacecolor="white",
                    markeredgewidth=0.6,
                    zorder=3,
                )

            candidate_rows.append(
                {
                    "candidate": candidate,
                    "figure": f"图{figure}",
                    "division": division_name,
                    "exact_matches": match_count,
                    "total_methods": 3,
                    "status": "FAIL" if match_count < 3 else "PASS",
                }
            )
            panel_label = f"({chr(ord('a') + panel_index)})"
            panel_index += 1
            ax.text(0.02, 0.97, panel_label, transform=ax.transAxes, va="top", fontweight="bold")
            ax.text(0.98, 0.97, candidate, transform=ax.transAxes, ha="right", va="top")
            ax.set_xlim(0.0, 66.0)
            ax.set_ylim(0.0, 31.0)
            ax.xaxis.set_major_locator(MaxNLocator(4))
            ax.yaxis.set_major_locator(MaxNLocator(4))
            if row == 1:
                ax.set_xlabel(r"Delay $\tau_1$ (ms)")
            if col == 0:
                ax.set_ylabel(division_name + "\n" + r"Delay $\tau_2$ (ms)")

    method_handles = [
        Line2D([0], [0], color=COLORS[method], linewidth=1.2, label=method)
        for method in ("Original", "Craig-Bampton", "Guyan")
    ]
    source_handles = [
        Line2D([0], [0], color="black", linestyle="--", linewidth=1.0, label="Full-chain candidate"),
        Line2D(
            [0],
            [0],
            color="black",
            linestyle="-",
            marker="o",
            markerfacecolor="white",
            markersize=3.0,
            label="Paper target",
        ),
    ]
    fig.legend(
        handles=method_handles + source_handles,
        loc="upper center",
        ncol=5,
        bbox_to_anchor=(0.5, 1.005),
        handlelength=1.7,
        columnspacing=0.9,
    )
    fig.subplots_adjust(left=0.09, right=0.99, bottom=0.095, top=0.91, wspace=0.12, hspace=0.15)
    fig.savefig(output_pdf)
    fig.savefig(output_png, dpi=600)
    fig.savefig(output_web, dpi=180)
    plt.close(fig)
    return {"pdf": output_pdf, "png": output_png, "web": output_web}, exact_rows, candidate_rows


def image_data_uri(path: Path) -> tuple[str, int, int]:
    raw = path.read_bytes()
    with Image.open(path) as image:
        width, height = image.size
    return "data:image/png;base64," + base64.b64encode(raw).decode("ascii"), width, height


def format_number(value: float) -> str:
    if value == 0.0:
        return "0"
    return f"{value:.6e}"


def html_table(headers: list[str], rows: list[list[str]]) -> str:
    head = "".join(f"<th>{html.escape(value)}</th>" for value in headers)
    body = "".join(
        "<tr>" + "".join(f"<td>{html.escape(value)}</td>" for value in row) + "</tr>"
        for row in rows
    )
    return f'<div class="table-wrap"><table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>'


def generate_html(
    response_results: list[dict[str, object]],
    response_figures: dict[str, dict[str, Path]],
    fig10_figure: dict[str, Path],
    candidate_rows: list[dict[str, object]],
    step8e_summary: dict[str, object],
) -> None:
    embedded: dict[str, tuple[str, int, int]] = {}
    for item in response_results:
        figure_id = str(item["figure_id"])
        embedded[figure_id] = image_data_uri(response_figures[figure_id]["web"])
    embedded["Fig.10"] = image_data_uri(fig10_figure["web"])

    response_table = html_table(
        ["小论文图", "全链计算对象", "数据点", "最大绝对差", "文件SHA-256", "结论"],
        [
            [
                str(item["figure_id"]),
                str(item["description"]),
                "40,961 × 10",
                format_number(float(item["maximum_absolute_difference"])),
                "完全相同" if item["sha256_equal"] else "不同",
                "计算级复现通过" if float(item["maximum_absolute_difference"]) == 0.0 else "需要复核",
            ]
            for item in response_results
        ],
    )
    candidate_table = html_table(
        ["候选", "合同含义", "图4-4命中", "图4-5命中", "六条合计", "结论"],
        [
            [
                candidate,
                CANDIDATE_DESCRIPTIONS[candidate],
                f"{sum(int(row['exact_matches']) for row in candidate_rows if row['candidate'] == candidate and row['figure'] == '图4-4')}/3",
                f"{sum(int(row['exact_matches']) for row in candidate_rows if row['candidate'] == candidate and row['figure'] == '图4-5')}/3",
                f"{sum(int(row['exact_matches']) for row in candidate_rows if row['candidate'] == candidate)}/6",
                "未复现论文边界",
            ]
            for candidate in ("R01", "R02", "R03", "R04")
        ],
    )
    mapping_table = html_table(
        ["图", "完整计算入口", "计算链输出", "当前结果", "本轮判断"],
        [
            [
                "Fig.6",
                "run_board18_adapted.m；第一类El Centro",
                "第一类划分_ElCentro地震响应.csv",
                "Fig06目录中的同名CSV",
                "逐字节相同",
            ],
            [
                "Fig.7",
                "run_board18_adapted.m；第二类El Centro",
                "第二类划分_ElCentro地震响应.csv",
                "Fig07目录中的同名CSV",
                "逐字节相同",
            ],
            [
                "Fig.8",
                "run_board18_adapted.m；第一类Chirp",
                "第一类划分_Chirp响应.csv",
                "Fig08目录中的同名CSV",
                "逐字节相同",
            ],
            [
                "Fig.9",
                "run_board18_adapted.m；第二类Chirp",
                "第二类划分_Chirp响应.csv",
                "Fig09目录中的同名CSV",
                "逐字节相同；采用物理一致Chirp局部窗",
            ],
            [
                "Fig.10",
                "build_board20_step8c_routes_matlab.m → run_board20_step8e_fullgrid_matlab('full') → bwboundaries",
                "24组31×67稳定掩膜与24条候选边界",
                "论文PDF提取的六条边界、共386点",
                "计算链通过；论文边界0/6命中",
            ],
        ],
    )

    figure_cards: list[str] = []
    for item in response_results:
        figure_id = str(item["figure_id"])
        uri, width, height = embedded[figure_id]
        figure_cards.append(
            f"""
            <article class="figure-card print-page">
              <div class="figure-head"><span class="tag pass">PASS</span><h3>{figure_id}：{html.escape(str(item['description']))}</h3></div>
              <img src="{uri}" width="{width}" height="{height}" alt="{figure_id}全链新算响应与当前结果叠加及残差对比图">
              <p>上排：全链新算曲线与当前结果空心标记叠加。下排：全链新算值减当前值。六个用于小论文的一层/三层方法列最大绝对差均为 <strong>0 mm</strong>；整份40961×10 CSV也逐字节一致。</p>
            </article>
            """
        )
    uri, width, height = embedded["Fig.10"]
    figure_cards.append(
        f"""
        <article class="figure-card print-page">
          <div class="figure-head"><span class="tag fail">0/6</span><h3>Fig.10：四种全链计算合同与论文目标</h3></div>
          <img src="{uri}" width="{width}" height="{height}" alt="Fig10两类划分四种计算候选与论文386点目标的八面板对比图">
          <p>虚线是模型与控制器算出的候选边界，带空心标记的实线是论文PDF中的目标边界。R01至R04对六条目标均为0/6命中。R02、R04的边界主要沿扫描框外缘，是“整个31×67扫描范围内稳定”，不能解释为找到了论文中的有限临界边界。</p>
        </article>
        """
    )

    css = """
    :root{--ink:#18212b;--muted:#5c6874;--paper:#f6f7f9;--card:#fff;--line:#dce1e6;--blue:#4477AA;--red:#B64A58;--green:#24704a;--amber:#8a6417}
    *{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font-family:"Segoe UI","Microsoft YaHei",sans-serif;line-height:1.72}
    header{background:linear-gradient(135deg,#17212b,#26394c);color:white;padding:46px 24px 34px}header .wrap{max-width:1160px;margin:auto}h1{font-size:clamp(28px,4vw,48px);line-height:1.18;margin:0 0 14px}header p{max-width:900px;margin:0;color:#e6edf3;font-size:17px}
    nav{position:sticky;top:0;z-index:5;background:#fff;border-bottom:1px solid var(--line);overflow-x:auto;white-space:nowrap}nav .wrap{max-width:1160px;margin:auto;display:flex}nav a{color:#314253;text-decoration:none;padding:12px 14px;font-size:14px}nav a:hover{background:#eef3f7}
    main{max-width:1160px;margin:auto;padding:28px 20px 72px}section{scroll-margin-top:58px;margin:0 0 28px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:28px;box-shadow:0 5px 20px rgba(30,45,60,.04)}h2{font-size:25px;margin:0 0 16px}h3{font-size:18px;margin:0}p{margin:10px 0}.lead{font-size:18px}.small{font-size:13px;color:var(--muted)}
    .grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}.metric{border:1px solid var(--line);border-radius:12px;padding:18px;background:#fbfcfd}.metric strong{display:block;font-size:27px;line-height:1.2}.metric span{color:var(--muted);font-size:14px}.metric.pass strong{color:var(--green)}.metric.fail strong{color:var(--red)}
    .callout{border-left:5px solid var(--blue);background:#eef4f8;padding:14px 16px;border-radius:8px;margin:16px 0}.callout.warn{border-color:#d39a25;background:#fff8e8}.callout.fail{border-color:var(--red);background:#fff0f2}
    .table-wrap{overflow-x:auto;margin:16px 0;border:1px solid var(--line);border-radius:10px}table{border-collapse:collapse;width:100%;min-width:760px;font-size:14px}th,td{padding:10px 12px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{background:#eef2f5;white-space:nowrap}tbody tr:last-child td{border-bottom:0}
    .figure-card{border:1px solid var(--line);border-radius:12px;padding:18px;margin:18px 0;background:#fff}.figure-card img{display:block;width:100%;height:auto;max-height:720px;object-fit:contain;margin:14px auto}.figure-head{display:flex;align-items:center;gap:10px}.tag{display:inline-block;padding:3px 9px;border-radius:999px;font-weight:700;font-size:12px;white-space:nowrap}.tag.pass{background:#e5f5eb;color:#1f6d43}.tag.fail{background:#fde7ea;color:#9d3543}
    code{font-family:Consolas,"Courier New",monospace;background:#f0f2f4;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}.flow{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;align-items:stretch}.flow div{padding:13px 10px;border:1px solid var(--line);border-radius:9px;text-align:center;background:#fafbfc}.flow div+div:before{content:"→";float:left;margin-left:-19px;color:#82909e}
    details{border:1px solid var(--line);border-radius:9px;padding:11px 13px;margin:10px 0}summary{cursor:pointer;font-weight:650}.status-list li{margin:8px 0}
    footer{max-width:1160px;margin:0 auto 50px;padding:0 20px;color:var(--muted);font-size:13px}
    @media (max-width:850px){main{padding:18px 12px 48px}section{padding:20px 16px}.grid{grid-template-columns:1fr}.flow{grid-template-columns:1fr}.flow div+div:before{content:"↓";float:none;display:block;margin:-20px 0 5px}.figure-head{align-items:flex-start}.figure-card{padding:12px}}
    @page{size:A4;margin:13mm}
    @media print{body{background:#fff;font-size:10.5pt}header{padding:18mm 10mm 12mm}nav{display:none}main{max-width:none;padding:0}section{box-shadow:none;border:0;border-radius:0;padding:6mm 0;margin:0;break-inside:auto}.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.print-page{break-before:page;break-inside:avoid-page;border:0;padding:0;margin:0}.figure-card img{max-height:190mm}.table-wrap{overflow:visible}table{min-width:0;font-size:8.5pt}th,td{padding:5px 6px}details{break-inside:avoid}footer{margin:8mm 0 0;padding:0}}
    """

    point_count = int(step8e_summary["point_count"])
    root_count = int(step8e_summary["total_physical_root_count"])
    stable_count = int(step8e_summary["stable_point_count"])
    unstable_count = int(step8e_summary["unstable_point_count"])
    report = rf"""<!doctype html>
<html lang="zh-CN">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>小论文Fig6至Fig10全链路计算结果对比汇报</title><style>{css}</style></head>
<body>
<header><div class="wrap"><h1>小论文 Fig.6–Fig.10<br>全链路计算结果对比汇报</h1><p>本报告回答一个单一问题：从模型和参数真正重新计算得到的结果，与 <code>260817\code</code> 中“现在的结果”是否相同。结论分成第三章响应图和第四章稳定域图两类，不能混为一谈。</p></div></header>
<nav><div class="wrap"><a href="#summary">结论</a><a href="#scope">比较对象</a><a href="#chain">运行链</a><a href="#results">逐图对比</a><a href="#fig10">Fig.10判读</a><a href="#mapping">代码映射</a><a href="#validation">验证</a><a href="#boundary">证据边界</a><a href="#action">下一步</a></div></nav>
<main>
<section id="summary">
  <h2>先说结论</h2>
  <p class="lead"><strong>Fig.6–Fig.9已经稳定实现计算级复现；Fig.10的计算链也能稳定运行，但没有复现出论文中的六条稳定边界。</strong></p>
  <div class="grid">
    <div class="metric pass"><strong>4 / 4</strong><span>Fig.6–Fig.9全链新算与当前数据逐字节相同</span></div>
    <div class="metric pass"><strong>{point_count:,}</strong><span>Fig.10本轮重新计算的时滞网格点</span></div>
    <div class="metric fail"><strong>0 / 6</strong><span>R01–R04任一候选对论文六条边界的完整命中</span></div>
  </div>
  <div class="callout"><strong>这次纠正了什么：</strong>旧HTML只汇报了“读取CSV/论文边界后重画”。那份包能证明画图没有走样，却没有回答您问的“计算链算出来什么”。本报告从已完成的板块18和板块20计算链出发，把新算结果与当前结果正面对比。</div>
  <p><strong>当前是否需要您操作：</strong>不需要。若只判断小论文Fig.6–Fig.9是否由完整计算链支持，答案是“是”；若要在论文中声称Fig.10六条边界已经计算级复现，答案仍是“不能”。</p>
</section>

<section id="scope">
  <h2>比较对象与判定规则</h2>
  <p>“全链新算结果”是本轮实际运行第三章Simulink链和第四章双时滞谱半径链得到的派生数据；“当前结果”是 <code>260817\code</code> 中Fig.6–Fig.10绘图包使用的数据。Fig.6–Fig.9当前CSV可以逐点比较；Fig.10当前数据是论文PDF提取的386个目标点，因此比较的是“计算候选边界是否等于论文目标”。</p>
  {response_table}
  <div class="callout warn"><strong>判定不降标：</strong>计算程序能跑通不自动等于论文曲线复现成功。Fig.10必须同时满足模型链可执行、数值求解稳定、论文六条边界匹配；本轮只通过前两项。</div>
</section>

<section id="chain">
  <h2>本轮实际运行了什么</h2>
  <h3>Fig.6–Fig.9响应链</h3>
  <div class="flow"><div>冻结参数与15自由度矩阵</div><div>两类自由度划分</div><div>Guyan / Craig–Bampton缩聚</div><div>Simulink固定步长 ode4</div><div>三层物理响应CSV</div></div>
  <p>入口为 <code>run_board18_adapted.m</code>。采样步长为1/1024 s，计算0–40 s；两类划分分别使用修复后的作者模型副本。当前四份结果CSV没有作为计算输入，只在计算结束后参与哈希与逐点验收。</p>
  <h3>Fig.10稳定域链</h3>
  <div class="flow"><div>六个15/6/9或15/5/8维模型</div><div>连续CARE与四种来源合同</div><div>双时滞最小增广矩阵</div><div>31×67网格全部特征根</div><div>谱半径稳定掩膜与边界</div></div>
  <p>入口为 <code>run_board20_step8e_fullgrid_matlab('full')</code>。本轮得到 {point_count:,} 个网格点、{root_count:,} 个物理特征根，其中稳定点 {stable_count:,} 个、不稳定点 {unstable_count:,} 个、临界点0个；全部点状态为PASS。计算阶段没有读取论文PDF、386点目标、历史稳定掩膜或 <code>lqr_2.mat/lqr_3.mat</code>。</p>
</section>

<section id="results">
  <h2>逐图图像对比</h2>
  <p>Fig.6–Fig.9上排使用“全链新算曲线 + 当前数据空心标记”；下排画逐点残差。Fig.10使用八个面板展示两类划分下的R01–R04，不挑最像的一条冒充答案。</p>
  {''.join(figure_cards)}
</section>

<section id="fig10">
  <h2>为什么Fig.10不能宣布成功</h2>
  {candidate_table}
  <p>论文和现存代码没有留下唯一的LQR/输入积分合同。R01–R04是四种有证据支持、公式自洽的补全方式；它们都通过49,848点全网格求解，却都没有同时命中Original、Craig–Bampton、Guyan在两类划分下的六条目标边界。</p>
  <details><summary>R02和R04为什么像一个外框</summary><p>这两种合同在当前31×67扫描网格内的2077/2077点全部稳定。<code>bwboundaries</code>提取到的是扫描框边缘，意思是“稳定域至少延伸到扫描上限”，不是论文中的有限临界时滞。</p></details>
  <details><summary>这是否说明计算代码错了</summary><p>不能这样下结论。MATLAB与独立Python求解器此前在49,848个点上的稳定分类完全一致，最大谱半径差为8.0602×10⁻14。当前更准确的结论是：计算实现稳定，但梁禹当年的唯一历史合同没有从现存材料中恢复出来。</p></details>
</section>

<section id="mapping">
  <h2>每张图对应哪个完整计算代码</h2>
  {mapping_table}
  <p class="small">比较图本身由本包 <code>code\生成全链路对比图与汇报.py</code> 从已封存的本轮计算输出生成；默认运行只读本包相对路径中的数据，不依赖原工程路径。使用 <code>--refresh-data</code> 才会从权威板块重新收集最新全链输出。</p>
</section>

<section id="validation">
  <h2>本轮验证结果</h2>
  <ul class="status-list">
    <li><strong>第三章真实运行：</strong>MATLAB R2025b退出码0；五个工况全部生成，四个小论文响应CSV各40961×10。</li>
    <li><strong>Fig.6–Fig.9数值门：</strong>四对文件SHA-256完全相同；所有元素最大绝对差为0；小论文使用的一层/三层六列最大绝对差也为0。</li>
    <li><strong>第四章真实运行：</strong>MATLAB全网格退出码0；{point_count:,}/{point_count:,}点PASS，{root_count:,}个根完成；本轮点摘要SHA-256与既有验证版相同。</li>
    <li><strong>Fig.10目标门：</strong>24条计算候选边界逐条与六条论文有序路径比较；R01、R02、R03、R04均为0/6。</li>
    <li><strong>绘图门：</strong>五份PDF为矢量输出，五份PNG为600 dpi；方法颜色、线型、坐标起点和点序合同一致。</li>
  </ul>
  <details><summary>本包中的审计文件</summary><p><code>04_数值审计\Fig06至Fig09逐列对比.csv</code>记录40列逐列误差；<code>04_数值审计\Fig10_24条候选逐路径精确匹配.csv</code>记录24条边界的点数和精确命中；<code>04_数值审计\本轮对比数据来源与SHA256.csv</code>记录所有权威来源与本地副本哈希。</p></details>
</section>

<section id="boundary">
  <h2>证据边界和仍然未知的内容</h2>
  <ul class="status-list">
    <li><strong>Fig.6–Fig.9已证明：</strong>现存参数、代码和必要适配可稳定重新生成当前结果，因此属于“计算级复现（现存代码/必要适配路线）”。</li>
    <li><strong>Fig.6–Fig.9未证明：</strong>梁禹当年保存的原始40961点工作区数组尚未找到，所以“作者历史逐点值”仍是待决定。</li>
    <li><strong>Fig.10已证明：</strong>六模型链、四种合同、双时滞谱半径和边界提取能从源矩阵完整运行并通过双求解器数值验证。</li>
    <li><strong>Fig.10未证明：</strong>哪一种合同就是梁禹当年使用的唯一合同；现有四种合同没有一项复现论文六条边界。</li>
    <li><strong>特别说明：</strong>板块21中305,382条能量记录、1,096条结果和19/19验证属于表4-1，不是Fig.10证据，本报告没有混用。</li>
  </ul>
</section>

<section id="action">
  <h2>下一步怎么处理</h2>
  <p><strong>现在可以做：</strong>把Fig.6–Fig.9的交付说明从“绘图级重排”纠正为“计算级复现通过”，并把板块18全链入口纳入正式代码包。Fig.10应继续标注为“全链实现通过、论文边界计算复现未通过”。</p>
  <p><strong>若继续追Fig.10：</strong>只需要追查缺失的历史LQR权重、反馈时滞位置、输入量纲或积分合同；不应再通过调参挑一条最像的曲线。验收标准保持六条有序路径逐条命中，而不是视觉大致相似。</p>
  <p><strong>本轮主汇报文件：</strong><code>小论文Fig6至Fig10_全链路计算结果对比汇报.html</code>。旧的 <code>小论文案例分析Fig6至Fig10_复现汇报.html</code>保留为绘图包验收历史，不再作为回答“完整计算链是否复现”的主证据。</p>
</section>
</main>
<footer>生成日期：2026-09-01。报告为独立单文件HTML，正文、CSS和五张必要对比图全部内嵌；不依赖网络、在线字体或旁置图片。</footer>
</body></html>"""
    REPORT_PATH.write_text(report, encoding="utf-8")


def write_readme(step8e_summary: dict[str, object]) -> None:
    readme = rf"""# 全链路计算结果对比

## 结论

- Fig.6--Fig.9：本轮真实Simulink全链新算与当前四份CSV逐字节相同，属于现存代码/必要适配路线的计算级复现。
- Fig.10：六模型链×四候选的{int(step8e_summary['point_count']):,}点全网格计算通过，但R01--R04对论文六条边界均为0/6命中。

## 本包如何独立重画比较图

在任意当前目录运行：

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'D:\\Software\\python\\python.exe' '本文件夹\\code\\生成全链路对比图与汇报.py'
```

默认模式只读取本文件夹内的相对路径数据，不依赖原仓库。`--refresh-data`只用于原仓库仍在本机时重新收集权威全链输出。

## 完整计算链入口

### Fig.6--Fig.9

```powershell
$env:BOARD18_RUN_ID='run1'
& 'D:\\Downlad\\Matlab\\bin\\matlab.exe' -batch "run('D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master/test/00_失败尝试与候选路线/板块18_图3-5至图3-15逐图计算复现/code/run_board18_adapted.m')"
```

### Fig.10

```powershell
& 'D:\\Downlad\\Matlab\\bin\\matlab.exe' -batch "addpath('D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master/test/00_失败尝试与候选路线/板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现/code'); run_board20_step8e_fullgrid_matlab('full');"
```

完整计算入口需要原板块冻结输入；比较图入口不需要。
"""
    (PACKAGE_ROOT / "README_从这里开始.md").write_text(readme, encoding="utf-8")


def write_manifest() -> None:
    manifest_path = AUDIT_ROOT / "本轮交付文件清单.csv"
    validation_report_path = AUDIT_ROOT / "全链路对比汇报静态验收.txt"
    files = sorted(
        path
        for path in PACKAGE_ROOT.rglob("*")
        if path.is_file() and path not in {manifest_path, validation_report_path}
    )
    rows = [
        {
            "relative_path": path.relative_to(PACKAGE_ROOT).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in files
    ]
    write_csv(manifest_path, ("relative_path", "size_bytes", "sha256"), rows)


def run(refresh_data: bool) -> None:
    for folder in (FULLCHAIN_ROOT, CURRENT_ROOT, FIGURE_ROOT, AUDIT_ROOT):
        folder.mkdir(parents=True, exist_ok=True)
    if refresh_data or not (AUDIT_ROOT / "本轮对比数据来源与SHA256.csv").is_file():
        refresh_local_bundle()

    configure_plotting()
    response_results: list[dict[str, object]] = []
    response_figures: dict[str, dict[str, Path]] = {}
    column_rows: list[dict[str, object]] = []
    for spec in RESPONSE_SPECS:
        full_path, current_path = response_paths(spec)
        fullchain = load_response_csv(full_path)
        current = load_response_csv(current_path)
        difference = fullchain - current
        full_hash = sha256_file(full_path)
        current_hash = sha256_file(current_path)
        result = {
            "figure_id": spec.figure_id,
            "description": spec.description,
            "thesis_mapping": spec.thesis_mapping,
            "row_count": fullchain.shape[0],
            "column_count": fullchain.shape[1],
            "maximum_absolute_difference": float(np.max(np.abs(difference))),
            "rmse_all": float(np.sqrt(np.mean(difference**2))),
            "fullchain_sha256": full_hash,
            "current_sha256": current_hash,
            "sha256_equal": full_hash == current_hash,
        }
        response_results.append(result)
        for column in range(10):
            delta = difference[:, column]
            column_rows.append(
                {
                    "figure_id": spec.figure_id,
                    "column_index_1based": column + 1,
                    "column_name": response_column_name(column),
                    "maximum_absolute_difference": float(np.max(np.abs(delta))),
                    "rmse": float(np.sqrt(np.mean(delta**2))),
                    "exact_elementwise_equal": int(np.array_equal(fullchain[:, column], current[:, column])),
                }
            )
        response_figures[spec.figure_id] = draw_response_comparison(spec, fullchain, current)

    write_csv(
        AUDIT_ROOT / "Fig06至Fig09逐列对比.csv",
        (
            "figure_id",
            "column_index_1based",
            "column_name",
            "maximum_absolute_difference",
            "rmse",
            "exact_elementwise_equal",
        ),
        column_rows,
    )
    write_csv(
        AUDIT_ROOT / "Fig06至Fig09文件级对比.csv",
        tuple(response_results[0].keys()),
        response_results,
    )

    fig10_figure, exact_rows, candidate_rows = draw_fig10_comparison()
    write_csv(
        AUDIT_ROOT / "Fig10_24条候选逐路径精确匹配.csv",
        tuple(exact_rows[0].keys()),
        exact_rows,
    )
    write_csv(
        AUDIT_ROOT / "Fig10_8面板命中汇总.csv",
        tuple(candidate_rows[0].keys()),
        candidate_rows,
    )

    step8e_summary_path = FULLCHAIN_ROOT / "Fig10_全网格计算" / "MATLAB步骤8E摘要.json"
    step8e_summary = json.loads(step8e_summary_path.read_text(encoding="utf-8"))
    if int(step8e_summary["point_count"]) != 49848 or not bool(step8e_summary["all_points_pass"]):
        raise RuntimeError("Fig.10全网格摘要未满足49,848点全部PASS")
    if any(float(item["maximum_absolute_difference"]) != 0.0 for item in response_results):
        raise RuntimeError("Fig.6--Fig.9存在非零差值")
    if any(int(row["exact_matches"]) != 0 for row in candidate_rows):
        raise RuntimeError("Fig.10候选命中状态与既有0/6裁决不一致")

    generate_html(response_results, response_figures, fig10_figure, candidate_rows, step8e_summary)
    write_readme(step8e_summary)
    write_manifest()
    print("STATUS=PASS")
    print(f"REPORT={REPORT_PATH}")
    print(f"PACKAGE={PACKAGE_ROOT}")
    print("FIG6_TO_FIG9_MAX_ABS=0")
    print("FIG10_CANDIDATE_TARGET_MATCH=0/6_FOR_R01_R02_R03_R04")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成Fig.6--Fig.10全链新算与当前结果对比图及独立HTML")
    parser.add_argument(
        "--refresh-data",
        action="store_true",
        help="从权威板块和当前绘图包重新复制本轮全链输出与当前基准；默认只读本包本地数据",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    run(args.refresh_data)

from __future__ import annotations

"""
板块20步骤8F：四个来源候选与论文图4-4/图4-5目标的数据裁决与绘图。

证据边界：
1. 候选稳定性只读取已冻结步骤8E Python逐点 CSV 的 stable 字段；
   不导入生成器，不重算特征值，不修改求解器或输入。
2. 候选边界必须由 MATLAB
   bwboundaries(M, 8, 'noholes') 的 B{1} 生成，再按 x=column、y=row
   映射并删除 x<=1 或 y<=1 的闭合边界部分。
3. 论文 PDF 只提供可见开边界，无法唯一恢复 31x67 完整掩膜。
   四条缩聚曲线的完整掩膜裁决固定为
   NOT_EVALUABLE_MISSING_SOURCE_MASK。
4. 仅两条 Original 的历史 MAT 边界与论文开边界一致，因此只有它们可作为
   31x67 完整掩膜主门。四条缩聚历史掩膜只报告诊断性 Hamming/IoU。

默认或 --data-only 只生成数据与裁决证据，严禁生成 PDF/PNG。
只有显式 --render 才会额外生成 4 份矢量 PDF 和 4 份 600 dpi PNG。
"""

import argparse
import csv
import hashlib
import json
import math
import os
import subprocess
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.io import loadmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step8f_计算候选与论文目标裁决"
DATA_ROOT = OUTPUT_ROOT / "data"
MASK_ROOT = DATA_ROOT / "候选稳定掩膜31x67"
CANDIDATE_BOUNDARY_ROOT = DATA_ROOT / "候选MATLAB边界"
HISTORY_MASK_ROOT = DATA_ROOT / "历史稳定掩膜31x67"
HISTORY_BOUNDARY_ROOT = DATA_ROOT / "历史MATLAB边界"
ADJUDICATION_ROOT = OUTPUT_ROOT / "裁决证据"
FIGURE_ROOT = OUTPUT_ROOT / "figures"

STEP8E_POINTS = (
    BOARD_ROOT
    / "outputs"
    / "step8e_四候选全网格"
    / "python"
    / "步骤8E_Python全网格逐点结果.csv"
)
PDF_VECTOR_ROOT = BOARD_ROOT / "outputs" / "step8f_论文矢量边界逐点复刻" / "data"
HISTORY_ROOT = (
    BOARD_ROOT
    / "input"
    / "plotting_baseline"
    / "第4章_缩聚对试验稳定性的影响"
    / "原始来源副本"
)
HISTORY_FILES = {
    1: HISTORY_ROOT / "第一类划分最终绘图数据_lqr_2.mat",
    2: HISTORY_ROOT / "第二类划分最终绘图数据_lqr_3.mat",
}
MATLAB_EXE = Path(r"D:\Downlad\Matlab\bin\matlab.exe")

N_L = 31
N_J = 67
DT_MS = 1000.0 / 1024.0
CANDIDATES = ("R01", "R02", "R03", "R04")
CANDIDATE_PANEL_LABELS = {
    "R01": r"R01: $\alpha=0.25$, generalized force",
    "R02": r"R02: $\alpha=0.25$, acceleration",
    "R03": r"R03: matrix $a_l$, generalized force",
    "R04": r"R04: matrix $a_l$, acceleration",
}
METHODS = ("Original", "CB", "Guyan")
STEP8E_METHOD_TO_CANONICAL = {
    "Original": "Original",
    "Craig_Bampton": "CB",
    "Guyan": "Guyan",
}
METHOD_TO_MAT = {"Original": "stab_o", "CB": "stab_C", "Guyan": "stab_g"}
METHOD_TO_CN = {
    "Original": "原结构",
    "CB": "Craig-Bampton",
    "Guyan": "Guyan",
}
FIGURE_ID = {1: "4-4", 2: "4-5"}


@dataclass(frozen=True)
class GroupKey:
    division: int
    method: str
    candidate_id: str


@dataclass
class GroupData:
    key: GroupKey
    candidate_name: str
    route: str
    dimension: int
    mask: np.ndarray


@dataclass(frozen=True)
class TargetPath:
    division: int
    method: str
    source_file: Path
    points: tuple[tuple[int, int], ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )


def write_rows(
    path: Path,
    fieldnames: Sequence[str],
    rows: Iterable[dict[str, Any]],
    *,
    utf8_bom: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoding = "utf-8-sig" if utf8_bom else "utf-8"
    with path.open("w", encoding=encoding, newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def save_binary_mask(path: Path, mask: np.ndarray) -> None:
    if mask.shape != (N_L, N_J):
        raise ValueError(f"掩膜尺寸错误：{path.name}: {mask.shape}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="ascii", newline="") as stream:
        writer = csv.writer(stream, lineterminator="\n")
        writer.writerows(mask.astype(np.uint8).tolist())


def rel_to_board(path: Path) -> str:
    return path.resolve().relative_to(BOARD_ROOT.resolve()).as_posix()


def require_inputs() -> None:
    required = [STEP8E_POINTS, MATLAB_EXE, *HISTORY_FILES.values()]
    for division in (1, 2):
        for method in METHODS:
            required.append(
                PDF_VECTOR_ROOT
                / f"图{FIGURE_ID[division]}_{method}_论文矢量边界.csv"
            )
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("缺少冻结输入：\n" + "\n".join(missing))


def parse_int01(value: str, *, field: str, point_key: str) -> bool:
    if value not in {"0", "1"}:
        raise ValueError(f"{point_key}: {field} 必须是0/1，实际={value!r}")
    return value == "1"


def load_candidate_groups() -> dict[GroupKey, GroupData]:
    groups: dict[GroupKey, GroupData] = {}
    seen_cells: dict[GroupKey, set[tuple[int, int]]] = defaultdict(set)
    row_count = 0
    with STEP8E_POINTS.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required_fields = {
            "point_key",
            "division",
            "method",
            "candidate_id",
            "candidate_name",
            "route",
            "dimension",
            "l_samples",
            "j_samples",
            "stable",
            "overall_pass",
        }
        missing = sorted(required_fields - set(reader.fieldnames or []))
        if missing:
            raise ValueError(f"步骤8E逐点CSV缺字段：{missing}")
        for row in reader:
            row_count += 1
            point_key = row["point_key"]
            division = int(row["division"])
            source_method = row["method"]
            if source_method not in STEP8E_METHOD_TO_CANONICAL:
                raise ValueError(f"{point_key}: 未知步骤8E方法名{source_method!r}")
            method = STEP8E_METHOD_TO_CANONICAL[source_method]
            candidate_id = row["candidate_id"]
            if division not in (1, 2) or method not in METHODS or candidate_id not in CANDIDATES:
                raise ValueError(f"{point_key}: 路线或候选身份不在冻结合同内")
            key = GroupKey(division, method, candidate_id)
            if key not in groups:
                groups[key] = GroupData(
                    key=key,
                    candidate_name=row["candidate_name"],
                    route=row["route"],
                    dimension=int(row["dimension"]),
                    mask=np.full((N_L, N_J), 255, dtype=np.uint8),
                )
            group = groups[key]
            if (
                group.candidate_name != row["candidate_name"]
                or group.route != row["route"]
                or group.dimension != int(row["dimension"])
            ):
                raise ValueError(f"{point_key}: 组内元数据不一致")
            l_value = int(row["l_samples"])
            j_value = int(row["j_samples"])
            if not (0 <= l_value < N_L and 0 <= j_value < N_J):
                raise ValueError(f"{point_key}: (l,j)=({l_value},{j_value})超出31x67合同")
            cell = (l_value, j_value)
            if cell in seen_cells[key]:
                raise ValueError(f"{point_key}: 重复网格点{cell}")
            seen_cells[key].add(cell)
            overall_pass = parse_int01(row["overall_pass"], field="overall_pass", point_key=point_key)
            if not overall_pass:
                raise ValueError(f"{point_key}: 步骤8E逐点门未通过")
            group.mask[l_value, j_value] = int(
                parse_int01(row["stable"], field="stable", point_key=point_key)
            )

    expected_keys = {
        GroupKey(division, method, candidate_id)
        for division in (1, 2)
        for method in METHODS
        for candidate_id in CANDIDATES
    }
    if set(groups) != expected_keys:
        raise ValueError(
            f"候选组合不完整：actual={len(groups)}, expected={len(expected_keys)}"
        )
    if row_count != len(expected_keys) * N_L * N_J:
        raise ValueError(f"逐点行数错误：actual={row_count}, expected=49848")
    for key, group in groups.items():
        if len(seen_cells[key]) != N_L * N_J or np.any(group.mask == 255):
            raise ValueError(f"{key}: 31x67网格不完整")
    return groups


def load_targets() -> dict[tuple[int, str], TargetPath]:
    targets: dict[tuple[int, str], TargetPath] = {}
    for division in (1, 2):
        for method in METHODS:
            source = (
                PDF_VECTOR_ROOT
                / f"图{FIGURE_ID[division]}_{method}_论文矢量边界.csv"
            )
            rows = read_rows(source)
            orders = [int(row["point_order"]) for row in rows]
            if orders != list(range(1, len(rows) + 1)):
                raise ValueError(f"{source.name}: point_order不连续")
            points = tuple(
                (int(row["tau1_step"]), int(row["tau2_step"])) for row in rows
            )
            if any(x <= 1 or y <= 1 for x, y in points):
                raise ValueError(f"{source.name}: 论文开边界含 x<=1 或 y<=1 点")
            if len(points) != len(set(points)):
                raise ValueError(f"{source.name}: 论文开边界含重复点")
            targets[(division, method)] = TargetPath(division, method, source, points)
    return targets


def load_history_masks() -> dict[tuple[int, str], np.ndarray]:
    result: dict[tuple[int, str], np.ndarray] = {}
    for division, source in HISTORY_FILES.items():
        raw = loadmat(source, squeeze_me=False, struct_as_record=False)
        for method, variable in METHOD_TO_MAT.items():
            if variable not in raw:
                raise KeyError(f"{source.name}: 缺少{variable}")
            values = np.asarray(raw[variable], dtype=float)
            if values.shape[0] < N_L or values.shape[1] < N_J:
                raise ValueError(f"{source.name}/{variable}: 不足31x67，实际{values.shape}")
            common = values[:N_L, :N_J]
            result[(division, method)] = (
                np.isfinite(common) & (common > 0.0) & (common < 1.0)
            )
    return result


def method_file_token(method: str) -> str:
    return {"Original": "Original", "CB": "Craig-Bampton", "Guyan": "Guyan"}[method]


def prepare_masks_and_matlab_jobs(
    groups: dict[GroupKey, GroupData],
    history_masks: dict[tuple[int, str], np.ndarray],
) -> tuple[list[dict[str, Any]], dict[str, Path], dict[str, Path]]:
    for folder in (
        MASK_ROOT,
        CANDIDATE_BOUNDARY_ROOT,
        HISTORY_MASK_ROOT,
        HISTORY_BOUNDARY_ROOT,
        ADJUDICATION_ROOT,
    ):
        folder.mkdir(parents=True, exist_ok=True)

    jobs: list[dict[str, Any]] = []
    mask_paths: dict[str, Path] = {}
    boundary_paths: dict[str, Path] = {}
    for key in sorted(groups, key=lambda value: (value.division, METHODS.index(value.method), value.candidate_id)):
        figure = FIGURE_ID[key.division]
        token = method_file_token(key.method)
        item_id = f"C_D{key.division}_{key.method}_{key.candidate_id}"
        mask_path = MASK_ROOT / f"候选_图{figure}_{token}_{key.candidate_id}_稳定掩膜31x67.csv"
        boundary_path = (
            CANDIDATE_BOUNDARY_ROOT
            / f"候选_图{figure}_{token}_{key.candidate_id}_MATLAB可见开边界.csv"
        )
        save_binary_mask(mask_path, groups[key].mask.astype(bool))
        mask_paths[item_id] = mask_path
        boundary_paths[item_id] = boundary_path
        jobs.append(
            {
                "item_id": item_id,
                "item_kind": "candidate",
                "division": key.division,
                "method": key.method,
                "candidate_id": key.candidate_id,
                "mask_file": str(mask_path.resolve()),
                "boundary_file": str(boundary_path.resolve()),
            }
        )

    for division in (1, 2):
        for method in METHODS:
            figure = FIGURE_ID[division]
            token = method_file_token(method)
            item_id = f"H_D{division}_{method}"
            mask_path = HISTORY_MASK_ROOT / f"历史_图{figure}_{token}_共同网格稳定掩膜31x67.csv"
            boundary_path = (
                HISTORY_BOUNDARY_ROOT
                / f"历史_图{figure}_{token}_MATLAB可见开边界.csv"
            )
            save_binary_mask(mask_path, history_masks[(division, method)])
            mask_paths[item_id] = mask_path
            boundary_paths[item_id] = boundary_path
            jobs.append(
                {
                    "item_id": item_id,
                    "item_kind": "history",
                    "division": division,
                    "method": method,
                    "candidate_id": "",
                    "mask_file": str(mask_path.resolve()),
                    "boundary_file": str(boundary_path.resolve()),
                }
            )
    return jobs, mask_paths, boundary_paths


def matlab_quote(path: Path) -> str:
    return str(path.resolve()).replace("'", "''").replace("\\", "/")


def run_matlab_bwboundaries(jobs: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    jobs_path = ADJUDICATION_ROOT / "MATLAB_bwboundaries任务表.csv"
    stats_path = ADJUDICATION_ROOT / "MATLAB_bwboundaries结构检查.csv"
    log_path = ADJUDICATION_ROOT / "MATLAB_bwboundaries运行日志.txt"
    write_rows(
        jobs_path,
        (
            "item_id",
            "item_kind",
            "division",
            "method",
            "candidate_id",
            "mask_file",
            "boundary_file",
        ),
        jobs,
        utf8_bom=False,
    )
    command = (
        "close all force; set(groot,'DefaultFigureVisible','off'); "
        f"jobs=readtable('{matlab_quote(jobs_path)}','TextType','string','Encoding','UTF-8',"
        "'Delimiter',',','ReadVariableNames',true,'VariableNamingRule','preserve'); "
        "n=height(jobs); item_id=strings(n,1); component_count=zeros(n,1); "
        "hole_pixel_count=zeros(n,1); returned_boundary_count=zeros(n,1); "
        "full_boundary_point_count=zeros(n,1); visible_path_point_count=zeros(n,1); "
        "for q=1:n; "
        "item_id(q)=jobs.item_id(q); M=logical(readmatrix(jobs.mask_file(q))); "
        f"if ~isequal(size(M),[{N_L},{N_J}]); error('MASK_SIZE:%s',item_id(q)); end; "
        "CC=bwconncomp(M,8); component_count(q)=CC.NumObjects; "
        "hole_pixel_count(q)=nnz(imfill(M,'holes') & ~M); "
        "B=bwboundaries(M,8,'noholes'); returned_boundary_count(q)=numel(B); "
        "if isempty(B); error('EMPTY_BOUNDARY:%s',item_id(q)); end; "
        "p=[B{1}(:,2),B{1}(:,1)]; full_boundary_point_count(q)=size(p,1); "
        "p=p(p(:,1)>1 & p(:,2)>1,:); visible_path_point_count(q)=size(p,1); "
        "T=table((1:size(p,1))',p(:,1),p(:,2),'VariableNames',"
        "{'point_order','x_index','y_index'}); "
        "writetable(T,jobs.boundary_file(q),'Encoding','UTF-8'); end; "
        "S=table(item_id,component_count,hole_pixel_count,returned_boundary_count,"
        "full_boundary_point_count,visible_path_point_count); "
        f"writetable(S,'{matlab_quote(stats_path)}','Encoding','UTF-8'); "
        "fprintf('STEP8F_BWBOUNDARIES_DONE items=%d\\n',n);"
    )
    completed = subprocess.run(
        [str(MATLAB_EXE), "-batch", command],
        cwd=str(BOARD_ROOT),
        text=True,
        encoding="utf-8",
        errors="replace",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    log_path.write_text(completed.stdout, encoding="utf-8")
    if completed.returncode != 0:
        raise RuntimeError(
            f"MATLAB bwboundaries失败，returncode={completed.returncode}\n{completed.stdout}"
        )
    stats_rows = read_rows(stats_path)
    if len(stats_rows) != len(jobs):
        raise ValueError(
            f"MATLAB结构检查行数错误：{len(stats_rows)} != {len(jobs)}"
        )
    stats = {row["item_id"]: row for row in stats_rows}
    if set(stats) != {str(job["item_id"]) for job in jobs}:
        raise ValueError("MATLAB结构检查item_id与任务表不一致")
    return stats


def read_matlab_path(path: Path) -> tuple[tuple[int, int], ...]:
    rows = read_rows(path)
    orders = [int(row["point_order"]) for row in rows]
    if orders != list(range(1, len(rows) + 1)):
        raise ValueError(f"{path.name}: MATLAB边界point_order不连续")
    return tuple((int(row["x_index"]), int(row["y_index"])) for row in rows)


def exact_sequences(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> tuple[bool, bool, bool]:
    original = tuple(candidate) == tuple(target)
    reversed_exact = tuple(candidate) == tuple(reversed(target))
    return original, reversed_exact, original or reversed_exact


def symmetric_hausdorff(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> float:
    a = np.asarray(candidate, dtype=float)
    b = np.asarray(target, dtype=float)
    if a.size == 0 or b.size == 0:
        return math.inf
    squared = np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)
    directed_ab = float(np.sqrt(np.min(squared, axis=1)).max())
    directed_ba = float(np.sqrt(np.min(squared, axis=0)).max())
    return max(directed_ab, directed_ba)


def endpoint_abs_difference(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> tuple[int, str]:
    if not candidate or not target:
        return 10**9, "EMPTY"
    c0 = np.asarray(candidate[0], dtype=int)
    c1 = np.asarray(candidate[-1], dtype=int)
    t0 = np.asarray(target[0], dtype=int)
    t1 = np.asarray(target[-1], dtype=int)
    forward = int(np.abs(c0 - t0).sum() + np.abs(c1 - t1).sum())
    reverse = int(np.abs(c0 - t1).sum() + np.abs(c1 - t0).sum())
    return (forward, "ORIGINAL") if forward <= reverse else (reverse, "REVERSED")


def ordered_path_edit_distance_one_direction(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> int:
    """Levenshtein距离：点级插入/删除/替换的代价均为1。"""
    previous = list(range(len(target) + 1))
    for candidate_index, candidate_point in enumerate(candidate, start=1):
        current = [candidate_index]
        for target_index, target_point in enumerate(target, start=1):
            substitution = 0 if candidate_point == target_point else 1
            current.append(
                min(
                    current[-1] + 1,
                    previous[target_index] + 1,
                    previous[target_index - 1] + substitution,
                )
            )
        previous = current
    return int(previous[-1])


def ordered_path_edit_distance(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> tuple[int, int, int, str]:
    original = ordered_path_edit_distance_one_direction(candidate, target)
    reversed_value = ordered_path_edit_distance_one_direction(candidate, tuple(reversed(target)))
    if original <= reversed_value:
        return original, original, reversed_value, "ORIGINAL"
    return reversed_value, original, reversed_value, "REVERSED"


def rightmost_absolute_difference(
    candidate_x: int,
    candidate_y: Sequence[int],
    target_x: int,
    target_y: Sequence[int],
) -> int:
    """最右可见列的固定整数距离：x绝对差+该列y集合对称差点数。"""
    return int(abs(candidate_x - target_x) + len(set(candidate_y) ^ set(target_y)))


def visible_area_proxy(points: Sequence[tuple[int, int]]) -> int:
    """开边界的非唯一面积代理：对每个可见y取max(x-1)再求和。"""
    per_y: dict[int, int] = {}
    for x_value, y_value in points:
        per_y[y_value] = max(per_y.get(y_value, 0), x_value - 1)
    return int(sum(per_y.values()))


def sorted_rightmost_y(points: Sequence[tuple[int, int]]) -> tuple[int, tuple[int, ...]]:
    if not points:
        return -1, ()
    xmax = max(x for x, _ in points)
    ys = tuple(sorted({y for x, y in points if x == xmax}))
    return xmax, ys


def stable_rightmost(mask: np.ndarray) -> tuple[int, int, tuple[int, ...]]:
    columns = np.flatnonzero(mask.any(axis=0))
    if columns.size == 0:
        return -1, -1, ()
    j0 = int(columns[-1])
    visible_y = tuple(int(row + 1) for row in np.flatnonzero(mask[:, j0]) if row + 1 > 1)
    return j0, j0 + 1, visible_y


def set_coverage(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> dict[str, Any]:
    candidate_set = set(candidate)
    target_set = set(target)
    target_covered = len(target_set & candidate_set)
    candidate_covered = len(candidate_set & target_set)
    return {
        "paper_unique_point_count": len(target_set),
        "candidate_unique_point_count": len(candidate_set),
        "paper_points_covered_count": target_covered,
        "paper_points_covered_fraction": target_covered / len(target_set) if target_set else 0.0,
        "candidate_points_covered_count": candidate_covered,
        "candidate_points_covered_fraction": candidate_covered / len(candidate_set) if candidate_set else 0.0,
        "point_set_exact": candidate_set == target_set,
    }


def iou_and_hamming(candidate: np.ndarray, history: np.ndarray) -> tuple[int, float, int, int]:
    xor = int(np.count_nonzero(candidate ^ history))
    intersection = int(np.count_nonzero(candidate & history))
    union = int(np.count_nonzero(candidate | history))
    iou = float(intersection / union) if union else 1.0
    return xor, iou, intersection, union


def adjudicate(
    groups: dict[GroupKey, GroupData],
    targets: dict[tuple[int, str], TargetPath],
    history_masks: dict[tuple[int, str], np.ndarray],
    jobs: list[dict[str, Any]],
    boundary_paths: dict[str, Path],
    matlab_stats: dict[str, dict[str, Any]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, Any],
    dict[GroupKey, tuple[tuple[int, int], ...]],
]:
    candidate_paths: dict[GroupKey, tuple[tuple[int, int], ...]] = {}
    history_paths: dict[tuple[int, str], tuple[tuple[int, int], ...]] = {}
    structural_failures: list[str] = []
    for job in jobs:
        item_id = str(job["item_id"])
        stat = matlab_stats[item_id]
        component_count = int(stat["component_count"])
        hole_pixel_count = int(stat["hole_pixel_count"])
        returned_boundary_count = int(stat["returned_boundary_count"])
        if component_count != 1 or hole_pixel_count != 0 or returned_boundary_count != 1:
            structural_failures.append(
                f"{item_id}: components={component_count}, holes={hole_pixel_count}, "
                f"boundaries={returned_boundary_count}"
            )
        points = read_matlab_path(boundary_paths[item_id])
        if job["item_kind"] == "candidate":
            key = GroupKey(int(job["division"]), str(job["method"]), str(job["candidate_id"]))
            candidate_paths[key] = points
        else:
            history_paths[(int(job["division"]), str(job["method"]))] = points

    history_target_consistency: dict[tuple[int, str], dict[str, Any]] = {}
    for division in (1, 2):
        for method in METHODS:
            history_path = history_paths[(division, method)]
            target = targets[(division, method)].points
            original, reversed_exact, allowed = exact_sequences(history_path, target)
            hx, hys = sorted_rightmost_y(history_path)
            tx, tys = sorted_rightmost_y(target)
            history_target_consistency[(division, method)] = {
                "sequence_exact_original_order": original,
                "sequence_exact_reversed_order": reversed_exact,
                "sequence_exact_allow_whole_reverse": allowed,
                "rightmost_x_exact": hx == tx,
                "rightmost_all_y_exact": hys == tys,
                "history_rightmost_x": hx,
                "history_rightmost_y": ";".join(map(str, hys)),
                "paper_rightmost_x": tx,
                "paper_rightmost_y": ";".join(map(str, tys)),
            }

    for division in (1, 2):
        original_consistency = history_target_consistency[(division, "Original")]
        if not (
            original_consistency["sequence_exact_allow_whole_reverse"]
            and original_consistency["rightmost_x_exact"]
            and original_consistency["rightmost_all_y_exact"]
        ):
            raise ValueError(f"图{FIGURE_ID[division]} Original历史掩膜边界与论文开边界不一致")
        for method in ("CB", "Guyan"):
            if history_target_consistency[(division, method)]["sequence_exact_allow_whole_reverse"]:
                raise ValueError(
                    f"图{FIGURE_ID[division]} {method}历史边界意外与论文完全一致，"
                    "与冻结证据合同冲突"
                )

    metrics: list[dict[str, Any]] = []
    for key in sorted(groups, key=lambda value: (value.division, METHODS.index(value.method), value.candidate_id)):
        group = groups[key]
        mask = group.mask.astype(bool)
        candidate = candidate_paths[key]
        target = targets[(key.division, key.method)].points
        history = history_masks[(key.division, key.method)]
        consistency = history_target_consistency[(key.division, key.method)]
        item_id = f"C_D{key.division}_{key.method}_{key.candidate_id}"
        stat = matlab_stats[item_id]

        original_exact, reversed_exact, path_exact = exact_sequences(candidate, target)
        edit_distance, edit_original, edit_reversed, edit_orientation = ordered_path_edit_distance(
            candidate, target
        )
        hausdorff = symmetric_hausdorff(candidate, target)
        endpoint_diff, endpoint_orientation = endpoint_abs_difference(candidate, target)
        coverage = set_coverage(candidate, target)
        candidate_x, candidate_path_y = sorted_rightmost_y(candidate)
        paper_x, paper_y = sorted_rightmost_y(target)
        stable_j0, stable_visible_x, stable_visible_y = stable_rightmost(mask)
        rightmost_x_exact = candidate_x == paper_x
        rightmost_y_exact = candidate_path_y == paper_y
        rightmost_difference = rightmost_absolute_difference(
            candidate_x, candidate_path_y, paper_x, paper_y
        )
        rightmost_x_abs_difference = abs(candidate_x - paper_x)
        rightmost_y_symmetric_difference_count = len(
            set(candidate_path_y) ^ set(paper_y)
        )
        mask_rightmost_x_exact_diagnostic = stable_visible_x == paper_x
        mask_rightmost_y_exact_diagnostic = stable_visible_y == paper_y
        xor_count, historical_iou, intersection, union = iou_and_hamming(mask, history)
        candidate_stable_count = int(mask.sum())
        historical_stable_count = int(history.sum())
        stable_count_difference = abs(candidate_stable_count - historical_stable_count)

        candidate_structure_pass = (
            int(stat["component_count"]) == 1
            and int(stat["hole_pixel_count"]) == 0
            and int(stat["returned_boundary_count"]) == 1
        )
        pdf_path_pass = (
            candidate_structure_pass
            and path_exact
            and rightmost_x_exact
            and rightmost_y_exact
        )
        if key.method == "Original":
            full_mask_status = (
                "PASS_AUTHOR_SOURCE_MASK_EXACT"
                if xor_count == 0 and historical_iou == 1.0
                else "FAIL_AUTHOR_SOURCE_MASK_MISMATCH"
            )
            complete_exact = pdf_path_pass and full_mask_status == "PASS_AUTHOR_SOURCE_MASK_EXACT"
            reproduction_status = (
                "PASS_COMPLETE_CALCULATION_REPRODUCTION"
                if complete_exact
                else "FAIL_CALCULATION_REPRODUCTION"
            )
            mask_authority = "AUTHOR_SOURCE_MASK_CONSISTENT_WITH_PDF"
            authoritative_stable_count: int | str = historical_stable_count
            authoritative_hamming: int | str = xor_count
            authoritative_iou: float | str = historical_iou
        else:
            full_mask_status = "NOT_EVALUABLE_MISSING_SOURCE_MASK"
            complete_exact = False
            reproduction_status = (
                "NOT_EVALUABLE_MISSING_SOURCE_MASK"
                if pdf_path_pass
                else "FAIL_VISIBLE_PATH_MISMATCH_AND_MISSING_SOURCE_MASK"
            )
            mask_authority = "DIAGNOSTIC_ONLY_HISTORY_MASK_CONFLICTS_WITH_PDF"
            authoritative_stable_count = "NA"
            authoritative_hamming = "NA"
            authoritative_iou = "NA"

        row: dict[str, Any] = {
            "figure_id": f"图{FIGURE_ID[key.division]}",
            "division": key.division,
            "method": key.method,
            "method_cn": METHOD_TO_CN[key.method],
            "candidate_id": key.candidate_id,
            "candidate_name": group.candidate_name,
            "route": group.route,
            "dimension": group.dimension,
            "candidate_stable_count": candidate_stable_count,
            "candidate_mask_rightmost_stable_j_zero_based_diagnostic": stable_j0,
            "candidate_mask_rightmost_visible_x_one_based_diagnostic": stable_visible_x,
            "candidate_mask_rightmost_all_visible_y_one_based_diagnostic": ";".join(map(str, stable_visible_y)),
            "candidate_matlab_path_rightmost_x_one_based": candidate_x,
            "candidate_matlab_path_rightmost_all_y_one_based": ";".join(map(str, candidate_path_y)),
            "candidate_mask_rightmost_x_matches_pdf_diagnostic": mask_rightmost_x_exact_diagnostic,
            "candidate_mask_rightmost_all_y_matches_pdf_diagnostic": mask_rightmost_y_exact_diagnostic,
            "candidate_visible_path_point_count": len(candidate),
            "paper_visible_path_point_count": len(target),
            "paper_rightmost_j_zero_based": paper_x - 1,
            "paper_rightmost_visible_x_one_based": paper_x,
            "paper_rightmost_all_y_one_based": ";".join(map(str, paper_y)),
            "matlab_8_connected_component_count": int(stat["component_count"]),
            "matlab_hole_pixel_count": int(stat["hole_pixel_count"]),
            "matlab_returned_boundary_count": int(stat["returned_boundary_count"]),
            "matlab_full_boundary_point_count": int(stat["full_boundary_point_count"]),
            "pdf_sequence_exact_original_order": original_exact,
            "pdf_sequence_exact_reversed_order": reversed_exact,
            "pdf_sequence_exact_allow_whole_reverse": path_exact,
            "pdf_ordered_path_edit_distance_allow_whole_reverse": edit_distance,
            "pdf_ordered_path_edit_distance_original_order": edit_original,
            "pdf_ordered_path_edit_distance_reversed_order": edit_reversed,
            "pdf_ordered_path_edit_distance_best_orientation": edit_orientation,
            "pdf_rightmost_x_exact": rightmost_x_exact,
            "pdf_rightmost_all_y_exact": rightmost_y_exact,
            "pdf_rightmost_absolute_difference_index_units": rightmost_difference,
            "pdf_rightmost_x_absolute_difference_index_units": rightmost_x_abs_difference,
            "pdf_rightmost_y_set_symmetric_difference_count": rightmost_y_symmetric_difference_count,
            "symmetric_hausdorff_index_units": hausdorff,
            "endpoint_absolute_difference_index_units": endpoint_diff,
            "endpoint_best_orientation": endpoint_orientation,
            "candidate_visible_area_proxy": visible_area_proxy(candidate),
            "paper_visible_area_proxy": visible_area_proxy(target),
            "visible_area_proxy_absolute_difference": abs(
                visible_area_proxy(candidate) - visible_area_proxy(target)
            ),
            "history_mask_authority": mask_authority,
            "history_pdf_sequence_exact_allow_whole_reverse": consistency[
                "sequence_exact_allow_whole_reverse"
            ],
            "historical_stable_count_diagnostic": historical_stable_count,
            "stable_count_absolute_difference_to_history_diagnostic": stable_count_difference,
            "historical_mask_hamming_xor_diagnostic": xor_count,
            "historical_mask_iou_diagnostic": historical_iou,
            "historical_mask_intersection_diagnostic": intersection,
            "historical_mask_union_diagnostic": union,
            "authoritative_source_mask_stable_count": authoritative_stable_count,
            "authoritative_source_mask_hamming_xor": authoritative_hamming,
            "authoritative_source_mask_iou": authoritative_iou,
            "candidate_boundary_structure_gate": "PASS" if candidate_structure_pass else "FAIL",
            "pdf_visible_path_gate": "PASS" if pdf_path_pass else "FAIL",
            "full_mask_gate": full_mask_status,
            "complete_reproduction_exact": complete_exact,
            "complete_reproduction_status": reproduction_status,
        }
        row.update(coverage)
        metrics.append(row)

    nearest: list[dict[str, Any]] = []
    for division in (1, 2):
        for method in METHODS:
            subset = [
                row
                for row in metrics
                if row["division"] == division and row["method"] == method
            ]
            winner = min(
                subset,
                key=lambda row: (
                    0 if row["pdf_sequence_exact_allow_whole_reverse"] else 1,
                    int(row["pdf_ordered_path_edit_distance_allow_whole_reverse"]),
                    float(row["symmetric_hausdorff_index_units"]),
                    int(row["pdf_rightmost_x_absolute_difference_index_units"]),
                    int(row["pdf_rightmost_y_set_symmetric_difference_count"]),
                    str(row["candidate_id"]),
                ),
            )
            nearest.append(
                {
                    "figure_id": winner["figure_id"],
                    "division": division,
                    "method": method,
                    "method_cn": METHOD_TO_CN[method],
                    "nearest_diagnostic_candidate": winner["candidate_id"],
                    "selection_rule": (
                        "pdf_exact_then_ordered_edit_distance_then_hausdorff_then_"
                        "rightmost_x_difference_then_rightmost_y_symmetric_difference_then_candidate_id"
                    ),
                    "pdf_sequence_exact_allow_whole_reverse": winner[
                        "pdf_sequence_exact_allow_whole_reverse"
                    ],
                    "symmetric_hausdorff_index_units": winner[
                        "symmetric_hausdorff_index_units"
                    ],
                    "pdf_ordered_path_edit_distance_allow_whole_reverse": winner[
                        "pdf_ordered_path_edit_distance_allow_whole_reverse"
                    ],
                    "pdf_rightmost_absolute_difference_index_units": winner[
                        "pdf_rightmost_absolute_difference_index_units"
                    ],
                    "pdf_rightmost_x_absolute_difference_index_units": winner[
                        "pdf_rightmost_x_absolute_difference_index_units"
                    ],
                    "pdf_rightmost_y_set_symmetric_difference_count": winner[
                        "pdf_rightmost_y_set_symmetric_difference_count"
                    ],
                    "endpoint_absolute_difference_index_units": winner[
                        "endpoint_absolute_difference_index_units"
                    ],
                    "stable_count_absolute_difference_to_history_diagnostic": winner[
                        "stable_count_absolute_difference_to_history_diagnostic"
                    ],
                    "complete_reproduction_status": winner["complete_reproduction_status"],
                    "interpretation": "NEAREST_DIAGNOSTIC_ONLY_NOT_REPRODUCTION",
                }
            )

    whole_figure_adjudication: list[dict[str, Any]] = []
    for division in (1, 2):
        for candidate_id in CANDIDATES:
            subset = [
                row
                for row in metrics
                if row["division"] == division and row["candidate_id"] == candidate_id
            ]
            if len(subset) != 3:
                raise ValueError(f"图{FIGURE_ID[division]} {candidate_id}不是三方法")
            visible_exact_count = sum(row["pdf_visible_path_gate"] == "PASS" for row in subset)
            verifiable_count = sum(
                row["full_mask_gate"] != "NOT_EVALUABLE_MISSING_SOURCE_MASK"
                for row in subset
            )
            verified_count = sum(
                row["full_mask_gate"] == "PASS_AUTHOR_SOURCE_MASK_EXACT"
                for row in subset
            )
            visible_all_exact = visible_exact_count == len(subset)
            all_masks_verifiable = verifiable_count == len(subset)
            complete_exact = visible_all_exact and all_masks_verifiable and verified_count == len(subset)
            if complete_exact:
                status = "PASS_COMPLETE_WHOLE_FIGURE_REPRODUCTION"
            elif not visible_all_exact:
                status = "FAIL_VISIBLE_PATH_MISMATCH_WITH_PARTIAL_MASK_VERIFIABILITY"
            else:
                status = "VISIBLE_PATHS_EXACT_BUT_FULL_MASKS_NOT_VERIFIABLE"
            whole_figure_adjudication.append(
                {
                    "figure_id": f"图{FIGURE_ID[division]}",
                    "division": division,
                    "candidate_id": candidate_id,
                    "candidate_short_name": CANDIDATE_PANEL_LABELS[candidate_id].replace("$", ""),
                    "method_count": len(subset),
                    "visible_path_exact_count": visible_exact_count,
                    "visible_path_all_exact": visible_all_exact,
                    "authoritative_full_mask_count": verifiable_count,
                    "missing_source_mask_count": len(subset) - verifiable_count,
                    "authoritative_full_mask_exact_count": verified_count,
                    "full_mask_verifiability": f"PARTIAL_{verifiable_count}_OF_{len(subset)}_AUTHORITATIVE",
                    "all_full_masks_verifiable": all_masks_verifiable,
                    "complete_reproduction_exact": complete_exact,
                    "whole_figure_status": status,
                }
            )

    global_candidate_adjudication: list[dict[str, Any]] = []
    for candidate_id in CANDIDATES:
        subset = [row for row in metrics if row["candidate_id"] == candidate_id]
        if len(subset) != 6:
            raise ValueError(f"{candidate_id}全局不是六条曲线")
        visible_exact_count = sum(row["pdf_visible_path_gate"] == "PASS" for row in subset)
        verifiable_count = sum(
            row["full_mask_gate"] != "NOT_EVALUABLE_MISSING_SOURCE_MASK" for row in subset
        )
        verified_count = sum(
            row["full_mask_gate"] == "PASS_AUTHOR_SOURCE_MASK_EXACT" for row in subset
        )
        visible_all_exact = visible_exact_count == len(subset)
        all_masks_verifiable = verifiable_count == len(subset)
        complete_exact = visible_all_exact and all_masks_verifiable and verified_count == len(subset)
        if complete_exact:
            status = "PASS_ALL_SIX_CURVES_COMPLETE_REPRODUCTION"
        elif not visible_all_exact:
            status = "FAIL_VISIBLE_PATH_MISMATCH_WITH_MISSING_SOURCE_MASKS"
        else:
            status = "ALL_VISIBLE_PATHS_EXACT_BUT_FULL_MASKS_NOT_VERIFIABLE"
        global_candidate_adjudication.append(
            {
                "candidate_id": candidate_id,
                "candidate_short_name": CANDIDATE_PANEL_LABELS[candidate_id].replace("$", ""),
                "curve_count": len(subset),
                "visible_path_exact_count": visible_exact_count,
                "visible_path_all_exact": visible_all_exact,
                "authoritative_full_mask_count": verifiable_count,
                "missing_source_mask_count": len(subset) - verifiable_count,
                "authoritative_full_mask_exact_count": verified_count,
                "full_mask_verifiability": f"PARTIAL_{verifiable_count}_OF_{len(subset)}_AUTHORITATIVE",
                "all_full_masks_verifiable": all_masks_verifiable,
                "complete_reproduction_exact": complete_exact,
                "global_six_curve_status": status,
            }
        )

    exact_count = sum(bool(row["complete_reproduction_exact"]) for row in metrics)
    globally_complete_candidates = [
        row["candidate_id"]
        for row in global_candidate_adjudication
        if row["complete_reproduction_exact"]
    ]
    all_six_reproduced = bool(globally_complete_candidates)
    summary = {
        "step": "8F",
        "evidence_level": "CALCULATION_CANDIDATE_ADJUDICATION",
        "candidate_group_count": len(groups),
        "grid_shape": [N_L, N_J],
        "candidate_point_count": len(groups) * N_L * N_J,
        "matlab_boundary_contract": "bwboundaries(M,8,'noholes'); B{1}; x=column; y=row; remove x<=1 or y<=1",
        "structural_gate": {
            "expected": "all 30 candidate/history masks have one 8-connected component, zero hole pixels, one returned boundary",
            "failure_count": len(structural_failures),
            "failures": structural_failures,
            "passed": len(structural_failures) == 0,
        },
        "pdf_target_limit": (
            "The visible open PDF boundary cannot uniquely recover a complete 31x67 source mask."
        ),
        "full_mask_adjudication": {
            "Original": "EVALUABLE_FROM_AUTHOR_HISTORY_MASK_BECAUSE_PATH_MATCHES_PDF",
            "Craig-Bampton": "NOT_EVALUABLE_MISSING_SOURCE_MASK",
            "Guyan": "NOT_EVALUABLE_MISSING_SOURCE_MASK",
        },
        "history_reduced_masks": "DIAGNOSTIC_ONLY_BECAUSE_THEIR_BOUNDARIES_CONFLICT_WITH_PDF",
        "history_target_consistency": {
            f"图{FIGURE_ID[division]}_{method}": payload
            for (division, method), payload in sorted(
                history_target_consistency.items(), key=lambda item: (item[0][0], METHODS.index(item[0][1]))
            )
        },
        "complete_reproduction_exact_candidate_count": exact_count,
        "whole_figure_adjudication_row_count": len(whole_figure_adjudication),
        "global_six_curve_adjudication_row_count": len(global_candidate_adjudication),
        "globally_complete_candidate_ids": globally_complete_candidates,
        "all_six_targets_completely_reproduced": all_six_reproduced,
        "overall_gate": (
            "PASS_COMPLETE_CALCULATION_REPRODUCTION"
            if all_six_reproduced
            else "FAIL_NO_COMPLETE_CALCULATION_REPRODUCTION"
        ),
        "nearest_candidate_semantics": "DIAGNOSTIC_ONLY_NOT_REPRODUCTION",
        "coordinate_mapping": {
            "index": "x=j+1, y=l+1",
            "physical_ms": "tau1=(x-1)*1000/1024, tau2=(y-1)*1000/1024",
        },
        "planned_render_outputs": [
            f"图{figure}_{'第一类划分' if figure == '4-4' else '第二类划分'}_四候选与论文目标_索引坐标.pdf"
            for figure in ("4-4", "4-5")
        ]
        + [
            f"图{figure}_{'第一类划分' if figure == '4-4' else '第二类划分'}_四候选与论文目标_物理毫秒.pdf"
            for figure in ("4-4", "4-5")
        ],
    }
    return (
        metrics,
        nearest,
        whole_figure_adjudication,
        global_candidate_adjudication,
        summary,
        candidate_paths,
    )


def write_adjudication_outputs(
    metrics: list[dict[str, Any]],
    nearest: list[dict[str, Any]],
    whole_figure_adjudication: list[dict[str, Any]],
    global_candidate_adjudication: list[dict[str, Any]],
    summary: dict[str, Any],
    groups: dict[GroupKey, GroupData],
    targets: dict[tuple[int, str], TargetPath],
) -> None:
    metrics_path = ADJUDICATION_ROOT / "24候选与六条论文目标逐项裁决.csv"
    nearest_path = ADJUDICATION_ROOT / "六条目标最近诊断候选.csv"
    summary_path = ADJUDICATION_ROOT / "步骤8F计算候选裁决摘要.json"
    whole_figure_path = ADJUDICATION_ROOT / "8行同候选整图级裁决.csv"
    global_candidate_path = ADJUDICATION_ROOT / "4行同候选六曲线全局裁决.csv"
    write_rows(metrics_path, tuple(metrics[0].keys()), metrics)
    write_rows(nearest_path, tuple(nearest[0].keys()), nearest)
    write_rows(
        whole_figure_path,
        tuple(whole_figure_adjudication[0].keys()),
        whole_figure_adjudication,
    )
    write_rows(
        global_candidate_path,
        tuple(global_candidate_adjudication[0].keys()),
        global_candidate_adjudication,
    )

    provenance: list[dict[str, Any]] = []
    source_paths = [STEP8E_POINTS, *HISTORY_FILES.values()]
    source_paths.extend(target.source_file for target in targets.values())
    source_paths.append(SCRIPT)
    for path in sorted(set(source_paths), key=lambda value: str(value).casefold()):
        provenance.append(
            {
                "role": "script" if path == SCRIPT else "read_only_input",
                "relative_path": rel_to_board(path),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    provenance_path = ADJUDICATION_ROOT / "输入与代码来源哈希.csv"
    write_rows(provenance_path, ("role", "relative_path", "size_bytes", "sha256"), provenance)

    summary["source_provenance_file"] = rel_to_board(provenance_path)
    summary["metrics_file"] = rel_to_board(metrics_path)
    summary["nearest_diagnostic_file"] = rel_to_board(nearest_path)
    summary["whole_figure_adjudication_file"] = rel_to_board(whole_figure_path)
    summary["global_six_curve_adjudication_file"] = rel_to_board(global_candidate_path)
    summary["candidate_ids"] = list(CANDIDATES)
    summary["methods"] = list(METHODS)
    summary["candidate_names"] = {
        candidate_id: next(
            group.candidate_name
            for key, group in groups.items()
            if key.candidate_id == candidate_id
        )
        for candidate_id in CANDIDATES
    }
    json_dump(summary_path, summary)

    report_lines = [
        "# 步骤 8F：图 4-4/图 4-5 计算候选与论文目标裁决",
        "",
        f"- 结论：`{summary['overall_gate']}`。",
        f"- 24个‘单目标×候选’组合中完整计算复现数：{summary['complete_reproduction_exact_candidate_count']}。",
        "- 候选数据：步骤8E Python逐点CSV的stable字段，24组×31×67=49,848点。",
        "- 候选边界：MATLAB `bwboundaries(M,8,'noholes')`的`B{1}`，再删除x<=1或y<=1。",
        "- 论文PDF只提供可见开边界，不能唯一恢复31×67完整掩膜。",
        "- 四条缩聚曲线的完整掩膜裁决为`NOT_EVALUABLE_MISSING_SOURCE_MASK`。",
        "- 两条Original历史掩膜的MATLAB边界与论文开边界一致，可执行完整掩膜XOR/IoU主门。",
        "- 四条缩聚历史掩膜与论文边界冲突，Hamming/IoU只是历史路线诊断。",
        "- “最近候选”只是诊断标签，不是完整复现。",
        "",
        "## 六条目标的最近诊断候选",
        "",
        "| 图 | 方法 | 候选 | PDF有序路径精确 | 编辑距离 | Hausdorff | 裁决 |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in nearest:
        report_lines.append(
            f"| {row['figure_id']} | {row['method_cn']} | {row['nearest_diagnostic_candidate']} | "
            f"{row['pdf_sequence_exact_allow_whole_reverse']} | "
            f"{int(row['pdf_ordered_path_edit_distance_allow_whole_reverse'])} | "
            f"{float(row['symmetric_hausdorff_index_units']):.6g} | "
            f"{row['complete_reproduction_status']} |"
        )
    report_lines.extend(
        [
            "",
            "## 坐标合同",
            "",
            "- 索引坐标：`(x,y)=(j+1,l+1)`。",
            "- 物理毫秒：`(tau1,tau2)=((x-1),(y-1))*1000/1024`。",
            "- 绝不把1-based绘图索引直接乘以时间步长。",
            "",
        ]
    )
    (ADJUDICATION_ROOT / "步骤8F裁决报告.md").write_text(
        "\n".join(report_lines), encoding="utf-8"
    )


def setup_plot_style() -> None:
    import matplotlib as mpl

    mpl.rcParams.update(
        {
            "text.usetex": True,
            "font.family": "serif",
            "font.serif": ["CMU Serif", "Computer Modern Roman"],
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
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def render_one_figure(
    division: int,
    coordinate_mode: str,
    groups: dict[GroupKey, GroupData],
    targets: dict[tuple[int, str], TargetPath],
    candidate_paths: dict[GroupKey, tuple[tuple[int, int], ...]],
) -> tuple[Path, Path]:
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.ticker import MaxNLocator

    setup_plot_style()
    calculation_style = {
        "Original": {"color": "#555555", "linestyle": "--"},
        "CB": {"color": "#EE6677", "linestyle": "-"},
        "Guyan": {"color": "#4477AA", "linestyle": "-."},
    }
    marker_style = {"Original": "o", "CB": "s", "Guyan": "^"}
    fig, axes = plt.subplots(2, 2, figsize=(7.48, 5.61), constrained_layout=False)
    for panel_index, (ax, candidate_id) in enumerate(zip(axes.flat, CANDIDATES)):
        for method in METHODS:
            key = GroupKey(division, method, candidate_id)
            candidate = np.asarray(candidate_paths[key], dtype=float)
            target = np.asarray(targets[(division, method)].points, dtype=float)
            if coordinate_mode == "physical_ms":
                candidate = (candidate - 1.0) * DT_MS
                target = (target - 1.0) * DT_MS
            style = calculation_style[method]
            ax.plot(
                candidate[:, 0],
                candidate[:, 1],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=1.2,
                zorder=3,
            )
            mark_every = max(1, len(target) // 8)
            ax.plot(
                target[:, 0],
                target[:, 1],
                color=style["color"],
                linestyle=":",
                linewidth=0.8,
                alpha=0.55,
                marker=marker_style[method],
                markerfacecolor="none",
                markeredgecolor=style["color"],
                markeredgewidth=0.8,
                markersize=3.6,
                markevery=mark_every,
                zorder=2,
            )
        ax.text(
            0.03,
            0.95,
            f"({chr(ord('a') + panel_index)}) {CANDIDATE_PANEL_LABELS[candidate_id]}",
            transform=ax.transAxes,
            va="top",
            ha="left",
            fontsize=8,
            fontweight="bold",
            bbox={
                "facecolor": "white",
                "edgecolor": "none",
                "alpha": 0.82,
                "pad": 1.5,
            },
        )
        ax.grid(False)
        ax.tick_params(direction="in", top=True, right=True)
        ax.xaxis.set_major_locator(MaxNLocator(nbins=5))
        ax.yaxis.set_major_locator(MaxNLocator(nbins=5))
        if coordinate_mode == "index":
            ax.set_xlim(1.0, float(N_J) + 0.5)
            ax.set_ylim(1.0, float(N_L) + 0.5)
            ax.set_xlabel(r"Delay sample index $j+1$")
            ax.set_ylabel(r"Delay sample index $\ell+1$")
        else:
            ax.set_xlim(0.0, (N_J - 0.5) * DT_MS)
            ax.set_ylim(0.0, (N_L - 0.5) * DT_MS)
            ax.set_xlabel(r"Delay $\tau_1$ (ms)")
            ax.set_ylabel(r"Delay $\tau_2$ (ms)")

    legend_handles: list[Line2D] = []
    for method in METHODS:
        style = calculation_style[method]
        label = "Original" if method == "Original" else method
        legend_handles.append(
            Line2D(
                [0],
                [0],
                color=style["color"],
                linestyle=style["linestyle"],
                linewidth=1.2,
                label=label,
            )
        )
    legend_handles.extend(
        [
            Line2D(
                [0],
                [0],
                color="#333333",
                linestyle="-",
                linewidth=1.2,
                label="Calculated boundary",
            ),
            Line2D(
                [0],
                [0],
                color="#777777",
                linestyle=":",
                linewidth=0.8,
                marker="o",
                markerfacecolor="none",
                markeredgewidth=0.8,
                markersize=3.6,
                label="Thesis vector target",
            ),
        ]
    )
    fig.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.995),
        ncol=5,
        frameon=False,
        handlelength=1.7,
        handletextpad=0.35,
        columnspacing=0.75,
    )
    fig.tight_layout(rect=(0.0, 0.0, 1.0, 0.90), pad=0.5, w_pad=0.7, h_pad=0.8)

    division_name = "第一类划分" if division == 1 else "第二类划分"
    coordinate_name = "索引坐标" if coordinate_mode == "index" else "物理毫秒"
    stem = f"图{FIGURE_ID[division]}_{division_name}_四候选与论文目标_{coordinate_name}"
    FIGURE_ROOT.mkdir(parents=True, exist_ok=True)
    pdf_path = FIGURE_ROOT / f"{stem}.pdf"
    png_path = FIGURE_ROOT / f"{stem}.png"
    fixed_time = datetime(2000, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    fig.savefig(
        pdf_path,
        format="pdf",
        metadata={
            "Creator": "Board20 Step8F deterministic scientific plotting",
            "Producer": "Matplotlib",
            "CreationDate": fixed_time,
            "ModDate": fixed_time,
        },
    )
    fig.savefig(
        png_path,
        format="png",
        dpi=600,
        metadata={"Software": "Board20 Step8F deterministic scientific plotting"},
    )
    plt.close(fig)
    return pdf_path, png_path


def render_all(
    groups: dict[GroupKey, GroupData],
    targets: dict[tuple[int, str], TargetPath],
    candidate_paths: dict[GroupKey, tuple[tuple[int, int], ...]],
) -> None:
    os.environ["SOURCE_DATE_EPOCH"] = "946684800"
    outputs: list[Path] = []
    for division in (1, 2):
        for coordinate_mode in ("index", "physical_ms"):
            outputs.extend(
                render_one_figure(
                    division, coordinate_mode, groups, targets, candidate_paths
                )
            )
    if len([path for path in outputs if path.suffix.lower() == ".pdf"]) != 4:
        raise RuntimeError("绘图PDF数量不是4")
    if len([path for path in outputs if path.suffix.lower() == ".png"]) != 4:
        raise RuntimeError("绘图PNG数量不是4")
    manifest = [
        {
            "relative_path": rel_to_board(path),
            "format": path.suffix.lower().lstrip("."),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in outputs
    ]
    write_rows(
        ADJUDICATION_ROOT / "绘图工件哈希清单.csv",
        ("relative_path", "format", "size_bytes", "sha256"),
        manifest,
    )


def build_data() -> tuple[
    dict[GroupKey, GroupData],
    dict[tuple[int, str], TargetPath],
    dict[GroupKey, tuple[tuple[int, int], ...]],
]:
    require_inputs()
    groups = load_candidate_groups()
    targets = load_targets()
    history_masks = load_history_masks()
    jobs, _, boundary_paths = prepare_masks_and_matlab_jobs(groups, history_masks)
    matlab_stats = run_matlab_bwboundaries(jobs)
    (
        metrics,
        nearest,
        whole_figure_adjudication,
        global_candidate_adjudication,
        summary,
        candidate_paths,
    ) = adjudicate(
        groups,
        targets,
        history_masks,
        jobs,
        boundary_paths,
        matlab_stats,
    )
    write_adjudication_outputs(
        metrics,
        nearest,
        whole_figure_adjudication,
        global_candidate_adjudication,
        summary,
        groups,
        targets,
    )
    return groups, targets, candidate_paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--data-only",
        action="store_true",
        help="只生成掩膜、MATLAB边界和裁决数据（默认）",
    )
    mode.add_argument(
        "--render",
        action="store_true",
        help="重建数据并生成4份矢量PDF和4份600dpi PNG",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    groups, targets, candidate_paths = build_data()
    if args.render:
        render_all(groups, targets, candidate_paths)
        print("STEP8F_RENDER_DONE: 4 PDF + 4 PNG")
    else:
        print("STEP8F_DATA_ONLY_DONE: no PDF/PNG generated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

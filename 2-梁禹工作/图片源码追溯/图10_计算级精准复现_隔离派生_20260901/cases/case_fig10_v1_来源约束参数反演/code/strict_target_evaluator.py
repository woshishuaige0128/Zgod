#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图10六曲线独立严格目标评估器。

证据边界：
1. 本文件只读候选边界/掩膜与 plotted_data.mat，不导入也不运行求解器。
2. 目标点从 MAT 文件动态读取，没有写入任何求解器代码。
3. 边界候选由 Python 直接验收；掩膜候选仅调用固定 MATLAB
   bwboundaries(M,8,'noholes') 辅助程序提取边界，不运行参数搜索。
4. 严格主门只接受目标原始点序；整体反转仅作诊断。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import numpy as np
from scipy.io import loadmat


SCRIPT = Path(__file__).resolve()
CASE_ROOT = SCRIPT.parent.parent
REPOSITORY_ROOT = SCRIPT.parents[5]
DEFAULT_TARGET = (
    REPOSITORY_ROOT.parent
    / "260817"
    / "code"
    / "Fig10_双时滞稳定域"
    / "输出"
    / "plotted_data.mat"
)
DEFAULT_MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
EXPECTED_TARGET_SHA256 = "9312FB45595499C4242BF00DAC344CE016CB64F844CB410EA89ECB1F6C8BC7E4"
SCHEMA_VERSION = "FIG10_STRICT_TARGET_EVALUATOR_V1"
MANIFEST_SCHEMA = "FIG10_CANDIDATE_MANIFEST_V1"
MS_PER_STEP = 1000.0 / 1024.0
MS_TOLERANCE = 1.0e-12


@dataclass(frozen=True)
class CurveContract:
    curve_id: str
    division: int
    figure_id: str
    method: str
    expected_point_count: int


CURVE_CONTRACTS: tuple[CurveContract, ...] = (
    CurveContract("division1_original", 1, "4-4", "Original", 72),
    CurveContract("division1_craig_bampton", 1, "4-4", "Craig-Bampton", 69),
    CurveContract("division1_guyan", 1, "4-4", "Guyan", 67),
    CurveContract("division2_original", 2, "4-5", "Original", 69),
    CurveContract("division2_craig_bampton", 2, "4-5", "Craig-Bampton", 56),
    CurveContract("division2_guyan", 2, "4-5", "Guyan", 53),
)
CONTRACT_BY_ID = {item.curve_id: item for item in CURVE_CONTRACTS}
EXPECTED_TOTAL_POINTS = sum(item.expected_point_count for item in CURVE_CONTRACTS)


@dataclass
class BoundaryData:
    points: tuple[tuple[int, int], ...]
    tau1_ms_declared: np.ndarray | None
    tau2_ms_declared: np.ndarray | None
    source_path: Path
    source_sha256: str
    input_type: str
    mask_metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class TargetData:
    points: tuple[tuple[int, int], ...]
    tau1_ms: np.ndarray
    tau2_ms: np.ndarray


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def json_dump(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: row.get(name, "") for name in fieldnames})


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON 顶层必须为对象：{path}")
    return payload


def normalize_vector(value: Any, dtype: np.dtype[Any]) -> np.ndarray:
    return np.asarray(value, dtype=dtype).reshape(-1)


def integer_steps(value: Any, label: str) -> np.ndarray:
    raw = normalize_vector(value, np.float64)
    if raw.size == 0 or not np.isfinite(raw).all():
        raise ValueError(f"{label} 为空或包含非有限值")
    rounded = np.rint(raw)
    if not np.array_equal(raw, rounded):
        raise ValueError(f"{label} 包含非整数步号")
    result = rounded.astype(np.int64)
    if np.any(result < 1):
        raise ValueError(f"{label} 必须是 1-based 正整数")
    return result


def load_target(path: Path) -> tuple[dict[str, TargetData], dict[str, Any]]:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"目标 MAT 不存在：{path}")
    target_hash = sha256(path)
    if target_hash != EXPECTED_TARGET_SHA256:
        raise ValueError(
            "目标 MAT SHA-256 与冻结合同不一致："
            f"actual={target_hash}; expected={EXPECTED_TARGET_SHA256}"
        )
    raw = loadmat(path, simplify_cells=True)
    plotted = raw.get("plottedData")
    if not isinstance(plotted, list) or len(plotted) != len(CURVE_CONTRACTS):
        raise ValueError("plottedData 不是固定的六曲线列表")
    targets: dict[str, TargetData] = {}
    target_internal_ms_error = 0.0
    for contract, entry in zip(CURVE_CONTRACTS, plotted, strict=True):
        if not isinstance(entry, dict):
            raise ValueError(f"{contract.curve_id}: 目标条目不是结构体")
        tau1 = integer_steps(entry["tau1_step"], f"{contract.curve_id}.tau1_step")
        tau2 = integer_steps(entry["tau2_step"], f"{contract.curve_id}.tau2_step")
        order = integer_steps(entry["point_order"], f"{contract.curve_id}.point_order")
        expected_order = np.arange(1, tau1.size + 1, dtype=np.int64)
        if not np.array_equal(order, expected_order):
            raise ValueError(f"{contract.curve_id}: 目标 point_order 不连续")
        if tau1.size != tau2.size or tau1.size != contract.expected_point_count:
            raise ValueError(
                f"{contract.curve_id}: 目标点数 {tau1.size} != {contract.expected_point_count}"
            )
        tau1_ms = normalize_vector(entry["tau1_ms"], np.float64)
        tau2_ms = normalize_vector(entry["tau2_ms"], np.float64)
        if tau1_ms.size != tau1.size or tau2_ms.size != tau2.size:
            raise ValueError(f"{contract.curve_id}: 目标毫秒字段长度不一致")
        internal_error = max(
            float(np.max(np.abs(tau1_ms - (tau1.astype(np.float64) - 1.0) * MS_PER_STEP))),
            float(np.max(np.abs(tau2_ms - (tau2.astype(np.float64) - 1.0) * MS_PER_STEP))),
        )
        target_internal_ms_error = max(target_internal_ms_error, internal_error)
        targets[contract.curve_id] = TargetData(
            points=tuple(zip(tau1.tolist(), tau2.tolist(), strict=True)),
            tau1_ms=tau1_ms,
            tau2_ms=tau2_ms,
        )
    metadata = raw.get("metadata", {})
    if isinstance(metadata, dict):
        point_count = int(metadata.get("pointCount", -1))
        sampling_period = float(metadata.get("samplingPeriodSeconds", math.nan))
        if point_count != EXPECTED_TOTAL_POINTS:
            raise ValueError(f"目标 metadata.pointCount={point_count} != {EXPECTED_TOTAL_POINTS}")
        if not math.isclose(sampling_period, 1.0 / 1024.0, rel_tol=0.0, abs_tol=1e-15):
            raise ValueError("目标采样周期不是 1/1024 s")
    return targets, {
        "path": str(path),
        "sha256": target_hash,
        "point_count": EXPECTED_TOTAL_POINTS,
        "target_internal_step_to_ms_max_abs_error": target_internal_ms_error,
    }


def pick_column(
    fieldnames: Sequence[str], explicit: dict[str, Any], logical_name: str, aliases: Sequence[str]
) -> str | None:
    if logical_name in explicit:
        value = str(explicit[logical_name])
        if value not in fieldnames:
            raise ValueError(f"显式列 {logical_name}={value} 不在 CSV 中")
        return value
    for alias in aliases:
        if alias in fieldnames:
            return alias
    return None


def load_boundary_csv(path: Path, entry: dict[str, Any], input_type: str) -> BoundaryData:
    path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"候选边界 CSV 不存在：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    if not rows:
        raise ValueError(f"候选边界 CSV 为空：{path}")
    explicit = entry.get("columns", {})
    if not isinstance(explicit, dict):
        raise ValueError(f"columns 必须为对象：{path}")
    order_col = pick_column(
        fieldnames, explicit, "point_order", ("point_order", "boundary_sequence", "sequence")
    )
    tau1_col = pick_column(
        fieldnames,
        explicit,
        "tau1_step",
        ("tau1_step", "x_index", "tau1_raw_index", "j_step", "j_index"),
    )
    tau2_col = pick_column(
        fieldnames,
        explicit,
        "tau2_step",
        ("tau2_step", "y_index", "tau2_raw_index", "l_step", "l_index"),
    )
    tau1_ms_col = pick_column(
        fieldnames, explicit, "tau1_ms", ("tau1_ms", "plotted_x_ms", "x_ms")
    )
    tau2_ms_col = pick_column(
        fieldnames, explicit, "tau2_ms", ("tau2_ms", "plotted_y_ms", "y_ms")
    )
    if order_col is None or tau1_col is None or tau2_col is None:
        raise ValueError(
            f"{path}: 必须显式或通过标准别名提供 point_order/tau1_step/tau2_step"
        )
    if (tau1_ms_col is None) != (tau2_ms_col is None):
        raise ValueError(f"{path}: tau1_ms/tau2_ms 必须同时存在或同时缺省")
    try:
        orders = np.asarray([float(row[order_col]) for row in rows], dtype=np.float64)
        tau1_raw = np.asarray([float(row[tau1_col]) for row in rows], dtype=np.float64)
        tau2_raw = np.asarray([float(row[tau2_col]) for row in rows], dtype=np.float64)
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{path}: 点序/步号列不是数值") from exc
    orders_int = integer_steps(orders, f"{path.name}.point_order")
    permutation = np.argsort(orders_int, kind="stable")
    sorted_order = orders_int[permutation]
    if not np.array_equal(sorted_order, np.arange(1, len(rows) + 1, dtype=np.int64)):
        raise ValueError(f"{path}: point_order 必须且只能覆盖 1..N")
    tau1 = integer_steps(tau1_raw[permutation], f"{path.name}.tau1_step")
    tau2 = integer_steps(tau2_raw[permutation], f"{path.name}.tau2_step")
    declared_x = declared_y = None
    if tau1_ms_col is not None and tau2_ms_col is not None:
        try:
            declared_x = np.asarray(
                [float(rows[index][tau1_ms_col]) for index in permutation], dtype=np.float64
            )
            declared_y = np.asarray(
                [float(rows[index][tau2_ms_col]) for index in permutation], dtype=np.float64
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"{path}: 毫秒列不是数值") from exc
        if not np.isfinite(declared_x).all() or not np.isfinite(declared_y).all():
            raise ValueError(f"{path}: 毫秒列包含非有限值")
    return BoundaryData(
        points=tuple(zip(tau1.tolist(), tau2.tolist(), strict=True)),
        tau1_ms_declared=declared_x,
        tau2_ms_declared=declared_y,
        source_path=path,
        source_sha256=sha256(path),
        input_type=input_type,
    )


def matlab_quote(path: Path) -> str:
    return str(path.resolve()).replace("'", "''")


def extract_mask_boundaries(
    mask_entries: list[dict[str, Any]],
    manifest_dir: Path,
    output_dir: Path,
    matlab_executable: Path,
) -> dict[str, tuple[Path, dict[str, Any]]]:
    matlab_executable = matlab_executable.resolve()
    if not matlab_executable.is_file():
        raise FileNotFoundError(f"MATLAB 可执行文件不存在：{matlab_executable}")
    extraction_dir = output_dir / "mask_boundary_extraction"
    extraction_dir.mkdir(parents=True, exist_ok=True)
    tasks: list[dict[str, str]] = []
    for entry in mask_entries:
        curve_id = str(entry["curve_id"])
        boundary_mode = str(entry.get("boundary_mode", ""))
        if boundary_mode != "matlab_bwboundaries_8_noholes_visible_open":
            raise ValueError(
                f"{curve_id}: mask_csv 必须声明 boundary_mode="
                "matlab_bwboundaries_8_noholes_visible_open"
            )
        source_path = (manifest_dir / str(entry["path"])).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"{curve_id}: 掩膜 CSV 不存在：{source_path}")
        expected_shape = entry.get("expected_shape")
        if not (
            isinstance(expected_shape, list)
            and len(expected_shape) == 2
            and all(isinstance(value, int) and value > 0 for value in expected_shape)
        ):
            raise ValueError(f"{curve_id}: mask_csv 必须声明两个正整数 expected_shape")
        tasks.append(
            {
                "curve_id": curve_id,
                "path": str(source_path),
                "source_sha256": sha256(source_path),
                "expected_rows": str(expected_shape[0]),
                "expected_columns": str(expected_shape[1]),
                "boundary_csv": str(extraction_dir / f"{curve_id}.csv"),
                "metadata_json": str(extraction_dir / f"{curve_id}.meta.json"),
            }
        )
    task_file = extraction_dir / "mask_extraction_tasks.json"
    json_dump(task_file, {"schema_version": "FIG10_MASK_EXTRACTION_TASKS_V1", "curves": tasks})
    command_text = (
        f"addpath('{matlab_quote(SCRIPT.parent)}'); "
        f"fig10_extract_mask_boundaries('{matlab_quote(task_file)}');"
    )
    command_record = extraction_dir / "matlab_command.txt"
    command_record.write_text(
        f'"{matlab_executable}" -batch "{command_text}"\n', encoding="utf-8"
    )
    process = subprocess.run(
        [str(matlab_executable), "-batch", command_text],
        cwd=SCRIPT.parent,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    (extraction_dir / "matlab_stdout.log").write_text(process.stdout, encoding="utf-8")
    (extraction_dir / "matlab_stderr.log").write_text(process.stderr, encoding="utf-8")
    json_dump(
        extraction_dir / "matlab_process.json",
        {"returncode": process.returncode, "command": [str(matlab_executable), "-batch", command_text]},
    )
    if process.returncode != 0:
        raise RuntimeError(
            "MATLAB 掩膜边界提取失败，详见 "
            f"{extraction_dir / 'matlab_stdout.log'} 与 matlab_stderr.log"
        )
    result: dict[str, tuple[Path, dict[str, Any]]] = {}
    for task in tasks:
        boundary_path = Path(task["boundary_csv"])
        metadata_path = Path(task["metadata_json"])
        if not boundary_path.is_file() or not metadata_path.is_file():
            raise RuntimeError(f"{task['curve_id']}: MATLAB 未生成完整提取工件")
        result[task["curve_id"]] = (boundary_path, load_json(metadata_path))
    return result


def load_candidate_manifest(
    manifest_path: Path, output_dir: Path, matlab_executable: Path
) -> tuple[dict[str, BoundaryData], dict[str, Any]]:
    manifest_path = manifest_path.resolve()
    manifest = load_json(manifest_path)
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise ValueError(
            f"manifest schema_version={manifest.get('schema_version')} != {MANIFEST_SCHEMA}"
        )
    entries = manifest.get("curves")
    if not isinstance(entries, list):
        raise ValueError("manifest.curves 必须是列表")
    by_id: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("manifest.curves 的每个元素必须是对象")
        curve_id = str(entry.get("curve_id", ""))
        if curve_id in by_id:
            raise ValueError(f"重复 curve_id：{curve_id}")
        by_id[curve_id] = entry
    if set(by_id) != set(CONTRACT_BY_ID):
        missing = sorted(set(CONTRACT_BY_ID) - set(by_id))
        extra = sorted(set(by_id) - set(CONTRACT_BY_ID))
        raise ValueError(f"manifest 必须恰好绑定六曲线：missing={missing}; extra={extra}")
    mask_entries = [entry for entry in entries if entry.get("input_type") == "mask_csv"]
    extracted = extract_mask_boundaries(
        mask_entries, manifest_path.parent, output_dir, matlab_executable
    ) if mask_entries else {}
    candidates: dict[str, BoundaryData] = {}
    for curve_id in [item.curve_id for item in CURVE_CONTRACTS]:
        entry = by_id[curve_id]
        input_type = str(entry.get("input_type", ""))
        if input_type == "boundary_csv":
            path = (manifest_path.parent / str(entry["path"])).resolve()
            candidates[curve_id] = load_boundary_csv(path, entry, input_type)
        elif input_type == "mask_csv":
            boundary_path, metadata = extracted[curve_id]
            data = load_boundary_csv(
                boundary_path,
                {
                    "columns": {
                        "point_order": "point_order",
                        "tau1_step": "tau1_step",
                        "tau2_step": "tau2_step",
                    }
                },
                input_type,
            )
            source_path = (manifest_path.parent / str(entry["path"])).resolve()
            data.source_path = source_path
            data.source_sha256 = sha256(source_path)
            data.mask_metadata = metadata
            candidates[curve_id] = data
        else:
            raise ValueError(f"{curve_id}: input_type 必须是 boundary_csv 或 mask_csv")
    return candidates, {
        "path": str(manifest_path),
        "sha256": sha256(manifest_path),
        "candidate_id": str(manifest.get("candidate_id", "UNSPECIFIED")),
        "evidence_label": str(manifest.get("evidence_label", "目标引导的校准计算复现")),
    }


def symmetric_hausdorff(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> float:
    a = np.asarray(candidate, dtype=np.float64)
    b = np.asarray(target, dtype=np.float64)
    squared = np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)
    return max(
        float(np.sqrt(np.min(squared, axis=1)).max()),
        float(np.sqrt(np.min(squared, axis=0)).max()),
    )


def levenshtein_points(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> int:
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


def evaluate_curve(
    contract: CurveContract,
    candidate: BoundaryData,
    target: TargetData,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_points = candidate.points
    target_points = target.points
    candidate_set = set(candidate_points)
    target_set = set(target_points)
    ordered_exact = candidate_points == target_points
    reversed_exact = candidate_points == tuple(reversed(target_points))
    set_exact = candidate_set == target_set
    start_exact = candidate_points[0] == target_points[0]
    end_exact = candidate_points[-1] == target_points[-1]
    endpoint_l1 = int(
        sum(abs(a - b) for a, b in zip(candidate_points[0], target_points[0], strict=True))
        + sum(abs(a - b) for a, b in zip(candidate_points[-1], target_points[-1], strict=True))
    )
    hausdorff_steps = symmetric_hausdorff(candidate_points, target_points)
    edit_original = levenshtein_points(candidate_points, target_points)
    edit_reversed = levenshtein_points(candidate_points, tuple(reversed(target_points)))
    candidate_steps = np.asarray(candidate_points, dtype=np.float64)
    candidate_ms = (candidate_steps - 1.0) * MS_PER_STEP
    declared_ms_present = (
        candidate.tau1_ms_declared is not None and candidate.tau2_ms_declared is not None
    )
    declared_ms_error: float | None = None
    if declared_ms_present:
        declared_ms_error = max(
            float(np.max(np.abs(candidate.tau1_ms_declared - candidate_ms[:, 0]))),
            float(np.max(np.abs(candidate.tau2_ms_declared - candidate_ms[:, 1]))),
        )
    ordered_ms_error: float | None = None
    if len(candidate_points) == len(target_points):
        ordered_ms_error = max(
            float(np.max(np.abs(candidate_ms[:, 0] - target.tau1_ms))),
            float(np.max(np.abs(candidate_ms[:, 1] - target.tau2_ms))),
        )
    point_count_exact = len(candidate_points) == contract.expected_point_count
    declared_ms_gate = declared_ms_error is None or declared_ms_error <= MS_TOLERANCE
    ordered_ms_gate = ordered_ms_error is not None and ordered_ms_error <= MS_TOLERANCE
    strict_pass = all(
        (
            point_count_exact,
            ordered_exact,
            set_exact,
            start_exact,
            end_exact,
            hausdorff_steps == 0.0,
            edit_original == 0,
            ordered_ms_gate,
            declared_ms_gate,
        )
    )
    metric = {
        "curve_id": contract.curve_id,
        "figure_id": contract.figure_id,
        "division": contract.division,
        "method": contract.method,
        "input_type": candidate.input_type,
        "candidate_source_path": str(candidate.source_path),
        "candidate_source_sha256": candidate.source_sha256,
        "target_point_count": len(target_points),
        "candidate_point_count": len(candidate_points),
        "expected_point_count": contract.expected_point_count,
        "point_count_exact": point_count_exact,
        "candidate_unique_point_count": len(candidate_set),
        "candidate_duplicate_point_count": len(candidate_points) - len(candidate_set),
        "target_unique_point_count": len(target_set),
        "ordered_exact_original": ordered_exact,
        "ordered_exact_reversed_diagnostic": reversed_exact,
        "set_exact": set_exact,
        "start_endpoint_exact": start_exact,
        "end_endpoint_exact": end_exact,
        "candidate_start_endpoint": list(candidate_points[0]),
        "candidate_end_endpoint": list(candidate_points[-1]),
        "target_start_endpoint": list(target_points[0]),
        "target_end_endpoint": list(target_points[-1]),
        "endpoint_l1_error_steps_original": endpoint_l1,
        "symmetric_hausdorff_steps": hausdorff_steps,
        "symmetric_hausdorff_ms": hausdorff_steps * MS_PER_STEP,
        "point_levenshtein_original": edit_original,
        "point_levenshtein_reversed_diagnostic": edit_reversed,
        "candidate_declared_ms_present": declared_ms_present,
        "candidate_declared_step_to_ms_max_abs_error": declared_ms_error,
        "ordered_candidate_to_target_ms_max_abs_error": ordered_ms_error,
        "ms_tolerance": MS_TOLERANCE,
        "strict_curve_status": "PASS" if strict_pass else "FAIL",
        "mask_metadata": candidate.mask_metadata,
    }
    point_rows: list[dict[str, Any]] = []
    for index in range(max(len(candidate_points), len(target_points))):
        candidate_point = candidate_points[index] if index < len(candidate_points) else None
        target_point = target_points[index] if index < len(target_points) else None
        row: dict[str, Any] = {
            "curve_id": contract.curve_id,
            "point_order": index + 1,
            "candidate_tau1_step": "" if candidate_point is None else candidate_point[0],
            "candidate_tau2_step": "" if candidate_point is None else candidate_point[1],
            "target_tau1_step": "" if target_point is None else target_point[0],
            "target_tau2_step": "" if target_point is None else target_point[1],
            "ordered_point_exact": candidate_point == target_point,
            "candidate_tau1_ms": "",
            "candidate_tau2_ms": "",
            "target_tau1_ms": "",
            "target_tau2_ms": "",
            "tau1_ms_abs_error": "",
            "tau2_ms_abs_error": "",
        }
        if candidate_point is not None:
            row["candidate_tau1_ms"] = (candidate_point[0] - 1) * MS_PER_STEP
            row["candidate_tau2_ms"] = (candidate_point[1] - 1) * MS_PER_STEP
        if target_point is not None:
            row["target_tau1_ms"] = float(target.tau1_ms[index])
            row["target_tau2_ms"] = float(target.tau2_ms[index])
        if candidate_point is not None and target_point is not None:
            row["tau1_ms_abs_error"] = abs(
                float(row["candidate_tau1_ms"]) - float(row["target_tau1_ms"])
            )
            row["tau2_ms_abs_error"] = abs(
                float(row["candidate_tau2_ms"]) - float(row["target_tau2_ms"])
            )
        point_rows.append(row)
    set_rows: list[dict[str, Any]] = []
    for point in sorted(target_set - candidate_set):
        set_rows.append(
            {
                "curve_id": contract.curve_id,
                "difference_type": "MISSING_FROM_CANDIDATE",
                "tau1_step": point[0],
                "tau2_step": point[1],
            }
        )
    for point in sorted(candidate_set - target_set):
        set_rows.append(
            {
                "curve_id": contract.curve_id,
                "difference_type": "EXCESS_IN_CANDIDATE",
                "tau1_step": point[0],
                "tau2_step": point[1],
            }
        )
    return metric, point_rows, set_rows


METRIC_FIELDS = (
    "curve_id",
    "figure_id",
    "division",
    "method",
    "input_type",
    "candidate_source_path",
    "candidate_source_sha256",
    "target_point_count",
    "candidate_point_count",
    "expected_point_count",
    "point_count_exact",
    "candidate_unique_point_count",
    "candidate_duplicate_point_count",
    "target_unique_point_count",
    "ordered_exact_original",
    "ordered_exact_reversed_diagnostic",
    "set_exact",
    "start_endpoint_exact",
    "end_endpoint_exact",
    "candidate_start_endpoint",
    "candidate_end_endpoint",
    "target_start_endpoint",
    "target_end_endpoint",
    "endpoint_l1_error_steps_original",
    "symmetric_hausdorff_steps",
    "symmetric_hausdorff_ms",
    "point_levenshtein_original",
    "point_levenshtein_reversed_diagnostic",
    "candidate_declared_ms_present",
    "candidate_declared_step_to_ms_max_abs_error",
    "ordered_candidate_to_target_ms_max_abs_error",
    "ms_tolerance",
    "strict_curve_status",
)
POINT_FIELDS = (
    "curve_id",
    "point_order",
    "candidate_tau1_step",
    "candidate_tau2_step",
    "target_tau1_step",
    "target_tau2_step",
    "ordered_point_exact",
    "candidate_tau1_ms",
    "candidate_tau2_ms",
    "target_tau1_ms",
    "target_tau2_ms",
    "tau1_ms_abs_error",
    "tau2_ms_abs_error",
)


def evaluate_manifest(
    manifest_path: Path,
    target_path: Path,
    output_dir: Path,
    matlab_executable: Path,
) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    targets, target_metadata = load_target(target_path)
    candidates, manifest_metadata = load_candidate_manifest(
        manifest_path, output_dir, matlab_executable
    )
    metrics: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    set_rows: list[dict[str, Any]] = []
    for contract in CURVE_CONTRACTS:
        metric, curve_points, curve_sets = evaluate_curve(
            contract, candidates[contract.curve_id], targets[contract.curve_id]
        )
        metrics.append(metric)
        point_rows.extend(curve_points)
        set_rows.extend(curve_sets)
    candidate_total = sum(int(row["candidate_point_count"]) for row in metrics)
    strict_status = (
        "PASS"
        if candidate_total == EXPECTED_TOTAL_POINTS
        and target_metadata["target_internal_step_to_ms_max_abs_error"] <= MS_TOLERANCE
        and all(row["strict_curve_status"] == "PASS" for row in metrics)
        else "FAIL"
    )
    summary = {
        "schema_version": SCHEMA_VERSION,
        "overall_status": strict_status,
        "evidence_label": manifest_metadata["evidence_label"],
        "claim_boundary": (
            "目标引导的校准计算复现；本评估器不证明已恢复作者原始参数合同。"
        ),
        "candidate_id": manifest_metadata["candidate_id"],
        "manifest": manifest_metadata,
        "target": target_metadata,
        "coordinate_contract": {
            "step_index_base": 1,
            "sampling_frequency_hz": 1024,
            "conversion": "tau_ms=(tau_step-1)*1000/1024",
            "ms_tolerance": MS_TOLERANCE,
        },
        "strict_gate": {
            "expected_curve_point_counts": [
                item.expected_point_count for item in CURVE_CONTRACTS
            ],
            "expected_total_point_count": EXPECTED_TOTAL_POINTS,
            "candidate_total_point_count": candidate_total,
            "total_point_count_exact": candidate_total == EXPECTED_TOTAL_POINTS,
            "curve_pass_count": sum(row["strict_curve_status"] == "PASS" for row in metrics),
            "curve_count": len(metrics),
            "ordered_exact_required_orientation": "ORIGINAL_ONLY",
            "set_difference_count": len(set_rows),
        },
        "curves": metrics,
        "evaluator": {"path": str(SCRIPT), "sha256": sha256(SCRIPT)},
    }
    json_dump(output_dir / "strict_evaluation_summary.json", summary)
    csv_metrics = []
    for metric in metrics:
        row = dict(metric)
        row.pop("mask_metadata", None)
        for key in (
            "candidate_start_endpoint",
            "candidate_end_endpoint",
            "target_start_endpoint",
            "target_end_endpoint",
        ):
            row[key] = json.dumps(row[key], ensure_ascii=False, separators=(",", ":"))
        csv_metrics.append(row)
    write_csv(output_dir / "curve_metrics.csv", METRIC_FIELDS, csv_metrics)
    write_csv(output_dir / "pointwise_comparison.csv", POINT_FIELDS, point_rows)
    write_csv(
        output_dir / "set_differences.csv",
        ("curve_id", "difference_type", "tau1_step", "tau2_step"),
        set_rows,
    )
    artifact_rows = []
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "artifact_hashes.csv":
            artifact_rows.append(
                {
                    "path": path.relative_to(output_dir).as_posix(),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
            )
    write_csv(
        output_dir / "artifact_hashes.csv", ("path", "bytes", "sha256"), artifact_rows
    )
    return summary


def make_boundary_csv(path: Path, target: TargetData, perturb: bool = False) -> None:
    rows = []
    for index, point in enumerate(target.points, start=1):
        tau1, tau2 = point
        if perturb and index == 1:
            tau1 += 1
        rows.append(
            {
                "point_order": index,
                "tau1_step": tau1,
                "tau2_step": tau2,
                "tau1_ms": (tau1 - 1) * MS_PER_STEP,
                "tau2_ms": (tau2 - 1) * MS_PER_STEP,
            }
        )
    write_csv(
        path,
        ("point_order", "tau1_step", "tau2_step", "tau1_ms", "tau2_ms"),
        rows,
    )


def run_self_test(target_path: Path, output_dir: Path, matlab_executable: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    targets, _ = load_target(target_path)
    exact_input = output_dir / "selftest_inputs" / "exact"
    perturbed_input = output_dir / "selftest_inputs" / "perturbed"
    exact_entries = []
    perturbed_entries = []
    for contract in CURVE_CONTRACTS:
        exact_csv = exact_input / f"{contract.curve_id}.csv"
        perturbed_csv = perturbed_input / f"{contract.curve_id}.csv"
        make_boundary_csv(exact_csv, targets[contract.curve_id], perturb=False)
        make_boundary_csv(
            perturbed_csv,
            targets[contract.curve_id],
            perturb=contract.curve_id == "division1_original",
        )
        base_entry = {
            "curve_id": contract.curve_id,
            "input_type": "boundary_csv",
            "columns": {
                "point_order": "point_order",
                "tau1_step": "tau1_step",
                "tau2_step": "tau2_step",
                "tau1_ms": "tau1_ms",
                "tau2_ms": "tau2_ms",
            },
        }
        exact_entries.append({**base_entry, "path": exact_csv.name})
        perturbed_entries.append({**base_entry, "path": perturbed_csv.name})
    exact_manifest = exact_input / "manifest.json"
    perturbed_manifest = perturbed_input / "manifest.json"
    json_dump(
        exact_manifest,
        {
            "schema_version": MANIFEST_SCHEMA,
            "candidate_id": "SELFTEST_EXACT_DYNAMIC_TARGET_COPY",
            "evidence_label": "评估器自测，不是计算复现",
            "curves": exact_entries,
        },
    )
    json_dump(
        perturbed_manifest,
        {
            "schema_version": MANIFEST_SCHEMA,
            "candidate_id": "SELFTEST_ONE_POINT_PERTURBATION",
            "evidence_label": "评估器自测，不是计算复现",
            "curves": perturbed_entries,
        },
    )
    exact_summary = evaluate_manifest(
        exact_manifest, target_path, output_dir / "exact_evaluation", matlab_executable
    )
    perturbed_summary = evaluate_manifest(
        perturbed_manifest,
        target_path,
        output_dir / "perturbed_evaluation",
        matlab_executable,
    )
    perturbed_curve = next(
        row
        for row in perturbed_summary["curves"]
        if row["curve_id"] == "division1_original"
    )
    checks = {
        "exact_dynamic_copy_passes": exact_summary["overall_status"] == "PASS",
        "one_point_perturbation_fails": perturbed_summary["overall_status"] == "FAIL",
        "perturbed_ordered_exact_false": not perturbed_curve["ordered_exact_original"],
        "perturbed_set_exact_false": not perturbed_curve["set_exact"],
        "perturbed_hausdorff_one_step": perturbed_curve["symmetric_hausdorff_steps"] == 1.0,
        "perturbed_edit_distance_one": perturbed_curve["point_levenshtein_original"] == 1,
        "uint8_target_conversion_was_promoted_safely": (
            exact_summary["target"]["target_internal_step_to_ms_max_abs_error"] <= MS_TOLERANCE
        ),
    }
    result = {
        "schema_version": "FIG10_STRICT_EVALUATOR_SELFTEST_V1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "exact_overall_status": exact_summary["overall_status"],
        "perturbed_overall_status": perturbed_summary["overall_status"],
        "perturbed_curve_metrics": perturbed_curve,
        "evaluator_sha256": sha256(SCRIPT),
    }
    json_dump(output_dir / "selftest_summary.json", result)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, help="候选六曲线清单 JSON")
    parser.add_argument("--target", type=Path, default=DEFAULT_TARGET, help="冻结 plotted_data.mat")
    parser.add_argument("--output-dir", type=Path, required=True, help="评估输出目录")
    parser.add_argument("--matlab", type=Path, default=DEFAULT_MATLAB, help="MATLAB 可执行文件")
    parser.add_argument("--self-test", action="store_true", help="运行动态正/反例自测")
    args = parser.parse_args()
    if args.self_test == (args.manifest is not None):
        parser.error("--self-test 与 --manifest 必须且只能选一个")
    return args


def main() -> int:
    args = parse_args()
    try:
        if args.self_test:
            summary = run_self_test(args.target, args.output_dir, args.matlab)
            print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))
            return 0 if summary["status"] == "PASS" else 1
        summary = evaluate_manifest(args.manifest, args.target, args.output_dir, args.matlab)
        print(
            json.dumps(
                {
                    "overall_status": summary["overall_status"],
                    "candidate_id": summary["candidate_id"],
                    "candidate_total_point_count": summary["strict_gate"][
                        "candidate_total_point_count"
                    ],
                    "curve_pass_count": summary["strict_gate"]["curve_pass_count"],
                    "output_dir": str(args.output_dir.resolve()),
                },
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
        )
        return 0 if summary["overall_status"] == "PASS" else 2
    except Exception as exc:
        error = {
            "schema_version": SCHEMA_VERSION,
            "overall_status": "ERROR",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        args.output_dir.mkdir(parents=True, exist_ok=True)
        json_dump(args.output_dir / "strict_evaluation_error.json", error)
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""统一审计板块20步骤2的既有运行产物。

本脚本只读取 ``outputs/step2_runs`` 中的状态/科学数组，以及步骤1冻结的
``input/historical_plotting/作者绘图目录/lqr_3.mat``。它不启动 MATLAB，
也不读取或修改 ``tmp/step2_runs`` 中的工作目录。

默认输出：``outputs/step2_audit``。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
import scipy.io


SCHEMA = "board20_step2_unified_audit_v2"

ROUTES: tuple[dict[str, str], ...] = (
    {
        "route_id": "energy_guyan_div1",
        "route_name": "Guyan 能量候选路线——第一类子结构划分",
    },
    {
        "route_id": "energy_guyan_div2",
        "route_name": "Guyan 能量候选路线——第二类子结构划分",
    },
    {
        "route_id": "main_cb_div1",
        "route_name": "Craig–Bampton 主路线——第一类子结构划分",
    },
    {
        "route_id": "main_cb_div2",
        "route_name": "Craig–Bampton 主路线——第二类子结构划分",
    },
    {
        "route_id": "main_ori_div1",
        "route_name": "原结构命名主路线——第一类子结构划分",
    },
    {
        "route_id": "main_guyan_div1",
        "route_name": "Guyan 主路线——第一类子结构划分",
    },
    {
        "route_id": "main_ori_div2",
        "route_name": "原结构命名主路线——第二类子结构划分",
    },
    {
        "route_id": "main_guyan_div2",
        "route_name": "Guyan 主路线——第二类子结构划分",
    },
)

# 该候选路线是步骤2主路线运行完成后预先登记的唯一目录一致替代项。
# 它必须单列，不能计入上面的八条主路线统计。
ALTERNATIVE_ROUTE: dict[str, str] = {
    "route_id": "alt_guyan_div1_stable_full_ps3",
    "route_name": "Guyan 第一类划分备用候选——稳定目录 New_Full.m + New_Ps3.m",
}

HISTORICAL_MASK_MAP: dict[str, dict[str, str]] = {
    "main_ori_div2": {
        "historical_variable": "stab_o",
        "method_label": "原结构",
    },
    "main_guyan_div2": {
        "historical_variable": "stab_g",
        "method_label": "Guyan",
    },
}

# MATLAB 1-based inclusive ranges are documented here; Python slices are below.
VALID_SEGMENTS_MATLAB = (
    {"rows": "1:21", "columns": "1:21", "point_count": 441},
    {"rows": "1:26", "columns": "22:41", "point_count": 520},
    {"rows": "1:26", "columns": "42:61", "point_count": 520},
    {"rows": "1:6", "columns": "62:67", "point_count": 36},
)
VALID_SEGMENTS_PYTHON = (
    (slice(0, 21), slice(0, 21)),
    (slice(0, 26), slice(21, 41)),
    (slice(0, 26), slice(41, 61)),
    (slice(0, 6), slice(61, 67)),
)
VALID_SHAPE = (26, 67)
VALID_POINT_COUNT = 1517
FIRST_DIVISION_SHAPE = (21, 21)
FIRST_DIVISION_POINT_COUNT = 441

ROUTE_CSV_FIELDS = (
    "route_id",
    "route_name",
    "selected_replicate",
    "audit_state",
    "final_status",
    "execution_status",
    "evidence_status",
    "actual_matlab_returncode",
    "timed_out",
    "actual_scan_point_count",
    "actual_stab_shape",
    "runtime_dlqr_reached",
    "input_hashes_before",
    "input_hashes_after",
    "config_seal_status",
    "code_seal_status",
    "process_status_consistency",
    "error_identifier",
    "error_message",
    "status_sha256",
    "process_exit_sha256",
    "raw_stab_sha256",
    "configured_replicates_without_status",
)

MASK_CSV_FIELDS = (
    "route_id",
    "route_name",
    "method_label",
    "selected_replicate",
    "comparison_status",
    "historical_file",
    "historical_variable",
    "historical_shape",
    "raw_shape",
    "valid_point_count",
    "raw_finite_count",
    "raw_positive_count",
    "rho_lt_1_count",
    "rho_positive_lt_1_count",
    "raw_minimum",
    "raw_maximum",
    "TP",
    "FP",
    "FN",
    "TN",
    "mismatch_count",
    "accuracy",
    "historical_stable_total",
    "historical_stable_inside_valid_domain",
    "historical_stable_outside_valid_domain",
    "raw_stab_sha256",
    "historical_sha256",
    "mat_loader",
    "reason",
)

DIFF_CSV_FIELDS = (
    "comparison_status",
    "left_route_id",
    "right_route_id",
    "valid_point_count",
    "finite_pair_count",
    "exact_equal_count",
    "nonzero_difference_count",
    "absolute_difference_gt_1e_12_count",
    "maximum_absolute_difference",
    "mean_absolute_difference",
    "rms_difference",
    "allclose_rtol_0_atol_1e_12",
    "stable_mask_disagreement_count",
    "reason",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"JSON 顶层不是对象: {path}")
    return value


def replicate_number(name: str) -> int:
    match = re.fullmatch(r"rep(\d+)", name)
    return int(match.group(1)) if match else -1


def relative_to_board(path: Path, board_root: Path) -> str:
    try:
        return path.resolve().relative_to(board_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def match_record_summary(records: Any) -> dict[str, Any]:
    if not isinstance(records, list) or not records:
        return {
            "status": "NOT_RECORDED",
            "match_count": 0,
            "total_count": 0,
            "summary": "NOT_RECORDED",
        }
    matches = sum(1 for item in records if isinstance(item, dict) and item.get("match") is True)
    total = len(records)
    status = "PASS" if matches == total else "FAIL"
    return {
        "status": status,
        "match_count": matches,
        "total_count": total,
        "summary": f"{matches}/{total} MATCH" if status == "PASS" else f"{matches}/{total} MATCH (FAIL)",
    }


def instrumentation_summary(
    status: dict[str, Any],
    process_exit: dict[str, Any] | None,
    metadata_dir: Path,
) -> dict[str, Any]:
    captured = status.get("instrumentation")
    if not isinstance(captured, dict) and isinstance(process_exit, dict):
        captured = process_exit.get("execution_identity")
    if not isinstance(captured, dict):
        captured = {}

    config_expected = captured.get("config_expected_sha256")
    config_captured_actual = captured.get("config_actual_sha256")
    config_captured_match = captured.get("config_match")
    config_path = metadata_dir / "run_config.json"
    hash_path = metadata_dir / "run_config.sha256"
    independent_actual = sha256_file(config_path) if config_path.is_file() else None
    independent_expected = None
    if hash_path.is_file():
        text = hash_path.read_text(encoding="utf-8-sig").strip()
        independent_expected = text.split()[0].upper() if text else None
    independent_match = (
        independent_actual == independent_expected
        if independent_actual is not None and independent_expected is not None
        else None
    )

    if config_expected is None and independent_expected is None:
        config_status = "NOT_RECORDED"
    else:
        checks = [
            value
            for value in (
                config_captured_match if isinstance(config_captured_match, bool) else None,
                independent_match,
                (
                    str(config_expected).upper() == str(config_captured_actual).upper()
                    if config_expected is not None and config_captured_actual is not None
                    else None
                ),
            )
            if value is not None
        ]
        config_status = "PASS" if checks and all(checks) else "FAIL"

    files = captured.get("files")
    code_summary = match_record_summary(files)
    return {
        "config_seal_status": config_status,
        "config_expected_sha256": str(config_expected).upper() if config_expected else independent_expected,
        "config_captured_actual_sha256": (
            str(config_captured_actual).upper() if config_captured_actual else None
        ),
        "config_independent_actual_sha256": independent_actual,
        "config_hash_file_sha256": independent_expected,
        "config_independent_match": independent_match,
        "code_seal_status": code_summary["status"],
        "code_seal_match_count": code_summary["match_count"],
        "code_seal_total_count": code_summary["total_count"],
        "code_seal_summary": code_summary["summary"],
        "captured_code_files": files if isinstance(files, list) else [],
    }


def choose_route_snapshot(route_root: Path) -> dict[str, Any] | None:
    candidates: list[dict[str, Any]] = []
    configured_without_status: list[str] = []
    if not route_root.is_dir():
        return None
    for replicate_dir in route_root.iterdir():
        if not replicate_dir.is_dir() or replicate_number(replicate_dir.name) < 0:
            continue
        metadata_dir = replicate_dir / "metadata"
        status_path = metadata_dir / "run_status.json"
        config_path = metadata_dir / "run_config.json"
        if status_path.is_file():
            candidates.append(
                {
                    "replicate": replicate_dir.name,
                    "replicate_number": replicate_number(replicate_dir.name),
                    "replicate_dir": replicate_dir,
                    "metadata_dir": metadata_dir,
                    "status_path": status_path,
                }
            )
        elif config_path.is_file():
            configured_without_status.append(replicate_dir.name)
    if not candidates:
        return {
            "selected": None,
            "configured_without_status": sorted(
                configured_without_status, key=replicate_number
            ),
        }
    selected = max(candidates, key=lambda item: item["replicate_number"])
    return {
        "selected": selected,
        "configured_without_status": sorted(
            configured_without_status, key=replicate_number
        ),
    }


def summarize_route(
    route_spec: dict[str, str], runs_root: Path, board_root: Path
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    route_id = route_spec["route_id"]
    route_root = runs_root / route_id / "original_mlx"
    snapshot = choose_route_snapshot(route_root)
    if snapshot is None or snapshot.get("selected") is None:
        row = {
            "route_id": route_id,
            "route_name": route_spec["route_name"],
            "selected_replicate": None,
            "audit_state": "PENDING",
            "final_status": "NO_RUN_STATUS",
            "execution_status": "NOT_EVALUATED",
            "evidence_status": "NOT_EVALUATED",
            "actual_matlab_returncode": None,
            "timed_out": None,
            "actual_scan_point_count": None,
            "actual_stab_shape": None,
            "runtime_dlqr_reached": None,
            "input_hashes_before": "NOT_RECORDED",
            "input_hashes_after": "NOT_RECORDED",
            "config_seal_status": "NOT_RECORDED",
            "code_seal_status": "NOT_RECORDED",
            "process_status_consistency": "NOT_EVALUATED",
            "error_identifier": None,
            "error_message": None,
            "status_sha256": None,
            "process_exit_sha256": None,
            "raw_stab_sha256": None,
            "configured_replicates_without_status": ";".join(
                (snapshot or {}).get("configured_without_status", [])
            ),
            "evidence_paths": {},
        }
        return row, None

    selected = snapshot["selected"]
    status_path: Path = selected["status_path"]
    metadata_dir: Path = selected["metadata_dir"]
    replicate_dir: Path = selected["replicate_dir"]
    process_path = metadata_dir / "process_exit.json"
    status = read_json(status_path)
    process_exit = read_json(process_path) if process_path.is_file() else None

    final_status = str(status.get("final_status") or "NOT_RECORDED")
    terminal_status = final_status not in {
        "RUNNING",
        "NOT_STARTED",
        "NOT_RECORDED",
        "PENDING",
    }
    terminal = terminal_status and process_exit is not None
    audit_state = "TERMINAL" if terminal else "PENDING"

    before = match_record_summary(status.get("input_hashes_before"))
    after = match_record_summary(status.get("input_hashes_after"))
    instrumentation = instrumentation_summary(status, process_exit, metadata_dir)

    returncode = None
    timed_out = None
    consistency = "NOT_EVALUATED"
    if process_exit is not None:
        returncode = process_exit.get("actual_matlab_returncode")
        timed_out = process_exit.get("timed_out")
        consistency_obj = process_exit.get("status_returncode_consistency")
        if isinstance(consistency_obj, dict):
            consistency = str(consistency_obj.get("result") or "NOT_RECORDED")

    raw_path = replicate_dir / "scientific" / "raw_stab.mat"
    raw_sha = sha256_file(raw_path) if terminal and raw_path.is_file() else None
    actual_shape = status.get("actual_stab_shape")
    if isinstance(actual_shape, list):
        actual_shape_text = "x".join(str(value) for value in actual_shape)
    else:
        actual_shape_text = None

    error = status.get("error") if isinstance(status.get("error"), dict) else {}
    row = {
        "route_id": route_id,
        "route_name": route_spec["route_name"],
        "selected_replicate": selected["replicate"],
        "audit_state": audit_state,
        "final_status": final_status,
        "execution_status": status.get("execution_status"),
        "evidence_status": status.get("evidence_status"),
        "actual_matlab_returncode": returncode,
        "timed_out": timed_out,
        "actual_scan_point_count": status.get("actual_scan_point_count"),
        "actual_stab_shape": actual_shape_text,
        "runtime_dlqr_reached": status.get("runtime_dlqr_reached"),
        "input_hashes_before": before["summary"],
        "input_hashes_after": after["summary"],
        "config_seal_status": instrumentation["config_seal_status"],
        "code_seal_status": instrumentation["code_seal_summary"],
        "process_status_consistency": consistency,
        "error_identifier": error.get("identifier"),
        "error_message": error.get("message"),
        "status_sha256": sha256_file(status_path),
        "process_exit_sha256": sha256_file(process_path) if process_path.is_file() else None,
        "raw_stab_sha256": raw_sha,
        "configured_replicates_without_status": ";".join(
            snapshot.get("configured_without_status", [])
        ),
        "evidence_paths": {
            "status": relative_to_board(status_path, board_root),
            "process_exit": (
                relative_to_board(process_path, board_root)
                if process_path.is_file()
                else None
            ),
            "raw_stab": (
                relative_to_board(raw_path, board_root) if raw_path.is_file() else None
            ),
        },
        "input_hash_details": {
            "before": before,
            "after": after,
        },
        "instrumentation_details": instrumentation,
        "status_snapshot": {
            "schema": status.get("schema"),
            "started_at": status.get("started_at"),
            "finished_at": status.get("finished_at"),
            "declared_method": status.get("declared_method"),
            "declared_division": status.get("declared_division"),
            "actual_code_identity": status.get("actual_code_identity"),
            "expected_scan_point_count": status.get("expected_scan_point_count"),
            "expected_stab_shape": status.get("expected_stab_shape"),
            "scan_evidence": status.get("scan_evidence"),
        },
    }
    return row, status


def load_mat_variable(path: Path, variable: str) -> tuple[np.ndarray, str]:
    """读取 MATLAB v5 或 v7.3 数值变量，并恢复 MATLAB 维度顺序。"""
    try:
        data = scipy.io.loadmat(path)
        if variable not in data:
            raise KeyError(f"MAT 文件中不存在变量 {variable}: {path}")
        return np.asarray(data[variable]), "scipy.io.loadmat (MATLAB v5)"
    except (NotImplementedError, ValueError, OSError) as scipy_error:
        try:
            with h5py.File(path, "r") as handle:
                if variable not in handle:
                    raise KeyError(f"MATLAB 7.3 文件中不存在变量 {variable}: {path}")
                dataset = handle[variable]
                if not isinstance(dataset, h5py.Dataset):
                    raise TypeError(f"变量 {variable} 不是直接数值数据集: {path}")
                array = np.asarray(dataset)
                if array.dtype.fields and {"real", "imag"}.issubset(array.dtype.fields):
                    array = array["real"] + 1j * array["imag"]
                if array.ndim > 1:
                    array = np.transpose(array, axes=tuple(reversed(range(array.ndim))))
                return array, "h5py (MATLAB 7.3; reversed storage axes)"
        except OSError as hdf_error:
            raise ValueError(
                f"无法按 MATLAB v5 或 v7.3 读取 {path}; "
                f"scipy={scipy_error!r}; h5py={hdf_error!r}"
            ) from hdf_error


def valid_domain_mask(shape: tuple[int, int] = VALID_SHAPE) -> np.ndarray:
    if shape[0] < VALID_SHAPE[0] or shape[1] < VALID_SHAPE[1]:
        raise ValueError(f"网格 {shape} 小于固定有效域 {VALID_SHAPE}")
    mask = np.zeros(shape, dtype=bool)
    for row_slice, column_slice in VALID_SEGMENTS_PYTHON:
        mask[row_slice, column_slice] = True
    if int(np.count_nonzero(mask)) != VALID_POINT_COUNT:
        raise AssertionError("四段固定有效域点数不是 1517")
    return mask


def find_historical_manifest_record(
    manifest_path: Path, frozen_relative_path: str
) -> dict[str, str] | None:
    target = frozen_relative_path.replace("\\", "/")
    with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            candidate = str(row.get("frozen_relative_path") or "").replace("\\", "/")
            if candidate == target:
                return dict(row)
    return None


def load_historical_reference(
    board_root: Path,
) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, str]]:
    relative_path = Path("input") / "historical_plotting" / "作者绘图目录" / "lqr_3.mat"
    path = board_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"冻结历史基准不存在: {path}")
    manifest_path = board_root / "input" / "input_manifest.csv"
    manifest_record = find_historical_manifest_record(
        manifest_path, "historical_plotting/作者绘图目录/lqr_3.mat"
    )
    actual_sha = sha256_file(path)
    expected_sha = (
        str(manifest_record.get("frozen_sha256") or "").upper()
        if manifest_record
        else None
    )
    arrays: dict[str, np.ndarray] = {}
    loaders: dict[str, str] = {}
    for variable in ("stab_o", "stab_g"):
        arrays[variable], loaders[variable] = load_mat_variable(path, variable)
    metadata = {
        "path": relative_to_board(path, board_root),
        "sha256": actual_sha,
        "manifest_expected_sha256": expected_sha,
        "manifest_hash_match": actual_sha == expected_sha if expected_sha else None,
        "manifest_item_id": manifest_record.get("item_id") if manifest_record else None,
        "stable_rule": "finite and 0 < historical_value < 1",
        "variables": {
            variable: {
                "shape": list(arrays[variable].shape),
                "loader": loaders[variable],
            }
            for variable in arrays
        },
    }
    return metadata, arrays, loaders


def load_first_division_historical_reference(
    board_root: Path,
) -> tuple[dict[str, Any], np.ndarray, str]:
    """读取第一类划分历史绘图文件，并固定 Guyan 左上 21×21 掩码。"""
    relative_path = Path("input") / "historical_plotting" / "作者绘图目录" / "lqr_2.mat"
    path = board_root / relative_path
    if not path.is_file():
        raise FileNotFoundError(f"冻结的第一类划分历史基准不存在: {path}")
    manifest_path = board_root / "input" / "input_manifest.csv"
    frozen_relative = "historical_plotting/作者绘图目录/lqr_2.mat"
    manifest_record = find_historical_manifest_record(manifest_path, frozen_relative)
    actual_sha = sha256_file(path)
    expected_sha = (
        str(manifest_record.get("frozen_sha256") or "").upper()
        if manifest_record
        else None
    )
    historical, loader = load_mat_variable(path, "stab_g")
    historical = np.asarray(np.real_if_close(historical), dtype=float)
    if (
        historical.shape[0] < FIRST_DIVISION_SHAPE[0]
        or historical.shape[1] < FIRST_DIVISION_SHAPE[1]
    ):
        raise ValueError(
            f"历史 stab_g 形状 {historical.shape} 无法覆盖第一类划分 21×21 网格"
        )
    metadata = {
        "path": relative_to_board(path, board_root),
        "sha256": actual_sha,
        "manifest_expected_sha256": expected_sha,
        "manifest_hash_match": actual_sha == expected_sha if expected_sha else None,
        "manifest_item_id": manifest_record.get("item_id") if manifest_record else None,
        "variable": "stab_g",
        "full_shape": list(historical.shape),
        "comparison_slice_matlab_1_based_inclusive": "rows 1:21, columns 1:21",
        "comparison_shape": list(FIRST_DIVISION_SHAPE),
        "comparison_point_count": FIRST_DIVISION_POINT_COUNT,
        "stable_rule": "finite and 0 < historical_value < 1",
        "loader": loader,
    }
    return metadata, historical, loader


def compare_route_to_historical(
    route: dict[str, Any],
    board_root: Path,
    historical_metadata: dict[str, Any],
    historical_arrays: dict[str, np.ndarray],
    historical_loaders: dict[str, str],
) -> tuple[dict[str, Any], np.ndarray | None, np.ndarray | None]:
    route_id = str(route["route_id"])
    mapping = HISTORICAL_MASK_MAP[route_id]
    base = {
        "route_id": route_id,
        "route_name": route["route_name"],
        "method_label": mapping["method_label"],
        "selected_replicate": route.get("selected_replicate"),
        "comparison_status": "PENDING",
        "historical_file": historical_metadata["path"],
        "historical_variable": mapping["historical_variable"],
        "historical_shape": None,
        "raw_shape": None,
        "valid_point_count": VALID_POINT_COUNT,
        "raw_finite_count": None,
        "raw_positive_count": None,
        "rho_lt_1_count": None,
        "rho_positive_lt_1_count": None,
        "raw_minimum": None,
        "raw_maximum": None,
        "TP": None,
        "FP": None,
        "FN": None,
        "TN": None,
        "mismatch_count": None,
        "accuracy": None,
        "historical_stable_total": None,
        "historical_stable_inside_valid_domain": None,
        "historical_stable_outside_valid_domain": None,
        "raw_stab_sha256": route.get("raw_stab_sha256"),
        "historical_sha256": historical_metadata["sha256"],
        "mat_loader": None,
        "reason": None,
    }
    if route.get("audit_state") != "TERMINAL":
        base["reason"] = "路线尚无终态 process_exit.json；完成后重跑本脚本"
        return base, None, None
    if route.get("final_status") != "SUCCESS":
        base["comparison_status"] = "NOT_AVAILABLE"
        base["reason"] = f"路线终态为 {route.get('final_status')}，没有成功的完整谱半径网格"
        return base, None, None

    raw_relative = route.get("evidence_paths", {}).get("raw_stab")
    if not raw_relative:
        base["comparison_status"] = "ERROR"
        base["reason"] = "成功状态缺少 scientific/raw_stab.mat"
        return base, None, None
    raw_path = board_root / Path(raw_relative)
    try:
        raw, raw_loader = load_mat_variable(raw_path, "stab")
        raw = np.asarray(np.real_if_close(raw), dtype=float)
        if raw.shape != VALID_SHAPE:
            raise ValueError(f"raw_stab 形状为 {raw.shape}，预期为 {VALID_SHAPE}")
        variable = mapping["historical_variable"]
        historical = np.asarray(np.real_if_close(historical_arrays[variable]), dtype=float)
        if historical.shape[0] < VALID_SHAPE[0] or historical.shape[1] < VALID_SHAPE[1]:
            raise ValueError(
                f"历史变量 {variable} 形状 {historical.shape} 无法覆盖 26×67 固定有效域"
            )
        raw_mask = valid_domain_mask(raw.shape)
        historical_domain_mask = valid_domain_mask(historical.shape)
        raw_values = raw[raw_mask]
        historical_values = historical[: VALID_SHAPE[0], : VALID_SHAPE[1]][raw_mask]

        raw_finite = np.isfinite(raw_values)
        raw_positive = raw_finite & (raw_values > 0.0)
        raw_stable = raw_finite & (raw_values < 1.0)
        raw_positive_stable = raw_positive & (raw_values < 1.0)
        historical_stable_values = (
            np.isfinite(historical_values)
            & (historical_values > 0.0)
            & (historical_values < 1.0)
        )
        historical_stable_full = (
            np.isfinite(historical) & (historical > 0.0) & (historical < 1.0)
        )

        tp = int(np.count_nonzero(raw_positive_stable & historical_stable_values))
        fp = int(np.count_nonzero(raw_positive_stable & ~historical_stable_values))
        fn = int(np.count_nonzero(~raw_positive_stable & historical_stable_values))
        tn = int(np.count_nonzero(~raw_positive_stable & ~historical_stable_values))
        if tp + fp + fn + tn != VALID_POINT_COUNT:
            raise AssertionError("混淆矩阵总数不是 1517")

        historical_total = int(np.count_nonzero(historical_stable_full))
        historical_inside = int(
            np.count_nonzero(historical_stable_full & historical_domain_mask)
        )
        historical_outside = historical_total - historical_inside
        finite_values = raw_values[raw_finite]
        base.update(
            {
                "comparison_status": "READY",
                "historical_shape": "x".join(str(value) for value in historical.shape),
                "raw_shape": "x".join(str(value) for value in raw.shape),
                "raw_finite_count": int(np.count_nonzero(raw_finite)),
                "raw_positive_count": int(np.count_nonzero(raw_positive)),
                "rho_lt_1_count": int(np.count_nonzero(raw_stable)),
                "rho_positive_lt_1_count": int(np.count_nonzero(raw_positive_stable)),
                "raw_minimum": float(np.min(finite_values)) if finite_values.size else None,
                "raw_maximum": float(np.max(finite_values)) if finite_values.size else None,
                "TP": tp,
                "FP": fp,
                "FN": fn,
                "TN": tn,
                "mismatch_count": fp + fn,
                "accuracy": (tp + tn) / VALID_POINT_COUNT,
                "historical_stable_total": historical_total,
                "historical_stable_inside_valid_domain": historical_inside,
                "historical_stable_outside_valid_domain": historical_outside,
                "mat_loader": f"raw={raw_loader}; historical={historical_loaders[variable]}",
                "reason": None,
            }
        )
        return base, raw, raw_positive_stable
    except Exception as error:  # 审计需保留证据缺口，而不是吞掉整张汇总表。
        base["comparison_status"] = "ERROR"
        base["reason"] = f"{type(error).__name__}: {error}"
        return base, None, None


def load_success_route_raw(
    route: dict[str, Any], board_root: Path, expected_shape: tuple[int, int]
) -> tuple[np.ndarray, str]:
    if route.get("audit_state") != "TERMINAL":
        raise ValueError(f"路线 {route.get('route_id')} 尚无进程终态")
    if route.get("final_status") != "SUCCESS":
        raise ValueError(
            f"路线 {route.get('route_id')} 终态为 {route.get('final_status')}，不是 SUCCESS"
        )
    raw_relative = route.get("evidence_paths", {}).get("raw_stab")
    if not raw_relative:
        raise FileNotFoundError(f"路线 {route.get('route_id')} 缺少 scientific/raw_stab.mat")
    raw, loader = load_mat_variable(board_root / Path(raw_relative), "stab")
    raw = np.asarray(np.real_if_close(raw), dtype=float)
    if raw.shape != expected_shape:
        raise ValueError(
            f"路线 {route.get('route_id')} 的 raw_stab 形状为 {raw.shape}，预期为 {expected_shape}"
        )
    return raw, loader


def compare_first_division_candidate_to_historical(
    route: dict[str, Any],
    board_root: Path,
    historical_metadata: dict[str, Any],
    historical: np.ndarray,
    historical_loader: str,
) -> tuple[dict[str, Any], np.ndarray | None, np.ndarray | None]:
    """逐格比较备用候选与 lqr_2.mat 中 Guyan 第一类划分掩码。"""
    base = {
        "route_id": route["route_id"],
        "route_name": route["route_name"],
        "method_label": "Guyan 第一类划分备用候选",
        "selected_replicate": route.get("selected_replicate"),
        "comparison_status": "PENDING",
        "historical_file": historical_metadata["path"],
        "historical_variable": "stab_g[1:21,1:21]",
        "historical_shape": "x".join(str(value) for value in historical.shape),
        "raw_shape": None,
        "valid_point_count": FIRST_DIVISION_POINT_COUNT,
        "raw_finite_count": None,
        "raw_positive_count": None,
        "rho_lt_1_count": None,
        "rho_positive_lt_1_count": None,
        "raw_minimum": None,
        "raw_maximum": None,
        "TP": None,
        "FP": None,
        "FN": None,
        "TN": None,
        "mismatch_count": None,
        "accuracy": None,
        "historical_stable_total": None,
        "historical_stable_inside_valid_domain": None,
        "historical_stable_outside_valid_domain": None,
        "raw_stab_sha256": route.get("raw_stab_sha256"),
        "historical_sha256": historical_metadata["sha256"],
        "mat_loader": None,
        "reason": None,
    }
    try:
        raw, raw_loader = load_success_route_raw(
            route, board_root, FIRST_DIVISION_SHAPE
        )
        historical_slice = historical[
            : FIRST_DIVISION_SHAPE[0], : FIRST_DIVISION_SHAPE[1]
        ]
        raw_values = raw.reshape(-1)
        historical_values = historical_slice.reshape(-1)
        raw_finite = np.isfinite(raw_values)
        raw_positive = raw_finite & (raw_values > 0.0)
        raw_stable = raw_finite & (raw_values < 1.0)
        raw_positive_stable = raw_positive & (raw_values < 1.0)
        historical_stable_values = (
            np.isfinite(historical_values)
            & (historical_values > 0.0)
            & (historical_values < 1.0)
        )
        historical_stable_full = (
            np.isfinite(historical) & (historical > 0.0) & (historical < 1.0)
        )
        tp = int(np.count_nonzero(raw_positive_stable & historical_stable_values))
        fp = int(np.count_nonzero(raw_positive_stable & ~historical_stable_values))
        fn = int(np.count_nonzero(~raw_positive_stable & historical_stable_values))
        tn = int(np.count_nonzero(~raw_positive_stable & ~historical_stable_values))
        if tp + fp + fn + tn != FIRST_DIVISION_POINT_COUNT:
            raise AssertionError("第一类划分混淆矩阵总数不是 441")
        full_stable = int(np.count_nonzero(historical_stable_full))
        inside_stable = int(np.count_nonzero(historical_stable_values))
        finite_values = raw_values[raw_finite]
        base.update(
            {
                "comparison_status": "READY",
                "raw_shape": "x".join(str(value) for value in raw.shape),
                "raw_finite_count": int(np.count_nonzero(raw_finite)),
                "raw_positive_count": int(np.count_nonzero(raw_positive)),
                "rho_lt_1_count": int(np.count_nonzero(raw_stable)),
                "rho_positive_lt_1_count": int(np.count_nonzero(raw_positive_stable)),
                "raw_minimum": float(np.min(finite_values)) if finite_values.size else None,
                "raw_maximum": float(np.max(finite_values)) if finite_values.size else None,
                "TP": tp,
                "FP": fp,
                "FN": fn,
                "TN": tn,
                "mismatch_count": fp + fn,
                "accuracy": (tp + tn) / FIRST_DIVISION_POINT_COUNT,
                "historical_stable_total": full_stable,
                "historical_stable_inside_valid_domain": inside_stable,
                "historical_stable_outside_valid_domain": full_stable - inside_stable,
                "mat_loader": f"raw={raw_loader}; historical={historical_loader}",
            }
        )
        return base, raw, raw_positive_stable.reshape(FIRST_DIVISION_SHAPE)
    except Exception as error:
        base["comparison_status"] = "ERROR"
        base["reason"] = f"{type(error).__name__}: {error}"
        return base, None, None


def compare_first_division_candidate_to_main(
    candidate_raw: np.ndarray | None,
    candidate_stable: np.ndarray | None,
    main_route: dict[str, Any],
    board_root: Path,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "comparison_status": "PENDING",
        "left_route_id": ALTERNATIVE_ROUTE["route_id"],
        "right_route_id": "main_guyan_div1",
        "valid_point_count": FIRST_DIVISION_POINT_COUNT,
        "finite_pair_count": None,
        "exact_equal_count": None,
        "nonzero_difference_count": None,
        "absolute_difference_gt_1e_12_count": None,
        "maximum_absolute_difference": None,
        "mean_absolute_difference": None,
        "rms_difference": None,
        "allclose_rtol_0_atol_1e_12": None,
        "stable_mask_disagreement_count": None,
        "reason": None,
    }
    try:
        if candidate_raw is None or candidate_stable is None:
            raise ValueError("备用候选没有可比较的完整 raw_stab")
        main_raw, _ = load_success_route_raw(
            main_route, board_root, FIRST_DIVISION_SHAPE
        )
        candidate_values = candidate_raw.reshape(-1)
        main_values = main_raw.reshape(-1)
        finite_pairs = np.isfinite(candidate_values) & np.isfinite(main_values)
        difference = candidate_values[finite_pairs] - main_values[finite_pairs]
        absolute = np.abs(difference)
        main_stable = (
            np.isfinite(main_raw) & (main_raw > 0.0) & (main_raw < 1.0)
        )
        row.update(
            {
                "comparison_status": "READY",
                "finite_pair_count": int(np.count_nonzero(finite_pairs)),
                "exact_equal_count": int(np.count_nonzero(difference == 0.0)),
                "nonzero_difference_count": int(np.count_nonzero(difference != 0.0)),
                "absolute_difference_gt_1e_12_count": int(
                    np.count_nonzero(absolute > 1.0e-12)
                ),
                "maximum_absolute_difference": (
                    float(np.max(absolute)) if absolute.size else None
                ),
                "mean_absolute_difference": (
                    float(np.mean(absolute)) if absolute.size else None
                ),
                "rms_difference": (
                    float(math.sqrt(float(np.mean(difference**2))))
                    if difference.size
                    else None
                ),
                "allclose_rtol_0_atol_1e_12": bool(
                    np.allclose(
                        candidate_raw,
                        main_raw,
                        rtol=0.0,
                        atol=1.0e-12,
                        equal_nan=True,
                    )
                ),
                "stable_mask_disagreement_count": int(
                    np.count_nonzero(candidate_stable != main_stable)
                ),
            }
        )
    except Exception as error:
        row["comparison_status"] = "ERROR"
        row["reason"] = f"{type(error).__name__}: {error}"
    return row


def compare_raw_routes(
    raw_arrays: dict[str, np.ndarray], stable_masks: dict[str, np.ndarray]
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "comparison_status": "PENDING",
        "left_route_id": "main_ori_div2",
        "right_route_id": "main_guyan_div2",
        "valid_point_count": VALID_POINT_COUNT,
        "finite_pair_count": None,
        "exact_equal_count": None,
        "nonzero_difference_count": None,
        "absolute_difference_gt_1e_12_count": None,
        "maximum_absolute_difference": None,
        "mean_absolute_difference": None,
        "rms_difference": None,
        "allclose_rtol_0_atol_1e_12": None,
        "stable_mask_disagreement_count": None,
        "reason": None,
    }
    missing = [
        route_id
        for route_id in ("main_ori_div2", "main_guyan_div2")
        if route_id not in raw_arrays
    ]
    if missing:
        row["reason"] = "缺少可比较的完整 raw_stab: " + ", ".join(missing)
        return row
    try:
        valid = valid_domain_mask(VALID_SHAPE)
        left = raw_arrays["main_ori_div2"][valid]
        right = raw_arrays["main_guyan_div2"][valid]
        finite_pairs = np.isfinite(left) & np.isfinite(right)
        difference = left[finite_pairs] - right[finite_pairs]
        absolute = np.abs(difference)
        exact = int(np.count_nonzero(difference == 0.0))
        row.update(
            {
                "comparison_status": "READY",
                "finite_pair_count": int(np.count_nonzero(finite_pairs)),
                "exact_equal_count": exact,
                "nonzero_difference_count": int(np.count_nonzero(difference != 0.0)),
                "absolute_difference_gt_1e_12_count": int(
                    np.count_nonzero(absolute > 1.0e-12)
                ),
                "maximum_absolute_difference": (
                    float(np.max(absolute)) if absolute.size else None
                ),
                "mean_absolute_difference": (
                    float(np.mean(absolute)) if absolute.size else None
                ),
                "rms_difference": (
                    float(math.sqrt(float(np.mean(difference**2))))
                    if difference.size
                    else None
                ),
                "allclose_rtol_0_atol_1e_12": bool(
                    np.allclose(left, right, rtol=0.0, atol=1.0e-12, equal_nan=True)
                ),
                "stable_mask_disagreement_count": int(
                    np.count_nonzero(
                        stable_masks["main_ori_div2"]
                        != stable_masks["main_guyan_div2"]
                    )
                ),
                "reason": None,
            }
        )
    except Exception as error:
        row["comparison_status"] = "ERROR"
        row["reason"] = f"{type(error).__name__}: {error}"
    return row


def csv_ready(row: dict[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    ready: dict[str, Any] = {}
    for field in fields:
        value = row.get(field)
        if isinstance(value, bool):
            ready[field] = "TRUE" if value else "FALSE"
        elif value is None:
            ready[field] = ""
        else:
            ready[field] = value
    return ready


def write_csv(path: Path, fields: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(csv_ready(row, fields))


def markdown_cell(value: Any) -> str:
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    text = str(value).replace("\r", " ").replace("\n", " ").replace("|", "\\|")
    return text


def render_markdown(
    script_path: Path,
    board_root: Path,
    route_rows: list[dict[str, Any]],
    alternative_route: dict[str, Any],
    mask_rows: list[dict[str, Any]],
    alternative_mask: dict[str, Any],
    raw_difference: dict[str, Any],
    alternative_difference: dict[str, Any],
    historical_metadata: dict[str, Any],
    first_division_historical_metadata: dict[str, Any],
    validation: dict[str, Any],
) -> str:
    lines = [
        "# 板块20步骤2：八条原始路线与一条备用候选统一审计草稿",
        "",
        "## 人话结论",
        "",
    ]
    terminal_count = sum(row["audit_state"] == "TERMINAL" for row in route_rows)
    pending_names = [row["route_name"] for row in route_rows if row["audit_state"] == "PENDING"]
    lines.append(
        f"八条预定原始路线中，当前有 **{terminal_count}/8** 条具有 MATLAB 进程终态和 `process_exit.json`。"
    )
    lines.append(
        "另有 **1 条预先登记的 Guyan 第一类划分备用候选**，以下始终单独列示，"
        "不计入八条主路线的分母或成功/失败统计。"
    )
    if pending_names:
        lines.append(
            "仍待完成：" + "；".join(pending_names) + "。本次汇总将其标为 `PENDING`，没有把中间检查点当成最终结果。"
        )
    ready_masks = [row for row in mask_rows if row["comparison_status"] == "READY"]
    if ready_masks:
        for row in ready_masks:
            lines.append(
                f"{row['method_label']}第二类划分的原始谱半径在 1,517 个固定有效点中有 "
                f"{row['rho_lt_1_count']} 个满足 `rho < 1`；与历史 `{row['historical_variable']}` "
                f"掩码相比，错位 {row['mismatch_count']} 点。"
            )
    if raw_difference["comparison_status"] == "PENDING":
        lines.append("原结构命名路线与 Guyan 路线的逐点谱半径差尚不能计算；待两条路线均形成终态后重跑即可自动补齐。")
    elif raw_difference["comparison_status"] == "READY":
        lines.append(
            "原结构命名路线与 Guyan 路线在固定有效域的最大逐点绝对差为 "
            f"`{raw_difference['maximum_absolute_difference']:.16g}`。"
        )
    if alternative_mask["comparison_status"] == "READY":
        lines.append(
            "备用候选在第一类划分 441 个点中有 "
            f"{alternative_mask['rho_positive_lt_1_count']} 个有限正谱半径满足 `rho < 1`；"
            f"与历史 `lqr_2.mat/stab_g(1:21,1:21)` 错位 {alternative_mask['mismatch_count']} 点。"
        )

    lines.extend(
        [
            "",
            "## 固定审计口径",
            "",
            "- `计算级复现`：原始 MLX 已由独立 MATLAB 进程运行，并保留终态、返回码、输入前后哈希和科学数组。",
            "- `绘图级复现`：这里仅用历史最终掩码进行逐点核对；错位不为 0 时，不得宣称历史图的数据生成路线已经闭合。",
            "- `历史值`：冻结的 `lqr_3.mat` 中 `stab_o` 或 `stab_g`；稳定判据固定为有限且 `0 < value < 1`。",
            "- `待决定`：没有进程终态的路线一律保留为 `PENDING`，不读取正在形成的工作目录检查点。",
            "- 新计算稳定判据：固定有效域内有限且 `rho < 1`；另列 `0 < rho < 1` 数，以排除未计算零值。",
            "- 固定有效域：MATLAB 索引 `(1:21,1:21)`、`(1:26,22:41)`、`(1:26,42:61)`、`(1:6,62:67)`，合计 1,517 点。",
            "- 备用候选比较域：仅 MATLAB 索引 `(1:21,1:21)`，恰为 21×21=441 点；没有把 `lqr_2.mat` 的其余区域塞进第一类划分计算。",
            "- 备用候选输入边界：`New_Ps3.m` 原生物理矩阵为 9×9，但原始候选 MLX 只抽取前 6 维；本审计仅忠实记录，不把它解释成论文理论闭合。",
            "",
            "## 八条原始路线状态",
            "",
            "| 原始路线 | 副本 | 审计状态 | 最终状态 | 执行状态 | 证据状态 | MATLAB返回码 | 点数 | 形状 | 实际到达dlqr | 输入运行前 | 输入运行后 | 配置封印 | 代码封印 |",
            "|---|---:|---|---|---|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    for row in route_rows:
        values = (
            row["route_name"],
            row["selected_replicate"],
            row["audit_state"],
            row["final_status"],
            row["execution_status"],
            row["evidence_status"],
            row["actual_matlab_returncode"],
            row["actual_scan_point_count"],
            row["actual_stab_shape"],
            row["runtime_dlqr_reached"],
            row["input_hashes_before"],
            row["input_hashes_after"],
            row["config_seal_status"],
            row["code_seal_status"],
        )
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")

    failed = [row for row in route_rows if row["final_status"] == "EXECUTION_FAIL"]
    if failed:
        lines.extend(["", "### 原脚本真实失败点", ""])
        for row in failed:
            lines.append(
                f"- {row['route_name']}：`{markdown_cell(row['error_identifier'])}`；"
                f"{markdown_cell(row['error_message'])}"
            )

    lines.extend(
        [
            "",
            "## 第一类划分备用候选（不计入八条主路线）",
            "",
            "| 候选路线 | 副本 | 审计状态 | 最终状态 | MATLAB返回码 | 点数 | 形状 | 实际到达dlqr | 输入运行前 | 输入运行后 | 配置封印 | 代码封印 |",
            "|---|---:|---|---|---:|---:|---|---|---|---|---|---|",
        ]
    )
    alternative_values = (
        alternative_route["route_name"],
        alternative_route["selected_replicate"],
        alternative_route["audit_state"],
        alternative_route["final_status"],
        alternative_route["actual_matlab_returncode"],
        alternative_route["actual_scan_point_count"],
        alternative_route["actual_stab_shape"],
        alternative_route["runtime_dlqr_reached"],
        alternative_route["input_hashes_before"],
        alternative_route["input_hashes_after"],
        alternative_route["config_seal_status"],
        alternative_route["code_seal_status"],
    )
    lines.append(
        "| " + " | ".join(markdown_cell(value) for value in alternative_values) + " |"
    )
    lines.extend(
        [
            "",
            "### 与 `lqr_2.mat` 的 Guyan 第一类划分历史掩码逐格比较",
            "",
            "| 状态 | 新计算稳定点 | TP | FP | FN | TN | 错位点 | 历史 21×21 稳定点 | 历史其余区域稳定点 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    alternative_mask_values = (
        alternative_mask["comparison_status"],
        alternative_mask["rho_positive_lt_1_count"],
        alternative_mask["TP"],
        alternative_mask["FP"],
        alternative_mask["FN"],
        alternative_mask["TN"],
        alternative_mask["mismatch_count"],
        alternative_mask["historical_stable_inside_valid_domain"],
        alternative_mask["historical_stable_outside_valid_domain"],
    )
    lines.append(
        "| "
        + " | ".join(markdown_cell(value) for value in alternative_mask_values)
        + " |"
    )
    if alternative_mask.get("reason"):
        lines.append(f"\n备用候选历史比较说明：{alternative_mask['reason']}\n")

    lines.extend(
        [
            "",
            "### 与 Guyan 第一类划分主路线逐格比较",
            "",
        ]
    )
    if alternative_difference["comparison_status"] == "READY":
        lines.extend(
            [
                f"- 有限点对：{alternative_difference['finite_pair_count']}/{FIRST_DIVISION_POINT_COUNT}。",
                f"- 完全相等点：{alternative_difference['exact_equal_count']}；非零差点：{alternative_difference['nonzero_difference_count']}。",
                f"- 最大绝对差：`{alternative_difference['maximum_absolute_difference']:.16g}`。",
                f"- 平均绝对差：`{alternative_difference['mean_absolute_difference']:.16g}`。",
                f"- 均方根差：`{alternative_difference['rms_difference']:.16g}`。",
                f"- 稳定/不稳定分类不同点：{alternative_difference['stable_mask_disagreement_count']}。",
            ]
        )
    else:
        lines.append(
            f"- 比较状态：`{alternative_difference['comparison_status']}`；"
            f"{alternative_difference.get('reason') or '没有补充说明'}。"
        )

    lines.extend(
        [
            "",
            "说明：`NOT_RECORDED` 表示该次较早运行没有记录相应封印字段，不等于封印校验失败。",
            "",
            "## 第二类划分：原始谱半径与历史掩码",
            "",
            "| 方法与路线 | 历史变量 | 状态 | rho<1点数 | TP | FP | FN | TN | 错位点 | 历史有效域外稳定点 |",
            "|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in mask_rows:
        values = (
            f"{row['method_label']}（{row['route_name']}）",
            row["historical_variable"],
            row["comparison_status"],
            row["rho_lt_1_count"],
            row["TP"],
            row["FP"],
            row["FN"],
            row["TN"],
            row["mismatch_count"],
            row["historical_stable_outside_valid_domain"],
        )
        lines.append("| " + " | ".join(markdown_cell(value) for value in values) + " |")
        if row.get("reason"):
            lines.append(f"\n{row['method_label']}路线说明：{row['reason']}\n")

    lines.extend(
        [
            "",
            "混淆矩阵以历史掩码为参照：TP=双方稳定，FP=新计算稳定但历史不稳定，FN=新计算不稳定但历史稳定，TN=双方不稳定。",
            "",
            "## 第二类划分：原结构命名路线与 Guyan 路线逐点差",
            "",
        ]
    )
    if raw_difference["comparison_status"] == "READY":
        lines.extend(
            [
                f"- 比较状态：`READY`，有限点对 {raw_difference['finite_pair_count']}/{VALID_POINT_COUNT}。",
                f"- 完全相等点：{raw_difference['exact_equal_count']}；非零差点：{raw_difference['nonzero_difference_count']}。",
                f"- 最大绝对差：`{raw_difference['maximum_absolute_difference']:.16g}`。",
                f"- 平均绝对差：`{raw_difference['mean_absolute_difference']:.16g}`。",
                f"- 均方根差：`{raw_difference['rms_difference']:.16g}`。",
                f"- 稳定/不稳定分类不同点：{raw_difference['stable_mask_disagreement_count']}。",
            ]
        )
    else:
        lines.append(
            f"- 比较状态：`{raw_difference['comparison_status']}`；{raw_difference.get('reason') or '没有补充说明'}。"
        )

    lines.extend(
        [
            "",
            "## 冻结历史基准与验证",
            "",
            f"- 历史文件：`{historical_metadata['path']}`。",
            f"- 实际 SHA-256：`{historical_metadata['sha256']}`。",
            f"- 与冻结清单一致：`{historical_metadata['manifest_hash_match']}`。",
            f"- 第一类划分历史文件：`{first_division_historical_metadata['path']}`。",
            f"- 第一类划分历史文件 SHA-256：`{first_division_historical_metadata['sha256']}`。",
            f"- 第一类划分历史文件与冻结清单一致：`{first_division_historical_metadata['manifest_hash_match']}`。",
            f"- 脚本 SHA-256：`{sha256_file(script_path)}`。",
            f"- 内部验证：`{validation['status']}`；八条主路线={validation['route_count']}，备用候选={validation['alternative_candidate_count']}，第二类划分掩码映射={validation['mask_comparison_count']}。",
            "",
            "## 可复跑命令",
            "",
            "```powershell",
            f"$env:PYTHONIOENCODING = \"utf-8\"",
            f"& 'D:\\Software\\python\\python.exe' '{script_path}'",
            "```",
            "",
            "输出文件：八条主路线的 `route_summary.csv`、`mask_comparison.csv`、`raw_ori_guyan_difference.csv`；备用候选单列的 `alternative_route_summary.csv`、`alternative_mask_comparison.csv`、`alternative_vs_main_difference.csv`；以及 `audit.json` 和本中文草稿。",
            "",
        ]
    )
    return "\n".join(lines)


def public_route_row(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def validate_audit(
    route_rows: list[dict[str, Any]],
    alternative_route: dict[str, Any],
    mask_rows: list[dict[str, Any]],
    alternative_mask: dict[str, Any],
    raw_difference: dict[str, Any],
    alternative_difference: dict[str, Any],
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def add(name: str, passed: bool, detail: str) -> None:
        checks.append({"name": name, "status": "PASS" if passed else "FAIL", "detail": detail})

    add("exactly_eight_routes", len(route_rows) == 8, f"count={len(route_rows)}")
    add(
        "unique_route_ids",
        len({row["route_id"] for row in route_rows}) == 8,
        "route_id 必须唯一",
    )
    add(
        "alternative_not_counted_as_primary_route",
        alternative_route["route_id"] not in {row["route_id"] for row in route_rows},
        f"primary=8; alternative={alternative_route['route_id']}",
    )
    add(
        "alternative_terminal_success",
        alternative_route["audit_state"] == "TERMINAL"
        and alternative_route["final_status"] == "SUCCESS",
        f"audit={alternative_route['audit_state']}; final={alternative_route['final_status']}",
    )
    add(
        "alternative_process_exit",
        alternative_route["actual_matlab_returncode"] == 0
        and alternative_route["timed_out"] is False
        and alternative_route["process_status_consistency"] == "PASS",
        (
            f"returncode={alternative_route['actual_matlab_returncode']}; "
            f"timed_out={alternative_route['timed_out']}; "
            f"consistency={alternative_route['process_status_consistency']}"
        ),
    )
    add(
        "alternative_grid_complete",
        alternative_route["actual_scan_point_count"] == FIRST_DIVISION_POINT_COUNT
        and alternative_route["actual_stab_shape"] == "21x21",
        (
            f"points={alternative_route['actual_scan_point_count']}; "
            f"shape={alternative_route['actual_stab_shape']}"
        ),
    )
    add(
        "alternative_input_hashes",
        alternative_route["input_hashes_before"] == "4/4 MATCH"
        and alternative_route["input_hashes_after"] == "4/4 MATCH",
        (
            f"before={alternative_route['input_hashes_before']}; "
            f"after={alternative_route['input_hashes_after']}"
        ),
    )
    add(
        "alternative_seals",
        alternative_route["config_seal_status"] == "PASS"
        and alternative_route["code_seal_status"] == "3/3 MATCH",
        (
            f"config={alternative_route['config_seal_status']}; "
            f"code={alternative_route['code_seal_status']}"
        ),
    )
    add("exactly_two_mask_mappings", len(mask_rows) == 2, f"count={len(mask_rows)}")
    for row in mask_rows:
        if row["comparison_status"] == "READY":
            confusion_total = sum(int(row[key]) for key in ("TP", "FP", "FN", "TN"))
            add(
                f"{row['route_id']}_confusion_total",
                confusion_total == VALID_POINT_COUNT,
                f"total={confusion_total}",
            )
            add(
                f"{row['route_id']}_valid_points",
                int(row["valid_point_count"]) == VALID_POINT_COUNT,
                f"valid={row['valid_point_count']}",
            )
        else:
            add(
                f"{row['route_id']}_pending_or_reported",
                row["comparison_status"] in {"PENDING", "NOT_AVAILABLE", "ERROR"},
                str(row["comparison_status"]),
            )
    if raw_difference["comparison_status"] == "READY":
        add(
            "raw_difference_point_count",
            raw_difference["finite_pair_count"] == VALID_POINT_COUNT,
            f"finite_pair_count={raw_difference['finite_pair_count']}",
        )
    else:
        add(
            "raw_difference_pending_or_reported",
            raw_difference["comparison_status"] in {"PENDING", "ERROR"},
            str(raw_difference["comparison_status"]),
        )
    if alternative_mask["comparison_status"] == "READY":
        alternative_confusion_total = sum(
            int(alternative_mask[key]) for key in ("TP", "FP", "FN", "TN")
        )
        add(
            "alternative_mask_confusion_total",
            alternative_confusion_total == FIRST_DIVISION_POINT_COUNT,
            f"total={alternative_confusion_total}",
        )
        add(
            "alternative_mask_raw_complete",
            alternative_mask["raw_finite_count"] == FIRST_DIVISION_POINT_COUNT
            and alternative_mask["raw_positive_count"] == FIRST_DIVISION_POINT_COUNT,
            (
                f"finite={alternative_mask['raw_finite_count']}; "
                f"positive={alternative_mask['raw_positive_count']}"
            ),
        )
    else:
        add(
            "alternative_mask_ready",
            False,
            str(alternative_mask["comparison_status"]),
        )
    add(
        "alternative_difference_ready",
        alternative_difference["comparison_status"] == "READY"
        and alternative_difference["finite_pair_count"] == FIRST_DIVISION_POINT_COUNT,
        (
            f"status={alternative_difference['comparison_status']}; "
            f"finite={alternative_difference['finite_pair_count']}"
        ),
    )
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    return {
        "status": status,
        "route_count": len(route_rows),
        "alternative_candidate_count": 1,
        "terminal_route_count": sum(row["audit_state"] == "TERMINAL" for row in route_rows),
        "pending_route_count": sum(row["audit_state"] == "PENDING" for row in route_rows),
        "mask_comparison_count": len(mask_rows),
        "ready_mask_comparison_count": sum(
            row["comparison_status"] == "READY" for row in mask_rows
        ),
        "checks": checks,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    default_board_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--board-root",
        type=Path,
        default=default_board_root,
        help="板块20隔离目录；默认由本脚本位置推导",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="审计输出目录；默认 <board-root>/outputs/step2_audit",
    )
    parser.add_argument(
        "--require-complete",
        action="store_true",
        help="若任一路线仍为 PENDING，则写出报告后返回退出码 2",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    board_root = args.board_root.resolve()
    runs_root = board_root / "outputs" / "step2_runs"
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else board_root / "outputs" / "step2_audit"
    )
    if not runs_root.is_dir():
        raise FileNotFoundError(f"步骤2运行产物目录不存在: {runs_root}")
    output_dir.mkdir(parents=True, exist_ok=True)

    route_rows: list[dict[str, Any]] = []
    for route_spec in ROUTES:
        row, _ = summarize_route(route_spec, runs_root, board_root)
        route_rows.append(row)
    alternative_route, _ = summarize_route(
        ALTERNATIVE_ROUTE, runs_root, board_root
    )

    historical_metadata, historical_arrays, historical_loaders = load_historical_reference(
        board_root
    )
    (
        first_division_historical_metadata,
        first_division_historical,
        first_division_historical_loader,
    ) = load_first_division_historical_reference(board_root)
    raw_arrays: dict[str, np.ndarray] = {}
    stable_masks: dict[str, np.ndarray] = {}
    mask_rows: list[dict[str, Any]] = []
    route_by_id = {row["route_id"]: row for row in route_rows}
    for route_id in ("main_ori_div2", "main_guyan_div2"):
        comparison, raw, stable_mask = compare_route_to_historical(
            route_by_id[route_id],
            board_root,
            historical_metadata,
            historical_arrays,
            historical_loaders,
        )
        mask_rows.append(comparison)
        if raw is not None and stable_mask is not None:
            raw_arrays[route_id] = raw
            stable_masks[route_id] = stable_mask

    raw_difference = compare_raw_routes(raw_arrays, stable_masks)
    alternative_mask, alternative_raw, alternative_stable = (
        compare_first_division_candidate_to_historical(
            alternative_route,
            board_root,
            first_division_historical_metadata,
            first_division_historical,
            first_division_historical_loader,
        )
    )
    alternative_difference = compare_first_division_candidate_to_main(
        alternative_raw,
        alternative_stable,
        route_by_id["main_guyan_div1"],
        board_root,
    )
    validation = validate_audit(
        route_rows,
        alternative_route,
        mask_rows,
        alternative_mask,
        raw_difference,
        alternative_difference,
    )

    payload = {
        "schema": SCHEMA,
        "board_root": str(board_root),
        "runs_root": relative_to_board(runs_root, board_root),
        "script": {
            "path": relative_to_board(Path(__file__), board_root),
            "sha256": sha256_file(Path(__file__)),
        },
        "fixed_rules": {
            "raw_stable_rule": "finite and rho < 1 within the fixed valid domain",
            "raw_positive_stable_rule_for_confusion_matrix": (
                "finite and 0 < rho < 1 within the fixed valid domain"
            ),
            "historical_stable_rule": "finite and 0 < historical_value < 1",
            "valid_shape": list(VALID_SHAPE),
            "valid_point_count": VALID_POINT_COUNT,
            "valid_segments_matlab_1_based_inclusive": list(VALID_SEGMENTS_MATLAB),
            "historical_mapping": HISTORICAL_MASK_MAP,
            "alternative_candidate": {
                "counted_in_primary_route_statistics": False,
                "route_id": ALTERNATIVE_ROUTE["route_id"],
                "comparison_shape": list(FIRST_DIVISION_SHAPE),
                "comparison_point_count": FIRST_DIVISION_POINT_COUNT,
                "historical_file": "lqr_2.mat",
                "historical_variable_and_slice": "stab_g(1:21,1:21)",
            },
            "pending_rule": (
                "highest-numbered replicate having run_status.json is PENDING unless both "
                "a terminal final_status and process_exit.json exist"
            ),
        },
        "historical_reference": historical_metadata,
        "first_division_historical_reference": first_division_historical_metadata,
        "routes": [public_route_row(row) for row in route_rows],
        "alternative_candidate": {
            "counted_in_primary_route_statistics": False,
            "route": public_route_row(alternative_route),
            "historical_mask_comparison": alternative_mask,
            "difference_from_main_guyan_div1": alternative_difference,
        },
        "mask_comparisons": mask_rows,
        "raw_ori_guyan_difference": raw_difference,
        "validation": validation,
    }

    write_csv(output_dir / "route_summary.csv", ROUTE_CSV_FIELDS, route_rows)
    write_csv(output_dir / "mask_comparison.csv", MASK_CSV_FIELDS, mask_rows)
    write_csv(
        output_dir / "raw_ori_guyan_difference.csv",
        DIFF_CSV_FIELDS,
        [raw_difference],
    )
    write_csv(
        output_dir / "alternative_route_summary.csv",
        ROUTE_CSV_FIELDS,
        [alternative_route],
    )
    write_csv(
        output_dir / "alternative_mask_comparison.csv",
        MASK_CSV_FIELDS,
        [alternative_mask],
    )
    write_csv(
        output_dir / "alternative_vs_main_difference.csv",
        DIFF_CSV_FIELDS,
        [alternative_difference],
    )
    with (output_dir / "audit.json").open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, indent=2, sort_keys=False)
        stream.write("\n")
    markdown = render_markdown(
        Path(__file__).resolve(),
        board_root,
        route_rows,
        alternative_route,
        mask_rows,
        alternative_mask,
        raw_difference,
        alternative_difference,
        historical_metadata,
        first_division_historical_metadata,
        validation,
    )
    (output_dir / "步骤2统一审计草稿.md").write_text(markdown, encoding="utf-8")

    console_summary = {
        "schema": SCHEMA,
        "output_dir": str(output_dir),
        "validation": validation["status"],
        "terminal_routes": validation["terminal_route_count"],
        "pending_routes": validation["pending_route_count"],
        "mask_statuses": {
            row["route_id"]: row["comparison_status"] for row in mask_rows
        },
        "raw_difference_status": raw_difference["comparison_status"],
        "alternative_candidate": {
            "counted_in_primary_route_statistics": False,
            "audit_state": alternative_route["audit_state"],
            "final_status": alternative_route["final_status"],
            "historical_mask_status": alternative_mask["comparison_status"],
            "difference_from_main_status": alternative_difference["comparison_status"],
        },
    }
    print(json.dumps(console_summary, ensure_ascii=False, indent=2))

    if validation["status"] != "PASS":
        return 1
    if args.require_complete and validation["pending_route_count"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

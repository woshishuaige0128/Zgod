#!/usr/bin/env python3
"""Summarise Board 20 step-4 continuous spectral-radius grids.

This analyser is deliberately read-only with respect to the route calculation
directories.  It reads the sealed route manifest, the five route status files,
the ten final author/common-grid MAT files, and the independent POSTCHECK
report.  It writes only deterministic audit artefacts under
``outputs/step4_audit``.

The five successful routes are *file-identity routes*.  They must not be
silently promoted to universal Original/Guyan/CB method claims, and this step
does not compare the historical 0/0.999 plotting masks.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

import h5py
import numpy as np
from scipy.io import loadmat


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parent.parent
CODE_ROOT = BOARD_ROOT / "code"
OUTPUT_ROOT = BOARD_ROOT / "outputs"
GRID_ROOT = OUTPUT_ROOT / "step4_rho_grids"
AUDIT_ROOT = OUTPUT_ROOT / "step4_audit"

MANIFEST_PATH = CODE_ROOT / "board20_step4_route_manifest.json"
POSTCHECK_JSON_PATH = AUDIT_ROOT / "postcheck.json"
POSTCHECK_CSV_PATH = AUDIT_ROOT / "postcheck_checks.csv"

SUMMARY_PATH = AUDIT_ROOT / "route_grid_summary.csv"
PAIR_PATH = AUDIT_ROOT / "route_pair_difference.csv"
ARTIFACT_PATH = AUDIT_ROOT / "artifact_manifest.csv"
AUDIT_PATH = AUDIT_ROOT / "audit.json"
REPORT_PATH = AUDIT_ROOT / "步骤4连续谱半径网格审计报告.md"

GRID_SPECS = (
    (
        "author_code_grid",
        "author_code_grid",
        "author_code_grid.mat",
        "作者代码网格",
    ),
    (
        "common_grid",
        "common_31x67_same_formula_candidate",
        "common_31x67_same_formula_candidate.mat",
        "统一31×67同公式补算网格",
    ),
)

SUMMARY_COLUMNS = [
    "route_id",
    "route_name",
    "route_role",
    "declared_method",
    "division",
    "route_formula",
    "grid_kind",
    "grid_label_zh",
    "mat_relpath",
    "mat_sha256",
    "mat_loader",
    "expected_shape",
    "actual_shape",
    "expected_points",
    "requested_points",
    "status_pass_points",
    "status_fail_points",
    "status_pending_points",
    "route_overall_status",
    "grid_audit_status",
    "rho_min",
    "rho_max",
    "stable_points",
    "critical_points",
    "max_pass_residual",
    "provenance_original_active_points",
    "provenance_commented_author_intent_points",
    "provenance_same_formula_supplement_points",
    "provenance_fail_points",
    "provenance_unassigned_or_unknown_points",
    "step2_compared_points",
    "step2_match_points",
    "step2_mismatch_points",
    "step2_max_abs_difference",
    "step2_classification_mismatch_points",
    "postcheck_relevant_checks",
    "postcheck_relevant_failed_checks",
]

PAIR_COLUMNS = [
    "comparison_id",
    "route_a",
    "route_b",
    "grid_kind",
    "shape_a",
    "shape_b",
    "compared_points",
    "rho_exact_equal_points",
    "rho_mismatch_points",
    "rho_all_exact_equal",
    "rho_max_abs_difference",
    "rho_mean_abs_difference",
    "stable_equal_points",
    "stable_mismatch_points",
    "stable_all_exact_equal",
    "critical_mismatch_points",
    "status_mismatch_points",
    "provenance_mismatch_points",
    "comparison_status",
    "interpretation",
]

ARTIFACT_COLUMNS = [
    "artifact_role",
    "route_id",
    "grid_kind",
    "relative_path",
    "size_bytes",
    "sha256",
    "identity_status",
    "note",
]


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relpath(path: Path) -> str:
    return path.resolve().relative_to(BOARD_ROOT).as_posix()


def _matlab_class(node: h5py.Dataset | h5py.Group) -> str:
    value = node.attrs.get("MATLAB_class", b"")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray) and value.size:
        first = value.reshape(-1)[0]
        return (
            first.decode("utf-8", errors="replace")
            if isinstance(first, bytes)
            else str(first)
        )
    return str(value)


def _restore_matlab_axes(array: np.ndarray) -> np.ndarray:
    if array.ndim < 2:
        return array
    return np.transpose(array, axes=tuple(range(array.ndim - 1, -1, -1)))


def _decode_hdf5_node(
    handle: h5py.File, node: h5py.Dataset | h5py.Group
) -> Any:
    if isinstance(node, h5py.Group):
        return {
            key: _decode_hdf5_node(handle, child)
            for key, child in node.items()
            if not key.startswith("#")
        }

    matlab_class = _matlab_class(node)
    raw = np.asarray(node)
    if matlab_class == "cell" or raw.dtype.kind == "O":
        refs = _restore_matlab_axes(raw)
        decoded = np.empty(refs.shape, dtype=object)
        for index in np.ndindex(refs.shape):
            ref = refs[index]
            decoded[index] = (
                _decode_hdf5_node(handle, handle[ref]) if ref else ""
            )
        return decoded

    array = _restore_matlab_axes(raw)
    if matlab_class == "char":
        chars = np.asarray(array, dtype=np.uint32)
        if chars.ndim <= 1 or 1 in chars.shape:
            return "".join(chr(int(code)) for code in chars.reshape(-1) if int(code))
        return np.asarray(
            [
                "".join(chr(int(code)) for code in row if int(code))
                for row in chars
            ],
            dtype=object,
        )
    if matlab_class == "logical":
        return array.astype(bool)
    return array


def load_mat_variables(
    path: Path, variable_names: Iterable[str] | None = None
) -> tuple[dict[str, Any], str]:
    """Load MATLAB v5-v7.3 data while restoring MATLAB axis order."""
    selected_names = set(variable_names) if variable_names is not None else None
    try:
        loaded = loadmat(
            path,
            squeeze_me=False,
            struct_as_record=False,
            variable_names=sorted(selected_names) if selected_names is not None else None,
        )
        return (
            {key: value for key, value in loaded.items() if not key.startswith("__")},
            "scipy.io.loadmat",
        )
    except (NotImplementedError, ValueError, OSError):
        with h5py.File(path, "r") as handle:
            result = {
                key: _decode_hdf5_node(handle, node)
                for key, node in handle.items()
                if not key.startswith("#")
                and (selected_names is None or key in selected_names)
            }
        return result, "h5py MATLAB-v7.3"


def numeric_array(value: Any) -> np.ndarray:
    return np.asarray(np.real(value), dtype=float)


def bool_array(value: Any) -> np.ndarray:
    array = np.asarray(value)
    if array.dtype.kind in "biufc":
        numeric = np.asarray(np.real(array), dtype=float)
        return np.isfinite(numeric) & (numeric != 0)
    result = np.zeros(array.shape, dtype=bool)
    for index in np.ndindex(array.shape):
        item = array[index]
        while isinstance(item, np.ndarray) and item.size == 1:
            item = item.reshape(-1)[0]
        result[index] = str(item).strip().lower() in {"1", "true", "yes", "pass"}
    return result


def shape_text(shape: Iterable[int]) -> str:
    return "x".join(str(int(value)) for value in shape)


def number_text(value: float | None) -> str:
    if value is None or not math.isfinite(float(value)):
        return ""
    return format(float(value), ".17g")


def write_csv(path: Path, rows: list[dict[str, Any]], columns: list[str]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def postcheck_index(postcheck: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    checks = postcheck.get("checks", [])
    return [item for item in checks if isinstance(item, Mapping)]


def relevant_postchecks(
    checks: list[Mapping[str, Any]], route_id: str, grid_kind: str
) -> list[Mapping[str, Any]]:
    token = f"{route_id}/{grid_kind}"
    return [item for item in checks if token in str(item.get("name", ""))]


def status_grid_record(status: Mapping[str, Any], status_key: str) -> Mapping[str, Any]:
    value = status.get(status_key, {})
    return value if isinstance(value, Mapping) else {}


def grid_record(
    route: Mapping[str, Any],
    grid_kind: str,
    status_key: str,
    filename: str,
    label_zh: str,
    status: Mapping[str, Any],
    checks: list[Mapping[str, Any]],
    manifest: Mapping[str, Any],
) -> tuple[dict[str, Any], dict[str, np.ndarray]]:
    route_id = str(route["route_id"])
    grid_contract_key = "author_code_grid" if grid_kind == "author_code_grid" else "common_grid"
    grid_contract = route[grid_contract_key]
    mat_path = GRID_ROOT / route_id / filename
    required = (
        "rho",
        "stable",
        "critical",
        "residual",
        "status",
        "provenance_code",
        "requested_mask",
        "step2_rho_reference",
        "step2_abs_diff",
        "step2_match",
    )
    variables, loader = load_mat_variables(mat_path, required)
    missing = [name for name in required if name not in variables]
    if missing:
        raise KeyError(f"{route_id}/{grid_kind} missing MAT variables: {missing}")

    rho = numeric_array(variables["rho"])
    stable = bool_array(variables["stable"])
    critical = bool_array(variables["critical"])
    residual = numeric_array(variables["residual"])
    point_status = numeric_array(variables["status"])
    provenance = numeric_array(variables["provenance_code"])
    requested = bool_array(variables["requested_mask"])
    step2_reference = numeric_array(variables["step2_rho_reference"])
    step2_abs_diff = numeric_array(variables["step2_abs_diff"])
    step2_match = bool_array(variables["step2_match"])

    arrays = {
        "rho": rho,
        "stable": stable,
        "critical": critical,
        "residual": residual,
        "status": point_status,
        "provenance": provenance,
        "requested": requested,
        "step2_reference": step2_reference,
        "step2_abs_diff": step2_abs_diff,
        "step2_match": step2_match,
    }
    actual_shape = tuple(int(value) for value in rho.shape)
    expected_shape = tuple(int(value) for value in grid_contract["expected_shape"])
    shape_ok = all(array.shape == actual_shape for array in arrays.values()) and actual_shape == expected_shape

    status_map = {str(k): int(v) for k, v in grid_contract["status_code_map"].items()}
    provenance_map = {
        str(k): int(v) for k, v in grid_contract["provenance_code_map"].items()
    }
    pass_mask = requested & (point_status == status_map["PASS"])
    fail_mask = requested & (point_status == status_map["FAIL"])
    pending_mask = requested & ~(pass_mask | fail_mask)

    rho_pass = rho[pass_mask]
    residual_pass = residual[pass_mask]
    expected_stable = pass_mask & np.isfinite(rho) & (rho > 0) & (rho < 1)
    critical_tol = float(
        read_json(CODE_ROOT / "board20_step4_validation_contract.json")
        .get("tolerances", {})
        .get("critical_abs_rho_minus_one", 1.0e-8)
    )
    expected_critical = pass_mask & np.isfinite(rho) & (np.abs(rho - 1) <= critical_tol)

    comparable = requested & np.isfinite(step2_reference) & (step2_reference > 0)
    compared_points = int(np.count_nonzero(comparable))
    finite_step2_diff = step2_abs_diff[comparable]
    step2_max = float(np.max(finite_step2_diff)) if finite_step2_diff.size else None
    step2_classification = (
        np.isfinite(step2_reference)
        & (step2_reference > 0)
        & (step2_reference < 1)
    )
    step2_classification_mismatch = int(
        np.count_nonzero((expected_stable != step2_classification) & comparable)
    )
    step2_match_points = int(np.count_nonzero(step2_match & comparable))
    step2_mismatch_points = compared_points - step2_match_points

    provenance_counts = Counter(int(value) for value in provenance[requested])
    known_codes = set(provenance_map.values())
    provenance_unknown = int(
        sum(count for code, count in provenance_counts.items() if code not in known_codes)
    )

    relevant = relevant_postchecks(checks, route_id, grid_kind)
    failed_relevant = [item for item in relevant if str(item.get("status", "")).upper() != "PASS"]
    status_entry = status_grid_record(status, status_key)
    requested_points = int(np.count_nonzero(requested))
    pass_points = int(np.count_nonzero(pass_mask))
    fail_points = int(np.count_nonzero(fail_mask))
    pending_points = int(np.count_nonzero(pending_mask))
    residual_tol = float(
        read_json(CODE_ROOT / "board20_step4_validation_contract.json")
        .get("tolerances", {})
        .get("pass_residual_max", 1.0e-8)
    )
    max_residual = float(np.max(residual_pass)) if residual_pass.size else None

    audit_pass = all(
        (
            shape_ok,
            str(status.get("overall_status", "")).upper() == "COMPLETE_PASS",
            requested_points == int(grid_contract["expected_point_count"]),
            pass_points == requested_points,
            fail_points == 0,
            pending_points == 0,
            bool(np.all(np.isfinite(rho_pass) & (rho_pass > 0))),
            bool(np.array_equal(stable, expected_stable)),
            bool(np.array_equal(critical, expected_critical)),
            max_residual is not None and max_residual <= residual_tol,
            step2_mismatch_points == 0,
            not failed_relevant,
            int(status_entry.get("requested_points", -1)) == requested_points,
            int(status_entry.get("pass_points", -1)) == pass_points,
            int(status_entry.get("fail_points", -1)) == fail_points,
            int(status_entry.get("pending_points", -1)) == pending_points,
            str(status_entry.get("output_sha256", "")).upper() == sha256(mat_path),
        )
    )

    row = {
        "route_id": route_id,
        "route_name": route["route_name"],
        "route_role": route.get("route_role", route.get("role", "")),
        "declared_method": route["declared_method"],
        "division": route["division"],
        "route_formula": route["route_formula"],
        "grid_kind": grid_kind,
        "grid_label_zh": label_zh,
        "mat_relpath": relpath(mat_path),
        "mat_sha256": sha256(mat_path),
        "mat_loader": loader,
        "expected_shape": shape_text(expected_shape),
        "actual_shape": shape_text(actual_shape),
        "expected_points": int(grid_contract["expected_point_count"]),
        "requested_points": requested_points,
        "status_pass_points": pass_points,
        "status_fail_points": fail_points,
        "status_pending_points": pending_points,
        "route_overall_status": status.get("overall_status", ""),
        "grid_audit_status": "PASS" if audit_pass else "FAIL",
        "rho_min": number_text(float(np.min(rho_pass)) if rho_pass.size else None),
        "rho_max": number_text(float(np.max(rho_pass)) if rho_pass.size else None),
        "stable_points": int(np.count_nonzero(stable & requested)),
        "critical_points": int(np.count_nonzero(critical & requested)),
        "max_pass_residual": number_text(max_residual),
        "provenance_original_active_points": provenance_counts.get(
            provenance_map["ORIGINAL_ACTIVE_POINT"], 0
        ),
        "provenance_commented_author_intent_points": provenance_counts.get(
            provenance_map["COMMENTED_AUTHOR_INTENT"], 0
        ),
        "provenance_same_formula_supplement_points": provenance_counts.get(
            provenance_map["SAME_FORMULA_SUPPLEMENT"], 0
        ),
        "provenance_fail_points": provenance_counts.get(provenance_map["FAIL"], 0),
        "provenance_unassigned_or_unknown_points": provenance_unknown,
        "step2_compared_points": compared_points,
        "step2_match_points": step2_match_points,
        "step2_mismatch_points": step2_mismatch_points,
        "step2_max_abs_difference": number_text(step2_max),
        "step2_classification_mismatch_points": step2_classification_mismatch,
        "postcheck_relevant_checks": len(relevant),
        "postcheck_relevant_failed_checks": len(failed_relevant),
    }
    return row, arrays


def pair_record(
    comparison_id: str,
    route_a: str,
    route_b: str,
    grid_kind: str,
    arrays_a: Mapping[str, np.ndarray],
    arrays_b: Mapping[str, np.ndarray],
    interpretation: str,
    require_all_equal: bool,
) -> dict[str, Any]:
    rho_a = arrays_a["rho"]
    rho_b = arrays_b["rho"]
    shape_a = rho_a.shape
    shape_b = rho_b.shape
    if shape_a != shape_b:
        return {
            "comparison_id": comparison_id,
            "route_a": route_a,
            "route_b": route_b,
            "grid_kind": grid_kind,
            "shape_a": shape_text(shape_a),
            "shape_b": shape_text(shape_b),
            "compared_points": 0,
            "comparison_status": "FAIL",
            "interpretation": interpretation + "；形状不一致，未逐点比较。",
        }

    comparable = arrays_a["requested"] & arrays_b["requested"]
    count = int(np.count_nonzero(comparable))
    rho_equal = (rho_a == rho_b) | (np.isnan(rho_a) & np.isnan(rho_b))
    rho_equal_points = int(np.count_nonzero(rho_equal & comparable))
    rho_mismatch = count - rho_equal_points
    finite_pair = comparable & np.isfinite(rho_a) & np.isfinite(rho_b)
    differences = np.abs(rho_a[finite_pair] - rho_b[finite_pair])
    rho_max = float(np.max(differences)) if differences.size else None
    rho_mean = float(np.mean(differences)) if differences.size else None

    stable_equal = arrays_a["stable"] == arrays_b["stable"]
    stable_equal_points = int(np.count_nonzero(stable_equal & comparable))
    stable_mismatch = count - stable_equal_points
    critical_mismatch = int(
        np.count_nonzero(
            (arrays_a["critical"] != arrays_b["critical"]) & comparable
        )
    )
    status_mismatch = int(
        np.count_nonzero((arrays_a["status"] != arrays_b["status"]) & comparable)
    )
    provenance_mismatch = int(
        np.count_nonzero(
            (arrays_a["provenance"] != arrays_b["provenance"]) & comparable
        )
    )
    all_equal = rho_mismatch == 0 and stable_mismatch == 0
    comparison_status = (
        "PASS"
        if require_all_equal and all_equal
        else "FAIL"
        if require_all_equal
        else "COMPARISON_COMPLETE_DIFFERENCE_REPORTED"
    )
    return {
        "comparison_id": comparison_id,
        "route_a": route_a,
        "route_b": route_b,
        "grid_kind": grid_kind,
        "shape_a": shape_text(shape_a),
        "shape_b": shape_text(shape_b),
        "compared_points": count,
        "rho_exact_equal_points": rho_equal_points,
        "rho_mismatch_points": rho_mismatch,
        "rho_all_exact_equal": str(rho_mismatch == 0).lower(),
        "rho_max_abs_difference": number_text(rho_max),
        "rho_mean_abs_difference": number_text(rho_mean),
        "stable_equal_points": stable_equal_points,
        "stable_mismatch_points": stable_mismatch,
        "stable_all_exact_equal": str(stable_mismatch == 0).lower(),
        "critical_mismatch_points": critical_mismatch,
        "status_mismatch_points": status_mismatch,
        "provenance_mismatch_points": provenance_mismatch,
        "comparison_status": comparison_status,
        "interpretation": interpretation,
    }


def artifact_row(
    role: str,
    path: Path,
    route_id: str = "",
    grid_kind: str = "",
    expected_hash: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    actual = sha256(path)
    identity = (
        "PASS"
        if expected_hash is None or actual == str(expected_hash).upper()
        else "FAIL"
    )
    return {
        "artifact_role": role,
        "route_id": route_id,
        "grid_kind": grid_kind,
        "relative_path": relpath(path),
        "size_bytes": path.stat().st_size,
        "sha256": actual,
        "identity_status": identity,
        "note": note,
    }


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]]) -> list[str]:
    result = [
        "| " + " | ".join(label for _, label in columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in rows:
        values = [str(row.get(key, "")).replace("|", "\\|") for key, _ in columns]
        result.append("| " + " | ".join(values) + " |")
    return result


def build_report(
    manifest: Mapping[str, Any],
    postcheck: Mapping[str, Any],
    summary_rows: list[dict[str, Any]],
    pair_rows: list[dict[str, Any]],
) -> str:
    failed_routes = manifest.get("failed_routes", [])
    passed_grids = sum(row["grid_audit_status"] == "PASS" for row in summary_rows)
    div2_pair = next(row for row in pair_rows if row["comparison_id"] == "DIV2_ORI_VS_GUYAN_COMMON")
    main_alt_common = next(
        row for row in pair_rows if row["comparison_id"] == "DIV1_GUYAN_MAIN_VS_ALT_COMMON"
    )

    lines = [
        "# 步骤4连续谱半径网格审计报告",
        "",
        "## 人话结论",
        "",
        f"五条成功路线的作者网格与统一网格共 10 份 MAT 文件已经逐项审计，{passed_grids}/10 份通过。这里的五条路线均是**文件身份路线**：结论只属于各自冻结的 MLX、依赖文件、工作区矩阵与公式组合，不能外推成某种降阶方法在一般意义上的结果。",
        "",
        "本步骤没有把历史 `0/0.999` 掩膜当作连续谱半径，也没有执行历史掩膜的正式匹配；后者属于后续步骤。没有建立任何成功图目录。",
        "",
        "Craig–Bampton 第一分区、Craig–Bampton 第二分区、能量法 Guyan 第一分区、能量法 Guyan 第二分区四条原始执行路线仍然失败。因此当前证据不能填满论文所需的“两分区 × Original/Craig–Bampton/Guyan”六格，也不能宣称图4-4或图4-5已经计算级复现成功。",
        "",
        "## 证据入口",
        "",
        f"- 路线清单：`{relpath(MANIFEST_PATH)}`，SHA-256 `{sha256(MANIFEST_PATH)}`。",
        f"- 独立后检：`{relpath(POSTCHECK_JSON_PATH)}`，结果 {postcheck['summary']['passed']}/{postcheck['summary']['total']} PASS。",
        f"- 路线网格明细：`{relpath(SUMMARY_PATH)}`。",
        f"- 路线两两差异：`{relpath(PAIR_PATH)}`。",
        f"- 证据文件清单：`{relpath(ARTIFACT_PATH)}`。",
        "",
        "## 五条文件身份路线的网格统计",
        "",
    ]
    lines.extend(
        markdown_table(
            summary_rows,
            [
                ("route_id", "文件身份路线"),
                ("grid_label_zh", "网格"),
                ("actual_shape", "形状"),
                ("grid_audit_status", "审计"),
                ("rho_min", "rho最小值"),
                ("rho_max", "rho最大值"),
                ("stable_points", "稳定点"),
                ("critical_points", "临界点"),
                ("max_pass_residual", "最大残差"),
                ("step2_compared_points", "步骤2比较点"),
                ("step2_max_abs_difference", "步骤2最大差"),
            ],
        )
    )
    lines.extend(
        [
            "",
            "来源标签的完整计数保存在 `route_grid_summary.csv`：`ORIGINAL_ACTIVE_POINT` 表示原程序实际活动点，`COMMENTED_AUTHOR_INTENT` 表示原程序被注释掉但可辨认的扫描意图，`SAME_FORMULA_SUPPLEMENT` 表示只沿同一冻结公式补算到共同网格。三类证据不能互相冒充。",
            "",
            "## 路线差异核验",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            pair_rows,
            [
                ("comparison_id", "比较"),
                ("grid_kind", "网格"),
                ("compared_points", "点数"),
                ("rho_mismatch_points", "rho不同点"),
                ("rho_max_abs_difference", "rho最大绝对差"),
                ("stable_mismatch_points", "稳定分类不同点"),
                ("critical_mismatch_points", "临界分类不同点"),
                ("comparison_status", "比较结论"),
            ],
        )
    )
    lines.extend(
        [
            "",
            f"第二分区 Original 与 Guyan 两条文件身份路线在统一 31×67 网格的 {div2_pair['compared_points']} 个点上，rho 精确相等点为 {div2_pair['rho_exact_equal_points']}，稳定分类差异为 {div2_pair['stable_mismatch_points']}。这说明两份冻结文件身份在当前有效计算路径上产生了相同数组；它不证明 Original 与 Guyan 两种方法理论上必然相同。",
            "",
            f"第一分区 Guyan 主路线与同目录替代路线在统一网格的 rho 不同点为 {main_alt_common['rho_mismatch_points']}，稳定分类不同点为 {main_alt_common['stable_mismatch_points']}。替代路线保持 `ALTERNATIVE_NOT_PRIMARY`，不能按结果更接近历史图就升级为主路线。",
            "",
            "## 四条执行失败路线",
            "",
        ]
    )
    for item in failed_routes:
        lines.append(
            f"- `{item['route_id']}`：`{item['execution_status']}`；{item['failure_reason']}；步骤4策略为 `{item['rho_grid_policy']}`。"
        )
    lines.extend(
        [
            "",
            "## 证据等级与边界",
            "",
            "- **计算级复现**：仅可用于上述五条冻结文件身份路线的连续谱半径网格本身；10份网格均通过本脚本与独立POSTCHECK的数值/形状/残差/来源审计。",
            "- **绘图级复现**：本步骤未评价，也未把历史掩膜画成最终图。",
            "- **历史值**：历史 `0/0.999` 掩膜仍只作为历史绘图数据存在，本步骤没有拿它填补计算失败。",
            "- **待决定**：Craig–Bampton与能量法Guyan原路线缺失可执行矩阵变量，论文六格仍不完整；是否修复原代码或只报告历史路线冲突，应在后续边界内决定。",
            "",
            "## 可重复生成说明",
            "",
            "本报告及四份结构化输出不写入当前时间；相同输入应产生字节级相同输出。脚本外部需连续执行两次并比较五份输出的 SHA-256，作为实际可重复性验收。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    manifest = read_json(MANIFEST_PATH)
    postcheck = read_json(POSTCHECK_JSON_PATH)
    checks = postcheck_index(postcheck)

    routes = manifest.get("routes", [])
    if len(routes) != 5:
        raise RuntimeError(f"Expected exactly five successful routes, got {len(routes)}")
    if str(postcheck.get("summary", {}).get("status", "")).upper() != "PASS":
        raise RuntimeError("Independent POSTCHECK is not PASS")

    summary_rows: list[dict[str, Any]] = []
    arrays_by_route_grid: dict[tuple[str, str], dict[str, np.ndarray]] = {}
    statuses: dict[str, Mapping[str, Any]] = {}
    for route in routes:
        route_id = str(route["route_id"])
        status_path = GRID_ROOT / route_id / "status.json"
        status = read_json(status_path)
        statuses[route_id] = status
        for grid_kind, status_key, filename, label_zh in GRID_SPECS:
            row, arrays = grid_record(
                route,
                grid_kind,
                status_key,
                filename,
                label_zh,
                status,
                checks,
                manifest,
            )
            summary_rows.append(row)
            arrays_by_route_grid[(route_id, grid_kind)] = arrays

    pair_rows = [
        pair_record(
            "DIV2_ORI_VS_GUYAN_COMMON",
            "main_ori_div2",
            "main_guyan_div2",
            "common_grid",
            arrays_by_route_grid[("main_ori_div2", "common_grid")],
            arrays_by_route_grid[("main_guyan_div2", "common_grid")],
            "第二分区两条文件身份路线的统一31×67网格；要求2077个rho与stable逐点精确相等。",
            True,
        ),
        pair_record(
            "DIV1_GUYAN_MAIN_VS_ALT_AUTHOR",
            "main_guyan_div1",
            "alt_guyan_div1_stable_full_ps3",
            "author_code_grid",
            arrays_by_route_grid[("main_guyan_div1", "author_code_grid")],
            arrays_by_route_grid[("alt_guyan_div1_stable_full_ps3", "author_code_grid")],
            "第一分区Guyan主路线与同目录替代路线的作者21×21网格差异；只报告差异，不按拟合结果选路线。",
            False,
        ),
        pair_record(
            "DIV1_GUYAN_MAIN_VS_ALT_COMMON",
            "main_guyan_div1",
            "alt_guyan_div1_stable_full_ps3",
            "common_grid",
            arrays_by_route_grid[("main_guyan_div1", "common_grid")],
            arrays_by_route_grid[("alt_guyan_div1_stable_full_ps3", "common_grid")],
            "第一分区Guyan主路线与同目录替代路线的统一31×67全网格差异；只报告数值/分类差异。",
            False,
        ),
    ]

    write_csv(SUMMARY_PATH, summary_rows, SUMMARY_COLUMNS)
    write_csv(PAIR_PATH, pair_rows, PAIR_COLUMNS)
    REPORT_PATH.write_text(
        build_report(manifest, postcheck, summary_rows, pair_rows),
        encoding="utf-8",
        newline="\n",
    )

    artifact_rows: list[dict[str, Any]] = [
        artifact_row("ANALYSER", SCRIPT_PATH),
        artifact_row("ROUTE_MANIFEST", MANIFEST_PATH),
        artifact_row("POSTCHECK_JSON", POSTCHECK_JSON_PATH),
        artifact_row("POSTCHECK_CSV", POSTCHECK_CSV_PATH),
    ]
    for route in routes:
        route_id = str(route["route_id"])
        status_path = GRID_ROOT / route_id / "status.json"
        artifact_rows.append(artifact_row("ROUTE_STATUS", status_path, route_id))
        for grid_kind, status_key, filename, _ in GRID_SPECS:
            mat_path = GRID_ROOT / route_id / filename
            expected_hash = str(statuses[route_id][status_key]["output_sha256"])
            artifact_rows.append(
                artifact_row(
                    "FINAL_GRID_MAT",
                    mat_path,
                    route_id,
                    grid_kind,
                    expected_hash,
                    "作者/共同网格最终文件",
                )
            )
    for failed in manifest.get("failed_routes", []):
        path = BOARD_ROOT / str(failed["run_status_relpath"])
        artifact_rows.append(
            artifact_row(
                "STEP2_FAILED_ROUTE_STATUS",
                path,
                str(failed["route_id"]),
                expected_hash=str(failed["run_status_sha256"]),
                note="执行失败证据；步骤4禁止生成rho网格",
            )
        )
    artifact_rows.extend(
        [
            artifact_row("GENERATED_SUMMARY", SUMMARY_PATH),
            artifact_row("GENERATED_PAIR_DIFFERENCE", PAIR_PATH),
            artifact_row("GENERATED_REPORT", REPORT_PATH),
        ]
    )
    write_csv(ARTIFACT_PATH, artifact_rows, ARTIFACT_COLUMNS)

    all_grid_pass = all(row["grid_audit_status"] == "PASS" for row in summary_rows)
    all_artifact_identity_pass = all(
        row["identity_status"] == "PASS" for row in artifact_rows
    )
    div2 = pair_rows[0]
    overall = (
        "PASS_WITH_SCOPE_LIMITATION"
        if all_grid_pass
        and all_artifact_identity_pass
        and div2["comparison_status"] == "PASS"
        else "FAIL"
    )
    audit = {
        "schema_version": "board20_step4_grid_audit_v1",
        "scope": "Board20 step4 continuous spectral-radius grids only",
        "source_snapshot": {
            "manifest": {
                "path": relpath(MANIFEST_PATH),
                "sha256": sha256(MANIFEST_PATH),
            },
            "postcheck": {
                "path": relpath(POSTCHECK_JSON_PATH),
                "sha256": sha256(POSTCHECK_JSON_PATH),
                "status": postcheck["summary"]["status"],
                "passed": postcheck["summary"]["passed"],
                "total": postcheck["summary"]["total"],
            },
            "analyser": {
                "path": relpath(SCRIPT_PATH),
                "sha256": sha256(SCRIPT_PATH),
            },
        },
        "summary": {
            "overall_status": overall,
            "successful_file_identity_routes": len(routes),
            "grid_records": len(summary_rows),
            "grid_pass_records": sum(
                row["grid_audit_status"] == "PASS" for row in summary_rows
            ),
            "step2_failed_routes": len(manifest.get("failed_routes", [])),
            "paper_six_cell_completion": "NOT_COMPLETE",
            "success_figure_directory_created": False,
        },
        "route_grid_summary": summary_rows,
        "route_pair_difference": pair_rows,
        "failed_routes": [
            {
                "route_id": item["route_id"],
                "execution_status": item["execution_status"],
                "failure_reason": item["failure_reason"],
                "rho_grid_policy": item["rho_grid_policy"],
            }
            for item in manifest.get("failed_routes", [])
        ],
        "claim_boundaries": {
            "five_routes_are_file_identity_routes": True,
            "general_method_equivalence_claimed": False,
            "historical_0_or_0999_mask_formally_compared": False,
            "historical_mask_used_to_fill_failed_calculation": False,
            "paper_six_cells_filled": False,
            "figure_4_4_or_4_5_success_claimed": False,
        },
        "outputs": {
            "route_grid_summary": {
                "path": relpath(SUMMARY_PATH),
                "sha256": sha256(SUMMARY_PATH),
            },
            "route_pair_difference": {
                "path": relpath(PAIR_PATH),
                "sha256": sha256(PAIR_PATH),
            },
            "artifact_manifest": {
                "path": relpath(ARTIFACT_PATH),
                "sha256": sha256(ARTIFACT_PATH),
            },
            "report": {
                "path": relpath(REPORT_PATH),
                "sha256": sha256(REPORT_PATH),
            },
        },
        "artifact_manifest_scope": {
            "listed": "all read evidence plus non-recursive generated summaries/report",
            "excluded_to_avoid_hash_cycles": [
                relpath(ARTIFACT_PATH),
                relpath(AUDIT_PATH),
            ],
        },
        "determinism_contract": {
            "current_time_embedded": False,
            "expected_same_inputs_same_bytes": True,
            "external_two_run_sha256_check_required": True,
        },
    }
    AUDIT_PATH.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(
        json.dumps(
            {
                "status": overall,
                "routes": len(routes),
                "grid_records": len(summary_rows),
                "grid_pass_records": sum(
                    row["grid_audit_status"] == "PASS" for row in summary_rows
                ),
                "postcheck": postcheck["summary"],
                "outputs": [
                    str(path)
                    for path in (
                        SUMMARY_PATH,
                        PAIR_PATH,
                        ARTIFACT_PATH,
                        AUDIT_PATH,
                        REPORT_PATH,
                    )
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if overall == "PASS_WITH_SCOPE_LIMITATION" else 1


if __name__ == "__main__":
    raise SystemExit(main())

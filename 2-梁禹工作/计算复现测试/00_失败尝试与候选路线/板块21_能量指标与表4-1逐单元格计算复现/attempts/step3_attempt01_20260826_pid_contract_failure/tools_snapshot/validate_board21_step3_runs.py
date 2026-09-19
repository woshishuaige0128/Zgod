from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

import h5py
import numpy as np


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
AUTHOR_ROOT = BOARD_ROOT / "input" / "author_energy"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"
TMP_ROOT = BOARD_ROOT / "tmp" / "step3_runs"
STAGE_ROOT = BOARD_ROOT / "outputs" / "step3_stage"
RUN_ROOT = BOARD_ROOT / "outputs" / "step3_runs"
LOG_ROOT = BOARD_ROOT / "logs" / "step3_runs"
ORCHESTRATION_ROOT = BOARD_ROOT / "outputs" / "step3_orchestration"
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "step3_validation"
EXPECTED_PYTHON = Path(r"D:\Software\python\python.exe")
EXPECTED_MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
REPLICATES = ("rep01", "rep02")
INPUT_MANIFEST_SHA256 = (
    "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
)
INPUT_FREEZE_SUMMARY_SHA256 = (
    "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"
)
EXPECTED_INPUT_CATEGORY_COUNTS = {
    "author_energy_tree": 36,
    "central_baseline": 3,
    "manuscript": 1,
    "prior_audit": 2,
    "stability_evidence": 2,
    "theory": 1,
    "upstream_candidate": 1,
    "upstream_passport": 7,
}
INSTRUMENT_FILES = {
    "stage_board21_step3_runs.py",
    "run_one_board21_energy_route.m",
    "execute_board21_step3_route.py",
    "run_board21_step3_all.py",
    "validate_board21_step3_runs.py",
}
INSTRUMENT_ORDER = (
    "stage_board21_step3_runs.py",
    "run_one_board21_energy_route.m",
    "execute_board21_step3_route.py",
    "run_board21_step3_all.py",
    "validate_board21_step3_runs.py",
)
FORMAL_OBJECT_NAMES = (
    "表4-1_两类划分Guyan与Craig--Bampton能量变化率",
    "结论C06_能量变化率稳定风险阈值",
)

STEP2_ANCHORS = {
    "outputs/step2_validation/checks.csv": "0207D7AAFC16BDCAC4298E387668DAABB143300F92927FDD4C6CABDBEDA13EF9",
    "outputs/step2_validation/validation_summary.json": "D2FD9B0DF2AD1B38F70B020E56CFCF93A92DD1132085870EC48D8990CE114A26",
    "outputs/step2_validation/step2_artifact_manifest.csv": "4BCD18ADB8321123ACFF53E30C0B5F02D5ED05C16181E7BAA829743831C5B9F9",
    "outputs/step2_validation/validation_output_manifest.csv": "DE3F2062E377007D39C59A74734F5033A2E780C68A61FAFE40E8867FF7DAE00A",
    "outputs/step2_determinism/determinism_audit.json": "9CD0C07D7956E4CC5F0ECC1956EAD54A21B9DD2AD3371F769DA6ED1D06CEED38",
    "outputs/step2_static_inventory/inventory_summary.json": "C587F4FA80E56512C7734D545A20BE483EADC5E09B5707A6D241ACBADE2A7D1C",
    "report/板块21_最小步骤2_公式与历史脚本静态审计.md": "7E642186B735E73B13547D10073AEE4B66146A7157860C1157F120165406B2DF",
    "code/validate_board21_step2_static_inventory.py": "53859497258128CD5FED7C43C089302DA2FB29B717DA9F08E0523A8A674CBB64",
}

SOURCES = {
    "PDmonicanshu.m": "A78F2608FEE0FA0775DEB0D7F778A51327C81BF88F25AA6D8E13D4202EB7B883",
    "PDmonicanshu2.m": "ADF1C89A4C9443168DCBBBBC5F9AAA1C68CE275C4F49E449C1CBABDEF86FF110",
    "PDmonicanshu3.m": "C35C7BFB19C3A5E98626FF1A07C14481F53973947E2C382EB81BD9642D9CF40E",
    "monicanshu_2_suoju.mlx": "1F885E0971033EBCB8632110EC5A47DA507126C718A80176FF3347B2ED6A08C5",
    "monicanshu_3_suoju.mlx": "D7AC9307B1A07D7AA442FDF37E7882BAE3EC519C021A5A317FFE9D9374E70D01",
    "energy_zonghe.mlx": "BCEDEF1887ABEE046A3018EB746B2088B0D63F9ACC917B9B4A78D97DEC84159D",
    "energy_zonghe2.mlx": "A84F903A5163AC0792FEA6BD0222003B3D2E1ED12B4D1B2CD6EABF325CA5CAAD",
    "Copy_of_energy_zonghe2.mlx": "80C4B3FE2A860552054D8FCEABA40365C5EE646BBB2EB21C9AF68E81AFE4715D",
    "Copy_2_of_energy_zonghe2.mlx": "8EBC3ACBD47B1D112395D4DCD951FE018F71A857E604187B443A2BFD572ADA66",
    "energy_zonghe3.mlx": "1F3B84A542AF40563F05C23402C2355345100D38A94D8EF130D5545A33D36614",
    "Copy_of_energy_zonghe3.mlx": "C067893CE26DA706774A886523F9000A2A0779268BB12A93A21E0EF0034296AC",
    "Copy_2_of_energy_zonghe3.mlx": "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D",
}

ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route_id": "reference15_pd19_energy",
        "route_label_cn": "旧15自由度参考体系：PD参数族1.9→energy_zonghe",
        "division_identity": "旧15自由度水平主坐标参考体系；不绑定表4-1两类整体划分",
        "parameter_family": "rho=785e3.*1.9",
        "upstream": "PDmonicanshu.m",
        "candidate": "energy_zonghe.mlx",
        "lengths": [15, 3, 6],
        "history": [6.5613, 6.5535],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1, 2],
        "upstream_required": ["KRrt", "MRrt", "T", "KRren", "MRren", "T_cb", "KR_cb", "MR_cb"],
        "static_boundary": "REFERENCE_NOT_TABLE4_1_DIVISION",
    },
    {
        "route_id": "division1_pd19_copy",
        "route_label_cn": "第一类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "upstream": "PDmonicanshu2.m",
        "candidate": "Copy_of_energy_zonghe2.mlx",
        "lengths": [6, 2, 5],
        "history": [9.6488, 9.3150],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "T", "KRren", "MRren", "T_cb", "KR_cb", "MR_cb"],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division1_tp17_energy",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_2_suoju.mlx",
        "candidate": "energy_zonghe2.mlx",
        "lengths": [6, 2, 5],
        "history": [9.7221, 9.3097],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division1_tp17_copy2_formula_invalid",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→Copy_2错误公式",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_2_suoju.mlx",
        "candidate": "Copy_2_of_energy_zonghe2.mlx",
        "lengths": [6, 2, 5],
        "history": [-33.7706, -41.7441],
        "denominator": "guyan_for_both",
        "sum_scope": "all_vectors",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "FORMULA_INVALID_NORMALIZATION_AND_DENOMINATOR",
    },
    {
        "route_id": "division2_pd19_copy",
        "route_label_cn": "第二类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe3",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "upstream": "PDmonicanshu3.m",
        "candidate": "Copy_of_energy_zonghe3.mlx",
        "lengths": [9, 2, 5],
        "history": [59.8619, 15.5000],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "T", "KRren", "MRren", "T_cb", "KR_cb", "MR_cb"],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division2_tp17_energy_coordinate_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→energy_zonghe3（坐标顺序冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_3_suoju.mlx",
        "candidate": "energy_zonghe3.mlx",
        "lengths": [9, 2, 5],
        "history": [59.8619, 16.9607],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "COORDINATE_ORDER_CONFLICT",
    },
    {
        "route_id": "division2_tp17_copy2_coordinate_formula_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→Copy_2（坐标与公式冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_3_suoju.mlx",
        "candidate": "Copy_2_of_energy_zonghe3.mlx",
        "lengths": [9, 2, 5],
        "history": [39.2658, 20.2060],
        "denominator": "guyan_for_both",
        "sum_scope": "all_vectors",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "COORDINATE_ORDER_AND_FORMULA_CONFLICT",
    },
)

EXPECTED_RUN_ORDER = tuple(
    (route["route_id"], replicate)
    for route in ROUTES
    for replicate in REPLICATES
)

ARTIFACT_ORDER = (
    "config_json",
    "config_hash_file",
    "run_status_json",
    "variable_inventory_json",
    "workspace_after_upstream",
    "workspace_success",
    "workspace_failure",
    "scientific_mat",
    "matlab_diary",
    "error_report",
    "matlab_command",
    "matlab_stdout",
    "matlab_stderr",
    "shell_combined_log",
)

REQUIRED_FINAL = (
    "E_total",
    "E_total_guyan",
    "E_total_cb",
    "energy_sum_orig",
    "energy_sum_guyan",
    "energy_sum_cb",
    "total_increase_guyan",
    "total_increase_cb",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    category: str,
    passed: bool,
    expected: Any,
    actual: Any,
    evidence: Path | str,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "expected": json.dumps(expected, ensure_ascii=False, sort_keys=True, default=str),
            "actual": json.dumps(actual, ensure_ascii=False, sort_keys=True, default=str),
            "evidence": str(evidence),
        }
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def normalize_struct_list(value: Any, field: str) -> list[dict[str, Any]]:
    """Normalize MATLAB jsonencode's 0/1/N struct representations."""
    if value is None or value == []:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise TypeError(f"{field} must be a MATLAB struct object or struct array")


def normalize_string_list(value: Any, field: str) -> list[str]:
    """Normalize MATLAB jsonencode's 0/1/N cell-string representations."""
    if value is None or value == []:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError(f"{field} must be a string or string array")


def strict_abs_rel_comparison(
    actual: Any, expected: Any, tolerance: float = 1e-12
) -> dict[str, Any]:
    """Require the absolute *and* relative error gates independently."""
    try:
        actual_float = float(actual)
        expected_float = float(expected)
    except (TypeError, ValueError, OverflowError) as error:
        return {
            "actual": actual,
            "expected": expected,
            "absolute_error": math.inf,
            "relative_error": math.inf,
            "absolute_error_le_tolerance": False,
            "relative_error_le_tolerance": False,
            "tolerance": tolerance,
            "error": f"{type(error).__name__}: {error}",
            "pass": False,
        }
    if not math.isfinite(actual_float) or not math.isfinite(expected_float):
        return {
            "actual": actual_float,
            "expected": expected_float,
            "absolute_error": math.inf,
            "relative_error": math.inf,
            "absolute_error_le_tolerance": False,
            "relative_error_le_tolerance": False,
            "tolerance": tolerance,
            "error": "nonfinite_operand",
            "pass": False,
        }
    absolute_error = abs(actual_float - expected_float)
    scale = max(abs(actual_float), abs(expected_float), np.finfo(np.float64).tiny)
    relative_error = absolute_error / scale
    absolute_pass = absolute_error <= tolerance
    relative_pass = relative_error <= tolerance
    return {
        "actual": actual_float,
        "expected": expected_float,
        "absolute_error": absolute_error,
        "relative_error": relative_error,
        "absolute_error_le_tolerance": absolute_pass,
        "relative_error_le_tolerance": relative_pass,
        "tolerance": tolerance,
        "error": "",
        "pass": bool(absolute_pass and relative_pass),
    }


def strict_abs_rel_close(actual: Any, expected: Any, tolerance: float = 1e-12) -> bool:
    return bool(strict_abs_rel_comparison(actual, expected, tolerance)["pass"])


def is_positive_integral_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer() and value > 0
    return False


def terminal_json_from_bytes(payload: bytes, field: str) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="strict")
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
    raise ValueError(f"{field} does not contain a terminal JSON object")


def terminal_json_line_bytes(payload: bytes, field: str) -> bytes:
    for line in reversed(payload.splitlines()):
        candidate = line.strip()
        if candidate:
            candidate.decode("utf-8", errors="strict")
            value = json.loads(candidate)
            if not isinstance(value, dict):
                raise TypeError(f"{field} terminal JSON is not an object")
            return candidate
    raise ValueError(f"{field} does not contain a nonempty terminal line")


def canonical_json_utf8(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def exact_absolute_path(value: Any, expected: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    actual = Path(value)
    return actual.is_absolute() and actual.resolve() == expected.resolve()


def verify_input_freeze() -> tuple[list[dict[str, str]], dict[str, Any]]:
    manifest_hash = sha256_file(INPUT_MANIFEST) if INPUT_MANIFEST.is_file() else "MISSING"
    summary_hash = (
        sha256_file(INPUT_FREEZE_SUMMARY)
        if INPUT_FREEZE_SUMMARY.is_file()
        else "MISSING"
    )
    if manifest_hash != INPUT_MANIFEST_SHA256:
        raise RuntimeError(
            f"input manifest seal mismatch: expected={INPUT_MANIFEST_SHA256}, "
            f"actual={manifest_hash}"
        )
    if summary_hash != INPUT_FREEZE_SUMMARY_SHA256:
        raise RuntimeError(
            "input freeze summary seal mismatch: "
            f"expected={INPUT_FREEZE_SUMMARY_SHA256}, actual={summary_hash}"
        )

    expected_fields = [
        "item_id",
        "category",
        "role",
        "source_absolute_path",
        "source_relative_label",
        "frozen_relative_path",
        "source_size_bytes",
        "source_sha256",
        "frozen_size_bytes",
        "frozen_sha256",
        "live_change_policy",
        "status",
    ]
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != expected_fields:
            raise RuntimeError(
                f"input manifest header mismatch: {reader.fieldnames}"
            )
        rows = list(reader)
    if len(rows) != 53:
        raise RuntimeError(f"input manifest must contain 53 rows, got {len(rows)}")

    row_errors: list[dict[str, Any]] = []
    category_counts = Counter(row.get("category", "") for row in rows)
    item_ids = [row.get("item_id", "") for row in rows]
    source_identities: list[str] = []
    frozen_identities: list[str] = []
    total_source_bytes = 0
    source_inside_board_count = 0
    for row_number, row in enumerate(rows, start=2):
        reasons: list[str] = []
        source_text = row.get("source_absolute_path", "")
        source = Path(source_text)
        frozen_relative_text = row.get("frozen_relative_path", "")
        frozen_relative = Path(frozen_relative_text)
        frozen = (BOARD_ROOT / "input" / frozen_relative).resolve()
        if not source.is_absolute():
            reasons.append("source_not_absolute")
        elif str(source.resolve()) != source_text:
            reasons.append("source_path_not_canonical_absolute_identity")
        if frozen_relative.is_absolute() or not is_within(frozen, BOARD_ROOT / "input"):
            reasons.append("frozen_relative_path_escapes_input_root")
        if row.get("status") != "MATCH":
            reasons.append("status_not_MATCH")
        if row.get("live_change_policy") != "immutable":
            reasons.append("live_change_policy_not_immutable")
        try:
            source_size = int(row.get("source_size_bytes", ""))
            frozen_size = int(row.get("frozen_size_bytes", ""))
        except ValueError:
            source_size = -1
            frozen_size = -1
            reasons.append("invalid_declared_size")
        source_actual_size = source.stat().st_size if source.is_file() else -1
        frozen_actual_size = frozen.stat().st_size if frozen.is_file() else -1
        source_actual_hash = sha256_file(source) if source.is_file() else "MISSING"
        frozen_actual_hash = sha256_file(frozen) if frozen.is_file() else "MISSING"
        if source_actual_size != source_size:
            reasons.append("source_size_mismatch")
        if frozen_actual_size != frozen_size:
            reasons.append("frozen_size_mismatch")
        if source_actual_hash != row.get("source_sha256"):
            reasons.append("source_hash_mismatch")
        if frozen_actual_hash != row.get("frozen_sha256"):
            reasons.append("frozen_hash_mismatch")
        if source_size != frozen_size or row.get("source_sha256") != row.get(
            "frozen_sha256"
        ):
            reasons.append("source_frozen_declared_identity_mismatch")
        if source_actual_size != frozen_actual_size or source_actual_hash != frozen_actual_hash:
            reasons.append("source_frozen_actual_identity_mismatch")
        if source.is_absolute() and is_within(source, BOARD_ROOT):
            source_inside_board_count += 1
        total_source_bytes += max(source_size, 0)
        source_identities.append(str(source.resolve()) if source.is_absolute() else source_text)
        frozen_identities.append(str(frozen))
        if reasons:
            row_errors.append(
                {
                    "row": row_number,
                    "item_id": row.get("item_id"),
                    "reasons": reasons,
                }
            )

    if len(set(item_ids)) != 53 or any(not item_id for item_id in item_ids):
        row_errors.append({"reason": "item_id_not_53_unique_nonempty"})
    if len(set(source_identities)) != 53:
        row_errors.append({"reason": "source_absolute_identity_not_53_unique"})
    if len(set(frozen_identities)) != 53:
        row_errors.append({"reason": "frozen_absolute_identity_not_53_unique"})
    if dict(category_counts) != EXPECTED_INPUT_CATEGORY_COUNTS:
        row_errors.append(
            {
                "reason": "category_counts_mismatch",
                "expected": EXPECTED_INPUT_CATEGORY_COUNTS,
                "actual": dict(category_counts),
            }
        )
    if source_inside_board_count != 0:
        row_errors.append(
            {
                "reason": "source_inside_board_root",
                "count": source_inside_board_count,
            }
        )

    summary = load_json(INPUT_FREEZE_SUMMARY)
    expected_summary = {
        "schema_version": "BOARD21_INPUT_FREEZE_V1",
        "status": "PASS",
        "input_count": 53,
        "author_energy_file_count": 36,
        "source_frozen_match_count": 53,
        "source_inside_board_root_count": 0,
        "total_source_bytes": total_source_bytes,
        "category_counts": EXPECTED_INPUT_CATEGORY_COUNTS,
    }
    summary_mismatches = {
        key: {"expected": expected, "actual": summary.get(key)}
        for key, expected in expected_summary.items()
        if summary.get(key) != expected
    }
    if row_errors or summary_mismatches:
        raise RuntimeError(
            "complete 53-row input freeze verification failed: "
            + json.dumps(
                {"row_errors": row_errors, "summary_mismatches": summary_mismatches},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return rows, summary


def author_manifest_by_name(
    all_rows: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    if all_rows is None:
        all_rows, _ = verify_input_freeze()
    selected = [
        row
        for row in all_rows
        if row.get("category") == "author_energy_tree"
        and Path(row.get("frozen_relative_path", "")).name in SOURCES
    ]
    result = {Path(row["frozen_relative_path"]).name: row for row in selected}
    if len(selected) != 12 or len(result) != 12 or set(result) != set(SOURCES):
        raise RuntimeError("step1 manifest does not uniquely cover the 12 route sources")
    for name, row in result.items():
        expected = SOURCES[name]
        if (
            row.get("source_sha256") != expected
            or row.get("frozen_sha256") != expected
            or row.get("status") != "MATCH"
        ):
            raise RuntimeError(f"step1 manifest identity mismatch: {name}")
    return result


def decode_h5_attribute(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict")
    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8", errors="strict")
    if isinstance(value, np.ndarray) and value.size == 1:
        return decode_h5_attribute(value.reshape(-1)[0])
    return str(value)


def dtype_signature(dtype: np.dtype[Any]) -> Any:
    return dtype.descr if dtype.fields else dtype.str


def h5_boolean_attribute(obj: h5py.Dataset | h5py.Group, name: str) -> bool:
    if name not in obj.attrs:
        return False
    raw = np.asarray(obj.attrs[name])
    if raw.size == 0:
        return False
    return bool(raw.astype(bool).any())


def matlab_empty_shape(raw: np.ndarray[Any, Any]) -> tuple[int, ...] | None:
    """Decode MATLAB v7.3's dimension payload for an empty array."""
    flat = np.asarray(raw).reshape(-1)
    if flat.size == 0 or not np.issubdtype(flat.dtype, np.number):
        return None
    as_float = flat.astype(np.float64, copy=False)
    if (
        not np.all(np.isfinite(as_float))
        or np.any(as_float < 0)
        or np.any(as_float != np.floor(as_float))
    ):
        return None
    return tuple(int(item) for item in as_float)


def dtype_matches_matlab_class(
    dtype: np.dtype[Any], matlab_class: str, compound_complex: bool
) -> bool:
    expected = {
        "double": ("f", 8),
        "single": ("f", 4),
        "int8": ("i", 1),
        "uint8": ("u", 1),
        "int16": ("i", 2),
        "uint16": ("u", 2),
        "int32": ("i", 4),
        "uint32": ("u", 4),
        "int64": ("i", 8),
        "uint64": ("u", 8),
    }.get(matlab_class)
    if expected is None:
        return False
    if compound_complex:
        if not dtype.fields or set(dtype.fields) != {"real", "imag"}:
            return False
        components = [dtype.fields["real"][0], dtype.fields["imag"][0]]
    else:
        components = [dtype]
    return all(item.kind == expected[0] and item.itemsize == expected[1] for item in components)


def h5_numeric_record(path: Path, name: str) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        if name not in handle or not isinstance(handle[name], h5py.Dataset):
            raise KeyError(f"numeric dataset missing: {name}: {path}")
        dataset = handle[name]
        raw = np.asarray(dataset)
        matlab_class = decode_h5_attribute(dataset.attrs.get("MATLAB_class", ""))
        matlab_empty = h5_boolean_attribute(dataset, "MATLAB_empty")
        matlab_sparse = h5_boolean_attribute(dataset, "MATLAB_sparse")
        matlab_global = h5_boolean_attribute(dataset, "MATLAB_global")
    original_dtype = dtype_signature(raw.dtype)
    compound_complex = bool(
        raw.dtype.fields and {"real", "imag"}.issubset(raw.dtype.fields)
    )
    value = raw["real"] + 1j * raw["imag"] if compound_complex else raw
    dtype_class_match = dtype_matches_matlab_class(
        raw.dtype, matlab_class, compound_complex
    )
    decoded_empty_shape = matlab_empty_shape(raw) if matlab_empty else None
    canonical_shape = (
        decoded_empty_shape
        if matlab_empty and decoded_empty_shape is not None
        else tuple(reversed(tuple(int(item) for item in raw.shape)))
    )
    return {
        "value": np.asarray(value),
        "matlab_class": matlab_class,
        "dtype": original_dtype,
        "shape": tuple(int(item) for item in raw.shape),
        "matlab_shape": canonical_shape,
        "is_complex": bool(compound_complex or np.iscomplexobj(raw)),
        "is_empty": bool(matlab_empty or raw.size == 0),
        "matlab_empty_attribute": matlab_empty,
        "matlab_empty_shape_decoded": (
            decoded_empty_shape is not None if matlab_empty else True
        ),
        "is_sparse": matlab_sparse,
        "is_global": matlab_global,
        "dtype_matches_matlab_class": dtype_class_match,
    }


def h5_dataset_content_record(path: Path, name: str) -> dict[str, Any]:
    """Return an exact raw-byte seal plus a numeric semantic array."""
    with h5py.File(path, "r") as handle:
        if name not in handle or not isinstance(handle[name], h5py.Dataset):
            raise KeyError(f"dataset missing for content comparison: {name}: {path}")
        raw = np.asarray(handle[name])
    compound_complex = bool(
        raw.dtype.fields and {"real", "imag"}.issubset(raw.dtype.fields)
    )
    if raw.dtype.hasobject:
        raise TypeError(
            f"object/reference dataset content comparison unsupported: {name}: {path}"
        )
    if compound_complex:
        value = raw["real"] + 1j * raw["imag"]
    else:
        value = raw
    value_array = np.asarray(value)
    if not np.issubdtype(value_array.dtype, np.number):
        raise TypeError(f"nonnumeric selected scientific dataset: {name}: {path}")
    contiguous_raw = np.ascontiguousarray(raw)
    payload = contiguous_raw.tobytes(order="C")
    return {
        "value": value_array,
        "raw_size_bytes": len(payload),
        "raw_sha256": hashlib.sha256(payload).hexdigest().upper(),
        "raw_dtype": dtype_signature(raw.dtype),
        "raw_shape": tuple(int(item) for item in raw.shape),
    }


def h5_names(path: Path) -> set[str]:
    with h5py.File(path, "r") as handle:
        return {name for name in handle.keys() if name != "#refs#"}


def scalar_from_record(record: dict[str, Any], name: str) -> float:
    value = np.asarray(record["value"]).reshape(-1)
    if value.size != 1:
        raise ValueError(f"expected scalar {name}, got {record['shape']}")
    scalar_value = value[0]
    if np.iscomplexobj(value):
        if abs(float(np.imag(scalar_value))) > 1e-12:
            raise ValueError(f"complex scalar exceeds 1e-12: {name}")
        scalar_value = np.real(scalar_value)
    return float(scalar_value)


def finite_numeric_record(path: Path, name: str) -> dict[str, Any]:
    record = h5_numeric_record(path, name)
    value = np.asarray(record["value"])
    if record["matlab_class"] != "double":
        raise ValueError(
            f"required scientific value is not MATLAB double for {name}: "
            f"{record['matlab_class']!r}: {path}"
        )
    if not record["dtype_matches_matlab_class"]:
        raise ValueError(
            f"MATLAB_class/HDF5 dtype mismatch for {name}: "
            f"class={record['matlab_class']!r}, dtype={record['dtype']!r}"
        )
    if record["is_empty"]:
        raise ValueError(f"empty required numeric value: {name}: {path}")
    if record["is_sparse"]:
        raise ValueError(f"sparse required scientific value is unsupported: {name}: {path}")
    if record["is_global"]:
        raise ValueError(f"global required scientific value is unsupported: {name}: {path}")
    if not np.issubdtype(value.dtype, np.number) or not np.all(np.isfinite(value)):
        raise ValueError(f"nonfinite or nonnumeric: {name}: {path}")
    if record["is_complex"] or np.iscomplexobj(value):
        raise ValueError(f"required scientific value must be strictly real: {name}: {path}")
    return record


def h5_workspace_metadata(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with h5py.File(path, "r") as handle:
        for name in handle.keys():
            if name == "#refs#":
                continue
            obj = handle[name]
            matlab_class = decode_h5_attribute(obj.attrs.get("MATLAB_class", ""))
            if isinstance(obj, h5py.Dataset):
                raw = np.asarray(obj)
                matlab_empty = h5_boolean_attribute(obj, "MATLAB_empty")
                matlab_sparse = h5_boolean_attribute(obj, "MATLAB_sparse")
                matlab_global = h5_boolean_attribute(obj, "MATLAB_global")
                decoded_empty_shape = (
                    matlab_empty_shape(raw) if matlab_empty else None
                )
                compound_complex = bool(
                    raw.dtype.fields
                    and {"real", "imag"}.issubset(raw.dtype.fields)
                )
                dtype_class_match = dtype_matches_matlab_class(
                    raw.dtype, matlab_class, compound_complex
                )
                rejection_reasons: list[str] = []
                if not matlab_class:
                    rejection_reasons.append("missing_MATLAB_class")
                if matlab_sparse:
                    rejection_reasons.append("sparse_root_dataset_unsupported")
                if matlab_empty and decoded_empty_shape is None:
                    rejection_reasons.append("empty_dimension_payload_invalid")
                if matlab_class in {
                    "double",
                    "single",
                    "int8",
                    "uint8",
                    "int16",
                    "uint16",
                    "int32",
                    "uint32",
                    "int64",
                    "uint64",
                } and not dtype_class_match:
                    rejection_reasons.append(
                        "MATLAB_numeric_class_HDF5_dtype_mismatch"
                    )
                result[name] = {
                    "object_type": "dataset",
                    "matlab_class": matlab_class,
                    "dtype": dtype_signature(raw.dtype),
                    "shape": tuple(int(item) for item in raw.shape),
                    "matlab_shape": (
                        decoded_empty_shape
                        if matlab_empty and decoded_empty_shape is not None
                        else tuple(reversed(tuple(int(item) for item in raw.shape)))
                    ),
                    "is_complex": bool(compound_complex or np.iscomplexobj(raw)),
                    "is_empty": bool(matlab_empty or raw.size == 0),
                    "matlab_empty_attribute": matlab_empty,
                    "matlab_empty_shape_decoded": (
                        decoded_empty_shape is not None if matlab_empty else True
                    ),
                    "is_sparse": matlab_sparse,
                    "is_global": matlab_global,
                    "dtype_matches_matlab_class": dtype_class_match,
                    "supported": not rejection_reasons,
                    "rejection_reasons": rejection_reasons,
                }
            else:
                result[name] = {
                    "object_type": "group",
                    "matlab_class": matlab_class,
                    "dtype": "GROUP",
                    "shape": (),
                    "matlab_shape": (),
                    "is_complex": False,
                    "is_empty": len(obj) == 0,
                    "matlab_empty_attribute": h5_boolean_attribute(
                        obj, "MATLAB_empty"
                    ),
                    "matlab_empty_shape_decoded": False,
                    "is_sparse": h5_boolean_attribute(obj, "MATLAB_sparse"),
                    "is_global": h5_boolean_attribute(obj, "MATLAB_global"),
                    "dtype_matches_matlab_class": False,
                    "supported": False,
                    "rejection_reasons": ["root_group_unsupported"],
                }
    return result


def inventory_records(value: Any, field: str) -> list[dict[str, Any]]:
    records = normalize_struct_list(value, field)
    required_fields = {
        "name",
        "class",
        "size",
        "bytes",
        "is_sparse",
        "is_complex",
        "is_global",
    }
    names: list[str] = []
    for index, record in enumerate(records, start=1):
        if set(record) != required_fields:
            raise ValueError(
                f"{field}[{index}] fields mismatch: expected={sorted(required_fields)}, "
                f"actual={sorted(record)}"
            )
        name = record.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field}[{index}] invalid variable name")
        matlab_class = record.get("class")
        if not isinstance(matlab_class, str) or not matlab_class:
            raise ValueError(f"{field}[{index}] invalid MATLAB class")
        size = record.get("size")
        if isinstance(size, int) and not isinstance(size, bool):
            size = [size]
        if not isinstance(size, list) or not size or any(
            not isinstance(item, int)
            or isinstance(item, bool)
            or item < 0
            for item in size
        ):
            raise ValueError(f"{field}[{index}] invalid size")
        byte_count = record.get("bytes")
        if (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise ValueError(f"{field}[{index}] invalid bytes")
        for boolean_field in ("is_sparse", "is_complex", "is_global"):
            if not isinstance(record.get(boolean_field), bool):
                raise ValueError(
                    f"{field}[{index}] {boolean_field} must be a JSON boolean"
                )
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError(f"{field} contains duplicate variable names")
    return records


def compare_inventory_to_workspace(
    records: list[dict[str, Any]], path: Path, field: str
) -> dict[str, Any]:
    metadata = h5_workspace_metadata(path)
    inventory_by_name = {record["name"]: record for record in records}
    names_match = set(inventory_by_name) == set(metadata)
    variable_rows: list[dict[str, Any]] = []
    all_match = names_match
    for name in sorted(set(inventory_by_name) | set(metadata)):
        inventory = inventory_by_name.get(name)
        saved = metadata.get(name)
        if inventory is None or saved is None:
            variable_rows.append(
                {"name": name, "present_in_inventory": inventory is not None, "present_in_workspace": saved is not None, "match": False}
            )
            all_match = False
            continue
        inventory_size = tuple(int(item) for item in (inventory["size"] if isinstance(inventory["size"], list) else [inventory["size"]]))
        class_match = saved["matlab_class"] == inventory["class"]
        complex_match = saved["is_complex"] is inventory["is_complex"]
        sparse_match = saved["is_sparse"] is inventory["is_sparse"]
        global_match = saved["is_global"] is inventory["is_global"]
        shape_match = saved["matlab_shape"] == inventory_size
        inventory_empty = any(item == 0 for item in inventory_size)
        empty_match = saved["is_empty"] is inventory_empty
        supported = saved["supported"]
        variable_match = bool(
            supported
            and class_match
            and complex_match
            and sparse_match
            and global_match
            and shape_match
            and empty_match
        )
        all_match &= variable_match
        variable_rows.append(
            {
                "name": name,
                "class_match": class_match,
                "complex_match": complex_match,
                "sparse_match": sparse_match,
                "global_match": global_match,
                "shape_match": shape_match,
                "empty_match": empty_match,
                "supported_workspace_object": supported,
                "inventory_size": inventory_size,
                "workspace": saved,
                "match": variable_match,
            }
        )
    return {
        "field": field,
        "workspace": str(path),
        "names_match": names_match,
        "variable_count": len(metadata),
        "variables": variable_rows,
        "pass": bool(all_match),
    }


def scientific_mat_crosscheck(
    paths: dict[str, Path],
    status: dict[str, Any],
    status_names: list[str],
    final_inventory: list[dict[str, Any]],
    final_workspace: Path,
) -> dict[str, Any]:
    """Cross-check the selected science MAT against status, whos, and workspace."""
    status_scientific = status.get("scientific")
    if not isinstance(status_scientific, dict):
        return {
            "pass": False,
            "error": "status.scientific is not an object",
        }
    scientific_names_error = ""
    try:
        nested_names = normalize_string_list(
            status_scientific.get("available_variables"),
            "status.scientific.available_variables",
        )
    except Exception as error:
        nested_names = []
        scientific_names_error = f"{type(error).__name__}: {error}"
    names_unique = len(status_names) == len(set(status_names))
    nested_names_match = not scientific_names_error and nested_names == status_names
    scientific_expected = bool(status_names)
    scientific_exists = paths["scientific_mat"].is_file()
    existence_match = scientific_exists is scientific_expected
    details: dict[str, Any] = {
        "status_names": status_names,
        "nested_status_names": nested_names,
        "status_names_unique": names_unique,
        "nested_status_names_match": nested_names_match,
        "scientific_names_error": scientific_names_error,
        "scientific_expected": scientific_expected,
        "scientific_exists": scientific_exists,
        "existence_match": existence_match,
        "root_names": [],
        "root_names_exact": not scientific_expected,
        "selected_names_in_inventory": not scientific_expected,
        "selected_names_in_workspace": not scientific_expected,
        "variables": [],
    }
    if not scientific_expected:
        details["pass"] = bool(
            names_unique
            and nested_names_match
            and existence_match
            and not scientific_names_error
        )
        return details
    if not scientific_exists:
        details["pass"] = False
        return details

    try:
        scientific_metadata = h5_workspace_metadata(paths["scientific_mat"])
        workspace_metadata = h5_workspace_metadata(final_workspace)
    except Exception as error:
        details["metadata_error"] = f"{type(error).__name__}: {error}"
        details["pass"] = False
        return details
    inventory_by_name = {record["name"]: record for record in final_inventory}
    root_names = sorted(scientific_metadata)
    root_names_exact = set(root_names) == set(status_names)
    selected_names_in_inventory = set(status_names).issubset(inventory_by_name)
    selected_names_in_workspace = set(status_names).issubset(workspace_metadata)
    details.update(
        {
            "root_names": root_names,
            "root_names_exact": root_names_exact,
            "selected_names_in_inventory": selected_names_in_inventory,
            "selected_names_in_workspace": selected_names_in_workspace,
        }
    )
    metadata_fields = (
        "object_type",
        "matlab_class",
        "dtype",
        "shape",
        "matlab_shape",
        "is_complex",
        "is_empty",
        "matlab_empty_attribute",
        "matlab_empty_shape_decoded",
        "is_sparse",
        "is_global",
        "dtype_matches_matlab_class",
        "supported",
        "rejection_reasons",
    )
    all_variables_match = True
    variable_rows: list[dict[str, Any]] = []
    for name in status_names:
        scientific = scientific_metadata.get(name)
        workspace = workspace_metadata.get(name)
        inventory = inventory_by_name.get(name)
        if scientific is None or workspace is None or inventory is None:
            variable_rows.append(
                {
                    "name": name,
                    "scientific_present": scientific is not None,
                    "workspace_present": workspace is not None,
                    "inventory_present": inventory is not None,
                    "match": False,
                }
            )
            all_variables_match = False
            continue
        metadata_match = {
            field: scientific.get(field) == workspace.get(field)
            for field in metadata_fields
        }
        inventory_size = tuple(inventory["size"])
        inventory_match = {
            "matlab_class": scientific["matlab_class"] == inventory["class"],
            "matlab_shape": scientific["matlab_shape"] == inventory_size,
            "is_complex": scientific["is_complex"] is inventory["is_complex"],
            "is_sparse": scientific["is_sparse"] is inventory["is_sparse"],
            "is_global": scientific["is_global"] is inventory["is_global"],
            "is_empty": scientific["is_empty"]
            is any(item == 0 for item in inventory_size),
        }
        content_error = ""
        scientific_content_summary: dict[str, Any] = {}
        workspace_content_summary: dict[str, Any] = {}
        semantic_content_equal = False
        bitwise_content_equal = False
        try:
            scientific_content = h5_dataset_content_record(
                paths["scientific_mat"], name
            )
            workspace_content = h5_dataset_content_record(final_workspace, name)
            scientific_value = scientific_content.pop("value")
            workspace_value = workspace_content.pop("value")
            scientific_content_summary = scientific_content
            workspace_content_summary = workspace_content
            if (
                np.issubdtype(scientific_value.dtype, np.inexact)
                or np.issubdtype(workspace_value.dtype, np.inexact)
            ):
                semantic_content_equal = bool(
                    np.array_equal(
                        scientific_value,
                        workspace_value,
                        equal_nan=True,
                    )
                )
            else:
                semantic_content_equal = bool(
                    np.array_equal(scientific_value, workspace_value)
                )
            bitwise_content_equal = bool(
                scientific_content_summary == workspace_content_summary
            )
        except Exception as error:
            content_error = f"{type(error).__name__}: {error}"
        content_match = bool(
            not content_error
            and semantic_content_equal
            and bitwise_content_equal
        )
        variable_match = bool(
            scientific["object_type"] == "dataset"
            and scientific["supported"]
            and workspace["supported"]
            and all(metadata_match.values())
            and all(inventory_match.values())
            and content_match
        )
        all_variables_match &= variable_match
        variable_rows.append(
            {
                "name": name,
                "scientific": scientific,
                "workspace": workspace,
                "inventory": inventory,
                "scientific_workspace_metadata_match": metadata_match,
                "inventory_metadata_match": inventory_match,
                "scientific_content": scientific_content_summary,
                "workspace_content": workspace_content_summary,
                "semantic_content_equal": semantic_content_equal,
                "bitwise_content_equal": bitwise_content_equal,
                "content_error": content_error,
                "content_match": content_match,
                "match": variable_match,
            }
        )
    details["variables"] = variable_rows
    details["pass"] = bool(
        names_unique
        and nested_names_match
        and existence_match
        and root_names_exact
        and selected_names_in_inventory
        and selected_names_in_workspace
        and all_variables_match
        and not scientific_names_error
    )
    return details


def normalized_error_message(value: str) -> str:
    text = value.replace("\\", "/")
    text = re.sub(r"rep0[12]", "repXX", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def target_processes() -> list[dict[str, Any]]:
    token = str(BOARD_ROOT).casefold()
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding=[Console]::OutputEncoding; "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw|pdftoppm)\\.exe$'} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("process query timed out after 30 seconds") from error
    stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0 or stderr_text:
        raise RuntimeError(
            f"process query failed rc={completed.returncode}: {stderr_text}"
        )
    text = completed.stdout.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return []
    raw = json.loads(text)
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise TypeError("process query did not return an object array")
    result = []
    for item in raw:
        pid = int(item.get("ProcessId") or -1)
        name = str(item.get("Name") or "")
        command_line = str(item.get("CommandLine") or "")
        if pid == os.getpid():
            continue
        if name.casefold() == "matlab.exe" or token in command_line.casefold():
            result.append(item)
    return result


def preflight(require_validation_absent: bool = True) -> dict[str, Any]:
    if Path(sys.executable).resolve() != EXPECTED_PYTHON.resolve():
        raise RuntimeError(f"wrong Python: {sys.executable}")
    if len(ROUTES) != 7 or len({route["route_id"] for route in ROUTES}) != 7:
        raise RuntimeError("expected seven unique routes")
    referenced = {
        route[key] for route in ROUTES for key in ("upstream", "candidate")
    }
    if referenced != set(SOURCES) or len(referenced) != 12:
        raise RuntimeError("route/source contract must cover exactly 12 unique sources")
    all_manifest_rows, freeze_summary = verify_input_freeze()
    source_mismatches = []
    manifest_rows = author_manifest_by_name(all_manifest_rows)
    for name, expected in SOURCES.items():
        path = AUTHOR_ROOT / name
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            source_mismatches.append((name, expected, actual))
        original = Path(manifest_rows[name]["source_absolute_path"])
        original_actual = sha256_file(original) if original.is_file() else "MISSING"
        if original_actual != expected:
            source_mismatches.append((str(original), expected, original_actual))
    if source_mismatches:
        raise RuntimeError(f"frozen source mismatch: {source_mismatches}")
    for relative, expected in STEP2_ANCHORS.items():
        path = BOARD_ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            raise RuntimeError(f"step2 anchor mismatch: {relative}: {actual}")
    if require_validation_absent and VALIDATION_ROOT.exists():
        raise FileExistsError(VALIDATION_ROOT)
    return {
        "status": "PREFLIGHT_PASS",
        "route_count": 7,
        "source_reference_count": 14,
        "unique_source_count": 12,
        "step2_anchor_count": len(STEP2_ANCHORS),
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        "input_row_count": len(all_manifest_rows),
        "input_category_counts": freeze_summary["category_counts"],
        "matlab_executed_by_preflight": False,
    }


def expected_run_paths(route: dict[str, Any], replicate: str) -> dict[str, Path]:
    route_id = route["route_id"]
    work_dir = (TMP_ROOT / route_id / replicate / "work").resolve()
    output_dir = (RUN_ROOT / route_id / replicate).resolve()
    metadata_dir = output_dir / "metadata"
    workspace_dir = output_dir / "workspace"
    scientific_dir = output_dir / "scientific"
    log_dir = (LOG_ROOT / route_id / replicate).resolve()
    config_json = metadata_dir / "run_config.json"
    return {
        "work_dir": work_dir,
        "output_dir": output_dir,
        "metadata_dir": metadata_dir,
        "workspace_dir": workspace_dir,
        "scientific_dir": scientific_dir,
        "log_dir": log_dir,
        "config_json": config_json,
        "config_hash_file": metadata_dir / "run_config.sha256",
        "run_status_json": metadata_dir / "run_status.json",
        "variable_inventory_json": metadata_dir / "variable_inventory.json",
        "workspace_after_upstream": workspace_dir / "workspace_after_upstream.mat",
        "workspace_success": workspace_dir / "workspace_complete.mat",
        "workspace_failure": workspace_dir / "workspace_failure.mat",
        "scientific_mat": scientific_dir / "historical_energy_outputs.mat",
        "matlab_diary": log_dir / "matlab_diary.log",
        "error_report": log_dir / "error_report.txt",
        "matlab_command": log_dir / "matlab_command.txt",
        "matlab_stdout": log_dir / "matlab_stdout.log",
        "matlab_stderr": log_dir / "matlab_stderr.log",
        "shell_combined_log": log_dir / "shell_stdout_stderr.log",
        "process_exit_json": metadata_dir / "process_exit.json",
        "upstream_file": work_dir / route["upstream"],
        "candidate_mlx": work_dir / route["candidate"],
    }


def expected_config_path_fields(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        "work_dir": paths["work_dir"],
        "output_dir": paths["output_dir"],
        "log_dir": paths["log_dir"],
        "upstream_file": paths["upstream_file"],
        "candidate_mlx": paths["candidate_mlx"],
        "status_json": paths["run_status_json"],
        "config_hash_file": paths["config_hash_file"],
        "variable_inventory_json": paths["variable_inventory_json"],
        "workspace_after_upstream": paths["workspace_after_upstream"],
        "workspace_success": paths["workspace_success"],
        "workspace_failure": paths["workspace_failure"],
        "scientific_mat": paths["scientific_mat"],
        "diary_file": paths["matlab_diary"],
        "error_report": paths["error_report"],
        "matlab_command_txt": paths["matlab_command"],
        "shell_log": paths["shell_combined_log"],
        "matlab_stdout_log": paths["matlab_stdout"],
        "matlab_stderr_log": paths["matlab_stderr"],
        "process_exit_json": paths["process_exit_json"],
    }


def inspect_hdf5_files(paths: dict[str, Path], required_names: set[str]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    passed = True
    for name in sorted(required_names):
        path = paths[name]
        record: dict[str, Any] = {
            "path": str(path),
            "exists": path.is_file(),
            "readable": False,
            "root_variables": [],
            "error": "",
        }
        if path.is_file():
            try:
                with h5py.File(path, "r") as handle:
                    record["root_variables"] = sorted(
                        key for key in handle.keys() if key != "#refs#"
                    )
                    record["readable"] = True
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
        passed &= bool(record["exists"] and record["readable"])
        details[name] = record
    return {"pass": bool(passed), "files": details}


def validate_artifact_seal(
    exit_record: dict[str, Any],
    paths: dict[str, Path],
    runner_success: bool,
    author_failure: bool,
    failed_stage: str,
    scientific_expected: bool,
) -> dict[str, Any]:
    always_required = {
        "config_json",
        "config_hash_file",
        "run_status_json",
        "variable_inventory_json",
        "matlab_diary",
        "matlab_command",
        "matlab_stdout",
        "matlab_stderr",
        "shell_combined_log",
    }
    success_required = {"workspace_after_upstream", "workspace_success"}
    failure_required = {"workspace_failure", "error_report"}
    if author_failure and failed_stage == "CANDIDATE_ORIGINAL_MLX":
        failure_required.add("workspace_after_upstream")
    expected_required = {
        name: bool(
            name in always_required
            or (name == "scientific_mat" and scientific_expected)
            or (runner_success and name in success_required)
            or (author_failure and name in failure_required)
        )
        for name in ARTIFACT_ORDER
    }
    expected_exists = dict(expected_required)
    seal = normalize_struct_list(exit_record.get("artifact_seal"), "artifact_seal")
    names = [item.get("name") for item in seal]
    item_rows: list[dict[str, Any]] = []
    passed = names == list(ARTIFACT_ORDER)
    for name in ARTIFACT_ORDER:
        matches = [item for item in seal if item.get("name") == name]
        if len(matches) != 1:
            item_rows.append(
                {"name": name, "record_count": len(matches), "match": False}
            )
            passed = False
            continue
        item = matches[0]
        path = paths[name]
        exists = path.is_file()
        size = path.stat().st_size if exists else -1
        digest = sha256_file(path) if exists else ""
        item_pass = bool(
            exact_absolute_path(item.get("path"), path)
            and item.get("required") is expected_required[name]
            and item.get("exists") is expected_exists[name]
            and exists is expected_exists[name]
            and item.get("size_bytes") == size
            and item.get("sha256") == digest
            and (not expected_required[name] or (exists and size >= 0 and bool(digest)))
            and (
                not expected_required[name]
                or name == "matlab_stderr"
                or size > 0
            )
        )
        passed &= item_pass
        item_rows.append(
            {
                "name": name,
                "path": str(path),
                "expected_required": expected_required[name],
                "exists": exists,
                "size_bytes": size,
                "sha256": digest,
                "sealed_record": item,
                "match": item_pass,
            }
        )

    stdout = paths["matlab_stdout"].read_bytes() if paths["matlab_stdout"].is_file() else b""
    stderr = paths["matlab_stderr"].read_bytes() if paths["matlab_stderr"].is_file() else b""
    expected_combined = (
        b"===== STDOUT =====\n"
        + stdout
        + b"\n===== STDERR =====\n"
        + stderr
        + b"\n"
    )
    actual_combined = (
        paths["shell_combined_log"].read_bytes()
        if paths["shell_combined_log"].is_file()
        else b""
    )
    stream_checks = {
        "stdout_size": exit_record.get("stdout_size_bytes") == len(stdout),
        "stderr_size": exit_record.get("stderr_size_bytes") == len(stderr),
        "stdout_hash": exit_record.get("stdout_sha256")
        == hashlib.sha256(stdout).hexdigest().upper(),
        "stderr_hash": exit_record.get("stderr_sha256")
        == hashlib.sha256(stderr).hexdigest().upper(),
        "combined_hash": exit_record.get("combined_log_sha256")
        == hashlib.sha256(actual_combined).hexdigest().upper(),
        "combined_exact_bytes": actual_combined == expected_combined,
        "stdout_path": exact_absolute_path(
            exit_record.get("matlab_stdout_path"), paths["matlab_stdout"]
        ),
        "stderr_path": exact_absolute_path(
            exit_record.get("matlab_stderr_path"), paths["matlab_stderr"]
        ),
        "combined_path": exact_absolute_path(
            exit_record.get("combined_log_path"), paths["shell_combined_log"]
        ),
        "executor_runtime_log_hash_gate": exit_record.get(
            "runtime_log_hashes_match"
        )
        is True,
    }
    passed &= all(stream_checks.values())
    recomputed_all_required = all(
        (not row.get("expected_required"))
        or (row.get("exists") and row.get("size_bytes", -1) >= 0 and row.get("sha256"))
        for row in item_rows
        if row.get("record_count", 1) == 1
    ) and len(item_rows) == len(ARTIFACT_ORDER)
    required_gate = (
        exit_record.get("all_required_artifacts_sealed") is recomputed_all_required
        and recomputed_all_required
        and exit_record.get("artifact_exclusivity_match") is True
        and exit_record.get("expected_artifact_exists") == expected_exists
    )
    passed &= required_gate
    return {
        "pass": bool(passed),
        "names_in_order": names,
        "items": item_rows,
        "stream_checks": stream_checks,
        "recomputed_all_required_artifacts_sealed": recomputed_all_required,
        "recorded_all_required_artifacts_sealed": exit_record.get(
            "all_required_artifacts_sealed"
        ),
    }


def publication_and_process_snapshot() -> dict[str, Any]:
    formal_present: list[str] = []
    failure_present: list[str] = []
    board22: list[str] = []
    publication_error = ""
    try:
        formal_present = [
            str(PROJECT_ROOT / "test" / name)
            for name in FORMAL_OBJECT_NAMES
            if (PROJECT_ROOT / "test" / name).exists()
        ]
        failure_present = [
            str(PROJECT_ROOT / "test" / "00_失败尝试与候选路线" / name)
            for name in FORMAL_OBJECT_NAMES
            if (PROJECT_ROOT / "test" / "00_失败尝试与候选路线" / name).exists()
        ]
        board22 = [
            str(path)
            for path in (PROJECT_ROOT / "test").rglob("*")
            if path.name.startswith("板块22")
        ]
    except Exception as error:
        publication_error = f"{type(error).__name__}: {error}"
    residual: list[dict[str, Any]] = []
    process_error = ""
    try:
        residual = target_processes()
    except Exception as error:
        process_error = f"{type(error).__name__}: {error}"
    return {
        "formal_present": formal_present,
        "failure_present": failure_present,
        "board22_present": board22,
        "publication_query_error": publication_error,
        "residual_processes": residual,
        "process_query_error": process_error,
    }


def validate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    preflight_summary = preflight(require_validation_absent=False)
    all_manifest_rows, freeze_summary = verify_input_freeze()
    manifest_rows = author_manifest_by_name(all_manifest_rows)
    checks: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    repeat_rows: list[dict[str, Any]] = []
    per_route_runs: dict[str, dict[str, dict[str, Any]]] = {}
    route_map = {route["route_id"]: route for route in ROUTES}
    sealed_tools = {
        name: sha256_file(SCRIPT.parent / name) for name in INSTRUMENT_ORDER
    }

    add_check(checks, "S3-ROUTE-COUNT", "contract", len(ROUTES) == 7, 7, len(ROUTES), SCRIPT)
    add_check(checks, "S3-UNIQUE-SOURCE-COUNT", "contract", len(SOURCES) == 12, 12, len(SOURCES), AUTHOR_ROOT)
    add_check(
        checks,
        "S3-INPUT-FREEZE-SEALS",
        "protected_input",
        sha256_file(INPUT_MANIFEST) == INPUT_MANIFEST_SHA256
        and sha256_file(INPUT_FREEZE_SUMMARY) == INPUT_FREEZE_SUMMARY_SHA256,
        {
            "input_manifest_sha256": INPUT_MANIFEST_SHA256,
            "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        },
        {
            "input_manifest_sha256": sha256_file(INPUT_MANIFEST),
            "input_freeze_summary_sha256": sha256_file(INPUT_FREEZE_SUMMARY),
        },
        INPUT_MANIFEST,
    )
    add_check(
        checks,
        "S3-INPUT-FREEZE-53-ROW-IDENTITY",
        "protected_input",
        len(all_manifest_rows) == 53
        and freeze_summary.get("category_counts") == EXPECTED_INPUT_CATEGORY_COUNTS,
        {"row_count": 53, "category_counts": EXPECTED_INPUT_CATEGORY_COUNTS},
        {"row_count": len(all_manifest_rows), "summary": freeze_summary},
        INPUT_MANIFEST,
    )
    for index, (relative, expected) in enumerate(STEP2_ANCHORS.items(), start=1):
        path = BOARD_ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        add_check(checks, f"S3-STEP2-ANCHOR-{index:02d}", "protected_input", actual == expected, expected, actual, path)

    stage_summary_path = STAGE_ROOT / "stage_summary.json"
    stage_summary = load_json(stage_summary_path)
    stage_expected = {
        "schema_version": "BOARD21_STEP3_STAGE_SUMMARY_V1",
        "status": "STAGED_NOT_RUN",
        "matlab_executed": False,
        "route_count": 7,
        "replicate_count": 2,
        "run_count": 14,
        "staged_input_row_count": 28,
        "unique_source_count": 12,
        "protected_input_count": 53,
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        "instrument_sha256": sealed_tools,
        "formal_success_directory_created": False,
        "board22_started": False,
    }
    stage_pass = all(stage_summary.get(key) == value for key, value in stage_expected.items())
    add_check(checks, "S3-STAGE-SUMMARY", "staging", stage_pass, stage_expected, stage_summary, stage_summary_path)

    config_csv = STAGE_ROOT / "run_configs.csv"
    expected_config_fields = [
        "route_id", "route_label_cn", "replicate", "config_path",
        "config_sha256", "static_boundary", "execution_status",
    ]
    with config_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        config_reader = csv.DictReader(stream)
        config_fields = config_reader.fieldnames
        config_rows = list(config_reader)
    actual_config_order = tuple(
        (row.get("route_id", ""), row.get("replicate", "")) for row in config_rows
    )
    config_set_pass = bool(
        config_fields == expected_config_fields
        and len(config_rows) == 14
        and actual_config_order == EXPECTED_RUN_ORDER
        and len(set(actual_config_order)) == 14
        and all(row.get("execution_status") == "STAGED_NOT_RUN" for row in config_rows)
    )
    add_check(
        checks,
        "S3-CONFIG-ORDER-AND-SCHEMA",
        "staging",
        config_set_pass,
        {"fields": expected_config_fields, "order": EXPECTED_RUN_ORDER, "execution_status": "STAGED_NOT_RUN"},
        {"fields": config_fields, "order": actual_config_order, "statuses": [row.get("execution_status") for row in config_rows]},
        config_csv,
    )
    if not config_set_pass:
        raise RuntimeError("ordered 14-run config set is not valid")

    staged_manifest_path = STAGE_ROOT / "staged_input_manifest.csv"
    expected_staged_fields = [
        "route_id", "replicate", "kind", "order", "name",
        "author_original_path", "frozen_path", "staged_path",
        "expected_sha256", "copied_sha256", "size_bytes",
    ]
    with staged_manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        staged_reader = csv.DictReader(stream)
        staged_fields = staged_reader.fieldnames
        staged_rows = list(staged_reader)
    expected_staged_rows: list[dict[str, str]] = []
    staged_file_checks: list[dict[str, Any]] = []
    for route in ROUTES:
        for replicate in REPLICATES:
            paths = expected_run_paths(route, replicate)
            for order, kind in enumerate(("upstream", "candidate"), start=1):
                name = route[kind]
                frozen_row = manifest_rows[name]
                staged_path = paths[f"{kind}_file" if kind == "upstream" else "candidate_mlx"]
                expected_staged_rows.append(
                    {
                        "route_id": route["route_id"],
                        "replicate": replicate,
                        "kind": kind,
                        "order": str(order),
                        "name": name,
                        "author_original_path": str(Path(frozen_row["source_absolute_path"]).resolve()),
                        "frozen_path": str((AUTHOR_ROOT / name).resolve()),
                        "staged_path": str(staged_path),
                        "expected_sha256": SOURCES[name],
                        "copied_sha256": SOURCES[name],
                        "size_bytes": frozen_row["frozen_size_bytes"],
                    }
                )
                staged_file_checks.append(
                    {
                        "path": str(staged_path),
                        "exists": staged_path.is_file(),
                        "size": staged_path.stat().st_size if staged_path.is_file() else -1,
                        "sha256": sha256_file(staged_path) if staged_path.is_file() else "MISSING",
                        "expected_size": int(frozen_row["frozen_size_bytes"]),
                        "expected_sha256": SOURCES[name],
                    }
                )
    staged_exact = bool(
        staged_fields == expected_staged_fields
        and staged_rows == expected_staged_rows
        and all(
            item["exists"]
            and item["size"] == item["expected_size"]
            and item["sha256"] == item["expected_sha256"]
            for item in staged_file_checks
        )
    )
    add_check(
        checks,
        "S3-STAGED-MANIFEST-EXACT",
        "staging",
        staged_exact,
        {"fields": expected_staged_fields, "rows": expected_staged_rows, "files_match": True},
        {"fields": staged_fields, "rows": staged_rows, "file_checks": staged_file_checks},
        staged_manifest_path,
    )

    config_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    exit_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    artifact_pass_count = 0
    hdf5_pass_count = 0
    inventory_pass_count = 0
    for run_index, (row, expected_pair) in enumerate(
        zip(config_rows, EXPECTED_RUN_ORDER, strict=True), start=1
    ):
        route_id, replicate = expected_pair
        route = route_map[route_id]
        paths = expected_run_paths(route, replicate)
        config_path = paths["config_json"]
        row_identity_pass = bool(
            row.get("route_id") == route_id
            and row.get("replicate") == replicate
            and row.get("route_label_cn") == route["route_label_cn"]
            and row.get("static_boundary") == route["static_boundary"]
            and row.get("execution_status") == "STAGED_NOT_RUN"
            and exact_absolute_path(row.get("config_path"), config_path)
        )
        config = load_json(config_path)
        config_hash = sha256_file(config_path)
        sidecar_hash = paths["config_hash_file"].read_text(encoding="utf-8").strip().upper()
        add_check(
            checks,
            f"S3-CONFIG-SEAL-{run_index:02d}",
            "staging",
            row_identity_pass
            and row.get("config_sha256") == config_hash
            and sidecar_hash == config_hash,
            {"pair": expected_pair, "config_path": str(config_path), "sha256": config_hash},
            {"row": row, "actual_sha256": config_hash, "sidecar_sha256": sidecar_hash},
            config_path,
        )
        expected_path_fields = expected_config_path_fields(paths)
        path_field_results = {
            field: exact_absolute_path(config.get(field), expected)
            for field, expected in expected_path_fields.items()
        }
        config_identity_pass = bool(
            config.get("schema_version") == "BOARD21_STEP3_ROUTE_CONFIG_V1"
            and config.get("route_id") == route_id
            and config.get("replicate") == replicate
            and config.get("route_label_cn") == route["route_label_cn"]
            and config.get("division_identity") == route["division_identity"]
            and config.get("parameter_family") == route["parameter_family"]
            and config.get("static_boundary") == route["static_boundary"]
            and config.get("expected_energy_lengths") == route["lengths"]
            and config.get("embedded_historical_percent") == route["history"]
            and config.get("execution_status") == "STAGED_NOT_RUN"
            and exact_absolute_path(config.get("matlab_executable"), EXPECTED_MATLAB)
            and config.get("allowed_work_files") == [route["upstream"], route["candidate"]]
            and all(path_field_results.values())
        )
        add_check(
            checks,
            f"S3-CONFIG-IDENTITY-PATHS-{run_index:02d}",
            "staging",
            config_identity_pass,
            {"route": route_id, "replicate": replicate, "execution_status": "STAGED_NOT_RUN", "all_absolute_paths_exact": True},
            {"config": config, "path_field_results": path_field_results},
            config_path,
        )

        expected_contracts: list[dict[str, Any]] = []
        for order, kind in enumerate(("upstream", "candidate"), start=1):
            name = route[kind]
            frozen_row = manifest_rows[name]
            staged_path = paths["upstream_file" if kind == "upstream" else "candidate_mlx"]
            expected_contracts.append(
                {
                    "kind": kind,
                    "order": order,
                    "name": name,
                    "author_original_path": str(Path(frozen_row["source_absolute_path"]).resolve()),
                    "frozen_path": str((AUTHOR_ROOT / name).resolve()),
                    "staged_path": str(staged_path),
                    "expected_sha256": SOURCES[name],
                    "copied_sha256": SOURCES[name],
                    "size_bytes": int(frozen_row["frozen_size_bytes"]),
                }
            )
        actual_contracts = normalize_struct_list(config.get("input_contracts"), "config.input_contracts")
        staged_projection = [
            {
                key: int(row_value[key]) if key in {"order", "size_bytes"} else row_value[key]
                for key in (
                    "kind", "order", "name", "author_original_path", "frozen_path",
                    "staged_path", "expected_sha256", "copied_sha256", "size_bytes",
                )
            }
            for row_value in staged_rows
            if row_value["route_id"] == route_id and row_value["replicate"] == replicate
        ]
        contract_files_match = all(
            Path(contract["author_original_path"]).is_file()
            and sha256_file(Path(contract["author_original_path"])) == contract["expected_sha256"]
            and Path(contract["frozen_path"]).is_file()
            and sha256_file(Path(contract["frozen_path"])) == contract["expected_sha256"]
            and Path(contract["staged_path"]).is_file()
            and sha256_file(Path(contract["staged_path"])) == contract["expected_sha256"]
            for contract in expected_contracts
        )
        contracts_pass = actual_contracts == expected_contracts == staged_projection and contract_files_match
        add_check(
            checks,
            f"S3-CONFIG-INPUT-CONTRACTS-{run_index:02d}",
            "input_hash",
            contracts_pass,
            expected_contracts,
            {"config": actual_contracts, "staged_manifest": staged_projection, "all_three_layers_match": contract_files_match},
            config_path,
        )

        expected_instrument_contracts = [
            {"name": name, "path": str((SCRIPT.parent / name).resolve()), "expected_sha256": sealed_tools[name]}
            for name in INSTRUMENT_ORDER
        ]
        actual_instrument_contracts = normalize_struct_list(
            config.get("instrument_contracts"), "config.instrument_contracts"
        )
        instrument_pass = bool(
            config.get("instrument_sha256") == sealed_tools
            and actual_instrument_contracts == expected_instrument_contracts
        )
        add_check(
            checks,
            f"S3-CONFIG-INSTRUMENT-SEAL-{run_index:02d}",
            "instrumentation",
            instrument_pass,
            {"hashes": sealed_tools, "contracts": expected_instrument_contracts},
            {"hashes": config.get("instrument_sha256"), "contracts": actual_instrument_contracts},
            config_path,
        )
        config_by_pair[expected_pair] = {"row": row, "config": config, "paths": paths, "hash": config_hash}

        status = load_json(paths["run_status_json"])
        exit_record = load_json(paths["process_exit_json"])
        exit_by_pair[expected_pair] = exit_record
        success = status.get("execution_status") == "EXECUTION_SUCCESS"
        author_failure = status.get("execution_status") == "EXECUTION_FAIL"
        scientific_name_error = ""
        try:
            status_scientific_names = normalize_string_list(
                status.get("available_scientific_variables"),
                "status.available_scientific_variables",
            )
        except Exception as error:
            status_scientific_names = []
            scientific_name_error = f"{type(error).__name__}: {error}"
        expected_status_config_contract = {
            "hash_file": str(paths["config_hash_file"]),
            "expected_sha256": config_hash,
            "actual_sha256": config_hash,
            "match": True,
        }
        status_environment = status.get("environment")
        status_terminal_pass = bool(
            status.get("schema_version") == "BOARD21_STEP3_ROUTE_STATUS_V1"
            and status.get("route_id") == route_id
            and status.get("replicate") == replicate
            and status.get("route_label_cn") == route["route_label_cn"]
            and status.get("division_identity") == route["division_identity"]
            and status.get("parameter_family") == route["parameter_family"]
            and status.get("static_boundary") == route["static_boundary"]
            and exact_absolute_path(status.get("config_path"), config_path)
            and status.get("config_contract") == expected_status_config_contract
            and status.get("capture_errors") == []
            and isinstance(status_environment, dict)
            and exact_absolute_path(status_environment.get("pwd"), paths["work_dir"])
            and exact_absolute_path(
                status_environment.get("matlab_root"), EXPECTED_MATLAB.parent.parent
            )
            and status_environment.get("matlab_release") == "2025b"
            and isinstance(status_environment.get("matlab_version"), str)
            and bool(status_environment.get("matlab_version"))
            and isinstance(status_environment.get("computer"), str)
            and bool(status_environment.get("computer"))
            and isinstance(status_environment.get("pid"), int)
            and not isinstance(status_environment.get("pid"), bool)
            and status_environment.get("pid") > 0
            and status_environment.get("pid") == exit_record.get("pid")
            and (
                (
                    success
                    and status.get("evidence_status") == "PASS"
                    and status.get("final_status") == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
                    and status.get("process_exit_semantics") == "ZERO"
                    and status.get("error_origin") == "NONE"
                    and not status.get("failed_stage")
                )
                or (
                    author_failure
                    and status.get("evidence_status") == "PASS_FAILURE_EVIDENCE"
                    and status.get("final_status") == "EXECUTION_FAIL_AUTHOR_ERROR_CAPTURED"
                    and status.get("process_exit_semantics") == "NONZERO_RETHROW"
                    and status.get("error_origin") == "AUTHOR_CALL"
                    and status.get("failed_stage") in {"UPSTREAM_ORIGINAL", "CANDIDATE_ORIGINAL_MLX"}
                )
            )
        )
        add_check(
            checks,
            f"S3-STATUS-TERMINAL-CONTRACT-{run_index:02d}",
            "execution",
            status_terminal_pass,
            "exact success terminal tuple or exact author-failure terminal tuple with error_origin",
            {key: status.get(key) for key in ("schema_version", "route_id", "replicate", "execution_status", "evidence_status", "final_status", "process_exit_semantics", "error_origin", "failed_stage")},
            paths["run_status_json"],
        )

        artifact_audit = validate_artifact_seal(
            exit_record,
            paths,
            success,
            author_failure,
            str(status.get("failed_stage", "")),
            bool(status_scientific_names),
        )
        artifact_audit["scientific_name_error"] = scientific_name_error
        artifact_audit["status_scientific_names"] = status_scientific_names
        artifact_audit["scientific_variable_count_match"] = (
            exit_record.get("scientific_variable_count")
            == len(status_scientific_names)
        )
        artifact_audit["pass"] &= bool(
            not scientific_name_error
            and artifact_audit["scientific_variable_count_match"]
        )
        if artifact_audit["pass"]:
            artifact_pass_count += 1
        add_check(
            checks,
            f"S3-ARTIFACT-SEAL-{run_index:02d}",
            "artifact_seal",
            artifact_audit["pass"],
            {"artifact_count": 14, "all_paths_sizes_hashes_required_and_stream_hashes_match": True},
            artifact_audit,
            paths["process_exit_json"],
        )

        expected_matlab_expression = (
            f"addpath('{str(SCRIPT.parent).replace(chr(39), chr(39) * 2)}'); "
            "run_one_board21_energy_route("
            f"'{str(config_path).replace(chr(39), chr(39) * 2)}');"
        )
        expected_matlab_command = [
            str(EXPECTED_MATLAB), "-batch", expected_matlab_expression
        ]
        exit_semantics_pass = bool(
            exit_record.get("schema_version") == "BOARD21_STEP3_PROCESS_EXIT_V1"
            and exit_record.get("route_id") == route_id
            and exit_record.get("replicate") == replicate
            and exit_record.get("command") == expected_matlab_command
            and exit_record.get("display_command")
            == subprocess.list2cmdline(expected_matlab_command)
            and exact_absolute_path(exit_record.get("cwd"), paths["work_dir"])
            and isinstance(exit_record.get("pid"), int)
            and exit_record.get("pid") > 0
            and isinstance(exit_record.get("duration_seconds"), (int, float))
            and exit_record.get("duration_seconds") >= 0
            and exit_record.get("timeout_seconds") == 900
            and exit_record.get("timed_out") is False
            and exit_record.get("status_json_exists") is True
            and exit_record.get("status_json_sha256") == sha256_file(paths["run_status_json"])
            and exit_record.get("status_read_error") == ""
            and exit_record.get("runner_execution_status") == status.get("execution_status")
            and exit_record.get("runner_evidence_status") == status.get("evidence_status")
            and exit_record.get("runner_final_status") == status.get("final_status")
            and exit_record.get("evidence_capture_ok") is True
            and (
                (success and exit_record.get("returncode") == 0 and exit_record.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED")
                or (author_failure and isinstance(exit_record.get("returncode"), int) and exit_record.get("returncode") != 0 and exit_record.get("orchestration_status") == "AUTHOR_FAILURE_EVIDENCE_CAPTURED")
            )
        )
        add_check(
            checks,
            f"S3-PROCESS-EXIT-CONTRACT-{run_index:02d}",
            "execution",
            exit_semantics_pass,
            "exact process exit schema, status seal, no timeout, and success/author-failure semantics",
            exit_record,
            paths["process_exit_json"],
        )

        expected_runtime_hashes: list[dict[str, Any]] = []
        for contract in expected_contracts:
            for layer, field in (
                ("author_original", "author_original_path"),
                ("step1_frozen", "frozen_path"),
                ("run_copy", "staged_path"),
            ):
                expected_runtime_hashes.append(
                    {
                        "layer": layer,
                        "kind": contract["kind"],
                        "path": contract[field],
                        "expected_sha256": contract["expected_sha256"],
                        "actual_sha256": contract["expected_sha256"],
                        "match": True,
                    }
                )
        before_hashes = normalize_struct_list(status.get("input_hashes_before"), "status.input_hashes_before")
        after_hashes = normalize_struct_list(status.get("input_hashes_after"), "status.input_hashes_after")
        add_check(
            checks,
            f"S3-RUNTIME-INPUT-HASHES-{run_index:02d}",
            "input_hash",
            before_hashes == expected_runtime_hashes and after_hashes == expected_runtime_hashes,
            {"before": expected_runtime_hashes, "after": expected_runtime_hashes},
            {"before": before_hashes, "after": after_hashes},
            paths["run_status_json"],
        )
        expected_runtime_instruments = [
            {
                "layer": "instrument", "kind": name,
                "path": str((SCRIPT.parent / name).resolve()),
                "expected_sha256": sealed_tools[name],
                "actual_sha256": sealed_tools[name], "match": True,
            }
            for name in INSTRUMENT_ORDER
        ]
        runtime_instruments = normalize_struct_list(status.get("instrument_contracts"), "status.instrument_contracts")
        add_check(
            checks,
            f"S3-RUNTIME-INSTRUMENTS-{run_index:02d}",
            "instrumentation",
            runtime_instruments == expected_runtime_instruments,
            expected_runtime_instruments,
            runtime_instruments,
            paths["run_status_json"],
        )
        expected_which = [
            {"name": route["upstream"], "expected": str(paths["upstream_file"]), "actual": str(paths["upstream_file"]), "match": True},
            {"name": route["candidate"], "expected": str(paths["candidate_mlx"]), "actual": str(paths["candidate_mlx"]), "match": True},
        ]
        which_rows = normalize_struct_list(status.get("which_contracts"), "status.which_contracts")
        add_check(checks, f"S3-WHICH-{run_index:02d}", "path_resolution", which_rows == expected_which, expected_which, which_rows, paths["run_status_json"])

        expected_work_files = sorted(
            [
                {"name": route[kind], "path": str(paths["upstream_file" if kind == "upstream" else "candidate_mlx"]), "bytes": int(manifest_rows[route[kind]]["frozen_size_bytes"]), "sha256": SOURCES[route[kind]]}
                for kind in ("upstream", "candidate")
            ],
            key=lambda item: item["name"],
        )
        before_files = sorted(normalize_struct_list(status.get("work_files_before"), "status.work_files_before"), key=lambda item: item.get("name", ""))
        after_files = sorted(normalize_struct_list(status.get("work_files_after"), "status.work_files_after"), key=lambda item: item.get("name", ""))
        add_check(
            checks,
            f"S3-WORK-WHITELIST-{run_index:02d}",
            "work_isolation",
            before_files == expected_work_files and after_files == expected_work_files,
            {"before": expected_work_files, "after": expected_work_files},
            {"before": before_files, "after": after_files},
            paths["work_dir"],
        )

        required_hdf5: set[str] = set()
        if status_scientific_names:
            required_hdf5.add("scientific_mat")
        if success:
            required_hdf5.update({"workspace_after_upstream", "workspace_success"})
        elif author_failure:
            required_hdf5.add("workspace_failure")
            if status.get("failed_stage") == "CANDIDATE_ORIGINAL_MLX":
                required_hdf5.add("workspace_after_upstream")
        hdf5_audit = inspect_hdf5_files(paths, required_hdf5)
        if hdf5_audit["pass"]:
            hdf5_pass_count += 1
        add_check(
            checks,
            f"S3-MAT-HDF5-READABLE-{run_index:02d}",
            "workspace",
            hdf5_audit["pass"],
            {"required_hdf5": sorted(required_hdf5), "all_readable": True},
            hdf5_audit,
            paths["output_dir"],
        )

        inventory_error = ""
        inventory_details: dict[str, Any] = {}
        inventory_pass = False
        after_final_inventory: list[dict[str, Any]] = []
        try:
            inventory = load_json(paths["variable_inventory_json"])
            if set(inventory) != {"after_clear", "after_upstream", "after_candidate_or_failure"}:
                raise ValueError(f"inventory top-level fields mismatch: {sorted(inventory)}")
            after_clear_inventory = inventory_records(inventory.get("after_clear"), "after_clear")
            after_upstream_inventory = inventory_records(inventory.get("after_upstream"), "after_upstream")
            after_final_inventory = inventory_records(inventory.get("after_candidate_or_failure"), "after_candidate_or_failure")
            inventory_details["after_clear_count"] = len(after_clear_inventory)
            inventory_pass = len(after_clear_inventory) == 0
            upstream_stage_pass = any(
                item.get("name") == "upstream_original" and item.get("status") == "PASS"
                for item in normalize_struct_list(status.get("stages"), "status.stages")
            )
            if upstream_stage_pass:
                upstream_comparison = compare_inventory_to_workspace(
                    after_upstream_inventory, paths["workspace_after_upstream"], "after_upstream"
                )
                upstream_names = set(h5_names(paths["workspace_after_upstream"]))
                upstream_comparison["required_upstream_variables_present"] = set(route["upstream_required"]).issubset(upstream_names)
                upstream_comparison["pass"] &= upstream_comparison["required_upstream_variables_present"]
                inventory_details["upstream"] = upstream_comparison
                inventory_pass &= upstream_comparison["pass"]
            else:
                no_upstream_snapshot = status.get("failed_stage") == "UPSTREAM_ORIGINAL" and not paths["workspace_after_upstream"].exists() and not after_upstream_inventory
                inventory_details["upstream"] = {"expected_author_failure_before_snapshot": True, "actual": no_upstream_snapshot, "pass": no_upstream_snapshot}
                inventory_pass &= no_upstream_snapshot
            final_workspace = paths["workspace_success"] if success else paths["workspace_failure"]
            final_comparison = compare_inventory_to_workspace(after_final_inventory, final_workspace, "after_candidate_or_failure")
            final_nonempty = len(h5_names(final_workspace)) > 0
            final_comparison["nonempty_workspace"] = final_nonempty
            final_comparison["nonempty_required"] = success
            if success:
                final_comparison["pass"] &= final_nonempty
            inventory_details["final"] = final_comparison
            inventory_pass &= final_comparison["pass"]
        except Exception as error:
            inventory_error = f"{type(error).__name__}: {error}"
            inventory_pass = False
        if inventory_pass:
            inventory_pass_count += 1
        add_check(
            checks,
            f"S3-INVENTORY-WORKSPACE-CROSSCHECK-{run_index:02d}",
            "workspace",
            inventory_pass,
            {
                "structure_exact": True,
                "workspace_names_classes_shapes_sparse_complex_global_match": True,
                "unsupported_root_groups_or_sparse_objects": "REJECT",
                "final_workspace_nonempty_if_success": True,
                "failure_workspace_may_be_empty": True,
            },
            {"error": inventory_error, "details": inventory_details},
            paths["variable_inventory_json"],
        )

        final_workspace = (
            paths["workspace_success"] if success else paths["workspace_failure"]
        )
        scientific_cross = scientific_mat_crosscheck(
            paths,
            status,
            status_scientific_names,
            after_final_inventory,
            final_workspace,
        )
        scientific_cross["top_level_name_parse_error"] = scientific_name_error
        scientific_cross["pass"] = bool(
            scientific_cross.get("pass") and not scientific_name_error
        )
        add_check(
            checks,
            f"S3-SCIENTIFIC-MAT-CROSSCHECK-{run_index:02d}",
            "scientific_output",
            scientific_cross["pass"],
            {
                "scientific_mat_exists_iff_selected_variables_nonempty": True,
                "root_names_exactly_equal_both_status_lists": True,
                "every_selected_variable_matches_inventory_and_final_workspace_metadata_and_exact_content": True,
            },
            scientific_cross,
            paths["scientific_mat"],
        )

        run_record: dict[str, Any] = {
            "route_id": route_id,
            "replicate": replicate,
            "status": status,
            "exit": exit_record,
            "science_valid": False,
            "failure_evidence_valid": False,
            "artifact_audit_pass": artifact_audit["pass"],
            "hdf5_audit_pass": hdf5_audit["pass"],
            "inventory_pass": inventory_pass,
            "scientific_cross_pass": scientific_cross["pass"],
        }
        if success:
            scientific_records: dict[str, dict[str, Any]] = {}
            stored_sums: dict[str, float] = {}
            recomputed_sums: dict[str, float] = {}
            totals: dict[str, float] = {}
            recomputed_totals: dict[str, float] = {}
            lengths: list[int] = []
            formula_error = ""
            formula_match = False
            status_match = False
            sum_comparisons: dict[str, dict[str, Any]] = {}
            total_comparisons: dict[str, dict[str, Any]] = {}
            status_comparisons: dict[str, dict[str, Any]] = {}
            try:
                names = h5_names(paths["scientific_mat"])
                if not set(REQUIRED_FINAL).issubset(names):
                    raise KeyError(f"missing required scientific variables: {sorted(set(REQUIRED_FINAL) - names)}")
                if not set(REQUIRED_FINAL).issubset(status_scientific_names):
                    raise KeyError(
                        "required scientific variables absent from status selection: "
                        f"{sorted(set(REQUIRED_FINAL) - set(status_scientific_names))}"
                    )
                for name in REQUIRED_FINAL:
                    scientific_records[name] = finite_numeric_record(paths["scientific_mat"], name)
                lengths = [
                    int(np.asarray(scientific_records[name]["value"]).size)
                    for name in ("E_total", "E_total_guyan", "E_total_cb")
                ]
                if lengths != route["lengths"]:
                    raise ValueError(f"energy length mismatch: expected={route['lengths']}, actual={lengths}")
                for name in ("energy_sum_orig", "energy_sum_guyan", "energy_sum_cb"):
                    stored_sums[name] = scalar_from_record(scientific_records[name], name)
                for name in ("total_increase_guyan", "total_increase_cb"):
                    totals[name] = scalar_from_record(scientific_records[name], name)
                original_vector = np.asarray(
                    scientific_records["E_total"]["value"], dtype=np.float64
                ).reshape(-1)
                guyan_vector = np.asarray(
                    scientific_records["E_total_guyan"]["value"], dtype=np.float64
                ).reshape(-1)
                cb_vector = np.asarray(
                    scientific_records["E_total_cb"]["value"], dtype=np.float64
                ).reshape(-1)
                if route["sum_scope"] == "all_vectors":
                    recomputed_sums = {
                        "energy_sum_orig": float(np.sum(original_vector)),
                        "energy_sum_guyan": float(np.sum(guyan_vector)),
                        "energy_sum_cb": float(np.sum(cb_vector)),
                    }
                elif route["sum_scope"] == "selected_original_and_cb":
                    retained = np.asarray(route["retained_zero_based"], dtype=int)
                    if np.any(retained < 0) or np.any(retained >= original_vector.size) or np.any(retained >= cb_vector.size):
                        raise IndexError(f"retained index outside energy vector for {route_id}")
                    recomputed_sums = {
                        "energy_sum_orig": float(np.sum(original_vector[retained])),
                        "energy_sum_guyan": float(np.sum(guyan_vector)),
                        "energy_sum_cb": float(np.sum(cb_vector[retained])),
                    }
                else:
                    raise ValueError(f"unknown sum scope: {route['sum_scope']}")
                sum_comparisons = {
                    name: strict_abs_rel_comparison(
                        stored_sums[name], recomputed_sums[name]
                    )
                    for name in stored_sums
                }
                sums_match = all(
                    comparison["pass"]
                    for comparison in sum_comparisons.values()
                )
                denominator = recomputed_sums["energy_sum_orig"] if route["denominator"] == "original" else recomputed_sums["energy_sum_guyan"]
                if not math.isfinite(denominator) or denominator == 0.0:
                    raise ZeroDivisionError(f"historical denominator invalid: {denominator}")
                recomputed_totals = {
                    "total_increase_guyan": (recomputed_sums["energy_sum_guyan"] - recomputed_sums["energy_sum_orig"]) / denominator * 100.0,
                    "total_increase_cb": (recomputed_sums["energy_sum_cb"] - recomputed_sums["energy_sum_orig"]) / denominator * 100.0,
                }
                total_comparisons = {
                    name: strict_abs_rel_comparison(
                        totals[name], recomputed_totals[name]
                    )
                    for name in totals
                }
                totals_match = all(
                    comparison["pass"]
                    for comparison in total_comparisons.values()
                )
                formula_match = sums_match and totals_match
                status_scientific = status.get("scientific")
                if not isinstance(status_scientific, dict):
                    raise TypeError("status.scientific is not an object")
                status_comparisons = {
                    name: strict_abs_rel_comparison(
                        status_scientific.get(name), value
                    )
                    for name, value in {**stored_sums, **totals}.items()
                }
                status_match = bool(
                    status_scientific.get("required_present") is True
                    and status_scientific.get("missing_required") == []
                    and status_scientific.get("lengths_match") is True
                    and status_scientific.get("all_finite") is True
                    and status_scientific.get("energy_lengths") == route["lengths"]
                    and status_scientific.get("expected_energy_lengths")
                    == route["lengths"]
                    and status_scientific.get("embedded_historical_percent")
                    == route["history"]
                    and all(
                        comparison["pass"]
                        for comparison in status_comparisons.values()
                    )
                )
            except Exception as error:
                formula_error = f"{type(error).__name__}: {error}"
            science_valid = bool(
                not formula_error
                and formula_match
                and status_match
                and status_terminal_pass
                and exit_semantics_pass
                and artifact_audit["pass"]
                and hdf5_audit["pass"]
                and inventory_pass
                and scientific_cross["pass"]
                and status.get("error_origin") == "NONE"
                and exit_record.get("returncode") == 0
                and paths["workspace_success"].is_file()
            )
            add_check(
                checks,
                f"S3-SCIENTIFIC-FORMULA-{run_index:02d}",
                "scientific_output",
                science_valid,
                {"lengths": route["lengths"], "sum_match": True, "formula_match": True, "status_match": True, "formula_exception": ""},
                {
                    "lengths": lengths,
                    "stored_sums": stored_sums,
                    "recomputed_sums": recomputed_sums,
                    "sum_comparisons": sum_comparisons,
                    "totals": totals,
                    "recomputed_totals": recomputed_totals,
                    "total_comparisons": total_comparisons,
                    "formula_match": formula_match,
                    "status_match": status_match,
                    "status_comparisons": status_comparisons,
                    "status_terminal_pass": status_terminal_pass,
                    "exit_semantics_pass": exit_semantics_pass,
                    "artifact_audit_pass": artifact_audit["pass"],
                    "hdf5_audit_pass": hdf5_audit["pass"],
                    "inventory_pass": inventory_pass,
                    "scientific_cross_pass": scientific_cross["pass"],
                    "formula_exception": formula_error,
                },
                paths["scientific_mat"],
            )
            run_record.update(
                {
                    "outcome": "SUCCESS",
                    "science_valid": science_valid,
                    "scientific_records": scientific_records,
                    "totals": totals,
                    "formula_error": formula_error,
                }
            )
        elif author_failure:
            error_record = status.get("error") if isinstance(status.get("error"), dict) else {}
            stack_error = ""
            try:
                stack = normalize_struct_list(error_record.get("stack"), "status.error.stack")
            except Exception as error:
                stack = []
                stack_error = f"{type(error).__name__}: {error}"
            failed_stage = str(status.get("failed_stage", ""))
            expected_failed_file = paths["upstream_file"] if failed_stage == "UPSTREAM_ORIGINAL" else paths["candidate_mlx"]
            failure_workspace_names: list[str] = []
            failure_workspace_error = ""
            try:
                failure_workspace_names = sorted(h5_names(paths["workspace_failure"]))
            except Exception as error:
                failure_workspace_error = f"{type(error).__name__}: {error}"
            error_report_error = ""
            error_report_exact_match = False
            error_report_actual_sha256 = ""
            error_report_expected_sha256 = ""
            error_report_actual_size = -1
            error_report_expected_size = -1
            try:
                report_text = str(error_record.get("report", ""))
                if not report_text:
                    report_text = (
                        f"{error_record.get('identifier', '')}: "
                        f"{error_record.get('message', '')}"
                    )
                expected_report_bytes = (report_text + "\n").encode("utf-8")
                actual_report_bytes = paths["error_report"].read_bytes()
                actual_report_bytes.decode("utf-8", errors="strict")
                error_report_expected_size = len(expected_report_bytes)
                error_report_actual_size = len(actual_report_bytes)
                error_report_expected_sha256 = hashlib.sha256(
                    expected_report_bytes
                ).hexdigest().upper()
                error_report_actual_sha256 = hashlib.sha256(
                    actual_report_bytes
                ).hexdigest().upper()
                error_report_exact_match = actual_report_bytes == expected_report_bytes
            except Exception as error:
                error_report_error = f"{type(error).__name__}: {error}"
            failure_evidence_valid = bool(
                status_terminal_pass
                and exit_semantics_pass
                and artifact_audit["pass"]
                and hdf5_audit["pass"]
                and inventory_pass
                and scientific_cross["pass"]
                and status.get("error_origin") == "AUTHOR_CALL"
                and failed_stage in {"UPSTREAM_ORIGINAL", "CANDIDATE_ORIGINAL_MLX"}
                and exact_absolute_path(status.get("failed_file"), expected_failed_file)
                and isinstance(exit_record.get("returncode"), int)
                and exit_record.get("returncode") != 0
                and bool(error_record.get("identifier"))
                and bool(error_record.get("message"))
                and bool(error_record.get("report"))
                and not stack_error
                and len(stack) > 0
                and all(
                    bool(item.get("file"))
                    and bool(item.get("name"))
                    and is_positive_integral_number(item.get("line"))
                    for item in stack
                )
                and paths["workspace_failure"].is_file()
                and not failure_workspace_error
                and not error_report_error
                and error_report_exact_match
            )
            add_check(
                checks,
                f"S3-AUTHOR-FAILURE-EVIDENCE-{run_index:02d}",
                "failure_output",
                failure_evidence_valid,
                {
                    "error_origin": "AUTHOR_CALL",
                    "exact_failed_stage_and_file": True,
                    "nonempty_stack": True,
                    "readable_failure_workspace_may_be_empty": True,
                    "nonzero_returncode": True,
                    "artifact_hdf5_inventory_scientific_cross_gates": True,
                    "error_report_exact_utf8_match_to_status_error_report": True,
                },
                {
                    "failed_stage": failed_stage,
                    "failed_file": status.get("failed_file"),
                    "error_origin": status.get("error_origin"),
                    "identifier": error_record.get("identifier"),
                    "stack": stack,
                    "stack_error": stack_error,
                    "failure_workspace_names": failure_workspace_names,
                    "failure_workspace_error": failure_workspace_error,
                    "error_report_error": error_report_error,
                    "error_report_exact_match": error_report_exact_match,
                    "error_report_expected_size": error_report_expected_size,
                    "error_report_actual_size": error_report_actual_size,
                    "error_report_expected_sha256": error_report_expected_sha256,
                    "error_report_actual_sha256": error_report_actual_sha256,
                    "returncode": exit_record.get("returncode"),
                    "status_terminal_pass": status_terminal_pass,
                    "exit_semantics_pass": exit_semantics_pass,
                    "artifact_audit_pass": artifact_audit["pass"],
                    "hdf5_audit_pass": hdf5_audit["pass"],
                    "inventory_pass": inventory_pass,
                    "scientific_cross_pass": scientific_cross["pass"],
                },
                paths["run_status_json"],
            )
            run_record.update(
                {
                    "outcome": "FAILURE",
                    "failure_evidence_valid": failure_evidence_valid,
                    "error": error_record,
                    "stack": stack,
                    "totals": {},
                }
            )
        else:
            add_check(
                checks,
                f"S3-UNRECOGNIZED-OUTCOME-{run_index:02d}",
                "execution",
                False,
                ["EXECUTION_SUCCESS", "EXECUTION_FAIL"],
                status.get("execution_status"),
                paths["run_status_json"],
            )
            run_record.update({"outcome": "INVALID", "totals": {}})
        per_route_runs.setdefault(route_id, {})[replicate] = run_record

    orchestration_path = ORCHESTRATION_ROOT / "run_all_summary.json"
    orchestration = load_json(orchestration_path)
    expected_run_order_json = [
        {"order": order, "route_id": route_id, "replicate": replicate}
        for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1)
    ]
    route_process_records = normalize_struct_list(orchestration.get("route_process_records"), "orchestration.route_process_records")
    orchestration_route_details: list[dict[str, Any]] = []
    orchestration_routes_pass = len(route_process_records) == 14
    capture_root = ORCHESTRATION_ROOT / "subprocess_captures"
    process_root = ORCHESTRATION_ROOT / "process_snapshots"
    for order, expected_pair in enumerate(EXPECTED_RUN_ORDER, start=1):
        route_id, replicate = expected_pair
        matches = [record for record in route_process_records if record.get("order") == order]
        if len(matches) != 1:
            orchestration_routes_pass = False
            orchestration_route_details.append({"order": order, "record_count": len(matches), "pass": False})
            continue
        record = matches[0]
        config_info = config_by_pair[expected_pair]
        exit_record = exit_by_pair[expected_pair]
        stem = f"{order:02d}__{route_id}__{replicate}"
        stdout_path = capture_root / f"{stem}.stdout.log"
        stderr_path = capture_root / f"{stem}.stderr.log"
        stdout_hash = sha256_file(stdout_path) if stdout_path.is_file() else "MISSING"
        stderr_hash = sha256_file(stderr_path) if stderr_path.is_file() else "MISSING"
        stdout_terminal_json: dict[str, Any] = {}
        stdout_terminal_error = ""
        stdout_terminal_line = b""
        try:
            stdout_payload = stdout_path.read_bytes()
            stdout_terminal_json = terminal_json_from_bytes(
                stdout_payload, f"executor stdout {stem}"
            )
            stdout_terminal_line = terminal_json_line_bytes(
                stdout_payload, f"executor stdout {stem}"
            )
        except Exception as error:
            stdout_terminal_error = f"{type(error).__name__}: {error}"
        executor_terminal_deep_match = bool(
            not stdout_terminal_error and stdout_terminal_json == exit_record
        )
        stdout_terminal_canonical = (
            canonical_json_utf8(stdout_terminal_json)
            if not stdout_terminal_error
            else b""
        )
        expected_executor_command = [
            str(EXPECTED_PYTHON),
            str((SCRIPT.parent / "execute_board21_step3_route.py").resolve()),
            str(config_info["paths"]["config_json"]),
            "--timeout-seconds",
            "900",
        ]
        before_snapshot = process_root / f"{stem}__before.json"
        after_snapshot = process_root / f"{stem}__after.json"
        snapshot_pass = bool(
            before_snapshot.is_file() and json.loads(before_snapshot.read_text(encoding="utf-8")) == []
            and after_snapshot.is_file() and json.loads(after_snapshot.read_text(encoding="utf-8")) == []
        )
        record_pass = bool(
            record.get("order") == order
            and record.get("route_id") == route_id
            and record.get("replicate") == replicate
            and record.get("route_label_cn") == route_map[route_id]["route_label_cn"]
            and exact_absolute_path(record.get("config_path"), config_info["paths"]["config_json"])
            and record.get("config_sha256") == config_info["hash"]
            and record.get("executor_command") == expected_executor_command
            and exact_absolute_path(record.get("executor_cwd"), PROJECT_ROOT)
            and record.get("executor_timeout_seconds") == 1000
            and record.get("executor_timed_out") is False
            and record.get("executor_timeout_error") == ""
            and record.get("executor_internal_timeout_seconds") == 900
            and record.get("executor_internal_timed_out") is False
            and record.get("executor_status_contract_pass") is True
            and record.get("executor_artifact_exclusivity_match") is True
            and record.get("executor_all_required_artifacts_sealed") is True
            and record.get("executor_runtime_log_hashes_match") is True
            and record.get("executor_returncode") == 0
            and record.get("executor_capture_error") == ""
            and record.get("executor_parse_error") == ""
            and record.get("executor_terminal_json_match") is True
            and executor_terminal_deep_match
            and exact_absolute_path(
                record.get("process_exit_json_path"),
                config_info["paths"]["process_exit_json"],
            )
            and record.get("process_exit_json_sha256")
            == sha256_file(config_info["paths"]["process_exit_json"])
            and record.get("process_exit_read_error") == ""
            and record.get("executor_terminal_json_line_sha256")
            == hashlib.sha256(stdout_terminal_line).hexdigest().upper()
            and record.get("executor_terminal_json_utf8_sha256")
            == hashlib.sha256(stdout_terminal_canonical).hexdigest().upper()
            and record.get("matlab_returncode") == exit_record.get("returncode")
            and record.get("orchestration_status") == exit_record.get("orchestration_status")
            and record.get("evidence_capture_ok") is True
            and record.get("instrument_sha256_before") == sealed_tools
            and record.get("instrument_sha256_after") == sealed_tools
            and record.get("instrument_seal_match") is True
            and record.get("post_instrument_error") == ""
            and record.get("target_processes_before") == []
            and record.get("target_processes_after") == []
            and record.get("post_process_query_error") == ""
            and exact_absolute_path(record.get("executor_stdout_path"), stdout_path)
            and exact_absolute_path(record.get("executor_stderr_path"), stderr_path)
            and record.get("executor_stdout_sha256") == stdout_hash
            and record.get("executor_stderr_sha256") == stderr_hash
            and snapshot_pass
        )
        orchestration_routes_pass &= record_pass
        orchestration_route_details.append(
            {
                "order": order,
                "pair": expected_pair,
                "expected_executor_command": expected_executor_command,
                "stdout_hash": stdout_hash,
                "stderr_hash": stderr_hash,
                "stdout_terminal_json": stdout_terminal_json,
                "stdout_terminal_error": stdout_terminal_error,
                "stdout_terminal_json_equals_process_exit": executor_terminal_deep_match,
                "stdout_terminal_json_line_sha256": hashlib.sha256(
                    stdout_terminal_line
                ).hexdigest().upper(),
                "stdout_terminal_json_utf8_sha256": hashlib.sha256(
                    stdout_terminal_canonical
                ).hexdigest().upper(),
                "process_snapshots_empty": snapshot_pass,
                "record": record,
                "pass": record_pass,
            }
        )
    route_record_success_count = sum(
        record.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED"
        for record in route_process_records
    )
    route_record_failure_count = sum(
        record.get("orchestration_status")
        == "AUTHOR_FAILURE_EVIDENCE_CAPTURED"
        for record in route_process_records
    )
    exit_record_success_count = sum(
        record.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED"
        for record in exit_by_pair.values()
    )
    exit_record_failure_count = sum(
        record.get("orchestration_status")
        == "AUTHOR_FAILURE_EVIDENCE_CAPTURED"
        for record in exit_by_pair.values()
    )
    validated_outcome_success_count = sum(
        run.get("outcome") == "SUCCESS"
        for runs in per_route_runs.values()
        for run in runs.values()
    )
    validated_outcome_failure_count = sum(
        run.get("outcome") == "FAILURE"
        for runs in per_route_runs.values()
        for run in runs.values()
    )
    orchestration_count_contract_pass = bool(
        route_record_success_count == exit_record_success_count
        == validated_outcome_success_count
        == orchestration.get("author_execution_success_count")
        and route_record_failure_count == exit_record_failure_count
        == validated_outcome_failure_count
        == orchestration.get("author_execution_failure_count")
        and route_record_success_count + route_record_failure_count == 14
    )
    orchestration_header_pass = bool(
        orchestration.get("schema_version") == "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V2"
        and orchestration.get("status") == "PASS"
        and exact_absolute_path(orchestration.get("project_root"), PROJECT_ROOT)
        and exact_absolute_path(orchestration.get("expected_python"), EXPECTED_PYTHON)
        and orchestration.get("expected_run_order") == expected_run_order_json
        and orchestration.get("sealed_instrument_sha256") == sealed_tools
        and orchestration.get("expected_run_count") == 14
        and orchestration.get("executed_run_count") == 14
        and orchestration.get("unstarted_runs") == []
        and orchestration.get("infrastructure_failure") is False
        and orchestration.get("terminal_error") == {}
        and orchestration.get("interruption_point") == "FINAL_PROCESS_QUERY"
        and orchestration.get("subprocess_contract_pass") is True
        and orchestration.get("process_query_contract_pass") is True
        and orchestration.get("route_contract_pass") is True
        and orchestration.get("author_execution_count_contract_pass") is True
        and exact_absolute_path(
            orchestration.get("process_query_capture_root"),
            ORCHESTRATION_ROOT / "process_query_captures",
        )
        and orchestration.get("timeout_contract_seconds")
        == {
            "stager_python": 120,
            "executor_python_wrapper": 1000,
            "matlab_inside_executor": 900,
            "powershell_process_query": 30,
        }
        and orchestration.get("started_with_target_process_count") == 0
        and orchestration.get("initial_target_processes") == []
        and orchestration.get("final_target_process_count") == 0
        and orchestration.get("final_target_processes") == []
        and orchestration.get("final_process_query_error") == ""
        and orchestration.get("matlab_process_count") == 0
        and orchestration_count_contract_pass
        and orchestration.get("stage_summary") == stage_summary
    )
    dry_summary = orchestration.get("dry_run_summary")
    orchestration_dry_pass = bool(
        isinstance(dry_summary, dict)
        and dry_summary.get("route_count") == 7
        and dry_summary.get("replicate_count") == 2
        and dry_summary.get("run_count") == 14
        and dry_summary.get("source_reference_count") == 14
        and dry_summary.get("unique_source_count") == 12
        and dry_summary.get("protected_input_count") == 53
        and dry_summary.get("category_counts") == EXPECTED_INPUT_CATEGORY_COUNTS
        and dry_summary.get("input_manifest_sha256") == INPUT_MANIFEST_SHA256
        and dry_summary.get("input_freeze_summary_sha256")
        == INPUT_FREEZE_SUMMARY_SHA256
        and dry_summary.get("instrument_sha256") == sealed_tools
    )
    subprocess_records = normalize_struct_list(
        orchestration.get("subprocess_records"), "orchestration.subprocess_records"
    )
    expected_subprocess_names = [
        "stager_dry_run",
        "stager_actual",
        *[
            f"{order:02d}__{route_id}__{replicate}"
            for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1)
        ],
    ]
    expected_subprocess_contracts: dict[str, dict[str, Any]] = {
        "stager_dry_run": {
            "command": [
                str(EXPECTED_PYTHON),
                str((SCRIPT.parent / "stage_board21_step3_runs.py").resolve()),
                "--dry-run",
            ],
            "timeout_seconds": 120,
            "terminal_json": dry_summary,
        },
        "stager_actual": {
            "command": [
                str(EXPECTED_PYTHON),
                str((SCRIPT.parent / "stage_board21_step3_runs.py").resolve()),
            ],
            "timeout_seconds": 120,
            "terminal_json": stage_summary,
        },
    }
    for order, pair in enumerate(EXPECTED_RUN_ORDER, start=1):
        route_id, replicate = pair
        name = f"{order:02d}__{route_id}__{replicate}"
        expected_subprocess_contracts[name] = {
            "command": [
                str(EXPECTED_PYTHON),
                str((SCRIPT.parent / "execute_board21_step3_route.py").resolve()),
                str(config_by_pair[pair]["paths"]["config_json"]),
                "--timeout-seconds",
                "900",
            ],
            "timeout_seconds": 1000,
            "terminal_json": exit_by_pair[pair],
        }
    subprocess_details: list[dict[str, Any]] = []
    subprocess_fields = {
        "name",
        "command",
        "cwd",
        "started_at",
        "finished_at",
        "duration_seconds",
        "timeout_seconds",
        "timed_out",
        "timeout_error",
        "environment_overrides",
        "returncode",
        "stdout_size_bytes",
        "stderr_size_bytes",
        "stdout_sha256",
        "stderr_sha256",
        "terminal_json",
        "terminal_json_error",
        "terminal_json_line_size_bytes",
        "terminal_json_line_sha256",
        "terminal_json_utf8_size_bytes",
        "terminal_json_utf8_sha256",
    }
    orchestration_subprocess_pass = (
        [item.get("name") for item in subprocess_records]
        == expected_subprocess_names
    )
    for item in subprocess_records:
        name = str(item.get("name", ""))
        contract = expected_subprocess_contracts.get(name)
        stdout_path = capture_root / f"{name}.stdout.log"
        stderr_path = capture_root / f"{name}.stderr.log"
        stdout_size = stdout_path.stat().st_size if stdout_path.is_file() else -1
        stderr_size = stderr_path.stat().st_size if stderr_path.is_file() else -1
        stdout_hash = sha256_file(stdout_path) if stdout_path.is_file() else "MISSING"
        stderr_hash = sha256_file(stderr_path) if stderr_path.is_file() else "MISSING"
        stdout_payload = stdout_path.read_bytes() if stdout_path.is_file() else b""
        terminal_value: dict[str, Any] = {}
        terminal_line = b""
        terminal_parse_error = ""
        try:
            terminal_value = terminal_json_from_bytes(
                stdout_payload, f"subprocess stdout {name}"
            )
            terminal_line = terminal_json_line_bytes(
                stdout_payload, f"subprocess stdout {name}"
            )
        except Exception as error:
            terminal_parse_error = f"{type(error).__name__}: {error}"
        expected_terminal = contract.get("terminal_json") if contract else None
        canonical_terminal = (
            canonical_json_utf8(terminal_value) if not terminal_parse_error else b""
        )
        item_pass = bool(
            contract is not None
            and name in expected_subprocess_names
            and set(item) == subprocess_fields
            and item.get("command") == contract["command"]
            and item.get("returncode") == 0
            and exact_absolute_path(item.get("cwd"), PROJECT_ROOT)
            and isinstance(item.get("started_at"), str)
            and bool(item.get("started_at"))
            and isinstance(item.get("finished_at"), str)
            and bool(item.get("finished_at"))
            and isinstance(item.get("duration_seconds"), (int, float))
            and not isinstance(item.get("duration_seconds"), bool)
            and item.get("duration_seconds") >= 0
            and item.get("timeout_seconds") == contract["timeout_seconds"]
            and item.get("timed_out") is False
            and item.get("timeout_error") == ""
            and item.get("environment_overrides")
            == {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            and item.get("stdout_size_bytes") == stdout_size
            and item.get("stderr_size_bytes") == stderr_size
            and item.get("stdout_sha256") == stdout_hash
            and item.get("stderr_sha256") == stderr_hash
            and stderr_size == 0
            and not terminal_parse_error
            and terminal_value == expected_terminal
            and item.get("terminal_json") == expected_terminal
            and item.get("terminal_json_error") == ""
            and item.get("terminal_json_line_size_bytes") == len(terminal_line)
            and item.get("terminal_json_line_sha256")
            == hashlib.sha256(terminal_line).hexdigest().upper()
            and item.get("terminal_json_utf8_size_bytes")
            == len(canonical_terminal)
            and item.get("terminal_json_utf8_sha256")
            == hashlib.sha256(canonical_terminal).hexdigest().upper()
        )
        orchestration_subprocess_pass &= item_pass
        subprocess_details.append(
            {
                "name": name,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "stdout_size": stdout_size,
                "stderr_size": stderr_size,
                "stdout_sha256": stdout_hash,
                "stderr_sha256": stderr_hash,
                "expected_contract": contract,
                "terminal_json": terminal_value,
                "terminal_parse_error": terminal_parse_error,
                "terminal_json_matches_expected": terminal_value
                == expected_terminal,
                "terminal_json_line_size_bytes": len(terminal_line),
                "terminal_json_line_sha256": hashlib.sha256(
                    terminal_line
                ).hexdigest().upper(),
                "terminal_json_utf8_size_bytes": len(canonical_terminal),
                "terminal_json_utf8_sha256": hashlib.sha256(
                    canonical_terminal
                ).hexdigest().upper(),
                "record": item,
                "pass": item_pass,
            }
        )

    process_query_records = normalize_struct_list(
        orchestration.get("process_query_records"),
        "orchestration.process_query_records",
    )
    process_query_script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding=[Console]::OutputEncoding; "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw|pdftoppm)\\.exe$'} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    expected_process_query_command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        process_query_script,
    ]
    process_query_capture_root = ORCHESTRATION_ROOT / "process_query_captures"
    expected_process_queries: list[dict[str, Any]] = [
        {
            "query_name": "00__initial",
            "snapshot": process_root / "00__initial.json",
            "stdout": process_query_capture_root / "00__initial.stdout.log",
            "stderr": process_query_capture_root / "00__initial.stderr.log",
            "summary_processes": orchestration.get("initial_target_processes"),
        }
    ]
    route_record_by_order = {
        int(record["order"]): record
        for record in route_process_records
        if isinstance(record.get("order"), int)
    }
    for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1):
        stem = f"{order:02d}__{route_id}__{replicate}"
        route_record = route_record_by_order.get(order, {})
        expected_process_queries.extend(
            [
                {
                    "query_name": f"{stem}__before",
                    "snapshot": process_root / f"{stem}__before.json",
                    "stdout": process_query_capture_root
                    / f"{stem}__before.stdout.log",
                    "stderr": process_query_capture_root
                    / f"{stem}__before.stderr.log",
                    "summary_processes": route_record.get(
                        "target_processes_before"
                    ),
                },
                {
                    "query_name": f"{stem}__after",
                    "snapshot": process_root / f"{stem}__after.json",
                    "stdout": process_query_capture_root
                    / f"{stem}__after.stdout.log",
                    "stderr": process_query_capture_root
                    / f"{stem}__after.stderr.log",
                    "summary_processes": route_record.get(
                        "target_processes_after"
                    ),
                },
            ]
        )
    expected_process_queries.append(
        {
            "query_name": "99__final",
            "snapshot": process_root / "99__final.json",
            "stdout": process_query_capture_root / "99__final.stdout.log",
            "stderr": process_query_capture_root / "99__final.stderr.log",
            "summary_processes": orchestration.get("final_target_processes"),
        }
    )
    process_query_fields = {
        "schema_version",
        "query_name",
        "command",
        "cwd",
        "started_at",
        "finished_at",
        "duration_seconds",
        "timeout_seconds",
        "timed_out",
        "timeout_error",
        "returncode",
        "stdout_size_bytes",
        "stderr_size_bytes",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_path",
        "stderr_path",
        "capture_error",
        "capture_match",
        "stderr_text",
        "parse_error",
        "raw_process_count",
        "filtered_process_count",
        "processes",
        "ok",
    }
    process_query_details: list[dict[str, Any]] = []
    query_owner_pids: list[int] = []
    orchestration_process_query_pass = bool(
        len(process_query_records) == 30
        and len(expected_process_queries) == 30
        and [item.get("query_name") for item in process_query_records]
        == [item["query_name"] for item in expected_process_queries]
    )
    empty_sha256 = hashlib.sha256(b"").hexdigest().upper()
    for index, expected_query in enumerate(expected_process_queries):
        if index >= len(process_query_records):
            orchestration_process_query_pass = False
            process_query_details.append(
                {
                    "query_name": expected_query["query_name"],
                    "record_missing": True,
                    "pass": False,
                }
            )
            continue
        item = process_query_records[index]
        snapshot_path = expected_query["snapshot"]
        snapshot_error = ""
        try:
            snapshot_value = json.loads(
                snapshot_path.read_text(encoding="utf-8")
            )
        except Exception as error:
            snapshot_value = None
            snapshot_error = f"{type(error).__name__}: {error}"
        capture_error = ""
        raw_processes: list[dict[str, Any]] = []
        independent_filtered_processes: list[dict[str, Any]] = []
        query_owner_candidates: list[dict[str, Any]] = []
        stdout_path = expected_query["stdout"]
        stderr_path = expected_query["stderr"]
        try:
            stdout_bytes = stdout_path.read_bytes()
            stderr_bytes = stderr_path.read_bytes()
            stdout_text = stdout_bytes.decode("utf-8-sig", errors="strict").strip()
            raw_value: Any = [] if not stdout_text else json.loads(stdout_text)
            if isinstance(raw_value, dict):
                raw_value = [raw_value]
            if not isinstance(raw_value, list) or not all(
                isinstance(raw_item, dict) for raw_item in raw_value
            ):
                raise TypeError("raw process query capture is not an object array")
            raw_processes = raw_value
            query_owner_candidates = [
                raw_item
                for raw_item in raw_processes
                if str(raw_item.get("Name", "")).casefold()
                in {"python.exe", "pythonw.exe"}
                and "run_board21_step3_all.py"
                in str(raw_item.get("CommandLine", "")).casefold()
                and is_positive_integral_number(raw_item.get("ProcessId"))
            ]
            if len(query_owner_candidates) != 1:
                raise ValueError(
                    "raw process query capture must identify exactly one run_all owner; "
                    f"found={len(query_owner_candidates)}"
                )
            query_owner_pid = int(query_owner_candidates[0]["ProcessId"])
            query_owner_pids.append(query_owner_pid)
            board_token = str(BOARD_ROOT).casefold()
            for raw_item in raw_processes:
                pid = int(raw_item.get("ProcessId") or -1)
                name = str(raw_item.get("Name") or "")
                command_line = str(raw_item.get("CommandLine") or "")
                if pid == query_owner_pid:
                    continue
                if (
                    name.casefold() == "matlab.exe"
                    or board_token in command_line.casefold()
                ):
                    independent_filtered_processes.append(raw_item)
        except Exception as error:
            stdout_bytes = b""
            stderr_bytes = b""
            capture_error = f"{type(error).__name__}: {error}"
        stdout_hash_value = item.get("stdout_sha256")
        stderr_hash_value = item.get("stderr_sha256")
        item_pass = bool(
            set(item) == process_query_fields
            and item.get("schema_version")
            == "BOARD21_STEP3_PROCESS_QUERY_V1"
            and item.get("query_name") == expected_query["query_name"]
            and item.get("command") == expected_process_query_command
            and exact_absolute_path(item.get("cwd"), PROJECT_ROOT)
            and isinstance(item.get("started_at"), str)
            and bool(item.get("started_at"))
            and isinstance(item.get("finished_at"), str)
            and bool(item.get("finished_at"))
            and isinstance(item.get("duration_seconds"), (int, float))
            and not isinstance(item.get("duration_seconds"), bool)
            and item.get("duration_seconds") >= 0
            and item.get("timeout_seconds") == 30
            and item.get("timed_out") is False
            and item.get("timeout_error") == ""
            and item.get("returncode") == 0
            and exact_absolute_path(item.get("stdout_path"), stdout_path)
            and exact_absolute_path(item.get("stderr_path"), stderr_path)
            and item.get("capture_error") == ""
            and item.get("capture_match") is True
            and not capture_error
            and isinstance(item.get("stdout_size_bytes"), int)
            and not isinstance(item.get("stdout_size_bytes"), bool)
            and item.get("stdout_size_bytes") == len(stdout_bytes)
            and item.get("stderr_size_bytes") == 0
            and isinstance(stdout_hash_value, str)
            and stdout_hash_value
            == hashlib.sha256(stdout_bytes).hexdigest().upper()
            and stderr_hash_value
            == hashlib.sha256(stderr_bytes).hexdigest().upper()
            and stderr_hash_value == empty_sha256
            and stderr_bytes == b""
            and item.get("stderr_text") == ""
            and item.get("parse_error") == ""
            and isinstance(item.get("raw_process_count"), int)
            and not isinstance(item.get("raw_process_count"), bool)
            and item.get("raw_process_count") == len(raw_processes)
            and item.get("filtered_process_count")
            == len(independent_filtered_processes)
            and item.get("processes") == independent_filtered_processes
            and independent_filtered_processes == []
            and item.get("ok") is True
            and not snapshot_error
            and snapshot_value == []
            and snapshot_value == expected_query["summary_processes"]
        )
        orchestration_process_query_pass &= item_pass
        process_query_details.append(
            {
                "query_name": expected_query["query_name"],
                "snapshot_path": str(snapshot_path),
                "snapshot_value": snapshot_value,
                "snapshot_error": snapshot_error,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "raw_capture_error": capture_error,
                "raw_process_count": len(raw_processes),
                "query_owner_candidates": query_owner_candidates,
                "independent_filtered_processes": independent_filtered_processes,
                "summary_processes": expected_query["summary_processes"],
                "record": item,
                "pass": item_pass,
            }
        )
    expected_process_query_capture_files = sorted(
        str(expected_query[kind].resolve())
        for expected_query in expected_process_queries
        for kind in ("stdout", "stderr")
    )
    process_query_capture_set_error = ""
    try:
        actual_process_query_capture_files = sorted(
            str(path.resolve())
            for path in process_query_capture_root.rglob("*")
            if path.is_file()
        )
        unexpected_capture_directories = sorted(
            str(path.resolve())
            for path in process_query_capture_root.rglob("*")
            if path.is_dir()
        )
    except Exception as error:
        actual_process_query_capture_files = []
        unexpected_capture_directories = []
        process_query_capture_set_error = f"{type(error).__name__}: {error}"
    process_query_capture_set_pass = bool(
        process_query_capture_root.is_dir()
        and not process_query_capture_set_error
        and actual_process_query_capture_files
        == expected_process_query_capture_files
        and not unexpected_capture_directories
        and len(query_owner_pids) == 30
        and len(set(query_owner_pids)) == 1
    )
    orchestration_process_query_pass &= process_query_capture_set_pass
    process_query_capture_set_audit = {
        "capture_root": str(process_query_capture_root),
        "expected_files": expected_process_query_capture_files,
        "actual_files": actual_process_query_capture_files,
        "unexpected_directories": unexpected_capture_directories,
        "query_owner_pids": query_owner_pids,
        "single_query_owner_pid": len(query_owner_pids) == 30
        and len(set(query_owner_pids)) == 1,
        "error": process_query_capture_set_error,
        "pass": process_query_capture_set_pass,
    }
    final_snapshot = process_root / "99__final.json"
    initial_snapshot = process_root / "00__initial.json"
    orchestration_snapshot_pass = bool(
        initial_snapshot.is_file() and json.loads(initial_snapshot.read_text(encoding="utf-8")) == []
        and final_snapshot.is_file() and json.loads(final_snapshot.read_text(encoding="utf-8")) == []
    )
    add_check(
        checks,
        "S3-ORCHESTRATION-V2-AND-GATES",
        "execution",
        orchestration_header_pass
        and orchestration_dry_pass
        and orchestration_routes_pass
        and orchestration_subprocess_pass
        and orchestration_process_query_pass
        and orchestration_snapshot_pass,
        {"schema_version": "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V2", "14_ordered_runs": True, "all_tool_seals_process_and_capture_gates": True},
        {
            "header_pass": orchestration_header_pass,
            "dry_run_pass": orchestration_dry_pass,
            "routes_pass": orchestration_routes_pass,
            "author_success_failure_count_contract_pass": orchestration_count_contract_pass,
            "recomputed_author_counts": {
                "route_record_success": route_record_success_count,
                "route_record_failure": route_record_failure_count,
                "exit_record_success": exit_record_success_count,
                "exit_record_failure": exit_record_failure_count,
                "validated_outcome_success": validated_outcome_success_count,
                "validated_outcome_failure": validated_outcome_failure_count,
                "summary_success": orchestration.get(
                    "author_execution_success_count"
                ),
                "summary_failure": orchestration.get(
                    "author_execution_failure_count"
                ),
            },
            "subprocess_captures_pass": orchestration_subprocess_pass,
            "process_query_records_pass": orchestration_process_query_pass,
            "process_query_capture_set": process_query_capture_set_audit,
            "initial_final_snapshots_empty": orchestration_snapshot_pass,
            "route_details": orchestration_route_details,
            "subprocess_details": subprocess_details,
            "process_query_details": process_query_details,
            "orchestration": orchestration,
        },
        orchestration_path,
    )

    repeat_pass_count = 0
    for route_index, route in enumerate(ROUTES, start=1):
        runs = per_route_runs.get(route["route_id"], {})
        first = runs.get("rep01")
        second = runs.get("rep02")
        route_pass = False
        outcome = "MISSING"
        max_abs = math.nan
        max_rel = math.nan
        details: dict[str, Any] = {}
        if first and second and first.get("outcome") == second.get("outcome") == "SUCCESS":
            outcome = "SUCCESS"
            variable_rows: list[dict[str, Any]] = []
            route_pass = bool(first.get("science_valid") and second.get("science_valid"))
            max_abs = 0.0
            max_rel = 0.0
            for name in REQUIRED_FINAL:
                first_record = first.get("scientific_records", {}).get(name)
                second_record = second.get("scientific_records", {}).get(name)
                if not first_record or not second_record:
                    variable_rows.append({"variable": name, "record_present_both": False, "pass": False})
                    route_pass = False
                    continue
                a = np.asarray(first_record["value"], dtype=np.float64)
                b = np.asarray(second_record["value"], dtype=np.float64)
                metadata_checks = {
                    "matlab_class": first_record["matlab_class"] == second_record["matlab_class"],
                    "dtype": first_record["dtype"] == second_record["dtype"],
                    "dtype_matches_matlab_class": first_record[
                        "dtype_matches_matlab_class"
                    ]
                    is True
                    and second_record["dtype_matches_matlab_class"] is True,
                    "shape": first_record["shape"] == second_record["shape"],
                    "matlab_shape": first_record["matlab_shape"]
                    == second_record["matlab_shape"],
                    "complex_flag": first_record["is_complex"] == second_record["is_complex"],
                    "empty_flag": first_record["is_empty"] == second_record["is_empty"],
                    "sparse_flag": first_record["is_sparse"]
                    == second_record["is_sparse"]
                    is False,
                    "global_flag": first_record["is_global"]
                    == second_record["is_global"]
                    is False,
                }
                if a.shape != b.shape:
                    local_abs = math.inf
                    local_rel = math.inf
                else:
                    difference = np.abs(a - b)
                    local_abs = float(np.max(difference)) if difference.size else 0.0
                    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), np.finfo(float).tiny)
                    local_rel = float(np.max(difference / scale)) if difference.size else 0.0
                thresholds = {
                    "max_abs_le_1e-12": local_abs <= 1e-12,
                    "max_rel_le_1e-12": local_rel <= 1e-12,
                }
                variable_pass = all(metadata_checks.values()) and all(thresholds.values())
                route_pass &= variable_pass
                max_abs = max(max_abs, local_abs)
                max_rel = max(max_rel, local_rel)
                variable_rows.append(
                    {"variable": name, "metadata_checks": metadata_checks, "thresholds": thresholds, "max_abs": local_abs, "max_rel": local_rel, "pass": variable_pass}
                )
            details = {"variables": variable_rows, "both_science_valid": bool(first.get("science_valid") and second.get("science_valid"))}
        elif first and second and first.get("outcome") == second.get("outcome") == "FAILURE":
            outcome = "FAILURE"
            a_status = first["status"]
            b_status = second["status"]
            a_error = first["error"]
            b_error = second["error"]
            a_stack = first.get("stack", [])
            b_stack = second.get("stack", [])
            first_location_a = (Path(a_stack[0].get("file", "")).name, a_stack[0].get("name"), int(a_stack[0].get("line", 0))) if a_stack else ("", "", 0)
            first_location_b = (Path(b_stack[0].get("file", "")).name, b_stack[0].get("name"), int(b_stack[0].get("line", 0))) if b_stack else ("", "", 0)
            comparisons = {
                "both_failure_evidence_valid": bool(first.get("failure_evidence_valid") and second.get("failure_evidence_valid")),
                "both_nonempty_stack": bool(a_stack and b_stack),
                "error_origin": a_status.get("error_origin") == b_status.get("error_origin") == "AUTHOR_CALL",
                "stage": a_status.get("failed_stage") == b_status.get("failed_stage"),
                "file": Path(a_status.get("failed_file", "")).name == Path(b_status.get("failed_file", "")).name,
                "identifier": bool(a_error.get("identifier")) and a_error.get("identifier") == b_error.get("identifier"),
                "message": normalized_error_message(str(a_error.get("message", ""))) == normalized_error_message(str(b_error.get("message", ""))),
                "first_stack_location": first_location_a == first_location_b,
            }
            route_pass = all(comparisons.values())
            details = {"comparisons": comparisons, "first_location_rep01": first_location_a, "first_location_rep02": first_location_b}
        add_check(
            checks,
            f"S3-REPEAT-{route_index:02d}",
            "repeatability",
            route_pass,
            "two science-valid successes with identical MATLAB_class/dtype/shape and both max_abs/max_rel <= 1e-12, or two evidence-valid identical author failures with nonempty stacks",
            {"outcome": outcome, "max_abs": max_abs, "max_rel": max_rel, "details": details},
            RUN_ROOT / route["route_id"],
        )
        if route_pass:
            repeat_pass_count += 1
        first_totals = first.get("totals", {}) if first else {}
        first_guyan = first_totals.get("total_increase_guyan")
        first_cb = first_totals.get("total_increase_cb")
        history_diff_guyan = first_guyan - route["history"][0] if isinstance(first_guyan, (int, float)) else math.nan
        history_diff_cb = first_cb - route["history"][1] if isinstance(first_cb, (int, float)) else math.nan
        route_results.append(
            {
                "route_id": route["route_id"], "static_boundary": route["static_boundary"],
                "execution_outcome": outcome, "repeat_status": "PASS" if route_pass else "FAIL",
                "max_abs_difference": max_abs, "max_relative_difference": max_rel,
                "embedded_historical_guyan_percent": route["history"][0], "embedded_historical_cb_percent": route["history"][1],
                "rep01_guyan_percent": first_guyan if isinstance(first_guyan, (int, float)) else "",
                "rep01_cb_percent": first_cb if isinstance(first_cb, (int, float)) else "",
                "history_difference_guyan_percent": history_diff_guyan, "history_difference_cb_percent": history_diff_cb,
                "paper_formula_4_45_status": "NOT_EVALUATED_STEP3", "table4_1_status": "HISTORICAL_NOT_ADJUDICATED",
            }
        )
        repeat_rows.append(
            {"route_id": route["route_id"], "outcome": outcome, "repeat_pass": route_pass, "max_abs_difference": max_abs, "max_relative_difference": max_rel, "details_json": json.dumps(details, ensure_ascii=False, sort_keys=True)}
        )

    boundary = publication_and_process_snapshot()
    add_check(
        checks,
        "S3-PUBLICATION-BOUNDARY",
        "publication",
        not boundary["publication_query_error"]
        and not boundary["formal_present"]
        and not boundary["failure_present"]
        and not boundary["board22_present"],
        {"query_error": "", "formal": [], "failure": [], "board22": []},
        {"query_error": boundary["publication_query_error"], "formal": boundary["formal_present"], "failure": boundary["failure_present"], "board22": boundary["board22_present"]},
        PROJECT_ROOT / "test",
    )
    add_check(
        checks,
        "S3-RESIDUAL-PROCESSES",
        "process",
        not boundary["process_query_error"] and not boundary["residual_processes"],
        {"query_error": "", "processes": []},
        {"query_error": boundary["process_query_error"], "processes": boundary["residual_processes"]},
        BOARD_ROOT,
    )
    add_check(checks, "S3-ALL-ROUTES-REPEAT", "scientific_execution", repeat_pass_count == 7, 7, repeat_pass_count, RUN_ROOT)

    failed_ids = [row["check_id"] for row in checks if row["status"] == "FAIL"]
    check_ids = [row["check_id"] for row in checks]
    summary = {
        "schema_version": "BOARD21_STEP3_INDEPENDENT_VALIDATION_V2",
        "status": "PASS" if not failed_ids and len(set(check_ids)) == len(check_ids) else "FAIL",
        "check_count": len(checks),
        "passed_count": sum(row["status"] == "PASS" for row in checks),
        "failed_count": len(failed_ids),
        "failed_check_ids": failed_ids,
        "check_ids_unique": len(set(check_ids)) == len(check_ids),
        "route_count": 7,
        "run_count": 14,
        "successful_route_count": sum(row["execution_outcome"] == "SUCCESS" for row in route_results),
        "failed_route_count": sum(row["execution_outcome"] == "FAILURE" for row in route_results),
        "repeat_pass_route_count": repeat_pass_count,
        "artifact_seal_pass_run_count": artifact_pass_count,
        "hdf5_readable_pass_run_count": hdf5_pass_count,
        "inventory_workspace_crosscheck_pass_run_count": inventory_pass_count,
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        "protected_input_row_count": 53,
        "orchestration_schema_version": orchestration.get("schema_version"),
        "formula_4_45_evaluated": False,
        "table4_1_adjudicated": False,
        "matlab_executed": True,
        "formal_success_directory_count": len(boundary["formal_present"]),
        "prepublication_failure_directory_count": len(boundary["failure_present"]),
        "board22_named_root_count": len(boundary["board22_present"]),
        "residual_target_process_count": len(boundary["residual_processes"]),
        "publication_query_error": boundary["publication_query_error"],
        "process_query_error": boundary["process_query_error"],
        "preflight_summary": preflight_summary,
        "scientific_status": "AUTHOR_HISTORICAL_ROUTES_EXECUTED_FORMULA_CORRECTNESS_PENDING_STEP4",
    }
    return checks, route_results, repeat_rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_failure_record_best_effort(
    failure: dict[str, Any], validation_root_created: bool
) -> tuple[str, list[str]]:
    """Write exclusively; never touch a validation root this attempt did not create."""
    errors: list[str] = []

    def attempt(candidate: Path) -> tuple[bool, bool]:
        failure["failure_record_destination"] = str(candidate)
        failure["failure_record_write_errors_before_destination"] = list(errors)
        failure["failure_record_written"] = True
        failure["failure_record_path"] = str(candidate)
        try:
            with candidate.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n"
                )
            return True, False
        except FileExistsError as error:
            failure["failure_record_written"] = False
            failure["failure_record_path"] = ""
            errors.append(f"{candidate}:FileExistsError: {error}")
            return False, True
        except Exception as error:
            failure["failure_record_written"] = False
            failure["failure_record_path"] = ""
            errors.append(f"{candidate}:{type(error).__name__}: {error}")
            return False, False

    if validation_root_created:
        primary = VALIDATION_ROOT / "validation_failure.json"
        primary_written, _ = attempt(primary)
        if primary_written:
            return str(primary), errors

    fallback_root = BOARD_ROOT / "logs" / "step3_validation_failures"
    try:
        fallback_root.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        errors.append(
            "fallback_directory_creation:"
            f"{type(error).__name__}: {error}"
        )
        return "", errors
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")
    for sequence in range(1, 101):
        candidate = fallback_root / (
            f"validation_failure_{timestamp}_pid{os.getpid()}_{sequence:03d}.json"
        )
        written, collision = attempt(candidate)
        if written:
            return str(candidate), errors
        if not collision:
            break
    return "", errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    validation_root_created = False
    try:
        VALIDATION_ROOT.mkdir(parents=True, exist_ok=False)
        validation_root_created = True
        checks, routes, repeats, summary = validate()
        write_csv(VALIDATION_ROOT / "checks.csv", checks)
        write_csv(VALIDATION_ROOT / "route_results.csv", routes)
        write_csv(VALIDATION_ROOT / "repeat_comparison.csv", repeats)
        with (VALIDATION_ROOT / "validation_summary.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if summary["status"] == "PASS" else 1
    except Exception as error:
        boundary = publication_and_process_snapshot()
        failure = {
            "schema_version": "BOARD21_STEP3_INDEPENDENT_VALIDATION_FAILURE_V2",
            "status": "VALIDATION_EXCEPTION",
            "failed_at": datetime.now().astimezone().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "validation_root_created_by_this_attempt": validation_root_created,
            "preexisting_validation_root_was_not_written": bool(
                not validation_root_created and VALIDATION_ROOT.exists()
            ),
            "formal_publication_boundary": {
                "formal_present": boundary["formal_present"],
                "failure_present": boundary["failure_present"],
                "board22_present": boundary["board22_present"],
                "query_error": boundary["publication_query_error"],
                "pass": not boundary["publication_query_error"]
                and not boundary["formal_present"]
                and not boundary["failure_present"]
                and not boundary["board22_present"],
            },
            "residual_process_boundary": {
                "processes": boundary["residual_processes"],
                "query_error": boundary["process_query_error"],
                "pass": not boundary["residual_processes"]
                and not boundary["process_query_error"],
            },
        }
        failure_record_path, failure_record_errors = write_failure_record_best_effort(
            failure, validation_root_created
        )
        failure["failure_record_written"] = bool(failure_record_path)
        failure["failure_record_path"] = failure_record_path
        failure["failure_record_write_errors"] = failure_record_errors
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

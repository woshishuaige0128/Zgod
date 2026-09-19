#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读汇总图10已有证据，不运行求解器、搜索或严格评价器。

输入只限于已有全树审计、历史掩膜回归、R01-R04只读审计、粗增益扫描、
H05/H06评价与可选H07评价产物。输出仅为JSON与CSV，不制作图件或HTML。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCRIPT = Path(__file__).resolve()
CASE_ROOT = SCRIPT.parent.parent
DELIVERY_ROOT = CASE_ROOT.parents[1]
EVALUATION_ROOT = CASE_ROOT / "evaluation"
DEFAULT_OUTPUT = EVALUATION_ROOT / "final_evidence_summary"

FULL_TREE_SCAN = DELIVERY_ROOT / "00_证据记录" / "01_全材料生成链扫描" / "扫描摘要.json"
FULL_TREE_REPORT = DELIVERY_ROOT / "00_证据记录" / "02_图10生成链全树终审.md"

HISTORY_DIR = EVALUATION_ROOT / "batch_ranker_reg_final"
R01_R04_DIR = EVALUATION_ROOT / "r01_r04_target_audit_v2"
GAIN_SWEEP_DIR = EVALUATION_ROOT / "coarse_gain_sweep_v1"
H05_H06_DIR = EVALUATION_ROOT / "historical_diagnostic_fullgrid_v1"

SCHEMA = "FIG10_FINAL_EVIDENCE_SUMMARY_V1"
BATCH_SCHEMA = "FIG10_BATCH_TARGET_EVALUATOR_V1"
EXPECTED_TARGET_SHA256 = "9312FB45595499C4242BF00DAC344CE016CB64F844CB410EA89ECB1F6C8BC7E4"
EXPECTED_ACTIVE_FIGURE_SHA256 = "EEA26CEFA38B9666AEF48C6E9355B8B23C14365F8D0DFFBD1E8E2E61646B9847"
EXPECTED_FULL_TREE_SCAN_SHA256 = "16FC6B77444AA7A1ABE6D7DB02EC86D5131E4A2D2D3893B2FD8501321A2BAE4D"
CALIBRATION_LABEL = "目标引导的校准计算复现"
HISTORICAL_LABEL = "历史MAT候选（绘图数据，不是计算合同）"

CURVES = (
    ("division1_original", 1, "Original"),
    ("division1_craig_bampton", 1, "Craig-Bampton"),
    ("division1_guyan", 1, "Guyan"),
    ("division2_original", 2, "Original"),
    ("division2_craig_bampton", 2, "Craig-Bampton"),
    ("division2_guyan", 2, "Guyan"),
)
CURVE_IDS = tuple(item[0] for item in CURVES)
CURVE_INDEX = {curve_id: index for index, curve_id in enumerate(CURVE_IDS)}

ROW_FIELDS = (
    "source_category",
    "source_group",
    "evidence_label",
    "reported_evidence_label",
    "candidate_id",
    "contract_id",
    "parameter_variant",
    "input_mode",
    "candidate_rank",
    "curve_source_rank",
    "ranking_eligibility_status",
    "candidate_strict_overall_status",
    "candidate_strict_curve_pass_count",
    "candidate_topology_violation_count",
    "curve_id",
    "division",
    "method",
    "route_id",
    "strict_curve_status",
    "topology_ranking_gate",
    "reported_topology_ranking_gate",
    "component_count_8_connected",
    "hole_pixel_count",
    "returned_boundary_count",
    "stable_point_count",
    "mask_coverage_state",
    "source_axis_evidence_eligibility",
    "integration_axis",
    "input_semantics_axis",
    "target_boundary_point_count",
    "candidate_boundary_point_count",
    "boundary_point_count_signed_error",
    "boundary_point_count_abs_error",
    "set_difference_count",
    "ordered_exact_original",
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
    "tau1_axis_prefix_index",
    "tau2_axis_prefix_index",
    "target_tau1_axis_index",
    "target_tau2_axis_index",
    "tau1_axis_abs_error_samples",
    "tau2_axis_abs_error_samples",
    "total_axis_abs_error_samples",
    "tau1_axis_farthest_index",
    "tau2_axis_farthest_index",
    "tau1_axis_holes_before_farthest",
    "tau2_axis_holes_before_farthest",
    "mask_sha256",
    "strict_summary_sha256",
    "route_input_fingerprint",
    "blind_manifest_sha256",
    "checkpoint_sha256",
    "points_sha256",
    "grid_axes_sha256",
    "route_summary_sha256",
    "bundle_sha256",
    "route_operator_sha256",
    "source_batch_sha256",
    "source_summary_path",
    "source_summary_sha256",
    "source_curve_metrics_path",
    "source_curve_metrics_sha256",
    "source_artifact_manifest_path",
    "source_artifact_manifest_sha256",
    "target_sha256",
    "strict_evaluator_sha256",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_sha256(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"JSON不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(payload, dict), f"JSON顶层不是对象：{path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    require(path.is_file(), f"CSV不存在：{path}")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def relative(path: Path) -> str:
    path = path.resolve()
    try:
        return path.relative_to(DELIVERY_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def evidence_file(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"证据文件不存在：{path}")
    return {
        "path": relative(path),
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def verify_artifact_manifest(directory: Path) -> dict[str, Any]:
    manifest = directory / "artifact_hashes.csv"
    rows = read_csv(manifest)
    require(rows and {"path", "bytes", "sha256"} <= set(rows[0]), f"产物清单字段错误：{manifest}")
    seen: set[str] = set()
    total_bytes = 0
    for row in rows:
        rel = row["path"].replace("\\", "/")
        rel_path = Path(rel)
        require(not rel_path.is_absolute() and ".." not in rel_path.parts, f"产物清单路径越界：{rel}")
        require(rel not in seen, f"产物清单路径重复：{rel}")
        seen.add(rel)
        actual = directory / rel_path
        require(actual.is_file(), f"产物清单文件缺失：{actual}")
        expected_bytes = int(row["bytes"])
        require(actual.stat().st_size == expected_bytes, f"产物字节数变化：{actual}")
        require(sha256_file(actual) == row["sha256"].upper(), f"产物SHA-256变化：{actual}")
        total_bytes += expected_bytes
    return {
        "status": "PASS",
        "manifest": evidence_file(manifest),
        "verified_artifact_count": len(rows),
        "verified_artifact_bytes": total_bytes,
    }


def optional_int(value: Any) -> int | str:
    if value is None or str(value).strip() == "":
        return ""
    return int(value)


def optional_float(value: Any) -> float | str:
    if value is None or str(value).strip() == "":
        return ""
    result = float(value)
    require(math.isfinite(result), f"浮点指标不是有限数：{value}")
    return result


def optional_bool(value: Any) -> bool | str:
    if value is None or str(value).strip() == "":
        return ""
    if isinstance(value, bool):
        return value
    normalized = str(value).strip().lower()
    require(normalized in {"true", "false"}, f"布尔字段非法：{value}")
    return normalized == "true"


def endpoint(value: Any) -> list[int] | str:
    if value is None or str(value).strip() == "":
        return ""
    parsed = value if isinstance(value, list) else json.loads(str(value))
    require(isinstance(parsed, list) and len(parsed) == 2, f"端点字段非法：{value}")
    return [int(parsed[0]), int(parsed[1])]


def normalize_topology_gate(value: Any) -> str:
    normalized = str(value)
    if normalized == "PASS":
        return "PASS"
    if normalized in {"REJECTED", "REJECTED_TOPOLOGY"}:
        return "REJECTED_TOPOLOGY"
    raise ValueError(f"未知拓扑门状态：{value}")


def coverage_state(stable_point_count: int) -> str:
    if stable_point_count == 0:
        return "ALL_UNSTABLE"
    if stable_point_count == 31 * 67:
        return "ALL_STABLE"
    return "PARTIAL_STABLE"


def gain_variant(input_root: Any) -> str:
    text = str(input_root).replace("\\", "/")
    match = re.search(r"gain_scale_(0(?:p\d+)?|1)(?:_|/|$)", text)
    if not match:
        return ""
    return match.group(1).replace("p", ".")


def load_full_tree_audit() -> dict[str, Any]:
    scan = read_json(FULL_TREE_SCAN)
    scan_evidence = evidence_file(FULL_TREE_SCAN)
    report_evidence = evidence_file(FULL_TREE_REPORT)
    require(scan_evidence["sha256"] == EXPECTED_FULL_TREE_SCAN_SHA256, "全树扫描摘要SHA-256变化")
    require(scan.get("status") == "SCAN_COMPLETE_WITH_READ_LIMITATIONS", "全树扫描状态错误")
    require(int(scan.get("file_count", -1)) == 6135, "全树扫描文件数不是6135")
    require(int(scan.get("source_protection_match_count", -1)) == 6135, "全树扫描源保护匹配数不是6135")
    require(int(scan.get("source_protection_changed_count", -1)) == 0, "全树扫描发现源文件变化")
    require(int(scan.get("source_protection_read_failed_count", -1)) == 0, "全树扫描源保护复核有读取失败")

    report = FULL_TREE_REPORT.read_text(encoding="utf-8")
    required_report_fragments = (
        "未找到生成最终六条图10边界或历史 lqr_2/lqr_3 掩膜的完整程序",
        EXPECTED_TARGET_SHA256,
        EXPECTED_ACTIVE_FIGURE_SHA256,
        "投稿图 `fig10_stability_domain.pdf`",
        CALIBRATION_LABEL,
    )
    for fragment in required_report_fragments:
        require(fragment in report, f"全树终审报告缺少预期证据片段：{fragment}")

    return {
        "source_id": "full_tree_generation_chain_audit",
        "status": "PASS_WITH_DOCUMENTED_READ_LIMITATIONS",
        "scan_status": scan["status"],
        "scan_file_count": int(scan["file_count"]),
        "scan_error_count": int(scan["error_count"]),
        "source_protection_match_count": int(scan["source_protection_match_count"]),
        "source_protection_changed_count": int(scan["source_protection_changed_count"]),
        "conclusion": "当前RHTS交付树中存在部分谱半径程序，但未找到最终六条图10边界或历史lqr_2/lqr_3掩膜的完整生成程序。",
        "evidence_files": [scan_evidence, report_evidence],
    }


def batch_curve_row(
    row: Mapping[str, str],
    candidate: Mapping[str, Any],
    source_category: str,
    source_group: str,
    evidence_label: str,
    source: Mapping[str, Any],
) -> dict[str, Any]:
    tau1_error = int(row["tau1_axis_prefix_intercept_error_samples"])
    tau2_error = int(row["tau2_axis_prefix_intercept_error_samples"])
    stable_points = int(row["stable_point_count"])
    reported_gate = row["topology_ranking_gate"]
    return {
        "source_category": source_category,
        "source_group": source_group,
        "evidence_label": evidence_label,
        "reported_evidence_label": source["reported_evidence_label"],
        "candidate_id": candidate["candidate_id"],
        "contract_id": candidate["contract_id"],
        "parameter_variant": gain_variant(candidate.get("input_root", "")),
        "input_mode": candidate["input_mode"],
        "candidate_rank": candidate.get("rank", ""),
        "curve_source_rank": "",
        "ranking_eligibility_status": candidate["ranking_eligibility_status"],
        "candidate_strict_overall_status": candidate["strict_overall_status"],
        "candidate_strict_curve_pass_count": int(candidate["strict_curve_pass_count"]),
        "candidate_topology_violation_count": int(candidate["topology_violation_count"]),
        "curve_id": row["curve_id"],
        "division": int(row["division"]),
        "method": row["method"],
        "route_id": row["route_id"],
        "strict_curve_status": row["strict_curve_status"],
        "topology_ranking_gate": normalize_topology_gate(reported_gate),
        "reported_topology_ranking_gate": reported_gate,
        "component_count_8_connected": int(row["component_count_8_connected"]),
        "hole_pixel_count": int(row["hole_pixel_count"]),
        "returned_boundary_count": int(row["returned_boundary_count"]),
        "stable_point_count": stable_points,
        "mask_coverage_state": coverage_state(stable_points),
        "source_axis_evidence_eligibility": "",
        "integration_axis": "",
        "input_semantics_axis": "",
        "target_boundary_point_count": int(row["target_boundary_point_count"]),
        "candidate_boundary_point_count": int(row["candidate_boundary_point_count"]),
        "boundary_point_count_signed_error": int(row["boundary_point_count_signed_error"]),
        "boundary_point_count_abs_error": int(row["boundary_point_count_abs_error"]),
        "set_difference_count": int(row["set_difference_count"]),
        "ordered_exact_original": optional_bool(row["ordered_exact_original"]),
        "set_exact": optional_bool(row["set_exact"]),
        "start_endpoint_exact": optional_bool(row["start_endpoint_exact"]),
        "end_endpoint_exact": optional_bool(row["end_endpoint_exact"]),
        "candidate_start_endpoint": endpoint(row["candidate_start_endpoint"]),
        "candidate_end_endpoint": endpoint(row["candidate_end_endpoint"]),
        "target_start_endpoint": endpoint(row["target_start_endpoint"]),
        "target_end_endpoint": endpoint(row["target_end_endpoint"]),
        "endpoint_l1_error_steps_original": int(row["endpoint_l1_error_steps_original"]),
        "symmetric_hausdorff_steps": optional_float(row["symmetric_hausdorff_steps"]),
        "symmetric_hausdorff_ms": optional_float(row["symmetric_hausdorff_ms"]),
        "point_levenshtein_original": int(row["point_levenshtein_original"]),
        "tau1_axis_prefix_index": int(row["tau1_axis_origin_prefix_last_index"]),
        "tau2_axis_prefix_index": int(row["tau2_axis_origin_prefix_last_index"]),
        "target_tau1_axis_index": int(row["target_tau1_axis_intercept_index"]),
        "target_tau2_axis_index": int(row["target_tau2_axis_intercept_index"]),
        "tau1_axis_abs_error_samples": tau1_error,
        "tau2_axis_abs_error_samples": tau2_error,
        "total_axis_abs_error_samples": tau1_error + tau2_error,
        "tau1_axis_farthest_index": int(row["tau1_axis_rightmost_stable_index"]),
        "tau2_axis_farthest_index": int(row["tau2_axis_highest_stable_index"]),
        "tau1_axis_holes_before_farthest": int(row["tau1_axis_hole_count_before_rightmost"]),
        "tau2_axis_holes_before_farthest": int(row["tau2_axis_hole_count_before_highest"]),
        "mask_sha256": row["mask_sha256"],
        "strict_summary_sha256": candidate["strict_summary_sha256"],
        "route_input_fingerprint": row["route_input_fingerprint"],
        "blind_manifest_sha256": row["blind_manifest_sha256"],
        "checkpoint_sha256": row["checkpoint_sha256"],
        "points_sha256": row["points_sha256"],
        "grid_axes_sha256": row["grid_axes_sha256"],
        "route_summary_sha256": row["route_summary_sha256"],
        "bundle_sha256": row["bundle_sha256"],
        "route_operator_sha256": row["route_operator_sha256"],
        "source_batch_sha256": source["batch_sha256"],
        "source_summary_path": source["summary"]["path"],
        "source_summary_sha256": source["summary"]["sha256"],
        "source_curve_metrics_path": source["curve_metrics"]["path"],
        "source_curve_metrics_sha256": source["curve_metrics"]["sha256"],
        "source_artifact_manifest_path": source["artifact_verification"]["manifest"]["path"],
        "source_artifact_manifest_sha256": source["artifact_verification"]["manifest"]["sha256"],
        "target_sha256": source["target_sha256"],
        "strict_evaluator_sha256": source["strict_evaluator_sha256"],
    }


def load_batch(
    directory: Path,
    source_category: str,
    source_group: str,
    evidence_label: str,
    expected_contracts: set[str] | None = None,
    selected_contracts: set[str] | None = None,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    summary_path = directory / "batch_evaluation_summary.json"
    curve_path = directory / "curve_metrics.csv"
    summary = read_json(summary_path)
    require(summary.get("schema_version") == BATCH_SCHEMA, f"批量评价schema错误：{summary_path}")
    require(summary.get("status") == "PASS", f"批量评价状态不是PASS：{summary_path}")
    artifact = verify_artifact_manifest(directory)
    candidates = summary.get("candidates")
    require(isinstance(candidates, list) and candidates, f"批量评价candidates为空：{summary_path}")
    candidate_by_id = {str(item["candidate_id"]): item for item in candidates}
    require(len(candidate_by_id) == len(candidates), f"批量评价candidate_id重复：{summary_path}")
    actual_contracts = {str(item["contract_id"]) for item in candidates}
    if expected_contracts is not None:
        require(actual_contracts == expected_contracts, f"批量评价合同集错误：{actual_contracts} != {expected_contracts}")
    selected_ids = {
        candidate_id
        for candidate_id, item in candidate_by_id.items()
        if selected_contracts is None or str(item["contract_id"]) in selected_contracts
    }
    require(selected_ids, f"批量评价未选中任何候选：{directory}")

    curve_rows = read_csv(curve_path)
    require(len(curve_rows) == len(candidates) * len(CURVE_IDS), f"批量评价逐曲线行数错误：{curve_path}")
    groups: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in curve_rows:
        require(row["candidate_id"] in candidate_by_id, f"逐曲线行含未知候选：{row['candidate_id']}")
        groups[row["candidate_id"]].append(row)
    for candidate_id in candidate_by_id:
        require({row["curve_id"] for row in groups[candidate_id]} == set(CURVE_IDS), f"{candidate_id}未恰好覆盖六曲线")

    source = {
        "source_id": source_group,
        "source_category": source_category,
        "status": "PASS",
        "directory": relative(directory),
        "summary": evidence_file(summary_path),
        "curve_metrics": evidence_file(curve_path),
        "artifact_verification": artifact,
        "batch_sha256": str(summary["batch_sha256"]),
        "target_sha256": str(summary["target_sha256_reported_by_strict_evaluator"]).upper(),
        "strict_evaluator_sha256": str(summary["strict_evaluator_sha256"]).upper(),
        "reported_evidence_label": str(summary.get("evidence_label", "")),
        "reported_candidate_count": int(summary["candidate_count"]),
        "selected_candidate_count": len(selected_ids),
    }
    require(source["target_sha256"] == EXPECTED_TARGET_SHA256, f"目标SHA-256错误：{directory}")
    if source_category != "HISTORICAL_MAT_CANDIDATE":
        require(evidence_label == CALIBRATION_LABEL, "来源约束计算候选标签错误")

    normalized_rows: list[dict[str, Any]] = []
    candidate_summaries: list[dict[str, Any]] = []
    for candidate_id in sorted(selected_ids):
        candidate = candidate_by_id[candidate_id]
        normalized_rows.extend(
            batch_curve_row(row, candidate, source_category, source_group, evidence_label, source)
            for row in groups[candidate_id]
        )
        candidate_summaries.append(
            {
                "source_category": source_category,
                "source_group": source_group,
                "evidence_label": evidence_label,
                "reported_evidence_label": source["reported_evidence_label"],
                "candidate_id": candidate_id,
                "contract_id": candidate["contract_id"],
                "parameter_variant": gain_variant(candidate.get("input_root", "")),
                "input_mode": candidate["input_mode"],
                "rank": candidate.get("rank", ""),
                "ranking_eligibility_status": candidate["ranking_eligibility_status"],
                "strict_overall_status": candidate["strict_overall_status"],
                "strict_curve_pass_count": int(candidate["strict_curve_pass_count"]),
                "failed_route_count": int(candidate["failed_route_count"]),
                "topology_violation_count": int(candidate["topology_violation_count"]),
                "topology_violations": json.loads(candidate["topology_violations_json"]),
                "total_abs_boundary_point_count_error": int(candidate["total_abs_boundary_point_count_error"]),
                "total_set_difference_count": int(candidate["total_set_difference_count"]),
                "total_point_levenshtein_original": int(candidate["total_point_levenshtein_original"]),
                "maximum_symmetric_hausdorff_steps": float(candidate["maximum_symmetric_hausdorff_steps"]),
                "sum_symmetric_hausdorff_steps": float(candidate["sum_symmetric_hausdorff_steps"]),
                "total_endpoint_l1_error_steps_original": int(candidate["total_endpoint_l1_error_steps_original"]),
                "total_axis_prefix_intercept_error_samples": int(candidate["total_axis_prefix_intercept_error_samples"]),
                "total_stable_point_count": int(candidate["total_stable_point_count"]),
                "source_batch_sha256": source["batch_sha256"],
                "source_summary_sha256": source["summary"]["sha256"],
            }
        )
    return source, normalized_rows, candidate_summaries


def load_r01_r04() -> tuple[dict[str, Any], list[dict[str, Any]], list[dict[str, Any]]]:
    summary_path = R01_R04_DIR / "audit_summary.json"
    curve_path = R01_R04_DIR / "source_curve_metrics.csv"
    summary = read_json(summary_path)
    require(summary.get("schema_version") == "FIG10_ARCHIVED_R01_R04_TARGET_AUDIT_V2", "R01-R04审计schema错误")
    require(summary.get("status") == "PASS", "R01-R04审计状态不是PASS")
    artifact = verify_artifact_manifest(R01_R04_DIR)
    all_rows = read_csv(curve_path)
    calculated = [row for row in all_rows if row["source_class"] == "CALCULATED_MASK"]
    historical = [row for row in all_rows if row["source_class"] == "HISTORICAL_MASK"]
    require(len(calculated) == 24 and len(historical) == 6, "R01-R04审计计算/历史行数错误")
    require({row["source_id"] for row in calculated} == {"R01", "R02", "R03", "R04"}, "R01-R04来源集错误")
    require(
        {row["curve_id"] for row in historical if row["strict_curve_status"] == "PASS"}
        == {"division1_original", "division2_original"},
        "R01-R04审计中历史掩膜通过集错误",
    )
    source = {
        "source_id": "archived_r01_r04_read_only_audit",
        "source_category": "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
        "status": "PASS",
        "directory": relative(R01_R04_DIR),
        "summary": evidence_file(summary_path),
        "curve_metrics": evidence_file(curve_path),
        "artifact_verification": artifact,
        "batch_sha256": str(summary["batch_sha256"]),
        "target_sha256": str(summary["target_sha256"]).upper(),
        "strict_evaluator_sha256": str(summary["strict_evaluator_sha256"]).upper(),
        "reported_evidence_label": "",
        "reported_candidate_count": 4,
        "selected_candidate_count": 4,
    }
    require(source["target_sha256"] == EXPECTED_TARGET_SHA256, "R01-R04目标SHA-256错误")
    normalized_rows: list[dict[str, Any]] = []
    candidate_summaries: list[dict[str, Any]] = []
    by_source: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in calculated:
        by_source[row["source_id"]].append(row)
    for source_id in ("R01", "R02", "R03", "R04"):
        group = by_source[source_id]
        require({row["curve_id"] for row in group} == set(CURVE_IDS), f"{source_id}未恰好覆盖六曲线")
        topology_violations = [row["curve_id"] for row in group if normalize_topology_gate(row["topology_ranking_gate"]) != "PASS"]
        strict_pass_count = sum(row["strict_curve_status"] == "PASS" for row in group)
        eligibility = "ELIGIBLE" if not topology_violations else "REJECTED_TOPOLOGY"
        strict_status = "PASS" if strict_pass_count == 6 else "FAIL"
        for row in group:
            tau1_error = int(row["tau1_axis_abs_error_samples"])
            tau2_error = int(row["tau2_axis_abs_error_samples"])
            normalized_rows.append(
                {
                    "source_category": "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
                    "source_group": "archived_r01_r04_read_only_audit",
                    "evidence_label": CALIBRATION_LABEL,
                    "reported_evidence_label": "",
                    "candidate_id": source_id,
                    "contract_id": source_id,
                    "parameter_variant": f"{row['integration_axis']}|{row['input_semantics_axis']}",
                    "input_mode": "ARCHIVED_FROZEN_31X67_MASK",
                    "candidate_rank": "",
                    "curve_source_rank": optional_int(row["calculated_source_rank_for_curve"]),
                    "ranking_eligibility_status": eligibility,
                    "candidate_strict_overall_status": strict_status,
                    "candidate_strict_curve_pass_count": strict_pass_count,
                    "candidate_topology_violation_count": len(topology_violations),
                    "curve_id": row["curve_id"],
                    "division": int(row["division"]),
                    "method": row["method"],
                    "route_id": f"{source_id}_{row['curve_id']}",
                    "strict_curve_status": row["strict_curve_status"],
                    "topology_ranking_gate": normalize_topology_gate(row["topology_ranking_gate"]),
                    "reported_topology_ranking_gate": row["topology_ranking_gate"],
                    "component_count_8_connected": int(row["component_count_8_connected"]),
                    "hole_pixel_count": int(row["hole_pixel_count"]),
                    "returned_boundary_count": int(row["returned_boundary_count"]),
                    "stable_point_count": int(row["stable_point_count"]),
                    "mask_coverage_state": row["mask_coverage_state"],
                    "source_axis_evidence_eligibility": row["source_axis_evidence_eligibility"],
                    "integration_axis": row["integration_axis"],
                    "input_semantics_axis": row["input_semantics_axis"],
                    "target_boundary_point_count": int(row["target_boundary_point_count"]),
                    "candidate_boundary_point_count": int(row["candidate_boundary_point_count"]),
                    "boundary_point_count_signed_error": int(row["boundary_point_count_signed_error"]),
                    "boundary_point_count_abs_error": int(row["boundary_point_count_abs_error"]),
                    "set_difference_count": int(row["set_difference_count"]),
                    "ordered_exact_original": optional_bool(row["ordered_exact_original"]),
                    "set_exact": optional_bool(row["set_exact"]),
                    "start_endpoint_exact": optional_bool(row["start_endpoint_exact"]),
                    "end_endpoint_exact": optional_bool(row["end_endpoint_exact"]),
                    "candidate_start_endpoint": endpoint(row["candidate_start_endpoint"]),
                    "candidate_end_endpoint": endpoint(row["candidate_end_endpoint"]),
                    "target_start_endpoint": endpoint(row["target_start_endpoint"]),
                    "target_end_endpoint": endpoint(row["target_end_endpoint"]),
                    "endpoint_l1_error_steps_original": int(row["endpoint_l1_error_steps_original"]),
                    "symmetric_hausdorff_steps": optional_float(row["symmetric_hausdorff_steps"]),
                    "symmetric_hausdorff_ms": optional_float(row["symmetric_hausdorff_ms"]),
                    "point_levenshtein_original": int(row["point_levenshtein_original"]),
                    "tau1_axis_prefix_index": int(row["tau1_axis_prefix_index"]),
                    "tau2_axis_prefix_index": int(row["tau2_axis_prefix_index"]),
                    "target_tau1_axis_index": int(row["target_tau1_axis_index"]),
                    "target_tau2_axis_index": int(row["target_tau2_axis_index"]),
                    "tau1_axis_abs_error_samples": tau1_error,
                    "tau2_axis_abs_error_samples": tau2_error,
                    "total_axis_abs_error_samples": tau1_error + tau2_error,
                    "tau1_axis_farthest_index": int(row["tau1_axis_farthest_index"]),
                    "tau2_axis_farthest_index": int(row["tau2_axis_farthest_index"]),
                    "tau1_axis_holes_before_farthest": int(row["tau1_axis_holes_before_farthest"]),
                    "tau2_axis_holes_before_farthest": int(row["tau2_axis_holes_before_farthest"]),
                    "mask_sha256": row["mask_sha256"],
                    "strict_summary_sha256": row["strict_summary_sha256"],
                    "route_input_fingerprint": "",
                    "blind_manifest_sha256": "",
                    "checkpoint_sha256": "",
                    "points_sha256": "",
                    "grid_axes_sha256": "",
                    "route_summary_sha256": "",
                    "bundle_sha256": "",
                    "route_operator_sha256": "",
                    "source_batch_sha256": source["batch_sha256"],
                    "source_summary_path": source["summary"]["path"],
                    "source_summary_sha256": source["summary"]["sha256"],
                    "source_curve_metrics_path": source["curve_metrics"]["path"],
                    "source_curve_metrics_sha256": source["curve_metrics"]["sha256"],
                    "source_artifact_manifest_path": source["artifact_verification"]["manifest"]["path"],
                    "source_artifact_manifest_sha256": source["artifact_verification"]["manifest"]["sha256"],
                    "target_sha256": source["target_sha256"],
                    "strict_evaluator_sha256": source["strict_evaluator_sha256"],
                }
            )
        candidate_summaries.append(
            {
                "source_category": "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
                "source_group": "archived_r01_r04_read_only_audit",
                "evidence_label": CALIBRATION_LABEL,
                "candidate_id": source_id,
                "contract_id": source_id,
                "parameter_variant": f"{group[0]['integration_axis']}|{group[0]['input_semantics_axis']}",
                "input_mode": "ARCHIVED_FROZEN_31X67_MASK",
                "rank": "",
                "ranking_eligibility_status": eligibility,
                "strict_overall_status": strict_status,
                "strict_curve_pass_count": strict_pass_count,
                "failed_route_count": 6 - strict_pass_count,
                "topology_violation_count": len(topology_violations),
                "topology_violations": topology_violations,
                "total_abs_boundary_point_count_error": sum(int(row["boundary_point_count_abs_error"]) for row in group),
                "total_set_difference_count": sum(int(row["set_difference_count"]) for row in group),
                "total_point_levenshtein_original": sum(int(row["point_levenshtein_original"]) for row in group),
                "maximum_symmetric_hausdorff_steps": max(float(row["symmetric_hausdorff_steps"]) for row in group),
                "sum_symmetric_hausdorff_steps": sum(float(row["symmetric_hausdorff_steps"]) for row in group),
                "total_endpoint_l1_error_steps_original": sum(int(row["endpoint_l1_error_steps_original"]) for row in group),
                "total_axis_prefix_intercept_error_samples": sum(int(row["total_axis_abs_error_samples"]) for row in group),
                "total_stable_point_count": sum(int(row["stable_point_count"]) for row in group),
                "source_batch_sha256": source["batch_sha256"],
                "source_summary_sha256": source["summary"]["sha256"],
            }
        )
    return source, normalized_rows, candidate_summaries


def discover_h07_evaluation() -> tuple[Path | None, dict[str, Any]]:
    matches: list[Path] = []
    for summary_path in sorted(EVALUATION_ROOT.glob("*/batch_evaluation_summary.json")):
        payload = read_json(summary_path)
        if payload.get("schema_version") != BATCH_SCHEMA:
            continue
        candidates = payload.get("candidates")
        if isinstance(candidates, list) and any(str(item.get("contract_id")) == "H07" for item in candidates):
            matches.append(summary_path.parent)
    require(len(matches) <= 1, f"发现多个H07评价来源，无法唯一选择：{matches}")
    if matches:
        return matches[0], {
            "contract_id": "H07",
            "status": "PRESENT",
            "evaluation_directory": relative(matches[0]),
            "pending_reason": "",
        }
    return None, {
        "contract_id": "H07",
        "status": "PENDING",
        "evaluation_directory": "",
        "pending_reason": "NO_H07_BATCH_EVALUATION_RESULT_FOUND",
        "searched_pattern": relative(EVALUATION_ROOT / "*" / "batch_evaluation_summary.json"),
    }


def csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    return value


def atomic_write_json(path: Path, payload: Mapping[str, Any]) -> None:
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8", newline="\n")
    os.replace(temp, path)


def atomic_write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field, "")) for field in fields})
    os.replace(temp, path)


def build(output_dir: Path) -> dict[str, Any]:
    output_dir = output_dir.resolve()
    if output_dir.exists():
        require(output_dir.is_dir() and not any(output_dir.iterdir()), f"输出目录必须不存在或为空：{output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)

    full_tree = load_full_tree_audit()
    history_source, history_rows, history_candidates = load_batch(
        HISTORY_DIR,
        "HISTORICAL_MAT_CANDIDATE",
        "historical_mask_regression",
        HISTORICAL_LABEL,
        expected_contracts={"REGRESSION"},
    )
    require(
        {row["curve_id"] for row in history_rows if row["strict_curve_status"] == "PASS"}
        == {"division1_original", "division2_original"},
        "历史掩膜回归必须仅两条Original通过",
    )
    r01_source, r01_rows, r01_candidates = load_r01_r04()
    gain_source, gain_rows, gain_candidates = load_batch(
        GAIN_SWEEP_DIR,
        "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
        "coarse_gain_sweep",
        CALIBRATION_LABEL,
        expected_contracts={"B1", "B2", "B3"},
    )
    require(len(gain_candidates) == 27 and len(gain_rows) == 162, "粗增益扫描必须含27候选/162曲线行")
    h_source, h_rows, h_candidates = load_batch(
        H05_H06_DIR,
        "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
        "historical_diagnostic_h05_h06",
        CALIBRATION_LABEL,
        expected_contracts={"H05", "H06"},
    )

    sources = [history_source, r01_source, gain_source, h_source]
    curve_rows = history_rows + r01_rows + gain_rows + h_rows
    candidate_summaries = history_candidates + r01_candidates + gain_candidates + h_candidates

    h07_dir, h07_status = discover_h07_evaluation()
    if h07_dir is not None:
        h07_source, h07_rows, h07_candidates = load_batch(
            h07_dir,
            "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
            "historical_diagnostic_h07",
            CALIBRATION_LABEL,
            selected_contracts={"H07"},
        )
        require(len(h07_candidates) == 1 and len(h07_rows) == 6, "H07评价必须恰好一候选/六曲线")
        sources.append(h07_source)
        curve_rows.extend(h07_rows)
        candidate_summaries.extend(h07_candidates)

    target_hashes = {row["target_sha256"] for row in curve_rows}
    evaluator_hashes = {row["strict_evaluator_sha256"] for row in curve_rows}
    require(target_hashes == {EXPECTED_TARGET_SHA256}, f"各证据批次目标SHA-256不一致：{target_hashes}")
    require(len(evaluator_hashes) == 1, f"各证据批次严格评价器SHA-256不一致：{evaluator_hashes}")

    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in curve_rows:
        require(set(row) == set(ROW_FIELDS), f"归一化逐曲线字段不闭合：{row.get('candidate_id')}/{row.get('curve_id')}")
        grouped[(row["source_category"], row["source_group"], row["candidate_id"])].append(row)
    require(len(grouped) == len(candidate_summaries), "候选摘要与逐曲线分组数不一致")
    for key, rows in grouped.items():
        require(len(rows) == 6 and {row["curve_id"] for row in rows} == set(CURVE_IDS), f"候选未恰好覆盖六曲线：{key}")

    category_order = {
        "HISTORICAL_MAT_CANDIDATE": 0,
        "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE": 1,
    }
    curve_rows.sort(
        key=lambda row: (
            category_order[row["source_category"]],
            row["source_group"],
            row["candidate_rank"] if isinstance(row["candidate_rank"], int) else 10**9,
            str(row["candidate_id"]).casefold(),
            CURVE_INDEX[row["curve_id"]],
        )
    )
    candidate_summaries.sort(
        key=lambda row: (
            category_order[row["source_category"]],
            row["source_group"],
            row["rank"] if isinstance(row["rank"], int) else 10**9,
            str(row["candidate_id"]).casefold(),
        )
    )

    historical_curve_rows = [row for row in curve_rows if row["source_category"] == "HISTORICAL_MAT_CANDIDATE"]
    calculated_curve_rows = [row for row in curve_rows if row["source_category"] == "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE"]
    strict_pass_rows = [row for row in curve_rows if row["strict_curve_status"] == "PASS"]
    topology_rejected_candidates = [row for row in candidate_summaries if row["ranking_eligibility_status"] == "REJECTED_TOPOLOGY"]

    payload: dict[str, Any] = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "completion_status": "COMPLETE" if h07_status["status"] == "PRESENT" else "COMPLETE_WITH_OPTIONAL_H07_PENDING",
        "scope": "EVALUATOR_SIDE_READ_ONLY_SUMMARY_NO_SOLVER_NO_SEARCH_NO_REEVALUATION_NO_FIGURE_NO_HTML",
        "claim_boundary": "本汇总不证明已恢复作者原始计算合同。",
        "evidence_identity_layers": {
            "current_article_active_figure": {
                "source_category": "CURRENT_ARTICLE_ACTIVE_FIGURE",
                "asset_name": "fig10_stability_domain.pdf",
                "article_asset_role": "ACTIVE_ARTICLE_FIGURE_AS_RECORDED_BY_FULL_TREE_AUDIT",
                "master_thesis_sources": ["图4-4 第一类子结构划分稳定域", "图4-5 第二类子结构划分稳定域"],
                "relationship_status": "DRAWING_LEVEL_CONSISTENT_WITH_MASTER_THESIS",
                "evidence_level": "DRAWING_LEVEL_VECTOR_TRACING_NOT_COMPUTATION_LEVEL",
                "active_figure_sha256_reported_by_full_tree_audit": EXPECTED_ACTIVE_FIGURE_SHA256,
                "plotted_data_sha256_reported_by_full_tree_audit": EXPECTED_TARGET_SHA256,
                "curve_count": 6,
                "boundary_point_count": 386,
            },
            "historical_mat_candidate": {
                "source_category": "HISTORICAL_MAT_CANDIDATE",
                "assets": ["lqr_2.mat", "lqr_3.mat"],
                "evidence_label": HISTORICAL_LABEL,
                "relationship_status": "TWO_ORIGINAL_CURVES_STRICT_PASS_FOUR_REDUCED_CURVES_STRICT_FAIL",
                "strict_pass_curve_ids": ["division1_original", "division2_original"],
                "claim_boundary": "历史MAT是绘图数据快照，不提供可执行计算参数合同。",
            },
            "source_constrained_calculation_candidate": {
                "source_category": "SOURCE_CONSTRAINED_CALCULATION_CANDIDATE",
                "evidence_label": CALIBRATION_LABEL,
                "relationship_status": "NO_INCLUDED_CANDIDATE_STRICTLY_MATCHES_ALL_SIX_CURVES",
                "claim_boundary": "目标引导评分后得到的候选不得写成已恢复作者原始合同。",
            },
        },
        "full_tree_audit": full_tree,
        "optional_evidence": {"H07": h07_status},
        "counts": {
            "evidence_source_count": len(sources),
            "candidate_count": len(candidate_summaries),
            "curve_result_row_count": len(curve_rows),
            "historical_candidate_count": len(history_candidates),
            "historical_curve_result_row_count": len(historical_curve_rows),
            "source_constrained_calculation_candidate_count": len(candidate_summaries) - len(history_candidates),
            "source_constrained_calculation_curve_result_row_count": len(calculated_curve_rows),
            "strict_pass_curve_result_count": len(strict_pass_rows),
            "strict_pass_source_constrained_calculation_curve_result_count": sum(
                row["strict_curve_status"] == "PASS" for row in calculated_curve_rows
            ),
            "topology_rejected_candidate_count": len(topology_rejected_candidates),
        },
        "target_sha256": EXPECTED_TARGET_SHA256,
        "strict_evaluator_sha256": next(iter(evaluator_hashes)),
        "evidence_sources": sources,
        "candidate_summaries": candidate_summaries,
        "curve_results": curve_rows,
        "outputs": {
            "json": relative(output_dir / "final_evidence_summary.json"),
            "csv": relative(output_dir / "final_evidence_summary.csv"),
        },
        "canonical_hash_contract": "SHA-256 of canonical JSON payload before adding canonical_payload_sha256",
    }
    payload["canonical_payload_sha256"] = canonical_sha256(payload)

    csv_rows = [
        {"final_summary_canonical_sha256": payload["canonical_payload_sha256"], **row}
        for row in curve_rows
    ]
    json_path = output_dir / "final_evidence_summary.json"
    csv_path = output_dir / "final_evidence_summary.csv"
    atomic_write_json(json_path, payload)
    atomic_write_csv(csv_path, ("final_summary_canonical_sha256", *ROW_FIELDS), csv_rows)
    return {
        "status": payload["status"],
        "completion_status": payload["completion_status"],
        "counts": payload["counts"],
        "h07": h07_status,
        "canonical_payload_sha256": payload["canonical_payload_sha256"],
        "json_path": str(json_path),
        "json_sha256": sha256_file(json_path),
        "csv_path": str(csv_path),
        "csv_sha256": sha256_file(csv_path),
        "script_sha256": sha256_file(SCRIPT),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT, help="必须不存在或为空的汇总输出目录")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result = build(args.output_dir)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": SCHEMA,
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                ensure_ascii=False,
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

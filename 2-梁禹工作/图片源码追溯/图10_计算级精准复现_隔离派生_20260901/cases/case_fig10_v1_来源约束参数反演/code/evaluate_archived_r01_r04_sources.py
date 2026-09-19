#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""只读评价板块20封存的R01-R04计算掩膜与历史掩膜。

本程序不导入、不调用任何求解器，不重算R01-R04。它只读取板块20最终封存包中
已存在的24个计算掩膜与6个历史掩膜，逐文件核对封存SHA-256，再调用现有
strict_target_evaluator/fig10_extract_mask_boundaries目标侧逻辑。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import strict_target_evaluator as evaluator


SCRIPT = Path(__file__).resolve()
REPOSITORY_ROOT = SCRIPT.parents[5]
BOARD20_PACKAGE = (
    REPOSITORY_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
    / "outputs"
    / "step8g_图4-4图4-5最终中文失败审计包"
)
FILE_MANIFEST = BOARD20_PACKAGE / "文件清单与SHA256.csv"
PACKAGE_SEAL = BOARD20_PACKAGE / "验证记录" / "步骤8G最终封存验收" / "步骤8G最终封存验收摘要.json"
CONTRACT_REGISTRY = SCRIPT.parent.parent / "contracts" / "known_board20_contracts.json"
DEFAULT_OUTPUT = SCRIPT.parent.parent / "evaluation" / "archived_r01_r04_target_audit"

SCHEMA = "FIG10_ARCHIVED_R01_R04_TARGET_AUDIT_V2"
MS_PER_SAMPLE = 1000.0 / 1024.0
EXPECTED_SHAPE = (31, 67)
GRID_POINT_COUNT = EXPECTED_SHAPE[0] * EXPECTED_SHAPE[1]
RANKING_CONTRACT = (
    "topology_rejection",
    "strict_failure",
    "boundary_point_count_abs_error",
    "set_difference_count",
    "point_levenshtein_original",
    "symmetric_hausdorff_steps",
    "endpoint_l1_error_steps_original",
    "total_axis_abs_error_samples",
)


@dataclass(frozen=True)
class CurveSpec:
    curve_id: str
    figure: str
    division: int
    method: str
    file_method: str


CURVES = (
    CurveSpec("division1_original", "4-4", 1, "Original", "Original"),
    CurveSpec("division1_craig_bampton", "4-4", 1, "Craig-Bampton", "Craig-Bampton"),
    CurveSpec("division1_guyan", "4-4", 1, "Guyan", "Guyan"),
    CurveSpec("division2_original", "4-5", 2, "Original", "Original"),
    CurveSpec("division2_craig_bampton", "4-5", 2, "Craig-Bampton", "Craig-Bampton"),
    CurveSpec("division2_guyan", "4-5", 2, "Guyan", "Guyan"),
)
CURVE_INDEX = {curve.curve_id: index for index, curve in enumerate(CURVES)}

SOURCE_INFO: dict[str, dict[str, str]] = {
    "R01": {
        "source_class": "CALCULATED_MASK",
        "integration_axis": "scalar_alpha_0p25",
        "input_semantics_axis": "generalized_force",
        "display_name": "论文CARE_alpha025_广义力",
    },
    "R02": {
        "source_class": "CALCULATED_MASK",
        "integration_axis": "scalar_alpha_0p25",
        "input_semantics_axis": "acceleration",
        "display_name": "论文CARE_alpha025_加速度",
    },
    "R03": {
        "source_class": "CALCULATED_MASK",
        "integration_axis": "route_matrix_al",
        "input_semantics_axis": "generalized_force",
        "display_name": "论文CARE_矩阵al_广义力",
    },
    "R04": {
        "source_class": "CALCULATED_MASK",
        "integration_axis": "route_matrix_al",
        "input_semantics_axis": "acceleration",
        "display_name": "论文CARE_矩阵al_加速度",
    },
    "HISTORICAL": {
        "source_class": "HISTORICAL_MASK",
        "integration_axis": "NOT_A_CALCULATION_CONTRACT",
        "input_semantics_axis": "NOT_A_CALCULATION_CONTRACT",
        "display_name": "历史lqr_2/lqr_3最终掩膜",
    },
}
SOURCE_ORDER = tuple(SOURCE_INFO)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_hash(payload: Any) -> str:
    raw = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp, path)


def write_json(path: Path, payload: Any) -> None:
    write_text(path, json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n")


def write_csv(path: Path, fields: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})
    os.replace(temp, path)


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(payload, dict), f"JSON顶层不是对象：{path}")
    return payload


def load_sealed_manifest() -> tuple[dict[str, dict[str, str]], dict[str, Any]]:
    require(FILE_MANIFEST.is_file(), f"板块20文件清单不存在：{FILE_MANIFEST}")
    with FILE_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(rows and {"相对路径", "字节数", "SHA256"} <= set(rows[0]), "板块20文件清单字段错误")
    by_path = {row["相对路径"].replace("\\", "/"): row for row in rows}
    require(len(by_path) == len(rows), "板块20文件清单含重复路径")
    seal = read_json(PACKAGE_SEAL)
    require(seal.get("package_seal_status") == "PASS", "板块20最终封存状态不是PASS")
    require(int(seal.get("fail_count", -1)) == 0, "板块20最终封存含失败项")
    return by_path, seal


def relative_mask_path(source_id: str, curve: CurveSpec) -> str:
    if source_id == "HISTORICAL":
        return (
            "计算结果/候选掩膜与边界/历史稳定掩膜31x67/"
            f"历史_图{curve.figure}_{curve.file_method}_共同网格稳定掩膜31x67.csv"
        )
    return (
        "计算结果/候选掩膜与边界/候选稳定掩膜31x67/"
        f"候选_图{curve.figure}_{curve.file_method}_{source_id}_稳定掩膜31x67.csv"
    )


def load_mask(path: Path) -> tuple[list[list[int]], dict[str, Any]]:
    matrix: list[list[int]] = []
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for line_no, raw_row in enumerate(csv.reader(stream), start=1):
            require(raw_row, f"掩膜空行：{path}:{line_no}")
            require(all(value.strip() in {"0", "1"} for value in raw_row), f"掩膜非0/1：{path}:{line_no}")
            matrix.append([int(value.strip()) for value in raw_row])
    require(len(matrix) == EXPECTED_SHAPE[0], f"掩膜行数错误：{path}")
    require(all(len(row) == EXPECTED_SHAPE[1] for row in matrix), f"掩膜列数错误：{path}")

    def prefix(values: Sequence[int]) -> int:
        last = -1
        for index, value in enumerate(values):
            if value != 1:
                break
            last = index
        return last

    tau1 = matrix[0]
    tau2 = [row[0] for row in matrix]
    tau1_any = max((i for i, value in enumerate(tau1) if value), default=-1)
    tau2_any = max((i for i, value in enumerate(tau2) if value), default=-1)
    return matrix, {
        "stable_point_count": sum(sum(row) for row in matrix),
        "tau1_axis_prefix_index": prefix(tau1),
        "tau2_axis_prefix_index": prefix(tau2),
        "tau1_axis_farthest_index": tau1_any,
        "tau2_axis_farthest_index": tau2_any,
        "tau1_axis_holes_before_farthest": 0 if tau1_any < 0 else sum(value == 0 for value in tau1[: tau1_any + 1]),
        "tau2_axis_holes_before_farthest": 0 if tau2_any < 0 else sum(value == 0 for value in tau2[: tau2_any + 1]),
    }


def verify_inputs() -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    sealed, seal = load_sealed_manifest()
    inputs: dict[str, dict[str, Any]] = {}
    expected_paths: set[str] = set()
    for source_id in SOURCE_ORDER:
        inputs[source_id] = {}
        for curve in CURVES:
            relative = relative_mask_path(source_id, curve)
            expected_paths.add(relative)
            require(relative in sealed, f"封存清单缺少掩膜：{relative}")
            path = BOARD20_PACKAGE / Path(relative)
            require(path.is_file(), f"封存掩膜不存在：{path}")
            record = sealed[relative]
            require(path.stat().st_size == int(record["字节数"]), f"掩膜字节数变化：{path}")
            actual_hash = sha256(path)
            require(actual_hash == record["SHA256"].upper(), f"掩膜SHA-256变化：{path}")
            _, stats = load_mask(path)
            inputs[source_id][curve.curve_id] = {
                "path": path.resolve(),
                "sha256": actual_hash,
                "manifest_relative_path": relative,
                **stats,
            }
    mask_manifest_paths = {
        path for path in sealed if "稳定掩膜31x67/" in path
    }
    require(mask_manifest_paths == expected_paths, "板块20封存包的31x67掩膜集合不等于预期30项")
    return inputs, seal


def make_manifest(source_id: str, inputs: Mapping[str, Any], output: Path) -> Path:
    entries = []
    for curve in CURVES:
        entries.append(
            {
                "curve_id": curve.curve_id,
                "input_type": "mask_csv",
                "path": str(inputs[curve.curve_id]["path"]),
                "expected_shape": [31, 67],
                "boundary_mode": "matlab_bwboundaries_8_noholes_visible_open",
            }
        )
    manifest = output / "m.json"
    write_json(
        manifest,
        {
            "schema_version": evaluator.MANIFEST_SCHEMA,
            "candidate_id": f"ARCHIVED_{source_id}",
            "evidence_label": (
                "板块20封存计算掩膜的目标侧只读评价"
                if source_id != "HISTORICAL"
                else "历史lqr_2/lqr_3掩膜的目标侧只读评价"
            ),
            "curves": entries,
        },
    )
    return manifest


def read_set_counts(path: Path) -> dict[str, int]:
    counts = {curve.curve_id: 0 for curve in CURVES}
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            counts[row["curve_id"]] += 1
    return counts


def finite(value: Any) -> float:
    result = float(value)
    require(math.isfinite(result), f"指标不是有限数：{value}")
    return result


def coverage_state(stable_point_count: int) -> str:
    if stable_point_count == 0:
        return "ALL_UNSTABLE"
    if stable_point_count == GRID_POINT_COUNT:
        return "ALL_STABLE"
    return "PARTIAL_STABLE"


def evaluate_sources(inputs: Mapping[str, Any], output: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for source_id in SOURCE_ORDER:
        source_dir = output / source_id.lower()
        source_dir.mkdir(parents=True, exist_ok=False)
        manifest = make_manifest(source_id, inputs[source_id], source_dir)
        evaluation_dir = source_dir / "e"
        summary = evaluator.evaluate_manifest(
            manifest,
            evaluator.DEFAULT_TARGET,
            evaluation_dir,
            evaluator.DEFAULT_MATLAB,
        )
        set_counts = read_set_counts(evaluation_dir / "set_differences.csv")
        metrics = {metric["curve_id"]: metric for metric in summary["curves"]}
        for curve in CURVES:
            metric = metrics[curve.curve_id]
            mask = inputs[source_id][curve.curve_id]
            topology = metric["mask_metadata"]
            target_tau1 = int(metric["target_start_endpoint"][0]) - 1
            target_tau2 = int(metric["target_end_endpoint"][1]) - 1
            tau1 = int(mask["tau1_axis_prefix_index"])
            tau2 = int(mask["tau2_axis_prefix_index"])
            topology_ok = (
                int(topology["component_count_8_connected"]) == 1
                and int(topology["hole_pixel_count"]) == 0
                and int(topology["returned_boundary_count"]) == 1
            )
            info = SOURCE_INFO[source_id]
            stable_point_count = int(mask["stable_point_count"])
            mask_coverage_state = coverage_state(stable_point_count)
            if source_id == "HISTORICAL":
                axis_eligibility = "NOT_APPLICABLE_HISTORICAL_MASK"
            elif mask_coverage_state != "PARTIAL_STABLE":
                axis_eligibility = f"UNQUALIFIED_{mask_coverage_state}"
            elif not topology_ok:
                axis_eligibility = "UNQUALIFIED_REJECTED_TOPOLOGY"
            else:
                axis_eligibility = "ELIGIBLE_PARTIAL_SINGLE_COMPONENT"
            rows.append(
                {
                    "source_id": source_id,
                    "source_class": info["source_class"],
                    "source_display_name": info["display_name"],
                    "integration_axis": info["integration_axis"],
                    "input_semantics_axis": info["input_semantics_axis"],
                    "curve_id": curve.curve_id,
                    "figure_id": curve.figure,
                    "division": curve.division,
                    "method": curve.method,
                    "strict_curve_status": metric["strict_curve_status"],
                    "topology_ranking_gate": "PASS" if topology_ok else "REJECTED_TOPOLOGY",
                    "component_count_8_connected": int(topology["component_count_8_connected"]),
                    "hole_pixel_count": int(topology["hole_pixel_count"]),
                    "returned_boundary_count": int(topology["returned_boundary_count"]),
                    "stable_point_count": stable_point_count,
                    "mask_coverage_state": mask_coverage_state,
                    "source_axis_evidence_eligibility": axis_eligibility,
                    "target_boundary_point_count": int(metric["target_point_count"]),
                    "candidate_boundary_point_count": int(metric["candidate_point_count"]),
                    "boundary_point_count_signed_error": int(metric["candidate_point_count"]) - int(metric["target_point_count"]),
                    "boundary_point_count_abs_error": abs(int(metric["candidate_point_count"]) - int(metric["target_point_count"])),
                    "ordered_exact_original": bool(metric["ordered_exact_original"]),
                    "set_exact": bool(metric["set_exact"]),
                    "set_difference_count": set_counts[curve.curve_id],
                    "point_levenshtein_original": int(metric["point_levenshtein_original"]),
                    "symmetric_hausdorff_steps": finite(metric["symmetric_hausdorff_steps"]),
                    "symmetric_hausdorff_ms": finite(metric["symmetric_hausdorff_ms"]),
                    "start_endpoint_exact": bool(metric["start_endpoint_exact"]),
                    "end_endpoint_exact": bool(metric["end_endpoint_exact"]),
                    "candidate_start_endpoint": json.dumps(metric["candidate_start_endpoint"], separators=(",", ":")),
                    "candidate_end_endpoint": json.dumps(metric["candidate_end_endpoint"], separators=(",", ":")),
                    "target_start_endpoint": json.dumps(metric["target_start_endpoint"], separators=(",", ":")),
                    "target_end_endpoint": json.dumps(metric["target_end_endpoint"], separators=(",", ":")),
                    "endpoint_l1_error_steps_original": int(metric["endpoint_l1_error_steps_original"]),
                    "tau1_axis_prefix_index": tau1,
                    "tau1_axis_prefix_ms": "" if tau1 < 0 else tau1 * MS_PER_SAMPLE,
                    "target_tau1_axis_index": target_tau1,
                    "tau1_axis_abs_error_samples": abs(tau1 - target_tau1),
                    "tau2_axis_prefix_index": tau2,
                    "tau2_axis_prefix_ms": "" if tau2 < 0 else tau2 * MS_PER_SAMPLE,
                    "target_tau2_axis_index": target_tau2,
                    "tau2_axis_abs_error_samples": abs(tau2 - target_tau2),
                    "total_axis_abs_error_samples": abs(tau1 - target_tau1) + abs(tau2 - target_tau2),
                    "tau1_axis_farthest_index": int(mask["tau1_axis_farthest_index"]),
                    "tau2_axis_farthest_index": int(mask["tau2_axis_farthest_index"]),
                    "tau1_axis_holes_before_farthest": int(mask["tau1_axis_holes_before_farthest"]),
                    "tau2_axis_holes_before_farthest": int(mask["tau2_axis_holes_before_farthest"]),
                    "mask_path": str(mask["path"]),
                    "mask_sha256": mask["sha256"],
                    "strict_summary_path": str(evaluation_dir / "strict_evaluation_summary.json"),
                    "strict_summary_sha256": sha256(evaluation_dir / "strict_evaluation_summary.json"),
                }
            )
    return rows


def score(row: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        0 if row["topology_ranking_gate"] == "PASS" else 1,
        0 if row["strict_curve_status"] == "PASS" else 1,
        int(row["boundary_point_count_abs_error"]),
        int(row["set_difference_count"]),
        int(row["point_levenshtein_original"]),
        float(row["symmetric_hausdorff_steps"]),
        int(row["endpoint_l1_error_steps_original"]),
        int(row["total_axis_abs_error_samples"]),
    )


def pair_winner(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    sa, sb = score(a), score(b)
    if sa < sb:
        return str(a["source_id"])
    if sb < sa:
        return str(b["source_id"])
    return "TIE"


def qualified_pair_winner(a: Mapping[str, Any], b: Mapping[str, Any]) -> str:
    qualified = [
        row
        for row in (a, b)
        if row["source_axis_evidence_eligibility"] == "ELIGIBLE_PARTIAL_SINGLE_COMPONENT"
    ]
    if not qualified:
        return "NO_QUALIFIED_SOURCE"
    if len(qualified) == 1:
        return str(qualified[0]["source_id"])
    return pair_winner(qualified[0], qualified[1])


def add_ranks_and_recommendations(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    recommendations: list[dict[str, Any]] = []
    for curve in CURVES:
        group = [row for row in rows if row["curve_id"] == curve.curve_id]
        group.sort(key=lambda row: (*score(row), SOURCE_ORDER.index(str(row["source_id"]))))
        for rank, row in enumerate(group, start=1):
            row["all_source_rank_for_curve"] = rank
        calculated = [row for row in group if row["source_class"] == "CALCULATED_MASK"]
        calculated.sort(key=lambda row: (*score(row), SOURCE_ORDER.index(str(row["source_id"]))))
        for rank, row in enumerate(calculated, start=1):
            row["calculated_source_rank_for_curve"] = rank
        discriminating = [
            row
            for row in calculated
            if row["source_axis_evidence_eligibility"] == "ELIGIBLE_PARTIAL_SINGLE_COMPONENT"
        ]
        discriminating.sort(key=lambda row: (*score(row), SOURCE_ORDER.index(str(row["source_id"]))))
        for rank, row in enumerate(discriminating, start=1):
            row["discriminating_calculated_rank_for_curve"] = rank
        historical = next(row for row in group if row["source_id"] == "HISTORICAL")
        by_source = {row["source_id"]: row for row in calculated}
        integration_force = qualified_pair_winner(by_source["R01"], by_source["R03"])
        integration_acceleration = qualified_pair_winner(by_source["R02"], by_source["R04"])
        input_scalar = "NO_VALID_PAIRED_COMPARISON_ACCELERATION_ALL_STABLE"
        input_matrix = "NO_VALID_PAIRED_COMPARISON_ACCELERATION_ALL_STABLE"

        integration_axes = {
            "R01": "scalar_alpha_0p25",
            "R02": "scalar_alpha_0p25",
            "R03": "route_matrix_al",
            "R04": "route_matrix_al",
        }
        input_axes = {
            "R01": "generalized_force",
            "R03": "generalized_force",
            "R02": "acceleration",
            "R04": "acceleration",
        }
        integration_votes = [
            integration_axes[value]
            for value in (integration_force, integration_acceleration)
            if value in integration_axes
        ]
        suggested_integration = integration_votes[0] if len(set(integration_votes)) == 1 and integration_votes else "MIXED_OR_TIED_NO_SINGLE_AXIS_WINNER"
        suggested_input = "generalized_force_AS_ONLY_DISCRIMINATING_LEVEL"
        best = calculated[0]
        require(discriminating, f"{curve.curve_id}没有可辨识的部分稳定计算掩膜")
        best_discriminating = discriminating[0]
        recommendation = (
            f"形式词典序最近为{best['source_id']}，但来源轴建议只采信可辨识的部分稳定掩膜；"
            f"本曲线对应{best_discriminating['source_id']}。R02/R04在24个计算掩膜中的12个加速度掩膜均为全网格稳定，"
            "不能用来证明加速度输入轴更接近目标。R01-R04已覆盖旧的2x2组合，不应重算。"
        )
        recommendations.append(
            {
                "curve_id": curve.curve_id,
                "figure_id": curve.figure,
                "method": curve.method,
                "best_calculated_source": best["source_id"],
                "best_calculated_integration_axis": best["integration_axis"],
                "best_calculated_input_semantics_axis": best["input_semantics_axis"],
                "best_calculated_score_json": json.dumps(list(score(best)), separators=(",", ":")),
                "best_calculated_mask_coverage_state": best["mask_coverage_state"],
                "best_discriminating_source": best_discriminating["source_id"],
                "best_discriminating_integration_axis": best_discriminating["integration_axis"],
                "best_discriminating_input_semantics_axis": best_discriminating["input_semantics_axis"],
                "best_discriminating_score_json": json.dumps(list(score(best_discriminating)), separators=(",", ":")),
                "integration_generalized_force_pair_winner": integration_force,
                "integration_acceleration_pair_winner": integration_acceleration,
                "suggested_integration_axis": suggested_integration,
                "input_scalar_alpha_pair_winner": input_scalar,
                "input_matrix_al_pair_winner": input_matrix,
                "suggested_input_semantics_axis": suggested_input,
                "historical_strict_curve_status": historical["strict_curve_status"],
                "historical_boundary_role": (
                    "EXACT_TARGET_BOUNDARY_HISTORICAL_VALUE_NOT_CALCULATION_CONTRACT"
                    if historical["strict_curve_status"] == "PASS"
                    else "HISTORICAL_VALUE_DIFFERS_FROM_CURRENT_TARGET_NOT_CALCULATION_CONTRACT"
                ),
                "factual_recommendation": recommendation,
            }
        )
    rows.sort(key=lambda row: (CURVE_INDEX[row["curve_id"]], int(row["all_source_rank_for_curve"])))
    return rows, recommendations


METRIC_FIELDS = (
    "curve_id", "figure_id", "division", "method", "all_source_rank_for_curve",
    "calculated_source_rank_for_curve", "discriminating_calculated_rank_for_curve",
    "source_id", "source_class", "source_display_name",
    "integration_axis", "input_semantics_axis", "strict_curve_status", "topology_ranking_gate",
    "component_count_8_connected", "hole_pixel_count", "returned_boundary_count", "stable_point_count",
    "mask_coverage_state", "source_axis_evidence_eligibility",
    "target_boundary_point_count", "candidate_boundary_point_count", "boundary_point_count_signed_error",
    "boundary_point_count_abs_error", "ordered_exact_original", "set_exact", "set_difference_count",
    "point_levenshtein_original", "symmetric_hausdorff_steps", "symmetric_hausdorff_ms",
    "start_endpoint_exact", "end_endpoint_exact", "candidate_start_endpoint", "candidate_end_endpoint",
    "target_start_endpoint", "target_end_endpoint", "endpoint_l1_error_steps_original",
    "tau1_axis_prefix_index", "tau1_axis_prefix_ms", "target_tau1_axis_index", "tau1_axis_abs_error_samples",
    "tau2_axis_prefix_index", "tau2_axis_prefix_ms", "target_tau2_axis_index", "tau2_axis_abs_error_samples",
    "total_axis_abs_error_samples", "tau1_axis_farthest_index", "tau2_axis_farthest_index",
    "tau1_axis_holes_before_farthest", "tau2_axis_holes_before_farthest", "mask_path", "mask_sha256",
    "strict_summary_path", "strict_summary_sha256",
)

RECOMMENDATION_FIELDS = (
    "curve_id", "figure_id", "method", "best_calculated_source", "best_calculated_integration_axis",
    "best_calculated_input_semantics_axis", "best_calculated_score_json", "best_calculated_mask_coverage_state",
    "best_discriminating_source", "best_discriminating_integration_axis",
    "best_discriminating_input_semantics_axis", "best_discriminating_score_json",
    "integration_generalized_force_pair_winner", "integration_acceleration_pair_winner",
    "suggested_integration_axis", "input_scalar_alpha_pair_winner", "input_matrix_al_pair_winner",
    "suggested_input_semantics_axis", "historical_strict_curve_status", "historical_boundary_role",
    "factual_recommendation",
)


def make_report(rows: Sequence[Mapping[str, Any]], recommendations: Sequence[Mapping[str, Any]], batch_hash: str) -> str:
    lines = [
        "# 板块20封存R01-R04与历史掩膜的图10目标侧只读评价",
        "",
        "## 结论边界",
        "",
        "本报告只评价已封存掩膜，没有运行求解器或重算R01-R04。计算掩膜、历史掩膜和当前论文目标保持三层分离。",
        f"批次SHA-256：`{batch_hash}`。",
        "",
        "## 六条目标曲线的最近已计算来源",
        "",
        "形式排名严格沿用批量评价词典序：拓扑、严格通过、边界点数差、集合差、编辑距、Hausdorff、端点、坐标轴截距。"
        "来源轴建议额外排除全稳定/全不稳定和拓扑拒绝掩膜。",
        "",
        "| 目标曲线 | 形式词典序最近 | 覆盖状态 | 最近可辨识来源 | 建议积分轴 | 输入轴证据 | 历史掩膜与当前目标 |",
        "|---|---:|---|---:|---|---|---|",
    ]
    for item in recommendations:
        lines.append(
            f"| {item['curve_id']} | {item['best_calculated_source']} | {item['best_calculated_mask_coverage_state']} | "
            f"{item['best_discriminating_source']} | {item['suggested_integration_axis']} | "
            f"{item['suggested_input_semantics_axis']} | {item['historical_boundary_role']} |"
        )
    lines.extend(
        [
            "",
            "## 新组合建议的事实边界",
            "",
            "R01-R04已经完整覆盖“scalar alpha / route-matrix al”与“generalized-force / acceleration”的2×2组合。"
            "因此不能把这两个轴的旧组合重新命名为新候选。R02/R04的12个加速度掩膜全部是2077/2077点稳定，"
            "不提供可辨识的目标边界；因此新组合应保留generalized-force输入轴，再按曲线选择R01或R03的积分轴，与板块28尚未共同测试的新轴做有界组合。",
            "",
            "历史掩膜即使与当前目标边界严格一致，也只证明历史绘图值一致；它不提供可执行的计算参数合同。",
        ]
    )
    return "\n".join(lines) + "\n"


def run(output: Path) -> dict[str, Any]:
    output = output.resolve()
    if output.exists():
        require(output.is_dir() and not any(output.iterdir()), f"输出目录必须不存在或为空：{output}")
    output.mkdir(parents=True, exist_ok=True)
    inputs, seal = verify_inputs()
    registry = read_json(CONTRACT_REGISTRY)
    require(registry.get("registry_version") == "known-board20-contracts-v1", "R01-R04合同登记版本错误")
    rows = evaluate_sources(inputs, output)
    rows, recommendations = add_ranks_and_recommendations(rows)
    require(len(rows) == 30, "详细指标不是30行")
    require(len(recommendations) == 6, "建议不是6行")

    hash_payload = {
        "schema_version": SCHEMA,
        "target_sha256": evaluator.EXPECTED_TARGET_SHA256,
        "strict_evaluator_sha256": evaluator.sha256(evaluator.SCRIPT),
        "matlab_helper_sha256": evaluator.sha256(evaluator.SCRIPT.parent / "fig10_extract_mask_boundaries.m"),
        "board20_file_manifest_sha256": sha256(FILE_MANIFEST),
        "contract_registry_sha256": sha256(CONTRACT_REGISTRY),
        "masks": [
            {"source_id": row["source_id"], "curve_id": row["curve_id"], "sha256": row["mask_sha256"]}
            for row in sorted(rows, key=lambda r: (str(r["source_id"]), CURVE_INDEX[str(r["curve_id"])]))
        ],
        "metrics": [
            {
                key: row[key]
                for key in (
                    "source_id", "source_class", "curve_id", "strict_curve_status", "topology_ranking_gate",
                    "stable_point_count", "candidate_boundary_point_count", "boundary_point_count_abs_error",
                    "set_difference_count", "point_levenshtein_original", "symmetric_hausdorff_steps",
                    "endpoint_l1_error_steps_original", "total_axis_abs_error_samples",
                )
            }
            for row in rows
        ],
        "recommendations": recommendations,
        "ranking_contract": list(RANKING_CONTRACT),
    }
    batch_hash = canonical_hash(hash_payload)
    write_csv(output / "source_curve_metrics.csv", METRIC_FIELDS, rows)
    write_csv(output / "curve_axis_recommendations.csv", RECOMMENDATION_FIELDS, recommendations)
    write_text(output / "只读评价报告.md", make_report(rows, recommendations, batch_hash))
    summary = {
        "schema_version": SCHEMA,
        "status": "PASS",
        "scope": "TARGET_SIDE_READ_ONLY_NO_SOLVER_NO_R01_R04_RECOMPUTATION",
        "source_layers": {
            "calculated_masks": "R01-R04, 24 frozen 31x67 masks",
            "historical_masks": "lqr_2/lqr_3, 6 frozen 31x67 masks",
            "target": "board28 frozen plotted_data.mat, 6 boundaries, 386 points",
        },
        "counts": {"calculated_masks": 24, "historical_masks": 6, "metric_rows": 30, "recommendation_rows": 6},
        "ranking_contract": list(RANKING_CONTRACT),
        "calculated_coverage_counts": {
            state: sum(
                1
                for row in rows
                if row["source_class"] == "CALCULATED_MASK" and row["mask_coverage_state"] == state
            )
            for state in ("ALL_UNSTABLE", "PARTIAL_STABLE", "ALL_STABLE")
        },
        "board20_package_seal": seal,
        "board20_file_manifest_sha256": sha256(FILE_MANIFEST),
        "contract_registry_sha256": sha256(CONTRACT_REGISTRY),
        "strict_evaluator_sha256": evaluator.sha256(evaluator.SCRIPT),
        "matlab_helper_sha256": evaluator.sha256(evaluator.SCRIPT.parent / "fig10_extract_mask_boundaries.m"),
        "target_sha256": evaluator.EXPECTED_TARGET_SHA256,
        "batch_sha256": batch_hash,
        "strict_pass_rows": [
            {"source_id": row["source_id"], "curve_id": row["curve_id"]}
            for row in rows
            if row["strict_curve_status"] == "PASS"
        ],
        "recommendations": recommendations,
        "claim_boundary": "历史掩膜不是计算合同；本评价不证明已恢复作者原始生成程序。",
    }
    write_json(output / "audit_summary.json", summary)
    artifact_manifest = output / "artifact_hashes.csv"
    artifact_rows = []
    for path in sorted(output.rglob("*")):
        if path.is_file() and path != artifact_manifest:
            artifact_rows.append(
                {"path": path.relative_to(output).as_posix(), "bytes": path.stat().st_size, "sha256": sha256(path)}
            )
    write_csv(artifact_manifest, ("path", "bytes", "sha256"), artifact_rows)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        summary = run(args.output_dir)
        print(
            json.dumps(
                {
                    "status": summary["status"],
                    "counts": summary["counts"],
                    "strict_pass_rows": summary["strict_pass_rows"],
                    "batch_sha256": summary["batch_sha256"],
                    "output_dir": str(args.output_dir.resolve()),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        error = {"schema_version": SCHEMA, "status": "ERROR", "error_type": type(exc).__name__, "error_message": str(exc)}
        try:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            write_json(args.output_dir / "audit_error.json", error)
        except Exception:
            pass
        print(json.dumps(error, ensure_ascii=False, indent=2), file=os.sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

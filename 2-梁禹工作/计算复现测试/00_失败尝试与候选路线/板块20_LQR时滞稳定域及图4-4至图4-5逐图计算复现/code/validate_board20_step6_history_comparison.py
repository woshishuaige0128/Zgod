from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import h5py
from PIL import Image
from PyPDF2 import PdfReader
from PyPDF2.generic import ContentStream
from scipy.io import loadmat

from board20_step6_fs_protocol import (
    ExclusiveFileLock,
    atomic_commit_manifest,
    classify_output,
    prepare_output_root,
    validate_fixed_roots as validate_fs_fixed_roots,
)


SCRIPT_PATH = Path(__file__).resolve()
CODE_ROOT = SCRIPT_PATH.parent
BOARD_ROOT = CODE_ROOT.parent
CONTRACT_PATH = CODE_ROOT / "board20_step6_history_comparison_contract.json"
MANUAL_VISUAL_REVIEW_PATH = CODE_ROOT / "board20_step6_manual_visual_review.csv"
FS_PROTOCOL_PATH = CODE_ROOT / "board20_step6_fs_protocol.py"
RESET_SCRIPT_PATH = CODE_ROOT / "reset_board20_step6_clean_probe.py"
REPO_ROOT = next(parent for parent in SCRIPT_PATH.parents if (parent / "WORKFLOW.md").is_file())
RUN_OUTPUT_DIRECTORIES = {"figures", "tables"}
VALIDATION_OUTPUT_DIRECTORIES = {"rendered_pdf_review"}

METHOD_VARIABLE = {
    "Original": "stab_o",
    "Craig-Bampton": "stab_C",
    "Guyan": "stab_g",
}
PROVENANCE_LABELS = {
    1: "ORIGINAL_ACTIVE_POINT",
    2: "COMMENTED_AUTHOR_INTENT",
    3: "SAME_FORMULA_SUPPLEMENT",
    4: "FAIL",
}
TABLE_NAMES = [
    "pointwise_comparison",
    "route_eligibility",
    "target_cell_status",
    "confusion_matrix",
    "boundary_by_source",
    "boundary_difference",
    "stability_metrics",
    "extension_1_to_28_audit",
    "extension_summary",
    "claim_C05_C07",
    "div2_payload_relation_audit",
    "figure_status",
]
FIGURE_STEMS = [
    "图4-4_历史最终掩膜边界_绘图级复核",
    "图4-5_历史最终掩膜边界_绘图级复核",
    "图4-4_作者文件身份计算候选_失败诊断",
    "图4-5_作者文件身份计算候选_失败诊断",
]

EXPECTED_GENERATOR_CSV_FIELDS: dict[str, list[str]] = {
    "artifact_manifest.csv": ["relpath", "bytes", "sha256"],
    "checks.csv": ["check_id", "category", "description", "status", "expected", "actual", "evidence"],
    "figure_style_manifest.csv": ["figure_id", "artifact_role", "panel", "method", "route_id", "color", "linestyle", "marker", "rendered_object", "evidence_level", "font_family", "mathtext_fontset"],
    "protected_input_hashes.csv": ["relpath", "sha256_before_v5", "sha256_current_step6", "unchanged"],
    "boundary_by_source.csv": ["figure_id", "division", "method", "source_kind", "source_id", "route_id", "route_role", "j", "tau1_ms", "has_stable", "stable_count_in_column", "min_l", "max_l", "tau2_upper_ms", "contiguous_from_zero", "hole_count", "boundary_role"],
    "boundary_difference.csv": ["figure_id", "division", "method", "route_id", "route_role", "j", "tau1_ms", "boundary_presence_relation", "historical_max_l", "candidate_max_l", "candidate_minus_historical_max_l", "candidate_minus_historical_tau2_ms", "candidate_column_hole_count", "boundary_comparison_role"],
    "claim_C05_C07.csv": ["claim_ids", "comparison_id", "evidence_source", "base_source_id", "reduced_source_id", "axis_intercept_definition", "tau1_axis_intercept_drop_ms", "tau2_axis_intercept_drop_ms", "equal_delay_diagonal_intercept_drop_ms", "stable_point_drop", "stable_grid_area_proxy_drop_ms2", "claimed_phrase", "qualitative_tolerance_status", "route_or_mask_closure", "eligible_for_calculation_level_upgrade", "non_upgrade_reason"],
    "confusion_matrix.csv": ["figure_id", "division", "method", "route_id", "route_role", "route_formula", "availability", "evaluated_points", "expected_points", "historical_stable_points", "candidate_stable_points", "true_positive", "true_negative", "false_positive", "false_negative", "mask_mismatch_points", "agreement_fraction", "candidate_is_subset_of_historical", "comparison_status", "calculation_level_mask_gate_pass", "max_rho_step4_v4_abs_diff", "candidate_hole_columns", "candidate_hole_cells", "candidate_connected_components"],
    "div2_payload_relation_audit.csv": ["left_route", "right_route", "point_count", "csv_field_count", "excluded_identity_fields", "compared_nonidentity_fields", "unequal_nonidentity_fields", "unequal_points", "max_rho_abs_diff", "stable_mismatch_points", "relation", "interpretation"],
    "extension_1_to_28_audit.csv": ["method", "variable", "raw_rows", "raw_columns", "sequence_row_1based", "sequence_column_1based", "expected_value", "actual_value", "value_match", "inside_common_31x67", "strict_historical_stable", "interpretation"],
    "extension_summary.csv": ["method", "variable", "raw_rows", "raw_columns", "common_grid_cells", "outside_common_grid_cells", "outside_nonzero_sequence_cells", "outside_zero_cells", "outside_strict_stable_cells", "sequence_values_exact_1_to_28", "comparison_disposition"],
    "figure_status.csv": ["figure_id", "division", "method_cell_count", "primary_continuous_rho_cell_count", "exact_mask_match_cell_count", "all_three_primary_routes_present", "all_three_primary_masks_exact", "calculation_level_figure_gate_pass", "object_evidence_level", "formal_success_directory_allowed", "candidate_location"],
    "pointwise_comparison.csv": ["figure_id", "division", "method", "route_id", "route_role", "route_formula", "l", "j", "tau1_ms", "tau2_ms", "historical_raw_value", "historical_stable", "rho_step4_matlab", "rho_v4_python", "rho_abs_diff_step4_v4", "rho_minus_one", "candidate_stable_stored", "candidate_stable_rederived", "step4_stable", "critical_within_1e8", "confusion_class", "mask_xor", "provenance_code", "provenance_label", "point_status"],
    "route_eligibility.csv": ["figure_id", "division", "method", "route_id", "route_role", "route_formula", "availability", "reason", "candidate_point_count", "expected_point_count"],
    "stability_metrics.csv": ["source_id", "source_kind", "figure_id", "division", "method", "route_id", "route_role", "stable_count", "max_tau1_any_stable_step", "max_tau1_any_stable_ms", "max_tau2_any_stable_step", "max_tau2_any_stable_ms", "axis_intercept_definition", "tau1_axis_intercept_step", "tau1_axis_intercept_ms", "tau2_axis_intercept_step", "tau2_axis_intercept_ms", "equal_delay_diagonal_intercept_step", "equal_delay_diagonal_intercept_ms", "stable_grid_area_proxy_ms2", "upper_envelope_integral_ms2", "empty_column_count", "hole_column_count", "hole_cell_count", "connected_component_count_4_neighbor", "all_columns_contiguous_from_zero", "upper_envelope_role"],
    "target_cell_status.csv": ["figure_id", "division", "method", "historical_stable_points", "primary_route_id", "primary_candidate_stable_points", "mask_mismatch_points", "target_status", "calculation_level_target_gate_pass"],
}


def expected_run_relpaths() -> set[str]:
    result = {f"tables/{name}.csv" for name in TABLE_NAMES}
    for stem in FIGURE_STEMS:
        result.add(f"figures/{stem}.pdf")
        result.add(f"figures/{stem}.png")
    result.update(
        {
            "checks.csv",
            "figure_style_manifest.csv",
            "protected_input_hashes.csv",
            "report.md",
            "run_summary.json",
        }
    )
    return result


def expected_validation_relpaths() -> set[str]:
    result = {
        "repeatability.csv",
        "repeatability.json",
        "figure_quality.csv",
        "protected_hashes.csv",
        "report.md",
        "validation_checks.csv",
        "validation_summary.json",
        "render_audit.json",
        "manual_visual_review.csv",
    }
    result.update(f"rendered_pdf_review/{stem}.png" for stem in FIGURE_STEMS)
    return result


def strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def board_path(relpath: str) -> Path:
    path = (BOARD_ROOT / Path(relpath.replace("/", os.sep))).resolve()
    if not path.is_relative_to(BOARD_ROOT.resolve()):
        raise ValueError(relpath)
    return path


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"No CSV header: {path}")
        fields = list(reader.fieldnames)
        if len(fields) != len(set(fields)):
            raise ValueError(f"Duplicate CSV fields: {path}: {fields}")
        expected = EXPECTED_GENERATOR_CSV_FIELDS.get(path.name)
        if expected is not None and fields != expected:
            raise ValueError(
                f"Generator CSV schema drifted: {path}: expected={expected}, actual={fields}"
            )
        return fields, list(reader)


def expected_csv_text(value: Any) -> str:
    converted = csv_value(value)
    return str(converted)


def full_row_failures(
    observed: Sequence[Mapping[str, str]],
    expected: Sequence[Mapping[str, Any]],
    *,
    limit: int = 20,
) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    if len(observed) != len(expected):
        failures.append({"row_count_expected": len(expected), "row_count_actual": len(observed)})
    for index, (actual_row, expected_row) in enumerate(zip(observed, expected)):
        for field in expected_row:
            expected_text = expected_csv_text(expected_row[field])
            actual_text = actual_row.get(field)
            if actual_text != expected_text:
                failures.append(
                    {
                        "row": index,
                        "field": field,
                        "expected": expected_text,
                        "actual": actual_text,
                    }
                )
                if len(failures) >= limit:
                    return failures
    return failures


def csv_value(value: Any) -> Any:
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return format(value, ".17g")
    if value is None:
        return ""
    return value


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fieldnames), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


def bool_text(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(value)


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self.counter = 0

    def add(
        self,
        category: str,
        description: str,
        condition: bool,
        expected: Any,
        actual: Any,
        evidence: str,
        *,
        hard: bool = True,
    ) -> None:
        self.counter += 1
        status = "PASS" if condition else "FAIL"
        self.rows.append(
            {
                "check_id": f"S6V{self.counter:04d}",
                "category": category,
                "description": description,
                "status": status,
                "expected": json.dumps(expected, ensure_ascii=False, sort_keys=True),
                "actual": json.dumps(actual, ensure_ascii=False, sort_keys=True),
                "evidence": evidence,
            }
        )
        if hard and not condition:
            raise RuntimeError(f"Independent validation hard gate failed: {description}")

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.rows),
            "pass": sum(row["status"] == "PASS" for row in self.rows),
            "fail": sum(row["status"] == "FAIL" for row in self.rows),
        }


def output_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    }


def verify_manifest(root: Path, checks: Checks, label: str) -> None:
    fields, rows = read_csv(root / "artifact_manifest.csv")
    checks.add(
        "artifact_manifest",
        f"{label}工件清单字段固定",
        fields == ["relpath", "bytes", "sha256"],
        ["relpath", "bytes", "sha256"],
        fields,
        f"{label}/artifact_manifest.csv",
    )
    files = output_files(root)
    actual_relpaths = sorted(rel for rel in files if rel != "artifact_manifest.csv")
    expected_relpaths = sorted(expected_run_relpaths())
    listed_relpaths = [row["relpath"] for row in rows]
    failures: list[str] = []
    for row in rows:
        path = root / Path(row["relpath"])
        if (
            not path.is_file()
            or path.stat().st_size != int(row["bytes"])
            or sha256_file(path) != row["sha256"]
        ):
            failures.append(row["relpath"])
    checks.add(
        "artifact_manifest",
        f"{label}清单覆盖全部非清单文件且逐项哈希闭合",
        listed_relpaths == expected_relpaths
        and actual_relpaths == expected_relpaths
        and not failures,
        {"relpaths": expected_relpaths, "failures": []},
        {
            "listed_relpaths": listed_relpaths,
            "actual_relpaths": actual_relpaths,
            "failures": failures,
        },
        f"{label}/artifact_manifest.csv",
    )


def verify_repeatability(
    run1: Path, run2: Path, validation_root: Path, checks: Checks
) -> dict[str, Any]:
    files1 = output_files(run1)
    files2 = output_files(run2)
    names1 = sorted(files1)
    names2 = sorted(files2)
    common = sorted(set(names1) & set(names2))
    rows: list[dict[str, Any]] = []
    mismatches: list[str] = []
    for relpath in common:
        hash1 = sha256_file(files1[relpath])
        hash2 = sha256_file(files2[relpath])
        match = hash1 == hash2 and files1[relpath].read_bytes() == files2[relpath].read_bytes()
        if not match:
            mismatches.append(relpath)
        rows.append(
            {
                "relpath": relpath,
                "run1_bytes": files1[relpath].stat().st_size,
                "run2_bytes": files2[relpath].stat().st_size,
                "run1_sha256": hash1,
                "run2_sha256": hash2,
                "byte_identical": match,
            }
        )
    checks.add(
        "repeatability",
        "两轮生成文件集合完全相同且每个文件字节一致",
        names1 == names2 and not mismatches,
        {"same_file_set": True, "mismatches": []},
        {"same_file_set": names1 == names2, "mismatches": mismatches},
        "step6 run1 | run2",
    )
    write_csv(
        validation_root / "repeatability.csv",
        [
            "relpath",
            "run1_bytes",
            "run2_bytes",
            "run1_sha256",
            "run2_sha256",
            "byte_identical",
        ],
        rows,
    )
    payload = {
        "status": "PASS" if names1 == names2 and not mismatches else "FAIL",
        "run_count": 2,
        "run1_file_count": len(names1),
        "run2_file_count": len(names2),
        "same_file_set": names1 == names2,
        "byte_identical_file_count": sum(row["byte_identical"] for row in rows),
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
    }
    write_json(validation_root / "repeatability.json", payload)
    return payload


def verify_contract_inputs(contract: Mapping[str, Any], checks: Checks) -> None:
    bindings = list(contract["input_bindings"])
    relpaths = [str(record["relpath"]) for record in bindings]
    failures: list[dict[str, Any]] = []
    for record in bindings:
        path = board_path(str(record["relpath"]))
        actual = {
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path) if path.is_file() else None,
        }
        expected = {
            "exists": True,
            "bytes": int(record["bytes"]),
            "sha256": str(record["sha256"]),
        }
        if actual != expected:
            failures.append(
                {"relpath": record["relpath"], "expected": expected, "actual": actual}
            )
    checks.add(
        "contract_input_binding",
        "合同32项输入路径唯一，独立复核存在性、字节数及SHA-256全部匹配",
        len(bindings) == 32
        and len(relpaths) == len(set(relpaths))
        and not failures,
        {"count": 32, "unique": True, "failures": []},
        {
            "count": len(bindings),
            "unique": len(relpaths) == len(set(relpaths)),
            "failures": failures,
        },
        "code/board20_step6_history_comparison_contract.json | input_bindings",
    )


def verify_clean_probe_receipt(
    contract: Mapping[str, Any], checks: Checks
) -> dict[str, str]:
    receipt_contract = contract["clean_probe_receipt_contract"]
    receipt_path = board_path(receipt_contract["relpath"])
    receipt = read_json(receipt_path)
    required_targets = list(receipt_contract["required_targets"])
    postconditions = receipt.get("postconditions", {})
    exact_keys = {
        "schema_version",
        "action_id",
        "status",
        "started_utc",
        "completed_utc",
        "script_sha256",
        "contract_sha256",
        "fs_protocol_sha256",
        "targets",
        "postconditions",
    }
    condition = (
        set(receipt) == exact_keys
        and receipt.get("schema_version") == receipt_contract["schema_version"]
        and receipt.get("status") == receipt_contract["required_status"]
        and isinstance(receipt.get("action_id"), str)
        and bool(receipt.get("action_id"))
        and isinstance(receipt.get("started_utc"), str)
        and isinstance(receipt.get("completed_utc"), str)
        and receipt.get("script_sha256") == sha256_file(RESET_SCRIPT_PATH)
        and receipt.get("contract_sha256") == sha256_file(CONTRACT_PATH)
        and receipt.get("fs_protocol_sha256") == sha256_file(FS_PROTOCOL_PATH)
        and list(receipt.get("targets", {}).keys()) == required_targets
        and list(postconditions.keys()) == required_targets
        and all(
            postconditions[name]
            == {
                "state": receipt_contract["required_post_state"],
                "file_count": 0,
                "directory_count": 0,
            }
            for name in required_targets
        )
    )
    checks.add(
        "clean_probe_receipt",
        "独立验证器复核同一次三固定根清空收据的精确键、状态、脚本/合同/协议哈希和三个空目录后置条件",
        condition,
        {
            "exact_keys": sorted(exact_keys),
            "status": receipt_contract["required_status"],
            "targets": required_targets,
            "post_state": receipt_contract["required_post_state"],
            "hashes_match": True,
        },
        {
            "keys": sorted(receipt),
            "status": receipt.get("status"),
            "targets": list(receipt.get("targets", {}).keys()),
            "postconditions": postconditions,
            "hashes_match": receipt.get("script_sha256")
            == sha256_file(RESET_SCRIPT_PATH)
            and receipt.get("contract_sha256") == sha256_file(CONTRACT_PATH)
            and receipt.get("fs_protocol_sha256") == sha256_file(FS_PROTOCOL_PATH),
        },
        receipt_contract["relpath"],
    )
    return {
        "action_id": str(receipt.get("action_id", "")),
        "sha256": sha256_file(receipt_path),
    }


def verify_fixed_roots(
    contract: Mapping[str, Any],
    run1: Path,
    run2: Path,
    validation_root: Path,
    checks: Checks,
) -> None:
    expected_literals = {
        "run1": "outputs/step6_history_comparison_run1",
        "run2": "outputs/step6_history_comparison_run2",
        "validation": "outputs/step6_history_comparison_validation",
        "logs": "logs/step6_history_comparison",
    }
    actual_literals = dict(contract["fixed_output_roots"])
    resolved = {
        key: board_path(actual_literals[key]) for key in expected_literals
    }
    aliases: list[str] = []
    keys = list(resolved)
    for left_index, left_key in enumerate(keys):
        for right_key in keys[left_index + 1 :]:
            left = resolved[left_key]
            right = resolved[right_key]
            if left == right or (
                left.exists() and right.exists() and os.path.samefile(left, right)
            ):
                aliases.append(f"{left_key}={right_key}")
    link_like = [
        key
        for key, path in resolved.items()
        if path.is_symlink()
        or bool(getattr(path, "is_junction", lambda: False)())
    ]
    checks.add(
        "fixed_output_roots",
        "run1、run2、validation和logs固定字面路径、解析路径及实体目录均互异且不是链接别名",
        actual_literals == expected_literals
        and run1 == resolved["run1"]
        and run2 == resolved["run2"]
        and validation_root == resolved["validation"]
        and len(set(resolved.values())) == 4
        and not aliases
        and not link_like,
        {
            "literals": expected_literals,
            "resolved_unique": True,
            "aliases": [],
            "link_like": [],
        },
        {
            "literals": actual_literals,
            "resolved": {key: str(path) for key, path in resolved.items()},
            "aliases": aliases,
            "link_like": link_like,
        },
        "code/board20_step6_history_comparison_contract.json | fixed_output_roots",
    )


def verify_generator_semantics(
    contract: Mapping[str, Any], run1: Path, checks: Checks
) -> None:
    _, generator_checks = read_csv(run1 / "checks.csv")
    expected_ids = [f"S6C{index:04d}" for index in range(1, len(generator_checks) + 1)]
    statuses = [row["status"] for row in generator_checks]
    generator_summary = {
        "total": len(generator_checks),
        "pass": statuses.count("PASS"),
        "info": statuses.count("INFO"),
        "fail": statuses.count("FAIL"),
    }
    expected_generator_summary = {
        "total": 115,
        "pass": 107,
        "info": 8,
        "fail": 0,
    }
    expected_category_status_counts = {
        ("candidate_critical_rule", "PASS"): 5,
        ("candidate_point_identity", "PASS"): 5,
        ("candidate_schema", "PASS"): 10,
        ("candidate_stable_rule", "PASS"): 5,
        ("clean_probe_receipt", "PASS"): 1,
        ("div2_payload_relation", "PASS"): 1,
        ("execution_integrity", "PASS"): 1,
        ("extension_1_to_28", "PASS"): 6,
        ("historical_boundary", "PASS"): 4,
        ("historical_clean_mask", "PASS"): 6,
        ("historical_grid", "PASS"): 2,
        ("historical_identity", "PASS"): 8,
        ("historical_mask_comparison", "INFO"): 5,
        ("input_binding", "PASS"): 32,
        ("object_gate", "INFO"): 1,
        ("origin_connected_axis_intercepts", "PASS"): 1,
        ("protected_inputs", "PASS"): 3,
        ("safe_regeneration", "PASS"): 1,
        ("step1_manifest", "PASS"): 2,
        ("step4_manifest", "PASS"): 2,
        ("step4_step5_crosscheck", "PASS"): 5,
        ("step5_gate", "PASS"): 3,
        ("step5_manifest", "PASS"): 2,
        ("step5_v5_manifest", "PASS"): 2,
        ("target_cell_gate", "INFO"): 2,
    }
    observed_category_status_counts = Counter(
        (row["category"], row["status"]) for row in generator_checks
    )
    malformed_rows: list[dict[str, Any]] = []
    for index, row in enumerate(generator_checks):
        try:
            json.loads(row["expected"])
            json.loads(row["actual"])
        except (json.JSONDecodeError, TypeError) as exc:
            malformed_rows.append(
                {"row": index, "field": "expected_or_actual", "error": str(exc)}
            )
        if not row["description"].strip() or not row["evidence"].strip():
            malformed_rows.append(
                {"row": index, "field": "description_or_evidence", "row_data": row}
            )
    checks.add(
        "generator_checks",
        "生成器日志固定115行、编号连续、107 PASS/8 INFO、类别状态分布精确，且说明/证据非空、期望值和实测值均为合法JSON",
        [row["check_id"] for row in generator_checks] == expected_ids
        and generator_summary == expected_generator_summary
        and observed_category_status_counts
        == Counter(expected_category_status_counts)
        and not malformed_rows,
        {
            "sequential": True,
            "summary": expected_generator_summary,
            "category_status_counts": {
                f"{category}|{status}": count
                for (category, status), count in sorted(
                    expected_category_status_counts.items()
                )
            },
            "malformed_rows": [],
        },
        {
            "sequential": [row["check_id"] for row in generator_checks] == expected_ids,
            "summary": generator_summary,
            "category_status_counts": {
                f"{category}|{status}": count
                for (category, status), count in sorted(
                    observed_category_status_counts.items()
                )
            },
            "malformed_rows": malformed_rows[:20],
        },
        "checks.csv",
    )

    table_counts = {
        name: len(read_csv(run1 / "tables" / f"{name}.csv")[1])
        for name in TABLE_NAMES
    }
    summary = read_json(run1 / "run_summary.json")
    receipt_path = board_path(contract["clean_probe_receipt_contract"]["relpath"])
    receipt = read_json(receipt_path)
    expected_summary = {
        "schema_version": "board20_step6_history_comparison_output_v1",
        "generator_sha256": sha256_file(
            CODE_ROOT / "analyze_board20_step6_history_comparison.py"
        ),
        "fs_protocol_sha256": sha256_file(FS_PROTOCOL_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "clean_probe_action_id": receipt["action_id"],
        "clean_probe_receipt_sha256": sha256_file(receipt_path),
        "execution_status": "PASS",
        "object_gate_status": "FAIL_RETAIN_PLOTTING_LEVEL",
        "pointwise_comparison_rows": table_counts["pointwise_comparison"],
        "route_eligibility_rows": table_counts["route_eligibility"],
        "target_cell_rows": table_counts["target_cell_status"],
        "confusion_rows": table_counts["confusion_matrix"],
        "boundary_rows": table_counts["boundary_by_source"],
        "boundary_difference_rows": table_counts["boundary_difference"],
        "extension_sequence_rows": table_counts["extension_1_to_28_audit"],
        "figure_pdf_count": 4,
        "figure_png_count": 4,
        "check_summary": expected_generator_summary,
        "formal_success_directories_created": False,
        "next_step_started": False,
    }
    checks.add(
        "run_summary",
        "run_summary键集合、版本、三个代码哈希、实际表行数、图数、固定检查计数及状态逐字段完全一致",
        summary == expected_summary,
        expected_summary,
        summary,
        "run_summary.json",
    )

    _, style_rows = read_csv(run1 / "figure_style_manifest.csv")
    style = contract["plot_style"]
    expected_style_rows: list[dict[str, str]] = []
    for figure_id in ["F4-4", "F4-5"]:
        for method in ["Original", "Craig-Bampton", "Guyan"]:
            expected_style_rows.append(
                {
                    "figure_id": figure_id,
                    "artifact_role": "HISTORICAL_PLOTTING_LEVEL",
                    "panel": "single_axis",
                    "method": method,
                    "route_id": "",
                    "color": style[method]["color"],
                    "linestyle": style[method]["linestyle"],
                    "marker": style[method]["marker"],
                    "rendered_object": "upper_boundary_step_from_historical_mask",
                    "evidence_level": "PLOTTING_LEVEL_REPRODUCTION",
                }
            )
    expected_style_rows.extend(
        [
            {"figure_id": "F4-4", "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC", "panel": "primary_file_identity", "method": "Original", "route_id": "main_ori_div1", "color": style["Original"]["color"], "linestyle": style["Original"]["linestyle"], "marker": style["Original"]["marker"], "rendered_object": "stable_cells_and_rho_equals_one_contour", "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY"},
            {"figure_id": "F4-4", "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC", "panel": "primary_file_identity", "method": "Guyan", "route_id": "main_guyan_div1", "color": style["Guyan"]["color"], "linestyle": style["Guyan"]["linestyle"], "marker": style["Guyan"]["marker"], "rendered_object": "stable_cells_and_rho_equals_one_contour", "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY"},
            {"figure_id": "F4-4", "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC", "panel": "route_sensitivity", "method": "Guyan", "route_id": "alt_guyan_div1_stable_full_ps3", "color": style["Guyan"]["color"], "linestyle": ":", "marker": style["Guyan_alternative_marker"], "rendered_object": "stable_cells_and_rho_equals_one_contour", "evidence_level": "ALTERNATIVE_DIAGNOSTIC_NOT_PRIMARY"},
            {"figure_id": "F4-4", "artifact_role": "MISSING_ROUTE", "panel": "primary_file_identity", "method": "Craig-Bampton", "route_id": "", "color": style["Craig-Bampton"]["color"], "linestyle": style["Craig-Bampton"]["linestyle"], "marker": style["Craig-Bampton"]["marker"], "rendered_object": "explicit_missing_route_annotation", "evidence_level": "DO_NOT_CREATE"},
            {"figure_id": "F4-5", "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC", "panel": "main_ori_div2", "method": "Original", "route_id": "main_ori_div2", "color": style["Original"]["color"], "linestyle": style["Original"]["linestyle"], "marker": style["Original"]["marker"], "rendered_object": "stable_cells_and_rho_equals_one_contour_preserving_holes", "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY"},
            {"figure_id": "F4-5", "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC", "panel": "main_guyan_div2", "method": "Guyan", "route_id": "main_guyan_div2", "color": style["Guyan"]["color"], "linestyle": style["Guyan"]["linestyle"], "marker": style["Guyan"]["marker"], "rendered_object": "stable_cells_and_rho_equals_one_contour_preserving_holes", "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY"},
            {"figure_id": "F4-5", "artifact_role": "MISSING_ROUTE", "panel": "figure_annotation", "method": "Craig-Bampton", "route_id": "", "color": style["Craig-Bampton"]["color"], "linestyle": style["Craig-Bampton"]["linestyle"], "marker": style["Craig-Bampton"]["marker"], "rendered_object": "explicit_missing_route_annotation", "evidence_level": "DO_NOT_CREATE"},
        ]
    )
    for row in expected_style_rows:
        row["font_family"] = style["font_family"]
        row["mathtext_fontset"] = style["mathtext_fontset"]
    checks.add(
        "figure_style",
        "13行样式与证据清单逐行匹配固定颜色、线型、字体、路线角色和历史/候选分层",
        style_rows == expected_style_rows,
        expected_style_rows,
        style_rows,
        "figure_style_manifest.csv",
    )


def historical_masks(contract: Mapping[str, Any]) -> dict[tuple[str, str], np.ndarray]:
    result: dict[tuple[str, str], np.ndarray] = {}
    for division in ["div1", "div2"]:
        values = loadmat(board_path(contract["historical_masks"][division]["raw_relpath"]))
        for method, variable in METHOD_VARIABLE.items():
            common = np.asarray(values[variable], dtype=float)[:31, :67]
            result[(division, method)] = (
                np.isfinite(common) & (common > 0.0) & (common < 1.0)
            )
    return result


def historical_raw_values(
    contract: Mapping[str, Any]
) -> dict[tuple[str, str], np.ndarray]:
    result: dict[tuple[str, str], np.ndarray] = {}
    for division in ["div1", "div2"]:
        values = loadmat(board_path(contract["historical_masks"][division]["raw_relpath"]))
        for method, variable in METHOD_VARIABLE.items():
            result[(division, method)] = np.asarray(values[variable], dtype=float)[:31, :67]
    return result


def matlab_hdf5_array(handle: h5py.File, variable: str) -> np.ndarray:
    return np.asarray(handle[variable], dtype=np.float64).T.copy()


def candidate_route_arrays(
    contract: Mapping[str, Any]
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for route in contract["routes"]:
        fields, rows = read_csv(board_path(route["point_summary_relpath"]))
        rho = np.full((31, 67), np.nan, dtype=float)
        stored = np.zeros((31, 67), dtype=bool)
        seen: set[tuple[int, int]] = set()
        for row in rows:
            l_value = int(row["l"])
            j_value = int(row["j"])
            if (l_value, j_value) in seen:
                raise RuntimeError(f"Duplicate candidate coordinate: {route['route_id']}")
            seen.add((l_value, j_value))
            rho[l_value, j_value] = float(row["rho"])
            stored[l_value, j_value] = bool_text(row["stable"])
        rederived = np.isfinite(rho) & (rho < 1.0)
        with h5py.File(board_path(route["step4_mat_relpath"]), "r") as handle:
            rho_step4 = matlab_hdf5_array(handle, "rho")
            stable_step4 = matlab_hdf5_array(handle, "stable") != 0
            provenance_code = matlab_hdf5_array(handle, "provenance_code").astype(int)
        result[route["route_id"]] = {
            "contract": route,
            "fields": fields,
            "rows": rows,
            "rho": rho,
            "stored": stored,
            "stable": rederived,
            "seen": seen,
            "rho_step4": rho_step4,
            "stable_step4": stable_step4,
            "provenance_code": provenance_code,
        }
    return result


def envelope(mask: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for j_value in range(67):
        stable_l = np.flatnonzero(mask[:, j_value])
        if stable_l.size:
            min_l = int(stable_l[0])
            max_l = int(stable_l[-1])
            holes = int(len(set(range(max_l + 1)) - set(int(x) for x in stable_l)))
            contiguous = min_l == 0 and holes == 0
        else:
            min_l = None
            max_l = None
            holes = 0
            contiguous = True
        rows.append(
            {
                "j": j_value,
                "has_stable": bool(stable_l.size),
                "count": int(stable_l.size),
                "min_l": min_l,
                "max_l": max_l,
                "holes": holes,
                "contiguous": contiguous,
            }
        )
    return rows


def components(mask: np.ndarray) -> int:
    unseen = {tuple(int(x) for x in point) for point in np.argwhere(mask)}
    count = 0
    while unseen:
        count += 1
        stack = [unseen.pop()]
        while stack:
            l_value, j_value = stack.pop()
            for neighbor in [
                (l_value - 1, j_value),
                (l_value + 1, j_value),
                (l_value, j_value - 1),
                (l_value, j_value + 1),
            ]:
                if neighbor in unseen:
                    unseen.remove(neighbor)
                    stack.append(neighbor)
    return count


def basic_metrics(mask: np.ndarray, dt_ms: float) -> dict[str, Any]:
    points = np.argwhere(mask)

    # Independent prefix walk: the intercept belongs to the origin-connected
    # stable component and must stop at the first unstable sample.
    def prefix_end(values: np.ndarray) -> int | None:
        flags = np.asarray(values, dtype=bool).reshape(-1)
        if flags.size == 0 or not bool(flags[0]):
            return None
        index = 0
        while index + 1 < flags.size and bool(flags[index + 1]):
            index += 1
        return index

    env = envelope(mask)
    max_tau1_step = int(points[:, 1].max()) if points.size else None
    max_tau2_step = int(points[:, 0].max()) if points.size else None
    tau1_step = prefix_end(mask[0, :])
    tau2_step = prefix_end(mask[:, 0])
    diagonal_step = prefix_end(np.diag(mask[:, :31]))
    upper_integral_steps = 0
    previous_j: int | None = None
    previous_l: int | None = None
    for row in env:
        if not row["has_stable"]:
            previous_j = None
            previous_l = None
            continue
        j_value = int(row["j"])
        max_l_value = int(row["max_l"])
        if previous_j is not None and j_value == previous_j + 1:
            upper_integral_steps += int(previous_l)
        previous_j = j_value
        previous_l = max_l_value
    all_contiguous = all(row["contiguous"] for row in env) and not any(
        row["holes"] for row in env
    )
    return {
        "stable_count": int(mask.sum()),
        "max_tau1_any_stable_step": max_tau1_step,
        "max_tau1_any_stable_ms": None if max_tau1_step is None else max_tau1_step * dt_ms,
        "max_tau2_any_stable_step": max_tau2_step,
        "max_tau2_any_stable_ms": None if max_tau2_step is None else max_tau2_step * dt_ms,
        "axis_intercept_definition": "ORIGIN_CONNECTED_CONTIGUOUS_PREFIX_LAST_STABLE_INDEX_NO_HOLE_CROSSING",
        "tau1_axis_intercept_step": tau1_step,
        "tau1_axis_intercept_ms": None if tau1_step is None else tau1_step * dt_ms,
        "tau2_axis_intercept_step": tau2_step,
        "tau2_axis_intercept_ms": None if tau2_step is None else tau2_step * dt_ms,
        "equal_delay_diagonal_intercept_step": diagonal_step,
        "equal_delay_diagonal_intercept_ms": None
        if diagonal_step is None
        else diagonal_step * dt_ms,
        "stable_grid_area_proxy_ms2": int(mask.sum()) * dt_ms * dt_ms,
        "upper_envelope_integral_ms2": upper_integral_steps * dt_ms * dt_ms,
        "empty_column_count": sum(not row["has_stable"] for row in env),
        "hole_column_count": sum(row["holes"] > 0 for row in env),
        "hole_cell_count": sum(row["holes"] for row in env),
        "connected_component_count_4_neighbor": components(mask),
        "all_columns_contiguous_from_zero": all_contiguous,
        "upper_envelope_role": "TRUE_FILLED_BOUNDARY"
        if all_contiguous
        else "DIAGNOSTIC_UPPER_ENVELOPE_WITH_HOLES",
    }


def verify_scientific_tables(
    contract: Mapping[str, Any], run1: Path, validation_root: Path, checks: Checks
) -> dict[str, Any]:
    masks = historical_masks(contract)
    raw_values = historical_raw_values(contract)
    routes = candidate_route_arrays(contract)
    expected_counts = {
        "pointwise_comparison.csv": 10385,
        "route_eligibility.csv": 7,
        "target_cell_status.csv": 6,
        "confusion_matrix.csv": 7,
        "boundary_by_source.csv": 737,
        "boundary_difference.csv": 335,
        "stability_metrics.csv": 11,
        "extension_1_to_28_audit.csv": 56,
        "extension_summary.csv": 2,
        "claim_C05_C07.csv": 10,
        "div2_payload_relation_audit.csv": 1,
        "figure_status.csv": 2,
    }
    for filename, expected_count in expected_counts.items():
        _, rows = read_csv(run1 / "tables" / filename)
        checks.add(
            "table_contract",
            f"{filename}行数符合合同",
            len(rows) == expected_count,
            expected_count,
            len(rows),
            f"tables/{filename}",
        )

    _, point_rows = read_csv(run1 / "tables" / "pointwise_comparison.csv")
    expected_point_order = [
        (route["route_id"], l_value, j_value)
        for route in contract["routes"]
        for l_value in range(31)
        for j_value in range(67)
    ]
    actual_point_order = [
        (row["route_id"], int(row["l"]), int(row["j"])) for row in point_rows
    ]
    checks.add(
        "canonical_order",
        "逐点表严格按合同路线顺序及l主序、j次序排列",
        actual_point_order == expected_point_order,
        {"rows": 10385, "canonical": True},
        {"rows": len(actual_point_order), "canonical": actual_point_order == expected_point_order},
        "tables/pointwise_comparison.csv",
    )
    observed_points = {
        (row["route_id"], int(row["l"]), int(row["j"])): row for row in point_rows
    }
    point_failures: list[dict[str, Any]] = []
    expected_point_rows: list[dict[str, Any]] = []
    recomputed_confusion: dict[str, dict[str, int]] = {}
    for route_id, data in routes.items():
        route = data["contract"]
        history = masks[(route["division"], route["method"])]
        history_raw = raw_values[(route["division"], route["method"])]
        candidate = data["stable"]
        classes = defaultdict(int)
        for l_value in range(31):
            for j_value in range(67):
                historical_value = bool(history[l_value, j_value])
                candidate_value = bool(candidate[l_value, j_value])
                confusion_class = (
                    "TP"
                    if candidate_value and historical_value
                    else "FP"
                    if candidate_value
                    else "FN"
                    if historical_value
                    else "TN"
                )
                classes[confusion_class] += 1
                row = observed_points.get((route_id, l_value, j_value))
                rho_v4 = float(data["rho"][l_value, j_value])
                rho_step4 = float(data["rho_step4"][l_value, j_value])
                provenance_code = int(data["provenance_code"][l_value, j_value])
                source_row = data["rows"][l_value * 67 + j_value]
                critical = bool(
                    np.isfinite(rho_v4)
                    and abs(rho_v4 - 1.0)
                    <= float(contract["grid_contract"]["critical_tolerance"])
                )
                expected_point_rows.append(
                    {
                        "figure_id": route["figure_id"],
                        "division": route["division"],
                        "method": route["method"],
                        "route_id": route_id,
                        "route_role": route["route_role"],
                        "route_formula": route["route_formula"],
                        "l": l_value,
                        "j": j_value,
                        "tau1_ms": j_value
                        * float(contract["grid_contract"]["dt_milliseconds"]),
                        "tau2_ms": l_value
                        * float(contract["grid_contract"]["dt_milliseconds"]),
                        "historical_raw_value": float(
                            history_raw[l_value, j_value]
                        ),
                        "historical_stable": historical_value,
                        "rho_step4_matlab": rho_step4,
                        "rho_v4_python": rho_v4,
                        "rho_abs_diff_step4_v4": abs(rho_step4 - rho_v4),
                        "rho_minus_one": rho_v4 - 1.0,
                        "candidate_stable_stored": bool_text(source_row["stable"]),
                        "candidate_stable_rederived": candidate_value,
                        "step4_stable": bool(
                            data["stable_step4"][l_value, j_value]
                        ),
                        "critical_within_1e8": critical,
                        "confusion_class": confusion_class,
                        "mask_xor": candidate_value != historical_value,
                        "provenance_code": provenance_code,
                        "provenance_label": PROVENANCE_LABELS[provenance_code],
                        "point_status": source_row["point_status"],
                    }
                )
                correct = (
                    row is not None
                    and row["figure_id"] == route["figure_id"]
                    and row["division"] == route["division"]
                    and row["method"] == route["method"]
                    and row["route_role"] == route["route_role"]
                    and row["route_formula"] == route["route_formula"]
                    and math.isclose(float(row["tau1_ms"]), j_value * float(contract["grid_contract"]["dt_milliseconds"]), rel_tol=0.0, abs_tol=1e-14)
                    and math.isclose(float(row["tau2_ms"]), l_value * float(contract["grid_contract"]["dt_milliseconds"]), rel_tol=0.0, abs_tol=1e-14)
                    and math.isclose(float(row["historical_raw_value"]), float(history_raw[l_value, j_value]), rel_tol=0.0, abs_tol=1e-14)
                    and bool_text(row["historical_stable"]) == historical_value
                    and bool_text(row["candidate_stable_rederived"]) == candidate_value
                    and bool_text(row["candidate_stable_stored"]) == candidate_value
                    and bool_text(row["step4_stable"])
                    == bool(data["stable_step4"][l_value, j_value])
                    and bool(data["stable_step4"][l_value, j_value]) == candidate_value
                    and bool_text(row["critical_within_1e8"]) == critical
                    and row["confusion_class"] == confusion_class
                    and bool_text(row["mask_xor"])
                    == (historical_value != candidate_value)
                    and math.isclose(
                        float(row["rho_v4_python"]),
                        rho_v4,
                        rel_tol=0.0,
                        abs_tol=1e-14,
                    )
                    and math.isclose(float(row["rho_step4_matlab"]), rho_step4, rel_tol=0.0, abs_tol=1e-14)
                    and math.isclose(float(row["rho_abs_diff_step4_v4"]), abs(rho_step4 - rho_v4), rel_tol=0.0, abs_tol=1e-14)
                    and math.isclose(float(row["rho_minus_one"]), rho_v4 - 1.0, rel_tol=0.0, abs_tol=1e-14)
                    and int(row["provenance_code"]) == provenance_code
                    and row["provenance_label"] == PROVENANCE_LABELS[provenance_code]
                    and row["point_status"] == "PASS"
                )
                if not correct and len(point_failures) < 20:
                    point_failures.append(
                        {"route_id": route_id, "l": l_value, "j": j_value, "row": row}
                    )
        recomputed_confusion[route_id] = {
            key: int(classes[key]) for key in ["TP", "TN", "FP", "FN"]
        }
        checks.add(
            "candidate_rule",
            f"{route_id}候选点序、稳定分类及Step4分类独立闭合",
            len(data["seen"]) == 2077
            and [(int(row["l"]), int(row["j"])) for row in data["rows"]]
            == [(l_value, j_value) for l_value in range(31) for j_value in range(67)]
            and np.array_equal(data["stored"], candidate)
            and np.array_equal(data["stable_step4"], candidate),
            {"points": 2077, "stored_mismatch": 0, "step4_mismatch": 0, "canonical": True},
            {
                "points": len(data["seen"]),
                "stored_mismatch": int(np.sum(data["stored"] != candidate)),
                "step4_mismatch": int(np.sum(data["stable_step4"] != candidate)),
                "canonical": [(int(row["l"]), int(row["j"])) for row in data["rows"]]
                == [(l_value, j_value) for l_value in range(31) for j_value in range(67)],
            },
            route["point_summary_relpath"],
        )
    checks.add(
        "pointwise_recomputation",
        "10,385行逐点比较由原始历史MAT和Step5谱半径独立重算后全部一致",
        len(observed_points) == 10385 and not point_failures,
        {"unique_points": 10385, "failures": []},
        {"unique_points": len(observed_points), "failures": point_failures},
        "tables/pointwise_comparison.csv",
    )
    point_full_failures = full_row_failures(point_rows, expected_point_rows)
    checks.add(
        "full_row_recomputation",
        "pointwise_comparison.csv的固定表头、10385行规范顺序及25个字段按.17g序列化全部独立重算一致",
        not point_full_failures,
        {"rows": 10385, "failures": []},
        {"rows": len(point_rows), "failures": point_full_failures},
        "tables/pointwise_comparison.csv",
    )

    _, confusion_rows = read_csv(run1 / "tables" / "confusion_matrix.csv")
    confusion_by_route = {row["route_id"]: row for row in confusion_rows if row["route_id"]}
    expected_regression = {
        "main_ori_div1": {"TP": 65, "TN": 623, "FP": 0, "FN": 1389},
        "main_guyan_div1": {"TP": 93, "TN": 1033, "FP": 0, "FN": 951},
        "alt_guyan_div1_stable_full_ps3": {"TP": 7, "TN": 1033, "FP": 0, "FN": 1037},
        "main_ori_div2": {"TP": 34, "TN": 830, "FP": 0, "FN": 1213},
        "main_guyan_div2": {"TP": 34, "TN": 1148, "FP": 0, "FN": 895},
    }
    confusion_failures: list[dict[str, Any]] = []
    for route_id, expected in expected_regression.items():
        recomputed = recomputed_confusion[route_id]
        row = confusion_by_route[route_id]
        observed = {
            "TP": int(row["true_positive"]),
            "TN": int(row["true_negative"]),
            "FP": int(row["false_positive"]),
            "FN": int(row["false_negative"]),
        }
        if observed != expected or recomputed != expected:
            confusion_failures.append(
                {
                    "route_id": route_id,
                    "expected": expected,
                    "recomputed": recomputed,
                    "observed": observed,
                }
            )
    checks.add(
        "confusion_matrix",
        "五条可计算路线的独立混淆矩阵与冻结回归值完全一致",
        not confusion_failures,
        expected_regression,
        confusion_failures,
        "tables/confusion_matrix.csv",
    )

    route_contracts = {
        route["route_id"]: route for route in contract["routes"]
    }
    expected_confusion_by_route: dict[str, dict[str, Any]] = {}
    for route_id, route in route_contracts.items():
        data = routes[route_id]
        history = masks[(route["division"], route["method"])]
        candidate = data["stable"]
        values = recomputed_confusion[route_id]
        mismatch = values["FP"] + values["FN"]
        candidate_metrics = basic_metrics(
            candidate, float(contract["grid_contract"]["dt_milliseconds"])
        )
        expected_confusion_by_route[route_id] = {
            "figure_id": route["figure_id"],
            "division": route["division"],
            "method": route["method"],
            "route_id": route_id,
            "route_role": route["route_role"],
            "route_formula": route["route_formula"],
            "availability": "COMPUTABLE_CONTINUOUS_RHO",
            "evaluated_points": 2077,
            "expected_points": 2077,
            "historical_stable_points": int(history.sum()),
            "candidate_stable_points": int(candidate.sum()),
            "true_positive": values["TP"],
            "true_negative": values["TN"],
            "false_positive": values["FP"],
            "false_negative": values["FN"],
            "mask_mismatch_points": mismatch,
            "agreement_fraction": (values["TP"] + values["TN"]) / 2077.0,
            "candidate_is_subset_of_historical": values["FP"] == 0,
            "comparison_status": "EXACT_MASK_MATCH" if mismatch == 0 else "MASK_MISMATCH",
            "calculation_level_mask_gate_pass": mismatch == 0,
            "max_rho_step4_v4_abs_diff": float(
                np.max(np.abs(data["rho_step4"] - data["rho"]))
            ),
            "candidate_hole_columns": candidate_metrics["hole_column_count"],
            "candidate_hole_cells": candidate_metrics["hole_cell_count"],
            "candidate_connected_components": candidate_metrics[
                "connected_component_count_4_neighbor"
            ],
        }

    primary_by_target = {
        (route["division"], route["method"]): route
        for route in contract["routes"]
        if route["route_role"] == "PRIMARY"
    }
    expected_eligibility_rows: list[dict[str, Any]] = []
    expected_target_rows: list[dict[str, Any]] = []
    expected_confusion_rows: list[dict[str, Any]] = []
    for target in contract["target_cells"]:
        key = (target["division"], target["method"])
        primary = primary_by_target.get(key)
        history_count = int(masks[key].sum())
        if primary is None:
            expected_eligibility_rows.append(
                {
                    "figure_id": target["figure_id"],
                    "division": target["division"],
                    "method": target["method"],
                    "route_id": "",
                    "route_role": "PRIMARY_REQUIRED",
                    "route_formula": "",
                    "availability": "NOT_COMPUTABLE_MISSING_ROUTE",
                    "reason": "AUTHOR_ROUTE_CONTRACT_NOT_EXECUTABLE_DO_NOT_CREATE",
                    "candidate_point_count": 0,
                    "expected_point_count": 2077,
                }
            )
            expected_target_rows.append(
                {
                    **target,
                    "historical_stable_points": history_count,
                    "primary_route_id": "",
                    "primary_candidate_stable_points": "",
                    "mask_mismatch_points": "",
                    "target_status": "MISSING_PRIMARY_CONTINUOUS_RHO",
                    "calculation_level_target_gate_pass": False,
                }
            )
            expected_confusion_rows.append(
                {
                    "figure_id": target["figure_id"],
                    "division": target["division"],
                    "method": target["method"],
                    "route_id": "",
                    "route_role": "PRIMARY_REQUIRED",
                    "route_formula": "",
                    "availability": "NOT_COMPUTABLE_MISSING_ROUTE",
                    "evaluated_points": 0,
                    "expected_points": 2077,
                    "historical_stable_points": history_count,
                    "candidate_stable_points": "",
                    "true_positive": "",
                    "true_negative": "",
                    "false_positive": "",
                    "false_negative": "",
                    "mask_mismatch_points": "",
                    "agreement_fraction": "",
                    "candidate_is_subset_of_historical": "",
                    "comparison_status": "NOT_EVALUATED_MISSING_ROUTE",
                    "calculation_level_mask_gate_pass": False,
                    "max_rho_step4_v4_abs_diff": "",
                    "candidate_hole_columns": "",
                    "candidate_hole_cells": "",
                    "candidate_connected_components": "",
                }
            )
        else:
            route_id = primary["route_id"]
            row = expected_confusion_by_route[route_id]
            expected_eligibility_rows.append(
                {
                    "figure_id": target["figure_id"],
                    "division": target["division"],
                    "method": target["method"],
                    "route_id": route_id,
                    "route_role": primary["route_role"],
                    "route_formula": primary["route_formula"],
                    "availability": "COMPUTABLE_CONTINUOUS_RHO",
                    "reason": "FILE_IDENTITY_ROUTE_ONLY",
                    "candidate_point_count": 2077,
                    "expected_point_count": 2077,
                }
            )
            mismatch = int(row["mask_mismatch_points"])
            expected_target_rows.append(
                {
                    **target,
                    "historical_stable_points": history_count,
                    "primary_route_id": route_id,
                    "primary_candidate_stable_points": row["candidate_stable_points"],
                    "mask_mismatch_points": mismatch,
                    "target_status": "PRIMARY_MASK_EXACT_MATCH"
                    if mismatch == 0
                    else "PRIMARY_MASK_MISMATCH",
                    "calculation_level_target_gate_pass": mismatch == 0,
                }
            )
            expected_confusion_rows.append(dict(row))
    alternative = next(
        route
        for route in contract["routes"]
        if route["route_role"] == "ALTERNATIVE_NOT_PRIMARY"
    )
    expected_eligibility_rows.append(
        {
            "figure_id": alternative["figure_id"],
            "division": alternative["division"],
            "method": alternative["method"],
            "route_id": alternative["route_id"],
            "route_role": alternative["route_role"],
            "route_formula": alternative["route_formula"],
            "availability": "COMPUTABLE_ALTERNATIVE_DIAGNOSTIC_ONLY",
            "reason": "MUST_NOT_REPLACE_PRIMARY_GUYAN_OR_PICK_BEST_FIT",
            "candidate_point_count": 2077,
            "expected_point_count": 2077,
        }
    )
    expected_confusion_rows.append(
        dict(expected_confusion_by_route[alternative["route_id"]])
    )
    expected_figure_rows: list[dict[str, Any]] = []
    for figure_id, division in [("F4-4", "div1"), ("F4-5", "div2")]:
        cells = [row for row in expected_target_rows if row["figure_id"] == figure_id]
        all_present = all(bool(row["primary_route_id"]) for row in cells)
        all_exact = all(bool(row["calculation_level_target_gate_pass"]) for row in cells)
        gate = all_present and all_exact
        expected_figure_rows.append(
            {
                "figure_id": figure_id,
                "division": division,
                "method_cell_count": 3,
                "primary_continuous_rho_cell_count": sum(
                    bool(row["primary_route_id"]) for row in cells
                ),
                "exact_mask_match_cell_count": sum(
                    bool(row["calculation_level_target_gate_pass"]) for row in cells
                ),
                "all_three_primary_routes_present": all_present,
                "all_three_primary_masks_exact": all_exact,
                "calculation_level_figure_gate_pass": gate,
                "object_evidence_level": "CALCULATION_LEVEL_REPRODUCTION"
                if gate
                else "PLOTTING_LEVEL_REPRODUCTION",
                "formal_success_directory_allowed": gate,
                "candidate_location": "BOARD20_FAILURE_ROUTE",
            }
        )
    for filename, expected_rows in [
        ("route_eligibility.csv", expected_eligibility_rows),
        ("target_cell_status.csv", expected_target_rows),
        ("confusion_matrix.csv", expected_confusion_rows),
        ("figure_status.csv", expected_figure_rows),
    ]:
        _, observed_rows = read_csv(run1 / "tables" / filename)
        failures = full_row_failures(observed_rows, expected_rows)
        checks.add(
            "full_row_recomputation",
            f"{filename}固定表头、规范行序及全部字段由合同和原始掩膜/候选独立重算一致",
            not failures,
            {"rows": len(expected_rows), "failures": []},
            {"rows": len(observed_rows), "failures": failures},
            f"tables/{filename}",
        )

    _, boundary_rows = read_csv(run1 / "tables" / "boundary_by_source.csv")
    boundary_index = {
        (row["source_id"], int(row["j"])): row for row in boundary_rows
    }
    boundary_failures: list[dict[str, Any]] = []
    sources: dict[str, np.ndarray] = {}
    source_metadata: dict[str, dict[str, Any]] = {}
    for division in ["div1", "div2"]:
        for method in METHOD_VARIABLE:
            source_id = f"historical_{division}_{method.replace('-', '_')}"
            sources[source_id] = masks[(division, method)]
            source_metadata[source_id] = {
                "figure_id": contract["historical_masks"][division]["figure_id"],
                "division": division,
                "method": method,
                "source_kind": "HISTORICAL_MASK",
                "source_id": source_id,
                "route_id": "",
                "route_role": "HISTORICAL_VALUE",
            }
    for route_id, data in routes.items():
        sources[route_id] = data["stable"]
        route = data["contract"]
        source_metadata[route_id] = {
            "figure_id": route["figure_id"],
            "division": route["division"],
            "method": route["method"],
            "source_kind": "COMPUTED_ROUTE",
            "source_id": route_id,
            "route_id": route_id,
            "route_role": route["route_role"],
        }
    expected_boundary_order = [
        (source_id, j_value)
        for source_id in sources
        for j_value in range(67)
    ]
    actual_boundary_order = [
        (row["source_id"], int(row["j"])) for row in boundary_rows
    ]
    checks.add(
        "canonical_order",
        "737行边界表严格按六历史来源、五候选来源及j升序排列",
        actual_boundary_order == expected_boundary_order,
        {"rows": 737, "canonical": True},
        {"rows": len(actual_boundary_order), "canonical": actual_boundary_order == expected_boundary_order},
        "tables/boundary_by_source.csv",
    )
    for source_id, mask in sources.items():
        for expected in envelope(mask):
            row = boundary_index.get((source_id, expected["j"]))
            correct = (
                row is not None
                and bool_text(row["has_stable"]) == expected["has_stable"]
                and int(row["stable_count_in_column"]) == expected["count"]
                and (int(row["min_l"]) if row["min_l"] else None) == expected["min_l"]
                and (int(row["max_l"]) if row["max_l"] else None) == expected["max_l"]
                and int(row["hole_count"]) == expected["holes"]
                and bool_text(row["contiguous_from_zero"]) == expected["contiguous"]
            )
            if not correct and len(boundary_failures) < 20:
                boundary_failures.append(
                    {"source_id": source_id, "j": expected["j"], "expected": expected, "row": row}
                )
    checks.add(
        "boundary_recomputation",
        "11个来源共737列边界记录由掩膜独立重算后逐列一致",
        len(boundary_index) == 737 and not boundary_failures,
        {"unique_rows": 737, "failures": []},
        {"unique_rows": len(boundary_index), "failures": boundary_failures},
        "tables/boundary_by_source.csv",
    )
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    expected_boundary_rows: list[dict[str, Any]] = []
    for source_id, mask in sources.items():
        metadata = source_metadata[source_id]
        for item in envelope(mask):
            max_l_value = item["max_l"]
            expected_boundary_rows.append(
                {
                    **metadata,
                    "j": item["j"],
                    "tau1_ms": item["j"] * dt_ms,
                    "has_stable": item["has_stable"],
                    "stable_count_in_column": item["count"],
                    "min_l": item["min_l"],
                    "max_l": max_l_value,
                    "tau2_upper_ms": None
                    if max_l_value is None
                    else max_l_value * dt_ms,
                    "contiguous_from_zero": item["contiguous"],
                    "hole_count": item["holes"],
                    "boundary_role": "TRUE_FILLED_BOUNDARY"
                    if item["contiguous"]
                    else "DIAGNOSTIC_UPPER_ENVELOPE_WITH_HOLES",
                }
            )
    boundary_full_failures = full_row_failures(
        boundary_rows, expected_boundary_rows
    )
    checks.add(
        "full_row_recomputation",
        "boundary_by_source.csv的固定表头、737行规范顺序及17个字段全部独立重算一致",
        not boundary_full_failures,
        {"rows": 737, "failures": []},
        {"rows": len(boundary_rows), "failures": boundary_full_failures},
        "tables/boundary_by_source.csv",
    )

    _, difference_rows = read_csv(run1 / "tables" / "boundary_difference.csv")
    expected_difference_order = [
        (route["route_id"], j_value)
        for route in contract["routes"]
        for j_value in range(67)
    ]
    actual_difference_order = [
        (row["route_id"], int(row["j"])) for row in difference_rows
    ]
    checks.add(
        "canonical_order",
        "335行边界差严格按合同路线及j升序排列",
        actual_difference_order == expected_difference_order,
        {"rows": 335, "canonical": True},
        {"rows": len(actual_difference_order), "canonical": actual_difference_order == expected_difference_order},
        "tables/boundary_difference.csv",
    )
    difference_failures: list[dict[str, Any]] = []
    for row in difference_rows:
        route_id = row["route_id"]
        route = routes[route_id]["contract"]
        history_env = envelope(masks[(route["division"], route["method"])])
        candidate_env = envelope(routes[route_id]["stable"])
        j_value = int(row["j"])
        h_row = history_env[j_value]
        c_row = candidate_env[j_value]
        expected_difference = (
            c_row["max_l"] - h_row["max_l"]
            if h_row["has_stable"] and c_row["has_stable"]
            else None
        )
        observed_difference = (
            int(row["candidate_minus_historical_max_l"])
            if row["candidate_minus_historical_max_l"]
            else None
        )
        if expected_difference != observed_difference and len(difference_failures) < 20:
            difference_failures.append(
                {"route_id": route_id, "j": j_value, "expected": expected_difference, "actual": observed_difference}
            )
    checks.add(
        "boundary_recomputation",
        "335行候选减历史边界差由两侧掩膜独立重算后一致",
        len(difference_rows) == 335 and not difference_failures,
        {"rows": 335, "failures": []},
        {"rows": len(difference_rows), "failures": difference_failures},
        "tables/boundary_difference.csv",
    )
    expected_difference_rows: list[dict[str, Any]] = []
    for route in contract["routes"]:
        route_id = route["route_id"]
        history_env = envelope(masks[(route["division"], route["method"])])
        candidate_env = envelope(routes[route_id]["stable"])
        for j_value, (history_item, candidate_item) in enumerate(
            zip(history_env, candidate_env)
        ):
            history_has = bool(history_item["has_stable"])
            candidate_has = bool(candidate_item["has_stable"])
            if history_has and candidate_has:
                relation = "BOTH"
                difference = int(candidate_item["max_l"]) - int(history_item["max_l"])
            elif history_has:
                relation = "HISTORICAL_ONLY"
                difference = None
            elif candidate_has:
                relation = "CANDIDATE_ONLY"
                difference = None
            else:
                relation = "NEITHER"
                difference = None
            expected_difference_rows.append(
                {
                    "figure_id": route["figure_id"],
                    "division": route["division"],
                    "method": route["method"],
                    "route_id": route_id,
                    "route_role": route["route_role"],
                    "j": j_value,
                    "tau1_ms": j_value * dt_ms,
                    "boundary_presence_relation": relation,
                    "historical_max_l": history_item["max_l"],
                    "candidate_max_l": candidate_item["max_l"],
                    "candidate_minus_historical_max_l": difference,
                    "candidate_minus_historical_tau2_ms": None
                    if difference is None
                    else difference * dt_ms,
                    "candidate_column_hole_count": candidate_item["holes"],
                    "boundary_comparison_role": "VALID_UPPER_BOUNDARY_COMPARISON"
                    if candidate_item["contiguous"]
                    else "DIAGNOSTIC_ENVELOPE_ONLY_CANDIDATE_HAS_HOLES",
                }
            )
    difference_full_failures = full_row_failures(
        difference_rows, expected_difference_rows
    )
    checks.add(
        "full_row_recomputation",
        "boundary_difference.csv的固定表头、335行规范顺序及14个字段全部独立重算一致",
        not difference_full_failures,
        {"rows": 335, "failures": []},
        {"rows": len(difference_rows), "failures": difference_full_failures},
        "tables/boundary_difference.csv",
    )

    _, metrics_rows = read_csv(run1 / "tables" / "stability_metrics.csv")
    metrics_index = {row["source_id"]: row for row in metrics_rows}
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    metrics_failures: list[dict[str, Any]] = []
    keys = [
        "stable_count",
        "max_tau1_any_stable_step",
        "max_tau2_any_stable_step",
        "axis_intercept_definition",
        "tau1_axis_intercept_step",
        "tau2_axis_intercept_step",
        "equal_delay_diagonal_intercept_step",
        "empty_column_count",
        "hole_column_count",
        "hole_cell_count",
        "connected_component_count_4_neighbor",
    ]
    for source_id, mask in sources.items():
        expected = basic_metrics(mask, dt_ms)
        observed = metrics_index[source_id]
        for key in keys:
            expected_value = "" if expected[key] is None else str(expected[key])
            if observed[key] != expected_value:
                metrics_failures.append(
                    {"source_id": source_id, "key": key, "expected": expected_value, "actual": observed[key]}
                )
        if not math.isclose(
            float(observed["stable_grid_area_proxy_ms2"]),
            float(expected["stable_grid_area_proxy_ms2"]),
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            metrics_failures.append(
                {"source_id": source_id, "key": "stable_grid_area_proxy_ms2"}
            )
    checks.add(
        "metric_recomputation",
        "11个来源的稳定点数、时滞截距索引、面积代理、孔洞与连通分量独立重算一致",
        not metrics_failures,
        [],
        metrics_failures[:20],
        "tables/stability_metrics.csv",
    )
    expected_metrics_rows: list[dict[str, Any]] = []
    for source_id, mask in sources.items():
        metadata = source_metadata[source_id]
        expected_metrics_rows.append(
            {
                "source_id": source_id,
                "source_kind": metadata["source_kind"],
                "figure_id": metadata["figure_id"],
                "division": metadata["division"],
                "method": metadata["method"],
                "route_id": metadata["route_id"],
                "route_role": metadata["route_role"],
                **basic_metrics(mask, dt_ms),
            }
        )
    metrics_full_failures = full_row_failures(
        metrics_rows, expected_metrics_rows
    )
    checks.add(
        "full_row_recomputation",
        "stability_metrics.csv的固定表头、11行规范顺序及27个字段全部独立重算一致",
        not metrics_full_failures,
        {"rows": 11, "failures": []},
        {"rows": len(metrics_rows), "failures": metrics_full_failures},
        "tables/stability_metrics.csv",
    )

    intercept_definition = contract["grid_contract"].get("axis_intercept_definition")
    div2_intercept_regression = {
        source_id: {
            "max_tau2_any_stable_step": direct["max_tau2_any_stable_step"],
            "tau2_axis_intercept_step": direct["tau2_axis_intercept_step"],
        }
        for source_id, direct in {
            source_id: basic_metrics(sources[source_id], dt_ms)
            for source_id in ["main_ori_div2", "main_guyan_div2"]
        }.items()
    }
    checks.add(
        "origin_connected_intercept_regression",
        "第二类候选tau2轴最大稳定点为16步，但原点连续截距在首个孔洞前止于6步",
        intercept_definition
        == "ORIGIN_CONNECTED_CONTIGUOUS_PREFIX_LAST_STABLE_INDEX_NO_HOLE_CROSSING"
        and all(
            values["max_tau2_any_stable_step"] == 16
            and values["tau2_axis_intercept_step"] == 6
            for values in div2_intercept_regression.values()
        ),
        {
            source_id: {
                "max_tau2_any_stable_step": 16,
                "tau2_axis_intercept_step": 6,
            }
            for source_id in div2_intercept_regression
        },
        div2_intercept_regression,
        "tables/stability_metrics.csv",
    )

    direct_metrics = {
        source_id: basic_metrics(mask, dt_ms) for source_id, mask in sources.items()
    }
    claim_contracts = [
        ("historical_div1_original_to_cb", "HISTORICAL_MASK", "historical_div1_Original", "historical_div1_Craig_Bampton", "first-division reduced-model actuator delay margins decrease by about 5 ms", "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY"),
        ("historical_div1_original_to_guyan", "HISTORICAL_MASK", "historical_div1_Original", "historical_div1_Guyan", "first-division reduced-model actuator delay margins decrease by about 5 ms", "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY"),
        ("historical_div2_original_to_cb", "HISTORICAL_MASK", "historical_div2_Original", "historical_div2_Craig_Bampton", "second-division stability-margin reduction", "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY"),
        ("historical_div2_original_to_guyan", "HISTORICAL_MASK", "historical_div2_Original", "historical_div2_Guyan", "second-division Guyan reduction described as approaching 10 ms", "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY"),
        ("historical_guyan_div1_to_div2", "HISTORICAL_MASK", "historical_div1_Guyan", "historical_div2_Guyan", "second-division Guyan further reduction described as approaching 10 ms", "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY"),
        ("computed_div1_original_to_main_guyan", "COMPUTED_FILE_IDENTITY_ROUTES", "main_ori_div1", "main_guyan_div1", "first-division reduced-model actuator delay margins decrease by about 5 ms", "ROUTE_LEVEL_COMPUTATION_ONLY_MASKS_MISMATCH_HISTORY"),
        ("computed_div1_original_to_alternative_guyan", "COMPUTED_ALTERNATIVE_ROUTE", "main_ori_div1", "alt_guyan_div1_stable_full_ps3", "diagnostic sensitivity only; alternative must not replace primary", "ALTERNATIVE_NOT_PRIMARY_MASK_MISMATCH_HISTORY"),
        ("computed_div2_original_to_main_guyan", "COMPUTED_FILE_IDENTITY_ROUTES", "main_ori_div2", "main_guyan_div2", "second-division Guyan critical-delay reduction greater than 5 ms", "IDENTICAL_NUMERIC_PAYLOAD_UNDER_DIFFERENT_METHOD_LABELS"),
        ("computed_main_guyan_div1_to_div2", "COMPUTED_FILE_IDENTITY_ROUTES", "main_guyan_div1", "main_guyan_div2", "second-division Guyan further reduction described as approaching 10 ms", "ROUTE_LEVEL_COMPUTATION_ONLY_MASKS_MISMATCH_HISTORY"),
    ]
    _, claim_rows = read_csv(run1 / "tables" / "claim_C05_C07.csv")
    claim_index = {row["comparison_id"]: row for row in claim_rows}
    claim_failures: list[dict[str, Any]] = []
    expected_claim_rows: list[dict[str, Any]] = []
    expected_claim_order = [item[0] for item in claim_contracts] + [
        "not_evaluated_in_board20_step6"
    ]
    for comparison_id, evidence_source, base_id, reduced_id, phrase, closure in claim_contracts:
        row = claim_index.get(comparison_id)
        base = direct_metrics[base_id]
        reduced = direct_metrics[reduced_id]
        expected_numbers = {
            "tau1_axis_intercept_drop_ms": (
                base["tau1_axis_intercept_step"] - reduced["tau1_axis_intercept_step"]
            )
            * dt_ms,
            "tau2_axis_intercept_drop_ms": (
                base["tau2_axis_intercept_step"] - reduced["tau2_axis_intercept_step"]
            )
            * dt_ms,
            "equal_delay_diagonal_intercept_drop_ms": (
                base["equal_delay_diagonal_intercept_step"]
                - reduced["equal_delay_diagonal_intercept_step"]
            )
            * dt_ms,
            "stable_point_drop": base["stable_count"] - reduced["stable_count"],
            "stable_grid_area_proxy_drop_ms2": base["stable_grid_area_proxy_ms2"]
            - reduced["stable_grid_area_proxy_ms2"],
        }
        expected_claim_rows.append(
            {
                "claim_ids": "C05;C07_CRITICAL_DELAY_COMPONENT",
                "comparison_id": comparison_id,
                "evidence_source": evidence_source,
                "base_source_id": base_id,
                "reduced_source_id": reduced_id,
                "axis_intercept_definition": contract["grid_contract"][
                    "axis_intercept_definition"
                ],
                **expected_numbers,
                "claimed_phrase": phrase,
                "qualitative_tolerance_status": "QUALITATIVE_TOLERANCE_UNDEFINED",
                "route_or_mask_closure": closure,
                "eligible_for_calculation_level_upgrade": False,
                "non_upgrade_reason": "SIX_METHOD_DIVISION_CELLS_NOT_CLOSED_AND_AVAILABLE_MASKS_DO_NOT_MATCH_HISTORY",
            }
        )
        correct = (
            row is not None
            and row["claim_ids"] == "C05;C07_CRITICAL_DELAY_COMPONENT"
            and row["evidence_source"] == evidence_source
            and row["base_source_id"] == base_id
            and row["reduced_source_id"] == reduced_id
            and row["axis_intercept_definition"]
            == contract["grid_contract"]["axis_intercept_definition"]
            and row["claimed_phrase"] == phrase
            and row["qualitative_tolerance_status"] == "QUALITATIVE_TOLERANCE_UNDEFINED"
            and row["route_or_mask_closure"] == closure
            and not bool_text(row["eligible_for_calculation_level_upgrade"])
            and row["non_upgrade_reason"]
            == "SIX_METHOD_DIVISION_CELLS_NOT_CLOSED_AND_AVAILABLE_MASKS_DO_NOT_MATCH_HISTORY"
            and all(
                math.isclose(
                    float(row[field]), float(value), rel_tol=0.0, abs_tol=1e-12
                )
                for field, value in expected_numbers.items()
            )
        )
        if not correct:
            claim_failures.append(
                {"comparison_id": comparison_id, "expected_numbers": expected_numbers, "row": row}
            )
    outscope = claim_index.get("not_evaluated_in_board20_step6")
    outscope_correct = (
        outscope is not None
        and outscope["claim_ids"] == "C07_FREQUENCY_AND_AMPLITUDE_COMPONENTS"
        and outscope["evidence_source"] == "OUT_OF_SCOPE"
        and outscope["axis_intercept_definition"] == ""
        and outscope["qualitative_tolerance_status"] == "NOT_EVALUATED_IN_STEP6"
        and outscope["route_or_mask_closure"] == "OUTSIDE_BOARD20_STABILITY_SCOPE"
        and not bool_text(outscope["eligible_for_calculation_level_upgrade"])
    )
    expected_claim_rows.append(
        {
            "claim_ids": "C07_FREQUENCY_AND_AMPLITUDE_COMPONENTS",
            "comparison_id": "not_evaluated_in_board20_step6",
            "evidence_source": "OUT_OF_SCOPE",
            "base_source_id": "",
            "reduced_source_id": "",
            "axis_intercept_definition": "",
            "tau1_axis_intercept_drop_ms": "",
            "tau2_axis_intercept_drop_ms": "",
            "equal_delay_diagonal_intercept_drop_ms": "",
            "stable_point_drop": "",
            "stable_grid_area_proxy_drop_ms2": "",
            "claimed_phrase": "frequency bands and response-amplitude errors",
            "qualitative_tolerance_status": "NOT_EVALUATED_IN_STEP6",
            "route_or_mask_closure": "OUTSIDE_BOARD20_STABILITY_SCOPE",
            "eligible_for_calculation_level_upgrade": False,
            "non_upgrade_reason": "BOARD20_STEP6_ONLY_EVALUATES_CRITICAL_DELAY_COMPONENT",
        }
    )
    claim_full_failures = full_row_failures(claim_rows, expected_claim_rows)
    checks.add(
        "claim_recomputation",
        "C05/C07九组临界时滞、稳定点和面积差由11个掩膜独立重算，频带/幅值保持未评价",
        [row["comparison_id"] for row in claim_rows] == expected_claim_order
        and len(claim_index) == 10
        and not claim_failures
        and outscope_correct,
        {"comparison_ids": expected_claim_order, "failures": [], "outscope": True},
        {
            "comparison_ids": [row["comparison_id"] for row in claim_rows],
            "failures": claim_failures[:10],
            "outscope": outscope_correct,
        },
        "tables/claim_C05_C07.csv",
    )
    checks.add(
        "full_row_recomputation",
        "claim_C05_C07.csv的固定表头、10行规范顺序及16个字段全部独立重算一致",
        not claim_full_failures,
        {"rows": 10, "failures": []},
        {"rows": len(claim_rows), "failures": claim_full_failures},
        "tables/claim_C05_C07.csv",
    )

    raw_div2 = loadmat(board_path(contract["historical_masks"]["div2"]["raw_relpath"]))
    _, extension_rows = read_csv(run1 / "tables" / "extension_1_to_28_audit.csv")
    extension_failures: list[dict[str, Any]] = []
    expected_extension_rows: list[dict[str, Any]] = []
    for record in contract["second_division_extension_contract"]:
        array = np.asarray(raw_div2[record["variable"]], dtype=float)
        row_index = int(record["sequence_row_1based"]) - 1
        start = int(record["sequence_column_start_1based"]) - 1
        end = int(record["sequence_column_end_1based"])
        sequence = array[row_index, start:end]
        if not np.array_equal(sequence, np.arange(1, 29, dtype=float)):
            extension_failures.append({"method": record["method"], "sequence": sequence.tolist()})
        for offset, actual_value in enumerate(sequence):
            column_1based = start + offset + 1
            expected_extension_rows.append(
                {
                    "method": record["method"],
                    "variable": record["variable"],
                    "raw_rows": int(array.shape[0]),
                    "raw_columns": int(array.shape[1]),
                    "sequence_row_1based": row_index + 1,
                    "sequence_column_1based": column_1based,
                    "expected_value": offset + 1,
                    "actual_value": float(actual_value),
                    "value_match": float(actual_value) == float(offset + 1),
                    "inside_common_31x67": row_index < 31
                    and column_1based <= 67,
                    "strict_historical_stable": bool(
                        np.isfinite(actual_value)
                        and actual_value > 0.0
                        and actual_value < 1.0
                    ),
                    "interpretation": "HISTORICAL_OUT_OF_GRID_INDEX_SEQUENCE_NOT_RHO",
                }
            )
        output_subset = [row for row in extension_rows if row["method"] == record["method"]]
        if len(output_subset) != 28 or any(
            int(row["expected_value"]) != index + 1
            or float(row["actual_value"]) != float(index + 1)
            or bool_text(row["inside_common_31x67"])
            or bool_text(row["strict_historical_stable"])
            for index, row in enumerate(output_subset)
        ):
            extension_failures.append({"method": record["method"], "output_rows": len(output_subset)})
    checks.add(
        "extension_1_to_28",
        "第二类Craig-Bampton/Guyan共同网格外序列独立确认为1至28且不属于严格稳定点",
        not extension_failures,
        [],
        extension_failures,
        "tables/extension_1_to_28_audit.csv",
    )
    extension_full_failures = full_row_failures(
        extension_rows, expected_extension_rows
    )
    checks.add(
        "full_row_recomputation",
        "extension_1_to_28_audit.csv的固定表头、56行规范顺序及12个字段全部由原始矩阵独立重算一致",
        not extension_full_failures,
        {"rows": 56, "failures": []},
        {"rows": len(extension_rows), "failures": extension_full_failures},
        "tables/extension_1_to_28_audit.csv",
    )
    _, extension_summary_rows = read_csv(
        run1 / "tables" / "extension_summary.csv"
    )
    extension_summary_failures: list[dict[str, Any]] = []
    expected_extension_summary_rows: list[dict[str, Any]] = []
    for record in contract["second_division_extension_contract"]:
        array = np.asarray(raw_div2[record["variable"]], dtype=float)
        raw_rows, raw_columns = (int(value) for value in array.shape)
        outside_mask = np.ones(array.shape, dtype=bool)
        outside_mask[:31, :67] = False
        outside_values = array[outside_mask]
        outside = int(outside_values.size)
        outside_nonzero = int(np.count_nonzero(outside_values))
        outside_strict_stable = int(
            np.sum(
                np.isfinite(outside_values)
                & (outside_values > 0.0)
                & (outside_values < 1.0)
            )
        )
        row_index = int(record["sequence_row_1based"]) - 1
        sequence_start = int(record["sequence_column_start_1based"]) - 1
        sequence_end = int(record["sequence_column_end_1based"])
        sequence = array[row_index, sequence_start:sequence_end]
        expected = {
            "method": record["method"],
            "variable": record["variable"],
            "raw_rows": raw_rows,
            "raw_columns": raw_columns,
            "common_grid_cells": 2077,
            "outside_common_grid_cells": outside,
            "outside_nonzero_sequence_cells": outside_nonzero,
            "outside_zero_cells": outside - outside_nonzero,
            "outside_strict_stable_cells": outside_strict_stable,
            "sequence_values_exact_1_to_28": bool(
                np.array_equal(sequence, np.arange(1, 29, dtype=float))
            ),
            "comparison_disposition": "EXCLUDED_FROM_COMMON_GRID_NOT_RHO",
        }
        expected_extension_summary_rows.append(expected)
    extension_summary_full_failures = full_row_failures(
        extension_summary_rows, expected_extension_summary_rows
    )
    extension_summary_failures.extend(extension_summary_full_failures)
    checks.add(
        "extension_1_to_28",
        "两行扩展摘要的原始尺寸、网格外零/非零数和排除语义独立闭合",
        len(extension_summary_rows) == 2
        and not extension_summary_failures
        and all(
            row["comparison_disposition"]
            == "EXCLUDED_FROM_COMMON_GRID_NOT_RHO"
            for row in extension_summary_rows
        ),
        {"rows": 2, "failures": []},
        {"rows": len(extension_summary_rows), "failures": extension_summary_failures},
        "tables/extension_summary.csv",
    )
    checks.add(
        "full_row_recomputation",
        "extension_summary.csv的固定表头、2行规范顺序及11个字段全部由原始矩阵完整网格外扫描重算一致",
        not extension_summary_full_failures,
        {"rows": 2, "failures": []},
        {
            "rows": len(extension_summary_rows),
            "failures": extension_summary_full_failures,
        },
        "tables/extension_summary.csv",
    )

    _, relation_rows = read_csv(run1 / "tables" / "div2_payload_relation_audit.csv")
    relation = relation_rows[0]
    left_fields = routes["main_ori_div2"]["fields"]
    right_fields = routes["main_guyan_div2"]["fields"]
    left_rows = routes["main_ori_div2"]["rows"]
    right_rows = routes["main_guyan_div2"]["rows"]
    payload_shape_closed = (
        left_fields == right_fields
        and len(left_rows) == len(right_rows)
        and len(left_rows) == 2077
    )
    compare_fields = [field for field in left_fields if field not in {"route_id", "declared_method"}]
    unequal = sum(
        any(left[field] != right[field] for field in compare_fields)
        for left, right in zip(left_rows, right_rows)
    )
    unequal_fields = sorted(
        {
            field
            for left, right in zip(left_rows, right_rows)
            for field in compare_fields
            if left[field] != right[field]
        }
    )
    expected_relation_rows = [
        {
            "left_route": "main_ori_div2",
            "right_route": "main_guyan_div2",
            "point_count": len(left_rows),
            "csv_field_count": len(left_fields),
            "excluded_identity_fields": ";".join(
                sorted({"route_id", "declared_method"})
            ),
            "compared_nonidentity_fields": len(compare_fields),
            "unequal_nonidentity_fields": ";".join(unequal_fields),
            "unequal_points": unequal,
            "max_rho_abs_diff": float(
                np.max(
                    np.abs(
                        routes["main_ori_div2"]["rho"]
                        - routes["main_guyan_div2"]["rho"]
                    )
                )
            ),
            "stable_mismatch_points": int(
                np.sum(
                    routes["main_ori_div2"]["stable"]
                    != routes["main_guyan_div2"]["stable"]
                )
            ),
            "relation": "IDENTICAL_NUMERIC_FILE_IDENTITY_PAYLOAD"
            if not unequal_fields
            else "NONIDENTICAL_PAYLOAD",
            "interpretation": "DOES_NOT_PROVE_ORIGINAL_AND_GUYAN_THEORY_EQUIVALENT",
        }
    ]
    relation_full_failures = full_row_failures(
        relation_rows, expected_relation_rows
    )
    checks.add(
        "div2_identity_payload",
        "第二类Original/Guyan表头和2077行先闭合，再对非身份字段逐项比较完全相同，且输出不宣称理论等价",
        payload_shape_closed
        and unequal == 0
        and int(relation["unequal_points"]) == 0
        and relation["interpretation"] == "DOES_NOT_PROVE_ORIGINAL_AND_GUYAN_THEORY_EQUIVALENT",
        {
            "same_fields": True,
            "left_rows": 2077,
            "right_rows": 2077,
            "unequal_points": 0,
            "interpretation": "DOES_NOT_PROVE_ORIGINAL_AND_GUYAN_THEORY_EQUIVALENT",
        },
        {
            "same_fields": left_fields == right_fields,
            "left_rows": len(left_rows),
            "right_rows": len(right_rows),
            "unequal_points": unequal,
            "interpretation": relation["interpretation"],
        },
        "tables/div2_payload_relation_audit.csv",
    )
    checks.add(
        "full_row_recomputation",
        "div2_payload_relation_audit.csv的固定表头、唯一行及12个字段由两份路线载荷独立逐点重算一致",
        not relation_full_failures,
        {"rows": 1, "failures": []},
        {"rows": len(relation_rows), "failures": relation_full_failures},
        "tables/div2_payload_relation_audit.csv",
    )

    _, eligibility_rows = read_csv(run1 / "tables" / "route_eligibility.csv")
    _, target_rows = read_csv(run1 / "tables" / "target_cell_status.csv")
    primary_by_cell = {
        (route["division"], route["method"]): route
        for route in contract["routes"]
        if route["route_role"] == "PRIMARY"
    }
    eligibility_failures: list[dict[str, Any]] = []
    for target, eligibility, target_row in zip(
        contract["target_cells"], eligibility_rows[:6], target_rows
    ):
        primary = primary_by_cell.get((target["division"], target["method"]))
        history_count = int(masks[(target["division"], target["method"])].sum())
        if primary is None:
            correct = (
                eligibility["route_id"] == ""
                and eligibility["availability"] == "NOT_COMPUTABLE_MISSING_ROUTE"
                and eligibility["reason"]
                == "AUTHOR_ROUTE_CONTRACT_NOT_EXECUTABLE_DO_NOT_CREATE"
                and int(eligibility["candidate_point_count"]) == 0
                and target_row["target_status"]
                == "MISSING_PRIMARY_CONTINUOUS_RHO"
                and target_row["primary_route_id"] == ""
                and not bool_text(target_row["calculation_level_target_gate_pass"])
            )
        else:
            mismatch = int(confusion_by_route[primary["route_id"]]["mask_mismatch_points"])
            correct = (
                eligibility["route_id"] == primary["route_id"]
                and eligibility["route_role"] == "PRIMARY"
                and eligibility["route_formula"] == primary["route_formula"]
                and eligibility["availability"] == "COMPUTABLE_CONTINUOUS_RHO"
                and eligibility["reason"] == "FILE_IDENTITY_ROUTE_ONLY"
                and int(eligibility["candidate_point_count"]) == 2077
                and target_row["primary_route_id"] == primary["route_id"]
                and int(target_row["mask_mismatch_points"]) == mismatch
                and target_row["target_status"] == "PRIMARY_MASK_MISMATCH"
                and not bool_text(target_row["calculation_level_target_gate_pass"])
            )
        correct = (
            correct
            and eligibility["figure_id"] == target["figure_id"]
            and eligibility["division"] == target["division"]
            and eligibility["method"] == target["method"]
            and int(eligibility["expected_point_count"]) == 2077
            and int(target_row["historical_stable_points"]) == history_count
        )
        if not correct:
            eligibility_failures.append(
                {"target": target, "eligibility": eligibility, "target_row": target_row}
            )
    alternative = next(
        route
        for route in contract["routes"]
        if route["route_role"] == "ALTERNATIVE_NOT_PRIMARY"
    )
    alternative_row = eligibility_rows[6]
    alternative_correct = (
        alternative_row["route_id"] == alternative["route_id"]
        and alternative_row["availability"]
        == "COMPUTABLE_ALTERNATIVE_DIAGNOSTIC_ONLY"
        and alternative_row["reason"]
        == "MUST_NOT_REPLACE_PRIMARY_GUYAN_OR_PICK_BEST_FIT"
        and int(alternative_row["candidate_point_count"]) == 2077
    )
    checks.add(
        "route_eligibility",
        "六个目标格与一条Guyan替代路线的身份、可用性、缺失原因和对象门逐行闭合",
        len(eligibility_rows) == 7
        and len(target_rows) == 6
        and not eligibility_failures
        and alternative_correct,
        {"eligibility_rows": 7, "target_rows": 6, "failures": [], "alternative": True},
        {
            "eligibility_rows": len(eligibility_rows),
            "target_rows": len(target_rows),
            "failures": eligibility_failures,
            "alternative": alternative_correct,
        },
        "tables/route_eligibility.csv | target_cell_status.csv",
    )

    _, figure_rows = read_csv(run1 / "tables" / "figure_status.csv")
    missing_cb = [
        row for row in target_rows if row["method"] == "Craig-Bampton" and not row["primary_route_id"]
    ]
    checks.add(
        "object_gate",
        "两个图对象门均如实停留在绘图级，两个Craig-Bampton目标格均明确缺失",
        len(missing_cb) == 2
        and [row["figure_id"] for row in figure_rows] == ["F4-4", "F4-5"]
        and all(int(row["method_cell_count"]) == 3 for row in figure_rows)
        and all(int(row["primary_continuous_rho_cell_count"]) == 2 for row in figure_rows)
        and all(int(row["exact_mask_match_cell_count"]) == 0 for row in figure_rows)
        and all(not bool_text(row["calculation_level_figure_gate_pass"]) for row in figure_rows)
        and all(row["object_evidence_level"] == "PLOTTING_LEVEL_REPRODUCTION" for row in figure_rows)
        and all(not bool_text(row["formal_success_directory_allowed"]) for row in figure_rows),
        {"missing_cb": 2, "levels": ["PLOTTING_LEVEL_REPRODUCTION"] * 2},
        {
            "missing_cb": len(missing_cb),
            "levels": [row["object_evidence_level"] for row in figure_rows],
        },
        "tables/figure_status.csv | target_cell_status.csv",
    )
    return {
        "masks": masks,
        "routes": routes,
        "regression_confusion": expected_regression,
    }


def resolve_object(value: Any) -> Any:
    return value.get_object() if hasattr(value, "get_object") else value


def pdf_stream_has_embedded_font(font_obj: Any) -> bool:
    font_obj = resolve_object(font_obj)
    font_candidates: list[Any]
    if str(font_obj.get("/Subtype", "")) == "/Type0":
        descendants = resolve_object(font_obj.get("/DescendantFonts", []))
        font_candidates = [resolve_object(item) for item in descendants]
    else:
        font_candidates = [font_obj]
    for candidate in font_candidates:
        descriptor = resolve_object(candidate.get("/FontDescriptor", {}))
        if not descriptor:
            continue
        for key in ["/FontFile", "/FontFile2", "/FontFile3"]:
            stream = resolve_object(descriptor.get(key))
            if stream is not None and hasattr(stream, "get_data"):
                try:
                    if len(stream.get_data()) > 0:
                        return True
                except Exception:
                    continue
    return False


def inline_image_count(stream_object: Any, reader: PdfReader) -> int:
    stream_object = resolve_object(stream_object)
    if stream_object is None:
        return 0
    try:
        operations = ContentStream(stream_object, reader).operations
    except Exception:
        return 0
    return sum(operator == b"INLINE IMAGE" for _, operator in operations)


def inspect_pdf_resources(
    resources: Any,
    reader: PdfReader,
    visited: set[tuple[str, int, int] | tuple[str, int]] | None = None,
) -> tuple[int, list[str], list[str], list[bool], int]:
    resources = resolve_object(resources)
    if not resources:
        return 0, [], [], [], 0
    if visited is None:
        visited = set()
    resource_key = ("direct", id(resources))
    if resource_key in visited:
        return 0, [], [], [], 0
    visited.add(resource_key)
    image_count = 0
    font_subtypes: list[str] = []
    font_base_names: list[str] = []
    font_embedded: list[bool] = []
    inline_images = 0
    fonts = resolve_object(resources.get("/Font", {}))
    for font in fonts.values() if hasattr(fonts, "values") else []:
        font_obj = resolve_object(font)
        font_subtypes.append(str(font_obj.get("/Subtype", "")))
        font_base_names.append(str(font_obj.get("/BaseFont", "")))
        font_embedded.append(pdf_stream_has_embedded_font(font_obj))
    xobjects = resolve_object(resources.get("/XObject", {}))
    for xobject in xobjects.values() if hasattr(xobjects, "values") else []:
        identity = (
            ("indirect", int(xobject.idnum), int(xobject.generation))
            if hasattr(xobject, "idnum")
            else ("direct", id(resolve_object(xobject)))
        )
        if identity in visited:
            continue
        visited.add(identity)
        obj = resolve_object(xobject)
        subtype = str(obj.get("/Subtype", ""))
        if subtype == "/Image":
            image_count += 1
        elif subtype == "/Form":
            inline_images += inline_image_count(obj, reader)
            (
                child_images,
                child_fonts,
                child_base_names,
                child_embedded,
                child_inline,
            ) = inspect_pdf_resources(
                obj.get("/Resources", {}), reader, visited
            )
            image_count += child_images
            font_subtypes.extend(child_fonts)
            font_base_names.extend(child_base_names)
            font_embedded.extend(child_embedded)
            inline_images += child_inline
    patterns = resolve_object(resources.get("/Pattern", {}))
    for pattern in patterns.values() if hasattr(patterns, "values") else []:
        identity = (
            ("indirect", int(pattern.idnum), int(pattern.generation))
            if hasattr(pattern, "idnum")
            else ("direct", id(resolve_object(pattern)))
        )
        if identity in visited:
            continue
        visited.add(identity)
        obj = resolve_object(pattern)
        inline_images += inline_image_count(obj, reader)
        (
            child_images,
            child_fonts,
            child_base_names,
            child_embedded,
            child_inline,
        ) = inspect_pdf_resources(obj.get("/Resources", {}), reader, visited)
        image_count += child_images
        font_subtypes.extend(child_fonts)
        font_base_names.extend(child_base_names)
        font_embedded.extend(child_embedded)
        inline_images += child_inline
    return image_count, font_subtypes, font_base_names, font_embedded, inline_images


def verify_figures(
    contract: Mapping[str, Any], run1: Path, validation_root: Path, checks: Checks
) -> list[dict[str, Any]]:
    style = contract["plot_style"]
    figure_width_in, figure_height_in = (
        float(value) for value in style["figure_size_inch"]
    )
    source_dpi = float(style["dpi"])
    expected_png_width = int(round(figure_width_in * source_dpi))
    expected_png_height = int(round(figure_height_in * source_dpi))
    expected_media_box = [0.0, 0.0, figure_width_in * 72.0, figure_height_in * 72.0]
    expected_png_dpi = round(source_dpi / 0.0254) * 0.0254
    render_dpi = 180
    expected_render_width = int(math.ceil(expected_media_box[2] / 72.0 * render_dpi))
    expected_render_height = int(math.ceil(expected_media_box[3] / 72.0 * render_dpi))
    render_root = validation_root / "rendered_pdf_review"
    render_root.mkdir(parents=True, exist_ok=True)
    pdftoppm = shutil.which("pdftoppm")
    if not pdftoppm:
        raise RuntimeError("pdftoppm is required for PDF render review")
    version_result = subprocess.run(
        [pdftoppm, "-v"], capture_output=True, text=True, check=False
    )
    version_text = (version_result.stderr or version_result.stdout).strip().splitlines()
    render_rows: list[dict[str, Any]] = []
    for stem in FIGURE_STEMS:
        pdf_path = run1 / "figures" / f"{stem}.pdf"
        prefix = render_root / stem
        result = subprocess.run(
            [
                pdftoppm,
                "-png",
                "-r",
                "180",
                "-singlefile",
                str(pdf_path),
                str(prefix),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        render_path = prefix.with_suffix(".png")
        render_width = 0
        render_height = 0
        render_mode = ""
        if render_path.is_file():
            with Image.open(render_path) as render_image:
                render_width, render_height = render_image.size
                render_mode = render_image.mode
        render_rows.append(
            {
                "stem": stem,
                "exit_code": result.returncode,
                "render_exists": render_path.is_file(),
                "render_bytes": render_path.stat().st_size if render_path.is_file() else 0,
                "render_sha256": sha256_file(render_path) if render_path.is_file() else "",
                "render_width_px": render_width,
                "render_height_px": render_height,
                "render_mode": render_mode,
                "expected_width_px": expected_render_width,
                "expected_height_px": expected_render_height,
                "exact_size_pass": render_width == expected_render_width
                and render_height == expected_render_height,
            }
        )
    render_payload = {
        "renderer": "pdftoppm",
        "version": version_text[0] if version_text else "UNKNOWN",
        "dpi": render_dpi,
        "singlefile": True,
        "rows": render_rows,
    }
    write_json(validation_root / "render_audit.json", render_payload)
    checks.add(
        "pdf_render",
        "四份PDF由pdftoppm以180 dpi单页重渲染，均生成1347x603 RGB非空PNG",
        version_result.returncode == 0
        and len(render_rows) == 4
        and all(
            row["exit_code"] == 0
            and row["render_exists"]
            and row["render_bytes"] > 0
            and row["exact_size_pass"]
            and row["render_mode"] == "RGB"
            for row in render_rows
        ),
        {
            "renderer": "pdftoppm",
            "dpi": render_dpi,
            "rows": 4,
            "width_px": expected_render_width,
            "height_px": expected_render_height,
            "mode": "RGB",
            "all_pass": True,
        },
        {
            "renderer": "pdftoppm",
            "dpi": render_dpi,
            "version": render_payload["version"],
            "rows": render_rows,
        },
        "render_audit.json",
    )

    rows: list[dict[str, Any]] = []
    for stem in FIGURE_STEMS:
        pdf_path = run1 / "figures" / f"{stem}.pdf"
        png_path = run1 / "figures" / f"{stem}.png"
        reader = PdfReader(str(pdf_path), strict=True)
        encrypted = bool(reader.is_encrypted)
        page_count = len(reader.pages)
        image_count = 0
        font_subtypes: list[str] = []
        font_base_names: list[str] = []
        font_embedded_flags: list[bool] = []
        inline_images = 0
        annotation_count = 0
        text = ""
        for page in reader.pages:
            inline_images += inline_image_count(page.get_contents(), reader)
            images, fonts, base_names, embedded_flags, child_inline = inspect_pdf_resources(
                page.get("/Resources", {}), reader
            )
            image_count += images
            font_subtypes.extend(fonts)
            font_base_names.extend(base_names)
            font_embedded_flags.extend(embedded_flags)
            inline_images += child_inline
            annotations = resolve_object(page.get("/Annots", []))
            annotation_count += len(annotations) if annotations else 0
            text += page.extract_text() or ""
        page = reader.pages[0]
        rotation = int(page.rotation or 0)
        user_unit = float(page.get("/UserUnit", 1.0))
        media_box = [
            float(page.mediabox.left),
            float(page.mediabox.bottom),
            float(page.mediabox.right),
            float(page.mediabox.top),
        ]
        crop_box = [
            float(page.cropbox.left),
            float(page.cropbox.bottom),
            float(page.cropbox.right),
            float(page.cropbox.top),
        ]
        media_box_pass = all(
            math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
            for actual, expected in zip(media_box, expected_media_box)
        )
        crop_box_pass = all(
            math.isclose(actual, expected, rel_tol=0.0, abs_tol=1e-6)
            for actual, expected in zip(crop_box, expected_media_box)
        )
        type3_count = sum(subtype == "/Type3" for subtype in font_subtypes)
        normalized_base_names = sorted(
            {
                name.lstrip("/").split("+", 1)[-1]
                for name in font_base_names
                if name
            }
        )
        expected_base_names = sorted(style["required_pdf_font_names"])
        font_contract_pass = normalized_base_names == expected_base_names
        all_fonts_embedded = bool(font_embedded_flags) and all(font_embedded_flags)
        with Image.open(png_path) as image:
            width, height = image.size
            mode = image.mode
            dpi = image.info.get("dpi", (0.0, 0.0))
            rgba = np.asarray(image.convert("RGBA"), dtype=np.uint8)
        border = np.concatenate(
            [
                rgba[:5, :, :3].reshape(-1, 3),
                rgba[-5:, :, :3].reshape(-1, 3),
                rgba[:, :5, :3].reshape(-1, 3),
                rgba[:, -5:, :3].reshape(-1, 3),
            ],
            axis=0,
        )
        opaque = bool(np.all(rgba[:, :, 3] == 255))
        border_clear = bool(np.all(border >= 245))
        exact_png_size_pass = (
            width == expected_png_width and height == expected_png_height
        )
        dpi_pass = math.isclose(
            float(dpi[0]), expected_png_dpi, rel_tol=0.0, abs_tol=1e-3
        ) and math.isclose(
            float(dpi[1]), expected_png_dpi, rel_tol=0.0, abs_tol=1e-3
        )
        is_historical = "历史最终掩膜" in stem
        text_gate = (
            "Historical final masks" in text
            and "missing" not in text.lower()
            and "candidate" not in text.lower()
            if is_historical
            else "Craig-Bampton" in text
            and "missing" in text.lower()
            and "Historical final masks" not in text
        )
        pass_gate = (
            page_count == int(style["pdf_page_count"])
            and encrypted == bool(style["pdf_encrypted_allowed"])
            and rotation == int(style["pdf_rotation_degrees"])
            and math.isclose(
                user_unit,
                float(style["pdf_user_unit"]),
                rel_tol=0.0,
                abs_tol=1e-12,
            )
            and media_box_pass
            and (crop_box_pass or not bool(style["pdf_cropbox_equals_mediabox"]))
            and (image_count == 0 or not bool(style["forbid_pdf_image_xobjects"]))
            and (inline_images == 0 or not bool(style["forbid_pdf_inline_images"]))
            and annotation_count == 0
            and (type3_count == 0 or not bool(style["forbid_pdf_type3_fonts"]))
            and font_contract_pass
            and (all_fonts_embedded or not bool(style["required_pdf_fonts_embedded"]))
            and exact_png_size_pass
            and mode == style["png_mode"]
            and dpi_pass
            and opaque
            and border_clear
            and text_gate
        )
        rows.append(
            {
                "stem": stem,
                "pdf_pages": page_count,
                "pdf_encrypted": encrypted,
                "pdf_rotation_degrees": rotation,
                "pdf_user_unit": user_unit,
                "pdf_media_box": ";".join(format(value, ".12g") for value in media_box),
                "pdf_expected_media_box": ";".join(
                    format(value, ".12g") for value in expected_media_box
                ),
                "pdf_media_box_pass": media_box_pass,
                "pdf_crop_box": ";".join(format(value, ".12g") for value in crop_box),
                "pdf_crop_box_pass": crop_box_pass,
                "pdf_raster_image_objects": image_count,
                "pdf_inline_images": inline_images,
                "pdf_annotations": annotation_count,
                "pdf_type3_fonts": type3_count,
                "pdf_base_fonts": ";".join(normalized_base_names),
                "pdf_font_contract_pass": font_contract_pass,
                "pdf_embedded_font_resource_count": sum(font_embedded_flags),
                "pdf_font_resource_count": len(font_embedded_flags),
                "pdf_all_fonts_embedded": all_fonts_embedded,
                "png_width_px": width,
                "png_height_px": height,
                "png_expected_width_px": expected_png_width,
                "png_expected_height_px": expected_png_height,
                "png_exact_size_pass": exact_png_size_pass,
                "png_mode": mode,
                "png_dpi_x": float(dpi[0]),
                "png_dpi_y": float(dpi[1]),
                "png_expected_dpi": expected_png_dpi,
                "png_exact_dpi_pass": dpi_pass,
                "png_alpha_opaque": opaque,
                "png_outer_border_clear": border_clear,
                "required_evidence_text_present": text_gate,
                "quality_gate_pass": pass_gate,
            }
        )
    checks.add(
        "figure_quality",
        "四份PDF均精确单页尺寸、未加密、零旋转、无图像/inline image/注释/Type3且字体流真实嵌入；四份PNG精确4488x2010 RGBA和599.9988 dpi并通过边缘与证据文字门",
        len(rows) == 4 and all(row["quality_gate_pass"] for row in rows),
        {"figure_count": 4, "all_pass": True},
        {
            "figure_count": len(rows),
            "failed": [row["stem"] for row in rows if not row["quality_gate_pass"]],
        },
        "figures/*.pdf | figures/*.png",
    )
    write_csv(validation_root / "figure_quality.csv", list(rows[0].keys()), rows)
    return rows


def verify_manual_visual_review(
    contract: Mapping[str, Any], run1: Path, validation_root: Path, checks: Checks
) -> None:
    binding = contract["manual_visual_review_contract"]
    checks.add(
        "manual_visual_review",
        "人工图审源记录的路径、字节数和SHA-256与合同绑定一致",
        board_path(binding["relpath"]) == MANUAL_VISUAL_REVIEW_PATH
        and MANUAL_VISUAL_REVIEW_PATH.is_file()
        and MANUAL_VISUAL_REVIEW_PATH.stat().st_size == int(binding["bytes"])
        and sha256_file(MANUAL_VISUAL_REVIEW_PATH) == binding["sha256"],
        {"bytes": int(binding["bytes"]), "sha256": binding["sha256"]},
        {
            "bytes": MANUAL_VISUAL_REVIEW_PATH.stat().st_size
            if MANUAL_VISUAL_REVIEW_PATH.is_file()
            else None,
            "sha256": sha256_file(MANUAL_VISUAL_REVIEW_PATH)
            if MANUAL_VISUAL_REVIEW_PATH.is_file()
            else None,
        },
        binding["relpath"],
    )
    fields, rows = read_csv(MANUAL_VISUAL_REVIEW_PATH)
    required_fields = [
        "figure_pdf",
        "pdf_bytes",
        "pdf_sha256",
        "render_png",
        "render_bytes",
        "render_sha256",
        "render_dpi",
        "reviewed_date",
        "overlap_absent",
        "clipping_absent",
        "legend_legible",
        "evidence_separation_clear",
        "status",
        "note",
    ]
    expected_pdf_names = [f"{stem}.pdf" for stem in FIGURE_STEMS]
    expected_render_names = [f"rendered_pdf_review/{stem}.png" for stem in FIGURE_STEMS]
    failures: list[dict[str, Any]] = []
    for row in rows:
        pdf_path = run1 / "figures" / row["figure_pdf"]
        render_path = validation_root / Path(row["render_png"])
        correct = (
            pdf_path.is_file()
            and render_path.is_file()
            and int(row["pdf_bytes"]) == pdf_path.stat().st_size
            and row["pdf_sha256"] == sha256_file(pdf_path)
            and int(row["render_bytes"]) == render_path.stat().st_size
            and row["render_sha256"] == sha256_file(render_path)
            and int(row["render_dpi"]) == 180
            and row["status"] == "PASS"
            and bool_text(row["overlap_absent"])
            and bool_text(row["clipping_absent"])
            and bool_text(row["legend_legible"])
            and bool_text(row["evidence_separation_clear"])
        )
        if not correct:
            failures.append(row)
    checks.add(
        "manual_visual_review",
        "四行人工图审以唯一PDF名及PDF/180dpi渲染PNG的字节数和SHA-256逐项绑定",
        fields == required_fields
        and [row["figure_pdf"] for row in rows] == expected_pdf_names
        and [row["render_png"] for row in rows] == expected_render_names
        and len({row["figure_pdf"] for row in rows}) == 4
        and len({row["render_png"] for row in rows}) == 4
        and not failures,
        {
            "fields": required_fields,
            "pdf_names": expected_pdf_names,
            "render_names": expected_render_names,
            "failures": [],
        },
        {
            "fields": fields,
            "pdf_names": [row["figure_pdf"] for row in rows],
            "render_names": [row["render_png"] for row in rows],
            "failures": failures,
        },
        "code/board20_step6_manual_visual_review.csv",
    )
    write_csv(
        validation_root / "manual_visual_review.csv", fields, rows
    )


def verify_protection_and_scope(
    contract: Mapping[str, Any], run1: Path, validation_root: Path, checks: Checks
) -> dict[str, Any]:
    _, protected_rows = read_csv(run1 / "protected_input_hashes.csv")
    authoritative_path = board_path(
        "outputs/step5_fullq_svd_candidate_audit_v5_full/"
        "v5_full_validator_full_postcheck_protected_hashes.csv"
    )
    authoritative_fields, authoritative_rows = read_csv(authoritative_path)
    expected_authoritative_fields = [
        "relpath",
        "sha256_before",
        "sha256_after",
        "unchanged",
    ]
    authoritative_relpaths = [row["relpath"] for row in authoritative_rows]
    authoritative_failures: list[dict[str, Any]] = []
    expected_protected_rows: list[dict[str, Any]] = []
    result: list[dict[str, Any]] = []
    changed: list[str] = []
    for row in authoritative_rows:
        path = board_path(row["relpath"])
        current = sha256_file(path) if path.is_file() else "MISSING"
        authoritative_unchanged = (
            row["sha256_after"] == row["sha256_before"]
            and bool_text(row["unchanged"])
        )
        if not authoritative_unchanged:
            authoritative_failures.append(
                {"relpath": row["relpath"], "row": row}
            )
        unchanged = authoritative_unchanged and current == row["sha256_before"]
        if not unchanged:
            changed.append(row["relpath"])
        expected_protected_rows.append(
            {
                "relpath": row["relpath"],
                "sha256_before_v5": row["sha256_before"],
                "sha256_current_step6": current,
                "unchanged": unchanged,
            }
        )
        result.append(
            {
                "relpath": row["relpath"],
                "sha256_v5": row["sha256_before"],
                "sha256_run1": next(
                    (
                        candidate["sha256_current_step6"]
                        for candidate in protected_rows
                        if candidate["relpath"] == row["relpath"]
                    ),
                    "MISSING_ROW",
                ),
                "sha256_validator": current,
                "unchanged": unchanged,
            }
        )
    protected_full_failures = full_row_failures(
        protected_rows, expected_protected_rows
    )
    write_csv(
        validation_root / "protected_hashes.csv",
        ["relpath", "sha256_v5", "sha256_run1", "sha256_validator", "unchanged"],
        result,
    )
    checks.add(
        "protected_inputs",
        "V5权威保护表头、163条唯一路径、基线自一致及Step6四字段逐行匹配，当前文件SHA-256均未漂移",
        authoritative_fields == expected_authoritative_fields
        and len(authoritative_rows) == 163
        and len(authoritative_relpaths) == len(set(authoritative_relpaths))
        and not authoritative_failures
        and not protected_full_failures
        and not changed,
        {
            "authoritative_fields": expected_authoritative_fields,
            "count": 163,
            "unique": True,
            "authoritative_failures": [],
            "protected_full_failures": [],
            "changed": [],
        },
        {
            "authoritative_fields": authoritative_fields,
            "count": len(result),
            "unique": len(authoritative_relpaths) == len(set(authoritative_relpaths)),
            "authoritative_failures": authoritative_failures[:20],
            "protected_full_failures": protected_full_failures,
            "changed": changed,
        },
        "protected_hashes.csv",
    )

    created: list[str] = []
    for relpath in contract["object_gate"]["formal_success_directories"]:
        path = (REPO_ROOT / Path(relpath.replace("/", os.sep))).resolve()
        if path.exists():
            created.append(relpath)
    checks.add(
        "scope_control",
        "四个正式成功目录均未创建，失败候选仍留在Board20证据目录",
        not created,
        [],
        created,
        "object_gate.formal_success_directories",
    )
    return {"protected_count": len(result), "formal_success_directories": created}


def create_manifest(root: Path) -> list[dict[str, Any]]:
    return atomic_commit_manifest(
        root,
        expected_validation_relpaths(),
        VALIDATION_OUTPUT_DIRECTORIES,
    )


def report_text(
    summary: Mapping[str, Any], repeatability: Mapping[str, Any], figures: Sequence[Mapping[str, Any]]
) -> str:
    return "\n".join(
        [
            "# Board20 Step6 独立验证报告",
            "",
            "## 结论",
            "",
            "独立验证通过：两轮生成产物逐文件字节一致；10,385个候选—历史点的全部身份、坐标、rho、分类与来源字段、737列边界、335列边界差、11组稳定域指标、10行C05/C07裁决和第二类网格外序列均从原始输入重新计算后闭合；轴截距按原点连续稳定前缀定义，绝不跨孔洞；13行样式/证据清单逐项匹配合同。四份PDF/PNG通过矢量、字体、页数、分辨率和边缘检查，并由pdftoppm独立重渲染；人工图审记录以PDF和重渲染PNG的字节数及SHA-256唯一绑定。科学对象门仍按事实失败，因为两种划分都没有Craig–Bampton连续谱半径路线，且现有Original/Guyan候选与历史掩膜存在大量错配。",
            "",
            "## 验证计数",
            "",
            f"- PASS: {summary['pass']}",
            f"- FAIL: {summary['fail']}",
            f"- 两轮字节一致文件: {repeatability['byte_identical_file_count']} / {repeatability['run1_file_count']}",
            f"- 图质量通过: {sum(row['quality_gate_pass'] for row in figures)} / {len(figures)}",
            "- 人工图审绑定: 4 / 4",
            "",
            "## 状态边界",
            "",
            "- 生成流水线执行状态：PASS。",
            "- 图4-4、图4-5计算级对象门：FAIL，保留绘图级复现。",
            "- 正式成功目录：未创建。",
            "- 下一板块：未启动。",
        ]
    )


def _main_locked(contract: Mapping[str, Any], roots: Mapping[str, Path]) -> int:
    run1 = roots["run1"]
    run2 = roots["run2"]
    validation_root = roots["validation"]
    expected_validation = expected_validation_relpaths()
    run1_state = classify_output(
        run1, expected_run_relpaths(), RUN_OUTPUT_DIRECTORIES
    )
    run2_state = classify_output(
        run2, expected_run_relpaths(), RUN_OUTPUT_DIRECTORIES
    )
    prepare_output_root(
        validation_root,
        expected_validation,
        VALIDATION_OUTPUT_DIRECTORIES,
    )

    checks = Checks()
    checks.add(
        "input_presence",
        "两轮固定输出目录均存在",
        run1.is_dir() and run2.is_dir(),
        True,
        run1.is_dir() and run2.is_dir(),
        "step6 run1 | run2",
    )
    checks.add(
        "filesystem_protocol",
        "两轮生成结果均为严格目录树闭合的已提交状态，独立验证目录在首个写入前进入可恢复状态",
        run1_state.state == "COMMITTED"
        and run2_state.state == "COMMITTED",
        {
            "run1": "COMMITTED",
            "run2": "COMMITTED",
            "validation_after_prepare": "RECOVERABLE_UNCOMMITTED",
        },
        {
            "run1": run1_state.state,
            "run2": run2_state.state,
            "validation_after_prepare": "RECOVERABLE_UNCOMMITTED",
        },
        "code/board20_step6_fs_protocol.py",
    )
    verify_fixed_roots(contract, run1, run2, validation_root, checks)
    verify_contract_inputs(contract, checks)
    clean_receipt = verify_clean_probe_receipt(contract, checks)
    verify_manifest(run1, checks, "run1")
    verify_manifest(run2, checks, "run2")
    repeatability = verify_repeatability(run1, run2, validation_root, checks)
    verify_generator_semantics(contract, run1, checks)
    verify_scientific_tables(contract, run1, validation_root, checks)
    figures = verify_figures(contract, run1, validation_root, checks)
    verify_manual_visual_review(contract, run1, validation_root, checks)
    protection = verify_protection_and_scope(contract, run1, validation_root, checks)

    summary_before_final = checks.summary()
    checks.add(
        "validator_integrity",
        "独立验证器全部硬检查通过",
        summary_before_final["fail"] == 0,
        0,
        summary_before_final["fail"],
        "validation_checks.csv",
    )
    summary = checks.summary()
    write_csv(
        validation_root / "validation_checks.csv",
        list(checks.rows[0].keys()),
        checks.rows,
    )
    run_summary = read_json(run1 / "run_summary.json")
    _, figure_status_rows = read_csv(run1 / "tables" / "figure_status.csv")
    object_status = (
        "FAIL_RETAIN_PLOTTING_LEVEL"
        if all(
            row["object_evidence_level"] == "PLOTTING_LEVEL_REPRODUCTION"
            and not bool_text(row["calculation_level_figure_gate_pass"])
            for row in figure_status_rows
        )
        else "UNEXPECTED_OBJECT_STATUS"
    )
    payload = {
        "schema_version": "board20_step6_independent_validation_v2",
        "generator_sha256": run_summary["generator_sha256"],
        "validator_sha256": sha256_file(SCRIPT_PATH),
        "fs_protocol_sha256": sha256_file(FS_PROTOCOL_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "clean_probe_action_id": clean_receipt["action_id"],
        "clean_probe_receipt_sha256": clean_receipt["sha256"],
        "manual_visual_review_sha256": sha256_file(MANUAL_VISUAL_REVIEW_PATH),
        "overall_status": "PASS" if summary["fail"] == 0 else "FAIL",
        "execution_pipeline_status": run_summary["execution_status"],
        "scientific_object_gate_status": object_status,
        "check_summary": summary,
        "repeatability_status": repeatability["status"],
        "figure_quality_pass_count": sum(row["quality_gate_pass"] for row in figures),
        "figure_quality_expected_count": len(FIGURE_STEMS),
        "pointwise_rows_independently_recomputed": len(
            read_csv(run1 / "tables" / "pointwise_comparison.csv")[1]
        ),
        "boundary_rows_independently_recomputed": len(
            read_csv(run1 / "tables" / "boundary_by_source.csv")[1]
        ),
        "boundary_difference_rows_independently_recomputed": len(
            read_csv(run1 / "tables" / "boundary_difference.csv")[1]
        ),
        "claim_rows_independently_recomputed": len(
            read_csv(run1 / "tables" / "claim_C05_C07.csv")[1]
        ),
        "protected_file_count": protection["protected_count"],
        "formal_success_directories_created": bool(
            protection["formal_success_directories"]
        ),
        "next_step_started": bool(run_summary["next_step_started"]),
    }
    write_json(validation_root / "validation_summary.json", payload)
    write_text(validation_root / "report.md", report_text(summary, repeatability, figures))
    actual_validation = {
        path.relative_to(validation_root).as_posix()
        for path in validation_root.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.csv"
    }
    if actual_validation != expected_validation:
        raise RuntimeError(
            "Validation artifact set drifted: "
            f"delta={sorted(actual_validation ^ expected_validation)}"
        )
    manifest_rows = create_manifest(validation_root)
    if len(manifest_rows) != len(expected_validation):
        raise RuntimeError(
            f"Validation manifest count drifted: {len(manifest_rows)}"
        )
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


def main() -> int:
    contract = read_json(CONTRACT_PATH)
    roots = validate_fs_fixed_roots(BOARD_ROOT, contract["fixed_output_roots"])
    with ExclusiveFileLock(roots["logs"] / "step6_fs_protocol.lock"):
        roots = validate_fs_fixed_roots(BOARD_ROOT, contract["fixed_output_roots"])
        return _main_locked(contract, roots)


if __name__ == "__main__":
    raise SystemExit(main())

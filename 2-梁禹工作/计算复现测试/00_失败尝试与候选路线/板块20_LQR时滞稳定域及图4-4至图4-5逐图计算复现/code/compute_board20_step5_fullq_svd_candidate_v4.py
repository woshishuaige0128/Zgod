#!/usr/bin/env python
"""Board20 Step-5 fourth isolated full-q/SVD candidate.

Every numerical operation is identical to sealed V3.  V4 repairs only one
metadata defect: ``write_route_outputs`` now expands checkpoint identity before
writing the explicit route-status schema, so identity cannot overwrite it.
V3 scientific files are never parsed, copied, or resumed; V3/V2/compact-failure
evidence is opened only as uninterpreted bytes for SHA-256 immutability checks.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import h5py
import numpy as np
import scipy.linalg as sla
from scipy.optimize import linear_sum_assignment

import compute_board20_step5_independent as base
import compute_board20_step5_fullq_candidate as v2engine


SCRIPT_FILENAME = "compute_board20_step5_fullq_svd_candidate_v4.py"
CONTRACT_FILENAME = "board20_step5_fullq_svd_candidate_v4_contract.json"
MANIFEST_FILENAME = "board20_step4_route_manifest.json"
BASE_COMPUTE_FILENAME = "compute_board20_step5_independent.py"
V2_ENGINE_FILENAME = "compute_board20_step5_fullq_candidate.py"
V3_REFERENCE_FILENAME = "compute_board20_step5_fullq_svd_candidate.py"

NUMERIC_AST_EQUIVALENCE_FUNCTIONS = (
    "selected_algorithm",
    "prepared_terms",
    "scale_normalized_svd_residual",
    "solve_spectrum",
    "deterministic_physical_pairing",
    "empty_root_data",
    "root_data",
    "optional_max",
    "solve_point",
)
PROTECTED_EVIDENCE_GROUPS = (
    "protected_v3_scientific_files",
    "protected_v3_failure_audit_files",
    "protected_v2_failure_audit_files",
    "protected_compact_failure_files",
)

ALGORITHM_FULL_Q = "FULL_Q_ORDINARY_HISTORY_COMPANION"
ALGORITHM_COMPACT = "COMPACT_SCALAR_DELAY_AUGMENTATION"

CSV_FIELDS = [
    "route_id", "route_role", "declared_method", "division", "route_formula",
    "l", "j", "matrix_order", "algorithm_selector_field",
    "algorithm_selector_value", "selected_algorithm", "selected_order",
    "compact_order", "full_q_order", "polynomial_degree", "clearing_power",
    "raw_root_count", "finite_root_count", "nonfinite_root_count",
    "zero_root_tolerance", "removed_zero_root_count", "retained_root_count",
    "compact_pairing_performed", "compact_raw_root_count",
    "compact_retained_root_count", "compact_zero_root_tolerance",
    "compact_removed_zero_root_count", "rho_compact_pairing",
    "stable_compact_pairing", "full_q_compact_rho_abs_diff",
    "full_q_compact_root_match_max_relative_diff",
    "near_unit_root_match_max_relative_diff", "pairing_diagnostic_role",
    "matched_physical_root_count", "theoretical_extra_zero_count",
    "unmatched_full_root_count", "unmatched_count_within_theoretical",
    "unmatched_full_max_abs", "unmatched_full_below_0p9",
    "unmatched_full_strictly_nondominant", "origin_splitting_status",
    "origin_split_gate_role", "rho", "stable", "critical",
    "dominant_root_real", "dominant_root_imag",
    "max_gated_svd_polynomial_residual",
    "max_gated_svd_laurent_residual",
    "max_gated_vector_block_polynomial_residual_diagnostic",
    "max_gated_vector_block_laurent_residual_diagnostic",
    "max_unmatched_full_svd_polynomial_residual_diagnostic",
    "max_unmatched_full_svd_laurent_residual_diagnostic",
    "max_unmatched_full_vector_block_polynomial_residual_diagnostic",
    "max_unmatched_full_vector_block_laurent_residual_diagnostic",
    "max_near_unit_svd_polynomial_residual",
    "max_near_unit_svd_laurent_residual",
    "max_near_unit_vector_block_polynomial_residual_diagnostic",
    "max_near_unit_vector_block_laurent_residual_diagnostic",
    "dominant_svd_polynomial_residual", "dominant_svd_laurent_residual",
    "dominant_vector_block_polynomial_residual_diagnostic",
    "dominant_vector_block_laurent_residual_diagnostic",
    "hard_residual_definition", "vector_block_residual_role",
    "direct_formula_coefficient_relative_difference",
    "stable_classification_match", "all_gated_svd_residuals_finite",
    "point_status", "failure_code",
]

STRING_FIELDS = {
    "route_id", "route_role", "declared_method", "division", "route_formula",
    "algorithm_selector_field", "selected_algorithm", "pairing_diagnostic_role",
    "origin_splitting_status", "origin_split_gate_role",
    "hard_residual_definition", "vector_block_residual_role",
    "point_status", "failure_code",
}
BOOL_FIELDS = {
    "stable", "critical", "compact_pairing_performed",
    "stable_compact_pairing", "unmatched_count_within_theoretical",
    "unmatched_full_below_0p9", "unmatched_full_strictly_nondominant",
    "stable_classification_match", "all_gated_svd_residuals_finite",
}
INT_FIELDS = {
    "l", "j", "matrix_order", "algorithm_selector_value", "selected_order",
    "compact_order", "full_q_order", "polynomial_degree", "clearing_power",
    "raw_root_count", "finite_root_count", "nonfinite_root_count",
    "removed_zero_root_count", "retained_root_count", "compact_raw_root_count",
    "compact_retained_root_count", "compact_removed_zero_root_count",
    "matched_physical_root_count", "theoretical_extra_zero_count",
    "unmatched_full_root_count",
}
RUNTIME_FIELDS = ("route_id", "l", "j", "elapsed_seconds", "point_status")

HARD_RESIDUAL_LABEL = (
    "SIGMA_MIN_DIRECT_MATRIX_OVER_SUM_SPECTRAL_NORM_WEIGHT"
)
VECTOR_ROLE = "DIAGNOSTIC_ONLY_VECTOR_BLOCK_CONDITIONING"
PAIRING_ROLE = "DIAGNOSTIC_ONLY_KNOWN_COMPACT_CONDITIONING"


@dataclass(frozen=True)
class Context:
    root: Path
    contract: dict[str, Any]
    manifest: dict[str, Any]
    specs: tuple[base.RouteSpec, ...]


@dataclass
class RootData:
    roots: np.ndarray
    svd_polynomial_residual: np.ndarray
    svd_laurent_residual: np.ndarray
    vector_block_polynomial_residual: np.ndarray
    vector_block_laurent_residual: np.ndarray
    finite: np.ndarray
    removed_as_zero: np.ndarray
    matched_physical: np.ndarray
    unmatched_full: np.ndarray
    paired_other_retained_index: np.ndarray
    pair_relative_distance: np.ndarray


@dataclass
class Spectrum:
    raw_roots: np.ndarray
    raw_svd_poly: np.ndarray
    raw_svd_laurent: np.ndarray
    raw_vector_poly: np.ndarray
    raw_vector_laurent: np.ndarray
    raw_finite: np.ndarray
    raw_removed: np.ndarray
    retained_indices: np.ndarray
    retained_roots: np.ndarray
    retained_svd_poly: np.ndarray
    retained_svd_laurent: np.ndarray
    retained_vector_poly: np.ndarray
    retained_vector_laurent: np.ndarray
    zero_tolerance: float
    removed_count: int
    rho: float
    stable: bool
    critical: bool
    dominant_index: int
    dominant_root: complex


@dataclass
class CandidatePoint:
    summary: dict[str, Any]
    selected_raw: RootData
    selected_retained: RootData
    pairing_compact_raw: RootData
    pairing_compact_retained: RootData
    elapsed_seconds: float


def code_root() -> Path:
    return Path(__file__).resolve().parent


def board_root() -> Path:
    return code_root().parent


def output_root() -> Path:
    return board_root() / "outputs" / "step5_fullq_svd_candidate_v4"


def log_root() -> Path:
    return board_root() / "logs" / "step5_fullq_svd_candidate_v4"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def json_safe(value: Any) -> Any:
    return v2engine.json_safe(value)


def append_check(
    checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "PASS" if passed else "FAIL",
            "detail": json_safe(detail),
        }
    )


def selected_algorithm(matrix_order: int) -> str:
    return ALGORITHM_FULL_Q if matrix_order <= 5 else ALGORITHM_COMPACT


def safe_board_relpath(relpath: str) -> Path:
    candidate = (board_root() / relpath).resolve()
    root = board_root().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Path escapes board root: {relpath}") from exc
    return candidate


def safe_workspace(root: Path, relpath: str) -> Path:
    return base.safe_relative_path(root, relpath, "outputs/step2_runs")


def matrix_payload_sha256(matrices: base.Matrices) -> str:
    return v2engine.matrix_payload_sha256(matrices)


def load_context() -> Context:
    root = board_root()
    contract = read_json(code_root() / CONTRACT_FILENAME)
    if contract.get("schema_version") != "board20_step5_fullq_svd_candidate_v4_contract_v4":
        raise ValueError("Unexpected V4 candidate contract schema.")
    manifest_path = code_root() / MANIFEST_FILENAME
    base_path = code_root() / BASE_COMPUTE_FILENAME
    v2_path = code_root() / V2_ENGINE_FILENAME
    v3_reference_path = code_root() / V3_REFERENCE_FILENAME
    if Path(base.__file__).resolve() != base_path.resolve():
        raise ValueError("Imported base compute module is not the sealed local file.")
    if Path(v2engine.__file__).resolve() != v2_path.resolve():
        raise ValueError("Imported V2 engine module is not the sealed local file.")
    if sha256_file(manifest_path) != contract["route_manifest_sha256"]:
        raise ValueError("Route-identity manifest SHA-256 mismatch.")
    if sha256_file(base_path) != contract["base_compute_sha256"]:
        raise ValueError("Immutable base compute SHA-256 mismatch.")
    if sha256_file(v2_path) != contract["v2_engine_sha256"]:
        raise ValueError("Immutable V2 engine SHA-256 mismatch.")
    if sha256_file(v3_reference_path) != contract["v3_reference_script_sha256"]:
        raise ValueError("Immutable V3 reference script SHA-256 mismatch.")
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != "board20_step4_route_manifest_v1":
        raise ValueError("Unexpected route manifest schema.")

    manifest_routes = {item["route_id"]: item for item in manifest["routes"]}
    contract_routes = list(contract["routes"])
    ids = [item["route_id"] for item in contract_routes]
    if len(ids) != 5 or set(ids) != set(manifest_routes):
        raise ValueError("V4 route identity is not exactly the sealed five routes.")

    specs: list[base.RouteSpec] = []
    for item in contract_routes:
        route_id = item["route_id"]
        source = manifest_routes[route_id]
        for field in (
            "route_role", "declared_method", "division", "route_formula",
            "workspace_relpath",
        ):
            if source[field] != item[field]:
                raise ValueError(f"Manifest/contract mismatch: {route_id}.{field}")
        restored_map = {
            logical: source["matrix_variable_map"][logical]
            for logical in item["matrix_variables"]
        }
        if restored_map != item["matrix_variables"]:
            raise ValueError(f"Manifest/contract matrix map mismatch: {route_id}")
        workspaces = [
            entry for entry in source["file_contracts"]
            if entry.get("role") == "workspace_complete"
        ]
        if len(workspaces) != 1 or workspaces[0]["sha256"] != item["workspace_sha256"]:
            raise ValueError(f"Manifest workspace seal mismatch: {route_id}")
        workspace = safe_workspace(root, item["workspace_relpath"])
        if not workspace.is_file() or sha256_file(workspace) != item["workspace_sha256"]:
            raise ValueError(f"Sealed workspace changed or is missing: {route_id}")
        pilot = tuple(
            tuple(map(int, pair)) for pair in contract["pilot_points"][route_id]
        )
        specs.append(
            base.RouteSpec(
                route_id=route_id,
                route_name=source["route_name"],
                route_role=item["route_role"],
                declared_method=item["declared_method"],
                division=item["division"],
                route_formula=item["route_formula"],
                workspace_relpath=item["workspace_relpath"],
                workspace_sha256=item["workspace_sha256"],
                matrix_variables=dict(item["matrix_variables"]),
                delay_dofs=tuple(
                    index - 1 for index in item["delay_dofs_matlab_1_based"]
                ),
                pilot_points=pilot,
            )
        )
    return Context(root=root, contract=contract, manifest=manifest, specs=tuple(specs))


def observed_protected_v2_hashes(context: Context) -> dict[str, str]:
    observed: dict[str, str] = {}
    for item in context.contract["protected_v2_files"]:
        path = safe_board_relpath(item["relpath"])
        if not path.is_file():
            observed[item["relpath"]] = "MISSING"
        else:
            observed[item["relpath"]] = sha256_file(path)
    return observed


def expected_protected_v2_hashes(context: Context) -> dict[str, str]:
    return {
        item["relpath"]: item["sha256"]
        for item in context.contract["protected_v2_files"]
    }


def observed_contract_hash_group(
    context: Context, group_name: str
) -> dict[str, str]:
    observed: dict[str, str] = {}
    for item in context.contract[group_name]:
        path = safe_board_relpath(item["relpath"])
        observed[item["relpath"]] = sha256_file(path) if path.is_file() else "MISSING"
    return observed


def expected_contract_hash_group(
    context: Context, group_name: str
) -> dict[str, str]:
    return {
        item["relpath"]: item["sha256"]
        for item in context.contract[group_name]
    }


def protected_evidence_snapshot(context: Context) -> dict[str, dict[str, str]]:
    return {
        group: observed_contract_hash_group(context, group)
        for group in PROTECTED_EVIDENCE_GROUPS
    }


def expected_protected_evidence(context: Context) -> dict[str, dict[str, str]]:
    return {
        group: expected_contract_hash_group(context, group)
        for group in PROTECTED_EVIDENCE_GROUPS
    }


def function_ast_sha256(path: Path, names: Sequence[str]) -> dict[str, str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    functions = {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    missing = [name for name in names if name not in functions]
    if missing:
        raise ValueError(f"Missing functions in AST comparison: {missing}")
    return {
        name: hashlib.sha256(
            ast.dump(
                functions[name], annotate_fields=True, include_attributes=False
            ).encode("utf-8")
        ).hexdigest().upper()
        for name in names
    }


def route_status_merge_positions(path: Path) -> dict[str, int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "write_route_outputs"
    )
    for node in ast.walk(target):
        if (
            isinstance(node, ast.Assign)
            and any(isinstance(item, ast.Name) and item.id == "status" for item in node.targets)
            and isinstance(node.value, ast.Dict)
        ):
            schema_index = next(
                index
                for index, key in enumerate(node.value.keys)
                if isinstance(key, ast.Constant) and key.value == "schema_version"
            )
            identity_unpack_index = next(
                index
                for index, (key, value) in enumerate(
                    zip(node.value.keys, node.value.values)
                )
                if key is None and isinstance(value, ast.Name) and value.id == "identity"
            )
            return {
                "identity_unpack_index": identity_unpack_index,
                "schema_version_index": schema_index,
            }
    raise ValueError("route_status dictionary AST was not found.")


def static_diff_selftest(context: Context) -> dict[str, Any]:
    names = tuple(context.contract["change_whitelist"][
        "numeric_ast_must_be_identical_functions"
    ])
    v3_path = code_root() / V3_REFERENCE_FILENAME
    v4_path = code_root() / SCRIPT_FILENAME
    v3_numeric = function_ast_sha256(v3_path, names)
    v4_numeric = function_ast_sha256(v4_path, names)
    v3_merge = route_status_merge_positions(v3_path)
    v4_merge = route_status_merge_positions(v4_path)
    numeric_equal = v3_numeric == v4_numeric
    v3_bug_present = (
        v3_merge["schema_version_index"] < v3_merge["identity_unpack_index"]
    )
    v4_fix_present = (
        v4_merge["identity_unpack_index"] < v4_merge["schema_version_index"]
    )
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_static_diff_v4",
        "status": (
            "PASS" if numeric_equal and v3_bug_present and v4_fix_present else "FAIL"
        ),
        "v3_reference_script_sha256": sha256_file(v3_path),
        "v4_candidate_script_sha256": sha256_file(v4_path),
        "numeric_function_ast_equal": numeric_equal,
        "numeric_function_ast_sha256_v3": v3_numeric,
        "numeric_function_ast_sha256_v4": v4_numeric,
        "v3_route_status_merge_positions": v3_merge,
        "v4_route_status_merge_positions": v4_merge,
        "only_functional_change": context.contract["change_whitelist"][
            "only_functional_change"
        ],
        "change_whitelist_sha256": sha256_json(
            context.contract["change_whitelist"]
        ),
    }


def build_input_seal(context: Context) -> dict[str, Any]:
    matrices = {
        spec.route_id: base.load_route_matrices(context.root, spec)
        for spec in context.specs
    }
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_input_seal_v4",
        "candidate_script_sha256": sha256_file(code_root() / SCRIPT_FILENAME),
        "candidate_contract_sha256": sha256_file(code_root() / CONTRACT_FILENAME),
        "route_manifest_sha256": sha256_file(code_root() / MANIFEST_FILENAME),
        "base_compute_sha256": sha256_file(code_root() / BASE_COMPUTE_FILENAME),
        "v2_engine_sha256": sha256_file(code_root() / V2_ENGINE_FILENAME),
        "v3_reference_script_sha256": sha256_file(
            code_root() / V3_REFERENCE_FILENAME
        ),
        "algorithm_selection_sha256": sha256_json(
            context.contract["algorithm_selection"]
        ),
        "root_policy_sha256": sha256_json(
            context.contract["root_and_pairing_policy"]
        ),
        "hard_residual_math_sha256": sha256_json(
            context.contract["hard_residual_math"]
        ),
        "numeric_gates_sha256": sha256_json(context.contract["numeric_gates"]),
        "protected_v2_file_sha256": observed_protected_v2_hashes(context),
        "protected_evidence_sha256": protected_evidence_snapshot(context),
        "static_diff_selftest_sha256": sha256_json(static_diff_selftest(context)),
        "workspace_sha256": {
            spec.route_id: spec.workspace_sha256 for spec in context.specs
        },
        "matrix_payload_sha256": {
            route_id: matrix_payload_sha256(value)
            for route_id, value in matrices.items()
        },
        "route_order": [spec.route_id for spec in context.specs],
    }


def verify_input_seal() -> tuple[Context, dict[str, Any]]:
    context = load_context()
    path = output_root() / "input_seal.json"
    if not path.is_file():
        raise FileNotFoundError("Run PASS preflight to create the V4 input seal.")
    observed = read_json(path)
    expected = build_input_seal(context)
    if observed != expected:
        raise RuntimeError(
            "V4 code/contract/dependency/workspace or protected evidence identity changed."
        )
    return context, observed


def v2_immutability_document(
    context: Context, phase: str, before: Mapping[str, str] | None = None
) -> dict[str, Any]:
    expected = expected_protected_v2_hashes(context)
    after = observed_protected_v2_hashes(context)
    before_map = dict(after if before is None else before)
    passed = after == expected and before_map == expected and after == before_map
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_v2_immutability_v4",
        "phase": phase,
        "status": "PASS" if passed else "FAIL",
        "v2_status": "PERMANENT_FAIL_IMMUTABLE",
        "audit_mode": "UNINTERPRETED_BYTES_SHA256_ONLY",
        "expected_sha256": expected,
        "before_sha256": before_map,
        "after_sha256": after,
        "all_expected_and_unchanged": passed,
    }


def protected_evidence_immutability_document(
    context: Context,
    phase: str,
    before: Mapping[str, Mapping[str, str]] | None = None,
) -> dict[str, Any]:
    expected = expected_protected_evidence(context)
    after = protected_evidence_snapshot(context)
    before_map = after if before is None else {
        group: dict(values) for group, values in before.items()
    }
    passed = after == expected and before_map == expected and after == before_map
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_protected_evidence_v4",
        "phase": phase,
        "status": "PASS" if passed else "FAIL",
        "audit_mode": "UNINTERPRETED_BYTES_SHA256_ONLY",
        "v3_status": "PERMANENT_VALIDATOR_FAIL_IMMUTABLE",
        "expected_sha256": expected,
        "before_sha256": before_map,
        "after_sha256": after,
        "all_expected_and_unchanged": passed,
    }


def contracts_status(context: Context) -> dict[str, Any]:
    failed_manifest = {
        item["route_id"]: item for item in context.manifest["failed_routes"]
    }
    failed = []
    for item in context.contract["noncomputable_failed_routes"]:
        source = failed_manifest[item["route_id"]]
        failed.append(
            {
                **item,
                "manifest_execution_status": source["execution_status"],
                "manifest_rho_grid_policy": source["rho_grid_policy"],
            }
        )
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_contracts_status_v4",
        "scientific_contracts": context.contract["scientific_contracts"],
        "noncomputable_failed_routes": failed,
        "v2_candidate_status": "PERMANENT_FAIL_IMMUTABLE",
        "v3_candidate_status": "PERMANENT_VALIDATOR_FAIL_IMMUTABLE",
        "v3_scientific_output_reuse_policy": "FORBIDDEN",
        "v3_not_gate_relaxation_statement": context.contract[
            "not_gate_relaxation_statement"
        ],
        "candidate_output_policy": (
            "Only the five calculable route IDs may receive route directories."
        ),
    }


def run_preflight() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        context = load_context()
        contract = context.contract
        append_check(checks, "candidate_contract_schema", True, contract["schema_version"])
        append_check(checks, "route_manifest_hash", True, contract["route_manifest_sha256"])
        append_check(checks, "base_compute_hash", True, contract["base_compute_sha256"])
        append_check(checks, "v2_engine_hash", True, contract["v2_engine_sha256"])
        append_check(
            checks, "v3_reference_script_hash", True,
            contract["v3_reference_script_sha256"],
        )
        append_check(checks, "route_count", len(context.specs) == 5, len(context.specs))
        append_check(
            checks, "point_summary_csv_schema",
            contract["output_schema"]["point_summary_csv_fields"] == CSV_FIELDS,
            len(CSV_FIELDS),
        )
        append_check(
            checks, "v4_is_not_gate_relaxation",
            contract["numeric_gates"]["gate_relaxation_allowed"] is False,
            contract["not_gate_relaxation_statement"],
        )
        append_check(
            checks, "hard_residual_gate_unchanged_1e8",
            float(contract["numeric_gates"]["max_gated_physical_svd_polynomial_residual"]) == 1e-8
            and float(contract["numeric_gates"]["max_gated_physical_svd_direct_laurent_residual"]) == 1e-8,
            [
                contract["numeric_gates"]["max_gated_physical_svd_polynomial_residual"],
                contract["numeric_gates"]["max_gated_physical_svd_direct_laurent_residual"],
            ],
        )
        protected_expected = expected_protected_v2_hashes(context)
        protected_observed = observed_protected_v2_hashes(context)
        append_check(
            checks, "protected_v2_hashes_before_seal",
            protected_observed == protected_expected,
            protected_observed,
        )
        protected_evidence_expected = expected_protected_evidence(context)
        protected_evidence_observed = protected_evidence_snapshot(context)
        for group_name in PROTECTED_EVIDENCE_GROUPS:
            append_check(
                checks, f"{group_name}_before_seal",
                protected_evidence_observed[group_name]
                == protected_evidence_expected[group_name],
                protected_evidence_observed[group_name],
            )
        diff_report = static_diff_selftest(context)
        append_check(
            checks, "numeric_function_ast_equivalence_v3_v4",
            bool(diff_report["numeric_function_ast_equal"]),
            diff_report["numeric_function_ast_sha256_v4"],
        )
        append_check(
            checks, "route_status_merge_order_only_functional_repair",
            diff_report["status"] == "PASS",
            {
                "v3": diff_report["v3_route_status_merge_positions"],
                "v4": diff_report["v4_route_status_merge_positions"],
            },
        )
        required = {tuple(point) for point in contract["required_pilot_points"]}
        pilot_total = sum(len(spec.pilot_points) for spec in context.specs)
        append_check(
            checks, "pilot_point_total_49",
            pilot_total == int(contract["pilot_total_points"]) == 49,
            pilot_total,
        )
        failed_ids = {
            item["route_id"] for item in contract["noncomputable_failed_routes"]
        }
        manifest_failed_ids = {
            item["route_id"] for item in context.manifest["failed_routes"]
        }
        append_check(
            checks, "four_failed_route_identity",
            failed_ids == manifest_failed_ids and len(failed_ids) == 4,
            sorted(failed_ids),
        )
        append_check(
            checks, "failed_routes_do_not_create",
            all(
                item["candidate_policy"] == "DO_NOT_CREATE"
                for item in contract["noncomputable_failed_routes"]
            ),
            "DO_NOT_CREATE",
        )
        existing_failed_dirs = (
            [
                path.as_posix()
                for route_id in sorted(failed_ids)
                for path in output_root().glob(f"**/{route_id}")
                if path.is_dir()
            ]
            if output_root().exists()
            else []
        )
        append_check(
            checks, "failed_route_directories_absent",
            not existing_failed_dirs, existing_failed_dirs,
        )
        append_check(
            checks, "isolated_output_root",
            output_root().resolve()
            not in {
                (board_root() / "outputs" / "step5_fullq_candidate").resolve(),
                (board_root() / "outputs" / "step5_fullq_svd_candidate").resolve(),
            },
            output_root().as_posix(),
        )

        actual_algorithms: dict[str, str] = {}
        matrix_payloads: dict[str, str] = {}
        for spec in context.specs:
            matrices = base.load_route_matrices(context.root, spec)
            n = int(matrices.M.shape[0])
            algorithm = selected_algorithm(n)
            actual_algorithms[spec.route_id] = algorithm
            matrix_payloads[spec.route_id] = matrix_payload_sha256(matrices)
            expected_n = int(
                contract["algorithm_selection"]["expected_matrix_orders"][spec.route_id]
            )
            expected_algorithm = contract["algorithm_selection"][
                "expected_selected_algorithms"
            ][spec.route_id]
            append_check(checks, f"{spec.route_id}.matrix_order", n == expected_n, n)
            append_check(
                checks, f"{spec.route_id}.algorithm_by_order",
                algorithm == expected_algorithm, algorithm,
            )
            append_check(
                checks, f"{spec.route_id}.workspace_hash",
                sha256_file(safe_workspace(context.root, spec.workspace_relpath))
                == spec.workspace_sha256,
                spec.workspace_sha256,
            )
            finite = all(
                np.all(np.isfinite(value))
                for value in (
                    matrices.M, matrices.C1, matrices.K1, matrices.C2,
                    matrices.K2, matrices.al,
                )
            )
            append_check(checks, f"{spec.route_id}.finite_matrices", finite, "finite")
            components = base.build_components(matrices, spec.route_formula)
            right_residual = np.linalg.norm(
                (components.T * (matrices.dt * matrices.dt)) @ matrices.al
                - matrices.M,
                ord="fro",
            ) / max(1.0, np.linalg.norm(matrices.M, ord="fro"))
            append_check(
                checks, f"{spec.route_id}.right_division_residual",
                right_residual <= 1e-12, float(right_residual),
            )
            append_check(
                checks, f"{spec.route_id}.pilot_unique",
                len(spec.pilot_points) == len(set(spec.pilot_points)),
                len(spec.pilot_points),
            )
            if n <= 5:
                append_check(
                    checks, f"{spec.route_id}.required_four_points",
                    required.issubset(set(spec.pilot_points)), sorted(required),
                )
        append_check(
            checks, "algorithm_selection_only_by_matrix_order",
            actual_algorithms
            == contract["algorithm_selection"]["expected_selected_algorithms"],
            actual_algorithms,
        )
        append_check(
            checks, "master_contract_not_closed",
            contract["scientific_contracts"]["master_thesis_route"]["status"]
            == "CONTRACT_NOT_CLOSED",
            contract["scientific_contracts"]["master_thesis_route"]["status"],
        )
        append_check(
            checks, "manuscript_contract_not_closed",
            contract["scientific_contracts"]["manuscript_0824_route"]["status"]
            == "CONTRACT_NOT_CLOSED",
            contract["scientific_contracts"]["manuscript_0824_route"]["status"],
        )

        passed = all(item["status"] == "PASS" for item in checks)
        seal = build_input_seal(context)
        seal_path = output_root() / "input_seal.json"
        if passed:
            if seal_path.is_file() and read_json(seal_path) != seal:
                raise RuntimeError("An incompatible V4 input seal already exists.")
            if not seal_path.is_file():
                base.atomic_write_json(seal_path, seal)
            base.atomic_write_json(
                output_root() / "contracts_status.json", contracts_status(context)
            )
            base.atomic_write_json(
                output_root() / "v2_failure_attribution.json",
                {
                    "schema_version": "board20_step5_fullq_svd_candidate_v4_v2_attribution_v4",
                    "v2_failure_attribution": contract["v2_failure_attribution"],
                    "not_gate_relaxation_statement": contract[
                        "not_gate_relaxation_statement"
                    ],
                    "protected_v2_file_sha256": protected_observed,
                },
            )
            base.atomic_write_json(
                output_root() / "hard_residual_math.json",
                {
                    "schema_version": "board20_step5_fullq_svd_candidate_v4_residual_math_v4",
                    "hard_residual_math": contract["hard_residual_math"],
                    "numeric_gates": contract["numeric_gates"],
                },
            )
            base.atomic_write_json(
                output_root() / "v2_immutability_baseline.json",
                v2_immutability_document(context, "PREFLIGHT_BASELINE"),
            )
            base.atomic_write_json(
                output_root() / "v3_immutability_baseline.json",
                protected_evidence_immutability_document(
                    context, "PREFLIGHT_BASELINE"
                ),
            )
            base.atomic_write_json(
                output_root() / "v3_failure_attribution.json",
                {
                    "schema_version": "board20_step5_fullq_svd_candidate_v4_v3_attribution_v4",
                    "v3_failure_attribution": contract["v3_failure_attribution"],
                    "v3_scientific_output_reuse_policy": "FORBIDDEN",
                    "protected_v3_scientific_sha256": (
                        protected_evidence_observed[
                            "protected_v3_scientific_files"
                        ]
                    ),
                    "protected_v3_failure_audit_sha256": (
                        protected_evidence_observed[
                            "protected_v3_failure_audit_files"
                        ]
                    ),
                },
            )
            base.atomic_write_json(
                output_root() / "static_diff_selftest.json", diff_report
            )
        document = {
            "schema_version": "board20_step5_fullq_svd_candidate_v4_preflight_v4",
            "status": "PASS" if passed else "FAIL",
            "check_count": len(checks),
            "pass_count": sum(item["status"] == "PASS" for item in checks),
            "fail_count": sum(item["status"] == "FAIL" for item in checks),
            "checks": checks,
            "input_seal_sha256": sha256_file(seal_path) if passed else None,
            "matrix_payload_sha256": matrix_payloads,
        }
    except Exception as exc:
        document = {
            "schema_version": "board20_step5_fullq_svd_candidate_v4_preflight_v4",
            "status": "FAIL",
            "check_count": len(checks),
            "pass_count": sum(item["status"] == "PASS" for item in checks),
            "fail_count": sum(item["status"] == "FAIL" for item in checks) + 1,
            "checks": checks,
            "failure_code": f"{type(exc).__name__}:{exc}",
        }
    base.atomic_write_json(output_root() / "preflight.json", document)
    return document


def require_gate(path: Path, expected_schema: str) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Required prior gate is missing: {path}")
    document = read_json(path)
    if document.get("schema_version") != expected_schema or document.get("status") != "PASS":
        raise RuntimeError(f"Required prior gate is not PASS: {path}")
    return document


def prepared_terms(
    terms: Sequence[tuple[int, np.ndarray]],
) -> tuple[tuple[int, np.ndarray, float], ...]:
    prepared: list[tuple[int, np.ndarray, float]] = []
    for exponent, matrix in terms:
        array = np.asarray(matrix, dtype=np.complex128)
        if not np.all(np.isfinite(array)):
            raise FloatingPointError(
                f"Nonfinite characteristic-matrix term at exponent {exponent}."
            )
        norm2 = float(np.linalg.norm(array, ord=2))
        if not math.isfinite(norm2):
            raise FloatingPointError(
                f"Nonfinite spectral norm at exponent {exponent}."
            )
        if norm2 == 0.0:
            continue
        prepared.append((int(exponent), array, norm2))
    if not prepared:
        raise ValueError("Characteristic matrix has no nonzero finite term.")
    return tuple(prepared)


def scale_normalized_svd_residual(
    terms: Sequence[tuple[int, np.ndarray, float]], root: complex
) -> float:
    """Return sigma_min(sum A_e z^e)/sum ||A_e||_2 |z|^e safely."""
    root = complex(root)
    if not (math.isfinite(root.real) and math.isfinite(root.imag)):
        return math.inf
    root_abs = abs(root)
    if root_abs == 0.0:
        if any(exponent < 0 for exponent, _matrix, _norm in terms):
            return math.inf
        active = [item for item in terms if item[0] == 0]
        if not active:
            return math.inf
        reference = max(math.log(norm2) for _e, _m, norm2 in active)
        scaled = np.zeros_like(active[0][1], dtype=np.complex128)
        denominator = 0.0
        for _exponent, matrix, norm2 in active:
            amplitude = math.exp(math.log(norm2) - reference)
            scaled += (amplitude / norm2) * matrix
            denominator += amplitude
    else:
        log_abs = math.log(root_abs)
        phase = math.atan2(root.imag, root.real)
        logs = [
            exponent * log_abs + math.log(norm2)
            for exponent, _matrix, norm2 in terms
        ]
        reference = max(logs)
        scaled = np.zeros_like(terms[0][1], dtype=np.complex128)
        denominator = 0.0
        for (exponent, matrix, norm2), log_weight in zip(terms, logs):
            amplitude = math.exp(log_weight - reference)
            phase_factor = complex(
                math.cos(exponent * phase), math.sin(exponent * phase)
            )
            scaled += (amplitude * phase_factor / norm2) * matrix
            denominator += amplitude
    if not (math.isfinite(denominator) and denominator > 0.0):
        return math.inf
    singular_values = sla.svdvals(scaled, overwrite_a=False, check_finite=False)
    if singular_values.size == 0:
        return math.inf
    residual = float(singular_values[-1] / denominator)
    return residual if math.isfinite(residual) else math.inf


def solve_spectrum(
    transition: np.ndarray,
    n: int,
    polynomial: Sequence[np.ndarray],
    direct_terms: Sequence[tuple[int, np.ndarray]],
    clearing_power: int,
) -> Spectrum:
    order = int(transition.shape[0])
    roots, vectors = sla.eig(
        np.array(transition, dtype=float, copy=True),
        left=False, right=True, overwrite_a=True, check_finite=False,
    )
    roots = np.asarray(roots, dtype=np.complex128).reshape(-1)
    finite = np.isfinite(roots.real) & np.isfinite(roots.imag)
    tolerance = v2engine.zero_tolerance(roots, finite, order)
    removed = (
        finite & (np.abs(roots) <= tolerance)
        if clearing_power > 0
        else np.zeros(roots.shape, dtype=bool)
    )
    poly_prepared = prepared_terms(list(enumerate(polynomial)))
    laurent_prepared = prepared_terms(direct_terms)
    svd_poly = np.full(roots.shape, np.nan, dtype=float)
    svd_laurent = np.full(roots.shape, np.nan, dtype=float)
    vector_poly = np.full(roots.shape, np.nan, dtype=float)
    vector_laurent = np.full(roots.shape, np.nan, dtype=float)
    for index in np.flatnonzero(finite):
        root = roots[index]
        svd_poly[index] = scale_normalized_svd_residual(poly_prepared, root)
        svd_laurent[index] = scale_normalized_svd_residual(
            laurent_prepared, root
        )
        physical = vectors[:n, index]
        vector_poly[index] = base.polynomial_residual(polynomial, root, physical)
        vector_laurent[index] = base.direct_laurent_residual(
            direct_terms, root, physical
        )
    retained_indices = np.flatnonzero(finite & ~removed)
    retained_roots = roots[retained_indices]
    if retained_roots.size == 0:
        raise FloatingPointError("No finite root remains above fixed zero tolerance.")
    magnitudes = np.abs(retained_roots)
    dominant_index = int(np.argmax(magnitudes))
    rho = float(magnitudes[dominant_index])
    if not (math.isfinite(rho) and rho > 0.0):
        raise FloatingPointError("rho is not finite and strictly positive.")
    return Spectrum(
        raw_roots=roots,
        raw_svd_poly=svd_poly,
        raw_svd_laurent=svd_laurent,
        raw_vector_poly=vector_poly,
        raw_vector_laurent=vector_laurent,
        raw_finite=finite,
        raw_removed=removed,
        retained_indices=retained_indices,
        retained_roots=retained_roots,
        retained_svd_poly=svd_poly[retained_indices],
        retained_svd_laurent=svd_laurent[retained_indices],
        retained_vector_poly=vector_poly[retained_indices],
        retained_vector_laurent=vector_laurent[retained_indices],
        zero_tolerance=float(tolerance),
        removed_count=int(np.count_nonzero(removed)),
        rho=rho,
        stable=bool(rho < 1.0),
        critical=bool(abs(rho - 1.0) <= 1e-8),
        dominant_index=dominant_index,
        dominant_root=complex(retained_roots[dominant_index]),
    )


def deterministic_physical_pairing(
    compact_roots: np.ndarray, full_roots: np.ndarray
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, float]:
    compact_roots = np.asarray(compact_roots, dtype=np.complex128).reshape(-1)
    full_roots = np.asarray(full_roots, dtype=np.complex128).reshape(-1)
    if compact_roots.size == 0 or full_roots.size < compact_roots.size:
        raise FloatingPointError(
            "Retained full-q count is smaller than retained compact count."
        )
    denominator = np.maximum(
        1.0,
        np.maximum(np.abs(compact_roots)[:, None], np.abs(full_roots)[None, :]),
    )
    costs = np.abs(compact_roots[:, None] - full_roots[None, :]) / denominator
    rows, columns = linear_sum_assignment(costs)
    if rows.size != compact_roots.size:
        raise FloatingPointError("Optimal pairing did not cover every compact root.")
    compact_to_full = np.full(compact_roots.size, -1, dtype=np.int64)
    full_to_compact = np.full(full_roots.size, -1, dtype=np.int64)
    compact_distance = np.full(compact_roots.size, np.nan, dtype=float)
    full_distance = np.full(full_roots.size, np.nan, dtype=float)
    compact_to_full[rows] = columns
    full_to_compact[columns] = rows
    pair_values = costs[rows, columns]
    compact_distance[rows] = pair_values
    full_distance[columns] = pair_values
    matched = full_to_compact >= 0
    unmatched = ~matched
    return (
        matched, unmatched, compact_to_full, full_to_compact,
        compact_distance, full_distance, float(np.max(pair_values)),
    )


def empty_root_data() -> RootData:
    return RootData(
        roots=np.empty(0, dtype=np.complex128),
        svd_polynomial_residual=np.empty(0, dtype=float),
        svd_laurent_residual=np.empty(0, dtype=float),
        vector_block_polynomial_residual=np.empty(0, dtype=float),
        vector_block_laurent_residual=np.empty(0, dtype=float),
        finite=np.empty(0, dtype=bool),
        removed_as_zero=np.empty(0, dtype=bool),
        matched_physical=np.empty(0, dtype=bool),
        unmatched_full=np.empty(0, dtype=bool),
        paired_other_retained_index=np.empty(0, dtype=np.int64),
        pair_relative_distance=np.empty(0, dtype=float),
    )


def root_data(
    roots: np.ndarray,
    svd_poly: np.ndarray,
    svd_laurent: np.ndarray,
    vector_poly: np.ndarray,
    vector_laurent: np.ndarray,
    finite: np.ndarray,
    removed: np.ndarray,
    matched: np.ndarray,
    unmatched: np.ndarray,
    pair_index: np.ndarray,
    pair_distance: np.ndarray,
) -> RootData:
    return RootData(
        roots=np.asarray(roots, dtype=np.complex128),
        svd_polynomial_residual=np.asarray(svd_poly, dtype=float),
        svd_laurent_residual=np.asarray(svd_laurent, dtype=float),
        vector_block_polynomial_residual=np.asarray(vector_poly, dtype=float),
        vector_block_laurent_residual=np.asarray(vector_laurent, dtype=float),
        finite=np.asarray(finite, dtype=bool),
        removed_as_zero=np.asarray(removed, dtype=bool),
        matched_physical=np.asarray(matched, dtype=bool),
        unmatched_full=np.asarray(unmatched, dtype=bool),
        paired_other_retained_index=np.asarray(pair_index, dtype=np.int64),
        pair_relative_distance=np.asarray(pair_distance, dtype=float),
    )


def optional_max(values: np.ndarray) -> float | None:
    return float(np.max(values)) if values.size else None


def solve_point(
    spec: base.RouteSpec,
    matrices: base.Matrices,
    l_value: int,
    j_value: int,
    gates: Mapping[str, Any],
) -> CandidatePoint:
    started = time.perf_counter()
    try:
        n = int(matrices.M.shape[0])
        algorithm = selected_algorithm(n)
        components = base.build_components(matrices, spec.route_formula)
        coefficients = base.build_coefficient_map(
            spec, components, l_value, j_value
        )
        direct_terms = base.direct_laurent_terms(
            spec, components, l_value, j_value
        )
        polynomial, clearing_power, degree = base.polynomial_from_coefficients(
            coefficients
        )
        formula_difference = base.formula_coefficient_relative_difference(
            spec, components, coefficients, l_value, j_value
        )
        compact_order = 2 * n + l_value + j_value
        full_q_order = n * (max(l_value, j_value) + 2)
        selected_transition = (
            base.build_full_q_history_matrix(
                components, coefficients, l_value, j_value
            )
            if algorithm == ALGORITHM_FULL_Q
            else base.build_compact_state_matrix(
                spec, components, l_value, j_value
            )
        )
        selected = solve_spectrum(
            selected_transition, n, polynomial, direct_terms, clearing_power
        )
        selected_order = int(selected_transition.shape[0])

        auxiliary: Spectrum | None = None
        pairing_performed = algorithm == ALGORITHM_FULL_Q
        theoretical_extra = max(0, full_q_order - compact_order)
        selected_matched = np.ones(selected.retained_roots.size, dtype=bool)
        selected_unmatched = np.zeros(selected.retained_roots.size, dtype=bool)
        selected_pair_index = np.full(
            selected.retained_roots.size, -1, dtype=np.int64
        )
        selected_pair_distance = np.full(
            selected.retained_roots.size, np.nan, dtype=float
        )
        compact_pair_index = np.empty(0, dtype=np.int64)
        compact_pair_distance = np.empty(0, dtype=float)
        root_match_difference: float | None = None
        near_match_difference: float | None = None
        rho_difference: float | None = None
        unmatched_max_abs: float | None = None
        compact_rho: float | None = None
        compact_stable = selected.stable

        if pairing_performed:
            compact_transition = base.build_compact_state_matrix(
                spec, components, l_value, j_value
            )
            auxiliary = solve_spectrum(
                compact_transition, n, polynomial, direct_terms, clearing_power
            )
            (
                selected_matched,
                selected_unmatched,
                compact_pair_index,
                selected_pair_index,
                compact_pair_distance,
                selected_pair_distance,
                root_match_difference,
            ) = deterministic_physical_pairing(
                auxiliary.retained_roots, selected.retained_roots
            )
            compact_rho = auxiliary.rho
            compact_stable = auxiliary.stable
            rho_difference = abs(selected.rho - auxiliary.rho)
            near_threshold = float(gates["near_unit_root_threshold"])
            near_match_difference = base.match_root_sets(
                auxiliary.retained_roots[
                    np.abs(auxiliary.retained_roots) >= near_threshold
                ],
                selected.retained_roots[
                    np.abs(selected.retained_roots) >= near_threshold
                ],
            )
            if np.any(selected_unmatched):
                unmatched_max_abs = float(
                    np.max(np.abs(selected.retained_roots[selected_unmatched]))
                )

        raw_matched = np.zeros(selected.raw_roots.size, dtype=bool)
        raw_unmatched = np.zeros(selected.raw_roots.size, dtype=bool)
        raw_pair_index = np.full(selected.raw_roots.size, -1, dtype=np.int64)
        raw_pair_distance = np.full(selected.raw_roots.size, np.nan, dtype=float)
        raw_matched[selected.retained_indices] = selected_matched
        raw_unmatched[selected.retained_indices] = selected_unmatched
        raw_pair_index[selected.retained_indices] = selected_pair_index
        raw_pair_distance[selected.retained_indices] = selected_pair_distance
        selected_raw_data = root_data(
            selected.raw_roots, selected.raw_svd_poly, selected.raw_svd_laurent,
            selected.raw_vector_poly, selected.raw_vector_laurent,
            selected.raw_finite, selected.raw_removed, raw_matched, raw_unmatched,
            raw_pair_index, raw_pair_distance,
        )
        selected_retained_data = root_data(
            selected.retained_roots, selected.retained_svd_poly,
            selected.retained_svd_laurent, selected.retained_vector_poly,
            selected.retained_vector_laurent,
            np.ones(selected.retained_roots.size, dtype=bool),
            np.zeros(selected.retained_roots.size, dtype=bool),
            selected_matched, selected_unmatched, selected_pair_index,
            selected_pair_distance,
        )

        if auxiliary is None:
            compact_raw_data = empty_root_data()
            compact_retained_data = empty_root_data()
            compact_tolerance: float | None = None
            compact_removed_count = 0
        else:
            compact_raw_pair_index = np.full(
                auxiliary.raw_roots.size, -1, dtype=np.int64
            )
            compact_raw_pair_distance = np.full(
                auxiliary.raw_roots.size, np.nan, dtype=float
            )
            compact_raw_pair_index[auxiliary.retained_indices] = compact_pair_index
            compact_raw_pair_distance[
                auxiliary.retained_indices
            ] = compact_pair_distance
            compact_raw_data = root_data(
                auxiliary.raw_roots, auxiliary.raw_svd_poly,
                auxiliary.raw_svd_laurent, auxiliary.raw_vector_poly,
                auxiliary.raw_vector_laurent, auxiliary.raw_finite,
                auxiliary.raw_removed,
                np.zeros(auxiliary.raw_roots.size, dtype=bool),
                np.zeros(auxiliary.raw_roots.size, dtype=bool),
                compact_raw_pair_index, compact_raw_pair_distance,
            )
            compact_retained_data = root_data(
                auxiliary.retained_roots, auxiliary.retained_svd_poly,
                auxiliary.retained_svd_laurent, auxiliary.retained_vector_poly,
                auxiliary.retained_vector_laurent,
                np.ones(auxiliary.retained_roots.size, dtype=bool),
                np.zeros(auxiliary.retained_roots.size, dtype=bool),
                np.zeros(auxiliary.retained_roots.size, dtype=bool),
                np.zeros(auxiliary.retained_roots.size, dtype=bool),
                compact_pair_index, compact_pair_distance,
            )
            compact_tolerance = auxiliary.zero_tolerance
            compact_removed_count = auxiliary.removed_count

        gated = selected_matched
        if not np.any(gated):
            raise FloatingPointError("No deterministically gated physical root remains.")
        gated_svd_poly = selected.retained_svd_poly[gated]
        gated_svd_laurent = selected.retained_svd_laurent[gated]
        gated_vector_poly = selected.retained_vector_poly[gated]
        gated_vector_laurent = selected.retained_vector_laurent[gated]
        all_gated_finite = bool(
            np.all(np.isfinite(gated_svd_poly))
            and np.all(np.isfinite(gated_svd_laurent))
        )
        max_gated_svd_poly = float(np.max(gated_svd_poly))
        max_gated_svd_laurent = float(np.max(gated_svd_laurent))
        max_gated_vector_poly = float(np.max(gated_vector_poly))
        max_gated_vector_laurent = float(np.max(gated_vector_laurent))

        unmatched_svd_poly = selected.retained_svd_poly[selected_unmatched]
        unmatched_svd_laurent = selected.retained_svd_laurent[selected_unmatched]
        unmatched_vector_poly = selected.retained_vector_poly[selected_unmatched]
        unmatched_vector_laurent = selected.retained_vector_laurent[
            selected_unmatched
        ]
        near_threshold = float(gates["near_unit_root_threshold"])
        near = gated & (np.abs(selected.retained_roots) >= near_threshold)
        dominant_index = selected.dominant_index

        matched_count = int(np.count_nonzero(selected_matched))
        unmatched_count = int(np.count_nonzero(selected_unmatched))
        unmatched_within_theoretical = bool(unmatched_count <= theoretical_extra)
        unmatched_below_limit = bool(
            unmatched_max_abs is None
            or unmatched_max_abs
            < float(gates["unmatched_full_max_abs_strictly_below"])
        )
        unmatched_nondominant = bool(
            unmatched_max_abs is None or unmatched_max_abs < selected.rho
        )
        stable_match = bool(selected.stable == compact_stable)
        origin_status = (
            "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING"
            if pairing_performed and unmatched_count
            else (
                "PASS_NO_UNMATCHED_FULL_ROOT"
                if pairing_performed
                else "NOT_APPLICABLE_COMPACT_SELECTED"
            )
        )

        failures: list[str] = []
        expected_order = full_q_order if n <= 5 else compact_order
        if selected_order != expected_order:
            failures.append("ORDER_SELECTED_MATRIX_MISMATCH")
        if selected.raw_roots.size != selected_order:
            failures.append("RAW_ROOT_COUNT_MISMATCH")
        if np.count_nonzero(~selected.raw_finite):
            failures.append("NONFINITE_SELECTED_ROOT")
        if not all_gated_finite:
            failures.append("NONFINITE_GATED_DIRECT_SVD_RESIDUAL")
        if max_gated_svd_poly > float(
            gates["max_gated_physical_svd_polynomial_residual"]
        ):
            failures.append("GATED_PHYSICAL_SVD_POLYNOMIAL_RESIDUAL")
        if max_gated_svd_laurent > float(
            gates["max_gated_physical_svd_direct_laurent_residual"]
        ):
            failures.append("GATED_PHYSICAL_SVD_LAURENT_RESIDUAL")
        if pairing_performed:
            if not unmatched_within_theoretical:
                failures.append("UNMATCHED_FULL_COUNT_EXCEEDS_THEORETICAL_EXTRA")
            if not unmatched_below_limit:
                failures.append("UNMATCHED_FULL_ROOT_REACHES_NEAR_UNIT_REGION")
            if not unmatched_nondominant:
                failures.append("UNMATCHED_FULL_ROOT_IS_DOMINANT")
            if not stable_match:
                failures.append("FULL_Q_COMPACT_STABLE_CLASSIFICATION_MISMATCH")
        if formula_difference > float(
            gates["direct_formula_coefficient_relative_difference"]
        ):
            failures.append("DIRECT_FORMULA_COEFFICIENT_MISMATCH")

        summary = {
            "route_id": spec.route_id,
            "route_role": spec.route_role,
            "declared_method": spec.declared_method,
            "division": spec.division,
            "route_formula": spec.route_formula,
            "l": int(l_value), "j": int(j_value), "matrix_order": n,
            "algorithm_selector_field": "matrix_order",
            "algorithm_selector_value": n,
            "selected_algorithm": algorithm,
            "selected_order": selected_order,
            "compact_order": compact_order,
            "full_q_order": full_q_order,
            "polynomial_degree": int(degree),
            "clearing_power": int(clearing_power),
            "raw_root_count": int(selected.raw_roots.size),
            "finite_root_count": int(np.count_nonzero(selected.raw_finite)),
            "nonfinite_root_count": int(np.count_nonzero(~selected.raw_finite)),
            "zero_root_tolerance": selected.zero_tolerance,
            "removed_zero_root_count": selected.removed_count,
            "retained_root_count": int(selected.retained_roots.size),
            "compact_pairing_performed": pairing_performed,
            "compact_raw_root_count": (
                int(auxiliary.raw_roots.size) if auxiliary is not None else 0
            ),
            "compact_retained_root_count": (
                int(auxiliary.retained_roots.size) if auxiliary is not None else 0
            ),
            "compact_zero_root_tolerance": compact_tolerance,
            "compact_removed_zero_root_count": compact_removed_count,
            "rho_compact_pairing": compact_rho,
            "stable_compact_pairing": bool(compact_stable),
            "full_q_compact_rho_abs_diff": rho_difference,
            "full_q_compact_root_match_max_relative_diff": root_match_difference,
            "near_unit_root_match_max_relative_diff": near_match_difference,
            "pairing_diagnostic_role": (
                PAIRING_ROLE if pairing_performed
                else "NOT_APPLICABLE_COMPACT_SELECTED"
            ),
            "matched_physical_root_count": matched_count,
            "theoretical_extra_zero_count": int(theoretical_extra),
            "unmatched_full_root_count": unmatched_count,
            "unmatched_count_within_theoretical": unmatched_within_theoretical,
            "unmatched_full_max_abs": unmatched_max_abs,
            "unmatched_full_below_0p9": unmatched_below_limit,
            "unmatched_full_strictly_nondominant": unmatched_nondominant,
            "origin_splitting_status": origin_status,
            "origin_split_gate_role": "DIAGNOSTIC_ONLY_NO_ROOT_REMOVAL",
            "rho": selected.rho,
            "stable": selected.stable,
            "critical": selected.critical,
            "dominant_root_real": float(selected.dominant_root.real),
            "dominant_root_imag": float(selected.dominant_root.imag),
            "max_gated_svd_polynomial_residual": max_gated_svd_poly,
            "max_gated_svd_laurent_residual": max_gated_svd_laurent,
            "max_gated_vector_block_polynomial_residual_diagnostic": max_gated_vector_poly,
            "max_gated_vector_block_laurent_residual_diagnostic": max_gated_vector_laurent,
            "max_unmatched_full_svd_polynomial_residual_diagnostic": optional_max(unmatched_svd_poly),
            "max_unmatched_full_svd_laurent_residual_diagnostic": optional_max(unmatched_svd_laurent),
            "max_unmatched_full_vector_block_polynomial_residual_diagnostic": optional_max(unmatched_vector_poly),
            "max_unmatched_full_vector_block_laurent_residual_diagnostic": optional_max(unmatched_vector_laurent),
            "max_near_unit_svd_polynomial_residual": optional_max(selected.retained_svd_poly[near]),
            "max_near_unit_svd_laurent_residual": optional_max(selected.retained_svd_laurent[near]),
            "max_near_unit_vector_block_polynomial_residual_diagnostic": optional_max(selected.retained_vector_poly[near]),
            "max_near_unit_vector_block_laurent_residual_diagnostic": optional_max(selected.retained_vector_laurent[near]),
            "dominant_svd_polynomial_residual": float(selected.retained_svd_poly[dominant_index]),
            "dominant_svd_laurent_residual": float(selected.retained_svd_laurent[dominant_index]),
            "dominant_vector_block_polynomial_residual_diagnostic": float(selected.retained_vector_poly[dominant_index]),
            "dominant_vector_block_laurent_residual_diagnostic": float(selected.retained_vector_laurent[dominant_index]),
            "hard_residual_definition": HARD_RESIDUAL_LABEL,
            "vector_block_residual_role": VECTOR_ROLE,
            "direct_formula_coefficient_relative_difference": float(formula_difference),
            "stable_classification_match": stable_match,
            "all_gated_svd_residuals_finite": all_gated_finite,
            "point_status": "PASS" if not failures else "FAIL",
            "failure_code": ";".join(failures),
        }
        return CandidatePoint(
            summary=summary,
            selected_raw=selected_raw_data,
            selected_retained=selected_retained_data,
            pairing_compact_raw=compact_raw_data,
            pairing_compact_retained=compact_retained_data,
            elapsed_seconds=time.perf_counter() - started,
        )
    except Exception as exc:
        n = int(matrices.M.shape[0])
        algorithm = selected_algorithm(n)
        compact_order = 2 * n + l_value + j_value
        full_q_order = n * (max(l_value, j_value) + 2)
        summary: dict[str, Any] = {field: "" for field in CSV_FIELDS}
        summary.update(
            {
                "route_id": spec.route_id, "route_role": spec.route_role,
                "declared_method": spec.declared_method,
                "division": spec.division, "route_formula": spec.route_formula,
                "l": int(l_value), "j": int(j_value), "matrix_order": n,
                "algorithm_selector_field": "matrix_order",
                "algorithm_selector_value": n,
                "selected_algorithm": algorithm,
                "selected_order": full_q_order if n <= 5 else compact_order,
                "compact_order": compact_order, "full_q_order": full_q_order,
                "raw_root_count": 0, "finite_root_count": 0,
                "nonfinite_root_count": 0, "removed_zero_root_count": 0,
                "retained_root_count": 0,
                "compact_pairing_performed": algorithm == ALGORITHM_FULL_Q,
                "compact_raw_root_count": 0,
                "compact_retained_root_count": 0,
                "compact_removed_zero_root_count": 0,
                "stable_compact_pairing": False,
                "pairing_diagnostic_role": (
                    PAIRING_ROLE if algorithm == ALGORITHM_FULL_Q
                    else "NOT_APPLICABLE_COMPACT_SELECTED"
                ),
                "matched_physical_root_count": 0,
                "theoretical_extra_zero_count": max(
                    0, full_q_order - compact_order
                ),
                "unmatched_full_root_count": 0,
                "unmatched_count_within_theoretical": False,
                "unmatched_full_below_0p9": False,
                "unmatched_full_strictly_nondominant": False,
                "origin_splitting_status": "SOLVE_FAILED",
                "origin_split_gate_role": "DIAGNOSTIC_ONLY_NO_ROOT_REMOVAL",
                "stable": False, "critical": False,
                "hard_residual_definition": HARD_RESIDUAL_LABEL,
                "vector_block_residual_role": VECTOR_ROLE,
                "stable_classification_match": False,
                "all_gated_svd_residuals_finite": False,
                "point_status": "FAIL",
                "failure_code": f"{type(exc).__name__}:{exc}",
            }
        )
        empty = empty_root_data()
        return CandidatePoint(
            summary=summary, selected_raw=empty,
            selected_retained=empty_root_data(),
            pairing_compact_raw=empty_root_data(),
            pairing_compact_retained=empty_root_data(),
            elapsed_seconds=time.perf_counter() - started,
        )


def run_selftest() -> dict[str, Any]:
    context, seal = verify_input_seal()
    preflight = require_gate(
        output_root() / "preflight.json",
        "board20_step5_fullq_svd_candidate_v4_preflight_v4",
    )
    if preflight.get("input_seal_sha256") != sha256_file(
        output_root() / "input_seal.json"
    ):
        raise RuntimeError("Preflight is not bound to the current V4 input seal.")
    checks: list[dict[str, Any]] = []
    gates = context.contract["numeric_gates"]
    protected_before = observed_protected_v2_hashes(context)
    protected_evidence_before = protected_evidence_snapshot(context)
    diff_report = static_diff_selftest(context)
    append_check(
        checks, "numeric_function_ast_equivalence_v3_v4",
        bool(diff_report["numeric_function_ast_equal"]),
        diff_report["numeric_function_ast_sha256_v4"],
    )
    append_check(
        checks, "route_status_merge_order_only_functional_repair",
        diff_report["status"] == "PASS",
        {
            "v3": diff_report["v3_route_status_merge_positions"],
            "v4": diff_report["v4_route_status_merge_positions"],
        },
    )

    identity = np.eye(2, dtype=float)
    polynomial_terms = prepared_terms(((0, -0.5 * identity), (1, identity)))
    polynomial_exact = scale_normalized_svd_residual(polynomial_terms, 0.5)
    polynomial_perturbed = scale_normalized_svd_residual(
        polynomial_terms, 0.5 + 1.0e-4
    )
    append_check(
        checks, "exact_polynomial_root_svd",
        math.isfinite(polynomial_exact) and polynomial_exact <= 1e-12,
        polynomial_exact,
    )
    append_check(
        checks, "perturbed_polynomial_root_rejected",
        math.isfinite(polynomial_perturbed) and polynomial_perturbed > 1e-8,
        polynomial_perturbed,
    )

    laurent_terms = prepared_terms(
        ((1, identity), (0, -0.5 * identity), (-1, -0.5 * identity))
    )
    laurent_exact = scale_normalized_svd_residual(laurent_terms, 1.0)
    laurent_perturbed = scale_normalized_svd_residual(
        laurent_terms, 1.0 + 1.0e-3
    )
    append_check(
        checks, "exact_laurent_root_svd",
        math.isfinite(laurent_exact) and laurent_exact <= 1e-12,
        laurent_exact,
    )
    append_check(
        checks, "perturbed_laurent_root_rejected",
        math.isfinite(laurent_perturbed) and laurent_perturbed > 1e-8,
        laurent_perturbed,
    )

    tiny_root = 2.0**-600
    extreme_terms = prepared_terms(
        ((-2, identity), (-1, -(tiny_root**-1) * identity))
    )
    extreme_exact = scale_normalized_svd_residual(extreme_terms, tiny_root)
    extreme_perturbed = scale_normalized_svd_residual(
        extreme_terms, tiny_root * (1.0 + 2.0**-20)
    )
    append_check(
        checks, "extreme_scale_exact_laurent_finite",
        math.isfinite(extreme_exact) and extreme_exact <= 1e-12,
        extreme_exact,
    )
    append_check(
        checks, "extreme_scale_perturbed_laurent_rejected",
        math.isfinite(extreme_perturbed) and extreme_perturbed > 1e-8,
        extreme_perturbed,
    )
    append_check(
        checks, "laurent_at_zero_is_undefined",
        math.isinf(scale_normalized_svd_residual(laurent_terms, 0.0)),
        "UNDEFINED_LAURENT_AT_ZERO",
    )
    zero_polynomial = prepared_terms(((0, identity), (1, identity)))
    zero_polynomial_value = scale_normalized_svd_residual(zero_polynomial, 0.0)
    append_check(
        checks, "polynomial_at_zero_uses_constant_term",
        math.isfinite(zero_polynomial_value)
        and abs(zero_polynomial_value - 1.0) <= 1e-14,
        zero_polynomial_value,
    )

    cases = [
        (5, "GUYAN_DIV1_H_LEFT", (1, 2)),
        (5, "DIV2_H_LEFT_FEEDBACK_OUTSIDE", (2, 1)),
        (6, "ORI_DIV1_H_RIGHT", (1, 2)),
        (6, "GUYAN_DIV1_H_LEFT", (2, 1)),
        (6, "DIV2_H_LEFT_FEEDBACK_OUTSIDE", (1, 2)),
    ]
    for n, formula, point in cases:
        matrices = base.synthetic_matrices(n)
        spec = base.synthetic_spec(formula)
        l_value, j_value = point
        result = solve_point(spec, matrices, l_value, j_value, gates)
        prefix = f"n{n}.{formula}.{l_value}.{j_value}"
        append_check(
            checks, prefix + ".algorithm",
            result.summary["selected_algorithm"] == selected_algorithm(n),
            result.summary["selected_algorithm"],
        )
        append_check(
            checks, prefix + ".point_status",
            result.summary["point_status"] == "PASS",
            result.summary["failure_code"],
        )
        append_check(
            checks, prefix + ".root_count",
            result.summary["raw_root_count"] == result.summary["selected_order"],
            result.summary["raw_root_count"],
        )
        append_check(
            checks, prefix + ".rho",
            result.summary.get("rho") not in (None, "")
            and math.isfinite(float(result.summary["rho"]))
            and float(result.summary["rho"]) > 0.0,
            result.summary.get("rho"),
        )
        append_check(
            checks, prefix + ".svd_polynomial_residual",
            result.summary.get("max_gated_svd_polynomial_residual") not in (None, "")
            and float(result.summary["max_gated_svd_polynomial_residual"])
            <= float(gates["max_gated_physical_svd_polynomial_residual"]),
            result.summary.get("max_gated_svd_polynomial_residual"),
        )
        append_check(
            checks, prefix + ".svd_laurent_residual",
            result.summary.get("max_gated_svd_laurent_residual") not in (None, "")
            and float(result.summary["max_gated_svd_laurent_residual"])
            <= float(gates["max_gated_physical_svd_direct_laurent_residual"]),
            result.summary.get("max_gated_svd_laurent_residual"),
        )
        append_check(
            checks, prefix + ".vector_block_diagnostic_saved",
            result.summary.get(
                "max_gated_vector_block_laurent_residual_diagnostic"
            ) not in (None, "")
            and result.summary["vector_block_residual_role"] == VECTOR_ROLE,
            [
                result.summary.get(
                    "max_gated_vector_block_laurent_residual_diagnostic"
                ),
                result.summary.get("vector_block_residual_role"),
            ],
        )
        append_check(
            checks, prefix + ".formula_identity",
            result.summary.get("direct_formula_coefficient_relative_difference")
            not in (None, "")
            and float(
                result.summary["direct_formula_coefficient_relative_difference"]
            )
            <= float(gates["direct_formula_coefficient_relative_difference"]),
            result.summary.get("direct_formula_coefficient_relative_difference"),
        )
        append_check(
            checks, prefix + ".pairing_mode",
            bool(result.summary["compact_pairing_performed"]) == (n <= 5),
            result.summary["compact_pairing_performed"],
        )
        append_check(
            checks, prefix + ".unmatched_count",
            bool(result.summary["unmatched_count_within_theoretical"]),
            [
                result.summary["unmatched_full_root_count"],
                result.summary["theoretical_extra_zero_count"],
            ],
        )
        append_check(
            checks, prefix + ".unmatched_below_0p9",
            bool(result.summary["unmatched_full_below_0p9"]),
            result.summary.get("unmatched_full_max_abs"),
        )
        append_check(
            checks, prefix + ".unmatched_nondominant",
            bool(result.summary["unmatched_full_strictly_nondominant"]),
            [result.summary.get("unmatched_full_max_abs"), result.summary.get("rho")],
        )
        append_check(
            checks, prefix + ".stable_match",
            bool(result.summary["stable_classification_match"]),
            [
                result.summary.get("stable"),
                result.summary.get("stable_compact_pairing"),
            ],
        )

    append_check(
        checks, "selector_n5",
        selected_algorithm(5) == ALGORITHM_FULL_Q, selected_algorithm(5),
    )
    append_check(
        checks, "selector_n6",
        selected_algorithm(6) == ALGORITHM_COMPACT, selected_algorithm(6),
    )
    append_check(
        checks, "selector_n15",
        selected_algorithm(15) == ALGORITHM_COMPACT, selected_algorithm(15),
    )
    protected_after = observed_protected_v2_hashes(context)
    append_check(
        checks, "protected_v2_files_unchanged_during_selftest",
        protected_before == protected_after == expected_protected_v2_hashes(context),
        protected_after,
    )
    protected_evidence_after = protected_evidence_snapshot(context)
    append_check(
        checks, "all_v3_v2_compact_failure_evidence_unchanged_during_selftest",
        protected_evidence_before
        == protected_evidence_after
        == expected_protected_evidence(context),
        protected_evidence_after,
    )
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    document = {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_selftest_v4",
        "status": status,
        "check_count": len(checks),
        "pass_count": sum(item["status"] == "PASS" for item in checks),
        "fail_count": sum(item["status"] == "FAIL" for item in checks),
        "checks": checks,
        "input_seal_sha256": sha256_file(output_root() / "input_seal.json"),
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
        "v2_engine_sha256": seal["v2_engine_sha256"],
        "v3_reference_script_sha256": seal["v3_reference_script_sha256"],
        "static_diff_selftest_sha256": seal["static_diff_selftest_sha256"],
        "protected_v2_before_sha256": protected_before,
        "protected_v2_after_sha256": protected_after,
        "protected_evidence_before_sha256": protected_evidence_before,
        "protected_evidence_after_sha256": protected_evidence_after,
    }
    base.atomic_write_json(output_root() / "selftest.json", document)
    return document


def h5_string_dtype() -> np.dtype:
    return h5py.string_dtype(encoding="utf-8")


def ragged_layout(arrays: Sequence[np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    counts = np.asarray([array.size for array in arrays], dtype=np.int64)
    offsets = np.zeros(counts.shape, dtype=np.int64)
    if counts.size > 1:
        offsets[1:] = np.cumsum(counts[:-1])
    return offsets, counts


def concatenate_or_empty(
    arrays: Sequence[np.ndarray], dtype: np.dtype
) -> np.ndarray:
    if arrays and sum(array.size for array in arrays):
        return np.concatenate(arrays).astype(dtype, copy=False)
    return np.empty(0, dtype=dtype)


def write_root_group(
    parent: h5py.Group, name: str, roots: Sequence[RootData]
) -> None:
    group = parent.create_group(name)
    offsets, counts = ragged_layout([item.roots for item in roots])
    joined = concatenate_or_empty([item.roots for item in roots], np.complex128)
    kwargs = {"compression": "gzip", "compression_opts": 4, "shuffle": True}
    group.create_dataset("offset", data=offsets, **kwargs)
    group.create_dataset("count", data=counts, **kwargs)
    group.create_dataset("real", data=joined.real.astype(np.float64), **kwargs)
    group.create_dataset("imag", data=joined.imag.astype(np.float64), **kwargs)
    for field, dtype in (
        ("svd_polynomial_residual", np.float64),
        ("svd_laurent_residual", np.float64),
        ("vector_block_polynomial_residual", np.float64),
        ("vector_block_laurent_residual", np.float64),
        ("finite", np.uint8),
        ("removed_as_zero", np.uint8),
        ("matched_physical", np.uint8),
        ("unmatched_full", np.uint8),
        ("paired_other_retained_index", np.int64),
        ("pair_relative_distance", np.float64),
    ):
        group.create_dataset(
            field,
            data=concatenate_or_empty(
                [np.asarray(getattr(item, field)) for item in roots], dtype
            ),
            **kwargs,
        )


def atomic_write_results_h5(
    path: Path, results: Sequence[CandidatePoint]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    if temporary.exists():
        temporary.unlink()
    with h5py.File(
        temporary, "w", libver="earliest", track_order=False
    ) as handle:
        handle.attrs["schema_version"] = (
            "board20_step5_fullq_svd_candidate_v4_roots_h5_v4"
        )
        handle.attrs["hard_residual_definition"] = HARD_RESIDUAL_LABEL
        handle.attrs["vector_block_residual_role"] = VECTOR_ROLE
        points = handle.create_group("points")
        for field in CSV_FIELDS:
            values = [item.summary.get(field) for item in results]
            if field in STRING_FIELDS:
                points.create_dataset(
                    field,
                    data=np.asarray(
                        ["" if value is None else str(value) for value in values],
                        dtype=object,
                    ),
                    dtype=h5_string_dtype(),
                )
            elif field in BOOL_FIELDS:
                points.create_dataset(
                    field,
                    data=np.asarray([bool(value) for value in values], dtype=np.uint8),
                )
            elif field in INT_FIELDS:
                points.create_dataset(
                    field,
                    data=np.asarray(
                        [
                            int(value) if value not in (None, "") else -1
                            for value in values
                        ],
                        dtype=np.int64,
                    ),
                )
            else:
                points.create_dataset(
                    field,
                    data=np.asarray(
                        [
                            float(value) if value not in (None, "") else math.nan
                            for value in values
                        ],
                        dtype=np.float64,
                    ),
                )
        records = [
            json.dumps(
                {key: json_safe(value) for key, value in item.summary.items()},
                ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                allow_nan=False,
            )
            for item in results
        ]
        points.create_dataset(
            "record_json", data=np.asarray(records, dtype=object),
            dtype=h5_string_dtype(),
        )
        selected = handle.create_group("selected")
        write_root_group(
            selected, "raw", [item.selected_raw for item in results]
        )
        write_root_group(
            selected, "retained", [item.selected_retained for item in results]
        )
        compact = handle.create_group("pairing_compact")
        write_root_group(
            compact, "raw", [item.pairing_compact_raw for item in results]
        )
        write_root_group(
            compact, "retained",
            [item.pairing_compact_retained for item in results],
        )
        handle.flush()
    base.replace_with_retry(temporary, path)


def read_root_slice(group: h5py.Group, index: int) -> RootData:
    offset = int(group["offset"][index])
    count = int(group["count"][index])
    selected = slice(offset, offset + count)
    return root_data(
        group["real"][selected] + 1j * group["imag"][selected],
        group["svd_polynomial_residual"][selected],
        group["svd_laurent_residual"][selected],
        group["vector_block_polynomial_residual"][selected],
        group["vector_block_laurent_residual"][selected],
        group["finite"][selected], group["removed_as_zero"][selected],
        group["matched_physical"][selected], group["unmatched_full"][selected],
        group["paired_other_retained_index"][selected],
        group["pair_relative_distance"][selected],
    )


def validate_root_group(group: h5py.Group, point_count: int) -> None:
    required = (
        "offset", "count", "real", "imag", "svd_polynomial_residual",
        "svd_laurent_residual", "vector_block_polynomial_residual",
        "vector_block_laurent_residual", "finite", "removed_as_zero",
        "matched_physical", "unmatched_full", "paired_other_retained_index",
        "pair_relative_distance",
    )
    if any(name not in group for name in required):
        raise RuntimeError(f"HDF5 root group is missing a V4 dataset: {group.name}")
    offsets = np.asarray(group["offset"][...], dtype=np.int64)
    counts = np.asarray(group["count"][...], dtype=np.int64)
    if offsets.size != point_count or counts.size != point_count:
        raise RuntimeError(f"HDF5 point/root layout mismatch: {group.name}")
    if np.any(counts < 0):
        raise RuntimeError(f"Negative HDF5 ragged count: {group.name}")
    expected_offsets = np.zeros(point_count, dtype=np.int64)
    if point_count > 1:
        expected_offsets[1:] = np.cumsum(counts[:-1])
    if not np.array_equal(offsets, expected_offsets):
        raise RuntimeError(f"Noncontiguous HDF5 ragged offsets: {group.name}")
    total = int(np.sum(counts))
    for name in required[2:]:
        if int(group[name].size) != total:
            raise RuntimeError(
                f"HDF5 flattened root dataset length mismatch: {group.name}/{name}"
            )


def read_results_h5(path: Path) -> list[CandidatePoint]:
    results: list[CandidatePoint] = []
    with h5py.File(path, "r") as handle:
        schema = handle.attrs.get("schema_version", "")
        if schema != "board20_step5_fullq_svd_candidate_v4_roots_h5_v4":
            raise RuntimeError("Checkpoint HDF5 schema is not V4.")
        if handle.attrs.get("hard_residual_definition", "") != HARD_RESIDUAL_LABEL:
            raise RuntimeError("Checkpoint hard-residual identity is not V4.")
        if handle.attrs.get("vector_block_residual_role", "") != VECTOR_ROLE:
            raise RuntimeError("Checkpoint vector-residual role is not V4.")
        records = handle["points/record_json"].asstr()[...]
        point_count = len(records)
        for field in CSV_FIELDS:
            if field not in handle["points"] or handle[f"points/{field}"].size != point_count:
                raise RuntimeError(f"HDF5 point dataset mismatch: points/{field}")
        for group_name in (
            "selected/raw", "selected/retained", "pairing_compact/raw",
            "pairing_compact/retained",
        ):
            validate_root_group(handle[group_name], point_count)
        for index, text in enumerate(records):
            results.append(
                CandidatePoint(
                    summary=json.loads(text),
                    selected_raw=read_root_slice(handle["selected/raw"], index),
                    selected_retained=read_root_slice(
                        handle["selected/retained"], index
                    ),
                    pairing_compact_raw=read_root_slice(
                        handle["pairing_compact/raw"], index
                    ),
                    pairing_compact_retained=read_root_slice(
                        handle["pairing_compact/retained"], index
                    ),
                    elapsed_seconds=0.0,
                )
            )
    return results


def checkpoint_identity(
    seal: Mapping[str, Any], spec: base.RouteSpec,
    points: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_checkpoint_identity_v4",
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
        "route_manifest_sha256": seal["route_manifest_sha256"],
        "base_compute_sha256": seal["base_compute_sha256"],
        "v2_engine_sha256": seal["v2_engine_sha256"],
        "v3_reference_script_sha256": seal["v3_reference_script_sha256"],
        "static_diff_selftest_sha256": seal["static_diff_selftest_sha256"],
        "protected_evidence_sha256": sha256_json(
            seal["protected_evidence_sha256"]
        ),
        "workspace_sha256": spec.workspace_sha256,
        "route_id": spec.route_id,
        "point_order_sha256": sha256_json([list(point) for point in points]),
        "hard_residual_math_sha256": seal["hard_residual_math_sha256"],
        "numeric_gates_sha256": seal["numeric_gates_sha256"],
    }


def write_checkpoint(
    route_directory: Path, results: Sequence[CandidatePoint],
    identity: Mapping[str, Any], state: str,
) -> None:
    h5_path = route_directory / "checkpoint.h5"
    atomic_write_results_h5(h5_path, results)
    base.atomic_write_json(
        route_directory / "checkpoint.json",
        {
            **identity,
            "state": state,
            "completed_point_count": len(results),
            "checkpoint_h5_sha256": sha256_file(h5_path),
        },
    )


def load_checkpoint(
    route_directory: Path, identity: Mapping[str, Any]
) -> list[CandidatePoint]:
    json_path = route_directory / "checkpoint.json"
    h5_path = route_directory / "checkpoint.h5"
    if not json_path.is_file() or not h5_path.is_file():
        raise FileNotFoundError(f"Complete V4 checkpoint pair required: {route_directory}")
    document = read_json(json_path)
    for key, value in identity.items():
        if document.get(key) != value:
            raise RuntimeError(f"V4 checkpoint identity mismatch: {key}")
    if document.get("checkpoint_h5_sha256") != sha256_file(h5_path):
        raise RuntimeError("V4 checkpoint HDF5 SHA-256 mismatch.")
    results = read_results_h5(h5_path)
    if len(results) != int(document["completed_point_count"]):
        raise RuntimeError("V4 checkpoint point count mismatch.")
    return results


def numeric_values(
    results: Sequence[CandidatePoint], field: str
) -> list[float]:
    values: list[float] = []
    for item in results:
        value = item.summary.get(field)
        if value not in (None, ""):
            values.append(float(value))
    return values


def write_route_outputs(
    route_directory: Path, results: Sequence[CandidatePoint],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    base.atomic_write_csv(
        route_directory / "point_summary.csv",
        [item.summary for item in results], CSV_FIELDS,
    )
    base.atomic_write_csv(
        route_directory / "point_runtime.csv",
        [
            {
                "route_id": item.summary["route_id"],
                "l": item.summary["l"], "j": item.summary["j"],
                "elapsed_seconds": item.elapsed_seconds,
                "point_status": item.summary["point_status"],
            }
            for item in results
        ],
        RUNTIME_FIELDS,
    )
    roots_path = route_directory / "roots.h5"
    atomic_write_results_h5(roots_path, results)
    pass_count = sum(item.summary["point_status"] == "PASS" for item in results)
    fail_count = len(results) - pass_count
    poly = numeric_values(results, "max_gated_svd_polynomial_residual")
    laurent = numeric_values(results, "max_gated_svd_laurent_residual")
    vector_poly = numeric_values(
        results, "max_gated_vector_block_polynomial_residual_diagnostic"
    )
    vector_laurent = numeric_values(
        results, "max_gated_vector_block_laurent_residual_diagnostic"
    )
    formula = numeric_values(
        results, "direct_formula_coefficient_relative_difference"
    )
    rhos = numeric_values(results, "rho")
    unmatched_abs = numeric_values(results, "unmatched_full_max_abs")
    rho_diffs = numeric_values(results, "full_q_compact_rho_abs_diff")
    status = {
        **identity,
        "schema_version": "board20_step5_fullq_svd_candidate_v4_route_status_v4",
        "status": "PASS" if fail_count == 0 else "FAIL",
        "route_id": identity["route_id"],
        "selected_algorithm": (
            results[0].summary["selected_algorithm"] if results else None
        ),
        "matrix_order": results[0].summary["matrix_order"] if results else None,
        "expected_point_count": len(results),
        "completed_point_count": len(results),
        "pass_point_count": pass_count,
        "fail_point_count": fail_count,
        "max_gated_svd_polynomial_residual": max(poly, default=None),
        "max_gated_svd_laurent_residual": max(laurent, default=None),
        "max_gated_vector_block_polynomial_residual_diagnostic": max(
            vector_poly, default=None
        ),
        "max_gated_vector_block_laurent_residual_diagnostic": max(
            vector_laurent, default=None
        ),
        "max_formula_relative_difference": max(formula, default=None),
        "rho_min": min(rhos, default=None),
        "rho_max": max(rhos, default=None),
        "origin_splitting_point_count": sum(
            item.summary.get("unmatched_full_root_count", 0) not in (0, None, "")
            for item in results
        ),
        "max_unmatched_full_abs": max(unmatched_abs, default=None),
        "max_full_q_compact_rho_abs_diff_diagnostic": max(
            rho_diffs, default=None
        ),
        "stable_classification_mismatch_count": sum(
            not bool(item.summary.get("stable_classification_match", False))
            for item in results
        ),
        "hard_residual_definition": HARD_RESIDUAL_LABEL,
        "vector_block_residual_role": VECTOR_ROLE,
        "point_summary_sha256": sha256_file(route_directory / "point_summary.csv"),
        "roots_h5_sha256": sha256_file(roots_path),
        "scientific_status_policy": "DETERMINISTIC_NO_WALL_CLOCK_FIELDS",
    }
    base.atomic_write_json(route_directory / "route_status.json", status)
    return status


def known_route_files() -> tuple[str, ...]:
    return (
        "point_summary.csv", "roots.h5", "route_status.json",
        "checkpoint.h5", "checkpoint.json", "point_runtime.csv",
    )


def clear_route_files(route_directory: Path) -> None:
    for name in known_route_files():
        path = route_directory / name
        if path.is_file():
            path.unlink()


def points_for_mode(
    context: Context, spec: base.RouteSpec, mode: str
) -> list[tuple[int, int]]:
    if mode == "pilot":
        return list(spec.pilot_points)
    grid = context.contract["full_grid"]
    return [
        (l_value, j_value)
        for l_value in range(int(grid["l_start"]), int(grid["l_end"]) + 1)
        for j_value in range(int(grid["j_start"]), int(grid["j_end"]) + 1)
    ]


def write_artifact_manifest(
    mode_directory: Path, route_ids: Sequence[str]
) -> Path:
    paths = [
        mode_directory / route_id / name
        for route_id in route_ids
        for name in ("point_summary.csv", "roots.h5", "route_status.json")
    ] + [
        mode_directory / "v2_immutability_postrun.json",
        mode_directory / "v3_immutability_postrun.json",
        mode_directory / "run_status.json",
    ]
    rows = [
        {
            "relpath": path.relative_to(mode_directory).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(
            paths, key=lambda item: item.relative_to(mode_directory).as_posix()
        )
    ]
    manifest_path = mode_directory / "artifact_manifest.csv"
    base.atomic_write_csv(manifest_path, rows, ("relpath", "bytes", "sha256"))
    return manifest_path


def run_scientific_mode(
    requested_mode: str, overwrite: bool, checkpoint_every: int,
    expected_manifest_sha256: str | None,
) -> dict[str, Any]:
    context, seal = verify_input_seal()
    preflight = require_gate(
        output_root() / "preflight.json",
        "board20_step5_fullq_svd_candidate_v4_preflight_v4",
    )
    if preflight.get("input_seal_sha256") != sha256_file(
        output_root() / "input_seal.json"
    ):
        raise RuntimeError("Preflight is not bound to the current V4 input seal.")
    selftest = require_gate(
        output_root() / "selftest.json",
        "board20_step5_fullq_svd_candidate_v4_selftest_v4",
    )
    expected_selftest_identity = {
        "input_seal_sha256": sha256_file(output_root() / "input_seal.json"),
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
        "v2_engine_sha256": seal["v2_engine_sha256"],
        "v3_reference_script_sha256": seal["v3_reference_script_sha256"],
        "static_diff_selftest_sha256": seal["static_diff_selftest_sha256"],
    }
    for key, expected in expected_selftest_identity.items():
        if selftest.get(key) != expected:
            raise RuntimeError(f"Selftest is not bound to current V4 identity: {key}")
    if requested_mode in ("full", "resume"):
        pilot_status = require_gate(
            output_root() / "pilot" / "run_status.json",
            "board20_step5_fullq_svd_candidate_v4_run_status_v4",
        )
        if (
            pilot_status.get("input_identity") != seal
            or pilot_status.get("mode") != "pilot"
            or int(pilot_status.get("route_count", -1)) != 5
            or int(pilot_status.get("expected_point_count", -1)) != 49
            or int(pilot_status.get("completed_point_count", -1)) != 49
            or int(pilot_status.get("fail_point_count", -1)) != 0
        ):
            raise RuntimeError("Pilot PASS is not the current sealed 5-route/49-point run.")
    mode = "full" if requested_mode == "resume" else requested_mode
    mode_directory = output_root() / mode
    mode_directory.mkdir(parents=True, exist_ok=True)
    gates = context.contract["numeric_gates"]
    route_statuses: list[dict[str, Any]] = []
    started = time.perf_counter()
    protected_before = observed_protected_v2_hashes(context)
    if protected_before != expected_protected_v2_hashes(context):
        raise RuntimeError("Protected V2 hash mismatch before scientific solve.")
    protected_evidence_before = protected_evidence_snapshot(context)
    if protected_evidence_before != expected_protected_evidence(context):
        raise RuntimeError(
            "Protected V3/V2/compact failure evidence mismatch before solve."
        )

    for spec in context.specs:
        matrices = base.load_route_matrices(context.root, spec)
        n = int(matrices.M.shape[0])
        algorithm = selected_algorithm(n)
        expected_algorithm = context.contract["algorithm_selection"][
            "expected_selected_algorithms"
        ][spec.route_id]
        if algorithm != expected_algorithm:
            raise RuntimeError(f"Order-only algorithm identity changed: {spec.route_id}")
        points = points_for_mode(context, spec, mode)
        route_directory = mode_directory / spec.route_id
        route_directory.mkdir(parents=True, exist_ok=True)
        identity = checkpoint_identity(seal, spec, points)
        if requested_mode == "resume":
            results = load_checkpoint(route_directory, identity)
        else:
            existing = [
                route_directory / name for name in known_route_files()
                if (route_directory / name).exists()
            ]
            if existing and not overwrite:
                raise FileExistsError(
                    f"V4 outputs already exist; pass --overwrite: {route_directory}"
                )
            if overwrite:
                clear_route_files(route_directory)
            results: list[CandidatePoint] = []
        if len(results) > len(points):
            raise RuntimeError(f"Checkpoint exceeds point contract: {spec.route_id}")
        for index, result in enumerate(results):
            if (int(result.summary["l"]), int(result.summary["j"])) != points[index]:
                raise RuntimeError(f"Checkpoint point order mismatch: {spec.route_id}")
        for index in range(len(results), len(points)):
            l_value, j_value = points[index]
            point = solve_point(spec, matrices, l_value, j_value, gates)
            results.append(point)
            logging.info(
                "%s %s %d/%d l=%d j=%d algorithm=%s status=%s rho=%s elapsed=%.3fs",
                mode, spec.route_id, index + 1, len(points), l_value, j_value,
                algorithm, point.summary["point_status"],
                point.summary.get("rho"), point.elapsed_seconds,
            )
            if (
                (index + 1) % checkpoint_every == 0
                or index + 1 == len(points)
                or point.summary["point_status"] != "PASS"
            ):
                write_checkpoint(
                    route_directory, results, identity,
                    "COMPLETE" if index + 1 == len(points) else "IN_PROGRESS",
                )
        if not results:
            write_checkpoint(route_directory, results, identity, "COMPLETE")
        route_statuses.append(
            write_route_outputs(route_directory, results, identity)
        )

    immutability = v2_immutability_document(
        context, f"{mode.upper()}_POSTRUN", protected_before
    )
    base.atomic_write_json(
        mode_directory / "v2_immutability_postrun.json", immutability
    )
    evidence_immutability = protected_evidence_immutability_document(
        context, f"{mode.upper()}_POSTRUN", protected_evidence_before
    )
    base.atomic_write_json(
        mode_directory / "v3_immutability_postrun.json", evidence_immutability
    )
    expected_total = sum(
        len(points_for_mode(context, spec, mode)) for spec in context.specs
    )
    completed = sum(int(item["completed_point_count"]) for item in route_statuses)
    failures = sum(int(item["fail_point_count"]) for item in route_statuses)
    status_text = (
        "PASS"
        if completed == expected_total
        and failures == 0
        and all(item["status"] == "PASS" for item in route_statuses)
        and immutability["status"] == "PASS"
        and evidence_immutability["status"] == "PASS"
        else "FAIL"
    )
    run_status = {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_run_status_v4",
        "status": status_text, "mode": mode,
        "route_count": len(route_statuses),
        "expected_point_count": expected_total,
        "completed_point_count": completed,
        "pass_point_count": completed - failures,
        "fail_point_count": failures,
        "route_statuses": route_statuses,
        "input_identity": seal,
        "algorithm_selection": context.contract["algorithm_selection"],
        "root_policy_sha256": seal["root_policy_sha256"],
        "hard_residual_math_sha256": seal["hard_residual_math_sha256"],
        "hard_residual_definition": HARD_RESIDUAL_LABEL,
        "vector_block_residual_role": VECTOR_ROLE,
        "v2_immutability": immutability,
        "v3_v2_compact_failure_evidence_immutability": evidence_immutability,
        "noncomputable_failed_routes": context.contract[
            "noncomputable_failed_routes"
        ],
        "scientific_contracts": context.contract["scientific_contracts"],
        "scientific_status_policy": "DETERMINISTIC_NO_WALL_CLOCK_FIELDS",
    }
    base.atomic_write_json(mode_directory / "run_status.json", run_status)
    manifest_path = write_artifact_manifest(
        mode_directory, [spec.route_id for spec in context.specs]
    )
    manifest_hash = sha256_file(manifest_path)
    repeatability = None
    if expected_manifest_sha256 is not None:
        expected = expected_manifest_sha256.upper()
        repeatability = {
            "schema_version": "board20_step5_fullq_svd_candidate_v4_repeatability_v4",
            "mode": mode,
            "baseline_artifact_manifest_sha256": expected,
            "repeat_artifact_manifest_sha256": manifest_hash,
            "scientific_artifacts_match": expected == manifest_hash,
            "status": "PASS" if expected == manifest_hash else "FAIL",
        }
        base.atomic_write_json(
            output_root() / f"{mode}_repeatability.json", repeatability
        )
        if expected != manifest_hash:
            raise RuntimeError(f"Repeated {mode} scientific manifest changed.")
    metadata = {
        "schema_version": "board20_step5_fullq_svd_candidate_v4_run_metadata_v4",
        "mode": mode, "requested_mode": requested_mode,
        "completed_at": base.utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "artifact_manifest_sha256": manifest_hash,
        "repeatability": repeatability,
    }
    base.atomic_write_json(mode_directory / "run_metadata.json", metadata)
    return {
        "status": status_text, "mode": mode, "points": completed,
        "pass": completed - failures, "fail": failures,
        "elapsed_seconds": metadata["elapsed_seconds"],
        "artifact_manifest_sha256": manifest_hash,
        "repeatability": repeatability,
    }


def configure_logging(mode: str) -> Path:
    log_root().mkdir(parents=True, exist_ok=True)
    path = log_root() / f"compute_{mode}.log"
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.FileHandler(path, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", required=True,
        choices=("preflight", "selftest", "pilot", "full", "resume"),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    parser.add_argument("--expected-manifest-sha256")
    parser.add_argument(
        "--explicit-full-authorization",
        action="store_true",
        help="Required in addition to a sealed PASS pilot for full/resume.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.mode)
    started = time.perf_counter()
    if args.checkpoint_every < 1:
        raise ValueError("--checkpoint-every must be positive.")
    if args.mode in ("full", "resume") and not args.explicit_full_authorization:
        raise PermissionError(
            "Full/resume requires --explicit-full-authorization after explicit approval."
        )
    if args.mode == "preflight":
        result = run_preflight()
    elif args.mode == "selftest":
        result = run_selftest()
    else:
        result = run_scientific_mode(
            args.mode, args.overwrite, args.checkpoint_every,
            args.expected_manifest_sha256,
        )
    logging.info(
        "BOARD20_STEP5_FULLQ_SVD_CANDIDATE_V4_%s=%s elapsed=%.3fs",
        args.mode.upper(), result.get("status"), time.perf_counter() - started,
    )
    print(
        json.dumps(
            {key: json_safe(value) for key, value in result.items()},
            ensure_ascii=False, sort_keys=True, separators=(",", ":"),
            allow_nan=False,
        )
    )
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

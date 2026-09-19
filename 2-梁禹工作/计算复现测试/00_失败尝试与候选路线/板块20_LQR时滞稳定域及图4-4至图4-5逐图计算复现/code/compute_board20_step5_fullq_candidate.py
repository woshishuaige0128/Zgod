#!/usr/bin/env python
"""Board20 Step-5 second, isolated, order-selected solver candidate.

The scientific computation reads only:

* this preregistered candidate contract;
* the sealed Step-4 *route-identity* manifest (identity fields only);
* the sealed Step-2 MATLAB-v7.3 workspaces; and
* immutable formula/state-builder definitions from the first independent
  Python source file whose SHA-256 is fixed in the candidate contract.

It never reads a Step-4 rho/pole/stability result, a prior Step-5 result, a
validator result, or a solver-conditioning result.  Solver selection depends
only on the actual contracted matrix order:

* n <= 5: ordinary full-q history companion at every point;
* n > 5: compact scalar-delay augmentation at every point.

All ordinary-eig roots are preserved.  The fixed zero tolerance removes only
numerical zeros created by clearing Laurent denominators.  Multiple zero roots
that numerically split above that tolerance remain in the retained spectrum
and in rho.  A deterministic compact/full-q assignment identifies matched
physical full-q roots for the strict residual gate; unmatched full-q roots are
never deleted and must pass the preregistered count, magnitude, dominance, and
stable-classification safety gates.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import sys
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

import h5py
import numpy as np
import scipy.linalg as sla
from scipy.optimize import linear_sum_assignment

import compute_board20_step5_independent as base


SCRIPT_FILENAME = "compute_board20_step5_fullq_candidate.py"
CONTRACT_FILENAME = "board20_step5_fullq_candidate_contract.json"
MANIFEST_FILENAME = "board20_step4_route_manifest.json"
BASE_COMPUTE_FILENAME = "compute_board20_step5_independent.py"

ALGORITHM_FULL_Q = "FULL_Q_ORDINARY_HISTORY_COMPANION"
ALGORITHM_COMPACT = "COMPACT_SCALAR_DELAY_AUGMENTATION"

CSV_FIELDS = [
    "route_id",
    "route_role",
    "declared_method",
    "division",
    "route_formula",
    "l",
    "j",
    "matrix_order",
    "algorithm_selector_field",
    "algorithm_selector_value",
    "selected_algorithm",
    "selected_order",
    "compact_order",
    "full_q_order",
    "polynomial_degree",
    "clearing_power",
    "raw_root_count",
    "finite_root_count",
    "nonfinite_root_count",
    "zero_root_tolerance",
    "removed_zero_root_count",
    "retained_root_count",
    "compact_pairing_performed",
    "compact_raw_root_count",
    "compact_retained_root_count",
    "compact_zero_root_tolerance",
    "compact_removed_zero_root_count",
    "rho_compact_pairing",
    "stable_compact_pairing",
    "full_q_compact_rho_abs_diff",
    "full_q_compact_root_match_max_relative_diff",
    "near_unit_root_match_max_relative_diff",
    "pairing_diagnostic_role",
    "matched_physical_root_count",
    "theoretical_extra_zero_count",
    "unmatched_full_root_count",
    "unmatched_count_within_theoretical",
    "unmatched_full_max_abs",
    "unmatched_full_below_0p9",
    "unmatched_full_strictly_nondominant",
    "origin_splitting_status",
    "origin_split_gate_role",
    "rho",
    "stable",
    "critical",
    "dominant_root_real",
    "dominant_root_imag",
    "max_gated_polynomial_residual",
    "max_gated_laurent_residual",
    "max_unmatched_full_polynomial_residual",
    "max_unmatched_full_laurent_residual",
    "max_near_unit_polynomial_residual",
    "max_near_unit_laurent_residual",
    "direct_formula_coefficient_relative_difference",
    "stable_classification_match",
    "all_gated_residuals_finite",
    "point_status",
    "failure_code",
]

STRING_FIELDS = {
    "route_id",
    "route_role",
    "declared_method",
    "division",
    "route_formula",
    "algorithm_selector_field",
    "selected_algorithm",
    "origin_splitting_status",
    "origin_split_gate_role",
    "pairing_diagnostic_role",
    "point_status",
    "failure_code",
}
BOOL_FIELDS = {
    "stable",
    "critical",
    "compact_pairing_performed",
    "stable_compact_pairing",
    "unmatched_count_within_theoretical",
    "unmatched_full_below_0p9",
    "unmatched_full_strictly_nondominant",
    "stable_classification_match",
    "all_gated_residuals_finite",
}
INT_FIELDS = {
    "l",
    "j",
    "matrix_order",
    "algorithm_selector_value",
    "selected_order",
    "compact_order",
    "full_q_order",
    "polynomial_degree",
    "clearing_power",
    "raw_root_count",
    "finite_root_count",
    "nonfinite_root_count",
    "removed_zero_root_count",
    "retained_root_count",
    "compact_raw_root_count",
    "compact_retained_root_count",
    "compact_removed_zero_root_count",
    "matched_physical_root_count",
    "theoretical_extra_zero_count",
    "unmatched_full_root_count",
}
RUNTIME_FIELDS = ["route_id", "l", "j", "elapsed_seconds", "point_status"]


@dataclass(frozen=True)
class Context:
    root: Path
    contract: dict[str, Any]
    manifest: dict[str, Any]
    specs: tuple[base.RouteSpec, ...]


@dataclass
class CandidatePoint:
    summary: dict[str, Any]
    raw_roots: np.ndarray
    raw_polynomial_residual: np.ndarray
    raw_laurent_residual: np.ndarray
    raw_finite: np.ndarray
    raw_removed_as_zero: np.ndarray
    raw_matched_physical: np.ndarray
    raw_unmatched_full: np.ndarray
    retained_roots: np.ndarray
    retained_polynomial_residual: np.ndarray
    retained_laurent_residual: np.ndarray
    retained_matched_physical: np.ndarray
    retained_unmatched_full: np.ndarray
    compact_raw_roots: np.ndarray
    compact_raw_polynomial_residual: np.ndarray
    compact_raw_laurent_residual: np.ndarray
    compact_raw_finite: np.ndarray
    compact_raw_removed_as_zero: np.ndarray
    compact_retained_roots: np.ndarray
    compact_retained_polynomial_residual: np.ndarray
    compact_retained_laurent_residual: np.ndarray
    elapsed_seconds: float


def code_root() -> Path:
    return Path(__file__).resolve().parent


def board_root() -> Path:
    return code_root().parent


def output_root() -> Path:
    return board_root() / "outputs" / "step5_fullq_candidate"


def log_root() -> Path:
    return board_root() / "logs" / "step5_fullq_candidate"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def json_safe(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value):
            return None
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
    return value


def matrix_payload_sha256(matrices: base.Matrices) -> str:
    digest = hashlib.sha256()
    names = ("M", "C1", "K1", "C2", "K2", "al", "dt", "S", "DeltaC", "DeltaK")
    for name in names:
        value = getattr(matrices, name)
        if value is None:
            continue
        array = np.asarray(value, dtype="<f8", order="C")
        digest.update(name.encode("utf-8"))
        digest.update(canonical_json_bytes(list(array.shape)))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()


def selected_algorithm(matrix_order: int) -> str:
    return ALGORITHM_FULL_Q if matrix_order <= 5 else ALGORITHM_COMPACT


def safe_workspace(root: Path, relpath: str) -> Path:
    return base.safe_relative_path(root, relpath, "outputs/step2_runs")


def load_context() -> Context:
    root = board_root()
    contract_path = code_root() / CONTRACT_FILENAME
    manifest_path = code_root() / MANIFEST_FILENAME
    base_path = code_root() / BASE_COMPUTE_FILENAME
    contract = read_json(contract_path)
    if contract.get("schema_version") != "board20_step5_fullq_candidate_contract_v2":
        raise ValueError("Unexpected candidate contract schema.")
    if sha256_file(manifest_path) != contract["route_manifest_sha256"]:
        raise ValueError("Route-identity manifest SHA-256 mismatch.")
    if sha256_file(base_path) != contract["base_compute_sha256"]:
        raise ValueError("Immutable base compute definition SHA-256 mismatch.")
    manifest = read_json(manifest_path)
    if manifest.get("schema_version") != "board20_step4_route_manifest_v1":
        raise ValueError("Unexpected route manifest schema.")

    manifest_routes = {item["route_id"]: item for item in manifest["routes"]}
    contract_routes = list(contract["routes"])
    ids = [item["route_id"] for item in contract_routes]
    if len(ids) != 5 or set(ids) != set(manifest_routes):
        raise ValueError("Candidate route identity is not exactly the sealed five routes.")

    specs: list[base.RouteSpec] = []
    for item in contract_routes:
        route_id = item["route_id"]
        source = manifest_routes[route_id]
        for field in ("route_role", "declared_method", "division", "route_formula", "workspace_relpath"):
            if source[field] != item[field]:
                raise ValueError(f"Manifest/contract identity mismatch: {route_id}.{field}")
        restored_map = {
            logical: source["matrix_variable_map"][logical]
            for logical in item["matrix_variables"]
        }
        if restored_map != item["matrix_variables"]:
            raise ValueError(f"Manifest/contract matrix map mismatch: {route_id}")
        workspace_contracts = [
            entry
            for entry in source["file_contracts"]
            if entry.get("role") == "workspace_complete"
        ]
        if len(workspace_contracts) != 1:
            raise ValueError(f"Exactly one workspace_complete identity is required: {route_id}")
        if workspace_contracts[0]["sha256"] != item["workspace_sha256"]:
            raise ValueError(f"Manifest workspace seal mismatch: {route_id}")
        workspace = safe_workspace(root, item["workspace_relpath"])
        if not workspace.is_file() or sha256_file(workspace) != item["workspace_sha256"]:
            raise ValueError(f"Sealed workspace changed or is missing: {route_id}")
        pilot = tuple(tuple(map(int, pair)) for pair in contract["pilot_points"][route_id])
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
                delay_dofs=tuple(index - 1 for index in item["delay_dofs_matlab_1_based"]),
                pilot_points=pilot,
            )
        )
    return Context(root=root, contract=contract, manifest=manifest, specs=tuple(specs))


def build_input_seal(context: Context) -> dict[str, Any]:
    matrices = {
        spec.route_id: base.load_route_matrices(context.root, spec)
        for spec in context.specs
    }
    return {
        "schema_version": "board20_step5_fullq_candidate_input_seal_v2",
        "candidate_script_sha256": sha256_file(code_root() / SCRIPT_FILENAME),
        "candidate_contract_sha256": sha256_file(code_root() / CONTRACT_FILENAME),
        "route_manifest_sha256": sha256_file(code_root() / MANIFEST_FILENAME),
        "base_compute_sha256": sha256_file(code_root() / BASE_COMPUTE_FILENAME),
        "algorithm_selection_sha256": sha256_json(context.contract["algorithm_selection"]),
        "root_policy_sha256": sha256_json(context.contract["root_and_pairing_policy"]),
        "workspace_sha256": {spec.route_id: spec.workspace_sha256 for spec in context.specs},
        "matrix_payload_sha256": {
            route_id: matrix_payload_sha256(value) for route_id, value in matrices.items()
        },
        "route_order": [spec.route_id for spec in context.specs],
    }


def verify_input_seal() -> tuple[Context, dict[str, Any]]:
    context = load_context()
    path = output_root() / "input_seal.json"
    if not path.is_file():
        raise FileNotFoundError("Run PASS preflight to create input_seal.json first.")
    observed = read_json(path)
    expected = build_input_seal(context)
    if observed != expected:
        raise RuntimeError("Candidate code/contract/dependency/manifest/workspace identity changed after sealing.")
    return context, observed


def append_check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any) -> None:
    checks.append({"check_id": check_id, "status": "PASS" if passed else "FAIL", "detail": json_safe(detail)})


def contracts_status(context: Context) -> dict[str, Any]:
    failed_manifest = {item["route_id"]: item for item in context.manifest["failed_routes"]}
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
        "schema_version": "board20_step5_fullq_candidate_contracts_status_v2",
        "scientific_contracts": context.contract["scientific_contracts"],
        "noncomputable_failed_routes": failed,
        "candidate_output_policy": "Only five calculable route IDs may receive route directories.",
    }


def run_preflight() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    try:
        context = load_context()
        append_check(checks, "candidate_contract_schema", True, context.contract["schema_version"])
        append_check(checks, "route_manifest_hash", True, context.contract["route_manifest_sha256"])
        append_check(checks, "base_compute_hash", True, context.contract["base_compute_sha256"])
        append_check(checks, "route_count", len(context.specs) == 5, len(context.specs))
        append_check(
            checks,
            "forbidden_computation_inputs_preregistered",
            len(context.contract["forbidden_computation_inputs"]) >= 8,
            context.contract["forbidden_computation_inputs"],
        )
        required = {tuple(point) for point in context.contract["required_pilot_points"]}
        failed_ids = {item["route_id"] for item in context.contract["noncomputable_failed_routes"]}
        manifest_failed_ids = {item["route_id"] for item in context.manifest["failed_routes"]}
        append_check(checks, "four_failed_route_identity", failed_ids == manifest_failed_ids and len(failed_ids) == 4, sorted(failed_ids))
        append_check(
            checks,
            "failed_routes_do_not_create",
            all(item["candidate_policy"] == "DO_NOT_CREATE" for item in context.contract["noncomputable_failed_routes"]),
            "DO_NOT_CREATE",
        )
        existing_failed_dirs = [
            path.as_posix()
            for route_id in sorted(failed_ids)
            for path in output_root().glob(f"**/{route_id}")
            if path.is_dir()
        ] if output_root().exists() else []
        append_check(checks, "failed_route_directories_absent", not existing_failed_dirs, existing_failed_dirs)

        actual_algorithms: dict[str, str] = {}
        matrix_payloads: dict[str, str] = {}
        for spec in context.specs:
            matrices = base.load_route_matrices(context.root, spec)
            n = int(matrices.M.shape[0])
            algorithm = selected_algorithm(n)
            actual_algorithms[spec.route_id] = algorithm
            matrix_payloads[spec.route_id] = matrix_payload_sha256(matrices)
            expected_n = int(context.contract["algorithm_selection"]["expected_matrix_orders"][spec.route_id])
            expected_algorithm = context.contract["algorithm_selection"]["expected_selected_algorithms"][spec.route_id]
            append_check(checks, f"{spec.route_id}.matrix_order", n == expected_n, n)
            append_check(checks, f"{spec.route_id}.algorithm_by_order", algorithm == expected_algorithm, algorithm)
            append_check(
                checks,
                f"{spec.route_id}.workspace_hash",
                sha256_file(safe_workspace(context.root, spec.workspace_relpath)) == spec.workspace_sha256,
                spec.workspace_sha256,
            )
            finite = all(
                np.all(np.isfinite(value))
                for value in (matrices.M, matrices.C1, matrices.K1, matrices.C2, matrices.K2, matrices.al)
            )
            append_check(checks, f"{spec.route_id}.finite_matrices", finite, "finite")
            components = base.build_components(matrices, spec.route_formula)
            right_division_residual = np.linalg.norm(
                (components.T * (matrices.dt * matrices.dt)) @ matrices.al - matrices.M,
                ord="fro",
            ) / max(1.0, np.linalg.norm(matrices.M, ord="fro"))
            append_check(checks, f"{spec.route_id}.right_division_residual", right_division_residual <= 1e-12, float(right_division_residual))
            append_check(checks, f"{spec.route_id}.pilot_unique", len(spec.pilot_points) == len(set(spec.pilot_points)), len(spec.pilot_points))
            if n <= 5:
                append_check(checks, f"{spec.route_id}.required_four_points", required.issubset(set(spec.pilot_points)), sorted(required))

        append_check(
            checks,
            "algorithm_selection_only_by_matrix_order",
            actual_algorithms == context.contract["algorithm_selection"]["expected_selected_algorithms"],
            actual_algorithms,
        )
        append_check(
            checks,
            "master_contract_not_closed",
            context.contract["scientific_contracts"]["master_thesis_route"]["status"] == "CONTRACT_NOT_CLOSED",
            context.contract["scientific_contracts"]["master_thesis_route"]["status"],
        )
        append_check(
            checks,
            "manuscript_contract_not_closed",
            context.contract["scientific_contracts"]["manuscript_0824_route"]["status"] == "CONTRACT_NOT_CLOSED",
            context.contract["scientific_contracts"]["manuscript_0824_route"]["status"],
        )

        passed = all(item["status"] == "PASS" for item in checks)
        seal = build_input_seal(context)
        seal_path = output_root() / "input_seal.json"
        if passed:
            if seal_path.is_file() and read_json(seal_path) != seal:
                raise RuntimeError("An incompatible candidate input seal already exists; do not overwrite it.")
            if not seal_path.is_file():
                base.atomic_write_json(seal_path, seal)
            base.atomic_write_json(output_root() / "contracts_status.json", contracts_status(context))
        document = {
            "schema_version": "board20_step5_fullq_candidate_preflight_v2",
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
            "schema_version": "board20_step5_fullq_candidate_preflight_v2",
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


def zero_tolerance(roots: np.ndarray, finite: np.ndarray, order: int) -> float:
    magnitudes = np.abs(roots[finite])
    nonzero = magnitudes[magnitudes > 0]
    scale = max(1.0, float(np.median(nonzero))) if nonzero.size else 1.0
    return max(1e-12, 100.0 * np.finfo(float).eps * max(1, order) * scale)


def solve_selected_spectrum(
    transition: np.ndarray,
    n: int,
    polynomial: Sequence[np.ndarray],
    direct_terms: Sequence[tuple[int, np.ndarray]],
    clearing_power: int,
) -> tuple[
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    np.ndarray,
    float,
    int,
    float,
    bool,
    bool,
    complex,
]:
    roots, vectors = sla.eig(
        transition,
        left=False,
        right=True,
        overwrite_a=True,
        check_finite=False,
    )
    roots = np.asarray(roots, dtype=np.complex128).reshape(-1)
    finite = np.isfinite(roots.real) & np.isfinite(roots.imag)
    tolerance = zero_tolerance(roots, finite, transition.shape[0])
    removed = finite & (np.abs(roots) <= tolerance) if clearing_power > 0 else np.zeros(roots.shape, dtype=bool)

    raw_poly = np.full(roots.shape, np.nan, dtype=float)
    raw_laurent = np.full(roots.shape, np.nan, dtype=float)
    for index in np.flatnonzero(finite):
        physical = vectors[:n, index]
        raw_poly[index] = base.polynomial_residual(polynomial, roots[index], physical)
        raw_laurent[index] = base.direct_laurent_residual(direct_terms, roots[index], physical)

    retained_indices = np.flatnonzero(finite & ~removed)
    retained = roots[retained_indices]
    if retained.size == 0:
        raise FloatingPointError("No finite root remains above the fixed zero tolerance.")
    retained_poly = raw_poly[retained_indices]
    retained_laurent = raw_laurent[retained_indices]
    magnitudes = np.abs(retained)
    dominant_index = int(np.argmax(magnitudes))
    rho = float(magnitudes[dominant_index])
    if not (math.isfinite(rho) and rho > 0):
        raise FloatingPointError("rho is not finite and strictly positive.")
    return (
        roots,
        raw_poly,
        raw_laurent,
        finite,
        removed,
        retained_indices,
        retained,
        retained_poly,
        retained_laurent,
        float(tolerance),
        int(np.count_nonzero(removed)),
        rho,
        bool(rho < 1.0),
        bool(abs(rho - 1.0) <= 1e-8),
        complex(retained[dominant_index]),
    )


def deterministic_physical_pairing(
    compact_roots: np.ndarray,
    full_roots: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    """Pair every retained compact root to one retained full-q root.

    The fixed cost and original eig-array row/column order are preregistered in
    the v2 contract.  Unselected full-q columns are returned as unmatched
    cleared-origin multiplicity diagnostics; no root is removed from rho.
    """
    compact_roots = np.asarray(compact_roots, dtype=np.complex128).reshape(-1)
    full_roots = np.asarray(full_roots, dtype=np.complex128).reshape(-1)
    if compact_roots.size == 0 or full_roots.size < compact_roots.size:
        raise FloatingPointError(
            "Retained full-q root count is smaller than retained compact root count."
        )
    denominator = np.maximum(
        1.0,
        np.maximum(np.abs(compact_roots)[:, None], np.abs(full_roots)[None, :]),
    )
    costs = np.abs(compact_roots[:, None] - full_roots[None, :]) / denominator
    row_indices, column_indices = linear_sum_assignment(costs)
    if row_indices.size != compact_roots.size:
        raise FloatingPointError("Optimal pairing did not cover every compact root.")
    matched = np.zeros(full_roots.size, dtype=bool)
    matched[column_indices] = True
    unmatched = ~matched
    maximum_cost = float(np.max(costs[row_indices, column_indices]))
    return matched, unmatched, maximum_cost


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
        coefficients = base.build_coefficient_map(spec, components, l_value, j_value)
        direct_terms = base.direct_laurent_terms(spec, components, l_value, j_value)
        polynomial, clearing_power, degree = base.polynomial_from_coefficients(coefficients)
        formula_difference = base.formula_coefficient_relative_difference(
            spec, components, coefficients, l_value, j_value
        )
        compact_order = 2 * n + l_value + j_value
        full_q_order = n * (max(l_value, j_value) + 2)
        if algorithm == ALGORITHM_FULL_Q:
            transition = base.build_full_q_history_matrix(
                components, coefficients, l_value, j_value
            )
        else:
            transition = base.build_compact_state_matrix(
                spec, components, l_value, j_value
            )
        selected_order = int(transition.shape[0])
        (
            raw_roots,
            raw_poly,
            raw_laurent,
            raw_finite,
            raw_removed,
            retained_indices,
            retained_roots,
            retained_poly,
            retained_laurent,
            tolerance,
            removed_count,
            rho,
            stable,
            critical,
            dominant,
        ) = solve_selected_spectrum(
            transition, n, polynomial, direct_terms, clearing_power
        )

        empty_c = np.empty(0, dtype=np.complex128)
        empty_f = np.empty(0, dtype=float)
        empty_b = np.empty(0, dtype=bool)
        compact_raw_roots = empty_c
        compact_raw_poly = empty_f
        compact_raw_laurent = empty_f
        compact_raw_finite = empty_b
        compact_raw_removed = empty_b
        compact_retained_roots = empty_c
        compact_retained_poly = empty_f
        compact_retained_laurent = empty_f

        theoretical_extra = max(0, full_q_order - compact_order)
        raw_matched = np.zeros(raw_roots.shape, dtype=bool)
        raw_unmatched = np.zeros(raw_roots.shape, dtype=bool)
        retained_matched = np.zeros(retained_roots.shape, dtype=bool)
        retained_unmatched = np.zeros(retained_roots.shape, dtype=bool)
        pairing_performed = algorithm == ALGORITHM_FULL_Q
        compact_tolerance: float | None = None
        compact_removed_count = 0
        compact_rho: float | None = None
        compact_stable = stable
        rho_difference: float | None = None
        root_match_difference: float | None = None
        near_unit_match_difference: float | None = None
        unmatched_max_abs: float | None = None
        max_unmatched_poly: float | None = None
        max_unmatched_laurent: float | None = None
        pairing_role = (
            "DIAGNOSTIC_ONLY_KNOWN_COMPACT_CONDITIONING"
            if pairing_performed
            else "NOT_APPLICABLE_COMPACT_SELECTED"
        )

        if pairing_performed:
            compact_transition = base.build_compact_state_matrix(
                spec, components, l_value, j_value
            )
            (
                compact_raw_roots,
                compact_raw_poly,
                compact_raw_laurent,
                compact_raw_finite,
                compact_raw_removed,
                _compact_retained_indices,
                compact_retained_roots,
                compact_retained_poly,
                compact_retained_laurent,
                compact_tolerance,
                compact_removed_count,
                compact_rho,
                compact_stable,
                _compact_critical,
                _compact_dominant,
            ) = solve_selected_spectrum(
                compact_transition, n, polynomial, direct_terms, clearing_power
            )
            retained_matched, retained_unmatched, root_match_difference = (
                deterministic_physical_pairing(
                    compact_retained_roots, retained_roots
                )
            )
            raw_matched[retained_indices[retained_matched]] = True
            raw_unmatched[retained_indices[retained_unmatched]] = True
            rho_difference = abs(rho - float(compact_rho))
            near_threshold = float(gates["near_unit_root_threshold"])
            near_unit_match_difference = base.match_root_sets(
                compact_retained_roots[
                    np.abs(compact_retained_roots) >= near_threshold
                ],
                retained_roots[np.abs(retained_roots) >= near_threshold],
            )
            if np.any(retained_unmatched):
                unmatched_max_abs = float(
                    np.max(np.abs(retained_roots[retained_unmatched]))
                )
                max_unmatched_poly = float(
                    np.max(retained_poly[retained_unmatched])
                )
                max_unmatched_laurent = float(
                    np.max(retained_laurent[retained_unmatched])
                )
            origin_status = (
                "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING"
                if np.any(retained_unmatched)
                else "PASS_NO_UNMATCHED_FULL_ROOT"
            )
        else:
            retained_matched[:] = True
            raw_matched[retained_indices] = True
            origin_status = "NOT_APPLICABLE_COMPACT_SELECTED"

        matched_count = int(np.count_nonzero(retained_matched))
        unmatched_count = int(np.count_nonzero(retained_unmatched))
        unmatched_within_theoretical = bool(unmatched_count <= theoretical_extra)
        unmatched_below_limit = bool(
            unmatched_max_abs is None
            or unmatched_max_abs
            < float(gates["unmatched_full_max_abs_strictly_below"])
        )
        unmatched_nondominant = bool(
            unmatched_max_abs is None or unmatched_max_abs < rho
        )
        stable_match = bool(stable == compact_stable)

        gated_poly = retained_poly[retained_matched]
        gated_laurent = retained_laurent[retained_matched]
        if gated_poly.size == 0:
            raise FloatingPointError("No deterministically matched physical root remains.")
        max_gated_poly = float(np.max(gated_poly))
        max_gated_laurent = float(np.max(gated_laurent))
        all_gated_finite = bool(
            np.all(np.isfinite(gated_poly))
            and np.all(np.isfinite(gated_laurent))
        )
        near_threshold = float(gates["near_unit_root_threshold"])
        near = retained_matched & (np.abs(retained_roots) >= near_threshold)
        near_poly = float(np.max(retained_poly[near])) if np.any(near) else None
        near_laurent = float(np.max(retained_laurent[near])) if np.any(near) else None

        failures: list[str] = []
        expected_order = full_q_order if n <= 5 else compact_order
        if selected_order != expected_order:
            failures.append("ORDER_SELECTED_MATRIX_MISMATCH")
        if raw_roots.size != selected_order:
            failures.append("RAW_ROOT_COUNT_MISMATCH")
        if np.count_nonzero(~raw_finite):
            failures.append("NONFINITE_SELECTED_ROOT")
        if not all_gated_finite:
            failures.append("NONFINITE_GATED_PHYSICAL_RESIDUAL")
        if algorithm == ALGORITHM_FULL_Q:
            poly_gate = float(gates["max_matched_physical_polynomial_residual"])
            laurent_gate = float(
                gates["max_matched_physical_direct_laurent_residual"]
            )
        else:
            poly_gate = float(gates["max_selected_compact_polynomial_residual"])
            laurent_gate = float(
                gates["max_selected_compact_direct_laurent_residual"]
            )
        if max_gated_poly > poly_gate:
            failures.append("GATED_PHYSICAL_POLYNOMIAL_RESIDUAL")
        if max_gated_laurent > laurent_gate:
            failures.append("GATED_PHYSICAL_LAURENT_RESIDUAL")
        if pairing_performed:
            if not unmatched_within_theoretical:
                failures.append("UNMATCHED_FULL_COUNT_EXCEEDS_THEORETICAL_EXTRA")
            if not unmatched_below_limit:
                failures.append("UNMATCHED_FULL_ROOT_REACHES_NEAR_UNIT_REGION")
            if not unmatched_nondominant:
                failures.append("UNMATCHED_FULL_ROOT_IS_DOMINANT")
            if not stable_match:
                failures.append("FULL_Q_COMPACT_STABLE_CLASSIFICATION_MISMATCH")
        if formula_difference > float(gates["direct_formula_coefficient_relative_difference"]):
            failures.append("DIRECT_FORMULA_COEFFICIENT_MISMATCH")

        summary = {
            "route_id": spec.route_id,
            "route_role": spec.route_role,
            "declared_method": spec.declared_method,
            "division": spec.division,
            "route_formula": spec.route_formula,
            "l": int(l_value),
            "j": int(j_value),
            "matrix_order": n,
            "algorithm_selector_field": "matrix_order",
            "algorithm_selector_value": n,
            "selected_algorithm": algorithm,
            "selected_order": selected_order,
            "compact_order": compact_order,
            "full_q_order": full_q_order,
            "polynomial_degree": int(degree),
            "clearing_power": int(clearing_power),
            "raw_root_count": int(raw_roots.size),
            "finite_root_count": int(np.count_nonzero(raw_finite)),
            "nonfinite_root_count": int(np.count_nonzero(~raw_finite)),
            "zero_root_tolerance": float(tolerance),
            "removed_zero_root_count": int(removed_count),
            "retained_root_count": int(retained_roots.size),
            "compact_pairing_performed": pairing_performed,
            "compact_raw_root_count": int(compact_raw_roots.size),
            "compact_retained_root_count": int(compact_retained_roots.size),
            "compact_zero_root_tolerance": compact_tolerance,
            "compact_removed_zero_root_count": int(compact_removed_count),
            "rho_compact_pairing": compact_rho,
            "stable_compact_pairing": bool(compact_stable),
            "full_q_compact_rho_abs_diff": rho_difference,
            "full_q_compact_root_match_max_relative_diff": root_match_difference,
            "near_unit_root_match_max_relative_diff": near_unit_match_difference,
            "pairing_diagnostic_role": pairing_role,
            "matched_physical_root_count": matched_count,
            "theoretical_extra_zero_count": int(theoretical_extra),
            "unmatched_full_root_count": unmatched_count,
            "unmatched_count_within_theoretical": unmatched_within_theoretical,
            "unmatched_full_max_abs": unmatched_max_abs,
            "unmatched_full_below_0p9": unmatched_below_limit,
            "unmatched_full_strictly_nondominant": unmatched_nondominant,
            "origin_splitting_status": origin_status,
            "origin_split_gate_role": "DIAGNOSTIC_ONLY_NO_ROOT_REMOVAL",
            "rho": rho,
            "stable": stable,
            "critical": critical,
            "dominant_root_real": float(dominant.real),
            "dominant_root_imag": float(dominant.imag),
            "max_gated_polynomial_residual": max_gated_poly,
            "max_gated_laurent_residual": max_gated_laurent,
            "max_unmatched_full_polynomial_residual": max_unmatched_poly,
            "max_unmatched_full_laurent_residual": max_unmatched_laurent,
            "max_near_unit_polynomial_residual": near_poly,
            "max_near_unit_laurent_residual": near_laurent,
            "direct_formula_coefficient_relative_difference": float(formula_difference),
            "stable_classification_match": stable_match,
            "all_gated_residuals_finite": all_gated_finite,
            "point_status": "PASS" if not failures else "FAIL",
            "failure_code": ";".join(failures),
        }
        return CandidatePoint(
            summary=summary,
            raw_roots=raw_roots,
            raw_polynomial_residual=raw_poly,
            raw_laurent_residual=raw_laurent,
            raw_finite=raw_finite,
            raw_removed_as_zero=raw_removed,
            raw_matched_physical=raw_matched,
            raw_unmatched_full=raw_unmatched,
            retained_roots=retained_roots,
            retained_polynomial_residual=retained_poly,
            retained_laurent_residual=retained_laurent,
            retained_matched_physical=retained_matched,
            retained_unmatched_full=retained_unmatched,
            compact_raw_roots=compact_raw_roots,
            compact_raw_polynomial_residual=compact_raw_poly,
            compact_raw_laurent_residual=compact_raw_laurent,
            compact_raw_finite=compact_raw_finite,
            compact_raw_removed_as_zero=compact_raw_removed,
            compact_retained_roots=compact_retained_roots,
            compact_retained_polynomial_residual=compact_retained_poly,
            compact_retained_laurent_residual=compact_retained_laurent,
            elapsed_seconds=time.perf_counter() - started,
        )
    except Exception as exc:
        n = int(matrices.M.shape[0])
        algorithm = selected_algorithm(n)
        compact_order = 2 * n + l_value + j_value
        full_q_order = n * (max(l_value, j_value) + 2)
        summary = {
            field: "" for field in CSV_FIELDS
        }
        summary.update(
            {
                "route_id": spec.route_id,
                "route_role": spec.route_role,
                "declared_method": spec.declared_method,
                "division": spec.division,
                "route_formula": spec.route_formula,
                "l": int(l_value),
                "j": int(j_value),
                "matrix_order": n,
                "algorithm_selector_field": "matrix_order",
                "algorithm_selector_value": n,
                "selected_algorithm": algorithm,
                "selected_order": full_q_order if n <= 5 else compact_order,
                "compact_order": compact_order,
                "full_q_order": full_q_order,
                "raw_root_count": 0,
                "finite_root_count": 0,
                "nonfinite_root_count": 0,
                "removed_zero_root_count": 0,
                "retained_root_count": 0,
                "compact_pairing_performed": algorithm == ALGORITHM_FULL_Q,
                "compact_raw_root_count": 0,
                "compact_retained_root_count": 0,
                "compact_removed_zero_root_count": 0,
                "stable_compact_pairing": False,
                "pairing_diagnostic_role": "DIAGNOSTIC_ONLY_KNOWN_COMPACT_CONDITIONING" if algorithm == ALGORITHM_FULL_Q else "NOT_APPLICABLE_COMPACT_SELECTED",
                "matched_physical_root_count": 0,
                "theoretical_extra_zero_count": max(0, full_q_order - compact_order),
                "unmatched_full_root_count": 0,
                "unmatched_count_within_theoretical": False,
                "unmatched_full_below_0p9": False,
                "unmatched_full_strictly_nondominant": False,
                "origin_splitting_status": "SOLVE_FAILED",
                "origin_split_gate_role": "DIAGNOSTIC_ONLY_NO_ROOT_REMOVAL",
                "stable": False,
                "critical": False,
                "stable_classification_match": False,
                "all_gated_residuals_finite": False,
                "point_status": "FAIL",
                "failure_code": f"{type(exc).__name__}:{exc}",
            }
        )
        empty_c = np.empty(0, dtype=np.complex128)
        empty_f = np.empty(0, dtype=float)
        empty_b = np.empty(0, dtype=bool)
        return CandidatePoint(
            summary=summary,
            raw_roots=empty_c,
            raw_polynomial_residual=empty_f,
            raw_laurent_residual=empty_f,
            raw_finite=empty_b,
            raw_removed_as_zero=empty_b,
            raw_matched_physical=empty_b,
            raw_unmatched_full=empty_b,
            retained_roots=empty_c,
            retained_polynomial_residual=empty_f,
            retained_laurent_residual=empty_f,
            retained_matched_physical=empty_b,
            retained_unmatched_full=empty_b,
            compact_raw_roots=empty_c,
            compact_raw_polynomial_residual=empty_f,
            compact_raw_laurent_residual=empty_f,
            compact_raw_finite=empty_b,
            compact_raw_removed_as_zero=empty_b,
            compact_retained_roots=empty_c,
            compact_retained_polynomial_residual=empty_f,
            compact_retained_laurent_residual=empty_f,
            elapsed_seconds=time.perf_counter() - started,
        )


def run_selftest() -> dict[str, Any]:
    context, seal = verify_input_seal()
    require_gate(
        output_root() / "preflight.json",
        "board20_step5_fullq_candidate_preflight_v2",
    )
    gates = context.contract["numeric_gates"]
    checks: list[dict[str, Any]] = []
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
        if formula == "ORI_DIV1_H_RIGHT" and n != 6:
            raise AssertionError("Synthetic right-H test requires delay DOF 6.")
        l_value, j_value = point
        result = solve_point(spec, matrices, l_value, j_value, gates)
        prefix = f"n{n}.{formula}.{l_value}.{j_value}"
        expected_algorithm = selected_algorithm(n)
        append_check(checks, prefix + ".algorithm", result.summary["selected_algorithm"] == expected_algorithm, result.summary["selected_algorithm"])
        append_check(checks, prefix + ".point_status", result.summary["point_status"] == "PASS", result.summary["failure_code"])
        append_check(checks, prefix + ".root_count", result.summary["raw_root_count"] == result.summary["selected_order"], result.summary["raw_root_count"])
        append_check(checks, prefix + ".rho", math.isfinite(float(result.summary["rho"])) and float(result.summary["rho"]) > 0, result.summary["rho"])
        poly_gate = float(
            gates["max_matched_physical_polynomial_residual"]
            if n <= 5
            else gates["max_selected_compact_polynomial_residual"]
        )
        laurent_gate = float(
            gates["max_matched_physical_direct_laurent_residual"]
            if n <= 5
            else gates["max_selected_compact_direct_laurent_residual"]
        )
        append_check(checks, prefix + ".poly_residual", float(result.summary["max_gated_polynomial_residual"]) <= poly_gate, result.summary["max_gated_polynomial_residual"])
        append_check(checks, prefix + ".laurent_residual", float(result.summary["max_gated_laurent_residual"]) <= laurent_gate, result.summary["max_gated_laurent_residual"])
        append_check(checks, prefix + ".formula_identity", float(result.summary["direct_formula_coefficient_relative_difference"]) <= float(gates["direct_formula_coefficient_relative_difference"]), result.summary["direct_formula_coefficient_relative_difference"])
        append_check(checks, prefix + ".pairing_mode", bool(result.summary["compact_pairing_performed"]) == (n <= 5), result.summary["compact_pairing_performed"])
        append_check(checks, prefix + ".unmatched_count", bool(result.summary["unmatched_count_within_theoretical"]), [result.summary["unmatched_full_root_count"], result.summary["theoretical_extra_zero_count"]])
        append_check(checks, prefix + ".unmatched_below_0p9", bool(result.summary["unmatched_full_below_0p9"]), result.summary["unmatched_full_max_abs"])
        append_check(checks, prefix + ".unmatched_nondominant", bool(result.summary["unmatched_full_strictly_nondominant"]), [result.summary["unmatched_full_max_abs"], result.summary["rho"]])
        append_check(checks, prefix + ".stable_match", bool(result.summary["stable_classification_match"]), [result.summary["stable"], result.summary["stable_compact_pairing"]])

    append_check(checks, "selector_n5", selected_algorithm(5) == ALGORITHM_FULL_Q, selected_algorithm(5))
    append_check(checks, "selector_n6", selected_algorithm(6) == ALGORITHM_COMPACT, selected_algorithm(6))
    append_check(checks, "selector_n15", selected_algorithm(15) == ALGORITHM_COMPACT, selected_algorithm(15))
    status = "PASS" if all(item["status"] == "PASS" for item in checks) else "FAIL"
    document = {
        "schema_version": "board20_step5_fullq_candidate_selftest_v2",
        "status": status,
        "check_count": len(checks),
        "pass_count": sum(item["status"] == "PASS" for item in checks),
        "fail_count": sum(item["status"] == "FAIL" for item in checks),
        "checks": checks,
        "input_seal_sha256": sha256_file(output_root() / "input_seal.json"),
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
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


def concatenate_or_empty(arrays: Sequence[np.ndarray], dtype: np.dtype) -> np.ndarray:
    return np.concatenate(arrays).astype(dtype, copy=False) if arrays and sum(array.size for array in arrays) else np.empty(0, dtype=dtype)


def write_root_group(
    parent: h5py.Group,
    name: str,
    roots: Sequence[np.ndarray],
    polynomial: Sequence[np.ndarray],
    laurent: Sequence[np.ndarray],
    finite: Sequence[np.ndarray],
    removed: Sequence[np.ndarray],
    matched_physical: Sequence[np.ndarray],
    unmatched_full: Sequence[np.ndarray],
) -> None:
    group = parent.create_group(name)
    offsets, counts = ragged_layout(roots)
    joined_roots = concatenate_or_empty(roots, np.complex128)
    kwargs = {"compression": "gzip", "compression_opts": 4, "shuffle": True}
    group.create_dataset("offset", data=offsets, **kwargs)
    group.create_dataset("count", data=counts, **kwargs)
    group.create_dataset("real", data=joined_roots.real.astype(np.float64), **kwargs)
    group.create_dataset("imag", data=joined_roots.imag.astype(np.float64), **kwargs)
    group.create_dataset("polynomial_residual", data=concatenate_or_empty(polynomial, np.float64), **kwargs)
    group.create_dataset("laurent_residual", data=concatenate_or_empty(laurent, np.float64), **kwargs)
    group.create_dataset("finite", data=concatenate_or_empty(finite, np.uint8), **kwargs)
    group.create_dataset("removed_as_zero", data=concatenate_or_empty(removed, np.uint8), **kwargs)
    group.create_dataset("matched_physical", data=concatenate_or_empty(matched_physical, np.uint8), **kwargs)
    group.create_dataset("unmatched_full", data=concatenate_or_empty(unmatched_full, np.uint8), **kwargs)


def atomic_write_results_h5(path: Path, results: Sequence[CandidatePoint]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    if temporary.exists():
        temporary.unlink()
    with h5py.File(temporary, "w", libver="earliest", track_order=False) as handle:
        points = handle.create_group("points")
        for field in CSV_FIELDS:
            values = [item.summary.get(field) for item in results]
            if field in STRING_FIELDS:
                points.create_dataset(field, data=np.asarray(["" if value is None else str(value) for value in values], dtype=object), dtype=h5_string_dtype())
            elif field in BOOL_FIELDS:
                points.create_dataset(field, data=np.asarray([bool(value) for value in values], dtype=np.uint8))
            elif field in INT_FIELDS:
                points.create_dataset(field, data=np.asarray([int(value) if value not in (None, "") else -1 for value in values], dtype=np.int64))
            else:
                points.create_dataset(field, data=np.asarray([float(value) if value not in (None, "") else math.nan for value in values], dtype=np.float64))
        records = [json.dumps({key: json_safe(value) for key, value in item.summary.items()}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False) for item in results]
        points.create_dataset("record_json", data=np.asarray(records, dtype=object), dtype=h5_string_dtype())
        selected = handle.create_group("selected")
        write_root_group(
            selected,
            "raw",
            [item.raw_roots for item in results],
            [item.raw_polynomial_residual for item in results],
            [item.raw_laurent_residual for item in results],
            [item.raw_finite for item in results],
            [item.raw_removed_as_zero for item in results],
            [item.raw_matched_physical for item in results],
            [item.raw_unmatched_full for item in results],
        )
        write_root_group(
            selected,
            "retained",
            [item.retained_roots for item in results],
            [item.retained_polynomial_residual for item in results],
            [item.retained_laurent_residual for item in results],
            [np.ones(item.retained_roots.shape, dtype=bool) for item in results],
            [np.zeros(item.retained_roots.shape, dtype=bool) for item in results],
            [item.retained_matched_physical for item in results],
            [item.retained_unmatched_full for item in results],
        )
        compact = handle.create_group("pairing_compact")
        write_root_group(
            compact,
            "raw",
            [item.compact_raw_roots for item in results],
            [item.compact_raw_polynomial_residual for item in results],
            [item.compact_raw_laurent_residual for item in results],
            [item.compact_raw_finite for item in results],
            [item.compact_raw_removed_as_zero for item in results],
            [np.zeros(item.compact_raw_roots.shape, dtype=bool) for item in results],
            [np.zeros(item.compact_raw_roots.shape, dtype=bool) for item in results],
        )
        write_root_group(
            compact,
            "retained",
            [item.compact_retained_roots for item in results],
            [item.compact_retained_polynomial_residual for item in results],
            [item.compact_retained_laurent_residual for item in results],
            [np.ones(item.compact_retained_roots.shape, dtype=bool) for item in results],
            [np.zeros(item.compact_retained_roots.shape, dtype=bool) for item in results],
            [np.zeros(item.compact_retained_roots.shape, dtype=bool) for item in results],
            [np.zeros(item.compact_retained_roots.shape, dtype=bool) for item in results],
        )
        handle.flush()
    base.replace_with_retry(temporary, path)


def read_root_slice(group: h5py.Group, index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    offset = int(group["offset"][index])
    count = int(group["count"][index])
    selected = slice(offset, offset + count)
    roots = group["real"][selected] + 1j * group["imag"][selected]
    return (
        np.asarray(roots, dtype=np.complex128),
        np.asarray(group["polynomial_residual"][selected], dtype=float),
        np.asarray(group["laurent_residual"][selected], dtype=float),
        np.asarray(group["finite"][selected], dtype=bool),
        np.asarray(group["removed_as_zero"][selected], dtype=bool),
        np.asarray(group["matched_physical"][selected], dtype=bool),
        np.asarray(group["unmatched_full"][selected], dtype=bool),
    )


def read_results_h5(path: Path) -> list[CandidatePoint]:
    results: list[CandidatePoint] = []
    with h5py.File(path, "r") as handle:
        records = handle["points/record_json"].asstr()[...]
        for index, text in enumerate(records):
            raw = read_root_slice(handle["selected/raw"], index)
            retained = read_root_slice(handle["selected/retained"], index)
            compact_raw = read_root_slice(handle["pairing_compact/raw"], index)
            compact_retained = read_root_slice(handle["pairing_compact/retained"], index)
            results.append(
                CandidatePoint(
                    summary=json.loads(text),
                    raw_roots=raw[0],
                    raw_polynomial_residual=raw[1],
                    raw_laurent_residual=raw[2],
                    raw_finite=raw[3],
                    raw_removed_as_zero=raw[4],
                    raw_matched_physical=raw[5],
                    raw_unmatched_full=raw[6],
                    retained_roots=retained[0],
                    retained_polynomial_residual=retained[1],
                    retained_laurent_residual=retained[2],
                    retained_matched_physical=retained[5],
                    retained_unmatched_full=retained[6],
                    compact_raw_roots=compact_raw[0],
                    compact_raw_polynomial_residual=compact_raw[1],
                    compact_raw_laurent_residual=compact_raw[2],
                    compact_raw_finite=compact_raw[3],
                    compact_raw_removed_as_zero=compact_raw[4],
                    compact_retained_roots=compact_retained[0],
                    compact_retained_polynomial_residual=compact_retained[1],
                    compact_retained_laurent_residual=compact_retained[2],
                    elapsed_seconds=0.0,
                )
            )
    return results


def checkpoint_identity(
    seal: Mapping[str, Any], spec: base.RouteSpec, points: Sequence[tuple[int, int]]
) -> dict[str, Any]:
    return {
        "schema_version": "board20_step5_fullq_candidate_checkpoint_identity_v2",
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
        "route_manifest_sha256": seal["route_manifest_sha256"],
        "base_compute_sha256": seal["base_compute_sha256"],
        "workspace_sha256": spec.workspace_sha256,
        "route_id": spec.route_id,
        "point_order_sha256": sha256_json([list(point) for point in points]),
    }


def write_checkpoint(
    route_directory: Path,
    results: Sequence[CandidatePoint],
    identity: Mapping[str, Any],
    state: str,
) -> None:
    h5_path = route_directory / "checkpoint.h5"
    atomic_write_results_h5(h5_path, results)
    document = {
        **identity,
        "state": state,
        "completed_point_count": len(results),
        "checkpoint_h5_sha256": sha256_file(h5_path),
    }
    base.atomic_write_json(route_directory / "checkpoint.json", document)


def load_checkpoint(
    route_directory: Path, identity: Mapping[str, Any]
) -> list[CandidatePoint]:
    json_path = route_directory / "checkpoint.json"
    h5_path = route_directory / "checkpoint.h5"
    if not json_path.is_file() or not h5_path.is_file():
        raise FileNotFoundError(f"Complete checkpoint pair required: {route_directory}")
    document = read_json(json_path)
    for key, value in identity.items():
        if document.get(key) != value:
            raise RuntimeError(f"Checkpoint identity mismatch: {key}")
    if document.get("checkpoint_h5_sha256") != sha256_file(h5_path):
        raise RuntimeError("Checkpoint HDF5 SHA-256 mismatch.")
    results = read_results_h5(h5_path)
    if len(results) != int(document["completed_point_count"]):
        raise RuntimeError("Checkpoint point count mismatch.")
    return results


def write_route_outputs(
    route_directory: Path,
    results: Sequence[CandidatePoint],
    identity: Mapping[str, Any],
) -> dict[str, Any]:
    base.atomic_write_csv(
        route_directory / "point_summary.csv",
        [item.summary for item in results],
        CSV_FIELDS,
    )
    base.atomic_write_csv(
        route_directory / "point_runtime.csv",
        [
            {
                "route_id": item.summary["route_id"],
                "l": item.summary["l"],
                "j": item.summary["j"],
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
    finite_residual_results = [item for item in results if item.summary["point_status"] in ("PASS", "FAIL") and item.retained_roots.size]
    status = {
        "schema_version": "board20_step5_fullq_candidate_route_status_v2",
        "status": "PASS" if fail_count == 0 else "FAIL",
        "route_id": identity["route_id"],
        "selected_algorithm": results[0].summary["selected_algorithm"] if results else None,
        "matrix_order": results[0].summary["matrix_order"] if results else None,
        "expected_point_count": len(results),
        "completed_point_count": len(results),
        "pass_point_count": pass_count,
        "fail_point_count": fail_count,
        "max_gated_polynomial_residual": max((float(item.summary["max_gated_polynomial_residual"]) for item in finite_residual_results if item.summary.get("max_gated_polynomial_residual") not in (None, "")), default=None),
        "max_gated_laurent_residual": max((float(item.summary["max_gated_laurent_residual"]) for item in finite_residual_results if item.summary.get("max_gated_laurent_residual") not in (None, "")), default=None),
        "max_formula_relative_difference": max((float(item.summary["direct_formula_coefficient_relative_difference"]) for item in finite_residual_results if item.summary.get("direct_formula_coefficient_relative_difference") not in (None, "")), default=None),
        "rho_min": min((float(item.summary["rho"]) for item in finite_residual_results if item.summary.get("rho") not in (None, "")), default=None),
        "rho_max": max((float(item.summary["rho"]) for item in finite_residual_results if item.summary.get("rho") not in (None, "")), default=None),
        "origin_splitting_point_count": sum(item.summary.get("unmatched_full_root_count", 0) not in (0, None, "") for item in results),
        "max_unmatched_full_abs": max((float(item.summary["unmatched_full_max_abs"]) for item in finite_residual_results if item.summary.get("unmatched_full_max_abs") not in (None, "")), default=None),
        "max_full_q_compact_rho_abs_diff_diagnostic": max((float(item.summary["full_q_compact_rho_abs_diff"]) for item in finite_residual_results if item.summary.get("full_q_compact_rho_abs_diff") not in (None, "")), default=None),
        "stable_classification_mismatch_count": sum(not bool(item.summary.get("stable_classification_match", False)) for item in results),
        "point_summary_sha256": sha256_file(route_directory / "point_summary.csv"),
        "roots_h5_sha256": sha256_file(roots_path),
        **identity,
        "scientific_status_policy": "DETERMINISTIC_NO_WALL_CLOCK_FIELDS",
    }
    base.atomic_write_json(route_directory / "route_status.json", status)
    return status


def known_route_files() -> tuple[str, ...]:
    return (
        "point_summary.csv",
        "roots.h5",
        "route_status.json",
        "checkpoint.h5",
        "checkpoint.json",
        "point_runtime.csv",
    )


def clear_route_files(route_directory: Path) -> None:
    for name in known_route_files():
        path = route_directory / name
        if path.is_file():
            path.unlink()


def points_for_mode(context: Context, spec: base.RouteSpec, mode: str) -> list[tuple[int, int]]:
    if mode == "pilot":
        return list(spec.pilot_points)
    grid = context.contract["full_grid"]
    return [
        (l_value, j_value)
        for l_value in range(int(grid["l_start"]), int(grid["l_end"]) + 1)
        for j_value in range(int(grid["j_start"]), int(grid["j_end"]) + 1)
    ]


def write_artifact_manifest(mode_directory: Path, route_ids: Sequence[str]) -> Path:
    paths = [
        mode_directory / route_id / name
        for route_id in route_ids
        for name in ("point_summary.csv", "roots.h5", "route_status.json")
    ] + [mode_directory / "run_status.json"]
    rows = []
    for path in sorted(paths, key=lambda item: item.relative_to(mode_directory).as_posix()):
        rows.append(
            {
                "relpath": path.relative_to(mode_directory).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    manifest_path = mode_directory / "artifact_manifest.csv"
    base.atomic_write_csv(manifest_path, rows, ("relpath", "bytes", "sha256"))
    return manifest_path


def run_scientific_mode(
    requested_mode: str,
    overwrite: bool,
    checkpoint_every: int,
    expected_manifest_sha256: str | None,
) -> dict[str, Any]:
    context, seal = verify_input_seal()
    require_gate(output_root() / "preflight.json", "board20_step5_fullq_candidate_preflight_v2")
    require_gate(output_root() / "selftest.json", "board20_step5_fullq_candidate_selftest_v2")
    if requested_mode in ("full", "resume"):
        require_gate(output_root() / "pilot" / "run_status.json", "board20_step5_fullq_candidate_run_status_v2")
    mode = "full" if requested_mode == "resume" else requested_mode
    mode_directory = output_root() / mode
    mode_directory.mkdir(parents=True, exist_ok=True)
    gates = context.contract["numeric_gates"]
    route_statuses: list[dict[str, Any]] = []
    started = time.perf_counter()

    for spec in context.specs:
        matrices = base.load_route_matrices(context.root, spec)
        n = int(matrices.M.shape[0])
        algorithm = selected_algorithm(n)
        expected_algorithm = context.contract["algorithm_selection"]["expected_selected_algorithms"][spec.route_id]
        if algorithm != expected_algorithm:
            raise RuntimeError(f"Order-only algorithm identity changed: {spec.route_id}")
        points = points_for_mode(context, spec, mode)
        route_directory = mode_directory / spec.route_id
        route_directory.mkdir(parents=True, exist_ok=True)
        identity = checkpoint_identity(seal, spec, points)
        if requested_mode == "resume":
            results = load_checkpoint(route_directory, identity)
        else:
            existing = [route_directory / name for name in known_route_files() if (route_directory / name).exists()]
            if existing and not overwrite:
                raise FileExistsError(f"Candidate outputs already exist; pass --overwrite: {route_directory}")
            if overwrite:
                clear_route_files(route_directory)
            results = []
        if len(results) > len(points):
            raise RuntimeError(f"Checkpoint exceeds point contract: {spec.route_id}")
        for index, result in enumerate(results):
            if (int(result.summary["l"]), int(result.summary["j"])) != points[index]:
                raise RuntimeError(f"Checkpoint point order mismatch: {spec.route_id}")

        for index in range(len(results), len(points)):
            l_value, j_value = points[index]
            point = solve_point(spec, matrices, l_value, j_value, gates)
            results.append(point)
            if point.summary["point_status"] != "PASS" or (index + 1) % 25 == 0 or index + 1 == len(points):
                logging.info(
                    "%s %s %d/%d l=%d j=%d algorithm=%s status=%s rho=%s elapsed=%.3fs",
                    mode,
                    spec.route_id,
                    index + 1,
                    len(points),
                    l_value,
                    j_value,
                    algorithm,
                    point.summary["point_status"],
                    point.summary.get("rho"),
                    point.elapsed_seconds,
                )
            if checkpoint_every > 0 and ((index + 1) % checkpoint_every == 0 or index + 1 == len(points)):
                write_checkpoint(
                    route_directory,
                    results,
                    identity,
                    "COMPLETE" if index + 1 == len(points) else "IN_PROGRESS",
                )
        if not results:
            write_checkpoint(route_directory, results, identity, "COMPLETE")
        route_statuses.append(write_route_outputs(route_directory, results, identity))

    expected_total = sum(len(points_for_mode(context, spec, mode)) for spec in context.specs)
    completed = sum(int(item["completed_point_count"]) for item in route_statuses)
    failures = sum(int(item["fail_point_count"]) for item in route_statuses)
    status_text = "PASS" if completed == expected_total and failures == 0 and all(item["status"] == "PASS" for item in route_statuses) else "FAIL"
    run_status = {
        "schema_version": "board20_step5_fullq_candidate_run_status_v2",
        "status": status_text,
        "mode": mode,
        "route_count": len(route_statuses),
        "expected_point_count": expected_total,
        "completed_point_count": completed,
        "pass_point_count": completed - failures,
        "fail_point_count": failures,
        "route_statuses": route_statuses,
        "input_identity": seal,
        "algorithm_selection": context.contract["algorithm_selection"],
        "root_policy_sha256": seal["root_policy_sha256"],
        "noncomputable_failed_routes": context.contract["noncomputable_failed_routes"],
        "scientific_contracts": context.contract["scientific_contracts"],
        "scientific_status_policy": "DETERMINISTIC_NO_WALL_CLOCK_FIELDS",
    }
    base.atomic_write_json(mode_directory / "run_status.json", run_status)
    manifest_path = write_artifact_manifest(mode_directory, [spec.route_id for spec in context.specs])
    manifest_hash = sha256_file(manifest_path)
    repeatability = None
    if expected_manifest_sha256 is not None:
        expected = expected_manifest_sha256.upper()
        repeatability = {
            "schema_version": "board20_step5_fullq_candidate_repeatability_v2",
            "mode": mode,
            "baseline_artifact_manifest_sha256": expected,
            "repeat_artifact_manifest_sha256": manifest_hash,
            "scientific_artifacts_match": expected == manifest_hash,
            "status": "PASS" if expected == manifest_hash else "FAIL",
        }
        base.atomic_write_json(output_root() / f"{mode}_repeatability.json", repeatability)
        if expected != manifest_hash:
            raise RuntimeError(f"Repeated {mode} scientific artifact manifest hash changed.")
    metadata = {
        "schema_version": "board20_step5_fullq_candidate_run_metadata_v2",
        "mode": mode,
        "requested_mode": requested_mode,
        "completed_at": base.utc_now(),
        "elapsed_seconds": time.perf_counter() - started,
        "artifact_manifest_sha256": manifest_hash,
        "repeatability": repeatability,
    }
    base.atomic_write_json(mode_directory / "run_metadata.json", metadata)
    return {
        "status": status_text,
        "mode": mode,
        "points": completed,
        "pass": completed - failures,
        "fail": failures,
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
        handlers=[logging.FileHandler(path, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
        force=True,
    )
    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("preflight", "selftest", "pilot", "full", "resume"),
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=100)
    parser.add_argument("--expected-manifest-sha256")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    configure_logging(args.mode)
    started = time.perf_counter()
    if args.checkpoint_every < 1:
        raise ValueError("--checkpoint-every must be positive.")
    if args.mode == "preflight":
        result = run_preflight()
    elif args.mode == "selftest":
        result = run_selftest()
    else:
        result = run_scientific_mode(
            args.mode,
            args.overwrite,
            args.checkpoint_every,
            args.expected_manifest_sha256,
        )
    logging.info(
        "BOARD20_STEP5_FULLQ_CANDIDATE_%s=%s elapsed=%.3fs",
        args.mode.upper(),
        result.get("status"),
        time.perf_counter() - started,
    )
    print(json.dumps({key: json_safe(value) for key, value in result.items()}, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

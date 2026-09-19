#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""独立核验板块28默认 gain_scale=1 数值物化结果。

本脚本不导入数值物化生成器，不求根、不运行时滞网格，也不读取任何论文边界、
绘图 MAT、边界 CSV 或目标 PDF。它直接从冻结科学合同、冻结源矩阵和已物化 MAT
重算关键矩阵关系，并核对 18 条路线赋值与 Stage0 表。
"""

from __future__ import annotations

import ast
import csv
import hashlib
import importlib.util
import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.io import loadmat
from scipy.linalg import solve_continuous_are


SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
CODE_DIR = CASE_DIR / "code"
DATA_DIR = CASE_DIR / "data" / "numeric_bundles" / "gain_scale_1_source_anchor"
CONTRACT_DIR = CASE_DIR / "data" / "contract_layer"

METHODS = ("Original", "Guyan", "Craig_Bampton")
METHOD_CODES = {"Original": 1, "Guyan": 2, "Craig_Bampton": 3}
CONTRACT_CODES = {"B1": 1, "B2": 2, "B3": 3}
DIMENSIONS = {
    1: {"Original": 15, "Guyan": 6, "Craig_Bampton": 9},
    2: {"Original": 15, "Guyan": 5, "Craig_Bampton": 8},
}
OPERATOR_FIELDS = (
    "mass_term",
    "base_zero",
    "base_minus_one",
    "delay_left",
    "delay_v_zero",
    "delay_v_minus_one",
)
NATIVE_REQUIRED = {
    "dt",
    "route_dimension",
    "mass_term",
    "base_zero",
    "base_minus_one",
    "delay_left",
    "delay_v_zero",
    "delay_v_minus_one",
    "register_scales",
}
LEGACY_REQUIRED = {
    "dt",
    "route_dimension",
    "integration_mass_operator",
    "C1",
    "K1",
    "delay_C_left_factor",
    "delay_C_right_factor",
    "delay_K_left_factor",
    "delay_K_right_factor",
    "feedback_C",
    "feedback_K",
}
CARE_Q = np.diag([1.0e6, 1.0e6, 1.0e4, 1.0e4])
CARE_R = np.diag([1.0e-2, 1.0e-2])


def find_repo_root() -> Path:
    for candidate in (CASE_DIR, *CASE_DIR.parents):
        if (candidate / "WORKFLOW.md").is_file() and (candidate / "test").is_dir():
            return candidate.resolve()
    raise RuntimeError("无法定位项目根目录")


REPO_ROOT = find_repo_root()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def semantic_array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    descriptor = canonical_json_bytes(
        {
            "dtype": array.dtype.str,
            "shape": list(array.shape),
            "order": "C",
        }
    )
    digest = hashlib.sha256()
    digest.update(descriptor)
    digest.update(b"\0")
    digest.update(array.tobytes(order="C"))
    return digest.hexdigest()


def legacy_array_sha256(value: np.ndarray) -> str:
    return hashlib.sha256(np.ascontiguousarray(value).tobytes(order="C")).hexdigest()


def route_operator_sha256(dimension: int, dt: float, operator: Mapping[str, np.ndarray]) -> str:
    inventory = {
        name: {
            "semantic_array_sha256": semantic_array_sha256(operator[name]),
            "dtype": np.ascontiguousarray(operator[name]).dtype.str,
            "shape": list(np.ascontiguousarray(operator[name]).shape),
        }
        for name in OPERATOR_FIELDS
    }
    payload = {
        "route_dimension": dimension,
        "dt_seconds": format(dt, ".17g"),
        "channel_to_delay_exponent": {"channel_1": "l", "channel_2": "j"},
        "operator_arrays": inventory,
    }
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest()


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_numeric_mat(
    path: Path, simplify: bool = False, preserve_shapes: bool = False
) -> dict[str, np.ndarray]:
    if simplify:
        raw = loadmat(path, simplify_cells=True)
    elif preserve_shapes:
        raw = loadmat(path, squeeze_me=False, struct_as_record=False)
    else:
        raw = loadmat(path, squeeze_me=True, struct_as_record=False)
    return {
        key: np.asarray(value).copy()
        for key, value in raw.items()
        if not key.startswith("__")
    }


def scalar(value: Any) -> float:
    array = np.asarray(value)
    if array.size != 1:
        raise ValueError(f"预期标量，实际 shape={array.shape}")
    return float(array.reshape(-1)[0])


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    actual_array = np.asarray(actual, dtype=np.float64)
    expected_array = np.asarray(expected, dtype=np.float64)
    if expected_array.ndim >= 2:
        denominator_norm = float(np.linalg.norm(expected_array, ord="fro"))
        difference_norm = float(np.linalg.norm(actual_array - expected_array, ord="fro"))
    else:
        denominator_norm = float(np.linalg.norm(expected_array.reshape(-1), ord=2))
        difference_norm = float(np.linalg.norm((actual_array - expected_array).reshape(-1), ord=2))
    denominator = max(denominator_norm, np.finfo(float).eps)
    return difference_norm / denominator


def symmetry_error(value: np.ndarray) -> float:
    array = np.asarray(value, dtype=np.float64)
    denominator = max(float(np.linalg.norm(array, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(array - array.T, ord="fro") / denominator)


def minimum_symmetric_eigenvalue(value: np.ndarray) -> float:
    array = np.asarray(value, dtype=np.float64)
    return float(np.min(np.linalg.eigvalsh(0.5 * (array + array.T))))


def controllability_metrics(a_matrix: np.ndarray, b_matrix: np.ndarray) -> tuple[int, float]:
    blocks = [b_matrix]
    current = b_matrix.copy()
    for _ in range(1, a_matrix.shape[0]):
        current = a_matrix @ current
        blocks.append(current)
    matrix = np.hstack(blocks)
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    return (
        int(np.linalg.matrix_rank(matrix)),
        float(singular_values[-1] / max(singular_values[0], np.finfo(float).eps)),
    )


def care_residual(
    a_matrix: np.ndarray,
    b_matrix: np.ndarray,
    q_weight: np.ndarray,
    r_weight: np.ndarray,
    solution: np.ndarray,
) -> float:
    residual = (
        a_matrix.T @ solution
        + solution @ a_matrix
        - solution @ b_matrix @ np.linalg.solve(r_weight, b_matrix.T @ solution)
        + q_weight
    )
    return float(np.linalg.norm(residual, ord="fro") / np.linalg.norm(q_weight, ord="fro"))


def standard_local_static_projection(
    local_full: Mapping[str, np.ndarray], local_selection: np.ndarray
) -> tuple[dict[str, np.ndarray], np.ndarray, float, list[int]]:
    local_dimension = local_full["M"].shape[0]
    master = [int(np.argmax(np.abs(row))) for row in local_selection]
    slave = [index for index in range(local_dimension) if index not in master]
    order = master + slave
    stiffness_ordered = local_full["K"][np.ix_(order, order)]
    retained = len(master)
    k_sm = stiffness_ordered[retained:, :retained]
    k_ss = stiffness_ordered[retained:, retained:]
    static_part = -np.linalg.solve(k_ss, k_sm)
    transform_ordered = np.vstack((np.eye(retained), static_part))
    transform = np.zeros((local_dimension, retained), dtype=np.float64)
    transform[order, :] = transform_ordered
    projected = {
        symbol: transform.T @ local_full[symbol] @ transform
        for symbol in ("M", "C", "K")
    }
    residual = float(
        np.linalg.norm(k_ss @ static_part + k_sm, ord="fro")
        / max(float(np.linalg.norm(k_sm, ord="fro")), np.finfo(float).eps)
    )
    return projected, transform, residual, master


def route_matrix_al(
    mass: np.ndarray, damping: np.ndarray, stiffness: np.ndarray, dt: float
) -> tuple[np.ndarray, np.ndarray, float]:
    coefficient = 4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness
    al_matrix = np.linalg.solve(coefficient, 4.0 * mass)
    integration_mass = np.linalg.solve(al_matrix.T, mass.T).T
    expected = mass + 0.5 * dt * damping + 0.25 * dt**2 * stiffness
    return al_matrix, integration_mass, relative_error(integration_mass, expected)


def zero_delay_operator(operator: Mapping[str, np.ndarray]) -> tuple[np.ndarray, np.ndarray]:
    return (
        operator["base_zero"] + operator["delay_left"] @ operator["delay_v_zero"],
        operator["base_minus_one"]
        + operator["delay_left"] @ operator["delay_v_minus_one"],
    )


def operator_pair_error(
    left: Mapping[str, np.ndarray], right: Mapping[str, np.ndarray]
) -> float:
    left_zero, left_minus = zero_delay_operator(left)
    right_zero, right_minus = zero_delay_operator(right)
    return max(relative_error(left_zero, right_zero), relative_error(left_minus, right_minus))


def laurent_coefficients(
    operator: Mapping[str, np.ndarray], delays: tuple[int, int]
) -> dict[int, np.ndarray]:
    result: dict[int, np.ndarray] = {}

    def add(exponent: int, value: np.ndarray) -> None:
        if exponent not in result:
            result[exponent] = np.zeros_like(operator["mass_term"])
        result[exponent] += value

    add(1, operator["mass_term"])
    add(0, operator["base_zero"])
    add(-1, operator["base_minus_one"])
    for channel, delay in enumerate(delays):
        add(
            -delay,
            np.outer(operator["delay_left"][:, channel], operator["delay_v_zero"][channel, :]),
        )
        add(
            -(delay + 1),
            np.outer(
                operator["delay_left"][:, channel],
                operator["delay_v_minus_one"][channel, :],
            ),
        )
    return result


def mapping_diff(left: Any, right: Any, prefix: str = "") -> set[str]:
    if isinstance(left, dict) and isinstance(right, dict):
        keys = set(left) | set(right)
        result: set[str] = set()
        for key in keys:
            path = f"{prefix}.{key}" if prefix else key
            if key not in left or key not in right:
                result.add(path)
            else:
                result |= mapping_diff(left[key], right[key], path)
        return result
    if left != right:
        return {prefix}
    return set()


def base_prefix(division: int, method: str) -> str:
    if method == "Original":
        return f"div{division}_Original_source_full15"
    if method == "Guyan":
        return f"div{division}_Guyan_source_standard_congruence"
    return f"div{division}_Craig_Bampton_source_sorted_three_modes"


def as_operator_native(data: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    return {name: np.ascontiguousarray(np.asarray(data[name], dtype=np.float64)) for name in OPERATOR_FIELDS}


def as_operator_legacy(data: Mapping[str, np.ndarray]) -> dict[str, np.ndarray]:
    dimension = int(round(scalar(data["route_dimension"])))
    dt = scalar(data["dt"])
    integration_mass = np.asarray(data["integration_mass_operator"], dtype=np.float64)
    c1 = np.asarray(data["C1"], dtype=np.float64)
    k1 = np.asarray(data["K1"], dtype=np.float64)
    delay_c_left = np.asarray(data["delay_C_left_factor"], dtype=np.float64).reshape(dimension, 2)
    delay_c_right = np.asarray(data["delay_C_right_factor"], dtype=np.float64).reshape(2, dimension)
    delay_k_left = np.asarray(data["delay_K_left_factor"], dtype=np.float64).reshape(dimension, 2)
    delay_k_right = np.asarray(data["delay_K_right_factor"], dtype=np.float64).reshape(2, dimension)
    if relative_error(delay_c_left, delay_k_left) > 1.0e-12:
        raise RuntimeError("旧路线 C/K 延迟左因子不共享")
    feedback_c = np.asarray(data["feedback_C"], dtype=np.float64)
    feedback_k = np.asarray(data["feedback_K"], dtype=np.float64)
    mass_term = integration_mass / (dt * dt)
    return {
        "mass_term": np.ascontiguousarray(mass_term),
        "base_zero": np.ascontiguousarray(
            -2.0 * mass_term + c1 / dt + k1 + feedback_c / dt + feedback_k
        ),
        "base_minus_one": np.ascontiguousarray(mass_term - c1 / dt - feedback_c / dt),
        "delay_left": np.ascontiguousarray(delay_c_left),
        "delay_v_zero": np.ascontiguousarray(delay_c_right / dt + delay_k_right),
        "delay_v_minus_one": np.ascontiguousarray(-delay_c_right / dt),
    }


def bool_text(value: str) -> bool:
    return value.strip().lower() == "true"


def float_matches(actual: float, recorded: str, absolute: float = 1.0e-12) -> bool:
    expected = float(recorded)
    return abs(actual - expected) <= max(absolute, 1.0e-10 * abs(expected))


def write_json(path: Path, value: Any) -> None:
    def json_default(item: Any) -> Any:
        if isinstance(item, np.generic):
            return item.item()
        if isinstance(item, np.ndarray):
            return item.tolist()
        if isinstance(item, Path):
            return str(item)
        raise TypeError(f"不可序列化类型：{type(item).__name__}")

    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
            default=json_default,
        )
        + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, rows: Iterable[Mapping[str, Any]], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    def check(name: str, passed: bool, detail: Any) -> None:
        checks.append({"check": name, "passed": bool(passed), "detail": detail})
        if not passed:
            failures.append(name)

    manifest = load_json(DATA_DIR / "materialization_manifest.json")
    assignments = load_csv(DATA_DIR / "route_assignments.csv")
    gate_rows = load_csv(DATA_DIR / "stage0_gate_results.csv")
    gates = {row["route_id"]: row for row in gate_rows}
    array_inventory = load_csv(DATA_DIR / "array_hash_inventory.csv")
    array_inventory_map = {(row["route_id"], row["field"]): row for row in array_inventory}
    mat_hash_rows = load_csv(DATA_DIR / "mat_artifact_hashes.csv")
    mat_hash_map = {row["route_id"]: row for row in mat_hash_rows}
    contracts = {
        contract_id: load_json(CONTRACT_DIR / f"{contract_id}.json")
        for contract_id in ("B1", "B2", "B3")
    }
    r03_reuse_contract = load_json(CONTRACT_DIR / "R03_REUSE.json")

    channel_paths = {
        "actuation_and_delay_channels.division_2.coordinates",
        "actuation_and_delay_channels.division_2.local_selector_zero_based",
        "controller_channels.division_2.coordinates",
        "controller_channels.division_2.local_selector_zero_based",
    }
    feedback_paths = {
        "delay_and_feedback.feedback_placement",
        "delay_and_feedback.feedback_formula",
        "delay_and_feedback.inside_bundle_rule",
    }
    expected_diffs = {
        "B1_vs_B2": channel_paths | feedback_paths,
        "B1_vs_B3": feedback_paths,
        "B2_vs_B3": channel_paths,
    }
    contract_diffs: dict[str, Any] = {}
    for left_id, right_id in (("B1", "B2"), ("B1", "B3"), ("B2", "B3")):
        key = f"{left_id}_vs_{right_id}"
        actual = mapping_diff(
            contracts[left_id]["scientific_contract"],
            contracts[right_id]["scientific_contract"],
        )
        expected = expected_diffs[key]
        contract_diffs[key] = {
            "actual_paths": sorted(actual),
            "expected_paths": sorted(expected),
            "unexpected_paths": sorted(actual - expected),
            "missing_expected_paths": sorted(expected - actual),
            "pass": actual == expected,
        }
        check(f"contract_axes_{key}", actual == expected, contract_diffs[key])

    forbidden_asset_markers = (
        "plotted_data",
        "plotteddata",
        "fig10_stability_domain",
        "submit_figure",
        "vector_boundary",
        "boundary_csv",
        "strict_evaluator",
        "目标边界",
        "论文矢量",
    )
    generator_sources = {
        name: (CODE_DIR / name).read_text(encoding="utf-8")
        for name in ("materialize_fig10_numeric_bundles.py", "build_fig10_candidate_bundles.py")
    }
    forbidden_hits = {
        name: [marker for marker in forbidden_asset_markers if marker in text.lower()]
        for name, text in generator_sources.items()
    }
    check(
        "generator_has_no_target_asset_reference",
        all(not hits for hits in forbidden_hits.values()),
        forbidden_hits,
    )
    imported_modules: dict[str, list[str]] = {}
    for name, text in generator_sources.items():
        tree = ast.parse(text)
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module)
        imported_modules[name] = sorted(modules)
    check(
        "generator_does_not_import_solver_or_evaluator",
        all(
            not any("evaluator" in module or "blind_search" in module for module in modules)
            for modules in imported_modules.values()
        ),
        imported_modules,
    )

    source_fingerprint_results: list[dict[str, Any]] = []
    source_by_id: dict[str, Path] = {}
    source_scope_pass = True
    for item in manifest["source_fingerprints"]:
        path = (REPO_ROOT / Path(item["repo_relative_path"])).resolve()
        actual_hash = sha256_file(path)
        lowered = path.as_posix().lower()
        marker_hits = [marker for marker in forbidden_asset_markers if marker in lowered]
        under_board20 = "板块20_lqr时滞稳定域及图4-4至图4-5逐图计算复现" in lowered
        row_pass = path.is_file() and actual_hash == item["sha256"] and not marker_hits and under_board20
        source_scope_pass &= row_pass
        source_by_id[item["source_id"]] = path
        source_fingerprint_results.append(
            {
                "source_id": item["source_id"],
                "path": path.relative_to(REPO_ROOT).as_posix(),
                "expected_sha256": item["sha256"],
                "actual_sha256": actual_hash,
                "forbidden_marker_hits": marker_hits,
                "under_board20_frozen_scope": under_board20,
                "pass": row_pass,
            }
        )
    check("all_declared_sources_frozen_and_target_free", source_scope_pass, source_fingerprint_results)
    validation_scope = load_json(source_by_id["board20_fullgrid_validation"]).get("scope")
    check(
        "reused_fullgrid_certificate_declares_no_boundary_scope",
        validation_scope == "no paper/PDF/history boundary",
        {"scope": validation_scope},
    )

    check(
        "manifest_counts",
        manifest["counts"] == {
            "global_contracts": 3,
            "route_assignments": 18,
            "new_numeric_route_bundles": 12,
            "reused_route_assignments": 6,
            "stage0_pass": 12,
            "stage0_fail": 0,
            "roots_computed": 0,
            "delay_grid_points_computed": 0,
            "parameter_candidates_evaluated": 0,
        },
        manifest["counts"],
    )
    check(
        "table_cardinalities",
        len(assignments) == 18
        and len({row["assignment_id"] for row in assignments}) == 18
        and len(gate_rows) == 12
        and len({row["route_id"] for row in gate_rows}) == 12
        and len(mat_hash_rows) == 12,
        {
            "assignments": len(assignments),
            "unique_assignments": len({row["assignment_id"] for row in assignments}),
            "stage0_rows": len(gate_rows),
            "mat_hash_rows": len(mat_hash_rows),
        },
    )

    source = load_numeric_mat(source_by_id["board20_step8b_frozen_mat"], simplify=True)
    new_route_rows = {item["route_id"]: item for item in manifest["new_routes"]}
    native_data: dict[str, dict[str, np.ndarray]] = {}
    native_operators: dict[str, dict[str, np.ndarray]] = {}
    for route_id, item in new_route_rows.items():
        path = (REPO_ROOT / Path(item["repo_relative_path"])).resolve()
        native_data[route_id] = load_numeric_mat(path)
        native_operators[route_id] = as_operator_native(native_data[route_id])

    assignment_hash_rows: list[dict[str, Any]] = []
    operators_by_assignment: dict[str, dict[str, np.ndarray]] = {}
    data_by_assignment: dict[str, dict[str, np.ndarray]] = {}
    paths_by_assignment: dict[str, Path] = {}
    all_assignment_hashes_pass = True
    all_assignment_schema_pass = True
    for row in assignments:
        assignment_id = row["assignment_id"]
        path = (REPO_ROOT / Path(row["repo_relative_path"])).resolve()
        data = load_numeric_mat(path)
        dimension = int(row["dimension"])
        legacy = row["assignment_action"] == "REUSE_BOARD20_R03_ROUTE"
        operator = as_operator_legacy(data) if legacy else as_operator_native(data)
        actual_file_hash = sha256_file(path)
        actual_operator_hash = route_operator_sha256(dimension, scalar(data["dt"]), operator)
        required = LEGACY_REQUIRED if legacy else NATIVE_REQUIRED
        missing = sorted(required - set(data))
        if legacy:
            shapes_pass = (
                operator["mass_term"].shape == (dimension, dimension)
                and operator["base_zero"].shape == (dimension, dimension)
                and operator["delay_left"].shape == (dimension, 2)
                and operator["delay_v_zero"].shape == (2, dimension)
                and scalar(data.get("feedback_placement_code", np.nan)) == 1.0
            )
            register_scales = np.maximum.reduce(
                (
                    np.linalg.norm(operator["delay_v_zero"], axis=1),
                    np.linalg.norm(operator["delay_v_minus_one"], axis=1),
                    np.full(2, np.finfo(float).eps),
                )
            )
        else:
            register_scales = np.asarray(data["register_scales"], dtype=np.float64).reshape(-1)
            shapes_pass = (
                operator["mass_term"].shape == (dimension, dimension)
                and operator["base_zero"].shape == (dimension, dimension)
                and operator["base_minus_one"].shape == (dimension, dimension)
                and operator["delay_left"].shape == (dimension, 2)
                and operator["delay_v_zero"].shape == (2, dimension)
                and operator["delay_v_minus_one"].shape == (2, dimension)
                and register_scales.shape == (2,)
            )
        finite = all(np.all(np.isfinite(value)) for value in operator.values()) and np.all(
            np.isfinite(register_scales)
        )
        schema_pass = (
            not missing
            and shapes_pass
            and finite
            and scalar(data["dt"]) > 0.0
            and np.linalg.matrix_rank(operator["mass_term"]) == dimension
            and np.all(register_scales > 0.0)
        )
        hash_pass = (
            actual_file_hash == row["artifact_sha256"]
            and actual_operator_hash == row["route_operator_sha256"]
        )
        all_assignment_hashes_pass &= hash_pass
        all_assignment_schema_pass &= schema_pass
        operators_by_assignment[assignment_id] = operator
        data_by_assignment[assignment_id] = data
        paths_by_assignment[assignment_id] = path
        assignment_hash_rows.append(
            {
                "assignment_id": assignment_id,
                "assignment_action": row["assignment_action"],
                "repo_relative_path": row["repo_relative_path"],
                "expected_artifact_sha256": row["artifact_sha256"],
                "actual_artifact_sha256": actual_file_hash,
                "artifact_hash_pass": actual_file_hash == row["artifact_sha256"],
                "expected_operator_sha256": row["route_operator_sha256"],
                "actual_operator_sha256": actual_operator_hash,
                "operator_hash_pass": actual_operator_hash == row["route_operator_sha256"],
                "missing_core_fields": ";".join(missing),
                "core_schema_pass": schema_pass,
            }
        )
    check("all_18_assignment_artifact_and_operator_hashes", all_assignment_hashes_pass, assignment_hash_rows)
    check("all_18_assignment_paths_satisfy_blind_core_shapes", all_assignment_schema_pass, assignment_hash_rows)

    b3_reuse_pass = True
    b3_reuse_detail: list[dict[str, Any]] = []
    assignment_map = {row["assignment_id"]: row for row in assignments}
    for method in METHODS:
        b2 = assignment_map[f"B2_D1_{method}"]
        b3 = assignment_map[f"B3_D1_{method}"]
        row_pass = all(
            b2[key] == b3[key]
            for key in ("repo_relative_path", "artifact_sha256", "route_operator_sha256", "dimension")
        )
        b3_reuse_pass &= row_pass
        b3_reuse_detail.append(
            {
                "method": method,
                "same_path": b2["repo_relative_path"] == b3["repo_relative_path"],
                "same_artifact_sha256": b2["artifact_sha256"] == b3["artifact_sha256"],
                "same_operator_sha256": b2["route_operator_sha256"] == b3["route_operator_sha256"],
                "pass": row_pass,
            }
        )
    check("B3_division1_reuses_exact_B2_operators", b3_reuse_pass, b3_reuse_detail)

    # 正式盲算加载器的只读契约探针；不调用求根函数。
    spec = importlib.util.spec_from_file_location("fig10_blind_core_probe", CODE_DIR / "fig10_blind_core.py")
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载正式盲算核心")
    core = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = core
    spec.loader.exec_module(core)
    production_loader_results: list[dict[str, Any]] = []
    production_loader_pass = True
    for row in assignments:
        metadata = {
            "route_id": row["assignment_id"],
            "contract_id": row["global_contract_id"],
            "dimension": int(row["dimension"]),
            "operator_layout": (
                "BOARD20_STEP8C_LEGACY_V1"
                if row["assignment_action"] == "REUSE_BOARD20_R03_ROUTE"
                else "MINIMAL_AUGMENTED_CORE_V1"
            ),
            "bundle_sha256": row["artifact_sha256"],
            "division": int(row["division"]),
        }
        try:
            bundle = core.load_blind_bundle(paths_by_assignment[row["assignment_id"]], metadata)
            passed = bundle.dimension == int(row["dimension"])
            error = ""
        except Exception as exc:  # pragma: no cover - evidence path
            passed = False
            error = f"{type(exc).__name__}: {exc}"
        production_loader_pass &= passed
        production_loader_results.append(
            {"assignment_id": row["assignment_id"], "passed": passed, "error": error}
        )
    check("production_blind_core_loads_all_18_assignments", production_loader_pass, production_loader_results)

    route_recalculation_rows: list[dict[str, Any]] = []
    independent_metrics: dict[str, dict[str, Any]] = {}
    reconstructed_operators: dict[str, dict[str, np.ndarray]] = {}
    reconstruction_pass = True
    psi11_mapping_pass = True
    psi11_mapping_detail: list[dict[str, Any]] = []

    for route_id, item in sorted(new_route_rows.items()):
        contract_id = item["contract_id"]
        division = int(item["division"])
        method = item["method"]
        dimension = int(item["dimension"])
        data = native_data[route_id]
        science = contracts[contract_id]["scientific_contract"]
        prefix = base_prefix(division, method)
        mass = np.asarray(source[f"{prefix}_M"], dtype=np.float64)
        damping = np.asarray(source[f"{prefix}_C"], dtype=np.float64)
        stiffness = np.asarray(source[f"{prefix}_K"], dtype=np.float64)
        recovery = np.asarray(source[f"div{division}_{method}_recovery_natural"], dtype=np.float64)
        embedding = np.asarray(source[f"div{division}_local_embedding_E"], dtype=np.float64)
        local_full = {
            symbol: np.asarray(source[f"div{division}_local_full_{symbol}"], dtype=np.float64)
            for symbol in ("M", "C", "K")
        }
        channel_contract = science["actuation_and_delay_channels"][f"division_{division}"]
        local_rows = [int(value) for value in channel_contract["local_selector_zero_based"]]
        local_selection = np.eye(local_full["M"].shape[0], dtype=np.float64)[local_rows, :]
        local_projected, local_transform, local_static_residual, local_master = (
            standard_local_static_projection(local_full, local_selection)
        )
        selector_right = local_selection @ embedding.T @ recovery
        selector_left = selector_right.copy()
        physical_left = selector_left.T
        physical_right_c = local_selection @ local_full["C"] @ embedding.T @ recovery
        physical_right_k = local_selection @ local_full["K"] @ embedding.T @ recovery
        physical_c2 = physical_left @ physical_right_c
        physical_k2 = physical_left @ physical_right_k
        c_remainder = damping - physical_c2
        k_remainder = stiffness - physical_k2

        zero = np.zeros((2, 2))
        identity = np.eye(2)
        a_matrix = np.block(
            [
                [zero, identity],
                [
                    -np.linalg.solve(local_projected["M"], local_projected["K"]),
                    -np.linalg.solve(local_projected["M"], local_projected["C"]),
                ],
            ]
        )
        b_matrix = np.vstack((zero, np.linalg.solve(local_projected["M"], identity)))
        p_solution = solve_continuous_are(a_matrix, b_matrix, CARE_Q, CARE_R)
        gain_full = np.linalg.solve(CARE_R, b_matrix.T @ p_solution)
        gain_active = gain_full.copy()
        delta_k = gain_active[:, :2]
        delta_c = gain_active[:, 2:]
        feedback_c = selector_left.T @ delta_c @ selector_right
        feedback_k = selector_left.T @ delta_k @ selector_right
        placement = science["delay_and_feedback"]["feedback_placement"]
        if placement == "OUTSIDE_H":
            active_right_c = physical_right_c.copy()
            active_right_k = physical_right_k.copy()
            external_c = feedback_c.copy()
            external_k = feedback_k.copy()
            placement_code = 1
        elif placement == "INSIDE_H":
            active_right_c = physical_right_c + delta_c @ selector_right
            active_right_k = physical_right_k + delta_k @ selector_right
            external_c = np.zeros_like(feedback_c)
            external_k = np.zeros_like(feedback_k)
            placement_code = 2
        else:
            raise RuntimeError(f"未知反馈位置：{placement}")
        active_c2 = physical_left @ active_right_c
        active_k2 = physical_left @ active_right_k
        dt = scalar(source[f"div{division}_source_dt"])
        al_matrix, integration_mass, integration_error = route_matrix_al(
            mass, damping, stiffness, dt
        )
        mass_term = integration_mass / (dt * dt)
        operator = {
            "mass_term": np.ascontiguousarray(mass_term),
            "base_zero": np.ascontiguousarray(
                -2.0 * mass_term
                + c_remainder / dt
                + k_remainder
                + external_c / dt
                + external_k
            ),
            "base_minus_one": np.ascontiguousarray(
                mass_term - c_remainder / dt - external_c / dt
            ),
            "delay_left": np.ascontiguousarray(physical_left),
            "delay_v_zero": np.ascontiguousarray(active_right_c / dt + active_right_k),
            "delay_v_minus_one": np.ascontiguousarray(-active_right_c / dt),
        }
        reconstructed_operators[route_id] = operator

        expected_fields = {
            "M": mass,
            "C": damping,
            "K": stiffness,
            "R_recovery": recovery,
            "W_test_basis": recovery,
            "E_local_embedding": embedding,
            "J_local_selection": local_selection,
            "S_R": selector_right,
            "S_L": selector_left,
            "M_local_full": local_full["M"],
            "C_local_full": local_full["C"],
            "K_local_full": local_full["K"],
            "T_local_static": local_transform,
            "M_controller_local": local_projected["M"],
            "C_controller_local": local_projected["C"],
            "K_controller_local": local_projected["K"],
            "A_continuous": a_matrix,
            "B_continuous": b_matrix,
            "Q_control": CARE_Q,
            "R_control_weight": CARE_R,
            "riccati_solution_P": p_solution,
            "controller_gain_full": gain_full,
            "controller_gain_active": gain_active,
            "DeltaK_full": delta_k,
            "DeltaC_full": delta_c,
            "DeltaK_active": delta_k,
            "DeltaC_active": delta_c,
            "physical_delay_left_factor": physical_left,
            "physical_delay_C_right_factor": physical_right_c,
            "physical_delay_K_right_factor": physical_right_k,
            "C2_physical_zero_delay": physical_c2,
            "K2_physical_zero_delay": physical_k2,
            "C1_physical_remainder": c_remainder,
            "K1_physical_remainder": k_remainder,
            "feedback_C_projected": feedback_c,
            "feedback_K_projected": feedback_k,
            "active_delay_left_factor": physical_left,
            "active_delay_C_right_factor": active_right_c,
            "active_delay_K_right_factor": active_right_k,
            "C2_active_zero_delay": active_c2,
            "K2_active_zero_delay": active_k2,
            "feedback_C_external": external_c,
            "feedback_K_external": external_k,
            "C_zero_delay_total": c_remainder + active_c2 + external_c,
            "K_zero_delay_total": k_remainder + active_k2 + external_k,
            "matrix_al": al_matrix,
            "integration_mass_operator": integration_mass,
            **operator,
        }
        field_errors = {
            field: relative_error(data[field], expected)
            for field, expected in expected_fields.items()
        }
        maximum_field_error = max(field_errors.values())
        identity_pass = (
            int(round(scalar(data["bundle_schema_version"]))) == 1
            and int(round(scalar(data["contract_id_code"]))) == CONTRACT_CODES[contract_id]
            and int(round(scalar(data["division"]))) == division
            and int(round(scalar(data["method_code"]))) == METHOD_CODES[method]
            and int(round(scalar(data["route_dimension"]))) == dimension
            and scalar(data["gain_scale"]) == 1.0
            and int(round(scalar(data["feedback_placement_code"]))) == placement_code
            and np.array_equal(
                np.asarray(data["channel_natural_dof_numbers"], dtype=np.float64).reshape(-1),
                np.asarray([int(name[3:]) for name in channel_contract["coordinates"]], dtype=np.float64),
            )
            and np.array_equal(
                np.asarray(data["channel_to_delay_exponent_code"], dtype=np.float64).reshape(-1),
                np.asarray([1.0, 2.0]),
            )
            and int(round(scalar(data["stage0_overall_pass_code"]))) == 1
        )

        if division == 2 and tuple(channel_contract["coordinates"]) == ("psi1", "psi11"):
            e1 = np.eye(15)[0, :]
            e11 = np.eye(15)[10, :]
            embedding_e1_error = relative_error(embedding.T[0:1, :], e1.reshape(1, -1))
            embedding_e11_error = relative_error(embedding.T[6:7, :], e11.reshape(1, -1))
            recovered_global = np.vstack((e1, e11)) @ recovery
            recovery_mapping_error = relative_error(selector_right, recovered_global)
            mapping_pass = max(embedding_e1_error, embedding_e11_error, recovery_mapping_error) <= 1.0e-12
            psi11_mapping_pass &= mapping_pass
            psi11_mapping_detail.append(
                {
                    "route_id": route_id,
                    "method": method,
                    "local_rows_zero_based": local_rows,
                    "embedding_e1_error": embedding_e1_error,
                    "embedding_e11_error": embedding_e11_error,
                    "recovered_selector_error": recovery_mapping_error,
                    "pass": mapping_pass,
                }
            )

        maximum_symmetry = max(
            symmetry_error(value)
            for value in (
                mass,
                damping,
                stiffness,
                local_projected["M"],
                local_projected["C"],
                local_projected["K"],
                p_solution,
            )
        )
        minimum_positive = min(
            minimum_symmetric_eigenvalue(value)
            for value in (
                mass,
                damping,
                stiffness,
                local_projected["M"],
                local_projected["C"],
                local_projected["K"],
                CARE_Q,
                CARE_R,
            )
        )
        control_rank, control_minimum = controllability_metrics(a_matrix, b_matrix)
        riccati_error = care_residual(a_matrix, b_matrix, CARE_Q, CARE_R, p_solution)
        closed_loop_metric = float(np.max(np.real(np.linalg.eigvals(a_matrix - b_matrix @ gain_active))))
        low_rank_error = max(
            relative_error(physical_left @ active_right_c, active_c2),
            relative_error(physical_left @ active_right_k, active_k2),
            relative_error(physical_left @ physical_right_c, physical_c2),
            relative_error(physical_left @ physical_right_k, physical_k2),
        )
        physical_closure = max(
            relative_error(c_remainder + physical_c2, damping),
            relative_error(k_remainder + physical_k2, stiffness),
        )
        total_closure = max(
            relative_error(c_remainder + active_c2 + external_c, damping + feedback_c),
            relative_error(k_remainder + active_k2 + external_k, stiffness + feedback_k),
        )
        zero_zero, zero_minus = zero_delay_operator(operator)
        zero_delay_closure = max(
            relative_error(
                zero_zero,
                -2.0 * mass_term + (damping + feedback_c) / dt + stiffness + feedback_k,
            ),
            relative_error(zero_minus, mass_term - (damping + feedback_c) / dt),
        )
        source_projection_error: float | None = None
        if tuple(channel_contract["coordinates"]) == ("psi1", "psi6"):
            source_projection_error = max(
                relative_error(
                    local_projected[symbol],
                    np.asarray(source[f"div{division}_local_psi1_psi6_projected_{symbol}"], dtype=np.float64),
                )
                for symbol in ("M", "C", "K")
            )
        independent_metrics[route_id] = {
            "maximum_symmetry_relative_error": maximum_symmetry,
            "minimum_positive_eigenvalue": minimum_positive,
            "recovery_rank": int(np.linalg.matrix_rank(recovery)),
            "selector_rank": int(np.linalg.matrix_rank(selector_right)),
            "local_master_zero_based": "/".join(str(value) for value in local_master),
            "local_static_constraint_relative_residual": local_static_residual,
            "local_projection_source_relative_error": source_projection_error,
            "controllability_rank": control_rank,
            "controllability_relative_minimum_singular_value": control_minimum,
            "care_relative_residual": riccati_error,
            "design_closed_loop_maximum_real_part": closed_loop_metric,
            "low_rank_factor_max_relative_error": low_rank_error,
            "physical_closure_max_relative_error": physical_closure,
            "zero_delay_total_closure_max_relative_error": total_closure,
            "zero_delay_operator_closure_max_relative_error": zero_delay_closure,
            "matrix_al_identity_relative_error": integration_error,
            "mass_term_rank": int(np.linalg.matrix_rank(mass_term)),
        }
        route_pass = maximum_field_error <= 1.0e-11 and identity_pass
        reconstruction_pass &= route_pass
        route_recalculation_rows.append(
            {
                "route_id": route_id,
                "contract_id": contract_id,
                "division": division,
                "method": method,
                "dimension": dimension,
                "feedback_placement": placement,
                "channel_pair": "/".join(channel_contract["coordinates"]),
                "maximum_independent_field_relative_error": maximum_field_error,
                "identity_fields_pass": identity_pass,
                "operator_sha256_recomputed": route_operator_sha256(dimension, dt, operator),
                "operator_sha256_recorded": item["route_operator_sha256"],
                "operator_sha256_pass": route_operator_sha256(dimension, dt, operator)
                == item["route_operator_sha256"],
                "route_reconstruction_pass": route_pass,
            }
        )
    check("all_12_native_bundles_independently_reconstructed", reconstruction_pass, route_recalculation_rows)
    check("division2_psi11_is_global_e11_through_recovery", psi11_mapping_pass, psi11_mapping_detail)

    # B1 与 B3 在第二类仅改变反馈位置，以下字段必须逐项不变。
    placement_invariant_fields = (
        "M",
        "C",
        "K",
        "R_recovery",
        "W_test_basis",
        "E_local_embedding",
        "J_local_selection",
        "S_R",
        "S_L",
        "M_local_full",
        "C_local_full",
        "K_local_full",
        "T_local_static",
        "M_controller_local",
        "C_controller_local",
        "K_controller_local",
        "A_continuous",
        "B_continuous",
        "Q_control",
        "R_control_weight",
        "riccati_solution_P",
        "controller_gain_full",
        "controller_gain_active",
        "DeltaK_full",
        "DeltaC_full",
        "DeltaK_active",
        "DeltaC_active",
        "physical_delay_left_factor",
        "physical_delay_C_right_factor",
        "physical_delay_K_right_factor",
        "C2_physical_zero_delay",
        "K2_physical_zero_delay",
        "C1_physical_remainder",
        "K1_physical_remainder",
        "feedback_C_projected",
        "feedback_K_projected",
        "C_zero_delay_total",
        "K_zero_delay_total",
        "dt",
        "matrix_al",
        "integration_mass_operator",
        "mass_term",
    )
    placement_invariance_detail: list[dict[str, Any]] = []
    placement_invariance_pass = True
    for method in METHODS:
        outside = native_data[f"B1_D2_{method}"]
        inside = native_data[f"B3_D2_{method}"]
        errors = {
            field: relative_error(inside[field], outside[field])
            for field in placement_invariant_fields
        }
        maximum_error = max(errors.values())
        passed = maximum_error <= 1.0e-12
        placement_invariance_pass &= passed
        placement_invariance_detail.append(
            {"method": method, "maximum_invariant_field_error": maximum_error, "pass": passed}
        )
    check(
        "B1_vs_B3_only_feedback_placement_changes_numeric_decomposition",
        placement_invariance_pass,
        placement_invariance_detail,
    )

    # B2 与 B3 在第二类仅改变通道映射，结构/积分矩阵必须逐项不变。
    mapping_invariant_fields = (
        "M",
        "C",
        "K",
        "R_recovery",
        "W_test_basis",
        "E_local_embedding",
        "M_local_full",
        "C_local_full",
        "K_local_full",
        "Q_control",
        "R_control_weight",
        "gain_scale",
        "dt",
        "matrix_al",
        "integration_mass_operator",
        "mass_term",
    )
    mapping_invariance_detail: list[dict[str, Any]] = []
    mapping_invariance_pass = True
    for method in METHODS:
        psi6 = native_data[f"B2_D2_{method}"]
        psi11 = native_data[f"B3_D2_{method}"]
        maximum_error = max(
            relative_error(psi11[field], psi6[field]) for field in mapping_invariant_fields
        )
        passed = maximum_error <= 1.0e-12
        mapping_invariance_pass &= passed
        mapping_invariance_detail.append(
            {"method": method, "maximum_invariant_field_error": maximum_error, "pass": passed}
        )
    check(
        "B2_vs_B3_only_division2_channel_mapping_changes_numeric_control_path",
        mapping_invariance_pass,
        mapping_invariance_detail,
    )

    # H 内/外必须在零时滞等价，但在非零时滞 Laurent 系数上出现正确的反馈平移。
    nonzero_delay_detail: list[dict[str, Any]] = []
    nonzero_delay_pass = True
    delays = (2, 5)
    for method in METHODS:
        outside_id = f"B1_D2_{method}"
        inside_id = f"B3_D2_{method}"
        outside = native_operators[outside_id]
        inside = native_operators[inside_id]
        zero_error = operator_pair_error(outside, inside)
        outside_coefficients = laurent_coefficients(outside, delays)
        inside_coefficients = laurent_coefficients(inside, delays)
        exponents = set(outside_coefficients) | set(inside_coefficients)
        actual_difference = {
            exponent: inside_coefficients.get(exponent, np.zeros_like(outside["mass_term"]))
            - outside_coefficients.get(exponent, np.zeros_like(outside["mass_term"]))
            for exponent in exponents
        }
        outside_data = native_data[outside_id]
        left = np.asarray(outside_data["physical_delay_left_factor"], dtype=np.float64)
        selector_right = np.asarray(outside_data["S_R"], dtype=np.float64)
        delta_c = np.asarray(outside_data["DeltaC_active"], dtype=np.float64)
        delta_k = np.asarray(outside_data["DeltaK_active"], dtype=np.float64)
        feedback_c = np.asarray(outside_data["feedback_C_projected"], dtype=np.float64)
        feedback_k = np.asarray(outside_data["feedback_K_projected"], dtype=np.float64)
        dt = scalar(outside_data["dt"])
        expected_difference: dict[int, np.ndarray] = defaultdict(
            lambda: np.zeros_like(outside["mass_term"])
        )
        expected_difference[0] += -feedback_c / dt - feedback_k
        expected_difference[-1] += feedback_c / dt
        delta_c_right = delta_c @ selector_right
        delta_k_right = delta_k @ selector_right
        for channel, delay in enumerate(delays):
            channel_delta_c = delta_c_right[channel, :]
            channel_delta_k = delta_k_right[channel, :]
            expected_difference[-delay] += np.outer(
                left[:, channel], channel_delta_c / dt + channel_delta_k
            )
            expected_difference[-(delay + 1)] += np.outer(
                left[:, channel], -channel_delta_c / dt
            )
        all_exponents = set(actual_difference) | set(expected_difference)
        difference_error = max(
            relative_error(
                actual_difference.get(exponent, np.zeros_like(outside["mass_term"])),
                expected_difference.get(exponent, np.zeros_like(outside["mass_term"])),
            )
            for exponent in all_exponents
        )
        nonzero_expected_exponents = [
            exponent
            for exponent, value in expected_difference.items()
            if float(np.linalg.norm(value, ord="fro")) > np.finfo(float).eps
        ]
        cancellation_roundoff_bound = max(
            64.0
            * np.finfo(float).eps
            * (
                float(np.linalg.norm(inside_coefficients[exponent], ord="fro"))
                + float(np.linalg.norm(outside_coefficients[exponent], ord="fro"))
                + float(np.linalg.norm(expected_difference[exponent], ord="fro"))
            )
            / float(np.linalg.norm(expected_difference[exponent], ord="fro"))
            for exponent in nonzero_expected_exponents
        )
        allowed_difference_error = max(1.0e-12, cancellation_roundoff_bound)
        difference_norm = math.sqrt(
            sum(float(np.linalg.norm(value, ord="fro")) ** 2 for value in actual_difference.values())
        )
        passed = (
            zero_error <= 1.0e-12
            and difference_error <= allowed_difference_error
            and difference_norm > 0.0
        )
        nonzero_delay_pass &= passed
        nonzero_delay_detail.append(
            {
                "method": method,
                "delays_l_j": list(delays),
                "zero_delay_operator_relative_error": zero_error,
                "nonzero_delay_coefficient_difference_norm": difference_norm,
                "nonzero_delay_expected_difference_relative_error": difference_error,
                "subtraction_conditioned_roundoff_bound": cancellation_roundoff_bound,
                "allowed_difference_relative_error": allowed_difference_error,
                "pass": passed,
            }
        )
    check(
        "H_inside_outside_nonzero_delay_coefficients_have_correct_sign_and_exponent",
        nonzero_delay_pass,
        nonzero_delay_detail,
    )

    # 独立重算 Stage0 表，包括与旧 R03 的源字段回归及成对零时滞算子误差。
    legacy_by_pair: dict[tuple[int, str], tuple[dict[str, np.ndarray], dict[str, np.ndarray]]] = {}
    for item in r03_reuse_contract["reuse_evidence"]["route_bundles"]:
        path = (REPO_ROOT / Path(item["repo_relative_path"])).resolve()
        if sha256_file(path) != item["mat_sha256"]:
            raise RuntimeError(f"R03 冻结路线哈希漂移：{item['bundle_id']}")
        legacy_data = load_numeric_mat(path)
        key = (int(item["division"]), item["method"])
        legacy_by_pair[key] = (as_operator_legacy(legacy_data), legacy_data)
    check(
        "R03_reuse_contract_closes_all_six_legacy_routes",
        len(legacy_by_pair) == 6,
        {"pairs": sorted(f"D{division}_{method}" for division, method in legacy_by_pair)},
    )

    regression_mapping = {
        "M": "M",
        "C": "C",
        "K": "K",
        "R_recovery": "R",
        "E_local_embedding": "E",
        "J_local_selection": "J",
        "S_R": "S_R",
        "S_L": "S_L",
        "M_controller_local": "M_controller_local",
        "C_controller_local": "C_controller_local",
        "K_controller_local": "K_controller_local",
        "Q_control": "Q_control",
        "R_control_weight": "R_control_weight",
        "riccati_solution_P": "riccati_solution_P",
        "controller_gain_full": "controller_gain",
        "DeltaK_full": "DeltaK",
        "DeltaC_full": "DeltaC",
        "physical_delay_left_factor": "delay_C_left_factor",
        "physical_delay_C_right_factor": "delay_C_right_factor",
        "physical_delay_K_right_factor": "delay_K_right_factor",
        "C1_physical_remainder": "C1",
        "K1_physical_remainder": "K1",
        "feedback_C_projected": "feedback_C",
        "feedback_K_projected": "feedback_K",
        "matrix_al": "matrix_al",
        "integration_mass_operator": "integration_mass_operator",
    }
    stage0_compare_rows: list[dict[str, Any]] = []
    stage0_compare_pass = True
    for route_id, metrics in sorted(independent_metrics.items()):
        row = gates[route_id]
        contract_id = route_id.split("_", 1)[0]
        division = int(row["division"])
        method = row["method"]
        if contract_id == "B2":
            legacy_operator, legacy_data = legacy_by_pair[(division, method)]
            regression_error = max(
                relative_error(native_data[route_id][new_key], legacy_data[old_key])
                for new_key, old_key in regression_mapping.items()
            )
            paired_error = operator_pair_error(native_operators[route_id], legacy_operator)
        elif contract_id == "B1":
            partner_id = f"B3_D{division}_{method}"
            if partner_id not in native_operators:
                partner_id = f"B2_D{division}_{method}"
            regression_error = None
            paired_error = operator_pair_error(native_operators[route_id], native_operators[partner_id])
        elif contract_id == "B3":
            partner_id = f"B1_D{division}_{method}"
            regression_error = None
            paired_error = operator_pair_error(native_operators[route_id], native_operators[partner_id])
        else:
            raise RuntimeError(route_id)

        numeric_columns = {
            "maximum_symmetry_relative_error": metrics["maximum_symmetry_relative_error"],
            "minimum_positive_eigenvalue": metrics["minimum_positive_eigenvalue"],
            "local_static_constraint_relative_residual": metrics[
                "local_static_constraint_relative_residual"
            ],
            "controllability_relative_minimum_singular_value": metrics[
                "controllability_relative_minimum_singular_value"
            ],
            "care_relative_residual": metrics["care_relative_residual"],
            "design_closed_loop_maximum_real_part": metrics[
                "design_closed_loop_maximum_real_part"
            ],
            "low_rank_factor_max_relative_error": metrics["low_rank_factor_max_relative_error"],
            "physical_closure_max_relative_error": metrics[
                "physical_closure_max_relative_error"
            ],
            "zero_delay_total_closure_max_relative_error": metrics[
                "zero_delay_total_closure_max_relative_error"
            ],
            "zero_delay_operator_closure_max_relative_error": metrics[
                "zero_delay_operator_closure_max_relative_error"
            ],
            "matrix_al_identity_relative_error": metrics[
                "matrix_al_identity_relative_error"
            ],
            "paired_zero_delay_operator_relative_error": paired_error,
        }
        if regression_error is not None:
            numeric_columns["board20_r03_source_regression_relative_error"] = regression_error
        if metrics["local_projection_source_relative_error"] is not None:
            numeric_columns["local_projection_source_relative_error"] = metrics[
                "local_projection_source_relative_error"
            ]
        numeric_mismatches = {
            name: {"actual": value, "recorded": row[name]}
            for name, value in numeric_columns.items()
            if not float_matches(value, row[name])
        }
        identity_pass = (
            int(row["dimension"]) == int(native_data[route_id]["route_dimension"].reshape(-1)[0])
            and row["local_master_zero_based"] == metrics["local_master_zero_based"]
            and int(row["recovery_rank"]) == metrics["recovery_rank"]
            and int(row["selector_rank"]) == metrics["selector_rank"]
            and int(row["controllability_rank"]) == metrics["controllability_rank"]
            and int(row["mass_term_rank"]) == metrics["mass_term_rank"]
            and bool_text(row["preliminary_stage0_pass"])
            and bool_text(row["overall_stage0_pass"])
            and bool_text(row["paired_zero_delay_operator_pass"])
        )
        passed = not numeric_mismatches and identity_pass
        stage0_compare_pass &= passed
        stage0_compare_rows.append(
            {
                "route_id": route_id,
                "numeric_mismatch_count": len(numeric_mismatches),
                "numeric_mismatches": numeric_mismatches,
                "identity_and_pass_flags_match": identity_pass,
                "independent_paired_zero_delay_error": paired_error,
                "independent_r03_source_regression_error": regression_error,
                "pass": passed,
            }
        )
    check("stage0_csv_matches_independent_recalculation", stage0_compare_pass, stage0_compare_rows)

    inventory_pass = True
    inventory_mismatches: list[dict[str, Any]] = []
    expected_inventory_keys: set[tuple[str, str]] = set()
    for route_id, item in new_route_rows.items():
        path = (REPO_ROOT / Path(item["repo_relative_path"])).resolve()
        data = load_numeric_mat(path, preserve_shapes=True)
        for field, value in data.items():
            key = (route_id, field)
            expected_inventory_keys.add(key)
            row = array_inventory_map.get(key)
            array = np.asarray(value)
            expected_shape = "x".join(str(number) for number in array.shape)
            mismatch: dict[str, Any] = {}
            if row is None:
                mismatch["missing_row"] = True
            else:
                if row["shape"] != expected_shape:
                    mismatch["shape"] = {"actual": expected_shape, "recorded": row["shape"]}
                if row["dtype"] != array.dtype.str:
                    mismatch["dtype"] = {"actual": array.dtype.str, "recorded": row["dtype"]}
                if bool_text(row["finite"]) != bool(np.all(np.isfinite(array))):
                    mismatch["finite"] = True
                if row["semantic_array_sha256"] != semantic_array_sha256(array):
                    mismatch["semantic_array_sha256"] = True
                if row["legacy_bytes_only_sha256"] != legacy_array_sha256(array):
                    mismatch["legacy_bytes_only_sha256"] = True
            if mismatch:
                inventory_pass = False
                inventory_mismatches.append({"route_id": route_id, "field": field, **mismatch})
    extra_inventory = sorted(set(array_inventory_map) - expected_inventory_keys)
    if extra_inventory:
        inventory_pass = False
    check(
        "array_hash_inventory_matches_all_12_MAT_fields",
        inventory_pass,
        {"mismatches": inventory_mismatches, "extra_rows": extra_inventory},
    )

    mat_hash_pass = True
    mat_hash_detail: list[dict[str, Any]] = []
    for route_id, item in new_route_rows.items():
        row = mat_hash_map[route_id]
        path = (REPO_ROOT / Path(item["repo_relative_path"])).resolve()
        actual_hash = sha256_file(path)
        actual_operator_hash = route_operator_sha256(
            int(item["dimension"]), scalar(native_data[route_id]["dt"]), native_operators[route_id]
        )
        passed = (
            row["artifact_sha256"] == actual_hash
            and row["route_operator_sha256"] == actual_operator_hash
            and int(row["bytes"]) == path.stat().st_size
            and row["effective_science_contract_sha256"]
            == item["effective_science_contract_sha256"]
        )
        mat_hash_pass &= passed
        mat_hash_detail.append(
            {
                "route_id": route_id,
                "bytes": path.stat().st_size,
                "artifact_sha256": actual_hash,
                "route_operator_sha256": actual_operator_hash,
                "pass": passed,
            }
        )
    check("mat_artifact_hash_table_matches_all_12_MAT_files", mat_hash_pass, mat_hash_detail)

    summary = {
        "schema_version": "FIG10_NUMERIC_BUNDLE_INDEPENDENT_AUDIT_V1",
        "status": "PASS" if not failures else "FAIL",
        "scope": "READ_ONLY_NUMERIC_BUNDLE_AUDIT_NO_ROOTS_NO_GRID_NO_TARGET_EVALUATION",
        "repo_root": str(REPO_ROOT),
        "case_dir": str(CASE_DIR),
        "counts": {
            "checks": len(checks),
            "passed": sum(item["passed"] for item in checks),
            "failed": len(failures),
            "new_mat_files": len(new_route_rows),
            "route_assignments": len(assignments),
            "stage0_rows": len(gate_rows),
        },
        "failed_checks": failures,
        "checks": checks,
        "contract_differences": contract_diffs,
        "target_dependency_audit": {
            "forbidden_asset_markers": list(forbidden_asset_markers),
            "generator_forbidden_hits": forbidden_hits,
            "source_fingerprints": source_fingerprint_results,
            "imported_modules": imported_modules,
            "reused_fullgrid_validation_scope": validation_scope,
        },
        "psi11_mapping": psi11_mapping_detail,
        "nonzero_delay_feedback_placement": nonzero_delay_detail,
        "stage0_recalculation": stage0_compare_rows,
    }
    write_json(SCRIPT_DIR / "numeric_bundle_independent_audit_summary.json", summary)
    write_json(SCRIPT_DIR / "numeric_bundle_contract_diff.json", contract_diffs)
    write_csv(
        SCRIPT_DIR / "numeric_bundle_assignment_hash_recheck.csv",
        assignment_hash_rows,
        list(assignment_hash_rows[0]),
    )
    write_csv(
        SCRIPT_DIR / "numeric_bundle_route_recalculation.csv",
        route_recalculation_rows,
        list(route_recalculation_rows[0]),
    )
    print(json.dumps({
        "status": summary["status"],
        "checks": summary["counts"]["checks"],
        "passed": summary["counts"]["passed"],
        "failed": summary["counts"]["failed"],
        "failed_checks": failures,
        "summary_path": str(SCRIPT_DIR / "numeric_bundle_independent_audit_summary.json"),
    }, ensure_ascii=False, sort_keys=True, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

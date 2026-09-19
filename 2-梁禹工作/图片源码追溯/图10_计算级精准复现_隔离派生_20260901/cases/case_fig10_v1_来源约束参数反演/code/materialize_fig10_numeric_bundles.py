#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块28：将B1/B2/B3冻结合同物化为数值路线包，但不求根、不跑网格。

默认 ``gain_scale=1`` 时只生成12条新路线：

* B1：仅生成第二类Original/Guyan/Craig--Bampton；第一类复用板块20 R03。
* B2：生成两类划分的全部六条路线。
* B3：仅生成第二类三条路线；第一类复用本轮B2。

``gain_scale`` 是单个显式CLI输入，不是搜索列表。允许范围为0至1。非1值被标记为
``TARGET_GUIDED_INFERRED_PARAMETER``，使用独立科学合同哈希与独立输出目录；此脚本
不会自动枚举、评价或选择任何参数。

允许读取的科学输入仅为：板块28冻结合同记录、板块20步骤8B冻结矩阵、板块20 R03
既有数值包与其验证证据。脚本不导入求根器，也不分配时滞网格。
"""

from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import io
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
from scipy.io import loadmat, savemat
from scipy.linalg import solve_continuous_are

import build_fig10_candidate_bundles as contract_builder


SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
CONTRACT_OUTPUT_DIR = CASE_DIR / "data" / "contract_layer"
DEFAULT_OUTPUT_ROOT = CASE_DIR / "data" / "numeric_bundles"

MATERIALIZATION_SCHEMA_VERSION = "fig10-numeric-bundle-v1"
MANIFEST_VERSION = "fig10-numeric-materialization-manifest-v1"
METHOD_ORDER = ("Original", "Guyan", "Craig_Bampton")
METHOD_CODE = {"Original": 1, "Guyan": 2, "Craig_Bampton": 3}
CONTRACT_CODE = {"B1": 1, "B2": 2, "B3": 3}
EXPECTED_DIMENSIONS = contract_builder.EXPECTED_DIMENSIONS

SYMMETRY_LIMIT = 1.0e-12
PROJECTION_LIMIT = 1.0e-12
FACTOR_LIMIT = 1.0e-12
CLOSURE_LIMIT = 1.0e-12
INTEGRATION_LIMIT = 1.0e-12
PAIR_LIMIT = 1.0e-12
R03_REGRESSION_LIMIT = 1.0e-12
RICCATI_LIMIT = 1.0e-6

CARE_Q = np.diag([1.0e6, 1.0e6, 1.0e4, 1.0e4])
CARE_R = np.diag([1.0e-2, 1.0e-2])

OPERATOR_FIELDS = (
    "mass_term",
    "base_zero",
    "base_minus_one",
    "delay_left",
    "delay_v_zero",
    "delay_v_minus_one",
)


class MaterializationError(RuntimeError):
    """数值物化或Stage0门禁失败。"""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MaterializationError(message)


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def pretty_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def csv_bytes(rows: Iterable[Mapping[str, Any]], fields: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=fields,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue().encode("utf-8")


def parse_gain_scale(text: str) -> tuple[Decimal, float, str]:
    try:
        decimal_value = Decimal(text)
    except InvalidOperation as exc:
        raise MaterializationError(f"gain_scale不是有效十进制数：{text}") from exc
    require(decimal_value.is_finite(), "gain_scale必须为有限十进制数")
    require(Decimal("0") <= decimal_value <= Decimal("1"), "gain_scale必须满足0<=gain_scale<=1")
    if decimal_value == 0:
        normalized = "0"
    else:
        normalized = format(decimal_value.normalize(), "f")
    return decimal_value, float(decimal_value), normalized


def gain_parameter_contract(normalized: str) -> dict[str, Any]:
    if normalized == "1":
        evidence_level = "SOURCE_ANCHOR_FULL_LQR"
    else:
        evidence_level = "TARGET_GUIDED_INFERRED_PARAMETER"
    return {
        "gain_scale_decimal": normalized,
        "bounds": {
            "lower": "0",
            "upper": "1",
            "lower_inclusive": True,
            "upper_inclusive": True,
        },
        "application": "DeltaK_active = gain_scale * DeltaK_CARE; DeltaC_active = gain_scale * DeltaC_CARE",
        "evidence_level": evidence_level,
        "search_status": "SINGLE_EXPLICIT_VALUE_ONLY_NO_SEARCH",
    }


def gain_slug(normalized: str) -> str:
    return normalized.replace("-", "m").replace(".", "p")


def effective_science_contract(
    base_science: dict[str, Any], parameter_contract: dict[str, Any]
) -> dict[str, Any]:
    return {
        "base_scientific_contract": copy.deepcopy(base_science),
        "continuous_parameter_contract": copy.deepcopy(parameter_contract),
    }


def effective_science_hash(
    base_science: dict[str, Any], parameter_contract: dict[str, Any]
) -> str:
    return sha256_bytes(canonical_json_bytes(effective_science_contract(base_science, parameter_contract)))


def numeric(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).copy()


def scalar(value: Any) -> float:
    return float(np.asarray(value, dtype=np.float64).reshape(-1)[0])


def mat_scalar(value: float | int | bool) -> np.ndarray:
    return np.asarray([[value]], dtype=np.float64)


def utf8_uint8(value: str) -> np.ndarray:
    return np.frombuffer(value.encode("utf-8"), dtype=np.uint8).reshape(-1, 1)


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected, ord="fro") / denominator)


def symmetry_error(value: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(value, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(value - value.T, ord="fro") / denominator)


def minimum_symmetric_eigenvalue(value: np.ndarray) -> float:
    symmetric = 0.5 * (value + value.T)
    return float(np.min(np.linalg.eigvalsh(symmetric)))


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


def route_operator_sha256(
    dimension: int, dt: float, operator: Mapping[str, np.ndarray]
) -> str:
    inventory = {
        name: {
            "semantic_array_sha256": semantic_array_sha256(operator[name]),
            "dtype": np.ascontiguousarray(operator[name]).dtype.str,
            "shape": list(np.ascontiguousarray(operator[name]).shape),
        }
        for name in OPERATOR_FIELDS
    }
    contract = {
        "route_dimension": dimension,
        "dt_seconds": format(dt, ".17g"),
        "channel_to_delay_exponent": {"channel_1": "l", "channel_2": "j"},
        "operator_arrays": inventory,
    }
    return sha256_bytes(canonical_json_bytes(contract))


def controllability_rank(a_matrix: np.ndarray, b_matrix: np.ndarray) -> tuple[int, float]:
    blocks = [b_matrix]
    current = b_matrix.copy()
    for _ in range(1, a_matrix.shape[0]):
        current = a_matrix @ current
        blocks.append(current)
    matrix = np.hstack(blocks)
    singular_values = np.linalg.svd(matrix, compute_uv=False)
    rank = int(np.linalg.matrix_rank(matrix))
    normalized_minimum = float(
        singular_values[-1] / max(singular_values[0], np.finfo(float).eps)
    )
    return rank, normalized_minimum


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
    denominator = max(float(np.linalg.norm(q_weight, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(residual, ord="fro") / denominator)


def standard_local_static_projection(
    local_full: dict[str, np.ndarray], local_selection: np.ndarray
) -> tuple[dict[str, np.ndarray], np.ndarray, float, list[int]]:
    local_dimension = local_full["M"].shape[0]
    require(local_selection.shape == (2, local_dimension), "局部选择矩阵形状必须为2×局部维数")
    require(np.linalg.matrix_rank(local_selection) == 2, "局部选择矩阵必须秩2")
    master = [int(np.argmax(np.abs(row))) for row in local_selection]
    require(len(set(master)) == 2, "两个局部主自由度不得重复")
    for row, index in zip(local_selection, master):
        expected = np.zeros(local_dimension)
        expected[index] = 1.0
        require(np.array_equal(row, expected), "局部选择矩阵必须由两条自然单位行组成")
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


def continuous_state_matrices(
    mass: np.ndarray, damping: np.ndarray, stiffness: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    identity = np.eye(2)
    zero = np.zeros((2, 2))
    a_matrix = np.block(
        [
            [zero, identity],
            [-np.linalg.solve(mass, stiffness), -np.linalg.solve(mass, damping)],
        ]
    )
    b_matrix = np.vstack((zero, np.linalg.solve(mass, identity)))
    return a_matrix, b_matrix


def route_matrix_al(
    mass: np.ndarray, damping: np.ndarray, stiffness: np.ndarray, dt: float
) -> tuple[np.ndarray, np.ndarray, float]:
    operator = 4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness
    al_matrix = np.linalg.solve(operator, 4.0 * mass)
    mass_right_div_al = np.linalg.solve(al_matrix.T, mass.T).T
    expected = mass + 0.5 * dt * damping + 0.25 * dt**2 * stiffness
    return al_matrix, mass_right_div_al, relative_error(mass_right_div_al, expected)


def base_prefix(division: int, method: str) -> str:
    if method == "Original":
        return f"div{division}_Original_source_full15"
    if method == "Guyan":
        return f"div{division}_Guyan_source_standard_congruence"
    if method == "Craig_Bampton":
        return f"div{division}_Craig_Bampton_source_sorted_three_modes"
    raise MaterializationError(f"未知方法：{method}")


def recovery_key(method: str) -> str:
    if method in METHOD_ORDER:
        return method
    raise MaterializationError(f"未知恢复矩阵方法：{method}")


def load_contract_records() -> tuple[dict[str, dict[str, Any]], dict[str, Any], dict[str, Path]]:
    expected_files, _ = contract_builder.expected_output_files()
    contract_builder.verify_existing_files(CONTRACT_OUTPUT_DIR, expected_files)
    generated_records, registry, sources = contract_builder.build_records()
    expected_by_id = {record["contract_id"]: record for record in generated_records}
    actual: dict[str, dict[str, Any]] = {}
    for contract_id in ("B1", "B2", "B3", "R03_REUSE"):
        path = CONTRACT_OUTPUT_DIR / f"{contract_id}.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        require(value == expected_by_id[contract_id], f"冻结合同记录已漂移：{contract_id}")
        actual[contract_id] = value
    return actual, registry, sources


def load_frozen_source(path: Path) -> dict[str, Any]:
    data = loadmat(path, simplify_cells=True)
    return {key: value for key, value in data.items() if not key.startswith("__")}


def expected_new_route_keys(gain_normalized: str) -> list[tuple[str, int, str]]:
    keys: list[tuple[str, int, str]] = []
    for contract_id in ("B1", "B2", "B3"):
        for division in (1, 2):
            for method in METHOD_ORDER:
                if contract_id == "B3" and division == 1:
                    continue
                if contract_id == "B1" and division == 1 and gain_normalized == "1":
                    continue
                keys.append((contract_id, division, method))
    expected_count = 12 if gain_normalized == "1" else 15
    require(len(keys) == expected_count, "新增路线计数内部错误")
    return keys


@dataclass
class RouteBuild:
    contract_id: str
    division: int
    method: str
    dimension: int
    base_contract_hash: str
    effective_contract_hash: str
    feedback_placement: str
    channel_pair: tuple[str, str]
    payload: dict[str, np.ndarray]
    operator: dict[str, np.ndarray]
    gate: dict[str, Any]
    paired_route_id: str | None = None
    paired_zero_delay_operator_error: float | None = None
    operator_sha256: str = ""
    relative_mat_path: str = ""
    artifact_sha256: str = ""

    @property
    def route_id(self) -> str:
        return f"{self.contract_id}_D{self.division}_{self.method}"


def build_one_route(
    source: dict[str, Any],
    contract_record: dict[str, Any],
    effective_hash: str,
    division: int,
    method: str,
    gain_scale: float,
    parameter_status_code: int,
) -> RouteBuild:
    contract_id = contract_record["contract_id"]
    science = contract_record["scientific_contract"]
    prefix = base_prefix(division, method)
    mass = numeric(source[f"{prefix}_M"])
    damping = numeric(source[f"{prefix}_C"])
    stiffness = numeric(source[f"{prefix}_K"])
    dimension = mass.shape[0]
    expected_dimension = EXPECTED_DIMENSIONS[division][method]
    recovery = numeric(source[f"div{division}_{recovery_key(method)}_recovery_natural"])
    test_basis = recovery.copy()
    embedding = numeric(source[f"div{division}_local_embedding_E"])
    local_full = {
        symbol: numeric(source[f"div{division}_local_full_{symbol}"])
        for symbol in ("M", "C", "K")
    }
    channel_contract = science["actuation_and_delay_channels"][f"division_{division}"]
    channel_pair = tuple(channel_contract["coordinates"])
    local_rows = channel_contract["local_selector_zero_based"]
    local_dimension = local_full["M"].shape[0]
    local_selection = np.eye(local_dimension, dtype=np.float64)[local_rows, :]
    local_projected, local_transform, local_static_residual, local_master = (
        standard_local_static_projection(local_full, local_selection)
    )

    dt = scalar(source[f"div{division}_source_dt"])
    a_matrix, b_matrix = continuous_state_matrices(
        local_projected["M"], local_projected["C"], local_projected["K"]
    )
    care_solution = solve_continuous_are(a_matrix, b_matrix, CARE_Q, CARE_R)
    gain_full = np.linalg.solve(CARE_R, b_matrix.T @ care_solution)
    gain_active = gain_scale * gain_full
    delta_k_full = gain_full[:, :2]
    delta_c_full = gain_full[:, 2:]
    delta_k_active = gain_scale * delta_k_full
    delta_c_active = gain_scale * delta_c_full
    closed_loop_eigenvalues = np.linalg.eigvals(a_matrix - b_matrix @ gain_active)
    design_stability_metric = float(np.max(np.real(closed_loop_eigenvalues)))
    riccati_error = care_residual(a_matrix, b_matrix, CARE_Q, CARE_R, care_solution)
    control_rank, controllability_relative_minimum = controllability_rank(a_matrix, b_matrix)

    selector_right = local_selection @ embedding.T @ recovery
    selector_left = local_selection @ embedding.T @ test_basis
    physical_right_c = local_selection @ local_full["C"] @ embedding.T @ recovery
    physical_right_k = local_selection @ local_full["K"] @ embedding.T @ recovery
    physical_left = selector_left.T
    physical_c2 = physical_left @ physical_right_c
    physical_k2 = physical_left @ physical_right_k
    damping_remainder = damping - physical_c2
    stiffness_remainder = stiffness - physical_k2

    feedback_projected_c = selector_left.T @ delta_c_active @ selector_right
    feedback_projected_k = selector_left.T @ delta_k_active @ selector_right
    feedback_placement = science["delay_and_feedback"]["feedback_placement"]
    if feedback_placement == "OUTSIDE_H":
        active_right_c = physical_right_c.copy()
        active_right_k = physical_right_k.copy()
        feedback_external_c = feedback_projected_c.copy()
        feedback_external_k = feedback_projected_k.copy()
        feedback_placement_code = 1
    elif feedback_placement == "INSIDE_H":
        active_right_c = physical_right_c + delta_c_active @ selector_right
        active_right_k = physical_right_k + delta_k_active @ selector_right
        feedback_external_c = np.zeros_like(feedback_projected_c)
        feedback_external_k = np.zeros_like(feedback_projected_k)
        feedback_placement_code = 2
    else:
        raise MaterializationError(f"未知反馈位置：{feedback_placement}")
    active_c2 = physical_left @ active_right_c
    active_k2 = physical_left @ active_right_k

    al_matrix, integration_mass_operator, integration_error = route_matrix_al(
        mass, damping, stiffness, dt
    )
    mass_term = integration_mass_operator / (dt * dt)
    base_zero = (
        -2.0 * mass_term
        + damping_remainder / dt
        + stiffness_remainder
        + feedback_external_c / dt
        + feedback_external_k
    )
    base_minus_one = (
        mass_term - damping_remainder / dt - feedback_external_c / dt
    )
    delay_left = physical_left.copy()
    delay_v_zero = active_right_c / dt + active_right_k
    delay_v_minus_one = -active_right_c / dt
    register_scales = np.maximum.reduce(
        (
            np.linalg.norm(delay_v_zero, axis=1),
            np.linalg.norm(delay_v_minus_one, axis=1),
            np.full(2, np.finfo(float).eps),
        )
    )
    operator = {
        "mass_term": np.ascontiguousarray(mass_term),
        "base_zero": np.ascontiguousarray(base_zero),
        "base_minus_one": np.ascontiguousarray(base_minus_one),
        "delay_left": np.ascontiguousarray(delay_left),
        "delay_v_zero": np.ascontiguousarray(delay_v_zero),
        "delay_v_minus_one": np.ascontiguousarray(delay_v_minus_one),
    }

    finite_pass = all(
        np.all(np.isfinite(value))
        for value in (
            mass,
            damping,
            stiffness,
            recovery,
            embedding,
            local_selection,
            local_transform,
            *local_projected.values(),
            a_matrix,
            b_matrix,
            care_solution,
            gain_full,
            gain_active,
            physical_left,
            physical_right_c,
            physical_right_k,
            active_right_c,
            active_right_k,
            feedback_projected_c,
            feedback_projected_k,
            feedback_external_c,
            feedback_external_k,
            al_matrix,
            integration_mass_operator,
            *operator.values(),
        )
    )
    dimension_pass = (
        mass.shape == (expected_dimension, expected_dimension)
        and damping.shape == mass.shape
        and stiffness.shape == mass.shape
        and recovery.shape == (15, expected_dimension)
        and embedding.shape[0] == 15
        and local_selection.shape == (2, embedding.shape[1])
        and selector_right.shape == (2, expected_dimension)
        and selector_left.shape == (2, expected_dimension)
        and local_projected["M"].shape == (2, 2)
    )
    maximum_symmetry_error = max(
        symmetry_error(value)
        for value in (
            mass,
            damping,
            stiffness,
            local_projected["M"],
            local_projected["C"],
            local_projected["K"],
            care_solution,
        )
    )
    minimum_positive_eigenvalue = min(
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
    recovery_rank = int(np.linalg.matrix_rank(recovery))
    selector_rank = int(np.linalg.matrix_rank(selector_right))
    active_c_factor_error = relative_error(physical_left @ active_right_c, active_c2)
    active_k_factor_error = relative_error(physical_left @ active_right_k, active_k2)
    physical_c_factor_error = relative_error(physical_left @ physical_right_c, physical_c2)
    physical_k_factor_error = relative_error(physical_left @ physical_right_k, physical_k2)
    low_rank_error = max(
        active_c_factor_error,
        active_k_factor_error,
        physical_c_factor_error,
        physical_k_factor_error,
    )
    physical_c_closure_error = relative_error(damping_remainder + physical_c2, damping)
    physical_k_closure_error = relative_error(stiffness_remainder + physical_k2, stiffness)
    physical_closure_error = max(physical_c_closure_error, physical_k_closure_error)
    total_c_closure_error = relative_error(
        damping_remainder + active_c2 + feedback_external_c,
        damping + feedback_projected_c,
    )
    total_k_closure_error = relative_error(
        stiffness_remainder + active_k2 + feedback_external_k,
        stiffness + feedback_projected_k,
    )
    total_closure_error = max(total_c_closure_error, total_k_closure_error)
    zero_delay_operator_zero = base_zero + delay_left @ delay_v_zero
    zero_delay_operator_minus_one = base_minus_one + delay_left @ delay_v_minus_one
    expected_zero = (
        -2.0 * mass_term
        + (damping + feedback_projected_c) / dt
        + stiffness
        + feedback_projected_k
    )
    expected_minus_one = mass_term - (damping + feedback_projected_c) / dt
    zero_delay_operator_closure_error = max(
        relative_error(zero_delay_operator_zero, expected_zero),
        relative_error(zero_delay_operator_minus_one, expected_minus_one),
    )
    mass_term_rank = int(np.linalg.matrix_rank(mass_term))

    local_projection_reference_status = "DERIVED_FROM_SOURCE_DOF_MAP"
    local_projection_source_error: float | None = None
    if channel_pair == ("psi1", "psi6"):
        source_projected = {
            symbol: numeric(source[f"div{division}_local_psi1_psi6_projected_{symbol}"])
            for symbol in ("M", "C", "K")
        }
        local_projection_source_error = max(
            relative_error(local_projected[symbol], source_projected[symbol])
            for symbol in ("M", "C", "K")
        )
        local_projection_reference_status = "STEP8B_PSI1_PSI6_MATCH"

    preliminary_pass = all(
        (
            finite_pass,
            dimension_pass,
            maximum_symmetry_error <= SYMMETRY_LIMIT,
            minimum_positive_eigenvalue > 0.0,
            recovery_rank == expected_dimension,
            selector_rank == 2,
            local_static_residual <= PROJECTION_LIMIT,
            local_projection_source_error is None
            or local_projection_source_error <= PROJECTION_LIMIT,
            control_rank == 4,
            riccati_error <= RICCATI_LIMIT,
            design_stability_metric < 0.0,
            low_rank_error <= FACTOR_LIMIT,
            physical_closure_error <= CLOSURE_LIMIT,
            total_closure_error <= CLOSURE_LIMIT,
            zero_delay_operator_closure_error <= CLOSURE_LIMIT,
            integration_error <= INTEGRATION_LIMIT,
            mass_term_rank == expected_dimension,
        )
    )

    gate: dict[str, Any] = {
        "route_id": f"{contract_id}_D{division}_{method}",
        "contract_id": contract_id,
        "division": division,
        "method": method,
        "dimension": dimension,
        "channel_pair": "/".join(channel_pair),
        "feedback_placement": feedback_placement,
        "gain_scale": format(gain_scale, ".17g"),
        "finite_pass": finite_pass,
        "dimension_pass": dimension_pass,
        "maximum_symmetry_relative_error": maximum_symmetry_error,
        "symmetry_pass": maximum_symmetry_error <= SYMMETRY_LIMIT,
        "minimum_positive_eigenvalue": minimum_positive_eigenvalue,
        "positive_definite_pass": minimum_positive_eigenvalue > 0.0,
        "recovery_rank": recovery_rank,
        "selector_rank": selector_rank,
        "rank_pass": recovery_rank == expected_dimension and selector_rank == 2,
        "local_master_zero_based": "/".join(str(value) for value in local_master),
        "local_static_constraint_relative_residual": local_static_residual,
        "local_projection_reference_status": local_projection_reference_status,
        "local_projection_source_relative_error": (
            "" if local_projection_source_error is None else local_projection_source_error
        ),
        "local_projection_pass": local_static_residual <= PROJECTION_LIMIT
        and (
            local_projection_source_error is None
            or local_projection_source_error <= PROJECTION_LIMIT
        ),
        "controllability_rank": control_rank,
        "controllability_relative_minimum_singular_value": controllability_relative_minimum,
        "controllability_pass": control_rank == 4,
        "care_relative_residual": riccati_error,
        "care_pass": riccati_error <= RICCATI_LIMIT,
        "design_closed_loop_maximum_real_part": design_stability_metric,
        "design_closed_loop_stability_pass": design_stability_metric < 0.0,
        "low_rank_factor_max_relative_error": low_rank_error,
        "low_rank_factor_pass": low_rank_error <= FACTOR_LIMIT,
        "physical_closure_max_relative_error": physical_closure_error,
        "physical_closure_pass": physical_closure_error <= CLOSURE_LIMIT,
        "zero_delay_total_closure_max_relative_error": total_closure_error,
        "zero_delay_operator_closure_max_relative_error": zero_delay_operator_closure_error,
        "zero_delay_total_closure_pass": total_closure_error <= CLOSURE_LIMIT
        and zero_delay_operator_closure_error <= CLOSURE_LIMIT,
        "matrix_al_identity_relative_error": integration_error,
        "matrix_al_identity_pass": integration_error <= INTEGRATION_LIMIT,
        "mass_term_rank": mass_term_rank,
        "mass_term_rank_pass": mass_term_rank == expected_dimension,
        "board20_r03_source_regression_relative_error": "",
        "board20_r03_source_regression_pass": "NOT_APPLICABLE",
        "paired_route_id": "",
        "paired_zero_delay_operator_relative_error": "",
        "paired_zero_delay_operator_pass": False,
        "preliminary_stage0_pass": preliminary_pass,
        "overall_stage0_pass": False,
    }

    payload: dict[str, np.ndarray] = {
        "bundle_schema_version": mat_scalar(1),
        "contract_id_code": mat_scalar(CONTRACT_CODE[contract_id]),
        "division": mat_scalar(division),
        "method_code": mat_scalar(METHOD_CODE[method]),
        "route_dimension": mat_scalar(dimension),
        "base_contract_sha256_utf8": utf8_uint8(contract_record["contract_hash"]),
        "effective_contract_sha256_utf8": utf8_uint8(effective_hash),
        "gain_scale": mat_scalar(gain_scale),
        "gain_parameter_status_code": mat_scalar(parameter_status_code),
        "feedback_placement_code": mat_scalar(feedback_placement_code),
        "channel_natural_dof_numbers": np.asarray(
            [[int(channel_pair[0][3:]), int(channel_pair[1][3:])]], dtype=np.float64
        ),
        "channel_to_delay_exponent_code": np.asarray([[1.0, 2.0]]),
        "M": mass,
        "C": damping,
        "K": stiffness,
        "R_recovery": recovery,
        "W_test_basis": test_basis,
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
        "Q_control": CARE_Q.copy(),
        "R_control_weight": CARE_R.copy(),
        "riccati_solution_P": care_solution,
        "controller_gain_full": gain_full,
        "controller_gain_active": gain_active,
        "DeltaK_full": delta_k_full,
        "DeltaC_full": delta_c_full,
        "DeltaK_active": delta_k_active,
        "DeltaC_active": delta_c_active,
        "physical_delay_left_factor": physical_left,
        "physical_delay_C_right_factor": physical_right_c,
        "physical_delay_K_right_factor": physical_right_k,
        "C2_physical_zero_delay": physical_c2,
        "K2_physical_zero_delay": physical_k2,
        "C1_physical_remainder": damping_remainder,
        "K1_physical_remainder": stiffness_remainder,
        "feedback_C_projected": feedback_projected_c,
        "feedback_K_projected": feedback_projected_k,
        "active_delay_left_factor": physical_left,
        "active_delay_C_right_factor": active_right_c,
        "active_delay_K_right_factor": active_right_k,
        "C2_active_zero_delay": active_c2,
        "K2_active_zero_delay": active_k2,
        "feedback_C_external": feedback_external_c,
        "feedback_K_external": feedback_external_k,
        "C_zero_delay_total": damping_remainder + active_c2 + feedback_external_c,
        "K_zero_delay_total": stiffness_remainder + active_k2 + feedback_external_k,
        "dt": mat_scalar(dt),
        "matrix_al": al_matrix,
        "integration_mass_operator": integration_mass_operator,
        "mass_term": mass_term,
        "base_zero": base_zero,
        "base_minus_one": base_minus_one,
        "delay_left": delay_left,
        "delay_v_zero": delay_v_zero,
        "delay_v_minus_one": delay_v_minus_one,
        "register_scales": register_scales.reshape(-1, 1),
        "closed_loop_eigenvalues_real": np.real(closed_loop_eigenvalues).reshape(-1, 1),
        "closed_loop_eigenvalues_imag": np.imag(closed_loop_eigenvalues).reshape(-1, 1),
        "stage0_local_static_residual": mat_scalar(local_static_residual),
        "stage0_care_residual": mat_scalar(riccati_error),
        "stage0_design_stability_metric": mat_scalar(design_stability_metric),
        "stage0_low_rank_error": mat_scalar(low_rank_error),
        "stage0_physical_closure_error": mat_scalar(physical_closure_error),
        "stage0_total_closure_error": mat_scalar(total_closure_error),
        "stage0_zero_delay_operator_closure_error": mat_scalar(
            zero_delay_operator_closure_error
        ),
        "stage0_matrix_al_identity_error": mat_scalar(integration_error),
    }
    return RouteBuild(
        contract_id=contract_id,
        division=division,
        method=method,
        dimension=dimension,
        base_contract_hash=contract_record["contract_hash"],
        effective_contract_hash=effective_hash,
        feedback_placement=feedback_placement,
        channel_pair=channel_pair,
        payload=payload,
        operator=operator,
        gate=gate,
    )


def load_board20_operator(path: Path) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    data = loadmat(path, squeeze_me=True, struct_as_record=False)
    dimension = int(round(scalar(data["route_dimension"])))
    dt = scalar(data["dt"])
    integration_mass_operator = numeric(data["integration_mass_operator"])
    c1 = numeric(data["C1"])
    k1 = numeric(data["K1"])
    delay_c_left = numeric(data["delay_C_left_factor"])
    delay_c_right = numeric(data["delay_C_right_factor"])
    delay_k_left = numeric(data["delay_K_left_factor"])
    delay_k_right = numeric(data["delay_K_right_factor"])
    feedback_c = numeric(data["feedback_C"])
    feedback_k = numeric(data["feedback_K"])
    require(delay_c_left.shape == (dimension, 2), f"板块20 R03左因子形状错误：{path}")
    require(relative_error(delay_c_left, delay_k_left) <= FACTOR_LIMIT, "板块20 R03 C/K左因子不共享")
    mass_term = integration_mass_operator / (dt * dt)
    operator = {
        "mass_term": mass_term,
        "base_zero": -2.0 * mass_term + c1 / dt + k1 + feedback_c / dt + feedback_k,
        "base_minus_one": mass_term - c1 / dt - feedback_c / dt,
        "delay_left": delay_c_left,
        "delay_v_zero": delay_c_right / dt + delay_k_right,
        "delay_v_minus_one": -delay_c_right / dt,
    }
    return operator, {key: numeric(value) for key, value in data.items() if not key.startswith("__")}


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
    return max(
        relative_error(left_zero, right_zero),
        relative_error(left_minus, right_minus),
    )


def board20_source_regression_error(
    route: RouteBuild, board20_data: Mapping[str, np.ndarray]
) -> float:
    mappings = {
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
    errors = []
    for new_key, old_key in mappings.items():
        require(old_key in board20_data, f"板块20 R03包缺字段：{old_key}")
        errors.append(relative_error(route.payload[new_key], numeric(board20_data[old_key])))
    return max(errors)


def finalize_route_gates(
    routes: list[RouteBuild],
    r03_lookup: dict[tuple[int, str], dict[str, Any]],
    gain_normalized: str,
) -> None:
    by_key = {(route.contract_id, route.division, route.method): route for route in routes}
    old_operator_cache: dict[tuple[int, str], dict[str, np.ndarray]] = {}
    old_data_cache: dict[tuple[int, str], dict[str, np.ndarray]] = {}
    for key, item in r03_lookup.items():
        operator, data = load_board20_operator(item["path"])
        old_operator_cache[key] = operator
        old_data_cache[key] = data
        item["route_operator_sha256"] = route_operator_sha256(
            item["dimension"], scalar(data["dt"]), operator
        )

    for route in routes:
        pair_error: float
        pair_id: str
        if route.contract_id == "B2":
            if gain_normalized == "1":
                pair_operator = old_operator_cache[(route.division, route.method)]
                pair_id = f"D{route.division}_{route.method}_R03"
                regression_error = board20_source_regression_error(
                    route, old_data_cache[(route.division, route.method)]
                )
                route.gate["board20_r03_source_regression_relative_error"] = regression_error
                route.gate["board20_r03_source_regression_pass"] = (
                    regression_error <= R03_REGRESSION_LIMIT
                )
            else:
                # 同一物理/控制数据的H外零时滞解析量；不是新路线，也不写包。
                payload = route.payload
                dt = scalar(payload["dt"])
                mass_term = payload["mass_term"]
                c1 = payload["C1_physical_remainder"]
                k1 = payload["K1_physical_remainder"]
                feedback_c = payload["feedback_C_projected"]
                feedback_k = payload["feedback_K_projected"]
                physical_left = payload["physical_delay_left_factor"]
                physical_c = payload["physical_delay_C_right_factor"]
                physical_k = payload["physical_delay_K_right_factor"]
                pair_operator = {
                    "mass_term": mass_term,
                    "base_zero": -2.0 * mass_term
                    + c1 / dt
                    + k1
                    + feedback_c / dt
                    + feedback_k,
                    "base_minus_one": mass_term - c1 / dt - feedback_c / dt,
                    "delay_left": physical_left,
                    "delay_v_zero": physical_c / dt + physical_k,
                    "delay_v_minus_one": -physical_c / dt,
                }
                pair_id = f"ANALYTIC_H_OUT_D{route.division}_{route.method}"
                route.gate["board20_r03_source_regression_pass"] = "NOT_APPLICABLE_NONUNIT_GAIN"
            pair_error = operator_pair_error(route.operator, pair_operator)
        elif route.contract_id == "B1":
            partner = by_key.get(("B3", route.division, route.method))
            if partner is None:
                partner = by_key[("B2", route.division, route.method)]
            pair_error = operator_pair_error(route.operator, partner.operator)
            pair_id = partner.route_id
        elif route.contract_id == "B3":
            partner = by_key[("B1", route.division, route.method)]
            pair_error = operator_pair_error(route.operator, partner.operator)
            pair_id = partner.route_id
        else:
            raise MaterializationError(f"未知路线合同：{route.contract_id}")
        route.paired_route_id = pair_id
        route.paired_zero_delay_operator_error = pair_error
        route.gate["paired_route_id"] = pair_id
        route.gate["paired_zero_delay_operator_relative_error"] = pair_error
        route.gate["paired_zero_delay_operator_pass"] = pair_error <= PAIR_LIMIT
        regression_pass = route.gate["board20_r03_source_regression_pass"]
        regression_ok = regression_pass in (
            True,
            "NOT_APPLICABLE",
            "NOT_APPLICABLE_NONUNIT_GAIN",
        )
        overall = bool(
            route.gate["preliminary_stage0_pass"]
            and route.gate["paired_zero_delay_operator_pass"]
            and regression_ok
        )
        route.gate["overall_stage0_pass"] = overall
        route.payload["stage0_paired_zero_delay_operator_error"] = mat_scalar(pair_error)
        route.payload["stage0_board20_r03_source_regression_error"] = mat_scalar(
            0.0
            if route.gate["board20_r03_source_regression_relative_error"] == ""
            else float(route.gate["board20_r03_source_regression_relative_error"])
        )
        route.payload["stage0_overall_pass_code"] = mat_scalar(int(overall))
        route.operator_sha256 = route_operator_sha256(
            route.dimension, scalar(route.payload["dt"]), route.operator
        )

    failed = [route.route_id for route in routes if not route.gate["overall_stage0_pass"]]
    require(not failed, f"Stage0门禁失败：{failed}")


def make_r03_lookup(
    r03_record: dict[str, Any], repo_root: Path
) -> dict[tuple[int, str], dict[str, Any]]:
    lookup: dict[tuple[int, str], dict[str, Any]] = {}
    for item in r03_record["reuse_evidence"]["route_bundles"]:
        path = contract_builder.resolve_repo_relative(repo_root, item["repo_relative_path"])
        require(path.is_file(), f"R03复用包缺失：{path}")
        require(sha256_file(path) == item["mat_sha256"], f"R03复用包哈希漂移：{item['bundle_id']}")
        key = (item["division"], item["method"])
        lookup[key] = {
            **copy.deepcopy(item),
            "path": path,
        }
    require(len(lookup) == 6, "R03六路线复用查找表不闭合")
    return lookup


def build_materialization(
    gain_text: str,
) -> tuple[
    list[RouteBuild],
    dict[str, dict[str, Any]],
    dict[str, Any],
    dict[str, Path],
    dict[tuple[int, str], dict[str, Any]],
    dict[str, str],
    dict[str, Any],
]:
    _, gain_value, gain_normalized = parse_gain_scale(gain_text)
    parameter_contract = gain_parameter_contract(gain_normalized)
    parameter_status_code = 1 if gain_normalized == "1" else 2
    records, registry, sources = load_contract_records()
    repo_root = contract_builder.find_repo_root()
    frozen_source = load_frozen_source(sources["board20_step8b_frozen_mat"])
    effective_hashes = {
        contract_id: effective_science_hash(
            records[contract_id]["scientific_contract"], parameter_contract
        )
        for contract_id in ("B1", "B2", "B3")
    }
    require(len(set(effective_hashes.values())) == 3, "B1/B2/B3有效科学合同哈希不唯一")
    r03_lookup = make_r03_lookup(records["R03_REUSE"], repo_root)
    routes: list[RouteBuild] = []
    for contract_id, division, method in expected_new_route_keys(gain_normalized):
        routes.append(
            build_one_route(
                frozen_source,
                records[contract_id],
                effective_hashes[contract_id],
                division,
                method,
                gain_value,
                parameter_status_code,
            )
        )
    finalize_route_gates(routes, r03_lookup, gain_normalized)
    context = {
        "gain_scale_decimal": gain_normalized,
        "gain_scale_float64": gain_value,
        "parameter_contract": parameter_contract,
        "parameter_status_code": parameter_status_code,
        "repo_root": repo_root,
    }
    return routes, records, registry, sources, r03_lookup, effective_hashes, context


def write_mat_deterministic(path: Path, payload: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp"
    savemat(
        str(temporary),
        payload,
        do_compression=True,
        oned_as="column",
        appendmat=False,
        long_field_names=True,
    )
    fixed_header = b"MATLAB 5.0 MAT-file, Fig10 Stage0 deterministic numeric bundle"
    with temporary.open("r+b") as stream:
        stream.seek(0)
        stream.write(fixed_header.ljust(116, b" ")[:116])
    temporary.replace(path)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.parent / f".{path.name}.tmp"
    temporary.write_bytes(payload)
    temporary.replace(path)


GATE_FIELDS = [
    "route_id",
    "contract_id",
    "division",
    "method",
    "dimension",
    "channel_pair",
    "feedback_placement",
    "gain_scale",
    "finite_pass",
    "dimension_pass",
    "maximum_symmetry_relative_error",
    "symmetry_pass",
    "minimum_positive_eigenvalue",
    "positive_definite_pass",
    "recovery_rank",
    "selector_rank",
    "rank_pass",
    "local_master_zero_based",
    "local_static_constraint_relative_residual",
    "local_projection_reference_status",
    "local_projection_source_relative_error",
    "local_projection_pass",
    "controllability_rank",
    "controllability_relative_minimum_singular_value",
    "controllability_pass",
    "care_relative_residual",
    "care_pass",
    "design_closed_loop_maximum_real_part",
    "design_closed_loop_stability_pass",
    "low_rank_factor_max_relative_error",
    "low_rank_factor_pass",
    "physical_closure_max_relative_error",
    "physical_closure_pass",
    "zero_delay_total_closure_max_relative_error",
    "zero_delay_operator_closure_max_relative_error",
    "zero_delay_total_closure_pass",
    "matrix_al_identity_relative_error",
    "matrix_al_identity_pass",
    "mass_term_rank",
    "mass_term_rank_pass",
    "board20_r03_source_regression_relative_error",
    "board20_r03_source_regression_pass",
    "paired_route_id",
    "paired_zero_delay_operator_relative_error",
    "paired_zero_delay_operator_pass",
    "preliminary_stage0_pass",
    "overall_stage0_pass",
]

ASSIGNMENT_FIELDS = [
    "assignment_id",
    "global_contract_id",
    "base_contract_sha256",
    "effective_science_contract_sha256",
    "gain_scale",
    "division",
    "method",
    "dimension",
    "assignment_action",
    "source_route_id",
    "repo_relative_path",
    "artifact_sha256",
    "route_operator_sha256",
    "stage0_status",
]

ARRAY_FIELDS = [
    "route_id",
    "field",
    "shape",
    "dtype",
    "finite",
    "semantic_array_sha256",
    "legacy_bytes_only_sha256",
]

MAT_HASH_FIELDS = [
    "route_id",
    "repo_relative_path",
    "bytes",
    "artifact_sha256",
    "route_operator_sha256",
    "effective_science_contract_sha256",
]


def ensure_output_scope(output_dir: Path, effective_batch_hash: str) -> None:
    resolved = output_dir.resolve()
    try:
        resolved.relative_to(CASE_DIR.resolve())
    except ValueError as exc:
        raise MaterializationError("数值物化输出必须位于板块28隔离案例目录内") from exc
    if resolved.exists() and any(resolved.iterdir()):
        manifest_path = resolved / "materialization_manifest.json"
        require(manifest_path.is_file(), f"非空输出目录缺少可核验manifest，拒绝覆盖：{resolved}")
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
        require(
            existing.get("effective_batch_sha256") == effective_batch_hash,
            "输出目录已有不同gain_scale或科学合同，拒绝覆盖",
        )


def build_route_assignments(
    routes: list[RouteBuild],
    records: dict[str, dict[str, Any]],
    r03_lookup: dict[tuple[int, str], dict[str, Any]],
    effective_hashes: dict[str, str],
    context: dict[str, Any],
) -> list[dict[str, Any]]:
    by_key = {(route.contract_id, route.division, route.method): route for route in routes}
    assignments: list[dict[str, Any]] = []
    for contract_id in ("B1", "B2", "B3"):
        for division in (1, 2):
            for method in METHOD_ORDER:
                assignment_id = f"{contract_id}_D{division}_{method}"
                if contract_id == "B3" and division == 1:
                    source = by_key[("B2", division, method)]
                    action = "REUSE_MATERIALIZED_B2_ROUTE"
                    source_route_id = source.route_id
                    relative_path = source.relative_mat_path
                    artifact_hash = source.artifact_sha256
                    operator_hash = source.operator_sha256
                    stage0_status = "PASS_REUSED_CURRENT_BATCH"
                elif (
                    contract_id == "B1"
                    and division == 1
                    and context["gain_scale_decimal"] == "1"
                ):
                    source_old = r03_lookup[(division, method)]
                    action = "REUSE_BOARD20_R03_ROUTE"
                    source_route_id = source_old["bundle_id"]
                    relative_path = source_old["repo_relative_path"]
                    artifact_hash = source_old["mat_sha256"]
                    operator_hash = source_old["route_operator_sha256"]
                    stage0_status = "PASS_REUSED_BOARD20_VERIFIED"
                else:
                    source = by_key[(contract_id, division, method)]
                    action = "MATERIALIZED_STAGE0_PASS"
                    source_route_id = source.route_id
                    relative_path = source.relative_mat_path
                    artifact_hash = source.artifact_sha256
                    operator_hash = source.operator_sha256
                    stage0_status = "PASS"
                assignments.append(
                    {
                        "assignment_id": assignment_id,
                        "global_contract_id": contract_id,
                        "base_contract_sha256": records[contract_id]["contract_hash"],
                        "effective_science_contract_sha256": effective_hashes[contract_id],
                        "gain_scale": context["gain_scale_decimal"],
                        "division": division,
                        "method": method,
                        "dimension": EXPECTED_DIMENSIONS[division][method],
                        "assignment_action": action,
                        "source_route_id": source_route_id,
                        "repo_relative_path": relative_path,
                        "artifact_sha256": artifact_hash,
                        "route_operator_sha256": operator_hash,
                        "stage0_status": stage0_status,
                    }
                )
    require(len(assignments) == 18, "B1/B2/B3路线赋值必须为18条")
    return assignments


def materialize_to_directory(
    gain_text: str, output_dir: Path
) -> dict[str, Any]:
    (
        routes,
        records,
        registry,
        sources,
        r03_lookup,
        effective_hashes,
        context,
    ) = build_materialization(gain_text)
    effective_batch_contract = {
        "gain_parameter_contract": context["parameter_contract"],
        "effective_contract_hashes": effective_hashes,
        "new_route_keys": [route.route_id for route in routes],
    }
    effective_batch_hash = sha256_bytes(canonical_json_bytes(effective_batch_contract))
    ensure_output_scope(output_dir, effective_batch_hash)
    repo_root: Path = context["repo_root"]

    mat_hash_rows: list[dict[str, Any]] = []
    array_rows: list[dict[str, Any]] = []
    for route in routes:
        relative_mat = Path("new_route_bundles") / f"{route.route_id}.mat"
        mat_path = output_dir / relative_mat
        write_mat_deterministic(mat_path, route.payload)
        route.relative_mat_path = mat_path.resolve().relative_to(repo_root).as_posix()
        route.artifact_sha256 = sha256_file(mat_path)
        mat_hash_rows.append(
            {
                "route_id": route.route_id,
                "repo_relative_path": route.relative_mat_path,
                "bytes": mat_path.stat().st_size,
                "artifact_sha256": route.artifact_sha256,
                "route_operator_sha256": route.operator_sha256,
                "effective_science_contract_sha256": route.effective_contract_hash,
            }
        )
        for field, value in route.payload.items():
            array = np.asarray(value)
            array_rows.append(
                {
                    "route_id": route.route_id,
                    "field": field,
                    "shape": "x".join(str(number) for number in array.shape),
                    "dtype": array.dtype.str,
                    "finite": bool(np.all(np.isfinite(array))),
                    "semantic_array_sha256": semantic_array_sha256(array),
                    "legacy_bytes_only_sha256": legacy_array_sha256(array),
                }
            )

    assignments = build_route_assignments(
        routes, records, r03_lookup, effective_hashes, context
    )
    gate_payload = csv_bytes([route.gate for route in routes], GATE_FIELDS)
    assignment_payload = csv_bytes(assignments, ASSIGNMENT_FIELDS)
    array_payload = csv_bytes(array_rows, ARRAY_FIELDS)
    mat_hash_payload = csv_bytes(mat_hash_rows, MAT_HASH_FIELDS)
    tabular = {
        "stage0_gate_results.csv": gate_payload,
        "route_assignments.csv": assignment_payload,
        "array_hash_inventory.csv": array_payload,
        "mat_artifact_hashes.csv": mat_hash_payload,
    }
    for name, payload in tabular.items():
        atomic_write_bytes(output_dir / name, payload)

    source_fingerprints = [
        {
            "source_id": item["source_id"],
            "repo_relative_path": item["repo_relative_path"],
            "sha256": item["sha256"],
        }
        for item in registry["source_fingerprints"]
    ]
    contract_artifacts = []
    for contract_id in ("B1", "B2", "B3", "R03_REUSE"):
        path = CONTRACT_OUTPUT_DIR / f"{contract_id}.json"
        contract_artifacts.append(
            {
                "contract_id": contract_id,
                "repo_relative_path": path.resolve().relative_to(repo_root).as_posix(),
                "artifact_sha256": sha256_file(path),
                "base_science_contract_sha256": records[contract_id]["contract_hash"],
            }
        )
    manifest = {
        "manifest_version": MANIFEST_VERSION,
        "status": "PASS_STAGE0_NUMERIC_MATERIALIZATION",
        "scope": "NUMERIC_BUNDLES_ONLY_NO_ROOTS_NO_DELAY_GRID_NO_PARAMETER_SEARCH",
        "gain_parameter_contract": context["parameter_contract"],
        "effective_batch_sha256": effective_batch_hash,
        "base_contracts_unchanged": True,
        "effective_science_contracts": [
            {
                "contract_id": contract_id,
                "base_contract_sha256": records[contract_id]["contract_hash"],
                "effective_science_contract_sha256": effective_hashes[contract_id],
                "effective_science_contract": effective_science_contract(
                    records[contract_id]["scientific_contract"],
                    context["parameter_contract"],
                ),
            }
            for contract_id in ("B1", "B2", "B3")
        ],
        "counts": {
            "global_contracts": 3,
            "route_assignments": 18,
            "new_numeric_route_bundles": len(routes),
            "reused_route_assignments": 18 - len(routes),
            "stage0_pass": sum(bool(route.gate["overall_stage0_pass"]) for route in routes),
            "stage0_fail": sum(not bool(route.gate["overall_stage0_pass"]) for route in routes),
            "roots_computed": 0,
            "delay_grid_points_computed": 0,
            "parameter_candidates_evaluated": 0,
        },
        "new_routes": [
            {
                "route_id": route.route_id,
                "contract_id": route.contract_id,
                "division": route.division,
                "method": route.method,
                "dimension": route.dimension,
                "channel_pair": list(route.channel_pair),
                "feedback_placement": route.feedback_placement,
                "base_contract_sha256": route.base_contract_hash,
                "effective_science_contract_sha256": route.effective_contract_hash,
                "route_operator_sha256": route.operator_sha256,
                "repo_relative_path": route.relative_mat_path,
                "artifact_sha256": route.artifact_sha256,
                "stage0_status": "PASS",
            }
            for route in routes
        ],
        "route_assignments": assignments,
        "tabular_artifacts": [
            {
                "name": name,
                "sha256": sha256_bytes(payload),
                "bytes": len(payload),
            }
            for name, payload in tabular.items()
        ],
        "source_fingerprints": source_fingerprints,
        "contract_artifacts": contract_artifacts,
        "generator_artifacts": [
            {
                "repo_relative_path": Path(__file__).resolve().relative_to(repo_root).as_posix(),
                "sha256": sha256_file(Path(__file__).resolve()),
            },
            {
                "repo_relative_path": Path(contract_builder.__file__).resolve().relative_to(repo_root).as_posix(),
                "sha256": sha256_file(Path(contract_builder.__file__).resolve()),
            },
        ],
        "stage0_limits": {
            "symmetry_relative_error": SYMMETRY_LIMIT,
            "local_projection_relative_error": PROJECTION_LIMIT,
            "care_relative_residual": RICCATI_LIMIT,
            "low_rank_factor_relative_error": FACTOR_LIMIT,
            "physical_closure_relative_error": CLOSURE_LIMIT,
            "zero_delay_total_closure_relative_error": CLOSURE_LIMIT,
            "matrix_al_identity_relative_error": INTEGRATION_LIMIT,
            "paired_zero_delay_operator_relative_error": PAIR_LIMIT,
            "board20_r03_source_regression_relative_error": R03_REGRESSION_LIMIT,
        },
    }
    manifest_payload = pretty_json_bytes(manifest)
    atomic_write_bytes(output_dir / "materialization_manifest.json", manifest_payload)
    verify_materialized_directory(output_dir)
    return {
        "status": manifest["status"],
        "output_dir": str(output_dir.resolve()),
        "gain_scale": context["gain_scale_decimal"],
        "gain_evidence_level": context["parameter_contract"]["evidence_level"],
        "effective_batch_sha256": effective_batch_hash,
        "new_numeric_route_bundles": len(routes),
        "route_assignments": len(assignments),
        "stage0_pass": manifest["counts"]["stage0_pass"],
        "stage0_fail": manifest["counts"]["stage0_fail"],
        "roots_computed": 0,
        "delay_grid_points_computed": 0,
        "parameter_candidates_evaluated": 0,
        "manifest_sha256": sha256_bytes(manifest_payload),
    }


def verify_materialized_directory(output_dir: Path) -> dict[str, Any]:
    manifest_path = output_dir / "materialization_manifest.json"
    require(manifest_path.is_file(), "缺少物化manifest")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest.get("status") == "PASS_STAGE0_NUMERIC_MATERIALIZATION", "物化manifest状态不是PASS")
    counts = manifest["counts"]
    require(counts["stage0_fail"] == 0, "物化manifest记录Stage0失败")
    require(counts["roots_computed"] == 0, "物化层不得记录任何根")
    require(counts["delay_grid_points_computed"] == 0, "物化层不得记录时滞网格点")
    require(counts["parameter_candidates_evaluated"] == 0, "物化层不得记录参数候选")
    for item in manifest["new_routes"]:
        path = contract_builder.resolve_repo_relative(
            contract_builder.find_repo_root(), item["repo_relative_path"]
        )
        require(path.is_file(), f"物化MAT缺失：{path}")
        require(sha256_file(path) == item["artifact_sha256"], f"物化MAT哈希不符：{item['route_id']}")
    for item in manifest["tabular_artifacts"]:
        path = output_dir / item["name"]
        require(path.is_file(), f"表格工件缺失：{path}")
        require(sha256_file(path) == item["sha256"], f"表格工件哈希不符：{path}")
    return manifest


def directory_file_hashes(output_dir: Path) -> dict[str, str]:
    return {
        path.relative_to(output_dir).as_posix(): sha256_file(path)
        for path in sorted(output_dir.rglob("*"))
        if path.is_file()
    }


def default_output_dir_for_gain(gain_text: str) -> Path:
    _, _, normalized = parse_gain_scale(gain_text)
    status = "source_anchor" if normalized == "1" else "target_guided_inferred"
    return DEFAULT_OUTPUT_ROOT / f"gain_scale_{gain_slug(normalized)}_{status}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="物化Fig10 B1/B2/B3数值路线包；不求根、不跑网格")
    parser.add_argument(
        "--gain-scale",
        default="1.0",
        help="单个增益比例，范围0至1；默认1.0。此参数不接受列表或范围。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="隔离输出目录；省略时按规范化gain_scale自动分目录。",
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="只在内存中重建12/15条路线并执行Stage0，不写文件。",
    )
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="只校验已存在的物化目录，不重建、不写文件。",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    require(not (args.check_only and args.verify_existing), "--check-only与--verify-existing不能同时使用")
    output_dir = (
        args.output_dir.resolve()
        if args.output_dir is not None
        else default_output_dir_for_gain(args.gain_scale).resolve()
    )
    try:
        output_dir.relative_to(CASE_DIR.resolve())
    except ValueError as exc:
        raise MaterializationError("输出目录必须位于板块28隔离案例内") from exc

    if args.verify_existing:
        manifest = verify_materialized_directory(output_dir)
        summary = {
            "action": "VERIFY_EXISTING",
            "status": manifest["status"],
            "output_dir": str(output_dir),
            "gain_scale": manifest["gain_parameter_contract"]["gain_scale_decimal"],
            "counts": manifest["counts"],
            "directory_files": len(directory_file_hashes(output_dir)),
        }
    elif args.check_only:
        routes, _, _, _, _, _, context = build_materialization(args.gain_scale)
        summary = {
            "action": "CHECK_ONLY",
            "status": "PASS_STAGE0_IN_MEMORY",
            "gain_scale": context["gain_scale_decimal"],
            "gain_evidence_level": context["parameter_contract"]["evidence_level"],
            "new_numeric_route_bundles_if_written": len(routes),
            "stage0_pass": sum(bool(route.gate["overall_stage0_pass"]) for route in routes),
            "stage0_fail": sum(not bool(route.gate["overall_stage0_pass"]) for route in routes),
            "roots_computed": 0,
            "delay_grid_points_computed": 0,
            "parameter_candidates_evaluated": 0,
        }
    else:
        summary = materialize_to_directory(args.gain_scale, output_dir)
        summary["action"] = "WRITE_NUMERIC_BUNDLES"
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

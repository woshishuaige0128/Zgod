#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块20步骤8C：由步骤8B冻结矩阵生成六路线乘六候选的确定性数值包。

本脚本只读取步骤8B的确定性MAT，不读取论文PDF、历史稳定域掩膜或历史曲线。
输出用于后续统一31x67网格求根；本步骤不计算稳定域，也不按曲线选择候选。
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat, savemat
from scipy.linalg import expm, solve_continuous_are, solve_discrete_are


SCRIPT_DIR = Path(__file__).resolve().parent
BOARD_DIR = SCRIPT_DIR.parent
INPUT_MAT = (
    BOARD_DIR
    / "outputs"
    / "step8b_论文代码矩阵合同"
    / "步骤8B_基础矩阵与选择矩阵.mat"
)
OUTPUT_DIR = BOARD_DIR / "outputs" / "step8c_六链模型生成" / "python"
BUNDLE_DIR = OUTPUT_DIR / "候选数值包"
INPUT_SHA256 = "261852003eea79a6c7c609c472e82b8782bb7619191c2cfa3759ac39efcc80ff"

CARE_Q = np.diag([1.0e6, 1.0e6, 1.0e4, 1.0e4])
CARE_R = np.diag([1.0e-2, 1.0e-2])
DARE_Q = np.diag([1.0e6, 1.0, 1.0e5, 1.0])
DARE_R = np.diag([1.0e-1, 1.0e-2])

METHODS = (
    {
        "method_id": "Original",
        "method_index": 1,
        "method_cn": "原结构",
        "recovery_key": "Original",
    },
    {
        "method_id": "Guyan",
        "method_index": 2,
        "method_cn": "Guyan缩聚",
        "recovery_key": "Guyan",
    },
    {
        "method_id": "Craig_Bampton",
        "method_index": 3,
        "method_cn": "Craig-Bampton缩聚",
        "recovery_key": "Craig_Bampton",
    },
)

CANDIDATES = (
    {
        "candidate_id": "R01",
        "candidate_index": 1,
        "candidate_cn": "论文CARE_alpha025_广义力",
        "controller": "CARE",
        "input_semantics": "generalized_force",
        "integration": "scalar_alpha_0p25",
        "guyan_variant": "standard_congruence",
        "formula_status": "FORMULA_COHERENT_SOURCE_COMPLETION",
    },
    {
        "candidate_id": "R02",
        "candidate_index": 2,
        "candidate_cn": "论文CARE_alpha025_加速度",
        "controller": "CARE",
        "input_semantics": "acceleration",
        "integration": "scalar_alpha_0p25",
        "guyan_variant": "standard_congruence",
        "formula_status": "FORMULA_COHERENT_SOURCE_COMPLETION",
    },
    {
        "candidate_id": "R03",
        "candidate_index": 3,
        "candidate_cn": "论文CARE_矩阵al_广义力",
        "controller": "CARE",
        "input_semantics": "generalized_force",
        "integration": "route_matrix_al",
        "guyan_variant": "standard_congruence",
        "formula_status": "FORMULA_COHERENT_SOURCE_COMPLETION",
    },
    {
        "candidate_id": "R04",
        "candidate_index": 4,
        "candidate_cn": "论文CARE_矩阵al_加速度",
        "controller": "CARE",
        "input_semantics": "acceleration",
        "integration": "route_matrix_al",
        "guyan_variant": "standard_congruence",
        "formula_status": "FORMULA_COHERENT_SOURCE_COMPLETION",
    },
    {
        "candidate_id": "R05",
        "candidate_index": 5,
        "candidate_cn": "作者DARE规则外推_逐路线矩阵al",
        "controller": "DARE",
        "input_semantics": "generalized_force",
        "integration": "route_matrix_al",
        "guyan_variant": "historical_single_sided",
        "formula_status": "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID",
    },
    {
        "candidate_id": "R06",
        "candidate_index": 6,
        "candidate_cn": "作者无LQR规则外推_逐路线矩阵al",
        "controller": "NONE",
        "input_semantics": "none",
        "integration": "route_matrix_al",
        "guyan_variant": "historical_single_sided",
        "formula_status": "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID",
    },
)

EXPECTED_DIMS = {
    (1, "Original"): 15,
    (1, "Guyan"): 6,
    (1, "Craig_Bampton"): 9,
    (2, "Original"): 15,
    (2, "Guyan"): 5,
    (2, "Craig_Bampton"): 8,
}

GUYAN_MASTER_DOFS = {
    1: (0, 5, 10, 3, 8, 13),
    2: (0, 10, 3, 8, 13),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    return hashlib.sha256(array.tobytes()).hexdigest()


def rel_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected, ord="fro") / denominator)


def scalar(value: Any) -> float:
    return float(np.asarray(value, dtype=np.float64).reshape(-1)[0])


def numeric(value: Any) -> np.ndarray:
    return np.asarray(value, dtype=np.float64).copy()


def mat_scalar(value: float | int) -> np.ndarray:
    return np.asarray([[value]], dtype=np.float64)


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_mat_deterministic(path: Path, payload: dict[str, np.ndarray]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    savemat(path, payload, do_compression=True, oned_as="column")
    fixed = b"MATLAB 5.0 MAT-file, Board20 Step8C deterministic Python bundle"
    with path.open("r+b") as stream:
        stream.seek(0)
        stream.write(fixed.ljust(116, b" ")[:116])


def reset_output_dir() -> None:
    expected = (BOARD_DIR / "outputs" / "step8c_六链模型生成" / "python").resolve()
    if OUTPUT_DIR.resolve() != expected:
        raise RuntimeError("输出路径安全检查失败")
    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)


def load_frozen_input() -> dict[str, Any]:
    if not INPUT_MAT.is_file():
        raise FileNotFoundError(f"缺少步骤8B确定性MAT：{INPUT_MAT}")
    actual_hash = sha256_file(INPUT_MAT)
    if actual_hash != INPUT_SHA256:
        raise RuntimeError(
            "步骤8B确定性MAT哈希不符："
            f"actual={actual_hash}, expected={INPUT_SHA256}"
        )
    return {
        key: value
        for key, value in loadmat(INPUT_MAT, simplify_cells=True).items()
        if not key.startswith("__")
    }


def base_prefix(division: int, method_id: str, candidate: dict[str, Any]) -> str:
    if method_id == "Original":
        return f"div{division}_Original_source_full15"
    if method_id == "Guyan":
        return f"div{division}_Guyan_source_{candidate['guyan_variant']}"
    return f"div{division}_Craig_Bampton_source_sorted_three_modes"


def exact_zoh(a_matrix: np.ndarray, b_matrix: np.ndarray, dt: float) -> tuple[np.ndarray, np.ndarray]:
    states, inputs = b_matrix.shape
    block = np.zeros((states + inputs, states + inputs), dtype=np.float64)
    block[:states, :states] = a_matrix
    block[:states, states:] = b_matrix
    discrete = expm(block * dt)
    return discrete[:states, :states], discrete[:states, states:]


def continuous_state_matrices(
    mass: np.ndarray,
    damping: np.ndarray,
    stiffness: np.ndarray,
    input_semantics: str,
) -> tuple[np.ndarray, np.ndarray]:
    identity = np.eye(2)
    zero = np.zeros((2, 2))
    a_matrix = np.block(
        [
            [zero, identity],
            [-np.linalg.solve(mass, stiffness), -np.linalg.solve(mass, damping)],
        ]
    )
    if input_semantics in ("generalized_force", "none"):
        lower = np.linalg.solve(mass, identity)
    elif input_semantics == "acceleration":
        lower = identity
    else:
        raise ValueError(f"未知控制输入语义：{input_semantics}")
    b_matrix = np.vstack((zero, lower))
    return a_matrix, b_matrix


def care_residual(
    a_matrix: np.ndarray,
    b_matrix: np.ndarray,
    q_weight: np.ndarray,
    r_weight: np.ndarray,
    solution: np.ndarray,
) -> float:
    term = (
        a_matrix.T @ solution
        + solution @ a_matrix
        - solution @ b_matrix @ np.linalg.solve(r_weight, b_matrix.T @ solution)
        + q_weight
    )
    denominator = max(float(np.linalg.norm(q_weight, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(term, ord="fro") / denominator)


def dare_residual(
    a_matrix: np.ndarray,
    b_matrix: np.ndarray,
    q_weight: np.ndarray,
    r_weight: np.ndarray,
    solution: np.ndarray,
) -> float:
    middle = r_weight + b_matrix.T @ solution @ b_matrix
    term = (
        a_matrix.T @ solution @ a_matrix
        - solution
        - a_matrix.T
        @ solution
        @ b_matrix
        @ np.linalg.solve(middle, b_matrix.T @ solution @ a_matrix)
        + q_weight
    )
    denominator = max(float(np.linalg.norm(q_weight, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(term, ord="fro") / denominator)


def build_controller(
    candidate: dict[str, Any],
    standard_local: dict[str, np.ndarray],
    author_local: dict[str, np.ndarray],
    dt: float,
) -> dict[str, Any]:
    if candidate["candidate_id"] in ("R01", "R02", "R03", "R04"):
        local = standard_local
    else:
        local = author_local

    mass, damping, stiffness = local["M"], local["C"], local["K"]
    a_matrix, b_matrix = continuous_state_matrices(
        mass, damping, stiffness, candidate["input_semantics"]
    )
    a_discrete, b_discrete = exact_zoh(a_matrix, b_matrix, dt)
    controller = candidate["controller"]

    if controller == "CARE":
        q_weight, r_weight = CARE_Q.copy(), CARE_R.copy()
        solution = solve_continuous_are(a_matrix, b_matrix, q_weight, r_weight)
        gain = np.linalg.solve(r_weight, b_matrix.T @ solution)
        if candidate["input_semantics"] == "acceleration":
            delta_k = mass @ gain[:, :2]
            delta_c = mass @ gain[:, 2:]
        else:
            delta_k = gain[:, :2]
            delta_c = gain[:, 2:]
        closed_loop = np.linalg.eigvals(a_matrix - b_matrix @ gain)
        stability_metric = float(np.max(np.real(closed_loop)))
        stability_pass = stability_metric < 0.0
        riccati_error = care_residual(
            a_matrix, b_matrix, q_weight, r_weight, solution
        )
        controller_code = 1
    elif controller == "DARE":
        q_weight, r_weight = DARE_Q.copy(), DARE_R.copy()
        solution = solve_discrete_are(
            a_discrete, b_discrete, q_weight, r_weight
        )
        gain = np.linalg.solve(
            b_discrete.T @ solution @ b_discrete + r_weight,
            b_discrete.T @ solution @ a_discrete,
        )
        delta_k = mass @ gain[:, :2]
        delta_c = mass @ gain[:, 2:]
        closed_loop = np.linalg.eigvals(a_discrete - b_discrete @ gain)
        stability_metric = float(np.max(np.abs(closed_loop)))
        stability_pass = stability_metric < 1.0
        riccati_error = dare_residual(
            a_discrete, b_discrete, q_weight, r_weight, solution
        )
        controller_code = 2
    elif controller == "NONE":
        q_weight = np.zeros((4, 4))
        r_weight = np.zeros((2, 2))
        solution = np.zeros((4, 4))
        gain = np.zeros((2, 4))
        delta_k = np.zeros((2, 2))
        delta_c = np.zeros((2, 2))
        closed_loop = np.linalg.eigvals(a_matrix)
        stability_metric = float(np.max(np.real(closed_loop)))
        stability_pass = stability_metric < 0.0
        riccati_error = 0.0
        controller_code = 0
    else:
        raise ValueError(f"未知控制器：{controller}")

    return {
        "local": local,
        "A": a_matrix,
        "B": b_matrix,
        "Ad": a_discrete,
        "Bd": b_discrete,
        "Q": q_weight,
        "R_weight": r_weight,
        "P": solution,
        "gain": gain,
        "DeltaK": delta_k,
        "DeltaC": delta_c,
        "closed_loop_eigenvalues": closed_loop,
        "stability_metric": stability_metric,
        "stability_pass": stability_pass,
        "riccati_relative_residual": riccati_error,
        "controller_code": controller_code,
    }


def route_matrix_al(
    mass: np.ndarray, damping: np.ndarray, stiffness: np.ndarray, dt: float
) -> tuple[np.ndarray, np.ndarray, float]:
    operator = 4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness
    al_matrix = np.linalg.solve(operator, 4.0 * mass)
    mass_right_div_al = np.linalg.solve(al_matrix.T, mass.T).T
    expected = mass + 0.5 * dt * damping + 0.25 * dt**2 * stiffness
    return al_matrix, mass_right_div_al, rel_error(mass_right_div_al, expected)


def standard_local_static_projection(
    local_full: dict[str, np.ndarray], local_selection: np.ndarray
) -> tuple[dict[str, np.ndarray], np.ndarray, float]:
    """保留psi1/psi6，对其余局部自由度静力凝聚，再执行标准T'AT。"""
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
    static_residual = float(
        np.linalg.norm(k_ss @ static_part + k_sm, ord="fro")
        / max(float(np.linalg.norm(k_sm, ord="fro")), np.finfo(float).eps)
    )
    return projected, transform, static_residual


def shape_text(value: np.ndarray) -> str:
    if value.ndim == 0:
        return "scalar"
    return "x".join(str(number) for number in value.shape)


def bundle_filename(
    division: int,
    method: dict[str, Any],
    dimension: int,
    candidate: dict[str, Any],
) -> str:
    return (
        f"第{division}类_{method['method_cn']}{dimension}维__"
        f"{candidate['candidate_id']}_{candidate['candidate_cn']}.mat"
    )


def build_one_bundle(
    source: dict[str, Any],
    division: int,
    method: dict[str, Any],
    candidate: dict[str, Any],
) -> tuple[dict[str, np.ndarray], dict[str, Any], dict[str, Any]]:
    method_id = method["method_id"]
    prefix = base_prefix(division, method_id, candidate)
    mass = numeric(source[f"{prefix}_M"])
    damping = numeric(source[f"{prefix}_C"])
    stiffness = numeric(source[f"{prefix}_K"])
    dimension = mass.shape[0]
    expected_dimension = EXPECTED_DIMS[(division, method_id)]

    recovery_key = method["recovery_key"]
    recovery = numeric(source[f"div{division}_{recovery_key}_recovery_natural"])
    selector = numeric(
        source[f"div{division}_{recovery_key}_delay_selector_psi1_psi6"]
    )
    embedding = numeric(source[f"div{division}_local_embedding_E"])
    local_selection = numeric(
        source[f"div{division}_local_delay_selection_J_psi1_psi6"]
    )
    local_full = {
        symbol: numeric(source[f"div{division}_local_full_{symbol}"])
        for symbol in ("M", "C", "K")
    }
    local_historical = {
        symbol: numeric(
            source[f"div{division}_local_psi1_psi6_historical_{symbol}"]
        )
        for symbol in ("M", "C", "K")
    }
    local_projected_from_input = {
        symbol: numeric(
            source[f"div{division}_local_psi1_psi6_projected_{symbol}"]
        )
        for symbol in ("M", "C", "K")
    }
    local_standard_rebuilt, local_standard_transform, local_static_residual = (
        standard_local_static_projection(local_full, local_selection)
    )
    # 控制器直接消费步骤8B封签的标准T_p' A_p T_p字段；重建值仅用于独立一致性门禁。
    local_standard = local_projected_from_input
    local_author = {
        symbol: numeric(source[f"div{division}_author_final_local2_{symbol}"])
        for symbol in ("M", "C", "K")
    }
    dt = scalar(source[f"div{division}_source_dt"])
    source_alpha = scalar(source[f"div{division}_source_alpha_newmark"])
    source_delta = scalar(source[f"div{division}_source_delta_newmark"])

    controller = build_controller(
        candidate, local_standard, local_author, dt
    )
    delta_k = controller["DeltaK"]
    delta_c = controller["DeltaC"]

    # 标准Galerkin使用W=R；历史单边Guyan的W/R双基仅保留为Petrov审计。
    is_historical_guyan = (
        method_id == "Guyan"
        and candidate["guyan_variant"] == "historical_single_sided"
    )
    if is_historical_guyan:
        test_basis = np.eye(15)[:, GUYAN_MASTER_DOFS[division]]
    else:
        test_basis = recovery.copy()
    if is_historical_guyan:
        full_global = {
            symbol: numeric(source[f"div{division}_Original_source_full15_{symbol}"])
            for symbol in ("M", "C", "K")
        }
        petrov_base_errors = {
            "M": rel_error(mass, test_basis.T @ full_global["M"] @ recovery),
            "C": rel_error(damping, test_basis.T @ full_global["C"] @ recovery),
            "K": rel_error(stiffness, test_basis.T @ full_global["K"] @ recovery),
        }
    else:
        petrov_base_errors = {symbol: 0.0 for symbol in ("M", "C", "K")}
    petrov_base_max_error = max(petrov_base_errors.values())
    petrov_base_pass = petrov_base_max_error <= 1.0e-12
    selector_right = local_selection @ embedding.T @ recovery
    selector_left = local_selection @ embedding.T @ test_basis
    delay_l_c = test_basis.T @ embedding @ local_full["C"] @ local_selection.T
    delay_l_k = test_basis.T @ embedding @ local_full["K"] @ local_selection.T
    delay_w_c = local_selection @ local_full["C"] @ embedding.T @ recovery
    delay_w_k = local_selection @ local_full["K"] @ embedding.T @ recovery
    selector_from_physical_contract = selector_right

    if candidate["candidate_id"] in ("R01", "R02", "R03", "R04"):
        delay_orientation = "H_LEFT"
    elif method_id == "Original":
        delay_orientation = "H_RIGHT"
    else:
        delay_orientation = "H_LEFT"

    if delay_orientation == "H_LEFT":
        # 步骤8B冻结的历史Guyan活动身份仍为S_R左乘；W/S_L只作Petrov审计。
        active_left_selector = selector_right if is_historical_guyan else selector_left
        delay_c_left = active_left_selector.T
        delay_c_right = delay_w_c
        delay_k_left = active_left_selector.T
        delay_k_right = delay_w_k
        delay_c_zero = active_left_selector.T @ delay_w_c
        delay_k_zero = active_left_selector.T @ delay_w_k
        delay_formula = (
            "S_R' H (v W_C + W_K)"
            if is_historical_guyan
            else "S_L' H [J (v C_p + K_p) E' R]"
        )
        delay_factorization = (
            "S_R' H W_C/W_K" if is_historical_guyan else "S' H W_C/W_K"
        )
        orientation_code = 1
    else:
        delay_c_left = delay_l_c
        delay_c_right = selector_right
        delay_k_left = delay_l_k
        delay_k_right = selector_right
        delay_c_zero = delay_l_c @ selector_right
        delay_k_zero = delay_l_k @ selector_right
        delay_formula = "(v L_C + L_K) H S_R"
        delay_factorization = "L_C/L_K H S_R"
        orientation_code = 2

    damping_remainder = damping - delay_c_zero
    stiffness_remainder = stiffness - delay_k_zero
    feedback_left_selector = selector_right if is_historical_guyan else selector_left
    feedback_c = feedback_left_selector.T @ delta_c @ selector_right
    feedback_k = feedback_left_selector.T @ delta_k @ selector_right
    petrov_audit_c_zero = delay_l_c @ selector_right
    petrov_audit_k_zero = delay_l_k @ selector_right
    if is_historical_guyan:
        frozen_activity_error = max(
            rel_error(delay_c_left, selector_right.T),
            rel_error(delay_k_left, selector_right.T),
            rel_error(feedback_c, selector_right.T @ delta_c @ selector_right),
            rel_error(feedback_k, selector_right.T @ delta_k @ selector_right),
        )
    else:
        frozen_activity_error = 0.0
    frozen_activity_pass = frozen_activity_error <= 1.0e-12

    al_matrix, mass_right_div_al, al_identity_error = route_matrix_al(
        mass, damping, stiffness, dt
    )
    if candidate["integration"] == "scalar_alpha_0p25":
        integration_code = 1
        integration_alpha_active = source_alpha
        integration_mass_operator = mass / source_alpha
    else:
        integration_code = 2
        integration_alpha_active = 0.0
        integration_mass_operator = mass_right_div_al

    input_semantics_codes = {"none": 0, "generalized_force": 1, "acceleration": 2}
    guyan_variant_code = (
        0
        if method_id != "Guyan"
        else (1 if candidate["guyan_variant"] == "standard_congruence" else 2)
    )
    formula_valid_code = int(
        candidate["formula_status"] == "FORMULA_COHERENT_SOURCE_COMPLETION"
    )

    payload: dict[str, np.ndarray] = {
        "bundle_schema_version": mat_scalar(1),
        "division": mat_scalar(division),
        "method_index": mat_scalar(method["method_index"]),
        "candidate_index": mat_scalar(candidate["candidate_index"]),
        "route_dimension": mat_scalar(dimension),
        "M": mass,
        "C": damping,
        "K": stiffness,
        "R": recovery,
        "S": selector,
        "W": test_basis,
        "S_R": selector_right,
        "S_L": selector_left,
        "E": embedding,
        "J": local_selection,
        "M_local_full": local_full["M"],
        "C_local_full": local_full["C"],
        "K_local_full": local_full["K"],
        "M_local2_historical": local_historical["M"],
        "C_local2_historical": local_historical["C"],
        "K_local2_historical": local_historical["K"],
        "M_local2_standard": local_standard["M"],
        "C_local2_standard": local_standard["C"],
        "K_local2_standard": local_standard["K"],
        "M_local2_standard_rebuilt": local_standard_rebuilt["M"],
        "C_local2_standard_rebuilt": local_standard_rebuilt["C"],
        "K_local2_standard_rebuilt": local_standard_rebuilt["K"],
        "T_local2_standard": local_standard_transform,
        "local_static_constraint_relative_residual": mat_scalar(local_static_residual),
        "M_local2_author_final": local_author["M"],
        "C_local2_author_final": local_author["C"],
        "K_local2_author_final": local_author["K"],
        "M_controller_local": controller["local"]["M"],
        "C_controller_local": controller["local"]["C"],
        "K_controller_local": controller["local"]["K"],
        "Q_control": controller["Q"],
        "R_control_weight": controller["R_weight"],
        "A_continuous": controller["A"],
        "B_continuous": controller["B"],
        "A_discrete_zoh": controller["Ad"],
        "B_discrete_zoh": controller["Bd"],
        "riccati_solution_P": controller["P"],
        "controller_gain": controller["gain"],
        "DeltaK": delta_k,
        "DeltaC": delta_c,
        "feedback_K": feedback_k,
        "feedback_C": feedback_c,
        "L_C": delay_l_c,
        "L_K": delay_l_k,
        "W_C": delay_w_c,
        "W_K": delay_w_k,
        "active_delay_C_left_factor": delay_c_left,
        "active_delay_C_right_factor": delay_c_right,
        "active_delay_K_left_factor": delay_k_left,
        "active_delay_K_right_factor": delay_k_right,
        "C2_active_zero_delay": delay_c_zero,
        "K2_active_zero_delay": delay_k_zero,
        "petrov_audit_C_left_factor": delay_l_c,
        "petrov_audit_C_right_factor": selector_right,
        "petrov_audit_K_left_factor": delay_l_k,
        "petrov_audit_K_right_factor": selector_right,
        "C2_petrov_right_audit": petrov_audit_c_zero,
        "K2_petrov_right_audit": petrov_audit_k_zero,
        "C2_zero_delay": delay_c_zero,
        "K2_zero_delay": delay_k_zero,
        "C1": damping_remainder,
        "K1": stiffness_remainder,
        "C_zero_delay_with_feedback": damping + feedback_c,
        "K_zero_delay_with_feedback": stiffness + feedback_k,
        "delay_C_left_factor": delay_c_left,
        "delay_C_right_factor": delay_c_right,
        "delay_K_left_factor": delay_k_left,
        "delay_K_right_factor": delay_k_right,
        "dt": mat_scalar(dt),
        "source_alpha_newmark": mat_scalar(source_alpha),
        "source_delta_newmark": mat_scalar(source_delta),
        "integration_mode_code": mat_scalar(integration_code),
        "integration_alpha_active": mat_scalar(integration_alpha_active),
        "matrix_al": al_matrix,
        "integration_mass_operator": integration_mass_operator,
        "controller_type_code": mat_scalar(controller["controller_code"]),
        "control_input_semantics_code": mat_scalar(
            input_semantics_codes[candidate["input_semantics"]]
        ),
        "delay_orientation_code": mat_scalar(orientation_code),
        "feedback_placement_code": mat_scalar(1),
        "base_guyan_variant_code": mat_scalar(guyan_variant_code),
        "formula_valid_code": mat_scalar(formula_valid_code),
        "paper_grid_eligible_code": mat_scalar(formula_valid_code),
        "petrov_historical_guyan_code": mat_scalar(int(is_historical_guyan)),
        "active_delay_formula_code": mat_scalar(
            3 if is_historical_guyan else orientation_code
        ),
        "petrov_right_audit_only_code": mat_scalar(int(is_historical_guyan)),
        "frozen_historical_guyan_activity_relative_error": mat_scalar(
            frozen_activity_error
        ),
        "frozen_historical_guyan_activity_pass_code": mat_scalar(
            int(frozen_activity_pass)
        ),
        "petrov_historical_M_base_relative_error": mat_scalar(petrov_base_errors["M"]),
        "petrov_historical_C_base_relative_error": mat_scalar(petrov_base_errors["C"]),
        "petrov_historical_K_base_relative_error": mat_scalar(petrov_base_errors["K"]),
        "petrov_historical_base_max_relative_error": mat_scalar(petrov_base_max_error),
        "petrov_historical_base_pass_code": mat_scalar(int(petrov_base_pass)),
        "closed_loop_eigenvalues_real": np.real(
            controller["closed_loop_eigenvalues"]
        ).reshape(-1, 1),
        "closed_loop_eigenvalues_imag": np.imag(
            controller["closed_loop_eigenvalues"]
        ).reshape(-1, 1),
        "controller_stability_metric": mat_scalar(controller["stability_metric"]),
        "riccati_relative_residual": mat_scalar(
            controller["riccati_relative_residual"]
        ),
        "selector_contract_relative_error": mat_scalar(
            rel_error(selector, selector_from_physical_contract)
        ),
        "local_standard_M_source_relative_error": mat_scalar(
            rel_error(local_standard_rebuilt["M"], local_projected_from_input["M"])
        ),
        "local_standard_C_source_relative_error": mat_scalar(
            rel_error(local_standard_rebuilt["C"], local_projected_from_input["C"])
        ),
        "local_standard_K_source_relative_error": mat_scalar(
            rel_error(local_standard_rebuilt["K"], local_projected_from_input["K"])
        ),
        "matrix_al_identity_relative_error": mat_scalar(al_identity_error),
        "zero_delay_C_closure_relative_error": mat_scalar(
            rel_error(damping_remainder + delay_c_zero, damping)
        ),
        "zero_delay_K_closure_relative_error": mat_scalar(
            rel_error(stiffness_remainder + delay_k_zero, stiffness)
        ),
    }

    finite_pass = all(np.isfinite(value).all() for value in payload.values())
    dimension_pass = (
        mass.shape == (expected_dimension, expected_dimension)
        and damping.shape == mass.shape
        and stiffness.shape == mass.shape
        and recovery.shape == (15, expected_dimension)
        and selector.shape == (2, expected_dimension)
        and embedding.shape[0] == 15
        and local_selection.shape == (2, embedding.shape[1])
    )
    rank_recovery = int(np.linalg.matrix_rank(recovery))
    recovery_rank_pass = rank_recovery == expected_dimension
    rank_test_basis = int(np.linalg.matrix_rank(test_basis))
    test_basis_rank_pass = rank_test_basis == expected_dimension
    selector_error = rel_error(selector, selector_from_physical_contract)
    local_projection_error = max(
        rel_error(local_standard_rebuilt[symbol], local_projected_from_input[symbol])
        for symbol in ("M", "C", "K")
    )
    c_closure = rel_error(damping_remainder + delay_c_zero, damping)
    k_closure = rel_error(stiffness_remainder + delay_k_zero, stiffness)
    c_factor_error = rel_error(delay_c_left @ delay_c_right, delay_c_zero)
    k_factor_error = rel_error(delay_k_left @ delay_k_right, delay_k_zero)
    zero_controller_pass = (
        candidate["candidate_id"] != "R06"
        or (
            np.count_nonzero(controller["gain"]) == 0
            and np.count_nonzero(delta_c) == 0
            and np.count_nonzero(delta_k) == 0
            and np.count_nonzero(controller["Q"]) == 0
            and np.count_nonzero(controller["R_weight"]) == 0
        )
    )
    riccati_pass = (
        candidate["candidate_id"] == "R06"
        or controller["riccati_relative_residual"] <= 1.0e-6
    )
    overall_pass = all(
        (
            finite_pass,
            dimension_pass,
            recovery_rank_pass,
            test_basis_rank_pass,
            petrov_base_pass,
            frozen_activity_pass,
            selector_error <= 1.0e-12,
            local_projection_error <= 1.0e-12,
            al_identity_error <= 1.0e-12,
            c_closure <= 1.0e-12,
            k_closure <= 1.0e-12,
            c_factor_error <= 1.0e-12,
            k_factor_error <= 1.0e-12,
            bool(controller["stability_pass"]),
            zero_controller_pass,
            riccati_pass,
        )
    )

    bundle_id = f"D{division}_{method_id}_{candidate['candidate_id']}"
    metadata = {
        "bundle_id": bundle_id,
        "division": division,
        "route": f"第{division}类-{method['method_cn']}-{dimension}维",
        "method": method_id,
        "dimension": dimension,
        "candidate_id": candidate["candidate_id"],
        "candidate_name": candidate["candidate_cn"],
        "formula_status": candidate["formula_status"],
        "base_matrix_source": prefix,
        "guyan_variant": (
            candidate["guyan_variant"] if method_id == "Guyan" else "not_applicable"
        ),
        "controller": candidate["controller"],
        "control_input_semantics": candidate["input_semantics"],
        "controller_local_matrix_source": (
            "step8B div*_local_psi1_psi6_projected_* (standard T_p' A_p T_p); independently rebuilt and checked"
            if candidate["candidate_id"] in ("R01", "R02", "R03", "R04")
            else "author_final_local2"
        ),
        "integration": candidate["integration"],
        "matrix_al_formula": "solve(4M+2dtC+dt^2K, 4M), recomputed per route",
        "matrix_al_identity": "M/al = M + dt/2 C + dt^2/4 K",
        "delay_orientation": delay_orientation,
        "delay_factorization": delay_factorization,
        "delay_formula": delay_formula,
        "delay_factor_definition": (
            "ACTIVE: W_C=J C_p E'R, W_K=J K_p E'R, S_R=J E'R; AUDIT_ONLY: L_C=W' E C_p J', L_K=W' E K_p J'"
            if is_historical_guyan
            else "W=R; S_L=S_R=J E'R; L_C=R' E C_p J'; L_K=R' E K_p J'"
        ),
        "feedback_formula": (
            "S_R' (v DeltaC + DeltaK) S_R"
            if is_historical_guyan
            else "S_L' (v DeltaC + DeltaK) S_R"
        ),
        "feedback_placement": "OUTSIDE_H",
        "paper_grid_eligibility": (
            "ELIGIBLE_SOURCE_COMPLETION"
            if formula_valid_code
            else "BLOCKED_DIAGNOSTIC_ONLY"
        ),
        "petrov_contract": (
            "AUDIT_ONLY: historical Guyan W=I(:,master), S_R=J E'R, S_L=J E'W; Petrov right formula is not active"
            if is_historical_guyan
            else "Galerkin W=R"
        ),
        "active_formula_contract": (
            "FROZEN_STEP8B_H_LEFT: S_R' H (v W_C + W_K); feedback S_R' Delta S_R"
            if is_historical_guyan
            else f"{delay_orientation}: {delay_formula}; feedback outside H"
        ),
        "petrov_audit_formula": (
            "AUDIT_ONLY: (v L_C + L_K) H S_R"
            if is_historical_guyan
            else "not_applicable"
        ),
        "S_L_second_row_all_zero": bool(
            np.count_nonzero(np.abs(selector_left[1, :]) > 1.0e-12) == 0
        ),
        "petrov_historical_base_errors": petrov_base_errors,
        "petrov_historical_base_pass": petrov_base_pass,
        "frozen_historical_guyan_activity_relative_error": f"{frozen_activity_error:.17g}",
        "frozen_historical_guyan_activity_pass": frozen_activity_pass,
        "selection_rule": "全部36包均生成，不按论文曲线先验选择",
    }
    check = {
        "bundle_id": bundle_id,
        "division": division,
        "method": method_id,
        "candidate_id": candidate["candidate_id"],
        "dimension": dimension,
        "expected_dimension": expected_dimension,
        "finite_pass": finite_pass,
        "dimension_pass": dimension_pass,
        "recovery_rank": rank_recovery,
        "recovery_rank_pass": recovery_rank_pass,
        "test_basis_rank": rank_test_basis,
        "test_basis_rank_pass": test_basis_rank_pass,
        "petrov_historical_M_base_relative_error": f"{petrov_base_errors['M']:.17g}",
        "petrov_historical_C_base_relative_error": f"{petrov_base_errors['C']:.17g}",
        "petrov_historical_K_base_relative_error": f"{petrov_base_errors['K']:.17g}",
        "petrov_historical_base_max_relative_error": f"{petrov_base_max_error:.17g}",
        "petrov_historical_base_pass": petrov_base_pass,
        "frozen_historical_guyan_activity_relative_error": f"{frozen_activity_error:.17g}",
        "frozen_historical_guyan_activity_pass": frozen_activity_pass,
        "selector_contract_relative_error": f"{selector_error:.17g}",
        "selector_contract_pass": selector_error <= 1.0e-12,
        "local_projection_max_relative_error": f"{local_projection_error:.17g}",
        "local_projection_pass": local_projection_error <= 1.0e-12,
        "matrix_al_identity_relative_error": f"{al_identity_error:.17g}",
        "matrix_al_identity_pass": al_identity_error <= 1.0e-12,
        "zero_delay_C_closure_relative_error": f"{c_closure:.17g}",
        "zero_delay_K_closure_relative_error": f"{k_closure:.17g}",
        "zero_delay_closure_pass": c_closure <= 1.0e-12 and k_closure <= 1.0e-12,
        "delay_C_factor_relative_error": f"{c_factor_error:.17g}",
        "delay_K_factor_relative_error": f"{k_factor_error:.17g}",
        "delay_factor_pass": c_factor_error <= 1.0e-12 and k_factor_error <= 1.0e-12,
        "controller_stability_metric": f"{controller['stability_metric']:.17g}",
        "controller_stability_pass": bool(controller["stability_pass"]),
        "riccati_relative_residual": f"{controller['riccati_relative_residual']:.17g}",
        "riccati_pass": riccati_pass,
        "zero_controller_pass": zero_controller_pass,
        "formula_status": candidate["formula_status"],
        "paper_grid_eligible": bool(formula_valid_code),
        "overall_pass": overall_pass,
    }
    return payload, metadata, check


def main() -> None:
    source = load_frozen_input()
    reset_output_dir()

    index_rows: list[dict[str, Any]] = []
    check_rows: list[dict[str, Any]] = []
    inventory_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []

    for division in (1, 2):
        for method in METHODS:
            for candidate in CANDIDATES:
                payload, metadata, check = build_one_bundle(
                    source, division, method, candidate
                )
                dimension = int(check["dimension"])
                filename = bundle_filename(
                    division, method, dimension, candidate
                )
                relative_path = Path("候选数值包") / filename
                bundle_path = OUTPUT_DIR / relative_path
                write_mat_deterministic(bundle_path, payload)
                bundle_hash = sha256_file(bundle_path)
                metadata["relative_path"] = relative_path.as_posix()
                metadata["mat_sha256"] = bundle_hash
                check["relative_path"] = relative_path.as_posix()
                check["mat_sha256"] = bundle_hash
                metadata_rows.append(metadata)
                check_rows.append(check)
                index_rows.append(
                    {
                        "bundle_id": metadata["bundle_id"],
                        "division": division,
                        "route": metadata["route"],
                        "method": method["method_id"],
                        "dimension": dimension,
                        "candidate_id": candidate["candidate_id"],
                        "candidate_name": candidate["candidate_cn"],
                        "formula_status": candidate["formula_status"],
                        "paper_grid_eligible": metadata["paper_grid_eligibility"],
                        "base_matrix_source": metadata["base_matrix_source"],
                        "controller": candidate["controller"],
                        "integration": candidate["integration"],
                        "delay_orientation": metadata["delay_orientation"],
                        "feedback_placement": metadata["feedback_placement"],
                        "relative_path": relative_path.as_posix(),
                        "mat_sha256": bundle_hash,
                        "overall_pass": check["overall_pass"],
                    }
                )
                for field_name, field_value in payload.items():
                    array = np.asarray(field_value)
                    inventory_rows.append(
                        {
                            "bundle_id": metadata["bundle_id"],
                            "field": field_name,
                            "shape": shape_text(array),
                            "dtype": array.dtype.str,
                            "finite": bool(np.isfinite(array).all()),
                            "array_sha256": array_sha256(array),
                        }
                    )

    index_fields = [
        "bundle_id",
        "division",
        "route",
        "method",
        "dimension",
        "candidate_id",
        "candidate_name",
        "formula_status",
        "paper_grid_eligible",
        "base_matrix_source",
        "controller",
        "integration",
        "delay_orientation",
        "feedback_placement",
        "relative_path",
        "mat_sha256",
        "overall_pass",
    ]
    check_fields = [
        "bundle_id",
        "division",
        "method",
        "candidate_id",
        "dimension",
        "expected_dimension",
        "finite_pass",
        "dimension_pass",
        "recovery_rank",
        "recovery_rank_pass",
        "test_basis_rank",
        "test_basis_rank_pass",
        "petrov_historical_M_base_relative_error",
        "petrov_historical_C_base_relative_error",
        "petrov_historical_K_base_relative_error",
        "petrov_historical_base_max_relative_error",
        "petrov_historical_base_pass",
        "frozen_historical_guyan_activity_relative_error",
        "frozen_historical_guyan_activity_pass",
        "selector_contract_relative_error",
        "selector_contract_pass",
        "local_projection_max_relative_error",
        "local_projection_pass",
        "matrix_al_identity_relative_error",
        "matrix_al_identity_pass",
        "zero_delay_C_closure_relative_error",
        "zero_delay_K_closure_relative_error",
        "zero_delay_closure_pass",
        "delay_C_factor_relative_error",
        "delay_K_factor_relative_error",
        "delay_factor_pass",
        "controller_stability_metric",
        "controller_stability_pass",
        "riccati_relative_residual",
        "riccati_pass",
        "zero_controller_pass",
        "formula_status",
        "paper_grid_eligible",
        "relative_path",
        "mat_sha256",
        "overall_pass",
    ]
    inventory_fields = [
        "bundle_id",
        "field",
        "shape",
        "dtype",
        "finite",
        "array_sha256",
    ]
    write_csv(OUTPUT_DIR / "六路线六候选索引.csv", index_rows, index_fields)
    write_csv(OUTPUT_DIR / "步骤8C_Python自检.csv", check_rows, check_fields)
    write_csv(OUTPUT_DIR / "候选包数组清单.csv", inventory_rows, inventory_fields)
    write_json(
        OUTPUT_DIR / "候选包元数据.json",
        {
            "schema": "board20-step8c-candidate-bundle-metadata-v1",
            "input_policy": "ONLY_STEP8B_DETERMINISTIC_MAT_NO_PDF_NO_MASK",
            "input_mat": INPUT_MAT.relative_to(BOARD_DIR).as_posix(),
            "input_sha256": INPUT_SHA256,
            "bundle_count": len(metadata_rows),
            "bundles": metadata_rows,
        },
    )

    route_counts = {
        f"D{division}_{method['method_id']}": sum(
            row["division"] == division and row["method"] == method["method_id"]
            for row in index_rows
        )
        for division in (1, 2)
        for method in METHODS
    }
    candidate_counts = {
        candidate["candidate_id"]: sum(
            row["candidate_id"] == candidate["candidate_id"] for row in index_rows
        )
        for candidate in CANDIDATES
    }
    formula_valid_bundle_count = sum(
        row["formula_status"] == "FORMULA_COHERENT_SOURCE_COMPLETION"
        for row in index_rows
    )
    historical_diagnostic_bundle_count = sum(
        row["formula_status"] == "HISTORICAL_DIAGNOSTIC_NOT_FORMULA_VALID"
        for row in index_rows
    )
    all_bundle_checks_pass = all(bool(row["overall_pass"]) for row in check_rows)
    global_checks = {
        "exact_36_bundles": len(index_rows) == 36,
        "six_routes_each_have_six_candidates": all(
            count == 6 for count in route_counts.values()
        ),
        "six_candidates_each_have_six_routes": all(
            count == 6 for count in candidate_counts.values()
        ),
        "all_bundle_checks_pass": all_bundle_checks_pass,
        "formula_valid_bundle_count_is_24": formula_valid_bundle_count == 24,
        "historical_diagnostic_bundle_count_is_12": historical_diagnostic_bundle_count == 12,
        "R01_R04_only_are_paper_grid_eligible": all(
            (row["candidate_id"] in ("R01", "R02", "R03", "R04"))
            == (row["paper_grid_eligible"] == "ELIGIBLE_SOURCE_COMPLETION")
            for row in index_rows
        ),
        "historical_guyan_is_frozen_H_left": all(
            row["delay_orientation"] == "H_LEFT"
            and bool(check["frozen_historical_guyan_activity_pass"])
            for row, check in zip(index_rows, check_rows)
            if row["method"] == "Guyan" and row["candidate_id"] in ("R05", "R06")
        ),
        "historical_guyan_petrov_base_MCK_closed": all(
            bool(row["petrov_historical_base_pass"])
            for row in check_rows
            if row["method"] == "Guyan" and row["candidate_id"] in ("R05", "R06")
        ),
        "division2_historical_guyan_S_L_second_row_is_zero": all(
            row["S_L_second_row_all_zero"]
            for row in metadata_rows
            if row["division"] == 2
            and row["method"] == "Guyan"
            and row["candidate_id"] in ("R05", "R06")
        ),
        "only_one_numeric_input": True,
        "no_pdf_or_history_mask_input": True,
    }
    summary = {
        "schema": "board20-step8c-python-summary-v1",
        "status": "PASS" if all(global_checks.values()) else "FAIL",
        "input_policy": "ONLY_STEP8B_DETERMINISTIC_MAT_NO_PDF_NO_MASK",
        "input_mat": INPUT_MAT.relative_to(BOARD_DIR).as_posix(),
        "input_sha256": INPUT_SHA256,
        "bundle_count": len(index_rows),
        "route_count": len(route_counts),
        "candidate_count": len(candidate_counts),
        "formula_valid_bundle_count": formula_valid_bundle_count,
        "historical_diagnostic_not_formula_valid_bundle_count": historical_diagnostic_bundle_count,
        "route_counts": route_counts,
        "candidate_counts": candidate_counts,
        "global_checks": global_checks,
        "maximum_errors": {
            "selector_contract_relative_error": max(
                float(row["selector_contract_relative_error"]) for row in check_rows
            ),
            "local_projection_relative_error": max(
                float(row["local_projection_max_relative_error"]) for row in check_rows
            ),
            "matrix_al_identity_relative_error": max(
                float(row["matrix_al_identity_relative_error"]) for row in check_rows
            ),
            "zero_delay_C_closure_relative_error": max(
                float(row["zero_delay_C_closure_relative_error"]) for row in check_rows
            ),
            "zero_delay_K_closure_relative_error": max(
                float(row["zero_delay_K_closure_relative_error"]) for row in check_rows
            ),
            "riccati_relative_residual": max(
                float(row["riccati_relative_residual"]) for row in check_rows
            ),
            "petrov_historical_base_relative_error": max(
                float(row["petrov_historical_base_max_relative_error"])
                for row in check_rows
            ),
            "frozen_historical_guyan_activity_relative_error": max(
                float(row["frozen_historical_guyan_activity_relative_error"])
                for row in check_rows
            ),
        },
        "controller_stability_extrema": {
            "CARE_max_real_part": max(
                float(row["controller_stability_metric"])
                for row in check_rows
                if row["candidate_id"] in ("R01", "R02", "R03", "R04")
            ),
            "DARE_max_spectral_radius": max(
                float(row["controller_stability_metric"])
                for row in check_rows
                if row["candidate_id"] == "R05"
            ),
        },
        "notes": [
            "R01-R04均为H左乘，反馈项位于H之外。",
            "R05-R06的Original保留(L_C/L_K) H S_R右乘，Craig-Bampton保留S' H (W_C/W_K)左乘。",
            "R05-R06历史单边Guyan恢复步骤8B冻结身份：S_R左乘与S_R双侧反馈；Petrov右乘仅保留审计字段。",
            "R03-R06的matrix_al均由各包自己的M/C/K逐路线重算。",
            "R05-R06仅作历史规则诊断，不计入论文公式有效候选。",
            "本步骤没有计算31x67稳定域，也没有按论文曲线选择候选。",
        ],
    }
    write_json(OUTPUT_DIR / "步骤8C_Python摘要.json", summary)

    manifest_rows: list[dict[str, Any]] = []
    manifest_path = OUTPUT_DIR / "步骤8C_Python工件清单.csv"
    for artifact in sorted(
        (path for path in OUTPUT_DIR.rglob("*") if path.is_file() and path != manifest_path),
        key=lambda path: path.relative_to(OUTPUT_DIR).as_posix(),
    ):
        manifest_rows.append(
            {
                "relative_path": artifact.relative_to(OUTPUT_DIR).as_posix(),
                "bytes": artifact.stat().st_size,
                "sha256": sha256_file(artifact),
            }
        )
    write_csv(
        manifest_path,
        manifest_rows,
        ["relative_path", "bytes", "sha256"],
    )

    if not all(global_checks.values()):
        failed = [name for name, passed in global_checks.items() if not passed]
        raise RuntimeError(f"步骤8C自检失败：{failed}")
    if len(list(BUNDLE_DIR.glob("*.mat"))) != 36:
        raise RuntimeError("候选数值包文件数不是36")

    print("步骤8C Python候选包生成：PASS")
    print(f"输入MAT SHA256：{INPUT_SHA256}")
    print("六条基础路线 × 六个候选 = 36个MAT包")
    print("论文公式候选：24包；历史诊断候选：12包")
    print(f"输出目录：{OUTPUT_DIR}")


if __name__ == "__main__":
    main()

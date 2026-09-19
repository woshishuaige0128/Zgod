#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块20最小步骤8D：Python 独立的单点广义特征值求解分支。

边界：
1. 只读取步骤8C的 Python 候选数值包和索引；
2. 只接受 R01--R04 且 paper_grid_eligible=1 的包；
3. R05/R06 在 scipy.io.loadmat 之前拒绝；
4. 只计算预先写死的 P00--P12，不扫描全网格，不根据结果更改试点；
5. 不导入任何仓库内的 MATLAB/Python 生成器或求解器代码。

主求解路线：利用两个时滞通道的共享左向量，把延迟力写成两个标量序列的
移位寄存器，建立阶数严格为 2*n+l+j 的最小增广广义特征值铅笔。该铅笔的
全部根即全部物理根；不用经验阈值从高重数原点簇中猜测根身份。清幂大伴随 QZ
只作原始诊断。每个物理特征对同时通过状态铅笔、Laurent原式和清幂多项式
回代，三类相对残差均不得超过 1e-8。
"""

from __future__ import annotations

import os

# 在导入 NumPy/SciPy 前冻结线程数，避免并行 BLAS 造成非确定顺序。
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import argparse
import csv
import hashlib
import io
import json
import math
import platform
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import scipy
from scipy.io import loadmat, savemat
from scipy.linalg import eig, solve


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parent.parent
INPUT_ROOT = BOARD_ROOT / "outputs" / "step8c_六链模型生成" / "python"
INDEX_PATH = INPUT_ROOT / "六路线六候选索引.csv"
BUNDLE_ROOT = INPUT_ROOT / "候选数值包"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step8d_单点双求解器门禁" / "python"

POINT_CSV = OUTPUT_ROOT / "步骤8D_Python试点逐点结果.csv"
REJECTION_CSV = OUTPUT_ROOT / "步骤8D_Python诊断候选拒绝.csv"
NPZ_PATH = OUTPUT_ROOT / "步骤8D_Python试点全部根.npz"
MAT_PATH = OUTPUT_ROOT / "步骤8D_Python试点全部根.mat"
JSON_PATH = OUTPUT_ROOT / "步骤8D_Python试点摘要.json"
REPORT_PATH = OUTPUT_ROOT / "步骤8D_Python单点门禁报告.md"
MANIFEST_PATH = OUTPUT_ROOT / "步骤8D_Python工件确定性清单.csv"

ELIGIBLE_CANDIDATES = ("R01", "R02", "R03", "R04")
REJECTED_CANDIDATES = ("R05", "R06")
ELIGIBLE_TEXT = "ELIGIBLE_SOURCE_COMPLETION"
ELIGIBLE_FORMULA_TEXT = "FORMULA_COHERENT_SOURCE_COMPLETION"
RESIDUAL_LIMIT = 1.0e-8
CRITICAL_TOLERANCE = 1.0e-8

# 试点是双求解器门禁的外部合同：不允许命令行覆盖，不允许按结果增删。
FROZEN_POINTS: tuple[tuple[str, int, int], ...] = (
    ("P00", 0, 0),
    ("P01", 1, 0),
    ("P02", 0, 1),
    ("P03", 3, 7),
    ("P04", 10, 20),
    ("P05", 15, 33),
    ("P06", 30, 66),
    ("P07", 1, 48),
    ("P08", 1, 51),
    ("P09", 1, 57),
    ("P10", 1, 58),
    ("P11", 1, 59),
    ("P12", 1, 64),
)

EXPECTED_ROUTE_KEYS = (
    (1, "Original", 15),
    (1, "Guyan", 6),
    (1, "Craig_Bampton", 9),
    (2, "Original", 15),
    (2, "Guyan", 5),
    (2, "Craig_Bampton", 8),
)

POINT_FIELDNAMES = (
    "point_row",
    "point_id",
    "l_samples",
    "j_samples",
    "bundle_id",
    "division",
    "route",
    "method",
    "dimension",
    "candidate_id",
    "candidate_name",
    "paper_grid_eligible",
    "formula_status",
    "source_mat_sha256",
    "laurent_min_exponent",
    "laurent_max_exponent",
    "clearing_power",
    "polynomial_degree",
    "pencil_order",
    "raw_root_count",
    "finite_raw_root_count",
    "infinite_raw_root_count",
    "nan_raw_root_count",
    "removed_origin_root_count",
    "structural_origin_multiplicity",
    "expected_physical_root_count",
    "physical_root_count",
    "retained_root_count",
    "minimum_physical_root_magnitude",
    "shared_left_factor_relative_error",
    "delay_channel_1_register_scale",
    "delay_channel_2_register_scale",
    "transition_reconstruction_relative_error",
    "rho",
    "dominant_root_real",
    "dominant_root_imag",
    "maximum_state_eigenpair_residual",
    "maximum_laurent_relative_residual",
    "maximum_polynomial_relative_residual",
    "max_relative_residual",
    "stable",
    "critical",
    "overall_pass",
)


class ContractError(RuntimeError):
    """输入、数值或输出合同不满足。"""


class CandidateRejected(ContractError):
    """候选路线在读取 MAT 前被资格门禁拒绝。"""


@dataclass(frozen=True)
class Bundle:
    """资格通过后的步骤8C数值包。"""

    row: Mapping[str, str]
    path: Path
    source_sha256: str
    dimension: int
    dt: float
    integration_mass_operator: np.ndarray
    c1: np.ndarray
    k1: np.ndarray
    delay_c_left: np.ndarray
    delay_c_right: np.ndarray
    delay_k_left: np.ndarray
    delay_k_right: np.ndarray
    feedback_c: np.ndarray
    feedback_k: np.ndarray


@dataclass(frozen=True)
class PointSolve:
    """一个候选包在一个固定试点上的结构性全物理根结果。"""

    row: Mapping[str, Any]
    full_companion_roots: np.ndarray
    full_companion_root_class: np.ndarray
    full_companion_alpha: np.ndarray
    full_companion_beta: np.ndarray
    physical_roots: np.ndarray
    physical_alpha: np.ndarray
    physical_beta: np.ndarray
    minimal_qz_diagnostic_roots: np.ndarray
    minimal_qz_diagnostic_alpha: np.ndarray
    minimal_qz_diagnostic_beta: np.ndarray
    state_eigenpair_residuals: np.ndarray
    laurent_residuals: np.ndarray
    polynomial_residuals: np.ndarray


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def scalar_float(value: Any, name: str) -> float:
    array = np.asarray(value)
    require(array.size == 1, f"{name} 必须是标量，实际 shape={array.shape}")
    result = float(array.reshape(-1)[0])
    require(math.isfinite(result), f"{name} 必须是有限数")
    return result


def matrix_float(value: Any, name: str, shape: tuple[int, int]) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    require(result.shape == shape, f"{name} shape={result.shape}，预期 {shape}")
    require(np.all(np.isfinite(result)), f"{name} 包含非有限数")
    return np.ascontiguousarray(result)


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected, ord="fro") / denominator)


def read_index() -> list[dict[str, str]]:
    require(INDEX_PATH.is_file(), f"缺少步骤8C索引：{INDEX_PATH}")
    with INDEX_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))

    require(len(rows) == 36, f"步骤8C索引必须有36行，实际 {len(rows)}")
    require(len({row["bundle_id"] for row in rows}) == 36, "bundle_id 不唯一")

    actual_candidates = {row["candidate_id"] for row in rows}
    require(
        actual_candidates == set(ELIGIBLE_CANDIDATES + REJECTED_CANDIDATES),
        f"候选集错误：{sorted(actual_candidates)}",
    )
    actual_routes = {
        (int(row["division"]), row["method"], int(row["dimension"])) for row in rows
    }
    require(actual_routes == set(EXPECTED_ROUTE_KEYS), f"六路线身份错误：{actual_routes}")

    for route_key in EXPECTED_ROUTE_KEYS:
        route_rows = [
            row
            for row in rows
            if (int(row["division"]), row["method"], int(row["dimension"])) == route_key
        ]
        require(len(route_rows) == 6, f"路线 {route_key} 不是6个候选")
        require(
            {row["candidate_id"] for row in route_rows}
            == set(ELIGIBLE_CANDIDATES + REJECTED_CANDIDATES),
            f"路线 {route_key} 候选身份不完整",
        )
    return rows


def route_sort_key(row: Mapping[str, str]) -> tuple[int, int, int]:
    method_order = {"Original": 0, "Guyan": 1, "Craig_Bampton": 2}
    return (
        int(row["division"]),
        method_order[row["method"]],
        int(row["candidate_id"][1:]),
    )


def guard_candidate_before_load(row: Mapping[str, str]) -> None:
    """MAT 读取前的硬门禁：诊断候选不进入数值求解器。"""

    candidate_id = row["candidate_id"]
    if candidate_id not in ELIGIBLE_CANDIDATES:
        raise CandidateRejected(
            f"{row['bundle_id']} 的 {candidate_id} 不在 R01--R04 公式一致候选集"
        )
    if row["paper_grid_eligible"] != ELIGIBLE_TEXT:
        raise CandidateRejected(
            f"{row['bundle_id']} paper_grid_eligible={row['paper_grid_eligible']}"
        )
    if row["formula_status"] != ELIGIBLE_FORMULA_TEXT:
        raise CandidateRejected(
            f"{row['bundle_id']} formula_status={row['formula_status']}"
        )


def load_eligible_bundle(row: Mapping[str, str]) -> Bundle:
    """只在 guard_candidate_before_load 通过后调用 loadmat。"""

    guard_candidate_before_load(row)
    path = INPUT_ROOT / row["relative_path"]
    require(path.is_file(), f"候选数值包不存在：{path}")
    source_sha = sha256_file(path)
    require(source_sha == row["mat_sha256"], f"{row['bundle_id']} MAT SHA-256 与索引不符")

    data = loadmat(path, squeeze_me=True, struct_as_record=False)
    n = int(row["dimension"])
    require(int(round(scalar_float(data["candidate_index"], "candidate_index"))) == int(row["candidate_id"][1:]),
            f"{row['bundle_id']} candidate_index 不符")
    require(int(round(scalar_float(data["division"], "division"))) == int(row["division"]),
            f"{row['bundle_id']} division 不符")
    require(int(round(scalar_float(data["route_dimension"], "route_dimension"))) == n,
            f"{row['bundle_id']} route_dimension 不符")
    require(scalar_float(data["formula_valid_code"], "formula_valid_code") == 1.0,
            f"{row['bundle_id']} formula_valid_code 不是1")
    require(scalar_float(data["paper_grid_eligible_code"], "paper_grid_eligible_code") == 1.0,
            f"{row['bundle_id']} paper_grid_eligible_code 不是1")
    require(scalar_float(data["feedback_placement_code"], "feedback_placement_code") == 1.0,
            f"{row['bundle_id']} 反馈必须位于 H 外")

    dt = scalar_float(data["dt"], "dt")
    require(dt > 0.0, f"{row['bundle_id']} dt 必须大于0")
    c1 = matrix_float(data["C1"], "C1", (n, n))
    k1 = matrix_float(data["K1"], "K1", (n, n))
    delay_c_left = matrix_float(data["delay_C_left_factor"], "delay_C_left_factor", (n, 2))
    delay_c_right = matrix_float(data["delay_C_right_factor"], "delay_C_right_factor", (2, n))
    delay_k_left = matrix_float(data["delay_K_left_factor"], "delay_K_left_factor", (n, 2))
    delay_k_right = matrix_float(data["delay_K_right_factor"], "delay_K_right_factor", (2, n))
    feedback_c = matrix_float(data["feedback_C"], "feedback_C", (n, n))
    feedback_k = matrix_float(data["feedback_K"], "feedback_K", (n, n))
    mass_operator = matrix_float(
        data["integration_mass_operator"], "integration_mass_operator", (n, n)
    )

    # 求解前独立检查低秩分解和零时滞闭合，避免把包中的预计算 C2/K2 盲信为求解依据。
    c2_rebuilt = delay_c_left @ delay_c_right
    k2_rebuilt = delay_k_left @ delay_k_right
    c2_stored = matrix_float(data["C2_zero_delay"], "C2_zero_delay", (n, n))
    k2_stored = matrix_float(data["K2_zero_delay"], "K2_zero_delay", (n, n))
    require(relative_error(c2_rebuilt, c2_stored) <= 1.0e-12,
            f"{row['bundle_id']} 时滞阻尼低秩分解不闭合")
    require(relative_error(k2_rebuilt, k2_stored) <= 1.0e-12,
            f"{row['bundle_id']} 时滞刚度低秩分解不闭合")
    full_c = matrix_float(data["C"], "C", (n, n))
    full_k = matrix_float(data["K"], "K", (n, n))
    require(relative_error(c1 + c2_rebuilt, full_c) <= 1.0e-12,
            f"{row['bundle_id']} C1+C2 零时滞不闭合")
    require(relative_error(k1 + k2_rebuilt, full_k) <= 1.0e-12,
            f"{row['bundle_id']} K1+K2 零时滞不闭合")

    return Bundle(
        row=dict(row),
        path=path,
        source_sha256=source_sha,
        dimension=n,
        dt=dt,
        integration_mass_operator=mass_operator,
        c1=c1,
        k1=k1,
        delay_c_left=delay_c_left,
        delay_c_right=delay_c_right,
        delay_k_left=delay_k_left,
        delay_k_right=delay_k_right,
        feedback_c=feedback_c,
        feedback_k=feedback_k,
    )


def add_laurent_coefficient(
    coefficients: dict[int, np.ndarray], exponent: int, value: np.ndarray
) -> None:
    """同幂次项必须相加，不得覆盖，包括 l=j 和 l/j=0 的情况。"""

    if exponent in coefficients:
        coefficients[exponent] = coefficients[exponent] + value
    else:
        coefficients[exponent] = np.array(value, dtype=np.float64, copy=True)


def build_polynomial(
    bundle: Bundle, l_samples: int, j_samples: int
) -> tuple[list[np.ndarray], int, int, int, dict[int, np.ndarray]]:
    require(isinstance(l_samples, int) and l_samples >= 0, "l 必须是非负整数采样时滞")
    require(isinstance(j_samples, int) and j_samples >= 0, "j 必须是非负整数采样时滞")
    n = bundle.dimension
    dt = bundle.dt
    coefficients: dict[int, np.ndarray] = {}

    mass_term = bundle.integration_mass_operator / (dt * dt)
    add_laurent_coefficient(coefficients, 1, mass_term)
    add_laurent_coefficient(
        coefficients,
        0,
        -2.0 * mass_term + bundle.c1 / dt + bundle.k1,
    )
    add_laurent_coefficient(
        coefficients,
        -1,
        mass_term - bundle.c1 / dt,
    )

    for channel, delay in enumerate((l_samples, j_samples)):
        damping_channel = np.outer(
            bundle.delay_c_left[:, channel], bundle.delay_c_right[channel, :]
        )
        stiffness_channel = np.outer(
            bundle.delay_k_left[:, channel], bundle.delay_k_right[channel, :]
        )
        add_laurent_coefficient(
            coefficients,
            -delay,
            damping_channel / dt + stiffness_channel,
        )
        add_laurent_coefficient(
            coefficients,
            -(delay + 1),
            -damping_channel / dt,
        )

    # 候选包合同规定控制反馈在 H 之外，因而只位于 0/-1 幂次。
    add_laurent_coefficient(
        coefficients,
        0,
        bundle.feedback_c / dt + bundle.feedback_k,
    )
    add_laurent_coefficient(
        coefficients,
        -1,
        -bundle.feedback_c / dt,
    )

    nonzero_exponents = sorted(
        exponent for exponent, value in coefficients.items() if np.any(value != 0.0)
    )
    require(nonzero_exponents, f"{bundle.row['bundle_id']} Laurent 系数全为零")
    minimum_exponent = nonzero_exponents[0]
    maximum_exponent = nonzero_exponents[-1]
    require(maximum_exponent == 1, f"Laurent 最高幂次应为1，实际 {maximum_exponent}")
    clearing_power = max(0, -minimum_exponent)
    degree = maximum_exponent + clearing_power
    require(degree >= 1, "清幂后矩阵多项式不得为常数")

    polynomial = [np.zeros((n, n), dtype=np.float64) for _ in range(degree + 1)]
    for exponent, value in coefficients.items():
        location = exponent + clearing_power
        require(0 <= location <= degree, f"幂次 {exponent} 清幂后越界")
        polynomial[location] += value

    require(np.any(polynomial[-1] != 0.0), "矩阵多项式首项不得为零")
    require(np.all(np.isfinite(np.stack(polynomial))), "矩阵多项式系数包含非有限数")
    ordered_laurent = {
        exponent: np.array(coefficients[exponent], dtype=np.float64, copy=True)
        for exponent in sorted(coefficients)
        if np.any(coefficients[exponent] != 0.0)
    }
    return polynomial, minimum_exponent, maximum_exponent, clearing_power, ordered_laurent


def solve_full_companion_diagnostic(
    polynomial: Sequence[np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """返回未做任何经验原点分类的大伴随 QZ 原始诊断。"""

    degree = len(polynomial) - 1
    n = polynomial[0].shape[0]
    coefficient_scale = max(float(np.linalg.norm(value, ord="fro")) for value in polynomial)
    require(math.isfinite(coefficient_scale) and coefficient_scale > 0.0,
            "大伴随系数缩放量非法")
    scaled = [value / coefficient_scale for value in polynomial]
    order = n * degree
    pencil_a = np.zeros((order, order), dtype=np.float64, order="F")
    pencil_b = np.zeros((order, order), dtype=np.float64, order="F")
    for block in range(degree):
        pencil_a[:n, block * n : (block + 1) * n] = -scaled[degree - block - 1]
    pencil_b[:n, :n] = scaled[degree]
    if degree > 1:
        identity = np.eye(n * (degree - 1), dtype=np.float64)
        pencil_a[n:, : n * (degree - 1)] = identity
        pencil_b[n:, n:] = identity

    homogeneous = eig(
        pencil_a,
        pencil_b,
        left=False,
        right=False,
        overwrite_a=True,
        overwrite_b=True,
        check_finite=False,
        homogeneous_eigvals=True,
    )
    alpha = homogeneous[0, :]
    beta = homogeneous[1, :]
    roots = np.full(alpha.shape, complex(np.nan, np.nan), dtype=np.complex128)
    beta_nonzero = beta != 0.0
    roots[beta_nonzero] = alpha[beta_nonzero] / beta[beta_nonzero]
    roots[(~beta_nonzero) & (alpha != 0.0)] = complex(np.inf, 0.0)
    nan_mask = np.isnan(roots.real) | np.isnan(roots.imag)
    finite_mask = np.isfinite(roots.real) & np.isfinite(roots.imag)
    infinite_mask = ~finite_mask & ~nan_mask
    require(not np.any(nan_mask), "大伴随 QZ 原始诊断返回NaN根")
    require(not np.any(infinite_mask), "大伴随首项应满秩，但QZ返回无穷根")

    root_class = np.zeros(roots.shape, dtype=np.int8)
    root_class[infinite_mask] = 2
    root_class[nan_mask] = 3
    magnitude_key = np.where(finite_mask, np.abs(roots), np.inf)
    real_key = np.where(finite_mask, roots.real, np.inf)
    imag_key = np.where(finite_mask, roots.imag, np.inf)
    order_index = np.lexsort((imag_key, real_key, magnitude_key, root_class))
    return roots[order_index], root_class[order_index], alpha[order_index], beta[order_index]


def build_minimal_augmented_pencil(
    bundle: Bundle, l_samples: int, j_samples: int
) -> tuple[np.ndarray, np.ndarray, float, np.ndarray]:
    """建立阶数严格为 2*n+l+j 的两通道缩放标量移位寄存器铅笔。"""

    n = bundle.dimension
    dt = bundle.dt
    delays = (l_samples, j_samples)
    state_order = 2 * n + l_samples + j_samples
    current = np.zeros((state_order, state_order), dtype=np.float64)
    following = np.zeros((state_order, state_order), dtype=np.float64)

    mass_term = bundle.integration_mass_operator / (dt * dt)
    base_zero = (
        -2.0 * mass_term
        + bundle.c1 / dt
        + bundle.k1
        + bundle.feedback_c / dt
        + bundle.feedback_k
    )
    base_minus_one = mass_term - bundle.c1 / dt - bundle.feedback_c / dt
    following[:n, :n] = mass_term
    current[:n, :n] = -base_zero
    current[:n, n : 2 * n] = -base_minus_one
    current[n : 2 * n, :n] = np.eye(n)
    following[n : 2 * n, n : 2 * n] = np.eye(n)

    offset = 2 * n
    maximum_factor_error = 0.0
    register_scales = np.empty(2, dtype=np.float64)
    for channel, delay in enumerate(delays):
        c_left = bundle.delay_c_left[:, channel]
        k_left = bundle.delay_k_left[:, channel]
        factor_denominator = max(
            float(np.linalg.norm(c_left, 2)),
            float(np.linalg.norm(k_left, 2)),
            np.finfo(float).eps,
        )
        factor_error = float(np.linalg.norm(c_left - k_left, 2) / factor_denominator)
        maximum_factor_error = max(maximum_factor_error, factor_error)
        require(
            factor_error <= 1.0e-12,
            f"通道{channel + 1}的阻尼/刚度时滞项未共享同一左向量：{factor_error:.17g}",
        )
        u_vector = c_left
        v_zero = bundle.delay_c_right[channel, :] / dt + bundle.delay_k_right[channel, :]
        v_minus_one = -bundle.delay_c_right[channel, :] / dt
        register_scale = max(
            float(np.linalg.norm(v_zero, 2)),
            float(np.linalg.norm(v_minus_one, 2)),
            np.finfo(float).eps,
        )
        register_scales[channel] = register_scale

        if delay == 0:
            current[:n, :n] -= np.outer(u_vector, v_zero)
            current[:n, n : 2 * n] -= np.outer(u_vector, v_minus_one)
            continue

        # q=s/register_scale 是 s 的固定量纲缩放；延迟力仍严格为
        # u*s=u*register_scale*q。缩放只改善特征向量的数值条件，不改根。
        current[:n, offset + delay - 1] -= u_vector * register_scale
        current[offset, :n] = v_zero / register_scale
        current[offset, n : 2 * n] = v_minus_one / register_scale
        following[offset, offset] = 1.0
        for register in range(1, delay):
            current[offset + register, offset + register - 1] = 1.0
            following[offset + register, offset + register] = 1.0
        offset += delay

    require(offset == state_order, f"最小增广阶数索引 {offset} 与 {state_order} 不符")
    require(np.linalg.matrix_rank(following) == state_order, "最小增广铅笔的下一时刻矩阵不满秩")
    require(np.all(np.isfinite(register_scales)) and np.all(register_scales > 0.0),
            "标量寄存器量纲缩放非法")
    return current, following, maximum_factor_error, register_scales


def polynomial_eigenpair_residuals(
    polynomial: Sequence[np.ndarray], roots: np.ndarray, physical_vectors: np.ndarray
) -> np.ndarray:
    degree = len(polynomial) - 1
    values = polynomial[degree] @ physical_vectors
    denominator = np.full(
        roots.shape, float(np.linalg.norm(polynomial[degree], ord="fro")), dtype=np.float64
    )
    for exponent in range(degree - 1, -1, -1):
        values = values * roots[np.newaxis, :] + polynomial[exponent] @ physical_vectors
        denominator = (
            np.abs(roots) * denominator
            + float(np.linalg.norm(polynomial[exponent], ord="fro"))
        )
    return np.linalg.norm(values, axis=0) / denominator


def laurent_eigenpair_residuals(
    coefficients: Mapping[int, np.ndarray],
    roots: np.ndarray,
    physical_vectors: np.ndarray,
) -> np.ndarray:
    exponents = np.asarray(sorted(coefficients), dtype=np.int64)
    coefficient_norms = np.asarray(
        [np.linalg.norm(coefficients[int(exponent)], ord="fro") for exponent in exponents],
        dtype=np.float64,
    )
    residuals = np.empty(roots.size, dtype=np.float64)
    for column, root in enumerate(roots):
        magnitude = abs(root)
        require(math.isfinite(magnitude) and magnitude > 0.0,
                "最小增广物理根必须是有限非零根")
        log_weights = exponents.astype(np.float64) * math.log(magnitude)
        maximum_log_weight = float(np.max(log_weights))
        scaled_magnitudes = np.exp(log_weights - maximum_log_weight)
        phases = np.exp(1j * exponents.astype(np.float64) * np.angle(root))
        factors = scaled_magnitudes * phases
        value = np.zeros(physical_vectors.shape[0], dtype=np.complex128)
        for index, exponent in enumerate(exponents):
            value += factors[index] * (
                coefficients[int(exponent)] @ physical_vectors[:, column]
            )
        denominator = float(np.sum(scaled_magnitudes * coefficient_norms))
        require(denominator > 0.0 and math.isfinite(denominator), "Laurent残差分母非法")
        residuals[column] = float(np.linalg.norm(value, 2) / denominator)
    return residuals


def solve_minimal_augmented(
    bundle: Bundle,
    l_samples: int,
    j_samples: int,
    polynomial: Sequence[np.ndarray],
    laurent_coefficients: Mapping[int, np.ndarray],
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
    np.ndarray,
    float,
]:
    current, following, factor_error, register_scales = build_minimal_augmented_pencil(
        bundle, l_samples, j_samples
    )
    expected_order = 2 * bundle.dimension + l_samples + j_samples
    require(current.shape == (expected_order, expected_order), "最小增广阶数不符")
    transition = solve(
        following,
        current,
        assume_a="gen",
        overwrite_a=False,
        overwrite_b=False,
        check_finite=False,
    )
    transition_reconstruction_error = relative_error(
        following @ transition, current
    )
    require(
        transition_reconstruction_error <= 1.0e-12,
        f"标准转移矩阵重构误差 {transition_reconstruction_error:.17g} 超过1e-12",
    )
    homogeneous, eigenvectors = eig(
        transition,
        left=False,
        right=True,
        overwrite_a=False,
        check_finite=False,
        homogeneous_eigvals=True,
    )
    alpha = homogeneous[0, :]
    beta = homogeneous[1, :]
    require(np.all(beta != 0.0), "最小增广铅笔返回无穷物理根")
    roots = alpha / beta
    require(roots.size == expected_order, "最小增广物理根数与阶数不符")
    require(np.all(np.isfinite(roots.real)) and np.all(np.isfinite(roots.imag)),
            "最小增广物理根包含非有限值")
    order_index = np.lexsort((roots.imag, roots.real, np.abs(roots)))
    roots = roots[order_index]
    alpha = alpha[order_index]
    beta = beta[order_index]
    eigenvectors = eigenvectors[:, order_index]

    # 原广义 QZ 只保留为最小增广铅笔的独立诊断，不参与主根、rho 或分类。
    qz_homogeneous = eig(
        current,
        following,
        left=False,
        right=False,
        overwrite_a=False,
        overwrite_b=False,
        check_finite=False,
        homogeneous_eigvals=True,
    )
    qz_alpha = qz_homogeneous[0, :]
    qz_beta = qz_homogeneous[1, :]
    qz_roots = np.full(qz_alpha.shape, complex(np.nan, np.nan), dtype=np.complex128)
    qz_beta_nonzero = qz_beta != 0.0
    qz_roots[qz_beta_nonzero] = qz_alpha[qz_beta_nonzero] / qz_beta[qz_beta_nonzero]
    qz_roots[(~qz_beta_nonzero) & (qz_alpha != 0.0)] = complex(np.inf, 0.0)
    qz_finite = np.isfinite(qz_roots.real) & np.isfinite(qz_roots.imag)
    qz_nan = np.isnan(qz_roots.real) | np.isnan(qz_roots.imag)
    qz_class = np.zeros(qz_roots.shape, dtype=np.int8)
    qz_class[~qz_finite & ~qz_nan] = 2
    qz_class[qz_nan] = 3
    qz_magnitude_key = np.where(qz_finite, np.abs(qz_roots), np.inf)
    qz_real_key = np.where(qz_finite, qz_roots.real, np.inf)
    qz_imag_key = np.where(qz_finite, qz_roots.imag, np.inf)
    qz_order = np.lexsort((qz_imag_key, qz_real_key, qz_magnitude_key, qz_class))
    qz_roots = qz_roots[qz_order]
    qz_alpha = qz_alpha[qz_order]
    qz_beta = qz_beta[qz_order]

    vector_norms = np.linalg.norm(eigenvectors, axis=0)
    require(np.all(np.isfinite(vector_norms)) and np.all(vector_norms > 0.0),
            "最小增广状态特征向量非法")
    state_values = current @ eigenvectors - (following @ eigenvectors) * roots[np.newaxis, :]
    state_denominator = (
        float(np.linalg.norm(current, ord="fro"))
        + np.abs(roots) * float(np.linalg.norm(following, ord="fro"))
    ) * vector_norms
    state_residuals = np.linalg.norm(state_values, axis=0) / state_denominator

    physical_vectors = np.array(
        eigenvectors[: bundle.dimension, :], dtype=np.complex128, copy=True
    )
    physical_norms = np.linalg.norm(physical_vectors, axis=0)
    require(np.all(np.isfinite(physical_norms)) and np.all(physical_norms > 0.0),
            "最小增广状态的前n维物理向量非法")
    physical_vectors /= physical_norms[np.newaxis, :]
    polynomial_residuals = polynomial_eigenpair_residuals(
        polynomial, roots, physical_vectors
    )
    laurent_residuals = laurent_eigenpair_residuals(
        laurent_coefficients, roots, physical_vectors
    )
    for label, values in (
        ("状态铅笔", state_residuals),
        ("Laurent原式", laurent_residuals),
        ("清幂多项式", polynomial_residuals),
    ):
        require(np.all(np.isfinite(values)), f"{label}残差包含非有限数")
        maximum = float(np.max(values))
        require(maximum <= RESIDUAL_LIMIT,
                f"{label}最大残差 {maximum:.17g} 超过 {RESIDUAL_LIMIT:.1e}")
    return (
        roots,
        alpha,
        beta,
        state_residuals,
        laurent_residuals,
        polynomial_residuals,
        qz_roots,
        qz_alpha,
        qz_beta,
        factor_error,
        register_scales,
        transition_reconstruction_error,
    )


def solve_bundle_point(
    bundle: Bundle, point_row: int, point_id: str, l_samples: int, j_samples: int
) -> PointSolve:
    (
        polynomial,
        minimum_exponent,
        maximum_exponent,
        clearing_power,
        laurent_coefficients,
    ) = build_polynomial(bundle, l_samples, j_samples)
    degree = len(polynomial) - 1
    raw_roots, raw_class, raw_alpha, raw_beta = solve_full_companion_diagnostic(polynomial)
    (
        physical_roots,
        physical_alpha,
        physical_beta,
        state_residuals,
        laurent_residuals,
        polynomial_residuals,
        minimal_qz_roots,
        minimal_qz_alpha,
        minimal_qz_beta,
        factor_error,
        register_scales,
        transition_reconstruction_error,
    ) = solve_minimal_augmented(
        bundle, l_samples, j_samples, polynomial, laurent_coefficients
    )

    expected_physical_count = 2 * bundle.dimension + l_samples + j_samples
    require(physical_roots.size == expected_physical_count, "物理根数与2n+l+j不符")
    structural_origin_multiplicity = int(raw_roots.size - physical_roots.size)
    require(structural_origin_multiplicity >= 0, "结构性原点重数为负")
    expected_structural_origin = (
        bundle.dimension * (max(l_samples, j_samples) + 2) - expected_physical_count
    )
    require(structural_origin_multiplicity == expected_structural_origin,
            "大伴随阶数与最小增广阶数之差不符")

    finite_raw_count = int(np.count_nonzero(raw_class == 0))
    infinite_raw_count = int(np.count_nonzero(raw_class == 2))
    nan_raw_count = int(np.count_nonzero(raw_class == 3))
    magnitudes = np.abs(physical_roots)
    dominant_index = int(np.argmax(magnitudes))
    dominant_root = physical_roots[dominant_index]
    rho = float(magnitudes[dominant_index])
    maximum_state = float(np.max(state_residuals))
    maximum_laurent = float(np.max(laurent_residuals))
    maximum_polynomial = float(np.max(polynomial_residuals))
    maximum_residual = max(maximum_state, maximum_laurent, maximum_polynomial)
    require(math.isfinite(rho) and rho > 0.0, f"rho={rho} 非法")

    source = bundle.row
    row: dict[str, Any] = {
        "point_row": point_row,
        "point_id": point_id,
        "l_samples": l_samples,
        "j_samples": j_samples,
        "bundle_id": source["bundle_id"],
        "division": int(source["division"]),
        "route": source["route"],
        "method": source["method"],
        "dimension": bundle.dimension,
        "candidate_id": source["candidate_id"],
        "candidate_name": source["candidate_name"],
        "paper_grid_eligible": 1,
        "formula_status": source["formula_status"],
        "source_mat_sha256": bundle.source_sha256,
        "laurent_min_exponent": minimum_exponent,
        "laurent_max_exponent": maximum_exponent,
        "clearing_power": clearing_power,
        "polynomial_degree": degree,
        "pencil_order": degree * bundle.dimension,
        "raw_root_count": int(raw_roots.size),
        "finite_raw_root_count": finite_raw_count,
        "infinite_raw_root_count": infinite_raw_count,
        "nan_raw_root_count": nan_raw_count,
        "removed_origin_root_count": structural_origin_multiplicity,
        "structural_origin_multiplicity": structural_origin_multiplicity,
        "expected_physical_root_count": expected_physical_count,
        "physical_root_count": int(physical_roots.size),
        "retained_root_count": int(physical_roots.size),
        "minimum_physical_root_magnitude": float(np.min(magnitudes)),
        "shared_left_factor_relative_error": factor_error,
        "delay_channel_1_register_scale": float(register_scales[0]),
        "delay_channel_2_register_scale": float(register_scales[1]),
        "transition_reconstruction_relative_error": transition_reconstruction_error,
        "rho": rho,
        "dominant_root_real": float(dominant_root.real),
        "dominant_root_imag": float(dominant_root.imag),
        "maximum_state_eigenpair_residual": maximum_state,
        "maximum_laurent_relative_residual": maximum_laurent,
        "maximum_polynomial_relative_residual": maximum_polynomial,
        "max_relative_residual": maximum_residual,
        "stable": int(rho < 1.0),
        "critical": int(abs(rho - 1.0) <= CRITICAL_TOLERANCE),
        "overall_pass": 1,
    }
    return PointSolve(
        row=row,
        full_companion_roots=raw_roots,
        full_companion_root_class=raw_class,
        full_companion_alpha=raw_alpha,
        full_companion_beta=raw_beta,
        physical_roots=physical_roots,
        physical_alpha=physical_alpha,
        physical_beta=physical_beta,
        minimal_qz_diagnostic_roots=minimal_qz_roots,
        minimal_qz_diagnostic_alpha=minimal_qz_alpha,
        minimal_qz_diagnostic_beta=minimal_qz_beta,
        state_eigenpair_residuals=state_residuals,
        laurent_residuals=laurent_residuals,
        polynomial_residuals=polynomial_residuals,
    )


def csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return format(value, ".17g")
    return value


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def fixed_unicode(values: Sequence[str]) -> np.ndarray:
    width = max(1, max((len(value) for value in values), default=1))
    return np.asarray(values, dtype=f"<U{width}")


def build_array_payload(
    solves: Sequence[PointSolve], rejection_rows: Sequence[Mapping[str, Any]]
) -> dict[str, np.ndarray]:
    rows = [solve.row for solve in solves]
    numeric_fields = (
        "point_row",
        "l_samples",
        "j_samples",
        "division",
        "dimension",
        "paper_grid_eligible",
        "laurent_min_exponent",
        "laurent_max_exponent",
        "clearing_power",
        "polynomial_degree",
        "pencil_order",
        "raw_root_count",
        "finite_raw_root_count",
        "infinite_raw_root_count",
        "nan_raw_root_count",
        "removed_origin_root_count",
        "structural_origin_multiplicity",
        "expected_physical_root_count",
        "physical_root_count",
        "retained_root_count",
        "minimum_physical_root_magnitude",
        "shared_left_factor_relative_error",
        "delay_channel_1_register_scale",
        "delay_channel_2_register_scale",
        "transition_reconstruction_relative_error",
        "rho",
        "dominant_root_real",
        "dominant_root_imag",
        "maximum_state_eigenpair_residual",
        "maximum_laurent_relative_residual",
        "maximum_polynomial_relative_residual",
        "max_relative_residual",
        "stable",
        "critical",
        "overall_pass",
    )
    integer_fields = {
        "point_row",
        "l_samples",
        "j_samples",
        "division",
        "dimension",
        "paper_grid_eligible",
        "laurent_min_exponent",
        "laurent_max_exponent",
        "clearing_power",
        "polynomial_degree",
        "pencil_order",
        "raw_root_count",
        "finite_raw_root_count",
        "infinite_raw_root_count",
        "nan_raw_root_count",
        "removed_origin_root_count",
        "structural_origin_multiplicity",
        "expected_physical_root_count",
        "physical_root_count",
        "retained_root_count",
        "stable",
        "critical",
        "overall_pass",
    }
    payload: dict[str, np.ndarray] = {}
    for field in numeric_fields:
        dtype = np.int64 if field in integer_fields else np.float64
        payload[f"point_{field}"] = np.asarray([row[field] for row in rows], dtype=dtype)

    for field in (
        "point_id",
        "bundle_id",
        "route",
        "method",
        "candidate_id",
        "candidate_name",
        "formula_status",
        "source_mat_sha256",
    ):
        payload[f"point_{field}"] = fixed_unicode([str(row[field]) for row in rows])

    raw_offsets = np.zeros(len(solves) + 1, dtype=np.int64)
    physical_offsets = np.zeros(len(solves) + 1, dtype=np.int64)
    for index, solve in enumerate(solves):
        raw_offsets[index + 1] = raw_offsets[index] + solve.full_companion_roots.size
        physical_offsets[index + 1] = physical_offsets[index] + solve.physical_roots.size
    payload["raw_root_offsets"] = raw_offsets
    payload["physical_root_offsets"] = physical_offsets
    payload["retained_root_offsets"] = physical_offsets.copy()
    payload["minimal_qz_diagnostic_root_offsets"] = physical_offsets.copy()
    payload["raw_root_real"] = np.concatenate(
        [solve.full_companion_roots.real for solve in solves]
    )
    payload["raw_root_imag"] = np.concatenate(
        [solve.full_companion_roots.imag for solve in solves]
    )
    payload["raw_root_class_code"] = np.concatenate(
        [solve.full_companion_root_class for solve in solves]
    ).astype(np.int8, copy=False)
    payload["raw_homogeneous_alpha_real"] = np.concatenate(
        [solve.full_companion_alpha.real for solve in solves]
    )
    payload["raw_homogeneous_alpha_imag"] = np.concatenate(
        [solve.full_companion_alpha.imag for solve in solves]
    )
    payload["raw_homogeneous_beta_real"] = np.concatenate(
        [solve.full_companion_beta.real for solve in solves]
    )
    payload["raw_homogeneous_beta_imag"] = np.concatenate(
        [solve.full_companion_beta.imag for solve in solves]
    )
    payload["physical_root_real"] = np.concatenate(
        [solve.physical_roots.real for solve in solves]
    )
    payload["physical_root_imag"] = np.concatenate(
        [solve.physical_roots.imag for solve in solves]
    )
    payload["physical_homogeneous_alpha_real"] = np.concatenate(
        [solve.physical_alpha.real for solve in solves]
    )
    payload["physical_homogeneous_alpha_imag"] = np.concatenate(
        [solve.physical_alpha.imag for solve in solves]
    )
    payload["physical_homogeneous_beta_real"] = np.concatenate(
        [solve.physical_beta.real for solve in solves]
    )
    payload["physical_homogeneous_beta_imag"] = np.concatenate(
        [solve.physical_beta.imag for solve in solves]
    )
    payload["minimal_qz_diagnostic_root_real"] = np.concatenate(
        [solve.minimal_qz_diagnostic_roots.real for solve in solves]
    )
    payload["minimal_qz_diagnostic_root_imag"] = np.concatenate(
        [solve.minimal_qz_diagnostic_roots.imag for solve in solves]
    )
    payload["minimal_qz_diagnostic_alpha_real"] = np.concatenate(
        [solve.minimal_qz_diagnostic_alpha.real for solve in solves]
    )
    payload["minimal_qz_diagnostic_alpha_imag"] = np.concatenate(
        [solve.minimal_qz_diagnostic_alpha.imag for solve in solves]
    )
    payload["minimal_qz_diagnostic_beta_real"] = np.concatenate(
        [solve.minimal_qz_diagnostic_beta.real for solve in solves]
    )
    payload["minimal_qz_diagnostic_beta_imag"] = np.concatenate(
        [solve.minimal_qz_diagnostic_beta.imag for solve in solves]
    )
    payload["physical_state_eigenpair_relative_residual"] = np.concatenate(
        [solve.state_eigenpair_residuals for solve in solves]
    )
    payload["physical_laurent_relative_residual"] = np.concatenate(
        [solve.laurent_residuals for solve in solves]
    )
    payload["physical_polynomial_relative_residual"] = np.concatenate(
        [solve.polynomial_residuals for solve in solves]
    )
    # 兼容读取名称：retained 在结构合同中即全部最小增广物理根。
    payload["retained_root_real"] = payload["physical_root_real"].copy()
    payload["retained_root_imag"] = payload["physical_root_imag"].copy()
    payload["retained_root_relative_residual"] = payload[
        "physical_polynomial_relative_residual"
    ].copy()
    payload["frozen_point_id"] = fixed_unicode([point[0] for point in FROZEN_POINTS])
    payload["frozen_point_l_samples"] = np.asarray([point[1] for point in FROZEN_POINTS], dtype=np.int64)
    payload["frozen_point_j_samples"] = np.asarray([point[2] for point in FROZEN_POINTS], dtype=np.int64)
    payload["eligible_candidate_id"] = fixed_unicode(list(ELIGIBLE_CANDIDATES))
    payload["rejected_candidate_id"] = fixed_unicode(list(REJECTED_CANDIDATES))
    payload["rejected_bundle_id"] = fixed_unicode([str(row["bundle_id"]) for row in rejection_rows])
    payload["residual_limit"] = np.asarray([RESIDUAL_LIMIT], dtype=np.float64)
    payload["critical_tolerance"] = np.asarray([CRITICAL_TOLERANCE], dtype=np.float64)
    payload["physical_root_contract_code"] = fixed_unicode(
        ["MINIMAL_AUGMENTED_ORDER_2N_PLUS_L_PLUS_J"]
    )
    payload["schema_version"] = np.asarray([2], dtype=np.int64)
    return payload


def write_deterministic_npz(path: Path, payload: Mapping[str, np.ndarray]) -> None:
    """使用固定 ZIP 时间戳和排序键写出可由 np.load 读取的确定性 NPZ。"""

    with path.open("wb") as raw_stream:
        with zipfile.ZipFile(raw_stream, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for key in sorted(payload):
                buffer = io.BytesIO()
                np.save(buffer, np.asarray(payload[key]), allow_pickle=False)
                info = zipfile.ZipInfo(filename=f"{key}.npy", date_time=(1980, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                info.external_attr = 0o600 << 16
                info.create_system = 3
                archive.writestr(info, buffer.getvalue(), compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)


def write_deterministic_mat(path: Path, payload: Mapping[str, np.ndarray]) -> None:
    savemat(path, dict(payload), do_compression=True, long_field_names=True, oned_as="column")
    deterministic_header = (
        b"MATLAB 5.0 MAT-file, Platform: PCWIN64, "
        b"Created by Board20 Step8D Python deterministic writer"
    )[:116].ljust(116, b" ")
    with path.open("r+b") as stream:
        stream.seek(0)
        stream.write(deterministic_header)


def json_ready(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, dict):
        return {str(key): json_ready(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_ready(item) for item in value]
    return value


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(json_ready(dict(payload)), ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def clean_known_outputs() -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for path in (
        POINT_CSV,
        REJECTION_CSV,
        NPZ_PATH,
        MAT_PATH,
        JSON_PATH,
        REPORT_PATH,
        MANIFEST_PATH,
    ):
        if path.exists():
            require(path.is_file(), f"预期输出目标不是文件：{path}")
            path.unlink()


def build_summary(
    solves: Sequence[PointSolve],
    rejection_rows: Sequence[Mapping[str, Any]],
    input_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    point_rows = [dict(solve.row) for solve in solves]
    expected_count = len(EXPECTED_ROUTE_KEYS) * len(ELIGIBLE_CANDIDATES) * len(FROZEN_POINTS)
    require(len(point_rows) == expected_count, f"逐点结果应为 {expected_count} 行，实际 {len(point_rows)}")
    require(all(int(row["overall_pass"]) == 1 for row in point_rows), "存在未通过试点")
    require(
        all(
            int(row["physical_root_count"])
            == 2 * int(row["dimension"])
            + int(row["l_samples"])
            + int(row["j_samples"])
            for row in point_rows
        ),
        "存在物理根数不等于2n+l+j的试点",
    )
    require(
        all(
            int(row["raw_root_count"])
            - int(row["physical_root_count"])
            == int(row["structural_origin_multiplicity"])
            for row in point_rows
        ),
        "结构性原点重数闭合失败",
    )
    require(len(rejection_rows) == len(EXPECTED_ROUTE_KEYS) * len(REJECTED_CANDIDATES),
            "R05/R06 拒绝数量不是12")

    route_candidate_coverage = {
        (int(row["division"]), row["method"], row["candidate_id"])
        for row in point_rows
    }
    require(len(route_candidate_coverage) == 24, "六路线x四候选覆盖不是24")
    for key in route_candidate_coverage:
        count = sum(
            1
            for row in point_rows
            if (int(row["division"]), row["method"], row["candidate_id"]) == key
        )
        require(count == len(FROZEN_POINTS), f"{key} 不是13个冻结试点")

    result = {
        "schema_version": 2,
        "status": "PASS_STEP8D_PYTHON_INDEPENDENT_PILOT",
        "scope": "six routes x R01-R04 x frozen P00-P12; no full-grid sweep",
        "solver": "scipy.linalg.solve(B,A) then scipy.linalg.eig on the exact-order 2*n+l+j minimal augmented transition matrix",
        "minimal_generalized_qz_diagnostic": "raw scipy generalized QZ roots of the same minimal pencil are stored separately and never used for rho or classification",
        "full_companion_diagnostic": "cleared-polynomial dense first companion, raw QZ only, never used for rho or physical-root count",
        "independence": "does not import repository MATLAB/Python generators or solvers",
        "fixed_points": [
            {"point_id": point_id, "l_samples": l_value, "j_samples": j_value}
            for point_id, l_value, j_value in FROZEN_POINTS
        ],
        "eligible_candidates": list(ELIGIBLE_CANDIDATES),
        "rejected_candidates": list(REJECTED_CANDIDATES),
        "input_index_sha256": sha256_file(INDEX_PATH),
        "input_bundle_count": len(input_rows),
        "loaded_eligible_bundle_count": len(route_candidate_coverage),
        "rejected_before_loadmat_count": len(rejection_rows),
        "point_result_count": len(point_rows),
        "overall_pass_count": sum(int(row["overall_pass"]) for row in point_rows),
        "stable_count": sum(int(row["stable"]) for row in point_rows),
        "critical_count": sum(int(row["critical"]) for row in point_rows),
        "maximum_relative_residual": max(float(row["max_relative_residual"]) for row in point_rows),
        "maximum_state_eigenpair_residual": max(
            float(row["maximum_state_eigenpair_residual"]) for row in point_rows
        ),
        "maximum_laurent_relative_residual": max(
            float(row["maximum_laurent_relative_residual"]) for row in point_rows
        ),
        "maximum_polynomial_relative_residual": max(
            float(row["maximum_polynomial_relative_residual"]) for row in point_rows
        ),
        "maximum_shared_left_factor_relative_error": max(
            float(row["shared_left_factor_relative_error"]) for row in point_rows
        ),
        "minimum_register_scale": min(
            min(
                float(row["delay_channel_1_register_scale"]),
                float(row["delay_channel_2_register_scale"]),
            )
            for row in point_rows
        ),
        "maximum_register_scale": max(
            max(
                float(row["delay_channel_1_register_scale"]),
                float(row["delay_channel_2_register_scale"]),
            )
            for row in point_rows
        ),
        "maximum_transition_reconstruction_relative_error": max(
            float(row["transition_reconstruction_relative_error"]) for row in point_rows
        ),
        "maximum_pencil_order": max(int(row["pencil_order"]) for row in point_rows),
        "maximum_minimal_augmented_order": max(
            int(row["physical_root_count"]) for row in point_rows
        ),
        "maximum_rho": max(float(row["rho"]) for row in point_rows),
        "minimum_rho": min(float(row["rho"]) for row in point_rows),
        "minimum_physical_root_magnitude": min(
            float(row["minimum_physical_root_magnitude"]) for row in point_rows
        ),
        "total_raw_root_count": sum(int(row["raw_root_count"]) for row in point_rows),
        "total_physical_root_count": sum(int(row["physical_root_count"]) for row in point_rows),
        "total_retained_root_count": sum(int(row["physical_root_count"]) for row in point_rows),
        "total_removed_origin_root_count": sum(int(row["removed_origin_root_count"]) for row in point_rows),
        "residual_limit": RESIDUAL_LIMIT,
        "same_exponent_rule": "sum every Laurent contribution at the same exponent before clearing",
        "physical_root_rule": "all and only eigenvalues of the exact 2*n+l+j minimal augmented pencil",
        "origin_root_rule": "structural multiplicity equals full-companion order minus 2*n+l+j; no magnitude threshold is used",
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "blas_threads": 1,
        },
        "point_results": point_rows,
        "rejections": [dict(row) for row in rejection_rows],
    }
    return result


def write_report(summary: Mapping[str, Any]) -> None:
    lines = [
        "# 板块20最小步骤8D：Python独立单点求解门禁",
        "",
        f"- 结论：`{summary['status']}`",
        f"- 计算范围：{summary['point_result_count']} 个“模型链—候选—试点”组合，全部通过；未扫描全网格。",
        f"- 资格门禁：R01--R04共24个数值包进入求解；R05/R06共{summary['rejected_before_loadmat_count']}个包在 `loadmat` 前拒绝。",
        f"- 求解器：{summary['solver']}。",
        f"- 标准转移矩阵最大重构误差：{summary['maximum_transition_reconstruction_relative_error']:.17g}。",
        f"- 标量寄存器固定量纲缩放范围：{summary['minimum_register_scale']:.17g} 至 {summary['maximum_register_scale']:.17g}。",
        f"- 最大最小增广阶数：{summary['maximum_minimal_augmented_order']}；大伴随诊断最大阶数：{summary['maximum_pencil_order']}。",
        f"- 最大残差：状态铅笔 {summary['maximum_state_eigenpair_residual']:.17g}，Laurent原式 {summary['maximum_laurent_relative_residual']:.17g}，清幂多项式 {summary['maximum_polynomial_relative_residual']:.17g} （三门均为 {RESIDUAL_LIMIT:.1e}）。",
        f"- 全部大伴随诊断根：{summary['total_raw_root_count']}；结构性原点重数：{summary['total_removed_origin_root_count']}；最小增广全部物理根：{summary['total_physical_root_count']}。",
        f"- 所有试点中最小物理根幅值：{summary['minimum_physical_root_magnitude']:.17g}。",
        "",
        "## 冻结试点",
        "",
        "`P00(0,0), P01(1,0), P02(0,1), P03(3,7), P04(10,20), P05(15,33), P06(30,66), P07(1,48), P08(1,51), P09(1,57), P10(1,58), P11(1,59), P12(1,64)`",
        "",
        "P07--P12是论文六条右端列附近的低行验收点，只用于验收，未用于调参。",
        "",
        "## 数值合同",
        "",
        "1. 同一 Laurent 幂次的惯性、非时滞、两个时滞通道和 H 外反馈项先相加，再清除负幂次。",
        "2. 每个时滞通道断言阻尼与刚度项共享同一左向量，并用长度为d的标量移位寄存器建立阶数2n+l+j的最小增广铅笔；寄存器按输入通道系数范数做固定量纲缩放。",
        "3. 谱半径、稳定分类和物理根数只来自最小增广铅笔；清幂大伴随QZ只作原始诊断，不用经验幅值阈值删根。",
        "4. 每个物理特征对同时回代最小增广状态铅笔、Laurent原式和清幂矩阵多项式，三类无量纲相对残差均必须不超过1e-8。",
        "",
        "## 输出",
        "",
        f"- `{POINT_CSV.name}`：逐点 rho、根数、清幂与残差门禁。",
        f"- `{NPZ_PATH.name}` 和 `{MAT_PATH.name}`：按 offset 索引的大伴随原始诊断根、全部最小增广物理根、homogeneous alpha/beta 和三类回代残差。",
        f"- `{JSON_PATH.name}`：可机器读取的完整摘要。",
        f"- `{REJECTION_CSV.name}`：R05/R06的读取前拒绝证据。",
        f"- `{MANIFEST_PATH.name}`：源代码、输入包与输出工件的 SHA-256 确定性清单。",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")


def write_manifest(index_rows: Sequence[Mapping[str, str]]) -> None:
    rows: list[dict[str, Any]] = []

    def append(role: str, path: Path) -> None:
        rows.append(
            {
                "role": role,
                "relative_path": path.relative_to(BOARD_ROOT).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )

    append("solver_source", SCRIPT_PATH)
    append("input_index", INDEX_PATH)
    for row in sorted(index_rows, key=route_sort_key):
        append("input_candidate_bundle", INPUT_ROOT / row["relative_path"])
    for path in (POINT_CSV, REJECTION_CSV, NPZ_PATH, MAT_PATH, JSON_PATH, REPORT_PATH):
        append("output_artifact", path)
    write_csv(MANIFEST_PATH, ("role", "relative_path", "bytes", "sha256"), rows)


def run() -> int:
    parser = argparse.ArgumentParser(
        description="板块20步骤8D Python独立冻结试点求解器（不提供试点覆盖参数）"
    )
    parser.parse_args()
    clean_known_outputs()
    index_rows = read_index()

    rejection_rows: list[dict[str, Any]] = []
    for row in sorted(index_rows, key=route_sort_key):
        if row["candidate_id"] not in REJECTED_CANDIDATES:
            continue
        loadmat_called = 0
        try:
            _ = load_eligible_bundle(row)
        except CandidateRejected as exc:
            rejection_rows.append(
                {
                    "bundle_id": row["bundle_id"],
                    "division": int(row["division"]),
                    "method": row["method"],
                    "dimension": int(row["dimension"]),
                    "candidate_id": row["candidate_id"],
                    "formula_status": row["formula_status"],
                    "paper_grid_eligible": row["paper_grid_eligible"],
                    "loadmat_called": loadmat_called,
                    "rejection_stage": "BEFORE_SCIPY_IO_LOADMAT",
                    "rejection_reason": str(exc),
                    "overall_pass": 1,
                }
            )
        else:
            raise ContractError(f"{row['bundle_id']} 应在 loadmat 前拒绝，但却通过")
    require(len(rejection_rows) == 12, f"R05/R06 应拒绝12个包，实际 {len(rejection_rows)}")

    eligible_rows = [
        row for row in sorted(index_rows, key=route_sort_key) if row["candidate_id"] in ELIGIBLE_CANDIDATES
    ]
    require(len(eligible_rows) == 24, f"R01--R04 应有24个包，实际 {len(eligible_rows)}")
    bundles = [load_eligible_bundle(row) for row in eligible_rows]

    solves: list[PointSolve] = []
    expected_total = len(bundles) * len(FROZEN_POINTS)
    for bundle_index, bundle in enumerate(bundles, start=1):
        print(
            f"[{bundle_index:02d}/{len(bundles):02d}] {bundle.row['bundle_id']} "
            f"n={bundle.dimension}",
            flush=True,
        )
        for point_id, l_samples, j_samples in FROZEN_POINTS:
            solve = solve_bundle_point(
                bundle,
                point_row=len(solves),
                point_id=point_id,
                l_samples=l_samples,
                j_samples=j_samples,
            )
            solves.append(solve)
            print(
                f"  {point_id}({l_samples},{j_samples}) "
                f"rho={solve.row['rho']:.12g} degree={solve.row['polynomial_degree']} "
                f"roots={solve.row['retained_root_count']} "
                f"res={solve.row['max_relative_residual']:.3e} "
                f"[{len(solves)}/{expected_total}]",
                flush=True,
            )

    point_rows = [solve.row for solve in solves]
    write_csv(POINT_CSV, POINT_FIELDNAMES, point_rows)
    write_csv(
        REJECTION_CSV,
        (
            "bundle_id",
            "division",
            "method",
            "dimension",
            "candidate_id",
            "formula_status",
            "paper_grid_eligible",
            "loadmat_called",
            "rejection_stage",
            "rejection_reason",
            "overall_pass",
        ),
        rejection_rows,
    )

    payload = build_array_payload(solves, rejection_rows)
    write_deterministic_npz(NPZ_PATH, payload)
    write_deterministic_mat(MAT_PATH, payload)
    summary = build_summary(solves, rejection_rows, index_rows)
    write_json(JSON_PATH, summary)
    write_report(summary)
    write_manifest(index_rows)

    print(
        f"PASS_STEP8D_PYTHON_INDEPENDENT_PILOT: {len(solves)}/{expected_total} 通过，"
        f"最大残差={summary['maximum_relative_residual']:.3e}，"
        f"R05/R06读取前拒绝={len(rejection_rows)}/12",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except ContractError as exc:
        print(f"FAIL_STEP8D_PYTHON_CONTRACT: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)

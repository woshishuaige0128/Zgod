#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块20步骤8E：Python独立的R01--R04四候选全网格求解。

计算边界：
1. 只读取步骤8C索引和R01--R04的24个公式一致数值包；
2. 在任何MAT读取和全网格数组分配前，依据索引硬拒绝R05/R06；
3. 固定计算六模型链 x R01--R04 x l=0..30 x j=0..66，共49,848点；
4. 不读取论文边界、历史稳定掩膜、步骤8D求解器或任何仓库求解器；
5. 主路线为gamma量纲缩放、阶数严格2*n+l+j的最小增广状态转移矩阵；
6. 全点保存全部物理根及逐根状态特征对残差，边界证书点另保存逐根
   Laurent原式与清幂矩阵多项式残差；所有适用残差门均为1e-8。

运行模式：
  --mode sentinel        先运行24组各10个固定性能哨兵并写出估时；
  --mode full-two-round  在哨兵通过后完整运行两轮并生成逐字节确定性证据。
"""

from __future__ import annotations

import os

# 必须在NumPy/SciPy导入前冻结BLAS线程，以固定数值顺序。
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import argparse
import csv
import gc
import hashlib
import io
import json
import math
import platform
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import scipy
from scipy.io import loadmat
from scipy.linalg import eig, solve


SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parent.parent
INPUT_ROOT = BOARD_ROOT / "outputs" / "step8c_六链模型生成" / "python"
INDEX_PATH = INPUT_ROOT / "六路线六候选索引.csv"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step8e_四候选全网格" / "python"

SENTINEL_CSV = OUTPUT_ROOT / "步骤8E_Python性能哨兵逐点.csv"
SENTINEL_JSON = OUTPUT_ROOT / "步骤8E_Python性能哨兵摘要.json"
SENTINEL_REPORT = OUTPUT_ROOT / "步骤8E_Python性能哨兵报告.md"

POINT_CSV = OUTPUT_ROOT / "步骤8E_Python全网格逐点结果.csv"
ROOT_NPZ = OUTPUT_ROOT / "步骤8E_Python全网格索引与边界证书.npz"
SHARD_ROOT = OUTPUT_ROOT / "全根分块"
CERTIFICATE_CSV = OUTPUT_ROOT / "步骤8E_Python边界证书.csv"
REJECTION_CSV = OUTPUT_ROOT / "步骤8E_Python诊断候选拒绝.csv"
SUMMARY_JSON = OUTPUT_ROOT / "步骤8E_Python全网格摘要.json"
REPORT_MD = OUTPUT_ROOT / "步骤8E_Python全网格计算报告.md"
CALCULATION_LOG = OUTPUT_ROOT / "步骤8E_Python确定性计算日志.txt"
DETERMINISM_CSV = OUTPUT_ROOT / "步骤8E_Python双轮逐字节确定性证据.csv"
MANIFEST_CSV = OUTPUT_ROOT / "步骤8E_Python工件哈希清单.csv"

FORMAL_ARTIFACTS = (
    POINT_CSV,
    ROOT_NPZ,
    CERTIFICATE_CSV,
    REJECTION_CSV,
    SUMMARY_JSON,
    REPORT_MD,
    CALCULATION_LOG,
)

ELIGIBLE_CANDIDATES = ("R01", "R02", "R03", "R04")
REJECTED_CANDIDATES = ("R05", "R06")
ELIGIBLE_TEXT = "ELIGIBLE_SOURCE_COMPLETION"
ELIGIBLE_FORMULA_TEXT = "FORMULA_COHERENT_SOURCE_COMPLETION"
RESIDUAL_LIMIT = 1.0e-8
FACTOR_LIMIT = 1.0e-12
TRANSITION_LIMIT = 1.0e-12
CRITICAL_TOLERANCE = 1.0e-8

L_VALUES = tuple(range(31))
J_VALUES = tuple(range(67))
POINTS_PER_GROUP = len(L_VALUES) * len(J_VALUES)
EXPECTED_GROUP_COUNT = 24
EXPECTED_POINT_COUNT = EXPECTED_GROUP_COUNT * POINTS_PER_GROUP
EXPECTED_TOTAL_ROOT_COUNT = 3_356_432
EXPECTED_SENTINEL_TOTAL_ROOT_COUNT = 13_232

# 外部冻结的性能哨兵：不得按运行结果增删或更改。
PERFORMANCE_SENTINELS: tuple[tuple[str, int, int], ...] = (
    ("S00", 0, 0),
    ("S01", 1, 0),
    ("S02", 0, 1),
    ("S03", 3, 7),
    ("S04", 10, 20),
    ("S05", 15, 33),
    ("S06", 30, 66),
    ("S07", 1, 48),
    ("S08", 1, 57),
    ("S09", 1, 64),
)

EXPECTED_ROUTE_KEYS = (
    (1, "Original", 15),
    (1, "Guyan", 6),
    (1, "Craig_Bampton", 9),
    (2, "Original", 15),
    (2, "Guyan", 5),
    (2, "Craig_Bampton", 8),
)

POINT_FIELDS = (
    "point_index",
    "point_key",
    "group_index",
    "bundle_id",
    "division",
    "route",
    "method",
    "dimension",
    "candidate_id",
    "candidate_name",
    "l_samples",
    "j_samples",
    "physical_root_count",
    "root_offset_start",
    "root_offset_end",
    "root_shard_name",
    "shard_root_offset_start",
    "shard_root_offset_end",
    "rho",
    "dominant_root_real",
    "dominant_root_imag",
    "stable",
    "critical",
    "stability_code",
    "stability_status",
    "delay_channel_1_register_scale",
    "delay_channel_2_register_scale",
    "shared_left_factor_relative_error",
    "transition_reconstruction_relative_error",
    "maximum_state_eigenpair_residual",
    "overall_pass",
)

CERTIFICATE_FIELDS = (
    "certificate_index",
    "certificate_key",
    "point_index",
    "bundle_id",
    "division",
    "route",
    "method",
    "dimension",
    "candidate_id",
    "l_samples",
    "j_samples",
    "rho",
    "stable",
    "critical",
    "stability_code",
    "stability_status",
    "l_adjacent_change_incident_count",
    "j_adjacent_change_incident_count",
    "l_row_nearest_to_unit",
    "j_column_nearest_to_unit",
    "reason_count",
    "physical_root_count",
    "global_root_offset_start",
    "global_root_offset_end",
    "root_shard_name",
    "shard_root_offset_start",
    "shard_root_offset_end",
    "certificate_root_offset_start",
    "certificate_root_offset_end",
    "maximum_state_eigenpair_residual",
    "maximum_laurent_relative_residual",
    "maximum_polynomial_relative_residual",
    "overall_pass",
)


class ContractError(RuntimeError):
    """输入、数值、资格或输出合同失败。"""


class CandidateRejected(ContractError):
    """R05/R06在任何MAT读取和网格分配前被拒绝。"""


@dataclass(frozen=True)
class Bundle:
    row: Mapping[str, str]
    path: Path
    source_sha256: str
    dimension: int
    dt: float
    mass_term: np.ndarray
    base_zero: np.ndarray
    base_minus_one: np.ndarray
    delay_left: np.ndarray
    delay_v_zero: np.ndarray
    delay_v_minus_one: np.ndarray
    register_scales: np.ndarray
    shared_left_factor_relative_error: float


@dataclass(frozen=True)
class SolveResult:
    roots: np.ndarray
    state_residuals: np.ndarray
    rho: float
    dominant_root: complex
    stable: int
    critical: int
    stability_code: int
    stability_status: str
    transition_reconstruction_relative_error: float
    physical_vectors: np.ndarray | None


@dataclass
class CertificateReason:
    l_adjacent_change_incident_count: int = 0
    j_adjacent_change_incident_count: int = 0
    l_row_nearest_to_unit: int = 0
    j_column_nearest_to_unit: int = 0

    @property
    def reason_count(self) -> int:
        return (
            int(self.l_adjacent_change_incident_count > 0)
            + int(self.j_adjacent_change_incident_count > 0)
            + self.l_row_nearest_to_unit
            + self.j_column_nearest_to_unit
        )


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
    require(array.size == 1, f"{name}必须是标量，实际shape={array.shape}")
    result = float(array.reshape(-1)[0])
    require(math.isfinite(result), f"{name}必须是有限数")
    return result


def matrix_float(value: Any, name: str, shape: tuple[int, int]) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    require(result.shape == shape, f"{name} shape={result.shape}，预期{shape}")
    require(np.all(np.isfinite(result)), f"{name}包含非有限数")
    return np.ascontiguousarray(result)


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected, ord="fro") / denominator)


def csv_value(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".17g")
    if isinstance(value, (np.integer,)):
        return int(value)
    return value


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: csv_value(row.get(key, "")) for key in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def fixed_unicode(values: Sequence[str]) -> np.ndarray:
    width = max(1, max((len(value) for value in values), default=1))
    return np.asarray(values, dtype=f"<U{width}")


def read_index() -> list[dict[str, str]]:
    require(INDEX_PATH.is_file(), f"缺少步骤8C索引：{INDEX_PATH}")
    with INDEX_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    require(len(rows) == 36, f"步骤8C索引必须36行，实际{len(rows)}")
    require(len({row["bundle_id"] for row in rows}) == 36, "bundle_id不唯一")
    require(
        {row["candidate_id"] for row in rows}
        == set(ELIGIBLE_CANDIDATES + REJECTED_CANDIDATES),
        "步骤8C候选身份集合不符",
    )
    actual_routes = {
        (int(row["division"]), row["method"], int(row["dimension"])) for row in rows
    }
    require(actual_routes == set(EXPECTED_ROUTE_KEYS), "六模型链身份不符")
    for route_key in EXPECTED_ROUTE_KEYS:
        route_rows = [
            row
            for row in rows
            if (int(row["division"]), row["method"], int(row["dimension"])) == route_key
        ]
        require(len(route_rows) == 6, f"模型链{route_key}不是6个候选")
        require(
            {row["candidate_id"] for row in route_rows}
            == set(ELIGIBLE_CANDIDATES + REJECTED_CANDIDATES),
            f"模型链{route_key}未严格覆盖R01--R06",
        )
    return rows


def route_sort_key(row: Mapping[str, str]) -> tuple[int, int, int]:
    method_order = {"Original": 0, "Guyan": 1, "Craig_Bampton": 2}
    return (
        int(row["division"]),
        method_order[row["method"]],
        int(row["candidate_id"][1:]),
    )


def guard_candidate_before_any_load_or_grid(row: Mapping[str, str]) -> None:
    candidate_id = row["candidate_id"]
    if candidate_id not in ELIGIBLE_CANDIDATES:
        raise CandidateRejected(
            f"{row['bundle_id']}的{candidate_id}不在R01--R04公式一致候选集"
        )
    if row["paper_grid_eligible"] != ELIGIBLE_TEXT:
        raise CandidateRejected(
            f"{row['bundle_id']} paper_grid_eligible={row['paper_grid_eligible']}"
        )
    if row["formula_status"] != ELIGIBLE_FORMULA_TEXT:
        raise CandidateRejected(
            f"{row['bundle_id']} formula_status={row['formula_status']}"
        )


def gate_entire_index_before_any_load_or_grid(
    index_rows: Sequence[Mapping[str, str]],
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """先完整拒绝R05/R06，再允许任何loadmat或全网格数组分配。"""

    eligible_rows: list[dict[str, str]] = []
    rejection_rows: list[dict[str, Any]] = []
    for source in sorted(index_rows, key=route_sort_key):
        row = dict(source)
        if row["candidate_id"] in REJECTED_CANDIDATES:
            try:
                guard_candidate_before_any_load_or_grid(row)
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
                        "loadmat_called": 0,
                        "grid_allocation_started": 0,
                        "rejection_stage": "BEFORE_ANY_LOADMAT_OR_GRID_ALLOCATION",
                        "rejection_reason": str(exc),
                        "overall_pass": 1,
                    }
                )
            else:
                raise ContractError(f"{row['bundle_id']}应在读取/网格分配前拒绝")
        else:
            guard_candidate_before_any_load_or_grid(row)
            eligible_rows.append(row)

    require(len(rejection_rows) == 12, f"R05/R06读取前拒绝应为12，实际{len(rejection_rows)}")
    require(len(eligible_rows) == EXPECTED_GROUP_COUNT, "R01--R04合格包不是24个")
    require(
        {row["candidate_id"] for row in eligible_rows} == set(ELIGIBLE_CANDIDATES),
        "合格候选集不是R01--R04",
    )
    expected_eligible_keys = {
        (division, method, candidate_id)
        for division, method, _ in EXPECTED_ROUTE_KEYS
        for candidate_id in ELIGIBLE_CANDIDATES
    }
    actual_eligible_keys = {
        (int(row["division"]), row["method"], row["candidate_id"])
        for row in eligible_rows
    }
    require(actual_eligible_keys == expected_eligible_keys,
            "24个合格包不是六模型链xR01--R04严格笛卡尔积")
    return eligible_rows, rejection_rows


def load_eligible_bundle(row: Mapping[str, str]) -> Bundle:
    """只能在全索引资格门执行完毕后由调用者使用。"""

    guard_candidate_before_any_load_or_grid(row)
    path = INPUT_ROOT / row["relative_path"]
    require(path.is_file(), f"候选数值包不存在：{path}")
    source_sha = sha256_file(path)
    require(source_sha == row["mat_sha256"], f"{row['bundle_id']} MAT SHA-256不符")
    data = loadmat(path, squeeze_me=True, struct_as_record=False)

    n = int(row["dimension"])
    require(
        int(round(scalar_float(data["candidate_index"], "candidate_index")))
        == int(row["candidate_id"][1:]),
        f"{row['bundle_id']} candidate_index不符",
    )
    require(
        int(round(scalar_float(data["division"], "division"))) == int(row["division"]),
        f"{row['bundle_id']} division不符",
    )
    require(
        int(round(scalar_float(data["route_dimension"], "route_dimension"))) == n,
        f"{row['bundle_id']} route_dimension不符",
    )
    require(scalar_float(data["formula_valid_code"], "formula_valid_code") == 1.0,
            f"{row['bundle_id']} formula_valid_code不是1")
    require(scalar_float(data["paper_grid_eligible_code"], "paper_grid_eligible_code") == 1.0,
            f"{row['bundle_id']} paper_grid_eligible_code不是1")
    require(scalar_float(data["feedback_placement_code"], "feedback_placement_code") == 1.0,
            f"{row['bundle_id']}反馈不在H之外")

    dt = scalar_float(data["dt"], "dt")
    require(dt > 0.0, f"{row['bundle_id']} dt必须大于0")
    integration_mass_operator = matrix_float(
        data["integration_mass_operator"], "integration_mass_operator", (n, n)
    )
    c1 = matrix_float(data["C1"], "C1", (n, n))
    k1 = matrix_float(data["K1"], "K1", (n, n))
    delay_c_left = matrix_float(
        data["delay_C_left_factor"], "delay_C_left_factor", (n, 2)
    )
    delay_c_right = matrix_float(
        data["delay_C_right_factor"], "delay_C_right_factor", (2, n)
    )
    delay_k_left = matrix_float(
        data["delay_K_left_factor"], "delay_K_left_factor", (n, 2)
    )
    delay_k_right = matrix_float(
        data["delay_K_right_factor"], "delay_K_right_factor", (2, n)
    )
    feedback_c = matrix_float(data["feedback_C"], "feedback_C", (n, n))
    feedback_k = matrix_float(data["feedback_K"], "feedback_K", (n, n))

    c2_rebuilt = delay_c_left @ delay_c_right
    k2_rebuilt = delay_k_left @ delay_k_right
    c2_stored = matrix_float(data["C2_zero_delay"], "C2_zero_delay", (n, n))
    k2_stored = matrix_float(data["K2_zero_delay"], "K2_zero_delay", (n, n))
    require(relative_error(c2_rebuilt, c2_stored) <= FACTOR_LIMIT,
            f"{row['bundle_id']}时滞阻尼低秩分解不闭合")
    require(relative_error(k2_rebuilt, k2_stored) <= FACTOR_LIMIT,
            f"{row['bundle_id']}时滞刚度低秩分解不闭合")
    full_c = matrix_float(data["C"], "C", (n, n))
    full_k = matrix_float(data["K"], "K", (n, n))
    require(relative_error(c1 + c2_rebuilt, full_c) <= FACTOR_LIMIT,
            f"{row['bundle_id']} C1+C2零时滞不闭合")
    require(relative_error(k1 + k2_rebuilt, full_k) <= FACTOR_LIMIT,
            f"{row['bundle_id']} K1+K2零时滞不闭合")

    delay_left = np.empty_like(delay_c_left)
    v_zero = np.empty_like(delay_c_right)
    v_minus_one = np.empty_like(delay_c_right)
    register_scales = np.empty(2, dtype=np.float64)
    maximum_factor_error = 0.0
    for channel in range(2):
        c_left = delay_c_left[:, channel]
        k_left = delay_k_left[:, channel]
        denominator = max(
            float(np.linalg.norm(c_left, 2)),
            float(np.linalg.norm(k_left, 2)),
            np.finfo(float).eps,
        )
        error = float(np.linalg.norm(c_left - k_left, 2) / denominator)
        maximum_factor_error = max(maximum_factor_error, error)
        require(error <= FACTOR_LIMIT,
                f"{row['bundle_id']}通道{channel + 1}未共享同一左向量：{error:.17g}")
        delay_left[:, channel] = c_left
        v_zero[channel, :] = delay_c_right[channel, :] / dt + delay_k_right[channel, :]
        v_minus_one[channel, :] = -delay_c_right[channel, :] / dt
        register_scales[channel] = max(
            float(np.linalg.norm(v_zero[channel, :], 2)),
            float(np.linalg.norm(v_minus_one[channel, :], 2)),
            np.finfo(float).eps,
        )

    mass_term = integration_mass_operator / (dt * dt)
    require(np.linalg.matrix_rank(mass_term) == n, f"{row['bundle_id']}质量推进块不满秩")
    base_zero = (
        -2.0 * mass_term
        + c1 / dt
        + k1
        + feedback_c / dt
        + feedback_k
    )
    base_minus_one = mass_term - c1 / dt - feedback_c / dt
    for name, value in (
        ("mass_term", mass_term),
        ("base_zero", base_zero),
        ("base_minus_one", base_minus_one),
        ("delay_left", delay_left),
        ("delay_v_zero", v_zero),
        ("delay_v_minus_one", v_minus_one),
        ("register_scales", register_scales),
    ):
        require(np.all(np.isfinite(value)), f"{row['bundle_id']} {name}包含非有限数")

    return Bundle(
        row=dict(row),
        path=path,
        source_sha256=source_sha,
        dimension=n,
        dt=dt,
        mass_term=np.ascontiguousarray(mass_term),
        base_zero=np.ascontiguousarray(base_zero),
        base_minus_one=np.ascontiguousarray(base_minus_one),
        delay_left=np.ascontiguousarray(delay_left),
        delay_v_zero=np.ascontiguousarray(v_zero),
        delay_v_minus_one=np.ascontiguousarray(v_minus_one),
        register_scales=np.ascontiguousarray(register_scales),
        shared_left_factor_relative_error=maximum_factor_error,
    )


def build_minimal_augmented_current(
    bundle: Bundle, l_samples: int, j_samples: int
) -> np.ndarray:
    """构造A y_k=z B y_k中的A；B为diag(mass_term,I)。"""

    require(l_samples in L_VALUES, f"l={l_samples}不在固定0..30网格")
    require(j_samples in J_VALUES, f"j={j_samples}不在固定0..66网格")
    n = bundle.dimension
    delays = (l_samples, j_samples)
    state_order = 2 * n + l_samples + j_samples
    current = np.zeros((state_order, state_order), dtype=np.float64)
    current[:n, :n] = -bundle.base_zero
    current[:n, n : 2 * n] = -bundle.base_minus_one
    current[n : 2 * n, :n] = np.eye(n)

    offset = 2 * n
    for channel, delay in enumerate(delays):
        u_vector = bundle.delay_left[:, channel]
        v_zero = bundle.delay_v_zero[channel, :]
        v_minus_one = bundle.delay_v_minus_one[channel, :]
        gamma = float(bundle.register_scales[channel])
        if delay == 0:
            current[:n, :n] -= np.outer(u_vector, v_zero)
            current[:n, n : 2 * n] -= np.outer(u_vector, v_minus_one)
            continue
        current[:n, offset + delay - 1] -= u_vector * gamma
        current[offset, :n] = v_zero / gamma
        current[offset, n : 2 * n] = v_minus_one / gamma
        for register in range(1, delay):
            current[offset + register, offset + register - 1] = 1.0
        offset += delay

    require(offset == state_order, f"最小增广索引{offset}与阶数{state_order}不符")
    require(np.all(np.isfinite(current)), "最小增广当前时刻矩阵包含非有限数")
    return current


def solve_minimal_point(
    bundle: Bundle,
    l_samples: int,
    j_samples: int,
    *,
    return_physical_vectors: bool,
) -> SolveResult:
    """以B^{-1}A标准转移矩阵求全部2*n+l+j个物理特征对。"""

    n = bundle.dimension
    expected_order = 2 * n + l_samples + j_samples
    current = build_minimal_augmented_current(bundle, l_samples, j_samples)
    require(current.shape == (expected_order, expected_order), "最小增广阶数不等于2n+l+j")

    # B=diag(mass_term,I)，只求解顶部n行；这是完整solve(B,A)的精确块实现。
    transition = np.array(current, dtype=np.float64, order="F", copy=True)
    transition[:n, :] = solve(
        bundle.mass_term,
        current[:n, :],
        assume_a="gen",
        overwrite_a=False,
        overwrite_b=False,
        check_finite=False,
    )
    reconstruction_top = bundle.mass_term @ transition[:n, :] - current[:n, :]
    current_norm = float(np.linalg.norm(current, ord="fro"))
    require(current_norm > 0.0 and math.isfinite(current_norm), "状态矩阵范数非法")
    transition_error = float(np.linalg.norm(reconstruction_top, ord="fro") / current_norm)
    require(transition_error <= TRANSITION_LIMIT,
            f"B*T-A重构误差{transition_error:.17g}超过{TRANSITION_LIMIT:.1e}")

    roots, eigenvectors = eig(
        transition,
        left=False,
        right=True,
        overwrite_a=True,
        check_finite=False,
    )
    require(roots.size == expected_order, "物理根数不等于2n+l+j")
    require(np.all(np.isfinite(roots.real)) and np.all(np.isfinite(roots.imag)),
            "物理根包含NaN/Inf")
    order_index = np.lexsort((roots.imag, roots.real, np.abs(roots)))
    roots = np.asarray(roots[order_index], dtype=np.complex128)
    eigenvectors = np.asarray(eigenvectors[:, order_index], dtype=np.complex128)

    vector_norms = np.linalg.norm(eigenvectors, axis=0)
    require(np.all(np.isfinite(vector_norms)) and np.all(vector_norms > 0.0),
            "状态特征向量范数非法")
    current_times_vectors = current @ eigenvectors
    following_times_vectors = np.empty_like(eigenvectors)
    following_times_vectors[:n, :] = bundle.mass_term @ eigenvectors[:n, :]
    following_times_vectors[n:, :] = eigenvectors[n:, :]
    following_norm = math.sqrt(
        float(np.linalg.norm(bundle.mass_term, ord="fro")) ** 2 + (expected_order - n)
    )
    state_denominator = (
        current_norm + np.abs(roots) * following_norm
    ) * vector_norms
    require(np.all(state_denominator > 0.0) and np.all(np.isfinite(state_denominator)),
            "状态特征对残差分母非法")
    state_residuals = np.linalg.norm(
        current_times_vectors - following_times_vectors * roots[np.newaxis, :], axis=0
    ) / state_denominator
    require(np.all(np.isfinite(state_residuals)), "状态特征对残差包含NaN/Inf")
    maximum_state_residual = float(np.max(state_residuals))
    require(maximum_state_residual <= RESIDUAL_LIMIT,
            f"状态特征对最大残差{maximum_state_residual:.17g}超过{RESIDUAL_LIMIT:.1e}")

    magnitudes = np.abs(roots)
    dominant_index = int(np.argmax(magnitudes))
    rho = float(magnitudes[dominant_index])
    require(math.isfinite(rho) and rho > 0.0, f"rho={rho}非法")
    dominant_root = complex(roots[dominant_index])
    stable = int(rho < 1.0)
    critical = int(abs(rho - 1.0) <= CRITICAL_TOLERANCE)
    if critical:
        stability_code = 0
        stability_status = "CRITICAL"
    elif stable:
        stability_code = -1
        stability_status = "STABLE"
    else:
        stability_code = 1
        stability_status = "UNSTABLE"

    physical_vectors: np.ndarray | None = None
    if return_physical_vectors:
        physical_vectors = np.array(eigenvectors[:n, :], dtype=np.complex128, copy=True)
        physical_norms = np.linalg.norm(physical_vectors, axis=0)
        require(np.all(np.isfinite(physical_norms)) and np.all(physical_norms > 0.0),
                "前n维物理向量范数非法")
        physical_vectors /= physical_norms[np.newaxis, :]

    return SolveResult(
        roots=roots,
        state_residuals=np.asarray(state_residuals, dtype=np.float64),
        rho=rho,
        dominant_root=dominant_root,
        stable=stable,
        critical=critical,
        stability_code=stability_code,
        stability_status=stability_status,
        transition_reconstruction_relative_error=transition_error,
        physical_vectors=physical_vectors,
    )


def add_laurent_coefficient(
    coefficients: dict[int, np.ndarray], exponent: int, value: np.ndarray
) -> None:
    """同一幂次的所有贡献严格相加，不允许覆盖。"""

    if exponent in coefficients:
        coefficients[exponent] = coefficients[exponent] + value
    else:
        coefficients[exponent] = np.array(value, dtype=np.float64, copy=True)


def build_laurent_and_polynomial(
    bundle: Bundle, l_samples: int, j_samples: int
) -> tuple[dict[int, np.ndarray], list[np.ndarray], int]:
    coefficients: dict[int, np.ndarray] = {}
    add_laurent_coefficient(coefficients, 1, bundle.mass_term)
    add_laurent_coefficient(coefficients, 0, bundle.base_zero)
    add_laurent_coefficient(coefficients, -1, bundle.base_minus_one)
    for channel, delay in enumerate((l_samples, j_samples)):
        add_laurent_coefficient(
            coefficients,
            -delay,
            np.outer(bundle.delay_left[:, channel], bundle.delay_v_zero[channel, :]),
        )
        add_laurent_coefficient(
            coefficients,
            -(delay + 1),
            np.outer(bundle.delay_left[:, channel], bundle.delay_v_minus_one[channel, :]),
        )
    ordered = {
        exponent: np.array(coefficients[exponent], dtype=np.float64, copy=True)
        for exponent in sorted(coefficients)
        if np.any(coefficients[exponent] != 0.0)
    }
    require(ordered, "Laurent系数全为零")
    minimum_exponent = min(ordered)
    maximum_exponent = max(ordered)
    require(maximum_exponent == 1, "Laurent最高幂次不是1")
    clearing_power = max(0, -minimum_exponent)
    degree = maximum_exponent + clearing_power
    polynomial = [
        np.zeros((bundle.dimension, bundle.dimension), dtype=np.float64)
        for _ in range(degree + 1)
    ]
    for exponent, value in ordered.items():
        polynomial[exponent + clearing_power] += value
    require(np.any(polynomial[-1] != 0.0), "清幂多项式首项为零")
    require(np.all(np.isfinite(np.stack(polynomial))), "清幂多项式包含非有限数")
    return ordered, polynomial, clearing_power


def polynomial_eigenpair_residuals(
    polynomial: Sequence[np.ndarray], roots: np.ndarray, physical_vectors: np.ndarray
) -> np.ndarray:
    degree = len(polynomial) - 1
    values = polynomial[degree] @ physical_vectors
    denominator = np.full(
        roots.shape,
        float(np.linalg.norm(polynomial[degree], ord="fro")),
        dtype=np.float64,
    )
    for exponent in range(degree - 1, -1, -1):
        values = values * roots[np.newaxis, :] + polynomial[exponent] @ physical_vectors
        denominator = (
            np.abs(roots) * denominator
            + float(np.linalg.norm(polynomial[exponent], ord="fro"))
        )
    require(np.all(denominator > 0.0) and np.all(np.isfinite(denominator)),
            "清幂多项式残差分母非法")
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
                "证书物理根必须是有限非零根")
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


def point_index_from(group_index: int, l_samples: int, j_samples: int) -> int:
    return group_index * POINTS_PER_GROUP + l_samples * len(J_VALUES) + j_samples


def point_components(point_index: int) -> tuple[int, int, int]:
    group_index, local_index = divmod(point_index, POINTS_PER_GROUP)
    l_samples, j_samples = divmod(local_index, len(J_VALUES))
    return group_index, l_samples, j_samples


def expected_group_root_count(dimension: int) -> int:
    result = sum(
        2 * dimension + l_samples + j_samples
        for l_samples in L_VALUES
        for j_samples in J_VALUES
    )
    require(result > 0, "分块根数非法")
    return result


def shard_path(bundle: Bundle) -> Path:
    return SHARD_ROOT / f"步骤8E_全根分块_{bundle.row['bundle_id']}.npz"


def formal_artifact_paths(bundles: Sequence[Bundle]) -> tuple[Path, ...]:
    return FORMAL_ARTIFACTS + tuple(shard_path(bundle) for bundle in bundles)


def make_point_key(bundle_id: str, l_samples: int, j_samples: int) -> str:
    return f"{bundle_id}__l{l_samples:02d}__j{j_samples:02d}"


def select_boundary_certificate(
    point_rho: np.ndarray, point_stability_code: np.ndarray
) -> dict[int, CertificateReason]:
    """只按冻结邻接/最近规则选点；不读取论文端点或历史掩膜。"""

    require(point_rho.shape == (EXPECTED_POINT_COUNT,), "rho全网格shape不符")
    require(point_stability_code.shape == (EXPECTED_POINT_COUNT,), "分类全网格shape不符")
    selected: dict[int, CertificateReason] = {}

    def reason_for(index: int) -> CertificateReason:
        if index not in selected:
            selected[index] = CertificateReason()
        return selected[index]

    for group_index in range(EXPECTED_GROUP_COUNT):
        start = group_index * POINTS_PER_GROUP
        stop = start + POINTS_PER_GROUP
        rho_grid = point_rho[start:stop].reshape(len(L_VALUES), len(J_VALUES))
        code_grid = point_stability_code[start:stop].reshape(len(L_VALUES), len(J_VALUES))

        # l方向相邻：固定j，比较(l,j)与(l+1,j)。
        for l_samples in range(len(L_VALUES) - 1):
            for j_samples in J_VALUES:
                if code_grid[l_samples, j_samples] != code_grid[l_samples + 1, j_samples]:
                    left = point_index_from(group_index, l_samples, j_samples)
                    right = point_index_from(group_index, l_samples + 1, j_samples)
                    reason_for(left).l_adjacent_change_incident_count += 1
                    reason_for(right).l_adjacent_change_incident_count += 1

        # j方向相邻：固定l，比较(l,j)与(l,j+1)。
        for l_samples in L_VALUES:
            for j_samples in range(len(J_VALUES) - 1):
                if code_grid[l_samples, j_samples] != code_grid[l_samples, j_samples + 1]:
                    lower = point_index_from(group_index, l_samples, j_samples)
                    upper = point_index_from(group_index, l_samples, j_samples + 1)
                    reason_for(lower).j_adjacent_change_incident_count += 1
                    reason_for(upper).j_adjacent_change_incident_count += 1

        # 每个固定l行选择|rho-1|严格最小值；浮点值完全相等时并列全收。
        distance = np.abs(rho_grid - 1.0)
        for l_samples in L_VALUES:
            row_distance = distance[l_samples, :]
            minimum = float(np.min(row_distance))
            for j_samples in np.flatnonzero(row_distance == minimum):
                reason_for(
                    point_index_from(group_index, l_samples, int(j_samples))
                ).l_row_nearest_to_unit = 1

        # 每个固定j列选择|rho-1|严格最小值；浮点值完全相等时并列全收。
        for j_samples in J_VALUES:
            column_distance = distance[:, j_samples]
            minimum = float(np.min(column_distance))
            for l_samples in np.flatnonzero(column_distance == minimum):
                reason_for(
                    point_index_from(group_index, int(l_samples), j_samples)
                ).j_column_nearest_to_unit = 1

    require(selected, "自动边界证书为空")
    require(all(reason.reason_count > 0 for reason in selected.values()), "证书存在无理由点")
    return selected


def write_deterministic_npz(path: Path, payload: Mapping[str, np.ndarray]) -> None:
    """固定键排序、ZIP时间戳和权限，使用无压缩扁平NPZ保证逐字节复算。"""

    with path.open("wb") as raw_stream:
        with zipfile.ZipFile(raw_stream, mode="w", compression=zipfile.ZIP_STORED) as archive:
            for key in sorted(payload):
                buffer = io.BytesIO()
                np.save(buffer, np.asarray(payload[key]), allow_pickle=False)
                info = zipfile.ZipInfo(
                    filename=f"{key}.npy", date_time=(1980, 1, 1, 0, 0, 0)
                )
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o600 << 16
                info.create_system = 3
                archive.writestr(info, buffer.getvalue())


def write_group_root_shard(
    bundle: Bundle,
    group_index: int,
    root_offsets: np.ndarray,
    physical_roots: np.ndarray,
    physical_state_residuals: np.ndarray,
    point_rho: np.ndarray,
    point_dominant_real: np.ndarray,
    point_dominant_imag: np.ndarray,
    point_stable: np.ndarray,
    point_critical: np.ndarray,
    point_stability_code: np.ndarray,
    point_maximum_state_residual: np.ndarray,
    point_transition_error: np.ndarray,
) -> Path:
    """一个模型链—候选一个确定性NPZ，共固定24个分块。"""

    point_start = group_index * POINTS_PER_GROUP
    point_stop = point_start + POINTS_PER_GROUP
    global_root_start = int(root_offsets[point_start])
    global_root_stop = int(root_offsets[point_stop])
    local_offsets = np.asarray(
        root_offsets[point_start : point_stop + 1] - global_root_start,
        dtype=np.int64,
    )
    expected_roots = expected_group_root_count(bundle.dimension)
    require(int(local_offsets[0]) == 0, "分块首offset不是0")
    require(int(local_offsets[-1]) == expected_roots, "分块末offset与解析根数不符")
    require(global_root_stop - global_root_start == expected_roots, "全局分块根区间不闭合")
    local_roots = physical_roots[global_root_start:global_root_stop]
    local_state = physical_state_residuals[global_root_start:global_root_stop]
    require(local_roots.size == expected_roots and local_state.size == expected_roots,
            "分块根/状态残差长度错误")
    payload: dict[str, np.ndarray] = {
        "schema_version": np.asarray([1], dtype=np.int64),
        "group_index": np.asarray([group_index], dtype=np.int64),
        "bundle_id": fixed_unicode([str(bundle.row["bundle_id"])]),
        "division": np.asarray([int(bundle.row["division"])], dtype=np.int64),
        "route": fixed_unicode([str(bundle.row["route"])]),
        "method": fixed_unicode([str(bundle.row["method"])]),
        "dimension": np.asarray([bundle.dimension], dtype=np.int64),
        "candidate_id": fixed_unicode([str(bundle.row["candidate_id"])]),
        "candidate_name": fixed_unicode([str(bundle.row["candidate_name"])]),
        "source_mat_sha256": fixed_unicode([bundle.source_sha256]),
        "grid_shape": np.asarray([len(L_VALUES), len(J_VALUES)], dtype=np.int64),
        "point_global_index": np.arange(point_start, point_stop, dtype=np.int64),
        "point_l_samples": np.repeat(np.asarray(L_VALUES, dtype=np.int64), len(J_VALUES)),
        "point_j_samples": np.tile(np.asarray(J_VALUES, dtype=np.int64), len(L_VALUES)),
        "point_physical_root_count": np.diff(local_offsets).astype(np.int64, copy=False),
        "physical_root_offsets": local_offsets,
        "physical_root_real": local_roots.real,
        "physical_root_imag": local_roots.imag,
        "physical_state_eigenpair_relative_residual": local_state,
        "point_rho": point_rho[point_start:point_stop],
        "point_dominant_root_real": point_dominant_real[point_start:point_stop],
        "point_dominant_root_imag": point_dominant_imag[point_start:point_stop],
        "point_stable": point_stable[point_start:point_stop],
        "point_critical": point_critical[point_start:point_stop],
        "point_stability_code": point_stability_code[point_start:point_stop],
        "point_maximum_state_eigenpair_residual": (
            point_maximum_state_residual[point_start:point_stop]
        ),
        "point_transition_reconstruction_relative_error": (
            point_transition_error[point_start:point_stop]
        ),
        "delay_channel_1_register_scale": np.asarray(
            [bundle.register_scales[0]], dtype=np.float64
        ),
        "delay_channel_2_register_scale": np.asarray(
            [bundle.register_scales[1]], dtype=np.float64
        ),
        "shared_left_factor_relative_error": np.asarray(
            [bundle.shared_left_factor_relative_error], dtype=np.float64
        ),
        "global_root_offset_start": np.asarray([global_root_start], dtype=np.int64),
        "global_root_offset_end": np.asarray([global_root_stop], dtype=np.int64),
        "residual_limit": np.asarray([RESIDUAL_LIMIT], dtype=np.float64),
        "critical_tolerance": np.asarray([CRITICAL_TOLERANCE], dtype=np.float64),
        "grid_order_code": fixed_unicode(["l_0_to_30_then_j_0_to_66"]),
        "physical_root_contract_code": fixed_unicode(
            ["ALL_MINIMAL_AUGMENTED_ROOTS_ORDER_2N_PLUS_L_PLUS_J"]
        ),
    }
    path = shard_path(bundle)
    write_deterministic_npz(path, payload)
    return path


def verify_group_root_shards(
    bundles: Sequence[Bundle], root_offsets: np.ndarray, point_rho: np.ndarray
) -> int:
    """逐分块只读复核键序、offset、全根、状态残差和rho。"""

    total_roots = 0
    for group_index, bundle in enumerate(bundles):
        path = shard_path(bundle)
        require(path.is_file(), f"缺少分块：{path.name}")
        with np.load(path, allow_pickle=False) as data:
            require(data.files == sorted(data.files), f"{path.name} NPZ键未固定排序")
            offsets = np.asarray(data["physical_root_offsets"])
            require(offsets.dtype == np.int64, f"{path.name} offsets不是int64")
            require(offsets.shape == (POINTS_PER_GROUP + 1,), f"{path.name} offsets shape错误")
            require(int(offsets[0]) == 0, f"{path.name}首offset不是0")
            expected_roots = expected_group_root_count(bundle.dimension)
            require(int(offsets[-1]) == expected_roots, f"{path.name}末offset错误")
            require(np.array_equal(np.diff(offsets), np.asarray(data["point_physical_root_count"])),
                    f"{path.name}逐点根数与offset不闭合")
            roots = np.asarray(data["physical_root_real"]) + 1j * np.asarray(
                data["physical_root_imag"]
            )
            state = np.asarray(data["physical_state_eigenpair_relative_residual"])
            require(roots.size == expected_roots and state.size == expected_roots,
                    f"{path.name}全根或状态残差长度错误")
            require(np.all(np.isfinite(roots.real)) and np.all(np.isfinite(roots.imag)),
                    f"{path.name}全根包含NaN/Inf")
            require(np.all(np.isfinite(state)) and float(np.max(state)) <= RESIDUAL_LIMIT,
                    f"{path.name}状态残差失败")
            local_rho = np.empty(POINTS_PER_GROUP, dtype=np.float64)
            for local_index in range(POINTS_PER_GROUP):
                local_rho[local_index] = float(
                    np.max(np.abs(roots[int(offsets[local_index]) : int(offsets[local_index + 1])]))
                )
            point_start = group_index * POINTS_PER_GROUP
            point_stop = point_start + POINTS_PER_GROUP
            require(np.array_equal(local_rho, point_rho[point_start:point_stop]),
                    f"{path.name}由根重算rho与全局逐点值不一致")
            require(np.array_equal(local_rho, np.asarray(data["point_rho"])),
                    f"{path.name}由根重算rho与分块rho不一致")
            global_start = int(np.asarray(data["global_root_offset_start"]).reshape(-1)[0])
            global_stop = int(np.asarray(data["global_root_offset_end"]).reshape(-1)[0])
            require(global_start == int(root_offsets[point_start]), "分块全局根起点错误")
            require(global_stop == int(root_offsets[point_stop]), "分块全局根终点错误")
            total_roots += roots.size
    require(total_roots == EXPECTED_TOTAL_ROOT_COUNT,
            f"只读复核24分块根总数{total_roots}不是3,356,432")
    return total_roots


def verify_point_csv_writeback(
    bundles: Sequence[Bundle],
    root_offsets: np.ndarray,
    point_rho: np.ndarray,
    point_stable: np.ndarray,
    point_critical: np.ndarray,
    point_stability_code: np.ndarray,
) -> int:
    """独立重读49,848行逐点CSV并闭合点键、分组与全局/分块offset。"""

    require(POINT_CSV.is_file(), "逐点CSV未写出")
    seen_keys: set[str] = set()
    group_counts = np.zeros(EXPECTED_GROUP_COUNT, dtype=np.int64)
    row_count = 0
    with POINT_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        require(tuple(reader.fieldnames or ()) == POINT_FIELDS, "逐点CSV字段集合或顺序错误")
        for expected_index, row in enumerate(reader):
            require(expected_index < EXPECTED_POINT_COUNT, "逐点CSV超过49,848行")
            require(int(row["point_index"]) == expected_index, "逐点CSV point_index不连续")
            group_index, l_samples, j_samples = point_components(expected_index)
            bundle = bundles[group_index]
            expected_key = make_point_key(
                str(bundle.row["bundle_id"]), l_samples, j_samples
            )
            require(row["point_key"] == expected_key, "逐点CSV point_key与固定点序不符")
            require(row["point_key"] not in seen_keys, "逐点CSV point_key重复")
            seen_keys.add(row["point_key"])
            require(int(row["group_index"]) == group_index, "逐点CSV group_index错误")
            require(row["bundle_id"] == bundle.row["bundle_id"], "逐点CSV bundle_id错误")
            require(int(row["l_samples"]) == l_samples, "逐点CSV l错误")
            require(int(row["j_samples"]) == j_samples, "逐点CSV j错误")
            global_start = int(root_offsets[expected_index])
            global_stop = int(root_offsets[expected_index + 1])
            group_root_start = int(root_offsets[group_index * POINTS_PER_GROUP])
            require(int(row["physical_root_count"]) == global_stop - global_start,
                    "逐点CSV根数错误")
            require(int(row["root_offset_start"]) == global_start,
                    "逐点CSV全局根起点错误")
            require(int(row["root_offset_end"]) == global_stop,
                    "逐点CSV全局根终点错误")
            require(row["root_shard_name"] == shard_path(bundle).name,
                    "逐点CSV分块名错误")
            require(int(row["shard_root_offset_start"]) == global_start - group_root_start,
                    "逐点CSV分块根起点错误")
            require(int(row["shard_root_offset_end"]) == global_stop - group_root_start,
                    "逐点CSV分块根终点错误")
            require(float(row["rho"]) == float(point_rho[expected_index]),
                    "逐点CSV rho不能float64无损回读")
            require(int(row["stable"]) == int(point_stable[expected_index]),
                    "逐点CSV stable错误")
            require(int(row["critical"]) == int(point_critical[expected_index]),
                    "逐点CSV critical错误")
            require(int(row["stability_code"]) == int(point_stability_code[expected_index]),
                    "逐点CSV stability_code错误")
            require(int(row["overall_pass"]) == 1, "逐点CSV存在未通过点")
            group_counts[group_index] += 1
            row_count += 1
    require(row_count == EXPECTED_POINT_COUNT, f"逐点CSV应为49,848行，实际{row_count}")
    require(len(seen_keys) == EXPECTED_POINT_COUNT, "逐点CSV唯一点键数不是49,848")
    require(np.all(group_counts == POINTS_PER_GROUP), "逐点CSV不是24组各2077行")
    return row_count


def artifact_hashes(paths: Sequence[Path]) -> list[dict[str, Any]]:
    return [
        {
            "artifact_name": path.name,
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in paths
    ]


def clean_paths(paths: Sequence[Path]) -> None:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    for path in paths:
        if path.exists():
            require(path.is_file(), f"输出目标不是文件：{path}")
            path.unlink()


def run_performance_sentinels(
    bundles: Sequence[Bundle], rejection_rows: Sequence[Mapping[str, Any]]
) -> dict[str, Any]:
    require(len(bundles) == EXPECTED_GROUP_COUNT, "性能哨兵必须覆盖24个合格包")
    clean_paths((SENTINEL_CSV, SENTINEL_JSON, SENTINEL_REPORT))
    rows: list[dict[str, Any]] = []
    group_summaries: list[dict[str, Any]] = []
    total_elapsed = 0.0
    total_roots = 0
    maximum_residual = 0.0

    for group_index, bundle in enumerate(bundles):
        group_elapsed = 0.0
        group_roots = 0
        group_maximum = 0.0
        print(
            f"[性能哨兵 {group_index + 1:02d}/{len(bundles):02d}] "
            f"{bundle.row['bundle_id']} n={bundle.dimension}",
            flush=True,
        )
        for sentinel_id, l_samples, j_samples in PERFORMANCE_SENTINELS:
            started = time.perf_counter()
            result = solve_minimal_point(
                bundle,
                l_samples,
                j_samples,
                return_physical_vectors=False,
            )
            elapsed = time.perf_counter() - started
            root_count = int(result.roots.size)
            maximum = float(np.max(result.state_residuals))
            rows.append(
                {
                    "group_index": group_index,
                    "bundle_id": bundle.row["bundle_id"],
                    "division": int(bundle.row["division"]),
                    "route": bundle.row["route"],
                    "method": bundle.row["method"],
                    "dimension": bundle.dimension,
                    "candidate_id": bundle.row["candidate_id"],
                    "sentinel_id": sentinel_id,
                    "l_samples": l_samples,
                    "j_samples": j_samples,
                    "physical_root_count": root_count,
                    "rho": result.rho,
                    "maximum_state_eigenpair_residual": maximum,
                    "elapsed_seconds": elapsed,
                    "overall_pass": 1,
                }
            )
            group_elapsed += elapsed
            group_roots += root_count
            group_maximum = max(group_maximum, maximum)
            print(
                f"  {sentinel_id}({l_samples},{j_samples}) order={root_count} "
                f"rho={result.rho:.12g} residual={maximum:.3e} "
                f"elapsed={elapsed:.4f}s",
                flush=True,
            )
        group_projection = group_elapsed / len(PERFORMANCE_SENTINELS) * POINTS_PER_GROUP
        group_summaries.append(
            {
                "group_index": group_index,
                "bundle_id": bundle.row["bundle_id"],
                "dimension": bundle.dimension,
                "candidate_id": bundle.row["candidate_id"],
                "sentinel_count": len(PERFORMANCE_SENTINELS),
                "sentinel_root_count": group_roots,
                "sentinel_elapsed_seconds": group_elapsed,
                "mean_seconds_per_sentinel": group_elapsed / len(PERFORMANCE_SENTINELS),
                "projected_one_round_seconds_from_group_mean": group_projection,
                "maximum_state_eigenpair_residual": group_maximum,
            }
        )
        total_elapsed += group_elapsed
        total_roots += group_roots
        maximum_residual = max(maximum_residual, group_maximum)

    require(len(rows) == EXPECTED_GROUP_COUNT * len(PERFORMANCE_SENTINELS),
            "性能哨兵不是24组x10点")
    require(total_roots == EXPECTED_SENTINEL_TOTAL_ROOT_COUNT,
            f"性能哨兵解析根总数应为{EXPECTED_SENTINEL_TOTAL_ROOT_COUNT}，实际{total_roots}")
    projected_one_round = sum(
        float(item["projected_one_round_seconds_from_group_mean"])
        for item in group_summaries
    )
    projected_two_round = 2.0 * projected_one_round
    summary = {
        "schema_version": 1,
        "status": "PASS_STEP8E_PYTHON_PERFORMANCE_SENTINELS",
        "scope": "24 eligible groups x 10 frozen sentinels; no full-grid allocation",
        "sentinel_points": [
            {"sentinel_id": sid, "l_samples": l, "j_samples": j}
            for sid, l, j in PERFORMANCE_SENTINELS
        ],
        "eligible_group_count": len(bundles),
        "rejected_before_any_loadmat_or_grid_count": len(rejection_rows),
        "sentinel_result_count": len(rows),
        "sentinel_total_root_count": total_roots,
        "expected_sentinel_total_root_count": EXPECTED_SENTINEL_TOTAL_ROOT_COUNT,
        "sentinel_total_elapsed_seconds": total_elapsed,
        "mean_seconds_per_sentinel": total_elapsed / len(rows),
        "projected_one_round_seconds_from_group_means": projected_one_round,
        "projected_two_round_seconds_from_group_means": projected_two_round,
        "projection_note": "conservative direct projection of each group's fixed 10-sentinel mean; certificate re-solves and artifact I/O are additional",
        "maximum_state_eigenpair_residual": maximum_residual,
        "residual_limit": RESIDUAL_LIMIT,
        "expected_full_grid_point_count": EXPECTED_POINT_COUNT,
        "expected_full_grid_total_root_count": EXPECTED_TOTAL_ROOT_COUNT,
        "solver_source_sha256": sha256_file(SCRIPT_PATH),
        "input_index_sha256": sha256_file(INDEX_PATH),
        "eligible_bundle_fingerprints": [
            {
                "bundle_id": bundle.row["bundle_id"],
                "source_mat_sha256": bundle.source_sha256,
            }
            for bundle in bundles
        ],
        "group_summaries": group_summaries,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "blas_threads": 1,
        },
    }
    write_csv(
        SENTINEL_CSV,
        (
            "group_index",
            "bundle_id",
            "division",
            "route",
            "method",
            "dimension",
            "candidate_id",
            "sentinel_id",
            "l_samples",
            "j_samples",
            "physical_root_count",
            "rho",
            "maximum_state_eigenpair_residual",
            "elapsed_seconds",
            "overall_pass",
        ),
        rows,
    )
    write_json(SENTINEL_JSON, summary)
    lines = [
        "# 步骤8E Python全网格性能哨兵",
        "",
        f"- 结论：`{summary['status']}`。",
        f"- 范围：24个合格模型包，每包10个预先冻结哨兵，共{len(rows)}点。",
        f"- 实测总用时：{total_elapsed:.6f} s；平均：{summary['mean_seconds_per_sentinel']:.6f} s/点。",
        f"- 全网格单轮直接投影：{projected_one_round:.2f} s（{projected_one_round / 60.0:.2f} min）。",
        f"- 两轮直接投影：{projected_two_round:.2f} s（{projected_two_round / 60.0:.2f} min）。",
        "- 投影依据：逐模型包用本包10个冻结哨兵平均秒/点乘以2077点；边界证书复算和工件写入另计。",
        f"- 哨兵物理根总数：{total_roots}；最大状态特征对残差：{maximum_residual:.17g}。",
        f"- R05/R06在任何loadmat或网格分配前拒绝：{len(rejection_rows)}/12。",
        "",
    ]
    SENTINEL_REPORT.write_text("\n".join(lines), encoding="utf-8")
    return summary


def verify_sentinel_prerequisite(bundles: Sequence[Bundle]) -> Mapping[str, Any]:
    require(SENTINEL_JSON.is_file(), "完整两轮前缺少性能哨兵摘要；先运行--mode sentinel")
    summary = json.loads(SENTINEL_JSON.read_text(encoding="utf-8"))
    require(summary.get("status") == "PASS_STEP8E_PYTHON_PERFORMANCE_SENTINELS",
            "性能哨兵摘要未通过")
    require(int(summary.get("eligible_group_count", -1)) == EXPECTED_GROUP_COUNT,
            "性能哨兵未覆盖24个合格包")
    require(int(summary.get("sentinel_result_count", -1))
            == EXPECTED_GROUP_COUNT * len(PERFORMANCE_SENTINELS),
            "性能哨兵未覆盖24组x10点")
    require(int(summary.get("sentinel_total_root_count", -1))
            == EXPECTED_SENTINEL_TOTAL_ROOT_COUNT,
            "性能哨兵根总数不是封签解析值13,232")
    require(float(summary.get("maximum_state_eigenpair_residual", math.inf)) <= RESIDUAL_LIMIT,
            "性能哨兵状态残差超门")
    actual_points = tuple(
        (
            str(item["sentinel_id"]),
            int(item["l_samples"]),
            int(item["j_samples"]),
        )
        for item in summary.get("sentinel_points", [])
    )
    require(actual_points == PERFORMANCE_SENTINELS, "性能哨兵点清单被更改")
    require(summary.get("solver_source_sha256") == sha256_file(SCRIPT_PATH),
            "性能哨兵摘要未绑定当前求解器源码SHA-256")
    require(summary.get("input_index_sha256") == sha256_file(INDEX_PATH),
            "性能哨兵摘要未绑定当前步骤8C索引SHA-256")
    expected_fingerprints = [
        {
            "bundle_id": bundle.row["bundle_id"],
            "source_mat_sha256": bundle.source_sha256,
        }
        for bundle in bundles
    ]
    require(summary.get("eligible_bundle_fingerprints") == expected_fingerprints,
            "性能哨兵摘要未绑定当前24个合格MAT包及固定顺序")
    expected_environment = {
        "python": platform.python_version(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "platform": platform.platform(),
        "blas_threads": 1,
    }
    require(summary.get("environment") == expected_environment,
            "性能哨兵摘要未绑定当前Python/NumPy/SciPy/单线程环境")
    return summary


def rejection_fieldnames() -> tuple[str, ...]:
    return (
        "bundle_id",
        "division",
        "method",
        "dimension",
        "candidate_id",
        "formula_status",
        "paper_grid_eligible",
        "loadmat_called",
        "grid_allocation_started",
        "rejection_stage",
        "rejection_reason",
        "overall_pass",
    )


def execute_full_round(
    bundles: Sequence[Bundle],
    rejection_rows: Sequence[Mapping[str, Any]],
    sentinel_summary: Mapping[str, Any],
) -> dict[str, Any]:
    """执行一轮完整49,848点；所有正式工件不含运行时间。"""

    require(len(bundles) == EXPECTED_GROUP_COUNT, "完整网格必须是24个模型包")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    SHARD_ROOT.mkdir(parents=True, exist_ok=True)
    clean_paths(formal_artifact_paths(bundles))
    write_csv(REJECTION_CSV, rejection_fieldnames(), rejection_rows)

    # 资格门已完整执行、24个合格包已加载后，才允许分配全网格数组。
    point_group_index = np.empty(EXPECTED_POINT_COUNT, dtype=np.int16)
    point_l_samples = np.empty(EXPECTED_POINT_COUNT, dtype=np.int16)
    point_j_samples = np.empty(EXPECTED_POINT_COUNT, dtype=np.int16)
    point_root_count = np.empty(EXPECTED_POINT_COUNT, dtype=np.int64)
    root_offsets = np.zeros(EXPECTED_POINT_COUNT + 1, dtype=np.int64)
    for group_index, bundle in enumerate(bundles):
        for l_samples in L_VALUES:
            for j_samples in J_VALUES:
                point_index = point_index_from(group_index, l_samples, j_samples)
                point_group_index[point_index] = group_index
                point_l_samples[point_index] = l_samples
                point_j_samples[point_index] = j_samples
                point_root_count[point_index] = 2 * bundle.dimension + l_samples + j_samples
    root_offsets[1:] = np.cumsum(point_root_count, dtype=np.int64)
    require(int(root_offsets[-1]) == EXPECTED_TOTAL_ROOT_COUNT,
            f"根总数应为{EXPECTED_TOTAL_ROOT_COUNT}，实际{int(root_offsets[-1])}")

    physical_roots = np.empty(EXPECTED_TOTAL_ROOT_COUNT, dtype=np.complex128)
    physical_state_residuals = np.empty(EXPECTED_TOTAL_ROOT_COUNT, dtype=np.float64)
    point_rho = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_dominant_real = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_dominant_imag = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_stable = np.empty(EXPECTED_POINT_COUNT, dtype=np.uint8)
    point_critical = np.empty(EXPECTED_POINT_COUNT, dtype=np.uint8)
    point_stability_code = np.empty(EXPECTED_POINT_COUNT, dtype=np.int8)
    point_maximum_state_residual = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_transition_error = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_gamma_1 = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_gamma_2 = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    point_factor_error = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)

    written_shards: list[Path] = []
    with POINT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=POINT_FIELDS)
        writer.writeheader()
        for group_index, bundle in enumerate(bundles):
            print(
                f"[全网格 {group_index + 1:02d}/{len(bundles):02d}] "
                f"{bundle.row['bundle_id']} n={bundle.dimension}",
                flush=True,
            )
            for l_samples in L_VALUES:
                for j_samples in J_VALUES:
                    point_index = point_index_from(group_index, l_samples, j_samples)
                    result = solve_minimal_point(
                        bundle,
                        l_samples,
                        j_samples,
                        return_physical_vectors=False,
                    )
                    start = int(root_offsets[point_index])
                    stop = int(root_offsets[point_index + 1])
                    expected_count = stop - start
                    require(result.roots.size == expected_count, "逐点根数与offset不符")
                    physical_roots[start:stop] = result.roots
                    physical_state_residuals[start:stop] = result.state_residuals
                    point_rho[point_index] = result.rho
                    point_dominant_real[point_index] = result.dominant_root.real
                    point_dominant_imag[point_index] = result.dominant_root.imag
                    point_stable[point_index] = result.stable
                    point_critical[point_index] = result.critical
                    point_stability_code[point_index] = result.stability_code
                    point_maximum_state_residual[point_index] = float(
                        np.max(result.state_residuals)
                    )
                    point_transition_error[point_index] = (
                        result.transition_reconstruction_relative_error
                    )
                    point_gamma_1[point_index] = bundle.register_scales[0]
                    point_gamma_2[point_index] = bundle.register_scales[1]
                    point_factor_error[point_index] = (
                        bundle.shared_left_factor_relative_error
                    )
                    row = {
                        "point_index": point_index,
                        "point_key": make_point_key(
                            str(bundle.row["bundle_id"]), l_samples, j_samples
                        ),
                        "group_index": group_index,
                        "bundle_id": bundle.row["bundle_id"],
                        "division": int(bundle.row["division"]),
                        "route": bundle.row["route"],
                        "method": bundle.row["method"],
                        "dimension": bundle.dimension,
                        "candidate_id": bundle.row["candidate_id"],
                        "candidate_name": bundle.row["candidate_name"],
                        "l_samples": l_samples,
                        "j_samples": j_samples,
                        "physical_root_count": expected_count,
                        "root_offset_start": start,
                        "root_offset_end": stop,
                        "root_shard_name": shard_path(bundle).name,
                        "shard_root_offset_start": (
                            start - int(root_offsets[group_index * POINTS_PER_GROUP])
                        ),
                        "shard_root_offset_end": (
                            stop - int(root_offsets[group_index * POINTS_PER_GROUP])
                        ),
                        "rho": result.rho,
                        "dominant_root_real": result.dominant_root.real,
                        "dominant_root_imag": result.dominant_root.imag,
                        "stable": result.stable,
                        "critical": result.critical,
                        "stability_code": result.stability_code,
                        "stability_status": result.stability_status,
                        "delay_channel_1_register_scale": bundle.register_scales[0],
                        "delay_channel_2_register_scale": bundle.register_scales[1],
                        "shared_left_factor_relative_error": (
                            bundle.shared_left_factor_relative_error
                        ),
                        "transition_reconstruction_relative_error": (
                            result.transition_reconstruction_relative_error
                        ),
                        "maximum_state_eigenpair_residual": float(
                            np.max(result.state_residuals)
                        ),
                        "overall_pass": 1,
                    }
                    writer.writerow(
                        {key: csv_value(row.get(key, "")) for key in POINT_FIELDS}
                    )
                if l_samples in (0, 5, 10, 15, 20, 25, 30):
                    completed = point_index_from(group_index, l_samples, J_VALUES[-1]) + 1
                    print(
                        f"  l={l_samples:02d}完成，累计{completed}/{EXPECTED_POINT_COUNT}点",
                        flush=True,
                    )
            written_shards.append(
                write_group_root_shard(
                    bundle,
                    group_index,
                    root_offsets,
                    physical_roots,
                    physical_state_residuals,
                    point_rho,
                    point_dominant_real,
                    point_dominant_imag,
                    point_stable,
                    point_critical,
                    point_stability_code,
                    point_maximum_state_residual,
                    point_transition_error,
                )
            )

    require(len(written_shards) == EXPECTED_GROUP_COUNT, "正式全根NPZ分块不是24个")
    require(len({path.name for path in written_shards}) == EXPECTED_GROUP_COUNT,
            "正式全根NPZ分块文件名不唯一")
    require(all(path.is_file() for path in written_shards), "存在未写出的正式全根NPZ分块")
    expected_shard_paths = {path.resolve() for path in written_shards}
    actual_shard_paths = {
        path.resolve() for path in SHARD_ROOT.iterdir() if path.is_file()
    }
    require(actual_shard_paths == expected_shard_paths,
            "全根分块目录实际文件集合不严格等于24个预期NPZ，存在缺失或历史残留")
    verified_point_csv_count = verify_point_csv_writeback(
        bundles,
        root_offsets,
        point_rho,
        point_stable,
        point_critical,
        point_stability_code,
    )
    require(verified_point_csv_count == EXPECTED_POINT_COUNT, "逐点CSV写回验收失败")
    analytic_group_total = sum(expected_group_root_count(bundle.dimension) for bundle in bundles)
    require(analytic_group_total == EXPECTED_TOTAL_ROOT_COUNT,
            "24分块解析根数之和不是3,356,432")
    verified_shard_root_total = verify_group_root_shards(
        bundles, root_offsets, point_rho
    )
    require(verified_shard_root_total == EXPECTED_TOTAL_ROOT_COUNT,
            "24分块只读复核根数失败")

    require(np.all(np.isfinite(physical_roots.real))
            and np.all(np.isfinite(physical_roots.imag)), "全根数组包含NaN/Inf")
    require(np.all(np.isfinite(physical_state_residuals)), "全根状态残差包含NaN/Inf")
    maximum_state_residual = float(np.max(physical_state_residuals))
    require(maximum_state_residual <= RESIDUAL_LIMIT, "全网格状态残差超门")
    recomputed_rho = np.empty(EXPECTED_POINT_COUNT, dtype=np.float64)
    for point_index in range(EXPECTED_POINT_COUNT):
        start = int(root_offsets[point_index])
        stop = int(root_offsets[point_index + 1])
        recomputed_rho[point_index] = float(np.max(np.abs(physical_roots[start:stop])))
    require(np.array_equal(recomputed_rho, point_rho), "由全根重算rho与逐点rho不完全一致")

    certificate_reasons = select_boundary_certificate(point_rho, point_stability_code)
    certificate_point_indices = np.asarray(sorted(certificate_reasons), dtype=np.int64)
    certificate_root_offsets = np.zeros(certificate_point_indices.size + 1, dtype=np.int64)
    certificate_root_counts = point_root_count[certificate_point_indices]
    certificate_root_offsets[1:] = np.cumsum(certificate_root_counts, dtype=np.int64)
    certificate_state_residuals = np.empty(
        int(certificate_root_offsets[-1]), dtype=np.float64
    )
    certificate_laurent_residuals = np.empty(
        int(certificate_root_offsets[-1]), dtype=np.float64
    )
    certificate_polynomial_residuals = np.empty(
        int(certificate_root_offsets[-1]), dtype=np.float64
    )
    certificate_maximum_laurent = np.empty(
        certificate_point_indices.size, dtype=np.float64
    )
    certificate_maximum_state = np.empty(
        certificate_point_indices.size, dtype=np.float64
    )
    certificate_maximum_polynomial = np.empty(
        certificate_point_indices.size, dtype=np.float64
    )
    certificate_rows: list[dict[str, Any]] = []

    print(
        f"[边界证书] 自动规则选中{certificate_point_indices.size}点，开始全根公式回代",
        flush=True,
    )
    last_group_index = -1
    for certificate_index, raw_point_index in enumerate(certificate_point_indices):
        point_index = int(raw_point_index)
        group_index, l_samples, j_samples = point_components(point_index)
        bundle = bundles[group_index]
        if group_index != last_group_index:
            print(
                f"  [证书 {group_index + 1:02d}/{len(bundles):02d}] "
                f"{bundle.row['bundle_id']}",
                flush=True,
            )
            last_group_index = group_index
        result = solve_minimal_point(
            bundle,
            l_samples,
            j_samples,
            return_physical_vectors=True,
        )
        global_start = int(root_offsets[point_index])
        global_stop = int(root_offsets[point_index + 1])
        require(np.array_equal(result.roots, physical_roots[global_start:global_stop]),
                "证书复算根与全网格主根不是逐字节同一序列")
        require(
            np.array_equal(
                result.state_residuals,
                physical_state_residuals[global_start:global_stop],
            ),
            "证书复算状态残差与全网格主状态残差不是逐字节同一序列",
        )
        require(result.physical_vectors is not None, "证书复算未返回物理向量")
        laurent, polynomial, _ = build_laurent_and_polynomial(
            bundle, l_samples, j_samples
        )
        laurent_residuals = laurent_eigenpair_residuals(
            laurent, result.roots, result.physical_vectors
        )
        polynomial_residuals = polynomial_eigenpair_residuals(
            polynomial, result.roots, result.physical_vectors
        )
        require(np.all(np.isfinite(laurent_residuals)), "证书Laurent残差包含NaN/Inf")
        require(np.all(np.isfinite(polynomial_residuals)), "证书多项式残差包含NaN/Inf")
        maximum_laurent = float(np.max(laurent_residuals))
        maximum_polynomial = float(np.max(polynomial_residuals))
        require(maximum_laurent <= RESIDUAL_LIMIT,
                f"证书Laurent残差{maximum_laurent:.17g}超门")
        require(maximum_polynomial <= RESIDUAL_LIMIT,
                f"证书清幂残差{maximum_polynomial:.17g}超门")
        cert_start = int(certificate_root_offsets[certificate_index])
        cert_stop = int(certificate_root_offsets[certificate_index + 1])
        certificate_state_residuals[cert_start:cert_stop] = result.state_residuals
        certificate_laurent_residuals[cert_start:cert_stop] = laurent_residuals
        certificate_polynomial_residuals[cert_start:cert_stop] = polynomial_residuals
        maximum_state = float(np.max(result.state_residuals))
        require(maximum_state <= RESIDUAL_LIMIT, "证书状态残差超门")
        certificate_maximum_state[certificate_index] = maximum_state
        certificate_maximum_laurent[certificate_index] = maximum_laurent
        certificate_maximum_polynomial[certificate_index] = maximum_polynomial
        reason = certificate_reasons[point_index]
        status = "CRITICAL" if point_critical[point_index] else (
            "STABLE" if point_stable[point_index] else "UNSTABLE"
        )
        certificate_rows.append(
            {
                "certificate_index": certificate_index,
                "certificate_key": make_point_key(
                    str(bundle.row["bundle_id"]), l_samples, j_samples
                ),
                "point_index": point_index,
                "bundle_id": bundle.row["bundle_id"],
                "division": int(bundle.row["division"]),
                "route": bundle.row["route"],
                "method": bundle.row["method"],
                "dimension": bundle.dimension,
                "candidate_id": bundle.row["candidate_id"],
                "l_samples": l_samples,
                "j_samples": j_samples,
                "rho": point_rho[point_index],
                "stable": point_stable[point_index],
                "critical": point_critical[point_index],
                "stability_code": point_stability_code[point_index],
                "stability_status": status,
                "l_adjacent_change_incident_count": (
                    reason.l_adjacent_change_incident_count
                ),
                "j_adjacent_change_incident_count": (
                    reason.j_adjacent_change_incident_count
                ),
                "l_row_nearest_to_unit": reason.l_row_nearest_to_unit,
                "j_column_nearest_to_unit": reason.j_column_nearest_to_unit,
                "reason_count": reason.reason_count,
                "physical_root_count": global_stop - global_start,
                "global_root_offset_start": global_start,
                "global_root_offset_end": global_stop,
                "root_shard_name": shard_path(bundle).name,
                "shard_root_offset_start": (
                    global_start - int(root_offsets[group_index * POINTS_PER_GROUP])
                ),
                "shard_root_offset_end": (
                    global_stop - int(root_offsets[group_index * POINTS_PER_GROUP])
                ),
                "certificate_root_offset_start": cert_start,
                "certificate_root_offset_end": cert_stop,
                "maximum_state_eigenpair_residual": maximum_state,
                "maximum_laurent_relative_residual": maximum_laurent,
                "maximum_polynomial_relative_residual": maximum_polynomial,
                "overall_pass": 1,
            }
        )

    write_csv(CERTIFICATE_CSV, CERTIFICATE_FIELDS, certificate_rows)
    maximum_certificate_state_residual = float(np.max(certificate_state_residuals))
    maximum_laurent_residual = float(np.max(certificate_laurent_residuals))
    maximum_polynomial_residual = float(np.max(certificate_polynomial_residuals))
    require(maximum_certificate_state_residual <= RESIDUAL_LIMIT, "证书状态全根残差超门")
    require(maximum_laurent_residual <= RESIDUAL_LIMIT, "证书Laurent全根残差超门")
    require(maximum_polynomial_residual <= RESIDUAL_LIMIT, "证书清幂全根残差超门")

    certificate_reason_l_change = np.asarray(
        [
            certificate_reasons[int(index)].l_adjacent_change_incident_count
            for index in certificate_point_indices
        ],
        dtype=np.int16,
    )
    certificate_reason_j_change = np.asarray(
        [
            certificate_reasons[int(index)].j_adjacent_change_incident_count
            for index in certificate_point_indices
        ],
        dtype=np.int16,
    )
    certificate_reason_l_nearest = np.asarray(
        [certificate_reasons[int(index)].l_row_nearest_to_unit for index in certificate_point_indices],
        dtype=np.uint8,
    )
    certificate_reason_j_nearest = np.asarray(
        [certificate_reasons[int(index)].j_column_nearest_to_unit for index in certificate_point_indices],
        dtype=np.uint8,
    )

    payload: dict[str, np.ndarray] = {
        "schema_version": np.asarray([1], dtype=np.int64),
        "grid_l_values": np.asarray(L_VALUES, dtype=np.int64),
        "grid_j_values": np.asarray(J_VALUES, dtype=np.int64),
        "group_bundle_id": fixed_unicode([str(bundle.row["bundle_id"]) for bundle in bundles]),
        "group_division": np.asarray([int(bundle.row["division"]) for bundle in bundles], dtype=np.int64),
        "group_route": fixed_unicode([str(bundle.row["route"]) for bundle in bundles]),
        "group_method": fixed_unicode([str(bundle.row["method"]) for bundle in bundles]),
        "group_dimension": np.asarray([bundle.dimension for bundle in bundles], dtype=np.int64),
        "group_candidate_id": fixed_unicode([str(bundle.row["candidate_id"]) for bundle in bundles]),
        "group_candidate_name": fixed_unicode([str(bundle.row["candidate_name"]) for bundle in bundles]),
        "group_source_mat_sha256": fixed_unicode([bundle.source_sha256 for bundle in bundles]),
        "group_root_shard_name": fixed_unicode([shard_path(bundle).name for bundle in bundles]),
        "group_global_root_offsets": np.asarray(
            [
                root_offsets[group_index * POINTS_PER_GROUP]
                for group_index in range(EXPECTED_GROUP_COUNT + 1)
            ],
            dtype=np.int64,
        ),
        "group_delay_channel_1_register_scale": np.asarray(
            [bundle.register_scales[0] for bundle in bundles], dtype=np.float64
        ),
        "group_delay_channel_2_register_scale": np.asarray(
            [bundle.register_scales[1] for bundle in bundles], dtype=np.float64
        ),
        "group_shared_left_factor_relative_error": np.asarray(
            [bundle.shared_left_factor_relative_error for bundle in bundles], dtype=np.float64
        ),
        "point_group_index": point_group_index,
        "point_l_samples": point_l_samples,
        "point_j_samples": point_j_samples,
        "point_physical_root_count": point_root_count,
        "physical_root_offsets": root_offsets,
        "point_rho": point_rho,
        "point_dominant_root_real": point_dominant_real,
        "point_dominant_root_imag": point_dominant_imag,
        "point_stable": point_stable,
        "point_critical": point_critical,
        "point_stability_code": point_stability_code,
        "point_delay_channel_1_register_scale": point_gamma_1,
        "point_delay_channel_2_register_scale": point_gamma_2,
        "point_shared_left_factor_relative_error": point_factor_error,
        "point_transition_reconstruction_relative_error": point_transition_error,
        "point_maximum_state_eigenpair_residual": point_maximum_state_residual,
        "point_overall_pass": np.ones(EXPECTED_POINT_COUNT, dtype=np.uint8),
        "certificate_point_indices": certificate_point_indices,
        "certificate_root_offsets": certificate_root_offsets,
        "certificate_state_eigenpair_relative_residual": certificate_state_residuals,
        "certificate_laurent_relative_residual": certificate_laurent_residuals,
        "certificate_polynomial_relative_residual": certificate_polynomial_residuals,
        "certificate_maximum_state_eigenpair_residual": certificate_maximum_state,
        "certificate_maximum_laurent_relative_residual": certificate_maximum_laurent,
        "certificate_maximum_polynomial_relative_residual": certificate_maximum_polynomial,
        "certificate_l_adjacent_change_incident_count": certificate_reason_l_change,
        "certificate_j_adjacent_change_incident_count": certificate_reason_j_change,
        "certificate_l_row_nearest_to_unit": certificate_reason_l_nearest,
        "certificate_j_column_nearest_to_unit": certificate_reason_j_nearest,
        "residual_limit": np.asarray([RESIDUAL_LIMIT], dtype=np.float64),
        "critical_tolerance": np.asarray([CRITICAL_TOLERANCE], dtype=np.float64),
        "expected_total_root_count": np.asarray([EXPECTED_TOTAL_ROOT_COUNT], dtype=np.int64),
        "grid_order_code": fixed_unicode(
            ["group_then_l_0_to_30_then_j_0_to_66"]
        ),
        "physical_root_contract_code": fixed_unicode(
            ["ALL_MINIMAL_AUGMENTED_ROOTS_ORDER_2N_PLUS_L_PLUS_J"]
        ),
        "certificate_selection_code": fixed_unicode(
            ["ALL_ADJACENT_CLASS_CHANGE_ENDPOINTS_PLUS_EXACT_ROW_COLUMN_MIN_ABS_RHO_MINUS_1"]
        ),
    }
    write_deterministic_npz(ROOT_NPZ, payload)

    with np.load(ROOT_NPZ, allow_pickle=False) as index_data:
        require(index_data.files == sorted(index_data.files), "全局索引NPZ键未固定排序")
        stored_offsets = np.asarray(index_data["physical_root_offsets"])
        require(stored_offsets.dtype == np.int64, "全局索引offsets不是int64")
        require(np.array_equal(stored_offsets, root_offsets), "全局索引offsets写回不一致")
        require(int(stored_offsets[-1]) == EXPECTED_TOTAL_ROOT_COUNT,
                "全局索引末offset不是3,356,432")
        stored_certificate_offsets = np.asarray(index_data["certificate_root_offsets"])
        require(stored_certificate_offsets.dtype == np.int64, "证书offsets不是int64")
        require(np.array_equal(stored_certificate_offsets, certificate_root_offsets),
                "证书offsets写回不一致")
        for key in (
            "certificate_state_eigenpair_relative_residual",
            "certificate_laurent_relative_residual",
            "certificate_polynomial_relative_residual",
        ):
            values = np.asarray(index_data[key])
            require(values.size == int(certificate_root_offsets[-1]),
                    f"{key}长度与证书offset不符")
            require(np.all(np.isfinite(values)) and float(np.max(values)) <= RESIDUAL_LIMIT,
                    f"{key}只读复核失败")

    certificate_membership = np.zeros(EXPECTED_POINT_COUNT, dtype=np.uint8)
    certificate_membership[certificate_point_indices] = 1
    group_summaries: list[dict[str, Any]] = []
    for group_index, bundle in enumerate(bundles):
        point_start = group_index * POINTS_PER_GROUP
        point_stop = point_start + POINTS_PER_GROUP
        root_start = int(root_offsets[point_start])
        root_stop = int(root_offsets[point_stop])
        group_certificate_mask = (
            (certificate_point_indices >= point_start)
            & (certificate_point_indices < point_stop)
        )
        group_certificate_positions = np.flatnonzero(group_certificate_mask)
        group_summaries.append(
            {
                "group_index": group_index,
                "bundle_id": bundle.row["bundle_id"],
                "division": int(bundle.row["division"]),
                "route": bundle.row["route"],
                "method": bundle.row["method"],
                "dimension": bundle.dimension,
                "candidate_id": bundle.row["candidate_id"],
                "point_count": POINTS_PER_GROUP,
                "physical_root_count": root_stop - root_start,
                "stable_boolean_count": int(np.count_nonzero(point_stable[point_start:point_stop])),
                "critical_boolean_count": int(np.count_nonzero(point_critical[point_start:point_stop])),
                "stable_class_count": int(
                    np.count_nonzero(point_stability_code[point_start:point_stop] == -1)
                ),
                "critical_class_count": int(
                    np.count_nonzero(point_stability_code[point_start:point_stop] == 0)
                ),
                "unstable_class_count": int(
                    np.count_nonzero(point_stability_code[point_start:point_stop] == 1)
                ),
                "minimum_rho": float(np.min(point_rho[point_start:point_stop])),
                "maximum_rho": float(np.max(point_rho[point_start:point_stop])),
                "maximum_state_eigenpair_residual": float(
                    np.max(point_maximum_state_residual[point_start:point_stop])
                ),
                "certificate_point_count": int(group_certificate_positions.size),
                "root_shard_name": shard_path(bundle).name,
                "root_shard_sha256": sha256_file(shard_path(bundle)),
            }
        )

    l_change_edge_count = sum(
        reason.l_adjacent_change_incident_count for reason in certificate_reasons.values()
    ) // 2
    j_change_edge_count = sum(
        reason.j_adjacent_change_incident_count for reason in certificate_reasons.values()
    ) // 2
    l_nearest_selection_count = sum(
        reason.l_row_nearest_to_unit for reason in certificate_reasons.values()
    )
    j_nearest_selection_count = sum(
        reason.j_column_nearest_to_unit for reason in certificate_reasons.values()
    )
    require(l_nearest_selection_count >= EXPECTED_GROUP_COUNT * len(L_VALUES),
            "固定l行最近点选择数不足")
    require(j_nearest_selection_count >= EXPECTED_GROUP_COUNT * len(J_VALUES),
            "固定j列最近点选择数不足")

    summary: dict[str, Any] = {
        "schema_version": 1,
        "status": "PASS_STEP8E_PYTHON_FULLGRID_ROUND",
        "scope": "six model chains x R01-R04 x l=0..30 x j=0..66",
        "solver": "independent gamma-scaled minimal augmented transition matrix of exact order 2*n+l+j",
        "independence": "does not import step8D or any repository generator/solver and does not read paper/history boundary masks",
        "eligible_group_count": len(bundles),
        "rejected_before_any_loadmat_or_grid_count": len(rejection_rows),
        "point_count": EXPECTED_POINT_COUNT,
        "points_per_group": POINTS_PER_GROUP,
        "root_shard_count": len(written_shards),
        "total_physical_root_count": int(root_offsets[-1]),
        "expected_total_physical_root_count": EXPECTED_TOTAL_ROOT_COUNT,
        "stable_boolean_count": int(np.count_nonzero(point_stable)),
        "critical_boolean_count": int(np.count_nonzero(point_critical)),
        "stable_class_count": int(np.count_nonzero(point_stability_code == -1)),
        "critical_class_count": int(np.count_nonzero(point_stability_code == 0)),
        "unstable_class_count": int(np.count_nonzero(point_stability_code == 1)),
        "minimum_rho": float(np.min(point_rho)),
        "maximum_rho": float(np.max(point_rho)),
        "minimum_physical_root_magnitude": float(np.min(np.abs(physical_roots))),
        "maximum_state_eigenpair_residual": maximum_state_residual,
        "maximum_transition_reconstruction_relative_error": float(
            np.max(point_transition_error)
        ),
        "maximum_shared_left_factor_relative_error": float(np.max(point_factor_error)),
        "minimum_register_scale": float(min(np.min(point_gamma_1), np.min(point_gamma_2))),
        "maximum_register_scale": float(max(np.max(point_gamma_1), np.max(point_gamma_2))),
        "certificate_point_count": int(certificate_point_indices.size),
        "certificate_root_count": int(certificate_root_offsets[-1]),
        "certificate_l_adjacent_change_edge_count": int(l_change_edge_count),
        "certificate_j_adjacent_change_edge_count": int(j_change_edge_count),
        "certificate_l_row_nearest_selection_count": int(l_nearest_selection_count),
        "certificate_j_column_nearest_selection_count": int(j_nearest_selection_count),
        "maximum_certificate_state_eigenpair_residual": maximum_certificate_state_residual,
        "maximum_certificate_laurent_relative_residual": maximum_laurent_residual,
        "maximum_certificate_polynomial_relative_residual": maximum_polynomial_residual,
        "residual_limit": RESIDUAL_LIMIT,
        "critical_tolerance": CRITICAL_TOLERANCE,
        "stable_rule": "stable = int(rho < 1.0), independent of critical",
        "critical_rule": "critical = int(abs(rho - 1.0) <= 1e-8), independent of stable",
        "certificate_rule": (
            "both endpoints of every l/j adjacent three-class change; all exact ties for "
            "minimum abs(rho-1) in every fixed-l row and fixed-j column"
        ),
        "certificate_exclusions": "no paper endpoints and no historical mask are read or selected",
        "tie_rule": "exact equality of stored float64 abs(rho-1); all exact ties retained",
        "sentinel_prerequisite_status": sentinel_summary["status"],
        "sentinel_prerequisite_result_count": int(sentinel_summary["sentinel_result_count"]),
        "input_index_sha256": sha256_file(INDEX_PATH),
        "solver_source_sha256": sha256_file(SCRIPT_PATH),
        "group_summaries": group_summaries,
        "environment": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "platform": platform.platform(),
            "blas_threads": 1,
        },
    }
    write_json(SUMMARY_JSON, summary)

    report_lines = [
        "# 步骤8E：Python独立四候选全网格计算报告",
        "",
        f"- 结论：`{summary['status']}`。",
        f"- 全网格：24个合格模型包，每包2077点，共{summary['point_count']}点。",
        f"- 全部物理根：{summary['total_physical_root_count']}，严格等于解析值{EXPECTED_TOTAL_ROOT_COUNT}；保存为24个确定性NPZ分块。",
        f"- 最大逐根状态残差：{summary['maximum_state_eigenpair_residual']:.17g}（门限{RESIDUAL_LIMIT:.1e}）。",
        f"- 自动边界证书：{summary['certificate_point_count']}点、{summary['certificate_root_count']}根。",
        f"- 证书最大逐根残差：状态{summary['maximum_certificate_state_eigenpair_residual']:.17g}，Laurent原式{summary['maximum_certificate_laurent_relative_residual']:.17g}，清幂多项式{summary['maximum_certificate_polynomial_relative_residual']:.17g}。",
        f"- 稳定布尔点数：{summary['stable_boolean_count']}；临界布尔点数：{summary['critical_boolean_count']}；两者按各自公式独立保存。",
        f"- R05/R06在任何loadmat或全网格分配前拒绝：{summary['rejected_before_any_loadmat_or_grid_count']}/12。",
        "",
        "## 自动证书规则",
        "",
        "1. 收录所有l方向和j方向相邻三分类变化边的两个端点。",
        "2. 每个固定l行收录|rho-1|严格最小点；每个固定j列同理；float64值完全相等时并列全收。",
        "3. 不读取论文边界端点、论文历史掩膜或任何既有稳定域边界。",
        "4. 每个证书点保存全部物理根对应的状态、Laurent原式和清幂多项式三类逐根残差。",
        "",
        "## 工件",
        "",
        f"- `{POINT_CSV.name}`：49,848行逐点结果与全局/分块offset。",
        f"- `{SHARD_ROOT.name}/`：24个全根与逐根状态残差确定性NPZ分块。",
        f"- `{ROOT_NPZ.name}`：全局索引、逐点状态和证书三残差。",
        f"- `{CERTIFICATE_CSV.name}`：自动边界证书键、原因与残差摘要。",
        f"- `{REJECTION_CSV.name}`：R05/R06读取与网格分配前拒绝证据。",
        "",
    ]
    REPORT_MD.write_text("\n".join(report_lines), encoding="utf-8")

    log_lines = [
        "STEP8E_PYTHON_DETERMINISTIC_CALCULATION_LOG",
        "STATUS=PASS_STEP8E_PYTHON_FULLGRID_ROUND",
        f"ELIGIBLE_GROUPS={len(bundles)}",
        f"REJECTED_BEFORE_LOAD_OR_GRID={len(rejection_rows)}",
        f"POINTS={EXPECTED_POINT_COUNT}",
        f"ROOT_SHARDS={len(written_shards)}",
        f"PHYSICAL_ROOTS={int(root_offsets[-1])}",
        f"CERTIFICATE_POINTS={int(certificate_point_indices.size)}",
        f"CERTIFICATE_ROOTS={int(certificate_root_offsets[-1])}",
        f"MAX_STATE_RESIDUAL={maximum_state_residual:.17g}",
        f"MAX_CERTIFICATE_LAURENT_RESIDUAL={maximum_laurent_residual:.17g}",
        f"MAX_CERTIFICATE_POLYNOMIAL_RESIDUAL={maximum_polynomial_residual:.17g}",
        "DYNAMIC_TIMING_EXCLUDED=1",
        "PAPER_OR_HISTORY_BOUNDARY_READ=0",
        "OVERALL_PASS=1",
        "",
    ]
    CALCULATION_LOG.write_text("\n".join(log_lines), encoding="utf-8")
    require(all(path.is_file() for path in formal_artifact_paths(bundles)),
            "一轮正式工件未全部写出")
    return summary


def expected_manifest_paths(bundles: Sequence[Bundle]) -> tuple[Path, ...]:
    return (
        (SCRIPT_PATH, INDEX_PATH)
        + tuple(bundle.path for bundle in bundles)
        + (SENTINEL_CSV, SENTINEL_JSON, SENTINEL_REPORT)
        + formal_artifact_paths(bundles)
        + (DETERMINISM_CSV,)
    )


def write_manifest(bundles: Sequence[Bundle]) -> None:
    rows: list[dict[str, Any]] = []

    def append(role: str, path: Path) -> None:
        require(path.is_file(), f"哈希清单目标不存在：{path}")
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
    for bundle in bundles:
        append("eligible_input_bundle", bundle.path)
    for path in (SENTINEL_CSV, SENTINEL_JSON, SENTINEL_REPORT):
        append("performance_sentinel_artifact", path)
    for path in formal_artifact_paths(bundles):
        append("deterministic_formal_artifact", path)
    append("two_round_determinism_evidence", DETERMINISM_CSV)
    expected_paths = expected_manifest_paths(bundles)
    require(len(expected_paths) == 61, "manifest预期路径数不是61")
    require(len(rows) == 61, "manifest待写行数不是61")
    require(len({row["relative_path"] for row in rows}) == 61,
            "manifest待写relative_path不唯一")
    require(
        {str((BOARD_ROOT / row["relative_path"]).resolve()) for row in rows}
        == {str(path.resolve()) for path in expected_paths},
        "manifest待写路径集合与预期61项不闭合",
    )
    write_csv(
        MANIFEST_CSV,
        ("role", "relative_path", "bytes", "sha256"),
        rows,
    )


def run_full_two_round(
    bundles: Sequence[Bundle],
    rejection_rows: Sequence[Mapping[str, Any]],
    sentinel_summary: Mapping[str, Any],
) -> None:
    """完整运行两轮；动态用时只打印到控制台，不进入任何正式工件。"""

    clean_paths((DETERMINISM_CSV, MANIFEST_CSV))
    formal_paths = formal_artifact_paths(bundles)
    require(len(formal_paths) == len(FORMAL_ARTIFACTS) + EXPECTED_GROUP_COUNT,
            "正式确定性工件应为7个全局工件+24个全根分块")
    require(len({path.name for path in formal_paths}) == 31,
            "31个正式确定性工件名称不唯一")

    first_started = time.perf_counter()
    first_summary = execute_full_round(bundles, rejection_rows, sentinel_summary)
    first_elapsed = time.perf_counter() - first_started
    first_hashes = artifact_hashes(formal_paths)
    require(len(first_hashes) == 31, "第一轮正式哈希项不是31")
    print(
        f"[完整第1轮] PASS，实际{first_elapsed:.2f}s；动态用时仅控制台显示",
        flush=True,
    )
    gc.collect()

    second_started = time.perf_counter()
    second_summary = execute_full_round(bundles, rejection_rows, sentinel_summary)
    second_elapsed = time.perf_counter() - second_started
    second_hashes = artifact_hashes(formal_paths)
    require(len(second_hashes) == 31, "第二轮正式哈希项不是31")
    require(first_summary == second_summary, "两轮确定性科学摘要对象不完全相同")

    first_by_name = {str(item["artifact_name"]): item for item in first_hashes}
    second_by_name = {str(item["artifact_name"]): item for item in second_hashes}
    require(first_by_name.keys() == second_by_name.keys(), "两轮正式工件名称集合不同")
    evidence_rows: list[dict[str, Any]] = []
    for path in formal_paths:
        name = path.name
        first = first_by_name[name]
        second = second_by_name[name]
        equal = int(
            int(first["bytes"]) == int(second["bytes"])
            and str(first["sha256"]) == str(second["sha256"])
        )
        require(equal == 1, f"两轮正式工件非逐字节一致：{name}")
        evidence_rows.append(
            {
                "schema_version": 1,
                "artifact_name": name,
                "round1_bytes": int(first["bytes"]),
                "round1_sha256": str(first["sha256"]),
                "round2_bytes": int(second["bytes"]),
                "round2_sha256": str(second["sha256"]),
                "equal": equal,
            }
        )
    write_csv(
        DETERMINISM_CSV,
        (
            "schema_version",
            "artifact_name",
            "round1_bytes",
            "round1_sha256",
            "round2_bytes",
            "round2_sha256",
            "equal",
        ),
        evidence_rows,
    )
    require(len(evidence_rows) == 31 and all(row["equal"] == 1 for row in evidence_rows),
            "31项双轮确定性证据失败")
    write_manifest(bundles)

    with DETERMINISM_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        stored_evidence = list(csv.DictReader(stream))
    require(len(stored_evidence) == 31, "双轮确定性证据写回行数不是31")
    require(all(row["equal"] == "1" for row in stored_evidence),
            "双轮确定性证据写回存在equal!=1")
    with MANIFEST_CSV.open("r", encoding="utf-8-sig", newline="") as stream:
        manifest_rows = list(csv.DictReader(stream))
    require(len(manifest_rows) == 61, "manifest写回行数不是61")
    require(len({row["relative_path"] for row in manifest_rows}) == 61,
            "manifest写回relative_path不唯一")
    require(
        {
            str((BOARD_ROOT / row["relative_path"]).resolve())
            for row in manifest_rows
        }
        == {str(path.resolve()) for path in expected_manifest_paths(bundles)},
        "manifest写回路径集合与预期61项不闭合",
    )
    for row in manifest_rows:
        path = BOARD_ROOT / row["relative_path"]
        require(path.is_file(), f"清单文件不存在：{path}")
        require(int(row["bytes"]) == path.stat().st_size, f"清单字节数不符：{path.name}")
        require(row["sha256"] == sha256_file(path), f"清单SHA-256不符：{path.name}")

    print(
        "PASS_STEP8E_PYTHON_FULLGRID_TWO_ROUNDS: "
        f"round1={first_elapsed:.2f}s round2={second_elapsed:.2f}s，"
        "31/31正式工件逐字节一致，"
        f"points={second_summary['point_count']} roots={second_summary['total_physical_root_count']}",
        flush=True,
    )


def prepare_qualified_inputs() -> tuple[
    list[dict[str, str]], list[dict[str, Any]], list[Bundle]
]:
    """固定顺序：读索引→全索引拒绝R05/R06→才允许loadmat R01--R04。"""

    index_rows = read_index()
    eligible_rows, rejection_rows = gate_entire_index_before_any_load_or_grid(index_rows)
    # 以上资格门完整闭合后，下面才第一次调用loadmat。
    bundles = [load_eligible_bundle(row) for row in eligible_rows]
    require(len(bundles) == EXPECTED_GROUP_COUNT, "合格数值包加载数不是24")
    return index_rows, rejection_rows, bundles


def run() -> int:
    parser = argparse.ArgumentParser(
        description="步骤8E Python独立四候选全网格求解；默认仅运行性能哨兵"
    )
    parser.add_argument(
        "--mode",
        choices=("sentinel", "full-two-round"),
        default="sentinel",
        help="sentinel为默认安全模式；full-two-round须已有通过的哨兵摘要",
    )
    args = parser.parse_args()
    _, rejection_rows, bundles = prepare_qualified_inputs()
    if args.mode == "sentinel":
        summary = run_performance_sentinels(bundles, rejection_rows)
        print(
            "PASS_STEP8E_PYTHON_PERFORMANCE_SENTINELS: "
            f"{summary['sentinel_result_count']}点，"
            f"{summary['mean_seconds_per_sentinel']:.6f}s/点，"
            f"预计两轮{summary['projected_two_round_seconds_from_group_means']:.2f}s",
            flush=True,
        )
        return 0

    sentinel_summary = verify_sentinel_prerequisite(bundles)
    run_full_two_round(bundles, rejection_rows, sentinel_summary)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except ContractError as exc:
        print(f"FAIL_STEP8E_PYTHON_CONTRACT: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(2)

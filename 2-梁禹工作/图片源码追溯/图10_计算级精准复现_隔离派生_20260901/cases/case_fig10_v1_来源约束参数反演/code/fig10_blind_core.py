#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图10盲算侧最小增广求根核心。

本模块只接收已物化的数值算子包，不解析绘图资产，不读取评估器，
不按运行结果改变合同。数值顺序与板块20 Python 最小增广路线一致。
"""

from __future__ import annotations

import os

# 必须在 NumPy/SciPy 导入前固定 BLAS 线程。
os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import hashlib
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
from scipy.io import loadmat
from scipy.linalg import eig, solve


CORE_SCHEMA_VERSION = "FIG10_BLIND_CORE_V1"
NATIVE_LAYOUT = "MINIMAL_AUGMENTED_CORE_V1"
LEGACY_LAYOUT = "BOARD20_STEP8C_LEGACY_V1"
SUPPORTED_LAYOUTS = (NATIVE_LAYOUT, LEGACY_LAYOUT)
RESIDUAL_LIMIT = 1.0e-8
FACTOR_LIMIT = 1.0e-12
TRANSITION_LIMIT = 1.0e-12
CRITICAL_TOLERANCE = 1.0e-8

# 这些标记只用于在任何文件打开之前拒绝绘图/校准资产。
DENIED_OPERATOR_PATH_MARKERS = (
    "plotted",
    "stability_domain",
    "submit_figure",
    "vector_boundary",
    "论文矢量",
    "目标边界",
)
ALLOWED_OPERATOR_SUFFIXES = (".mat", ".npz")


class BlindContractError(RuntimeError):
    """盲算输入、数值闭合或残差门失败。"""


@dataclass(frozen=True)
class BlindBundle:
    route_id: str
    contract_id: str
    path: Path
    source_sha256: str
    operator_layout: str
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
class BlindSolveResult:
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BlindContractError(message)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def assert_operator_input_path(path: Path) -> Path:
    resolved = path.resolve()
    lowered = resolved.as_posix().lower()
    require(
        resolved.suffix.lower() in ALLOWED_OPERATOR_SUFFIXES,
        f"数值算子包后缀必须是 {ALLOWED_OPERATOR_SUFFIXES}：{resolved}",
    )
    for marker in DENIED_OPERATOR_PATH_MARKERS:
        require(marker.lower() not in lowered, f"数值算子包路径命中防火墙标记：{marker}")
    return resolved


def scalar_float(value: Any, name: str) -> float:
    array = np.asarray(value)
    require(array.size == 1, f"{name}必须是标量，实际 shape={array.shape}")
    result = float(array.reshape(-1)[0])
    require(math.isfinite(result), f"{name}必须是有限数")
    return result


def scalar_int(value: Any, name: str) -> int:
    result = scalar_float(value, name)
    rounded = int(round(result))
    require(result == rounded, f"{name}={result} 不是整数")
    return rounded


def matrix_float(value: Any, name: str, shape: tuple[int, int]) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    require(result.shape == shape, f"{name} shape={result.shape}，预期 {shape}")
    require(np.all(np.isfinite(result)), f"{name}包含非有限数")
    return np.ascontiguousarray(result)


def vector_float(value: Any, name: str, length: int) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64).reshape(-1)
    require(result.shape == (length,), f"{name} shape={result.shape}，预期 ({length},)")
    require(np.all(np.isfinite(result)), f"{name}包含非有限数")
    return np.ascontiguousarray(result)


def relative_error(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected, ord="fro")), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected, ord="fro") / denominator)


def load_array_mapping(path: Path) -> dict[str, Any]:
    if path.suffix.lower() == ".mat":
        return loadmat(path, squeeze_me=True, struct_as_record=False)
    with np.load(path, allow_pickle=False) as archive:
        return {name: np.array(archive[name], copy=True) for name in archive.files}


def _validate_identity(data: Mapping[str, Any], metadata: Mapping[str, Any], dimension: int) -> None:
    if "route_dimension" in data:
        require(
            scalar_int(data["route_dimension"], "route_dimension") == dimension,
            "算子包 route_dimension 与清单不一致",
        )
    if "dimension" in data:
        require(
            scalar_int(data["dimension"], "dimension") == dimension,
            "算子包 dimension 与清单不一致",
        )
    optional_pairs = (
        ("division", "division"),
        ("candidate_index", "candidate_index"),
    )
    for data_key, metadata_key in optional_pairs:
        if data_key in data and metadata_key in metadata:
            require(
                scalar_int(data[data_key], data_key) == int(metadata[metadata_key]),
                f"算子包 {data_key} 与清单不一致",
            )


def _load_native(
    data: Mapping[str, Any], metadata: Mapping[str, Any], path: Path, source_hash: str
) -> BlindBundle:
    n = int(metadata["dimension"])
    _validate_identity(data, metadata, n)
    dt = scalar_float(data["dt"], "dt")
    require(dt > 0.0, "dt必须大于0")
    mass_term = matrix_float(data["mass_term"], "mass_term", (n, n))
    base_zero = matrix_float(data["base_zero"], "base_zero", (n, n))
    base_minus_one = matrix_float(data["base_minus_one"], "base_minus_one", (n, n))
    delay_left = matrix_float(data["delay_left"], "delay_left", (n, 2))
    delay_v_zero = matrix_float(data["delay_v_zero"], "delay_v_zero", (2, n))
    delay_v_minus_one = matrix_float(
        data["delay_v_minus_one"], "delay_v_minus_one", (2, n)
    )
    register_scales = vector_float(data["register_scales"], "register_scales", 2)
    require(np.all(register_scales > 0.0), "register_scales必须严格为正")
    require(np.linalg.matrix_rank(mass_term) == n, "mass_term不满秩")
    return BlindBundle(
        route_id=str(metadata["route_id"]),
        contract_id=str(metadata["contract_id"]),
        path=path,
        source_sha256=source_hash,
        operator_layout=NATIVE_LAYOUT,
        dimension=n,
        dt=dt,
        mass_term=mass_term,
        base_zero=base_zero,
        base_minus_one=base_minus_one,
        delay_left=delay_left,
        delay_v_zero=delay_v_zero,
        delay_v_minus_one=delay_v_minus_one,
        register_scales=register_scales,
        shared_left_factor_relative_error=float(
            scalar_float(data.get("shared_left_factor_relative_error", 0.0),
                         "shared_left_factor_relative_error")
        ),
    )


def _load_legacy(
    data: Mapping[str, Any], metadata: Mapping[str, Any], path: Path, source_hash: str
) -> BlindBundle:
    n = int(metadata["dimension"])
    _validate_identity(data, metadata, n)
    for gate_name in ("formula_valid_code", "paper_grid_eligible_code"):
        if gate_name in data:
            require(scalar_float(data[gate_name], gate_name) == 1.0, f"{gate_name}不是1")
    require(
        scalar_float(data.get("feedback_placement_code", math.nan),
                     "feedback_placement_code") == 1.0,
        "旧布局只支持已冻结的 H 外反馈算子包",
    )
    dt = scalar_float(data["dt"], "dt")
    require(dt > 0.0, "dt必须大于0")
    integration_mass_operator = matrix_float(
        data["integration_mass_operator"], "integration_mass_operator", (n, n)
    )
    c1 = matrix_float(data["C1"], "C1", (n, n))
    k1 = matrix_float(data["K1"], "K1", (n, n))
    delay_c_left = matrix_float(data["delay_C_left_factor"], "delay_C_left_factor", (n, 2))
    delay_c_right = matrix_float(
        data["delay_C_right_factor"], "delay_C_right_factor", (2, n)
    )
    delay_k_left = matrix_float(data["delay_K_left_factor"], "delay_K_left_factor", (n, 2))
    delay_k_right = matrix_float(
        data["delay_K_right_factor"], "delay_K_right_factor", (2, n)
    )
    feedback_c = matrix_float(data["feedback_C"], "feedback_C", (n, n))
    feedback_k = matrix_float(data["feedback_K"], "feedback_K", (n, n))

    c2_rebuilt = delay_c_left @ delay_c_right
    k2_rebuilt = delay_k_left @ delay_k_right
    if "C2_zero_delay" in data:
        require(
            relative_error(c2_rebuilt, matrix_float(data["C2_zero_delay"], "C2_zero_delay", (n, n)))
            <= FACTOR_LIMIT,
            "时滞阻尼低秩分解不闭合",
        )
    if "K2_zero_delay" in data:
        require(
            relative_error(k2_rebuilt, matrix_float(data["K2_zero_delay"], "K2_zero_delay", (n, n)))
            <= FACTOR_LIMIT,
            "时滞刚度低秩分解不闭合",
        )
    if "C" in data:
        require(
            relative_error(c1 + c2_rebuilt, matrix_float(data["C"], "C", (n, n)))
            <= FACTOR_LIMIT,
            "C1+C2零时滞不闭合",
        )
    if "K" in data:
        require(
            relative_error(k1 + k2_rebuilt, matrix_float(data["K"], "K", (n, n)))
            <= FACTOR_LIMIT,
            "K1+K2零时滞不闭合",
        )

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
        require(error <= FACTOR_LIMIT, f"通道{channel + 1}未共享左向量")
        delay_left[:, channel] = c_left
        v_zero[channel, :] = delay_c_right[channel, :] / dt + delay_k_right[channel, :]
        v_minus_one[channel, :] = -delay_c_right[channel, :] / dt
        register_scales[channel] = max(
            float(np.linalg.norm(v_zero[channel, :], 2)),
            float(np.linalg.norm(v_minus_one[channel, :], 2)),
            np.finfo(float).eps,
        )

    mass_term = integration_mass_operator / (dt * dt)
    require(np.linalg.matrix_rank(mass_term) == n, "质量推进块不满秩")
    base_zero = -2.0 * mass_term + c1 / dt + k1 + feedback_c / dt + feedback_k
    base_minus_one = mass_term - c1 / dt - feedback_c / dt
    return BlindBundle(
        route_id=str(metadata["route_id"]),
        contract_id=str(metadata["contract_id"]),
        path=path,
        source_sha256=source_hash,
        operator_layout=LEGACY_LAYOUT,
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


def load_blind_bundle(path: Path, metadata: Mapping[str, Any]) -> BlindBundle:
    for key in (
        "route_id",
        "contract_id",
        "dimension",
        "operator_layout",
        "bundle_sha256",
    ):
        require(key in metadata, f"路线清单缺少 {key}")
    layout = str(metadata["operator_layout"])
    require(layout in SUPPORTED_LAYOUTS, f"不支持的 operator_layout={layout}")
    dimension = int(metadata["dimension"])
    require(dimension > 0, "dimension必须为正整数")
    resolved = assert_operator_input_path(path)
    require(resolved.is_file(), f"数值算子包不存在：{resolved}")
    actual_hash = sha256_file(resolved)
    expected_hash = str(metadata["bundle_sha256"]).upper()
    require(actual_hash == expected_hash, f"数值算子包 SHA-256 不符：{resolved}")
    data = load_array_mapping(resolved)
    if layout == NATIVE_LAYOUT:
        return _load_native(data, metadata, resolved, actual_hash)
    return _load_legacy(data, metadata, resolved, actual_hash)


def build_minimal_augmented_current(
    bundle: BlindBundle, l_samples: int, j_samples: int
) -> np.ndarray:
    require(isinstance(l_samples, int) and l_samples >= 0, "l_samples必须是非负整数")
    require(isinstance(j_samples, int) and j_samples >= 0, "j_samples必须是非负整数")
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
        require(gamma > 0.0 and math.isfinite(gamma), f"通道{channel + 1} gamma非法")
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
    require(offset == state_order, "最小增广索引与解析阶数不符")
    require(np.all(np.isfinite(current)), "最小增广矩阵包含非有限数")
    return current


def solve_minimal_point(
    bundle: BlindBundle,
    l_samples: int,
    j_samples: int,
    *,
    return_physical_vectors: bool = False,
) -> BlindSolveResult:
    n = bundle.dimension
    expected_order = 2 * n + l_samples + j_samples
    current = build_minimal_augmented_current(bundle, l_samples, j_samples)
    require(current.shape == (expected_order, expected_order), "最小增广阶数错误")

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
    require(
        transition_error <= TRANSITION_LIMIT,
        f"B*T-A重构误差 {transition_error:.17g} 超过 {TRANSITION_LIMIT:.1e}",
    )

    roots, eigenvectors = eig(
        transition,
        left=False,
        right=True,
        overwrite_a=True,
        check_finite=False,
    )
    require(roots.size == expected_order, "物理根数不等于 2n+l+j")
    require(np.all(np.isfinite(roots.real)) and np.all(np.isfinite(roots.imag)), "物理根非有限")
    order_index = np.lexsort((roots.imag, roots.real, np.abs(roots)))
    roots = np.asarray(roots[order_index], dtype=np.complex128)
    eigenvectors = np.asarray(eigenvectors[:, order_index], dtype=np.complex128)

    vector_norms = np.linalg.norm(eigenvectors, axis=0)
    require(np.all(np.isfinite(vector_norms)) and np.all(vector_norms > 0.0), "特征向量范数非法")
    current_times_vectors = current @ eigenvectors
    following_times_vectors = np.empty_like(eigenvectors)
    following_times_vectors[:n, :] = bundle.mass_term @ eigenvectors[:n, :]
    following_times_vectors[n:, :] = eigenvectors[n:, :]
    following_norm = math.sqrt(
        float(np.linalg.norm(bundle.mass_term, ord="fro")) ** 2 + (expected_order - n)
    )
    denominator = (current_norm + np.abs(roots) * following_norm) * vector_norms
    require(np.all(denominator > 0.0) and np.all(np.isfinite(denominator)), "状态残差分母非法")
    state_residuals = np.linalg.norm(
        current_times_vectors - following_times_vectors * roots[np.newaxis, :], axis=0
    ) / denominator
    require(np.all(np.isfinite(state_residuals)), "状态特征对残差非有限")
    maximum_residual = float(np.max(state_residuals))
    require(
        maximum_residual <= RESIDUAL_LIMIT,
        f"状态特征对残差 {maximum_residual:.17g} 超过 {RESIDUAL_LIMIT:.1e}",
    )

    magnitudes = np.abs(roots)
    dominant_index = int(np.argmax(magnitudes))
    rho = float(magnitudes[dominant_index])
    require(math.isfinite(rho) and rho >= 0.0, "rho非法")
    dominant_root = complex(roots[dominant_index])
    stable = int(rho < 1.0)
    critical = int(abs(rho - 1.0) <= CRITICAL_TOLERANCE)
    if critical:
        stability_code, stability_status = 0, "CRITICAL"
    elif stable:
        stability_code, stability_status = -1, "STABLE"
    else:
        stability_code, stability_status = 1, "UNSTABLE"

    physical_vectors: np.ndarray | None = None
    if return_physical_vectors:
        physical_vectors = np.array(eigenvectors[:n, :], dtype=np.complex128, copy=True)
        physical_norms = np.linalg.norm(physical_vectors, axis=0)
        require(np.all(np.isfinite(physical_norms)) and np.all(physical_norms > 0.0),
                "物理特征向量范数非法")
        physical_vectors /= physical_norms[np.newaxis, :]

    return BlindSolveResult(
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
    if exponent in coefficients:
        coefficients[exponent] = coefficients[exponent] + value
    else:
        coefficients[exponent] = np.array(value, dtype=np.float64, copy=True)


def build_laurent_and_polynomial(
    bundle: BlindBundle, l_samples: int, j_samples: int
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
    require(ordered and max(ordered) == 1, "Laurent系数为空或最高幂不是1")
    clearing_power = max(0, -min(ordered))
    degree = max(ordered) + clearing_power
    polynomial = [
        np.zeros((bundle.dimension, bundle.dimension), dtype=np.float64)
        for _ in range(degree + 1)
    ]
    for exponent, value in ordered.items():
        polynomial[exponent + clearing_power] += value
    require(np.any(polynomial[-1] != 0.0), "清幂多项式首项为零")
    return ordered, polynomial, clearing_power


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
        require(abs(root) > 0.0, "Laurent残差不支持零根")
        log_weights = exponents * math.log(abs(root))
        maximum_log = float(np.max(log_weights))
        scaled_magnitudes = np.exp(log_weights - maximum_log)
        phases = np.exp(1j * exponents * np.angle(root))
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


def expected_root_count(bundle: BlindBundle, l_samples: int, j_samples: int) -> int:
    return 2 * bundle.dimension + l_samples + j_samples


def operator_summary(bundle: BlindBundle) -> dict[str, Any]:
    return {
        "schema_version": CORE_SCHEMA_VERSION,
        "route_id": bundle.route_id,
        "contract_id": bundle.contract_id,
        "operator_layout": bundle.operator_layout,
        "path": str(bundle.path),
        "sha256": bundle.source_sha256,
        "dimension": bundle.dimension,
        "dt": bundle.dt,
        "register_scales": bundle.register_scales.tolist(),
        "shared_left_factor_relative_error": bundle.shared_left_factor_relative_error,
    }

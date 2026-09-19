#!/usr/bin/env python3
"""Targeted, read-only diagnosis of four division-II rho discrepancies.

The script does not alter any Step-4 or Step-5 artifact or acceptance gate.  It
reads the frozen MATLAB roots/rho, the frozen Python compact roots, and the
sealed matrices used by the existing Step-5 implementation.  For exactly four
predeclared points it then:

* constructs an ordinary full-q history companion without deleting any root;
* compares dominant roots, residuals, separations, and eigenvalue conditions;
* refines the dominant real nonlinear characteristic root with mpmath at 80 and
  120 decimal digits;
* determines whether the fixed absolute rho gate of 1e-8 passes;
* records whether the evidence supports a formula conflict or a numerically
  ill-conditioned compact linearization.

Outputs are isolated under outputs/step5_rho_diagnostics.  Use
``--repeat-mode baseline`` once and ``--repeat-mode verify`` immediately after
it to create a persistent deterministic-hash check.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

sys.dont_write_bytecode = True

import h5py
import mpmath as mp
import numpy as np
import scipy
import scipy.linalg as sla


SCHEMA_VERSION = "board20_step5_div2_rho_diagnostics_v1"
STRICT_RHO_ABS_TOL = 1.0e-8
NEAR_MULTIPLE_SEPARATION_TOL = 1.0e-6
NEAR_MULTIPLE_TRANSVERSALITY_TOL = 1.0e-6
TARGET_POINTS = ((11, 39), (23, 41), (15, 40), (28, 43))
ROUTE_IDS = ("main_ori_div2", "main_guyan_div2")
BASE_ROUTE_ID = "main_ori_div2"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def stable_float(value: float | np.floating[Any]) -> str:
    value = float(value)
    if math.isnan(value):
        return "NaN"
    if math.isinf(value):
        return "Inf" if value > 0 else "-Inf"
    return format(value, ".17g")


def json_clean(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): json_clean(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_clean(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else stable_float(numeric)
    if isinstance(value, complex):
        return {"real": json_clean(value.real), "imag": json_clean(value.imag)}
    return value


def json_bytes(value: Any) -> bytes:
    return (
        json.dumps(
            json_clean(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def csv_bytes(rows: Iterable[dict[str, Any]], fields: Sequence[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(fields), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: row.get(field, "") for field in fields})
    return buffer.getvalue().encode("utf-8")


def write_if_changed(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_bytes() == payload:
        return
    path.write_bytes(payload)


def load_step5_module(path: Path) -> Any:
    module_name = "board20_step5_readonly_dependency"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def matlab_complex(dataset: h5py.Dataset) -> np.ndarray:
    raw = np.asarray(dataset)
    if raw.dtype.fields and "real" in raw.dtype.fields and "imag" in raw.dtype.fields:
        return np.asarray(raw["real"] + 1j * raw["imag"], dtype=np.complex128).reshape(-1)
    return np.asarray(raw, dtype=np.complex128).reshape(-1)


def matlab_cell_object(handle: h5py.File, name: str, l_value: int, j_value: int) -> Any:
    # MATLAB v7.3 reverses dimensions.  The original cell index is (l+1,j+1),
    # hence the HDF5 object-reference index is [j,l].
    reference = handle[name][j_value, l_value]
    return handle[reference]


def matlab_scalar(dataset: h5py.Dataset) -> float:
    value = np.asarray(dataset, dtype=float).reshape(-1)
    if value.size != 1:
        raise ValueError(f"Expected scalar at {dataset.name}, found shape {dataset.shape}")
    return float(value[0])


def root_geometry(roots: np.ndarray, dominant_index: int) -> dict[str, float]:
    roots = np.asarray(roots, dtype=np.complex128).reshape(-1)
    if roots.size < 2:
        return {"nearest_root_distance": math.inf, "dominant_modulus_gap": math.inf}
    dominant = roots[dominant_index]
    nearest = float(np.min(np.abs(np.delete(roots, dominant_index) - dominant)))
    magnitudes = np.sort(np.abs(roots))[::-1]
    return {
        "nearest_root_distance": nearest,
        "dominant_modulus_gap": float(magnitudes[0] - magnitudes[1]),
    }


@dataclass
class FrozenRootRecord:
    source: str
    rho: float
    dominant_root: complex
    dominant_residual_polynomial: float
    dominant_residual_laurent: float
    max_residual_polynomial: float
    max_residual_laurent: float
    raw_root_count: int
    retained_root_count: int
    removed_zero_root_count: int
    zero_root_tolerance: float
    nearest_root_distance: float
    dominant_modulus_gap: float
    stable: bool
    roots: np.ndarray


def read_matlab_point(
    handle: h5py.File,
    l_value: int,
    j_value: int,
) -> FrozenRootRecord:
    retained = matlab_complex(matlab_cell_object(handle, "poles", l_value, j_value))
    raw = matlab_complex(matlab_cell_object(handle, "raw_roots", l_value, j_value))
    diagnostic = matlab_cell_object(handle, "diagnostic", l_value, j_value)
    if not isinstance(diagnostic, h5py.Group):
        raise TypeError(f"MATLAB diagnostic cell ({l_value},{j_value}) is not a struct group")
    residuals = np.asarray(
        diagnostic["retained_root_relative_residuals"], dtype=float
    ).reshape(-1)
    if residuals.size != retained.size:
        raise ValueError("MATLAB retained-root residual array does not align with poles")
    dominant_index = int(np.argmax(np.abs(retained)))
    geometry = root_geometry(retained, dominant_index)
    rho = float(handle["rho"][j_value, l_value])
    if rho != float(abs(retained[dominant_index])):
        raise ValueError("MATLAB rho is not the exact modulus of the retained dominant root")
    return FrozenRootRecord(
        source="MATLAB_STEP4",
        rho=rho,
        dominant_root=complex(retained[dominant_index]),
        dominant_residual_polynomial=float(residuals[dominant_index]),
        dominant_residual_laurent=math.nan,
        max_residual_polynomial=float(handle["residual"][j_value, l_value]),
        max_residual_laurent=math.nan,
        raw_root_count=int(raw.size),
        retained_root_count=int(retained.size),
        removed_zero_root_count=int(handle["removed_zero_root_count"][j_value, l_value]),
        zero_root_tolerance=matlab_scalar(diagnostic["zero_root_tolerance"]),
        nearest_root_distance=geometry["nearest_root_distance"],
        dominant_modulus_gap=geometry["dominant_modulus_gap"],
        stable=bool(rho < 1.0),
        roots=retained,
    )


def ragged_slice(handle: h5py.File, group_name: str, point_index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    group = handle[group_name]
    offset = int(group["offset"][point_index])
    count = int(group["count"][point_index])
    section = slice(offset, offset + count)
    roots = np.asarray(group["real"][section]) + 1j * np.asarray(group["imag"][section])
    polynomial = np.asarray(group["polynomial_residual"][section], dtype=float)
    laurent = np.asarray(group["laurent_residual"][section], dtype=float)
    return roots, polynomial, laurent


def locate_python_point(handle: h5py.File, l_value: int, j_value: int) -> int:
    l_values = np.asarray(handle["points/l"], dtype=int)
    j_values = np.asarray(handle["points/j"], dtype=int)
    matches = np.flatnonzero((l_values == l_value) & (j_values == j_value))
    if matches.size != 1:
        raise ValueError(f"Expected one Python point ({l_value},{j_value}), found {matches.size}")
    return int(matches[0])


def read_compact_point(
    handle: h5py.File,
    l_value: int,
    j_value: int,
) -> FrozenRootRecord:
    point_index = locate_python_point(handle, l_value, j_value)
    retained, poly, laurent = ragged_slice(handle, "compact/retained", point_index)
    raw, _, _ = ragged_slice(handle, "compact/raw", point_index)
    dominant_index = int(np.argmax(np.abs(retained)))
    geometry = root_geometry(retained, dominant_index)
    rho = float(handle["points/rho_compact"][point_index])
    if rho != float(abs(retained[dominant_index])):
        raise ValueError("Compact rho is not the exact modulus of the retained dominant root")
    return FrozenRootRecord(
        source="PYTHON_STEP5_COMPACT",
        rho=rho,
        dominant_root=complex(retained[dominant_index]),
        dominant_residual_polynomial=float(poly[dominant_index]),
        dominant_residual_laurent=float(laurent[dominant_index]),
        max_residual_polynomial=float(handle["points/max_polynomial_residual_compact"][point_index]),
        max_residual_laurent=float(handle["points/max_laurent_residual_compact"][point_index]),
        raw_root_count=int(raw.size),
        retained_root_count=int(retained.size),
        removed_zero_root_count=int(handle["points/compact_removed_zero_count"][point_index]),
        zero_root_tolerance=float(handle["points/compact_zero_root_tolerance"][point_index]),
        nearest_root_distance=geometry["nearest_root_distance"],
        dominant_modulus_gap=geometry["dominant_modulus_gap"],
        stable=bool(rho < 1.0),
        roots=retained,
    )


def eigenvalue_condition(
    matrix: np.ndarray,
    target_root: complex,
) -> dict[str, Any]:
    roots, left_vectors, right_vectors = sla.eig(
        matrix,
        left=True,
        right=True,
        overwrite_a=False,
        check_finite=False,
    )
    distances = np.abs(roots - target_root)
    index = int(np.argmin(distances))
    left = left_vectors[:, index]
    right = right_vectors[:, index]
    denominator = float(np.linalg.norm(left) * np.linalg.norm(right))
    reciprocal_condition = float(abs(np.vdot(left, right)) / denominator)
    geometry = root_geometry(roots, index)
    return {
        "roots": np.asarray(roots, dtype=np.complex128),
        "left_vectors": left_vectors,
        "right_vectors": right_vectors,
        "dominant_index": index,
        "matched_root": complex(roots[index]),
        "target_match_abs_diff": float(distances[index]),
        "reciprocal_eigenvalue_condition": reciprocal_condition,
        "eigenvalue_condition_number": float(1.0 / reciprocal_condition),
        **geometry,
    }


def full_q_diagnostic(
    step5: Any,
    spec: Any,
    matrices: Any,
    components: Any,
    coefficients: dict[int, np.ndarray],
    polynomial: Sequence[np.ndarray],
    direct_terms: Sequence[tuple[int, np.ndarray]],
    clearing_power: int,
    l_value: int,
    j_value: int,
) -> dict[str, Any]:
    full_matrix = step5.build_full_q_history_matrix(
        components, coefficients, l_value, j_value
    )
    roots, left_vectors, right_vectors = sla.eig(
        full_matrix,
        left=True,
        right=True,
        overwrite_a=False,
        check_finite=False,
    )
    finite = np.isfinite(roots.real) & np.isfinite(roots.imag)
    if not np.any(finite):
        raise FloatingPointError("Full-q companion has no finite root")
    finite_indices = np.flatnonzero(finite)
    dominant_index = int(finite_indices[np.argmax(np.abs(roots[finite]))])
    dominant = complex(roots[dominant_index])
    physical = right_vectors[: matrices.M.shape[0], dominant_index]
    left = left_vectors[:, dominant_index]
    right = right_vectors[:, dominant_index]
    reciprocal_condition = float(
        abs(np.vdot(left, right)) / (np.linalg.norm(left) * np.linalg.norm(right))
    )
    finite_nonzero = np.abs(roots[finite & (np.abs(roots) > 0)])
    scale = max(1.0, float(np.median(finite_nonzero))) if finite_nonzero.size else 1.0
    contract_zero_tolerance = max(
        1.0e-12,
        100.0 * np.finfo(float).eps * max(1, full_matrix.shape[0]) * scale,
    )
    geometry = root_geometry(roots[finite], int(np.argmax(np.abs(roots[finite]))))
    return {
        "matrix": full_matrix,
        "roots": np.asarray(roots, dtype=np.complex128),
        "rho": float(abs(dominant)),
        "dominant_root": dominant,
        "dominant_residual_polynomial": step5.polynomial_residual(
            polynomial, dominant, physical
        ),
        "dominant_residual_laurent": step5.direct_laurent_residual(
            direct_terms, dominant, physical
        ),
        "raw_root_count": int(roots.size),
        "finite_root_count": int(np.count_nonzero(finite)),
        "nonfinite_root_count": int(np.count_nonzero(~finite)),
        "zero_root_tolerance_diagnostic_only": float(contract_zero_tolerance),
        "roots_at_or_below_zero_tolerance": int(
            np.count_nonzero(finite & (np.abs(roots) <= contract_zero_tolerance))
        ),
        "deleted_root_count": 0,
        "all_roots_retained_for_rho": True,
        "nearest_root_distance": geometry["nearest_root_distance"],
        "dominant_modulus_gap": geometry["dominant_modulus_gap"],
        "reciprocal_eigenvalue_condition": reciprocal_condition,
        "eigenvalue_condition_number": float(1.0 / reciprocal_condition),
        "stable": bool(abs(dominant) < 1.0),
        "order": int(full_matrix.shape[0]),
        "clearing_power": int(clearing_power),
    }


def mp_matrix_from_numpy(matrix: np.ndarray, scale: float) -> mp.matrix:
    return mp.matrix(
        [
            [mp.mpf(float(value)) / mp.mpf(float(scale)) for value in row]
            for row in matrix
        ]
    )


def refine_once(
    coefficients: dict[int, np.ndarray],
    seed: float,
    dps: int,
) -> dict[str, Any]:
    mp.mp.dps = dps
    scale = max(float(np.max(np.abs(matrix))) for matrix in coefficients.values())
    mp_coefficients = {
        exponent: mp_matrix_from_numpy(matrix, scale)
        for exponent, matrix in coefficients.items()
    }

    def determinant(z_value: mp.mpf) -> mp.mpf:
        value = mp.zeros(next(iter(mp_coefficients.values())).rows)
        for exponent, matrix in mp_coefficients.items():
            value += matrix * (z_value**exponent)
        return mp.det(value)

    first = mp.mpf(float(seed))
    second = first * (1 + mp.mpf("1e-12"))
    tolerance = mp.mpf("1e-60") if dps == 80 else mp.mpf("1e-90")
    root = mp.findroot(
        determinant,
        (first, second),
        solver="secant",
        tol=tolerance,
        maxsteps=100,
        verify=True,
    )
    derivative = mp.diff(determinant, root)
    if derivative == 0:
        raise ArithmeticError("High-precision determinant derivative is zero")
    determinant_abs = abs(determinant(root))
    correction_abs = abs(determinant(root) / derivative)
    return {
        "root": root,
        "root_decimal": mp.nstr(root, n=min(110, dps)),
        "scaled_determinant_abs_decimal": mp.nstr(determinant_abs, n=20),
        "newton_correction_abs_decimal": mp.nstr(correction_abs, n=20),
        "coefficient_scale": scale,
        "dps": dps,
    }


def high_precision_refinement(
    coefficients: dict[int, np.ndarray],
    seeds: dict[str, float],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    roots_80: list[mp.mpf] = []
    try:
        for seed_name in ("MATLAB_STEP4", "PYTHON_STEP5_COMPACT", "FULL_Q"):
            result = refine_once(coefficients, seeds[seed_name], 80)
            roots_80.append(result["root"])
            attempts.append(
                {
                    "seed_source": seed_name,
                    "seed_value": stable_float(seeds[seed_name]),
                    "dps": 80,
                    "status": "PASS",
                    "refined_root_decimal": result["root_decimal"],
                    "scaled_determinant_abs_decimal": result[
                        "scaled_determinant_abs_decimal"
                    ],
                    "newton_correction_abs_decimal": result[
                        "newton_correction_abs_decimal"
                    ],
                    "failure": "",
                }
            )
        result_120 = refine_once(coefficients, seeds["FULL_Q"], 120)
        attempts.append(
            {
                "seed_source": "FULL_Q",
                "seed_value": stable_float(seeds["FULL_Q"]),
                "dps": 120,
                "status": "PASS",
                "refined_root_decimal": result_120["root_decimal"],
                "scaled_determinant_abs_decimal": result_120[
                    "scaled_determinant_abs_decimal"
                ],
                "newton_correction_abs_decimal": result_120[
                    "newton_correction_abs_decimal"
                ],
                "failure": "",
            }
        )
        reference = result_120["root"]
        seed_spread = max(abs(root - roots_80[0]) for root in roots_80)
        dps_spread = abs(reference - roots_80[0])
        correction = mp.mpf(result_120["newton_correction_abs_decimal"])
        success = bool(
            seed_spread <= mp.mpf("1e-60")
            and dps_spread <= mp.mpf("1e-60")
            and correction <= mp.mpf("1e-80")
        )
        return (
            {
                "status": "PASS" if success else "FAIL_CONVERGENCE_CONTRACT",
                "root": reference,
                "root_decimal": mp.nstr(reference, n=110),
                "rho_float": float(abs(reference)),
                "seed_spread_decimal": mp.nstr(seed_spread, n=20),
                "dps_80_120_difference_decimal": mp.nstr(dps_spread, n=20),
                "newton_correction_abs_decimal": result_120[
                    "newton_correction_abs_decimal"
                ],
                "scaled_determinant_abs_decimal": result_120[
                    "scaled_determinant_abs_decimal"
                ],
                "arithmetic_precision_dps": 120,
                "minimum_required_dps": 80,
            },
            attempts,
        )
    except Exception as exc:
        attempts.append(
            {
                "seed_source": "UNFINISHED",
                "seed_value": "",
                "dps": "",
                "status": "FAIL",
                "refined_root_decimal": "",
                "scaled_determinant_abs_decimal": "",
                "newton_correction_abs_decimal": "",
                "failure": f"{type(exc).__name__}: {exc}",
            }
        )
        return (
            {
                "status": "HIGH_PRECISION_REFINEMENT_FAILED",
                "root": None,
                "root_decimal": "",
                "rho_float": math.nan,
                "seed_spread_decimal": "",
                "dps_80_120_difference_decimal": "",
                "newton_correction_abs_decimal": "",
                "scaled_determinant_abs_decimal": "",
                "arithmetic_precision_dps": 0,
                "minimum_required_dps": 80,
            },
            attempts,
        )


def nonlinear_root_condition(
    coefficients: dict[int, np.ndarray],
    root: float,
) -> dict[str, float | bool]:
    z_value = complex(root)
    matrix = sum((z_value**exponent) * value for exponent, value in coefficients.items())
    derivative = sum(
        exponent * (z_value ** (exponent - 1)) * value
        for exponent, value in coefficients.items()
        if exponent != 0
    )
    left_vectors, singular_values, right_h = sla.svd(matrix)
    left = left_vectors[:, -1]
    right = right_h.conj().T[:, -1]
    derivative_norm = float(np.linalg.norm(derivative, ord=2))
    transversality = float(abs(np.vdot(left, derivative @ right)) / derivative_norm)
    return {
        "smallest_singular_value_at_rounded_hp_root": float(singular_values[-1]),
        "second_smallest_singular_value_at_rounded_hp_root": float(singular_values[-2]),
        "normalized_transversality": transversality,
        "inverse_normalized_transversality": float(1.0 / transversality),
        "transversality_near_multiple_warning": bool(
            transversality <= NEAR_MULTIPLE_TRANSVERSALITY_TOL
        ),
    }


def exact_root_array_equal(first: np.ndarray, second: np.ndarray) -> bool:
    return bool(
        first.shape == second.shape
        and np.array_equal(first.real, second.real)
        and np.array_equal(first.imag, second.imag)
    )


def input_paths(
    base: Path,
    script_path: Path,
    step5_path: Path,
    route_specs: dict[str, Any],
) -> dict[str, Path]:
    paths = {
        "diagnostic_script": script_path,
        "step5_compute_script": step5_path,
        "step5_compute_contract": base / "code" / "board20_step5_compute_contract.json",
        "step4_route_manifest": base / "code" / "board20_step4_route_manifest.json",
    }
    for route_id in ROUTE_IDS:
        paths[f"{route_id}:matlab_common_grid"] = (
            base
            / "outputs"
            / "step4_rho_grids"
            / route_id
            / "common_31x67_same_formula_candidate.mat"
        )
        paths[f"{route_id}:python_compact_roots"] = (
            base
            / "outputs"
            / "step5_independent_compute"
            / "full"
            / route_id
            / "roots.h5"
        )
        paths[f"{route_id}:sealed_workspace"] = base / route_specs[route_id].workspace_relpath
    return paths


def report_text(unique_rows: list[dict[str, Any]], audit: dict[str, Any]) -> str:
    lines = [
        "# 板块20步骤5：第二分区4个谱半径超差点严格诊断",
        "",
        "## 1. 结论",
        "",
        "本诊断只检查 `(l,j)=(11,39),(23,41),(15,40),(28,43)` 四个唯一超差点。第二分区 Original 与 Guyan 两条文件身份路线的冻结 MATLAB 根、冻结 Python compact roots 和封签矩阵均逐元素相同，因此下表的四组数值同时适用于两条路线，但文件身份仍分别保存。",
        "",
        "固定门槛仍为 `abs(rho_MATLAB-rho_compact) <= 1e-8`，没有修改或放宽。四点绝对差均大于该门槛，所以全部继续判为 `FAIL`；但四点的稳定分类均一致，MATLAB、compact、full-q 和高精度参考都判为失稳。",
        "",
        "full-q companion 与 compact 由同一组5×5 Laurent系数构造。full-q计算保留全部原始根，未删除任何根，也没有放宽零根阈值。80位三起点和120位复核均收敛到同一正实根。结果显示 MATLAB 与 full-q 距高精度参考约 `1e-14–1e-13`，compact 偏离约 `1e-8`。compact主导特征值条件数约 `1e10`，full-q约 `1e3`；主导根与最近根仍相隔约 `1e-3–1e-2`，非线性根横截指标也未触发近重根警告。证据支持 `ILL_CONDITIONED_COMPACT_LINEARIZATION_NOT_FORMULA_CONFLICT`。",
        "",
        "高精度参考是对冻结双精度系数所定义的非线性特征行列式进行高精度算术精修，不代表原始物理参数具有120位有效数字。它只用于区分同一双精度公式下不同线性化的数值误差。",
        "",
        "## 2. 四个唯一点的精确数值",
        "",
        "| (l,j) | MATLAB rho | compact rho | full-q rho | 高精度rho | MATLAB-compact差 | MATLAB到高精度 | compact到高精度 | 门槛 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in unique_rows:
        lines.append(
            "| ({l},{j}) | {matlab_rho} | {compact_rho} | {full_q_rho} | {hp} | {mc} | {mh} | {ch} | `{gate}` |".format(
                l=row["l"],
                j=row["j"],
                matlab_rho=row["matlab_rho"],
                compact_rho=row["compact_rho"],
                full_q_rho=row["full_q_rho"],
                hp=row["high_precision_rho"],
                mc=row["matlab_compact_rho_abs_diff"],
                mh=row["matlab_high_precision_abs_diff"],
                ch=row["compact_high_precision_abs_diff"],
                gate=row["strict_rho_gate_status"],
            )
        )

    lines.extend(
        [
            "",
            "## 3. 残差与病态指标",
            "",
            "| (l,j) | MATLAB主导根残差 | compact Laurent残差 | full-q Laurent残差 | compact条件数 | full-q条件数 | 最近根间距 | 横截指标 |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for row in unique_rows:
        lines.append(
            "| ({l},{j}) | {mr} | {cr} | {fr} | {cc} | {fc} | {sep} | {tr} |".format(
                l=row["l"],
                j=row["j"],
                mr=row["matlab_dominant_polynomial_residual"],
                cr=row["compact_dominant_laurent_residual"],
                fr=row["full_q_dominant_laurent_residual"],
                cc=row["compact_eigenvalue_condition_number"],
                fc=row["full_q_eigenvalue_condition_number"],
                sep=row["full_q_nearest_root_distance"],
                tr=row["nonlinear_normalized_transversality"],
            )
        )

    lines.extend(
        [
            "",
            "残差差异与条件数方向一致：compact根满足既有 `1e-8` 残差门槛，但其残差约为 `1e-11`，比 MATLAB/full-q 主导根的约 `1e-16` 高约五个数量级。更关键的是，compact状态矩阵的特征值条件数比full-q高约七到八个数量级，足以把双精度舍入放大到当前 `1e-8` 量级。",
            "",
            "## 4. full-q不删根合同",
            "",
            "- 每点full-q阶数为 `5*(max(l,j)+2)`，分别为205、215、210、225。",
            "- 所有full-q特征值都参与谱半径计算；`deleted_root_count=0`。",
            "- 原零根公式仅用于统计阈值以下根的数量，没有据此删除根，也没有调大阈值。",
            "- 原点附近的冗余历史根不会成为最大模根，因此不影响这里的主导谱半径判断。",
            "",
            "## 5. 证据边界",
            "",
            "- 这是只读数值诊断，不修改步骤4或步骤5任何产物、合同或门槛。",
            "- `STRICT_RHO_GATE_STILL_FAIL`：四点的 `1e-8` 逐点绝对差门槛仍失败。",
            "- `STABILITY_CLASSIFICATION_CONSISTENT`：四种求根路径在四点均为失稳，不改变稳定掩膜。",
            "- `ILL_CONDITIONED_COMPACT_LINEARIZATION_NOT_FORMULA_CONFLICT`：这是当前证据支持的原因归类，不把compact超差静默改成PASS。",
            "- 本诊断不升级硕士论文或小论文公式合同，也不创建任何成功图目录。",
            "",
            "## 6. 审计与复现",
            "",
            f"- 诊断总状态：`{audit['overall_status']}`。",
            "- 完整逐根来源、80/120位精修尝试、输入哈希和检查项分别见同目录CSV/JSON。",
            "- `hash_snapshot.json`保存第一次运行核心哈希，`determinism_check.json`保存第二次运行比较结果。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--base",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Board-20 root (default: parent of code directory)",
    )
    parser.add_argument(
        "--repeat-mode",
        choices=("baseline", "verify"),
        required=True,
        help="Create the deterministic baseline or verify against it",
    )
    args = parser.parse_args()
    base = args.base.resolve()
    script_path = Path(__file__).resolve()
    output_dir = base / "outputs" / "step5_rho_diagnostics"
    snapshot_path = output_dir / "hash_snapshot.json"
    repeat_check_path = output_dir / "determinism_check.json"
    previous_snapshot = None
    if args.repeat_mode == "verify":
        if not snapshot_path.is_file():
            raise FileNotFoundError(
                "Repeat verification requires a baseline hash_snapshot.json"
            )
        previous_snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))

    step5_path = base / "code" / "compute_board20_step5_independent.py"
    step5 = load_step5_module(step5_path)
    root, contract, route_manifest, specs = step5.load_contract_and_routes()
    if root.resolve() != base:
        raise ValueError(f"Step-5 dependency resolved a different Board-20 root: {root}")
    route_specs = {spec.route_id: spec for spec in specs if spec.route_id in ROUTE_IDS}
    if tuple(route_specs) != ROUTE_IDS:
        raise ValueError(f"Expected route identities {ROUTE_IDS}, found {tuple(route_specs)}")
    for spec in route_specs.values():
        if spec.route_formula != "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
            raise ValueError(f"Unexpected formula for {spec.route_id}: {spec.route_formula}")

    inputs = input_paths(base, script_path, step5_path, route_specs)
    missing_inputs = [str(path) for path in inputs.values() if not path.is_file()]
    if missing_inputs:
        raise FileNotFoundError(f"Missing diagnostic inputs: {missing_inputs}")
    input_hash_before = {name: sha256_file(path) for name, path in inputs.items()}

    matrices_by_route = {
        route_id: step5.load_route_matrices(base, route_specs[route_id])
        for route_id in ROUTE_IDS
    }
    components_by_route = {
        route_id: step5.build_components(
            matrices_by_route[route_id], route_specs[route_id].route_formula
        )
        for route_id in ROUTE_IDS
    }

    matlab_files = {
        route_id: h5py.File(inputs[f"{route_id}:matlab_common_grid"], "r")
        for route_id in ROUTE_IDS
    }
    compact_files = {
        route_id: h5py.File(inputs[f"{route_id}:python_compact_roots"], "r")
        for route_id in ROUTE_IDS
    }

    unique_rows: list[dict[str, Any]] = []
    route_rows: list[dict[str, Any]] = []
    source_rows: list[dict[str, Any]] = []
    refinement_rows: list[dict[str, Any]] = []
    checks: list[dict[str, Any]] = []
    high_precision_all_pass = True
    strict_gate_failures_confirmed = True
    classification_all_consistent = True
    diagnosis_all_numeric = True
    cross_route_all_exact = True

    try:
        for l_value, j_value in TARGET_POINTS:
            matlab_records = {
                route_id: read_matlab_point(
                    matlab_files[route_id], l_value, j_value
                )
                for route_id in ROUTE_IDS
            }
            compact_records = {
                route_id: read_compact_point(
                    compact_files[route_id], l_value, j_value
                )
                for route_id in ROUTE_IDS
            }
            matlab_exact = exact_root_array_equal(
                matlab_records[ROUTE_IDS[0]].roots,
                matlab_records[ROUTE_IDS[1]].roots,
            )
            compact_exact = exact_root_array_equal(
                compact_records[ROUTE_IDS[0]].roots,
                compact_records[ROUTE_IDS[1]].roots,
            )

            coefficient_maps = {
                route_id: step5.build_coefficient_map(
                    route_specs[route_id],
                    components_by_route[route_id],
                    l_value,
                    j_value,
                )
                for route_id in ROUTE_IDS
            }
            coefficient_exact = bool(
                coefficient_maps[ROUTE_IDS[0]].keys()
                == coefficient_maps[ROUTE_IDS[1]].keys()
                and all(
                    np.array_equal(
                        coefficient_maps[ROUTE_IDS[0]][exponent],
                        coefficient_maps[ROUTE_IDS[1]][exponent],
                    )
                    for exponent in coefficient_maps[ROUTE_IDS[0]]
                )
            )
            cross_route_point_exact = matlab_exact and compact_exact and coefficient_exact
            cross_route_all_exact &= cross_route_point_exact
            if not cross_route_point_exact:
                raise AssertionError(
                    f"The two division-II file identities differ at ({l_value},{j_value})"
                )

            spec = route_specs[BASE_ROUTE_ID]
            matrices = matrices_by_route[BASE_ROUTE_ID]
            components = components_by_route[BASE_ROUTE_ID]
            coefficients = coefficient_maps[BASE_ROUTE_ID]
            polynomial, clearing_power, polynomial_degree = (
                step5.polynomial_from_coefficients(coefficients)
            )
            direct_terms = step5.direct_laurent_terms(
                spec, components, l_value, j_value
            )
            compact_matrix = step5.build_compact_state_matrix(
                spec, components, l_value, j_value
            )
            compact_condition = eigenvalue_condition(
                compact_matrix,
                compact_records[BASE_ROUTE_ID].dominant_root,
            )
            if compact_condition["target_match_abs_diff"] > 1.0e-14:
                raise AssertionError(
                    "Reconstructed compact matrix does not reproduce the frozen compact root"
                )
            full = full_q_diagnostic(
                step5,
                spec,
                matrices,
                components,
                coefficients,
                polynomial,
                direct_terms,
                clearing_power,
                l_value,
                j_value,
            )

            matlab = matlab_records[BASE_ROUTE_ID]
            compact = compact_records[BASE_ROUTE_ID]
            hp, attempts = high_precision_refinement(
                coefficients,
                {
                    "MATLAB_STEP4": matlab.rho,
                    "PYTHON_STEP5_COMPACT": compact.rho,
                    "FULL_Q": full["rho"],
                },
            )
            for attempt in attempts:
                refinement_rows.append(
                    {"l": l_value, "j": j_value, **attempt}
                )
            hp_pass = hp["status"] == "PASS"
            high_precision_all_pass &= hp_pass
            if hp_pass:
                hp_root = hp["root"]
                matlab_hp_error_mp = abs(mp.mpf(matlab.rho) - hp_root)
                compact_hp_error_mp = abs(mp.mpf(compact.rho) - hp_root)
                full_hp_error_mp = abs(mp.mpf(full["rho"]) - hp_root)
                matlab_hp_error = float(matlab_hp_error_mp)
                compact_hp_error = float(compact_hp_error_mp)
                full_hp_error = float(full_hp_error_mp)
                closer = "MATLAB_STEP4" if matlab_hp_error < compact_hp_error else "PYTHON_STEP5_COMPACT"
                nonlinear = nonlinear_root_condition(coefficients, hp["rho_float"])
            else:
                matlab_hp_error = compact_hp_error = full_hp_error = math.nan
                matlab_hp_error_mp = compact_hp_error_mp = full_hp_error_mp = None
                closer = "INCONCLUSIVE_HIGH_PRECISION_FAILED"
                nonlinear = {
                    "smallest_singular_value_at_rounded_hp_root": math.nan,
                    "second_smallest_singular_value_at_rounded_hp_root": math.nan,
                    "normalized_transversality": math.nan,
                    "inverse_normalized_transversality": math.nan,
                    "transversality_near_multiple_warning": True,
                }

            matlab_compact_diff = abs(matlab.rho - compact.rho)
            strict_gate_pass = matlab_compact_diff <= STRICT_RHO_ABS_TOL
            strict_gate_failures_confirmed &= not strict_gate_pass
            classifications = (
                matlab.stable,
                compact.stable,
                full["stable"],
                bool(hp["rho_float"] < 1.0) if hp_pass else None,
            )
            classification_consistent = hp_pass and len(set(classifications)) == 1
            classification_all_consistent &= classification_consistent
            near_multiple_warning = bool(
                full["nearest_root_distance"] <= NEAR_MULTIPLE_SEPARATION_TOL
                or nonlinear["transversality_near_multiple_warning"]
            )
            numeric_diagnosis = bool(
                hp_pass
                and matlab_hp_error <= 1.0e-10
                and full_hp_error <= 1.0e-10
                and compact_hp_error > STRICT_RHO_ABS_TOL
                and compact_condition["eigenvalue_condition_number"]
                >= 1.0e5 * full["eigenvalue_condition_number"]
                and not near_multiple_warning
                and classification_consistent
            )
            diagnosis_all_numeric &= numeric_diagnosis
            diagnosis = (
                "ILL_CONDITIONED_COMPACT_LINEARIZATION_NOT_FORMULA_CONFLICT"
                if numeric_diagnosis
                else "INCONCLUSIVE"
            )

            unique_row = {
                "l": l_value,
                "j": j_value,
                "route_formula": spec.route_formula,
                "matrix_order": matrices.M.shape[0],
                "polynomial_degree": polynomial_degree,
                "clearing_power": clearing_power,
                "compact_order": compact_matrix.shape[0],
                "full_q_order": full["order"],
                "matlab_rho": stable_float(matlab.rho),
                "compact_rho": stable_float(compact.rho),
                "full_q_rho": stable_float(full["rho"]),
                "high_precision_rho": hp["root_decimal"],
                "matlab_compact_rho_abs_diff": stable_float(matlab_compact_diff),
                "strict_rho_abs_tolerance": stable_float(STRICT_RHO_ABS_TOL),
                "strict_rho_gate_status": "PASS" if strict_gate_pass else "FAIL",
                "matlab_high_precision_abs_diff": stable_float(matlab_hp_error),
                "compact_high_precision_abs_diff": stable_float(compact_hp_error),
                "full_q_high_precision_abs_diff": stable_float(full_hp_error),
                "closer_to_high_precision_between_matlab_and_compact": closer,
                "matlab_stable": str(matlab.stable).upper(),
                "compact_stable": str(compact.stable).upper(),
                "full_q_stable": str(full["stable"]).upper(),
                "high_precision_stable": str(classifications[3]).upper(),
                "stability_classification_consistent": str(
                    classification_consistent
                ).upper(),
                "matlab_dominant_polynomial_residual": stable_float(
                    matlab.dominant_residual_polynomial
                ),
                "matlab_max_retained_polynomial_residual": stable_float(
                    matlab.max_residual_polynomial
                ),
                "compact_dominant_polynomial_residual": stable_float(
                    compact.dominant_residual_polynomial
                ),
                "compact_dominant_laurent_residual": stable_float(
                    compact.dominant_residual_laurent
                ),
                "compact_max_polynomial_residual": stable_float(
                    compact.max_residual_polynomial
                ),
                "compact_max_laurent_residual": stable_float(
                    compact.max_residual_laurent
                ),
                "full_q_dominant_polynomial_residual": stable_float(
                    full["dominant_residual_polynomial"]
                ),
                "full_q_dominant_laurent_residual": stable_float(
                    full["dominant_residual_laurent"]
                ),
                "matlab_nearest_root_distance": stable_float(
                    matlab.nearest_root_distance
                ),
                "compact_nearest_root_distance": stable_float(
                    compact.nearest_root_distance
                ),
                "full_q_nearest_root_distance": stable_float(
                    full["nearest_root_distance"]
                ),
                "matlab_dominant_modulus_gap": stable_float(
                    matlab.dominant_modulus_gap
                ),
                "compact_dominant_modulus_gap": stable_float(
                    compact.dominant_modulus_gap
                ),
                "full_q_dominant_modulus_gap": stable_float(
                    full["dominant_modulus_gap"]
                ),
                "compact_reciprocal_eigenvalue_condition": stable_float(
                    compact_condition["reciprocal_eigenvalue_condition"]
                ),
                "compact_eigenvalue_condition_number": stable_float(
                    compact_condition["eigenvalue_condition_number"]
                ),
                "full_q_reciprocal_eigenvalue_condition": stable_float(
                    full["reciprocal_eigenvalue_condition"]
                ),
                "full_q_eigenvalue_condition_number": stable_float(
                    full["eigenvalue_condition_number"]
                ),
                "compact_to_full_condition_number_ratio": stable_float(
                    compact_condition["eigenvalue_condition_number"]
                    / full["eigenvalue_condition_number"]
                ),
                "nonlinear_normalized_transversality": stable_float(
                    nonlinear["normalized_transversality"]
                ),
                "nonlinear_inverse_normalized_transversality": stable_float(
                    nonlinear["inverse_normalized_transversality"]
                ),
                "near_multiple_root_warning": str(near_multiple_warning).upper(),
                "full_q_raw_root_count": full["raw_root_count"],
                "full_q_nonfinite_root_count": full["nonfinite_root_count"],
                "full_q_zero_tolerance_diagnostic_only": stable_float(
                    full["zero_root_tolerance_diagnostic_only"]
                ),
                "full_q_roots_at_or_below_zero_tolerance": full[
                    "roots_at_or_below_zero_tolerance"
                ],
                "full_q_deleted_root_count": full["deleted_root_count"],
                "full_q_all_roots_retained_for_rho": str(
                    full["all_roots_retained_for_rho"]
                ).upper(),
                "high_precision_status": hp["status"],
                "high_precision_seed_spread": hp["seed_spread_decimal"],
                "high_precision_80_120_difference": hp[
                    "dps_80_120_difference_decimal"
                ],
                "high_precision_newton_correction": hp[
                    "newton_correction_abs_decimal"
                ],
                "high_precision_scaled_determinant_abs": hp[
                    "scaled_determinant_abs_decimal"
                ],
                "diagnosis": diagnosis,
                "cross_route_matlab_roots_exact_equal": str(matlab_exact).upper(),
                "cross_route_compact_roots_exact_equal": str(compact_exact).upper(),
                "cross_route_coefficient_maps_exact_equal": str(
                    coefficient_exact
                ).upper(),
            }
            unique_rows.append(unique_row)

            for route_id in ROUTE_IDS:
                route_matlab = matlab_records[route_id]
                route_compact = compact_records[route_id]
                route_rows.append(
                    {
                        "route_id": route_id,
                        "declared_method": route_specs[route_id].declared_method,
                        **unique_row,
                        "route_matlab_rho": stable_float(route_matlab.rho),
                        "route_compact_rho": stable_float(route_compact.rho),
                        "route_matlab_compact_abs_diff": stable_float(
                            abs(route_matlab.rho - route_compact.rho)
                        ),
                    }
                )

            sources = (
                (
                    "MATLAB_STEP4",
                    matlab.rho,
                    matlab.dominant_root,
                    matlab.dominant_residual_polynomial,
                    matlab.dominant_residual_laurent,
                    matlab.nearest_root_distance,
                    matlab.dominant_modulus_gap,
                    math.nan,
                ),
                (
                    "PYTHON_STEP5_COMPACT",
                    compact.rho,
                    compact.dominant_root,
                    compact.dominant_residual_polynomial,
                    compact.dominant_residual_laurent,
                    compact.nearest_root_distance,
                    compact.dominant_modulus_gap,
                    compact_condition["eigenvalue_condition_number"],
                ),
                (
                    "TARGETED_FULL_Q_ALL_ROOTS_RETAINED",
                    full["rho"],
                    full["dominant_root"],
                    full["dominant_residual_polynomial"],
                    full["dominant_residual_laurent"],
                    full["nearest_root_distance"],
                    full["dominant_modulus_gap"],
                    full["eigenvalue_condition_number"],
                ),
                (
                    "MPMATH_120DPS_NONLINEAR_REFINEMENT",
                    hp["rho_float"],
                    complex(hp["rho_float"]),
                    math.nan,
                    math.nan,
                    full["nearest_root_distance"],
                    full["dominant_modulus_gap"],
                    math.nan,
                ),
            )
            for (
                source,
                rho,
                root_value,
                polynomial_residual,
                laurent_residual,
                nearest,
                modulus_gap,
                condition_number,
            ) in sources:
                source_rows.append(
                    {
                        "l": l_value,
                        "j": j_value,
                        "source": source,
                        "rho": stable_float(rho),
                        "dominant_root_real": stable_float(root_value.real),
                        "dominant_root_imag": stable_float(root_value.imag),
                        "dominant_polynomial_residual": stable_float(
                            polynomial_residual
                        ),
                        "dominant_laurent_residual": stable_float(laurent_residual),
                        "nearest_root_distance": stable_float(nearest),
                        "dominant_modulus_gap": stable_float(modulus_gap),
                        "eigenvalue_condition_number": stable_float(condition_number),
                        "stable": str(bool(rho < 1.0)).upper()
                        if math.isfinite(float(rho))
                        else "INCONCLUSIVE",
                    }
                )
    finally:
        for handle in matlab_files.values():
            handle.close()
        for handle in compact_files.values():
            handle.close()

    input_hash_after = {name: sha256_file(path) for name, path in inputs.items()}
    inputs_unchanged = input_hash_before == input_hash_after
    if not inputs_unchanged:
        raise RuntimeError("One or more read-only input files changed during diagnosis")

    checks.extend(
        [
            {
                "check_id": "D-RHO-001",
                "description": "诊断对象严格等于预声明4个唯一点",
                "expected": str(TARGET_POINTS),
                "actual": str(tuple((row["l"], row["j"]) for row in unique_rows)),
                "status": "PASS"
                if tuple((row["l"], row["j"]) for row in unique_rows)
                == TARGET_POINTS
                else "FAIL",
            },
            {
                "check_id": "D-RHO-002",
                "description": "两条第二分区文件身份路线的冻结根与系数逐点完全相同",
                "expected": "TRUE",
                "actual": str(cross_route_all_exact).upper(),
                "status": "PASS" if cross_route_all_exact else "FAIL",
            },
            {
                "check_id": "D-RHO-003",
                "description": "full-q计算不删除任何根",
                "expected": "每点deleted_root_count=0",
                "actual": str([row["full_q_deleted_root_count"] for row in unique_rows]),
                "status": "PASS"
                if all(row["full_q_deleted_root_count"] == 0 for row in unique_rows)
                else "FAIL",
            },
            {
                "check_id": "D-RHO-004",
                "description": "80位三起点与120位复核均可靠收敛",
                "expected": "TRUE",
                "actual": str(high_precision_all_pass).upper(),
                "status": "PASS" if high_precision_all_pass else "FAIL",
            },
            {
                "check_id": "D-RHO-005",
                "description": "四点MATLAB/compact绝对差仍严格超过1e-8",
                "expected": "4个EXPECTED_FAIL均确认",
                "actual": str(
                    [row["matlab_compact_rho_abs_diff"] for row in unique_rows]
                ),
                "status": "EXPECTED_FAIL_CONFIRMED"
                if strict_gate_failures_confirmed
                else "FAIL_UNEXPECTED_GATE_RESULT",
            },
            {
                "check_id": "D-RHO-006",
                "description": "MATLAB/compact/full-q/高精度稳定分类一致",
                "expected": "TRUE",
                "actual": str(classification_all_consistent).upper(),
                "status": "PASS" if classification_all_consistent else "FAIL",
            },
            {
                "check_id": "D-RHO-007",
                "description": "四点均支持compact线性化病态而非公式冲突",
                "expected": "TRUE",
                "actual": str(diagnosis_all_numeric).upper(),
                "status": "PASS" if diagnosis_all_numeric else "INCONCLUSIVE",
            },
            {
                "check_id": "D-RHO-008",
                "description": "全部既有只读输入哈希在诊断前后不变",
                "expected": "TRUE",
                "actual": str(inputs_unchanged).upper(),
                "status": "PASS" if inputs_unchanged else "FAIL",
            },
        ]
    )

    hard_failures = [
        row
        for row in checks
        if row["status"] not in ("PASS", "EXPECTED_FAIL_CONFIRMED")
    ]
    overall_status = (
        "DIAGNOSTIC_COMPLETED_STRICT_GATE_STILL_FAIL_NUMERIC_CONDITIONING_CONFIRMED"
        if not hard_failures
        else "DIAGNOSTIC_INCONCLUSIVE"
    )

    input_rows = []
    for name, path in inputs.items():
        input_rows.append(
            {
                "role": name,
                "path": str(path.relative_to(base)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256_before": input_hash_before[name],
                "sha256_after": input_hash_after[name],
                "unchanged": str(input_hash_before[name] == input_hash_after[name]).upper(),
            }
        )

    audit = {
        "schema_version": SCHEMA_VERSION,
        "overall_status": overall_status,
        "scope": {
            "routes": list(ROUTE_IDS),
            "unique_points": [list(point) for point in TARGET_POINTS],
            "existing_step4_or_step5_outputs_modified": False,
            "existing_contracts_or_gates_modified": False,
            "new_output_root": "outputs/step5_rho_diagnostics",
        },
        "fixed_contract": {
            "rho_absolute_tolerance": STRICT_RHO_ABS_TOL,
            "stable_definition": "rho < 1",
            "zero_root_threshold_relaxed": False,
            "full_q_roots_deleted": 0,
        },
        "method": {
            "full_q_companion": "ordinary full-coordinate q-history companion, all roots retained",
            "high_precision": "mpmath direct Laurent determinant, 3 seeds at 80 dps plus full-q seed at 120 dps",
            "high_precision_reference_boundary": "root of the nonlinear characteristic determinant defined by frozen float64 coefficient matrices",
            "compact_condition": "right/left eigenvector reciprocal condition |y^H x|/(||y|| ||x||)",
            "near_multiple_tests": {
                "nearest_root_distance_warning_below": NEAR_MULTIPLE_SEPARATION_TOL,
                "normalized_nonlinear_transversality_warning_below": NEAR_MULTIPLE_TRANSVERSALITY_TOL,
            },
        },
        "cross_route_exact_identity": cross_route_all_exact,
        "strict_gate_failures_confirmed": strict_gate_failures_confirmed,
        "stability_classification_consistent": classification_all_consistent,
        "diagnosis": (
            "ILL_CONDITIONED_COMPACT_LINEARIZATION_NOT_FORMULA_CONFLICT"
            if diagnosis_all_numeric
            else "INCONCLUSIVE"
        ),
        "high_precision_all_pass": high_precision_all_pass,
        "input_hashes_unchanged": inputs_unchanged,
        "points": unique_rows,
        "checks": checks,
        "software": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "scipy": scipy.__version__,
            "h5py": h5py.__version__,
            "mpmath": mp.__version__,
        },
        "evidence_boundary": {
            "step5_strict_gate_changed": False,
            "step5_strict_gate_result": "FAIL_AT_FOUR_UNIQUE_POINTS",
            "stable_mask_changed": False,
            "thesis_or_manuscript_contract_upgraded": False,
            "success_figure_directory_created": False,
        },
    }

    unique_fields = list(unique_rows[0].keys())
    route_fields = list(route_rows[0].keys())
    source_fields = list(source_rows[0].keys())
    refinement_fields = list(refinement_rows[0].keys())
    check_fields = ["check_id", "description", "expected", "actual", "status"]
    input_fields = [
        "role",
        "path",
        "bytes",
        "sha256_before",
        "sha256_after",
        "unchanged",
    ]

    core_payloads = {
        "unique_point_diagnostics.csv": csv_bytes(unique_rows, unique_fields),
        "route_point_diagnostics.csv": csv_bytes(route_rows, route_fields),
        "root_source_diagnostics.csv": csv_bytes(source_rows, source_fields),
        "high_precision_refinement.csv": csv_bytes(
            refinement_rows, refinement_fields
        ),
        "checks.csv": csv_bytes(checks, check_fields),
        "input_manifest.csv": csv_bytes(input_rows, input_fields),
        "audit.json": json_bytes(audit),
        "步骤5_第二分区4个谱半径超差点严格诊断.md": (
            report_text(unique_rows, audit) + "\n"
        ).encode("utf-8"),
    }
    for filename, payload in core_payloads.items():
        write_if_changed(output_dir / filename, payload)

    artifact_rows = []
    for name, path in inputs.items():
        artifact_rows.append(
            {
                "role": f"readonly_input:{name}",
                "path": str(path.relative_to(base)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    for filename in core_payloads:
        path = output_dir / filename
        artifact_rows.append(
            {
                "role": "generated_core_output",
                "path": str(path.relative_to(base)).replace("\\", "/"),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    artifact_manifest_payload = csv_bytes(
        artifact_rows, ["role", "path", "bytes", "sha256"]
    )
    write_if_changed(output_dir / "artifact_manifest.csv", artifact_manifest_payload)

    repeat_targets = {
        "code/diagnose_board20_step5_div2_rho.py": script_path,
        **{
            f"outputs/step5_rho_diagnostics/{filename}": output_dir / filename
            for filename in core_payloads
        },
        "outputs/step5_rho_diagnostics/artifact_manifest.csv": output_dir
        / "artifact_manifest.csv",
    }
    current_hashes = {name: sha256_file(path) for name, path in repeat_targets.items()}
    current_snapshot = {
        "schema_version": "board20_step5_rho_repeat_snapshot_v1",
        "hashes": current_hashes,
    }
    if args.repeat_mode == "baseline":
        repeat_check = {
            "schema_version": "board20_step5_rho_repeat_check_v1",
            "mode": "baseline",
            "status": "BASELINE_CREATED",
            "files_checked": len(current_hashes),
            "mismatches": [],
        }
        write_if_changed(snapshot_path, json_bytes(current_snapshot))
    else:
        assert previous_snapshot is not None
        prior_hashes = previous_snapshot.get("hashes", {})
        all_names = sorted(set(prior_hashes) | set(current_hashes))
        mismatches = [
            {
                "path": name,
                "baseline_sha256": prior_hashes.get(name, "MISSING"),
                "current_sha256": current_hashes.get(name, "MISSING"),
            }
            for name in all_names
            if prior_hashes.get(name) != current_hashes.get(name)
        ]
        repeat_check = {
            "schema_version": "board20_step5_rho_repeat_check_v1",
            "mode": "verify",
            "status": "PASS" if not mismatches else "FAIL",
            "files_checked": len(all_names),
            "mismatches": mismatches,
            "baseline_hashes": prior_hashes,
            "current_hashes": current_hashes,
        }
    write_if_changed(repeat_check_path, json_bytes(repeat_check))

    print(f"BOARD20_STEP5_DIV2_RHO_DIAGNOSTIC={overall_status}")
    for row in unique_rows:
        print(
            f"POINT=({row['l']},{row['j']}) "
            f"MATLAB_COMPACT_DIFF={row['matlab_compact_rho_abs_diff']} "
            f"STRICT_GATE={row['strict_rho_gate_status']} "
            f"DIAGNOSIS={row['diagnosis']}"
        )
    print(f"REPEAT_MODE={args.repeat_mode} REPEAT_STATUS={repeat_check['status']}")
    print(f"OUTPUT_DIR={output_dir}")

    exit_failure = bool(hard_failures)
    if args.repeat_mode == "verify" and repeat_check["status"] != "PASS":
        exit_failure = True
    return 2 if exit_failure else 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
"""Read-only numerical-solver diagnosis for the four Step-5 div2 outliers.

This script deliberately does not change the registered Step-4 or Step-5
scientific artifacts and does not change the fixed 1e-8 acceptance gate.  It
rebuilds the Laurent matrix polynomial from the two sealed div2 workspaces and
compares four numerical linearizations only at the four pre-identified points:

1. compact scalar-delay augmentation followed by ordinary ``eig``;
2. full-q history companion followed by ordinary ``eig``;
3. a SciPy generalized first-companion QZ pencil with the same common
   coefficient scaling used by the Step-4 MATLAB solver;
4. the same generalized QZ pencil without coefficient scaling, as a control.

The Step-4 MATLAB rho values are comparison references only.  They are never
used to construct a Python root or replace a Python result.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import h5py
import numpy as np
import scipy.linalg as sla


BOARD_ROOT = Path(__file__).resolve().parents[1]
CODE_ROOT = BOARD_ROOT / "code"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step5_solver_conditioning"
COMPUTE_ROOT = BOARD_ROOT / "outputs" / "step5_independent_compute" / "full"
STEP4_ROOT = BOARD_ROOT / "outputs" / "step4_rho_grids"

COMPUTE_CONTRACT_PATH = CODE_ROOT / "board20_step5_compute_contract.json"
ROUTE_MANIFEST_PATH = CODE_ROOT / "board20_step4_route_manifest.json"
MATLAB_SOLVER_PATH = CODE_ROOT / "solve_board20_author_poles.m"
COMPUTE_SCRIPT_PATH = CODE_ROOT / "compute_board20_step5_independent.py"
VALIDATION_CONTRACT_PATH = CODE_ROOT / "board20_step5_validation_contract.json"
VALIDATOR_SCRIPT_PATH = CODE_ROOT / "validate_board20_step5.py"
DIAGNOSTIC_SCRIPT_PATH = Path(__file__).resolve()

EXPECTED_COMPUTE_CONTRACT_SHA256 = (
    "558C778EFBC6F924A037A59B9ED3E439C8E6A5C1A6D36861CBF75BD59CB3D2D2"
)
EXPECTED_ROUTE_MANIFEST_SHA256 = (
    "397564F6884DE082995D04DF9AB62F13244DFA8C6129BDDB1F18A2DF0BE88D6E"
)
EXPECTED_COMPUTE_SCRIPT_SHA256 = (
    "F30032228779711BAA03CCD1D1FE2A2FCAFF14335B4D3F0290831CEBDBF26C69"
)

ROUTE_IDS = ("main_ori_div2", "main_guyan_div2")
POINTS = ((11, 39), (15, 40), (23, 41), (28, 43))
SOLVER_ORDER = (
    "compact_ordinary_eig",
    "full_q_ordinary_eig",
    "generalized_qz_matlab_scaled",
    "generalized_qz_unscaled_control",
)
RHO_TOLERANCE = 1.0e-8
RESIDUAL_TOLERANCE = 1.0e-8
FORMULA_IDENTITY_TOLERANCE = 1.0e-12


@dataclass(frozen=True)
class RouteData:
    route_id: str
    workspace_path: Path
    workspace_sha256: str
    matrices: dict[str, np.ndarray | float]
    matrix_payload_sha256: str


@dataclass(frozen=True)
class EigenSolution:
    roots: np.ndarray
    left_vectors: np.ndarray
    right_vectors: np.ndarray
    finite_mask: np.ndarray
    infinite_count: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def write_json(path: Path, value: Any) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def relative_path(path: Path) -> str:
    return path.resolve().relative_to(BOARD_ROOT.resolve()).as_posix()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def matlab73_numeric(file: h5py.File, name: str) -> np.ndarray:
    value = np.asarray(file[name])
    if value.dtype.fields and {"real", "imag"}.issubset(value.dtype.fields):
        value = value["real"] + 1j * value["imag"]
    if value.ndim >= 2:
        value = value.T
    return np.asarray(value)


def matlab73_cell_complex(file: h5py.File, name: str, l_value: int, j_value: int) -> np.ndarray:
    reference = file[name][j_value, l_value]
    if not reference:
        return np.empty(0, dtype=np.complex128)
    value = np.asarray(file[reference])
    if value.dtype.fields and {"real", "imag"}.issubset(value.dtype.fields):
        value = value["real"] + 1j * value["imag"]
    return np.asarray(value, dtype=np.complex128).reshape(-1)


def matrix_payload_sha256(matrices: Mapping[str, np.ndarray | float]) -> str:
    digest = hashlib.sha256()
    for name in sorted(matrices):
        digest.update(name.encode("utf-8"))
        value = matrices[name]
        array = np.asarray(value, dtype="<f8", order="C")
        digest.update(canonical_json(list(array.shape)).encode("ascii"))
        digest.update(array.tobytes(order="C"))
    return digest.hexdigest().upper()


def load_routes() -> tuple[list[RouteData], dict[str, Any]]:
    if sha256_file(COMPUTE_CONTRACT_PATH) != EXPECTED_COMPUTE_CONTRACT_SHA256:
        raise RuntimeError("The sealed Step-5 compute contract hash changed.")
    if sha256_file(ROUTE_MANIFEST_PATH) != EXPECTED_ROUTE_MANIFEST_SHA256:
        raise RuntimeError("The sealed Step-4 route manifest hash changed.")
    if sha256_file(COMPUTE_SCRIPT_PATH) != EXPECTED_COMPUTE_SCRIPT_SHA256:
        raise RuntimeError("The sealed Step-5 compute script hash changed.")

    contract = read_json(COMPUTE_CONTRACT_PATH)
    route_map = {entry["route_id"]: entry for entry in contract["routes"]}
    routes: list[RouteData] = []
    for route_id in ROUTE_IDS:
        entry = route_map[route_id]
        if entry["route_formula"] != "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
            raise RuntimeError(f"Unexpected formula for {route_id}.")
        if entry["delay_dofs_matlab_1_based"] != [1, 2]:
            raise RuntimeError(f"Unexpected delay DOFs for {route_id}.")
        workspace = BOARD_ROOT / entry["workspace_relpath"]
        actual_hash = sha256_file(workspace)
        expected_hash = str(entry["workspace_sha256"]).upper()
        if actual_hash != expected_hash:
            raise RuntimeError(f"Workspace hash changed for {route_id}.")
        matrices: dict[str, np.ndarray | float] = {}
        with h5py.File(workspace, "r") as file:
            for logical, stored in entry["matrix_variables"].items():
                value = matlab73_numeric(file, stored)
                if logical == "dt":
                    matrices[logical] = float(np.asarray(value).squeeze())
                else:
                    matrices[logical] = np.asarray(value, dtype=np.float64)
        routes.append(
            RouteData(
                route_id=route_id,
                workspace_path=workspace,
                workspace_sha256=actual_hash,
                matrices=matrices,
                matrix_payload_sha256=matrix_payload_sha256(matrices),
            )
        )
    return routes, contract


def protected_input_paths(routes: Sequence[RouteData]) -> list[Path]:
    paths = [
        COMPUTE_CONTRACT_PATH,
        ROUTE_MANIFEST_PATH,
        MATLAB_SOLVER_PATH,
        COMPUTE_SCRIPT_PATH,
        VALIDATION_CONTRACT_PATH,
        VALIDATOR_SCRIPT_PATH,
        BOARD_ROOT / "outputs" / "step5_audit" / "full_postcheck.json",
        BOARD_ROOT / "outputs" / "step5_audit" / "full_postcheck_checks.csv",
        BOARD_ROOT / "outputs" / "step5_audit" / "full_postcheck_report.md",
        BOARD_ROOT / "logs" / "step5_validation" / "full_postcheck.log",
    ]
    for route in routes:
        paths.extend(
            [
                route.workspace_path,
                STEP4_ROOT / route.route_id / "common_31x67_same_formula_candidate.mat",
                COMPUTE_ROOT / route.route_id / "point_summary.csv",
                COMPUTE_ROOT / route.route_id / "roots.h5",
                COMPUTE_ROOT / route.route_id / "route_status.json",
            ]
        )
    missing = [str(path) for path in paths if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Protected input is missing: {missing}")
    return paths


def hash_paths(paths: Iterable[Path]) -> dict[str, str]:
    return {relative_path(path): sha256_file(path) for path in sorted(paths, key=lambda item: relative_path(item))}


def add_coefficient(store: dict[int, np.ndarray], exponent: int, matrix: np.ndarray) -> None:
    if exponent in store:
        store[exponent] = store[exponent] + matrix
    else:
        store[exponent] = np.array(matrix, dtype=np.float64, copy=True)


def build_laurent_coefficients(
    matrices: Mapping[str, np.ndarray | float], l_value: int, j_value: int
) -> dict[int, np.ndarray]:
    """Independent reconstruction of the sealed div2 left-H/outside-feedback formula."""
    M = np.asarray(matrices["M"], dtype=np.float64)
    C1 = np.asarray(matrices["C1"], dtype=np.float64)
    K1 = np.asarray(matrices["K1"], dtype=np.float64)
    C2 = np.asarray(matrices["C2"], dtype=np.float64)
    K2 = np.asarray(matrices["K2"], dtype=np.float64)
    al = np.asarray(matrices["al"], dtype=np.float64)
    S = np.asarray(matrices["S"], dtype=np.float64)
    delta_c = np.asarray(matrices["DeltaC"], dtype=np.float64)
    delta_k = np.asarray(matrices["DeltaK"], dtype=np.float64)
    dt = float(matrices["dt"])
    n = M.shape[0]

    # MATLAB M/al is X*al=M.  This is an independent solve, never inv(al).
    T = sla.solve(al.T, M.T, assume_a="gen", check_finite=True).T / (dt * dt)
    coefficients: dict[int, np.ndarray] = {}
    add_coefficient(coefficients, 1, T)
    add_coefficient(coefficients, 0, -2.0 * T + C1 / dt + K1)
    add_coefficient(coefficients, -1, T - C1 / dt)

    delayed_zero = C2 / dt + K2
    delayed_minus_one = -C2 / dt
    for delay, dof in zip((l_value, j_value), (0, 1), strict=True):
        H = np.zeros((n, n), dtype=np.float64)
        H[dof, dof] = 1.0
        add_coefficient(coefficients, -delay, H @ delayed_zero)
        add_coefficient(coefficients, -(delay + 1), H @ delayed_minus_one)

    # Second-division feedback is explicitly outside H.
    add_coefficient(coefficients, 0, S.T @ (delta_c / dt + delta_k) @ S)
    add_coefficient(coefficients, -1, S.T @ (-delta_c / dt) @ S)
    return {
        exponent: matrix
        for exponent, matrix in sorted(coefficients.items())
        if np.any(matrix != 0.0)
    }


def direct_characteristic_matrix(
    matrices: Mapping[str, np.ndarray | float], l_value: int, j_value: int, z: complex
) -> np.ndarray:
    M = np.asarray(matrices["M"], dtype=np.float64)
    C1 = np.asarray(matrices["C1"], dtype=np.float64)
    K1 = np.asarray(matrices["K1"], dtype=np.float64)
    C2 = np.asarray(matrices["C2"], dtype=np.float64)
    K2 = np.asarray(matrices["K2"], dtype=np.float64)
    al = np.asarray(matrices["al"], dtype=np.float64)
    S = np.asarray(matrices["S"], dtype=np.float64)
    delta_c = np.asarray(matrices["DeltaC"], dtype=np.float64)
    delta_k = np.asarray(matrices["DeltaK"], dtype=np.float64)
    dt = float(matrices["dt"])
    right_division = sla.solve(al.T, M.T, assume_a="gen", check_finite=True).T
    velocity = (z - 1.0) / (z * dt)
    acceleration = (z - 1.0) ** 2 / (z * dt * dt)
    H = np.zeros_like(M, dtype=np.complex128)
    H[0, 0] = z ** (-l_value)
    H[1, 1] = z ** (-j_value)
    return (
        acceleration * right_division
        + velocity * C1
        + K1
        + H @ (velocity * C2 + K2)
        + S.T @ (velocity * delta_c + delta_k) @ S
    )


def evaluate_laurent(coefficients: Mapping[int, np.ndarray], z: complex) -> np.ndarray:
    value = np.zeros_like(next(iter(coefficients.values())), dtype=np.complex128)
    for exponent, matrix in coefficients.items():
        value += (z**exponent) * matrix
    return value


def formula_identity_error(
    matrices: Mapping[str, np.ndarray | float],
    coefficients: Mapping[int, np.ndarray],
    l_value: int,
    j_value: int,
) -> float:
    errors: list[float] = []
    for z in (0.83 + 0.17j, 1.12 - 0.13j, -0.71 + 0.29j):
        direct = direct_characteristic_matrix(matrices, l_value, j_value, z)
        expanded = evaluate_laurent(coefficients, z)
        denominator = max(1.0, float(np.linalg.norm(direct, ord="fro")))
        errors.append(float(np.linalg.norm(direct - expanded, ord="fro") / denominator))
    return max(errors)


def polynomial_from_laurent(
    coefficients: Mapping[int, np.ndarray],
) -> tuple[list[np.ndarray], int, int]:
    exponents = sorted(coefficients)
    clearing_power = max(0, -exponents[0])
    degree = exponents[-1] + clearing_power
    n = next(iter(coefficients.values())).shape[0]
    polynomial = [np.zeros((n, n), dtype=np.float64) for _ in range(degree + 1)]
    for exponent, matrix in coefficients.items():
        polynomial[exponent + clearing_power] += matrix
    while len(polynomial) > 1 and not np.any(polynomial[-1] != 0.0):
        polynomial.pop()
    return polynomial, clearing_power, len(polynomial) - 1


def build_compact_state_matrix(
    matrices: Mapping[str, np.ndarray | float], l_value: int, j_value: int
) -> np.ndarray:
    M = np.asarray(matrices["M"], dtype=np.float64)
    C1 = np.asarray(matrices["C1"], dtype=np.float64)
    K1 = np.asarray(matrices["K1"], dtype=np.float64)
    C2 = np.asarray(matrices["C2"], dtype=np.float64)
    K2 = np.asarray(matrices["K2"], dtype=np.float64)
    al = np.asarray(matrices["al"], dtype=np.float64)
    S = np.asarray(matrices["S"], dtype=np.float64)
    delta_c = np.asarray(matrices["DeltaC"], dtype=np.float64)
    delta_k = np.asarray(matrices["DeltaK"], dtype=np.float64)
    dt = float(matrices["dt"])
    n = M.shape[0]
    delays = (l_value, j_value)
    T = sla.solve(al.T, M.T, assume_a="gen", check_finite=True).T / (dt * dt)
    base_zero = -2.0 * T + C1 / dt + K1
    base_minus_one = T - C1 / dt
    delayed_zero = C2 / dt + K2
    delayed_minus_one = -C2 / dt
    feedback_zero = S.T @ (delta_c / dt + delta_k) @ S
    feedback_minus_one = S.T @ (-delta_c / dt) @ S

    order = 2 * n + l_value + j_value
    rhs = np.zeros((n, order), dtype=np.float64)
    rhs[:, :n] = -(base_zero + feedback_zero)
    rhs[:, n : 2 * n] = -(base_minus_one + feedback_minus_one)
    offsets = (2 * n, 2 * n + l_value)
    for delay, dof, offset in zip(delays, (0, 1), offsets, strict=True):
        input_zero = delayed_zero[dof, :]
        input_minus = delayed_minus_one[dof, :]
        output = np.zeros(n, dtype=np.float64)
        output[dof] = 1.0
        if delay == 0:
            rhs[:, :n] -= np.outer(output, input_zero)
            rhs[:, n : 2 * n] -= np.outer(output, input_minus)
        else:
            rhs[:, offset + delay - 1] -= output

    transition = np.zeros((order, order), dtype=np.float64)
    transition[:n, :] = sla.solve(T, rhs, assume_a="gen", check_finite=True)
    transition[n : 2 * n, :n] = np.eye(n)
    for delay, dof, offset in zip(delays, (0, 1), offsets, strict=True):
        if delay == 0:
            continue
        transition[offset, :n] = delayed_zero[dof, :]
        transition[offset, n : 2 * n] = delayed_minus_one[dof, :]
        for position in range(1, delay):
            transition[offset + position, offset + position - 1] = 1.0
    return transition


def build_full_q_state_matrix(
    polynomial: Sequence[np.ndarray],
) -> np.ndarray:
    degree = len(polynomial) - 1
    n = polynomial[0].shape[0]
    transition = np.zeros((n * degree, n * degree), dtype=np.float64)
    top = np.hstack([-polynomial[degree - block - 1] for block in range(degree)])
    transition[:n, :] = sla.solve(
        polynomial[-1], top, assume_a="gen", check_finite=True
    )
    if degree > 1:
        transition[n:, :-n] = np.eye(n * (degree - 1))
    return transition


def build_generalized_first_companion(
    polynomial: Sequence[np.ndarray], coefficient_scaled: bool
) -> tuple[np.ndarray, np.ndarray, float]:
    """Independently encode the Step-4 MATLAB first companion pencil."""
    degree = len(polynomial) - 1
    n = polynomial[0].shape[0]
    coefficient_scale = (
        max(float(np.linalg.norm(matrix, ord="fro")) for matrix in polynomial)
        if coefficient_scaled
        else 1.0
    )
    if not math.isfinite(coefficient_scale) or coefficient_scale <= 0:
        raise FloatingPointError("Invalid polynomial coefficient scale.")
    scaled = [matrix / coefficient_scale for matrix in polynomial]
    order = n * degree
    A = np.zeros((order, order), dtype=np.float64)
    B = np.zeros((order, order), dtype=np.float64)
    for block in range(degree):
        columns = slice(block * n, (block + 1) * n)
        A[:n, columns] = -scaled[degree - block - 1]
    B[:n, :n] = scaled[-1]
    if degree > 1:
        A[n:, : n * (degree - 1)] = np.eye(n * (degree - 1))
        B[n:, n:] = np.eye(n * (degree - 1))
    return A, B, coefficient_scale


def solve_ordinary(matrix: np.ndarray) -> EigenSolution:
    roots, left, right = sla.eig(
        matrix,
        left=True,
        right=True,
        overwrite_a=False,
        check_finite=True,
    )
    roots = np.asarray(roots, dtype=np.complex128)
    finite = np.isfinite(roots.real) & np.isfinite(roots.imag)
    return EigenSolution(roots, left, right, finite, int(np.count_nonzero(~finite)))


def solve_generalized(A: np.ndarray, B: np.ndarray) -> EigenSolution:
    homogeneous, left, right = sla.eig(
        A,
        B,
        left=True,
        right=True,
        homogeneous_eigvals=True,
        overwrite_a=False,
        overwrite_b=False,
        check_finite=True,
    )
    alpha = np.asarray(homogeneous[0], dtype=np.complex128)
    beta = np.asarray(homogeneous[1], dtype=np.complex128)
    beta_scale = np.maximum(1.0, np.maximum(np.abs(alpha), np.abs(beta)))
    finite = np.abs(beta) > np.finfo(float).eps * beta_scale
    roots = np.full(alpha.shape, complex(np.inf, 0.0), dtype=np.complex128)
    roots[finite] = alpha[finite] / beta[finite]
    finite &= np.isfinite(roots.real) & np.isfinite(roots.imag)
    return EigenSolution(roots, left, right, finite, int(np.count_nonzero(~finite)))


def zero_root_tolerance(roots: np.ndarray, finite: np.ndarray, order: int) -> float:
    magnitudes = np.abs(roots[finite])
    nonzero = magnitudes[magnitudes > 0]
    scale = max(1.0, float(np.median(nonzero))) if nonzero.size else 1.0
    return max(1.0e-12, 100.0 * np.finfo(float).eps * max(1, order) * scale)


def normalized_direct_residuals(
    coefficients: Mapping[int, np.ndarray], root: complex, physical_vector: np.ndarray
) -> tuple[float, float]:
    value = evaluate_laurent(coefficients, root)
    denominator = sum(
        float(np.linalg.norm(matrix, ord="fro")) * (abs(root) ** exponent)
        for exponent, matrix in coefficients.items()
    )
    singular_values = np.linalg.svd(value, compute_uv=False)
    sigma_residual = float(singular_values[-1] / denominator)
    vector_norm = float(np.linalg.norm(physical_vector))
    vector_residual = float(
        np.linalg.norm(value @ physical_vector) / (denominator * vector_norm)
    )
    return sigma_residual, vector_residual


def physical_root_condition(
    coefficients: Mapping[int, np.ndarray], root: complex
) -> tuple[float, float]:
    value = evaluate_laurent(coefficients, root)
    left, _singular, right_h = np.linalg.svd(value, full_matrices=False)
    y = left[:, -1]
    x = right_h.conj().T[:, -1]
    derivative = np.zeros_like(value)
    for exponent, matrix in coefficients.items():
        derivative += exponent * (root ** (exponent - 1)) * matrix
    denominator = sum(
        float(np.linalg.norm(matrix, ord="fro")) * (abs(root) ** exponent)
        for exponent, matrix in coefficients.items()
    )
    reciprocal = float(abs(root) * abs(np.vdot(y, derivative @ x)) / denominator)
    indicator = math.inf if reciprocal == 0 else 1.0 / reciprocal
    return reciprocal, indicator


def pencil_condition(
    A: np.ndarray,
    B: np.ndarray,
    root: complex,
    left_vector: np.ndarray,
    right_vector: np.ndarray,
) -> tuple[float, float, float, float]:
    left_norm = float(np.linalg.norm(left_vector))
    right_norm = float(np.linalg.norm(right_vector))
    Bx = B @ right_vector
    overlap_denominator = left_norm * float(np.linalg.norm(Bx))
    coupling = float(abs(np.vdot(left_vector, Bx)))
    overlap = coupling / overlap_denominator if overlap_denominator > 0 else 0.0
    matrix_scale = float(np.linalg.norm(A, ord="fro")) + abs(root) * float(
        np.linalg.norm(B, ord="fro")
    )
    relative_rcond = (
        abs(root) * coupling / (left_norm * right_norm * matrix_scale)
        if left_norm > 0 and right_norm > 0 and matrix_scale > 0
        else 0.0
    )
    condition_indicator = math.inf if relative_rcond == 0 else 1.0 / relative_rcond
    pencil_residual = float(
        np.linalg.norm(A @ right_vector - root * Bx)
        / (matrix_scale * right_norm)
    )
    return overlap, relative_rcond, condition_indicator, pencil_residual


def nearest_neighbor_spacing(root: complex, roots: np.ndarray, dominant_index: int) -> tuple[float, float]:
    if roots.size <= 1:
        return math.inf, math.inf
    mask = np.ones(roots.size, dtype=bool)
    mask[dominant_index] = False
    absolute = float(np.min(np.abs(roots[mask] - root)))
    return absolute, absolute / max(1.0, abs(root))


def finite_number(value: float) -> float | None:
    return float(value) if math.isfinite(float(value)) else None


def load_step5_record(route_id: str, l_value: int, j_value: int) -> dict[str, str]:
    path = COMPUTE_ROOT / route_id / "point_summary.csv"
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if int(row["l"]) == l_value and int(row["j"]) == j_value:
                return dict(row)
    raise KeyError(f"Step-5 point ({l_value},{j_value}) missing for {route_id}.")


def read_step4_reference(
    route_id: str, l_value: int, j_value: int
) -> tuple[float, bool, np.ndarray, int, int]:
    path = STEP4_ROOT / route_id / "common_31x67_same_formula_candidate.mat"
    with h5py.File(path, "r") as file:
        rho = float(matlab73_numeric(file, "rho")[l_value, j_value])
        stable = bool(matlab73_numeric(file, "stable")[l_value, j_value])
        roots = matlab73_cell_complex(file, "poles", l_value, j_value)
        degree = int(matlab73_numeric(file, "poly_degree")[l_value, j_value])
        clearing = int(matlab73_numeric(file, "clearing_power")[l_value, j_value])
    return rho, stable, roots, degree, clearing


def dominant_matlab_root(roots: np.ndarray) -> complex:
    if roots.size == 0:
        raise FloatingPointError("Step-4 retained root set is empty.")
    magnitudes = np.abs(roots)
    maximum = float(np.max(magnitudes))
    candidates = np.flatnonzero(magnitudes >= maximum - 8.0 * np.finfo(float).eps * max(1.0, maximum))
    selected = sorted(
        (complex(roots[index]) for index in candidates),
        key=lambda value: (-value.imag, -value.real),
    )[0]
    return selected


def diagnose_solver(
    *,
    route: RouteData,
    l_value: int,
    j_value: int,
    solver: str,
    A: np.ndarray,
    B: np.ndarray,
    solution: EigenSolution,
    physical_slice: slice,
    coefficients: Mapping[int, np.ndarray],
    clearing_power: int,
    coefficient_scale: float,
    matlab_rho: float,
    matlab_stable: bool,
    matlab_roots: np.ndarray,
    step5_record: Mapping[str, str],
    formula_error: float,
) -> dict[str, Any]:
    tolerance = zero_root_tolerance(solution.roots, solution.finite_mask, A.shape[0])
    zero_mask = np.zeros(solution.roots.shape, dtype=bool)
    if clearing_power > 0:
        zero_mask = solution.finite_mask & (np.abs(solution.roots) <= tolerance)
    retained_indices = np.flatnonzero(solution.finite_mask & ~zero_mask)
    if retained_indices.size == 0:
        raise FloatingPointError(f"No retained roots for {solver}.")
    retained_roots = solution.roots[retained_indices]
    retained_position = int(np.argmax(np.abs(retained_roots)))
    raw_index = int(retained_indices[retained_position])
    root = complex(solution.roots[raw_index])
    rho = float(abs(root))
    physical = solution.right_vectors[physical_slice, raw_index]
    sigma_residual, vector_residual = normalized_direct_residuals(coefficients, root, physical)
    physical_rcond, physical_condition = physical_root_condition(coefficients, root)
    overlap, pencil_rcond, pencil_condition_indicator, pencil_residual = pencil_condition(
        A,
        B,
        root,
        solution.left_vectors[:, raw_index],
        solution.right_vectors[:, raw_index],
    )
    spacing_abs, spacing_relative = nearest_neighbor_spacing(
        root, retained_roots, retained_position
    )
    nearest_matlab = float(np.min(np.abs(matlab_roots - root)))
    matlab_root = dominant_matlab_root(matlab_roots)
    rho_difference = abs(rho - matlab_rho)
    stable = bool(math.isfinite(rho) and rho > 0 and rho < 1.0)
    stored_root = complex(
        float(step5_record["dominant_root_real"]),
        float(step5_record["dominant_root_imag"]),
    )
    return {
        "route_id": route.route_id,
        "workspace_sha256": route.workspace_sha256,
        "matrix_payload_sha256": route.matrix_payload_sha256,
        "l": l_value,
        "j": j_value,
        "solver": solver,
        "matrix_order": int(A.shape[0]),
        "polynomial_degree": int(max(l_value, j_value) + 2),
        "clearing_power": int(clearing_power),
        "coefficient_scale": coefficient_scale,
        "finite_root_count": int(np.count_nonzero(solution.finite_mask)),
        "infinite_root_count": int(solution.infinite_count),
        "removed_zero_root_count": int(np.count_nonzero(zero_mask)),
        "retained_root_count": int(retained_indices.size),
        "zero_root_tolerance": tolerance,
        "rho": rho,
        "dominant_root_real": root.real,
        "dominant_root_imag": root.imag,
        "matlab_rho": matlab_rho,
        "matlab_dominant_root_real": matlab_root.real,
        "matlab_dominant_root_imag": matlab_root.imag,
        "rho_abs_diff_to_matlab": rho_difference,
        "dominant_root_abs_diff_to_nearest_matlab_root": nearest_matlab,
        "step5_stored_compact_rho": float(step5_record["rho_compact"]),
        "rho_abs_diff_to_step5_stored_compact": abs(rho - float(step5_record["rho_compact"])),
        "dominant_root_abs_diff_to_step5_stored_compact": abs(root - stored_root),
        "stable": stable,
        "matlab_stable": matlab_stable,
        "stable_matches_matlab": stable == matlab_stable,
        "rho_gate_1e8": "PASS" if rho_difference <= RHO_TOLERANCE else "FAIL",
        "formula_identity_relative_error": formula_error,
        "normalized_direct_sigma_min_residual": sigma_residual,
        "normalized_direct_vector_residual": vector_residual,
        "direct_residual_gate_1e8": (
            "PASS"
            if max(sigma_residual, vector_residual) <= RESIDUAL_TOLERANCE
            else "FAIL"
        ),
        "dominant_nearest_neighbor_abs_spacing": finite_number(spacing_abs),
        "dominant_nearest_neighbor_relative_spacing": finite_number(spacing_relative),
        "pencil_left_right_B_overlap": overlap,
        "pencil_relative_rcond_fro": pencil_rcond,
        "pencil_condition_indicator_fro": finite_number(pencil_condition_indicator),
        "pencil_eigenpair_residual": pencil_residual,
        "physical_root_relative_rcond": physical_rcond,
        "physical_root_condition_indicator": finite_number(physical_condition),
    }


RESULT_COLUMNS = [
    "route_id",
    "workspace_sha256",
    "matrix_payload_sha256",
    "l",
    "j",
    "solver",
    "matrix_order",
    "polynomial_degree",
    "clearing_power",
    "coefficient_scale",
    "finite_root_count",
    "infinite_root_count",
    "removed_zero_root_count",
    "retained_root_count",
    "zero_root_tolerance",
    "rho",
    "dominant_root_real",
    "dominant_root_imag",
    "matlab_rho",
    "matlab_dominant_root_real",
    "matlab_dominant_root_imag",
    "rho_abs_diff_to_matlab",
    "dominant_root_abs_diff_to_nearest_matlab_root",
    "step5_stored_compact_rho",
    "rho_abs_diff_to_step5_stored_compact",
    "dominant_root_abs_diff_to_step5_stored_compact",
    "stable",
    "matlab_stable",
    "stable_matches_matlab",
    "rho_gate_1e8",
    "formula_identity_relative_error",
    "normalized_direct_sigma_min_residual",
    "normalized_direct_vector_residual",
    "direct_residual_gate_1e8",
    "dominant_nearest_neighbor_abs_spacing",
    "dominant_nearest_neighbor_relative_spacing",
    "pencil_left_right_B_overlap",
    "pencil_relative_rcond_fro",
    "pencil_condition_indicator_fro",
    "pencil_eigenpair_residual",
    "physical_root_relative_rcond",
    "physical_root_condition_indicator",
]


def csv_value(value: Any) -> Any:
    if isinstance(value, float):
        return format(value, ".17g")
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return ""
    return value


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], columns: Sequence[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(columns), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({column: csv_value(row.get(column)) for column in columns})


def solver_summaries(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for solver in SOLVER_ORDER:
        selected = [record for record in records if record["solver"] == solver]
        summaries.append(
            {
                "solver": solver,
                "records": len(selected),
                "rho_gate_pass_count": sum(record["rho_gate_1e8"] == "PASS" for record in selected),
                "rho_gate_fail_count": sum(record["rho_gate_1e8"] == "FAIL" for record in selected),
                "max_rho_abs_diff_to_matlab": max(record["rho_abs_diff_to_matlab"] for record in selected),
                "max_direct_sigma_min_residual": max(
                    record["normalized_direct_sigma_min_residual"] for record in selected
                ),
                "max_direct_vector_residual": max(
                    record["normalized_direct_vector_residual"] for record in selected
                ),
                "stable_mismatch_count": sum(not record["stable_matches_matlab"] for record in selected),
                "min_dominant_relative_spacing": min(
                    record["dominant_nearest_neighbor_relative_spacing"] for record in selected
                ),
                "min_pencil_condition_indicator_fro": min(
                    record["pencil_condition_indicator_fro"] for record in selected
                ),
                "max_pencil_condition_indicator_fro": max(
                    record["pencil_condition_indicator_fro"] for record in selected
                ),
                "min_physical_root_condition_indicator": min(
                    record["physical_root_condition_indicator"] for record in selected
                ),
                "max_physical_root_condition_indicator": max(
                    record["physical_root_condition_indicator"] for record in selected
                ),
                "max_formula_identity_relative_error": max(
                    record["formula_identity_relative_error"] for record in selected
                ),
            }
        )
    return summaries


def point_summary_rows(records: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for route_id in ROUTE_IDS:
        for l_value, j_value in POINTS:
            selected = [
                record
                for record in records
                if record["route_id"] == route_id
                and record["l"] == l_value
                and record["j"] == j_value
            ]
            by_solver = {record["solver"]: record for record in selected}
            row: dict[str, Any] = {
                "route_id": route_id,
                "l": l_value,
                "j": j_value,
                "matlab_rho": selected[0]["matlab_rho"],
                "matlab_stable": selected[0]["matlab_stable"],
            }
            for solver in SOLVER_ORDER:
                record = by_solver[solver]
                prefix = solver
                row[f"{prefix}_rho"] = record["rho"]
                row[f"{prefix}_rho_abs_diff_to_matlab"] = record["rho_abs_diff_to_matlab"]
                row[f"{prefix}_rho_gate_1e8"] = record["rho_gate_1e8"]
                row[f"{prefix}_direct_sigma_residual"] = record[
                    "normalized_direct_sigma_min_residual"
                ]
            rows.append(row)
    return rows


def render_report(
    records: Sequence[Mapping[str, Any]],
    summaries: Sequence[Mapping[str, Any]],
    protected_unchanged: bool,
    payload_equal: bool,
) -> str:
    lines = [
        "# Board20 Step5 第二分区4点数值求解器条件性诊断",
        "",
        "> 状态：`DIAGNOSTIC_ONLY_VALIDATOR_FAIL_UNCHANGED`。本报告不修改步骤4/5任何科学工件，不放宽 `1e-8` 门槛，不覆盖已封签验收器的2项 `FAIL`。",
        "",
        "## 求解器比较摘要",
        "",
        "| 求解器 | 8条路线-点记录中 rho门槛通过 | 最大 |rho-MATLAB| | 最大直接Laurent向量残差 | 稳定分类错配 |",
        "|---|---:|---:|---:|---:|",
    ]
    for summary in summaries:
        lines.append(
            "| {solver} | {passed}/8 | {rho:.17g} | {residual:.17g} | {mismatch} |".format(
                solver=summary["solver"],
                passed=summary["rho_gate_pass_count"],
                rho=summary["max_rho_abs_diff_to_matlab"],
                residual=summary["max_direct_vector_residual"],
                mismatch=summary["stable_mismatch_count"],
            )
        )
    lines.extend(
        [
            "",
            "## 根间距与左/右特征向量条件指标",
            "",
            "| 求解器 | 主导根最小相对最近邻间距 | 矩阵铅笔相对条件指标范围 | 物理Laurent根条件指标范围 |",
            "|---|---:|---:|---:|",
        ]
    )
    for summary in summaries:
        lines.append(
            "| {solver} | {spacing:.17g} | {pencil_min:.17g} -- {pencil_max:.17g} | {physical_min:.17g} -- {physical_max:.17g} |".format(
                solver=summary["solver"],
                spacing=summary["min_dominant_relative_spacing"],
                pencil_min=summary["min_pencil_condition_indicator_fro"],
                pencil_max=summary["max_pencil_condition_indicator_fro"],
                physical_min=summary["min_physical_root_condition_indicator"],
                physical_max=summary["max_physical_root_condition_indicator"],
            )
        )
    lines.extend(
        [
            "",
            "## 逐点 rho 结果",
            "",
            "| 文件身份路线 | (l,j) | MATLAB rho | compact差 | full-q差 | 缩放QZ差 | 未缩放QZ差 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
    )
    for route_id in ROUTE_IDS:
        for point in POINTS:
            selected = [
                record
                for record in records
                if record["route_id"] == route_id
                and (record["l"], record["j"]) == point
            ]
            by_solver = {record["solver"]: record for record in selected}
            lines.append(
                "| {route} | ({l},{j}) | {matlab:.17g} | {compact:.17g} | {full:.17g} | {scaled:.17g} | {unscaled:.17g} |".format(
                    route=route_id,
                    l=point[0],
                    j=point[1],
                    matlab=selected[0]["matlab_rho"],
                    compact=by_solver["compact_ordinary_eig"]["rho_abs_diff_to_matlab"],
                    full=by_solver["full_q_ordinary_eig"]["rho_abs_diff_to_matlab"],
                    scaled=by_solver["generalized_qz_matlab_scaled"]["rho_abs_diff_to_matlab"],
                    unscaled=by_solver["generalized_qz_unscaled_control"]["rho_abs_diff_to_matlab"],
                )
            )
    scaled = next(summary for summary in summaries if summary["solver"] == "generalized_qz_matlab_scaled")
    compact = next(summary for summary in summaries if summary["solver"] == "compact_ordinary_eig")
    inference = (
        "同形缩放QZ在8/8条路线-点记录上通过原 `1e-8` rho门槛，而compact仅0/8通过。"
        "这支持“差异来自线性化/特征值算法及根条件性”的诊断，不是对原验收FAIL的改判。"
        if scaled["rho_gate_pass_count"] == 8 and compact["rho_gate_pass_count"] < 8
        else "不同线性化在至少一个点仍未全部通过原 `1e-8` rho门槛；因此不能把差异单独归因于compact线性化。"
    )
    lines.extend(
        [
            "",
            "## 诊断边界",
            "",
            f"- {inference}",
            f"- 两个路线工作区的文件SHA-256不同，但本诊断所读全部逻辑矩阵逐字节载荷相同：`{payload_equal}`。因此数值结果相同不取消两条文件身份路线。",
            f"- 诊断前后受保护的步骤4/5输入哈希完全不变：`{protected_unchanged}`。",
            "- `pencil_condition_indicator_fro` 是基于左/右特征向量和 Frobenius 范数的相对条件指标；`physical_root_condition_indicator` 另外直接使用 Laurent 矩阵的左/右最小奇异向量与导数。",
            "- 完整数值、根间距、残差和条件指标见 `conditioning_results.csv`。",
            "",
        ]
    )
    return "\n".join(lines)


def write_manifest(paths: Sequence[Path]) -> Path:
    manifest_path = OUTPUT_ROOT / "artifact_manifest.csv"
    rows = [
        {
            "relative_path": path.relative_to(OUTPUT_ROOT).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths, key=lambda item: item.relative_to(OUTPUT_ROOT).as_posix())
    ]
    write_csv(manifest_path, rows, ("relative_path", "bytes", "sha256"))
    return manifest_path


def run_diagnosis(expected_manifest_sha256: str | None) -> dict[str, Any]:
    routes, _contract = load_routes()
    protected_paths = protected_input_paths(routes)
    before_hashes = hash_paths(protected_paths)
    records: list[dict[str, Any]] = []

    for route in routes:
        n = np.asarray(route.matrices["M"]).shape[0]
        for l_value, j_value in POINTS:
            coefficients = build_laurent_coefficients(route.matrices, l_value, j_value)
            formula_error = formula_identity_error(
                route.matrices, coefficients, l_value, j_value
            )
            if formula_error > FORMULA_IDENTITY_TOLERANCE:
                raise FloatingPointError(
                    f"Formula identity failed at {route.route_id} ({l_value},{j_value})."
                )
            polynomial, clearing_power, degree = polynomial_from_laurent(coefficients)
            matlab_rho, matlab_stable, matlab_roots, matlab_degree, matlab_clearing = (
                read_step4_reference(route.route_id, l_value, j_value)
            )
            if degree != matlab_degree or clearing_power != matlab_clearing:
                raise RuntimeError(
                    f"Polynomial identity mismatch at {route.route_id} ({l_value},{j_value})."
                )
            step5_record = load_step5_record(route.route_id, l_value, j_value)

            compact = build_compact_state_matrix(route.matrices, l_value, j_value)
            compact_solution = solve_ordinary(compact)
            records.append(
                diagnose_solver(
                    route=route,
                    l_value=l_value,
                    j_value=j_value,
                    solver="compact_ordinary_eig",
                    A=compact,
                    B=np.eye(compact.shape[0]),
                    solution=compact_solution,
                    physical_slice=slice(0, n),
                    coefficients=coefficients,
                    clearing_power=clearing_power,
                    coefficient_scale=1.0,
                    matlab_rho=matlab_rho,
                    matlab_stable=matlab_stable,
                    matlab_roots=matlab_roots,
                    step5_record=step5_record,
                    formula_error=formula_error,
                )
            )

            full_q = build_full_q_state_matrix(polynomial)
            full_solution = solve_ordinary(full_q)
            records.append(
                diagnose_solver(
                    route=route,
                    l_value=l_value,
                    j_value=j_value,
                    solver="full_q_ordinary_eig",
                    A=full_q,
                    B=np.eye(full_q.shape[0]),
                    solution=full_solution,
                    physical_slice=slice(0, n),
                    coefficients=coefficients,
                    clearing_power=clearing_power,
                    coefficient_scale=1.0,
                    matlab_rho=matlab_rho,
                    matlab_stable=matlab_stable,
                    matlab_roots=matlab_roots,
                    step5_record=step5_record,
                    formula_error=formula_error,
                )
            )

            for solver, scaled in (
                ("generalized_qz_matlab_scaled", True),
                ("generalized_qz_unscaled_control", False),
            ):
                A, B, coefficient_scale = build_generalized_first_companion(
                    polynomial, coefficient_scaled=scaled
                )
                qz_solution = solve_generalized(A, B)
                records.append(
                    diagnose_solver(
                        route=route,
                        l_value=l_value,
                        j_value=j_value,
                        solver=solver,
                        A=A,
                        B=B,
                        solution=qz_solution,
                        physical_slice=slice(A.shape[0] - n, A.shape[0]),
                        coefficients=coefficients,
                        clearing_power=clearing_power,
                        coefficient_scale=coefficient_scale,
                        matlab_rho=matlab_rho,
                        matlab_stable=matlab_stable,
                        matlab_roots=matlab_roots,
                        step5_record=step5_record,
                        formula_error=formula_error,
                    )
                )

    records.sort(
        key=lambda record: (
            ROUTE_IDS.index(record["route_id"]),
            POINTS.index((record["l"], record["j"])),
            SOLVER_ORDER.index(record["solver"]),
        )
    )
    after_hashes = hash_paths(protected_paths)
    if before_hashes != after_hashes:
        changed = sorted(path for path in before_hashes if before_hashes[path] != after_hashes.get(path))
        raise RuntimeError(f"Protected Step-4/5 input changed during diagnosis: {changed}")

    payload_equal = len({route.matrix_payload_sha256 for route in routes}) == 1
    summaries = solver_summaries(records)
    points = point_summary_rows(records)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    results_path = OUTPUT_ROOT / "conditioning_results.csv"
    point_path = OUTPUT_ROOT / "point_summary.csv"
    json_path = OUTPUT_ROOT / "diagnostic.json"
    report_path = OUTPUT_ROOT / "report.md"
    status_path = OUTPUT_ROOT / "run_status.json"
    write_csv(results_path, records, RESULT_COLUMNS)
    point_columns = list(points[0])
    write_csv(point_path, points, point_columns)

    diagnostic = {
        "schema_version": "board20_step5_solver_conditioning_v1",
        "status": "DIAGNOSTIC_ONLY_VALIDATOR_FAIL_UNCHANGED",
        "scope": {
            "routes": list(ROUTE_IDS),
            "unique_points": [list(point) for point in POINTS],
            "route_point_records": len(ROUTE_IDS) * len(POINTS),
            "solver_records": len(records),
        },
        "fixed_gates": {
            "rho_abs_diff_to_matlab": RHO_TOLERANCE,
            "direct_laurent_residual": RESIDUAL_TOLERANCE,
            "formula_identity": FORMULA_IDENTITY_TOLERANCE,
            "gate_was_not_changed": True,
        },
        "algorithm_contract": {
            "compact_ordinary_eig": "scalar-delay state [q_k,q_(k-1),u1 history,u2 history], ordinary scipy.linalg.eig",
            "full_q_ordinary_eig": "full q history first companion with leading coefficient solve, ordinary scipy.linalg.eig",
            "generalized_qz_matlab_scaled": "independently encoded dense first companion A-lambda B, all polynomial coefficients divided by max Frobenius coefficient norm, scipy generalized eig/QZ",
            "generalized_qz_unscaled_control": "same independently encoded generalized pencil without coefficient scaling",
            "matlab_rho_is_comparison_only": True,
        },
        "sealed_identities": {
            "diagnostic_script_sha256": sha256_file(DIAGNOSTIC_SCRIPT_PATH),
            "compute_contract_sha256": EXPECTED_COMPUTE_CONTRACT_SHA256,
            "route_manifest_sha256": EXPECTED_ROUTE_MANIFEST_SHA256,
            "compute_script_sha256": EXPECTED_COMPUTE_SCRIPT_SHA256,
            "routes": [
                {
                    "route_id": route.route_id,
                    "workspace_sha256": route.workspace_sha256,
                    "matrix_payload_sha256": route.matrix_payload_sha256,
                }
                for route in routes
            ],
            "two_route_matrix_payloads_are_identical": payload_equal,
        },
        "solver_summaries": summaries,
        "protected_input_hashes_before": before_hashes,
        "protected_input_hashes_after": after_hashes,
        "protected_inputs_unchanged": before_hashes == after_hashes,
        "validator_verdict": {
            "prior_full_postcheck_status": "FAIL",
            "prior_failed_checks": ["S5-POST-0095", "S5-POST-0108"],
            "overridden": False,
        },
        "records": records,
    }
    write_json(json_path, diagnostic)
    report_path.write_text(
        render_report(records, summaries, before_hashes == after_hashes, payload_equal),
        encoding="utf-8",
        newline="\n",
    )
    run_status = {
        "schema_version": "board20_step5_solver_conditioning_run_v1",
        "status": "PASS_DIAGNOSTIC_COMPLETE_VALIDATOR_FAIL_UNCHANGED",
        "diagnostic_script_sha256": sha256_file(DIAGNOSTIC_SCRIPT_PATH),
        "route_count": len(routes),
        "unique_point_count": len(POINTS),
        "route_point_count": len(routes) * len(POINTS),
        "solver_record_count": len(records),
        "protected_inputs_unchanged": before_hashes == after_hashes,
        "validator_verdict_overridden": False,
        "solver_summaries": summaries,
    }
    write_json(status_path, run_status)
    manifest_path = write_manifest(
        (results_path, point_path, json_path, report_path, status_path)
    )
    manifest_hash = sha256_file(manifest_path)

    repeatability: dict[str, Any] | None = None
    if expected_manifest_sha256 is not None:
        expected = expected_manifest_sha256.upper()
        repeatability = {
            "schema_version": "board20_step5_solver_conditioning_repeatability_v1",
            "baseline_artifact_manifest_sha256": expected,
            "repeat_artifact_manifest_sha256": manifest_hash,
            "scientific_artifacts_match": expected == manifest_hash,
            "status": "PASS" if expected == manifest_hash else "FAIL",
        }
        write_json(OUTPUT_ROOT / "repeatability_check.json", repeatability)
        if expected != manifest_hash:
            raise RuntimeError("Repeated scientific artifact manifest hash changed.")

    return {
        "status": run_status["status"],
        "solver_records": len(records),
        "artifact_manifest_sha256": manifest_hash,
        "repeatability": repeatability,
        "solver_summaries": summaries,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--expected-manifest-sha256",
        help="On the second independent run, require the scientific artifact manifest to match this first-run SHA-256.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    summary = run_diagnosis(args.expected_manifest_sha256)
    print(canonical_json(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

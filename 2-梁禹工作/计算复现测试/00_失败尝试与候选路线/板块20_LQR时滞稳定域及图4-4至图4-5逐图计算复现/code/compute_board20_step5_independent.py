#!/usr/bin/env python
"""Independent Board-20 delay-spectrum computation.

The scientific computation in this process reads exactly two kinds of input:

1. the sealed route-identity manifest; and
2. the five sealed step-2 MATLAB v7.3 workspaces named by the compute contract.

No MATLAB spectral-radius, pole, stability-mask, boundary, or plotting result is
an input.  The primary solver is an explicit time-domain state matrix with two
full displacement blocks and rank-one scalar delay lines.  During the real
41-point pilot, every point is also solved with a conventional full-q history
companion matrix.  Their only permissible spectral-order difference is at
z=0, which lies outside the original Laurent characteristic equation.
"""

from __future__ import annotations

import os

# Fix numerical-library threading before importing NumPy/SciPy.  This makes
# timing and checkpoint behaviour reproducible and avoids nested BLAS workers.
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ.setdefault("MKL_NUM_THREADS", "1")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

import argparse
import csv
import hashlib
import json
import logging
import math
import platform
import shutil
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

import h5py
import numpy as np
import scipy
import scipy.linalg as sla
from scipy.optimize import linear_sum_assignment


CONTRACT_FILENAME = "board20_step5_compute_contract.json"
ROUTE_MANIFEST_FILENAME = "board20_step4_route_manifest.json"
SCRIPT_FILENAME = "compute_board20_step5_independent.py"
CSV_FIELDS = [
    "route_id",
    "route_role",
    "declared_method",
    "route_formula",
    "l",
    "j",
    "matrix_order",
    "compact_order",
    "full_q_order",
    "poly_degree",
    "clearing_power",
    "compact_raw_root_count",
    "compact_zero_root_tolerance",
    "compact_removed_zero_count",
    "compact_retained_root_count",
    "rho_compact",
    "stable_compact",
    "critical_compact",
    "max_polynomial_residual_compact",
    "max_laurent_residual_compact",
    "full_crosscheck_performed",
    "full_raw_root_count",
    "full_zero_root_tolerance",
    "full_removed_zero_count",
    "full_retained_root_count",
    "rho_full",
    "stable_full",
    "max_polynomial_residual_full",
    "max_laurent_residual_full",
    "compact_full_rho_abs_diff",
    "root_match_max_relative_diff",
    "near_unit_root_match_max_relative_diff",
    "extra_full_roots_are_zero",
    "strict_root_set_status",
    "theoretical_extra_zero_count",
    "observed_extra_zero_count",
    "full_q_origin_multiplicity_splitting_count",
    "full_q_origin_multiplicity_splitting_max_abs",
    "direct_formula_coefficient_relative_difference",
    "dominant_root_real",
    "dominant_root_imag",
    "point_status",
    "failure_code",
]
RUNTIME_CSV_FIELDS = ["route_id", "l", "j", "elapsed_seconds", "point_status"]


@dataclass(frozen=True)
class RouteSpec:
    route_id: str
    route_name: str
    route_role: str
    declared_method: str
    division: str
    route_formula: str
    workspace_relpath: str
    workspace_sha256: str
    matrix_variables: dict[str, str]
    delay_dofs: tuple[int, int]
    pilot_points: tuple[tuple[int, int], ...]


@dataclass(frozen=True)
class Matrices:
    M: np.ndarray
    C1: np.ndarray
    K1: np.ndarray
    C2: np.ndarray
    K2: np.ndarray
    al: np.ndarray
    dt: float
    S: np.ndarray | None = None
    DeltaC: np.ndarray | None = None
    DeltaK: np.ndarray | None = None


@dataclass(frozen=True)
class Components:
    T: np.ndarray
    base_zero: np.ndarray
    base_minus_one: np.ndarray
    delayed_zero: np.ndarray
    delayed_minus_one: np.ndarray
    feedback_zero: np.ndarray
    feedback_minus_one: np.ndarray


@dataclass
class Spectrum:
    raw: np.ndarray
    retained: np.ndarray
    polynomial_residual: np.ndarray
    laurent_residual: np.ndarray
    zero_root_tolerance: float
    removed_zero_count: int
    rho: float
    stable: bool
    critical: bool
    dominant_root: complex
    nonfinite_root_count: int


@dataclass
class PointResult:
    summary: dict[str, Any]
    compact_raw: np.ndarray
    compact_retained: np.ndarray
    compact_polynomial_residual: np.ndarray
    compact_laurent_residual: np.ndarray
    full_raw: np.ndarray
    full_retained: np.ndarray
    full_polynomial_residual: np.ndarray
    full_laurent_residual: np.ndarray


def utc_now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def replace_with_retry(source: Path, destination: Path, attempts: int = 20) -> None:
    """Atomically replace a file, tolerating only transient Windows file locks."""
    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 >= attempts:
                raise
            # Antivirus/indexer handles can briefly deny replacement even
            # after both Python handles are closed.  This retry changes no
            # scientific bytes and never falls back to a non-atomic write.
            time.sleep(min(0.05 * (2**attempt), 1.0))


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("wb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())
    replace_with_retry(temporary, path)


def atomic_write_json(path: Path, value: Any) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_bytes(path, text.encode("utf-8"))


def atomic_write_csv(path: Path, rows: Sequence[dict[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fields), extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({key: json_scalar(row.get(key, "")) for key in fields})
        handle.flush()
        os.fsync(handle.fileno())
    replace_with_retry(temporary, path)


def json_scalar(value: Any) -> Any:
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
    return value


def safe_relative_path(root: Path, relpath: str, required_prefix: str) -> Path:
    candidate = (root / Path(relpath)).resolve()
    resolved_root = root.resolve()
    try:
        relative = candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"Path escapes Board-20 root: {relpath}") from exc
    normalized = relative.as_posix()
    prefix = required_prefix.rstrip("/") + "/"
    if not normalized.startswith(prefix):
        raise ValueError(
            f"Path {relpath!r} is outside the required input prefix {required_prefix!r}."
        )
    return candidate


def code_directory() -> Path:
    return Path(__file__).resolve().parent


def board_root() -> Path:
    return code_directory().parent


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_contract_and_routes() -> tuple[Path, dict[str, Any], dict[str, Any], list[RouteSpec]]:
    root = board_root()
    contract_path = code_directory() / CONTRACT_FILENAME
    manifest_path = code_directory() / ROUTE_MANIFEST_FILENAME
    contract = load_json(contract_path)
    if sha256_file(manifest_path) != contract["route_manifest_sha256"]:
        raise ValueError("The route manifest SHA-256 does not match the compute contract.")
    manifest = load_json(manifest_path)
    manifest_routes = {item["route_id"]: item for item in manifest["routes"]}
    contract_routes = contract["routes"]
    expected_ids = [item["route_id"] for item in contract_routes]
    if set(expected_ids) != set(manifest_routes) or len(expected_ids) != 5:
        raise ValueError("The sealed calculable route identity is not exactly the expected five routes.")

    specs: list[RouteSpec] = []
    for item in contract_routes:
        route_id = item["route_id"]
        source = manifest_routes[route_id]
        comparisons = {
            "route_role": item["route_role"],
            "route_formula": item["route_formula"],
            "workspace_relpath": item["workspace_relpath"],
        }
        for field, expected in comparisons.items():
            if source[field] != expected:
                raise ValueError(f"Manifest/contract mismatch for {route_id}.{field}.")
        matrix_map = {
            key: source["matrix_variable_map"][key]
            for key in item["matrix_variables"]
        }
        if matrix_map != item["matrix_variables"]:
            raise ValueError(f"Manifest/contract matrix-variable mismatch for {route_id}.")
        workspace_contracts = [
            entry
            for entry in source["file_contracts"]
            if entry.get("role") == "workspace_complete"
        ]
        if len(workspace_contracts) != 1:
            raise ValueError(f"Expected one workspace_complete seal for {route_id}.")
        if workspace_contracts[0]["sha256"] != item["workspace_sha256"]:
            raise ValueError(f"Workspace seal mismatch in manifest for {route_id}.")
        workspace = safe_relative_path(root, item["workspace_relpath"], "outputs/step2_runs")
        if not workspace.is_file():
            raise FileNotFoundError(workspace)
        if sha256_file(workspace) != item["workspace_sha256"]:
            raise ValueError(f"Current workspace hash mismatch for {route_id}.")
        points = tuple(tuple(map(int, pair)) for pair in contract["pilot_points"][route_id])
        specs.append(
            RouteSpec(
                route_id=route_id,
                route_name=source["route_name"],
                route_role=item["route_role"],
                declared_method=source["declared_method"],
                division=source["division"],
                route_formula=item["route_formula"],
                workspace_relpath=item["workspace_relpath"],
                workspace_sha256=item["workspace_sha256"],
                matrix_variables=dict(item["matrix_variables"]),
                delay_dofs=tuple(index - 1 for index in item["delay_dofs_matlab_1_based"]),
                pilot_points=points,
            )
        )
    return root, contract, manifest, specs


def read_matlab_v73_numeric(handle: h5py.File, variable_name: str) -> np.ndarray:
    if variable_name not in handle:
        raise KeyError(f"Required sealed-workspace variable {variable_name!r} is missing.")
    dataset = handle[variable_name]
    if not isinstance(dataset, h5py.Dataset):
        raise TypeError(f"{variable_name!r} is not an HDF5 numeric dataset.")
    if dataset.dtype.kind not in "biuf":
        raise TypeError(f"{variable_name!r} has non-real-numeric HDF5 dtype {dataset.dtype}.")
    # MATLAB v7.3 stores dimensions in reverse order.  The transpose is
    # essential for non-square S and is retained for every numeric matrix.
    value = np.asarray(dataset, dtype=np.float64).T.copy()
    if not np.all(np.isfinite(value)):
        raise ValueError(f"{variable_name!r} contains NaN or Inf.")
    return value


def load_route_matrices(root: Path, spec: RouteSpec) -> Matrices:
    workspace = safe_relative_path(root, spec.workspace_relpath, "outputs/step2_runs")
    if sha256_file(workspace) != spec.workspace_sha256:
        raise ValueError(f"Workspace changed before matrix load: {spec.route_id}.")
    loaded: dict[str, np.ndarray] = {}
    with h5py.File(workspace, "r") as handle:
        # Only the explicitly contracted matrix variables are accessed.  No
        # workspace result variable is enumerated or loaded.
        for logical_name, variable_name in spec.matrix_variables.items():
            loaded[logical_name] = read_matlab_v73_numeric(handle, variable_name)

    dt_array = loaded.pop("dt")
    if dt_array.size != 1:
        raise ValueError(f"dt must be scalar for {spec.route_id}.")
    dt = float(dt_array.reshape(-1)[0])
    if not (math.isfinite(dt) and dt > 0):
        raise ValueError(f"dt must be finite and positive for {spec.route_id}.")

    n = loaded["M"].shape[0]
    for name in ("M", "C1", "K1", "C2", "K2", "al"):
        if loaded[name].shape != (n, n):
            raise ValueError(f"{spec.route_id}.{name} is not {n}x{n}.")
    if max(spec.delay_dofs) >= n:
        raise ValueError(f"Delay DOF is outside the matrix order for {spec.route_id}.")
    if np.linalg.cond(loaded["al"]) >= 1.0 / np.finfo(float).eps:
        raise ValueError(f"al is numerically singular for {spec.route_id}.")

    if spec.route_formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        for name in ("S", "DeltaC", "DeltaK"):
            if name not in loaded:
                raise ValueError(f"{name} is required by {spec.route_id}.")
        feedback_order = loaded["S"].shape[0]
        if loaded["S"].shape[1] != n:
            raise ValueError(f"Restored S must have {n} columns for {spec.route_id}.")
        if loaded["DeltaC"].shape != (feedback_order, feedback_order):
            raise ValueError(f"DeltaC shape mismatch for {spec.route_id}.")
        if loaded["DeltaK"].shape != (feedback_order, feedback_order):
            raise ValueError(f"DeltaK shape mismatch for {spec.route_id}.")
    else:
        if any(name in loaded for name in ("S", "DeltaC", "DeltaK")):
            raise ValueError(f"Unexpected feedback matrices in {spec.route_id} contract.")

    return Matrices(
        M=loaded["M"],
        C1=loaded["C1"],
        K1=loaded["K1"],
        C2=loaded["C2"],
        K2=loaded["K2"],
        al=loaded["al"],
        dt=dt,
        S=loaded.get("S"),
        DeltaC=loaded.get("DeltaC"),
        DeltaK=loaded.get("DeltaK"),
    )


def build_components(matrices: Matrices, route_formula: str) -> Components:
    # MATLAB right division M/al means X*al=M.  This solve is the required
    # independent Python equivalent and deliberately avoids inverse(al).
    mass_term = sla.solve(
        matrices.al.T,
        matrices.M.T,
        assume_a="gen",
        check_finite=True,
    ).T / (matrices.dt**2)
    base_zero = -2.0 * mass_term + matrices.C1 / matrices.dt + matrices.K1
    base_minus_one = mass_term - matrices.C1 / matrices.dt
    delayed_zero = matrices.C2 / matrices.dt + matrices.K2
    delayed_minus_one = -matrices.C2 / matrices.dt
    n = matrices.M.shape[0]
    feedback_zero = np.zeros((n, n), dtype=float)
    feedback_minus_one = np.zeros((n, n), dtype=float)
    if route_formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        assert matrices.S is not None
        assert matrices.DeltaC is not None
        assert matrices.DeltaK is not None
        feedback_zero = matrices.S.T @ (
            matrices.DeltaC / matrices.dt + matrices.DeltaK
        ) @ matrices.S
        feedback_minus_one = matrices.S.T @ (
            -matrices.DeltaC / matrices.dt
        ) @ matrices.S
    return Components(
        T=mass_term,
        base_zero=base_zero,
        base_minus_one=base_minus_one,
        delayed_zero=delayed_zero,
        delayed_minus_one=delayed_minus_one,
        feedback_zero=feedback_zero,
        feedback_minus_one=feedback_minus_one,
    )


def validate_delay(value: int, name: str) -> int:
    if isinstance(value, bool) or int(value) != value or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer sample delay.")
    return int(value)


def selector(n: int, index: int) -> np.ndarray:
    result = np.zeros((n, n), dtype=float)
    result[index, index] = 1.0
    return result


def add_coefficient(store: dict[int, np.ndarray], exponent: int, value: np.ndarray) -> None:
    if exponent in store:
        store[exponent] = store[exponent] + value
    else:
        store[exponent] = np.array(value, dtype=float, copy=True)


def build_coefficient_map(
    spec: RouteSpec,
    components: Components,
    l: int,
    j: int,
) -> dict[int, np.ndarray]:
    l = validate_delay(l, "l")
    j = validate_delay(j, "j")
    n = components.T.shape[0]
    coefficients: dict[int, np.ndarray] = {}
    add_coefficient(coefficients, 1, components.T)
    add_coefficient(coefficients, 0, components.base_zero)
    add_coefficient(coefficients, -1, components.base_minus_one)
    for delay, dof in zip((l, j), spec.delay_dofs):
        channel_selector = selector(n, dof)
        if spec.route_formula == "ORI_DIV1_H_RIGHT":
            at_delay = components.delayed_zero @ channel_selector
            after_delay = components.delayed_minus_one @ channel_selector
        elif spec.route_formula in (
            "GUYAN_DIV1_H_LEFT",
            "DIV2_H_LEFT_FEEDBACK_OUTSIDE",
        ):
            at_delay = channel_selector @ components.delayed_zero
            after_delay = channel_selector @ components.delayed_minus_one
        else:
            raise ValueError(f"Unsupported route formula {spec.route_formula!r}.")
        add_coefficient(coefficients, -delay, at_delay)
        add_coefficient(coefficients, -(delay + 1), after_delay)
    if spec.route_formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        add_coefficient(coefficients, 0, components.feedback_zero)
        add_coefficient(coefficients, -1, components.feedback_minus_one)
    return {
        exponent: matrix
        for exponent, matrix in sorted(coefficients.items())
        if np.any(matrix != 0.0)
    }


def direct_laurent_terms(
    spec: RouteSpec,
    components: Components,
    l: int,
    j: int,
) -> list[tuple[int, np.ndarray]]:
    """Construct direct formula terms without coefficient-bin consolidation."""
    n = components.T.shape[0]
    terms: list[tuple[int, np.ndarray]] = [
        (1, components.T),
        (0, components.base_zero),
        (-1, components.base_minus_one),
    ]
    for delay, dof in zip((l, j), spec.delay_dofs):
        channel_selector = selector(n, dof)
        if spec.route_formula == "ORI_DIV1_H_RIGHT":
            terms.append((-delay, components.delayed_zero @ channel_selector))
            terms.append((-(delay + 1), components.delayed_minus_one @ channel_selector))
        else:
            terms.append((-delay, channel_selector @ components.delayed_zero))
            terms.append((-(delay + 1), channel_selector @ components.delayed_minus_one))
    if spec.route_formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        # The feedback is intentionally outside H: its exponents never depend
        # on l or j.
        terms.append((0, components.feedback_zero))
        terms.append((-1, components.feedback_minus_one))
    return [(exponent, matrix) for exponent, matrix in terms if np.any(matrix != 0.0)]


def polynomial_from_coefficients(
    coefficients: dict[int, np.ndarray],
) -> tuple[list[np.ndarray], int, int]:
    exponents = sorted(coefficients)
    if not exponents:
        raise ValueError("The characteristic matrix is identically zero.")
    clearing_power = max(0, -exponents[0])
    degree = exponents[-1] + clearing_power
    n = next(iter(coefficients.values())).shape[0]
    polynomial = [np.zeros((n, n), dtype=float) for _ in range(degree + 1)]
    for exponent, matrix in coefficients.items():
        polynomial[exponent + clearing_power] += matrix
    while len(polynomial) > 1 and not np.any(polynomial[-1] != 0.0):
        polynomial.pop()
    degree = len(polynomial) - 1
    if degree < 1:
        raise ValueError("The cleared characteristic matrix has no positive degree.")
    return polynomial, clearing_power, degree


def evaluate_coefficient_matrix(coefficients: dict[int, np.ndarray], z: complex) -> np.ndarray:
    n = next(iter(coefficients.values())).shape[0]
    value = np.zeros((n, n), dtype=np.complex128)
    for exponent, matrix in coefficients.items():
        value += (z**exponent) * matrix
    return value


def evaluate_direct_matrix(
    spec: RouteSpec,
    components: Components,
    l: int,
    j: int,
    z: complex,
) -> np.ndarray:
    n = components.T.shape[0]
    value = (
        components.T * z
        + components.base_zero
        + components.base_minus_one / z
    ).astype(np.complex128)
    delays = (l, j)
    if spec.route_formula == "ORI_DIV1_H_RIGHT":
        h_zero = np.zeros((n, n), dtype=np.complex128)
        h_minus = np.zeros((n, n), dtype=np.complex128)
        for delay, dof in zip(delays, spec.delay_dofs):
            h_zero[dof, dof] += z ** (-delay)
            h_minus[dof, dof] += z ** (-(delay + 1))
        value += components.delayed_zero @ h_zero
        value += components.delayed_minus_one @ h_minus
    else:
        h_zero = np.zeros((n, n), dtype=np.complex128)
        h_minus = np.zeros((n, n), dtype=np.complex128)
        for delay, dof in zip(delays, spec.delay_dofs):
            h_zero[dof, dof] += z ** (-delay)
            h_minus[dof, dof] += z ** (-(delay + 1))
        value += h_zero @ components.delayed_zero
        value += h_minus @ components.delayed_minus_one
    if spec.route_formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        value += components.feedback_zero + components.feedback_minus_one / z
    return value


def formula_coefficient_relative_difference(
    spec: RouteSpec,
    components: Components,
    coefficients: dict[int, np.ndarray],
    l: int,
    j: int,
) -> float:
    probes = (0.83 + 0.17j, 1.12 - 0.13j, -0.71 + 0.29j)
    differences = []
    for z in probes:
        first = evaluate_coefficient_matrix(coefficients, z)
        second = evaluate_direct_matrix(spec, components, l, j, z)
        differences.append(
            float(np.linalg.norm(first - second, ord="fro") / max(1.0, np.linalg.norm(second, ord="fro")))
        )
    return max(differences)


def build_compact_state_matrix(
    spec: RouteSpec,
    components: Components,
    l: int,
    j: int,
) -> np.ndarray:
    """Build [q_k,q_(k-1),two scalar-delay chains], order 2*n+l+j."""
    n = components.T.shape[0]
    delays = (validate_delay(l, "l"), validate_delay(j, "j"))
    order = 2 * n + sum(delays)
    rhs = np.zeros((n, order), dtype=float)
    rhs[:, :n] = -(components.base_zero + components.feedback_zero)
    rhs[:, n : 2 * n] = -(components.base_minus_one + components.feedback_minus_one)

    chain_offsets = (2 * n, 2 * n + delays[0])
    for channel, (delay, dof, offset) in enumerate(
        zip(delays, spec.delay_dofs, chain_offsets)
    ):
        if spec.route_formula == "ORI_DIV1_H_RIGHT":
            vector = np.zeros(n, dtype=float)
            vector[dof] = 1.0
            output_zero = components.delayed_zero[:, dof]
            output_minus = components.delayed_minus_one[:, dof]
            if delay == 0:
                rhs[:, :n] -= np.outer(output_zero, vector)
                rhs[:, n : 2 * n] -= np.outer(output_minus, vector)
            elif delay == 1:
                rhs[:, n : 2 * n] -= np.outer(output_zero, vector)
                rhs[:, offset] -= output_minus
            else:
                rhs[:, offset + delay - 2] -= output_zero
                rhs[:, offset + delay - 1] -= output_minus
        else:
            input_zero = components.delayed_zero[dof, :]
            input_minus = components.delayed_minus_one[dof, :]
            output = np.zeros(n, dtype=float)
            output[dof] = 1.0
            if delay == 0:
                rhs[:, :n] -= np.outer(output, input_zero)
                rhs[:, n : 2 * n] -= np.outer(output, input_minus)
            else:
                rhs[:, offset + delay - 1] -= output

    transition = np.zeros((order, order), dtype=float)
    transition[:n, :] = sla.solve(
        components.T,
        rhs,
        assume_a="gen",
        check_finite=False,
    )
    transition[n : 2 * n, :n] = np.eye(n)

    for delay, dof, offset in zip(delays, spec.delay_dofs, chain_offsets):
        if delay == 0:
            continue
        if spec.route_formula == "ORI_DIV1_H_RIGHT":
            # At k+1 the first appended older value is y_(k-1), already
            # present as the selected component of q_(k-1).
            transition[offset, n + dof] = 1.0
        else:
            # At k+1 the first appended value is u_k.
            transition[offset, :n] = components.delayed_zero[dof, :]
            transition[offset, n : 2 * n] = components.delayed_minus_one[dof, :]
        for position in range(1, delay):
            transition[offset + position, offset + position - 1] = 1.0
    if transition.shape != (2 * n + l + j, 2 * n + l + j):
        raise AssertionError("Compact augmentation order is not 2*n+l+j.")
    return transition


def build_full_q_history_matrix(
    components: Components,
    coefficients: dict[int, np.ndarray],
    l: int,
    j: int,
) -> np.ndarray:
    """Ordinary full-coordinate history companion used only for crosschecks."""
    n = components.T.shape[0]
    block_count = max(l, j) + 2
    order = n * block_count
    rhs = np.zeros((n, order), dtype=float)
    for exponent, matrix in coefficients.items():
        if exponent == 1:
            continue
        lag = -exponent
        if lag < 0 or lag >= block_count:
            raise AssertionError(f"Unexpected Laurent exponent {exponent}.")
        rhs[:, lag * n : (lag + 1) * n] -= matrix
    transition = np.zeros((order, order), dtype=float)
    transition[:n, :] = sla.solve(
        components.T,
        rhs,
        assume_a="gen",
        check_finite=False,
    )
    if block_count > 1:
        transition[n:, :-n] = np.eye(n * (block_count - 1))
    return transition


def polynomial_residual(
    polynomial: Sequence[np.ndarray],
    root: complex,
    vector: np.ndarray,
) -> float:
    vector_norm = float(np.linalg.norm(vector))
    if not (math.isfinite(vector_norm) and vector_norm > 0):
        return math.inf
    value = polynomial[-1] @ vector
    denominator = float(np.linalg.norm(polynomial[-1], ord="fro")) * vector_norm
    for coefficient in reversed(polynomial[:-1]):
        value = root * value + coefficient @ vector
        denominator = abs(root) * denominator + float(np.linalg.norm(coefficient, ord="fro")) * vector_norm
    if not (math.isfinite(denominator) and denominator > 0):
        return math.inf
    return float(np.linalg.norm(value) / denominator)


def direct_laurent_residual(
    terms: Sequence[tuple[int, np.ndarray]],
    root: complex,
    vector: np.ndarray,
) -> float:
    vector_norm = float(np.linalg.norm(vector))
    root_abs = abs(root)
    if not (math.isfinite(vector_norm) and vector_norm > 0 and root_abs > 0):
        return math.inf
    log_abs = math.log(root_abs)
    phase = math.atan2(root.imag, root.real)
    active: list[tuple[int, np.ndarray, float]] = []
    log_scales: list[float] = []
    for exponent, matrix in terms:
        matrix_norm = float(np.linalg.norm(matrix, ord="fro"))
        if matrix_norm == 0:
            continue
        log_scale = exponent * log_abs + math.log(matrix_norm)
        active.append((exponent, matrix, matrix_norm))
        log_scales.append(log_scale)
    if not active:
        return math.inf
    reference = max(log_scales)
    value = np.zeros_like(vector, dtype=np.complex128)
    denominator = 0.0
    for exponent, matrix, matrix_norm in active:
        amplitude = math.exp(exponent * log_abs + math.log(matrix_norm) - reference)
        phase_factor = complex(math.cos(exponent * phase), math.sin(exponent * phase))
        # Divide by matrix_norm so the amplitude-times-matrix product equals
        # z**exponent * matrix under the common reference scaling.
        value += (amplitude * phase_factor / matrix_norm) * (matrix @ vector)
        denominator += amplitude * vector_norm
    if not (math.isfinite(denominator) and denominator > 0):
        return math.inf
    return float(np.linalg.norm(value) / denominator)


def solve_spectrum(
    transition: np.ndarray,
    n: int,
    polynomial: Sequence[np.ndarray],
    direct_terms: Sequence[tuple[int, np.ndarray]],
    clearing_power: int,
) -> Spectrum:
    roots, vectors = sla.eig(
        transition,
        left=False,
        right=True,
        overwrite_a=True,
        check_finite=False,
    )
    roots = np.asarray(roots, dtype=np.complex128).reshape(-1)
    finite = np.isfinite(roots.real) & np.isfinite(roots.imag)
    finite_abs = np.abs(roots[finite])
    finite_nonzero = finite_abs[finite_abs > 0]
    scale = max(1.0, float(np.median(finite_nonzero))) if finite_nonzero.size else 1.0
    zero_tolerance = max(
        1e-12,
        100.0 * np.finfo(float).eps * max(1, transition.shape[0]) * scale,
    )
    zero_mask = np.zeros(roots.shape, dtype=bool)
    if clearing_power > 0:
        zero_mask = finite & (np.abs(roots) <= zero_tolerance)
    retained_indices = np.flatnonzero(finite & ~zero_mask)
    retained = roots[retained_indices]
    if retained.size == 0:
        raise FloatingPointError("No finite nonzero root remains.")
    poly = np.empty(retained.size, dtype=float)
    laurent = np.empty(retained.size, dtype=float)
    for output_index, root_index in enumerate(retained_indices):
        physical = vectors[:n, root_index]
        poly[output_index] = polynomial_residual(polynomial, roots[root_index], physical)
        laurent[output_index] = direct_laurent_residual(direct_terms, roots[root_index], physical)
    magnitudes = np.abs(retained)
    dominant_index = int(np.argmax(magnitudes))
    rho = float(magnitudes[dominant_index])
    if not (math.isfinite(rho) and rho > 0):
        raise FloatingPointError("rho is not finite and strictly positive.")
    return Spectrum(
        raw=roots,
        retained=retained,
        polynomial_residual=poly,
        laurent_residual=laurent,
        zero_root_tolerance=float(zero_tolerance),
        removed_zero_count=int(np.count_nonzero(zero_mask)),
        rho=rho,
        stable=bool(rho < 1.0),
        critical=bool(abs(rho - 1.0) <= 1e-8),
        dominant_root=complex(retained[dominant_index]),
        nonfinite_root_count=int(np.count_nonzero(~finite)),
    )


def match_root_sets(first: np.ndarray, second: np.ndarray) -> float:
    if first.size == 0 and second.size == 0:
        return 0.0
    if first.size != second.size or first.size == 0:
        return math.inf
    denominator = np.maximum(
        1.0,
        np.maximum(np.abs(first)[:, None], np.abs(second)[None, :]),
    )
    costs = np.abs(first[:, None] - second[None, :]) / denominator
    row_indices, column_indices = linear_sum_assignment(costs)
    return float(np.max(costs[row_indices, column_indices]))


def rectangular_root_diagnostic(
    compact_roots: np.ndarray,
    full_roots: np.ndarray,
) -> tuple[float, np.ndarray]:
    """Match the compact set into a larger full set and return unmatched full roots."""
    if compact_roots.size == 0 or full_roots.size < compact_roots.size:
        return math.inf, np.asarray(full_roots, dtype=np.complex128)
    denominator = np.maximum(
        1.0,
        np.maximum(np.abs(compact_roots)[:, None], np.abs(full_roots)[None, :]),
    )
    costs = np.abs(compact_roots[:, None] - full_roots[None, :]) / denominator
    row_indices, column_indices = linear_sum_assignment(costs)
    selected = np.zeros(full_roots.size, dtype=bool)
    selected[column_indices] = True
    return float(np.max(costs[row_indices, column_indices])), full_roots[~selected]


def empty_complex() -> np.ndarray:
    return np.empty(0, dtype=np.complex128)


def empty_float() -> np.ndarray:
    return np.empty(0, dtype=float)


def failed_point_result(spec: RouteSpec, matrices: Matrices, l: int, j: int, started: float, exc: Exception) -> PointResult:
    n = matrices.M.shape[0]
    summary = {
        "route_id": spec.route_id,
        "route_role": spec.route_role,
        "declared_method": spec.declared_method,
        "route_formula": spec.route_formula,
        "l": l,
        "j": j,
        "matrix_order": n,
        "compact_order": 2 * n + l + j,
        "full_q_order": n * (max(l, j) + 2),
        "poly_degree": -1,
        "clearing_power": -1,
        "compact_raw_root_count": 0,
        "compact_zero_root_tolerance": math.nan,
        "compact_removed_zero_count": 0,
        "compact_retained_root_count": 0,
        "rho_compact": math.nan,
        "stable_compact": False,
        "critical_compact": False,
        "max_polynomial_residual_compact": math.nan,
        "max_laurent_residual_compact": math.nan,
        "full_crosscheck_performed": False,
        "full_raw_root_count": 0,
        "full_zero_root_tolerance": math.nan,
        "full_removed_zero_count": 0,
        "full_retained_root_count": 0,
        "rho_full": math.nan,
        "stable_full": False,
        "max_polynomial_residual_full": math.nan,
        "max_laurent_residual_full": math.nan,
        "compact_full_rho_abs_diff": math.nan,
        "root_match_max_relative_diff": math.nan,
        "near_unit_root_match_max_relative_diff": math.nan,
        "extra_full_roots_are_zero": False,
        "strict_root_set_status": "NOT_RUN",
        "theoretical_extra_zero_count": 0,
        "observed_extra_zero_count": 0,
        "full_q_origin_multiplicity_splitting_count": 0,
        "full_q_origin_multiplicity_splitting_max_abs": math.nan,
        "direct_formula_coefficient_relative_difference": math.nan,
        "dominant_root_real": math.nan,
        "dominant_root_imag": math.nan,
        "elapsed_seconds": time.perf_counter() - started,
        "point_status": "FAIL",
        "failure_code": f"{type(exc).__name__}:{exc}",
    }
    return PointResult(
        summary,
        empty_complex(),
        empty_complex(),
        empty_float(),
        empty_float(),
        empty_complex(),
        empty_complex(),
        empty_float(),
        empty_float(),
    )


def solve_point(
    spec: RouteSpec,
    matrices: Matrices,
    l: int,
    j: int,
    gates: dict[str, Any],
    full_crosscheck: bool,
) -> PointResult:
    started = time.perf_counter()
    try:
        components = build_components(matrices, spec.route_formula)
        coefficients = build_coefficient_map(spec, components, l, j)
        direct_terms = direct_laurent_terms(spec, components, l, j)
        polynomial, clearing_power, poly_degree = polynomial_from_coefficients(coefficients)
        formula_difference = formula_coefficient_relative_difference(
            spec, components, coefficients, l, j
        )
        compact_matrix = build_compact_state_matrix(spec, components, l, j)
        compact = solve_spectrum(
            compact_matrix,
            matrices.M.shape[0],
            polynomial,
            direct_terms,
            clearing_power,
        )

        full: Spectrum | None = None
        rho_difference = math.nan
        root_difference = math.nan
        near_unit_root_difference = math.nan
        extra_roots_are_zero = False
        strict_root_set_status = "NOT_RUN"
        theoretical_extra_zero_count = 0
        observed_extra_zero_count = 0
        origin_splitting_count = 0
        origin_splitting_max_abs = math.nan
        if full_crosscheck:
            full_matrix = build_full_q_history_matrix(components, coefficients, l, j)
            full = solve_spectrum(
                full_matrix,
                matrices.M.shape[0],
                polynomial,
                direct_terms,
                clearing_power,
            )
            rho_difference = abs(compact.rho - full.rho)
            root_difference = match_root_sets(compact.retained, full.retained)
            order_difference = full_matrix.shape[0] - compact_matrix.shape[0]
            zero_difference = full.removed_zero_count - compact.removed_zero_count
            theoretical_extra_zero_count = int(order_difference)
            observed_extra_zero_count = int(zero_difference)
            origin_splitting_count = int(max(0, order_difference - zero_difference))
            _, unmatched_full = rectangular_root_diagnostic(compact.retained, full.retained)
            if unmatched_full.size:
                origin_splitting_max_abs = float(np.max(np.abs(unmatched_full)))
            near_threshold = float(gates["near_unit_root_threshold"])
            near_compact = compact.retained[np.abs(compact.retained) >= near_threshold]
            near_full = full.retained[np.abs(full.retained) >= near_threshold]
            near_unit_root_difference = match_root_sets(near_compact, near_full)
            extra_roots_are_zero = bool(
                order_difference >= 0
                and zero_difference == order_difference
                and compact.retained.size == full.retained.size
                and compact.raw.size + order_difference == full.raw.size
            )
            strict_root_set_status = (
                "PASS"
                if extra_roots_are_zero
                and root_difference <= float(gates["compact_full_root_relative_matching_difference"])
                else "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING"
            )

        failures: list[str] = []
        residual_gate = float(gates["max_polynomial_residual"])
        laurent_gate = float(gates["max_direct_laurent_residual"])
        formula_gate = float(gates["direct_formula_coefficient_relative_difference"])
        if compact.nonfinite_root_count:
            failures.append("COMPACT_NONFINITE_ROOT")
        if np.max(compact.polynomial_residual) > residual_gate:
            failures.append("COMPACT_POLYNOMIAL_RESIDUAL")
        if np.max(compact.laurent_residual) > laurent_gate:
            failures.append("COMPACT_LAURENT_RESIDUAL")
        if formula_difference > formula_gate:
            failures.append("DIRECT_FORMULA_COEFFICIENT_MISMATCH")
        if full_crosscheck:
            assert full is not None
            if rho_difference > float(gates["compact_full_rho_absolute_difference"]):
                failures.append("COMPACT_FULL_RHO_MISMATCH")
            if compact.stable != full.stable:
                failures.append("COMPACT_FULL_STABLE_MISMATCH")
            if near_unit_root_difference > float(gates["near_unit_root_relative_matching_difference"]):
                failures.append("COMPACT_FULL_NEAR_UNIT_ROOT_MISMATCH")

        max_poly_full = float(np.max(full.polynomial_residual)) if full is not None else math.nan
        max_laurent_full = float(np.max(full.laurent_residual)) if full is not None else math.nan
        n = matrices.M.shape[0]
        summary = {
            "route_id": spec.route_id,
            "route_role": spec.route_role,
            "declared_method": spec.declared_method,
            "route_formula": spec.route_formula,
            "l": int(l),
            "j": int(j),
            "matrix_order": n,
            "compact_order": int(compact_matrix.shape[0]),
            "full_q_order": int(n * (max(l, j) + 2)),
            "poly_degree": int(poly_degree),
            "clearing_power": int(clearing_power),
            "compact_raw_root_count": int(compact.raw.size),
            "compact_zero_root_tolerance": compact.zero_root_tolerance,
            "compact_removed_zero_count": compact.removed_zero_count,
            "compact_retained_root_count": int(compact.retained.size),
            "rho_compact": compact.rho,
            "stable_compact": compact.stable,
            "critical_compact": compact.critical,
            "max_polynomial_residual_compact": float(np.max(compact.polynomial_residual)),
            "max_laurent_residual_compact": float(np.max(compact.laurent_residual)),
            "full_crosscheck_performed": bool(full_crosscheck),
            "full_raw_root_count": int(full.raw.size) if full is not None else 0,
            "full_zero_root_tolerance": full.zero_root_tolerance if full is not None else math.nan,
            "full_removed_zero_count": full.removed_zero_count if full is not None else 0,
            "full_retained_root_count": int(full.retained.size) if full is not None else 0,
            "rho_full": full.rho if full is not None else math.nan,
            "stable_full": full.stable if full is not None else False,
            "max_polynomial_residual_full": max_poly_full,
            "max_laurent_residual_full": max_laurent_full,
            "compact_full_rho_abs_diff": rho_difference,
            "root_match_max_relative_diff": root_difference,
            "near_unit_root_match_max_relative_diff": near_unit_root_difference,
            "extra_full_roots_are_zero": extra_roots_are_zero,
            "strict_root_set_status": strict_root_set_status,
            "theoretical_extra_zero_count": theoretical_extra_zero_count,
            "observed_extra_zero_count": observed_extra_zero_count,
            "full_q_origin_multiplicity_splitting_count": origin_splitting_count,
            "full_q_origin_multiplicity_splitting_max_abs": origin_splitting_max_abs,
            "direct_formula_coefficient_relative_difference": formula_difference,
            "dominant_root_real": float(compact.dominant_root.real),
            "dominant_root_imag": float(compact.dominant_root.imag),
            "elapsed_seconds": time.perf_counter() - started,
            "point_status": "PASS" if not failures else "FAIL",
            "failure_code": "" if not failures else ";".join(failures),
        }
        return PointResult(
            summary=summary,
            compact_raw=compact.raw,
            compact_retained=compact.retained,
            compact_polynomial_residual=compact.polynomial_residual,
            compact_laurent_residual=compact.laurent_residual,
            full_raw=full.raw if full is not None else empty_complex(),
            full_retained=full.retained if full is not None else empty_complex(),
            full_polynomial_residual=full.polynomial_residual if full is not None else empty_float(),
            full_laurent_residual=full.laurent_residual if full is not None else empty_float(),
        )
    except Exception as exc:  # Every real point must keep an explicit failure.
        return failed_point_result(spec, matrices, l, j, started, exc)


def h5_string_dtype() -> np.dtype:
    return h5py.string_dtype(encoding="utf-8")


def write_ragged_root_group(
    parent: h5py.Group,
    name: str,
    results: Sequence[PointResult],
    roots_getter: Callable[[PointResult], np.ndarray],
    polynomial_getter: Callable[[PointResult], np.ndarray] | None,
    laurent_getter: Callable[[PointResult], np.ndarray] | None,
) -> None:
    group = parent.create_group(name)
    counts = np.asarray([roots_getter(item).size for item in results], dtype=np.int64)
    offsets = np.zeros(len(results), dtype=np.int64)
    if len(results) > 1:
        offsets[1:] = np.cumsum(counts[:-1])
    roots = np.concatenate([roots_getter(item) for item in results]) if counts.sum() else empty_complex()
    if polynomial_getter is None:
        poly = np.full(roots.size, np.nan, dtype=float)
    else:
        poly = np.concatenate([polynomial_getter(item) for item in results]) if counts.sum() else empty_float()
    if laurent_getter is None:
        laurent = np.full(roots.size, np.nan, dtype=float)
    else:
        laurent = np.concatenate([laurent_getter(item) for item in results]) if counts.sum() else empty_float()
    if poly.size != roots.size or laurent.size != roots.size:
        raise AssertionError(f"Ragged residual length mismatch for {name}.")
    group.create_dataset("offset", data=offsets)
    group.create_dataset("count", data=counts)
    group.create_dataset("real", data=roots.real, compression="gzip", shuffle=True)
    group.create_dataset("imag", data=roots.imag, compression="gzip", shuffle=True)
    group.create_dataset("polynomial_residual", data=poly, compression="gzip", shuffle=True)
    group.create_dataset("laurent_residual", data=laurent, compression="gzip", shuffle=True)


def atomic_write_results_h5(
    path: Path,
    results: Sequence[PointResult],
    metadata: dict[str, Any],
    *,
    include_runtime_in_record_json: bool,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}")
    with h5py.File(temporary, "w") as handle:
        handle.attrs["schema_version"] = "board20_step5_roots_h5_v1"
        handle.attrs["metadata_json"] = json.dumps(metadata, ensure_ascii=False, sort_keys=True)
        points = handle.create_group("points")
        records = [
            dict(item.summary)
            if include_runtime_in_record_json
            else {key: value for key, value in item.summary.items() if key != "elapsed_seconds"}
            for item in results
        ]
        points.create_dataset(
            "record_json",
            data=np.asarray(
                [json.dumps(record, ensure_ascii=False, sort_keys=True) for record in records],
                dtype=h5_string_dtype(),
            ),
        )
        for field in CSV_FIELDS:
            values = [record[field] for record in records]
            if field in ("route_id", "route_role", "declared_method", "route_formula", "point_status", "failure_code"):
                points.create_dataset(field, data=np.asarray(values, dtype=h5_string_dtype()))
            elif all(isinstance(value, (bool, np.bool_)) for value in values):
                points.create_dataset(field, data=np.asarray(values, dtype=np.uint8))
            else:
                try:
                    points.create_dataset(field, data=np.asarray(values, dtype=np.float64))
                except (TypeError, ValueError):
                    points.create_dataset(
                        field,
                        data=np.asarray([str(value) for value in values], dtype=h5_string_dtype()),
                    )
        compact = handle.create_group("compact")
        write_ragged_root_group(compact, "raw", results, lambda item: item.compact_raw, None, None)
        write_ragged_root_group(
            compact,
            "retained",
            results,
            lambda item: item.compact_retained,
            lambda item: item.compact_polynomial_residual,
            lambda item: item.compact_laurent_residual,
        )
        full = handle.create_group("full_q")
        write_ragged_root_group(full, "raw", results, lambda item: item.full_raw, None, None)
        write_ragged_root_group(
            full,
            "retained",
            results,
            lambda item: item.full_retained,
            lambda item: item.full_polynomial_residual,
            lambda item: item.full_laurent_residual,
        )
        handle.flush()
    replace_with_retry(temporary, path)


def read_ragged_root_group(group: h5py.Group, index: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    offset = int(group["offset"][index])
    count = int(group["count"][index])
    section = slice(offset, offset + count)
    roots = np.asarray(group["real"][section]) + 1j * np.asarray(group["imag"][section])
    poly = np.asarray(group["polynomial_residual"][section], dtype=float)
    laurent = np.asarray(group["laurent_residual"][section], dtype=float)
    return roots.astype(np.complex128), poly, laurent


def read_results_h5(path: Path) -> list[PointResult]:
    results: list[PointResult] = []
    with h5py.File(path, "r") as handle:
        record_values = handle["points/record_json"][:]
        for index, encoded in enumerate(record_values):
            text = encoded.decode("utf-8") if isinstance(encoded, bytes) else str(encoded)
            summary = json.loads(text)
            compact_raw, _, _ = read_ragged_root_group(handle["compact/raw"], index)
            compact_retained, compact_poly, compact_laurent = read_ragged_root_group(
                handle["compact/retained"], index
            )
            full_raw, _, _ = read_ragged_root_group(handle["full_q/raw"], index)
            full_retained, full_poly, full_laurent = read_ragged_root_group(
                handle["full_q/retained"], index
            )
            results.append(
                PointResult(
                    summary,
                    compact_raw,
                    compact_retained,
                    compact_poly,
                    compact_laurent,
                    full_raw,
                    full_retained,
                    full_poly,
                    full_laurent,
                )
            )
    return results


def checkpoint_identity(
    mode: str,
    spec: RouteSpec,
    code_hash: str,
    contract_hash: str,
    manifest_hash: str,
    expected_points: Sequence[tuple[int, int]],
) -> dict[str, Any]:
    return {
        "schema_version": "board20_step5_checkpoint_identity_v1",
        "mode": mode,
        "route_id": spec.route_id,
        "code_sha256": code_hash,
        "contract_sha256": contract_hash,
        "manifest_sha256": manifest_hash,
        "workspace_sha256": spec.workspace_sha256,
        "expected_points_sha256": hashlib.sha256(canonical_json_bytes(list(expected_points))).hexdigest().upper(),
        "expected_point_count": len(expected_points),
    }


def write_checkpoint(
    route_directory: Path,
    results: Sequence[PointResult],
    identity: dict[str, Any],
    status: str,
) -> None:
    h5_path = route_directory / "checkpoint.h5"
    atomic_write_results_h5(
        h5_path,
        results,
        {**identity, "checkpoint_status": status},
        include_runtime_in_record_json=True,
    )
    checkpoint = {
        **identity,
        "checkpoint_status": status,
        "completed_point_count": len(results),
        "checkpoint_h5_sha256": sha256_file(h5_path),
        "updated_at": utc_now(),
    }
    atomic_write_json(route_directory / "checkpoint.json", checkpoint)


def load_checkpoint(route_directory: Path, identity: dict[str, Any]) -> list[PointResult]:
    json_path = route_directory / "checkpoint.json"
    h5_path = route_directory / "checkpoint.h5"
    if not json_path.is_file() or not h5_path.is_file():
        raise FileNotFoundError(f"A complete checkpoint pair is required in {route_directory}.")
    checkpoint = load_json(json_path)
    for field, expected in identity.items():
        if checkpoint.get(field) != expected:
            raise ValueError(f"Checkpoint identity mismatch for {field}.")
    if sha256_file(h5_path) != checkpoint["checkpoint_h5_sha256"]:
        raise ValueError("Checkpoint HDF5 hash mismatch.")
    results = read_results_h5(h5_path)
    if len(results) != checkpoint["completed_point_count"]:
        raise ValueError("Checkpoint point count does not match HDF5 records.")
    return results


def write_final_route_outputs(
    route_directory: Path,
    results: Sequence[PointResult],
    identity: dict[str, Any],
) -> dict[str, Any]:
    atomic_write_csv(
        route_directory / "point_summary.csv",
        [item.summary for item in results],
        CSV_FIELDS,
    )
    atomic_write_csv(
        route_directory / "point_runtime.csv",
        [item.summary for item in results],
        RUNTIME_CSV_FIELDS,
    )
    checkpoint_h5 = route_directory / "checkpoint.h5"
    roots_path = route_directory / "roots.h5"
    atomic_write_results_h5(
        roots_path,
        results,
        identity,
        include_runtime_in_record_json=False,
    )
    pass_count = sum(item.summary["point_status"] == "PASS" for item in results)
    fail_count = len(results) - pass_count
    finite_rhos = [
        float(item.summary["rho_compact"])
        for item in results
        if math.isfinite(float(item.summary["rho_compact"]))
    ]
    route_status = {
        **identity,
        "status": "PASS" if fail_count == 0 and len(results) == identity["expected_point_count"] else "FAIL",
        "completed_point_count": len(results),
        "pass_point_count": pass_count,
        "fail_point_count": fail_count,
        "rho_min": min(finite_rhos) if finite_rhos else None,
        "rho_max": max(finite_rhos) if finite_rhos else None,
        "max_compact_polynomial_residual": max(
            (float(item.summary["max_polynomial_residual_compact"]) for item in results),
            default=math.nan,
        ),
        "max_compact_laurent_residual": max(
            (float(item.summary["max_laurent_residual_compact"]) for item in results),
            default=math.nan,
        ),
        "point_summary_sha256": sha256_file(route_directory / "point_summary.csv"),
        "roots_h5_sha256": sha256_file(roots_path),
        "scientific_status_policy": "DETERMINISTIC_NO_WALL_CLOCK_FIELDS",
    }
    atomic_write_json(route_directory / "route_status.json", route_status)
    return route_status


def dependency_metadata() -> dict[str, Any]:
    return {
        "python": sys.version.replace("\n", " "),
        "python_executable": sys.executable,
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
        "h5py": h5py.__version__,
        "blas_lapack": str(getattr(np.__config__, "CONFIG", "UNAVAILABLE")),
        "thread_environment": {
            name: os.environ.get(name)
            for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS")
        },
    }


def append_check(checks: list[dict[str, Any]], check_id: str, passed: bool, detail: Any) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "PASS" if passed else "FAIL",
            "detail": json_scalar(detail),
        }
    )


def contracts_status_document(contract: dict[str, Any], manifest: dict[str, Any]) -> dict[str, Any]:
    manifest_failed = {item["route_id"]: item for item in manifest["failed_routes"]}
    failed_routes = []
    for item in contract["noncomputable_failed_routes"]:
        source = manifest_failed.get(item["route_id"])
        failed_routes.append(
            {
                **item,
                "manifest_execution_status": source.get("execution_status") if source else "MISSING",
                "failure_reason": source.get("failure_reason") if source else "MISSING",
                "output_directory_must_not_exist": True,
            }
        )
    return {
        "schema_version": "board20_step5_contracts_status_v1",
        "scientific_contracts": contract["scientific_contracts"],
        "noncomputable_failed_routes": failed_routes,
    }


def run_preflight() -> dict[str, Any]:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []
    try:
        root, contract, manifest, specs = load_contract_and_routes()
        append_check(checks, "contract_schema", contract.get("schema_version") == "board20_step5_independent_compute_contract_v1", contract.get("schema_version"))
        append_check(checks, "manifest_schema", manifest.get("schema_version") == "board20_step4_route_manifest_v1", manifest.get("schema_version"))
        append_check(checks, "route_count", len(specs) == 5, len(specs))
        pilot_count = sum(len(spec.pilot_points) for spec in specs)
        append_check(checks, "pilot_point_count", pilot_count == 41, pilot_count)
        append_check(
            checks,
            "pilot_point_uniqueness_per_route",
            all(len(set(spec.pilot_points)) == len(spec.pilot_points) for spec in specs),
            "Each route has unique (l,j) points.",
        )
        forbidden_source_token = "outputs/" + "step" + "4_rho_grids"
        source_text = (code_directory() / SCRIPT_FILENAME).read_text(encoding="utf-8")
        append_check(
            checks,
            "source_has_no_forbidden_result_path",
            forbidden_source_token not in source_text,
            "The computation source has no MATLAB-result directory literal.",
        )
        append_check(
            checks,
            "master_thesis_contract_not_closed",
            contract["scientific_contracts"]["master_thesis_route"]["status"] == "CONTRACT_NOT_CLOSED",
            contract["scientific_contracts"]["master_thesis_route"]["status"],
        )
        append_check(
            checks,
            "manuscript_contract_not_closed",
            contract["scientific_contracts"]["manuscript_0824_route"]["status"] == "CONTRACT_NOT_CLOSED",
            contract["scientific_contracts"]["manuscript_0824_route"]["status"],
        )
        failed_ids = {item["route_id"] for item in contract["noncomputable_failed_routes"]}
        append_check(
            checks,
            "four_failed_routes_do_not_create",
            failed_ids == {"main_cb_div1", "main_cb_div2", "energy_guyan_div1", "energy_guyan_div2"}
            and all(item["step5_policy"] == "DO_NOT_CREATE" for item in contract["noncomputable_failed_routes"]),
            sorted(failed_ids),
        )
        for spec in specs:
            workspace = safe_relative_path(root, spec.workspace_relpath, "outputs/step2_runs")
            append_check(checks, f"{spec.route_id}.workspace_hash", sha256_file(workspace) == spec.workspace_sha256, spec.workspace_sha256)
            matrices = load_route_matrices(root, spec)
            n = matrices.M.shape[0]
            append_check(checks, f"{spec.route_id}.matrix_order", n == (15 if spec.route_id == "main_ori_div1" else 5), n)
            append_check(checks, f"{spec.route_id}.finite_matrices", all(np.all(np.isfinite(value)) for value in (matrices.M, matrices.C1, matrices.K1, matrices.C2, matrices.K2, matrices.al)), "finite")
            components = build_components(matrices, spec.route_formula)
            right_division_residual = np.linalg.norm(components.T * matrices.dt**2 @ matrices.al - matrices.M, ord="fro") / max(1.0, np.linalg.norm(matrices.M, ord="fro"))
            append_check(checks, f"{spec.route_id}.right_division_residual", right_division_residual <= 1e-12, float(right_division_residual))
            if spec.route_formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
                append_check(checks, f"{spec.route_id}.restored_S_shape", matrices.S is not None and matrices.S.shape == (2, n), matrices.S.shape if matrices.S is not None else None)
        status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
        document = {
            "schema_version": "board20_step5_preflight_v1",
            "status": status,
            "check_count": len(checks),
            "pass_count": sum(check["status"] == "PASS" for check in checks),
            "fail_count": sum(check["status"] == "FAIL" for check in checks),
            "checks": checks,
            "input_identity": {
                "code_sha256": sha256_file(code_directory() / SCRIPT_FILENAME),
                "contract_sha256": sha256_file(code_directory() / CONTRACT_FILENAME),
                "manifest_sha256": sha256_file(code_directory() / ROUTE_MANIFEST_FILENAME),
                "workspace_sha256": {spec.route_id: spec.workspace_sha256 for spec in specs},
            },
            "dependencies": dependency_metadata(),
            "elapsed_seconds": time.perf_counter() - started,
            "completed_at": utc_now(),
        }
        output_root = root / contract["output_root_relpath"]
        output_root.mkdir(parents=True, exist_ok=True)
        atomic_write_json(output_root / "contracts_status.json", contracts_status_document(contract, manifest))
        atomic_write_json(output_root / "preflight.json", document)
        return document
    except Exception as exc:
        document = {
            "schema_version": "board20_step5_preflight_v1",
            "status": "FAIL",
            "check_count": len(checks) + 1,
            "pass_count": sum(check["status"] == "PASS" for check in checks),
            "fail_count": sum(check["status"] == "FAIL" for check in checks) + 1,
            "checks": checks + [{"check_id": "preflight_exception", "status": "FAIL", "detail": f"{type(exc).__name__}:{exc}"}],
            "elapsed_seconds": time.perf_counter() - started,
            "completed_at": utc_now(),
        }
        try:
            root = board_root()
            output_root = root / "outputs/step5_independent_compute"
            output_root.mkdir(parents=True, exist_ok=True)
            atomic_write_json(output_root / "preflight.json", document)
        except Exception:
            pass
        return document


def synthetic_matrices(n: int = 6) -> Matrices:
    rng = np.random.default_rng(20260825)
    a = rng.normal(size=(n, n))
    b = rng.normal(size=(n, n))
    M = a.T @ a + 4.0 * np.eye(n)
    al = b.T @ b + 2.0 * np.eye(n)
    C1 = np.diag(np.linspace(0.15, 0.45, n))
    K1 = np.diag(np.linspace(2.0, 7.0, n))
    C2 = 0.015 * rng.normal(size=(n, n))
    K2 = 0.030 * rng.normal(size=(n, n))
    S = np.zeros((2, n))
    S[0, 0] = 1.0
    S[1, 1] = 1.0
    return Matrices(
        M=M,
        C1=C1,
        K1=K1,
        C2=C2,
        K2=K2,
        al=al,
        dt=0.01,
        S=S,
        DeltaC=np.asarray([[0.04, 0.01], [0.01, 0.03]]),
        DeltaK=np.asarray([[0.2, -0.02], [-0.02, 0.18]]),
    )


def synthetic_spec(formula: str) -> RouteSpec:
    return RouteSpec(
        route_id=f"synthetic_{formula.lower()}",
        route_name="Deterministic algorithm selftest",
        route_role="ALGORITHMIC_SELFTEST",
        declared_method="ALGORITHMIC_SELFTEST",
        division="synthetic",
        route_formula=formula,
        workspace_relpath="",
        workspace_sha256="",
        matrix_variables={},
        delay_dofs=(0, 5) if formula == "ORI_DIV1_H_RIGHT" else (0, 1),
        pilot_points=(),
    )


def run_selftest() -> dict[str, Any]:
    started = time.perf_counter()
    checks: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    root, contract, _, _ = load_contract_and_routes()
    gates = contract["numeric_gates"]
    matrices = synthetic_matrices()

    nonsymmetric_m = np.asarray([[2.0, 1.0], [0.3, 1.4]])
    nonsymmetric_al = np.asarray([[1.2, 0.4], [-0.2, 0.9]])
    right_solution = sla.solve(nonsymmetric_al.T, nonsymmetric_m.T).T
    append_check(
        checks,
        "matlab_right_division_identity",
        np.linalg.norm(right_solution @ nonsymmetric_al - nonsymmetric_m, ord="fro") <= 1e-14,
        float(np.linalg.norm(right_solution @ nonsymmetric_al - nonsymmetric_m, ord="fro")),
    )
    append_check(
        checks,
        "right_division_not_elementwise",
        not np.allclose(right_solution, nonsymmetric_m / nonsymmetric_al),
        "solve(al.T,M.T).T differs from elementwise division",
    )

    formulas = (
        "ORI_DIV1_H_RIGHT",
        "GUYAN_DIV1_H_LEFT",
        "DIV2_H_LEFT_FEEDBACK_OUTSIDE",
    )
    for formula in formulas:
        spec = synthetic_spec(formula)
        components = build_components(matrices, formula)
        for l, j in ((0, 0), (2, 3)):
            coefficients = build_coefficient_map(spec, components, l, j)
            terms = direct_laurent_terms(spec, components, l, j)
            polynomial, clearing, _ = polynomial_from_coefficients(coefficients)
            compact_matrix = build_compact_state_matrix(spec, components, l, j)
            full_matrix = build_full_q_history_matrix(components, coefficients, l, j)
            compact = solve_spectrum(compact_matrix, matrices.M.shape[0], polynomial, terms, clearing)
            full = solve_spectrum(full_matrix, matrices.M.shape[0], polynomial, terms, clearing)
            root_difference = match_root_sets(compact.retained, full.retained)
            near_threshold = float(gates["near_unit_root_threshold"])
            near_root_difference = match_root_sets(
                compact.retained[np.abs(compact.retained) >= near_threshold],
                full.retained[np.abs(full.retained) >= near_threshold],
            )
            formula_difference = formula_coefficient_relative_difference(spec, components, coefficients, l, j)
            prefix = f"{formula}.l{l}.j{j}"
            append_check(checks, prefix + ".compact_order", compact_matrix.shape[0] == 2 * matrices.M.shape[0] + l + j, compact_matrix.shape[0])
            append_check(checks, prefix + ".full_order", full_matrix.shape[0] == matrices.M.shape[0] * (max(l, j) + 2), full_matrix.shape[0])
            append_check(checks, prefix + ".rho_match", abs(compact.rho - full.rho) <= float(gates["compact_full_rho_absolute_difference"]), abs(compact.rho - full.rho))
            append_check(checks, prefix + ".near_unit_root_match", near_root_difference <= float(gates["near_unit_root_relative_matching_difference"]), near_root_difference)
            append_check(checks, prefix + ".compact_poly_residual", float(np.max(compact.polynomial_residual)) <= float(gates["max_polynomial_residual"]), float(np.max(compact.polynomial_residual)))
            append_check(checks, prefix + ".compact_laurent_residual", float(np.max(compact.laurent_residual)) <= float(gates["max_direct_laurent_residual"]), float(np.max(compact.laurent_residual)))
            append_check(checks, prefix + ".formula_identity", formula_difference <= float(gates["direct_formula_coefficient_relative_difference"]), formula_difference)
            order_difference = full_matrix.shape[0] - compact_matrix.shape[0]
            zero_difference = full.removed_zero_count - compact.removed_zero_count
            diagnostics.append(
                {
                    "diagnostic_id": prefix + ".strict_all_root_set",
                    "status": "PASS" if compact.retained.size == full.retained.size and order_difference == zero_difference and root_difference <= float(gates["compact_full_root_relative_matching_difference"]) else "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING",
                    "compact_retained_count": int(compact.retained.size),
                    "full_retained_count": int(full.retained.size),
                    "root_match_max_relative_diff": root_difference,
                    "theoretical_extra_zero_count": int(order_difference),
                    "observed_extra_zero_count": int(zero_difference),
                }
            )

    left_spec = synthetic_spec("GUYAN_DIV1_H_LEFT")
    right_spec = synthetic_spec("ORI_DIV1_H_RIGHT")
    left_components = build_components(matrices, left_spec.route_formula)
    right_components = build_components(matrices, right_spec.route_formula)
    z_probe = 0.91 + 0.22j
    left_matrix = evaluate_direct_matrix(left_spec, left_components, 2, 3, z_probe)
    right_matrix = evaluate_direct_matrix(right_spec, right_components, 2, 3, z_probe)
    append_check(checks, "left_right_placement_identifiable", np.linalg.norm(left_matrix - right_matrix, ord="fro") > 1e-8, float(np.linalg.norm(left_matrix - right_matrix, ord="fro")))

    div2_spec = synthetic_spec("DIV2_H_LEFT_FEEDBACK_OUTSIDE")
    div2_components = build_components(matrices, div2_spec.route_formula)
    delayed_feedback_wrong = selector(6, 0) @ div2_components.feedback_zero * z_probe ** -2 + selector(6, 1) @ div2_components.feedback_zero * z_probe ** -3
    outside_feedback = div2_components.feedback_zero
    append_check(checks, "feedback_outside_H_identifiable", np.linalg.norm(outside_feedback - delayed_feedback_wrong, ord="fro") > 1e-8, float(np.linalg.norm(outside_feedback - delayed_feedback_wrong, ord="fro")))
    append_check(checks, "master_contract_remains_not_closed", contract["scientific_contracts"]["master_thesis_route"]["status"] == "CONTRACT_NOT_CLOSED", contract["scientific_contracts"]["master_thesis_route"]["status"])
    append_check(checks, "manuscript_contract_remains_not_closed", contract["scientific_contracts"]["manuscript_0824_route"]["status"] == "CONTRACT_NOT_CLOSED", contract["scientific_contracts"]["manuscript_0824_route"]["status"])

    status = "PASS" if all(check["status"] == "PASS" for check in checks) else "FAIL"
    document = {
        "schema_version": "board20_step5_selftest_v1",
        "evidence_label": "ALGORITHMIC_SELFTEST_NOT_SCIENTIFIC_RESULT",
        "status": status,
        "check_count": len(checks),
        "pass_count": sum(check["status"] == "PASS" for check in checks),
        "fail_count": sum(check["status"] == "FAIL" for check in checks),
        "checks": checks,
        "diagnostics_not_acceptance_gates": diagnostics,
        "input_identity": {
            "code_sha256": sha256_file(code_directory() / SCRIPT_FILENAME),
            "contract_sha256": sha256_file(code_directory() / CONTRACT_FILENAME),
            "manifest_sha256": sha256_file(code_directory() / ROUTE_MANIFEST_FILENAME),
        },
        "elapsed_seconds": time.perf_counter() - started,
        "completed_at": utc_now(),
    }
    output_root = root / contract["output_root_relpath"]
    output_root.mkdir(parents=True, exist_ok=True)
    atomic_write_json(output_root / "selftest.json", document)
    return document


def require_prior_gate(output_root: Path, filename: str, code_hash: str, contract_hash: str, manifest_hash: str) -> None:
    path = output_root / filename
    if not path.is_file():
        raise FileNotFoundError(f"Required prior gate is missing: {path}")
    report = load_json(path)
    if report.get("status") != "PASS":
        raise ValueError(f"Required prior gate did not pass: {filename}")
    identity = report.get("input_identity", {})
    expected = {
        "code_sha256": code_hash,
        "contract_sha256": contract_hash,
        "manifest_sha256": manifest_hash,
    }
    for key, value in expected.items():
        if identity.get(key) != value:
            raise ValueError(f"Prior gate {filename} has stale {key}.")


def known_route_files() -> tuple[str, ...]:
    return (
        "point_summary.csv",
        "roots.h5",
        "route_status.json",
        "checkpoint.h5",
        "checkpoint.json",
        "point_runtime.csv",
    )


def clear_known_route_files(route_directory: Path) -> None:
    for filename in known_route_files():
        path = route_directory / filename
        if path.is_file():
            path.unlink()


def mode_points(contract: dict[str, Any], spec: RouteSpec, mode: str) -> list[tuple[int, int]]:
    if mode == "pilot":
        return list(spec.pilot_points)
    grid = contract["full_grid"]
    return [
        (l, j)
        for l in range(int(grid["l_start"]), int(grid["l_end"]) + 1)
        for j in range(int(grid["j_start"]), int(grid["j_end"]) + 1)
    ]


def write_artifact_manifest(directory: Path) -> Path:
    manifest_path = directory / "artifact_manifest.csv"
    rows = []
    for path in sorted(directory.rglob("*"), key=lambda value: value.as_posix()):
        if not path.is_file() or path == manifest_path or ".tmp." in path.name:
            continue
        if path.name in {
            "checkpoint.h5",
            "checkpoint.json",
            "point_runtime.csv",
            "run_metadata.json",
        }:
            continue
        rows.append(
            {
                "relpath": path.relative_to(directory).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    atomic_write_csv(manifest_path, rows, ("relpath", "bytes", "sha256"))
    return manifest_path


def run_scientific_mode(mode: str, overwrite: bool, checkpoint_every: int) -> dict[str, Any]:
    started = time.perf_counter()
    root, contract, manifest, specs = load_contract_and_routes()
    code_hash = sha256_file(code_directory() / SCRIPT_FILENAME)
    contract_hash = sha256_file(code_directory() / CONTRACT_FILENAME)
    manifest_hash = sha256_file(code_directory() / ROUTE_MANIFEST_FILENAME)
    output_root = root / contract["output_root_relpath"]
    require_prior_gate(output_root, "preflight.json", code_hash, contract_hash, manifest_hash)
    require_prior_gate(output_root, "selftest.json", code_hash, contract_hash, manifest_hash)
    if mode in ("full", "resume"):
        pilot_status_path = output_root / "pilot" / "run_status.json"
        if not pilot_status_path.is_file() or load_json(pilot_status_path).get("status") != "PASS":
            raise ValueError("A passing 41-point pilot is required before full/resume.")

    effective_mode = "full" if mode == "resume" else mode
    resume = mode == "resume"
    mode_directory = output_root / effective_mode
    mode_directory.mkdir(parents=True, exist_ok=True)
    gates = contract["numeric_gates"]
    route_statuses: list[dict[str, Any]] = []

    for spec in specs:
        matrices = load_route_matrices(root, spec)
        points = mode_points(contract, spec, effective_mode)
        identity = checkpoint_identity(
            effective_mode,
            spec,
            code_hash,
            contract_hash,
            manifest_hash,
            points,
        )
        route_directory = mode_directory / spec.route_id
        route_directory.mkdir(parents=True, exist_ok=True)
        if resume:
            results = load_checkpoint(route_directory, identity)
        else:
            existing = [route_directory / name for name in known_route_files() if (route_directory / name).exists()]
            if existing and not overwrite:
                raise FileExistsError(
                    f"Existing route outputs require --overwrite or --mode resume: {route_directory}"
                )
            if overwrite:
                clear_known_route_files(route_directory)
            results = []

        completed_pairs = [(int(item.summary["l"]), int(item.summary["j"])) for item in results]
        if completed_pairs != points[: len(completed_pairs)]:
            raise ValueError(f"Checkpoint point order mismatch for {spec.route_id}.")
        for point_index in range(len(results), len(points)):
            l, j = points[point_index]
            point = solve_point(
                spec,
                matrices,
                l,
                j,
                gates,
                full_crosscheck=(effective_mode == "pilot"),
            )
            results.append(point)
            logging.info(
                "%s %s point %d/%d (l=%d,j=%d) status=%s rho=%s elapsed=%.3fs",
                effective_mode,
                spec.route_id,
                point_index + 1,
                len(points),
                l,
                j,
                point.summary["point_status"],
                point.summary["rho_compact"],
                point.summary["elapsed_seconds"],
            )
            if (
                effective_mode == "pilot"
                or (point_index + 1) % checkpoint_every == 0
                or point_index + 1 == len(points)
            ):
                write_checkpoint(
                    route_directory,
                    results,
                    identity,
                    "COMPLETE" if point_index + 1 == len(points) else "IN_PROGRESS",
                )
        if not results and not (route_directory / "checkpoint.h5").is_file():
            write_checkpoint(route_directory, results, identity, "COMPLETE")
        route_statuses.append(write_final_route_outputs(route_directory, results, identity))

    total_points = sum(int(item["completed_point_count"]) for item in route_statuses)
    total_fail = sum(int(item["fail_point_count"]) for item in route_statuses)
    expected_total = 41 if effective_mode == "pilot" else int(contract["full_grid"]["total_points"])
    status = "PASS" if total_fail == 0 and total_points == expected_total and all(item["status"] == "PASS" for item in route_statuses) else "FAIL"
    elapsed_seconds = time.perf_counter() - started
    run_status = {
        "schema_version": "board20_step5_run_status_v1",
        "mode": effective_mode,
        "status": status,
        "route_count": len(route_statuses),
        "completed_point_count": total_points,
        "expected_point_count": expected_total,
        "pass_point_count": total_points - total_fail,
        "fail_point_count": total_fail,
        "route_statuses": route_statuses,
        "input_identity": {
            "code_sha256": code_hash,
            "contract_sha256": contract_hash,
            "manifest_sha256": manifest_hash,
            "workspace_sha256": {spec.route_id: spec.workspace_sha256 for spec in specs},
        },
        "scientific_contracts": contract["scientific_contracts"],
        "noncomputable_failed_routes": contract["noncomputable_failed_routes"],
        "contracts_status_sha256": sha256_file(output_root / "contracts_status.json"),
        "scientific_status_policy": "DETERMINISTIC_NO_WALL_CLOCK_FIELDS",
    }
    atomic_write_json(mode_directory / "run_status.json", run_status)
    run_metadata = {
        "schema_version": "board20_step5_run_metadata_v1",
        "mode": effective_mode,
        "status": status,
        "elapsed_seconds": elapsed_seconds,
        "completed_at": utc_now(),
        "dependencies": dependency_metadata(),
        "scientific_run_status_sha256": sha256_file(mode_directory / "run_status.json"),
    }
    atomic_write_json(mode_directory / "run_metadata.json", run_metadata)
    artifact_manifest = write_artifact_manifest(mode_directory)
    return {
        **run_status,
        "artifact_manifest_sha256": sha256_file(artifact_manifest),
        "elapsed_seconds": elapsed_seconds,
    }


def configure_logging(root: Path, mode: str) -> Path:
    log_directory = root / "logs/step5"
    log_directory.mkdir(parents=True, exist_ok=True)
    log_path = log_directory / f"compute_{mode}.log"
    handlers: list[logging.Handler] = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_path, mode="a", encoding="utf-8"),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=handlers,
        force=True,
    )
    return log_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("preflight", "selftest", "pilot", "full", "resume"),
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite only the five known files inside each selected route output directory.",
    )
    parser.add_argument(
        "--checkpoint-every",
        type=int,
        default=10,
        help="Full-grid atomic checkpoint interval; pilot always checkpoints every point.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.checkpoint_every < 1:
        raise SystemExit("--checkpoint-every must be positive.")
    root = board_root()
    log_path = configure_logging(root, args.mode)
    logging.info("Starting independent Board-20 step-5 mode=%s", args.mode)
    logging.info("Log path: %s", log_path)
    if args.mode == "preflight":
        result = run_preflight()
    elif args.mode == "selftest":
        result = run_selftest()
    else:
        result = run_scientific_mode(args.mode, args.overwrite, args.checkpoint_every)
    logging.info(
        "BOARD20_STEP5_%s=%s points=%s pass=%s fail=%s elapsed=%.3fs",
        args.mode.upper(),
        result.get("status"),
        result.get("completed_point_count", result.get("check_count", 0)),
        result.get("pass_point_count", result.get("pass_count", 0)),
        result.get("fail_point_count", result.get("fail_count", 0)),
        float(result.get("elapsed_seconds", 0.0)),
    )
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

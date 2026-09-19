from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
from scipy import linalg
from scipy.io import loadmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
DEFAULT_INPUT_ROOT = BOARD_ROOT / "outputs" / "s4i"

VALUE_FIELDS = [
    "row_order", "case_id", "scope", "coordinate_identity", "route_variant",
    "result_identity", "excitation_identity", "recovery_identity", "mode_count",
    "model", "quantity", "row", "column", "value", "value_status",
    "uncertainty_flags",
]
RESULT_FIELDS = [
    "result_order", "case_id", "scope", "coordinate_identity", "route_variant",
    "result_identity", "excitation_identity", "recovery_identity", "mode_count",
    "comparison_model", "eq445_sum", "eq445_status",
    "historical_total_percent", "author_target_percent", "author_abs_error",
    "boundary_status",
]


@dataclass(frozen=True)
class ModalResult:
    M: np.ndarray
    K: np.ndarray
    r: np.ndarray
    eigenvalue: np.ndarray
    frequency_hz: np.ndarray
    phi: np.ndarray
    gamma_numerator: np.ndarray
    gamma_denominator: np.ndarray
    gamma: np.ndarray
    gamma_sq: np.ndarray
    participation_denominator: float
    participation_ratio: np.ndarray
    energy_raw: np.ndarray
    energy_column_sum: np.ndarray
    energy_normalized: np.ndarray
    energy_used: np.ndarray
    energy_total: np.ndarray


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def canonical_number(value: float) -> str:
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite canonical number: {number}")
    if number == 0.0:
        number = 0.0
    return format(number, ".17g")


def write_csv_new(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def read_hdf5_value(path: Path, name: str) -> np.ndarray:
    with h5py.File(path, "r") as handle:
        if name not in handle or not isinstance(handle[name], h5py.Dataset):
            raise KeyError(f"missing numeric dataset {name} in {path}")
        value = np.asarray(handle[name])
    if value.ndim >= 2:
        value = value.transpose(tuple(reversed(range(value.ndim))))
    value = np.asarray(value, dtype=np.float64)
    if np.iscomplexobj(value) or not np.all(np.isfinite(value)):
        raise ValueError(f"invalid numeric dataset {name} in {path}")
    return np.squeeze(value)


def read_hdf5_many(path: Path, names: Iterable[str]) -> dict[str, np.ndarray]:
    result: dict[str, np.ndarray] = {}
    with h5py.File(path, "r") as handle:
        for name in names:
            if name not in handle or not isinstance(handle[name], h5py.Dataset):
                raise KeyError(f"missing numeric dataset {name} in {path}")
            value = np.asarray(handle[name])
            if value.ndim >= 2:
                value = value.transpose(tuple(reversed(range(value.ndim))))
            value = np.asarray(value, dtype=np.float64)
            if np.iscomplexobj(value) or not np.all(np.isfinite(value)):
                raise ValueError(f"invalid numeric dataset {name} in {path}")
            result[name] = np.squeeze(value)
    return result


def as_matrix(value: np.ndarray, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != matrix.shape[1]:
        raise ValueError(f"{name} is not square: {matrix.shape}")
    return matrix


def as_transform(value: np.ndarray, full_size: int, name: str) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.ndim != 2 or matrix.shape[0] != full_size:
        raise ValueError(f"{name} transform shape mismatch: {matrix.shape}, full={full_size}")
    return matrix


def canonicalize_modes(M: np.ndarray, phi: np.ndarray) -> np.ndarray:
    result = np.asarray(phi, dtype=np.float64).copy()
    for index in range(result.shape[1]):
        denominator = float(result[:, index].T @ M @ result[:, index])
        if not math.isfinite(denominator) or denominator <= 0.0:
            raise ValueError(f"non-positive modal mass at mode {index + 1}: {denominator}")
        result[:, index] /= math.sqrt(denominator)
        pivot = int(np.argmax(np.abs(result[:, index])))
        if result[pivot, index] < 0.0:
            result[:, index] *= -1.0
    return result


def solve_modes(M: np.ndarray, K: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    M = as_matrix(M, "M")
    K = as_matrix(K, "K")
    if M.shape != K.shape:
        raise ValueError(f"M/K size mismatch: {M.shape} vs {K.shape}")
    scale_m = max(1.0, float(np.linalg.norm(M, ord="fro")))
    scale_k = max(1.0, float(np.linalg.norm(K, ord="fro")))
    if np.linalg.norm(M - M.T, ord="fro") > 1e-10 * scale_m:
        raise ValueError("M is not symmetric within the fixed hard gate")
    if np.linalg.norm(K - K.T, ord="fro") > 1e-10 * scale_k:
        raise ValueError("K is not symmetric within the fixed hard gate")
    if float(np.min(np.linalg.eigvalsh(M))) <= 0.0:
        raise ValueError("M is not positive definite")
    eigenvalue, phi = linalg.eigh(K, M, check_finite=True)
    order = np.argsort(eigenvalue, kind="stable")
    eigenvalue = np.asarray(eigenvalue[order], dtype=np.float64)
    phi = np.asarray(phi[:, order], dtype=np.float64)
    if np.any(eigenvalue <= 0.0) or not np.all(np.isfinite(eigenvalue)):
        raise ValueError("generalized eigenvalues are not finite and positive")
    phi = canonicalize_modes(M, phi)
    residual = np.linalg.norm(K @ phi - M @ phi @ np.diag(eigenvalue), ord="fro")
    scale = max(1.0, np.linalg.norm(K @ phi, ord="fro"))
    if residual / scale > 1e-10:
        raise ValueError(f"generalized eigen residual exceeds hard gate: {residual / scale}")
    return eigenvalue, phi


def modal_from_basis(
    M: np.ndarray,
    K: np.ndarray,
    r: np.ndarray,
    eigenvalue: np.ndarray,
    phi: np.ndarray,
    mode_count: int,
    energy_normalized: bool,
) -> ModalResult:
    M = as_matrix(M, "M")
    K = as_matrix(K, "K")
    r = np.asarray(r, dtype=np.float64).reshape(-1)
    eigenvalue = np.asarray(eigenvalue, dtype=np.float64).reshape(-1)
    phi = np.asarray(phi, dtype=np.float64)
    if r.size != M.shape[0] or phi.shape[0] != M.shape[0] or phi.shape[1] != eigenvalue.size:
        raise ValueError("modal input dimension mismatch")
    count = eigenvalue.size if mode_count == -1 else int(mode_count)
    if count < 1 or count > eigenvalue.size:
        raise ValueError(f"invalid mode count {count} for {eigenvalue.size} modes")
    eigenvalue = eigenvalue[:count].copy()
    phi = canonicalize_modes(M, phi[:, :count])
    gamma_numerator = phi.T @ M @ r
    gamma_denominator = np.einsum("ij,ij->j", phi, M @ phi)
    if np.any(np.abs(gamma_denominator) <= 1e-15):
        raise ValueError("Eq.4-41 modal denominator is zero")
    gamma = gamma_numerator / gamma_denominator
    gamma_sq = gamma * gamma
    participation_denominator = float(np.sum(gamma_sq))
    if participation_denominator <= 0.0 or not math.isfinite(participation_denominator):
        raise ValueError("Eq.4-42 participation denominator is non-positive")
    participation_ratio = gamma_sq / participation_denominator
    energy_raw = (
        0.5
        * np.diag(M)[:, None]
        * np.square(phi)
        * eigenvalue[None, :]
    )
    energy_column_sum = np.sum(energy_raw, axis=0)
    if np.any(np.abs(energy_column_sum) <= 1e-15):
        raise ValueError("Eq.4-43 energy column denominator is zero")
    energy_norm = energy_raw / energy_column_sum[None, :]
    energy_used = energy_norm if energy_normalized else energy_raw
    energy_total = energy_used @ participation_ratio
    arrays = (
        eigenvalue, phi, gamma_numerator, gamma_denominator, gamma, gamma_sq,
        participation_ratio, energy_raw, energy_column_sum, energy_norm,
        energy_used, energy_total,
    )
    if not all(np.all(np.isfinite(array)) for array in arrays):
        raise ValueError("modal calculation produced non-finite output")
    return ModalResult(
        M=M, K=K, r=r,
        eigenvalue=eigenvalue,
        frequency_hz=np.sqrt(eigenvalue) / (2.0 * math.pi),
        phi=phi,
        gamma_numerator=gamma_numerator,
        gamma_denominator=gamma_denominator,
        gamma=gamma,
        gamma_sq=gamma_sq,
        participation_denominator=participation_denominator,
        participation_ratio=participation_ratio,
        energy_raw=energy_raw,
        energy_column_sum=energy_column_sum,
        energy_normalized=energy_norm,
        energy_used=energy_used,
        energy_total=energy_total,
    )


def analyze(
    M: np.ndarray,
    K: np.ndarray,
    r: np.ndarray,
    mode_count: int = -1,
    energy_normalized: bool = True,
) -> ModalResult:
    eigenvalue, phi = solve_modes(M, K)
    return modal_from_basis(M, K, r, eigenvalue, phi, mode_count, energy_normalized)


def recovered_analysis(
    M_full: np.ndarray,
    K_full: np.ndarray,
    r_full: np.ndarray,
    transform: np.ndarray,
    reduced: ModalResult,
    energy_normalized: bool = True,
) -> ModalResult:
    phi_physical = transform @ reduced.phi
    return modal_from_basis(
        M_full, K_full, r_full, reduced.eigenvalue, phi_physical,
        reduced.eigenvalue.size, energy_normalized,
    )


def make_context(
    *, case_id: str, scope: str, coordinate_identity: str, route_variant: str,
    result_identity: str, excitation_identity: str, recovery_identity: str,
    mode_count: int,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "scope": scope,
        "coordinate_identity": coordinate_identity,
        "route_variant": route_variant,
        "result_identity": result_identity,
        "excitation_identity": excitation_identity,
        "recovery_identity": recovery_identity,
        "mode_count": mode_count,
    }


def emit_array(
    rows: list[dict[str, Any]], context: dict[str, Any], model: str,
    quantity: str, value: Any, status: str = "FINITE",
    uncertainty_flags: str = "",
) -> None:
    array = np.asarray(value, dtype=np.float64)
    if not np.all(np.isfinite(array)):
        raise ValueError(f"cannot emit non-finite {quantity}")
    if array.ndim == 0:
        entries = [(0, 0, float(array))]
    elif array.ndim == 1:
        entries = [(index + 1, 0, float(item)) for index, item in enumerate(array)]
    elif array.ndim == 2:
        entries = [
            (row + 1, column + 1, float(array[row, column]))
            for row in range(array.shape[0])
            for column in range(array.shape[1])
        ]
    else:
        raise ValueError(f"cannot emit rank-{array.ndim} array {quantity}")
    for row_index, column_index, item in entries:
        record = dict(context)
        record.update(
            {
                "row_order": len(rows) + 1,
                "model": model,
                "quantity": quantity,
                "row": row_index,
                "column": column_index,
                "value": canonical_number(item),
                "value_status": status,
                "uncertainty_flags": uncertainty_flags,
            }
        )
        rows.append(record)


def emit_modal(
    rows: list[dict[str, Any]], context: dict[str, Any], model: str,
    result: ModalResult, uncertainty_flags: str,
) -> None:
    quantities = (
        ("input_M", result.M),
        ("input_K", result.K),
        ("input_r", result.r),
        ("eigenvalue", result.eigenvalue),
        ("frequency_hz", result.frequency_hz),
        ("phi_mass_normalized", result.phi),
        ("eq441_numerator", result.gamma_numerator),
        ("eq441_denominator", result.gamma_denominator),
        ("eq441_gamma", result.gamma),
        ("eq442_gamma_sq", result.gamma_sq),
        ("eq442_gamma_sq_sum", result.participation_denominator),
        ("eq442_participation_ratio", result.participation_ratio),
        ("eq443_energy_raw", result.energy_raw),
        ("eq443_energy_column_sum", result.energy_column_sum),
        ("eq443_energy_normalized", result.energy_normalized),
        ("energy_used_by_branch", result.energy_used),
        ("eq444_energy_total", result.energy_total),
        ("invariant_participation_sum", np.sum(result.participation_ratio)),
        ("invariant_energy_total_sum", np.sum(result.energy_total)),
        ("invariant_max_modal_mass_error", np.max(np.abs(result.gamma_denominator - 1.0))),
    )
    for quantity, value in quantities:
        emit_array(rows, context, model, quantity, value, uncertainty_flags=uncertainty_flags)


def emit_mode_sensitivity(
    rows: list[dict[str, Any]], context: dict[str, Any], model: str,
    result: ModalResult, uncertainty_flags: str,
) -> None:
    """Emit the mode-count sweep without duplicating full matrix/basis payloads."""
    quantities = (
        ("eigenvalue", result.eigenvalue),
        ("frequency_hz", result.frequency_hz),
        ("eq441_numerator", result.gamma_numerator),
        ("eq441_denominator", result.gamma_denominator),
        ("eq441_gamma", result.gamma),
        ("eq442_gamma_sq", result.gamma_sq),
        ("eq442_gamma_sq_sum", result.participation_denominator),
        ("eq442_participation_ratio", result.participation_ratio),
        ("eq444_energy_total", result.energy_total),
        ("invariant_participation_sum", np.sum(result.participation_ratio)),
        ("invariant_energy_total_sum", np.sum(result.energy_total)),
        ("invariant_max_modal_mass_error", np.max(np.abs(result.gamma_denominator - 1.0))),
    )
    for quantity, value in quantities:
        emit_array(rows, context, model, quantity, value, uncertainty_flags=uncertainty_flags)


def eq445(
    original: np.ndarray, reduced: np.ndarray, d_original: list[int], d_reduced: list[int]
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float, str]:
    original = np.asarray(original, dtype=np.float64).reshape(-1)
    reduced = np.asarray(reduced, dtype=np.float64).reshape(-1)
    oi = np.asarray(d_original, dtype=int) - 1
    ri = np.asarray(d_reduced, dtype=int) - 1
    if oi.size != ri.size or oi.size == 0:
        raise ValueError("Eq.4-45 coordinate sets are empty or unequal")
    if np.any(oi < 0) or np.any(oi >= original.size) or np.any(ri < 0) or np.any(ri >= reduced.size):
        raise IndexError("Eq.4-45 coordinate set is out of range")
    denominator = original[oi]
    numerator = reduced[ri] - denominator
    if np.any(denominator == 0.0):
        return numerator, denominator, np.zeros_like(numerator), 0.0, "UNDEFINED_DENOMINATOR"
    ratio = numerator / denominator
    status = "ILL_CONDITIONED" if np.any(np.abs(denominator) <= 1e-14) else "FINITE"
    return numerator, denominator, ratio, float(np.sum(ratio)), status


def emit_eq445(
    rows: list[dict[str, Any]], context: dict[str, Any], comparison_model: str,
    original: np.ndarray, reduced: np.ndarray, d_original: list[int], d_reduced: list[int],
    uncertainty_flags: str,
) -> tuple[float, str]:
    numerator, denominator, ratio, total, status = eq445(
        original, reduced, d_original, d_reduced
    )
    emit_array(rows, context, comparison_model, "eq445_numerator", numerator, status, uncertainty_flags)
    emit_array(rows, context, comparison_model, "eq445_denominator", denominator, status, uncertainty_flags)
    if status != "UNDEFINED_DENOMINATOR":
        emit_array(rows, context, comparison_model, "eq445_signed_ratio", ratio, status, uncertainty_flags)
        emit_array(rows, context, comparison_model, "eq445_signed_sum", total, status, uncertainty_flags)
    return total, status


def sum_scope(values: np.ndarray, indices: list[int], scope: str) -> float:
    vector = np.asarray(values, dtype=np.float64).reshape(-1)
    if scope == "ALL":
        return float(np.sum(vector))
    if scope != "SELECTED":
        raise ValueError(f"unknown historical sum scope: {scope}")
    selected = np.asarray(indices, dtype=int) - 1
    return float(np.sum(vector[selected]))


def author_vectors(spec: dict[str, Any], literal_mass: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    dimension = literal_mass.shape[0]
    rule = spec["excitation_rule"]
    if rule == "BINARY_FIRST_3":
        literal = np.zeros(dimension)
        literal[:3] = 1.0
        direction = literal.copy()
    elif rule == "BINARY_FIRST_2":
        literal = np.zeros(dimension)
        literal[:2] = 1.0
        direction = literal.copy()
    elif rule == "MASS_TIMES_ONES":
        direction = np.ones(dimension)
        literal = literal_mass @ direction
    else:
        raise ValueError(f"unknown excitation rule: {rule}")
    return literal, direction


def load_case(case_json: Path) -> tuple[dict[str, Any], dict[str, np.ndarray], dict[str, np.ndarray]]:
    spec = json.loads(case_json.read_text(encoding="utf-8"))
    case_root = case_json.parent
    names = {
        spec["full_M"], spec["full_K"],
        spec["guyan_M"], spec["guyan_K"], spec["guyan_T"],
        spec["cb_M"], spec["cb_K"], spec["cb_T"],
    }
    workspace = read_hdf5_many(case_root / spec["workspace_file"], sorted(names))
    targets = read_hdf5_many(
        case_root / spec["historical_target_file"],
        [
            "E_total", "E_total_guyan", "E_total_cb",
            "energy_sum_orig", "energy_sum_guyan", "energy_sum_cb",
            "total_increase_guyan", "total_increase_cb",
        ],
    )
    return spec, workspace, targets


def add_result(
    results: list[dict[str, Any]], context: dict[str, Any], comparison_model: str,
    eq445_sum: float | None, eq445_status: str,
    boundary_status: str, historical_total: float | None = None,
    author_target: float | None = None,
) -> None:
    error = None
    if historical_total is not None and author_target is not None:
        error = abs(historical_total - author_target)
    record = dict(context)
    record.update(
        {
            "result_order": len(results) + 1,
            "comparison_model": comparison_model,
            "eq445_sum": "" if eq445_sum is None else canonical_number(eq445_sum),
            "eq445_status": eq445_status,
            "historical_total_percent": "" if historical_total is None else canonical_number(historical_total),
            "author_target_percent": "" if author_target is None else canonical_number(author_target),
            "author_abs_error": "" if error is None else canonical_number(error),
            "boundary_status": boundary_status,
        }
    )
    results.append(record)


def run_historical_case(
    spec: dict[str, Any], data: dict[str, np.ndarray], targets: dict[str, np.ndarray],
    values: list[dict[str, Any]], results: list[dict[str, Any]],
) -> None:
    raw_M = as_matrix(data[spec["full_M"]], spec["full_M"])
    raw_K = as_matrix(data[spec["full_K"]], spec["full_K"])
    order = np.asarray(spec["consumer_order"], dtype=int) - 1
    full_M = raw_M[np.ix_(order, order)]
    full_K = raw_K[np.ix_(order, order)]
    literal, _ = author_vectors(spec, full_M)
    T = as_transform(data[spec["guyan_T"]], full_M.shape[0], spec["guyan_T"])
    Tcb = as_transform(data[spec["cb_T"]], full_M.shape[0], spec["cb_T"])
    M_g = as_matrix(data[spec["guyan_M"]], spec["guyan_M"])
    K_g = as_matrix(data[spec["guyan_K"]], spec["guyan_K"])
    M_cb = as_matrix(data[spec["cb_M"]], spec["cb_M"])
    K_cb = as_matrix(data[spec["cb_K"]], spec["cb_K"])
    original = analyze(full_M, full_K, literal, -1, bool(spec["energy_normalized"]))
    guyan = analyze(M_g, K_g, T.T @ literal, -1, bool(spec["energy_normalized"]))
    cb = analyze(M_cb, K_cb, Tcb.T @ literal, -1, bool(spec["energy_normalized"]))
    context = make_context(
        case_id=spec["case_id"], scope="HISTORICAL",
        coordinate_identity="AUTHOR_CONSUMER_ORDER",
        route_variant="AUTHOR_HISTORICAL_FORMULA",
        result_identity="AUTHOR_ROUTE_REPRODUCED",
        excitation_identity="AUTHOR_LITERAL",
        recovery_identity="REDUCED_GENERALIZED",
        mode_count=-1,
    )
    flags = spec["coordinate_status"]
    emit_array(values, context, "guyan", "input_T", T, uncertainty_flags=flags)
    emit_array(values, context, "cb", "input_T", Tcb, uncertainty_flags=flags)
    emit_modal(values, context, "orig", original, flags)
    emit_modal(values, context, "guyan", guyan, flags)
    emit_modal(values, context, "cb", cb, flags)
    sums = {
        "orig": sum_scope(original.energy_total, spec["d_orig"], spec["orig_sum_scope"]),
        "guyan": sum_scope(guyan.energy_total, spec["d_guyan"], spec["guyan_sum_scope"]),
        "cb": sum_scope(cb.energy_total, spec["d_cb"], spec["cb_sum_scope"]),
    }
    denominator = sums["orig"] if spec["historical_denominator"] == "ORIGINAL" else sums["guyan"]
    if denominator == 0.0:
        raise ValueError("historical denominator is exactly zero")
    total_g = (sums["guyan"] - sums["orig"]) / denominator * 100.0
    total_cb = (sums["cb"] - sums["orig"]) / denominator * 100.0
    target_g = float(np.asarray(targets["total_increase_guyan"]).reshape(-1)[0])
    target_cb = float(np.asarray(targets["total_increase_cb"]).reshape(-1)[0])
    target_vectors = {
        "orig": np.asarray(targets["E_total"]).reshape(-1),
        "guyan": np.asarray(targets["E_total_guyan"]).reshape(-1),
        "cb": np.asarray(targets["E_total_cb"]).reshape(-1),
    }
    computed_vectors = {"orig": original.energy_total, "guyan": guyan.energy_total, "cb": cb.energy_total}
    for name in ("orig", "guyan", "cb"):
        if target_vectors[name].shape != computed_vectors[name].shape:
            raise ValueError(f"historical vector length mismatch for {spec['case_id']} {name}")
        emit_array(
            values, context, name, "author_saved_energy_total", target_vectors[name],
            uncertainty_flags=flags,
        )
        emit_array(
            values, context, name, "author_saved_energy_total_abs_error",
            np.abs(computed_vectors[name] - target_vectors[name]),
            uncertainty_flags=flags,
        )
    for name, item in sums.items():
        emit_array(values, context, name, "historical_energy_sum", item, uncertainty_flags=flags)
    emit_array(values, context, "guyan", "historical_total_increase_percent", total_g, uncertainty_flags=flags)
    emit_array(values, context, "cb", "historical_total_increase_percent", total_cb, uncertainty_flags=flags)
    emit_array(values, context, "guyan", "author_saved_total_increase_percent", target_g, uncertainty_flags=flags)
    emit_array(values, context, "cb", "author_saved_total_increase_percent", target_cb, uncertainty_flags=flags)
    if max(abs(total_g - target_g), abs(total_cb - target_cb)) > 1e-8:
        raise ValueError(
            f"historical author-route reproduction failed for {spec['case_id']}: "
            f"{total_g}/{total_cb} vs {target_g}/{target_cb}"
        )
    add_result(
        results, context, "guyan", None, "NOT_EQ445",
        f"{flags}|HISTORICAL_RATIO_OF_SUMS_PERCENT",
        total_g, target_g,
    )
    add_result(
        results, context, "cb", None, "NOT_EQ445",
        f"{flags}|HISTORICAL_RATIO_OF_SUMS_PERCENT",
        total_cb, target_cb,
    )


def paper_variants(
    *, case_id: str, coordinate_identity: str, boundary: str,
    full_M: np.ndarray, full_K: np.ndarray, literal: np.ndarray, direction: np.ndarray,
    T: np.ndarray, M_g_hist: np.ndarray, K_g_hist: np.ndarray,
    Tcb: np.ndarray, M_cb: np.ndarray, K_cb: np.ndarray,
    d_orig: list[int], d_guyan: list[int], d_cb: list[int],
    values: list[dict[str, Any]], results: list[dict[str, Any]],
) -> None:
    M_g_standard = T.T @ full_M @ T
    K_g_standard = T.T @ full_K @ T
    variants = (
        ("GUYAN_HISTORICAL_ONESIDED", "guyan", T, M_g_hist, K_g_hist, d_guyan),
        ("GUYAN_STANDARD_CONGRUENT", "guyan", T, M_g_standard, K_g_standard, d_guyan),
        ("CB_SAVED_CONGRUENT", "cb", Tcb, M_cb, K_cb, d_cb),
    )
    for excitation_identity in ("AUTHOR_LITERAL", "FORCE_CONSISTENT_INFERENCE"):
        full_r = literal if excitation_identity == "AUTHOR_LITERAL" else direction
        full_eigenvalue, full_phi = solve_modes(full_M, full_K)
        for route_variant, model, transform, reduced_M, reduced_K, d_reduced in variants:
            if excitation_identity == "AUTHOR_LITERAL":
                reduced_r = transform.T @ literal
            else:
                reduced_force = transform.T @ full_M @ direction
                reduced_r = linalg.solve(reduced_M, reduced_force, assume_a="sym")
            reduced_eigenvalue, reduced_phi = solve_modes(reduced_M, reduced_K)
            maximum_common = min(full_eigenvalue.size, reduced_eigenvalue.size)
            for mode_count in [-1, *range(1, maximum_common + 1)]:
                original = modal_from_basis(
                    full_M, full_K, full_r, full_eigenvalue, full_phi,
                    mode_count, True,
                )
                reduced = modal_from_basis(
                    reduced_M, reduced_K, reduced_r,
                    reduced_eigenvalue, reduced_phi, mode_count, True,
                )
                direct_recovery = (
                    "CB_REDUCED_GENERALIZED" if model == "cb"
                    else "GUYAN_REDUCED_GENERALIZED"
                )
                context = make_context(
                    case_id=case_id, scope="PAPER",
                    coordinate_identity=coordinate_identity,
                    route_variant=route_variant,
                    result_identity="PAPER_LITERAL_CONDITIONAL",
                    excitation_identity=excitation_identity,
                    recovery_identity=direct_recovery,
                    mode_count=mode_count,
                )
                flags = (
                    f"{boundary}|INPUT_IDENTITY_UNRESOLVED|MODE_COUNT_UNSPECIFIED|"
                    "D_SET_UNSPECIFIED|WHOLE_VS_LOCAL_MODEL_UNRESOLVED"
                )
                if model == "cb":
                    flags += "|CB_ANALOGY_NOT_PRINTED_IN_EQ445|CB_RECOVERY_UNSPECIFIED"
                if mode_count == -1:
                    emit_array(values, context, model, "input_T", transform, uncertainty_flags=flags)
                    emit_modal(values, context, "orig", original, flags)
                    emit_modal(values, context, model, reduced, flags)
                else:
                    emit_mode_sensitivity(values, context, "orig", original, flags)
                    emit_mode_sensitivity(values, context, model, reduced, flags)
                total, status = emit_eq445(
                    values, context, model,
                    original.energy_total, reduced.energy_total,
                    d_orig, d_reduced, flags,
                )
                add_result(results, context, model, total, status, flags)

                recovered = recovered_analysis(
                    full_M, full_K, full_r, transform, reduced, True
                )
                recovered_identity = (
                    "CB_PHYSICAL_RECOVERY_INFERENCE" if model == "cb"
                    else "GUYAN_PHYSICAL_RECOVERY_INFERENCE"
                )
                recovered_context = make_context(
                    case_id=case_id, scope="PAPER",
                    coordinate_identity=coordinate_identity,
                    route_variant=route_variant,
                    result_identity="PAPER_LITERAL_CONDITIONAL",
                    excitation_identity=excitation_identity,
                    recovery_identity=recovered_identity,
                    mode_count=mode_count,
                )
                if mode_count == -1:
                    emit_array(values, recovered_context, model, "input_T", transform, uncertainty_flags=flags)
                    emit_modal(values, recovered_context, "orig", original, flags)
                    emit_modal(values, recovered_context, model, recovered, flags)
                else:
                    emit_mode_sensitivity(values, recovered_context, "orig", original, flags)
                    emit_mode_sensitivity(values, recovered_context, model, recovered, flags)
                total, status = emit_eq445(
                    values, recovered_context, model,
                    original.energy_total, recovered.energy_total,
                    d_orig, d_orig, flags,
                )
                add_result(results, recovered_context, model, total, status, flags)


def run_paper_case(
    spec: dict[str, Any], data: dict[str, np.ndarray],
    values: list[dict[str, Any]], results: list[dict[str, Any]],
) -> None:
    raw_M = as_matrix(data[spec["full_M"]], spec["full_M"])
    raw_K = as_matrix(data[spec["full_K"]], spec["full_K"])
    T = as_transform(data[spec["guyan_T"]], raw_M.shape[0], spec["guyan_T"])
    Tcb = as_transform(data[spec["cb_T"]], raw_M.shape[0], spec["cb_T"])
    M_g = as_matrix(data[spec["guyan_M"]], spec["guyan_M"])
    K_g = as_matrix(data[spec["guyan_K"]], spec["guyan_K"])
    M_cb = as_matrix(data[spec["cb_M"]], spec["cb_M"])
    K_cb = as_matrix(data[spec["cb_K"]], spec["cb_K"])
    coordinate_branches = [
        ("AUTHOR_CONSUMER_ORDER", spec["consumer_order"], spec["coordinate_status"]),
    ]
    if spec["consumer_order"] != spec["producer_order"]:
        coordinate_branches.append(
            ("PRODUCER_ALIGNED_ORDER", spec["producer_order"], "COORDINATE_ALIGNMENT_INFERENCE")
        )
    for coordinate_identity, order_values, boundary in coordinate_branches:
        order = np.asarray(order_values, dtype=int) - 1
        full_M = raw_M[np.ix_(order, order)]
        full_K = raw_K[np.ix_(order, order)]
        literal, direction = author_vectors(spec, full_M)
        paper_variants(
            case_id=spec["case_id"], coordinate_identity=coordinate_identity,
            boundary=boundary, full_M=full_M, full_K=full_K,
            literal=literal, direction=direction,
            T=T, M_g_hist=M_g, K_g_hist=K_g,
            Tcb=Tcb, M_cb=M_cb, K_cb=K_cb,
            d_orig=spec["d_orig"], d_guyan=spec["d_guyan"], d_cb=spec["d_cb"],
            values=values, results=results,
        )


def matlab_struct_field(value: Any, name: str) -> np.ndarray:
    if not hasattr(value, name):
        raise KeyError(f"MATLAB struct is missing field {name}")
    return np.asarray(getattr(value, name), dtype=np.float64)


def run_whole_model_cases(
    input_root: Path, values: list[dict[str, Any]], results: list[dict[str, Any]]
) -> None:
    global_mat = input_root / "g" / "gr.mat"
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        loaded = loadmat(
            global_mat,
            variable_names=["MRrt", "KRrt", "division1", "division2"],
            squeeze_me=True,
            struct_as_record=False,
        )
    for division in (1, 2):
        D = loaded[f"division{division}"]
        full_M = matlab_struct_field(D, "Mo")
        full_K = matlab_struct_field(D, "Ko")
        T = matlab_struct_field(D, "T")
        Tcb = matlab_struct_field(D, "T_cb")
        M_g = matlab_struct_field(D, "M_historical")
        K_g = matlab_struct_field(D, "K_historical")
        M_cb = matlab_struct_field(D, "M_cb")
        K_cb = matlab_struct_field(D, "K_cb")
        direction = matlab_struct_field(D, "force_mask_ordered").reshape(-1)
        d = [1, 2, 3] if division == 1 else [1, 2]
        paper_variants(
            case_id=f"w0{division}",
            coordinate_identity=f"BOARD17_DIVISION{division}_ORDERED_MODEL",
            boundary=(
                "WHOLE_MODEL_EXISTING_CANDIDATE|"
                "BOARD17_CALCULATION_LEVEL_EXTERNAL_ASSET_INDIRECTLY_PASSPORT_BOUND_CURRENT_HASH_MATCH|"
                "LOCAL_NUMERICAL_SUBSTRUCTURE_12D_PENDING"
            ),
            full_M=full_M, full_K=full_K,
            literal=direction, direction=direction,
            T=T, M_g_hist=M_g, K_g_hist=K_g,
            Tcb=Tcb, M_cb=M_cb, K_cb=K_cb,
            d_orig=d, d_guyan=d, d_cb=d,
            values=values, results=results,
        )
        emit_context = make_context(
            case_id=f"w0{division}", scope="WHOLE_INPUT_AUDIT",
            coordinate_identity=f"BOARD17_DIVISION{division}_ORDERED_MODEL",
            route_variant="BOARD17_SEALED_MATRIX_IDENTITY",
            result_identity="WHOLE_MODEL_EXISTING_CANDIDATE",
            excitation_identity="NOT_APPLICABLE",
            recovery_identity="NOT_APPLICABLE",
            mode_count=-1,
        )
        emit_array(values, emit_context, "guyan", "matrix_identity_M_standard_minus_TtMT", matlab_struct_field(D, "M_projected") - T.T @ full_M @ T)
        emit_array(values, emit_context, "guyan", "matrix_identity_K_standard_minus_TtKT", matlab_struct_field(D, "K_projected") - T.T @ full_K @ T)
        emit_array(values, emit_context, "cb", "matrix_identity_M_cb_minus_TtMT", M_cb - Tcb.T @ full_M @ Tcb)
        emit_array(values, emit_context, "cb", "matrix_identity_K_cb_minus_TtKT", K_cb - Tcb.T @ full_K @ Tcb)


def output_manifest(output_root: Path, names: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for order, name in enumerate(names, start=1):
        path = output_root / name
        rows.append(
            {
                "artifact_order": order,
                "relative_path": name,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "manifest_scope": "CANONICAL_PAYLOAD_EXCLUDING_OUTPUT_MANIFEST_ITSELF",
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--execution-token", default="")
    args = parser.parse_args()
    input_root = args.input_root.resolve()
    output_root = args.output_root.resolve()
    if output_root.exists():
        raise FileExistsError(f"exclusive compute output already exists: {output_root}")
    if not input_root.is_dir():
        raise FileNotFoundError(input_root)
    stage_summary = json.loads((input_root / "staging_summary.json").read_text(encoding="utf-8"))
    if (
        stage_summary.get("status") != "PASS"
        or stage_summary.get("step3_run_case_count") != 14
        or stage_summary.get("total_manifest_item_count") != 103
        or stage_summary.get("table4_1_adjudicated") is not False
    ):
        raise RuntimeError("Step4 staging summary contract failed")
    with (input_root / "case_index.csv").open("r", encoding="utf-8", newline="") as stream:
        case_index = list(csv.DictReader(stream))
    if len(case_index) != 14 or len({row["case_id"] for row in case_index}) != 14:
        raise RuntimeError("Step4 case index cardinality/uniqueness failed")

    output_root.mkdir(parents=True)
    values: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    for row in case_index:
        case_json = input_root / row["staged_relative_dir"] / "case.json"
        spec, data, targets = load_case(case_json)
        if spec["case_id"] != row["case_id"] or spec["route_id"] != row["route_id"]:
            raise RuntimeError(f"case index/contract mismatch: {row['case_id']}")
        run_historical_case(spec, data, targets, values, results)
        run_paper_case(spec, data, values, results)
    run_whole_model_cases(input_root, values, results)

    write_csv_new(output_root / "values.csv", values, VALUE_FIELDS)
    write_csv_new(output_root / "case_results.csv", results, RESULT_FIELDS)
    historical = [row for row in results if row["scope"] == "HISTORICAL"]
    paper = [row for row in results if row["scope"] == "PAPER"]
    summary = {
        "schema_version": "BOARD21_STEP4_COMPUTE_V1",
        "implementation": "PYTHON_SCIPY_INDEPENDENT",
        "status": "PASS",
        "input_case_count": 14,
        "whole_model_candidate_count": 2,
        "value_row_count": len(values),
        "case_result_count": len(results),
        "historical_result_count": len(historical),
        "paper_conditional_result_count": len(paper),
        "author_route_reproduction_count": len(historical),
        "max_author_abs_error": max(float(row["author_abs_error"]) for row in historical),
        "formula_4_45_evaluated_conditionally": True,
        "table4_1_adjudicated": False,
        "scientific_status": "AUTHOR_ROUTE_REPRODUCED_AND_PAPER_LITERAL_CONDITIONAL_TABLE4_1_PENDING",
        "values_sha256": sha256_file(output_root / "values.csv"),
        "case_results_sha256": sha256_file(output_root / "case_results.csv"),
    }
    write_json_new(output_root / "compute_summary.json", summary)
    manifest_rows = output_manifest(
        output_root, ["values.csv", "case_results.csv", "compute_summary.json"]
    )
    write_csv_new(
        output_root / "output_manifest.csv",
        manifest_rows,
        ["artifact_order", "relative_path", "size_bytes", "sha256", "manifest_scope"],
    )
    terminal = dict(summary)
    terminal["execution_token"] = args.execution_token
    print(json.dumps(terminal, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, sort_keys=True))
        raise

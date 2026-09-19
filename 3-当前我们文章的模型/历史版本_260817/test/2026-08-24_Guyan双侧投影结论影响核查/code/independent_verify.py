#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Independently verify the isolated Guyan route-comparison exports.

This verifier is deliberately limited to the current isolated test directory.
It reads MATLAB exports below outputs and writes only:

    outputs/python_validation.csv
    outputs/python_validation_summary.json

Required MATLAB exports
-----------------------

Matrices:

    outputs/matrices/division_1_guyan_matrices.mat
    outputs/matrices/division_2_guyan_matrices.mat

Each MAT file must contain one top-level struct named matrixBundle.  Required
fields are division, master, slave, order, T, T_cb, Mf, Mo, Co, Ko,
M_historical, C_historical, K_historical, M_projected, C_projected and
K_projected.  M_cb, C_cb and K_cb are accepted only as an all-or-none optional
trio and, when present, are checked against an independent congruence
projection.

Tables:

    outputs/matrices/guyan_matrix_audit.csv
    outputs/modal/guyan_modal_comparison.csv
    outputs/metrics/historical_baseline_check.csv
    outputs/metrics/route_invariant_check.csv
    outputs/metrics/guyan_response_metrics.csv

Responses:

    outputs/responses/historical_single_sided/
    outputs/responses/projected_congruence/

Each response directory must contain exactly the four expected Chinese-named
CSV files (two divisions times El Centro/Chirp).  Each CSV must contain exactly
the 10 MATLAB columns: time and Original/Guyan/CraigBampton responses for
floors 1--3.

What is independently recomputed
--------------------------------

For each division, NumPy/SciPy independently rebuilds the static constraint,
T, the historical one-sided M/C/K, the standard T-transpose A T matrices,
Craig--Bampton projected matrices from the exported T_cb, matrix diagnostics,
and the first two generalized natural frequencies.  Pandas/NumPy independently
recompute all three-floor full-record NRMSE/peak metrics and all five existing
Chirp-band NRMSE values.  Original and Craig--Bampton response invariance
between the two Guyan routes is independently checked.

The historical-baseline CSV is a MATLAB gate against frozen historical data.
This verifier checks that record's exact schema, coverage, tolerances and
internal pass logic, but intentionally does not read any original asset outside
the isolated outputs tree.  It is therefore labelled as a historical gate
record, not as an independent numerical reproduction.

Missing or ambiguous files, missing rows, duplicated keys, non-finite required
values, failed mathematical gates, or MATLAB/Python disagreement produce a
non-zero exit.  No tolerance is relaxed dynamically.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
import traceback
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd
from scipy import io as scipy_io
from scipy import linalg as scipy_linalg


SCHEMA_VERSION = "2.0"
EXPECTED_DOF = 15
EXPECTED_SAMPLES = 40961
DT_S = 1.0 / 1024.0
STOP_TIME_S = 40.0

MATRIX_GATE_TOL = 1.0e-12
EXPORT_REL_TOL = 1.0e-10
CB_BASIS_REL_TOL = 1.0e-10
CB_EIGENSPACE_REL_TOL = 1.0e-8
TIME_ABS_TOL_S = 1.0e-12
BASELINE_ABS_TOL_MM = 1.0e-9
BASELINE_REL_TOL = 1.0e-10
METRIC_ATOL = 1.0e-9
METRIC_RTOL = 1.0e-8

DIVISION_CONTRACT: dict[int, dict[str, list[int]]] = {
    1: {
        "master": [1, 6, 11, 4, 9, 14],
        "slave": [2, 3, 5, 7, 8, 10, 12, 13, 15],
        "force_mask": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    },
    2: {
        "master": [1, 11, 4, 9, 14],
        "slave": [6, 2, 3, 5, 7, 8, 10, 12, 13, 15],
        "force_mask": [1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    },
}

ROUTES = ("historical_single_sided", "projected_congruence")
EXCITATIONS = ("ElCentro", "Chirp")
DIVISION_LABEL = {1: "第一类划分", 2: "第二类划分"}
EXCITATION_TOKEN = {"ElCentro": "ElCentro地震响应", "Chirp": "Chirp响应"}

RESPONSE_COLUMNS = [
    "时间_s",
    "原结构_一层_mm",
    "Guyan_一层_mm",
    "CraigBampton_一层_mm",
    "原结构_二层_mm",
    "Guyan_二层_mm",
    "CraigBampton_二层_mm",
    "原结构_三层_mm",
    "Guyan_三层_mm",
    "CraigBampton_三层_mm",
]

MATRIX_BUNDLE_REQUIRED_FIELDS = {
    "division",
    "master",
    "slave",
    "order",
    "T",
    "T_cb",
    "Mf",
    "Mo",
    "Co",
    "Ko",
    "M_historical",
    "C_historical",
    "K_historical",
    "M_projected",
    "C_projected",
    "K_projected",
}
MATRIX_BUNDLE_OPTIONAL_CB_FIELDS = {"M_cb", "C_cb", "K_cb"}

MATRIX_AUDIT_COLUMNS = [
    "division",
    "n_master",
    "n_slave",
    "T_rows",
    "T_columns",
    "rank_T",
    "static_residual",
    "relative_M",
    "relative_C",
    "relative_K",
    "symmetry_M_historical",
    "symmetry_C_historical",
    "symmetry_K_historical",
    "symmetry_M_projected",
    "symmetry_C_projected",
    "symmetry_K_projected",
    "min_eigenvalue_M_projected",
    "min_eigenvalue_C_projected",
    "min_eigenvalue_K_projected",
    "damping_negative_tolerance",
]

MODAL_COLUMNS = [
    "division",
    "model",
    "route",
    "mode",
    "full_frequency_hz",
    "frequency_hz",
    "relative_frequency_error_percent",
]

BASELINE_COLUMNS = [
    "division",
    "excitation",
    "samples",
    "max_time_error_s",
    "max_abs_response_error_mm",
    "frozen_response_scale_mm",
    "allowed_max_response_error_mm",
    "relative_frobenius_error",
    "relative_tolerance",
    "pass",
]

INVARIANT_COLUMNS = [
    "division",
    "excitation",
    "max_abs_original_cb_error_mm",
    "reference_scale_mm",
    "allowed_max_error_mm",
    "relative_frobenius_error",
    "relative_tolerance",
    "pass",
]

RESPONSE_METRIC_COLUMNS = [
    "route",
    "division",
    "excitation",
    "scope",
    "lower_frequency_hz",
    "upper_frequency_hz",
    "floor",
    "method",
    "samples",
    "full_record_peak_to_peak_denominator_mm",
    "nrmse_percent",
    "full_absolute_peak_mm",
    "method_absolute_peak_mm",
    "absolute_peak_relative_error_percent",
]

BANDS = (
    ("0.1--1.9 Hz", 0.1, 1.9),
    ("1.9--3.5 Hz", 1.9, 3.5),
    ("3.5--5.4 Hz", 3.5, 5.4),
    ("5.4--8.1 Hz", 5.4, 8.1),
    ("8.1--10.0 Hz", 8.1, 10.0),
)

VALIDATION_COLUMNS = [
    "category",
    "evidence_label",
    "division",
    "route",
    "excitation",
    "scope",
    "method",
    "floor",
    "matrix",
    "mode",
    "metric",
    "python_value",
    "matlab_value",
    "absolute_difference",
    "relative_difference",
    "absolute_tolerance",
    "relative_tolerance",
    "hard_gate",
    "passed",
    "source_file",
    "details",
]


class ValidationError(RuntimeError):
    """Raised for a missing, ambiguous or malformed required input."""


@dataclass(frozen=True)
class ResponseData:
    route: str
    division: int
    excitation: str
    source: Path
    time_s: np.ndarray
    original_mm: np.ndarray
    guyan_mm: np.ndarray
    cb_mm: np.ndarray


class Verifier:
    def __init__(self) -> None:
        self.root = Path(__file__).resolve().parent.parent
        self.output_dir = self._within(self.root / "outputs")
        self.records: list[dict[str, Any]] = []
        self.violations: list[str] = []
        self.inputs: dict[str, dict[str, Any]] = {}
        self.matrix_results: dict[int, dict[str, Any]] = {}
        self.responses: dict[tuple[str, int, str], ResponseData] = {}

    def _within(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root.resolve())
        except ValueError as exc:
            raise ValidationError(
                f"Path escapes isolated test root: {resolved}"
            ) from exc
        return resolved

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    def _require_file(self, relative_path: str) -> Path:
        path = self._within(self.root / relative_path)
        if not path.is_file():
            raise ValidationError(f"Missing required file: {relative_path}")
        self.inputs[relative_path] = {
            "sha256": self._sha256(path),
            "bytes": path.stat().st_size,
        }
        return path

    def _read_csv(self, relative_path: str, expected_columns: list[str]) -> tuple[Path, pd.DataFrame]:
        path = self._require_file(relative_path)
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "gb18030"):
            try:
                frame = pd.read_csv(path, encoding=encoding)
                break
            except UnicodeDecodeError as exc:
                last_error = exc
        else:
            raise ValidationError(
                f"Cannot decode required CSV {relative_path}: {last_error}"
            )
        actual_columns = list(frame.columns)
        if actual_columns != expected_columns:
            raise ValidationError(
                f"CSV schema mismatch in {relative_path}; "
                f"expected {expected_columns}, got {actual_columns}"
            )
        if frame.empty:
            raise ValidationError(f"Required CSV is empty: {relative_path}")
        return path, frame

    @staticmethod
    def _numeric_scalar(value: Any, description: str, allow_nan: bool = False) -> float:
        try:
            result = float(value)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{description} is not numeric: {value!r}") from exc
        if math.isnan(result) and allow_nan:
            return result
        if not math.isfinite(result):
            raise ValidationError(f"{description} must be finite, got {result!r}")
        return result

    @classmethod
    def _integer_scalar(cls, value: Any, description: str) -> int:
        number = cls._numeric_scalar(value, description)
        rounded = int(round(number))
        if abs(number - rounded) > 1.0e-12:
            raise ValidationError(f"{description} must be integer-like, got {number}")
        return rounded

    @staticmethod
    def _truth(value: Any, description: str) -> bool:
        if isinstance(value, (bool, np.bool_)):
            return bool(value)
        if isinstance(value, (int, float, np.integer, np.floating)):
            number = float(value)
            if number == 1.0:
                return True
            if number == 0.0:
                return False
        token = str(value).strip().casefold()
        if token in {"true", "pass", "passed", "ok", "yes", "1"}:
            return True
        if token in {"false", "fail", "failed", "no", "0"}:
            return False
        raise ValidationError(f"{description} is not an unambiguous Boolean: {value!r}")

    @staticmethod
    def _real_array(value: Any, description: str, ndim: int | None = None) -> np.ndarray:
        array = np.asarray(value)
        if np.iscomplexobj(array):
            scale = max(1.0, float(np.max(np.abs(np.real(array)))))
            if float(np.max(np.abs(np.imag(array)))) > 1.0e-12 * scale:
                raise ValidationError(f"{description} has a significant imaginary part")
            array = np.real(array)
        try:
            array = np.asarray(array, dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValidationError(f"{description} is not a real numeric array") from exc
        if ndim is not None and array.ndim != ndim:
            raise ValidationError(
                f"{description} must have {ndim} dimensions, got shape {array.shape}"
            )
        if not np.all(np.isfinite(array)):
            raise ValidationError(f"{description} contains NaN or Inf")
        return array

    @classmethod
    def _int_vector(cls, value: Any, description: str) -> list[int]:
        array = cls._real_array(value, description).reshape(-1)
        result = [cls._integer_scalar(item, description) for item in array]
        return result

    @staticmethod
    def _relative_frobenius(actual: np.ndarray, reference: np.ndarray) -> float:
        denominator = max(float(np.linalg.norm(reference, ord="fro")), np.finfo(float).eps)
        return float(np.linalg.norm(actual - reference, ord="fro") / denominator)

    @staticmethod
    def _symmetry_residual(matrix: np.ndarray) -> float:
        denominator = max(float(np.linalg.norm(matrix, ord="fro")), np.finfo(float).eps)
        return float(np.linalg.norm(matrix - matrix.T, ord="fro") / denominator)

    @staticmethod
    def _min_symmetric_eigenvalue(matrix: np.ndarray) -> float:
        values = np.linalg.eigvalsh((matrix + matrix.T) / 2.0)
        return float(np.min(values))

    @staticmethod
    def _natural_frequencies(mass: np.ndarray, stiffness: np.ndarray, count: int, description: str) -> np.ndarray:
        eigenvalues = scipy_linalg.eigvals(stiffness, mass, check_finite=True)
        if not np.all(np.isfinite(eigenvalues)):
            raise ValidationError(f"{description} generalized eigenvalues contain NaN/Inf")
        real_scale = max(1.0, float(np.max(np.abs(np.real(eigenvalues)))))
        imaginary_tolerance = 1.0e-9 * real_scale
        max_imaginary = float(np.max(np.abs(np.imag(eigenvalues))))
        if max_imaginary > imaginary_tolerance:
            raise ValidationError(
                f"{description} generalized eigenvalues have significant imaginary part "
                f"{max_imaginary:.6e} > {imaginary_tolerance:.6e}"
            )
        positive = np.sort(np.real(eigenvalues)[np.real(eigenvalues) > 0.0])
        if positive.size < count:
            raise ValidationError(
                f"{description} has only {positive.size} positive eigenvalues; need {count}"
            )
        return np.sqrt(positive[:count]) / (2.0 * np.pi)

    @staticmethod
    def _close(actual: float, expected: float, atol: float, rtol: float) -> bool:
        if math.isnan(expected):
            return math.isnan(actual)
        if not math.isfinite(actual) or not math.isfinite(expected):
            return False
        return bool(np.isclose(actual, expected, atol=atol, rtol=rtol))

    def _record(
        self,
        *,
        category: str,
        metric: str,
        python_value: Any,
        passed: bool,
        evidence_label: str = "计算级复现",
        matlab_value: Any = None,
        absolute_difference: Any = None,
        relative_difference: Any = None,
        absolute_tolerance: Any = None,
        relative_tolerance: Any = None,
        hard_gate: bool = True,
        source_file: str = "",
        details: str = "",
        division: Any = "",
        route: str = "",
        excitation: str = "",
        scope: str = "",
        method: str = "",
        floor: Any = "",
        matrix: str = "",
        mode: Any = "",
    ) -> None:
        row = {
            "category": category,
            "evidence_label": evidence_label,
            "division": division,
            "route": route,
            "excitation": excitation,
            "scope": scope,
            "method": method,
            "floor": floor,
            "matrix": matrix,
            "mode": mode,
            "metric": metric,
            "python_value": python_value,
            "matlab_value": matlab_value,
            "absolute_difference": absolute_difference,
            "relative_difference": relative_difference,
            "absolute_tolerance": absolute_tolerance,
            "relative_tolerance": relative_tolerance,
            "hard_gate": bool(hard_gate),
            "passed": bool(passed),
            "source_file": source_file,
            "details": details,
        }
        self.records.append(row)
        if hard_gate and not passed:
            context = ", ".join(
                str(item)
                for item in (
                    category,
                    f"division={division}" if division != "" else "",
                    f"route={route}" if route else "",
                    f"excitation={excitation}" if excitation else "",
                    f"floor={floor}" if floor != "" else "",
                    f"method={method}" if method else "",
                    f"matrix={matrix}" if matrix else "",
                    f"mode={mode}" if mode != "" else "",
                    metric,
                )
                if item
            )
            self.violations.append(f"Hard gate failed: {context}")

    def _compare_numeric(
        self,
        *,
        category: str,
        metric: str,
        python_value: float,
        matlab_value: float,
        atol: float = METRIC_ATOL,
        rtol: float = METRIC_RTOL,
        **context: Any,
    ) -> None:
        passed = self._close(float(matlab_value), float(python_value), atol, rtol)
        if math.isnan(float(python_value)) or math.isnan(float(matlab_value)):
            absolute_difference: float | None = None
            relative_difference: float | None = None
        else:
            absolute_difference = abs(float(matlab_value) - float(python_value))
            relative_difference = absolute_difference / max(
                abs(float(python_value)), np.finfo(float).eps
            )
        self._record(
            category=category,
            metric=metric,
            python_value=python_value,
            matlab_value=matlab_value,
            absolute_difference=absolute_difference,
            relative_difference=relative_difference,
            absolute_tolerance=atol,
            relative_tolerance=rtol,
            passed=passed,
            **context,
        )

    def _gate_value(
        self,
        *,
        category: str,
        metric: str,
        value: float,
        passed: bool,
        tolerance: Any,
        **context: Any,
    ) -> None:
        self._record(
            category=category,
            metric=metric,
            python_value=value,
            absolute_tolerance=tolerance,
            passed=passed,
            **context,
        )

    def _load_matrix_bundle(self, division: int) -> dict[str, Any]:
        relative_path = f"outputs/matrices/division_{division}_guyan_matrices.mat"
        path = self._require_file(relative_path)
        try:
            raw = scipy_io.loadmat(path, squeeze_me=True, struct_as_record=False)
        except NotImplementedError as exc:
            raise ValidationError(
                f"{relative_path} appears to be MATLAB v7.3; expected -v7"
            ) from exc
        public_keys = [key for key in raw if not key.startswith("__")]
        if public_keys != ["matrixBundle"]:
            raise ValidationError(
                f"{relative_path} must contain exactly one top-level variable "
                f"matrixBundle; got {public_keys}"
            )
        bundle = raw["matrixBundle"]
        field_names = set(getattr(bundle, "_fieldnames", []) or [])
        missing = MATRIX_BUNDLE_REQUIRED_FIELDS - field_names
        if missing:
            raise ValidationError(
                f"{relative_path} matrixBundle missing fields: {sorted(missing)}"
            )
        unknown = field_names - (
            MATRIX_BUNDLE_REQUIRED_FIELDS | MATRIX_BUNDLE_OPTIONAL_CB_FIELDS
        )
        if unknown:
            raise ValidationError(
                f"{relative_path} matrixBundle has unexpected fields: {sorted(unknown)}"
            )
        optional_present = field_names & MATRIX_BUNDLE_OPTIONAL_CB_FIELDS
        if optional_present and optional_present != MATRIX_BUNDLE_OPTIONAL_CB_FIELDS:
            raise ValidationError(
                f"{relative_path} optional CB matrices must be all-or-none; got "
                f"{sorted(optional_present)}"
            )

        def field(name: str) -> Any:
            return getattr(bundle, name)

        embedded_division = self._integer_scalar(
            field("division"), f"{relative_path}: matrixBundle.division"
        )
        if embedded_division != division:
            raise ValidationError(
                f"{relative_path} division field is {embedded_division}, expected {division}"
            )
        master = self._int_vector(field("master"), f"{relative_path}: master")
        slave = self._int_vector(field("slave"), f"{relative_path}: slave")
        order = self._int_vector(field("order"), f"{relative_path}: order")
        contract = DIVISION_CONTRACT[division]
        if master != contract["master"]:
            raise ValidationError(
                f"{relative_path} master mismatch: {master} != {contract['master']}"
            )
        if slave != contract["slave"]:
            raise ValidationError(
                f"{relative_path} slave mismatch: {slave} != {contract['slave']}"
            )
        if order != master + slave or sorted(order) != list(range(1, EXPECTED_DOF + 1)):
            raise ValidationError(
                f"{relative_path} order is not the exact one-based [master,slave] permutation"
            )

        nm = len(master)
        ns = len(slave)

        def square(name: str, size: int) -> np.ndarray:
            array = self._real_array(field(name), f"{relative_path}: {name}", ndim=2)
            if array.shape != (size, size):
                raise ValidationError(
                    f"{relative_path}: {name} shape {array.shape}, expected {(size, size)}"
                )
            return array

        mo = square("Mo", EXPECTED_DOF)
        co = square("Co", EXPECTED_DOF)
        ko = square("Ko", EXPECTED_DOF)
        t_exported = self._real_array(field("T"), f"{relative_path}: T", ndim=2)
        if t_exported.shape != (EXPECTED_DOF, nm):
            raise ValidationError(
                f"{relative_path}: T shape {t_exported.shape}, "
                f"expected {(EXPECTED_DOF, nm)}"
            )
        t_cb = self._real_array(field("T_cb"), f"{relative_path}: T_cb", ndim=2)
        if t_cb.shape != (EXPECTED_DOF, nm + 3):
            raise ValidationError(
                f"{relative_path}: T_cb shape {t_cb.shape}, "
                f"expected {(EXPECTED_DOF, nm + 3)}"
            )

        mf = self._real_array(field("Mf"), f"{relative_path}: Mf").reshape(-1)
        if mf.shape != (EXPECTED_DOF,):
            raise ValidationError(
                f"{relative_path}: Mf shape {mf.shape}, expected {(EXPECTED_DOF,)}"
            )

        exported = {
            "M_historical": square("M_historical", nm),
            "C_historical": square("C_historical", nm),
            "K_historical": square("K_historical", nm),
            "M_projected": square("M_projected", nm),
            "C_projected": square("C_projected", nm),
            "K_projected": square("K_projected", nm),
        }

        ksm = ko[nm:, :nm]
        kss = ko[nm:, nm:]
        try:
            static_relation = -scipy_linalg.solve(
                kss, ksm, assume_a="gen", check_finite=True
            )
        except scipy_linalg.LinAlgError as exc:
            raise ValidationError(
                f"{relative_path}: Kss is singular; cannot rebuild Guyan T"
            ) from exc
        t_independent = np.vstack((np.eye(nm), static_relation))

        computed: dict[str, np.ndarray] = {}
        for letter, matrix in (("M", mo), ("C", co), ("K", ko)):
            computed[f"{letter}_historical"] = (
                matrix[:nm, :nm] + matrix[:nm, nm:] @ static_relation
            )
            computed[f"{letter}_projected"] = t_independent.T @ matrix @ t_independent
            computed[f"{letter}_cb"] = t_cb.T @ matrix @ t_cb

        source = self._relative(path)
        t_error = self._relative_frobenius(t_exported, t_independent)
        self._gate_value(
            category="matrix_export",
            metric="relative_frobenius_exported_T_vs_independent_T",
            value=t_error,
            passed=t_error <= EXPORT_REL_TOL,
            tolerance=EXPORT_REL_TOL,
            division=division,
            source_file=source,
        )

        expected_mf = np.asarray(contract["force_mask"], dtype=float) * np.diag(mo)
        mf_error = float(
            np.linalg.norm(mf - expected_mf)
            / max(float(np.linalg.norm(expected_mf)), np.finfo(float).eps)
        )
        self._gate_value(
            category="matrix_export",
            metric="relative_error_Mf_vs_contract",
            value=mf_error,
            passed=mf_error <= EXPORT_REL_TOL,
            tolerance=EXPORT_REL_TOL,
            division=division,
            source_file=source,
        )

        for name, exported_matrix in exported.items():
            error = self._relative_frobenius(exported_matrix, computed[name])
            self._gate_value(
                category="matrix_export",
                metric=f"relative_frobenius_exported_{name}_vs_independent",
                value=error,
                passed=error <= EXPORT_REL_TOL,
                tolerance=EXPORT_REL_TOL,
                division=division,
                matrix=name[0],
                method=name[2:],
                source_file=source,
            )

        if optional_present:
            for letter in ("M", "C", "K"):
                exported_cb = square(f"{letter}_cb", nm + 3)
                error = self._relative_frobenius(
                    exported_cb, computed[f"{letter}_cb"]
                )
                self._gate_value(
                    category="matrix_export",
                    metric=f"relative_frobenius_exported_{letter}_cb_vs_independent",
                    value=error,
                    passed=error <= EXPORT_REL_TOL,
                    tolerance=EXPORT_REL_TOL,
                    division=division,
                    matrix=letter,
                    method="Craig-Bampton",
                    source_file=source,
                )

        top_left_error = self._relative_frobenius(t_cb[:nm, :nm], np.eye(nm))
        top_right_error = float(np.linalg.norm(t_cb[:nm, nm:], ord="fro"))
        bottom_left_error = self._relative_frobenius(
            t_cb[nm:, :nm], static_relation
        )
        for metric, value in (
            ("T_cb_top_left_identity_error", top_left_error),
            ("T_cb_top_right_zero_error", top_right_error),
            ("T_cb_bottom_left_static_constraint_error", bottom_left_error),
        ):
            self._gate_value(
                category="cb_basis",
                metric=metric,
                value=value,
                passed=value <= CB_BASIS_REL_TOL,
                tolerance=CB_BASIS_REL_TOL,
                division=division,
                method="Craig-Bampton",
                source_file=source,
            )

        phi = t_cb[nm:, nm:]
        mss = mo[nm:, nm:]
        gram_m = phi.T @ mss @ phi
        gram_k = phi.T @ ko[nm:, nm:] @ phi
        try:
            modal_operator = scipy_linalg.solve(
                gram_m, gram_k, assume_a="gen", check_finite=True
            )
        except scipy_linalg.LinAlgError as exc:
            raise ValidationError(
                f"{relative_path}: exported T_cb fixed-interface modes are rank deficient"
            ) from exc
        cb_residual = float(
            np.linalg.norm(
                ko[nm:, nm:] @ phi - mss @ phi @ modal_operator, ord="fro"
            )
            / max(
                float(np.linalg.norm(ko[nm:, nm:] @ phi, ord="fro")),
                np.finfo(float).eps,
            )
        )
        self._gate_value(
            category="cb_basis",
            metric="fixed_interface_eigenspace_residual",
            value=cb_residual,
            passed=cb_residual <= CB_EIGENSPACE_REL_TOL,
            tolerance=CB_EIGENSPACE_REL_TOL,
            division=division,
            method="Craig-Bampton",
            source_file=source,
        )

        rank_t = int(np.linalg.matrix_rank(t_independent))
        rank_t_cb = int(np.linalg.matrix_rank(t_cb))
        static_residual = float(
            np.linalg.norm(ksm + kss @ static_relation, ord="fro")
            / max(float(np.linalg.norm(ksm, ord="fro")), np.finfo(float).eps)
        )
        self._gate_value(
            category="matrix_invariant",
            metric="rank_T",
            value=rank_t,
            passed=rank_t == nm,
            tolerance=0,
            division=division,
            source_file=source,
        )
        self._gate_value(
            category="matrix_invariant",
            metric="rank_T_cb",
            value=rank_t_cb,
            passed=rank_t_cb == nm + 3,
            tolerance=0,
            division=division,
            method="Craig-Bampton",
            source_file=source,
        )
        self._gate_value(
            category="matrix_invariant",
            metric="static_residual",
            value=static_residual,
            passed=static_residual < MATRIX_GATE_TOL,
            tolerance=MATRIX_GATE_TOL,
            division=division,
            source_file=source,
        )

        audit: dict[str, float | int] = {
            "division": division,
            "n_master": nm,
            "n_slave": ns,
            "T_rows": int(t_independent.shape[0]),
            "T_columns": int(t_independent.shape[1]),
            "rank_T": rank_t,
            "static_residual": static_residual,
        }
        for letter in ("M", "C", "K"):
            historical = computed[f"{letter}_historical"]
            projected = computed[f"{letter}_projected"]
            audit[f"relative_{letter}"] = self._relative_frobenius(
                historical, projected
            )
            audit[f"symmetry_{letter}_historical"] = self._symmetry_residual(
                historical
            )
            audit[f"symmetry_{letter}_projected"] = self._symmetry_residual(
                projected
            )
            audit[f"min_eigenvalue_{letter}_projected"] = (
                self._min_symmetric_eigenvalue(projected)
            )

            relative_difference = float(audit[f"relative_{letter}"])
            self._record(
                category="route_difference",
                metric="relative_frobenius_historical_vs_projected",
                python_value=relative_difference,
                passed=(letter != "K" or relative_difference < MATRIX_GATE_TOL),
                absolute_tolerance=(MATRIX_GATE_TOL if letter == "K" else ""),
                hard_gate=(letter == "K"),
                division=division,
                matrix=letter,
                source_file=source,
                details=(
                    "M/C difference is the quantity under study; K equivalence is a hard gate."
                ),
            )

            for method_name, matrix_value, symmetry_is_gate in (
                ("full", {"M": mo, "C": co, "K": ko}[letter], True),
                ("historical", historical, letter == "K"),
                ("projected", projected, True),
                ("Craig-Bampton", computed[f"{letter}_cb"], True),
            ):
                symmetry = self._symmetry_residual(matrix_value)
                self._record(
                    category="matrix_property",
                    metric="relative_symmetry_residual",
                    python_value=symmetry,
                    passed=(symmetry < MATRIX_GATE_TOL),
                    absolute_tolerance=MATRIX_GATE_TOL,
                    hard_gate=symmetry_is_gate,
                    division=division,
                    matrix=letter,
                    method=method_name,
                    source_file=source,
                    details=(
                        "Historical one-sided M/C symmetry is diagnostic, not a gate; "
                        "historical K remains a gate because it must equal projected K."
                        if not symmetry_is_gate
                        else ""
                    ),
                )

        damping_negative_tolerance = MATRIX_GATE_TOL * max(
            float(np.linalg.norm(computed["C_projected"], ord=2)), 1.0
        )
        audit["damping_negative_tolerance"] = damping_negative_tolerance

        for method_name, matrices in (
            ("full", {"M": mo, "C": co, "K": ko}),
            (
                "historical",
                {
                    "M": computed["M_historical"],
                    "C": computed["C_historical"],
                    "K": computed["K_historical"],
                },
            ),
            (
                "projected",
                {
                    "M": computed["M_projected"],
                    "C": computed["C_projected"],
                    "K": computed["K_projected"],
                },
            ),
            (
                "Craig-Bampton",
                {
                    "M": computed["M_cb"],
                    "C": computed["C_cb"],
                    "K": computed["K_cb"],
                },
            ),
        ):
            for letter, matrix_value in matrices.items():
                minimum = self._min_symmetric_eigenvalue(matrix_value)
                if letter in {"M", "K"}:
                    passed = minimum > 0.0
                    tolerance = 0.0
                else:
                    negative_tolerance = MATRIX_GATE_TOL * max(
                        float(np.linalg.norm(matrix_value, ord=2)), 1.0
                    )
                    passed = minimum >= -negative_tolerance
                    tolerance = negative_tolerance
                self._record(
                    category="matrix_property",
                    metric="minimum_symmetric_eigenvalue",
                    python_value=minimum,
                    passed=passed,
                    absolute_tolerance=tolerance,
                    hard_gate=(method_name != "historical" or letter == "K"),
                    division=division,
                    matrix=letter,
                    method=method_name,
                    source_file=source,
                    details=(
                        "Historical one-sided M/C definiteness is diagnostic because "
                        "the matrices can be nonsymmetric."
                        if method_name == "historical" and letter in {"M", "C"}
                        else ""
                    ),
                )

        modal = {
            ("Original", "route_invariant"): self._natural_frequencies(
                mo, ko, 2, f"Division {division} Original"
            ),
            ("Guyan", "historical_single_sided"): self._natural_frequencies(
                computed["M_historical"],
                computed["K_historical"],
                2,
                f"Division {division} historical Guyan",
            ),
            ("Guyan", "projected_congruence"): self._natural_frequencies(
                computed["M_projected"],
                computed["K_projected"],
                2,
                f"Division {division} projected Guyan",
            ),
            ("Craig-Bampton", "route_invariant"): self._natural_frequencies(
                computed["M_cb"],
                computed["K_cb"],
                2,
                f"Division {division} Craig-Bampton",
            ),
        }

        return {
            "source": path,
            "master": master,
            "slave": slave,
            "order": order,
            "T": t_independent,
            "T_cb": t_cb,
            "computed": computed,
            "audit": audit,
            "modal": modal,
        }

    def validate_matrices(self) -> None:
        for division in (1, 2):
            self.matrix_results[division] = self._load_matrix_bundle(division)
        self._validate_matrix_audit_csv()
        self._validate_modal_csv()

    def _validate_matrix_audit_csv(self) -> None:
        relative_path = "outputs/matrices/guyan_matrix_audit.csv"
        path, frame = self._read_csv(relative_path, MATRIX_AUDIT_COLUMNS)
        if len(frame) != 2:
            raise ValidationError(
                f"{relative_path} must have exactly 2 rows, got {len(frame)}"
            )
        divisions = [
            self._integer_scalar(value, f"{relative_path}: division")
            for value in frame["division"]
        ]
        if sorted(divisions) != [1, 2] or len(set(divisions)) != 2:
            raise ValidationError(
                f"{relative_path} must contain one row for each division"
            )
        source = self._relative(path)
        for index, division in enumerate(divisions):
            row = frame.iloc[index]
            expected = self.matrix_results[division]["audit"]
            for column in MATRIX_AUDIT_COLUMNS:
                if column in {
                    "division",
                    "n_master",
                    "n_slave",
                    "T_rows",
                    "T_columns",
                    "rank_T",
                }:
                    matlab_value = self._integer_scalar(
                        row[column], f"{relative_path}: {column}"
                    )
                    python_value = int(expected[column])
                    self._compare_numeric(
                        category="matrix_audit_table",
                        metric=column,
                        python_value=float(python_value),
                        matlab_value=float(matlab_value),
                        atol=0.0,
                        rtol=0.0,
                        division=division,
                        source_file=source,
                    )
                else:
                    matlab_value = self._numeric_scalar(
                        row[column], f"{relative_path}: {column}"
                    )
                    self._compare_numeric(
                        category="matrix_audit_table",
                        metric=column,
                        python_value=float(expected[column]),
                        matlab_value=matlab_value,
                        division=division,
                        source_file=source,
                    )

    def _validate_modal_csv(self) -> None:
        relative_path = "outputs/modal/guyan_modal_comparison.csv"
        path, frame = self._read_csv(relative_path, MODAL_COLUMNS)
        expected_keys = {
            (division, model, route, mode)
            for division in (1, 2)
            for model, route in (
                ("Original", "route_invariant"),
                ("Guyan", "historical_single_sided"),
                ("Guyan", "projected_congruence"),
                ("Craig-Bampton", "route_invariant"),
            )
            for mode in (1, 2)
        }
        rows: dict[tuple[int, str, str, int], pd.Series] = {}
        for _, row in frame.iterrows():
            division = self._integer_scalar(row["division"], f"{relative_path}: division")
            model = str(row["model"]).strip()
            route = str(row["route"]).strip()
            mode = self._integer_scalar(row["mode"], f"{relative_path}: mode")
            key = (division, model, route, mode)
            if key in rows:
                raise ValidationError(f"Duplicate modal key in {relative_path}: {key}")
            rows[key] = row
        if set(rows) != expected_keys:
            missing = sorted(expected_keys - set(rows))
            extra = sorted(set(rows) - expected_keys)
            raise ValidationError(
                f"{relative_path} modal coverage mismatch; missing={missing}, extra={extra}"
            )

        source = self._relative(path)
        for key in sorted(expected_keys):
            division, model, route, mode = key
            row = rows[key]
            full_frequency = float(
                self.matrix_results[division]["modal"][
                    ("Original", "route_invariant")
                ][mode - 1]
            )
            frequency = float(
                self.matrix_results[division]["modal"][(model, route)][mode - 1]
            )
            error_percent = abs(frequency - full_frequency) / full_frequency * 100.0
            context = {
                "division": division,
                "method": model,
                "route": route,
                "mode": mode,
                "source_file": source,
            }
            for metric, python_value in (
                ("full_frequency_hz", full_frequency),
                ("frequency_hz", frequency),
                ("relative_frequency_error_percent", error_percent),
            ):
                matlab_value = self._numeric_scalar(
                    row[metric], f"{relative_path}: {key} {metric}"
                )
                self._compare_numeric(
                    category="modal_table",
                    metric=metric,
                    python_value=python_value,
                    matlab_value=matlab_value,
                    **context,
                )

    def _load_one_response(
        self, route: str, division: int, excitation: str
    ) -> ResponseData:
        filename = (
            f"{DIVISION_LABEL[division]}_{EXCITATION_TOKEN[excitation]}.csv"
        )
        relative_path = f"outputs/responses/{route}/{filename}"
        path, frame = self._read_csv(relative_path, RESPONSE_COLUMNS)
        if len(frame) != EXPECTED_SAMPLES:
            raise ValidationError(
                f"{relative_path} has {len(frame)} samples, expected {EXPECTED_SAMPLES}"
            )
        try:
            values = frame.to_numpy(dtype=float)
        except (TypeError, ValueError) as exc:
            raise ValidationError(
                f"{relative_path} contains nonnumeric response data"
            ) from exc
        if values.shape != (EXPECTED_SAMPLES, 10) or not np.all(np.isfinite(values)):
            raise ValidationError(
                f"{relative_path} must be a finite {EXPECTED_SAMPLES}x10 numeric table"
            )
        time_s = values[:, 0]
        expected_time = np.arange(EXPECTED_SAMPLES, dtype=float) * DT_S
        max_time_error = float(np.max(np.abs(time_s - expected_time)))
        self._gate_value(
            category="response_input",
            metric="max_fixed_step_time_error_s",
            value=max_time_error,
            passed=max_time_error <= TIME_ABS_TOL_S,
            tolerance=TIME_ABS_TOL_S,
            route=route,
            division=division,
            excitation=excitation,
            source_file=self._relative(path),
        )
        if not np.all(np.diff(time_s) > 0.0):
            raise ValidationError(f"{relative_path} time axis is not strictly increasing")
        if abs(float(time_s[-1]) - STOP_TIME_S) > TIME_ABS_TOL_S:
            raise ValidationError(
                f"{relative_path} final time is {time_s[-1]}, expected {STOP_TIME_S}"
            )
        original = values[:, [1, 4, 7]]
        guyan = values[:, [2, 5, 8]]
        cb = values[:, [3, 6, 9]]
        return ResponseData(
            route=route,
            division=division,
            excitation=excitation,
            source=path,
            time_s=time_s,
            original_mm=original,
            guyan_mm=guyan,
            cb_mm=cb,
        )

    def validate_responses(self) -> None:
        for route in ROUTES:
            directory = self._within(self.root / "outputs" / "responses" / route)
            if not directory.is_dir():
                raise ValidationError(
                    f"Missing required response directory: {self._relative(directory)}"
                )
            expected_names = {
                f"{DIVISION_LABEL[division]}_{EXCITATION_TOKEN[excitation]}.csv"
                for division in (1, 2)
                for excitation in EXCITATIONS
            }
            actual_names = {path.name for path in directory.glob("*.csv")}
            if actual_names != expected_names:
                raise ValidationError(
                    f"Ambiguous response CSV set in {self._relative(directory)}; "
                    f"missing={sorted(expected_names - actual_names)}, "
                    f"extra={sorted(actual_names - expected_names)}"
                )
            for division in (1, 2):
                for excitation in EXCITATIONS:
                    key = (route, division, excitation)
                    self.responses[key] = self._load_one_response(
                        route, division, excitation
                    )
        self._validate_historical_baseline_csv()
        self._validate_route_invariant_csv()
        self._validate_response_metrics_csv()

    def _validate_historical_baseline_csv(self) -> None:
        relative_path = "outputs/metrics/historical_baseline_check.csv"
        path, frame = self._read_csv(relative_path, BASELINE_COLUMNS)
        expected_keys = {
            (division, excitation)
            for division in (1, 2)
            for excitation in EXCITATIONS
        }
        rows: dict[tuple[int, str], pd.Series] = {}
        for _, row in frame.iterrows():
            division = self._integer_scalar(row["division"], f"{relative_path}: division")
            excitation = str(row["excitation"]).strip()
            key = (division, excitation)
            if key in rows:
                raise ValidationError(f"Duplicate baseline key in {relative_path}: {key}")
            rows[key] = row
        if set(rows) != expected_keys:
            raise ValidationError(
                f"{relative_path} must contain exactly four division/excitation rows; "
                f"missing={sorted(expected_keys - set(rows))}, "
                f"extra={sorted(set(rows) - expected_keys)}"
            )

        source = self._relative(path)
        for key in sorted(expected_keys):
            division, excitation = key
            row = rows[key]
            samples = self._integer_scalar(row["samples"], f"{relative_path}: samples")
            max_time = self._numeric_scalar(
                row["max_time_error_s"], f"{relative_path}: max_time_error_s"
            )
            max_abs = self._numeric_scalar(
                row["max_abs_response_error_mm"],
                f"{relative_path}: max_abs_response_error_mm",
            )
            scale = self._numeric_scalar(
                row["frozen_response_scale_mm"],
                f"{relative_path}: frozen_response_scale_mm",
            )
            allowed = self._numeric_scalar(
                row["allowed_max_response_error_mm"],
                f"{relative_path}: allowed_max_response_error_mm",
            )
            relative_error = self._numeric_scalar(
                row["relative_frobenius_error"],
                f"{relative_path}: relative_frobenius_error",
            )
            relative_tolerance = self._numeric_scalar(
                row["relative_tolerance"], f"{relative_path}: relative_tolerance"
            )
            matlab_pass = self._truth(row["pass"], f"{relative_path}: pass")
            expected_allowed = BASELINE_ABS_TOL_MM + BASELINE_REL_TOL * max(1.0, scale)
            logical_pass = (
                samples == EXPECTED_SAMPLES
                and max_time <= TIME_ABS_TOL_S
                and max_abs <= allowed
                and relative_error <= relative_tolerance
                and relative_tolerance == BASELINE_REL_TOL
            )
            context = {
                "division": division,
                "excitation": excitation,
                "source_file": source,
                "evidence_label": "历史值（MATLAB基线门槛记录）",
            }
            self._compare_numeric(
                category="historical_baseline_record",
                metric="samples",
                python_value=float(EXPECTED_SAMPLES),
                matlab_value=float(samples),
                atol=0.0,
                rtol=0.0,
                **context,
            )
            self._compare_numeric(
                category="historical_baseline_record",
                metric="allowed_max_response_error_mm_formula",
                python_value=expected_allowed,
                matlab_value=allowed,
                **context,
            )
            for metric, value, passed, tolerance in (
                ("max_time_error_s", max_time, max_time <= TIME_ABS_TOL_S, TIME_ABS_TOL_S),
                ("max_abs_response_error_mm", max_abs, max_abs <= allowed, allowed),
                (
                    "relative_frobenius_error",
                    relative_error,
                    relative_error <= relative_tolerance,
                    relative_tolerance,
                ),
            ):
                self._record(
                    category="historical_baseline_record",
                    metric=metric,
                    python_value=value,
                    absolute_tolerance=tolerance,
                    passed=passed,
                    evidence_label="历史值（MATLAB基线门槛记录）",
                    division=division,
                    excitation=excitation,
                    source_file=source,
                    details=(
                        "Checked from the isolated MATLAB gate table; frozen source "
                        "responses are not independently reread here."
                    ),
                )
            self._record(
                category="historical_baseline_record",
                metric="pass_logic",
                python_value=logical_pass,
                matlab_value=matlab_pass,
                passed=(logical_pass and matlab_pass),
                evidence_label="历史值（MATLAB基线门槛记录）",
                division=division,
                excitation=excitation,
                source_file=source,
            )

    def _validate_route_invariant_csv(self) -> None:
        relative_path = "outputs/metrics/route_invariant_check.csv"
        path, frame = self._read_csv(relative_path, INVARIANT_COLUMNS)
        expected_keys = {
            (division, excitation)
            for division in (1, 2)
            for excitation in EXCITATIONS
        }
        rows: dict[tuple[int, str], pd.Series] = {}
        for _, row in frame.iterrows():
            division = self._integer_scalar(row["division"], f"{relative_path}: division")
            excitation = str(row["excitation"]).strip()
            key = (division, excitation)
            if key in rows:
                raise ValidationError(f"Duplicate invariant key in {relative_path}: {key}")
            rows[key] = row
        if set(rows) != expected_keys:
            raise ValidationError(
                f"{relative_path} must contain exactly four division/excitation rows; "
                f"missing={sorted(expected_keys - set(rows))}, "
                f"extra={sorted(set(rows) - expected_keys)}"
            )

        source = self._relative(path)
        for key in sorted(expected_keys):
            division, excitation = key
            historical = self.responses[("historical_single_sided", division, excitation)]
            projected = self.responses[("projected_congruence", division, excitation)]
            time_error = float(np.max(np.abs(historical.time_s - projected.time_s)))
            invariant_historical = np.column_stack(
                (historical.original_mm, historical.cb_mm)
            )
            invariant_projected = np.column_stack(
                (projected.original_mm, projected.cb_mm)
            )
            difference = invariant_historical - invariant_projected
            max_abs = float(np.max(np.abs(difference)))
            scale = float(np.max(np.abs(invariant_historical)))
            allowed = BASELINE_ABS_TOL_MM + BASELINE_REL_TOL * max(1.0, scale)
            relative_error = float(
                np.linalg.norm(difference)
                / max(float(np.linalg.norm(invariant_historical)), np.finfo(float).eps)
            )
            logical_pass = (
                time_error <= TIME_ABS_TOL_S
                and max_abs <= allowed
                and relative_error <= BASELINE_REL_TOL
            )
            row = rows[key]
            context = {
                "division": division,
                "excitation": excitation,
                "source_file": source,
            }
            self._gate_value(
                category="route_invariant",
                metric="max_time_axis_difference_s",
                value=time_error,
                passed=time_error <= TIME_ABS_TOL_S,
                tolerance=TIME_ABS_TOL_S,
                **context,
            )
            comparisons = {
                "max_abs_original_cb_error_mm": max_abs,
                "reference_scale_mm": scale,
                "allowed_max_error_mm": allowed,
                "relative_frobenius_error": relative_error,
                "relative_tolerance": BASELINE_REL_TOL,
            }
            for metric, python_value in comparisons.items():
                matlab_value = self._numeric_scalar(
                    row[metric], f"{relative_path}: {key} {metric}"
                )
                self._compare_numeric(
                    category="route_invariant",
                    metric=metric,
                    python_value=python_value,
                    matlab_value=matlab_value,
                    **context,
                )
            matlab_pass = self._truth(row["pass"], f"{relative_path}: {key} pass")
            self._record(
                category="route_invariant",
                metric="pass_logic",
                python_value=logical_pass,
                matlab_value=matlab_pass,
                passed=(logical_pass and matlab_pass),
                division=division,
                excitation=excitation,
                source_file=source,
            )

    @staticmethod
    def _nrmse_percent(
        reference: np.ndarray,
        approximation: np.ndarray,
        mask: np.ndarray,
        denominator: float,
    ) -> float:
        difference = reference[mask] - approximation[mask]
        return float(np.sqrt(np.mean(difference * difference)) / denominator * 100.0)

    def _expected_response_metric_rows(self) -> dict[tuple[Any, ...], dict[str, float]]:
        expected: dict[tuple[Any, ...], dict[str, float]] = {}
        for route in ROUTES:
            for division in (1, 2):
                for excitation in EXCITATIONS:
                    response = self.responses[(route, division, excitation)]
                    for floor_index in range(3):
                        floor = floor_index + 1
                        reference = response.original_mm[:, floor_index]
                        denominator = float(np.max(reference) - np.min(reference))
                        full_peak = float(np.max(np.abs(reference)))
                        if denominator <= np.finfo(float).eps:
                            raise ValidationError(
                                f"Zero full-record peak-to-peak denominator: "
                                f"{route}, division {division}, {excitation}, floor {floor}"
                            )
                        if full_peak <= np.finfo(float).eps:
                            raise ValidationError(
                                f"Zero full-model absolute peak: {route}, division "
                                f"{division}, {excitation}, floor {floor}"
                            )
                        for method, approximation in (
                            ("Guyan", response.guyan_mm[:, floor_index]),
                            ("Craig-Bampton", response.cb_mm[:, floor_index]),
                        ):
                            method_peak = float(np.max(np.abs(approximation)))
                            peak_error = abs(method_peak - full_peak) / full_peak * 100.0
                            key = (
                                route,
                                division,
                                excitation,
                                "full_record",
                                floor,
                                method,
                            )
                            expected[key] = {
                                "lower_frequency_hz": math.nan,
                                "upper_frequency_hz": math.nan,
                                "samples": float(EXPECTED_SAMPLES),
                                "full_record_peak_to_peak_denominator_mm": denominator,
                                "nrmse_percent": self._nrmse_percent(
                                    reference,
                                    approximation,
                                    np.ones(EXPECTED_SAMPLES, dtype=bool),
                                    denominator,
                                ),
                                "full_absolute_peak_mm": full_peak,
                                "method_absolute_peak_mm": method_peak,
                                "absolute_peak_relative_error_percent": peak_error,
                            }

                            if excitation == "Chirp":
                                instantaneous_frequency = (
                                    0.1
                                    + (10.0 - 0.1)
                                    / STOP_TIME_S
                                    * response.time_s
                                )
                                for band_index, (scope, lower, upper) in enumerate(BANDS):
                                    if band_index < len(BANDS) - 1:
                                        mask = (
                                            (instantaneous_frequency >= lower)
                                            & (instantaneous_frequency < upper)
                                        )
                                    else:
                                        mask = (
                                            (instantaneous_frequency >= lower)
                                            & (instantaneous_frequency <= upper)
                                        )
                                    samples = int(np.count_nonzero(mask))
                                    if samples <= 1:
                                        raise ValidationError(
                                            f"Insufficient Chirp samples in {scope}"
                                        )
                                    band_key = (
                                        route,
                                        division,
                                        excitation,
                                        scope,
                                        floor,
                                        method,
                                    )
                                    expected[band_key] = {
                                        "lower_frequency_hz": lower,
                                        "upper_frequency_hz": upper,
                                        "samples": float(samples),
                                        "full_record_peak_to_peak_denominator_mm": denominator,
                                        "nrmse_percent": self._nrmse_percent(
                                            reference,
                                            approximation,
                                            mask,
                                            denominator,
                                        ),
                                        "full_absolute_peak_mm": math.nan,
                                        "method_absolute_peak_mm": math.nan,
                                        "absolute_peak_relative_error_percent": math.nan,
                                    }
        return expected

    def _validate_response_metrics_csv(self) -> None:
        relative_path = "outputs/metrics/guyan_response_metrics.csv"
        path, frame = self._read_csv(relative_path, RESPONSE_METRIC_COLUMNS)
        expected = self._expected_response_metric_rows()
        rows: dict[tuple[Any, ...], pd.Series] = {}
        for _, row in frame.iterrows():
            route = str(row["route"]).strip()
            division = self._integer_scalar(row["division"], f"{relative_path}: division")
            excitation = str(row["excitation"]).strip()
            scope = str(row["scope"]).strip()
            floor = self._integer_scalar(row["floor"], f"{relative_path}: floor")
            method = str(row["method"]).strip()
            key = (route, division, excitation, scope, floor, method)
            if key in rows:
                raise ValidationError(f"Duplicate response metric key: {key}")
            rows[key] = row
        if set(rows) != set(expected):
            missing = sorted(set(expected) - set(rows))
            extra = sorted(set(rows) - set(expected))
            raise ValidationError(
                f"{relative_path} response metric coverage mismatch; "
                f"expected {len(expected)} rows, got {len(rows)}; "
                f"missing={missing[:12]}, extra={extra[:12]}"
            )

        source = self._relative(path)
        for key in sorted(expected):
            route, division, excitation, scope, floor, method = key
            row = rows[key]
            values = expected[key]
            context = {
                "route": route,
                "division": division,
                "excitation": excitation,
                "scope": scope,
                "floor": floor,
                "method": method,
                "source_file": source,
            }
            for metric, python_value in values.items():
                allow_nan = math.isnan(float(python_value))
                matlab_value = self._numeric_scalar(
                    row[metric],
                    f"{relative_path}: {key} {metric}",
                    allow_nan=allow_nan,
                )
                if metric == "samples":
                    matlab_samples = self._integer_scalar(
                        row[metric], f"{relative_path}: {key} samples"
                    )
                    self._compare_numeric(
                        category="response_metric_table",
                        metric=metric,
                        python_value=python_value,
                        matlab_value=float(matlab_samples),
                        atol=0.0,
                        rtol=0.0,
                        **context,
                    )
                else:
                    self._compare_numeric(
                        category="response_metric_table",
                        metric=metric,
                        python_value=python_value,
                        matlab_value=matlab_value,
                        **context,
                    )

    def validate(self) -> None:
        if not self.output_dir.is_dir():
            raise ValidationError(
                "Missing outputs directory. MATLAB exports must be produced first."
            )
        self.validate_matrices()
        self.validate_responses()

    def write_artifacts(self, status: str, error: str = "") -> None:
        self.output_dir.mkdir(parents=False, exist_ok=True)
        validation_path = self._within(self.output_dir / "python_validation.csv")
        summary_path = self._within(
            self.output_dir / "python_validation_summary.json"
        )
        frame = pd.DataFrame(self.records, columns=VALIDATION_COLUMNS)
        frame.to_csv(validation_path, index=False, encoding="utf-8-sig")
        category_counts: dict[str, int] = {}
        for row in self.records:
            category = str(row["category"])
            category_counts[category] = category_counts.get(category, 0) + 1
        summary = {
            "schema_version": SCHEMA_VERSION,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "exit_semantics": {
                "PASS": 0,
                "FAIL": 2,
                "ERROR": 3,
            },
            "isolated_test_root": str(self.root),
            "inputs": self.inputs,
            "records": {
                "total": len(self.records),
                "passed": sum(bool(row["passed"]) for row in self.records),
                "failed": sum(not bool(row["passed"]) for row in self.records),
                "by_category": category_counts,
            },
            "violations": self.violations,
            "error": error,
            "fixed_contract": {
                "matrix_files": [
                    "outputs/matrices/division_1_guyan_matrices.mat",
                    "outputs/matrices/division_2_guyan_matrices.mat",
                ],
                "matrix_audit": "outputs/matrices/guyan_matrix_audit.csv",
                "modal": "outputs/modal/guyan_modal_comparison.csv",
                "historical_baseline": (
                    "outputs/metrics/historical_baseline_check.csv"
                ),
                "route_invariant": "outputs/metrics/route_invariant_check.csv",
                "response_metrics": "outputs/metrics/guyan_response_metrics.csv",
                "response_routes": list(ROUTES),
                "expected_response_csv_count": 8,
                "expected_response_metric_rows": 168,
            },
            "tolerances": {
                "matrix_gate": MATRIX_GATE_TOL,
                "export_relative": EXPORT_REL_TOL,
                "cb_basis_relative": CB_BASIS_REL_TOL,
                "cb_eigenspace_relative": CB_EIGENSPACE_REL_TOL,
                "time_absolute_s": TIME_ABS_TOL_S,
                "historical_baseline_absolute_mm": BASELINE_ABS_TOL_MM,
                "historical_baseline_relative": BASELINE_REL_TOL,
                "matlab_python_metric_absolute": METRIC_ATOL,
                "matlab_python_metric_relative": METRIC_RTOL,
            },
            "evidence_labels": {
                "matrix_modal_response_metrics": "计算级复现",
                "route_invariant": "计算级复现",
                "historical_baseline": (
                    "历史值（MATLAB基线门槛记录；本脚本不读取隔离目录外原资产）"
                ),
                "plotting": "未涉及",
                "decision": "本脚本只验证，不替 Doctor Bego 选择论文权威路线",
            },
            "output_files": {
                "validation_csv": self._relative(validation_path),
                "summary_json": self._relative(summary_path),
            },
        }
        with summary_path.open("w", encoding="utf-8", newline="\n") as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)
            stream.write("\n")


def main() -> int:
    verifier = Verifier()
    try:
        verifier.validate()
        if verifier.violations:
            status = "FAIL"
            exit_code = 2
        else:
            status = "PASS"
            exit_code = 0
        verifier.write_artifacts(status)
        print(
            f"independent_verify: {status}; "
            f"records={len(verifier.records)}; violations={len(verifier.violations)}"
        )
        return exit_code
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"
        verifier.violations.append(error)
        try:
            verifier.write_artifacts("ERROR", error=error)
        except Exception:
            traceback.print_exc()
        traceback.print_exc()
        return 3


if __name__ == "__main__":
    sys.exit(main())

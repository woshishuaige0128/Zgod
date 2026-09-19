"""独立复算表3-1频率误差和表3-2多种MAC口径，并与MATLAB逐行比较。"""

from __future__ import annotations

import csv
import json
import math
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg
from scipy.io import loadmat
from scipy.io.matlab import MatReadWarning


TOL_FREQUENCY_HZ = 5e-10
TOL_ERROR_PERCENT = 5e-10
TOL_MAC = 5e-10
TOL_RESIDUAL = 5e-10


def find_board_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if parent.name == "板块19_表3-1至表3-3逐单元格计算复现":
            return parent
    raise RuntimeError("无法定位板块19根目录。")


def solve_modes(k_matrix: np.ndarray, m_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    eigenvalues, eigenvectors = linalg.eig(k_matrix, m_matrix)
    imaginary_ratio = np.max(
        np.abs(eigenvalues.imag) / np.maximum(np.abs(eigenvalues.real), np.finfo(float).eps)
    )
    if imaginary_ratio > 1e-10:
        raise ValueError(f"广义特征值虚部比例超限：{imaginary_ratio:.16g}")
    order = np.argsort(eigenvalues.real)
    eigenvalues = eigenvalues.real[order]
    eigenvectors = eigenvectors.real[:, order]
    if np.any(eigenvalues <= 0):
        raise ValueError("出现非正广义特征值。")
    eigenvectors /= np.linalg.norm(eigenvectors, axis=0, keepdims=True)
    frequencies = np.sqrt(eigenvalues) / (2 * np.pi)
    return eigenvectors, eigenvalues, frequencies


def generalized_residual(
    k_matrix: np.ndarray, m_matrix: np.ndarray, eigenvectors: np.ndarray, eigenvalues: np.ndarray
) -> float:
    numerator = np.linalg.norm(
        k_matrix @ eigenvectors - m_matrix @ eigenvectors @ np.diag(eigenvalues), ord="fro"
    )
    denominator = max(np.linalg.norm(k_matrix @ eigenvectors, ord="fro"), np.finfo(float).eps)
    return float(numerator / denominator)


def euclidean_mac(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    a = np.asarray(vector_a, dtype=float).reshape(-1)
    b = np.asarray(vector_b, dtype=float).reshape(-1)
    if a.shape != b.shape:
        raise ValueError(f"MAC维数不一致：{a.shape} vs {b.shape}")
    return float(abs(np.vdot(a, b)) ** 2 / (np.vdot(a, a).real * np.vdot(b, b).real))


def weighted_mac(vector_a: np.ndarray, vector_b: np.ndarray, weight: np.ndarray) -> float:
    a = np.asarray(vector_a, dtype=float).reshape(-1)
    b = np.asarray(vector_b, dtype=float).reshape(-1)
    numerator = abs(a.T @ weight @ b) ** 2
    denominator = (a.T @ weight @ a) * (b.T @ weight @ b)
    return float(numerator / denominator)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def as_float(value: str) -> float:
    return float(value) if value not in {"", "NaN", "nan"} else math.nan


def main() -> None:
    script_path = Path(__file__).resolve()
    board_root = find_board_root(script_path.parent)
    input_mat = board_root / "input" / "board17" / "outputs" / "global_routes_matlab.mat"
    matlab_dir = board_root / "outputs" / "modal_matlab"
    output_dir = board_root / "outputs" / "modal_python"
    output_dir.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MatReadWarning)
        source = loadmat(input_mat, simplify_cells=True)

    m_full = np.asarray(source["MRrt"], dtype=float)
    k_full = np.asarray(source["KRrt"], dtype=float)
    phi_full, lambda_full, frequency_full = solve_modes(k_full, m_full)
    full_residual = generalized_residual(k_full, m_full, phi_full, lambda_full)
    if full_residual > TOL_RESIDUAL:
        raise RuntimeError(f"完整模型特征残差超限：{full_residual:.16g}")

    paper_frequency = {
        (1, "Guyan", 1): 0.648,
        (1, "Guyan", 2): 5.411,
        (1, "Craig-Bampton", 1): 0.003,
        (1, "Craig-Bampton", 2): 0.284,
        (2, "Guyan", 1): 13.040,
        (2, "Guyan", 2): 24.575,
        (2, "Craig-Bampton", 1): 0.007,
        (2, "Craig-Bampton", 2): 0.834,
    }
    paper_mac = {
        (1, "Guyan", 1): 1.0000,
        (1, "Guyan", 2): 0.9998,
        (1, "Craig-Bampton", 1): 1.0000,
        (1, "Craig-Bampton", 2): 1.0000,
        (2, "Guyan", 1): 0.9962,
        (2, "Guyan", 2): 0.9255,
        (2, "Craig-Bampton", 1): 1.0000,
        (2, "Craig-Bampton", 2): 0.9998,
    }

    frequency_rows: list[dict[str, Any]] = []
    mac_rows: list[dict[str, Any]] = []
    residual_rows: list[dict[str, Any]] = []

    for division in (1, 2):
        division_data = source[f"division{division}"]
        master_one_based = np.asarray(division_data["master"], dtype=int).reshape(-1)
        master = master_one_based - 1
        n_master = int(division_data["n_master"])
        route_definitions = [
            (
                "Guyan",
                "historical_single_sided",
                division_data["K_historical"],
                division_data["M_historical"],
                division_data["R_guyan_natural"],
            ),
            (
                "Guyan",
                "projected_congruence",
                division_data["K_projected"],
                division_data["M_projected"],
                division_data["R_guyan_natural"],
            ),
            (
                "Craig-Bampton",
                "sorted_cb",
                division_data["K_cb"],
                division_data["M_cb"],
                division_data["R_cb_natural"],
            ),
            (
                "Craig-Bampton",
                "raw_cb",
                division_data["K_cb_raw"],
                division_data["M_cb_raw"],
                division_data["R_cb_raw_natural"],
            ),
        ]
        solved: dict[str, tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]] = {}
        for method, route, k_reduced, m_reduced, recovery in route_definitions:
            k_reduced = np.asarray(k_reduced, dtype=float)
            m_reduced = np.asarray(m_reduced, dtype=float)
            recovery = np.asarray(recovery, dtype=float)
            phi_reduced, lambda_reduced, frequency_reduced = solve_modes(k_reduced, m_reduced)
            residual = generalized_residual(k_reduced, m_reduced, phi_reduced, lambda_reduced)
            residual_rows.append(
                {
                    "division": division,
                    "method": method,
                    "route": route,
                    "relative_eigen_residual": residual,
                    "pass": residual <= TOL_RESIDUAL,
                }
            )
            solved[route] = (phi_reduced, lambda_reduced, frequency_reduced, recovery)
            for mode in (1, 2):
                relative_error = (
                    100
                    * abs(frequency_reduced[mode - 1] - frequency_full[mode - 1])
                    / frequency_full[mode - 1]
                )
                paper_value = paper_frequency[(division, method, mode)]
                rounded_value = float(np.round(relative_error, 3))
                frequency_rows.append(
                    {
                        "division": division,
                        "method": method,
                        "route": route,
                        "mode": mode,
                        "full_frequency_hz": frequency_full[mode - 1],
                        "reduced_frequency_hz": frequency_reduced[mode - 1],
                        "relative_error_percent": relative_error,
                        "paper_value_percent": paper_value,
                        "printed_decimals": 3,
                        "rounded_value": rounded_value,
                        "absolute_difference_percent": abs(relative_error - paper_value),
                        "rounded_match": abs(rounded_value - paper_value) <= 5e-12,
                    }
                )

        method_definitions = [
            ("Guyan", solved["historical_single_sided"]),
            ("Craig-Bampton", solved["sorted_cb"]),
        ]
        for method, (phi_reduced, _lambda, _frequency, recovery) in method_definitions:
            for mode in (1, 2):
                full_vector = phi_full[:, mode - 1]
                reduced_vector = phi_reduced[:, mode - 1]
                recovered_vector = recovery @ reduced_vector
                candidate_definitions = [
                    (
                        "boundary_correct_master",
                        n_master,
                        euclidean_mac(full_vector[master], reduced_vector[:n_master]),
                        "作者脚本意图：只比较正确顺序保留坐标",
                    ),
                    (
                        "full_recovery_euclidean",
                        15,
                        euclidean_mac(full_vector, recovered_vector),
                        "必要适配：恢复到完整15维后普通欧氏MAC",
                    ),
                    (
                        "full_recovery_mass_weighted",
                        15,
                        weighted_mac(full_vector, recovered_vector, m_full),
                        "候选：恢复到完整15维后以完整质量矩阵加权",
                    ),
                    (
                        "three_floor_euclidean",
                        3,
                        euclidean_mac(full_vector[[0, 5, 10]], recovered_vector[[0, 5, 10]]),
                        "候选：只比较三层水平位移",
                    ),
                    (
                        "first_two_boundary_euclidean",
                        min(2, n_master),
                        euclidean_mac(full_vector[master[:2]], reduced_vector[:2]),
                        "motai2.m候选：只比较前两个保留坐标",
                    ),
                ]
                if division == 1:
                    wrong_order = np.array([1, 11, 6, 4, 9, 14], dtype=int) - 1
                    candidate_definitions.append(
                        (
                            "script_literal_wrong_order",
                            6,
                            euclidean_mac(full_vector[wrong_order], reduced_vector[:n_master]),
                            "MAC.m字面顺序：交换自然自由度6与11",
                        )
                    )
                else:
                    candidate_definitions.append(
                        (
                            "script_literal_wrong_order",
                            6,
                            math.nan,
                            "FAIL_DIMENSION_AND_NMODES：脚本6坐标/6阶，第二类Guyan仅5维",
                        )
                    )

                paper_value = paper_mac[(division, method, mode)]
                for route, coordinate_dimension, value, interpretation in candidate_definitions:
                    rounded_value = math.nan if math.isnan(value) else float(np.round(value, 4))
                    rounded_match = (
                        False if math.isnan(value) else abs(rounded_value - paper_value) <= 5e-12
                    )
                    mac_rows.append(
                        {
                            "division": division,
                            "method": method,
                            "route": route,
                            "mode": mode,
                            "coordinate_dimension": coordinate_dimension,
                            "mac_value": value,
                            "paper_value": paper_value,
                            "printed_decimals": 4,
                            "rounded_value": rounded_value,
                            "absolute_difference": math.nan if math.isnan(value) else abs(value - paper_value),
                            "rounded_match": rounded_match,
                            "interpretation": interpretation,
                        }
                    )

    frequency_fields = [
        "division",
        "method",
        "route",
        "mode",
        "full_frequency_hz",
        "reduced_frequency_hz",
        "relative_error_percent",
        "paper_value_percent",
        "printed_decimals",
        "rounded_value",
        "absolute_difference_percent",
        "rounded_match",
    ]
    mac_fields = [
        "division",
        "method",
        "route",
        "mode",
        "coordinate_dimension",
        "mac_value",
        "paper_value",
        "printed_decimals",
        "rounded_value",
        "absolute_difference",
        "rounded_match",
        "interpretation",
    ]
    residual_fields = ["division", "method", "route", "relative_eigen_residual", "pass"]
    write_csv(output_dir / "frequency_candidates_python.csv", frequency_rows, frequency_fields)
    write_csv(output_dir / "mac_candidates_python.csv", mac_rows, mac_fields)
    write_csv(output_dir / "modal_eigen_residuals_python.csv", residual_rows, residual_fields)

    matlab_frequency = read_csv(matlab_dir / "frequency_candidates_matlab.csv")
    matlab_mac = read_csv(matlab_dir / "mac_candidates_matlab.csv")
    frequency_by_key = {
        (int(row["division"]), row["method"], row["route"], int(row["mode"])): row
        for row in frequency_rows
    }
    mac_by_key = {
        (int(row["division"]), row["method"], row["route"], int(row["mode"])): row
        for row in mac_rows
    }

    comparisons: list[dict[str, Any]] = []
    for row in matlab_frequency:
        key = (int(row["division"]), row["method"], row["route"], int(row["mode"]))
        python_row = frequency_by_key[key]
        frequency_difference = abs(
            as_float(row["reduced_frequency_hz"]) - float(python_row["reduced_frequency_hz"])
        )
        error_difference = abs(
            as_float(row["relative_error_percent"]) - float(python_row["relative_error_percent"])
        )
        comparisons.append(
            {
                "category": "frequency",
                "division": key[0],
                "method": key[1],
                "route": key[2],
                "mode": key[3],
                "matlab_value": as_float(row["relative_error_percent"]),
                "python_value": python_row["relative_error_percent"],
                "absolute_difference": error_difference,
                "auxiliary_difference": frequency_difference,
                "criterion": f"error<={TOL_ERROR_PERCENT};frequency_hz<={TOL_FREQUENCY_HZ}",
                "result": "PASS"
                if error_difference <= TOL_ERROR_PERCENT and frequency_difference <= TOL_FREQUENCY_HZ
                else "FAIL",
            }
        )
    for row in matlab_mac:
        key = (int(row["division"]), row["method"], row["route"], int(row["mode"]))
        python_row = mac_by_key[key]
        matlab_value = as_float(row["mac_value"])
        python_value = float(python_row["mac_value"])
        if math.isnan(matlab_value) and math.isnan(python_value):
            difference = 0.0
            passed = True
        else:
            difference = abs(matlab_value - python_value)
            passed = difference <= TOL_MAC
        comparisons.append(
            {
                "category": "mac",
                "division": key[0],
                "method": key[1],
                "route": key[2],
                "mode": key[3],
                "matlab_value": matlab_value,
                "python_value": python_value,
                "absolute_difference": difference,
                "auxiliary_difference": 0.0,
                "criterion": f"mac<={TOL_MAC}",
                "result": "PASS" if passed else "FAIL",
            }
        )

    comparison_fields = [
        "category",
        "division",
        "method",
        "route",
        "mode",
        "matlab_value",
        "python_value",
        "absolute_difference",
        "auxiliary_difference",
        "criterion",
        "result",
    ]
    write_csv(output_dir / "modal_cross_language_comparison.csv", comparisons, comparison_fields)

    table31_rows: list[dict[str, Any]] = []
    for row in frequency_rows:
        selected = (row["method"] == "Guyan" and row["route"] == "historical_single_sided") or (
            row["method"] == "Craig-Bampton" and row["route"] == "sorted_cb"
        )
        if not selected:
            continue
        key = (row["division"], row["method"], row["route"], row["mode"])
        comparison = next(
            item
            for item in comparisons
            if item["category"] == "frequency"
            and (item["division"], item["method"], item["route"], item["mode"]) == key
        )
        match = bool(row["rounded_match"]) and comparison["result"] == "PASS"
        table31_rows.append(
            {
                **row,
                "matlab_python_absolute_difference": comparison["absolute_difference"],
                "cross_language_pass": comparison["result"] == "PASS",
                "evidence_label": "计算级复现（当前冻结历史路线）" if match else "历史值/待决定",
                "formula": "100*abs(f_full-f_red)/f_full",
                "source_file": "input/board17/outputs/global_routes_matlab.mat",
            }
        )

    table32_rows: list[dict[str, Any]] = []
    for row in mac_rows:
        if row["route"] != "boundary_correct_master":
            continue
        key = (row["division"], row["method"], row["route"], row["mode"])
        comparison = next(
            item
            for item in comparisons
            if item["category"] == "mac"
            and (item["division"], item["method"], item["route"], item["mode"]) == key
        )
        match = bool(row["rounded_match"]) and comparison["result"] == "PASS"
        table32_rows.append(
            {
                **row,
                "matlab_python_absolute_difference": comparison["absolute_difference"],
                "cross_language_pass": comparison["result"] == "PASS",
                "evidence_label": "计算级复现（正确保留坐标历史口径）" if match else "历史值/待决定",
                "formula": "abs(phi_full.T@phi_red)^2/((phi_full.T@phi_full)*(phi_red.T@phi_red))",
                "source_file": "input/board17/outputs/global_routes_matlab.mat",
            }
        )

    table31_fields = frequency_fields + [
        "matlab_python_absolute_difference",
        "cross_language_pass",
        "evidence_label",
        "formula",
        "source_file",
    ]
    table32_fields = mac_fields + [
        "matlab_python_absolute_difference",
        "cross_language_pass",
        "evidence_label",
        "formula",
        "source_file",
    ]
    write_csv(output_dir / "table3_1_cell_adjudication.csv", table31_rows, table31_fields)
    write_csv(output_dir / "table3_2_cell_adjudication.csv", table32_rows, table32_fields)

    summary = {
        "full_model_first_two_frequency_hz": frequency_full[:2].tolist(),
        "full_model_relative_eigen_residual": full_residual,
        "maximum_python_reduced_eigen_residual": max(row["relative_eigen_residual"] for row in residual_rows),
        "comparison_rows": len(comparisons),
        "comparison_pass_count": sum(row["result"] == "PASS" for row in comparisons),
        "comparison_fail_count": sum(row["result"] != "PASS" for row in comparisons),
        "maximum_frequency_error_absolute_difference": max(
            row["absolute_difference"] for row in comparisons if row["category"] == "frequency"
        ),
        "maximum_frequency_hz_absolute_difference": max(
            row["auxiliary_difference"] for row in comparisons if row["category"] == "frequency"
        ),
        "maximum_mac_absolute_difference": max(
            row["absolute_difference"] for row in comparisons if row["category"] == "mac"
        ),
        "table3_1_cells": len(table31_rows),
        "table3_1_rounded_matches": sum(row["rounded_match"] for row in table31_rows),
        "table3_2_cells": len(table32_rows),
        "table3_2_rounded_matches": sum(row["rounded_match"] for row in table32_rows),
        "status": "PASS"
        if all(row["result"] == "PASS" for row in comparisons)
        and full_residual <= TOL_RESIDUAL
        and all(row["relative_eigen_residual"] <= TOL_RESIDUAL for row in residual_rows)
        else "FAIL",
    }
    (output_dir / "modal_cross_language_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["status"] != "PASS":
        raise SystemExit(1)


if __name__ == "__main__":
    main()

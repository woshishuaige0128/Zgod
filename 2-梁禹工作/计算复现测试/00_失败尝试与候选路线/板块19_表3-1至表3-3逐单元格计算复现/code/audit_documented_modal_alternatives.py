"""审计原工程明确写过的其他模态路线；禁止任意自由度组合或数值拟合。"""

from __future__ import annotations

import csv
import json
import warnings
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg
from scipy.io import loadmat
from scipy.io.matlab import MatReadWarning


TOL = 5e-10


def find_board_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if parent.name == "板块19_表3-1至表3-3逐单元格计算复现":
            return parent
    raise RuntimeError("无法定位板块19根目录。")


def solve_modes(k_matrix: np.ndarray, m_matrix: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    values, vectors = linalg.eig(k_matrix, m_matrix)
    ratio = np.max(np.abs(values.imag) / np.maximum(np.abs(values.real), np.finfo(float).eps))
    if ratio > 1e-10:
        raise ValueError(f"特征值虚部比例超限：{ratio:.16g}")
    order = np.argsort(values.real)
    values = values.real[order]
    vectors = vectors.real[:, order]
    vectors /= np.linalg.norm(vectors, axis=0, keepdims=True)
    return np.sqrt(values) / (2 * np.pi), vectors


def mac(vector_a: np.ndarray, vector_b: np.ndarray) -> float:
    a = np.asarray(vector_a, dtype=float).reshape(-1)
    b = np.asarray(vector_b, dtype=float).reshape(-1)
    return float(abs(a.T @ b) ** 2 / ((a.T @ a) * (b.T @ b)))


def recovery_to_natural(transform_ordered: np.ndarray, ordered_ids_one_based: np.ndarray) -> np.ndarray:
    ids = np.asarray(ordered_ids_one_based, dtype=int).reshape(-1) - 1
    recovery = np.zeros((len(ids), transform_ordered.shape[1]))
    recovery[ids, :] = transform_ordered
    return recovery


def reduce_global(
    m_full: np.ndarray, k_full: np.ndarray, master_one_based: list[int], include_cb: bool
) -> dict[str, dict[str, Any]]:
    master = np.asarray(master_one_based, dtype=int) - 1
    slave = np.asarray([index for index in range(m_full.shape[0]) if index not in set(master)], dtype=int)
    ordered = np.concatenate([master, slave])
    m_ordered = m_full[np.ix_(ordered, ordered)]
    k_ordered = k_full[np.ix_(ordered, ordered)]
    n_master = len(master)
    m_mm = m_ordered[:n_master, :n_master]
    m_ms = m_ordered[:n_master, n_master:]
    k_mm = k_ordered[:n_master, :n_master]
    k_ms = k_ordered[:n_master, n_master:]
    k_sm = k_ordered[n_master:, :n_master]
    k_ss = k_ordered[n_master:, n_master:]
    m_ss = m_ordered[n_master:, n_master:]
    static = -linalg.solve(k_ss, k_sm, assume_a="sym")
    transform_guyan = np.vstack([np.eye(n_master), static])
    m_guyan = m_mm + m_ms @ static
    k_guyan = k_mm + k_ms @ static
    routes: dict[str, dict[str, Any]] = {
        "Guyan": {
            "M": m_guyan,
            "K": k_guyan,
            "T_ordered": transform_guyan,
            "master": master,
            "ordered": ordered,
        }
    }
    if include_cb:
        fixed_values, fixed_vectors = linalg.eig(k_ss, m_ss)
        order = np.argsort(fixed_values.real)
        fixed_vectors = fixed_vectors.real[:, order[:3]]
        transform_cb = np.block(
            [
                [np.eye(n_master), np.zeros((n_master, 3))],
                [static, fixed_vectors],
            ]
        )
        routes["Craig-Bampton"] = {
            "M": transform_cb.T @ m_ordered @ transform_cb,
            "K": transform_cb.T @ k_ordered @ transform_cb,
            "T_ordered": transform_cb,
            "master": master,
            "ordered": ordered,
        }
    return routes


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    board_root = find_board_root(Path(__file__).resolve().parent)
    global_mat = board_root / "input" / "board17" / "outputs" / "global_routes_matlab.mat"
    local_mat = board_root / "input" / "board17" / "outputs" / "local_pd_reductions.mat"
    output_dir = board_root / "outputs" / "documented_alternatives"
    output_dir.mkdir(parents=True, exist_ok=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", MatReadWarning)
        global_data = loadmat(global_mat, simplify_cells=True)
        local_data = loadmat(local_mat, simplify_cells=True)

    m_full = np.asarray(global_data["MRrt"], dtype=float)
    k_full = np.asarray(global_data["KRrt"], dtype=float)
    full_frequency, full_modes = solve_modes(k_full, m_full)

    candidates: list[dict[str, Any]] = []
    for route, master_ids, include_cb, source_evidence in [
        (
            "phy_full_master_1_6_4_9_11",
            [1, 6, 4, 9, 11],
            False,
            "input/documented_alternatives/phy.m:39-54；源码仅有Guyan",
        ),
        (
            "energy_three_floor_master_1_6_11",
            [1, 6, 11],
            True,
            "input/documented_alternatives/PDmonicanshu_energy.m:190-235；CB固定界面模态r=3",
        ),
    ]:
        reduced_routes = reduce_global(m_full, k_full, master_ids, include_cb)
        for method, route_data in reduced_routes.items():
            frequency, modes = solve_modes(route_data["K"], route_data["M"])
            recovery = recovery_to_natural(route_data["T_ordered"], route_data["ordered"] + 1)
            candidates.append(
                {
                    "candidate_route": route,
                    "model_scope": "完整15自由度替代主自由度集合",
                    "admissible_model_scope": True,
                    "method": method,
                    "frequency": frequency,
                    "modes": modes,
                    "full_frequency": full_frequency,
                    "full_modes": full_modes,
                    "master": route_data["master"],
                    "recovery": recovery,
                    "source_evidence": source_evidence,
                    "local_frequency_reference_max_abs_hz": 0.0,
                }
            )

    for local_name, label, source_evidence in [
        (
            "pd2",
            "局部物理子结构PD2_6自由度",
            "input/documented_alternatives/PDmonicanshu2.m:123-165",
        ),
        (
            "pd3",
            "局部物理子结构PD3_9自由度",
            "input/documented_alternatives/PDmonicanshu3.m:124-166",
        ),
    ]:
        local = local_data[local_name]
        local_full_frequency, local_full_modes = solve_modes(local["KPrt"], local["MPrt"])
        master = np.asarray(local["index_master"], dtype=int).reshape(-1) - 1
        ordered = np.asarray(local["idx_all"], dtype=int).reshape(-1)
        for method, k_name, m_name, t_name, reference_name in [
            ("Guyan", "KRren", "MRren", "T", "guyan_frequency_hz"),
            ("Craig-Bampton", "KR_cb", "MR_cb", "T_cb", "cb_frequency_hz"),
        ]:
            frequency, modes = solve_modes(local[k_name], local[m_name])
            reference = np.asarray(local[reference_name], dtype=float).reshape(-1)
            reference_difference = float(np.max(np.abs(frequency - reference)))
            if reference_difference > TOL:
                raise RuntimeError(f"{local_name}/{method} 与冻结板块17频率不一致：{reference_difference}")
            recovery = recovery_to_natural(np.asarray(local[t_name], dtype=float), ordered)
            candidates.append(
                {
                    "candidate_route": f"{local_name}_local_physical",
                    "model_scope": label,
                    "admissible_model_scope": False,
                    "method": method,
                    "frequency": frequency,
                    "modes": modes,
                    "full_frequency": local_full_frequency,
                    "full_modes": local_full_modes,
                    "master": master,
                    "recovery": recovery,
                    "source_evidence": source_evidence,
                    "local_frequency_reference_max_abs_hz": reference_difference,
                }
            )

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
    for candidate in candidates:
        for mode in (1, 2):
            frequency_error = (
                100
                * abs(candidate["frequency"][mode - 1] - candidate["full_frequency"][mode - 1])
                / candidate["full_frequency"][mode - 1]
            )
            boundary_mac = mac(
                candidate["full_modes"][candidate["master"], mode - 1],
                candidate["modes"][: len(candidate["master"]), mode - 1],
            )
            recovered_mac = mac(
                candidate["full_modes"][:, mode - 1],
                candidate["recovery"] @ candidate["modes"][:, mode - 1],
            )
            for paper_division in (1, 2):
                target_frequency = paper_frequency[(paper_division, candidate["method"], mode)]
                rounded_frequency = float(np.round(frequency_error, 3))
                frequency_rows.append(
                    {
                        "candidate_route": candidate["candidate_route"],
                        "model_scope": candidate["model_scope"],
                        "admissible_model_scope": candidate["admissible_model_scope"],
                        "method": candidate["method"],
                        "mode": mode,
                        "paper_division_compared": paper_division,
                        "full_frequency_hz": candidate["full_frequency"][mode - 1],
                        "reduced_frequency_hz": candidate["frequency"][mode - 1],
                        "relative_error_percent": frequency_error,
                        "paper_value_percent": target_frequency,
                        "rounded_value": rounded_frequency,
                        "rounded_match": abs(rounded_frequency - target_frequency) <= 5e-12,
                        "absolute_difference_percent": abs(frequency_error - target_frequency),
                        "source_evidence": candidate["source_evidence"],
                        "local_frequency_reference_max_abs_hz": candidate[
                            "local_frequency_reference_max_abs_hz"
                        ],
                    }
                )
                for metric_route, value in [
                    ("boundary_correct_master", boundary_mac),
                    ("full_recovery_euclidean", recovered_mac),
                ]:
                    target_mac = paper_mac[(paper_division, candidate["method"], mode)]
                    rounded_mac = float(np.round(value, 4))
                    mac_rows.append(
                        {
                            "candidate_route": candidate["candidate_route"],
                            "model_scope": candidate["model_scope"],
                            "admissible_model_scope": candidate["admissible_model_scope"],
                            "method": candidate["method"],
                            "mode": mode,
                            "mac_route": metric_route,
                            "paper_division_compared": paper_division,
                            "mac_value": value,
                            "paper_value": target_mac,
                            "rounded_value": rounded_mac,
                            "rounded_match": abs(rounded_mac - target_mac) <= 5e-12,
                            "absolute_difference": abs(value - target_mac),
                            "source_evidence": candidate["source_evidence"],
                        }
                    )

    write_csv(output_dir / "documented_frequency_alternatives.csv", frequency_rows)
    write_csv(output_dir / "documented_mac_alternatives.csv", mac_rows)

    second_frequency_rows = [row for row in frequency_rows if row["paper_division_compared"] == 2]
    second_mac_rows = [row for row in mac_rows if row["paper_division_compared"] == 2]
    required_cells = {
        ("Guyan", 1),
        ("Guyan", 2),
        ("Craig-Bampton", 1),
        ("Craig-Bampton", 2),
    }
    complete_frequency_routes: list[str] = []
    for route in sorted({row["candidate_route"] for row in second_frequency_rows}):
        route_rows = [row for row in second_frequency_rows if row["candidate_route"] == route]
        present = {(row["method"], row["mode"]) for row in route_rows}
        if (
            present == required_cells
            and all(row["admissible_model_scope"] for row in route_rows)
            and all(row["rounded_match"] for row in route_rows)
        ):
            complete_frequency_routes.append(route)
    complete_mac_routes: list[str] = []
    for route in sorted({row["candidate_route"] for row in second_mac_rows}):
        for mac_route in sorted(
            {row["mac_route"] for row in second_mac_rows if row["candidate_route"] == route}
        ):
            route_rows = [
                row
                for row in second_mac_rows
                if row["candidate_route"] == route and row["mac_route"] == mac_route
            ]
            present = {(row["method"], row["mode"]) for row in route_rows}
            if (
                present == required_cells
                and all(row["admissible_model_scope"] for row in route_rows)
                and all(row["rounded_match"] for row in route_rows)
            ):
                complete_mac_routes.append(f"{route}/{mac_route}")
    summary = {
        "candidate_route_count": len({row["candidate_route"] for row in frequency_rows}),
        "frequency_comparison_rows": len(frequency_rows),
        "mac_comparison_rows": len(mac_rows),
        "second_division_frequency_rounded_matches": sum(row["rounded_match"] for row in second_frequency_rows),
        "second_division_mac_rounded_matches": sum(row["rounded_match"] for row in second_mac_rows),
        "second_division_complete_frequency_routes": complete_frequency_routes,
        "second_division_complete_mac_routes": complete_mac_routes,
        "second_division_complete_frequency_route_found": bool(complete_frequency_routes),
        "second_division_complete_mac_route_found": bool(complete_mac_routes),
        "maximum_local_frequency_reference_difference_hz": max(
            row["local_frequency_reference_max_abs_hz"] for row in frequency_rows
        ),
        "search_boundary": "仅源码明确写出的phy、能量三水平、PD2、PD3；未枚举任意自由度组合，未拟合参数",
        "status": "NO_COMPLETE_DOCUMENTED_ALTERNATIVE_MATCH"
        if not complete_frequency_routes and not complete_mac_routes
        else "COMPLETE_DOCUMENTED_ALTERNATIVE_REQUIRES_REVIEW",
    }
    (output_dir / "documented_alternatives_summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

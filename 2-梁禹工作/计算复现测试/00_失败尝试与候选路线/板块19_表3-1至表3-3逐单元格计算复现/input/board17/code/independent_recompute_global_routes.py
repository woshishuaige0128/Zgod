from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg
from scipy.io import loadmat, savemat


SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE_ROOT = SCRIPT_PATH.parents[1]
INPUT_ROOT = CANDIDATE_ROOT / "input"
OUTPUT_ROOT = CANDIDATE_ROOT / "outputs"
LOG_ROOT = CANDIDATE_ROOT / "logs"
REFERENCE_MAT = INPUT_ROOT / "upstream_u01" / "reference_model_matlab.mat"
LEGACY_ROOT = INPUT_ROOT / "legacy_audit"

OUTPUT_MAT = OUTPUT_ROOT / "independent_global_routes_python.mat"
OUTPUT_MATRIX_CSV = OUTPUT_ROOT / "independent_global_matrix_checks.csv"
OUTPUT_MODAL_CSV = OUTPUT_ROOT / "independent_global_modal_results.csv"
OUTPUT_SUMMARY = OUTPUT_ROOT / "independent_global_summary.json"
LOG_PATH = LOG_ROOT / "independent_global_recompute.log"

REFERENCE_MAT_SHA256 = (
    "7F9C7C6ACEEDA106304B943F280CCFFF06CBA9137059857A4D89CB06D5B0DAB3"
)
MATRIX_TOL = 5.0e-12
STATIC_TOL = 5.0e-12
FREQUENCY_TOL_HZ = 5.0e-10
SUBSPACE_ANGLE_TOL_RAD = 5.0e-8

PRELIMINARY_RUN_ATTEMPTS = [
    {
        "attempt": 1,
        "result": "运行失败，未进入验收",
        "cause": "通用相对误差函数对15x1载荷向量Mf错误指定Frobenius范数；确认Mf为向量后修正为按数组维数选择范数。",
    }
]

DIVISIONS = {
    1: {
        "master": [1, 6, 11, 4, 9, 14],
        "slave": [2, 3, 5, 7, 8, 10, 12, 13, 15],
        "force_mask": [1, 1, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "expected_guyan_dimension": 6,
        "expected_cb_dimension": 9,
    },
    2: {
        "master": [1, 11, 4, 9, 14],
        "slave": [6, 2, 3, 5, 7, 8, 10, 12, 13, 15],
        "force_mask": [1, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0, 0],
        "expected_guyan_dimension": 5,
        "expected_cb_dimension": 8,
    },
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_frobenius(actual: np.ndarray, reference: np.ndarray) -> float:
    actual_array = np.asarray(actual)
    reference_array = np.asarray(reference)
    norm_order = "fro" if reference_array.ndim == 2 else None
    denominator = float(np.linalg.norm(reference_array, ord=norm_order))
    if denominator == 0.0:
        return float(np.linalg.norm(actual_array - reference_array, ord=norm_order))
    return float(
        np.linalg.norm(actual_array - reference_array, ord=norm_order) / denominator
    )


def symmetry_residual(matrix: np.ndarray) -> float:
    denominator = float(np.linalg.norm(matrix, ord="fro"))
    if denominator == 0.0:
        return 0.0
    return float(np.linalg.norm(matrix - matrix.T, ord="fro") / denominator)


def natural_frequencies(mass: np.ndarray, stiffness: np.ndarray) -> np.ndarray:
    eigenvalues = linalg.eigvals(stiffness, mass)
    if np.max(np.abs(eigenvalues.imag)) > 1.0e-7:
        raise RuntimeError(
            f"广义特征值出现不可忽略虚部: {np.max(np.abs(eigenvalues.imag)):.17g}"
        )
    values = np.sort(eigenvalues.real)
    if values[0] <= 0.0:
        raise RuntimeError(f"广义特征值非正: min={values[0]:.17g}")
    return np.sqrt(values) / (2.0 * np.pi)


def canonical_fixed_interface_modes(
    stiffness: np.ndarray, mass: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    eigenvalues, eigenvectors = linalg.eig(stiffness, mass)
    if np.max(np.abs(eigenvalues.imag)) > 1.0e-7:
        raise RuntimeError("固定界面特征值出现不可忽略虚部")
    order = np.argsort(eigenvalues.real)
    eigenvalues = eigenvalues.real[order]
    eigenvectors = eigenvectors.real[:, order]
    if eigenvalues[0] <= 0.0:
        raise RuntimeError("固定界面特征值非正")
    for column in range(eigenvectors.shape[1]):
        norm = float(np.linalg.norm(eigenvectors[:, column]))
        if norm == 0.0:
            raise RuntimeError("固定界面特征向量范数为零")
        eigenvectors[:, column] /= norm
        pivot = int(np.argmax(np.abs(eigenvectors[:, column])))
        if eigenvectors[pivot, column] < 0.0:
            eigenvectors[:, column] *= -1.0
    return eigenvalues, eigenvectors


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"拒绝写空 CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_division(
    mass: np.ndarray,
    damping: np.ndarray,
    stiffness: np.ndarray,
    division: int,
) -> dict[str, Any]:
    definition = DIVISIONS[division]
    master_1 = np.asarray(definition["master"], dtype=int)
    slave_1 = np.asarray(definition["slave"], dtype=int)
    order_1 = np.concatenate([master_1, slave_1])
    if sorted(order_1.tolist()) != list(range(1, 16)) or len(np.unique(order_1)) != 15:
        raise RuntimeError(f"第{division}类主从自由度不是1:15的无重复分割")

    order = order_1 - 1
    master_count = master_1.size
    mass_ordered = mass[np.ix_(order, order)]
    damping_ordered = damping[np.ix_(order, order)]
    stiffness_ordered = stiffness[np.ix_(order, order)]

    m_mm = mass_ordered[:master_count, :master_count]
    m_ms = mass_ordered[:master_count, master_count:]
    c_mm = damping_ordered[:master_count, :master_count]
    c_ms = damping_ordered[:master_count, master_count:]
    k_mm = stiffness_ordered[:master_count, :master_count]
    k_ms = stiffness_ordered[:master_count, master_count:]
    k_sm = stiffness_ordered[master_count:, :master_count]
    k_ss = stiffness_ordered[master_count:, master_count:]
    m_ss = mass_ordered[master_count:, master_count:]

    static_relation = -linalg.solve(k_ss, k_sm, assume_a="sym")
    transform = np.vstack([np.eye(master_count), static_relation])
    historical_mass = m_mm + m_ms @ static_relation
    historical_damping = c_mm + c_ms @ static_relation
    historical_stiffness = k_mm + k_ms @ static_relation
    projected_mass = transform.T @ mass_ordered @ transform
    projected_damping = transform.T @ damping_ordered @ transform
    projected_stiffness = transform.T @ stiffness_ordered @ transform

    fixed_eigenvalues, fixed_modes = canonical_fixed_interface_modes(k_ss, m_ss)
    retained_modes = 3
    cb_transform = np.block(
        [
            [np.eye(master_count), np.zeros((master_count, retained_modes))],
            [static_relation, fixed_modes[:, :retained_modes]],
        ]
    )
    cb_mass = cb_transform.T @ mass_ordered @ cb_transform
    cb_damping = cb_transform.T @ damping_ordered @ cb_transform
    cb_stiffness = cb_transform.T @ stiffness_ordered @ cb_transform

    permutation = np.eye(15)[order, :]
    natural_recovery_guyan = permutation.T @ transform
    natural_recovery_cb = permutation.T @ cb_transform
    floor_selector = np.eye(15)[np.asarray([1, 6, 11]) - 1, :]
    floor_rows_ordered = np.asarray(
        [int(np.flatnonzero(order_1 == floor)[0]) for floor in [1, 6, 11]], dtype=int
    )
    ordered_floor_selector = np.eye(15)[floor_rows_ordered, :]
    floor_recovery_guyan_from_ordered = ordered_floor_selector @ transform
    floor_recovery_cb_from_ordered = ordered_floor_selector @ cb_transform
    floor_recovery_guyan_from_natural = floor_selector @ natural_recovery_guyan
    floor_recovery_cb_from_natural = floor_selector @ natural_recovery_cb

    force_mask = np.asarray(definition["force_mask"], dtype=float)
    mf = force_mask * np.diag(mass_ordered)
    force_projection_guyan = transform.T @ mf
    force_projection_cb = cb_transform.T @ mf

    return {
        "division": division,
        "master": master_1,
        "slave": slave_1,
        "order": order_1,
        "force_mask": force_mask,
        "Mo": mass_ordered,
        "Co": damping_ordered,
        "Ko": stiffness_ordered,
        "Ksm": k_sm,
        "Kss": k_ss,
        "Mss": m_ss,
        "static_relation": static_relation,
        "T": transform,
        "M_historical": historical_mass,
        "C_historical": historical_damping,
        "K_historical": historical_stiffness,
        "M_projected": projected_mass,
        "C_projected": projected_damping,
        "K_projected": projected_stiffness,
        "fixed_interface_eigenvalues": fixed_eigenvalues,
        "fixed_interface_frequencies_hz": np.sqrt(fixed_eigenvalues) / (2.0 * np.pi),
        "fixed_interface_modes": fixed_modes,
        "retained_fixed_interface_modes": retained_modes,
        "T_cb": cb_transform,
        "M_cb": cb_mass,
        "C_cb": cb_damping,
        "K_cb": cb_stiffness,
        "permutation_order_from_natural": permutation,
        "natural_recovery_guyan": natural_recovery_guyan,
        "natural_recovery_cb": natural_recovery_cb,
        "floor_selector_natural": floor_selector,
        "floor_rows_ordered": floor_rows_ordered + 1,
        "floor_recovery_guyan_ordered": floor_recovery_guyan_from_ordered,
        "floor_recovery_cb_ordered": floor_recovery_cb_from_ordered,
        "floor_recovery_guyan_natural": floor_recovery_guyan_from_natural,
        "floor_recovery_cb_natural": floor_recovery_cb_from_natural,
        "Mf": mf,
        "force_projection_guyan": force_projection_guyan,
        "force_projection_cb": force_projection_cb,
    }


def compare_legacy_bundle(
    computed: dict[str, Any], legacy_path: Path
) -> tuple[dict[str, float], dict[str, Any]]:
    legacy = loadmat(legacy_path, simplify_cells=True)["matrixBundle"]
    comparisons: dict[str, float] = {}
    for field in [
        "Mo",
        "Co",
        "Ko",
        "T",
        "M_historical",
        "C_historical",
        "K_historical",
        "M_projected",
        "C_projected",
        "K_projected",
        "Mf",
    ]:
        comparisons[field] = relative_frobenius(
            np.asarray(computed[field]), np.asarray(legacy[field])
        )

    master_count = int(np.asarray(computed["master"]).size)
    computed_modes = np.asarray(computed["T_cb"])[master_count:, master_count:]
    legacy_modes = np.asarray(legacy["T_cb"])[master_count:, master_count:]
    maximum_angle = float(
        np.max(linalg.subspace_angles(computed_modes, legacy_modes))
    )
    comparisons["T_cb_fixed_interface_subspace_max_angle_rad"] = maximum_angle

    cb_frequency_computed = natural_frequencies(
        np.asarray(computed["M_cb"]), np.asarray(computed["K_cb"])
    )
    cb_frequency_legacy = natural_frequencies(
        np.asarray(legacy["M_cb"]), np.asarray(legacy["K_cb"])
    )
    comparisons["CB_frequency_max_abs_hz"] = float(
        np.max(np.abs(cb_frequency_computed - cb_frequency_legacy))
    )
    metadata = {
        "legacy_master": np.asarray(legacy["master"]).reshape(-1).astype(int).tolist(),
        "legacy_slave": np.asarray(legacy["slave"]).reshape(-1).astype(int).tolist(),
        "legacy_order": np.asarray(legacy["order"]).reshape(-1).astype(int).tolist(),
        "legacy_path": str(legacy_path),
    }
    return comparisons, metadata


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)
    reference_hash = sha256(REFERENCE_MAT)
    if reference_hash != REFERENCE_MAT_SHA256:
        raise RuntimeError(
            f"上游MAT哈希变化: {reference_hash} != {REFERENCE_MAT_SHA256}"
        )

    source = loadmat(
        REFERENCE_MAT,
        variable_names=["MRrt", "CRrt", "KRrt"],
        squeeze_me=False,
    )
    mass = np.asarray(source["MRrt"], dtype=float)
    damping = np.asarray(source["CRrt"], dtype=float)
    stiffness = np.asarray(source["KRrt"], dtype=float)
    if mass.shape != (15, 15) or damping.shape != (15, 15) or stiffness.shape != (15, 15):
        raise RuntimeError(
            f"完整模型矩阵维数错误: M{mass.shape}, C{damping.shape}, K{stiffness.shape}"
        )

    full_frequencies = natural_frequencies(mass, stiffness)
    computed = {
        division: build_division(mass, damping, stiffness, division)
        for division in sorted(DIVISIONS)
    }
    legacy_matrix_rows = {
        int(row["division"]): row
        for row in read_csv(LEGACY_ROOT / "guyan_matrix_audit.csv")
    }
    legacy_modal_rows = read_csv(LEGACY_ROOT / "guyan_modal_comparison.csv")

    checks: list[dict[str, Any]] = []
    modal_rows: list[dict[str, Any]] = []
    failures: list[str] = []
    legacy_comparisons: dict[str, Any] = {}

    def record(
        division: int,
        check: str,
        actual: float | int | str,
        criterion: str,
        passed: bool,
    ) -> None:
        checks.append(
            {
                "division": division,
                "check": check,
                "actual": actual,
                "criterion": criterion,
                "result": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            failures.append(f"division_{division}|{check}|actual={actual}|{criterion}")

    for division, result in computed.items():
        definition = DIVISIONS[division]
        master_count = len(definition["master"])
        slave_count = len(definition["slave"])
        expected_cb = int(definition["expected_cb_dimension"])
        legacy_path = LEGACY_ROOT / f"division_{division}_guyan_matrices.mat"
        comparison, metadata = compare_legacy_bundle(result, legacy_path)
        legacy_comparisons[str(division)] = {
            "matrix_comparison": comparison,
            "metadata": metadata,
        }

        record(
            division,
            "主从自由度为1:15无重复分割",
            len(np.unique(result["order"])),
            "unique=15 and sorted=1:15",
            len(np.unique(result["order"])) == 15
            and sorted(result["order"].tolist()) == list(range(1, 16)),
        )
        record(
            division,
            "Guyan变换维数",
            f"{result['T'].shape[0]}x{result['T'].shape[1]}",
            f"15x{master_count}",
            result["T"].shape == (15, master_count),
        )
        record(
            division,
            "Guyan变换满列秩",
            int(np.linalg.matrix_rank(result["T"])),
            f"rank={master_count}",
            int(np.linalg.matrix_rank(result["T"])) == master_count,
        )
        record(
            division,
            "Craig-Bampton变换维数",
            f"{result['T_cb'].shape[0]}x{result['T_cb'].shape[1]}",
            f"15x{expected_cb}",
            result["T_cb"].shape == (15, expected_cb),
        )
        static_residual = float(
            np.linalg.norm(
                result["Ksm"] + result["Kss"] @ result["static_relation"],
                ord="fro",
            )
            / np.linalg.norm(result["Ksm"], ord="fro")
        )
        record(
            division,
            "静力约束残差",
            static_residual,
            f"<={STATIC_TOL}",
            static_residual <= STATIC_TOL,
        )
        floor_guyan_error = float(
            np.max(
                np.abs(
                    result["floor_recovery_guyan_ordered"]
                    - result["floor_recovery_guyan_natural"]
                )
            )
        )
        floor_cb_error = float(
            np.max(
                np.abs(
                    result["floor_recovery_cb_ordered"]
                    - result["floor_recovery_cb_natural"]
                )
            )
        )
        record(
            division,
            "三层Guyan自然/重排恢复一致",
            floor_guyan_error,
            f"<={MATRIX_TOL}",
            floor_guyan_error <= MATRIX_TOL,
        )
        record(
            division,
            "三层CB自然/重排恢复一致",
            floor_cb_error,
            f"<={MATRIX_TOL}",
            floor_cb_error <= MATRIX_TOL,
        )
        record(
            division,
            "Guyan载荷投影维数",
            int(result["force_projection_guyan"].size),
            f"={master_count}",
            int(result["force_projection_guyan"].size) == master_count,
        )
        record(
            division,
            "CB载荷投影维数",
            int(result["force_projection_cb"].size),
            f"={expected_cb}",
            int(result["force_projection_cb"].size) == expected_cb,
        )

        for field, value in comparison.items():
            tolerance = (
                SUBSPACE_ANGLE_TOL_RAD
                if field == "T_cb_fixed_interface_subspace_max_angle_rad"
                else FREQUENCY_TOL_HZ
                if field == "CB_frequency_max_abs_hz"
                else MATRIX_TOL
            )
            record(
                division,
                f"冻结板块14交叉验证_{field}",
                value,
                f"<={tolerance}",
                value <= tolerance,
            )

        legacy_matrix = legacy_matrix_rows[division]
        current_metrics = {
            "static_residual": static_residual,
            "relative_M": relative_frobenius(
                result["M_historical"], result["M_projected"]
            ),
            "relative_C": relative_frobenius(
                result["C_historical"], result["C_projected"]
            ),
            "relative_K": relative_frobenius(
                result["K_historical"], result["K_projected"]
            ),
        }
        for field, actual in current_metrics.items():
            expected = float(legacy_matrix[field])
            error = abs(actual - expected)
            record(
                division,
                f"冻结板块14数值回归_{field}",
                error,
                f"abs_error<={MATRIX_TOL}",
                error <= MATRIX_TOL,
            )

        route_frequencies = {
            ("Original", "route_invariant"): full_frequencies,
            ("Guyan", "historical_single_sided"): natural_frequencies(
                result["M_historical"], result["K_historical"]
            ),
            ("Guyan", "projected_congruence"): natural_frequencies(
                result["M_projected"], result["K_projected"]
            ),
            ("Craig-Bampton", "route_invariant"): natural_frequencies(
                result["M_cb"], result["K_cb"]
            ),
        }
        for (model, route), frequencies in route_frequencies.items():
            for mode in (1, 2):
                frequency = float(frequencies[mode - 1])
                relative_error = 100.0 * abs(
                    frequency - full_frequencies[mode - 1]
                ) / full_frequencies[mode - 1]
                modal_rows.append(
                    {
                        "division": division,
                        "model": model,
                        "route": route,
                        "mode": mode,
                        "full_frequency_hz": float(full_frequencies[mode - 1]),
                        "frequency_hz": frequency,
                        "relative_frequency_error_percent": float(relative_error),
                    }
                )
                matches = [
                    row
                    for row in legacy_modal_rows
                    if int(row["division"]) == division
                    and row["model"] == model
                    and row["route"] == route
                    and int(row["mode"]) == mode
                ]
                if len(matches) != 1:
                    record(
                        division,
                        f"冻结板块14模态行唯一_{model}_{route}_mode{mode}",
                        len(matches),
                        "=1",
                        False,
                    )
                else:
                    frequency_error = abs(
                        frequency - float(matches[0]["frequency_hz"])
                    )
                    record(
                        division,
                        f"冻结板块14频率回归_{model}_{route}_mode{mode}",
                        frequency_error,
                        f"<={FREQUENCY_TOL_HZ} Hz",
                        frequency_error <= FREQUENCY_TOL_HZ,
                    )

    save_payload: dict[str, Any] = {
        "MRrt": mass,
        "CRrt": damping,
        "KRrt": stiffness,
        "full_frequencies_hz": full_frequencies,
        "division1": computed[1],
        "division2": computed[2],
    }
    savemat(OUTPUT_MAT, save_payload, do_compression=True, long_field_names=True)
    write_csv(OUTPUT_MATRIX_CSV, checks)
    write_csv(OUTPUT_MODAL_CSV, modal_rows)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "route": "独立Python公式重建，不调用MATLAB缩聚代码",
        "reference_mat": str(REFERENCE_MAT),
        "reference_mat_sha256": reference_hash,
        "matrix_tolerance": MATRIX_TOL,
        "static_tolerance": STATIC_TOL,
        "frequency_tolerance_hz": FREQUENCY_TOL_HZ,
        "subspace_angle_tolerance_rad": SUBSPACE_ANGLE_TOL_RAD,
        "check_count": len(checks),
        "pass_count": sum(row["result"] == "PASS" for row in checks),
        "failure_count": len(failures),
        "failures": failures,
        "division_dimensions": {
            str(division): {
                "guyan": list(computed[division]["T"].shape),
                "craig_bampton": list(computed[division]["T_cb"].shape),
                "retained_fixed_interface_modes": int(
                    computed[division]["retained_fixed_interface_modes"]
                ),
            }
            for division in computed
        },
        "historical_vs_projected_relative_differences": {
            str(division): {
                "mass": relative_frobenius(
                    computed[division]["M_historical"],
                    computed[division]["M_projected"],
                ),
                "damping": relative_frobenius(
                    computed[division]["C_historical"],
                    computed[division]["C_projected"],
                ),
                "stiffness": relative_frobenius(
                    computed[division]["K_historical"],
                    computed[division]["K_projected"],
                ),
            }
            for division in computed
        },
        "legacy_cross_checks": legacy_comparisons,
        "preliminary_run_attempts": PRELIMINARY_RUN_ATTEMPTS,
        "output_mat": str(OUTPUT_MAT),
        "pass": len(failures) == 0,
    }
    OUTPUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    LOG_PATH.write_text(
        "\n".join(
            [
                "板块17完整15自由度全局缩聚独立Python重算",
                f"生成时间(UTC): {summary['generated_at_utc']}",
                f"上游MAT SHA-256: {reference_hash}",
                f"检查数: {len(checks)}",
                f"通过数: {summary['pass_count']}",
                f"失败数: {len(failures)}",
                f"结论: {'PASS' if summary['pass'] else 'FAIL'}",
                "前置运行失败记录：",
                *[
                    f"- 第{item['attempt']}次：{item['result']}；原因：{item['cause']}"
                    for item in PRELIMINARY_RUN_ATTEMPTS
                ],
                *[f"- {item}" for item in failures],
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

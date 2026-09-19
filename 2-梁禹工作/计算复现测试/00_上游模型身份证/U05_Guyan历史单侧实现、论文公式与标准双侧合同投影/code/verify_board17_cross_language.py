from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from scipy import linalg
from scipy.io import loadmat


SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE_ROOT = SCRIPT_PATH.parents[1]
OUTPUT_ROOT = CANDIDATE_ROOT / "outputs"
LOG_ROOT = CANDIDATE_ROOT / "logs"

MATLAB_MAT = OUTPUT_ROOT / "global_routes_matlab.mat"
PYTHON_MAT = OUTPUT_ROOT / "independent_global_routes_python.mat"
MATLAB_SUMMARY = OUTPUT_ROOT / "global_route_summary.json"
MATLAB_HASHES = OUTPUT_ROOT / "global_output_hashes.csv"
ORIGINAL_COMPARISON_CSV = OUTPUT_ROOT / "global_original_script_comparison.csv"

OUTPUT_CHECKS = OUTPUT_ROOT / "cross_language_matrix_checks.csv"
OUTPUT_MODAL = OUTPUT_ROOT / "cross_language_modal_comparison.csv"
OUTPUT_SUMMARY = OUTPUT_ROOT / "cross_language_summary.json"
LOG_PATH = LOG_ROOT / "cross_language_verification.log"

MATRIX_TOL = 5.0e-12
FREQUENCY_TOL_HZ = 5.0e-10
SUBSPACE_ANGLE_TOL_RAD = 5.0e-8

PRELIMINARY_RUN_ATTEMPTS = [
    {
        "attempt": 1,
        "result": "78/82通过，未通过最终验收",
        "cause": "SciPy将MATLAB string对象读取为MCOS元数据，4个原脚本状态文本不可解析；矩阵、子空间、频率和布尔/哈希字段均未失败。改从同步输出的纯文本CSV读取状态。",
    }
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_error(actual: Any, reference: Any) -> float:
    actual_array = np.asarray(actual, dtype=float)
    reference_array = np.asarray(reference, dtype=float)
    if actual_array.shape != reference_array.shape:
        return float("inf")
    norm_order = "fro" if reference_array.ndim == 2 else None
    denominator = float(np.linalg.norm(reference_array, ord=norm_order))
    difference = float(
        np.linalg.norm(actual_array - reference_array, ord=norm_order)
    )
    return difference if denominator == 0.0 else difference / denominator


def natural_frequencies(mass: Any, stiffness: Any) -> np.ndarray:
    eigenvalues = linalg.eigvals(
        np.asarray(stiffness, dtype=float), np.asarray(mass, dtype=float)
    )
    if np.max(np.abs(eigenvalues.imag)) > 1.0e-7:
        raise RuntimeError("跨语言比较中的广义特征值出现不可忽略虚部")
    values = np.sort(eigenvalues.real)
    if values[0] <= 0.0:
        raise RuntimeError("跨语言比较中的广义特征值非正")
    return np.sqrt(values) / (2.0 * np.pi)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"拒绝写空CSV: {path}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def verify_hash_table(path: Path) -> tuple[int, list[str]]:
    problems: list[str] = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        raw_path = row.get("path", row.get("file", row.get("relative_path", "")))
        expected = row.get("sha256", row.get("SHA256", ""))
        if not raw_path or not expected:
            problems.append(f"HASH_TABLE_SCHEMA|{row}")
            continue
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = CANDIDATE_ROOT / candidate
        candidate = candidate.resolve()
        if not candidate.is_file():
            problems.append(f"HASH_TARGET_MISSING|{candidate}")
            continue
        actual = sha256(candidate)
        if actual != expected.upper():
            problems.append(f"HASH_MISMATCH|{candidate}|{actual}|{expected}")
    return len(rows), problems


def scalar_bool(value: Any) -> bool:
    array = np.asarray(value).reshape(-1)
    if array.size != 1:
        raise RuntimeError(f"期望标量布尔量，实际尺寸={array.shape}")
    return bool(array[0])


def scalar_text(value: Any) -> str:
    if isinstance(value, str):
        return value
    array = np.asarray(value).reshape(-1)
    if array.size == 0:
        return ""
    return str(array[0])


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    LOG_ROOT.mkdir(parents=True, exist_ok=True)

    matlab = loadmat(
        MATLAB_MAT,
        variable_names=[
            "MRrt",
            "CRrt",
            "KRrt",
            "full_frequency_hz",
            "division1",
            "division2",
            "original1",
            "original2",
            "directOriginal1",
            "directOriginal2",
        ],
        simplify_cells=True,
    )
    python = loadmat(
        PYTHON_MAT,
        variable_names=[
            "MRrt",
            "CRrt",
            "KRrt",
            "full_frequencies_hz",
            "division1",
            "division2",
        ],
        simplify_cells=True,
    )
    matlab_summary = json.loads(MATLAB_SUMMARY.read_text(encoding="utf-8"))
    with ORIGINAL_COMPARISON_CSV.open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        original_comparison_rows = {
            int(row["division"]): row for row in csv.DictReader(handle)
        }

    checks: list[dict[str, Any]] = []
    modal_rows: list[dict[str, Any]] = []
    failures: list[str] = []

    def record(
        division: int | str,
        category: str,
        check: str,
        actual: Any,
        criterion: str,
        passed: bool,
    ) -> None:
        checks.append(
            {
                "division": division,
                "category": category,
                "check": check,
                "actual": actual,
                "criterion": criterion,
                "result": "PASS" if passed else "FAIL",
            }
        )
        if not passed:
            failures.append(f"{division}|{category}|{check}|actual={actual}|{criterion}")

    for field in ("MRrt", "CRrt", "KRrt"):
        error = relative_error(matlab[field], python[field])
        record(
            "global",
            "完整模型",
            f"MATLAB_vs_Python_{field}",
            error,
            f"relative_error<={MATRIX_TOL}",
            error <= MATRIX_TOL,
        )
    full_frequency_error = float(
        np.max(
            np.abs(
                np.asarray(matlab["full_frequency_hz"]).reshape(-1)
                - np.asarray(python["full_frequencies_hz"]).reshape(-1)
            )
        )
    )
    record(
        "global",
        "完整模型",
        "15阶频率最大绝对差",
        full_frequency_error,
        f"<={FREQUENCY_TOL_HZ} Hz",
        full_frequency_error <= FREQUENCY_TOL_HZ,
    )

    direct_fields = [
        "Mo",
        "Co",
        "Ko",
        "Ksm",
        "Kss",
        "Mss",
        "static_relation",
        "T",
        "M_historical",
        "C_historical",
        "K_historical",
        "M_projected",
        "C_projected",
        "K_projected",
        "Mf",
        "R_guyan_natural",
        "floor_recovery_guyan",
        "input_guyan",
    ]
    python_alias = {
        "R_guyan_natural": "natural_recovery_guyan",
        "floor_recovery_guyan": "floor_recovery_guyan_ordered",
        "input_guyan": "force_projection_guyan",
    }

    maximum_direct_error = 0.0
    maximum_cb_aligned_error = 0.0
    maximum_subspace_angle = 0.0
    maximum_modal_frequency_error = 0.0

    for division in (1, 2):
        m = matlab[f"division{division}"]
        p = python[f"division{division}"]
        original = matlab[f"original{division}"]
        direct_original = matlab[f"directOriginal{division}"]
        original_comparison = original_comparison_rows[division]
        master = np.asarray(m["master"]).reshape(-1).astype(int)
        slave = np.asarray(m["slave"]).reshape(-1).astype(int)
        order = np.asarray(m["order"]).reshape(-1).astype(int)
        p_master = np.asarray(p["master"]).reshape(-1).astype(int)
        p_slave = np.asarray(p["slave"]).reshape(-1).astype(int)
        p_order = np.asarray(p["order"]).reshape(-1).astype(int)
        master_count = master.size
        retained = int(np.asarray(m["r"]).reshape(-1)[0])

        for label, actual, reference in (
            ("master", master, p_master),
            ("slave", slave, p_slave),
            ("order", order, p_order),
        ):
            passed = np.array_equal(actual, reference)
            record(
                division,
                "自由度契约",
                f"MATLAB_vs_Python_{label}",
                actual.tolist(),
                f"={reference.tolist()}",
                passed,
            )

        for matlab_field in direct_fields:
            python_field = python_alias.get(matlab_field, matlab_field)
            error = relative_error(m[matlab_field], p[python_field])
            maximum_direct_error = max(maximum_direct_error, error)
            record(
                division,
                "逐矩阵",
                f"MATLAB_vs_Python_{matlab_field}",
                error,
                f"relative_error<={MATRIX_TOL}",
                error <= MATRIX_TOL,
            )

        m_tcb = np.asarray(m["T_cb"], dtype=float)
        p_tcb = np.asarray(p["T_cb"], dtype=float)
        m_modes = m_tcb[master_count:, master_count:]
        p_modes = p_tcb[master_count:, master_count:]
        angles = linalg.subspace_angles(m_modes, p_modes)
        max_angle = float(np.max(angles))
        maximum_subspace_angle = max(maximum_subspace_angle, max_angle)
        record(
            division,
            "Craig-Bampton",
            "固定界面保留3模态子空间最大夹角",
            max_angle,
            f"<={SUBSPACE_ANGLE_TOL_RAD} rad",
            retained == 3 and max_angle <= SUBSPACE_ANGLE_TOL_RAD,
        )

        scales: list[float] = []
        for mode in range(retained):
            p_column = p_tcb[:, master_count + mode]
            m_column = m_tcb[:, master_count + mode]
            scale = float(np.dot(p_column, m_column) / np.dot(p_column, p_column))
            scales.append(scale)
        coordinate = np.diag(np.asarray([1.0] * master_count + scales))
        aligned_transform = p_tcb @ coordinate
        transform_error = relative_error(m_tcb, aligned_transform)
        record(
            division,
            "Craig-Bampton",
            "列缩放对齐后的T_cb",
            transform_error,
            f"relative_error<={MATRIX_TOL}",
            transform_error <= MATRIX_TOL,
        )

        for prefix in ("M", "C", "K"):
            aligned = coordinate.T @ np.asarray(p[f"{prefix}_cb"]) @ coordinate
            error = relative_error(m[f"{prefix}_cb"], aligned)
            maximum_cb_aligned_error = max(maximum_cb_aligned_error, error)
            record(
                division,
                "Craig-Bampton",
                f"列缩放对齐后的{prefix}_cb",
                error,
                f"relative_error<={MATRIX_TOL}",
                error <= MATRIX_TOL,
            )

        aligned_recovery = np.asarray(p["natural_recovery_cb"]) @ coordinate
        recovery_error = relative_error(m["R_cb_natural"], aligned_recovery)
        record(
            division,
            "恢复接口",
            "列缩放对齐后的自然坐标CB恢复矩阵",
            recovery_error,
            f"relative_error<={MATRIX_TOL}",
            recovery_error <= MATRIX_TOL,
        )
        aligned_floor = np.asarray(p["floor_recovery_cb_ordered"]) @ coordinate
        floor_error = relative_error(m["floor_recovery_cb"], aligned_floor)
        record(
            division,
            "恢复接口",
            "列缩放对齐后的三层CB恢复矩阵",
            floor_error,
            f"relative_error<={MATRIX_TOL}",
            floor_error <= MATRIX_TOL,
        )

        matlab_route_frequencies = {
            "historical_guyan": natural_frequencies(
                m["M_historical"], m["K_historical"]
            ),
            "projected_guyan": natural_frequencies(
                m["M_projected"], m["K_projected"]
            ),
            "sorted_cb": natural_frequencies(m["M_cb"], m["K_cb"]),
        }
        python_route_frequencies = {
            "historical_guyan": natural_frequencies(
                p["M_historical"], p["K_historical"]
            ),
            "projected_guyan": natural_frequencies(
                p["M_projected"], p["K_projected"]
            ),
            "sorted_cb": natural_frequencies(p["M_cb"], p["K_cb"]),
        }
        for route in matlab_route_frequencies:
            m_frequency = matlab_route_frequencies[route]
            p_frequency = python_route_frequencies[route]
            max_error = float(np.max(np.abs(m_frequency - p_frequency)))
            maximum_modal_frequency_error = max(
                maximum_modal_frequency_error, max_error
            )
            record(
                division,
                "模态频率",
                f"MATLAB_vs_Python_{route}_全阶",
                max_error,
                f"max_abs<={FREQUENCY_TOL_HZ} Hz",
                max_error <= FREQUENCY_TOL_HZ,
            )
            for index, (matlab_value, python_value) in enumerate(
                zip(m_frequency, p_frequency, strict=True), start=1
            ):
                modal_rows.append(
                    {
                        "division": division,
                        "route": route,
                        "mode": index,
                        "matlab_frequency_hz": float(matlab_value),
                        "python_frequency_hz": float(python_value),
                        "absolute_difference_hz": float(
                            abs(matlab_value - python_value)
                        ),
                    }
                )

        original_status = original_comparison["script_status"]
        original_success = scalar_bool(original["success"])
        bytecopy_match = scalar_bool(original["bytecopy_sha256_match"])
        direct_status = original_comparison["direct_filename_status"]
        direct_identifier = original_comparison[
            "direct_filename_error_identifier"
        ]
        csv_bytecopy_match = original_comparison["bytecopy_sha256_match"] == "1"
        csv_script_success = original_comparison["script_success"] == "1"
        record(
            division,
            "作者原脚本",
            "逐字节相同ASCII文件名副本执行",
            f"status={original_status};mat_success={original_success};csv_success={csv_script_success};mat_hash={bytecopy_match};csv_hash={csv_bytecopy_match}",
            "SUCCESS;MAT/CSV success=true;MAT/CSV bytecopy_sha256_match=true",
            original_status == "SUCCESS"
            and original_success
            and csv_script_success
            and bytecopy_match
            and csv_bytecopy_match,
        )
        record(
            division,
            "作者原脚本",
            "中文原文件名直接运行失败如实保留",
            f"status={direct_status};identifier={direct_identifier}",
            "FAILED;MATLAB:m_illegal_character",
            direct_status == "FAILED"
            and direct_identifier == "MATLAB:m_illegal_character",
        )
        for field, division_field in (
            ("T", "T"),
            ("M_historical", "M_historical"),
            ("C_historical", "C_historical"),
            ("K_historical", "K_historical"),
            ("Mf", "Mf"),
        ):
            error = relative_error(original[field], m[division_field])
            record(
                division,
                "作者原脚本",
                f"bytecopy原脚本_vs_MATLAB重建_{field}",
                error,
                f"relative_error<={MATRIX_TOL}",
                error <= MATRIX_TOL,
            )

    summary_internal_pass = bool(matlab_summary.get("internal_gate_pass"))
    record(
        "global",
        "MATLAB内部门槛",
        "global_route_summary.internal_gate_pass",
        summary_internal_pass,
        "true",
        summary_internal_pass,
    )
    hash_row_count, hash_problems = verify_hash_table(MATLAB_HASHES)
    record(
        "global",
        "制品哈希",
        "global_output_hashes逐项重算",
        f"rows={hash_row_count};problems={len(hash_problems)}",
        "problems=0",
        len(hash_problems) == 0,
    )
    failures.extend(hash_problems)

    summary = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "matlab_mat": str(MATLAB_MAT),
        "matlab_mat_sha256": sha256(MATLAB_MAT),
        "python_mat": str(PYTHON_MAT),
        "python_mat_sha256": sha256(PYTHON_MAT),
        "matlab_summary_sha256": sha256(MATLAB_SUMMARY),
        "matrix_tolerance": MATRIX_TOL,
        "frequency_tolerance_hz": FREQUENCY_TOL_HZ,
        "subspace_angle_tolerance_rad": SUBSPACE_ANGLE_TOL_RAD,
        "check_count": len(checks),
        "pass_count": sum(row["result"] == "PASS" for row in checks),
        "failure_count": len(failures),
        "maximum_direct_matrix_relative_error": maximum_direct_error,
        "maximum_cb_aligned_matrix_relative_error": maximum_cb_aligned_error,
        "maximum_cb_subspace_angle_rad": maximum_subspace_angle,
        "maximum_modal_frequency_absolute_error_hz": maximum_modal_frequency_error,
        "hash_table_row_count": hash_row_count,
        "preliminary_run_attempts": PRELIMINARY_RUN_ATTEMPTS,
        "failures": failures,
        "pass": len(failures) == 0,
    }
    write_csv(OUTPUT_CHECKS, checks)
    write_csv(OUTPUT_MODAL, modal_rows)
    OUTPUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    LOG_PATH.write_text(
        "\n".join(
            [
                "板块17 MATLAB-Python跨语言全局缩聚验证",
                f"生成时间(UTC): {summary['generated_at_utc']}",
                f"MATLAB MAT SHA-256: {summary['matlab_mat_sha256']}",
                f"Python MAT SHA-256: {summary['python_mat_sha256']}",
                f"检查数: {summary['check_count']}",
                f"通过数: {summary['pass_count']}",
                f"失败数: {summary['failure_count']}",
                f"最大直接矩阵相对误差: {maximum_direct_error:.17g}",
                f"最大CB对齐矩阵相对误差: {maximum_cb_aligned_error:.17g}",
                f"最大CB子空间角(rad): {maximum_subspace_angle:.17g}",
                f"最大频率绝对差(Hz): {maximum_modal_frequency_error:.17g}",
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

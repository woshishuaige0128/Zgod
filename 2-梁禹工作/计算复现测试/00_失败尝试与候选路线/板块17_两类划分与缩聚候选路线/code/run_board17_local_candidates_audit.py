from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
from scipy.io import loadmat


CODE_DIR = Path(__file__).resolve().parent
ROOT = CODE_DIR.parent
INPUT_LOCAL = ROOT / "input" / "local_candidates"
INPUT_RESPONSE = ROOT / "input" / "response_chain"
OUTPUT = ROOT / "outputs"
LOG = ROOT / "logs"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(name: str) -> list[dict[str, str]]:
    with (OUTPUT / name).open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def rel_error(actual: np.ndarray, expected: np.ndarray) -> float:
    actual = np.asarray(actual, dtype=float)
    expected = np.asarray(expected, dtype=float)
    scale = max(1.0, float(np.linalg.norm(expected, ord="fro")))
    return float(np.linalg.norm(actual - expected, ord="fro") / scale)


def verify_pd_struct(label: str, data: dict, full: int, slave: int) -> dict:
    assert data["run_status"] == "success"
    assert int(data["full_dof"]) == full
    assert int(data["master_dof"]) == 2
    assert int(data["slave_dof"]) == slave
    assert int(data["guyan_dof"]) == 2
    assert int(data["cb_modes"]) == 3
    assert int(data["cb_dof"]) == 5
    assert abs(float(data["damping_numeric"]) - 0.1) <= 1e-15
    assert abs(float(data["damping_comment_claim"]) - 0.05) <= 1e-15
    assert not bool(data["damping_comment_consistency"])

    for matrix_name, shape in {
        "KPrt": (full, full),
        "MPrt": (full, full),
        "CPrt": (full, full),
        "KRren": (2, 2),
        "MRren": (2, 2),
        "CRren": (2, 2),
        "T": (full, 2),
        "T_cb": (full, 5),
        "KR_cb": (5, 5),
        "MR_cb": (5, 5),
        "CR_cb": (5, 5),
    }.items():
        matrix = np.asarray(data[matrix_name], dtype=float)
        assert matrix.shape == shape, (label, matrix_name, matrix.shape, shape)
        assert np.isfinite(matrix).all(), (label, matrix_name)

    master = np.atleast_1d(data["index_master"]).astype(int) - 1
    slave_index = np.atleast_1d(data["index_slave"]).astype(int) - 1
    idx_all = np.concatenate((master, slave_index))
    k = np.asarray(data["KPrt"], dtype=float)
    m = np.asarray(data["MPrt"], dtype=float)
    c = np.asarray(data["CPrt"], dtype=float)
    kmm = k[np.ix_(master, master)]
    kms = k[np.ix_(master, slave_index)]
    kss = k[np.ix_(slave_index, slave_index)]
    ksm = k[np.ix_(slave_index, master)]
    mmm = m[np.ix_(master, master)]
    mms = m[np.ix_(master, slave_index)]
    cmm = c[np.ix_(master, master)]
    cms = c[np.ix_(master, slave_index)]
    constraint = np.linalg.solve(kss, ksm)
    t_expected = np.vstack((np.eye(2), -constraint))

    errors = {
        "T_author_formula_rel": rel_error(data["T"], t_expected),
        "K_guyan_author_formula_rel": rel_error(data["KRren"], kmm - kms @ constraint),
        "M_guyan_author_formula_rel": rel_error(data["MRren"], mmm - mms @ constraint),
        "C_guyan_author_formula_rel": rel_error(data["CRren"], cmm - cms @ constraint),
    }

    ordered_m = m[np.ix_(idx_all, idx_all)]
    ordered_c = c[np.ix_(idx_all, idx_all)]
    ordered_k = k[np.ix_(idx_all, idx_all)]
    t_cb = np.asarray(data["T_cb"], dtype=float)
    errors.update(
        {
            "M_cb_projection_rel": rel_error(data["MR_cb"], t_cb.T @ ordered_m @ t_cb),
            "C_cb_projection_rel": rel_error(data["CR_cb"], t_cb.T @ ordered_c @ t_cb),
            "K_cb_projection_rel": rel_error(data["KR_cb"], t_cb.T @ ordered_k @ t_cb),
        }
    )
    assert max(errors.values()) <= 1e-12, (label, errors)
    return errors


def verify_matrix_csv(pd: dict[str, dict]) -> int:
    rows = read_csv("local_pd_matrix_values.csv")
    grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault((row["Script"], row["Matrix"]), []).append(row)
    for (script, matrix_name), matrix_rows in grouped.items():
        matrix = np.asarray(pd[script][matrix_name], dtype=float)
        rebuilt = np.full(matrix.shape, np.nan, dtype=float)
        for row in matrix_rows:
            assert abs(float(row["ValueImag"])) <= 1e-15
            rebuilt[int(row["MatrixRow"]) - 1, int(row["MatrixColumn"]) - 1] = float(
                row["ValueReal"]
            )
        assert np.isfinite(rebuilt).all(), (script, matrix_name)
        assert rel_error(rebuilt, matrix) <= 1e-14, (script, matrix_name)
    return len(rows)


def verify_attempts() -> dict:
    rows = read_csv("local_new_script_attempts.csv")
    assert len(rows) == 12
    by_key = {(row["script"], row["scenario"]): row for row in rows}
    scripts = ("New_Ps2.m", "New_Ns2.m", "New_Ps3.m", "New_Ns3.m")
    for script in scripts:
        literal = by_key[(script, "empty_workspace")]
        contextual = by_key[(script, "frozen_full15_no_coeff")]
        probe = by_key[(script, "unit_coeff_dimension_probe")]
        assert literal["run_status"] == "error"
        assert literal["status_label"] == "FAILED_ATTEMPT"
        assert contextual["run_status"] == "error"
        assert contextual["error_identifier"] == "MATLAB:UndefinedFunction"
        assert probe["run_status"] == "success"
        assert probe["status_label"] == "DIMENSION_PROBE_ONLY_NOT_REPRODUCTION"

    ns2 = by_key[("New_Ns2.m", "unit_coeff_dimension_probe")]
    ps3 = by_key[("New_Ps3.m", "unit_coeff_dimension_probe")]
    ns3 = by_key[("New_Ns3.m", "unit_coeff_dimension_probe")]
    assert (int(float(ns2["KNrt_rows"])), int(float(ns2["lN_rows"]))) == (11, 15)
    assert (int(float(ps3["KPrt_rows"])), int(float(ps3["lP_rows"]))) == (9, 6)
    assert (int(float(ns3["KNrt_rows"])), int(float(ns3["lN_rows"]))) == (15, 15)
    assert int(float(ns3["locate_count"])) == 14
    return {
        "attempt_count": len(rows),
        "literal_error_count": 4,
        "context_missing_coeff_error_count": 4,
        "dimension_probe_success_count": 4,
        "ns2_matrix_vector_rows": [11, 15],
        "ps3_matrix_vector_rows": [9, 6],
        "ns3_matrix_vector_locate_rows": [15, 15, 14],
    }


def verify_damping_audit() -> None:
    rows = {r["Script"]: r for r in read_csv("local_damping_comment_audit.csv")}
    expected = {
        "PDmonicanshu2.m": (0.1, 0.05, "CONFLICT_NUMERIC_VALUE_VS_COMMENT"),
        "PDmonicanshu3.m": (0.1, 0.05, "CONFLICT_NUMERIC_VALUE_VS_COMMENT"),
        "New_Ps2.m": (0.1, 0.05, "CONFLICT_NUMERIC_VALUE_VS_COMMENT"),
        "New_Ns2.m": (0.1, 0.05, "CONFLICT_NUMERIC_VALUE_VS_COMMENT"),
        "New_Ps3.m": (0.05, 0.05, "MATCH"),
    }
    for script, (numeric, comment, observation) in expected.items():
        row = rows[script]
        assert abs(float(row["DampingNumeric"]) - numeric) <= 1e-15
        assert abs(float(row["DampingCommentClaim"]) - comment) <= 1e-15
        assert row["Observation"] == observation
    assert rows["New_Ns3.m"]["Observation"] == "NO_LOCAL_DAMPING_ASSIGNMENT"


def verify_summary_and_gate() -> None:
    with (OUTPUT / "local_candidate_summary.json").open("r", encoding="utf-8") as stream:
        summary = json.load(stream)
    assert summary["generated_at"].endswith("+08:00")
    assert "***" not in summary["generated_at"]
    assert summary["new_attempt_count"] == 12
    assert summary["new_attempt_success_count"] == 4
    assert summary["new_attempt_error_count"] == 8
    assert summary["assembly_12d_result"] == "FAIL_PENDING_DECISION"
    assert summary["no_assembled_matrix_created"] is True

    gate = read_csv("local_assembly_12d_gate.csv")
    assert len(gate) == 8
    assert gate[-1]["Result"] == "FAIL_PENDING_DECISION"
    assert sum(row["Result"] == "PASS" for row in gate) == 1
    assert not any("12x12" in p.name.lower() and p.suffix.lower() == ".mat" for p in OUTPUT.iterdir())


def write_audit_outputs(audit: dict) -> tuple[Path, Path, Path]:
    json_path = OUTPUT / "local_candidate_python_audit.json"
    log_path = LOG / "local_candidate_python_audit.log"
    manifest_path = OUTPUT / "local_artifact_manifest.csv"
    json_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "Board 17 independent Python audit: PASS",
        f"Timestamp: {audit['audited_at']}",
        f"PD2 maximum formula relative error: {audit['formula_errors']['PDmonicanshu2.m']['max']:.3e}",
        f"PD3 maximum formula relative error: {audit['formula_errors']['PDmonicanshu3.m']['max']:.3e}",
        f"Matrix CSV rows checked: {audit['matrix_csv_rows_checked']}",
        "New_* attempts: 4 literal errors + 4 missing-coefficient errors + 4 dimension probes",
        "12-DOF assembly gate: FAIL_PENDING_DECISION",
        "No assembled 12x12 MAT file exists.",
    ]
    log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    paths: list[tuple[str, Path]] = []
    for source in sorted(INPUT_LOCAL.glob("*.m")):
        paths.append(("frozen_local_input", source))
    paths.append(("frozen_response_input", INPUT_RESPONSE / "PDmonicanshu.m"))
    for source in sorted(CODE_DIR.glob("run_board17_local_candidates*")):
        paths.append(("runner_or_auditor", source))
    for source in sorted(OUTPUT.glob("local_*")):
        if source.is_file() and source != manifest_path:
            paths.append(("local_output", source))
    for source in sorted(LOG.glob("local_*")):
        if source.is_file():
            paths.append(("local_log", source))

    with manifest_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("category", "relative_path", "bytes", "sha256"),
        )
        writer.writeheader()
        for category, source in paths:
            writer.writerow(
                {
                    "category": category,
                    "relative_path": source.relative_to(ROOT).as_posix(),
                    "bytes": source.stat().st_size,
                    "sha256": sha256(source),
                }
            )
    return json_path, log_path, manifest_path


def main() -> None:
    mat = loadmat(OUTPUT / "local_pd_reductions.mat", simplify_cells=True)
    pd2 = mat["pd2"]
    pd3 = mat["pd3"]
    errors2 = verify_pd_struct("PDmonicanshu2.m", pd2, 6, 4)
    errors3 = verify_pd_struct("PDmonicanshu3.m", pd3, 9, 7)
    matrix_rows = verify_matrix_csv({"PDmonicanshu2.m": pd2, "PDmonicanshu3.m": pd3})
    attempt_evidence = verify_attempts()
    verify_damping_audit()
    verify_summary_and_gate()

    audit = {
        "status": "PASS",
        "audited_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "python_executable_required": r"D:\Software\python\python.exe",
        "formula_tolerance": 1e-12,
        "formula_errors": {
            "PDmonicanshu2.m": {**errors2, "max": max(errors2.values())},
            "PDmonicanshu3.m": {**errors3, "max": max(errors3.values())},
        },
        "matrix_csv_rows_checked": matrix_rows,
        "attempt_evidence": attempt_evidence,
        "damping_comment_audit": "PASS",
        "assembled_12d_status": "FAIL_PENDING_DECISION",
        "assembled_12d_matrix_created": False,
    }
    json_path, log_path, manifest_path = write_audit_outputs(audit)
    print("PYTHON_AUDIT_STATUS=PASS")
    print(f"MATRIX_CSV_ROWS_CHECKED={matrix_rows}")
    print(f"PD2_MAX_FORMULA_REL_ERROR={max(errors2.values()):.17g}")
    print(f"PD3_MAX_FORMULA_REL_ERROR={max(errors3.values()):.17g}")
    print("ASSEMBLY_12D_STATUS=FAIL_PENDING_DECISION")
    print(f"AUDIT_JSON={json_path}")
    print(f"AUDIT_LOG={log_path}")
    print(f"HASH_MANIFEST={manifest_path}")


if __name__ == "__main__":
    main()

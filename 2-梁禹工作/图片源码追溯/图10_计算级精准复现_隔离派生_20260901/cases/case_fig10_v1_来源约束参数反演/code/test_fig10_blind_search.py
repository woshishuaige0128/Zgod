#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图10盲算核心/调度器的合成与旧 R03 加载回归。

本测试不运行 B1/B2/B3，不执行科学参数搜索。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np

import fig10_blind_core as core


SCRIPT = Path(__file__).resolve()
CODE_DIR = SCRIPT.parent
RUNNER = CODE_DIR / "run_fig10_blind_search.py"
REPOSITORY_ROOT = SCRIPT.parents[5]
BOARD20_ROOT = (
    REPOSITORY_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
)
R03_BUNDLE = (
    BOARD20_ROOT
    / "outputs"
    / "step8c_六链模型生成"
    / "python"
    / "候选数值包"
    / "第1类_原结构15维__R03_论文CARE_矩阵al_广义力.mat"
)
R03_RESULTS = (
    BOARD20_ROOT
    / "outputs"
    / "step8e_四候选全网格"
    / "python"
    / "步骤8E_Python全网格逐点结果.csv"
)
R03_BUNDLE_SHA256 = "D5E81B75E16F038F14C8CF0D9E4DA4550C875BF3CC17F513F31352DDF512DF2B"
R03_RESULTS_SHA256 = "9028D1010EA698BECAEFC5026F9B705ECD032FFAD7D1575F65E74403150E225A"
R03_POINTS = ((0, 0), (7, 13), (30, 66))


def sha256(path: Path) -> str:
    return core.sha256_file(path)


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def make_synthetic_bundle(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        dimension=np.asarray([1], dtype=np.int64),
        dt=np.asarray([1.0 / 1024.0], dtype=np.float64),
        mass_term=np.asarray([[1.0]], dtype=np.float64),
        base_zero=np.asarray([[-0.5]], dtype=np.float64),
        base_minus_one=np.asarray([[0.06]], dtype=np.float64),
        delay_left=np.zeros((1, 2), dtype=np.float64),
        delay_v_zero=np.zeros((2, 1), dtype=np.float64),
        delay_v_minus_one=np.zeros((2, 1), dtype=np.float64),
        register_scales=np.ones(2, dtype=np.float64),
        shared_left_factor_relative_error=np.asarray([0.0], dtype=np.float64),
    )


def synthetic_manifest(bundle: Path) -> dict[str, Any]:
    return {
        "schema_version": "FIG10_BLIND_SEARCH_MANIFEST_V1",
        "run_id": "SYNTHETIC_REGRESSION",
        "allowed_bundle_roots": [str(bundle.parent)],
        "sampling": {
            "grid": {"l_min": 0, "l_max": 2, "j_min": 0, "j_max": 3},
            "sentinel_points": [[0, 0], [2, 3]],
            "fixed_sparse_band_points": [[0, 1], [1, 2], [2, 2]],
        },
        "routes": [
            {
                "route_id": "synthetic_route",
                "contract_id": "SYNTHETIC_CORE_CONTRACT",
                "contract_hash": hashlib.sha256(b"synthetic-contract").hexdigest().upper(),
                "division": 1,
                "method": "Synthetic",
                "dimension": 1,
                "operator_layout": core.NATIVE_LAYOUT,
                "bundle_path": str(bundle),
                "bundle_sha256": sha256(bundle),
            }
        ],
    }


def run_runner(manifest: Path, output: Path, mode: str, resume: bool = False) -> dict[str, Any]:
    command = [
        sys.executable,
        str(RUNNER),
        "--manifest",
        str(manifest),
        "--output-dir",
        str(output),
        "--mode",
        mode,
        "--checkpoint-every",
        "1",
    ]
    if resume:
        command.append("--resume")
    environment = dict(os.environ)
    environment["PYTHONIOENCODING"] = "utf-8"
    process = subprocess.run(
        command,
        cwd=CODE_DIR,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        raise RuntimeError(
            f"runner {mode} failed: code={process.returncode}\n{process.stdout}\n{process.stderr}"
        )
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def load_r03_reference() -> dict[tuple[int, int], dict[str, str]]:
    if sha256(R03_BUNDLE) != R03_BUNDLE_SHA256:
        raise RuntimeError("R03算子包哈希漂移")
    if sha256(R03_RESULTS) != R03_RESULTS_SHA256:
        raise RuntimeError("R03旧全网格结果哈希漂移")
    selected: dict[tuple[int, int], dict[str, str]] = {}
    with R03_RESULTS.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            point = (int(row["l_samples"]), int(row["j_samples"]))
            if (
                row["candidate_id"] == "R03"
                and row["division"] == "1"
                and row["method"] == "Original"
                and point in R03_POINTS
            ):
                selected[point] = row
    if set(selected) != set(R03_POINTS):
        raise RuntimeError("R03冻结哨兵点不闭合")
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    checks: dict[str, bool] = {}
    evidence: dict[str, Any] = {}

    with tempfile.TemporaryDirectory(prefix="fig10_blind_regression_") as temporary:
        work = Path(temporary)
        bundle_path = work / "bundles" / "synthetic_operator_bundle.npz"
        make_synthetic_bundle(bundle_path)
        manifest_path = work / "synthetic_manifest.json"
        write_json(manifest_path, synthetic_manifest(bundle_path))

        metadata = synthetic_manifest(bundle_path)["routes"][0]
        bundle = core.load_blind_bundle(bundle_path, metadata)
        point00 = core.solve_minimal_point(bundle, 0, 0, return_physical_vectors=True)
        checks["synthetic_root_count_two"] = point00.roots.size == 2
        checks["synthetic_roots_are_0p2_0p3"] = np.allclose(
            point00.roots, np.asarray([0.2, 0.3], dtype=np.complex128), rtol=0.0, atol=1e-14
        )
        checks["synthetic_rho_0p3"] = math_isclose(point00.rho, 0.3, 1e-14)
        checks["synthetic_state_residual_pass"] = float(np.max(point00.state_residuals)) <= core.RESIDUAL_LIMIT

        mode_expected = {"sentinel": 2, "sparse-band": 3, "full-grid": 12}
        mode_records = {}
        for mode, expected_count in mode_expected.items():
            mode_output = work / f"run_{mode}"
            first = run_runner(manifest_path, mode_output, mode)
            summary = json.loads((mode_output / "run_summary.json").read_text(encoding="utf-8"))
            checkpoint = json.loads(
                (
                    mode_output
                    / "routes"
                    / "synthetic_route"
                    / mode
                    / "checkpoint.json"
                ).read_text(encoding="utf-8")
            )
            checks[f"{mode}_point_count"] = summary["point_count"] == expected_count
            checks[f"{mode}_checkpoint_complete"] = (
                checkpoint["status"] == "COMPLETE"
                and checkpoint["completed_point_count"] == expected_count
            )
            checks[f"{mode}_hash_manifest_exists"] = (
                mode_output / "artifact_hash_manifest.csv"
            ).is_file()
            mode_records[mode] = {"first_run": first, "summary": summary, "checkpoint": checkpoint}

        full_route = work / "run_full-grid" / "routes" / "synthetic_route" / "full-grid"
        mask = np.loadtxt(full_route / "stable_mask.csv", delimiter=",", dtype=np.uint8)
        checks["full_grid_mask_shape_3x4"] = mask.shape == (3, 4)
        checks["full_grid_mask_all_stable"] = np.array_equal(mask, np.ones((3, 4), dtype=np.uint8))
        checks["full_grid_mask_has_no_header"] = (full_route / "stable_mask.csv").read_text(
            encoding="ascii"
        ).splitlines()[0] == "1,1,1,1"

        sentinel_output = work / "run_sentinel"
        before_points_hash = sha256(
            sentinel_output / "routes" / "synthetic_route" / "sentinel" / "points.csv"
        )
        resumed = run_runner(manifest_path, sentinel_output, "sentinel", resume=True)
        after_points_hash = sha256(
            sentinel_output / "routes" / "synthetic_route" / "sentinel" / "points.csv"
        )
        checks["completed_checkpoint_resume_preserves_points"] = before_points_hash == after_points_hash
        checks["no_atomic_temp_files_left"] = not any(work.rglob("*.tmp"))
        mode_records["sentinel"]["resume_run"] = resumed
        evidence["synthetic"] = {
            "bundle_sha256": sha256(bundle_path),
            "manifest_sha256": sha256(manifest_path),
            "point00_roots_real": point00.roots.real.tolist(),
            "point00_roots_imag": point00.roots.imag.tolist(),
            "point00_rho": point00.rho,
            "maximum_state_residual": float(np.max(point00.state_residuals)),
            "modes": mode_records,
        }

    reference = load_r03_reference()
    r03_metadata = {
        "route_id": "D1_Original_R03_regression",
        "contract_id": "BOARD20_R03_FROZEN_REGRESSION",
        "dimension": 15,
        "division": 1,
        "candidate_index": 3,
        "operator_layout": core.LEGACY_LAYOUT,
        "bundle_sha256": R03_BUNDLE_SHA256,
    }
    r03_bundle = core.load_blind_bundle(R03_BUNDLE, r03_metadata)
    r03_rows = []
    for point in R03_POINTS:
        result = core.solve_minimal_point(r03_bundle, point[0], point[1])
        expected = reference[point]
        rho_error = abs(result.rho - float(expected["rho"]))
        dominant_error = abs(
            result.dominant_root
            - complex(float(expected["dominant_root_real"]), float(expected["dominant_root_imag"]))
        )
        r03_rows.append(
            {
                "l_samples": point[0],
                "j_samples": point[1],
                "expected_rho": float(expected["rho"]),
                "actual_rho": result.rho,
                "rho_abs_error": rho_error,
                "expected_root_count": int(expected["physical_root_count"]),
                "actual_root_count": result.roots.size,
                "dominant_root_abs_error": dominant_error,
                "expected_stability_code": int(expected["stability_code"]),
                "actual_stability_code": result.stability_code,
                "maximum_state_residual": float(np.max(result.state_residuals)),
            }
        )
    checks["r03_three_points_loaded_and_solved"] = len(r03_rows) == 3
    checks["r03_root_counts_exact"] = all(
        row["actual_root_count"] == row["expected_root_count"] for row in r03_rows
    )
    checks["r03_rho_abs_error_le_1e-13"] = all(row["rho_abs_error"] <= 1e-13 for row in r03_rows)
    checks["r03_dominant_root_abs_error_le_1e-13"] = all(
        row["dominant_root_abs_error"] <= 1e-13 for row in r03_rows
    )
    checks["r03_classification_exact"] = all(
        row["actual_stability_code"] == row["expected_stability_code"] for row in r03_rows
    )
    checks["r03_residuals_pass"] = all(
        row["maximum_state_residual"] <= core.RESIDUAL_LIMIT for row in r03_rows
    )
    evidence["r03_regression"] = {
        "bundle_path": str(R03_BUNDLE),
        "bundle_sha256": R03_BUNDLE_SHA256,
        "reference_csv_path": str(R03_RESULTS),
        "reference_csv_sha256": R03_RESULTS_SHA256,
        "points": r03_rows,
    }

    status = "PASS" if all(checks.values()) else "FAIL"
    summary = {
        "schema_version": "FIG10_BLIND_REGRESSION_V1",
        "status": status,
        "scientific_search_executed": False,
        "checks": checks,
        "evidence": evidence,
        "code_hashes": {
            "fig10_blind_core.py": sha256(CODE_DIR / "fig10_blind_core.py"),
            "run_fig10_blind_search.py": sha256(RUNNER),
            "test_fig10_blind_search.py": sha256(SCRIPT),
        },
    }
    write_json(output_dir / "blind_regression_summary.json", summary)
    with (output_dir / "r03_three_point_regression.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(stream, fieldnames=list(r03_rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(r03_rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if status == "PASS" else 1


def math_isclose(actual: float, expected: float, tolerance: float) -> bool:
    return abs(actual - expected) <= tolerance


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H07能量脚本整束历史来源补全诊断的合成/真实Stage0测试。

本测试只核验源码证据、数值物化与盲算清单；不调用特征根函数，不运行时滞网格，
不读取绘图数据、目标CSV、PDF或严格评价器。
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Mapping

import numpy as np
from scipy.io import loadmat
from scipy.linalg import solve_discrete_are
from scipy.signal import cont2discrete


SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
EVALUATION_DIR = CASE_DIR / "evaluation" / "h07_energy_bundle_diagnostic_stage0"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_h07_energy_bundle_diagnostic as h07
import fig10_blind_core as core
import run_fig10_blind_search as runner


EXPECTED_CORE_SHA256 = "9F001CD1E57F8909070295EBC8E265B2CE6619784EE1ADDA75F762B49B377411"
FIELD_TOL = 2.0e-12


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected)), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected) / denominator)


def independent_native_operator(data: Mapping[str, Any]) -> dict[str, np.ndarray]:
    dt = float(np.asarray(data["dt"], dtype=np.float64).reshape(-1)[0])
    integration = np.asarray(data["integration_mass_operator"], dtype=np.float64)
    c1 = np.asarray(data["C1"], dtype=np.float64)
    k1 = np.asarray(data["K1"], dtype=np.float64)
    feedback_c = np.asarray(data["feedback_C"], dtype=np.float64)
    feedback_k = np.asarray(data["feedback_K"], dtype=np.float64)
    delay_c_left = np.asarray(data["delay_C_left_H_right"], dtype=np.float64)
    delay_k_left = np.asarray(data["delay_K_left_H_right"], dtype=np.float64)
    delay_right = np.asarray(data["delay_right_selector"], dtype=np.float64)

    mass = integration / dt**2
    base_zero = -2.0 * mass + c1 / dt + k1 + feedback_c / dt + feedback_k
    base_minus = mass - c1 / dt - feedback_c / dt
    delay_left = delay_right.T
    delay_v_zero = delay_c_left.T / dt + delay_k_left.T
    delay_v_minus = -delay_c_left.T / dt
    scales = np.maximum.reduce(
        (
            np.linalg.norm(delay_v_zero, axis=1),
            np.linalg.norm(delay_v_minus, axis=1),
            np.full(2, np.finfo(float).eps),
        )
    )
    return {
        "mass_term": mass.T,
        "base_zero": base_zero.T,
        "base_minus_one": base_minus.T,
        "delay_left": delay_left,
        "delay_v_zero": delay_v_zero,
        "delay_v_minus_one": delay_v_minus,
        "register_scales": scales,
    }


def atomic_write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode(
        "utf-8"
    )
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        temporary = Path(temporary_name)
        if temporary.exists():
            temporary.unlink()


class H07EnergyBundleDiagnosticTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = h07.repo_root()
        cls.artifacts, cls.summary = h07.build_artifacts(cls.repo_root)
        h07.verify_output(h07.DEFAULT_OUTPUT_DIR, cls.artifacts)

    def test_01_frozen_source_lines_and_hashes_close(self) -> None:
        evidence = h07.validate_source_evidence(self.repo_root)
        self.assertEqual(evidence["step8b_sha256"], h07.STEP8B_SHA256)
        self.assertEqual(evidence["mlx_contract_sha256"], h07.MLX_CONTRACT_SHA256)
        self.assertEqual(len(evidence["source_scripts"]), 6)
        for row in evidence["source_scripts"]:
            self.assertEqual(sha256_file(self.repo_root / row["code_repo_relative_path"]), row["code_sha256"])
            self.assertEqual(sha256_file(self.repo_root / row["mlx_repo_relative_path"]), row["mlx_sha256"])
            self.assertTrue(row["line_assertions"])

        guy2 = h07.SOURCE_FILES["luxvjie_guyan_LQR2.m"]["line_assertions"]
        self.assertEqual(guy2[42], "Q = diag([4e8, 1e4, 1e2, 1e1]);")
        self.assertEqual(guy2[43], "R = diag([3e-3,1e-2]);")
        self.assertIn("*H", guy2[74])
        self.assertEqual(guy2[2], "index2 = [3,4,5,6,7,8];")

    def test_02_synthetic_stage0_zoh_dare_diagonal_and_right_H(self) -> None:
        dt = 1.0 / 1024.0
        mass_local = np.diag([2.0, 3.0])
        damping_local = np.diag([0.3, 0.4])
        stiffness_local = np.diag([5.0, 7.0])
        identity = np.eye(2)
        zero = np.zeros((2, 2))
        a_matrix = np.block(
            [
                [zero, identity],
                [
                    -np.linalg.solve(mass_local, stiffness_local),
                    -np.linalg.solve(mass_local, damping_local),
                ],
            ]
        )
        b_matrix = np.vstack((zero, np.linalg.solve(mass_local, identity)))
        ad, bd = h07.exact_zoh(a_matrix, b_matrix, dt)
        ad_ref, bd_ref, _, _, _ = cont2discrete(
            (a_matrix, b_matrix, np.eye(4), np.zeros((4, 2))), dt, method="zoh"
        )
        self.assertLessEqual(rel(ad, ad_ref), 1.0e-14)
        self.assertLessEqual(rel(bd, bd_ref), 1.0e-14)

        p = solve_discrete_are(ad, bd, h07.Q_ENERGY, h07.R_ENERGY)
        gain = np.linalg.solve(h07.R_ENERGY + bd.T @ p @ bd, bd.T @ p @ ad)
        self.assertLess(h07.dare_residual(ad, bd, p), 1.0e-10)
        self.assertLess(float(np.max(np.abs(np.linalg.eigvals(ad - bd @ gain)))), 1.0)
        delta_k = np.diag(np.diag(mass_local @ gain[:, :2]))
        delta_c = np.diag(np.diag(mass_local @ gain[:, 2:]))
        self.assertEqual(np.count_nonzero(delta_k - np.diag(np.diag(delta_k))), 0)
        self.assertEqual(np.count_nonzero(delta_c - np.diag(np.diag(delta_c))), 0)

        n = 3
        delay_c_left = np.asarray([[1.0, 0.2], [0.1, 0.8], [0.4, 0.3]])
        delay_k_left = np.asarray([[2.0, 0.1], [0.2, 1.5], [0.7, 0.6]])
        delay_right = np.asarray([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        h_matrix = np.diag([0.25, 0.75])
        direct = (delay_c_left / dt + delay_k_left) @ h_matrix @ delay_right
        native = delay_right.T @ h_matrix @ (delay_c_left.T / dt + delay_k_left.T)
        self.assertLessEqual(rel(native, direct.T), 1.0e-15)
        self.assertEqual(native.shape, (n, n))

    def test_03_real_six_route_stage0_field_recalculation(self) -> None:
        routes = self.summary["routes"]
        self.assertEqual(len(routes), 6)
        for route in routes:
            with self.subTest(route=route.route_id):
                path = h07.DEFAULT_OUTPUT_DIR / "numeric_bundles" / f"{route.route_id}_native.mat"
                data = loadmat(path, squeeze_me=True, struct_as_record=False)
                expected = independent_native_operator(data)
                for field in h07.OPERATOR_FIELDS:
                    actual = np.asarray(data[field], dtype=np.float64)
                    if field == "register_scales":
                        actual = actual.reshape(-1)
                    self.assertLessEqual(rel(actual, expected[field]), FIELD_TOL, field)

                mass = np.asarray(data["M"], dtype=np.float64)
                damping = np.asarray(data["C"], dtype=np.float64)
                stiffness = np.asarray(data["K"], dtype=np.float64)
                dt = float(np.asarray(data["dt"]).reshape(-1)[0])
                al_full = np.linalg.solve(
                    4.0 * mass + 2.0 * dt * damping + dt**2 * stiffness,
                    4.0 * mass,
                )
                al_diag = np.diag(np.diag(al_full))
                integration = np.linalg.solve(al_diag.T, mass.T).T
                self.assertLessEqual(rel(al_full, np.asarray(data["matrix_al_full"])), FIELD_TOL)
                self.assertLessEqual(rel(al_diag, np.asarray(data["matrix_al_diag"])), FIELD_TOL)
                self.assertLessEqual(
                    rel(integration, np.asarray(data["integration_mass_operator"])), FIELD_TOL
                )

                c2 = np.asarray(data["delay_C_left_H_right"]) @ np.asarray(
                    data["delay_right_selector"]
                )
                k2 = np.asarray(data["delay_K_left_H_right"]) @ np.asarray(
                    data["delay_right_selector"]
                )
                self.assertLessEqual(rel(c2, np.asarray(data["C2_completed_delayed_columns"])), FIELD_TOL)
                self.assertLessEqual(rel(k2, np.asarray(data["K2_completed_delayed_columns"])), FIELD_TOL)
                self.assertLessEqual(rel(np.asarray(data["C1"]) + c2, damping), FIELD_TOL)
                self.assertLessEqual(rel(np.asarray(data["K1"]) + k2, stiffness), FIELD_TOL)

                local_mass = np.asarray(data["M_controller_local"])
                gain = np.asarray(data["controller_gain"])
                delta_k = np.diag(np.diag(local_mass @ gain[:, :2]))
                delta_c = np.diag(np.diag(local_mass @ gain[:, 2:]))
                self.assertLessEqual(rel(delta_k, np.asarray(data["DeltaK_diag"])), FIELD_TOL)
                self.assertLessEqual(rel(delta_c, np.asarray(data["DeltaC_diag"])), FIELD_TOL)
                self.assertEqual(int(np.asarray(data["formula_valid_code"]).reshape(-1)[0]), 0)
                self.assertEqual(int(np.asarray(data["paper_grid_eligible_code"]).reshape(-1)[0]), 0)
                self.assertEqual(
                    int(np.asarray(data["energy_literal_KN_CN_block_equivalence_claimed_code"]).reshape(-1)[0]),
                    0,
                )

    def test_04_H07_manifest_and_native_bundles_load_without_execution(self) -> None:
        manifest_path = h07.DEFAULT_OUTPUT_DIR / "manifests" / "H07.json"
        manifest, _, _ = runner.load_manifest(manifest_path)
        self.assertEqual(manifest["evidence_level"], h07.DIAGNOSTIC_STATUS)
        self.assertFalse(manifest["paper_formula_eligible"])
        self.assertFalse(manifest["paper_grid_eligible"])
        self.assertFalse(manifest["scientific_search_executed"])
        self.assertEqual(manifest["roots_computed"], 0)
        self.assertEqual(manifest["grid_points_computed"], 0)
        self.assertEqual(len(manifest["routes"]), 6)
        for route in manifest["routes"]:
            self.assertEqual(route["source_support_status"], h07.DIAGNOSTIC_STATUS)
            self.assertEqual(route["delay_decomposition_status"], h07.DELAY_HYBRID_STATUS)
            self.assertTrue(route["extrapolation_required"])
            self.assertFalse(route["energy_literal_KN_CN_block_equivalence_claimed"])
            self.assertEqual(route["formula_valid_code"], 0)
            self.assertEqual(route["paper_grid_eligible_code"], 0)
            bundle_path = (manifest_path.parent / route["bundle_path"]).resolve()
            bundle = core.load_blind_bundle(bundle_path, route)
            self.assertEqual(bundle.operator_layout, core.NATIVE_LAYOUT)
            self.assertEqual(bundle.dimension, route["dimension"])

    def test_05_two_builds_are_byte_deterministic_and_existing_output_matches(self) -> None:
        first, _ = h07.build_artifacts(self.repo_root)
        second, _ = h07.build_artifacts(self.repo_root)
        self.assertEqual(set(first), set(second))
        self.assertEqual(
            {name: h07.sha256_bytes(value) for name, value in first.items()},
            {name: h07.sha256_bytes(value) for name, value in second.items()},
        )
        h07.verify_output(h07.DEFAULT_OUTPUT_DIR, first)

    def test_06_old_formula_gate_is_unchanged_and_targets_are_absent(self) -> None:
        core_path = SCRIPT_DIR / "fig10_blind_core.py"
        self.assertEqual(sha256_file(core_path), EXPECTED_CORE_SHA256)
        core_text = core_path.read_text(encoding="utf-8")
        self.assertIn('for gate_name in ("formula_valid_code", "paper_grid_eligible_code")', core_text)
        generator_text = (SCRIPT_DIR / "build_h07_energy_bundle_diagnostic.py").read_text(
            encoding="utf-8"
        )
        for forbidden in (
            "plotted_data",
            "strict_target_evaluator",
            "target_csv",
            "solve_blind_point",
            "build_minimal_augmented",
            "梁禹手稿.pdf",
        ):
            self.assertNotIn(forbidden, generator_text)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(H07EnergyBundleDiagnosticTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    manifest_path = h07.DEFAULT_OUTPUT_DIR / "h07_materialization_manifest.json"
    summary = {
        "schema_version": "FIG10_H07_ENERGY_BUNDLE_DIAGNOSTIC_TEST_V1",
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "synthetic_stage0_covered": True,
        "real_stage0_routes_checked": 6,
        "source_line_and_hash_checks": 6,
        "native_manifest_loaded_without_execution": True,
        "deterministic_two_build_hashes_checked": True,
        "blind_core_sha256": sha256_file(SCRIPT_DIR / "fig10_blind_core.py"),
        "materialization_manifest_sha256": sha256_file(manifest_path),
        "roots_computed": 0,
        "grid_points_computed": 0,
        "diagnostic_status": h07.DIAGNOSTIC_STATUS,
        "delay_decomposition_status": h07.DELAY_HYBRID_STATUS,
    }
    atomic_write_json(EVALUATION_DIR / "test_summary.json", summary)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

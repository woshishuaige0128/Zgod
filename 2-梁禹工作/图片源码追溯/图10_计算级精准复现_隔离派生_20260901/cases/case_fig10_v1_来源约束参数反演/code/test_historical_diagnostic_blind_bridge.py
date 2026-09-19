#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""H05/H06历史诊断盲算桥的合成与真实Stage0独立测试。

本测试只加载数值包和盲算清单，不调用特征根函数，不运行任何时滞点。
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
from scipy.io import loadmat, savemat


SCRIPT_DIR = Path(__file__).resolve().parent
CASE_DIR = SCRIPT_DIR.parent
EVALUATION_DIR = CASE_DIR / "evaluation" / "historical_diagnostic_bridge_stage0"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import build_historical_diagnostic_blind_bridge as bridge
import fig10_blind_core as core
import run_fig10_blind_search as runner


EXPECTED_CORE_SHA256 = "9F001CD1E57F8909070295EBC8E265B2CE6619784EE1ADDA75F762B49B377411"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def rel(actual: np.ndarray, expected: np.ndarray) -> float:
    denominator = max(float(np.linalg.norm(expected)), np.finfo(float).eps)
    return float(np.linalg.norm(actual - expected) / denominator)


def synthetic_source(transposed: bool) -> dict[str, np.ndarray]:
    n = 3
    dt = 0.25
    mass = np.diag([2.0, 3.0, 5.0])
    c1 = np.diag([0.4, 0.5, 0.6])
    k1 = np.diag([4.0, 5.0, 6.0])
    feedback_c = np.diag([0.03, 0.04, 0.05])
    feedback_k = np.diag([0.2, 0.3, 0.4])
    if transposed:
        c_left = np.asarray([[1.0, 0.0], [0.0, 1.0], [0.2, 0.3]])
        k_left = np.asarray([[0.7, 0.1], [0.2, 0.9], [0.4, 0.6]])
        shared_right = np.asarray([[0.2, 0.1, 0.0], [0.0, 0.3, 0.1]])
        c_right = shared_right
        k_right = shared_right.copy()
    else:
        shared_left = np.asarray([[1.0, 0.0], [0.0, 1.0], [0.2, 0.3]])
        c_left = shared_left
        k_left = shared_left.copy()
        c_right = np.asarray([[0.2, 0.1, 0.0], [0.0, 0.3, 0.1]])
        k_right = np.asarray([[0.5, 0.0, 0.2], [0.1, 0.4, 0.0]])
    c2 = c_left @ c_right
    k2 = k_left @ k_right
    return {
        "dt": np.asarray([[dt]]),
        "M": mass,
        "matrix_al": np.eye(n),
        "integration_mass_operator": mass.copy(),
        "C1": c1,
        "K1": k1,
        "feedback_C": feedback_c,
        "feedback_K": feedback_k,
        "delay_C_left_factor": c_left,
        "delay_K_left_factor": k_left,
        "delay_C_right_factor": c_right,
        "delay_K_right_factor": k_right,
        "C2_zero_delay": c2,
        "K2_zero_delay": k2,
        "C": c1 + c2,
        "K": k1 + k2,
    }


def reference_operator(data: Mapping[str, Any], transpose: bool) -> dict[str, np.ndarray]:
    dt = float(np.asarray(data["dt"]).reshape(-1)[0])
    integration = np.asarray(data["integration_mass_operator"], dtype=np.float64)
    c1 = np.asarray(data["C1"], dtype=np.float64)
    k1 = np.asarray(data["K1"], dtype=np.float64)
    feedback_c = np.asarray(data["feedback_C"], dtype=np.float64)
    feedback_k = np.asarray(data["feedback_K"], dtype=np.float64)
    c_left = np.asarray(data["delay_C_left_factor"], dtype=np.float64)
    k_left = np.asarray(data["delay_K_left_factor"], dtype=np.float64)
    c_right = np.asarray(data["delay_C_right_factor"], dtype=np.float64)
    k_right = np.asarray(data["delay_K_right_factor"], dtype=np.float64)
    mass = integration / dt**2
    base_zero = -2.0 * mass + c1 / dt + k1 + feedback_c / dt + feedback_k
    base_minus = mass - c1 / dt - feedback_c / dt
    if transpose:
        mass = mass.T
        base_zero = base_zero.T
        base_minus = base_minus.T
        delay_left = c_right.T
        v_zero = c_left.T / dt + k_left.T
        v_minus = -c_left.T / dt
    else:
        delay_left = c_left
        v_zero = c_right / dt + k_right
        v_minus = -c_right / dt
    scales = np.maximum.reduce(
        (
            np.linalg.norm(v_zero, axis=1),
            np.linalg.norm(v_minus, axis=1),
            np.full(2, np.finfo(float).eps),
        )
    )
    return {
        "mass_term": mass,
        "base_zero": base_zero,
        "base_minus_one": base_minus,
        "delay_left": delay_left,
        "delay_v_zero": v_zero,
        "delay_v_minus_one": v_minus,
        "register_scales": scales,
    }


def legacy_metadata(path: Path, dimension: int, contract_id: str, division: int, candidate: int) -> dict[str, Any]:
    return {
        "route_id": f"LEGACY_{contract_id}_D{division}",
        "contract_id": contract_id,
        "dimension": dimension,
        "division": division,
        "candidate_index": candidate,
        "operator_layout": core.LEGACY_LAYOUT,
        "bundle_sha256": sha256_file(path),
    }


class HistoricalDiagnosticBridgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repo_root = bridge.repo_root_from_script()
        cls.artifacts, cls.summary = bridge.build_artifacts(cls.repo_root)
        bridge.verify_output(bridge.DEFAULT_OUTPUT_DIR, cls.artifacts)

    def test_01_synthetic_direct_and_transposed_conversion(self) -> None:
        for transpose in (False, True):
            with self.subTest(transpose=transpose):
                data = synthetic_source(transpose)
                actual, checks, actual_transpose = bridge.convert_legacy_arrays(data, 3)
                expected = reference_operator(data, transpose)
                self.assertEqual(actual_transpose, transpose)
                for field in bridge.OPERATOR_FIELDS:
                    self.assertLessEqual(rel(actual[field], expected[field]), 1.0e-15, field)
                gated = [
                    value
                    for name, value in checks.items()
                    if name not in ("source_shared_left_relative_error", "source_shared_right_relative_error")
                ]
                self.assertLessEqual(max(gated), bridge.FACTOR_LIMIT)

    def test_02_real_routes_independent_field_recalculation(self) -> None:
        self.assertEqual(len(self.summary["routes"]), 12)
        for route in self.summary["routes"]:
            with self.subTest(route=route.route_id):
                source_path = self.repo_root / route.source_relative_path
                source = loadmat(source_path, squeeze_me=True, struct_as_record=False)
                expected = reference_operator(
                    source, bool(route.stage0["operator_transpose_for_shared_left"])
                )
                output_path = (
                    bridge.DEFAULT_OUTPUT_DIR
                    / "numeric_bundles"
                    / route.diagnostic_contract_id
                    / f"{route.route_id}_native.mat"
                )
                output = loadmat(output_path, squeeze_me=True, struct_as_record=False)
                for field in bridge.OPERATOR_FIELDS:
                    actual = np.asarray(output[field], dtype=np.float64)
                    if field == "register_scales":
                        actual = actual.reshape(-1)
                    self.assertLessEqual(rel(actual, expected[field]), 1.0e-15, field)
                self.assertEqual(int(np.asarray(output["formula_valid_code"]).reshape(-1)[0]), 0)
                self.assertEqual(int(np.asarray(output["paper_grid_eligible_code"]).reshape(-1)[0]), 0)
                metadata = {
                    "route_id": route.route_id,
                    "contract_id": route.diagnostic_contract_id,
                    "dimension": route.dimension,
                    "division": route.division,
                    "candidate_index": int(route.source_contract_id[-2:]),
                    "operator_layout": core.NATIVE_LAYOUT,
                    "bundle_sha256": sha256_file(output_path),
                }
                loaded = core.load_blind_bundle(output_path, metadata)
                self.assertEqual(loaded.operator_layout, core.NATIVE_LAYOUT)
                self.assertEqual(loaded.dimension, route.dimension)

    def test_03_legacy_formula_and_paper_gates_remain_blocking(self) -> None:
        route = self.summary["routes"][0]
        source_path = self.repo_root / route.source_relative_path
        metadata = legacy_metadata(
            source_path,
            route.dimension,
            route.source_contract_id,
            route.division,
            int(route.source_contract_id[-2:]),
        )
        with self.assertRaisesRegex(core.BlindContractError, "formula_valid_code不是1"):
            core.load_blind_bundle(source_path, metadata)

        source = {
            key: value
            for key, value in loadmat(source_path, squeeze_me=False, struct_as_record=False).items()
            if not key.startswith("__")
        }
        source["formula_valid_code"] = np.asarray([[1.0]])
        source["paper_grid_eligible_code"] = np.asarray([[0.0]])
        with tempfile.TemporaryDirectory(prefix="fig10_historical_gate_") as temporary:
            clone = Path(temporary) / "legacy_gate_probe.mat"
            savemat(clone, source, do_compression=True, oned_as="column")
            clone_metadata = legacy_metadata(
                clone,
                route.dimension,
                route.source_contract_id,
                route.division,
                int(route.source_contract_id[-2:]),
            )
            with self.assertRaisesRegex(core.BlindContractError, "paper_grid_eligible_code不是1"):
                core.load_blind_bundle(clone, clone_metadata)

    def test_04_h05_h06_manifests_are_loadable_without_execution(self) -> None:
        for contract_id in ("H05", "H06"):
            with self.subTest(contract_id=contract_id):
                manifest_path = bridge.DEFAULT_OUTPUT_DIR / "manifests" / f"{contract_id}.json"
                manifest, _, _ = runner.load_manifest(manifest_path)
                self.assertEqual(manifest["evidence_level"], bridge.DIAGNOSTIC_STATUS)
                self.assertFalse(manifest["paper_formula_eligible"])
                self.assertFalse(manifest["paper_grid_eligible"])
                self.assertEqual(manifest["roots_computed"], 0)
                self.assertEqual(manifest["grid_points_computed"], 0)
                self.assertEqual(len(manifest["routes"]), 6)

    def test_05_two_independent_builds_are_byte_deterministic(self) -> None:
        first, _ = bridge.build_artifacts(self.repo_root)
        second, _ = bridge.build_artifacts(self.repo_root)
        self.assertEqual(set(first), set(second))
        hashes_first = {name: bridge.sha256_bytes(payload) for name, payload in first.items()}
        hashes_second = {name: bridge.sha256_bytes(payload) for name, payload in second.items()}
        self.assertEqual(hashes_first, hashes_second)

    def test_06_blind_core_formula_gate_file_is_unchanged(self) -> None:
        core_path = SCRIPT_DIR / "fig10_blind_core.py"
        self.assertEqual(sha256_file(core_path), EXPECTED_CORE_SHA256)
        generator_text = (SCRIPT_DIR / "build_historical_diagnostic_blind_bridge.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("strict_target_evaluator", generator_text)
        self.assertNotIn("solve_blind_point", generator_text)
        self.assertNotIn("build_minimal_augmented", generator_text)


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


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(HistoricalDiagnosticBridgeTests)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    bridge_manifest_path = bridge.DEFAULT_OUTPUT_DIR / "bridge_manifest.json"
    summary = {
        "schema_version": "FIG10_HISTORICAL_DIAGNOSTIC_BRIDGE_TEST_V1",
        "status": "PASS" if result.wasSuccessful() else "FAIL",
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "synthetic_stage0_covered": True,
        "real_stage0_routes_checked": 12,
        "legacy_formula_gate_direct_rejection_checked": True,
        "legacy_paper_grid_gate_rejection_checked": True,
        "native_manifests_loaded_without_execution": 2,
        "deterministic_two_build_hashes_checked": True,
        "blind_core_sha256": sha256_file(SCRIPT_DIR / "fig10_blind_core.py"),
        "bridge_manifest_sha256": sha256_file(bridge_manifest_path),
        "roots_computed": 0,
        "grid_points_computed": 0,
        "diagnostic_status": bridge.DIAGNOSTIC_STATUS,
    }
    atomic_write_json(EVALUATION_DIR / "test_summary.json", summary)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())

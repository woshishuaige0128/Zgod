#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""板块28合同层单元测试；不物化矩阵、不求根、不运行网格。"""

from __future__ import annotations

import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
BUILDER_PATH = SCRIPT_DIR / "build_fig10_candidate_bundles.py"


def load_builder() -> Any:
    spec = importlib.util.spec_from_file_location("fig10_contract_builder", BUILDER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("无法加载Fig10合同构建器")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def flatten_leaves(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key in sorted(value):
            child_prefix = f"{prefix}.{key}" if prefix else key
            result.update(flatten_leaves(value[key], child_prefix))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            child_prefix = f"{prefix}.{index}" if prefix else str(index)
            result.update(flatten_leaves(item, child_prefix))
        return result
    return {prefix: value}


def changed_leaf_paths(left: Any, right: Any) -> set[str]:
    flat_left = flatten_leaves(left)
    flat_right = flatten_leaves(right)
    return {
        key
        for key in set(flat_left) | set(flat_right)
        if flat_left.get(key) != flat_right.get(key)
    }


class Fig10ContractLayerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.builder = load_builder()
        cls.records, cls.registry, cls.sources = cls.builder.build_records()
        cls.by_id = {record["contract_id"]: record for record in cls.records}
        cls.known = cls.builder.realize_known_contracts(cls.registry)

    def test_01_schema_and_registry_are_valid_json(self) -> None:
        schema = json.loads(self.builder.SCHEMA_PATH.read_text(encoding="utf-8"))
        registry = json.loads(self.builder.KNOWN_REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(registry["registry_version"], "known-board20-contracts-v1")

    def test_02_known_board20_hashes_and_coverage_boundary(self) -> None:
        expected = {
            "R01": "32f5acb86035a5bd8756e146f7a47fc9746b8aa128549ca153249ffde5bbd80e",
            "R02": "22199257e8267581d2fa79962e00d2822ed68c896222929d25bdb669bea42918",
            "R03": "20e3d26326c590af155e0db5adc3e6ed2686c3e09136fa76869c53bb776130d0",
            "R04": "f7169d9be9bfdf6b1f7facc40fa1ce5bf5bf950d6dd30c820dc24c508938e8d5",
        }
        actual = {
            contract_id: self.builder.science_contract_sha256(science)
            for contract_id, science in self.known.items()
        }
        self.assertEqual(actual, expected)
        diagnostics = self.registry["non_fullgrid_diagnostics"]
        self.assertEqual([item["contract_id"] for item in diagnostics], ["R05", "R06"])
        self.assertTrue(
            all(item["coverage_status"] == "BUNDLES_BUILT_FULLGRID_POINTS_ZERO" for item in diagnostics)
        )

    def test_03_exact_record_set_and_no_search(self) -> None:
        self.assertEqual(list(self.by_id), ["B1", "B2", "B3", "R03_REUSE"])
        for contract_id in ("B1", "B2", "B3"):
            record = self.by_id[contract_id]
            self.assertEqual(record["record_kind"], "NEW_SKELETON")
            self.assertEqual(record["search_action"], "MATERIALIZE_LATER_NO_SEARCH")
            self.assertEqual(record["materialization_status"], "CONTRACT_ONLY_NOT_MATERIALIZED")
            self.assertIsNone(record["reuse_evidence"])
        reuse = self.by_id["R03_REUSE"]
        self.assertEqual(reuse["search_action"], "REUSE_EXISTING_NO_RERUN")
        self.assertEqual(reuse["route_bundle_plan"], [])

    def test_04_b1_only_changes_division2_channel_contract(self) -> None:
        changed = changed_leaf_paths(
            self.known["R03"], self.by_id["B1"]["scientific_contract"]
        )
        self.assertEqual(
            changed,
            {
                "actuation_and_delay_channels.division_2.coordinates.1",
                "actuation_and_delay_channels.division_2.local_selector_zero_based.1",
                "controller_channels.division_2.coordinates.1",
                "controller_channels.division_2.local_selector_zero_based.1",
            },
        )
        science = self.by_id["B1"]["scientific_contract"]
        self.assertEqual(science["actuation_and_delay_channels"]["division_2"]["coordinates"], ["psi1", "psi11"])
        self.assertEqual(science["controller_channels"]["division_2"]["local_selector_zero_based"], [0, 6])
        self.assertEqual(science["delay_and_feedback"]["feedback_placement"], "OUTSIDE_H")

    def test_05_b2_only_changes_feedback_placement_and_assembly_rule(self) -> None:
        changed = changed_leaf_paths(
            self.known["R03"], self.by_id["B2"]["scientific_contract"]
        )
        self.assertEqual(
            changed,
            {
                "delay_and_feedback.feedback_placement",
                "delay_and_feedback.feedback_formula",
                "delay_and_feedback.inside_bundle_rule",
            },
        )
        science = self.by_id["B2"]["scientific_contract"]
        self.assertEqual(science["actuation_and_delay_channels"]["division_2"]["coordinates"], ["psi1", "psi6"])
        self.assertEqual(science["delay_and_feedback"]["feedback_placement"], "INSIDE_H")

    def test_06_b3_is_union_of_b1_and_b2_changes(self) -> None:
        changed_b1 = changed_leaf_paths(
            self.known["R03"], self.by_id["B1"]["scientific_contract"]
        )
        changed_b2 = changed_leaf_paths(
            self.known["R03"], self.by_id["B2"]["scientific_contract"]
        )
        changed_b3 = changed_leaf_paths(
            self.known["R03"], self.by_id["B3"]["scientific_contract"]
        )
        self.assertEqual(changed_b3, changed_b1 | changed_b2)
        self.assertEqual(
            self.by_id["B3"]["evidence_level"],
            "ARTICLE_FORMULA_ON_BOARD20_MATRIX_PACKAGE_DIAGNOSTIC",
        )
        self.assertEqual(
            self.by_id["B3"]["scientific_contract"]["matrix_package"]["article_dimension_contract_status"],
            "BOARD20_NUMERIC_PACKAGE_IS_NOT_ARTICLE_6_AND_12_MODEL",
        )

    def test_07_new_contract_hashes_are_unique_and_not_r01_to_r04(self) -> None:
        known_hashes = {
            self.builder.science_contract_sha256(science) for science in self.known.values()
        }
        new_hashes = [self.by_id[key]["contract_hash"] for key in ("B1", "B2", "B3")]
        self.assertEqual(len(set(new_hashes)), 3)
        self.assertTrue(all(value not in known_hashes for value in new_hashes))
        self.assertEqual(
            self.by_id["R03_REUSE"]["contract_hash"],
            self.builder.science_contract_sha256(self.known["R03"]),
        )

    def test_08_route_level_reuse_plan_is_explicit(self) -> None:
        b1 = self.by_id["B1"]["route_bundle_plan"]
        b2 = self.by_id["B2"]["route_bundle_plan"]
        b3 = self.by_id["B3"]["route_bundle_plan"]
        self.assertEqual(
            sum(item["operator_action"] == "REUSE_EXISTING_R03_ROUTE" for item in b1),
            3,
        )
        self.assertEqual(
            sum(item["operator_action"] == "MATERIALIZE_LATER" for item in b1),
            3,
        )
        self.assertTrue(all(item["operator_action"] == "MATERIALIZE_LATER" for item in b2))
        self.assertEqual(
            sum(item["operator_action"] == "REUSE_B2_ROUTE_AFTER_MATERIALIZATION" for item in b3),
            3,
        )
        self.assertTrue(all(item["route_operator_sha256"] is None for item in b1 + b2 + b3))

    def test_09_r03_reuse_evidence_closes_six_bundles(self) -> None:
        evidence = self.by_id["R03_REUSE"]["reuse_evidence"]
        self.assertEqual(evidence["fullgrid_point_count"], 12462)
        self.assertEqual(evidence["rerun_policy"], "DO_NOT_RERUN_KNOWN_CONTRACT")
        bundles = evidence["route_bundles"]
        self.assertEqual(len(bundles), 6)
        self.assertEqual(
            {(item["division"], item["method"]) for item in bundles},
            {(division, method) for division in (1, 2) for method in self.builder.METHOD_ORDER},
        )
        self.assertTrue(all(item["overall_pass"] for item in bundles))

    def test_10_target_firewall_and_dependency_allowlist(self) -> None:
        forbidden_exact_names = (
            "plotted_data.mat",
            "fig10_stability_domain.pdf",
            "论文边界.csv",
            "目标边界.csv",
        )
        builder_text = BUILDER_PATH.read_text(encoding="utf-8").lower()
        output_text = json.dumps(self.records, ensure_ascii=False).lower()
        for forbidden in forbidden_exact_names:
            self.assertNotIn(forbidden.lower(), builder_text)
            self.assertNotIn(forbidden.lower(), output_text)
        self.assertNotIn("import numpy", builder_text)
        self.assertNotIn("import scipy", builder_text)
        self.assertNotIn("import matplotlib", builder_text)
        board20_root = (
            self.builder.find_repo_root()
            / "test"
            / "00_失败尝试与候选路线"
            / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
        ).resolve()
        for source_path in self.sources.values():
            source_path.resolve().relative_to(board20_root)

    def test_11_deterministic_double_generation(self) -> None:
        files_first, rows_first = self.builder.expected_output_files()
        files_second, rows_second = self.builder.expected_output_files()
        self.assertEqual(files_first, files_second)
        self.assertEqual(rows_first, rows_second)
        with tempfile.TemporaryDirectory(prefix="fig10_contract_a_") as first_dir, tempfile.TemporaryDirectory(
            prefix="fig10_contract_b_"
        ) as second_dir:
            first = Path(first_dir)
            second = Path(second_dir)
            self.builder.write_files_atomic(first, files_first)
            self.builder.write_files_atomic(second, files_second)
            for name in files_first:
                self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_12_unknown_or_missing_top_level_field_is_rejected(self) -> None:
        valid = copy.deepcopy(self.by_id["B1"])
        missing = copy.deepcopy(valid)
        missing.pop("notes")
        with self.assertRaises(self.builder.ContractError):
            self.builder.validate_record(missing)
        extra = copy.deepcopy(valid)
        extra["unexpected"] = True
        with self.assertRaises(self.builder.ContractError):
            self.builder.validate_record(extra)


if __name__ == "__main__":
    unittest.main(verbosity=2)

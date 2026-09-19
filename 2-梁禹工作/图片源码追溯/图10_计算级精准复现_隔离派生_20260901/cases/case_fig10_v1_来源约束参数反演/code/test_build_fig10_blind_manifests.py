#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""盲算清单桥的最小自测：只构造临时数值包和物化清单。"""

from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
from pathlib import Path


SCRIPT = Path(__file__).resolve().with_name("build_fig10_blind_manifests.py")
SPEC = importlib.util.spec_from_file_location("fig10_blind_manifest_builder", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
BUILDER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILDER)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def synthetic_source(repo_root: Path, gain: str) -> dict:
    assignments = []
    for contract_index, contract_id in enumerate(BUILDER.CONTRACTS, start=1):
        contract_hash = f"{contract_index:064x}"
        for division in (1, 2):
            for method in ("Original", "Craig_Bampton", "Guyan"):
                route_id = f"{contract_id}_D{division}_{method}"
                relative = Path("bundles") / f"{route_id}.mat"
                bundle = repo_root / relative
                bundle.parent.mkdir(parents=True, exist_ok=True)
                bundle.write_bytes((route_id + "\n").encode("ascii"))
                assignments.append(
                    {
                        "assignment_id": route_id,
                        "global_contract_id": contract_id,
                        "division": division,
                        "method": method,
                        "dimension": 4,
                        "gain_scale": gain,
                        "repo_relative_path": relative.as_posix(),
                        "artifact_sha256": BUILDER.sha256_file(bundle),
                        "assignment_action": "MATERIALIZE_NEW_ROUTE",
                        "source_route_id": route_id,
                        "effective_science_contract_sha256": contract_hash,
                        "route_operator_sha256": f"{contract_index + division:064x}",
                        "stage0_status": "PASS",
                    }
                )
    return {
        "status": "PASS_STAGE0_NUMERIC_MATERIALIZATION",
        "gain_parameter_contract": {
            "gain_scale_decimal": gain,
            "evidence_level": "TARGET_GUIDED_INFERRED_PARAMETER",
        },
        "counts": {
            "new_numeric_route_bundles": 18,
            "stage0_pass": 18,
            "stage0_fail": 0,
            "roots_computed": 0,
        },
        "route_assignments": assignments,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="fig10_blind_manifest_test_") as temporary:
        root = Path(temporary)
        repo_root = root / "repo"
        case_root = repo_root / "case"
        materialization_dir = (
            case_root
            / "data"
            / "numeric_bundles"
            / "gain_scale_0p375_target_guided_inferred"
        )
        materialization_dir.mkdir(parents=True)
        materialization = materialization_dir / "materialization_manifest.json"
        source = synthetic_source(repo_root, "0.375")
        materialization.write_bytes(BUILDER.canonical_bytes(source))

        expected_output = (
            case_root
            / "data"
            / "blind_manifests"
            / "gain_scale_0p375_target_guided_inferred"
        ).resolve()
        require(
            BUILDER.default_output_dir(case_root, materialization) == expected_output,
            "默认输出目录未跟随物化清单目录",
        )

        built_first = BUILDER.build_all(repo_root, materialization)
        built_second = BUILDER.build_all(repo_root, materialization)
        require(
            BUILDER.expected_outputs(built_first) == BUILDER.expected_outputs(built_second),
            "同一物化清单两次生成不确定",
        )
        for contract_id, manifest in built_first.items():
            require(manifest["gain_scale"] == 0.375, f"{contract_id}增益派生错误")
            require(
                manifest["run_id"]
                == f"FIG10_{contract_id}_GAIN_SCALE_0P375_TARGET_GUIDED_INFERRED",
                f"{contract_id}运行标识派生错误",
            )
            require(len(manifest["routes"]) == 6, f"{contract_id}路线数错误")

        inconsistent = copy.deepcopy(source)
        inconsistent["route_assignments"][0]["gain_scale"] = "0.5"
        materialization.write_bytes(BUILDER.canonical_bytes(inconsistent))
        try:
            BUILDER.build_all(repo_root, materialization)
        except BUILDER.ManifestError:
            inconsistent_rejected = True
        else:
            inconsistent_rejected = False
        require(inconsistent_rejected, "未拒绝路线与顶层不一致的gain_scale")

    result = {
        "status": "PASS",
        "tests": {
            "dynamic_gain_scale": True,
            "dynamic_run_id": True,
            "dynamic_default_output_dir": True,
            "deterministic_payloads": True,
            "inconsistent_route_gain_rejected": True,
        },
        "scientific_search_executed": False,
        "roots_computed": 0,
        "delay_grid_points_computed": 0,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

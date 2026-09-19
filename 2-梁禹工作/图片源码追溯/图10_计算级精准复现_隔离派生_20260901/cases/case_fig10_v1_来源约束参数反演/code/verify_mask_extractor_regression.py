#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""回归验证掩膜入口与旧 MATLAB bwboundaries 边界逐点一致。"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import strict_target_evaluator as evaluator


SCRIPT = Path(__file__).resolve()
REPOSITORY_ROOT = SCRIPT.parents[5]
BOARD20_ROOT = (
    REPOSITORY_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
)
PACKAGE_ROOT = (
    BOARD20_ROOT
    / "outputs"
    / "step8g_图4-4图4-5最终中文失败审计包"
    / "计算结果"
    / "候选掩膜与边界"
)


def read_old_boundary(path: Path) -> tuple[tuple[int, int], ...]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    orders = [int(row["point_order"]) for row in rows]
    if orders != list(range(1, len(rows) + 1)):
        raise ValueError(f"{path}: 旧边界 point_order 不连续")
    return tuple((int(row["x_index"]), int(row["y_index"])) for row in rows)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: verify_mask_extractor_regression.py OUTPUT_DIR")
    output_dir = Path(sys.argv[1]).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    entries = []
    old_boundary_paths: dict[str, Path] = {}
    for contract in evaluator.CURVE_CONTRACTS:
        figure_name = f"图{contract.figure_id}"
        base = f"{figure_name}_{contract.method}"
        mask_path = (
            PACKAGE_ROOT
            / "历史稳定掩膜31x67"
            / f"历史_{base}_共同网格稳定掩膜31x67.csv"
        )
        old_boundary_path = (
            PACKAGE_ROOT
            / "历史MATLAB边界"
            / f"历史_{base}_MATLAB可见开边界.csv"
        )
        if not mask_path.is_file() or not old_boundary_path.is_file():
            raise FileNotFoundError(f"回归输入缺失：{base}")
        entries.append(
            {
                "curve_id": contract.curve_id,
                "input_type": "mask_csv",
                "path": str(mask_path),
                "expected_shape": [31, 67],
                "boundary_mode": "matlab_bwboundaries_8_noholes_visible_open",
            }
        )
        old_boundary_paths[contract.curve_id] = old_boundary_path

    manifest_path = output_dir / "board20_historical_mask_manifest.json"
    evaluator.json_dump(
        manifest_path,
        {
            "schema_version": evaluator.MANIFEST_SCHEMA,
            "candidate_id": "BOARD20_HISTORICAL_MASK_EXTRACTOR_REGRESSION",
            "evidence_label": "掩膜提取器回归测试，不是当前计算复现",
            "curves": entries,
        },
    )
    evaluation_dir = output_dir / "target_evaluation"
    summary = evaluator.evaluate_manifest(
        manifest_path,
        evaluator.DEFAULT_TARGET,
        evaluation_dir,
        evaluator.DEFAULT_MATLAB,
    )

    rows = []
    for contract in evaluator.CURVE_CONTRACTS:
        extracted_path = (
            evaluation_dir / "mask_boundary_extraction" / f"{contract.curve_id}.csv"
        )
        extracted = evaluator.load_boundary_csv(
            extracted_path,
            {
                "columns": {
                    "point_order": "point_order",
                    "tau1_step": "tau1_step",
                    "tau2_step": "tau2_step",
                }
            },
            "mask_csv",
        ).points
        old_path = old_boundary_paths[contract.curve_id]
        old = read_old_boundary(old_path)
        rows.append(
            {
                "curve_id": contract.curve_id,
                "extracted_point_count": len(extracted),
                "old_matlab_point_count": len(old),
                "ordered_exact": extracted == old,
                "old_boundary_path": str(old_path),
                "old_boundary_sha256": evaluator.sha256(old_path),
                "extracted_boundary_path": str(extracted_path),
                "extracted_boundary_sha256": evaluator.sha256(extracted_path),
            }
        )

    curve_pass_ids = [
        row["curve_id"]
        for row in summary["curves"]
        if row["strict_curve_status"] == "PASS"
    ]
    checks = {
        "six_old_matlab_boundaries_reproduced_ordered_exact": (
            len(rows) == 6 and all(row["ordered_exact"] for row in rows)
        ),
        "historical_masks_do_not_false_pass_current_six_curve_target": (
            summary["overall_status"] == "FAIL"
        ),
        "only_two_original_curves_match_current_target": (
            curve_pass_ids == ["division1_original", "division2_original"]
        ),
        "matlab_process_exit_zero": (
            json.loads(
                (
                    evaluation_dir
                    / "mask_boundary_extraction"
                    / "matlab_process.json"
                ).read_text(encoding="utf-8")
            )["returncode"]
            == 0
        ),
    }
    regression = {
        "schema_version": "FIG10_MASK_EXTRACTOR_REGRESSION_V1",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "target_evaluation_overall_status_expected_fail": summary["overall_status"],
        "target_curve_pass_ids": curve_pass_ids,
        "rows": rows,
        "evaluator_sha256": evaluator.sha256(evaluator.SCRIPT),
        "matlab_helper_sha256": evaluator.sha256(
            evaluator.SCRIPT.parent / "fig10_extract_mask_boundaries.m"
        ),
    }
    evaluator.json_dump(output_dir / "mask_extractor_regression_summary.json", regression)
    evaluator.write_csv(
        output_dir / "mask_extractor_regression_curves.csv",
        (
            "curve_id",
            "extracted_point_count",
            "old_matlab_point_count",
            "ordered_exact",
            "old_boundary_path",
            "old_boundary_sha256",
            "extracted_boundary_path",
            "extracted_boundary_sha256",
        ),
        rows,
    )
    print(json.dumps(regression, ensure_ascii=False, indent=2))
    return 0 if regression["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

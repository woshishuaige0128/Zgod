from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
OUTPUT_ROOT = BOARD_ROOT / "outputs"
INPUT_MANIFEST_PATH = BOARD_ROOT / "input" / "input_manifest.csv"
REPORT_PATH = BOARD_ROOT / "report" / "板块20_最小步骤1_输入冻结与合同验收.md"
NOTE_PATH = PROJECT_ROOT / "Ref" / "notes" / "Liang2025_实时混合试验缩聚与稳定性.md"
CHECK_CSV = OUTPUT_ROOT / "step1_validation.csv"
CHECK_JSON = OUTPUT_ROOT / "step1_validation.json"
ARTIFACT_CSV = OUTPUT_ROOT / "step1_artifact_manifest.csv"

EXCLUDED_RELATIVE = {
    "outputs/step1_validation.csv",
    "outputs/step1_validation.json",
    "outputs/step1_artifact_manifest.csv",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def add(
    checks: list[dict[str, Any]],
    check: str,
    expected: Any,
    actual: Any,
    passed: bool,
    evidence: str,
) -> None:
    checks.append(
        {
            "check_id": f"S1-{len(checks) + 1:03d}",
            "check": check,
            "expected": json.dumps(expected, ensure_ascii=False, sort_keys=True),
            "actual": json.dumps(actual, ensure_ascii=False, sort_keys=True),
            "status": "PASS" if passed else "FAIL",
            "evidence": evidence,
        }
    )


def build_artifact_manifest() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(
        (candidate for candidate in BOARD_ROOT.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(BOARD_ROOT).as_posix().casefold(),
    ):
        relative = path.relative_to(BOARD_ROOT).as_posix()
        if relative in EXCLUDED_RELATIVE or "__pycache__" in path.parts:
            continue
        rows.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    with ARTIFACT_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return rows


def find_record(records: list[dict[str, Any]], suffix: str) -> dict[str, Any]:
    hits = [record for record in records if record["frozen_relative_path"].endswith(suffix)]
    if len(hits) != 1:
        raise RuntimeError(f"MLX合同记录不唯一：{suffix}; hits={len(hits)}")
    return hits[0]


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []

    freeze_summary_path = OUTPUT_ROOT / "input_freeze_summary.json"
    freeze_validation_path = OUTPUT_ROOT / "input_freeze_validation.json"
    mlx_contract_path = OUTPUT_ROOT / "mlx_contract.json"
    mat_identity_path = OUTPUT_ROOT / "mat_identity.json"
    required = [
        freeze_summary_path,
        freeze_validation_path,
        mlx_contract_path,
        mat_identity_path,
        INPUT_MANIFEST_PATH,
        REPORT_PATH,
        NOTE_PATH,
    ]
    missing = [str(path) for path in required if not path.is_file()]
    add(
        checks,
        "最小步骤1必需文件存在",
        [],
        missing,
        not missing,
        ";".join(str(path) for path in required),
    )
    if missing:
        raise FileNotFoundError("缺少步骤1必需文件：" + "; ".join(missing))

    freeze = load_json(freeze_summary_path)
    add(
        checks,
        "冻结源与副本",
        {"source_count": 185, "match_count": 185, "status": "PASS"},
        {key: freeze.get(key) for key in ("source_count", "match_count", "status")},
        freeze.get("source_count") == 185
        and freeze.get("match_count") == 185
        and freeze.get("status") == "PASS",
        str(freeze_summary_path),
    )
    add(
        checks,
        "冻结目的唯一且源不在板块目录",
        {"unique": 185, "inside": 0},
        {
            "unique": freeze.get("frozen_destination_unique_count"),
            "inside": freeze.get("source_inside_board_count"),
        },
        freeze.get("frozen_destination_unique_count") == 185
        and freeze.get("source_inside_board_count") == 0,
        str(freeze_summary_path),
    )
    with INPUT_MANIFEST_PATH.open("r", encoding="utf-8-sig", newline="") as stream:
        input_manifest_rows = list(csv.DictReader(stream))
    helper_rows = [
        row
        for row in input_manifest_rows
        if row["frozen_relative_path"]
        == "historical_upstream/新物理子结构方案/fcn_newmark_beta_const.m"
    ]
    helper_actual = {
        "count": len(helper_rows),
        "item_id": helper_rows[0]["item_id"] if len(helper_rows) == 1 else "",
        "source_sha256": helper_rows[0]["source_sha256"] if len(helper_rows) == 1 else "",
        "frozen_sha256": helper_rows[0]["frozen_sha256"] if len(helper_rows) == 1 else "",
        "status": helper_rows[0]["status"] if len(helper_rows) == 1 else "",
    }
    helper_expected = {
        "count": 1,
        "item_id": "B20-0185",
        "source_sha256": "0EE9605726A9FFC773F1DFEA1A6090F4AA35705D8F4BB8611E804D7D830689B0",
        "frozen_sha256": "0EE9605726A9FFC773F1DFEA1A6090F4AA35705D8F4BB8611E804D7D830689B0",
        "status": "MATCH",
    }
    add(
        checks,
        "稳定域New_Full真实外部依赖补冻",
        helper_expected,
        helper_actual,
        helper_actual == helper_expected,
        str(INPUT_MANIFEST_PATH),
    )
    add(
        checks,
        "论文保护哈希",
        {
            "thesis": "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1",
            "manuscript": "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76",
        },
        {
            "thesis": freeze.get("thesis_sha256"),
            "manuscript": freeze.get("manuscript_sha256"),
        },
        freeze.get("thesis_sha256")
        == "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
        and freeze.get("manuscript_sha256")
        == "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76",
        str(freeze_summary_path),
    )

    freeze_validation = load_json(freeze_validation_path)
    add(
        checks,
        "独立冻结总验收",
        {"passed": 533, "failed": 0, "pass": True},
        {
            "passed": freeze_validation.get("passed_checks"),
            "failed": freeze_validation.get("failed_checks"),
            "pass": freeze_validation.get("pass"),
        },
        freeze_validation.get("passed_checks") == 533
        and freeze_validation.get("failed_checks") == 0
        and freeze_validation.get("pass") is True,
        str(freeze_validation_path),
    )
    add(
        checks,
        "板块15保护源实时复核",
        326,
        freeze_validation.get("board15_live_protected_passed"),
        freeze_validation.get("board15_live_protected_passed") == 326,
        str(freeze_validation_path),
    )

    mlx = load_json(mlx_contract_path)
    records = mlx.get("records", [])
    add(
        checks,
        "冻结MLX代码合同数量",
        47,
        mlx.get("record_count"),
        mlx.get("record_count") == 47 and len(records) == 47,
        str(mlx_contract_path),
    )
    main_prefix = "historical_stability_route/稳定域/"
    outer_prefix = "plotting_baseline/第4章_缩聚对试验稳定性的影响/原始来源副本/"
    main_names = [
        "luxvjie_ori_LQR2.mlx",
        "luxvjie_ori_LQR3.mlx",
        "luxvjie_guyan_LQR2.mlx",
        "luxvjie_guyan_LQR3.mlx",
        "luxvjie_cb_LQR2.mlx",
        "luxvjie_cb_LQR3.mlx",
    ]
    pair_results: dict[str, bool] = {}
    for name in main_names:
        left = find_record(records, main_prefix + name)
        right = find_record(records, outer_prefix + name)
        pair_results[name] = (
            left["source_sha256"] == right["source_sha256"]
            and left["normalized_code_sha256"] == right["normalized_code_sha256"]
        )
    add(
        checks,
        "六份主MLX与外层副本代码身份",
        {name: True for name in main_names},
        pair_results,
        all(pair_results.values()),
        str(mlx_contract_path),
    )

    ori2 = find_record(records, main_prefix + "luxvjie_ori_LQR2.mlx")
    add(
        checks,
        "原结构LQR2真实执行合同",
        {"dlqr": False, "loops": [], "save": []},
        {
            "dlqr": ori2["has_dlqr_call"],
            "loops": ori2["loop_ranges"],
            "save": ori2["save_targets"],
        },
        not ori2["has_dlqr_call"]
        and not ori2["loop_ranges"]
        and not ori2["save_targets"],
        str(mlx_contract_path),
    )
    cb2 = find_record(records, main_prefix + "luxvjie_cb_LQR2.mlx")
    cb3 = find_record(records, main_prefix + "luxvjie_cb_LQR3.mlx")
    add(
        checks,
        "两份CB-LQR主脚本同字节且无LQR",
        {"same_sha": True, "dlqr2": False, "dlqr3": False, "status": ["error"]},
        {
            "same_sha": cb2["source_sha256"] == cb3["source_sha256"],
            "dlqr2": cb2["has_dlqr_call"],
            "dlqr3": cb3["has_dlqr_call"],
            "status2": cb2["embedded_output_status"],
            "status3": cb3["embedded_output_status"],
        },
        cb2["source_sha256"] == cb3["source_sha256"]
        and not cb2["has_dlqr_call"]
        and not cb3["has_dlqr_call"]
        and cb2["embedded_output_status"] == ["error"]
        and cb3["embedded_output_status"] == ["error"],
        str(mlx_contract_path),
    )
    expected_q = ["diag([1e6, 1, 1e5, 1])"]
    expected_r = ["diag([1e-1, 1e-2])"]
    main3_results: dict[str, bool] = {}
    for name in ("luxvjie_ori_LQR3.mlx", "luxvjie_guyan_LQR3.mlx"):
        record = find_record(records, main_prefix + name)
        main3_results[name] = (
            record["has_dlqr_call"]
            and record["q_literals"] == expected_q
            and record["r_literals"] == expected_r
            and record["save_targets"] == ["stab_guyan_lqr.mat"]
        )
    add(
        checks,
        "两份主LQR3的实际Q/R与保存名",
        {name: True for name in main3_results},
        main3_results,
        all(main3_results.values()),
        str(mlx_contract_path),
    )
    energy_results: dict[str, bool] = {}
    for name in ("luxvjie_guyan_LQR2.mlx", "luxvjie_guyan_LQR3.mlx"):
        record = find_record(records, "alternative_lqr_route/能量指标/" + name)
        energy_results[name] = (
            record["has_dlqr_call"]
            and record["q_literals"] == ["diag([4e8, 1e4, 1e2, 1e1])"]
            and record["r_literals"] == ["diag([3e-3,1e-2])"]
        )
    add(
        checks,
        "能量目录两份冲突LQR的Q/R",
        {name: True for name in energy_results},
        energy_results,
        all(energy_results.values()),
        str(mlx_contract_path),
    )

    mat = load_json(mat_identity_path)
    add(
        checks,
        "相关MAT身份与绘图链",
        {"mats": 17, "variables": 53, "chain": "39/39", "status": "PASS"},
        {
            "mats": mat.get("relevant_mat_count"),
            "variables": mat.get("variable_count"),
            "chain": f"{mat.get('plotting_chain_passed')}/{mat.get('plotting_chain_checked')}",
            "status": mat.get("status"),
        },
        mat.get("relevant_mat_count") == 17
        and mat.get("variable_count") == 53
        and mat.get("plotting_chain_passed") == 39
        and mat.get("plotting_chain_checked") == 39
        and mat.get("status") == "PASS",
        str(mat_identity_path),
    )
    points2 = mat["final_mask_summary"]["lqr_2"]
    points3 = mat["final_mask_summary"]["lqr_3"]
    actual_points = [
        points2["stab_o"]["stable_points_0_lt_x_lt_1"],
        points2["stab_C"]["stable_points_0_lt_x_lt_1"],
        points2["stab_g"]["stable_points_0_lt_x_lt_1"],
        points3["stab_o"]["stable_points_common_31x67"],
        points3["stab_C"]["stable_points_common_31x67"],
        points3["stab_g"]["stable_points_common_31x67"],
    ]
    add(
        checks,
        "六个最终历史掩膜稳定点数",
        [1454, 1175, 1044, 1247, 1072, 929],
        actual_points,
        actual_points == [1454, 1175, 1044, 1247, 1072, 929],
        str(mat_identity_path),
    )
    anomalies = mat["anomalies"]
    anomalies_pass = (
        anomalies["stab_C_row36_cols68_95_is_1_to_28"] is True
        and anomalies["stab_g_row32_cols68_95_is_1_to_28"] is True
        and anomalies["stab_C_outside_common_grid_between_zero_one_count"] == 0
        and anomalies["stab_g_outside_common_grid_between_zero_one_count"] == 0
    )
    add(
        checks,
        "第二类共同网格外异常序列",
        "两段1..28且网格外0<x<1点数为0",
        anomalies,
        anomalies_pass,
        str(mat_identity_path),
    )
    add(
        checks,
        "连续极点候选不能认领最终掩膜",
        284,
        mat.get("minimum_continuous_candidate_mismatch_points"),
        mat.get("minimum_continuous_candidate_mismatch_points") == 284,
        str(mat_identity_path),
    )

    note_text = NOTE_PATH.read_text(encoding="utf-8")
    note_markers = [
        "2026-08-25原页视觉校正",
        "把硕士论文式(4-38)至式(4-40)中LQR项的时滞位置记反",
        "板块20图4-4、图4-5与LQR稳定域原页复核",
        "板块20首次冻结共184项",
        "板块20补充冻结后共185项",
    ]
    add(
        checks,
        "文献精读笔记包含原页校正和板块20留痕",
        note_markers,
        [marker for marker in note_markers if marker in note_text],
        all(marker in note_text for marker in note_markers),
        str(NOTE_PATH),
    )
    report_text = REPORT_PATH.read_text(encoding="utf-8")
    report_markers = [
        "185/185个SHA-256一致",
        "533/533项通过",
        "39/39项PASS",
        "最佳结果仍差284点",
        "绘图级复现",
        "计算级复现",
        "历史值",
        "待决定",
    ]
    add(
        checks,
        "步骤1报告自包含且证据等级齐全",
        report_markers,
        [marker for marker in report_markers if marker in report_text],
        all(marker in report_text for marker in report_markers),
        str(REPORT_PATH),
    )

    success_directories = [
        PROJECT_ROOT / "test" / "图4-4_第一类子结构划分稳定域",
        PROJECT_ROOT / "test" / "图4-5_第二类子结构划分稳定域",
        PROJECT_ROOT / "test" / "结论C05_两类划分的稳定裕度下降量",
        PROJECT_ROOT / "test" / "结论C07_结论章频率区间、误差幅值与临界时滞总结",
    ]
    existing_success = [str(path) for path in success_directories if path.exists()]
    add(
        checks,
        "步骤1不得提前建立正式成功目录",
        [],
        existing_success,
        not existing_success,
        ";".join(str(path) for path in success_directories),
    )

    artifacts = build_artifact_manifest()
    artifact_errors: list[str] = []
    for row in artifacts:
        path = BOARD_ROOT / row["relative_path"]
        if (
            not path.is_file()
            or path.stat().st_size != row["size_bytes"]
            or sha256_file(path) != row["sha256"]
        ):
            artifact_errors.append(row["relative_path"])
    add(
        checks,
        "步骤1工件清单即时复核",
        {"errors": []},
        {"artifact_count": len(artifacts), "errors": artifact_errors},
        not artifact_errors,
        str(ARTIFACT_CSV),
    )

    failed = [check for check in checks if check["status"] == "FAIL"]
    with CHECK_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(checks[0].keys()))
        writer.writeheader()
        writer.writerows(checks)
    summary = {
        "schema": "board20_step1_validation_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "checks": len(checks),
        "passed": len(checks) - len(failed),
        "failed": len(failed),
        "artifact_count": len(artifacts),
        "artifact_manifest_sha256": sha256_file(ARTIFACT_CSV),
        "failures": failed,
        "status": "PASS" if not failed else "FAIL",
    }
    CHECK_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"BOARD20_STEP1_{summary['status']} "
        f"checks={summary['passed']}/{summary['checks']} artifacts={len(artifacts)}"
    )
    print(f"CSV={CHECK_CSV}")
    print(f"JSON={CHECK_JSON}")
    print(f"MANIFEST={ARTIFACT_CSV}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

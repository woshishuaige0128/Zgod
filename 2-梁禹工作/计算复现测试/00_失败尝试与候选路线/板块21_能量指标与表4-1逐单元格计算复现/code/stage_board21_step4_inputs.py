from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import stat
import sys
from pathlib import Path, PurePosixPath
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
STEP3_ROOT = BOARD_ROOT / "outputs" / "step3_runs"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "s4i"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"
BOARD17_FROZEN_MANIFEST = (
    BOARD_ROOT / "input" / "upstream_passport" / "board17_artifact_manifest.csv"
)
BOARD17_FROZEN_SUMMARY = (
    BOARD_ROOT / "input" / "upstream_passport" / "board17_validation_summary.json"
)

INPUT_MANIFEST_SHA256 = "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
INPUT_FREEZE_SUMMARY_SHA256 = "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"
BOARD17_FROZEN_MANIFEST_SHA256 = "43C29665D0E08EF4FFB8D9067B38F797797735EA382E7F5B004EA2637A787405"
BOARD17_FROZEN_SUMMARY_SHA256 = "AE580B5A25F89F68E257DADB0F243962F634248C035864EBC8F681C083AEBF4A"

UPSTREAM_ANCHORS = {
    "outputs/step2_static_inventory/inventory_summary.json": "C587F4FA80E56512C7734D545A20BE483EADC5E09B5707A6D241ACBADE2A7D1C",
    "outputs/step2_validation/checks.csv": "0207D7AAFC16BDCAC4298E387668DAABB143300F92927FDD4C6CABDBEDA13EF9",
    "outputs/step2_validation/step2_artifact_manifest.csv": "4BCD18ADB8321123ACFF53E30C0B5F02D5ED05C16181E7BAA829743831C5B9F9",
    "outputs/step2_determinism/determinism_audit.json": "9CD0C07D7956E4CC5F0ECC1956EAD54A21B9DD2AD3371F769DA6ED1D06CEED38",
    "report/板块21_最小步骤2_公式与历史脚本静态审计.md": "7E642186B735E73B13547D10073AEE4B66146A7157860C1157F120165406B2DF",
    "outputs/step3_stage/stage_summary.json": "F0F44C7C7128D2AC6DF88BFD5C0FF9367211B95DBF54EC32C145CB167986D238",
    "outputs/step3_stage/run_configs.csv": "D70D2D6F20C77BA6C709A7AED3BD2CE46B60165F8AB9516C15E2979F3AD87BFF",
    "outputs/step3_stage/staged_input_manifest.csv": "6DEA6F89A367C4684D34FECA7EC8F5D28CF606BA753830B9AEB0E403382B94EE",
    "outputs/step3_orchestration/run_all_summary.json": "03A2FA963E685259C0692733D536231C60B5FD1FFB514BDC297980377619DA44",
    "outputs/step3_validation/checks.csv": "1E0A0D715809A06B3E33BD2A73EAA8471D157B53F1277DD6D0C8F4D7DCC28236",
    "outputs/step3_validation/route_results.csv": "007CED89C2E109F0095E375808FC4547759AB0F9537ED54D955B734ADBB6DAC6",
    "outputs/step3_validation/repeat_comparison.csv": "230886D9378816E0B7BB14B7DB489A2C536F4EE82025E18EC7DA67F13188D48D",
    "outputs/step3_validation/validation_summary.json": "09CCF3FF1C1EA8E45C4B0FF30ADF1827FAB4F5AC966C3A680302E64F76EBB897",
}

SOURCE_ROLES = (
    ("run_config", "metadata/run_config.json", "cfg.json"),
    ("run_config_sha256", "metadata/run_config.sha256", "cfg.sha256"),
    ("run_status", "metadata/run_status.json", "status.json"),
    ("process_exit", "metadata/process_exit.json", "exit.json"),
    ("variable_inventory", "metadata/variable_inventory.json", "vars.json"),
    ("workspace_after_upstream", "workspace/workspace_after_upstream.mat", "u.mat"),
    ("historical_energy_outputs", "scientific/historical_energy_outputs.mat", "h.mat"),
)

ROUTES: tuple[dict[str, Any], ...] = (
    {
        "alias": "r01",
        "route_id": "reference15_pd19_energy",
        "route_label_cn": "旧15自由度参考体系：PD参数族1.9→energy_zonghe",
        "division_identity": "旧15自由度水平主坐标参考体系；不绑定表4-1两类整体划分",
        "parameter_family": "rho=785e3.*1.9",
        "full_M": "MRrt", "full_K": "KRrt",
        "guyan_M": "MRren", "guyan_K": "KRren", "guyan_T": "T",
        "cb_M": "MR_cb", "cb_K": "KR_cb", "cb_T": "T_cb",
        "consumer_order": [1, 6, 11, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15],
        "producer_order": [1, 6, 11, 2, 3, 4, 5, 7, 8, 9, 10, 12, 13, 14, 15],
        "d_orig": [1, 2, 3], "d_guyan": [1, 2, 3], "d_cb": [1, 2, 3],
        "excitation_rule": "BINARY_FIRST_3",
        "energy_normalized": True,
        "orig_sum_scope": "SELECTED", "guyan_sum_scope": "ALL", "cb_sum_scope": "SELECTED",
        "historical_denominator": "ORIGINAL",
        "coordinate_status": "PASS",
    },
    {
        "alias": "r02",
        "route_id": "division1_pd19_copy",
        "route_label_cn": "第一类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MRren", "guyan_K": "KRren", "guyan_T": "T",
        "cb_M": "MR_cb", "cb_K": "KR_cb", "cb_T": "T_cb",
        "consumer_order": [1, 4, 2, 3, 5, 6], "producer_order": [1, 4, 2, 3, 5, 6],
        "d_orig": [1, 2], "d_guyan": [1, 2], "d_cb": [1, 2],
        "excitation_rule": "BINARY_FIRST_2",
        "energy_normalized": True,
        "orig_sum_scope": "SELECTED", "guyan_sum_scope": "ALL", "cb_sum_scope": "SELECTED",
        "historical_denominator": "ORIGINAL",
        "coordinate_status": "PASS",
    },
    {
        "alias": "r03",
        "route_id": "division1_tp17_energy",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer_order": [1, 4, 2, 3, 5, 6], "producer_order": [1, 4, 2, 3, 5, 6],
        "d_orig": [1, 2], "d_guyan": [1, 2], "d_cb": [1, 2],
        "excitation_rule": "MASS_TIMES_ONES",
        "energy_normalized": True,
        "orig_sum_scope": "SELECTED", "guyan_sum_scope": "ALL", "cb_sum_scope": "SELECTED",
        "historical_denominator": "ORIGINAL",
        "coordinate_status": "PASS_WITH_INPUT_IDENTITY_UNRESOLVED",
    },
    {
        "alias": "r04",
        "route_id": "division1_tp17_copy2_formula_invalid",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→Copy_2错误公式",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer_order": [1, 4, 2, 3, 5, 6], "producer_order": [1, 4, 2, 3, 5, 6],
        "d_orig": [1, 2], "d_guyan": [1, 2], "d_cb": [1, 2],
        "excitation_rule": "MASS_TIMES_ONES",
        "energy_normalized": False,
        "orig_sum_scope": "ALL", "guyan_sum_scope": "ALL", "cb_sum_scope": "ALL",
        "historical_denominator": "GUYAN",
        "coordinate_status": "PASS_WITH_INPUT_IDENTITY_UNRESOLVED",
    },
    {
        "alias": "r05",
        "route_id": "division2_pd19_copy",
        "route_label_cn": "第二类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe3",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MRren", "guyan_K": "KRren", "guyan_T": "T",
        "cb_M": "MR_cb", "cb_K": "KR_cb", "cb_T": "T_cb",
        "consumer_order": [1, 7, 4, 2, 3, 5, 6, 8, 9],
        "producer_order": [1, 7, 4, 2, 3, 5, 6, 8, 9],
        "d_orig": [1, 2], "d_guyan": [1, 2], "d_cb": [1, 2],
        "excitation_rule": "BINARY_FIRST_3",
        "energy_normalized": True,
        "orig_sum_scope": "SELECTED", "guyan_sum_scope": "ALL", "cb_sum_scope": "SELECTED",
        "historical_denominator": "ORIGINAL",
        "coordinate_status": "PASS",
    },
    {
        "alias": "r06",
        "route_id": "division2_tp17_energy_coordinate_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→energy_zonghe3（坐标顺序冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer_order": [1, 7, 4, 2, 3, 5, 6, 8, 9],
        "producer_order": [1, 7, 2, 3, 4, 5, 6, 8, 9],
        "d_orig": [1, 2], "d_guyan": [1, 2], "d_cb": [1, 2],
        "excitation_rule": "BINARY_FIRST_3",
        "energy_normalized": True,
        "orig_sum_scope": "SELECTED", "guyan_sum_scope": "ALL", "cb_sum_scope": "SELECTED",
        "historical_denominator": "ORIGINAL",
        "coordinate_status": "COORDINATE_ORDER_CONFLICT",
    },
    {
        "alias": "r07",
        "route_id": "division2_tp17_copy2_coordinate_formula_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→Copy_2（坐标与公式冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "full_M": "MPrt", "full_K": "KPrt",
        "guyan_M": "MPren", "guyan_K": "KPren", "guyan_T": "TP",
        "cb_M": "MP_cb", "cb_K": "KP_cb", "cb_T": "TP_cb",
        "consumer_order": [1, 7, 4, 2, 3, 5, 6, 8, 9],
        "producer_order": [1, 7, 2, 3, 4, 5, 6, 8, 9],
        "d_orig": [1, 2], "d_guyan": [1, 2], "d_cb": [1, 2],
        "excitation_rule": "BINARY_FIRST_3",
        "energy_normalized": False,
        "orig_sum_scope": "SELECTED", "guyan_sum_scope": "ALL", "cb_sum_scope": "SELECTED",
        "historical_denominator": "GUYAN",
        "coordinate_status": "COORDINATE_ORDER_AND_FORMULA_CONFLICT",
    },
)

GLOBAL_SOURCES = (
    (
        "global_routes_matlab",
        "test/00_失败尝试与候选路线/板块17_两类划分与缩聚候选路线/outputs/global_routes_matlab.mat",
        "g/gr.mat",
        "A58A830134259585ECD091BA37B3A69640E79D3AA10B5094E106F2EC01ED56ED",
    ),
    (
        "global_reduced_matrix_entries",
        "test/00_失败尝试与候选路线/板块17_两类划分与缩聚候选路线/outputs/global_reduced_matrix_entries.csv",
        "g/gm.csv",
        "EF688B4C6DF630DAF25CBB28A480EB93606901E73C47D8BF428135074EC613D5",
    ),
    (
        "global_recovery_matrices",
        "test/00_失败尝试与候选路线/板块17_两类划分与缩聚候选路线/outputs/global_recovery_matrices.csv",
        "g/gt.csv",
        "1E26A8C62986415B6F3B6BE779E0D39000C1F889C91B25C7864B1BD1DAEA4A80",
    ),
    (
        "global_input_projection",
        "test/00_失败尝试与候选路线/板块17_两类划分与缩聚候选路线/outputs/global_input_projection.csv",
        "g/gi.csv",
        "30B412F9DD862949B8CAD062E5E940AB3EF1F1106EDC90B3C027E10966E016E0",
    ),
    (
        "global_route_summary",
        "test/00_失败尝试与候选路线/板块17_两类划分与缩聚候选路线/outputs/global_route_summary.json",
        "g/gs.json",
        "833FFCB4D0986292F53F2EACD699FF99918020A8CBFD134AB06B930D5FBAB579",
    ),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def utf16_units(path: Path) -> int:
    return len(str(path).encode("utf-16-le")) // 2


def is_reparse(path: Path) -> bool:
    info = path.lstat()
    attrs = getattr(info, "st_file_attributes", 0)
    return path.is_symlink() or bool(attrs & stat.FILE_ATTRIBUTE_REPARSE_POINT)


def require_plain_file(path: Path) -> None:
    if not path.is_absolute() or not path.is_file() or is_reparse(path):
        raise RuntimeError(f"not a plain absolute file: {path}")


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def write_csv_new(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def verify_anchor(path: Path, expected: str) -> None:
    require_plain_file(path)
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(f"anchor mismatch: {path}: {actual} != {expected}")


def board17_manifest_map() -> dict[str, tuple[int, str]]:
    verify_anchor(BOARD17_FROZEN_MANIFEST, BOARD17_FROZEN_MANIFEST_SHA256)
    verify_anchor(BOARD17_FROZEN_SUMMARY, BOARD17_FROZEN_SUMMARY_SHA256)
    summary = json.loads(BOARD17_FROZEN_SUMMARY.read_text(encoding="utf-8"))
    if summary.get("pass") is not True or summary.get("check_count") != 59 or summary.get("pass_count") != 59:
        raise RuntimeError("Board17 validation summary is not the sealed 59/59 PASS state")
    result: dict[str, tuple[int, str]] = {}
    with BOARD17_FROZEN_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            relative = PurePosixPath(row["relative_path"]).as_posix()
            result[relative] = (int(row["size_bytes"]), row["sha256"])
    if len(result) != 305:
        raise RuntimeError(f"Board17 artifact manifest cardinality mismatch: {len(result)}")
    return result


def copy_one(
    *, item_id: str, category: str, case_id: str, role: str, source: Path,
    target: Path, binding: str, expected_hash: str | None = None,
    expected_size: int | None = None,
) -> dict[str, Any]:
    require_plain_file(source)
    if utf16_units(target) > 220:
        raise RuntimeError(f"projected path exceeds 220 UTF-16 code units: {target}")
    source_hash = sha256_file(source)
    source_size = source.stat().st_size
    if expected_hash is not None and source_hash != expected_hash:
        raise RuntimeError(f"source hash mismatch for {source}")
    if expected_size is not None and source_size != expected_size:
        raise RuntimeError(f"source size mismatch for {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(target)
    shutil.copyfile(source, target)
    if sha256_file(target) != source_hash or target.stat().st_size != source_size:
        raise RuntimeError(f"copy verification failed: {target}")
    return {
        "item_id": item_id,
        "category": category,
        "case_id": case_id,
        "role": role,
        "source_absolute_path": str(source),
        "staged_relative_path": target.relative_to(OUTPUT_ROOT).as_posix(),
        "size_bytes": source_size,
        "sha256": source_hash,
        "binding": binding,
        "status": "MATCH",
    }


def main() -> int:
    if OUTPUT_ROOT.exists():
        raise FileExistsError(f"exclusive staging target already exists: {OUTPUT_ROOT}")
    verify_anchor(INPUT_MANIFEST, INPUT_MANIFEST_SHA256)
    verify_anchor(INPUT_FREEZE_SUMMARY, INPUT_FREEZE_SUMMARY_SHA256)
    freeze = json.loads(INPUT_FREEZE_SUMMARY.read_text(encoding="utf-8"))
    if freeze.get("status") != "PASS" or freeze.get("input_count") != 53:
        raise RuntimeError("Step1 freeze summary is not the sealed 53/53 PASS state")
    for relative, expected in UPSTREAM_ANCHORS.items():
        verify_anchor(BOARD_ROOT / PurePosixPath(relative), expected)
    b17_manifest = board17_manifest_map()

    OUTPUT_ROOT.mkdir(parents=True)
    manifest_rows: list[dict[str, Any]] = []
    case_rows: list[dict[str, Any]] = []
    item_number = 0

    for route in ROUTES:
        for rep_number, replicate in enumerate(("rep01", "rep02"), start=1):
            case_id = f"{route['alias']}_p{rep_number}"
            source_root = STEP3_ROOT / route["route_id"] / replicate
            target_root = OUTPUT_ROOT / route["alias"] / f"p{rep_number}"
            for role, source_relative, target_name in SOURCE_ROLES:
                item_number += 1
                manifest_rows.append(
                    copy_one(
                        item_id=f"S4I-{item_number:04d}",
                        category="step3_run_evidence",
                        case_id=case_id,
                        role=role,
                        source=(source_root / PurePosixPath(source_relative)).resolve(),
                        target=target_root / target_name,
                        binding="STEP3_FORMAL_RUN_CURRENT_HASH_AND_TOP_LEVEL_SEALS",
                    )
                )
            status = json.loads((target_root / "status.json").read_text(encoding="utf-8"))
            exit_record = json.loads((target_root / "exit.json").read_text(encoding="utf-8"))
            config = json.loads((target_root / "cfg.json").read_text(encoding="utf-8"))
            cfg_hash_text = (target_root / "cfg.sha256").read_text(encoding="ascii").strip().upper()
            if (
                status.get("route_id") != route["route_id"]
                or status.get("replicate") != replicate
                or status.get("execution_status") != "EXECUTION_SUCCESS"
                or status.get("evidence_status") != "PASS"
                or status.get("current_stage") != "COMPLETE"
                or exit_record.get("orchestration_status") != "SUCCESS_EVIDENCE_CAPTURED"
                or exit_record.get("returncode") != 0
                or exit_record.get("status_contract_pass") is not True
                or config.get("route_id") != route["route_id"]
                or config.get("replicate") != replicate
                or cfg_hash_text != sha256_file(target_root / "cfg.json")
            ):
                raise RuntimeError(f"Step3 case terminal contract failed: {case_id}")
            case_contract = dict(route)
            case_contract.update(
                {
                    "schema_version": "BOARD21_STEP4_CASE_V1",
                    "case_id": case_id,
                    "replicate": replicate,
                    "staged_relative_dir": target_root.relative_to(OUTPUT_ROOT).as_posix(),
                    "workspace_file": "u.mat",
                    "historical_target_file": "h.mat",
                    "result_boundaries": [
                        "AUTHOR_ROUTE_REPRODUCED",
                        "PAPER_LITERAL_CONDITIONAL",
                        "TABLE4_1_NOT_ADJUDICATED",
                    ],
                }
            )
            write_json_new(target_root / "case.json", case_contract)
            case_rows.append(
                {
                    "case_id": case_id,
                    "route_alias": route["alias"],
                    "route_id": route["route_id"],
                    "replicate": replicate,
                    "staged_relative_dir": target_root.relative_to(OUTPUT_ROOT).as_posix(),
                    "coordinate_status": route["coordinate_status"],
                    "formula_status": "HISTORICAL_ERROR" if not route["energy_normalized"] else "HISTORICAL_NON_EQ445",
                }
            )

    for role, source_relative, target_relative, expected_hash in GLOBAL_SOURCES:
        item_number += 1
        manifest_entry = b17_manifest.get(source_relative)
        if manifest_entry is None:
            raise RuntimeError(f"Board17 frozen manifest does not bind: {source_relative}")
        expected_size, manifest_hash = manifest_entry
        if manifest_hash != expected_hash:
            raise RuntimeError(f"Board17 manifest hash contract mismatch: {source_relative}")
        manifest_rows.append(
            copy_one(
                item_id=f"S4I-{item_number:04d}",
                category="board17_whole_model_existing_candidate",
                case_id="whole_model_existing_candidate",
                role=role,
                source=(PROJECT_ROOT / PurePosixPath(source_relative)).resolve(),
                target=OUTPUT_ROOT / PurePosixPath(target_relative),
                binding="BOARD17_CALCULATION_LEVEL_EXTERNAL_ASSET_INDIRECTLY_PASSPORT_BOUND_CURRENT_HASH_MATCH",
                expected_hash=expected_hash,
                expected_size=expected_size,
            )
        )

    if item_number != 103 or len(manifest_rows) != 103 or len(case_rows) != 14:
        raise RuntimeError("Step4 staging cardinality contract failed")
    fields = [
        "item_id", "category", "case_id", "role", "source_absolute_path",
        "staged_relative_path", "size_bytes", "sha256", "binding", "status",
    ]
    write_csv_new(OUTPUT_ROOT / "input_manifest.csv", manifest_rows, fields)
    write_csv_new(
        OUTPUT_ROOT / "case_index.csv",
        case_rows,
        [
            "case_id", "route_alias", "route_id", "replicate",
            "staged_relative_dir", "coordinate_status", "formula_status",
        ],
    )
    global_contract = {
        "schema_version": "BOARD21_STEP4_GLOBAL_INPUT_V1",
        "asset_status": "BOARD17_CALCULATION_LEVEL_EXTERNAL_ASSET_INDIRECTLY_PASSPORT_BOUND_CURRENT_HASH_MATCH",
        "whole_model_candidates": [
            {
                "division": 1,
                "order": [1, 6, 11, 4, 9, 14, 2, 3, 5, 7, 8, 10, 12, 13, 15],
                "guyan_dimensions": [15, 6],
                "cb_dimensions": [15, 9],
                "n_cb_fixed_interface_modes": 3,
            },
            {
                "division": 2,
                "order": [1, 11, 4, 9, 14, 6, 2, 3, 5, 7, 8, 10, 12, 13, 15],
                "guyan_dimensions": [15, 5],
                "cb_dimensions": [15, 8],
                "n_cb_fixed_interface_modes": 3,
            },
        ],
        "scientific_boundaries": [
            "WHOLE_MODEL_EXISTING_CANDIDATE",
            "LOCAL_NUMERICAL_SUBSTRUCTURE_12D_PENDING",
            "TABLE4_1_NOT_ADJUDICATED",
        ],
    }
    write_json_new(OUTPUT_ROOT / "global_contract.json", global_contract)
    summary = {
        "schema_version": "BOARD21_STEP4_INPUT_STAGE_V1",
        "status": "PASS",
        "step3_run_case_count": 14,
        "step3_evidence_item_count": 98,
        "board17_external_candidate_item_count": 5,
        "total_manifest_item_count": 103,
        "case_contract_count": 14,
        "step1_direct_freeze_count": 53,
        "global_asset_directly_frozen_by_board21_step1": False,
        "global_asset_binding": "BOARD17_CALCULATION_LEVEL_EXTERNAL_ASSET_INDIRECTLY_PASSPORT_BOUND_CURRENT_HASH_MATCH",
        "formula_4_45_evaluated": False,
        "table4_1_adjudicated": False,
    }
    write_json_new(OUTPUT_ROOT / "staging_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(json.dumps({"status": "FAIL", "error": f"{type(error).__name__}: {error}"}, ensure_ascii=False, sort_keys=True))
        raise

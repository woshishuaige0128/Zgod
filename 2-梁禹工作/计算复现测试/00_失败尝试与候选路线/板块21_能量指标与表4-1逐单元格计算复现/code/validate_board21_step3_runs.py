from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import subprocess
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

import h5py
import numpy as np


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
AUTHOR_ROOT = BOARD_ROOT / "input" / "author_energy"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"
TMP_ROOT = BOARD_ROOT / "tmp" / "step3_runs"
STAGE_ROOT = BOARD_ROOT / "outputs" / "step3_stage"
RUN_ROOT = BOARD_ROOT / "outputs" / "step3_runs"
LOG_ROOT = BOARD_ROOT / "logs" / "step3_runs"
ORCHESTRATION_ROOT = BOARD_ROOT / "outputs" / "step3_orchestration"
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "step3_validation"
ATTEMPT01_ROOT = (
    BOARD_ROOT
    / "attempts"
    / "step3_attempt01_20260826_pid_contract_failure"
)
ATTEMPT02_ROOT = BOARD_ROOT / "attempts" / "a02"
EXPECTED_PYTHON = Path(r"D:\Software\python\python.exe")
EXPECTED_MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
REPLICATES = ("rep01", "rep02")
INPUT_MANIFEST_SHA256 = (
    "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
)
INPUT_FREEZE_SUMMARY_SHA256 = (
    "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"
)
EXPECTED_INPUT_CATEGORY_COUNTS = {
    "author_energy_tree": 36,
    "central_baseline": 3,
    "manuscript": 1,
    "prior_audit": 2,
    "stability_evidence": 2,
    "theory": 1,
    "upstream_candidate": 1,
    "upstream_passport": 7,
}
INSTRUMENT_FILES = {
    "stage_board21_step3_runs.py",
    "run_one_board21_energy_route.m",
    "execute_board21_step3_route.py",
    "run_board21_step3_all.py",
    "validate_board21_step3_runs.py",
}
INSTRUMENT_ORDER = (
    "stage_board21_step3_runs.py",
    "run_one_board21_energy_route.m",
    "execute_board21_step3_route.py",
    "run_board21_step3_all.py",
    "validate_board21_step3_runs.py",
)
ATTEMPT01_METADATA_SHA256 = {
    "attempt_summary.json": (
        "E37B68D9994811CD4D2CCE1D42268A42261DCBD455087E05370FC5DFB55641F4"
    ),
    "attempt_file_manifest.csv": (
        "36A47CD37275E2B5F69413B550C35E45FE58933466C35B6BD1BF9A9ED4F87688"
    ),
    "tool_snapshot_manifest.csv": (
        "D4532DD99C7DFB99BC2D4F1B1D6A9749C63F7F52D5555FE9B6FFBC2E66CF21CF"
    ),
}
ATTEMPT01_TOOL_SHA256 = {
    "stage_board21_step3_runs.py": (
        "9DEE64A057A82343227C2F49B23BEECB5A5AF076877CB2A54B478FCFAE769AA1"
    ),
    "run_one_board21_energy_route.m": (
        "8363F5BCE4139AF24174B63A6EDE71006E0D5EFFA057EFFC592A2BA14B654DF7"
    ),
    "execute_board21_step3_route.py": (
        "1FE62446A444C41409C21409AE40E773E73E105082DCE02BC197B5C67D6BEA53"
    ),
    "run_board21_step3_all.py": (
        "F80F3F5375679BDD912A204ED5AFE6DD1F45D7F401F7D06F5A852571D489C930"
    ),
    "validate_board21_step3_runs.py": (
        "A37138D25E45FD10F8B674FDB5C46785F188C9B248B85322B0FBBD90EF8A0183"
    ),
}
ATTEMPT01_LOGICAL_ROOTS = {
    "outputs_step3_stage": ATTEMPT01_ROOT / "outputs" / "step3_stage",
    "outputs_step3_runs": ATTEMPT01_ROOT / "outputs" / "step3_runs",
    "outputs_step3_orchestration": (
        ATTEMPT01_ROOT / "outputs" / "step3_orchestration"
    ),
    "tmp_step3_runs": ATTEMPT01_ROOT / "tmp" / "step3_runs",
    "logs_step3_runs": ATTEMPT01_ROOT / "logs" / "step3_runs",
}
ATTEMPT02_METADATA_SHA256 = {
    "attempt_summary.json": (
        "DBECF3228753B3F701C89B1D3BBAE39BBFB567776EFC529E647C0C4036F2180A"
    ),
    "attempt_file_manifest.csv": (
        "141799B20C1B3C530260771BCE5C30FDD1D69C63212D0C65F9133860DFF6DBF7"
    ),
    "tool_snapshot_manifest.csv": (
        "FABE65F364B38B6B6C63C575203B12CCC56659FF8CCD21F976F512CBFD23DF05"
    ),
}
ATTEMPT02_TOOL_SHA256 = {
    "stage_board21_step3_runs.py": (
        "9DEE64A057A82343227C2F49B23BEECB5A5AF076877CB2A54B478FCFAE769AA1"
    ),
    "run_one_board21_energy_route.m": (
        "692B749833FD5A30526AE3CA6F2CEE55630F0A908BE0A75BC8E9B4F294E08D00"
    ),
    "execute_board21_step3_route.py": (
        "CEB805DF2F4E83DF4C2B93350AF257B0058923C372D5735A5730FE4694C47DD6"
    ),
    "run_board21_step3_all.py": (
        "FFD6D9A5E25C2CE17DB43A2A633D2549A6A9540A040C135CB144D20C7B73E273"
    ),
    "validate_board21_step3_runs.py": (
        "AA6343FF2F0694BCF4E7ED3E3B7E842538FB33650026B062086095DBF0E703F5"
    ),
}
ATTEMPT02_PINNED_FILE_SHA256 = {
    "outputs/step3_orchestration/run_all_summary.json": (
        "2823E1D47718215C810E9AE8EC6B5638D59B936BB9B0229C4585A985A84EF354"
    ),
    "outputs/step3_validation/checks.csv": (
        "E4B6BA59429EC033AFBAD33F6612D2649D094928557B774DB7C55C87EB949CC7"
    ),
    "outputs/step3_validation/repeat_comparison.csv": (
        "7273447D016B3030C8A25CE821D588778B717496DBD2B4FFD16AA719BAFEF2E3"
    ),
    "outputs/step3_validation/route_results.csv": (
        "A52A1FE7112BEFEBE86B0A3A8124F773012F427F31339BA38C40C984C41BEBFA"
    ),
    "outputs/step3_validation/validation_summary.json": (
        "CE8C7BCCC8C1E151727AC42751EF90946D9699C090AFFDAB23644A2CD494D6A4"
    ),
}
ATTEMPT02_LOGICAL_ROOTS = {
    "tmp_step3_runs": ATTEMPT02_ROOT / "tmp" / "step3_runs",
    "outputs_step3_stage": ATTEMPT02_ROOT / "outputs" / "step3_stage",
    "outputs_step3_runs": ATTEMPT02_ROOT / "outputs" / "step3_runs",
    "logs_step3_runs": ATTEMPT02_ROOT / "logs" / "step3_runs",
    "outputs_step3_orchestration": (
        ATTEMPT02_ROOT / "outputs" / "step3_orchestration"
    ),
    "outputs_step3_validation": (
        ATTEMPT02_ROOT / "outputs" / "step3_validation"
    ),
}
ATTEMPT02_ROOT_COUNTS = {
    "tmp_step3_runs": {"file_count": 28, "total_size_bytes": 1_075_314},
    "outputs_step3_stage": {"file_count": 3, "total_size_bytes": 28_529},
    "outputs_step3_runs": {"file_count": 112, "total_size_bytes": 6_727_585},
    "logs_step3_runs": {"file_count": 70, "total_size_bytes": 115_522},
    "outputs_step3_orchestration": {
        "file_count": 123,
        "total_size_bytes": 505_908,
    },
    "outputs_step3_validation": {
        "file_count": 4,
        "total_size_bytes": 5_564_634,
    },
}
ATTEMPT02_FAILED_CHECK_IDS = {
    "S3-SCIENTIFIC-FORMULA-13",
    "S3-SCIENTIFIC-FORMULA-14",
    "S3-REPEAT-07",
    "S3-ALL-ROUTES-REPEAT",
}
FORMAL_OBJECT_NAMES = (
    "表4-1_两类划分Guyan与Craig--Bampton能量变化率",
    "结论C06_能量变化率稳定风险阈值",
)

STEP2_ANCHORS = {
    "outputs/step2_validation/checks.csv": "0207D7AAFC16BDCAC4298E387668DAABB143300F92927FDD4C6CABDBEDA13EF9",
    "outputs/step2_validation/validation_summary.json": "D2FD9B0DF2AD1B38F70B020E56CFCF93A92DD1132085870EC48D8990CE114A26",
    "outputs/step2_validation/step2_artifact_manifest.csv": "4BCD18ADB8321123ACFF53E30C0B5F02D5ED05C16181E7BAA829743831C5B9F9",
    "outputs/step2_validation/validation_output_manifest.csv": "DE3F2062E377007D39C59A74734F5033A2E780C68A61FAFE40E8867FF7DAE00A",
    "outputs/step2_determinism/determinism_audit.json": "9CD0C07D7956E4CC5F0ECC1956EAD54A21B9DD2AD3371F769DA6ED1D06CEED38",
    "outputs/step2_static_inventory/inventory_summary.json": "C587F4FA80E56512C7734D545A20BE483EADC5E09B5707A6D241ACBADE2A7D1C",
    "report/板块21_最小步骤2_公式与历史脚本静态审计.md": "7E642186B735E73B13547D10073AEE4B66146A7157860C1157F120165406B2DF",
    "code/validate_board21_step2_static_inventory.py": "53859497258128CD5FED7C43C089302DA2FB29B717DA9F08E0523A8A674CBB64",
}

SOURCES = {
    "PDmonicanshu.m": "A78F2608FEE0FA0775DEB0D7F778A51327C81BF88F25AA6D8E13D4202EB7B883",
    "PDmonicanshu2.m": "ADF1C89A4C9443168DCBBBBC5F9AAA1C68CE275C4F49E449C1CBABDEF86FF110",
    "PDmonicanshu3.m": "C35C7BFB19C3A5E98626FF1A07C14481F53973947E2C382EB81BD9642D9CF40E",
    "monicanshu_2_suoju.mlx": "1F885E0971033EBCB8632110EC5A47DA507126C718A80176FF3347B2ED6A08C5",
    "monicanshu_3_suoju.mlx": "D7AC9307B1A07D7AA442FDF37E7882BAE3EC519C021A5A317FFE9D9374E70D01",
    "energy_zonghe.mlx": "BCEDEF1887ABEE046A3018EB746B2088B0D63F9ACC917B9B4A78D97DEC84159D",
    "energy_zonghe2.mlx": "A84F903A5163AC0792FEA6BD0222003B3D2E1ED12B4D1B2CD6EABF325CA5CAAD",
    "Copy_of_energy_zonghe2.mlx": "80C4B3FE2A860552054D8FCEABA40365C5EE646BBB2EB21C9AF68E81AFE4715D",
    "Copy_2_of_energy_zonghe2.mlx": "8EBC3ACBD47B1D112395D4DCD951FE018F71A857E604187B443A2BFD572ADA66",
    "energy_zonghe3.mlx": "1F3B84A542AF40563F05C23402C2355345100D38A94D8EF130D5545A33D36614",
    "Copy_of_energy_zonghe3.mlx": "C067893CE26DA706774A886523F9000A2A0779268BB12A93A21E0EF0034296AC",
    "Copy_2_of_energy_zonghe3.mlx": "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D",
}

ROUTE7_FORMULA_RECORD = (
    BOARD_ROOT
    / "outputs"
    / "step2_static_inventory"
    / "extracted_mlx_records"
    / "Copy_2_of_energy_zonghe3__record.json"
)
ROUTE7_FORMULA_SOURCE_CONTRACT = {
    "schema_version": "BOARD21_STEP3_ROUTE7_FORMULA_SOURCE_CONTRACT_V1",
    "contract_id": "COPY2_ENERGY3_C002_C003_C004",
    "route_id": "division2_tp17_copy2_coordinate_formula_conflict",
    "record_sha256": (
        "010217DBEF67168C5A23EEA24B818D2291C59A0141AB305F86CB6968D957F40D"
    ),
    "source_name": "Copy_2_of_energy_zonghe3.mlx",
    "source_sha256": (
        "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D"
    ),
    "source_size_bytes": 71_469,
    "code_cell_count": 4,
    "cell_contracts": [
        {
            "code_index_zero_based": 1,
            "paragraph_index": 3,
            "cell_index": 2,
            "text_sha256": (
                "B0EC066DC22F717BF0E2F4DDF538AA070C99F8B3BF26649507AE1B9B28FCD5A3"
            ),
        },
        {
            "code_index_zero_based": 2,
            "paragraph_index": 5,
            "cell_index": 3,
            "text_sha256": (
                "FF6324B69613061FC0D16025BCF9933776EFCC193BCE84996F7E239D5183D70C"
            ),
        },
        {
            "code_index_zero_based": 3,
            "paragraph_index": 7,
            "cell_index": 4,
            "text_sha256": (
                "954F2A68BE41E4EBFFAF676F2C13719E806B1E742BD6FBF8F8D7C63A2768BD11"
            ),
        },
    ],
    "matlab_retained_one_based": [1, 2],
    "python_retained_zero_based": [0, 1],
    "d2_relation": "d2=d",
    "component_sum_scopes": {
        "energy_sum_orig": "selected_d",
        "energy_sum_guyan": "all_vector",
        "energy_sum_cb": "selected_d2",
    },
    "denominator_by_total": {
        "total_increase_guyan": "energy_sum_guyan",
        "total_increase_cb": "energy_sum_guyan",
    },
    "route_sum_scope": "selected_original_and_cb",
    "route_denominator": "guyan_for_both",
    "normalized_c004_statements": [
        "energy_sum_guyan=sum(E_total_guyan)",
        "energy_sum_orig=sum(E_total(d))",
        (
            "total_increase_guyan=(energy_sum_guyan-energy_sum_orig)"
            "./energy_sum_guyan*100"
        ),
        "energy_sum_cb=sum(E_total_cb(d2))",
        "energy_sum_orig=sum(E_total(d))",
        (
            "total_increase_cb=(energy_sum_cb-energy_sum_orig)"
            "./energy_sum_guyan*100"
        ),
    ],
}

ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route_id": "reference15_pd19_energy",
        "route_label_cn": "旧15自由度参考体系：PD参数族1.9→energy_zonghe",
        "division_identity": "旧15自由度水平主坐标参考体系；不绑定表4-1两类整体划分",
        "parameter_family": "rho=785e3.*1.9",
        "upstream": "PDmonicanshu.m",
        "candidate": "energy_zonghe.mlx",
        "lengths": [15, 3, 6],
        "history": [6.5613, 6.5535],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1, 2],
        "upstream_required": ["KRrt", "MRrt", "T", "KRren", "MRren", "T_cb", "KR_cb", "MR_cb"],
        "static_boundary": "REFERENCE_NOT_TABLE4_1_DIVISION",
    },
    {
        "route_id": "division1_pd19_copy",
        "route_label_cn": "第一类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "upstream": "PDmonicanshu2.m",
        "candidate": "Copy_of_energy_zonghe2.mlx",
        "lengths": [6, 2, 5],
        "history": [9.6488, 9.3150],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "T", "KRren", "MRren", "T_cb", "KR_cb", "MR_cb"],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division1_tp17_energy",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_2_suoju.mlx",
        "candidate": "energy_zonghe2.mlx",
        "lengths": [6, 2, 5],
        "history": [9.7221, 9.3097],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division1_tp17_copy2_formula_invalid",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→Copy_2错误公式",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_2_suoju.mlx",
        "candidate": "Copy_2_of_energy_zonghe2.mlx",
        "lengths": [6, 2, 5],
        "history": [-33.7706, -41.7441],
        "denominator": "guyan_for_both",
        "sum_scope": "all_vectors",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "FORMULA_INVALID_NORMALIZATION_AND_DENOMINATOR",
    },
    {
        "route_id": "division2_pd19_copy",
        "route_label_cn": "第二类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe3",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "upstream": "PDmonicanshu3.m",
        "candidate": "Copy_of_energy_zonghe3.mlx",
        "lengths": [9, 2, 5],
        "history": [59.8619, 15.5000],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "T", "KRren", "MRren", "T_cb", "KR_cb", "MR_cb"],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division2_tp17_energy_coordinate_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→energy_zonghe3（坐标顺序冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_3_suoju.mlx",
        "candidate": "energy_zonghe3.mlx",
        "lengths": [9, 2, 5],
        "history": [59.8619, 16.9607],
        "denominator": "original",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "COORDINATE_ORDER_CONFLICT",
    },
    {
        "route_id": "division2_tp17_copy2_coordinate_formula_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→Copy_2（坐标与公式冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream": "monicanshu_3_suoju.mlx",
        "candidate": "Copy_2_of_energy_zonghe3.mlx",
        "lengths": [9, 2, 5],
        "history": [39.2658, 20.2060],
        "denominator": "guyan_for_both",
        "sum_scope": "selected_original_and_cb",
        "retained_zero_based": [0, 1],
        "formula_source_contract_id": "COPY2_ENERGY3_C002_C003_C004",
        "upstream_required": ["KPrt", "MPrt", "TP", "KPren", "MPren", "TP_cb", "KP_cb", "MP_cb"],
        "static_boundary": "COORDINATE_ORDER_AND_FORMULA_CONFLICT",
    },
)

EXPECTED_RUN_ORDER = tuple(
    (route["route_id"], replicate)
    for route in ROUTES
    for replicate in REPLICATES
)

ARTIFACT_ORDER = (
    "config_json",
    "config_hash_file",
    "run_status_json",
    "variable_inventory_json",
    "workspace_after_upstream",
    "workspace_success",
    "workspace_failure",
    "scientific_mat",
    "matlab_diary",
    "error_report",
    "matlab_command",
    "matlab_stdout",
    "matlab_stderr",
    "shell_combined_log",
)

REQUIRED_FINAL = (
    "E_total",
    "E_total_guyan",
    "E_total_cb",
    "energy_sum_orig",
    "energy_sum_guyan",
    "energy_sum_cb",
    "total_increase_guyan",
    "total_increase_cb",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_upper_sha256_text(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9A-F]{64}", value) is not None


def sha256_ascii_text(value: str) -> str:
    return hashlib.sha256(value.encode("ascii", errors="strict")).hexdigest().upper()


def add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    category: str,
    passed: bool,
    expected: Any,
    actual: Any,
    evidence: Path | str,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "expected": json.dumps(expected, ensure_ascii=False, sort_keys=True, default=str),
            "actual": json.dumps(actual, ensure_ascii=False, sort_keys=True, default=str),
            "evidence": str(evidence),
        }
    )


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def evaluate_route7_formula_source_contract(
    route: dict[str, Any],
) -> dict[str, Any]:
    contract = ROUTE7_FORMULA_SOURCE_CONTRACT
    checks: dict[str, bool] = {}
    result: dict[str, Any] = {
        "schema_version": contract["schema_version"],
        "contract_id": contract["contract_id"],
        "record_path": str(ROUTE7_FORMULA_RECORD),
        "checks": checks,
        "errors": [],
        "derived": {},
        "pass": False,
    }

    def record_check(name: str, passed: Any) -> None:
        checks[name] = bool(passed)

    try:
        record_hash = (
            sha256_file(ROUTE7_FORMULA_RECORD)
            if ROUTE7_FORMULA_RECORD.is_file()
            else "MISSING"
        )
        record = load_json(ROUTE7_FORMULA_RECORD)
        source_name = str(contract["source_name"])
        source_path = AUTHOR_ROOT / source_name
        source_hash = sha256_file(source_path) if source_path.is_file() else "MISSING"
        code_cells = record.get("code_cells")
        paragraphs = record.get("paragraphs")
        if not isinstance(code_cells, list) or not all(
            isinstance(item, str) for item in code_cells
        ):
            raise TypeError("route7 record code_cells must be a string list")
        if not isinstance(paragraphs, list) or not all(
            isinstance(item, dict) for item in paragraphs
        ):
            raise TypeError("route7 record paragraphs must be an object list")

        record_check("record.sha256", record_hash == contract["record_sha256"])
        record_check("record.source_name", record.get("source_name") == source_name)
        record_check(
            "record.source_sha256",
            record.get("source_sha256") == contract["source_sha256"],
        )
        record_check(
            "record.source_size_bytes",
            record.get("source_size_bytes") == contract["source_size_bytes"],
        )
        record_check(
            "record.code_cell_count", len(code_cells) == contract["code_cell_count"]
        )
        record_check("source.exists", source_path.is_file())
        record_check("source.sha256", source_hash == contract["source_sha256"])
        record_check(
            "source.manifest_sha256", SOURCES.get(source_name) == contract["source_sha256"]
        )

        for cell_contract in contract["cell_contracts"]:
            code_index = int(cell_contract["code_index_zero_based"])
            paragraph_index = int(cell_contract["paragraph_index"])
            cell_index = int(cell_contract["cell_index"])
            label = f"cell.C{cell_index:03d}"
            cell_text = code_cells[code_index] if code_index < len(code_cells) else None
            cell_hash = (
                hashlib.sha256(cell_text.encode("utf-8")).hexdigest().upper()
                if isinstance(cell_text, str)
                else "MISSING"
            )
            paragraph = next(
                (
                    item
                    for item in paragraphs
                    if item.get("paragraph_index") == paragraph_index
                ),
                None,
            )
            record_check(
                f"{label}.text_sha256",
                cell_hash == cell_contract["text_sha256"],
            )
            record_check(
                f"{label}.paragraph_mapping",
                isinstance(paragraph, dict)
                and paragraph.get("kind") == "code"
                and paragraph.get("cell_index") == cell_index
                and paragraph.get("text") == cell_text
                and paragraph.get("text_sha256") == cell_contract["text_sha256"],
            )

        active_lines: list[str] = []
        for cell in code_cells:
            for raw_line in cell.splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("%"):
                    continue
                active_lines.append(stripped.split("%", 1)[0].strip())
        d_matches: list[list[int]] = []
        d2_match_count = 0
        for line in active_lines:
            d_match = re.fullmatch(
                r"d\s*=\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]\s*;?", line
            )
            if d_match:
                d_matches.append([int(d_match.group(1)), int(d_match.group(2))])
            if re.fullmatch(r"d2\s*=\s*d\s*;?", line):
                d2_match_count += 1
        matlab_retained = d_matches[0] if len(d_matches) == 1 else []
        python_retained = [value - 1 for value in matlab_retained]
        record_check(
            "derived.d_unique",
            len(d_matches) == 1
            and matlab_retained == contract["matlab_retained_one_based"],
        )
        record_check("derived.d2_unique", d2_match_count == 1)
        record_check(
            "derived.python_retained_zero_based",
            python_retained == contract["python_retained_zero_based"],
        )

        c004_index = int(contract["cell_contracts"][-1]["code_index_zero_based"])
        c004_lines = []
        if c004_index < len(code_cells):
            for raw_line in code_cells[c004_index].splitlines():
                stripped = raw_line.strip()
                if not stripped or stripped.startswith("%"):
                    continue
                statement = re.sub(r"\s+", "", stripped.split("%", 1)[0])
                c004_lines.append(statement.removesuffix(";"))
        record_check(
            "derived.c004_statements",
            c004_lines == contract["normalized_c004_statements"],
        )

        derived = {
            "matlab_retained_one_based": matlab_retained,
            "python_retained_zero_based": python_retained,
            "d2_relation": "d2=d" if d2_match_count == 1 else "UNRESOLVED",
            "component_sum_scopes": (
                contract["component_sum_scopes"]
                if c004_lines == contract["normalized_c004_statements"]
                else {}
            ),
            "denominator_by_total": (
                contract["denominator_by_total"]
                if c004_lines == contract["normalized_c004_statements"]
                else {}
            ),
            "normalized_c004_statements": c004_lines,
        }
        result["derived"] = derived
        record_check("route.route_id", route.get("route_id") == contract["route_id"])
        record_check("route.candidate", route.get("candidate") == source_name)
        record_check(
            "route.formula_source_contract_id",
            route.get("formula_source_contract_id") == contract["contract_id"],
        )
        record_check(
            "route.retained_zero_based",
            route.get("retained_zero_based") == python_retained,
        )
        record_check(
            "route.sum_scope", route.get("sum_scope") == contract["route_sum_scope"]
        )
        record_check(
            "route.denominator",
            route.get("denominator") == contract["route_denominator"],
        )
        record_check(
            "route.static_boundary",
            route.get("static_boundary") == "COORDINATE_ORDER_AND_FORMULA_CONFLICT",
        )
    except Exception as error:
        result["errors"].append(f"{type(error).__name__}: {error}")
        result["traceback"] = traceback.format_exc()

    failed_fields = sorted(name for name, passed in checks.items() if not passed)
    passed = bool(checks and not failed_fields and not result["errors"])
    result["failed_fields"] = failed_fields
    result["pass"] = passed
    result["status"] = "PASS" if passed else "FAIL"
    return result


def normalize_struct_list(value: Any, field: str) -> list[dict[str, Any]]:
    """Normalize MATLAB jsonencode's 0/1/N struct representations."""
    if value is None or value == []:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise TypeError(f"{field} must be a MATLAB struct object or struct array")


def normalize_string_list(value: Any, field: str) -> list[str]:
    """Normalize MATLAB jsonencode's 0/1/N cell-string representations."""
    if value is None or value == []:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError(f"{field} must be a string or string array")


def strict_abs_rel_comparison(
    actual: Any, expected: Any, tolerance: float = 1e-12
) -> dict[str, Any]:
    """Require the absolute *and* relative error gates independently."""
    try:
        actual_float = float(actual)
        expected_float = float(expected)
    except (TypeError, ValueError, OverflowError) as error:
        return {
            "actual": actual,
            "expected": expected,
            "absolute_error": math.inf,
            "relative_error": math.inf,
            "absolute_error_le_tolerance": False,
            "relative_error_le_tolerance": False,
            "tolerance": tolerance,
            "error": f"{type(error).__name__}: {error}",
            "pass": False,
        }
    if not math.isfinite(actual_float) or not math.isfinite(expected_float):
        return {
            "actual": actual_float,
            "expected": expected_float,
            "absolute_error": math.inf,
            "relative_error": math.inf,
            "absolute_error_le_tolerance": False,
            "relative_error_le_tolerance": False,
            "tolerance": tolerance,
            "error": "nonfinite_operand",
            "pass": False,
        }
    absolute_error = abs(actual_float - expected_float)
    scale = max(abs(actual_float), abs(expected_float), np.finfo(np.float64).tiny)
    relative_error = absolute_error / scale
    absolute_pass = absolute_error <= tolerance
    relative_pass = relative_error <= tolerance
    return {
        "actual": actual_float,
        "expected": expected_float,
        "absolute_error": absolute_error,
        "relative_error": relative_error,
        "absolute_error_le_tolerance": absolute_pass,
        "relative_error_le_tolerance": relative_pass,
        "tolerance": tolerance,
        "error": "",
        "pass": bool(absolute_pass and relative_pass),
    }


def strict_abs_rel_close(actual: Any, expected: Any, tolerance: float = 1e-12) -> bool:
    return bool(strict_abs_rel_comparison(actual, expected, tolerance)["pass"])


def is_positive_integral_number(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value > 0
    if isinstance(value, float):
        return math.isfinite(value) and value.is_integer() and value > 0
    return False


def is_strict_positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def terminal_json_from_bytes(payload: bytes, field: str) -> dict[str, Any]:
    text = payload.decode("utf-8", errors="strict")
    for line in reversed(text.splitlines()):
        candidate = line.strip()
        if candidate.startswith("{") and candidate.endswith("}"):
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
    raise ValueError(f"{field} does not contain a terminal JSON object")


def terminal_json_line_bytes(payload: bytes, field: str) -> bytes:
    for line in reversed(payload.splitlines()):
        candidate = line.strip()
        if candidate:
            candidate.decode("utf-8", errors="strict")
            value = json.loads(candidate)
            if not isinstance(value, dict):
                raise TypeError(f"{field} terminal JSON is not an object")
            return candidate
    raise ValueError(f"{field} does not contain a nonempty terminal line")


def canonical_json_utf8(value: dict[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def exact_absolute_path(value: Any, expected: Path) -> bool:
    if not isinstance(value, str) or not value:
        return False
    actual = Path(value)
    return actual.is_absolute() and actual.resolve() == expected.resolve()


def verify_input_freeze() -> tuple[list[dict[str, str]], dict[str, Any]]:
    manifest_hash = sha256_file(INPUT_MANIFEST) if INPUT_MANIFEST.is_file() else "MISSING"
    summary_hash = (
        sha256_file(INPUT_FREEZE_SUMMARY)
        if INPUT_FREEZE_SUMMARY.is_file()
        else "MISSING"
    )
    if manifest_hash != INPUT_MANIFEST_SHA256:
        raise RuntimeError(
            f"input manifest seal mismatch: expected={INPUT_MANIFEST_SHA256}, "
            f"actual={manifest_hash}"
        )
    if summary_hash != INPUT_FREEZE_SUMMARY_SHA256:
        raise RuntimeError(
            "input freeze summary seal mismatch: "
            f"expected={INPUT_FREEZE_SUMMARY_SHA256}, actual={summary_hash}"
        )

    expected_fields = [
        "item_id",
        "category",
        "role",
        "source_absolute_path",
        "source_relative_label",
        "frozen_relative_path",
        "source_size_bytes",
        "source_sha256",
        "frozen_size_bytes",
        "frozen_sha256",
        "live_change_policy",
        "status",
    ]
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != expected_fields:
            raise RuntimeError(
                f"input manifest header mismatch: {reader.fieldnames}"
            )
        rows = list(reader)
    if len(rows) != 53:
        raise RuntimeError(f"input manifest must contain 53 rows, got {len(rows)}")

    row_errors: list[dict[str, Any]] = []
    category_counts = Counter(row.get("category", "") for row in rows)
    item_ids = [row.get("item_id", "") for row in rows]
    source_identities: list[str] = []
    frozen_identities: list[str] = []
    total_source_bytes = 0
    source_inside_board_count = 0
    for row_number, row in enumerate(rows, start=2):
        reasons: list[str] = []
        source_text = row.get("source_absolute_path", "")
        source = Path(source_text)
        frozen_relative_text = row.get("frozen_relative_path", "")
        frozen_relative = Path(frozen_relative_text)
        frozen = (BOARD_ROOT / "input" / frozen_relative).resolve()
        if not source.is_absolute():
            reasons.append("source_not_absolute")
        elif str(source.resolve()) != source_text:
            reasons.append("source_path_not_canonical_absolute_identity")
        if frozen_relative.is_absolute() or not is_within(frozen, BOARD_ROOT / "input"):
            reasons.append("frozen_relative_path_escapes_input_root")
        if row.get("status") != "MATCH":
            reasons.append("status_not_MATCH")
        if row.get("live_change_policy") != "immutable":
            reasons.append("live_change_policy_not_immutable")
        try:
            source_size = int(row.get("source_size_bytes", ""))
            frozen_size = int(row.get("frozen_size_bytes", ""))
        except ValueError:
            source_size = -1
            frozen_size = -1
            reasons.append("invalid_declared_size")
        source_actual_size = source.stat().st_size if source.is_file() else -1
        frozen_actual_size = frozen.stat().st_size if frozen.is_file() else -1
        source_actual_hash = sha256_file(source) if source.is_file() else "MISSING"
        frozen_actual_hash = sha256_file(frozen) if frozen.is_file() else "MISSING"
        if source_actual_size != source_size:
            reasons.append("source_size_mismatch")
        if frozen_actual_size != frozen_size:
            reasons.append("frozen_size_mismatch")
        if source_actual_hash != row.get("source_sha256"):
            reasons.append("source_hash_mismatch")
        if frozen_actual_hash != row.get("frozen_sha256"):
            reasons.append("frozen_hash_mismatch")
        if source_size != frozen_size or row.get("source_sha256") != row.get(
            "frozen_sha256"
        ):
            reasons.append("source_frozen_declared_identity_mismatch")
        if source_actual_size != frozen_actual_size or source_actual_hash != frozen_actual_hash:
            reasons.append("source_frozen_actual_identity_mismatch")
        if source.is_absolute() and is_within(source, BOARD_ROOT):
            source_inside_board_count += 1
        total_source_bytes += max(source_size, 0)
        source_identities.append(str(source.resolve()) if source.is_absolute() else source_text)
        frozen_identities.append(str(frozen))
        if reasons:
            row_errors.append(
                {
                    "row": row_number,
                    "item_id": row.get("item_id"),
                    "reasons": reasons,
                }
            )

    if len(set(item_ids)) != 53 or any(not item_id for item_id in item_ids):
        row_errors.append({"reason": "item_id_not_53_unique_nonempty"})
    if len(set(source_identities)) != 53:
        row_errors.append({"reason": "source_absolute_identity_not_53_unique"})
    if len(set(frozen_identities)) != 53:
        row_errors.append({"reason": "frozen_absolute_identity_not_53_unique"})
    if dict(category_counts) != EXPECTED_INPUT_CATEGORY_COUNTS:
        row_errors.append(
            {
                "reason": "category_counts_mismatch",
                "expected": EXPECTED_INPUT_CATEGORY_COUNTS,
                "actual": dict(category_counts),
            }
        )
    if source_inside_board_count != 0:
        row_errors.append(
            {
                "reason": "source_inside_board_root",
                "count": source_inside_board_count,
            }
        )

    summary = load_json(INPUT_FREEZE_SUMMARY)
    expected_summary = {
        "schema_version": "BOARD21_INPUT_FREEZE_V1",
        "status": "PASS",
        "input_count": 53,
        "author_energy_file_count": 36,
        "source_frozen_match_count": 53,
        "source_inside_board_root_count": 0,
        "total_source_bytes": total_source_bytes,
        "category_counts": EXPECTED_INPUT_CATEGORY_COUNTS,
    }
    summary_mismatches = {
        key: {"expected": expected, "actual": summary.get(key)}
        for key, expected in expected_summary.items()
        if summary.get(key) != expected
    }
    if row_errors or summary_mismatches:
        raise RuntimeError(
            "complete 53-row input freeze verification failed: "
            + json.dumps(
                {"row_errors": row_errors, "summary_mismatches": summary_mismatches},
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return rows, summary


def author_manifest_by_name(
    all_rows: list[dict[str, str]] | None = None,
) -> dict[str, dict[str, str]]:
    if all_rows is None:
        all_rows, _ = verify_input_freeze()
    selected = [
        row
        for row in all_rows
        if row.get("category") == "author_energy_tree"
        and Path(row.get("frozen_relative_path", "")).name in SOURCES
    ]
    result = {Path(row["frozen_relative_path"]).name: row for row in selected}
    if len(selected) != 12 or len(result) != 12 or set(result) != set(SOURCES):
        raise RuntimeError("step1 manifest does not uniquely cover the 12 route sources")
    for name, row in result.items():
        expected = SOURCES[name]
        if (
            row.get("source_sha256") != expected
            or row.get("frozen_sha256") != expected
            or row.get("status") != "MATCH"
        ):
            raise RuntimeError(f"step1 manifest identity mismatch: {name}")
    return result


def decode_h5_attribute(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="strict")
    if isinstance(value, np.bytes_):
        return bytes(value).decode("utf-8", errors="strict")
    if isinstance(value, np.ndarray) and value.size == 1:
        return decode_h5_attribute(value.reshape(-1)[0])
    return str(value)


def dtype_signature(dtype: np.dtype[Any]) -> Any:
    return dtype.descr if dtype.fields else dtype.str


def h5_boolean_attribute(obj: h5py.Dataset | h5py.Group, name: str) -> bool:
    if name not in obj.attrs:
        return False
    raw = np.asarray(obj.attrs[name])
    if raw.size == 0:
        return False
    return bool(raw.astype(bool).any())


def matlab_empty_shape(raw: np.ndarray[Any, Any]) -> tuple[int, ...] | None:
    """Decode MATLAB v7.3's dimension payload for an empty array."""
    flat = np.asarray(raw).reshape(-1)
    if flat.size == 0 or not np.issubdtype(flat.dtype, np.number):
        return None
    as_float = flat.astype(np.float64, copy=False)
    if (
        not np.all(np.isfinite(as_float))
        or np.any(as_float < 0)
        or np.any(as_float != np.floor(as_float))
    ):
        return None
    return tuple(int(item) for item in as_float)


def dtype_matches_matlab_class(
    dtype: np.dtype[Any], matlab_class: str, compound_complex: bool
) -> bool:
    expected = {
        "double": ("f", 8),
        "single": ("f", 4),
        "int8": ("i", 1),
        "uint8": ("u", 1),
        "int16": ("i", 2),
        "uint16": ("u", 2),
        "int32": ("i", 4),
        "uint32": ("u", 4),
        "int64": ("i", 8),
        "uint64": ("u", 8),
    }.get(matlab_class)
    if expected is None:
        return False
    if compound_complex:
        if not dtype.fields or set(dtype.fields) != {"real", "imag"}:
            return False
        components = [dtype.fields["real"][0], dtype.fields["imag"][0]]
    else:
        components = [dtype]
    return all(item.kind == expected[0] and item.itemsize == expected[1] for item in components)


def h5_numeric_record(path: Path, name: str) -> dict[str, Any]:
    with h5py.File(path, "r") as handle:
        if name not in handle or not isinstance(handle[name], h5py.Dataset):
            raise KeyError(f"numeric dataset missing: {name}: {path}")
        dataset = handle[name]
        raw = np.asarray(dataset)
        matlab_class = decode_h5_attribute(dataset.attrs.get("MATLAB_class", ""))
        matlab_empty = h5_boolean_attribute(dataset, "MATLAB_empty")
        matlab_sparse = h5_boolean_attribute(dataset, "MATLAB_sparse")
        matlab_global = h5_boolean_attribute(dataset, "MATLAB_global")
    original_dtype = dtype_signature(raw.dtype)
    compound_complex = bool(
        raw.dtype.fields and {"real", "imag"}.issubset(raw.dtype.fields)
    )
    value = raw["real"] + 1j * raw["imag"] if compound_complex else raw
    dtype_class_match = dtype_matches_matlab_class(
        raw.dtype, matlab_class, compound_complex
    )
    decoded_empty_shape = matlab_empty_shape(raw) if matlab_empty else None
    canonical_shape = (
        decoded_empty_shape
        if matlab_empty and decoded_empty_shape is not None
        else tuple(reversed(tuple(int(item) for item in raw.shape)))
    )
    return {
        "value": np.asarray(value),
        "matlab_class": matlab_class,
        "dtype": original_dtype,
        "shape": tuple(int(item) for item in raw.shape),
        "matlab_shape": canonical_shape,
        "is_complex": bool(compound_complex or np.iscomplexobj(raw)),
        "is_empty": bool(matlab_empty or raw.size == 0),
        "matlab_empty_attribute": matlab_empty,
        "matlab_empty_shape_decoded": (
            decoded_empty_shape is not None if matlab_empty else True
        ),
        "is_sparse": matlab_sparse,
        "is_global": matlab_global,
        "dtype_matches_matlab_class": dtype_class_match,
    }


def h5_dataset_content_record(path: Path, name: str) -> dict[str, Any]:
    """Return an exact raw-byte seal plus a numeric semantic array."""
    with h5py.File(path, "r") as handle:
        if name not in handle or not isinstance(handle[name], h5py.Dataset):
            raise KeyError(f"dataset missing for content comparison: {name}: {path}")
        raw = np.asarray(handle[name])
    compound_complex = bool(
        raw.dtype.fields and {"real", "imag"}.issubset(raw.dtype.fields)
    )
    if raw.dtype.hasobject:
        raise TypeError(
            f"object/reference dataset content comparison unsupported: {name}: {path}"
        )
    if compound_complex:
        value = raw["real"] + 1j * raw["imag"]
    else:
        value = raw
    value_array = np.asarray(value)
    if not np.issubdtype(value_array.dtype, np.number):
        raise TypeError(f"nonnumeric selected scientific dataset: {name}: {path}")
    contiguous_raw = np.ascontiguousarray(raw)
    payload = contiguous_raw.tobytes(order="C")
    return {
        "value": value_array,
        "raw_size_bytes": len(payload),
        "raw_sha256": hashlib.sha256(payload).hexdigest().upper(),
        "raw_dtype": dtype_signature(raw.dtype),
        "raw_shape": tuple(int(item) for item in raw.shape),
    }


def h5_names(path: Path) -> set[str]:
    with h5py.File(path, "r") as handle:
        return {name for name in handle.keys() if name != "#refs#"}


def scalar_from_record(record: dict[str, Any], name: str) -> float:
    value = np.asarray(record["value"]).reshape(-1)
    if value.size != 1:
        raise ValueError(f"expected scalar {name}, got {record['shape']}")
    scalar_value = value[0]
    if np.iscomplexobj(value):
        if abs(float(np.imag(scalar_value))) > 1e-12:
            raise ValueError(f"complex scalar exceeds 1e-12: {name}")
        scalar_value = np.real(scalar_value)
    return float(scalar_value)


def finite_numeric_record(path: Path, name: str) -> dict[str, Any]:
    record = h5_numeric_record(path, name)
    value = np.asarray(record["value"])
    if record["matlab_class"] != "double":
        raise ValueError(
            f"required scientific value is not MATLAB double for {name}: "
            f"{record['matlab_class']!r}: {path}"
        )
    if not record["dtype_matches_matlab_class"]:
        raise ValueError(
            f"MATLAB_class/HDF5 dtype mismatch for {name}: "
            f"class={record['matlab_class']!r}, dtype={record['dtype']!r}"
        )
    if record["is_empty"]:
        raise ValueError(f"empty required numeric value: {name}: {path}")
    if record["is_sparse"]:
        raise ValueError(f"sparse required scientific value is unsupported: {name}: {path}")
    if record["is_global"]:
        raise ValueError(f"global required scientific value is unsupported: {name}: {path}")
    if not np.issubdtype(value.dtype, np.number) or not np.all(np.isfinite(value)):
        raise ValueError(f"nonfinite or nonnumeric: {name}: {path}")
    if record["is_complex"] or np.iscomplexobj(value):
        raise ValueError(f"required scientific value must be strictly real: {name}: {path}")
    return record


def h5_workspace_metadata(path: Path) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    with h5py.File(path, "r") as handle:
        for name in handle.keys():
            if name == "#refs#":
                continue
            obj = handle[name]
            matlab_class = decode_h5_attribute(obj.attrs.get("MATLAB_class", ""))
            if isinstance(obj, h5py.Dataset):
                raw = np.asarray(obj)
                matlab_empty = h5_boolean_attribute(obj, "MATLAB_empty")
                matlab_sparse = h5_boolean_attribute(obj, "MATLAB_sparse")
                matlab_global = h5_boolean_attribute(obj, "MATLAB_global")
                decoded_empty_shape = (
                    matlab_empty_shape(raw) if matlab_empty else None
                )
                compound_complex = bool(
                    raw.dtype.fields
                    and {"real", "imag"}.issubset(raw.dtype.fields)
                )
                dtype_class_match = dtype_matches_matlab_class(
                    raw.dtype, matlab_class, compound_complex
                )
                rejection_reasons: list[str] = []
                if not matlab_class:
                    rejection_reasons.append("missing_MATLAB_class")
                if matlab_sparse:
                    rejection_reasons.append("sparse_root_dataset_unsupported")
                if matlab_empty and decoded_empty_shape is None:
                    rejection_reasons.append("empty_dimension_payload_invalid")
                if matlab_class in {
                    "double",
                    "single",
                    "int8",
                    "uint8",
                    "int16",
                    "uint16",
                    "int32",
                    "uint32",
                    "int64",
                    "uint64",
                } and not dtype_class_match:
                    rejection_reasons.append(
                        "MATLAB_numeric_class_HDF5_dtype_mismatch"
                    )
                result[name] = {
                    "object_type": "dataset",
                    "matlab_class": matlab_class,
                    "dtype": dtype_signature(raw.dtype),
                    "shape": tuple(int(item) for item in raw.shape),
                    "matlab_shape": (
                        decoded_empty_shape
                        if matlab_empty and decoded_empty_shape is not None
                        else tuple(reversed(tuple(int(item) for item in raw.shape)))
                    ),
                    "is_complex": bool(compound_complex or np.iscomplexobj(raw)),
                    "is_empty": bool(matlab_empty or raw.size == 0),
                    "matlab_empty_attribute": matlab_empty,
                    "matlab_empty_shape_decoded": (
                        decoded_empty_shape is not None if matlab_empty else True
                    ),
                    "is_sparse": matlab_sparse,
                    "is_global": matlab_global,
                    "dtype_matches_matlab_class": dtype_class_match,
                    "supported": not rejection_reasons,
                    "rejection_reasons": rejection_reasons,
                }
            else:
                result[name] = {
                    "object_type": "group",
                    "matlab_class": matlab_class,
                    "dtype": "GROUP",
                    "shape": (),
                    "matlab_shape": (),
                    "is_complex": False,
                    "is_empty": len(obj) == 0,
                    "matlab_empty_attribute": h5_boolean_attribute(
                        obj, "MATLAB_empty"
                    ),
                    "matlab_empty_shape_decoded": False,
                    "is_sparse": h5_boolean_attribute(obj, "MATLAB_sparse"),
                    "is_global": h5_boolean_attribute(obj, "MATLAB_global"),
                    "dtype_matches_matlab_class": False,
                    "supported": False,
                    "rejection_reasons": ["root_group_unsupported"],
                }
    return result


def inventory_records(value: Any, field: str) -> list[dict[str, Any]]:
    records = normalize_struct_list(value, field)
    required_fields = {
        "name",
        "class",
        "size",
        "bytes",
        "is_sparse",
        "is_complex",
        "is_global",
    }
    names: list[str] = []
    for index, record in enumerate(records, start=1):
        if set(record) != required_fields:
            raise ValueError(
                f"{field}[{index}] fields mismatch: expected={sorted(required_fields)}, "
                f"actual={sorted(record)}"
            )
        name = record.get("name")
        if not isinstance(name, str) or not name:
            raise ValueError(f"{field}[{index}] invalid variable name")
        matlab_class = record.get("class")
        if not isinstance(matlab_class, str) or not matlab_class:
            raise ValueError(f"{field}[{index}] invalid MATLAB class")
        size = record.get("size")
        if isinstance(size, int) and not isinstance(size, bool):
            size = [size]
        if not isinstance(size, list) or not size or any(
            not isinstance(item, int)
            or isinstance(item, bool)
            or item < 0
            for item in size
        ):
            raise ValueError(f"{field}[{index}] invalid size")
        byte_count = record.get("bytes")
        if (
            not isinstance(byte_count, int)
            or isinstance(byte_count, bool)
            or byte_count < 0
        ):
            raise ValueError(f"{field}[{index}] invalid bytes")
        for boolean_field in ("is_sparse", "is_complex", "is_global"):
            if not isinstance(record.get(boolean_field), bool):
                raise ValueError(
                    f"{field}[{index}] {boolean_field} must be a JSON boolean"
                )
        names.append(name)
    if len(names) != len(set(names)):
        raise ValueError(f"{field} contains duplicate variable names")
    return records


def compare_inventory_to_workspace(
    records: list[dict[str, Any]], path: Path, field: str
) -> dict[str, Any]:
    metadata = h5_workspace_metadata(path)
    inventory_by_name = {record["name"]: record for record in records}
    names_match = set(inventory_by_name) == set(metadata)
    variable_rows: list[dict[str, Any]] = []
    all_match = names_match
    for name in sorted(set(inventory_by_name) | set(metadata)):
        inventory = inventory_by_name.get(name)
        saved = metadata.get(name)
        if inventory is None or saved is None:
            variable_rows.append(
                {"name": name, "present_in_inventory": inventory is not None, "present_in_workspace": saved is not None, "match": False}
            )
            all_match = False
            continue
        inventory_size = tuple(int(item) for item in (inventory["size"] if isinstance(inventory["size"], list) else [inventory["size"]]))
        class_match = saved["matlab_class"] == inventory["class"]
        complex_match = saved["is_complex"] is inventory["is_complex"]
        sparse_match = saved["is_sparse"] is inventory["is_sparse"]
        global_match = saved["is_global"] is inventory["is_global"]
        shape_match = saved["matlab_shape"] == inventory_size
        inventory_empty = any(item == 0 for item in inventory_size)
        empty_match = saved["is_empty"] is inventory_empty
        supported = saved["supported"]
        variable_match = bool(
            supported
            and class_match
            and complex_match
            and sparse_match
            and global_match
            and shape_match
            and empty_match
        )
        all_match &= variable_match
        variable_rows.append(
            {
                "name": name,
                "class_match": class_match,
                "complex_match": complex_match,
                "sparse_match": sparse_match,
                "global_match": global_match,
                "shape_match": shape_match,
                "empty_match": empty_match,
                "supported_workspace_object": supported,
                "inventory_size": inventory_size,
                "workspace": saved,
                "match": variable_match,
            }
        )
    return {
        "field": field,
        "workspace": str(path),
        "names_match": names_match,
        "variable_count": len(metadata),
        "variables": variable_rows,
        "pass": bool(all_match),
    }


def scientific_mat_crosscheck(
    paths: dict[str, Path],
    status: dict[str, Any],
    status_names: list[str],
    final_inventory: list[dict[str, Any]],
    final_workspace: Path,
) -> dict[str, Any]:
    """Cross-check the selected science MAT against status, whos, and workspace."""
    status_scientific = status.get("scientific")
    if not isinstance(status_scientific, dict):
        return {
            "pass": False,
            "error": "status.scientific is not an object",
        }
    scientific_names_error = ""
    try:
        nested_names = normalize_string_list(
            status_scientific.get("available_variables"),
            "status.scientific.available_variables",
        )
    except Exception as error:
        nested_names = []
        scientific_names_error = f"{type(error).__name__}: {error}"
    names_unique = len(status_names) == len(set(status_names))
    nested_names_match = not scientific_names_error and nested_names == status_names
    scientific_expected = bool(status_names)
    scientific_exists = paths["scientific_mat"].is_file()
    existence_match = scientific_exists is scientific_expected
    details: dict[str, Any] = {
        "status_names": status_names,
        "nested_status_names": nested_names,
        "status_names_unique": names_unique,
        "nested_status_names_match": nested_names_match,
        "scientific_names_error": scientific_names_error,
        "scientific_expected": scientific_expected,
        "scientific_exists": scientific_exists,
        "existence_match": existence_match,
        "root_names": [],
        "root_names_exact": not scientific_expected,
        "selected_names_in_inventory": not scientific_expected,
        "selected_names_in_workspace": not scientific_expected,
        "variables": [],
    }
    if not scientific_expected:
        details["pass"] = bool(
            names_unique
            and nested_names_match
            and existence_match
            and not scientific_names_error
        )
        return details
    if not scientific_exists:
        details["pass"] = False
        return details

    try:
        scientific_metadata = h5_workspace_metadata(paths["scientific_mat"])
        workspace_metadata = h5_workspace_metadata(final_workspace)
    except Exception as error:
        details["metadata_error"] = f"{type(error).__name__}: {error}"
        details["pass"] = False
        return details
    inventory_by_name = {record["name"]: record for record in final_inventory}
    root_names = sorted(scientific_metadata)
    root_names_exact = set(root_names) == set(status_names)
    selected_names_in_inventory = set(status_names).issubset(inventory_by_name)
    selected_names_in_workspace = set(status_names).issubset(workspace_metadata)
    details.update(
        {
            "root_names": root_names,
            "root_names_exact": root_names_exact,
            "selected_names_in_inventory": selected_names_in_inventory,
            "selected_names_in_workspace": selected_names_in_workspace,
        }
    )
    metadata_fields = (
        "object_type",
        "matlab_class",
        "dtype",
        "shape",
        "matlab_shape",
        "is_complex",
        "is_empty",
        "matlab_empty_attribute",
        "matlab_empty_shape_decoded",
        "is_sparse",
        "is_global",
        "dtype_matches_matlab_class",
        "supported",
        "rejection_reasons",
    )
    all_variables_match = True
    variable_rows: list[dict[str, Any]] = []
    for name in status_names:
        scientific = scientific_metadata.get(name)
        workspace = workspace_metadata.get(name)
        inventory = inventory_by_name.get(name)
        if scientific is None or workspace is None or inventory is None:
            variable_rows.append(
                {
                    "name": name,
                    "scientific_present": scientific is not None,
                    "workspace_present": workspace is not None,
                    "inventory_present": inventory is not None,
                    "match": False,
                }
            )
            all_variables_match = False
            continue
        metadata_match = {
            field: scientific.get(field) == workspace.get(field)
            for field in metadata_fields
        }
        inventory_size = tuple(inventory["size"])
        inventory_match = {
            "matlab_class": scientific["matlab_class"] == inventory["class"],
            "matlab_shape": scientific["matlab_shape"] == inventory_size,
            "is_complex": scientific["is_complex"] is inventory["is_complex"],
            "is_sparse": scientific["is_sparse"] is inventory["is_sparse"],
            "is_global": scientific["is_global"] is inventory["is_global"],
            "is_empty": scientific["is_empty"]
            is any(item == 0 for item in inventory_size),
        }
        content_error = ""
        scientific_content_summary: dict[str, Any] = {}
        workspace_content_summary: dict[str, Any] = {}
        semantic_content_equal = False
        bitwise_content_equal = False
        try:
            scientific_content = h5_dataset_content_record(
                paths["scientific_mat"], name
            )
            workspace_content = h5_dataset_content_record(final_workspace, name)
            scientific_value = scientific_content.pop("value")
            workspace_value = workspace_content.pop("value")
            scientific_content_summary = scientific_content
            workspace_content_summary = workspace_content
            if (
                np.issubdtype(scientific_value.dtype, np.inexact)
                or np.issubdtype(workspace_value.dtype, np.inexact)
            ):
                semantic_content_equal = bool(
                    np.array_equal(
                        scientific_value,
                        workspace_value,
                        equal_nan=True,
                    )
                )
            else:
                semantic_content_equal = bool(
                    np.array_equal(scientific_value, workspace_value)
                )
            bitwise_content_equal = bool(
                scientific_content_summary == workspace_content_summary
            )
        except Exception as error:
            content_error = f"{type(error).__name__}: {error}"
        content_match = bool(
            not content_error
            and semantic_content_equal
            and bitwise_content_equal
        )
        variable_match = bool(
            scientific["object_type"] == "dataset"
            and scientific["supported"]
            and workspace["supported"]
            and all(metadata_match.values())
            and all(inventory_match.values())
            and content_match
        )
        all_variables_match &= variable_match
        variable_rows.append(
            {
                "name": name,
                "scientific": scientific,
                "workspace": workspace,
                "inventory": inventory,
                "scientific_workspace_metadata_match": metadata_match,
                "inventory_metadata_match": inventory_match,
                "scientific_content": scientific_content_summary,
                "workspace_content": workspace_content_summary,
                "semantic_content_equal": semantic_content_equal,
                "bitwise_content_equal": bitwise_content_equal,
                "content_error": content_error,
                "content_match": content_match,
                "match": variable_match,
            }
        )
    details["variables"] = variable_rows
    details["pass"] = bool(
        names_unique
        and nested_names_match
        and existence_match
        and root_names_exact
        and selected_names_in_inventory
        and selected_names_in_workspace
        and all_variables_match
        and not scientific_names_error
    )
    return details


def normalized_error_message(value: str) -> str:
    text = value.replace("\\", "/")
    text = re.sub(r"rep0[12]", "repXX", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def target_processes() -> list[dict[str, Any]]:
    token = str(BOARD_ROOT).casefold()
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding=[Console]::OutputEncoding; "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw|pdftoppm)\\.exe$'} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError("process query timed out after 30 seconds") from error
    stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
    if completed.returncode != 0 or stderr_text:
        raise RuntimeError(
            f"process query failed rc={completed.returncode}: {stderr_text}"
        )
    text = completed.stdout.decode("utf-8-sig", errors="replace").strip()
    if not text:
        return []
    raw = json.loads(text)
    if raw is None:
        return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise TypeError("process query did not return an object array")
    result = []
    for item in raw:
        pid = int(item.get("ProcessId") or -1)
        name = str(item.get("Name") or "")
        command_line = str(item.get("CommandLine") or "")
        if pid == os.getpid():
            continue
        if name.casefold() == "matlab.exe" or token in command_line.casefold():
            result.append(item)
    return result


def preflight(require_validation_absent: bool = True) -> dict[str, Any]:
    if Path(sys.executable).resolve() != EXPECTED_PYTHON.resolve():
        raise RuntimeError(f"wrong Python: {sys.executable}")
    if len(ROUTES) != 7 or len({route["route_id"] for route in ROUTES}) != 7:
        raise RuntimeError("expected seven unique routes")
    referenced = {
        route[key] for route in ROUTES for key in ("upstream", "candidate")
    }
    if referenced != set(SOURCES) or len(referenced) != 12:
        raise RuntimeError("route/source contract must cover exactly 12 unique sources")
    all_manifest_rows, freeze_summary = verify_input_freeze()
    source_mismatches = []
    manifest_rows = author_manifest_by_name(all_manifest_rows)
    for name, expected in SOURCES.items():
        path = AUTHOR_ROOT / name
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            source_mismatches.append((name, expected, actual))
        original = Path(manifest_rows[name]["source_absolute_path"])
        original_actual = sha256_file(original) if original.is_file() else "MISSING"
        if original_actual != expected:
            source_mismatches.append((str(original), expected, original_actual))
    if source_mismatches:
        raise RuntimeError(f"frozen source mismatch: {source_mismatches}")
    for relative, expected in STEP2_ANCHORS.items():
        path = BOARD_ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != expected:
            raise RuntimeError(f"step2 anchor mismatch: {relative}: {actual}")
    route7 = next(
        route
        for route in ROUTES
        if route["route_id"] == ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]
    )
    route7_formula_contract = evaluate_route7_formula_source_contract(route7)
    mutated_route7 = dict(route7)
    mutated_route7["sum_scope"] = "all_vectors"
    route7_formula_mutation = evaluate_route7_formula_source_contract(mutated_route7)
    mutation_rejected = bool(
        route7_formula_contract.get("pass") is True
        and route7_formula_mutation.get("pass") is False
        and route7_formula_mutation.get("failed_fields") == ["route.sum_scope"]
    )
    if route7_formula_contract.get("pass") is not True:
        raise RuntimeError(
            f"route7 frozen formula source contract failed: {route7_formula_contract}"
        )
    if not mutation_rejected:
        raise RuntimeError(
            "route7 all_vectors negative mutation was not uniquely rejected: "
            f"{route7_formula_mutation}"
        )
    attempt02_archive_audit = audit_attempt02_archive()
    if attempt02_archive_audit.get("pass") is not True:
        raise RuntimeError(
            f"attempt02 archive audit failed: {attempt02_archive_audit}"
        )
    if require_validation_absent and VALIDATION_ROOT.exists():
        raise FileExistsError(VALIDATION_ROOT)
    return {
        "status": "PREFLIGHT_PASS",
        "route_count": 7,
        "source_reference_count": 14,
        "unique_source_count": 12,
        "step2_anchor_count": len(STEP2_ANCHORS),
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        "input_row_count": len(all_manifest_rows),
        "input_category_counts": freeze_summary["category_counts"],
        "route7_formula_source_contract_pass": True,
        "route7_all_vectors_negative_mutation_rejected": True,
        "attempt02_archive_audit_schema_version": (
            attempt02_archive_audit["schema_version"]
        ),
        "attempt02_archive_audit_status": attempt02_archive_audit["status"],
        "attempt02_archive_audit_check_count": attempt02_archive_audit["check_count"],
        "matlab_executed_by_preflight": False,
    }


def expected_run_paths(route: dict[str, Any], replicate: str) -> dict[str, Path]:
    route_id = route["route_id"]
    work_dir = (TMP_ROOT / route_id / replicate / "work").resolve()
    output_dir = (RUN_ROOT / route_id / replicate).resolve()
    metadata_dir = output_dir / "metadata"
    workspace_dir = output_dir / "workspace"
    scientific_dir = output_dir / "scientific"
    log_dir = (LOG_ROOT / route_id / replicate).resolve()
    config_json = metadata_dir / "run_config.json"
    return {
        "work_dir": work_dir,
        "output_dir": output_dir,
        "metadata_dir": metadata_dir,
        "workspace_dir": workspace_dir,
        "scientific_dir": scientific_dir,
        "log_dir": log_dir,
        "config_json": config_json,
        "config_hash_file": metadata_dir / "run_config.sha256",
        "run_status_json": metadata_dir / "run_status.json",
        "variable_inventory_json": metadata_dir / "variable_inventory.json",
        "workspace_after_upstream": workspace_dir / "workspace_after_upstream.mat",
        "workspace_success": workspace_dir / "workspace_complete.mat",
        "workspace_failure": workspace_dir / "workspace_failure.mat",
        "scientific_mat": scientific_dir / "historical_energy_outputs.mat",
        "matlab_diary": log_dir / "matlab_diary.log",
        "error_report": log_dir / "error_report.txt",
        "matlab_command": log_dir / "matlab_command.txt",
        "matlab_stdout": log_dir / "matlab_stdout.log",
        "matlab_stderr": log_dir / "matlab_stderr.log",
        "shell_combined_log": log_dir / "shell_stdout_stderr.log",
        "process_exit_json": metadata_dir / "process_exit.json",
        "upstream_file": work_dir / route["upstream"],
        "candidate_mlx": work_dir / route["candidate"],
    }


def expected_config_path_fields(paths: dict[str, Path]) -> dict[str, Path]:
    return {
        "work_dir": paths["work_dir"],
        "output_dir": paths["output_dir"],
        "log_dir": paths["log_dir"],
        "upstream_file": paths["upstream_file"],
        "candidate_mlx": paths["candidate_mlx"],
        "status_json": paths["run_status_json"],
        "config_hash_file": paths["config_hash_file"],
        "variable_inventory_json": paths["variable_inventory_json"],
        "workspace_after_upstream": paths["workspace_after_upstream"],
        "workspace_success": paths["workspace_success"],
        "workspace_failure": paths["workspace_failure"],
        "scientific_mat": paths["scientific_mat"],
        "diary_file": paths["matlab_diary"],
        "error_report": paths["error_report"],
        "matlab_command_txt": paths["matlab_command"],
        "shell_log": paths["shell_combined_log"],
        "matlab_stdout_log": paths["matlab_stdout"],
        "matlab_stderr_log": paths["matlab_stderr"],
        "process_exit_json": paths["process_exit_json"],
    }


def inspect_hdf5_files(paths: dict[str, Path], required_names: set[str]) -> dict[str, Any]:
    details: dict[str, Any] = {}
    passed = True
    for name in sorted(required_names):
        path = paths[name]
        record: dict[str, Any] = {
            "path": str(path),
            "exists": path.is_file(),
            "readable": False,
            "root_variables": [],
            "error": "",
        }
        if path.is_file():
            try:
                with h5py.File(path, "r") as handle:
                    record["root_variables"] = sorted(
                        key for key in handle.keys() if key != "#refs#"
                    )
                    record["readable"] = True
            except Exception as error:
                record["error"] = f"{type(error).__name__}: {error}"
        passed &= bool(record["exists"] and record["readable"])
        details[name] = record
    return {"pass": bool(passed), "files": details}


def validate_artifact_seal(
    exit_record: dict[str, Any],
    paths: dict[str, Path],
    runner_success: bool,
    author_failure: bool,
    failed_stage: str,
    scientific_expected: bool,
) -> dict[str, Any]:
    always_required = {
        "config_json",
        "config_hash_file",
        "run_status_json",
        "variable_inventory_json",
        "matlab_diary",
        "matlab_command",
        "matlab_stdout",
        "matlab_stderr",
        "shell_combined_log",
    }
    success_required = {"workspace_after_upstream", "workspace_success"}
    failure_required = {"workspace_failure", "error_report"}
    if author_failure and failed_stage == "CANDIDATE_ORIGINAL_MLX":
        failure_required.add("workspace_after_upstream")
    expected_required = {
        name: bool(
            name in always_required
            or (name == "scientific_mat" and scientific_expected)
            or (runner_success and name in success_required)
            or (author_failure and name in failure_required)
        )
        for name in ARTIFACT_ORDER
    }
    expected_exists = dict(expected_required)
    seal = normalize_struct_list(exit_record.get("artifact_seal"), "artifact_seal")
    names = [item.get("name") for item in seal]
    item_rows: list[dict[str, Any]] = []
    passed = names == list(ARTIFACT_ORDER)
    for name in ARTIFACT_ORDER:
        matches = [item for item in seal if item.get("name") == name]
        if len(matches) != 1:
            item_rows.append(
                {"name": name, "record_count": len(matches), "match": False}
            )
            passed = False
            continue
        item = matches[0]
        path = paths[name]
        exists = path.is_file()
        size = path.stat().st_size if exists else -1
        digest = sha256_file(path) if exists else ""
        item_pass = bool(
            exact_absolute_path(item.get("path"), path)
            and item.get("required") is expected_required[name]
            and item.get("exists") is expected_exists[name]
            and exists is expected_exists[name]
            and item.get("size_bytes") == size
            and item.get("sha256") == digest
            and (not expected_required[name] or (exists and size >= 0 and bool(digest)))
            and (
                not expected_required[name]
                or name == "matlab_stderr"
                or size > 0
            )
        )
        passed &= item_pass
        item_rows.append(
            {
                "name": name,
                "path": str(path),
                "expected_required": expected_required[name],
                "exists": exists,
                "size_bytes": size,
                "sha256": digest,
                "sealed_record": item,
                "match": item_pass,
            }
        )

    stdout = paths["matlab_stdout"].read_bytes() if paths["matlab_stdout"].is_file() else b""
    stderr = paths["matlab_stderr"].read_bytes() if paths["matlab_stderr"].is_file() else b""
    expected_combined = (
        b"===== STDOUT =====\n"
        + stdout
        + b"\n===== STDERR =====\n"
        + stderr
        + b"\n"
    )
    actual_combined = (
        paths["shell_combined_log"].read_bytes()
        if paths["shell_combined_log"].is_file()
        else b""
    )
    stream_checks = {
        "stdout_size": exit_record.get("stdout_size_bytes") == len(stdout),
        "stderr_size": exit_record.get("stderr_size_bytes") == len(stderr),
        "stdout_hash": exit_record.get("stdout_sha256")
        == hashlib.sha256(stdout).hexdigest().upper(),
        "stderr_hash": exit_record.get("stderr_sha256")
        == hashlib.sha256(stderr).hexdigest().upper(),
        "combined_hash": exit_record.get("combined_log_sha256")
        == hashlib.sha256(actual_combined).hexdigest().upper(),
        "combined_exact_bytes": actual_combined == expected_combined,
        "stdout_path": exact_absolute_path(
            exit_record.get("matlab_stdout_path"), paths["matlab_stdout"]
        ),
        "stderr_path": exact_absolute_path(
            exit_record.get("matlab_stderr_path"), paths["matlab_stderr"]
        ),
        "combined_path": exact_absolute_path(
            exit_record.get("combined_log_path"), paths["shell_combined_log"]
        ),
        "executor_runtime_log_hash_gate": exit_record.get(
            "runtime_log_hashes_match"
        )
        is True,
    }
    passed &= all(stream_checks.values())
    recomputed_all_required = all(
        (not row.get("expected_required"))
        or (row.get("exists") and row.get("size_bytes", -1) >= 0 and row.get("sha256"))
        for row in item_rows
        if row.get("record_count", 1) == 1
    ) and len(item_rows) == len(ARTIFACT_ORDER)
    required_gate = (
        exit_record.get("all_required_artifacts_sealed") is recomputed_all_required
        and recomputed_all_required
        and exit_record.get("artifact_exclusivity_match") is True
        and exit_record.get("expected_artifact_exists") == expected_exists
    )
    passed &= required_gate
    return {
        "pass": bool(passed),
        "names_in_order": names,
        "items": item_rows,
        "stream_checks": stream_checks,
        "recomputed_all_required_artifacts_sealed": recomputed_all_required,
        "recorded_all_required_artifacts_sealed": exit_record.get(
            "all_required_artifacts_sealed"
        ),
    }


def audit_attempt01_archive() -> dict[str, Any]:
    """Independently seal and interpret the preserved V1 PID-contract failure."""
    audit: dict[str, Any] = {
        "schema_version": "BOARD21_STEP3_ATTEMPT01_ARCHIVE_AUDIT_V1",
        "archive_root": str(ATTEMPT01_ROOT.resolve()),
        "status": "FAIL",
        "pass": False,
        "checks": {},
        "errors": [],
    }
    checks: dict[str, bool] = audit["checks"]

    def record(name: str, passed: Any) -> None:
        checks[name] = bool(passed)

    try:
        metadata_actual = {
            name: sha256_file(ATTEMPT01_ROOT / name)
            if (ATTEMPT01_ROOT / name).is_file()
            else "MISSING"
            for name in ATTEMPT01_METADATA_SHA256
        }
        audit["metadata_sha256_expected"] = ATTEMPT01_METADATA_SHA256
        audit["metadata_sha256_actual"] = metadata_actual
        record(
            "three_pinned_archive_metadata_hashes_match",
            metadata_actual == ATTEMPT01_METADATA_SHA256,
        )

        manifest_path = ATTEMPT01_ROOT / "attempt_file_manifest.csv"
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            manifest_reader = csv.DictReader(stream)
            manifest_fields = list(manifest_reader.fieldnames or [])
            manifest_rows = list(manifest_reader)
        expected_manifest_fields = [
            "logical_root",
            "relative_path",
            "size_bytes",
            "sha256",
        ]
        record("artifact_manifest_fields_exact", manifest_fields == expected_manifest_fields)
        manifest_seen: set[tuple[str, str]] = set()
        manifest_expected_files: set[str] = set()
        manifest_row_errors: list[dict[str, Any]] = []
        manifest_total_size = 0
        for row_index, row in enumerate(manifest_rows, start=1):
            reasons: list[str] = []
            logical_root = str(row.get("logical_root", ""))
            relative_text = str(row.get("relative_path", ""))
            pure_relative = PurePosixPath(relative_text)
            relative_safe = bool(
                relative_text
                and "\\" not in relative_text
                and not pure_relative.is_absolute()
                and relative_text == pure_relative.as_posix()
                and all(part not in {"", ".", ".."} for part in pure_relative.parts)
            )
            if not relative_safe:
                reasons.append("unsafe_or_noncanonical_relative_path")
            root = ATTEMPT01_LOGICAL_ROOTS.get(logical_root)
            if root is None:
                reasons.append("unknown_logical_root")
            identity = (logical_root, relative_text)
            if identity in manifest_seen:
                reasons.append("duplicate_manifest_identity")
            manifest_seen.add(identity)
            size_text = str(row.get("size_bytes", ""))
            try:
                expected_size = int(size_text)
                if expected_size < 0 or size_text != str(expected_size):
                    raise ValueError("size is not canonical nonnegative decimal")
            except Exception:
                expected_size = -1
                reasons.append("invalid_size_bytes")
            expected_sha256 = row.get("sha256")
            if not is_upper_sha256_text(expected_sha256):
                reasons.append("invalid_sha256")
            candidate: Path | None = None
            if root is not None and relative_safe:
                candidate = root.joinpath(*pure_relative.parts)
                if not is_within(candidate, root):
                    reasons.append("path_escapes_logical_root")
                elif not candidate.is_file():
                    reasons.append("file_missing")
                else:
                    actual_size = candidate.stat().st_size
                    actual_sha256 = sha256_file(candidate)
                    if actual_size != expected_size:
                        reasons.append("size_mismatch")
                    if actual_sha256 != expected_sha256:
                        reasons.append("sha256_mismatch")
                    manifest_expected_files.add(
                        candidate.resolve().relative_to(ATTEMPT01_ROOT.resolve()).as_posix()
                    )
            if expected_size >= 0:
                manifest_total_size += expected_size
            if reasons:
                manifest_row_errors.append(
                    {
                        "row": row_index,
                        "logical_root": logical_root,
                        "relative_path": relative_text,
                        "reasons": reasons,
                    }
                )
        actual_artifact_files = {
            path.resolve().relative_to(ATTEMPT01_ROOT.resolve()).as_posix()
            for root in ATTEMPT01_LOGICAL_ROOTS.values()
            for path in root.rglob("*")
            if path.is_file()
        }
        artifact_file_set_missing = sorted(
            manifest_expected_files - actual_artifact_files
        )
        artifact_file_set_unexpected = sorted(
            actual_artifact_files - manifest_expected_files
        )
        audit["artifact_manifest"] = {
            "row_count": len(manifest_rows),
            "total_size_bytes": manifest_total_size,
            "row_errors": manifest_row_errors,
            "actual_artifact_file_count": len(actual_artifact_files),
            "missing_files": artifact_file_set_missing,
            "unexpected_files": artifact_file_set_unexpected,
        }
        record(
            "artifact_manifest_89_rows_all_sizes_and_hashes_match",
            len(manifest_rows) == 89
            and len(manifest_seen) == 89
            and manifest_total_size == 1_732_889
            and not manifest_row_errors,
        )
        record(
            "artifact_manifest_file_set_closed",
            manifest_expected_files == actual_artifact_files,
        )

        tool_manifest_path = ATTEMPT01_ROOT / "tool_snapshot_manifest.csv"
        with tool_manifest_path.open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            tool_reader = csv.DictReader(stream)
            tool_fields = list(tool_reader.fieldnames or [])
            tool_rows = list(tool_reader)
        expected_tool_fields = ["name", "relative_path", "size_bytes", "sha256"]
        tool_row_errors: list[dict[str, Any]] = []
        expected_tool_files: set[str] = set()
        for index, name in enumerate(INSTRUMENT_ORDER):
            if index >= len(tool_rows):
                tool_row_errors.append(
                    {"index": index + 1, "name": name, "reason": "row_missing"}
                )
                continue
            row = tool_rows[index]
            relative_path = f"tools_snapshot/{name}"
            candidate = ATTEMPT01_ROOT / "tools_snapshot" / name
            try:
                size_value = int(str(row.get("size_bytes", "")))
                size_canonical = str(size_value) == str(row.get("size_bytes", ""))
            except Exception:
                size_value = -1
                size_canonical = False
            row_pass = bool(
                row.get("name") == name
                and row.get("relative_path") == relative_path
                and row.get("sha256") == ATTEMPT01_TOOL_SHA256[name]
                and size_canonical
                and size_value >= 0
                and candidate.is_file()
                and candidate.stat().st_size == size_value
                and sha256_file(candidate) == ATTEMPT01_TOOL_SHA256[name]
            )
            if not row_pass:
                tool_row_errors.append(
                    {"index": index + 1, "name": name, "row": row}
                )
            expected_tool_files.add(relative_path)
        actual_tool_files = {
            path.resolve().relative_to(ATTEMPT01_ROOT.resolve()).as_posix()
            for path in (ATTEMPT01_ROOT / "tools_snapshot").rglob("*")
            if path.is_file()
        }
        audit["tool_snapshot"] = {
            "row_count": len(tool_rows),
            "row_errors": tool_row_errors,
            "expected_sha256": ATTEMPT01_TOOL_SHA256,
            "actual_files": sorted(actual_tool_files),
        }
        record("tool_manifest_fields_exact", tool_fields == expected_tool_fields)
        record(
            "five_old_tool_snapshots_exact",
            len(tool_rows) == 5
            and not tool_row_errors
            and actual_tool_files == expected_tool_files,
        )

        summary = load_json(ATTEMPT01_ROOT / "attempt_summary.json")
        expected_moved_roots = [
            {
                "destination": str(ATTEMPT01_LOGICAL_ROOTS[logical].resolve()),
                "logical_root": logical,
                "source_before_archive": str(source.resolve()),
            }
            for logical, source in (
                ("outputs_step3_stage", STAGE_ROOT),
                ("outputs_step3_runs", RUN_ROOT),
                ("outputs_step3_orchestration", ORCHESTRATION_ROOT),
                ("tmp_step3_runs", TMP_ROOT),
                ("logs_step3_runs", LOG_ROOT),
            )
        ]
        semantic_diagnosis = summary.get("semantic_diagnosis")
        semantic_checks = (
            semantic_diagnosis.get("checks")
            if isinstance(semantic_diagnosis, dict)
            else None
        )
        expected_semantic_check_names = {
            "correct_interruption_point",
            "executor_rejected_evidence",
            "infrastructure_failure",
            "launcher_and_matlab_pid_are_positive_and_distinct",
            "matlab_exit_zero",
            "one_run_executed",
            "only_environment_contract_failed",
            "orchestration_failed",
            "orchestration_schema_v2",
            "runner_completed_science",
            "thirteen_runs_unstarted",
            "zero_final_processes",
        }
        process_before = summary.get("process_before_archive")
        process_after = summary.get("process_after_archive")
        empty_hash = hashlib.sha256(b"").hexdigest().upper()

        def archived_process_record_pass(value: Any) -> bool:
            return bool(
                isinstance(value, dict)
                and value.get("returncode") == 0
                and value.get("stderr_size_bytes") == 0
                and value.get("stderr_sha256") == empty_hash
                and value.get("target_processes") == []
                and isinstance(value.get("stdout_size_bytes"), int)
                and not isinstance(value.get("stdout_size_bytes"), bool)
                and value.get("stdout_size_bytes") > 0
                and is_upper_sha256_text(value.get("stdout_sha256"))
            )

        summary_semantics_pass = bool(
            summary.get("schema_version") == "BOARD21_STEP3_ATTEMPT_ARCHIVE_V1"
            and summary.get("attempt_id")
            == "step3_attempt01_20260826_pid_contract_failure"
            and summary.get("archive_status")
            == "FAILED_INFRASTRUCTURE_ATTEMPT_PRESERVED"
            and summary.get("attempt_file_manifest")
            == "attempt_file_manifest.csv"
            and summary.get("tool_snapshot_manifest")
            == "tool_snapshot_manifest.csv"
            and summary.get("artifact_file_count") == 89
            and summary.get("artifact_total_size_bytes") == 1_732_889
            and summary.get("tool_snapshot_count") == 5
            and summary.get("tool_snapshot_sha256") == ATTEMPT01_TOOL_SHA256
            and summary.get("moved_roots") == expected_moved_roots
            and summary.get("internal_absolute_paths_are_historical") is True
            and summary.get("standard_step3_roots_absent_after_archive") is True
            and summary.get("step3_validation_was_absent") is True
            and isinstance(semantic_diagnosis, dict)
            and semantic_diagnosis.get("launcher_pid") == 9232
            and semantic_diagnosis.get("matlab_pid") == 27592
            and semantic_diagnosis.get("false_status_contract_checks")
            == ["environment"]
            and isinstance(semantic_checks, dict)
            and set(semantic_checks) == expected_semantic_check_names
            and all(value is True for value in semantic_checks.values())
            and archived_process_record_pass(process_before)
            and archived_process_record_pass(process_after)
        )
        record("archive_summary_semantics_exact", summary_semantics_pass)

        orchestration_path = (
            ATTEMPT01_LOGICAL_ROOTS["outputs_step3_orchestration"]
            / "run_all_summary.json"
        )
        exit_path = (
            ATTEMPT01_LOGICAL_ROOTS["outputs_step3_runs"]
            / "reference15_pd19_energy"
            / "rep01"
            / "metadata"
            / "process_exit.json"
        )
        status_path = exit_path.with_name("run_status.json")
        orchestration = load_json(orchestration_path)
        exit_record = load_json(exit_path)
        status = load_json(status_path)
        route_records = normalize_struct_list(
            orchestration.get("route_process_records"),
            "attempt01.route_process_records",
        )
        route_record = route_records[0] if len(route_records) == 1 else {}
        expected_unstarted = [
            {"route_id": route_id, "replicate": replicate}
            for route_id, replicate in EXPECTED_RUN_ORDER[1:]
        ]
        expected_query_names = [
            "00__initial",
            "01__reference15_pd19_energy__rep01__before",
            "01__reference15_pd19_energy__rep01__after",
            "99__final",
        ]
        process_query_records = normalize_struct_list(
            orchestration.get("process_query_records"),
            "attempt01.process_query_records",
        )
        process_queries_pass = bool(
            [item.get("query_name") for item in process_query_records]
            == expected_query_names
            and all(
                item.get("ok") is True
                and item.get("timed_out") is False
                and item.get("filtered_process_count") == 0
                and item.get("processes") == []
                for item in process_query_records
            )
        )
        subprocess_records = normalize_struct_list(
            orchestration.get("subprocess_records"),
            "attempt01.subprocess_records",
        )
        subprocess_semantics_pass = bool(
            [item.get("name") for item in subprocess_records]
            == [
                "stager_dry_run",
                "stager_actual",
                "01__reference15_pd19_energy__rep01",
            ]
            and [item.get("returncode") for item in subprocess_records]
            == [0, 0, 2]
            and all(item.get("timed_out") is False for item in subprocess_records)
        )
        old_orchestration_pass = bool(
            orchestration.get("schema_version")
            == "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V2"
            and orchestration.get("status") == "FAIL"
            and orchestration.get("expected_run_count") == 14
            and orchestration.get("executed_run_count") == 1
            and orchestration.get("unstarted_runs") == expected_unstarted
            and orchestration.get("infrastructure_failure") is True
            and orchestration.get("interruption_point")
            == "01__reference15_pd19_energy__rep01__INFRASTRUCTURE_FAILURE"
            and orchestration.get("terminal_error") == {}
            and orchestration.get("final_target_process_count") == 0
            and orchestration.get("final_target_processes") == []
            and orchestration.get("matlab_process_count") == 0
            and len(route_records) == 1
            and process_queries_pass
            and subprocess_semantics_pass
        )
        record("old_orchestration_one_run_and_thirteen_unstarted", old_orchestration_pass)

        status_contract_checks = exit_record.get("status_contract_checks")
        false_status_checks = (
            sorted(
                name
                for name, value in status_contract_checks.items()
                if value is False
            )
            if isinstance(status_contract_checks, dict)
            else []
        )
        status_check_values_are_boolean = bool(
            isinstance(status_contract_checks, dict)
            and status_contract_checks
            and all(type(value) is bool for value in status_contract_checks.values())
        )
        status_environment = status.get("environment")
        available_scientific = status.get("available_scientific_variables")
        status_scientific = status.get("scientific")
        expected_required_audit = []
        for name, count in zip(
            REQUIRED_FINAL,
            [*ROUTES[0]["lengths"], 1, 1, 1, 1, 1],
            strict=True,
        ):
            expected_required_audit.append(
                {
                    "name": name,
                    "matlab_class": "double",
                    "is_double": True,
                    "is_real": True,
                    "is_dense": True,
                    "is_global": False,
                    "is_finite": True,
                    "numel": count,
                    "storage_contract_pass": True,
                }
            )
        runner_science_pass = bool(
            isinstance(status_scientific, dict)
            and status_scientific.get("required_present") is True
            and status_scientific.get("missing_required") == []
            and status_scientific.get("energy_lengths") == ROUTES[0]["lengths"]
            and status_scientific.get("expected_energy_lengths")
            == ROUTES[0]["lengths"]
            and status_scientific.get("lengths_match") is True
            and status_scientific.get("all_finite") is True
            and status_scientific.get("required_variables_valid") is True
            and status_scientific.get("required_variable_audit")
            == expected_required_audit
            and status_scientific.get("summary_scalars_valid") is True
            and isinstance(available_scientific, list)
            and status_scientific.get("available_variables")
            == available_scientific
            and exit_record.get("scientific_variables") == available_scientific
            and exit_record.get("scientific_variable_count")
            == len(available_scientific)
        )
        one_success_only_environment_failed = bool(
            status.get("schema_version") == "BOARD21_STEP3_ROUTE_STATUS_V1"
            and status.get("route_id") == "reference15_pd19_energy"
            and status.get("replicate") == "rep01"
            and status.get("execution_status") == "EXECUTION_SUCCESS"
            and status.get("evidence_status") == "PASS"
            and status.get("final_status")
            == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
            and status.get("process_exit_semantics") == "ZERO"
            and status.get("error_origin") == "NONE"
            and status.get("failed_stage") == ""
            and status.get("capture_errors") == []
            and isinstance(status_environment, dict)
            and is_strict_positive_int(status_environment.get("pid"))
            and status_environment.get("pid") == 27592
            and exit_record.get("schema_version")
            == "BOARD21_STEP3_PROCESS_EXIT_V1"
            and exit_record.get("pid") == 9232
            and is_strict_positive_int(exit_record.get("pid"))
            and exit_record.get("pid") != status_environment.get("pid")
            and exit_record.get("returncode") == 0
            and exit_record.get("timed_out") is False
            and exit_record.get("runner_execution_status")
            == "EXECUTION_SUCCESS"
            and exit_record.get("runner_evidence_status") == "PASS"
            and exit_record.get("runner_final_status")
            == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
            and exit_record.get("runner_success_contract") is True
            and status_check_values_are_boolean
            and false_status_checks == ["environment"]
            and exit_record.get("status_contract_pass") is False
            and exit_record.get("status_contract_error") == ""
            and exit_record.get("evidence_capture_ok") is False
            and exit_record.get("artifact_exclusivity_match") is True
            and exit_record.get("all_required_artifacts_sealed") is True
            and exit_record.get("runtime_log_hashes_match") is True
            and exit_record.get("orchestration_status")
            == "ZERO_EXIT_STATUS_MISMATCH"
            and exit_record.get("status_json_sha256") == sha256_file(status_path)
            and runner_science_pass
        )
        record(
            "one_author_success_rejected_only_by_old_environment_pid_gate",
            one_success_only_environment_failed,
        )

        route_record_pass = bool(
            route_record.get("order") == 1
            and route_record.get("route_id") == "reference15_pd19_energy"
            and route_record.get("replicate") == "rep01"
            and route_record.get("executor_returncode") == 2
            and route_record.get("executor_timed_out") is False
            and route_record.get("executor_status_contract_pass") is False
            and route_record.get("executor_artifact_exclusivity_match") is True
            and route_record.get("executor_all_required_artifacts_sealed") is True
            and route_record.get("executor_runtime_log_hashes_match") is True
            and route_record.get("matlab_returncode") == 0
            and route_record.get("evidence_capture_ok") is False
            and route_record.get("orchestration_status")
            == "ZERO_EXIT_STATUS_MISMATCH"
            and route_record.get("target_processes_before") == []
            and route_record.get("target_processes_after") == []
        )
        record("old_run_all_route_record_matches_pid_failure", route_record_pass)

        executor_stdout_path = (
            ATTEMPT01_LOGICAL_ROOTS["outputs_step3_orchestration"]
            / "subprocess_captures"
            / "01__reference15_pd19_energy__rep01.stdout.log"
        )
        executor_stdout = executor_stdout_path.read_bytes()
        executor_terminal = terminal_json_from_bytes(
            executor_stdout, "attempt01 executor stdout"
        )
        executor_terminal_match = bool(
            executor_terminal == exit_record
            and route_record.get("executor_terminal_json_match") is True
            and route_record.get("executor_stdout_sha256")
            == hashlib.sha256(executor_stdout).hexdigest().upper()
            and route_record.get("process_exit_json_sha256")
            == sha256_file(exit_path)
        )
        record(
            "archived_executor_stdout_terminal_json_equals_process_exit",
            executor_terminal_match,
        )

        scientific_path = (
            ATTEMPT01_LOGICAL_ROOTS["outputs_step3_runs"]
            / "reference15_pd19_energy"
            / "rep01"
            / "scientific"
            / "historical_energy_outputs.mat"
        )
        science_records = {
            name: finite_numeric_record(scientific_path, name)
            for name in REQUIRED_FINAL
        }
        science_lengths = [
            int(np.asarray(science_records[name]["value"]).size)
            for name in ("E_total", "E_total_guyan", "E_total_cb")
        ]
        orig = np.asarray(
            science_records["E_total"]["value"], dtype=np.float64
        ).reshape(-1)
        guyan = np.asarray(
            science_records["E_total_guyan"]["value"], dtype=np.float64
        ).reshape(-1)
        cb = np.asarray(
            science_records["E_total_cb"]["value"], dtype=np.float64
        ).reshape(-1)
        retained = np.asarray(ROUTES[0]["retained_zero_based"], dtype=int)
        recomputed_sums = {
            "energy_sum_orig": float(np.sum(orig[retained])),
            "energy_sum_guyan": float(np.sum(guyan)),
            "energy_sum_cb": float(np.sum(cb[retained])),
        }
        stored_sums = {
            name: scalar_from_record(science_records[name], name)
            for name in ("energy_sum_orig", "energy_sum_guyan", "energy_sum_cb")
        }
        denominator = recomputed_sums["energy_sum_orig"]
        recomputed_totals = {
            "total_increase_guyan": (
                recomputed_sums["energy_sum_guyan"]
                - recomputed_sums["energy_sum_orig"]
            )
            / denominator
            * 100.0,
            "total_increase_cb": (
                recomputed_sums["energy_sum_cb"]
                - recomputed_sums["energy_sum_orig"]
            )
            / denominator
            * 100.0,
        }
        stored_totals = {
            name: scalar_from_record(science_records[name], name)
            for name in ("total_increase_guyan", "total_increase_cb")
        }
        sum_comparisons = {
            name: strict_abs_rel_comparison(stored_sums[name], expected)
            for name, expected in recomputed_sums.items()
        }
        total_comparisons = {
            name: strict_abs_rel_comparison(stored_totals[name], expected)
            for name, expected in recomputed_totals.items()
        }
        archived_science_formula_pass = bool(
            science_lengths == ROUTES[0]["lengths"]
            and denominator != 0.0
            and math.isfinite(denominator)
            and all(item["pass"] for item in sum_comparisons.values())
            and all(item["pass"] for item in total_comparisons.values())
        )
        audit["archived_science_formula"] = {
            "lengths": science_lengths,
            "stored_sums": stored_sums,
            "recomputed_sums": recomputed_sums,
            "sum_comparisons": sum_comparisons,
            "stored_totals": stored_totals,
            "recomputed_totals": recomputed_totals,
            "total_comparisons": total_comparisons,
        }
        record(
            "archived_scientific_mat_independent_formula_recomputation",
            archived_science_formula_pass,
        )

        archived_status_files = list(
            ATTEMPT01_LOGICAL_ROOTS["outputs_step3_runs"].rglob(
                "run_status.json"
            )
        )
        archived_exit_files = list(
            ATTEMPT01_LOGICAL_ROOTS["outputs_step3_runs"].rglob(
                "process_exit.json"
            )
        )
        record(
            "exactly_one_archived_author_execution_record",
            archived_status_files == [status_path]
            and archived_exit_files == [exit_path],
        )
        record(
            "archived_process_boundaries_zero",
            process_queries_pass
            and orchestration.get("final_target_process_count") == 0
            and orchestration.get("final_target_processes") == []
            and archived_process_record_pass(process_before)
            and archived_process_record_pass(process_after),
        )

        top_level_files = set(ATTEMPT01_METADATA_SHA256)
        expected_archive_files = (
            top_level_files | manifest_expected_files | expected_tool_files
        )
        actual_archive_files = {
            path.resolve().relative_to(ATTEMPT01_ROOT.resolve()).as_posix()
            for path in ATTEMPT01_ROOT.rglob("*")
            if path.is_file()
        }
        archive_missing = sorted(expected_archive_files - actual_archive_files)
        archive_unexpected = sorted(actual_archive_files - expected_archive_files)
        archive_links = sorted(
            path.resolve().relative_to(ATTEMPT01_ROOT.resolve()).as_posix()
            for path in ATTEMPT01_ROOT.rglob("*")
            if path.is_symlink()
        )
        audit["archive_closure"] = {
            "expected_file_count": len(expected_archive_files),
            "actual_file_count": len(actual_archive_files),
            "missing_files": archive_missing,
            "unexpected_files": archive_unexpected,
            "symbolic_links": archive_links,
        }
        record(
            "entire_archive_file_set_closed",
            actual_archive_files == expected_archive_files and not archive_links,
        )
    except Exception as error:
        audit["errors"].append(f"{type(error).__name__}: {error}")
        audit["traceback"] = traceback.format_exc()

    audit_pass = bool(checks and all(checks.values()) and not audit["errors"])
    audit["pass"] = audit_pass
    audit["status"] = "PASS" if audit_pass else "FAIL"
    audit["check_count"] = len(checks)
    audit["failed_checks"] = sorted(
        name for name, passed in checks.items() if not passed
    )
    return audit


def ordinary_tree_inventory(root: Path) -> dict[str, Any]:
    files: set[str] = set()
    directories: set[str] = set()
    links_or_junctions: list[str] = []
    special_nodes: list[str] = []
    if not root.is_dir() or root.is_symlink() or root.is_junction():
        return {
            "root_is_ordinary_directory": False,
            "files": files,
            "directories": directories,
            "links_or_junctions": [str(root)],
            "special_nodes": special_nodes,
        }
    for current_text, directory_names, file_names in os.walk(
        root, topdown=True, followlinks=False
    ):
        current = Path(current_text)
        retained_directories: list[str] = []
        for name in directory_names:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or path.is_junction():
                links_or_junctions.append(relative)
            elif path.is_dir():
                directories.add(relative)
                retained_directories.append(name)
            else:
                special_nodes.append(relative)
        directory_names[:] = retained_directories
        for name in file_names:
            path = current / name
            relative = path.relative_to(root).as_posix()
            if path.is_symlink() or path.is_junction():
                links_or_junctions.append(relative)
            elif path.is_file():
                files.add(relative)
            else:
                special_nodes.append(relative)
    return {
        "root_is_ordinary_directory": True,
        "files": files,
        "directories": directories,
        "links_or_junctions": sorted(links_or_junctions),
        "special_nodes": sorted(special_nodes),
    }


def audit_attempt02_archive() -> dict[str, Any]:
    audit: dict[str, Any] = {
        "schema_version": "BOARD21_STEP3_ATTEMPT02_ARCHIVE_AUDIT_V1",
        "archive_root": str(ATTEMPT02_ROOT.resolve()),
        "attempt_id": "step3_attempt02_20260826_validator_sum_scope_contract_failure",
        "status": "FAIL",
        "pass": False,
        "checks": {},
        "errors": [],
    }
    checks: dict[str, bool] = audit["checks"]

    def record(name: str, passed: Any) -> None:
        checks[name] = bool(passed)

    try:
        csv.field_size_limit(2**31 - 1)
        tree = ordinary_tree_inventory(ATTEMPT02_ROOT)
        record(
            "archive_root_ordinary_no_links",
            tree["root_is_ordinary_directory"]
            and not tree["links_or_junctions"]
            and not tree["special_nodes"],
        )

        metadata_actual = {
            name: sha256_file(ATTEMPT02_ROOT / name)
            if (ATTEMPT02_ROOT / name).is_file()
            else "MISSING"
            for name in ATTEMPT02_METADATA_SHA256
        }
        audit["metadata_sha256_expected"] = ATTEMPT02_METADATA_SHA256
        audit["metadata_sha256_actual"] = metadata_actual
        record(
            "three_pinned_metadata_hashes_match",
            metadata_actual == ATTEMPT02_METADATA_SHA256,
        )

        manifest_path = ATTEMPT02_ROOT / "attempt_file_manifest.csv"
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            manifest_reader = csv.DictReader(stream)
            manifest_fields = list(manifest_reader.fieldnames or [])
            manifest_rows = list(manifest_reader)
        expected_manifest_fields = [
            "logical_root",
            "relative_path",
            "size_bytes",
            "sha256",
        ]
        manifest_seen: set[tuple[str, str]] = set()
        manifest_expected_files: set[str] = set()
        manifest_row_errors: list[dict[str, Any]] = []
        root_stats = {
            logical: {"file_count": 0, "total_size_bytes": 0}
            for logical in ATTEMPT02_LOGICAL_ROOTS
        }
        for index, row in enumerate(manifest_rows, start=1):
            reasons: list[str] = []
            logical_root = str(row.get("logical_root", ""))
            relative_text = str(row.get("relative_path", ""))
            pure_relative = PurePosixPath(relative_text)
            relative_safe = bool(
                relative_text
                and not pure_relative.is_absolute()
                and relative_text == pure_relative.as_posix()
                and all(part not in {"", ".", ".."} for part in pure_relative.parts)
            )
            if not relative_safe:
                reasons.append("unsafe_or_noncanonical_relative_path")
            identity = (logical_root, relative_text)
            if identity in manifest_seen:
                reasons.append("duplicate_manifest_identity")
            manifest_seen.add(identity)
            root = ATTEMPT02_LOGICAL_ROOTS.get(logical_root)
            if root is None:
                reasons.append("unknown_logical_root")
            size_text = str(row.get("size_bytes", ""))
            try:
                expected_size = int(size_text)
                if expected_size < 0 or size_text != str(expected_size):
                    raise ValueError("noncanonical size")
            except Exception:
                expected_size = -1
                reasons.append("invalid_size_bytes")
            expected_sha256 = row.get("sha256")
            if not is_upper_sha256_text(expected_sha256):
                reasons.append("invalid_sha256")
            if root is not None and relative_safe:
                candidate = root.joinpath(*pure_relative.parts)
                try:
                    candidate.resolve(strict=False).relative_to(root.resolve())
                except Exception:
                    reasons.append("candidate_escaped_logical_root")
                if not candidate.is_file():
                    reasons.append("missing_file")
                elif expected_size >= 0 and is_upper_sha256_text(expected_sha256):
                    if candidate.stat().st_size != expected_size:
                        reasons.append("size_mismatch")
                    if sha256_file(candidate) != expected_sha256:
                        reasons.append("sha256_mismatch")
                    archive_relative = (
                        candidate.resolve().relative_to(ATTEMPT02_ROOT.resolve()).as_posix()
                    )
                    manifest_expected_files.add(archive_relative)
                    root_stats[logical_root]["file_count"] += 1
                    root_stats[logical_root]["total_size_bytes"] += expected_size
            if reasons:
                manifest_row_errors.append(
                    {
                        "index": index,
                        "logical_root": logical_root,
                        "relative_path": relative_text,
                        "reasons": reasons,
                    }
                )
        manifest_total_size = sum(
            int(row["size_bytes"])
            for row in manifest_rows
            if str(row.get("size_bytes", "")).isdigit()
        )
        audit["artifact_manifest"] = {
            "fieldnames": manifest_fields,
            "row_count": len(manifest_rows),
            "total_size_bytes": manifest_total_size,
            "root_stats": root_stats,
            "row_errors": manifest_row_errors,
        }
        record(
            "artifact_manifest_schema_340_unique_rows",
            manifest_fields == expected_manifest_fields
            and len(manifest_rows) == 340
            and len(manifest_seen) == 340
            and not manifest_row_errors,
        )
        record(
            "artifact_manifest_files_hashes_root_totals_exact",
            len(manifest_expected_files) == 340
            and manifest_total_size == 14_017_492
            and root_stats == ATTEMPT02_ROOT_COUNTS
            and not manifest_row_errors,
        )

        tool_manifest_path = ATTEMPT02_ROOT / "tool_snapshot_manifest.csv"
        with tool_manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            tool_reader = csv.DictReader(stream)
            tool_fields = list(tool_reader.fieldnames or [])
            tool_rows = list(tool_reader)
        expected_tool_fields = ["name", "relative_path", "size_bytes", "sha256"]
        tool_row_errors: list[dict[str, Any]] = []
        expected_tool_files: set[str] = set()
        for index, name in enumerate(INSTRUMENT_ORDER):
            if index >= len(tool_rows):
                tool_row_errors.append(
                    {"index": index + 1, "name": name, "reason": "row_missing"}
                )
                continue
            row = tool_rows[index]
            candidate = ATTEMPT02_ROOT / "tools_snapshot" / name
            try:
                size_value = int(str(row.get("size_bytes", "")))
                size_canonical = str(size_value) == str(row.get("size_bytes", ""))
            except Exception:
                size_value = -1
                size_canonical = False
            relative_path = f"tools_snapshot/{name}"
            row_pass = bool(
                row.get("name") == name
                and row.get("relative_path") == relative_path
                and row.get("sha256") == ATTEMPT02_TOOL_SHA256[name]
                and size_canonical
                and size_value >= 0
                and candidate.is_file()
                and candidate.stat().st_size == size_value
                and sha256_file(candidate) == ATTEMPT02_TOOL_SHA256[name]
            )
            if not row_pass:
                tool_row_errors.append({"index": index + 1, "name": name, "row": row})
            expected_tool_files.add(relative_path)
        audit["tool_snapshot"] = {
            "fieldnames": tool_fields,
            "row_count": len(tool_rows),
            "row_errors": tool_row_errors,
        }
        record(
            "tool_manifest_five_snapshots_exact",
            tool_fields == expected_tool_fields
            and len(tool_rows) == 5
            and not tool_row_errors,
        )

        summary = load_json(ATTEMPT02_ROOT / "attempt_summary.json")
        empty_hash = hashlib.sha256(b"").hexdigest().upper()

        def archived_process_record_pass(value: Any) -> bool:
            return bool(
                isinstance(value, dict)
                and value.get("returncode") == 0
                and value.get("stderr_size_bytes") == 0
                and value.get("stderr_sha256") == empty_hash
                and value.get("target_processes") == []
                and isinstance(value.get("stdout_size_bytes"), int)
                and value.get("stdout_size_bytes") > 0
                and is_upper_sha256_text(value.get("stdout_sha256"))
            )

        source_by_logical = {
            "tmp_step3_runs": TMP_ROOT,
            "outputs_step3_stage": STAGE_ROOT,
            "outputs_step3_runs": RUN_ROOT,
            "logs_step3_runs": LOG_ROOT,
            "outputs_step3_orchestration": ORCHESTRATION_ROOT,
            "outputs_step3_validation": VALIDATION_ROOT,
        }
        expected_moved_roots = [
            {
                "logical_root": logical,
                "source_before_archive": str(source_by_logical[logical]),
                "destination": str(ATTEMPT02_LOGICAL_ROOTS[logical]),
            }
            for logical in ATTEMPT02_LOGICAL_ROOTS
        ]
        expected_route7_contract = {
            "source": "Copy_2_of_energy_zonghe3.mlx C004",
            "source_sha256": SOURCES["Copy_2_of_energy_zonghe3.mlx"],
            "retained_one_based": [1, 2],
            "energy_sum_orig": "sum(E_total(d))",
            "energy_sum_guyan": "sum(E_total_guyan)",
            "energy_sum_cb": "sum(E_total_cb(d2))",
            "guyan_denominator": "energy_sum_guyan",
            "cb_denominator": "energy_sum_guyan",
            "paper_formula_correct": False,
            "coordinate_order_correct": False,
        }
        created_at_valid = False
        try:
            created_at_valid = datetime.fromisoformat(
                str(summary.get("created_at"))
            ).tzinfo is not None
        except Exception:
            created_at_valid = False
        summary_semantics_pass = bool(
            summary.get("schema_version") == "BOARD21_STEP3_ATTEMPT_ARCHIVE_V2"
            and summary.get("archive_status")
            == "VALIDATOR_CONTRACT_FAILURE_ATTEMPT_PRESERVED"
            and summary.get("attempt_id")
            == "step3_attempt02_20260826_validator_sum_scope_contract_failure"
            and summary.get("physical_archive_directory") == "a02"
            and created_at_valid
            and summary.get("artifact_file_count") == 340
            and summary.get("artifact_total_size_bytes") == 14_017_492
            and summary.get("tool_snapshot_count") == 5
            and summary.get("attempt_file_manifest") == "attempt_file_manifest.csv"
            and summary.get("tool_snapshot_manifest") == "tool_snapshot_manifest.csv"
            and summary.get("root_counts") == ATTEMPT02_ROOT_COUNTS
            and summary.get("tool_snapshot_sha256") == ATTEMPT02_TOOL_SHA256
            and summary.get("pinned_file_sha256") == ATTEMPT02_PINNED_FILE_SHA256
            and summary.get("correct_route7_author_contract")
            == expected_route7_contract
            and summary.get("moved_roots") == expected_moved_roots
            and summary.get("internal_absolute_paths_are_historical") is True
            and summary.get("standard_step3_roots_absent_after_archive") is True
            and archived_process_record_pass(summary.get("process_before_archive"))
            and archived_process_record_pass(summary.get("process_after_archive"))
        )
        record("summary_identity_counts_and_process_boundaries_exact", summary_semantics_pass)

        pinned_actual = {
            relative: sha256_file(ATTEMPT02_ROOT / PurePosixPath(relative))
            if (ATTEMPT02_ROOT / PurePosixPath(relative)).is_file()
            else "MISSING"
            for relative in ATTEMPT02_PINNED_FILE_SHA256
        }
        audit["pinned_file_sha256_expected"] = ATTEMPT02_PINNED_FILE_SHA256
        audit["pinned_file_sha256_actual"] = pinned_actual

        expected_archive_files = (
            set(ATTEMPT02_METADATA_SHA256)
            | manifest_expected_files
            | expected_tool_files
        )
        final_lengths = {
            relative: len(str(ATTEMPT02_ROOT / PurePosixPath(relative)))
            for relative in expected_archive_files
        }
        building_root = ATTEMPT02_ROOT.parent / ".b02"
        building_lengths = {
            relative: len(str(building_root / PurePosixPath(relative)))
            for relative in expected_archive_files
        }
        final_maximum = max(final_lengths.values())
        building_maximum = max(building_lengths.values())
        final_maximum_paths = {
            str(ATTEMPT02_ROOT / PurePosixPath(relative))
            for relative, length in final_lengths.items()
            if length == final_maximum
        }
        building_maximum_paths = {
            str(building_root / PurePosixPath(relative))
            for relative, length in building_lengths.items()
            if length == building_maximum
        }
        path_budget = summary.get("path_budget")
        final_budget = path_budget.get("final") if isinstance(path_budget, dict) else {}
        building_budget = (
            path_budget.get("building") if isinstance(path_budget, dict) else {}
        )
        synthetic_241 = ATTEMPT02_ROOT / (
            "x" * (241 - len(str(ATTEMPT02_ROOT)) - 1)
        )
        path_budget_pass = bool(
            len(expected_archive_files) == 348
            and final_maximum == 238
            and building_maximum == 239
            and max((len(str(ATTEMPT02_ROOT / PurePosixPath(path))) for path in tree["files"]), default=0)
            <= 240
            and max((len(str(ATTEMPT02_ROOT / PurePosixPath(path))) for path in tree["directories"]), default=0)
            <= 240
            and len(str(synthetic_241)) == 241
            and len(str(synthetic_241)) > 240
            and isinstance(final_budget, dict)
            and final_budget.get("label") == "final archive"
            and final_budget.get("limit") == 240
            and final_budget.get("projected_path_count") == 348
            and final_budget.get("maximum_length") == final_maximum
            and final_budget.get("maximum_path") in final_maximum_paths
            and final_budget.get("over_limit_count") == 0
            and isinstance(building_budget, dict)
            and building_budget.get("label") == "building archive"
            and building_budget.get("limit") == 240
            and building_budget.get("projected_path_count") == 348
            and building_budget.get("maximum_length") == building_maximum
            and building_budget.get("maximum_path") in building_maximum_paths
            and building_budget.get("over_limit_count") == 0
        )
        audit["path_budget_recomputed"] = {
            "projected_file_count": len(expected_archive_files),
            "final_maximum_length": final_maximum,
            "building_maximum_length": building_maximum,
            "synthetic_negative_length": len(str(synthetic_241)),
        }
        record("path_budget_recomputed", path_budget_pass)

        orchestration_path = (
            ATTEMPT02_LOGICAL_ROOTS["outputs_step3_orchestration"]
            / "run_all_summary.json"
        )
        orchestration = load_json(orchestration_path)
        route_process_records = normalize_struct_list(
            orchestration.get("route_process_records"),
            "attempt02.route_process_records",
        )
        process_query_records = normalize_struct_list(
            orchestration.get("process_query_records"),
            "attempt02.process_query_records",
        )
        subprocess_records = normalize_struct_list(
            orchestration.get("subprocess_records"),
            "attempt02.subprocess_records",
        )
        tokens = [str(item.get("execution_token", "")) for item in route_process_records]
        route_records_pass = bool(
            len(route_process_records) == 14
            and len(set(tokens)) == 14
            and all(re.fullmatch(r"[0-9A-F]{64}", token) for token in tokens)
            and all(
                item.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED"
                and item.get("executor_returncode") == 0
                and item.get("matlab_returncode") == 0
                and item.get("evidence_capture_ok") is True
                and item.get("execution_identity_contract_pass") is True
                and item.get("execution_token_match") is True
                and item.get("execution_token_sha256")
                == sha256_ascii_text(str(item.get("execution_token")))
                and item.get("instrument_seal_match") is True
                and item.get("instrument_sha256_before") == ATTEMPT02_TOOL_SHA256
                and item.get("instrument_sha256_after") == ATTEMPT02_TOOL_SHA256
                and item.get("target_processes_before") == []
                and item.get("target_processes_after") == []
                for item in route_process_records
            )
        )
        process_records_pass = bool(
            len(process_query_records) == 30
            and all(
                item.get("ok") is True
                and item.get("capture_match") is True
                and item.get("processes") == []
                and item.get("filtered_process_count") == 0
                and item.get("returncode") == 0
                and item.get("timed_out") is False
                for item in process_query_records
            )
        )
        subprocess_pass = bool(
            len(subprocess_records) == 16
            and all(
                item.get("returncode") == 0
                and item.get("timed_out") is False
                and item.get("timeout_error") == ""
                for item in subprocess_records
            )
        )
        orchestration_pass = bool(
            pinned_actual[
                "outputs/step3_orchestration/run_all_summary.json"
            ]
            == ATTEMPT02_PINNED_FILE_SHA256[
                "outputs/step3_orchestration/run_all_summary.json"
            ]
            and orchestration.get("schema_version")
            == "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V3"
            and orchestration.get("status") == "PASS"
            and orchestration.get("expected_run_count") == 14
            and orchestration.get("executed_run_count") == 14
            and orchestration.get("author_execution_success_count") == 14
            and orchestration.get("author_execution_failure_count") == 0
            and orchestration.get("author_execution_count_contract_pass") is True
            and orchestration.get("infrastructure_failure") is False
            and orchestration.get("unstarted_runs") == []
            and orchestration.get("route_contract_pass") is True
            and orchestration.get("execution_identity_contract_pass") is True
            and orchestration.get("subprocess_contract_pass") is True
            and orchestration.get("process_query_contract_pass") is True
            and orchestration.get("unique_execution_token_count") == 14
            and orchestration.get("sealed_instrument_sha256") == ATTEMPT02_TOOL_SHA256
            and orchestration.get("final_target_process_count") == 0
            and orchestration.get("final_target_processes") == []
            and orchestration.get("terminal_error") == {}
            and route_records_pass
            and process_records_pass
            and subprocess_pass
        )
        record("archived_orchestration_v3_14_success_exact", orchestration_pass)

        validation_root = ATTEMPT02_LOGICAL_ROOTS["outputs_step3_validation"]
        validation_summary = load_json(validation_root / "validation_summary.json")
        with (validation_root / "checks.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            checks_reader = csv.DictReader(stream)
            archived_check_fields = list(checks_reader.fieldnames or [])
            archived_check_rows = list(checks_reader)
        with (validation_root / "route_results.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            route_reader = csv.DictReader(stream)
            archived_route_fields = list(route_reader.fieldnames or [])
            archived_route_rows = list(route_reader)
        with (validation_root / "repeat_comparison.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            repeat_reader = csv.DictReader(stream)
            archived_repeat_fields = list(repeat_reader.fieldnames or [])
            archived_repeat_rows = list(repeat_reader)
        archived_failed_rows = [
            row for row in archived_check_rows if row.get("status") == "FAIL"
        ]
        archived_failed_ids = {str(row.get("check_id")) for row in archived_failed_rows}
        archived_check_ids = [str(row.get("check_id")) for row in archived_check_rows]
        validation_pass = bool(
            all(
                pinned_actual[relative] == expected
                for relative, expected in ATTEMPT02_PINNED_FILE_SHA256.items()
                if relative.startswith("outputs/step3_validation/")
            )
            and validation_summary.get("schema_version")
            == "BOARD21_STEP3_INDEPENDENT_VALIDATION_V2"
            and validation_summary.get("status") == "FAIL"
            and validation_summary.get("check_count") == 251
            and validation_summary.get("passed_count") == 247
            and validation_summary.get("failed_count") == 4
            and set(validation_summary.get("failed_check_ids", []))
            == ATTEMPT02_FAILED_CHECK_IDS
            and validation_summary.get("check_ids_unique") is True
            and validation_summary.get("successful_route_count") == 7
            and validation_summary.get("failed_route_count") == 0
            and validation_summary.get("repeat_pass_route_count") == 6
            and validation_summary.get("artifact_seal_pass_run_count") == 14
            and validation_summary.get("hdf5_readable_pass_run_count") == 14
            and validation_summary.get("inventory_workspace_crosscheck_pass_run_count")
            == 14
            and archived_check_fields
            == ["check_id", "category", "status", "expected", "actual", "evidence"]
            and len(archived_check_rows) == 251
            and len(set(archived_check_ids)) == 251
            and archived_failed_ids == ATTEMPT02_FAILED_CHECK_IDS
            and all(
                row.get("status") in {"PASS", "FAIL"}
                and (
                    row.get("status") == "FAIL"
                    if row.get("check_id") in ATTEMPT02_FAILED_CHECK_IDS
                    else row.get("status") == "PASS"
                )
                for row in archived_check_rows
            )
            and len(archived_route_rows) == 7
            and len(archived_repeat_rows) == 7
        )
        audit["archived_validation"] = {
            "check_fields": archived_check_fields,
            "route_fields": archived_route_fields,
            "repeat_fields": archived_repeat_fields,
            "check_count": len(archived_check_rows),
            "failed_check_ids": sorted(archived_failed_ids),
        }
        record("archived_validation_exact_four_failures", validation_pass)

        check_by_id = {
            str(row.get("check_id")): row for row in archived_check_rows
        }
        expected_route7_sums = {
            "energy_sum_orig": 22403.23860163083,
            "energy_sum_guyan": 36887.32701500341,
            "energy_sum_cb": 29856.69162409193,
        }
        expected_route7_totals = {
            "total_increase_guyan": 39.26575760689132,
            "total_increase_cb": 20.20599925668106,
        }
        formula_cascade_pass = True
        formula_cascade_details: dict[str, Any] = {}
        for check_id in ("S3-SCIENTIFIC-FORMULA-13", "S3-SCIENTIFIC-FORMULA-14"):
            row = check_by_id.get(check_id, {})
            try:
                actual = json.loads(str(row.get("actual", "")))
            except Exception:
                actual = {}
            formula_cascade_details[check_id] = actual
            stored_sums = actual.get("stored_sums") if isinstance(actual, dict) else {}
            stored_totals = actual.get("totals") if isinstance(actual, dict) else {}
            formula_cascade_pass &= bool(
                row.get("status") == "FAIL"
                and isinstance(actual, dict)
                and actual.get("formula_match") is False
                and actual.get("status_match") is True
                and actual.get("scientific_cross_pass") is True
                and actual.get("artifact_audit_pass") is True
                and actual.get("hdf5_audit_pass") is True
                and actual.get("inventory_pass") is True
                and actual.get("formula_exception") == ""
                and all(
                    strict_abs_rel_comparison(stored_sums.get(name), expected)["pass"]
                    for name, expected in expected_route7_sums.items()
                )
                and all(
                    strict_abs_rel_comparison(stored_totals.get(name), expected)["pass"]
                    for name, expected in expected_route7_totals.items()
                )
            )
        repeat_check = check_by_id.get("S3-REPEAT-07", {})
        all_routes_check = check_by_id.get("S3-ALL-ROUTES-REPEAT", {})
        try:
            repeat_actual = json.loads(str(repeat_check.get("actual", "")))
        except Exception:
            repeat_actual = {}
        route7_result = next(
            (
                row
                for row in archived_route_rows
                if row.get("route_id")
                == ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]
            ),
            {},
        )
        route7_repeat = next(
            (
                row
                for row in archived_repeat_rows
                if row.get("route_id")
                == ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]
            ),
            {},
        )
        cascade_pass = bool(
            formula_cascade_pass
            and repeat_check.get("status") == "FAIL"
            and isinstance(repeat_actual, dict)
            and repeat_actual.get("outcome") == "SUCCESS"
            and repeat_actual.get("max_abs") == 0.0
            and repeat_actual.get("max_rel") == 0.0
            and isinstance(repeat_actual.get("details"), dict)
            and repeat_actual["details"].get("both_science_valid") is False
            and all_routes_check.get("status") == "FAIL"
            and all_routes_check.get("expected") == "7"
            and all_routes_check.get("actual") == "6"
            and route7_result.get("execution_outcome") == "SUCCESS"
            and route7_result.get("repeat_status") == "FAIL"
            and float(route7_result.get("max_abs_difference", "nan")) == 0.0
            and float(route7_result.get("max_relative_difference", "nan")) == 0.0
            and strict_abs_rel_comparison(
                route7_result.get("rep01_guyan_percent"),
                expected_route7_totals["total_increase_guyan"],
            )["pass"]
            and strict_abs_rel_comparison(
                route7_result.get("rep01_cb_percent"),
                expected_route7_totals["total_increase_cb"],
            )["pass"]
            and route7_repeat.get("outcome") == "SUCCESS"
            and route7_repeat.get("repeat_pass") == "False"
            and float(route7_repeat.get("max_abs_difference", "nan")) == 0.0
            and float(route7_repeat.get("max_relative_difference", "nan")) == 0.0
            and summary.get("correct_route7_author_contract")
            == expected_route7_contract
        )
        audit["route7_failure_cascade"] = {
            "formula_checks": formula_cascade_details,
            "repeat_check": repeat_actual,
            "route_result": route7_result,
            "repeat_row": route7_repeat,
        }
        record("route7_failure_cascade_exact", cascade_pass)

        route7_science_paths = {
            replicate: (
                ATTEMPT02_LOGICAL_ROOTS["outputs_step3_runs"]
                / ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]
                / replicate
                / "scientific"
                / "historical_energy_outputs.mat"
            )
            for replicate in REPLICATES
        }
        route7_variable_names = (
            "E_total",
            "E_total_guyan",
            "E_total_cb",
            "energy_sum_orig",
            "energy_sum_guyan",
            "energy_sum_cb",
            "total_increase_guyan",
            "total_increase_cb",
        )
        route7_records = {
            replicate: {
                name: finite_numeric_record(path, name)
                for name in route7_variable_names
            }
            for replicate, path in route7_science_paths.items()
        }
        repeat_exact = all(
            np.array_equal(
                np.asarray(route7_records["rep01"][name]["value"]),
                np.asarray(route7_records["rep02"][name]["value"]),
                equal_nan=False,
            )
            for name in route7_variable_names
        )
        maximum_absolute = 0.0
        maximum_relative = 0.0
        for name in route7_variable_names:
            first = np.asarray(route7_records["rep01"][name]["value"], dtype=float)
            second = np.asarray(route7_records["rep02"][name]["value"], dtype=float)
            absolute = np.abs(first - second)
            denominator_array = np.maximum(
                np.maximum(np.abs(first), np.abs(second)), np.finfo(float).tiny
            )
            maximum_absolute = max(maximum_absolute, float(np.max(absolute)))
            maximum_relative = max(
                maximum_relative, float(np.max(absolute / denominator_array))
            )
        recomputed_by_replicate: dict[str, Any] = {}
        route7_formula_pass = repeat_exact
        for replicate, records in route7_records.items():
            original = np.asarray(records["E_total"]["value"], dtype=float).reshape(-1)
            guyan = np.asarray(records["E_total_guyan"]["value"], dtype=float).reshape(-1)
            cb = np.asarray(records["E_total_cb"]["value"], dtype=float).reshape(-1)
            retained = np.asarray([0, 1], dtype=int)
            recomputed_sums = {
                "energy_sum_orig": float(np.sum(original[retained])),
                "energy_sum_guyan": float(np.sum(guyan)),
                "energy_sum_cb": float(np.sum(cb[retained])),
            }
            denominator_value = recomputed_sums["energy_sum_guyan"]
            recomputed_totals = {
                "total_increase_guyan": (
                    recomputed_sums["energy_sum_guyan"]
                    - recomputed_sums["energy_sum_orig"]
                )
                / denominator_value
                * 100.0,
                "total_increase_cb": (
                    recomputed_sums["energy_sum_cb"]
                    - recomputed_sums["energy_sum_orig"]
                )
                / denominator_value
                * 100.0,
            }
            stored_sums = {
                name: scalar_from_record(records[name], name)
                for name in expected_route7_sums
            }
            stored_totals = {
                name: scalar_from_record(records[name], name)
                for name in expected_route7_totals
            }
            comparisons = {
                name: strict_abs_rel_comparison(stored_sums[name], value)
                for name, value in recomputed_sums.items()
            }
            comparisons.update(
                {
                    name: strict_abs_rel_comparison(stored_totals[name], value)
                    for name, value in recomputed_totals.items()
                }
            )
            route7_formula_pass &= bool(
                original.size == 9
                and guyan.size == 2
                and cb.size == 5
                and denominator_value != 0.0
                and all(item["pass"] for item in comparisons.values())
                and all(
                    strict_abs_rel_comparison(recomputed_sums[name], expected)["pass"]
                    for name, expected in expected_route7_sums.items()
                )
                and all(
                    strict_abs_rel_comparison(recomputed_totals[name], expected)["pass"]
                    for name, expected in expected_route7_totals.items()
                )
            )
            recomputed_by_replicate[replicate] = {
                "sums": recomputed_sums,
                "totals": recomputed_totals,
                "comparisons": comparisons,
            }
        semantic_diagnosis = summary.get("semantic_diagnosis")
        route7_summary_values = (
            semantic_diagnosis.get("route7_author_values")
            if isinstance(semantic_diagnosis, dict)
            else {}
        )
        route7_formula_pass &= bool(
            maximum_absolute == 0.0
            and maximum_relative == 0.0
            and isinstance(semantic_diagnosis, dict)
            and semantic_diagnosis.get("route7_repeat_max_abs") == 0.0
            and semantic_diagnosis.get("route7_repeat_max_rel") == 0.0
            and all(
                strict_abs_rel_comparison(route7_summary_values.get(name), expected)[
                    "pass"
                ]
                for name, expected in {
                    "energy_sum_orig_selected": expected_route7_sums[
                        "energy_sum_orig"
                    ],
                    "energy_sum_guyan": expected_route7_sums["energy_sum_guyan"],
                    "energy_sum_cb_selected": expected_route7_sums["energy_sum_cb"],
                    "total_increase_guyan": expected_route7_totals[
                        "total_increase_guyan"
                    ],
                    "total_increase_cb": expected_route7_totals["total_increase_cb"],
                }.items()
            )
        )
        audit["route7_mat_recomputation"] = {
            "repeat_exact": repeat_exact,
            "maximum_absolute": maximum_absolute,
            "maximum_relative": maximum_relative,
            "replicates": recomputed_by_replicate,
        }
        record("route7_mat_exact_repeat_and_formula_recomputed", route7_formula_pass)

        actual_archive_files = set(tree["files"])
        expected_directories: set[str] = set()
        for relative in expected_archive_files:
            parent = PurePosixPath(relative).parent
            while parent != PurePosixPath("."):
                expected_directories.add(parent.as_posix())
                parent = parent.parent
        actual_archive_bytes = sum(
            (ATTEMPT02_ROOT / PurePosixPath(relative)).stat().st_size
            for relative in actual_archive_files
        )
        archive_missing = sorted(expected_archive_files - actual_archive_files)
        archive_unexpected = sorted(actual_archive_files - expected_archive_files)
        directory_missing = sorted(expected_directories - tree["directories"])
        directory_unexpected = sorted(tree["directories"] - expected_directories)
        audit["archive_closure"] = {
            "expected_file_count": len(expected_archive_files),
            "actual_file_count": len(actual_archive_files),
            "actual_total_size_bytes": actual_archive_bytes,
            "expected_directory_count": len(expected_directories),
            "actual_directory_count": len(tree["directories"]),
            "missing_files": archive_missing,
            "unexpected_files": archive_unexpected,
            "missing_directories": directory_missing,
            "unexpected_directories": directory_unexpected,
            "links_or_junctions": tree["links_or_junctions"],
            "special_nodes": tree["special_nodes"],
        }
        record(
            "entire_archive_file_and_directory_set_closed",
            actual_archive_files == expected_archive_files
            and tree["directories"] == expected_directories
            and len(actual_archive_files) == 348
            and actual_archive_bytes == 14_440_421
            and len(tree["directories"]) == 132
            and not tree["links_or_junctions"]
            and not tree["special_nodes"],
        )
    except Exception as error:
        audit["errors"].append(f"{type(error).__name__}: {error}")
        audit["traceback"] = traceback.format_exc()

    audit_pass = bool(checks and all(checks.values()) and not audit["errors"])
    audit["pass"] = audit_pass
    audit["status"] = "PASS" if audit_pass else "FAIL"
    audit["check_count"] = len(checks)
    audit["failed_checks"] = sorted(
        name for name, passed in checks.items() if not passed
    )
    return audit


def publication_and_process_snapshot() -> dict[str, Any]:
    formal_present: list[str] = []
    failure_present: list[str] = []
    board22: list[str] = []
    publication_error = ""
    try:
        formal_present = [
            str(PROJECT_ROOT / "test" / name)
            for name in FORMAL_OBJECT_NAMES
            if (PROJECT_ROOT / "test" / name).exists()
        ]
        failure_present = [
            str(PROJECT_ROOT / "test" / "00_失败尝试与候选路线" / name)
            for name in FORMAL_OBJECT_NAMES
            if (PROJECT_ROOT / "test" / "00_失败尝试与候选路线" / name).exists()
        ]
        board22 = [
            str(path)
            for path in (PROJECT_ROOT / "test").rglob("*")
            if path.name.startswith("板块22")
        ]
    except Exception as error:
        publication_error = f"{type(error).__name__}: {error}"
    residual: list[dict[str, Any]] = []
    process_error = ""
    try:
        residual = target_processes()
    except Exception as error:
        process_error = f"{type(error).__name__}: {error}"
    return {
        "formal_present": formal_present,
        "failure_present": failure_present,
        "board22_present": board22,
        "publication_query_error": publication_error,
        "residual_processes": residual,
        "process_query_error": process_error,
    }


def validate() -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    preflight_summary = preflight(require_validation_absent=False)
    all_manifest_rows, freeze_summary = verify_input_freeze()
    manifest_rows = author_manifest_by_name(all_manifest_rows)
    checks: list[dict[str, Any]] = []
    route_results: list[dict[str, Any]] = []
    repeat_rows: list[dict[str, Any]] = []
    per_route_runs: dict[str, dict[str, dict[str, Any]]] = {}
    route_map = {route["route_id"]: route for route in ROUTES}
    sealed_tools = {
        name: sha256_file(SCRIPT.parent / name) for name in INSTRUMENT_ORDER
    }
    attempt01_archive_audit = audit_attempt01_archive()
    attempt02_archive_audit = audit_attempt02_archive()
    route7_formula_source_contract = evaluate_route7_formula_source_contract(
        route_map[ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]]
    )
    mutated_route7 = dict(route_map[ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]])
    mutated_route7["sum_scope"] = "all_vectors"
    route7_formula_mutation = evaluate_route7_formula_source_contract(mutated_route7)
    route7_formula_mutation_rejected = bool(
        route7_formula_source_contract.get("pass") is True
        and route7_formula_mutation.get("pass") is False
        and route7_formula_mutation.get("failed_fields") == ["route.sum_scope"]
    )

    add_check(checks, "S3-ROUTE-COUNT", "contract", len(ROUTES) == 7, 7, len(ROUTES), SCRIPT)
    add_check(checks, "S3-UNIQUE-SOURCE-COUNT", "contract", len(SOURCES) == 12, 12, len(SOURCES), AUTHOR_ROOT)
    add_check(
        checks,
        "S3-FORMULA-SOURCE-CONTRACT-07",
        "protected_formula_source",
        route7_formula_source_contract.get("pass") is True,
        {
            "schema_version": "BOARD21_STEP3_ROUTE7_FORMULA_SOURCE_CONTRACT_V1",
            "status": "PASS",
            "failed_fields": [],
        },
        route7_formula_source_contract,
        ROUTE7_FORMULA_RECORD,
    )
    add_check(
        checks,
        "S3-FORMULA-SOURCE-MUTATION-07",
        "negative_mutation",
        route7_formula_mutation_rejected,
        {
            "positive_pass": True,
            "mutant_pass": False,
            "mutant_failed_fields": ["route.sum_scope"],
        },
        {
            "positive_pass": route7_formula_source_contract.get("pass"),
            "mutant_pass": route7_formula_mutation.get("pass"),
            "mutant_failed_fields": route7_formula_mutation.get("failed_fields"),
        },
        SCRIPT,
    )
    add_check(
        checks,
        "S3-ATTEMPT01-ARCHIVE-INDEPENDENT-AUDIT",
        "archived_failure_evidence",
        attempt01_archive_audit.get("pass") is True,
        {
            "schema_version": "BOARD21_STEP3_ATTEMPT01_ARCHIVE_AUDIT_V1",
            "status": "PASS",
            "all_pinned_hashes_manifests_semantics_science_and_closure": True,
        },
        attempt01_archive_audit,
        ATTEMPT01_ROOT,
    )
    add_check(
        checks,
        "S3-ATTEMPT02-ARCHIVE-INDEPENDENT-AUDIT",
        "archived_validator_contract_failure_evidence",
        attempt02_archive_audit.get("pass") is True,
        {
            "schema_version": "BOARD21_STEP3_ATTEMPT02_ARCHIVE_AUDIT_V1",
            "status": "PASS",
            "check_count": 12,
            "failed_checks": [],
            "archive_file_count": 348,
        },
        {
            "schema_version": attempt02_archive_audit.get("schema_version"),
            "status": attempt02_archive_audit.get("status"),
            "check_count": attempt02_archive_audit.get("check_count"),
            "failed_checks": attempt02_archive_audit.get("failed_checks"),
            "archive_file_count": attempt02_archive_audit.get(
                "archive_closure", {}
            ).get("actual_file_count"),
            "errors": attempt02_archive_audit.get("errors"),
        },
        ATTEMPT02_ROOT,
    )
    add_check(
        checks,
        "S3-INPUT-FREEZE-SEALS",
        "protected_input",
        sha256_file(INPUT_MANIFEST) == INPUT_MANIFEST_SHA256
        and sha256_file(INPUT_FREEZE_SUMMARY) == INPUT_FREEZE_SUMMARY_SHA256,
        {
            "input_manifest_sha256": INPUT_MANIFEST_SHA256,
            "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        },
        {
            "input_manifest_sha256": sha256_file(INPUT_MANIFEST),
            "input_freeze_summary_sha256": sha256_file(INPUT_FREEZE_SUMMARY),
        },
        INPUT_MANIFEST,
    )
    add_check(
        checks,
        "S3-INPUT-FREEZE-53-ROW-IDENTITY",
        "protected_input",
        len(all_manifest_rows) == 53
        and freeze_summary.get("category_counts") == EXPECTED_INPUT_CATEGORY_COUNTS,
        {"row_count": 53, "category_counts": EXPECTED_INPUT_CATEGORY_COUNTS},
        {"row_count": len(all_manifest_rows), "summary": freeze_summary},
        INPUT_MANIFEST,
    )
    for index, (relative, expected) in enumerate(STEP2_ANCHORS.items(), start=1):
        path = BOARD_ROOT / relative
        actual = sha256_file(path) if path.is_file() else "MISSING"
        add_check(checks, f"S3-STEP2-ANCHOR-{index:02d}", "protected_input", actual == expected, expected, actual, path)

    stage_summary_path = STAGE_ROOT / "stage_summary.json"
    stage_summary = load_json(stage_summary_path)
    stage_expected = {
        "schema_version": "BOARD21_STEP3_STAGE_SUMMARY_V1",
        "status": "STAGED_NOT_RUN",
        "matlab_executed": False,
        "route_count": 7,
        "replicate_count": 2,
        "run_count": 14,
        "staged_input_row_count": 28,
        "unique_source_count": 12,
        "protected_input_count": 53,
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        "instrument_sha256": sealed_tools,
        "formal_success_directory_created": False,
        "board22_started": False,
    }
    stage_pass = all(stage_summary.get(key) == value for key, value in stage_expected.items())
    add_check(checks, "S3-STAGE-SUMMARY", "staging", stage_pass, stage_expected, stage_summary, stage_summary_path)

    config_csv = STAGE_ROOT / "run_configs.csv"
    expected_config_fields = [
        "route_id", "route_label_cn", "replicate", "config_path",
        "config_sha256", "static_boundary", "execution_status",
    ]
    with config_csv.open("r", encoding="utf-8-sig", newline="") as stream:
        config_reader = csv.DictReader(stream)
        config_fields = config_reader.fieldnames
        config_rows = list(config_reader)
    actual_config_order = tuple(
        (row.get("route_id", ""), row.get("replicate", "")) for row in config_rows
    )
    config_set_pass = bool(
        config_fields == expected_config_fields
        and len(config_rows) == 14
        and actual_config_order == EXPECTED_RUN_ORDER
        and len(set(actual_config_order)) == 14
        and all(row.get("execution_status") == "STAGED_NOT_RUN" for row in config_rows)
    )
    add_check(
        checks,
        "S3-CONFIG-ORDER-AND-SCHEMA",
        "staging",
        config_set_pass,
        {"fields": expected_config_fields, "order": EXPECTED_RUN_ORDER, "execution_status": "STAGED_NOT_RUN"},
        {"fields": config_fields, "order": actual_config_order, "statuses": [row.get("execution_status") for row in config_rows]},
        config_csv,
    )
    if not config_set_pass:
        raise RuntimeError("ordered 14-run config set is not valid")

    staged_manifest_path = STAGE_ROOT / "staged_input_manifest.csv"
    expected_staged_fields = [
        "route_id", "replicate", "kind", "order", "name",
        "author_original_path", "frozen_path", "staged_path",
        "expected_sha256", "copied_sha256", "size_bytes",
    ]
    with staged_manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
        staged_reader = csv.DictReader(stream)
        staged_fields = staged_reader.fieldnames
        staged_rows = list(staged_reader)
    expected_staged_rows: list[dict[str, str]] = []
    staged_file_checks: list[dict[str, Any]] = []
    for route in ROUTES:
        for replicate in REPLICATES:
            paths = expected_run_paths(route, replicate)
            for order, kind in enumerate(("upstream", "candidate"), start=1):
                name = route[kind]
                frozen_row = manifest_rows[name]
                staged_path = paths[f"{kind}_file" if kind == "upstream" else "candidate_mlx"]
                expected_staged_rows.append(
                    {
                        "route_id": route["route_id"],
                        "replicate": replicate,
                        "kind": kind,
                        "order": str(order),
                        "name": name,
                        "author_original_path": str(Path(frozen_row["source_absolute_path"]).resolve()),
                        "frozen_path": str((AUTHOR_ROOT / name).resolve()),
                        "staged_path": str(staged_path),
                        "expected_sha256": SOURCES[name],
                        "copied_sha256": SOURCES[name],
                        "size_bytes": frozen_row["frozen_size_bytes"],
                    }
                )
                staged_file_checks.append(
                    {
                        "path": str(staged_path),
                        "exists": staged_path.is_file(),
                        "size": staged_path.stat().st_size if staged_path.is_file() else -1,
                        "sha256": sha256_file(staged_path) if staged_path.is_file() else "MISSING",
                        "expected_size": int(frozen_row["frozen_size_bytes"]),
                        "expected_sha256": SOURCES[name],
                    }
                )
    staged_exact = bool(
        staged_fields == expected_staged_fields
        and staged_rows == expected_staged_rows
        and all(
            item["exists"]
            and item["size"] == item["expected_size"]
            and item["sha256"] == item["expected_sha256"]
            for item in staged_file_checks
        )
    )
    add_check(
        checks,
        "S3-STAGED-MANIFEST-EXACT",
        "staging",
        staged_exact,
        {"fields": expected_staged_fields, "rows": expected_staged_rows, "files_match": True},
        {"fields": staged_fields, "rows": staged_rows, "file_checks": staged_file_checks},
        staged_manifest_path,
    )

    config_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    exit_by_pair: dict[tuple[str, str], dict[str, Any]] = {}
    artifact_pass_count = 0
    hdf5_pass_count = 0
    inventory_pass_count = 0
    for run_index, (row, expected_pair) in enumerate(
        zip(config_rows, EXPECTED_RUN_ORDER, strict=True), start=1
    ):
        route_id, replicate = expected_pair
        route = route_map[route_id]
        route_formula_source_contract_pass = bool(
            route_id != ROUTE7_FORMULA_SOURCE_CONTRACT["route_id"]
            or route7_formula_source_contract.get("pass") is True
        )
        paths = expected_run_paths(route, replicate)
        config_path = paths["config_json"]
        row_identity_pass = bool(
            row.get("route_id") == route_id
            and row.get("replicate") == replicate
            and row.get("route_label_cn") == route["route_label_cn"]
            and row.get("static_boundary") == route["static_boundary"]
            and row.get("execution_status") == "STAGED_NOT_RUN"
            and exact_absolute_path(row.get("config_path"), config_path)
        )
        config = load_json(config_path)
        config_hash = sha256_file(config_path)
        sidecar_hash = paths["config_hash_file"].read_text(encoding="utf-8").strip().upper()
        add_check(
            checks,
            f"S3-CONFIG-SEAL-{run_index:02d}",
            "staging",
            row_identity_pass
            and row.get("config_sha256") == config_hash
            and sidecar_hash == config_hash,
            {"pair": expected_pair, "config_path": str(config_path), "sha256": config_hash},
            {"row": row, "actual_sha256": config_hash, "sidecar_sha256": sidecar_hash},
            config_path,
        )
        expected_path_fields = expected_config_path_fields(paths)
        path_field_results = {
            field: exact_absolute_path(config.get(field), expected)
            for field, expected in expected_path_fields.items()
        }
        config_identity_pass = bool(
            config.get("schema_version") == "BOARD21_STEP3_ROUTE_CONFIG_V1"
            and config.get("route_id") == route_id
            and config.get("replicate") == replicate
            and config.get("route_label_cn") == route["route_label_cn"]
            and config.get("division_identity") == route["division_identity"]
            and config.get("parameter_family") == route["parameter_family"]
            and config.get("static_boundary") == route["static_boundary"]
            and config.get("expected_energy_lengths") == route["lengths"]
            and config.get("embedded_historical_percent") == route["history"]
            and config.get("execution_status") == "STAGED_NOT_RUN"
            and exact_absolute_path(config.get("matlab_executable"), EXPECTED_MATLAB)
            and config.get("allowed_work_files") == [route["upstream"], route["candidate"]]
            and all(path_field_results.values())
        )
        add_check(
            checks,
            f"S3-CONFIG-IDENTITY-PATHS-{run_index:02d}",
            "staging",
            config_identity_pass,
            {"route": route_id, "replicate": replicate, "execution_status": "STAGED_NOT_RUN", "all_absolute_paths_exact": True},
            {"config": config, "path_field_results": path_field_results},
            config_path,
        )

        expected_contracts: list[dict[str, Any]] = []
        for order, kind in enumerate(("upstream", "candidate"), start=1):
            name = route[kind]
            frozen_row = manifest_rows[name]
            staged_path = paths["upstream_file" if kind == "upstream" else "candidate_mlx"]
            expected_contracts.append(
                {
                    "kind": kind,
                    "order": order,
                    "name": name,
                    "author_original_path": str(Path(frozen_row["source_absolute_path"]).resolve()),
                    "frozen_path": str((AUTHOR_ROOT / name).resolve()),
                    "staged_path": str(staged_path),
                    "expected_sha256": SOURCES[name],
                    "copied_sha256": SOURCES[name],
                    "size_bytes": int(frozen_row["frozen_size_bytes"]),
                }
            )
        actual_contracts = normalize_struct_list(config.get("input_contracts"), "config.input_contracts")
        staged_projection = [
            {
                key: int(row_value[key]) if key in {"order", "size_bytes"} else row_value[key]
                for key in (
                    "kind", "order", "name", "author_original_path", "frozen_path",
                    "staged_path", "expected_sha256", "copied_sha256", "size_bytes",
                )
            }
            for row_value in staged_rows
            if row_value["route_id"] == route_id and row_value["replicate"] == replicate
        ]
        contract_files_match = all(
            Path(contract["author_original_path"]).is_file()
            and sha256_file(Path(contract["author_original_path"])) == contract["expected_sha256"]
            and Path(contract["frozen_path"]).is_file()
            and sha256_file(Path(contract["frozen_path"])) == contract["expected_sha256"]
            and Path(contract["staged_path"]).is_file()
            and sha256_file(Path(contract["staged_path"])) == contract["expected_sha256"]
            for contract in expected_contracts
        )
        contracts_pass = actual_contracts == expected_contracts == staged_projection and contract_files_match
        add_check(
            checks,
            f"S3-CONFIG-INPUT-CONTRACTS-{run_index:02d}",
            "input_hash",
            contracts_pass,
            expected_contracts,
            {"config": actual_contracts, "staged_manifest": staged_projection, "all_three_layers_match": contract_files_match},
            config_path,
        )

        expected_instrument_contracts = [
            {"name": name, "path": str((SCRIPT.parent / name).resolve()), "expected_sha256": sealed_tools[name]}
            for name in INSTRUMENT_ORDER
        ]
        actual_instrument_contracts = normalize_struct_list(
            config.get("instrument_contracts"), "config.instrument_contracts"
        )
        instrument_pass = bool(
            config.get("instrument_sha256") == sealed_tools
            and actual_instrument_contracts == expected_instrument_contracts
        )
        add_check(
            checks,
            f"S3-CONFIG-INSTRUMENT-SEAL-{run_index:02d}",
            "instrumentation",
            instrument_pass,
            {"hashes": sealed_tools, "contracts": expected_instrument_contracts},
            {"hashes": config.get("instrument_sha256"), "contracts": actual_instrument_contracts},
            config_path,
        )
        config_by_pair[expected_pair] = {"row": row, "config": config, "paths": paths, "hash": config_hash}

        status = load_json(paths["run_status_json"])
        exit_record = load_json(paths["process_exit_json"])
        exit_by_pair[expected_pair] = exit_record
        success = status.get("execution_status") == "EXECUTION_SUCCESS"
        author_failure = status.get("execution_status") == "EXECUTION_FAIL"
        scientific_name_error = ""
        try:
            status_scientific_names = normalize_string_list(
                status.get("available_scientific_variables"),
                "status.available_scientific_variables",
            )
        except Exception as error:
            status_scientific_names = []
            scientific_name_error = f"{type(error).__name__}: {error}"
        expected_status_config_contract = {
            "hash_file": str(paths["config_hash_file"]),
            "expected_sha256": config_hash,
            "actual_sha256": config_hash,
            "match": True,
        }
        status_environment = status.get("environment")
        status_execution_token = (
            status_environment.get("execution_token")
            if isinstance(status_environment, dict)
            else None
        )
        exit_execution_token = exit_record.get("execution_token")
        execution_token_format_pass = bool(
            is_upper_sha256_text(status_execution_token)
            and is_upper_sha256_text(exit_execution_token)
        )
        recomputed_execution_token_sha256 = (
            sha256_ascii_text(exit_execution_token)
            if isinstance(exit_execution_token, str)
            and execution_token_format_pass
            else ""
        )
        execution_identity_pass = bool(
            status.get("schema_version") == "BOARD21_STEP3_ROUTE_STATUS_V2"
            and exit_record.get("schema_version")
            == "BOARD21_STEP3_PROCESS_EXIT_V2"
            and execution_token_format_pass
            and "pid" not in exit_record
            and status_execution_token == exit_execution_token
            and exit_record.get("execution_token_sha256")
            == recomputed_execution_token_sha256
            and exit_record.get("execution_token_match") is True
            and is_strict_positive_int(exit_record.get("launcher_pid"))
            and is_strict_positive_int(exit_record.get("matlab_pid"))
            and isinstance(status_environment, dict)
            and status_environment.get("pid") == exit_record.get("matlab_pid")
        )
        status_terminal_pass = bool(
            status.get("schema_version") == "BOARD21_STEP3_ROUTE_STATUS_V2"
            and status.get("route_id") == route_id
            and status.get("replicate") == replicate
            and status.get("route_label_cn") == route["route_label_cn"]
            and status.get("division_identity") == route["division_identity"]
            and status.get("parameter_family") == route["parameter_family"]
            and status.get("static_boundary") == route["static_boundary"]
            and exact_absolute_path(status.get("config_path"), config_path)
            and status.get("config_contract") == expected_status_config_contract
            and status.get("capture_errors") == []
            and isinstance(status_environment, dict)
            and exact_absolute_path(status_environment.get("pwd"), paths["work_dir"])
            and exact_absolute_path(
                status_environment.get("matlab_root"), EXPECTED_MATLAB.parent.parent
            )
            and status_environment.get("matlab_release") == "2025b"
            and isinstance(status_environment.get("matlab_version"), str)
            and bool(status_environment.get("matlab_version"))
            and isinstance(status_environment.get("computer"), str)
            and bool(status_environment.get("computer"))
            and isinstance(status_environment.get("pid"), int)
            and not isinstance(status_environment.get("pid"), bool)
            and status_environment.get("pid") > 0
            and status_environment.get("pid") == exit_record.get("matlab_pid")
            and execution_identity_pass
            and (
                (
                    success
                    and status.get("evidence_status") == "PASS"
                    and status.get("final_status") == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
                    and status.get("process_exit_semantics") == "ZERO"
                    and status.get("error_origin") == "NONE"
                    and not status.get("failed_stage")
                )
                or (
                    author_failure
                    and status.get("evidence_status") == "PASS_FAILURE_EVIDENCE"
                    and status.get("final_status") == "EXECUTION_FAIL_AUTHOR_ERROR_CAPTURED"
                    and status.get("process_exit_semantics") == "NONZERO_RETHROW"
                    and status.get("error_origin") == "AUTHOR_CALL"
                    and status.get("failed_stage") in {"UPSTREAM_ORIGINAL", "CANDIDATE_ORIGINAL_MLX"}
                )
            )
        )
        add_check(
            checks,
            f"S3-STATUS-TERMINAL-CONTRACT-{run_index:02d}",
            "execution",
            status_terminal_pass,
            "exact success terminal tuple or exact author-failure terminal tuple with error_origin",
            {key: status.get(key) for key in ("schema_version", "route_id", "replicate", "execution_status", "evidence_status", "final_status", "process_exit_semantics", "error_origin", "failed_stage")},
            paths["run_status_json"],
        )
        add_check(
            checks,
            f"S3-EXECUTION-IDENTITY-{run_index:02d}",
            "execution",
            execution_identity_pass,
            {
                "status_schema": "BOARD21_STEP3_ROUTE_STATUS_V2",
                "process_exit_schema": "BOARD21_STEP3_PROCESS_EXIT_V2",
                "launcher_pid": "positive integer, may differ from matlab_pid",
                "matlab_pid": "positive integer equal to status.environment.pid",
                "execution_token": "same uppercase 64-hex in status and process exit",
                "execution_token_sha256": "independently recomputed",
                "execution_token_match": True,
            },
            {
                "status_schema": status.get("schema_version"),
                "process_exit_schema": exit_record.get("schema_version"),
                "launcher_pid": exit_record.get("launcher_pid"),
                "matlab_pid": exit_record.get("matlab_pid"),
                "status_environment_pid": (
                    status_environment.get("pid")
                    if isinstance(status_environment, dict)
                    else None
                ),
                "status_execution_token": status_execution_token,
                "exit_execution_token": exit_execution_token,
                "execution_token_sha256": exit_record.get(
                    "execution_token_sha256"
                ),
                "recomputed_execution_token_sha256": recomputed_execution_token_sha256,
                "execution_token_match": exit_record.get(
                    "execution_token_match"
                ),
            },
            paths["process_exit_json"],
        )

        artifact_audit = validate_artifact_seal(
            exit_record,
            paths,
            success,
            author_failure,
            str(status.get("failed_stage", "")),
            bool(status_scientific_names),
        )
        artifact_audit["scientific_name_error"] = scientific_name_error
        artifact_audit["status_scientific_names"] = status_scientific_names
        artifact_audit["scientific_variable_count_match"] = (
            exit_record.get("scientific_variable_count")
            == len(status_scientific_names)
        )
        artifact_audit["pass"] &= bool(
            not scientific_name_error
            and artifact_audit["scientific_variable_count_match"]
        )
        if artifact_audit["pass"]:
            artifact_pass_count += 1
        add_check(
            checks,
            f"S3-ARTIFACT-SEAL-{run_index:02d}",
            "artifact_seal",
            artifact_audit["pass"],
            {"artifact_count": 14, "all_paths_sizes_hashes_required_and_stream_hashes_match": True},
            artifact_audit,
            paths["process_exit_json"],
        )

        expected_matlab_expression = (
            f"addpath('{str(SCRIPT.parent).replace(chr(39), chr(39) * 2)}'); "
            "run_one_board21_energy_route("
            f"'{str(config_path).replace(chr(39), chr(39) * 2)}');"
        )
        expected_matlab_command = [
            str(EXPECTED_MATLAB), "-batch", expected_matlab_expression
        ]
        exit_semantics_pass = bool(
            exit_record.get("schema_version") == "BOARD21_STEP3_PROCESS_EXIT_V2"
            and exit_record.get("route_id") == route_id
            and exit_record.get("replicate") == replicate
            and exit_record.get("command") == expected_matlab_command
            and exit_record.get("display_command")
            == subprocess.list2cmdline(expected_matlab_command)
            and exact_absolute_path(exit_record.get("cwd"), paths["work_dir"])
            and is_strict_positive_int(exit_record.get("launcher_pid"))
            and is_strict_positive_int(exit_record.get("matlab_pid"))
            and execution_identity_pass
            and isinstance(exit_record.get("duration_seconds"), (int, float))
            and exit_record.get("duration_seconds") >= 0
            and exit_record.get("timeout_seconds") == 900
            and exit_record.get("timed_out") is False
            and exit_record.get("status_json_exists") is True
            and exit_record.get("status_json_sha256") == sha256_file(paths["run_status_json"])
            and exit_record.get("status_read_error") == ""
            and exit_record.get("runner_execution_status") == status.get("execution_status")
            and exit_record.get("runner_evidence_status") == status.get("evidence_status")
            and exit_record.get("runner_final_status") == status.get("final_status")
            and exit_record.get("evidence_capture_ok") is True
            and (
                (success and exit_record.get("returncode") == 0 and exit_record.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED")
                or (author_failure and isinstance(exit_record.get("returncode"), int) and exit_record.get("returncode") != 0 and exit_record.get("orchestration_status") == "AUTHOR_FAILURE_EVIDENCE_CAPTURED")
            )
        )
        add_check(
            checks,
            f"S3-PROCESS-EXIT-CONTRACT-{run_index:02d}",
            "execution",
            exit_semantics_pass,
            "exact process exit schema, status seal, no timeout, and success/author-failure semantics",
            exit_record,
            paths["process_exit_json"],
        )

        expected_runtime_hashes: list[dict[str, Any]] = []
        for contract in expected_contracts:
            for layer, field in (
                ("author_original", "author_original_path"),
                ("step1_frozen", "frozen_path"),
                ("run_copy", "staged_path"),
            ):
                expected_runtime_hashes.append(
                    {
                        "layer": layer,
                        "kind": contract["kind"],
                        "path": contract[field],
                        "expected_sha256": contract["expected_sha256"],
                        "actual_sha256": contract["expected_sha256"],
                        "match": True,
                    }
                )
        before_hashes = normalize_struct_list(status.get("input_hashes_before"), "status.input_hashes_before")
        after_hashes = normalize_struct_list(status.get("input_hashes_after"), "status.input_hashes_after")
        add_check(
            checks,
            f"S3-RUNTIME-INPUT-HASHES-{run_index:02d}",
            "input_hash",
            before_hashes == expected_runtime_hashes and after_hashes == expected_runtime_hashes,
            {"before": expected_runtime_hashes, "after": expected_runtime_hashes},
            {"before": before_hashes, "after": after_hashes},
            paths["run_status_json"],
        )
        expected_runtime_instruments = [
            {
                "layer": "instrument", "kind": name,
                "path": str((SCRIPT.parent / name).resolve()),
                "expected_sha256": sealed_tools[name],
                "actual_sha256": sealed_tools[name], "match": True,
            }
            for name in INSTRUMENT_ORDER
        ]
        runtime_instruments = normalize_struct_list(status.get("instrument_contracts"), "status.instrument_contracts")
        add_check(
            checks,
            f"S3-RUNTIME-INSTRUMENTS-{run_index:02d}",
            "instrumentation",
            runtime_instruments == expected_runtime_instruments,
            expected_runtime_instruments,
            runtime_instruments,
            paths["run_status_json"],
        )
        expected_which = [
            {"name": route["upstream"], "expected": str(paths["upstream_file"]), "actual": str(paths["upstream_file"]), "match": True},
            {"name": route["candidate"], "expected": str(paths["candidate_mlx"]), "actual": str(paths["candidate_mlx"]), "match": True},
        ]
        which_rows = normalize_struct_list(status.get("which_contracts"), "status.which_contracts")
        add_check(checks, f"S3-WHICH-{run_index:02d}", "path_resolution", which_rows == expected_which, expected_which, which_rows, paths["run_status_json"])

        expected_work_files = sorted(
            [
                {"name": route[kind], "path": str(paths["upstream_file" if kind == "upstream" else "candidate_mlx"]), "bytes": int(manifest_rows[route[kind]]["frozen_size_bytes"]), "sha256": SOURCES[route[kind]]}
                for kind in ("upstream", "candidate")
            ],
            key=lambda item: item["name"],
        )
        before_files = sorted(normalize_struct_list(status.get("work_files_before"), "status.work_files_before"), key=lambda item: item.get("name", ""))
        after_files = sorted(normalize_struct_list(status.get("work_files_after"), "status.work_files_after"), key=lambda item: item.get("name", ""))
        add_check(
            checks,
            f"S3-WORK-WHITELIST-{run_index:02d}",
            "work_isolation",
            before_files == expected_work_files and after_files == expected_work_files,
            {"before": expected_work_files, "after": expected_work_files},
            {"before": before_files, "after": after_files},
            paths["work_dir"],
        )

        required_hdf5: set[str] = set()
        if status_scientific_names:
            required_hdf5.add("scientific_mat")
        if success:
            required_hdf5.update({"workspace_after_upstream", "workspace_success"})
        elif author_failure:
            required_hdf5.add("workspace_failure")
            if status.get("failed_stage") == "CANDIDATE_ORIGINAL_MLX":
                required_hdf5.add("workspace_after_upstream")
        hdf5_audit = inspect_hdf5_files(paths, required_hdf5)
        if hdf5_audit["pass"]:
            hdf5_pass_count += 1
        add_check(
            checks,
            f"S3-MAT-HDF5-READABLE-{run_index:02d}",
            "workspace",
            hdf5_audit["pass"],
            {"required_hdf5": sorted(required_hdf5), "all_readable": True},
            hdf5_audit,
            paths["output_dir"],
        )

        inventory_error = ""
        inventory_details: dict[str, Any] = {}
        inventory_pass = False
        after_final_inventory: list[dict[str, Any]] = []
        try:
            inventory = load_json(paths["variable_inventory_json"])
            if set(inventory) != {"after_clear", "after_upstream", "after_candidate_or_failure"}:
                raise ValueError(f"inventory top-level fields mismatch: {sorted(inventory)}")
            after_clear_inventory = inventory_records(inventory.get("after_clear"), "after_clear")
            after_upstream_inventory = inventory_records(inventory.get("after_upstream"), "after_upstream")
            after_final_inventory = inventory_records(inventory.get("after_candidate_or_failure"), "after_candidate_or_failure")
            inventory_details["after_clear_count"] = len(after_clear_inventory)
            inventory_pass = len(after_clear_inventory) == 0
            upstream_stage_pass = any(
                item.get("name") == "upstream_original" and item.get("status") == "PASS"
                for item in normalize_struct_list(status.get("stages"), "status.stages")
            )
            if upstream_stage_pass:
                upstream_comparison = compare_inventory_to_workspace(
                    after_upstream_inventory, paths["workspace_after_upstream"], "after_upstream"
                )
                upstream_names = set(h5_names(paths["workspace_after_upstream"]))
                upstream_comparison["required_upstream_variables_present"] = set(route["upstream_required"]).issubset(upstream_names)
                upstream_comparison["pass"] &= upstream_comparison["required_upstream_variables_present"]
                inventory_details["upstream"] = upstream_comparison
                inventory_pass &= upstream_comparison["pass"]
            else:
                no_upstream_snapshot = status.get("failed_stage") == "UPSTREAM_ORIGINAL" and not paths["workspace_after_upstream"].exists() and not after_upstream_inventory
                inventory_details["upstream"] = {"expected_author_failure_before_snapshot": True, "actual": no_upstream_snapshot, "pass": no_upstream_snapshot}
                inventory_pass &= no_upstream_snapshot
            final_workspace = paths["workspace_success"] if success else paths["workspace_failure"]
            final_comparison = compare_inventory_to_workspace(after_final_inventory, final_workspace, "after_candidate_or_failure")
            final_nonempty = len(h5_names(final_workspace)) > 0
            final_comparison["nonempty_workspace"] = final_nonempty
            final_comparison["nonempty_required"] = success
            if success:
                final_comparison["pass"] &= final_nonempty
            inventory_details["final"] = final_comparison
            inventory_pass &= final_comparison["pass"]
        except Exception as error:
            inventory_error = f"{type(error).__name__}: {error}"
            inventory_pass = False
        if inventory_pass:
            inventory_pass_count += 1
        add_check(
            checks,
            f"S3-INVENTORY-WORKSPACE-CROSSCHECK-{run_index:02d}",
            "workspace",
            inventory_pass,
            {
                "structure_exact": True,
                "workspace_names_classes_shapes_sparse_complex_global_match": True,
                "unsupported_root_groups_or_sparse_objects": "REJECT",
                "final_workspace_nonempty_if_success": True,
                "failure_workspace_may_be_empty": True,
            },
            {"error": inventory_error, "details": inventory_details},
            paths["variable_inventory_json"],
        )

        final_workspace = (
            paths["workspace_success"] if success else paths["workspace_failure"]
        )
        scientific_cross = scientific_mat_crosscheck(
            paths,
            status,
            status_scientific_names,
            after_final_inventory,
            final_workspace,
        )
        scientific_cross["top_level_name_parse_error"] = scientific_name_error
        scientific_cross["pass"] = bool(
            scientific_cross.get("pass") and not scientific_name_error
        )
        add_check(
            checks,
            f"S3-SCIENTIFIC-MAT-CROSSCHECK-{run_index:02d}",
            "scientific_output",
            scientific_cross["pass"],
            {
                "scientific_mat_exists_iff_selected_variables_nonempty": True,
                "root_names_exactly_equal_both_status_lists": True,
                "every_selected_variable_matches_inventory_and_final_workspace_metadata_and_exact_content": True,
            },
            scientific_cross,
            paths["scientific_mat"],
        )

        run_record: dict[str, Any] = {
            "route_id": route_id,
            "replicate": replicate,
            "status": status,
            "exit": exit_record,
            "science_valid": False,
            "failure_evidence_valid": False,
            "artifact_audit_pass": artifact_audit["pass"],
            "hdf5_audit_pass": hdf5_audit["pass"],
            "inventory_pass": inventory_pass,
            "scientific_cross_pass": scientific_cross["pass"],
        }
        if success:
            scientific_records: dict[str, dict[str, Any]] = {}
            stored_sums: dict[str, float] = {}
            recomputed_sums: dict[str, float] = {}
            totals: dict[str, float] = {}
            recomputed_totals: dict[str, float] = {}
            lengths: list[int] = []
            formula_error = ""
            formula_match = False
            status_match = False
            required_variable_audit_match = False
            required_variable_audit_types_pass = False
            status_summary_numeric_types_pass = False
            actual_required_variable_audit: list[dict[str, Any]] = []
            expected_required_variable_audit = [
                {
                    "name": name,
                    "matlab_class": "double",
                    "is_double": True,
                    "is_real": True,
                    "is_dense": True,
                    "is_global": False,
                    "is_finite": True,
                    "numel": count,
                    "storage_contract_pass": True,
                }
                for name, count in zip(
                    REQUIRED_FINAL,
                    [*route["lengths"], 1, 1, 1, 1, 1],
                    strict=True,
                )
            ]
            sum_comparisons: dict[str, dict[str, Any]] = {}
            total_comparisons: dict[str, dict[str, Any]] = {}
            status_comparisons: dict[str, dict[str, Any]] = {}
            try:
                names = h5_names(paths["scientific_mat"])
                if not set(REQUIRED_FINAL).issubset(names):
                    raise KeyError(f"missing required scientific variables: {sorted(set(REQUIRED_FINAL) - names)}")
                if not set(REQUIRED_FINAL).issubset(status_scientific_names):
                    raise KeyError(
                        "required scientific variables absent from status selection: "
                        f"{sorted(set(REQUIRED_FINAL) - set(status_scientific_names))}"
                    )
                for name in REQUIRED_FINAL:
                    scientific_records[name] = finite_numeric_record(paths["scientific_mat"], name)
                lengths = [
                    int(np.asarray(scientific_records[name]["value"]).size)
                    for name in ("E_total", "E_total_guyan", "E_total_cb")
                ]
                if lengths != route["lengths"]:
                    raise ValueError(f"energy length mismatch: expected={route['lengths']}, actual={lengths}")
                for name in ("energy_sum_orig", "energy_sum_guyan", "energy_sum_cb"):
                    stored_sums[name] = scalar_from_record(scientific_records[name], name)
                for name in ("total_increase_guyan", "total_increase_cb"):
                    totals[name] = scalar_from_record(scientific_records[name], name)
                original_vector = np.asarray(
                    scientific_records["E_total"]["value"], dtype=np.float64
                ).reshape(-1)
                guyan_vector = np.asarray(
                    scientific_records["E_total_guyan"]["value"], dtype=np.float64
                ).reshape(-1)
                cb_vector = np.asarray(
                    scientific_records["E_total_cb"]["value"], dtype=np.float64
                ).reshape(-1)
                if route["sum_scope"] == "all_vectors":
                    recomputed_sums = {
                        "energy_sum_orig": float(np.sum(original_vector)),
                        "energy_sum_guyan": float(np.sum(guyan_vector)),
                        "energy_sum_cb": float(np.sum(cb_vector)),
                    }
                elif route["sum_scope"] == "selected_original_and_cb":
                    retained = np.asarray(route["retained_zero_based"], dtype=int)
                    if np.any(retained < 0) or np.any(retained >= original_vector.size) or np.any(retained >= cb_vector.size):
                        raise IndexError(f"retained index outside energy vector for {route_id}")
                    recomputed_sums = {
                        "energy_sum_orig": float(np.sum(original_vector[retained])),
                        "energy_sum_guyan": float(np.sum(guyan_vector)),
                        "energy_sum_cb": float(np.sum(cb_vector[retained])),
                    }
                else:
                    raise ValueError(f"unknown sum scope: {route['sum_scope']}")
                sum_comparisons = {
                    name: strict_abs_rel_comparison(
                        stored_sums[name], recomputed_sums[name]
                    )
                    for name in stored_sums
                }
                sums_match = all(
                    comparison["pass"]
                    for comparison in sum_comparisons.values()
                )
                if route["denominator"] == "original":
                    denominator = recomputed_sums["energy_sum_orig"]
                elif route["denominator"] == "guyan_for_both":
                    denominator = recomputed_sums["energy_sum_guyan"]
                else:
                    raise ValueError(
                        f"unknown historical denominator: {route['denominator']}"
                    )
                if not math.isfinite(denominator) or denominator == 0.0:
                    raise ZeroDivisionError(f"historical denominator invalid: {denominator}")
                recomputed_totals = {
                    "total_increase_guyan": (recomputed_sums["energy_sum_guyan"] - recomputed_sums["energy_sum_orig"]) / denominator * 100.0,
                    "total_increase_cb": (recomputed_sums["energy_sum_cb"] - recomputed_sums["energy_sum_orig"]) / denominator * 100.0,
                }
                total_comparisons = {
                    name: strict_abs_rel_comparison(
                        totals[name], recomputed_totals[name]
                    )
                    for name in totals
                }
                totals_match = all(
                    comparison["pass"]
                    for comparison in total_comparisons.values()
                )
                formula_match = sums_match and totals_match
                status_scientific = status.get("scientific")
                if not isinstance(status_scientific, dict):
                    raise TypeError("status.scientific is not an object")
                actual_required_variable_audit = normalize_struct_list(
                    status_scientific.get("required_variable_audit"),
                    "status.scientific.required_variable_audit",
                )
                expected_required_audit_fields = set(
                    expected_required_variable_audit[0]
                )
                required_variable_audit_types_pass = bool(
                    len(actual_required_variable_audit) == len(REQUIRED_FINAL)
                    and all(
                        set(item) == expected_required_audit_fields
                        and isinstance(item.get("name"), str)
                        and isinstance(item.get("matlab_class"), str)
                        and all(
                            type(item.get(field)) is bool
                            for field in (
                                "is_double",
                                "is_real",
                                "is_dense",
                                "is_global",
                                "is_finite",
                                "storage_contract_pass",
                            )
                        )
                        and is_strict_positive_int(item.get("numel"))
                        for item in actual_required_variable_audit
                    )
                )
                required_variable_audit_match = bool(
                    required_variable_audit_types_pass
                    and actual_required_variable_audit
                    == expected_required_variable_audit
                )
                status_summary_numeric_types_pass = all(
                    isinstance(status_scientific.get(name), (int, float))
                    and not isinstance(status_scientific.get(name), bool)
                    and math.isfinite(float(status_scientific.get(name)))
                    for name in (*stored_sums, *totals)
                )
                status_comparisons = {
                    name: strict_abs_rel_comparison(
                        status_scientific.get(name), value
                    )
                    for name, value in {**stored_sums, **totals}.items()
                }
                status_match = bool(
                    status_scientific.get("required_present") is True
                    and status_scientific.get("missing_required") == []
                    and status_scientific.get("lengths_match") is True
                    and status_scientific.get("all_finite") is True
                    and status_scientific.get("required_variables_valid") is True
                    and required_variable_audit_match
                    and status_scientific.get("summary_scalars_valid") is True
                    and status_summary_numeric_types_pass
                    and status_scientific.get("energy_lengths") == route["lengths"]
                    and all(
                        is_strict_positive_int(value)
                        for value in status_scientific.get("energy_lengths", [])
                    )
                    and status_scientific.get("expected_energy_lengths")
                    == route["lengths"]
                    and status_scientific.get("embedded_historical_percent")
                    == route["history"]
                    and all(
                        comparison["pass"]
                        for comparison in status_comparisons.values()
                    )
                )
            except Exception as error:
                formula_error = f"{type(error).__name__}: {error}"
            science_valid = bool(
                not formula_error
                and formula_match
                and status_match
                and status_terminal_pass
                and exit_semantics_pass
                and artifact_audit["pass"]
                and hdf5_audit["pass"]
                and inventory_pass
                and scientific_cross["pass"]
                and route_formula_source_contract_pass
                and status.get("error_origin") == "NONE"
                and exit_record.get("returncode") == 0
                and paths["workspace_success"].is_file()
            )
            add_check(
                checks,
                f"S3-SCIENTIFIC-FORMULA-{run_index:02d}",
                "scientific_output",
                science_valid,
                {
                    "lengths": route["lengths"],
                    "sum_match": True,
                    "formula_match": True,
                    "status_match": True,
                    "formula_source_contract_pass": True,
                    "formula_exception": "",
                },
                {
                    "lengths": lengths,
                    "stored_sums": stored_sums,
                    "recomputed_sums": recomputed_sums,
                    "sum_comparisons": sum_comparisons,
                    "totals": totals,
                    "recomputed_totals": recomputed_totals,
                    "total_comparisons": total_comparisons,
                    "formula_match": formula_match,
                    "status_match": status_match,
                    "status_comparisons": status_comparisons,
                    "expected_required_variable_audit": expected_required_variable_audit,
                    "actual_required_variable_audit": actual_required_variable_audit,
                    "required_variable_audit_types_pass": required_variable_audit_types_pass,
                    "required_variable_audit_match": required_variable_audit_match,
                    "status_summary_numeric_types_pass": status_summary_numeric_types_pass,
                    "status_terminal_pass": status_terminal_pass,
                    "exit_semantics_pass": exit_semantics_pass,
                    "artifact_audit_pass": artifact_audit["pass"],
                    "hdf5_audit_pass": hdf5_audit["pass"],
                    "inventory_pass": inventory_pass,
                    "scientific_cross_pass": scientific_cross["pass"],
                    "formula_source_contract_pass": (
                        route_formula_source_contract_pass
                    ),
                    "formula_exception": formula_error,
                },
                paths["scientific_mat"],
            )
            run_record.update(
                {
                    "outcome": "SUCCESS",
                    "science_valid": science_valid,
                    "scientific_records": scientific_records,
                    "totals": totals,
                    "formula_error": formula_error,
                }
            )
        elif author_failure:
            error_record = status.get("error") if isinstance(status.get("error"), dict) else {}
            stack_error = ""
            try:
                stack = normalize_struct_list(error_record.get("stack"), "status.error.stack")
            except Exception as error:
                stack = []
                stack_error = f"{type(error).__name__}: {error}"
            failed_stage = str(status.get("failed_stage", ""))
            expected_failed_file = paths["upstream_file"] if failed_stage == "UPSTREAM_ORIGINAL" else paths["candidate_mlx"]
            failure_workspace_names: list[str] = []
            failure_workspace_error = ""
            try:
                failure_workspace_names = sorted(h5_names(paths["workspace_failure"]))
            except Exception as error:
                failure_workspace_error = f"{type(error).__name__}: {error}"
            error_report_error = ""
            error_report_exact_match = False
            error_report_actual_sha256 = ""
            error_report_expected_sha256 = ""
            error_report_actual_size = -1
            error_report_expected_size = -1
            try:
                report_text = str(error_record.get("report", ""))
                if not report_text:
                    report_text = (
                        f"{error_record.get('identifier', '')}: "
                        f"{error_record.get('message', '')}"
                    )
                expected_report_bytes = (report_text + "\n").encode("utf-8")
                actual_report_bytes = paths["error_report"].read_bytes()
                actual_report_bytes.decode("utf-8", errors="strict")
                error_report_expected_size = len(expected_report_bytes)
                error_report_actual_size = len(actual_report_bytes)
                error_report_expected_sha256 = hashlib.sha256(
                    expected_report_bytes
                ).hexdigest().upper()
                error_report_actual_sha256 = hashlib.sha256(
                    actual_report_bytes
                ).hexdigest().upper()
                error_report_exact_match = actual_report_bytes == expected_report_bytes
            except Exception as error:
                error_report_error = f"{type(error).__name__}: {error}"
            failure_evidence_valid = bool(
                status_terminal_pass
                and exit_semantics_pass
                and artifact_audit["pass"]
                and hdf5_audit["pass"]
                and inventory_pass
                and scientific_cross["pass"]
                and status.get("error_origin") == "AUTHOR_CALL"
                and failed_stage in {"UPSTREAM_ORIGINAL", "CANDIDATE_ORIGINAL_MLX"}
                and exact_absolute_path(status.get("failed_file"), expected_failed_file)
                and isinstance(exit_record.get("returncode"), int)
                and exit_record.get("returncode") != 0
                and bool(error_record.get("identifier"))
                and bool(error_record.get("message"))
                and bool(error_record.get("report"))
                and not stack_error
                and len(stack) > 0
                and all(
                    bool(item.get("file"))
                    and bool(item.get("name"))
                    and is_positive_integral_number(item.get("line"))
                    for item in stack
                )
                and paths["workspace_failure"].is_file()
                and not failure_workspace_error
                and not error_report_error
                and error_report_exact_match
            )
            add_check(
                checks,
                f"S3-AUTHOR-FAILURE-EVIDENCE-{run_index:02d}",
                "failure_output",
                failure_evidence_valid,
                {
                    "error_origin": "AUTHOR_CALL",
                    "exact_failed_stage_and_file": True,
                    "nonempty_stack": True,
                    "readable_failure_workspace_may_be_empty": True,
                    "nonzero_returncode": True,
                    "artifact_hdf5_inventory_scientific_cross_gates": True,
                    "error_report_exact_utf8_match_to_status_error_report": True,
                },
                {
                    "failed_stage": failed_stage,
                    "failed_file": status.get("failed_file"),
                    "error_origin": status.get("error_origin"),
                    "identifier": error_record.get("identifier"),
                    "stack": stack,
                    "stack_error": stack_error,
                    "failure_workspace_names": failure_workspace_names,
                    "failure_workspace_error": failure_workspace_error,
                    "error_report_error": error_report_error,
                    "error_report_exact_match": error_report_exact_match,
                    "error_report_expected_size": error_report_expected_size,
                    "error_report_actual_size": error_report_actual_size,
                    "error_report_expected_sha256": error_report_expected_sha256,
                    "error_report_actual_sha256": error_report_actual_sha256,
                    "returncode": exit_record.get("returncode"),
                    "status_terminal_pass": status_terminal_pass,
                    "exit_semantics_pass": exit_semantics_pass,
                    "artifact_audit_pass": artifact_audit["pass"],
                    "hdf5_audit_pass": hdf5_audit["pass"],
                    "inventory_pass": inventory_pass,
                    "scientific_cross_pass": scientific_cross["pass"],
                },
                paths["run_status_json"],
            )
            run_record.update(
                {
                    "outcome": "FAILURE",
                    "failure_evidence_valid": failure_evidence_valid,
                    "error": error_record,
                    "stack": stack,
                    "totals": {},
                }
            )
        else:
            add_check(
                checks,
                f"S3-UNRECOGNIZED-OUTCOME-{run_index:02d}",
                "execution",
                False,
                ["EXECUTION_SUCCESS", "EXECUTION_FAIL"],
                status.get("execution_status"),
                paths["run_status_json"],
            )
            run_record.update({"outcome": "INVALID", "totals": {}})
        per_route_runs.setdefault(route_id, {})[replicate] = run_record

    orchestration_path = ORCHESTRATION_ROOT / "run_all_summary.json"
    orchestration = load_json(orchestration_path)
    expected_run_order_json = [
        {"order": order, "route_id": route_id, "replicate": replicate}
        for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1)
    ]
    route_process_records = normalize_struct_list(orchestration.get("route_process_records"), "orchestration.route_process_records")
    orchestration_route_details: list[dict[str, Any]] = []
    orchestration_routes_pass = len(route_process_records) == 14
    orchestration_route_identity_pass = len(route_process_records) == 14
    orchestration_route_execution_tokens: list[str] = []
    capture_root = ORCHESTRATION_ROOT / "subprocess_captures"
    process_root = ORCHESTRATION_ROOT / "process_snapshots"
    for order, expected_pair in enumerate(EXPECTED_RUN_ORDER, start=1):
        route_id, replicate = expected_pair
        matches = [record for record in route_process_records if record.get("order") == order]
        if len(matches) != 1:
            orchestration_routes_pass = False
            orchestration_route_identity_pass = False
            orchestration_route_details.append({"order": order, "record_count": len(matches), "pass": False})
            continue
        record = matches[0]
        config_info = config_by_pair[expected_pair]
        exit_record = exit_by_pair[expected_pair]
        stem = f"{order:02d}__{route_id}__{replicate}"
        stdout_path = capture_root / f"{stem}.stdout.log"
        stderr_path = capture_root / f"{stem}.stderr.log"
        stdout_hash = sha256_file(stdout_path) if stdout_path.is_file() else "MISSING"
        stderr_hash = sha256_file(stderr_path) if stderr_path.is_file() else "MISSING"
        stdout_terminal_json: dict[str, Any] = {}
        stdout_terminal_error = ""
        stdout_terminal_line = b""
        try:
            stdout_payload = stdout_path.read_bytes()
            stdout_terminal_json = terminal_json_from_bytes(
                stdout_payload, f"executor stdout {stem}"
            )
            stdout_terminal_line = terminal_json_line_bytes(
                stdout_payload, f"executor stdout {stem}"
            )
        except Exception as error:
            stdout_terminal_error = f"{type(error).__name__}: {error}"
        executor_terminal_deep_match = bool(
            not stdout_terminal_error and stdout_terminal_json == exit_record
        )
        stdout_terminal_canonical = (
            canonical_json_utf8(stdout_terminal_json)
            if not stdout_terminal_error
            else b""
        )
        route_execution_token = record.get("execution_token")
        route_execution_token_sha256 = (
            sha256_ascii_text(route_execution_token)
            if is_upper_sha256_text(route_execution_token)
            else ""
        )
        route_execution_identity_pass = bool(
            record.get("process_exit_schema_version")
            == "BOARD21_STEP3_PROCESS_EXIT_V2"
            and "pid" not in record
            and record.get("process_exit_schema_version")
            == exit_record.get("schema_version")
            and is_strict_positive_int(record.get("launcher_pid"))
            and record.get("launcher_pid") == exit_record.get("launcher_pid")
            and is_strict_positive_int(record.get("matlab_pid"))
            and record.get("matlab_pid") == exit_record.get("matlab_pid")
            and is_upper_sha256_text(route_execution_token)
            and route_execution_token == exit_record.get("execution_token")
            and record.get("execution_token_sha256")
            == route_execution_token_sha256
            and record.get("execution_token_sha256")
            == exit_record.get("execution_token_sha256")
            and record.get("execution_token_match") is True
            and record.get("execution_token_match")
            is exit_record.get("execution_token_match")
            and record.get("execution_identity_contract_pass") is True
        )
        orchestration_route_identity_pass &= route_execution_identity_pass
        if is_upper_sha256_text(route_execution_token):
            orchestration_route_execution_tokens.append(route_execution_token)
        expected_executor_command = [
            str(EXPECTED_PYTHON),
            str((SCRIPT.parent / "execute_board21_step3_route.py").resolve()),
            str(config_info["paths"]["config_json"]),
            "--timeout-seconds",
            "900",
        ]
        before_snapshot = process_root / f"{stem}__before.json"
        after_snapshot = process_root / f"{stem}__after.json"
        snapshot_pass = bool(
            before_snapshot.is_file() and json.loads(before_snapshot.read_text(encoding="utf-8")) == []
            and after_snapshot.is_file() and json.loads(after_snapshot.read_text(encoding="utf-8")) == []
        )
        record_pass = bool(
            record.get("order") == order
            and record.get("route_id") == route_id
            and record.get("replicate") == replicate
            and record.get("route_label_cn") == route_map[route_id]["route_label_cn"]
            and exact_absolute_path(record.get("config_path"), config_info["paths"]["config_json"])
            and record.get("config_sha256") == config_info["hash"]
            and record.get("executor_command") == expected_executor_command
            and exact_absolute_path(record.get("executor_cwd"), PROJECT_ROOT)
            and record.get("executor_timeout_seconds") == 1000
            and record.get("executor_timed_out") is False
            and record.get("executor_timeout_error") == ""
            and record.get("executor_internal_timeout_seconds") == 900
            and record.get("executor_internal_timed_out") is False
            and record.get("executor_status_contract_pass") is True
            and record.get("executor_artifact_exclusivity_match") is True
            and record.get("executor_all_required_artifacts_sealed") is True
            and record.get("executor_runtime_log_hashes_match") is True
            and record.get("executor_returncode") == 0
            and record.get("executor_capture_error") == ""
            and record.get("executor_parse_error") == ""
            and record.get("executor_terminal_json_match") is True
            and executor_terminal_deep_match
            and route_execution_identity_pass
            and exact_absolute_path(
                record.get("process_exit_json_path"),
                config_info["paths"]["process_exit_json"],
            )
            and record.get("process_exit_json_sha256")
            == sha256_file(config_info["paths"]["process_exit_json"])
            and record.get("process_exit_read_error") == ""
            and record.get("executor_terminal_json_line_sha256")
            == hashlib.sha256(stdout_terminal_line).hexdigest().upper()
            and record.get("executor_terminal_json_utf8_sha256")
            == hashlib.sha256(stdout_terminal_canonical).hexdigest().upper()
            and record.get("matlab_returncode") == exit_record.get("returncode")
            and record.get("orchestration_status") == exit_record.get("orchestration_status")
            and record.get("evidence_capture_ok") is True
            and record.get("instrument_sha256_before") == sealed_tools
            and record.get("instrument_sha256_after") == sealed_tools
            and record.get("instrument_seal_match") is True
            and record.get("post_instrument_error") == ""
            and record.get("target_processes_before") == []
            and record.get("target_processes_after") == []
            and record.get("post_process_query_error") == ""
            and exact_absolute_path(record.get("executor_stdout_path"), stdout_path)
            and exact_absolute_path(record.get("executor_stderr_path"), stderr_path)
            and record.get("executor_stdout_sha256") == stdout_hash
            and record.get("executor_stderr_sha256") == stderr_hash
            and snapshot_pass
        )
        orchestration_routes_pass &= record_pass
        orchestration_route_details.append(
            {
                "order": order,
                "pair": expected_pair,
                "expected_executor_command": expected_executor_command,
                "stdout_hash": stdout_hash,
                "stderr_hash": stderr_hash,
                "stdout_terminal_json": stdout_terminal_json,
                "stdout_terminal_error": stdout_terminal_error,
                "stdout_terminal_json_equals_process_exit": executor_terminal_deep_match,
                "stdout_terminal_json_line_sha256": hashlib.sha256(
                    stdout_terminal_line
                ).hexdigest().upper(),
                "stdout_terminal_json_utf8_sha256": hashlib.sha256(
                    stdout_terminal_canonical
                ).hexdigest().upper(),
                "route_execution_identity_pass": route_execution_identity_pass,
                "recomputed_execution_token_sha256": route_execution_token_sha256,
                "process_snapshots_empty": snapshot_pass,
                "record": record,
                "pass": record_pass,
            }
        )
    recomputed_unique_execution_token_count = len(
        set(orchestration_route_execution_tokens)
    )
    orchestration_execution_identity_pass = bool(
        orchestration_route_identity_pass
        and len(orchestration_route_execution_tokens) == 14
        and recomputed_unique_execution_token_count == 14
    )
    route_record_success_count = sum(
        record.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED"
        for record in route_process_records
    )
    route_record_failure_count = sum(
        record.get("orchestration_status")
        == "AUTHOR_FAILURE_EVIDENCE_CAPTURED"
        for record in route_process_records
    )
    exit_record_success_count = sum(
        record.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED"
        for record in exit_by_pair.values()
    )
    exit_record_failure_count = sum(
        record.get("orchestration_status")
        == "AUTHOR_FAILURE_EVIDENCE_CAPTURED"
        for record in exit_by_pair.values()
    )
    validated_outcome_success_count = sum(
        run.get("outcome") == "SUCCESS"
        for runs in per_route_runs.values()
        for run in runs.values()
    )
    validated_outcome_failure_count = sum(
        run.get("outcome") == "FAILURE"
        for runs in per_route_runs.values()
        for run in runs.values()
    )
    orchestration_count_contract_pass = bool(
        route_record_success_count == exit_record_success_count
        == validated_outcome_success_count
        == orchestration.get("author_execution_success_count")
        and route_record_failure_count == exit_record_failure_count
        == validated_outcome_failure_count
        == orchestration.get("author_execution_failure_count")
        and route_record_success_count + route_record_failure_count == 14
    )
    orchestration_header_pass = bool(
        orchestration.get("schema_version") == "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V3"
        and orchestration.get("status") == "PASS"
        and exact_absolute_path(orchestration.get("project_root"), PROJECT_ROOT)
        and exact_absolute_path(orchestration.get("expected_python"), EXPECTED_PYTHON)
        and orchestration.get("expected_run_order") == expected_run_order_json
        and orchestration.get("sealed_instrument_sha256") == sealed_tools
        and orchestration.get("expected_run_count") == 14
        and orchestration.get("executed_run_count") == 14
        and orchestration.get("unstarted_runs") == []
        and orchestration.get("infrastructure_failure") is False
        and orchestration.get("terminal_error") == {}
        and orchestration.get("interruption_point") == "FINAL_PROCESS_QUERY"
        and orchestration.get("subprocess_contract_pass") is True
        and orchestration.get("process_query_contract_pass") is True
        and orchestration.get("route_contract_pass") is True
        and orchestration.get("execution_identity_contract_pass") is True
        and is_strict_positive_int(
            orchestration.get("unique_execution_token_count")
        )
        and orchestration.get("unique_execution_token_count")
        == recomputed_unique_execution_token_count
        == 14
        and orchestration_execution_identity_pass
        and orchestration.get("author_execution_count_contract_pass") is True
        and exact_absolute_path(
            orchestration.get("process_query_capture_root"),
            ORCHESTRATION_ROOT / "process_query_captures",
        )
        and orchestration.get("timeout_contract_seconds")
        == {
            "stager_python": 120,
            "executor_python_wrapper": 1000,
            "matlab_inside_executor": 900,
            "powershell_process_query": 30,
        }
        and orchestration.get("started_with_target_process_count") == 0
        and orchestration.get("initial_target_processes") == []
        and orchestration.get("final_target_process_count") == 0
        and orchestration.get("final_target_processes") == []
        and orchestration.get("final_process_query_error") == ""
        and orchestration.get("matlab_process_count") == 0
        and orchestration_count_contract_pass
        and orchestration.get("stage_summary") == stage_summary
    )
    dry_summary = orchestration.get("dry_run_summary")
    orchestration_dry_pass = bool(
        isinstance(dry_summary, dict)
        and dry_summary.get("route_count") == 7
        and dry_summary.get("replicate_count") == 2
        and dry_summary.get("run_count") == 14
        and dry_summary.get("source_reference_count") == 14
        and dry_summary.get("unique_source_count") == 12
        and dry_summary.get("protected_input_count") == 53
        and dry_summary.get("category_counts") == EXPECTED_INPUT_CATEGORY_COUNTS
        and dry_summary.get("input_manifest_sha256") == INPUT_MANIFEST_SHA256
        and dry_summary.get("input_freeze_summary_sha256")
        == INPUT_FREEZE_SUMMARY_SHA256
        and dry_summary.get("instrument_sha256") == sealed_tools
    )
    subprocess_records = normalize_struct_list(
        orchestration.get("subprocess_records"), "orchestration.subprocess_records"
    )
    expected_subprocess_names = [
        "stager_dry_run",
        "stager_actual",
        *[
            f"{order:02d}__{route_id}__{replicate}"
            for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1)
        ],
    ]
    expected_subprocess_contracts: dict[str, dict[str, Any]] = {
        "stager_dry_run": {
            "command": [
                str(EXPECTED_PYTHON),
                str((SCRIPT.parent / "stage_board21_step3_runs.py").resolve()),
                "--dry-run",
            ],
            "timeout_seconds": 120,
            "terminal_json": dry_summary,
        },
        "stager_actual": {
            "command": [
                str(EXPECTED_PYTHON),
                str((SCRIPT.parent / "stage_board21_step3_runs.py").resolve()),
            ],
            "timeout_seconds": 120,
            "terminal_json": stage_summary,
        },
    }
    for order, pair in enumerate(EXPECTED_RUN_ORDER, start=1):
        route_id, replicate = pair
        name = f"{order:02d}__{route_id}__{replicate}"
        expected_subprocess_contracts[name] = {
            "command": [
                str(EXPECTED_PYTHON),
                str((SCRIPT.parent / "execute_board21_step3_route.py").resolve()),
                str(config_by_pair[pair]["paths"]["config_json"]),
                "--timeout-seconds",
                "900",
            ],
            "timeout_seconds": 1000,
            "terminal_json": exit_by_pair[pair],
        }
    subprocess_details: list[dict[str, Any]] = []
    subprocess_fields = {
        "name",
        "command",
        "cwd",
        "started_at",
        "finished_at",
        "duration_seconds",
        "timeout_seconds",
        "timed_out",
        "timeout_error",
        "environment_overrides",
        "returncode",
        "stdout_size_bytes",
        "stderr_size_bytes",
        "stdout_sha256",
        "stderr_sha256",
        "terminal_json",
        "terminal_json_error",
        "terminal_json_line_size_bytes",
        "terminal_json_line_sha256",
        "terminal_json_utf8_size_bytes",
        "terminal_json_utf8_sha256",
    }
    orchestration_subprocess_pass = (
        [item.get("name") for item in subprocess_records]
        == expected_subprocess_names
    )
    for item in subprocess_records:
        name = str(item.get("name", ""))
        contract = expected_subprocess_contracts.get(name)
        stdout_path = capture_root / f"{name}.stdout.log"
        stderr_path = capture_root / f"{name}.stderr.log"
        stdout_size = stdout_path.stat().st_size if stdout_path.is_file() else -1
        stderr_size = stderr_path.stat().st_size if stderr_path.is_file() else -1
        stdout_hash = sha256_file(stdout_path) if stdout_path.is_file() else "MISSING"
        stderr_hash = sha256_file(stderr_path) if stderr_path.is_file() else "MISSING"
        stdout_payload = stdout_path.read_bytes() if stdout_path.is_file() else b""
        terminal_value: dict[str, Any] = {}
        terminal_line = b""
        terminal_parse_error = ""
        try:
            terminal_value = terminal_json_from_bytes(
                stdout_payload, f"subprocess stdout {name}"
            )
            terminal_line = terminal_json_line_bytes(
                stdout_payload, f"subprocess stdout {name}"
            )
        except Exception as error:
            terminal_parse_error = f"{type(error).__name__}: {error}"
        expected_terminal = contract.get("terminal_json") if contract else None
        canonical_terminal = (
            canonical_json_utf8(terminal_value) if not terminal_parse_error else b""
        )
        item_pass = bool(
            contract is not None
            and name in expected_subprocess_names
            and set(item) == subprocess_fields
            and item.get("command") == contract["command"]
            and item.get("returncode") == 0
            and exact_absolute_path(item.get("cwd"), PROJECT_ROOT)
            and isinstance(item.get("started_at"), str)
            and bool(item.get("started_at"))
            and isinstance(item.get("finished_at"), str)
            and bool(item.get("finished_at"))
            and isinstance(item.get("duration_seconds"), (int, float))
            and not isinstance(item.get("duration_seconds"), bool)
            and item.get("duration_seconds") >= 0
            and item.get("timeout_seconds") == contract["timeout_seconds"]
            and item.get("timed_out") is False
            and item.get("timeout_error") == ""
            and item.get("environment_overrides")
            == {"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            and item.get("stdout_size_bytes") == stdout_size
            and item.get("stderr_size_bytes") == stderr_size
            and item.get("stdout_sha256") == stdout_hash
            and item.get("stderr_sha256") == stderr_hash
            and stderr_size == 0
            and not terminal_parse_error
            and terminal_value == expected_terminal
            and item.get("terminal_json") == expected_terminal
            and item.get("terminal_json_error") == ""
            and item.get("terminal_json_line_size_bytes") == len(terminal_line)
            and item.get("terminal_json_line_sha256")
            == hashlib.sha256(terminal_line).hexdigest().upper()
            and item.get("terminal_json_utf8_size_bytes")
            == len(canonical_terminal)
            and item.get("terminal_json_utf8_sha256")
            == hashlib.sha256(canonical_terminal).hexdigest().upper()
        )
        orchestration_subprocess_pass &= item_pass
        subprocess_details.append(
            {
                "name": name,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "stdout_size": stdout_size,
                "stderr_size": stderr_size,
                "stdout_sha256": stdout_hash,
                "stderr_sha256": stderr_hash,
                "expected_contract": contract,
                "terminal_json": terminal_value,
                "terminal_parse_error": terminal_parse_error,
                "terminal_json_matches_expected": terminal_value
                == expected_terminal,
                "terminal_json_line_size_bytes": len(terminal_line),
                "terminal_json_line_sha256": hashlib.sha256(
                    terminal_line
                ).hexdigest().upper(),
                "terminal_json_utf8_size_bytes": len(canonical_terminal),
                "terminal_json_utf8_sha256": hashlib.sha256(
                    canonical_terminal
                ).hexdigest().upper(),
                "record": item,
                "pass": item_pass,
            }
        )

    process_query_records = normalize_struct_list(
        orchestration.get("process_query_records"),
        "orchestration.process_query_records",
    )
    process_query_script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding=[Console]::OutputEncoding; "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw|pdftoppm)\\.exe$'} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    expected_process_query_command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        process_query_script,
    ]
    process_query_capture_root = ORCHESTRATION_ROOT / "process_query_captures"
    expected_process_queries: list[dict[str, Any]] = [
        {
            "query_name": "00__initial",
            "snapshot": process_root / "00__initial.json",
            "stdout": process_query_capture_root / "00__initial.stdout.log",
            "stderr": process_query_capture_root / "00__initial.stderr.log",
            "summary_processes": orchestration.get("initial_target_processes"),
        }
    ]
    route_record_by_order = {
        int(record["order"]): record
        for record in route_process_records
        if isinstance(record.get("order"), int)
    }
    for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1):
        stem = f"{order:02d}__{route_id}__{replicate}"
        route_record = route_record_by_order.get(order, {})
        expected_process_queries.extend(
            [
                {
                    "query_name": f"{stem}__before",
                    "snapshot": process_root / f"{stem}__before.json",
                    "stdout": process_query_capture_root
                    / f"{stem}__before.stdout.log",
                    "stderr": process_query_capture_root
                    / f"{stem}__before.stderr.log",
                    "summary_processes": route_record.get(
                        "target_processes_before"
                    ),
                },
                {
                    "query_name": f"{stem}__after",
                    "snapshot": process_root / f"{stem}__after.json",
                    "stdout": process_query_capture_root
                    / f"{stem}__after.stdout.log",
                    "stderr": process_query_capture_root
                    / f"{stem}__after.stderr.log",
                    "summary_processes": route_record.get(
                        "target_processes_after"
                    ),
                },
            ]
        )
    expected_process_queries.append(
        {
            "query_name": "99__final",
            "snapshot": process_root / "99__final.json",
            "stdout": process_query_capture_root / "99__final.stdout.log",
            "stderr": process_query_capture_root / "99__final.stderr.log",
            "summary_processes": orchestration.get("final_target_processes"),
        }
    )
    process_query_fields = {
        "schema_version",
        "query_name",
        "command",
        "cwd",
        "started_at",
        "finished_at",
        "duration_seconds",
        "timeout_seconds",
        "timed_out",
        "timeout_error",
        "returncode",
        "stdout_size_bytes",
        "stderr_size_bytes",
        "stdout_sha256",
        "stderr_sha256",
        "stdout_path",
        "stderr_path",
        "capture_error",
        "capture_match",
        "stderr_text",
        "parse_error",
        "raw_process_count",
        "filtered_process_count",
        "processes",
        "ok",
    }
    process_query_details: list[dict[str, Any]] = []
    query_owner_pids: list[int] = []
    orchestration_process_query_pass = bool(
        len(process_query_records) == 30
        and len(expected_process_queries) == 30
        and [item.get("query_name") for item in process_query_records]
        == [item["query_name"] for item in expected_process_queries]
    )
    empty_sha256 = hashlib.sha256(b"").hexdigest().upper()
    for index, expected_query in enumerate(expected_process_queries):
        if index >= len(process_query_records):
            orchestration_process_query_pass = False
            process_query_details.append(
                {
                    "query_name": expected_query["query_name"],
                    "record_missing": True,
                    "pass": False,
                }
            )
            continue
        item = process_query_records[index]
        snapshot_path = expected_query["snapshot"]
        snapshot_error = ""
        try:
            snapshot_value = json.loads(
                snapshot_path.read_text(encoding="utf-8")
            )
        except Exception as error:
            snapshot_value = None
            snapshot_error = f"{type(error).__name__}: {error}"
        capture_error = ""
        raw_processes: list[dict[str, Any]] = []
        independent_filtered_processes: list[dict[str, Any]] = []
        query_owner_candidates: list[dict[str, Any]] = []
        stdout_path = expected_query["stdout"]
        stderr_path = expected_query["stderr"]
        try:
            stdout_bytes = stdout_path.read_bytes()
            stderr_bytes = stderr_path.read_bytes()
            stdout_text = stdout_bytes.decode("utf-8-sig", errors="strict").strip()
            raw_value: Any = [] if not stdout_text else json.loads(stdout_text)
            if isinstance(raw_value, dict):
                raw_value = [raw_value]
            if not isinstance(raw_value, list) or not all(
                isinstance(raw_item, dict) for raw_item in raw_value
            ):
                raise TypeError("raw process query capture is not an object array")
            raw_processes = raw_value
            query_owner_candidates = [
                raw_item
                for raw_item in raw_processes
                if str(raw_item.get("Name", "")).casefold()
                in {"python.exe", "pythonw.exe"}
                and "run_board21_step3_all.py"
                in str(raw_item.get("CommandLine", "")).casefold()
                and is_positive_integral_number(raw_item.get("ProcessId"))
            ]
            if len(query_owner_candidates) != 1:
                raise ValueError(
                    "raw process query capture must identify exactly one run_all owner; "
                    f"found={len(query_owner_candidates)}"
                )
            query_owner_pid = int(query_owner_candidates[0]["ProcessId"])
            query_owner_pids.append(query_owner_pid)
            board_token = str(BOARD_ROOT).casefold()
            for raw_item in raw_processes:
                pid = int(raw_item.get("ProcessId") or -1)
                name = str(raw_item.get("Name") or "")
                command_line = str(raw_item.get("CommandLine") or "")
                if pid == query_owner_pid:
                    continue
                if (
                    name.casefold() == "matlab.exe"
                    or board_token in command_line.casefold()
                ):
                    independent_filtered_processes.append(raw_item)
        except Exception as error:
            stdout_bytes = b""
            stderr_bytes = b""
            capture_error = f"{type(error).__name__}: {error}"
        stdout_hash_value = item.get("stdout_sha256")
        stderr_hash_value = item.get("stderr_sha256")
        item_pass = bool(
            set(item) == process_query_fields
            and item.get("schema_version")
            == "BOARD21_STEP3_PROCESS_QUERY_V1"
            and item.get("query_name") == expected_query["query_name"]
            and item.get("command") == expected_process_query_command
            and exact_absolute_path(item.get("cwd"), PROJECT_ROOT)
            and isinstance(item.get("started_at"), str)
            and bool(item.get("started_at"))
            and isinstance(item.get("finished_at"), str)
            and bool(item.get("finished_at"))
            and isinstance(item.get("duration_seconds"), (int, float))
            and not isinstance(item.get("duration_seconds"), bool)
            and item.get("duration_seconds") >= 0
            and item.get("timeout_seconds") == 30
            and item.get("timed_out") is False
            and item.get("timeout_error") == ""
            and item.get("returncode") == 0
            and exact_absolute_path(item.get("stdout_path"), stdout_path)
            and exact_absolute_path(item.get("stderr_path"), stderr_path)
            and item.get("capture_error") == ""
            and item.get("capture_match") is True
            and not capture_error
            and isinstance(item.get("stdout_size_bytes"), int)
            and not isinstance(item.get("stdout_size_bytes"), bool)
            and item.get("stdout_size_bytes") == len(stdout_bytes)
            and item.get("stderr_size_bytes") == 0
            and isinstance(stdout_hash_value, str)
            and stdout_hash_value
            == hashlib.sha256(stdout_bytes).hexdigest().upper()
            and stderr_hash_value
            == hashlib.sha256(stderr_bytes).hexdigest().upper()
            and stderr_hash_value == empty_sha256
            and stderr_bytes == b""
            and item.get("stderr_text") == ""
            and item.get("parse_error") == ""
            and isinstance(item.get("raw_process_count"), int)
            and not isinstance(item.get("raw_process_count"), bool)
            and item.get("raw_process_count") == len(raw_processes)
            and item.get("filtered_process_count")
            == len(independent_filtered_processes)
            and item.get("processes") == independent_filtered_processes
            and independent_filtered_processes == []
            and item.get("ok") is True
            and not snapshot_error
            and snapshot_value == []
            and snapshot_value == expected_query["summary_processes"]
        )
        orchestration_process_query_pass &= item_pass
        process_query_details.append(
            {
                "query_name": expected_query["query_name"],
                "snapshot_path": str(snapshot_path),
                "snapshot_value": snapshot_value,
                "snapshot_error": snapshot_error,
                "stdout_path": str(stdout_path),
                "stderr_path": str(stderr_path),
                "raw_capture_error": capture_error,
                "raw_process_count": len(raw_processes),
                "query_owner_candidates": query_owner_candidates,
                "independent_filtered_processes": independent_filtered_processes,
                "summary_processes": expected_query["summary_processes"],
                "record": item,
                "pass": item_pass,
            }
        )
    expected_process_query_capture_files = sorted(
        str(expected_query[kind].resolve())
        for expected_query in expected_process_queries
        for kind in ("stdout", "stderr")
    )
    process_query_capture_set_error = ""
    try:
        actual_process_query_capture_files = sorted(
            str(path.resolve())
            for path in process_query_capture_root.rglob("*")
            if path.is_file()
        )
        unexpected_capture_directories = sorted(
            str(path.resolve())
            for path in process_query_capture_root.rglob("*")
            if path.is_dir()
        )
    except Exception as error:
        actual_process_query_capture_files = []
        unexpected_capture_directories = []
        process_query_capture_set_error = f"{type(error).__name__}: {error}"
    process_query_capture_set_pass = bool(
        process_query_capture_root.is_dir()
        and not process_query_capture_set_error
        and actual_process_query_capture_files
        == expected_process_query_capture_files
        and not unexpected_capture_directories
        and len(query_owner_pids) == 30
        and len(set(query_owner_pids)) == 1
    )
    orchestration_process_query_pass &= process_query_capture_set_pass
    process_query_capture_set_audit = {
        "capture_root": str(process_query_capture_root),
        "expected_files": expected_process_query_capture_files,
        "actual_files": actual_process_query_capture_files,
        "unexpected_directories": unexpected_capture_directories,
        "query_owner_pids": query_owner_pids,
        "single_query_owner_pid": len(query_owner_pids) == 30
        and len(set(query_owner_pids)) == 1,
        "error": process_query_capture_set_error,
        "pass": process_query_capture_set_pass,
    }
    final_snapshot = process_root / "99__final.json"
    initial_snapshot = process_root / "00__initial.json"
    orchestration_snapshot_pass = bool(
        initial_snapshot.is_file() and json.loads(initial_snapshot.read_text(encoding="utf-8")) == []
        and final_snapshot.is_file() and json.loads(final_snapshot.read_text(encoding="utf-8")) == []
    )
    add_check(
        checks,
        "S3-ORCHESTRATION-V3-AND-GATES",
        "execution",
        orchestration_header_pass
        and orchestration_dry_pass
        and orchestration_routes_pass
        and orchestration_subprocess_pass
        and orchestration_process_query_pass
        and orchestration_snapshot_pass,
        {
            "schema_version": "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V3",
            "14_ordered_runs": True,
            "14_unique_execution_tokens": True,
            "all_tool_seals_process_and_capture_gates": True,
        },
        {
            "header_pass": orchestration_header_pass,
            "dry_run_pass": orchestration_dry_pass,
            "routes_pass": orchestration_routes_pass,
            "execution_identity_contract_pass": orchestration_execution_identity_pass,
            "route_identity_records_pass": orchestration_route_identity_pass,
            "recomputed_execution_token_count": len(
                orchestration_route_execution_tokens
            ),
            "recomputed_unique_execution_token_count": recomputed_unique_execution_token_count,
            "summary_unique_execution_token_count": orchestration.get(
                "unique_execution_token_count"
            ),
            "author_success_failure_count_contract_pass": orchestration_count_contract_pass,
            "recomputed_author_counts": {
                "route_record_success": route_record_success_count,
                "route_record_failure": route_record_failure_count,
                "exit_record_success": exit_record_success_count,
                "exit_record_failure": exit_record_failure_count,
                "validated_outcome_success": validated_outcome_success_count,
                "validated_outcome_failure": validated_outcome_failure_count,
                "summary_success": orchestration.get(
                    "author_execution_success_count"
                ),
                "summary_failure": orchestration.get(
                    "author_execution_failure_count"
                ),
            },
            "subprocess_captures_pass": orchestration_subprocess_pass,
            "process_query_records_pass": orchestration_process_query_pass,
            "process_query_capture_set": process_query_capture_set_audit,
            "initial_final_snapshots_empty": orchestration_snapshot_pass,
            "route_details": orchestration_route_details,
            "subprocess_details": subprocess_details,
            "process_query_details": process_query_details,
            "orchestration": orchestration,
        },
        orchestration_path,
    )

    repeat_pass_count = 0
    for route_index, route in enumerate(ROUTES, start=1):
        runs = per_route_runs.get(route["route_id"], {})
        first = runs.get("rep01")
        second = runs.get("rep02")
        route_pass = False
        outcome = "MISSING"
        max_abs = math.nan
        max_rel = math.nan
        details: dict[str, Any] = {}
        if first and second and first.get("outcome") == second.get("outcome") == "SUCCESS":
            outcome = "SUCCESS"
            variable_rows: list[dict[str, Any]] = []
            route_pass = bool(first.get("science_valid") and second.get("science_valid"))
            max_abs = 0.0
            max_rel = 0.0
            for name in REQUIRED_FINAL:
                first_record = first.get("scientific_records", {}).get(name)
                second_record = second.get("scientific_records", {}).get(name)
                if not first_record or not second_record:
                    variable_rows.append({"variable": name, "record_present_both": False, "pass": False})
                    route_pass = False
                    continue
                a = np.asarray(first_record["value"], dtype=np.float64)
                b = np.asarray(second_record["value"], dtype=np.float64)
                metadata_checks = {
                    "matlab_class": first_record["matlab_class"] == second_record["matlab_class"],
                    "dtype": first_record["dtype"] == second_record["dtype"],
                    "dtype_matches_matlab_class": first_record[
                        "dtype_matches_matlab_class"
                    ]
                    is True
                    and second_record["dtype_matches_matlab_class"] is True,
                    "shape": first_record["shape"] == second_record["shape"],
                    "matlab_shape": first_record["matlab_shape"]
                    == second_record["matlab_shape"],
                    "complex_flag": first_record["is_complex"] == second_record["is_complex"],
                    "empty_flag": first_record["is_empty"] == second_record["is_empty"],
                    "sparse_flag": first_record["is_sparse"]
                    == second_record["is_sparse"]
                    is False,
                    "global_flag": first_record["is_global"]
                    == second_record["is_global"]
                    is False,
                }
                if a.shape != b.shape:
                    local_abs = math.inf
                    local_rel = math.inf
                else:
                    difference = np.abs(a - b)
                    local_abs = float(np.max(difference)) if difference.size else 0.0
                    scale = np.maximum(np.maximum(np.abs(a), np.abs(b)), np.finfo(float).tiny)
                    local_rel = float(np.max(difference / scale)) if difference.size else 0.0
                thresholds = {
                    "max_abs_le_1e-12": local_abs <= 1e-12,
                    "max_rel_le_1e-12": local_rel <= 1e-12,
                }
                variable_pass = all(metadata_checks.values()) and all(thresholds.values())
                route_pass &= variable_pass
                max_abs = max(max_abs, local_abs)
                max_rel = max(max_rel, local_rel)
                variable_rows.append(
                    {"variable": name, "metadata_checks": metadata_checks, "thresholds": thresholds, "max_abs": local_abs, "max_rel": local_rel, "pass": variable_pass}
                )
            details = {"variables": variable_rows, "both_science_valid": bool(first.get("science_valid") and second.get("science_valid"))}
        elif first and second and first.get("outcome") == second.get("outcome") == "FAILURE":
            outcome = "FAILURE"
            a_status = first["status"]
            b_status = second["status"]
            a_error = first["error"]
            b_error = second["error"]
            a_stack = first.get("stack", [])
            b_stack = second.get("stack", [])
            first_location_a = (Path(a_stack[0].get("file", "")).name, a_stack[0].get("name"), int(a_stack[0].get("line", 0))) if a_stack else ("", "", 0)
            first_location_b = (Path(b_stack[0].get("file", "")).name, b_stack[0].get("name"), int(b_stack[0].get("line", 0))) if b_stack else ("", "", 0)
            comparisons = {
                "both_failure_evidence_valid": bool(first.get("failure_evidence_valid") and second.get("failure_evidence_valid")),
                "both_nonempty_stack": bool(a_stack and b_stack),
                "error_origin": a_status.get("error_origin") == b_status.get("error_origin") == "AUTHOR_CALL",
                "stage": a_status.get("failed_stage") == b_status.get("failed_stage"),
                "file": Path(a_status.get("failed_file", "")).name == Path(b_status.get("failed_file", "")).name,
                "identifier": bool(a_error.get("identifier")) and a_error.get("identifier") == b_error.get("identifier"),
                "message": normalized_error_message(str(a_error.get("message", ""))) == normalized_error_message(str(b_error.get("message", ""))),
                "first_stack_location": first_location_a == first_location_b,
            }
            route_pass = all(comparisons.values())
            details = {"comparisons": comparisons, "first_location_rep01": first_location_a, "first_location_rep02": first_location_b}
        add_check(
            checks,
            f"S3-REPEAT-{route_index:02d}",
            "repeatability",
            route_pass,
            "two science-valid successes with identical MATLAB_class/dtype/shape and both max_abs/max_rel <= 1e-12, or two evidence-valid identical author failures with nonempty stacks",
            {"outcome": outcome, "max_abs": max_abs, "max_rel": max_rel, "details": details},
            RUN_ROOT / route["route_id"],
        )
        if route_pass:
            repeat_pass_count += 1
        first_totals = first.get("totals", {}) if first else {}
        first_guyan = first_totals.get("total_increase_guyan")
        first_cb = first_totals.get("total_increase_cb")
        history_diff_guyan = first_guyan - route["history"][0] if isinstance(first_guyan, (int, float)) else math.nan
        history_diff_cb = first_cb - route["history"][1] if isinstance(first_cb, (int, float)) else math.nan
        route_results.append(
            {
                "route_id": route["route_id"], "static_boundary": route["static_boundary"],
                "execution_outcome": outcome, "repeat_status": "PASS" if route_pass else "FAIL",
                "max_abs_difference": max_abs, "max_relative_difference": max_rel,
                "embedded_historical_guyan_percent": route["history"][0], "embedded_historical_cb_percent": route["history"][1],
                "rep01_guyan_percent": first_guyan if isinstance(first_guyan, (int, float)) else "",
                "rep01_cb_percent": first_cb if isinstance(first_cb, (int, float)) else "",
                "history_difference_guyan_percent": history_diff_guyan, "history_difference_cb_percent": history_diff_cb,
                "paper_formula_4_45_status": "NOT_EVALUATED_STEP3", "table4_1_status": "HISTORICAL_NOT_ADJUDICATED",
            }
        )
        repeat_rows.append(
            {"route_id": route["route_id"], "outcome": outcome, "repeat_pass": route_pass, "max_abs_difference": max_abs, "max_relative_difference": max_rel, "details_json": json.dumps(details, ensure_ascii=False, sort_keys=True)}
        )

    boundary = publication_and_process_snapshot()
    add_check(
        checks,
        "S3-PUBLICATION-BOUNDARY",
        "publication",
        not boundary["publication_query_error"]
        and not boundary["formal_present"]
        and not boundary["failure_present"]
        and not boundary["board22_present"],
        {"query_error": "", "formal": [], "failure": [], "board22": []},
        {"query_error": boundary["publication_query_error"], "formal": boundary["formal_present"], "failure": boundary["failure_present"], "board22": boundary["board22_present"]},
        PROJECT_ROOT / "test",
    )
    add_check(
        checks,
        "S3-RESIDUAL-PROCESSES",
        "process",
        not boundary["process_query_error"] and not boundary["residual_processes"],
        {"query_error": "", "processes": []},
        {"query_error": boundary["process_query_error"], "processes": boundary["residual_processes"]},
        BOARD_ROOT,
    )
    add_check(checks, "S3-ALL-ROUTES-REPEAT", "scientific_execution", repeat_pass_count == 7, 7, repeat_pass_count, RUN_ROOT)

    failed_ids = [row["check_id"] for row in checks if row["status"] == "FAIL"]
    check_ids = [row["check_id"] for row in checks]
    summary = {
        "schema_version": "BOARD21_STEP3_INDEPENDENT_VALIDATION_V2",
        "status": "PASS" if not failed_ids and len(set(check_ids)) == len(check_ids) else "FAIL",
        "check_count": len(checks),
        "passed_count": sum(row["status"] == "PASS" for row in checks),
        "failed_count": len(failed_ids),
        "failed_check_ids": failed_ids,
        "check_ids_unique": len(set(check_ids)) == len(check_ids),
        "route_count": 7,
        "run_count": 14,
        "successful_route_count": sum(row["execution_outcome"] == "SUCCESS" for row in route_results),
        "failed_route_count": sum(row["execution_outcome"] == "FAILURE" for row in route_results),
        "repeat_pass_route_count": repeat_pass_count,
        "artifact_seal_pass_run_count": artifact_pass_count,
        "hdf5_readable_pass_run_count": hdf5_pass_count,
        "inventory_workspace_crosscheck_pass_run_count": inventory_pass_count,
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
        "protected_input_row_count": 53,
        "attempt01_archive_audit_schema_version": attempt01_archive_audit.get(
            "schema_version"
        ),
        "attempt01_archive_audit_status": attempt01_archive_audit.get("status"),
        "attempt02_archive_audit_schema_version": attempt02_archive_audit.get(
            "schema_version"
        ),
        "attempt02_archive_audit_status": attempt02_archive_audit.get("status"),
        "attempt02_archive_audit_check_count": attempt02_archive_audit.get(
            "check_count"
        ),
        "attempt02_archive_audit_failed_checks": attempt02_archive_audit.get(
            "failed_checks"
        ),
        "attempt02_archive_attempt_id": attempt02_archive_audit.get("attempt_id"),
        "attempt02_archive_actual_file_count": attempt02_archive_audit.get(
            "archive_closure", {}
        ).get("actual_file_count"),
        "attempt02_archive_metadata_sha256_actual": attempt02_archive_audit.get(
            "metadata_sha256_actual"
        ),
        "route7_formula_source_contract_status": route7_formula_source_contract.get(
            "status"
        ),
        "route7_all_vectors_negative_mutation_rejected": (
            route7_formula_mutation_rejected
        ),
        "orchestration_schema_version": orchestration.get("schema_version"),
        "formula_4_45_evaluated": False,
        "table4_1_adjudicated": False,
        "matlab_executed": True,
        "formal_success_directory_count": len(boundary["formal_present"]),
        "prepublication_failure_directory_count": len(boundary["failure_present"]),
        "board22_named_root_count": len(boundary["board22_present"]),
        "residual_target_process_count": len(boundary["residual_processes"]),
        "publication_query_error": boundary["publication_query_error"],
        "process_query_error": boundary["process_query_error"],
        "preflight_summary": preflight_summary,
        "scientific_status": "AUTHOR_HISTORICAL_ROUTES_EXECUTED_FORMULA_CORRECTNESS_PENDING_STEP4",
    }
    return checks, route_results, repeat_rows, summary


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0]) if rows else []
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_failure_record_best_effort(
    failure: dict[str, Any], validation_root_created: bool
) -> tuple[str, list[str]]:
    """Write exclusively; never touch a validation root this attempt did not create."""
    errors: list[str] = []

    def attempt(candidate: Path) -> tuple[bool, bool]:
        failure["failure_record_destination"] = str(candidate)
        failure["failure_record_write_errors_before_destination"] = list(errors)
        failure["failure_record_written"] = True
        failure["failure_record_path"] = str(candidate)
        try:
            with candidate.open("x", encoding="utf-8", newline="\n") as stream:
                stream.write(
                    json.dumps(failure, ensure_ascii=False, indent=2, sort_keys=True)
                    + "\n"
                )
            return True, False
        except FileExistsError as error:
            failure["failure_record_written"] = False
            failure["failure_record_path"] = ""
            errors.append(f"{candidate}:FileExistsError: {error}")
            return False, True
        except Exception as error:
            failure["failure_record_written"] = False
            failure["failure_record_path"] = ""
            errors.append(f"{candidate}:{type(error).__name__}: {error}")
            return False, False

    if validation_root_created:
        primary = VALIDATION_ROOT / "validation_failure.json"
        primary_written, _ = attempt(primary)
        if primary_written:
            return str(primary), errors

    fallback_root = BOARD_ROOT / "logs" / "step3_validation_failures"
    try:
        fallback_root.mkdir(parents=True, exist_ok=True)
    except Exception as error:
        errors.append(
            "fallback_directory_creation:"
            f"{type(error).__name__}: {error}"
        )
        return "", errors
    timestamp = datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%f%z")
    for sequence in range(1, 101):
        candidate = fallback_root / (
            f"validation_failure_{timestamp}_pid{os.getpid()}_{sequence:03d}.json"
        )
        written, collision = attempt(candidate)
        if written:
            return str(candidate), errors
        if not collision:
            break
    return "", errors


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--preflight", action="store_true")
    mode.add_argument("--audit-attempt01", action="store_true")
    mode.add_argument("--audit-attempt02", action="store_true")
    args = parser.parse_args()
    if args.preflight:
        result = preflight()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    if args.audit_attempt01:
        result = audit_attempt01_archive()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["pass"] else 1
    if args.audit_attempt02:
        result = audit_attempt02_archive()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if result["pass"] else 1
    validation_root_created = False
    try:
        VALIDATION_ROOT.mkdir(parents=True, exist_ok=False)
        validation_root_created = True
        checks, routes, repeats, summary = validate()
        write_csv(VALIDATION_ROOT / "checks.csv", checks)
        write_csv(VALIDATION_ROOT / "route_results.csv", routes)
        write_csv(VALIDATION_ROOT / "repeat_comparison.csv", repeats)
        with (VALIDATION_ROOT / "validation_summary.json").open(
            "x", encoding="utf-8", newline="\n"
        ) as stream:
            stream.write(
                json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True)
                + "\n"
            )
        print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
        return 0 if summary["status"] == "PASS" else 1
    except Exception as error:
        boundary = publication_and_process_snapshot()
        failure = {
            "schema_version": "BOARD21_STEP3_INDEPENDENT_VALIDATION_FAILURE_V2",
            "status": "VALIDATION_EXCEPTION",
            "failed_at": datetime.now().astimezone().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "validation_root_created_by_this_attempt": validation_root_created,
            "preexisting_validation_root_was_not_written": bool(
                not validation_root_created and VALIDATION_ROOT.exists()
            ),
            "formal_publication_boundary": {
                "formal_present": boundary["formal_present"],
                "failure_present": boundary["failure_present"],
                "board22_present": boundary["board22_present"],
                "query_error": boundary["publication_query_error"],
                "pass": not boundary["publication_query_error"]
                and not boundary["formal_present"]
                and not boundary["failure_present"]
                and not boundary["board22_present"],
            },
            "residual_process_boundary": {
                "processes": boundary["residual_processes"],
                "query_error": boundary["process_query_error"],
                "pass": not boundary["residual_processes"]
                and not boundary["process_query_error"],
            },
        }
        failure_record_path, failure_record_errors = write_failure_record_best_effort(
            failure, validation_root_created
        )
        failure["failure_record_written"] = bool(failure_record_path)
        failure["failure_record_path"] = failure_record_path
        failure["failure_record_write_errors"] = failure_record_errors
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

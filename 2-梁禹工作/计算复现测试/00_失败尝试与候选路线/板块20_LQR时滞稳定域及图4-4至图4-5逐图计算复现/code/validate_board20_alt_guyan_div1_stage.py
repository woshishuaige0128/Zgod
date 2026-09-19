from __future__ import annotations

import csv
import hashlib
import json
import re
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
INPUT_ROOT = BOARD_ROOT / "input"
INPUT_MANIFEST = INPUT_ROOT / "input_manifest.csv"

ROUTE_ID = "alt_guyan_div1_stable_full_ps3"
REPLICATE = "rep01"
RUN_RELATIVE = Path(ROUTE_ID) / "original_mlx" / REPLICATE
WORK_DIR = BOARD_ROOT / "tmp" / "step2_runs" / RUN_RELATIVE / "work"
RUN_OUTPUT_DIR = BOARD_ROOT / "outputs" / "step2_runs" / RUN_RELATIVE
RUN_LOG_DIR = BOARD_ROOT / "logs" / "step2_runs" / RUN_RELATIVE
CONFIG_PATH = RUN_OUTPUT_DIR / "metadata" / "run_config.json"
VALIDATION_PATH = RUN_OUTPUT_DIR / "metadata" / "stage_validation.json"

EXPECTED_IDS = ["B20-0028", "B20-0031", "B20-0185", "B20-0018"]
EXPECTED_WORK_FILES = {
    "New_Full.m",
    "New_Ps3.m",
    "dependencies/fcn_newmark_beta_const.m",
    "luxvjie_guyan_LQR2.mlx",
}
EXPECTED_EXISTING_INSTRUMENTS = {
    "stager": "stage_board20_step2_runs.py",
    "matlab_runner": "run_one_board20_candidate.m",
    "outer_executor": "execute_board20_step2_route.py",
}
EXPECTED_PROTECTED_HASHES = {
    "stage_board20_step2_runs.py": "918C786BD8E1A1FBFB9A9B156B30A45A90D4207EB56F1509C2D29F3F08943FD7",
    "validate_board20_step2_stage.py": "7F31B862D8614536AFC4599C718F09868F925A333D0FD3C65A1C3C73AD435C22",
    "run_one_board20_candidate.m": "76682306E224E5C02B6EFC6C3D2FD4B69048C7CBF58A9337A7378B5A823E6D27",
    "execute_board20_step2_route.py": "B5B31D2C72643CDCE24D85D4745C924BE3CFF1A47D6839EBA76FB7206420E604",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def normalize_code(text: str) -> str:
    return re.sub(r"\s+", "", text)


def mlx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        root = ElementTree.fromstring(archive.read("matlab/document.xml"))
    return "\n".join(value.strip() for value in root.itertext() if value.strip())


def main() -> int:
    if VALIDATION_PATH.exists():
        raise FileExistsError(f"验收结果已存在，拒绝覆盖：{VALIDATION_PATH}")
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(f"缺少配置：{CONFIG_PATH}")
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))

    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        manifest_rows = list(csv.DictReader(stream))
    by_id = {row["item_id"]: row for row in manifest_rows}

    checks: list[dict[str, Any]] = []

    def check(name: str, condition: bool, detail: Any) -> None:
        checks.append(
            {
                "name": name,
                "status": "PASS" if condition else "FAIL",
                "detail": detail,
            }
        )

    check(
        "CONFIG_SCHEMA_ROUTE_REPLICATE",
        config.get("schema") == "board20_original_mlx_run_config_v2"
        and config.get("route_id") == ROUTE_ID
        and config.get("replicate") == REPLICATE,
        {
            "schema": config.get("schema"),
            "route_id": config.get("route_id"),
            "replicate": config.get("replicate"),
        },
    )

    config_hash_file = Path(config["config_hash_file"])
    expected_config_hash = config_hash_file.read_text(encoding="ascii").strip().upper()
    actual_config_hash = sha256_file(CONFIG_PATH)
    check(
        "CONFIG_SEAL",
        expected_config_hash == actual_config_hash,
        {
            "expected_sha256": expected_config_hash,
            "actual_sha256": actual_config_hash,
        },
    )

    contracts = config.get("file_contracts", [])
    contract_ids = [row.get("frozen_manifest_item_id") for row in contracts]
    contract_results: list[dict[str, Any]] = []
    all_contracts_match = contract_ids == EXPECTED_IDS
    for contract in contracts:
        item_id = str(contract.get("frozen_manifest_item_id", ""))
        path = Path(str(contract.get("path", "")))
        manifest = by_id.get(item_id)
        expected = str(contract.get("expected_sha256", "")).upper()
        actual = sha256_file(path) if path.is_file() else ""
        manifest_hash = manifest["frozen_sha256"].upper() if manifest else ""
        match = (
            manifest is not None
            and manifest.get("status") == "MATCH"
            and expected == manifest_hash
            and actual == expected
        )
        all_contracts_match = all_contracts_match and match
        contract_results.append(
            {
                "item_id": item_id,
                "path": str(path),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "manifest_sha256": manifest_hash,
                "match": match,
            }
        )
    check(
        "FOUR_FROZEN_INPUT_CONTRACTS",
        all_contracts_match and len(contracts) == 4,
        contract_results,
    )

    actual_work_files = {
        str(path.relative_to(WORK_DIR)).replace("\\", "/")
        for path in WORK_DIR.rglob("*")
        if path.is_file()
    }
    check(
        "EXACT_WORK_ALLOWLIST",
        actual_work_files == EXPECTED_WORK_FILES
        and set(config.get("allowed_work_files", [])) == EXPECTED_WORK_FILES,
        {
            "expected": sorted(EXPECTED_WORK_FILES),
            "actual": sorted(actual_work_files),
            "configured": sorted(config.get("allowed_work_files", [])),
        },
    )

    stale_stab = [
        str(path.relative_to(WORK_DIR)).replace("\\", "/")
        for path in WORK_DIR.rglob("*")
        if path.is_file() and path.name.lower().startswith("stab")
    ]
    check("FRESH_WORKDIR_NO_STAB_OUTPUT", not stale_stab, stale_stab)

    reserved_keys = [
        "status_json",
        "diary_file",
        "workspace_success",
        "workspace_failure",
        "scientific_arrays",
        "raw_stab",
        "profile_info",
        "process_exit_json",
        "command_txt",
        "shell_log",
    ]
    existing_reserved = [
        {"key": key, "path": str(config[key])}
        for key in reserved_keys
        if Path(str(config[key])).exists()
    ]
    check("NO_EXECUTION_OUTPUT_EXISTS", not existing_reserved, existing_reserved)

    instrument_results: list[dict[str, Any]] = []
    instruments_match = True
    instrumentation = config.get("instrumentation", {})
    for name, expected_name in EXPECTED_EXISTING_INSTRUMENTS.items():
        item = instrumentation.get(name, {})
        path = Path(str(item.get("path", "")))
        expected = str(item.get("sha256", "")).upper()
        actual = sha256_file(path) if path.is_file() else ""
        match = path.name == expected_name and actual == expected
        instruments_match = instruments_match and match
        instrument_results.append(
            {
                "name": name,
                "path": str(path),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": match,
            }
        )
    check("THREE_EXISTING_CODE_SEALS", instruments_match, instrument_results)

    protected_results: list[dict[str, Any]] = []
    protected_match = True
    for filename, expected in EXPECTED_PROTECTED_HASHES.items():
        path = BOARD_ROOT / "code" / filename
        actual = sha256_file(path) if path.is_file() else ""
        match = actual == expected
        protected_match = protected_match and match
        protected_results.append(
            {
                "filename": filename,
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": match,
            }
        )
    check("FOUR_EXISTING_SEALED_FILES_UNCHANGED", protected_match, protected_results)

    provenance = config.get("staging_provenance", {})
    actual_stager = provenance.get("actual_stager", {})
    actual_stager_path = Path(str(actual_stager.get("path", "")))
    actual_stager_expected = str(actual_stager.get("sha256", "")).upper()
    actual_stager_hash = (
        sha256_file(actual_stager_path) if actual_stager_path.is_file() else ""
    )
    check(
        "INDEPENDENT_STAGER_PROVENANCE",
        provenance.get("mode") == "INDEPENDENT_ALT_ROUTE_STAGER"
        and provenance.get("matlab_launched_by_stager") is False
        and actual_stager_path.name
        == "stage_board20_alt_guyan_div1_stable_full_ps3.py"
        and actual_stager_hash == actual_stager_expected,
        {
            "path": str(actual_stager_path),
            "expected_sha256": actual_stager_expected,
            "actual_sha256": actual_stager_hash,
            "matlab_launched_by_stager": provenance.get(
                "matlab_launched_by_stager"
            ),
        },
    )

    ps3_text = normalize_code((WORK_DIR / "New_Ps3.m").read_text(encoding="utf-8"))
    candidate_text = normalize_code(mlx_text(WORK_DIR / "luxvjie_guyan_LQR2.mlx"))
    ps3_is_9d = (
        "locate2=[1,2,3,6,7,8,11,12,13];" in ps3_text
        and "MPrt=diag([M4M2M2M4M2M2M4M2M2]);" in ps3_text
    )
    candidate_uses_first_6d = (
        "index3=[1,4];" in candidate_text
        and "index4=[2,3,5,6];" in candidate_text
        and "Kmn=KPrt(index3,index3);" in candidate_text
        and "Ksn=KPrt(index4,index4);" in candidate_text
    )
    conflicts = config.get("semantic_conflicts", [])
    conflict_disclosed = any(
        row.get("id") == "PS3_9X9_TRUNCATED_TO_FIRST_6_DOF"
        and row.get("status") == "DISCLOSED_NOT_RESOLVED"
        for row in conflicts
        if isinstance(row, dict)
    )
    check(
        "PS3_9X9_VS_LQR2_FIRST6_CONFLICT_DISCLOSED",
        ps3_is_9d and candidate_uses_first_6d and conflict_disclosed,
        {
            "new_ps3_native_9d_static_evidence": ps3_is_9d,
            "candidate_first_6d_static_evidence": candidate_uses_first_6d,
            "config_disclosure": conflict_disclosed,
        },
    )

    route_contract_ok = (
        config.get("upstream_identity_status")
        == "PRECOMMITTED_SAME_DIRECTORY_CANDIDATE_WITH_DIMENSION_SEMANTIC_CONFLICT"
        and config.get("source_contains_dlqr") is False
        and config.get("expected_scan_point_count") == 441
        and config.get("expected_stab_shape") == [21, 21]
        and config.get("expected_written_regions") == [[1, 21, 1, 21]]
        and config.get("source_save_call_count") == 0
        and config.get("author_save_targets") == []
        and len(config.get("upstream_files", [])) == 2
        and len(config.get("dependency_directories", [])) == 1
    )
    check(
        "RUNNER_EXECUTOR_COMPATIBLE_ROUTE_CONTRACT",
        route_contract_ok,
        {
            "upstream_identity_status": config.get("upstream_identity_status"),
            "expected_scan_point_count": config.get("expected_scan_point_count"),
            "expected_stab_shape": config.get("expected_stab_shape"),
            "expected_written_regions": config.get("expected_written_regions"),
            "upstream_count": len(config.get("upstream_files", [])),
            "dependency_directory_count": len(
                config.get("dependency_directories", [])
            ),
        },
    )

    failed = [row for row in checks if row["status"] != "PASS"]
    result = {
        "schema": "board20_alt_guyan_div1_stage_validation_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "route_id": ROUTE_ID,
        "replicate": REPLICATE,
        "overall_status": "PASS" if not failed else "FAIL",
        "matlab_launched_by_validation": False,
        "check_count": len(checks),
        "pass_count": len(checks) - len(failed),
        "fail_count": len(failed),
        "checks": checks,
    }
    VALIDATION_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())

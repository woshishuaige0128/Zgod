from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import traceback
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
AUTHOR_ROOT = BOARD_ROOT / "input" / "author_energy"
INPUT_MANIFEST = BOARD_ROOT / "input" / "input_manifest.csv"
INPUT_FREEZE_SUMMARY = BOARD_ROOT / "input" / "input_freeze_summary.json"
TMP_ROOT = BOARD_ROOT / "tmp" / "step3_runs"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step3_runs"
LOG_ROOT = BOARD_ROOT / "logs" / "step3_runs"
STAGE_ROOT = BOARD_ROOT / "outputs" / "step3_stage"
INPUT_MANIFEST_SHA256 = "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
INPUT_FREEZE_SUMMARY_SHA256 = "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"
EXPECTED_CATEGORY_COUNTS = {
    "author_energy_tree": 36,
    "central_baseline": 3,
    "manuscript": 1,
    "prior_audit": 2,
    "stability_evidence": 2,
    "theory": 1,
    "upstream_candidate": 1,
    "upstream_passport": 7,
}

REPLICATES = ("rep01", "rep02")
INSTRUMENT_FILES = (
    "stage_board21_step3_runs.py",
    "run_one_board21_energy_route.m",
    "execute_board21_step3_route.py",
    "run_board21_step3_all.py",
    "validate_board21_step3_runs.py",
)

ROUTES: tuple[dict[str, Any], ...] = (
    {
        "route_id": "reference15_pd19_energy",
        "route_label_cn": "旧15自由度参考体系：PD参数族1.9→energy_zonghe",
        "division_identity": "旧15自由度水平主坐标参考体系；不绑定表4-1两类整体划分",
        "parameter_family": "rho=785e3.*1.9",
        "upstream_name": "PDmonicanshu.m",
        "upstream_sha256": "A78F2608FEE0FA0775DEB0D7F778A51327C81BF88F25AA6D8E13D4202EB7B883",
        "candidate_name": "energy_zonghe.mlx",
        "candidate_sha256": "BCEDEF1887ABEE046A3018EB746B2088B0D63F9ACC917B9B4A78D97DEC84159D",
        "expected_energy_lengths": [15, 3, 6],
        "embedded_historical_percent": [6.5613, 6.5535],
        "static_boundary": "REFERENCE_NOT_TABLE4_1_DIVISION",
    },
    {
        "route_id": "division1_pd19_copy",
        "route_label_cn": "第一类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "upstream_name": "PDmonicanshu2.m",
        "upstream_sha256": "ADF1C89A4C9443168DCBBBBC5F9AAA1C68CE275C4F49E449C1CBABDEF86FF110",
        "candidate_name": "Copy_of_energy_zonghe2.mlx",
        "candidate_sha256": "80C4B3FE2A860552054D8FCEABA40365C5EE646BBB2EB21C9AF68E81AFE4715D",
        "expected_energy_lengths": [6, 2, 5],
        "embedded_historical_percent": [9.6488, 9.3150],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division1_tp17_energy",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→energy_zonghe2",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream_name": "monicanshu_2_suoju.mlx",
        "upstream_sha256": "1F885E0971033EBCB8632110EC5A47DA507126C718A80176FF3347B2ED6A08C5",
        "candidate_name": "energy_zonghe2.mlx",
        "candidate_sha256": "A84F903A5163AC0792FEA6BD0222003B3D2E1ED12B4D1B2CD6EABF325CA5CAAD",
        "expected_energy_lengths": [6, 2, 5],
        "embedded_historical_percent": [9.7221, 9.3097],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division1_tp17_copy2_formula_invalid",
        "route_label_cn": "第一类局部物理子结构：TP参数族1.7→Copy_2错误公式",
        "division_identity": "第一类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream_name": "monicanshu_2_suoju.mlx",
        "upstream_sha256": "1F885E0971033EBCB8632110EC5A47DA507126C718A80176FF3347B2ED6A08C5",
        "candidate_name": "Copy_2_of_energy_zonghe2.mlx",
        "candidate_sha256": "8EBC3ACBD47B1D112395D4DCD951FE018F71A857E604187B443A2BFD572ADA66",
        "expected_energy_lengths": [6, 2, 5],
        "embedded_historical_percent": [-33.7706, -41.7441],
        "static_boundary": "FORMULA_INVALID_NORMALIZATION_AND_DENOMINATOR",
    },
    {
        "route_id": "division2_pd19_copy",
        "route_label_cn": "第二类局部物理子结构：PD参数族1.9→Copy_of_energy_zonghe3",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.9",
        "upstream_name": "PDmonicanshu3.m",
        "upstream_sha256": "C35C7BFB19C3A5E98626FF1A07C14481F53973947E2C382EB81BD9642D9CF40E",
        "candidate_name": "Copy_of_energy_zonghe3.mlx",
        "candidate_sha256": "C067893CE26DA706774A886523F9000A2A0779268BB12A93A21E0EF0034296AC",
        "expected_energy_lengths": [9, 2, 5],
        "embedded_historical_percent": [59.8619, 15.5000],
        "static_boundary": "STATIC_DIMENSION_AND_COORDINATE_PASS",
    },
    {
        "route_id": "division2_tp17_energy_coordinate_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→energy_zonghe3（坐标顺序冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream_name": "monicanshu_3_suoju.mlx",
        "upstream_sha256": "D7AC9307B1A07D7AA442FDF37E7882BAE3EC519C021A5A317FFE9D9374E70D01",
        "candidate_name": "energy_zonghe3.mlx",
        "candidate_sha256": "1F3B84A542AF40563F05C23402C2355345100D38A94D8EF130D5545A33D36614",
        "expected_energy_lengths": [9, 2, 5],
        "embedded_historical_percent": [59.8619, 16.9607],
        "static_boundary": "COORDINATE_ORDER_CONFLICT",
    },
    {
        "route_id": "division2_tp17_copy2_coordinate_formula_conflict",
        "route_label_cn": "第二类局部物理子结构：TP参数族1.7→Copy_2（坐标与公式冲突）",
        "division_identity": "第二类划分局部物理子结构",
        "parameter_family": "rho=785e3.*1.7",
        "upstream_name": "monicanshu_3_suoju.mlx",
        "upstream_sha256": "D7AC9307B1A07D7AA442FDF37E7882BAE3EC519C021A5A317FFE9D9374E70D01",
        "candidate_name": "Copy_2_of_energy_zonghe3.mlx",
        "candidate_sha256": "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D",
        "expected_energy_lengths": [9, 2, 5],
        "embedded_historical_percent": [39.2658, 20.2060],
        "static_boundary": "COORDINATE_ORDER_AND_FORMULA_CONFLICT",
    },
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def write_csv_new(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def manifest_row(name: str) -> dict[str, str]:
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = [
            row
            for row in csv.DictReader(stream)
            if row.get("category") == "author_energy_tree"
            and Path(row.get("frozen_relative_path", "")).name == name
        ]
    if len(rows) != 1:
        raise RuntimeError(f"expected one frozen manifest row for {name}, got {len(rows)}")
    return rows[0]


def verify_full_input_freeze() -> dict[str, Any]:
    if sha256_file(INPUT_MANIFEST) != INPUT_MANIFEST_SHA256:
        raise RuntimeError("step1 input manifest hash mismatch")
    if sha256_file(INPUT_FREEZE_SUMMARY) != INPUT_FREEZE_SUMMARY_SHA256:
        raise RuntimeError("step1 input freeze summary hash mismatch")
    summary = json.loads(INPUT_FREEZE_SUMMARY.read_text(encoding="utf-8"))
    if (
        summary.get("schema_version") != "BOARD21_INPUT_FREEZE_V1"
        or summary.get("status") != "PASS"
        or summary.get("input_count") != 53
        or summary.get("source_frozen_match_count") != 53
        or summary.get("category_counts") != EXPECTED_CATEGORY_COUNTS
    ):
        raise RuntimeError(f"step1 input freeze summary contract mismatch: {summary}")
    with INPUT_MANIFEST.open("r", encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    category_counts = Counter(row.get("category", "") for row in rows)
    item_ids = [row.get("item_id", "") for row in rows]
    if (
        len(rows) != 53
        or len(set(item_ids)) != 53
        or dict(category_counts) != EXPECTED_CATEGORY_COUNTS
    ):
        raise RuntimeError("step1 input manifest cardinality/category mismatch")
    input_root = (BOARD_ROOT / "input").resolve()
    for row in rows:
        source = Path(row["source_absolute_path"])
        frozen = (input_root / row["frozen_relative_path"]).resolve()
        try:
            frozen.relative_to(input_root)
        except ValueError as error:
            raise RuntimeError(f"frozen path escapes input root: {frozen}") from error
        expected_hash = row["source_sha256"]
        expected_size = int(row["source_size_bytes"])
        if (
            not source.is_absolute()
            or not source.is_file()
            or not frozen.is_file()
            or row.get("status") != "MATCH"
            or row.get("live_change_policy") != "immutable"
            or row.get("frozen_sha256") != expected_hash
            or int(row["frozen_size_bytes"]) != expected_size
            or source.stat().st_size != expected_size
            or frozen.stat().st_size != expected_size
            or sha256_file(source) != expected_hash
            or sha256_file(frozen) != expected_hash
        ):
            raise RuntimeError(f"protected input mismatch: {row.get('item_id')}")
    return {
        "protected_input_count": len(rows),
        "category_counts": dict(category_counts),
        "input_manifest_sha256": INPUT_MANIFEST_SHA256,
        "input_freeze_summary_sha256": INPUT_FREEZE_SUMMARY_SHA256,
    }


def source_contract(route: dict[str, Any], key: str) -> tuple[Path, str, dict[str, str]]:
    name = str(route[f"{key}_name"])
    expected = str(route[f"{key}_sha256"])
    path = AUTHOR_ROOT / name
    if not path.is_file():
        raise FileNotFoundError(f"missing frozen {key}: {path}")
    actual = sha256_file(path)
    if actual != expected:
        raise RuntimeError(
            f"frozen {key} hash mismatch for {name}: expected={expected}, actual={actual}"
        )
    row = manifest_row(name)
    if (
        row.get("frozen_sha256") != expected
        or row.get("source_sha256") != expected
        or row.get("status") != "MATCH"
    ):
        raise RuntimeError(f"step1 manifest contract mismatch for {name}")
    original = Path(row["source_absolute_path"])
    if not original.is_file() or sha256_file(original) != expected:
        raise RuntimeError(f"author original hash mismatch for {name}: {original}")
    return path, actual, row


def preflight() -> dict[str, Any]:
    full_input_summary = verify_full_input_freeze()
    if len(ROUTES) != 7 or len({str(route["route_id"]) for route in ROUTES}) != 7:
        raise RuntimeError("route contract must contain exactly seven unique routes")
    source_rows: list[dict[str, str]] = []
    for route in ROUTES:
        for key in ("upstream", "candidate"):
            path, actual, row = source_contract(route, key)
            source_rows.append(
                {
                    "route_id": str(route["route_id"]),
                    "kind": key,
                    "name": path.name,
                    "sha256": actual,
                    "author_original_path": row["source_absolute_path"],
                }
            )
        lengths = list(route["expected_energy_lengths"])
        history = list(route["embedded_historical_percent"])
        if len(lengths) != 3 or any(int(value) <= 0 for value in lengths):
            raise RuntimeError(f"invalid energy lengths: {route['route_id']}")
        if len(history) != 2:
            raise RuntimeError(f"invalid historical pair: {route['route_id']}")

    instrument_hashes: dict[str, str] = {}
    for name in INSTRUMENT_FILES:
        path = SCRIPT.parent / name
        if not path.is_file():
            raise FileNotFoundError(f"missing instrument: {path}")
        instrument_hashes[name] = sha256_file(path)

    targets = [STAGE_ROOT]
    for route in ROUTES:
        for replicate in REPLICATES:
            relative = Path(str(route["route_id"])) / replicate
            targets.extend(
                (TMP_ROOT / relative, OUTPUT_ROOT / relative, LOG_ROOT / relative)
            )
    existing = [str(path) for path in targets if path.exists()]
    if existing:
        raise FileExistsError(
            "step3 refuses to overwrite existing targets: " + " | ".join(existing)
        )
    return {
        "route_count": len(ROUTES),
        "replicate_count": len(REPLICATES),
        "run_count": len(ROUTES) * len(REPLICATES),
        "source_reference_count": len(source_rows),
        "unique_source_count": len({(row["name"], row["sha256"]) for row in source_rows}),
        "instrument_sha256": instrument_hashes,
        **full_input_summary,
    }


def _stage_after_root(preflight_summary: dict[str, Any]) -> dict[str, Any]:
    manifest_rows: list[dict[str, Any]] = []
    config_rows: list[dict[str, Any]] = []
    instrument_hashes = dict(preflight_summary["instrument_sha256"])
    created_at = datetime.now().astimezone().isoformat()

    for route in ROUTES:
        for replicate in REPLICATES:
            relative = Path(str(route["route_id"])) / replicate
            work_dir = TMP_ROOT / relative / "work"
            output_dir = OUTPUT_ROOT / relative
            metadata_dir = output_dir / "metadata"
            workspace_dir = output_dir / "workspace"
            scientific_dir = output_dir / "scientific"
            log_dir = LOG_ROOT / relative
            for path in (work_dir, metadata_dir, workspace_dir, scientific_dir, log_dir):
                path.mkdir(parents=True, exist_ok=False)

            staged_paths: dict[str, Path] = {}
            input_contracts: list[dict[str, Any]] = []
            for order, key in enumerate(("upstream", "candidate"), start=1):
                source, source_hash, frozen_row = source_contract(route, key)
                destination = work_dir / source.name
                shutil.copy2(source, destination)
                copied_hash = sha256_file(destination)
                if copied_hash != source_hash:
                    raise RuntimeError(f"copy hash mismatch: {destination}")
                staged_paths[key] = destination
                contract = {
                    "kind": key,
                    "order": order,
                    "name": source.name,
                    "author_original_path": str(
                        Path(frozen_row["source_absolute_path"]).resolve()
                    ),
                    "frozen_path": str(source.resolve()),
                    "staged_path": str(destination.resolve()),
                    "expected_sha256": source_hash,
                    "copied_sha256": copied_hash,
                    "size_bytes": destination.stat().st_size,
                }
                input_contracts.append(contract)
                manifest_rows.append(
                    {
                        "route_id": route["route_id"],
                        "replicate": replicate,
                        **contract,
                    }
                )

            config_path = metadata_dir / "run_config.json"
            config_hash_path = metadata_dir / "run_config.sha256"
            instrument_contracts = [
                {
                    "name": name,
                    "path": str((SCRIPT.parent / name).resolve()),
                    "expected_sha256": instrument_hashes[name],
                }
                for name in INSTRUMENT_FILES
            ]
            config = {
                "schema_version": "BOARD21_STEP3_ROUTE_CONFIG_V1",
                "created_at": created_at,
                "route_id": route["route_id"],
                "route_label_cn": route["route_label_cn"],
                "replicate": replicate,
                "division_identity": route["division_identity"],
                "parameter_family": route["parameter_family"],
                "static_boundary": route["static_boundary"],
                "expected_energy_lengths": route["expected_energy_lengths"],
                "embedded_historical_percent": route["embedded_historical_percent"],
                "execution_status": "STAGED_NOT_RUN",
                "matlab_executable": "D:\\Downlad\\Matlab\\bin\\matlab.exe",
                "work_dir": str(work_dir.resolve()),
                "output_dir": str(output_dir.resolve()),
                "log_dir": str(log_dir.resolve()),
                "upstream_file": str(staged_paths["upstream"].resolve()),
                "candidate_mlx": str(staged_paths["candidate"].resolve()),
                "input_contracts": input_contracts,
                "instrument_sha256": instrument_hashes,
                "instrument_contracts": instrument_contracts,
                "allowed_work_files": [
                    staged_paths["upstream"].name,
                    staged_paths["candidate"].name,
                ],
                "status_json": str((metadata_dir / "run_status.json").resolve()),
                "config_hash_file": str(config_hash_path.resolve()),
                "variable_inventory_json": str(
                    (metadata_dir / "variable_inventory.json").resolve()
                ),
                "workspace_after_upstream": str(
                    (workspace_dir / "workspace_after_upstream.mat").resolve()
                ),
                "workspace_success": str(
                    (workspace_dir / "workspace_complete.mat").resolve()
                ),
                "workspace_failure": str(
                    (workspace_dir / "workspace_failure.mat").resolve()
                ),
                "scientific_mat": str(
                    (scientific_dir / "historical_energy_outputs.mat").resolve()
                ),
                "diary_file": str((log_dir / "matlab_diary.log").resolve()),
                "error_report": str((log_dir / "error_report.txt").resolve()),
                "matlab_command_txt": str(
                    (log_dir / "matlab_command.txt").resolve()
                ),
                "shell_log": str((log_dir / "shell_stdout_stderr.log").resolve()),
                "matlab_stdout_log": str(
                    (log_dir / "matlab_stdout.log").resolve()
                ),
                "matlab_stderr_log": str(
                    (log_dir / "matlab_stderr.log").resolve()
                ),
                "process_exit_json": str(
                    (metadata_dir / "process_exit.json").resolve()
                ),
            }
            write_json_new(config_path, config)
            config_hash = sha256_file(config_path)
            write_text_new(config_hash_path, config_hash + "\n")
            config_rows.append(
                {
                    "route_id": route["route_id"],
                    "route_label_cn": route["route_label_cn"],
                    "replicate": replicate,
                    "config_path": str(config_path.resolve()),
                    "config_sha256": config_hash,
                    "static_boundary": route["static_boundary"],
                    "execution_status": "STAGED_NOT_RUN",
                }
            )

    write_csv_new(
        STAGE_ROOT / "staged_input_manifest.csv",
        manifest_rows,
        [
            "route_id",
            "replicate",
            "kind",
            "order",
            "name",
            "author_original_path",
            "frozen_path",
            "staged_path",
            "expected_sha256",
            "copied_sha256",
            "size_bytes",
        ],
    )
    write_csv_new(
        STAGE_ROOT / "run_configs.csv",
        config_rows,
        [
            "route_id",
            "route_label_cn",
            "replicate",
            "config_path",
            "config_sha256",
            "static_boundary",
            "execution_status",
        ],
    )
    summary = {
        "schema_version": "BOARD21_STEP3_STAGE_SUMMARY_V1",
        "status": "STAGED_NOT_RUN",
        "matlab_executed": False,
        "route_count": len(ROUTES),
        "replicate_count": len(REPLICATES),
        "run_count": len(config_rows),
        "staged_input_row_count": len(manifest_rows),
        "unique_source_count": preflight_summary["unique_source_count"],
        "protected_input_count": preflight_summary["protected_input_count"],
        "input_manifest_sha256": preflight_summary["input_manifest_sha256"],
        "input_freeze_summary_sha256": preflight_summary[
            "input_freeze_summary_sha256"
        ],
        "instrument_sha256": instrument_hashes,
        "formal_success_directory_created": False,
        "board22_started": False,
    }
    write_json_new(STAGE_ROOT / "stage_summary.json", summary)
    return summary


def stage() -> dict[str, Any]:
    preflight_summary = preflight()
    STAGE_ROOT.mkdir(parents=True, exist_ok=False)
    try:
        return _stage_after_root(preflight_summary)
    except Exception as error:
        intended_targets = [STAGE_ROOT]
        for route in ROUTES:
            for replicate in REPLICATES:
                relative = Path(str(route["route_id"])) / replicate
                intended_targets.extend(
                    (TMP_ROOT / relative, OUTPUT_ROOT / relative, LOG_ROOT / relative)
                )
        partial_artifacts: list[dict[str, Any]] = []
        partial_manifest_errors: list[str] = []
        seen_files: set[Path] = set()
        for target in intended_targets:
            candidates = [target] if target.is_file() else (
                sorted(path for path in target.rglob("*") if path.is_file())
                if target.is_dir()
                else []
            )
            for path in candidates:
                resolved = path.resolve()
                if resolved in seen_files:
                    continue
                seen_files.add(resolved)
                try:
                    partial_artifacts.append(
                        {
                            "path": str(resolved),
                            "size_bytes": path.stat().st_size,
                            "sha256": sha256_file(path),
                        }
                    )
                except Exception as manifest_error:
                    partial_manifest_errors.append(
                        f"{resolved}: {type(manifest_error).__name__}: "
                        f"{manifest_error}"
                    )
        failure = {
            "schema_version": "BOARD21_STEP3_STAGE_FAILURE_V1",
            "status": "STAGE_FAILED_PARTIAL_OUTPUTS_RECORDED",
            "matlab_executed": False,
            "failed_at": datetime.now().astimezone().isoformat(),
            "error_type": type(error).__name__,
            "error_message": str(error),
            "traceback": traceback.format_exc(),
            "preflight_summary": preflight_summary,
            "existing_intended_targets": [
                str(path.resolve()) for path in intended_targets if path.exists()
            ],
            "created_config_count": len(
                list(OUTPUT_ROOT.glob("*/*/metadata/run_config.json"))
            )
            if OUTPUT_ROOT.exists()
            else 0,
            "partial_artifact_count": len(partial_artifacts),
            "partial_artifact_manifest": partial_artifacts,
            "partial_manifest_complete": not partial_manifest_errors,
            "partial_manifest_errors": partial_manifest_errors,
            "formal_success_directory_created": False,
            "board22_started": False,
        }
        failure_path = STAGE_ROOT / "stage_failure.json"
        try:
            if not failure_path.exists():
                write_json_new(failure_path, failure)
        except Exception as failure_write_error:
            print(
                "BOARD21_STEP3_STAGE_FAILURE_RECORD_WRITE_FAIL: "
                f"{type(failure_write_error).__name__}: {failure_write_error}",
                file=sys.stderr,
            )
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只做来源、哈希、工具和目标空置预检，不创建任何目录。",
    )
    args = parser.parse_args()
    result = preflight() if args.dry_run else stage()
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"BOARD21_STEP3_STAGE_FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise

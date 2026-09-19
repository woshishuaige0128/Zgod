from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
CODE_ROOT = SCRIPT.parent
BOARD_ROOT = CODE_ROOT.parent
ATTEMPTS_ROOT = BOARD_ROOT / "attempts"
ATTEMPT_ID = "step3_attempt02_20260826_validator_sum_scope_contract_failure"
ATTEMPT_DIRNAME = "a02"
BUILDING_DIRNAME = ".b02"
ATTEMPT_ROOT = ATTEMPTS_ROOT / ATTEMPT_DIRNAME
BUILDING_ROOT = ATTEMPTS_ROOT / BUILDING_DIRNAME
SAFE_WINDOWS_PATH_LENGTH = 240

SOURCE_MOVES = (
    ("tmp_step3_runs", BOARD_ROOT / "tmp" / "step3_runs", Path("tmp/step3_runs")),
    (
        "outputs_step3_stage",
        BOARD_ROOT / "outputs" / "step3_stage",
        Path("outputs/step3_stage"),
    ),
    (
        "outputs_step3_runs",
        BOARD_ROOT / "outputs" / "step3_runs",
        Path("outputs/step3_runs"),
    ),
    (
        "logs_step3_runs",
        BOARD_ROOT / "logs" / "step3_runs",
        Path("logs/step3_runs"),
    ),
    (
        "outputs_step3_orchestration",
        BOARD_ROOT / "outputs" / "step3_orchestration",
        Path("outputs/step3_orchestration"),
    ),
    (
        "outputs_step3_validation",
        BOARD_ROOT / "outputs" / "step3_validation",
        Path("outputs/step3_validation"),
    ),
)

EXPECTED_ROOT_COUNTS = {
    "tmp_step3_runs": (28, 1_075_314),
    "outputs_step3_stage": (3, 28_529),
    "outputs_step3_runs": (112, 6_727_585),
    "logs_step3_runs": (70, 115_522),
    "outputs_step3_orchestration": (123, 505_908),
    "outputs_step3_validation": (4, 5_564_634),
}
EXPECTED_ARTIFACT_COUNT = 340
EXPECTED_ARTIFACT_BYTES = 14_017_492

EXPECTED_PINNED_HASHES = {
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

EXPECTED_TOOL_HASHES = {
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

EXPECTED_FAILED_CHECK_IDS = {
    "S3-SCIENTIFIC-FORMULA-13",
    "S3-SCIENTIFIC-FORMULA-14",
    "S3-REPEAT-07",
    "S3-ALL-ROUTES-REPEAT",
}
ROUTE7_ID = "division2_tp17_copy2_coordinate_formula_conflict"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root must be an object: {path}")
    return value


def load_csv(path: Path) -> list[dict[str, str]]:
    csv.field_size_limit(2**31 - 1)
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def write_csv_new(
    path: Path, rows: list[dict[str, Any]], fieldnames: list[str]
) -> None:
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def assert_descendant(path: Path, parent: Path, label: str) -> Path:
    resolved_parent = parent.resolve(strict=True)
    resolved = path.resolve(strict=False)
    resolved.relative_to(resolved_parent)
    if resolved == resolved_parent:
        raise RuntimeError(f"{label} may not equal parent: {resolved}")
    return resolved


def is_link_like(path: Path) -> bool:
    return path.is_symlink() or path.is_junction()


def scan_tree(logical_root: str, root: Path) -> list[dict[str, Any]]:
    if not root.is_dir() or is_link_like(root):
        raise FileNotFoundError(f"ordinary directory required: {root}")
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if is_link_like(path):
            raise RuntimeError(f"symbolic link or junction is forbidden: {path}")
        if path.is_file():
            rows.append(
                {
                    "logical_root": logical_root,
                    "relative_path": path.relative_to(root).as_posix(),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return rows


def describe_manifest_difference(
    before: list[dict[str, Any]], after: list[dict[str, Any]]
) -> dict[str, Any]:
    def key(row: dict[str, Any]) -> tuple[str, str]:
        return str(row["logical_root"]), str(row["relative_path"])

    before_map = {key(row): row for row in before}
    after_map = {key(row): row for row in after}
    missing = sorted(set(before_map) - set(after_map))
    extra = sorted(set(after_map) - set(before_map))
    changed = sorted(
        item
        for item in set(before_map) & set(after_map)
        if before_map[item] != after_map[item]
    )
    first_positional_difference: dict[str, Any] | None = None
    for index, (before_row, after_row) in enumerate(zip(before, after, strict=False)):
        if before_row != after_row:
            first_positional_difference = {
                "index": index,
                "before": before_row,
                "after": after_row,
            }
            break
    return {
        "before_count": len(before),
        "after_count": len(after),
        "order_only": not missing and not extra and not changed,
        "missing": [list(item) for item in missing[:10]],
        "extra": [list(item) for item in extra[:10]],
        "changed": [
            {
                "key": list(item),
                "before": before_map[item],
                "after": after_map[item],
            }
            for item in changed[:10]
        ],
        "first_positional_difference": first_positional_difference,
    }


def projected_path_budget(
    rows: list[dict[str, Any]], archive_root: Path, label: str
) -> dict[str, Any]:
    destination_by_root = {
        logical_root: relative_destination
        for logical_root, _, relative_destination in SOURCE_MOVES
    }
    projected: list[tuple[str, int]] = []
    for row in rows:
        logical_root = str(row["logical_root"])
        relative_destination = destination_by_root[logical_root]
        target = (
            archive_root
            / relative_destination
            / Path(str(row["relative_path"]))
        ).resolve(strict=False)
        projected.append((str(target), len(str(target))))
    auxiliary = [
        *(Path("tools_snapshot") / name for name in EXPECTED_TOOL_HASHES),
        Path("attempt_file_manifest.csv"),
        Path("tool_snapshot_manifest.csv"),
        Path("attempt_summary.json"),
    ]
    for relative in auxiliary:
        target = (archive_root / relative).resolve(strict=False)
        projected.append((str(target), len(str(target))))
    over_limit = [item for item in projected if item[1] > SAFE_WINDOWS_PATH_LENGTH]
    maximum = max(projected, key=lambda item: item[1])
    if over_limit:
        raise RuntimeError(
            f"{label} projected path exceeds {SAFE_WINDOWS_PATH_LENGTH}: "
            + json.dumps(
                {
                    "maximum": {"path": maximum[0], "length": maximum[1]},
                    "over_limit_count": len(over_limit),
                    "first_over_limit": {
                        "path": over_limit[0][0],
                        "length": over_limit[0][1],
                    },
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return {
        "label": label,
        "limit": SAFE_WINDOWS_PATH_LENGTH,
        "projected_path_count": len(projected),
        "maximum_path": maximum[0],
        "maximum_length": maximum[1],
        "over_limit_count": 0,
    }


def query_target_processes() -> dict[str, Any]:
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding=[Console]::OutputEncoding; "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw|pdftoppm)\\.exe$'} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        cwd=BOARD_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=30,
    )
    if completed.returncode != 0 or completed.stderr:
        raise RuntimeError(
            "process query failed: "
            + completed.stderr.decode("utf-8", errors="replace")
        )
    text = completed.stdout.decode("utf-8-sig").strip()
    raw: Any = [] if not text else json.loads(text)
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list) or not all(isinstance(item, dict) for item in raw):
        raise TypeError("process query did not return an object array")
    board_token = str(BOARD_ROOT).casefold()
    targets = []
    for item in raw:
        pid = int(item.get("ProcessId") or -1)
        name = str(item.get("Name") or "")
        command_line = str(item.get("CommandLine") or "")
        if pid == os.getpid():
            continue
        if name.casefold() == "matlab.exe" or board_token in command_line.casefold():
            targets.append(item)
    return {
        "returncode": completed.returncode,
        "stdout_size_bytes": len(completed.stdout),
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest().upper(),
        "stderr_size_bytes": len(completed.stderr),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest().upper(),
        "target_processes": targets,
    }


def exact_float(value: Any, expected: float, label: str) -> None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise TypeError(f"{label} must be a numeric scalar")
    if not math.isfinite(float(value)) or float(value) != expected:
        raise ValueError(f"{label} mismatch: {value!r} != {expected!r}")


def verify_semantics() -> dict[str, Any]:
    orchestration_path = BOARD_ROOT / "outputs/step3_orchestration/run_all_summary.json"
    validation_root = BOARD_ROOT / "outputs/step3_validation"
    orchestration = load_json(orchestration_path)
    validation = load_json(validation_root / "validation_summary.json")
    checks = load_csv(validation_root / "checks.csv")
    repeats = load_csv(validation_root / "repeat_comparison.csv")
    routes = load_csv(validation_root / "route_results.csv")

    records = orchestration.get("route_process_records")
    tokens = [row.get("execution_token") for row in records] if isinstance(records, list) else []
    orchestration_checks = {
        "schema_v3": orchestration.get("schema_version")
        == "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V3",
        "status_pass": orchestration.get("status") == "PASS",
        "fourteen_runs": orchestration.get("expected_run_count") == 14
        and orchestration.get("executed_run_count") == 14
        and len(records) == 14,
        "fourteen_author_successes": orchestration.get(
            "author_execution_success_count"
        )
        == 14
        and orchestration.get("author_execution_failure_count") == 0,
        "no_infrastructure_failure": orchestration.get("infrastructure_failure")
        is False,
        "no_unstarted": orchestration.get("unstarted_runs") == [],
        "all_contracts": all(
            orchestration.get(name) is True
            for name in (
                "subprocess_contract_pass",
                "process_query_contract_pass",
                "route_contract_pass",
                "execution_identity_contract_pass",
                "author_execution_count_contract_pass",
            )
        ),
        "fourteen_unique_tokens": len(tokens) == 14
        and len(set(tokens)) == 14
        and orchestration.get("unique_execution_token_count") == 14,
        "thirty_process_queries": len(orchestration.get("process_query_records", []))
        == 30,
        "sixteen_subprocesses": len(orchestration.get("subprocess_records", []))
        == 16,
        "zero_final_targets": orchestration.get("final_target_process_count") == 0
        and orchestration.get("final_target_processes") == []
        and orchestration.get("final_process_query_error") == "",
        "all_route_evidence_success": all(
            isinstance(row, dict)
            and row.get("orchestration_status") == "SUCCESS_EVIDENCE_CAPTURED"
            and row.get("evidence_capture_ok") is True
            and row.get("execution_token_match") is True
            for row in records
        ),
    }
    if not all(orchestration_checks.values()):
        raise RuntimeError(f"orchestration semantics mismatch: {orchestration_checks}")

    failed_rows = [row for row in checks if row.get("status") == "FAIL"]
    failed_ids = {row.get("check_id") for row in failed_rows}
    validation_checks = {
        "schema_v2": validation.get("schema_version")
        == "BOARD21_STEP3_INDEPENDENT_VALIDATION_V2",
        "status_fail": validation.get("status") == "FAIL",
        "counts_247_of_251": validation.get("check_count") == 251
        and validation.get("passed_count") == 247
        and validation.get("failed_count") == 4,
        "unique_ids": validation.get("check_ids_unique") is True,
        "exact_failed_ids": set(validation.get("failed_check_ids", []))
        == EXPECTED_FAILED_CHECK_IDS
        and failed_ids == EXPECTED_FAILED_CHECK_IDS
        and len(failed_rows) == 4,
        "all_runs_scientifically_readable": validation.get(
            "artifact_seal_pass_run_count"
        )
        == 14
        and validation.get("hdf5_readable_pass_run_count") == 14
        and validation.get("inventory_workspace_crosscheck_pass_run_count") == 14,
        "seven_author_success_routes": validation.get("successful_route_count") == 7
        and validation.get("failed_route_count") == 0,
        "six_repeat_routes": validation.get("repeat_pass_route_count") == 6,
        "no_publication_or_process_leak": validation.get(
            "formal_success_directory_count"
        )
        == 0
        and validation.get("prepublication_failure_directory_count") == 0
        and validation.get("board22_named_root_count") == 0
        and validation.get("residual_target_process_count") == 0,
    }
    if not all(validation_checks.values()):
        raise RuntimeError(f"validation failure semantics mismatch: {validation_checks}")

    repeat7_rows = [row for row in repeats if row.get("route_id") == ROUTE7_ID]
    route7_rows = [row for row in routes if row.get("route_id") == ROUTE7_ID]
    if len(repeat7_rows) != 1 or len(route7_rows) != 1:
        raise RuntimeError("route7 rows are not unique")
    repeat7 = repeat7_rows[0]
    route7 = route7_rows[0]
    repeat_details = json.loads(repeat7["details_json"])
    variable_rows = repeat_details.get("variables", [])
    if not (
        repeat7.get("outcome") == "SUCCESS"
        and repeat7.get("repeat_pass") == "False"
        and repeat7.get("max_abs_difference") == "0.0"
        and repeat7.get("max_relative_difference") == "0.0"
        and repeat_details.get("both_science_valid") is False
        and len(variable_rows) == 8
        and all(
            row.get("pass") is True
            and row.get("max_abs") == 0.0
            and row.get("max_rel") == 0.0
            for row in variable_rows
        )
    ):
        raise RuntimeError(f"route7 repeat cascade mismatch: {repeat7}")
    if not (
        route7.get("execution_outcome") == "SUCCESS"
        and route7.get("repeat_status") == "FAIL"
        and route7.get("static_boundary")
        == "COORDINATE_ORDER_AND_FORMULA_CONFLICT"
    ):
        raise RuntimeError(f"route7 summary mismatch: {route7}")
    exact_float(float(route7["rep01_guyan_percent"]), 39.26575760689132, "route7 guyan")
    exact_float(float(route7["rep01_cb_percent"]), 20.20599925668106, "route7 cb")

    formula_rows = {
        row["check_id"]: json.loads(row["actual"])
        for row in failed_rows
        if row["check_id"] in {"S3-SCIENTIFIC-FORMULA-13", "S3-SCIENTIFIC-FORMULA-14"}
    }
    if set(formula_rows) != {
        "S3-SCIENTIFIC-FORMULA-13",
        "S3-SCIENTIFIC-FORMULA-14",
    }:
        raise RuntimeError("route7 formula failure records missing")
    for check_id, actual in formula_rows.items():
        if not (
            actual.get("formula_match") is False
            and actual.get("status_match") is True
            and actual.get("scientific_cross_pass") is True
        ):
            raise RuntimeError(f"unexpected formula cascade semantics: {check_id}")
        stored = actual.get("stored_sums", {})
        totals = actual.get("totals", {})
        exact_float(stored.get("energy_sum_orig"), 22403.23860163083, f"{check_id} orig")
        exact_float(stored.get("energy_sum_guyan"), 36887.32701500341, f"{check_id} guyan sum")
        exact_float(stored.get("energy_sum_cb"), 29856.69162409193, f"{check_id} cb sum")
        exact_float(totals.get("total_increase_guyan"), 39.26575760689132, f"{check_id} guyan total")
        exact_float(totals.get("total_increase_cb"), 20.20599925668106, f"{check_id} cb total")

    return {
        "orchestration_checks": orchestration_checks,
        "validation_checks": validation_checks,
        "failed_check_ids": sorted(EXPECTED_FAILED_CHECK_IDS),
        "route7_repeat_max_abs": 0.0,
        "route7_repeat_max_rel": 0.0,
        "route7_author_values": {
            "energy_sum_orig_selected": 22403.23860163083,
            "energy_sum_guyan": 36887.32701500341,
            "energy_sum_cb_selected": 29856.69162409193,
            "total_increase_guyan": 39.26575760689132,
            "total_increase_cb": 20.20599925668106,
        },
    }


def preflight() -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    board = BOARD_ROOT.resolve(strict=True)
    if is_link_like(ATTEMPTS_ROOT) or not ATTEMPTS_ROOT.is_dir():
        raise FileNotFoundError(
            f"ordinary attempts directory required: {ATTEMPTS_ROOT}"
        )
    attempts = ATTEMPTS_ROOT.resolve(strict=True)
    attempts.relative_to(board)
    if attempts == board:
        raise RuntimeError(f"attempts directory may not equal board root: {attempts}")
    assert_descendant(ATTEMPT_ROOT, ATTEMPTS_ROOT, "attempt root")
    assert_descendant(BUILDING_ROOT, ATTEMPTS_ROOT, "building root")
    if ATTEMPT_ROOT.exists() or is_link_like(ATTEMPT_ROOT):
        raise FileExistsError(f"refusing to overwrite attempt archive: {ATTEMPT_ROOT}")
    if BUILDING_ROOT.exists() or is_link_like(BUILDING_ROOT):
        raise FileExistsError(f"stale building archive exists: {BUILDING_ROOT}")

    for relative, expected_hash in EXPECTED_PINNED_HASHES.items():
        path = BOARD_ROOT / relative
        actual_hash = sha256_file(path) if path.is_file() else "MISSING"
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"pinned attempt file drift: {relative}: {actual_hash} != {expected_hash}"
            )
    for name, expected_hash in EXPECTED_TOOL_HASHES.items():
        path = CODE_ROOT / name
        actual_hash = sha256_file(path) if path.is_file() else "MISSING"
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"attempt tool drift: {name}: {actual_hash} != {expected_hash}"
            )

    artifact_rows: list[dict[str, Any]] = []
    root_counts: dict[str, dict[str, int]] = {}
    for logical_root, source, _ in SOURCE_MOVES:
        if is_link_like(source) or not source.is_dir():
            raise FileNotFoundError(f"ordinary source root required: {source}")
        assert_descendant(source, board, "source root")
        rows = scan_tree(logical_root, source)
        count = len(rows)
        size = sum(int(row["size_bytes"]) for row in rows)
        expected_count, expected_size = EXPECTED_ROOT_COUNTS[logical_root]
        if (count, size) != (expected_count, expected_size):
            raise RuntimeError(
                f"root count/size drift: {logical_root}: {(count, size)} != "
                f"{(expected_count, expected_size)}"
            )
        root_counts[logical_root] = {"file_count": count, "total_size_bytes": size}
        artifact_rows.extend(rows)
    if len(artifact_rows) != EXPECTED_ARTIFACT_COUNT or sum(
        int(row["size_bytes"]) for row in artifact_rows
    ) != EXPECTED_ARTIFACT_BYTES:
        raise RuntimeError("combined artifact count/size drift")

    path_budget = {
        "final": projected_path_budget(artifact_rows, ATTEMPT_ROOT, "final archive"),
        "building": projected_path_budget(
            artifact_rows, BUILDING_ROOT, "building archive"
        ),
    }

    processes = query_target_processes()
    if processes["target_processes"]:
        raise RuntimeError(f"target process exists: {processes['target_processes']}")
    semantics = verify_semantics()
    return artifact_rows, {
        "root_counts": root_counts,
        "processes": processes,
        "path_budget": path_budget,
    }, semantics


def execute_archive() -> dict[str, Any]:
    pre_rows, preflight_record, semantics = preflight()
    building_root = BUILDING_ROOT
    assert_descendant(building_root, ATTEMPTS_ROOT, "building root")
    building_root.mkdir(parents=False, exist_ok=False)
    moved: list[tuple[Path, Path]] = []
    try:
        tools_root = building_root / "tools_snapshot"
        tools_root.mkdir()
        tool_rows: list[dict[str, Any]] = []
        for name, expected_hash in EXPECTED_TOOL_HASHES.items():
            source = CODE_ROOT / name
            destination = tools_root / name
            with source.open("rb") as reader, destination.open("xb") as writer:
                shutil.copyfileobj(reader, writer, length=1024 * 1024)
            actual_hash = sha256_file(destination)
            if actual_hash != expected_hash:
                raise RuntimeError(f"tool snapshot mismatch after copy: {name}")
            tool_rows.append(
                {
                    "name": name,
                    "relative_path": destination.relative_to(building_root).as_posix(),
                    "size_bytes": destination.stat().st_size,
                    "sha256": actual_hash,
                }
            )

        for _, source, relative_destination in SOURCE_MOVES:
            destination = building_root / relative_destination
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                raise FileExistsError(destination)
            source.rename(destination)
            moved.append((source, destination))

        post_rows: list[dict[str, Any]] = []
        for logical_root, _, relative_destination in SOURCE_MOVES:
            post_rows.extend(scan_tree(logical_root, building_root / relative_destination))
        if pre_rows != post_rows:
            difference = describe_manifest_difference(pre_rows, post_rows)
            raise RuntimeError(
                "pre/post move artifact manifest mismatch: "
                + json.dumps(difference, ensure_ascii=False, sort_keys=True)
            )
        if any(source.exists() for _, source, _ in SOURCE_MOVES):
            raise RuntimeError("one or more standard roots remain after move")

        process_after = query_target_processes()
        if process_after["target_processes"]:
            raise RuntimeError(
                f"target process exists after move: {process_after['target_processes']}"
            )

        write_csv_new(
            building_root / "attempt_file_manifest.csv",
            post_rows,
            ["logical_root", "relative_path", "size_bytes", "sha256"],
        )
        write_csv_new(
            building_root / "tool_snapshot_manifest.csv",
            tool_rows,
            ["name", "relative_path", "size_bytes", "sha256"],
        )
        summary = {
            "schema_version": "BOARD21_STEP3_ATTEMPT_ARCHIVE_V2",
            "archive_status": "VALIDATOR_CONTRACT_FAILURE_ATTEMPT_PRESERVED",
            "attempt_id": ATTEMPT_ID,
            "physical_archive_directory": ATTEMPT_DIRNAME,
            "created_at": datetime.now().astimezone().isoformat(),
            "reason": (
                "The V3 orchestration completed all 14 author runs, but the V2 "
                "independent validator incorrectly declared route 7 sum_scope=all_vectors."
            ),
            "scientific_interpretation": (
                "All seven author routes executed twice and route 7 was exactly "
                "repeatable. This attempt is not accepted as the final Step3 evidence "
                "because its sealed validator used the wrong historical sum scope."
            ),
            "correct_route7_author_contract": {
                "source": "Copy_2_of_energy_zonghe3.mlx C004",
                "source_sha256": (
                    "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D"
                ),
                "retained_one_based": [1, 2],
                "energy_sum_orig": "sum(E_total(d))",
                "energy_sum_guyan": "sum(E_total_guyan)",
                "energy_sum_cb": "sum(E_total_cb(d2))",
                "guyan_denominator": "energy_sum_guyan",
                "cb_denominator": "energy_sum_guyan",
                "paper_formula_correct": False,
                "coordinate_order_correct": False,
            },
            "semantic_diagnosis": semantics,
            "moved_roots": [
                {
                    "logical_root": logical_root,
                    "source_before_archive": str(source),
                    "destination": str(ATTEMPT_ROOT / relative_destination),
                }
                for logical_root, source, relative_destination in SOURCE_MOVES
            ],
            "root_counts": preflight_record["root_counts"],
            "path_budget": preflight_record["path_budget"],
            "artifact_file_count": len(post_rows),
            "artifact_total_size_bytes": sum(
                int(row["size_bytes"]) for row in post_rows
            ),
            "tool_snapshot_count": len(tool_rows),
            "tool_snapshot_sha256": {
                row["name"]: row["sha256"] for row in tool_rows
            },
            "pinned_file_sha256": EXPECTED_PINNED_HASHES,
            "attempt_file_manifest": "attempt_file_manifest.csv",
            "tool_snapshot_manifest": "tool_snapshot_manifest.csv",
            "process_before_archive": preflight_record["processes"],
            "process_after_archive": process_after,
            "standard_step3_roots_absent_after_archive": True,
            "internal_absolute_paths_are_historical": True,
        }
        write_json_new(building_root / "attempt_summary.json", summary)
        final_moved = [
            (source, ATTEMPT_ROOT / destination.relative_to(building_root))
            for source, destination in moved
        ]
        building_root.rename(ATTEMPT_ROOT)
        moved = final_moved
        return summary
    except Exception:
        for source, destination in reversed(moved):
            if destination.exists() and not source.exists():
                source.parent.mkdir(parents=True, exist_ok=True)
                destination.rename(source)
        raise


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--execute",
        action="store_true",
        help="move the six verified roots into the immutable attempt archive",
    )
    args = parser.parse_args()
    if args.execute:
        result = execute_archive()
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    rows, preflight_record, semantics = preflight()
    result = {
        "schema_version": "BOARD21_STEP3_ATTEMPT02_ARCHIVE_PREFLIGHT_V1",
        "status": "PREFLIGHT_PASS",
        "execute_requested": False,
        "artifact_file_count": len(rows),
        "artifact_total_size_bytes": sum(int(row["size_bytes"]) for row in rows),
        "root_counts": preflight_record["root_counts"],
        "path_budget": preflight_record["path_budget"],
        "target_process_count": len(preflight_record["processes"]["target_processes"]),
        "semantic_diagnosis": semantics,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

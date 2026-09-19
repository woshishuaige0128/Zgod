from __future__ import annotations

import csv
import hashlib
import json
import os
import shutil
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
CODE_ROOT = SCRIPT.parent
BOARD_ROOT = CODE_ROOT.parent
ATTEMPT_ROOT = (
    BOARD_ROOT
    / "attempts"
    / "step3_attempt01_20260826_pid_contract_failure"
)
TOOLS_ROOT = ATTEMPT_ROOT / "tools_snapshot"

SOURCE_MOVES = (
    (
        "outputs_step3_stage",
        BOARD_ROOT / "outputs" / "step3_stage",
        ATTEMPT_ROOT / "outputs" / "step3_stage",
    ),
    (
        "outputs_step3_runs",
        BOARD_ROOT / "outputs" / "step3_runs",
        ATTEMPT_ROOT / "outputs" / "step3_runs",
    ),
    (
        "outputs_step3_orchestration",
        BOARD_ROOT / "outputs" / "step3_orchestration",
        ATTEMPT_ROOT / "outputs" / "step3_orchestration",
    ),
    (
        "tmp_step3_runs",
        BOARD_ROOT / "tmp" / "step3_runs",
        ATTEMPT_ROOT / "tmp" / "step3_runs",
    ),
    (
        "logs_step3_runs",
        BOARD_ROOT / "logs" / "step3_runs",
        ATTEMPT_ROOT / "logs" / "step3_runs",
    ),
)

EXPECTED_TOOL_HASHES = {
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


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON root is not an object: {path}")
    return value


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def write_csv_new(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = ["logical_root", "relative_path", "size_bytes", "sha256"]
    with path.open("x", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def assert_within(path: Path, parent: Path, label: str) -> Path:
    resolved = path.resolve(strict=False)
    resolved.relative_to(parent.resolve(strict=True))
    if resolved == parent.resolve(strict=True):
        raise RuntimeError(f"{label} may not equal parent root: {resolved}")
    return resolved


def scan_tree(logical_root: str, root: Path) -> list[dict[str, Any]]:
    if not root.is_dir():
        raise FileNotFoundError(root)
    rows: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise RuntimeError(f"symbolic link is not allowed in attempt evidence: {path}")
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
    if not isinstance(raw, list):
        raise TypeError("process query did not return a list")
    target: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            raise TypeError("process query contains a non-object item")
        pid = int(item.get("ProcessId") or -1)
        name = str(item.get("Name") or "")
        command_line = str(item.get("CommandLine") or "")
        if pid == os.getpid():
            continue
        if name.casefold() == "matlab.exe" or any(
            token in command_line.casefold()
            for token in (
                "run_board21_step3_all.py",
                "execute_board21_step3_route.py",
            )
        ):
            target.append(item)
    return {
        "returncode": completed.returncode,
        "stdout_size_bytes": len(completed.stdout),
        "stdout_sha256": hashlib.sha256(completed.stdout).hexdigest().upper(),
        "stderr_size_bytes": len(completed.stderr),
        "stderr_sha256": hashlib.sha256(completed.stderr).hexdigest().upper(),
        "target_processes": target,
    }


def verify_attempt_semantics() -> dict[str, Any]:
    run_root = BOARD_ROOT / "outputs" / "step3_runs"
    orchestration_path = (
        BOARD_ROOT
        / "outputs"
        / "step3_orchestration"
        / "run_all_summary.json"
    )
    status_path = (
        run_root
        / "reference15_pd19_energy"
        / "rep01"
        / "metadata"
        / "run_status.json"
    )
    exit_path = status_path.with_name("process_exit.json")
    orchestration = load_json(orchestration_path)
    status = load_json(status_path)
    exit_record = load_json(exit_path)
    false_status_checks = sorted(
        key
        for key, value in exit_record.get("status_contract_checks", {}).items()
        if value is not True
    )
    launcher_pid = int(exit_record.get("pid"))
    matlab_pid = int(status.get("environment", {}).get("pid"))
    checks = {
        "orchestration_schema_v2": orchestration.get("schema_version")
        == "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V2",
        "orchestration_failed": orchestration.get("status") == "FAIL",
        "one_run_executed": orchestration.get("executed_run_count") == 1,
        "thirteen_runs_unstarted": len(orchestration.get("unstarted_runs", [])) == 13,
        "infrastructure_failure": orchestration.get("infrastructure_failure") is True,
        "correct_interruption_point": orchestration.get("interruption_point")
        == "01__reference15_pd19_energy__rep01__INFRASTRUCTURE_FAILURE",
        "zero_final_processes": orchestration.get("final_target_process_count") == 0
        and orchestration.get("final_target_processes") == [],
        "runner_completed_science": status.get("execution_status")
        == "EXECUTION_SUCCESS"
        and status.get("evidence_status") == "PASS"
        and status.get("final_status") == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
        and status.get("capture_errors") == [],
        "matlab_exit_zero": exit_record.get("returncode") == 0
        and exit_record.get("timed_out") is False,
        "executor_rejected_evidence": exit_record.get("evidence_capture_ok") is False
        and exit_record.get("orchestration_status") == "ZERO_EXIT_STATUS_MISMATCH",
        "only_environment_contract_failed": false_status_checks == ["environment"],
        "launcher_and_matlab_pid_are_positive_and_distinct": launcher_pid > 0
        and matlab_pid > 0
        and launcher_pid != matlab_pid,
    }
    if not all(checks.values()):
        raise RuntimeError(f"attempt semantics did not match diagnosis: {checks}")
    return {
        "checks": checks,
        "launcher_pid": launcher_pid,
        "matlab_pid": matlab_pid,
        "false_status_contract_checks": false_status_checks,
        "orchestration_path_before_archive": str(orchestration_path),
        "status_path_before_archive": str(status_path),
        "process_exit_path_before_archive": str(exit_path),
    }


def main() -> int:
    board = BOARD_ROOT.resolve(strict=True)
    attempt = assert_within(ATTEMPT_ROOT, board, "attempt root")
    if not ATTEMPT_ROOT.is_dir() or not TOOLS_ROOT.is_dir():
        raise RuntimeError(
            "attempt root and the pre-created tools_snapshot directory must exist"
        )
    if any((ATTEMPT_ROOT / name).exists() for name in ("outputs", "tmp", "logs")):
        raise FileExistsError("attempt archive move destinations already exist")
    if (BOARD_ROOT / "outputs" / "step3_validation").exists():
        raise RuntimeError("unexpected step3_validation exists before archive")

    tool_rows: list[dict[str, Any]] = []
    for name, expected_hash in EXPECTED_TOOL_HASHES.items():
        path = TOOLS_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"missing attempt tool snapshot: {path}")
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                f"attempt tool hash mismatch: {name}: {actual_hash} != {expected_hash}"
            )
        tool_rows.append(
            {
                "name": name,
                "relative_path": path.relative_to(ATTEMPT_ROOT).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": actual_hash,
            }
        )

    for _, source, destination in SOURCE_MOVES:
        source_resolved = assert_within(source, board, "source root")
        destination_resolved = assert_within(destination, attempt, "destination root")
        if not source_resolved.is_dir():
            raise FileNotFoundError(source_resolved)
        if destination_resolved.exists():
            raise FileExistsError(destination_resolved)

    process_before = query_target_processes()
    if process_before["target_processes"]:
        raise RuntimeError(
            f"target process exists before archive: {process_before['target_processes']}"
        )
    semantic_diagnosis = verify_attempt_semantics()

    pre_rows: list[dict[str, Any]] = []
    for logical_root, source, _ in SOURCE_MOVES:
        pre_rows.extend(scan_tree(logical_root, source))
    if not pre_rows:
        raise RuntimeError("attempt artifact manifest would be empty")

    for _, source, destination in SOURCE_MOVES:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(destination))

    post_rows: list[dict[str, Any]] = []
    for logical_root, _, destination in SOURCE_MOVES:
        post_rows.extend(scan_tree(logical_root, destination))
    if pre_rows != post_rows:
        raise RuntimeError("pre/post move file manifest mismatch")
    if any(source.exists() for _, source, _ in SOURCE_MOVES):
        raise RuntimeError("one or more standard attempt roots still exist after move")

    process_after = query_target_processes()
    if process_after["target_processes"]:
        raise RuntimeError(
            f"target process exists after archive: {process_after['target_processes']}"
        )

    write_csv_new(ATTEMPT_ROOT / "attempt_file_manifest.csv", post_rows)
    with (ATTEMPT_ROOT / "tool_snapshot_manifest.csv").open(
        "x", encoding="utf-8-sig", newline=""
    ) as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["name", "relative_path", "size_bytes", "sha256"],
        )
        writer.writeheader()
        writer.writerows(tool_rows)

    summary = {
        "schema_version": "BOARD21_STEP3_ATTEMPT_ARCHIVE_V1",
        "archive_status": "FAILED_INFRASTRUCTURE_ATTEMPT_PRESERVED",
        "created_at": datetime.now().astimezone().isoformat(),
        "attempt_id": "step3_attempt01_20260826_pid_contract_failure",
        "reason": (
            "Windows MATLAB launcher PID and actual MATLAB child PID were distinct; "
            "the V1 evidence contract incorrectly required equality."
        ),
        "scientific_interpretation": (
            "The first author route completed inside MATLAB, but this attempt is not "
            "accepted as Step3 evidence because the outer infrastructure contract failed."
        ),
        "semantic_diagnosis": semantic_diagnosis,
        "moved_roots": [
            {
                "logical_root": logical_root,
                "source_before_archive": str(source),
                "destination": str(destination),
            }
            for logical_root, source, destination in SOURCE_MOVES
        ],
        "step3_validation_was_absent": True,
        "artifact_file_count": len(post_rows),
        "artifact_total_size_bytes": sum(int(row["size_bytes"]) for row in post_rows),
        "tool_snapshot_count": len(tool_rows),
        "tool_snapshot_sha256": {
            row["name"]: row["sha256"] for row in tool_rows
        },
        "attempt_file_manifest": "attempt_file_manifest.csv",
        "tool_snapshot_manifest": "tool_snapshot_manifest.csv",
        "process_before_archive": process_before,
        "process_after_archive": process_after,
        "standard_step3_roots_absent_after_archive": True,
        "internal_absolute_paths_are_historical": True,
    }
    write_json_new(ATTEMPT_ROOT / "attempt_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
CODE_ROOT = SCRIPT.parent
BOARD_ROOT = CODE_ROOT.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
STAGER = CODE_ROOT / "stage_board21_step4_inputs.py"
PYTHON_COMPUTE = CODE_ROOT / "compute_board21_step4_formulas.py"
MATLAB_COMPUTE = CODE_ROOT / "compute_board21_step4_formulas.m"
VALIDATOR = CODE_ROOT / "validate_board21_step4.py"
INPUT_ROOT = BOARD_ROOT / "outputs" / "s4i"
COMPUTE_ROOT = BOARD_ROOT / "outputs" / "s4"
ORCHESTRATION_ROOT = BOARD_ROOT / "outputs" / "s4o"
LOG_ROOT = BOARD_ROOT / "logs" / "s4"
PYTHON_EXE = Path(r"D:\Software\python\python.exe")
MATLAB_EXE = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
PYTHON_TIMEOUT = 1200
MATLAB_TIMEOUT = 1800
PROCESS_QUERY_TIMEOUT = 30
ENVIRONMENT = {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
    "PYTHONDONTWRITEBYTECODE": "1",
}
INSTRUMENTS = (
    "stage_board21_step4_inputs.py",
    "compute_board21_step4_formulas.py",
    "compute_board21_step4_formulas.m",
    "run_board21_step4_all.py",
    "validate_board21_step4.py",
)


def timestamp() -> str:
    return datetime.now().astimezone().isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


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


def write_csv_new(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def terminal_json(stdout: bytes) -> dict[str, Any]:
    lines = [line.strip() for line in stdout.decode("utf-8").splitlines() if line.strip()]
    if not lines:
        raise RuntimeError("subprocess stdout has no nonempty terminal line")
    value = json.loads(lines[-1])
    if not isinstance(value, dict):
        raise TypeError("terminal JSON is not an object")
    return value


def run_process(name: str, command: list[str], timeout_seconds: int) -> dict[str, Any]:
    environment = os.environ.copy()
    environment.update(ENVIRONMENT)
    started = timestamp()
    start_clock = time.monotonic()
    timed_out = False
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout_seconds,
            check=False,
            env=environment,
        )
        returncode: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
        timeout_error = ""
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = None
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        timeout_error = f"TimeoutExpired after {timeout_seconds} seconds"
    record = {
        "name": name,
        "command": command,
        "cwd": str(PROJECT_ROOT),
        "started_at": started,
        "finished_at": timestamp(),
        "duration_seconds": time.monotonic() - start_clock,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "timeout_error": timeout_error,
        "returncode": returncode,
        "stdout_size_bytes": len(stdout),
        "stderr_size_bytes": len(stderr),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "stdout": stdout,
        "stderr": stderr,
    }
    try:
        record["terminal_json"] = terminal_json(stdout)
        record["terminal_json_error"] = ""
    except Exception as error:
        record["terminal_json"] = {}
        record["terminal_json_error"] = f"{type(error).__name__}: {error}"
    return record


def public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in record.items() if key not in {"stdout", "stderr"}}


def save_process_record(record: dict[str, Any]) -> None:
    base = LOG_ROOT / record["name"]
    with (base.with_suffix(".stdout.log")).open("xb") as stream:
        stream.write(record["stdout"])
    with (base.with_suffix(".stderr.log")).open("xb") as stream:
        stream.write(record["stderr"])
    write_json_new(base.with_suffix(".json"), public_record(record))


def query_target_processes(label: str) -> dict[str, Any]:
    board_token = str(BOARD_ROOT).replace("'", "''")
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw)\\.exe$' -and "
        "$_.CommandLine -like '*" + board_token + "*' -and "
        "($_.CommandLine -like '*compute_board21_step4_formulas*' -or "
        "$_.CommandLine -like '*stage_board21_step4_inputs*')} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    completed = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", script],
        cwd=PROJECT_ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=PROCESS_QUERY_TIMEOUT,
        check=False,
    )
    raw = completed.stdout.decode("utf-8-sig").strip()
    if completed.returncode != 0:
        raise RuntimeError(
            f"process query {label} failed: {completed.stderr.decode('utf-8', errors='replace')}"
        )
    parsed: Any = [] if not raw else json.loads(raw)
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list):
        raise TypeError("process query result is not a list")
    current_pid = os.getpid()
    items = [item for item in parsed if int(item.get("ProcessId", -1)) != current_pid]
    record = {
        "label": label,
        "returncode": completed.returncode,
        "stdout_sha256": sha256_bytes(completed.stdout),
        "stderr_sha256": sha256_bytes(completed.stderr),
        "target_count": len(items),
        "items": items,
    }
    write_json_new(LOG_ROOT / f"process_{label}.json", record)
    return record


def matlab_quote(path: Path | str) -> str:
    return str(path).replace("'", "''")


def expected_payload_files(root: Path) -> list[Path]:
    names = ["values.csv", "case_results.csv", "compute_summary.json", "output_manifest.csv"]
    paths = [root / name for name in names]
    if not all(path.is_file() for path in paths):
        raise RuntimeError(f"compute payload is incomplete: {root}")
    extras = sorted(path.name for path in root.iterdir() if path.is_file() and path.name not in names)
    directories = [path.name for path in root.iterdir() if path.is_dir()]
    if extras or directories:
        raise RuntimeError(f"compute payload is not closed: extras={extras}, dirs={directories}")
    return paths


def main() -> int:
    for required in (PYTHON_EXE, MATLAB_EXE, STAGER, PYTHON_COMPUTE, MATLAB_COMPUTE, VALIDATOR):
        if not required.is_file():
            raise FileNotFoundError(required)
    for target in (INPUT_ROOT, COMPUTE_ROOT, ORCHESTRATION_ROOT, LOG_ROOT):
        if target.exists():
            raise FileExistsError(f"exclusive Step4 target already exists: {target}")
    ORCHESTRATION_ROOT.mkdir(parents=True)
    LOG_ROOT.mkdir(parents=True)
    records: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    tool_hashes_before = {name: sha256_file(CODE_ROOT / name) for name in INSTRUMENTS}
    snapshots.append(query_target_processes("initial"))
    if snapshots[-1]["target_count"] != 0:
        raise RuntimeError("Step4 target process exists before orchestration")

    stage_record = run_process(
        "stage",
        [str(PYTHON_EXE), "-B", str(STAGER)],
        300,
    )
    records.append(stage_record)
    save_process_record(stage_record)
    if (
        stage_record["returncode"] != 0
        or stage_record["timed_out"]
        or stage_record["terminal_json"].get("status") != "PASS"
        or stage_record["terminal_json"].get("total_manifest_item_count") != 103
    ):
        raise RuntimeError("Step4 input staging failed")

    run_specs = []
    for round_id in ("a", "b"):
        for implementation in ("py", "matlab"):
            output = COMPUTE_ROOT / round_id / implementation
            token = f"BOARD21_STEP4_{round_id.upper()}_{implementation.upper()}"
            run_specs.append((round_id, implementation, output, token))
    for run_number, (round_id, implementation, output, token) in enumerate(run_specs, start=1):
        if implementation == "py":
            command = [
                str(PYTHON_EXE), "-B", str(PYTHON_COMPUTE),
                "--input-root", str(INPUT_ROOT),
                "--output-root", str(output),
                "--execution-token", token,
            ]
            timeout_seconds = PYTHON_TIMEOUT
        else:
            snapshots.append(query_target_processes(f"before_matlab_{round_id}"))
            if snapshots[-1]["target_count"] != 0:
                raise RuntimeError(f"target process exists before MATLAB round {round_id}")
            expression = (
                f"addpath('{matlab_quote(CODE_ROOT)}'); "
                f"compute_board21_step4_formulas('{matlab_quote(INPUT_ROOT)}',"
                f"'{matlab_quote(output)}','{token}');"
            )
            command = [str(MATLAB_EXE), "-batch", expression]
            timeout_seconds = MATLAB_TIMEOUT
        record = run_process(
            f"run_{run_number:02d}_{round_id}_{implementation}",
            command,
            timeout_seconds,
        )
        records.append(record)
        save_process_record(record)
        if (
            record["returncode"] != 0
            or record["timed_out"]
            or record["terminal_json"].get("status") != "PASS"
            or record["terminal_json"].get("table4_1_adjudicated") is not False
        ):
            raise RuntimeError(f"Step4 compute failed: {round_id}/{implementation}")
        expected_payload_files(output)
        if implementation == "matlab":
            snapshots.append(query_target_processes(f"after_matlab_{round_id}"))
            if snapshots[-1]["target_count"] != 0:
                raise RuntimeError(f"target process remains after MATLAB round {round_id}")

    determinism_rows: list[dict[str, Any]] = []
    for implementation in ("py", "matlab"):
        a_root = COMPUTE_ROOT / "a" / implementation
        b_root = COMPUTE_ROOT / "b" / implementation
        for name in ("values.csv", "case_results.csv", "compute_summary.json", "output_manifest.csv"):
            a = a_root / name
            b = b_root / name
            a_hash = sha256_file(a)
            b_hash = sha256_file(b)
            match = a.stat().st_size == b.stat().st_size and a_hash == b_hash
            determinism_rows.append(
                {
                    "implementation": implementation,
                    "relative_path": name,
                    "a_size_bytes": a.stat().st_size,
                    "b_size_bytes": b.stat().st_size,
                    "a_sha256": a_hash,
                    "b_sha256": b_hash,
                    "byte_identical": str(match).upper(),
                }
            )
            if not match:
                raise RuntimeError(f"determinism failure: {implementation}/{name}")
    write_csv_new(
        ORCHESTRATION_ROOT / "determinism.csv",
        determinism_rows,
        [
            "implementation", "relative_path", "a_size_bytes", "b_size_bytes",
            "a_sha256", "b_sha256", "byte_identical",
        ],
    )
    snapshots.append(query_target_processes("final"))
    if snapshots[-1]["target_count"] != 0:
        raise RuntimeError("Step4 target process remains at final query")
    tool_hashes_after = {name: sha256_file(CODE_ROOT / name) for name in INSTRUMENTS}
    if tool_hashes_before != tool_hashes_after:
        raise RuntimeError("Step4 instrument changed during orchestration")
    write_json_new(
        ORCHESTRATION_ROOT / "process_records.json",
        {
            "schema_version": "BOARD21_STEP4_PROCESS_RECORDS_V1",
            "records": [public_record(record) for record in records],
            "process_snapshots": snapshots,
        },
    )
    tool_rows = [
        {"name": name, "sha256": tool_hashes_after[name], "status": "UNCHANGED"}
        for name in INSTRUMENTS
    ]
    write_csv_new(
        ORCHESTRATION_ROOT / "tool_hashes.csv",
        tool_rows,
        ["name", "sha256", "status"],
    )
    summary = {
        "schema_version": "BOARD21_STEP4_ORCHESTRATION_V1",
        "status": "PASS",
        "stage_status": "PASS",
        "compute_run_count": 4,
        "compute_success_count": 4,
        "python_round_count": 2,
        "matlab_round_count": 2,
        "determinism_check_count": len(determinism_rows),
        "determinism_pass_count": sum(row["byte_identical"] == "TRUE" for row in determinism_rows),
        "initial_target_process_count": snapshots[0]["target_count"],
        "final_target_process_count": snapshots[-1]["target_count"],
        "instrument_count": len(tool_hashes_after),
        "formula_4_45_evaluated_conditionally": True,
        "table4_1_adjudicated": False,
        "scientific_status": "AUTHOR_ROUTE_REPRODUCED_AND_PAPER_LITERAL_CONDITIONAL_TABLE4_1_PENDING",
        "started_at": records[0]["started_at"],
        "finished_at": timestamp(),
    }
    write_json_new(ORCHESTRATION_ROOT / "run_all_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        failure = {
            "schema_version": "BOARD21_STEP4_ORCHESTRATION_FAILURE_V1",
            "status": "FAIL",
            "error": f"{type(error).__name__}: {error}",
            "finished_at": timestamp(),
        }
        try:
            if ORCHESTRATION_ROOT.is_dir() and not (ORCHESTRATION_ROOT / "failure_summary.json").exists():
                write_json_new(ORCHESTRATION_ROOT / "failure_summary.json", failure)
        except Exception:
            pass
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        raise

from __future__ import annotations

import csv
import hashlib
import json
import os
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
CODE_ROOT = SCRIPT.parent
BOARD_ROOT = CODE_ROOT.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
STAGER = CODE_ROOT / "stage_board21_step3_runs.py"
EXECUTOR = CODE_ROOT / "execute_board21_step3_route.py"
STAGE_ROOT = BOARD_ROOT / "outputs" / "step3_stage"
RUN_ROOT = BOARD_ROOT / "outputs" / "step3_runs"
WORK_ROOT = BOARD_ROOT / "tmp" / "step3_runs"
LOG_ROOT = BOARD_ROOT / "logs" / "step3_runs"
ORCHESTRATION_ROOT = BOARD_ROOT / "outputs" / "step3_orchestration"
EXPECTED_PYTHON = Path(r"D:\Software\python\python.exe")
STAGER_TIMEOUT_SECONDS = 120
EXECUTOR_WRAPPER_TIMEOUT_SECONDS = 1000
MATLAB_TIMEOUT_SECONDS = 900
PROCESS_QUERY_TIMEOUT_SECONDS = 30
PYTHON_ENVIRONMENT_OVERRIDES = {
    "PYTHONIOENCODING": "utf-8",
    "PYTHONUTF8": "1",
}
INPUT_MANIFEST_SHA256 = "8808274780EFB5CF4E3BF26C6466FC92F2AB91206A5D7EFBC004A177A6EFBFD2"
INPUT_FREEZE_SUMMARY_SHA256 = "ADE5A15A91BE7802AF92A8A7CD7A9600EA86CE6FE85148A8057F9944AA88C84F"

ROUTE_ORDER = (
    "reference15_pd19_energy",
    "division1_pd19_copy",
    "division1_tp17_energy",
    "division1_tp17_copy2_formula_invalid",
    "division2_pd19_copy",
    "division2_tp17_energy_coordinate_conflict",
    "division2_tp17_copy2_coordinate_formula_conflict",
)
ROUTE_FILES = {
    "reference15_pd19_energy": ("PDmonicanshu.m", "energy_zonghe.mlx"),
    "division1_pd19_copy": ("PDmonicanshu2.m", "Copy_of_energy_zonghe2.mlx"),
    "division1_tp17_energy": ("monicanshu_2_suoju.mlx", "energy_zonghe2.mlx"),
    "division1_tp17_copy2_formula_invalid": (
        "monicanshu_2_suoju.mlx",
        "Copy_2_of_energy_zonghe2.mlx",
    ),
    "division2_pd19_copy": ("PDmonicanshu3.m", "Copy_of_energy_zonghe3.mlx"),
    "division2_tp17_energy_coordinate_conflict": (
        "monicanshu_3_suoju.mlx",
        "energy_zonghe3.mlx",
    ),
    "division2_tp17_copy2_coordinate_formula_conflict": (
        "monicanshu_3_suoju.mlx",
        "Copy_2_of_energy_zonghe3.mlx",
    ),
}
REPLICATES = ("rep01", "rep02")
EXPECTED_RUN_ORDER = tuple(
    (route_id, replicate)
    for route_id in ROUTE_ORDER
    for replicate in REPLICATES
)
INSTRUMENT_FILES = (
    "stage_board21_step3_runs.py",
    "run_one_board21_energy_route.m",
    "execute_board21_step3_route.py",
    "run_board21_step3_all.py",
    "validate_board21_step3_runs.py",
)


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat()


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest().upper()


def positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def uppercase_hex_64(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789ABCDEF" for character in value)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def instrument_hashes() -> dict[str, str]:
    result: dict[str, str] = {}
    for name in INSTRUMENT_FILES:
        path = CODE_ROOT / name
        if not path.is_file():
            raise FileNotFoundError(f"missing instrument: {path}")
        result[name] = sha256_file(path)
    return result


def write_json_new(path: Path, value: Any) -> None:
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(payload)


def write_bytes_new(path: Path, payload: bytes) -> None:
    with path.open("xb") as stream:
        stream.write(payload)


def terminal_json_record(stdout: bytes) -> dict[str, Any]:
    nonempty_lines = [line.strip() for line in stdout.splitlines() if line.strip()]
    if not nonempty_lines:
        raise RuntimeError("subprocess stdout has no nonempty terminal line")
    raw_line = nonempty_lines[-1]
    text = raw_line.decode("utf-8")
    value = json.loads(text)
    if not isinstance(value, dict):
        raise TypeError("subprocess terminal JSON must be an object")
    canonical = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return {
        "value": value,
        "line_size_bytes": len(raw_line),
        "line_sha256": sha256_bytes(raw_line),
        "utf8_size_bytes": len(canonical),
        "utf8_sha256": sha256_bytes(canonical),
    }


def run_python(arguments: list[str], timeout_seconds: int) -> dict[str, Any]:
    command = [str(EXPECTED_PYTHON), *arguments]
    child_environment = os.environ.copy()
    child_environment.update(PYTHON_ENVIRONMENT_OVERRIDES)
    started_at = timestamp_now()
    started_monotonic = time.monotonic()
    timed_out = False
    timeout_error = ""
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
            env=child_environment,
        )
        returncode: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = None
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        timeout_error = (
            f"TimeoutExpired: command exceeded {timeout_seconds} seconds"
        )
    return {
        "command": command,
        "cwd": str(PROJECT_ROOT),
        "started_at": started_at,
        "finished_at": timestamp_now(),
        "duration_seconds": time.monotonic() - started_monotonic,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "timeout_error": timeout_error,
        "environment_overrides": PYTHON_ENVIRONMENT_OVERRIDES,
        "returncode": returncode,
        "stdout": stdout,
        "stderr": stderr,
    }


def subprocess_record(name: str, result: dict[str, Any]) -> dict[str, Any]:
    terminal: dict[str, Any] = {}
    terminal_error = ""
    try:
        terminal = terminal_json_record(result["stdout"])
    except Exception as error:
        terminal_error = f"{type(error).__name__}: {error}"
    return {
        "name": name,
        "command": result["command"],
        "cwd": result["cwd"],
        "started_at": result["started_at"],
        "finished_at": result["finished_at"],
        "duration_seconds": result["duration_seconds"],
        "timeout_seconds": result["timeout_seconds"],
        "timed_out": result["timed_out"],
        "timeout_error": result["timeout_error"],
        "environment_overrides": result["environment_overrides"],
        "returncode": result["returncode"],
        "stdout_size_bytes": len(result["stdout"]),
        "stderr_size_bytes": len(result["stderr"]),
        "stdout_sha256": sha256_bytes(result["stdout"]),
        "stderr_sha256": sha256_bytes(result["stderr"]),
        "terminal_json": terminal.get("value", {}),
        "terminal_json_error": terminal_error,
        "terminal_json_line_size_bytes": terminal.get("line_size_bytes", -1),
        "terminal_json_line_sha256": terminal.get("line_sha256", ""),
        "terminal_json_utf8_size_bytes": terminal.get("utf8_size_bytes", -1),
        "terminal_json_utf8_sha256": terminal.get("utf8_sha256", ""),
    }


def target_processes(
    query_name: str,
) -> tuple[dict[str, Any], bytes, bytes]:
    board_token = str(BOARD_ROOT).casefold()
    script = (
        "$ErrorActionPreference='Stop'; "
        "[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding=[Console]::OutputEncoding; "
        "$items=Get-CimInstance Win32_Process | Where-Object {"
        "$_.Name -match '^(MATLAB|python|pythonw|pdftoppm)\\.exe$'} | "
        "Select-Object Name,ProcessId,ParentProcessId,CommandLine; "
        "$items | ConvertTo-Json -Compress"
    )
    command = ["powershell.exe", "-NoProfile", "-Command", script]
    started_at = timestamp_now()
    started_monotonic = time.monotonic()
    timed_out = False
    timeout_error = ""
    try:
        completed = subprocess.run(
            command,
            cwd=PROJECT_ROOT,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=PROCESS_QUERY_TIMEOUT_SECONDS,
        )
        returncode: int | None = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        returncode = None
        stdout = error.stdout or b""
        stderr = error.stderr or b""
        timeout_error = (
            "TimeoutExpired: PowerShell process query exceeded "
            f"{PROCESS_QUERY_TIMEOUT_SECONDS} seconds"
        )

    parse_error = ""
    raw_process_count = 0
    result: list[dict[str, Any]] = []
    stderr_text = stderr.decode("utf-8", errors="replace").strip()
    if not timed_out and returncode == 0 and stderr == b"":
        try:
            text = stdout.decode("utf-8-sig").strip()
            raw: Any = [] if not text else json.loads(text)
            if isinstance(raw, dict):
                raw = [raw]
            if not isinstance(raw, list) or not all(
                isinstance(item, dict) for item in raw
            ):
                raise TypeError("PowerShell process query JSON must be an array")
            raw_process_count = len(raw)
            for item in raw:
                pid = int(item.get("ProcessId") or -1)
                name = str(item.get("Name") or "")
                command_line = str(item.get("CommandLine") or "")
                if pid == os.getpid():
                    continue
                if (
                    name.casefold() == "matlab.exe"
                    or board_token in command_line.casefold()
                ):
                    result.append(item)
        except Exception as error:
            parse_error = f"{type(error).__name__}: {error}"
    ok = bool(
        not timed_out
        and returncode == 0
        and stderr == b""
        and not parse_error
    )
    record = {
        "schema_version": "BOARD21_STEP3_PROCESS_QUERY_V1",
        "query_name": query_name,
        "command": command,
        "cwd": str(PROJECT_ROOT),
        "started_at": started_at,
        "finished_at": timestamp_now(),
        "duration_seconds": time.monotonic() - started_monotonic,
        "timeout_seconds": PROCESS_QUERY_TIMEOUT_SECONDS,
        "timed_out": timed_out,
        "timeout_error": timeout_error,
        "returncode": returncode,
        "stdout_size_bytes": len(stdout),
        "stderr_size_bytes": len(stderr),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "stderr_text": stderr_text,
        "parse_error": parse_error,
        "raw_process_count": raw_process_count,
        "filtered_process_count": len(result),
        "processes": result,
        "ok": ok,
    }
    return record, stdout, stderr


def capture_process_query(
    query_name: str,
    capture_root: Path,
) -> dict[str, Any]:
    if not query_name or not all(
        character.isalnum() or character in {"_", "-"}
        for character in query_name
    ):
        raise ValueError(f"unsafe process query name: {query_name!r}")
    record, stdout, stderr = target_processes(query_name)
    stdout_path = capture_root / f"{query_name}.stdout.log"
    stderr_path = capture_root / f"{query_name}.stderr.log"
    capture_error = ""
    try:
        write_bytes_new(stdout_path, stdout)
        write_bytes_new(stderr_path, stderr)
    except Exception as error:
        capture_error = f"{type(error).__name__}: {error}"
    stdout_exists = stdout_path.is_file()
    stderr_exists = stderr_path.is_file()
    capture_match = bool(
        not capture_error
        and stdout_exists
        and stderr_exists
        and stdout_path.stat().st_size == len(stdout)
        and stderr_path.stat().st_size == len(stderr)
        and sha256_file(stdout_path) == sha256_bytes(stdout)
        and sha256_file(stderr_path) == sha256_bytes(stderr)
    )
    record.update(
        {
            "stdout_path": str(stdout_path.resolve()),
            "stderr_path": str(stderr_path.resolve()),
            "capture_error": capture_error,
            "capture_match": capture_match,
        }
    )
    return record


def process_query_capture_matches(
    record: dict[str, Any], capture_root: Path
) -> bool:
    query_name = str(record.get("query_name", ""))
    if not query_name or not all(
        character.isalnum() or character in {"_", "-"}
        for character in query_name
    ):
        return False
    expected_stdout = (capture_root / f"{query_name}.stdout.log").resolve()
    expected_stderr = (capture_root / f"{query_name}.stderr.log").resolve()
    try:
        actual_stdout = Path(str(record.get("stdout_path", "")))
        actual_stderr = Path(str(record.get("stderr_path", "")))
        if (
            not actual_stdout.is_absolute()
            or not actual_stderr.is_absolute()
            or actual_stdout.resolve() != expected_stdout
            or actual_stderr.resolve() != expected_stderr
            or not expected_stdout.is_file()
            or not expected_stderr.is_file()
        ):
            return False
        return bool(
            expected_stdout.stat().st_size == record.get("stdout_size_bytes")
            and expected_stderr.stat().st_size == record.get("stderr_size_bytes")
            and sha256_file(expected_stdout) == record.get("stdout_sha256")
            and sha256_file(expected_stderr) == record.get("stderr_sha256")
            and expected_stderr.stat().st_size == 0
        )
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def exact_path(actual: Any, expected: Path, label: str) -> None:
    path = Path(str(actual))
    if not path.is_absolute() or path.resolve() != expected.resolve():
        raise RuntimeError(
            f"{label} mismatch: expected={expected.resolve()}, actual={actual}"
        )


def verify_config_rows(
    rows: list[dict[str, str]], sealed_tools: dict[str, str]
) -> list[dict[str, Any]]:
    actual_order = tuple((row.get("route_id", ""), row.get("replicate", "")) for row in rows)
    if actual_order != EXPECTED_RUN_ORDER:
        raise RuntimeError(
            f"run config order mismatch: expected={EXPECTED_RUN_ORDER}, actual={actual_order}"
        )
    if len(rows) != 14 or len(set(actual_order)) != 14:
        raise RuntimeError("run config rows must be exactly 14 unique ordered pairs")

    verified: list[dict[str, Any]] = []
    config_paths: set[Path] = set()
    for row, (route_id, replicate) in zip(rows, EXPECTED_RUN_ORDER, strict=True):
        if row.get("execution_status") != "STAGED_NOT_RUN":
            raise RuntimeError(f"unexpected CSV execution status: {route_id}/{replicate}")
        expected_config_path = (
            RUN_ROOT / route_id / replicate / "metadata" / "run_config.json"
        ).resolve()
        exact_path(row.get("config_path", ""), expected_config_path, "config_path")
        config_path = Path(row["config_path"]).resolve()
        if config_path in config_paths:
            raise RuntimeError(f"duplicate config path: {config_path}")
        config_paths.add(config_path)
        if not config_path.is_file():
            raise FileNotFoundError(config_path)
        config_hash = sha256_file(config_path)
        if config_hash != row.get("config_sha256"):
            raise RuntimeError(f"config hash mismatch in CSV: {config_path}")
        config = json.loads(config_path.read_text(encoding="utf-8"))
        if config.get("schema_version") != "BOARD21_STEP3_ROUTE_CONFIG_V1":
            raise RuntimeError(f"config schema mismatch: {config_path}")
        for field, expected in (
            ("route_id", route_id),
            ("replicate", replicate),
            ("route_label_cn", row.get("route_label_cn")),
            ("static_boundary", row.get("static_boundary")),
            ("execution_status", "STAGED_NOT_RUN"),
        ):
            if config.get(field) != expected:
                raise RuntimeError(
                    f"config/CSV mismatch {field}: {route_id}/{replicate}"
                )
        expected_output = (RUN_ROOT / route_id / replicate).resolve()
        expected_work = (WORK_ROOT / route_id / replicate / "work").resolve()
        expected_log = (LOG_ROOT / route_id / replicate).resolve()
        expected_metadata = expected_output / "metadata"
        expected_workspace = expected_output / "workspace"
        expected_scientific = expected_output / "scientific"
        exact_path(config.get("output_dir", ""), expected_output, "output_dir")
        exact_path(config.get("work_dir", ""), expected_work, "work_dir")
        exact_path(config.get("log_dir", ""), expected_log, "log_dir")
        upstream_name, candidate_name = ROUTE_FILES[route_id]
        expected_paths = {
            "config_hash_file": expected_config_path.with_suffix(".sha256"),
            "upstream_file": expected_work / upstream_name,
            "candidate_mlx": expected_work / candidate_name,
            "status_json": expected_metadata / "run_status.json",
            "variable_inventory_json": expected_metadata
            / "variable_inventory.json",
            "workspace_after_upstream": expected_workspace
            / "workspace_after_upstream.mat",
            "workspace_success": expected_workspace / "workspace_complete.mat",
            "workspace_failure": expected_workspace / "workspace_failure.mat",
            "scientific_mat": expected_scientific
            / "historical_energy_outputs.mat",
            "diary_file": expected_log / "matlab_diary.log",
            "error_report": expected_log / "error_report.txt",
            "matlab_command_txt": expected_log / "matlab_command.txt",
            "shell_log": expected_log / "shell_stdout_stderr.log",
            "matlab_stdout_log": expected_log / "matlab_stdout.log",
            "matlab_stderr_log": expected_log / "matlab_stderr.log",
            "process_exit_json": expected_metadata / "process_exit.json",
        }
        for field, expected_path in expected_paths.items():
            exact_path(config.get(field, ""), expected_path, field)
        if config.get("allowed_work_files") != [upstream_name, candidate_name]:
            raise RuntimeError(f"allowed work files mismatch: {config_path}")
        input_contracts = config.get("input_contracts")
        if not isinstance(input_contracts, list) or len(input_contracts) != 2:
            raise RuntimeError(f"input contract cardinality mismatch: {config_path}")
        for contract, kind, name, contract_order in zip(
            input_contracts,
            ("upstream", "candidate"),
            (upstream_name, candidate_name),
            (1, 2),
            strict=True,
        ):
            if (
                contract.get("kind") != kind
                or contract.get("name") != name
                or contract.get("order") != contract_order
            ):
                raise RuntimeError(f"input contract identity mismatch: {config_path}")
            exact_path(
                contract.get("staged_path", ""),
                expected_work / name,
                f"{kind}.staged_path",
            )
        exact_path(
            config.get("matlab_executable", ""),
            Path(r"D:\Downlad\Matlab\bin\matlab.exe"),
            "matlab_executable",
        )
        config_hash_text = expected_config_path.with_suffix(".sha256").read_text(
            encoding="utf-8"
        ).strip().upper()
        if config_hash_text != config_hash:
            raise RuntimeError(f"config sidecar hash mismatch: {config_path}")
        if config.get("instrument_sha256") != sealed_tools:
            raise RuntimeError(f"config tool seal mismatch: {config_path}")
        contracts = config.get("instrument_contracts")
        expected_contracts = [
            {
                "name": name,
                "path": str((CODE_ROOT / name).resolve()),
                "expected_sha256": sealed_tools[name],
            }
            for name in INSTRUMENT_FILES
        ]
        if contracts != expected_contracts:
            raise RuntimeError(f"config instrument contracts mismatch: {config_path}")
        verified.append(
            {
                "row": row,
                "config": config,
                "config_path": config_path,
                "config_sha256": config_hash,
            }
        )
    return verified


def main() -> int:
    if Path(sys.executable).resolve() != EXPECTED_PYTHON.resolve():
        raise RuntimeError(f"must use exact Python: {EXPECTED_PYTHON}; got {sys.executable}")
    if ORCHESTRATION_ROOT.exists():
        raise FileExistsError(f"refusing to overwrite: {ORCHESTRATION_ROOT}")

    sealed_tools = instrument_hashes()
    ORCHESTRATION_ROOT.mkdir(parents=True, exist_ok=False)
    capture_root = ORCHESTRATION_ROOT / "subprocess_captures"
    process_root = ORCHESTRATION_ROOT / "process_snapshots"
    process_query_capture_root = ORCHESTRATION_ROOT / "process_query_captures"
    capture_root.mkdir(exist_ok=False)
    process_root.mkdir(exist_ok=False)
    process_query_capture_root.mkdir(exist_ok=False)

    attempt_started_at = timestamp_now()
    records: list[dict[str, Any]] = []
    subprocess_records: list[dict[str, Any]] = []
    process_query_records: list[dict[str, Any]] = []
    dry_summary: dict[str, Any] = {}
    stage_summary: dict[str, Any] = {}
    initial_processes: list[dict[str, Any]] = []
    final_processes: list[dict[str, Any]] = []
    final_process_query_error = ""
    infrastructure_failure = False
    interruption_point = "INITIAL_PROCESS_QUERY"
    terminal_error: dict[str, Any] = {}

    try:
        initial_query = capture_process_query(
            "00__initial", process_query_capture_root
        )
        process_query_records.append(initial_query)
        if not initial_query["ok"] or not initial_query["capture_match"]:
            raise RuntimeError(f"initial process query failed: {initial_query}")
        initial_processes = initial_query["processes"]
        write_json_new(process_root / "00__initial.json", initial_processes)
        if initial_processes:
            raise RuntimeError(
                f"target processes exist before run: {initial_processes}"
            )

        interruption_point = "STAGER_DRY_RUN"
        dry = run_python(
            [str(STAGER), "--dry-run"], STAGER_TIMEOUT_SECONDS
        )
        write_bytes_new(capture_root / "stager_dry_run.stdout.log", dry["stdout"])
        write_bytes_new(capture_root / "stager_dry_run.stderr.log", dry["stderr"])
        dry_record = subprocess_record("stager_dry_run", dry)
        subprocess_records.append(dry_record)
        if (
            dry["timed_out"]
            or dry["returncode"] != 0
            or dry["stderr"]
            or dry_record["terminal_json_error"]
        ):
            raise RuntimeError(
                "stager dry-run failed: "
                + dry["stderr"].decode("utf-8", errors="replace")
                + f" timeout={dry['timeout_error']} "
                + f"terminal_json={dry_record['terminal_json_error']}"
            )
        dry_summary = dry_record["terminal_json"]
        if (
            dry_summary.get("route_count") != 7
            or dry_summary.get("run_count") != 14
            or dry_summary.get("source_reference_count") != 14
            or dry_summary.get("unique_source_count") != 12
            or dry_summary.get("protected_input_count") != 53
            or dry_summary.get("input_manifest_sha256")
            != INPUT_MANIFEST_SHA256
            or dry_summary.get("input_freeze_summary_sha256")
            != INPUT_FREEZE_SUMMARY_SHA256
            or dry_summary.get("instrument_sha256") != sealed_tools
        ):
            raise RuntimeError(f"unexpected dry-run summary: {dry_summary}")
        if instrument_hashes() != sealed_tools:
            raise RuntimeError("instrument drift after stager dry-run")

        interruption_point = "STAGER_ACTUAL"
        staged = run_python([str(STAGER)], STAGER_TIMEOUT_SECONDS)
        write_bytes_new(capture_root / "stager_actual.stdout.log", staged["stdout"])
        write_bytes_new(capture_root / "stager_actual.stderr.log", staged["stderr"])
        stage_record = subprocess_record("stager_actual", staged)
        subprocess_records.append(stage_record)
        if (
            staged["timed_out"]
            or staged["returncode"] != 0
            or staged["stderr"]
            or stage_record["terminal_json_error"]
        ):
            raise RuntimeError(
                "stager actual run failed: "
                + staged["stderr"].decode("utf-8", errors="replace")
                + f" timeout={staged['timeout_error']} "
                + f"terminal_json={stage_record['terminal_json_error']}"
            )
        stage_summary = stage_record["terminal_json"]
        if (
            stage_summary.get("status") != "STAGED_NOT_RUN"
            or stage_summary.get("route_count") != 7
            or stage_summary.get("run_count") != 14
            or stage_summary.get("staged_input_row_count") != 28
            or stage_summary.get("unique_source_count") != 12
            or stage_summary.get("protected_input_count") != 53
            or stage_summary.get("input_manifest_sha256")
            != INPUT_MANIFEST_SHA256
            or stage_summary.get("input_freeze_summary_sha256")
            != INPUT_FREEZE_SUMMARY_SHA256
            or stage_summary.get("matlab_executed") is not False
            or stage_summary.get("instrument_sha256") != sealed_tools
            or dry_summary.get("instrument_sha256")
            != stage_summary.get("instrument_sha256")
        ):
            raise RuntimeError(f"unexpected stage summary: {stage_summary}")
        if instrument_hashes() != sealed_tools:
            raise RuntimeError("instrument drift after actual staging")

        interruption_point = "CONFIG_SET_VALIDATION"
        with (STAGE_ROOT / "run_configs.csv").open(
            "r", encoding="utf-8-sig", newline=""
        ) as stream:
            reader = csv.DictReader(stream)
            expected_fields = [
                "route_id",
                "route_label_cn",
                "replicate",
                "config_path",
                "config_sha256",
                "static_boundary",
                "execution_status",
            ]
            if reader.fieldnames != expected_fields:
                raise RuntimeError(
                    f"run config CSV header mismatch: {reader.fieldnames}"
                )
            config_rows = list(reader)
        verified_configs = verify_config_rows(config_rows, sealed_tools)

        for order, item in enumerate(verified_configs, start=1):
            row = item["row"]
            route_id = row["route_id"]
            replicate = row["replicate"]
            stem = f"{order:02d}__{route_id}__{replicate}"
            interruption_point = f"{stem}__PRE_PROCESS_QUERY"
            before_query = capture_process_query(
                f"{stem}__before", process_query_capture_root
            )
            process_query_records.append(before_query)
            if not before_query["ok"] or not before_query["capture_match"]:
                raise RuntimeError(
                    f"process query failed before {route_id}/{replicate}: "
                    f"{before_query}"
                )
            before_processes = before_query["processes"]
            write_json_new(process_root / f"{stem}__before.json", before_processes)
            if before_processes:
                raise RuntimeError(
                    f"target processes exist before {route_id}/{replicate}: "
                    f"{before_processes}"
                )
            tools_before = instrument_hashes()
            if tools_before != sealed_tools:
                raise RuntimeError(
                    f"instrument drift before {route_id}/{replicate}"
                )
            config_path = item["config_path"]
            config_hash = sha256_file(config_path)
            if config_hash != item["config_sha256"]:
                raise RuntimeError(f"config drift before execution: {config_path}")

            interruption_point = f"{stem}__EXECUTOR"
            result = run_python(
                [
                    str(EXECUTOR),
                    str(config_path),
                    "--timeout-seconds",
                    str(MATLAB_TIMEOUT_SECONDS),
                ],
                EXECUTOR_WRAPPER_TIMEOUT_SECONDS,
            )
            stdout_path = capture_root / f"{stem}.stdout.log"
            stderr_path = capture_root / f"{stem}.stderr.log"
            route_subprocess_record = subprocess_record(stem, result)
            subprocess_records.append(route_subprocess_record)
            executor_capture_error = ""
            try:
                write_bytes_new(stdout_path, result["stdout"])
                write_bytes_new(stderr_path, result["stderr"])
            except Exception as error:
                executor_capture_error = f"{type(error).__name__}: {error}"
            executor_summary: dict[str, Any] = {}
            parse_error = route_subprocess_record["terminal_json_error"]
            if not parse_error:
                executor_summary = route_subprocess_record["terminal_json"]

            process_exit_path = Path(item["config"]["process_exit_json"])
            process_exit_record: dict[str, Any] = {}
            process_exit_read_error = ""
            try:
                raw_exit = json.loads(process_exit_path.read_text(encoding="utf-8"))
                if not isinstance(raw_exit, dict):
                    raise TypeError("process_exit.json must be an object")
                process_exit_record = raw_exit
            except Exception as error:
                process_exit_read_error = f"{type(error).__name__}: {error}"
            executor_terminal_json_match = bool(
                not parse_error
                and not process_exit_read_error
                and executor_summary == process_exit_record
            )
            execution_token = executor_summary.get("execution_token")
            execution_token_sha256 = executor_summary.get(
                "execution_token_sha256"
            )
            launcher_pid = executor_summary.get("launcher_pid")
            matlab_pid = executor_summary.get("matlab_pid")
            execution_identity_contract_pass = bool(
                executor_summary.get("schema_version")
                == "BOARD21_STEP3_PROCESS_EXIT_V2"
                and "pid" not in executor_summary
                and positive_integer(launcher_pid)
                and positive_integer(matlab_pid)
                and uppercase_hex_64(execution_token)
                and execution_token_sha256
                == sha256_bytes(execution_token.encode("ascii"))
                and executor_summary.get("execution_token_match") is True
            )

            interruption_point = f"{stem}__POST_PROCESS_QUERY"
            tools_after: dict[str, str] = {}
            post_tool_error = ""
            try:
                tools_after = instrument_hashes()
            except Exception as error:
                post_tool_error = f"{type(error).__name__}: {error}"
            after_processes: list[dict[str, Any]] = []
            post_process_query_error = ""
            try:
                after_query = capture_process_query(
                    f"{stem}__after", process_query_capture_root
                )
                process_query_records.append(after_query)
                if not after_query["ok"] or not after_query["capture_match"]:
                    raise RuntimeError(f"process query failed: {after_query}")
                after_processes = after_query["processes"]
                write_json_new(
                    process_root / f"{stem}__after.json", after_processes
                )
            except Exception as error:
                post_process_query_error = f"{type(error).__name__}: {error}"
                try:
                    write_json_new(
                        process_root / f"{stem}__after_query_failure.json",
                        {"error": post_process_query_error},
                    )
                except Exception as snapshot_write_error:
                    post_process_query_error += (
                        "; snapshot_write="
                        f"{type(snapshot_write_error).__name__}: "
                        f"{snapshot_write_error}"
                    )
            evidence_ok = (
                not executor_capture_error
                and not result["timed_out"]
                and result["returncode"] == 0
                and result["stderr"] == b""
                and not parse_error
                and not process_exit_read_error
                and executor_terminal_json_match
                and executor_summary.get("route_id") == route_id
                and executor_summary.get("replicate") == replicate
                and executor_summary.get("timeout_seconds")
                == MATLAB_TIMEOUT_SECONDS
                and executor_summary.get("timed_out") is False
                and executor_summary.get("status_contract_pass") is True
                and executor_summary.get("artifact_exclusivity_match") is True
                and executor_summary.get("all_required_artifacts_sealed") is True
                and executor_summary.get("runtime_log_hashes_match") is True
                and bool(executor_summary.get("evidence_capture_ok"))
                and execution_identity_contract_pass
            )
            tool_seal_match = not post_tool_error and tools_after == sealed_tools
            record = {
                "order": order,
                "route_id": route_id,
                "route_label_cn": row["route_label_cn"],
                "replicate": replicate,
                "config_path": str(config_path),
                "config_sha256": config_hash,
                "executor_command": result["command"],
                "executor_cwd": result["cwd"],
                "executor_timeout_seconds": result["timeout_seconds"],
                "executor_timed_out": result["timed_out"],
                "executor_timeout_error": result["timeout_error"],
                "executor_returncode": result["returncode"],
                "executor_stdout_sha256": sha256_bytes(result["stdout"]),
                "executor_stderr_sha256": sha256_bytes(result["stderr"]),
                "executor_stdout_path": str(stdout_path),
                "executor_stderr_path": str(stderr_path),
                "executor_capture_error": executor_capture_error,
                "executor_parse_error": parse_error,
                "process_exit_json_path": str(process_exit_path),
                "process_exit_json_sha256": (
                    sha256_file(process_exit_path)
                    if process_exit_path.is_file()
                    else ""
                ),
                "process_exit_read_error": process_exit_read_error,
                "executor_terminal_json_match": executor_terminal_json_match,
                "process_exit_schema_version": executor_summary.get(
                    "schema_version"
                ),
                "launcher_pid": launcher_pid,
                "matlab_pid": matlab_pid,
                "execution_token": execution_token,
                "execution_token_sha256": execution_token_sha256,
                "execution_token_match": executor_summary.get(
                    "execution_token_match"
                ),
                "execution_identity_contract_pass": (
                    execution_identity_contract_pass
                ),
                "executor_terminal_json_line_sha256": route_subprocess_record[
                    "terminal_json_line_sha256"
                ],
                "executor_terminal_json_utf8_sha256": route_subprocess_record[
                    "terminal_json_utf8_sha256"
                ],
                "executor_internal_timeout_seconds": executor_summary.get(
                    "timeout_seconds"
                ),
                "executor_internal_timed_out": executor_summary.get("timed_out"),
                "executor_status_contract_pass": executor_summary.get(
                    "status_contract_pass"
                ),
                "executor_artifact_exclusivity_match": executor_summary.get(
                    "artifact_exclusivity_match"
                ),
                "executor_all_required_artifacts_sealed": executor_summary.get(
                    "all_required_artifacts_sealed"
                ),
                "executor_runtime_log_hashes_match": executor_summary.get(
                    "runtime_log_hashes_match"
                ),
                "matlab_returncode": executor_summary.get("returncode"),
                "orchestration_status": executor_summary.get(
                    "orchestration_status", "MISSING"
                ),
                "evidence_capture_ok": evidence_ok,
                "instrument_sha256_before": tools_before,
                "instrument_sha256_after": tools_after,
                "instrument_seal_match": tool_seal_match,
                "post_instrument_error": post_tool_error,
                "target_processes_before": before_processes,
                "target_processes_after": after_processes,
                "post_process_query_error": post_process_query_error,
            }
            records.append(record)
            if (
                result["timed_out"]
                or result["returncode"] != 0
                or bool(result["stderr"])
                or not evidence_ok
                or not tool_seal_match
                or after_processes
                or bool(post_process_query_error)
            ):
                infrastructure_failure = True
                interruption_point = f"{stem}__INFRASTRUCTURE_FAILURE"
                break
        else:
            interruption_point = "FINAL_PROCESS_QUERY"
    except Exception as error:
        infrastructure_failure = True
        terminal_error = {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        }
    finally:
        try:
            final_query = capture_process_query(
                "99__final", process_query_capture_root
            )
            process_query_records.append(final_query)
            if not final_query["ok"] or not final_query["capture_match"]:
                raise RuntimeError(f"final process query failed: {final_query}")
            final_processes = final_query["processes"]
            write_json_new(process_root / "99__final.json", final_processes)
            if final_processes:
                infrastructure_failure = True
        except Exception as error:
            infrastructure_failure = True
            final_process_query_error = f"{type(error).__name__}: {error}"
            try:
                write_json_new(
                    process_root / "99__final_query_failure.json",
                    {"error": final_process_query_error},
                )
            except Exception:
                pass

    executed_pairs = [(row["route_id"], row["replicate"]) for row in records]
    unstarted_runs = [
        {"route_id": route_id, "replicate": replicate}
        for route_id, replicate in EXPECTED_RUN_ORDER
        if (route_id, replicate) not in executed_pairs
    ]
    subprocess_contract_pass = bool(
        len(subprocess_records) == 16
        and all(
            item.get("timed_out") is False
            and item.get("timeout_error") == ""
            and item.get("environment_overrides")
            == PYTHON_ENVIRONMENT_OVERRIDES
            and item.get("returncode") == 0
            and item.get("stderr_size_bytes") == 0
            and item.get("terminal_json_error") == ""
            and isinstance(item.get("terminal_json"), dict)
            and bool(item.get("terminal_json"))
            for item in subprocess_records
        )
    )
    process_query_contract_pass = bool(
        len(process_query_records) == 30
        and all(
            item.get("schema_version") == "BOARD21_STEP3_PROCESS_QUERY_V1"
            and item.get("timeout_seconds") == PROCESS_QUERY_TIMEOUT_SECONDS
            and item.get("timed_out") is False
            and item.get("timeout_error") == ""
            and item.get("returncode") == 0
            and item.get("stderr_size_bytes") == 0
            and item.get("stderr_text") == ""
            and item.get("parse_error") == ""
            and item.get("capture_error") == ""
            and item.get("capture_match") is True
            and process_query_capture_matches(
                item, process_query_capture_root
            )
            and item.get("ok") is True
            for item in process_query_records
        )
    )
    route_contract_pass = bool(
        len(records) == 14
        and all(
            item.get("executor_timeout_seconds")
            == EXECUTOR_WRAPPER_TIMEOUT_SECONDS
            and item.get("executor_timed_out") is False
            and item.get("executor_timeout_error") == ""
            and item.get("executor_returncode") == 0
            and item.get("executor_capture_error") == ""
            and item.get("executor_parse_error") == ""
            and item.get("process_exit_read_error") == ""
            and item.get("executor_terminal_json_match") is True
            and item.get("executor_internal_timeout_seconds")
            == MATLAB_TIMEOUT_SECONDS
            and item.get("executor_internal_timed_out") is False
            and item.get("executor_status_contract_pass") is True
            and item.get("executor_artifact_exclusivity_match") is True
            and item.get("executor_all_required_artifacts_sealed") is True
            and item.get("executor_runtime_log_hashes_match") is True
            and item.get("process_exit_schema_version")
            == "BOARD21_STEP3_PROCESS_EXIT_V2"
            and positive_integer(item.get("launcher_pid"))
            and positive_integer(item.get("matlab_pid"))
            and uppercase_hex_64(item.get("execution_token"))
            and item.get("execution_token_sha256")
            == sha256_bytes(item["execution_token"].encode("ascii"))
            and item.get("execution_token_match") is True
            and item.get("execution_identity_contract_pass") is True
            and item.get("evidence_capture_ok") is True
            and item.get("instrument_seal_match") is True
            and item.get("target_processes_before") == []
            and item.get("target_processes_after") == []
            and item.get("post_process_query_error") == ""
            for item in records
        )
    )
    execution_tokens = [
        row.get("execution_token")
        for row in records
        if uppercase_hex_64(row.get("execution_token"))
    ]
    unique_execution_token_count = len(set(execution_tokens))
    execution_identity_contract_pass = bool(
        len(records) == 14
        and len(execution_tokens) == 14
        and unique_execution_token_count == 14
        and all(
            row.get("execution_identity_contract_pass") is True
            for row in records
        )
    )
    author_execution_success_count = sum(
        row["orchestration_status"] == "SUCCESS_EVIDENCE_CAPTURED"
        for row in records
    )
    author_execution_failure_count = sum(
        row["orchestration_status"] == "AUTHOR_FAILURE_EVIDENCE_CAPTURED"
        for row in records
    )
    author_execution_count_contract_pass = bool(
        len(records) == 14
        and author_execution_success_count + author_execution_failure_count == 14
    )
    status = (
        "PASS"
        if not infrastructure_failure
        and not terminal_error
        and len(records) == 14
        and subprocess_contract_pass
        and process_query_contract_pass
        and route_contract_pass
        and execution_identity_contract_pass
        and author_execution_count_contract_pass
        and not final_processes
        and not final_process_query_error
        else "FAIL"
    )
    summary = {
        "schema_version": "BOARD21_STEP3_ORCHESTRATION_SUMMARY_V3",
        "attempt_started_at": attempt_started_at,
        "completed_at": timestamp_now(),
        "project_root": str(PROJECT_ROOT),
        "expected_python": str(EXPECTED_PYTHON),
        "sealed_instrument_sha256": sealed_tools,
        "expected_run_order": [
            {"order": order, "route_id": route_id, "replicate": replicate}
            for order, (route_id, replicate) in enumerate(EXPECTED_RUN_ORDER, start=1)
        ],
        "started_with_target_process_count": len(initial_processes),
        "initial_target_processes": initial_processes,
        "dry_run_summary": dry_summary,
        "stage_summary": stage_summary,
        "subprocess_records": subprocess_records,
        "subprocess_contract_pass": subprocess_contract_pass,
        "process_query_records": process_query_records,
        "process_query_capture_root": str(process_query_capture_root.resolve()),
        "process_query_contract_pass": process_query_contract_pass,
        "route_contract_pass": route_contract_pass,
        "execution_identity_contract_pass": execution_identity_contract_pass,
        "unique_execution_token_count": unique_execution_token_count,
        "timeout_contract_seconds": {
            "stager_python": STAGER_TIMEOUT_SECONDS,
            "executor_python_wrapper": EXECUTOR_WRAPPER_TIMEOUT_SECONDS,
            "matlab_inside_executor": MATLAB_TIMEOUT_SECONDS,
            "powershell_process_query": PROCESS_QUERY_TIMEOUT_SECONDS,
        },
        "expected_run_count": 14,
        "executed_run_count": len(records),
        "route_process_records": records,
        "unstarted_runs": unstarted_runs,
        "interruption_point": interruption_point,
        "terminal_error": terminal_error,
        "infrastructure_failure": infrastructure_failure,
        "final_target_processes": final_processes,
        "final_target_process_count": len(final_processes),
        "final_process_query_error": final_process_query_error,
        "matlab_process_count": sum(
            str(item.get("Name", "")).casefold() == "matlab.exe"
            for item in final_processes
        ),
        "author_execution_success_count": author_execution_success_count,
        "author_execution_failure_count": author_execution_failure_count,
        "author_execution_count_contract_pass": (
            author_execution_count_contract_pass
        ),
        "status": status,
    }
    write_json_new(ORCHESTRATION_ROOT / "run_all_summary.json", summary)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if status == "PASS" else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        failure = {
            "schema_version": "BOARD21_STEP3_RUN_ALL_TERMINAL_FAILURE_V1",
            "status": "FAIL",
            "infrastructure_failure": True,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        print(
            f"BOARD21_STEP3_ALL_FAIL: {type(error).__name__}: {error}",
            file=sys.stderr,
        )
        raise

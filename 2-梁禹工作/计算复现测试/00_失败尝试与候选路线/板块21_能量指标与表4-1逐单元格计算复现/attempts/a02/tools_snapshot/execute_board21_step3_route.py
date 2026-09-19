from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import secrets
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
CODE_ROOT = SCRIPT.parent
EXPECTED_MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
EXPECTED_MATLAB_RELEASE = "2025b"
REQUIRED_SCIENTIFIC_VARIABLES = {
    "E_total",
    "E_total_guyan",
    "E_total_cb",
    "energy_sum_orig",
    "energy_sum_guyan",
    "energy_sum_cb",
    "total_increase_guyan",
    "total_increase_cb",
}
ALLOWED_SCIENTIFIC_VARIABLES = {
    "E_total", "E_total_guyan", "E_total_cb", "E", "Gamma", "GammaSq",
    "participation_ratio", "energy_sum_orig", "energy_sum_guyan",
    "energy_sum_cb", "total_increase_guyan", "total_increase_cb", "KRrt",
    "MRrt", "CRrt", "KPrt", "MPrt", "CPrt", "T", "KRren", "MRren",
    "CRren", "T_cb", "KR_cb", "MR_cb", "CR_cb", "TP", "KPren",
    "MPren", "CPren", "TP_cb", "KP_cb", "MP_cb", "CP_cb", "index1",
    "index2", "index3", "index4", "order", "d", "d2", "r", "r0",
}


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


def write_text_new(path: Path, value: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(value)


def artifact_record(name: str, path: Path, required: bool) -> dict[str, Any]:
    exists = path.is_file()
    return {
        "name": name,
        "path": str(path.resolve()),
        "required": required,
        "exists": exists,
        "size_bytes": path.stat().st_size if exists else -1,
        "sha256": sha256_file(path) if exists else "",
    }


def string_list(value: Any) -> list[str]:
    if value is None or value == []:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return value
    raise TypeError("expected a string or string array")


def struct_list(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None or value == []:
        return []
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list) and all(isinstance(item, dict) for item in value):
        return value
    raise TypeError(f"{label} must be a struct or struct array")


def same_path(actual: Any, expected: Path) -> bool:
    try:
        candidate = Path(str(actual))
        return candidate.is_absolute() and candidate.resolve() == expected.resolve()
    except (OSError, RuntimeError, TypeError, ValueError):
        return False


def finite_scalar(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def positive_integer(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def expected_input_hash_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    layers = (
        ("author_original", "author_original_path"),
        ("step1_frozen", "frozen_path"),
        ("run_copy", "staged_path"),
    )
    for contract in config["input_contracts"]:
        expected_hash = str(contract["expected_sha256"]).upper()
        for layer, field in layers:
            result.append(
                {
                    "layer": layer,
                    "kind": contract["kind"],
                    "path": str(Path(contract[field]).resolve()),
                    "expected_sha256": expected_hash,
                    "actual_sha256": expected_hash,
                    "match": True,
                }
            )
    return result


def expected_instrument_hash_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "layer": "instrument",
            "kind": contract["name"],
            "path": str(Path(contract["path"]).resolve()),
            "expected_sha256": str(contract["expected_sha256"]).upper(),
            "actual_sha256": str(contract["expected_sha256"]).upper(),
            "match": True,
        }
        for contract in config["instrument_contracts"]
    ]


def expected_work_file_records(config: dict[str, Any]) -> list[dict[str, Any]]:
    records = []
    for contract in config["input_contracts"]:
        path = Path(contract["staged_path"])
        records.append(
            {
                "name": path.name,
                "path": str(path.resolve()),
                "bytes": path.stat().st_size,
                "sha256": str(contract["expected_sha256"]).upper(),
            }
        )
    return sorted(records, key=lambda item: item["name"])


def status_contract_audit(
    status: dict[str, Any] | None,
    config: dict[str, Any],
    config_path: Path,
    execution_token: str,
    runner_success: bool,
    runner_author_failure: bool,
) -> tuple[dict[str, bool], str, list[str]]:
    checks: dict[str, bool] = {}
    errors: list[str] = []
    scientific_variables: list[str] = []
    if not isinstance(status, dict):
        return {"status_is_object": False}, "status is not a JSON object", []

    try:
        scientific_variables = string_list(
            status.get("available_scientific_variables")
        )
        scientific = status.get("scientific")
        if not isinstance(scientific, dict):
            raise TypeError("status.scientific must be an object")
        scientific_record_names = string_list(scientific.get("available_variables"))
        checks["scientific_names_unique"] = (
            len(scientific_variables) == len(set(scientific_variables))
        )
        checks["scientific_names_allowed"] = set(scientific_variables).issubset(
            ALLOWED_SCIENTIFIC_VARIABLES
        )
        checks["scientific_names_cross_field_match"] = (
            scientific_variables == scientific_record_names
        )
        if runner_success:
            checks["success_required_scientific_names_present"] = (
                REQUIRED_SCIENTIFIC_VARIABLES.issubset(scientific_variables)
            )
            checks["success_scientific_contract"] = bool(
                scientific.get("required_present") is True
                and scientific.get("missing_required") == []
                and scientific.get("lengths_match") is True
                and scientific.get("all_finite") is True
                and scientific.get("energy_lengths")
                == config["expected_energy_lengths"]
                and scientific.get("expected_energy_lengths")
                == config["expected_energy_lengths"]
                and scientific.get("embedded_historical_percent")
                == config["embedded_historical_percent"]
                and all(
                    finite_scalar(scientific.get(name))
                    for name in (
                        "energy_sum_orig",
                        "energy_sum_guyan",
                        "energy_sum_cb",
                        "total_increase_guyan",
                        "total_increase_cb",
                    )
                )
            )
    except Exception as error:
        errors.append(f"scientific_contract:{type(error).__name__}: {error}")
        checks["scientific_contract_parse"] = False

    expected_config_hash = sha256_file(config_path)
    expected_config_contract = {
        "hash_file": str(Path(config["config_hash_file"]).resolve()),
        "expected_sha256": expected_config_hash,
        "actual_sha256": expected_config_hash,
        "match": True,
    }
    checks["identity"] = bool(
        status.get("schema_version") == "BOARD21_STEP3_ROUTE_STATUS_V2"
        and status.get("route_id") == config["route_id"]
        and status.get("route_label_cn") == config["route_label_cn"]
        and status.get("replicate") == config["replicate"]
        and status.get("division_identity") == config["division_identity"]
        and status.get("parameter_family") == config["parameter_family"]
        and status.get("static_boundary") == config["static_boundary"]
        and same_path(status.get("config_path"), config_path)
    )
    checks["config_seal"] = status.get("config_contract") == expected_config_contract
    checks["capture_errors_empty"] = status.get("capture_errors") == []

    environment = status.get("environment")
    checks["environment"] = bool(
        isinstance(environment, dict)
        and same_path(environment.get("pwd"), Path(config["work_dir"]))
        and same_path(environment.get("matlab_root"), EXPECTED_MATLAB.parent.parent)
        and environment.get("matlab_release") == EXPECTED_MATLAB_RELEASE
        and isinstance(environment.get("matlab_version"), str)
        and bool(environment.get("matlab_version"))
        and isinstance(environment.get("computer"), str)
        and bool(environment.get("computer"))
        and positive_integer(environment.get("pid"))
    )
    checks["execution_token"] = bool(
        isinstance(environment, dict)
        and environment.get("execution_token") == execution_token
    )

    try:
        expected_input = expected_input_hash_records(config)
        checks["input_hashes_before"] = (
            struct_list(status.get("input_hashes_before"), "input_hashes_before")
            == expected_input
        )
        checks["input_hashes_after"] = (
            struct_list(status.get("input_hashes_after"), "input_hashes_after")
            == expected_input
        )
        checks["instrument_hashes"] = (
            struct_list(status.get("instrument_contracts"), "instrument_contracts")
            == expected_instrument_hash_records(config)
        )
        expected_which = [
            {
                "name": Path(contract["staged_path"]).name,
                "expected": str(Path(contract["staged_path"]).resolve()),
                "actual": str(Path(contract["staged_path"]).resolve()),
                "match": True,
            }
            for contract in config["input_contracts"]
        ]
        checks["which_paths"] = (
            struct_list(status.get("which_contracts"), "which_contracts")
            == expected_which
        )
        expected_work = expected_work_file_records(config)
        checks["work_files_before"] = (
            sorted(
                struct_list(status.get("work_files_before"), "work_files_before"),
                key=lambda item: item.get("name", ""),
            )
            == expected_work
        )
        checks["work_files_after"] = (
            sorted(
                struct_list(status.get("work_files_after"), "work_files_after"),
                key=lambda item: item.get("name", ""),
            )
            == expected_work
        )
    except Exception as error:
        errors.append(f"runtime_seals:{type(error).__name__}: {error}")
        checks["runtime_seal_parse"] = False

    error_record = status.get("error")
    if runner_success:
        checks["success_terminal"] = bool(
            status.get("execution_status") == "EXECUTION_SUCCESS"
            and status.get("evidence_status") == "PASS"
            and status.get("final_status") == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
            and status.get("process_exit_semantics") == "ZERO"
            and status.get("error_origin") == "NONE"
            and status.get("failed_stage") == ""
            and status.get("failed_file") == ""
            and status.get("current_stage") == "COMPLETE"
            and status.get("current_file") == ""
            and isinstance(error_record, dict)
            and error_record.get("identifier") == ""
            and error_record.get("message") == ""
            and error_record.get("stack") == []
        )
    elif runner_author_failure:
        failed_stage = status.get("failed_stage")
        expected_failed_file = (
            config["upstream_file"]
            if failed_stage == "UPSTREAM_ORIGINAL"
            else config["candidate_mlx"]
        )
        error_stack = (
            error_record.get("stack") if isinstance(error_record, dict) else None
        )
        if isinstance(error_stack, dict):
            error_stack = [error_stack]
        checks["author_failure_terminal"] = bool(
            status.get("execution_status") == "EXECUTION_FAIL"
            and status.get("evidence_status") == "PASS_FAILURE_EVIDENCE"
            and status.get("final_status") == "EXECUTION_FAIL_AUTHOR_ERROR_CAPTURED"
            and status.get("process_exit_semantics") == "NONZERO_RETHROW"
            and status.get("error_origin") == "AUTHOR_CALL"
            and failed_stage in {"UPSTREAM_ORIGINAL", "CANDIDATE_ORIGINAL_MLX"}
            and same_path(status.get("failed_file"), Path(expected_failed_file))
            and status.get("current_stage") == "FAILED_COMPLETE"
            and status.get("current_file") == ""
            and isinstance(error_record, dict)
            and bool(error_record.get("identifier"))
            and bool(error_record.get("message"))
            and isinstance(error_stack, list)
            and len(error_stack) > 0
        )
    else:
        checks["recognized_terminal_outcome"] = False

    return checks, "; ".join(errors), scientific_variables


def matlab_quote(value: str) -> str:
    return value.replace("'", "''")


def load_and_verify_config(config_path: Path) -> dict[str, Any]:
    if not config_path.is_file():
        raise FileNotFoundError(config_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    if config.get("schema_version") != "BOARD21_STEP3_ROUTE_CONFIG_V1":
        raise RuntimeError("step3 config schema mismatch")
    hash_file = Path(config["config_hash_file"])
    expected = hash_file.read_text(encoding="utf-8").strip().upper()
    actual = sha256_file(config_path)
    if expected != actual:
        raise RuntimeError(f"config hash mismatch: expected={expected}, actual={actual}")
    if Path(config["matlab_executable"]).resolve() != EXPECTED_MATLAB.resolve():
        raise RuntimeError(f"unexpected MATLAB executable: {config['matlab_executable']}")
    if not EXPECTED_MATLAB.is_file():
        raise FileNotFoundError(EXPECTED_MATLAB)
    instrument_contracts = config.get("instrument_contracts")
    if not isinstance(instrument_contracts, list) or not instrument_contracts:
        raise RuntimeError("instrument contract set is empty or malformed")
    instrument_names = [contract.get("name") for contract in instrument_contracts]
    if len(instrument_names) != len(set(instrument_names)):
        raise RuntimeError("instrument contract names are not unique")
    expected_instrument_map = {
        contract["name"]: str(contract["expected_sha256"]).upper()
        for contract in instrument_contracts
    }
    if config.get("instrument_sha256") != expected_instrument_map:
        raise RuntimeError("instrument hash map/contracts mismatch")
    for contract in instrument_contracts:
        path = Path(contract["path"])
        actual_hash = sha256_file(path)
        if actual_hash != str(contract["expected_sha256"]).upper():
            raise RuntimeError(f"instrument hash mismatch: {path}")

    input_contracts = config.get("input_contracts")
    if not isinstance(input_contracts, list) or len(input_contracts) != 2:
        raise RuntimeError("input contracts must contain exactly two records")
    if [contract.get("kind") for contract in input_contracts] != [
        "upstream",
        "candidate",
    ] or [contract.get("order") for contract in input_contracts] != [1, 2]:
        raise RuntimeError("input contract kind/order mismatch")
    if config.get("allowed_work_files") != [
        contract.get("name") for contract in input_contracts
    ]:
        raise RuntimeError("allowed work files/input contracts mismatch")
    if not same_path(config.get("upstream_file"), Path(input_contracts[0]["staged_path"])):
        raise RuntimeError("upstream path/input contract mismatch")
    if not same_path(config.get("candidate_mlx"), Path(input_contracts[1]["staged_path"])):
        raise RuntimeError("candidate path/input contract mismatch")
    for contract in input_contracts:
        expected_hash = str(contract["expected_sha256"]).upper()
        if str(contract.get("copied_sha256", "")).upper() != expected_hash:
            raise RuntimeError("input copied/expected hash mismatch")
        for field in ("author_original_path", "frozen_path", "staged_path"):
            path = Path(contract[field])
            if not path.is_file() or sha256_file(path) != expected_hash:
                raise RuntimeError(f"three-layer input mismatch: {field}: {path}")
        staged_path = Path(contract["staged_path"])
        if contract.get("size_bytes") != staged_path.stat().st_size:
            raise RuntimeError(f"input size mismatch: {staged_path}")
    return config


def execute(config_path: Path, timeout_seconds: int) -> dict[str, Any]:
    config = load_and_verify_config(config_path)
    command_path = Path(config["matlab_command_txt"])
    shell_log_path = Path(config["shell_log"])
    stdout_log_path = Path(config["matlab_stdout_log"])
    stderr_log_path = Path(config["matlab_stderr_log"])
    exit_path = Path(config["process_exit_json"])
    status_path = Path(config["status_json"])
    for path in (
        command_path,
        shell_log_path,
        stdout_log_path,
        stderr_log_path,
        exit_path,
        status_path,
    ):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite route output: {path}")

    expression = (
        f"addpath('{matlab_quote(str(CODE_ROOT))}'); "
        f"run_one_board21_energy_route('{matlab_quote(str(config_path.resolve()))}');"
    )
    command = [str(EXPECTED_MATLAB), "-batch", expression]
    display_command = subprocess.list2cmdline(command)
    write_text_new(command_path, display_command + "\n")
    execution_token = secrets.token_hex(32).upper()
    if len(execution_token) != 64 or any(
        character not in "0123456789ABCDEF" for character in execution_token
    ):
        raise RuntimeError("generated execution token is not uppercase 64-hex")
    matlab_environment = os.environ.copy()
    matlab_environment["BOARD21_STEP3_EXECUTION_TOKEN"] = execution_token

    started = datetime.now().astimezone()
    started_monotonic = time.monotonic()
    process = subprocess.Popen(
        command,
        cwd=config["work_dir"],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=matlab_environment,
    )
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        timed_out = True
        process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate(timeout=20)
    finished = datetime.now().astimezone()
    duration = time.monotonic() - started_monotonic

    log_payload = (
        b"===== STDOUT =====\n"
        + stdout
        + b"\n===== STDERR =====\n"
        + stderr
        + b"\n"
    )
    with stdout_log_path.open("xb") as stream:
        stream.write(stdout)
    with stderr_log_path.open("xb") as stream:
        stream.write(stderr)
    with shell_log_path.open("xb") as stream:
        stream.write(log_payload)

    status: dict[str, Any] | None = None
    status_error = ""
    if status_path.is_file():
        try:
            status = json.loads(status_path.read_text(encoding="utf-8"))
        except Exception as error:  # evidence, not a swallowed success
            status_error = f"{type(error).__name__}: {error}"
    else:
        status_error = "run_status.json missing"

    status_environment = (
        status.get("environment", {}) if isinstance(status, dict) else {}
    )
    if not isinstance(status_environment, dict):
        status_environment = {}
    matlab_pid = status_environment.get("pid")
    execution_token_match = (
        status_environment.get("execution_token") == execution_token
    )

    error_record = status.get("error", {}) if status else {}
    error_stack = error_record.get("stack", []) if isinstance(error_record, dict) else []
    if isinstance(error_stack, dict):
        error_stack = [error_stack]
    runner_success = bool(
        status
        and status.get("execution_status") == "EXECUTION_SUCCESS"
        and status.get("evidence_status") == "PASS"
        and status.get("final_status") == "SUCCESS_AUTHOR_ROUTE_REPEAT_PENDING"
        and status.get("error_origin") == "NONE"
    )
    runner_author_failure = bool(
        status
        and status.get("execution_status") == "EXECUTION_FAIL"
        and status.get("evidence_status") == "PASS_FAILURE_EVIDENCE"
        and status.get("final_status") == "EXECUTION_FAIL_AUTHOR_ERROR_CAPTURED"
        and status.get("error_origin") == "AUTHOR_CALL"
        and status.get("failed_stage")
        in {"UPSTREAM_ORIGINAL", "CANDIDATE_ORIGINAL_MLX"}
        and isinstance(error_record, dict)
        and bool(error_record.get("identifier"))
        and bool(error_record.get("message"))
        and isinstance(error_stack, list)
        and len(error_stack) > 0
    )
    failed_stage = str(status.get("failed_stage", "")) if status else ""
    status_contract_checks, status_contract_error, scientific_variables = (
        status_contract_audit(
            status,
            config,
            config_path,
            execution_token,
            runner_success,
            runner_author_failure,
        )
    )
    status_contract_pass = bool(
        status_contract_checks
        and all(status_contract_checks.values())
        and not status_contract_error
    )
    artifact_paths = {
        "config_json": config_path,
        "config_hash_file": Path(config["config_hash_file"]),
        "run_status_json": status_path,
        "variable_inventory_json": Path(config["variable_inventory_json"]),
        "workspace_after_upstream": Path(config["workspace_after_upstream"]),
        "workspace_success": Path(config["workspace_success"]),
        "workspace_failure": Path(config["workspace_failure"]),
        "scientific_mat": Path(config["scientific_mat"]),
        "matlab_diary": Path(config["diary_file"]),
        "error_report": Path(config["error_report"]),
        "matlab_command": command_path,
        "matlab_stdout": stdout_log_path,
        "matlab_stderr": stderr_log_path,
        "shell_combined_log": shell_log_path,
    }
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
    if runner_author_failure and failed_stage == "CANDIDATE_ORIGINAL_MLX":
        failure_required.add("workspace_after_upstream")
    expected_exists = {
        name: bool(
            name in always_required
            or (name == "scientific_mat" and bool(scientific_variables))
            or (runner_success and name in success_required)
            or (runner_author_failure and name in failure_required)
        )
        for name in artifact_paths
    }
    artifact_seal = [
        artifact_record(
            name,
            path,
            expected_exists[name],
        )
        for name, path in artifact_paths.items()
    ]
    artifact_exclusivity_match = all(
        item["exists"] is expected_exists[item["name"]]
        for item in artifact_seal
    )
    all_required_artifacts_sealed = artifact_exclusivity_match and all(
        (not item["required"])
        or (
            item["exists"]
            and item["size_bytes"] >= 0
            and bool(item["sha256"])
            and (item["name"] == "matlab_stderr" or item["size_bytes"] > 0)
        )
        for item in artifact_seal
    )
    seal_by_name = {item["name"]: item for item in artifact_seal}
    runtime_log_hashes_match = bool(
        seal_by_name["matlab_stdout"]["size_bytes"] == len(stdout)
        and seal_by_name["matlab_stdout"]["sha256"] == sha256_bytes(stdout)
        and seal_by_name["matlab_stderr"]["size_bytes"] == len(stderr)
        and seal_by_name["matlab_stderr"]["sha256"] == sha256_bytes(stderr)
        and seal_by_name["shell_combined_log"]["size_bytes"] == len(log_payload)
        and seal_by_name["shell_combined_log"]["sha256"]
        == sha256_bytes(log_payload)
    )
    all_required_artifacts_sealed &= runtime_log_hashes_match

    process_record = {
        "schema_version": "BOARD21_STEP3_PROCESS_EXIT_V2",
        "route_id": config["route_id"],
        "replicate": config["replicate"],
        "command": command,
        "display_command": display_command,
        "cwd": config["work_dir"],
        "launcher_pid": process.pid,
        "matlab_pid": matlab_pid,
        "execution_token": execution_token,
        "execution_token_sha256": sha256_bytes(execution_token.encode("ascii")),
        "execution_token_match": execution_token_match,
        "started_at": started.isoformat(),
        "finished_at": finished.isoformat(),
        "duration_seconds": duration,
        "timeout_seconds": timeout_seconds,
        "timed_out": timed_out,
        "returncode": process.returncode,
        "stdout_size_bytes": len(stdout),
        "stderr_size_bytes": len(stderr),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_sha256": sha256_bytes(stderr),
        "combined_log_sha256": sha256_bytes(log_payload),
        "matlab_stdout_path": str(stdout_log_path.resolve()),
        "matlab_stderr_path": str(stderr_log_path.resolve()),
        "combined_log_path": str(shell_log_path.resolve()),
        "status_json_exists": status_path.is_file(),
        "status_json_sha256": sha256_file(status_path) if status_path.is_file() else "",
        "status_read_error": status_error,
        "runner_execution_status": status.get("execution_status", "") if status else "",
        "runner_evidence_status": status.get("evidence_status", "") if status else "",
        "runner_final_status": status.get("final_status", "") if status else "",
        "runner_success_contract": runner_success,
        "runner_author_failure_contract": runner_author_failure,
        "status_contract_checks": status_contract_checks,
        "status_contract_error": status_contract_error,
        "status_contract_pass": status_contract_pass,
        "artifact_seal": artifact_seal,
        "all_required_artifacts_sealed": all_required_artifacts_sealed,
        "artifact_exclusivity_match": artifact_exclusivity_match,
        "expected_artifact_exists": expected_exists,
        "scientific_variable_count": len(scientific_variables),
        "scientific_variables": scientific_variables,
        "runtime_log_hashes_match": runtime_log_hashes_match,
    }
    if timed_out:
        evidence_ok = False
        orchestration_status = "TIMEOUT_INFRASTRUCTURE_FAIL"
    elif process.returncode == 0:
        evidence_ok = (
            runner_success
            and status_contract_pass
            and all_required_artifacts_sealed
            and execution_token_match
        )
        orchestration_status = (
            "SUCCESS_EVIDENCE_CAPTURED" if evidence_ok else "ZERO_EXIT_STATUS_MISMATCH"
        )
    else:
        evidence_ok = (
            runner_author_failure
            and status_contract_pass
            and all_required_artifacts_sealed
            and execution_token_match
        )
        orchestration_status = (
            "AUTHOR_FAILURE_EVIDENCE_CAPTURED"
            if evidence_ok
            else "NONZERO_EXIT_EVIDENCE_INCOMPLETE"
        )
    process_record["orchestration_status"] = orchestration_status
    process_record["evidence_capture_ok"] = evidence_ok
    write_json_new(exit_path, process_record)
    return process_record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("config", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.timeout_seconds < 60:
        parser.error("timeout must be at least 60 seconds")
    record = execute(args.config.resolve(), args.timeout_seconds)
    print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0 if record["evidence_capture_ok"] else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        failure = {
            "schema_version": "BOARD21_STEP3_EXECUTOR_TERMINAL_FAILURE_V1",
            "evidence_capture_ok": False,
            "orchestration_status": "EXECUTOR_EARLY_INFRASTRUCTURE_FAIL",
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        print(json.dumps(failure, ensure_ascii=False, sort_keys=True))
        print(f"BOARD21_STEP3_EXECUTOR_FAIL: {type(error).__name__}: {error}", file=sys.stderr)
        raise

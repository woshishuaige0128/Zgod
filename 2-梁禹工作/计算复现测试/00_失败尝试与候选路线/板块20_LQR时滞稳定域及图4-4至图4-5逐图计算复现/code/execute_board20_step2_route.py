#!/usr/bin/env python
"""以外层进程证据运行一条板块20原始 MLX 候选路线。

本脚本不生成或修改 ``run_config.json``，也不解释科学结果。它只启动
``run_one_board20_candidate``，将 MATLAB 的真实进程退出信息与内层
``run_status.json`` 交叉核验。所有写入均为新建，任何既有输出都会使本
脚本在启动 MATLAB 前拒绝执行，避免覆盖既有复现证据。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO


MATLAB_EXE = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
DEFAULT_TIMEOUT_SECONDS = 60.0 * 60.0


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def verify_execution_identity(
    config_path: Path, config: dict[str, Any]
) -> dict[str, Any]:
    hash_file = require_path(config, "config_hash_file")
    if not hash_file.is_file():
        raise FileNotFoundError(f"缺少run_config封签：{hash_file}")
    expected_config = hash_file.read_text(encoding="ascii").strip().upper()
    actual_config = sha256_file(config_path)
    if actual_config != expected_config:
        raise ValueError("run_config.json与分发时封签不一致")
    instrumentation = config.get("instrumentation")
    if not isinstance(instrumentation, dict):
        raise ValueError("run_config.json缺少instrumentation封签")
    files: list[dict[str, Any]] = []
    for name in ("stager", "matlab_runner", "outer_executor"):
        item = instrumentation.get(name)
        if not isinstance(item, dict):
            raise ValueError(f"instrumentation缺少{name}")
        path = Path(str(item.get("path", ""))).resolve()
        expected = str(item.get("sha256", "")).upper()
        if not path.is_file():
            raise FileNotFoundError(f"运行仪器文件缺失：{path}")
        actual = sha256_file(path)
        match = actual == expected
        files.append(
            {
                "name": name,
                "path": str(path),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "match": match,
            }
        )
        if not match:
            raise ValueError(f"运行仪器代码已漂移：{name}")
    return {
        "config_path": str(config_path),
        "config_hash_file": str(hash_file),
        "config_expected_sha256": expected_config,
        "config_actual_sha256": actual_config,
        "config_match": True,
        "files": files,
    }


def timestamp_record() -> dict[str, str]:
    """返回同一时刻的 UTC 与本地 ISO-8601 时间戳。"""
    instant = datetime.now(timezone.utc)
    return {
        "utc": instant.isoformat(),
        "local": instant.astimezone().isoformat(),
    }


def matlab_quote(value: str) -> str:
    """将 Python 路径转为 MATLAB 单引号字符串字面量。"""
    return value.replace("'", "''")


def json_load(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as stream:
        value = json.load(stream)
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须为对象：{path}")
    return value


def require_path(config: dict[str, Any], key: str) -> Path:
    value = config.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"run_config.json 缺少非空字符串字段：{key}")
    return Path(value).resolve()


def author_saved_targets(config: dict[str, Any]) -> list[Path]:
    directory = require_path(config, "author_saved_dir")
    route_id = config.get("route_id")
    replicate = config.get("replicate")
    targets = config.get("author_save_targets", [])
    if not isinstance(route_id, str) or not isinstance(replicate, str):
        raise ValueError("run_config.json 缺少 route_id 或 replicate")
    if not isinstance(targets, list) or not all(isinstance(x, str) for x in targets):
        raise ValueError("author_save_targets 必须为字符串列表")
    result: list[Path] = []
    for target in targets:
        source_name = Path(target).name
        stem = Path(source_name).stem
        suffix = Path(source_name).suffix
        result.append(directory / f"{route_id}__{replicate}__{stem}{suffix}")
    return result


def reserved_outputs(
    config_path: Path, config: dict[str, Any]
) -> tuple[Path, Path, Path, list[Path]]:
    """返回过程记录、合并日志和 MATLAB 内层可能写入的固定目标。"""
    process_exit = Path(
        config.get("process_exit_json", config_path.parent / "process_exit.json")
    ).resolve()
    log_dir = require_path(config, "run_log_dir")
    combined_log = Path(
        config.get("shell_log", log_dir / "shell_stdout_stderr.log")
    ).resolve()
    command_text = Path(
        config.get("command_txt", log_dir / "matlab_command.txt")
    ).resolve()
    matlab_outputs = [
        require_path(config, key)
        for key in (
            "status_json",
            "diary_file",
            "workspace_success",
            "workspace_failure",
            "scientific_arrays",
            "raw_stab",
            "profile_info",
        )
    ]
    matlab_outputs.append(log_dir / "error_report.txt")
    matlab_outputs.extend(author_saved_targets(config))
    return process_exit, combined_log, command_text, matlab_outputs


def refuse_existing_outputs(paths: list[Path]) -> None:
    existing = [str(path) for path in paths if path.exists()]
    if existing:
        joined = "\n".join(existing)
        raise FileExistsError(f"输出目标已存在，拒绝覆盖或重跑：\n{joined}")


def exclusive_json_write(path: Path, value: dict[str, Any]) -> None:
    """仅新建 JSON，禁止替换已有过程记录。"""
    encoded = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as error:
        raise FileExistsError(f"过程记录已存在，拒绝覆盖：{path}") from error
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(encoded)


def terminate_own_process_tree(process: subprocess.Popen[bytes]) -> dict[str, Any]:
    """仅在超时时终止本脚本启动的 PID 及其子树。"""
    termination: dict[str, Any] = {
        "attempted": True,
        "target_pid": process.pid,
        "scope": "仅本脚本启动的精确 PID 及其子进程树",
        "method": None,
        "taskkill_returncode": None,
        "taskkill_stdout": None,
        "taskkill_stderr": None,
        "fallback_used": False,
        "fallback_error": None,
    }
    if os.name == "nt":
        termination["method"] = "taskkill /PID <pid> /T /F"
        try:
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            termination["taskkill_returncode"] = completed.returncode
            termination["taskkill_stdout"] = completed.stdout.decode("utf-8", errors="replace")
            termination["taskkill_stderr"] = completed.stderr.decode("utf-8", errors="replace")
        except OSError as error:
            termination["taskkill_stderr"] = f"{type(error).__name__}: {error}"
    else:
        termination["method"] = "Popen.kill（非 Windows 后备路径）"
        termination["fallback_used"] = True
        try:
            process.kill()
        except OSError as error:
            termination["fallback_error"] = f"{type(error).__name__}: {error}"

    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        termination["fallback_used"] = True
        try:
            # taskkill 异常时仅杀死仍由本对象持有的精确根进程。
            process.kill()
            process.wait(timeout=30)
        except (OSError, subprocess.TimeoutExpired) as error:
            termination["fallback_error"] = f"{type(error).__name__}: {error}"
    return termination


def read_status(status_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    if not status_path.is_file():
        return None, f"MATLAB 未生成 run_status.json：{status_path}"
    try:
        return json_load(status_path), None
    except (OSError, ValueError, json.JSONDecodeError) as error:
        return None, f"run_status.json 不可读取：{type(error).__name__}: {error}"


def assess_status_returncode(
    status: dict[str, Any] | None,
    status_error: str | None,
    returncode: int | None,
    timed_out: bool,
    launch_exception: str | None,
) -> dict[str, Any]:
    """核验 MATLAB 内层状态的返回码约定，而不把预期失败伪装为成功。"""
    final_status = status.get("final_status") if status else None
    semantics = status.get("process_exit_semantics") if status else None
    expected: int | None = None
    reason: str
    if final_status == "SUCCESS":
        expected = 0
        reason = "SUCCESS 必须对应 MATLAB returncode=0"
    elif final_status in {"EXECUTION_FAIL", "EXECUTION_SUCCESS_EVIDENCE_FAIL"}:
        reason = f"{final_status} 必须对应 MATLAB returncode 非零"
    elif final_status is None:
        reason = status_error or "缺少 status.final_status"
    else:
        reason = f"未知 status.final_status={final_status!r}，无法建立返回码约定"

    if timed_out:
        result = "FAIL"
        reason = "MATLAB 超时，不能以未完成状态作为有效执行证据"
    elif launch_exception:
        result = "FAIL"
        reason = "MATLAB 进程未成功启动，不能核验内层状态"
    elif final_status == "SUCCESS":
        result = "PASS" if returncode == 0 else "FAIL"
    elif final_status in {"EXECUTION_FAIL", "EXECUTION_SUCCESS_EVIDENCE_FAIL"}:
        result = "PASS" if returncode is not None and returncode != 0 else "FAIL"
    else:
        result = "FAIL"
    return {
        "status_file_present": status is not None,
        "status_final_status": final_status,
        "status_process_exit_semantics": semantics,
        "actual_matlab_returncode": returncode,
        "expected_returncode": expected,
        "rule": reason,
        "result": result,
    }


def append_log(stream: BinaryIO, message: str) -> None:
    stream.write(message.encode("utf-8", errors="replace"))
    stream.flush()


def run_candidate(config_path: Path, timeout_seconds: float) -> int:
    config = json_load(config_path)
    if config.get("schema") != "board20_original_mlx_run_config_v2":
        raise ValueError("run_config.json schema 不是 board20_original_mlx_run_config_v2")
    if timeout_seconds <= 0:
        raise ValueError("--timeout-seconds 必须大于 0")
    if not MATLAB_EXE.is_file():
        raise FileNotFoundError(f"MATLAB 可执行文件不存在：{MATLAB_EXE}")
    execution_identity = verify_execution_identity(config_path, config)

    process_exit_path, combined_log_path, command_text_path, matlab_outputs = (
        reserved_outputs(config_path, config)
    )
    all_output_targets = [
        process_exit_path,
        combined_log_path,
        command_text_path,
        *matlab_outputs,
    ]
    refuse_existing_outputs(all_output_targets)
    for target in all_output_targets:
        if not target.parent.is_dir():
            raise FileNotFoundError(f"输出父目录不存在，拒绝隐式创建：{target.parent}")

    code_dir = Path(__file__).resolve().parent
    matlab_expression = (
        f"addpath('{matlab_quote(str(code_dir))}'); "
        f"run_one_board20_candidate('{matlab_quote(str(config_path))}');"
    )
    command = [str(MATLAB_EXE), "-batch", matlab_expression]
    command_windows = subprocess.list2cmdline(command)
    command_text_path.write_text(command_windows + "\n", encoding="utf-8")
    started = timestamp_record()
    record: dict[str, Any] = {
        "schema": "board20_outer_process_exit_v1",
        "config_path": str(config_path),
        "route_id": config.get("route_id"),
        "replicate": config.get("replicate"),
        "timeout_seconds": timeout_seconds,
        "execution_identity": execution_identity,
        "command_argv": command,
        "command_windows": command_windows,
        "command_text_file": str(command_text_path),
        "combined_stdout_stderr_log": str(combined_log_path),
        "started_at": started,
        "finished_at": None,
        "pid": None,
        "actual_matlab_returncode": None,
        "timed_out": False,
        "launch_exception": None,
        "termination": {"attempted": False},
        "status_read_error": None,
        "status_returncode_consistency": None,
        "scientific_execution_status": "NOT_EVALUATED",
        "evidence_capture_status": "NOT_EVALUATED",
        "outer_script_exit_code": None,
    }

    process: subprocess.Popen[bytes] | None = None
    with combined_log_path.open("xb") as log_stream:
        append_log(log_stream, "BOARD20_OUTER_PROCESS_START\n")
        append_log(log_stream, f"CONFIG={config_path}\n")
        append_log(log_stream, f"COMMAND={record['command_windows']}\n")
        append_log(log_stream, f"STARTED_UTC={started['utc']}\n")
        append_log(log_stream, f"STARTED_LOCAL={started['local']}\n")
        try:
            process = subprocess.Popen(
                command,
                cwd=str(code_dir),
                stdin=subprocess.DEVNULL,
                stdout=log_stream,
                stderr=subprocess.STDOUT,
            )
            record["pid"] = process.pid
            append_log(log_stream, f"PID={process.pid}\n")
            try:
                record["actual_matlab_returncode"] = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                record["timed_out"] = True
                append_log(log_stream, f"BOARD20_OUTER_TIMEOUT seconds={timeout_seconds}\n")
                record["termination"] = terminate_own_process_tree(process)
                record["actual_matlab_returncode"] = process.returncode
        except (OSError, subprocess.SubprocessError) as error:
            record["launch_exception"] = f"{type(error).__name__}: {error}"
            append_log(log_stream, f"BOARD20_OUTER_LAUNCH_EXCEPTION {record['launch_exception']}\n")
        finally:
            record["finished_at"] = timestamp_record()
            append_log(log_stream, f"FINISHED_UTC={record['finished_at']['utc']}\n")
            append_log(log_stream, f"FINISHED_LOCAL={record['finished_at']['local']}\n")
            append_log(log_stream, f"RETURN_CODE={record['actual_matlab_returncode']}\n")

    status_path = require_path(config, "status_json")
    status, status_error = read_status(status_path)
    record["status_read_error"] = status_error
    consistency = assess_status_returncode(
        status,
        status_error,
        record["actual_matlab_returncode"],
        bool(record["timed_out"]),
        record["launch_exception"],
    )
    record["status_returncode_consistency"] = consistency
    scientific_success = (
        status is not None
        and status.get("final_status") == "SUCCESS"
        and status.get("execution_status") == "EXECUTION_SUCCESS"
        and status.get("evidence_status") == "PASS"
        and record["actual_matlab_returncode"] == 0
        and not record["timed_out"]
        and record["launch_exception"] is None
    )
    record["scientific_execution_status"] = (
        status.get("execution_status", "UNKNOWN") if status else "UNKNOWN"
    )
    inner_evidence = status.get("evidence_status") if status else None
    record["evidence_capture_status"] = (
        "PASS"
        if consistency["result"] == "PASS" and inner_evidence == "PASS"
        else "FAIL"
    )
    script_exit = 0 if scientific_success and record["evidence_capture_status"] == "PASS" else 1
    record["outer_script_exit_code"] = script_exit
    exclusive_json_write(process_exit_path, record)
    return script_exit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "仅运行一条板块20原始MLX候选路线，并保存 MATLAB 进程退出证据。"
        )
    )
    parser.add_argument("config", type=Path, help="该路线 metadata/run_config.json 的绝对或相对路径")
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=DEFAULT_TIMEOUT_SECONDS,
        help=f"MATLAB 最长运行秒数，默认 {DEFAULT_TIMEOUT_SECONDS:g} 秒",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    config_path = args.config.expanduser().resolve()
    try:
        if not config_path.is_file():
            raise FileNotFoundError(f"run_config.json 不存在：{config_path}")
        return run_candidate(config_path, args.timeout_seconds)
    except Exception as error:  # 启动前错误不得伪造成某条路线的 MATLAB 执行证据。
        print(f"BOARD20_OUTER_EXECUTOR_ERROR: {type(error).__name__}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())

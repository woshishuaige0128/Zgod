from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parents[1]
PROJECT_ROOT = SCRIPT.parents[4]
BUILDER = BOARD_ROOT / "code" / "build_board21_step2_static_inventory.py"
VALIDATOR = BOARD_ROOT / "code" / "validate_board21_step2_static_inventory.py"
INVENTORY_ROOT = BOARD_ROOT / "outputs" / "step2_static_inventory"
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "step2_validation"
AUDIT_ROOT = BOARD_ROOT / "outputs" / "step2_determinism"
AUDIT_PATH = AUDIT_ROOT / "determinism_audit.json"
EXPECTED_PYTHON = Path(r"D:\Software\python\python.exe")
EXPECTED_SNAPSHOT_COUNT = 79
EXPECTED_ARTIFACT_COUNT = 83


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def atomic_write_json(path: Path, value: Any) -> None:
    payload = (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def run_script(path: Path, rewritten_sentinel: Path) -> dict[str, Any]:
    sentinel_before = (
        rewritten_sentinel.stat().st_mtime_ns
        if rewritten_sentinel.is_file()
        else None
    )
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    completed = subprocess.run(
        [str(EXPECTED_PYTHON), str(path)],
        cwd=PROJECT_ROOT,
        env=environment,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    stdout_lines = [line for line in completed.stdout.splitlines() if line.strip()]
    parsed_last_line: dict[str, Any] | None = None
    if stdout_lines:
        try:
            candidate = json.loads(stdout_lines[-1])
            if isinstance(candidate, dict):
                parsed_last_line = candidate
        except json.JSONDecodeError:
            parsed_last_line = None
    sentinel_after = (
        rewritten_sentinel.stat().st_mtime_ns
        if rewritten_sentinel.is_file()
        else None
    )
    return {
        "script": path.relative_to(BOARD_ROOT).as_posix(),
        "returncode": completed.returncode,
        "last_stdout_json": parsed_last_line,
        "stderr": completed.stderr.strip(),
        "output_rewritten": (
            sentinel_after is not None
            and (sentinel_before is None or sentinel_after != sentinel_before)
        ),
    }


def builder_result_ok(result: dict[str, Any]) -> bool:
    summary = result.get("last_stdout_json")
    return (
        result.get("returncode") == 0
        and result.get("stderr") == ""
        and result.get("output_rewritten") is True
        and isinstance(summary, dict)
        and summary.get("schema_version")
        == "BOARD21_STEP2_STATIC_INVENTORY_V3"
        and summary.get("status") == "STATIC_INVENTORY_PASS"
        and summary.get("matlab_executed") is False
        and summary.get("author_file_count") == 36
        and summary.get("energy_route_count") == 7
        and summary.get("formula_route_audit_count") == 35
        and summary.get("historical_target_count") == 4
    )


def validator_result_ok(result: dict[str, Any]) -> bool:
    summary = result.get("last_stdout_json")
    return (
        result.get("returncode") == 0
        and result.get("stderr") == ""
        and result.get("output_rewritten") is True
        and isinstance(summary, dict)
        and summary.get("schema_version")
        == "BOARD21_STEP2_INDEPENDENT_VALIDATION_V2"
        and summary.get("status") == "PASS"
        and summary.get("check_count") == 298
        and summary.get("passed_count") == 298
        and summary.get("failed_count") == 0
        and summary.get("failed_check_ids") == []
        and summary.get("matlab_executed") is False
        and summary.get("inventory_file_count") == 75
        and summary.get("artifact_manifest_file_count")
        == EXPECTED_ARTIFACT_COUNT
        and summary.get("validation_root_file_count") == 4
        and summary.get("validation_output_manifest_verified") is True
        and summary.get("validation_output_postcondition_status") == "PASS"
    )


def snapshot() -> list[dict[str, Any]]:
    rows = []
    for label, root in (
        ("step2_static_inventory", INVENTORY_ROOT),
        ("step2_validation", VALIDATION_ROOT),
    ):
        for path in sorted(
            (item for item in root.rglob("*") if item.is_file()),
            key=lambda item: item.as_posix().casefold(),
        ):
            rows.append(
                {
                    "relative_path": (
                        f"{label}/{path.relative_to(root).as_posix()}"
                    ),
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                }
            )
    return rows


def snapshot_map(rows: list[dict[str, Any]]) -> dict[str, tuple[int, str]]:
    return {
        row["relative_path"]: (row["size_bytes"], row["sha256"])
        for row in rows
    }


def main() -> int:
    AUDIT_ROOT.mkdir(parents=True, exist_ok=True)
    preflight_entries = sorted(
        path.relative_to(AUDIT_ROOT).as_posix()
        for path in AUDIT_ROOT.rglob("*")
    )
    preflight_ok = all(
        relative == AUDIT_PATH.name and (AUDIT_ROOT / relative).is_file()
        for relative in preflight_entries
    )
    python_exact = Path(sys.executable).resolve() == EXPECTED_PYTHON.resolve()
    tool_sha256 = {
        path.relative_to(BOARD_ROOT).as_posix(): sha256_file(path)
        for path in (BUILDER, VALIDATOR, SCRIPT)
    }
    rounds = []
    for round_index in (1, 2):
        build_result = run_script(
            BUILDER, INVENTORY_ROOT / "inventory_summary.json"
        )
        validation_result = run_script(
            VALIDATOR, VALIDATION_ROOT / "validation_summary.json"
        )
        rows = snapshot()
        rounds.append(
            {
                "round": round_index,
                "builder": build_result,
                "validator": validation_result,
                "snapshot_file_count": len(rows),
                "empty_files": [
                    row["relative_path"]
                    for row in rows
                    if row["size_bytes"] <= 0
                ],
                "snapshot": rows,
            }
        )
    first = snapshot_map(rounds[0]["snapshot"])
    second = snapshot_map(rounds[1]["snapshot"])
    missing_in_round2 = sorted(set(first) - set(second))
    extra_in_round2 = sorted(set(second) - set(first))
    different = sorted(
        path for path in set(first) & set(second) if first[path] != second[path]
    )
    command_ok = all(
        builder_result_ok(item["builder"])
        and validator_result_ok(item["validator"])
        for item in rounds
    )
    count_ok = all(
        item["snapshot_file_count"] == EXPECTED_SNAPSHOT_COUNT
        for item in rounds
    )
    nonempty_ok = all(not item["empty_files"] for item in rounds)
    exact_match = not missing_in_round2 and not extra_in_round2 and not different
    status = (
        "PASS"
        if preflight_ok
        and python_exact
        and command_ok
        and count_ok
        and nonempty_ok
        and exact_match
        else "FAIL"
    )
    audit = {
        "schema_version": "BOARD21_STEP2_DETERMINISM_AUDIT_V1",
        "status": status,
        "matlab_executed": False,
        "python_executable": str(Path(sys.executable).resolve()),
        "expected_python_executable": str(EXPECTED_PYTHON.resolve()),
        "python_executable_exact": python_exact,
        "tool_sha256_before_rounds": tool_sha256,
        "expected_snapshot_file_count": EXPECTED_SNAPSHOT_COUNT,
        "audit_root_preflight_entries": preflight_entries,
        "audit_root_preflight_ok": preflight_ok,
        "rounds": rounds,
        "comparison": {
            "exact_match": exact_match,
            "missing_in_round2": missing_in_round2,
            "extra_in_round2": extra_in_round2,
            "different": different,
        },
    }
    atomic_write_json(AUDIT_PATH, audit)
    final_entries = sorted(
        path.relative_to(AUDIT_ROOT).as_posix()
        for path in AUDIT_ROOT.rglob("*")
    )
    if final_entries != [AUDIT_PATH.name]:
        audit["status"] = "FAIL"
        audit["audit_root_final_entries"] = final_entries
        atomic_write_json(AUDIT_PATH, audit)
    print(
        json.dumps(
            {
                "status": audit["status"],
                "round_file_counts": [
                    item["snapshot_file_count"] for item in rounds
                ],
                "missing_count": len(missing_in_round2),
                "extra_count": len(extra_in_round2),
                "different_count": len(different),
                "audit_path": AUDIT_PATH.relative_to(PROJECT_ROOT).as_posix(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if audit["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path
from types import ModuleType


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parents[1]
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "step1_validation"
OUTPUT_PATH = VALIDATION_ROOT / "relative_handle_race_test.json"
MODULE_PATHS = (
    ("freeze", SCRIPT.parent / "freeze_board21_inputs.py"),
    ("validator", SCRIPT.parent / "validate_board21_step1.py"),
)


def load_module(role: str, path: Path) -> ModuleType:
    payload = path.read_bytes()
    captured_hash = hashlib.sha256(payload).hexdigest().upper()
    module = ModuleType(f"board21_{role}_race_target")
    module.__file__ = str(path)
    module.__package__ = ""
    exec(compile(payload, str(path), "exec"), module.__dict__)
    after_hash = sha256_file(path)
    if after_hash != captured_hash:
        raise RuntimeError(
            f"Race-test target changed while loading: before={captured_hash}, "
            f"after={after_hash}, path={path}"
        )
    module.__captured_sha256__ = captured_hash
    return module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_if_file(path: Path) -> bytes | None:
    return path.read_bytes() if path.is_file() else None


def run_attack_scenario(
    module: ModuleType,
    role: str,
    timing: str,
) -> dict[str, object]:
    payload = f"board21-relative-handle-{role}-{timing}".encode("utf-8")
    sentinel = b"replacement-directory-sentinel"
    with tempfile.TemporaryDirectory(
        prefix=f"board21_{role}_{timing}_race_"
    ) as temp_root:
        root = Path(temp_root).resolve()
        original = root / "locked_parent"
        renamed_original = root / "renamed_original"
        replacement = root / "locked_parent"
        target = original / "result.bin"
        original.mkdir()

        old_board_root = module.BOARD_ROOT
        attack_attempted = False
        attack_blocked = False
        attack_completed = False
        operation_succeeded = False
        operation_error_type = ""
        path_mismatch_detected = False

        def attempt_directory_replacement() -> None:
            nonlocal attack_attempted, attack_blocked, attack_completed
            attack_attempted = True
            try:
                os.rename(original, renamed_original)
            except PermissionError:
                attack_blocked = True
                return
            attack_completed = True
            replacement.mkdir()
            (replacement / "sentinel.bin").write_bytes(sentinel)

        original_open = module.nt_open_relative_file
        original_rename = module.rename_handle_relative

        def attacked_open(*args: object, **kwargs: object) -> object:
            if not attack_attempted:
                attempt_directory_replacement()
            return original_open(*args, **kwargs)

        def attacked_rename(*args: object, **kwargs: object) -> object:
            if not attack_attempted:
                attempt_directory_replacement()
            return original_rename(*args, **kwargs)

        try:
            module.BOARD_ROOT = root
            if timing == "before_temporary_open":
                module.nt_open_relative_file = attacked_open
            elif timing == "after_temporary_open":
                module.rename_handle_relative = attacked_rename
            else:
                raise ValueError(f"Unsupported attack timing: {timing}")
            try:
                module.safe_atomic_write_bytes(target, payload, root)
                operation_succeeded = True
            except (OSError, RuntimeError) as exc:
                operation_error_type = type(exc).__name__
                path_mismatch_detected = "Handle final path mismatch" in str(exc)
        finally:
            module.nt_open_relative_file = original_open
            module.rename_handle_relative = original_rename
            module.BOARD_ROOT = old_board_root

        original_result = read_if_file(original / "result.bin")
        renamed_result = read_if_file(renamed_original / "result.bin")
        replacement_result = read_if_file(replacement / "result.bin")
        replacement_sentinel = read_if_file(replacement / "sentinel.bin")
        actual_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }

        if attack_blocked:
            expected_files = {"locked_parent/result.bin"}
            safe_outcome = (
                operation_succeeded
                and original_result == payload
                and renamed_result is None
                and actual_files == expected_files
            )
        else:
            expected_renamed_payload = (
                None if timing == "before_temporary_open" else payload
            )
            expected_files = {"locked_parent/sentinel.bin"}
            if timing == "after_temporary_open":
                expected_files.add("renamed_original/result.bin")
            safe_outcome = (
                attack_completed
                and not operation_succeeded
                and original_result is None
                and renamed_result == expected_renamed_payload
                and replacement_result is None
                and replacement_sentinel == sentinel
                and path_mismatch_detected
                and actual_files == expected_files
            )

        return {
            "timing": timing,
            "status": "PASS" if attack_attempted and safe_outcome else "FAIL",
            "attack_attempted": attack_attempted,
            "attack_blocked_by_windows": attack_blocked,
            "attack_completed": attack_completed,
            "operation_succeeded": operation_succeeded,
            "operation_error_type": operation_error_type,
            "path_mismatch_detected": path_mismatch_detected,
            "payload_at_original_path": original_result == payload,
            "payload_at_renamed_original_object": renamed_result == payload,
            "replacement_directory_not_written": (
                replacement_result is None if attack_completed else "NOT_CREATED"
            ),
            "replacement_sentinel_unchanged": (
                replacement_sentinel == sentinel if attack_completed else "NOT_CREATED"
            ),
            "temporary_file_leak_absent": actual_files == expected_files,
            "actual_files": sorted(actual_files),
            "safe_outcome": safe_outcome,
        }


def run_ancestor_chain_acquisition_attack(
    module: ModuleType,
    role: str,
) -> dict[str, object]:
    timing = "during_ancestor_chain_acquisition"
    payload = f"board21-relative-handle-{role}-{timing}".encode("utf-8")
    sentinel = b"replacement-directory-sentinel"
    with tempfile.TemporaryDirectory(
        prefix=f"board21_{role}_{timing}_race_"
    ) as temp_root:
        root = Path(temp_root).resolve()
        board = root / "board_root"
        output = board / "outputs"
        target = output / "result.bin"
        renamed_board = root / "renamed_board_root"
        replacement = board
        output.mkdir(parents=True)

        old_board_root = module.BOARD_ROOT
        original_open_directory = module.open_locked_directory
        attack_attempted = False
        attack_blocked = False
        attack_completed = False
        operation_succeeded = False
        operation_error_type = ""
        path_mismatch_detected = False

        def attacked_open_directory(path: Path) -> object:
            nonlocal attack_attempted, attack_blocked, attack_completed
            opened = original_open_directory(path)
            if (
                not attack_attempted
                and module.normalized_windows_path(path)
                == module.normalized_windows_path(board)
            ):
                attack_attempted = True
                try:
                    os.rename(board, renamed_board)
                except PermissionError:
                    attack_blocked = True
                else:
                    attack_completed = True
                    (replacement / "outputs").mkdir(parents=True)
                    (replacement / "sentinel.bin").write_bytes(sentinel)
            return opened

        try:
            module.BOARD_ROOT = board
            module.open_locked_directory = attacked_open_directory
            try:
                module.safe_atomic_write_bytes(target, payload, board)
                operation_succeeded = True
            except (OSError, RuntimeError) as exc:
                operation_error_type = type(exc).__name__
                path_mismatch_detected = "Handle final path mismatch" in str(exc)
        finally:
            module.open_locked_directory = original_open_directory
            module.BOARD_ROOT = old_board_root

        actual_files = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        replacement_result = read_if_file(replacement / "outputs" / "result.bin")
        renamed_result = read_if_file(renamed_board / "outputs" / "result.bin")
        replacement_sentinel = read_if_file(replacement / "sentinel.bin")
        if attack_blocked:
            expected_files = {"board_root/outputs/result.bin"}
            safe_outcome = (
                operation_succeeded
                and read_if_file(target) == payload
                and renamed_result is None
                and actual_files == expected_files
            )
        else:
            expected_files = {"board_root/sentinel.bin"}
            safe_outcome = (
                attack_completed
                and not operation_succeeded
                and path_mismatch_detected
                and replacement_result is None
                and renamed_result is None
                and replacement_sentinel == sentinel
                and actual_files == expected_files
            )

        return {
            "timing": timing,
            "status": "PASS" if attack_attempted and safe_outcome else "FAIL",
            "attack_attempted": attack_attempted,
            "attack_blocked_by_windows": attack_blocked,
            "attack_completed": attack_completed,
            "operation_succeeded": operation_succeeded,
            "operation_error_type": operation_error_type,
            "path_mismatch_detected": path_mismatch_detected,
            "replacement_tree_not_written": replacement_result is None,
            "renamed_original_tree_not_written": renamed_result is None,
            "replacement_sentinel_unchanged": (
                replacement_sentinel == sentinel if attack_completed else "NOT_CREATED"
            ),
            "temporary_file_leak_absent": actual_files == expected_files,
            "actual_files": sorted(actual_files),
            "safe_outcome": safe_outcome,
        }


def exercise_relative_directory_binding(module: ModuleType, role: str) -> dict[str, object]:
    scenarios = [
        run_ancestor_chain_acquisition_attack(module, role),
        run_attack_scenario(module, role, "before_temporary_open"),
        run_attack_scenario(module, role, "after_temporary_open"),
    ]
    status = "PASS" if all(item["status"] == "PASS" for item in scenarios) else "FAIL"
    return {
        "module_role": role,
        "module_relative_path": MODULE_PATHS[0][1].parent.joinpath(
            "freeze_board21_inputs.py" if role == "freeze" else "validate_board21_step1.py"
        ).relative_to(BOARD_ROOT).as_posix(),
        "module_sha256": str(module.__captured_sha256__),
        "status": status,
        "scenarios": scenarios,
    }


def exercise_dangling_junction_boundaries(validator: ModuleType) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="board21_dangling_junction_") as temp_root:
        root = Path(temp_root).resolve()
        target = root / "junction_target"
        junction = root / "板块22_断链联接探针"
        target.mkdir()
        completed = subprocess.run(
            ["cmd.exe", "/d", "/c", "mklink", "/J", str(junction), str(target)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        junction_created = completed.returncode == 0 and os.path.lexists(junction)
        target_removed = False
        lexists_after_target_removal = False
        follows_as_existing = True
        nofollow_reparse_detected = False
        named_boundary_detected = False
        if junction_created:
            os.rmdir(target)
            target_removed = not os.path.lexists(target)
            lexists_after_target_removal = os.path.lexists(junction)
            follows_as_existing = junction.exists()
            with os.scandir(root) as iterator:
                junction_entry = next(
                    entry for entry in iterator if entry.name == junction.name
                )
                _, nofollow_reparse_detected, _ = validator.nofollow_entry_flags(
                    junction_entry
                )
            named_boundary_detected = junction in (
                validator.find_named_directory_or_reparse_entries(root, "板块22")
            )
            os.rmdir(junction)

        checks = {
            "junction_created": junction_created,
            "target_removed": target_removed,
            "dangling_entry_lexists": lexists_after_target_removal,
            "dangling_entry_exists_is_false": not follows_as_existing,
            "nofollow_reparse_detected": nofollow_reparse_detected,
            "named_boundary_detected": named_boundary_detected,
            "junction_cleanup_complete": not os.path.lexists(junction),
        }
        return {
            "status": "PASS" if all(checks.values()) else "FAIL",
            "checks": checks,
            "creation_returncode": completed.returncode,
        }


def main() -> int:
    if not VALIDATION_ROOT.is_dir():
        raise FileNotFoundError(
            f"Validation directory must exist before security test: {VALIDATION_ROOT}"
        )
    module_results = []
    loaded_modules: dict[str, ModuleType] = {}
    for role, path in MODULE_PATHS:
        module = load_module(role, path)
        loaded_modules[role] = module
        module_results.append(exercise_relative_directory_binding(module, role))
    boundary_protocol_result = exercise_dangling_junction_boundaries(
        loaded_modules["validator"]
    )

    result = {
        "schema_version": "BOARD21_RELATIVE_HANDLE_RACE_TEST_V1",
        "overall_status": (
            "PASS"
            if all(item["status"] == "PASS" for item in module_results)
            and boundary_protocol_result["status"] == "PASS"
            else "FAIL"
        ),
        "module_results": module_results,
        "boundary_protocol_result": boundary_protocol_result,
    }
    payload = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    loaded_modules["freeze"].safe_atomic_write_bytes(
        OUTPUT_PATH,
        payload,
        VALIDATION_ROOT,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

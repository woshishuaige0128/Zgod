from __future__ import annotations

import csv
import hashlib
import io
import os
import stat
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping


MANIFEST_NAME = "artifact_manifest.csv"
MANIFEST_TEMP_NAME = ".artifact_manifest.csv.tmp"
MANIFEST_FIELDS = ["relpath", "bytes", "sha256"]
FILE_ATTRIBUTE_REPARSE_POINT = 0x0400
EXPECTED_FIXED_ROOTS = {
    "run1": "outputs/step6_history_comparison_run1",
    "run2": "outputs/step6_history_comparison_run2",
    "validation": "outputs/step6_history_comparison_validation",
    "logs": "logs/step6_history_comparison",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def lexical_exists(path: Path) -> bool:
    return os.path.lexists(str(path))


def _is_reparse_stat(value: os.stat_result) -> bool:
    return bool(
        int(getattr(value, "st_file_attributes", 0))
        & FILE_ATTRIBUTE_REPARSE_POINT
    )


def _assert_not_link_or_reparse(path: Path) -> os.stat_result:
    value = path.lstat()
    is_junction = getattr(path, "is_junction", lambda: False)()
    if path.is_symlink() or is_junction or _is_reparse_stat(value):
        raise RuntimeError(f"Link, junction, or reparse point is forbidden: {path}")
    return value


def _validate_existing_components(board_root: Path, lexical_path: Path) -> None:
    board_absolute = Path(os.path.abspath(str(board_root)))
    candidate_absolute = Path(os.path.abspath(str(lexical_path)))
    if not candidate_absolute.is_relative_to(board_absolute):
        raise RuntimeError(f"Path escapes Board20 root lexically: {lexical_path}")
    current = board_absolute
    _assert_not_link_or_reparse(current)
    for part in candidate_absolute.relative_to(board_absolute).parts:
        current = current / part
        if lexical_exists(current):
            _assert_not_link_or_reparse(current)


def validate_fixed_roots(
    board_root: Path, raw_roots: Mapping[str, str]
) -> dict[str, Path]:
    """Validate lexical and resolved identities before any write or removal."""
    if dict(raw_roots) != EXPECTED_FIXED_ROOTS:
        raise RuntimeError(
            "Step6 fixed root literal contract drifted before filesystem access: "
            f"expected={EXPECTED_FIXED_ROOTS}, actual={dict(raw_roots)}"
        )
    board_absolute = Path(os.path.abspath(str(board_root)))
    board_resolved = board_absolute.resolve(strict=True)
    result: dict[str, Path] = {}
    lexical_keys: set[str] = set()
    resolved_keys: set[str] = set()

    for name, raw in raw_roots.items():
        if not isinstance(raw, str) or not raw:
            raise RuntimeError(f"Fixed root {name!r} must be a nonempty POSIX relative path")
        pure = PurePosixPath(raw)
        if pure.is_absolute() or raw != pure.as_posix() or any(
            part in {"", ".", ".."} for part in pure.parts
        ):
            raise RuntimeError(f"Fixed root {name!r} is not canonical: {raw!r}")
        lexical = board_absolute.joinpath(*pure.parts)
        _validate_existing_components(board_absolute, lexical)
        resolved = lexical.resolve(strict=False)
        if not resolved.is_relative_to(board_resolved):
            raise RuntimeError(f"Fixed root {name!r} escapes Board20 root: {raw!r}")

        lexical_key = os.path.normcase(os.path.abspath(str(lexical)))
        resolved_key = os.path.normcase(os.path.abspath(str(resolved)))
        if lexical_key in lexical_keys or resolved_key in resolved_keys:
            raise RuntimeError(f"Fixed root aliases another root: {name}={raw}")
        lexical_keys.add(lexical_key)
        resolved_keys.add(resolved_key)
        result[name] = lexical

    existing = [(name, path) for name, path in result.items() if lexical_exists(path)]
    for index, (left_name, left_path) in enumerate(existing):
        for right_name, right_path in existing[index + 1 :]:
            if os.path.samefile(left_path, right_path):
                raise RuntimeError(
                    f"Fixed roots resolve to the same filesystem object: "
                    f"{left_name} and {right_name}"
                )
    return result


@dataclass(frozen=True)
class Inventory:
    files: frozenset[str]
    directories: frozenset[str]


@dataclass(frozen=True)
class OutputState:
    state: str
    inventory: Inventory
    manifest_sha256: str | None


def strict_inventory(root: Path) -> Inventory:
    if not lexical_exists(root):
        return Inventory(frozenset(), frozenset())
    root_stat = _assert_not_link_or_reparse(root)
    if not stat.S_ISDIR(root_stat.st_mode):
        raise RuntimeError(f"Output root is not a regular directory: {root}")

    files: set[str] = set()
    directories: set[str] = set()

    def walk(directory: Path) -> None:
        with os.scandir(directory) as entries:
            ordered = sorted(entries, key=lambda item: item.name)
        for entry in ordered:
            path = Path(entry.path)
            value = _assert_not_link_or_reparse(path)
            relpath = path.relative_to(root).as_posix()
            if stat.S_ISDIR(value.st_mode):
                directories.add(relpath)
                walk(path)
            elif stat.S_ISREG(value.st_mode):
                if int(getattr(value, "st_nlink", 1)) != 1:
                    raise RuntimeError(f"Hard-linked file is forbidden: {path}")
                files.add(relpath)
            else:
                raise RuntimeError(f"Unsupported filesystem object in output root: {path}")

    walk(root)
    return Inventory(frozenset(files), frozenset(directories))


def _read_manifest(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != MANIFEST_FIELDS:
            raise RuntimeError(
                f"Manifest schema drifted: expected={MANIFEST_FIELDS}, "
                f"actual={reader.fieldnames}, path={path}"
            )
        rows = list(reader)
    relpaths = [row["relpath"] for row in rows]
    if len(relpaths) != len(set(relpaths)):
        raise RuntimeError(f"Manifest contains duplicate relpaths: {path}")
    if relpaths != sorted(relpaths):
        raise RuntimeError(f"Manifest relpaths are not in canonical sorted order: {path}")
    return rows


def classify_output(
    root: Path,
    expected_files: Iterable[str],
    expected_directories: Iterable[str],
) -> OutputState:
    expected_file_set = frozenset(expected_files)
    expected_directory_set = frozenset(expected_directories)
    if not lexical_exists(root):
        return OutputState(
            "ABSENT", Inventory(frozenset(), frozenset()), None
        )

    inventory = strict_inventory(root)
    files = inventory.files
    directories = inventory.directories
    manifest_path = root / MANIFEST_NAME
    manifest_present = MANIFEST_NAME in files
    temp_present = MANIFEST_TEMP_NAME in files

    if manifest_present:
        if temp_present:
            raise RuntimeError(f"Committed output also contains manifest temp: {root}")
        required_files = expected_file_set | {MANIFEST_NAME}
        if files != required_files or directories != expected_directory_set:
            raise RuntimeError(
                f"Committed output tree drifted: {root}; "
                f"file_delta={sorted(files ^ required_files)}, "
                f"directory_delta={sorted(directories ^ expected_directory_set)}"
            )
        rows = _read_manifest(manifest_path)
        listed = [row["relpath"] for row in rows]
        if listed != sorted(expected_file_set):
            raise RuntimeError(
                f"Manifest artifact list drifted: {root}; "
                f"delta={sorted(set(listed) ^ set(expected_file_set))}"
            )
        failures: list[str] = []
        for row in rows:
            path = root / Path(row["relpath"])
            if (
                path.stat().st_size != int(row["bytes"])
                or sha256_file(path) != row["sha256"]
            ):
                failures.append(row["relpath"])
        if failures:
            raise RuntimeError(f"Committed manifest hash failures: {failures}")
        return OutputState("COMMITTED", inventory, sha256_file(manifest_path))

    allowed_files = expected_file_set | {MANIFEST_TEMP_NAME}
    if not files.issubset(allowed_files) or not directories.issubset(
        expected_directory_set
    ):
        raise RuntimeError(
            f"Uncommitted output contains unknown objects: {root}; "
            f"unexpected_files={sorted(files - allowed_files)}, "
            f"unexpected_directories={sorted(directories - expected_directory_set)}"
        )
    return OutputState("RECOVERABLE_UNCOMMITTED", inventory, None)


def prepare_output_root(
    root: Path,
    expected_files: Iterable[str],
    expected_directories: Iterable[str],
) -> OutputState:
    expected_file_set = frozenset(expected_files)
    expected_directory_set = frozenset(expected_directories)
    prior = classify_output(root, expected_file_set, expected_directory_set)
    if prior.state == "COMMITTED":
        (root / MANIFEST_NAME).unlink()
    if lexical_exists(root / MANIFEST_TEMP_NAME):
        temp_stat = _assert_not_link_or_reparse(root / MANIFEST_TEMP_NAME)
        if not stat.S_ISREG(temp_stat.st_mode):
            raise RuntimeError(f"Manifest temp is not a regular file: {root}")
        (root / MANIFEST_TEMP_NAME).unlink()
    root.mkdir(parents=True, exist_ok=True)
    for relpath in sorted(expected_directory_set):
        (root / Path(relpath)).mkdir(parents=True, exist_ok=True)
    current = classify_output(root, expected_file_set, expected_directory_set)
    if current.state != "RECOVERABLE_UNCOMMITTED":
        raise RuntimeError(f"Output did not enter recoverable state: {root}")
    return prior


def _manifest_bytes(root: Path, expected_files: frozenset[str]) -> bytes:
    rows = [
        {
            "relpath": relpath,
            "bytes": (root / Path(relpath)).stat().st_size,
            "sha256": sha256_file(root / Path(relpath)),
        }
        for relpath in sorted(expected_files)
    ]
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8")


def atomic_commit_manifest(
    root: Path,
    expected_files: Iterable[str],
    expected_directories: Iterable[str],
    fail_hook: Callable[[str], None] | None = None,
) -> list[dict[str, str]]:
    expected_file_set = frozenset(expected_files)
    expected_directory_set = frozenset(expected_directories)
    state = classify_output(root, expected_file_set, expected_directory_set)
    if state.state != "RECOVERABLE_UNCOMMITTED":
        raise RuntimeError(f"Output is not ready for manifest commit: {root}")
    if (
        state.inventory.files != expected_file_set
        or state.inventory.directories != expected_directory_set
    ):
        raise RuntimeError(
            f"Cannot commit incomplete output tree: {root}; "
            f"file_delta={sorted(state.inventory.files ^ expected_file_set)}, "
            f"directory_delta={sorted(state.inventory.directories ^ expected_directory_set)}"
        )

    payload = _manifest_bytes(root, expected_file_set)
    temp_path = root / MANIFEST_TEMP_NAME
    manifest_path = root / MANIFEST_NAME
    binary_flag = int(getattr(os, "O_BINARY", 0))
    descriptor = os.open(
        temp_path,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | binary_flag,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    if fail_hook is not None:
        fail_hook("after_manifest_temp_fsync")
    os.replace(temp_path, manifest_path)
    if fail_hook is not None:
        fail_hook("after_manifest_replace")

    committed = classify_output(root, expected_file_set, expected_directory_set)
    if committed.state != "COMMITTED":
        raise RuntimeError(f"Manifest commit did not close output: {root}")
    return _read_manifest(manifest_path)


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(f".{path.name}.tmp")
    if lexical_exists(temp):
        _assert_not_link_or_reparse(temp)
        temp.unlink()
    descriptor = os.open(
        temp,
        os.O_WRONLY
        | os.O_CREAT
        | os.O_EXCL
        | int(getattr(os, "O_BINARY", 0)),
        0o600,
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
    finally:
        if descriptor >= 0:
            os.close(descriptor)
    os.replace(temp, path)


class ExclusiveFileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._stream = None

    def __enter__(self) -> "ExclusiveFileLock":
        import msvcrt

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._stream = self.path.open("a+b")
        self._stream.seek(0, os.SEEK_END)
        if self._stream.tell() == 0:
            self._stream.write(b"0")
            self._stream.flush()
        self._stream.seek(0)
        try:
            msvcrt.locking(self._stream.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError as exc:
            self._stream.close()
            self._stream = None
            raise RuntimeError(f"Step6 filesystem protocol is already locked: {self.path}") from exc
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        import msvcrt

        if self._stream is not None:
            self._stream.seek(0)
            msvcrt.locking(self._stream.fileno(), msvcrt.LK_UNLCK, 1)
            self._stream.close()
            self._stream = None

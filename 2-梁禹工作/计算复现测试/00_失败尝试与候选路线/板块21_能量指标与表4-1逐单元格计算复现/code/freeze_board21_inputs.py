from __future__ import annotations

import csv
import ctypes
import hashlib
import io
import json
import msvcrt
import os
import secrets
from collections import Counter
from contextlib import contextmanager
from ctypes import wintypes
from pathlib import Path, PurePosixPath
from typing import Any, BinaryIO, Iterator


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parents[1]
PROJECT_ROOT = BOARD_ROOT.parents[2]
AUTHOR_ROOT = PROJECT_ROOT / "liangyustability-master"
ENERGY_ROOT = AUTHOR_ROOT / "能量指标"
INPUT_ROOT = BOARD_ROOT / "input"
MANIFEST_PATH = INPUT_ROOT / "input_manifest.csv"
SUMMARY_PATH = INPUT_ROOT / "input_freeze_summary.json"
REPARSE_POINT_ATTRIBUTE = 0x400
FILE_ATTRIBUTE_DIRECTORY = 0x10
FILE_SHARE_READ = 0x1
OPEN_EXISTING = 3
FILE_READ_ATTRIBUTES = 0x80
SYNCHRONIZE = 0x100000
GENERIC_READ = 0x80000000
FILE_FLAG_OPEN_REPARSE_POINT = 0x00200000
FILE_FLAG_BACKUP_SEMANTICS = 0x02000000
FILE_FLAG_SEQUENTIAL_SCAN = 0x08000000
FILE_ATTRIBUTE_TAG_INFO_CLASS = 9
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value
GENERIC_WRITE = 0x40000000
DELETE_ACCESS = 0x00010000
OBJ_CASE_INSENSITIVE = 0x40
FILE_OPEN = 1
FILE_CREATE = 2
FILE_NON_DIRECTORY_FILE = 0x40
FILE_SYNCHRONOUS_IO_NONALERT = 0x20
FILE_ATTRIBUTE_NORMAL = 0x80
NATIVE_FILE_RENAME_INFORMATION_CLASS = 10
NATIVE_FILE_DISPOSITION_INFORMATION_CLASS = 13


class FileAttributeTagInfo(ctypes.Structure):
    _fields_ = [
        ("FileAttributes", wintypes.DWORD),
        ("ReparseTag", wintypes.DWORD),
    ]


class ByHandleFileInformation(ctypes.Structure):
    _fields_ = [
        ("dwFileAttributes", wintypes.DWORD),
        ("ftCreationTime", wintypes.FILETIME),
        ("ftLastAccessTime", wintypes.FILETIME),
        ("ftLastWriteTime", wintypes.FILETIME),
        ("dwVolumeSerialNumber", wintypes.DWORD),
        ("nFileSizeHigh", wintypes.DWORD),
        ("nFileSizeLow", wintypes.DWORD),
        ("nNumberOfLinks", wintypes.DWORD),
        ("nFileIndexHigh", wintypes.DWORD),
        ("nFileIndexLow", wintypes.DWORD),
    ]


class UnicodeString(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.USHORT),
        ("MaximumLength", wintypes.USHORT),
        ("Buffer", wintypes.LPWSTR),
    ]


class ObjectAttributes(ctypes.Structure):
    _fields_ = [
        ("Length", wintypes.ULONG),
        ("RootDirectory", wintypes.HANDLE),
        ("ObjectName", ctypes.POINTER(UnicodeString)),
        ("Attributes", wintypes.ULONG),
        ("SecurityDescriptor", wintypes.LPVOID),
        ("SecurityQualityOfService", wintypes.LPVOID),
    ]


class IoStatusBlock(ctypes.Structure):
    _fields_ = [
        ("Status", ctypes.c_void_p),
        ("Information", ctypes.c_size_t),
    ]


class FileRenameInfoHead(ctypes.Structure):
    _fields_ = [
        ("ReplaceIfExists", wintypes.BYTE),
        ("RootDirectory", wintypes.HANDLE),
        ("FileNameLength", wintypes.DWORD),
    ]


class FileDispositionInfo(ctypes.Structure):
    _fields_ = [("DeleteFile", wintypes.BYTE)]


KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
CREATE_FILE_W = KERNEL32.CreateFileW
CREATE_FILE_W.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
CREATE_FILE_W.restype = wintypes.HANDLE
GET_FINAL_PATH_NAME_BY_HANDLE_W = KERNEL32.GetFinalPathNameByHandleW
GET_FINAL_PATH_NAME_BY_HANDLE_W.argtypes = [
    wintypes.HANDLE,
    wintypes.LPWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
]
GET_FINAL_PATH_NAME_BY_HANDLE_W.restype = wintypes.DWORD
GET_FILE_INFORMATION_BY_HANDLE_EX = KERNEL32.GetFileInformationByHandleEx
GET_FILE_INFORMATION_BY_HANDLE_EX.argtypes = [
    wintypes.HANDLE,
    ctypes.c_int,
    wintypes.LPVOID,
    wintypes.DWORD,
]
GET_FILE_INFORMATION_BY_HANDLE_EX.restype = wintypes.BOOL
GET_FILE_INFORMATION_BY_HANDLE = KERNEL32.GetFileInformationByHandle
GET_FILE_INFORMATION_BY_HANDLE.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(ByHandleFileInformation),
]
GET_FILE_INFORMATION_BY_HANDLE.restype = wintypes.BOOL
CLOSE_HANDLE = KERNEL32.CloseHandle
CLOSE_HANDLE.argtypes = [wintypes.HANDLE]
CLOSE_HANDLE.restype = wintypes.BOOL
NTDLL = ctypes.WinDLL("ntdll", use_last_error=True)
NT_CREATE_FILE = NTDLL.NtCreateFile
NT_CREATE_FILE.argtypes = [
    ctypes.POINTER(wintypes.HANDLE),
    wintypes.DWORD,
    ctypes.POINTER(ObjectAttributes),
    ctypes.POINTER(IoStatusBlock),
    ctypes.c_void_p,
    wintypes.ULONG,
    wintypes.ULONG,
    wintypes.ULONG,
    wintypes.ULONG,
    ctypes.c_void_p,
    wintypes.ULONG,
]
NT_CREATE_FILE.restype = ctypes.c_long
NT_SET_INFORMATION_FILE = NTDLL.NtSetInformationFile
NT_SET_INFORMATION_FILE.argtypes = [
    wintypes.HANDLE,
    ctypes.POINTER(IoStatusBlock),
    wintypes.LPVOID,
    wintypes.ULONG,
    ctypes.c_int,
]
NT_SET_INFORMATION_FILE.restype = ctypes.c_long
RTL_NT_STATUS_TO_DOS_ERROR = NTDLL.RtlNtStatusToDosError
RTL_NT_STATUS_TO_DOS_ERROR.argtypes = [ctypes.c_long]
RTL_NT_STATUS_TO_DOS_ERROR.restype = wintypes.ULONG


ENERGY_EXPECTED_FILES = (
    "Copy_2_of_energy_zonghe2.mlx",
    "Copy_2_of_energy_zonghe3.mlx",
    "Copy_of_energy_zonghe2.mlx",
    "Copy_of_energy_zonghe3.mlx",
    "energy_zonghe.mlx",
    "energy_zonghe2.mlx",
    "energy_zonghe3.mlx",
    "energy.m",
    "EQ.mat",
    "luxvjie_cb_2.mlx",
    "luxvjie_cb_3.mlx",
    "luxvjie_cb_LQR2.mlx",
    "luxvjie_cb_LQR3.mlx",
    "luxvjie_guyan_2.mlx",
    "luxvjie_guyan_LQR2.mlx",
    "luxvjie_guyan_LQR3.mlx",
    "luxvjie_ori_LQR2.mlx",
    "luxvjie_ori_LQR3.mlx",
    "lvxvjie_guyan_2.slx",
    "lvxvjie_guyan_3.slx",
    "monicanshu_2_suoju.mlx",
    "monicanshu_2.mlx",
    "monicanshu_3_suoju.mlx",
    "monicanshu_3.mlx",
    "PDmonicanshu.m",
    "PDmonicanshu2.m",
    "PDmonicanshu3.m",
    "simulink_str_2.mlx",
    "simulink_str_3.mlx",
    "stab_3.mat",
    "tes.m",
    "test.slx",
    "untitled.mlx",
    "untitled2.mlx",
    "untitled3.mlx",
    "untitled4.mlx",
)


EXTRA_SOURCES = (
    (
        "theory",
        "thesis_pdf",
        PROJECT_ROOT
        / "figure"
        / "第3章_缩聚对试验精度的影响"
        / "原始来源副本"
        / "论文与答辩材料"
        / "梁禹手稿.pdf",
        "theory/梁禹手稿.pdf",
    ),
    (
        "manuscript",
        "manuscript_0824",
        Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript_0824.tex"),
        "manuscript/manuscript_0824.tex",
    ),
    (
        "central_baseline",
        "object_index_pre_board21",
        PROJECT_ROOT / "test" / "00_总索引与复现规则" / "全部对象总索引.csv",
        "central_baseline/全部对象总索引_板块21前.csv",
    ),
    (
        "central_baseline",
        "board15_source_manifest",
        PROJECT_ROOT / "test" / "00_总索引与复现规则" / "源文件冻结清单.csv",
        "central_baseline/源文件冻结清单.csv",
    ),
    (
        "central_baseline",
        "board15_source_recheck",
        PROJECT_ROOT / "test" / "00_总索引与复现规则" / "源文件冻结复核.csv",
        "central_baseline/源文件冻结复核.csv",
    ),
    (
        "prior_audit",
        "closure_audit_md",
        PROJECT_ROOT / "need-help" / "2026-08-18_推导案例闭环.md",
        "prior_audit/2026-08-18_推导案例闭环.md",
    ),
    (
        "prior_audit",
        "case_metrics_audit_py",
        PROJECT_ROOT / "need-help" / "audit_case_metrics.py",
        "prior_audit/audit_case_metrics.py",
    ),
    (
        "upstream_passport",
        "board16_artifact_manifest",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块16_参考模型候选路线"
        / "report"
        / "board16_artifact_manifest.csv",
        "upstream_passport/board16_artifact_manifest.csv",
    ),
    (
        "upstream_passport",
        "board16_validation_summary",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块16_参考模型候选路线"
        / "outputs"
        / "independent_validation_summary.json",
        "upstream_passport/board16_validation_summary.json",
    ),
    (
        "upstream_passport",
        "board17_artifact_manifest",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块17_两类划分与缩聚候选路线"
        / "report"
        / "board17_artifact_manifest.csv",
        "upstream_passport/board17_artifact_manifest.csv",
    ),
    (
        "upstream_passport",
        "board17_validation_summary",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块17_两类划分与缩聚候选路线"
        / "report"
        / "board17_final_validation_summary.json",
        "upstream_passport/board17_validation_summary.json",
    ),
    (
        "upstream_candidate",
        "board17_local_pd_reductions",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块17_两类划分与缩聚候选路线"
        / "outputs"
        / "local_pd_reductions.mat",
        "upstream_candidate/board17_local_pd_reductions.mat",
    ),
    (
        "upstream_passport",
        "board18_validation_summary",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块18_图3-5至图3-15逐图计算复现"
        / "outputs"
        / "final_validation"
        / "board18_final_validation_summary.json",
        "upstream_passport/board18_validation_summary.json",
    ),
    (
        "upstream_passport",
        "board19_validation_summary",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块19_表3-1至表3-3逐单元格计算复现"
        / "outputs"
        / "final_validation"
        / "board19_final_validation_summary.json",
        "upstream_passport/board19_validation_summary.json",
    ),
    (
        "upstream_passport",
        "board20_validation_summary",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
        / "outputs"
        / "step7_final_validation"
        / "validation_summary.json",
        "upstream_passport/board20_validation_summary.json",
    ),
    (
        "stability_evidence",
        "chapter4_historical_stability_statistics",
        PROJECT_ROOT
        / "figure"
        / "第4章_缩聚对试验稳定性的影响"
        / "输入数据"
        / "第4章稳定域统计.csv",
        "stability_evidence/第4章稳定域统计.csv",
    ),
    (
        "stability_evidence",
        "board20_stability_metrics",
        PROJECT_ROOT
        / "test"
        / "00_失败尝试与候选路线"
        / "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
        / "outputs"
        / "step6_history_comparison_run1"
        / "tables"
        / "stability_metrics.csv",
        "stability_evidence/board20_stability_metrics.csv",
    ),
)


FIELDNAMES = (
    "item_id",
    "category",
    "role",
    "source_absolute_path",
    "source_relative_label",
    "frozen_relative_path",
    "source_size_bytes",
    "source_sha256",
    "frozen_size_bytes",
    "frozen_sha256",
    "live_change_policy",
    "status",
)


def absolute_lexical(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def is_reparse_point(path: Path) -> bool:
    try:
        file_attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(file_attributes & REPARSE_POINT_ATTRIBUTE) or path.is_symlink()


def assert_no_reparse_chain(path: Path) -> None:
    absolute = absolute_lexical(path)
    components = tuple(reversed((absolute, *absolute.parents)))
    for component in components:
        if is_reparse_point(component):
            raise RuntimeError(f"Reparse point forbidden in protected path chain: {component}")


def lexical_is_within(path: Path, root: Path) -> bool:
    try:
        absolute_lexical(path).relative_to(absolute_lexical(root))
        return True
    except ValueError:
        return False


def normalized_windows_path(path: Path | str) -> str:
    return os.path.normcase(os.path.normpath(os.fspath(absolute_lexical(Path(path)))))


def final_path_from_handle(handle: int) -> Path:
    buffer = ctypes.create_unicode_buffer(32768)
    length = GET_FINAL_PATH_NAME_BY_HANDLE_W(handle, buffer, len(buffer), 0)
    if length == 0:
        raise ctypes.WinError(ctypes.get_last_error())
    if length >= len(buffer):
        raise RuntimeError("GetFinalPathNameByHandleW buffer unexpectedly too small")
    value = buffer.value
    if value.startswith("\\\\?\\UNC\\"):
        value = "\\\\" + value[8:]
    elif value.startswith("\\\\?\\"):
        value = value[4:]
    return absolute_lexical(Path(value))


def handle_identity(handle: int) -> tuple[int, int]:
    information = ByHandleFileInformation()
    if not GET_FILE_INFORMATION_BY_HANDLE(handle, ctypes.byref(information)):
        raise ctypes.WinError(ctypes.get_last_error())
    file_index = (int(information.nFileIndexHigh) << 32) | int(
        information.nFileIndexLow
    )
    return int(information.dwVolumeSerialNumber), file_index


def validate_handle(
    handle: int,
    expected_path: Path,
    *,
    require_directory: bool,
) -> tuple[int, int]:
    tag_information = FileAttributeTagInfo()
    if not GET_FILE_INFORMATION_BY_HANDLE_EX(
        handle,
        FILE_ATTRIBUTE_TAG_INFO_CLASS,
        ctypes.byref(tag_information),
        ctypes.sizeof(tag_information),
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    attributes = int(tag_information.FileAttributes)
    if attributes & REPARSE_POINT_ATTRIBUTE:
        raise RuntimeError(f"Reparse-point handle forbidden: {expected_path}")
    is_directory = bool(attributes & FILE_ATTRIBUTE_DIRECTORY)
    if is_directory != require_directory:
        raise RuntimeError(
            f"Handle type mismatch for {expected_path}: directory={is_directory}"
        )
    actual_path = final_path_from_handle(handle)
    if normalized_windows_path(actual_path) != normalized_windows_path(expected_path):
        raise RuntimeError(
            f"Handle final path mismatch: expected={expected_path}, actual={actual_path}"
        )
    return handle_identity(handle)


def validate_relative_name(name: str) -> None:
    if (
        not name
        or name in {".", ".."}
        or "/" in name
        or "\\" in name
        or ":" in name
        or Path(name).name != name
    ):
        raise RuntimeError(f"Unsafe relative NT file name: {name!r}")


def nt_open_relative_file(
    parent_handle: int,
    parent_path: Path,
    name: str,
    *,
    desired_access: int,
    share_access: int,
    create_disposition: int,
) -> tuple[int, tuple[int, int]]:
    validate_relative_name(name)
    name_buffer = ctypes.create_unicode_buffer(name)
    name_bytes = name.encode("utf-16-le")
    unicode_name = UnicodeString(
        len(name_bytes),
        len(name_bytes) + 2,
        ctypes.cast(name_buffer, wintypes.LPWSTR),
    )
    attributes = ObjectAttributes(
        ctypes.sizeof(ObjectAttributes),
        parent_handle,
        ctypes.pointer(unicode_name),
        OBJ_CASE_INSENSITIVE,
        None,
        None,
    )
    io_status = IoStatusBlock()
    result_handle = wintypes.HANDLE()
    status = NT_CREATE_FILE(
        ctypes.byref(result_handle),
        desired_access,
        ctypes.byref(attributes),
        ctypes.byref(io_status),
        None,
        FILE_ATTRIBUTE_NORMAL,
        share_access,
        create_disposition,
        FILE_NON_DIRECTORY_FILE
        | FILE_SYNCHRONOUS_IO_NONALERT
        | FILE_FLAG_OPEN_REPARSE_POINT,
        None,
        0,
    )
    if status < 0:
        error_code = int(RTL_NT_STATUS_TO_DOS_ERROR(status))
        raise OSError(error_code, os.strerror(error_code), name)
    handle = int(result_handle.value)
    expected_path = absolute_lexical(parent_path / name)
    try:
        identity = validate_handle(handle, expected_path, require_directory=False)
    except Exception:
        if create_disposition == FILE_CREATE:
            try:
                mark_handle_delete(handle)
            except OSError:
                pass
        CLOSE_HANDLE(handle)
        raise
    return handle, identity


def rename_handle_relative(
    file_handle: int,
    parent_handle: int,
    target_name: str,
    *,
    replace_if_exists: bool,
) -> None:
    validate_relative_name(target_name)
    encoded_name = target_name.encode("utf-16-le")
    filename_offset = FileRenameInfoHead.FileNameLength.offset + ctypes.sizeof(
        wintypes.DWORD
    )
    buffer = ctypes.create_string_buffer(filename_offset + len(encoded_name))
    head = FileRenameInfoHead.from_buffer(buffer)
    head.ReplaceIfExists = int(replace_if_exists)
    head.RootDirectory = parent_handle
    head.FileNameLength = len(encoded_name)
    ctypes.memmove(
        ctypes.addressof(buffer) + filename_offset,
        encoded_name,
        len(encoded_name),
    )
    io_status = IoStatusBlock()
    status = NT_SET_INFORMATION_FILE(
        file_handle,
        ctypes.byref(io_status),
        buffer,
        len(buffer),
        NATIVE_FILE_RENAME_INFORMATION_CLASS,
    )
    if status < 0:
        error_code = int(RTL_NT_STATUS_TO_DOS_ERROR(status))
        raise OSError(error_code, os.strerror(error_code), target_name)


def mark_handle_delete(file_handle: int) -> None:
    disposition = FileDispositionInfo(True)
    io_status = IoStatusBlock()
    status = NT_SET_INFORMATION_FILE(
        file_handle,
        ctypes.byref(io_status),
        ctypes.byref(disposition),
        ctypes.sizeof(disposition),
        NATIVE_FILE_DISPOSITION_INFORMATION_CLASS,
    )
    if status < 0:
        error_code = int(RTL_NT_STATUS_TO_DOS_ERROR(status))
        raise OSError(error_code, os.strerror(error_code))


def open_locked_directory(path: Path) -> tuple[int, tuple[int, int]]:
    absolute = absolute_lexical(path)
    handle = CREATE_FILE_W(
        str(absolute),
        FILE_READ_ATTRIBUTES | SYNCHRONIZE,
        FILE_SHARE_READ,
        None,
        OPEN_EXISTING,
        FILE_FLAG_BACKUP_SEMANTICS | FILE_FLAG_OPEN_REPARSE_POINT,
        None,
    )
    if handle == INVALID_HANDLE_VALUE:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        identity = validate_handle(handle, absolute, require_directory=True)
    except Exception:
        CLOSE_HANDLE(handle)
        raise
    return handle, identity


@contextmanager
def locked_full_ancestor_chain(parent: Path) -> Iterator[int]:
    absolute_parent = absolute_lexical(parent)
    components = tuple(reversed(absolute_parent.parents)) + (absolute_parent,)
    handles: list[tuple[int, Path, tuple[int, int]]] = []
    try:
        for component in components:
            if not component.is_dir():
                raise FileNotFoundError(
                    f"Secure I/O requires pre-existing directory chain: {component}"
                )
            handle, identity = open_locked_directory(component)
            handles.append((handle, component, identity))
        if not handles:
            raise RuntimeError(f"No directory handle acquired for: {absolute_parent}")
        for handle, component, identity in handles:
            if validate_handle(handle, component, require_directory=True) != identity:
                raise RuntimeError(
                    f"Directory identity changed before protected I/O: {component}"
                )
        yield handles[-1][0]
        for handle, component, identity in handles:
            if validate_handle(handle, component, require_directory=True) != identity:
                raise RuntimeError(f"Directory identity changed after protected I/O: {component}")
    finally:
        for handle, _, _ in reversed(handles):
            CLOSE_HANDLE(handle)


@contextmanager
def secure_read_stream(path: Path) -> Iterator[BinaryIO]:
    absolute = absolute_lexical(path)
    with locked_full_ancestor_chain(absolute.parent) as parent_handle:
        handle, identity = nt_open_relative_file(
            parent_handle,
            absolute.parent,
            absolute.name,
            desired_access=GENERIC_READ | SYNCHRONIZE,
            share_access=FILE_SHARE_READ,
            create_disposition=FILE_OPEN,
        )
        transferred = False
        descriptor = -1
        stream: BinaryIO | None = None
        try:
            descriptor = msvcrt.open_osfhandle(handle, os.O_RDONLY | os.O_BINARY)
            transferred = True
            stream = os.fdopen(descriptor, "rb")
            descriptor = -1
            yield stream
            stream.flush()
            if validate_handle(handle, absolute, require_directory=False) != identity:
                raise RuntimeError(f"Source file identity changed while locked: {absolute}")
        finally:
            if stream is not None:
                stream.close()
            elif descriptor >= 0:
                os.close(descriptor)
            elif not transferred:
                CLOSE_HANDLE(handle)


def secure_read_bytes(path: Path) -> bytes:
    with secure_read_stream(path) as stream:
        return stream.read()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with secure_read_stream(path) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def ensure_safe_directory(path: Path, allowed_root: Path) -> Path:
    absolute = absolute_lexical(path)
    allowed = absolute_lexical(allowed_root)
    board = absolute_lexical(BOARD_ROOT)
    if not lexical_is_within(absolute, allowed) or not lexical_is_within(allowed, board):
        raise RuntimeError(f"Directory escapes Board21 write boundary: {absolute}")
    with locked_full_ancestor_chain(absolute):
        assert_no_reparse_chain(absolute)
    return absolute


def assert_safe_write_target(path: Path, allowed_root: Path) -> Path:
    absolute = absolute_lexical(path)
    allowed = absolute_lexical(allowed_root)
    board = absolute_lexical(BOARD_ROOT)
    if not lexical_is_within(allowed, board):
        raise RuntimeError(f"Allowed root escapes Board21 root: {allowed}")
    if not lexical_is_within(absolute, allowed):
        raise RuntimeError(f"Write target escapes allowed root: {absolute}")
    if not allowed.is_dir() or not absolute.parent.is_dir():
        raise FileNotFoundError(f"Secure write directories must already exist: {absolute.parent}")
    assert_no_reparse_chain(absolute)
    return absolute


def safe_atomic_write_bytes(
    path: Path,
    payload: bytes,
    allowed_root: Path,
    *,
    require_missing: bool = False,
) -> None:
    target = assert_safe_write_target(path, allowed_root)
    with locked_full_ancestor_chain(target.parent) as parent_handle:
        target = assert_safe_write_target(target, allowed_root)
        temporary_name = f".{target.name}.{secrets.token_hex(16)}.tmp"
        temporary_handle, _ = nt_open_relative_file(
            parent_handle,
            target.parent,
            temporary_name,
            desired_access=GENERIC_READ
            | GENERIC_WRITE
            | DELETE_ACCESS
            | SYNCHRONIZE,
            share_access=0,
            create_disposition=FILE_CREATE,
        )
        transferred = False
        descriptor = -1
        renamed = False
        stream: BinaryIO | None = None
        try:
            descriptor = msvcrt.open_osfhandle(
                temporary_handle, os.O_RDWR | os.O_BINARY
            )
            transferred = True
            stream = os.fdopen(descriptor, "w+b")
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
            rename_handle_relative(
                temporary_handle,
                parent_handle,
                target.name,
                replace_if_exists=not require_missing,
            )
            renamed = True
            validate_handle(
                temporary_handle,
                target,
                require_directory=False,
            )
        finally:
            cleanup_error: Exception | None = None
            if not renamed:
                try:
                    mark_handle_delete(temporary_handle)
                except Exception as exc:
                    cleanup_error = exc
            if stream is not None:
                stream.close()
            elif descriptor >= 0:
                os.close(descriptor)
            elif not transferred:
                CLOSE_HANDLE(temporary_handle)
            if cleanup_error is not None:
                raise cleanup_error


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def source_label(path: Path) -> str:
    absolute = absolute_lexical(path)
    if lexical_is_within(absolute, PROJECT_ROOT):
        return "project/" + absolute.relative_to(absolute_lexical(PROJECT_ROOT)).as_posix()
    return absolute.as_posix()


def atomic_write_text(path: Path, text: str) -> None:
    safe_atomic_write_bytes(path, text.encode("utf-8"), INPUT_ROOT)


def atomic_write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=FIELDNAMES, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    safe_atomic_write_bytes(path, stream.getvalue().encode("utf-8"), INPUT_ROOT)


def build_catalogue() -> list[tuple[str, str, Path, str]]:
    if not ENERGY_ROOT.is_dir():
        raise FileNotFoundError(f"Author energy root missing: {ENERGY_ROOT}")
    assert_no_reparse_chain(ENERGY_ROOT)

    energy_members = tuple(ENERGY_ROOT.rglob("*"))
    for member in energy_members:
        assert_no_reparse_chain(member)
    actual_files = tuple(
        sorted(
            (path.relative_to(ENERGY_ROOT).as_posix() for path in energy_members if path.is_file()),
            key=str.casefold,
        )
    )
    expected_files = tuple(sorted(ENERGY_EXPECTED_FILES, key=str.casefold))
    actual_directories = tuple(path for path in energy_members if path.is_dir())
    if actual_files != expected_files:
        missing = sorted(set(ENERGY_EXPECTED_FILES) - set(actual_files))
        extra = sorted(set(actual_files) - set(ENERGY_EXPECTED_FILES))
        raise RuntimeError(f"Energy tree drift: missing={missing}, extra={extra}")
    if actual_directories:
        raise RuntimeError(f"Energy tree unexpectedly contains directories: {actual_directories}")

    catalogue: list[tuple[str, str, Path, str]] = []
    for relative in expected_files:
        catalogue.append(
            (
                "author_energy_tree",
                f"author_energy:{relative}",
                ENERGY_ROOT / relative,
                f"author_energy/{relative}",
            )
        )
    catalogue.extend(EXTRA_SOURCES)

    expected_categories = Counter(
        {
            "author_energy_tree": 36,
            "central_baseline": 3,
            "manuscript": 1,
            "prior_audit": 2,
            "stability_evidence": 2,
            "theory": 1,
            "upstream_candidate": 1,
            "upstream_passport": 7,
        }
    )
    actual_categories = Counter(item[0] for item in catalogue)
    if len(catalogue) != 53 or actual_categories != expected_categories:
        raise RuntimeError(
            f"Board21 catalogue invariant failed: count={len(catalogue)}, "
            f"categories={dict(actual_categories)}"
        )

    source_keys = [normalized_windows_path(item[2]) for item in catalogue]
    frozen_keys: list[str] = []
    for _, _, _, frozen_relative in catalogue:
        pure = PurePosixPath(frozen_relative)
        if (
            not frozen_relative
            or pure.is_absolute()
            or ".." in pure.parts
            or pure.as_posix() != frozen_relative
        ):
            raise RuntimeError(f"Unsafe or non-canonical frozen path: {frozen_relative}")
        canonical = absolute_lexical(INPUT_ROOT.joinpath(*pure.parts))
        if not lexical_is_within(canonical, INPUT_ROOT):
            raise RuntimeError(f"Frozen path escapes input root: {frozen_relative}")
        frozen_keys.append(str(canonical).casefold())
    if len(source_keys) != len(set(source_keys)):
        raise RuntimeError("Duplicate source path in Board21 catalogue")
    if len(frozen_keys) != len(set(frozen_keys)):
        raise RuntimeError("Duplicate frozen path in Board21 catalogue")
    return catalogue


def freeze() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    for relative in ("code", "input", "logs", "outputs", "report", "tmp"):
        ensure_safe_directory(BOARD_ROOT / relative, BOARD_ROOT)

    rows: list[dict[str, Any]] = []
    catalogue = build_catalogue()
    for index, (category, role, source, frozen_relative) in enumerate(catalogue, start=1):
        assert_no_reparse_chain(source)
        source = absolute_lexical(source)
        if not source.is_file():
            raise FileNotFoundError(f"Required Board21 input missing: {source}")
        if lexical_is_within(source, BOARD_ROOT):
            raise RuntimeError(f"Source must remain outside Board21 root: {source}")
        if category == "author_energy_tree":
            if normalized_windows_path(source.parent) != normalized_windows_path(ENERGY_ROOT):
                raise RuntimeError(f"Author energy source escaped exact source directory: {source}")

        destination = absolute_lexical(INPUT_ROOT / frozen_relative)
        if not lexical_is_within(destination, INPUT_ROOT):
            raise RuntimeError(f"Frozen destination escapes input root: {destination}")
        ensure_safe_directory(destination.parent, INPUT_ROOT)

        source_payload = secure_read_bytes(source)
        source_hash = hashlib.sha256(source_payload).hexdigest().upper()
        source_size = len(source_payload)
        if destination.exists():
            destination_hash = sha256_file(destination)
            destination_size = len(secure_read_bytes(destination))
            if destination_hash != source_hash or destination_size != source_size:
                raise RuntimeError(
                    f"Existing frozen copy differs from live source; refusing overwrite: {destination}"
                )
        else:
            safe_atomic_write_bytes(
                destination,
                source_payload,
                INPUT_ROOT,
                require_missing=True,
            )
        frozen_payload = secure_read_bytes(destination)
        frozen_hash = hashlib.sha256(frozen_payload).hexdigest().upper()
        frozen_size = len(frozen_payload)
        source_after = secure_read_bytes(source)
        if source_after != source_payload:
            raise RuntimeError(f"Source changed during Board21 freeze: {source}")

        rows.append(
            {
                "item_id": f"B21-{index:04d}",
                "category": category,
                "role": role,
                "source_absolute_path": str(source),
                "source_relative_label": source_label(source),
                "frozen_relative_path": destination.relative_to(INPUT_ROOT).as_posix(),
                "source_size_bytes": source_size,
                "source_sha256": source_hash,
                "frozen_size_bytes": frozen_size,
                "frozen_sha256": frozen_hash,
                "live_change_policy": "immutable",
                "status": "MATCH"
                if source_size == frozen_size and source_hash == frozen_hash
                else "MISMATCH",
            }
        )

    category_counts = dict(sorted(Counter(row["category"] for row in rows).items()))
    summary: dict[str, Any] = {
        "schema_version": "BOARD21_INPUT_FREEZE_V1",
        "status": "PASS" if all(row["status"] == "MATCH" for row in rows) else "FAIL",
        "input_count": len(rows),
        "author_energy_file_count": category_counts.get("author_energy_tree", 0),
        "category_counts": category_counts,
        "total_source_bytes": sum(int(row["source_size_bytes"]) for row in rows),
        "source_inside_board_root_count": sum(
            is_within(Path(str(row["source_absolute_path"])), BOARD_ROOT) for row in rows
        ),
        "source_frozen_match_count": sum(row["status"] == "MATCH" for row in rows),
    }
    atomic_write_csv(MANIFEST_PATH, rows)
    atomic_write_text(
        SUMMARY_PATH,
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    return rows, summary


def main() -> int:
    _, summary = freeze()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

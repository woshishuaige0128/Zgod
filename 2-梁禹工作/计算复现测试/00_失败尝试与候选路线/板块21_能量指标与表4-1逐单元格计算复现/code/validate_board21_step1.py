from __future__ import annotations

import csv
import ctypes
import hashlib
import io
import json
import msvcrt
import os
import secrets
import stat
import subprocess
import sys
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
SUMMARY_INPUT_PATH = INPUT_ROOT / "input_freeze_summary.json"
VALIDATION_ROOT = BOARD_ROOT / "outputs" / "step1_validation"
CHECKS_PATH = VALIDATION_ROOT / "checks.csv"
SUMMARY_PATH = VALIDATION_ROOT / "validation_summary.json"
ARTIFACT_MANIFEST_PATH = BOARD_ROOT / "outputs" / "step1_artifact_manifest.csv"
RACE_TEST_PATH = VALIDATION_ROOT / "relative_handle_race_test.json"
RACE_TEST_SCRIPT = BOARD_ROOT / "code" / "test_board21_relative_handle_race.py"
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


EXPECTED_ENERGY_FILES = (
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


FIXED_ROLE_HASHES = {
    "thesis_pdf": "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1",
    "manuscript_0824": "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76",
    "object_index_pre_board21": "E1BCE04ADB90E03EC74BE25647D643EE7578D92AE8E34EFAB2C507608897A839",
    "board15_source_manifest": "897C43D958ACB8CBC160F689847D4EB14EBCF425D08C251FC6AE6AFEF0BAD45A",
    "board15_source_recheck": "3E4FCE13603FD9AFE4741FA0F7023DB2016358E3ACA04EFEC0E7ECCC9420FB7B",
    "closure_audit_md": "D164FAC4E7990553BD29C5BD45234ADC1C2E3093408DB931196D1F4D2B71DE03",
    "case_metrics_audit_py": "A56203F55C99751058DFD7652D21CE5AB7F940D84F72D6550249C44366C46F44",
    "board16_artifact_manifest": "F18B2A4E18D27D21581AE05F88D380B12663E5EDE4368E03FF179D89A09C4A93",
    "board16_validation_summary": "E9303435C956C73D4D933D68EAA0870919EB820A620DD297B0AF561086817976",
    "board17_artifact_manifest": "43C29665D0E08EF4FFB8D9067B38F797797735EA382E7F5B004EA2637A787405",
    "board17_validation_summary": "AE580B5A25F89F68E257DADB0F243962F634248C035864EBC8F681C083AEBF4A",
    "board17_local_pd_reductions": "763C0BB0158F942E392246776D0B5D3926A71AFF69DB50473EFA41DE0263A36F",
    "board18_validation_summary": "236D5AC6BCB9FD9EBCC60F5D6FF4FDB1C87B788E445C7CF3AB733F20BAACD934",
    "board19_validation_summary": "9F3F11CAD44430F94F47420F25BB1E3585AF60BF107F5E451D79677BF735F6E6",
    "board20_validation_summary": "3EB7CC400C9B061055BE9632470E59689CBB24EED6934C03FB7AA92B018D0086",
    "chapter4_historical_stability_statistics": "4D46A8BC30700B5E4906142916C7EA45E73F3CE8C2F2A21467D61E306726C722",
    "board20_stability_metrics": "D092576E0C7D9D1264AA8A0953A88268341F51B1D6941A2FB47D0278982F3A05",
}


CRITICAL_ENERGY_HASHES = {
    "energy_zonghe.mlx": "BCEDEF1887ABEE046A3018EB746B2088B0D63F9ACC917B9B4A78D97DEC84159D",
    "energy_zonghe2.mlx": "A84F903A5163AC0792FEA6BD0222003B3D2E1ED12B4D1B2CD6EABF325CA5CAAD",
    "Copy_of_energy_zonghe2.mlx": "80C4B3FE2A860552054D8FCEABA40365C5EE646BBB2EB21C9AF68E81AFE4715D",
    "Copy_2_of_energy_zonghe2.mlx": "8EBC3ACBD47B1D112395D4DCD951FE018F71A857E604187B443A2BFD572ADA66",
    "energy_zonghe3.mlx": "1F3B84A542AF40563F05C23402C2355345100D38A94D8EF130D5545A33D36614",
    "Copy_of_energy_zonghe3.mlx": "C067893CE26DA706774A886523F9000A2A0779268BB12A93A21E0EF0034296AC",
    "Copy_2_of_energy_zonghe3.mlx": "446840E932376D1F16B05A16EC8DEA2D8CA5CB733AE6448E64337306CCC7A98D",
    "monicanshu_2_suoju.mlx": "1F885E0971033EBCB8632110EC5A47DA507126C718A80176FF3347B2ED6A08C5",
    "monicanshu_3_suoju.mlx": "D7AC9307B1A07D7AA442FDF37E7882BAE3EC519C021A5A317FFE9D9374E70D01",
    "lvxvjie_guyan_2.slx": "CC8F41338ADBF5C29BF1933D4CF885741FCC76EDFF97E9B53104BBD968BCB542",
    "lvxvjie_guyan_3.slx": "569AD4685A02A75BF26985C74BD611C0E83C1120A34AA522DB6AAA11B375B680",
}


REQUIRED_MANIFEST_COLUMNS = {
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
}

EXPECTED_CATEGORY_COUNTS = {
    "author_energy_tree": 36,
    "central_baseline": 3,
    "manuscript": 1,
    "prior_audit": 2,
    "stability_evidence": 2,
    "theory": 1,
    "upstream_candidate": 1,
    "upstream_passport": 7,
}

EXPECTED_EXTERNAL_BINDINGS = (
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
    for component in reversed((absolute, *absolute.parents)):
        if is_reparse_point(component):
            raise RuntimeError(f"Reparse point forbidden in protected path chain: {component}")


def nofollow_entry_flags(entry: os.DirEntry[str]) -> tuple[bool, bool, bool]:
    information = entry.stat(follow_symlinks=False)
    attributes = int(getattr(information, "st_file_attributes", 0))
    is_reparse = bool(attributes & REPARSE_POINT_ATTRIBUTE) or entry.is_symlink()
    is_directory = bool(attributes & FILE_ATTRIBUTE_DIRECTORY) or stat.S_ISDIR(
        information.st_mode
    )
    is_regular_file = stat.S_ISREG(information.st_mode) and not is_reparse
    return is_directory, is_reparse, is_regular_file


def find_named_directory_or_reparse_entries(root: Path, prefix: str) -> list[Path]:
    root = absolute_lexical(root)
    matches: list[Path] = []
    pending = [root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as iterator:
            entries = sorted(tuple(iterator), key=lambda item: item.name.casefold())
        for entry in entries:
            path = absolute_lexical(Path(entry.path))
            is_directory, is_reparse, _ = nofollow_entry_flags(entry)
            if entry.name.startswith(prefix) and (is_directory or is_reparse):
                matches.append(path)
            if is_directory and not is_reparse:
                pending.append(path)
    return sorted(matches, key=lambda item: item.as_posix().casefold())


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


def secure_csv_rows(path: Path) -> tuple[list[dict[str, str]], set[str]]:
    text = secure_read_bytes(path).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text, newline=""))
    rows = list(reader)
    return rows, set(reader.fieldnames or [])


def hash_and_size_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with secure_read_stream(path) as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest().upper(), size


def sha256_file(path: Path) -> str:
    return hash_and_size_file(path)[0]


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


def safe_atomic_write_bytes(path: Path, payload: bytes, allowed_root: Path) -> None:
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
                replace_if_exists=True,
            )
            renamed = True
            validate_handle(temporary_handle, target, require_directory=False)
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


def add_check(
    checks: list[dict[str, str]],
    check_id: str,
    category: str,
    passed: bool,
    expected: Any,
    actual: Any,
    detail: str,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "category": category,
            "status": "PASS" if passed else "FAIL",
            "expected": str(expected),
            "actual": str(actual),
            "detail": detail,
        }
    )


def load_manifest() -> tuple[list[dict[str, str]], set[str]]:
    if not MANIFEST_PATH.is_file():
        return [], set()
    return secure_csv_rows(MANIFEST_PATH)


def validate_manifest(checks: list[dict[str, str]]) -> list[dict[str, str]]:
    rows, columns = load_manifest()
    add_check(
        checks,
        "S1-0001",
        "manifest_schema",
        REQUIRED_MANIFEST_COLUMNS.issubset(columns),
        sorted(REQUIRED_MANIFEST_COLUMNS),
        sorted(columns),
        "Input manifest contains all required columns",
    )
    add_check(
        checks,
        "S1-0002",
        "manifest_count",
        len(rows) == 53,
        53,
        len(rows),
        "36 author energy files plus 17 fixed evidence bindings",
    )

    ids = [row.get("item_id", "") for row in rows]
    roles = [row.get("role", "") for row in rows]
    sources = [row.get("source_absolute_path", "").casefold() for row in rows]
    frozen = [row.get("frozen_relative_path", "").casefold() for row in rows]
    for offset, (label, values) in enumerate(
        (("item_id", ids), ("role", roles), ("source", sources), ("frozen", frozen)),
        start=3,
    ):
        add_check(
            checks,
            f"S1-{offset:04d}",
            "manifest_uniqueness",
            len(values) == len(set(values)) and all(values),
            "all unique and non-empty",
            f"unique={len(set(values))}, total={len(values)}",
            f"Manifest {label} values are unique",
        )

    for index, row in enumerate(rows, start=1):
        source = Path(row.get("source_absolute_path", ""))
        frozen_rel = row.get("frozen_relative_path", "")
        pure_rel = PurePosixPath(frozen_rel)
        frozen_path = INPUT_ROOT.joinpath(*pure_rel.parts)
        expected_source_hash = row.get("source_sha256", "").upper()
        expected_frozen_hash = row.get("frozen_sha256", "").upper()
        try:
            expected_source_size = int(row.get("source_size_bytes", ""))
            expected_frozen_size = int(row.get("frozen_size_bytes", ""))
        except ValueError:
            expected_source_size = -1
            expected_frozen_size = -2

        source_exists = source.is_file()
        frozen_exists = frozen_path.is_file()
        if source_exists:
            source_hash, source_size = hash_and_size_file(source)
        else:
            source_hash, source_size = "MISSING", -1
        if frozen_exists:
            frozen_hash, frozen_size = hash_and_size_file(frozen_path)
        else:
            frozen_hash, frozen_size = "MISSING", -1
        safe_relative = bool(frozen_rel) and not pure_rel.is_absolute() and ".." not in pure_rel.parts
        passed = all(
            (
                source_exists,
                frozen_exists,
                not is_within(source, BOARD_ROOT) if source_exists else False,
                safe_relative,
                is_within(frozen_path, INPUT_ROOT),
                source_hash == expected_source_hash,
                frozen_hash == expected_frozen_hash,
                source_hash == frozen_hash,
                source_size == expected_source_size,
                frozen_size == expected_frozen_size,
                row.get("status") == "MATCH",
                row.get("live_change_policy") == "immutable",
            )
        )
        if source_exists and frozen_exists:
            try:
                passed = passed and not os.path.samefile(source, frozen_path)
            except OSError:
                passed = False
        add_check(
            checks,
            f"S1-MANIFEST-{index:04d}",
            "manifest_binding",
            passed,
            "live source and independent frozen copy byte-identical",
            f"source={source_hash}, frozen={frozen_hash}",
            row.get("role", ""),
        )
    return rows


def validate_exact_role_bindings(
    checks: list[dict[str, str]], rows: list[dict[str, str]]
) -> None:
    expected_bindings: list[tuple[str, str, Path, str]] = []
    for name in sorted(EXPECTED_ENERGY_FILES, key=str.casefold):
        expected_bindings.append(
            (
                "author_energy_tree",
                f"author_energy:{name}",
                ENERGY_ROOT / name,
                f"author_energy/{name}",
            )
        )
    expected_bindings.extend(EXPECTED_EXTERNAL_BINDINGS)
    if len(expected_bindings) != 53:
        raise RuntimeError(
            f"Independent expected-binding contract must contain 53 entries, got {len(expected_bindings)}"
        )

    row_by_role = {row.get("role", ""): row for row in rows}
    for index, (category, role, source, frozen_relative) in enumerate(
        expected_bindings, start=1
    ):
        row = row_by_role.get(role)
        expected_source = str(absolute_lexical(source))
        actual_source = row.get("source_absolute_path", "") if row else "MISSING"
        source_matches = (
            actual_source.casefold() == expected_source.casefold()
            and normalized_windows_path(actual_source)
            == normalized_windows_path(expected_source)
        )
        author_name_matches = True
        if category == "author_energy_tree":
            name = role.removeprefix("author_energy:")
            author_name_matches = (
                Path(actual_source).name == name
                and PurePosixPath(frozen_relative).name == name
            )
        required_hash = FIXED_ROLE_HASHES.get(role)
        fixed_hash_matches = (
            True
            if required_hash is None
            else bool(row)
            and row.get("source_sha256", "").upper() == required_hash
        )
        passed = bool(row) and all(
            (
                row.get("item_id") == f"B21-{index:04d}",
                row.get("category") == category,
                source_matches,
                row.get("frozen_relative_path") == frozen_relative,
                author_name_matches,
                fixed_hash_matches,
            )
        )
        add_check(
            checks,
            f"S1-EXACT-BINDING-{index:04d}",
            "exact_role_binding",
            passed,
            f"B21-{index:04d}|{category}|{role}|{expected_source}|{frozen_relative}",
            (
                "MISSING"
                if row is None
                else "|".join(
                    (
                        row.get("item_id", ""),
                        row.get("category", ""),
                        row.get("role", ""),
                        row.get("source_absolute_path", ""),
                        row.get("frozen_relative_path", ""),
                    )
                )
            ),
            "Independent role/category/source/frozen-path identity contract",
        )


def validate_seal_hygiene(checks: list[dict[str, str]]) -> None:
    forbidden: list[str] = []
    for path in BOARD_ROOT.rglob("*"):
        relative = path.relative_to(BOARD_ROOT)
        if path.is_file() and (
            path.name.casefold().endswith((".tmp", ".copytmp"))
            or (relative.parts and relative.parts[0].casefold() == "tmp")
        ):
            forbidden.append(relative.as_posix())
    add_check(
        checks,
        "S1-SEAL-HYGIENE",
        "artifact_seal_hygiene",
        not forbidden,
        "no files under Board21/tmp and no temporary files; every cache file is included",
        "none" if not forbidden else "|".join(sorted(forbidden)),
        "Artifact manifest excludes only itself and includes any __pycache__/pyc files",
    )


def validate_filesystem_safety(checks: list[dict[str, str]]) -> bool:
    reparse_paths: list[str] = []
    if is_reparse_point(BOARD_ROOT):
        reparse_paths.append(str(BOARD_ROOT))
    for directory, directory_names, file_names in os.walk(
        BOARD_ROOT, topdown=True, followlinks=False
    ):
        directory_path = Path(directory)
        retained_directories: list[str] = []
        for name in directory_names:
            candidate = directory_path / name
            if is_reparse_point(candidate):
                reparse_paths.append(str(candidate))
            else:
                retained_directories.append(name)
        directory_names[:] = retained_directories
        for name in file_names:
            candidate = directory_path / name
            if is_reparse_point(candidate):
                reparse_paths.append(str(candidate))
    add_check(
        checks,
        "S1-FILESYSTEM-SAFETY",
        "filesystem_write_boundary",
        not reparse_paths,
        0,
        len(reparse_paths),
        "Board21 root contains no symlink, junction, or reparse point: "
        + " | ".join(reparse_paths),
    )
    return not reparse_paths


def validate_freeze_summary_and_input_tree(
    checks: list[dict[str, str]], rows: list[dict[str, str]]
) -> None:
    try:
        actual_summary = json.loads(secure_read_bytes(SUMMARY_INPUT_PATH).decode("utf-8"))
    except (
        FileNotFoundError,
        json.JSONDecodeError,
        OSError,
        RuntimeError,
        UnicodeDecodeError,
    ) as exc:
        actual_summary = {"READ_ERROR": str(exc)}

    category_counts = dict(
        sorted(Counter(row.get("category", "") for row in rows).items())
    )
    expected_summary = {
        "schema_version": "BOARD21_INPUT_FREEZE_V1",
        "status": "PASS",
        "input_count": 53,
        "author_energy_file_count": 36,
        "category_counts": dict(sorted(EXPECTED_CATEGORY_COUNTS.items())),
        "total_source_bytes": sum(
            int(row.get("source_size_bytes", "-1"))
            if row.get("source_size_bytes", "").isdigit()
            else -1
            for row in rows
        ),
        "source_inside_board_root_count": sum(
            is_within(Path(row.get("source_absolute_path", "")), BOARD_ROOT)
            for row in rows
        ),
        "source_frozen_match_count": sum(row.get("status") == "MATCH" for row in rows),
    }
    summary_passed = (
        actual_summary == expected_summary
        and category_counts == dict(sorted(EXPECTED_CATEGORY_COUNTS.items()))
    )
    add_check(
        checks,
        "S1-FREEZE-SUMMARY",
        "freeze_summary_semantics",
        summary_passed,
        json.dumps(expected_summary, ensure_ascii=False, sort_keys=True),
        json.dumps(actual_summary, ensure_ascii=False, sort_keys=True),
        "Freeze summary is independently derived from the 53 manifest rows",
    )

    expected_input_files = {
        row.get("frozen_relative_path", "").casefold() for row in rows
    } | {
        MANIFEST_PATH.relative_to(INPUT_ROOT).as_posix().casefold(),
        SUMMARY_INPUT_PATH.relative_to(INPUT_ROOT).as_posix().casefold(),
    }
    actual_input_files = {
        path.relative_to(INPUT_ROOT).as_posix().casefold()
        for path in INPUT_ROOT.rglob("*")
        if path.is_file()
    }
    add_check(
        checks,
        "S1-INPUT-TREE-EXACT",
        "input_tree_exactness",
        actual_input_files == expected_input_files,
        sorted(expected_input_files),
        sorted(actual_input_files),
        "Input tree contains exactly 53 frozen files plus manifest and summary",
    )


def validate_residual_processes(checks: list[dict[str, str]]) -> list[str]:
    command = ["tasklist.exe", "/FO", "CSV", "/NH"]
    try:
        completed = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        decoded = completed.stdout.decode("utf-8", errors="replace")
        residual: list[str] = []
        targets = {"matlab.exe", "python.exe", "pythonw.exe", "pdftoppm.exe"}
        for row in csv.reader(io.StringIO(decoded)):
            if len(row) < 2:
                continue
            image_name = row[0].strip().casefold()
            try:
                process_id = int(row[1].strip())
            except ValueError:
                continue
            if image_name in targets and process_id != os.getpid():
                residual.append(f"{image_name}:{process_id}")
        passed = completed.returncode == 0 and not residual
        detail = (
            f"tasklist_returncode={completed.returncode}; residual="
            + ("|".join(sorted(residual)) if residual else "none")
        )
    except OSError as exc:
        residual = [f"PROCESS_QUERY_ERROR:{exc}"]
        passed = False
        detail = residual[0]
    add_check(
        checks,
        "S1-RESIDUAL-PROCESSES",
        "residual_process_boundary",
        passed,
        "no MATLAB/python/pythonw/pdftoppm except current validator process",
        "none" if not residual else "|".join(sorted(residual)),
        detail,
    )
    return residual


def validate_relative_handle_race_evidence(checks: list[dict[str, str]]) -> str:
    first_local_check = len(checks)
    try:
        with secure_read_stream(RACE_TEST_PATH) as stream:
            evidence = json.loads(stream.read().decode("utf-8"))
    except (OSError, RuntimeError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        add_check(
            checks,
            "S1-RACE-EVIDENCE-READ",
            "relative_handle_race",
            False,
            "readable BOARD21_RELATIVE_HANDLE_RACE_TEST_V1 evidence",
            f"{type(exc).__name__}: {exc}",
            str(RACE_TEST_PATH),
        )
        return "FAIL"

    schema = evidence.get("schema_version")
    overall_status = evidence.get("overall_status")
    module_results = evidence.get("module_results", [])
    by_role = {
        item.get("module_role"): item
        for item in module_results
        if isinstance(item, dict) and isinstance(item.get("module_role"), str)
    }
    add_check(
        checks,
        "S1-RACE-SCHEMA",
        "relative_handle_race",
        schema == "BOARD21_RELATIVE_HANDLE_RACE_TEST_V1",
        "BOARD21_RELATIVE_HANDLE_RACE_TEST_V1",
        schema,
        "Security race-test evidence schema",
    )
    add_check(
        checks,
        "S1-RACE-OVERALL",
        "relative_handle_race",
        overall_status == "PASS",
        "PASS",
        overall_status,
        "Both independent Board21 I/O implementations pass all three attack timings",
    )
    add_check(
        checks,
        "S1-RACE-ROLESET",
        "relative_handle_race",
        set(by_role) == {"freeze", "validator"},
        ["freeze", "validator"],
        sorted(by_role),
        "Exact implementation roles covered by the race test",
    )

    expected_modules = {
        "freeze": BOARD_ROOT / "code" / "freeze_board21_inputs.py",
        "validator": BOARD_ROOT / "code" / "validate_board21_step1.py",
    }
    expected_timings = {
        "during_ancestor_chain_acquisition",
        "before_temporary_open",
        "after_temporary_open",
    }
    for role, module_path in expected_modules.items():
        item = by_role.get(role, {})
        expected_relative = module_path.relative_to(BOARD_ROOT).as_posix()
        actual_relative = item.get("module_relative_path", "MISSING")
        add_check(
            checks,
            f"S1-RACE-{role.upper()}-PATH",
            "relative_handle_race",
            actual_relative == expected_relative,
            expected_relative,
            actual_relative,
            "Race evidence binds the exact implementation path",
        )
        expected_hash = sha256_file(module_path)
        actual_hash = item.get("module_sha256", "MISSING")
        add_check(
            checks,
            f"S1-RACE-{role.upper()}-HASH",
            "relative_handle_race",
            actual_hash == expected_hash,
            expected_hash,
            actual_hash,
            "Race evidence binds the current implementation bytes",
        )
        scenarios = item.get("scenarios", [])
        scenario_map = {
            scenario.get("timing"): scenario
            for scenario in scenarios
            if isinstance(scenario, dict)
            and isinstance(scenario.get("timing"), str)
        }
        actual_timing_status = {
            timing: scenario_map.get(timing, {}).get("status", "MISSING")
            for timing in expected_timings
        }
        add_check(
            checks,
            f"S1-RACE-{role.upper()}-TIMINGS",
            "relative_handle_race",
            set(scenario_map) == expected_timings
            and all(status == "PASS" for status in actual_timing_status.values()),
            {timing: "PASS" for timing in sorted(expected_timings)},
            {timing: actual_timing_status[timing] for timing in sorted(expected_timings)},
            "Directory replacement is safe during chain acquisition and before/after temporary-file open",
        )
        add_check(
            checks,
            f"S1-RACE-{role.upper()}-STATUS",
            "relative_handle_race",
            item.get("status") == "PASS",
            "PASS",
            item.get("status", "MISSING"),
            "Implementation-level race-test status",
        )
    boundary_protocol = evidence.get("boundary_protocol_result", {})
    boundary_checks = boundary_protocol.get("checks", {})
    add_check(
        checks,
        "S1-DANGLING-JUNCTION-PROTOCOL",
        "nofollow_boundary_protocol",
        boundary_protocol.get("status") == "PASS"
        and boundary_checks
        and all(value is True for value in boundary_checks.values()),
        "PASS with every dangling-junction check true",
        {
            "status": boundary_protocol.get("status", "MISSING"),
            "checks": boundary_checks,
        },
        "Real Windows junction is made dangling; lexists and no-follow name scan must still detect it",
    )
    local_checks = checks[first_local_check:]
    return (
        "PASS"
        if local_checks and all(check["status"] == "PASS" for check in local_checks)
        else "FAIL"
    )


def run_relative_handle_race_probe(checks: list[dict[str, str]]) -> bool:
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    try:
        completed = subprocess.run(
            [sys.executable, str(RACE_TEST_SCRIPT)],
            cwd=str(PROJECT_ROOT),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        stdout_text = completed.stdout.decode("utf-8", errors="replace").strip()
        stderr_text = completed.stderr.decode("utf-8", errors="replace").strip()
        try:
            child_summary = json.loads(stdout_text) if stdout_text else {}
        except json.JSONDecodeError:
            child_summary = {}
        passed = (
            completed.returncode == 0
            and child_summary.get("schema_version")
            == "BOARD21_RELATIVE_HANDLE_RACE_TEST_V1"
            and child_summary.get("overall_status") == "PASS"
        )
        actual = {
            "returncode": completed.returncode,
            "schema_version": child_summary.get("schema_version", "MISSING"),
            "overall_status": child_summary.get("overall_status", "MISSING"),
            "stderr_empty": not stderr_text,
        }
        detail = (
            "Dynamic child process executed all three attack timings for both current "
            "implementations; stderr=" + (stderr_text[:500] if stderr_text else "none")
        )
    except OSError as exc:
        passed = False
        actual = {"error": f"{type(exc).__name__}: {exc}"}
        detail = "Unable to execute dynamic relative-handle race probe"
    add_check(
        checks,
        "S1-RACE-EXEC",
        "relative_handle_race",
        passed,
        {
            "returncode": 0,
            "schema_version": "BOARD21_RELATIVE_HANDLE_RACE_TEST_V1",
            "overall_status": "PASS",
        },
        actual,
        detail,
    )
    return passed


def validate_energy_tree(
    checks: list[dict[str, str]], rows: list[dict[str, str]]
) -> None:
    with os.scandir(ENERGY_ROOT) as iterator:
        entries = sorted(tuple(iterator), key=lambda item: item.name.casefold())
    actual_files: list[str] = []
    unexpected_entries: list[str] = []
    for entry in entries:
        is_directory, is_reparse, is_regular_file = nofollow_entry_flags(entry)
        if is_regular_file:
            actual_files.append(entry.name)
        else:
            kinds = []
            if is_directory:
                kinds.append("directory")
            if is_reparse:
                kinds.append("reparse")
            if not kinds:
                kinds.append("non_regular")
            unexpected_entries.append(f"{entry.name}[{'+'.join(kinds)}]")
    actual_files_tuple = tuple(sorted(actual_files, key=str.casefold))
    expected_files = tuple(sorted(EXPECTED_ENERGY_FILES, key=str.casefold))
    add_check(
        checks,
        "S1-ENERGY-TREE",
        "author_energy_tree",
        actual_files_tuple == expected_files and not unexpected_entries,
        list(expected_files),
        {
            "regular_files": list(actual_files_tuple),
            "unexpected_entries": unexpected_entries,
        },
        "No-follow exact entry gate; directories, dangling junctions and all reparse entries fail",
    )
    energy_rows = [row for row in rows if row.get("category") == "author_energy_tree"]
    energy_roles = {
        row.get("role", "").removeprefix("author_energy:") for row in energy_rows
    }
    add_check(
        checks,
        "S1-ENERGY-MANIFEST",
        "author_energy_tree",
        len(energy_rows) == 36 and energy_roles == set(EXPECTED_ENERGY_FILES),
        "36 exact author energy files",
        f"count={len(energy_rows)}, unique={len(energy_roles)}",
        "Manifest coverage of the complete author energy directory",
    )

    role_map = {row.get("role", ""): row for row in rows}
    for index, (name, expected_hash) in enumerate(
        sorted(CRITICAL_ENERGY_HASHES.items()), start=1
    ):
        role = f"author_energy:{name}"
        row = role_map.get(role)
        actual = row.get("source_sha256", "").upper() if row else "MISSING"
        add_check(
            checks,
            f"S1-CRITICAL-{index:02d}",
            "critical_author_hash",
            actual == expected_hash,
            expected_hash,
            actual,
            name,
        )


def validate_fixed_roles(
    checks: list[dict[str, str]], rows: list[dict[str, str]]
) -> None:
    role_map = {row.get("role", ""): row for row in rows}
    for index, (role, expected_hash) in enumerate(
        FIXED_ROLE_HASHES.items(), start=1
    ):
        row = role_map.get(role)
        actual = row.get("source_sha256", "").upper() if row else "MISSING"
        add_check(
            checks,
            f"S1-FIXED-{index:02d}",
            "fixed_evidence_hash",
            actual == expected_hash,
            expected_hash,
            actual,
            role,
        )


def validate_central_326(checks: list[dict[str, str]]) -> int:
    baseline = PROJECT_ROOT / "test" / "00_总索引与复现规则" / "源文件冻结清单.csv"
    rows, _ = secure_csv_rows(baseline)
    add_check(
        checks,
        "S1-CENTRAL-COUNT",
        "central_source_protection",
        len(rows) == 326,
        326,
        len(rows),
        "Board15 central protected source count",
    )
    passed_count = 0
    for index, row in enumerate(rows, start=1):
        path = Path(row.get("绝对路径", ""))
        expected_hash = row.get("SHA256", "").upper()
        try:
            expected_size = int(row.get("文件大小_字节", ""))
        except ValueError:
            expected_size = -1
        exists = path.is_file()
        if exists:
            actual_hash, actual_size = hash_and_size_file(path)
        else:
            actual_hash, actual_size = "MISSING", -1
        passed = exists and actual_hash == expected_hash and actual_size == expected_size
        passed_count += int(passed)
        add_check(
            checks,
            f"S1-CENTRAL-{index:04d}",
            "central_source_protection",
            passed,
            f"{expected_hash}|{expected_size}",
            f"{actual_hash}|{actual_size}",
            row.get("相对路径", ""),
        )
    return passed_count


def validate_object_boundaries(
    checks: list[dict[str, str]],
) -> tuple[int, int, int, dict[str, str], str]:
    index_path = PROJECT_ROOT / "test" / "00_总索引与复现规则" / "全部对象总索引.csv"
    frozen_index = INPUT_ROOT / "central_baseline" / "全部对象总索引_板块21前.csv"
    live_hash = sha256_file(index_path) if index_path.is_file() else "MISSING"
    frozen_hash = sha256_file(frozen_index) if frozen_index.is_file() else "MISSING"
    add_check(
        checks,
        "S1-INDEX-BYTE",
        "object_index_baseline",
        live_hash == frozen_hash == FIXED_ROLE_HASHES["object_index_pre_board21"],
        FIXED_ROLE_HASHES["object_index_pre_board21"],
        f"live={live_hash}, frozen={frozen_hash}",
        "Central object index remains byte-identical during Step1",
    )
    rows, _ = secure_csv_rows(index_path)
    by_id = {row.get("对象ID", ""): row for row in rows}
    evidence_levels: dict[str, str] = {}
    for object_id in ("T4-1", "C06"):
        row = by_id.get(object_id)
        evidence_levels[object_id] = (
            row.get("当前证据等级", "MISSING") if row else "MISSING"
        )
        passed = bool(row) and row.get("当前证据等级") == "历史值"
        add_check(
            checks,
            f"S1-INDEX-{object_id}",
            "object_index_baseline",
            passed,
            "当前证据等级=历史值",
            row.get("当前证据等级", "MISSING") if row else "MISSING",
            object_id,
        )

    object_names = (
        "表4-1_两类划分Guyan与Craig--Bampton能量变化率",
        "结论C06_能量变化率稳定风险阈值",
    )
    success_count = 0
    failure_count = 0
    for index, name in enumerate(object_names, start=1):
        success = PROJECT_ROOT / "test" / name
        failure = PROJECT_ROOT / "test" / "00_失败尝试与候选路线" / name
        success_present = os.path.lexists(success)
        failure_present = os.path.lexists(failure)
        success_count += int(success_present)
        failure_count += int(failure_present)
        add_check(
            checks,
            f"S1-DIR-SUCCESS-{index}",
            "object_directory_boundary",
            not success_present,
            "absent",
            "present" if success_present else "absent",
            str(success),
        )
        add_check(
            checks,
            f"S1-DIR-FAILURE-{index}",
            "object_directory_boundary",
            not failure_present,
            "absent until publication",
            "present" if failure_present else "absent",
            str(failure),
        )

    board22_roots = find_named_directory_or_reparse_entries(
        PROJECT_ROOT / "test", "板块22"
    )
    add_check(
        checks,
        "S1-BOARD22",
        "next_board_boundary",
        not board22_roots,
        0,
        len(board22_roots),
        "No directory under test may have a name beginning with 板块22 during Step1",
    )
    return len(board22_roots), success_count, failure_count, evidence_levels, live_hash


def atomic_write_text(path: Path, text: str, allowed_root: Path) -> None:
    safe_atomic_write_bytes(path, text.encode("utf-8"), allowed_root)


def write_checks(checks: list[dict[str, str]]) -> None:
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=("check_id", "category", "status", "expected", "actual", "detail"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(checks)
    safe_atomic_write_bytes(
        CHECKS_PATH, stream.getvalue().encode("utf-8"), VALIDATION_ROOT
    )


def write_artifact_manifest() -> None:
    rows: list[dict[str, Any]] = []
    for path in sorted(BOARD_ROOT.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file():
            continue
        relative = path.relative_to(BOARD_ROOT)
        if path.resolve() == ARTIFACT_MANIFEST_PATH.resolve():
            continue
        file_hash, file_size = hash_and_size_file(path)
        rows.append(
            {
                "relative_path": relative.as_posix(),
                "size_bytes": file_size,
                "sha256": file_hash,
            }
        )
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(
        stream,
        fieldnames=("relative_path", "size_bytes", "sha256"),
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    safe_atomic_write_bytes(
        ARTIFACT_MANIFEST_PATH,
        stream.getvalue().encode("utf-8"),
        BOARD_ROOT / "outputs",
    )


def main() -> int:
    checks: list[dict[str, str]] = []
    if not validate_filesystem_safety(checks):
        print(
            json.dumps(
                {
                    "schema_version": "BOARD21_STEP1_VALIDATION_V2",
                    "overall_status": "FAIL",
                    "reason": "reparse point detected inside Board21 root; no files written",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 1
    validate_seal_hygiene(checks)
    rows = validate_manifest(checks)
    validate_exact_role_bindings(checks, rows)
    validate_freeze_summary_and_input_tree(checks, rows)
    validate_energy_tree(checks, rows)
    validate_fixed_roles(checks, rows)
    race_probe_passed = run_relative_handle_race_probe(checks)
    race_evidence_status = validate_relative_handle_race_evidence(checks)
    race_test_status = (
        "PASS" if race_probe_passed and race_evidence_status == "PASS" else "FAIL"
    )
    protected_count = validate_central_326(checks)
    (
        board22_root_count,
        success_directory_count,
        failure_directory_count,
        evidence_levels,
        live_index_hash,
    ) = validate_object_boundaries(checks)
    residual_processes = validate_residual_processes(checks)

    status_counts = Counter(check["status"] for check in checks)
    role_map = {row.get("role", ""): row for row in rows}
    summary = {
        "schema_version": "BOARD21_STEP1_VALIDATION_V2",
        "overall_status": "PASS" if status_counts.get("FAIL", 0) == 0 else "FAIL",
        "check_summary": {
            "total": len(checks),
            "pass": status_counts.get("PASS", 0),
            "fail": status_counts.get("FAIL", 0),
        },
        "input_count": len(rows),
        "author_energy_file_count": sum(
            row.get("category") == "author_energy_tree" for row in rows
        ),
        "central_protected_source_match_count": protected_count,
        "formal_success_directory_count": success_directory_count,
        "prepublication_failure_directory_count": failure_directory_count,
        "board22_named_root_count": board22_root_count,
        "board22_named_root_started": board22_root_count > 0,
        "board22_boundary_scope": "directories under test whose names start with 板块22",
        "residual_target_process_count": len(residual_processes),
        "relative_handle_race_status": race_test_status,
        "evidence_levels": evidence_levels,
        "thesis_sha256": role_map.get("thesis_pdf", {}).get(
            "source_sha256", "MISSING"
        ),
        "manuscript_sha256": role_map.get("manuscript_0824", {}).get(
            "source_sha256", "MISSING"
        ),
        "index_pre_board21_sha256": live_index_hash,
    }
    write_checks(checks)
    atomic_write_text(
        SUMMARY_PATH,
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        VALIDATION_ROOT,
    )
    write_artifact_manifest()
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图4-4/图4-5完整复现：最小步骤8A全盘资产检索与身份冻结。

本程序只读取源树和压缩包，不修改任何作者文件。它回答三个问题：

1. 论文出图所需的六个稳定掩膜或连续谱半径网格是否仍在磁盘中；
2. 同名文件、压缩包副本和派生工作区是否真的是另一版数据；
3. 后续六路线重算所依据的论文、矩阵和作者脚本是否已用哈希锁定。

PDF中的彩色曲线只作为后续验收参考，不参与本程序的数值反推。
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import sys
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import h5py
import numpy as np
from scipy.io import loadmat, whosmat


SEARCH_ROOT = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS")
PROJECT_ROOT = Path(__file__).resolve().parents[4]
BOARD_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = BOARD_ROOT / "outputs" / "step8a_全盘源资产检索"

AUTHOR_TREE = SEARCH_ROOT / "liangyustability-master" / "liangyustability-master"
THESIS_PDF = SEARCH_ROOT / "梁禹手稿.pdf"
BOARD17_ROOT = (
    PROJECT_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块17_两类划分与缩聚候选路线"
)

TARGET_BOUNDARIES = (
    {"figure": "图4-4", "method": "原结构", "expected_rightmost_col": 64},
    {"figure": "图4-4", "method": "Craig-Bampton", "expected_rightmost_col": 59},
    {"figure": "图4-4", "method": "Guyan", "expected_rightmost_col": 58},
    {"figure": "图4-5", "method": "原结构", "expected_rightmost_col": 57},
    {"figure": "图4-5", "method": "Craig-Bampton", "expected_rightmost_col": 51},
    {"figure": "图4-5", "method": "Guyan", "expected_rightmost_col": 48},
)

EXPECTED_HISTORICAL = {
    ("图4-4", "原结构"): ("lqr_2.mat", "stab_o"),
    ("图4-4", "Craig-Bampton"): ("lqr_2.mat", "stab_C"),
    ("图4-4", "Guyan"): ("lqr_2.mat", "stab_g"),
    ("图4-5", "原结构"): ("lqr_3.mat", "stab_o"),
    ("图4-5", "Craig-Bampton"): ("lqr_3.mat", "stab_C"),
    ("图4-5", "Guyan"): ("lqr_3.mat", "stab_g"),
}

KEY_INPUTS = (
    ("硕士论文", THESIS_PDF),
    ("作者最终绘图脚本", AUTHOR_TREE / "新结构稳定" / "绘图" / "huitu_2.m"),
    ("第一类历史最终MAT", AUTHOR_TREE / "新结构稳定" / "绘图" / "lqr_2.mat"),
    ("第二类历史最终MAT", AUTHOR_TREE / "新结构稳定" / "绘图" / "lqr_3.mat"),
    ("第一类原结构Live Script", AUTHOR_TREE / "新结构稳定" / "稳定域" / "luxvjie_ori_LQR2.mlx"),
    ("第二类原结构Live Script", AUTHOR_TREE / "新结构稳定" / "稳定域" / "luxvjie_ori_LQR3.mlx"),
    ("第一类Guyan Live Script", AUTHOR_TREE / "新结构稳定" / "稳定域" / "luxvjie_guyan_LQR2.mlx"),
    ("第二类Guyan Live Script", AUTHOR_TREE / "新结构稳定" / "稳定域" / "luxvjie_guyan_LQR3.mlx"),
    ("第一类Craig-Bampton Live Script", AUTHOR_TREE / "新结构稳定" / "稳定域" / "luxvjie_cb_LQR2.mlx"),
    ("第二类Craig-Bampton Live Script", AUTHOR_TREE / "新结构稳定" / "稳定域" / "luxvjie_cb_LQR3.mlx"),
    ("板块17六路线全局矩阵", BOARD17_ROOT / "outputs" / "global_routes_matlab.mat"),
    ("板块17局部物理子结构矩阵", BOARD17_ROOT / "outputs" / "local_pd_reductions.mat"),
)


@dataclass(frozen=True)
class NumericVariable:
    container: str
    location: str
    variable: str
    array: np.ndarray


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_array(array: np.ndarray) -> str:
    """对解释后的数值数组建立与MAT容器无关的身份。"""
    contiguous = np.ascontiguousarray(array)
    header = (
        f"dtype={contiguous.dtype.str};shape="
        + "x".join(str(value) for value in contiguous.shape)
        + ";order=C;"
    ).encode("ascii")
    return sha256_bytes(header + contiguous.tobytes(order="C"))


def write_csv(path: Path, rows: list[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def source_category(path_text: str) -> str:
    normalized = path_text.replace("/", "\\").lower()
    author_prefix = str(AUTHOR_TREE).lower() + "\\"
    if normalized.startswith(author_prefix):
        return "作者源树"
    if "\\test\\" in normalized:
        return "本项目派生测试资产"
    if "\\figure\\" in normalized:
        return "本项目整理图片资产"
    if "::" in normalized:
        return "压缩包内部资产"
    return "其他RHTS资产"


def iter_files_and_directories(root: Path) -> tuple[list[Path], int, int]:
    files: list[Path] = []
    directory_count = 0
    total_size = 0
    for current, directories, filenames in os.walk(root):
        directory_count += len(directories)
        current_path = Path(current)
        for name in filenames:
            path = current_path / name
            files.append(path)
            try:
                total_size += path.stat().st_size
            except OSError:
                pass
    files.sort(key=lambda value: str(value).casefold())
    return files, directory_count, total_size


def is_hdf5_header(data: bytes) -> bool:
    signature = b"\x89HDF\r\n\x1a\n"
    # MATLAB v7.3 MAT通常使用512字节HDF5 user block；普通HDF5从0开始。
    return any(
        len(data) >= offset + len(signature)
        and data[offset : offset + len(signature)] == signature
        for offset in (0, 512, 1024, 2048, 4096)
    )


def numeric_2d_arrays_from_hdf5(handle: h5py.File) -> Iterable[tuple[str, np.ndarray]]:
    datasets: list[tuple[str, h5py.Dataset]] = []

    def append_dataset(name: str, obj: Any) -> None:
        if isinstance(obj, h5py.Dataset):
            datasets.append((name, obj))

    # MATLAB v7.3的`#refs#`可能含数十万对象引用；用户变量仍在根层命名。
    # 逐根变量遍历可以完整覆盖目标变量，同时避免遍历引用池。
    for root_name in sorted(handle.keys()):
        if root_name == "#refs#":
            continue
        root_object = handle[root_name]
        if isinstance(root_object, h5py.Dataset):
            datasets.append((root_name, root_object))
        elif isinstance(root_object, h5py.Group):
            root_object.visititems(
                lambda child_name, child_object, prefix=root_name: append_dataset(
                    f"{prefix}/{child_name}", child_object
                )
            )
    for name, dataset in datasets:
        if dataset.ndim != 2 or dataset.size == 0 or dataset.size > 5_000_000:
            continue
        if dataset.dtype.kind not in "biufc":
            continue
        lowered = name.lower()
        name_relevant = any(token in lowered for token in ("stab", "lqr", "rho", "spectral"))
        shape_relevant = all(20 <= int(value) <= 200 for value in dataset.shape)
        # v7.3工作区常含大型响应时程。目标稳定域为约31x67的二维网格；
        # 这里只跳过名称和形状都无关的数据集，文件本身仍逐个计数并哈希。
        if not (name_relevant or shape_relevant):
            continue
        try:
            value = np.asarray(dataset[()])
        except (OSError, TypeError, ValueError):
            continue
        if value.ndim == 2 and np.issubdtype(value.dtype, np.number):
            # MATLAB v7.3按列主序保存，h5py看到的二维尺寸和索引方向相反。
            yield name, value.T


def numeric_2d_arrays_from_legacy_bytes(data: bytes) -> Iterable[tuple[str, np.ndarray]]:
    buffer = io.BytesIO(data)
    try:
        variables = whosmat(buffer)
    except Exception:
        return
    names = [
        name
        for name, shape, cls in variables
        if len(shape) == 2
        and int(np.prod(shape)) <= 5_000_000
        and cls in {"double", "single", "int8", "uint8", "int16", "uint16", "int32", "uint32", "int64", "uint64", "logical"}
    ]
    if not names:
        return
    buffer.seek(0)
    try:
        loaded = loadmat(buffer, variable_names=names, squeeze_me=False, struct_as_record=False)
    except Exception:
        return
    for name in names:
        value = loaded.get(name)
        if isinstance(value, np.ndarray) and value.ndim == 2 and np.issubdtype(value.dtype, np.number):
            yield name, value


def numeric_2d_arrays_from_path(path: Path) -> Iterable[tuple[str, np.ndarray]]:
    try:
        with path.open("rb") as handle:
            header = handle.read(8192)
    except OSError:
        return
    if is_hdf5_header(header):
        try:
            with h5py.File(path, "r") as handle:
                yield from numeric_2d_arrays_from_hdf5(handle)
        except (OSError, ValueError):
            return
        return
    try:
        data = path.read_bytes()
    except OSError:
        return
    yield from numeric_2d_arrays_from_legacy_bytes(data)


def numeric_2d_arrays_from_zip_bytes(data: bytes) -> Iterable[tuple[str, np.ndarray]]:
    if is_hdf5_header(data[:8]):
        try:
            with h5py.File(io.BytesIO(data), "r") as handle:
                yield from numeric_2d_arrays_from_hdf5(handle)
        except (OSError, ValueError):
            return
    else:
        yield from numeric_2d_arrays_from_legacy_bytes(data)


def summarize_numeric(variable: NumericVariable) -> dict[str, Any] | None:
    array = np.asarray(variable.array)
    if array.ndim != 2 or array.size == 0:
        return None
    real_array = np.real_if_close(array)
    if np.iscomplexobj(real_array):
        return None
    real_array = np.asarray(real_array, dtype=float)
    finite = np.isfinite(real_array)
    if not np.any(finite):
        return None
    stable = finite & (real_array > 0.0) & (real_array < 1.0)
    rows, cols = np.nonzero(stable)
    common = stable[: min(31, stable.shape[0]), : min(67, stable.shape[1])]
    common_rows, common_cols = np.nonzero(common)

    lowered = f"{variable.location}::{variable.variable}".lower()
    name_relevant = any(token in lowered for token in ("stab", "lqr", "rho", "spectral"))
    shape_relevant = array.shape[0] >= 20 and array.shape[1] >= 20
    if not (name_relevant or (shape_relevant and np.count_nonzero(stable) >= 100)):
        return None

    finite_values = real_array[finite]
    unique_preview = ""
    if real_array.size <= 20_000:
        unique = np.unique(finite_values)
        if unique.size <= 35:
            unique_preview = ";".join(f"{value:.12g}" for value in unique)
        else:
            unique_preview = f"{unique.size}个唯一值"

    return {
        "容器": variable.container,
        "文件或压缩包位置": variable.location,
        "来源类别": source_category(variable.location),
        "变量名": variable.variable,
        "形状": f"{array.shape[0]}x{array.shape[1]}",
        "数据类型": str(array.dtype),
        "数组SHA256": sha256_array(array),
        "有限最小值": f"{float(np.min(finite_values)):.17g}",
        "有限最大值": f"{float(np.max(finite_values)):.17g}",
        "唯一值概览": unique_preview,
        "0小于值小于1数量": int(np.count_nonzero(stable)),
        "全数组最右稳定列_1基": int(cols.max() + 1) if cols.size else "",
        "共同31x67最右稳定列_1基": int(common_cols.max() + 1) if common_cols.size else "",
        "共同31x67稳定点数": int(np.count_nonzero(common)),
        "共同31x67最低稳定行_1基": int(common_rows.min() + 1) if common_rows.size else "",
        "共同31x67最高稳定行_1基": int(common_rows.max() + 1) if common_rows.size else "",
    }


def scan_mat_files(mat_files: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidate_rows: list[dict[str, Any]] = []
    file_rows: list[dict[str, Any]] = []
    for index, path in enumerate(mat_files, start=1):
        status = "PASS"
        variables_seen = 0
        error = ""
        try:
            file_hash = sha256_file(path)
            for name, array in numeric_2d_arrays_from_path(path):
                variables_seen += 1
                summary = summarize_numeric(
                    NumericVariable("磁盘MAT", str(path), name, array)
                )
                if summary is not None:
                    candidate_rows.append(summary)
            if path.name.startswith("._"):
                status = "INVALID_MACOS_RESOURCE_FORK"
            elif variables_seen == 0:
                status = "NO_READABLE_NUMERIC_2D_VARIABLE"
        except Exception as exc:  # 保留单文件失败，不中断全树审计。
            file_hash = ""
            status = "FAIL"
            error = f"{type(exc).__name__}: {exc}"
        file_rows.append(
            {
                "序号": index,
                "绝对路径": str(path),
                "来源类别": source_category(str(path)),
                "文件字节数": path.stat().st_size if path.exists() else "",
                "文件SHA256": file_hash,
                "可读二维数值变量数": variables_seen,
                "状态": status,
                "错误": error,
            }
        )
    return candidate_rows, file_rows


def scan_zip_files(zip_files: list[Path]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    archive_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    for path in zip_files:
        mat_count = 0
        relevant_backup_count = 0
        entry_count = 0
        errors: list[str] = []
        try:
            archive_hash = sha256_file(path)
            with zipfile.ZipFile(path, "r") as archive:
                infos = archive.infolist()
                entry_count = len(infos)
                for info in infos:
                    lowered = info.filename.lower()
                    if any(token in lowered for token in ("autosave", "backup", "workspace", ".asv", ".bak")):
                        relevant_backup_count += 1
                    if not lowered.endswith(".mat"):
                        continue
                    mat_count += 1
                    try:
                        data = archive.read(info)
                        for name, array in numeric_2d_arrays_from_zip_bytes(data):
                            summary = summarize_numeric(
                                NumericVariable(
                                    "ZIP内MAT",
                                    f"{path}::{info.filename}",
                                    name,
                                    array,
                                )
                            )
                            if summary is not None:
                                candidate_rows.append(summary)
                    except Exception as exc:
                        errors.append(f"{info.filename}: {type(exc).__name__}: {exc}")
            status = "PASS" if not errors else "PARTIAL"
        except Exception as exc:
            archive_hash = ""
            status = "FAIL"
            errors.append(f"{type(exc).__name__}: {exc}")
        archive_rows.append(
            {
                "绝对路径": str(path),
                "文件SHA256": archive_hash,
                "压缩包条目数": entry_count,
                "MAT条目数": mat_count,
                "自动保存或工作区命名条目数": relevant_backup_count,
                "状态": status,
                "错误数": len(errors),
                "错误摘要": " | ".join(errors[:5]),
            }
        )
    return candidate_rows, archive_rows


def locate_historical_row(
    rows: list[dict[str, Any]], filename: str, variable: str
) -> dict[str, Any] | None:
    expected_suffix = str(AUTHOR_TREE / "新结构稳定" / "绘图" / filename).casefold()
    matches = [
        row
        for row in rows
        if row["文件或压缩包位置"].casefold() == expected_suffix
        and row["变量名"] == variable
    ]
    if len(matches) != 1:
        return None
    return matches[0]


def build_boundary_identity_rows(candidate_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    identity_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    for target in TARGET_BOUNDARIES:
        key = (target["figure"], target["method"])
        filename, variable = EXPECTED_HISTORICAL[key]
        row = locate_historical_row(candidate_rows, filename, variable)
        actual = row["共同31x67最右稳定列_1基"] if row is not None else ""
        exact = actual == target["expected_rightmost_col"]
        identity_rows.append(
            {
                "论文图片": target["figure"],
                "方法": target["method"],
                "论文矢量边界最右列_1基": target["expected_rightmost_col"],
                "现存历史MAT": str(AUTHOR_TREE / "新结构稳定" / "绘图" / filename),
                "变量名": variable,
                "现存形状": row["形状"] if row else "未找到",
                "现存共同31x67最右列_1基": actual,
                "现存共同31x67稳定点数": row["共同31x67稳定点数"] if row else "",
                "数组SHA256": row["数组SHA256"] if row else "",
                "是否与论文最右列一致": "是" if exact else "否",
                "证据标签": "历史值与论文边界一致" if exact else "现存历史值不是论文出图版",
            }
        )

        same_endpoint = [
            candidate
            for candidate in candidate_rows
            if candidate["共同31x67最右稳定列_1基"] == target["expected_rightmost_col"]
            and candidate["来源类别"] in {"作者源树", "压缩包内部资产", "其他RHTS资产"}
        ]
        exact_identity = [
            candidate
            for candidate in same_endpoint
            if Path(candidate["文件或压缩包位置"].split("::", 1)[0]).name.casefold()
            == filename.casefold()
            and candidate["变量名"] == variable
        ]
        target_rows.append(
            {
                "论文图片": target["figure"],
                "方法": target["method"],
                "目标最右列_1基": target["expected_rightmost_col"],
                "同终点候选变量数_不代表方法身份": len(same_endpoint),
                "方法身份完全匹配变量数": len(exact_identity),
                "检索裁决": "FOUND" if exact_identity else "MISSING",
                "说明": (
                    "现存方法身份数组与论文最右列一致"
                    if exact_identity
                    else "未找到同一图片、同一方法身份且边界一致的原始掩膜或连续谱半径网格"
                ),
            }
        )
    return identity_rows, target_rows


def build_key_input_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, path in KEY_INPUTS:
        exists = path.is_file()
        rows.append(
            {
                "角色": role,
                "绝对路径": str(path),
                "是否存在": "是" if exists else "否",
                "文件字节数": path.stat().st_size if exists else "",
                "SHA256": sha256_file(path) if exists else "",
                "后续用途": (
                    "仅作论文边界验收，不作计算输入"
                    if path == THESIS_PDF
                    else "计算合同或来源身份"
                ),
            }
        )
    return rows


def main() -> int:
    if not SEARCH_ROOT.is_dir():
        raise FileNotFoundError(f"搜索根目录不存在：{SEARCH_ROOT}")
    if PROJECT_ROOT != Path.cwd().resolve():
        print(f"提示：当前目录为 {Path.cwd().resolve()}，项目根目录识别为 {PROJECT_ROOT}")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files, directory_count, total_size = iter_files_and_directories(SEARCH_ROOT)
    extension_counts = Counter(path.suffix.lower() or "<无扩展名>" for path in files)
    mat_files = [path for path in files if path.suffix.lower() == ".mat"]
    hdf5_mat_count = 0
    for path in mat_files:
        try:
            with path.open("rb") as handle:
                if is_hdf5_header(handle.read(8192)):
                    hdf5_mat_count += 1
        except OSError:
            pass
    zip_files = [path for path in files if path.suffix.lower() == ".zip"]
    rar_or_7z = [path for path in files if path.suffix.lower() in {".rar", ".7z"}]

    disk_candidates, mat_file_rows = scan_mat_files(mat_files)
    zip_candidates, archive_rows = scan_zip_files(zip_files)
    all_candidates = disk_candidates + zip_candidates
    all_candidates.sort(
        key=lambda row: (
            row["文件或压缩包位置"].casefold(),
            row["变量名"].casefold(),
        )
    )

    identity_rows, target_rows = build_boundary_identity_rows(all_candidates)
    key_input_rows = build_key_input_rows()

    named_backup = [
        path
        for path in files
        if any(
            token in str(path).lower()
            for token in ("workspace", "autosave", "backup", ".asv", ".bak")
        )
    ]
    source_named_backup = [
        path
        for path in named_backup
        if source_category(str(path)) not in {"本项目派生测试资产", "本项目整理图片资产"}
    ]

    fields_candidates = [
        "容器",
        "文件或压缩包位置",
        "来源类别",
        "变量名",
        "形状",
        "数据类型",
        "数组SHA256",
        "有限最小值",
        "有限最大值",
        "唯一值概览",
        "0小于值小于1数量",
        "全数组最右稳定列_1基",
        "共同31x67最右稳定列_1基",
        "共同31x67稳定点数",
        "共同31x67最低稳定行_1基",
        "共同31x67最高稳定行_1基",
    ]
    write_csv(OUTPUT_DIR / "全部MAT候选变量审计.csv", all_candidates, fields_candidates)
    write_csv(
        OUTPUT_DIR / "全部MAT文件哈希与读取状态.csv",
        mat_file_rows,
        [
            "序号",
            "绝对路径",
            "来源类别",
            "文件字节数",
            "文件SHA256",
            "可读二维数值变量数",
            "状态",
            "错误",
        ],
    )
    write_csv(
        OUTPUT_DIR / "压缩包审计.csv",
        archive_rows,
        [
            "绝对路径",
            "文件SHA256",
            "压缩包条目数",
            "MAT条目数",
            "自动保存或工作区命名条目数",
            "状态",
            "错误数",
            "错误摘要",
        ],
    )
    write_csv(
        OUTPUT_DIR / "论文六条边界与现存MAT身份对照.csv",
        identity_rows,
        list(identity_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "论文目标边界缺失检索.csv",
        target_rows,
        list(target_rows[0].keys()),
    )
    write_csv(
        OUTPUT_DIR / "步骤8后续关键输入哈希清单.csv",
        key_input_rows,
        list(key_input_rows[0].keys()),
    )

    missing = [row for row in target_rows if row["检索裁决"] == "MISSING"]
    invalid_resource_forks = [
        row for row in mat_file_rows if row["状态"] == "INVALID_MACOS_RESOURCE_FORK"
    ]
    readable_mat = [
        row
        for row in mat_file_rows
        if row["状态"] not in {"FAIL", "INVALID_MACOS_RESOURCE_FORK"}
    ]
    summary = {
        "schema": "board20.step8a.asset-search.v1",
        "generated_at": now_iso(),
        "search_root": str(SEARCH_ROOT),
        "file_count": len(files),
        "directory_count_below_root": directory_count,
        "total_bytes": total_size,
        "extension_counts": dict(sorted(extension_counts.items())),
        "mat_file_count": len(mat_files),
        "hdf5_v73_mat_count": hdf5_mat_count,
        "readable_or_non_numeric_mat_count": len(readable_mat),
        "invalid_macos_resource_fork_count": len(invalid_resource_forks),
        "zip_file_count": len(zip_files),
        "rar_or_7z_count": len(rar_or_7z),
        "candidate_numeric_variable_count": len(all_candidates),
        "named_workspace_autosave_backup_file_count": len(named_backup),
        "source_tree_named_workspace_autosave_backup_file_count": len(source_named_backup),
        "target_boundary_count": len(target_rows),
        "missing_identity_correct_target_count": len(missing),
        "all_six_original_workspaces_recovered": len(missing) == 0,
        "gate_status": "PASS_SEARCH_COMPLETE_INPUTS_MISSING" if missing else "PASS_ALL_INPUTS_FOUND",
        "scientific_conclusion": (
            "未找到原作者论文出图版完整输入或工作区；排除从隐藏MAT、ZIP、自动保存或备份直接恢复六条曲线的路线。"
            if missing
            else "六条论文边界均找到方法身份一致的源数组。"
        ),
        "next_action": (
            "只能依照硕士论文公式、冻结15自由度模型和可审计缩聚矩阵重建六条计算链；PDF曲线仅用于点对点验收。"
            if missing
            else "从已找到源数组验证生成链。"
        ),
    }
    write_json(OUTPUT_DIR / "步骤8A全盘检索摘要.json", summary)

    readme = f"""# 图4-4/图4-5完整复现：步骤8A全盘源资产检索

生成时间：`{summary['generated_at']}`

## 结论

{summary['scientific_conclusion']}

本检索覆盖 `{len(files)}` 个文件、`{directory_count}` 个子目录、`{total_size}` 字节；逐个核验 `{len(mat_files)}` 个磁盘MAT及 `{len(zip_files)}` 个ZIP压缩包。发现 `{len(invalid_resource_forks)}` 个 `__MACOSX/._*.mat` 资源叉，它们不是有效MAT数据文件。源树中以 workspace/autosave/backup/.asv/.bak 命名的文件数为 `{len(source_named_backup)}`。

论文PDF矢量边界给出的目标最右列为：图4-4原结构/CB/Guyan = `64/59/58`，图4-5 = `57/51/48`。现存作者最终MAT为 `64/55/52` 与 `57/54/51`；只有两条原结构路线的边界终点一致，其余四条方法身份不一致或数据缺失。

## 使用边界

- PDF矢量曲线只用于最终逐点验收，不能作为重算输入或调参目标。
- 同一最右列但方法名不同的数组不能冒充目标方法。
- `test/` 和 `figure/` 中的2026年派生副本不会被提升为作者原始工作区。
- 下一步依据硕士论文公式、板块17冻结矩阵和作者脚本中可追溯部分重建六条计算链。

## 主要文件

- `步骤8A全盘检索摘要.json`：机器可读总门槛。
- `论文六条边界与现存MAT身份对照.csv`：六条曲线逐项身份裁决。
- `论文目标边界缺失检索.csv`：是否找到同图、同方法、同边界源数组。
- `全部MAT候选变量审计.csv`：磁盘和ZIP内相关二维数值变量。
- `全部MAT文件哈希与读取状态.csv`：每个磁盘MAT的读取状态与SHA-256。
- `压缩包审计.csv`：压缩包身份和内部MAT数量。
- `步骤8后续关键输入哈希清单.csv`：论文、作者脚本、历史MAT和板块17矩阵的冻结身份。
"""
    (OUTPUT_DIR / "README_步骤8A检索说明.md").write_text(readme, encoding="utf-8")

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["gate_status"].startswith("PASS") else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"步骤8A审计失败：{type(exc).__name__}: {exc}", file=sys.stderr)
        raise

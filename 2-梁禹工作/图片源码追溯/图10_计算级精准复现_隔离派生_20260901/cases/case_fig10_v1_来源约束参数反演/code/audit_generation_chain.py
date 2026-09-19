from __future__ import annotations

import argparse
import csv
import gzip
import hashlib
import html
import json
import os
import re
import sys
import time
import zipfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

import h5py
import numpy as np
from scipy.io import loadmat, whosmat


DEFAULT_ROOTS = [
    Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS"),
]

RELEVANT_EXTENSIONS = {
    ".m", ".mlx", ".slx", ".mdl", ".sldd", ".mat", ".fig", ".asv", ".p",
    ".log", ".txt", ".xml", ".json", ".csv", ".md", ".bak", ".old", ".zip",
    ".original", ".r2023a", ".r2023b", ".slxc", ".orig", ".gz", ".rar", ".7z", ".tar",
}
TEXT_EXTENSIONS = {".m", ".mdl", ".asv", ".log", ".txt", ".xml", ".json", ".csv", ".md", ".bak", ".old"}
ARCHIVE_EXTENSIONS = {".mlx", ".slx", ".zip", ".original", ".r2023a", ".r2023b", ".slxc"}
GZIP_EXTENSIONS = {".gz"}
MAT_LIKE_EXTENSIONS = {".mat", ".fig"}
BINARY_LIMIT_EXTENSIONS = {".p", ".sldd", ".rar", ".7z", ".tar", ".orig"}
TARGET_SHAPES = {(31, 67), (45, 95), (41, 95), (67, 31), (95, 45), (95, 41)}
TARGET_VARIABLES = {"stab_o", "stab_c", "stab_g", "stab", "plotteddata", "metadata"}
KEYWORDS = [
    "stab_o",
    "stab_c",
    "stab_g",
    "lqr_2.mat",
    "lqr_3.mat",
    "plotted_data.mat",
    "plotteddata",
    "bwboundaries",
    "spectral radius",
    "spectral_radius",
    "max(abs",
    "rho=max",
    "rho = max",
    "eig(",
    "roots(",
    "polyeig",
    "dlqr",
    "lqr(",
    "care(",
    "dare(",
    "0:30",
    "0:66",
    "31x67",
    "45x95",
    "41x95",
    "0.999",
    ".999",
    "1/1024",
    "1024 hz",
    "1024hz",
    "writematrix",
    "writetable",
    "preloadfcn",
    "initfcn",
    "startfcn",
    "stopfcn",
    "closefcn",
    "modelworkspace",
    "datadictionary",
]
IO_PATTERN = re.compile(
    r"(?i)\b(load|save|run|sim|open_system|evalin|assignin|set_param|get_param|matfile|writematrix|writetable|save_system)\b"
)
CALLBACK_PATTERN = re.compile(
    r"(?i)(PreLoadFcn|PostLoadFcn|InitFcn|StartFcn|PauseFcn|ContinueFcn|StopFcn|CloseFcn|LoadFcn|ModelWorkspace|DataDictionary|ExternalSource)"
)
TAG_PATTERN = re.compile(r"<[^>]+>")
SPACE_PATTERN = re.compile(r"\s+")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="只读审计图10 MATLAB/Simulink/MAT 生成链")
    parser.add_argument("--root", action="append", dest="roots", help="可重复指定扫描根")
    parser.add_argument("--out", help="证据输出目录")
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def decode_bytes(data: bytes) -> tuple[str, str]:
    for encoding in ("utf-8", "utf-8-sig", "utf-16", "gb18030", "latin-1"):
        try:
            return data.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace"), "latin-1-replace"


def normalized_text(raw: str) -> str:
    return html.unescape(TAG_PATTERN.sub("\n", raw)).replace("\r\n", "\n").replace("\r", "\n")


def compact_snippet(text: str, start: int, width: int = 220) -> str:
    left = max(0, start - width // 2)
    right = min(len(text), start + width)
    return SPACE_PATTERN.sub(" ", text[left:right]).strip()


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def list_files(roots: list[Path], excluded_root: Path) -> list[tuple[int, Path]]:
    files: list[tuple[int, Path]] = []
    excluded_resolved = excluded_root.resolve()
    for root_index, root in enumerate(roots, start=1):
        root = root.resolve()
        for dirpath, dirnames, filenames in os.walk(root):
            current = Path(dirpath).resolve()
            dirnames[:] = [
                name
                for name in dirnames
                if not (current / name).resolve().is_relative_to(excluded_resolved)
            ]
            for name in filenames:
                path = current / name
                if path.suffix.lower() in RELEVANT_EXTENSIONS:
                    files.append((root_index, path))
    files.sort(key=lambda item: str(item[1]).lower())
    return files


def inspect_mat(path: Path) -> tuple[list[dict], str]:
    rows: list[dict] = []
    try:
        for name, shape, class_name in whosmat(path):
            rows.append(
                {
                    "variable": name,
                    "shape": "x".join(str(value) for value in shape),
                    "class": class_name,
                    "reader": "scipy.whosmat",
                }
            )
        return rows, ""
    except Exception as scipy_error:
        try:
            with h5py.File(path, "r") as handle:
                def visitor(name: str, obj) -> None:
                    if isinstance(obj, h5py.Dataset) and not name.startswith("#refs#"):
                        rows.append(
                            {
                                "variable": name,
                                "shape": "x".join(str(value) for value in obj.shape),
                                "class": str(obj.dtype),
                                "reader": "h5py",
                            }
                        )
                handle.visititems(visitor)
            return rows, ""
        except Exception as h5_error:
            return [], f"scipy={type(scipy_error).__name__}:{scipy_error}; h5py={type(h5_error).__name__}:{h5_error}"


def inspect_numeric_features(path: Path, field_rows: list[dict]) -> tuple[list[dict], str]:
    selected = [
        row
        for row in field_rows
        if row["variable"].lower() in TARGET_VARIABLES
        or tuple(int(value) for value in row["shape"].split("x") if value) in TARGET_SHAPES
    ]
    if not selected:
        return [], ""
    rows: list[dict] = []
    try:
        scipy_names = [row["variable"] for row in selected if row["reader"] == "scipy.whosmat"]
        if scipy_names:
            loaded = loadmat(path, variable_names=scipy_names, squeeze_me=False, struct_as_record=False)
            for name in scipy_names:
                value = loaded.get(name)
                if value is None or not np.issubdtype(value.dtype, np.number):
                    continue
                flat = np.asarray(value).reshape(-1)
                finite = flat[np.isfinite(flat)]
                unique = np.unique(finite) if finite.size <= 200_000 else np.array([])
                rows.append(
                    {
                        "path": str(path),
                        "variable": name,
                        "shape": "x".join(str(v) for v in value.shape),
                        "count": int(flat.size),
                        "finite_count": int(finite.size),
                        "min": float(np.min(finite)) if finite.size else "",
                        "max": float(np.max(finite)) if finite.size else "",
                        "stable_0_lt_x_lt_1_count": int(np.count_nonzero((finite > 0) & (finite < 1))),
                        "zero_count": int(np.count_nonzero(finite == 0)),
                        "value_0_999_count": int(np.count_nonzero(np.isclose(finite, 0.999, rtol=0, atol=1e-12))),
                        "unique_count": int(unique.size) if unique.size else "",
                        "unique_values_if_le_40": json.dumps(unique.tolist()) if 0 < unique.size <= 40 else "",
                        "reader": "scipy.loadmat",
                    }
                )
        h5_names = [row["variable"] for row in selected if row["reader"] == "h5py"]
        if h5_names:
            with h5py.File(path, "r") as handle:
                for name in h5_names:
                    value = np.asarray(handle[name])
                    if not np.issubdtype(value.dtype, np.number):
                        continue
                    flat = value.reshape(-1)
                    finite = flat[np.isfinite(flat)]
                    unique = np.unique(finite) if finite.size <= 200_000 else np.array([])
                    rows.append(
                        {
                            "path": str(path),
                            "variable": name,
                            "shape": "x".join(str(v) for v in value.shape),
                            "count": int(flat.size),
                            "finite_count": int(finite.size),
                            "min": float(np.min(finite)) if finite.size else "",
                            "max": float(np.max(finite)) if finite.size else "",
                            "stable_0_lt_x_lt_1_count": int(np.count_nonzero((finite > 0) & (finite < 1))),
                            "zero_count": int(np.count_nonzero(finite == 0)),
                            "value_0_999_count": int(np.count_nonzero(np.isclose(finite, 0.999, rtol=0, atol=1e-12))),
                            "unique_count": int(unique.size) if unique.size else "",
                            "unique_values_if_le_40": json.dumps(unique.tolist()) if 0 < unique.size <= 40 else "",
                            "reader": "h5py",
                        }
                    )
        return rows, ""
    except Exception as error:
        return rows, f"{type(error).__name__}:{error}"


def scan_text(
    path: Path,
    container: str,
    text: str,
    keyword_rows: list[dict],
    io_rows: list[dict],
    callback_rows: list[dict],
) -> None:
    lower = text.lower()
    for keyword in KEYWORDS:
        needle = keyword.lower()
        index = lower.find(needle)
        if index >= 0:
            occurrence_count = lower.count(needle)
            line_number = text.count("\n", 0, index) + 1
            keyword_rows.append(
                {
                    "path": str(path),
                    "container": container,
                    "line": line_number,
                    "keyword": keyword,
                    "occurrence_count": occurrence_count,
                    "snippet": compact_snippet(text, index),
                }
            )

    # Large numerical CSV files can contain millions of rows but no MATLAB I/O
    # statements or Simulink callbacks. Avoid splitting them unless a whole-file
    # precheck proves that at least one relevant pattern exists.
    has_io = IO_PATTERN.search(text) is not None
    has_callback = CALLBACK_PATTERN.search(text) is not None
    if has_io or has_callback:
        for line_number, line in enumerate(text.splitlines(), start=1):
            if has_io and IO_PATTERN.search(line):
                io_rows.append(
                    {
                        "path": str(path),
                        "container": container,
                        "line": line_number,
                        "statement": SPACE_PATTERN.sub(" ", line).strip()[:1000],
                    }
                )
            callback_match = CALLBACK_PATTERN.search(line) if has_callback else None
            if callback_match:
                callback_rows.append(
                    {
                        "path": str(path),
                        "container": container,
                        "line": line_number,
                        "callback_or_workspace": callback_match.group(1),
                        "snippet": SPACE_PATTERN.sub(" ", line).strip()[:1200],
                    }
                )


def main() -> int:
    args = parse_args()
    roots = [Path(value) for value in args.roots] if args.roots else DEFAULT_ROOTS
    delivery_root = Path(__file__).resolve().parents[3]
    out_dir = Path(args.out).resolve() if args.out else delivery_root / "00_证据记录" / "01_全材料生成链扫描"
    out_dir.mkdir(parents=True, exist_ok=True)

    started = time.time()
    files = list_files(roots, delivery_root)
    inventory_rows: list[dict] = []
    mat_rows: list[dict] = []
    keyword_rows: list[dict] = []
    io_rows: list[dict] = []
    callback_rows: list[dict] = []
    archive_rows: list[dict] = []
    numeric_feature_rows: list[dict] = []
    binary_limit_rows: list[dict] = []
    duplicate_index: dict[str, list[str]] = defaultdict(list)
    errors: list[dict] = []

    for ordinal, (root_index, path) in enumerate(files, start=1):
        try:
            stat = path.stat()
            digest = sha256_file(path)
            duplicate_index[digest].append(str(path))
            inventory_rows.append(
                {
                    "ordinal": ordinal,
                    "root_index": root_index,
                    "path": str(path),
                    "extension": path.suffix.lower(),
                    "size_bytes": stat.st_size,
                    "mtime_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(stat.st_mtime)),
                    "sha256": digest,
                }
            )

            suffix = path.suffix.lower()
            if suffix in MAT_LIKE_EXTENSIONS:
                fields, error = inspect_mat(path)
                if error:
                    errors.append({"path": str(path), "stage": "mat_like", "error": error})
                for field in fields:
                    mat_rows.append({"path": str(path), **field})
                features, feature_error = inspect_numeric_features(path, fields)
                numeric_feature_rows.extend(features)
                if feature_error:
                    errors.append({"path": str(path), "stage": "numeric_features", "error": feature_error})
            elif suffix in TEXT_EXTENSIONS:
                data = path.read_bytes()
                text, encoding = decode_bytes(data)
                scan_text(path, f"file[{encoding}]", text, keyword_rows, io_rows, callback_rows)
            elif suffix in ARCHIVE_EXTENSIONS:
                try:
                    with zipfile.ZipFile(path, "r") as archive:
                        for member in archive.infolist():
                            if member.is_dir() or member.file_size > 8 * 1024 * 1024:
                                continue
                            lowered = member.filename.lower()
                            if not lowered.endswith((".xml", ".rels", ".txt", ".m", ".json")):
                                continue
                            data = archive.read(member)
                            raw, encoding = decode_bytes(data)
                            text = normalized_text(raw)
                            archive_rows.append(
                                {
                                    "path": str(path),
                                    "member": member.filename,
                                    "size_bytes": member.file_size,
                                    "encoding": encoding,
                                }
                            )
                            scan_text(path, member.filename, text, keyword_rows, io_rows, callback_rows)
                except Exception as archive_error:
                    errors.append(
                        {"path": str(path), "stage": "archive", "error": f"{type(archive_error).__name__}:{archive_error}"}
                    )
            elif suffix in GZIP_EXTENSIONS:
                try:
                    with gzip.open(path, "rb") as archive:
                        data = archive.read(32 * 1024 * 1024 + 1)
                    if len(data) > 32 * 1024 * 1024:
                        binary_limit_rows.append(
                            {
                                "path": str(path),
                                "extension": suffix,
                                "size_bytes": stat.st_size,
                                "inspection": "decompressed prefix search only",
                                "limitation": "decompressed content exceeds 32 MiB audit cap",
                            }
                        )
                        data = data[: 32 * 1024 * 1024]
                    raw, encoding = decode_bytes(data)
                    scan_text(path, f"gzip[{encoding}]", raw, keyword_rows, io_rows, callback_rows)
                except Exception as archive_error:
                    errors.append(
                        {"path": str(path), "stage": "gzip", "error": f"{type(archive_error).__name__}:{archive_error}"}
                    )
            elif suffix in BINARY_LIMIT_EXTENSIONS:
                data = path.read_bytes()
                raw, encoding = decode_bytes(data[: min(len(data), 32 * 1024 * 1024)])
                scan_text(path, f"binary-prefix[{encoding}]", raw, keyword_rows, io_rows, callback_rows)
                binary_limit_rows.append(
                    {
                        "path": str(path),
                        "extension": suffix,
                        "size_bytes": stat.st_size,
                        "inspection": "ASCII/Unicode prefix search only",
                        "limitation": "compiled or proprietary binary content cannot be semantically decompiled by this audit",
                    }
                )
        except Exception as error:
            errors.append({"path": str(path), "stage": "file", "error": f"{type(error).__name__}:{error}"})

        if ordinal % 100 == 0:
            print(f"processed {ordinal}/{len(files)}", flush=True)

    duplicate_rows: list[dict] = []
    for digest, paths in sorted(duplicate_index.items()):
        if len(paths) < 2:
            continue
        for path in paths:
            duplicate_rows.append({"sha256": digest, "copy_count": len(paths), "path": path})

    write_csv(
        out_dir / "相关文件清单.csv",
        ["ordinal", "root_index", "path", "extension", "size_bytes", "mtime_iso", "sha256"],
        inventory_rows,
    )
    write_csv(out_dir / "MAT字段清单.csv", ["path", "variable", "shape", "class", "reader"], mat_rows)
    write_csv(
        out_dir / "MAT数值特征.csv",
        ["path", "variable", "shape", "count", "finite_count", "min", "max", "stable_0_lt_x_lt_1_count", "zero_count", "value_0_999_count", "unique_count", "unique_values_if_le_40", "reader"],
        numeric_feature_rows,
    )
    write_csv(
        out_dir / "关键字命中.csv",
        ["path", "container", "line", "keyword", "occurrence_count", "snippet"],
        keyword_rows,
    )
    write_csv(out_dir / "调用与读写语句.csv", ["path", "container", "line", "statement"], io_rows)
    write_csv(
        out_dir / "Simulink回调与工作区命中.csv",
        ["path", "container", "line", "callback_or_workspace", "snippet"],
        callback_rows,
    )
    write_csv(out_dir / "MLX_SLX解包成员.csv", ["path", "member", "size_bytes", "encoding"], archive_rows)
    write_csv(out_dir / "同哈希副本.csv", ["sha256", "copy_count", "path"], duplicate_rows)
    write_csv(out_dir / "扫描错误.csv", ["path", "stage", "error"], errors)
    write_csv(
        out_dir / "二进制入口限制.csv",
        ["path", "extension", "size_bytes", "inspection", "limitation"],
        binary_limit_rows,
    )

    protection_rows: list[dict] = []
    for ordinal, row in enumerate(inventory_rows, start=1):
        path = Path(row["path"])
        try:
            after_hash = sha256_file(path)
            status = "MATCH" if after_hash == row["sha256"] else "CHANGED"
            error = ""
        except Exception as protection_error:
            after_hash = ""
            status = "READ_FAILED"
            error = f"{type(protection_error).__name__}:{protection_error}"
        protection_rows.append(
            {
                "path": str(path),
                "before_sha256": row["sha256"],
                "after_sha256": after_hash,
                "status": status,
                "error": error,
            }
        )
        if ordinal % 250 == 0:
            print(f"protection rehash {ordinal}/{len(inventory_rows)}", flush=True)
    write_csv(out_dir / "源文件前后哈希.csv", ["path", "before_sha256", "after_sha256", "status", "error"], protection_rows)

    extension_counts = Counter(row["extension"] for row in inventory_rows)
    target_names = {"lqr_2.mat", "lqr_3.mat", "plotted_data.mat"}
    target_files = [row for row in inventory_rows if Path(row["path"]).name.lower() in target_names]
    target_fields = [
        row
        for row in mat_rows
        if Path(row["path"]).name.lower() in target_names
        or row["variable"].lower() in TARGET_VARIABLES
    ]
    writer_like_hits = [
        row
        for row in io_rows
        if re.search(r"(?i)\bsave\b", row["statement"])
        and re.search(r"(?i)(stab_o|stab_c|stab_g|lqr_2|lqr_3|plotted_data)", row["statement"])
    ]

    summary = {
        "status": "SCAN_COMPLETE" if not errors else "SCAN_COMPLETE_WITH_READ_LIMITATIONS",
        "started_epoch": started,
        "finished_epoch": time.time(),
        "elapsed_seconds": time.time() - started,
        "roots": [str(root.resolve()) for root in roots],
        "excluded_delivery_root": str(delivery_root),
        "relevant_extensions": sorted(RELEVANT_EXTENSIONS),
        "file_count": len(inventory_rows),
        "extension_counts": dict(sorted(extension_counts.items())),
        "mat_field_count": len(mat_rows),
        "mat_numeric_feature_count": len(numeric_feature_rows),
        "keyword_hit_count": len(keyword_rows),
        "io_statement_count": len(io_rows),
        "callback_workspace_hit_count": len(callback_rows),
        "archive_member_count": len(archive_rows),
        "duplicate_file_row_count": len(duplicate_rows),
        "error_count": len(errors),
        "binary_limit_count": len(binary_limit_rows),
        "source_protection_match_count": sum(row["status"] == "MATCH" for row in protection_rows),
        "source_protection_changed_count": sum(row["status"] == "CHANGED" for row in protection_rows),
        "source_protection_read_failed_count": sum(row["status"] == "READ_FAILED" for row in protection_rows),
        "target_files": target_files,
        "target_fields": target_fields,
        "writer_like_hits": writer_like_hits,
    }
    (out_dir / "扫描摘要.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

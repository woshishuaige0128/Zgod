#!/usr/bin/env python
"""板块18候选图的独立、可机读验收。

本脚本只读取 ``outputs/figure_candidates`` 和 ``outputs/adapted_run1``，
并把验收结果写入 ``outputs/figure_validation``。它不会创建成功目录，
不会修改原始论文、MAT/CSV/SLX，也不会把主观视觉判断标成 PASS。

硬门禁包括：

* 11 个对象目录、12 对 PDF/PNG（图3-15有两个版本）；
* 图对象合同、逐点绘图长表、指标表和 SHA-256 清单；
* PDF 单页、正 MediaBox、无 Type 3 字体、无覆盖整页的大栅格图；
* PNG 实际 DPI 不低于 590、白底合理且内容非空；
* 每个绘图点独立回查 adapted_run1 的原始响应 CSV；
* 图3-15历史版两个局部窗与图3-10逐点完全相等；
* 图3-15修正版三个面板全部来自第二类 Chirp 三层响应。

返回码：全部门禁通过为 0；任一失败或依赖缺失为 1。
"""

from __future__ import annotations

import csv
import hashlib
import json
import locale
import math
import re
import shutil
import subprocess
import sys
import traceback
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


IMPORT_ERRORS: dict[str, str] = {}

try:
    import numpy as np
except Exception as exc:  # pragma: no cover - exercised only when dependency is absent
    np = None  # type: ignore[assignment]
    IMPORT_ERRORS["numpy"] = f"{type(exc).__name__}: {exc}"

try:
    from PIL import Image
except Exception as exc:  # pragma: no cover - exercised only when dependency is absent
    Image = None  # type: ignore[assignment]
    IMPORT_ERRORS["Pillow"] = f"{type(exc).__name__}: {exc}"

SCRIPT_PATH = Path(__file__).resolve()
BOARD_ROOT = SCRIPT_PATH.parent.parent
OUTPUTS_ROOT = BOARD_ROOT / "outputs"
CANDIDATE_ROOT = OUTPUTS_ROOT / "figure_candidates"
VALIDATION_ROOT = OUTPUTS_ROOT / "figure_validation"
DETAIL_PATH = VALIDATION_ROOT / "validation_detail.csv"
SUMMARY_PATH = VALIDATION_ROOT / "validation_summary.json"
FIGURE_CONTRACT_PATH = OUTPUTS_ROOT / "figure_contract.csv"
RAW_INPUT_ROOT = OUTPUTS_ROOT / "adapted_run1" / "输入数据"

EXPECTED_OBJECT_IDS = [f"F3-{number}" for number in range(5, 16)]
EXPECTED_OBJECT_SET = set(EXPECTED_OBJECT_IDS)

FIGURE_CONTRACT_COLUMNS = [
    "对象ID",
    "原稿图号",
    "唯一图号",
    "图名",
    "PDF页",
    "印刷页",
    "划分",
    "激励",
    "楼层",
    "源数据",
    "输出变量",
    "方法列",
    "全时窗",
    "局部窗",
    "单位",
    "原稿异常",
    "历史值状态",
]

PLOT_DATA_COLUMNS = [
    "object_id",
    "object_name",
    "version",
    "panel",
    "source_dataset",
    "source_mat_filename",
    "source_column",
    "time_s",
    "floor",
    "method",
    "response_mm",
    "value_mm",
    "window_start_s",
    "window_end_s",
]

METRICS_COLUMNS = [
    "object_id",
    "object_name",
    "version",
    "panel",
    "source_dataset",
    "source_mat_filename",
    "source_column",
    "floor",
    "method",
    "sample_count",
    "window_start_s",
    "window_end_s",
    "peak_abs_mm",
    "rms_mm",
    "final_mm",
    "min_mm",
    "max_mm",
    "status",
]

MANIFEST_COLUMNS = [
    "figure_pair_id",
    "object_id",
    "object_name",
    "version",
    "figure_basename",
    "artifact_type",
    "relative_path",
    "sha256",
    "size_bytes",
    "expected_pdf_pages",
    "expected_png_dpi",
    "source_data_csv_relative_path",
    "metrics_csv_relative_path",
    "contract_json_relative_path",
]

CONTRACT_TOP_LEVEL_KEYS = {
    "schema_version",
    "object_id",
    "figure_number",
    "object_name",
    "object_directory",
    "versions",
    "source_files",
    "mat_method_order",
    "mat_floor_order",
    "plotting_method_order",
    "sample_count",
    "time_contract",
    "style",
    "output_contract",
    "comparison_evidence",
    "historical_value_status",
}

GENERATION_SUMMARY_REQUIRED_KEYS = {
    "schema_version",
    "status",
    "generated_at_utc",
    "candidate_root",
    "input_root",
    "comparison_csv",
    "object_count",
    "figure_pair_count",
    "pdf_count",
    "png_count",
    "manifest_sha256",
    "f3_15_historical_assertion",
    "source_mat_sha256",
    "output_contract",
}

RAW_DATASETS = {
    "unit": "单位激励_原结构三层响应.csv",
    "division1_elcentro": "第一类划分_ElCentro地震响应.csv",
    "division2_elcentro": "第二类划分_ElCentro地震响应.csv",
    "division1_chirp": "第一类划分_Chirp响应.csv",
    "division2_chirp": "第二类划分_Chirp响应.csv",
}

RAW_MAT_FILENAMES = {
    dataset_id: Path(filename).with_suffix(".mat").name
    for dataset_id, filename in RAW_DATASETS.items()
}

RAW_COLUMNS = [
    "时间_s",
    "原结构_一层_mm",
    "Guyan_一层_mm",
    "CraigBampton_一层_mm",
    "原结构_二层_mm",
    "Guyan_二层_mm",
    "CraigBampton_二层_mm",
    "原结构_三层_mm",
    "Guyan_三层_mm",
    "CraigBampton_三层_mm",
]

MAT_METHOD_ORDER = ["Original", "Guyan", "Craig-Bampton"]
PLOTTING_METHOD_ORDER = ["Original", "Craig-Bampton", "Guyan"]
MAT_FLOOR_ORDER = ["Floor 1", "Floor 2", "Floor 3"]
MAT_METHOD_INDEX = {name: index for index, name in enumerate(MAT_METHOD_ORDER)}
MAT_FLOOR_INDEX = {name: index for index, name in enumerate(MAT_FLOOR_ORDER)}

OBJECT_ROUTE = {
    "F3-5": ("unit", ["Floor 1", "Floor 2", "Floor 3"], "unit"),
    "F3-6": ("division1_elcentro", ["Floor 1"], "earthquake"),
    "F3-7": ("division1_elcentro", ["Floor 2"], "earthquake"),
    "F3-8": ("division1_elcentro", ["Floor 3"], "earthquake"),
    "F3-9": ("division2_elcentro", ["Floor 1"], "earthquake"),
    "F3-10": ("division2_elcentro", ["Floor 3"], "earthquake"),
    "F3-11": ("division1_chirp", ["Floor 1"], "chirp"),
    "F3-12": ("division1_chirp", ["Floor 2"], "chirp"),
    "F3-13": ("division1_chirp", ["Floor 3"], "chirp"),
    "F3-14": ("division2_chirp", ["Floor 1"], "chirp"),
    "F3-15": ("division2_chirp", ["Floor 3"], "chirp"),
}

WINDOWS = {
    "unit": [("full", 0.0, 40.0)],
    "earthquake": [
        ("full", 0.0, 40.0),
        ("zoom_1", 10.0, 11.0),
        ("zoom_2", 21.5, 22.5),
    ],
    "chirp": [
        ("full", 0.0, 40.0),
        ("zoom_1", 13.0, 14.0),
        ("zoom_2", 38.0, 38.3),
    ],
}

DETAIL_COLUMNS = [
    "check_id",
    "category",
    "object_id",
    "version",
    "artifact",
    "path",
    "check",
    "status",
    "expected",
    "actual",
    "detail",
]

DETAILS: list[dict[str, str]] = []
STATS: dict[str, Any] = {
    "object_count_observed": 0,
    "figure_pair_count_observed": 0,
    "pdf_count_observed": 0,
    "png_count_observed": 0,
    "manifest_row_count_observed": 0,
    "f3_15_historical_pointwise_equal": False,
    "f3_15_corrected_from_division2_chirp": False,
}


def _display(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.replace("\r", " ").replace("\n", " | ")
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    except TypeError:
        return str(value)


def record(
    category: str,
    check_name: str,
    passed: bool,
    *,
    expected: Any = "",
    actual: Any = "",
    detail: Any = "",
    object_id: str = "",
    version: str = "",
    artifact: str = "",
    path: Path | str | None = None,
) -> bool:
    DETAILS.append(
        {
            "check_id": f"C{len(DETAILS) + 1:05d}",
            "category": category,
            "object_id": object_id,
            "version": version,
            "artifact": artifact,
            "path": "" if path is None else str(path),
            "check": check_name,
            "status": "PASS" if passed else "FAIL",
            "expected": _display(expected),
            "actual": _display(actual),
            "detail": _display(detail),
        }
    )
    return passed


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = list(reader.fieldnames or [])
        return header, list(reader)


def safe_candidate_path(relative_path: str) -> Path | None:
    parts = [part for part in relative_path.replace("\\", "/").split("/") if part]
    if Path(relative_path).is_absolute() or not parts or any(part == ".." for part in parts):
        return None
    candidate = CANDIDATE_ROOT.joinpath(*parts).resolve()
    root = CANDIDATE_ROOT.resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    return candidate


def float_close(left: float, right: float, *, atol: float = 1.0e-12) -> bool:
    return math.isfinite(left) and math.isfinite(right) and abs(left - right) <= atol


def mat_source_column(method: str, floor: str) -> str:
    """Return the exact zero-based response tensor expression used by plotter."""
    return f"response_mm[:,{MAT_FLOOR_INDEX[floor]},{MAT_METHOD_INDEX[method]}]"


def csv_source_column(method: str, floor: str) -> str:
    """Map the same floor/method to the independently read adapted-run CSV."""
    floor_map = {"Floor 1": "一层", "Floor 2": "二层", "Floor 3": "三层"}
    method_map = {
        "Original": "原结构",
        "Guyan": "Guyan",
        "Craig-Bampton": "CraigBampton",
    }
    return f"{method_map[method]}_{floor_map[floor]}_mm"


def expected_versions(object_id: str, object_directory: str) -> list[dict[str, Any]]:
    if object_id == "F3-15":
        return [
            {
                "version": "paper_historical_composite",
                "figure_basename": "F3-15_论文历史组合版",
                "panels": [
                    {
                        "panel": "full",
                        "source_dataset": "division2_chirp",
                        "floors": ["Floor 3"],
                        "methods": PLOTTING_METHOD_ORDER,
                        "window_start_s": 0.0,
                        "window_end_s": 40.0,
                    },
                    {
                        "panel": "zoom_1",
                        "source_dataset": "division2_elcentro",
                        "floors": ["Floor 3"],
                        "methods": PLOTTING_METHOD_ORDER,
                        "window_start_s": 10.0,
                        "window_end_s": 11.0,
                    },
                    {
                        "panel": "zoom_2",
                        "source_dataset": "division2_elcentro",
                        "floors": ["Floor 3"],
                        "methods": PLOTTING_METHOD_ORDER,
                        "window_start_s": 21.5,
                        "window_end_s": 22.5,
                    },
                ],
            },
            {
                "version": "physically_consistent_corrected",
                "figure_basename": "F3-15_物理一致修正版",
                "panels": [
                    {
                        "panel": panel,
                        "source_dataset": "division2_chirp",
                        "floors": ["Floor 3"],
                        "methods": PLOTTING_METHOD_ORDER,
                        "window_start_s": start,
                        "window_end_s": end,
                    }
                    for panel, start, end in WINDOWS["chirp"]
                ],
            },
        ]

    dataset_id, floors, route_kind = OBJECT_ROUTE[object_id]
    methods = ["Original"] if object_id == "F3-5" else PLOTTING_METHOD_ORDER
    return [
        {
            "version": "standard",
            "figure_basename": object_directory,
            "panels": [
                {
                    "panel": panel,
                    "source_dataset": dataset_id,
                    "floors": list(floors),
                    "methods": list(methods),
                    "window_start_s": start,
                    "window_end_s": end,
                }
                for panel, start, end in WINDOWS[route_kind]
            ],
        }
    ]


def expected_group_signatures(
    version_specs: Iterable[dict[str, Any]],
) -> set[tuple[str, str, str, str, str, str, float, float]]:
    signatures: set[tuple[str, str, str, str, str, str, float, float]] = set()
    for version_spec in version_specs:
        version = version_spec["version"]
        for panel_spec in version_spec["panels"]:
            dataset_id = panel_spec["source_dataset"]
            for floor in panel_spec["floors"]:
                for method in panel_spec["methods"]:
                    signatures.add(
                        (
                            version,
                            panel_spec["panel"],
                            dataset_id,
                            floor,
                            method,
                            mat_source_column(method, floor),
                            float(panel_spec["window_start_s"]),
                            float(panel_spec["window_end_s"]),
                        )
                    )
    return signatures


def normalize_floor_contract(value: Any) -> list[str]:
    if isinstance(value, list):
        values = [str(item) for item in value]
    elif isinstance(value, str):
        values = re.findall(r"Floor\s*[123]", value)
        if not values:
            values = [value]
    else:
        values = [str(value)]
    normalized = [re.sub(r"Floor\s*", "Floor ", item).strip() for item in values]
    return normalized


def validate_dependencies() -> dict[str, str | None]:
    dependency_paths: dict[str, str | None] = {}
    for executable in ("pdfinfo", "pdffonts", "pdfimages"):
        dependency_paths[executable] = shutil.which(executable)
        record(
            "dependency",
            f"{executable}可执行文件存在",
            dependency_paths[executable] is not None,
            expected="可从PATH解析",
            actual=dependency_paths[executable] or "MISSING",
        )
    for module_name in ("numpy", "Pillow"):
        error = IMPORT_ERRORS.get(module_name)
        record(
            "dependency",
            f"Python依赖{module_name}可导入",
            error is None,
            expected="IMPORT_OK",
            actual="IMPORT_OK" if error is None else error,
        )
    return dependency_paths


def validate_figure_contract() -> dict[str, dict[str, str]]:
    if not FIGURE_CONTRACT_PATH.is_file():
        record(
            "figure_contract",
            "逐图合同文件存在",
            False,
            expected=str(FIGURE_CONTRACT_PATH),
            actual="MISSING",
        )
        return {}
    header, rows = read_csv_rows(FIGURE_CONTRACT_PATH)
    record(
        "figure_contract",
        "逐图合同列严格一致",
        header == FIGURE_CONTRACT_COLUMNS,
        expected=FIGURE_CONTRACT_COLUMNS,
        actual=header,
        path=FIGURE_CONTRACT_PATH,
    )
    ids = [row.get("对象ID", "") for row in rows]
    numbers = [row.get("唯一图号", "") for row in rows]
    names = [row.get("图名", "") for row in rows]
    record(
        "figure_contract",
        "逐图合同恰有11个对象",
        len(rows) == 11 and set(ids) == EXPECTED_OBJECT_SET,
        expected=EXPECTED_OBJECT_IDS,
        actual=ids,
        path=FIGURE_CONTRACT_PATH,
    )
    record(
        "figure_contract",
        "对象ID唯一",
        len(ids) == len(set(ids)),
        expected=11,
        actual=len(set(ids)),
        path=FIGURE_CONTRACT_PATH,
    )
    record(
        "figure_contract",
        "唯一图号唯一",
        len(numbers) == len(set(numbers)) == 11,
        expected=11,
        actual=len(set(numbers)),
        path=FIGURE_CONTRACT_PATH,
    )
    record(
        "figure_contract",
        "图名非空且唯一",
        all(names) and len(names) == len(set(names)) == 11,
        expected=11,
        actual=len(set(names)),
        path=FIGURE_CONTRACT_PATH,
    )
    by_id = {row.get("对象ID", ""): row for row in rows}
    for object_id in EXPECTED_OBJECT_IDS:
        row = by_id.get(object_id)
        expected_number = object_id.replace("F", "")
        record(
            "figure_contract",
            "对象ID与唯一图号对应",
            row is not None and row.get("唯一图号") == expected_number,
            expected=expected_number,
            actual="MISSING" if row is None else row.get("唯一图号"),
            object_id=object_id,
            path=FIGURE_CONTRACT_PATH,
        )
    return by_id


def discover_object_directories() -> dict[str, Path]:
    if not CANDIDATE_ROOT.is_dir():
        record(
            "candidate_structure",
            "候选图根目录存在",
            False,
            expected=str(CANDIDATE_ROOT),
            actual="MISSING",
        )
        return {}
    record(
        "candidate_structure",
        "候选图根目录存在",
        True,
        expected=str(CANDIDATE_ROOT),
        actual=str(CANDIDATE_ROOT),
    )
    mapping: dict[str, Path] = {}
    invalid: list[str] = []
    for entry in sorted(CANDIDATE_ROOT.iterdir(), key=lambda item: item.name):
        if not entry.is_dir():
            continue
        match = re.fullmatch(r"(F3-(?:[5-9]|1[0-5]))_(.+)", entry.name)
        if match is None:
            invalid.append(entry.name)
            continue
        object_id = match.group(1)
        if object_id in mapping:
            invalid.append(entry.name)
        else:
            mapping[object_id] = entry
    STATS["object_count_observed"] = len(mapping)
    record(
        "candidate_structure",
        "11个对象目录命名且唯一",
        len(mapping) == 11 and set(mapping) == EXPECTED_OBJECT_SET and not invalid,
        expected={"ids": EXPECTED_OBJECT_IDS, "invalid": []},
        actual={"ids": list(mapping), "invalid": invalid},
        path=CANDIDATE_ROOT,
    )
    return mapping


def load_raw_datasets() -> dict[str, dict[str, Any]]:
    datasets: dict[str, dict[str, Any]] = {}
    if np is None:
        record(
            "raw_data",
            "原始响应CSV可载入",
            False,
            expected="numpy可用",
            actual="numpy缺失",
        )
        return datasets
    for dataset_id, filename in RAW_DATASETS.items():
        path = RAW_INPUT_ROOT / filename
        if not path.is_file():
            record(
                "raw_data",
                "原始响应CSV存在",
                False,
                expected=str(path),
                actual="MISSING",
                artifact=dataset_id,
                path=path,
            )
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            header = list(reader.fieldnames or [])
            columns: dict[str, list[float]] = {name: [] for name in header}
            parse_errors: list[str] = []
            for row_number, row in enumerate(reader, start=2):
                try:
                    for name in header:
                        columns[name].append(float(row[name]))
                except Exception as exc:
                    if len(parse_errors) < 10:
                        parse_errors.append(f"row {row_number}: {type(exc).__name__}: {exc}")
        record(
            "raw_data",
            "原始响应CSV列严格一致",
            header == RAW_COLUMNS,
            expected=RAW_COLUMNS,
            actual=header,
            artifact=dataset_id,
            path=path,
        )
        record(
            "raw_data",
            "原始响应CSV可解析",
            not parse_errors and bool(columns.get("时间_s")),
            expected="0 errors and nonempty",
            actual={"errors": parse_errors, "rows": len(columns.get("时间_s", []))},
            artifact=dataset_id,
            path=path,
        )
        if parse_errors or header != RAW_COLUMNS:
            continue
        arrays = {name: np.asarray(values, dtype=np.float64) for name, values in columns.items()}
        time = arrays["时间_s"]
        all_finite = all(np.isfinite(values).all() for values in arrays.values())
        time_increasing = len(time) == 40961 and np.all(np.diff(time) > 0.0)
        record(
            "raw_data",
            "原始响应CSV有限且时间严格递增",
            bool(all_finite and time_increasing),
            expected={"rows": 40961, "finite": True, "strictly_increasing": True},
            actual={
                "rows": int(len(time)),
                "finite": bool(all_finite),
                "strictly_increasing": bool(len(time) > 1 and np.all(np.diff(time) > 0.0)),
            },
            artifact=dataset_id,
            path=path,
        )
        if all_finite and time_increasing:
            datasets[dataset_id] = {
                "path": path,
                "time": time,
                "columns": arrays,
                "mat_filename": RAW_MAT_FILENAMES[dataset_id],
            }
    return datasets


def validate_contract_json(
    path: Path,
    object_id: str,
    object_name: str,
    object_directory: str,
    version_specs: list[dict[str, Any]],
) -> dict[str, Any] | None:
    if not path.is_file():
        record(
            "object_contract",
            "contract.json存在",
            False,
            expected=str(path),
            actual="MISSING",
            object_id=object_id,
            path=path,
        )
        return None
    try:
        contract = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        record(
            "object_contract",
            "contract.json可解析",
            False,
            expected="valid JSON",
            actual=f"{type(exc).__name__}: {exc}",
            object_id=object_id,
            path=path,
        )
        return None
    expected_top_level_keys = set(CONTRACT_TOP_LEVEL_KEYS)
    if object_id == "F3-15":
        expected_top_level_keys.add("figure_3_15_exception")
    record(
        "object_contract",
        "contract.json顶层键严格一致",
        isinstance(contract, dict) and set(contract) == expected_top_level_keys,
        expected=sorted(expected_top_level_keys),
        actual=sorted(contract) if isinstance(contract, dict) else type(contract).__name__,
        object_id=object_id,
        path=path,
    )
    if not isinstance(contract, dict):
        return None
    if object_id == "F3-15":
        exception = contract.get("figure_3_15_exception")
        exception_ok = (
            isinstance(exception, dict)
            and set(exception)
            == {"paper_historical_composite", "physically_consistent_corrected"}
            and all(isinstance(value, str) and value.strip() for value in exception.values())
        )
        record(
            "object_contract",
            "图3-15专属异常说明包含且仅包含两个版本",
            exception_ok,
            expected=["paper_historical_composite", "physically_consistent_corrected"],
            actual=exception,
            object_id=object_id,
            path=path,
        )
    identity_ok = (
        contract.get("object_id") == object_id
        and contract.get("figure_number") == object_id.replace("F", "")
        and contract.get("object_name") == object_name
        and contract.get("object_directory") == object_directory
    )
    record(
        "object_contract",
        "对象身份与总合同一致",
        identity_ok,
        expected={
            "object_id": object_id,
            "figure_number": object_id.replace("F", ""),
            "object_name": object_name,
            "object_directory": object_directory,
        },
        actual={
            key: contract.get(key)
            for key in ("object_id", "figure_number", "object_name", "object_directory")
        },
        object_id=object_id,
        path=path,
    )
    record(
        "object_contract",
        "MAT与绘图顺序合同一致",
        contract.get("mat_method_order") == MAT_METHOD_ORDER
        and contract.get("mat_floor_order") == MAT_FLOOR_ORDER
        and contract.get("plotting_method_order") == PLOTTING_METHOD_ORDER,
        expected={
            "mat_method_order": MAT_METHOD_ORDER,
            "mat_floor_order": MAT_FLOOR_ORDER,
            "plotting_method_order": PLOTTING_METHOD_ORDER,
        },
        actual={
            "mat_method_order": contract.get("mat_method_order"),
            "mat_floor_order": contract.get("mat_floor_order"),
            "plotting_method_order": contract.get("plotting_method_order"),
        },
        object_id=object_id,
        path=path,
    )
    actual_versions = contract.get("versions")
    versions_ok = isinstance(actual_versions, list)
    actual_by_name = {
        item.get("version"): item
        for item in actual_versions or []
        if isinstance(item, dict) and isinstance(item.get("version"), str)
    }
    versions_ok = versions_ok and len(actual_by_name) == len(version_specs)
    versions_ok = versions_ok and set(actual_by_name) == {
        item["version"] for item in version_specs
    }
    record(
        "object_contract",
        "版本集合严格一致",
        versions_ok,
        expected=[item["version"] for item in version_specs],
        actual=list(actual_by_name),
        object_id=object_id,
        path=path,
    )
    for expected_version in version_specs:
        version = expected_version["version"]
        actual_version = actual_by_name.get(version)
        if actual_version is None:
            continue
        basename_ok = actual_version.get("figure_basename") == expected_version["figure_basename"]
        record(
            "object_contract",
            "版本图文件基名一致",
            basename_ok,
            expected=expected_version["figure_basename"],
            actual=actual_version.get("figure_basename"),
            object_id=object_id,
            version=version,
            path=path,
        )
        panels = actual_version.get("panels")
        panel_by_name = {
            item.get("panel"): item
            for item in panels or []
            if isinstance(item, dict) and isinstance(item.get("panel"), str)
        }
        expected_panel_by_name = {
            item["panel"]: item for item in expected_version["panels"]
        }
        panel_set_ok = (
            isinstance(panels, list)
            and len(panel_by_name) == len(expected_panel_by_name)
            and set(panel_by_name) == set(expected_panel_by_name)
        )
        record(
            "object_contract",
            "面板集合严格一致",
            panel_set_ok,
            expected=list(expected_panel_by_name),
            actual=list(panel_by_name),
            object_id=object_id,
            version=version,
            path=path,
        )
        for panel_name, expected_panel in expected_panel_by_name.items():
            actual_panel = panel_by_name.get(panel_name)
            if actual_panel is None:
                continue
            core_keys = {
                "panel",
                "source_dataset",
                "floors",
                "methods",
                "window_start_s",
                "window_end_s",
            }
            additional_keys = {"source_mat_filename", "window_inclusive"}
            actual_core = {key: actual_panel.get(key) for key in core_keys}
            try:
                actual_start = float(actual_panel.get("window_start_s"))
                actual_end = float(actual_panel.get("window_end_s"))
            except (TypeError, ValueError):
                actual_start = math.nan
                actual_end = math.nan
            panel_ok = (
                core_keys.issubset(actual_panel)
                and actual_panel.get("panel") == panel_name
                and actual_panel.get("source_dataset") == expected_panel["source_dataset"]
                and normalize_floor_contract(actual_panel.get("floors"))
                == expected_panel["floors"]
                and actual_panel.get("methods") == expected_panel["methods"]
            )
            panel_ok = panel_ok and float_close(
                actual_start, expected_panel["window_start_s"], atol=1.0e-14
            )
            panel_ok = panel_ok and float_close(
                actual_end, expected_panel["window_end_s"], atol=1.0e-14
            )
            record(
                "object_contract",
                "面板数据源、楼层、方法和时间窗一致",
                panel_ok,
                expected=expected_panel,
                actual=actual_core,
                object_id=object_id,
                version=version,
                artifact=panel_name,
                path=path,
            )
            expected_source_mat = RAW_MAT_FILENAMES[expected_panel["source_dataset"]]
            additions_ok = (
                set(actual_panel) == core_keys | additional_keys
                and actual_panel.get("source_mat_filename") == expected_source_mat
                and actual_panel.get("window_inclusive") is True
            )
            record(
                "object_contract",
                "面板附加MAT文件名与闭区间标志严格一致",
                additions_ok,
                expected={
                    "exact_keys": sorted(core_keys | additional_keys),
                    "source_mat_filename": expected_source_mat,
                    "window_inclusive": True,
                },
                actual={
                    "keys": sorted(actual_panel),
                    "source_mat_filename": actual_panel.get("source_mat_filename"),
                    "window_inclusive": actual_panel.get("window_inclusive"),
                },
                object_id=object_id,
                version=version,
                artifact=panel_name,
                path=path,
            )
    return contract


GroupKey = tuple[str, str, str, str, str, str, str, float, float]


def read_and_validate_plot_data(
    path: Path,
    object_id: str,
    object_name: str,
    version_specs: list[dict[str, Any]],
    raw_datasets: dict[str, dict[str, Any]],
) -> dict[GroupKey, dict[str, Any]]:
    groups: dict[GroupKey, dict[str, Any]] = {}
    if np is None:
        record(
            "plot_data",
            "逐点绘图数据可复核",
            False,
            expected="numpy可用",
            actual="numpy缺失",
            object_id=object_id,
            path=path,
        )
        return groups
    if not path.is_file():
        record(
            "plot_data",
            "figure_plot_data.csv存在",
            False,
            expected=str(path),
            actual="MISSING",
            object_id=object_id,
            path=path,
        )
        return groups
    parse_errors: list[str] = []
    row_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        header = list(reader.fieldnames or [])
        record(
            "plot_data",
            "figure_plot_data.csv列严格一致",
            header == PLOT_DATA_COLUMNS,
            expected=PLOT_DATA_COLUMNS,
            actual=header,
            object_id=object_id,
            path=path,
        )
        for row_number, row in enumerate(reader, start=2):
            row_count += 1
            try:
                if row["object_id"] != object_id:
                    raise ValueError(f"object_id={row['object_id']!r}")
                if row["object_name"] != object_name:
                    raise ValueError(f"object_name={row['object_name']!r}")
                time_s = float(row["time_s"])
                response_mm = float(row["response_mm"])
                value_mm = float(row["value_mm"])
                window_start = float(row["window_start_s"])
                window_end = float(row["window_end_s"])
                numeric = (time_s, response_mm, value_mm, window_start, window_end)
                if not all(math.isfinite(value) for value in numeric):
                    raise ValueError("non-finite numeric value")
                key: GroupKey = (
                    row["version"],
                    row["panel"],
                    row["source_dataset"],
                    row["source_mat_filename"],
                    row["source_column"],
                    row["floor"],
                    row["method"],
                    window_start,
                    window_end,
                )
                if key not in groups:
                    groups[key] = {
                        "times": [],
                        "values": [],
                        "responses": [],
                        "first_row": row_number,
                    }
                groups[key]["times"].append(time_s)
                groups[key]["values"].append(value_mm)
                groups[key]["responses"].append(response_mm)
            except Exception as exc:
                if len(parse_errors) < 10:
                    parse_errors.append(f"row {row_number}: {type(exc).__name__}: {exc}")
    record(
        "plot_data",
        "figure_plot_data.csv逐行可解析且身份一致",
        row_count > 0 and not parse_errors,
        expected="nonempty, finite, matching object identity",
        actual={"rows": row_count, "errors": parse_errors},
        object_id=object_id,
        path=path,
    )
    observed_signatures = {
        (version, panel, dataset, floor, method, source_column, start, end)
        for (
            version,
            panel,
            dataset,
            _source_mat,
            source_column,
            floor,
            method,
            start,
            end,
        ) in groups
    }
    expected_signatures = expected_group_signatures(version_specs)
    record(
        "plot_data",
        "逐点数据分组合同严格一致",
        observed_signatures == expected_signatures,
        expected=sorted(expected_signatures),
        actual=sorted(observed_signatures),
        object_id=object_id,
        path=path,
    )
    for key, payload in groups.items():
        (
            version,
            panel,
            dataset_id,
            source_mat_filename,
            source_column,
            floor,
            method,
            start,
            end,
        ) = key
        times = np.asarray(payload["times"], dtype=np.float64)
        values = np.asarray(payload["values"], dtype=np.float64)
        responses = np.asarray(payload["responses"], dtype=np.float64)
        payload["times"] = times
        payload["values"] = values
        payload["responses"] = responses
        finite = bool(
            np.isfinite(times).all()
            and np.isfinite(values).all()
            and np.isfinite(responses).all()
        )
        increasing = bool(len(times) > 0 and (len(times) == 1 or np.all(np.diff(times) > 0.0)))
        response_alias_error = (
            float(np.max(np.abs(values - responses))) if len(values) else math.inf
        )
        window_ok = bool(
            len(times)
            and times[0] >= start - 1.0e-14
            and times[-1] <= end + 1.0e-14
        )
        record(
            "plot_data",
            "组内时间有限递增、窗内且value_mm等于response_mm",
            finite and increasing and window_ok and response_alias_error <= 1.0e-15,
            expected={
                "finite": True,
                "strictly_increasing": True,
                "window": [start, end],
                "max_value_response_abs_diff_mm": "<=1e-15",
            },
            actual={
                "samples": int(len(times)),
                "finite": finite,
                "strictly_increasing": increasing,
                "first_time_s": float(times[0]) if len(times) else None,
                "last_time_s": float(times[-1]) if len(times) else None,
                "max_value_response_abs_diff_mm": response_alias_error,
            },
            object_id=object_id,
            version=version,
            artifact=panel,
            path=path,
        )
        expected_column = None
        expected_csv_column = None
        if method in PLOTTING_METHOD_ORDER and floor in MAT_FLOOR_ORDER:
            expected_column = mat_source_column(method, floor)
            expected_csv_column = csv_source_column(method, floor)
        source_identity_ok = (
            dataset_id in RAW_MAT_FILENAMES
            and source_mat_filename == RAW_MAT_FILENAMES.get(dataset_id)
            and source_column == expected_column
        )
        record(
            "plot_data",
            "数据集、MAT文件与方法列映射一致",
            source_identity_ok,
            expected={
                "source_mat_filename": RAW_MAT_FILENAMES.get(dataset_id),
                "source_column_mat_expression": expected_column,
                "independent_csv_column": expected_csv_column,
            },
            actual={
                "source_mat_filename": source_mat_filename,
                "source_column": source_column,
            },
            object_id=object_id,
            version=version,
            artifact=panel,
            path=path,
        )
        raw = raw_datasets.get(dataset_id)
        if raw is None or expected_csv_column not in raw.get("columns", {}):
            record(
                "plot_data",
                "逐点回查adapted_run1原始响应",
                False,
                expected=f"available {dataset_id}/{expected_csv_column}",
                actual="MISSING",
                object_id=object_id,
                version=version,
                artifact=panel,
                path=path,
            )
            continue
        raw_time = raw["time"]
        mask = (raw_time >= start - 1.0e-14) & (raw_time <= end + 1.0e-14)
        expected_time = raw_time[mask]
        expected_values = raw["columns"][expected_csv_column][mask]
        same_length = len(times) == len(expected_time)
        time_error = (
            float(np.max(np.abs(times - expected_time))) if same_length and len(times) else math.inf
        )
        value_error = (
            float(np.max(np.abs(values - expected_values)))
            if same_length and len(values)
            else math.inf
        )
        record(
            "plot_data",
            "逐点回查adapted_run1原始响应",
            same_length and time_error <= 1.0e-14 and value_error <= 1.0e-12,
            expected={
                "samples": int(len(expected_time)),
                "max_time_abs_diff_s": "<=1e-14",
                "max_value_abs_diff_mm": "<=1e-12",
            },
            actual={
                "samples": int(len(times)),
                "max_time_abs_diff_s": time_error,
                "max_value_abs_diff_mm": value_error,
            },
            object_id=object_id,
            version=version,
            artifact=panel,
            path=path,
        )
    return groups


def validate_metrics(
    path: Path,
    object_id: str,
    object_name: str,
    groups: dict[GroupKey, dict[str, Any]],
) -> None:
    if np is None:
        record(
            "metrics",
            "指标可独立复算",
            False,
            expected="numpy可用",
            actual="numpy缺失",
            object_id=object_id,
            path=path,
        )
        return
    if not path.is_file():
        record(
            "metrics",
            "metrics.csv存在",
            False,
            expected=str(path),
            actual="MISSING",
            object_id=object_id,
            path=path,
        )
        return
    header, rows = read_csv_rows(path)
    record(
        "metrics",
        "metrics.csv列严格一致",
        header == METRICS_COLUMNS,
        expected=METRICS_COLUMNS,
        actual=header,
        object_id=object_id,
        path=path,
    )
    metric_by_group: dict[GroupKey, dict[str, str]] = {}
    errors: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        try:
            if row["object_id"] != object_id or row["object_name"] != object_name:
                raise ValueError("object identity mismatch")
            start = float(row["window_start_s"])
            end = float(row["window_end_s"])
            key: GroupKey = (
                row["version"],
                row["panel"],
                row["source_dataset"],
                row["source_mat_filename"],
                row["source_column"],
                row["floor"],
                row["method"],
                start,
                end,
            )
            if key in metric_by_group:
                raise ValueError("duplicate metric group")
            metric_by_group[key] = row
        except Exception as exc:
            if len(errors) < 10:
                errors.append(f"row {row_number}: {type(exc).__name__}: {exc}")
    record(
        "metrics",
        "指标行与逐点数据分组一一对应",
        not errors and set(metric_by_group) == set(groups),
        expected={"group_count": len(groups), "groups": sorted(groups)},
        actual={
            "group_count": len(metric_by_group),
            "groups": sorted(metric_by_group),
            "errors": errors,
        },
        object_id=object_id,
        path=path,
    )
    for key, row in metric_by_group.items():
        payload = groups.get(key)
        version, panel = key[0], key[1]
        if payload is None:
            continue
        values = payload["values"]
        expected_metrics = {
            "sample_count": int(len(values)),
            "peak_abs_mm": float(np.max(np.abs(values))),
            "rms_mm": float(np.sqrt(np.mean(values * values))),
            "final_mm": float(values[-1]),
            "min_mm": float(np.min(values)),
            "max_mm": float(np.max(values)),
        }
        try:
            observed_metrics = {
                "sample_count": int(row["sample_count"]),
                "peak_abs_mm": float(row["peak_abs_mm"]),
                "rms_mm": float(row["rms_mm"]),
                "final_mm": float(row["final_mm"]),
                "min_mm": float(row["min_mm"]),
                "max_mm": float(row["max_mm"]),
            }
            finite = all(
                math.isfinite(float(value)) for value in observed_metrics.values()
            )
            numeric_ok = observed_metrics["sample_count"] == expected_metrics["sample_count"]
            for name in (
                "peak_abs_mm",
                "rms_mm",
                "final_mm",
                "min_mm",
                "max_mm",
            ):
                tolerance = max(1.0e-12, abs(expected_metrics[name]) * 1.0e-10)
                numeric_ok = numeric_ok and abs(
                    observed_metrics[name] - expected_metrics[name]
                ) <= tolerance
            status_ok = row.get("status") == "PASS"
        except Exception:
            observed_metrics = {name: row.get(name) for name in expected_metrics}
            finite = False
            numeric_ok = False
            status_ok = False
        record(
            "metrics",
            "指标有限、状态PASS且由逐点数据独立复算一致",
            finite and numeric_ok and status_ok,
            expected={**expected_metrics, "status": "PASS"},
            actual={**observed_metrics, "status": row.get("status")},
            object_id=object_id,
            version=version,
            artifact=panel,
            path=path,
        )


def run_tool(executable: str, args: list[str]) -> tuple[int, str, str]:
    encoding = locale.getpreferredencoding(False) or "utf-8"
    completed = subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        encoding=encoding,
        errors="replace",
        timeout=60,
        check=False,
    )
    return completed.returncode, completed.stdout, completed.stderr


def validate_pdf(
    path: Path,
    object_id: str,
    version: str,
    tools: dict[str, str | None],
) -> None:
    media_width = math.nan
    media_height = math.nan
    pdfinfo = tools.get("pdfinfo")
    if pdfinfo is None:
        record(
            "pdf",
            "pdfinfo解析单页、Page size和正MediaBox",
            False,
            expected="pdfinfo available",
            actual="MISSING",
            object_id=object_id,
            version=version,
            artifact=path.name,
            path=path,
        )
    else:
        try:
            code, stdout, stderr = run_tool(pdfinfo, ["-box", str(path)])
            pages_match = re.search(r"^Pages:\s*(\d+)\s*$", stdout, flags=re.MULTILINE)
            size_match = re.search(
                r"^Page size:\s*([0-9.eE+-]+)\s*x\s*([0-9.eE+-]+)\s*pts",
                stdout,
                flags=re.MULTILINE,
            )
            media_match = re.search(
                r"^MediaBox:\s*([0-9.eE+-]+)\s+([0-9.eE+-]+)\s+"
                r"([0-9.eE+-]+)\s+([0-9.eE+-]+)\s*$",
                stdout,
                flags=re.MULTILINE,
            )
            info_pages = int(pages_match.group(1)) if pages_match else None
            info_width = float(size_match.group(1)) if size_match else math.nan
            info_height = float(size_match.group(2)) if size_match else math.nan
            if media_match:
                media_x0, media_y0, media_x1, media_y1 = (
                    float(media_match.group(index)) for index in range(1, 5)
                )
                media_width = media_x1 - media_x0
                media_height = media_y1 - media_y0
            info_ok = (
                code == 0
                and info_pages == 1
                and info_width > 0.0
                and info_height > 0.0
                and media_width > 0.0
                and media_height > 0.0
            )
            record(
                "pdf",
                "pdfinfo解析单页、Page size和正MediaBox",
                info_ok,
                expected={
                    "returncode": 0,
                    "pages": 1,
                    "page_size": "positive",
                    "media_box": "positive width and height",
                },
                actual={
                    "returncode": code,
                    "pages": info_pages,
                    "page_width_pt": info_width,
                    "page_height_pt": info_height,
                    "media_width_pt": media_width,
                    "media_height_pt": media_height,
                    "stderr": stderr.strip(),
                },
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )
        except Exception as exc:
            record(
                "pdf",
                "pdfinfo解析单页、Page size和正MediaBox",
                False,
                expected="successful parse",
                actual=f"{type(exc).__name__}: {exc}",
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )

    pdffonts = tools.get("pdffonts")
    if pdffonts is None:
        record(
            "pdf",
            "pdffonts确认无Type 3字体",
            False,
            expected="pdffonts available",
            actual="MISSING",
            object_id=object_id,
            version=version,
            artifact=path.name,
            path=path,
        )
    else:
        try:
            code, stdout, stderr = run_tool(pdffonts, [str(path)])
            type3 = bool(re.search(r"\bType\s*3\b", stdout, flags=re.IGNORECASE))
            font_rows = [
                line
                for line in stdout.splitlines()
                if line.strip()
                and not line.lower().lstrip().startswith("name")
                and not set(line.strip()) <= {"-", " "}
            ]
            record(
                "pdf",
                "pdffonts确认无Type 3字体",
                code == 0 and not type3,
                expected={"returncode": 0, "type3": False},
                actual={
                    "returncode": code,
                    "type3": type3,
                    "font_row_count": len(font_rows),
                    "stderr": stderr.strip(),
                },
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )
        except Exception as exc:
            record(
                "pdf",
                "pdffonts确认无Type 3字体",
                False,
                expected="successful parse",
                actual=f"{type(exc).__name__}: {exc}",
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )

    pdfimages = tools.get("pdfimages")
    if pdfimages is None:
        record(
            "pdf",
            "pdfimages确认无覆盖整页的大栅格图",
            False,
            expected="pdfimages available",
            actual="MISSING",
            object_id=object_id,
            version=version,
            artifact=path.name,
            path=path,
        )
    else:
        try:
            code, stdout, stderr = run_tool(pdfimages, ["-list", str(path)])
            images: list[dict[str, float | int | str]] = []
            for line in stdout.splitlines():
                parts = line.split()
                if len(parts) < 14 or not parts[0].isdigit() or not parts[1].isdigit():
                    continue
                try:
                    width_px = int(parts[3])
                    height_px = int(parts[4])
                    x_ppi = float(parts[12])
                    y_ppi = float(parts[13])
                    width_fraction = (
                        (width_px / x_ppi * 72.0) / media_width
                        if x_ppi > 0.0 and media_width > 0.0
                        else math.nan
                    )
                    height_fraction = (
                        (height_px / y_ppi * 72.0) / media_height
                        if y_ppi > 0.0 and media_height > 0.0
                        else math.nan
                    )
                    images.append(
                        {
                            "type": parts[2],
                            "width_px": width_px,
                            "height_px": height_px,
                            "x_ppi": x_ppi,
                            "y_ppi": y_ppi,
                            "width_fraction": width_fraction,
                            "height_fraction": height_fraction,
                        }
                    )
                except (ValueError, IndexError):
                    continue
            covering = [
                item
                for item in images
                if math.isfinite(float(item["width_fraction"]))
                and math.isfinite(float(item["height_fraction"]))
                and (
                    (
                        float(item["width_fraction"]) >= 0.80
                        and float(item["height_fraction"]) >= 0.80
                    )
                    or float(item["width_fraction"]) * float(item["height_fraction"])
                    >= 0.70
                )
            ]
            max_area = max(
                (
                    float(item["width_fraction"]) * float(item["height_fraction"])
                    for item in images
                    if math.isfinite(float(item["width_fraction"]))
                    and math.isfinite(float(item["height_fraction"]))
                ),
                default=0.0,
            )
            record(
                "pdf",
                "pdfimages确认无覆盖整页的大栅格图",
                code == 0 and not covering,
                expected={
                    "returncode": 0,
                    "covering_image_count": 0,
                    "rule": "width>=0.80 and height>=0.80, or area>=0.70",
                },
                actual={
                    "returncode": code,
                    "image_count": len(images),
                    "covering_image_count": len(covering),
                    "max_page_area_fraction": max_area,
                    "stderr": stderr.strip(),
                },
                detail=(
                    "无嵌入图像，曲线图为纯矢量候选"
                    if not images
                    else "存在小型嵌入图像，但没有覆盖整页的大图"
                ),
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )
        except Exception as exc:
            record(
                "pdf",
                "pdfimages确认无覆盖整页的大栅格图",
                False,
                expected="successful parse",
                actual=f"{type(exc).__name__}: {exc}",
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )


def validate_png(path: Path, object_id: str, version: str) -> None:
    if Image is None or np is None:
        record(
            "png",
            "PNG像素、DPI、白底和非空性可检查",
            False,
            expected="Pillow and numpy available",
            actual={"Pillow": Image is not None, "numpy": np is not None},
            object_id=object_id,
            version=version,
            artifact=path.name,
            path=path,
        )
        return
    try:
        with Image.open(path) as image:
            image.load()
            width, height = image.size
            dpi_raw = image.info.get("dpi")
            if isinstance(dpi_raw, (tuple, list)) and len(dpi_raw) >= 2:
                dpi_x = float(dpi_raw[0])
                dpi_y = float(dpi_raw[1])
            else:
                dpi_x = math.nan
                dpi_y = math.nan
            size_ok = width > 0 and height > 0
            dpi_ok = math.isfinite(dpi_x) and math.isfinite(dpi_y) and min(dpi_x, dpi_y) >= 590.0
            record(
                "png",
                "PNG像素为正且实际DPI不低于590",
                size_ok and dpi_ok,
                expected={"width_px": ">0", "height_px": ">0", "dpi_min": 590.0},
                actual={
                    "width_px": width,
                    "height_px": height,
                    "dpi_x": dpi_x,
                    "dpi_y": dpi_y,
                    "mode": image.mode,
                },
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )
            sample = image.convert("RGBA")
            sample.thumbnail((512, 512), Image.Resampling.LANCZOS)
            rgba = np.asarray(sample, dtype=np.float64)
            alpha = rgba[..., 3] / 255.0
            transparent_fraction = float(np.mean(alpha < 0.99))
            rgb = rgba[..., :3] * alpha[..., None] + 255.0 * (1.0 - alpha[..., None])
            white = np.all(rgb >= 245.0, axis=2)
            white_fraction = float(np.mean(white))
            band = max(1, min(rgb.shape[0], rgb.shape[1]) // 50)
            border = np.concatenate(
                [
                    white[:band, :].ravel(),
                    white[-band:, :].ravel(),
                    white[:, :band].ravel(),
                    white[:, -band:].ravel(),
                ]
            )
            border_white_fraction = float(np.mean(border))
            nonwhite_fraction = 1.0 - white_fraction
            dynamic_range = float(np.max(rgb) - np.min(rgb))
            background_ok = (
                0.20 <= white_fraction <= 0.997
                and border_white_fraction >= 0.60
                and nonwhite_fraction >= 0.003
                and dynamic_range >= 20.0
                and transparent_fraction <= 0.01
            )
            record(
                "png",
                "PNG白底合理、内容非空且非透明整图",
                background_ok,
                expected={
                    "white_fraction": "0.20..0.997",
                    "border_white_fraction": ">=0.60",
                    "nonwhite_fraction": ">=0.003",
                    "dynamic_range": ">=20",
                    "transparent_fraction": "<=0.01",
                },
                actual={
                    "white_fraction": white_fraction,
                    "border_white_fraction": border_white_fraction,
                    "nonwhite_fraction": nonwhite_fraction,
                    "dynamic_range": dynamic_range,
                    "transparent_fraction": transparent_fraction,
                    "sample_width_px": int(rgb.shape[1]),
                    "sample_height_px": int(rgb.shape[0]),
                },
                object_id=object_id,
                version=version,
                artifact=path.name,
                path=path,
            )
    except Exception as exc:
        record(
            "png",
            "PNG可由Pillow完整读取",
            False,
            expected="readable PNG",
            actual=f"{type(exc).__name__}: {exc}",
            object_id=object_id,
            version=version,
            artifact=path.name,
            path=path,
        )


def validate_manifest_and_artifacts(
    object_dirs: dict[str, Path],
    figure_contract: dict[str, dict[str, str]],
    tools: dict[str, str | None],
) -> None:
    manifest_path = CANDIDATE_ROOT / "artifact_manifest.csv"
    if not manifest_path.is_file():
        record(
            "manifest",
            "artifact_manifest.csv存在",
            False,
            expected=str(manifest_path),
            actual="MISSING",
            path=manifest_path,
        )
        return
    header, rows = read_csv_rows(manifest_path)
    STATS["manifest_row_count_observed"] = len(rows)
    record(
        "manifest",
        "artifact_manifest.csv列严格一致",
        header == MANIFEST_COLUMNS,
        expected=MANIFEST_COLUMNS,
        actual=header,
        path=manifest_path,
    )
    record(
        "manifest",
        "清单恰有24行",
        len(rows) == 24,
        expected=24,
        actual=len(rows),
        path=manifest_path,
    )
    relative_paths = [row.get("relative_path", "") for row in rows]
    record(
        "manifest",
        "清单相对路径唯一",
        len(relative_paths) == len(set(relative_paths)) == 24,
        expected=24,
        actual=len(set(relative_paths)),
        path=manifest_path,
    )
    pair_rows: dict[str, list[dict[str, str]]] = defaultdict(list)
    manifest_pdf_paths: set[str] = set()
    manifest_png_paths: set[str] = set()
    for row in rows:
        pair_rows[row.get("figure_pair_id", "")].append(row)
        artifact_type = row.get("artifact_type", "").lower()
        normalized_rel = row.get("relative_path", "").replace("\\", "/")
        if artifact_type == "pdf":
            manifest_pdf_paths.add(normalized_rel)
        elif artifact_type == "png":
            manifest_png_paths.add(normalized_rel)
    STATS["figure_pair_count_observed"] = len(pair_rows)
    STATS["pdf_count_observed"] = len(manifest_pdf_paths)
    STATS["png_count_observed"] = len(manifest_png_paths)
    record(
        "manifest",
        "12个PDF/PNG配对且每对类型齐全",
        len(pair_rows) == 12
        and all(
            len(items) == 2
            and {item.get("artifact_type", "").lower() for item in items} == {"pdf", "png"}
            for items in pair_rows.values()
        ),
        expected={"pair_count": 12, "types_per_pair": ["pdf", "png"]},
        actual={
            "pair_count": len(pair_rows),
            "pairs": {
                key: [item.get("artifact_type") for item in value]
                for key, value in pair_rows.items()
            },
        },
        path=manifest_path,
    )
    pair_counts_by_object = defaultdict(int)
    for items in pair_rows.values():
        if items:
            pair_counts_by_object[items[0].get("object_id", "")] += 1
    expected_pair_counts = {object_id: 1 for object_id in EXPECTED_OBJECT_IDS}
    expected_pair_counts["F3-15"] = 2
    record(
        "manifest",
        "每个对象的图对数量一致",
        dict(pair_counts_by_object) == expected_pair_counts,
        expected=expected_pair_counts,
        actual=dict(pair_counts_by_object),
        path=manifest_path,
    )
    actual_pdf_paths = {
        path.relative_to(CANDIDATE_ROOT).as_posix()
        for path in CANDIDATE_ROOT.rglob("*.pdf")
        if path.is_file()
    }
    actual_png_paths = {
        path.relative_to(CANDIDATE_ROOT).as_posix()
        for path in CANDIDATE_ROOT.rglob("*.png")
        if path.is_file()
    }
    record(
        "manifest",
        "磁盘PDF集合与清单严格一致",
        len(actual_pdf_paths) == 12 and actual_pdf_paths == manifest_pdf_paths,
        expected=sorted(manifest_pdf_paths),
        actual=sorted(actual_pdf_paths),
        path=CANDIDATE_ROOT,
    )
    record(
        "manifest",
        "磁盘PNG集合与清单严格一致",
        len(actual_png_paths) == 12 and actual_png_paths == manifest_png_paths,
        expected=sorted(manifest_png_paths),
        actual=sorted(actual_png_paths),
        path=CANDIDATE_ROOT,
    )

    validated_paths: set[Path] = set()
    for row in rows:
        object_id = row.get("object_id", "")
        version = row.get("version", "")
        artifact_type = row.get("artifact_type", "").lower()
        rel = row.get("relative_path", "")
        path = safe_candidate_path(rel)
        path_ok = path is not None and path.is_file()
        record(
            "manifest",
            "清单相对路径安全且文件存在",
            path_ok,
            expected="safe existing path below candidate root",
            actual=rel,
            object_id=object_id,
            version=version,
            artifact=artifact_type,
            path=path or rel,
        )
        expected_object_dir = object_dirs.get(object_id)
        expected_name = figure_contract.get(object_id, {}).get("图名")
        identity_ok = (
            expected_object_dir is not None
            and expected_name is not None
            and row.get("object_name") == expected_name
        )
        version_specs = (
            expected_versions(object_id, expected_object_dir.name)
            if expected_object_dir is not None and object_id in EXPECTED_OBJECT_SET
            else []
        )
        version_by_name = {item["version"]: item for item in version_specs}
        spec = version_by_name.get(version)
        identity_ok = identity_ok and spec is not None
        if spec is not None:
            identity_ok = identity_ok and row.get("figure_basename") == spec["figure_basename"]
            expected_suffix = f".{artifact_type}"
            identity_ok = identity_ok and path is not None and path.name == spec["figure_basename"] + expected_suffix
        record(
            "manifest",
            "清单对象、版本、基名和扩展名一致",
            identity_ok,
            expected=(spec if spec is not None else "known object/version"),
            actual={
                "object_name": row.get("object_name"),
                "version": version,
                "figure_basename": row.get("figure_basename"),
                "filename": path.name if path is not None else None,
            },
            object_id=object_id,
            version=version,
            artifact=artifact_type,
            path=path or rel,
        )
        reference_ok = True
        reference_actual: dict[str, str] = {}
        for field in (
            "source_data_csv_relative_path",
            "metrics_csv_relative_path",
            "contract_json_relative_path",
        ):
            referenced = safe_candidate_path(row.get(field, ""))
            reference_actual[field] = row.get(field, "")
            reference_ok = reference_ok and referenced is not None and referenced.is_file()
            if expected_object_dir is not None and referenced is not None:
                try:
                    referenced.relative_to(expected_object_dir.resolve())
                except ValueError:
                    reference_ok = False
        record(
            "manifest",
            "清单引用的数据、指标和合同均存在于本对象目录",
            reference_ok,
            expected="three existing files below the object's directory",
            actual=reference_actual,
            object_id=object_id,
            version=version,
            artifact=artifact_type,
            path=manifest_path,
        )
        if not path_ok or path is None:
            continue
        actual_hash = sha256_file(path)
        try:
            expected_size = int(row.get("size_bytes", ""))
        except ValueError:
            expected_size = -1
        hash_ok = actual_hash == row.get("sha256", "").upper()
        size_ok = path.stat().st_size == expected_size
        record(
            "manifest",
            "文件SHA-256与字节数匹配清单",
            hash_ok and size_ok,
            expected={"sha256": row.get("sha256"), "size_bytes": expected_size},
            actual={"sha256": actual_hash, "size_bytes": path.stat().st_size},
            object_id=object_id,
            version=version,
            artifact=artifact_type,
            path=path,
        )
        declared_contract_ok = True
        if artifact_type == "pdf":
            try:
                declared_contract_ok = int(row.get("expected_pdf_pages", "")) == 1
            except ValueError:
                declared_contract_ok = False
        elif artifact_type == "png":
            try:
                declared_contract_ok = float(row.get("expected_png_dpi", "")) >= 600.0
            except ValueError:
                declared_contract_ok = False
        else:
            declared_contract_ok = False
        record(
            "manifest",
            "清单声明的PDF页数或PNG目标DPI正确",
            declared_contract_ok,
            expected="PDF pages=1; PNG target dpi>=600",
            actual={
                "artifact_type": artifact_type,
                "expected_pdf_pages": row.get("expected_pdf_pages"),
                "expected_png_dpi": row.get("expected_png_dpi"),
            },
            object_id=object_id,
            version=version,
            artifact=artifact_type,
            path=path,
        )
        if path in validated_paths:
            continue
        validated_paths.add(path)
        if artifact_type == "pdf":
            validate_pdf(path, object_id, version, tools)
        elif artifact_type == "png":
            validate_png(path, object_id, version)


def find_group(
    groups: dict[GroupKey, dict[str, Any]],
    *,
    version: str,
    panel: str,
    dataset: str,
    floor: str,
    method: str,
    start: float,
    end: float,
) -> dict[str, Any] | None:
    for key, value in groups.items():
        (
            key_version,
            key_panel,
            key_dataset,
            _source_mat,
            _source_column,
            key_floor,
            key_method,
            key_start,
            key_end,
        ) = key
        if (
            key_version == version
            and key_panel == panel
            and key_dataset == dataset
            and key_floor == floor
            and key_method == method
            and float_close(key_start, start, atol=1.0e-14)
            and float_close(key_end, end, atol=1.0e-14)
        ):
            return value
    return None


def validate_f3_15_independently(
    retained_groups: dict[str, dict[GroupKey, dict[str, Any]]]
) -> None:
    if np is None:
        record(
            "f3_15",
            "图3-15历史与修正版可独立复核",
            False,
            expected="numpy available",
            actual="numpy missing",
            object_id="F3-15",
        )
        return
    f310 = retained_groups.get("F3-10", {})
    f315 = retained_groups.get("F3-15", {})
    historical_all_pass = True
    for panel, start, end in WINDOWS["earthquake"][1:]:
        for method in PLOTTING_METHOD_ORDER:
            left = find_group(
                f315,
                version="paper_historical_composite",
                panel=panel,
                dataset="division2_elcentro",
                floor="Floor 3",
                method=method,
                start=start,
                end=end,
            )
            right = find_group(
                f310,
                version="standard",
                panel=panel,
                dataset="division2_elcentro",
                floor="Floor 3",
                method=method,
                start=start,
                end=end,
            )
            if left is None or right is None:
                passed = False
                actual: Any = "missing compared group"
            else:
                same_time = np.array_equal(left["times"], right["times"])
                same_values = np.array_equal(left["values"], right["values"])
                passed = bool(same_time and same_values)
                actual = {
                    "left_samples": int(len(left["times"])),
                    "right_samples": int(len(right["times"])),
                    "time_array_equal": bool(same_time),
                    "value_array_equal": bool(same_values),
                    "max_time_abs_diff_s": (
                        float(np.max(np.abs(left["times"] - right["times"])))
                        if len(left["times"]) == len(right["times"])
                        else math.inf
                    ),
                    "max_value_abs_diff_mm": (
                        float(np.max(np.abs(left["values"] - right["values"])))
                        if len(left["values"]) == len(right["values"])
                        else math.inf
                    ),
                }
            historical_all_pass = historical_all_pass and passed
            record(
                "f3_15",
                "历史版局部窗与图3-10第二类ElCentro三层逐点完全相等",
                passed,
                expected={
                    "source": "F3-10/division2_elcentro/Floor 3",
                    "panel": panel,
                    "method": method,
                    "window": [start, end],
                    "time_array_equal": True,
                    "value_array_equal": True,
                },
                actual=actual,
                object_id="F3-15",
                version="paper_historical_composite",
                artifact=panel,
            )
    STATS["f3_15_historical_pointwise_equal"] = historical_all_pass

    corrected_all_pass = True
    for panel, start, end in WINDOWS["chirp"]:
        for method in PLOTTING_METHOD_ORDER:
            group = find_group(
                f315,
                version="physically_consistent_corrected",
                panel=panel,
                dataset="division2_chirp",
                floor="Floor 3",
                method=method,
                start=start,
                end=end,
            )
            passed = group is not None
            corrected_all_pass = corrected_all_pass and passed
            record(
                "f3_15",
                "修正版面板来自第二类Chirp三层响应",
                passed,
                expected={
                    "source_dataset": "division2_chirp",
                    "floor": "Floor 3",
                    "panel": panel,
                    "method": method,
                    "window": [start, end],
                },
                actual="MATCH" if passed else "MISSING_OR_WRONG_SOURCE",
                object_id="F3-15",
                version="physically_consistent_corrected",
                artifact=panel,
            )
    STATS["f3_15_corrected_from_division2_chirp"] = corrected_all_pass


def validate_generation_summary() -> None:
    path = CANDIDATE_ROOT / "generation_summary.json"
    if not path.is_file():
        record(
            "generation_summary",
            "generation_summary.json存在",
            False,
            expected=str(path),
            actual="MISSING",
            path=path,
        )
        return
    try:
        summary = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        record(
            "generation_summary",
            "generation_summary.json可解析",
            False,
            expected="valid JSON",
            actual=f"{type(exc).__name__}: {exc}",
            path=path,
        )
        return
    required_ok = isinstance(summary, dict) and GENERATION_SUMMARY_REQUIRED_KEYS.issubset(summary)
    record(
        "generation_summary",
        "生成摘要包含冻结键",
        required_ok,
        expected=sorted(GENERATION_SUMMARY_REQUIRED_KEYS),
        actual=sorted(summary) if isinstance(summary, dict) else type(summary).__name__,
        path=path,
    )
    if not isinstance(summary, dict):
        return
    counts_ok = (
        summary.get("status") == "PASS"
        and summary.get("object_count") == 11
        and summary.get("figure_pair_count") == 12
        and summary.get("pdf_count") == 12
        and summary.get("png_count") == 12
    )
    record(
        "generation_summary",
        "生成摘要状态与数量一致",
        counts_ok,
        expected={
            "status": "PASS",
            "object_count": 11,
            "figure_pair_count": 12,
            "pdf_count": 12,
            "png_count": 12,
        },
        actual={
            key: summary.get(key)
            for key in ("status", "object_count", "figure_pair_count", "pdf_count", "png_count")
        },
        path=path,
    )
    manifest_path = CANDIDATE_ROOT / "artifact_manifest.csv"
    actual_hash = sha256_file(manifest_path) if manifest_path.is_file() else None
    record(
        "generation_summary",
        "生成摘要中的清单SHA-256匹配",
        actual_hash is not None and summary.get("manifest_sha256", "").upper() == actual_hash,
        expected=actual_hash,
        actual=summary.get("manifest_sha256"),
        path=path,
    )


def validate_objects(
    object_dirs: dict[str, Path],
    figure_contract: dict[str, dict[str, str]],
    raw_datasets: dict[str, dict[str, Any]],
) -> dict[str, dict[GroupKey, dict[str, Any]]]:
    retained: dict[str, dict[GroupKey, dict[str, Any]]] = {}
    seen_contract_object_ids: list[str] = []
    seen_contract_numbers: list[str] = []
    for object_id in EXPECTED_OBJECT_IDS:
        directory = object_dirs.get(object_id)
        contract_row = figure_contract.get(object_id)
        if directory is None or contract_row is None:
            record(
                "object_structure",
                "对象目录和总合同均存在",
                False,
                expected={"directory": True, "figure_contract_row": True},
                actual={"directory": directory is not None, "figure_contract_row": contract_row is not None},
                object_id=object_id,
                path=directory or CANDIDATE_ROOT,
            )
            continue
        object_name = contract_row["图名"]
        expected_directory = f"{object_id}_{object_name}"
        record(
            "object_structure",
            "对象目录名等于对象ID加中文图名",
            directory.name == expected_directory,
            expected=expected_directory,
            actual=directory.name,
            object_id=object_id,
            path=directory,
        )
        figures_dir = directory / "figures"
        data_path = directory / "data" / "figure_plot_data.csv"
        metrics_path = directory / "metrics.csv"
        contract_path = directory / "contract.json"
        required_ok = figures_dir.is_dir() and data_path.is_file() and metrics_path.is_file() and contract_path.is_file()
        record(
            "object_structure",
            "对象固定目录与三个审计文件存在",
            required_ok,
            expected={
                "figures_dir": True,
                "figure_plot_data.csv": True,
                "metrics.csv": True,
                "contract.json": True,
            },
            actual={
                "figures_dir": figures_dir.is_dir(),
                "figure_plot_data.csv": data_path.is_file(),
                "metrics.csv": metrics_path.is_file(),
                "contract.json": contract_path.is_file(),
            },
            object_id=object_id,
            path=directory,
        )
        version_specs = expected_versions(object_id, directory.name)
        contract = validate_contract_json(
            contract_path,
            object_id,
            object_name,
            directory.name,
            version_specs,
        )
        if contract is not None:
            seen_contract_object_ids.append(str(contract.get("object_id", "")))
            seen_contract_numbers.append(str(contract.get("figure_number", "")))
        groups = read_and_validate_plot_data(
            data_path,
            object_id,
            object_name,
            version_specs,
            raw_datasets,
        )
        validate_metrics(metrics_path, object_id, object_name, groups)
        if object_id in {"F3-10", "F3-15"}:
            retained[object_id] = groups
    record(
        "object_contract",
        "11份对象合同的对象ID全局唯一",
        len(seen_contract_object_ids) == 11
        and len(set(seen_contract_object_ids)) == 11
        and set(seen_contract_object_ids) == EXPECTED_OBJECT_SET,
        expected=EXPECTED_OBJECT_IDS,
        actual=seen_contract_object_ids,
        path=CANDIDATE_ROOT,
    )
    record(
        "object_contract",
        "11份对象合同的图号全局唯一",
        len(seen_contract_numbers) == 11 and len(set(seen_contract_numbers)) == 11,
        expected=11,
        actual={"count": len(seen_contract_numbers), "unique": len(set(seen_contract_numbers))},
        path=CANDIDATE_ROOT,
    )
    return retained


def write_reports(dependency_paths: dict[str, str | None]) -> int:
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    with DETAIL_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=DETAIL_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(DETAILS)
    failures = [row for row in DETAILS if row["status"] == "FAIL"]
    passes = [row for row in DETAILS if row["status"] == "PASS"]
    summary = {
        "schema_version": "board18.figure-validation.v1",
        "status": "PASS" if not failures else "FAIL",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "candidate_root": str(CANDIDATE_ROOT),
        "validation_root": str(VALIDATION_ROOT),
        "detail_csv": str(DETAIL_PATH),
        "detail_csv_sha256": sha256_file(DETAIL_PATH),
        "check_count": len(DETAILS),
        "pass_count": len(passes),
        "failure_count": len(failures),
        "object_count_expected": 11,
        "object_count_observed": STATS["object_count_observed"],
        "figure_pair_count_expected": 12,
        "figure_pair_count_observed": STATS["figure_pair_count_observed"],
        "pdf_count_expected": 12,
        "pdf_count_observed": STATS["pdf_count_observed"],
        "png_count_expected": 12,
        "png_count_observed": STATS["png_count_observed"],
        "manifest_row_count_expected": 24,
        "manifest_row_count_observed": STATS["manifest_row_count_observed"],
        "f3_15_historical_pointwise_equal": STATS[
            "f3_15_historical_pointwise_equal"
        ],
        "f3_15_corrected_from_division2_chirp": STATS[
            "f3_15_corrected_from_division2_chirp"
        ],
        "subjective_visual_review": "NOT_PERFORMED_BY_DESIGN",
        "dependencies": {
            "executables": dependency_paths,
            "python_import_errors": IMPORT_ERRORS,
        },
        "failure_check_ids": [row["check_id"] for row in failures],
    }
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if not failures else 1


def main() -> int:
    dependency_paths: dict[str, str | None] = {}
    try:
        dependency_paths = validate_dependencies()
        figure_contract = validate_figure_contract()
        object_dirs = discover_object_directories()
        raw_datasets = load_raw_datasets()
        retained_groups = validate_objects(object_dirs, figure_contract, raw_datasets)
        validate_f3_15_independently(retained_groups)
        validate_manifest_and_artifacts(object_dirs, figure_contract, dependency_paths)
        validate_generation_summary()
    except Exception as exc:  # preserve a machine-readable FAIL even for unforeseen errors
        record(
            "internal",
            "验证器未发生未捕获异常",
            False,
            expected="no exception",
            actual=f"{type(exc).__name__}: {exc}",
            detail=traceback.format_exc(),
            path=SCRIPT_PATH,
        )
    return write_reports(dependency_paths)


if __name__ == "__main__":
    raise SystemExit(main())

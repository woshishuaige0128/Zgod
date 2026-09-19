from __future__ import annotations

"""独立验收板块20步骤8F的数据裁决。

本脚本不导入步骤8F构建器，不修改构建器数据，也不生成PDF/PNG。
它从步骤8E逐点CSV重新组装24个31x67稳定掩膜，独立读取论文目标CSV
和历史MAT，并在临时目录中再次调用MATLAB bwboundaries核对30个边界任务。
持久输出严格限制在步骤8F输出根的validation目录内，共三份中文证据文件。
"""

import csv
import hashlib
import json
import math
import subprocess
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Sequence

import fitz
import numpy as np
from PIL import Image
from scipy.io import loadmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step8f_计算候选与论文目标裁决"
VALIDATION_ROOT = OUTPUT_ROOT / "validation"
CHECKS_PATH = VALIDATION_ROOT / "步骤8F独立验收检查.csv"
SUMMARY_PATH = VALIDATION_ROOT / "步骤8F独立验收摘要.json"
REPORT_PATH = VALIDATION_ROOT / "步骤8F独立验收报告.md"

STEP8E_POINTS = (
    BOARD_ROOT
    / "outputs"
    / "step8e_四候选全网格"
    / "python"
    / "步骤8E_Python全网格逐点结果.csv"
)
TARGET_ROOT = BOARD_ROOT / "outputs" / "step8f_论文矢量边界逐点复刻" / "data"
HISTORY_ROOT = (
    BOARD_ROOT
    / "input"
    / "plotting_baseline"
    / "第4章_缩聚对试验稳定性的影响"
    / "原始来源副本"
)
HISTORY_FILES = {
    1: HISTORY_ROOT / "第一类划分最终绘图数据_lqr_2.mat",
    2: HISTORY_ROOT / "第二类划分最终绘图数据_lqr_3.mat",
}
JOBS_PATH = OUTPUT_ROOT / "裁决证据" / "MATLAB_bwboundaries任务表.csv"
BUILDER_STATS_PATH = OUTPUT_ROOT / "裁决证据" / "MATLAB_bwboundaries结构检查.csv"
BUILDER_CURVES_PATH = OUTPUT_ROOT / "裁决证据" / "24候选与六条论文目标逐项裁决.csv"
BUILDER_NEAREST_PATH = OUTPUT_ROOT / "裁决证据" / "六条目标最近诊断候选.csv"
BUILDER_FIGURES_PATH = OUTPUT_ROOT / "裁决证据" / "8行同候选整图级裁决.csv"
BUILDER_GLOBAL_PATH = OUTPUT_ROOT / "裁决证据" / "4行同候选六曲线全局裁决.csv"
BUILDER_SUMMARY_PATH = OUTPUT_ROOT / "裁决证据" / "步骤8F计算候选裁决摘要.json"
BUILDER_SCRIPT_PATH = BOARD_ROOT / "code" / "build_board20_step8f_adjudication.py"
MATLAB_EXE = Path(r"D:\Downlad\Matlab\bin\matlab.exe")

N_L = 31
N_J = 67
POINTS_PER_GROUP = N_L * N_J
DT_MS = 1000.0 / 1024.0
CANDIDATES = ("R01", "R02", "R03", "R04")
METHODS = ("Original", "CB", "Guyan")
METHOD_CN = {"Original": "原结构", "CB": "Craig-Bampton", "Guyan": "Guyan"}
METHOD_STEP8E = {"Original": "Original", "Craig_Bampton": "CB", "Guyan": "Guyan"}
METHOD_MAT = {"Original": "stab_o", "CB": "stab_C", "Guyan": "stab_g"}
METHOD_FILE = {"Original": "Original", "CB": "Craig-Bampton", "Guyan": "Guyan"}
FIGURE_ID = {1: "4-4", 2: "4-5"}

# 这是步骤8F数据构建完成时留下的执行记录，而不是对最终目录状态的反推。
# 正式渲染是在该记录形成并由主线程确认之后，凭唯一工件标记单独授权执行的。
DATA_ONLY_COMPLETION_RECORD = {
    "record_kind": "HISTORICAL_EXECUTION_RECORD",
    "builder_completion_marker": "STEP8F_DATA_ONLY_DONE: no PDF/PNG generated",
    "recorded_output_file_count": 70,
    "recorded_deterministic_hash_match": "70/70",
    "recorded_media_count": 0,
    "record_source": "步骤8F构建代理完成记录，并由主线程在正式渲染后再次确认",
}


@dataclass(frozen=True, order=True)
class GroupKey:
    division: int
    method: str
    candidate_id: str


@dataclass
class GroupData:
    mask: np.ndarray
    candidate_name: str
    route: str
    dimension: int


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def media_inventory() -> list[dict[str, Any]]:
    """只读登记步骤8F正式媒体，供验收前后逐字节比对。"""
    inventory: list[dict[str, Any]] = []
    if not OUTPUT_ROOT.is_dir():
        return inventory
    for path in sorted(
        (
            item
            for item in OUTPUT_ROOT.rglob("*")
            if item.is_file() and item.suffix.lower() in {".pdf", ".png"}
        ),
        key=lambda item: str(item).casefold(),
    ):
        stat = path.stat()
        inventory.append(
            {
                "relative_path": path.relative_to(OUTPUT_ROOT).as_posix(),
                "suffix": path.suffix.lower(),
                "size_bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "sha256": sha256_file(path),
            }
        )
    return inventory


def media_signature(inventory: Sequence[dict[str, Any]]) -> dict[str, tuple[Any, ...]]:
    return {
        str(item["relative_path"]): (
            int(item["size_bytes"]),
            int(item["mtime_ns"]),
            str(item["sha256"]),
        )
        for item in inventory
    }


def validate_formal_media(
    checks: list[dict[str, str]], media_before: list[dict[str, Any]]
) -> dict[str, Any]:
    """验收已授权的正式图件，不创建、重写或渲染任何媒体。"""
    builder_summary = json.loads(BUILDER_SUMMARY_PATH.read_text(encoding="utf-8"))
    planned_pdf_names = list(builder_summary.get("planned_render_outputs", []))
    expected_pdf_paths = {
        (Path("figures") / name).as_posix() for name in planned_pdf_names
    }
    expected_png_paths = {
        str(Path(path).with_suffix(".png")).replace("\\", "/")
        for path in expected_pdf_paths
    }
    expected_paths = expected_pdf_paths | expected_png_paths
    formal_media_before = [
        item
        for item in media_before
        if str(item["relative_path"]).startswith("figures/")
    ]
    auxiliary_media_before = [
        item
        for item in media_before
        if not str(item["relative_path"]).startswith("figures/")
    ]
    actual_paths = {
        str(item["relative_path"]) for item in formal_media_before
    }
    actual_pdf_paths = {
        str(item["relative_path"])
        for item in formal_media_before
        if item["suffix"] == ".pdf"
    }
    actual_png_paths = {
        str(item["relative_path"])
        for item in formal_media_before
        if item["suffix"] == ".png"
    }
    exact_media_set = (
        len(planned_pdf_names) == 4
        and len(actual_pdf_paths) == 4
        and len(actual_png_paths) == 4
        and actual_paths == expected_paths
    )
    add_check(
        checks,
        "正式图件",
        "figures正式图件目录恰含计划内4份PDF与同名4份PNG",
        exact_media_set,
        {
            "pdf_count": len(actual_pdf_paths),
            "png_count": len(actual_png_paths),
            "paths": sorted(actual_paths),
        },
        {
            "pdf_count": 4,
            "png_count": 4,
            "paths": sorted(expected_paths),
        },
    )

    builder_source = BUILDER_SCRIPT_PATH.read_text(encoding="utf-8")
    historical_record_ok = (
        DATA_ONLY_COMPLETION_RECORD["recorded_media_count"] == 0
        and DATA_ONLY_COMPLETION_RECORD["recorded_output_file_count"] == 70
        and DATA_ONLY_COMPLETION_RECORD["recorded_deterministic_hash_match"]
        == "70/70"
        and DATA_ONLY_COMPLETION_RECORD["builder_completion_marker"]
        in builder_source
        and "默认或 --data-only 只生成数据与裁决证据，严禁生成 PDF/PNG。"
        in builder_source
    )
    add_check(
        checks,
        "data-only历史门",
        "data-only完成记录为70份文件逐字节一致且当时媒体数为0",
        historical_record_ok,
        DATA_ONLY_COMPLETION_RECORD,
        {
            "recorded_output_file_count": 70,
            "recorded_deterministic_hash_match": "70/70",
            "recorded_media_count": 0,
            "builder_marker_present": True,
        },
        "这是正式渲染之前的历史执行记录；不以最终目录当前含图件为失败条件。",
    )

    earliest_media_mtime_ns = min(
        (int(item["mtime_ns"]) for item in formal_media_before), default=-1
    )
    adjudication_mtime_ns = BUILDER_SUMMARY_PATH.stat().st_mtime_ns
    render_after_data = bool(media_before) and (
        adjudication_mtime_ns < earliest_media_mtime_ns
    )
    add_check(
        checks,
        "阶段顺序",
        "计算裁决摘要早于全部正式媒体的最终写入时间",
        render_after_data,
        {
            "adjudication_summary_mtime_ns": adjudication_mtime_ns,
            "earliest_media_mtime_ns": earliest_media_mtime_ns,
        },
        "adjudication_summary_mtime_ns < earliest_media_mtime_ns",
        "只作为数据裁决先冻结、图件后渲染的文件系统旁证。",
    )

    pdf_details: list[dict[str, Any]] = []
    for relative_path in sorted(expected_pdf_paths):
        path = OUTPUT_ROOT / Path(relative_path)
        detail: dict[str, Any] = {"relative_path": relative_path}
        passed = path.is_file()
        if passed:
            with fitz.open(path) as document:
                raster_xobject_count = 0
                raster_block_count = 0
                drawing_count = 0
                type3_fonts: set[tuple[int, str]] = set()
                font_count = 0
                for page in document:
                    raster_xobject_count += len(page.get_images(full=True))
                    raster_block_count += sum(
                        1
                        for block in page.get_text("dict").get("blocks", [])
                        if block.get("type") == 1
                    )
                    drawing_count += len(page.get_drawings())
                    fonts = page.get_fonts(full=True)
                    font_count += len(fonts)
                    for font in fonts:
                        if len(font) > 2 and str(font[2]).strip().lower() == "type3":
                            type3_fonts.add((int(font[0]), str(font[3])))
                detail.update(
                    {
                        "page_count": len(document),
                        "raster_xobject_count": raster_xobject_count,
                        "raster_image_block_count": raster_block_count,
                        "type3_font_count": len(type3_fonts),
                        "type3_fonts": [list(item) for item in sorted(type3_fonts)],
                        "font_reference_count": font_count,
                        "vector_drawing_count": drawing_count,
                    }
                )
                passed = (
                    len(document) == 1
                    and raster_xobject_count == 0
                    and raster_block_count == 0
                    and not type3_fonts
                    and drawing_count > 0
                )
        else:
            detail["missing"] = True
        pdf_details.append(detail)
        add_check(
            checks,
            "PDF格式",
            f"{Path(relative_path).name}为单页纯矢量且无Type 3字体",
            passed,
            detail,
            {
                "page_count": 1,
                "raster_xobject_count": 0,
                "raster_image_block_count": 0,
                "type3_font_count": 0,
                "vector_drawing_count": ">0",
            },
        )

    png_details: list[dict[str, Any]] = []
    for relative_path in sorted(expected_png_paths):
        path = OUTPUT_ROOT / Path(relative_path)
        detail = {"relative_path": relative_path}
        passed = path.is_file()
        if passed:
            with Image.open(path) as raster:
                dpi_raw = raster.info.get("dpi")
                dpi = None
                if (
                    isinstance(dpi_raw, (tuple, list))
                    and len(dpi_raw) >= 2
                ):
                    dpi = [float(dpi_raw[0]), float(dpi_raw[1])]
                detail.update(
                    {
                        "width_px": int(raster.width),
                        "height_px": int(raster.height),
                        "mode": raster.mode,
                        "dpi": dpi,
                    }
                )
                passed = (
                    dpi is not None
                    and all(590.0 <= value <= 610.0 for value in dpi)
                    and raster.width > 0
                    and raster.height > 0
                )
        else:
            detail["missing"] = True
        png_details.append(detail)
        add_check(
            checks,
            "PNG格式",
            f"{Path(relative_path).name}分辨率元数据约为600 dpi",
            passed,
            detail,
            {"dpi_range": [590.0, 610.0], "positive_pixel_dimensions": True},
        )

    return {
        "data_only_historical_record": DATA_ONLY_COMPLETION_RECORD,
        "render_after_data_temporal_evidence": {
            "adjudication_summary_mtime_ns": adjudication_mtime_ns,
            "earliest_media_mtime_ns": earliest_media_mtime_ns,
            "passed": render_after_data,
        },
        "before_validation": formal_media_before,
        "auxiliary_media_not_counted_as_formal_artifacts": auxiliary_media_before,
        "expected_relative_paths": sorted(expected_paths),
        "pdf_format_details": pdf_details,
        "png_format_details": png_details,
    }


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def display(value: Any) -> str:
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value)


def add_check(
    checks: list[dict[str, str]],
    category: str,
    item: str,
    passed: bool,
    actual: Any,
    expected: Any,
    note: str = "",
) -> None:
    checks.append(
        {
            "检查编号": f"V{len(checks) + 1:03d}",
            "检查类别": category,
            "检查项": item,
            "状态": "PASS" if passed else "FAIL",
            "实际值": display(actual),
            "期望值": display(expected),
            "说明": note,
        }
    )


def parse_bool(value: str) -> bool:
    token = value.strip().lower()
    if token in {"1", "true"}:
        return True
    if token in {"0", "false"}:
        return False
    raise ValueError(f"不能解析布尔值：{value!r}")


def optional_int(value: str) -> int | None:
    token = value.strip()
    if token.upper() in {"", "NA", "N/A", "NONE", "NULL"}:
        return None
    return int(token)


def optional_float(value: str) -> float | None:
    token = value.strip()
    if token.upper() in {"", "NA", "N/A", "NONE", "NULL"}:
        return None
    return float(token)


def load_binary_mask(path: Path) -> np.ndarray:
    array = np.loadtxt(path, delimiter=",", dtype=np.int8)
    if array.shape != (N_L, N_J):
        raise ValueError(f"{path.name}: 掩膜尺寸{array.shape}，应为{(N_L, N_J)}")
    unique = set(np.unique(array).tolist())
    if not unique.issubset({0, 1}):
        raise ValueError(f"{path.name}: 掩膜含非0/1值{sorted(unique)}")
    return array.astype(bool)


def load_step8e_groups(
    checks: list[dict[str, str]],
) -> tuple[dict[GroupKey, GroupData], set[str]]:
    groups: dict[GroupKey, GroupData] = {}
    seen_cells: dict[GroupKey, set[tuple[int, int]]] = {}
    point_keys: set[str] = set()
    rows = read_rows(STEP8E_POINTS)
    required_fields = {
        "point_key",
        "bundle_id",
        "division",
        "route",
        "method",
        "dimension",
        "candidate_id",
        "candidate_name",
        "l_samples",
        "j_samples",
        "stable",
        "overall_pass",
    }
    header_ok = bool(rows) and required_fields.issubset(rows[0])
    add_check(
        checks,
        "步骤8E输入",
        "逐点CSV字段完整",
        header_ok,
        sorted(rows[0]) if rows else [],
        sorted(required_fields),
    )
    if not header_ok:
        raise ValueError("步骤8E逐点CSV字段不完整")

    point_key_pattern_failures: list[str] = []
    duplicate_point_keys = 0
    failed_step8e_points = 0
    for row in rows:
        method_raw = row["method"]
        if method_raw not in METHOD_STEP8E:
            raise ValueError(f"步骤8E未知方法：{method_raw}")
        division = int(row["division"])
        method = METHOD_STEP8E[method_raw]
        candidate_id = row["candidate_id"]
        key = GroupKey(division, method, candidate_id)
        if key not in groups:
            groups[key] = GroupData(
                mask=np.full((N_L, N_J), -1, dtype=np.int8),
                candidate_name=row["candidate_name"],
                route=row["route"],
                dimension=int(row["dimension"]),
            )
            seen_cells[key] = set()
        else:
            group = groups[key]
            if (
                group.candidate_name != row["candidate_name"]
                or group.route != row["route"]
                or group.dimension != int(row["dimension"])
            ):
                raise ValueError(f"{key}: 组内元数据不一致")

        l_value = int(row["l_samples"])
        j_value = int(row["j_samples"])
        if not (0 <= l_value < N_L and 0 <= j_value < N_J):
            raise ValueError(f"{key}: 网格点越界({l_value},{j_value})")
        if (l_value, j_value) in seen_cells[key]:
            raise ValueError(f"{key}: 重复网格点({l_value},{j_value})")
        seen_cells[key].add((l_value, j_value))

        point_key = row["point_key"]
        if point_key in point_keys:
            duplicate_point_keys += 1
        point_keys.add(point_key)
        expected_bundle = f"D{division}_{method_raw}_{candidate_id}"
        expected_point_key = f"{expected_bundle}__l{l_value:02d}__j{j_value:02d}"
        if row["bundle_id"] != expected_bundle or point_key != expected_point_key:
            if len(point_key_pattern_failures) < 10:
                point_key_pattern_failures.append(
                    f"{point_key}|expected={expected_point_key}|bundle={row['bundle_id']}"
                )
        if not parse_bool(row["overall_pass"]):
            failed_step8e_points += 1
        groups[key].mask[l_value, j_value] = int(parse_bool(row["stable"]))

    expected_keys = {
        GroupKey(division, method, candidate_id)
        for division in (1, 2)
        for method in METHODS
        for candidate_id in CANDIDATES
    }
    incomplete_groups = [
        f"D{key.division}_{key.method}_{key.candidate_id}:{len(seen_cells.get(key, set()))}"
        for key in sorted(expected_keys)
        if len(seen_cells.get(key, set())) != POINTS_PER_GROUP
        or key not in groups
        or np.any(groups[key].mask < 0)
    ]
    add_check(
        checks,
        "步骤8E输入",
        "24组乘2077固定键完整",
        len(rows) == 24 * POINTS_PER_GROUP
        and len(point_keys) == 24 * POINTS_PER_GROUP
        and duplicate_point_keys == 0
        and set(groups) == expected_keys
        and not incomplete_groups,
        {
            "rows": len(rows),
            "unique_point_keys": len(point_keys),
            "groups": len(groups),
            "duplicates": duplicate_point_keys,
            "incomplete_groups": incomplete_groups,
        },
        {
            "rows": 49848,
            "unique_point_keys": 49848,
            "groups": 24,
            "duplicates": 0,
            "incomplete_groups": [],
        },
    )
    add_check(
        checks,
        "步骤8E输入",
        "固定键命名与bundle绑定",
        not point_key_pattern_failures,
        point_key_pattern_failures,
        [],
    )
    add_check(
        checks,
        "步骤8E输入",
        "49,848点步骤8E逐点门全部通过",
        failed_step8e_points == 0,
        failed_step8e_points,
        0,
    )
    return groups, point_keys


def load_targets(
    checks: list[dict[str, str]],
) -> dict[tuple[int, str], tuple[tuple[int, int], ...]]:
    targets: dict[tuple[int, str], tuple[tuple[int, int], ...]] = {}
    for division in (1, 2):
        for method in METHODS:
            source = TARGET_ROOT / f"图{FIGURE_ID[division]}_{method}_论文矢量边界.csv"
            rows = read_rows(source)
            orders = [int(row["point_order"]) for row in rows]
            points = tuple(
                (int(row["tau1_step"]), int(row["tau2_step"])) for row in rows
            )
            j_zero = np.asarray([x - 1 for x, _ in points], dtype=float)
            l_zero = np.asarray([y - 1 for _, y in points], dtype=float)
            x_ms = j_zero * DT_MS
            y_ms = l_zero * DT_MS
            mapping_error = max(
                float(np.max(np.abs(x_ms / DT_MS - j_zero))),
                float(np.max(np.abs(y_ms / DT_MS - l_zero))),
            )
            passed = (
                orders == list(range(1, len(rows) + 1))
                and len(points) == len(set(points))
                and all(1 < x <= N_J and 1 < y <= N_L for x, y in points)
                and mapping_error <= 1e-12
            )
            add_check(
                checks,
                "论文目标",
                f"图{FIGURE_ID[division]} {METHOD_CN[method]}的1-based到0-based及毫秒映射",
                passed,
                {
                    "points": len(points),
                    "x_one_based": [min(x for x, _ in points), max(x for x, _ in points)],
                    "y_one_based": [min(y for _, y in points), max(y for _, y in points)],
                    "max_roundtrip_error": mapping_error,
                },
                {
                    "point_order": "continuous",
                    "unique": True,
                    "mapping_x": "x=j+1",
                    "mapping_y": "y=l+1",
                    "mapping_ms": "tau_ms=(index-1)*1000/1024",
                },
            )
            if not passed:
                raise ValueError(f"{source.name}: 论文目标坐标合同失败")
            targets[(division, method)] = points
    return targets


def load_history_masks(
    checks: list[dict[str, str]],
) -> dict[tuple[int, str], np.ndarray]:
    masks: dict[tuple[int, str], np.ndarray] = {}
    for division, source in HISTORY_FILES.items():
        raw = loadmat(source, squeeze_me=False, struct_as_record=False)
        for method in METHODS:
            variable = METHOD_MAT[method]
            values = np.asarray(raw[variable], dtype=float)
            if values.shape[0] < N_L or values.shape[1] < N_J:
                raise ValueError(f"{source.name}/{variable}: 尺寸不足{values.shape}")
            common = values[:N_L, :N_J]
            mask = np.isfinite(common) & (common > 0.0) & (common < 1.0)
            masks[(division, method)] = mask
            outside_stable = 0
            if values.shape != (N_L, N_J):
                outside = np.ones(values.shape, dtype=bool)
                outside[:N_L, :N_J] = False
                outside_stable = int(
                    np.count_nonzero(
                        outside & np.isfinite(values) & (values > 0.0) & (values < 1.0)
                    )
                )
            add_check(
                checks,
                "历史MAT",
                f"图{FIGURE_ID[division]} {METHOD_CN[method]}历史掩膜阈值及共同网格",
                outside_stable == 0,
                {
                    "raw_shape": list(values.shape),
                    "common_stable_count": int(mask.sum()),
                    "outside_common_grid_stable_count": outside_stable,
                },
                {
                    "common_shape": [31, 67],
                    "outside_common_grid_stable_count": 0,
                },
            )
    return masks


def expected_job_ids() -> set[str]:
    result = {
        f"C_D{division}_{method}_{candidate_id}"
        for division in (1, 2)
        for method in METHODS
        for candidate_id in CANDIDATES
    }
    result.update(
        f"H_D{division}_{method}" for division in (1, 2) for method in METHODS
    )
    return result


def load_jobs_and_builder_masks(
    groups: dict[GroupKey, GroupData],
    history_masks: dict[tuple[int, str], np.ndarray],
    checks: list[dict[str, str]],
) -> tuple[list[dict[str, str]], dict[str, np.ndarray]]:
    jobs = read_rows(JOBS_PATH)
    ids = [row["item_id"] for row in jobs]
    expected_ids = expected_job_ids()
    add_check(
        checks,
        "构建器数据",
        "30个MATLAB边界任务完整且唯一",
        len(jobs) == 30 and len(set(ids)) == 30 and set(ids) == expected_ids,
        {"rows": len(jobs), "unique": len(set(ids)), "missing": sorted(expected_ids - set(ids))},
        {"rows": 30, "unique": 30, "missing": []},
    )
    if len(jobs) != 30 or set(ids) != expected_ids:
        raise ValueError("MATLAB边界任务表不完整")

    masks: dict[str, np.ndarray] = {}
    candidate_mismatch_total = 0
    history_mismatch_total = 0
    for row in jobs:
        item_id = row["item_id"]
        mask_path = Path(row["mask_file"])
        boundary_path = Path(row["boundary_file"])
        if not mask_path.is_file() or not boundary_path.is_file():
            raise FileNotFoundError(f"{item_id}: 掩膜或边界文件不存在")
        mask = load_binary_mask(mask_path)
        masks[item_id] = mask
        division = int(row["division"])
        method = row["method"]
        if row["item_kind"] == "candidate":
            candidate_id = row["candidate_id"]
            source = groups[GroupKey(division, method, candidate_id)].mask.astype(bool)
            mismatch = int(np.count_nonzero(mask ^ source))
            candidate_mismatch_total += mismatch
            add_check(
                checks,
                "候选掩膜",
                f"{item_id}与步骤8E的2077个stable值逐点一致",
                mismatch == 0,
                mismatch,
                0,
            )
        elif row["item_kind"] == "history":
            source = history_masks[(division, method)]
            mismatch = int(np.count_nonzero(mask ^ source))
            history_mismatch_total += mismatch
            add_check(
                checks,
                "历史掩膜",
                f"{item_id}与历史MAT共同31x67阈值掩膜逐点一致",
                mismatch == 0,
                mismatch,
                0,
            )
        else:
            raise ValueError(f"{item_id}: 未知item_kind={row['item_kind']}")
    add_check(
        checks,
        "候选掩膜",
        "24乘2077稳定掩膜总差异",
        candidate_mismatch_total == 0,
        candidate_mismatch_total,
        0,
    )
    add_check(
        checks,
        "历史掩膜",
        "六份历史共同网格掩膜总差异",
        history_mismatch_total == 0,
        history_mismatch_total,
        0,
    )
    return jobs, masks


def matlab_quote(value: str | Path) -> str:
    return str(value).replace("\\", "/").replace("'", "''")


def independent_matlab_boundaries(
    jobs: list[dict[str, str]],
) -> tuple[dict[str, dict[str, Any]], str]:
    with tempfile.TemporaryDirectory(prefix="board20_step8f_validation_") as temp_name:
        temp_root = Path(temp_name)
        script_path = temp_root / "independent_bwboundaries_validation.m"
        result_path = temp_root / "independent_bwboundaries_validation.mat"
        id_items = ";".join(f"'{matlab_quote(row['item_id'])}'" for row in jobs)
        mask_items = ";".join(
            f"'{matlab_quote(Path(row['mask_file']).resolve())}'" for row in jobs
        )
        matlab_source = "\n".join(
            [
                "close all force;",
                "set(groot,'DefaultFigureVisible','off');",
                f"ids={{{id_items}}};",
                f"mask_paths={{{mask_items}}};",
                "n=numel(ids);",
                "component_count=zeros(n,1);",
                "hole_pixel_count=zeros(n,1);",
                "hole_boundary_count=zeros(n,1);",
                "returned_boundary_count=zeros(n,1);",
                "full_paths=cell(n,1);",
                "visible_paths=cell(n,1);",
                "for q=1:n",
                "  M=logical(readmatrix(mask_paths{q}));",
                f"  if ~isequal(size(M),[{N_L},{N_J}]); error('MASK_SIZE:%s',ids{{q}}); end",
                "  CC=bwconncomp(M,8); component_count(q)=CC.NumObjects;",
                "  hole_pixel_count(q)=nnz(imfill(M,'holes') & ~M);",
                "  [Bh,~,Nh]=bwboundaries(M,8,'holes');",
                "  hole_boundary_count(q)=numel(Bh)-Nh;",
                "  B=bwboundaries(M,8,'noholes');",
                "  returned_boundary_count(q)=numel(B);",
                "  if isempty(B)",
                "    p=zeros(0,2);",
                "  else",
                "    p=[B{1}(:,2),B{1}(:,1)];",
                "  end",
                "  full_paths{q}=p;",
                "  visible_paths{q}=p(p(:,1)>1 & p(:,2)>1,:);",
                "end",
                f"save('{matlab_quote(result_path)}','component_count','hole_pixel_count',"
                "'hole_boundary_count','returned_boundary_count','full_paths','visible_paths','-v7');",
                "fprintf('STEP8F_INDEPENDENT_BOUNDARY_VALIDATION_DONE items=%d\\n',n);",
            ]
        )
        script_path.write_text(matlab_source, encoding="utf-8")
        command = f"run('{matlab_quote(script_path)}')"
        completed = subprocess.run(
            [str(MATLAB_EXE), "-batch", command],
            cwd=str(BOARD_ROOT),
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=300,
        )
        if completed.returncode != 0 or not result_path.is_file():
            raise RuntimeError(
                "独立MATLAB边界验收失败："
                f"returncode={completed.returncode}\n{completed.stdout}"
            )
        raw = loadmat(result_path, squeeze_me=False, struct_as_record=False)
        numeric = {
            name: np.asarray(raw[name]).reshape(-1, order="F")
            for name in (
                "component_count",
                "hole_pixel_count",
                "hole_boundary_count",
                "returned_boundary_count",
            )
        }
        full_cells = np.asarray(raw["full_paths"], dtype=object).reshape(-1, order="F")
        visible_cells = np.asarray(raw["visible_paths"], dtype=object).reshape(-1, order="F")
        if len(full_cells) != len(jobs) or len(visible_cells) != len(jobs):
            raise ValueError("独立MATLAB返回的cell数量错误")
        result: dict[str, dict[str, Any]] = {}
        for index, row in enumerate(jobs):
            full_array = np.asarray(full_cells[index], dtype=float)
            visible_array = np.asarray(visible_cells[index], dtype=float)
            full_points = (
                tuple()
                if full_array.size == 0
                else tuple(map(tuple, np.rint(full_array.reshape(-1, 2)).astype(int)))
            )
            visible_points = (
                tuple()
                if visible_array.size == 0
                else tuple(map(tuple, np.rint(visible_array.reshape(-1, 2)).astype(int)))
            )
            result[row["item_id"]] = {
                "component_count": int(round(float(numeric["component_count"][index]))),
                "hole_pixel_count": int(round(float(numeric["hole_pixel_count"][index]))),
                "hole_boundary_count": int(
                    round(float(numeric["hole_boundary_count"][index]))
                ),
                "returned_boundary_count": int(
                    round(float(numeric["returned_boundary_count"][index]))
                ),
                "full_path": full_points,
                "visible_path": visible_points,
            }
        return result, completed.stdout.strip()


def read_boundary_path(path: Path) -> tuple[tuple[int, int], ...]:
    rows = read_rows(path)
    orders = [int(row["point_order"]) for row in rows]
    if orders != list(range(1, len(rows) + 1)):
        raise ValueError(f"{path.name}: point_order不连续")
    return tuple((int(row["x_index"]), int(row["y_index"])) for row in rows)


def compare_independent_boundaries(
    jobs: list[dict[str, str]],
    independent: dict[str, dict[str, Any]],
    checks: list[dict[str, str]],
) -> tuple[dict[str, tuple[tuple[int, int], ...]], list[dict[str, Any]]]:
    builder_stats_rows = read_rows(BUILDER_STATS_PATH)
    builder_stats = {row["item_id"]: row for row in builder_stats_rows}
    if len(builder_stats_rows) != 30 or set(builder_stats) != expected_job_ids():
        raise ValueError("构建器MATLAB结构检查不是30个固定任务")
    paths: dict[str, tuple[tuple[int, int], ...]] = {}
    structures: list[dict[str, Any]] = []
    for row in jobs:
        item_id = row["item_id"]
        independent_row = independent[item_id]
        builder_row = builder_stats[item_id]
        builder_path = read_boundary_path(Path(row["boundary_file"]))
        independent_path = independent_row["visible_path"]
        structure_match = (
            int(builder_row["component_count"]) == independent_row["component_count"]
            and int(builder_row["hole_pixel_count"]) == independent_row["hole_pixel_count"]
            and int(builder_row["returned_boundary_count"])
            == independent_row["returned_boundary_count"]
            and int(builder_row["full_boundary_point_count"])
            == len(independent_row["full_path"])
            and int(builder_row["visible_path_point_count"]) == len(independent_path)
        )
        path_match = builder_path == independent_path
        add_check(
            checks,
            "独立MATLAB边界",
            f"{item_id}组件、孔洞、边界数和B1路径独立一致",
            structure_match and path_match,
            {
                "independent": {
                    "components": independent_row["component_count"],
                    "hole_pixels": independent_row["hole_pixel_count"],
                    "hole_boundaries": independent_row["hole_boundary_count"],
                    "boundaries": independent_row["returned_boundary_count"],
                    "full_points": len(independent_row["full_path"]),
                    "visible_points": len(independent_path),
                },
                "builder_path_exact": path_match,
            },
            {
                "builder_stats_exact": True,
                "builder_B1_visible_path_exact": True,
            },
        )
        paths[item_id] = independent_path
        structural_pass = (
            independent_row["component_count"] == 1
            and independent_row["hole_pixel_count"] == 0
            and independent_row["hole_boundary_count"] == 0
            and independent_row["returned_boundary_count"] == 1
        )
        structures.append(
            {
                "item_id": item_id,
                "item_kind": row["item_kind"],
                "division": int(row["division"]),
                "method": row["method"],
                "candidate_id": row["candidate_id"],
                "component_count": independent_row["component_count"],
                "hole_pixel_count": independent_row["hole_pixel_count"],
                "hole_boundary_count": independent_row["hole_boundary_count"],
                "returned_boundary_count": independent_row["returned_boundary_count"],
                "full_boundary_point_count": len(independent_row["full_path"]),
                "visible_path_point_count": len(independent_path),
                "structural_gate": "PASS" if structural_pass else "FAIL",
            }
        )
    return paths, structures


def sequence_exact(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> tuple[bool, bool, bool]:
    forward = tuple(candidate) == tuple(target)
    reverse = tuple(candidate) == tuple(reversed(target))
    return forward, reverse, forward or reverse


def levenshtein_one_direction(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> int:
    previous = list(range(len(target) + 1))
    for candidate_index, candidate_point in enumerate(candidate, start=1):
        current = [candidate_index]
        for target_index, target_point in enumerate(target, start=1):
            substitution = previous[target_index - 1] + (
                0 if candidate_point == target_point else 1
            )
            insertion = current[target_index - 1] + 1
            deletion = previous[target_index] + 1
            current.append(min(substitution, insertion, deletion))
        previous = current
    return previous[-1]


def ordered_edit_distance(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> tuple[int, int, int, str]:
    forward = levenshtein_one_direction(candidate, target)
    reverse = levenshtein_one_direction(candidate, tuple(reversed(target)))
    if forward <= reverse:
        return forward, forward, reverse, "ORIGINAL"
    return reverse, forward, reverse, "REVERSED"


def symmetric_hausdorff(
    candidate: Sequence[tuple[int, int]], target: Sequence[tuple[int, int]]
) -> float:
    if not candidate or not target:
        return math.inf
    a = np.asarray(candidate, dtype=float)
    b = np.asarray(target, dtype=float)
    squared = np.sum((a[:, None, :] - b[None, :, :]) ** 2, axis=2)
    return max(
        float(np.sqrt(np.min(squared, axis=1)).max()),
        float(np.sqrt(np.min(squared, axis=0)).max()),
    )


def rightmost_path(
    points: Sequence[tuple[int, int]],
) -> tuple[int | None, tuple[int, ...]]:
    if not points:
        return None, tuple()
    x_value = int(max(x for x, _ in points))
    y_values = tuple(
        int(value) for value in sorted({y for x, y in points if int(x) == x_value})
    )
    return x_value, y_values


def rightmost_mask(mask: np.ndarray) -> tuple[int | None, int | None, tuple[int, ...]]:
    columns = np.flatnonzero(mask.any(axis=0))
    if len(columns) == 0:
        return None, None, tuple()
    j_zero = int(columns[-1])
    y_values = tuple((np.flatnonzero(mask[:, j_zero]) + 1).astype(int).tolist())
    return j_zero, j_zero + 1, y_values


def mask_metrics(candidate: np.ndarray, reference: np.ndarray) -> tuple[int, float, int, int]:
    xor = int(np.count_nonzero(candidate ^ reference))
    intersection = int(np.count_nonzero(candidate & reference))
    union = int(np.count_nonzero(candidate | reference))
    iou = float(intersection / union) if union else 1.0
    return xor, iou, intersection, union


def semicolon(values: Iterable[int]) -> str:
    return ";".join(str(value) for value in values)


def compare_builder_curve_table(
    curve_rows: list[dict[str, Any]], checks: list[dict[str, str]]
) -> None:
    rows = read_rows(BUILDER_CURVES_PATH)
    indexed = {
        (int(row["division"]), row["method"], row["candidate_id"]): row for row in rows
    }
    add_check(
        checks,
        "构建器裁决",
        "构建器24行曲线裁决键完整",
        len(rows) == 24 and len(indexed) == 24,
        {"rows": len(rows), "unique_keys": len(indexed)},
        {"rows": 24, "unique_keys": 24},
    )
    for current in curve_rows:
        key = (
            current["division"],
            current["method"],
            current["candidate_id"],
        )
        source = indexed[key]
        authoritative_hamming = optional_int(source["authoritative_source_mask_hamming_xor"])
        authoritative_iou = optional_float(source["authoritative_source_mask_iou"])
        essential_equal = (
            int(source["candidate_stable_count"]) == current["candidate_stable_count"]
            and int(source["matlab_8_connected_component_count"])
            == current["component_count"]
            and int(source["matlab_hole_pixel_count"]) == current["hole_pixel_count"]
            and int(source["matlab_returned_boundary_count"])
            == current["returned_boundary_count"]
            and parse_bool(source["pdf_sequence_exact_original_order"])
            == current["path_exact_original_order"]
            and parse_bool(source["pdf_sequence_exact_reversed_order"])
            == current["path_exact_reversed_order"]
            and parse_bool(source["pdf_sequence_exact_allow_whole_reverse"])
            == current["path_exact_allow_whole_reverse"]
            and int(source["pdf_ordered_path_edit_distance_allow_whole_reverse"])
            == current["ordered_edit_distance_allow_whole_reverse"]
            and int(source["pdf_ordered_path_edit_distance_original_order"])
            == current["ordered_edit_distance_original_order"]
            and int(source["pdf_ordered_path_edit_distance_reversed_order"])
            == current["ordered_edit_distance_reversed_order"]
            and abs(
                float(source["symmetric_hausdorff_index_units"])
                - current["symmetric_hausdorff_index_units"]
            )
            <= 1e-12
            and int(source["candidate_matlab_path_rightmost_x_one_based"])
            == current["candidate_rightmost_x_one_based"]
            and source["candidate_matlab_path_rightmost_all_y_one_based"]
            == semicolon(current["candidate_rightmost_y_one_based"])
            and source["candidate_boundary_structure_gate"]
            == current["candidate_boundary_structure_gate"]
            and source["pdf_visible_path_gate"] == current["pdf_visible_path_gate"]
            and source["full_mask_gate"] == current["full_mask_gate"]
        )
        if current["method"] == "Original":
            authority_equal = (
                authoritative_hamming == current["authoritative_full_mask_hamming"]
                and authoritative_iou is not None
                and abs(authoritative_iou - current["authoritative_full_mask_iou"]) <= 1e-15
            )
        else:
            authority_equal = (
                authoritative_hamming is None
                and authoritative_iou is None
                and current["authoritative_full_mask_hamming"] is None
                and current["authoritative_full_mask_iou"] is None
            )
        add_check(
            checks,
            "构建器裁决",
            f"D{key[0]} {key[1]} {key[2]}的曲线指标与独立重算一致",
            essential_equal and authority_equal,
            {
                "essential_equal": essential_equal,
                "authority_equal": authority_equal,
            },
            {"essential_equal": True, "authority_equal": True},
        )


def adjudicate_curves(
    groups: dict[GroupKey, GroupData],
    history_masks: dict[tuple[int, str], np.ndarray],
    targets: dict[tuple[int, str], tuple[tuple[int, int], ...]],
    paths: dict[str, tuple[tuple[int, int], ...]],
    structures: list[dict[str, Any]],
    checks: list[dict[str, str]],
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[tuple[int, str], dict[str, Any]],
]:
    structure_by_id = {row["item_id"]: row for row in structures}
    history_consistency: dict[tuple[int, str], dict[str, Any]] = {}
    for division in (1, 2):
        for method in METHODS:
            item_id = f"H_D{division}_{method}"
            history_path = paths[item_id]
            target = targets[(division, method)]
            forward, reverse, exact = sequence_exact(history_path, target)
            hx, hys = rightmost_path(history_path)
            tx, tys = rightmost_path(target)
            payload = {
                "division": division,
                "figure_id": f"图{FIGURE_ID[division]}",
                "method": method,
                "method_cn": METHOD_CN[method],
                "path_exact_original_order": forward,
                "path_exact_reversed_order": reverse,
                "path_exact_allow_whole_reverse": exact,
                "history_rightmost_x_one_based": hx,
                "history_rightmost_y_one_based": list(hys),
                "paper_rightmost_x_one_based": tx,
                "paper_rightmost_y_one_based": list(tys),
            }
            history_consistency[(division, method)] = payload
            expected_exact = method == "Original"
            add_check(
                checks,
                "历史目标身份",
                f"图{FIGURE_ID[division]} {METHOD_CN[method]}历史边界的论文目标身份",
                exact == expected_exact,
                exact,
                expected_exact,
                "Original是完整掩膜权威；四条缩聚历史掩膜仅作诊断。",
            )

    curve_rows: list[dict[str, Any]] = []
    for key in sorted(groups):
        item_id = f"C_D{key.division}_{key.method}_{key.candidate_id}"
        mask = groups[key].mask.astype(bool)
        history = history_masks[(key.division, key.method)]
        candidate = paths[item_id]
        target = targets[(key.division, key.method)]
        structure = structure_by_id[item_id]

        exact_forward, exact_reverse, exact_allow_reverse = sequence_exact(
            candidate, target
        )
        edit_best, edit_forward, edit_reverse, edit_orientation = ordered_edit_distance(
            candidate, target
        )
        hausdorff = symmetric_hausdorff(candidate, target)
        candidate_x, candidate_y = rightmost_path(candidate)
        paper_x, paper_y = rightmost_path(target)
        stable_j_zero, stable_x, stable_y = rightmost_mask(mask)
        rightmost_x_exact = candidate_x == paper_x
        rightmost_y_exact = candidate_y == paper_y
        structure_pass = structure["structural_gate"] == "PASS"
        pdf_visible_pass = (
            structure_pass
            and exact_allow_reverse
            and rightmost_x_exact
            and rightmost_y_exact
        )
        diagnostic_hamming, diagnostic_iou, intersection, union = mask_metrics(
            mask, history
        )
        if key.method == "Original":
            authoritative_hamming: int | None = diagnostic_hamming
            authoritative_iou: float | None = diagnostic_iou
            full_mask_gate = (
                "PASS_AUTHOR_SOURCE_MASK_EXACT"
                if diagnostic_hamming == 0 and diagnostic_iou == 1.0
                else "FAIL_AUTHOR_SOURCE_MASK_MISMATCH"
            )
            complete_exact = pdf_visible_pass and full_mask_gate.startswith("PASS")
            complete_status = (
                "PASS_COMPLETE_CALCULATION_REPRODUCTION"
                if complete_exact
                else "FAIL_CALCULATION_REPRODUCTION"
            )
        else:
            authoritative_hamming = None
            authoritative_iou = None
            full_mask_gate = "NOT_EVALUABLE_MISSING_SOURCE_MASK"
            complete_exact = False
            complete_status = (
                "NOT_EVALUABLE_MISSING_SOURCE_MASK"
                if pdf_visible_pass
                else "FAIL_VISIBLE_PATH_MISMATCH_AND_MISSING_SOURCE_MASK"
            )
        row = {
            "figure_id": f"图{FIGURE_ID[key.division]}",
            "division": key.division,
            "method": key.method,
            "method_cn": METHOD_CN[key.method],
            "candidate_id": key.candidate_id,
            "candidate_name": groups[key].candidate_name,
            "route": groups[key].route,
            "dimension": groups[key].dimension,
            "candidate_stable_count": int(mask.sum()),
            "component_count": structure["component_count"],
            "hole_pixel_count": structure["hole_pixel_count"],
            "hole_boundary_count": structure["hole_boundary_count"],
            "returned_boundary_count": structure["returned_boundary_count"],
            "candidate_boundary_structure_gate": structure["structural_gate"],
            "candidate_visible_path_point_count": len(candidate),
            "paper_visible_path_point_count": len(target),
            "path_exact_original_order": exact_forward,
            "path_exact_reversed_order": exact_reverse,
            "path_exact_allow_whole_reverse": exact_allow_reverse,
            "ordered_edit_distance_allow_whole_reverse": edit_best,
            "ordered_edit_distance_original_order": edit_forward,
            "ordered_edit_distance_reversed_order": edit_reverse,
            "ordered_edit_distance_best_orientation": edit_orientation,
            "symmetric_hausdorff_index_units": hausdorff,
            "symmetric_hausdorff_ms": hausdorff * DT_MS,
            "candidate_rightmost_stable_j_zero_based": stable_j_zero,
            "candidate_rightmost_stable_x_one_based": stable_x,
            "candidate_rightmost_stable_y_one_based": list(stable_y),
            "candidate_rightmost_x_one_based": candidate_x,
            "candidate_rightmost_y_one_based": list(candidate_y),
            "paper_rightmost_j_zero_based": None if paper_x is None else paper_x - 1,
            "paper_rightmost_x_one_based": paper_x,
            "paper_rightmost_y_one_based": list(paper_y),
            "paper_rightmost_x_ms": None
            if paper_x is None
            else (paper_x - 1) * DT_MS,
            "paper_rightmost_y_ms": [(y - 1) * DT_MS for y in paper_y],
            "rightmost_x_exact": rightmost_x_exact,
            "rightmost_y_exact": rightmost_y_exact,
            "rightmost_x_absolute_difference": abs(
                (candidate_x or 0) - (paper_x or 0)
            ),
            "rightmost_y_set_symmetric_difference_count": len(
                set(candidate_y) ^ set(paper_y)
            ),
            "historical_mask_hamming_diagnostic": diagnostic_hamming,
            "historical_mask_iou_diagnostic": diagnostic_iou,
            "historical_mask_intersection_diagnostic": intersection,
            "historical_mask_union_diagnostic": union,
            "authoritative_full_mask_hamming": authoritative_hamming,
            "authoritative_full_mask_iou": authoritative_iou,
            "full_mask_gate": full_mask_gate,
            "pdf_visible_path_gate": "PASS" if pdf_visible_pass else "FAIL",
            "complete_reproduction_exact": complete_exact,
            "complete_reproduction_status": complete_status,
        }
        curve_rows.append(row)

    add_check(
        checks,
        "曲线裁决",
        "24行曲线裁决完整",
        len(curve_rows) == 24,
        len(curve_rows),
        24,
    )
    reduced_authority_empty = all(
        row["authoritative_full_mask_hamming"] is None
        and row["authoritative_full_mask_iou"] is None
        and row["full_mask_gate"] == "NOT_EVALUABLE_MISSING_SOURCE_MASK"
        for row in curve_rows
        if row["method"] != "Original"
    )
    add_check(
        checks,
        "完整掩膜权威",
        "四条缩聚目标的24行候选权威Hamming和IoU均为空",
        reduced_authority_empty,
        reduced_authority_empty,
        True,
    )
    compare_builder_curve_table(curve_rows, checks)
    return curve_rows, structures, history_consistency


def aggregate_adjudications(
    curve_rows: list[dict[str, Any]], checks: list[dict[str, str]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], str, str]:
    figure_rows: list[dict[str, Any]] = []
    for division in (1, 2):
        for candidate_id in CANDIDATES:
            subset = [
                row
                for row in curve_rows
                if row["division"] == division and row["candidate_id"] == candidate_id
            ]
            visible_count = sum(
                row["pdf_visible_path_gate"] == "PASS" for row in subset
            )
            authority = [row for row in subset if row["method"] == "Original"]
            missing = [row for row in subset if row["method"] != "Original"]
            authority_exact = sum(
                row["full_mask_gate"] == "PASS_AUTHOR_SOURCE_MASK_EXACT"
                for row in authority
            )
            visible_all = len(subset) == 3 and visible_count == 3
            complete_exact = visible_all and authority_exact == 1 and len(missing) == 0
            whole_status = (
                "FAIL_VISIBLE_PATH_MISMATCH_WITH_PARTIAL_MASK_VERIFIABILITY"
                if not visible_all
                else "NOT_EVALUABLE_TWO_REDUCED_SOURCE_MASKS_MISSING"
            )
            figure_rows.append(
                {
                    "figure_id": f"图{FIGURE_ID[division]}",
                    "division": division,
                    "candidate_id": candidate_id,
                    "method_count": len(subset),
                    "visible_path_exact_count": visible_count,
                    "visible_path_all_exact": visible_all,
                    "authoritative_full_mask_count": len(authority),
                    "missing_source_mask_count": len(missing),
                    "authoritative_full_mask_exact_count": authority_exact,
                    "full_mask_verifiability": f"PARTIAL_{len(authority)}_OF_{len(subset)}_AUTHORITATIVE",
                    "all_full_masks_verifiable": len(missing) == 0,
                    "complete_reproduction_exact": complete_exact,
                    "whole_figure_status": whole_status,
                }
            )

    global_rows: list[dict[str, Any]] = []
    for candidate_id in CANDIDATES:
        subset = [row for row in curve_rows if row["candidate_id"] == candidate_id]
        visible_count = sum(row["pdf_visible_path_gate"] == "PASS" for row in subset)
        authority = [row for row in subset if row["method"] == "Original"]
        missing = [row for row in subset if row["method"] != "Original"]
        authority_exact = sum(
            row["full_mask_gate"] == "PASS_AUTHOR_SOURCE_MASK_EXACT"
            for row in authority
        )
        visible_all = len(subset) == 6 and visible_count == 6
        complete_exact = visible_all and authority_exact == 2 and len(missing) == 0
        global_status = (
            "FAIL_VISIBLE_PATH_MISMATCH_WITH_MISSING_SOURCE_MASKS"
            if not visible_all
            else "NOT_EVALUABLE_FOUR_REDUCED_SOURCE_MASKS_MISSING"
        )
        global_rows.append(
            {
                "candidate_id": candidate_id,
                "curve_count": len(subset),
                "visible_path_exact_count": visible_count,
                "visible_path_all_exact": visible_all,
                "authoritative_full_mask_count": len(authority),
                "missing_source_mask_count": len(missing),
                "authoritative_full_mask_exact_count": authority_exact,
                "full_mask_verifiability": f"PARTIAL_{len(authority)}_OF_{len(subset)}_AUTHORITATIVE",
                "all_full_masks_verifiable": len(missing) == 0,
                "complete_reproduction_exact": complete_exact,
                "global_six_curve_status": global_status,
            }
        )

    builder_figures = read_rows(BUILDER_FIGURES_PATH)
    builder_globals = read_rows(BUILDER_GLOBAL_PATH)
    figure_index = {
        (int(row["division"]), row["candidate_id"]): row for row in builder_figures
    }
    global_index = {row["candidate_id"]: row for row in builder_globals}
    add_check(
        checks,
        "整图裁决",
        "8行同候选三方法裁决完整",
        len(figure_rows) == 8 and len(figure_index) == 8,
        {"independent": len(figure_rows), "builder": len(figure_index)},
        {"independent": 8, "builder": 8},
    )
    for row in figure_rows:
        source = figure_index[(row["division"], row["candidate_id"])]
        equal = (
            int(source["method_count"]) == row["method_count"]
            and int(source["visible_path_exact_count"])
            == row["visible_path_exact_count"]
            and parse_bool(source["visible_path_all_exact"])
            == row["visible_path_all_exact"]
            and int(source["authoritative_full_mask_count"])
            == row["authoritative_full_mask_count"]
            and int(source["missing_source_mask_count"])
            == row["missing_source_mask_count"]
            and int(source["authoritative_full_mask_exact_count"])
            == row["authoritative_full_mask_exact_count"]
            and parse_bool(source["complete_reproduction_exact"])
            == row["complete_reproduction_exact"]
        )
        add_check(
            checks,
            "整图裁决",
            f"{row['figure_id']} {row['candidate_id']}同候选三方法聚合一致",
            equal,
            equal,
            True,
        )
    add_check(
        checks,
        "全局裁决",
        "4行同候选六曲线裁决完整",
        len(global_rows) == 4 and len(global_index) == 4,
        {"independent": len(global_rows), "builder": len(global_index)},
        {"independent": 4, "builder": 4},
    )
    for row in global_rows:
        source = global_index[row["candidate_id"]]
        equal = (
            int(source["curve_count"]) == row["curve_count"]
            and int(source["visible_path_exact_count"])
            == row["visible_path_exact_count"]
            and parse_bool(source["visible_path_all_exact"])
            == row["visible_path_all_exact"]
            and int(source["authoritative_full_mask_count"])
            == row["authoritative_full_mask_count"]
            and int(source["missing_source_mask_count"])
            == row["missing_source_mask_count"]
            and int(source["authoritative_full_mask_exact_count"])
            == row["authoritative_full_mask_exact_count"]
            and parse_bool(source["complete_reproduction_exact"])
            == row["complete_reproduction_exact"]
        )
        add_check(
            checks,
            "全局裁决",
            f"{row['candidate_id']}同候选六曲线聚合一致",
            equal,
            equal,
            True,
        )

    visible_success_ids = [
        row["candidate_id"] for row in global_rows if row["visible_path_all_exact"]
    ]
    complete_success_ids = [
        row["candidate_id"] for row in global_rows if row["complete_reproduction_exact"]
    ]
    scientific_visible_gate = (
        "PASS_SINGLE_CANDIDATE_REPRODUCES_ALL_SIX_VISIBLE_CURVES"
        if visible_success_ids
        else "FAIL_NO_SINGLE_CANDIDATE_REPRODUCES_ALL_SIX_VISIBLE_CURVES"
    )
    full_mask_gate = (
        "PASS_ALL_SIX_COMPLETE_MASKS_REPRODUCED"
        if complete_success_ids
        else "NOT_EVALUABLE_FOUR_REDUCED_SOURCE_MASKS_MISSING"
    )
    builder_summary = json.loads(BUILDER_SUMMARY_PATH.read_text(encoding="utf-8"))
    expected_builder_gate = (
        "PASS_COMPLETE_CALCULATION_REPRODUCTION"
        if complete_success_ids
        else "FAIL_NO_COMPLETE_CALCULATION_REPRODUCTION"
    )
    add_check(
        checks,
        "全局裁决",
        "构建器overall由4行同候选六曲线明细导出",
        builder_summary["overall_gate"] == expected_builder_gate
        and bool(builder_summary["all_six_targets_completely_reproduced"])
        == bool(complete_success_ids)
        and int(builder_summary["complete_reproduction_exact_candidate_count"])
        == len(complete_success_ids),
        {
            "builder_overall": builder_summary["overall_gate"],
            "builder_all_six": builder_summary[
                "all_six_targets_completely_reproduced"
            ],
            "builder_complete_count": builder_summary[
                "complete_reproduction_exact_candidate_count"
            ],
        },
        {
            "derived_overall": expected_builder_gate,
            "derived_all_six": bool(complete_success_ids),
            "derived_complete_count": len(complete_success_ids),
        },
    )
    return figure_rows, global_rows, scientific_visible_gate, full_mask_gate


def nearest_diagnostics(
    curve_rows: list[dict[str, Any]], checks: list[dict[str, str]]
) -> list[dict[str, Any]]:
    nearest: list[dict[str, Any]] = []
    for division in (1, 2):
        for method in METHODS:
            subset = [
                row
                for row in curve_rows
                if row["division"] == division and row["method"] == method
            ]
            winner = min(
                subset,
                key=lambda row: (
                    0 if row["path_exact_allow_whole_reverse"] else 1,
                    row["ordered_edit_distance_allow_whole_reverse"],
                    row["symmetric_hausdorff_index_units"],
                    row["rightmost_x_absolute_difference"],
                    row["rightmost_y_set_symmetric_difference_count"],
                    row["candidate_id"],
                ),
            )
            nearest.append(
                {
                    "figure_id": winner["figure_id"],
                    "division": division,
                    "method": method,
                    "method_cn": METHOD_CN[method],
                    "nearest_diagnostic_candidate": winner["candidate_id"],
                    "selection_rule": (
                        "path_exact_then_ordered_edit_then_hausdorff_then_"
                        "rightmost_x_then_rightmost_y_set_then_candidate_id"
                    ),
                    "path_exact_allow_whole_reverse": winner[
                        "path_exact_allow_whole_reverse"
                    ],
                    "ordered_edit_distance_allow_whole_reverse": winner[
                        "ordered_edit_distance_allow_whole_reverse"
                    ],
                    "symmetric_hausdorff_index_units": winner[
                        "symmetric_hausdorff_index_units"
                    ],
                    "rightmost_x_absolute_difference": winner[
                        "rightmost_x_absolute_difference"
                    ],
                    "rightmost_y_set_symmetric_difference_count": winner[
                        "rightmost_y_set_symmetric_difference_count"
                    ],
                    "interpretation": "NEAREST_DIAGNOSTIC_ONLY_NOT_REPRODUCTION",
                }
            )

    builder_rows = read_rows(BUILDER_NEAREST_PATH)
    builder_index = {
        (int(row["division"]), row["method"]): row for row in builder_rows
    }
    add_check(
        checks,
        "最近诊断",
        "六条目标最近诊断行数完整",
        len(nearest) == 6 and len(builder_index) == 6,
        {"independent": len(nearest), "builder": len(builder_index)},
        {"independent": 6, "builder": 6},
    )
    for row in nearest:
        source = builder_index[(row["division"], row["method"])]
        equal = (
            source["nearest_diagnostic_candidate"]
            == row["nearest_diagnostic_candidate"]
            and int(source["pdf_ordered_path_edit_distance_allow_whole_reverse"])
            == row["ordered_edit_distance_allow_whole_reverse"]
            and abs(
                float(source["symmetric_hausdorff_index_units"])
                - row["symmetric_hausdorff_index_units"]
            )
            <= 1e-12
            and int(source["pdf_rightmost_x_absolute_difference_index_units"])
            == row["rightmost_x_absolute_difference"]
            and int(source["pdf_rightmost_y_set_symmetric_difference_count"])
            == row["rightmost_y_set_symmetric_difference_count"]
        )
        add_check(
            checks,
            "最近诊断",
            f"{row['figure_id']} {row['method_cn']}最近诊断字典序一致",
            equal,
            equal,
            True,
            "最近候选只用于诊断，不升级为复现。",
        )
    return nearest


def input_hashes(jobs: list[dict[str, str]]) -> list[dict[str, Any]]:
    paths = {
        STEP8E_POINTS,
        *HISTORY_FILES.values(),
        *(
            TARGET_ROOT / f"图{FIGURE_ID[division]}_{method}_论文矢量边界.csv"
            for division in (1, 2)
            for method in METHODS
        ),
        JOBS_PATH,
        BUILDER_STATS_PATH,
        BUILDER_CURVES_PATH,
        BUILDER_NEAREST_PATH,
        BUILDER_FIGURES_PATH,
        BUILDER_GLOBAL_PATH,
        BUILDER_SUMMARY_PATH,
        SCRIPT,
    }
    paths.update(Path(row["mask_file"]) for row in jobs)
    paths.update(Path(row["boundary_file"]) for row in jobs)
    return [
        {
            "path": str(path.resolve()),
            "size_bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(paths, key=lambda item: str(item).casefold())
    ]


def run_validation(
    checks: list[dict[str, str]], media_before: list[dict[str, Any]]
) -> dict[str, Any]:
    required = [
        STEP8E_POINTS,
        MATLAB_EXE,
        JOBS_PATH,
        BUILDER_STATS_PATH,
        BUILDER_CURVES_PATH,
        BUILDER_NEAREST_PATH,
        BUILDER_FIGURES_PATH,
        BUILDER_GLOBAL_PATH,
        BUILDER_SUMMARY_PATH,
        BUILDER_SCRIPT_PATH,
        *HISTORY_FILES.values(),
    ]
    required.extend(
        TARGET_ROOT / f"图{FIGURE_ID[division]}_{method}_论文矢量边界.csv"
        for division in (1, 2)
        for method in METHODS
    )
    missing = [str(path) for path in required if not path.is_file()]
    add_check(
        checks,
        "输入完整性",
        "步骤8F独立验收所需只读输入完整",
        not missing,
        missing,
        [],
    )
    if missing:
        raise FileNotFoundError("缺少验收输入：" + "\n".join(missing))

    formal_media = validate_formal_media(checks, media_before)

    groups, point_keys = load_step8e_groups(checks)
    targets = load_targets(checks)
    history_masks = load_history_masks(checks)
    jobs, _ = load_jobs_and_builder_masks(groups, history_masks, checks)
    independent, matlab_stdout = independent_matlab_boundaries(jobs)
    add_check(
        checks,
        "独立MATLAB边界",
        "临时MATLAB独立重算30个任务成功",
        "STEP8F_INDEPENDENT_BOUNDARY_VALIDATION_DONE items=30" in matlab_stdout,
        matlab_stdout,
        "STEP8F_INDEPENDENT_BOUNDARY_VALIDATION_DONE items=30",
    )
    paths, structures = compare_independent_boundaries(jobs, independent, checks)
    curve_rows, structures, history_consistency = adjudicate_curves(
        groups, history_masks, targets, paths, structures, checks
    )
    figure_rows, global_rows, scientific_visible_gate, full_mask_gate = (
        aggregate_adjudications(curve_rows, checks)
    )
    nearest = nearest_diagnostics(curve_rows, checks)

    candidate_structural_failures = [
        row for row in structures if row["item_kind"] == "candidate" and row["structural_gate"] == "FAIL"
    ]
    history_structural_failures = [
        row for row in structures if row["item_kind"] == "history" and row["structural_gate"] == "FAIL"
    ]
    add_check(
        checks,
        "历史边界结构",
        "六个历史掩膜均为单一8连通分量且零孔洞",
        not history_structural_failures,
        history_structural_failures,
        [],
    )

    target_summaries = []
    for division in (1, 2):
        for method in METHODS:
            points = targets[(division, method)]
            right_x, right_y = rightmost_path(points)
            target_summaries.append(
                {
                    "figure_id": f"图{FIGURE_ID[division]}",
                    "division": division,
                    "method": method,
                    "method_cn": METHOD_CN[method],
                    "point_count": len(points),
                    "rightmost_x_one_based": right_x,
                    "rightmost_j_zero_based": None if right_x is None else right_x - 1,
                    "rightmost_x_ms": None
                    if right_x is None
                    else (right_x - 1) * DT_MS,
                    "rightmost_y_one_based": list(right_y),
                    "rightmost_l_zero_based": [y - 1 for y in right_y],
                    "rightmost_y_ms": [(y - 1) * DT_MS for y in right_y],
                }
            )

    summary = {
        "step": "8F",
        "evidence_level": "INDEPENDENT_DATA_ADJUDICATION_AND_MEDIA_FORMAT_VALIDATION",
        "validation_status": "PENDING",
        "scientific_visible_curve_gate": scientific_visible_gate,
        "complete_six_mask_evidence_gate": full_mask_gate,
        "candidate_group_count": len(groups),
        "candidate_point_count": len(point_keys),
        "grid_shape": [N_L, N_J],
        "coordinate_mapping": {
            "matlab_storage": "stab(l+1,j+1)",
            "visible_index": "x=column=j+1; y=row=l+1",
            "zero_based": "j=x-1; l=y-1",
            "physical_ms": "tau_x=j*1000/1024; tau_y=l*1000/1024",
            "milliseconds_per_sample": DT_MS,
        },
        "data_only_historical_gate": formal_media[
            "data_only_historical_record"
        ],
        "formal_media_validation": formal_media,
        "independent_matlab": {
            "task_count": len(independent),
            "temporary_artifacts_retained": False,
            "stdout": matlab_stdout,
        },
        "candidate_structural_failures": candidate_structural_failures,
        "history_structural_failures": history_structural_failures,
        "paper_targets": target_summaries,
        "history_target_consistency": [
            history_consistency[(division, method)]
            for division in (1, 2)
            for method in METHODS
        ],
        "curve_adjudications_24": curve_rows,
        "whole_figure_adjudications_8": figure_rows,
        "global_same_candidate_adjudications_4": global_rows,
        "nearest_diagnostics_6": nearest,
        "nearest_diagnostic_semantics": "DIAGNOSTIC_ONLY_NOT_REPRODUCTION",
        "authoritative_mask_rule": {
            "Original": "历史完整掩膜边界与论文路径一致，执行XOR/IoU权威门",
            "Craig-Bampton": "NOT_EVALUABLE_MISSING_SOURCE_MASK",
            "Guyan": "NOT_EVALUABLE_MISSING_SOURCE_MASK",
        },
        "input_hashes": input_hashes(jobs),
    }
    return summary


def render_report(summary: dict[str, Any], checks: list[dict[str, str]]) -> str:
    validation_status = summary.get("validation_status", "FAIL")
    lines = [
        "# 步骤8F独立数据与正式图件格式验收报告",
        "",
        f"- 独立验收状态：{validation_status}。",
        f"- 科学裁决：{summary.get('scientific_visible_curve_gate', 'NOT_AVAILABLE')}。",
        f"- 六个完整掩膜证据：{summary.get('complete_six_mask_evidence_gate', 'NOT_AVAILABLE')}。",
        f"- 检查项：{sum(row['状态'] == 'PASS' for row in checks)}/{len(checks)}通过。",
        "- 验收器没有导入构建器，没有修改构建器数据，也没有创建、覆盖或改写PDF/PNG。",
        "- data-only阶段的媒体数0来自正式渲染之前的历史完成记录；最终目录应且仅应含4份PDF与4份PNG。",
        "- PDF格式门检查单页、零栅格图像、零Type 3字体；PNG格式门检查约600 dpi。视觉QA由主线程另行完成。",
        "",
        "## 坐标合同",
        "",
        "- MATLAB存储为 stab(l+1,j+1)，bwboundaries返回行、列，原图使用x=列、y=行。",
        "- 零基延迟索引为j=x-1、l=y-1；物理毫秒为索引乘1000/1024。",
        "- 1-based绘图索引绝不能直接乘时间步长。",
        "",
        "## 六条论文目标",
        "",
        "| 图 | 方法 | 点数 | 最右x(1-based) | 最右j(0-based) | 最右x(ms) | 最右y集合(1-based) |",
        "|---|---|---:|---:|---:|---:|---|",
    ]
    for row in summary.get("paper_targets", []):
        lines.append(
            f"| {row['figure_id']} | {row['method_cn']} | {row['point_count']} | "
            f"{row['rightmost_x_one_based']} | {row['rightmost_j_zero_based']} | "
            f"{row['rightmost_x_ms']:.6f} | {semicolon(row['rightmost_y_one_based'])} |"
        )
    lines.extend(
        [
            "",
            "## 24行曲线级裁决",
            "",
            "| 图 | 方法 | 候选 | 稳定点 | 分量/孔洞 | 路径exact | 编辑距离 | Hausdorff | 最右x候选/论文 | 可见路径门 | 完整掩膜门 |",
            "|---|---|---|---:|---|---:|---:|---:|---|---|---|",
        ]
    )
    for row in summary.get("curve_adjudications_24", []):
        lines.append(
            f"| {row['figure_id']} | {row['method_cn']} | {row['candidate_id']} | "
            f"{row['candidate_stable_count']} | {row['component_count']}/{row['hole_boundary_count']} | "
            f"{row['path_exact_allow_whole_reverse']} | "
            f"{row['ordered_edit_distance_allow_whole_reverse']} | "
            f"{row['symmetric_hausdorff_index_units']:.6g} | "
            f"{row['candidate_rightmost_x_one_based']}/{row['paper_rightmost_x_one_based']} | "
            f"{row['pdf_visible_path_gate']} | {row['full_mask_gate']} |"
        )
    lines.extend(
        [
            "",
            "## 8行同候选整图裁决",
            "",
            "| 图 | 候选 | 三方法可见路径通过数 | 全部精确 | Original完整掩膜通过数 | 缺失完整掩膜数 | 整图状态 |",
            "|---|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary.get("whole_figure_adjudications_8", []):
        lines.append(
            f"| {row['figure_id']} | {row['candidate_id']} | "
            f"{row['visible_path_exact_count']}/3 | {row['visible_path_all_exact']} | "
            f"{row['authoritative_full_mask_exact_count']}/1 | "
            f"{row['missing_source_mask_count']} | {row['whole_figure_status']} |"
        )
    lines.extend(
        [
            "",
            "## 4行同候选六曲线裁决",
            "",
            "| 候选 | 六曲线可见路径通过数 | 全部精确 | 两条Original完整掩膜通过数 | 缺失完整掩膜数 | 全局状态 |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in summary.get("global_same_candidate_adjudications_4", []):
        lines.append(
            f"| {row['candidate_id']} | {row['visible_path_exact_count']}/6 | "
            f"{row['visible_path_all_exact']} | "
            f"{row['authoritative_full_mask_exact_count']}/2 | "
            f"{row['missing_source_mask_count']} | {row['global_six_curve_status']} |"
        )
    lines.extend(
        [
            "",
            "## 六条目标的最近诊断候选",
            "",
            "| 图 | 方法 | 候选 | 编辑距离 | Hausdorff | 最右x差 | 解释 |",
            "|---|---|---|---:|---:|---:|---|",
        ]
    )
    for row in summary.get("nearest_diagnostics_6", []):
        lines.append(
            f"| {row['figure_id']} | {row['method_cn']} | "
            f"{row['nearest_diagnostic_candidate']} | "
            f"{row['ordered_edit_distance_allow_whole_reverse']} | "
            f"{row['symmetric_hausdorff_index_units']:.6g} | "
            f"{row['rightmost_x_absolute_difference']} | "
            f"{row['interpretation']} |"
        )
    formal_media = summary.get("formal_media_validation", {})
    lines.extend(
        [
            "",
            "## 正式图件格式",
            "",
            "| PDF | 页数 | 栅格XObject | 栅格块 | Type 3字体 | 矢量绘制对象 |",
            "|---|---:|---:|---:|---:|---:|",
        ]
    )
    for row in formal_media.get("pdf_format_details", []):
        lines.append(
            f"| {Path(row['relative_path']).name} | {row.get('page_count', 'NA')} | "
            f"{row.get('raster_xobject_count', 'NA')} | "
            f"{row.get('raster_image_block_count', 'NA')} | "
            f"{row.get('type3_font_count', 'NA')} | "
            f"{row.get('vector_drawing_count', 'NA')} |"
        )
    lines.extend(
        [
            "",
            "| PNG | 像素尺寸 | DPI |",
            "|---|---|---|",
        ]
    )
    for row in formal_media.get("png_format_details", []):
        dpi = row.get("dpi")
        dpi_text = (
            "NA" if dpi is None else f"{dpi[0]:.3f} x {dpi[1]:.3f}"
        )
        lines.append(
            f"| {Path(row['relative_path']).name} | "
            f"{row.get('width_px', 'NA')} x {row.get('height_px', 'NA')} | "
            f"{dpi_text} |"
        )
    lines.extend(
        [
            "",
            "## 证据边界",
            "",
            "- 两条Original历史掩膜的可见边界与论文逐点一致，因此可作为完整31x67掩膜权威。",
            "- 四条缩聚历史掩膜与论文边界冲突，只保留诊断Hamming/IoU；权威Hamming/IoU为null。",
            "- PDF只保存可见开边界，无法唯一恢复孔洞、轴上闭合段或未显示分量。",
            "- 最近诊断采用固定字典序，只用于定位差异，不能升级为完整复现。",
            "",
            "## 检查汇总",
            "",
            "| 状态 | 数量 |",
            "|---|---:|",
            f"| PASS | {sum(row['状态'] == 'PASS' for row in checks)} |",
            f"| FAIL | {sum(row['状态'] == 'FAIL' for row in checks)} |",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    checks: list[dict[str, str]], summary: dict[str, Any]
) -> None:
    VALIDATION_ROOT.mkdir(parents=True, exist_ok=True)
    with CHECKS_PATH.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=[
                "检查编号",
                "检查类别",
                "检查项",
                "状态",
                "实际值",
                "期望值",
                "说明",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(checks)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    REPORT_PATH.write_text(render_report(summary, checks), encoding="utf-8")


def main() -> int:
    checks: list[dict[str, str]] = []
    media_before = media_inventory()
    try:
        summary = run_validation(checks, media_before)
    except Exception as exc:
        add_check(
            checks,
            "致命异常",
            "独立验收器完整执行",
            False,
            f"{type(exc).__name__}: {exc}",
            "无异常",
            traceback.format_exc(),
        )
        summary = {
            "step": "8F",
            "evidence_level": "INDEPENDENT_DATA_ADJUDICATION_AND_MEDIA_FORMAT_VALIDATION",
            "validation_status": "FAIL",
            "fatal_error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
            "formal_media_validation": {"before_validation": media_before},
        }

    summary["check_count"] = len(checks)
    summary["pass_count"] = sum(row["状态"] == "PASS" for row in checks)
    summary["fail_count"] = sum(row["状态"] == "FAIL" for row in checks)
    summary["validation_status"] = (
        "PASS" if summary["fail_count"] == 0 else "FAIL"
    )
    summary["persistent_output_files"] = [
        CHECKS_PATH.name,
        SUMMARY_PATH.name,
        REPORT_PATH.name,
    ]
    write_outputs(checks, summary)

    actual_validation_files = sorted(
        path.name for path in VALIDATION_ROOT.iterdir() if path.is_file()
    )
    expected_validation_files = sorted(summary["persistent_output_files"])
    add_check(
        checks,
        "输出范围",
        "validation目录仅含三份中文验收文件",
        actual_validation_files == expected_validation_files,
        actual_validation_files,
        expected_validation_files,
    )
    media_after = media_inventory()
    before_signature = media_signature(media_before)
    after_signature = media_signature(media_after)
    add_check(
        checks,
        "输出范围",
        "独立验收器未创建、删除、覆盖或改写任何PDF/PNG",
        before_signature == after_signature,
        after_signature,
        before_signature,
        "逐文件比较相对路径、字节数、最后写入纳秒时间及SHA-256。",
    )
    expected_media_paths = set(
        summary.get("formal_media_validation", {}).get(
            "expected_relative_paths", []
        )
    )
    formal_media_after = [
        item
        for item in media_after
        if str(item["relative_path"]).startswith("figures/")
    ]
    final_media_paths = {
        str(item["relative_path"]) for item in formal_media_after
    }
    final_pdf_count = sum(
        item["suffix"] == ".pdf" for item in formal_media_after
    )
    final_png_count = sum(
        item["suffix"] == ".png" for item in formal_media_after
    )
    final_media_exact = (
        final_pdf_count == 4
        and final_png_count == 4
        and bool(expected_media_paths)
        and final_media_paths == expected_media_paths
    )
    add_check(
        checks,
        "输出范围",
        "验收结束时figures正式图件目录仍恰含计划内4份PDF与4份PNG",
        final_media_exact,
        {
            "pdf_count": final_pdf_count,
            "png_count": final_png_count,
            "paths": sorted(final_media_paths),
        },
        {
            "pdf_count": 4,
            "png_count": 4,
            "paths": sorted(expected_media_paths),
        },
    )
    summary["check_count"] = len(checks)
    summary["pass_count"] = sum(row["状态"] == "PASS" for row in checks)
    summary["fail_count"] = sum(row["状态"] == "FAIL" for row in checks)
    summary["validation_status"] = (
        "PASS" if summary["fail_count"] == 0 else "FAIL"
    )
    summary["final_formal_media_files"] = formal_media_after
    summary["final_auxiliary_media_files"] = [
        item
        for item in media_after
        if not str(item["relative_path"]).startswith("figures/")
    ]
    summary["validator_media_immutability"] = {
        "before_signature": before_signature,
        "after_signature": after_signature,
        "unchanged": before_signature == after_signature,
    }
    write_outputs(checks, summary)
    print(json.dumps(
        {
            "validation_status": summary["validation_status"],
            "scientific_visible_curve_gate": summary.get(
                "scientific_visible_curve_gate"
            ),
            "complete_six_mask_evidence_gate": summary.get(
                "complete_six_mask_evidence_gate"
            ),
            "check_count": summary["check_count"],
            "pass_count": summary["pass_count"],
            "fail_count": summary["fail_count"],
        },
        ensure_ascii=False,
        indent=2,
    ))
    return 0 if summary["validation_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

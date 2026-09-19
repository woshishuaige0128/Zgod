from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE_ROOT = SCRIPT_PATH.parent.parent


def find_project_root(start: Path) -> Path:
    for parent in (start, *start.parents):
        if (parent / "WORKFLOW.md").is_file() and (parent / "figure").is_dir():
            return parent
    raise RuntimeError("无法从脚本位置定位项目根目录（缺少 WORKFLOW.md/figure）。")


PROJECT_ROOT = find_project_root(CANDIDATE_ROOT)
RTHS_ROOT = PROJECT_ROOT.parent
CHAPTER_ROOT = PROJECT_ROOT / "figure" / "第3章_缩聚对试验精度的影响"
AUTHOR_PROJECT_ROOT = PROJECT_ROOT / "liangyustability-master"

INPUT_ROOT = CANDIDATE_ROOT / "input"
OUTPUT_ROOT = CANDIDATE_ROOT / "outputs"
LOG_ROOT = CANDIDATE_ROOT / "logs"
REPORT_ROOT = CANDIDATE_ROOT / "report"
TMP_ROOT = CANDIDATE_ROOT / "tmp"

PROTECTED_MANIFEST = (
    PROJECT_ROOT / "test" / "00_总索引与复现规则" / "源文件冻结清单.csv"
)
BOARD17_ROOT = (
    PROJECT_ROOT
    / "test"
    / "00_失败尝试与候选路线"
    / "板块17_两类划分与缩聚候选路线"
)
BOARD17_MANIFEST = BOARD17_ROOT / "report" / "board17_artifact_manifest.csv"
BOARD17_SUMMARY = BOARD17_ROOT / "report" / "board17_final_validation_summary.json"

EXPECTED_THESIS_SHA256 = (
    "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
)
EXPECTED_BASELINE_COLUMNS = [
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
DATASET_STEMS = [
    "单位激励_原结构三层响应",
    "第一类划分_ElCentro地震响应",
    "第二类划分_ElCentro地震响应",
    "第一类划分_Chirp响应",
    "第二类划分_Chirp响应",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def require_file(path: Path, label: str) -> Path:
    if not path.is_file():
        raise RuntimeError(f"缺少{label}: {path}")
    return path


def natural_figure_key(path: Path) -> tuple[int, str]:
    match = re.match(r"图3-(\d+)_", path.name)
    return (int(match.group(1)) if match else 999, path.name)


def figure_contract_rows() -> list[dict[str, str]]:
    common_history = (
        "论文曲线为历史值；现有MAT/CSV为既有计算级旁证；"
        "板块18尚待从冻结作者模型独立重跑并逐图裁决"
    )
    three_methods = "Original;Guyan;Craig-Bampton"
    earth = "El Centro原记录乘EQ_intensity=0.40一次"
    chirp = "40 s内0.1 Hz线性升至10 Hz的Chirp"

    def dataset(stem: str) -> str:
        return (
            f"input/plotting_baseline/输入数据/{stem}.mat;"
            f"input/plotting_baseline/输入数据/{stem}.csv"
        )

    rows = [
        {
            "对象ID": "F3-5",
            "原稿图号": "3-5",
            "唯一图号": "3-5",
            "图名": "单位激励下的3层响应",
            "PDF页": "41",
            "印刷页": "31",
            "划分": "完整原结构（不区分第一类/第二类）",
            "激励": "t=1 s开始的1 m/s^2地面加速度阶跃",
            "楼层": "一层;二层;三层",
            "源数据": dataset("单位激励_原结构三层响应"),
            "输出变量": "time_s;response_mm[:,Original,一至三层];simout3/simout/simout1",
            "方法列": "CSV原结构_一层_mm;原结构_二层_mm;原结构_三层_mm",
            "全时窗": "0-40 s",
            "局部窗": "不适用（原稿为单面板）",
            "单位": "原稿m并显示×10^-3；冻结MAT/CSV为mm",
            "原稿异常": "正文未给单位阶跃开始时刻；精确定义来自可追溯模型恢复说明",
            "历史值状态": common_history,
        }
    ]

    specs = [
        ("F3-6", "3-6", "3-6", "42", "32", "第一类", earth, "一层", "第一类划分_ElCentro地震响应", "simout3", "10-11 s;21.5-22.5 s", "无"),
        ("F3-7", "3-7", "3-7", "42-43", "32-33", "第一类", earth, "二层", "第一类划分_ElCentro地震响应", "simout", "10-11 s;21.5-22.5 s", "全时域图与局部图跨PDF两页，题注在PDF第43页"),
        ("F3-8", "3-8", "3-8", "43", "33", "第一类", earth, "三层", "第一类划分_ElCentro地震响应", "simout1", "10-11 s;21.5-22.5 s", "无"),
        ("F3-9", "3-9", "3-9", "44", "34", "第二类", earth, "一层", "第二类划分_ElCentro地震响应", "simout3", "10-11 s;21.5-22.5 s", "第二类未给二层地震响应图；psi6由缩聚坐标恢复"),
        ("F3-10", "3-10", "3-10", "44-45", "34-35", "第二类", earth, "三层", "第二类划分_ElCentro地震响应", "simout1", "10-11 s;21.5-22.5 s", "全时域图与局部图跨PDF两页；原SLX三层Guyan/CB端口缺线，既有副本含可审计修复"),
        ("F3-11", "3-11", "3-11", "46", "36", "第一类", chirp, "一层", "第一类划分_Chirp响应", "simout3", "13-14 s;38-38.3 s", "无"),
        ("F3-12", "3-11", "3-12", "47", "37", "第一类", chirp, "二层", "第一类划分_Chirp响应", "simout", "13-14 s;38-38.3 s", "原稿重复印为图3-11；按正文连续关系唯一编号为图3-12"),
        ("F3-13", "3-13", "3-13", "47-48", "37-38", "第一类", chirp, "三层", "第一类划分_Chirp响应", "simout1", "13-14 s;38-38.3 s", "全时域图与局部图跨PDF两页，题注在PDF第48页"),
        ("F3-14", "3-13", "3-14", "48", "38", "第二类", chirp, "一层", "第二类划分_Chirp响应", "simout3", "13-14 s;38-38.3 s", "原稿重复印为图3-13；按正文连续关系唯一编号为图3-14"),
        ("F3-15", "3-13", "3-15", "49", "39", "第二类", chirp, "三层", "第二类划分_Chirp响应", "simout1", "13-14 s;38-38.3 s", "原稿重复印为图3-13；全时域为Chirp，但两个局部图误贴地震10-11 s与21.5-22.5 s，不能作为Chirp计算基准"),
    ]
    for object_id, original_no, unique_no, pdf_page, printed_page, division, excitation, floor, stem, workspace, local_windows, anomaly in specs:
        floor_token = {"一层": "一层", "二层": "二层", "三层": "三层"}[floor]
        rows.append(
            {
                "对象ID": object_id,
                "原稿图号": original_no,
                "唯一图号": unique_no,
                "图名": f"{division}子结构划分-{('地震激励下的' if 'El Centro' in excitation else 'Chirp信号的')}{floor}水平位移",
                "PDF页": pdf_page,
                "印刷页": printed_page,
                "划分": division,
                "激励": excitation,
                "楼层": floor,
                "源数据": dataset(stem),
                "输出变量": f"time_s;response_mm[:,三种方法,{floor_token}];{workspace}",
                "方法列": (
                    f"CSV原结构_{floor_token}_mm;Guyan_{floor_token}_mm;"
                    f"CraigBampton_{floor_token}_mm|MAT:{three_methods}"
                ),
                "全时窗": "0-40 s",
                "局部窗": local_windows,
                "单位": "mm",
                "原稿异常": anomaly,
                "历史值状态": common_history,
            }
        )
    return rows


def collect_freeze_sources() -> list[tuple[str, Path, str]]:
    source_copy = CHAPTER_ROOT / "原始来源副本"
    model_dir = source_copy / "模型与参数原件"
    aux_ground_dir = source_copy / "辅助来源_地震记录"
    live_dir = source_copy / "原始LiveScript"
    transfer_dir = source_copy / "MLX转存文本"
    author_plot_dir = source_copy / "原绘图脚本"
    baseline_data_dir = CHAPTER_ROOT / "输入数据"
    baseline_code_dir = CHAPTER_ROOT / "可复现代码"
    baseline_validation_dir = CHAPTER_ROOT / "验证记录" / "逐图验证"
    board16_dir = (
        PROJECT_ROOT
        / "test"
        / "00_上游模型身份证"
        / "U01_参考结构参数与15自由度矩阵"
    )

    items: list[tuple[str, Path, str]] = []

    def add(role: str, source: Path, relative_target: str) -> None:
        items.append((role, require_file(source, role), relative_target))

    add("硕士论文PDF", RTHS_ROOT / "梁禹手稿.pdf", "input/author_source/论文与答辩材料/梁禹手稿.pdf")
    add("硕士答辩PPT", RTHS_ROOT / "梁禹硕士答辩-20250528.pptx", "input/author_source/论文与答辩材料/梁禹硕士答辩-20250528.pptx")

    for name in ["PDmonicanshu.m", "EQ.mat", "lvxvjie_guyan_2.slx", "lvxvjie_guyan.slx"]:
        add("作者模型与参数原件", model_dir / name, f"input/author_source/模型与参数原件/{name}")
    add(
        "2026现存响应生成器（非作者历史原件）",
        baseline_code_dir / "regenerate_chapter3_data.m",
        "input/current_reproduction_code/regenerate_chapter3_data.m",
    )
    for source in sorted(aux_ground_dir.glob("*.mat")):
        add("作者辅助地震记录", source, f"input/author_source/辅助来源_地震记录/{source.name}")
    if len(list(aux_ground_dir.glob("*.mat"))) != 3:
        raise RuntimeError("作者辅助地震记录应恰为3个MAT文件。")
    for name in ["untitled.mlx", "untitled2.mlx"]:
        add("作者原始LiveScript", live_dir / name, f"input/author_source/原始LiveScript/{name}")
    for name in ["untitled_转存.m", "untitled2_转存.m"]:
        add("作者MLX转存文本", transfer_dir / name, f"input/author_source/MLX转存文本/{name}")
    picture_files = sorted(author_plot_dir.glob("picture*.m"))
    if len(picture_files) != 5:
        raise RuntimeError(f"作者picture*.m应恰为5份，现场为{len(picture_files)}份。")
    for source in picture_files:
        add("作者绘图脚本", source, f"input/author_source/作者绘图脚本/{source.name}")

    for stem in DATASET_STEMS:
        for suffix in [".mat", ".csv"]:
            source = baseline_data_dir / f"{stem}{suffix}"
            add("既有五组绘图基线MAT_CSV", source, f"input/plotting_baseline/输入数据/{source.name}")

    plot_codes = sorted(
        [
            path
            for path in baseline_code_dir.glob("图3-*_绘制*.py")
            if re.match(r"^图3-(5|6|7|8|9|10|11|12|13|14|15)_", path.name)
        ],
        key=natural_figure_key,
    )
    if len(plot_codes) != 11:
        raise RuntimeError(f"图3-5至图3-15绘图代码应为11份，现场为{len(plot_codes)}份。")
    for source in plot_codes:
        add("既有逐图绘图代码", source, f"input/plotting_baseline/可复现代码/{source.name}")

    validation_files = sorted(
        [
            path
            for path in baseline_validation_dir.glob("图3-*_验证.md")
            if re.match(r"^图3-(5|6|7|8|9|10|11|12|13|14|15)_", path.name)
        ],
        key=natural_figure_key,
    )
    if len(validation_files) != 11:
        raise RuntimeError(f"图3-5至图3-15逐图验证记录应为11份，现场为{len(validation_files)}份。")
    for source in validation_files:
        add("既有逐图验证记录", source, f"input/plotting_baseline/验证记录/逐图验证/{source.name}")

    aggregate_sources = [
        ("第三章来源与恢复说明", CHAPTER_ROOT / "来源与恢复说明.md"),
        ("第三章复现README", CHAPTER_ROOT / "README_第3章图片复现.md"),
        ("第三章交付清单", CHAPTER_ROOT / "章节交付清单.csv"),
        ("28图总索引", PROJECT_ROOT / "figure" / "00_总索引与说明" / "图片总索引.csv"),
        ("45对象总索引", PROJECT_ROOT / "test" / "00_总索引与复现规则" / "全部对象总索引.csv"),
        ("326保护源清单", PROTECTED_MANIFEST),
        ("第三章数值统计", CHAPTER_ROOT / "验证记录" / "第3章仿真响应数值统计.csv"),
    ]
    for role, source in aggregate_sources:
        add(role, source, f"input/plotting_baseline/验证记录/汇总/{source.name}")

    board16_sources = [
        ("U01完整15自由度矩阵", board16_dir / "data" / "reference_model_matlab.mat"),
        ("U01自然自由度映射", board16_dir / "data" / "dof_map.csv"),
        ("U01参考参数", board16_dir / "data" / "reference_parameters.csv"),
        ("板块16验收摘要", board16_dir / "report" / "board16_acceptance_summary.json"),
        ("板块16工件清单", board16_dir / "report" / "board16_artifact_manifest.csv"),
    ]
    for role, source in board16_sources:
        add(role, source, f"input/upstream_passports/board16/{source.name}")

    board17_output_names = [
        "global_routes_matlab.mat",
        "independent_global_routes_python.mat",
        "global_route_summary.json",
        "cross_language_summary.json",
        "contract_divisions.csv",
        "contract_dof_membership.csv",
        "contract_recovery.csv",
        "contract_simulink_outputs.csv",
        "contract_simulink_workspace.csv",
        "global_dimension_gates.csv",
        "global_recovery_matrices.csv",
        "global_source_hashes.csv",
        "object_adjudication.csv",
        "local_dof_sets.csv",
    ]
    for name in board17_output_names:
        add("板块17缩聚模型身份证", BOARD17_ROOT / "outputs" / name, f"input/upstream_passports/board17/{name}")
    board17_report_names = [
        "board17_final_validation_summary.json",
        "board17_artifact_manifest.csv",
        "板块17_最终验收记录.md",
    ]
    for name in board17_report_names:
        add("板块17最终验收", BOARD17_ROOT / "report" / name, f"input/upstream_passports/board17/{name}")

    target_counts = Counter(target for _, _, target in items)
    duplicate_targets = sorted(target for target, count in target_counts.items() if count != 1)
    if duplicate_targets:
        raise RuntimeError(f"冻结目标路径重复: {duplicate_targets}")
    return items


def validate_baseline_datasets() -> list[dict[str, Any]]:
    from scipy.io import whosmat

    rows: list[dict[str, Any]] = []
    data_dir = CHAPTER_ROOT / "输入数据"
    required_vars = {
        "time_s": (40961, 1),
        "response_mm": (40961, 3, 3),
        "method_order": (1, 3),
        "floor_order": (1, 3),
    }
    for stem in DATASET_STEMS:
        mat_path = require_file(data_dir / f"{stem}.mat", "绘图基线MAT")
        csv_path = require_file(data_dir / f"{stem}.csv", "绘图基线CSV")
        inventory = {name: tuple(shape) for name, shape, _ in whosmat(mat_path)}
        mat_ok = all(inventory.get(name) == shape for name, shape in required_vars.items())
        with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
            header = next(csv.reader(handle))
        csv_ok = header == EXPECTED_BASELINE_COLUMNS
        rows.append(
            {
                "dataset": stem,
                "mat_schema_ok": mat_ok,
                "csv_schema_ok": csv_ok,
                "mat_variables": json.dumps(inventory, ensure_ascii=False, sort_keys=True),
                "csv_columns": json.dumps(header, ensure_ascii=False),
                "status": "PASS" if mat_ok and csv_ok else "FAIL",
            }
        )
    return rows


def freeze_inputs(items: list[tuple[str, Path, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for role, source, relative_target in items:
        if is_within(source, CANDIDATE_ROOT):
            raise RuntimeError(f"冻结源不得位于板块18候选目录内: {source}")
        target = CANDIDATE_ROOT / Path(*PurePosixPath(relative_target).parts)
        if not is_within(target, CANDIDATE_ROOT):
            raise RuntimeError(f"冻结目标越出候选目录: {target}")
        source_size = source.stat().st_size
        source_hash_before = sha256_file(source)
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if not target.is_file():
                raise RuntimeError(f"冻结目标已存在但不是文件: {target}")
            if target.stat().st_size != source_size or sha256_file(target) != source_hash_before:
                raise RuntimeError(f"冻结目标已存在且与源不同，拒绝覆盖: {target}")
            action = "REUSED_MATCH"
        else:
            shutil.copy2(source, target)
            action = "COPIED"
        source_hash_after = sha256_file(source)
        target_hash = sha256_file(target)
        target_size = target.stat().st_size
        status = (
            "MATCH"
            if source_size == target_size
            and source_hash_before == source_hash_after == target_hash
            else "MISMATCH"
        )
        rows.append(
            {
                "role": role,
                "source_path": str(source),
                "copied_relative_path": relative_target,
                "source_size_bytes": source_size,
                "copy_size_bytes": target_size,
                "source_sha256_before": source_hash_before,
                "source_sha256_after": source_hash_after,
                "copy_sha256": target_hash,
                "source_outside_candidate": True,
                "copy_inside_candidate": True,
                "status": status,
                "action": action,
            }
        )
    return rows


def recheck_protected_sources() -> tuple[list[dict[str, Any]], bool]:
    require_file(PROTECTED_MANIFEST, "326保护源清单")
    source_rows = read_csv(PROTECTED_MANIFEST)
    output_rows: list[dict[str, Any]] = []
    for index, row in enumerate(source_rows, start=1):
        path = Path(row.get("绝对路径", ""))
        exists = path.is_file()
        expected_size = int(row.get("文件大小_字节", "-1") or -1)
        expected_hash = (row.get("SHA256", "") or "").upper()
        actual_size = path.stat().st_size if exists else -1
        actual_hash = sha256_file(path) if exists else ""
        match = exists and actual_size == expected_size and actual_hash == expected_hash
        output_rows.append(
            {
                "row": index,
                "category": row.get("类别", ""),
                "absolute_path": str(path),
                "expected_size_bytes": expected_size,
                "actual_size_bytes": actual_size,
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "status": "MATCH" if match else "MISMATCH",
                "reason": "" if match else "文件缺失、大小变化或SHA-256变化",
            }
        )
    passed = len(source_rows) == 326 and all(row["status"] == "MATCH" for row in output_rows)
    return output_rows, passed


def recheck_board17_artifacts() -> tuple[list[dict[str, Any]], bool]:
    require_file(BOARD17_MANIFEST, "板块17工件清单")
    manifest_rows = read_csv(BOARD17_MANIFEST)
    output_rows: list[dict[str, Any]] = []
    for index, row in enumerate(manifest_rows, start=1):
        relative = row.get("relative_path", "")
        parts = PurePosixPath(relative).parts
        path = (PROJECT_ROOT / Path(*parts)).resolve()
        scoped = is_within(path, PROJECT_ROOT)
        exists = scoped and path.is_file()
        expected_size = int(row.get("size_bytes", "-1") or -1)
        expected_hash = (row.get("sha256", "") or "").upper()
        actual_size = path.stat().st_size if exists else -1
        actual_hash = sha256_file(path) if exists else ""
        match = scoped and exists and actual_size == expected_size and actual_hash == expected_hash
        output_rows.append(
            {
                "row": index,
                "relative_path": relative,
                "resolved_path": str(path),
                "inside_project": scoped,
                "expected_size_bytes": expected_size,
                "actual_size_bytes": actual_size,
                "expected_sha256": expected_hash,
                "actual_sha256": actual_hash,
                "status": "MATCH" if match else "MISMATCH",
                "reason": "" if match else "路径越界、文件缺失、大小变化或SHA-256变化",
            }
        )
    summary = json.loads(require_file(BOARD17_SUMMARY, "板块17验收摘要").read_text(encoding="utf-8"))
    passed = (
        len(manifest_rows) == 305
        and all(row["status"] == "MATCH" for row in output_rows)
        and summary.get("pass") is True
        and int(summary.get("board17_artifact_manifest_count", -1)) == 305
    )
    return output_rows, passed


def inspect_mat(path: Path) -> tuple[list[tuple[str, tuple[int, ...], str]], str]:
    try:
        from scipy.io import whosmat

        return [(name, tuple(shape), kind) for name, shape, kind in whosmat(path)], ""
    except Exception as exc:  # v7.3/HDF5或损坏文件需要保留人工复核状态
        return [], f"{type(exc).__name__}: {exc}"


def history_timeseries_scan() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not AUTHOR_PROJECT_ROOT.is_dir():
        raise RuntimeError(f"梁禹原工程目录不存在: {AUTHOR_PROJECT_ROOT}")
    candidates = sorted(
        [
            path
            for path in AUTHOR_PROJECT_ROOT.rglob("*")
            if path.is_file() and path.suffix.lower() in {".mat", ".fig", ".csv"}
        ],
        key=lambda item: item.as_posix().lower(),
    )
    rows: list[dict[str, Any]] = []
    time_tokens = ("time", "tout", "时间")
    response_tokens = ("simout", "response", "disp", "displacement", "位移", "yout", "xout")
    excitation_tokens = ("eq.mat", "accel", "elcentro", "kobe", "morgan", "ground_motion")
    different_analysis_tokens = ("stability", "稳定", "lqr", "能量", "energy", "benchmark")

    for path in candidates:
        relative = path.relative_to(AUTHOR_PROJECT_ROOT).as_posix()
        suffix = path.suffix.lower()
        variables: list[tuple[str, tuple[int, ...], str]] = []
        inspect_error = ""
        csv_header: list[str] = []
        csv_data_rows = -1
        if suffix == ".mat":
            variables, inspect_error = inspect_mat(path)
        elif suffix == ".csv":
            try:
                with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
                    reader = csv.reader(handle)
                    csv_header = next(reader, [])
                    csv_data_rows = sum(1 for _ in reader)
            except Exception as exc:
                inspect_error = f"{type(exc).__name__}: {exc}"

        names = [name.lower() for name, _, _ in variables] + [name.lower() for name in csv_header]
        has_time = any(any(token in name for token in time_tokens) or name == "t" for name in names)
        has_response = any(any(token in name for token in response_tokens) for name in names)
        large_timeseries = any(
            len(shape) == 2 and shape[0] >= 1000 and 2 <= shape[1] <= 50
            for _, shape, _ in variables
        ) or csv_data_rows >= 1000
        lowered_path = relative.lower()
        excitation_only = any(token in lowered_path for token in excitation_tokens)
        different_analysis = any(token in lowered_path for token in different_analysis_tokens)

        if inspect_error:
            status = "MANUAL_REVIEW_REQUIRED"
            reason = "MAT/CSV目录可定位，但当前Python只读库存取失败；不能据此认定为第三章历史响应。"
        elif suffix == ".fig":
            status = "EXCLUDED_FIG_PRESENTATION_ONLY"
            reason = "FIG只保存展示对象，未与三方法原始时序和模型运行入口建立唯一关系。"
        elif excitation_only and not has_response:
            status = "EXCLUDED_EXCITATION_ONLY"
            reason = "仅为地震/加速度输入，不是Original/Guyan/Craig-Bampton三方法响应工作区。"
        elif different_analysis and not (has_time and has_response):
            status = "EXCLUDED_DIFFERENT_ANALYSIS"
            reason = "文件名/路径属于稳定性、LQR、能量或基准模型，不是图3-5至图3-15响应。"
        elif has_time and (has_response or large_timeseries):
            status = "POTENTIAL_HISTORY_TIMESERIES_REVIEW"
            reason = "发现时间与响应/长时序特征；只能作为历史候选，后续仍须核对方法列、激励、楼层和来源。"
        elif large_timeseries:
            status = "POTENTIAL_NUMERIC_ARRAY_REVIEW"
            reason = "发现长二维数组但没有明确时间/响应字段；保留人工复核，不作为绘图基准。"
        elif suffix == ".csv" and any("matrix" in name for name in names + [lowered_path]):
            status = "EXCLUDED_STRUCTURAL_MATRIX"
            reason = "CSV为结构质量/刚度矩阵，不含第三章三方法时程。"
        else:
            status = "EXCLUDED_NO_TIME_RESPONSE_SIGNATURE"
            reason = "未发现可同时证明时间轴和Original/Guyan/Craig-Bampton响应的变量签名。"

        variable_summary = ";".join(
            f"{name}:{'x'.join(str(value) for value in shape)}:{kind}"
            for name, shape, kind in variables
        )
        rows.append(
            {
                "absolute_path": str(path),
                "relative_path": relative,
                "extension": suffix,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "variable_count": len(variables),
                "variable_summary": variable_summary,
                "csv_header": json.dumps(csv_header, ensure_ascii=False),
                "csv_data_rows": csv_data_rows,
                "has_time_signature": has_time,
                "has_response_signature": has_response,
                "has_large_timeseries_shape": large_timeseries,
                "inspection_error": inspect_error,
                "status": status,
                "reason": reason,
            }
        )

    status_counts = Counter(str(row["status"]) for row in rows)
    extension_counts = Counter(str(row["extension"]) for row in rows)
    summary = {
        "generated_at_utc": utc_now(),
        "scan_root": str(AUTHOR_PROJECT_ROOT),
        "scope": "梁禹原工程内全部MAT/FIG/CSV，排除后建figure/test目录",
        "total_candidates": len(rows),
        "extension_counts": dict(sorted(extension_counts.items())),
        "status_counts": dict(sorted(status_counts.items())),
        "potential_review_count": sum(
            1 for row in rows if str(row["status"]).startswith("POTENTIAL_")
        ),
        "manual_review_count": sum(
            1 for row in rows if row["status"] == "MANUAL_REVIEW_REQUIRED"
        ),
        "excluded_count": sum(
            1 for row in rows if str(row["status"]).startswith("EXCLUDED_")
        ),
        "potential_paths": [
            row["relative_path"]
            for row in rows
            if str(row["status"]).startswith("POTENTIAL_")
        ],
        "policy": (
            "扫描命中只获得历史候选身份；没有方法列、激励、楼层、时间轴和代码入口的联合证据，"
            "不得作为图3-5至图3-15计算级复现基准。"
        ),
    }
    return rows, summary


def main() -> int:
    for directory in [INPUT_ROOT, OUTPUT_ROOT, LOG_ROOT, REPORT_ROOT, TMP_ROOT]:
        directory.mkdir(parents=True, exist_ok=True)

    figure_rows = figure_contract_rows()
    if len(figure_rows) != 11 or len({row["对象ID"] for row in figure_rows}) != 11:
        raise RuntimeError("逐图合同必须恰为11行且对象ID唯一。")
    figure_contract_path = OUTPUT_ROOT / "figure_contract.csv"
    contract_fields = [
        "对象ID", "原稿图号", "唯一图号", "图名", "PDF页", "印刷页", "划分", "激励",
        "楼层", "源数据", "输出变量", "方法列", "全时窗", "局部窗", "单位", "原稿异常", "历史值状态",
    ]
    write_csv(figure_contract_path, contract_fields, figure_rows)

    baseline_checks = validate_baseline_datasets()
    baseline_check_path = OUTPUT_ROOT / "baseline_dataset_schema_checks.csv"
    write_csv(
        baseline_check_path,
        ["dataset", "mat_schema_ok", "csv_schema_ok", "mat_variables", "csv_columns", "status"],
        baseline_checks,
    )
    baseline_pass = len(baseline_checks) == 5 and all(row["status"] == "PASS" for row in baseline_checks)

    protected_rows, protected_pass = recheck_protected_sources()
    protected_recheck_path = OUTPUT_ROOT / "protected_source_recheck.csv"
    write_csv(
        protected_recheck_path,
        ["row", "category", "absolute_path", "expected_size_bytes", "actual_size_bytes", "expected_sha256", "actual_sha256", "status", "reason"],
        protected_rows,
    )

    board17_rows, board17_pass = recheck_board17_artifacts()
    board17_recheck_path = OUTPUT_ROOT / "board17_artifact_recheck.csv"
    write_csv(
        board17_recheck_path,
        ["row", "relative_path", "resolved_path", "inside_project", "expected_size_bytes", "actual_size_bytes", "expected_sha256", "actual_sha256", "status", "reason"],
        board17_rows,
    )

    freeze_items = collect_freeze_sources()
    freeze_rows = freeze_inputs(freeze_items)
    input_manifest_path = INPUT_ROOT / "input_manifest.csv"
    input_fields = [
        "role", "source_path", "copied_relative_path", "source_size_bytes", "copy_size_bytes",
        "source_sha256_before", "source_sha256_after", "copy_sha256", "source_outside_candidate",
        "copy_inside_candidate", "status", "action",
    ]
    write_csv(input_manifest_path, input_fields, freeze_rows)
    freeze_pass = bool(freeze_rows) and all(row["status"] == "MATCH" for row in freeze_rows)
    thesis_rows = [row for row in freeze_rows if row["role"] == "硕士论文PDF"]
    thesis_hash_ok = (
        len(thesis_rows) == 1
        and thesis_rows[0]["copy_sha256"] == EXPECTED_THESIS_SHA256
    )
    freeze_summary = {
        "generated_at_utc": utc_now(),
        "source_count": len(freeze_rows),
        "copy_count": len(freeze_rows),
        "match_count": sum(1 for row in freeze_rows if row["status"] == "MATCH"),
        "copied_count": sum(1 for row in freeze_rows if row["action"] == "COPIED"),
        "reused_match_count": sum(1 for row in freeze_rows if row["action"] == "REUSED_MATCH"),
        "all_match": freeze_pass,
        "thesis_sha256": thesis_rows[0]["copy_sha256"] if thesis_rows else "",
        "thesis_hash_ok": thesis_hash_ok,
        "manifest_sha256": sha256_file(input_manifest_path),
    }
    write_json(INPUT_ROOT / "input_freeze_summary.json", freeze_summary)

    history_rows, history_summary = history_timeseries_scan()
    history_scan_path = OUTPUT_ROOT / "history_timeseries_scan.csv"
    history_fields = [
        "absolute_path", "relative_path", "extension", "size_bytes", "sha256", "variable_count",
        "variable_summary", "csv_header", "csv_data_rows", "has_time_signature",
        "has_response_signature", "has_large_timeseries_shape", "inspection_error", "status", "reason",
    ]
    write_csv(history_scan_path, history_fields, history_rows)
    history_summary["scan_csv_sha256"] = sha256_file(history_scan_path)
    write_json(OUTPUT_ROOT / "history_timeseries_scan_summary.json", history_summary)

    success_dir_names = [
        f"图3-{number}_" for number in range(5, 16)
    ]
    existing_success_dirs = [
        str(path)
        for path in (PROJECT_ROOT / "test").iterdir()
        if path.is_dir() and any(path.name.startswith(prefix) for prefix in success_dir_names)
    ]

    overall_pass = all(
        [
            baseline_pass,
            protected_pass,
            board17_pass,
            freeze_pass,
            thesis_hash_ok,
            len(history_rows) == 42,
            Counter(row["extension"] for row in history_rows) == Counter({".mat": 38, ".csv": 4}),
            not existing_success_dirs,
        ]
    )
    summary = {
        "generated_at_utc": utc_now(),
        "script": str(SCRIPT_PATH),
        "script_sha256_before_summary_write": sha256_file(SCRIPT_PATH),
        "overall_status": "PASS" if overall_pass else "FAIL",
        "figure_contract_rows": len(figure_rows),
        "figure_contract_sha256": sha256_file(figure_contract_path),
        "baseline_dataset_count": len(baseline_checks),
        "baseline_dataset_pass_count": sum(row["status"] == "PASS" for row in baseline_checks),
        "protected_source_count": len(protected_rows),
        "protected_source_match_count": sum(row["status"] == "MATCH" for row in protected_rows),
        "board17_artifact_count": len(board17_rows),
        "board17_artifact_match_count": sum(row["status"] == "MATCH" for row in board17_rows),
        "freeze_source_count": len(freeze_rows),
        "freeze_match_count": sum(row["status"] == "MATCH" for row in freeze_rows),
        "freeze_manifest_sha256": sha256_file(input_manifest_path),
        "history_scan_count": len(history_rows),
        "history_extension_counts": history_summary["extension_counts"],
        "history_status_counts": history_summary["status_counts"],
        "history_potential_review_count": history_summary["potential_review_count"],
        "history_manual_review_count": history_summary["manual_review_count"],
        "success_directories_created": 0,
        "preexisting_success_directories": existing_success_dirs,
        "protected_pass": protected_pass,
        "board17_pass": board17_pass,
        "baseline_pass": baseline_pass,
        "freeze_pass": freeze_pass,
        "thesis_hash_ok": thesis_hash_ok,
        "source_assets_modified": False,
        "simulation_run": False,
        "plot_run": False,
    }
    summary_path = OUTPUT_ROOT / "build_board18_summary.json"
    write_json(summary_path, summary)

    log_lines = [
        "板块18图3-5至图3-15逐图计算复现：合同与冻结",
        f"生成时间UTC: {summary['generated_at_utc']}",
        f"总状态: {summary['overall_status']}",
        f"逐图合同: {len(figure_rows)}/11",
        f"五组MAT/CSV模式: {summary['baseline_dataset_pass_count']}/5 PASS",
        f"保护源: {summary['protected_source_match_count']}/326 MATCH",
        f"板块17工件: {summary['board17_artifact_match_count']}/305 MATCH",
        f"冻结输入: {summary['freeze_match_count']}/{summary['freeze_source_count']} MATCH",
        f"历史候选扫描: {len(history_rows)}（MAT={history_summary['extension_counts'].get('.mat', 0)}, FIG={history_summary['extension_counts'].get('.fig', 0)}, CSV={history_summary['extension_counts'].get('.csv', 0)}）",
        f"历史候选需复核: {history_summary['potential_review_count']}，格式人工复核: {history_summary['manual_review_count']}",
        "本脚本未运行MATLAB/Simulink、未出图、未修改源资产、未建立成功目录。",
    ]
    (LOG_ROOT / "build_board18_contract_and_freeze.log").write_text(
        "\n".join(log_lines) + "\n", encoding="utf-8"
    )
    print("\n".join(log_lines))
    return 0 if overall_pass else 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        LOG_ROOT.mkdir(parents=True, exist_ok=True)
        message = f"板块18合同与冻结脚本异常：{type(exc).__name__}: {exc}"
        (LOG_ROOT / "build_board18_contract_and_freeze.log").write_text(
            message + "\n", encoding="utf-8"
        )
        print(message, file=sys.stderr)
        raise SystemExit(2)

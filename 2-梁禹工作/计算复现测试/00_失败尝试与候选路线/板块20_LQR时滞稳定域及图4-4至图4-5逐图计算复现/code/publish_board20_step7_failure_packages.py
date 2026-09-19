from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import stat
import tempfile
from pathlib import Path
from typing import Any, Iterable


BOARD_NAME = "板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现"
CONTRACT_NAME = "board20_step7_publication_contract.json"
PACKAGE_MANIFEST_FIELDS = ["relative_path", "size_bytes", "sha256", "role"]
SHARED_MANIFEST_FIELDS = [
    "object_id",
    "central_relative_path",
    "size_bytes",
    "sha256",
    "source_step",
    "role",
    "copy_policy",
    "scope_note",
]


def find_board_root(start: Path) -> Path:
    for candidate in (start, *start.parents):
        if candidate.name == BOARD_NAME:
            return candidate.resolve()
    raise RuntimeError("无法定位板块20隔离目录。")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not reader.fieldnames:
            raise ValueError(f"CSV没有表头：{path}")
        return list(reader.fieldnames), list(reader)


def write_csv(path: Path, fieldnames: list[str], rows: Iterable[dict[str, Any]]) -> None:
    rows_list = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, extrasaction="raise", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows_list)
    os.replace(temporary, path)


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def assert_regular_file(path: Path) -> None:
    if not path.is_file() or path.is_symlink():
        raise FileNotFoundError(f"缺少普通文件或检测到链接：{path}")
    if hasattr(path.stat(), "st_file_attributes"):
        attrs = path.stat().st_file_attributes
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if attrs & reparse:
            raise RuntimeError(f"拒绝重解析点：{path}")


def assert_within(child: Path, parent: Path) -> None:
    resolved_child = child.resolve()
    resolved_parent = parent.resolve()
    if resolved_child != resolved_parent and resolved_parent not in resolved_child.parents:
        raise RuntimeError(f"路径越界：{resolved_child} 不在 {resolved_parent} 内")


def copy_file(source: Path, destination: Path) -> None:
    assert_regular_file(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, destination)
    if sha256_file(source) != sha256_file(destination):
        raise RuntimeError(f"复制哈希不一致：{source} -> {destination}")


def role_for(relative_path: str) -> str:
    if relative_path == "README.md":
        return "self_contained_readme"
    if relative_path == "package_summary.json":
        return "machine_readable_summary"
    if relative_path == "shared_evidence_manifest.csv":
        return "shared_hash_bound_reference"
    if relative_path.startswith("code/"):
        return "rerun_entry"
    if relative_path.startswith("data/"):
        return "object_specific_evidence"
    if relative_path.startswith("logs/"):
        return "execution_or_failure_log"
    if relative_path.startswith("figures/"):
        return "figure_copy"
    if relative_path.startswith("visual/"):
        return "visual_quality_evidence"
    return "supporting_evidence"


def build_artifact_manifest(package_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(package_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_symlink():
            raise RuntimeError(f"包内禁止链接：{path}")
        if not path.is_file() or path.name == "artifact_manifest.csv":
            continue
        if path.stat().st_nlink != 1:
            raise RuntimeError(f"包内禁止硬链接：{path}")
        relative = path.relative_to(package_root).as_posix()
        rows.append(
            {
                "relative_path": relative,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "role": role_for(relative),
            }
        )
    write_csv(package_root / "artifact_manifest.csv", PACKAGE_MANIFEST_FIELDS, rows)
    return rows


def compare_trees(left: Path, right: Path) -> list[dict[str, Any]]:
    def inventory(root: Path) -> dict[str, Path]:
        return {
            path.relative_to(root).as_posix(): path
            for path in root.rglob("*")
            if path.is_file()
        }

    left_files = inventory(left)
    right_files = inventory(right)
    if set(left_files) != set(right_files):
        missing = sorted(set(left_files) ^ set(right_files))
        raise RuntimeError(f"两轮文件集合不同：{missing[:10]}")
    rows: list[dict[str, Any]] = []
    for relative in sorted(left_files, key=str.casefold):
        left_path = left_files[relative]
        right_path = right_files[relative]
        left_hash = sha256_file(left_path)
        right_hash = sha256_file(right_path)
        identical = left_path.stat().st_size == right_path.stat().st_size and left_hash == right_hash
        rows.append(
            {
                "relative_path": relative,
                "run1_size_bytes": left_path.stat().st_size,
                "run2_size_bytes": right_path.stat().st_size,
                "run1_sha256": left_hash,
                "run2_sha256": right_hash,
                "byte_identical": str(identical),
            }
        )
        if not identical:
            raise RuntimeError(f"两轮字节不一致：{relative}")
    return rows


def filter_table(
    source: Path,
    destination: Path,
    predicate,
    expected_count: int | None = None,
) -> list[dict[str, str]]:
    fields, rows = read_csv(source)
    selected = [row for row in rows if predicate(row)]
    if expected_count is not None and len(selected) != expected_count:
        raise RuntimeError(f"过滤行数异常：{source.name} -> {destination.name}: {len(selected)} != {expected_count}")
    write_csv(destination, fields, selected)
    return selected


def selected_routes_table(board_root: Path, route_ids: set[str], destination: Path) -> None:
    sources = [
        ("outputs/step2_audit/route_summary.csv", "route_summary.csv"),
        ("outputs/step2_audit/alternative_route_summary.csv", "alternative_route_summary.csv"),
    ]
    all_rows: list[dict[str, str]] = []
    common_fields: list[str] | None = None
    for relative, source_label in sources:
        fields, rows = read_csv(board_root / relative)
        if common_fields is None:
            common_fields = fields
        elif fields != common_fields:
            raise RuntimeError("步骤2路线摘要表头不一致。")
        for row in rows:
            if row["route_id"] in route_ids:
                all_rows.append({"source_table": source_label, **row})
    found = {row["route_id"] for row in all_rows}
    if found != route_ids:
        raise RuntimeError(f"步骤2路线集合异常：{sorted(found)} != {sorted(route_ids)}")
    write_csv(destination, ["source_table", *(common_fields or [])], all_rows)


def copy_figures_and_visuals(board_root: Path, package_root: Path, stems: list[str], object_id: str) -> None:
    run_root = board_root / "outputs/step6_history_comparison_run1"
    validation_root = board_root / "outputs/step6_history_comparison_validation"
    for stem in stems:
        for suffix in (".pdf", ".png"):
            copy_file(run_root / "figures" / f"{stem}{suffix}", package_root / "figures" / f"{stem}{suffix}")
        copy_file(
            validation_root / "rendered_pdf_review" / f"{stem}.png",
            package_root / "visual" / "rendered_pdf_review" / f"{stem}.png",
        )
    selected_stems = set(stems)
    filter_table(
        validation_root / "figure_quality.csv",
        package_root / "visual" / f"{object_id}_图件质量.csv",
        lambda row: row["stem"] in selected_stems,
        len(stems),
    )
    filter_table(
        validation_root / "manual_visual_review.csv",
        package_root / "visual" / f"{object_id}_人工视觉记录.csv",
        lambda row: Path(row["figure_pdf"]).stem in selected_stems,
        len(stems),
    )


def copy_common_logs(board_root: Path, package_root: Path) -> None:
    mappings = [
        ("outputs/step6_history_comparison_run1/run_summary.json", "logs/步骤6运行摘要.json"),
        ("outputs/step6_history_comparison_validation/validation_summary.json", "logs/步骤6独立验证摘要.json"),
        ("outputs/step6_history_comparison_validation/repeatability.csv", "logs/两轮重复性.csv"),
    ]
    for source, destination in mappings:
        copy_file(board_root / source, package_root / destination)


def copy_cb_failure_logs(board_root: Path, package_root: Path, route_id: str) -> None:
    source_log_root = board_root / "logs/step2_runs" / route_id / "original_mlx/rep02"
    source_metadata_root = board_root / "outputs/step2_runs" / route_id / "original_mlx/rep02/metadata"
    destination_root = package_root / "logs/Craig-Bampton主路线原样失败"
    for name in ("error_report.txt", "matlab_command.txt", "matlab_diary.log", "shell_stdout_stderr.log"):
        copy_file(source_log_root / name, destination_root / name)
    for name in ("process_exit.json", "run_config.json", "run_status.json"):
        copy_file(source_metadata_root / name, destination_root / name)


def common_shared_sources(board_root: Path, object_id: str, route_ids: set[str]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []

    def add(relative: str, step: str, role: str, note: str) -> None:
        path = board_root / relative
        assert_regular_file(path)
        rows.append(
            {
                "object_id": object_id,
                "central_relative_path": relative.replace("\\", "/"),
                "size_bytes": str(path.stat().st_size),
                "sha256": sha256_file(path),
                "source_step": step,
                "role": role,
                "copy_policy": "SHARED_HASH_BOUND_REFERENCE",
                "scope_note": note,
            }
        )

    fixed = [
        ("input/input_manifest.csv", "STEP1", "frozen_input_ledger", "板块20冻结输入权威清单"),
        ("input/theory/梁禹手稿.pdf", "STEP1", "thesis_frozen_copy", "论文权威冻结副本，不在对象包重复复制"),
        ("input/theory/manuscript_0824.tex", "STEP1", "manuscript_frozen_copy", "小论文公式源冻结副本"),
        ("report/板块20_最小步骤1_输入冻结与合同验收.md", "STEP1", "step_report", "输入冻结与合同验收"),
        ("report/板块20_公式语义审计_草稿.md", "STEP3", "formula_semantics_report", "公式与代码语义分流记录"),
        ("outputs/step2_audit/route_summary.csv", "STEP2", "author_route_terminal_status", "六份作者主路线终态"),
        ("outputs/step2_audit/alternative_route_summary.csv", "STEP2", "alternative_route_terminal_status", "替代路线终态，不替代主路线"),
        ("outputs/step4_audit/route_grid_summary.csv", "STEP4", "continuous_rho_grid_summary", "连续rho网格摘要"),
        ("outputs/step4_audit/postcheck.json", "STEP4", "step4_independent_postcheck", "步骤4独立后检查"),
        ("outputs/step5_fullq_svd_candidate_audit_v5_full/v5_full_validator_full_postcheck_report.md", "STEP5", "step5_final_report", "步骤5全网格独立交叉验证报告"),
        ("outputs/step5_fullq_svd_candidate_audit_v5_full/v5_full_validator_full_postcheck_route_summary.csv", "STEP5", "step5_route_summary", "步骤5全路线独立摘要"),
        ("outputs/step5_fullq_svd_candidate_audit_v5_full/v5_full_validator_full_postcheck_point_comparison.csv", "STEP5", "step5_point_comparison", "步骤5逐点独立对比，大表共享引用"),
        ("outputs/step6_history_comparison_run1/artifact_manifest.csv", "STEP6", "step6_run_manifest", "步骤6运行1封存清单"),
        ("outputs/step6_history_comparison_run1/report.md", "STEP6", "step6_report", "历史掩膜逐点比较报告"),
        ("outputs/step6_history_comparison_run1/run_summary.json", "STEP6", "step6_run_summary", "执行管线摘要，不能替代科学对象门"),
        ("outputs/step6_history_comparison_run1/tables/pointwise_comparison.csv", "STEP6", "step6_pointwise_authority", "包内仅保存对象过滤子集"),
        ("outputs/step6_history_comparison_run1/tables/claim_C05_C07.csv", "STEP6", "claim_adjudication_authority", "C05/C07声明与范围裁决"),
        ("outputs/step6_history_comparison_validation/artifact_manifest.csv", "STEP6", "step6_validation_manifest", "步骤6独立验收封存清单"),
        ("outputs/step6_history_comparison_validation/validation_summary.json", "STEP6", "step6_validation_summary", "64/64执行证据检查摘要"),
        ("outputs/step6_history_comparison_validation/validation_checks.csv", "STEP6", "step6_validation_checks", "独立验收逐项结果"),
        ("outputs/step6_history_comparison_validation/protected_hashes.csv", "STEP6", "protected_source_hashes", "163项保护源复核"),
        ("code/board20_step6_history_comparison_contract.json", "STEP6", "step6_contract", "步骤6冻结判据"),
        ("code/analyze_board20_step6_history_comparison.py", "STEP6", "step6_generator", "步骤6生成器"),
        ("code/validate_board20_step6_history_comparison.py", "STEP6", "step6_validator", "步骤6独立验收器"),
        ("code/board20_step6_fs_protocol.py", "STEP6", "filesystem_protocol", "固定根与文件系统安全协议"),
        ("code/reset_board20_step6_clean_probe.py", "STEP6", "clean_probe_reset", "清洁探针恢复入口"),
        ("code/test_board20_step6_fs_protocol.py", "STEP6", "filesystem_protocol_tests", "8/8协议测试入口"),
        ("code/board20_step7_publication_contract.json", "STEP7", "publication_contract", "对象发布与索引裁决合同"),
    ]
    for args in fixed:
        add(*args)

    if object_id == "F4-4":
        historical_inputs = [
            "input/historical_plotting/作者绘图目录/lqr_2.mat",
            "input/plotting_baseline/第4章_缩聚对试验稳定性的影响/原始来源副本/第一类划分最终绘图数据_lqr_2.mat",
        ]
    elif object_id == "F4-5":
        historical_inputs = [
            "input/historical_plotting/作者绘图目录/lqr_3.mat",
            "input/plotting_baseline/第4章_缩聚对试验稳定性的影响/原始来源副本/第二类划分最终绘图数据_lqr_3.mat",
        ]
    else:
        historical_inputs = [
            "input/historical_plotting/作者绘图目录/lqr_2.mat",
            "input/historical_plotting/作者绘图目录/lqr_3.mat",
            "input/plotting_baseline/第4章_缩聚对试验稳定性的影响/原始来源副本/第一类划分最终绘图数据_lqr_2.mat",
            "input/plotting_baseline/第4章_缩聚对试验稳定性的影响/原始来源副本/第二类划分最终绘图数据_lqr_3.mat",
        ]
    for relative in historical_inputs:
        add(relative, "STEP1", "historical_plotting_input", "历史掩膜只承担绘图级/历史值身份")

    fields, grid_rows = read_csv(board_root / "outputs/step4_audit/route_grid_summary.csv")
    if "route_id" not in fields or "mat_relpath" not in fields:
        raise RuntimeError("步骤4摘要缺少route_id或mat_relpath。")
    grid_paths = sorted({row["mat_relpath"] for row in grid_rows if row["route_id"] in route_ids})
    for relative in grid_paths:
        add(relative, "STEP4", "large_continuous_rho_grid", "大型网格不复制，仅中央哈希绑定")
    return rows


def build_shared_manifest(board_root: Path, package_root: Path, object_id: str, route_ids: set[str]) -> None:
    rows = common_shared_sources(board_root, object_id, route_ids)
    if len({row["central_relative_path"] for row in rows}) != len(rows):
        raise RuntimeError(f"共享证据路径重复：{object_id}")
    write_csv(package_root / "shared_evidence_manifest.csv", SHARED_MANIFEST_FIELDS, rows)


def figure_readme(spec: dict[str, Any], division_label: str) -> str:
    object_id = spec["object_id"]
    mismatch = "/".join(str(value) for value in spec["expected_mask_mismatch"].values())
    extra = (
        "第一类Guyan替代路线仍错配1037点，只是一个明确失败的替代候选，不能替换缺失或错配的主路线。"
        if object_id == "F4-4"
        else "第二类Original/Guyan候选有3个孔洞列、29个孔洞格和2个四邻域分量；轴截距必须停在原点连续前缀第6步（5.859375 ms），不能跨孔洞取第16步。两标签非身份载荷相同只证明文件重复，不证明理论等价；共同网格外1至28明确不是rho。"
    )
    return f"""# {spec['paper_name']}：失败证据包

## 人话结论

本对象**没有达到计算级复现**。历史31×67稳定掩膜和边界可以逐点重画，因此最终证据等级保留为“绘图级复现”；但三种方法只恢复2/3条主连续谱半径路线，0/3方法与历史掩膜逐点一致，Craig–Bampton主路线因作者程序缺少`MRren`而真实失败。对应正式成功目录刻意保持不存在。

{division_label}Original、主Guyan及可用替代路线的错配点数为{mismatch}。{extra}

## 计算合同

- 统一网格：`tau1=0..66`、`tau2=0..30`，步长`1/1024 s=0.9765625 ms`，共2077点。
- 连续候选稳定判据：`isfinite(rho) and rho < 1`。
- 历史MAT中的0/0.999掩膜只承担绘图级或历史值身份，不能冒充连续rho。
- 轴截距取原点连续稳定前缀最后一点，禁止跨越孔洞。
- 步骤6执行管线通过，不等于本图科学对象门通过；本图对象门为`FAIL`。

## 文件导航

- `data/`：对象门、三方法格、逐点混淆、边界和步骤2/4/5路线摘要。
- `logs/`：步骤6摘要、两轮重复性和Craig–Bampton作者主程序真实失败现场。
- `figures/`：历史绘图级复核与计算候选失败诊断的PDF/PNG原样副本。
- `visual/`：图件质量、人工视觉记录和180 dpi独立渲染。
- `shared_evidence_manifest.csv`：论文、MAT、大网格、计算器和验证器的中央哈希绑定；大型文件不重复复制。
- `artifact_manifest.csv`：本包除清单自身外全部文件的字节数与SHA-256。
- `code/复现入口.md`：从中央板块重新运行步骤6与步骤7验收的入口。

## 禁止误读

这里的“失败”表示现有作者文件身份路线不能逐点恢复论文历史掩膜，不表示图不能重画，也不表示论文一定错误。替代候选、历史掩膜和缺失路线必须分栏保留，不能择优拼成一个伪造成功对象。
"""


def conclusion_readme(spec: dict[str, Any]) -> str:
    if spec["object_id"] == "C05":
        scope = "本包评价第一类和第二类划分的临界时滞下降量。"
        result = (
            "历史第一类Original到Craig–Bampton的tau1/tau2/对角线下降量为8.7890625/4.8828125/1.953125 ms，"
            "Original到Guyan为11.71875/7.8125/4.8828125 ms；第二类对应为2.9296875/1.953125/2.9296875 ms和"
            "5.859375/2.9296875/3.90625 ms。论文的“约5 ms/接近10 ms”没有给出唯一的轴或对角线标量口径，"
            "九条声明均不得升级为计算级。"
        )
        excluded = "没有额外排除分量，但不允许从多组截距中挑选一个数字拟合论文措辞。"
    else:
        scope = "本包只评价结论C07中的临界时滞分量。"
        result = (
            "临界时滞仍只能保留为历史值：Craig–Bampton两条连续路线缺失，现有候选掩膜也不匹配历史掩膜，"
            "因而没有形成唯一“降低5 ms以上”的计算级闭合。"
        )
        excluded = (
            "频率区间和响应幅值明确记为`NOT_EVALUATED`，不在板块20稳定域范围；"
            "不得从板块18或19顺手填入并升级C07整体。"
        )
    return f"""# {spec['paper_name']}：失败证据包

## 人话结论

本对象**没有达到计算级复现**，整体证据等级保持“历史值”，正式成功目录刻意保持不存在。{scope}

{result}

## 范围边界

{excluded}

## 截距与证据合同

- 统一网格31×67，时滞步长0.9765625 ms。
- 轴截距只取原点连续稳定前缀最后一点，禁止跨孔洞；对角线也按同一离散网格定义。
- 历史0/0.999掩膜只承担绘图级派生值；连续rho候选必须满足`isfinite(rho) and rho < 1`。
- 步骤6执行检查通过不等于结论科学门通过；`eligible_for_calculation_level_upgrade`必须全部为`False`。

## 文件导航

- `data/`：声明裁决、两图对象门、六个方法目标格、稳定域指标和混淆矩阵。
- `figures/`：图4-4/4-5历史边界与候选失败诊断的原样PDF/PNG副本。
- `visual/`：图件质量、人工视觉记录与独立渲染。
- `logs/`：步骤6运行、独立验证和两轮重复性摘要。
- `shared_evidence_manifest.csv`：论文、MAT、大网格、代码与验证器的中央哈希绑定。
- `artifact_manifest.csv`：本包除清单自身外全部文件的字节数与SHA-256。
- `code/复现入口.md`：中央可重跑入口。

## 禁止误读

“历史值”表示论文陈述已定位但完整计算路线尚未闭合；不能把历史掩膜派生量写成连续rho计算结果，也不能挑选最接近论文措辞的一条轴线充当唯一口径。
"""


def rerun_entry(board_root: Path) -> str:
    return f"""# 复现入口

所有命令都在唯一中央板块目录执行：

`{board_root.as_posix()}`

PowerShell先设置中文输出：

`$env:PYTHONIOENCODING = 'utf-8'`

依次运行：

1. `D:/Software/python/python.exe code/test_board20_step6_fs_protocol.py`
2. `D:/Software/python/python.exe code/reset_board20_step6_clean_probe.py --execute`
3. `D:/Software/python/python.exe code/analyze_board20_step6_history_comparison.py --run-id run1`
4. `D:/Software/python/python.exe code/analyze_board20_step6_history_comparison.py --run-id run2`
5. `D:/Software/python/python.exe code/validate_board20_step6_history_comparison.py`
6. `D:/Software/python/python.exe code/publish_board20_step7_failure_packages.py --verify-existing --revision reseal`
7. `D:/Software/python/python.exe code/validate_board20_step7_final.py`

步骤1至5的冻结合同、运行报告和大网格由`shared_evidence_manifest.csv`逐项绑定。本对象包不承担计算源身份，不得反向覆盖`input/`或中央`outputs/`；历史掩膜、计算候选和真实失败日志必须保持证据分层。
"""


def build_figure_package(board_root: Path, package_root: Path, spec: dict[str, Any]) -> None:
    object_id = spec["object_id"]
    division = "div1" if object_id == "F4-4" else "div2"
    route_ids = set(spec["route_ids"])
    tables = board_root / "outputs/step6_history_comparison_run1/tables"
    data_root = package_root / "data"
    table_specs = [
        ("figure_status.csv", f"{object_id}_对象门.csv", 1),
        ("target_cell_status.csv", f"{object_id}_三方法目标格.csv", 3),
        ("route_eligibility.csv", f"{object_id}_路线资格.csv", 4 if object_id == "F4-4" else 3),
        ("confusion_matrix.csv", f"{object_id}_混淆矩阵.csv", 4 if object_id == "F4-4" else 3),
        ("stability_metrics.csv", f"{object_id}_稳定域指标.csv", 6 if object_id == "F4-4" else 5),
        ("pointwise_comparison.csv", f"{object_id}_逐点比较.csv", 6231 if object_id == "F4-4" else 4154),
        ("boundary_by_source.csv", f"{object_id}_来源边界.csv", 402 if object_id == "F4-4" else 335),
        ("boundary_difference.csv", f"{object_id}_候选减历史边界.csv", 201 if object_id == "F4-4" else 134),
    ]
    for source_name, destination_name, count in table_specs:
        filter_table(
            tables / source_name,
            data_root / destination_name,
            lambda row, oid=object_id: row.get("figure_id") == oid,
            count,
        )
    filter_table(
        board_root / "outputs/step6_history_comparison_run1/figure_style_manifest.csv",
        data_root / f"{object_id}_绘图样式与证据分层.csv",
        lambda row: row["figure_id"] == object_id,
        7 if object_id == "F4-4" else 6,
    )
    selected_routes_table(board_root, route_ids, data_root / f"{object_id}_步骤2作者路线终态.csv")
    filter_table(
        board_root / "outputs/step4_audit/route_grid_summary.csv",
        data_root / f"{object_id}_步骤4连续rho网格摘要.csv",
        lambda row: row["route_id"] in route_ids,
        6 if object_id == "F4-4" else 4,
    )
    filter_table(
        board_root / "outputs/step5_fullq_svd_candidate_audit_v5_full/v5_full_validator_full_postcheck_route_summary.csv",
        data_root / f"{object_id}_步骤5独立交叉验证摘要.csv",
        lambda row: row["route_id"] in route_ids,
        3 if object_id == "F4-4" else 2,
    )
    if object_id == "F4-5":
        copy_file(tables / "div2_payload_relation_audit.csv", data_root / "第二类两标签载荷关系.csv")
        copy_file(tables / "extension_summary.csv", data_root / "第二类共同网格外序列摘要.csv")
        copy_file(tables / "extension_1_to_28_audit.csv", data_root / "第二类共同网格外1至28逐点.csv")
    stems = [
        f"图4-{4 if object_id == 'F4-4' else 5}_历史最终掩膜边界_绘图级复核",
        f"图4-{4 if object_id == 'F4-4' else 5}_作者文件身份计算候选_失败诊断",
    ]
    copy_figures_and_visuals(board_root, package_root, stems, object_id)
    copy_common_logs(board_root, package_root)
    copy_cb_failure_logs(board_root, package_root, "main_cb_div1" if division == "div1" else "main_cb_div2")
    write_text(package_root / "README.md", figure_readme(spec, "第一类" if division == "div1" else "第二类"))
    write_text(package_root / "code/复现入口.md", rerun_entry(board_root))
    build_shared_manifest(board_root, package_root, object_id, route_ids)


def build_conclusion_package(board_root: Path, package_root: Path, spec: dict[str, Any]) -> None:
    object_id = spec["object_id"]
    tables = board_root / "outputs/step6_history_comparison_run1/tables"
    data_root = package_root / "data"
    if object_id == "C05":
        filter_table(
            tables / "claim_C05_C07.csv",
            data_root / "C05_临界时滞声明与裁决.csv",
            lambda row: "C05" in row["claim_ids"],
            9,
        )
    else:
        fields, rows = read_csv(tables / "claim_C05_C07.csv")
        if len(rows) != 10:
            raise RuntimeError(f"C07声明表应为10行，实际{len(rows)}行。")
        write_csv(data_root / "C07_临界时滞声明与未评价项.csv", fields, rows)
        scope_fields = ["component", "status", "evidence_level", "evaluated_in_board20", "scope_note"]
        scope_rows = [
            {
                "component": "critical_delay",
                "status": "EVALUATED_PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY",
                "evidence_level": "历史值",
                "evaluated_in_board20": "True",
                "scope_note": "历史掩膜派生量已审计但计算路线未闭合",
            },
            {
                "component": "frequency_bands",
                "status": "NOT_EVALUATED",
                "evidence_level": "历史值",
                "evaluated_in_board20": "False",
                "scope_note": "不在板块20稳定域范围",
            },
            {
                "component": "response_amplitude_errors",
                "status": "NOT_EVALUATED",
                "evidence_level": "历史值",
                "evaluated_in_board20": "False",
                "scope_note": "不在板块20稳定域范围",
            },
        ]
        write_csv(data_root / "C07_组件范围裁决.csv", scope_fields, scope_rows)
    shared_tables = [
        ("figure_status.csv", f"{object_id}_两图对象门.csv", 2),
        ("target_cell_status.csv", f"{object_id}_六方法目标格.csv", 6),
        ("stability_metrics.csv", f"{object_id}_稳定域指标.csv", 11),
        ("confusion_matrix.csv", f"{object_id}_混淆矩阵.csv", 7),
    ]
    for source_name, destination_name, count in shared_tables:
        fields, rows = read_csv(tables / source_name)
        if len(rows) != count:
            raise RuntimeError(f"{source_name}行数异常：{len(rows)} != {count}")
        write_csv(data_root / destination_name, fields, rows)
    stems = [
        "图4-4_历史最终掩膜边界_绘图级复核",
        "图4-4_作者文件身份计算候选_失败诊断",
        "图4-5_历史最终掩膜边界_绘图级复核",
        "图4-5_作者文件身份计算候选_失败诊断",
    ]
    copy_figures_and_visuals(board_root, package_root, stems, object_id)
    copy_common_logs(board_root, package_root)
    write_text(package_root / "README.md", conclusion_readme(spec))
    write_text(package_root / "code/复现入口.md", rerun_entry(board_root))
    route_ids = {
        "main_ori_div1",
        "main_cb_div1",
        "main_guyan_div1",
        "alt_guyan_div1_stable_full_ps3",
        "main_ori_div2",
        "main_cb_div2",
        "main_guyan_div2",
    }
    build_shared_manifest(board_root, package_root, object_id, route_ids)


def build_package(board_root: Path, package_root: Path, spec: dict[str, Any], contract: dict[str, Any]) -> None:
    if package_root.exists():
        raise FileExistsError(f"构建目标必须不存在：{package_root}")
    package_root.mkdir(parents=True)
    if spec["object_id"].startswith("F4-"):
        build_figure_package(board_root, package_root, spec)
    else:
        build_conclusion_package(board_root, package_root, spec)
    summary: dict[str, Any] = {
        "schema_version": "BOARD20_STEP7_FAILURE_PACKAGE_V1",
        "object_id": spec["object_id"],
        "paper_name": spec["paper_name"],
        "object_type": spec["object_type"],
        "evaluated_scope": spec["evaluated_scope"],
        "excluded_scope": spec["excluded_scope"],
        "target_evidence_level": spec["target_evidence_level"],
        "final_evidence_level": spec["final_evidence_level"],
        "calculation_level_gate_pass": False,
        "formal_success_directory_allowed": False,
        "formal_success_directory_exists": False,
        "failure_package_relative_path": f"test/00_失败尝试与候选路线/{spec['package_name']}",
        "central_board_relative_path": f"test/00_失败尝试与候选路线/{BOARD_NAME}",
        "step6_run_manifest_sha256": contract["sealed_hashes"]["step6_run1_manifest_sha256"],
        "step6_validation_manifest_sha256": contract["sealed_hashes"]["step6_validation_manifest_sha256"],
        "status": "FAILURE_EVIDENCE_PACKAGED",
    }
    if spec["object_id"].startswith("F4-"):
        summary.update(
            {
                "method_cell_count": spec["method_cell_count"],
                "primary_continuous_rho_cell_count": spec["primary_continuous_rho_cell_count"],
                "exact_mask_match_cell_count": spec["exact_mask_match_cell_count"],
                "expected_mask_mismatch": spec["expected_mask_mismatch"],
            }
        )
    elif spec["object_id"] == "C05":
        summary["critical_delay_component_review_level"] = "PLOTTING_LEVEL_HISTORICAL_MASK_DERIVATION"
    else:
        summary.update(
            {
                "evaluated_components": ["critical_delay"],
                "not_evaluated_components": ["frequency_bands", "response_amplitude_errors"],
                "frequency_amplitude_status": "NOT_EVALUATED",
            }
        )
    write_json(package_root / "package_summary.json", summary)
    manifest = build_artifact_manifest(package_root)
    if len(manifest) < 20:
        raise RuntimeError(f"证据包文件过少：{spec['object_id']}只有{len(manifest)}件。")


def build_run(board_root: Path, output_root: Path, contract: dict[str, Any]) -> None:
    expected_parent = board_root / "outputs"
    assert_within(output_root, expected_parent)
    if output_root.exists():
        raise FileExistsError(f"拒绝覆盖既有构建轮次：{output_root}")
    output_root.mkdir(parents=True)
    packages_root = output_root / "packages"
    packages_root.mkdir()
    package_summaries: list[dict[str, Any]] = []
    for spec in contract["objects"]:
        package_root = packages_root / spec["package_name"]
        build_package(board_root, package_root, spec, contract)
        package_summaries.append(
            {
                "object_id": spec["object_id"],
                "package_name": spec["package_name"],
                "final_evidence_level": spec["final_evidence_level"],
                "status": "FAILURE_EVIDENCE_PACKAGED",
            }
        )
    write_json(
        output_root / "build_summary.json",
        {
            "schema_version": "BOARD20_STEP7_BUILD_SUMMARY_V1",
            "package_count": len(package_summaries),
            "formal_success_directory_count": 0,
            "packages": package_summaries,
            "status": "PASS",
        },
    )
    rows: list[dict[str, Any]] = []
    for path in sorted(output_root.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if path.is_file() and path.name != "artifact_manifest.csv":
            relative = path.relative_to(output_root).as_posix()
            rows.append(
                {
                    "relative_path": relative,
                    "size_bytes": path.stat().st_size,
                    "sha256": sha256_file(path),
                    "role": "package_build_artifact",
                }
            )
    write_csv(output_root / "artifact_manifest.csv", PACKAGE_MANIFEST_FIELDS, rows)


def verify_index_pre_state(board_root: Path, project_root: Path, contract: dict[str, Any]) -> None:
    pre = board_root / contract["index_contract"]["pre_snapshot_relative_path"]
    live = project_root / contract["index_contract"]["live_relative_path_from_project"]
    assert_regular_file(pre)
    assert_regular_file(live)
    if pre.read_bytes() != live.read_bytes():
        raise RuntimeError("发布前总索引已偏离板块20前快照；拒绝隐式覆盖。")


def verify_sealed_hashes(board_root: Path, contract: dict[str, Any]) -> None:
    bindings = {
        "step6_run1_manifest_sha256": "outputs/step6_history_comparison_run1/artifact_manifest.csv",
        "step6_run2_manifest_sha256": "outputs/step6_history_comparison_run2/artifact_manifest.csv",
        "step6_validation_manifest_sha256": "outputs/step6_history_comparison_validation/artifact_manifest.csv",
        "step6_validation_summary_sha256": "outputs/step6_history_comparison_validation/validation_summary.json",
        "step6_generator_sha256": "code/analyze_board20_step6_history_comparison.py",
        "step6_validator_sha256": "code/validate_board20_step6_history_comparison.py",
        "step6_contract_sha256": "code/board20_step6_history_comparison_contract.json",
        "thesis_sha256": "input/theory/梁禹手稿.pdf",
        "manuscript_sha256": "input/theory/manuscript_0824.tex",
    }
    for key, relative in bindings.items():
        path = board_root / relative
        actual = sha256_file(path)
        expected = contract["sealed_hashes"][key]
        if actual != expected:
            raise RuntimeError(f"封存哈希改变：{relative}: {actual} != {expected}")
    receipt = board_root / "logs/step6_history_comparison/clean_probe_record.json"
    if sha256_file(receipt) != contract["sealed_hashes"]["step6_clean_probe_receipt_sha256"]:
        raise RuntimeError("步骤6清洁探针收据哈希改变。")
    receipt_payload = json.loads(receipt.read_text(encoding="utf-8"))
    if receipt_payload.get("action_id") != contract["sealed_hashes"]["step6_clean_probe_action_id"]:
        raise RuntimeError("步骤6清洁探针动作编号与步骤7合同不一致。")


def publish_packages(board_root: Path, project_root: Path, run1: Path, contract: dict[str, Any]) -> None:
    failure_root = project_root / "test/00_失败尝试与候选路线"
    test_root = project_root / "test"
    assert_within(failure_root, test_root)
    for spec in contract["objects"]:
        success = test_root / spec["package_name"]
        if success.exists():
            raise RuntimeError(f"未闭合对象不应存在正式成功目录：{success}")

    sources = {spec["package_name"]: run1 / "packages" / spec["package_name"] for spec in contract["objects"]}
    existing = [failure_root / name for name in sources if (failure_root / name).exists()]
    if existing:
        for target in existing:
            source = sources[target.name]
            compare_trees(source, target)
        if len(existing) != len(sources):
            raise RuntimeError("检测到部分发布状态；拒绝补写造成非事务状态。")
        return

    staging = Path(tempfile.mkdtemp(prefix=".board20_step7_publish_", dir=failure_root))
    assert_within(staging, failure_root)
    committed: list[Path] = []
    try:
        for name, source in sources.items():
            destination = staging / name
            shutil.copytree(source, destination, copy_function=shutil.copyfile)
            compare_trees(source, destination)
        for name in sources:
            source = staging / name
            target = failure_root / name
            if target.exists():
                raise FileExistsError(f"发布目标在提交前出现：{target}")
            os.replace(source, target)
            committed.append(target)
    except Exception:
        for target in reversed(committed):
            assert_within(target, failure_root)
            shutil.rmtree(target)
        raise
    finally:
        if staging.exists():
            assert_within(staging, failure_root)
            shutil.rmtree(staging)


def publish_reseal_packages(
    board_root: Path,
    project_root: Path,
    run1: Path,
    contract: dict[str, Any],
) -> None:
    failure_root = project_root / "test/00_失败尝试与候选路线"
    test_root = project_root / "test"
    archive_root = board_root / "outputs/step7_preprobe_published_snapshot/packages"
    initial_root = board_root / "outputs/step7_package_build_run1/packages"
    assert_within(failure_root, test_root)
    assert_within(archive_root, board_root / "outputs")
    for spec in contract["objects"]:
        success = test_root / spec["package_name"]
        if success.exists():
            raise RuntimeError(f"未闭合对象不应存在正式成功目录：{success}")

    names = [spec["package_name"] for spec in contract["objects"]]
    new_sources = {name: run1 / "packages" / name for name in names}
    current_targets = {name: failure_root / name for name in names}
    old_sources = {name: initial_root / name for name in names}

    if archive_root.exists():
        for name in names:
            compare_trees(old_sources[name], archive_root / name)
            compare_trees(new_sources[name], current_targets[name])
        return

    for name in names:
        if not current_targets[name].is_dir():
            raise RuntimeError(f"重封存前旧发布包缺失：{current_targets[name]}")
        compare_trees(old_sources[name], current_targets[name])

    staging = Path(tempfile.mkdtemp(prefix=".board20_step7_reseal_", dir=failure_root))
    assert_within(staging, failure_root)
    for name in names:
        destination = staging / name
        shutil.copytree(new_sources[name], destination, copy_function=shutil.copyfile)
        compare_trees(new_sources[name], destination)

    archive_root.mkdir(parents=True, exist_ok=False)
    moved_old: list[str] = []
    committed_new: list[str] = []
    try:
        for name in names:
            os.replace(current_targets[name], archive_root / name)
            moved_old.append(name)
        for name in names:
            os.replace(staging / name, current_targets[name])
            committed_new.append(name)
    except Exception:
        for name in reversed(committed_new):
            if current_targets[name].exists():
                os.replace(current_targets[name], staging / f"{name}.failed_new")
        for name in reversed(moved_old):
            if (archive_root / name).exists() and not current_targets[name].exists():
                os.replace(archive_root / name, current_targets[name])
        raise
    finally:
        if staging.exists() and not any(staging.iterdir()):
            staging.rmdir()


def verify_existing(
    board_root: Path,
    project_root: Path,
    contract: dict[str, Any],
    run1: Path,
    run2: Path,
    published_root: Path,
) -> dict[str, Any]:
    rows = compare_trees(run1, run2)
    test_root = project_root / "test"
    for spec in contract["objects"]:
        success = test_root / spec["package_name"]
        failure = published_root / spec["package_name"]
        if success.exists():
            raise RuntimeError(f"正式成功目录意外存在：{success}")
        compare_trees(run1 / "packages" / spec["package_name"], failure)
    return {
        "build_file_count": len(rows),
        "byte_identical_count": sum(row["byte_identical"] == "True" for row in rows),
        "package_count": len(contract["objects"]),
        "formal_success_directory_count": 0,
        "status": "PASS",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="板块20最小步骤7失败证据包可重复构建与事务发布")
    parser.add_argument("--verify-existing", action="store_true", help="只验证两轮构建与已发布目录，不写包")
    parser.add_argument(
        "--revision",
        choices=["initial", "reseal"],
        default="initial",
        help="initial保留首次封存；reseal绑定发布后真实清洁探针动作并保留首次发布快照",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    board_root = find_board_root(Path(__file__).resolve().parent)
    project_root = board_root.parents[2].resolve()
    contract_path = board_root / "code" / CONTRACT_NAME
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    if contract["schema_version"] != "BOARD20_STEP7_PUBLICATION_CONTRACT_V1":
        raise RuntimeError("步骤7发布合同版本不匹配。")
    verify_sealed_hashes(board_root, contract)

    if args.revision == "initial":
        run1 = board_root / "outputs/step7_package_build_run1"
        run2 = board_root / "outputs/step7_package_build_run2"
        repeatability_path = board_root / "outputs/step7_package_repeatability.csv"
        receipt_path = board_root / "outputs/step7_publication_receipt.json"
        archive = board_root / "outputs/step7_preprobe_published_snapshot/packages"
        published_root = archive if archive.exists() else project_root / "test/00_失败尝试与候选路线"
    else:
        run1 = board_root / "outputs/step7_package_reseal_run1"
        run2 = board_root / "outputs/step7_package_reseal_run2"
        repeatability_path = board_root / "outputs/step7_package_reseal_repeatability.csv"
        receipt_path = board_root / "outputs/step7_package_reseal_receipt.json"
        published_root = project_root / "test/00_失败尝试与候选路线"

    if args.verify_existing:
        result = verify_existing(board_root, project_root, contract, run1, run2, published_root)
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        return

    if args.revision == "initial":
        verify_index_pre_state(board_root, project_root, contract)
    build_run(board_root, run1, contract)
    build_run(board_root, run2, contract)
    repeatability = compare_trees(run1, run2)
    write_csv(
        repeatability_path,
        [
            "relative_path",
            "run1_size_bytes",
            "run2_size_bytes",
            "run1_sha256",
            "run2_sha256",
            "byte_identical",
        ],
        repeatability,
    )
    if args.revision == "initial":
        publish_packages(board_root, project_root, run1, contract)
    else:
        publish_reseal_packages(board_root, project_root, run1, contract)
    result = verify_existing(board_root, project_root, contract, run1, run2, published_root)
    write_json(receipt_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

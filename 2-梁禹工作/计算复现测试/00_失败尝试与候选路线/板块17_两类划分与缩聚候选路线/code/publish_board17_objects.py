from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[4]
OUTPUTS = CANDIDATE / "outputs"
LOGS = CANDIDATE / "logs"

SUCCESS_ROOT = PROJECT_ROOT / "test" / "00_上游模型身份证"
FAILURE_ROOT = PROJECT_ROOT / "test" / "00_失败尝试与候选路线"

U03_NAME = "U03_第一类物理_数值子结构划分"
U04_NAME = "U04_第二类物理_数值子结构划分"
U05_NAME = "U05_Guyan历史单侧实现、论文公式与标准双侧合同投影"
U06_NAME = "U06_Craig--Bampton三固定界面模态的实际实现"

SUCCESS_U05 = SUCCESS_ROOT / U05_NAME
SUCCESS_U06 = SUCCESS_ROOT / U06_NAME
FAILURE_U03 = FAILURE_ROOT / U03_NAME
FAILURE_U04 = FAILURE_ROOT / U04_NAME
FAILURE_U05 = FAILURE_ROOT / U05_NAME
FAILURE_U06 = FAILURE_ROOT / U06_NAME

LOCAL_DOF_CSV = OUTPUTS / "local_dof_sets.csv"
ADJUDICATION_CSV = OUTPUTS / "object_adjudication.csv"
PUBLISH_HASHES_CSV = OUTPUTS / "publish_artifact_hashes.csv"
LOG_PATH = LOGS / "publish_board17_objects.log"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"拒绝写空CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def relative(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()


def copy_artifact(source_relative: str, package: Path, target_relative: str) -> Path:
    source = CANDIDATE / source_relative
    target = package / target_relative
    if not source.is_file():
        raise FileNotFoundError(f"发布源不存在: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    if sha256(source) != sha256(target):
        raise RuntimeError(f"发布复制哈希不一致: {source} -> {target}")
    return target


def write_readme(package: Path, text: str) -> Path:
    package.mkdir(parents=True, exist_ok=True)
    readme = package / "README.md"
    readme.write_text(text.rstrip() + "\n", encoding="utf-8")
    return readme


def package_manifest(package: Path) -> Path:
    rows: list[dict[str, Any]] = []
    manifest = package / "package_manifest.csv"
    for path in sorted(package.rglob("*"), key=lambda item: item.as_posix()):
        if not path.is_file() or path == manifest or "__pycache__" in path.parts:
            continue
        rows.append(
            {
                "relative_path": path.relative_to(package).as_posix(),
                "size_bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    write_csv(manifest, rows)
    return manifest


def publish_package(
    package: Path,
    readme_text: str,
    mappings: list[tuple[str, str]],
) -> list[Path]:
    published = [write_readme(package, readme_text)]
    for source_relative, target_relative in mappings:
        published.append(copy_artifact(source_relative, package, target_relative))
    published.append(package_manifest(package))
    return published


def main() -> int:
    OUTPUTS.mkdir(parents=True, exist_ok=True)
    LOGS.mkdir(parents=True, exist_ok=True)

    for forbidden in (SUCCESS_ROOT / U03_NAME, SUCCESS_ROOT / U04_NAME):
        if forbidden.exists():
            raise RuntimeError(f"U03/U04未通过整体门槛，拒绝保留成功目录: {forbidden}")

    local_rows = [
        {
            "division": 1,
            "route_identity": "论文局部物理子结构",
            "substructure": "physical",
            "retained_dofs": "[1,6]",
            "condensed_dofs": "[2,3,7,8]",
            "shared_interface_dofs": "[1,6]",
            "source": "梁禹手稿式(3-1); PDmonicanshu2.m",
            "evidence_label": "计算级复现（仅局部物理子结构）",
            "assembly_status": "待决定",
        },
        {
            "division": 1,
            "route_identity": "论文局部数值子结构",
            "substructure": "numerical",
            "retained_dofs": "[1,4,6,9,11,14]",
            "condensed_dofs": "[3,5,7,8,10,12,13,15]",
            "shared_interface_dofs": "[1,6]",
            "source": "梁禹手稿式(3-7); New_Ns2.m候选",
            "evidence_label": "历史集合；计算未闭合",
            "assembly_status": "待决定",
        },
        {
            "division": 1,
            "route_identity": "当前响应生成器完整15自由度组合划分",
            "substructure": "combined_full_model",
            "retained_dofs": "[1,6,11,4,9,14]",
            "condensed_dofs": "[2,3,5,7,8,10,12,13,15]",
            "shared_interface_dofs": "不适用（无P/N重复坐标）",
            "source": "regenerate_chapter3_data.m:248-250",
            "evidence_label": "计算级复现",
            "assembly_status": "PASS",
        },
        {
            "division": 2,
            "route_identity": "论文局部物理子结构",
            "substructure": "physical",
            "retained_dofs": "[1,11]",
            "condensed_dofs": "[2,3,6,7,8,12,13]",
            "shared_interface_dofs": "[1,6,11]",
            "source": "梁禹手稿式(3-9); PDmonicanshu3.m",
            "evidence_label": "计算级复现（仅局部物理子结构）",
            "assembly_status": "待决定",
        },
        {
            "division": 2,
            "route_identity": "论文局部数值子结构",
            "substructure": "numerical",
            "retained_dofs": "[1,4,6,9,11,14]",
            "condensed_dofs": "[3,5,8,10,13,15]",
            "shared_interface_dofs": "[1,6,11]",
            "source": "梁禹手稿式(3-10); New_Ns3.m候选",
            "evidence_label": "历史集合；计算未闭合",
            "assembly_status": "待决定",
        },
        {
            "division": 2,
            "route_identity": "当前响应生成器完整15自由度组合划分",
            "substructure": "combined_full_model",
            "retained_dofs": "[1,11,4,9,14]",
            "condensed_dofs": "[6,2,3,5,7,8,10,12,13,15]",
            "shared_interface_dofs": "不适用（无P/N重复坐标）",
            "source": "regenerate_chapter3_data.m:252-254",
            "evidence_label": "计算级复现",
            "assembly_status": "PASS",
        },
    ]
    write_csv(LOCAL_DOF_CSV, local_rows)

    adjudication_rows = [
        {
            "object_id": "U03",
            "object_name": "第一类物理/数值子结构划分",
            "successful_route": "当前完整15自由度组合划分、6维Guyan、9维CB及恢复接口",
            "evidence_level": "部分计算级复现",
            "overall_status": "待决定",
            "success_directory_created": 0,
            "failure_directory_created": 1,
            "blocking_route": "局部数值侧缩聚、P/N散布组装与12维矩阵未闭合",
        },
        {
            "object_id": "U04",
            "object_name": "第二类物理/数值子结构划分",
            "successful_route": "当前完整15自由度组合划分、5维Guyan、8维CB及psi6恢复接口",
            "evidence_level": "部分计算级复现",
            "overall_status": "待决定",
            "success_directory_created": 0,
            "failure_directory_created": 1,
            "blocking_route": "局部数值侧缩聚、P/N散布组装与12维矩阵未闭合",
        },
        {
            "object_id": "U05",
            "object_name": "Guyan历史单侧实现、论文公式与标准双侧合同投影",
            "successful_route": "历史单边、论文/标准合同投影均重建并交叉验证",
            "evidence_level": "计算级复现",
            "overall_status": "PASS_WITH_RECORDED_FORMULA_CONFLICT",
            "success_directory_created": 1,
            "failure_directory_created": 1,
            "blocking_route": "无；历史与标准质量/阻尼不同是保留冲突，不是缺失",
        },
        {
            "object_id": "U06",
            "object_name": "Craig--Bampton三固定界面模态的实际实现",
            "successful_route": "当前完整模型第一类9维、第二类8维，均保留3个固定界面模态",
            "evidence_level": "计算级复现",
            "overall_status": "PASS_CURRENT_9_8_ROUTE;12D_PENDING",
            "success_directory_created": 1,
            "failure_directory_created": 1,
            "blocking_route": "论文分子结构12维组装未闭合，单独保留为失败/待决定分支",
        },
    ]
    write_csv(ADJUDICATION_CSV, adjudication_rows)

    common_global = [
        ("code/run_board17_global_routes.m", "code/run_board17_global_routes.m"),
        ("code/independent_recompute_global_routes.py", "code/independent_recompute_global_routes.py"),
        ("code/verify_board17_cross_language.py", "code/verify_board17_cross_language.py"),
        ("outputs/global_routes_matlab.mat", "data/global_routes_matlab.mat"),
        ("outputs/independent_global_routes_python.mat", "data/independent_global_routes_python.mat"),
        ("outputs/global_matrix_audit.csv", "data/global_matrix_audit.csv"),
        ("outputs/global_modal_frequencies.csv", "data/global_modal_frequencies.csv"),
        ("outputs/independent_global_matrix_checks.csv", "data/independent_global_matrix_checks.csv"),
        ("outputs/independent_global_modal_results.csv", "data/independent_global_modal_results.csv"),
        ("outputs/cross_language_matrix_checks.csv", "data/cross_language_matrix_checks.csv"),
        ("outputs/cross_language_modal_comparison.csv", "data/cross_language_modal_comparison.csv"),
        ("outputs/cross_language_summary.json", "data/cross_language_summary.json"),
        ("outputs/contract_conflicts.csv", "data/contract_conflicts.csv"),
        ("outputs/object_adjudication.csv", "data/object_adjudication.csv"),
    ]
    local_failure = [
        ("code/run_board17_local_candidates.m", "code/run_board17_local_candidates.m"),
        ("code/run_board17_local_candidates_audit.py", "code/run_board17_local_candidates_audit.py"),
        ("outputs/local_dof_sets.csv", "data/local_dof_sets.csv"),
        ("outputs/local_pd_reduction_summary.csv", "data/local_pd_reduction_summary.csv"),
        ("outputs/local_pd_reductions.mat", "data/local_pd_reductions.mat"),
        ("outputs/local_new_script_attempts.csv", "data/local_new_script_attempts.csv"),
        ("outputs/local_interface_dimension_audit.csv", "data/local_interface_dimension_audit.csv"),
        ("outputs/local_assembly_12d_gate.csv", "data/local_assembly_12d_gate.csv"),
        ("outputs/local_candidate_summary.json", "data/local_candidate_summary.json"),
        ("outputs/local_candidate_python_audit.json", "data/local_candidate_python_audit.json"),
        ("outputs/object_adjudication.csv", "data/object_adjudication.csv"),
    ]

    published: list[Path] = [LOCAL_DOF_CSV, ADJUDICATION_CSV]
    published += publish_package(
        SUCCESS_U05,
        """# U05 Guyan三条公式路线（计算级复现）

本包锁定当前15自由度模型上的三条身份：作者历史单边消元、论文/标准双侧合同投影、独立Python重建。两类划分的历史/标准质量矩阵相对差分别为9.977893886%和37.301270253%，阻尼差为0.951999751%和8.415963930%；刚度在数值精度内等价。差异是公式路线冲突，不被静默合并。

证据边界：本包没有运行Simulink响应，也不证明论文分子结构12维装配。`data/object_adjudication.csv` 给出对象级裁决，`data/contract_conflicts.csv` 保留公式冲突。
""",
        common_global
        + [
            ("outputs/contract_formula_crosswalk.csv", "data/contract_formula_crosswalk.csv"),
            ("outputs/global_reduced_matrix_entries.csv", "data/global_reduced_matrix_entries.csv"),
            ("outputs/independent_global_summary.json", "data/independent_global_summary.json"),
        ],
    )
    published += publish_package(
        FAILURE_U05,
        """# U05公式冲突保全包

U05整体已经达到计算级复现。本目录不是“对象失败”，而是专门保留历史单边消元与标准双侧合同投影不一致的证据，防止成功包把冲突抹去。质量和阻尼差异不应被降容差处理；两条路线均保留。
""",
        [
            ("outputs/contract_formula_crosswalk.csv", "data/contract_formula_crosswalk.csv"),
            ("outputs/contract_conflicts.csv", "data/contract_conflicts.csv"),
            ("outputs/global_matrix_audit.csv", "data/global_matrix_audit.csv"),
            ("outputs/object_adjudication.csv", "data/object_adjudication.csv"),
        ],
    )
    published += publish_package(
        SUCCESS_U06,
        """# U06 Craig--Bampton实际实现（计算级复现）

本包只把当前完整15自由度一次缩聚路线标为计算级复现：第一类变换15x9，第二类15x8，每个完整划分总共保留r=3个固定界面模态。原Live Script用`eig(Kss,Mss)`后直接取前三列，当前生成器显式按特征值升序后取前三列；实际代码没有`svds`。

论文“数值侧9维+物理侧5维-两个共享接口=12维”是另一条分子结构装配路线，未在本成功包冒充完成；其失败证据保存在对应失败包。
""",
        common_global
        + [
            ("outputs/global_dimension_gates.csv", "data/global_dimension_gates.csv"),
            ("outputs/global_recovery_matrices.csv", "data/global_recovery_matrices.csv"),
            ("outputs/global_input_projection.csv", "data/global_input_projection.csv"),
            ("outputs/contract_formula_crosswalk.csv", "data/contract_formula_crosswalk.csv"),
        ],
    )
    published += publish_package(
        FAILURE_U06,
        """# U06的12维分子结构失败分支（待决定）

当前9/8维完整模型路线已经成功；本目录只保留论文12维候选未闭合的分支。冻结脚本缺少数值子结构Craig--Bampton缩聚、显式共享接口装配算子和12x12 M/C/K，且存在载荷维数与a0/a1来源问题。没有拼造12维矩阵。
""",
        local_failure,
    )

    u03_common = common_global + local_failure + [
        ("outputs/contract_divisions.csv", "data/contract_divisions.csv"),
        ("outputs/contract_dof_membership.csv", "data/contract_dof_membership.csv"),
        ("outputs/contract_recovery.csv", "data/contract_recovery.csv"),
    ]
    published += publish_package(
        FAILURE_U03,
        """# U03第一类物理/数值子结构划分（部分计算级复现；整体待决定）

已成功：当前完整15自由度组合主/从划分、6维Guyan、9维Craig--Bampton、载荷投影和三层恢复接口；局部物理子结构PDmonicanshu2也可运行。

未闭合：局部数值侧缩聚、物理/数值共享接口散布算子和12维装配矩阵。故不建立U03成功目录。本目录同时保存已成功子路线和失败分支，以免用全局组合路线覆盖论文分子结构路线。
""",
        u03_common,
    )
    published += publish_package(
        FAILURE_U04,
        """# U04第二类物理/数值子结构划分（部分计算级复现；整体待决定）

已成功：当前完整15自由度组合主/从划分、5维Guyan、8维Craig--Bampton、psi6作为从自由度仍参与惯性力并通过P*T/P*Tcb恢复；局部物理子结构PDmonicanshu3也可运行。

未闭合：局部数值侧缩聚、共享接口散布算子和12维装配矩阵；New_Ps3还存在9x9矩阵配6x1载荷。故不建立U04成功目录。
""",
        u03_common,
    )

    log_lines = [
        "板块17对象发布",
        f"生成时间(UTC): {datetime.now(timezone.utc).isoformat()}",
        "U03: 部分计算级复现；整体待决定；仅失败/证据包",
        "U04: 部分计算级复现；整体待决定；仅失败/证据包",
        "U05: 计算级复现；成功包；公式冲突另存失败路线目录",
        "U06: 当前9/8维计算级复现；成功包；12维候选失败包",
        f"发布文件计数（含包内manifest，去重前）: {len(published)}",
    ]
    LOG_PATH.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    scope_files: set[Path] = {LOCAL_DOF_CSV, ADJUDICATION_CSV, LOG_PATH}
    for package in (
        SUCCESS_U05,
        SUCCESS_U06,
        FAILURE_U03,
        FAILURE_U04,
        FAILURE_U05,
        FAILURE_U06,
    ):
        scope_files.update(
            path
            for path in package.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts
        )
    hash_rows = [
        {
            "relative_path": relative(path),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(scope_files, key=lambda item: relative(item))
    ]
    write_csv(PUBLISH_HASHES_CSV, hash_rows)

    result = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "published_hash_row_count": len(hash_rows),
        "success_directories": [relative(SUCCESS_U05), relative(SUCCESS_U06)],
        "failure_directories": [
            relative(FAILURE_U03),
            relative(FAILURE_U04),
            relative(FAILURE_U05),
            relative(FAILURE_U06),
        ],
        "u03_success_directory_absent": not (SUCCESS_ROOT / U03_NAME).exists(),
        "u04_success_directory_absent": not (SUCCESS_ROOT / U04_NAME).exists(),
        "publish_hashes_sha256": sha256(PUBLISH_HASHES_CSV),
        "pass": True,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

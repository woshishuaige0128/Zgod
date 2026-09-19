from __future__ import annotations

import csv
import hashlib
import json
import os
import py_compile
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCRIPT_PATH = Path(__file__).resolve()
CANDIDATE = SCRIPT_PATH.parents[1]
PROJECT_ROOT = SCRIPT_PATH.parents[4]
RHTS_ROOT = PROJECT_ROOT.parent
OUTPUTS = CANDIDATE / "outputs"
REPORT = CANDIDATE / "report"

PROTECTED_MANIFEST = CANDIDATE / "input" / "project_contract" / "源文件冻结清单.csv"
BOARD16_MANIFEST = CANDIDATE / "input" / "upstream_u01" / "board16_artifact_manifest.csv"
BOARD14_MANIFEST = (
    RHTS_ROOT
    / "260817"
    / "test"
    / "2026-08-24_Guyan双侧投影结论影响核查"
    / "source_manifest.csv"
)
INDEX_PATH = PROJECT_ROOT / "test" / "00_总索引与复现规则" / "全部对象总索引.csv"
THESIS_PATH = RHTS_ROOT / "梁禹手稿.pdf"
MANUSCRIPT_PATH = RHTS_ROOT / "260817" / "manuscript_0824.tex"

MAIN_REPORT = REPORT / "板块17_两类自由度划分与缩聚路线复现报告.md"
VALIDATION_CSV = REPORT / "board17_final_validation.csv"
VALIDATION_JSON = REPORT / "board17_final_validation_summary.json"
VALIDATION_MD = REPORT / "板块17_最终验收记录.md"
ARTIFACT_MANIFEST = REPORT / "board17_artifact_manifest.csv"
FINAL_META_HASHES = REPORT / "board17_final_meta_hashes.csv"

U03_NAME = "U03_第一类物理_数值子结构划分"
U04_NAME = "U04_第二类物理_数值子结构划分"
U05_NAME = "U05_Guyan历史单侧实现、论文公式与标准双侧合同投影"
U06_NAME = "U06_Craig--Bampton三固定界面模态的实际实现"
SUCCESS_ROOT = PROJECT_ROOT / "test" / "00_上游模型身份证"
FAILURE_ROOT = PROJECT_ROOT / "test" / "00_失败尝试与候选路线"

EXPECTED_THESIS_SHA = "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
EXPECTED_MANUSCRIPT_SHA = "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76"

PRELIMINARY_VALIDATION_ATTEMPTS = [
    {
        "attempt": 1,
        "result": "验证器未进入门槛检查",
        "cause": "指定Python环境未安装psutil；改用Windows自带tasklist核对MATLAB/Python/PythonW残留进程，不安装新依赖。",
    }
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise RuntimeError(f"拒绝写空CSV: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def audit_protected_sources() -> tuple[int, list[str]]:
    rows = read_csv(PROTECTED_MANIFEST)
    problems: list[str] = []
    for row in rows:
        path = Path(row["绝对路径"])
        if not path.is_file():
            problems.append(f"MISSING|{path}")
            continue
        if path.stat().st_size != int(row["文件大小_字节"]):
            problems.append(f"SIZE|{path}")
        actual = sha256(path)
        if actual != row["SHA256"].upper():
            problems.append(f"HASH|{path}|{actual}|{row['SHA256']}")
    return len(rows), problems


def audit_board16_artifacts() -> tuple[int, list[str]]:
    rows = read_csv(BOARD16_MANIFEST)
    problems: list[str] = []
    for row in rows:
        path = PROJECT_ROOT / Path(row["relative_path"])
        if not path.is_file():
            problems.append(f"MISSING|{path}")
            continue
        if path.stat().st_size != int(row["size_bytes"]):
            problems.append(f"SIZE|{path}")
        actual = sha256(path)
        if actual != row["sha256"].upper():
            problems.append(f"HASH|{path}|{actual}|{row['sha256']}")
    return len(rows), problems


def audit_board14_sources() -> tuple[int, list[str]]:
    rows = read_csv(BOARD14_MANIFEST)
    problems: list[str] = []
    for row in rows:
        source = Path(row["SourcePath"])
        copied = Path(row["CopyPath"])
        expected_source = row["SHA256Before"].upper()
        expected_copy = row["SHA256Copy"].upper()
        if not source.is_file():
            problems.append(f"SOURCE_MISSING|{source}")
        elif sha256(source) != expected_source:
            problems.append(f"SOURCE_HASH|{source}")
        if not copied.is_file():
            problems.append(f"COPY_MISSING|{copied}")
        elif sha256(copied) != expected_copy:
            problems.append(f"COPY_HASH|{copied}")
        if row["InitialIntegrity"] != "MATCH":
            problems.append(f"INITIAL_NOT_MATCH|{source}")
    return len(rows), problems


def audit_hash_manifest(path: Path, base: Path) -> tuple[int, list[str]]:
    rows = read_csv(path)
    problems: list[str] = []
    for row in rows:
        raw = row.get("relative_path", row.get("path", ""))
        expected = row.get("sha256", row.get("SHA256", ""))
        if not raw or not expected:
            problems.append(f"SCHEMA|{path}|{row}")
            continue
        target = Path(raw)
        if not target.is_absolute():
            target = base / target
        if not target.is_file():
            problems.append(f"MISSING|{target}")
            continue
        if "size_bytes" in row and row["size_bytes"]:
            if target.stat().st_size != int(row["size_bytes"]):
                problems.append(f"SIZE|{target}")
        actual = sha256(target)
        if actual != expected.upper():
            problems.append(f"HASH|{target}|{actual}|{expected}")
    return len(rows), problems


def compile_python_scripts() -> tuple[int, list[str]]:
    scripts = sorted((CANDIDATE / "code").glob("*.py"))
    problems: list[str] = []
    for script in scripts:
        try:
            py_compile.compile(str(script), doraise=True)
        except py_compile.PyCompileError as exc:
            problems.append(f"{script}|{exc}")
    return len(scripts), problems


def residual_processes() -> list[str]:
    current_pid = os.getpid()
    residual: list[str] = []
    completed = subprocess.run(
        ["tasklist", "/FO", "CSV", "/NH"],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="mbcs",
        errors="replace",
    )
    for row in csv.reader(completed.stdout.splitlines()):
        if len(row) < 2:
            continue
        name = row[0].strip().lower()
        try:
            pid = int(row[1].replace(",", ""))
        except ValueError:
            continue
        if pid == current_pid:
            continue
        if name in {"matlab.exe", "python.exe", "pythonw.exe", "matlab"}:
            residual.append(f"{pid}:{name}")
    return residual


def build_artifact_manifest() -> tuple[int, list[str]]:
    excluded_names = {
        ARTIFACT_MANIFEST.name,
        VALIDATION_CSV.name,
        VALIDATION_JSON.name,
        VALIDATION_MD.name,
        FINAL_META_HASHES.name,
    }
    package_roots = [
        CANDIDATE,
        FAILURE_ROOT / U03_NAME,
        FAILURE_ROOT / U04_NAME,
        FAILURE_ROOT / U05_NAME,
        FAILURE_ROOT / U06_NAME,
        SUCCESS_ROOT / U05_NAME,
        SUCCESS_ROOT / U06_NAME,
    ]
    paths: set[Path] = {INDEX_PATH}
    for root in package_roots:
        if not root.is_dir():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            if path.parent == REPORT and path.name in excluded_names:
                continue
            paths.add(path)
    rows = [
        {
            "relative_path": path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in sorted(paths, key=lambda item: item.as_posix())
    ]
    write_csv(ARTIFACT_MANIFEST, rows)
    return audit_hash_manifest(ARTIFACT_MANIFEST, PROJECT_ROOT)


def main() -> int:
    REPORT.mkdir(parents=True, exist_ok=True)
    checks: list[dict[str, Any]] = []
    failures: list[str] = []

    def record(
        check: str,
        actual: Any,
        expected: str,
        passed: bool,
        evidence: str,
    ) -> None:
        checks.append(
            {
                "check": check,
                "actual": actual,
                "expected": expected,
                "result": "PASS" if passed else "FAIL",
                "evidence": evidence,
            }
        )
        if not passed:
            failures.append(f"{check}|actual={actual}|expected={expected}")

    protected_count, protected_problems = audit_protected_sources()
    record(
        "326项保护源当前哈希",
        f"rows={protected_count};problems={len(protected_problems)}",
        "rows=326;problems=0",
        protected_count == 326 and not protected_problems,
        str(PROTECTED_MANIFEST),
    )
    failures.extend(protected_problems)

    board16_count, board16_problems = audit_board16_artifacts()
    record(
        "板块16工件当前哈希",
        f"rows={board16_count};problems={len(board16_problems)}",
        "rows=166;problems=0",
        board16_count == 166 and not board16_problems,
        str(BOARD16_MANIFEST),
    )
    failures.extend(board16_problems)

    board14_count, board14_problems = audit_board14_sources()
    record(
        "板块14源与冻结副本当前哈希",
        f"rows={board14_count};problems={len(board14_problems)}",
        "rows=23;source/copy problems=0",
        board14_count == 23 and not board14_problems,
        str(BOARD14_MANIFEST),
    )
    failures.extend(board14_problems)

    input_summary = read_json(OUTPUTS / "input_freeze_independent_summary.json")
    record(
        "板块17输入冻结独立复核",
        f"pass={input_summary.get('pass')};sources={input_summary.get('source_count')};rehashed={input_summary.get('rehashed_file_count')};problems={input_summary.get('problem_count')}",
        "true;32;64;0",
        input_summary.get("pass") is True
        and input_summary.get("source_count") == 32
        and input_summary.get("rehashed_file_count") == 64
        and input_summary.get("problem_count") == 0,
        "outputs/input_freeze_independent_summary.json",
    )

    contract = read_json(OUTPUTS / "contract_summary.json")
    record(
        "自由度公式Simulink契约门槛",
        f"status={contract.get('overall_status')};gates={contract.get('gate_pass_count')}/{contract.get('gate_count')}",
        "PASS;22/22",
        contract.get("overall_status") == "PASS"
        and contract.get("gate_pass_count") == contract.get("gate_count") == 22,
        "outputs/contract_summary.json",
    )
    record(
        "七个契约冲突已显式保留",
        contract.get("conflict_count"),
        "7",
        contract.get("conflict_count") == 7,
        "outputs/contract_conflicts.csv",
    )
    findings = contract.get("key_findings", {})
    record(
        "第一类组合维数",
        findings.get("division_1"),
        "Guyan6;CB9",
        findings.get("division_1", {}).get("guyan_width") == 6
        and findings.get("division_1", {}).get("cb_width") == 9,
        "outputs/contract_divisions.csv",
    )
    record(
        "第二类组合维数与psi6恢复",
        findings.get("division_2"),
        "Guyan5;CB8;psi6 slave recovered",
        findings.get("division_2", {}).get("guyan_width") == 5
        and findings.get("division_2", {}).get("cb_width") == 8
        and "slave_recovered" in str(findings.get("division_2", {}).get("psi6")),
        "outputs/contract_divisions.csv;outputs/contract_recovery.csv",
    )
    record(
        "Simulink输出变量顺序",
        findings.get("workspace_outputs"),
        "simout3=floor1;simout=floor2;simout1=floor3",
        findings.get("workspace_outputs")
        == {"simout": "floor2", "simout1": "floor3", "simout3": "floor1"},
        "outputs/contract_simulink_outputs.csv",
    )
    record(
        "冻结SLX标准callback为空",
        findings.get("model_callbacks"),
        "no_nonempty_standard_model_callbacks_in_frozen_slx",
        findings.get("model_callbacks")
        == "no_nonempty_standard_model_callbacks_in_frozen_slx",
        "outputs/contract_simulink_callbacks.csv",
    )

    global_summary = read_json(OUTPUTS / "global_route_summary.json")
    record(
        "MATLAB全局缩聚内部门槛",
        global_summary.get("internal_gate_pass"),
        "true",
        global_summary.get("internal_gate_pass") is True,
        "outputs/global_route_summary.json",
    )
    for division in (1, 2):
        item = global_summary[f"division{division}"]
        expected_guyan, expected_cb = ((6, 9) if division == 1 else (5, 8))
        record(
            f"第{division}类MATLAB维数",
            f"{item.get('guyan_dimension')}/{item.get('cb_dimension')}",
            f"{expected_guyan}/{expected_cb}",
            item.get("guyan_dimension") == expected_guyan
            and item.get("cb_dimension") == expected_cb,
            "outputs/global_dimension_gates.csv",
        )
        record(
            f"第{division}类作者脚本ASCII字节副本成功",
            f"status={item.get('original_transfer_status')};hash={item.get('bytecopy_sha256_match')};compare={item.get('original_transfer_comparison_pass')}",
            "SUCCESS;true;true",
            item.get("original_transfer_status") == "SUCCESS"
            and item.get("bytecopy_sha256_match") is True
            and item.get("original_transfer_comparison_pass") is True,
            "outputs/global_original_script_comparison.csv",
        )
        record(
            f"第{division}类中文原文件名入口失败保留",
            f"{item.get('direct_chinese_filename_status')};{item.get('direct_chinese_filename_error_identifier')}",
            "FAILED;MATLAB:m_illegal_character",
            item.get("direct_chinese_filename_status") == "FAILED"
            and item.get("direct_chinese_filename_error_identifier")
            == "MATLAB:m_illegal_character",
            "logs/global_routes_matlab.log",
        )

    independent = read_json(OUTPUTS / "independent_global_summary.json")
    record(
        "独立Python全局公式重建",
        f"{independent.get('pass_count')}/{independent.get('check_count')};fail={independent.get('failure_count')}",
        "68/68;fail=0",
        independent.get("pass") is True
        and independent.get("pass_count") == independent.get("check_count") == 68
        and independent.get("failure_count") == 0,
        "outputs/independent_global_summary.json",
    )
    differences = independent.get("historical_vs_projected_relative_differences", {})
    record(
        "历史与标准Guyan质量差复现",
        f"{differences.get('1', {}).get('mass')};{differences.get('2', {}).get('mass')}",
        "0.09977893886275215;0.3730127025329254",
        abs(differences.get("1", {}).get("mass", 0) - 0.09977893886275215) < 1e-14
        and abs(differences.get("2", {}).get("mass", 0) - 0.3730127025329254) < 1e-14,
        "outputs/independent_global_summary.json",
    )

    cross = read_json(OUTPUTS / "cross_language_summary.json")
    record(
        "MATLAB-Python跨语言验证",
        f"{cross.get('pass_count')}/{cross.get('check_count')};fail={cross.get('failure_count')}",
        "82/82;fail=0",
        cross.get("pass") is True
        and cross.get("pass_count") == cross.get("check_count") == 82
        and cross.get("failure_count") == 0,
        "outputs/cross_language_summary.json",
    )
    record(
        "跨语言矩阵最大误差",
        cross.get("maximum_direct_matrix_relative_error"),
        "<=5e-12",
        cross.get("maximum_direct_matrix_relative_error", 1) <= 5e-12,
        "outputs/cross_language_matrix_checks.csv",
    )
    record(
        "跨语言CB子空间角",
        cross.get("maximum_cb_subspace_angle_rad"),
        "<=5e-8 rad",
        cross.get("maximum_cb_subspace_angle_rad", 1) <= 5e-8,
        "outputs/cross_language_summary.json",
    )
    record(
        "跨语言频率最大差",
        cross.get("maximum_modal_frequency_absolute_error_hz"),
        "<=5e-10 Hz",
        cross.get("maximum_modal_frequency_absolute_error_hz", 1) <= 5e-10,
        "outputs/cross_language_modal_comparison.csv",
    )

    local_audit = read_json(OUTPUTS / "local_candidate_python_audit.json")
    record(
        "局部候选独立公式审计",
        f"status={local_audit.get('status')};rows={local_audit.get('matrix_csv_rows_checked')}",
        "PASS;630",
        local_audit.get("status") == "PASS"
        and local_audit.get("matrix_csv_rows_checked") == 630,
        "outputs/local_candidate_python_audit.json",
    )
    record(
        "局部PD2/PD3公式误差",
        local_audit.get("formula_errors"),
        "each max<=1e-12",
        all(
            item.get("max", 1) <= 1e-12
            for item in local_audit.get("formula_errors", {}).values()
        )
        and len(local_audit.get("formula_errors", {})) == 2,
        "outputs/local_candidate_python_audit.json",
    )
    record(
        "四个New脚本12次尝试",
        local_audit.get("attempt_evidence"),
        "12 attempts;4 literal errors;4 missing-coefficient errors;4 probes",
        local_audit.get("attempt_evidence", {}).get("attempt_count") == 12
        and local_audit.get("attempt_evidence", {}).get("literal_error_count") == 4
        and local_audit.get("attempt_evidence", {}).get(
            "context_missing_coeff_error_count"
        )
        == 4
        and local_audit.get("attempt_evidence", {}).get(
            "dimension_probe_success_count"
        )
        == 4,
        "outputs/local_new_script_attempts.csv",
    )
    record(
        "12维装配失败且未造矩阵",
        f"status={local_audit.get('assembled_12d_status')};created={local_audit.get('assembled_12d_matrix_created')}",
        "FAIL_PENDING_DECISION;false",
        local_audit.get("assembled_12d_status") == "FAIL_PENDING_DECISION"
        and local_audit.get("assembled_12d_matrix_created") is False,
        "outputs/local_assembly_12d_gate.csv",
    )

    adjudication = {row["object_id"]: row for row in read_csv(OUTPUTS / "object_adjudication.csv")}
    record(
        "U03-U06逐对象裁决行",
        sorted(adjudication),
        "U03,U04,U05,U06",
        sorted(adjudication) == ["U03", "U04", "U05", "U06"],
        "outputs/object_adjudication.csv",
    )
    record(
        "U03/U04部分计算级且整体待决定",
        f"U03={adjudication.get('U03')};U04={adjudication.get('U04')}",
        "evidence=部分计算级复现;status=待决定;no success dir",
        all(
            adjudication.get(item, {}).get("evidence_level") == "部分计算级复现"
            and adjudication.get(item, {}).get("overall_status") == "待决定"
            and adjudication.get(item, {}).get("success_directory_created") == "0"
            for item in ("U03", "U04")
        ),
        "outputs/object_adjudication.csv",
    )
    record(
        "U05/U06计算级成功",
        f"U05={adjudication.get('U05')};U06={adjudication.get('U06')}",
        "evidence=计算级复现;success dir created",
        all(
            adjudication.get(item, {}).get("evidence_level") == "计算级复现"
            and adjudication.get(item, {}).get("success_directory_created") == "1"
            for item in ("U05", "U06")
        ),
        "outputs/object_adjudication.csv",
    )
    local_dof_rows = read_csv(OUTPUTS / "local_dof_sets.csv")
    record(
        "局部与组合自由度集合表",
        len(local_dof_rows),
        "6 rows",
        len(local_dof_rows) == 6
        and sum(row["substructure"] == "combined_full_model" for row in local_dof_rows)
        == 2,
        "outputs/local_dof_sets.csv",
    )

    required_directory_checks = {
        "U03成功目录不存在": not (SUCCESS_ROOT / U03_NAME).exists(),
        "U04成功目录不存在": not (SUCCESS_ROOT / U04_NAME).exists(),
        "U03失败证据包存在": (FAILURE_ROOT / U03_NAME).is_dir(),
        "U04失败证据包存在": (FAILURE_ROOT / U04_NAME).is_dir(),
        "U05成功包存在": (SUCCESS_ROOT / U05_NAME).is_dir(),
        "U05公式冲突包存在": (FAILURE_ROOT / U05_NAME).is_dir(),
        "U06成功包存在": (SUCCESS_ROOT / U06_NAME).is_dir(),
        "U06的12维失败包存在": (FAILURE_ROOT / U06_NAME).is_dir(),
    }
    for label, passed in required_directory_checks.items():
        record(label, passed, "true", passed, "test/00_上游模型身份证;test/00_失败尝试与候选路线")

    publish_count, publish_problems = audit_hash_manifest(
        OUTPUTS / "publish_artifact_hashes.csv", PROJECT_ROOT
    )
    record(
        "119项发布文件当前哈希",
        f"rows={publish_count};problems={len(publish_problems)}",
        "rows=119;problems=0",
        publish_count == 119 and not publish_problems,
        "outputs/publish_artifact_hashes.csv",
    )
    failures.extend(publish_problems)

    package_manifest_problems: list[str] = []
    package_manifest_rows = 0
    for package in [
        FAILURE_ROOT / U03_NAME,
        FAILURE_ROOT / U04_NAME,
        FAILURE_ROOT / U05_NAME,
        FAILURE_ROOT / U06_NAME,
        SUCCESS_ROOT / U05_NAME,
        SUCCESS_ROOT / U06_NAME,
    ]:
        count, problems = audit_hash_manifest(
            package / "package_manifest.csv", package
        )
        package_manifest_rows += count
        package_manifest_problems.extend(problems)
    record(
        "六个对象包内部清单",
        f"rows={package_manifest_rows};problems={len(package_manifest_problems)}",
        "problems=0",
        not package_manifest_problems,
        "各对象包/package_manifest.csv",
    )
    failures.extend(package_manifest_problems)

    index_rows = read_csv(INDEX_PATH)
    index_by_id = {row["对象ID"]: row for row in index_rows}
    record(
        "45项总索引结构",
        f"rows={len(index_rows)};unique={len(index_by_id)};columns={len(index_rows[0])}",
        "45;45;15",
        len(index_rows) == 45 and len(index_by_id) == 45 and len(index_rows[0]) == 15,
        str(INDEX_PATH),
    )
    record(
        "总索引U03/U04状态",
        f"{index_by_id['U03']['当前证据等级']}|{index_by_id['U03']['当前状态']}|{index_by_id['U04']['当前证据等级']}|{index_by_id['U04']['当前状态']}",
        "部分计算级复现;状态含待决定",
        all(
            index_by_id[item]["当前证据等级"] == "部分计算级复现"
            and "待决定" in index_by_id[item]["当前状态"]
            for item in ("U03", "U04")
        ),
        str(INDEX_PATH),
    )
    record(
        "总索引U05/U06证据等级",
        f"{index_by_id['U05']['当前证据等级']};{index_by_id['U06']['当前证据等级']}",
        "计算级复现;计算级复现",
        index_by_id["U05"]["当前证据等级"] == "计算级复现"
        and index_by_id["U06"]["当前证据等级"] == "计算级复现",
        str(INDEX_PATH),
    )
    u06_baseline = index_by_id["U06"]["对比基准"]
    record(
        "总索引U06实际eig身份",
        u06_baseline,
        "contains eig and not svds",
        "eig" in u06_baseline and "svds" not in u06_baseline,
        str(INDEX_PATH),
    )

    report_text = MAIN_REPORT.read_text(encoding="utf-8")
    report_markers = [
        "68/68",
        "82/82",
        "630",
        "ψ6",
        "FAIL_PENDING_DECISION",
        "U03",
        "U04",
        "U05",
        "U06",
        "manuscript_0824.tex",
        "没有运行 Simulink",
        "部分计算级复现；对象整体状态仍为待决定",
    ]
    record(
        "中文证据报告长度",
        len(report_text),
        ">=10000 characters",
        len(report_text) >= 10000,
        str(MAIN_REPORT),
    )
    missing_markers = [marker for marker in report_markers if marker not in report_text]
    record(
        "中文证据报告必含主题",
        f"missing={missing_markers}",
        "missing=[]",
        not missing_markers,
        str(MAIN_REPORT),
    )
    for conflict_id in [
        "C01_DIV1_R_COMMENT",
        "C03_DIV1_MODAL_SORT",
        "C01_DIV2_R_COMMENT",
        "C03_DIV2_MODAL_SORT",
        "C02_GUYAN_FORMULA_ROUTE",
        "C04_DIV2_PHYSICAL_PRELUDE",
        "C05_DIV2_THIRD_FLOOR_REPAIR",
    ]:
        record(
            f"报告包含冲突{conflict_id}",
            conflict_id in report_text,
            "true",
            conflict_id in report_text,
            str(MAIN_REPORT),
        )

    record(
        "硕士论文保护哈希",
        sha256(THESIS_PATH),
        EXPECTED_THESIS_SHA,
        THESIS_PATH.is_file() and sha256(THESIS_PATH) == EXPECTED_THESIS_SHA,
        str(THESIS_PATH),
    )
    record(
        "manuscript_0824.tex保护哈希",
        sha256(MANUSCRIPT_PATH),
        EXPECTED_MANUSCRIPT_SHA,
        MANUSCRIPT_PATH.is_file() and sha256(MANUSCRIPT_PATH) == EXPECTED_MANUSCRIPT_SHA,
        str(MANUSCRIPT_PATH),
    )

    script_count, compile_problems = compile_python_scripts()
    record(
        "板块17全部Python脚本语法",
        f"scripts={script_count};problems={len(compile_problems)}",
        "problems=0",
        not compile_problems,
        "candidate/code/*.py",
    )
    failures.extend(compile_problems)

    residual = residual_processes()
    record(
        "MATLAB/Python/PythonW残留进程",
        residual,
        "[] (current validator excluded)",
        not residual,
        "psutil process inventory",
    )

    artifact_count, artifact_problems = build_artifact_manifest()
    record(
        "板块17完整工件清单当前哈希",
        f"rows={artifact_count};problems={len(artifact_problems)}",
        "problems=0",
        artifact_count > 0 and not artifact_problems,
        str(ARTIFACT_MANIFEST),
    )
    failures.extend(artifact_problems)

    generated_at = datetime.now(timezone.utc).isoformat()
    summary = {
        "generated_at_utc": generated_at,
        "check_count": len(checks),
        "pass_count": sum(row["result"] == "PASS" for row in checks),
        "failure_count": len(failures),
        "protected_source_count": protected_count,
        "board16_artifact_count": board16_count,
        "board14_source_count": board14_count,
        "published_artifact_count": publish_count,
        "board17_artifact_manifest_count": artifact_count,
        "report_character_count": len(report_text),
        "report_sha256": sha256(MAIN_REPORT),
        "index_sha256": sha256(INDEX_PATH),
        "preliminary_validation_attempts": PRELIMINARY_VALIDATION_ATTEMPTS,
        "failures": failures,
        "pass": len(failures) == 0,
    }
    write_csv(VALIDATION_CSV, checks)
    VALIDATION_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    validation_lines = [
        "# 板块17最终验收记录",
        "",
        f"生成时间（UTC）：{generated_at}",
        "",
        f"最终结论：**{'PASS' if summary['pass'] else 'FAIL'}**。",
        "",
        f"- 明确门槛：{summary['pass_count']}/{summary['check_count']} PASS。",
        f"- 失败记录数：{summary['failure_count']}。",
        f"- 保护源：{protected_count}/326 当前哈希核对。",
        f"- 板块16工件：{board16_count}/166 当前哈希核对。",
        f"- 板块14来源：{board14_count}/23 源与副本核对。",
        f"- 板块17发布文件：{publish_count}/119 当前哈希核对。",
        f"- 板块17完整工件清单：{artifact_count} 项，清单自身除外。",
        f"- 中文证据报告：{len(report_text)} 字符，SHA-256 `{sha256(MAIN_REPORT)}`。",
        "- U03/U04：部分计算级复现，对象整体待决定，未建立成功目录。",
        "- U05：计算级复现，历史单边与标准双侧冲突显式保留。",
        "- U06：当前9/8维路线计算级复现，12维分子结构候选待决定。",
        "- 本板块没有运行Simulink响应、逐图时程、稳定域或能量算例。",
        "",
        "## 前置验证器失败记录",
        *[
            f"- 第{item['attempt']}次：{item['result']}；原因：{item['cause']}"
            for item in PRELIMINARY_VALIDATION_ATTEMPTS
        ],
    ]
    if failures:
        validation_lines.extend(["", "## 失败清单", *[f"- {item}" for item in failures]])
    VALIDATION_MD.write_text("\n".join(validation_lines) + "\n", encoding="utf-8")

    meta_paths = [ARTIFACT_MANIFEST, VALIDATION_CSV, VALIDATION_JSON, VALIDATION_MD]
    meta_rows = [
        {
            "relative_path": path.relative_to(CANDIDATE).as_posix(),
            "size_bytes": path.stat().st_size,
            "sha256": sha256(path),
        }
        for path in meta_paths
    ]
    write_csv(FINAL_META_HASHES, meta_rows)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

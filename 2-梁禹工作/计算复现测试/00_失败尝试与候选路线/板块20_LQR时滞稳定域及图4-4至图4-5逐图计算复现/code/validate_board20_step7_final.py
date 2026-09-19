from __future__ import annotations

import csv
import hashlib
import json
import math
import os
import stat
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image
from PyPDF2 import PdfReader


SCRIPT_PATH = Path(__file__).resolve()
CODE_ROOT = SCRIPT_PATH.parent
BOARD_ROOT = CODE_ROOT.parent
PROJECT_ROOT = BOARD_ROOT.parents[2]
TEST_ROOT = PROJECT_ROOT / "test"
FAILURE_ROOT = TEST_ROOT / "00_失败尝试与候选路线"
OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step7_final_validation"

PUBLICATION_CONTRACT_PATH = CODE_ROOT / "board20_step7_publication_contract.json"
EXPECTED_PUBLICATION_CONTRACT_SHA256 = (
    "449D6B4E6AFBE58B0E39BC6F51D573615F0D186C18FBC423BEACAEC0417B7E79"
)
EXPECTED_PRE_INDEX_SHA256 = (
    "737F7D47A5FE641430E45FA508D0885D120FDE6FB00EF9E3CACAFE39A9136418"
)
EXPECTED_THESIS_SHA256 = (
    "DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1"
)
EXPECTED_MANUSCRIPT_SHA256 = (
    "15A5025246A25809E33E8A38F13C3E71C23607C7765D967730F6105B5445DB76"
)

STEP6_RUN1 = BOARD_ROOT / "outputs" / "step6_history_comparison_run1"
STEP6_RUN2 = BOARD_ROOT / "outputs" / "step6_history_comparison_run2"
STEP6_VALIDATION = BOARD_ROOT / "outputs" / "step6_history_comparison_validation"
STEP6_TABLES = STEP6_RUN1 / "tables"
STEP6_CONTRACT = CODE_ROOT / "board20_step6_history_comparison_contract.json"
STEP6_GENERATOR = CODE_ROOT / "analyze_board20_step6_history_comparison.py"
STEP6_VALIDATOR = CODE_ROOT / "validate_board20_step6_history_comparison.py"
STEP5_PROTECTED = (
    BOARD_ROOT
    / "outputs"
    / "step5_fullq_svd_candidate_audit_v5_full"
    / "v5_full_validator_full_postcheck_protected_hashes.csv"
)

INDEX_PRE = BOARD_ROOT / "input" / "project_contract" / "全部对象总索引_板块20前快照.csv"
INDEX_LIVE = TEST_ROOT / "00_总索引与复现规则" / "全部对象总索引.csv"
THESIS_PATH = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\梁禹手稿.pdf")
MANUSCRIPT_PATH = Path(
    r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\260817\manuscript_0824.tex"
)

ARTIFACT_FIELDS = ["relative_path", "size_bytes", "sha256", "role"]
SHARED_FIELDS = [
    "object_id",
    "central_relative_path",
    "size_bytes",
    "sha256",
    "source_step",
    "role",
    "copy_policy",
    "scope_note",
]
INDEX_FIELDS = [
    "对象ID",
    "对象类型",
    "论文编号",
    "唯一图号",
    "名称",
    "PDF页",
    "印刷页",
    "计算对象",
    "对比基准",
    "目标证据等级",
    "当前证据等级",
    "当前状态",
    "成功文件夹",
    "失败尝试目录",
    "备注",
]

FIGURE_STEMS: dict[str, list[str]] = {
    "F4-4": [
        "图4-4_历史最终掩膜边界_绘图级复核",
        "图4-4_作者文件身份计算候选_失败诊断",
    ],
    "F4-5": [
        "图4-5_历史最终掩膜边界_绘图级复核",
        "图4-5_作者文件身份计算候选_失败诊断",
    ],
}
ALL_FIGURE_STEMS = FIGURE_STEMS["F4-4"] + FIGURE_STEMS["F4-5"]

OBJECT_SPECS: dict[str, dict[str, Any]] = {
    "F4-4": {
        "package_name": "图4-4_第一类子结构划分稳定域",
        "success_name": "图4-4_第一类子结构划分稳定域",
        "final_evidence": "绘图级复现",
        "figure_id": "F4-4",
        "division": "div1",
        "route_ids": {
            "main_ori_div1",
            "main_cb_div1",
            "main_guyan_div1",
            "alt_guyan_div1_stable_full_ps3",
        },
        "figure_stems": FIGURE_STEMS["F4-4"],
        "expected_mismatch": {
            "main_ori_div1": 1389,
            "main_guyan_div1": 951,
            "alt_guyan_div1_stable_full_ps3": 1037,
        },
    },
    "F4-5": {
        "package_name": "图4-5_第二类子结构划分稳定域",
        "success_name": "图4-5_第二类子结构划分稳定域",
        "final_evidence": "绘图级复现",
        "figure_id": "F4-5",
        "division": "div2",
        "route_ids": {"main_ori_div2", "main_cb_div2", "main_guyan_div2"},
        "figure_stems": FIGURE_STEMS["F4-5"],
        "expected_mismatch": {
            "main_ori_div2": 1213,
            "main_guyan_div2": 895,
        },
    },
    "C05": {
        "package_name": "结论C05_两类划分的稳定裕度下降量",
        "success_name": "结论C05_两类划分的稳定裕度下降量",
        "final_evidence": "历史值",
        "figure_stems": ALL_FIGURE_STEMS,
    },
    "C07": {
        "package_name": "结论C07_结论章频率区间、误差幅值与临界时滞总结",
        "success_name": "结论C07_结论章频率区间、误差幅值与临界时滞总结",
        "final_evidence": "历史值",
        "figure_stems": ALL_FIGURE_STEMS,
    },
}

C07_SCOPE_FIELDS = [
    "component",
    "status",
    "evidence_level",
    "evaluated_in_board20",
    "scope_note",
]
C07_SCOPE_ROWS = [
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


def strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"JSON存在重复键：{key}")
        result[key] = value
    return result


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=strict_object)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV缺少表头：{path}")
        fields = list(reader.fieldnames)
        if len(fields) != len(set(fields)):
            raise ValueError(f"CSV存在重复字段：{path}: {fields}")
        return fields, list(reader)


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return format(value, ".17g")
    return str(value)


def write_csv(
    path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream, fieldnames=list(fieldnames), extrasaction="raise", lineterminator="\n"
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({field: csv_value(row.get(field)) for field in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def bool_text(value: str) -> bool:
    if value == "True":
        return True
    if value == "False":
        return False
    raise ValueError(f"不是固定布尔文本：{value!r}")


def relative_to_project(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        normalized: dict[str, Any] = {}
        for key, item in value.items():
            if isinstance(key, tuple):
                normalized_key = "|".join(str(part) for part in key)
            else:
                normalized_key = str(key)
            normalized[normalized_key] = json_safe(item)
        return normalized
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, set):
        return [json_safe(item) for item in sorted(value, key=str)]
    if isinstance(value, Path):
        return value.as_posix()
    return value


class Checks:
    def __init__(self) -> None:
        self.rows: list[dict[str, str]] = []
        self._counter = 0

    def add(
        self,
        category: str,
        description: str,
        condition: bool,
        expected: Any,
        actual: Any,
        evidence: str,
    ) -> None:
        self._counter += 1
        self.rows.append(
            {
                "check_id": f"S7V{self._counter:04d}",
                "category": category,
                "description": description,
                "status": "PASS" if condition else "FAIL",
                "expected": json.dumps(json_safe(expected), ensure_ascii=False, sort_keys=True),
                "actual": json.dumps(json_safe(actual), ensure_ascii=False, sort_keys=True),
                "evidence": evidence,
            }
        )

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.rows),
            "pass": sum(row["status"] == "PASS" for row in self.rows),
            "fail": sum(row["status"] == "FAIL" for row in self.rows),
        }


def package_root(object_id: str) -> Path:
    return FAILURE_ROOT / str(OBJECT_SPECS[object_id]["package_name"])


def success_root(object_id: str) -> Path:
    return TEST_ROOT / str(OBJECT_SPECS[object_id]["success_name"])


def output_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"), key=lambda item: item.as_posix())
        if path.is_file()
    }


def resolve_board_relative(relpath: str) -> Path:
    pure = Path(relpath.replace("/", os.sep))
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError(f"共享证据路径不是安全的板块相对路径：{relpath}")
    path = (BOARD_ROOT / pure).resolve()
    if not path.is_relative_to(BOARD_ROOT.resolve()):
        raise ValueError(f"共享证据路径逃逸板块目录：{relpath}")
    return path


def compare_csv_rows(
    observed_path: Path,
    expected_fields: Sequence[str],
    expected_rows: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    observed_fields, observed_rows = read_csv(observed_path)
    differences: list[dict[str, Any]] = []
    for index, (observed, expected) in enumerate(zip(observed_rows, expected_rows)):
        for field in expected_fields:
            if observed.get(field) != expected.get(field):
                differences.append(
                    {
                        "row": index,
                        "field": field,
                        "expected": expected.get(field),
                        "actual": observed.get(field),
                    }
                )
                if len(differences) == 20:
                    break
        if len(differences) == 20:
            break
    return {
        "pass": observed_fields == list(expected_fields)
        and len(observed_rows) == len(expected_rows)
        and not differences,
        "expected_fields": list(expected_fields),
        "actual_fields": observed_fields,
        "expected_rows": len(expected_rows),
        "actual_rows": len(observed_rows),
        "differences": differences,
    }


def filtered_source(
    source: Path, predicate: Any
) -> tuple[list[str], list[dict[str, str]]]:
    fields, rows = read_csv(source)
    return fields, [row for row in rows if predicate(row)]


def verify_publication_contract(checks: Checks) -> dict[str, Any]:
    actual_hash = sha256_file(PUBLICATION_CONTRACT_PATH)
    checks.add(
        "contract",
        "第七步发布合同SHA-256与冻结权威值一致",
        actual_hash == EXPECTED_PUBLICATION_CONTRACT_SHA256,
        EXPECTED_PUBLICATION_CONTRACT_SHA256,
        actual_hash,
        relative_to_project(PUBLICATION_CONTRACT_PATH),
    )
    contract = read_json(PUBLICATION_CONTRACT_PATH)
    object_ids = [record.get("object_id") for record in contract.get("objects", [])]
    checks.add(
        "contract",
        "发布合同模式、四对象顺序、固定网格与不可变科学裁决闭合",
        contract.get("schema_version") == "BOARD20_STEP7_PUBLICATION_CONTRACT_V1"
        and object_ids == ["F4-4", "F4-5", "C05", "C07"]
        and contract.get("fixed_grid", {}).get("point_count") == 2077
        and contract.get("fixed_grid", {}).get("axis_intercept_rule")
        == "ORIGIN_CONNECTED_CONTIGUOUS_PREFIX_LAST_STABLE_INDEX_NO_HOLE_CROSSING"
        and contract.get("immutable_scientific_dispositions", {}).get(
            "scientific_object_gate"
        )
        == "FAIL_RETAIN_PLOTTING_LEVEL"
        and contract.get("immutable_scientific_dispositions", {}).get(
            "formal_success_directory_count"
        )
        == 0
        and contract.get("immutable_scientific_dispositions", {}).get(
            "failure_package_count"
        )
        == 4,
        {
            "schema": "BOARD20_STEP7_PUBLICATION_CONTRACT_V1",
            "objects": ["F4-4", "F4-5", "C05", "C07"],
            "point_count": 2077,
            "scientific_object_gate": "FAIL_RETAIN_PLOTTING_LEVEL",
            "success": 0,
            "failure": 4,
        },
        {
            "schema": contract.get("schema_version"),
            "objects": object_ids,
            "point_count": contract.get("fixed_grid", {}).get("point_count"),
            "scientific_object_gate": contract.get(
                "immutable_scientific_dispositions", {}
            ).get("scientific_object_gate"),
            "success": contract.get("immutable_scientific_dispositions", {}).get(
                "formal_success_directory_count"
            ),
            "failure": contract.get("immutable_scientific_dispositions", {}).get(
                "failure_package_count"
            ),
        },
        relative_to_project(PUBLICATION_CONTRACT_PATH),
    )
    return contract


def verify_step6_seal(contract: Mapping[str, Any], checks: Checks) -> None:
    sealed = contract["sealed_hashes"]
    paths = {
        "step6_run1_manifest_sha256": STEP6_RUN1 / "artifact_manifest.csv",
        "step6_run2_manifest_sha256": STEP6_RUN2 / "artifact_manifest.csv",
        "step6_validation_manifest_sha256": STEP6_VALIDATION / "artifact_manifest.csv",
        "step6_validation_summary_sha256": STEP6_VALIDATION / "validation_summary.json",
        "step6_generator_sha256": STEP6_GENERATOR,
        "step6_validator_sha256": STEP6_VALIDATOR,
        "step6_contract_sha256": STEP6_CONTRACT,
    }
    failures: list[dict[str, str]] = []
    for key, path in paths.items():
        actual = sha256_file(path) if path.is_file() else "MISSING"
        if actual != sealed[key]:
            failures.append({"key": key, "expected": sealed[key], "actual": actual})
    receipt_path = BOARD_ROOT / "logs" / "step6_history_comparison" / "clean_probe_record.json"
    receipt_hash = sha256_file(receipt_path) if receipt_path.is_file() else "MISSING"
    receipt_payload = read_json(receipt_path) if receipt_path.is_file() else {}
    if receipt_hash != sealed["step6_clean_probe_receipt_sha256"]:
        failures.append(
            {
                "key": "step6_clean_probe_receipt_sha256",
                "expected": sealed["step6_clean_probe_receipt_sha256"],
                "actual": receipt_hash,
            }
        )
    if receipt_payload.get("action_id") != sealed["step6_clean_probe_action_id"]:
        failures.append(
            {
                "key": "step6_clean_probe_action_id",
                "expected": sealed["step6_clean_probe_action_id"],
                "actual": str(receipt_payload.get("action_id", "MISSING")),
            }
        )
    checks.add(
        "step6_seal",
        "第六步两轮清单、验证清单/摘要、清洁探针动作/收据、生成器、验收器和合同的封存身份均未漂移",
        not failures,
        [],
        failures,
        "board20_step7_publication_contract.json | sealed_hashes",
    )

    for label, root in (
        ("step6_run1", STEP6_RUN1),
        ("step6_run2", STEP6_RUN2),
        ("step6_validation", STEP6_VALIDATION),
    ):
        fields, rows = read_csv(root / "artifact_manifest.csv")
        files = output_files(root)
        actual_names = sorted(name for name in files if name != "artifact_manifest.csv")
        listed_names = [row["relpath"] for row in rows]
        bad: list[str] = []
        for row in rows:
            path = root / Path(row["relpath"])
            if (
                not path.is_file()
                or path.stat().st_size != int(row["bytes"])
                or sha256_file(path) != row["sha256"]
            ):
                bad.append(row["relpath"])
        checks.add(
            "step6_manifest",
            f"{label}清单覆盖全部非清单文件且逐项字节数/SHA-256闭合",
            fields == ["relpath", "bytes", "sha256"]
            and listed_names == actual_names
            and len(listed_names) == len(set(listed_names))
            and not bad,
            {"fields": ["relpath", "bytes", "sha256"], "bad": []},
            {
                "fields": fields,
                "listed": len(listed_names),
                "actual": len(actual_names),
                "unique": len(listed_names) == len(set(listed_names)),
                "bad": bad,
            },
            relative_to_project(root / "artifact_manifest.csv"),
        )

    files1 = output_files(STEP6_RUN1)
    files2 = output_files(STEP6_RUN2)
    names1 = sorted(files1)
    names2 = sorted(files2)
    mismatches = [
        name
        for name in sorted(set(names1) & set(names2))
        if files1[name].stat().st_size != files2[name].stat().st_size
        or sha256_file(files1[name]) != sha256_file(files2[name])
    ]
    checks.add(
        "step6_repeatability",
        "第六步两轮26项提交树文件集合和逐文件SHA-256一致",
        names1 == names2 and len(names1) == 26 and not mismatches,
        {"file_count": 26, "same_names": True, "mismatches": []},
        {
            "run1_count": len(names1),
            "run2_count": len(names2),
            "same_names": names1 == names2,
            "mismatches": mismatches,
        },
        "outputs/step6_history_comparison_run1 | run2",
    )

    run_summary = read_json(STEP6_RUN1 / "run_summary.json")
    validation_summary = read_json(STEP6_VALIDATION / "validation_summary.json")
    checks.add(
        "step6_status",
        "第六步生成107 PASS+8 INFO且独立验收64/64，科学对象门仍为失败并保留绘图级",
        run_summary.get("check_summary")
        == {"fail": 0, "info": 8, "pass": 107, "total": 115}
        and run_summary.get("object_gate_status") == "FAIL_RETAIN_PLOTTING_LEVEL"
        and validation_summary.get("check_summary")
        == {"fail": 0, "pass": 64, "total": 64}
        and validation_summary.get("scientific_object_gate_status")
        == "FAIL_RETAIN_PLOTTING_LEVEL"
        and validation_summary.get("protected_file_count") == 163,
        {
            "generator": "107 PASS + 8 INFO + 0 FAIL",
            "validator": "64/64 PASS",
            "object_gate": "FAIL_RETAIN_PLOTTING_LEVEL",
            "protected": 163,
        },
        {
            "generator": run_summary.get("check_summary"),
            "validator": validation_summary.get("check_summary"),
            "object_gate": validation_summary.get("scientific_object_gate_status"),
            "protected": validation_summary.get("protected_file_count"),
        },
        relative_to_project(STEP6_VALIDATION / "validation_summary.json"),
    )

    step6_contract = read_json(STEP6_CONTRACT)
    bindings = step6_contract.get("input_bindings", [])
    binding_paths: list[str] = []
    binding_failures: list[dict[str, Any]] = []
    for record in bindings:
        relpath = str(record["relpath"])
        binding_paths.append(relpath)
        path = resolve_board_relative(relpath)
        actual_size = path.stat().st_size if path.is_file() else -1
        actual_hash = sha256_file(path) if path.is_file() else "MISSING"
        if actual_size != int(record["bytes"]) or actual_hash != record["sha256"]:
            binding_failures.append(
                {
                    "relpath": relpath,
                    "expected_size": record["bytes"],
                    "actual_size": actual_size,
                    "expected_hash": record["sha256"],
                    "actual_hash": actual_hash,
                }
            )
    checks.add(
        "step6_input_bindings",
        "第六步合同32项输入绑定路径唯一并按字节数/SHA-256逐项复核",
        len(bindings) == 32
        and len(binding_paths) == len(set(binding_paths))
        and not binding_failures,
        {"count": 32, "unique": True, "failures": []},
        {
            "count": len(bindings),
            "unique": len(binding_paths) == len(set(binding_paths)),
            "failures": binding_failures,
        },
        relative_to_project(STEP6_CONTRACT),
    )


def verify_protected_files(checks: Checks) -> None:
    fields, rows = read_csv(STEP5_PROTECTED)
    relpaths = [row["relpath"] for row in rows]
    failures: list[dict[str, str]] = []
    for row in rows:
        path = resolve_board_relative(row["relpath"])
        current = sha256_file(path) if path.is_file() else "MISSING"
        valid = (
            row["sha256_before"] == row["sha256_after"] == current
            and bool_text(row["unchanged"])
        )
        if not valid:
            failures.append(
                {
                    "relpath": row["relpath"],
                    "before": row["sha256_before"],
                    "after": row["sha256_after"],
                    "current": current,
                    "unchanged": row["unchanged"],
                }
            )
    category_counts = Counter(Path(relpath).parts[0] for relpath in relpaths)
    checks.add(
        "protected_files",
        "第六步继承的163项保护源（47代码、6日志、110输出）路径唯一且当前SHA-256未漂移",
        fields == ["relpath", "sha256_before", "sha256_after", "unchanged"]
        and len(rows) == 163
        and len(relpaths) == len(set(relpaths))
        and category_counts == {"code": 47, "logs": 6, "outputs": 110}
        and not failures,
        {
            "fields": ["relpath", "sha256_before", "sha256_after", "unchanged"],
            "count": 163,
            "categories": {"code": 47, "logs": 6, "outputs": 110},
            "failures": [],
        },
        {
            "fields": fields,
            "count": len(rows),
            "unique": len(relpaths) == len(set(relpaths)),
            "categories": dict(category_counts),
            "failures": failures[:20],
        },
        relative_to_project(STEP5_PROTECTED),
    )


def verify_protected_papers(contract: Mapping[str, Any], checks: Checks) -> None:
    sealed = contract["sealed_hashes"]
    actual_thesis = sha256_file(THESIS_PATH) if THESIS_PATH.is_file() else "MISSING"
    actual_manuscript = (
        sha256_file(MANUSCRIPT_PATH) if MANUSCRIPT_PATH.is_file() else "MISSING"
    )
    checks.add(
        "protected_papers",
        "梁禹硕士论文与manuscript_0824.tex保护哈希均未改变",
        sealed["thesis_sha256"]
        == EXPECTED_THESIS_SHA256
        == actual_thesis
        and sealed["manuscript_sha256"]
        == EXPECTED_MANUSCRIPT_SHA256
        == actual_manuscript,
        {
            "thesis": EXPECTED_THESIS_SHA256,
            "manuscript": EXPECTED_MANUSCRIPT_SHA256,
        },
        {"thesis": actual_thesis, "manuscript": actual_manuscript},
        f"{THESIS_PATH} | {MANUSCRIPT_PATH}",
    )


def verify_no_links(package: Path, object_id: str, checks: Checks) -> None:
    failures: list[dict[str, Any]] = []
    items = [package, *sorted(package.rglob("*"), key=lambda path: path.as_posix())]
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    for path in items:
        metadata = path.lstat()
        is_reparse = bool(getattr(metadata, "st_file_attributes", 0) & reparse_flag)
        is_link = path.is_symlink() or os.path.islink(path)
        hardlink_count = metadata.st_nlink if path.is_file() else 1
        if is_reparse or is_link or hardlink_count != 1:
            failures.append(
                {
                    "relative_path": "."
                    if path == package
                    else path.relative_to(package).as_posix(),
                    "is_symlink": is_link,
                    "is_reparse": is_reparse,
                    "hardlink_count": hardlink_count,
                }
            )
    checks.add(
        "filesystem_safety",
        f"{object_id}失败证据包不含符号链接、硬链接或Windows重解析点",
        not failures,
        [],
        failures,
        relative_to_project(package),
    )


def verify_package_manifest(object_id: str, package: Path, checks: Checks) -> None:
    manifest_path = package / "artifact_manifest.csv"
    fields, rows = read_csv(manifest_path)
    listed = [row["relative_path"] for row in rows]
    files = output_files(package)
    actual = sorted(
        (name for name in files if name != "artifact_manifest.csv"), key=str.casefold
    )
    failures: list[dict[str, Any]] = []
    for row in rows:
        relpath = row["relative_path"]
        pure = Path(relpath)
        if pure.is_absolute() or ".." in pure.parts:
            failures.append({"relative_path": relpath, "reason": "UNSAFE_PATH"})
            continue
        path = package / pure
        actual_size = path.stat().st_size if path.is_file() else -1
        actual_hash = sha256_file(path) if path.is_file() else "MISSING"
        if (
            actual_size != int(row["size_bytes"])
            or actual_hash != row["sha256"]
            or not row["role"]
        ):
            failures.append(
                {
                    "relative_path": relpath,
                    "expected_size": row["size_bytes"],
                    "actual_size": actual_size,
                    "expected_hash": row["sha256"],
                    "actual_hash": actual_hash,
                    "role": row["role"],
                }
            )
    checks.add(
        "package_manifest",
        f"{object_id}工件清单覆盖除自身外全部文件且逐项字节数/SHA-256/角色闭合",
        fields == ARTIFACT_FIELDS
        and listed == actual
        and len(listed) == len(set(listed))
        and not failures,
        {"fields": ARTIFACT_FIELDS, "listed_equals_actual": True, "failures": []},
        {
            "fields": fields,
            "listed_count": len(listed),
            "actual_count": len(actual),
            "listed_equals_actual": listed == actual,
            "unique": len(listed) == len(set(listed)),
            "failures": failures[:20],
        },
        relative_to_project(manifest_path),
    )


def verify_shared_bindings(object_id: str, package: Path, checks: Checks) -> None:
    path = package / "shared_evidence_manifest.csv"
    fields, rows = read_csv(path)
    central_paths: list[str] = []
    failures: list[dict[str, Any]] = []
    for row in rows:
        central_relpath = row["central_relative_path"]
        central_paths.append(central_relpath)
        try:
            central = resolve_board_relative(central_relpath)
            actual_size = central.stat().st_size if central.is_file() else -1
            actual_hash = sha256_file(central) if central.is_file() else "MISSING"
        except (OSError, ValueError) as error:
            actual_size = -1
            actual_hash = f"ERROR:{error}"
        valid = (
            row["object_id"] == object_id
            and row["copy_policy"] == "SHARED_HASH_BOUND_REFERENCE"
            and bool(row["source_step"])
            and bool(row["role"])
            and bool(row["scope_note"])
            and actual_size == int(row["size_bytes"])
            and actual_hash == row["sha256"]
        )
        if not valid:
            failures.append(
                {
                    "central_relative_path": central_relpath,
                    "object_id": row["object_id"],
                    "copy_policy": row["copy_policy"],
                    "expected_size": row["size_bytes"],
                    "actual_size": actual_size,
                    "expected_hash": row["sha256"],
                    "actual_hash": actual_hash,
                }
            )
    checks.add(
        "shared_bindings",
        f"{object_id}共享证据绑定字段固定、路径唯一且中央文件字节数/SHA-256逐项闭合",
        fields == SHARED_FIELDS
        and bool(rows)
        and len(central_paths) == len(set(central_paths))
        and not failures,
        {
            "fields": SHARED_FIELDS,
            "nonempty": True,
            "unique": True,
            "failures": [],
        },
        {
            "fields": fields,
            "row_count": len(rows),
            "unique": len(central_paths) == len(set(central_paths)),
            "failures": failures[:20],
        },
        relative_to_project(path),
    )


def expected_package_csvs(
    object_id: str,
) -> list[tuple[str, list[str], list[dict[str, str]]]]:
    result: list[tuple[str, list[str], list[dict[str, str]]]] = []

    def add(
        destination_name: str, source: Path, predicate: Any = lambda row: True
    ) -> None:
        fields, rows = filtered_source(source, predicate)
        result.append((destination_name, fields, rows))

    if object_id in {"F4-4", "F4-5"}:
        spec = OBJECT_SPECS[object_id]
        figure_id = str(spec["figure_id"])
        route_ids = set(spec["route_ids"])
        add(
            f"{object_id}_对象门.csv",
            STEP6_TABLES / "figure_status.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_三方法目标格.csv",
            STEP6_TABLES / "target_cell_status.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_路线资格.csv",
            STEP6_TABLES / "route_eligibility.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_混淆矩阵.csv",
            STEP6_TABLES / "confusion_matrix.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_稳定域指标.csv",
            STEP6_TABLES / "stability_metrics.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_逐点比较.csv",
            STEP6_TABLES / "pointwise_comparison.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_来源边界.csv",
            STEP6_TABLES / "boundary_by_source.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_候选减历史边界.csv",
            STEP6_TABLES / "boundary_difference.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        add(
            f"{object_id}_绘图样式与证据分层.csv",
            STEP6_RUN1 / "figure_style_manifest.csv",
            lambda row: row["figure_id"] == figure_id,
        )
        step2_sources = [
            (
                "route_summary.csv",
                BOARD_ROOT / "outputs" / "step2_audit" / "route_summary.csv",
            ),
            (
                "alternative_route_summary.csv",
                BOARD_ROOT
                / "outputs"
                / "step2_audit"
                / "alternative_route_summary.csv",
            ),
        ]
        step2_fields: list[str] | None = None
        step2_rows: list[dict[str, str]] = []
        for source_label, source_path in step2_sources:
            fields, rows = read_csv(source_path)
            if step2_fields is None:
                step2_fields = fields
            elif fields != step2_fields:
                raise RuntimeError("步骤2主路线与替代路线摘要表头不一致。")
            step2_rows.extend(
                {"source_table": source_label, **row}
                for row in rows
                if row["route_id"] in route_ids
            )
        result.append(
            (
                f"{object_id}_步骤2作者路线终态.csv",
                ["source_table", *(step2_fields or [])],
                step2_rows,
            )
        )
        add(
            f"{object_id}_步骤4连续rho网格摘要.csv",
            BOARD_ROOT / "outputs" / "step4_audit" / "route_grid_summary.csv",
            lambda row: row["route_id"] in route_ids,
        )
        add(
            f"{object_id}_步骤5独立交叉验证摘要.csv",
            STEP5_PROTECTED.parent / "v5_full_validator_full_postcheck_route_summary.csv",
            lambda row: row["route_id"] in route_ids,
        )
        if object_id == "F4-5":
            add(
                "第二类两标签载荷关系.csv",
                STEP6_TABLES / "div2_payload_relation_audit.csv",
            )
            add(
                "第二类共同网格外序列摘要.csv",
                STEP6_TABLES / "extension_summary.csv",
            )
            add(
                "第二类共同网格外1至28逐点.csv",
                STEP6_TABLES / "extension_1_to_28_audit.csv",
            )
    elif object_id == "C05":
        add(
            "C05_临界时滞声明与裁决.csv",
            STEP6_TABLES / "claim_C05_C07.csv",
            lambda row: "C05" in row["claim_ids"].split(";"),
        )
        add("C05_两图对象门.csv", STEP6_TABLES / "figure_status.csv")
        add("C05_六方法目标格.csv", STEP6_TABLES / "target_cell_status.csv")
        add("C05_稳定域指标.csv", STEP6_TABLES / "stability_metrics.csv")
        add("C05_混淆矩阵.csv", STEP6_TABLES / "confusion_matrix.csv")
    elif object_id == "C07":
        result.append(("C07_组件范围裁决.csv", C07_SCOPE_FIELDS, C07_SCOPE_ROWS))
        add(
            "C07_临界时滞声明与未评价项.csv",
            STEP6_TABLES / "claim_C05_C07.csv",
        )
        add("C07_两图对象门.csv", STEP6_TABLES / "figure_status.csv")
        add("C07_六方法目标格.csv", STEP6_TABLES / "target_cell_status.csv")
        add("C07_稳定域指标.csv", STEP6_TABLES / "stability_metrics.csv")
        add("C07_混淆矩阵.csv", STEP6_TABLES / "confusion_matrix.csv")
    else:
        raise ValueError(object_id)
    return result


def verify_package_csvs(object_id: str, package: Path, checks: Checks) -> None:
    for filename, expected_fields, expected_rows in expected_package_csvs(object_id):
        observed = package / "data" / filename
        result = compare_csv_rows(observed, expected_fields, expected_rows)
        checks.add(
            "package_csv",
            f"{object_id}：{filename}与中央权威表的固定筛选结果逐字段逐行一致",
            bool(result["pass"]),
            {
                "fields": expected_fields,
                "rows": len(expected_rows),
                "differences": [],
            },
            {
                "fields": result["actual_fields"],
                "rows": result["actual_rows"],
                "differences": result["differences"],
            },
            relative_to_project(observed),
        )


def verify_visuals(object_id: str, package: Path, checks: Checks) -> None:
    stems = list(OBJECT_SPECS[object_id]["figure_stems"])
    copy_failures: list[dict[str, str]] = []
    quality_failures: list[dict[str, Any]] = []
    for stem in stems:
        for extension in ("pdf", "png"):
            source = STEP6_RUN1 / "figures" / f"{stem}.{extension}"
            target = package / "figures" / f"{stem}.{extension}"
            source_hash = sha256_file(source) if source.is_file() else "MISSING"
            target_hash = sha256_file(target) if target.is_file() else "MISSING"
            if (
                not source.is_file()
                or not target.is_file()
                or source.stat().st_size != target.stat().st_size
                or source_hash != target_hash
            ):
                copy_failures.append(
                    {
                        "artifact": f"{stem}.{extension}",
                        "source_hash": source_hash,
                        "target_hash": target_hash,
                    }
                )
        source_render = STEP6_VALIDATION / "rendered_pdf_review" / f"{stem}.png"
        target_render = package / "visual" / "rendered_pdf_review" / f"{stem}.png"
        if (
            not source_render.is_file()
            or not target_render.is_file()
            or source_render.stat().st_size != target_render.stat().st_size
            or sha256_file(source_render) != sha256_file(target_render)
        ):
            copy_failures.append({"artifact": f"rendered_pdf_review/{stem}.png"})

        pdf_path = package / "figures" / f"{stem}.pdf"
        png_path = package / "figures" / f"{stem}.png"
        try:
            reader = PdfReader(str(pdf_path))
            pdf_ok = len(reader.pages) == 1 and not reader.is_encrypted
        except Exception as error:  # pragma: no cover - records malformed external artifact
            pdf_ok = False
            quality_failures.append({"stem": stem, "pdf_error": str(error)})
        try:
            with Image.open(png_path) as image:
                dpi = image.info.get("dpi", (0.0, 0.0))
                png_ok = (
                    image.format == "PNG"
                    and image.size == (4488, 2010)
                    and image.mode == "RGBA"
                    and math.isclose(float(dpi[0]), 599.9988, abs_tol=0.02)
                    and math.isclose(float(dpi[1]), 599.9988, abs_tol=0.02)
                )
        except Exception as error:  # pragma: no cover - records malformed external artifact
            png_ok = False
            quality_failures.append({"stem": stem, "png_error": str(error)})
        if not pdf_ok or not png_ok:
            quality_failures.append(
                {"stem": stem, "single_page_unencrypted_pdf": pdf_ok, "png_gate": png_ok}
            )

    checks.add(
        "visual_copy",
        f"{object_id}图件、PNG和180 dpi PDF重渲染均与第六步中央产物字节/SHA-256一致",
        not copy_failures,
        [],
        copy_failures,
        relative_to_project(package / "figures"),
    )
    checks.add(
        "visual_quality",
        f"{object_id}所含PDF均为单页未加密，PNG均为4488×2010 RGBA且约600 dpi",
        not quality_failures,
        [],
        quality_failures,
        relative_to_project(package / "figures"),
    )

    quality_source = STEP6_VALIDATION / "figure_quality.csv"
    quality_fields, quality_rows = filtered_source(
        quality_source, lambda row: row["stem"] in stems
    )
    quality_target = package / "visual" / f"{object_id}_图件质量.csv"
    quality_result = compare_csv_rows(quality_target, quality_fields, quality_rows)
    checks.add(
        "visual_quality_record",
        f"{object_id}图件质量记录与第六步对应行全字段一致且全部通过",
        bool(quality_result["pass"])
        and len(quality_rows) == len(stems)
        and all(bool_text(row["quality_gate_pass"]) for row in quality_rows),
        {"rows": len(stems), "all_pass": True, "differences": []},
        {
            "rows": quality_result["actual_rows"],
            "all_pass": all(bool_text(row["quality_gate_pass"]) for row in quality_rows),
            "differences": quality_result["differences"],
        },
        relative_to_project(quality_target),
    )

    manual_source = STEP6_VALIDATION / "manual_visual_review.csv"
    manual_fields, manual_rows = filtered_source(
        manual_source, lambda row: Path(row["figure_pdf"]).stem in stems
    )
    manual_target = package / "visual" / f"{object_id}_人工视觉记录.csv"
    manual_result = compare_csv_rows(manual_target, manual_fields, manual_rows)
    manual_gate = all(
        row["status"] == "PASS"
        and bool_text(row["overlap_absent"])
        and bool_text(row["clipping_absent"])
        and bool_text(row["legend_legible"])
        and bool_text(row["evidence_separation_clear"])
        for row in manual_rows
    )
    checks.add(
        "manual_visual_review",
        f"{object_id}人工视觉记录与第六步对应行全字段一致，且重叠/裁切/图例/证据分层全部通过",
        bool(manual_result["pass"])
        and len(manual_rows) == len(stems)
        and manual_gate,
        {"rows": len(stems), "all_pass": True, "differences": []},
        {
            "rows": manual_result["actual_rows"],
            "all_pass": manual_gate,
            "differences": manual_result["differences"],
        },
        relative_to_project(manual_target),
    )


def verify_package_logs(object_id: str, package: Path, checks: Checks) -> None:
    common = [
        (
            STEP6_RUN1 / "run_summary.json",
            package / "logs" / "步骤6运行摘要.json",
        ),
        (
            STEP6_VALIDATION / "validation_summary.json",
            package / "logs" / "步骤6独立验证摘要.json",
        ),
        (
            STEP6_VALIDATION / "repeatability.csv",
            package / "logs" / "两轮重复性.csv",
        ),
    ]
    mappings = list(common)
    if object_id in {"F4-4", "F4-5"}:
        division = "div1" if object_id == "F4-4" else "div2"
        route_id = f"main_cb_{division}"
        destination = package / "logs" / "Craig-Bampton主路线原样失败"
        for name in (
            "error_report.txt",
            "matlab_command.txt",
            "matlab_diary.log",
            "shell_stdout_stderr.log",
        ):
            mappings.append(
                (
                    BOARD_ROOT
                    / "logs"
                    / "step2_runs"
                    / route_id
                    / "original_mlx"
                    / "rep02"
                    / name,
                    destination / name,
                )
            )
        for name in ("process_exit.json", "run_config.json", "run_status.json"):
            mappings.append(
                (
                    BOARD_ROOT
                    / "outputs"
                    / "step2_runs"
                    / route_id
                    / "original_mlx"
                    / "rep02"
                    / "metadata"
                    / name,
                    destination / name,
                )
            )
    failures: list[dict[str, str]] = []
    for source, target in mappings:
        source_hash = sha256_file(source) if source.is_file() else "MISSING"
        target_hash = sha256_file(target) if target.is_file() else "MISSING"
        if (
            not source.is_file()
            or not target.is_file()
            or source.stat().st_size != target.stat().st_size
            or source_hash != target_hash
        ):
            failures.append(
                {
                    "source": relative_to_project(source),
                    "target": relative_to_project(target),
                    "source_hash": source_hash,
                    "target_hash": target_hash,
                }
            )
    checks.add(
        "package_logs",
        f"{object_id}步骤6摘要/重复性记录"
        + ("及Craig-Bampton七件真实失败现场" if object_id.startswith("F") else "")
        + "均与中央来源逐字节一致",
        not failures,
        [],
        failures,
        relative_to_project(package / "logs"),
    )
    if object_id in {"F4-4", "F4-5"}:
        cb_log_root = package / "logs" / "Craig-Bampton主路线原样失败"
        error_text = (cb_log_root / "error_report.txt").read_text(
            encoding="utf-8", errors="replace"
        )
        run_status = read_json(cb_log_root / "run_status.json")
        error_record = run_status.get("error", {})
        checks.add(
            "craig_bampton_failure",
            f"{object_id}保留Craig-Bampton主路线MRren未定义的真实MATLAB失败，不伪造连续rho",
            "MRren" in error_text
            and run_status.get("final_status") == "EXECUTION_FAIL"
            and run_status.get("execution_status") == "EXECUTION_FAIL"
            and error_record.get("identifier") == "MATLAB:UndefinedFunction"
            and "MRren" in str(error_record.get("message", "")),
            {
                "error_report_contains": "MRren",
                "identifier": "MATLAB:UndefinedFunction",
                "final_status": "EXECUTION_FAIL",
                "execution_status": "EXECUTION_FAIL",
            },
            {
                "error_report_contains_MRren": "MRren" in error_text,
                "identifier": error_record.get("identifier"),
                "message": error_record.get("message"),
                "final_status": run_status.get("final_status"),
                "execution_status": run_status.get("execution_status"),
            },
            f"{relative_to_project(cb_log_root / 'error_report.txt')} | "
            f"{relative_to_project(cb_log_root / 'run_status.json')}",
        )


def verify_package_docs(object_id: str, package: Path, checks: Checks) -> None:
    readme_path = package / "README.md"
    rerun_path = package / "code" / "复现入口.md"
    summary_path = package / "package_summary.json"
    readme = readme_path.read_text(encoding="utf-8")
    rerun = rerun_path.read_text(encoding="utf-8")
    summary = read_json(summary_path)
    required = ["失败证据", "正式成功目录", OBJECT_SPECS[object_id]["final_evidence"]]
    if object_id.startswith("F"):
        required.extend(["Craig–Bampton", "计算级"])
    elif object_id == "C05":
        required.extend(["约5", "接近10", "原点连续"])
    else:
        required.extend(["临界时滞", "频率", "幅值", "NOT_EVALUATED"])
    missing = [marker for marker in required if marker not in readme]
    checks.add(
        "package_docs",
        f"{object_id}自包含README明确失败、成功目录边界和证据等级",
        not missing and len(readme.encode("utf-8")) > 800,
        {"missing": [], "minimum_utf8_bytes": 801},
        {"missing": missing, "utf8_bytes": len(readme.encode("utf-8"))},
        relative_to_project(readme_path),
    )
    rerun_markers = [
        "D:/Software/python/python.exe",
        "analyze_board20_step6_history_comparison.py",
        "validate_board20_step6_history_comparison.py",
    ]
    rerun_missing = [marker for marker in rerun_markers if marker not in rerun]
    checks.add(
        "package_docs",
        f"{object_id}复现入口明确使用固定Python和第六步生成/独立验收入口",
        not rerun_missing,
        [],
        rerun_missing,
        relative_to_project(rerun_path),
    )
    summary_text = json.dumps(summary, ensure_ascii=False, sort_keys=True)
    checks.add(
        "package_summary",
        f"{object_id}机器摘要标记失败证据已发布、正式成功目录不存在且证据等级不越级",
        summary.get("object_id") == object_id
        and summary.get("status") == "FAILURE_EVIDENCE_PACKAGED"
        and summary.get("formal_success_directory_exists") is False
        and str(OBJECT_SPECS[object_id]["final_evidence"]) in summary_text,
        {
            "object_id": object_id,
            "status": "FAILURE_EVIDENCE_PACKAGED",
            "formal_success_directory_exists": False,
            "evidence_contains": OBJECT_SPECS[object_id]["final_evidence"],
        },
        summary,
        relative_to_project(summary_path),
    )


def verify_scientific_semantics(contract: Mapping[str, Any], checks: Checks) -> None:
    _, pointwise = read_csv(STEP6_TABLES / "pointwise_comparison.csv")
    _, route_rows = read_csv(STEP6_TABLES / "route_eligibility.csv")
    _, target_rows = read_csv(STEP6_TABLES / "target_cell_status.csv")
    _, confusion_rows = read_csv(STEP6_TABLES / "confusion_matrix.csv")
    _, metric_rows = read_csv(STEP6_TABLES / "stability_metrics.csv")
    _, figure_rows = read_csv(STEP6_TABLES / "figure_status.csv")
    _, claim_rows = read_csv(STEP6_TABLES / "claim_C05_C07.csv")

    row_counts = {
        "pointwise": len(pointwise),
        "route": len(route_rows),
        "target": len(target_rows),
        "confusion": len(confusion_rows),
        "metrics": len(metric_rows),
        "figures": len(figure_rows),
        "claims": len(claim_rows),
    }
    checks.add(
        "scientific_counts",
        "中央科学表行数固定为10385/7/6/7/11/2/10",
        row_counts
        == {
            "pointwise": 10385,
            "route": 7,
            "target": 6,
            "confusion": 7,
            "metrics": 11,
            "figures": 2,
            "claims": 10,
        },
        {
            "pointwise": 10385,
            "route": 7,
            "target": 6,
            "confusion": 7,
            "metrics": 11,
            "figures": 2,
            "claims": 10,
        },
        row_counts,
        relative_to_project(STEP6_TABLES),
    )

    expected_figure = {
        "F4-4": ("div1", 3, 2, 0),
        "F4-5": ("div2", 3, 2, 0),
    }
    figure_failures: list[dict[str, str]] = []
    for row in figure_rows:
        expected = expected_figure.get(row["figure_id"])
        if expected is None or not (
            row["division"] == expected[0]
            and int(row["method_cell_count"]) == expected[1]
            and int(row["primary_continuous_rho_cell_count"]) == expected[2]
            and int(row["exact_mask_match_cell_count"]) == expected[3]
            and not bool_text(row["calculation_level_figure_gate_pass"])
            and row["object_evidence_level"] == "PLOTTING_LEVEL_REPRODUCTION"
            and not bool_text(row["formal_success_directory_allowed"])
        ):
            figure_failures.append(row)
    checks.add(
        "scientific_gate",
        "图4-4和图4-5均为2/3主连续rho路线、0/3精确掩膜，计算级门失败并保留绘图级",
        len(figure_rows) == 2 and not figure_failures,
        [],
        figure_failures,
        relative_to_project(STEP6_TABLES / "figure_status.csv"),
    )

    contract_by_id = {row["object_id"]: row for row in contract["objects"]}
    mismatch_actual = {
        row["route_id"]: int(row["mask_mismatch_points"])
        for row in confusion_rows
        if row["route_id"] and row["mask_mismatch_points"]
    }
    expected_mismatch: dict[str, int] = {}
    for object_id in ("F4-4", "F4-5"):
        expected_mismatch.update(contract_by_id[object_id]["expected_mask_mismatch"])
    mismatch_subset = {key: mismatch_actual.get(key) for key in expected_mismatch}
    checks.add(
        "scientific_mismatch",
        "Original/Guyan主路线及第一类Guyan替代路线掩膜错配数精确为1389/951/1037/1213/895",
        mismatch_subset == expected_mismatch,
        expected_mismatch,
        mismatch_subset,
        relative_to_project(STEP6_TABLES / "confusion_matrix.csv"),
    )

    target_expected = {
        ("F4-4", "Original"): (1454, 1389),
        ("F4-4", "Craig-Bampton"): (1175, None),
        ("F4-4", "Guyan"): (1044, 951),
        ("F4-5", "Original"): (1247, 1213),
        ("F4-5", "Craig-Bampton"): (1072, None),
        ("F4-5", "Guyan"): (929, 895),
    }
    target_actual = {
        (row["figure_id"], row["method"]): (
            int(row["historical_stable_points"]),
            int(row["mask_mismatch_points"])
            if row["mask_mismatch_points"]
            else None,
        )
        for row in target_rows
    }
    checks.add(
        "scientific_targets",
        "六个方法目标格的历史稳定点数和主路线错配数精确闭合，Craig-Bampton保持路线缺失",
        target_actual == target_expected
        and all(not bool_text(row["calculation_level_target_gate_pass"]) for row in target_rows)
        and sum(row["target_status"] == "MISSING_PRIMARY_CONTINUOUS_RHO" for row in target_rows)
        == 2,
        target_expected,
        target_actual,
        relative_to_project(STEP6_TABLES / "target_cell_status.csv"),
    )

    route_point_counts = Counter(row["route_id"] for row in pointwise)
    checks.add(
        "scientific_pointwise",
        "五条可计算路线各有2077点，Craig-Bampton两条必需主路线明确不可计算且没有伪造逐点rho",
        route_point_counts
        == {
            "main_ori_div1": 2077,
            "main_guyan_div1": 2077,
            "alt_guyan_div1_stable_full_ps3": 2077,
            "main_ori_div2": 2077,
            "main_guyan_div2": 2077,
        }
        and sum(row["availability"] == "NOT_COMPUTABLE_MISSING_ROUTE" for row in route_rows)
        == 2
        and all(
            row["candidate_point_count"] == "0"
            for row in route_rows
            if row["availability"] == "NOT_COMPUTABLE_MISSING_ROUTE"
        ),
        {
            "five_routes_each": 2077,
            "missing_cb_routes": 2,
            "fabricated_cb_points": 0,
        },
        {"route_point_counts": dict(route_point_counts)},
        relative_to_project(STEP6_TABLES / "pointwise_comparison.csv"),
    )

    delay_claims = [row for row in claim_rows if "C05" in row["claim_ids"].split(";")]
    out_of_scope = [
        row
        for row in claim_rows
        if row["claim_ids"] == "C07_FREQUENCY_AND_AMPLITUDE_COMPONENTS"
    ]
    axis_rule = "ORIGIN_CONNECTED_CONTIGUOUS_PREFIX_LAST_STABLE_INDEX_NO_HOLE_CROSSING"
    checks.add(
        "c05_scope",
        "C05九行临界时滞裁决全部采用原点连续前缀且不得跨孔洞，均禁止计算级升级",
        len(delay_claims) == 9
        and all(row["axis_intercept_definition"] == axis_rule for row in delay_claims)
        and all(not bool_text(row["eligible_for_calculation_level_upgrade"]) for row in delay_claims)
        and all(row["qualitative_tolerance_status"] == "QUALITATIVE_TOLERANCE_UNDEFINED" for row in delay_claims),
        {"rows": 9, "axis_rule": axis_rule, "upgrade": False},
        {
            "rows": len(delay_claims),
            "axis_rules": sorted({row["axis_intercept_definition"] for row in delay_claims}),
            "upgrade_true": sum(bool_text(row["eligible_for_calculation_level_upgrade"]) for row in delay_claims),
        },
        relative_to_project(STEP6_TABLES / "claim_C05_C07.csv"),
    )
    checks.add(
        "c07_scope",
        "C07仅临界时滞分量被审计；频率区间和响应幅值明确未评价且不得升级",
        len(out_of_scope) == 1
        and out_of_scope[0]["evidence_source"] == "OUT_OF_SCOPE"
        and out_of_scope[0]["qualitative_tolerance_status"] == "NOT_EVALUATED_IN_STEP6"
        and out_of_scope[0]["route_or_mask_closure"] == "OUTSIDE_BOARD20_STABILITY_SCOPE"
        and not bool_text(out_of_scope[0]["eligible_for_calculation_level_upgrade"]),
        {
            "rows": 1,
            "status": "NOT_EVALUATED_IN_STEP6",
            "upgrade": False,
        },
        out_of_scope,
        relative_to_project(STEP6_TABLES / "claim_C05_C07.csv"),
    )


def verify_index(contract: Mapping[str, Any], checks: Checks) -> None:
    pre_hash = sha256_file(INDEX_PRE)
    pre_fields, pre_rows = read_csv(INDEX_PRE)
    live_fields, live_rows = read_csv(INDEX_LIVE)
    contract_by_id = {record["object_id"]: record for record in contract["objects"]}
    changes: list[dict[str, str]] = []
    if len(pre_rows) == len(live_rows):
        for pre_row, live_row in zip(pre_rows, live_rows):
            for field in INDEX_FIELDS:
                if pre_row[field] != live_row[field]:
                    changes.append(
                        {
                            "object_id": pre_row["对象ID"],
                            "field": field,
                            "before": pre_row[field],
                            "after": live_row[field],
                        }
                    )
    expected_pairs = {
        (object_id, field)
        for object_id in OBJECT_SPECS
        for field in ("当前状态", "备注")
    }
    actual_pairs = {(change["object_id"], change["field"]) for change in changes}
    target_values_ok = all(
        change["after"]
        == contract_by_id[change["object_id"]][
            "index_current_status" if change["field"] == "当前状态" else "index_note"
        ]
        for change in changes
        if (change["object_id"], change["field"]) in expected_pairs
    )
    preserved_cells = len(pre_rows) * len(INDEX_FIELDS) - len(changes)
    checks.add(
        "index_evolution",
        "45×15总索引只改变四个目标对象的当前状态和备注共8格，其余667/675格逐字保留",
        pre_hash == EXPECTED_PRE_INDEX_SHA256
        and pre_fields == live_fields == INDEX_FIELDS
        and len(pre_rows) == len(live_rows) == 45
        and [row["对象ID"] for row in pre_rows] == [row["对象ID"] for row in live_rows]
        and len(changes) == 8
        and actual_pairs == expected_pairs
        and target_values_ok
        and preserved_cells == 667,
        {
            "pre_hash": EXPECTED_PRE_INDEX_SHA256,
            "shape": [45, 15],
            "changed_cells": 8,
            "changed_pairs": sorted(expected_pairs),
            "preserved_cells": 667,
            "target_values_match_contract": True,
        },
        {
            "pre_hash": pre_hash,
            "pre_shape": [len(pre_rows), len(pre_fields)],
            "live_shape": [len(live_rows), len(live_fields)],
            "changed_cells": len(changes),
            "changed_pairs": sorted(actual_pairs),
            "preserved_cells": preserved_cells,
            "target_values_match_contract": target_values_ok,
        },
        f"{relative_to_project(INDEX_PRE)} -> {relative_to_project(INDEX_LIVE)}",
    )

    live_by_id = {row["对象ID"]: row for row in live_rows}
    failures: list[dict[str, Any]] = []
    for object_id, spec in OBJECT_SPECS.items():
        row = live_by_id[object_id]
        expected_failure = relative_to_project(package_root(object_id))
        expected_success = relative_to_project(success_root(object_id))
        if not (
            row["当前证据等级"] == spec["final_evidence"]
            and row["目标证据等级"] == "计算级复现"
            and row["失败尝试目录"] == expected_failure
            and row["成功文件夹"] == expected_success
        ):
            failures.append(
                {
                    "object_id": object_id,
                    "current_evidence": row["当前证据等级"],
                    "target_evidence": row["目标证据等级"],
                    "failure": row["失败尝试目录"],
                    "success": row["成功文件夹"],
                }
            )
    checks.add(
        "index_paths",
        "四对象证据等级、正式成功路径和失败证据路径与固定目录完全一致",
        not failures,
        [],
        failures,
        relative_to_project(INDEX_LIVE),
    )


def verify_documents(checks: Checks) -> None:
    documents: list[tuple[Path, list[str]]] = [
        (
            TEST_ROOT / "README.md",
            ["板块20", "最小步骤7", "绘图级复现", "历史值"],
        ),
        (
            TEST_ROOT / "00_总索引与复现规则" / "README.md",
            ["板块20", "最小步骤7", "历史基线", "禁止"],
        ),
        (
            TEST_ROOT / "00_总索引与复现规则" / "验收记录.md",
            ["板块20", "最小步骤7", "FAIL_RETAIN_PLOTTING_LEVEL", "667"],
        ),
        (
            FAILURE_ROOT / "README.md",
            [
                "板块20",
                "最小步骤7",
                *[str(spec["package_name"]) for spec in OBJECT_SPECS.values()],
            ],
        ),
        (
            PROJECT_ROOT / "Ref" / "notes" / "Liang2025_实时混合试验缩聚与稳定性.md",
            ["板块20", "最小步骤7", "图4-4", "图4-5", "C05", "C07", "未评价"],
        ),
        (
            PROJECT_ROOT / "WORKFLOW.md",
            ["板块20", "最小步骤7", "FAIL_RETAIN_PLOTTING_LEVEL"],
        ),
    ]
    for path, markers in documents:
        text = path.read_text(encoding="utf-8") if path.is_file() else ""
        missing = [marker for marker in markers if marker not in text]
        checks.add(
            "documentation",
            f"{path.name}包含第七步终态所需的对象、证据等级或禁止覆盖边界",
            path.is_file() and not missing,
            {"exists": True, "missing": []},
            {"exists": path.is_file(), "missing": missing},
            relative_to_project(path),
        )


def verify_package_set(contract: Mapping[str, Any], checks: Checks) -> None:
    contract_by_id = {record["object_id"]: record for record in contract["objects"]}
    present_successes: list[str] = []
    missing_failures: list[str] = []
    for object_id in OBJECT_SPECS:
        package = package_root(object_id)
        success = success_root(object_id)
        if success.exists():
            present_successes.append(relative_to_project(success))
        if not package.is_dir():
            missing_failures.append(relative_to_project(package))
        expected_package_name = contract_by_id[object_id]["package_name"]
        checks.add(
            "fixed_roots",
            f"{object_id}合同包名与验收器硬编码失败目录一致",
            package.name == expected_package_name,
            expected_package_name,
            package.name,
            relative_to_project(PUBLICATION_CONTRACT_PATH),
        )
    checks.add(
        "scope_control",
        "四个失败证据目录全部存在，四个正式成功目录全部不存在",
        not missing_failures and not present_successes,
        {"failure_packages": 4, "success_directories": 0},
        {
            "failure_packages": 4 - len(missing_failures),
            "missing_failure_packages": missing_failures,
            "success_directories": present_successes,
        },
        relative_to_project(TEST_ROOT),
    )

    for object_id in OBJECT_SPECS:
        package = package_root(object_id)
        verify_no_links(package, object_id, checks)
        verify_package_manifest(object_id, package, checks)
        verify_shared_bindings(object_id, package, checks)
        verify_package_csvs(object_id, package, checks)
        verify_visuals(object_id, package, checks)
        verify_package_logs(object_id, package, checks)
        verify_package_docs(object_id, package, checks)


def prepare_output_root(checks: Checks) -> None:
    expected = {"checks.csv", "validation_summary.json", "artifact_manifest.csv"}
    if OUTPUT_ROOT.exists() and not OUTPUT_ROOT.is_dir():
        raise RuntimeError(f"固定验收输出路径不是目录：{OUTPUT_ROOT}")
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    actual = {
        path.relative_to(OUTPUT_ROOT).as_posix()
        for path in OUTPUT_ROOT.rglob("*")
        if path.is_file()
    }
    unexpected = sorted(actual - expected)
    checks.add(
        "output_scope",
        "固定验收输出目录不存在额外文件，支持在原三件输出上确定性重复执行",
        not unexpected,
        [],
        unexpected,
        relative_to_project(OUTPUT_ROOT),
    )


def write_outputs(contract: Mapping[str, Any], checks: Checks) -> dict[str, Any]:
    summary = checks.summary()
    payload = {
        "schema_version": "BOARD20_STEP7_INDEPENDENT_VALIDATION_V1",
        "overall_status": "PASS" if summary["fail"] == 0 else "FAIL",
        "check_summary": summary,
        "validator_sha256": sha256_file(SCRIPT_PATH),
        "publication_contract_sha256": sha256_file(PUBLICATION_CONTRACT_PATH),
        "step6_run1_manifest_sha256": sha256_file(
            STEP6_RUN1 / "artifact_manifest.csv"
        ),
        "step6_run2_manifest_sha256": sha256_file(
            STEP6_RUN2 / "artifact_manifest.csv"
        ),
        "step6_validation_manifest_sha256": sha256_file(
            STEP6_VALIDATION / "artifact_manifest.csv"
        ),
        "index_pre_snapshot_sha256": sha256_file(INDEX_PRE),
        "index_live_sha256": sha256_file(INDEX_LIVE),
        "failure_package_count": sum(
            package_root(object_id).is_dir() for object_id in OBJECT_SPECS
        ),
        "formal_success_directory_count": sum(
            success_root(object_id).exists() for object_id in OBJECT_SPECS
        ),
        "scientific_object_gate": contract["immutable_scientific_dispositions"][
            "scientific_object_gate"
        ],
        "f4_4_final_evidence_level": "绘图级复现",
        "f4_5_final_evidence_level": "绘图级复现",
        "c05_final_evidence_level": "历史值",
        "c07_final_evidence_level": "历史值",
        "c07_frequency_bands": "NOT_EVALUATED",
        "c07_response_amplitude_errors": "NOT_EVALUATED",
        "next_board_started": False,
    }
    write_csv(
        OUTPUT_ROOT / "checks.csv",
        ["check_id", "category", "description", "status", "expected", "actual", "evidence"],
        checks.rows,
    )
    write_json(OUTPUT_ROOT / "validation_summary.json", payload)
    manifest_rows: list[dict[str, Any]] = []
    for filename, role in (
        ("checks.csv", "independent_validation_checks"),
        ("validation_summary.json", "independent_validation_summary"),
    ):
        path = OUTPUT_ROOT / filename
        manifest_rows.append(
            {
                "relative_path": filename,
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "role": role,
            }
        )
    write_csv(OUTPUT_ROOT / "artifact_manifest.csv", ARTIFACT_FIELDS, manifest_rows)
    actual = sorted(output_files(OUTPUT_ROOT))
    if actual != ["artifact_manifest.csv", "checks.csv", "validation_summary.json"]:
        raise RuntimeError(f"验收输出文件集合漂移：{actual}")
    manifest_fields, observed_manifest = read_csv(OUTPUT_ROOT / "artifact_manifest.csv")
    if manifest_fields != ARTIFACT_FIELDS or observed_manifest != [
        {field: csv_value(row[field]) for field in ARTIFACT_FIELDS}
        for row in manifest_rows
    ]:
        raise RuntimeError("验收输出工件清单回读不一致。")
    return payload


def main() -> int:
    checks = Checks()
    prepare_output_root(checks)
    contract = verify_publication_contract(checks)
    verify_step6_seal(contract, checks)
    verify_protected_files(checks)
    verify_protected_papers(contract, checks)
    verify_scientific_semantics(contract, checks)
    verify_package_set(contract, checks)
    verify_index(contract, checks)
    verify_documents(checks)
    payload = write_outputs(contract, checks)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    if payload["overall_status"] != "PASS":
        failed = [row["check_id"] for row in checks.rows if row["status"] == "FAIL"]
        raise SystemExit(f"Board20最小步骤7独立验收失败：{failed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

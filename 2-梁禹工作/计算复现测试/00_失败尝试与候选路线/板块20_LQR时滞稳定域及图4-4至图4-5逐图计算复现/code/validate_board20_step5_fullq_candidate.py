#!/usr/bin/env python
"""Independent read-only validator for the stopped Board20 Step-5 v2 candidate.

V2 is intentionally not a successful solver candidate: its sealed preflight
passed, but its sealed synthetic selftest has six fixed-gate failures.  This
validator preserves that state, proves that no pilot/full computation exists,
and protects the first compact validator and solver-conditioning diagnosis.

The script never writes inside ``outputs/step5_fullq_candidate`` and never
changes a Step-4, Step-5, validator, or conditioning artifact.
"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import h5py


BOARD_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
CONTRACT_PATH = SCRIPT_PATH.with_name(
    "board20_step5_fullq_candidate_validation_contract.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def resolve_relpath(relpath: str) -> Path:
    path = (BOARD_ROOT / relpath).resolve()
    path.relative_to(BOARD_ROOT.resolve())
    return path


def relpath(path: Path) -> str:
    return path.resolve().relative_to(BOARD_ROOT.resolve()).as_posix()


def format_csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    return str(value)


def write_csv(path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: format_csv_value(row.get(field)) for field in fields})


@dataclass
class Audit:
    checks: list[dict[str, Any]] = field(default_factory=list)

    def add(
        self,
        category: str,
        description: str,
        expected: Any,
        actual: Any,
        passed: bool,
        evidence: str = "",
        information: bool = False,
    ) -> None:
        status = "INFO" if information else ("PASS" if passed else "FAIL")
        self.checks.append(
            {
                "check_id": f"S5FQ-V2-{len(self.checks) + 1:04d}",
                "category": category,
                "description": description,
                "expected": expected,
                "actual": actual,
                "status": status,
                "evidence": evidence,
            }
        )

    @property
    def failed(self) -> list[dict[str, Any]]:
        return [check for check in self.checks if check["status"] == "FAIL"]

    @property
    def passed_count(self) -> int:
        return sum(check["status"] == "PASS" for check in self.checks)

    @property
    def information_count(self) -> int:
        return sum(check["status"] == "INFO" for check in self.checks)


def expected_hash_paths(contract: Mapping[str, Any]) -> dict[Path, str]:
    paths = contract["paths"]
    seals = contract["sealed_candidate_identity"]
    revision = contract["preseal_revision_identity"]
    result = {
        resolve_relpath(paths["candidate_contract"]): seals["candidate_contract_sha256"],
        resolve_relpath(paths["candidate_script"]): seals["candidate_script_sha256"],
        resolve_relpath(paths["base_compute"]): seals["base_compute_sha256"],
        resolve_relpath(paths["route_manifest"]): seals["route_manifest_sha256"],
        resolve_relpath(paths["draft_v1"]): revision["draft_preserved_sha256"],
        resolve_relpath(paths["revision_record"]): revision["revision_record_sha256"],
        resolve_relpath("outputs/step5_fullq_candidate/input_seal.json"): seals[
            "input_seal_sha256"
        ],
        resolve_relpath("outputs/step5_fullq_candidate/preflight.json"): seals[
            "preflight_sha256"
        ],
        resolve_relpath("outputs/step5_fullq_candidate/selftest.json"): seals[
            "selftest_sha256"
        ],
        resolve_relpath("outputs/step5_fullq_candidate/contracts_status.json"): seals[
            "contracts_status_sha256"
        ],
    }
    for relative, expected in contract["protected_prior_evidence"].items():
        result[resolve_relpath(relative)] = expected
    return result


def hash_snapshot(paths: Sequence[Path]) -> dict[str, str]:
    return {relpath(path): sha256_file(path) for path in sorted(paths, key=relpath)}


def check_hash_seals(
    audit: Audit, expected: Mapping[Path, str]
) -> tuple[dict[str, str], list[str]]:
    observed: dict[str, str] = {}
    failures: list[str] = []
    for path, expected_hash in sorted(expected.items(), key=lambda item: relpath(item[0])):
        relative = relpath(path)
        if not path.is_file():
            actual = "MISSING"
            failures.append(relative)
        else:
            actual = sha256_file(path)
            if actual != expected_hash:
                failures.append(relative)
        observed[relative] = actual
    audit.add(
        "sealed_identity",
        "v2候选、预封签修订、第一次验收和条件性诊断的SHA-256均保持封签值",
        {relpath(path): value for path, value in sorted(expected.items(), key=lambda item: relpath(item[0]))},
        {"failures": failures, "observed": observed},
        not failures,
    )
    return observed, failures


def check_revision_history(audit: Audit, contract: Mapping[str, Any]) -> None:
    draft_path = resolve_relpath(contract["paths"]["draft_v1"])
    revision_path = resolve_relpath(contract["paths"]["revision_record"])
    formal_path = resolve_relpath(contract["paths"]["candidate_contract"])
    draft = read_json(draft_path)
    revision = read_json(revision_path)
    formal = read_json(formal_path)
    expected = contract["preseal_revision_identity"]

    audit.add(
        "preseal_revision",
        "v1草稿保留为PRESEAL_DRAFT_SUPERSEDED且记录原始预注释哈希",
        {
            "draft_status": "PRESEAL_DRAFT_SUPERSEDED",
            "original": expected["draft_original_pre_annotation_sha256"],
        },
        {
            "draft_status": draft.get("draft_status"),
            "original": draft.get("original_pre_annotation_sha256"),
        },
        draft.get("draft_status") == "PRESEAL_DRAFT_SUPERSEDED"
        and draft.get("original_pre_annotation_sha256")
        == expected["draft_original_pre_annotation_sha256"],
        relpath(draft_path),
    )
    audit.add(
        "preseal_revision",
        "v2修订明确发生在输入封签和任何科学求解之前，且不是结果后放宽门槛",
        {
            "timing": expected["required_revision_timing"],
            "gate_relaxation_after_results": False,
            "scientific_results_existed_when_revised": False,
        },
        {
            "timing": revision.get("revision_timing"),
            "gate_relaxation_after_results": revision.get("gate_relaxation_after_results"),
            "scientific_results_existed_when_revised": revision.get(
                "scientific_results_existed_when_revised"
            ),
        },
        revision.get("revision_timing") == expected["required_revision_timing"]
        and revision.get("gate_relaxation_after_results") is False
        and revision.get("scientific_results_existed_when_revised") is False,
        relpath(revision_path),
    )
    audit.add(
        "preseal_revision",
        "正式v2合同只替代预封签v1草稿并绑定同一草稿身份",
        {
            "schema": "board20_step5_fullq_candidate_contract_v2",
            "status": "FORMAL_PRESEAL_V2",
            "draft_original": expected["draft_original_pre_annotation_sha256"],
        },
        {
            "schema": formal.get("schema_version"),
            "status": formal.get("contract_status"),
            "draft_original": formal.get("supersedes", {}).get(
                "draft_original_pre_annotation_sha256"
            ),
        },
        formal.get("schema_version") == "board20_step5_fullq_candidate_contract_v2"
        and formal.get("contract_status") == "FORMAL_PRESEAL_V2"
        and formal.get("supersedes", {}).get("draft_original_pre_annotation_sha256")
        == expected["draft_original_pre_annotation_sha256"],
        relpath(formal_path),
    )


def selected_algorithm_ast_identity(source: str) -> dict[str, Any]:
    tree = ast.parse(source)
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "selected_algorithm"
        ),
        None,
    )
    if function is None:
        return {"present": False}
    arguments = [argument.arg for argument in function.args.args]
    names = sorted({node.id for node in ast.walk(function) if isinstance(node, ast.Name)})
    calls = sorted(
        {
            ast.unparse(node.func)
            for node in ast.walk(function)
            if isinstance(node, ast.Call)
        }
    )
    returns = [ast.unparse(node.value) for node in ast.walk(function) if isinstance(node, ast.Return)]
    return {
        "present": True,
        "arguments": arguments,
        "names": names,
        "calls": calls,
        "returns": returns,
    }


def check_source_isolation(audit: Audit, contract: Mapping[str, Any]) -> None:
    source_path = resolve_relpath(contract["paths"]["candidate_script"])
    source = source_path.read_text(encoding="utf-8")
    normalized = source.replace("\\", "/").lower()
    forbidden = [
        literal
        for literal in contract["forbidden_candidate_input_literals"]
        if literal.lower() in normalized
    ]
    audit.add(
        "source_isolation",
        "候选计算源码不含步骤4数值网格、旧步骤5、validator或条件性诊断答案路径",
        [],
        forbidden,
        not forbidden,
        relpath(source_path),
    )
    dangerous = [
        token
        for token in ("matlab.engine", "subprocess.run", "subprocess.Popen", "os.system")
        if token in source
    ]
    audit.add(
        "source_isolation",
        "候选计算源码不调用MATLAB求解器或外部进程复制答案",
        [],
        dangerous,
        not dangerous,
        relpath(source_path),
    )
    identity = selected_algorithm_ast_identity(source)
    allowed_names = {
        "matrix_order",
        "ALGORITHM_FULL_Q",
        "ALGORITHM_COMPACT",
        "int",
        "str",
    }
    passed = (
        identity.get("present") is True
        and identity.get("arguments") == ["matrix_order"]
        and not identity.get("calls")
        and set(identity.get("names", [])) <= allowed_names
        and identity.get("returns")
        == ["ALGORITHM_FULL_Q if matrix_order <= 5 else ALGORITHM_COMPACT"]
    )
    audit.add(
        "algorithm_identity",
        "selected_algorithm源码只由matrix_order<=5唯一决定，无路线或结果覆盖",
        {
            "arguments": ["matrix_order"],
            "calls": [],
            "return": "ALGORITHM_FULL_Q if matrix_order <= 5 else ALGORITHM_COMPACT",
        },
        identity,
        passed,
        relpath(source_path),
    )


def matlab73_shape(path: Path, dataset: str) -> tuple[int, ...]:
    with h5py.File(path, "r") as file:
        shape = tuple(int(value) for value in file[dataset].shape)
    return tuple(reversed(shape)) if len(shape) >= 2 else shape


def check_candidate_contract(audit: Audit, validation: Mapping[str, Any]) -> None:
    candidate_path = resolve_relpath(validation["paths"]["candidate_contract"])
    candidate = read_json(candidate_path)
    rules = validation["candidate_contract_rules"]
    routes = candidate.get("routes", [])
    route_map = {route["route_id"]: route for route in routes}
    pilot = candidate.get("pilot_points", {})
    pilot_total = sum(len(points) for points in pilot.values())
    audit.add(
        "route_contract",
        "候选合同精确登记五条文件身份路线和49个不重复试点",
        {"routes": 5, "pilot_points": 49},
        {
            "routes": len(routes),
            "pilot_points": pilot_total,
            "unique_by_route": {
                route_id: len(points) == len({tuple(point) for point in points})
                for route_id, points in pilot.items()
            },
        },
        len(routes) == rules["route_count"]
        and pilot_total == rules["pilot_total_points"]
        and all(len(points) == len({tuple(point) for point in points}) for points in pilot.values()),
        relpath(candidate_path),
    )
    expected_algorithms = rules["matrix_order_to_algorithm"]
    observed_algorithms: dict[str, Any] = {}
    identity_failures: list[str] = []
    required_four = {tuple(point) for point in rules["required_original_outlier_points"]}
    four_point_failures: list[str] = []
    for route_id, expected in expected_algorithms.items():
        route = route_map.get(route_id)
        if route is None:
            identity_failures.append(f"{route_id}:missing")
            continue
        workspace = resolve_relpath(route["workspace_relpath"])
        dataset = route["matrix_variables"]["M"]
        shape = matlab73_shape(workspace, dataset)
        matrix_order = shape[0] if len(shape) == 2 and shape[0] == shape[1] else -1
        algorithm = (
            "FULL_Q_ORDINARY_HISTORY_COMPANION"
            if matrix_order <= 5
            else "COMPACT_SCALAR_DELAY_AUGMENTATION"
        )
        observed_algorithms[route_id] = [matrix_order, algorithm]
        if [matrix_order, algorithm] != expected:
            identity_failures.append(route_id)
        if matrix_order <= 5 and not required_four.issubset(
            {tuple(point) for point in pilot.get(route_id, [])}
        ):
            four_point_failures.append(route_id)
    audit.add(
        "algorithm_identity",
        "五条路线的实际matrix_order唯一选择预登记算法",
        expected_algorithms,
        {"observed": observed_algorithms, "failures": identity_failures},
        not identity_failures,
        relpath(candidate_path),
    )
    audit.add(
        "pilot_contract",
        "四条5阶full-q路线的49点试点集合均包含四个原超差坐标",
        sorted(required_four),
        {"failures": four_point_failures},
        not four_point_failures,
        relpath(candidate_path),
    )
    full_grid = candidate.get("full_grid", {})
    audit.add(
        "grid_contract",
        "候选全网格合同保持五路线各31x67、总10385点",
        {"shape": [31, 67], "total": 10385},
        {"shape": full_grid.get("shape"), "total": full_grid.get("total_points")},
        full_grid.get("shape") == rules["full_grid_shape"]
        and full_grid.get("total_points") == rules["full_total_points"],
        relpath(candidate_path),
    )
    selection = candidate.get("algorithm_selection", {})
    audit.add(
        "algorithm_identity",
        "算法合同禁止路线/点覆盖和MATLAB结果依赖选择",
        {
            "selector": "matrix_order",
            "route_or_point_override_allowed": False,
            "matlab_result_dependent_selection_allowed": False,
        },
        {
            "selector": selection.get("selector_field"),
            "route_or_point_override_allowed": selection.get(
                "route_or_point_override_allowed"
            ),
            "matlab_result_dependent_selection_allowed": selection.get(
                "matlab_result_dependent_selection_allowed"
            ),
        },
        selection.get("selector_field") == "matrix_order"
        and selection.get("route_or_point_override_allowed") is False
        and selection.get("matlab_result_dependent_selection_allowed") is False,
        relpath(candidate_path),
    )


def check_candidate_contract_status(audit: Audit, validation: Mapping[str, Any]) -> None:
    path = resolve_relpath("outputs/step5_fullq_candidate/contracts_status.json")
    document = read_json(path)
    failed_expected = set(validation["candidate_contract_rules"]["failed_route_ids"])
    failed_entries = document.get("noncomputable_failed_routes", [])
    failed_actual = {entry.get("route_id") for entry in failed_entries}
    failed_pass = (
        failed_actual == failed_expected
        and all(entry.get("candidate_policy") == "DO_NOT_CREATE" for entry in failed_entries)
        and all(entry.get("candidate_status") == "CONTRACT_NOT_EXECUTABLE" for entry in failed_entries)
    )
    audit.add(
        "failed_routes",
        "四条上游失败路线在v2仍为CONTRACT_NOT_EXECUTABLE/DO_NOT_CREATE",
        sorted(failed_expected),
        {
            "ids": sorted(item for item in failed_actual if item is not None),
            "entries": failed_entries,
        },
        failed_pass,
        relpath(path),
    )
    scientific = document.get("scientific_contracts", {})
    paper_statuses = {
        "master_thesis_route": scientific.get("master_thesis_route", {}).get("status"),
        "manuscript_0824_route": scientific.get("manuscript_0824_route", {}).get("status"),
    }
    audit.add(
        "paper_contract",
        "硕士论文和manuscript_0824公式路线仍为CONTRACT_NOT_CLOSED",
        {
            "master_thesis_route": "CONTRACT_NOT_CLOSED",
            "manuscript_0824_route": "CONTRACT_NOT_CLOSED",
        },
        paper_statuses,
        set(paper_statuses.values()) == {"CONTRACT_NOT_CLOSED"},
        relpath(path),
    )


def check_candidate_preflight(audit: Audit, validation: Mapping[str, Any]) -> None:
    path = resolve_relpath("outputs/step5_fullq_candidate/preflight.json")
    document = read_json(path)
    expected = validation["expected_candidate_preflight"]
    actual = {
        key: document.get(key)
        for key in ("schema_version", "status", "check_count", "pass_count", "fail_count")
    }
    inner_failures = [
        check.get("check_id") for check in document.get("checks", []) if check.get("status") != "PASS"
    ]
    passed = actual == expected and not inner_failures and len(document.get("checks", [])) == 45
    audit.add(
        "candidate_preflight",
        "候选自身输入预检封签为45/45 PASS",
        expected,
        {"summary": actual, "inner_failures": inner_failures},
        passed,
        relpath(path),
    )


def check_input_seal(audit: Audit, validation: Mapping[str, Any]) -> None:
    path = resolve_relpath("outputs/step5_fullq_candidate/input_seal.json")
    seal = read_json(path)
    expected = validation["sealed_candidate_identity"]
    actual = {
        "candidate_contract_sha256": seal.get("candidate_contract_sha256"),
        "candidate_script_sha256": seal.get("candidate_script_sha256"),
        "base_compute_sha256": seal.get("base_compute_sha256"),
        "route_manifest_sha256": seal.get("route_manifest_sha256"),
        "route_count": len(seal.get("route_order", [])),
    }
    passed = (
        actual["candidate_contract_sha256"] == expected["candidate_contract_sha256"]
        and actual["candidate_script_sha256"] == expected["candidate_script_sha256"]
        and actual["base_compute_sha256"] == expected["base_compute_sha256"]
        and actual["route_manifest_sha256"] == expected["route_manifest_sha256"]
        and actual["route_count"] == 5
    )
    audit.add(
        "input_seal",
        "候选输入封签绑定v2合同、候选脚本、基础脚本、路线清单和五路线顺序",
        {
            "candidate_contract_sha256": expected["candidate_contract_sha256"],
            "candidate_script_sha256": expected["candidate_script_sha256"],
            "base_compute_sha256": expected["base_compute_sha256"],
            "route_manifest_sha256": expected["route_manifest_sha256"],
            "route_count": 5,
        },
        actual,
        passed,
        relpath(path),
    )


def check_candidate_selftest(audit: Audit, validation: Mapping[str, Any]) -> list[dict[str, Any]]:
    path = resolve_relpath("outputs/step5_fullq_candidate/selftest.json")
    document = read_json(path)
    expected = validation["expected_candidate_selftest"]
    actual_summary = {
        key: document.get(key)
        for key in ("schema_version", "status", "check_count", "pass_count", "fail_count")
    }
    expected_summary = {
        key: expected[key]
        for key in ("schema_version", "status", "check_count", "pass_count", "fail_count")
    }
    failed = [check for check in document.get("checks", []) if check.get("status") == "FAIL"]
    failed_ids = [check.get("check_id") for check in failed]
    audit.add(
        "candidate_selftest_identity",
        "候选自身合成自测封签身份真实记录57 PASS/6 FAIL",
        {
            "summary": expected_summary,
            "failed_check_ids": expected["failed_check_ids"],
        },
        {"summary": actual_summary, "failed_check_ids": failed_ids},
        actual_summary == expected_summary and failed_ids == expected["failed_check_ids"],
        relpath(path),
    )
    for check in failed:
        audit.add(
            "candidate_selftest_gate",
            f"v2进入pilot前必须通过合成自测：{check['check_id']}",
            "PASS_REQUIRED_BEFORE_PILOT",
            {"candidate_status": "FAIL", "detail": check.get("detail")},
            False,
            relpath(path),
        )
    return failed


def check_no_scientific_outputs(audit: Audit, validation: Mapping[str, Any]) -> None:
    root = resolve_relpath(validation["paths"]["candidate_output_root"])
    mode_dirs = [str(path) for path in (root / "pilot", root / "full") if path.exists()]
    audit.add(
        "stopped_before_pilot",
        "v2因selftest失败未创建pilot或full科学目录",
        [],
        mode_dirs,
        not mode_dirs,
        relpath(root),
    )
    forbidden_ids = validation["candidate_contract_rules"]["failed_route_ids"] + [
        "master_thesis_route",
        "manuscript_0824_route",
    ]
    forbidden_dirs = [
        relpath(path)
        for route_id in forbidden_ids
        for path in root.glob(f"**/{route_id}")
        if path.is_dir()
    ]
    audit.add(
        "forbidden_outputs",
        "四失败路线和两论文合同未闭合路线均无候选科学网格目录",
        [],
        forbidden_dirs,
        not forbidden_dirs,
        relpath(root),
    )


def check_prior_verdicts(audit: Audit) -> None:
    compact_path = resolve_relpath("outputs/step5_audit/full_postcheck.json")
    compact = read_json(compact_path)
    summary = compact.get("summary", {})
    failed_checks = [
        check.get("check_id")
        for check in compact.get("checks", [])
        if check.get("status") == "FAIL"
    ]
    audit.add(
        "prior_compact_verdict",
        "第一次compact全网格validator仍保持2 FAIL",
        {
            "overall_status": "FAIL",
            "failed_checks": 2,
            "ids": ["S5-POST-0095", "S5-POST-0108"],
        },
        {
            "overall_status": summary.get("overall_status"),
            "failed_checks": summary.get("failed_checks"),
            "ids": failed_checks,
        },
        summary.get("overall_status") == "FAIL"
        and summary.get("failed_checks") == 2
        and failed_checks == ["S5-POST-0095", "S5-POST-0108"],
        relpath(compact_path),
    )
    diagnosis_path = resolve_relpath("outputs/step5_solver_conditioning/diagnostic.json")
    diagnosis = read_json(diagnosis_path)
    repeat_path = resolve_relpath(
        "outputs/step5_solver_conditioning/repeatability_check.json"
    )
    repeat = read_json(repeat_path)
    audit.add(
        "prior_conditioning_diagnosis",
        "求解器条件性诊断仍为DIAGNOSTIC_ONLY且没有覆盖第一次validator FAIL",
        {
            "status": "DIAGNOSTIC_ONLY_VALIDATOR_FAIL_UNCHANGED",
            "overridden": False,
            "repeatability": "PASS",
        },
        {
            "status": diagnosis.get("status"),
            "overridden": diagnosis.get("validator_verdict", {}).get("overridden"),
            "repeatability": repeat.get("status"),
        },
        diagnosis.get("status") == "DIAGNOSTIC_ONLY_VALIDATOR_FAIL_UNCHANGED"
        and diagnosis.get("validator_verdict", {}).get("overridden") is False
        and repeat.get("status") == "PASS",
        relpath(diagnosis_path),
    )


def write_report(
    path: Path, summary: Mapping[str, Any], failed_selftests: Sequence[Mapping[str, Any]]
) -> None:
    lines = [
        "# Board20 Step5 full-q第二候选v2独立只读封存审计",
        "",
        f"> 结论：`{summary['overall_status']}`。v2不得进入pilot/full，不改写第一次compact validator的2项FAIL。",
        "",
        "## 人话结论",
        "",
        "- 候选自身preflight：45/45 PASS，说明文件、矩阵、路线和算法选择封签成功。",
        "- 候选自身synthetic selftest：57 PASS / 6 FAIL，所以科学计算必须在pilot之前停止。",
        "- `outputs/step5_fullq_candidate/pilot` 和 `full` 均不存在，没有候选网格可被误认为通过。",
        "- 此审计只封存v2失败现场；未来v3必须使用新合同、新脚本哈希和新验收身份。",
        "",
        "## 六个原门槛失败",
        "",
        "| 候选selftest check_id | 实际值/失败码 |",
        "|---|---:|",
    ]
    for check in failed_selftests:
        lines.append(f"| {check.get('check_id')} | {format_csv_value(check.get('detail'))} |")
    lines.extend(
        [
            "",
            "## 证据保护",
            "",
            "- v1草稿、v2修订记录、v2合同/脚本/输入封签哈希均与预登记值相同。",
            "- 第一次compact全网格验收仍是 `S5-POST-0095` 和 `S5-POST-0108` 两项FAIL。",
            "- 条件性诊断仍是 `DIAGNOSTIC_ONLY_VALIDATOR_FAIL_UNCHANGED`。",
            "- 审计前后所有受保护工件SHA-256完全不变。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_audit_outputs(
    audit: Audit,
    contract: Mapping[str, Any],
    protected_before: Mapping[str, str],
    protected_after: Mapping[str, str],
    failed_selftests: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    output_root = resolve_relpath(contract["paths"]["audit_output_root"])
    log_root = resolve_relpath(contract["paths"]["audit_log_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    unexpected_failures = [
        check
        for check in audit.failed
        if check["category"] != "candidate_selftest_gate"
    ]
    expected_failure_ids = contract["expected_candidate_selftest"]["failed_check_ids"]
    selftest_gate_failures = [
        check for check in audit.failed if check["category"] == "candidate_selftest_gate"
    ]
    expected_stop = (
        not unexpected_failures
        and len(selftest_gate_failures) == 6
        and [check.get("check_id") for check in failed_selftests] == expected_failure_ids
    )
    overall_status = (
        "V2_STOPPED_SELFTEST_FAIL_NO_PILOT"
        if expected_stop
        else "AUDIT_INTEGRITY_FAIL"
    )
    summary = {
        "mode": "precheck",
        "overall_status": overall_status,
        "total_checks": len(audit.checks),
        "passed_checks": audit.passed_count,
        "information_checks": audit.information_count,
        "failed_checks": len(audit.failed),
        "candidate_preflight": "PASS_45_OF_45",
        "candidate_selftest": "FAIL_57_PASS_6_FAIL",
        "pilot_exists": False,
        "full_exists": False,
        "postcheck_authorized": False,
    }
    document = {
        "schema_version": "board20_step5_fullq_candidate_v2_audit_v1",
        "validator": {
            "script_relpath": relpath(SCRIPT_PATH),
            "script_sha256": sha256_file(SCRIPT_PATH),
            "contract_relpath": relpath(CONTRACT_PATH),
            "contract_sha256": sha256_file(CONTRACT_PATH),
        },
        "summary": summary,
        "candidate_lifecycle": contract["candidate_lifecycle"],
        "checks": audit.checks,
        "protected_hashes_before": protected_before,
        "protected_hashes_after": protected_after,
    }
    json_path = output_root / "v2_precheck.json"
    checks_path = output_root / "v2_precheck_checks.csv"
    report_path = output_root / "v2_precheck_report.md"
    hashes_path = output_root / "v2_protected_hashes.csv"
    log_path = log_root / "v2_precheck.log"
    write_json(json_path, document)
    check_fields = (
        "check_id",
        "category",
        "description",
        "expected",
        "actual",
        "status",
        "evidence",
    )
    write_csv(checks_path, audit.checks, check_fields)
    write_report(report_path, summary, failed_selftests)
    hash_rows = [
        {
            "relpath": relative,
            "sha256_before": protected_before[relative],
            "sha256_after": protected_after.get(relative, "MISSING"),
            "unchanged": protected_before[relative]
            == protected_after.get(relative, "MISSING"),
        }
        for relative in sorted(protected_before)
    ]
    write_csv(
        hashes_path,
        hash_rows,
        ("relpath", "sha256_before", "sha256_after", "unchanged"),
    )
    log_lines = [
        canonical_json(
            {
                "check_id": check["check_id"],
                "category": check["category"],
                "status": check["status"],
                "description": check["description"],
            }
        )
        for check in audit.checks
    ]
    log_lines.append(canonical_json(summary))
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8", newline="\n")
    artifact_rows = [
        {
            "relpath": path.relative_to(output_root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": sha256_file(path),
        }
        for path in sorted(
            (json_path, checks_path, report_path, hashes_path),
            key=lambda item: item.relative_to(output_root).as_posix(),
        )
    ]
    write_csv(
        output_root / "v2_precheck_artifact_manifest.csv",
        artifact_rows,
        ("relpath", "bytes", "sha256"),
    )
    return summary


def run_precheck() -> dict[str, Any]:
    contract = read_json(CONTRACT_PATH)
    audit = Audit()
    audit.add(
        "validation_contract",
        "v2独立验证合同schema和停止状态已固定",
        {
            "schema": "board20_step5_fullq_candidate_validation_contract_v1",
            "status": "V2_STOPPED_SELFTEST_FAIL_NO_PILOT",
        },
        {
            "schema": contract.get("schema_version"),
            "status": contract.get("candidate_lifecycle", {}).get("required_status"),
        },
        contract.get("schema_version")
        == "board20_step5_fullq_candidate_validation_contract_v1"
        and contract.get("candidate_lifecycle", {}).get("required_status")
        == "V2_STOPPED_SELFTEST_FAIL_NO_PILOT",
        relpath(CONTRACT_PATH),
    )
    expected_paths = expected_hash_paths(contract)
    protected_before = hash_snapshot(list(expected_paths))
    check_hash_seals(audit, expected_paths)
    check_revision_history(audit, contract)
    check_source_isolation(audit, contract)
    check_candidate_contract(audit, contract)
    check_candidate_contract_status(audit, contract)
    check_candidate_preflight(audit, contract)
    check_input_seal(audit, contract)
    failed_selftests = check_candidate_selftest(audit, contract)
    check_no_scientific_outputs(audit, contract)
    check_prior_verdicts(audit)
    protected_after = hash_snapshot(list(expected_paths))
    changed = [
        relative
        for relative in protected_before
        if protected_before[relative] != protected_after.get(relative)
    ]
    audit.add(
        "immutability",
        "v2审计前后候选、原Step4/Step5、第一次validator和条件性诊断工件哈希完全不变",
        [],
        changed,
        not changed,
    )
    return write_audit_outputs(
        audit,
        contract,
        protected_before,
        protected_after,
        failed_selftests,
    )


def run_stopped_guard(mode: str) -> dict[str, Any]:
    contract = read_json(CONTRACT_PATH)
    candidate_root = resolve_relpath(contract["paths"]["candidate_output_root"])
    mode_name = "pilot" if mode == "pilot-postcheck" else "full"
    exists = (candidate_root / mode_name).exists()
    status = "NOT_AUTHORIZED_V2_STOPPED"
    document = {
        "schema_version": "board20_step5_fullq_candidate_v2_postcheck_guard_v1",
        "mode": mode,
        "status": status,
        "candidate_selftest_status": read_json(candidate_root / "selftest.json").get("status"),
        "mode_directory_exists": exists,
        "reason": "V2 synthetic selftest has six fixed-gate failures; pilot/full postcheck is prohibited even if a directory later appears.",
        "candidate_outputs_modified": False,
    }
    output_root = resolve_relpath(contract["paths"]["audit_output_root"])
    write_json(output_root / f"v2_{mode.replace('-', '_')}_guard.json", document)
    return document


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("precheck", "pilot-postcheck", "full-postcheck"),
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.mode == "precheck":
        summary = run_precheck()
        print(canonical_json(summary))
        return 1 if summary["overall_status"] != "PASS" else 0
    guard = run_stopped_guard(args.mode)
    print(canonical_json(guard))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

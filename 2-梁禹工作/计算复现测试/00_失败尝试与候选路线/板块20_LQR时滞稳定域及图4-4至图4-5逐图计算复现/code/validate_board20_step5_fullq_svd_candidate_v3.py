#!/usr/bin/env python
"""Independent read-only validator V3 for the sealed isolated V4 candidate.

This file is a separate successor version; it never overwrites validator V1,
the permanently failed validator V2, either failed audit, or the failed V3
candidate evidence. A legacy waiting guard remains fail-closed for an unsealed
contract. Under the formal V4 precheck-only seal, ``precheck``
inspects only sealed code, static
candidate gate documents, source workspaces, Step-4 reference identities, and
prior failure evidence; it deliberately does not parse pilot/full scientific
outputs. ``pilot-postcheck`` and ``full-postcheck`` require an explicit CLI
authorization flag and validate already-sealed candidate outputs without ever
launching the candidate computation.

All validator writes are isolated under ``outputs/step5_fullq_svd_candidate_audit_v3``
and ``logs/step5_fullq_svd_candidate_validation_v3``. Candidate, Step-4, original
Step-5, V2-failure, and conditioning-diagnosis files are never modified.
"""

from __future__ import annotations

import argparse
import ast
import copy
import csv
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import h5py
import numpy as np
import scipy.linalg as sla


BOARD_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = Path(__file__).resolve()
CONTRACT_PATH = SCRIPT_PATH.with_name(
    "board20_step5_fullq_svd_candidate_validation_contract_v3.json"
)
VALIDATOR_V1_PATH = SCRIPT_PATH.with_name(
    "validate_board20_step5_fullq_svd_candidate.py"
)
VALIDATOR_V1_SHA256 = "19CCAC6A1630B9A61783326012F207963EA88970E980EEBD018F73D28DEDE8AC"
FAILURE_ATTRIBUTION_PATH = SCRIPT_PATH.with_name(
    "board20_step5_fullq_svd_candidate_validator_v1_failure_attribution.json"
)
FAILURE_ATTRIBUTION_SHA256 = "3B924DBFC48C68651ABEEF9156613EAE891D750B837DEEA9BECC13B140F9271E"
REVISION_RECORD_PATH = SCRIPT_PATH.with_name(
    "board20_step5_fullq_svd_candidate_validator_v3_revision_contract.json"
)
VALIDATOR_V2_PATH = SCRIPT_PATH.with_name(
    "validate_board20_step5_fullq_svd_candidate_v2.py"
)
VALIDATOR_V2_SHA256 = "D6E0111413BD8E51A068AEDDFF509FC8159FC946E51EE1A0DFE53EF9DE2CB4A2"
VALIDATOR_V2_FAILURE_PATH = SCRIPT_PATH.with_name(
    "board20_step5_fullq_svd_candidate_validator_v2_precheck_failure_attribution.json"
)
VALIDATOR_V2_FAILURE_SHA256 = (
    "DD30D9953535DB959EDACEE6327C4FAA85D6284513AEE92B0D6C06A3AE595CBD"
)
FORMAL_CONTRACT_STATUSES = frozenset(
    {"FORMAL_V4_VALIDATOR_V3_SEALED_PRECHECK_ONLY"}
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def json_safe(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        value = float(value)
    if isinstance(value, float):
        if math.isnan(value):
            return "NaN"
        if math.isinf(value):
            return "Inf" if value > 0 else "-Inf"
    return value


def canonical_json(value: Any) -> str:
    return json.dumps(
        json_safe(value),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_json(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def resolve_relpath(relative: str) -> Path:
    path = (BOARD_ROOT / relative).resolve()
    path.relative_to(BOARD_ROOT.resolve())
    return path


def relative(path: Path) -> str:
    return path.resolve().relative_to(BOARD_ROOT.resolve()).as_posix()


def csv_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, (dict, list, tuple)):
        return canonical_json(value)
    return str(value)


def write_csv(
    path: Path, rows: Sequence[Mapping[str, Any]], fields: Sequence[str]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(fields), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({name: csv_value(row.get(name)) for name in fields})


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), [dict(row) for row in reader]


@dataclass
class Audit:
    prefix: str
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
                "check_id": f"{self.prefix}-{len(self.checks) + 1:04d}",
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
        return [item for item in self.checks if item["status"] == "FAIL"]

    @property
    def pass_count(self) -> int:
        return sum(item["status"] == "PASS" for item in self.checks)

    @property
    def info_count(self) -> int:
        return sum(item["status"] == "INFO" for item in self.checks)


def hash_snapshot(paths: Iterable[Path]) -> dict[str, str]:
    unique = sorted({path.resolve() for path in paths}, key=relative)
    return {
        relative(path): sha256_file(path) if path.is_file() else "MISSING"
        for path in unique
    }


def expected_static_hashes(contract: Mapping[str, Any]) -> dict[Path, str]:
    paths = contract["paths"]
    seals = contract["sealed_candidate_identity"]
    result = {
        resolve_relpath(paths["candidate_contract"]): seals["candidate_contract_sha256"],
        resolve_relpath(paths["candidate_script"]): seals["candidate_script_sha256"],
        resolve_relpath(paths["base_compute"]): seals["base_compute_sha256"],
        resolve_relpath(paths["v2_engine"]): seals["v2_engine_sha256"],
        resolve_relpath(paths["route_manifest"]): seals["route_manifest_sha256"],
    }
    static_names = {
        "input_seal.json": "input_seal_sha256",
        "preflight.json": "preflight_sha256",
        "selftest.json": "selftest_sha256",
        "contracts_status.json": "contracts_status_sha256",
        "hard_residual_math.json": "hard_residual_math_sha256",
        "v2_failure_attribution.json": "v2_failure_attribution_sha256",
        "v2_immutability_baseline.json": "v2_immutability_baseline_sha256",
        "v3_failure_attribution.json": "v3_failure_attribution_sha256",
        "v3_immutability_baseline.json": "v3_immutability_baseline_sha256",
        "static_diff_selftest.json": "static_diff_selftest_file_sha256",
    }
    candidate_root = resolve_relpath(paths["candidate_output_root"])
    for filename, key in static_names.items():
        result[candidate_root / filename] = seals[key]
    for mapping_name in ("protected_v2_files", "protected_prior_evidence"):
        for relpath, expected in contract[mapping_name].items():
            result[resolve_relpath(relpath)] = expected
    for record in contract["sealed_step4_references"].values():
        result[resolve_relpath(record["mat_relpath"])] = record["mat_sha256"]
        result[resolve_relpath(record["status_relpath"])] = record["status_sha256"]
    step4_manifest = contract["sealed_step4_audit_manifest"]
    result[resolve_relpath(step4_manifest["relpath"])] = step4_manifest["sha256"]
    return result


def check_expected_hashes(
    audit: Audit, expected: Mapping[Path, str]
) -> dict[str, str]:
    observed: dict[str, str] = {}
    failures: list[str] = []
    for path, expected_hash in sorted(expected.items(), key=lambda item: relative(item[0])):
        actual = sha256_file(path) if path.is_file() else "MISSING"
        observed[relative(path)] = actual
        if actual != expected_hash:
            failures.append(relative(path))
    audit.add(
        "sealed_identity",
        "V4源码/静态门、V3永久失败、V2失败、第一次compact FAIL、条件性诊断及Step-4基准均保持预登记SHA-256",
        {relative(path): value for path, value in sorted(expected.items(), key=lambda item: relative(item[0]))},
        {"mismatch_paths": failures, "observed": observed},
        not failures,
    )
    return observed


def selected_algorithm_ast(source: str) -> dict[str, Any]:
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
    return {
        "present": True,
        "arguments": [argument.arg for argument in function.args.args],
        "names": sorted(
            {node.id for node in ast.walk(function) if isinstance(node, ast.Name)}
        ),
        "calls": sorted(
            {
                ast.unparse(node.func)
                for node in ast.walk(function)
                if isinstance(node, ast.Call)
            }
        ),
        "returns": [
            ast.unparse(node.value)
            for node in ast.walk(function)
            if isinstance(node, ast.Return)
        ],
    }


def top_level_functions(source: str) -> dict[str, ast.FunctionDef]:
    tree = ast.parse(source)
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }


def function_ast_sha256(node: ast.FunctionDef) -> str:
    payload = ast.dump(node, include_attributes=False).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def route_status_merge_positions(source: str) -> dict[str, int | None]:
    function = top_level_functions(source).get("write_route_outputs")
    if function is None:
        return {"identity_unpack_index": None, "schema_version_index": None}
    status_dict = None
    for node in ast.walk(function):
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "status"
                for target in node.targets
            )
            and isinstance(node.value, ast.Dict)
        ):
            status_dict = node.value
            break
    if status_dict is None:
        return {"identity_unpack_index": None, "schema_version_index": None}
    identity_index = None
    schema_index = None
    for index, (key, value) in enumerate(zip(status_dict.keys, status_dict.values)):
        if key is None and isinstance(value, ast.Name) and value.id == "identity":
            identity_index = index
        if isinstance(key, ast.Constant) and key.value == "schema_version":
            schema_index = index
    return {
        "identity_unpack_index": identity_index,
        "schema_version_index": schema_index,
    }


def check_candidate_v4_change_review(
    audit: Audit, validation: Mapping[str, Any]
) -> None:
    review = validation["candidate_v4_change_review"]
    v3_path = resolve_relpath(review["v3_reference_script_relpath"])
    v4_path = resolve_relpath(validation["paths"]["candidate_script"])
    v3_source = v3_path.read_text(encoding="utf-8")
    v4_source = v4_path.read_text(encoding="utf-8")
    v3_functions = top_level_functions(v3_source)
    v4_functions = top_level_functions(v4_source)
    names = review["numeric_function_names"]
    v3_hashes = {
        name: function_ast_sha256(v3_functions[name])
        for name in names
        if name in v3_functions
    }
    v4_hashes = {
        name: function_ast_sha256(v4_functions[name])
        for name in names
        if name in v4_functions
    }
    missing = [
        name for name in names if name not in v3_functions or name not in v4_functions
    ]
    audit.add(
        "v4_change_review",
        "V4九个数值函数AST与V3逐项相同，根/残差/门槛未改",
        review["numeric_function_ast_sha256"],
        {"v3": v3_hashes, "v4": v4_hashes, "missing": missing},
        not missing
        and v3_hashes == v4_hashes == review["numeric_function_ast_sha256"],
        relative(v4_path),
    )
    positions = {
        "v3": route_status_merge_positions(v3_source),
        "v4": route_status_merge_positions(v4_source),
    }
    audit.add(
        "v4_change_review",
        "V4唯一功能修复为route_status先展开checkpoint identity、再写显式route_status schema",
        {
            "v3": review["v3_route_status_merge_positions"],
            "v4": review["v4_route_status_merge_positions"],
        },
        positions,
        positions["v3"] == review["v3_route_status_merge_positions"]
        and positions["v4"] == review["v4_route_status_merge_positions"]
        and positions["v3"]["schema_version_index"]
        < positions["v3"]["identity_unpack_index"]
        and positions["v4"]["identity_unpack_index"]
        < positions["v4"]["schema_version_index"],
        relative(v4_path),
    )
    static_path = resolve_relpath(validation["paths"]["candidate_output_root"]) / (
        "static_diff_selftest.json"
    )
    static_document = read_json(static_path)
    actual = {
        "schema_version": static_document.get("schema_version"),
        "status": static_document.get("status"),
        "v3_reference_script_sha256": static_document.get(
            "v3_reference_script_sha256"
        ),
        "v4_candidate_script_sha256": static_document.get(
            "v4_candidate_script_sha256"
        ),
        "numeric_function_ast_equal": static_document.get(
            "numeric_function_ast_equal"
        ),
        "only_functional_change": static_document.get("only_functional_change"),
    }
    audit.add(
        "v4_change_review",
        "候选自身静态diff封签与独立AST复核相互一致",
        review["static_diff_expected"],
        actual,
        actual == review["static_diff_expected"],
        relative(static_path),
    )


class _PairingRoleNormalizer(ast.NodeTransformer):
    def __init__(self) -> None:
        self.replacement = ast.parse(
            'validation["candidate_contract_rules"]["pairing_diagnostic_role"]',
            mode="eval",
        ).body

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        node.keywords = [
            keyword for keyword in node.keywords if keyword.arg != "field_name"
        ]
        return node

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if node.id == "expected_pairing_role":
            return ast.copy_location(copy.deepcopy(self.replacement), node)
        return node


class _AuditDescriptionNormalizer(ast.NodeTransformer):
    """Normalize only human audit prose; leave executable manifest logic exact."""

    def visit_Call(self, node: ast.Call) -> ast.AST:
        self.generic_visit(node)
        if (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "audit"
            and node.func.attr == "add"
            and len(node.args) >= 2
        ):
            node.args[1] = ast.Constant(value="<AUDIT_DESCRIPTION>")
        return node

def check_validator_revision_whitelist(
    audit: Audit, validation: Mapping[str, Any]
) -> None:
    review = validation["validator_revision_review"]
    v1_source = VALIDATOR_V1_PATH.read_text(encoding="utf-8")
    v2_source = SCRIPT_PATH.read_text(encoding="utf-8")
    v1_functions = top_level_functions(v1_source)
    v2_functions = top_level_functions(v2_source)
    core_hashes_v1 = {
        name: function_ast_sha256(v1_functions[name])
        for name in review["unchanged_scientific_core_functions"]
    }
    core_hashes_v2 = {
        name: function_ast_sha256(v2_functions[name])
        for name in review["unchanged_scientific_core_functions"]
    }
    audit.add(
        "validator_revision",
        "validator V3的24个Step-4索引、Laurent公式、SVD残差、根与安全门数值核心AST与V1完全一致",
        core_hashes_v1,
        core_hashes_v2,
        core_hashes_v1 == core_hashes_v2,
        relative(SCRIPT_PATH),
    )
    manifest_v1 = copy.deepcopy(v1_functions["verify_candidate_manifest"])
    manifest_v3 = copy.deepcopy(v2_functions["verify_candidate_manifest"])
    manifest_v1 = _AuditDescriptionNormalizer().visit(manifest_v1)
    manifest_v3 = _AuditDescriptionNormalizer().visit(manifest_v3)
    ast.fix_missing_locations(manifest_v1)
    ast.fix_missing_locations(manifest_v3)
    manifest_body_equal = ast.dump(
        manifest_v1, include_attributes=False
    ) == ast.dump(manifest_v3, include_attributes=False)
    operational = validation["operational_manifest_review"]
    postcheck = validation["postcheck"]
    expected_path_count = (
        validation["candidate_contract_rules"]["route_count"]
        * len(postcheck["route_scientific_files"])
        + len(postcheck["mode_scientific_files"])
    )
    operational_actual = {
        "executable_body_equal_after_audit_prose_normalization": manifest_body_equal,
        "manifest_fields": postcheck["scientific_manifest_fields"],
        "manifest_row_count": postcheck["scientific_manifest_row_count"],
        "derived_exact_path_count": expected_path_count,
        "route_scientific_files": postcheck["route_scientific_files"],
        "mode_scientific_files": postcheck["mode_scientific_files"],
        "requires_exact_relpath_order_no_extra": operational[
            "requires_exact_relpath_order_no_extra"
        ],
        "requires_declared_bytes_and_sha256_match": operational[
            "requires_declared_bytes_and_sha256_match"
        ],
    }
    operational_expected = {
        "executable_body_equal_after_audit_prose_normalization": True,
        "manifest_fields": operational["manifest_fields"],
        "manifest_row_count": operational["manifest_row_count"],
        "derived_exact_path_count": operational["manifest_row_count"],
        "route_scientific_files": operational["route_scientific_files"],
        "mode_scientific_files": operational["mode_scientific_files"],
        "requires_exact_relpath_order_no_extra": True,
        "requires_declared_bytes_and_sha256_match": True,
    }
    audit.add(
        "validator_operational_manifest",
        "verify_candidate_manifest仅规范化人类报告文字，可执行体与V1严格等价，且精确要求18路径/字节/SHA无额外项",
        operational_expected,
        operational_actual,
        operational_actual == operational_expected,
        relative(SCRIPT_PATH),
    )
    v2_scalar = copy.deepcopy(v2_functions["scalar_equal"])
    scalar_shape = (
        len(v2_scalar.args.args) >= 1
        and v2_scalar.args.args[-1].arg == "field_name"
        and len(v2_scalar.args.defaults) >= 1
        and isinstance(v2_scalar.body[0], ast.FunctionDef)
        and v2_scalar.body[0].name == "missing"
        and isinstance(v2_scalar.body[1], ast.If)
    )
    if scalar_shape:
        v2_scalar.args.args = v2_scalar.args.args[:-1]
        v2_scalar.args.defaults = v2_scalar.args.defaults[:-1]
        v2_scalar.body = v2_scalar.body[2:]
    scalar_normalized = ast.dump(v2_scalar, include_attributes=False)
    scalar_v1 = ast.dump(v1_functions["scalar_equal"], include_attributes=False)

    v2_route = copy.deepcopy(v2_functions["validate_route_scientific"])
    v2_route.body = [
        statement
        for statement in v2_route.body
        if not (
            isinstance(statement, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "expected_pairing_role"
                for target in statement.targets
            )
        )
    ]
    v2_route = _PairingRoleNormalizer().visit(v2_route)
    ast.fix_missing_locations(v2_route)
    route_normalized = ast.dump(v2_route, include_attributes=False)
    route_v1 = ast.dump(
        v1_functions["validate_route_scientific"], include_attributes=False
    )

    module = ast.parse(v2_source)
    nullable_node = next(
        (
            node.value
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name)
                and target.id == "NULLABLE_NUMERIC_FIELDS"
                for target in node.targets
            )
        ),
        None,
    )
    nullable = sorted(ast.literal_eval(nullable_node)) if nullable_node else []
    expected_nullable = sorted(
        validation["allowed_representation_change_whitelist"]["V2-REP-001"][
            "nullable_numeric_fields"
        ]
    )
    expected_roles = validation["allowed_representation_change_whitelist"][
        "V2-REP-002"
    ]["mapping"]
    actual_roles = validation["candidate_contract_rules"][
        "pairing_diagnostic_roles"
    ]
    passed = (
        scalar_shape
        and scalar_normalized == scalar_v1
        and route_normalized == route_v1
        and nullable == expected_nullable
        and actual_roles == expected_roles
    )
    audit.add(
        "validator_revision",
        "validator V3继承V2的科学表示变更，仍仅为null↔NaN与compact/full-q诊断标签两项白名单",
        {
            "scalar_equal_normalizes_to_v1": True,
            "validate_route_scientific_normalizes_to_v1": True,
            "nullable_numeric_fields": expected_nullable,
            "pairing_diagnostic_roles": expected_roles,
        },
        {
            "scalar_equal_normalizes_to_v1": scalar_normalized == scalar_v1,
            "validate_route_scientific_normalizes_to_v1": route_normalized
            == route_v1,
            "nullable_numeric_fields": nullable,
            "pairing_diagnostic_roles": actual_roles,
        },
        passed,
        relative(SCRIPT_PATH),
    )


def check_source_isolation(audit: Audit, contract: Mapping[str, Any]) -> None:
    path = resolve_relpath(contract["paths"]["candidate_script"])
    source = path.read_text(encoding="utf-8")
    normalized = source.replace("\\", "/").lower()
    rules = contract["source_isolation"]
    forbidden_paths = [
        item for item in rules["forbidden_path_literals"] if item.lower() in normalized
    ]
    forbidden_exec = [
        item for item in rules["forbidden_execution_literals"] if item.lower() in normalized
    ]
    audit.add(
        "source_isolation",
        "候选源码不含Step-4数值输出、旧Step-5、validator或条件性诊断答案路径",
        [],
        forbidden_paths,
        not forbidden_paths,
        relative(path),
    )
    audit.add(
        "source_isolation",
        "候选源码不调用MATLAB引擎、外部子进程或系统命令取得答案",
        [],
        forbidden_exec,
        not forbidden_exec,
        relative(path),
    )
    identity = selected_algorithm_ast(source)
    passed = (
        identity.get("present") is True
        and identity.get("arguments") == [rules["algorithm_selector_argument"]]
        and not identity.get("calls")
        and identity.get("returns") == [rules["algorithm_selector_expression"]]
        and set(identity.get("names", []))
        <= {
            "matrix_order",
            "ALGORITHM_FULL_Q",
            "ALGORITHM_COMPACT",
            "int",
            "str",
        }
    )
    audit.add(
        "algorithm_identity",
        "候选selected_algorithm只由matrix_order<=5唯一决定，无路线、点或MATLAB结果覆盖",
        {
            "arguments": [rules["algorithm_selector_argument"]],
            "calls": [],
            "returns": [rules["algorithm_selector_expression"]],
        },
        identity,
        passed,
        relative(path),
    )


def matlab_numeric(handle: h5py.File, variable: str) -> np.ndarray:
    dataset = handle[variable]
    value = np.asarray(dataset, dtype=np.float64).T.copy()
    if not np.all(np.isfinite(value)):
        raise ValueError(f"Nonfinite MATLAB array: {variable}")
    return value


def matrix_order(workspace: Path, variable: str) -> int:
    with h5py.File(workspace, "r") as handle:
        shape = matlab_numeric(handle, variable).shape
    if len(shape) != 2 or shape[0] != shape[1]:
        raise ValueError(f"Matrix is not square: {workspace}:{variable}")
    return int(shape[0])


def check_candidate_contract(audit: Audit, validation: Mapping[str, Any]) -> None:
    path = resolve_relpath(validation["paths"]["candidate_contract"])
    document = read_json(path)
    rules = validation["candidate_contract_rules"]
    routes = document.get("routes", [])
    route_map = {item.get("route_id"): item for item in routes}
    pilot = document.get("pilot_points", {})
    actual_counts = {route_id: len(points) for route_id, points in pilot.items()}
    total = sum(actual_counts.values())
    unique = {
        route_id: len(points) == len({tuple(map(int, point)) for point in points})
        for route_id, points in pilot.items()
    }
    audit.add(
        "candidate_contract",
        "V4合同身份为正式预封签且精确登记五条路线、49个不重复试点",
        {
            "schema": rules["schema_version"],
            "status": rules["contract_status"],
            "route_ids": rules["route_ids"],
            "pilot_counts": rules["pilot_route_point_counts"],
            "pilot_total": rules["pilot_total_points"],
        },
        {
            "schema": document.get("schema_version"),
            "status": document.get("contract_status"),
            "route_ids": [item.get("route_id") for item in routes],
            "pilot_counts": actual_counts,
            "pilot_total": total,
            "unique": unique,
        },
        document.get("schema_version") == rules["schema_version"]
        and document.get("contract_status") == rules["contract_status"]
        and [item.get("route_id") for item in routes] == rules["route_ids"]
        and actual_counts == rules["pilot_route_point_counts"]
        and total == rules["pilot_total_points"]
        and all(unique.values()),
        relative(path),
    )
    observed_algorithms: dict[str, Any] = {}
    failures: list[str] = []
    for route_id in rules["route_ids"]:
        route = route_map[route_id]
        workspace = resolve_relpath(route["workspace_relpath"])
        actual_hash = sha256_file(workspace) if workspace.is_file() else "MISSING"
        n = matrix_order(workspace, route["matrix_variables"]["M"])
        algorithm = (
            "FULL_Q_ORDINARY_HISTORY_COMPANION"
            if n <= 5
            else "COMPACT_SCALAR_DELAY_AUGMENTATION"
        )
        observed_algorithms[route_id] = {
            "workspace_sha256": actual_hash,
            "matrix_order": n,
            "selected_algorithm": algorithm,
        }
        if (
            actual_hash != route["workspace_sha256"]
            or n != rules["matrix_orders"][route_id]
            or algorithm != rules["selected_algorithms"][route_id]
        ):
            failures.append(route_id)
    audit.add(
        "algorithm_identity",
        "五条封签workspace的实际矩阵阶数唯一选择预登记算法（15阶紧凑、四条5阶full-q）",
        {
            route_id: [
                rules["matrix_orders"][route_id],
                rules["selected_algorithms"][route_id],
            ]
            for route_id in rules["route_ids"]
        },
        {"observed": observed_algorithms, "failures": failures},
        not failures,
        relative(path),
    )
    required_points = {tuple(item) for item in rules["previous_conditioning_points"]}
    missing_points = {
        route_id: sorted(required_points - {tuple(point) for point in pilot[route_id]})
        for route_id in rules["route_ids"]
        if rules["matrix_orders"][route_id] <= 5
        and not required_points.issubset({tuple(point) for point in pilot[route_id]})
    }
    audit.add(
        "pilot_contract",
        "四条5阶路线的试点均包含此前四个病态坐标",
        [],
        missing_points,
        not missing_points,
        relative(path),
    )
    wrong_local_indices = {
        route_id: pilot[route_id][6:10]
        for route_id in rules["route_ids"]
        if rules["matrix_orders"][route_id] <= 5
        and [tuple(point) for point in pilot[route_id][6:10]]
        != [tuple(point) for point in rules["previous_conditioning_points"]]
    }
    audit.add(
        "pilot_contract",
        "四个历史病态坐标在四条5阶路线的本地索引6..9（零基）保持固定",
        rules["previous_conditioning_points"],
        wrong_local_indices,
        not wrong_local_indices,
        relative(path),
    )
    full = document.get("full_grid", {})
    audit.add(
        "full_contract",
        "full模式预登记为五路线各31x67、合计10385点，validator只验收不启动计算",
        {
            "shape": rules["full_shape"],
            "points_per_route": rules["full_points_per_route"],
            "total_points": rules["full_total_points"],
        },
        {
            "shape": full.get("shape"),
            "points_per_route": full.get("points_per_route"),
            "total_points": full.get("total_points"),
        },
        full.get("shape") == rules["full_shape"]
        and full.get("points_per_route") == rules["full_points_per_route"]
        and full.get("total_points") == rules["full_total_points"],
        relative(path),
    )
    hard = document.get("hard_residual_math", {})
    gates = document.get("numeric_gates", {})
    unchanged = document.get("root_and_pairing_policy", {}).get(
        "root_generation_unchanged_from_v2"
    )
    audit.add(
        "v3_residual_contract",
        "V4保持原P(z)/Laurent G(z)归一sigma_min硬残差；旧q块残差仅诊断，1e-8门槛未降低",
        {
            "root_generation_unchanged_from_v2": True,
            "poly_gate": 1e-8,
            "laurent_gate": 1e-8,
            "vector_role": rules["vector_block_residual_role"],
            "gate_relaxation_allowed": False,
        },
        {
            "root_generation_unchanged_from_v2": unchanged,
            "poly_gate": gates.get("max_gated_physical_svd_polynomial_residual"),
            "laurent_gate": gates.get(
                "max_gated_physical_svd_direct_laurent_residual"
            ),
            "vector_role": gates.get("vector_block_residual_gate_role"),
            "svd_vector": hard.get("svd_vector"),
            "gate_relaxation_allowed": gates.get("gate_relaxation_allowed"),
        },
        unchanged is True
        and gates.get("max_gated_physical_svd_polynomial_residual") == 1e-8
        and gates.get("max_gated_physical_svd_direct_laurent_residual") == 1e-8
        and gates.get("vector_block_residual_gate_role")
        == rules["vector_block_residual_role"]
        and gates.get("gate_relaxation_allowed") is False
        and "No companion eigenvector" in hard.get("svd_vector", ""),
        relative(path),
    )
    expected_fields = validation["postcheck"]["point_summary_fields"]
    output = document.get("output_schema", {})
    audit.add(
        "output_schema",
        "V4合同精确固定70列CSV、四个根组和每组14个dataset",
        {
            "csv_fields": expected_fields,
            "root_groups": validation["postcheck"]["root_groups"],
            "root_datasets": validation["postcheck"]["root_datasets"],
        },
        {
            "csv_fields": output.get("point_summary_csv_fields"),
            "root_groups": output.get("roots_h5_point_groups"),
            "root_datasets": output.get("roots_h5_datasets_per_root_group"),
        },
        output.get("point_summary_csv_fields") == expected_fields
        and output.get("roots_h5_point_groups")
        == validation["postcheck"]["root_groups"]
        and output.get("roots_h5_datasets_per_root_group")
        == validation["postcheck"]["root_datasets"],
        relative(path),
    )


def check_static_candidate_documents(
    audit: Audit, validation: Mapping[str, Any]
) -> None:
    root = resolve_relpath(validation["paths"]["candidate_output_root"])
    preflight = read_json(root / "preflight.json")
    expected_preflight = validation["expected_candidate_preflight"]
    actual_preflight = {
        key: preflight.get(key)
        for key in (
            "schema_version",
            "status",
            "check_count",
            "pass_count",
            "fail_count",
            "input_seal_sha256",
        )
    }
    inner_preflight = [
        item.get("check_id")
        for item in preflight.get("checks", [])
        if item.get("status") != "PASS"
    ]
    audit.add(
        "candidate_preflight",
        f"候选自身preflight封签为{expected_preflight['check_count']}/{expected_preflight['pass_count']} PASS并绑定当前input seal",
        expected_preflight,
        {"summary": actual_preflight, "inner_failures": inner_preflight},
        actual_preflight == expected_preflight
        and len(preflight.get("checks", [])) == expected_preflight["check_count"]
        and not inner_preflight,
        relative(root / "preflight.json"),
    )
    selftest = read_json(root / "selftest.json")
    expected_selftest = validation["expected_candidate_selftest"]
    actual_selftest = {key: selftest.get(key) for key in expected_selftest}
    inner_selftest = [
        item.get("check_id")
        for item in selftest.get("checks", [])
        if item.get("status") != "PASS"
    ]
    audit.add(
        "candidate_selftest",
        f"候选自身synthetic selftest封签为{expected_selftest['check_count']}/{expected_selftest['pass_count']} PASS且无隐藏FAIL",
        expected_selftest,
        {"summary": actual_selftest, "inner_failures": inner_selftest},
        actual_selftest == expected_selftest
        and len(selftest.get("checks", [])) == expected_selftest["check_count"]
        and not inner_selftest,
        relative(root / "selftest.json"),
    )
    seal = read_json(root / "input_seal.json")
    seals = validation["sealed_candidate_identity"]
    expected_identity = {
        "candidate_contract_sha256": seals["candidate_contract_sha256"],
        "candidate_script_sha256": seals["candidate_script_sha256"],
        "base_compute_sha256": seals["base_compute_sha256"],
        "v2_engine_sha256": seals["v2_engine_sha256"],
        "v3_reference_script_sha256": seals["v3_reference_script_sha256"],
        "static_diff_selftest_sha256": seals[
            "static_diff_selftest_canonical_sha256"
        ],
        "route_manifest_sha256": seals["route_manifest_sha256"],
        "route_count": 5,
    }
    actual_identity = {
        "candidate_contract_sha256": seal.get("candidate_contract_sha256"),
        "candidate_script_sha256": seal.get("candidate_script_sha256"),
        "base_compute_sha256": seal.get("base_compute_sha256"),
        "v2_engine_sha256": seal.get("v2_engine_sha256"),
        "v3_reference_script_sha256": seal.get("v3_reference_script_sha256"),
        "static_diff_selftest_sha256": seal.get("static_diff_selftest_sha256"),
        "route_manifest_sha256": seal.get("route_manifest_sha256"),
        "route_count": len(seal.get("route_order", [])),
    }
    audit.add(
        "input_seal",
        "input seal绑定V4合同/脚本、V3参考脚本、基础实现、V2根引擎、路线清单与五路线顺序",
        expected_identity,
        actual_identity,
        actual_identity == expected_identity,
        relative(root / "input_seal.json"),
    )
    static_diff_path = root / "static_diff_selftest.json"
    static_diff_domains = {
        "file_bytes_sha256": sha256_file(static_diff_path),
        "input_seal_canonical_sha256": seal.get("static_diff_selftest_sha256"),
    }
    expected_static_diff_domains = {
        "file_bytes_sha256": seals["static_diff_selftest_file_sha256"],
        "input_seal_canonical_sha256": seals[
            "static_diff_selftest_canonical_sha256"
        ],
    }
    audit.add(
        "static_diff_hash_domains",
        "static_diff文件字节SHA(95CE…)与input seal内部canonical SHA(5EBE…)分域独立硬核对",
        expected_static_diff_domains,
        static_diff_domains,
        static_diff_domains == expected_static_diff_domains,
        relative(static_diff_path),
    )
    contracts = read_json(root / "contracts_status.json")
    failed = {
        item.get("route_id"): [
            item.get("candidate_status"),
            item.get("candidate_policy"),
        ]
        for item in contracts.get("noncomputable_failed_routes", [])
    }
    paper = contracts.get("scientific_contracts", {})
    expected_failed = {
        route_id: ["CONTRACT_NOT_EXECUTABLE", "DO_NOT_CREATE"]
        for route_id in validation["candidate_contract_rules"]["failed_route_ids"]
    }
    expected_paper = {
        route_id: "CONTRACT_NOT_CLOSED"
        for route_id in validation["candidate_contract_rules"]["paper_route_ids"]
    }
    actual_paper = {
        route_id: paper.get(route_id, {}).get("status") for route_id in expected_paper
    }
    audit.add(
        "route_boundary",
        "四条历史执行失败路线保持DO_NOT_CREATE，两条论文路线保持CONTRACT_NOT_CLOSED",
        {"failed": expected_failed, "paper": expected_paper},
        {"failed": failed, "paper": actual_paper},
        failed == expected_failed and actual_paper == expected_paper,
        relative(root / "contracts_status.json"),
    )
    attribution = read_json(root / "v2_failure_attribution.json")
    baseline = read_json(root / "v2_immutability_baseline.json")
    attr = attribution.get("v2_failure_attribution", {})
    audit.add(
        "v2_failure_preservation",
        "V2仍永久FAIL且未启动pilot/full；V3没有回写或覆盖V2证据",
        {
            "status": "PERMANENT_FAIL_IMMUTABLE",
            "failed_mode": "selftest",
            "pilot_started": False,
            "full_started": False,
            "baseline_status": "PASS",
        },
        {
            "status": attr.get("status"),
            "failed_mode": attr.get("failed_mode"),
            "pilot_started": attr.get("pilot_started"),
            "full_started": attr.get("full_started"),
            "baseline_status": baseline.get("status"),
            "baseline_unchanged": baseline.get("all_expected_and_unchanged"),
        },
        attr.get("status") == "PERMANENT_FAIL_IMMUTABLE"
        and attr.get("failed_mode") == "selftest"
        and attr.get("pilot_started") is False
        and attr.get("full_started") is False
        and baseline.get("status") == "PASS"
        and baseline.get("all_expected_and_unchanged") is True,
        relative(root / "v2_failure_attribution.json"),
    )
    hard = read_json(root / "hard_residual_math.json")
    hard_math = hard.get("hard_residual_math", {})
    hard_gates = hard.get("numeric_gates", {})
    audit.add(
        "hard_residual_identity",
        "静态数学封签明确直接sigma_min硬门槛与旧向量残差诊断边界",
        {
            "poly": 1e-8,
            "laurent": 1e-8,
            "vector_role": validation["candidate_contract_rules"][
                "vector_block_residual_role"
            ],
        },
        {
            "poly": hard_gates.get("max_gated_physical_svd_polynomial_residual"),
            "laurent": hard_gates.get(
                "max_gated_physical_svd_direct_laurent_residual"
            ),
            "vector_role": hard_gates.get("vector_block_residual_gate_role"),
            "svd_vector": hard_math.get("svd_vector"),
        },
        hard_gates.get("max_gated_physical_svd_polynomial_residual") == 1e-8
        and hard_gates.get("max_gated_physical_svd_direct_laurent_residual")
        == 1e-8
        and hard_gates.get("vector_block_residual_gate_role")
        == validation["candidate_contract_rules"]["vector_block_residual_role"]
        and "No companion eigenvector" in hard_math.get("svd_vector", ""),
        relative(root / "hard_residual_math.json"),
    )
    v3_attribution_path = root / "v3_failure_attribution.json"
    v3_baseline_path = root / "v3_immutability_baseline.json"
    v3_attribution = read_json(v3_attribution_path).get(
        "v3_failure_attribution", {}
    )
    v3_baseline = read_json(v3_baseline_path)
    expected_v1 = validation["protected_v1_failed_audit_identity"]
    observed_v1 = {
        "status": v3_attribution.get("status"),
        "overall_status": v3_attribution.get("overall_status"),
        "passed_checks": v3_attribution.get("passed_checks"),
        "information_checks": v3_attribution.get("information_checks"),
        "failed_checks": v3_attribution.get("failed_checks"),
        "total_checks": v3_attribution.get("total_checks"),
        "audit_primary_json_sha256": v3_attribution.get(
            "audit_primary_json_sha256"
        ),
        "audit_checks_sha256": v3_attribution.get("audit_checks_sha256"),
        "audit_report_sha256": v3_attribution.get("audit_report_sha256"),
        "audit_manifest_sha256": v3_attribution.get("audit_manifest_sha256"),
        "scientific_output_reuse_policy": read_json(
            v3_attribution_path
        ).get("v3_scientific_output_reuse_policy"),
        "baseline_status": v3_baseline.get("status"),
        "baseline_unchanged": v3_baseline.get("all_expected_and_unchanged"),
    }
    audit.add(
        "v3_failure_preservation",
        "V3保持永久validator FAIL，V1失败审计哈希与V3科学工件禁止复用规则未变",
        expected_v1,
        observed_v1,
        observed_v1 == expected_v1,
        relative(v3_attribution_path),
    )


def check_prior_verdicts(audit: Audit) -> None:
    compact_path = resolve_relpath("outputs/step5_audit/full_postcheck.json")
    compact = read_json(compact_path)
    summary = compact.get("summary", {})
    failed_ids = [
        item.get("check_id")
        for item in compact.get("checks", [])
        if item.get("status") == "FAIL"
    ]
    audit.add(
        "prior_compact_verdict",
        "第一次compact全网格validator仍保持原门槛下2项FAIL",
        {
            "overall_status": "FAIL",
            "failed_checks": 2,
            "ids": ["S5-POST-0095", "S5-POST-0108"],
        },
        {
            "overall_status": summary.get("overall_status"),
            "failed_checks": summary.get("failed_checks"),
            "ids": failed_ids,
        },
        summary.get("overall_status") == "FAIL"
        and summary.get("failed_checks") == 2
        and failed_ids == ["S5-POST-0095", "S5-POST-0108"],
        relative(compact_path),
    )
    diagnosis_path = resolve_relpath("outputs/step5_solver_conditioning/diagnostic.json")
    diagnosis = read_json(diagnosis_path)
    repeat = read_json(
        resolve_relpath("outputs/step5_solver_conditioning/repeatability_check.json")
    )
    audit.add(
        "prior_conditioning_diagnosis",
        "条件性诊断仍为DIAGNOSTIC_ONLY且没有覆盖第一次validator FAIL",
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
        relative(diagnosis_path),
    )
    v2_audit_path = resolve_relpath(
        "outputs/step5_fullq_candidate_audit/v2_precheck.json"
    )
    v2_audit = read_json(v2_audit_path)
    audit.add(
        "prior_v2_verdict",
        "第二版候选独立审计仍封存为selftest失败、未进入pilot",
        "V2_STOPPED_SELFTEST_FAIL_NO_PILOT",
        v2_audit.get("summary", {}).get("overall_status"),
        v2_audit.get("summary", {}).get("overall_status")
        == "V2_STOPPED_SELFTEST_FAIL_NO_PILOT",
        relative(v2_audit_path),
    )


def check_validator_v2_precheck_failure_preservation(
    audit: Audit, validation: Mapping[str, Any]
) -> None:
    expected = validation["protected_validator_v2_precheck_failure_identity"]
    path = resolve_relpath(expected["relpath"])
    document = read_json(path)
    execution = document.get("execution", {})
    frozen = document.get("validator_v2_frozen_identity", {})
    audit_bundle = document.get("audit_bundle_frozen_identity", {})
    actual = {
        "relpath": expected["relpath"],
        "sha256": sha256_file(path),
        "record_status": document.get("record_status"),
        "overall_status": execution.get("overall_status"),
        "total_checks": execution.get("total_checks"),
        "passed_checks": execution.get("passed_checks"),
        "information_checks": execution.get("information_checks"),
        "failed_checks": execution.get("failed_checks"),
        "candidate_scientific_outputs_parsed": execution.get(
            "candidate_scientific_outputs_parsed"
        ),
        "candidate_computation_launched": execution.get(
            "candidate_computation_launched"
        ),
        "candidate_outputs_modified": execution.get("candidate_outputs_modified"),
        "v4_pilot_directory_existed_after": execution.get(
            "v4_pilot_directory_existed_after"
        ),
        "v4_full_directory_existed_after": execution.get(
            "v4_full_directory_existed_after"
        ),
        "script_sha256": frozen.get("script_sha256"),
        "contract_sha256": frozen.get("contract_sha256"),
        "binding_record_sha256": frozen.get("binding_record_sha256"),
        "audit_primary_json_sha256": audit_bundle.get("primary_json", {}).get(
            "sha256"
        ),
    }
    audit.add(
        "validator_v2_failure_preservation",
        "validator V2的30 PASS/2 FAIL预检及脚本/合同/binding/主审计哈希保持永久FAIL",
        expected,
        actual,
        actual == expected,
        relative(path),
    )


def check_step4_audit_manifest(
    audit: Audit, validation: Mapping[str, Any]
) -> None:
    contract = validation["sealed_step4_audit_manifest"]
    path = resolve_relpath(contract["relpath"])
    fields, rows = read_csv(path)
    records = {
        row.get("route_id"): row
        for row in rows
        if row.get("artifact_role") == contract["required_common_grid_role"]
        and row.get("grid_kind") == contract["required_common_grid_kind"]
    }
    failures: list[dict[str, Any]] = []
    for route_id, reference in validation["sealed_step4_references"].items():
        row = records.get(route_id)
        if row is None:
            failures.append({"route_id": route_id, "reason": "MISSING"})
            continue
        expected = {
            "relative_path": reference["mat_relpath"],
            "sha256": reference["mat_sha256"],
            "identity_status": contract["identity_status"],
        }
        actual = {key: row.get(key) for key in expected}
        if actual != expected:
            failures.append(
                {
                    "route_id": route_id,
                    "reason": "IDENTITY",
                    "expected": expected,
                    "actual": actual,
                }
            )
    audit.add(
        "step4_reference_identity",
        "盲读数值前先由封签Step-4审计manifest绑定五个31x67 common-grid MAT",
        {
            "manifest_sha256": contract["sha256"],
            "route_count": 5,
            "all_identity_status": "PASS",
        },
        {
            "manifest_sha256": sha256_file(path),
            "fields": fields,
            "matched_route_count": len(records),
            "failures": failures,
        },
        sha256_file(path) == contract["sha256"]
        and len(records) == 5
        and not failures,
        relative(path),
    )


def prepared_terms(
    terms: Sequence[tuple[int, np.ndarray]],
) -> tuple[tuple[int, np.ndarray, float], ...]:
    result: list[tuple[int, np.ndarray, float]] = []
    for exponent, matrix in terms:
        value = np.asarray(matrix, dtype=np.complex128)
        norm = float(np.linalg.norm(value, ord=2))
        if not math.isfinite(norm):
            raise FloatingPointError("Nonfinite term norm")
        if norm > 0.0:
            result.append((int(exponent), value, norm))
    if not result:
        raise ValueError("No nonzero characteristic term")
    return tuple(result)


def normalized_svd_residual(
    terms: Sequence[tuple[int, np.ndarray, float]], root: complex
) -> float:
    """Independent NumPy-SVD implementation of the preregistered V3 residual."""
    root = complex(root)
    if not (math.isfinite(root.real) and math.isfinite(root.imag)):
        return math.inf
    magnitude = abs(root)
    if magnitude == 0.0:
        if any(exponent < 0 for exponent, _matrix, _norm in terms):
            return math.inf
        active = [item for item in terms if item[0] == 0]
        if not active:
            return math.inf
        reference = max(math.log(norm) for _exponent, _matrix, norm in active)
        scaled = np.zeros_like(active[0][1], dtype=np.complex128)
        denominator = 0.0
        for _exponent, matrix, norm in active:
            amplitude = math.exp(math.log(norm) - reference)
            scaled += (amplitude / norm) * matrix
            denominator += amplitude
    else:
        log_abs = math.log(magnitude)
        phase = math.atan2(root.imag, root.real)
        logs = [
            exponent * log_abs + math.log(norm)
            for exponent, _matrix, norm in terms
        ]
        reference = max(logs)
        scaled = np.zeros_like(terms[0][1], dtype=np.complex128)
        denominator = 0.0
        for (exponent, matrix, norm), log_weight in zip(terms, logs):
            amplitude = math.exp(log_weight - reference)
            phase_factor = complex(
                math.cos(exponent * phase), math.sin(exponent * phase)
            )
            scaled += amplitude * phase_factor * matrix / norm
            denominator += amplitude
    if not (math.isfinite(denominator) and denominator > 0.0):
        return math.inf
    singular_values = np.linalg.svd(scaled, compute_uv=False)
    result = float(singular_values[-1] / denominator)
    return result if math.isfinite(result) else math.inf


def check_validator_math_selftest(audit: Audit) -> None:
    identity = np.eye(2)
    poly = prepared_terms(((0, -0.5 * identity), (1, identity)))
    exact_poly = normalized_svd_residual(poly, 0.5)
    perturbed_poly = normalized_svd_residual(poly, 0.5001)
    laurent = prepared_terms(((-1, -identity), (0, identity)))
    exact_laurent = normalized_svd_residual(laurent, 1.0)
    perturbed_laurent = normalized_svd_residual(laurent, 1.001)
    tiny = 2.0 ** -600
    extreme = prepared_terms(((-2, identity), (-1, -(1.0 / tiny) * identity)))
    exact_extreme = normalized_svd_residual(extreme, tiny)
    perturbed_extreme = normalized_svd_residual(
        extreme, tiny * (1.0 + 2.0 ** -20)
    )
    actual = {
        "exact_poly": exact_poly,
        "perturbed_poly": perturbed_poly,
        "exact_laurent": exact_laurent,
        "perturbed_laurent": perturbed_laurent,
        "exact_extreme": exact_extreme,
        "perturbed_extreme": perturbed_extreme,
        "laurent_zero": normalized_svd_residual(laurent, 0.0),
    }
    passed = (
        exact_poly <= 1e-12
        and perturbed_poly > 1e-8
        and exact_laurent <= 1e-12
        and perturbed_laurent > 1e-8
        and math.isfinite(exact_extreme)
        and exact_extreme <= 1e-12
        and math.isfinite(perturbed_extreme)
        and perturbed_extreme > 1e-8
        and math.isinf(actual["laurent_zero"])
    )
    audit.add(
        "validator_selftest",
        "独立NumPy-SVD残差实现通过精确根、扰动根、极端尺度和Laurent零边界自测",
        "ALL_SELFTEST_GATES_PASS",
        actual,
        passed,
        relative(SCRIPT_PATH),
    )


def precheck_mode_markers(audit: Audit, validation: Mapping[str, Any]) -> None:
    root = resolve_relpath(validation["paths"]["candidate_output_root"])
    markers: dict[str, str] = {}
    for mode in ("pilot", "full"):
        mode_root = root / mode
        markers[mode] = (
            "SEALED_MARKER_PRESENT_NOT_PARSED"
            if (mode_root / "run_status.json").is_file()
            and (mode_root / "artifact_manifest.csv").is_file()
            else "NO_COMPLETE_SEALED_MARKER"
        )
    unexpected_markers = [
        mode
        for mode, marker in markers.items()
        if marker == "SEALED_MARKER_PRESENT_NOT_PARSED"
    ]
    audit.add(
        "postcheck_boundary",
        "precheck不解析pilot/full科学文件；当前预检封签下如存在未授权sealed marker则硬FAIL",
        {"unexpected_sealed_markers": [], "scientific_content_parsed": False},
        {
            "markers": markers,
            "unexpected_sealed_markers": unexpected_markers,
            "scientific_content_parsed": False,
        },
        not unexpected_markers,
        relative(root),
    )
    forbidden = validation["candidate_contract_rules"]["failed_route_ids"] + validation[
        "candidate_contract_rules"
    ]["paper_route_ids"]
    existing = [
        relative(path)
        for route_id in forbidden
        for path in root.glob(f"**/{route_id}")
        if path.is_dir()
    ]
    audit.add(
        "forbidden_outputs",
        "四失败路线和两论文合同未闭合路线均无候选科学目录",
        [],
        existing,
        not existing,
        relative(root),
    )


def report_precheck(path: Path, summary: Mapping[str, Any]) -> None:
    lines = [
        "# Board20 Step5第四版隔离候选 / validator V3独立静态预检",
        "",
        f"> 结论：`{summary['overall_status']}`。本次没有读取或验收pilot/full科学结果，也没有启动任何计算。",
        "",
        "## 人话结论",
        "",
        "- V4合同、计算脚本、基础实现、根引擎和输入封签均与最终SHA-256一致。",
        "- 候选自身preflight为58/58 PASS，synthetic selftest为80/80 PASS。",
        "- V4保留原1e-8门槛；硬残差仍直接计算原P(z)和Laurent G(z)的归一sigma_min，旧伴随向量q块残差仅作诊断。",
        "- V3永久失败及V1失败审计、V2失败证据、第一次compact validator的2项FAIL和条件性诊断裁决均保持不变。",
        "- validator V3继承的科学表示修订仅有null↔NaN与compact/full-q诊断标签两项；科学公式和门槛未改。",
        "- pilot/full事后验收必须另行明确授权并带CLI显式标志；validator本身永不启动候选计算。",
        "",
        "## 后续硬门",
        "",
        "- 49点试点或10385点全网格必须完整通过CSV/HDF5/checkpoint/manifest身份检查。",
        "- 每个门控物理根必须独立重算P(z)与G(z)归一SVD残差且均不超过1e-8。",
        "- 与封签Step-4 MATLAB rho逐点绝对差不超过1e-8，rho<1分类逐点一致。",
        "- repeatability必须声明baseline=repeat=实际科学manifest SHA，五路线checkpoint HDF5哈希必须自洽。",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_audit_bundle(
    mode: str,
    audit: Audit,
    validation: Mapping[str, Any],
    protected_before: Mapping[str, str],
    protected_after: Mapping[str, str],
    route_rows: Sequence[Mapping[str, Any]] = (),
    point_rows: Sequence[Mapping[str, Any]] = (),
    conditioning_rows: Sequence[Mapping[str, Any]] = (),
    authorization_binding: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    output_root = resolve_relpath(validation["paths"]["audit_output_root"])
    log_root = resolve_relpath(validation["paths"]["audit_log_root"])
    output_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    stem = "v4_validator_v3_" + mode.replace("-", "_")
    if mode == "precheck":
        overall = "PASS_STATIC_POSTCHECK_NOT_AUTHORIZED" if not audit.failed else "FAIL"
    else:
        overall = "PASS" if not audit.failed else "FAIL"
    summary = {
        "mode": mode,
        "overall_status": overall,
        "total_checks": len(audit.checks),
        "passed_checks": audit.pass_count,
        "information_checks": audit.info_count,
        "failed_checks": len(audit.failed),
        "candidate_outputs_modified": False,
        "candidate_computation_launched": False,
        "explicit_postcheck_authorization": mode != "precheck",
    }
    document = {
        "schema_version": "board20_step5_fullq_svd_candidate_validator_v3_audit_v1",
        "validator": {
            "script_relpath": relative(SCRIPT_PATH),
            "script_sha256": sha256_file(SCRIPT_PATH),
            "contract_relpath": relative(CONTRACT_PATH),
            "contract_sha256": sha256_file(CONTRACT_PATH),
        },
        "summary": summary,
        "authorization_binding": authorization_binding or {},
        "checks": audit.checks,
        "protected_hashes_before": dict(protected_before),
        "protected_hashes_after": dict(protected_after),
    }
    json_path = output_root / f"{stem}.json"
    checks_path = output_root / f"{stem}_checks.csv"
    hashes_path = output_root / f"{stem}_protected_hashes.csv"
    report_path = output_root / f"{stem}_report.md"
    log_path = log_root / f"{stem}.log"
    write_json(json_path, document)
    write_csv(
        checks_path,
        audit.checks,
        ("check_id", "category", "description", "expected", "actual", "status", "evidence"),
    )
    write_csv(
        hashes_path,
        [
            {
                "relpath": path,
                "sha256_before": protected_before[path],
                "sha256_after": protected_after.get(path, "MISSING"),
                "unchanged": protected_before[path]
                == protected_after.get(path, "MISSING"),
            }
            for path in sorted(protected_before)
        ],
        ("relpath", "sha256_before", "sha256_after", "unchanged"),
    )
    extra_paths: list[Path] = []
    if mode == "precheck":
        report_precheck(report_path, summary)
    else:
        report_postcheck(report_path, summary, route_rows, conditioning_rows)
        route_path = output_root / f"{stem}_route_summary.csv"
        point_path = output_root / f"{stem}_point_comparison.csv"
        conditioning_path = output_root / f"{stem}_previous_conditioning_points.csv"
        write_csv(
            route_path,
            route_rows,
            (
                "route_id",
                "point_count",
                "max_rho_abs_diff_to_step4",
                "rho_gate_fail_count",
                "stable_mismatch_count",
                "max_recomputed_svd_polynomial_residual",
                "max_recomputed_svd_laurent_residual",
                "residual_gate_fail_count",
                "formula_gate_fail_count",
                "unmatched_safety_fail_count",
                "origin_splitting_point_count",
                "status",
            ),
        )
        point_fields = (
            "route_id",
            "l",
            "j",
            "rho_candidate",
            "rho_step4_matlab",
            "rho_abs_diff",
            "rho_gate_pass",
            "stable_candidate",
            "stable_step4_matlab",
            "stable_match",
            "recomputed_max_svd_polynomial_residual",
            "recomputed_max_svd_laurent_residual",
            "saved_recomputed_residual_match",
            "formula_relative_difference",
            "unmatched_safety_pass",
            "origin_splitting_status",
            "point_status",
        )
        write_csv(point_path, point_rows, point_fields)
        write_csv(conditioning_path, conditioning_rows, point_fields)
        extra_paths.extend((route_path, point_path, conditioning_path))
    log_lines = [
        canonical_json(
            {
                "check_id": item["check_id"],
                "category": item["category"],
                "status": item["status"],
                "description": item["description"],
            }
        )
        for item in audit.checks
    ]
    log_lines.append(canonical_json(summary))
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8", newline="\n")
    scientific_paths = [json_path, checks_path, hashes_path, report_path, *extra_paths]
    manifest_path = output_root / f"{stem}_artifact_manifest.csv"
    write_csv(
        manifest_path,
        [
            {
                "relpath": path.relative_to(output_root).as_posix(),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
            for path in sorted(
                scientific_paths,
                key=lambda item: item.relative_to(output_root).as_posix(),
            )
        ],
        ("relpath", "bytes", "sha256"),
    )
    return summary


def run_precheck() -> dict[str, Any]:
    validation = read_json(CONTRACT_PATH)
    audit = Audit("S5FQSV4-V3-PRE")
    audit.add(
        "validation_contract",
        "独立V4候选validator V3合同schema与只读模式边界已固定",
        "board20_step5_fullq_svd_candidate_validation_contract_v3",
        validation.get("schema_version"),
        validation.get("schema_version")
        == "board20_step5_fullq_svd_candidate_validation_contract_v3",
        relative(CONTRACT_PATH),
    )
    expected = expected_static_hashes(validation)
    before = hash_snapshot(expected)
    check_expected_hashes(audit, expected)
    check_source_isolation(audit, validation)
    check_candidate_v4_change_review(audit, validation)
    check_validator_revision_whitelist(audit, validation)
    check_candidate_contract(audit, validation)
    check_static_candidate_documents(audit, validation)
    check_prior_verdicts(audit)
    check_validator_v2_precheck_failure_preservation(audit, validation)
    check_step4_audit_manifest(audit, validation)
    check_validator_math_selftest(audit)
    precheck_mode_markers(audit, validation)
    after = hash_snapshot(expected)
    changed = [path for path in before if before[path] != after.get(path)]
    audit.add(
        "immutability",
        "静态预检前后V4候选、V3永久失败、Step-4基准、V2失败及既有Step-5证据字节完全不变",
        [],
        changed,
        not changed,
    )
    return write_audit_bundle("precheck", audit, validation, before, after)


INT_FIELDS = {
    "l",
    "j",
    "matrix_order",
    "algorithm_selector_value",
    "selected_order",
    "compact_order",
    "full_q_order",
    "polynomial_degree",
    "clearing_power",
    "raw_root_count",
    "finite_root_count",
    "nonfinite_root_count",
    "removed_zero_root_count",
    "retained_root_count",
    "compact_raw_root_count",
    "compact_retained_root_count",
    "compact_removed_zero_root_count",
    "matched_physical_root_count",
    "theoretical_extra_zero_count",
    "unmatched_full_root_count",
}
BOOL_FIELDS = {
    "stable",
    "critical",
    "compact_pairing_performed",
    "stable_compact_pairing",
    "unmatched_count_within_theoretical",
    "unmatched_full_below_0p9",
    "unmatched_full_strictly_nondominant",
    "stable_classification_match",
    "all_gated_svd_residuals_finite",
}
STRING_FIELDS = {
    "route_id",
    "route_role",
    "declared_method",
    "division",
    "route_formula",
    "algorithm_selector_field",
    "selected_algorithm",
    "pairing_diagnostic_role",
    "origin_splitting_status",
    "origin_split_gate_role",
    "hard_residual_definition",
    "vector_block_residual_role",
    "point_status",
    "failure_code",
}
NULLABLE_NUMERIC_FIELDS = {
    "compact_zero_root_tolerance",
    "rho_compact_pairing",
    "full_q_compact_rho_abs_diff",
    "full_q_compact_root_match_max_relative_diff",
    "near_unit_root_match_max_relative_diff",
    "unmatched_full_max_abs",
    "max_unmatched_full_svd_polynomial_residual_diagnostic",
    "max_unmatched_full_svd_laurent_residual_diagnostic",
    "max_unmatched_full_vector_block_polynomial_residual_diagnostic",
    "max_unmatched_full_vector_block_laurent_residual_diagnostic",
    "max_near_unit_svd_polynomial_residual",
    "max_near_unit_svd_laurent_residual",
    "max_near_unit_vector_block_polynomial_residual_diagnostic",
    "max_near_unit_vector_block_laurent_residual_diagnostic",
}


def as_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, np.integer)):
        if int(value) in (0, 1):
            return bool(value)
    text = str(value).strip().lower()
    if text in ("true", "1"):
        return True
    if text in ("false", "0"):
        return False
    raise ValueError(f"Not a boolean: {value!r}")


def as_float(value: Any) -> float:
    if value is None or value == "":
        return math.nan
    text = str(value).strip()
    if text.lower() in ("nan", "+nan", "-nan"):
        return math.nan
    if text.lower() in ("inf", "+inf", "infinity", "+infinity"):
        return math.inf
    if text.lower() in ("-inf", "-infinity"):
        return -math.inf
    return float(value)


def parse_csv_record(row: Mapping[str, str]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in row.items():
        if name in STRING_FIELDS:
            result[name] = value
        elif value == "":
            result[name] = None
        elif name in BOOL_FIELDS:
            result[name] = as_bool(value)
        elif name in INT_FIELDS:
            result[name] = int(value)
        else:
            result[name] = as_float(value)
    return result


def scalar_equal(
    first: Any,
    second: Any,
    tolerance: float = 1e-14,
    field_name: str | None = None,
) -> bool:
    def missing(value: Any) -> bool:
        if value in (None, ""):
            return True
        if isinstance(value, (float, np.floating)):
            return math.isnan(float(value))
        return False

    if field_name in NULLABLE_NUMERIC_FIELDS and missing(first) and missing(second):
        return True
    if first in (None, "") and second in (None, ""):
        return True
    if isinstance(first, (bytes, np.bytes_)):
        first = first.decode("utf-8")
    if isinstance(second, (bytes, np.bytes_)):
        second = second.decode("utf-8")
    if isinstance(first, (bool, np.bool_)) or isinstance(second, (bool, np.bool_)):
        try:
            return as_bool(first) == as_bool(second)
        except ValueError:
            return False
    if isinstance(first, str) or isinstance(second, str):
        # A numeric HDF5 value may be compared with a JSON numeric string only
        # after both fail exact text equality.
        if str(first) == str(second):
            return True
        try:
            first_number = as_float(first)
            second_number = as_float(second)
        except (TypeError, ValueError):
            return False
        return float_equal(first_number, second_number, tolerance, tolerance)
    if isinstance(first, (int, float, np.number)) and isinstance(
        second, (int, float, np.number)
    ):
        return float_equal(float(first), float(second), tolerance, tolerance)
    return first == second


def float_equal(
    first: float, second: float, absolute: float, relative_tolerance: float
) -> bool:
    if math.isnan(first) and math.isnan(second):
        return True
    if math.isinf(first) or math.isinf(second):
        return first == second
    return abs(first - second) <= absolute + relative_tolerance * max(
        abs(first), abs(second)
    )


@dataclass(frozen=True)
class RouteMath:
    route_id: str
    formula: str
    delay_dofs: tuple[int, int]
    M: np.ndarray
    C1: np.ndarray
    K1: np.ndarray
    C2: np.ndarray
    K2: np.ndarray
    al: np.ndarray
    dt: float
    S: np.ndarray | None
    delta_c: np.ndarray | None
    delta_k: np.ndarray | None
    mass_term: np.ndarray
    base_zero: np.ndarray
    base_minus_one: np.ndarray
    delayed_zero: np.ndarray
    delayed_minus_one: np.ndarray
    feedback_zero: np.ndarray
    feedback_minus_one: np.ndarray


def load_route_math(route: Mapping[str, Any]) -> RouteMath:
    workspace = resolve_relpath(route["workspace_relpath"])
    loaded: dict[str, np.ndarray] = {}
    with h5py.File(workspace, "r") as handle:
        for logical, variable in route["matrix_variables"].items():
            loaded[logical] = matlab_numeric(handle, variable)
    dt = float(loaded["dt"].reshape(-1)[0])
    mass = sla.solve(
        loaded["al"].T,
        loaded["M"].T,
        assume_a="gen",
        check_finite=True,
    ).T / (dt**2)
    n = loaded["M"].shape[0]
    feedback_zero = np.zeros((n, n), dtype=float)
    feedback_minus = np.zeros((n, n), dtype=float)
    if route["route_formula"] == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        feedback_zero = loaded["S"].T @ (
            loaded["DeltaC"] / dt + loaded["DeltaK"]
        ) @ loaded["S"]
        feedback_minus = loaded["S"].T @ (-loaded["DeltaC"] / dt) @ loaded["S"]
    return RouteMath(
        route_id=str(route["route_id"]),
        formula=str(route["route_formula"]),
        delay_dofs=tuple(
            int(value) - 1 for value in route["delay_dofs_matlab_1_based"]
        ),
        M=loaded["M"],
        C1=loaded["C1"],
        K1=loaded["K1"],
        C2=loaded["C2"],
        K2=loaded["K2"],
        al=loaded["al"],
        dt=dt,
        S=loaded.get("S"),
        delta_c=loaded.get("DeltaC"),
        delta_k=loaded.get("DeltaK"),
        mass_term=mass,
        base_zero=-2.0 * mass + loaded["C1"] / dt + loaded["K1"],
        base_minus_one=mass - loaded["C1"] / dt,
        delayed_zero=loaded["C2"] / dt + loaded["K2"],
        delayed_minus_one=-loaded["C2"] / dt,
        feedback_zero=feedback_zero,
        feedback_minus_one=feedback_minus,
    )


def selector(order: int, index: int) -> np.ndarray:
    value = np.zeros((order, order), dtype=float)
    value[index, index] = 1.0
    return value


def direct_terms(
    route: RouteMath, l_value: int, j_value: int
) -> list[tuple[int, np.ndarray]]:
    terms: list[tuple[int, np.ndarray]] = [
        (1, route.mass_term),
        (0, route.base_zero),
        (-1, route.base_minus_one),
    ]
    order = route.M.shape[0]
    for delay, dof in zip((l_value, j_value), route.delay_dofs):
        channel = selector(order, dof)
        if route.formula == "ORI_DIV1_H_RIGHT":
            terms.append((-delay, route.delayed_zero @ channel))
            terms.append((-(delay + 1), route.delayed_minus_one @ channel))
        elif route.formula in (
            "GUYAN_DIV1_H_LEFT",
            "DIV2_H_LEFT_FEEDBACK_OUTSIDE",
        ):
            terms.append((-delay, channel @ route.delayed_zero))
            terms.append((-(delay + 1), channel @ route.delayed_minus_one))
        else:
            raise ValueError(f"Unsupported route formula: {route.formula}")
    if route.formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        terms.append((0, route.feedback_zero))
        terms.append((-1, route.feedback_minus_one))
    return [(exponent, matrix) for exponent, matrix in terms if np.any(matrix != 0.0)]


def consolidate_terms(
    terms: Sequence[tuple[int, np.ndarray]],
) -> dict[int, np.ndarray]:
    result: dict[int, np.ndarray] = {}
    for exponent, matrix in terms:
        if exponent in result:
            result[exponent] = result[exponent] + matrix
        else:
            result[exponent] = np.array(matrix, dtype=float, copy=True)
    return {
        exponent: value
        for exponent, value in sorted(result.items())
        if np.any(value != 0.0)
    }


def polynomial_terms_from_coefficients(
    coefficients: Mapping[int, np.ndarray],
) -> tuple[list[tuple[int, np.ndarray]], int, int]:
    exponents = sorted(coefficients)
    clearing = max(0, -exponents[0])
    degree = exponents[-1] + clearing
    order = next(iter(coefficients.values())).shape[0]
    polynomial = [np.zeros((order, order), dtype=float) for _ in range(degree + 1)]
    for exponent, matrix in coefficients.items():
        polynomial[exponent + clearing] += matrix
    while len(polynomial) > 1 and not np.any(polynomial[-1] != 0.0):
        polynomial.pop()
    return list(enumerate(polynomial)), clearing, len(polynomial) - 1


def direct_formula_matrix(
    route: RouteMath, l_value: int, j_value: int, root: complex
) -> np.ndarray:
    order = route.M.shape[0]
    value = (
        route.mass_term * root
        + route.base_zero
        + route.base_minus_one / root
    ).astype(np.complex128)
    h_zero = np.zeros((order, order), dtype=np.complex128)
    h_minus = np.zeros((order, order), dtype=np.complex128)
    for delay, dof in zip((l_value, j_value), route.delay_dofs):
        h_zero[dof, dof] += root ** (-delay)
        h_minus[dof, dof] += root ** (-(delay + 1))
    if route.formula == "ORI_DIV1_H_RIGHT":
        value += route.delayed_zero @ h_zero
        value += route.delayed_minus_one @ h_minus
    else:
        value += h_zero @ route.delayed_zero
        value += h_minus @ route.delayed_minus_one
    if route.formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        value += route.feedback_zero + route.feedback_minus_one / root
    return value


def formula_identity_difference(
    route: RouteMath,
    coefficients: Mapping[int, np.ndarray],
    l_value: int,
    j_value: int,
) -> float:
    differences: list[float] = []
    for root in (0.83 + 0.17j, 1.12 - 0.13j, -0.71 + 0.29j):
        consolidated = np.zeros_like(route.M, dtype=np.complex128)
        for exponent, matrix in coefficients.items():
            consolidated += (root**exponent) * matrix
        direct = direct_formula_matrix(route, l_value, j_value, root)
        differences.append(
            float(
                np.linalg.norm(consolidated - direct, ord="fro")
                / max(1.0, float(np.linalg.norm(direct, ord="fro")))
            )
        )
    return max(differences)


def h5_text(value: Any) -> str:
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8")
    return str(value)


def validate_root_group_layout(
    group: h5py.Group,
    point_count: int,
    expected_datasets: Sequence[str],
) -> tuple[bool, dict[str, Any]]:
    names = sorted(group.keys())
    expected = sorted(expected_datasets)
    if names != expected:
        return False, {"datasets": names, "expected": expected}
    offsets = np.asarray(group["offset"], dtype=np.int64).reshape(-1)
    counts = np.asarray(group["count"], dtype=np.int64).reshape(-1)
    if len(offsets) != point_count or len(counts) != point_count:
        return False, {
            "offset_count_length": [len(offsets), len(counts)],
            "point_count": point_count,
        }
    expected_offsets = np.concatenate(
        (np.array([0], dtype=np.int64), np.cumsum(counts[:-1], dtype=np.int64))
    ) if point_count else np.empty(0, dtype=np.int64)
    total = int(np.sum(counts))
    flat_failures = {
        name: int(group[name].size)
        for name in expected_datasets
        if name not in ("offset", "count") and int(group[name].size) != total
    }
    passed = (
        np.array_equal(offsets, expected_offsets)
        and np.all(counts >= 0)
        and not flat_failures
    )
    return passed, {
        "point_count": point_count,
        "total_roots": total,
        "offsets_contiguous": bool(np.array_equal(offsets, expected_offsets)),
        "negative_counts": int(np.sum(counts < 0)),
        "flat_length_failures": flat_failures,
    }


def root_slice(group: h5py.Group, index: int) -> dict[str, np.ndarray]:
    offset = int(np.asarray(group["offset"])[index])
    count = int(np.asarray(group["count"])[index])
    selected = slice(offset, offset + count)
    result: dict[str, np.ndarray] = {}
    for name in group.keys():
        if name in ("offset", "count"):
            continue
        result[name] = np.asarray(group[name][selected])
    result["root"] = np.asarray(result["real"], dtype=float) + 1j * np.asarray(
        result["imag"], dtype=float
    )
    return result


def expected_points(
    candidate_contract: Mapping[str, Any], route_id: str, mode: str
) -> list[tuple[int, int]]:
    if mode == "pilot":
        return [
            (int(point[0]), int(point[1]))
            for point in candidate_contract["pilot_points"][route_id]
        ]
    return [(l_value, j_value) for l_value in range(31) for j_value in range(67)]


def load_step4_reference(record: Mapping[str, Any]) -> tuple[np.ndarray, np.ndarray]:
    path = resolve_relpath(record["mat_relpath"])
    with h5py.File(path, "r") as handle:
        rho = matlab_numeric(handle, "rho")
        stable = matlab_numeric(handle, "stable")
    if rho.shape != (31, 67) or stable.shape != (31, 67):
        raise ValueError(f"Unexpected Step-4 grid shape: {path}")
    return rho, stable


def verify_candidate_manifest(
    audit: Audit,
    mode_root: Path,
    mode: str,
    route_ids: Sequence[str],
    postcheck: Mapping[str, Any],
) -> tuple[list[Path], str]:
    path = mode_root / "artifact_manifest.csv"
    fields, rows = read_csv(path)
    expected_relpaths = sorted(
        [
            f"{route_id}/{filename}"
            for route_id in route_ids
            for filename in postcheck["route_scientific_files"]
        ]
        + list(postcheck["mode_scientific_files"])
    )
    actual_relpaths = [row.get("relpath", "") for row in rows]
    failures: list[dict[str, Any]] = []
    paths: list[Path] = []
    for row in rows:
        candidate = (mode_root / row["relpath"]).resolve()
        try:
            candidate.relative_to(mode_root.resolve())
        except ValueError:
            failures.append({"relpath": row["relpath"], "reason": "PATH_ESCAPE"})
            continue
        paths.append(candidate)
        if not candidate.is_file():
            failures.append({"relpath": row["relpath"], "reason": "MISSING"})
            continue
        observed = sha256_file(candidate)
        if observed != str(row.get("sha256", "")).upper():
            failures.append(
                {
                    "relpath": row["relpath"],
                    "reason": "SHA256",
                    "declared": row.get("sha256"),
                    "observed": observed,
                }
            )
        if int(row.get("bytes", "-1")) != candidate.stat().st_size:
            failures.append({"relpath": row["relpath"], "reason": "BYTES"})
    manifest_sha256 = sha256_file(path)
    sealed_hash = postcheck["sealed_mode_artifact_manifest_sha256"].get(mode)
    sealed_hash_matches = sealed_hash is None or manifest_sha256 == sealed_hash
    passed = (
        fields == postcheck["scientific_manifest_fields"]
        and len(rows) == postcheck["scientific_manifest_row_count"]
        and actual_relpaths == expected_relpaths
        and not failures
        and sealed_hash_matches
    )
    audit.add(
        "candidate_manifest",
        f"候选科学manifest精确列出{postcheck['scientific_manifest_row_count']}项工件且逐项字节数/SHA-256吻合",
        {
            "fields": postcheck["scientific_manifest_fields"],
            "row_count": postcheck["scientific_manifest_row_count"],
            "relpaths": expected_relpaths,
            "sealed_manifest_sha256": sealed_hash,
        },
        {
            "fields": fields,
            "row_count": len(rows),
            "relpaths": actual_relpaths,
            "failures": failures,
            "manifest_sha256": manifest_sha256,
            "sealed_hash_matches": sealed_hash_matches,
        },
        passed,
        relative(path),
    )
    return paths, manifest_sha256


def verify_repeatability(
    audit: Audit,
    candidate_root: Path,
    mode: str,
    manifest_sha256: str,
    postcheck: Mapping[str, Any],
) -> tuple[Path, dict[str, Any]]:
    path = candidate_root / f"{mode}_repeatability.json"
    document = read_json(path) if path.is_file() else {}
    actual = {
        "schema_version": document.get("schema_version"),
        "mode": document.get("mode"),
        "status": document.get("status"),
        "scientific_artifacts_match": document.get("scientific_artifacts_match"),
        "baseline": document.get("baseline_artifact_manifest_sha256"),
        "repeat": document.get("repeat_artifact_manifest_sha256"),
        "actual": manifest_sha256,
    }
    passed = (
        path.is_file()
        and actual["schema_version"] == postcheck["candidate_repeatability_schema"]
        and actual["mode"] == mode
        and actual["status"] == "PASS"
        and actual["scientific_artifacts_match"] is True
        and actual["baseline"] == actual["repeat"] == manifest_sha256
    )
    audit.add(
        "candidate_repeatability",
        "候选repeatability必须为PASS且baseline=repeat=实际科学manifest SHA-256",
        {
            "schema_version": postcheck["candidate_repeatability_schema"],
            "mode": mode,
            "status": "PASS",
            "scientific_artifacts_match": True,
            "baseline=repeat=actual": True,
        },
        actual,
        passed,
        relative(path) if path.is_file() else str(path),
    )
    return path, document


def verify_run_status(
    audit: Audit,
    mode_root: Path,
    mode: str,
    route_count: int,
    expected_count: int,
    input_seal: Mapping[str, Any],
    postcheck: Mapping[str, Any],
) -> dict[str, Any]:
    path = mode_root / "run_status.json"
    document = read_json(path)
    actual = {
        "schema_version": document.get("schema_version"),
        "status": document.get("status"),
        "mode": document.get("mode"),
        "route_count": document.get("route_count"),
        "expected_point_count": document.get("expected_point_count"),
        "completed_point_count": document.get("completed_point_count"),
        "pass_point_count": document.get("pass_point_count"),
        "fail_point_count": document.get("fail_point_count"),
        "input_identity_matches": document.get("input_identity") == input_seal,
    }
    passed = (
        actual["schema_version"] == postcheck["candidate_run_status_schema"]
        and actual["status"] == "PASS"
        and actual["mode"] == mode
        and actual["route_count"] == route_count
        and actual["expected_point_count"] == expected_count
        and actual["completed_point_count"] == expected_count
        and actual["pass_point_count"] == expected_count
        and actual["fail_point_count"] == 0
        and actual["input_identity_matches"] is True
    )
    audit.add(
        "candidate_run_status",
        "候选run_status必须绑定当前input seal并完整PASS全部合同点",
        {
            "schema_version": postcheck["candidate_run_status_schema"],
            "status": "PASS",
            "mode": mode,
            "route_count": route_count,
            "expected/completed/pass/fail": [expected_count, expected_count, expected_count, 0],
            "input_identity_matches": True,
        },
        actual,
        passed,
        relative(path),
    )
    immutability = document.get("v2_immutability", {})
    audit.add(
        "candidate_v2_immutability",
        "候选科学运行前后八个V2文件SHA-256保持不变",
        {"status": "PASS", "all_expected_and_unchanged": True},
        {
            "status": immutability.get("status"),
            "all_expected_and_unchanged": immutability.get(
                "all_expected_and_unchanged"
            ),
        },
        immutability.get("status") == "PASS"
        and immutability.get("all_expected_and_unchanged") is True,
        relative(path),
    )
    return document


def verify_checkpoint(
    audit: Audit,
    route_root: Path,
    route: Mapping[str, Any],
    points: Sequence[tuple[int, int]],
    input_seal: Mapping[str, Any],
    postcheck: Mapping[str, Any],
) -> tuple[Path, Path]:
    json_path = route_root / "checkpoint.json"
    h5_path = route_root / "checkpoint.h5"
    document = read_json(json_path) if json_path.is_file() else {}
    h5_hash = sha256_file(h5_path) if h5_path.is_file() else "MISSING"
    identity_keys = (
        "candidate_script_sha256",
        "candidate_contract_sha256",
        "route_manifest_sha256",
        "base_compute_sha256",
        "v2_engine_sha256",
        "hard_residual_math_sha256",
        "numeric_gates_sha256",
    )
    identity_failures = [
        key for key in identity_keys if document.get(key) != input_seal.get(key)
    ]
    h5_schema = "MISSING"
    record_count = -1
    if h5_path.is_file():
        with h5py.File(h5_path, "r") as handle:
            h5_schema = h5_text(handle.attrs.get("schema_version", ""))
            if "points/record_json" in handle:
                record_count = int(handle["points/record_json"].size)
    actual = {
        "schema_version": document.get("schema_version"),
        "state": document.get("state"),
        "completed_point_count": document.get("completed_point_count"),
        "route_id": document.get("route_id"),
        "workspace_sha256": document.get("workspace_sha256"),
        "point_order_sha256": document.get("point_order_sha256"),
        "checkpoint_h5_sha256_declared": document.get("checkpoint_h5_sha256"),
        "checkpoint_h5_sha256_observed": h5_hash,
        "h5_schema": h5_schema,
        "h5_record_count": record_count,
        "identity_failures": identity_failures,
    }
    passed = (
        json_path.is_file()
        and h5_path.is_file()
        and document.get("schema_version") == postcheck["candidate_checkpoint_schema"]
        and document.get("state") in postcheck["checkpoint_allowed_states"]
        and document.get("completed_point_count") == len(points)
        and document.get("route_id") == route["route_id"]
        and document.get("workspace_sha256") == route["workspace_sha256"]
        and document.get("point_order_sha256")
        == sha256_json([list(point) for point in points])
        and document.get("checkpoint_h5_sha256") == h5_hash
        and h5_schema == postcheck["candidate_roots_h5_schema"]
        and record_count == len(points)
        and not identity_failures
    )
    audit.add(
        "checkpoint_identity",
        f"{route['route_id']} checkpoint状态/身份/点序/HDF5哈希自洽",
        {
            "state_in": postcheck["checkpoint_allowed_states"],
            "completed_point_count": len(points),
            "route_id": route["route_id"],
            "workspace_sha256": route["workspace_sha256"],
            "point_order_sha256": sha256_json([list(point) for point in points]),
            "h5_hash_matches": True,
            "h5_schema": postcheck["candidate_roots_h5_schema"],
        },
        actual,
        passed,
        relative(json_path) if json_path.is_file() else str(json_path),
    )
    return json_path, h5_path


def h5_point_scalar(handle: h5py.File, field: str, index: int) -> Any:
    dataset = handle[f"points/{field}"]
    value = dataset[index]
    if isinstance(value, (bytes, np.bytes_)):
        return value.decode("utf-8")
    if isinstance(value, np.generic):
        return value.item()
    return value


def validate_route_scientific(
    audit: Audit,
    validation: Mapping[str, Any],
    candidate_contract: Mapping[str, Any],
    route: Mapping[str, Any],
    mode: str,
    route_root: Path,
    step4_rho: np.ndarray,
    step4_stable: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    postcheck = validation["postcheck"]
    gates = postcheck["gates"]
    route_id = route["route_id"]
    points = expected_points(candidate_contract, route_id, mode)
    expected_algorithm = validation["candidate_contract_rules"]["selected_algorithms"][
        route_id
    ]
    expected_pairing_role = validation["candidate_contract_rules"][
        "pairing_diagnostic_roles"
    ][expected_algorithm]
    expected_order = validation["candidate_contract_rules"]["matrix_orders"][route_id]
    summary_path = route_root / "point_summary.csv"
    roots_path = route_root / "roots.h5"
    status_path = route_root / "route_status.json"
    runtime_path = route_root / "point_runtime.csv"
    fields, raw_rows = read_csv(summary_path)
    rows = [parse_csv_record(row) for row in raw_rows]
    observed_points = [
        (int(row.get("l", -1)), int(row.get("j", -1))) for row in rows
    ]
    audit.add(
        "route_csv_schema",
        f"{route_id} CSV字段与{len(points)}个点的顺序精确匹配合同",
        {"fields": postcheck["point_summary_fields"], "points": points},
        {"fields": fields, "points": observed_points},
        fields == postcheck["point_summary_fields"] and observed_points == points,
        relative(summary_path),
    )
    runtime_fields, runtime_rows = read_csv(runtime_path)
    runtime_points = [
        (int(row.get("l", -1)), int(row.get("j", -1))) for row in runtime_rows
    ]
    runtime_failures = [
        index
        for index, row in enumerate(runtime_rows)
        if row.get("route_id") != route_id
        or row.get("point_status") != "PASS"
        or not math.isfinite(as_float(row.get("elapsed_seconds")))
        or as_float(row.get("elapsed_seconds")) < 0.0
    ]
    audit.add(
        "route_runtime_schema",
        f"{route_id} operational point_runtime为封签源码定义的5列且点序完整（时间不进入科学哈希）",
        {
            "fields": postcheck["point_runtime_fields"],
            "points": points,
            "row_failures": [],
        },
        {
            "fields": runtime_fields,
            "points": runtime_points,
            "row_failures": runtime_failures,
        },
        runtime_fields == postcheck["point_runtime_fields"]
        and runtime_points == points
        and not runtime_failures,
        relative(runtime_path),
    )
    route_status = read_json(status_path)
    route_status_actual = {
        "schema_version": route_status.get("schema_version"),
        "status": route_status.get("status"),
        "route_id": route_status.get("route_id"),
        "expected_point_count": route_status.get("expected_point_count"),
        "completed_point_count": route_status.get("completed_point_count"),
        "pass_point_count": route_status.get("pass_point_count"),
        "fail_point_count": route_status.get("fail_point_count"),
        "selected_algorithm": route_status.get("selected_algorithm"),
        "matrix_order": route_status.get("matrix_order"),
        "point_summary_sha256": route_status.get("point_summary_sha256"),
        "roots_h5_sha256": route_status.get("roots_h5_sha256"),
    }
    route_status_passed = (
        route_status.get("schema_version") == postcheck["candidate_route_status_schema"]
        and route_status.get("status") == "PASS"
        and route_status.get("route_id") == route_id
        and route_status.get("expected_point_count") == len(points)
        and route_status.get("completed_point_count") == len(points)
        and route_status.get("pass_point_count") == len(points)
        and route_status.get("fail_point_count") == 0
        and route_status.get("selected_algorithm") == expected_algorithm
        and route_status.get("matrix_order") == expected_order
        and route_status.get("point_summary_sha256") == sha256_file(summary_path)
        and route_status.get("roots_h5_sha256") == sha256_file(roots_path)
    )
    audit.add(
        "route_status",
        f"{route_id} route_status完整PASS并绑定CSV/HDF5哈希",
        {
            "schema": postcheck["candidate_route_status_schema"],
            "status": "PASS",
            "point_count": len(points),
            "algorithm": expected_algorithm,
            "matrix_order": expected_order,
            "hashes_match": True,
        },
        route_status_actual,
        route_status_passed,
        relative(status_path),
    )
    point_rows: list[dict[str, Any]] = []
    route_math = load_route_math(route)
    schema_failures: list[str] = []
    point_integrity_failures: list[str] = []
    residual_failure_points: list[list[int]] = []
    rho_failure_points: list[list[int]] = []
    stable_failure_points: list[list[int]] = []
    formula_failure_points: list[list[int]] = []
    safety_failure_points: list[list[int]] = []
    recompute_mismatch_points: list[list[int]] = []
    max_rho_diff = 0.0
    max_poly = 0.0
    max_laurent = 0.0
    origin_count = 0
    with h5py.File(roots_path, "r") as handle:
        schema = h5_text(handle.attrs.get("schema_version", ""))
        hard_label = h5_text(handle.attrs.get("hard_residual_definition", ""))
        vector_role = h5_text(handle.attrs.get("vector_block_residual_role", ""))
        if schema != postcheck["candidate_roots_h5_schema"]:
            schema_failures.append("schema_version")
        if hard_label != validation["candidate_contract_rules"]["hard_residual_definition"]:
            schema_failures.append("hard_residual_definition")
        if vector_role != validation["candidate_contract_rules"]["vector_block_residual_role"]:
            schema_failures.append("vector_block_residual_role")
        if "points/record_json" not in handle:
            schema_failures.append("points/record_json")
            records: list[str] = []
        else:
            records = [h5_text(item) for item in handle["points/record_json"][...]]
        if len(records) != len(rows):
            schema_failures.append("record_count")
        points_group = handle.get("points")
        for field_name in postcheck["point_summary_fields"]:
            if points_group is None or field_name not in points_group:
                schema_failures.append(f"points/{field_name}")
            elif int(points_group[field_name].size) != len(rows):
                schema_failures.append(f"points/{field_name}:length")
        for group_name in postcheck["root_groups"]:
            if group_name not in handle:
                schema_failures.append(group_name)
                continue
            passed, detail = validate_root_group_layout(
                handle[group_name], len(rows), postcheck["root_datasets"]
            )
            if not passed:
                schema_failures.append(f"{group_name}:{canonical_json(detail)}")
        if not schema_failures:
            for index, row in enumerate(rows):
                l_value, j_value = points[index]
                record = json.loads(records[index])
                for field_name in postcheck["point_summary_fields"]:
                    if not scalar_equal(
                        row.get(field_name), record.get(field_name), field_name=field_name
                    ):
                        point_integrity_failures.append(
                            f"{l_value},{j_value}:csv-json:{field_name}"
                        )
                        break
                    h5_value = h5_point_scalar(handle, field_name, index)
                    if not scalar_equal(
                        record.get(field_name), h5_value, field_name=field_name
                    ):
                        point_integrity_failures.append(
                            f"{l_value},{j_value}:json-h5:{field_name}"
                        )
                        break
                selected_raw = root_slice(handle["selected/raw"], index)
                selected = root_slice(handle["selected/retained"], index)
                compact_raw = root_slice(handle["pairing_compact/raw"], index)
                compact = root_slice(handle["pairing_compact/retained"], index)
                roots = np.asarray(selected["root"], dtype=np.complex128)
                if (
                    len(selected_raw["root"]) != int(row["raw_root_count"])
                    or len(roots) != int(row["retained_root_count"])
                    or len(compact_raw["root"]) != int(row["compact_raw_root_count"])
                    or len(compact["root"]) != int(row["compact_retained_root_count"])
                ):
                    point_integrity_failures.append(
                        f"{l_value},{j_value}:root-count"
                    )
                rho_candidate = float(row["rho"])
                rho_from_roots = (
                    float(np.max(np.abs(roots))) if roots.size else math.nan
                )
                stable_candidate = bool(row["stable"])
                stable_rule = (
                    math.isfinite(rho_candidate)
                    and rho_candidate > 0.0
                    and rho_candidate < 1.0
                )
                critical_rule = math.isfinite(rho_candidate) and abs(
                    rho_candidate - 1.0
                ) <= 1e-8
                if (
                    not float_equal(rho_candidate, rho_from_roots, 1e-14, 1e-14)
                    or stable_candidate != stable_rule
                    or bool(row["critical"]) != critical_rule
                    or row["point_status"] != "PASS"
                    or row["failure_code"] not in ("", None)
                    or row["matrix_order"] != expected_order
                    or row["algorithm_selector_field"] != "matrix_order"
                    or row["algorithm_selector_value"] != expected_order
                    or row["selected_algorithm"] != expected_algorithm
                    or row["hard_residual_definition"]
                    != validation["candidate_contract_rules"]["hard_residual_definition"]
                    or row["vector_block_residual_role"]
                    != validation["candidate_contract_rules"]["vector_block_residual_role"]
                    or row["pairing_diagnostic_role"]
                    != expected_pairing_role
                    or bool(row["stable_classification_match"]) is not True
                    or bool(row["all_gated_svd_residuals_finite"]) is not True
                ):
                    point_integrity_failures.append(
                        f"{l_value},{j_value}:point-identity"
                    )
                if expected_algorithm == "FULL_Q_ORDINARY_HISTORY_COMPANION":
                    gated = np.asarray(selected["matched_physical"], dtype=bool)
                else:
                    gated = np.ones(roots.shape, dtype=bool)
                if int(np.sum(gated)) != int(row["matched_physical_root_count"]):
                    point_integrity_failures.append(
                        f"{l_value},{j_value}:matched-count"
                    )
                terms = direct_terms(route_math, l_value, j_value)
                coefficients = consolidate_terms(terms)
                poly_terms, clearing, degree = polynomial_terms_from_coefficients(
                    coefficients
                )
                if clearing != int(row["clearing_power"]) or degree != int(
                    row["polynomial_degree"]
                ):
                    point_integrity_failures.append(
                        f"{l_value},{j_value}:polynomial-identity"
                    )
                prepared_poly = prepared_terms(poly_terms)
                prepared_laurent = prepared_terms(terms)
                independent_poly = np.asarray(
                    [
                        normalized_svd_residual(prepared_poly, root)
                        for root in roots[gated]
                    ],
                    dtype=float,
                )
                independent_laurent = np.asarray(
                    [
                        normalized_svd_residual(prepared_laurent, root)
                        for root in roots[gated]
                    ],
                    dtype=float,
                )
                saved_poly = np.asarray(
                    selected["svd_polynomial_residual"], dtype=float
                )[gated]
                saved_laurent = np.asarray(
                    selected["svd_laurent_residual"], dtype=float
                )[gated]
                independent_poly_max = (
                    float(np.max(independent_poly))
                    if independent_poly.size
                    else math.inf
                )
                independent_laurent_max = (
                    float(np.max(independent_laurent))
                    if independent_laurent.size
                    else math.inf
                )
                max_poly = max(max_poly, independent_poly_max)
                max_laurent = max(max_laurent, independent_laurent_max)
                residual_gate_pass = (
                    independent_poly.size > 0
                    and independent_laurent.size > 0
                    and np.all(np.isfinite(independent_poly))
                    and np.all(np.isfinite(independent_laurent))
                    and independent_poly_max <= gates["svd_polynomial_residual"]
                    and independent_laurent_max <= gates["svd_laurent_residual"]
                )
                if not residual_gate_pass:
                    residual_failure_points.append([l_value, j_value])
                saved_match = (
                    saved_poly.shape == independent_poly.shape
                    and saved_laurent.shape == independent_laurent.shape
                    and all(
                        float_equal(
                            float(first),
                            float(second),
                            gates["saved_vs_recomputed_residual_abs_tolerance"],
                            gates["saved_vs_recomputed_residual_relative_tolerance"],
                        )
                        for first, second in zip(saved_poly, independent_poly)
                    )
                    and all(
                        float_equal(
                            float(first),
                            float(second),
                            gates["saved_vs_recomputed_residual_abs_tolerance"],
                            gates["saved_vs_recomputed_residual_relative_tolerance"],
                        )
                        for first, second in zip(saved_laurent, independent_laurent)
                    )
                    and float_equal(
                        float(row["max_gated_svd_polynomial_residual"]),
                        independent_poly_max,
                        gates["saved_vs_recomputed_residual_abs_tolerance"],
                        gates["saved_vs_recomputed_residual_relative_tolerance"],
                    )
                    and float_equal(
                        float(row["max_gated_svd_laurent_residual"]),
                        independent_laurent_max,
                        gates["saved_vs_recomputed_residual_abs_tolerance"],
                        gates["saved_vs_recomputed_residual_relative_tolerance"],
                    )
                )
                if not saved_match:
                    recompute_mismatch_points.append([l_value, j_value])
                formula_difference = formula_identity_difference(
                    route_math, coefficients, l_value, j_value
                )
                formula_pass = (
                    formula_difference <= gates["formula_identity_relative_difference"]
                    and float(row["direct_formula_coefficient_relative_difference"])
                    <= gates["formula_identity_relative_difference"]
                    and float_equal(
                        formula_difference,
                        float(row["direct_formula_coefficient_relative_difference"]),
                        gates["formula_identity_relative_difference"],
                        gates["formula_identity_relative_difference"],
                    )
                )
                if not formula_pass:
                    formula_failure_points.append([l_value, j_value])
                unmatched = np.asarray(selected["unmatched_full"], dtype=bool)
                unmatched_roots = roots[unmatched]
                unmatched_count = int(np.sum(unmatched))
                unmatched_max = (
                    float(np.max(np.abs(unmatched_roots)))
                    if unmatched_roots.size
                    else None
                )
                safety_pass = (
                    unmatched_count == int(row["unmatched_full_root_count"])
                    and unmatched_count <= int(row["theoretical_extra_zero_count"])
                    and (
                        unmatched_max is None
                        or unmatched_max < gates["unmatched_full_max_abs_strictly_below"]
                    )
                    and (unmatched_max is None or unmatched_max < rho_candidate)
                    and bool(row["unmatched_count_within_theoretical"])
                    and bool(row["unmatched_full_below_0p9"])
                    and bool(row["unmatched_full_strictly_nondominant"])
                )
                if not safety_pass:
                    safety_failure_points.append([l_value, j_value])
                if unmatched_count > 0:
                    origin_count += 1
                rho_step4 = float(step4_rho[l_value, j_value])
                stable_step4 = bool(step4_stable[l_value, j_value] != 0)
                rho_diff = abs(rho_candidate - rho_step4)
                max_rho_diff = max(max_rho_diff, rho_diff)
                rho_pass = (
                    math.isfinite(rho_candidate)
                    and rho_candidate > 0.0
                    and math.isfinite(rho_step4)
                    and rho_diff <= gates["rho_abs_difference_to_step4"]
                )
                stable_match = stable_candidate == stable_step4
                if not rho_pass:
                    rho_failure_points.append([l_value, j_value])
                if not stable_match:
                    stable_failure_points.append([l_value, j_value])
                point_rows.append(
                    {
                        "route_id": route_id,
                        "l": l_value,
                        "j": j_value,
                        "rho_candidate": rho_candidate,
                        "rho_step4_matlab": rho_step4,
                        "rho_abs_diff": rho_diff,
                        "rho_gate_pass": rho_pass,
                        "stable_candidate": stable_candidate,
                        "stable_step4_matlab": stable_step4,
                        "stable_match": stable_match,
                        "recomputed_max_svd_polynomial_residual": independent_poly_max,
                        "recomputed_max_svd_laurent_residual": independent_laurent_max,
                        "saved_recomputed_residual_match": saved_match,
                        "formula_relative_difference": formula_difference,
                        "unmatched_safety_pass": safety_pass,
                        "origin_splitting_status": row["origin_splitting_status"],
                        "point_status": row["point_status"],
                    }
                )
    audit.add(
        "route_hdf5_schema",
        f"{route_id} roots.h5的schema、70个points dataset及四个ragged根组完整自洽",
        [],
        schema_failures,
        not schema_failures,
        relative(roots_path),
    )
    audit.add(
        "route_point_identity",
        f"{route_id} CSV/record_json/points datasets、根数量、rho和算法身份逐点一致",
        [],
        point_integrity_failures,
        not point_integrity_failures,
        relative(roots_path),
    )
    audit.add(
        "route_svd_recompute",
        f"{route_id}所有门控物理根独立重算P(z)/G(z)归一SVD残差<=1e-8且与保存值相符",
        {
            "residual_gate_failures": [],
            "saved_recompute_mismatches": [],
        },
        {
            "max_polynomial": max_poly,
            "max_laurent": max_laurent,
            "residual_gate_failures": residual_failure_points,
            "saved_recompute_mismatches": recompute_mismatch_points,
        },
        not residual_failure_points and not recompute_mismatch_points,
        relative(roots_path),
    )
    audit.add(
        "route_formula_identity",
        f"{route_id}同一Laurent系数与直接公式身份误差<=1e-12",
        [],
        formula_failure_points,
        not formula_failure_points,
        relative(summary_path),
    )
    audit.add(
        "route_step4_rho",
        f"{route_id}逐点rho与Step-4 MATLAB绝对差<=1e-8",
        [],
        {"max_abs_diff": max_rho_diff, "failure_points": rho_failure_points},
        not rho_failure_points,
        validation["sealed_step4_references"][route_id]["mat_relpath"],
    )
    audit.add(
        "route_stable_classification",
        f"{route_id}逐点rho<1稳定分类与Step-4 MATLAB一致",
        [],
        stable_failure_points,
        not stable_failure_points,
        validation["sealed_step4_references"][route_id]["mat_relpath"],
    )
    audit.add(
        "route_origin_safety",
        f"{route_id}原点重根裂分仅为INFO，未匹配full-q根数量/<0.9/非主导安全门为硬检查",
        [],
        {
            "origin_splitting_point_count": origin_count,
            "safety_failure_points": safety_failure_points,
        },
        not safety_failure_points,
        relative(roots_path),
        information=not safety_failure_points and origin_count > 0,
    )
    failures = (
        bool(schema_failures)
        or bool(point_integrity_failures)
        or bool(residual_failure_points)
        or bool(recompute_mismatch_points)
        or bool(formula_failure_points)
        or bool(rho_failure_points)
        or bool(stable_failure_points)
        or bool(safety_failure_points)
        or not route_status_passed
        or fields != postcheck["point_summary_fields"]
        or observed_points != points
        or runtime_fields != postcheck["point_runtime_fields"]
        or runtime_points != points
        or bool(runtime_failures)
    )
    route_summary = {
        "route_id": route_id,
        "point_count": len(points),
        "max_rho_abs_diff_to_step4": max_rho_diff,
        "rho_gate_fail_count": len(rho_failure_points),
        "stable_mismatch_count": len(stable_failure_points),
        "max_recomputed_svd_polynomial_residual": max_poly,
        "max_recomputed_svd_laurent_residual": max_laurent,
        "residual_gate_fail_count": len(residual_failure_points)
        + len(recompute_mismatch_points),
        "formula_gate_fail_count": len(formula_failure_points),
        "unmatched_safety_fail_count": len(safety_failure_points),
        "origin_splitting_point_count": origin_count,
        "status": "FAIL" if failures else "PASS",
    }
    return route_summary, point_rows


def report_postcheck(
    path: Path,
    summary: Mapping[str, Any],
    route_rows: Sequence[Mapping[str, Any]],
    conditioning_rows: Sequence[Mapping[str, Any]],
) -> None:
    lines = [
        "# Board20 Step5第四版隔离候选 / validator V3独立只读事后验收",
        "",
        f"> 结论：`{summary['overall_status']}`。validator没有启动候选计算，也没有修改候选或既有证据。",
        "",
        "## 路线结果",
        "",
        "| 文件身份路线 | 点数 | 最大rho绝对差 | 最大P(z) SVD残差 | 最大G(z) SVD残差 | 状态 |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for row in route_rows:
        lines.append(
            "| {route_id} | {point_count} | {max_rho_abs_diff_to_step4:.17g} | "
            "{max_recomputed_svd_polynomial_residual:.17g} | "
            "{max_recomputed_svd_laurent_residual:.17g} | {status} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 第二分区此前四个病态坐标",
            "",
            "| 路线 | (l,j) | V4 rho | Step-4 MATLAB rho | 绝对差 | 门槛 |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for row in conditioning_rows:
        lines.append(
            f"| {row['route_id']} | ({row['l']},{row['j']}) | "
            f"{row['rho_candidate']:.17g} | {row['rho_step4_matlab']:.17g} | "
            f"{row['rho_abs_diff']:.17g} | {'PASS' if row['rho_gate_pass'] else 'FAIL'} |"
        )
    lines.extend(
        [
            "",
            "## 裁决边界",
            "",
            "- 直接归一sigma_min残差、rho差、stable分类、公式身份和未匹配根安全条件均是硬门。",
            "- 旧伴随向量q块残差、compact/full-q全根匹配差和安全范围内的原点重根裂分只作诊断。",
            "- 任何PASS只适用于五条封签作者文件身份路线；硕士论文路线和manuscript_0824路线仍未闭合。",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def run_postcheck(mode_arg: str) -> dict[str, Any]:
    validation = read_json(CONTRACT_PATH)
    scientific_mode = "pilot" if mode_arg == "pilot-postcheck" else "full"
    audit = Audit(
        "S5FQSV4-V3-" + ("PILOT" if scientific_mode == "pilot" else "FULL")
    )
    expected_static = expected_static_hashes(validation)
    candidate_contract = read_json(
        resolve_relpath(validation["paths"]["candidate_contract"])
    )
    candidate_root = resolve_relpath(validation["paths"]["candidate_output_root"])
    mode_root = candidate_root / scientific_mode
    route_ids = validation["candidate_contract_rules"]["route_ids"]
    route_map = {item["route_id"]: item for item in candidate_contract["routes"]}
    expected_total = (
        validation["candidate_contract_rules"]["pilot_total_points"]
        if scientific_mode == "pilot"
        else validation["candidate_contract_rules"]["full_total_points"]
    )
    check_expected_hashes(audit, expected_static)
    check_source_isolation(audit, validation)
    check_candidate_contract(audit, validation)
    check_static_candidate_documents(audit, validation)
    check_prior_verdicts(audit)
    check_validator_v2_precheck_failure_preservation(audit, validation)
    check_step4_audit_manifest(audit, validation)
    check_validator_math_selftest(audit)
    manifest_paths, manifest_hash = verify_candidate_manifest(
        audit, mode_root, scientific_mode, route_ids, validation["postcheck"]
    )
    repeat_path, _repeatability = verify_repeatability(
        audit,
        candidate_root,
        scientific_mode,
        manifest_hash,
        validation["postcheck"],
    )
    input_seal_path = candidate_root / "input_seal.json"
    input_seal = read_json(input_seal_path)
    run_status = verify_run_status(
        audit,
        mode_root,
        scientific_mode,
        len(route_ids),
        expected_total,
        input_seal,
        validation["postcheck"],
    )
    if scientific_mode == "full":
        pilot_audit_path = resolve_relpath(
            validation["postcheck"]["prior_pilot_validator_audit_relpath"]
        )
        pilot_audit = read_json(pilot_audit_path) if pilot_audit_path.is_file() else {}
        audit.add(
            "prior_pilot_validator",
            "full事后验收要求同一独立validator的49点pilot裁决已PASS",
            "PASS",
            pilot_audit.get("summary", {}).get("overall_status", "MISSING"),
            pilot_audit.get("summary", {}).get("overall_status") == "PASS",
            relative(pilot_audit_path) if pilot_audit_path.is_file() else str(pilot_audit_path),
        )
    checkpoint_paths: list[Path] = []
    for route_id in route_ids:
        points = expected_points(candidate_contract, route_id, scientific_mode)
        checkpoint_paths.extend(
            verify_checkpoint(
                audit,
                mode_root / route_id,
                route_map[route_id],
                points,
                input_seal,
                validation["postcheck"],
            )
        )
    protected_paths = set(expected_static)
    protected_paths.update(manifest_paths)
    protected_paths.add(mode_root / "artifact_manifest.csv")
    protected_paths.add(repeat_path)
    protected_paths.update(checkpoint_paths)
    for route in candidate_contract["routes"]:
        protected_paths.add(resolve_relpath(route["workspace_relpath"]))
        protected_paths.add(
            mode_root / route["route_id"] / "point_runtime.csv"
        )
    if scientific_mode == "full":
        protected_paths.add(
            resolve_relpath(
                validation["postcheck"]["prior_pilot_validator_audit_relpath"]
            )
        )
    before = hash_snapshot(protected_paths)
    route_rows: list[dict[str, Any]] = []
    point_rows: list[dict[str, Any]] = []
    for route_id in route_ids:
        step4_rho, step4_stable = load_step4_reference(
            validation["sealed_step4_references"][route_id]
        )
        route_summary, route_points = validate_route_scientific(
            audit,
            validation,
            candidate_contract,
            route_map[route_id],
            scientific_mode,
            mode_root / route_id,
            step4_rho,
            step4_stable,
        )
        route_rows.append(route_summary)
        point_rows.extend(route_points)
    forbidden_ids = validation["candidate_contract_rules"]["failed_route_ids"] + validation[
        "candidate_contract_rules"
    ]["paper_route_ids"]
    forbidden = [
        relative(path)
        for route_id in forbidden_ids
        for path in candidate_root.glob(f"**/{route_id}")
        if path.is_dir()
    ]
    audit.add(
        "forbidden_outputs",
        "四失败路线和两论文合同未闭合路线未创建候选网格目录",
        [],
        forbidden,
        not forbidden,
        relative(candidate_root),
    )
    after = hash_snapshot(protected_paths)
    changed = [path for path in before if before[path] != after.get(path)]
    audit.add(
        "immutability",
        "事后验收前后候选科学工件、checkpoint、Step-4基准、workspace及既有失败证据哈希完全不变",
        [],
        changed,
        not changed,
    )
    conditioning_points = {
        tuple(point)
        for point in validation["candidate_contract_rules"][
            "previous_conditioning_points"
        ]
    }
    conditioning_routes = set(
        validation["candidate_contract_rules"]["previous_conditioning_routes"]
    )
    conditioning_rows = [
        row
        for row in point_rows
        if row["route_id"] in conditioning_routes
        and (row["l"], row["j"]) in conditioning_points
    ]
    expected_conditioning_count = 8
    audit.add(
        "previous_conditioning_points",
        "第二分区Original/Guyan此前四个病态坐标共8条路线点记录单独报告",
        expected_conditioning_count,
        len(conditioning_rows),
        len(conditioning_rows) == expected_conditioning_count,
    )
    authorization_binding = {
        "candidate_script_sha256": validation["sealed_candidate_identity"][
            "candidate_script_sha256"
        ],
        "candidate_contract_sha256": validation["sealed_candidate_identity"][
            "candidate_contract_sha256"
        ],
        "input_seal_sha256": sha256_file(input_seal_path),
        "run_status_sha256": sha256_file(mode_root / "run_status.json"),
        "artifact_manifest_sha256": manifest_hash,
        "repeatability_sha256": sha256_file(repeat_path)
        if repeat_path.is_file()
        else "MISSING",
        "validator_script_sha256": sha256_file(SCRIPT_PATH),
        "validator_contract_sha256": sha256_file(CONTRACT_PATH),
        "mode": scientific_mode,
        "candidate_status": run_status.get("status"),
        "full_computation_launched_by_validator": False,
    }
    return write_audit_bundle(
        mode_arg,
        audit,
        validation,
        before,
        after,
        route_rows,
        point_rows,
        conditioning_rows,
        authorization_binding,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        required=True,
        choices=("precheck", "pilot-postcheck", "full-postcheck"),
    )
    parser.add_argument(
        "--explicit-postcheck-authorization",
        action="store_true",
        help="Required for pilot/full postcheck. This never launches computation.",
    )
    return parser


def waiting_v4_guard(mode: str) -> dict[str, Any] | None:
    """Fail closed unless the contract has one exact formal sealed status."""
    validation = read_json(CONTRACT_PATH)
    contract_status = validation.get("contract_status")
    if contract_status in FORMAL_CONTRACT_STATUSES:
        return None
    protected = {
        "validator_v1": [VALIDATOR_V1_PATH, VALIDATOR_V1_SHA256],
        "failure_attribution": [
            FAILURE_ATTRIBUTION_PATH,
            FAILURE_ATTRIBUTION_SHA256,
        ],
        "validator_v2": [VALIDATOR_V2_PATH, VALIDATOR_V2_SHA256],
        "validator_v2_precheck_failure": [
            VALIDATOR_V2_FAILURE_PATH,
            VALIDATOR_V2_FAILURE_SHA256,
        ],
        "revision_record": [
            REVISION_RECORD_PATH,
            validation.get("revision_record_sha256"),
        ],
    }
    observed = {
        name: sha256_file(path) if path.is_file() else "MISSING"
        for name, (path, _expected) in protected.items()
    }
    expected = {name: value for name, (_path, value) in protected.items()}
    unchanged = observed == expected
    pending = validation.get("pending_v4_identity", {})
    waiting = contract_status == "WAITING_VALIDATOR_V3_SEAL"
    status = (
        "WAITING_VALIDATOR_V3_SEAL"
        if waiting and unchanged
        else (
            "PROTECTED_PREDECESSOR_EVIDENCE_MISMATCH"
            if waiting
            else "INVALID_UNSEALED_CONTRACT_STATUS"
        )
    )
    return {
        "schema_version": "board20_step5_fullq_svd_candidate_validator_v3_waiting_guard_v1",
        "mode": mode,
        "status": status,
        "contract_status": contract_status,
        "allowed_formal_contract_statuses": sorted(FORMAL_CONTRACT_STATUSES),
        "predecessor_validators_and_failure_records_unchanged": unchanged,
        "expected_protected_sha256": expected,
        "observed_protected_sha256": observed,
        "pending_v4_identity": pending,
        "candidate_scientific_outputs_parsed": False,
        "candidate_computation_launched": False,
        "audit_output_written": False,
        "postcheck_authorized": False,
    }


def main() -> int:
    args = build_parser().parse_args()
    guard = waiting_v4_guard(args.mode)
    if guard is not None:
        print(canonical_json(guard))
        return 3 if guard["status"] == "WAITING_VALIDATOR_V3_SEAL" else 1
    if args.mode == "precheck":
        summary = run_precheck()
        print(canonical_json(summary))
        return 0 if summary["overall_status"].startswith("PASS") else 1
    validation = read_json(CONTRACT_PATH)
    scientific_mode = "pilot" if args.mode == "pilot-postcheck" else "full"
    enabled_key = f"{scientific_mode}_postcheck_enabled"
    if validation.get("activation_policy", {}).get(enabled_key) is not True:
        guard = {
            "schema_version": "board20_step5_fullq_svd_candidate_postcheck_guard_v3",
            "mode": args.mode,
            "status": "NOT_SEALED_FOR_POSTCHECK",
            "reason": (
                "The formal V4 validator contract is precheck-only. A new "
                "candidate-mode seal, repeatability identity, explicit external "
                "authorization, and contract revision are required before postcheck."
            ),
            "candidate_scientific_outputs_parsed": False,
            "candidate_computation_launched": False,
        }
        print(canonical_json(guard))
        return 2
    if not args.explicit_postcheck_authorization:
        guard = {
            "schema_version": "board20_step5_fullq_svd_candidate_postcheck_guard_v1",
            "mode": args.mode,
            "status": "NOT_AUTHORIZED",
            "reason": "Explicit external authorization plus --explicit-postcheck-authorization is required. No candidate file was parsed or modified.",
            "candidate_computation_launched": False,
        }
        print(canonical_json(guard))
        return 2
    summary = run_postcheck(args.mode)
    print(canonical_json(summary))
    return 0 if summary["overall_status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

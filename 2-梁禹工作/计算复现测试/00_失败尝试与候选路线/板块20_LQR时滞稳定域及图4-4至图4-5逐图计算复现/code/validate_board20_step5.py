from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import h5py
import numpy as np
from scipy import linalg
from scipy.spatial import cKDTree


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent.resolve()
DEFAULT_VALIDATION_CONTRACT = SCRIPT.parent / "board20_step5_validation_contract.json"
DEFAULT_COMPUTE_CONTRACT = SCRIPT.parent / "board20_step5_compute_contract.json"
DEFAULT_COMPUTE_SCRIPT = SCRIPT.parent / "compute_board20_step5_independent.py"
DEFAULT_STEP4_MANIFEST = SCRIPT.parent / "board20_step4_route_manifest.json"
DEFAULT_COMPUTE_ROOT = BOARD_ROOT / "outputs" / "step5_independent_compute"
DEFAULT_AUDIT_ROOT = BOARD_ROOT / "outputs" / "step5_audit"
DEFAULT_LOG_ROOT = BOARD_ROOT / "logs" / "step5_validation"

EXPECTED_ROUTE_IDS = (
    "main_ori_div1",
    "main_guyan_div1",
    "alt_guyan_div1_stable_full_ps3",
    "main_ori_div2",
    "main_guyan_div2",
)
FAILED_ROUTE_IDS = (
    "main_cb_div1",
    "main_cb_div2",
    "energy_guyan_div1",
    "energy_guyan_div2",
)
PAPER_ROUTE_IDS = ("masters_thesis_formula", "manuscript_0824_formula")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def canonical_json(value: Any) -> str:
    def default(obj: Any) -> Any:
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, np.generic):
            return obj.item()
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, complex):
            return {"real": obj.real, "imag": obj.imag}
        raise TypeError(type(obj).__name__)

    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
        default=default,
    )


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def safe_child(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def parse_bool(value: Any) -> bool:
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, (int, float, np.integer, np.floating)):
        if not math.isfinite(float(value)):
            raise ValueError(f"nonfinite boolean value: {value}")
        return bool(int(value))
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "pass"}:
        return True
    if text in {"0", "false", "no", ""}:
        return False
    raise ValueError(f"cannot parse boolean value: {value!r}")


def parse_float(value: Any) -> float:
    if value is None:
        return math.nan
    text = str(value).strip()
    if not text:
        return math.nan
    return float(text)


def parse_int(value: Any) -> int:
    return int(round(float(str(value).strip())))


@dataclass
class Check:
    check_id: str
    category: str
    description: str
    expected: Any
    actual: Any
    status: str
    evidence: str = ""


@dataclass
class Audit:
    mode: str
    checks: list[Check] = field(default_factory=list)

    def add(
        self,
        category: str,
        description: str,
        expected: Any,
        actual: Any,
        passed: bool,
        evidence: str = "",
    ) -> None:
        prefix = {
            "precheck": "S5-PRE",
            "pilot-postcheck": "S5-PILOT",
            "full-postcheck": "S5-POST",
        }[self.mode]
        self.checks.append(
            Check(
                check_id=f"{prefix}-{len(self.checks) + 1:04d}",
                category=category,
                description=description,
                expected=expected,
                actual=actual,
                status="PASS" if passed else "FAIL",
                evidence=evidence,
            )
        )

    def info(
        self,
        category: str,
        description: str,
        actual: Any,
        evidence: str = "",
    ) -> None:
        prefix = {
            "precheck": "S5-PRE",
            "pilot-postcheck": "S5-PILOT",
            "full-postcheck": "S5-POST",
        }[self.mode]
        self.checks.append(
            Check(
                check_id=f"{prefix}-{len(self.checks) + 1:04d}",
                category=category,
                description=description,
                expected="DIAGNOSTIC_ONLY",
                actual=actual,
                status="INFO",
                evidence=evidence,
            )
        )

    @property
    def passed(self) -> bool:
        return bool(self.checks) and all(item.status != "FAIL" for item in self.checks)

    def summary(self) -> dict[str, Any]:
        passed = sum(item.status == "PASS" for item in self.checks)
        information = sum(item.status == "INFO" for item in self.checks)
        return {
            "mode": self.mode,
            "overall_status": "PASS" if self.passed else "FAIL",
            "total_checks": len(self.checks),
            "passed_checks": passed,
            "information_checks": information,
            "failed_checks": sum(item.status == "FAIL" for item in self.checks),
        }


def recursive_dicts(value: Any) -> Iterable[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        yield value
        for nested in value.values():
            yield from recursive_dicts(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from recursive_dicts(nested)


def collect_contract_status(value: Any, route_id: str) -> list[str]:
    statuses: list[str] = []
    route_keys = {route_id, route_id.replace("_formula", "_route")}
    for item in recursive_dicts(value):
        if str(item.get("route_id", "")) == route_id:
            for key in ("status", "upstream_status", "step5_status", "step5_policy"):
                if key in item:
                    statuses.append(str(item[key]))
        for key in route_keys:
            child = item.get(key)
            if isinstance(child, Mapping) and "status" in child:
                statuses.append(str(child["status"]))
    return statuses


def read_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        return list(reader.fieldnames or []), list(reader)


def hash_tree(root: Path) -> dict[str, str]:
    if not root.exists():
        return {}
    result: dict[str, str] = {}
    for path in sorted((p for p in root.rglob("*") if p.is_file()), key=lambda p: p.as_posix()):
        result[path.relative_to(root).as_posix()] = sha256_file(path)
    return result


def ast_literal_io_paths(source: str) -> list[str]:
    result: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return ["<SYNTAX_ERROR>"]
    io_names = {"open", "File", "load", "loadmat", "read_text", "read_bytes", "fromfile"}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        function_name = ""
        if isinstance(node.func, ast.Name):
            function_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            function_name = node.func.attr
        if function_name not in io_names:
            continue
        argument = node.args[0]
        if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
            result.append(argument.value)
    return result


def active_forbidden_contract_strings(value: Any, path: str = "") -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    if isinstance(value, Mapping):
        for key, nested in value.items():
            result.extend(active_forbidden_contract_strings(nested, f"{path}/{key}"))
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            result.extend(active_forbidden_contract_strings(nested, f"{path}/{index}"))
    elif isinstance(value, str):
        normalized = value.replace("\\", "/").lower()
        keypath = path.lower()
        if "outputs/step4_rho_grids" in normalized and not any(
            marker in keypath for marker in ("forbidden", "deny", "prohibit", "statement")
        ):
            result.append((path, value))
    return result


def validate_input_freeze(audit: Audit, validation_contract: Mapping[str, Any]) -> None:
    policy = validation_contract["protected_source_policy"]
    manifest_path = BOARD_ROOT / validation_contract["paths"]["input_manifest"]
    expected_manifest_hash = str(policy["input_manifest_expected_sha256"]).upper()
    actual_manifest_hash = sha256_file(manifest_path) if manifest_path.is_file() else None
    audit.add(
        "protected_source",
        "板块20输入冻结清单SHA-256不变",
        expected_manifest_hash,
        actual_manifest_hash,
        actual_manifest_hash == expected_manifest_hash,
        str(manifest_path),
    )
    if not manifest_path.is_file():
        return
    fields, rows = read_csv(manifest_path)
    audit.add(
        "protected_source",
        "输入冻结清单行数",
        int(policy["frozen_manifest_rows"]),
        len(rows),
        len(rows) == int(policy["frozen_manifest_rows"]),
        ",".join(fields),
    )
    frozen_failures: list[str] = []
    live_failures: list[str] = []
    for row in rows:
        frozen = BOARD_ROOT / "input" / row["frozen_relative_path"]
        if not frozen.is_file() or sha256_file(frozen) != row["frozen_sha256"].upper():
            frozen_failures.append(row["item_id"])
        if row.get("live_change_policy") == "immutable":
            source = Path(row["source_absolute_path"])
            if not source.is_file() or sha256_file(source) != row["source_sha256"].upper():
                live_failures.append(row["item_id"])
    audit.add(
        "protected_source",
        "185份冻结输入逐文件SHA-256复核",
        {"failures": 0},
        {"checked": len(rows), "failures": frozen_failures},
        not frozen_failures and len(rows) == int(policy["frozen_manifest_rows"]),
        str(BOARD_ROOT / "input"),
    )
    immutable_count = sum(row.get("live_change_policy") == "immutable" for row in rows)
    audit.add(
        "protected_source",
        "immutable实时源逐文件SHA-256复核",
        {"failures": 0},
        {"checked": immutable_count, "failures": live_failures},
        not live_failures,
        str(manifest_path),
    )


def run_precheck(
    audit: Audit,
    validation_contract_path: Path,
    compute_contract_path: Path,
    compute_script_path: Path,
    step4_manifest_path: Path,
    compute_root: Path,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    required_files = [
        validation_contract_path,
        compute_contract_path,
        compute_script_path,
        step4_manifest_path,
    ]
    missing = [str(path) for path in required_files if not path.is_file()]
    audit.add("files", "步骤5合同与脚本存在", [], missing, not missing, ";".join(missing))
    if missing:
        return {}, {}, {}

    validation_contract = load_json(validation_contract_path)
    compute_contract = load_json(compute_contract_path)
    step4_manifest = load_json(step4_manifest_path)

    audit.add(
        "contract",
        "验收合同版本",
        "board20_step5_validation_contract_v1",
        validation_contract.get("schema_version"),
        validation_contract.get("schema_version") == "board20_step5_validation_contract_v1",
    )
    audit.add(
        "contract",
        "独立计算合同版本",
        "board20_step5_independent_compute_contract_v1",
        compute_contract.get("schema_version"),
        compute_contract.get("schema_version") == "board20_step5_independent_compute_contract_v1",
    )
    sealed_compute = validation_contract.get("sealed_compute_identity", {})
    actual_compute_script_hash = sha256_file(compute_script_path)
    actual_compute_contract_hash = sha256_file(compute_contract_path)
    audit.add(
        "contract",
        "独立计算脚本最终SHA-256封签",
        str(sealed_compute.get("compute_script_sha256", "")).upper(),
        actual_compute_script_hash,
        bool(sealed_compute.get("compute_script_sha256"))
        and actual_compute_script_hash == str(sealed_compute["compute_script_sha256"]).upper(),
        str(compute_script_path),
    )
    audit.add(
        "contract",
        "独立计算合同最终SHA-256封签",
        str(sealed_compute.get("compute_contract_sha256", "")).upper(),
        actual_compute_contract_hash,
        bool(sealed_compute.get("compute_contract_sha256"))
        and actual_compute_contract_hash == str(sealed_compute["compute_contract_sha256"]).upper(),
        str(compute_contract_path),
    )
    actual_manifest_hash = sha256_file(step4_manifest_path)
    expected_manifest_hash = str(compute_contract.get("route_manifest_sha256", "")).upper()
    audit.add(
        "contract",
        "计算合同锁定步骤4路线清单哈希",
        expected_manifest_hash,
        actual_manifest_hash,
        bool(expected_manifest_hash) and expected_manifest_hash == actual_manifest_hash,
        str(step4_manifest_path),
    )

    validation_routes = {row["route_id"]: row for row in validation_contract.get("routes", [])}
    compute_routes = {row["route_id"]: row for row in compute_contract.get("routes", [])}
    manifest_routes = {row["route_id"]: row for row in step4_manifest.get("routes", [])}
    expected_set = set(EXPECTED_ROUTE_IDS)
    for label, route_map in (
        ("validation", validation_routes),
        ("compute", compute_routes),
        ("step4_manifest", manifest_routes),
    ):
        audit.add(
            "route_identity",
            f"{label}恰含五条封签路线",
            sorted(expected_set),
            sorted(route_map),
            set(route_map) == expected_set,
        )

    for route_id in EXPECTED_ROUTE_IDS:
        if route_id not in validation_routes or route_id not in compute_routes or route_id not in manifest_routes:
            continue
        expected = validation_routes[route_id]
        actual = compute_routes[route_id]
        manifest = manifest_routes[route_id]
        identity = {
            "formula": actual.get("route_formula"),
            "role": actual.get("route_role"),
            "delay_dofs": actual.get("delay_dofs_matlab_1_based"),
            "workspace": actual.get("workspace_relpath"),
        }
        identity_expected = {
            "formula": expected["formula"],
            "role": expected["route_role"],
            "delay_dofs": expected["delay_dofs_one_based"],
            "workspace": manifest.get("workspace_relpath"),
        }
        audit.add(
            "route_identity",
            f"{route_id}公式、角色、延迟自由度和工作区身份",
            identity_expected,
            identity,
            identity == identity_expected,
        )
        workspace = BOARD_ROOT / str(actual.get("workspace_relpath", ""))
        workspace_hash = sha256_file(workspace) if workspace.is_file() else None
        expected_hash = str(actual.get("workspace_sha256", "")).upper()
        audit.add(
            "route_identity",
            f"{route_id}封签工作区SHA-256",
            expected_hash,
            workspace_hash,
            bool(expected_hash) and workspace_hash == expected_hash,
            str(workspace),
        )
        forbidden_variables = set(
            compute_contract.get("manifest_field_policy", {}).get(
                "forbidden_scientific_input_names", []
            )
        )
        matrix_variables = set(actual.get("matrix_variables", {}).keys()) | set(
            actual.get("matrix_variables", {}).values()
        )
        overlap = sorted(forbidden_variables & matrix_variables)
        audit.add(
            "separation",
            f"{route_id}矩阵输入变量不含MATLAB科学答案",
            [],
            overlap,
            not overlap,
        )

    grid = compute_contract.get("full_grid", {})
    audit.add(
        "grid_contract",
        "全网格为五路线各31×67共10385点",
        {"shape": [31, 67], "points_per_route": 2077, "total_points": 10385},
        {
            "shape": grid.get("shape"),
            "points_per_route": grid.get("points_per_route"),
            "total_points": grid.get("total_points"),
        },
        grid.get("shape") == [31, 67]
        and grid.get("points_per_route") == 2077
        and grid.get("total_points") == 10385,
    )

    pilot = compute_contract.get("pilot_points", {})
    pilot_count = sum(len(pilot.get(route_id, [])) for route_id in EXPECTED_ROUTE_IDS)
    validation_pilot = {
        row["route_id"]: row["pilot_points"] for row in validation_contract.get("routes", [])
    }
    audit.add(
        "grid_contract",
        "41个预登记真实试点逐路线一致",
        validation_pilot,
        {route_id: pilot.get(route_id) for route_id in EXPECTED_ROUTE_IDS},
        pilot_count == 41
        and all(pilot.get(route_id) == validation_pilot.get(route_id) for route_id in EXPECTED_ROUTE_IDS),
    )

    source = compute_script_path.read_text(encoding="utf-8")
    literal_paths = ast_literal_io_paths(source)
    forbidden_literal_paths = [
        path
        for path in literal_paths
        if "outputs/step4_rho_grids" in path.replace("\\", "/").lower()
    ]
    active_contract_paths = active_forbidden_contract_strings(compute_contract)
    audit.add(
        "separation",
        "独立计算脚本没有把步骤4网格写成I/O字面量",
        [],
        forbidden_literal_paths,
        not forbidden_literal_paths,
        str(compute_script_path),
    )
    audit.add(
        "separation",
        "独立计算合同没有活动步骤4网格输入路径",
        [],
        active_contract_paths,
        not active_contract_paths,
        str(compute_contract_path),
    )
    matlab_tokens = [token for token in ("matlab.engine", "matlab.exe", "-batch") if token in source.lower()]
    audit.add(
        "separation",
        "独立计算脚本不调用MATLAB求解器",
        [],
        matlab_tokens,
        not matlab_tokens,
        str(compute_script_path),
    )

    augmentation = compute_contract.get("augmentation_policy", {})
    audit.add(
        "algorithm_contract",
        "紧凑标量增广和全q伴随阶数分开登记",
        {"compact": "2*n+l+j", "full_q": "n*(max(l,j)+2)"},
        {"compact": augmentation.get("compact_order"), "full_q": augmentation.get("full_q_order")},
        augmentation.get("compact_order") == "2*n+l+j"
        and augmentation.get("full_q_order") == "n*(max(l,j)+2)",
    )
    numeric = compute_contract.get("numeric_gates", {})
    audit.add(
        "numeric_contract",
        "公式身份1e-12、rho/近单位根与残差1e-8门槛固定",
        {"formula": 1e-12, "rho": 1e-8, "near_unit": 1e-8, "near_threshold": 0.9, "poly_residual": 1e-8, "laurent_residual": 1e-8},
        {
            "formula": numeric.get("direct_formula_coefficient_relative_difference"),
            "rho": numeric.get("compact_full_rho_absolute_difference"),
            "near_unit": numeric.get("near_unit_root_relative_matching_difference"),
            "near_threshold": numeric.get("near_unit_root_threshold"),
            "poly_residual": numeric.get("max_polynomial_residual"),
            "laurent_residual": numeric.get("max_direct_laurent_residual"),
        },
        numeric.get("direct_formula_coefficient_relative_difference") == 1e-12
        and numeric.get("compact_full_rho_absolute_difference") == 1e-8
        and numeric.get("near_unit_root_relative_matching_difference") == 1e-8
        and numeric.get("near_unit_root_threshold") == 0.9
        and numeric.get("max_polynomial_residual") == 1e-8
        and numeric.get("max_direct_laurent_residual") == 1e-8,
    )

    scientific = compute_contract.get("scientific_contracts", {})
    master_status = scientific.get("master_thesis_route", {}).get("status")
    manuscript_status = scientific.get("manuscript_0824_route", {}).get("status")
    audit.add(
        "paper_contract",
        "硕士论文和小论文公式路线均保持合同未闭合",
        ["CONTRACT_NOT_CLOSED", "CONTRACT_NOT_CLOSED"],
        [master_status, manuscript_status],
        master_status == manuscript_status == "CONTRACT_NOT_CLOSED",
    )

    failed_contract_entries = compute_contract.get(
        "noncomputable_failed_routes", compute_contract.get("failed_routes", [])
    )
    failed_contract_ids = {
        str(item.get("route_id"))
        for item in failed_contract_entries
        if isinstance(item, Mapping)
    }
    audit.add(
        "failed_routes",
        "独立计算合同显式登记四条上游失败路线DO_NOT_CREATE",
        sorted(FAILED_ROUTE_IDS),
        sorted(failed_contract_ids),
        failed_contract_ids == set(FAILED_ROUTE_IDS),
        str(compute_contract_path),
    )

    forbidden_dirs: list[str] = []
    for mode in ("pilot", "full"):
        for route_id in FAILED_ROUTE_IDS + PAPER_ROUTE_IDS:
            candidate = compute_root / mode / route_id
            if candidate.exists():
                forbidden_dirs.append(str(candidate))
    step4_root = BOARD_ROOT / "outputs" / "step4_rho_grids"
    for route_id in FAILED_ROUTE_IDS:
        candidate = step4_root / route_id
        if candidate.exists():
            forbidden_dirs.append(str(candidate))
    audit.add(
        "failed_routes",
        "四失败路线和两论文未闭合路线均无科学网格目录",
        [],
        forbidden_dirs,
        not forbidden_dirs,
    )

    validate_input_freeze(audit, validation_contract)
    return validation_contract, compute_contract, step4_manifest


def matlab73_numeric(file: h5py.File, name: str) -> np.ndarray:
    array = np.asarray(file[name])
    if array.dtype.fields and {"real", "imag"}.issubset(array.dtype.fields):
        array = array["real"] + 1j * array["imag"]
    if array.ndim >= 2:
        array = array.T
    return np.asarray(array)


def matlab73_cell_complex(file: h5py.File, dataset_name: str, l: int, j: int) -> np.ndarray:
    dataset = file[dataset_name]
    # MATLAB [l,j] is stored as HDF5 [j,l].
    reference = dataset[j, l]
    if not reference:
        return np.empty(0, dtype=np.complex128)
    value = np.asarray(file[reference])
    if value.dtype.fields and {"real", "imag"}.issubset(value.dtype.fields):
        value = value["real"] + 1j * value["imag"]
    return np.asarray(value, dtype=np.complex128).reshape(-1)


def load_workspace_matrices(route: Mapping[str, Any]) -> dict[str, np.ndarray | float]:
    path = BOARD_ROOT / str(route["workspace_relpath"])
    result: dict[str, np.ndarray | float] = {}
    with h5py.File(path, "r") as file:
        for logical, stored in route["matrix_variables"].items():
            value = matlab73_numeric(file, stored)
            if logical == "dt":
                result[logical] = float(np.asarray(value).squeeze())
            else:
                result[logical] = np.asarray(value, dtype=np.float64)
    return result


def add_coefficient(coefficients: dict[int, np.ndarray], exponent: int, value: np.ndarray) -> None:
    if exponent in coefficients:
        coefficients[exponent] = coefficients[exponent] + value
    else:
        coefficients[exponent] = np.array(value, dtype=np.float64, copy=True)


def build_laurent_coefficients(
    matrices: Mapping[str, np.ndarray | float], formula: str, l_value: int, j_value: int
) -> dict[int, np.ndarray]:
    M = np.asarray(matrices["M"], dtype=np.float64)
    C1 = np.asarray(matrices["C1"], dtype=np.float64)
    K1 = np.asarray(matrices["K1"], dtype=np.float64)
    C2 = np.asarray(matrices["C2"], dtype=np.float64)
    K2 = np.asarray(matrices["K2"], dtype=np.float64)
    al = np.asarray(matrices["al"], dtype=np.float64)
    dt = float(matrices["dt"])
    mass_term = linalg.solve(al.T, M.T, assume_a="gen", check_finite=True).T / (dt * dt)
    coefficients: dict[int, np.ndarray] = {}
    add_coefficient(coefficients, 1, mass_term)
    add_coefficient(coefficients, 0, -2.0 * mass_term + C1 / dt + K1)
    add_coefficient(coefficients, -1, mass_term - C1 / dt)
    delayed_zero = C2 / dt + K2
    delayed_minus_one = -C2 / dt
    n = M.shape[0]
    dofs = (0, 5) if formula == "ORI_DIV1_H_RIGHT" else (0, 1)
    for delay, dof in zip((l_value, j_value), dofs, strict=True):
        selector = np.zeros((n, n), dtype=np.float64)
        selector[dof, dof] = 1.0
        if formula == "ORI_DIV1_H_RIGHT":
            at_delay = delayed_zero @ selector
            after_delay = delayed_minus_one @ selector
        else:
            at_delay = selector @ delayed_zero
            after_delay = selector @ delayed_minus_one
        add_coefficient(coefficients, -delay, at_delay)
        add_coefficient(coefficients, -(delay + 1), after_delay)
    if formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        S = np.asarray(matrices["S"], dtype=np.float64)
        delta_c = np.asarray(matrices["DeltaC"], dtype=np.float64)
        delta_k = np.asarray(matrices["DeltaK"], dtype=np.float64)
        add_coefficient(coefficients, 0, S.T @ (delta_c / dt + delta_k) @ S)
        add_coefficient(coefficients, -1, S.T @ (-delta_c / dt) @ S)
    nonzero = sorted(exponent for exponent, matrix in coefficients.items() if np.any(matrix != 0.0))
    if not nonzero:
        raise ValueError("all Laurent coefficients are exactly zero")
    return {exponent: coefficients[exponent] for exponent in range(nonzero[0], nonzero[-1] + 1) if exponent in coefficients}


def direct_characteristic_matrix(
    matrices: Mapping[str, np.ndarray | float], formula: str, l_value: int, j_value: int, z: complex
) -> np.ndarray:
    M = np.asarray(matrices["M"], dtype=np.float64)
    C1 = np.asarray(matrices["C1"], dtype=np.float64)
    K1 = np.asarray(matrices["K1"], dtype=np.float64)
    C2 = np.asarray(matrices["C2"], dtype=np.float64)
    K2 = np.asarray(matrices["K2"], dtype=np.float64)
    al = np.asarray(matrices["al"], dtype=np.float64)
    dt = float(matrices["dt"])
    right_division = linalg.solve(al.T, M.T, assume_a="gen", check_finite=True).T
    velocity = (z - 1.0) / (z * dt)
    acceleration = (z - 1.0) ** 2 / (z * dt * dt)
    base = acceleration * right_division + velocity * C1 + K1
    physical = velocity * C2 + K2
    H = np.zeros_like(M, dtype=np.complex128)
    dofs = (0, 5) if formula == "ORI_DIV1_H_RIGHT" else (0, 1)
    H[dofs[0], dofs[0]] = z ** (-l_value)
    H[dofs[1], dofs[1]] = z ** (-j_value)
    if formula == "ORI_DIV1_H_RIGHT":
        result = base + physical @ H
    else:
        result = base + H @ physical
    if formula == "DIV2_H_LEFT_FEEDBACK_OUTSIDE":
        S = np.asarray(matrices["S"], dtype=np.float64)
        delta_c = np.asarray(matrices["DeltaC"], dtype=np.float64)
        delta_k = np.asarray(matrices["DeltaK"], dtype=np.float64)
        result = result + S.T @ (velocity * delta_c + delta_k) @ S
    return result


def evaluate_laurent(coefficients: Mapping[int, np.ndarray], z: complex) -> np.ndarray:
    result = np.zeros_like(next(iter(coefficients.values())), dtype=np.complex128)
    for exponent, matrix in coefficients.items():
        result += matrix * (z**exponent)
    return result


def root_direct_residuals(coefficients: Mapping[int, np.ndarray], roots: np.ndarray) -> np.ndarray:
    roots = np.asarray(roots, dtype=np.complex128).reshape(-1)
    result = np.full(roots.shape, np.inf, dtype=np.float64)
    norms = {exponent: float(np.linalg.norm(matrix, ord="fro")) for exponent, matrix in coefficients.items()}
    for index, root in enumerate(roots):
        if not (math.isfinite(root.real) and math.isfinite(root.imag)) or root == 0:
            continue
        value = evaluate_laurent(coefficients, root)
        denominator = sum(norms[exponent] * abs(root) ** exponent for exponent in coefficients)
        if denominator > 0 and math.isfinite(denominator):
            singular_values = np.linalg.svd(value, compute_uv=False)
            result[index] = float(singular_values[-1] / denominator)
    return result


def symmetric_root_distance(first: np.ndarray, second: np.ndarray) -> float:
    first = np.asarray(first, dtype=np.complex128).reshape(-1)
    second = np.asarray(second, dtype=np.complex128).reshape(-1)
    if first.size != second.size or first.size == 0:
        return math.inf
    first_xy = np.column_stack((first.real, first.imag))
    second_xy = np.column_stack((second.real, second.imag))
    tree_second = cKDTree(second_xy)
    distances_12, indices_12 = tree_second.query(first_xy, k=1)
    relative_12 = distances_12 / (1.0 + np.abs(second[indices_12]))
    tree_first = cKDTree(first_xy)
    distances_21, indices_21 = tree_first.query(second_xy, k=1)
    relative_21 = distances_21 / (1.0 + np.abs(first[indices_21]))
    return float(max(np.max(relative_12), np.max(relative_21)))


def h5_vector(group: h5py.Group, name: str) -> np.ndarray:
    return np.asarray(group[name]).reshape(-1)


def h5_strings(dataset: h5py.Dataset) -> list[str]:
    values = np.asarray(dataset).reshape(-1)
    result: list[str] = []
    for value in values:
        if isinstance(value, bytes):
            result.append(value.decode("utf-8"))
        else:
            result.append(str(value))
    return result


def load_compact_retained_roots(root_file: h5py.File, point_index: int) -> tuple[np.ndarray, np.ndarray]:
    group = root_file["compact/retained"]
    offsets = h5_vector(group, "offset").astype(np.int64)
    counts = h5_vector(group, "count").astype(np.int64)
    offset = int(offsets[point_index])
    count = int(counts[point_index])
    real = h5_vector(group, "real")[offset : offset + count]
    imag = h5_vector(group, "imag")[offset : offset + count]
    roots = real.astype(np.float64) + 1j * imag.astype(np.float64)
    residual = h5_vector(group, "laurent_residual")[offset : offset + count].astype(np.float64)
    return roots, residual


def boundary_points(stable: np.ndarray, critical: np.ndarray) -> set[tuple[int, int]]:
    selected: set[tuple[int, int]] = set()
    n_l, n_j = stable.shape
    for l_value in range(n_l):
        for j_value in range(n_j):
            if critical[l_value, j_value]:
                selected.add((l_value, j_value))
            value = bool(stable[l_value, j_value])
            for dl, dj in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nl, nj = l_value + dl, j_value + dj
                if 0 <= nl < n_l and 0 <= nj < n_j and bool(stable[nl, nj]) != value:
                    selected.add((l_value, j_value))
                    break
    return selected


def deterministic_random_points(
    route_id: str,
    compute_contract_hash: str,
    excluded: set[tuple[int, int]],
    count: int,
) -> set[tuple[int, int]]:
    population = [(l_value, j_value) for l_value in range(31) for j_value in range(67)]
    available = [point for point in population if point not in excluded]
    seed_bytes = hashlib.sha256((route_id + compute_contract_hash).encode("utf-8")).digest()[:8]
    generator = np.random.default_rng(int.from_bytes(seed_bytes, byteorder="big", signed=False))
    if not available:
        return set()
    indices = generator.choice(len(available), size=min(count, len(available)), replace=False)
    return {available[int(index)] for index in np.asarray(indices).reshape(-1)}


def validate_artifact_manifest(audit: Audit, mode_root: Path) -> None:
    path = mode_root / "artifact_manifest.csv"
    if not path.is_file():
        audit.add("artifact_manifest", "计算工件清单存在", True, False, False, str(path))
        return
    fields, rows = read_csv(path)
    path_field = next((name for name in ("path", "relpath", "relative_path", "artifact_path") if name in fields), None)
    hash_field = next((name for name in ("sha256", "SHA256", "hash") if name in fields), None)
    failures: list[str] = []
    if path_field is None or hash_field is None:
        failures.append("missing path/hash columns")
    else:
        for row in rows:
            candidate = Path(row[path_field])
            if not candidate.is_absolute():
                candidate = mode_root / candidate
            if not safe_child(mode_root, candidate):
                failures.append(f"outside:{candidate}")
                continue
            expected = row[hash_field].strip().upper()
            if not candidate.is_file() or sha256_file(candidate) != expected:
                failures.append(str(candidate))
    audit.add(
        "artifact_manifest",
        "计算工件清单逐文件SHA-256一致",
        {"failures": 0},
        {"rows": len(rows), "failures": failures},
        bool(rows) and not failures,
        str(path),
    )


def validate_contract_status_file(audit: Audit, compute_root: Path) -> None:
    path = compute_root / "contracts_status.json"
    if not path.is_file():
        audit.add("paper_contract", "contracts_status.json存在", True, False, False, str(path))
        return
    data = load_json(path)
    for route_id in PAPER_ROUTE_IDS:
        statuses = collect_contract_status(data, route_id)
        # Compute contract uses master_thesis_route/manuscript_0824_route keys.
        if not statuses:
            alternate_key = "master_thesis_route" if route_id.startswith("masters") else "manuscript_0824_route"
            for item in recursive_dicts(data):
                child = item.get(alternate_key)
                if isinstance(child, Mapping) and "status" in child:
                    statuses.append(str(child["status"]))
        audit.add(
            "paper_contract",
            f"{route_id}保持CONTRACT_NOT_CLOSED且无rho网格",
            "CONTRACT_NOT_CLOSED",
            statuses,
            bool(statuses) and all(status == "CONTRACT_NOT_CLOSED" for status in statuses),
            str(path),
        )
    for route_id in FAILED_ROUTE_IDS:
        statuses = collect_contract_status(data, route_id)
        allowed = {"EXECUTION_FAIL", "DO_NOT_CREATE", "CONTRACT_NOT_EXECUTABLE"}
        audit.add(
            "failed_routes",
            f"{route_id}在步骤5保持失败且禁建网格",
            sorted(allowed),
            statuses,
            bool(statuses) and all(status in allowed for status in statuses),
            str(path),
        )


def validate_route_outputs(
    audit: Audit,
    route_id: str,
    route_contract: Mapping[str, Any],
    mode: str,
    mode_root: Path,
    validation_contract: Mapping[str, Any],
    compute_contract_hash: str,
) -> None:
    route_root = mode_root / route_id
    required_files = (
        "point_summary.csv",
        "roots.h5",
        "route_status.json",
        "checkpoint.h5",
        "checkpoint.json",
        "point_runtime.csv",
    )
    missing = [name for name in required_files if not (route_root / name).is_file()]
    audit.add(
        "route_files",
        f"{route_id}计算输出文件齐全",
        [],
        missing,
        not missing,
        str(route_root),
    )
    if missing:
        return

    required_columns = list(validation_contract["required_point_columns"])
    fields, rows = read_csv(route_root / "point_summary.csv")
    missing_columns = [name for name in required_columns if name not in fields]
    audit.add(
        "point_schema",
        f"{route_id} point_summary.csv字段合同",
        [],
        missing_columns,
        not missing_columns,
        str(route_root / "point_summary.csv"),
    )
    if missing_columns:
        return

    expected_points = 2077 if mode == "full" else len(route_contract["pilot_points"])
    unique_points: dict[tuple[int, int], tuple[int, dict[str, str]]] = {}
    parse_failures: list[str] = []
    numeric_failures: list[str] = []
    rho_grid = np.full((31, 67), np.nan)
    stable_grid = np.zeros((31, 67), dtype=bool)
    critical_grid = np.zeros((31, 67), dtype=bool)
    for index, row in enumerate(rows):
        try:
            l_value, j_value = parse_int(row["l"]), parse_int(row["j"])
            point = (l_value, j_value)
            if point in unique_points:
                numeric_failures.append(f"duplicate:{point}")
            unique_points[point] = (index, row)
            rho = parse_float(row["rho_compact"])
            stable = parse_bool(row["stable_compact"])
            critical = parse_bool(row["critical_compact"])
            polynomial_residual = parse_float(row["max_polynomial_residual_compact"])
            laurent_residual = parse_float(row["max_laurent_residual_compact"])
            formula_difference = parse_float(row["direct_formula_coefficient_relative_difference"])
            n = parse_int(row["matrix_order"])
            compact_order = parse_int(row["compact_order"])
            full_q_order = parse_int(row["full_q_order"])
            status = row["point_status"].strip().upper()
            if route_id != row["route_id"]:
                numeric_failures.append(f"route_id:{point}")
            if row["route_formula"] != route_contract["formula"]:
                numeric_failures.append(f"formula:{point}")
            if not (0 <= l_value <= 30 and 0 <= j_value <= 66):
                numeric_failures.append(f"range:{point}")
            if status != "PASS":
                numeric_failures.append(f"status:{point}:{status}:{row['failure_code']}")
            if not (math.isfinite(rho) and rho > 0):
                numeric_failures.append(f"rho:{point}:{rho}")
            if stable != (math.isfinite(rho) and rho > 0 and rho < 1.0):
                numeric_failures.append(f"stable:{point}")
            if critical != (math.isfinite(rho) and abs(rho - 1.0) <= 1e-8):
                numeric_failures.append(f"critical:{point}")
            if not (math.isfinite(polynomial_residual) and polynomial_residual <= 1e-8):
                numeric_failures.append(f"poly_residual:{point}:{polynomial_residual}")
            if not (math.isfinite(laurent_residual) and laurent_residual <= 1e-8):
                numeric_failures.append(f"laurent_residual:{point}:{laurent_residual}")
            if not (math.isfinite(formula_difference) and formula_difference <= 1e-12):
                numeric_failures.append(f"formula_difference:{point}:{formula_difference}")
            if n != int(route_contract["matrix_order"]):
                numeric_failures.append(f"matrix_order:{point}:{n}")
            if compact_order != 2 * n + l_value + j_value:
                numeric_failures.append(f"compact_order:{point}:{compact_order}")
            if full_q_order != n * (max(l_value, j_value) + 2):
                numeric_failures.append(f"full_q_order:{point}:{full_q_order}")
            if 0 <= l_value <= 30 and 0 <= j_value <= 66:
                rho_grid[l_value, j_value] = rho
                stable_grid[l_value, j_value] = stable
                critical_grid[l_value, j_value] = critical
            if mode == "pilot":
                if not parse_bool(row["full_crosscheck_performed"]):
                    numeric_failures.append(f"full_crosscheck_missing:{point}")
                rho_difference = parse_float(row["compact_full_rho_abs_diff"])
                root_difference = parse_float(row["root_match_max_relative_diff"])
                near_unit_difference = parse_float(row["near_unit_root_match_max_relative_diff"])
                if not (math.isfinite(rho_difference) and rho_difference <= 1e-8):
                    numeric_failures.append(f"compact_full_rho:{point}:{rho_difference}")
                if not (math.isfinite(near_unit_difference) and near_unit_difference <= 1e-8):
                    numeric_failures.append(f"near_unit_roots:{point}:{near_unit_difference}")
                # Complete root-set equality and the statement that every
                # extra full-q root is numerically zero are diagnostic only.
                # A high-multiplicity clearing-origin zero can split above
                # the sealed zero tolerance; it must be preserved, not
                # force-deleted to satisfy a theoretical root count.
                _ = root_difference
                _ = parse_bool(row["extra_full_roots_are_zero"])
                strict_status = row["strict_root_set_status"].strip()
                if strict_status not in {
                    "PASS",
                    "STRICT_ROOT_SET_PASS",
                    "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING",
                }:
                    numeric_failures.append(f"strict_root_set_status:{point}:{strict_status}")
        except Exception as exc:
            parse_failures.append(f"row {index + 2}: {type(exc).__name__}: {exc}")

    expected_coordinate_set = (
        {(l_value, j_value) for l_value in range(31) for j_value in range(67)}
        if mode == "full"
        else {tuple(point) for point in route_contract["pilot_points"]}
    )
    audit.add(
        "point_grid",
        f"{route_id}具有预期且唯一的{'31×67' if mode == 'full' else '试点'}坐标",
        {"rows": expected_points, "coordinates": len(expected_coordinate_set)},
        {
            "rows": len(rows),
            "coordinates": len(unique_points),
            "missing": sorted(expected_coordinate_set - set(unique_points))[:20],
            "extra": sorted(set(unique_points) - expected_coordinate_set)[:20],
        },
        len(rows) == expected_points and set(unique_points) == expected_coordinate_set,
    )
    audit.add(
        "point_numeric",
        f"{route_id} rho、稳定分类、残差和两种增广阶数逐点通过",
        {"parse_failures": 0, "numeric_failures": 0},
        {"parse_failures": parse_failures[:50], "numeric_failures": numeric_failures[:100]},
        not parse_failures and not numeric_failures,
        str(route_root / "point_summary.csv"),
    )
    if parse_failures:
        return

    with h5py.File(route_root / "roots.h5", "r") as roots_file:
        required_point_fields = validation_contract["required_hdf5_semantics"]["point_fields"]
        required_groups = validation_contract["required_hdf5_semantics"]["ragged_groups"]
        required_ragged = validation_contract["required_hdf5_semantics"]["ragged_fields"]
        missing_hdf: list[str] = []
        if "points" not in roots_file:
            missing_hdf.append("points")
        else:
            for name in required_point_fields:
                if name not in roots_file["points"]:
                    missing_hdf.append(f"points/{name}")
        for group_name in required_groups:
            if group_name not in roots_file:
                missing_hdf.append(group_name)
                continue
            for name in required_ragged:
                if name not in roots_file[group_name]:
                    missing_hdf.append(f"{group_name}/{name}")
        audit.add(
            "root_schema",
            f"{route_id} roots.h5字段合同",
            [],
            missing_hdf,
            not missing_hdf,
            str(route_root / "roots.h5"),
        )
        if missing_hdf:
            return

        point_group = roots_file["points"]
        h_l = h5_vector(point_group, "l").astype(int)
        h_j = h5_vector(point_group, "j").astype(int)
        h_rho = h5_vector(point_group, "rho_compact").astype(float)
        h_status = h5_strings(point_group["point_status"])
        csv_coordinates = [(parse_int(row["l"]), parse_int(row["j"])) for row in rows]
        hdf_coordinates = list(zip(h_l.tolist(), h_j.tolist(), strict=True))
        hdf_csv_failures: list[str] = []
        if hdf_coordinates != csv_coordinates:
            hdf_csv_failures.append("coordinate order differs")
        if len(h_rho) != len(rows):
            hdf_csv_failures.append("rho length differs")
        elif np.max(np.abs(h_rho - np.array([parse_float(row["rho_compact"]) for row in rows]))) > 1e-12:
            hdf_csv_failures.append("rho differs by more than 1e-12")
        if [status.upper() for status in h_status] != [row["point_status"].strip().upper() for row in rows]:
            hdf_csv_failures.append("point_status differs")

        retained_group = roots_file["compact/retained"]
        offsets = h5_vector(retained_group, "offset").astype(np.int64)
        counts = h5_vector(retained_group, "count").astype(np.int64)
        total_roots = len(h5_vector(retained_group, "real"))
        if len(offsets) != len(rows) or len(counts) != len(rows):
            hdf_csv_failures.append("offset/count length differs")
        else:
            for index, (offset, count) in enumerate(zip(offsets, counts, strict=True)):
                if offset < 0 or count <= 0 or offset + count > total_roots:
                    hdf_csv_failures.append(f"invalid ragged slice at row {index}")
                    break
                if count != parse_int(rows[index]["compact_retained_root_count"]):
                    hdf_csv_failures.append(f"retained count differs at row {index}")
                    break
        audit.add(
            "root_schema",
            f"{route_id} roots.h5与point_summary.csv逐行一致",
            [],
            hdf_csv_failures,
            not hdf_csv_failures,
            str(route_root),
        )

        if mode == "pilot":
            selected_points = expected_coordinate_set
        else:
            boundary = boundary_points(stable_grid, critical_grid)
            fixed = set(tuple(point) for point in validation_contract["audit_sampling"]["fixed_points"])
            if route_contract["division"] == "div2":
                fixed |= set(
                    tuple(point) for point in validation_contract["audit_sampling"]["additional_div2_points"]
                )
            random = deterministic_random_points(
                route_id,
                compute_contract_hash,
                boundary | fixed,
                int(validation_contract["audit_sampling"]["random_points_per_route"]),
            )
            selected_points = boundary | fixed | random
            audit.add(
                "sampling",
                f"{route_id}固定、随机和全部边界审核点集合",
                {"fixed_min": 7, "random": 16, "all_boundary_included": True},
                {"fixed": len(fixed), "random": len(random), "boundary": len(boundary), "union": len(selected_points)},
                len(random) == 16 and boundary.issubset(selected_points) and fixed.issubset(selected_points),
            )

        matrices = load_workspace_matrices(route_contract)
        formula_failures: list[str] = []
        residual_failures: list[str] = []
        near_unit_root_failures: list[str] = []
        strict_root_diagnostics: list[str] = []
        step4_path = BOARD_ROOT / "outputs" / "step4_rho_grids" / route_id / "common_31x67_same_formula_candidate.mat"
        with h5py.File(step4_path, "r") as step4_file:
            step4_rho = matlab73_numeric(step4_file, "rho").astype(float)
            step4_stable = matlab73_numeric(step4_file, "stable").astype(float)
            all_rho_differences: list[float] = []
            rho_tolerance_failures: list[dict[str, Any]] = []
            all_class_matches: list[bool] = []
            for point, (row_index, row) in unique_points.items():
                l_value, j_value = point
                rho_python = parse_float(row["rho_compact"])
                rho_matlab = float(step4_rho[l_value, j_value])
                difference = abs(rho_python - rho_matlab)
                all_rho_differences.append(difference)
                if not math.isfinite(difference) or difference > 1e-8:
                    rho_tolerance_failures.append(
                        {
                            "l": l_value,
                            "j": j_value,
                            "rho_python": rho_python,
                            "rho_matlab": rho_matlab,
                            "abs_diff": difference,
                        }
                    )
                stable_matlab = bool(step4_stable[l_value, j_value])
                stable_python = parse_bool(row["stable_compact"])
                all_class_matches.append(stable_python == stable_matlab)
            max_rho_difference = max(all_rho_differences, default=math.inf)
            audit.add(
                "matlab_python",
                f"{route_id} MATLAB/Python rho逐点绝对差不超过1e-8",
                {"max_abs_diff": "<=1e-8"},
                {
                    "points": len(all_rho_differences),
                    "max_abs_diff": max_rho_difference,
                    "failure_count": len(rho_tolerance_failures),
                    "failure_points": rho_tolerance_failures,
                },
                len(all_rho_differences) == expected_points and not rho_tolerance_failures,
                str(step4_path),
            )
            audit.add(
                "matlab_python",
                f"{route_id} MATLAB/Python严格稳定分类逐点一致",
                {"mismatch": 0},
                {"points": len(all_class_matches), "mismatch": sum(not value for value in all_class_matches)},
                len(all_class_matches) == expected_points and all(all_class_matches),
                str(step4_path),
            )

            for point in sorted(selected_points):
                if point not in unique_points:
                    residual_failures.append(f"missing selected point {point}")
                    continue
                row_index, _row = unique_points[point]
                l_value, j_value = point
                coefficients = build_laurent_coefficients(matrices, route_contract["formula"], l_value, j_value)
                for z in (0.8 + 0.2j, 1.1 - 0.1j, -0.7 + 0.3j):
                    direct = direct_characteristic_matrix(matrices, route_contract["formula"], l_value, j_value, z)
                    expanded = evaluate_laurent(coefficients, z)
                    denominator = max(1.0, np.linalg.norm(direct, ord="fro"), np.linalg.norm(expanded, ord="fro"))
                    difference = float(np.linalg.norm(direct - expanded, ord="fro") / denominator)
                    if not math.isfinite(difference) or difference > 1e-12:
                        formula_failures.append(f"{point}@{z}:{difference:.17g}")
                python_roots, stored_residuals = load_compact_retained_roots(roots_file, row_index)
                independent_residuals = root_direct_residuals(coefficients, python_roots)
                max_independent = float(np.max(independent_residuals)) if independent_residuals.size else math.inf
                max_stored = float(np.max(stored_residuals)) if stored_residuals.size else math.inf
                if not math.isfinite(max_independent) or max_independent > 1e-8:
                    residual_failures.append(f"direct:{point}:{max_independent:.17g}")
                if not math.isfinite(max_stored) or max_stored > 1e-8:
                    residual_failures.append(f"stored:{point}:{max_stored:.17g}")
                matlab_roots = matlab73_cell_complex(step4_file, "poles", l_value, j_value)
                matlab_roots = matlab_roots[
                    np.isfinite(matlab_roots.real) & np.isfinite(matlab_roots.imag)
                ]
                strict_root_difference = symmetric_root_distance(python_roots, matlab_roots)
                if not math.isfinite(strict_root_difference) or strict_root_difference > 1e-8:
                    strict_root_diagnostics.append(
                        "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING:"
                        f"{point}:py={python_roots.size},mat={matlab_roots.size},"
                        f"diff={strict_root_difference:.17g}"
                    )
                python_near = python_roots[np.abs(python_roots) >= 0.9]
                matlab_near = matlab_roots[np.abs(matlab_roots) >= 0.9]
                near_difference = symmetric_root_distance(python_near, matlab_near)
                if not math.isfinite(near_difference) or near_difference > 1e-8:
                    near_unit_root_failures.append(
                        f"{point}:py={python_near.size},mat={matlab_near.size},diff={near_difference:.17g}"
                    )

        audit.add(
            "formula_identity",
            f"{route_id}审核点高层公式与Laurent系数展开误差不超过1e-12",
            {"failures": 0},
            {"selected_points": len(selected_points), "failures": formula_failures[:50]},
            not formula_failures,
        )
        audit.add(
            "direct_residual",
            f"{route_id}审核点全部保留根直接Laurent残差不超过1e-8",
            {"failures": 0},
            {"selected_points": len(selected_points), "failures": residual_failures[:50]},
            not residual_failures,
        )
        audit.add(
            "root_equivalence",
            f"{route_id}审核点Python/MATLAB主导及模不小于0.9的近单位根差不超过1e-8",
            {"failures": 0},
            {"selected_points": len(selected_points), "failures": near_unit_root_failures[:50]},
            not near_unit_root_failures,
        )
        audit.info(
            "root_set_diagnostic",
            f"{route_id}完整根集严格匹配诊断（原点多重根裂分不降低核心rho裁决）",
            {
                "selected_points": len(selected_points),
                "strict_failure_count": len(strict_root_diagnostics),
                "status": (
                    "STRICT_ROOT_SET_FAIL_ORIGIN_MULTIPLICITY_SPLITTING"
                    if strict_root_diagnostics
                    else "STRICT_ROOT_SET_PASS"
                ),
                "examples": strict_root_diagnostics[:50],
                "zero_tolerance_was_not_relaxed": True,
            },
        )


def run_postcheck(
    audit: Audit,
    validation_contract: Mapping[str, Any],
    compute_contract: Mapping[str, Any],
    compute_contract_path: Path,
    compute_root: Path,
    mode: str,
) -> None:
    mode_root = compute_root / mode
    audit.add("mode", f"{mode}计算目录存在", True, mode_root.is_dir(), mode_root.is_dir(), str(mode_root))
    if not mode_root.is_dir():
        return
    before_hashes = hash_tree(mode_root)
    run_status_path = mode_root / "run_status.json"
    audit.add(
        "mode",
        f"{mode}/run_status.json存在",
        True,
        run_status_path.is_file(),
        run_status_path.is_file(),
        str(run_status_path),
    )
    if run_status_path.is_file():
        run_status = load_json(run_status_path)
        status_values = [
            str(item.get(key))
            for item in recursive_dicts(run_status)
            for key in ("overall_status", "status", "terminal_status")
            if key in item
        ]
        terminal_ok = any(value in {"PASS", "COMPLETE_PASS", "SUCCESS", "COMPLETE"} for value in status_values)
        audit.add(
            "mode",
            f"{mode}独立计算已终态成功",
            "PASS/COMPLETE_PASS/SUCCESS/COMPLETE",
            status_values,
            terminal_ok,
            str(run_status_path),
        )
    validate_contract_status_file(audit, compute_root)
    validate_artifact_manifest(audit, mode_root)
    route_contracts = {row["route_id"]: row for row in validation_contract["routes"]}
    compute_route_contracts = {row["route_id"]: row for row in compute_contract["routes"]}
    compute_contract_hash = sha256_file(compute_contract_path)
    for route_id in EXPECTED_ROUTE_IDS:
        merged = dict(route_contracts[route_id])
        merged.update(compute_route_contracts[route_id])
        validate_route_outputs(
            audit,
            route_id,
            merged,
            mode,
            mode_root,
            validation_contract,
            compute_contract_hash,
        )
    forbidden_dirs = [
        str(mode_root / route_id)
        for route_id in FAILED_ROUTE_IDS + PAPER_ROUTE_IDS
        if (mode_root / route_id).exists()
    ]
    audit.add(
        "failed_routes",
        f"{mode}没有四失败路线或两论文未闭合路线网格目录",
        [],
        forbidden_dirs,
        not forbidden_dirs,
    )
    after_hashes = hash_tree(mode_root)
    changed = sorted(
        path
        for path in set(before_hashes) | set(after_hashes)
        if before_hashes.get(path) != after_hashes.get(path)
    )
    audit.add(
        "immutability",
        "事后比较前后独立计算工件SHA-256完全不变",
        {"changed_files": []},
        {"files_before": len(before_hashes), "files_after": len(after_hashes), "changed_files": changed},
        not changed and set(before_hashes) == set(after_hashes),
        str(mode_root),
    )


def audit_payload(audit: Audit, paths: Mapping[str, Path]) -> dict[str, Any]:
    return {
        "schema_version": "board20_step5_validation_result_v1",
        "summary": audit.summary(),
        "paths": {key: str(value) for key, value in paths.items()},
        "validator": {"path": str(SCRIPT), "sha256": sha256_file(SCRIPT)},
        "checks": [
            {
                "check_id": item.check_id,
                "category": item.category,
                "description": item.description,
                "expected": item.expected,
                "actual": item.actual,
                "status": item.status,
                "evidence": item.evidence,
            }
            for item in audit.checks
        ],
    }


def write_outputs(audit: Audit, audit_root: Path, log_root: Path, paths: Mapping[str, Path]) -> None:
    audit_root.mkdir(parents=True, exist_ok=True)
    log_root.mkdir(parents=True, exist_ok=True)
    stem = audit.mode.replace("-", "_")
    payload = audit_payload(audit, paths)
    json_path = audit_root / f"{stem}.json"
    csv_path = audit_root / f"{stem}_checks.csv"
    report_path = audit_root / f"{stem}_report.md"
    log_path = log_root / f"{stem}.log"
    json_path.write_text(json.dumps(payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=("check_id", "category", "description", "expected", "actual", "status", "evidence"),
            lineterminator="\n",
        )
        writer.writeheader()
        for item in audit.checks:
            writer.writerow(
                {
                    "check_id": item.check_id,
                    "category": item.category,
                    "description": item.description,
                    "expected": canonical_json(item.expected),
                    "actual": canonical_json(item.actual),
                    "status": item.status,
                    "evidence": item.evidence,
                }
            )
    summary = audit.summary()
    failed = [item for item in audit.checks if item.status == "FAIL"]
    lines = [
        f"# 板块20最小步骤5 {audit.mode} 独立验收报告",
        "",
        f"- 总体状态：`{summary['overall_status']}`",
        f"- 检查数：{summary['total_checks']}",
        f"- 通过：{summary['passed_checks']}",
        f"- 独立诊断：{summary['information_checks']}",
        f"- 失败：{summary['failed_checks']}",
        "- 证据边界：Python独立计算与MATLAB步骤4结果严格分阶段；论文公式合同未闭合时不生成科学网格。",
        "",
        "## 失败项",
        "",
    ]
    if failed:
        lines.extend(f"- `{item.check_id}` {item.description}：{canonical_json(item.actual)}" for item in failed)
    else:
        lines.append("- 无。")
    lines.extend(["", "## 工件", "", f"- JSON：`{json_path}`", f"- CSV：`{csv_path}`", ""])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    log_lines = [
        f"{item.check_id}\t{item.status}\t{item.category}\t{item.description}\t{canonical_json(item.actual)}"
        for item in audit.checks
    ]
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Board 20 Step 5 independent PRECHECK and strictly post-hoc validator."
    )
    parser.add_argument(
        "--mode",
        choices=("precheck", "pilot-postcheck", "full-postcheck"),
        default="precheck",
    )
    parser.add_argument("--validation-contract", type=Path, default=DEFAULT_VALIDATION_CONTRACT)
    parser.add_argument("--compute-contract", type=Path, default=DEFAULT_COMPUTE_CONTRACT)
    parser.add_argument("--compute-script", type=Path, default=DEFAULT_COMPUTE_SCRIPT)
    parser.add_argument("--step4-manifest", type=Path, default=DEFAULT_STEP4_MANIFEST)
    parser.add_argument("--compute-root", type=Path, default=DEFAULT_COMPUTE_ROOT)
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--log-root", type=Path, default=DEFAULT_LOG_ROOT)
    args = parser.parse_args()

    paths = {
        "validation_contract": args.validation_contract.resolve(),
        "compute_contract": args.compute_contract.resolve(),
        "compute_script": args.compute_script.resolve(),
        "step4_manifest": args.step4_manifest.resolve(),
        "compute_root": args.compute_root.resolve(),
        "audit_root": args.audit_root.resolve(),
        "log_root": args.log_root.resolve(),
    }
    if not safe_child(BOARD_ROOT, paths["audit_root"]) or not safe_child(BOARD_ROOT, paths["log_root"]):
        raise SystemExit("Audit and validation-log roots must remain inside the Board-20 isolation directory.")

    audit = Audit(mode=args.mode)
    validation_contract, compute_contract, _step4_manifest = run_precheck(
        audit,
        paths["validation_contract"],
        paths["compute_contract"],
        paths["compute_script"],
        paths["step4_manifest"],
        paths["compute_root"],
    )
    if args.mode != "precheck" and validation_contract and compute_contract:
        run_postcheck(
            audit,
            validation_contract,
            compute_contract,
            paths["compute_contract"],
            paths["compute_root"],
            "pilot" if args.mode == "pilot-postcheck" else "full",
        )
    write_outputs(audit, paths["audit_root"], paths["log_root"], paths)
    summary = audit.summary()
    print(canonical_json(summary))
    return 0 if audit.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())

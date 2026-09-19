from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import h5py
import numpy as np
from scipy.io import loadmat

from board20_step6_fs_protocol import (
    ExclusiveFileLock,
    atomic_commit_manifest,
    prepare_output_root,
    validate_fixed_roots,
)


SCRIPT_PATH = Path(__file__).resolve()
CODE_ROOT = SCRIPT_PATH.parent
BOARD_ROOT = CODE_ROOT.parent
CONTRACT_PATH = CODE_ROOT / "board20_step6_history_comparison_contract.json"
FS_PROTOCOL_PATH = CODE_ROOT / "board20_step6_fs_protocol.py"
RESET_SCRIPT_PATH = CODE_ROOT / "reset_board20_step6_clean_probe.py"
RUN_OUTPUT_DIRECTORIES = {"figures", "tables"}

# Keep Matplotlib and TeX output deterministic across the two required runs.
os.environ["SOURCE_DATE_EPOCH"] = "946684800"
os.environ["MPLCONFIGDIR"] = str(
    BOARD_ROOT / "logs" / "step6_history_comparison" / "mplconfig"
)
Path(os.environ["MPLCONFIGDIR"]).mkdir(parents=True, exist_ok=True)

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402


METHOD_ORDER = ["Original", "Craig-Bampton", "Guyan"]
METHOD_LABEL_ZH = {
    "原结构": "Original",
    "Craig-Bampton": "Craig-Bampton",
    "Guyan": "Guyan",
}
PROVENANCE_LABELS = {
    1: "ORIGINAL_ACTIVE_POINT",
    2: "COMMENTED_AUTHOR_INTENT",
    3: "SAME_FORMULA_SUPPLEMENT",
    4: "FAIL",
}
TABLE_NAMES = [
    "pointwise_comparison",
    "route_eligibility",
    "target_cell_status",
    "confusion_matrix",
    "boundary_by_source",
    "boundary_difference",
    "stability_metrics",
    "extension_1_to_28_audit",
    "extension_summary",
    "claim_C05_C07",
    "div2_payload_relation_audit",
    "figure_status",
]
FIGURE_STEMS = [
    "图4-4_历史最终掩膜边界_绘图级复核",
    "图4-5_历史最终掩膜边界_绘图级复核",
    "图4-4_作者文件身份计算候选_失败诊断",
    "图4-5_作者文件身份计算候选_失败诊断",
]


def expected_output_relpaths() -> set[str]:
    relpaths = {f"tables/{name}.csv" for name in TABLE_NAMES}
    for stem in FIGURE_STEMS:
        relpaths.add(f"figures/{stem}.pdf")
        relpaths.add(f"figures/{stem}.png")
    relpaths.update(
        {
            "checks.csv",
            "figure_style_manifest.csv",
            "protected_input_hashes.csv",
            "report.md",
            "run_summary.json",
        }
    )
    return relpaths


def strict_object(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
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


def resolve_relpath(relpath: str) -> Path:
    path = (BOARD_ROOT / Path(relpath.replace("/", os.sep))).resolve()
    if not path.is_relative_to(BOARD_ROOT.resolve()):
        raise ValueError(f"Path escapes Board20 root: {relpath}")
    return path


def relative(path: Path) -> str:
    return path.resolve().relative_to(BOARD_ROOT.resolve()).as_posix()


def bool_text(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text == "true":
        return True
    if text == "false":
        return False
    raise ValueError(f"Not a Boolean text: {value!r}")


def csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "True" if value else "False"
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return format(value, ".17g")
    return value


def write_csv(path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=list(fieldnames),
            extrasaction="raise",
            lineterminator="\n",
        )
        writer.writeheader()
        for row in rows:
            writer.writerow({name: csv_value(row.get(name)) for name in fieldnames})


def write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text.rstrip() + "\n", encoding="utf-8", newline="\n")


class CheckBook:
    def __init__(self) -> None:
        self.rows: list[dict[str, Any]] = []
        self._counter = 0

    def add(
        self,
        category: str,
        description: str,
        status: str,
        expected: Any,
        actual: Any,
        evidence: str,
    ) -> None:
        if status not in {"PASS", "INFO", "FAIL"}:
            raise ValueError(status)
        self._counter += 1
        self.rows.append(
            {
                "check_id": f"S6C{self._counter:04d}",
                "category": category,
                "description": description,
                "status": status,
                "expected": json.dumps(expected, ensure_ascii=False, sort_keys=True),
                "actual": json.dumps(actual, ensure_ascii=False, sort_keys=True),
                "evidence": evidence,
            }
        )

    def require(
        self,
        category: str,
        description: str,
        condition: bool,
        expected: Any,
        actual: Any,
        evidence: str,
    ) -> None:
        self.add(
            category,
            description,
            "PASS" if condition else "FAIL",
            expected,
            actual,
            evidence,
        )
        if not condition:
            raise RuntimeError(f"Hard gate failed: {description}")

    def info(
        self,
        category: str,
        description: str,
        expected: Any,
        actual: Any,
        evidence: str,
    ) -> None:
        self.add(category, description, "INFO", expected, actual, evidence)

    def summary(self) -> dict[str, int]:
        return {
            "total": len(self.rows),
            "pass": sum(row["status"] == "PASS" for row in self.rows),
            "info": sum(row["status"] == "INFO" for row in self.rows),
            "fail": sum(row["status"] == "FAIL" for row in self.rows),
        }


def verify_input_bindings(contract: Mapping[str, Any], checks: CheckBook) -> None:
    for binding in contract["input_bindings"]:
        path = resolve_relpath(binding["relpath"])
        actual = {
            "exists": path.is_file(),
            "bytes": path.stat().st_size if path.is_file() else None,
            "sha256": sha256_file(path) if path.is_file() else None,
        }
        expected = {
            "exists": True,
            "bytes": int(binding["bytes"]),
            "sha256": binding["sha256"],
        }
        checks.require(
            "input_binding",
            f"绑定输入未漂移：{binding['relpath']}",
            actual == expected,
            expected,
            actual,
            binding["relpath"],
        )


def verify_clean_probe_receipt(
    contract: Mapping[str, Any], checks: CheckBook
) -> dict[str, str]:
    receipt_contract = contract["clean_probe_receipt_contract"]
    receipt_path = resolve_relpath(receipt_contract["relpath"])
    receipt = read_json(receipt_path)
    required_targets = list(receipt_contract["required_targets"])
    expected_keys = {
        "schema_version",
        "action_id",
        "status",
        "started_utc",
        "completed_utc",
        "script_sha256",
        "contract_sha256",
        "fs_protocol_sha256",
        "targets",
        "postconditions",
    }
    postconditions = receipt.get("postconditions", {})
    condition = (
        set(receipt) == expected_keys
        and receipt.get("schema_version") == receipt_contract["schema_version"]
        and receipt.get("status") == receipt_contract["required_status"]
        and isinstance(receipt.get("action_id"), str)
        and bool(receipt.get("action_id"))
        and isinstance(receipt.get("started_utc"), str)
        and isinstance(receipt.get("completed_utc"), str)
        and receipt.get("script_sha256") == sha256_file(RESET_SCRIPT_PATH)
        and receipt.get("contract_sha256") == sha256_file(CONTRACT_PATH)
        and receipt.get("fs_protocol_sha256") == sha256_file(FS_PROTOCOL_PATH)
        and list(receipt.get("targets", {}).keys()) == required_targets
        and list(postconditions.keys()) == required_targets
        and all(
            postconditions[name]
            == {
                "state": receipt_contract["required_post_state"],
                "file_count": 0,
                "directory_count": 0,
            }
            for name in required_targets
        )
    )
    checks.require(
        "clean_probe_receipt",
        "两轮生成绑定同一次三固定根清空收据，收据状态、脚本/合同/协议哈希及三个空目录后置条件闭合",
        condition,
        {
            "schema_version": receipt_contract["schema_version"],
            "status": receipt_contract["required_status"],
            "targets": required_targets,
            "post_state": receipt_contract["required_post_state"],
            "hashes_match": True,
        },
        {
            "schema_version": receipt.get("schema_version"),
            "status": receipt.get("status"),
            "targets": list(receipt.get("targets", {}).keys()),
            "postconditions": postconditions,
            "hashes_match": receipt.get("script_sha256")
            == sha256_file(RESET_SCRIPT_PATH)
            and receipt.get("contract_sha256") == sha256_file(CONTRACT_PATH)
            and receipt.get("fs_protocol_sha256") == sha256_file(FS_PROTOCOL_PATH),
        },
        receipt_contract["relpath"],
    )
    return {
        "action_id": str(receipt.get("action_id", "")),
        "sha256": sha256_file(receipt_path),
    }


def read_csv_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames is None:
            raise ValueError(f"CSV has no header: {path}")
        return list(reader.fieldnames), list(reader)


def matlab_numeric(handle: h5py.File, variable: str) -> np.ndarray:
    return np.asarray(handle[variable], dtype=np.float64).T.copy()


def stable_mask_from_historical(values: np.ndarray) -> np.ndarray:
    return np.isfinite(values) & (values > 0.0) & (values < 1.0)


def upper_envelope(mask: np.ndarray) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for j in range(mask.shape[1]):
        stable_rows = np.flatnonzero(mask[:, j])
        has_stable = bool(stable_rows.size)
        if has_stable:
            min_l = int(stable_rows[0])
            max_l = int(stable_rows[-1])
            expected = np.arange(max_l + 1)
            missing = np.setdiff1d(expected, stable_rows, assume_unique=True)
            hole_count = int(missing.size)
            contiguous = min_l == 0 and hole_count == 0
        else:
            min_l = None
            max_l = None
            hole_count = 0
            contiguous = True
        rows.append(
            {
                "j": j,
                "has_stable": has_stable,
                "stable_count_in_column": int(stable_rows.size),
                "min_l": min_l,
                "max_l": max_l,
                "contiguous_from_zero": contiguous,
                "hole_count": hole_count,
            }
        )
    return rows


def origin_connected_intercept(values: np.ndarray) -> int | None:
    """Return the last stable index in the stable prefix connected to index zero."""
    flags = np.asarray(values, dtype=bool).reshape(-1)
    if flags.size == 0 or not bool(flags[0]):
        return None
    first_unstable = np.flatnonzero(~flags)
    return int(first_unstable[0] - 1) if first_unstable.size else int(flags.size - 1)


def mask_metrics(mask: np.ndarray, dt_ms: float) -> dict[str, Any]:
    points = np.argwhere(mask)
    if points.size:
        max_l = int(points[:, 0].max())
        max_j = int(points[:, 1].max())
    else:
        max_l = None
        max_j = None

    diag_len = min(mask.shape)
    tau1_intercept = origin_connected_intercept(mask[0, :])
    tau2_intercept = origin_connected_intercept(mask[:, 0])
    diagonal_intercept = origin_connected_intercept(
        np.diag(mask[:diag_len, :diag_len])
    )

    envelope = upper_envelope(mask)
    hole_columns = sum(row["hole_count"] > 0 for row in envelope)
    hole_cells = sum(int(row["hole_count"]) for row in envelope)
    empty_columns = sum(not row["has_stable"] for row in envelope)
    all_columns_contiguous = hole_columns == 0 and all(
        row["contiguous_from_zero"] for row in envelope
    )

    # Integrate each contiguous run of non-empty columns separately. The value is
    # an upper-envelope diagnostic when holes exist; the grid-cell proxy remains
    # the only exact classification-area proxy in that case.
    integral_step2 = 0
    previous_j: int | None = None
    previous_l: int | None = None
    for row in envelope:
        if not row["has_stable"]:
            previous_j = None
            previous_l = None
            continue
        j = int(row["j"])
        max_l_col = int(row["max_l"])
        if previous_j is not None and j == previous_j + 1:
            integral_step2 += int(previous_l)
        previous_j = j
        previous_l = max_l_col

    stable_count = int(mask.sum())
    return {
        "stable_count": stable_count,
        "max_tau1_any_stable_step": max_j,
        "max_tau1_any_stable_ms": None if max_j is None else max_j * dt_ms,
        "max_tau2_any_stable_step": max_l,
        "max_tau2_any_stable_ms": None if max_l is None else max_l * dt_ms,
        "axis_intercept_definition": "ORIGIN_CONNECTED_CONTIGUOUS_PREFIX_LAST_STABLE_INDEX_NO_HOLE_CROSSING",
        "tau1_axis_intercept_step": tau1_intercept,
        "tau1_axis_intercept_ms": None
        if tau1_intercept is None
        else tau1_intercept * dt_ms,
        "tau2_axis_intercept_step": tau2_intercept,
        "tau2_axis_intercept_ms": None
        if tau2_intercept is None
        else tau2_intercept * dt_ms,
        "equal_delay_diagonal_intercept_step": diagonal_intercept,
        "equal_delay_diagonal_intercept_ms": None
        if diagonal_intercept is None
        else diagonal_intercept * dt_ms,
        "stable_grid_area_proxy_ms2": stable_count * dt_ms * dt_ms,
        "upper_envelope_integral_ms2": integral_step2 * dt_ms * dt_ms,
        "empty_column_count": empty_columns,
        "hole_column_count": hole_columns,
        "hole_cell_count": hole_cells,
        "connected_component_count_4_neighbor": connected_components_4(mask),
        "all_columns_contiguous_from_zero": all_columns_contiguous,
        "upper_envelope_role": "TRUE_FILLED_BOUNDARY"
        if all_columns_contiguous
        else "DIAGNOSTIC_UPPER_ENVELOPE_WITH_HOLES",
    }


def load_historical(
    contract: Mapping[str, Any], checks: CheckBook
) -> tuple[
    dict[tuple[str, str], np.ndarray],
    dict[tuple[str, str], np.ndarray],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    masks: dict[tuple[str, str], np.ndarray] = {}
    raw_values: dict[tuple[str, str], np.ndarray] = {}
    boundary_rows: list[dict[str, Any]] = []
    extension_rows: list[dict[str, Any]] = []
    grid = contract["grid_contract"]
    dt_ms = float(grid["dt_milliseconds"])
    method_variables = contract["method_variables"]

    for division in ["div1", "div2"]:
        record = contract["historical_masks"][division]
        raw_path = resolve_relpath(record["raw_relpath"])
        duplicate_path = resolve_relpath(record["duplicate_relpath"])
        clean_path = resolve_relpath(record["clean_relpath"])
        raw = loadmat(raw_path)
        duplicate = loadmat(duplicate_path)
        clean = loadmat(clean_path)

        checks.require(
            "historical_identity",
            f"{division}历史MAT与绘图级原始来源副本字节相同",
            raw_path.read_bytes() == duplicate_path.read_bytes(),
            True,
            raw_path.read_bytes() == duplicate_path.read_bytes(),
            f"{record['raw_relpath']} | {record['duplicate_relpath']}",
        )
        clean_shape = tuple(int(x) for x in np.asarray(clean["common_grid_shape"]).ravel())
        checks.require(
            "historical_grid",
            f"{division}清洗MAT共同网格尺寸",
            clean_shape == tuple(grid["shape"]),
            grid["shape"],
            clean_shape,
            record["clean_relpath"],
        )

        for method in METHOD_ORDER:
            variables = method_variables[method]
            values = np.asarray(raw[variables["historical_variable"]], dtype=float)
            duplicate_values = np.asarray(
                duplicate[variables["historical_variable"]], dtype=float
            )
            checks.require(
                "historical_identity",
                f"{division} {method}原始数组与来源副本逐元素相同",
                np.array_equal(values, duplicate_values),
                True,
                np.array_equal(values, duplicate_values),
                record["raw_relpath"],
            )
            common = values[:31, :67]
            mask = stable_mask_from_historical(common)
            clean_mask = np.asarray(clean[variables["clean_variable"]], dtype=bool)
            checks.require(
                "historical_clean_mask",
                f"{division} {method}原始历史谓词与清洗掩膜逐点一致",
                mask.shape == (31, 67) and np.array_equal(mask, clean_mask),
                {"shape": [31, 67], "mismatch": 0},
                {
                    "shape": list(mask.shape),
                    "mismatch": int(np.sum(mask != clean_mask)),
                },
                record["clean_relpath"],
            )
            masks[(division, method)] = mask
            raw_values[(division, method)] = common

            for envelope_row in upper_envelope(mask):
                max_l = envelope_row["max_l"]
                boundary_rows.append(
                    {
                        "figure_id": record["figure_id"],
                        "division": division,
                        "method": method,
                        "source_kind": "HISTORICAL_MASK",
                        "source_id": f"historical_{division}_{method.replace('-', '_')}",
                        "route_id": "",
                        "route_role": "HISTORICAL_VALUE",
                        "j": envelope_row["j"],
                        "tau1_ms": envelope_row["j"] * dt_ms,
                        "has_stable": envelope_row["has_stable"],
                        "stable_count_in_column": envelope_row[
                            "stable_count_in_column"
                        ],
                        "min_l": envelope_row["min_l"],
                        "max_l": max_l,
                        "tau2_upper_ms": None if max_l is None else max_l * dt_ms,
                        "contiguous_from_zero": envelope_row[
                            "contiguous_from_zero"
                        ],
                        "hole_count": envelope_row["hole_count"],
                        "boundary_role": "TRUE_FILLED_BOUNDARY",
                    }
                )

    # Validate the two out-of-grid 1..28 sequences without reinterpreting them.
    div2_raw = loadmat(resolve_relpath(contract["historical_masks"]["div2"]["raw_relpath"]))
    for extension in contract["second_division_extension_contract"]:
        values = np.asarray(div2_raw[extension["variable"]], dtype=float)
        expected_shape = tuple(extension["raw_shape"])
        checks.require(
            "extension_1_to_28",
            f"{extension['method']}第二类历史扩展数组尺寸",
            values.shape == expected_shape,
            expected_shape,
            values.shape,
            contract["historical_masks"]["div2"]["raw_relpath"],
        )
        row = int(extension["sequence_row_1based"]) - 1
        start = int(extension["sequence_column_start_1based"]) - 1
        end = int(extension["sequence_column_end_1based"])
        actual_sequence = values[row, start:end]
        expected_sequence = np.arange(1, 29, dtype=float)
        checks.require(
            "extension_1_to_28",
            f"{extension['method']}网格外序列精确为1至28",
            np.array_equal(actual_sequence, expected_sequence),
            expected_sequence.tolist(),
            actual_sequence.tolist(),
            contract["historical_masks"]["div2"]["raw_relpath"],
        )
        outside = values.copy()
        outside[:31, :67] = 0.0
        outside_nonzero = int(np.count_nonzero(outside))
        outside_stable = int(np.sum(stable_mask_from_historical(outside)))
        checks.require(
            "extension_1_to_28",
            f"{extension['method']}共同格外只有28个非零序列且无严格稳定点",
            outside_nonzero == 28 and outside_stable == 0,
            {"outside_nonzero": 28, "outside_stable": 0},
            {
                "outside_nonzero": outside_nonzero,
                "outside_stable": outside_stable,
            },
            contract["historical_masks"]["div2"]["raw_relpath"],
        )
        for offset, actual in enumerate(actual_sequence):
            column_1based = start + offset + 1
            extension_rows.append(
                {
                    "method": extension["method"],
                    "variable": extension["variable"],
                    "raw_rows": values.shape[0],
                    "raw_columns": values.shape[1],
                    "sequence_row_1based": row + 1,
                    "sequence_column_1based": column_1based,
                    "expected_value": offset + 1,
                    "actual_value": float(actual),
                    "value_match": float(actual) == float(offset + 1),
                    "inside_common_31x67": row < 31 and column_1based <= 67,
                    "strict_historical_stable": bool(
                        np.isfinite(actual) and actual > 0.0 and actual < 1.0
                    ),
                    "interpretation": "HISTORICAL_OUT_OF_GRID_INDEX_SEQUENCE_NOT_RHO",
                }
            )

    return masks, raw_values, boundary_rows, extension_rows


def connected_components_4(mask: np.ndarray) -> int:
    visited = np.zeros(mask.shape, dtype=bool)
    count = 0
    for start_l, start_j in np.argwhere(mask):
        if visited[start_l, start_j]:
            continue
        count += 1
        stack = [(int(start_l), int(start_j))]
        visited[start_l, start_j] = True
        while stack:
            l_value, j_value = stack.pop()
            for dl, dj in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
                nl, nj = l_value + dl, j_value + dj
                if (
                    0 <= nl < mask.shape[0]
                    and 0 <= nj < mask.shape[1]
                    and mask[nl, nj]
                    and not visited[nl, nj]
                ):
                    visited[nl, nj] = True
                    stack.append((nl, nj))
    return count


def verify_upstream_gate(contract: Mapping[str, Any], checks: CheckBook) -> None:
    v5_path = resolve_relpath(
        "outputs/step5_fullq_svd_candidate_audit_v5_full/"
        "v5_full_validator_full_postcheck.json"
    )
    v5 = read_json(v5_path)
    summary = v5["summary"]
    expected_summary = {
        "overall_status": "PASS",
        "passed_checks": 100,
        "information_checks": 4,
        "failed_checks": 0,
        "candidate_computation_launched": False,
        "candidate_outputs_modified": False,
    }
    actual_summary = {key: summary.get(key) for key in expected_summary}
    checks.require(
        "step5_gate",
        "V5全网格后检查状态允许进入历史掩膜比较",
        actual_summary == expected_summary,
        expected_summary,
        actual_summary,
        relative(v5_path),
    )

    repeat_path = resolve_relpath(
        "code/board20_step5_fullq_svd_candidate_validator_v5_full_postcheck_repeatability.json"
    )
    repeat = read_json(repeat_path)
    expected_repeat = {
        "status": "PASS",
        "run_count": 2,
        "each_run_exit_code": 0,
        "each_run_overall_status": "PASS",
        "each_run_pass_count": 100,
        "each_run_info_count": 4,
        "each_run_fail_count": 0,
        "each_run_point_comparison_count": 10385,
        "artifact_match_count": 9,
        "artifact_mismatch_count": 0,
        "scientific_report_and_log_artifacts_byte_identical": True,
    }
    actual_repeat = {key: repeat.get(key) for key in expected_repeat}
    checks.require(
        "step5_gate",
        "V5两轮后检查重复性记录通过",
        actual_repeat == expected_repeat,
        expected_repeat,
        actual_repeat,
        relative(repeat_path),
    )

    artifact_failures: list[str] = []
    for relpath, record in sorted(repeat["run1_artifacts"].items()):
        path = resolve_relpath(relpath)
        if (
            not path.is_file()
            or path.stat().st_size != int(record["bytes"])
            or sha256_file(path) != record["sha256"]
        ):
            artifact_failures.append(relpath)
    checks.require(
        "step5_gate",
        "V5首轮封存的9项科学、报告与日志工件仍未漂移",
        not artifact_failures,
        {"artifact_count": 9, "failures": []},
        {
            "artifact_count": len(repeat["run1_artifacts"]),
            "failures": artifact_failures,
        },
        relative(repeat_path),
    )

    protected_path = resolve_relpath(
        "outputs/step5_fullq_svd_candidate_audit_v5_full/"
        "v5_full_validator_full_postcheck_protected_hashes.csv"
    )
    fields, protected_rows = read_csv_rows(protected_path)
    checks.require(
        "protected_inputs",
        "V5保护哈希表字段完整",
        fields == ["relpath", "sha256_before", "sha256_after", "unchanged"],
        ["relpath", "sha256_before", "sha256_after", "unchanged"],
        fields,
        relative(protected_path),
    )
    protected_failures: list[str] = []
    for row in protected_rows:
        path = resolve_relpath(row["relpath"])
        expected = row["sha256_before"]
        current = sha256_file(path) if path.is_file() else "MISSING"
        if (
            row["sha256_after"] != expected
            or not bool_text(row["unchanged"])
            or current != expected
        ):
            protected_failures.append(row["relpath"])
    checks.require(
        "protected_inputs",
        "V5登记的163项保护文件当前哈希不变",
        len(protected_rows) == 163 and not protected_failures,
        {"count": 163, "failures": []},
        {"count": len(protected_rows), "failures": protected_failures},
        relative(protected_path),
    )


def verify_artifact_manifest(
    manifest_relpath: str, checks: CheckBook, category: str
) -> None:
    manifest = resolve_relpath(manifest_relpath)
    fields, rows = read_csv_rows(manifest)
    if {"relpath", "bytes", "sha256"}.issubset(fields):
        path_field = "relpath"
        bytes_field = "bytes"
    elif {"relative_path", "size_bytes", "sha256"}.issubset(fields):
        path_field = "relative_path"
        bytes_field = "size_bytes"
    else:
        path_field = ""
        bytes_field = ""
    required_variants = [
        ["relpath", "bytes", "sha256"],
        ["relative_path", "size_bytes", "sha256"],
    ]
    checks.require(
        category,
        "工件清单字段匹配当前或早期显式格式",
        bool(path_field and bytes_field),
        required_variants,
        fields,
        manifest_relpath,
    )
    failures: list[str] = []
    for row in rows:
        row_relpath = row[path_field]
        candidates = [resolve_relpath(row_relpath)]
        local_candidate = (
            manifest.parent / Path(row_relpath.replace("/", os.sep))
        ).resolve()
        if local_candidate.is_relative_to(BOARD_ROOT.resolve()):
            candidates.append(local_candidate)
        matches = [
            path
            for path in dict.fromkeys(candidates)
            if path.is_file()
            and path.stat().st_size == int(row[bytes_field])
            and sha256_file(path) == row["sha256"]
        ]
        if not matches:
            failures.append(row[path_field])
    checks.require(
        category,
        f"{manifest_relpath}逐文件字节数与SHA-256闭合",
        not failures,
        {"rows": len(rows), "failures": []},
        {"rows": len(rows), "failures": failures},
        manifest_relpath,
    )


def validate_frozen_boundaries(
    contract: Mapping[str, Any], historical_masks: Mapping[tuple[str, str], np.ndarray], checks: CheckBook
) -> None:
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    for division in ["div1", "div2"]:
        record = contract["historical_masks"][division]
        fields, rows = read_csv_rows(resolve_relpath(record["boundary_relpath"]))
        required = {
            "方法",
            "原图横坐标索引",
            "原图纵坐标索引",
            "时滞1采样步",
            "时滞2采样步",
            "时滞1毫秒",
            "时滞2毫秒",
        }
        checks.require(
            "historical_boundary",
            f"{division}冻结边界CSV字段完整",
            required.issubset(fields),
            sorted(required),
            fields,
            record["boundary_relpath"],
        )
        observed: dict[tuple[str, int], tuple[int, int, int, float, float]] = {}
        for row in rows:
            method = METHOD_LABEL_ZH[row["方法"]]
            x_index = int(row["原图横坐标索引"])
            observed[(method, x_index - 1)] = (
                int(row["原图纵坐标索引"]) - 1,
                int(row["时滞1采样步"]),
                int(row["时滞2采样步"]),
                float(row["时滞1毫秒"]),
                float(row["时滞2毫秒"]),
            )
        mismatches: list[dict[str, Any]] = []
        expected_count = 0
        for method in METHOD_ORDER:
            for envelope in upper_envelope(historical_masks[(division, method)]):
                if not envelope["has_stable"]:
                    continue
                expected_count += 1
                j = int(envelope["j"])
                l_value = int(envelope["max_l"])
                expected = (l_value, j, l_value, j * dt_ms, l_value * dt_ms)
                actual = observed.get((method, j))
                match = actual is not None and actual[:3] == expected[:3]
                if match:
                    match = math.isclose(actual[3], expected[3], abs_tol=5e-10) and math.isclose(
                        actual[4], expected[4], abs_tol=5e-10
                    )
                if not match:
                    mismatches.append(
                        {"method": method, "j": j, "expected": expected, "actual": actual}
                    )
        checks.require(
            "historical_boundary",
            f"{division}原始历史掩膜重新提取边界与冻结CSV逐行一致",
            len(observed) == expected_count and not mismatches,
            {"rows": expected_count, "mismatches": []},
            {"rows": len(observed), "mismatches": mismatches[:10]},
            record["boundary_relpath"],
        )


def load_route_data(
    route: Mapping[str, Any], contract: Mapping[str, Any], checks: CheckBook
) -> dict[str, Any]:
    grid = contract["grid_contract"]
    point_path = resolve_relpath(route["point_summary_relpath"])
    fields, rows = read_csv_rows(point_path)
    required_fields = {
        "route_id",
        "route_role",
        "declared_method",
        "division",
        "route_formula",
        "l",
        "j",
        "rho",
        "stable",
        "critical",
        "point_status",
    }
    checks.require(
        "candidate_schema",
        f"{route['route_id']} Step5点表字段完整",
        required_fields.issubset(fields),
        sorted(required_fields),
        fields,
        route["point_summary_relpath"],
    )
    checks.require(
        "candidate_schema",
        f"{route['route_id']} Step5点数为2077",
        len(rows) == int(grid["point_count"]),
        int(grid["point_count"]),
        len(rows),
        route["point_summary_relpath"],
    )

    rho = np.full((31, 67), np.nan, dtype=float)
    stable_stored = np.zeros((31, 67), dtype=bool)
    critical_stored = np.zeros((31, 67), dtype=bool)
    seen = np.zeros((31, 67), dtype=bool)
    order_failures: list[list[int]] = []
    identity_failures: list[int] = []
    for index, row in enumerate(rows):
        l_value = int(row["l"])
        j_value = int(row["j"])
        expected_l, expected_j = divmod(index, 67)
        if (l_value, j_value) != (expected_l, expected_j):
            order_failures.append([index, l_value, j_value, expected_l, expected_j])
        if not (0 <= l_value < 31 and 0 <= j_value < 67) or seen[l_value, j_value]:
            raise RuntimeError(f"Duplicate or invalid coordinate in {point_path}: {(l_value, j_value)}")
        seen[l_value, j_value] = True
        rho[l_value, j_value] = float(row["rho"])
        stable_stored[l_value, j_value] = bool_text(row["stable"])
        critical_stored[l_value, j_value] = bool_text(row["critical"])
        if (
            row["route_id"] != route["route_id"]
            or row["route_role"] != route["route_role"]
            or row["declared_method"] != route["method"]
            or row["division"] != route["division"]
            or row["route_formula"] != route["route_formula"]
            or row["point_status"] != "PASS"
        ):
            identity_failures.append(index)

    checks.require(
        "candidate_point_identity",
        f"{route['route_id']}点序、坐标全集与路线身份严格闭合",
        bool(np.all(seen)) and not order_failures and not identity_failures,
        {"seen": 2077, "order_failures": [], "identity_failures": []},
        {
            "seen": int(seen.sum()),
            "order_failures": order_failures[:10],
            "identity_failures": identity_failures[:10],
        },
        route["point_summary_relpath"],
    )

    stable_rederived = np.isfinite(rho) & (rho < 1.0)
    critical_rederived = np.isfinite(rho) & (np.abs(rho - 1.0) <= float(grid["critical_tolerance"]))
    checks.require(
        "candidate_stable_rule",
        f"{route['route_id']}保存稳定分类严格等于finite(rho)且rho<1",
        np.array_equal(stable_stored, stable_rederived),
        0,
        int(np.sum(stable_stored != stable_rederived)),
        route["point_summary_relpath"],
    )
    checks.require(
        "candidate_critical_rule",
        f"{route['route_id']}临界诊断严格等于|rho-1|<=1e-8",
        np.array_equal(critical_stored, critical_rederived),
        0,
        int(np.sum(critical_stored != critical_rederived)),
        route["point_summary_relpath"],
    )

    step4_path = resolve_relpath(route["step4_mat_relpath"])
    with h5py.File(step4_path, "r") as handle:
        rho_step4 = matlab_numeric(handle, "rho")
        stable_step4 = matlab_numeric(handle, "stable") != 0
        provenance_code = matlab_numeric(handle, "provenance_code").astype(int)
        status_step4 = matlab_numeric(handle, "status").astype(int)
    max_rho_diff = float(np.max(np.abs(rho - rho_step4)))
    checks.require(
        "step4_step5_crosscheck",
        f"{route['route_id']} Step4 MATLAB与Step5 V4 rho差不高于1e-8且分类一致",
        rho_step4.shape == (31, 67)
        and max_rho_diff <= 1e-8
        and np.array_equal(stable_rederived, stable_step4)
        and np.all(status_step4 == 1),
        {"shape": [31, 67], "max_rho_abs_diff_lte": 1e-8, "stable_mismatch": 0, "status": 1},
        {
            "shape": list(rho_step4.shape),
            "max_rho_abs_diff": max_rho_diff,
            "stable_mismatch": int(np.sum(stable_rederived != stable_step4)),
            "status_unique": sorted(int(x) for x in np.unique(status_step4)),
        },
        route["step4_mat_relpath"],
    )
    return {
        "route": dict(route),
        "fields": fields,
        "rows": rows,
        "rho": rho,
        "stable": stable_rederived,
        "critical": critical_rederived,
        "rho_step4": rho_step4,
        "stable_step4": stable_step4,
        "provenance_code": provenance_code,
        "max_rho_step4_v4_abs_diff": max_rho_diff,
    }


def difference_or_none(base: Any, reduced: Any) -> float | int | None:
    if base is None or reduced is None or base == "" or reduced == "":
        return None
    return base - reduced


def build_comparison_tables(
    contract: Mapping[str, Any],
    historical_masks: Mapping[tuple[str, str], np.ndarray],
    historical_raw: Mapping[tuple[str, str], np.ndarray],
    historical_boundary_rows: list[dict[str, Any]],
    extension_rows: list[dict[str, Any]],
    route_data: Mapping[str, Mapping[str, Any]],
    checks: CheckBook,
) -> dict[str, Any]:
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    point_rows: list[dict[str, Any]] = []
    confusion_by_route: dict[str, dict[str, Any]] = {}
    boundary_rows = list(historical_boundary_rows)
    boundary_difference_rows: list[dict[str, Any]] = []
    metrics_rows: list[dict[str, Any]] = []
    metrics_by_source: dict[str, dict[str, Any]] = {}

    for division in ["div1", "div2"]:
        figure_id = contract["historical_masks"][division]["figure_id"]
        for method in METHOD_ORDER:
            source_id = f"historical_{division}_{method.replace('-', '_')}"
            metrics = mask_metrics(historical_masks[(division, method)], dt_ms)
            row = {
                "source_id": source_id,
                "source_kind": "HISTORICAL_MASK",
                "figure_id": figure_id,
                "division": division,
                "method": method,
                "route_id": "",
                "route_role": "HISTORICAL_VALUE",
                **metrics,
            }
            metrics_rows.append(row)
            metrics_by_source[source_id] = row

    for route in contract["routes"]:
        route_id = route["route_id"]
        data = route_data[route_id]
        candidate = np.asarray(data["stable"], dtype=bool)
        history = historical_masks[(route["division"], route["method"])]
        raw = historical_raw[(route["division"], route["method"])]
        tp = int(np.sum(candidate & history))
        tn = int(np.sum(~candidate & ~history))
        fp = int(np.sum(candidate & ~history))
        fn = int(np.sum(~candidate & history))
        mismatch = fp + fn
        metrics = mask_metrics(candidate, dt_ms)
        comparison_status = "EXACT_MASK_MATCH" if mismatch == 0 else "MASK_MISMATCH"
        confusion = {
            "figure_id": route["figure_id"],
            "division": route["division"],
            "method": route["method"],
            "route_id": route_id,
            "route_role": route["route_role"],
            "route_formula": route["route_formula"],
            "availability": "COMPUTABLE_CONTINUOUS_RHO",
            "evaluated_points": 2077,
            "expected_points": 2077,
            "historical_stable_points": int(history.sum()),
            "candidate_stable_points": int(candidate.sum()),
            "true_positive": tp,
            "true_negative": tn,
            "false_positive": fp,
            "false_negative": fn,
            "mask_mismatch_points": mismatch,
            "agreement_fraction": (tp + tn) / 2077.0,
            "candidate_is_subset_of_historical": fp == 0,
            "comparison_status": comparison_status,
            "calculation_level_mask_gate_pass": mismatch == 0,
            "max_rho_step4_v4_abs_diff": data["max_rho_step4_v4_abs_diff"],
            "candidate_hole_columns": metrics["hole_column_count"],
            "candidate_hole_cells": metrics["hole_cell_count"],
            "candidate_connected_components": metrics[
                "connected_component_count_4_neighbor"
            ],
        }
        confusion_by_route[route_id] = confusion
        checks.info(
            "historical_mask_comparison",
            f"{route_id}与对应历史掩膜的对象门结果",
            {"mask_mismatch_points": 0, "calculation_level_mask_gate_pass": True},
            {
                "mask_mismatch_points": mismatch,
                "calculation_level_mask_gate_pass": mismatch == 0,
            },
            route["point_summary_relpath"],
        )

        metric_row = {
            "source_id": route_id,
            "source_kind": "COMPUTED_ROUTE",
            "figure_id": route["figure_id"],
            "division": route["division"],
            "method": route["method"],
            "route_id": route_id,
            "route_role": route["route_role"],
            **metrics,
        }
        metrics_rows.append(metric_row)
        metrics_by_source[route_id] = metric_row

        route_envelope = upper_envelope(candidate)
        history_envelope = upper_envelope(history)
        for envelope in route_envelope:
            max_l = envelope["max_l"]
            boundary_rows.append(
                {
                    "figure_id": route["figure_id"],
                    "division": route["division"],
                    "method": route["method"],
                    "source_kind": "COMPUTED_ROUTE",
                    "source_id": route_id,
                    "route_id": route_id,
                    "route_role": route["route_role"],
                    "j": envelope["j"],
                    "tau1_ms": envelope["j"] * dt_ms,
                    "has_stable": envelope["has_stable"],
                    "stable_count_in_column": envelope[
                        "stable_count_in_column"
                    ],
                    "min_l": envelope["min_l"],
                    "max_l": max_l,
                    "tau2_upper_ms": None if max_l is None else max_l * dt_ms,
                    "contiguous_from_zero": envelope["contiguous_from_zero"],
                    "hole_count": envelope["hole_count"],
                    "boundary_role": "TRUE_FILLED_BOUNDARY"
                    if envelope["contiguous_from_zero"]
                    else "DIAGNOSTIC_UPPER_ENVELOPE_WITH_HOLES",
                }
            )
            historical_envelope = history_envelope[int(envelope["j"])]
            history_has = bool(historical_envelope["has_stable"])
            candidate_has = bool(envelope["has_stable"])
            if history_has and candidate_has:
                relation = "BOTH"
                boundary_difference = int(envelope["max_l"]) - int(
                    historical_envelope["max_l"]
                )
            elif history_has:
                relation = "HISTORICAL_ONLY"
                boundary_difference = None
            elif candidate_has:
                relation = "CANDIDATE_ONLY"
                boundary_difference = None
            else:
                relation = "NEITHER"
                boundary_difference = None
            boundary_difference_rows.append(
                {
                    "figure_id": route["figure_id"],
                    "division": route["division"],
                    "method": route["method"],
                    "route_id": route_id,
                    "route_role": route["route_role"],
                    "j": envelope["j"],
                    "tau1_ms": envelope["j"] * dt_ms,
                    "boundary_presence_relation": relation,
                    "historical_max_l": historical_envelope["max_l"],
                    "candidate_max_l": envelope["max_l"],
                    "candidate_minus_historical_max_l": boundary_difference,
                    "candidate_minus_historical_tau2_ms": None
                    if boundary_difference is None
                    else boundary_difference * dt_ms,
                    "candidate_column_hole_count": envelope["hole_count"],
                    "boundary_comparison_role": "VALID_UPPER_BOUNDARY_COMPARISON"
                    if envelope["contiguous_from_zero"]
                    else "DIAGNOSTIC_ENVELOPE_ONLY_CANDIDATE_HAS_HOLES",
                }
            )

        for index, csv_row in enumerate(data["rows"]):
            l_value, j_value = divmod(index, 67)
            historical_stable = bool(history[l_value, j_value])
            candidate_stable = bool(candidate[l_value, j_value])
            if candidate_stable and historical_stable:
                confusion_class = "TP"
            elif candidate_stable and not historical_stable:
                confusion_class = "FP"
            elif not candidate_stable and historical_stable:
                confusion_class = "FN"
            else:
                confusion_class = "TN"
            provenance_code = int(data["provenance_code"][l_value, j_value])
            point_rows.append(
                {
                    "figure_id": route["figure_id"],
                    "division": route["division"],
                    "method": route["method"],
                    "route_id": route_id,
                    "route_role": route["route_role"],
                    "route_formula": route["route_formula"],
                    "l": l_value,
                    "j": j_value,
                    "tau1_ms": j_value * dt_ms,
                    "tau2_ms": l_value * dt_ms,
                    "historical_raw_value": float(raw[l_value, j_value]),
                    "historical_stable": historical_stable,
                    "rho_step4_matlab": float(data["rho_step4"][l_value, j_value]),
                    "rho_v4_python": float(data["rho"][l_value, j_value]),
                    "rho_abs_diff_step4_v4": abs(
                        float(data["rho_step4"][l_value, j_value])
                        - float(data["rho"][l_value, j_value])
                    ),
                    "rho_minus_one": float(data["rho"][l_value, j_value]) - 1.0,
                    "candidate_stable_stored": bool_text(csv_row["stable"]),
                    "candidate_stable_rederived": candidate_stable,
                    "step4_stable": bool(data["stable_step4"][l_value, j_value]),
                    "critical_within_1e8": bool(data["critical"][l_value, j_value]),
                    "confusion_class": confusion_class,
                    "mask_xor": candidate_stable != historical_stable,
                    "provenance_code": provenance_code,
                    "provenance_label": PROVENANCE_LABELS[provenance_code],
                    "point_status": csv_row["point_status"],
                }
            )

    primary_by_target: dict[tuple[str, str], Mapping[str, Any]] = {}
    for route in contract["routes"]:
        if route["route_role"] == "PRIMARY":
            primary_by_target[(route["division"], route["method"])] = route

    eligibility_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    confusion_rows: list[dict[str, Any]] = []
    for target in contract["target_cells"]:
        key = (target["division"], target["method"])
        primary = primary_by_target.get(key)
        history_count = int(historical_masks[key].sum())
        if primary is None:
            eligibility = {
                "figure_id": target["figure_id"],
                "division": target["division"],
                "method": target["method"],
                "route_id": "",
                "route_role": "PRIMARY_REQUIRED",
                "route_formula": "",
                "availability": "NOT_COMPUTABLE_MISSING_ROUTE",
                "reason": "AUTHOR_ROUTE_CONTRACT_NOT_EXECUTABLE_DO_NOT_CREATE",
                "candidate_point_count": 0,
                "expected_point_count": 2077,
            }
            target_status = "MISSING_PRIMARY_CONTINUOUS_RHO"
            target_row = {
                **target,
                "historical_stable_points": history_count,
                "primary_route_id": "",
                "primary_candidate_stable_points": "",
                "mask_mismatch_points": "",
                "target_status": target_status,
                "calculation_level_target_gate_pass": False,
            }
            confusion_row = {
                "figure_id": target["figure_id"],
                "division": target["division"],
                "method": target["method"],
                "route_id": "",
                "route_role": "PRIMARY_REQUIRED",
                "route_formula": "",
                "availability": "NOT_COMPUTABLE_MISSING_ROUTE",
                "evaluated_points": 0,
                "expected_points": 2077,
                "historical_stable_points": history_count,
                "candidate_stable_points": "",
                "true_positive": "",
                "true_negative": "",
                "false_positive": "",
                "false_negative": "",
                "mask_mismatch_points": "",
                "agreement_fraction": "",
                "candidate_is_subset_of_historical": "",
                "comparison_status": "NOT_EVALUATED_MISSING_ROUTE",
                "calculation_level_mask_gate_pass": False,
                "max_rho_step4_v4_abs_diff": "",
                "candidate_hole_columns": "",
                "candidate_hole_cells": "",
                "candidate_connected_components": "",
            }
            checks.info(
                "target_cell_gate",
                f"{target['figure_id']} {target['method']}连续rho路线缺失",
                "PRIMARY_CONTINUOUS_RHO_PRESENT",
                target_status,
                "code/board20_step4_route_manifest.json",
            )
        else:
            route_confusion = confusion_by_route[primary["route_id"]]
            eligibility = {
                "figure_id": target["figure_id"],
                "division": target["division"],
                "method": target["method"],
                "route_id": primary["route_id"],
                "route_role": primary["route_role"],
                "route_formula": primary["route_formula"],
                "availability": "COMPUTABLE_CONTINUOUS_RHO",
                "reason": "FILE_IDENTITY_ROUTE_ONLY",
                "candidate_point_count": 2077,
                "expected_point_count": 2077,
            }
            target_status = (
                "PRIMARY_MASK_EXACT_MATCH"
                if route_confusion["mask_mismatch_points"] == 0
                else "PRIMARY_MASK_MISMATCH"
            )
            target_row = {
                **target,
                "historical_stable_points": history_count,
                "primary_route_id": primary["route_id"],
                "primary_candidate_stable_points": route_confusion[
                    "candidate_stable_points"
                ],
                "mask_mismatch_points": route_confusion["mask_mismatch_points"],
                "target_status": target_status,
                "calculation_level_target_gate_pass": route_confusion[
                    "mask_mismatch_points"
                ]
                == 0,
            }
            confusion_row = dict(route_confusion)
        eligibility_rows.append(eligibility)
        target_rows.append(target_row)
        confusion_rows.append(confusion_row)

    # Preserve the alternative Guyan route as a seventh eligibility/confusion row.
    alternative = next(
        route for route in contract["routes"] if route["route_role"] == "ALTERNATIVE_NOT_PRIMARY"
    )
    eligibility_rows.append(
        {
            "figure_id": alternative["figure_id"],
            "division": alternative["division"],
            "method": alternative["method"],
            "route_id": alternative["route_id"],
            "route_role": alternative["route_role"],
            "route_formula": alternative["route_formula"],
            "availability": "COMPUTABLE_ALTERNATIVE_DIAGNOSTIC_ONLY",
            "reason": "MUST_NOT_REPLACE_PRIMARY_GUYAN_OR_PICK_BEST_FIT",
            "candidate_point_count": 2077,
            "expected_point_count": 2077,
        }
    )
    confusion_rows.append(dict(confusion_by_route[alternative["route_id"]]))

    figure_rows: list[dict[str, Any]] = []
    for figure_id, division in [("F4-4", "div1"), ("F4-5", "div2")]:
        cells = [row for row in target_rows if row["figure_id"] == figure_id]
        all_three_present = all(row["primary_route_id"] for row in cells)
        all_three_exact = all(
            bool(row["calculation_level_target_gate_pass"]) for row in cells
        )
        figure_gate_pass = all_three_present and all_three_exact
        figure_rows.append(
            {
                "figure_id": figure_id,
                "division": division,
                "method_cell_count": 3,
                "primary_continuous_rho_cell_count": sum(
                    bool(row["primary_route_id"]) for row in cells
                ),
                "exact_mask_match_cell_count": sum(
                    bool(row["calculation_level_target_gate_pass"]) for row in cells
                ),
                "all_three_primary_routes_present": all_three_present,
                "all_three_primary_masks_exact": all_three_exact,
                "calculation_level_figure_gate_pass": figure_gate_pass,
                "object_evidence_level": "CALCULATION_LEVEL_REPRODUCTION"
                if figure_gate_pass
                else "PLOTTING_LEVEL_REPRODUCTION",
                "formal_success_directory_allowed": figure_gate_pass,
                "candidate_location": "BOARD20_FAILURE_ROUTE",
            }
        )

    extension_summary_rows: list[dict[str, Any]] = []
    for extension in contract["second_division_extension_contract"]:
        raw_rows, raw_columns = extension["raw_shape"]
        outside_cells = int(raw_rows * raw_columns - 31 * 67)
        method_rows = [row for row in extension_rows if row["method"] == extension["method"]]
        extension_summary_rows.append(
            {
                "method": extension["method"],
                "variable": extension["variable"],
                "raw_rows": raw_rows,
                "raw_columns": raw_columns,
                "common_grid_cells": 2077,
                "outside_common_grid_cells": outside_cells,
                "outside_nonzero_sequence_cells": len(method_rows),
                "outside_zero_cells": outside_cells - len(method_rows),
                "outside_strict_stable_cells": sum(
                    bool(row["strict_historical_stable"]) for row in method_rows
                ),
                "sequence_values_exact_1_to_28": all(
                    row["value_match"] for row in method_rows
                )
                and len(method_rows) == 28,
                "comparison_disposition": "EXCLUDED_FROM_COMMON_GRID_NOT_RHO",
            }
        )

    # Confirm the two second-division labels carry the same numeric payload,
    # without converting that fact into a theory-equivalence claim.
    left = route_data["main_ori_div2"]
    right = route_data["main_guyan_div2"]
    excluded_fields = {"route_id", "declared_method"}
    compared_fields = [field for field in left["fields"] if field not in excluded_fields]
    unequal_fields: set[str] = set()
    unequal_points = 0
    for left_row, right_row in zip(left["rows"], right["rows"]):
        row_unequal = False
        for field in compared_fields:
            if left_row[field] != right_row[field]:
                unequal_fields.add(field)
                row_unequal = True
        unequal_points += int(row_unequal)
    div2_relation_rows = [
        {
            "left_route": "main_ori_div2",
            "right_route": "main_guyan_div2",
            "point_count": len(left["rows"]),
            "csv_field_count": len(left["fields"]),
            "excluded_identity_fields": ";".join(sorted(excluded_fields)),
            "compared_nonidentity_fields": len(compared_fields),
            "unequal_nonidentity_fields": ";".join(sorted(unequal_fields)),
            "unequal_points": unequal_points,
            "max_rho_abs_diff": float(np.max(np.abs(left["rho"] - right["rho"]))),
            "stable_mismatch_points": int(np.sum(left["stable"] != right["stable"])),
            "relation": "IDENTICAL_NUMERIC_FILE_IDENTITY_PAYLOAD"
            if not unequal_fields
            else "NONIDENTICAL_PAYLOAD",
            "interpretation": "DOES_NOT_PROVE_ORIGINAL_AND_GUYAN_THEORY_EQUIVALENT",
        }
    ]
    checks.require(
        "div2_payload_relation",
        "第二类Original/Guyan除身份字段外的Step5 CSV载荷逐字段相同",
        not unequal_fields and unequal_points == 0,
        {"unequal_fields": [], "unequal_points": 0},
        {"unequal_fields": sorted(unequal_fields), "unequal_points": unequal_points},
        "outputs/step5_fullq_svd_candidate_v4/full",
    )

    expected_intercept_definition = contract["grid_contract"][
        "axis_intercept_definition"
    ]
    div2_origin_intercepts = {
        route_id: {
            "max_tau2_any_stable_step": metrics_by_source[route_id][
                "max_tau2_any_stable_step"
            ],
            "tau2_axis_intercept_step": metrics_by_source[route_id][
                "tau2_axis_intercept_step"
            ],
            "definition": metrics_by_source[route_id]["axis_intercept_definition"],
        }
        for route_id in ["main_ori_div2", "main_guyan_div2"]
    }
    checks.require(
        "origin_connected_axis_intercepts",
        "轴截距只取从原点连续稳定前缀，第二类候选不得跨过孔洞取最后稳定点",
        expected_intercept_definition
        == "ORIGIN_CONNECTED_CONTIGUOUS_PREFIX_LAST_STABLE_INDEX_NO_HOLE_CROSSING"
        and all(
            values["max_tau2_any_stable_step"] == 16
            and values["tau2_axis_intercept_step"] == 6
            and values["definition"] == expected_intercept_definition
            for values in div2_origin_intercepts.values()
        ),
        {
            route_id: {
                "max_tau2_any_stable_step": 16,
                "tau2_axis_intercept_step": 6,
                "definition": expected_intercept_definition,
            }
            for route_id in div2_origin_intercepts
        },
        div2_origin_intercepts,
        "tables/stability_metrics.csv",
    )

    claim_rows: list[dict[str, Any]] = []

    def add_claim(
        comparison_id: str,
        evidence_source: str,
        base_source_id: str,
        reduced_source_id: str,
        claimed_phrase: str,
        route_closure: str,
    ) -> None:
        base = metrics_by_source[base_source_id]
        reduced = metrics_by_source[reduced_source_id]
        claim_rows.append(
            {
                "claim_ids": "C05;C07_CRITICAL_DELAY_COMPONENT",
                "comparison_id": comparison_id,
                "evidence_source": evidence_source,
                "base_source_id": base_source_id,
                "reduced_source_id": reduced_source_id,
                "axis_intercept_definition": contract["grid_contract"][
                    "axis_intercept_definition"
                ],
                "tau1_axis_intercept_drop_ms": difference_or_none(
                    base["tau1_axis_intercept_ms"], reduced["tau1_axis_intercept_ms"]
                ),
                "tau2_axis_intercept_drop_ms": difference_or_none(
                    base["tau2_axis_intercept_ms"], reduced["tau2_axis_intercept_ms"]
                ),
                "equal_delay_diagonal_intercept_drop_ms": difference_or_none(
                    base["equal_delay_diagonal_intercept_ms"],
                    reduced["equal_delay_diagonal_intercept_ms"],
                ),
                "stable_point_drop": difference_or_none(
                    base["stable_count"], reduced["stable_count"]
                ),
                "stable_grid_area_proxy_drop_ms2": difference_or_none(
                    base["stable_grid_area_proxy_ms2"],
                    reduced["stable_grid_area_proxy_ms2"],
                ),
                "claimed_phrase": claimed_phrase,
                "qualitative_tolerance_status": "QUALITATIVE_TOLERANCE_UNDEFINED",
                "route_or_mask_closure": route_closure,
                "eligible_for_calculation_level_upgrade": False,
                "non_upgrade_reason": "SIX_METHOD_DIVISION_CELLS_NOT_CLOSED_AND_AVAILABLE_MASKS_DO_NOT_MATCH_HISTORY",
            }
        )

    add_claim(
        "historical_div1_original_to_cb",
        "HISTORICAL_MASK",
        "historical_div1_Original",
        "historical_div1_Craig_Bampton",
        "first-division reduced-model actuator delay margins decrease by about 5 ms",
        "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY",
    )
    add_claim(
        "historical_div1_original_to_guyan",
        "HISTORICAL_MASK",
        "historical_div1_Original",
        "historical_div1_Guyan",
        "first-division reduced-model actuator delay margins decrease by about 5 ms",
        "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY",
    )
    add_claim(
        "historical_div2_original_to_cb",
        "HISTORICAL_MASK",
        "historical_div2_Original",
        "historical_div2_Craig_Bampton",
        "second-division stability-margin reduction",
        "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY",
    )
    add_claim(
        "historical_div2_original_to_guyan",
        "HISTORICAL_MASK",
        "historical_div2_Original",
        "historical_div2_Guyan",
        "second-division Guyan reduction described as approaching 10 ms",
        "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY",
    )
    add_claim(
        "historical_guyan_div1_to_div2",
        "HISTORICAL_MASK",
        "historical_div1_Guyan",
        "historical_div2_Guyan",
        "second-division Guyan further reduction described as approaching 10 ms",
        "PLOTTING_LEVEL_HISTORICAL_VALUE_ONLY",
    )
    add_claim(
        "computed_div1_original_to_main_guyan",
        "COMPUTED_FILE_IDENTITY_ROUTES",
        "main_ori_div1",
        "main_guyan_div1",
        "first-division reduced-model actuator delay margins decrease by about 5 ms",
        "ROUTE_LEVEL_COMPUTATION_ONLY_MASKS_MISMATCH_HISTORY",
    )
    add_claim(
        "computed_div1_original_to_alternative_guyan",
        "COMPUTED_ALTERNATIVE_ROUTE",
        "main_ori_div1",
        "alt_guyan_div1_stable_full_ps3",
        "diagnostic sensitivity only; alternative must not replace primary",
        "ALTERNATIVE_NOT_PRIMARY_MASK_MISMATCH_HISTORY",
    )
    add_claim(
        "computed_div2_original_to_main_guyan",
        "COMPUTED_FILE_IDENTITY_ROUTES",
        "main_ori_div2",
        "main_guyan_div2",
        "second-division Guyan critical-delay reduction greater than 5 ms",
        "IDENTICAL_NUMERIC_PAYLOAD_UNDER_DIFFERENT_METHOD_LABELS",
    )
    add_claim(
        "computed_main_guyan_div1_to_div2",
        "COMPUTED_FILE_IDENTITY_ROUTES",
        "main_guyan_div1",
        "main_guyan_div2",
        "second-division Guyan further reduction described as approaching 10 ms",
        "ROUTE_LEVEL_COMPUTATION_ONLY_MASKS_MISMATCH_HISTORY",
    )
    claim_rows.append(
        {
            "claim_ids": "C07_FREQUENCY_AND_AMPLITUDE_COMPONENTS",
            "comparison_id": "not_evaluated_in_board20_step6",
            "evidence_source": "OUT_OF_SCOPE",
            "base_source_id": "",
            "reduced_source_id": "",
            "axis_intercept_definition": "",
            "tau1_axis_intercept_drop_ms": "",
            "tau2_axis_intercept_drop_ms": "",
            "equal_delay_diagonal_intercept_drop_ms": "",
            "stable_point_drop": "",
            "stable_grid_area_proxy_drop_ms2": "",
            "claimed_phrase": "frequency bands and response-amplitude errors",
            "qualitative_tolerance_status": "NOT_EVALUATED_IN_STEP6",
            "route_or_mask_closure": "OUTSIDE_BOARD20_STABILITY_SCOPE",
            "eligible_for_calculation_level_upgrade": False,
            "non_upgrade_reason": "BOARD20_STEP6_ONLY_EVALUATES_CRITICAL_DELAY_COMPONENT",
        }
    )

    return {
        "pointwise_comparison": point_rows,
        "route_eligibility": eligibility_rows,
        "target_cell_status": target_rows,
        "confusion_matrix": confusion_rows,
        "boundary_by_source": boundary_rows,
        "boundary_difference": boundary_difference_rows,
        "stability_metrics": metrics_rows,
        "extension_1_to_28_audit": extension_rows,
        "extension_summary": extension_summary_rows,
        "claim_C05_C07": claim_rows,
        "div2_payload_relation_audit": div2_relation_rows,
        "figure_status": figure_rows,
    }


FIXED_PDF_DATE = datetime(2000, 1, 1, tzinfo=timezone.utc)


def configure_plot_style(contract: Mapping[str, Any]) -> None:
    style = contract["plot_style"]
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": [style["font_family"]],
            "font.size": float(style["font_size_pt"]),
            "mathtext.fontset": style["mathtext_fontset"],
            "axes.linewidth": 0.8,
            "axes.unicode_minus": False,
            "xtick.direction": "in",
            "ytick.direction": "in",
            "xtick.top": True,
            "ytick.right": True,
            "legend.frameon": bool(style["legend_frame_allowed"]),
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.dpi": int(style["dpi"]),
        }
    )


def format_delay_axis(
    axis: mpl.axes.Axes, contract: Mapping[str, Any], *, panel_label: str | None = None
) -> None:
    grid = contract["grid_contract"]
    dt_ms = float(grid["dt_milliseconds"])
    axis.set_xlim(0.0, int(grid["j_end"]) * dt_ms)
    axis.set_ylim(0.0, int(grid["l_end"]) * dt_ms)
    axis.set_xlabel(r"Actuator delay $\tau_1$ (ms)")
    axis.set_ylabel(r"Actuator delay $\tau_2$ (ms)")
    axis.xaxis.set_major_locator(MaxNLocator(nbins=7, min_n_ticks=5))
    axis.yaxis.set_major_locator(MaxNLocator(nbins=6, min_n_ticks=5))
    axis.grid(False)
    if panel_label:
        axis.text(
            0.025,
            0.955,
            panel_label,
            transform=axis.transAxes,
            ha="left",
            va="top",
            fontsize=8,
            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 1.5},
        )


def save_figure_pair(
    figure: mpl.figure.Figure,
    output_stem: Path,
    contract: Mapping[str, Any],
    *,
    document_title: str,
) -> tuple[Path, Path]:
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    pdf_path = output_stem.with_suffix(".pdf")
    png_path = output_stem.with_suffix(".png")
    pdf_metadata = {
        "Title": document_title,
        "Author": "Board20 Step6 evidence pipeline",
        "Subject": "Evidence-separated LQR delay-stability comparison",
        "Keywords": "Liang Yu; LQR; delay stability; reproduction audit",
        "Creator": "Board20 Step6 deterministic generator",
        "Producer": "Matplotlib deterministic PDF backend",
        "CreationDate": FIXED_PDF_DATE,
        "ModDate": FIXED_PDF_DATE,
    }
    figure.savefig(pdf_path, format="pdf", metadata=pdf_metadata)
    figure.savefig(
        png_path,
        format="png",
        dpi=int(contract["plot_style"]["dpi"]),
        metadata={"Software": "Board20 Step6 deterministic generator"},
    )
    plt.close(figure)
    return pdf_path, png_path


def historical_boundary_figure(
    division: str,
    historical_masks: Mapping[tuple[str, str], np.ndarray],
    contract: Mapping[str, Any],
    output_root: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    figure_size = tuple(float(x) for x in contract["plot_style"]["figure_size_inch"])
    figure, axis = plt.subplots(figsize=figure_size)
    style_rows: list[dict[str, Any]] = []
    for method in METHOD_ORDER:
        style = contract["plot_style"][method]
        envelope = upper_envelope(historical_masks[(division, method)])
        x_values = [row["j"] * dt_ms for row in envelope if row["has_stable"]]
        y_values = [int(row["max_l"]) * dt_ms for row in envelope if row["has_stable"]]
        axis.step(
            x_values,
            y_values,
            where="post",
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markersize=3.2,
            markerfacecolor="white",
            markeredgewidth=0.75,
            linewidth=1.35,
            markevery=max(1, len(x_values) // 10),
            label=method,
        )
        style_rows.append(
            {
                "figure_id": contract["historical_masks"][division]["figure_id"],
                "artifact_role": "HISTORICAL_PLOTTING_LEVEL",
                "panel": "single_axis",
                "method": method,
                "route_id": "",
                "color": style["color"],
                "linestyle": style["linestyle"],
                "marker": style["marker"],
                "rendered_object": "upper_boundary_step_from_historical_mask",
                "evidence_level": "PLOTTING_LEVEL_REPRODUCTION",
            }
        )
    format_delay_axis(axis, contract)
    axis.legend(loc="upper right", ncol=1, handlelength=3.2)
    axis.text(
        0.025,
        0.055,
        "Historical final masks | plotting-level evidence",
        transform=axis.transAxes,
        ha="left",
        va="bottom",
        fontsize=8,
        color="#333333",
    )
    figure.subplots_adjust(left=0.105, right=0.985, bottom=0.18, top=0.965)
    if division == "div1":
        stem = output_root / "figures" / "图4-4_历史最终掩膜边界_绘图级复核"
        document_title = "Figure 4-4 historical final-mask boundary audit"
    else:
        stem = output_root / "figures" / "图4-5_历史最终掩膜边界_绘图级复核"
        document_title = "Figure 4-5 historical final-mask boundary audit"
    pdf_path, png_path = save_figure_pair(
        figure, stem, contract, document_title=document_title
    )
    return [pdf_path, png_path], style_rows


def draw_rho_contour(
    axis: mpl.axes.Axes,
    rho: np.ndarray,
    contract: Mapping[str, Any],
    *,
    color: str,
    linestyle: str,
    linewidth: float = 1.35,
) -> bool:
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    x_values = np.arange(67, dtype=float) * dt_ms
    y_values = np.arange(31, dtype=float) * dt_ms
    finite = rho[np.isfinite(rho)]
    if finite.size == 0 or not (float(finite.min()) <= 1.0 <= float(finite.max())):
        return False
    axis.contour(
        x_values,
        y_values,
        rho,
        levels=[1.0],
        colors=[color],
        linestyles=[linestyle],
        linewidths=[linewidth],
        antialiased=True,
    )
    return True


def scatter_stable_cells(
    axis: mpl.axes.Axes,
    mask: np.ndarray,
    contract: Mapping[str, Any],
    *,
    color: str,
    marker: str,
    alpha: float = 0.66,
) -> None:
    dt_ms = float(contract["grid_contract"]["dt_milliseconds"])
    points = np.argwhere(mask)
    if not points.size:
        return
    axis.scatter(
        points[:, 1] * dt_ms,
        points[:, 0] * dt_ms,
        s=10,
        marker=marker,
        facecolors="none",
        edgecolors=color,
        linewidths=0.55,
        alpha=alpha,
        rasterized=False,
    )


def computed_div1_figure(
    route_data: Mapping[str, Mapping[str, Any]],
    contract: Mapping[str, Any],
    output_root: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    original = route_data["main_ori_div1"]
    primary_guyan = route_data["main_guyan_div1"]
    alternative = route_data["alt_guyan_div1_stable_full_ps3"]
    style_o = contract["plot_style"]["Original"]
    style_g = contract["plot_style"]["Guyan"]
    figure_size = tuple(float(x) for x in contract["plot_style"]["figure_size_inch"])
    figure, axes = plt.subplots(1, 2, figsize=figure_size, sharex=True, sharey=True)

    for data, style, label in [
        (original, style_o, "Original primary"),
        (primary_guyan, style_g, "Guyan primary"),
    ]:
        scatter_stable_cells(
            axes[0], data["stable"], contract, color=style["color"], marker=style["marker"]
        )
        contour_present = draw_rho_contour(
            axes[0],
            data["rho"],
            contract,
            color=style["color"],
            linestyle=style["linestyle"],
        )
        axes[0].plot(
            [],
            [],
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markerfacecolor="none",
            label=f"{label}: stable cells + " + (r"$\rho=1$" if contour_present else "no crossing"),
        )
    format_delay_axis(axes[0], contract)
    axes[0].legend(loc="upper right", fontsize=7.2, handlelength=2.5)

    for data, marker, label, alpha in [
        (primary_guyan, style_g["marker"], "Guyan primary", 0.72),
        (
            alternative,
            contract["plot_style"]["Guyan_alternative_marker"],
            "Guyan alternative (diagnostic only)",
            0.82,
        ),
    ]:
        scatter_stable_cells(
            axes[1], data["stable"], contract, color=style_g["color"], marker=marker, alpha=alpha
        )
        draw_rho_contour(
            axes[1],
            data["rho"],
            contract,
            color=style_g["color"],
            linestyle=style_g["linestyle"] if data is primary_guyan else ":",
            linewidth=1.35 if data is primary_guyan else 1.1,
        )
        axes[1].plot(
            [],
            [],
            color=style_g["color"],
            linestyle=style_g["linestyle"] if data is primary_guyan else ":",
            marker=marker,
            markerfacecolor="none",
            label=label,
        )
    format_delay_axis(axes[1], contract)
    axes[1].set_ylabel("")
    axes[1].legend(loc="upper right", fontsize=7.0, handlelength=2.5)
    figure.text(0.285, 0.955, "Primary file-identity routes", ha="center", va="top", fontsize=8)
    figure.text(0.75, 0.955, "Guyan route sensitivity", ha="center", va="top", fontsize=8)
    figure.text(
        0.5,
        0.025,
        "Craig-Bampton continuous-rho route is missing; partial candidates are not a three-method reproduction.",
        ha="center",
        va="bottom",
        fontsize=6.9,
        color="#333333",
    )
    figure.subplots_adjust(left=0.09, right=0.99, bottom=0.245, top=0.855, wspace=0.13)
    stem = output_root / "figures" / "图4-4_作者文件身份计算候选_失败诊断"
    pdf_path, png_path = save_figure_pair(
        figure,
        stem,
        contract,
        document_title="Figure 4-4 file-identity computed-route failure diagnostic",
    )
    style_rows = [
        {
            "figure_id": "F4-4",
            "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC",
            "panel": "primary_file_identity",
            "method": "Original",
            "route_id": "main_ori_div1",
            "color": style_o["color"],
            "linestyle": style_o["linestyle"],
            "marker": style_o["marker"],
            "rendered_object": "stable_cells_and_rho_equals_one_contour",
            "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY",
        },
        {
            "figure_id": "F4-4",
            "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC",
            "panel": "primary_file_identity",
            "method": "Guyan",
            "route_id": "main_guyan_div1",
            "color": style_g["color"],
            "linestyle": style_g["linestyle"],
            "marker": style_g["marker"],
            "rendered_object": "stable_cells_and_rho_equals_one_contour",
            "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY",
        },
        {
            "figure_id": "F4-4",
            "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC",
            "panel": "route_sensitivity",
            "method": "Guyan",
            "route_id": "alt_guyan_div1_stable_full_ps3",
            "color": style_g["color"],
            "linestyle": ":",
            "marker": contract["plot_style"]["Guyan_alternative_marker"],
            "rendered_object": "stable_cells_and_rho_equals_one_contour",
            "evidence_level": "ALTERNATIVE_DIAGNOSTIC_NOT_PRIMARY",
        },
        {
            "figure_id": "F4-4",
            "artifact_role": "MISSING_ROUTE",
            "panel": "primary_file_identity",
            "method": "Craig-Bampton",
            "route_id": "",
            "color": contract["plot_style"]["Craig-Bampton"]["color"],
            "linestyle": contract["plot_style"]["Craig-Bampton"]["linestyle"],
            "marker": contract["plot_style"]["Craig-Bampton"]["marker"],
            "rendered_object": "explicit_missing_route_annotation",
            "evidence_level": "DO_NOT_CREATE",
        },
    ]
    return [pdf_path, png_path], style_rows


def computed_div2_figure(
    route_data: Mapping[str, Mapping[str, Any]],
    contract: Mapping[str, Any],
    output_root: Path,
) -> tuple[list[Path], list[dict[str, Any]]]:
    routes = [
        ("main_ori_div2", "Original", "Original-labelled payload"),
        ("main_guyan_div2", "Guyan", "Guyan-labelled payload"),
    ]
    figure_size = tuple(float(x) for x in contract["plot_style"]["figure_size_inch"])
    figure, axes = plt.subplots(1, 2, figsize=figure_size, sharex=True, sharey=True)
    style_rows: list[dict[str, Any]] = []
    for axis, (route_id, method, label) in zip(axes, routes):
        data = route_data[route_id]
        style = contract["plot_style"][method]
        scatter_stable_cells(
            axis, data["stable"], contract, color=style["color"], marker=style["marker"], alpha=0.82
        )
        contour_present = draw_rho_contour(
            axis,
            data["rho"],
            contract,
            color=style["color"],
            linestyle=style["linestyle"],
        )
        axis.plot(
            [],
            [],
            color=style["color"],
            linestyle=style["linestyle"],
            marker=style["marker"],
            markerfacecolor="none",
            label="stable cells + " + (r"$\rho=1$" if contour_present else "no crossing"),
        )
        format_delay_axis(axis, contract, panel_label=label)
        axis.legend(loc="upper right", fontsize=7.2, handlelength=2.5)
        style_rows.append(
            {
                "figure_id": "F4-5",
                "artifact_role": "COMPUTED_FAILURE_DIAGNOSTIC",
                "panel": route_id,
                "method": method,
                "route_id": route_id,
                "color": style["color"],
                "linestyle": style["linestyle"],
                "marker": style["marker"],
                "rendered_object": "stable_cells_and_rho_equals_one_contour_preserving_holes",
                "evidence_level": "ROUTE_LEVEL_COMPUTATION_ONLY",
            }
        )
    axes[1].set_ylabel("")
    figure.text(
        0.5,
        0.975,
        "The two panels have identical numeric payloads; label identity is not theory equivalence.\n"
        "Craig-Bampton continuous-rho route is missing.",
        ha="center",
        va="top",
        fontsize=6.9,
        color="#333333",
    )
    figure.text(
        0.5,
        0.025,
        "Both labelled payloads retain 29 hole cells in 3 columns and 2 connected components.",
        ha="center",
        va="bottom",
        fontsize=6.9,
        color="#333333",
    )
    figure.subplots_adjust(left=0.09, right=0.99, bottom=0.245, top=0.79, wspace=0.13)
    stem = output_root / "figures" / "图4-5_作者文件身份计算候选_失败诊断"
    pdf_path, png_path = save_figure_pair(
        figure,
        stem,
        contract,
        document_title="Figure 4-5 file-identity computed-route failure diagnostic",
    )
    style_rows.append(
        {
            "figure_id": "F4-5",
            "artifact_role": "MISSING_ROUTE",
            "panel": "figure_annotation",
            "method": "Craig-Bampton",
            "route_id": "",
            "color": contract["plot_style"]["Craig-Bampton"]["color"],
            "linestyle": contract["plot_style"]["Craig-Bampton"]["linestyle"],
            "marker": contract["plot_style"]["Craig-Bampton"]["marker"],
            "rendered_object": "explicit_missing_route_annotation",
            "evidence_level": "DO_NOT_CREATE",
        }
    )
    return [pdf_path, png_path], style_rows


def write_tables(output_root: Path, tables: Mapping[str, list[dict[str, Any]]]) -> None:
    for name, rows in tables.items():
        if not rows:
            raise RuntimeError(f"Table unexpectedly empty: {name}")
        write_csv(output_root / "tables" / f"{name}.csv", list(rows[0].keys()), rows)


def snapshot_protected_inputs(output_root: Path) -> list[dict[str, Any]]:
    source = resolve_relpath(
        "outputs/step5_fullq_svd_candidate_audit_v5_full/"
        "v5_full_validator_full_postcheck_protected_hashes.csv"
    )
    _, rows = read_csv_rows(source)
    result: list[dict[str, Any]] = []
    for row in rows:
        path = resolve_relpath(row["relpath"])
        current = sha256_file(path) if path.is_file() else "MISSING"
        result.append(
            {
                "relpath": row["relpath"],
                "sha256_before_v5": row["sha256_before"],
                "sha256_current_step6": current,
                "unchanged": current == row["sha256_before"],
            }
        )
    write_csv(
        output_root / "protected_input_hashes.csv",
        ["relpath", "sha256_before_v5", "sha256_current_step6", "unchanged"],
        result,
    )
    return result


def create_artifact_manifest(output_root: Path) -> list[dict[str, Any]]:
    return atomic_commit_manifest(
        output_root,
        expected_output_relpaths(),
        RUN_OUTPUT_DIRECTORIES,
    )


def comparison_report(
    tables: Mapping[str, list[dict[str, Any]]], check_summary: Mapping[str, int]
) -> str:
    confusion = tables["confusion_matrix"]
    figures = tables["figure_status"]
    lines = [
        "# Board20 Step6 - 历史稳定域与作者文件身份候选计算核对",
        "",
        "## 人话结论",
        "",
        "历史 `.mat` 可以在共同 31×67 网格上完整恢复为六个绘图级稳定掩膜；现有作者文件身份候选路线也都能给出完整 2,077 点连续谱半径，但没有一条候选与对应历史掩膜逐点一致，而且两种划分都缺少 Craig–Bampton 的可执行连续谱半径路线。因此图4-4、图4-5仍只能保留为绘图级复现，候选计算属于失败诊断，不能建立正式成功目录。",
        "",
        "## 逐路线结果",
        "",
        "| 图 | 方法 | 路线 | 候选稳定点 | 历史稳定点 | 错配点 | TP | TN | FP | FN | 状态 |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in confusion:
        lines.append(
            "| {figure_id} | {method} | {route_id} | {candidate_stable_points} | "
            "{historical_stable_points} | {mask_mismatch_points} | {true_positive} | "
            "{true_negative} | {false_positive} | {false_negative} | {comparison_status} |".format(**row)
        )
    lines.extend(
        [
            "",
            "## 图对象门",
            "",
            "| 图 | 三种主路线齐全 | 三种掩膜全匹配 | 证据等级 | 可建正式成功目录 |",
            "|---|---|---|---|---|",
        ]
    )
    for row in figures:
        lines.append(
            f"| {row['figure_id']} | {row['all_three_primary_routes_present']} | "
            f"{row['all_three_primary_masks_exact']} | {row['object_evidence_level']} | "
            f"{row['formal_success_directory_allowed']} |"
        )
    lines.extend(
        [
            "",
            "## 证据边界",
            "",
            "- 历史图只画历史最终掩膜边界，标为绘图级证据。",
            "- 当前计算图只画现有路线的稳定格点与 `rho=1` 等值线，标为候选失败诊断。",
            "- 第一类 Guyan 备选路线仅作敏感性对照，禁止择优替代主路线。",
            "- 第二类 Original/Guyan 的非身份数值载荷完全相同；这只证明文件身份载荷相同，不证明两种理论等价。",
            "- 第二类候选有孔洞，图中保留实际稳定格点与等值线，不把上包络伪装成填充边界。",
            "- 轴截距定义为从原点开始的连续稳定前缀终点；遇到首个不稳定格即停止，绝不跨孔洞取轴上最后稳定点。",
            "- 历史第二类 Craig–Bampton/Guyan 网格外的 `1..28` 是索引序列，不纳入共同网格稳定判断。",
            "- 结论 C07 的频带和幅值部分不在本步骤范围内；这里只登记临界时滞分量。",
            "",
            "## 生成器内部检查",
            "",
            f"- PASS: {check_summary['pass']}",
            f"- INFO: {check_summary['info']}",
            f"- FAIL: {check_summary['fail']}",
            "",
            "最终独立验证器另行核对两轮字节重复性、逐点结果、PDF/PNG质量和保护哈希。",
        ]
    )
    return "\n".join(lines)


def generate_output(
    contract: Mapping[str, Any], output_root: Path, checks: CheckBook
) -> None:
    expected_relpaths = expected_output_relpaths()
    prepare_output_root(
        output_root,
        expected_relpaths,
        RUN_OUTPUT_DIRECTORIES,
    )
    checks.require(
        "safe_regeneration",
        "Step6输出根在首个工件写入前通过固定目录树、无链接及可恢复提交状态检查",
        True,
        {
            "safe": True,
            "expected_nonmanifest_files": 25,
            "allowed_prior_states": [
                "ABSENT",
                "COMMITTED",
                "RECOVERABLE_UNCOMMITTED",
            ],
        },
        {
            "safe": True,
            "expected_nonmanifest_files": len(expected_relpaths),
        },
        "fixed Step6 run output root",
    )

    clean_receipt = verify_clean_probe_receipt(contract, checks)
    verify_input_bindings(contract, checks)
    verify_upstream_gate(contract, checks)
    verify_artifact_manifest("outputs/step1_artifact_manifest.csv", checks, "step1_manifest")
    verify_artifact_manifest("outputs/step4_audit/artifact_manifest.csv", checks, "step4_manifest")
    verify_artifact_manifest(
        "outputs/step5_fullq_svd_candidate_v4/full/artifact_manifest.csv",
        checks,
        "step5_manifest",
    )
    verify_artifact_manifest(
        "outputs/step5_fullq_svd_candidate_audit_v5_full/"
        "v5_full_validator_full_postcheck_artifact_manifest.csv",
        checks,
        "step5_v5_manifest",
    )

    historical_masks, historical_raw, boundary_rows, extension_rows = load_historical(
        contract, checks
    )
    validate_frozen_boundaries(contract, historical_masks, checks)
    route_data = {
        route["route_id"]: load_route_data(route, contract, checks)
        for route in contract["routes"]
    }
    tables = build_comparison_tables(
        contract,
        historical_masks,
        historical_raw,
        boundary_rows,
        extension_rows,
        route_data,
        checks,
    )
    write_tables(output_root, tables)

    configure_plot_style(contract)
    figure_paths: list[Path] = []
    style_rows: list[dict[str, Any]] = []
    for division in ["div1", "div2"]:
        paths, rows = historical_boundary_figure(
            division, historical_masks, contract, output_root
        )
        figure_paths.extend(paths)
        style_rows.extend(rows)
    paths, rows = computed_div1_figure(route_data, contract, output_root)
    figure_paths.extend(paths)
    style_rows.extend(rows)
    paths, rows = computed_div2_figure(route_data, contract, output_root)
    figure_paths.extend(paths)
    style_rows.extend(rows)
    for row in style_rows:
        row["font_family"] = contract["plot_style"]["font_family"]
        row["mathtext_fontset"] = contract["plot_style"]["mathtext_fontset"]
    write_csv(
        output_root / "figure_style_manifest.csv",
        list(style_rows[0].keys()),
        style_rows,
    )

    protected_rows = snapshot_protected_inputs(output_root)
    checks.require(
        "protected_inputs",
        "163项保护文件在Step6生成后仍与V5基线哈希相同",
        len(protected_rows) == 163 and all(row["unchanged"] for row in protected_rows),
        {"count": 163, "changed": []},
        {
            "count": len(protected_rows),
            "changed": [row["relpath"] for row in protected_rows if not row["unchanged"]],
        },
        "protected_input_hashes.csv",
    )
    checks.info(
        "object_gate",
        "图4-4与图4-5对象门按合同如实失败，不建立正式成功目录",
        {
            "figure_gate_pass": True,
            "formal_success_directory_allowed": True,
        },
        {
            "figure_gate_pass": False,
            "formal_success_directory_allowed": False,
            "reason": "missing Craig-Bampton continuous-rho routes and nonzero mask mismatches",
        },
        "tables/figure_status.csv",
    )
    check_summary = checks.summary()
    checks.require(
        "execution_integrity",
        "生成器内部无FAIL检查",
        check_summary["fail"] == 0,
        0,
        check_summary["fail"],
        "checks.csv",
    )
    check_summary = checks.summary()
    write_csv(output_root / "checks.csv", list(checks.rows[0].keys()), checks.rows)
    write_text(output_root / "report.md", comparison_report(tables, check_summary))
    run_summary = {
        "schema_version": "board20_step6_history_comparison_output_v1",
        "generator_sha256": sha256_file(SCRIPT_PATH),
        "fs_protocol_sha256": sha256_file(FS_PROTOCOL_PATH),
        "contract_sha256": sha256_file(CONTRACT_PATH),
        "clean_probe_action_id": clean_receipt["action_id"],
        "clean_probe_receipt_sha256": clean_receipt["sha256"],
        "execution_status": "PASS",
        "object_gate_status": "FAIL_RETAIN_PLOTTING_LEVEL",
        "pointwise_comparison_rows": len(tables["pointwise_comparison"]),
        "route_eligibility_rows": len(tables["route_eligibility"]),
        "target_cell_rows": len(tables["target_cell_status"]),
        "confusion_rows": len(tables["confusion_matrix"]),
        "boundary_rows": len(tables["boundary_by_source"]),
        "boundary_difference_rows": len(tables["boundary_difference"]),
        "extension_sequence_rows": len(tables["extension_1_to_28_audit"]),
        "figure_pdf_count": sum(path.suffix.lower() == ".pdf" for path in figure_paths),
        "figure_png_count": sum(path.suffix.lower() == ".png" for path in figure_paths),
        "check_summary": check_summary,
        "formal_success_directories_created": False,
        "next_step_started": False,
    }
    write_json(output_root / "run_summary.json", run_summary)
    actual_relpaths = {
        path.relative_to(output_root).as_posix()
        for path in output_root.rglob("*")
        if path.is_file() and path.name != "artifact_manifest.csv"
    }
    if actual_relpaths != expected_relpaths:
        raise RuntimeError(
            "Generated Step6 artifact set drifted: "
            f"delta={sorted(actual_relpaths ^ expected_relpaths)}"
        )
    manifest_rows = create_artifact_manifest(output_root)
    if len(manifest_rows) != len(expected_relpaths):
        raise RuntimeError(
            f"Unexpected artifact manifest count: {len(manifest_rows)}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Board20 Step6 deterministic historical-mask comparison generator"
    )
    parser.add_argument("--run-id", choices=["run1", "run2"], required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = read_json(CONTRACT_PATH)
    roots = validate_fixed_roots(BOARD_ROOT, contract["fixed_output_roots"])
    with ExclusiveFileLock(roots["logs"] / "step6_fs_protocol.lock"):
        roots = validate_fixed_roots(BOARD_ROOT, contract["fixed_output_roots"])
        output_root = roots[args.run_id]
        checks = CheckBook()
        generate_output(contract, output_root, checks)
    print(
        json.dumps(
            {
                "execution_status": "PASS",
                "object_gate_status": "FAIL_RETAIN_PLOTTING_LEVEL",
                "output_root": relative(output_root),
                "checks": checks.summary(),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from scipy.io import loadmat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent
INPUT_ROOT = BOARD_ROOT / "input"
OUTPUT_ROOT = BOARD_ROOT / "outputs"
IDENTITY_CSV = OUTPUT_ROOT / "mat_identity.csv"
ARRAY_HASH_CSV = OUTPUT_ROOT / "array_hashes.csv"
SUMMARY_JSON = OUTPUT_ROOT / "mat_identity.json"


RELEVANT_FILE_NAMES = {
    "lqr_2.mat",
    "lqr_3.mat",
    "origin_lqr_2.mat",
    "origin_lqr_3.mat",
    "guyan_lqr_2.mat",
    "guyan_lqr_3.mat",
    "CB_lqr_2.mat",
    "CB_lqr_3.mat",
    "cb_2.mat",
    "stab_2.mat",
    "stab_2_guyan.mat",
    "stab_guyan_lqr.mat",
    "stab_3.mat",
    "第一类划分最终绘图数据_lqr_2.mat",
    "第二类划分最终绘图数据_lqr_3.mat",
    "图4-4_第一类子结构划分稳定域_清洗数据.mat",
    "图4-5_第二类子结构划分稳定域_清洗数据.mat",
}

METHODS = {
    "原结构": ("stab_o", "original"),
    "Craig-Bampton": ("stab_C", "craig_bampton"),
    "Guyan": ("stab_g", "guyan"),
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def sha256_array(array: np.ndarray) -> str:
    data = np.asarray(array)
    header = json.dumps(
        {"dtype": data.dtype.str, "shape": list(data.shape), "order": "F"},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    payload = np.asfortranarray(data).tobytes(order="F")
    return hashlib.sha256(header + b"\0" + payload).hexdigest().upper()


def rel(path: Path) -> str:
    return path.resolve().relative_to(INPUT_ROOT.resolve()).as_posix()


def json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def load_numeric_mat(path: Path) -> dict[str, np.ndarray]:
    raw = loadmat(path, squeeze_me=False, struct_as_record=False)
    return {
        key: np.asarray(value)
        for key, value in raw.items()
        if not key.startswith("__")
    }


def numeric_stats(array: np.ndarray) -> dict[str, Any]:
    data = np.asarray(array)
    numeric = data.dtype.kind in "biufc"
    result: dict[str, Any] = {
        "dtype": str(data.dtype),
        "shape": list(data.shape),
        "ndim": int(data.ndim),
        "element_count": int(data.size),
        "is_numeric": bool(numeric),
        "array_sha256": sha256_array(data),
    }
    if not numeric:
        result.update(
            {
                "finite_count": "",
                "nan_count": "",
                "inf_count": "",
                "min_value": "",
                "max_value": "",
                "unique_count": "",
                "unique_preview": [],
                "zero_count": "",
                "positive_count": "",
                "between_zero_one_count": "",
                "less_than_one_count": "",
                "equal_0_999_count": "",
            }
        )
        return result

    values = np.abs(data) if np.iscomplexobj(data) else data.astype(float, copy=False)
    finite = np.isfinite(values)
    finite_values = values[finite]
    unique = np.unique(finite_values) if finite_values.size <= 2_000_000 else np.array([])
    preview = unique[:20].tolist()
    result.update(
        {
            "finite_count": int(finite.sum()),
            "nan_count": int(np.isnan(values).sum()),
            "inf_count": int(np.isinf(values).sum()),
            "min_value": float(np.min(finite_values)) if finite_values.size else "",
            "max_value": float(np.max(finite_values)) if finite_values.size else "",
            "unique_count": int(unique.size) if unique.size else "",
            "unique_preview": preview,
            "zero_count": int(np.count_nonzero(finite & (values == 0))),
            "positive_count": int(np.count_nonzero(finite & (values > 0))),
            "between_zero_one_count": int(
                np.count_nonzero(finite & (values > 0) & (values < 1))
            ),
            "less_than_one_count": int(np.count_nonzero(finite & (values < 1))),
            "equal_0_999_count": int(
                np.count_nonzero(finite & np.isclose(values, 0.999, rtol=0, atol=0))
            ),
        }
    )
    return result


def find_unique(paths: list[Path], *, fragment: str, name: str) -> Path:
    hits = [path for path in paths if fragment in rel(path) and path.name == name]
    if len(hits) != 1:
        raise RuntimeError(f"路径身份不唯一：fragment={fragment}; name={name}; hits={hits}")
    return hits[0]


def boundary(mask: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    plot_rows: list[tuple[int, int]] = []
    for column in range(mask.shape[1]):
        rows = np.flatnonzero(mask[:, column])
        if rows.size:
            plot_rows.append((column + 1, int(rows[-1] + 1)))
    plot_index = np.asarray(plot_rows, dtype=np.int32)
    steps = plot_index - 1
    milliseconds = steps.astype(float) * (1000.0 / 1024.0)
    return plot_index, steps, milliseconds


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def audit_chain(paths: list[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_fragment = "plotting_baseline/第4章_缩聚对试验稳定性的影响"
    source2 = find_unique(
        paths,
        fragment=baseline_fragment + "/原始来源副本",
        name="第一类划分最终绘图数据_lqr_2.mat",
    )
    source3 = find_unique(
        paths,
        fragment=baseline_fragment + "/原始来源副本",
        name="第二类划分最终绘图数据_lqr_3.mat",
    )
    cleaned2 = find_unique(
        paths,
        fragment=baseline_fragment + "/输入数据",
        name="图4-4_第一类子结构划分稳定域_清洗数据.mat",
    )
    cleaned3 = find_unique(
        paths,
        fragment=baseline_fragment + "/输入数据",
        name="图4-5_第二类子结构划分稳定域_清洗数据.mat",
    )
    data_root = cleaned2.parent
    boundary2_csv = data_root / "图4-4_第一类子结构划分稳定域_边界数据.csv"
    boundary3_csv = data_root / "图4-5_第二类子结构划分稳定域_边界数据.csv"
    stats_csv = data_root / "第4章稳定域统计.csv"
    for path in (boundary2_csv, boundary3_csv, stats_csv):
        if not path.is_file():
            raise FileNotFoundError(f"缺少冻结绘图链CSV：{path}")

    checks: list[dict[str, Any]] = []
    raw_by_division = {"4-4": load_numeric_mat(source2), "4-5": load_numeric_mat(source3)}
    clean_by_division = {"4-4": load_numeric_mat(cleaned2), "4-5": load_numeric_mat(cleaned3)}
    csv_by_division = {"4-4": read_csv(boundary2_csv), "4-5": read_csv(boundary3_csv)}
    stats_rows = read_csv(stats_csv)
    mask_cache: dict[str, dict[str, np.ndarray]] = {}

    for division_id in ("4-4", "4-5"):
        raw = raw_by_division[division_id]
        cleaned = clean_by_division[division_id]
        common_shape = tuple(int(v) for v in np.asarray(raw["stab_o"]).shape)
        expected_shape = tuple(int(v) for v in cleaned["common_grid_shape"].ravel())
        checks.append(
            {
                "check": f"{division_id}:共同网格",
                "expected": [31, 67],
                "actual": list(common_shape),
                "passed": common_shape == (31, 67) and expected_shape == common_shape,
            }
        )
        mask_cache[division_id] = {}
        for method, (raw_key, stem) in METHODS.items():
            values = np.asarray(raw[raw_key], dtype=float)
            cropped = values[: common_shape[0], : common_shape[1]]
            stable = np.isfinite(cropped) & (cropped > 0) & (cropped < 1)
            mask_cache[division_id][method] = stable
            stored_mask = np.asarray(cleaned[f"{stem}_stable_mask"], dtype=bool)
            plot_index, steps, milliseconds = boundary(stable)
            expected_arrays = {
                "stable_mask": (stored_mask, stable),
                "boundary_plot_index": (
                    np.asarray(cleaned[f"{stem}_boundary_plot_index"]),
                    plot_index,
                ),
                "boundary_delay_steps": (
                    np.asarray(cleaned[f"{stem}_boundary_delay_steps"]),
                    steps,
                ),
                "boundary_delay_ms": (
                    np.asarray(cleaned[f"{stem}_boundary_delay_ms"], dtype=float),
                    milliseconds,
                ),
            }
            for quantity, (stored, computed) in expected_arrays.items():
                equal = (
                    np.array_equal(stored, computed)
                    if quantity != "boundary_delay_ms"
                    else np.allclose(stored, computed, rtol=0, atol=5e-10)
                )
                checks.append(
                    {
                        "check": f"{division_id}:{method}:{quantity}",
                        "expected": "computed_from_raw_mask",
                        "actual": {
                            "stored_shape": list(stored.shape),
                            "computed_shape": list(computed.shape),
                        },
                        "passed": bool(equal),
                    }
                )

            csv_rows = [
                row
                for row in csv_by_division[division_id]
                if row.get("方法") == method
            ]
            csv_values = np.asarray(
                [
                    [
                        int(row["原图横坐标索引"]),
                        int(row["原图纵坐标索引"]),
                        int(row["时滞1采样步"]),
                        int(row["时滞2采样步"]),
                        float(row["时滞1毫秒"]),
                        float(row["时滞2毫秒"]),
                    ]
                    for row in csv_rows
                ],
                dtype=float,
            )
            expected_csv = np.column_stack([plot_index, steps, milliseconds])
            checks.append(
                {
                    "check": f"{division_id}:{method}:boundary_csv",
                    "expected": list(expected_csv.shape),
                    "actual": list(csv_values.shape),
                    "passed": bool(
                        csv_values.shape == expected_csv.shape
                        and np.allclose(csv_values, expected_csv, rtol=0, atol=5e-10)
                    ),
                }
            )
            stats_hit = [
                row
                for row in stats_rows
                if row.get("唯一ID") == division_id and row.get("方法") == method
            ]
            checks.append(
                {
                    "check": f"{division_id}:{method}:stable_count_stats_csv",
                    "expected": int(stable.sum()),
                    "actual": int(stats_hit[0]["稳定网格点数"]) if len(stats_hit) == 1 else None,
                    "passed": len(stats_hit) == 1
                    and int(stats_hit[0]["稳定网格点数"]) == int(stable.sum()),
                }
            )

    anomalies = {
        "stab_C_row36_cols68_95_is_1_to_28": bool(
            np.array_equal(raw_by_division["4-5"]["stab_C"][35, 67:95], np.arange(1, 29))
        ),
        "stab_g_row32_cols68_95_is_1_to_28": bool(
            np.array_equal(raw_by_division["4-5"]["stab_g"][31, 67:95], np.arange(1, 29))
        ),
    }
    for key in ("stab_C", "stab_g"):
        values = np.asarray(raw_by_division["4-5"][key], dtype=float)
        outside = np.ones(values.shape, dtype=bool)
        outside[:31, :67] = False
        anomalies[f"{key}_outside_common_grid_between_zero_one_count"] = int(
            np.count_nonzero(outside & (values > 0) & (values < 1))
        )
    anomalies_pass = (
        anomalies["stab_C_row36_cols68_95_is_1_to_28"]
        and anomalies["stab_g_row32_cols68_95_is_1_to_28"]
        and anomalies["stab_C_outside_common_grid_between_zero_one_count"] == 0
        and anomalies["stab_g_outside_common_grid_between_zero_one_count"] == 0
    )
    checks.append(
        {
            "check": "4-5:共同网格外异常序列",
            "expected": "两段1..28且共同网格外0<x<1点数均为0",
            "actual": anomalies,
            "passed": bool(anomalies_pass),
        }
    )
    return checks, {"anomalies": anomalies, "masks": mask_cache}


def main() -> int:
    if not INPUT_ROOT.is_dir():
        raise FileNotFoundError(f"冻结输入目录不存在：{INPUT_ROOT}")
    all_mat_paths = sorted(INPUT_ROOT.rglob("*.mat"), key=lambda path: rel(path).casefold())
    paths = [path for path in all_mat_paths if path.name in RELEVANT_FILE_NAMES]
    if len(paths) != 17:
        raise RuntimeError(f"相关MAT应为17份，实际{len(paths)}份：{[rel(p) for p in paths]}")

    identity_rows: list[dict[str, Any]] = []
    array_rows: list[dict[str, Any]] = []
    file_hash_groups: dict[str, list[str]] = defaultdict(list)
    array_hash_groups: dict[str, list[str]] = defaultdict(list)
    loaded: dict[str, dict[str, np.ndarray]] = {}
    for path in paths:
        relative = rel(path)
        file_hash = sha256_file(path)
        file_hash_groups[file_hash].append(relative)
        variables = load_numeric_mat(path)
        loaded[relative] = variables
        for variable, array in sorted(variables.items()):
            stats = numeric_stats(array)
            array_id = f"{relative}::{variable}"
            array_hash_groups[stats["array_sha256"]].append(array_id)
            row = {
                "frozen_relative_path": relative,
                "file_sha256": file_hash,
                "file_size_bytes": path.stat().st_size,
                "variable": variable,
                **stats,
            }
            row["shape"] = json_cell(row["shape"])
            row["unique_preview"] = json_cell(row["unique_preview"])
            identity_rows.append(row)
            array_rows.append(
                {
                    "array_id": array_id,
                    "array_sha256": stats["array_sha256"],
                    "dtype": stats["dtype"],
                    "shape": row["shape"],
                }
            )

    duplicate_file_groups = [
        {"sha256": digest, "count": len(members), "members": members}
        for digest, members in sorted(file_hash_groups.items())
        if len(members) > 1
    ]
    duplicate_array_groups = [
        {"sha256": digest, "count": len(members), "members": members}
        for digest, members in sorted(array_hash_groups.items())
        if len(members) > 1
    ]
    group_lookup: dict[str, tuple[str, int]] = {}
    for index, group in enumerate(duplicate_array_groups, start=1):
        group_id = f"DUP-A-{index:03d}"
        for member in group["members"]:
            group_lookup[member] = (group_id, int(group["count"]))
    for row in array_rows:
        group_id, count = group_lookup.get(row["array_id"], ("", 1))
        row["duplicate_group_id"] = group_id
        row["duplicate_group_count"] = count

    chain_checks, chain_context = audit_chain(paths)

    historical_plotting = "historical_plotting/作者绘图目录/"
    author_lqr2 = loaded[historical_plotting + "lqr_2.mat"]
    author_lqr3 = loaded[historical_plotting + "lqr_3.mat"]
    final_mask_summary = {
        "lqr_2": {
            key: {
                "shape": list(np.asarray(author_lqr2[key]).shape),
                "stable_points_0_lt_x_lt_1": int(
                    np.count_nonzero((author_lqr2[key] > 0) & (author_lqr2[key] < 1))
                ),
                "unique": np.unique(author_lqr2[key]).tolist(),
            }
            for key in ("stab_o", "stab_C", "stab_g")
        },
        "lqr_3": {
            key: {
                "shape": list(np.asarray(author_lqr3[key]).shape),
                "stable_points_common_31x67": int(
                    np.count_nonzero(
                        (author_lqr3[key][:31, :67] > 0)
                        & (author_lqr3[key][:31, :67] < 1)
                    )
                ),
                "min": float(np.min(author_lqr3[key])),
                "max": float(np.max(author_lqr3[key])),
            }
            for key in ("stab_o", "stab_C", "stab_g")
        },
    }

    candidate_ids = [
        "historical_plotting/作者绘图目录/origin_lqr_3.mat",
        "historical_plotting/作者绘图目录/guyan_lqr_3.mat",
        "historical_plotting/作者绘图目录/CB_lqr_2.mat",
        "historical_plotting/作者绘图目录/CB_lqr_3.mat",
    ]
    candidate_comparisons: list[dict[str, Any]] = []
    targets = {
        "4-4:stab_o": chain_context["masks"]["4-4"]["原结构"],
        "4-4:stab_C": chain_context["masks"]["4-4"]["Craig-Bampton"],
        "4-4:stab_g": chain_context["masks"]["4-4"]["Guyan"],
        "4-5:stab_o": chain_context["masks"]["4-5"]["原结构"],
        "4-5:stab_C": chain_context["masks"]["4-5"]["Craig-Bampton"],
        "4-5:stab_g": chain_context["masks"]["4-5"]["Guyan"],
    }
    for candidate_id in candidate_ids:
        values = np.asarray(loaded[candidate_id]["stab"], dtype=float)
        candidate_mask = np.isfinite(values) & (values > 0) & (values < 1)
        for target_id, target in targets.items():
            rows = min(candidate_mask.shape[0], target.shape[0])
            columns = min(candidate_mask.shape[1], target.shape[1])
            left = candidate_mask[:rows, :columns]
            right = target[:rows, :columns]
            mismatch = int(np.count_nonzero(left != right))
            candidate_comparisons.append(
                {
                    "candidate": candidate_id,
                    "target": target_id,
                    "comparison_shape": [rows, columns],
                    "mismatch_points": mismatch,
                    "match_fraction": float(1.0 - mismatch / (rows * columns)),
                    "scientific_status": "MISMATCH" if mismatch else "EXACT_MATCH",
                }
            )

    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    identity_fields = list(identity_rows[0].keys())
    with IDENTITY_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=identity_fields)
        writer.writeheader()
        writer.writerows(identity_rows)
    array_fields = list(array_rows[0].keys())
    with ARRAY_HASH_CSV.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=array_fields)
        writer.writeheader()
        writer.writerows(array_rows)

    failed_checks = [check for check in chain_checks if not check["passed"]]
    summary = {
        "schema": "board20_mat_identity_v1",
        "created_at": datetime.now().astimezone().isoformat(),
        "input_boundary": "frozen input only",
        "relevant_mat_count": len(paths),
        "variable_count": len(identity_rows),
        "duplicate_file_groups": duplicate_file_groups,
        "duplicate_array_groups": duplicate_array_groups,
        "final_mask_summary": final_mask_summary,
        "plotting_chain_checks": chain_checks,
        "plotting_chain_passed": len(chain_checks) - len(failed_checks),
        "plotting_chain_checked": len(chain_checks),
        "anomalies": chain_context["anomalies"],
        "continuous_candidate_comparisons": candidate_comparisons,
        "minimum_continuous_candidate_mismatch_points": min(
            item["mismatch_points"] for item in candidate_comparisons
        ),
        "status": "PASS" if not failed_checks else "FAIL",
    }
    SUMMARY_JSON.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"MAT_IDENTITY_{summary['status']} mats={len(paths)} variables={len(identity_rows)} "
        f"plotting_chain={summary['plotting_chain_passed']}/{summary['plotting_chain_checked']} "
        f"min_candidate_mismatch={summary['minimum_continuous_candidate_mismatch_points']}"
    )
    print(f"CSV={IDENTITY_CSV}")
    print(f"ARRAY_HASHES={ARRAY_HASH_CSV}")
    print(f"JSON={SUMMARY_JSON}")
    return 0 if not failed_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())

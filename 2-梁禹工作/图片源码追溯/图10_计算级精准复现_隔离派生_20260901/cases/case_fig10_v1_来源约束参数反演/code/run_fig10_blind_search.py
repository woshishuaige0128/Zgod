#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""图10盲算调度器：动态算子合同、固定哨兵、固定稀疏条带和全网格。

本程序只根据清单中的数值算子和固定点集计算谱半径。它不导入
评估器，不根据外部曲线改动点集。
"""

from __future__ import annotations

import os

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import argparse
import csv
import hashlib
import json
import math
import re
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

import fig10_blind_core as core


SCRIPT = Path(__file__).resolve()
MANIFEST_SCHEMA = "FIG10_BLIND_SEARCH_MANIFEST_V1"
RUN_SCHEMA = "FIG10_BLIND_SEARCH_RUN_V1"
MODES = ("sentinel", "sparse-band", "full-grid")
ROUTE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
SHA256_PATTERN = re.compile(r"^[0-9A-Fa-f]{64}$")

POINT_FIELDS = (
    "route_id",
    "contract_id",
    "division",
    "method",
    "mode",
    "point_order",
    "l_samples",
    "j_samples",
    "physical_root_count",
    "rho",
    "dominant_root_real",
    "dominant_root_imag",
    "stable",
    "critical",
    "stability_code",
    "stability_status",
    "maximum_state_eigenpair_residual",
    "transition_reconstruction_relative_error",
    "overall_pass",
)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise core.BlindContractError(message)


def canonical_json_bytes(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def payload_sha256(payload: Any) -> str:
    return hashlib.sha256(canonical_json_bytes(payload)).hexdigest().upper()


def atomic_write_bytes(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_json(path: Path, payload: Any) -> None:
    body = json.dumps(
        payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False
    ) + "\n"
    atomic_write_bytes(path, body.encode("utf-8"))


def csv_value(value: Any) -> Any:
    if isinstance(value, (float, np.floating)):
        return format(float(value), ".17g")
    if isinstance(value, np.integer):
        return int(value)
    return value


def atomic_write_csv(
    path: Path, fieldnames: Sequence[str], rows: Iterable[Mapping[str, Any]]
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8-sig",
        newline="",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            for row in rows:
                writer.writerow({name: csv_value(row.get(name, "")) for name in fieldnames})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_binary_matrix(path: Path, matrix: np.ndarray) -> None:
    require(matrix.ndim == 2, "稳定掩膜必须是二维矩阵")
    require(np.all((matrix == 0) | (matrix == 1)), "稳定掩膜必须只含0/1")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="ascii",
        newline="",
        prefix=f".{path.name}.",
        suffix=".tmp",
        dir=path.parent,
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerows(matrix.astype(np.uint8).tolist())
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    require(isinstance(payload, dict), f"JSON顶层必须是对象：{path}")
    return payload


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def resolve_from(base: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (base / path).resolve()


def is_under(path: Path, roots: Sequence[Path]) -> bool:
    return any(path == root or path.is_relative_to(root) for root in roots)


def parse_axis(config: Mapping[str, Any], name: str) -> tuple[int, ...]:
    list_key = f"{name}_values"
    if list_key in config:
        raw = config[list_key]
        require(isinstance(raw, list) and raw, f"grid.{list_key}必须是非空列表")
        values = tuple(int(value) for value in raw)
    else:
        minimum = int(config[f"{name}_min"])
        maximum = int(config[f"{name}_max"])
        step = int(config.get(f"{name}_step", 1))
        require(step > 0 and maximum >= minimum >= 0, f"grid.{name}范围非法")
        values = tuple(range(minimum, maximum + 1, step))
    require(all(isinstance(value, int) and value >= 0 for value in values), f"grid.{name}必须非负")
    require(tuple(sorted(set(values))) == values, f"grid.{name}必须严格升序且无重复")
    return values


def parse_points(raw: Any, label: str) -> tuple[tuple[int, int], ...]:
    require(isinstance(raw, list) and raw, f"{label}必须是非空列表")
    points = []
    for index, item in enumerate(raw):
        require(isinstance(item, list) and len(item) == 2, f"{label}[{index}]必须是[l,j]")
        l_samples, j_samples = int(item[0]), int(item[1])
        require(l_samples >= 0 and j_samples >= 0, f"{label}[{index}]包含负延迟")
        points.append((l_samples, j_samples))
    require(len(points) == len(set(points)), f"{label}包含重复点")
    return tuple(points)


def route_sampling(route: Mapping[str, Any], manifest: Mapping[str, Any]) -> Mapping[str, Any]:
    sampling = route.get("sampling", manifest.get("sampling"))
    require(isinstance(sampling, dict), f"{route['route_id']}缺少sampling合同")
    return sampling


def select_points(
    route: Mapping[str, Any], manifest: Mapping[str, Any], mode: str
) -> tuple[tuple[int, int], ...]:
    sampling = route_sampling(route, manifest)
    grid = sampling.get("grid")
    require(isinstance(grid, dict), f"{route['route_id']}缺少sampling.grid")
    l_values = parse_axis(grid, "l")
    j_values = parse_axis(grid, "j")
    if mode == "full-grid":
        points = tuple((l_samples, j_samples) for l_samples in l_values for j_samples in j_values)
    elif mode == "sentinel":
        points = parse_points(sampling.get("sentinel_points"), "sampling.sentinel_points")
    else:
        points = parse_points(
            sampling.get("fixed_sparse_band_points"), "sampling.fixed_sparse_band_points"
        )
    allowed_l, allowed_j = set(l_values), set(j_values)
    require(
        all(l_samples in allowed_l and j_samples in allowed_j for l_samples, j_samples in points),
        f"{route['route_id']} {mode}点超出sampling.grid",
    )
    return points


def validate_route_entry(route: Mapping[str, Any]) -> None:
    required = (
        "route_id",
        "contract_id",
        "contract_hash",
        "division",
        "method",
        "dimension",
        "operator_layout",
        "bundle_path",
        "bundle_sha256",
    )
    for key in required:
        require(key in route, f"路线条目缺少 {key}")
    require(ROUTE_ID_PATTERN.fullmatch(str(route["route_id"])) is not None, "route_id不安全")
    require(SHA256_PATTERN.fullmatch(str(route["contract_hash"])) is not None, "contract_hash不是SHA-256")
    require(SHA256_PATTERN.fullmatch(str(route["bundle_sha256"])) is not None, "bundle_sha256不是SHA-256")
    require(int(route["division"]) in (1, 2), "division必须是1或2")
    require(int(route["dimension"]) > 0, "dimension必须大于0")
    require(str(route["operator_layout"]) in core.SUPPORTED_LAYOUTS, "operator_layout不支持")


def load_manifest(path: Path) -> tuple[dict[str, Any], str, list[Path]]:
    path = path.resolve()
    manifest = read_json(path)
    require(manifest.get("schema_version") == MANIFEST_SCHEMA, "盲算清单schema_version错误")
    roots_raw = manifest.get("allowed_bundle_roots")
    require(isinstance(roots_raw, list) and roots_raw, "allowed_bundle_roots必须是非空列表")
    roots = [resolve_from(path.parent, str(value)) for value in roots_raw]
    routes = manifest.get("routes")
    require(isinstance(routes, list) and routes, "routes必须是非空列表")
    route_ids = []
    for route in routes:
        require(isinstance(route, dict), "routes元素必须是对象")
        validate_route_entry(route)
        route_ids.append(str(route["route_id"]))
        bundle_path = resolve_from(path.parent, str(route["bundle_path"]))
        require(is_under(bundle_path, roots), f"{route['route_id']}算子包超出allowed_bundle_roots")
        core.assert_operator_input_path(bundle_path)
    require(len(route_ids) == len(set(route_ids)), "route_id重复")
    return manifest, core.sha256_file(path), roots


def route_fingerprint(route: Mapping[str, Any], mode: str, points: Sequence[tuple[int, int]]) -> str:
    return payload_sha256(
        {
            "route_id": route["route_id"],
            "contract_id": route["contract_id"],
            "contract_hash": str(route["contract_hash"]).upper(),
            "bundle_sha256": str(route["bundle_sha256"]).upper(),
            "operator_layout": route["operator_layout"],
            "dimension": int(route["dimension"]),
            "mode": mode,
            "points": [list(point) for point in points],
        }
    )


def validate_result_prefix(
    rows: Sequence[Mapping[str, str]],
    route: Mapping[str, Any],
    mode: str,
    points: Sequence[tuple[int, int]],
) -> None:
    require(len(rows) <= len(points), "已有结果超过固定点数")
    for index, row in enumerate(rows):
        require(row["route_id"] == str(route["route_id"]), "恢复CSV route_id不符")
        require(row["contract_id"] == str(route["contract_id"]), "恢复CSV contract_id不符")
        require(row["mode"] == mode, "恢复CSV mode不符")
        require(int(row["point_order"]) == index + 1, "恢复CSV point_order不连续")
        require(
            (int(row["l_samples"]), int(row["j_samples"])) == points[index],
            "恢复CSV不是固定点集前缀",
        )


def checkpoint_payload(
    *,
    status: str,
    manifest_sha256: str,
    route: Mapping[str, Any],
    mode: str,
    points: Sequence[tuple[int, int]],
    rows: Sequence[Mapping[str, Any]],
    results_path: Path,
    error: str | None = None,
) -> dict[str, Any]:
    payload = {
        "schema_version": RUN_SCHEMA,
        "status": status,
        "manifest_sha256": manifest_sha256,
        "route_id": route["route_id"],
        "contract_id": route["contract_id"],
        "contract_hash": str(route["contract_hash"]).upper(),
        "bundle_sha256": str(route["bundle_sha256"]).upper(),
        "mode": mode,
        "route_fingerprint": route_fingerprint(route, mode, points),
        "point_selection_sha256": payload_sha256([list(point) for point in points]),
        "total_point_count": len(points),
        "completed_point_count": len(rows),
        "next_point_index": len(rows),
        "results_csv": str(results_path),
        "results_csv_sha256": core.sha256_file(results_path) if results_path.is_file() else None,
        "error": error,
    }
    return payload


def load_resume_rows(
    checkpoint_path: Path,
    results_path: Path,
    manifest_sha256: str,
    route: Mapping[str, Any],
    mode: str,
    points: Sequence[tuple[int, int]],
) -> list[dict[str, str]]:
    checkpoint = read_json(checkpoint_path)
    expected = route_fingerprint(route, mode, points)
    require(checkpoint.get("manifest_sha256") == manifest_sha256, "检查点manifest哈希不符")
    require(checkpoint.get("route_fingerprint") == expected, "检查点路线指纹不符")
    require(results_path.is_file(), "恢复时缺少逐点CSV")
    rows = read_csv(results_path)
    validate_result_prefix(rows, route, mode, points)
    checkpoint_count = int(checkpoint.get("completed_point_count", -1))
    require(len(rows) >= checkpoint_count >= 0, "逐点CSV比检查点更短")
    if len(rows) == checkpoint_count:
        require(
            checkpoint.get("results_csv_sha256") == core.sha256_file(results_path),
            "检查点逐点CSV哈希不符",
        )
    return rows


def result_row(
    route: Mapping[str, Any], mode: str, point_order: int, l_samples: int, j_samples: int,
    result: core.BlindSolveResult,
) -> dict[str, Any]:
    return {
        "route_id": route["route_id"],
        "contract_id": route["contract_id"],
        "division": int(route["division"]),
        "method": route["method"],
        "mode": mode,
        "point_order": point_order,
        "l_samples": l_samples,
        "j_samples": j_samples,
        "physical_root_count": result.roots.size,
        "rho": result.rho,
        "dominant_root_real": result.dominant_root.real,
        "dominant_root_imag": result.dominant_root.imag,
        "stable": result.stable,
        "critical": result.critical,
        "stability_code": result.stability_code,
        "stability_status": result.stability_status,
        "maximum_state_eigenpair_residual": float(np.max(result.state_residuals)),
        "transition_reconstruction_relative_error": result.transition_reconstruction_relative_error,
        "overall_pass": 1,
    }


def write_full_grid_mask(
    route_dir: Path,
    route: Mapping[str, Any],
    manifest: Mapping[str, Any],
    rows: Sequence[Mapping[str, Any]],
) -> None:
    sampling = route_sampling(route, manifest)
    grid = sampling["grid"]
    l_values = parse_axis(grid, "l")
    j_values = parse_axis(grid, "j")
    require(len(rows) == len(l_values) * len(j_values), "全网格行数不闭合")
    matrix = np.empty((len(l_values), len(j_values)), dtype=np.uint8)
    for row in rows:
        l_index = l_values.index(int(row["l_samples"]))
        j_index = j_values.index(int(row["j_samples"]))
        matrix[l_index, j_index] = int(row["stable"])
    atomic_write_binary_matrix(route_dir / "stable_mask.csv", matrix)
    atomic_write_json(
        route_dir / "grid_axes.json",
        {
            "schema_version": RUN_SCHEMA,
            "row_axis": "l_samples",
            "column_axis": "j_samples",
            "l_values": list(l_values),
            "j_values": list(j_values),
            "mask_shape": list(matrix.shape),
            "stable_rule": "rho < 1.0",
        },
    )


def summarize_route(
    route: Mapping[str, Any], mode: str, rows: Sequence[Mapping[str, Any]], bundle: core.BlindBundle
) -> dict[str, Any]:
    rho = np.asarray([float(row["rho"]) for row in rows], dtype=np.float64)
    residual = np.asarray(
        [float(row["maximum_state_eigenpair_residual"]) for row in rows], dtype=np.float64
    )
    return {
        "schema_version": RUN_SCHEMA,
        "status": "PASS",
        "route_id": route["route_id"],
        "contract_id": route["contract_id"],
        "contract_hash": str(route["contract_hash"]).upper(),
        "mode": mode,
        "point_count": len(rows),
        "stable_point_count": sum(int(row["stable"]) for row in rows),
        "critical_point_count": sum(int(row["critical"]) for row in rows),
        "minimum_rho": float(np.min(rho)),
        "maximum_rho": float(np.max(rho)),
        "maximum_state_eigenpair_residual": float(np.max(residual)),
        "bundle": core.operator_summary(bundle),
    }


def run_route(
    *,
    manifest: Mapping[str, Any],
    manifest_path: Path,
    manifest_sha256: str,
    route: Mapping[str, Any],
    mode: str,
    output_root: Path,
    resume: bool,
    checkpoint_every: int,
) -> dict[str, Any]:
    points = select_points(route, manifest, mode)
    route_dir = output_root / "routes" / str(route["route_id"]) / mode
    results_path = route_dir / "points.csv"
    checkpoint_path = route_dir / "checkpoint.json"
    route_summary_path = route_dir / "route_summary.json"
    if checkpoint_path.exists() or results_path.exists():
        require(resume, f"{route['route_id']}/{mode}已有工件，必须显式--resume")
        require(checkpoint_path.is_file() and results_path.is_file(), "检查点与逐点CSV不成对")
        rows: list[dict[str, Any]] = list(
            load_resume_rows(
                checkpoint_path, results_path, manifest_sha256, route, mode, points
            )
        )
    else:
        rows = []

    bundle_path = resolve_from(manifest_path.parent, str(route["bundle_path"]))
    bundle = core.load_blind_bundle(bundle_path, route)
    try:
        for point_index in range(len(rows), len(points)):
            l_samples, j_samples = points[point_index]
            solved = core.solve_minimal_point(bundle, l_samples, j_samples)
            require(
                solved.roots.size == core.expected_root_count(bundle, l_samples, j_samples),
                "物理根数不闭合",
            )
            rows.append(result_row(route, mode, point_index + 1, l_samples, j_samples, solved))
            if len(rows) % checkpoint_every == 0 or len(rows) == len(points):
                atomic_write_csv(results_path, POINT_FIELDS, rows)
                atomic_write_json(
                    checkpoint_path,
                    checkpoint_payload(
                        status="COMPLETE" if len(rows) == len(points) else "IN_PROGRESS",
                        manifest_sha256=manifest_sha256,
                        route=route,
                        mode=mode,
                        points=points,
                        rows=rows,
                        results_path=results_path,
                    ),
                )
    except Exception as exc:
        if rows:
            atomic_write_csv(results_path, POINT_FIELDS, rows)
        atomic_write_json(
            checkpoint_path,
            checkpoint_payload(
                status="ERROR",
                manifest_sha256=manifest_sha256,
                route=route,
                mode=mode,
                points=points,
                rows=rows,
                results_path=results_path,
                error=f"{type(exc).__name__}: {exc}",
            ),
        )
        raise

    validate_result_prefix(rows, route, mode, points)
    if mode == "full-grid":
        write_full_grid_mask(route_dir, route, manifest, rows)
    summary = summarize_route(route, mode, rows, bundle)
    atomic_write_json(route_summary_path, summary)
    return summary


def write_hash_manifest(
    output_root: Path,
    manifest_path: Path,
    routes: Sequence[Mapping[str, Any]],
) -> Path:
    hash_path = output_root / "artifact_hash_manifest.csv"
    rows: list[dict[str, Any]] = []
    seen: set[Path] = set()

    def append(role: str, path: Path) -> None:
        resolved = path.resolve()
        if resolved in seen:
            return
        require(resolved.is_file(), f"哈希清单工件不存在：{resolved}")
        seen.add(resolved)
        rows.append(
            {
                "role": role,
                "path": str(resolved),
                "bytes": resolved.stat().st_size,
                "sha256": core.sha256_file(resolved),
            }
        )

    append("code", SCRIPT)
    append("code", Path(core.__file__))
    append("input_manifest", manifest_path)
    for route in routes:
        append("operator_bundle", resolve_from(manifest_path.parent, str(route["bundle_path"])))
    for path in sorted(output_root.rglob("*")):
        if path.is_file() and path.resolve() != hash_path.resolve():
            append("output", path)
    atomic_write_csv(hash_path, ("role", "path", "bytes", "sha256"), rows)
    return hash_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--route-id", action="append", default=[], help="可重复；缺省运行清单全部路线")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--checkpoint-every", type=int, default=25)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_root = args.output_dir.resolve()
    try:
        require(args.checkpoint_every > 0, "--checkpoint-every必须大于0")
        manifest_path = args.manifest.resolve()
        manifest, manifest_sha256, _ = load_manifest(manifest_path)
        all_routes = list(manifest["routes"])
        if args.route_id:
            requested = set(args.route_id)
            known = {str(route["route_id"]) for route in all_routes}
            require(requested <= known, f"未知route-id：{sorted(requested - known)}")
            routes = [route for route in all_routes if str(route["route_id"]) in requested]
        else:
            routes = all_routes
        require(routes, "未选中任何路线")
        summaries = []
        for route in routes:
            summaries.append(
                run_route(
                    manifest=manifest,
                    manifest_path=manifest_path,
                    manifest_sha256=manifest_sha256,
                    route=route,
                    mode=args.mode,
                    output_root=output_root,
                    resume=args.resume,
                    checkpoint_every=args.checkpoint_every,
                )
            )
        run_summary = {
            "schema_version": RUN_SCHEMA,
            "status": "PASS",
            "blind_calculation_only": True,
            "mode": args.mode,
            "manifest_path": str(manifest_path),
            "manifest_sha256": manifest_sha256,
            "route_count": len(routes),
            "point_count": sum(int(summary["point_count"]) for summary in summaries),
            "route_summaries": summaries,
            "resume_requested": args.resume,
        }
        atomic_write_json(output_root / "run_summary.json", run_summary)
        hash_path = write_hash_manifest(output_root, manifest_path, routes)
        print(
            json.dumps(
                {
                    "status": "PASS",
                    "mode": args.mode,
                    "route_count": len(routes),
                    "point_count": run_summary["point_count"],
                    "hash_manifest": str(hash_path),
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0
    except Exception as exc:
        error = {
            "schema_version": RUN_SCHEMA,
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }
        try:
            atomic_write_json(output_root / "run_error.json", error)
        except Exception:
            pass
        print(json.dumps(error, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

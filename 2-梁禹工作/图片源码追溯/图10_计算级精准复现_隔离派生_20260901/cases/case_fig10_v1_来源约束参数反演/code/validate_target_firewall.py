#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""静态+临时目录动态验证图10盲算代码的目标防火墙。"""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import numpy as np


SCRIPT = Path(__file__).resolve()
CODE_DIR = SCRIPT.parent
CORE_PATH = CODE_DIR / "fig10_blind_core.py"
RUNNER_PATH = CODE_DIR / "run_fig10_blind_search.py"
VALIDATION_SCHEMA = "FIG10_TARGET_FIREWALL_VALIDATION_V1"
FORBIDDEN_EXACT_LITERALS = (
    "plotted_data.mat",
    "fig10_stability_domain.pdf",
    "target_boundary.csv",
)
FORBIDDEN_IMPORT_PREFIXES = (
    "strict_target_evaluator",
    "fitz",
    "pdfplumber",
    "pypdf",
    "PyPDF2",
    "matplotlib",
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_csv(path: Path, fieldnames: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def collect_static_evidence(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text, filename=str(path))
    imports: list[str] = []
    open_calls: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            imports.append(node.module or "")
        elif isinstance(node, ast.Call):
            function_name = ""
            if isinstance(node.func, ast.Name):
                function_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                function_name = node.func.attr
            if function_name in {"open", "loadmat", "load", "read_text", "read_bytes"}:
                open_calls.append({"line": node.lineno, "function": function_name})
    forbidden_imports = sorted(
        name
        for name in imports
        if any(name == prefix or name.startswith(prefix + ".") for prefix in FORBIDDEN_IMPORT_PREFIXES)
    )
    literal_hits = sorted(literal for literal in FORBIDDEN_EXACT_LITERALS if literal in text.lower())
    return {
        "path": str(path),
        "sha256": sha256(path),
        "imports": sorted(set(imports)),
        "forbidden_imports": forbidden_imports,
        "forbidden_exact_literal_hits": literal_hits,
        "file_access_calls": open_calls,
        "pass": not forbidden_imports and not literal_hits,
    }


def make_synthetic_bundle(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        path,
        dimension=np.asarray([1], dtype=np.int64),
        dt=np.asarray([1.0 / 1024.0], dtype=np.float64),
        mass_term=np.asarray([[1.0]], dtype=np.float64),
        base_zero=np.asarray([[-0.5]], dtype=np.float64),
        base_minus_one=np.asarray([[0.06]], dtype=np.float64),
        delay_left=np.zeros((1, 2), dtype=np.float64),
        delay_v_zero=np.zeros((2, 1), dtype=np.float64),
        delay_v_minus_one=np.zeros((2, 1), dtype=np.float64),
        register_scales=np.ones(2, dtype=np.float64),
        shared_left_factor_relative_error=np.asarray([0.0], dtype=np.float64),
    )


def manifest_payload(bundle_path: Path, allowed_root: Path) -> dict[str, Any]:
    return {
        "schema_version": "FIG10_BLIND_SEARCH_MANIFEST_V1",
        "run_id": "FIREWALL_SYNTHETIC",
        "allowed_bundle_roots": [str(allowed_root)],
        "sampling": {
            "grid": {"l_min": 0, "l_max": 2, "j_min": 0, "j_max": 3},
            "sentinel_points": [[0, 0], [2, 3]],
            "fixed_sparse_band_points": [[0, 1], [1, 2], [2, 2]],
        },
        "routes": [
            {
                "route_id": "synthetic_route",
                "contract_id": "SYNTHETIC_CORE_CONTRACT",
                "contract_hash": hashlib.sha256(b"synthetic-contract").hexdigest().upper(),
                "division": 1,
                "method": "Synthetic",
                "dimension": 1,
                "operator_layout": "MINIMAL_AUGMENTED_CORE_V1",
                "bundle_path": str(bundle_path),
                "bundle_sha256": sha256(bundle_path),
            }
        ],
    }


def sitecustomize_text() -> str:
    return r'''import json
import os
import sys
from pathlib import Path

DENIED = {str(Path(value).resolve()).lower() for value in json.loads(os.environ["FIG10_FIREWALL_DENIED_PATHS"])}
LOG = Path(os.environ["FIG10_FIREWALL_AUDIT_LOG"])
ACTIVE = False

def record(payload):
    global ACTIVE
    if ACTIVE:
        return
    ACTIVE = True
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(payload, ensure_ascii=False) + "\n")
    finally:
        ACTIVE = False

def hook(event, args):
    if event != "open" or ACTIVE or not args:
        return
    raw = args[0]
    if not isinstance(raw, (str, bytes, os.PathLike)):
        return
    try:
        resolved = str(Path(os.fsdecode(raw)).resolve())
    except Exception:
        return
    lowered = resolved.lower()
    suffix = Path(resolved).suffix.lower()
    if lowered in DENIED:
        record({"event": "DENIED_ATTEMPT", "path": resolved, "mode": str(args[1] if len(args) > 1 else "")})
        raise PermissionError("FIG10_FIREWALL_DENIED_READ")
    if suffix in {".mat", ".csv", ".pdf"}:
        record({"event": "SENSITIVE_SUFFIX_OPEN", "path": resolved, "mode": str(args[1] if len(args) > 1 else "")})

sys.addaudithook(hook)
'''


def run_child(
    python_executable: Path,
    runner_path: Path,
    manifest_path: Path,
    output_dir: Path,
    hook_dir: Path,
    denied_paths: list[Path],
    audit_log: Path,
) -> dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(hook_dir)
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PYTHONIOENCODING"] = "utf-8"
    environment["FIG10_FIREWALL_DENIED_PATHS"] = json.dumps([str(path) for path in denied_paths])
    environment["FIG10_FIREWALL_AUDIT_LOG"] = str(audit_log)
    command = [
        str(python_executable),
        str(runner_path),
        "--manifest",
        str(manifest_path),
        "--output-dir",
        str(output_dir),
        "--mode",
        "sentinel",
        "--checkpoint-every",
        "1",
    ]
    process = subprocess.run(
        command,
        cwd=runner_path.parent,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    return {
        "command": command,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def read_audit(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dynamic_validation(work_root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    code_copy = work_root / "code"
    hook_dir = work_root / "audit_hook"
    bundle_root = work_root / "operator_bundles"
    decoy_root = work_root / "decoy_inputs"
    code_copy.mkdir(parents=True, exist_ok=True)
    hook_dir.mkdir(parents=True, exist_ok=True)
    decoy_root.mkdir(parents=True, exist_ok=True)
    copied_core = code_copy / CORE_PATH.name
    copied_runner = code_copy / RUNNER_PATH.name
    shutil.copy2(CORE_PATH, copied_core)
    shutil.copy2(RUNNER_PATH, copied_runner)
    (hook_dir / "sitecustomize.py").write_text(sitecustomize_text(), encoding="utf-8")

    bundle_path = bundle_root / "synthetic_operator_bundle.npz"
    make_synthetic_bundle(bundle_path)
    good_manifest = work_root / "good_manifest.json"
    write_json(good_manifest, manifest_payload(bundle_path, bundle_root))

    decoys = [
        decoy_root / "plotted_data.mat",
        decoy_root / "target_boundary.csv",
        decoy_root / "fig10_stability_domain.pdf",
    ]
    for index, path in enumerate(decoys, start=1):
        path.write_bytes(f"DECOY-{index}".encode("ascii"))
    before_hashes = {str(path): sha256(path) for path in decoys}

    audit_log = work_root / "audit_events.jsonl"
    good_run = run_child(
        Path(sys.executable),
        copied_runner,
        good_manifest,
        work_root / "good_run_output",
        hook_dir,
        decoys,
        audit_log,
    )

    malicious_runs = []
    for index, decoy in enumerate(decoys, start=1):
        malicious = manifest_payload(bundle_path, decoy_root)
        route = malicious["routes"][0]
        route["bundle_path"] = str(decoy)
        route["bundle_sha256"] = sha256(decoy)
        malicious_manifest = work_root / f"malicious_{index}.json"
        write_json(malicious_manifest, malicious)
        malicious_runs.append(
            run_child(
                Path(sys.executable),
                copied_runner,
                malicious_manifest,
                work_root / f"malicious_{index}_output",
                hook_dir,
                decoys,
                audit_log,
            )
        )

    events = read_audit(audit_log)
    after_hashes = {str(path): sha256(path) for path in decoys}
    good_summary_path = work_root / "good_run_output" / "run_summary.json"
    good_summary = json.loads(good_summary_path.read_text(encoding="utf-8")) if good_summary_path.is_file() else {}
    checks = {
        "good_synthetic_run_passed": good_run["returncode"] == 0 and good_summary.get("status") == "PASS",
        "good_synthetic_point_count_two": good_summary.get("point_count") == 2,
        "all_three_malicious_paths_rejected": all(run["returncode"] != 0 for run in malicious_runs),
        "no_denied_file_open_attempt_reached_os": not any(
            event.get("event") == "DENIED_ATTEMPT" for event in events
        ),
        "decoy_hashes_unchanged": before_hashes == after_hashes,
        "copied_code_hashes_match": sha256(copied_core) == sha256(CORE_PATH)
        and sha256(copied_runner) == sha256(RUNNER_PATH),
    }
    result = {
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "good_run": good_run,
        "malicious_runs": malicious_runs,
        "decoy_hashes_before": before_hashes,
        "decoy_hashes_after": after_hashes,
        "audit_event_count": len(events),
        "denied_attempt_count": sum(event.get("event") == "DENIED_ATTEMPT" for event in events),
        "temporary_work_root": str(work_root),
    }
    return result, events


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = args.output_dir.resolve()
    static = [collect_static_evidence(CORE_PATH), collect_static_evidence(RUNNER_PATH)]
    with tempfile.TemporaryDirectory(prefix="fig10_firewall_") as temporary:
        dynamic, events = dynamic_validation(Path(temporary))
    checks = {
        "static_blind_files_pass": all(item["pass"] for item in static),
        "dynamic_temporary_directory_pass": dynamic["status"] == "PASS",
    }
    summary = {
        "schema_version": VALIDATION_SCHEMA,
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "static_evidence": static,
        "dynamic_evidence": dynamic,
        "validator_path": str(SCRIPT),
        "validator_sha256": sha256(SCRIPT),
    }
    write_json(output_dir / "target_firewall_summary.json", summary)
    write_csv(
        output_dir / "target_firewall_audit_events.csv",
        ("event", "path", "mode"),
        [
            {"event": event.get("event", ""), "path": event.get("path", ""), "mode": event.get("mode", "")}
            for event in events
        ],
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())

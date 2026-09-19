from __future__ import annotations

import argparse
import json
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from board20_step6_fs_protocol import (
    ExclusiveFileLock,
    atomic_write_bytes,
    classify_output,
    lexical_exists,
    sha256_file,
    strict_inventory,
    validate_fixed_roots,
)


SCRIPT_PATH = Path(__file__).resolve()
CODE_ROOT = SCRIPT_PATH.parent
BOARD_ROOT = CODE_ROOT.parent
CONTRACT_PATH = CODE_ROOT / "board20_step6_history_comparison_contract.json"
FS_PROTOCOL_PATH = CODE_ROOT / "board20_step6_fs_protocol.py"
RUN_DIRECTORIES = {"figures", "tables"}
VALIDATION_DIRECTORIES = {"rendered_pdf_review"}
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


def strict_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_contract() -> dict[str, Any]:
    return json.loads(
        CONTRACT_PATH.read_text(encoding="utf-8"),
        object_pairs_hook=strict_object,
    )


def run_files() -> set[str]:
    result = {f"tables/{name}.csv" for name in TABLE_NAMES}
    for stem in FIGURE_STEMS:
        result.add(f"figures/{stem}.pdf")
        result.add(f"figures/{stem}.png")
    result.update(
        {
            "checks.csv",
            "figure_style_manifest.csv",
            "protected_input_hashes.csv",
            "report.md",
            "run_summary.json",
        }
    )
    if len(result) != 25:
        raise RuntimeError(f"Run artifact specification drifted: {len(result)}")
    return result


def validation_files() -> set[str]:
    result = {
        "repeatability.csv",
        "repeatability.json",
        "figure_quality.csv",
        "protected_hashes.csv",
        "report.md",
        "validation_checks.csv",
        "validation_summary.json",
        "render_audit.json",
        "manual_visual_review.csv",
    }
    result.update(
        f"rendered_pdf_review/{stem}.png" for stem in FIGURE_STEMS
    )
    if len(result) != 13:
        raise RuntimeError(f"Validation artifact specification drifted: {len(result)}")
    return result


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace(
        "+00:00", "Z"
    )


def write_receipt(path: Path, payload: dict[str, Any]) -> None:
    data = (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")
    atomic_write_bytes(path, data)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely reset the three fixed Board20 Step6 derived roots"
    )
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    contract = read_contract()
    roots = validate_fixed_roots(BOARD_ROOT, contract["fixed_output_roots"])
    specifications = {
        "run1": (run_files(), RUN_DIRECTORIES),
        "run2": (run_files(), RUN_DIRECTORIES),
        "validation": (validation_files(), VALIDATION_DIRECTORIES),
    }

    with ExclusiveFileLock(roots["logs"] / "step6_fs_protocol.lock"):
        roots = validate_fixed_roots(BOARD_ROOT, contract["fixed_output_roots"])
        preflight: dict[str, dict[str, Any]] = {}
        for name, (expected_files, expected_directories) in specifications.items():
            state = classify_output(
                roots[name], expected_files, expected_directories
            )
            preflight[name] = {
                "logical_relpath": contract["fixed_output_roots"][name],
                "lexical_absolute_path": os.path.abspath(str(roots[name])),
                "resolved_absolute_path": str(roots[name].resolve(strict=False)),
                "state": state.state,
                "file_count": len(state.inventory.files),
                "directory_count": len(state.inventory.directories),
                "manifest_sha256": state.manifest_sha256,
            }

        for name in ["run1", "run2", "validation"]:
            record = preflight[name]
            print(
                f"AUDIT {record['logical_relpath']} "
                f"files={record['file_count']} directories={record['directory_count']} "
                f"state={record['state']}"
            )
        if not args.execute:
            print("DRY_RUN_ONLY")
            return 0

        action_id = str(uuid.uuid4())
        receipt_path = roots["logs"] / "clean_probe_record.json"
        receipt: dict[str, Any] = {
            "schema_version": "board20_step6_clean_probe_receipt_v1",
            "action_id": action_id,
            "status": "INTENT",
            "started_utc": utc_now(),
            "completed_utc": None,
            "script_sha256": sha256_file(SCRIPT_PATH),
            "contract_sha256": sha256_file(CONTRACT_PATH),
            "fs_protocol_sha256": sha256_file(FS_PROTOCOL_PATH),
            "targets": preflight,
            "postconditions": {},
        }
        write_receipt(receipt_path, receipt)

        postconditions: dict[str, dict[str, Any]] = {}
        for name in ["run1", "run2", "validation"]:
            target = roots[name]
            if lexical_exists(target):
                shutil.rmtree(target)
            target.mkdir(parents=True, exist_ok=False)
            inventory = strict_inventory(target)
            if inventory.files or inventory.directories:
                raise RuntimeError(f"Reset target is not empty: {target}")
            postconditions[name] = {
                "state": "EMPTY_DIRECTORY",
                "file_count": 0,
                "directory_count": 0,
            }
            print(f"RESET_EMPTY {contract['fixed_output_roots'][name]}")

        receipt["status"] = "COMPLETED"
        receipt["completed_utc"] = utc_now()
        receipt["postconditions"] = postconditions
        write_receipt(receipt_path, receipt)
        print(
            json.dumps(
                {
                    "action_id": action_id,
                    "receipt": receipt_path.relative_to(BOARD_ROOT).as_posix(),
                    "status": "COMPLETED",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

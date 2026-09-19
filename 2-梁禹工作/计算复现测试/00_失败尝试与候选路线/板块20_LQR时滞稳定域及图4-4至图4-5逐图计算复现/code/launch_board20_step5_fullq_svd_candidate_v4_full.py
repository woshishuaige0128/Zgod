#!/usr/bin/env python3
"""Fail-closed external full/resume launcher for the sealed V4 candidate.

This launcher is deliberately inert while ``code/full_authorization.json`` is
absent.  It never imports the candidate, never creates the full directory, and
never writes an authorization.  Only after every sealed candidate, independent
pilot-postcheck, two-run determinism, root-attestation, and mode-specific gate
passes does it invoke the candidate as the final operation with a fixed absolute
Python executable and an argv list (``shell=False``).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


CODE_DIR = Path(__file__).resolve().parent
ROOT = CODE_DIR.parent.resolve()
CONTRACT_PATH = CODE_DIR / (
    "board20_step5_fullq_svd_candidate_v4_full_gate_waiting_contract.json"
)
AUTHORIZATION_RELPATH = "code/full_authorization.json"
AUTHORIZATION_PATH = ROOT / AUTHORIZATION_RELPATH
CONTRACT_SCHEMA = (
    "board20_step5_fullq_svd_candidate_v4_full_gate_waiting_contract_v1"
)
AUTHORIZATION_SCHEMA = (
    "board20_step5_fullq_svd_candidate_v4_full_authorization_v1"
)
CHECKPOINT_SCHEMA = (
    "board20_step5_fullq_svd_candidate_v4_checkpoint_identity_v4"
)
H5_SCHEMA = "board20_step5_fullq_svd_candidate_v4_roots_h5_v4"
HARD_RESIDUAL_LABEL = "SIGMA_MIN_DIRECT_MATRIX_OVER_SUM_SPECTRAL_NORM_WEIGHT"
VECTOR_ROLE = "DIAGNOSTIC_ONLY_VECTOR_BLOCK_CONDITIONING"
HEX64 = re.compile(r"[0-9A-F]{64}")


class GateFailure(RuntimeError):
    """A fail-closed gate rejection before candidate invocation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateFailure(message)


def require_mapping(value: Any, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{label} must be a JSON object.")
    return value


def require_hex64(value: Any, label: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value.upper()) is not None,
            f"{label} must be a non-placeholder 64-character SHA-256.")
    return value.upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest().upper()


def canonical_json_sha256(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Required JSON file is absent: {path}")
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            document = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateFailure(f"Cannot parse required JSON {path}: {exc}") from exc
    require(isinstance(document, dict), f"JSON root must be an object: {path}")
    return document


def resolve_relpath(relpath: str) -> Path:
    require(isinstance(relpath, str) and relpath != "", "Empty relative path.")
    pure = PurePosixPath(relpath)
    require(not pure.is_absolute(), f"Absolute path is forbidden: {relpath}")
    require(".." not in pure.parts and "." not in pure.parts,
            f"Path traversal is forbidden: {relpath}")
    path = (ROOT / Path(*pure.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise GateFailure(f"Path leaves the isolated root: {relpath}") from exc
    return path


def require_file_hash(relpath: str, expected_sha256: str, label: str) -> Path:
    path = resolve_relpath(relpath)
    require(path.is_file(), f"{label} is absent: {relpath}")
    expected = require_hex64(expected_sha256, f"{label} expected SHA-256")
    actual = sha256_file(path)
    require(actual == expected,
            f"{label} SHA-256 mismatch: expected {expected}, actual {actual}")
    return path


def h5_text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


def read_h5_records(path: Path) -> list[dict[str, Any]]:
    try:
        import h5py  # type: ignore
    except ImportError as exc:
        raise GateFailure("h5py is required to validate checkpoint HDF5 files.") from exc
    try:
        with h5py.File(path, "r") as handle:
            require(h5_text(handle.attrs.get("schema_version", "")) == H5_SCHEMA,
                    f"Checkpoint HDF5 schema mismatch: {path}")
            require(
                h5_text(handle.attrs.get("hard_residual_definition", ""))
                == HARD_RESIDUAL_LABEL,
                f"Checkpoint HDF5 residual identity mismatch: {path}",
            )
            require(
                h5_text(handle.attrs.get("vector_block_residual_role", ""))
                == VECTOR_ROLE,
                f"Checkpoint HDF5 vector role mismatch: {path}",
            )
            require("points/record_json" in handle,
                    f"Checkpoint HDF5 lacks points/record_json: {path}")
            raw_records = handle["points/record_json"].asstr()[...]
            records: list[dict[str, Any]] = []
            for index, raw in enumerate(raw_records):
                try:
                    record = json.loads(str(raw))
                except json.JSONDecodeError as exc:
                    raise GateFailure(
                        f"Invalid HDF5 record_json at index {index}: {path}"
                    ) from exc
                require(isinstance(record, dict),
                        f"HDF5 record_json is not an object at index {index}: {path}")
                records.append(record)
            return records
    except GateFailure:
        raise
    except Exception as exc:
        raise GateFailure(f"Cannot validate checkpoint HDF5 {path}: {exc}") from exc


def require_record_order(
    records: Sequence[Mapping[str, Any]],
    route_id: str,
    expected_points: Sequence[Sequence[int]],
) -> None:
    require(len(records) == len(expected_points),
            f"Checkpoint HDF5 point count mismatch for {route_id}.")
    for index, (record, expected) in enumerate(zip(records, expected_points)):
        actual = [int(record.get("l", -1)), int(record.get("j", -1))]
        require(record.get("route_id") == route_id,
                f"Checkpoint HDF5 route mismatch for {route_id} at index {index}.")
        require(actual == list(expected),
                f"Checkpoint HDF5 point order mismatch for {route_id} at index {index}.")


def verify_manifest(
    manifest_path: Path,
    expected_fields: Sequence[str] | None = None,
    expected_rows: int | None = None,
) -> dict[str, str]:
    try:
        with manifest_path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise GateFailure(f"Cannot parse manifest {manifest_path}: {exc}") from exc
    if expected_fields is not None:
        require(fields == list(expected_fields),
                f"Manifest field mismatch: {manifest_path}")
    require(fields == ["relpath", "bytes", "sha256"],
            f"Manifest must use relpath,bytes,sha256: {manifest_path}")
    if expected_rows is not None:
        require(len(rows) == expected_rows,
                f"Manifest row count mismatch: {manifest_path}")
    observed: dict[str, str] = {}
    for row in rows:
        relpath = str(row.get("relpath", ""))
        require(relpath not in observed, f"Duplicate manifest relpath: {relpath}")
        pure = PurePosixPath(relpath)
        require(relpath != "" and not pure.is_absolute() and ".." not in pure.parts,
                f"Unsafe manifest relpath: {relpath}")
        artifact = (manifest_path.parent / Path(*pure.parts)).resolve()
        try:
            artifact.relative_to(manifest_path.parent.resolve())
        except ValueError as exc:
            raise GateFailure(f"Manifest artifact leaves its root: {relpath}") from exc
        require(artifact.is_file(), f"Manifest artifact is absent: {artifact}")
        actual_hash = sha256_file(artifact)
        expected_hash = require_hex64(row.get("sha256"),
                                      f"Manifest SHA-256 for {relpath}")
        require(actual_hash == expected_hash,
                f"Manifest artifact SHA-256 mismatch: {relpath}")
        try:
            expected_bytes = int(str(row.get("bytes", "")))
        except ValueError as exc:
            raise GateFailure(f"Invalid manifest byte count: {relpath}") from exc
        require(artifact.stat().st_size == expected_bytes,
                f"Manifest artifact byte count mismatch: {relpath}")
        observed[relpath] = actual_hash
    return observed


def verify_authorization(
    contract: Mapping[str, Any], mode: str, checkpoint_every: int
) -> dict[str, Any]:
    require(AUTHORIZATION_PATH.is_file(),
            "WAITING: code/full_authorization.json is absent; candidate was not invoked.")
    authorization = read_json(AUTHORIZATION_PATH)
    require(authorization.get("schema_version") == AUTHORIZATION_SCHEMA,
            "Full authorization schema mismatch.")
    require(authorization.get("authorization_status") == "AUTHORIZED",
            "Full authorization status is not AUTHORIZED.")
    require(authorization.get("effective_authorization") is True,
            "Full authorization is not effective.")
    require(authorization.get("authorized_modes") == ["full", "resume"],
            "Authorization must explicitly cover exactly full and resume.")
    require(mode in authorization["authorized_modes"],
            f"Requested mode is not authorized: {mode}")
    required_checkpoint = int(
        contract["external_authorization_gate"]["required_checkpoint_every"]
    )
    require(checkpoint_every == required_checkpoint,
            f"--checkpoint-every must remain {required_checkpoint}.")
    require(authorization.get("checkpoint_every") == required_checkpoint,
            "Authorization checkpoint cadence mismatch.")
    expected_full_relpath = contract["fixed_runtime"]["full_output_relpath"]
    require(authorization.get("full_output_relpath") == expected_full_relpath,
            "Authorization full output path mismatch.")

    attestation = require_mapping(
        authorization.get("root_attestation"), "root_attestation"
    )
    require(attestation.get("generated_by_role") == "ROOT_AGENT",
            "Authorization was not attested by the root agent.")
    require(attestation.get("basis_type") == "USER_ORIGINAL_GOAL",
            "Authorization basis is not the user's original goal.")
    require(
        attestation.get("decision")
        == "AUTHORIZE_V4_FULL_AFTER_INDEPENDENT_PILOT_POSTCHECK_PASS",
        "Root authorization decision text mismatch.",
    )
    require(attestation.get("pilot_audit_was_pass_before_authorization") is True,
            "Root did not attest that pilot audit passed before authorization.")
    goal_text = attestation.get("user_original_goal_verbatim")
    require(isinstance(goal_text, str) and goal_text.strip() != "",
            "The user's original goal must be recorded verbatim.")
    goal_hash = require_hex64(
        attestation.get("user_original_goal_sha256"),
        "root_attestation.user_original_goal_sha256",
    )
    require(sha256_text(goal_text) == goal_hash,
            "User original goal text and SHA-256 do not match.")

    gate_identity = require_mapping(
        authorization.get("gate_identity"), "gate_identity"
    )
    contract_hash = sha256_file(CONTRACT_PATH)
    launcher_hash = sha256_file(Path(__file__).resolve())
    require(require_hex64(gate_identity.get("contract_sha256"),
                          "gate contract SHA-256") == contract_hash,
            "External authorization does not bind the current gate contract.")
    require(require_hex64(gate_identity.get("launcher_sha256"),
                          "gate launcher SHA-256") == launcher_hash,
            "External authorization does not bind the current launcher.")
    return authorization


def verify_fixed_candidate(
    contract: Mapping[str, Any], authorization: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = contract["fixed_runtime"]
    gates = contract["sealed_candidate_gates"]
    candidate_identity = require_mapping(
        authorization.get("candidate_identity_sha256"),
        "candidate_identity_sha256",
    )
    expected_authorization_identity = {
        "candidate_script": runtime["candidate_script_sha256"],
        "candidate_contract": runtime["candidate_contract_sha256"],
        "input_seal": runtime["input_seal_sha256"],
        "preflight": gates["preflight"]["sha256"],
        "selftest": gates["selftest"]["sha256"],
        "pilot_manifest": gates["pilot_manifest"]["sha256"],
        "pilot_repeatability": gates["pilot_repeatability"]["sha256"],
        "pilot_run_status": gates["pilot_run_status"]["sha256"],
    }
    for key, expected in expected_authorization_identity.items():
        actual = require_hex64(candidate_identity.get(key),
                               f"candidate_identity_sha256.{key}")
        require(actual == expected,
                f"Authorization candidate identity mismatch: {key}")

    candidate_script = require_file_hash(
        runtime["candidate_script_relpath"], runtime["candidate_script_sha256"],
        "sealed candidate script",
    )
    require(candidate_script.resolve() != Path(__file__).resolve(),
            "Launcher and candidate paths unexpectedly coincide.")
    require_file_hash(
        runtime["candidate_contract_relpath"], runtime["candidate_contract_sha256"],
        "sealed candidate contract",
    )
    seal_path = require_file_hash(
        runtime["input_seal_relpath"], runtime["input_seal_sha256"],
        "sealed candidate input seal",
    )
    seal = read_json(seal_path)
    require(seal.get("schema_version")
            == "board20_step5_fullq_svd_candidate_v4_input_seal_v4",
            "Input seal schema mismatch.")
    require(seal.get("candidate_script_sha256") == runtime["candidate_script_sha256"],
            "Input seal candidate script identity mismatch.")
    require(seal.get("candidate_contract_sha256")
            == runtime["candidate_contract_sha256"],
            "Input seal candidate contract identity mismatch.")

    for gate_name in ("preflight", "selftest"):
        expected = gates[gate_name]
        path = require_file_hash(expected["relpath"], expected["sha256"], gate_name)
        document = read_json(path)
        for key in ("schema_version", "status", "check_count", "pass_count", "fail_count"):
            require(document.get(key) == expected[key],
                    f"{gate_name} field mismatch: {key}")
        checks = document.get("checks")
        require(isinstance(checks, list) and len(checks) == expected["check_count"],
                f"{gate_name} check list length mismatch.")
        require(all(isinstance(item, dict) and item.get("status") == "PASS"
                    for item in checks),
                f"{gate_name} contains a non-PASS check.")
        require(document.get("input_seal_sha256") == runtime["input_seal_sha256"],
                f"{gate_name} is not bound to the sealed input.")
        if gate_name == "selftest":
            require(document.get("candidate_script_sha256")
                    == runtime["candidate_script_sha256"],
                    "Selftest candidate script identity mismatch.")
            require(document.get("candidate_contract_sha256")
                    == runtime["candidate_contract_sha256"],
                    "Selftest candidate contract identity mismatch.")

    manifest_spec = gates["pilot_manifest"]
    manifest_path = require_file_hash(
        manifest_spec["relpath"], manifest_spec["sha256"], "pilot manifest"
    )
    verify_manifest(
        manifest_path,
        expected_fields=manifest_spec["fields"],
        expected_rows=int(manifest_spec["row_count"]),
    )

    repeat_spec = gates["pilot_repeatability"]
    repeat_path = require_file_hash(
        repeat_spec["relpath"], repeat_spec["sha256"], "pilot repeatability"
    )
    repeatability = read_json(repeat_path)
    for key in ("schema_version", "mode", "status", "scientific_artifacts_match"):
        require(repeatability.get(key) == repeat_spec[key],
                f"Pilot repeatability field mismatch: {key}")
    baseline_key, repeat_key = repeat_spec["actual_long_field_names"]
    actual_manifest_hash = sha256_file(manifest_path)
    require(baseline_key == "baseline_artifact_manifest_sha256"
            and repeat_key == "repeat_artifact_manifest_sha256",
            "Contract does not name the actual long repeatability keys.")
    require(
        repeatability.get(baseline_key)
        == repeatability.get(repeat_key)
        == actual_manifest_hash,
        "Pilot repeatability must satisfy baseline=repeat=actual manifest SHA-256.",
    )

    run_spec = gates["pilot_run_status"]
    run_path = require_file_hash(
        run_spec["relpath"], run_spec["sha256"], "pilot run status"
    )
    run_status = read_json(run_path)
    for key in (
        "schema_version", "status", "mode", "route_count",
        "expected_point_count", "completed_point_count", "pass_point_count",
        "fail_point_count",
    ):
        require(run_status.get(key) == run_spec[key],
                f"Pilot run-status field mismatch: {key}")
    require(run_status.get("input_identity") == seal,
            "Pilot run status is not bound to the exact input seal.")
    return seal, run_status


def verify_candidate_two_run_records(contract: Mapping[str, Any]) -> None:
    gates = contract["sealed_candidate_gates"]
    records = gates["candidate_two_run_external_records"]
    baseline_path = require_file_hash(
        records["run1_baseline_relpath"], records["run1_baseline_sha256"],
        "candidate pilot run-1 baseline record",
    )
    repeat_path = require_file_hash(
        records["repeatability_external_relpath"],
        records["repeatability_external_sha256"],
        "candidate pilot external repeatability record",
    )
    baseline = read_json(baseline_path)
    repeat = read_json(repeat_path)
    manifest_hash = gates["pilot_manifest"]["sha256"]
    require(baseline.get("candidate_status") == "PASS",
            "Candidate run-1 baseline is not PASS.")
    require(baseline.get("completed_point_count") == 49
            and baseline.get("fail_point_count") == 0,
            "Candidate run-1 baseline point counts mismatch.")
    require(baseline.get("artifact_manifest_sha256") == manifest_hash,
            "Candidate run-1 baseline manifest mismatch.")
    require(baseline.get("full_run_authorized_by_this_record") is False,
            "Candidate run-1 baseline must not authorize full.")
    require(repeat.get("status") == records["required_status"],
            "Candidate external repeatability is not PASS.")
    require(repeat.get("candidate_run_count") == records["required_run_count"],
            "Candidate external repeatability run count mismatch.")
    require(repeat.get("artifact_count") == records["required_artifact_count"],
            "Candidate external repeatability artifact count mismatch.")
    require(repeat.get("artifact_byte_or_sha_mismatch_count")
            == records["required_artifact_mismatch_count"],
            "Candidate external repeatability has artifact mismatches.")
    require(repeat.get("protected_evidence_change_count")
            == records["required_protected_change_count"],
            "Candidate external repeatability reports protected changes.")
    require(repeat.get("scientific_artifacts_match") is True,
            "Candidate external repeatability artifacts do not match.")
    require(
        repeat.get("baseline_artifact_manifest_sha256")
        == repeat.get("repeat_artifact_manifest_sha256")
        == repeat.get("externally_recomputed_artifact_manifest_sha256")
        == manifest_hash,
        "Candidate external repeatability must satisfy baseline=repeat=actual.",
    )
    require(repeat.get("full_run_or_postcheck_authorized_by_this_record") is False,
            "Candidate external repeatability record must not authorize full.")


def verify_pilot_routes(
    contract: Mapping[str, Any], seal: Mapping[str, Any],
    run_status: Mapping[str, Any],
) -> None:
    candidate_contract = read_json(
        resolve_relpath(contract["fixed_runtime"]["candidate_contract_relpath"])
    )
    pilot_points = require_mapping(
        candidate_contract.get("pilot_points"), "candidate pilot_points"
    )
    route_status_list = run_status.get("route_statuses")
    require(isinstance(route_status_list, list) and len(route_status_list) == 5,
            "Pilot run status must contain exactly five route statuses.")
    run_routes = {
        item.get("route_id"): item
        for item in route_status_list
        if isinstance(item, dict)
    }
    require(len(run_routes) == 5, "Pilot route-status identities are not unique.")
    for spec in contract["pilot_routes"]:
        route_id = spec["route_id"]
        status_path = require_file_hash(
            spec["route_status_relpath"], spec["route_status_sha256"],
            f"pilot route status {route_id}",
        )
        checkpoint_path = require_file_hash(
            spec["checkpoint_json_relpath"], spec["checkpoint_json_sha256"],
            f"pilot checkpoint JSON {route_id}",
        )
        h5_path = require_file_hash(
            spec["checkpoint_h5_relpath"], spec["checkpoint_h5_sha256"],
            f"pilot checkpoint HDF5 {route_id}",
        )
        route_status = read_json(status_path)
        checkpoint = read_json(checkpoint_path)
        expected_points = pilot_points.get(route_id)
        require(isinstance(expected_points, list)
                and len(expected_points) == spec["expected_point_count"],
                f"Pilot point contract mismatch for {route_id}.")
        expected_order_hash = canonical_json_sha256(expected_points)
        require(expected_order_hash == spec["point_order_sha256"],
                f"Pilot point-order preregistration mismatch for {route_id}.")
        require(route_status == run_routes.get(route_id),
                f"Pilot run-status embedded route differs for {route_id}.")
        require(route_status.get("schema_version")
                == "board20_step5_fullq_svd_candidate_v4_route_status_v4",
                f"Pilot route-status schema mismatch for {route_id}.")
        require(route_status.get("status") == "PASS"
                and route_status.get("fail_point_count") == 0,
                f"Pilot route is not PASS for {route_id}.")
        require(route_status.get("completed_point_count")
                == spec["expected_point_count"],
                f"Pilot route point count mismatch for {route_id}.")
        require(checkpoint.get("schema_version") == CHECKPOINT_SCHEMA,
                f"Pilot checkpoint schema mismatch for {route_id}.")
        require(checkpoint.get("state") == "COMPLETE",
                f"Pilot checkpoint is not COMPLETE for {route_id}.")
        require(checkpoint.get("completed_point_count")
                == spec["expected_point_count"],
                f"Pilot checkpoint point count mismatch for {route_id}.")
        require(checkpoint.get("checkpoint_h5_sha256")
                == spec["checkpoint_h5_sha256"],
                f"Pilot checkpoint HDF5 binding mismatch for {route_id}.")
        require(checkpoint.get("point_order_sha256") == expected_order_hash,
                f"Pilot checkpoint point-order hash mismatch for {route_id}.")
        require(checkpoint.get("candidate_script_sha256")
                == seal["candidate_script_sha256"],
                f"Pilot checkpoint candidate script mismatch for {route_id}.")
        require(checkpoint.get("candidate_contract_sha256")
                == seal["candidate_contract_sha256"],
                f"Pilot checkpoint candidate contract mismatch for {route_id}.")
        records = read_h5_records(h5_path)
        require_record_order(records, route_id, expected_points)


def verify_validator_and_postcheck(
    contract: Mapping[str, Any], authorization: Mapping[str, Any]
) -> None:
    validator_spec = contract["independent_validator_v4_gate"]
    authorized_validator = require_mapping(
        authorization.get("validator_v4_identity_sha256"),
        "validator_v4_identity_sha256",
    )
    validator_hashes: dict[str, str] = {}
    validator_paths: dict[str, Path] = {}
    for name, item in validator_spec["identity_files"].items():
        expected = require_hex64(authorized_validator.get(name),
                                 f"validator_v4_identity_sha256.{name}")
        path = require_file_hash(item["relpath"], expected,
                                 f"validator V4 {name}")
        validator_hashes[name] = expected
        validator_paths[name] = path
        if path.suffix.lower() == ".json":
            read_json(path)
    validator_contract = read_json(validator_paths["contract"])
    require(validator_contract.get("contract_status")
            == validator_spec["required_contract_status"],
            "Validator V4 contract status mismatch.")
    activation = require_mapping(
        validator_contract.get("activation_policy"),
        "validator activation_policy",
    )
    require(activation.get("pilot_postcheck_enabled")
            is validator_spec["required_pilot_postcheck_enabled"],
            "Validator V4 pilot-postcheck activation mismatch.")
    require(activation.get("full_postcheck_enabled")
            is validator_spec["required_full_postcheck_enabled"],
            "Validator V4 full-postcheck must remain disabled.")
    require(activation.get("candidate_computation_may_be_launched_by_validator")
            is False,
            "Validator V4 must not launch candidate computation.")

    postcheck_spec = contract["independent_pilot_postcheck_gate"]
    authorized_artifacts = require_mapping(
        authorization.get("pilot_postcheck_artifacts_sha256"),
        "pilot_postcheck_artifacts_sha256",
    )
    expected_relpaths = {
        item["relpath"] for item in postcheck_spec["artifacts"].values()
    }
    require(set(authorized_artifacts) == expected_relpaths,
            "Authorization must bind exactly all six pilot-postcheck artifacts.")
    artifact_hashes: dict[str, str] = {}
    artifact_paths: dict[str, Path] = {}
    for name, item in postcheck_spec["artifacts"].items():
        relpath = item["relpath"]
        expected = require_hex64(authorized_artifacts.get(relpath),
                                 f"pilot postcheck artifact {relpath}")
        artifact_paths[name] = require_file_hash(
            relpath, expected, f"pilot postcheck {name}"
        )
        artifact_hashes[relpath] = expected

    postcheck = read_json(artifact_paths["main_json"])
    require(postcheck.get("schema_version")
            == postcheck_spec["required_main_schema_version"],
            "Independent pilot postcheck schema mismatch.")
    summary = require_mapping(postcheck.get("summary"), "pilot postcheck summary")
    require(summary.get("mode") == postcheck_spec["required_summary_mode"],
            "Independent pilot postcheck mode mismatch.")
    require(summary.get("overall_status")
            == postcheck_spec["required_overall_status"],
            "Independent pilot postcheck is not PASS.")
    require(summary.get("failed_checks") == postcheck_spec["required_failed_checks"],
            "Independent pilot postcheck contains failed checks.")
    require(summary.get("candidate_computation_launched") is False,
            "Independent pilot postcheck launched candidate computation.")
    require(summary.get("candidate_outputs_modified") is False,
            "Independent pilot postcheck modified candidate outputs.")
    require(summary.get("explicit_postcheck_authorization") is True,
            "Independent pilot postcheck lacked explicit authorization.")
    require(postcheck.get("protected_hashes_before")
            == postcheck.get("protected_hashes_after"),
            "Independent pilot postcheck changed protected files.")
    binding = require_mapping(
        postcheck.get("authorization_binding"),
        "pilot postcheck authorization_binding",
    )
    runtime = contract["fixed_runtime"]
    gates = contract["sealed_candidate_gates"]
    require(binding.get("candidate_contract_sha256")
            == runtime["candidate_contract_sha256"],
            "Pilot postcheck candidate contract binding mismatch.")
    require(binding.get("candidate_script_sha256")
            == runtime["candidate_script_sha256"],
            "Pilot postcheck candidate script binding mismatch.")
    require(binding.get("input_seal_sha256") == runtime["input_seal_sha256"],
            "Pilot postcheck input seal binding mismatch.")
    require(binding.get("artifact_manifest_sha256")
            == gates["pilot_manifest"]["sha256"],
            "Pilot postcheck candidate manifest binding mismatch.")
    require(binding.get("repeatability_sha256")
            == gates["pilot_repeatability"]["sha256"],
            "Pilot postcheck candidate repeatability binding mismatch.")
    require(binding.get("run_status_sha256")
            == gates["pilot_run_status"]["sha256"],
            "Pilot postcheck candidate run-status binding mismatch.")
    require(binding.get("candidate_status") == "PASS"
            and binding.get("mode") == "pilot",
            "Pilot postcheck candidate status/mode binding mismatch.")
    require(binding.get("full_computation_launched_by_validator") is False,
            "Pilot postcheck claims a full computation was launched.")
    require(binding.get("validator_script_sha256") == validator_hashes["script"],
            "Pilot postcheck validator script binding mismatch.")
    require(binding.get("validator_contract_sha256")
            == validator_hashes["contract"],
            "Pilot postcheck validator contract binding mismatch.")
    verify_manifest(artifact_paths["artifact_manifest"])
    verify_postcheck_determinism(
        contract, authorization, validator_hashes, artifact_hashes
    )


def verify_postcheck_determinism(
    contract: Mapping[str, Any],
    authorization: Mapping[str, Any],
    validator_hashes: Mapping[str, str],
    artifact_hashes: Mapping[str, str],
) -> None:
    spec = contract["independent_pilot_postcheck_determinism_gate"]
    binding = require_mapping(
        authorization.get("pilot_postcheck_determinism"),
        "pilot_postcheck_determinism",
    )
    baseline_spec = spec["run1_baseline"]
    repeat_spec = spec["repeatability"]
    require(binding.get("run1_baseline_relpath") == baseline_spec["relpath"],
            "Postcheck run-1 baseline path mismatch in authorization.")
    require(binding.get("repeatability_relpath") == repeat_spec["relpath"],
            "Postcheck repeatability path mismatch in authorization.")
    baseline_path = require_file_hash(
        baseline_spec["relpath"],
        require_hex64(binding.get("run1_baseline_sha256"),
                      "postcheck run-1 baseline SHA-256"),
        "postcheck run-1 baseline record",
    )
    repeat_path = require_file_hash(
        repeat_spec["relpath"],
        require_hex64(binding.get("repeatability_sha256"),
                      "postcheck repeatability SHA-256"),
        "postcheck two-run repeatability record",
    )
    baseline = read_json(baseline_path)
    repeat = read_json(repeat_path)
    require(baseline.get("schema_version")
            == baseline_spec["required_schema_version"],
            "Postcheck run-1 baseline schema mismatch.")
    require(baseline.get("pilot_postcheck_status") == "PASS",
            "Postcheck run-1 baseline is not PASS.")
    require(baseline.get("exit_code") == 0 and baseline.get("fail_count") == 0,
            "Postcheck run-1 baseline records a failure.")
    require(baseline.get("candidate_computation_launched") is False,
            "Postcheck run-1 baseline says candidate computation was launched.")
    require(baseline.get("candidate_outputs_modified") is False,
            "Postcheck run-1 baseline says candidate outputs changed.")
    require(baseline.get("v4_full_directory_existed") is False,
            "Postcheck run-1 baseline was not recorded before full.")
    baseline_validator = require_mapping(
        baseline.get("validator_identity"), "postcheck baseline validator_identity"
    )
    expected_validator = {
        "script_sha256": validator_hashes["script"],
        "contract_sha256": validator_hashes["contract"],
        "binding_sha256": validator_hashes["binding"],
        "revision_contract_sha256": validator_hashes["revision"],
    }
    require(dict(baseline_validator) == expected_validator,
            "Postcheck run-1 validator identity mismatch.")
    require(baseline.get("run1_artifact_sha256") == dict(artifact_hashes),
            "Postcheck run-1 artifact hashes do not match current six artifacts.")
    require(baseline.get("repeat_run_authorized_by_this_record") is False
            and baseline.get("full_run_authorized_by_this_record") is False,
            "Postcheck run-1 baseline must not itself authorize another run/full.")

    require(repeat.get("schema_version") == repeat_spec["required_schema_version"],
            "Postcheck repeatability schema mismatch.")
    require(repeat.get("status") == repeat_spec["required_status"],
            "Postcheck repeatability is not PASS.")
    require(repeat.get("mode") == repeat_spec["required_mode"],
            "Postcheck repeatability mode mismatch.")
    require(repeat.get("run_count") == repeat_spec["required_run_count"],
            "Postcheck repeatability run count mismatch.")
    require(repeat.get("each_run_fail_count") == 0,
            "A postcheck deterministic run contains failures.")
    require(repeat.get("run1_baseline_relpath") == baseline_spec["relpath"]
            and repeat.get("run1_baseline_sha256") == sha256_file(baseline_path),
            "Postcheck repeatability does not bind its run-1 baseline.")
    require(repeat.get("artifact_count_compared")
            == repeat_spec["required_artifact_count_compared"],
            "Postcheck repeatability artifact count mismatch.")
    require(repeat.get("artifact_mismatch_count")
            == repeat_spec["required_artifact_mismatch_count"],
            "Postcheck repeatability reports artifact mismatches.")
    require(repeat.get("identical_artifact_sha256") == dict(artifact_hashes),
            "Postcheck two-run artifact hashes are not identical/current.")
    require(repeat.get("candidate_computation_launched") is False
            and repeat.get("candidate_outputs_modified") is False,
            "Postcheck repeatability reports candidate computation/modification.")
    require(repeat.get("v4_full_directory_existed") is False,
            "Postcheck repeatability was not completed before full.")
    require(repeat.get("candidate_full_authorized_by_this_record") is False,
            "Postcheck repeatability must not itself authorize full.")


def verify_initial_full_absence(contract: Mapping[str, Any]) -> None:
    full_path = resolve_relpath(contract["fixed_runtime"]["full_output_relpath"])
    require(not full_path.exists(),
            "Initial full requires the full output path to be completely absent.")


def full_points(contract: Mapping[str, Any]) -> list[list[int]]:
    policy = contract["full_and_resume_policy"]
    points = [[l_value, j_value] for l_value in range(31) for j_value in range(67)]
    require(len(points) == policy["points_per_route"],
            "Internal full point count does not match the contract.")
    require(canonical_json_sha256(points) == policy["full_point_order_sha256"],
            "Internal full point order does not match the contract.")
    return points


def expected_checkpoint_identity(
    seal: Mapping[str, Any], route_id: str, point_order_sha256: str
) -> dict[str, Any]:
    workspace = require_mapping(seal.get("workspace_sha256"), "seal workspace_sha256")
    return {
        "schema_version": CHECKPOINT_SCHEMA,
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
        "route_manifest_sha256": seal["route_manifest_sha256"],
        "base_compute_sha256": seal["base_compute_sha256"],
        "v2_engine_sha256": seal["v2_engine_sha256"],
        "v3_reference_script_sha256": seal["v3_reference_script_sha256"],
        "static_diff_selftest_sha256": seal["static_diff_selftest_sha256"],
        "protected_evidence_sha256": canonical_json_sha256(
            seal["protected_evidence_sha256"]
        ),
        "workspace_sha256": workspace[route_id],
        "route_id": route_id,
        "point_order_sha256": point_order_sha256,
        "hard_residual_math_sha256": seal["hard_residual_math_sha256"],
        "numeric_gates_sha256": seal["numeric_gates_sha256"],
    }


def verify_resume_checkpoints(
    contract: Mapping[str, Any], seal: Mapping[str, Any]
) -> None:
    full_path = resolve_relpath(contract["fixed_runtime"]["full_output_relpath"])
    require(full_path.is_dir(), "Resume requires an existing full output directory.")
    route_ids = [item["route_id"] for item in contract["pilot_routes"]]
    observed_route_dirs = sorted(
        path.name for path in full_path.iterdir() if path.is_dir()
    )
    require(observed_route_dirs == sorted(route_ids),
            "Resume requires exactly the five contracted full route directories.")
    points = full_points(contract)
    point_order_hash = canonical_json_sha256(points)
    allowed_states = set(
        contract["full_and_resume_policy"]["resume_allowed_checkpoint_states"]
    )
    for route_id in route_ids:
        route_dir = full_path / route_id
        json_path = route_dir / "checkpoint.json"
        h5_path = route_dir / "checkpoint.h5"
        require(json_path.is_file() and h5_path.is_file(),
                f"Resume requires a complete checkpoint pair for {route_id}.")
        checkpoint = read_json(json_path)
        expected_identity = expected_checkpoint_identity(
            seal, route_id, point_order_hash
        )
        for key, expected in expected_identity.items():
            require(checkpoint.get(key) == expected,
                    f"Resume checkpoint identity mismatch for {route_id}: {key}")
        state = checkpoint.get("state")
        require(state in allowed_states,
                f"Resume checkpoint state is not allowed for {route_id}: {state}")
        count = checkpoint.get("completed_point_count")
        require(isinstance(count, int) and 0 <= count <= len(points),
                f"Resume checkpoint point count is invalid for {route_id}.")
        if state == "COMPLETE":
            require(count == len(points),
                    f"COMPLETE checkpoint is not complete for {route_id}.")
        else:
            require(count < len(points),
                    f"IN_PROGRESS checkpoint cannot contain the complete grid: {route_id}")
        expected_h5_hash = require_hex64(
            checkpoint.get("checkpoint_h5_sha256"),
            f"resume checkpoint HDF5 SHA-256 {route_id}",
        )
        actual_h5_hash = sha256_file(h5_path)
        require(actual_h5_hash == expected_h5_hash,
                f"Resume checkpoint HDF5 SHA-256 mismatch for {route_id}.")
        records = read_h5_records(h5_path)
        require(len(records) == count,
                f"Resume checkpoint JSON/HDF5 point count mismatch for {route_id}.")
        require_record_order(records, route_id, points[:count])


def build_candidate_command(
    contract: Mapping[str, Any], mode: str, checkpoint_every: int
) -> list[str]:
    runtime = contract["fixed_runtime"]
    python_path = Path(runtime["python_executable"])
    require(python_path.is_absolute() and python_path.is_file(),
            f"Fixed absolute Python executable is absent: {python_path}")
    candidate_path = resolve_relpath(runtime["candidate_script_relpath"])
    require(candidate_path.is_file(), "Candidate script disappeared after gate checks.")
    return [
        str(python_path),
        str(candidate_path),
        "--mode",
        mode,
        "--explicit-full-authorization",
        "--checkpoint-every",
        str(checkpoint_every),
    ]


def run_all_gates(mode: str, checkpoint_every: int) -> tuple[dict[str, Any], list[str]]:
    contract = read_json(CONTRACT_PATH)
    require(contract.get("schema_version") == CONTRACT_SCHEMA,
            "WAITING gate contract schema mismatch.")
    require(
        contract.get("contract_status")
        == "WAITING_FOR_INDEPENDENT_PILOT_POSTCHECK_AND_ROOT_FULL_AUTHORIZATION",
        "Gate contract is not the preregistered WAITING contract.",
    )
    require(contract.get("effective_full_authorization") is False,
            "WAITING contract must never self-authorize.")
    authorization = verify_authorization(contract, mode, checkpoint_every)
    seal, run_status = verify_fixed_candidate(contract, authorization)
    verify_candidate_two_run_records(contract)
    verify_pilot_routes(contract, seal, run_status)
    verify_validator_and_postcheck(contract, authorization)
    if mode == "full":
        verify_initial_full_absence(contract)
    else:
        verify_resume_checkpoints(contract, seal)
    command = build_candidate_command(contract, mode, checkpoint_every)
    return authorization, command


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Fail-closed external launcher for the sealed Board-20 Step-5 V4 "
            "full/resume candidate. Current state is WAITING; help never launches."
        )
    )
    parser.add_argument(
        "--mode", required=True, choices=("full", "resume"),
        help="full requires an absent full directory; resume validates five checkpoints.",
    )
    parser.add_argument(
        "--checkpoint-every", type=int, default=25,
        help="Fixed authorized checkpoint cadence (default and currently required: 25).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidate_invoked = False
    try:
        _authorization, command = run_all_gates(
            args.mode, args.checkpoint_every
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": "board20_step5_fullq_svd_candidate_v4_full_gate_result_v1",
                    "status": "WAITING_FAIL_CLOSED",
                    "requested_mode": args.mode,
                    "candidate_invoked": candidate_invoked,
                    "full_directory_created_by_launcher": False,
                    "authorization_relpath": AUTHORIZATION_RELPATH,
                    "reason": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 3

    print(
        json.dumps(
            {
                "schema_version": "board20_step5_fullq_svd_candidate_v4_full_gate_result_v1",
                "status": "ALL_EXTERNAL_GATES_PASS_LAUNCHING_CANDIDATE",
                "requested_mode": args.mode,
                "checkpoint_every": args.checkpoint_every,
                "shell": False,
                "candidate_command_argv": command,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    candidate_invoked = True
    completed = subprocess.run(
        command,
        cwd=str(ROOT),
        shell=False,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Formal fail-closed V2 full/resume launcher for the sealed V4 candidate.

The formal contract seals the independent validator V4 PASS pilot postcheck and
its two-run deterministic evidence.  This launcher still remains inert until a
separate root-created ``code/full_authorization.json`` binds the exact hashes of
the formal contract, this launcher, its revision contract, and its binding
record, together with a matching attestation of the user's original goal.

The candidate is never imported.  The sole candidate invocation is the last
operation after every gate passes and uses a fixed absolute Python executable,
an argv list, and ``shell=False``.
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
CONTRACT_PATH = CODE_DIR / "board20_step5_fullq_svd_candidate_v4_full_gate_contract.json"
REVISION_PATH = CODE_DIR / (
    "board20_step5_fullq_svd_candidate_v4_full_gate_revision_contract.json"
)
BINDING_PATH = CODE_DIR / (
    "board20_step5_fullq_svd_candidate_v4_full_gate_binding_record.json"
)
AUTHORIZATION_RELPATH = "code/full_authorization.json"
AUTHORIZATION_PATH = ROOT / AUTHORIZATION_RELPATH
CONTRACT_SCHEMA = "board20_step5_fullq_svd_candidate_v4_full_gate_contract_v1"
AUTHORIZATION_SCHEMA = "board20_step5_fullq_svd_candidate_v4_full_authorization_v1"
CHECKPOINT_SCHEMA = "board20_step5_fullq_svd_candidate_v4_checkpoint_identity_v4"
H5_SCHEMA = "board20_step5_fullq_svd_candidate_v4_roots_h5_v4"
HARD_RESIDUAL_LABEL = "SIGMA_MIN_DIRECT_MATRIX_OVER_SUM_SPECTRAL_NORM_WEIGHT"
VECTOR_ROLE = "DIAGNOSTIC_ONLY_VECTOR_BLOCK_CONDITIONING"
HEX64 = re.compile(r"[0-9A-F]{64}")


class GateFailure(RuntimeError):
    """Fail-closed rejection raised before candidate invocation."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise GateFailure(message)


def mapping(value: Any, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), f"{label} must be a JSON object.")
    return value


def hex64(value: Any, label: str) -> str:
    require(isinstance(value, str) and HEX64.fullmatch(value.upper()) is not None,
            f"{label} must be a non-placeholder SHA-256.")
    return value.upper()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest().upper()


def sha256_json(value: Any) -> str:
    raw = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest().upper()


def read_json(path: Path) -> dict[str, Any]:
    require(path.is_file(), f"Required JSON is absent: {path}")
    try:
        with path.open("r", encoding="utf-8-sig") as stream:
            value = json.load(stream)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateFailure(f"Cannot parse JSON {path}: {exc}") from exc
    require(isinstance(value, dict), f"JSON root must be an object: {path}")
    return value


def resolve_relpath(relpath: str) -> Path:
    require(isinstance(relpath, str) and relpath != "", "Empty relative path.")
    pure = PurePosixPath(relpath)
    require(not pure.is_absolute() and ".." not in pure.parts and "." not in pure.parts,
            f"Unsafe relative path: {relpath}")
    path = (ROOT / Path(*pure.parts)).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError as exc:
        raise GateFailure(f"Path leaves the isolated root: {relpath}") from exc
    return path


def require_hash(relpath: str, expected: str, label: str) -> Path:
    path = resolve_relpath(relpath)
    require(path.is_file(), f"{label} is absent: {relpath}")
    expected_hash = hex64(expected, f"{label} expected SHA-256")
    actual = sha256_file(path)
    require(actual == expected_hash,
            f"{label} SHA-256 mismatch: expected {expected_hash}, actual {actual}")
    return path


def verify_manifest(
    path: Path, expected_rows: int | None = None
) -> dict[str, str]:
    try:
        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            fields = list(reader.fieldnames or [])
            rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise GateFailure(f"Cannot parse manifest {path}: {exc}") from exc
    require(fields == ["relpath", "bytes", "sha256"],
            f"Manifest fields mismatch: {path}")
    if expected_rows is not None:
        require(len(rows) == expected_rows, f"Manifest row count mismatch: {path}")
    observed: dict[str, str] = {}
    for row in rows:
        relpath = str(row.get("relpath", ""))
        pure = PurePosixPath(relpath)
        require(relpath != "" and not pure.is_absolute() and ".." not in pure.parts,
                f"Unsafe manifest relpath: {relpath}")
        require(relpath not in observed, f"Duplicate manifest relpath: {relpath}")
        artifact = (path.parent / Path(*pure.parts)).resolve()
        try:
            artifact.relative_to(path.parent.resolve())
        except ValueError as exc:
            raise GateFailure(f"Manifest path leaves its root: {relpath}") from exc
        require(artifact.is_file(), f"Manifest artifact is absent: {artifact}")
        expected_hash = hex64(row.get("sha256"), f"manifest {relpath} SHA-256")
        actual_hash = sha256_file(artifact)
        require(actual_hash == expected_hash,
                f"Manifest artifact hash mismatch: {relpath}")
        try:
            expected_bytes = int(str(row.get("bytes", "")))
        except ValueError as exc:
            raise GateFailure(f"Invalid manifest byte count: {relpath}") from exc
        require(artifact.stat().st_size == expected_bytes,
                f"Manifest artifact byte count mismatch: {relpath}")
        observed[relpath] = actual_hash
    return observed


def h5_text(value: Any) -> str:
    return value.decode("utf-8") if isinstance(value, bytes) else str(value)


def read_h5_records(path: Path) -> list[dict[str, Any]]:
    try:
        import h5py  # type: ignore
    except ImportError as exc:
        raise GateFailure("h5py is required for checkpoint validation.") from exc
    try:
        with h5py.File(path, "r") as handle:
            require(h5_text(handle.attrs.get("schema_version", "")) == H5_SCHEMA,
                    f"HDF5 schema mismatch: {path}")
            require(h5_text(handle.attrs.get("hard_residual_definition", ""))
                    == HARD_RESIDUAL_LABEL,
                    f"HDF5 hard-residual identity mismatch: {path}")
            require(h5_text(handle.attrs.get("vector_block_residual_role", ""))
                    == VECTOR_ROLE,
                    f"HDF5 vector role mismatch: {path}")
            require("points/record_json" in handle,
                    f"HDF5 record_json is absent: {path}")
            records: list[dict[str, Any]] = []
            for index, raw in enumerate(handle["points/record_json"].asstr()[...]):
                try:
                    item = json.loads(str(raw))
                except json.JSONDecodeError as exc:
                    raise GateFailure(
                        f"Invalid HDF5 record_json at {path}, index {index}"
                    ) from exc
                require(isinstance(item, dict),
                        f"HDF5 record_json is not an object: {path}, index {index}")
                records.append(item)
            return records
    except GateFailure:
        raise
    except Exception as exc:
        raise GateFailure(f"Cannot validate HDF5 {path}: {exc}") from exc


def verify_record_order(
    records: Sequence[Mapping[str, Any]], route_id: str,
    expected_points: Sequence[Sequence[int]],
) -> None:
    require(len(records) == len(expected_points),
            f"HDF5 point count mismatch for {route_id}.")
    for index, (record, expected) in enumerate(zip(records, expected_points)):
        require(record.get("route_id") == route_id,
                f"HDF5 route mismatch for {route_id}, index {index}.")
        actual = [int(record.get("l", -1)), int(record.get("j", -1))]
        require(actual == list(expected),
                f"HDF5 point order mismatch for {route_id}, index {index}.")


def load_contract() -> dict[str, Any]:
    contract = read_json(CONTRACT_PATH)
    require(contract.get("schema_version") == CONTRACT_SCHEMA,
            "Formal gate contract schema mismatch.")
    require(contract.get("contract_status") == "SEALED_AWAITING_ROOT_AUTHORIZATION",
            "Formal gate contract status mismatch.")
    require(contract.get("effective_full_authorization") is False,
            "Formal gate contract must never self-authorize.")
    return contract


def verify_external_authorization(
    contract: Mapping[str, Any], mode: str, checkpoint_every: int
) -> dict[str, Any]:
    require(AUTHORIZATION_PATH.is_file(),
            "SEALED_AWAITING_ROOT_AUTHORIZATION: code/full_authorization.json is absent; candidate was not invoked.")
    authorization = read_json(AUTHORIZATION_PATH)
    gate = contract["authorization_gate"]
    require(authorization.get("schema_version") == gate["schema_version"],
            "Authorization schema mismatch.")
    require(authorization.get("authorization_status")
            == gate["required_authorization_status"],
            "Authorization status mismatch.")
    require(authorization.get("effective_authorization")
            is gate["required_effective_authorization"],
            "Authorization is not effective.")
    require(authorization.get("authorized_modes")
            == gate["required_authorized_modes"],
            "Authorization must cover exactly full and resume.")
    require(mode in authorization["authorized_modes"],
            f"Requested mode is not authorized: {mode}")
    required_every = int(gate["required_checkpoint_every"])
    require(checkpoint_every == required_every
            and authorization.get("checkpoint_every") == required_every,
            f"Checkpoint cadence must be exactly {required_every}.")
    require(authorization.get("full_output_relpath")
            == contract["fixed_runtime"]["full_output_relpath"],
            "Authorization full output path mismatch.")

    identity = mapping(authorization.get("gate_identity_sha256"),
                       "gate_identity_sha256")
    expected_paths = {
        "contract": CONTRACT_PATH,
        "launcher": Path(__file__).resolve(),
        "revision": REVISION_PATH,
        "binding": BINDING_PATH,
    }
    require(set(identity) == set(gate["required_gate_hash_keys"]),
            "Authorization must bind exactly the four formal gate files.")
    for key, path in expected_paths.items():
        require(path.is_file(), f"Formal gate file is absent: {path}")
        expected_hash = hex64(identity.get(key), f"gate_identity_sha256.{key}")
        require(sha256_file(path) == expected_hash,
                f"Authorization does not bind the current formal gate {key}.")

    attestation = mapping(authorization.get("root_attestation"),
                          "root_attestation")
    required_attestation = gate["required_root_attestation"]
    for key in (
        "generated_by_role", "basis_type", "decision",
        "pilot_audit_was_pass_before_authorization",
        "formal_gate_was_independently_reviewed",
    ):
        require(attestation.get(key) == required_attestation[key],
                f"Root attestation mismatch: {key}")
    goal_text = attestation.get("user_original_goal_verbatim")
    require(isinstance(goal_text, str) and goal_text.strip() != "",
            "Root authorization must record the user's original goal verbatim.")
    goal_hash = hex64(attestation.get("user_original_goal_sha256"),
                      "root_attestation.user_original_goal_sha256")
    require(goal_hash == sha256_text(goal_text),
            "User original goal text/hash mismatch.")
    verify_formal_binding(contract, identity)
    return authorization


def verify_formal_binding(
    contract: Mapping[str, Any], identity: Mapping[str, Any]
) -> None:
    revision = read_json(REVISION_PATH)
    binding = read_json(BINDING_PATH)
    require(revision.get("schema_version")
            == "board20_step5_fullq_svd_candidate_v4_full_gate_revision_contract_v1",
            "Formal gate revision schema mismatch.")
    require(revision.get("status")
            == "SEALED_REVISION_SCOPE_POSTCHECK_PASS_AWAITING_ROOT_AUTHORIZATION",
            "Formal gate revision status mismatch.")
    require(binding.get("schema_version")
            == "board20_step5_fullq_svd_candidate_v4_full_gate_binding_record_v1",
            "Formal gate binding schema mismatch.")
    require(binding.get("status")
            == "SEALED_STATIC_REVIEW_PASS_AWAITING_ROOT_AUTHORIZATION",
            "Formal gate binding status mismatch.")
    formal = mapping(binding.get("formal_gate_identity"),
                     "binding formal_gate_identity")
    files = contract["formal_gate_files"]
    expected = {
        "contract_relpath": files["contract_relpath"],
        "contract_sha256": identity["contract"],
        "launcher_relpath": files["launcher_relpath"],
        "launcher_sha256": identity["launcher"],
        "revision_relpath": files["revision_relpath"],
        "revision_sha256": identity["revision"],
    }
    require(dict(formal) == expected,
            "Formal binding record does not bind contract/launcher/revision.")
    require(binding.get("full_authorization_existed_at_seal") is False
            and binding.get("full_directory_existed_at_seal") is False,
            "Formal binding was not sealed before authorization/full.")


def verify_candidate_gates(
    contract: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    runtime = contract["fixed_runtime"]
    gates = contract["candidate_gates"]
    require_hash(runtime["candidate_script_relpath"],
                 runtime["candidate_script_sha256"], "candidate script")
    candidate_contract_path = require_hash(
        runtime["candidate_contract_relpath"],
        runtime["candidate_contract_sha256"], "candidate contract"
    )
    candidate_contract = read_json(candidate_contract_path)
    seal_path = require_hash(runtime["input_seal_relpath"],
                             runtime["input_seal_sha256"], "input seal")
    seal = read_json(seal_path)
    require(seal.get("schema_version")
            == "board20_step5_fullq_svd_candidate_v4_input_seal_v4",
            "Input seal schema mismatch.")
    require(seal.get("candidate_script_sha256") == runtime["candidate_script_sha256"]
            and seal.get("candidate_contract_sha256")
            == runtime["candidate_contract_sha256"],
            "Input seal candidate identity mismatch.")

    for name in ("preflight", "selftest"):
        spec = gates[name]
        path = require_hash(spec["relpath"], spec["sha256"], name)
        document = read_json(path)
        for key in (
            "schema_version", "status", "check_count", "pass_count", "fail_count"
        ):
            require(document.get(key) == spec[key], f"{name} mismatch: {key}")
        checks = document.get("checks")
        require(isinstance(checks, list) and len(checks) == spec["check_count"],
                f"{name} check list length mismatch.")
        require(all(isinstance(item, dict) and item.get("status") == "PASS"
                    for item in checks), f"{name} contains a non-PASS check.")
        require(document.get("input_seal_sha256") == runtime["input_seal_sha256"],
                f"{name} input seal binding mismatch.")

    manifest_spec = gates["pilot_manifest"]
    manifest_path = require_hash(
        manifest_spec["relpath"], manifest_spec["sha256"], "pilot manifest"
    )
    verify_manifest(manifest_path, int(manifest_spec["row_count"]))
    actual_manifest_hash = sha256_file(manifest_path)

    repeat_spec = gates["pilot_repeatability"]
    repeat_path = require_hash(
        repeat_spec["relpath"], repeat_spec["sha256"], "pilot repeatability"
    )
    repeat = read_json(repeat_path)
    for key in ("schema_version", "status", "mode", "scientific_artifacts_match"):
        require(repeat.get(key) == repeat_spec[key],
                f"Pilot repeatability mismatch: {key}")
    baseline_key = repeat_spec["baseline_long_key"]
    repeat_key = repeat_spec["repeat_long_key"]
    require(baseline_key == "baseline_artifact_manifest_sha256"
            and repeat_key == "repeat_artifact_manifest_sha256",
            "Repeatability long-key contract mismatch.")
    require(repeat.get(baseline_key) == repeat.get(repeat_key)
            == actual_manifest_hash,
            "Pilot repeatability must satisfy baseline=repeat=actual manifest.")

    run_spec = gates["pilot_run_status"]
    run_path = require_hash(run_spec["relpath"], run_spec["sha256"],
                            "pilot run status")
    run_status = read_json(run_path)
    for key in (
        "schema_version", "status", "mode", "route_count",
        "expected_point_count", "completed_point_count", "pass_point_count",
        "fail_point_count",
    ):
        require(run_status.get(key) == run_spec[key],
                f"Pilot run-status mismatch: {key}")
    require(run_status.get("input_identity") == seal,
            "Pilot run status is not bound to the exact input seal.")

    baseline_spec = gates["pilot_run1_baseline"]
    baseline = read_json(require_hash(
        baseline_spec["relpath"], baseline_spec["sha256"],
        "candidate pilot run-1 baseline"
    ))
    require(baseline.get("candidate_status") == "PASS"
            and baseline.get("completed_point_count") == 49
            and baseline.get("fail_point_count") == 0
            and baseline.get("artifact_manifest_sha256") == actual_manifest_hash
            and baseline.get("full_run_authorized_by_this_record") is False,
            "Candidate pilot run-1 baseline mismatch.")
    external_spec = gates["pilot_external_repeatability"]
    external = read_json(require_hash(
        external_spec["relpath"], external_spec["sha256"],
        "candidate pilot external repeatability"
    ))
    require(external.get("status") == external_spec["status"]
            and external.get("candidate_run_count")
            == external_spec["candidate_run_count"]
            and external.get("artifact_count") == external_spec["artifact_count"]
            and external.get("artifact_byte_or_sha_mismatch_count")
            == external_spec["artifact_mismatch_count"]
            and external.get("protected_evidence_change_count")
            == external_spec["protected_evidence_change_count"]
            and external.get("scientific_artifacts_match") is True,
            "Candidate external repeatability mismatch.")
    require(external.get("baseline_artifact_manifest_sha256")
            == external.get("repeat_artifact_manifest_sha256")
            == external.get("externally_recomputed_artifact_manifest_sha256")
            == actual_manifest_hash,
            "Candidate external repeatability must satisfy baseline=repeat=actual.")
    require(external.get("full_run_or_postcheck_authorized_by_this_record") is False,
            "Candidate external repeatability must not authorize full.")
    verify_pilot_routes(contract, candidate_contract, seal, run_status)
    return seal, run_status


def verify_pilot_routes(
    contract: Mapping[str, Any], candidate_contract: Mapping[str, Any],
    seal: Mapping[str, Any], run_status: Mapping[str, Any],
) -> None:
    pilot_points = mapping(candidate_contract.get("pilot_points"), "pilot_points")
    embedded = run_status.get("route_statuses")
    require(isinstance(embedded, list) and len(embedded) == 5,
            "Pilot run status must contain five route statuses.")
    embedded_by_route = {
        item.get("route_id"): item for item in embedded if isinstance(item, dict)
    }
    require(len(embedded_by_route) == 5, "Pilot route identities are not unique.")
    for spec in contract["pilot_routes"]:
        route_id = spec["route_id"]
        status = read_json(require_hash(
            spec["route_status_relpath"], spec["route_status_sha256"],
            f"pilot route status {route_id}"
        ))
        checkpoint = read_json(require_hash(
            spec["checkpoint_json_relpath"], spec["checkpoint_json_sha256"],
            f"pilot checkpoint JSON {route_id}"
        ))
        h5_path = require_hash(
            spec["checkpoint_h5_relpath"], spec["checkpoint_h5_sha256"],
            f"pilot checkpoint HDF5 {route_id}"
        )
        points = pilot_points.get(route_id)
        require(isinstance(points, list) and len(points) == spec["expected_point_count"],
                f"Pilot point count contract mismatch for {route_id}.")
        order_hash = sha256_json(points)
        require(order_hash == spec["point_order_sha256"],
                f"Pilot point-order preregistration mismatch for {route_id}.")
        require(status == embedded_by_route.get(route_id),
                f"Embedded route status mismatch for {route_id}.")
        require(status.get("schema_version")
                == "board20_step5_fullq_svd_candidate_v4_route_status_v4"
                and status.get("status") == "PASS"
                and status.get("completed_point_count") == spec["expected_point_count"]
                and status.get("fail_point_count") == 0,
                f"Pilot route status is not sealed PASS for {route_id}.")
        require(checkpoint.get("schema_version") == CHECKPOINT_SCHEMA
                and checkpoint.get("state") == "COMPLETE"
                and checkpoint.get("completed_point_count")
                == spec["expected_point_count"]
                and checkpoint.get("point_order_sha256") == order_hash
                and checkpoint.get("checkpoint_h5_sha256")
                == spec["checkpoint_h5_sha256"],
                f"Pilot checkpoint identity mismatch for {route_id}.")
        require(checkpoint.get("candidate_script_sha256")
                == seal["candidate_script_sha256"]
                and checkpoint.get("candidate_contract_sha256")
                == seal["candidate_contract_sha256"],
                f"Pilot checkpoint candidate identity mismatch for {route_id}.")
        verify_record_order(read_h5_records(h5_path), route_id, points)


def verify_validator_postcheck(contract: Mapping[str, Any]) -> None:
    validator = contract["validator_v4_gate"]
    identity_paths: dict[str, Path] = {}
    for key in ("script", "contract", "revision", "binding"):
        item = validator[key]
        identity_paths[key] = require_hash(
            item["relpath"], item["sha256"], f"validator V4 {key}"
        )
    validator_contract = read_json(identity_paths["contract"])
    require(validator_contract.get("contract_status")
            == validator["required_contract_status"],
            "Validator V4 contract status mismatch.")
    activation = mapping(validator_contract.get("activation_policy"),
                         "validator activation_policy")
    require(activation.get("pilot_postcheck_enabled") is True
            and activation.get("full_postcheck_enabled") is False
            and activation.get("candidate_computation_may_be_launched_by_validator")
            is False,
            "Validator V4 activation boundary mismatch.")

    pre_spec = validator["precheck_repeatability"]
    pre = read_json(require_hash(pre_spec["relpath"], pre_spec["sha256"],
                                 "validator V4 precheck repeatability"))
    for key in (
        "schema_version", "status", "run_count", "artifact_count_compared",
        "artifact_mismatch_count", "each_run_fail_count",
        "protected_file_change_count_each_run",
    ):
        require(pre.get(key) == pre_spec[key],
                f"Validator precheck repeatability mismatch: {key}")
    require(pre.get("candidate_computation_authorized_by_this_record") is False
            and pre.get("full_postcheck_authorized_by_this_record") is False,
            "Validator precheck repeatability must not authorize computation/full.")
    pre_baseline_path = resolve_relpath(str(pre.get("run1_baseline_relpath", "")))
    require(pre_baseline_path.is_file()
            and sha256_file(pre_baseline_path) == pre.get("run1_baseline_sha256"),
            "Validator precheck repeatability baseline binding mismatch.")

    post = contract["pilot_postcheck_gate"]
    artifact_paths: dict[str, Path] = {}
    for relpath, expected_hash in post["artifacts"].items():
        artifact_paths[relpath] = require_hash(
            relpath, expected_hash, f"pilot postcheck artifact {relpath}"
        )
    main_relpath = (
        "outputs/step5_fullq_svd_candidate_audit_v4/"
        "v4_validator_v4_pilot_postcheck.json"
    )
    main = read_json(artifact_paths[main_relpath])
    require(main.get("schema_version") == post["main_schema_version"],
            "Pilot postcheck main schema mismatch.")
    summary = mapping(main.get("summary"), "pilot postcheck summary")
    for key, expected in post["required_summary"].items():
        require(summary.get(key) == expected,
                f"Pilot postcheck summary mismatch: {key}")
    checks = main.get("checks")
    require(isinstance(checks, list) and len(checks) == 97,
            "Pilot postcheck check count mismatch.")
    require(sum(item.get("status") == "PASS" for item in checks
                if isinstance(item, dict)) == 93
            and sum(item.get("status") == "INFO" for item in checks
                    if isinstance(item, dict)) == 4,
            "Pilot postcheck PASS/INFO distribution mismatch.")
    require(main.get("protected_hashes_before") == main.get("protected_hashes_after"),
            "Pilot postcheck reports protected-file changes.")
    main_validator = mapping(main.get("validator"), "pilot postcheck validator")
    require(main_validator.get("script_sha256") == validator["script"]["sha256"]
            and main_validator.get("contract_sha256")
            == validator["contract"]["sha256"],
            "Pilot postcheck validator identity mismatch.")
    auth_binding = mapping(main.get("authorization_binding"),
                           "pilot postcheck authorization_binding")
    runtime = contract["fixed_runtime"]
    candidate = contract["candidate_gates"]
    required_binding = {
        "candidate_script_sha256": runtime["candidate_script_sha256"],
        "candidate_contract_sha256": runtime["candidate_contract_sha256"],
        "input_seal_sha256": runtime["input_seal_sha256"],
        "run_status_sha256": candidate["pilot_run_status"]["sha256"],
        "artifact_manifest_sha256": candidate["pilot_manifest"]["sha256"],
        "repeatability_sha256": candidate["pilot_repeatability"]["sha256"],
        "validator_script_sha256": validator["script"]["sha256"],
        "validator_contract_sha256": validator["contract"]["sha256"],
        "candidate_status": "PASS",
        "mode": "pilot",
        "full_computation_launched_by_validator": False,
    }
    for key, expected in required_binding.items():
        require(auth_binding.get(key) == expected,
                f"Pilot postcheck authorization binding mismatch: {key}")

    manifest_relpath = (
        "outputs/step5_fullq_svd_candidate_audit_v4/"
        "v4_validator_v4_pilot_postcheck_artifact_manifest.csv"
    )
    observed_manifest = verify_manifest(artifact_paths[manifest_relpath], 7)
    for relpath, actual_hash in observed_manifest.items():
        full_relpath = (
            "outputs/step5_fullq_svd_candidate_audit_v4/" + relpath
        )
        require(post["artifacts"].get(full_relpath) == actual_hash,
                f"Pilot postcheck manifest is not bound in formal contract: {relpath}")

    baseline_spec = post["run1_baseline"]
    baseline_path = require_hash(
        baseline_spec["relpath"], baseline_spec["sha256"],
        "pilot postcheck run-1 baseline"
    )
    baseline = read_json(baseline_path)
    for key in ("schema_version", "status", "mode", "fail_count",
                "protected_file_change_count"):
        require(baseline.get(key) == baseline_spec[key],
                f"Pilot postcheck run-1 baseline mismatch: {key}")
    expected_validator_identity = {
        "script_sha256": validator["script"]["sha256"],
        "contract_sha256": validator["contract"]["sha256"],
        "revision_contract_sha256": validator["revision"]["sha256"],
        "binding_sha256": validator["binding"]["sha256"],
    }
    require(baseline.get("validator_identity") == expected_validator_identity,
            "Pilot postcheck run-1 validator identity mismatch.")
    require(baseline.get("run1_artifact_sha256") == post["artifacts"],
            "Pilot postcheck run-1 nine-artifact map mismatch.")
    require(baseline.get("second_pilot_postcheck_authorized_by_this_record") is False
            and baseline.get("full_computation_or_postcheck_authorized_by_this_record")
            is False,
            "Pilot postcheck run-1 baseline must not authorize another/full run.")

    repeat_spec = post["repeatability"]
    repeat = read_json(require_hash(
        repeat_spec["relpath"], repeat_spec["sha256"],
        "pilot postcheck repeatability"
    ))
    for key in (
        "schema_version", "status", "mode", "run_count",
        "each_run_fail_count", "each_run_protected_file_change_count",
        "artifact_count_compared", "artifact_mismatch_count",
        "hard_gate_failure_count",
    ):
        require(repeat.get(key) == repeat_spec[key],
                f"Pilot postcheck repeatability mismatch: {key}")
    require(repeat.get("run1_baseline_relpath") == baseline_spec["relpath"]
            and repeat.get("run1_baseline_sha256") == sha256_file(baseline_path),
            "Pilot postcheck repeatability baseline binding mismatch.")
    require(repeat.get("identical_artifact_sha256") == post["artifacts"],
            "Pilot postcheck two-run nine-artifact map mismatch.")
    require(repeat.get("full_computation_authorized_by_this_record") is False
            and repeat.get("full_postcheck_authorized_by_this_record") is False,
            "Pilot postcheck repeatability must not authorize full.")


def verify_lineage(contract: Mapping[str, Any]) -> None:
    lineage = contract["lineage"]
    require_hash(lineage["waiting_contract_relpath"],
                 lineage["waiting_contract_sha256"], "WAITING contract lineage")
    require_hash(lineage["waiting_launcher_relpath"],
                 lineage["waiting_launcher_sha256"], "WAITING launcher lineage")


def verify_all_sealed_evidence(
    contract: Mapping[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    verify_lineage(contract)
    seal, run_status = verify_candidate_gates(contract)
    verify_validator_postcheck(contract)
    return seal, run_status


def full_points(contract: Mapping[str, Any]) -> list[list[int]]:
    points = [[l_value, j_value] for l_value in range(31) for j_value in range(67)]
    policy = contract["full_and_resume_policy"]
    require(len(points) == policy["points_per_route"],
            "Full point count contract mismatch.")
    require(sha256_json(points) == policy["full_point_order_sha256"],
            "Full point order contract mismatch.")
    return points


def expected_checkpoint_identity(
    seal: Mapping[str, Any], route_id: str, point_order_hash: str
) -> dict[str, Any]:
    workspaces = mapping(seal.get("workspace_sha256"), "seal workspace_sha256")
    return {
        "schema_version": CHECKPOINT_SCHEMA,
        "candidate_script_sha256": seal["candidate_script_sha256"],
        "candidate_contract_sha256": seal["candidate_contract_sha256"],
        "route_manifest_sha256": seal["route_manifest_sha256"],
        "base_compute_sha256": seal["base_compute_sha256"],
        "v2_engine_sha256": seal["v2_engine_sha256"],
        "v3_reference_script_sha256": seal["v3_reference_script_sha256"],
        "static_diff_selftest_sha256": seal["static_diff_selftest_sha256"],
        "protected_evidence_sha256": sha256_json(seal["protected_evidence_sha256"]),
        "workspace_sha256": workspaces[route_id],
        "route_id": route_id,
        "point_order_sha256": point_order_hash,
        "hard_residual_math_sha256": seal["hard_residual_math_sha256"],
        "numeric_gates_sha256": seal["numeric_gates_sha256"],
    }


def verify_mode_boundary(
    contract: Mapping[str, Any], seal: Mapping[str, Any], mode: str
) -> None:
    full_root = resolve_relpath(contract["fixed_runtime"]["full_output_relpath"])
    if mode == "full":
        require(not full_root.exists(),
                "Initial full requires the full output path to be absent.")
        return
    require(full_root.is_dir(), "Resume requires an existing full directory.")
    route_ids = [item["route_id"] for item in contract["pilot_routes"]]
    observed_dirs = sorted(path.name for path in full_root.iterdir() if path.is_dir())
    require(observed_dirs == sorted(route_ids),
            "Resume requires exactly five contracted route directories.")
    points = full_points(contract)
    order_hash = sha256_json(points)
    allowed_states = set(
        contract["full_and_resume_policy"]["resume_allowed_checkpoint_states"]
    )
    for route_id in route_ids:
        route_root = full_root / route_id
        json_path = route_root / "checkpoint.json"
        h5_path = route_root / "checkpoint.h5"
        require(json_path.is_file() and h5_path.is_file(),
                f"Resume checkpoint pair is absent for {route_id}.")
        checkpoint = read_json(json_path)
        for key, expected in expected_checkpoint_identity(
            seal, route_id, order_hash
        ).items():
            require(checkpoint.get(key) == expected,
                    f"Resume checkpoint identity mismatch for {route_id}: {key}")
        state = checkpoint.get("state")
        require(state in allowed_states,
                f"Resume checkpoint state is invalid for {route_id}: {state}")
        count = checkpoint.get("completed_point_count")
        require(isinstance(count, int) and 0 <= count <= len(points),
                f"Resume checkpoint point count is invalid for {route_id}.")
        if state == "COMPLETE":
            require(count == len(points),
                    f"COMPLETE checkpoint is incomplete for {route_id}.")
        else:
            require(count < len(points),
                    f"IN_PROGRESS checkpoint contains a full grid for {route_id}.")
        expected_h5_hash = hex64(checkpoint.get("checkpoint_h5_sha256"),
                                 f"resume checkpoint HDF5 {route_id}")
        require(sha256_file(h5_path) == expected_h5_hash,
                f"Resume checkpoint HDF5 hash mismatch for {route_id}.")
        records = read_h5_records(h5_path)
        require(len(records) == count,
                f"Resume checkpoint JSON/HDF5 count mismatch for {route_id}.")
        verify_record_order(records, route_id, points[:count])


def candidate_command(
    contract: Mapping[str, Any], mode: str, checkpoint_every: int
) -> list[str]:
    runtime = contract["fixed_runtime"]
    python_path = Path(runtime["python_executable"])
    require(python_path.is_absolute() and python_path.is_file(),
            f"Fixed Python executable is absent: {python_path}")
    candidate_path = resolve_relpath(runtime["candidate_script_relpath"])
    require(candidate_path.is_file(), "Candidate script disappeared after checks.")
    return [
        str(python_path), str(candidate_path), "--mode", mode,
        "--explicit-full-authorization", "--checkpoint-every",
        str(checkpoint_every),
    ]


def run_all_gates(mode: str, checkpoint_every: int) -> list[str]:
    contract = load_contract()
    verify_external_authorization(contract, mode, checkpoint_every)
    seal, _run_status = verify_all_sealed_evidence(contract)
    verify_mode_boundary(contract, seal, mode)
    return candidate_command(contract, mode, checkpoint_every)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Formal fail-closed V2 launcher for Board-20 Step-5 V4 full/resume. "
            "Current state: SEALED_AWAITING_ROOT_AUTHORIZATION."
        )
    )
    parser.add_argument(
        "--mode", required=True, choices=("full", "resume"),
        help="full requires an absent full directory; resume validates five checkpoints.",
    )
    parser.add_argument(
        "--checkpoint-every", type=int, default=25,
        help="Fixed authorized checkpoint cadence (default and required: 25).",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    candidate_invoked = False
    try:
        command = run_all_gates(args.mode, args.checkpoint_every)
    except Exception as exc:
        print(json.dumps({
            "schema_version": "board20_step5_fullq_svd_candidate_v4_full_gate_v2_result_v1",
            "status": "SEALED_FAIL_CLOSED",
            "requested_mode": args.mode,
            "candidate_invoked": candidate_invoked,
            "full_directory_created_by_launcher": False,
            "authorization_relpath": AUTHORIZATION_RELPATH,
            "reason": str(exc),
        }, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 3

    print(json.dumps({
        "schema_version": "board20_step5_fullq_svd_candidate_v4_full_gate_v2_result_v1",
        "status": "ALL_FORMAL_GATES_PASS_LAUNCHING_CANDIDATE",
        "requested_mode": args.mode,
        "checkpoint_every": args.checkpoint_every,
        "shell": False,
        "candidate_command_argv": command,
    }, ensure_ascii=False, sort_keys=True))
    candidate_invoked = True
    completed = subprocess.run(
        command, cwd=str(ROOT), shell=False, check=False
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())

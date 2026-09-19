from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import h5py
import numpy as np
from scipy.io import loadmat, savemat


SCRIPT = Path(__file__).resolve()
BOARD_ROOT = SCRIPT.parent.parent.resolve()
DEFAULT_MANIFEST = SCRIPT.parent / "board20_step4_route_manifest.json"
DEFAULT_SCHEMA = SCRIPT.parent / "board20_step4_validation_contract.json"
DEFAULT_OUTPUT_ROOT = BOARD_ROOT / "outputs" / "step4_rho_grids"

RHO_TOL = 1.0e-8
RESIDUAL_TOL = 1.0e-8
CRITICAL_TOL = 1.0e-8
SENTINEL_TOL = 1.0e-15

PRIMARY_ROUTE_IDS = {
    "main_ori_div1",
    "main_guyan_div1",
    "main_ori_div2",
    "main_guyan_div2",
}
ALTERNATIVE_ROUTE_ID = "alt_guyan_div1_stable_full_ps3"
SUCCESS_ROUTE_IDS = PRIMARY_ROUTE_IDS | {ALTERNATIVE_ROUTE_ID}
FAILED_ROUTE_IDS = {
    "main_cb_div1",
    "main_cb_div2",
    "energy_guyan_div1",
    "energy_guyan_div2",
}

# These are immutable facts from the completed step-2 evidence package.  Keeping
# them in this independent validator prevents a modified live manifest from
# silently redefining its own upstream truth.
STEP2: dict[str, dict[str, Any]] = {
    "main_ori_div1": {
        "replicate": "rep03",
        "terminal": "SUCCESS",
        "formula": "ORI_DIV1_H_RIGHT",
        "division": "div1",
        "role": "PRIMARY",
        "author_points": 441,
        "active_points": 1,
        "commented_points": 440,
        "supplemental_points": 1636,
        "author_shape": (21, 21),
        "raw_shape": (20, 20),
        "required_workspace": {
            "MRrt": (15, 15),
            "C1": (15, 15),
            "K1": (15, 15),
            "C2": (15, 15),
            "K2": (15, 15),
            "al": (15, 15),
            "dt": (1, 1),
        },
        "sha256": {
            "run_config": "76A951B9A998CD2219EDFB7498FC49B33AD90EEA65878255C7C483D2E89A4DB4",
            "run_status": "D0DC8000FD222B7A64BF7DEE9A4BA63B34755F0E25127D9205CE29CA117BE4CC",
            "workspace": "E0FFF9B1B0CFF5DB7013FE888D8A5957D3AC8776952EA40446109FE5A1C35923",
            "raw_stab": "FC47A86F4ECE4F5C84323C2135520C76055C76D1EFD9692F7D21A5FFC8A026BA",
        },
    },
    "main_guyan_div1": {
        "replicate": "rep03",
        "terminal": "SUCCESS",
        "formula": "GUYAN_DIV1_H_LEFT",
        "division": "div1",
        "role": "PRIMARY",
        "author_points": 441,
        "active_points": 441,
        "commented_points": 0,
        "supplemental_points": 1636,
        "author_shape": (21, 21),
        "raw_shape": (21, 21),
        "required_workspace": {
            "MRren": (5, 5),
            "C1": (5, 5),
            "K1": (5, 5),
            "C2": (5, 5),
            "K2": (5, 5),
            "al": (5, 5),
            "dt": (1, 1),
        },
        "sha256": {
            "run_config": "1DBF7929BCD096F02D294AED29AF196A92F8289A51DF770599816C07F7C097D6",
            "run_status": "BD86753392039D45F5444621F370A50BB83B891861BEF351D49DAA752E3E1DF3",
            "workspace": "2CE61CAC0828B9D7DF1151B456A559D051CF6C48C60714756CCFABE03E392FD7",
            "raw_stab": "FEA2C539A79EE9A2E20AA05E2C02B5E559DD8D2ADCDDA646BA227FB3EA515237",
        },
    },
    "alt_guyan_div1_stable_full_ps3": {
        "replicate": "rep01",
        "terminal": "SUCCESS",
        "formula": "GUYAN_DIV1_H_LEFT",
        "division": "div1",
        "role": "ALTERNATIVE_NOT_PRIMARY",
        "author_points": 441,
        "active_points": 441,
        "commented_points": 0,
        "supplemental_points": 1636,
        "author_shape": (21, 21),
        "raw_shape": (21, 21),
        "required_workspace": {
            "MRren": (5, 5),
            "C1": (5, 5),
            "K1": (5, 5),
            "C2": (5, 5),
            "K2": (5, 5),
            "al": (5, 5),
            "dt": (1, 1),
        },
        "sha256": {
            "run_config": "65F6CE0A87E950197D6F5D1AAEE0D17787EE53ACC59023F06F2E33F3B87ACDDF",
            "run_status": "F2C5A93034D93273939784C5B8BCE29D7E0390CEC96DAFBAD1F15CC13D0C8A71",
            "workspace": "5264AAE6FFACD10E87E4EA7067CD00EF547F0AA850BFC9CAAA1443C923DEC305",
            "raw_stab": "D70FF3F74B8771794AB91D821EA1BA5BC66532C6972191E9AFA0A6135EC98BCA",
        },
    },
    "main_ori_div2": {
        "replicate": "rep03",
        "terminal": "SUCCESS",
        "formula": "DIV2_H_LEFT_FEEDBACK_OUTSIDE",
        "division": "div2",
        "role": "PRIMARY",
        "author_points": 1517,
        "active_points": 1517,
        "commented_points": 0,
        "supplemental_points": 560,
        "author_shape": (26, 67),
        "raw_shape": (26, 67),
        "required_workspace": {
            "MRren": (5, 5),
            "C1": (5, 5),
            "K1": (5, 5),
            "C2": (5, 5),
            "K2": (5, 5),
            "al": (5, 5),
            "dt": (1, 1),
            "S": (2, 5),
            "DeltaC": (2, 2),
            "DeltaK": (2, 2),
        },
        "sha256": {
            "run_config": "6C8164ED4F659642A118C5453E6C2807027F0C1CDCBC1B33DE7B29A0DA51823A",
            "run_status": "658ABA74288920BA5E2DF999FF211E2D5C049F6B419216024EF5CDBD3652D5B3",
            "workspace": "7781807F01B9D95CA9554F3AE5449065C4DEB4C2FF8FFC62679E08BEC8757061",
            "raw_stab": "C4EA3005174054829456C24C74770F57ADF422DFD075A39E347CBA6876899E85",
        },
    },
    "main_guyan_div2": {
        "replicate": "rep03",
        "terminal": "SUCCESS",
        "formula": "DIV2_H_LEFT_FEEDBACK_OUTSIDE",
        "division": "div2",
        "role": "PRIMARY",
        "author_points": 1517,
        "active_points": 1517,
        "commented_points": 0,
        "supplemental_points": 560,
        "author_shape": (26, 67),
        "raw_shape": (26, 67),
        "required_workspace": {
            "MRren": (5, 5),
            "C1": (5, 5),
            "K1": (5, 5),
            "C2": (5, 5),
            "K2": (5, 5),
            "al": (5, 5),
            "dt": (1, 1),
            "S": (2, 5),
            "DeltaC": (2, 2),
            "DeltaK": (2, 2),
        },
        "sha256": {
            "run_config": "D86844031A20C270AA6D8EC680FC94E6DF73FE5B962D590935A7F4DFB66A37E4",
            "run_status": "790ADB62FB1EA25B82DD73495A197327B002EDF4B9FF07AF3D20545433444AD9",
            "workspace": "5B677B11EDCEC3AA7EE4955BE7B46ADB3F1BC7957BD7A7673456AE3F24476F21",
            "raw_stab": "798BF53D873943F3CE17EFDE69F10D7CD94FF055539CE80B5FC317499664433D",
        },
    },
    "main_cb_div1": {
        "replicate": "rep02",
        "terminal": "EXECUTION_FAIL",
        "missing_symbol": "MRren",
        "sha256": {
            "run_config": "36700A4F24FECC621EEAFCA1C0BA2C389DA1C0C9990A492044389F5F5C961E8E",
            "run_status": "F4D4E3318D913029E8937856ECA1F49FDF9D6913AEDE34106F3A5F99850A330D",
            "workspace": "EDEF15BC3A9E5966830E81F9FA5F338684EC2BE8AFC064AC3EB12EC9D8D59516",
        },
    },
    "main_cb_div2": {
        "replicate": "rep02",
        "terminal": "EXECUTION_FAIL",
        "missing_symbol": "MRren",
        "sha256": {
            "run_config": "E5CF4931FC0859CCA3EA9C7796B7F3F85FD433BFCF39D8F4F895F513FDFC5B38",
            "run_status": "53E67624B1F2E8B70E347D4FA2E0F4403859AD86A515C81640583310A3515061",
            "workspace": "964DDA02559E5AEDEC698350A3FC839F884801088053499EC42B89B706A03F10",
        },
    },
    "energy_guyan_div1": {
        "replicate": "rep02",
        "terminal": "EXECUTION_FAIL",
        "missing_symbol": "KPren",
        "sha256": {
            "run_config": "C4BA508DD4E397F4999E34AB5E439ED3B35C8152DDC8BFF9B2BA8FCD52DFDA70",
            "run_status": "AD2F98B43D5BDC0CBF1F0980CE9073325144E41FA80B31097CCDACC4D6BAE141",
            "workspace": "2BF1E8519FF971C1D8316D86673C594EFE74842CE2498BC7BFEC3FC269E8D848",
        },
    },
    "energy_guyan_div2": {
        "replicate": "rep02",
        "terminal": "EXECUTION_FAIL",
        "missing_symbol": "KPren",
        "sha256": {
            "run_config": "8EB91BD7A252ED60FE9965F53824D8EBE18EB2ED7E985AF1B950C09A042D1028",
            "run_status": "29FBC2E1DC5C25BD6949CA45DE36738E5EE432E12F565F2A18F54C38BE6BA33F",
            "workspace": "B66FAF62642E59C508D1B69628A3E4563543B3E7D7BFC3DE415EA78FC8F40801",
        },
    },
}


@dataclass
class Check:
    check_id: str
    name: str
    expected: Any
    actual: Any
    status: str
    evidence: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "expected": self.expected,
            "actual": self.actual,
            "status": self.status,
            "evidence": self.evidence,
        }


class CheckLog:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.checks: list[Check] = []

    def add(
        self,
        name: str,
        expected: Any,
        actual: Any,
        passed: bool,
        evidence: str = "",
    ) -> None:
        self.checks.append(
            Check(
                check_id=f"{self.prefix}-{len(self.checks) + 1:04d}",
                name=name,
                expected=expected,
                actual=actual,
                status="PASS" if passed else "FAIL",
                evidence=evidence,
            )
        )

    @property
    def passed(self) -> bool:
        return all(item.status == "PASS" for item in self.checks)

    def summary(self) -> dict[str, int | str]:
        passed = sum(item.status == "PASS" for item in self.checks)
        failed = len(self.checks) - passed
        return {
            "status": "PASS" if failed == 0 else "FAIL",
            "total": len(self.checks),
            "passed": passed,
            "failed": failed,
        }


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_board_path(value: str | Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = BOARD_ROOT / path
    return path.resolve()


def normalize_division(value: Any) -> str:
    text = str(value).strip().lower()
    if text in {"1", "div1", "division1", "第一类", "第一类子结构划分"}:
        return "div1"
    if text in {"2", "div2", "division2", "第二类", "第二类子结构划分"}:
        return "div2"
    return text


def route_id_of(item: Any) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, Mapping):
        return str(item.get("route_id", ""))
    return ""


def step2_base(route_id: str) -> Path:
    replicate = STEP2[route_id]["replicate"]
    return (
        BOARD_ROOT
        / "outputs"
        / "step2_runs"
        / route_id
        / "original_mlx"
        / replicate
    )


def step2_paths(route_id: str) -> dict[str, Path]:
    base = step2_base(route_id)
    success = STEP2[route_id]["terminal"] == "SUCCESS"
    paths = {
        "run_config": base / "metadata" / "run_config.json",
        "run_status": base / "metadata" / "run_status.json",
        "workspace": base
        / "workspace"
        / ("workspace_complete.mat" if success else "workspace_failure.mat"),
    }
    if success:
        paths["raw_stab"] = base / "scientific" / "raw_stab.mat"
    return paths


def _matlab_class(node: h5py.Dataset | h5py.Group) -> str:
    value = node.attrs.get("MATLAB_class", b"")
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, np.ndarray) and value.size:
        first = value.reshape(-1)[0]
        return (
            first.decode("utf-8", errors="replace")
            if isinstance(first, bytes)
            else str(first)
        )
    return str(value)


def _restore_matlab_axes(array: np.ndarray) -> np.ndarray:
    if array.ndim < 2:
        return array
    return np.transpose(array, axes=tuple(range(array.ndim - 1, -1, -1)))


def _decode_hdf5_node(handle: h5py.File, node: h5py.Dataset | h5py.Group) -> Any:
    if isinstance(node, h5py.Group):
        return {
            key: _decode_hdf5_node(handle, child)
            for key, child in node.items()
            if not key.startswith("#")
        }

    matlab_class = _matlab_class(node)
    raw = np.asarray(node)
    if matlab_class == "cell" or raw.dtype.kind == "O":
        refs = _restore_matlab_axes(raw)
        decoded = np.empty(refs.shape, dtype=object)
        for index in np.ndindex(refs.shape):
            ref = refs[index]
            if ref:
                decoded[index] = _decode_hdf5_node(handle, handle[ref])
            else:
                decoded[index] = ""
        return decoded

    array = _restore_matlab_axes(raw)
    if matlab_class == "char":
        chars = np.asarray(array, dtype=np.uint32)
        if chars.ndim <= 1 or 1 in chars.shape:
            return "".join(chr(int(code)) for code in chars.reshape(-1) if int(code))
        rows: list[str] = []
        for row in chars:
            rows.append("".join(chr(int(code)) for code in row if int(code)))
        return np.asarray(rows, dtype=object)
    if matlab_class == "logical":
        return array.astype(bool)
    return array


def load_mat_variables(path: Path) -> tuple[dict[str, Any], str]:
    """Load MATLAB v5-v7.3 variables while restoring MATLAB dimensions."""
    try:
        loaded = loadmat(path, squeeze_me=False, struct_as_record=False)
        return (
            {key: value for key, value in loaded.items() if not key.startswith("__")},
            "scipy.io.loadmat",
        )
    except (NotImplementedError, ValueError, OSError):
        with h5py.File(path, "r") as handle:
            result = {
                key: _decode_hdf5_node(handle, node)
                for key, node in handle.items()
                if not key.startswith("#")
            }
        return result, "h5py MATLAB-v7.3"


def mat_shapes(path: Path) -> tuple[dict[str, tuple[int, ...]], str]:
    values, loader = load_mat_variables(path)
    result: dict[str, tuple[int, ...]] = {}
    for key, value in values.items():
        if isinstance(value, np.ndarray):
            result[key] = tuple(int(number) for number in value.shape)
        elif np.isscalar(value):
            result[key] = (1, 1)
    return result, loader


def numeric_scalar(value: Any, default: int = -1) -> int:
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return default


def expand_regions(regions: Any) -> tuple[set[tuple[int, int]], list[str]]:
    points: set[tuple[int, int]] = set()
    errors: list[str] = []
    if regions is None:
        return points, errors
    if isinstance(regions, Mapping):
        regions = [regions]
    if not isinstance(regions, list):
        return points, ["regions不是列表"]
    for index, region in enumerate(regions):
        if isinstance(region, (list, tuple)) and len(region) == 4:
            l_start, l_end, j_start, j_end = map(int, region)
        elif isinstance(region, Mapping):
            try:
                l_start = int(region["l_start"])
                l_end = int(region["l_end"])
                j_start = int(region["j_start"])
                j_end = int(region["j_end"])
            except (KeyError, TypeError, ValueError):
                errors.append(f"region[{index}]字段不完整")
                continue
        else:
            errors.append(f"region[{index}]格式不支持")
            continue
        if min(l_start, j_start) < 0 or l_end < l_start or j_end < j_start:
            errors.append(f"region[{index}]范围非法")
            continue
        points.update(
            (l_value, j_value)
            for l_value in range(l_start, l_end + 1)
            for j_value in range(j_start, j_end + 1)
        )
    return points, errors


def coordinates_from_raw(raw: np.ndarray) -> set[tuple[int, int]]:
    mask = np.isfinite(raw) & (raw > 0)
    return {tuple(map(int, pair)) for pair in np.argwhere(mask)}


def values_at(array: np.ndarray, points: set[tuple[int, int]]) -> np.ndarray:
    if not points:
        return np.asarray([], dtype=array.dtype)
    ordered = sorted(points)
    return np.asarray([array[l_value, j_value] for l_value, j_value in ordered])


def normalize_contract_entries(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, Mapping):
        result: list[dict[str, Any]] = []
        for key, item in value.items():
            if isinstance(item, Mapping):
                row = dict(item)
                row.setdefault("kind", str(key))
                result.append(row)
        return result
    if isinstance(value, list):
        return [dict(item) for item in value if isinstance(item, Mapping)]
    return []


def contract_path(entry: Mapping[str, Any]) -> Path | None:
    value = (
        entry.get("path")
        or entry.get("relative_path")
        or entry.get("relpath")
        or entry.get("source_relpath")
    )
    if not value:
        return None
    return resolve_board_path(str(value))


def contract_hash(entry: Mapping[str, Any]) -> str:
    return str(entry.get("sha256") or entry.get("expected_sha256") or "").upper()


def validate_live_file_contracts(
    log: CheckLog,
    route_id: str,
    entries: Any,
    required_paths: set[Path],
) -> None:
    rows = normalize_contract_entries(entries)
    failures: list[str] = []
    covered: set[Path] = set()
    for index, row in enumerate(rows):
        path = contract_path(row)
        expected_hash = contract_hash(row)
        if path is None:
            failures.append(f"row={index}:missing_path")
            continue
        covered.add(path)
        if not is_within(path, BOARD_ROOT):
            failures.append(f"row={index}:outside_board:{path}")
            continue
        if not path.is_file():
            failures.append(f"row={index}:missing:{path}")
            continue
        actual_hash = sha256_file(path)
        if len(expected_hash) != 64 or actual_hash != expected_hash:
            failures.append(
                f"row={index}:hash:{path.name}:expected={expected_hash}:actual={actual_hash}"
            )
    missing_coverage = sorted(str(path) for path in required_paths - covered)
    passed = bool(rows) and not failures and not missing_coverage
    log.add(
        f"{route_id}步骤4清单文件合同实时SHA-256",
        {
            "minimum_contracts": len(required_paths),
            "required_paths_covered": len(required_paths),
            "failures": [],
        },
        {
            "contracts": len(rows),
            "required_paths_covered": len(required_paths & covered),
            "missing_coverage": missing_coverage,
            "failures": failures[:10],
        },
        passed,
        "route.file_contracts",
    )


def validate_step2_config_and_code(
    log: CheckLog,
    route_id: str,
    config: Mapping[str, Any],
    status: Mapping[str, Any],
    require_instrumentation: bool,
) -> None:
    config_rows = normalize_contract_entries(config.get("file_contracts"))
    live_failures: list[str] = []
    for index, row in enumerate(config_rows):
        path = contract_path(row)
        expected_hash = contract_hash(row)
        if path is None or not path.is_file():
            live_failures.append(f"row={index}:missing")
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            live_failures.append(f"row={index}:{path.name}:hash_mismatch")
    log.add(
        f"{route_id}步骤2输入代码实时哈希",
        {"contracts": len(config_rows), "failures": []},
        {"contracts": len(config_rows), "failures": live_failures},
        bool(config_rows) and not live_failures,
        "step2 run_config.file_contracts",
    )

    before = status.get("input_hashes_before")
    after = status.get("input_hashes_after")
    before_rows = before if isinstance(before, list) else []
    after_rows = after if isinstance(after, list) else []
    before_ok = bool(before_rows) and all(bool(row.get("match")) for row in before_rows)
    after_ok = bool(after_rows) and all(bool(row.get("match")) for row in after_rows)
    log.add(
        f"{route_id}步骤2输入运行前后未改变",
        {"before_all_match": True, "after_all_match": True},
        {
            "before_count": len(before_rows),
            "before_all_match": before_ok,
            "after_count": len(after_rows),
            "after_all_match": after_ok,
        },
        before_ok and after_ok and len(before_rows) == len(after_rows),
        "step2 run_status.input_hashes_before/after",
    )

    config_instrumentation = config.get("instrumentation")
    instrumentation_rows: list[dict[str, Any]] = []
    if isinstance(config_instrumentation, Mapping):
        for name, value in config_instrumentation.items():
            if isinstance(value, Mapping):
                row = dict(value)
                row["name"] = name
                instrumentation_rows.append(row)
    instrumentation_failures: list[str] = []
    for row in instrumentation_rows:
        path_value = row.get("path")
        path = Path(str(path_value)).resolve() if path_value else None
        expected_hash = str(row.get("sha256", "")).upper()
        if path is None or not path.is_file():
            instrumentation_failures.append(f"{row.get('name')}:missing")
        elif sha256_file(path) != expected_hash:
            instrumentation_failures.append(f"{row.get('name')}:hash_mismatch")
    if require_instrumentation:
        expected_instrumentation: Any = {"count": 3, "failures": []}
        instrumentation_passed = (
            len(instrumentation_rows) == 3 and not instrumentation_failures
        )
    else:
        # The four rep02 failure captures predate the v2 instrumentation seal.
        # Their actual candidate/upstream code is still fully covered by the
        # run_config.file_contracts check above, so absence of this duplicate
        # three-file seal is an explicit historical fact rather than a bypass.
        expected_instrumentation = {
            "historical_state": "NOT_RECORDED_ALLOWED_FOR_EXECUTION_FAIL_REP02",
            "count": 0,
            "failures": [],
        }
        instrumentation_passed = (
            len(instrumentation_rows) == 0 and not instrumentation_failures
        )
    log.add(
        f"{route_id}步骤2运行基础设施代码密封",
        expected_instrumentation,
        {
            "count": len(instrumentation_rows),
            "failures": instrumentation_failures,
            "input_code_contract_already_checked": True,
        },
        instrumentation_passed,
        "step2 run_config.instrumentation",
    )


def count_value(value: Any) -> int:
    if isinstance(value, (int, np.integer)):
        return int(value)
    if isinstance(value, list):
        return len(value)
    return -1


def grid_path(grid: Mapping[str, Any]) -> Path | None:
    value = (
        grid.get("output_relpath")
        or grid.get("path")
        or grid.get("mat_relpath")
        or grid.get("output_path")
    )
    return resolve_board_path(str(value)) if value else None


def output_root_from_manifest(manifest: Mapping[str, Any]) -> Path:
    value = manifest.get("output_root_relpath") or manifest.get("output_root")
    return resolve_board_path(str(value)) if value else DEFAULT_OUTPUT_ROOT.resolve()


def validate_route_regions(
    log: CheckLog,
    route_id: str,
    route: Mapping[str, Any],
    raw: np.ndarray,
) -> tuple[set[tuple[int, int]], set[tuple[int, int]]]:
    expected = STEP2[route_id]
    active, active_errors = expand_regions(route.get("active_regions"))
    commented, commented_errors = expand_regions(
        route.get("commented_author_intent_regions")
    )
    raw_active = coordinates_from_raw(raw)

    region_metadata_failures: list[str] = []
    for key, expected_provenance in (
        ("active_regions", "ORIGINAL_ACTIVE_POINT"),
        ("commented_author_intent_regions", "COMMENTED_AUTHOR_INTENT"),
    ):
        region_items = route.get(key) or []
        if isinstance(region_items, Mapping):
            region_items = [region_items]
        for index, region in enumerate(region_items):
            if not isinstance(region, Mapping):
                continue
            provenance = str(region.get("provenance", expected_provenance))
            grids = set(str(item) for item in region.get("grids", []))
            if provenance != expected_provenance:
                region_metadata_failures.append(
                    f"{key}[{index}].provenance={provenance}"
                )
            if grids and not grids.issubset({"author_code_grid", "common_grid"}):
                region_metadata_failures.append(f"{key}[{index}].grids={sorted(grids)}")

    author_shape = tuple(expected["author_shape"])
    common_shape = (31, 67)
    all_declared = active | commented
    out_of_author = sorted(
        point
        for point in all_declared
        if not (0 <= point[0] < author_shape[0] and 0 <= point[1] < author_shape[1])
    )
    out_of_common = sorted(
        point
        for point in all_declared
        if not (0 <= point[0] < common_shape[0] and 0 <= point[1] < common_shape[1])
    )
    overlap = active & commented

    log.add(
        f"{route_id}原样活动区域与步骤2 raw_stab 一致",
        {
            "active_count": expected["active_points"],
            "raw_active_count": expected["active_points"],
            "set_difference": 0,
        },
        {
            "active_count": len(active),
            "raw_active_count": len(raw_active),
            "symmetric_difference": len(active ^ raw_active),
            "errors": active_errors,
        },
        not active_errors
        and len(active) == expected["active_points"]
        and active == raw_active,
        "route.active_regions + step2 raw_stab finite positive coordinates",
    )
    log.add(
        f"{route_id}注释循环意图区域",
        {
            "commented_count": expected["commented_points"],
            "overlap": 0,
            "out_of_bounds": 0,
        },
        {
            "commented_count": len(commented),
            "overlap": len(overlap),
            "out_of_author": len(out_of_author),
            "out_of_common": len(out_of_common),
            "errors": commented_errors,
            "metadata_failures": region_metadata_failures,
        },
        not commented_errors
        and not region_metadata_failures
        and len(commented) == expected["commented_points"]
        and not overlap
        and not out_of_author
        and not out_of_common,
        "route.commented_author_intent_regions",
    )
    return active, commented


def validate_success_route_precheck(
    log: CheckLog,
    route_id: str,
    route: Mapping[str, Any],
) -> None:
    expected = STEP2[route_id]
    paths = step2_paths(route_id)
    base = step2_base(route_id)
    expected_relbase = base.relative_to(BOARD_ROOT).as_posix()

    role = str(route.get("route_role") or route.get("role") or "")
    formula = str(route.get("route_formula") or route.get("formula") or "")
    division = normalize_division(route.get("division"))
    source_relbase = str(route.get("source_step2_relpath", "")).replace("\\", "/").rstrip("/")
    log.add(
        f"{route_id}身份、公式与主/备用角色",
        {
            "division": expected["division"],
            "formula": expected["formula"],
            "role": expected["role"],
            "source_step2_relpath": expected_relbase,
        },
        {
            "division": division,
            "formula": formula,
            "role": role,
            "source_step2_relpath": source_relbase,
        },
        division == expected["division"]
        and formula == expected["formula"]
        and role == expected["role"]
        and source_relbase == expected_relbase,
        "route manifest",
    )

    # raw_stab is independently sealed by the validator's immutable step-2
    # hash table below.  The route manifest's four-file contract intentionally
    # covers workspace/config/status/extracted-author-code.
    required_manifest_paths: set[Path] = {
        paths["workspace"],
        paths["run_config"],
        paths["run_status"],
    }
    source_m_value = route.get("source_m_relpath") or route.get("source_m")
    if source_m_value:
        source_m_path = resolve_board_path(str(source_m_value))
        required_manifest_paths.add(source_m_path)
    validate_live_file_contracts(
        log, route_id, route.get("file_contracts"), required_manifest_paths
    )

    expected_route_fields = {
        "workspace_relpath": paths["workspace"],
        "run_config_relpath": paths["run_config"],
        "run_status_relpath": paths["run_status"],
    }
    route_path_failures: list[str] = []
    for field, expected_path in expected_route_fields.items():
        value = route.get(field)
        if value is None or resolve_board_path(str(value)) != expected_path.resolve():
            route_path_failures.append(field)
    log.add(
        f"{route_id}步骤2证据路径唯一",
        [],
        route_path_failures,
        not route_path_failures,
        "route workspace/config/status/raw paths",
    )

    missing = [key for key, path in paths.items() if not path.is_file()]
    hash_actual = {
        key: sha256_file(path) if path.is_file() else None for key, path in paths.items()
    }
    hash_expected = expected["sha256"]
    hash_failures = [
        key
        for key in hash_expected
        if hash_actual.get(key) != hash_expected.get(key)
    ]
    log.add(
        f"{route_id}步骤2配置、状态、工作区和原始谱半径密封",
        hash_expected,
        {"hashes": hash_actual, "missing": missing},
        not missing and not hash_failures,
        str(base),
    )

    if missing:
        return
    config = read_json(paths["run_config"])
    status = read_json(paths["run_status"])
    validate_step2_config_and_code(
        log, route_id, config, status, require_instrumentation=True
    )

    expected_map = {
        "M": "MRrt" if route_id == "main_ori_div1" else "MRren",
        "C1": "C1",
        "K1": "K1",
        "C2": "C2",
        "K2": "K2",
        "al": "al",
        "dt": "dt",
        "step2_rho_reference": "stab",
    }
    if expected["division"] == "div2":
        expected_map.update({"S": "S", "DeltaC": "DeltaC", "DeltaK": "DeltaK"})
    actual_map = route.get("matrix_variable_map")
    actual_map = dict(actual_map) if isinstance(actual_map, Mapping) else {}
    log.add(
        f"{route_id}步骤4矩阵变量映射",
        expected_map,
        actual_map,
        actual_map == expected_map,
        "route.matrix_variable_map",
    )
    log.add(
        f"{route_id}步骤2候选MLX身份",
        str(config.get("candidate_sha256", "")).upper(),
        str(route.get("candidate_mlx_sha256", "")).upper(),
        bool(config.get("candidate_sha256"))
        and str(config.get("candidate_sha256", "")).upper()
        == str(route.get("candidate_mlx_sha256", "")).upper(),
        "route.candidate_mlx_sha256 + step2 run_config",
    )

    terminal_ok = (
        status.get("final_status") == "SUCCESS"
        and status.get("execution_status") == "EXECUTION_SUCCESS"
        and status.get("evidence_status") == "PASS"
        and not status.get("capture_errors")
    )
    log.add(
        f"{route_id}步骤2成功终态",
        {
            "final_status": "SUCCESS",
            "execution_status": "EXECUTION_SUCCESS",
            "evidence_status": "PASS",
            "capture_errors": 0,
        },
        {
            "final_status": status.get("final_status"),
            "execution_status": status.get("execution_status"),
            "evidence_status": status.get("evidence_status"),
            "capture_errors": len(status.get("capture_errors") or []),
        },
        terminal_ok,
        str(paths["run_status"]),
    )

    shapes, loader = mat_shapes(paths["workspace"])
    required_shapes = expected["required_workspace"]
    workspace_failures = {
        name: {"expected": shape, "actual": shapes.get(name)}
        for name, shape in required_shapes.items()
        if shapes.get(name) != shape
    }
    log.add(
        f"{route_id}求解器工作区矩阵字段与维数",
        required_shapes,
        {"failures": workspace_failures, "loader": loader},
        not workspace_failures,
        str(paths["workspace"]),
    )

    raw_values, raw_loader = load_mat_variables(paths["raw_stab"])
    raw_value = raw_values.get("stab")
    raw = np.asarray(raw_value, dtype=float) if raw_value is not None else np.empty((0, 0))
    raw_ok = raw.shape == tuple(expected["raw_shape"])
    log.add(
        f"{route_id}步骤2 raw_stab 维数与载入方式",
        {"variable": "stab", "shape": expected["raw_shape"]},
        {"shape": tuple(raw.shape), "loader": raw_loader},
        raw_ok,
        str(paths["raw_stab"]),
    )
    if raw_ok:
        validate_route_regions(log, route_id, route, raw)

    author = route.get("author_code_grid")
    common = route.get("common_grid")
    author = author if isinstance(author, Mapping) else {}
    common = common if isinstance(common, Mapping) else {}
    author_shape = tuple(author.get("expected_shape") or [])
    common_shape = tuple(common.get("expected_shape") or [])
    author_points = numeric_scalar(author.get("expected_point_count"))
    common_points = numeric_scalar(common.get("expected_point_count"))
    count_snapshot = {
        "active_points": count_value(route.get("active_points")),
        "commented_author_intent_points": count_value(
            route.get("commented_author_intent_points")
        ),
        "supplemental_points": count_value(route.get("supplemental_points")),
        "author_grid_points": author_points,
        "common_grid_points": common_points,
        "author_shape": author_shape,
        "common_shape": common_shape,
    }
    expected_counts = {
        "active_points": expected["active_points"],
        "commented_author_intent_points": expected["commented_points"],
        "supplemental_points": expected["supplemental_points"],
        "author_grid_points": expected["author_points"],
        "common_grid_points": 2077,
        "author_shape": tuple(expected["author_shape"]),
        "common_shape": (31, 67),
    }
    log.add(
        f"{route_id}作者网格与31×67共同网格点数",
        expected_counts,
        count_snapshot,
        count_snapshot == expected_counts,
        "route author_code_grid/common_grid",
    )

    output_paths = [path for path in (grid_path(author), grid_path(common)) if path]
    path_failures = [
        str(path)
        for path in output_paths
        if not is_within(path, DEFAULT_OUTPUT_ROOT)
    ]
    log.add(
        f"{route_id}步骤4输出位于隔离目录",
        {"paths": 2, "outside": []},
        {"paths": len(output_paths), "outside": path_failures},
        len(output_paths) == 2 and not path_failures,
        str(DEFAULT_OUTPUT_ROOT),
    )


def validate_failed_route_precheck(
    log: CheckLog,
    route_id: str,
    manifest_item: Any,
    output_root: Path,
) -> None:
    expected = STEP2[route_id]
    paths = step2_paths(route_id)
    missing = [key for key, path in paths.items() if not path.is_file()]
    actual_hashes = {
        key: sha256_file(path) if path.is_file() else None for key, path in paths.items()
    }
    log.add(
        f"{route_id}步骤2失败证据密封",
        expected["sha256"],
        {"hashes": actual_hashes, "missing": missing},
        not missing and actual_hashes == expected["sha256"],
        str(step2_base(route_id)),
    )
    if missing:
        return
    config = read_json(paths["run_config"])
    status = read_json(paths["run_status"])
    validate_step2_config_and_code(
        log, route_id, config, status, require_instrumentation=False
    )
    message = str((status.get("error") or {}).get("message", ""))
    terminal_ok = (
        status.get("final_status") == "EXECUTION_FAIL"
        and status.get("execution_status") == "EXECUTION_FAIL"
        and status.get("evidence_status") == "PASS"
        and expected["missing_symbol"] in message
    )
    log.add(
        f"{route_id}保持原样执行失败",
        {
            "final_status": "EXECUTION_FAIL",
            "evidence_status": "PASS",
            "missing_symbol": expected["missing_symbol"],
        },
        {
            "final_status": status.get("final_status"),
            "execution_status": status.get("execution_status"),
            "evidence_status": status.get("evidence_status"),
            "message": message,
        },
        terminal_ok,
        str(paths["run_status"]),
    )

    raw_path = step2_base(route_id) / "scientific" / "raw_stab.mat"
    route_output = output_root / route_id
    forbidden_grid_files = (
        [path for path in route_output.rglob("*.mat") if path.is_file()]
        if route_output.exists()
        else []
    )
    log.add(
        f"{route_id}失败路线没有rho网格",
        {"step2_raw_stab_exists": False, "step4_mat_files": []},
        {
            "step2_raw_stab_exists": raw_path.exists(),
            "step4_mat_files": [str(path) for path in forbidden_grid_files],
        },
        not raw_path.exists() and not forbidden_grid_files,
        str(route_output),
    )

    if isinstance(manifest_item, Mapping):
        config_path = resolve_board_path(str(manifest_item.get("run_config_relpath", "")))
        status_path = resolve_board_path(str(manifest_item.get("run_status_relpath", "")))
        manifest_config_hash = str(manifest_item.get("run_config_sha256", "")).upper()
        manifest_status_hash = str(manifest_item.get("run_status_sha256", "")).upper()
        workspace_path = resolve_board_path(str(manifest_item.get("workspace_relpath", "")))
        manifest_workspace_hash = str(
            manifest_item.get("workspace_sha256", "")
        ).upper()
        reason = str(manifest_item.get("error_message", ""))
        policy = str(manifest_item.get("rho_grid_policy", ""))
        log.add(
            f"{route_id}失败路线清单声明",
            {
                "config_path": str(paths["run_config"]),
                "status_path": str(paths["run_status"]),
                "config_sha256": expected["sha256"]["run_config"],
                "status_sha256": expected["sha256"]["run_status"],
                "workspace_path": str(paths["workspace"]),
                "workspace_sha256": expected["sha256"]["workspace"],
                "reason_contains": expected["missing_symbol"],
                "rho_grid_policy": "DO_NOT_CREATE",
            },
            {
                "config_path": str(config_path),
                "status_path": str(status_path),
                "config_sha256": manifest_config_hash,
                "status_sha256": manifest_status_hash,
                "workspace_path": str(workspace_path),
                "workspace_sha256": manifest_workspace_hash,
                "reason": reason,
                "rho_grid_policy": policy,
            },
            config_path == paths["run_config"].resolve()
            and status_path == paths["run_status"].resolve()
            and manifest_config_hash == expected["sha256"]["run_config"]
            and manifest_status_hash == expected["sha256"]["run_status"]
            and workspace_path == paths["workspace"].resolve()
            and manifest_workspace_hash == expected["sha256"]["workspace"]
            and expected["missing_symbol"] in reason
            and policy == "DO_NOT_CREATE",
            "manifest.failed_routes",
        )


def validate_upstream(
    manifest_path: Path,
    require_empty_outputs: bool,
) -> tuple[CheckLog, dict[str, Any] | None]:
    log = CheckLog("S4-PRE")
    log.add(
        "步骤4验证合同存在",
        True,
        DEFAULT_SCHEMA.is_file(),
        DEFAULT_SCHEMA.is_file(),
        str(DEFAULT_SCHEMA),
    )
    if not manifest_path.is_file():
        log.add(
            "步骤4路线清单存在",
            True,
            False,
            False,
            str(manifest_path),
        )
        return log, None
    try:
        manifest = read_json(manifest_path)
    except Exception as exc:  # defensive: emit an auditable failure, not traceback only
        log.add(
            "步骤4路线清单可解析",
            "valid JSON",
            f"{type(exc).__name__}: {exc}",
            False,
            str(manifest_path),
        )
        return log, None

    log.add(
        "步骤4路线清单schema版本",
        "board20_step4_route_manifest_v1",
        manifest.get("schema_version") or manifest.get("schema"),
        (manifest.get("schema_version") or manifest.get("schema"))
        == "board20_step4_route_manifest_v1",
        str(manifest_path),
    )

    solver_contract = manifest.get("solver")
    solver_contract = solver_contract if isinstance(solver_contract, Mapping) else {}
    required_result_fields = [
        "poles",
        "rho",
        "poly_degree",
        "clearing_power",
        "removed_zero_root_count",
        "max_relative_residual",
        "point_status",
        "stable",
    ]
    additional_result_fields = [
        "raw_roots",
        "retained_root_count",
        "critical",
        "diagnostic",
    ]
    solver_path = SCRIPT.parent / "solve_board20_author_poles.m"
    runner_path = SCRIPT.parent / "run_board20_step4_rho_grids.m"
    log.add(
        "单点求解器接口合同",
        {
            "function": "solve_board20_author_poles",
            "required_result_fields": required_result_fields,
            "additional_result_fields": additional_result_fields,
        },
        {
            "function": solver_contract.get("function"),
            "required_result_fields": solver_contract.get("required_result_fields"),
            "additional_result_fields": solver_contract.get("additional_result_fields"),
        },
        solver_contract.get("function") == "solve_board20_author_poles"
        and solver_contract.get("required_result_fields") == required_result_fields
        and solver_contract.get("additional_result_fields") == additional_result_fields,
        str(manifest_path),
    )
    log.add(
        "步骤4求解器与编排器文件存在并记录实时哈希",
        {"solver_exists": True, "runner_exists": True},
        {
            "solver_exists": solver_path.is_file(),
            "solver_sha256": sha256_file(solver_path) if solver_path.is_file() else None,
            "runner_exists": runner_path.is_file(),
            "runner_sha256": sha256_file(runner_path) if runner_path.is_file() else None,
        },
        solver_path.is_file() and runner_path.is_file(),
        str(SCRIPT.parent),
    )

    routes = manifest.get("routes") if isinstance(manifest.get("routes"), list) else []
    route_ids = [route_id_of(item) for item in routes]
    failed = (
        manifest.get("failed_routes")
        if isinstance(manifest.get("failed_routes"), list)
        else []
    )
    failed_ids = [route_id_of(item) for item in failed]
    log.add(
        "五条可执行候选路线唯一且完整",
        sorted(SUCCESS_ROUTE_IDS),
        sorted(route_ids),
        len(route_ids) == 5
        and len(set(route_ids)) == 5
        and set(route_ids) == SUCCESS_ROUTE_IDS,
        str(manifest_path),
    )
    log.add(
        "四条失败路线唯一且完整",
        sorted(FAILED_ROUTE_IDS),
        sorted(failed_ids),
        len(failed_ids) == 4
        and len(set(failed_ids)) == 4
        and set(failed_ids) == FAILED_ROUTE_IDS,
        str(manifest_path),
    )

    route_by_id = {
        route_id_of(item): item for item in routes if isinstance(item, Mapping)
    }
    for route_id in sorted(SUCCESS_ROUTE_IDS):
        route = route_by_id.get(route_id)
        if route is None:
            continue
        validate_success_route_precheck(log, route_id, route)

    output_root = output_root_from_manifest(manifest)
    failed_by_id = {route_id_of(item): item for item in failed}
    for route_id in sorted(FAILED_ROUTE_IDS):
        validate_failed_route_precheck(
            log, route_id, failed_by_id.get(route_id), output_root
        )

    output_root_ok = is_within(output_root, BOARD_ROOT / "outputs")
    log.add(
        "步骤4输出根目录隔离",
        str(DEFAULT_OUTPUT_ROOT.resolve()),
        str(output_root),
        output_root_ok and output_root == DEFAULT_OUTPUT_ROOT.resolve(),
        "manifest.output_root_relpath",
    )
    if require_empty_outputs:
        existing_files = (
            sorted(str(path.relative_to(output_root)) for path in output_root.rglob("*") if path.is_file())
            if output_root.exists()
            else []
        )
        log.add(
            "PRECHECK运行前输出为空",
            [],
            existing_files,
            not existing_files,
            str(output_root),
        )
    return log, manifest


VARIABLE_ALIASES: dict[str, tuple[str, ...]] = {
    "rho": ("rho", "rho_grid", "spectral_radius", "max_pole_modulus"),
    "stable": ("stable", "stable_grid", "stability"),
    "critical": ("critical", "critical_grid"),
    "residual": (
        "residual",
        "residual_grid",
        "max_relative_residual",
        "max_relative_residual_grid",
    ),
    "point_status_code": (
        "status",
        "point_status_code",
        "status_grid",
        "point_status",
    ),
    "diagnostic": ("diagnostic", "diagnostic_grid", "failure_reason"),
    "provenance_code": (
        "provenance_code",
        "provenance_grid",
        "point_provenance_code",
    ),
}


def select_variable(
    variables: Mapping[str, Any],
    grid: Mapping[str, Any],
    semantic: str,
) -> tuple[Any, str | None]:
    mapping = grid.get("mat_variables")
    declared = mapping.get(semantic) if isinstance(mapping, Mapping) else None
    candidates = ([str(declared)] if declared else []) + list(VARIABLE_ALIASES[semantic])
    seen: set[str] = set()
    for name in candidates:
        if name in seen:
            continue
        seen.add(name)
        if name in variables:
            return variables[name], name
    return None, None


def code_map(grid: Mapping[str, Any], key: str, defaults: Mapping[str, int]) -> dict[str, int]:
    value = grid.get(key)
    if not isinstance(value, Mapping):
        return dict(defaults)
    result: dict[str, int] = {}
    for name, code in value.items():
        try:
            result[str(name)] = int(code)
        except (TypeError, ValueError):
            continue
    return result or dict(defaults)


def normalize_code_grid(
    value: Any,
    mapping: Mapping[str, int],
    shape: tuple[int, int],
) -> np.ndarray | None:
    if value is None:
        return None
    array = np.asarray(value)
    if array.shape != shape:
        return array
    if array.dtype.kind in "biufc":
        return np.asarray(np.real(array), dtype=float)
    result = np.full(shape, np.nan, dtype=float)
    for index in np.ndindex(shape):
        item = array[index]
        while isinstance(item, np.ndarray) and item.size == 1:
            item = item.reshape(-1)[0]
        text = str(item).strip()
        if text in mapping:
            result[index] = mapping[text]
        elif text in {"", "NOT_REQUESTED", "NONE", "0"}:
            result[index] = 0
    return result


def normalize_bool_grid(value: Any, shape: tuple[int, int]) -> np.ndarray | None:
    if value is None:
        return None
    array = np.asarray(value)
    if array.shape != shape:
        return array
    if array.dtype.kind in "biufc":
        numeric = np.asarray(np.real(array), dtype=float)
        return np.asarray(np.isfinite(numeric) & (numeric != 0), dtype=bool)
    result = np.zeros(shape, dtype=bool)
    for index in np.ndindex(shape):
        item = array[index]
        while isinstance(item, np.ndarray) and item.size == 1:
            item = item.reshape(-1)[0]
        if isinstance(item, (bool, np.bool_)):
            result[index] = bool(item)
        elif isinstance(item, (int, float, np.integer, np.floating)):
            numeric = float(item)
            result[index] = math.isfinite(numeric) and numeric != 0
        else:
            text = str(item).strip().lower()
            result[index] = text in {"1", "true", "yes", "pass"}
    return result


def diagnostic_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, np.ndarray) and value.size == 0:
        return ""
    while isinstance(value, np.ndarray) and value.size == 1:
        value = value.reshape(-1)[0]
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace").strip()
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, Mapping):
        return json.dumps(value, ensure_ascii=False, default=str)
    return str(value).strip()


def diagnostic_grid_value(value: Any, index: tuple[int, int]) -> str:
    if value is None:
        return ""
    if isinstance(value, np.ndarray) and value.shape == ():
        return diagnostic_text(value.item())
    if isinstance(value, np.ndarray) and value.ndim >= 2:
        try:
            return diagnostic_text(value[index])
        except IndexError:
            return ""
    return diagnostic_text(value)


def expected_grid_masks(
    route: Mapping[str, Any],
    grid_kind: str,
    shape: tuple[int, int],
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    active, _ = expand_regions(route.get("active_regions"))
    commented, _ = expand_regions(route.get("commented_author_intent_regions"))
    requested = np.zeros(shape, dtype=bool)
    active_mask = np.zeros(shape, dtype=bool)
    commented_mask = np.zeros(shape, dtype=bool)
    for point in active:
        if 0 <= point[0] < shape[0] and 0 <= point[1] < shape[1]:
            requested[point] = True
            active_mask[point] = True
    for point in commented:
        if 0 <= point[0] < shape[0] and 0 <= point[1] < shape[1]:
            requested[point] = True
            commented_mask[point] = True
    if grid_kind == "common_grid":
        requested[:, :] = True
    supplemental_mask = requested & ~active_mask & ~commented_mask
    return requested, active_mask, commented_mask, supplemental_mask


def has_ordered_1_to_28(array: np.ndarray, mask: np.ndarray) -> bool:
    target = np.arange(1.0, 29.0)
    working = np.where(mask, array, np.nan)
    sequences: list[np.ndarray] = [working.ravel(order="C"), working.ravel(order="F")]
    sequences.extend(working[row, :] for row in range(working.shape[0]))
    sequences.extend(working[:, column] for column in range(working.shape[1]))
    for sequence in sequences:
        if sequence.size < 28:
            continue
        for start in range(sequence.size - 27):
            window = np.asarray(sequence[start : start + 28], dtype=float)
            if np.all(np.isfinite(window)) and np.array_equal(window, target):
                return True
    return False


def validate_grid_arrays(
    log: CheckLog,
    route_id: str,
    route: Mapping[str, Any],
    grid_kind: str,
    grid: Mapping[str, Any],
    variables: Mapping[str, Any],
    raw: np.ndarray,
    evidence: str,
) -> None:
    shape = tuple(int(item) for item in grid.get("expected_shape", []))
    if len(shape) != 2:
        log.add(
            f"{route_id}/{grid_kind}网格维数合同",
            "two-dimensional shape",
            shape,
            False,
            evidence,
        )
        return

    selected: dict[str, Any] = {}
    names: dict[str, str | None] = {}
    for semantic in VARIABLE_ALIASES:
        selected[semantic], names[semantic] = select_variable(variables, grid, semantic)
    required_semantics = {
        "rho",
        "stable",
        "critical",
        "residual",
        "point_status_code",
        "diagnostic",
        "provenance_code",
    }
    missing = sorted(name for name in required_semantics if selected[name] is None)
    log.add(
        f"{route_id}/{grid_kind}核心MAT变量完整",
        sorted(required_semantics),
        {"resolved": names, "missing": missing},
        not missing,
        evidence,
    )
    if missing:
        return

    rho = np.asarray(selected["rho"], dtype=float)
    residual = np.asarray(selected["residual"], dtype=float)
    stable = normalize_bool_grid(selected["stable"], shape)
    critical = normalize_bool_grid(selected["critical"], shape)
    status_mapping = code_map(grid, "status_code_map", {"PASS": 1, "FAIL": 2})
    provenance_mapping = code_map(
        grid,
        "provenance_code_map",
        {
            "ORIGINAL_ACTIVE_POINT": 1,
            "COMMENTED_AUTHOR_INTENT": 2,
            "SAME_FORMULA_SUPPLEMENT": 3,
            "FAIL": 4,
        },
    )
    status = normalize_code_grid(selected["point_status_code"], status_mapping, shape)
    provenance = normalize_code_grid(selected["provenance_code"], provenance_mapping, shape)
    arrays = {
        "rho": rho,
        "residual": residual,
        "stable": stable,
        "critical": critical,
        "status": status,
        "provenance": provenance,
    }
    wrong_shapes = {
        name: tuple(value.shape) if isinstance(value, np.ndarray) else None
        for name, value in arrays.items()
        if not isinstance(value, np.ndarray) or value.shape != shape
    }
    log.add(
        f"{route_id}/{grid_kind}全部网格变量维数",
        shape,
        wrong_shapes or {"all": shape},
        not wrong_shapes,
        evidence,
    )
    if wrong_shapes or status is None or provenance is None or stable is None or critical is None:
        return

    requested, active_mask, commented_mask, supplemental_mask = expected_grid_masks(
        route, grid_kind, shape
    )
    pass_code = status_mapping.get("PASS", 1)
    fail_code = status_mapping.get("FAIL", 2)
    pass_mask = requested & (status == pass_code)
    fail_mask = requested & (status == fail_code)
    explicit_mask = pass_mask | fail_mask
    unexpected_status_codes = sorted(
        float(item)
        for item in np.unique(status[requested])
        if item not in {float(pass_code), float(fail_code)}
    )
    nonpoint_status_nonzero = int(np.count_nonzero(status[~requested] != 0))
    log.add(
        f"{route_id}/{grid_kind}每个请求点均为PASS或明确FAIL",
        {
            "requested": int(np.count_nonzero(requested)),
            "explicit": int(np.count_nonzero(requested)),
            "unexpected_codes": [],
            "nonpoint_status_nonzero": 0,
        },
        {
            "requested": int(np.count_nonzero(requested)),
            "pass": int(np.count_nonzero(pass_mask)),
            "fail": int(np.count_nonzero(fail_mask)),
            "explicit": int(np.count_nonzero(explicit_mask)),
            "unexpected_codes": unexpected_status_codes,
            "nonpoint_status_nonzero": nonpoint_status_nonzero,
        },
        np.array_equal(explicit_mask, requested)
        and not unexpected_status_codes
        and nonpoint_status_nonzero == 0,
        evidence,
    )

    pass_rho_ok = np.isfinite(rho[pass_mask]) & (rho[pass_mask] > 0)
    fail_rho = rho[fail_mask]
    # A solver exception has NaN rho; a later contract failure (for example an
    # active-point mismatch) may retain its finite positive rho as evidence.
    # Neither case may be mistaken for a passing point.
    fail_rho_ok = np.isnan(fail_rho) | (np.isfinite(fail_rho) & (fail_rho > 0))
    nonpoint_rho_is_nan = np.isnan(rho[~requested])
    log.add(
        f"{route_id}/{grid_kind}rho只在PASS点为有限正值",
        {
            "pass_invalid": 0,
            "fail_invalid": 0,
            "nonpoint_non_nan": 0,
        },
        {
            "pass_invalid": int(np.count_nonzero(~pass_rho_ok)),
            "fail_invalid": int(np.count_nonzero(~fail_rho_ok)),
            "nonpoint_non_nan": int(np.count_nonzero(~nonpoint_rho_is_nan)),
        },
        bool(np.all(pass_rho_ok))
        and bool(np.all(fail_rho_ok))
        and bool(np.all(nonpoint_rho_is_nan)),
        evidence,
    )

    expected_stable = pass_mask & np.isfinite(rho) & (rho > 0) & (rho < 1)
    expected_critical = pass_mask & np.isfinite(rho) & (np.abs(rho - 1) <= CRITICAL_TOL)
    stable_mismatch = int(np.count_nonzero(stable != expected_stable))
    critical_mismatch = int(np.count_nonzero(critical != expected_critical))
    log.add(
        f"{route_id}/{grid_kind}stable严格由finite且0<rho<1生成",
        0,
        stable_mismatch,
        stable_mismatch == 0,
        evidence,
    )
    log.add(
        f"{route_id}/{grid_kind}临界点严格按|rho-1|<=1e-8生成",
        0,
        critical_mismatch,
        critical_mismatch == 0,
        evidence,
    )

    pass_residual = residual[pass_mask]
    pass_residual_ok = (
        np.isfinite(pass_residual)
        & (pass_residual >= 0)
        & (pass_residual <= RESIDUAL_TOL)
    )
    fail_diagnostics_missing = 0
    for index in map(tuple, np.argwhere(fail_mask)):
        if not diagnostic_grid_value(selected["diagnostic"], index):
            fail_diagnostics_missing += 1
    log.add(
        f"{route_id}/{grid_kind}根残差与失败诊断",
        {"pass_residual_over_1e-8": 0, "failed_diagnostic_missing": 0},
        {
            "pass_residual_over_1e-8": int(np.count_nonzero(~pass_residual_ok)),
            "maximum_pass_residual": (
                float(np.max(pass_residual)) if pass_residual.size else None
            ),
            "failed_diagnostic_missing": fail_diagnostics_missing,
        },
        bool(np.all(pass_residual_ok)) and fail_diagnostics_missing == 0,
        evidence,
    )

    expected_provenance = np.zeros(shape, dtype=float)
    expected_provenance[active_mask] = provenance_mapping.get(
        "ORIGINAL_ACTIVE_POINT", 1
    )
    expected_provenance[commented_mask] = provenance_mapping.get(
        "COMMENTED_AUTHOR_INTENT", 2
    )
    expected_provenance[supplemental_mask] = provenance_mapping.get(
        "SAME_FORMULA_SUPPLEMENT", 3
    )
    expected_provenance[fail_mask] = provenance_mapping.get("FAIL", 4)
    provenance_mismatch = int(np.count_nonzero(provenance != expected_provenance))
    log.add(
        f"{route_id}/{grid_kind}原样/注释意图/同公式补算标签不越界",
        0,
        provenance_mismatch,
        provenance_mismatch == 0,
        evidence,
    )

    active_points = {tuple(map(int, item)) for item in np.argwhere(active_mask)}
    comparable_points = {
        point
        for point in active_points
        if point[0] < raw.shape[0] and point[1] < raw.shape[1]
    }
    raw_values = values_at(raw, comparable_points)
    output_values = values_at(rho, comparable_points)
    differences = np.abs(output_values - raw_values)
    raw_classification = np.isfinite(raw_values) & (raw_values > 0) & (raw_values < 1)
    output_classification = np.isfinite(output_values) & (output_values > 0) & (
        output_values < 1
    )
    active_pass = bool(np.all((pass_mask & active_mask) == active_mask))
    max_difference = float(np.max(differences)) if differences.size else math.inf
    classification_mismatch = int(
        np.count_nonzero(raw_classification != output_classification)
    )
    log.add(
        f"{route_id}/{grid_kind}原样活动点复现步骤2 raw_stab",
        {
            "points": len(active_points),
            "max_abs_difference": f"<= {RHO_TOL}",
            "classification_mismatch": 0,
            "all_active_points_pass": True,
        },
        {
            "points": len(comparable_points),
            "max_abs_difference": max_difference,
            "classification_mismatch": classification_mismatch,
            "all_active_points_pass": active_pass,
        },
        len(comparable_points) == len(active_points)
        and active_pass
        and max_difference <= RHO_TOL
        and classification_mismatch == 0,
        evidence,
    )

    exact_0999 = int(
        np.count_nonzero(pass_mask & np.isclose(rho, 0.999, rtol=0.0, atol=SENTINEL_TOL))
    )
    zero_pass = int(np.count_nonzero(pass_mask & (rho == 0)))
    ordered_1_28 = has_ordered_1_to_28(rho, pass_mask)
    log.add(
        f"{route_id}/{grid_kind}未混入历史0/0.999掩膜或1至28索引",
        {"zero_pass": 0, "exact_0.999": 0, "ordered_1_to_28": False},
        {
            "zero_pass": zero_pass,
            "exact_0.999": exact_0999,
            "ordered_1_to_28": ordered_1_28,
        },
        zero_pass == 0 and exact_0999 == 0 and not ordered_1_28,
        evidence,
    )

    # Runner mirrors these independent comparisons into the MAT file.  If the
    # mirrors are present, validate them as additional evidence; the direct
    # comparison above remains authoritative.
    reference = variables.get("step2_rho_reference")
    abs_diff = variables.get("step2_abs_diff")
    step2_match = variables.get("step2_match")
    if reference is not None or abs_diff is not None or step2_match is not None:
        reference_array = np.asarray(reference, dtype=float)
        diff_array = np.asarray(abs_diff, dtype=float)
        match_array = normalize_bool_grid(step2_match, shape)
        mirror_shapes_ok = (
            reference_array.shape == shape
            and diff_array.shape == shape
            and isinstance(match_array, np.ndarray)
            and match_array.shape == shape
        )
        mirror_ok = False
        if mirror_shapes_ok and match_array is not None:
            mirror_ok = (
                np.allclose(
                    reference_array[active_mask], raw_values, rtol=0.0, atol=0.0
                )
                and np.allclose(
                    diff_array[active_mask], differences, rtol=0.0, atol=1.0e-15
                )
                and bool(np.all(match_array[active_mask]))
            )
        log.add(
            f"{route_id}/{grid_kind}步骤2匹配镜像字段",
            True,
            {"shapes_ok": mirror_shapes_ok, "values_ok": mirror_ok},
            mirror_ok,
            evidence,
        )


def validate_route_status(
    log: CheckLog,
    route_id: str,
    route: Mapping[str, Any],
    output_root: Path,
) -> None:
    value = route.get("status_relpath") or route.get("status_json")
    status_path = resolve_board_path(str(value)) if value else output_root / route_id / "status.json"
    if not status_path.is_file():
        log.add(
            f"{route_id}步骤4路线状态文件存在",
            True,
            False,
            False,
            str(status_path),
        )
        return
    try:
        status = read_json(status_path)
    except Exception as exc:
        log.add(
            f"{route_id}步骤4路线状态文件可解析",
            "valid JSON",
            f"{type(exc).__name__}: {exc}",
            False,
            str(status_path),
        )
        return
    final = str(
        status.get("final_status")
        or status.get("status")
        or status.get("execution_status")
        or status.get("overall_status")
        or ""
    ).upper()
    terminal_values = {
        "SUCCESS",
        "PASS",
        "COMPLETE",
        "COMPLETED",
        "COMPLETED_WITH_POINT_FAILURES",
        "COMPLETE_PASS",
        "COMPLETE_WITH_FAIL",
    }
    log.add(
        f"{route_id}步骤4路线终态",
        {"route_id": route_id, "terminal": sorted(terminal_values)},
        {"route_id": status.get("route_id"), "final": final},
        status.get("route_id") == route_id and final in terminal_values,
        str(status_path),
    )


def validate_postcheck(
    manifest_path: Path,
) -> tuple[CheckLog, dict[str, Any] | None]:
    upstream_log, manifest = validate_upstream(manifest_path, require_empty_outputs=False)
    log = CheckLog("S4-POST")
    for item in upstream_log.checks:
        log.checks.append(
            Check(
                check_id=f"S4-POST-{len(log.checks) + 1:04d}",
                name=f"上游复核：{item.name}",
                expected=item.expected,
                actual=item.actual,
                status=item.status,
                evidence=item.evidence,
            )
        )
    if manifest is None:
        return log, None

    output_root = output_root_from_manifest(manifest)
    routes = {
        route_id_of(item): item
        for item in manifest.get("routes", [])
        if isinstance(item, Mapping)
    }
    for route_id in sorted(SUCCESS_ROUTE_IDS):
        route = routes.get(route_id)
        if route is None:
            continue
        raw_path = step2_paths(route_id)["raw_stab"]
        raw_variables, _ = load_mat_variables(raw_path)
        raw = np.asarray(raw_variables["stab"], dtype=float)
        validate_route_status(log, route_id, route, output_root)
        for grid_kind in ("author_code_grid", "common_grid"):
            grid_value = route.get(grid_kind)
            if not isinstance(grid_value, Mapping):
                log.add(
                    f"{route_id}/{grid_kind}合同存在",
                    True,
                    False,
                    False,
                    str(manifest_path),
                )
                continue
            path = grid_path(grid_value)
            if path is None or not path.is_file():
                log.add(
                    f"{route_id}/{grid_kind}MAT输出存在",
                    True,
                    False,
                    False,
                    str(path),
                )
                continue
            variables, loader = load_mat_variables(path)
            validate_grid_arrays(
                log,
                route_id,
                route,
                grid_kind,
                grid_value,
                variables,
                raw,
                f"{path}; loader={loader}",
            )

    # Repeat the failed-route grid prohibition after all successful outputs exist.
    for route_id in sorted(FAILED_ROUTE_IDS):
        route_output = output_root / route_id
        files = (
            sorted(str(path) for path in route_output.rglob("*.mat") if path.is_file())
            if route_output.exists()
            else []
        )
        log.add(
            f"{route_id}POSTCHECK仍无rho网格",
            [],
            files,
            not files,
            str(route_output),
        )
    return log, manifest


def check_named(log: CheckLog, contains: str) -> list[Check]:
    return [item for item in log.checks if contains in item.name]


def run_selftest() -> CheckLog:
    log = CheckLog("S4-SELFTEST")
    with tempfile.TemporaryDirectory(prefix="board20_step4_validator_") as temp_name:
        temp = Path(temp_name)
        expected = np.asarray([[1.25, 2.5, 3.75], [4.0, 5.0, 6.0]], dtype=float)

        v5_path = temp / "v5.mat"
        savemat(v5_path, {"probe": expected})
        v5_values, v5_loader = load_mat_variables(v5_path)
        log.add(
            "MATLAB v5读取自测",
            expected.tolist(),
            np.asarray(v5_values.get("probe")).tolist(),
            v5_loader == "scipy.io.loadmat"
            and np.array_equal(np.asarray(v5_values.get("probe")), expected),
            str(v5_path),
        )

        v73_path = temp / "v73.mat"
        with h5py.File(v73_path, "w") as handle:
            dataset = handle.create_dataset("probe", data=expected.T)
            dataset.attrs["MATLAB_class"] = np.bytes_("double")
        v73_values, v73_loader = load_mat_variables(v73_path)
        log.add(
            "MATLAB v7.3 HDF5轴恢复自测",
            expected.tolist(),
            np.asarray(v73_values.get("probe")).tolist(),
            v73_loader == "h5py MATLAB-v7.3"
            and np.array_equal(np.asarray(v73_values.get("probe")), expected),
            str(v73_path),
        )

        cell_path = temp / "v73_cell.mat"
        with h5py.File(cell_path, "w") as handle:
            references = handle.create_group("#refs#")
            true_value = references.create_dataset("true", data=np.asarray([[1]], dtype=np.uint8))
            true_value.attrs["MATLAB_class"] = np.bytes_("logical")
            false_value = references.create_dataset("false", data=np.asarray([[0]], dtype=np.uint8))
            false_value.attrs["MATLAB_class"] = np.bytes_("logical")
            stored = np.empty((2, 2), dtype=h5py.ref_dtype)
            stored[0, 0] = true_value.ref
            stored[0, 1] = false_value.ref
            stored[1, 0] = false_value.ref
            stored[1, 1] = true_value.ref
            cell = handle.create_dataset("critical", data=stored)
            cell.attrs["MATLAB_class"] = np.bytes_("cell")
        cell_values, _ = load_mat_variables(cell_path)
        normalized_cell = normalize_bool_grid(cell_values["critical"], (2, 2))
        expected_cell = np.asarray([[True, False], [False, True]])
        log.add(
            "MATLAB v7.3 cell logical读取自测",
            expected_cell.tolist(),
            normalized_cell.tolist() if normalized_cell is not None else None,
            normalized_cell is not None
            and np.array_equal(normalized_cell, expected_cell),
            str(cell_path),
        )

    route: dict[str, Any] = {
        "active_regions": {
            "l_start": 0,
            "l_end": 1,
            "j_start": 0,
            "j_end": 1,
        },
        "commented_author_intent_regions": [],
    }
    grid: dict[str, Any] = {
        "expected_shape": [2, 2],
        "expected_point_count": 4,
        "status_code_map": {"PASS": 1, "FAIL": 2},
        "provenance_code_map": {
            "ORIGINAL_ACTIVE_POINT": 1,
            "COMMENTED_AUTHOR_INTENT": 2,
            "SAME_FORMULA_SUPPLEMENT": 3,
            "FAIL": 4,
        },
        "mat_variables": {
            "rho": "rho",
            "stable": "stable",
            "critical": "critical",
            "residual": "residual",
            "point_status_code": "status",
            "diagnostic": "diagnostic",
            "provenance_code": "provenance_code",
        },
    }
    rho = np.asarray([[0.8, 1.0], [1.2, 0.95]], dtype=float)
    stable = np.isfinite(rho) & (rho > 0) & (rho < 1)
    critical = np.abs(rho - 1) <= CRITICAL_TOL
    variables: dict[str, Any] = {
        "rho": rho,
        "stable": stable,
        "critical": critical,
        "residual": np.full((2, 2), 1.0e-12),
        "status": np.ones((2, 2)),
        "diagnostic": np.full((2, 2), "PASS", dtype=object),
        "provenance_code": np.ones((2, 2)),
    }
    semantic_log = CheckLog("SYNTHETIC")
    validate_grid_arrays(
        semantic_log,
        "synthetic",
        route,
        "author_code_grid",
        grid,
        variables,
        rho.copy(),
        "synthetic",
    )
    log.add(
        "正确网格语义自测",
        "PASS",
        semantic_log.summary(),
        semantic_log.passed,
        "in-memory synthetic grid",
    )

    wrong_stable = dict(variables)
    wrong_stable["stable"] = np.logical_not(stable)
    wrong_log = CheckLog("SYNTHETIC")
    validate_grid_arrays(
        wrong_log,
        "synthetic",
        route,
        "author_code_grid",
        grid,
        wrong_stable,
        rho.copy(),
        "synthetic wrong stable",
    )
    stable_checks = check_named(wrong_log, "stable严格")
    log.add(
        "错误stable可被拒绝",
        "FAIL detected",
        [item.status for item in stable_checks],
        bool(stable_checks) and all(item.status == "FAIL" for item in stable_checks),
        "in-memory mutation",
    )

    wrong_residual = dict(variables)
    wrong_residual["residual"] = np.full((2, 2), 1.1e-8)
    residual_log = CheckLog("SYNTHETIC")
    validate_grid_arrays(
        residual_log,
        "synthetic",
        route,
        "author_code_grid",
        grid,
        wrong_residual,
        rho.copy(),
        "synthetic wrong residual",
    )
    residual_checks = check_named(residual_log, "根残差")
    log.add(
        "超过1e-8残差可被拒绝",
        "FAIL detected",
        [item.status for item in residual_checks],
        bool(residual_checks) and all(item.status == "FAIL" for item in residual_checks),
        "in-memory mutation",
    )

    sentinel_variables = dict(variables)
    sentinel_rho = rho.copy()
    sentinel_rho[0, 0] = 0.999
    sentinel_variables["rho"] = sentinel_rho
    sentinel_variables["stable"] = (
        np.isfinite(sentinel_rho) & (sentinel_rho > 0) & (sentinel_rho < 1)
    )
    sentinel_log = CheckLog("SYNTHETIC")
    validate_grid_arrays(
        sentinel_log,
        "synthetic",
        route,
        "author_code_grid",
        grid,
        sentinel_variables,
        sentinel_rho.copy(),
        "synthetic historical sentinel",
    )
    contamination_checks = check_named(sentinel_log, "未混入历史")
    log.add(
        "历史0.999哨兵可被拒绝",
        "FAIL detected",
        [item.status for item in contamination_checks],
        bool(contamination_checks)
        and all(item.status == "FAIL" for item in contamination_checks),
        "in-memory mutation",
    )

    sequence = np.arange(1.0, 29.0).reshape(1, 28)
    log.add(
        "1至28索引序列污染可被识别",
        True,
        has_ordered_1_to_28(sequence, np.ones_like(sequence, dtype=bool)),
        has_ordered_1_to_28(sequence, np.ones_like(sequence, dtype=bool)),
        "direct contamination detector",
    )

    numeric_bool = normalize_bool_grid(
        np.asarray([[1.0, np.nan], [0.0, np.nan]]), (2, 2)
    )
    expected_numeric_bool = np.asarray([[True, False], [False, False]])
    log.add(
        "stable数值网格中的NaN不被当作True",
        expected_numeric_bool.tolist(),
        numeric_bool.tolist() if numeric_bool is not None else None,
        numeric_bool is not None
        and np.array_equal(numeric_bool, expected_numeric_bool),
        "stable normalization",
    )

    points, errors = expand_regions(
        {
            "l_start": 0,
            "l_end": 20,
            "j_start": 0,
            "j_end": 20,
        }
    )
    log.add(
        "单对象region展开为441点",
        {"count": 441, "errors": []},
        {"count": len(points), "errors": errors},
        len(points) == 441 and not errors,
        "region parser",
    )
    return log


def report_payload(
    mode: str,
    manifest_path: Path,
    log: CheckLog,
) -> dict[str, Any]:
    return {
        "schema": "board20_step4_independent_validation_v1",
        "mode": mode.upper(),
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "board_root": str(BOARD_ROOT),
        "validator": {
            "path": str(SCRIPT),
            "sha256": sha256_file(SCRIPT),
        },
        "validation_contract": {
            "path": str(DEFAULT_SCHEMA),
            "sha256": sha256_file(DEFAULT_SCHEMA) if DEFAULT_SCHEMA.is_file() else None,
        },
        "manifest": {
            "path": str(manifest_path),
            "sha256": sha256_file(manifest_path) if manifest_path.is_file() else None,
        },
        "tolerances": {
            "rho_active_abs": RHO_TOL,
            "pass_residual_max": RESIDUAL_TOL,
            "critical_abs_rho_minus_one": CRITICAL_TOL,
        },
        "summary": log.summary(),
        "checks": [item.as_dict() for item in log.checks],
    }


def write_report_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def write_report_csv(path: Path, log: CheckLog) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(
            stream,
            fieldnames=["check_id", "name", "expected", "actual", "status", "evidence"],
        )
        writer.writeheader()
        for item in log.checks:
            row = item.as_dict()
            row["expected"] = json.dumps(row["expected"], ensure_ascii=False, default=str)
            row["actual"] = json.dumps(row["actual"], ensure_ascii=False, default=str)
            writer.writerow(row)


def print_summary(mode: str, log: CheckLog, verbose: bool) -> None:
    summary = log.summary()
    print(
        f"BOARD20_STEP4_{mode.upper()}={summary['status']} "
        f"checks={summary['total']} pass={summary['passed']} fail={summary['failed']}"
    )
    if verbose or summary["failed"]:
        for item in log.checks:
            if verbose or item.status == "FAIL":
                print(f"[{item.status}] {item.check_id} {item.name}")
                if item.status == "FAIL":
                    print(
                        "  expected="
                        + json.dumps(item.expected, ensure_ascii=False, default=str)
                    )
                    print(
                        "  actual="
                        + json.dumps(item.actual, ensure_ascii=False, default=str)
                    )
                    if item.evidence:
                        print(f"  evidence={item.evidence}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "板块20最小步骤4独立验收器：PRECHECK不运行MATLAB；POSTCHECK逐点验收rho、"
            "stable、critical、残差、原样活动点和补算标签。"
        )
    )
    parser.add_argument(
        "--mode",
        choices=("precheck", "postcheck", "selftest"),
        default="precheck",
    )
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-csv", type=Path)
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    manifest_path = args.manifest.resolve()
    if args.mode == "precheck":
        log, _ = validate_upstream(manifest_path, require_empty_outputs=True)
    elif args.mode == "postcheck":
        log, _ = validate_postcheck(manifest_path)
    else:
        log = run_selftest()

    payload = report_payload(args.mode, manifest_path, log)
    if args.report_json:
        write_report_json(args.report_json.resolve(), payload)
    if args.report_csv:
        write_report_csv(args.report_csv.resolve(), log)
    print_summary(args.mode, log, args.verbose)
    return 0 if log.passed else 1


if __name__ == "__main__":
    sys.exit(main())

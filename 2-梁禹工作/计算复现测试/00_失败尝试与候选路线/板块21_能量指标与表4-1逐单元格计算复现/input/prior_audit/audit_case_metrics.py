"""只读复核第3章响应 NRMSE、Chirp 分频段 NRMSE 和第4章稳定掩膜。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from scipy.io import loadmat


WORKSPACE = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master")
CHAPTER3 = WORKSPACE / "figure" / "第3章_缩聚对试验精度的影响"
STABILITY_DIR = WORKSPACE / "liangyustability-master" / "新结构稳定" / "绘图"
BANDS_SECONDS = np.array(
    [[0.0, 7.27], [7.27, 13.73], [13.73, 21.4], [21.4, 32.31], [32.31, 40.0]]
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def load_response(name: str) -> tuple[np.ndarray, np.ndarray]:
    path = CHAPTER3 / "输入数据" / name
    matrix = np.loadtxt(path, delimiter=",", skiprows=1, encoding="utf-8-sig")
    return matrix[:, 0], matrix[:, 1:]


def nrmse_percent(reference: np.ndarray, reduced: np.ndarray) -> float:
    denominator = np.ptp(reference)
    if denominator <= 0:
        raise ValueError("参考响应幅值范围必须为正。")
    return float(np.sqrt(np.mean((reference - reduced) ** 2)) / denominator * 100.0)


def response_metrics(name: str, include_bands: bool) -> dict[str, object]:
    time, response = load_response(name)
    result: dict[str, object] = {
        "file": name,
        "sha256": sha256(CHAPTER3 / "输入数据" / name),
        "shape": list(response.shape),
        "dt_seconds": float(np.median(np.diff(time))),
        "floors": {},
    }
    for floor in range(3):
        reference = response[:, 3 * floor]
        guyan = response[:, 3 * floor + 1]
        cb = response[:, 3 * floor + 2]
        floor_result: dict[str, object] = {
            "overall_nrmse_percent": {
                "Guyan": nrmse_percent(reference, guyan),
                "Craig-Bampton": nrmse_percent(reference, cb),
            }
        }
        if include_bands:
            denominator = np.ptp(reference)
            floor_result["band_nrmse_percent"] = {
                "Guyan": [],
                "Craig-Bampton": [],
            }
            for start, end in BANDS_SECONDS:
                selection = (time >= start) & (time < end)
                for method, reduced in (("Guyan", guyan), ("Craig-Bampton", cb)):
                    value = np.sqrt(np.mean((reference[selection] - reduced[selection]) ** 2))
                    floor_result["band_nrmse_percent"][method].append(
                        float(value / denominator * 100.0)
                    )
        result["floors"][str(floor + 1)] = floor_result
    return result


def stability_summary(name: str) -> dict[str, object]:
    path = STABILITY_DIR / name
    data = loadmat(path)
    result: dict[str, object] = {"file": name, "sha256": sha256(path), "variables": {}}
    for variable in ("stab_o", "stab_C", "stab_g"):
        values = np.asarray(data[variable], dtype=float)
        common = values[:31, :67]
        unique = np.unique(values[np.isfinite(values)])
        result["variables"][variable] = {
            "shape": list(values.shape),
            "minimum": float(np.min(values)),
            "maximum": float(np.max(values)),
            "unique_count": int(unique.size),
            "unique_values_if_short": unique.tolist() if unique.size <= 35 else [],
            "stable_points_on_common_31x67_grid": int(np.count_nonzero((common > 0) & (common < 1))),
        }
    return result


def main() -> None:
    payload = {
        "earthquake": [
            response_metrics("第一类划分_ElCentro地震响应.csv", include_bands=False),
            response_metrics("第二类划分_ElCentro地震响应.csv", include_bands=False),
        ],
        "chirp": [
            response_metrics("第一类划分_Chirp响应.csv", include_bands=True),
            response_metrics("第二类划分_Chirp响应.csv", include_bands=True),
        ],
        "stability": [stability_summary("lqr_2.mat"), stability_summary("lqr_3.mat")],
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

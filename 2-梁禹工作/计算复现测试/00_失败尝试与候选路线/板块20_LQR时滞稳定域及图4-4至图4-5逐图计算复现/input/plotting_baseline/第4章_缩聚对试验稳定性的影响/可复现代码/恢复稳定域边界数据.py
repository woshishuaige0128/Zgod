from __future__ import annotations

import csv
from pathlib import Path

import numpy as np
from scipy.io import savemat

from 第4章绘图核心 import (
    章节目录,
    数据目录,
    采样周期秒,
    采样周期毫秒,
    提取上边界,
    读取稳定域掩膜,
)


方法与变量 = {
    "原结构": "stab_o",
    "Craig-Bampton": "stab_C",
    "Guyan": "stab_g",
}


def _写CSV(path: Path, fieldnames, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def 恢复一类数据(类别: int):
    唯一ID = "4-4" if 类别 == 1 else "4-5"
    划分 = "第一类子结构划分" if 类别 == 1 else "第二类子结构划分"
    源文件 = "第一类划分最终绘图数据_lqr_2.mat" if 类别 == 1 else "第二类划分最终绘图数据_lqr_3.mat"
    masks, raw_shapes = 读取稳定域掩膜(类别)
    common_shape = masks["原结构"].shape

    boundary_rows = []
    stats_rows = []
    mat_payload = {
        "dt_seconds": np.array([[采样周期秒]], dtype=float),
        "plot_index_offset": np.array([[1]], dtype=np.int32),
        "common_grid_shape": np.asarray(common_shape, dtype=np.int32),
    }

    for method in ["原结构", "Craig-Bampton", "Guyan"]:
        mask = masks[method]
        x_index, y_index, x_ms, y_ms = 提取上边界(mask)
        x_steps = x_index - 1
        y_steps = y_index - 1
        # 与绘图的 steps-post 定义一致：每个区间使用其左端上边界高度。
        area_integral = float(np.sum(y_ms[:-1] * np.diff(x_ms)))
        area_grid_proxy = float(mask.sum() * 采样周期毫秒**2)
        anomaly = "无"
        if 类别 == 2 and method in {"Craig-Bampton", "Guyan"}:
            if method == "Craig-Bampton":
                exact_position = "stab_C第36行、第68-95列为1..28"
            else:
                exact_position = "stab_g第32行、第68-95列为1..28"
            anomaly = (
                f"{exact_position}；共同31x67网格外满足0<值<1的稳定点为0，其余扩展单元全为0。"
                "原huitu_2.m按stab_o的31x67尺寸设置xlim/ylim；因此按共同物理网格裁剪，"
                "上述索引序列不参与边界。"
            )

        for xi, yi, xs, ys, xm, ym in zip(x_index, y_index, x_steps, y_steps, x_ms, y_ms):
            boundary_rows.append(
                {
                    "唯一ID": 唯一ID,
                    "划分": 划分,
                    "方法": method,
                    "源文件": 源文件,
                    "源变量": 方法与变量[method],
                    "原图横坐标索引": int(xi),
                    "原图纵坐标索引": int(yi),
                    "时滞1采样步": int(xs),
                    "时滞2采样步": int(ys),
                    "时滞1毫秒": f"{xm:.9f}",
                    "时滞2毫秒": f"{ym:.9f}",
                }
            )

        stats_rows.append(
            {
                "唯一ID": 唯一ID,
                "划分": 划分,
                "方法": method,
                "源文件": 源文件,
                "源变量": 方法与变量[method],
                "原数组尺寸": f"{raw_shapes[method][0]}x{raw_shapes[method][1]}",
                "共同物理网格": f"{common_shape[0]}x{common_shape[1]}",
                "稳定网格点数": int(mask.sum()),
                "时滞1最大采样步": int(x_steps.max()),
                "时滞1最大毫秒": f"{x_ms.max():.9f}",
                "时滞2最大采样步": int(y_steps.max()),
                "时滞2最大毫秒": f"{y_ms.max():.9f}",
                "边界积分面积_毫秒平方": f"{area_integral:.9f}",
                "稳定网格面积代理_毫秒平方": f"{area_grid_proxy:.9f}",
                "数据异常说明": anomaly,
            }
        )

        stem = {"原结构": "original", "Craig-Bampton": "craig_bampton", "Guyan": "guyan"}[method]
        mat_payload[f"{stem}_stable_mask"] = mask.astype(np.uint8)
        mat_payload[f"{stem}_boundary_plot_index"] = np.column_stack([x_index, y_index]).astype(np.int32)
        mat_payload[f"{stem}_boundary_delay_steps"] = np.column_stack([x_steps, y_steps]).astype(np.int32)
        mat_payload[f"{stem}_boundary_delay_ms"] = np.column_stack([x_ms, y_ms])

    csv_name = f"图{唯一ID}_{划分}稳定域_边界数据.csv"
    mat_name = f"图{唯一ID}_{划分}稳定域_清洗数据.mat"
    _写CSV(数据目录 / csv_name, list(boundary_rows[0].keys()), boundary_rows)
    savemat(数据目录 / mat_name, mat_payload, do_compression=True)
    return stats_rows


def 主程序() -> None:
    数据目录.mkdir(parents=True, exist_ok=True)
    stats = 恢复一类数据(1) + 恢复一类数据(2)
    _写CSV(数据目录 / "第4章稳定域统计.csv", list(stats[0].keys()), stats)
    print(f"稳定域边界、清洗MAT和统计表已写入: {数据目录}")


if __name__ == "__main__":
    主程序()

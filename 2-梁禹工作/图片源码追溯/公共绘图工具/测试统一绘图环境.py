"""生成并验证一张临时科研图，证明TeX字体和双格式导出可用。"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from PIL import Image

工具目录 = Path(__file__).resolve().parent
sys.path.insert(0, str(工具目录))
from 科研绘图样式 import 导出图片, 图幅尺寸, 方法样式, 设置坐标轴, 验证图对象  # noqa: E402


输出目录 = Path(__file__).resolve().parents[1] / "00_总索引与说明" / "环境自检"
x = np.linspace(0.0, 2.0 * np.pi, 200)
fig, ax = plt.subplots(figsize=图幅尺寸(2), constrained_layout=True)
ax.plot(x, np.sin(x), label="Origin", **方法样式["Origin"])
ax.plot(x, 0.95 * np.sin(x + 0.05), label="Craig-Bampton", **方法样式["Craig-Bampton"])
ax.plot(x, 0.80 * np.sin(x + 0.15), label="Guyan", **方法样式["Guyan"])
ax.set_xlabel(r"Time (s)")
ax.set_ylabel(r"Displacement (mm)")
ax.legend(loc="upper right")
设置坐标轴(ax)
错误 = 验证图对象(fig)
if 错误:
    raise RuntimeError("；".join(错误))
pdf, png = 导出图片(fig, 输出目录 / "统一绘图环境自检")
plt.close(fig)

with Image.open(png) as im:
    dpi = im.info.get("dpi", (0, 0))
    if min(dpi) < 590:
        raise RuntimeError(f"PNG DPI不足：{dpi}")
    print(f"PNG={im.size[0]}x{im.size[1]} px, dpi={dpi}")
print(f"PDF={pdf} ({pdf.stat().st_size} bytes)")
print(f"PNG={png} ({png.stat().st_size} bytes)")

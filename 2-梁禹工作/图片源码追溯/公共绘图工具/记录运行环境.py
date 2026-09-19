"""记录复现28张图片所需的软件版本，不修改系统设置。"""

from __future__ import annotations

import datetime as dt
import os
import platform
import subprocess
import sys
from pathlib import Path

import matplotlib
import numpy
import PIL
import scipy


工作区 = Path(__file__).resolve().parents[2]
输出 = 工作区 / "figure" / "00_总索引与说明" / "运行环境.txt"
MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")


def 运行输出(cmd: list[str], timeout: int = 120) -> str:
    result = subprocess.run(
        cmd,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        env={**os.environ, "PYTHONIOENCODING": "utf-8"},
    )
    return " | ".join(line.strip() for line in result.stdout.splitlines() if line.strip())


信息 = [
    f"生成时间：{dt.datetime.now().astimezone().isoformat(timespec='seconds')}",
    f"工作区：{工作区}",
    f"操作系统：{platform.platform()}",
    f"Python：{sys.version.replace(chr(10), ' ')}",
    f"NumPy：{numpy.__version__}",
    f"SciPy：{scipy.__version__}",
    f"Matplotlib：{matplotlib.__version__}",
    f"Pillow：{PIL.__version__}",
    f"pdfLaTeX：{运行输出(['pdflatex', '--version']).split(' | ')[0]}",
    f"XeLaTeX：{运行输出(['xelatex', '--version']).split(' | ')[0]}",
    f"MATLAB：{运行输出([str(MATLAB), '-batch', """fprintf('MATLAB_VERSION=%s\\n',version); fprintf('SIMULINK=%d CONTROL=%d ROBUST=%d IMAGE=%d\\n',license('test','Simulink'),license('test','Control_Toolbox'),license('test','Robust_Toolbox'),license('test','Image_Toolbox'));"""]) }",
]
输出.write_text("\n".join(信息) + "\n", encoding="utf-8")
print(f"已写入：{输出}")

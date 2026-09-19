"""图2-9 中文单图入口：调用 MATLAB 只读导出原生 Simulink 子系统。"""
from __future__ import annotations

import subprocess
import importlib.util
from pathlib import Path


MATLAB = Path(r"D:\Downlad\Matlab\bin\matlab.exe")
MATLAB脚本 = Path(__file__).with_name("export_fig_2_9_physical_force.m")


def 生成图2_9() -> None:
    if not MATLAB.is_file():
        raise FileNotFoundError(f"MATLAB不存在：{MATLAB}")
    if not MATLAB脚本.is_file():
        raise FileNotFoundError(f"MATLAB脚本不存在：{MATLAB脚本}")
    matlab_path = MATLAB脚本.as_posix().replace("'", "''")
    subprocess.run([str(MATLAB), "-batch", f"run('{matlab_path}')"], check=True)
    裁切脚本 = MATLAB脚本.with_name("crop_fig_2_9_vector_pdf.py")
    spec = importlib.util.spec_from_file_location("图2_9矢量裁切", 裁切脚本)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载：{裁切脚本}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.紧裁图2_9()
    # 以紧裁后的最终矢量 PDF 为唯一版式基准重新渲染 600 dpi PNG。
    pdf = MATLAB脚本.parents[1] / "PDF结果" / "图2-9_物理子结构反力计算.pdf"
    png目录 = MATLAB脚本.parents[1] / "PNG结果"
    pdftoppm = Path(r"D:\Downlad\texlive\2026\bin\windows\pdftoppm.exe")
    subprocess.run([str(pdftoppm), "-png", "-r", "600", "-singlefile", str(pdf),
                    str(png目录 / "图2-9_物理子结构反力计算")], check=True)


if __name__ == "__main__":
    生成图2_9()

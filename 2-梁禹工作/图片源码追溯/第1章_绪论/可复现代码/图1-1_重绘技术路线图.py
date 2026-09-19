"""新建重绘：图1-1 技术路线图。"""
import importlib.util
from pathlib import Path
p = Path(__file__).resolve().parents[2] / "第2章_系统缩聚理论和模型建立" / "可复现代码" / "重绘第1至2章矢量示意图.py"
s = importlib.util.spec_from_file_location("重绘示意图", p); m = importlib.util.module_from_spec(s); s.loader.exec_module(m)
m.生成单图("1-1")

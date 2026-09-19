"""八个中文入口共用的单图运行器。"""
from __future__ import annotations
import importlib.util
from pathlib import Path


def 运行(uid: str):
    path = Path(__file__).with_name("重绘第1至2章矢量示意图.py")
    spec = importlib.util.spec_from_file_location("重绘第1至2章矢量示意图", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module.生成单图(uid)

"""从任意当前目录一键重新生成第1章和第2章全部10张图片。"""
from __future__ import annotations

import importlib.util
from pathlib import Path


代码目录 = Path(__file__).resolve().parent


def _加载模块(名称: str, 路径: Path):
    spec = importlib.util.spec_from_file_location(名称, 路径)
    if spec is None or spec.loader is None:
        raise ImportError(f"无法加载：{路径}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    矢量 = _加载模块("重绘第1至2章矢量示意图", 代码目录 / "重绘第1至2章矢量示意图.py")
    for 唯一ID in ("1-1", "2-1", "2-2", "2-3", "2-4", "2-5", "2-6", "2-7", "2-8"):
        矢量.生成单图(唯一ID)

    原生 = _加载模块("图2_9导出入口", 代码目录 / "图2-9_导出物理子结构反力计算.py")
    原生.生成图2_9()

    项目根 = 代码目录.parents[2]
    预期 = [
        项目根 / "figure" / "第1章_绪论" / "PDF结果" / "图1-1_技术路线图.pdf",
        项目根 / "figure" / "第1章_绪论" / "PNG结果" / "图1-1_技术路线图.png",
    ]
    图题 = {
        "2-1": "RTHS反馈控制闭环图", "2-2": "Craig-Bampton法子结构划分",
        "2-3": "参考结构尺寸", "2-4": "参考结构自由度", "2-5": "简化自由度",
        "2-6": "第一类子结构划分", "2-7": "第二类子结构划分",
        "2-8": "Simulink模型", "2-9": "物理子结构反力计算",
    }
    章根 = 项目根 / "figure" / "第2章_系统缩聚理论和模型建立"
    for 唯一ID, 标题 in 图题.items():
        预期.extend((章根 / "PDF结果" / f"图{唯一ID}_{标题}.pdf",
                   章根 / "PNG结果" / f"图{唯一ID}_{标题}.png"))
    缺失 = [str(p) for p in 预期 if not p.is_file() or p.stat().st_size == 0]
    if 缺失:
        raise RuntimeError("生成后缺失结果：\n" + "\n".join(缺失))
    验收 = _加载模块("验证第1至2章交付", 代码目录 / "验证第1至2章交付.py")
    验收.验证()
    print(f"已重新生成并核验 {len(预期) // 2} 张图片的 PDF+PNG。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

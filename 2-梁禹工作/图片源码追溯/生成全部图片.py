"""从任意当前目录一键重建、汇总并审计梁禹论文全部28张图片。"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


图片根 = Path(__file__).resolve().parent
工作区 = 图片根.parent
工具 = 图片根 / "公共绘图工具"


def 运行脚本(path: Path) -> None:
    print(f"\n[运行] {path.relative_to(工作区)}", flush=True)
    env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
    subprocess.run([sys.executable, str(path)], cwd=工作区, env=env, check=True)


def 主函数() -> int:
    章节入口 = sorted(
        p
        for p in 图片根.glob("第*章_*/可复现代码/生成第*章全部图片.py")
        if p.is_file()
    )
    # 第1章和第2章允许合并为同一个“生成第1至2章全部图片.py”入口。
    if len(章节入口) != 3:
        found = [p.relative_to(工作区).as_posix() for p in 章节入口]
        raise RuntimeError(f"应找到3个章节级一键入口（第1至2章合并、第3章、第4章），实际{found}")
    for path in 章节入口:
        运行脚本(path)

    for name in (
        "汇总章节交付清单.py",
        "记录运行环境.py",
        "核验原始来源未改动.py",
        "生成最终图片哈希清单.py",
        "审计全部图片.py",
        "生成审阅总览.py",
        "生成验证总报告.py",
    ):
        运行脚本(工具 / name)
    print("\n全部28张图片已重建并通过自动完整性审计。", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(主函数())

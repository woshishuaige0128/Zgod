#!/usr/bin/env python3
"""为板块18的12张候选PNG生成三张只读视觉巡检蒙太奇。"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


BOARD = Path(__file__).resolve().parents[1]
SOURCE = BOARD / "outputs" / "figure_candidates"
OUTPUT = BOARD / "outputs" / "visual_review_tmp"
CELL = (1280, 900)
LABEL_HEIGHT = 70
MARGIN = 30


def font(size: int) -> ImageFont.FreeTypeFont:
    candidates = (
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/arial.ttf"),
    )
    for candidate in candidates:
        if candidate.is_file():
            return ImageFont.truetype(str(candidate), size=size)
    raise FileNotFoundError("未找到可用于蒙太奇标签的Windows字体")


def label_for(path: Path) -> str:
    return f"{path.parents[1].name} / {path.stem}"


def main() -> int:
    paths = sorted(SOURCE.rglob("*.png"), key=lambda path: path.as_posix())
    if len(paths) != 12:
        raise RuntimeError(f"应有12张候选PNG，实际{len(paths)}")
    if OUTPUT.exists():
        raise FileExistsError(f"视觉巡检临时目录已存在，拒绝覆盖：{OUTPUT}")
    OUTPUT.mkdir(parents=True)
    title_font = font(30)
    for group_index in range(3):
        group = paths[group_index * 4 : (group_index + 1) * 4]
        canvas = Image.new(
            "RGB",
            (2 * (CELL[0] + 2 * MARGIN), 2 * (CELL[1] + LABEL_HEIGHT + 2 * MARGIN)),
            "white",
        )
        draw = ImageDraw.Draw(canvas)
        for item_index, path in enumerate(group):
            row, column = divmod(item_index, 2)
            x0 = column * (CELL[0] + 2 * MARGIN) + MARGIN
            y0 = row * (CELL[1] + LABEL_HEIGHT + 2 * MARGIN) + MARGIN
            with Image.open(path) as source:
                image = ImageOps.contain(source.convert("RGB"), CELL, Image.Resampling.LANCZOS)
            x = x0 + (CELL[0] - image.width) // 2
            y = y0 + (CELL[1] - image.height) // 2
            canvas.paste(image, (x, y))
            draw.rectangle((x0, y0, x0 + CELL[0], y0 + CELL[1]), outline="#777777", width=2)
            draw.text((x0, y0 + CELL[1] + 14), label_for(path), fill="black", font=title_font)
        output = OUTPUT / f"board18_visual_montage_{group_index + 1}.png"
        canvas.save(output, format="PNG", dpi=(150, 150))
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

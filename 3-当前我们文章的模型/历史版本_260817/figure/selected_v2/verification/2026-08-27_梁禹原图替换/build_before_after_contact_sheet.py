from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps


SELECTED_DIR = Path(__file__).resolve().parents[2]
OUTPUT_PATH = Path(__file__).resolve().parent / "图1至图5_梁禹原图与Image2_v2并排总览.png"

PAIRS = [
    ("图1", "fig01_rths_loop_optionD.png", "fig01_rths_loop_optionD_v2.png"),
    ("图2", "fig02_pole_mapping_optionB.png", "fig02_pole_mapping_optionB_v2.png"),
    ("图3", "fig03_benchmark_geometry_optionC.png", "fig03_benchmark_geometry_optionC_v2.png"),
    ("图4(a)", "fig04a_dof_assumptions_optionD.png", "fig04a_dof_assumptions_optionD_v2.png"),
    ("图4(b)", "fig04b_dof_idealized_optionD.png", "fig04b_dof_idealized_optionD_v2.png"),
    ("图5(a)", "fig05a_divisionI_concept_optionD.png", "fig05a_divisionI_concept_optionD_v2.png"),
    ("图5(b)", "fig05b_divisionII_concept_optionD.png", "fig05b_divisionII_concept_optionD_v2.png"),
]


def font(size: int) -> ImageFont.FreeTypeFont:
    for path in [Path("C:/Windows/Fonts/msyh.ttc"), Path("C:/Windows/Fonts/simhei.ttf")]:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def main() -> None:
    missing = [name for _, current, old in PAIRS for name in (current, old) if not (SELECTED_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"缺少图片：{missing}")

    margin = 36
    gutter = 24
    title_h = 88
    header_h = 50
    row_h = 500
    cell_w = 930
    label_w = 100
    footer_h = 65
    width = margin * 2 + label_w + cell_w * 2 + gutter
    height = margin * 2 + title_h + header_h + len(PAIRS) * row_h + footer_h
    canvas = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(canvas)
    draw.text((width // 2, margin), "图1—图5替换前后并排核对", font=font(38), fill="#202020", anchor="ma")
    y_header = margin + title_h
    draw.text((margin + label_w + cell_w // 2, y_header), "当前稳定引用：梁禹大论文600 dpi原图", font=font(25), fill="#202020", anchor="ma")
    draw.text((margin + label_w + cell_w + gutter + cell_w // 2, y_header), "_v2保留版：此前选定的Image 2图片", font=font(25), fill="#202020", anchor="ma")

    for index, (label, current_name, old_name) in enumerate(PAIRS):
        y0 = y_header + header_h + index * row_h
        draw.text((margin + label_w // 2, y0 + row_h // 2), label, font=font(27), fill="#202020", anchor="mm")
        for column, filename in enumerate((current_name, old_name)):
            x0 = margin + label_w + column * (cell_w + gutter)
            draw.rounded_rectangle((x0, y0 + 8, x0 + cell_w, y0 + row_h - 8), radius=8, outline="#B0B0B0", width=2)
            with Image.open(SELECTED_DIR / filename) as source:
                image = ImageOps.contain(source.convert("RGB"), (cell_w - 38, row_h - 54), Image.Resampling.LANCZOS)
            canvas.paste(image, (x0 + (cell_w - image.width) // 2, y0 + (row_h - image.height) // 2))

    draw.text(
        (width // 2, height - margin - 5),
        "左列为当前TeX实际引用；右列为完整保留的替换前版本。总览只用于视觉核对。",
        font=font(21),
        fill="#505050",
        anchor="ms",
    )
    canvas.save(OUTPUT_PATH, dpi=(180, 180), optimize=True)
    print(f"已生成：{OUTPUT_PATH}")
    print(f"尺寸：{canvas.width} x {canvas.height} px；配对数量：{len(PAIRS)}")


if __name__ == "__main__":
    main()

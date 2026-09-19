"""按稿件顺序一键生成图6至图10。"""

from 图6至图10_绘图核心 import (
    绘制_图10_稳定域双面板,
    绘制_图6_第一类ElCentro响应,
    绘制_图7_第二类ElCentro响应,
    绘制_图8_第一类Chirp响应,
    绘制_图9_第二类Chirp响应,
)


def main() -> None:
    functions = (
        绘制_图6_第一类ElCentro响应,
        绘制_图7_第二类ElCentro响应,
        绘制_图8_第一类Chirp响应,
        绘制_图9_第二类Chirp响应,
        绘制_图10_稳定域双面板,
    )
    for function in functions:
        pdf, png = function()
        print(f"已生成：{pdf}")
        print(f"已生成：{png}")


if __name__ == "__main__":
    main()

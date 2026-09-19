"""生成期刊图8：第一类划分Chirp一层/三层响应。

输入：第一类划分_Chirp响应.csv。
对照：梁禹大论文唯一编号图3-11（PDF第46页）和图3-13（第47至48页，相关图在第48页上部）。
"""

from 图6至图10_绘图核心 import 绘制_图8_第一类Chirp响应


if __name__ == "__main__":
    for path in 绘制_图8_第一类Chirp响应():
        print(path)

"""生成期刊图9：第二类划分Chirp一层/三层响应。

输入：第二类划分_Chirp响应.csv。
对照：梁禹大论文唯一编号图3-14（PDF第48页下部）和图3-15（PDF第49页）。
"""

from 图6至图10_绘图核心 import 绘制_图9_第二类Chirp响应


if __name__ == "__main__":
    for path in 绘制_图9_第二类Chirp响应():
        print(path)

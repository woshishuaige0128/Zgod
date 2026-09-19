"""生成期刊图7：第二类划分El Centro一层/三层响应。

输入：第二类划分_ElCentro地震响应.csv。
对照：梁禹大论文图3-9（PDF第44页）和图3-10（PDF第45页）。
"""

from 图6至图10_绘图核心 import 绘制_图7_第二类ElCentro响应


if __name__ == "__main__":
    for path in 绘制_图7_第二类ElCentro响应():
        print(path)

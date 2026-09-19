"""生成期刊图6：第一类划分El Centro一层/三层响应。

输入：第一类划分_ElCentro地震响应.csv。
对照：梁禹大论文图3-6（PDF第42页）和图3-8（PDF第43页）。
"""

from 图6至图10_绘图核心 import 绘制_图6_第一类ElCentro响应


if __name__ == "__main__":
    for path in 绘制_图6_第一类ElCentro响应():
        print(path)

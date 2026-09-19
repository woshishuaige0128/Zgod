# Fig.6 MATLAB操作说明

这个文件夹可以单独复制到任意位置运行。它不读取本文件夹之外的代码、数据或公共函数。

## 这张图是什么

- 内容：第一类子结构划分在 El Centro 地震输入下的一层与三层位移响应。
- 两行：上面是一层，下面是三层。
- 三列：40 s全时程、10–11 s局部窗、21.5–22.5 s局部窗。
- 三种方法：Original、Craig–Bampton、Guyan。

## 一步一步生成图片

1. 将整个 `Fig06_第一类划分_ElCentro响应` 文件夹复制到您需要的位置；不要只复制 `.m` 文件。
2. 打开 MATLAB。
3. 在 MATLAB 左侧“当前文件夹”窗口中进入这个图文件夹。
4. 双击 `RUN_THIS_FIGURE.m`。
5. 点击编辑器顶部绿色三角形“运行”。也可以在命令窗口输入 `RUN_THIS_FIGURE` 后按回车。
6. 等到命令窗口出现 `Fig.6 generated successfully.`。
7. 打开 `输出` 文件夹查看结果：
   - `输出/PDF/fig06_eq_div1.pdf`：论文用矢量图；
   - `输出/PNG/fig06_eq_div1.png`：600 dpi预览图；
   - `输出/plotted_data.mat`：真正传给18条曲线的绘图数据；
   - `输出/data_audit.csv`：输入尺寸、时间步长和实际字体记录。

## 一步一步验证

1. 双击 `VERIFY_THIS_FIGURE.m`。
2. 点击绿色三角形“运行”。也可以输入 `VERIFY_THIS_FIGURE` 后按回车。
3. 看到 `Fig.6 validation PASS.` 才表示通过。
4. 打开 `输出/validation_report.txt`，第一行必须是 `STATUS=PASS`。

验证脚本会重新读取CSV，独立重算6个坐标轴中的18条曲线，并检查每条曲线最大误差不超过 `1e-12`。

## 文件移动后为什么仍能运行

两个入口都通过 `fileparts(mfilename('fullpath'))` 找到自身位置，再用 `fullfile` 查找同一文件夹内的数据和输出目录。因此，MATLAB启动位置和这个文件夹的磁盘位置不会改变结果。

## MATLAB版本与字体

- 建议 MATLAB R2020a 或更新版本，以使用 `exportgraphics`。
- 程序优先使用 `CMU Serif`；若电脑没有该字体，则使用 `Times New Roman`，最后回退到 `Serif`。
- 实际使用的字体会写入 `输出/data_audit.csv` 和 `输出/validation_report.txt`。

## 不要改动的内容

- 不要改变输入CSV的列顺序。
- 不要只移动 `RUN_THIS_FIGURE.m`；应移动整个图文件夹。
- 如果需要改配色或时间窗，先保留本文件夹副本，再改新副本。

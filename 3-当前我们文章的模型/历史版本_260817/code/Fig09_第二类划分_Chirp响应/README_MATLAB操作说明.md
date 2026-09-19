# Fig. 9：第二类子结构划分的 Chirp 响应

这个文件夹可以单独复制到任意位置运行。它不需要总代码包，也不读取文件夹外的数据。

## 第一次画图

1. 打开 MATLAB。
2. 在 Windows 文件资源管理器中打开本文件夹。
3. 双击 `RUN_THIS_FIGURE.m`，MATLAB 编辑器会显示脚本。
4. 点击编辑器上方绿色的 **运行** 按钮。
5. 等待命令窗口显示“Fig. 9 绘制完成”。

输出在：

- `输出/PDF/fig09_chirp_div2.pdf`：论文排版用的矢量图。
- `输出/PNG/fig09_chirp_div2.png`：600 dpi 预览图。
- `输出/plotted_data.mat`：本次绘图实际读取的数据快照。
- `输出/data_audit.csv`：数据尺寸、时间范围、步长和有限性检查。

## 检查是否真的成功

1. 双击 `VERIFY_THIS_FIGURE.m`。
2. 点击绿色的 **运行** 按钮。
3. 命令窗口出现“Fig. 9 验收通过”即表示通过。
4. 打开 `输出/validation_report.txt`，第一行必须是 `STATUS=PASS`。

## 图中六个小窗表示什么

- 第一行：一层位移；第二行：三层位移。
- 第一列：0–40 s 全时程。
- 第二列：13–14 s 局部放大。
- 第三列：38–38.3 s 局部放大。
- 灰色圆点虚线：Original。
- 红色方块实线：Craig–Bampton。
- 蓝色三角点划线：Guyan。

脚本优先使用 `CMU Serif`。如果电脑没有安装该字体，就使用 `Times New Roman`；实际采用的字体会写入 `输出/data_audit.csv` 和 `输出/validation_report.txt`。

## 重新运行

可以直接再次运行 `RUN_THIS_FIGURE.m`。同名PDF、PNG和数据快照会被本次结果更新；输入CSV不会被修改。

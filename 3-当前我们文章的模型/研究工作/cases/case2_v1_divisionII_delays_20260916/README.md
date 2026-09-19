# 划分二多时滞案例选图

本目录用于 Doctor Bego 选择论文的有时滞展示工况。18组时滞（含零时滞），每组地震与扫频两输入、四种模型。具体选点和科学状态以 results/selected_delays.json、主报告为准。

## 先看图
- 主报告：../../reports/划分二多时滞案例选图汇报.html。包含全部候选、稳定性、图件、可展开指标、筛选和候选标记，可离线移动。
- PDF：../../reports/划分二多时滞案例选图.pdf。
- figures：每个候选两幅图，文件名n05_01表示首层5步、顶层1步；每步0.9765625 ms。另有整数时滞图、等时滞误差图和局部对照图。所有图同时提供矢量PDF和600dpi PNG。

## 三个优先查看的组合
- 首层/顶层均3.90625 ms：稳定等时滞候选。
- 首层4.8828125 ms、顶层0.9765625 ms：稳定且接近Guyan边界的不等时滞候选。
- 首层4.8828125 ms、顶层1.953125 ms：Guyan失稳、CB和两个未缩聚参考稳定，用于稳定性差异展示。40秒内是否明显增长还受激励和模态参与影响。
- 首层/顶层均4.8828125 ms：三个子结构模型失稳，完整15参考稳定；单独作失稳示例。

## 模型含义
- Full15：原完整框架15自由度，物理部分仅首层和顶层两列反力带时滞，其余界面理想协调。
- Uncondensed19：数值12自由度、物理9自由度，只共享两个作动坐标，共19自由度。实现采用全部固定界面模态的可逆变换；它与直接保留局部自由度的装配一致。
- Guyan6：两个子结构分别标准合同投影后，仅在两个作动坐标装配；6自由度。
- CB12：每子结构保留3个质量归一化固定界面模态；12自由度。

主要误差图比较Guyan/CB相对于相同时滞Uncondensed19的偏差。CSV同时给出相对于相同时滞Full15、零时滞Full15的指标。三种参照不能混用。

## 计算代码
在复制出的目录中依次运行：
1. `D:/Software/python/python.exe -X utf8 code/prepare_delays.py`：构建和检查模型、调查81个整数时滞组合、确定18个候选，写model_and_cases.mat。
2. MATLAB：`addpath('code'); RUN_DELAY_RESPONSES; VERIFY_LQR`。需要Control System Toolbox。默认结果写results/matlab_run；目录存在时拒绝覆盖。可显式指定新的输出目录；第二参数可给待运行的候选序号。
3. `D:/Software/python/python.exe -X utf8 code/check_responses.py MATLAB输出目录`：Python独立增广状态重算、反馈平衡核验和全指标。
4. `D:/Software/python/python.exe -X utf8 code/plot_delays.py`：39幅科学图。需要NumPy、SciPy、Matplotlib、TeX Live和Poppler。
5. `D:/Software/python/python.exe -X utf8 code/verify_figures.py` 及 `code/build_selection_report.py`。

运行Python前建议PowerShell设置 `$env:PYTHONIOENCODING='utf-8'` 和 `$env:OPENBLAS_NUM_THREADS='1'`。正式结果来自MATLAB直接CR递推；Python用独立增广状态方程逐时刻交叉校验。当前输出未作为仿真的输入。

## 关键文件
- data/EQ.mat：原始地震输入。
- sources：本轮冻结来源副本与SHA-256，不是待编辑原稿。
- results/model_and_cases.mat：局部装配模型、共同LQR增益、输入、时滞、增广矩阵。
- results/n*_responses.npz：全部候选的三楼层物理端和数值端完整时程。
- results/response_metrics.csv：各候选、输入、方法、楼层的全部指标。
- results/*checks.json：实际数值/图件/报告检查。
- results/figure_records.json：每幅图的时滞、输出、坐标和曲线数据哈希。
- 本轮MATLAB完整q/v内部状态保存在 ../../temp/divisionII_delays_20260916/matlab_run；主交付保留可重新产生它们的代码及输出层时程，避免把大量中间状态混进图件目录。

## 当前边界
本轮是依据现稿假定重建的子结构闭环，具有相同全框架参数但不同于上一轮直接缩聚全框架的15/5/8模型。共同通道反馈用于隔离结构/接口影响，并非每种模型分别重新设计LQR。源局部脚本两处额外转角刚度及局部10%阻尼未沿用，原因与验证见MODEL_SPECIFICATION.md。

本轮计算与选图材料完成后，正式采用哪个时滞由Doctor Bego决定；不把绘图和数值核验当作新理论证明或外部审查。

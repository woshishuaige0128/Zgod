# 标准 Guyan 与现稿逐图对照

本案例由 Doctor Bego 于2026-09-16授权：先计算标准Guyan，再按论文案例图逐张比较。原稿未修改。

## 首先看什么
- 主汇报：../../reports/标准Guyan重算与论文逐图新旧对照汇报.html。
- 方便翻阅：../../reports/标准Guyan论文逐图新旧对照.pdf。
- figures/pairs：图5—15的独立并排PNG；图14新边界明确待计算。
- figures/standard：9张新结果图及相同输入图5，PDF为矢量，PNG为600dpi。
- figures/legacy_same_scale：本轮重算的旧实现，和标准图采用完全相同坐标范围。
- sources/original_figures：现稿原图，15张均已与当前PDF像素核对。

## 实际计算与关键结果
完成旧/标准两实现×两划分×两输入，共8套Simulink响应。每套40961时刻、3楼层×3模型，0—40秒、dt=1/1024秒、ode4、零初值。完整模型和CB新旧保持一致。

标准Guyan采用同一静态基底，对M、C、K均执行合同投影，荷载继续T转置f；没有调整结构质量、阻尼比、输入幅值或CB模式数。扫频输入沿用原From Workspace网格插值，未把本次数值结果当作连续扫频解析解。

划分二首层地震NRMSE从10.911259%降到0.642096%；扫频全记录从11.714831%降到1.272224%。第二阶频率误差从30.574461%降到7.549461%。中间层恢复误差和动能份额见报告及results中的全精度数据。

## 代码和数据
- RUN_COMPARISON.m：MATLAB入口，实际数值计算，不读取旧响应作为输入。
- code/*.m：完整框架装配、Guyan/CB、输入、Simulink积分、模态和指标。
- 必要输入/EQ.mat：本轮冻结的地震输入。
- results/legacy 与 results/standard：本轮完整数据、指标CSV、MAT以及可打开的SLX。
- code/PLOT_COMPARISON.py：已采用的Python/Matplotlib绘图代码。
- sources/source_manifest.json、figure_map.json：来源哈希与原稿图号映射。

## 重跑方法
MATLAB需要Simulink和Control System Toolbox。打开本目录后运行 `RUN_COMPARISON`，默认写入results下新的时间戳目录，不覆盖本轮封存结果。也可显式传入一个尚不存在的输出目录。

Python绘图需要NumPy、SciPy、Matplotlib、TeX Live与Poppler。运行 `D:/Software/python/python.exe -X utf8 code/PLOT_COMPARISON.py 计算结果目录`；计算目录须含legacy/standard。绘图入口会重建figures中的对应图，建议复制案例后试验。测试及绘图缓存放temp。

## 验收及科学状态
290项数值核验通过，独立Python RK4与Simulink最大差3.943512183468556e-13 mm。旧实现与现稿数据、完整模型/CB保持、模态、荷载、恢复和指标分别核验。图件数值映射、共同坐标、矢量/600dpi、HTML离线交互及PDF页面验收见results/*qa.json。

图14历史稳定边界没有被当作标准Guyan的新结果。新误差理论、CR闭环稳定域和GPT Pro外部审查仍未开展。本轮用于审阅实现变化的影响。

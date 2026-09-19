# Guyan 双侧投影对论文结论的影响核查

## 任务目的

在不修改论文、原 MATLAB/Simulink 模型、原始矩阵、历史数据和既有图片包的前提下，对同一 15 自由度框架、同一两种子结构划分、同一 El Centro 与 chirp 激励进行两条 Guyan 路线对照：

1. 历史路线：只把静力从自由度关系代入主自由度平衡方程，质量、阻尼和刚度采用单侧消元；载荷仍沿用原 Simulink 中的 `T'*Mf`。
2. 标准路线：使用同一个 Guyan 变换 `T=[I;-Kss\Ksm]`，对质量、阻尼、刚度和载荷执行双侧合同投影。

最终逐条判断 `manuscript_0823V2_all_figures.tex` 中依赖 Guyan 数值的结论属于 A（保持）、B（排序保持但数字需改）、C（结论需收缩）、D（被当前计算反驳）或 E（证据不足）。

## 隔离边界

- 本目录是唯一新增计算目录。
- 原论文、原模型、原始数据、历史输出和图片包只读。
- 不研究稳定性、LQR 或能量指标。
- 不新增子结构划分、激励、参数、算例或评价指标。
- 本轮不编辑论文；计算结束后只提交影响报告。

## 目录

- `source_manifest.csv`：源文件路径、时间戳、大小及冻结前后 SHA-256。
- `assumptions.md`：自由度、公式、输入、输出和指标口径。
- `input_copies/`：计算所需源文件的逐字节副本。
- `code/`：冻结、MATLAB 主计算、Python 独立复核和绘图代码。
- `outputs/`：矩阵、频率、时程和指标 CSV/MAT。
- `logs/`：真实命令、退出码、标准输出和失败迭代。
- `figures/`：仅用于本核查的对比 PDF/PNG。
- `report/Guyan结论影响核查.md`：逐结论影响报告。

## 当前状态

计算与核验已完成，论文保持未修改：

- 23 个源文件冻结前/复制件/冻结后 SHA-256 一致；最终源哈希复核见 `outputs/source_integrity_final.csv`。
- MATLAB 四个历史基线 `4/4 PASS`，随后完成标准双侧路线的同四个既有案例；退出码 0。
- Python 独立重构与指标复核 `1582/1582 PASS`，0 violations；证据见 `outputs/python_validation_summary.json`。
- 4 组审计对比图均输出矢量 PDF 与 600 dpi PNG，自动验收 `4/4 PASS`。
- 总体论文影响为 **C（核心排序保持，但结论必须收缩）**：CB 的 NRMSE 仍在 42/42 项中更小，Division II 仍在 21/21 项中更困难；但“Division II 不应使用 Guyan”等强结论不再由标准公式支持。
- 已触发 C 级停止门槛。当前只交 `report/Guyan结论影响核查.md`，等待 Doctor Bego 选择文章策略；没有编辑 TeX，也没有计算稳定性、LQR 或能量。

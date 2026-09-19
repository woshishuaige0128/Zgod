# 完整框架等时滞统一模型：候选方案与代数原型

本包回答如何使完整、Guyan和Craig–Bampton（CB）模型表示同一原15自由度框架的同一等时滞反馈路径。两条候选基底分别是完整框架直接缩聚，以及保留所有共同界面后分别进行局部缩聚。两者都依赖未作动界面的理想补充协调，正式采用和实验实现解释尚待研究决定。

## 阅读顺序

1. 主汇报：`../../reports/完整框架等时滞统一模型方案汇报.html`，单文件可独立移动。
2. `theory/unified_full15.pdf`及同名可编辑TeX：完整定义、推导、两条路线及审查问题。
3. `results/model_summary.json`：真实保留坐标、模型阶数和局部质量检查。
4. 三份`validation_*.json`：1066项统一模型检查、432项独立MATLAB检查、24项误差恒等式检查。

## 代码与输入

- `code/unified_model.py`：完整物理坐标反馈、两类基底、一致投影、连续/CR特征算子和通道历史矩阵；不含时程积分入口。
- `code/verify_unified.py`：系数恒等、兼容装配、零/全模态极限、单步代数及完整恢复。
- `code/VERIFY_UNIFIED.m`：独立求模态及完整坐标历史递推。
- `code/verify_error_identities.py`：残量误差恒等式与遗漏模态Schur补。
- `sources/`：冻结原完整矩阵、上一轮局部矩阵和已有控制增益等7项输入；来源及SHA-256见`source_manifest.json`。
- `results/operators.mat`：可交叉检查的候选系数与基底。

检查脚本采用相对路径读取本包的sources/results，不需要回读原案例。环境为Python的NumPy/SciPy与MATLAB。本轮没有生成新地震/扫频时程或进行稳定边界扫描。

## 在独立临时副本复核

先把本目录复制到研究根temp内，再在副本内运行；保护正式结果。

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:OPENBLAS_NUM_THREADS='1'
& 'D:/Software/python/python.exe' -B -X utf8 code/verify_unified.py
& 'D:/Software/python/python.exe' -B -X utf8 code/verify_error_identities.py
& 'D:/Downlad/Matlab/bin/matlab.exe' -batch "addpath('code'); VERIFY_UNIFIED('results/validation_matlab.json')"
```

TeX使用XeLaTeX，两次编译解决内部交叉引用；本文件使用文内完整出处，不调用BibTeX。`build_report.py`用于原研究目录中的报告重建，不属于独立数值核验入口。

## 科学状态与关键选择

- 结构与算法一致性：本地代数通过。对原框架的实际响应误差、稳定边界和“CB更好”的范围尚未由本轮新增计算。
- 完整框架路线：Guyan6/5、CB保留3内部模态时9/8阶；保留原划分二中间层位移被缩聚的问题。
- 完整界面局部路线：两划分Guyan均9阶。划分一内部模态数上限为数值5、物理1；划分二为数值3、物理3。划分一零质量坐标被保留于共同界面，内部模态质量正定问题得到解决，未改质量分配。
- 两条路线分别改变原理论的缩聚层级或界面保留集合；都需要用户确定论文定位。原代码、稿件、两个旧案例和上一轮审计保持。
- 本轮固定增益仅为代数测试系数，来自已验证的划分二控制器。尚未重新设计划分一控制器。
- 理论审查材料已准备，尚未发送或收到外部意见。详见研究根pro_reviews/unified_full15_equal_delay_20260916。

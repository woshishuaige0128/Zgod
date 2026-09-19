# 原完整框架基准与两套模型一致性核查

本轮只核查模型、代数恒等式和既有时程，不改变接口理论，不运行新时程仿真。

主汇报：../../reports/原完整框架基准与两套模型一致性核查汇报.html。

## 文件与结论

- sources/：冻结代码、原稿和矩阵来源；source_manifest.json登记29个来源，含按绝对路径读取的既有响应文件。
- code/audit_models.py：完整框架缩聚极限、局部装配及协调、质量秩、延迟/投影次序、等时滞既有时程分解。
- code/VERIFY_ALGEBRA.m：MATLAB独立执行历史源脚本的矩阵定义，检查完整协调后的矩阵与延迟次序。
- results/algebra_checks.json：134项检查，验收标准1e-10。
- results/findings.json：模型尺寸、遗漏约束、零质量坐标及延迟算子差异。
- results/error_decomposition.csv：6组已有等时滞、两输入、两缩聚方法、三楼层，共72行。失稳行只用于分解闭合，不用于正常精度排序。
- results/audit_matrices.mat：约束矩阵、恢复映射、局部矩阵及延迟算子诊断。
- evidence_map.json：关键结论的冻结文件与行号。
- MODEL_AUDIT.md：代数解释与必要的科学状态边界。

## 运行

Python：D:/Software/python/python.exe，设置PYTHONIOENCODING=utf-8、OPENBLAS_NUM_THREADS=1。

1. 运行 `code/audit_models.py`。它读取封存的两个案例，不运行它们的仿真入口。
2. MATLAB添加本目录code路径，运行 `VERIFY_ALGEBRA('研究根/temp/full_order_consistency_20260916/matlab_algebra.mat')`。
3. 运行 `code/build_report.py`。

检查运行在同一研究根中。报告本身可独立离线移动，审计代码依赖source_manifest中明确列出的既有响应，不声称整个审计目录脱离原研究根仍能重算。

## 主要结果

标准Guyan已正确实现。完整框架的CB全内部模态恢复15自由度；只共享两作动坐标的局部完整空间分别为18和19坐标。划分一按历史集中质量分配重建时存在一个数值侧零质量坐标，普通正定质量全模态展开前提不满足。有时滞下，坐标变换和沿坐标选列延迟不自动交换，因此前轮19-15之差在非零时滞时不能称为纯接口误差。

本轮核查完成不等于统一模型完成；后续理论修订、响应计算和正式图件均需按报告中的研究决定继续。

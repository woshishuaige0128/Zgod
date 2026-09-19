# 图10六曲线严格目标评估器

## 证据边界

- `strict_target_evaluator.py` 只读候选边界/掩膜与冻结的 `plotted_data.mat`，不导入或运行求解器。
- 目标点由评估器在运行时读取，没有写入参数搜索代码。
- 评估通过只能表述为“目标引导的校准计算复现”；它不证明已恢复作者原始参数合同。

## 输入

复制 `candidate_manifest_template.json` 并显式绑定六条曲线。清单必须恰好包含：

1. `division1_original`：第一类子结构划分 / Original。
2. `division1_craig_bampton`：第一类子结构划分 / Craig--Bampton。
3. `division1_guyan`：第一类子结构划分 / Guyan。
4. `division2_original`：第二类子结构划分 / Original。
5. `division2_craig_bampton`：第二类子结构划分 / Craig--Bampton。
6. `division2_guyan`：第二类子结构划分 / Guyan。

`boundary_csv` 必须提供连续的 `point_order=1..N` 和 1-based `tau1_step/tau2_step`。可选 `tau1_ms/tau2_ms`；若提供，会额外验证换算误差。

`mask_csv` 必须是无表头 0/1 矩阵，并声明尺寸和固定规则 `matlab_bwboundaries_8_noholes_visible_open`。评估器调用 `fig10_extract_mask_boundaries.m` 执行 `bwboundaries(M,8,'noholes')`，取 `B{1}`，再删除 `x<=1` 或 `y<=1` 的坐标轴闭合段。

## 运行

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" `
  ".\strict_target_evaluator.py" `
  --manifest ".\candidate_manifest.json" `
  --output-dir "..\evaluation\candidate_id"
```

动态正/反例自测：

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" `
  ".\strict_target_evaluator.py" `
  --self-test `
  --output-dir "..\evaluation\strict_evaluator_selftest"
```

返回码：`0=PASS`，`2=VALID EVALUATION BUT FAIL`，`1=ERROR`。

## 严格主门

- 六曲线点数为 `72/69/67/69/56/53`，总点数为 `386`。
- 原始顺序逐点完全一致；整体反转仅作诊断，不计入通过。
- 集合差为 0，起点和终点均一致。
- 对称 Hausdorff 距离为 0，点级 Levenshtein 编辑距离为 0。
- 坐标合同为 `tau_ms=(tau_step-1)*1000/1024`，毫秒误差不超过 `1e-12`。

## 机读输出

- `strict_evaluation_summary.json`：全局主门、六曲线全部指标、输入/目标/代码哈希。
- `curve_metrics.csv`：每条曲线一行的严格指标。
- `pointwise_comparison.csv`：原始顺序的步号与毫秒逐点对比。
- `set_differences.csv`：候选缺失点与多余点。
- `artifact_hashes.csv`：评估输出 SHA-256 清单。

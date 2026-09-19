# 复算入口与证据

主汇报：本目录上一级的《表3至表5数值准确性核查汇报.html》。

本次核查从原入口第1--7节重新计算四套时程；原输入、计算段和局部函数保持字节内容一致。仅跳过出图和读取参考CSV的末端比较。临时计算的精确位置见 `evidence/runtime_derivation.json`。

复算顺序：
1. MATLAB执行 `tmp/table345_audit_20260906/temp/run_four_audit_cases.m`，会重新生成临时运行目录中的计算数据。
2. 用 `D:/Software/python/python.exe -X utf8` 运行 `code/compute_metrics.py`。
3. 在MATLAB将本目录 `code` 加入路径，运行 `compute_metrics_matlab`。
4. 用相同Python执行 `code/build_report.py`，比较两种实现并生成报告。
5. 用捆绑Node执行 `code/qa_report.cjs`，使用本机Chrome验证本地HTML并生成临时A4打印版；再执行 `code/finalize_audit.py`。

`prepare_audit.py` 仅用于建立首次来源冻结和隔离运行目录；如已有冻结清单会拒绝覆盖。没有必要重新运行它。

本报告的Python/MATLAB指标计算读取的是本轮重新生成的 `audit_snapshot.mat`。当前绘图CSV只用于新计算结束后的误差检查。原表数值仅用于最后的逐格判定，未参与模型、振型或响应计算。

原始图10生成模型不完整，本次表5以图6--9可执行模型套用现稿公式得到条件结果；这不等于证明它与图10历史稳定边界同模型。

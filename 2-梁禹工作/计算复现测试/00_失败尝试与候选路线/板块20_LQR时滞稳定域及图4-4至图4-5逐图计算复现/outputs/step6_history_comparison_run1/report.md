# Board20 Step6 - 历史稳定域与作者文件身份候选计算核对

## 人话结论

历史 `.mat` 可以在共同 31×67 网格上完整恢复为六个绘图级稳定掩膜；现有作者文件身份候选路线也都能给出完整 2,077 点连续谱半径，但没有一条候选与对应历史掩膜逐点一致，而且两种划分都缺少 Craig–Bampton 的可执行连续谱半径路线。因此图4-4、图4-5仍只能保留为绘图级复现，候选计算属于失败诊断，不能建立正式成功目录。

## 逐路线结果

| 图 | 方法 | 路线 | 候选稳定点 | 历史稳定点 | 错配点 | TP | TN | FP | FN | 状态 |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| F4-4 | Original | main_ori_div1 | 65 | 1454 | 1389 | 65 | 623 | 0 | 1389 | MASK_MISMATCH |
| F4-4 | Craig-Bampton |  |  | 1175 |  |  |  |  |  | NOT_EVALUATED_MISSING_ROUTE |
| F4-4 | Guyan | main_guyan_div1 | 93 | 1044 | 951 | 93 | 1033 | 0 | 951 | MASK_MISMATCH |
| F4-5 | Original | main_ori_div2 | 34 | 1247 | 1213 | 34 | 830 | 0 | 1213 | MASK_MISMATCH |
| F4-5 | Craig-Bampton |  |  | 1072 |  |  |  |  |  | NOT_EVALUATED_MISSING_ROUTE |
| F4-5 | Guyan | main_guyan_div2 | 34 | 929 | 895 | 34 | 1148 | 0 | 895 | MASK_MISMATCH |
| F4-4 | Guyan | alt_guyan_div1_stable_full_ps3 | 7 | 1044 | 1037 | 7 | 1033 | 0 | 1037 | MASK_MISMATCH |

## 图对象门

| 图 | 三种主路线齐全 | 三种掩膜全匹配 | 证据等级 | 可建正式成功目录 |
|---|---|---|---|---|
| F4-4 | False | False | PLOTTING_LEVEL_REPRODUCTION | False |
| F4-5 | False | False | PLOTTING_LEVEL_REPRODUCTION | False |

## 证据边界

- 历史图只画历史最终掩膜边界，标为绘图级证据。
- 当前计算图只画现有路线的稳定格点与 `rho=1` 等值线，标为候选失败诊断。
- 第一类 Guyan 备选路线仅作敏感性对照，禁止择优替代主路线。
- 第二类 Original/Guyan 的非身份数值载荷完全相同；这只证明文件身份载荷相同，不证明两种理论等价。
- 第二类候选有孔洞，图中保留实际稳定格点与等值线，不把上包络伪装成填充边界。
- 轴截距定义为从原点开始的连续稳定前缀终点；遇到首个不稳定格即停止，绝不跨孔洞取轴上最后稳定点。
- 历史第二类 Craig–Bampton/Guyan 网格外的 `1..28` 是索引序列，不纳入共同网格稳定判断。
- 结论 C07 的频带和幅值部分不在本步骤范围内；这里只登记临界时滞分量。

## 生成器内部检查

- PASS: 107
- INFO: 8
- FAIL: 0

最终独立验证器另行核对两轮字节重复性、逐点结果、PDF/PNG质量和保护哈希。

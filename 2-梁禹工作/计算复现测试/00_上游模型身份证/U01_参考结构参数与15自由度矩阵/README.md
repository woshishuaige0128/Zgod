# U01：参考结构参数与15自由度矩阵

验收状态：**计算级复现**（限定于当前冻结的真实响应代码路线）。

## 成功范围

- `PDmonicanshu.m` 生成的15×15 `MRrt/CRrt/KRrt` 可从干净 MATLAB 会话重现。
- Python按三层四柱、每层三梁连接关系独立装配，与 MATLAB 的 `M/C/K` 相对误差分别为 `0`、`8.76e-15`、`8.91e-18`。
- 三个矩阵均为15×15、对称、满秩、正定。

## 不包含的声称

本目录**不声称**实际响应代码与硕士论文/小论文材料表一致。代码使用 `E=206 GPa`、`rho=1,491,500 kg/m³`、柱面积1077.4172 mm²；小论文写的是 `E=200 GPa`、`rho=7850 kg/m³`、柱面积3330 mm²。两者关系仍为**待决定**。

## 目录说明

- `input/`：与原件哈希一致的9个输入；`PDmonicanshu_response_route.m` 是响应入口的另名阅读副本。
- `code/`：MATLAB执行入口和Python独立装配器。
- `outputs/`：可直接重跑的完整输出结构。
- `data/`：精选的矩阵身份证。
- `report/`：完整板块16中文证据报告。
- `logs/`：MATLAB和独立Python最终通过日志。

## 重新验证

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'D:\Software\python\python.exe' '.\code\independent_verify_reference.py'
```


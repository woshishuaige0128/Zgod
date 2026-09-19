# 原完整框架等时滞案例

先看 `完整框架等时滞案例_图解汇报.html`，其中包含全部新旧图对应；详细解释见 `CASE_ANALYSIS.md`。这是统一的15坐标虚拟反馈模型，未修改原稿或封存案例。

## 文件导航
- `MODEL_SPECIFICATION.md`：结构、反馈、输入、输出、控制与协调假定。
- `CASE_PROTOCOL.md`：在正式计算前确定的选点/验收规则及Pro意见落实。
- `theory/`：5页32式可编辑TeX和已编译PDF。
- `data/`：独立运行需要的3个冻结MAT文件，来源与哈希见 `source_manifest.json`。
- `code/`：计算、验证和制图入口；导入不执行研究仿真。
- `results/`：原始时程、全部极点、频响、指标、独立验证与来源清单。数千秒慢扫频的完整记录占主要空间，整个结果约0.9GB。
- `figures/`：科研矢量PDF、600dpi PNG、140dpi报告预览和逐曲线来源；保留数、频响、边界、加载撤载、地震、原快扫、慢扫及补充完整保留。

## 科学口径
主模型零附加增益，保留物理刚度/阻尼时滞反馈；两通道相同延迟。划分一Guyan6/CB9，划分二Guyan5/CB8；全部内部模态恢复15坐标完整系统。精度主比较用各划分匹配的同时滞完整模型；最终总偏差另与原被动无时滞RK4框架比较。完整模型原临界前候选点全部保留，三者共同稳定响应点不能冒称完整模型近临界点。

23张新科学图的历史映射按原稿真实TeX图注核对。旧新条件不同，只作主题对照；不将旧新全部差异归于Guyan修正。HTML已做静态检查，科学图和理论PDF实际渲染查看；本地HTML浏览器视觉验收受安全限制，未绕过。

## 独立重跑（在副本或temp内）
将整个文件夹复制到独立目录，至少保留code与data。以下均从本案例目录运行，输出放temp而非覆盖交付结果。Python使用完整路径；依赖numpy、scipy、numba、matplotlib、PyMuPDF、Pillow、mpmath，绘图需TeX Live及Computer Modern。

```powershell
$env:PYTHONIOENCODING='utf-8'
$env:OPENBLAS_NUM_THREADS='1'
& 'D:/Software/python/python.exe' -B -X utf8 code/verify_model.py --out temp/validation
& 'D:/Software/python/python.exe' -B -X utf8 code/verify_theory.py --out temp/validation
& 'D:/Software/python/python.exe' -B -X utf8 code/reproduce_key_results.py --out temp/reproduction
```

`reproduce_key_results.py`重新计算两种划分的地震误差与六个细网格失稳区间端点，对照交付数值。它不复跑数千秒扫频，也不等于独立物理试验。上述入口已在临时code/data副本实际运行。

完整案例重跑顺序：

```powershell
& 'D:/Software/python/python.exe' -B -X utf8 code/case_dynamics.py --out temp/computed --review results/theory_review_authorization.json
& 'D:/Software/python/python.exe' -B -X utf8 code/case_responses.py --out temp/computed --dynamics temp/computed/dynamics.json
& 'D:/Software/python/python.exe' -B -X utf8 code/critical_mechanism.py --out temp/computed
& 'D:/Software/python/python.exe' -B -X utf8 code/verify_cases.py --out temp/computed
& 'D:/Downlad/Matlab/bin/matlab.exe' -batch "addpath('code');VERIFY_CASES('temp/computed');"
& 'D:/Software/python/python.exe' -B -X utf8 code/plot_cases.py --results temp/computed --out temp/figures
& 'D:/Software/python/python.exe' -B -X utf8 code/plot_focus.py --results temp/computed --out temp/figures
```

`VERIFY_MODEL.m`用于独立短记录/矩阵检查：先由verify_model.py导出crosscheck_inputs.mat，再用MATLAB运行，具体参数见函数首行。`build_delivery.py`用于本研究目录下汇报生成，因要读取旧图目录，不属于独立核心求解器。已有单文件HTML可离线直接复制查看，不依赖旧图路径。

## 已知解释边界
- 被动嵌套Ritz频率收敛具有理论依据；有时滞点响应与稳定性改善属于本案例证据，不保证所有指标单调改善。
- 当前稳定边界是首次网格失稳相邻区间；不能扩大成精确连续临界值或整个稳定域包含定理。
- 解析误差是传递算子/有限卷积矩阵表达。实测地震的数值误差仍需输入数据和矩阵运算。
- 高频误差与边界改善一致；尚未完成临界根偏移对各遗漏耦合项的因果贡献分解。
- GPT Pro做文字/代码审读，未执行本地Python或MATLAB。详见随包审查范围记录。

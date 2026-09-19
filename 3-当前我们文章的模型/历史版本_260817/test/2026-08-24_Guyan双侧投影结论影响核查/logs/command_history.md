# 命令与迭代日志

## 2026-08-24 源文件冻结

### 尝试 1：Windows PowerShell 5 直接执行

- 命令：`powershell.exe -NoProfile -ExecutionPolicy Bypass -File "...\\code\\freeze_sources.ps1"`
- 退出码：`1`
- 结果：脚本在解析阶段报错 `The string is missing the terminator: '.`，定位到第 85 行附近。
- 数据状态复核：`source_manifest.csv` 不存在，`input_copies` 中文件数为 0；没有复制、覆盖或修改源文件。
- 原因判断：脚本含中文路径且为 UTF-8 无 BOM，Windows PowerShell 5 按本地代码页解释时发生解析错误。
- 修正原则：脚本逻辑不变，改由原生支持 UTF-8 的 PowerShell 7 (`pwsh`) 执行。

### 尝试 2：PowerShell 7 执行

- 命令：`C:\Users\lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\powershell\pwsh.exe -NoProfile -File "...\\code\\freeze_sources.ps1"`
- 退出码：`0`
- 结果：冻结 23 个源文件；源文件冻结前哈希、复制件哈希、源文件冻结后哈希全部一致。
- 清单：`source_manifest.csv` 共 23 行，23 个唯一源路径、23 个唯一复制路径；`InitialIntegrity=MATCH` 共 23 行。

## 2026-08-24 计算前进程基线

- 检查对象：`MATLAB`、`python`、`pythonw`。
- 结果：`NONE`；计算前没有同名残留进程。

## 2026-08-24 MATLAB 环境预检

- 命令：`D:\Downlad\Matlab\bin\matlab.exe -batch "...version/license/which..."`
- 退出码：`0`
- MATLAB：`R2025b (25.2.0.2998904)`。
- Simulink 许可证：可用；Control System Toolbox 许可证：可用。
- `sim` 与 `ss` 均可解析到本机 MATLAB 安装。

## 2026-08-24 MATLAB 主脚本静态检查

- 命令：`D:\Downlad\Matlab\bin\matlab.exe -batch "issues=checkcode('.../code/run_guyan_impact.m','-id'); ..."`
- 退出码：`0`
- 结果：发现 9 条 `MSNU` 提示，均为可移除的 `#ok<NASGU>` 抑制标记；没有语法错误或不可解析项。
- 审查结论：脚本按“矩阵门槛 → 4/4 历史基线 → 标准路线 4 个既有案例 → 指标”执行；历史基线失败时在标准路线第一次仿真前 `error`。

## 2026-08-24 MATLAB 实际计算（尝试 1）

- 命令：`D:\Downlad\Matlab\bin\matlab.exe -batch "run('.../code/run_guyan_impact.m')"`
- 退出码：`0`
- 开始/完成：`17:23:56` / `17:27:59`。
- 历史基线：四个案例全部通过，最大绝对响应差均为 `4.9737991503207e-14 mm`，时间轴误差为 0；标准路线只在该门槛通过后运行。
- 路线不变性：四个案例的 Original 与 Craig--Bampton 两次运行逐元素差为 0。
- 输出：矩阵、模态、8 份响应 CSV/MAT、168 行指标和汇总 MAT 已写入 `outputs/`；MATLAB 日志使用唯一时间戳文件保留。
- 非致命信息：Simulink 报告未连接的旧 Chirp/Step/Demux 端口，以及为旧版本 SLX 保存 `.r2023b` 备份；这些块已被隔离 From Workspace 输入旁路，历史基线仍逐项通过。

## 2026-08-24 Python 独立复核

### 静态语法检查

- 命令：`D:\Software\python\python.exe -m py_compile ...\code\independent_verify.py`
- 退出码：`0`

### 尝试 1：严格接口读取

- 命令：`D:\Software\python\python.exe ...\code\independent_verify.py`
- 退出码：`1`
- 失败原因：MATLAB 矩阵审计表实际含额外维数列 `T_rows`、`T_columns`，Python 的精确列契约尚未登记这两列，故在数值比较前以 schema mismatch 停止。
- 保留证据：错误摘要复制为 `outputs/python_validation_summary_attempt1_schema_error.json`。
- 修正：只把 `T_rows`、`T_columns` 纳入 Python 契约和整数逐项核对；未改计算公式、数据或任何容差。

### 尝试 2：维数列契约修正后运行

- 退出码：`1`
- 失败原因：新增维数检查误引用不存在的局部变量 `t`；实际独立变换变量名为 `t_independent`。仍在数值门槛前停止。
- 保留证据：`outputs/python_validation_summary_attempt2_name_error.json`。
- 修正：只把两处 `.shape` 引用改为 `t_independent.shape`；公式、数据和容差不变。

### 尝试 3：最终独立复核

- `py_compile` 退出码：`0`。
- 独立复核退出码：`0`。
- 结果：`PASS; records=1582; violations=0`。
- 输出：`outputs/python_validation.csv`、`outputs/python_validation_summary.json`。
- 含义：Python 独立重构矩阵、CB 基底、前两阶频率、三层 NRMSE/峰值、五个 chirp 频段以及 Original/CB 路线不变性，逐项与 MATLAB 导出一致。

## 2026-08-24 审计对比图

- `plot_guyan_comparison.py` 语法检查退出码：`0`；实际绘图退出码：`0`。
- 生成：两类划分 × 两种激励共 4 组，每组为三层、四方法时程；均保存矢量 PDF 与 600 dpi PNG，只位于 `figures/`。
- 目视检查：4 张图的坐标、图例、线型、三层顺序和曲线覆盖均正常；历史 Guyan 与标准 Guyan 的差异可清晰辨认。
- 图形自动验收尝试 1：退出码 `1`，缺少 `pypdf`；改用环境已有 `PyPDF2`，未安装新包。
- 图形自动验收尝试 2：退出码 `1`，旧版 `PyPDF2` 返回间接 `/Resources` 对象；补充 `get_object()` 兼容处理。
- 图形自动验收尝试 3：退出码 `0`，`PASS; figures=4`。4 个 PDF 均单页且无栅格 Image XObject；4 个 PNG 均约 600 dpi、尺寸至少 4000×3500 px。结果保存为 `outputs/figure_validation.csv`。

## 2026-08-24 最终完整性与进程检查

- 命令：PowerShell 7 执行 `code/verify_source_integrity.ps1`。
- 退出码：`0`。
- 源文件：23/23 最终 SHA-256 与冻结值一致；0 缺失、0 不匹配。结果为 `outputs/source_integrity_final.csv`。
- 进程：`MATLAB`、`python`、`pythonw` 均为 `NONE`；没有本任务残留计算进程。


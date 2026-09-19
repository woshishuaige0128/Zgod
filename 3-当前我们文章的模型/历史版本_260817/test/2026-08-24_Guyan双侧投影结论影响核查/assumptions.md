# 计算假设与固定口径

## 权威对象

- 论文：`D:/JZ_PhD/10_论文_Papers/Li/RHTS/260817/manuscript_0823V2_all_figures.tex`
- 历史响应生成器：`figure/第3章_缩聚对试验精度的影响/可复现代码/regenerate_chapter3_data.m`
- 完整模型矩阵：`PDmonicanshu.m` 生成的 `MRrt`、`CRrt`、`KRrt`。

## 两种划分与坐标顺序

完整模型有 15 个自由度。每一类均先按 `[master, slave]` 重排。

- Division I：`master=[1,6,11,4,9,14]`，`slave=[2,3,5,7,8,10,12,13,15]`。
- Division II：`master=[1,11,4,9,14]`，`slave=[6,2,3,5,7,8,10,12,13,15]`。

三层水平位移为原编号 `[1,6,11]`。历史输出映射为 `simout3=第一层`、`simout=第二层`、`simout1=第三层`；本次统一同时保存三层，不混用楼层。

## 两条 Guyan 路线

令

\[
R=-K_{ss}^{-1}K_{sm},\qquad T_G=\begin{bmatrix}I\\R\end{bmatrix}.
\]

历史路线严格复现：

\[
M_h=M_{mm}+M_{ms}R,\quad
C_h=C_{mm}+C_{ms}R,\quad
K_h=K_{mm}+K_{ms}R.
\]

标准路线：

\[
M_p=T_G^{T}MT_G,\quad
C_p=T_G^{T}CT_G,\quad
K_p=T_G^{T}KT_G.
\]

两条路线均沿用原模型的 `T_G^{T}f` 载荷输入和 `P T_G` 三层物理响应恢复，因此唯一主动改变的是 Guyan 的质量、阻尼矩阵构造；刚度应在数值容差内等价。

## 输入与时间离散

- El Centro：原 `EQ.mat` 中 `ElCentroAccel`，沿用 `EQ_intensity=0.40`。
- Chirp：`sin(2*pi*0.1*t + pi*(10-0.1)/40*t^2)`，0.1--10 Hz，40 s。
- 固定步长：`dt=1/1024 s`。
- 仿真时长：40 s。
- Simulink 求解器：历史生成器相同的固定步长 `ode4`。

## 矩阵门槛与相对范数

统一采用 Frobenius 相对差：

\[
\operatorname{rel}(A_h,A_p)=\frac{\lVert A_h-A_p\rVert_F}{\lVert A_p\rVert_F}.
\]

硬门槛：

- `rank(T_G)=n_master`。
- `norm(Ksm+Kss*R,'fro')/max(norm(Ksm,'fro'),eps) < 1e-12`。
- 标准 `M_p,C_p,K_p` 对称残差均小于 `1e-12`。
- 两条刚度路线相对差小于 `1e-12`。
- 标准质量、刚度必须正定；标准阻尼不得出现超出舍入量级的负特征值。

## 结果指标

仅使用当前论文精度结论直接依赖的指标：

- 前两阶自然频率及相对完整模型误差。
- 第一、第二、第三层全时程 NRMSE。
- 第一、第二、第三层绝对峰值及相对完整模型峰值误差。
- chirp 五个既有频段的 NRMSE，频段与论文一致。

不新增相位算法；仅在已有时程可直接稳定判读时做描述，不作为新评价支线。

## 论文影响与停止门槛

- `A`：数值和定性结论均保持。可建议采用标准公式并做最小文字/数字更新。
- `B`：Craig--Bampton 与 Guyan 的方法排序、两类划分的方向和核心 take-home 均保持，但频率、NRMSE、峰值或表图数字需更新。仍可建议标准公式，并逐项列出替换范围。
- `C`：主要工况出现方法排序翻转、Division I/II 方向明显改变，或强结论只能在收缩后成立。
- `D`：核心故事被本次同输入、同楼层计算反驳。
- `E`：因证据不足无法判断。

若总体影响落入 `C` 或 `D`，计算与影响报告完成后立即停止，不编辑论文。报告另外提供 2--3 种文章策略，至少比较：保留标准 Guyan 并按新结果改写；收缩为 Craig--Bampton 与完整模型验证并弱化 Guyan；仅在硕士论文有充分依据时重新定义比较对象。不得把历史错误公式包装成标准 Guyan，也不得为保护原结论调整阈值、代码或指标。

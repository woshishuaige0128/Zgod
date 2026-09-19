# 文献学习：Development of Direct Integration Algorithms for Structural Dynamics Using Discrete Control Theory

**作者：** Cheng Chen; James M. Ricles  
**年份：** 2008  
**期刊/会议：** *Journal of Engineering Mechanics*, 134(8), 676--683  
**DOI：** 10.1061/(ASCE)0733-9399(2008)134:8(676)

## 证据范围与完整性

- 已核对 ASCE 官方题名、作者、卷期、页码和摘要；官方摘要确认本文以离散传递函数与极点映射建立直接积分算法，并提出 CR 显式算法。
- 本轮未直接取得原刊全文，因此不能冒充完成了原文逐页、逐节精读。以下 CR 递推式与矩阵参数定义由公开的一手学位论文、ASCE 会议论文及 WCEE 论文交叉核对；在取得原刊全文后仍应补充原文公式号、精确页码和图表索引。
- 官方来源：[ASCE 论文页面](https://ascelibrary.org/doi/abs/10.1061/%28ASCE%290733-9399%282008%29134%3A8%28676%29)。矩阵形式交叉来源：[Lehigh 学位论文](https://preserve.lehigh.edu/_flysystem/fedora/2023-11/preservebp-10369004.pdf)；单自由度形式交叉来源：[WCEE 2012 论文](https://www.iitk.ac.in/nicee/wcee/article/WCEE2012_0215.pdf)。

## 图表公式索引

### 公式

1. CR 速度递推：
   \[
   \dot{\mathbf u}_{i+1}=\dot{\mathbf u}_{i}
   +\Delta t\,\boldsymbol{\alpha}_{1}\ddot{\mathbf u}_{i}.
   \]
2. CR 位移递推：
   \[
   \mathbf u_{i+1}=\mathbf u_i+\Delta t\,\dot{\mathbf u}_{i}
   +\Delta t^2\boldsymbol{\alpha}_{2}\ddot{\mathbf u}_{i}.
   \]
3. 本文稳定性推导使用的特定 CR 参数：
   \[
   \boldsymbol{\alpha}_{1}=\boldsymbol{\alpha}_{2}=\boldsymbol{\alpha}
   =\left(4\mathbf M+2\Delta t\mathbf C+\Delta t^2\mathbf K\right)^{-1}(4\mathbf M).
   \]
4. 在零初始条件的特征方程推导下，对递推式作单边或双边 Z 变换均可得到：
   \[
   \dot{\mathbf u}(z)=\frac{z-1}{z\Delta t}\mathbf u(z),\qquad
   \ddot{\mathbf u}(z)=\boldsymbol{\alpha}^{-1}
   \frac{(z-1)^2}{z\Delta t^2}\mathbf u(z).
   \]
5. 代回动力平衡时，惯性项的矩阵次序应为：
   \[
   \frac{(z-1)^2}{z\Delta t^2}\mathbf M\boldsymbol{\alpha}^{-1}\mathbf u(z),
   \]
   不能在无交换性证明时写成
   \(\boldsymbol{\alpha}^{-1}\mathbf M\mathbf u(z)\)。

### 图表

- 原刊全文尚未取得，本轮不填写未经核验的图号、表号和原文公式号。

## Research Outline（按当前可核实材料）

### 1. 研究问题

- 结构动力学直接积分算法既要稳定，也要准确；作者用离散控制理论的传递函数与极点映射来系统构造积分算法。

### 2. 方法

- 将连续结构动力系统映射到离散域，以离散传递函数考察积分算法性质。
- 利用控制理论的极点映射规则提出 CR 显式积分算法。
- 对本文稿件相关的特例，采用
  \(\boldsymbol{\alpha}_1=\boldsymbol{\alpha}_2=\boldsymbol{\alpha}\)。

### 3. 结果与结论

- ASCE 官方摘要将 CR 算法描述为显式算法，并报告其具有无条件稳定性和与 Newmark 常加速度方法相当的精度。
- 对当前稿件而言，最关键的不是上述性能宣传，而是两个递推式及
  \(\boldsymbol{\alpha}_1=\boldsymbol{\alpha}_2\) 的矩阵身份；它们决定 Z 域公式的形式。

### 4. 尚待原刊全文补齐

- 原文章节标题与逐节方法/结果。
- 原文公式号、公式所在精确页码、图表号与图表结论。
- 数值算例、误差定义和稳定性证明的逐项摘录。

## 核心贡献

1. 用离散控制理论统一分析结构动力学直接积分算法。
2. 把离散传递函数和极点映射用于积分算法设计。
3. 提出 CR 显式直接积分算法。
4. 给出兼顾稳定性与精度的算法性质，并与常用 Newmark 方法建立性能参照。

## 可引用观点

| 可引用观点（转述） | 来源位置 | 可用于本稿 |
|---|---|---|
| 直接积分算法的可靠性需要同时考虑稳定性和精度。 | ASCE 官方摘要；原刊 pp. 676--683，精确页待全文核验 | 稳定性章节的 CR 算法引入 |
| CR 算法由离散传递函数和控制理论极点映射构造。 | ASCE 官方摘要；原刊 pp. 676--683，精确页待全文核验 | 解释算法来源，避免误称后向差分 |
| 对当前采用的 CR 特例，\(\boldsymbol{\alpha}_1=\boldsymbol{\alpha}_2\) 为矩阵参数。 | Lehigh 学位论文与公开会议论文交叉核对；非原刊精确页证据 | 支撑式 (3.5) 的矩阵写法与推导 |

## 可对比的方法

- Newmark 常加速度法：可作为精度与稳定性比较基准。
- 一般后向差分：当前 Z 域速度关系在外形上相似，但这里是由 CR 两个递推式以及
  \(\boldsymbol{\alpha}_1=\boldsymbol{\alpha}_2\) 推导得到，不能仅凭外形认定为后向差分误用。

## 本文局限性与当前使用边界

1. CR 积分公式正确，不等于整套实时混合试验稳定性模型自动正确；控制力、执行器时滞和 LQR 信号路径仍须独立核对。
2. Z 变换写法用于特征方程时应注明零初始条件；非零初始项影响响应表达的分子/外载项，而不改变本次特征分母的构造。
3. \(\boldsymbol{\alpha}\) 是矩阵。稿件不能继续用标量式的 \(1/\alpha\)，也必须保持
   \(\mathbf M\boldsymbol{\alpha}^{-1}\) 的乘法次序。
4. 原刊全文未直接取得，因此当前笔记不能作为原文逐页精读的替代品。

## 对当前稿件的直接结论

- 式 (3.5) 的函数形式可由 CR 递推严格推出，不是因为“看起来像后向差分”就构成错误。
- 稿件必须补两个 CR 递推式、矩阵
  \(\boldsymbol{\alpha}\) 的显式定义、零初始条件，并把式 (3.8) 的惯性项写成
  \(\mathbf M_{\rm re}\boldsymbol{\alpha}^{-1}\)。
- 仅针对 CR 离散公式的质疑，无需重算稳定域；但这不能推出“全部稳定性结果无需重算”，因为 LQR 是否经过执行器时滞是另一项独立模型冲突。

## BibTeX

```bibtex
@article{ChenRicles2008,
  author  = {Chen, Cheng and Ricles, James M.},
  title   = {Development of Direct Integration Algorithms for Structural Dynamics Using Discrete Control Theory},
  journal = {Journal of Engineering Mechanics},
  year    = {2008},
  volume  = {134},
  number  = {8},
  pages   = {676--683},
  doi     = {10.1061/(ASCE)0733-9399(2008)134:8(676)}
}
```

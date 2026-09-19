"""生成“第二、三章推导—案例—代码闭环审计”自包含求助简报。"""

from __future__ import annotations

import hashlib
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

from audit_case_metrics import response_metrics, stability_summary


WORKSPACE = Path(r"D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master")
RHTS_ROOT = WORKSPACE.parent
INNER = WORKSPACE / "liangyustability-master"
CHAPTER3 = WORKSPACE / "figure" / "第3章_缩聚对试验精度的影响"
CHAPTER4 = WORKSPACE / "figure" / "第4章_缩聚对试验稳定性的影响"
OUTPUT = WORKSPACE / "need-help" / "2026-08-18_推导案例闭环.md"

ACTIVE_TEX = RHTS_ROOT / "260817" / "manuscript.tex"
BASELINE_TEX = RHTS_ROOT / "manuscript" / "260813" / "manuscript_completed_en.tex"


def read_text(path: Path) -> str:
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise UnicodeDecodeError("unknown", b"", 0, 1, f"无法解码 {path}")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def relative_path(path: Path) -> str:
    try:
        return path.relative_to(WORKSPACE).as_posix()
    except ValueError:
        return path.as_posix()


def fenced(text: str, language: str = "text") -> str:
    return f"```{language}\n{text.rstrip()}\n```\n"


def mlx_markdown(path: Path) -> str:
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    with zipfile.ZipFile(path) as archive:
        document = archive.read("matlab/document.xml")
    root = ET.fromstring(document)
    output: list[str] = []
    code_cell = 0
    for paragraph in root.findall(".//w:body/w:p", namespace):
        style_node = paragraph.find("./w:pPr/w:pStyle", namespace)
        style = ""
        if style_node is not None:
            style = style_node.attrib.get(
                "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}val", ""
            )
        text = "".join(node.text or "" for node in paragraph.findall(".//w:t", namespace)).strip()
        if not text:
            continue
        if style == "code":
            code_cell += 1
            output.append(f"**代码单元 C{code_cell}**\n\n{fenced(text, 'matlab')}")
        else:
            output.append(f"> Live Script 文本：{text}\n")
    return "\n".join(output)


def source_appendix(path: Path, language: str, title: str | None = None) -> str:
    content = read_text(path)
    heading = title or path.name
    return (
        f"### {heading}\n\n"
        f"- 路径：`{path.as_posix()}`\n"
        f"- SHA-256：`{sha256(path)}`\n"
        f"- 字节数：`{path.stat().st_size}`；文本行数：`{len(content.splitlines())}`\n\n"
        + fenced(content, language)
    )


def mlx_appendix(path: Path, title: str | None = None) -> str:
    return (
        f"### {title or path.name}\n\n"
        f"- 路径：`{path.as_posix()}`\n"
        f"- SHA-256：`{sha256(path)}`\n"
        f"- 字节数：`{path.stat().st_size}`\n"
        f"- 转存规则：按 `matlab/document.xml` 中原始段落顺序展开；代码单元完整保留，"
        f"`C编号` 仅是本简报为便于审阅添加的定位标签。\n\n"
        + mlx_markdown(path)
        + "\n"
    )


def format_values(values: list[float]) -> str:
    return ", ".join(f"{value:.6f}" for value in values)


def build_response_tables() -> str:
    earthquake = [
        ("第一类物理子结构划分", response_metrics("第一类划分_ElCentro地震响应.csv", False)),
        ("第二类物理子结构划分", response_metrics("第二类划分_ElCentro地震响应.csv", False)),
    ]
    chirp = [
        ("第一类物理子结构划分", response_metrics("第一类划分_Chirp响应.csv", True)),
        ("第二类物理子结构划分", response_metrics("第二类划分_Chirp响应.csv", True)),
    ]
    lines = [
        "#### El Centro 三层响应的独立 NRMSE 重算（%）",
        "",
        "公式与稿件一致：`100*sqrt(mean((x_full-x_red)^2))/(max(x_full)-min(x_full))`。",
        "",
        "| 物理子结构划分 | 楼层 | Guyan | Craig–Bampton |",
        "|---|---:|---:|---:|",
    ]
    for name, result in earthquake:
        for floor, values in result["floors"].items():
            metric = values["overall_nrmse_percent"]
            lines.append(
                f"| {name} | {floor} | {metric['Guyan']:.6f} | {metric['Craig-Bampton']:.6f} |"
            )
    lines.extend(
        [
            "",
            "现稿表中第一类的 `0.7578/0.0058` 对应**二层**，第二类的 "
            "`10.9355/0.0272` 对应**三层**。表题未声明楼层，且两类划分使用了不同楼层。",
            "",
            "#### Chirp 五频段 NRMSE 的独立重算（%）",
            "",
            "时间段严格复用 `RMSE.m`：0–7.27、7.27–13.73、13.73–21.4、"
            "21.4–32.31、32.31–40 s；每段 RMSE 均除以全时程参考响应幅值范围。",
            "",
            "| 物理子结构划分 | 楼层 | 方法 | 0.1–1.9 Hz | 1.9–3.5 Hz | 3.5–5.4 Hz | 5.4–8.1 Hz | 8.1–10 Hz |",
            "|---|---:|---|---:|---:|---:|---:|---:|",
        ]
    )
    for name, result in chirp:
        for floor, values in result["floors"].items():
            bands = values["band_nrmse_percent"]
            for method in ("Guyan", "Craig-Bampton"):
                cells = " | ".join(f"{value:.6f}" for value in bands[method])
                lines.append(f"| {name} | {floor} | {method} | {cells} |")
    lines.extend(
        [
            "",
            "现稿第一类五频段行可追到二层（仅存在末位舍入差）；第二类稿件中的 "
            "Guyan `[2.9956,19.0594,14.8760,7.4984,2.8127]` 与 Craig–Bampton "
            "`[0.0037,0.0560,0.0296,0.0139,0.0070]` 不对应当前任一楼层。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_stability_table() -> str:
    summaries = [stability_summary("lqr_2.mat"), stability_summary("lqr_3.mat")]
    labels = {"stab_o": "原结构", "stab_C": "Craig–Bampton", "stab_g": "Guyan"}
    lines = [
        "| 数据文件 | 变量/方法 | 原数组尺寸 | 全数组不同数值个数 | 共同 31×67 网格稳定点数 | 数值性质 |",
        "|---|---|---:|---:|---:|---|",
    ]
    for summary in summaries:
        for variable, values in summary["variables"].items():
            shape = "×".join(str(value) for value in values["shape"])
            unique = values["unique_values_if_short"]
            nature = "0/0.999 稳定掩膜" if unique == [0.0, 0.999] else "含0/0.999及1…28异常索引序列"
            lines.append(
                f"| {summary['file']} | {variable}/{labels[variable]} | {shape} | "
                f"{values['unique_count']} | {values['stable_points_on_common_31x67_grid']} | {nature} |"
            )
    return "\n".join(lines) + "\n"


def source_inventory(paths: list[Path]) -> str:
    lines = [
        "| 文件 | 字节数 | SHA-256 |",
        "|---|---:|---|",
    ]
    for path in paths:
        lines.append(f"| `{relative_path(path)}` | {path.stat().st_size} | `{sha256(path)}` |")
    return "\n".join(lines) + "\n"


def main() -> None:
    parts: list[str] = []
    parts.append(
        r"""# 请审查第二、三章推导与案例代码是否形成可复算闭环

> **致外部 AI**：这是一份独立的求助简报，所有需要的项目上下文、公式、代码、数值证据和来源边界均已包含。请按以下方式回答：
> 1. **身份**：请以“结构动力学、实时混合试验、模型降阶与离散时滞稳定性方向的资深研究者，同时以挑剔的期刊审稿人”的视角作答。
> 2. **先通读全文再答**，重点是第 7 段“明确的求助点”；请按编号逐条回应，不要把不同问题混在一起。
> 3. **如果信息仍有缺口**：先按最合理的假设作答，显式列出所用假设，并在回答末尾集中给出“需要补充的信息清单”。不要因缺信息拒答，也不要不声明便自行脑补。
> 4. **不要编造**：任何文献建议必须给出可核验的作者、年份和标题；不确定的标“需核实”。每个关键判断应给出数学或代码依据，回答会被独立核验后才采纳。
> 5. **不要迎合**：第 6 段的初步判断只是待审意见。如果判断有误，请直接反驳，并说明最强的反对理由及更合理的替代方案。

---

## 1. 大背景与最终目标

- **领域/项目**：这是一个三层三跨钢框架多自由度实时混合试验（RTHS）研究。论文比较 Guyan 静力凝聚和 Craig–Bampton 动力子结构法对模态、El Centro 地震响应、0.1–10 Hz 线性扫频响应以及双作动器时滞稳定域的影响。
- **最终目标**：使论文第二章的结构建模与缩聚理论、第三章的离散多时滞稳定性推导、现有 MATLAB/Simulink 案例和结果表格逐项闭合；不新增结构算例，只在必要时重算现有两种物理子结构划分。
- **上游背景**：当前修订理论稿 `D:/JZ_PhD/10_论文_Papers/Li/RHTS/260817/manuscript.tex` 已写出完整结构、数值/物理子结构、界面条件、Guyan 和 Craig–Bampton 推导，但只到第二章结束。此前计划的独立第三章标题为“Discrete-time delay-dependent stability formulation”，包含“3.1 Reduced multiple-delay representation”和“3.2 Closed-loop characteristic equation and pole criterion”，尚未落盘。
- **下游用途**：确认闭环后才合并英文完整稿、重写案例结果和结论；若公式与代码不一致，则须先确定权威算法，再重跑既有数据，不能用旧表值反向修改理论。
- **已有成果**：第三章图形资产已从干净 MATLAB 会话真实重建五组 Simulink 工况；第四章稳定域可以从历史 MAT 稳定掩膜重画，但没有从模型矩阵开始完整复算极点网格。这两种状态在本简报中分别称为“计算级复现”和“绘图级复现”，不可混称。

### 1.1 本次审计采用的权威文件层级

1. **当前第二章理论**：`260817/manuscript.tex`（修订稿，当前到第二章结束）。
2. **既有案例与表格基线**：`manuscript/260813/manuscript_completed_en.tex`（较早英文完整稿，其第二章为空白占位，稳定性位于后续 benchmark 小节）。
3. **计算事实**：MATLAB/Simulink 源代码、Live Script 内嵌代码、已验收 MAT/CSV 及 SHA-256。
4. **解释性证据**：硕士论文精读笔记与图片复现项目的来源/验证记录。

### 1.2 一句话审计结论

**案例用到了第二章的大部分缩聚思想和第三章的“极点在单位圆内”判据，但没有形成完整闭环。Craig–Bampton 的矩阵投影、载荷投影和位移恢复基本一致；Guyan 的质量/阻尼矩阵与第二章合同投影冲突；独立第三章不存在，现有代码采用的 `z` 域动态刚度特征方程也没有写入正文；稳定域仅可重画、不能从头复算；能量公式、代码和表值不一致。**

## 2. 术语/缩写表

| 术语/符号 | 本项目中的含义 |
|---|---|
| RTHS | 实时混合试验；数值子结构和物理子结构在实时步内交换界面位移与恢复力。 |
| Case I/第一类物理子结构划分 | 当前响应再生代码的主自由度为 `[1,6,11,4,9,14]`，从自由度为 `[2,3,5,7,8,10,12,13,15]`。物理上保留第一、第二层水平坐标以及相关转角。 |
| Case II/第二类物理子结构划分 | 主自由度为 `[1,11,4,9,14]`，从自由度为 `[2,3,5,6,7,8,10,12,13,15]`；关键中间层水平坐标被凝聚。 |
| `T` | Guyan 变换矩阵，代码为 `[I; -Kss\Ksm]`。 |
| `Tcb` | Craig–Bampton 变换矩阵，由约束模态和固定界面模态组成。 |
| `r=3`/`N_r=3` | 每种 Craig–Bampton 模型硬编码保留的前三阶固定界面模态数；当前没有阶数敏感性依据。 |
| `MRrt,CRrt,KRrt` | 15 自由度完整参考模型的质量、阻尼、刚度矩阵。 |
| `MRren,CRren,KRren` | 历史 Guyan 代码生成的降阶矩阵，质量/阻尼使用单侧块消元。 |
| `MRcb,CRcb,KRcb` | Craig–Bampton 降阶矩阵，使用双侧合同投影。 |
| `d_1,d_2` | 两个作动器通道的整数采样延迟；物理时滞为 `tau_i=d_i*Delta t`。 |
| `H(z)` | 延迟矩阵。不同历史脚本都在前两个对角元放置 `z^{-d_1}` 和 `z^{-d_2}`，但其余对角元取 0 或 1、以及左乘或右乘延迟动力项并不统一。 |
| `G(z)` | 现有稳定性脚本中的离散动态刚度/特征矩阵。 |
| `mu(d_1,d_2)` | `det G(z)=0` 全部根的最大模；理论稳定条件应为 `mu<1`。 |
| `stab_o/stab_C/stab_g` | 历史最终 MAT 中原结构、Craig–Bampton、Guyan 的稳定掩膜变量；不是原始谱半径网格。 |
| NRMSE | 均方根误差除以完整模型响应全时程峰峰值，再乘 100%。 |
| MAC | 模态保证准则。当前旧脚本只比较保留坐标且存在顺序/维数问题。 |
| `Delta E` | 稿件所称“模态能量重分配指标”，并非运行中机械能。现有多个脚本对它有互不一致的实现。 |

## 3. 当前阶段

- **整体工作流位置**：论文理论—案例闭环审计，位于“合并修订第二章/撰写第三章”之前。
- **本阶段交付**：回答“案例是否实际使用第二、三章推导、遗漏了什么”，并把全部相关公式、代码、数据摘要、数值复核和待决问题装入一份可交给陌生专家的 Markdown。
- **已完成进度**：
  1. 逐式比对当前第二章、旧完整稿、响应再生入口和稳定/能量 Live Script；
  2. 只读解析 SLX/MLX；
  3. 实际运行 MATLAB 对比两种 Guyan 矩阵算法；
  4. 实际运行 Python 从已验收 CSV/MAT 重算三层 NRMSE、Chirp 五频段 NRMSE和稳定掩膜取值；
  5. 核对历史稳定域统计、能量脚本保存输出及源码哈希。
- **未做事项**：未改论文、未改原 MATLAB/Simulink、未生成新案例、未替换任何旧表值，也未把本简报发送给外部模型。

## 4. 当前做法（详细）

### 4.1 第二章理论起点

完整系统运动方程写为

\[
\mathbf M\ddot{\mathbf u}+\mathbf C\dot{\mathbf u}+\mathbf K\mathbf u=\mathbf f.
\]

若 `u≈Tq`，当前修订稿使用 Galerkin/合同投影：

\[
\mathbf M_r=\mathbf T^{\mathsf T}\mathbf M\mathbf T,\quad
\mathbf C_r=\mathbf T^{\mathsf T}\mathbf C\mathbf T,\quad
\mathbf K_r=\mathbf T^{\mathsf T}\mathbf K\mathbf T,
\]

\[
\mathbf f_r=\mathbf T^{\mathsf T}\mathbf f.
\]

Guyan 在主/从自由度分块后假定从自由度静力平衡：

\[
\mathbf u_s=-\mathbf K_{ss}^{-1}\mathbf K_{sm}\mathbf u_m,
\qquad
\mathbf T_G=
\begin{bmatrix}
\mathbf I\\-\mathbf K_{ss}^{-1}\mathbf K_{sm}
\end{bmatrix}.
\]

Craig–Bampton 变换按代码采用

\[
\mathbf T_{CB}=
\begin{bmatrix}
\mathbf I & \mathbf 0\\
-\mathbf K_{ss}^{-1}\mathbf K_{sm} & \boldsymbol\Phi_s
\end{bmatrix},
\]

其中 `Phi_s` 是固定主自由度后的内部模态，本项目硬编码取 `r=3`。

### 4.2 案例真实调用链

`regenerate_chapter3_data.m` 从同一 15 自由度完整模型构造三套状态空间：

\[
\dot{\mathbf x}=\begin{bmatrix}\mathbf0&\mathbf I\\-\mathbf M^{-1}\mathbf K&-\mathbf M^{-1}\mathbf C\end{bmatrix}\mathbf x+
\begin{bmatrix}\mathbf0\\\mathbf M^{-1}\end{bmatrix}\mathbf f.
\]

- 完整模型：直接使用 `MRrt,CRrt,KRrt`。
- Guyan：构造 `T`，但历史代码对 `M,C,K` 使用单侧块消元；三层位移用 `P*T` 恢复，载荷在 SLX 中用 `T'*Mf` 投影。
- Craig–Bampton：固定界面特征值排序后取前三阶，三矩阵均用 `Tcb'*(.)*Tcb`，三层位移用 `P*Tcb` 恢复，载荷用 `Tcb'*Mf` 投影。
- 两类物理子结构划分均运行 El Centro×0.40 和 0.1–10 Hz/40 s 线性 Chirp；每组 40961 点，`Delta t=1/1024 s`。

这些时程案例实际是“同一完整 15 自由度模型的三种表示”的比较。`New_Ps2.m/New_Ns2.m` 所构造的物理/数值子结构矩阵没有进入最终再生入口，因此现有时程不能单独证明第二章界面力平衡与物理—数值子结构耦合方程。

### 4.3 计划第三章与现有稳定性代码

旧稿写的是通用递推

\[
\mathbf x_{k+1}=\mathbf A_0\mathbf x_k+\mathbf A_1\mathbf x_{k-d_1}+\mathbf A_2\mathbf x_{k-d_2}+\mathbf B\mathbf r_k,
\]

再构造增广矩阵 `Acal(d1,d2)` 并要求 `rho(Acal)<1`。工程内没有找到 `A0/A1/A2/Acal` 的构造或扫描代码。

实际 Live Script 走的是 `z` 域动态刚度路线。按代码逐项抄写（尚未证明推导正确）：

\[
\boldsymbol\alpha=(4\mathbf M+2\Delta t\mathbf C+\Delta t^2\mathbf K)^{-1}(4\mathbf M),
\]

不同历史脚本实际存在两种互相冲突的定义：

\[
\mathbf H_0(z)=\operatorname{diag}(z^{-d_1},z^{-d_2},0,\ldots,0),\qquad
\mathbf H_I(z)=\operatorname{diag}(z^{-d_1},z^{-d_2},1,\ldots,1).
\]

稳定域候选 `*_LQR3.mlx` 多处从 `zeros` 构造 `H_0` 并左乘延迟动力项；能量目录的部分稳定脚本从 `eye` 构造 `H_I` 并右乘延迟动力项。这不是记号差异，需要先确定通道分解和矩阵乘法方向。以下先按前一种代码逐项抄写；不含 LQR 时为

\[
\mathbf G(z)=
\frac{(z-1)^2}{z\Delta t^2}\mathbf M\boldsymbol\alpha^{-1}
+\frac{z-1}{z\Delta t}\mathbf C_1+\mathbf K_1
+\mathbf H(z)\left(\frac{z-1}{z\Delta t}\mathbf C_2+\mathbf K_2\right).
\]

部分 `LQR3` 脚本再加 `S^T DeltaG(z) S`，其中

\[
\Delta\mathbf G(z)=\frac{z-1}{z\Delta t}\Delta\mathbf C+\Delta\mathbf K.
\]

代码随后求

\[
\det\mathbf G(z;d_1,d_2)=0,\qquad
\mu(d_1,d_2)=\max_p|z_p|,
\]

并以 `mu<1` 判断稳定。这一根模判据与单位圆概念一致，但尚无代码证明它与旧稿增广矩阵谱半径完全等价；也没有可靠脚本生成最终 31×67 稳定域。

### 4.4 LQR 当前三套冲突参数

| 来源 | 算法 | Q | R |
|---|---|---|---|
| 旧英文稿 | 连续 CARE | `diag(1e6,1e6,1e4,1e4)` | `diag(1e-2,1e-2)` |
| 稳定域 `*_LQR3.mlx` | `c2d` 后 `dlqr` | `diag([1e6,1,1e5,1])` | `diag([1e-1,1e-2])` |
| 能量目录 `luxvjie_guyan_LQR2/3.mlx` | `dlqr` | `diag([4e8,1e4,1e2,1e1])` | `diag([3e-3,1e-2])` |

因此目前无法把旧稿连续 CARE、离散控制器代码和最终稳定域视为同一控制器链。

### 4.5 稿件能量指标与脚本做法

稿件定义

\[
\Gamma_i=\frac{\boldsymbol\phi_i^{\mathsf T}\mathbf M\mathbf r}
{\boldsymbol\phi_i^{\mathsf T}\mathbf M\boldsymbol\phi_i},\qquad
p_i=\frac{\Gamma_i^2}{\sum_k\Gamma_k^2},
\]

\[
E_{j,i}=\frac{m_j\phi_{j,i}^2}{\sum_\ell m_\ell\phi_{\ell,i}^2},\qquad
E_j^{\mathrm{total}}=\sum_i p_iE_{j,i},
\]

\[
\Delta E=\sum_{k=1}^{q}
\frac{E_{\mathrm{red}}^{\mathrm{total}}(k)-E_{\mathrm{full}}^{\mathrm{total}}(d_k)}
{E_{\mathrm{full}}^{\mathrm{total}}(d_k)}.
\]

可追溯 Live Script 主要计算“选定坐标能量总和之差/某个总和”，不是上式的逐坐标相对变化之和。不同副本又对模态内归一化、激励向量 `r` 和分母采用不同写法。

### 4.6 硬约束

1. 不新增结构案例；可以重跑当前两类物理子结构划分。
2. 不为保留旧表值而篡改理论或降低验收标准。
3. 原始 MATLAB/Simulink、历史 MAT/CSV、当前 TeX 在决策前保持只读；修复应在明确的新入口中完成。
4. 所有结果必须从干净 MATLAB 会话可运行，保存公式参数、原始指标网格、输出表和 SHA-256。
5. 含时滞理论必须忠实对应最终代码：选择增广状态路线或动态刚度路线之一；若两者并存，需要给出等价证明与数值对照。

## 5. 遇到的问题

### 5.1 公式—案例—代码映射总表

| 理论/指标 | 案例是否使用 | 一致性判定 | 证据/遗漏 |
|---|---|---|---|
| 完整结构运动方程 | 是 | 基本一致 | 15 自由度 `M,C,K` 用于模态、地震、Chirp。 |
| 数值/物理子结构方程与界面条件 | 仅作为背景 | 未直接验证 | 最终响应入口未调用 `New_Ps2/New_Ns2`；没有界面兼容/力平衡残差。 |
| 主/从坐标分块 | 是 | 代码明确、正文映射缺失 | 代码使用上述 15 活动自由度集合；旧稿却写 29 自由度集合 `{21,27}` 与 `{18,19,29}`，两者无映射。 |
| Guyan 静力约束与 `T` | 是 | 坐标关系一致 | `T=[I;-Kss\Ksm]`。 |
| Guyan `Mr,Cr,Kr=T'*(.)*T` | 是，但实现冲突 | **阻断级** | `Kr` 等价；`Mr/Cr` 为单侧消元，不是合同投影。 |
| Craig–Bampton 固定界面/约束模态 | 是 | 基本一致 | 外层再生已排序后取 `r=3`；未给 `r=3` 收敛依据。 |
| Craig–Bampton 合同投影 | 是 | 一致 | `Tcb'*(M,C,K)*Tcb`。 |
| 载荷投影与三层响应恢复 | 是 | 仅三层位移闭合 | SLX 用 `T'*Mf/Tcb'*Mf`，输出用 `P*T/P*Tcb`；未验全部内部位移、转角、内力。 |
| 频率误差 | 有旧表值 | 旧表继承有偏 Guyan 矩阵 | 修正合同投影后必须重算。 |
| MAC | 有脚本 | **当前脚本不可验收** | 自由度顺序错、第二类维数错、CB 维数错，且只比边界坐标。 |
| El Centro NRMSE | 是 | 数值可复算，表格标注缺失 | 第一类取二层、第二类取三层。 |
| Chirp 分频段 NRMSE | 是 | 第一类可追溯，第二类旧表不可复算 | 当前任一楼层均不匹配第二类旧表。 |
| 多时滞递推/增广矩阵 | 否 | **遗漏** | 只在旧稿出现，代码无 `A0/A1/A2/Acal`。 |
| `z` 域特征方程与最大根模 | 是 | 代码存在、正文缺失 | 计划第三章 3.2 的核心公式未写；清分母、伪根和等价性未验证。 |
| LQR | 部分脚本使用 | **阻断级冲突** | 连续/离散算法及 Q/R 三套不一致。 |
| 最终稳定域 | 仅可重画 | **不是从头复算** | 最终 MAT 是稳定掩膜，候选脚本不能生成它。 |
| 能量指标 | 旧脚本有计算 | **公式、代码、数值三者冲突** | 仅第二类表值可追到有公式错误的脚本；第一类无代码输出。 |
| “Delta E>0.3 表示明显收缩” | 否 | **无验证** | 仅四个不统一值，无联合代码、统计或敏感性分析。 |

#### 5.1.1 当前第二章每个公式标签的落地状态

| 当前第二章标签 | 案例落地状态 | 需要补充或修正 |
|---|---|---|
| `eq:full-order-eom` | 直接用于完整模型模态、地震和 Chirp | 结果节应显式回引；地震等效力符号需说明。 |
| `eq:substructure-eom` | 作为建模背景 | 最终响应入口未装配真实数值/物理子结构闭环。 |
| `eq:numerical-eom` | 未单独验证 | 若保留“RTHS耦合验证”措辞，应给数值子结构装配证据。 |
| `eq:physical-eom` | 未单独验证 | `New_Ps2.m` 未进入最终响应再生入口。 |
| `eq:interface-conditions` | 未直接使用为验收量 | 缺位移兼容与界面力平衡残差。 |
| `eq:common-coordinate-partition` | 实际用于主/从自由度分块 | 缺 29 自由度到 15 活动自由度映射和两类划分正式定义。 |
| `eq:partitioned-local-eom` | 直接用于 Guyan/CB 分块 | 代码可对应，正文结果未说明矩阵顺序。 |
| `eq:general-reduction` | 直接使用 | `T/Tcb` 均构造。 |
| `eq:general-projection` | CB 一致；Guyan 的 M/C 不一致 | Guyan 冲突是阻断项。 |
| `eq:guyan-static-equilibrium` | 直接使用 | 只支持刚度静力关系。 |
| `eq:guyan-coordinate-relation` | 直接使用 | `-Kss\Ksm`。 |
| `eq:guyan-transformation` | 直接用于载荷投影和三层位移恢复 | 未验全部内部坐标与内力。 |
| `eq:guyan-reduced-eom` | 历史代码意图使用，但 M/C 不符合 | 当前 Guyan 案例不能验证该式。 |
| `eq:cb-coordinate-order` | 直接使用 | 需报告 `r=3` 及坐标顺序。 |
| `eq:cb-partitioned-eom` | 直接使用 | 与特征问题代码对应。 |
| `eq:fixed-interface-modes` | 直接使用 | 外层已排序，需补残差/正交与截断依据。 |
| `eq:constraint-modes` | 直接使用 | `-Kss\Ksm`。 |
| `eq:cb-transformation` | 直接使用 | 两类划分均用于响应。 |
| `eq:cb-reduced-coordinate` | 直接使用 | 需把边界坐标与固定界面模态坐标映射写入案例。 |
| `eq:cb-reduced-matrices` | 直接且一致 | `Tcb'*(M,C,K)*Tcb`。 |
| `eq:cb-reduced-eom` | 直接用于状态空间与响应 | 结果节应回引。 |
| `eq:cb-internal-recovery` | 用于三层物理位移恢复 | 未验全部内部响应和恢复残差。 |

### 5.2 阻断问题一：Guyan 质量/阻尼矩阵不是第二章合同投影

现有代码：

```matlab
T = [eye(nm); -Kss\Ksm];
Mg = Mmm - Mms*(Kss\Ksm);
Cg = Cmm - Cms*(Kss\Ksm);
Kg = Kmm - Kms*(Kss\Ksm);
```

第二章要求：

```matlab
Mg = T' * Mo * T;
Cg = T' * Co * T;
Kg = T' * Ko * T;
```

同一参数的实际 MATLAB 对照输出为：

```text
FULL f1=2.70742574 f2=9.32840869 Hz
CASE_I relM=0.0997789388628 relC=0.00951999751215 relK=1.07196787865e-16 legacy=[2.72497702 9.83319103] projected=[2.70750294 9.36641472] Hz
CASE_II relM=0.373012702533 relC=0.0841596393017 relK=2.49966253798e-16 legacy=[3.22291949 12.18051937] projected=[2.72040833 10.03265330] Hz
```

这不是舍入误差：第二类质量矩阵相对差 37.30%，前两阶频率明显改变。由于完整质量矩阵近似对角，`Mms=0`，历史 `Mg` 退化为 `Mmm`，漏掉了 `Psi^T Mss Psi` 等从自由度惯性贡献。旧稿 Guyan 频率误差和所有 Guyan 时程都继承这套历史矩阵，不能称为当前第二章合同投影的验证。

### 5.3 阻断问题二：响应表格的坐标来源混用或不可追溯

"""
    )
    parts.append(build_response_tables())
    parts.append(
        r"""
### 5.4 阻断问题三：稳定域文件不是谱半径网格

"""
    )
    parts.append(build_stability_table())
    parts.append(
        r"""

外层 `huitu_2.m` 和当前图片复现代码只用 `0<value<1` 识别稳定点、裁剪共同 31×67 网格并提边界。工程内没有找到把原始根模统一改写成 `0.999` 的生成代码；六个候选 Live Script 的循环范围、保存语句和文件身份也不足以生成最终数组。因此论文不能写“本次从谱半径扫描获得稳定域”，只能写“基于历史最终稳定掩膜重绘”，直到重新计算通过。

现有已验收 CSV 给出的两个轴向最大时滞为：

| 物理子结构划分 | 方法 | 方向1最大时滞/ms | 方向2最大时滞/ms | 稳定网格面积代理/ms² |
|---|---|---:|---:|---:|
| 第一类 | 原结构 | 61.523438 | 29.296875 | 1386.642456 |
| 第一类 | Craig–Bampton | 52.734375 | 24.414063 | 1120.567322 |
| 第一类 | Guyan | 49.804688 | 23.437500 | 995.635986 |
| 第二类 | 原结构 | 54.687500 | 26.367188 | 1189.231873 |
| 第二类 | Craig–Bampton | 51.757813 | 24.414063 | 1022.338867 |
| 第二类 | Guyan | 48.828125 | 23.437500 | 885.963440 |

所以原结构到 Guyan 的两方向损失分别为第一类 `11.718750/5.859375 ms`、第二类 `5.859375/2.929688 ms`。旧稿“第一类每向约 5 ms、第二类接近 10 ms且更严重”的描述与当前统计不一致。

### 5.5 阻断问题四：第三章实际特征方程、增广矩阵和 LQR 没有闭合

1. 当前理论稿没有独立第三章。
2. 旧稿的 `A0/A1/A2/Acal` 仅是通用形式，没有从缩聚矩阵、积分算法和两作动器通道推导这些矩阵。
3. 实际代码用 `det G(z)=0`，但正文未定义 `alpha,C1,C2,K1,K2,H(z),S,DeltaG`。
4. `H` 在不同代码中分别从全零矩阵或单位阵开始，且延迟动力项有左乘和右乘两种写法；必须依据通道物理意义统一，否则会改变系统。
5. 部分代码把 `alpha` 再强制取对角；另一些不取，对应离散模型身份不统一。
6. `solve(det(G)==0,z)` 对含 `z^{-d}` 的有理表达式没有显式清分母、去除伪根和检查残差。
7. LQR 的连续/离散形式及 Q/R 冲突，候选 CB 两个划分脚本还具有相同 SHA-256，不能证明两套划分均独立计算。

### 5.6 阻断问题五：能量指标没有统一定义或产出链

Live Script 保存输出清单：

| 文件 | Guyan/% | Craig–Bampton/% | 与稿件表关系 |
|---|---:|---:|---|
| `energy_zonghe.mlx` | 6.5613 | 6.5535 | 不匹配 |
| `energy_zonghe2.mlx` | 9.7221 | 9.3097 | 不匹配 |
| `Copy_of_energy_zonghe2.mlx` | 9.6488 | 9.3150 | 不匹配 |
| `Copy_2_of_energy_zonghe2.mlx` | -33.7706 | -41.7441 | 不匹配 |
| `energy_zonghe3.mlx` | 59.8619 | 16.9607 | 不匹配 |
| `Copy_of_energy_zonghe3.mlx` | 59.8619 | 15.5000 | 不匹配 |
| `Copy_2_of_energy_zonghe3.mlx` | 39.2658 | 20.2060 | 除以100后可匹配第二类 `0.3927/0.2021` |

唯一匹配第二类表值的 `Copy_2_of_energy_zonghe3.mlx` 注释掉了模态内能量归一化；Guyan 用 `(sum_g-sum_o)/sum_g`，Craig–Bampton 也错误地继续用 `sum_g` 作分母。它既不是稿件的逐坐标相对变化之和，也不是统一的总量相对变化。第一类 `0.3065/0.1879` 在现存 Live Script 输出中找不到。当前没有代码同时加载稳定域与能量结果，也没有阈值 `0.3` 的统计检验。

### 5.7 其他高优先级遗漏

1. **Case I/II 定义冲突**：旧稿的 29 自由度集合 `{21,27}`、`{18,19,29}` 与实际 15 活动自由度集合没有映射。
2. **模态脚本不可验收**：`MAC.m/fguyou.m` 把第一类主坐标顺序写成 `[1,11,6,4,9,14]`；第二类只有 5 个 Guyan 自由度却请求 6 阶；`MAC_full.m` 的 CB 维数不匹配；未用 `T/Tcb` 全场恢复。
3. **固定界面模态数无依据**：`r=3` 硬编码，原 Live Script 甚至有“取前5阶”的错误注释；外层虽已排序，但无截断阶数敏感性或残差验收。
4. **参数来源不清**：`rho=785e3*1.9` 与“steel density”注释不协调；`New_Ps2.m` 实际阻尼比 10%，注释写 5%；需确认是否为已标定等效参数。
5. **子结构脚本不可独立运行**：`New_Full.m` 依赖不在同目录的函数；`New_Ns2.m` 存在 11×11 矩阵与 15×1 向量混用。这些脚本没有进入最终响应再生链。
6. **地震力符号**：若正文使用 `-M Gamma u_g_ddot`，需说明当前 SLX 质量增益和地震数据符号约定。
7. **经验阈值**：旧稿的“NRMSE约7%且频率误差超过10%产生明显失真”及 `Delta E>0.3` 均只能算本算例观察，不能写成理论推论。
8. **试验交叉频率**：`0.5f1` 和 `2f1` 的实验选择规则对应图仍是占位说明，现有资产不足以核验。

### 5.8 最短复现步骤

1. 运行 `D:/Downlad/Matlab/bin/matlab.exe -batch "run('.../need-help/audit_guyan_projection.m')"`，获得 5.2 的矩阵与频率对照。
2. 运行 `D:/Software/python/python.exe need-help/audit_case_metrics.py`，从四个已验收响应 CSV 和两个稳定 MAT 直接生成 5.3、5.4 的 JSON 证据。
3. 解压任一 `.mlx` 的 `matlab/document.xml`，按代码单元读取；本简报第 8 段已完成完整转存。
4. 对照 `regenerate_chapter3_data.m` 的 `build_reduction_models`、`make_state_space`、`run_model_case`，确认缩聚矩阵、输入投影与输出恢复的调用关系。

## 6. 已尝试与初步判断

### 6.1 已尝试并得到的结果

1. **仅做文字比对**：发现独立第三章不存在，但不能判断代码走哪条数学路线。
2. **解析 MATLAB/Simulink**：确认响应链确实使用 `T/Tcb` 做载荷投影和三层位移恢复；同时确认 Guyan 的 `M/C` 未双侧投影。
3. **同参数数值对照**：证明 Guyan 差异会实质改变频率，不是文字符号差异。
4. **从已验收 CSV 重算指标**：定位地震表混用楼层、Chirp 第二类旧表不可追溯。
5. **检查最终稳定域 MAT**：确认其为 0/0.999 掩膜而非最大根模网格；现有复现只能画边界。
6. **遍历能量 Live Script 输出**：定位第二类表值唯一来源及其分母/归一化错误；第一类无代码来源。

### 6.2 此前的外部意见

本问题尚未发送给外部 AI。关联对话只有用户提出“撰写独立第三章、必须服务后续案例”的需求，没有外部模型回复或可采纳方案。

### 6.3 我的初步判断（待反驳，不是已接受结论）

> 我倾向于把当前第二章的合同投影视为权威定义，修正 Guyan 的 `M/C` 并重跑现有两类划分；把第三章改写为与实际 `z` 域特征矩阵一致的路线，并建立一个新的、从缩聚矩阵到原始 `mu(d1,d2)` 网格的单一入口。旧稳定掩膜与能量表只作历史对照，不直接继承。若外部专家认为历史单侧消元在本项目有明确理论依据，或增广状态路线更可靠，请给出严格推导并反驳上述倾向。

## 7. 明确的求助点

请按编号逐条回答：

1. **判定 Guyan 权威算法**：在当前第二章写有 `Mr=T'MT, Cr=T'CT, Kr=T'KT` 的前提下，评估“修正代码并重跑”与“保留历史单侧消元并改写理论”两条路线；给出明确推荐、数学理由和期刊可辩护性。
2. **审查第三章动态刚度推导**：从离散积分与两通道延迟出发，检查第 4.3 段代码导出的 `alpha`、`H(z)`、`G(z)` 是否自洽；特别审查矩阵右除、`alpha` 对角化、`H` 其余对角为零、LQR 项是否应受时滞，以及清分母/伪根问题。
3. **决定特征方程路线**：判断论文应只保留 `det G(z)=0`，还是保留增广矩阵 `Acal`；若两者并存，请给出可直接写入论文的等价条件、推导结构和至少一个数值交叉验证方案。
4. **统一 LQR**：判断应采用连续 CARE 后离散实现还是直接离散 `dlqr`，并说明 Q/R 维度、状态顺序、`DeltaK/DeltaC` 解释及第三章需要披露的参数。
5. **修正案例定义与精度指标**：给出 29 自由度编号到 15 活动自由度的最低限度映射说明；提出一个同时适用于两类划分的频率误差、全坐标 MAC、地震 NRMSE 和 Chirp 分频段 NRMSE 输出规范。
6. **统一或否定能量指标**：审查稿件 `Delta E` 是否有清晰物理/数学意义；若可保留，给出无歧义公式、激励向量定义、归一化和分母；若不可保留，请明确建议删除，并给出更合适的解释量但不要凭空增加无法计算的数据。
7. **给出“不新增结构案例”的最小修复顺序**：区分哪些只需重写、哪些只需后处理现有 CSV、哪些必须重跑现有两类划分、哪些旧结论必须删除或降格为“历史/描述性观察”。
8. **反驳初步判断并检查遗漏**：以审稿人视角列出本简报仍漏掉的最强失效模式，尤其是接口平衡、地震输入符号、固定界面模态截断、根求解稳健性和稳定边界容差。

### 怎样算解决（验收标准）

- 给出一套唯一、互不冲突的第二章 Guyan/CB 矩阵定义和第三章稳定性公式。
- 每个公式明确到矩阵维度、状态/坐标顺序、单位和代码变量名，可由现有 MATLAB 实现。
- 至少设计 10 组延迟点的 `eig(Acal)` 与 `det G=0` 根集合对照；若不保留其中一条路线，应说明删除理由。
- 新稳定性入口保存原始 `mu(d1,d2)`、根残差、失败状态和稳定掩膜；共同 31×67 网格的分类应与最终结论逐点可审计。
- Guyan/CB 投影残差 `norm(Mr-T'*M*T,'fro')/norm(T'*M*T,'fro')`（C、K 同理）小于 `1e-12`。
- Craig–Bampton 固定界面特征残差和质量正交误差建议小于 `1e-10`，并说明 `r=3` 的接受依据。
- 四个精度表和能量表（若保留）均由单一入口产生 CSV/MAT，四位小数舍入误差不超过 `5e-5`，同时保存源哈希。
- 任何“阈值”都必须有预先定义的统计或敏感性依据；否则改为本算例的描述性观察。

### 不需要做/请避开

- 不要建议新增另一座结构或新实验来掩盖当前代码链问题。
- 不要把历史 0/0.999 稳定掩膜称为原始谱半径。
- 不要为了复现旧表值而倒推一套未被代码采用的公式。
- 不要凭文件名判定方法身份；请以变量、矩阵维度、代码内容和哈希为准。

### 期待的答案形式

1. 先给“一页式判决”：保留/重算/删除清单。
2. 再给公式审查，逐式标“正确/需改/无法判断”。
3. 给最小 MATLAB 伪代码或函数接口，覆盖矩阵生成、极点计算、指标输出和验收。
4. 最后列需要补充的信息、潜在审稿质疑和推荐修复顺序。

## 8. 附加上下文

### 8.1 审计证据与来源完整性说明

- 第 8.3 起附当前第二章、旧完整稿、响应生成、模态/NRMSE、稳定性与能量的完整相关代码。
- `.mlx` 并非黑箱：本简报直接从其 OOXML 中按原顺序转存所有文本与代码单元。
- 响应 CSV 每个约 40961×10，全文嵌入会产生数十万行且不增加公式审查信息；因此本简报给出文件哈希、维度、精确重算表和完整读取脚本，原始 CSV 不逐行嵌入。
- 原始 SLX 是压缩 XML 图模型；其关键块参数与连线已在正文列明，完整二进制 SLX 不适合嵌入 Markdown，响应再生入口和模型恢复记录完整附后。

"""
    )

    text_sources: list[tuple[Path, str, str]] = [
        (ACTIVE_TEX, "latex", "当前修订第二章全文：260817/manuscript.tex"),
        (BASELINE_TEX, "latex", "既有英文完整稿全文：manuscript_completed_en.tex"),
        (CHAPTER3 / "可复现代码" / "regenerate_chapter3_data.m", "matlab", "第三章响应计算级再生入口"),
        (CHAPTER3 / "原始来源副本" / "模型与参数原件" / "PDmonicanshu.m", "matlab", "15自由度完整模型参数入口"),
        (CHAPTER3 / "原始来源副本" / "模型与参数原件" / "New_Full.m", "matlab", "历史完整模型脚本 New_Full.m"),
        (CHAPTER3 / "原始来源副本" / "模型与参数原件" / "New_Ps2.m", "matlab", "历史物理子结构脚本 New_Ps2.m"),
        (CHAPTER3 / "原始来源副本" / "模型与参数原件" / "New_Ns2.m", "matlab", "历史数值子结构脚本 New_Ns2.m"),
        (CHAPTER3 / "原始来源副本" / "MLX转存文本" / "untitled_转存.m", "matlab", "第二类划分原缩聚 Live Script 转存"),
        (CHAPTER3 / "原始来源副本" / "MLX转存文本" / "untitled2_转存.m", "matlab", "第一类划分原缩聚 Live Script 转存"),
        (CHAPTER3 / "原始来源副本" / "MLX转存文本" / "New_stability_luxvjie4_转存.m", "matlab", "完整模型动态刚度稳定性代码转存"),
        (CHAPTER3 / "原始来源副本" / "MLX转存文本" / "New_stability_luxvjie_guyan_转存.m", "matlab", "Guyan动态刚度稳定性代码转存"),
        (INNER / "新结构稳定" / "精度指标" / "fguyou.m", "matlab", "频率误差与边界MAC脚本 fguyou.m"),
        (INNER / "新结构稳定" / "精度指标" / "MAC.m", "matlab", "频率误差与边界MAC重复脚本 MAC.m"),
        (INNER / "新结构稳定" / "精度指标" / "MAC_full.m", "matlab", "全模型名义MAC脚本 MAC_full.m"),
        (INNER / "新结构稳定" / "精度指标" / "RMSE_full.m", "matlab", "全时程NRMSE脚本"),
        (INNER / "新结构稳定" / "精度指标" / "RMSE.m", "matlab", "Chirp分频段NRMSE脚本"),
        (INNER / "新结构稳定" / "绘图" / "modal_analysis.m", "matlab", "历史模态参与率对比脚本"),
        (INNER / "新结构稳定" / "绘图" / "modal_energy_ratios_batch.m", "matlab", "批量模态能量比函数"),
        (INNER / "新结构稳定" / "绘图" / "modal_participation_factors.m", "matlab", "模态参与因子函数"),
        (INNER / "新结构稳定" / "绘图" / "calc_MPF.m", "matlab", "另一版模态参与率函数"),
        (INNER / "新结构稳定" / "绘图" / "compute_MAC.m", "matlab", "MAC辅助函数"),
        (INNER / "新结构稳定" / "绘图" / "huitu_2.m", "matlab", "历史稳定掩膜绘图脚本"),
        (CHAPTER4 / "来源与恢复说明.md", "markdown", "第四章稳定域来源边界"),
        (CHAPTER4 / "输入数据" / "第4章稳定域统计.csv", "csv", "第四章稳定域统计CSV"),
        (CHAPTER3 / "来源与恢复说明.md", "markdown", "第三章响应来源与恢复边界"),
        (CHAPTER3 / "验证记录" / "两类子结构映射审计与修正报告.md", "markdown", "两类物理子结构映射审计"),
        (WORKSPACE / "Ref" / "notes" / "Liang2025_实时混合试验缩聚与稳定性.md", "markdown", "硕士论文精读与公式索引"),
        (WORKSPACE / "need-help" / "audit_guyan_projection.m", "matlab", "本次Guyan投影独立审计脚本"),
        (WORKSPACE / "need-help" / "audit_case_metrics.py", "python", "本次响应与稳定掩膜独立审计脚本"),
    ]

    stability_mlx = [
        CHAPTER4 / "原始来源副本" / name
        for name in (
            "luxvjie_ori_LQR2.mlx",
            "luxvjie_ori_LQR3.mlx",
            "luxvjie_guyan_LQR2.mlx",
            "luxvjie_guyan_LQR3.mlx",
            "luxvjie_cb_LQR2.mlx",
            "luxvjie_cb_LQR3.mlx",
        )
    ]
    energy_dir = INNER / "能量指标"
    energy_mlx = [
        energy_dir / name
        for name in (
            "energy_zonghe.mlx",
            "energy_zonghe2.mlx",
            "Copy_of_energy_zonghe2.mlx",
            "Copy_2_of_energy_zonghe2.mlx",
            "energy_zonghe3.mlx",
            "Copy_of_energy_zonghe3.mlx",
            "Copy_2_of_energy_zonghe3.mlx",
            "luxvjie_guyan_LQR2.mlx",
            "luxvjie_guyan_LQR3.mlx",
        )
    ]
    all_paths = [item[0] for item in text_sources] + stability_mlx + energy_mlx
    missing = [path for path in all_paths if not path.is_file()]
    if missing:
        raise FileNotFoundError("以下附录源文件不存在：\n" + "\n".join(str(path) for path in missing))

    parts.append("### 8.2 全部附录源文件 SHA-256 清单\n\n")
    parts.append(source_inventory(all_paths))
    parts.append("\n### 8.3 文本源文件全文\n\n")
    for path, language, title in text_sources:
        parts.append(source_appendix(path, language, title))
        parts.append("\n")

    parts.append("\n### 8.4 六个稳定域候选 Live Script 完整转存\n\n")
    for path in stability_mlx:
        parts.append(mlx_appendix(path))

    parts.append("\n### 8.5 能量与控制参数 Live Script 完整转存\n\n")
    for path in energy_mlx:
        parts.append(mlx_appendix(path))

    parts.append(
        "\n### 8.6 本简报的自包含边界\n\n"
        "本简报已经提供可供专家审查所需的理论全文、代码全文、Live Script 代码单元、"
        "响应/稳定域精确重算、文件哈希和研究约束。未逐行嵌入的只有大型原始 CSV 与二进制 SLX/MAT；"
        "其读取逻辑、尺寸、哈希、关键变量及完整重算脚本均已提供。若外部专家认为仍需某个二进制变量，"
        "请在答复末尾按“文件—变量—用途”明确列出。\n"
    )

    document = "".join(parts)
    OUTPUT.write_text(document, encoding="utf-8", newline="\n")
    chinese_characters = len(re.findall(r"[\u4e00-\u9fff]", document))
    lexical_tokens = len(re.findall(r"[\u4e00-\u9fff]|[A-Za-z0-9_]+", document))
    print(f"OUTPUT={OUTPUT}")
    print(f"BYTES={OUTPUT.stat().st_size}")
    print(f"LINES={len(document.splitlines())}")
    print(f"CHINESE_CHARACTERS={chinese_characters}")
    print(f"LEXICAL_TOKENS={lexical_tokens}")
    print(f"SHA256={sha256(OUTPUT)}")


if __name__ == "__main__":
    main()

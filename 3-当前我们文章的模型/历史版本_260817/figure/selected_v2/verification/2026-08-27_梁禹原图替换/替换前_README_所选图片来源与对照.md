# `manuscript_0823V2` 前五图选定方案与来源

## 使用状态

- Doctor Bego 于 2026-08-23 选定：图1-D、图2-B、图3-C、图4-D、图5-D。
- 本目录中的七个PNG是从 `../image2_图1至图5四方案评审/` 原样复制的稳定引用件；文件名改为ASCII，便于LaTeX跨环境编译。
- 它们是依据论文正文与梁禹大论文素材生成并人工审查的 Image 2 栅格概念图，不是参数化矢量绘图产物。生成提示词与修正过程见 `../image2_图1至图5四方案评审/提示词与审计/Image2_最终提示词与修正轨迹.md`。
- LaTeX插入代码位于 `../../manuscript_0823V2_selected_figures.tex`。原始 `../../manuscript_0823V2.tex` 不作修改。

## 逐图来源、对照与检查重点

| 稿件图片 | 选定方案与引用文件 | 评审源文件 | 应对照的梁禹大论文图片 | 对比检查重点 |
|---|---|---|---|---|
| 图1，`fig:rths-loop` | 图1-D；`fig01_rths_loop_optionD.png` | `图1/图1_方案D_多执行器时滞放大.png` | 图2-1，PDF第21页 | 数值子结构—控制器—多执行器独立时滞—物理子结构的主通道，以及位移反馈和恢复力反馈方向 |
| 图2，`fig:pole-plane` | 图2-B；`fig02_pole_mapping_optionB.png` | `图2/图2_方案B_稳定区域映射.png` | 图4-2，PDF第59页 | `z=e^{s\Delta t}`映射、左半平面与单位圆内部、稳定边界，以及 `s=0\rightarrow z=1` |
| 图3，`fig:benchmark-geometry` | 图3-C；`fig03_benchmark_geometry_optionC.png` | `图3/图3_方案C_构件就地引线.png` | 图2-3，PDF第28页 | 三跨三层、`3×762 mm`与`3×635 mm`、支座类型、W5×16柱和定制工字梁尺寸 |
| 图4(a)，`fig:dof-idealization` | 图4-D(a)；`fig04a_dof_assumptions_optionD.png` | `图4/图4_方案D_a_理想化假设叠加.png` | 图2-4，PDF第29页 | 16个节点、完整29自由度编号、竖向位移约束与同层水平位移合并假设 |
| 图4(b)，`fig:dof-idealization` | 图4-D(b)；`fig04b_dof_idealized_optionD.png` | `图4/图4_方案D_b_最终模型假设摘要.png` | 图2-5，PDF第30页 | 简化后的15自由度、三层水平自由度 `psi1/psi6/psi11` 与12个节点转角 |
| 图5(a)，`fig:division` | 图5-D(a)；`fig05a_divisionI_concept_optionD.png` | `图5/图5_方案D_a_第一类完整框架覆盖.png` | 图3-1，PDF第37页 | 第一类划分的物理外跨下两层、约40%物理范围，以及 `psi1/psi6` 两个受控水平坐标 |
| 图5(b)，`fig:division` | 图5-D(b)；`fig05b_divisionII_concept_optionD.png` | `图5/图5_方案D_b_第二类完整框架覆盖.png` | 图3-2，PDF第37页 | 第二类划分的物理外跨三层、约60%物理范围，`psi1/psi11`受控而`psi6`缩聚重构 |

## 文件完整性

七个引用文件与评审源文件的SHA-256必须逐项一致，具体值见 `selected_figures_manifest.csv`。图6至图10尚未选定，本轮不会在TeX中替换其占位框。

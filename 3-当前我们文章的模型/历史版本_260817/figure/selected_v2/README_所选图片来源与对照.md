# 图1—图5当前梁禹原图与 `_v2` 保留版来源

## 当前使用状态（2026-08-27）

- 本目录7张**无 `_v2` 后缀**的稳定引用文件现为梁禹大论文原图的600 dpi仅裁边版本。现有TeX继续使用原文件名，因此无需修改 `\includegraphics` 语句即可改用梁禹原图。
- 此前由Doctor Bego选定的图1-D、图2-B、图3-C、图4-D和图5-D共7张Image 2栅格概念图，均按原文件主名增加 `_v2` 后缀保留，内容和SHA-256与替换前完全一致。
- 原稳定文件名中的 `optionB`、`optionC`、`optionD` 仅为保持既有TeX引用而保留的历史名称；它们不再表示无后缀文件的当前来源性质。
- 本次没有修改 `manuscript_0826.tex`、`manuscript_0826_anti_defensive.tex` 或 `temp.tex`。替换前README和旧7行清单已原样封存在 `verification/2026-08-27_梁禹原图替换/`。

## 逐图文件、来源与检查位置

| 稿件图片 | 当前稳定引用文件（梁禹原图） | Image 2保留文件 | 应对照的梁禹大论文图片 | PDF页码 | 对比检查重点 |
|---|---|---|---|---:|---|
| 图1，`fig:rths-loop` | `fig01_rths_loop_optionD.png` | `fig01_rths_loop_optionD_v2.png` | 图2-1，RTHS反馈控制闭环图 | 21 | 数值子结构、控制器、作动器/传输系统、物理子结构及位移/力反馈闭环 |
| 图2，`fig:pole-plane` | `fig02_pole_mapping_optionB.png` | `fig02_pole_mapping_optionB_v2.png` | 图4-2，极点平面图 | 59 | 左侧 \(s^R\) 平面稳定区域、右侧 \(z^R\) 单位圆及极点关系 |
| 图3，`fig:benchmark-geometry` | `fig03_benchmark_geometry_optionC.png` | `fig03_benchmark_geometry_optionC_v2.png` | 图2-3，参考结构尺寸 | 28 | 三跨三层、结构尺寸、构件截面尺寸和边界条件 |
| 图4(a)，`fig:dof-idealization` | `fig04a_dof_assumptions_optionD.png` | `fig04a_dof_assumptions_optionD_v2.png` | 图2-4 | 29 | 16个节点与完整自由度编号 |
| 图4(b)，`fig:dof-idealization` | `fig04b_dof_idealized_optionD.png` | `fig04b_dof_idealized_optionD_v2.png` | 图2-5，简化的自由度 | 30 | 简化后的水平平动与节点转动自由度编号 |
| 图5(a)，`fig:division` | `fig05a_divisionI_concept_optionD.png` | `fig05a_divisionI_concept_optionD_v2.png` | 图3-1，第一类子结构自由度选取 | 37 | 第一类子结构划分与红色保留自由度 |
| 图5(b)，`fig:division` | `fig05b_divisionII_concept_optionD.png` | `fig05b_divisionII_concept_optionD_v2.png` | 图3-2，第二类子结构自由度选取 | 37 | 第二类子结构划分与红色保留自由度 |

这里的PDF页码从封面开始计数。梁禹原图的最高保真证据是 `../图1至图5_梁禹大论文原图留档/00_完整源PDF/梁禹手稿.pdf`；当前PNG只是从完整PDF页面在600 dpi下渲染并仅裁边得到的排版使用版。

## 文件完整性与版本边界

- 当前7张无后缀文件、7张 `_v2` 文件的尺寸与SHA-256见 `selected_figures_manifest.csv`。
- 替换前后对应关系和双哈希门结果见 `verification/2026-08-27_梁禹原图替换/替换映射与双哈希门.csv`。
- `verification/` 根目录中早于2026-08-27的页面渲染和验收记录对应此前Image 2版本；本次替换的编译与页面验收统一存放在 `verification/2026-08-27_梁禹原图替换/`，不得混用。
- 这次操作只切换图片资产，不判断梁禹大论文原图的科学表达是否优于Image 2版本。两套图均已保留，可继续对照选择。

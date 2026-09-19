# 图6图内频率与图15变化幅度修订

本包为2026-09-07按Doctor Bego确认选择生成的独立版本；上一版86个文件完整保留。

- `图6排版与图15变化幅度指标修改汇报.html`：主汇报，包含更新图6、图15、全部8个柱值、表5四值及16处完整原文/新文对照；可离线独立阅读。
- `main.tex`：可编辑主稿；`main.pdf`：38页编译稿。图6第24页，图13第31页，图15/表5第33页。
- `submit_figure`：15幅投稿矢量图；本轮只重绘图6、图15，另附600dpi PNG。图6频率注释8pt，位于各自子图内空白处。
- `supplementary_data`：原样保留的模型矩阵和响应时程。
- `refinement_evidence/data/modal_share_deviation.json`及`actuator_share_deviations.csv`：本版指标，以逐坐标绝对相对变化相加。表5依次为0.0455、0.0039、1.3859、0.0423。
- data目录的其余文件为上一版计算输入/来源；其中`explanation_calculations.json`与`new_actuator_share_contributions.csv`含上一版有向指标，用于追溯比较，不是本版表5的取值入口。
- `refinement_evidence/manuscript_changes.json`、`main_changes.diff`、`baseline`：16处修改及旧稿基准。改动继续标红；原42条负间距保持。
- `refinement_evidence/code`：准备、计算、出图、改稿与验收代码。两份plot脚本及revise_metric/build_report脚本可在本包内运行；准备及编译验收脚本记录本次在原工作区tmp的运行环境。

验证：8个柱值通过两条数值路径交叉核对，最大差1.3628e-14；图6的12条曲线和12项频率一致，4组8pt注释与曲线有2.5pt避让；主稿41项一致性/编译检查与报告13项浏览器检查通过。报告5页A4打印已渲染检查。

主稿就地编译：pdflatex main.tex → bibtex main → pdflatex main.tex两遍。全部模板、文献和图件均已包含。原负间距造成的部分公式紧贴/重叠按用户要求保留；结构模型和闭环稳定性研究范围未扩大。本轮修改已完成，待用户审阅。

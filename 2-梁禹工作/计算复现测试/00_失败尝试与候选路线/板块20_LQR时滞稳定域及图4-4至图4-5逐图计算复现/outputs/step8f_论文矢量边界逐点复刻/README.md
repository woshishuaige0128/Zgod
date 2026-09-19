# 图 4-4 与图 4-5：论文矢量边界逐点复刻

## 结论与证据级别

本目录完成的是**绘图级复刻**：脚本直接读取《梁禹手稿.pdf》物理页 70 中图 4-4、图 4-5 的六条矢量折线，恢复论文坐标轴上的整数采样步，并重新绘图。六个 CSV 与论文 PDF 矢量路径逐点一致。

本目录**不是计算级复现**。它没有从质量、阻尼、刚度矩阵重新计算谱半径，也不能证明论文曲线背后的数值程序正确。

## 坐标单位

- `tau1_step`、`tau2_step` 保留论文横纵坐标的采样步数。
- 论文说明采样周期为 `dt = 1/1024 s`；本目录没有把坐标擅自换成毫秒。
- 图 4-4 的 Guyan 曲线最右列为 `tau1_step=58`，并保留 `tau2_step=2,3` 两个点。右侧低点因此接近横轴。

## 数据来源与自动提取

- 源 PDF：`D:\JZ_PhD\10_论文_Papers\Li\RHTS\梁禹手稿.pdf`
- 源 PDF SHA-256：`DDA04CE3DBFF6A5DCE33E6A7D07191F5A33D27F025174087EE395DFE4CF9D5D1`
- 物理页：70（PyMuPDF 页索引 69）
- 图 4-4 的 Original、CB、Guyan 折线对象：19、92、162
- 图 4-5 的 Original、CB、Guyan 折线对象：260、330、387

脚本按每条矢量路径中唯一横纵坐标的次序恢复整数采样步，避免手抄。验收脚本会重新打开源 PDF、重新提取六条路径，并与 CSV 的顺序和每个坐标逐点比较。

## 一键重建与验收

```powershell
$env:PYTHONIOENCODING = 'utf-8'
& 'D:\Software\python\python.exe' '.\code\rebuild_thesis_vector_trace.py'
& 'D:\Software\python\python.exe' '.\code\validate_thesis_vector_trace.py'
& 'D:\Software\python\python.exe' '.\code\check_repeatability.py'
```

应在本 README 所在目录运行。验收成功时，`validation\逐点验收摘要.json` 中的 `overall_status` 为 `PASS`，并且 `source_pdf_vector_grid_path_point_match_100_percent` 为 `true`。

## 目录内容

- `code/`：可重跑提取、绘图和验收脚本。
- `data/`：六条论文矢量边界 CSV；每行是路径中的一个有序点。
- `figures/`：两张矢量 PDF 和两张 600 dpi PNG。
- `validation/`：提取元数据、逐项验收、验收摘要和文件 SHA-256 清单。
- `visual_qa/`：由最终 PDF 重新渲染的 300 dpi 图片，用于肉眼检查。
- `MRren与两图差异说明.md`：用直观语言解释 `MRren`、旧图端点错误及计算证据边界。
- `validation/图4-4图4-5代码映射.csv`：六条曲线的现存数据、候选计算脚本和裁决。

## 现存 MAT 候选的标签修正

目录 `figure\第4章_缩聚对试验稳定性的影响\作者现存MAT原脚本复跑候选` 已统一采用“作者现存MAT原脚本复跑候选”文件名；验收 JSON 也明确写为候选复跑，并记录四条缩聚曲线不匹配论文。此前带“论文忠实复刻”误名的 10 个派生文件已移到可恢复审计目录 `tmp\chapter4_faithful_repeatability\obsolete_mislabeled_outputs_20260827`，不再出现在正式候选目录中。

# `manuscript_0823V2` 图6至图10计算结果图

## 方法样式

- Original：深灰色 `#555555`、虚线、圆标记。
- Craig--Bampton：红色 `#EE6677`、实线、方形标记。
- Guyan：蓝色 `#4477AA`、点划线、三角标记。
- 长时程曲线不放标记以减少噪声；局部放大窗和稳定边界保留标记，保证灰度打印仍可区分。
- Computer Modern 9 pt；坐标轴0.8 pt；四边向内刻度；无标题、无网格、无边框图例。

## 逐图源码、输入与梁禹大论文对照

| 稿件图 | 输出 | 独立源码 | 输入数据 | 梁禹大论文对照 | 检查重点 |
|---|---|---|---|---|---|
| 图6，`fig:eq-div1` | `PDF/fig06_eq_div1.pdf` | `源码/06_绘制fig06_eq_div1_第一类ElCentro响应.py` | `第一类划分_ElCentro地震响应.csv` | 图3-6第42页；图3-8第43页 | 第一类划分一层/三层；全时程、10–11 s和21.5–22.5 s |
| 图7，`fig:eq-div2` | `PDF/fig07_eq_div2.pdf` | `源码/07_绘制fig07_eq_div2_第二类ElCentro响应.py` | `第二类划分_ElCentro地震响应.csv` | 图3-9第44页；图3-10第45页 | 第二类划分一层/三层；Guyan在10–11 s的幅值和相位偏差 |
| 图8，`fig:chirp-div1` | `PDF/fig08_chirp_div1.pdf` | `源码/08_绘制fig08_chirp_div1_第一类Chirp响应.py` | `第一类划分_Chirp响应.csv` | 唯一编号图3-11第46页；图3-13第47–48页 | 第一类划分一层/三层；全时程、13–14 s和38–38.3 s |
| 图9，`fig:chirp-div2` | `PDF/fig09_chirp_div2.pdf` | `源码/09_绘制fig09_chirp_div2_第二类Chirp响应.py` | `第二类划分_Chirp响应.csv` | 唯一编号图3-14第48页下部；图3-15第49页 | 第二类划分一层/三层；Guyan在共振段和高频段的偏差 |
| 图10，`fig:stability-domain` | `PDF/fig10_stability_domain.pdf` | `源码/10_绘制fig10_stability_domain_双划分稳定域.py` | 图4-4与图4-5稳定域边界CSV | 图4-4和图4-5，均第70页 | 两类划分、三方法边界身份、毫秒坐标与边界排序 |

## 如何重新生成与验证

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" ".\源码\生成图6至图10.py"
& "D:\Software\python\python.exe" ".\源码\验证图6至图10.py"
```

若只重画一张，运行对应的06至10号独立入口。每个入口只负责一张稿件图片。

## 证据边界

- 图6至图9直接读取既有已验收响应快照，是计算结果的绘图级重新排版；本目录没有重跑Simulink。
- 图10读取历史稳定掩膜导出的边界快照，只能称为稳定边界的绘图级复现；本目录没有从特征方程重新计算谱半径或闭环极点。

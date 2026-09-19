# 第4章“系统缩聚对RTHS试验稳定性的影响”图片交付

本目录包含手稿第4章的5张图片。图4-1至图4-3为依据原稿证据新建的矢量重绘；图4-4与图4-5由原MATLAB最终绘图数据按原稳定判据恢复边界并重新绘制。

## 一键生成

使用系统指定Python，可从任意当前目录执行：

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" "D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\figure\第4章_缩聚对试验稳定性的影响\可复现代码\生成第4章全部图片.py"
```

该入口会重新计算来源SHA-256、恢复两类稳定域边界CSV/MAT，并真正调用5张图的绘制函数生成PDF和PNG。

## 自动验收

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" "D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\figure\第4章_缩聚对试验稳定性的影响\可复现代码\验收第4章交付物.py"
```

验收脚本检查清单完整性、相对路径、5份PDF页数/字体/纯矢量性、5份PNG像素和DPI，以及稳定域清洗MAT的关键字段。

## 关键文件

- `章节交付清单.csv`：每张图的代码、数据、PDF、PNG、来源、恢复方式和状态。
- `来源与恢复说明.md`：图4-1外部引用身份、图4-4/4-5稳定域证据链和数据异常处理。
- `输入数据/第4章稳定域统计.csv`：最大时滞、边界面积、稳定网格面积代理与源数组尺寸。
- `原始来源副本/SHA256清单.csv`：全部保存来源证据的哈希。
- `验证记录/`：逐图人工视觉与数值验证记录、PDF渲染预览和自动验收JSON。

## 诚实边界

六个稳定域候选Live Script依赖上游工作区矩阵，且存在循环/保存被注释、方法名与保存名混用等问题。本交付已可靠复现最终稳定域图片及其数据边界，但不声称从零重新完成全部闭环极点网格扫描；详细证据见`来源与恢复说明.md`。

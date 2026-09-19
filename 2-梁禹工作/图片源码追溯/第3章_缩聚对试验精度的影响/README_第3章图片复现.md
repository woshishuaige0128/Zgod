# 第3章图片复现

## 一键重绘 13 张图

可从任意当前目录运行：

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" "D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\figure\第3章_缩聚对试验精度的影响\可复现代码\生成第3章全部图片.py"
```

该入口只读取已经保存的真实仿真 MAT 数据，重绘图3-1、图3-2、图3-5至图3-15，并覆盖更新 `PDF结果`、`PNG结果`、图片文件/样式验证表和26项最终图片 SHA-256；静态的 `章节交付清单.csv` 用于逐图定位这些产物。

## 单独重绘任意一张图

`可复现代码` 中另有13个以“图号 + 中文图意”命名的单图入口，例如：

```powershell
$env:PYTHONIOENCODING = "utf-8"
& "D:\Software\python\python.exe" "D:\JZ_PhD\10_论文_Papers\Li\RHTS\liangyustability-master\figure\第3章_缩聚对试验精度的影响\可复现代码\图3-15_绘制第二类Chirp三层响应.py"
```

每个入口仅重绘本图对应的PDF与PNG，并同步重建共享的26项最终图片哈希清单。13个入口与唯一ID的逐一映射见 `章节交付清单.csv`，批量实跑结果见 `验证记录/13个中文单图入口运行验证.csv`。

## 从干净 MATLAB 会话再生真实数据

```powershell
& "D:\Downlad\Matlab\bin\matlab.exe" -batch "run('D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master/figure/第3章_缩聚对试验精度的影响/可复现代码/regenerate_chapter3_data.m')"
```

成功标准：退出码 0，日志结尾包含“五组响应数据与统计均通过”和“已刷新14项最终生成数据SHA-256”，并生成 5 组响应 MAT/CSV。随后再运行 Python 一键重绘入口。

## 交付定位

- `章节交付清单.csv`：13 张图逐图定位代码、数据、来源、PDF、PNG 和验证记录。
- `来源与恢复说明.md`：原始数据链、模型适配、方法/楼层/单位映射与图3-15修复依据。
- `验证记录/再生第3章真实仿真数据_日志.txt`：真实 MATLAB/Simulink 运行日志。
- `验证记录/第3章仿真响应数值统计.csv`：每个工况、楼层、方法的峰值、RMS 和末值。
- `验证记录/第3章全部图片文件与样式验证.csv`：输出尺寸、600 dpi 和文件完整性检查。
- `原始来源副本/SHA256清单.csv`：本章25个原始来源副本的相对路径、SHA-256、字节数和时间戳。
- `验证记录/第3章生成数据_SHA256.csv`：最终用于出图的14个响应/激励/统计文件哈希；不含旧错误映射审计留存；每次MATLAB数据再生成功后自动刷新。
- `验证记录/第3章最终图片_SHA256.csv`：13个PDF和13个PNG最终产物哈希；每次总图或单图重绘后自动刷新。

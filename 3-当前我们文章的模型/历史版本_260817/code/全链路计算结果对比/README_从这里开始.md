# 全链路计算结果对比

## 结论

- Fig.6--Fig.9：本轮真实Simulink全链新算与当前四份CSV逐字节相同，属于现存代码/必要适配路线的计算级复现。
- Fig.10：六模型链×四候选的49,848点全网格计算通过，但R01--R04对论文六条边界均为0/6命中。

## 本包如何独立重画比较图

在任意当前目录运行：

```powershell
$env:PYTHONIOENCODING='utf-8'
& 'D:\\Software\\python\\python.exe' '本文件夹\\code\\生成全链路对比图与汇报.py'
```

默认模式只读取本文件夹内的相对路径数据，不依赖原仓库。`--refresh-data`只用于原仓库仍在本机时重新收集权威全链输出。

## 完整计算链入口

### Fig.6--Fig.9

```powershell
$env:BOARD18_RUN_ID='run1'
& 'D:\\Downlad\\Matlab\\bin\\matlab.exe' -batch "run('D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master/test/00_失败尝试与候选路线/板块18_图3-5至图3-15逐图计算复现/code/run_board18_adapted.m')"
```

### Fig.10

```powershell
& 'D:\\Downlad\\Matlab\\bin\\matlab.exe' -batch "addpath('D:/JZ_PhD/10_论文_Papers/Li/RHTS/liangyustability-master/test/00_失败尝试与候选路线/板块20_LQR时滞稳定域及图4-4至图4-5逐图计算复现/code'); run_board20_step8e_fullgrid_matlab('full');"
```

完整计算入口需要原板块冻结输入；比较图入口不需要。
